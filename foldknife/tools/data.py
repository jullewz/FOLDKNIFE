"""Data tools: CSV, JSON, SQLite, Excel (XLSX without libraries), charts and grouping."""
from __future__ import annotations

import csv
import io
import json
import math
import re
import sqlite3
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

from ..core import ui
from ..core.registry import tool
from ..core.utils import offer_save

# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------


def sniff_dialect(sample: str) -> csv.Dialect | type[csv.Dialect]:
    try:
        return csv.Sniffer().sniff(sample[:8192], delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def read_csv(path: Path) -> tuple[list[str], list[list[str]], str]:
    text = ui.read_text_file(path)
    dialect = sniff_dialect(text)
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if r]
    if not rows:
        return [], [], getattr(dialect, "delimiter", ",")
    headers = [h.strip() or f"column{i + 1}" for i, h in enumerate(rows[0])]
    width = len(headers)
    data = [r + [""] * (width - len(r)) if len(r) < width else r[:width] for r in rows[1:]]
    return headers, data, getattr(dialect, "delimiter", ",")


def write_csv(path: Path, headers: list[str], rows: list[list[Any]], delimiter: str = ";") -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=delimiter)
        w.writerow(headers)
        w.writerows(rows)


def to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", "").replace(" ", "").replace("€", "").replace("%", "")
    if not s:
        return None
    if s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(",", "")
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def column_stats(values: list[str]) -> dict[str, Any]:
    non_empty = [v for v in values if str(v).strip()]
    nums = [n for n in (to_number(v) for v in non_empty) if n is not None]
    out: dict[str, Any] = {"rows": len(values), "empty": len(values) - len(non_empty), "distinct values": len(set(non_empty))}
    if non_empty and len(nums) >= len(non_empty) * 0.9:
        out["type"] = "number"
        out.update({"sum": sum(nums), "mean": statistics.fmean(nums), "median": statistics.median(nums),
                    "min": min(nums), "max": max(nums)})
        if len(nums) > 1:
            out["stdev"] = statistics.stdev(nums)
    else:
        out["type"] = "text"
        lengths = [len(v) for v in non_empty] or [0]
        out["length"] = f"{min(lengths)}–{max(lengths)} characters"
    out["most common"] = ", ".join(f"{v} ({c})" for v, c in Counter(non_empty).most_common(3))
    return out


OPERATORS = ["=", "!=", ">", "<", ">=", "<=", "contains", "does not contain", "starts with", "ends with", "regex", "empty", "not empty"]


def row_matches(value: str, op: str, target: str) -> bool:
    if op == "empty":
        return not value.strip()
    if op == "not empty":
        return bool(value.strip())
    if op in (">", "<", ">=", "<="):
        a, b = to_number(value), to_number(target)
        if a is None or b is None:
            return False
        return {"<": a < b, ">": a > b, ">=": a >= b, "<=": a <= b}[op]
    if op in ("=", "!="):
        a, b = to_number(value), to_number(target)
        eq = (a == b) if a is not None and b is not None else value.strip().lower() == target.strip().lower()
        return eq if op == "=" else not eq
    v, t = value.lower(), target.lower()
    if op == "contains":
        return t in v
    if op == "does not contain":
        return t not in v
    if op == "starts with":
        return v.startswith(t)
    if op == "ends with":
        return v.endswith(t)
    if op == "regex":
        return re.search(target, value) is not None
    raise ValueError(op)


def choose_column(headers: list[str], prompt: str = "Column") -> int:
    return ui.choose(prompt, headers)


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------

