"""File and folder tools."""
from __future__ import annotations

import datetime as dt
import difflib
import filecmp
import fnmatch
import hashlib
import os
import re
import shutil
import stat
import time
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable

from ..core import ui
from ..core.registry import tool
from ..core.utils import iter_files, unique_path

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

_SIZE_UNITS = {"": 1, "b": 1, "k": 1024, "kb": 1024, "kt": 1024, "m": 1024 ** 2, "mb": 1024 ** 2,
               "mt": 1024 ** 2, "g": 1024 ** 3, "gb": 1024 ** 3, "gt": 1024 ** 3, "t": 1024 ** 4,
               "tb": 1024 ** 4}


def parse_size(text: str) -> int:
    """Parses a size: '10MB', '1.5 GB', '500k', '2048'."""
    m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]*)\s*", text)
    if not m:
        raise ValueError(f"I don't understand the size {text!r}")
    unit = m.group(2).lower()
    if unit not in _SIZE_UNITS:
        raise ValueError(f"Unknown size unit: {m.group(2)}")
    return int(float(m.group(1).replace(",", ".")) * _SIZE_UNITS[unit])


SIGNATURES: list[tuple[int, bytes, str]] = [
    (0, b"\x89PNG\r\n\x1a\n", "PNG image"),
    (0, b"\xff\xd8\xff", "JPEG image"),
    (0, b"GIF87a", "GIF image"),
    (0, b"GIF89a", "GIF image (possibly animated)"),
    (0, b"BM", "BMP image"),
    (0, b"II*\x00", "TIFF image"),
    (0, b"MM\x00*", "TIFF image"),
    (0, b"\x00\x00\x01\x00", "ICO icon"),
    (0, b"8BPS", "Photoshop image (PSD)"),
    (0, b"%PDF", "PDF document"),
    (0, b"PK\x03\x04", "ZIP archive (or DOCX/XLSX/JAR/APK)"),
    (0, b"Rar!\x1a\x07", "RAR archive"),
    (0, b"7z\xbc\xaf\x27\x1c", "7-Zip archive"),
    (0, b"\x1f\x8b", "GZIP compressed"),
    (0, b"BZh", "BZIP2 compressed"),
    (0, b"\xfd7zXZ\x00", "XZ compressed"),
    (0, b"\x28\xb5\x2f\xfd", "Zstandard compressed"),
    (0, b"ID3", "MP3 audio (ID3)"),
    (0, b"\xff\xfb", "MP3 audio"),
    (0, b"\xff\xf3", "MP3 audio"),
    (0, b"fLaC", "FLAC audio"),
    (0, b"OggS", "Ogg media (Vorbis/Opus)"),
    (0, b"MThd", "MIDI music"),
    (0, b"\x1aE\xdf\xa3", "Matroska/WebM video"),
    (0, b"FLV", "Flash video"),
    (0, b"MZ", "Windows program (EXE/DLL)"),
    (0, b"\x7fELF", "Linux program (ELF)"),
    (0, b"\xca\xfe\xba\xbe", "Java class / Mach-O"),
    (0, b"\xcf\xfa\xed\xfe", "macOS program (Mach-O)"),
    (0, b"\x00asm", "WebAssembly"),
    (0, b"SQLite format 3\x00", "SQLite database"),
    (0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "Old Office file (DOC/XLS/PPT)"),
    (0, b"{\\rtf", "RTF document"),
    (0, b"\x00\x01\x00\x00\x00", "TrueType font"),
    (0, b"OTTO", "OpenType font"),
    (0, b"wOFF", "WOFF web font"),
    (0, b"wOF2", "WOFF2 web font"),
    (0, b"#!", "Script (shebang)"),
    (0, b"<?xml", "XML document"),
    (0, b"\xef\xbb\xbf", "Text (UTF-8 BOM)"),
    (4, b"ftypqt", "QuickTime video"),
    (4, b"ftypM4A", "M4A audio"),
    (4, b"ftypheic", "HEIC image"),
    (4, b"ftyp", "MP4/MOV video"),
]


