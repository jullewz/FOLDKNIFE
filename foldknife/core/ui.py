"""Foldknife UI helpers: colours, boxes, tables, prompts and progress bars.

All output goes through these functions so colours can be turned off
(setting or NO_COLOR environment variable) and the Windows console works correctly.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

# --------------------------------------------------------------------------
# Terminal setup
# --------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_state: dict[str, Any] = {"color": True, "initialized": False, "unicode": True}


def _enable_windows_vt() -> None:
    """Enables ANSI mode in the Windows console (Windows 10+)."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        for handle_id in (-11, -12):  # STDOUT, STDERR
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        os.system("")


def init_terminal(color: bool | None = None) -> None:
    """Prepares the terminal: UTF-8, Windows VT mode and colour detection."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    if os.name == "nt":
        _enable_windows_vt()
    if color is None:
        color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    _state["color"] = bool(color)
    _state["initialized"] = True


def set_color(enabled: bool) -> None:
    _state["color"] = bool(enabled)


def color_enabled() -> bool:
    return bool(_state["color"])


def is_tty() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def term_width(default: int = 80) -> int:
    try:
        return max(40, shutil.get_terminal_size((default, 24)).columns)
    except Exception:
        return default


def term_height(default: int = 24) -> int:
    try:
        return max(10, shutil.get_terminal_size((80, default)).lines)
    except Exception:
        return default


def clear() -> None:
    """Clears the screen (only in a real terminal)."""
    if not is_tty():
        print()
        return
    if color_enabled():
        print("\x1b[2J\x1b[H", end="", flush=True)
    else:
        os.system("cls" if os.name == "nt" else "clear")


def hide_cursor() -> None:
    if is_tty() and color_enabled():
        print("\x1b[?25l", end="", flush=True)


def show_cursor() -> None:
    if is_tty() and color_enabled():
        print("\x1b[?25h", end="", flush=True)


def move_home() -> None:
    if color_enabled():
        print("\x1b[H", end="")


# --------------------------------------------------------------------------
# Colours
# --------------------------------------------------------------------------

CODES = {
    "reset": 0, "bold": 1, "dim": 2, "italic": 3, "underline": 4, "blink": 5,
    "reverse": 7, "strike": 9,
    "black": 30, "red": 31, "green": 32, "yellow": 33, "blue": 34,
    "magenta": 35, "cyan": 36, "white": 37, "gray": 90,
    "bright_red": 91, "bright_green": 92, "bright_yellow": 93, "bright_blue": 94,
    "bright_magenta": 95, "bright_cyan": 96, "bright_white": 97,
    "bg_black": 40, "bg_red": 41, "bg_green": 42, "bg_yellow": 43, "bg_blue": 44,
    "bg_magenta": 45, "bg_cyan": 46, "bg_white": 47, "bg_gray": 100,
}


def c(text: Any, *styles: str | int) -> str:
    """Colours text with the given styles (e.g. c("hi", "bold", "red"))."""
    text = str(text)
    if not _state["color"] or not styles:
        return text
    codes = ";".join(str(CODES[s]) if isinstance(s, str) else str(s) for s in styles)
    return f"\x1b[{codes}m{text}\x1b[0m"


def rgb(text: Any, r: int, g: int, b: int) -> str:
    """24-bit foreground colour."""
    if not _state["color"]:
        return str(text)
    return f"\x1b[38;2;{int(r)};{int(g)};{int(b)}m{text}\x1b[0m"


def bg_rgb(text: Any, r: int, g: int, b: int) -> str:
    """24-bit background colour."""
    if not _state["color"]:
        return str(text)
    return f"\x1b[48;2;{int(r)};{int(g)};{int(b)}m{text}\x1b[0m"


def fg_bg_rgb(text: Any, fg: tuple[int, int, int], bg: tuple[int, int, int]) -> str:
    if not _state["color"]:
        return str(text)
    return (f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]};48;2;{bg[0]};{bg[1]};{bg[2]}m"
            f"{text}\x1b[0m")


def fg256(text: Any, n: int) -> str:
    if not _state["color"]:
        return str(text)
    return f"\x1b[38;5;{int(n)}m{text}\x1b[0m"


def red(t: Any) -> str: return c(t, "bright_red")
def green(t: Any) -> str: return c(t, "bright_green")
def yellow(t: Any) -> str: return c(t, "bright_yellow")
def blue(t: Any) -> str: return c(t, "bright_blue")
def cyan(t: Any) -> str: return c(t, "bright_cyan")
def magenta(t: Any) -> str: return c(t, "bright_magenta")
def gray(t: Any) -> str: return c(t, "gray")
def bold(t: Any) -> str: return c(t, "bold")
def dim(t: Any) -> str: return c(t, "dim")
def under(t: Any) -> str: return c(t, "underline")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    if ch in "​‌‍️":
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def visible_len(text: str) -> int:
    """Width of a string in the terminal (ANSI codes and wide characters included)."""
    return sum(char_width(ch) for ch in strip_ansi(str(text)))


def pad(text: str, width: int, align: str = "<") -> str:
    text = str(text)
    gap = max(0, width - visible_len(text))
    if align == ">":
        return " " * gap + text
    if align == "^":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def truncate(text: str, width: int, ellipsis: str = "…") -> str:
    """Shortens (uncoloured) text to the given width."""
    text = str(text)
    if visible_len(text) <= width:
        return text
    plain = strip_ansi(text)
    out, used = [], 0
    for ch in plain:
        w = char_width(ch)
        if used + w > width - len(ellipsis):
            break
        out.append(ch)
        used += w
    return "".join(out) + ellipsis


def gradient(text: str, start: tuple[int, int, int], end: tuple[int, int, int]) -> str:
    """Colour gradient over text, one character at a time."""
    if not _state["color"] or not text:
        return text
    n = max(1, len(text) - 1)
    out = []
    for i, ch in enumerate(text):
        t = i / n
        r = round(start[0] + (end[0] - start[0]) * t)
        g = round(start[1] + (end[1] - start[1]) * t)
        b = round(start[2] + (end[2] - start[2]) * t)
        out.append(f"\x1b[38;2;{r};{g};{b}m{ch}")
    return "".join(out) + "\x1b[0m"


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    import colorsys

    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def rainbow(text: str, offset: float = 0.0) -> str:
    if not _state["color"]:
        return text
    out = []
    visible = [ch for ch in text]
    n = max(1, len(visible))
    for i, ch in enumerate(visible):
        r, g, b = hsv_to_rgb(offset + i / n, 0.75, 1.0)
        out.append(f"\x1b[38;2;{r};{g};{b}m{ch}")
    return "".join(out) + "\x1b[0m"


# --------------------------------------------------------------------------
# Messages and boxes
# --------------------------------------------------------------------------

def success(msg: Any) -> None:
    print(c("✔ ", "bright_green") + str(msg))


def error(msg: Any) -> None:
    print(c("✘ ", "bright_red") + str(msg))


def warn(msg: Any) -> None:
    print(c("! ", "bright_yellow") + str(msg))


def info(msg: Any) -> None:
    print(c("• ", "bright_cyan") + str(msg))


def hr(char: str = "─", width: int | None = None, color: str = "gray") -> None:
    print(c(char * (width or min(term_width(), 100)), color))


def box(content: str | Sequence[str], title: str | None = None, color: str = "bright_cyan",
        padding: int = 1, width: int | None = None, align: str = "<") -> None:
    """Draws a rounded box around text."""
    print(render_box(content, title, color, padding, width, align))


def render_box(content: str | Sequence[str], title: str | None = None,
               color: str = "bright_cyan", padding: int = 1,
               width: int | None = None, align: str = "<") -> str:
    lines = content.splitlines() if isinstance(content, str) else [str(x) for x in content]
    max_inner = (width or min(term_width(), 100)) - 2 - padding * 2
    wrapped: list[str] = []
    for line in lines:
        if visible_len(line) <= max_inner:
            wrapped.append(line)
        else:
            plain = strip_ansi(line)
            wrapped.extend(textwrap.wrap(plain, max_inner) or [""])
    inner = max([visible_len(x) for x in wrapped] + [visible_len(title or "") + 2, 10])
    if width:
        inner = max(inner, width - 2 - padding * 2)
    total = inner + padding * 2
    if title:
        t = f" {title} "
        top = "╭─" + t + "─" * max(0, total - visible_len(t) - 1) + "╮"
        top = c("╭─", color) + c(t, "bold", color) + c("─" * max(0, total - visible_len(t) - 1) + "╮", color)
    else:
        top = c("╭" + "─" * total + "╮", color)
    out = [top]
    side = c("│", color)
    for line in wrapped:
        out.append(side + " " * padding + pad(line, inner, align) + " " * padding + side)
    out.append(c("╰" + "─" * total + "╯", color))
    return "\n".join(out)


def header(title: str, subtitle: str | None = None, color: str = "bright_cyan") -> None:
    lines = [c(title, "bold")]
    if subtitle:
        lines.append(gray(subtitle))
    box(lines, color=color)


def print_kv(pairs: Iterable[tuple[Any, Any]] | dict, key_color: str = "bright_cyan",
             sep: str = " : ") -> None:
    """Prints key–value pairs neatly aligned."""
    items = list(pairs.items()) if isinstance(pairs, dict) else list(pairs)
    if not items:
        return
    width = max(visible_len(str(k)) for k, _ in items)
    for k, v in items:
        print(c(pad(str(k), width), key_color) + gray(sep) + str(v))


# --------------------------------------------------------------------------
# Tables and charts
# --------------------------------------------------------------------------

def render_table(rows: Sequence[Sequence[Any]], headers: Sequence[Any] | None = None,
                 align: Sequence[str] | None = None, max_col_width: int = 40,
                 color: str = "gray", header_color: str = "bright_cyan") -> str:
    rows = [list(r) for r in rows]
    ncols = max([len(r) for r in rows] + [len(headers or [])] + [0])
    if ncols == 0:
        return gray("(empty)")
    for r in rows:
        r.extend([""] * (ncols - len(r)))
    if align is None:
        align = []
        for i in range(ncols):
            numeric = rows and all(isinstance(r[i], (int, float)) or r[i] == "" for r in rows)
            align.append(">" if numeric and any(r[i] != "" for r in rows) else "<")
    align = list(align) + ["<"] * (ncols - len(align))

    def fmt(v: Any) -> str:
        if isinstance(v, float):
            s = f"{v:.4f}".rstrip("0").rstrip(".")
            return s if s not in ("", "-0") else "0"
        return str(v)

    str_rows = [[truncate(fmt(v), max_col_width) for v in r] for r in rows]
    str_head = [truncate(str(h), max_col_width) for h in headers] if headers else None
    widths = [0] * ncols
    for r in ([str_head] if str_head else []) + str_rows:
        for i, v in enumerate(r):
            widths[i] = max(widths[i], visible_len(v))
    line = lambda l, m, r_: c(l + m.join("─" * (w + 2) for w in widths) + r_, color)  # noqa: E731
    bar = c("│", color)
    out = [line("┌", "┬", "┐")]
    if str_head:
        out.append(bar + bar.join(" " + c(pad(h, widths[i], "<"), "bold", header_color) + " "
                                  for i, h in enumerate(str_head)) + bar)
        out.append(line("├", "┼", "┤"))
    for r in str_rows:
        out.append(bar + bar.join(" " + pad(v, widths[i], align[i]) + " " for i, v in enumerate(r)) + bar)
    out.append(line("└", "┴", "┘"))
    return "\n".join(out)


def table(rows: Sequence[Sequence[Any]], headers: Sequence[Any] | None = None,
          align: Sequence[str] | None = None, max_col_width: int = 40) -> None:
    print(render_table(rows, headers, align, max_col_width))


SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values: Sequence[float]) -> str:
    vals = [float(v) for v in values]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1.0
    return "".join(SPARK_CHARS[min(7, int((v - lo) / span * 7.999))] for v in vals)


def bar_chart(items: Sequence[tuple[str, float]], width: int | None = None,
              color: str = "bright_cyan", value_fmt: Callable[[float], str] | None = None) -> None:
    """Horizontal bar chart: [(name, value), ...]."""
    if not items:
        print(gray("(no data)"))
        return
    value_fmt = value_fmt or (lambda v: fi_num(v, 2 if v != int(v) else 0))
    label_w = min(30, max(visible_len(str(k)) for k, _ in items))
    vals = [abs(float(v)) for _, v in items]
    top = max(vals) or 1.0
    width = width or max(10, min(60, term_width() - label_w - 20))
    for (label, value), v in zip(items, vals):
        full = v / top * width
        n = int(full)
        frac = full - n
        partial = " ▏▎▍▌▋▊▉"[int(frac * 8)] if n < width else ""
        bar = "█" * n + (partial if partial.strip() else "")
        print(pad(truncate(str(label), label_w), label_w) + " " + c(bar, color) + " "
              + gray(value_fmt(float(value))))


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def fi_num(x: float | int, decimals: int = 2) -> str:
    """Number format: 1,234,567.89."""
    if isinstance(x, int) and decimals == 0:
        s = f"{x:,}"
    else:
        s = f"{x:,.{decimals}f}"
    return s


def fmt_bytes(n: float, decimals: int = 1) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1024 or unit == "PB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{fi_num(n, decimals)} {unit}"
        n /= 1024
    return f"{n} B"


def fmt_duration(seconds: float) -> str:
    """Human readable duration: 2 h 3 min 4 s."""
    if seconds < 0:
        return "-" + fmt_duration(-seconds)
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{fi_num(seconds, 1)} s"
    seconds = int(round(seconds))
    parts = []
    for name, size in (("v", 365 * 86400), ("vrk", 86400), ("h", 3600), ("min", 60), ("s", 1)):
        if seconds >= size:
            q, seconds = divmod(seconds, size)
            parts.append(f"{q} {name}")
    return " ".join(parts[:3]) if parts else "0 s"


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------

_YES = {"k", "yes", "kylla", "y", "yes", "j", "ja", "joo", "jep", "1", "true", "ok"}
_NO = {"e", "ei", "n", "no", "nej", "0", "false", "eip"}


def _prompt(prompt: str, suffix: str = "") -> str:
    return c("? ", "bright_magenta") + c(prompt, "bold") + (gray(suffix) if suffix else "") + " "


def ask(prompt: str, default: Any = None, *, allow_empty: bool = False,
        validator: Callable[[str], str | None] | None = None) -> str:
    """Asks for text. An empty answer returns the default."""
    suffix = f"[{default}]" if default not in (None, "") else ""
    while True:
        raw = input(_prompt(prompt, suffix)).strip()
        if not raw:
            if default is not None:
                return str(default)
            if allow_empty:
                return ""
            warn("Enter a value (Ctrl+C cancels).")
            continue
        if validator:
            problem = validator(raw)
            if problem:
                error(problem)
                continue
        return raw


def parse_number(raw: str) -> float:
    s = raw.strip().replace(" ", "").replace(" ", "").replace("_", "")
    if s.count(",") == 1 and "." not in s and not re.fullmatch(r"-?\d{1,3},\d{3}", s):
        s = s.replace(",", ".")
    s = s.replace(",", "")
    return float(s)


def ask_int(prompt: str, default: int | None = None, min_value: int | None = None,
            max_value: int | None = None) -> int:
    while True:
        raw = ask(prompt, default)
        try:
            value = int(parse_number(raw)) if any(ch in raw for ch in ".,e") else int(
                raw.replace(" ", "").replace("_", ""))
        except ValueError:
            error("Enter a whole number.")
            continue
        if min_value is not None and value < min_value:
            error(f"The smallest allowed value is {min_value}.")
            continue
        if max_value is not None and value > max_value:
            error(f"The largest allowed value is {max_value}.")
            continue
        return value


def ask_float(prompt: str, default: float | None = None, min_value: float | None = None,
              max_value: float | None = None) -> float:
    while True:
        raw = ask(prompt, default)
        try:
            value = parse_number(raw)
        except ValueError:
            error("Enter a number.")
            continue
        if min_value is not None and value < min_value:
            error(f"The smallest allowed value is {min_value}.")
            continue
        if max_value is not None and value > max_value:
            error(f"The largest allowed value is {max_value}.")
            continue
        return value


def ask_yes_no(prompt: str, default: bool | None = True) -> bool:
    suffix = "(Y/n)" if default is True else "(y/N)" if default is False else "(y/n)"
    while True:
        raw = input(_prompt(prompt, suffix)).strip().lower()
        if not raw and default is not None:
            return default
        if raw in _YES:
            return True
        if raw in _NO:
            return False
        warn("Answer y (yes) or n (no).")


def choose(prompt: str, options: Sequence[str], default: int | None = None,
           descriptions: Sequence[str] | None = None) -> int:
    """Shows a numbered list and returns the chosen index (0-based)."""
    for i, opt in enumerate(options, 1):
        desc = f"  {gray(descriptions[i - 1])}" if descriptions and i - 1 < len(descriptions) and descriptions[i - 1] else ""
        print(f"  {c(str(i).rjust(2), 'bright_yellow')}) {opt}{desc}")
    while True:
        raw = ask(prompt, default + 1 if default is not None else None)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        low = raw.lower()
        matches = [i for i, o in enumerate(options) if strip_ansi(o).lower().startswith(low)]
        if len(matches) == 1:
            return matches[0]
        error(f"Choose a number 1–{len(options)}.")


def choose_optional(prompt: str, options: Sequence[str],
                    descriptions: Sequence[str] | None = None) -> int | None:
    """Like choose, but empty or 0 returns None (back)."""
    for i, opt in enumerate(options, 1):
        desc = f"  {gray(descriptions[i - 1])}" if descriptions and i - 1 < len(descriptions) and descriptions[i - 1] else ""
        print(f"  {c(str(i).rjust(2), 'bright_yellow')}) {opt}{desc}")
    print(f"  {c(' 0', 'bright_yellow')}) {gray('Back')}")
    while True:
        raw = input(_prompt(prompt)).strip()
        if raw in ("", "0", "q"):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        error(f"Choose a number 0–{len(options)}.")


def strip_path_quotes(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1]
    if raw.startswith("& '") and raw.endswith("'"):  # PowerShell drag and drop
        raw = raw[3:-1]
    return raw


def ask_path(prompt: str, must_exist: bool = True, kind: str = "any",
             default: str | Path | None = None) -> Path:
    """Asks for a path. kind: 'any', 'file' or 'dir'. Drag and drop works."""
    while True:
        raw = ask(prompt, str(default) if default is not None else None)
        path = Path(os.path.expandvars(os.path.expanduser(strip_path_quotes(raw))))
        if must_exist and not path.exists():
            error(f"Path not found: {path}")
            continue
        if must_exist and kind == "file" and not path.is_file():
            error("Enter a file path (not a folder).")
            continue
        if must_exist and kind == "dir" and not path.is_dir():
            error("Enter a folder path.")
            continue
        return path


def multiline(prompt: str = "Type or paste the text", end: str = ".") -> str:
    """Reads many lines until a line contains only the end marker or EOF."""
    print(c("? ", "bright_magenta") + c(prompt, "bold"))
    print(gray(f"  (finish with a line containing only '{end}' or Ctrl+{'Z+Enter' if os.name == 'nt' else 'D'})"))
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == end:
            break
        lines.append(line)
    return "\n".join(lines)


def get_text(prompt: str = "Text") -> str:
    """Asks for text: one line, empty = multi-line input, @path = read from a file."""
    raw = input(_prompt(prompt, "(empty = multiple lines, @path = from a file)"))
    if raw.strip().startswith("@"):
        path = Path(os.path.expanduser(strip_path_quotes(raw.strip()[1:])))
        try:
            return read_text_file(path)
        except OSError as exc:
            error(f"Could not read the file: {exc}")
            return get_text(prompt)
    if raw.strip():
        return raw
    return multiline()


def read_text_file(path: Path) -> str:
    """Reads a text file guessing its encoding (utf-8, utf-16, cp1252, latin-1)."""
    data = Path(path).read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def pause(msg: str = "[Enter] continue…") -> None:
    try:
        input(gray(msg))
    except EOFError:
        pass


def confirm_danger(msg: str) -> bool:
    warn(msg)
    return ask_yes_no("Are you sure you want to continue?", default=False)


def paginate(lines: Sequence[str], page_size: int | None = None) -> None:
    """Shows long output one page at a time."""
    lines = list(lines)
    page_size = page_size or max(5, term_height() - 4)
    if len(lines) <= page_size or not is_tty():
        for line in lines:
            print(line)
        return
    pos = 0
    while pos < len(lines):
        for line in lines[pos:pos + page_size]:
            print(line)
        pos += page_size
        if pos >= len(lines):
            break
        left = len(lines) - pos
        try:
            raw = input(gray(f"-- {left} lines left: [Enter] next, a all, q quit -- ")).strip().lower()
        except EOFError:
            break
        if raw == "q":
            break
        if raw in ("a", "k"):
            for line in lines[pos:]:
                print(line)
            break


# --------------------------------------------------------------------------
# Progress
# --------------------------------------------------------------------------

class ProgressBar:
    """Simple progress bar. Usage: with ProgressBar(100) as pb: pb.update()."""

    def __init__(self, total: float | None, label: str = "", unit: str = "",
                 byte_mode: bool = False) -> None:
        self.total = total
        self.label = label
        self.unit = unit
        self.byte_mode = byte_mode
        self.current = 0.0
        self.start = time.time()
        self._last_draw = 0.0
        self._tty = sys.stdout.isatty()

    def __enter__(self) -> "ProgressBar":
        self.draw(force=True)
        return self

    def __exit__(self, *exc: Any) -> None:
        self.finish()

    def _fmt(self, value: float) -> str:
        if self.byte_mode:
            return fmt_bytes(value)
        return f"{int(value)}{self.unit}"

    def update(self, amount: float = 1) -> None:
        self.current += amount
        self.draw()

    def set(self, value: float) -> None:
        self.current = value
        self.draw()

    def draw(self, force: bool = False) -> None:
        now = time.time()
        if not self._tty or (not force and now - self._last_draw < 0.08):
            return
        self._last_draw = now
        elapsed = max(1e-6, now - self.start)
        rate = self.current / elapsed
        width = max(10, min(40, term_width() - 50))
        if self.total:
            frac = min(1.0, self.current / self.total)
            filled = int(frac * width)
            bar = c("█" * filled, "bright_green") + gray("░" * (width - filled))
            eta = (self.total - self.current) / rate if rate > 0 else 0
            text = (f"\r{self.label} {bar} {frac * 100:5.1f}% "
                    f"{self._fmt(self.current)}/{self._fmt(self.total)} "
                    f"{gray('ETA ' + fmt_duration(eta)) if self.current < self.total else ''}")
        else:
            spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[int(now * 10) % 10]
            text = f"\r{self.label} {c(spin, 'bright_cyan')} {self._fmt(self.current)}"
        print(text + " " * 4, end="", flush=True)

    def finish(self) -> None:
        if self._tty:
            self.draw(force=True)
            print()


def progress(iterable: Iterable[Any], total: int | None = None, label: str = "") -> Iterator[Any]:
    if total is None:
        try:
            total = len(iterable)  # type: ignore[arg-type]
        except TypeError:
            total = None
    with ProgressBar(total, label) as pb:
        for item in iterable:
            yield item
            pb.update()


class Spinner:
    """Spinning wait animation for long operations: with Spinner("Loading"): ..."""

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, label: str = "Please wait") -> None:
        self.label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            print(f"\r{c(frame, 'bright_cyan')} {self.label}…", end="", flush=True)
            i += 1
            self._stop.wait(0.08)
        print("\r" + " " * (visible_len(self.label) + 6) + "\r", end="", flush=True)

    def __enter__(self) -> "Spinner":
        if sys.stdout.isatty():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)


def countdown_bar(seconds: float, label: str = "", on_tick: Callable[[float], None] | None = None) -> None:
    """Shows elapsed time as a bar (timers). Ctrl+C stops."""
    start = time.time()
    width = max(10, min(50, term_width() - 30))
    while True:
        elapsed = time.time() - start
        left = max(0.0, seconds - elapsed)
        frac = min(1.0, elapsed / seconds) if seconds else 1.0
        filled = int(frac * width)
        mins, secs = divmod(int(round(left)), 60)
        hours, mins = divmod(mins, 60)
        clock = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"
        print(f"\r{label} {c('█' * filled, 'bright_green')}{gray('░' * (width - filled))} "
              f"{c(clock, 'bold')}  ", end="", flush=True)
        if on_tick:
            on_tick(left)
        if left <= 0:
            break
        time.sleep(min(0.25, left))
    print()


def beep(times: int = 1) -> None:
    for _ in range(times):
        print("\a", end="", flush=True)
        time.sleep(0.25)