def json_tree(obj: Any, indent: str = "", key: str | None = None, depth: int = 0, max_depth: int = 6,
              max_items: int = 25) -> Iterator[str]:
    label = ui.cyan(f"{key}: ") if key is not None else ""
    if isinstance(obj, dict):
        yield f"{indent}{label}{ui.gray('{')}{ui.gray(f' {len(obj)} keys') if obj else ''}"
        if depth >= max_depth:
            yield f"{indent}  {ui.gray('…')}"
        else:
            for i, (k, v) in enumerate(obj.items()):
                if i >= max_items:
                    yield f"{indent}  {ui.gray(f'… and {len(obj) - max_items} more')}"
                    break
                yield from json_tree(v, indent + "  ", str(k), depth + 1, max_depth, max_items)
        yield f"{indent}{ui.gray('}')}"
    elif isinstance(obj, list):
        yield f"{indent}{label}{ui.gray('[')}{ui.gray(f' {len(obj)} items') if obj else ''}"
        if depth >= max_depth:
            yield f"{indent}  {ui.gray('…')}"
        else:
            for i, v in enumerate(obj):
                if i >= max_items:
                    yield f"{indent}  {ui.gray(f'… and {len(obj) - max_items} more')}"
                    break
                yield from json_tree(v, indent + "  ", f"[{i}]", depth + 1, max_depth, max_items)
        yield f"{indent}{ui.gray(']')}"
    elif isinstance(obj, str):
        yield f"{indent}{label}{ui.green(json.dumps(obj, ensure_ascii=False)[:200])}"
    elif isinstance(obj, bool):
        yield f"{indent}{label}{ui.magenta(str(obj).lower())}"
    elif obj is None:
        yield f"{indent}{label}{ui.gray('null')}"
    else:
        yield f"{indent}{label}{ui.yellow(str(obj))}"


def _path_tokens(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for part in re.findall(r"[^.\[\]]+|\[[^\]]*\]", path.strip().lstrip("$").lstrip(".")):
        if part.startswith("["):
            inner = part[1:-1].strip().strip("'\"")
            tokens.append(int(inner) if re.fullmatch(r"-?\d+", inner) else inner)
        else:
            tokens.append(part)
    return tokens


def json_query(obj: Any, path: str) -> list[Any]:
    """Simple path query: users[0].name, users[*].email, items.*.id"""
    current = [obj]
    for tok in _path_tokens(path):
        nxt = []
        for node in current:
            if tok == "*":
                if isinstance(node, dict):
                    nxt.extend(node.values())
                elif isinstance(node, list):
                    nxt.extend(node)
            elif isinstance(tok, int) and isinstance(node, list):
                if -len(node) <= tok < len(node):
                    nxt.append(node[tok])
            elif isinstance(node, dict) and str(tok) in node:
                nxt.append(node[str(tok)])
        current = nxt
    return current


def json_diff(a: Any, b: Any, path: str = "$") -> list[tuple[str, str, Any, Any]]:
    diffs: list[tuple[str, str, Any, Any]] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() | b.keys():
            p = f"{path}.{k}"
            if k not in b:
                diffs.append((p, "removed", a[k], None))
            elif k not in a:
                diffs.append((p, "added", None, b[k]))
            else:
                diffs.extend(json_diff(a[k], b[k], p))
    elif isinstance(a, list) and isinstance(b, list):
        for i in range(max(len(a), len(b))):
            p = f"{path}[{i}]"
            if i >= len(b):
                diffs.append((p, "removed", a[i], None))
            elif i >= len(a):
                diffs.append((p, "added", None, b[i]))
            else:
                diffs.extend(json_diff(a[i], b[i], p))
    elif a != b:
        diffs.append((path, "changed", a, b))
    return sorted(diffs)


# --------------------------------------------------------------------------
# XLSX (Office Open XML) without libraries
# --------------------------------------------------------------------------

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def col_letter(idx: int) -> str:
    s = ""
    idx += 1
    while idx:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch.upper()) - 64
    return n - 1


def xlsx_sheets(path: Path) -> list[tuple[str, str]]:
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target", "") for r in rels.iter(f"{{{NS_PKG_REL}}}Relationship")}
    out = []
    for s in wb.iter(f"{{{NS_MAIN}}}sheet"):
        rid = s.get(f"{{{NS_REL}}}id")
        target = targets.get(rid, "")
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        out.append((s.get("name", "?"), target))
    return out


def read_xlsx(path: Path, sheet: int = 0) -> list[list[str]]:
    sheets = xlsx_sheets(path)
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in sst.iter(f"{{{NS_MAIN}}}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS_MAIN}}}t")))
        root = ET.fromstring(z.read(sheets[sheet][1]))
    rows: list[list[str]] = []
    for row in root.iter(f"{{{NS_MAIN}}}row"):
        r_idx = int(row.get("r", len(rows) + 1)) - 1
        while len(rows) < r_idx:
            rows.append([])
        cells: list[str] = []
        for c in row.iter(f"{{{NS_MAIN}}}c"):
            ref = c.get("r", "")
            m = re.match(r"([A-Z]+)", ref)
            ci = col_index(m.group(1)) if m else len(cells)
            while len(cells) < ci:
                cells.append("")
            t = c.get("t", "n")
            v = c.find(f"{{{NS_MAIN}}}v")
            if t == "s" and v is not None:
                val = shared[int(v.text or 0)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{NS_MAIN}}}t"))
            elif t == "b" and v is not None:
                val = "TRUE" if v.text == "1" else "FALSE"
            else:
                val = v.text if v is not None and v.text is not None else ""
                if t == "n" and val and re.fullmatch(r"-?\d+\.\d+0{6,}\d*", val):
                    val = str(round(float(val), 10))
            cells.append(val)
        rows.append(cells)
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) for r in rows]