def detect_type(path: Path) -> str:
    """Detects the file type from its first bytes (not the extension)."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(64)
    except OSError as exc:
        return f"not readable ({exc.strerror})"
    if not head:
        return "empty file"
    if head.startswith(b"RIFF") and len(head) >= 12:
        kind = head[8:12]
        return {b"WAVE": "WAV audio", b"AVI ": "AVI video", b"WEBP": "WebP image"}.get(kind, "RIFF file")
    for offset, sig, name in SIGNATURES:
        if head[offset:offset + len(sig)] == sig:
            return name
    lowered = head.lstrip().lower()
    if lowered.startswith((b"<!doctype html", b"<html")):
        return "HTML document"
    if lowered.startswith((b"{", b"[")):
        return "JSON or text"
    try:
        head.decode("utf-8")
        return "text file"
    except UnicodeDecodeError:
        printable = sum(32 <= b < 127 or b in (9, 10, 13) for b in head)
        return "text file (8-bit)" if printable / len(head) > 0.85 else "unknown binary"


def _hash_file(path: Path, limit: int | None = None, chunk: int = 1 << 20) -> str:
    h = hashlib.blake2b(digest_size=20)
    read = 0
    with open(path, "rb") as fh:
        while True:
            want = chunk if limit is None else min(chunk, limit - read)
            if want <= 0:
                break
            block = fh.read(want)
            if not block:
                break
            h.update(block)
            read += len(block)
    return h.hexdigest()


def find_duplicates(root: Path, min_size: int = 1, include_hidden: bool = False,
                    on_progress: Callable[[int], None] | None = None) -> list[list[Path]]:
    """Finds files with identical content: first by size, then by the start and finally by the full content."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    for p in iter_files(root, include_hidden=include_hidden):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size >= min_size:
            by_size[size].append(p)
    groups: list[list[Path]] = []
    done = 0
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_head: dict[str, list[Path]] = defaultdict(list)
        for p in paths:
            try:
                by_head[_hash_file(p, limit=65536)].append(p)
            except OSError:
                continue
        for same_head in by_head.values():
            if len(same_head) < 2:
                continue
            if size <= 65536:
                groups.append(sorted(same_head))
                continue
            by_full: dict[str, list[Path]] = defaultdict(list)
            for p in same_head:
                try:
                    by_full[_hash_file(p)].append(p)
                except OSError:
                    continue
                done += 1
                if on_progress:
                    on_progress(done)
            groups.extend(sorted(g) for g in by_full.values() if len(g) > 1)
    groups.sort(key=lambda g: -g[0].stat().st_size * (len(g) - 1))
    return groups


def largest_files(root: Path, n: int = 20) -> list[tuple[int, Path]]:
    import heapq

    heap: list[tuple[int, str]] = []
    for p in iter_files(root, include_hidden=True):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if len(heap) < n:
            heapq.heappush(heap, (size, str(p)))
        elif size > heap[0][0]:
            heapq.heapreplace(heap, (size, str(p)))
    return [(s, Path(p)) for s, p in sorted(heap, reverse=True)]


def dir_size(path: Path) -> tuple[int, int]:
    """Returns (size in bytes, number of files)."""
    total = count = 0
    for p in iter_files(path, include_hidden=True, skip_dirs=set()):
        try:
            total += p.stat().st_size
            count += 1
        except OSError:
            pass
    return total, count


def dir_sizes(root: Path) -> list[tuple[str, int, int]]:
    rows = []
    try:
        entries = list(os.scandir(root))
    except OSError:
        return rows
    loose_size = loose_count = 0
    for e in entries:
        try:
            if e.is_dir(follow_symlinks=False):
                size, count = dir_size(Path(e.path))
                rows.append((e.name + os.sep, size, count))
            elif e.is_file(follow_symlinks=False):
                loose_size += e.stat().st_size
                loose_count += 1
        except OSError:
            continue
    if loose_count:
        rows.append(("(files directly here)", loose_size, loose_count))
    rows.sort(key=lambda r: -r[1])
    return rows


def tree_lines(root: Path, max_depth: int = 3, show_files: bool = True, show_hidden: bool = False,
               limit: int = 400) -> list[str]:
    lines = [ui.c(root.name or str(root), "bold", "bright_blue")]
    count = 0

    def walk(path: Path, prefix: str, depth: int) -> None:
        nonlocal count
        if depth > max_depth or count >= limit:
            return
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        entries = [e for e in entries if show_hidden or not e.name.startswith(".")]
        if not show_files:
            entries = [e for e in entries if e.is_dir()]
        for i, e in enumerate(entries):
            if count >= limit:
                lines.append(prefix + ui.gray("… (list truncated)"))
                return
            last = i == len(entries) - 1
            branch = "└── " if last else "├── "
            if e.is_dir(follow_symlinks=False):
                lines.append(prefix + ui.gray(branch) + ui.c(e.name + "/", "bright_blue"))
                count += 1
                walk(Path(e.path), prefix + ("    " if last else ui.gray("│   ")), depth + 1)
            else:
                try:
                    size = ui.gray(f" ({ui.fmt_bytes(e.stat().st_size)})")
                except OSError:
                    size = ""
                lines.append(prefix + ui.gray(branch) + e.name + size)
                count += 1

    walk(root, "", 1)
    return lines


