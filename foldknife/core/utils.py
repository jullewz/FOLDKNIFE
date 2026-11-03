"""General helpers: clipboard, HTTP, parsing dates and durations, files."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Iterator

USER_AGENT = "Foldknife/1.0 (+https://github.com/; Python multitool)"

# --------------------------------------------------------------------------
# Clipboard and opening files
# --------------------------------------------------------------------------


def copy_to_clipboard(text: str) -> bool:
    """Copies text to the clipboard. Returns True on success."""
    try:
        if os.name == "nt":
            subprocess.run(["clip"], input=text.encode("utf-16"), check=True)
            return True
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            return True
        for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, input=text.encode("utf-8"), check=True)
                return True
    except (OSError, subprocess.CalledProcessError):
        return False
    return False


def paste_from_clipboard() -> str | None:
    try:
        if os.name == "nt":
            out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                                 capture_output=True, check=True)
            return out.stdout.decode(errors="replace").rstrip("\r\n")
        if sys.platform == "darwin":
            return subprocess.run(["pbpaste"], capture_output=True, check=True).stdout.decode()
        for cmd in (["wl-paste"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]):
            if shutil.which(cmd[0]):
                return subprocess.run(cmd, capture_output=True, check=True).stdout.decode()
    except (OSError, subprocess.CalledProcessError):
        return None
    return None


def open_path(path: str | Path) -> bool:
    """Opens a file or folder with the default program."""
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def offer_copy(text: str) -> None:
    """Asks whether to copy the result to the clipboard."""
    from . import ui

    if not ui.is_tty():
        return
    if ui.ask_yes_no("Copy to clipboard?", default=False):
        if copy_to_clipboard(text):
            ui.success("Copied to clipboard.")
        else:
            ui.warn("The clipboard isn't available on this computer.")


def offer_save(text: str, default_name: str) -> Path | None:
    """Asks whether to save the result to a file."""
    from . import ui

    if not ui.is_tty():
        return None
    if not ui.ask_yes_no("Save to a file?", default=False):
        return None
    path = ui.ask_path("File name", must_exist=False, default=default_name)
    path.write_text(text, encoding="utf-8")
    ui.success(f"Saved: {path.resolve()}")
    return path


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


class NetError(Exception):
    """Network error with a readable explanation."""


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def http_request(url: str, method: str = "GET", data: bytes | None = None,
                 headers: dict[str, str] | None = None, timeout: float = 15.0,
                 follow_redirects: bool = True) -> tuple[int, dict[str, str], bytes, str]:
    """Makes an HTTP request. Returns (status, headers, body, final_url)."""
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    handlers: list[Any] = [urllib.request.HTTPSHandler(context=_ssl_context())]
    if not follow_redirects:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
                return None
        handlers.append(NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers.items()), body, resp.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, body, url
    except urllib.error.URLError as exc:
        raise NetError(f"Connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise NetError("Timed out – the server didn't answer in time.") from exc
    except OSError as exc:
        raise NetError(f"Network error: {exc}") from exc


def http_get(url: str, timeout: float = 15.0, headers: dict[str, str] | None = None) -> bytes:
    status, _, body, _ = http_request(url, headers=headers, timeout=timeout)
    if status >= 400:
        raise NetError(f"The server answered with error {status}.")
    return body


def http_json(url: str, timeout: float = 15.0, headers: dict[str, str] | None = None) -> Any:
    hdrs = {"Accept": "application/json"}
    hdrs.update(headers or {})
    body = http_get(url, timeout=timeout, headers=hdrs)
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NetError("The server returned invalid JSON.") from exc


def quote(text: str) -> str:
    return urllib.parse.quote(text, safe="")


# --------------------------------------------------------------------------
# Dates and durations
# --------------------------------------------------------------------------

FI_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
FI_WEEKDAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FI_MONTHS = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]


def fi_date(d: dt.date) -> str:
    return f"{d.year}-{d.month:02d}-{d.day:02d}"


def fi_datetime(d: dt.datetime) -> str:
    return f"{d.year}-{d.month:02d}-{d.day:02d} {d.hour:02d}:{d.minute:02d}:{d.second:02d}"


def parse_date(text: str, today: dt.date | None = None) -> dt.date:
    """Parses a date: 2026-12-31, 31.12.2026, 12/31/2026, today, tomorrow, yesterday, +7, -3."""
    today = today or dt.date.today()
    s = text.strip().lower()
    words = {"today": 0, "now": 0, "tomorrow": 1, "yesterday": -1,
             "tänään": 0, "tanaan": 0, "nyt": 0, "huomenna": 1, "ylihuomenna": 2,
             "eilen": -1, "toissapäivänä": -2, "toissapaivana": -2}
    if s in words:
        return today + dt.timedelta(days=words[s])
    m = re.fullmatch(r"([+-])\s*(\d+)\s*(days?|weeks?|pv|päivää|d|vk|viikkoa|w)?", s)
    if m:
        n = int(m.group(2)) * (7 if (m.group(3) or "") in ("vk", "viikkoa", "w", "week", "weeks") else 1)
        return today + dt.timedelta(days=n if m.group(1) == "+" else -n)
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})?", s)
    if m:
        year = int(m.group(3)) if m.group(3) else today.year
        if year < 100:
            year += 2000
        return dt.date(year, int(m.group(2)), int(m.group(1)))
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:  # month/day/year (US)
        return dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    raise ValueError(f"I don't understand the date {text!r} (try e.g. 2026-12-24)")


def parse_time_of_day(text: str) -> dt.time:
    m = re.fullmatch(r"\s*(\d{1,2})(?:[:.](\d{2}))?(?:[:.](\d{2}))?\s*", text)
    if not m:
        raise ValueError("Enter a time like 14:30.")
    h, mi, se = int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)
    return dt.time(h, mi, se)


_DUR_UNITS = {
    "ms": 0.001, "s": 1, "sek": 1, "sekuntia": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "mins": 60, "minute": 60, "minutes": 60, "hour": 3600, "hours": 3600, "hrs": 3600,
    "day": 86400, "days": 86400, "week": 604800, "weeks": 604800,
    "m": 60, "min": 60, "minuuttia": 60, "minuutti": 60,
    "h": 3600, "t": 3600, "tuntia": 3600, "tunti": 3600, "hr": 3600,
    "d": 86400, "pv": 86400, "päivä": 86400, "päivää": 86400, "vrk": 86400,
    "vk": 604800, "w": 604800, "viikko": 604800, "viikkoa": 604800,
}


def parse_duration(text: str) -> float:
    """Parses a duration: '25', '25min', '1h 30min', '90s', '1:30:00', '2.5h'. A plain number = minutes."""
    s = text.strip().lower().replace(",", ".")
    if not s:
        raise ValueError("Empty duration.")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s) * 60
    if re.fullmatch(r"\d+(:\d{1,2}){1,2}", s):
        parts = [int(p) for p in s.split(":")]
        total = 0
        for p in parts:
            total = total * 60 + p
        return float(total if len(parts) == 3 else total * 1)
    total = 0.0
    found = False
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([a-zäö]+)", s):
        if unit not in _DUR_UNITS:
            raise ValueError(f"Unknown time unit: {unit}")
        total += float(num) * _DUR_UNITS[unit]
        found = True
    if not found:
        raise ValueError(f"I don't understand the duration {text!r}")
    return total


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
             ".mypy_cache", ".pytest_cache", ".idea", ".vscode", "dist", "build", ".tox",
             "$RECYCLE.BIN", "System Volume Information"}


def is_hidden(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    if os.name == "nt":
        try:
            import stat

            return bool(path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)  # type: ignore[attr-defined]
        except (OSError, AttributeError):
            return False
    return False


def iter_files(root: str | Path, recursive: bool = True, include_hidden: bool = False,
               extensions: Iterable[str] | None = None, skip_dirs: set[str] | None = None) -> Iterator[Path]:
    """Walks files in a folder. Skips hidden and common junk folders."""
    root = Path(root)
    exts = {e.lower() if e.startswith(".") else "." + e.lower() for e in extensions} if extensions else None
    skip = SKIP_DIRS if skip_dirs is None else skip_dirs
    if root.is_file():
        yield root
        return
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            continue
        entries.sort(key=lambda e: e.name.lower())
        for entry in entries:
            p = Path(entry.path)
            if not include_hidden and (entry.name.startswith(".") or is_hidden(p)):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if recursive and entry.name not in skip:
                        stack.append(p)
                elif entry.is_file(follow_symlinks=False):
                    if exts is None or p.suffix.lower() in exts:
                        yield p
            except OSError:
                continue


def safe_filename(name: str, replacement: str = "_") -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', replacement, name).strip(" .")
    return name or "file"


def unique_path(path: Path) -> Path:
    """Returns a free path by appending (2), (3)… if needed."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 2
    while True:
        cand = path.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists():
            return cand
        i += 1


def human_list(items: Iterable[Any], conj: str = "and") -> str:
    items = [str(i) for i in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" {conj} " + items[-1]


def chunked(seq: list[Any], n: int) -> Iterator[list[Any]]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