def write_xlsx(path: Path, rows: list[list[Any]], sheet_name: str = "Sheet1", bold_header: bool = True) -> None:
    def cell(ci: int, ri: int, value: Any, style: int) -> str:
        ref = f"{col_letter(ci)}{ri + 1}"
        s = f' s="{style}"' if style else ""
        num: float | None = None
        if ri > 0:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                num = float(value)
            elif isinstance(value, str) and re.fullmatch(r"-?\d+([.,]\d+)?", value.strip()) \
                    and not re.match(r"-?0\d", value.strip()):
                num = to_number(value)
        if num is not None:
            shown = str(int(num)) if num.is_integer() and abs(num) < 1e15 else repr(num)
            return f'<c r="{ref}"{s}><v>{shown}</v></c>'
        text = xml_escape(str(value if value is not None else ""))
        return f'<c r="{ref}" t="inlineStr"{s}><is><t xml:space="preserve">{text}</t></is></c>'

    sheet_rows = "".join(
        f'<row r="{ri + 1}">' + "".join(cell(ci, ri, v, 1 if (ri == 0 and bold_header) else 0) for ci, v in enumerate(r)) + "</row>"
        for ri, r in enumerate(rows))
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{NS_PKG_REL}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}"><sheets>'
            f'<sheet name="{xml_escape(sheet_name[:31])}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{NS_PKG_REL}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>',
        "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<styleSheet xmlns="{NS_MAIN}">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            '</styleSheet>',
        "xl/worksheets/sheet1.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<worksheet xmlns="{NS_MAIN}"><sheetData>{sheet_rows}</sheetData></worksheet>',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------