def find_files(root: Path, pattern: str = "*", min_size: int | None = None, max_size: int | None = None,
               newer_days: float | None = None, older_days: float | None = None,
               include_hidden: bool = False) -> list[Path]:
    now = time.time()
    patterns = [p.strip() for p in pattern.split(";") if p.strip()] or ["*"]
    out = []
    for p in iter_files(root, include_hidden=include_hidden):
        name = p.name.lower()
        if not any(fnmatch.fnmatch(name, pat.lower()) for pat in patterns):
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        if min_size is not None and st.st_size < min_size:
            continue
        if max_size is not None and st.st_size > max_size:
            continue
        age_days = (now - st.st_mtime) / 86400
        if newer_days is not None and age_days > newer_days:
            continue
        if older_days is not None and age_days < older_days:
            continue
        out.append(p)
    return out


TEXT_EXTS = {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".htm", ".css",
             ".csv", ".xml", ".yml", ".yaml", ".ini", ".cfg", ".toml", ".java", ".c", ".h", ".cpp",
             ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1", ".sql", ".log",
             ".lua", ".kt", ".swift", ".vue", ".svelte", ".tex", ".srt", ".conf", ".env", ".gd"}


def grep(root: Path, pattern: str, use_regex: bool = False, ignore_case: bool = True,
         extensions: Iterable[str] | None = None, max_results: int = 1000) -> list[tuple[Path, int, str]]:
    flags = re.IGNORECASE if ignore_case else 0
    rx = re.compile(pattern if use_regex else re.escape(pattern), flags)
    exts = set(extensions) if extensions else TEXT_EXTS
    results = []
    for p in iter_files(root, extensions=exts):
        try:
            if p.stat().st_size > 20 * 1024 * 1024:
                continue
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    if rx.search(line):
                        results.append((p, lineno, line.rstrip("\n")))
                        if len(results) >= max_results:
                            return results
        except OSError:
            continue
    return results


def rename_plan(files: list[Path], mode: str, **kw: str) -> list[tuple[Path, Path]]:
    """Computes new names. mode: prefix, suffix, replace, regex, number, lower, upper, title, ext, date."""
    plan = []
    width = len(str(len(files) + int(kw.get("start", "1")) - 1))
    for i, p in enumerate(files):
        stem, ext = p.stem, p.suffix
        if mode == "prefix":
            new = kw["text"] + p.name
        elif mode == "suffix":
            new = stem + kw["text"] + ext
        elif mode == "replace":
            new = p.name.replace(kw["find"], kw["repl"])
        elif mode == "regex":
            new = re.sub(kw["find"], kw["repl"], p.name)
        elif mode == "number":
            n = int(kw.get("start", "1")) + i
            new = f"{kw.get('base', '')}{str(n).zfill(max(width, int(kw.get('pad', '0') or 0)))}{ext}"
        elif mode == "lower":
            new = p.name.lower()
        elif mode == "upper":
            new = stem.upper() + ext
        elif mode == "title":
            new = stem.replace("_", " ").title() + ext
        elif mode == "spaces":
            new = re.sub(r"\s+", kw.get("repl", "_"), p.name)
        elif mode == "ext":
            e = kw["text"] if kw["text"].startswith(".") else "." + kw["text"]
            new = stem + e
        elif mode == "date":
            stamp = dt.datetime.fromtimestamp(p.stat().st_mtime).strftime(kw.get("fmt", "%Y-%m-%d_%H%M%S"))
            new = f"{stamp}_{p.name}" if kw.get("keep", "k") == "k" else f"{stamp}{ext}"
        else:
            raise ValueError(f"Unknown mode: {mode}")
        if new != p.name:
            plan.append((p, p.with_name(new)))
    return plan


def apply_renames(plan: list[tuple[Path, Path]]) -> tuple[int, list[str]]:
    """Renames in two phases (via temporary names) so chains and swaps work."""
    errors: list[str] = []
    targets = [dst for _, dst in plan]
    if len(set(targets)) != len(targets):
        return 0, ["Several files would get the same name – change the rule."]
    sources = {src for src, _ in plan}
    for _, dst in plan:
        if dst.exists() and dst not in sources:
            errors.append(f"Target already exists: {dst.name}")
    if errors:
        return 0, errors
    temps = []
    for i, (src, dst) in enumerate(plan):
        tmp = src.with_name(f".foldknife-rename-{os.getpid()}-{i}{src.suffix}")
        try:
            src.rename(tmp)
            temps.append((tmp, dst, src))
        except OSError as exc:
            errors.append(f"{src.name}: {exc.strerror}")
    done = 0
    for tmp, dst, src in temps:
        try:
            tmp.rename(dst)
            done += 1
        except OSError as exc:
            errors.append(f"{dst.name}: {exc.strerror}")
            try:
                tmp.rename(src)
            except OSError:
                pass
    return done, errors


TYPE_FOLDERS = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", ".tif", ".tiff", ".ico", ".raw", ".psd"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".flv", ".m4v"},
    "Music": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus", ".mid"},
    "Documents": {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".xls", ".xlsx", ".ods",
                   ".ppt", ".pptx", ".odp", ".csv", ".epub"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"},
    "Programs": {".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage", ".apk", ".jar", ".bat"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".java", ".c", ".cpp", ".cs", ".go",
              ".rs", ".php", ".rb", ".sh", ".sql", ".xml", ".yml", ".yaml", ".lua", ".ipynb"},
    "Fonts": {".ttf", ".otf", ".woff", ".woff2"},
    "Torrents": {".torrent"},
}


def organize_plan(root: Path) -> list[tuple[Path, Path]]:
    plan = []
    for entry in sorted(root.iterdir()):
        if not entry.is_file() or entry.name.startswith("."):
            continue
        ext = entry.suffix.lower()
        folder = next((name for name, exts in TYPE_FOLDERS.items() if ext in exts), "Other")
        plan.append((entry, root / folder / entry.name))
    return plan


def empty_dirs(root: Path) -> list[Path]:
    result = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        p = Path(dirpath)
        if p == root:
            continue
        try:
            if not any(p.iterdir()):
                result.append(p)
        except OSError:
            continue
    return result