def line_chart(values: list[float], width: int = 60, height: int = 14) -> list[str]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    dots_w, dots_h = width * 2, height * 4
    grid = [[0] * width for _ in range(height)]
    bits = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]]
    prev = None
    for dx in range(dots_w):
        pos = dx / max(1, dots_w - 1) * (len(values) - 1)
        i = int(pos)
        frac = pos - i
        v = values[i] if i + 1 >= len(values) else values[i] * (1 - frac) + values[i + 1] * frac
        row = int(round((hi - v) / span * (dots_h - 1)))
        rows = range(min(prev, row), max(prev, row) + 1) if prev is not None else [row]
        for r in rows:
            grid[r // 4][dx // 2] |= bits[r % 4][dx % 2]
        prev = row
    out = []
    for r in range(height):
        label = (f"{hi:.4g}" if r == 0 else f"{lo:.4g}" if r == height - 1 else "").rjust(9)
        out.append(ui.gray(label) + " " + ui.c("".join(chr(0x2800 + b) if b else " " for b in grid[r]), "bright_cyan"))
    return out


PIE_COLORS = ["bright_red", "bright_yellow", "bright_green", "bright_cyan", "bright_blue", "bright_magenta", "red", "green"]


def pie_bar(items: list[tuple[str, float]], width: int = 60) -> list[str]:
    total = sum(v for _, v in items) or 1
    bar = ""
    legend = []
    for i, (label, v) in enumerate(items):
        n = max(1, round(v / total * width)) if v else 0
        color = PIE_COLORS[i % len(PIE_COLORS)]
        bar += ui.c("█" * n, color)
        legend.append(f"  {ui.c('■', color)} {label}: {v:g} ({v / total * 100:.1f} %)")
    return [bar] + legend


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("data", "data-csv-viewer", "CSV viewer", "Opens a CSV or Excel CSV file as a table (also with ; separators)", ("csv", "taulukko", "excel"))
def csv_view_tool() -> None:
    path = ui.ask_path("CSV file", kind="file")
    headers, rows, delim = read_csv(path)
    ui.info(f"{len(rows)} rows × {len(headers)} columns (delimiter {delim!r})")
    cols = ui.ask("Columns to show as numbers separated by commas (empty = all)", allow_empty=True)
    idx = [int(x) - 1 for x in re.findall(r"\d+", cols) if 0 < int(x) <= len(headers)] or list(range(len(headers)))
    page = max(5, ui.term_height() - 8)
    pos = 0
    while pos < len(rows):
        ui.table([[r[i] for i in idx] for r in rows[pos:pos + page]], [headers[i] for i in idx], max_col_width=30)
        pos += page
        if pos >= len(rows):
            break
        if input(ui.gray(f"-- rows {pos}/{len(rows)}: Enter = next, q = quit -- ")).strip().lower() == "q":
            break


@tool("data", "data-csv-column-statistics", "CSV column statistics", "Types, blanks, sums, averages and most common values for every column",
      ("csv", "tilasto", "analyysi", "profiili"))
def csv_stats_tool() -> None:
    headers, rows, _ = read_csv(ui.ask_path("CSV file", kind="file"))
    for i, h in enumerate(headers):
        st = column_stats([r[i] for r in rows])
        print(ui.c(f"\n{h}", "bold", "bright_cyan") + ui.gray(f"  ({st.pop('type')})"))
        ui.print_kv([(k, ui.fi_num(v, 2) if isinstance(v, float) else v) for k, v in st.items()])


@tool("data", "data-filter-and-sort-csv", "Filter and sort CSV", "Filter rows by conditions, sort and save to a new file",
      ("csv", "filter", "suodata", "lajittele", "sort"))
def csv_filter_tool() -> None:
    path = ui.ask_path("CSV file", kind="file")
    headers, rows, delim = read_csv(path)
    filtered = rows
    while ui.ask_yes_no(f"Add a condition? ({len(filtered)} rows now)", filtered is rows):
        ci = choose_column(headers)
        op = OPERATORS[ui.choose("Condition", OPERATORS)]
        target = ui.ask("Value", allow_empty=True) if op not in ("empty", "not empty") else ""
        try:
            filtered = [r for r in filtered if row_matches(r[ci], op, target)]
        except re.error as exc:
            ui.error(f"Invalid regex: {exc}")
    if ui.ask_yes_no("Sort?", False):
        ci = choose_column(headers, "Sort by column")
        desc = ui.ask_yes_no("Descending order?", False)
        filtered = sorted(filtered, key=lambda r: (to_number(r[ci]) is None, to_number(r[ci]) or 0, r[ci].lower()), reverse=desc)
    ui.table(filtered[:20], headers, max_col_width=25)
    ui.info(f"{len(filtered)} / {len(rows)} rows")
    if ui.ask_yes_no("Save?", True):
        target = Path(ui.ask("File", path.stem + "-suodatettu.csv"))
        write_csv(target, headers, filtered, delim)
        ui.success(f"Saved: {target.resolve()}")


@tool("data", "data-combine-csv-files", "Combine CSV files", "Stacks files with the same shape or joins them on a key column",
      ("csv", "merge", "join", "merge"))
def csv_merge_tool() -> None:
    mode = ui.choose("Method", ["Stack on top of each other (same columns)", "Join on a key"])
    if mode == 0:
        folder = ui.ask_path("Folder containing the CSVs", kind="dir", default=".")
        files = sorted(folder.glob("*.csv"))
        all_headers: list[str] = []
        all_rows: list[dict[str, str]] = []
        for f in files:
            h, rows, _ = read_csv(f)
            for col in h + ["source"]:
                if col not in all_headers:
                    all_headers.append(col)
            all_rows.extend({**dict(zip(h, r)), "source": f.name} for r in rows)
        target = Path(ui.ask("Save", "merged.csv"))
        write_csv(target, all_headers, [[r.get(c, "") for c in all_headers] for r in all_rows])
        ui.success(f"{len(files)} files, {len(all_rows)} rows → {target.resolve()}")
        return
    ha, ra, _ = read_csv(ui.ask_path("Left file", kind="file"))
    hb, rb, _ = read_csv(ui.ask_path("Right file", kind="file"))
    ka = choose_column(ha, "Key in left")
    kb = choose_column(hb, "Key in right")
    kind = ui.choose("Join", ["Inner join (only common)", "Left join (everything from left)"])
    index: dict[str, list[list[str]]] = defaultdict(list)
    for r in rb:
        index[r[kb].strip().lower()].append(r)
    extra = [h for i, h in enumerate(hb) if i != kb]
    out = []
    for r in ra:
        matches = index.get(r[ka].strip().lower())
        if matches:
            for m in matches:
                out.append(r + [v for i, v in enumerate(m) if i != kb])
        elif kind == 1:
            out.append(r + [""] * len(extra))
    target = Path(ui.ask("Save", "liitetty.csv"))
    write_csv(target, ha + extra, out)
    ui.success(f"{len(out)} rows → {target.resolve()}")


@tool("data", "data-json-viewer", "JSON viewer and query", "Shows JSON as a colourful tree and fetches values by path (users[*].name)",
      ("json", "puu", "jq", "polku", "query"))
def json_tool() -> None:
    raw = ui.get_text("JSON (or @file)")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        ui.error(f"Invalid JSON: {exc}")
        return
    ui.paginate(list(json_tree(obj)))
    while True:
        q = ui.ask("Path query (e.g. data[0].name, items[*].id – empty quits)", allow_empty=True)
        if not q:
            break
        res = json_query(obj, q)
        ui.info(f"{len(res)} matches")
        for r in res[:50]:
            print("  " + json.dumps(r, ensure_ascii=False)[:300])


@tool("data", "data-json-diff", "JSON diff", "Shows added, removed and changed fields between two JSONs",
      ("json", "diff", "vertaa"))
def json_diff_tool() -> None:
    try:
        a = json.loads(ui.get_text("First JSON"))
        b = json.loads(ui.get_text("Second JSON"))
    except json.JSONDecodeError as exc:
        ui.error(f"Invalid JSON: {exc}")
        return
    diffs = json_diff(a, b)
    if not diffs:
        ui.success("The contents are identical.")
        return
    for path, kind, old, new in diffs[:300]:
        if kind == "added":
            print(f"  {ui.green('+')} {path} = {json.dumps(new, ensure_ascii=False)[:120]}")
        elif kind == "removed":
            print(f"  {ui.red('-')} {path} = {json.dumps(old, ensure_ascii=False)[:120]}")
        else:
            print(f"  {ui.yellow('~')} {path}: {json.dumps(old, ensure_ascii=False)[:60]} → {json.dumps(new, ensure_ascii=False)[:60]}")
    ui.info(f"{len(diffs)} differences")


@tool("data", "data-sqlite-browser", "SQLite browser", "Opens a .db file: tables, schema, SQL queries and CSV export",
      ("sqlite", "sql", "tietokanta", "database", "db"))
def sqlite_tool() -> None:
    path = ui.ask_path("SQLite file (created if new)", must_exist=False, default="database.db")
    con = sqlite3.connect(str(path))
    try:
        while True:
            tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            rows = []
            for t in tables:
                n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                cols = ", ".join(c[1] for c in con.execute(f'PRAGMA table_info("{t}")'))
                rows.append((t, n, cols[:60]))
            ui.table(rows or [("(no tables)", "", "")], ["Table", "Rows", "Columns"])
            print(ui.gray("Type an SQL query, '.export TABLE' exports to CSV, '.schema TABLE', empty quits."))
            sql = input(ui.c("sql> ", "bright_green")).strip()
            if not sql:
                break
            if sql.startswith(".export "):
                t = sql[8:].strip()
                cur = con.execute(f'SELECT * FROM "{t}"')
                target = Path(f"{t}.csv")
                write_csv(target, [d[0] for d in cur.description], cur.fetchall())
                ui.success(f"Exported: {target.resolve()}")
                continue
            if sql.startswith(".schema "):
                t = sql[8:].strip()
                ui.table([(c[1], c[2], "yes" if c[3] else "", c[4] if c[4] is not None else "", "PK" if c[5] else "")
                          for c in con.execute(f'PRAGMA table_info("{t}")')], ["Column", "Type", "NOT NULL", "Default", ""])
                continue
            try:
                cur = con.execute(sql)
                if cur.description:
                    data = cur.fetchmany(500)
                    ui.table(data, [d[0] for d in cur.description], max_col_width=30)
                    ui.info(f"{len(data)} rows" + (" (showing the first 500)" if len(data) == 500 else ""))
                else:
                    if not sql.lower().startswith(("insert", "update", "delete", "create", "drop", "alter", "replace")) or \
                            ui.ask_yes_no("Save the changes?", True):
                        con.commit()
                        ui.success(f"OK, {cur.rowcount if cur.rowcount >= 0 else 0} rows changed.")
                    else:
                        con.rollback()
            except sqlite3.Error as exc:
                ui.error(f"SQL error: {exc}")
    finally:
        con.close()


@tool("data", "data-terminal-charts", "Terminal charts", "Bar, line and pie charts from your own numbers or CSV columns",
      ("kaavio", "chart", "graafi", "bar", "visualisointi"))
def chart_tool() -> None:
    src = ui.choose("Data", ["Type 'name value' lines", "CSV file columns"])
    items: list[tuple[str, float]] = []
    if src == 0:
        text = ui.get_text("Lines (e.g. 'January 120')")
        for line in text.splitlines():
            m = re.match(r"\s*(.+?)[\s;:,]+(-?[\d\s]+(?:[.,]\d+)?)\s*$", line)
            if m:
                items.append((m.group(1), to_number(m.group(2)) or 0.0))
    else:
        headers, rows, _ = read_csv(ui.ask_path("CSV file", kind="file"))
        li = choose_column(headers, "Label column")
        vi = choose_column(headers, "Value column")
        items = [(r[li], to_number(r[vi]) or 0.0) for r in rows]
    if not items:
        ui.error("No data.")
        return
    kind = ui.choose("Chart", ["Bars", "Line", "Pie (shares)"])
    if kind == 0:
        ui.bar_chart(items[:60])
    elif kind == 1:
        for line in line_chart([v for _, v in items], max(20, min(100, ui.term_width() - 14))):
            print(line)
        print(ui.gray(f"          {items[0][0]} … {items[-1][0]}"))
    else:
        for line in pie_bar(items[:8]):
            print(line)


@tool("data", "data-excel-to-csv", "Excel ↔ CSV", "Reads an .xlsx file into CSV or makes an .xlsx from CSV – without Excel or libraries",
      ("excel", "xlsx", "csv", "taulukko"))
def excel_tool() -> None:
    mode = ui.choose("Direction", ["Excel (.xlsx) → CSV", "CSV → Excel (.xlsx)"])
    if mode == 0:
        path = ui.ask_path("XLSX file", kind="file")
        try:
            sheets = xlsx_sheets(path)
        except (zipfile.BadZipFile, KeyError, ET.ParseError):
            ui.error("The file isn't a valid .xlsx (the old .xls format isn't supported).")
            return
        idx = ui.choose("Sheet", [s[0] for s in sheets], 0) if len(sheets) > 1 else 0
        rows = read_xlsx(path, idx)
        ui.table(rows[:15], max_col_width=20)
        target = Path(ui.ask("Save as CSV", f"{path.stem}-{sheets[idx][0]}.csv"))
        write_csv(target, rows[0] if rows else [], rows[1:])
        ui.success(f"{len(rows)} rows → {target.resolve()}")
        print(ui.gray("  Note: dates show as Excel serial numbers (e.g. 46000 = year 2025)."))
    else:
        path = ui.ask_path("CSV file", kind="file")
        headers, rows, _ = read_csv(path)
        target = Path(ui.ask("Save", path.stem + ".xlsx"))
        write_xlsx(target, [headers] + rows, path.stem)
        ui.success(f"Saved: {target.resolve()} ({len(rows)} rows)")


@tool("data", "data-grouping", "Grouping (pivot)", "Sums, averages and counts per group – like an Excel pivot table",
      ("pivot", "group by", "ryhmittely", "sum"))
def pivot_tool() -> None:
    headers, rows, _ = read_csv(ui.ask_path("CSV file", kind="file"))
    gi = choose_column(headers, "Group by column")
    agg = ui.choose("Calculation", ["Count", "Sum", "Average", "Min", "Max"])
    vi = choose_column(headers, "Value column") if agg else gi
    groups: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        v = to_number(r[vi]) if agg else 1.0
        if v is not None:
            groups[r[gi] or "(empty)"].append(v)
    fn = [len, sum, statistics.fmean, min, max][agg]
    result = sorted(((k, float(fn(v))) for k, v in groups.items()), key=lambda kv: -kv[1])
    name = ["Count", "Sum", "Average", "Min", "Max"][agg]
    ui.table([(k, ui.fi_num(v, 2 if agg else 0)) for k, v in result], [headers[gi], name], align=["<", ">"])
    ui.bar_chart(result[:15])
    text = "\n".join(f"{k};{v}" for k, v in result)
    offer_save(f"{headers[gi]};{name}\n{text}", "pivot.csv")