def file_info(path: Path) -> list[tuple[str, str]]:
    st = path.stat()
    rows = [
        ("Name", path.name),
        ("Folder", str(path.parent.resolve())),
        ("Size", f"{ui.fmt_bytes(st.st_size)} ({ui.fi_num(st.st_size, 0)} bytes)"),
        ("Type (by content)", detect_type(path) if path.is_file() else "folder"),
        ("Modified", dt.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")),
        ("Accessed", dt.datetime.fromtimestamp(st.st_atime).strftime("%Y-%m-%d %H:%M:%S")),
        ("Created / metadata", dt.datetime.fromtimestamp(getattr(st, "st_birthtime", st.st_ctime)).strftime("%Y-%m-%d %H:%M:%S")),
        ("Permissions", stat.filemode(st.st_mode)),
    ]
    if path.is_file() and st.st_size < 50 * 1024 * 1024:
        try:
            data = path.read_bytes()
            rows.append(("SHA-256", hashlib.sha256(data).hexdigest()))
            if b"\x00" not in data[:4096]:
                text = data.decode("utf-8", errors="replace")
                rows.append(("Rows", ui.fi_num(text.count("\n") + (1 if text and not text.endswith("\n") else 0), 0)))
                rows.append(("Words", ui.fi_num(len(text.split()), 0)))
                rows.append(("Line endings", "Windows (CRLF)" if b"\r\n" in data else "Unix (LF)" if b"\n" in data else "-"))
        except OSError:
            pass
    return rows


def split_file(path: Path, part_size: int) -> list[Path]:
    parts = []
    with open(path, "rb") as fh:
        i = 1
        while True:
            chunk = fh.read(part_size)
            if not chunk:
                break
            part = path.with_name(f"{path.name}.part{i:03d}")
            part.write_bytes(chunk)
            parts.append(part)
            i += 1
    return parts


def join_parts(first: Path) -> Path:
    m = re.match(r"(.+)\.part(\d{3})$", first.name)
    if not m:
        raise ValueError("Choose the first part (name ends with .part001).")
    base = first.with_name(m.group(1))
    target = unique_path(base)
    i = 1
    with open(target, "wb") as out:
        while True:
            part = first.with_name(f"{m.group(1)}.part{i:03d}")
            if not part.exists():
                break
            out.write(part.read_bytes())
            i += 1
    return target


def safe_extract(zip_path: Path, dest: Path) -> int:
    """Extracts a zip while preventing paths from escaping the target folder (zip slip)."""
    dest = dest.resolve()
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if not str(target).startswith(str(dest)):
                raise ValueError(f"Dangerous path in archive: {member.filename}")
            zf.extract(member, dest)
            count += 1
    return count


def zip_paths(paths: list[Path], target: Path, on_file: Callable[[Path], None] | None = None) -> int:
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for base in paths:
            if base.is_file():
                zf.write(base, base.name)
                count += 1
                continue
            for f in iter_files(base, include_hidden=True, skip_dirs=set()):
                zf.write(f, Path(base.name) / f.relative_to(base))
                count += 1
                if on_file:
                    on_file(f)
    return count


def sync_plan(src: Path, dst: Path) -> list[tuple[str, Path, Path]]:
    plan = []
    for f in iter_files(src, include_hidden=True, skip_dirs=set()):
        rel = f.relative_to(src)
        target = dst / rel
        if not target.exists():
            plan.append(("uusi", f, target))
        else:
            s, t = f.stat(), target.stat()
            if s.st_size != t.st_size or s.st_mtime > t.st_mtime + 2:
                plan.append(("update", f, target))
    return plan


def ext_stats(root: Path) -> list[tuple[str, int, int]]:
    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for p in iter_files(root):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        ext = p.suffix.lower() or "(no extension)"
        stats[ext][0] += 1
        stats[ext][1] += size
    return sorted(((e, c, s) for e, (c, s) in stats.items()), key=lambda r: -r[2])


def _rel(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("files", "files-find-duplicates", "Find duplicates",
      "Finds files with identical content and frees up space", ("duplikaatti", "tupla", "sama"))
def duplicates_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    min_kb = ui.ask_float("Minimum size (KB)", 1)
    with ui.Spinner("Looking for duplicates"):
        groups = find_duplicates(root, int(min_kb * 1024))
    if not groups:
        ui.success("No duplicates found.")
        return
    wasted = sum(g[0].stat().st_size * (len(g) - 1) for g in groups)
    ui.warn(f"Found {len(groups)} groups, wasted space {ui.fmt_bytes(wasted)}.")
    lines = []
    for i, g in enumerate(groups, 1):
        lines.append(ui.c(f"\nGroup {i} – {ui.fmt_bytes(g[0].stat().st_size)} × {len(g)}", "bold"))
        lines.extend(f"   {j}. {_rel(p, root)}" for j, p in enumerate(g, 1))
    ui.paginate(lines)
    if not ui.ask_yes_no("Delete the duplicates (the first of each group is kept)?", default=False):
        return
    if not ui.confirm_danger("Deleting is permanent (no recycle bin)."):
        return
    removed = freed = 0
    for g in groups:
        for p in g[1:]:
            try:
                size = p.stat().st_size
                p.unlink()
                removed += 1
                freed += size
            except OSError as exc:
                ui.error(f"{p}: {exc.strerror}")
    ui.success(f"Deleted {removed} files, freed {ui.fmt_bytes(freed)}.")


@tool("files", "files-largest-files", "Largest files", "Shows the biggest files in a folder", ("iso", "tila"))
def largest_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    n = ui.ask_int("How many to show", 20, 1, 500)
    with ui.Spinner("Scanning files"):
        rows = largest_files(root, n)
    ui.table([(ui.fmt_bytes(s), _rel(p, root)) for s, p in rows], ["Size", "File"], align=[">", "<"], max_col_width=80)


@tool("files", "files-disk-usage", "Disk usage", "Where did the space go? Folder sizes as a chart",
      ("levytila", "koko", "disk"))
def dir_sizes_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    with ui.Spinner("Calculating sizes"):
        rows = dir_sizes(root)
    if not rows:
        ui.info("The folder is empty.")
        return
    total = sum(r[1] for r in rows)
    ui.info(f"Total {ui.fmt_bytes(total)} · {ui.fi_num(sum(r[2] for r in rows), 0)} files")
    ui.bar_chart([(name, size) for name, size, _ in rows[:25]], value_fmt=lambda v: ui.fmt_bytes(v))


@tool("files", "files-folder-tree", "Folder tree", "Draws a folder's structure as a tree", ("tree", "rakenne"))
def tree_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    depth = ui.ask_int("Depth", 3, 1, 20)
    files = ui.ask_yes_no("Show files too?", True)
    lines = tree_lines(root, depth, files)
    ui.paginate(lines)
    if ui.ask_yes_no("Save the tree to a text file?", default=False):
        target = Path(ui.ask("File", "folder-tree.txt"))
        target.write_text("\n".join(ui.strip_ansi(x) for x in lines), encoding="utf-8")
        ui.success(f"Saved: {target.resolve()}")


@tool("files", "files-file-search", "File search", "Find by name, size and age (e.g. *.mp4;*.mkv)",
      ("find", "etsi", "hae"))
def find_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    pattern = ui.ask("Name pattern (* and ?, several separated by ;)", "*")
    min_s = ui.ask("Minimum size (e.g. 10MB, empty = no limit)", allow_empty=True)
    max_s = ui.ask("Maximum size (empty = no limit)", allow_empty=True)
    newer = ui.ask("Modified within the last N days (empty = no limit)", allow_empty=True)
    with ui.Spinner("Searching"):
        found = find_files(root, pattern, parse_size(min_s) if min_s else None,
                           parse_size(max_s) if max_s else None, float(newer) if newer else None)
    ui.info(f"Found {len(found)} files.")
    lines = []
    total = 0
    for p in found:
        st = p.stat()
        total += st.st_size
        when = dt.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
        lines.append(f"{ui.gray(when)} {ui.fmt_bytes(st.st_size):>10}  {_rel(p, root)}")
    ui.paginate(lines)
    if found:
        ui.info(f"Total size {ui.fmt_bytes(total)}")


@tool("files", "files-grep", "Search text in files", "Searches a word or regex in all text files",
      ("grep", "content", "teksti"))
def grep_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    pattern = ui.ask("Text to search for")
    regex = ui.ask_yes_no("Is the search a regular expression (regex)?", False)
    case = ui.ask_yes_no("Case sensitive?", False)
    exts = ui.ask("File extensions separated by commas (empty = common text files)", allow_empty=True)
    ext_list = [e.strip() if e.strip().startswith(".") else "." + e.strip() for e in exts.split(",") if e.strip()]
    try:
        with ui.Spinner("Searching"):
            results = grep(root, pattern, regex, not case, ext_list or None)
    except re.error as exc:
        ui.error(f"Invalid regex: {exc}")
        return
    rx = re.compile(pattern if regex else re.escape(pattern), 0 if case else re.IGNORECASE)
    lines = []
    last = None
    for p, lineno, line in results:
        if p != last:
            lines.append(ui.c(_rel(p, root), "bold", "bright_blue"))
            last = p
        shown = rx.sub(lambda m: ui.c(m.group(0), "bold", "bright_red"), line.strip()[:200])
        lines.append(f"  {ui.gray(str(lineno).rjust(5))}: {shown}")
    ui.paginate(lines)
    ui.info(f"{len(results)} matches in {len({r[0] for r in results})} files.")


@tool("files", "files-bulk-rename", "Bulk rename", "Rename dozens of files at once with a preview",
      ("rename", "rename", "numerointi"))
def rename_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    pattern = ui.ask("Which files (e.g. *.jpg)", "*")
    files = sorted((p for p in root.iterdir() if p.is_file() and fnmatch.fnmatch(p.name.lower(), pattern.lower())),
                   key=lambda p: p.name.lower())
    if not files:
        ui.warn("No files.")
        return
    ui.info(f"{len(files)} files selected.")
    modes = [("prefix", "Add to the start"), ("suffix", "Add to the end (before the extension)"),
             ("replace", "Find and replace"), ("regex", "Regex replace"), ("number", "Number them (image_001.jpg…)"),
             ("lower", "lower case"), ("upper", "UPPER CASE"), ("title", "Title Case"),
             ("spaces", "Spaces to underscores"), ("ext", "Change extension"), ("date", "Modification date first")]
    idx = ui.choose("Method", [m[1] for m in modes])
    mode = modes[idx][0]
    kw: dict[str, str] = {}
    if mode in ("prefix", "suffix", "ext"):
        kw["text"] = ui.ask("Text")
    elif mode in ("replace", "regex"):
        kw["find"] = ui.ask("Find")
        kw["repl"] = ui.ask("Replace with (empty = delete)", allow_empty=True)
    elif mode == "number":
        kw["base"] = ui.ask("Name prefix", "file_")
        kw["start"] = str(ui.ask_int("Start number", 1))
        kw["pad"] = str(ui.ask_int("Minimum number width", 3, 1, 10))
    elif mode == "spaces":
        kw["repl"] = ui.ask("Replace spaces with", "_")
    try:
        plan = rename_plan(files, mode, **kw)
    except re.error as exc:
        ui.error(f"Invalid regex: {exc}")
        return
    if not plan:
        ui.info("No name would change.")
        return
    ui.table([(src.name, "→", dst.name) for src, dst in plan[:40]], ["Old", "", "New"], max_col_width=50)
    if len(plan) > 40:
        ui.info(f"… and {len(plan) - 40} more")
    if ui.ask_yes_no(f"Rename {len(plan)} files?", default=False):
        done, errors = apply_renames(plan)
        for e in errors:
            ui.error(e)
        ui.success(f"Renamed {done} files.")


@tool("files", "files-organise-by-type", "Organise by type", "Moves files into subfolders: Images, Videos…",
      ("lataukset", "downloads", "siivous", "organize"))
def organize_tool() -> None:
    root = ui.ask_path("Folder (e.g. Downloads)", kind="dir", default=str(Path.home() / "Downloads"))
    plan = organize_plan(root)
    if not plan:
        ui.info("No files to move.")
        return
    summary: dict[str, int] = defaultdict(int)
    for _, dst in plan:
        summary[dst.parent.name] += 1
    ui.bar_chart(sorted(summary.items(), key=lambda kv: -kv[1]))
    if not ui.ask_yes_no(f"Move {len(plan)} files?", default=False):
        return
    moved = 0
    for src, dst in plan:
        dst.parent.mkdir(exist_ok=True)
        try:
            shutil.move(str(src), str(unique_path(dst)))
            moved += 1
        except OSError as exc:
            ui.error(f"{src.name}: {exc}")
    ui.success(f"Moved {moved} files.")


@tool("files", "files-empty-folders", "Empty folders", "Finds and deletes empty folders", ("empty", "siivous"))
def empty_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    found = empty_dirs(root)
    if not found:
        ui.success("No empty folders found.")
        return
    ui.paginate([_rel(p, root) for p in found])
    if ui.ask_yes_no(f"Delete {len(found)} empty folders?", default=False):
        n = 0
        for p in found:
            try:
                p.rmdir()
                n += 1
            except OSError:
                pass
        ui.success(f"Deleted {n} folders.")


@tool("files", "files-file-info", "File info", "Size, times, permissions, SHA-256 and the real type",
      ("info", "tyyppi", "magic"))
def info_tool() -> None:
    path = ui.ask_path("File or folder")
    rows = file_info(path)
    if path.is_dir():
        size, count = dir_size(path)
        rows.insert(2, ("Payload", f"{ui.fi_num(count, 0)} files, {ui.fmt_bytes(size)}"))
    ui.print_kv(rows)


@tool("files", "files-compare-files", "Compare files", "Are two files identical? Shows the differences line by line",
      ("diff", "ero"))
def compare_tool() -> None:
    a = ui.ask_path("First file", kind="file")
    b = ui.ask_path("Second file", kind="file")
    if filecmp.cmp(a, b, shallow=False):
        ui.success("The files are exactly the same.")
        return
    ui.warn("The files differ.")
    if "text" not in detect_type(a) and "JSON" not in detect_type(a):
        ui.info(f"Sizes: {ui.fmt_bytes(a.stat().st_size)} vs {ui.fmt_bytes(b.stat().st_size)}")
        return
    la = ui.read_text_file(a).splitlines()
    lb = ui.read_text_file(b).splitlines()
    out = []
    for line in difflib.unified_diff(la, lb, a.name, b.name, lineterm="", n=2):
        if line.startswith("+") and not line.startswith("+++"):
            out.append(ui.green(line))
        elif line.startswith("-") and not line.startswith("---"):
            out.append(ui.red(line))
        elif line.startswith("@@"):
            out.append(ui.cyan(line))
        else:
            out.append(line)
    ui.paginate(out)
    ratio = difflib.SequenceMatcher(None, la, lb).ratio()
    ui.info(f"Similarity: {ratio * 100:.1f} %")


@tool("files", "files-compare-folders", "Compare folders", "Which files are missing or differ between two folders",
      ("diff", "kansio", "synkronointi"))
def compare_dirs_tool() -> None:
    a = ui.ask_path("Folder A", kind="dir")
    b = ui.ask_path("Folder B", kind="dir")
    only_a, only_b, differ = [], [], []

    def walk(cmp: filecmp.dircmp, prefix: str = "") -> None:
        only_a.extend(prefix + x for x in cmp.left_only)
        only_b.extend(prefix + x for x in cmp.right_only)
        _, mismatch, errors = filecmp.cmpfiles(cmp.left, cmp.right, cmp.common_files, shallow=False)
        differ.extend(prefix + x for x in mismatch + errors)
        for name, sub in cmp.subdirs.items():
            walk(sub, prefix + name + "/")

    walk(filecmp.dircmp(a, b))
    for title, items, color in (("Only in A", only_a, "bright_yellow"), ("Only in B", only_b, "bright_blue"),
                                ("Different content", differ, "bright_red")):
        print(ui.c(f"\n{title} ({len(items)})", "bold", color))
        for x in items[:200]:
            print("  " + x)
    if not (only_a or only_b or differ):
        ui.success("The folders are identical.")


@tool("files", "files-split-join", "Split / join a file", "Split a big file into parts (e.g. for Discord's limit) and join them back",
      ("split", "join", "osat"))
def split_tool() -> None:
    mode = ui.choose("Action", ["Split into parts", "Join parts"])
    if mode == 0:
        path = ui.ask_path("File", kind="file")
        size = parse_size(ui.ask("Part size (e.g. 10MB, 25MB)", "10MB"))
        parts = split_file(path, size)
        ui.success(f"Created {len(parts)} parts: {parts[0].name} … {parts[-1].name}")
    else:
        first = ui.ask_path("First part (.part001)", kind="file")
        target = join_parts(first)
        ui.success(f"Joined: {target} ({ui.fmt_bytes(target.stat().st_size)})")


@tool("files", "files-zip-tools", "Zip tools", "Compress, extract and list zip archives safely",
      ("pakkaa", "pura", "arkisto", "unzip"))
def zip_tool() -> None:
    mode = ui.choose("Action", ["Compress a folder or file", "Extract a zip", "Show zip contents", "Test zip integrity"])
    if mode == 0:
        src = ui.ask_path("What to compress")
        target = unique_path(Path(ui.ask("Archive name", src.name + ".zip")))
        with ui.ProgressBar(None, "Compressing", unit=" files") as pb:
            n = zip_paths([src], target, on_file=lambda _: pb.update())
        ui.success(f"{n} files → {target} ({ui.fmt_bytes(target.stat().st_size)})")
        return
    zpath = ui.ask_path("Zip file", kind="file")
    if mode == 1:
        dest = Path(ui.ask("Extract to folder", zpath.stem))
        dest.mkdir(parents=True, exist_ok=True)
        n = safe_extract(zpath, dest)
        ui.success(f"Extracted {n} items to {dest.resolve()}")
    elif mode == 2:
        with zipfile.ZipFile(zpath) as zf:
            infos = zf.infolist()
            rows = [(i.filename, ui.fmt_bytes(i.file_size), ui.fmt_bytes(i.compress_size),
                     f"{dt.datetime(*i.date_time):%Y-%m-%d %H:%M}") for i in infos[:300]]
        ui.table(rows, ["Name", "Size", "Packed", "Date"], max_col_width=60)
        total = sum(i.file_size for i in infos)
        packed = sum(i.compress_size for i in infos)
        ui.info(f"{len(infos)} items, {ui.fmt_bytes(total)} → {ui.fmt_bytes(packed)}"
                + (f" (compression {100 - packed / total * 100:.0f} %)" if total else ""))
    else:
        with zipfile.ZipFile(zpath) as zf:
            bad = zf.testzip()
        ui.success("The archive is intact.") if bad is None else ui.error(f"Broken file: {bad}")


@tool("files", "files-backup", "Back up a folder", "Compresses a folder into a timestamped zip file",
      ("backup", "varmuus"))
def backup_tool() -> None:
    src = ui.ask_path("Folder to back up", kind="dir")
    dest_dir = ui.ask_path("Folder to save the backup in", kind="dir", default=str(Path.home()))
    target = dest_dir / f"{src.name}-{dt.datetime.now():%Y%m%d-%H%M%S}.zip"
    with ui.ProgressBar(None, "Compressing", unit=" files") as pb:
        n = zip_paths([src], target, on_file=lambda _: pb.update())
    ui.success(f"Backup ready: {target} ({n} files, {ui.fmt_bytes(target.stat().st_size)})")
    old = sorted(dest_dir.glob(f"{src.name}-*.zip"))
    if len(old) > 5 and ui.ask_yes_no(f"There are {len(old)} backups. Delete the oldest so that 5 remain?", False):
        for p in old[:-5]:
            p.unlink()
        ui.success(f"Deleted {len(old) - 5} old backups.")


@tool("files", "files-recently-modified", "Recently modified", "Which files have changed recently", ("recent", "uusimmat"))
def recent_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    days = ui.ask_float("For how many days", 1)
    found = find_files(root, "*", newer_days=days)
    found.sort(key=lambda p: -p.stat().st_mtime)
    rows = [(dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M"), ui.fmt_bytes(p.stat().st_size),
             _rel(p, root)) for p in found[:200]]
    ui.table(rows, ["Modified", "Size", "File"], max_col_width=70)
    ui.info(f"{len(found)} files modified in the last {ui.fi_num(days, 1)} days.")


@tool("files", "files-extension-stats", "Statistics by extension", "How many and how much space each file type takes",
      ("extension", "extension", "tilasto"))
def ext_tool() -> None:
    root = ui.ask_path("Folder", kind="dir", default=".")
    with ui.Spinner("Counting"):
        rows = ext_stats(root)
    ui.table([(e, c, ui.fmt_bytes(s)) for e, c, s in rows[:40]], ["Extension", "Count", "Size"], align=["<", ">", ">"])
    ui.bar_chart([(e, s) for e, _, s in rows[:12]], value_fmt=lambda v: ui.fmt_bytes(v))


@tool("files", "files-mirror", "Mirror a folder", "Copies new and changed files to another folder (one-way)",
      ("sync", "synkronoi", "kopioi"))
def sync_tool() -> None:
    src = ui.ask_path("Source folder", kind="dir")
    dst = ui.ask_path("Target folder", must_exist=False)
    plan = sync_plan(src, dst)
    if not plan:
        ui.success("The target is already up to date.")
        return
    new = sum(1 for a, _, _ in plan if a == "uusi")
    ui.info(f"To copy: {new} new, {len(plan) - new} updated, total "
            f"{ui.fmt_bytes(sum(s.stat().st_size for _, s, _ in plan))}")
    for action, s, _ in plan[:15]:
        print(f"  {ui.green('+') if action == 'uusi' else ui.yellow('~')} {_rel(s, src)}")
    if not ui.ask_yes_no("Copy now?", True):
        return
    with ui.ProgressBar(len(plan), "Copying") as pb:
        for _, s, t in plan:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, t)
            pb.update()
    ui.success("Done. Nothing was deleted from the target.")
