"""Reads single key presses without Enter (real-time games).

On Windows msvcrt is used, elsewhere termios/tty/select.
If the terminal isn't interactive, it falls back to plain input().
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any

ARROWS = {"UP", "DOWN", "LEFT", "RIGHT"}
WASD = {"w": "UP", "s": "DOWN", "a": "LEFT", "d": "RIGHT",
        "W": "UP", "S": "DOWN", "A": "LEFT", "D": "RIGHT"}


def _normalize(ch: str) -> str:
    if ch in ("\r", "\n"):
        return "ENTER"
    if ch in ("\x7f", "\x08"):
        return "BACKSPACE"
    if ch == "\x1b":
        return "ESC"
    if ch == "\t":
        return "TAB"
    if ch == "\x03":
        raise KeyboardInterrupt
    return ch


def interactive() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


if os.name == "nt":  # pragma: no cover - Windows only
    import msvcrt

    _WIN_ARROWS = {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}

    class RawMode:
        def __enter__(self) -> "RawMode":
            print("\x1b[?25l", end="", flush=True)
            return self

        def __exit__(self, *exc: Any) -> None:
            print("\x1b[?25h", end="", flush=True)

    def _read_win() -> str:
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return _WIN_ARROWS.get(msvcrt.getwch(), "")
        return _normalize(ch)

    def getch() -> str:
        if not interactive():
            return _fallback()
        return _read_win()

    def get_key(timeout: float = 0.0) -> str | None:
        """Returns the pressed key, or None if nothing was pressed in time."""
        end = time.time() + timeout
        while True:
            if msvcrt.kbhit():
                return _read_win()
            if time.time() >= end:
                return None
            time.sleep(0.01)

else:
    import select
    import termios
    import tty

    _UNIX_ARROWS = {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT",
                    "OA": "UP", "OB": "DOWN", "OC": "RIGHT", "OD": "LEFT"}

    class RawMode:
        """Puts the terminal into cbreak mode for a game and restores it afterwards."""

        def __init__(self) -> None:
            self.fd = sys.stdin.fileno() if interactive() else None
            self.old: Any = None

        def __enter__(self) -> "RawMode":
            if self.fd is not None:
                self.old = termios.tcgetattr(self.fd)
                tty.setcbreak(self.fd)
                print("\x1b[?25l", end="", flush=True)
            return self

        def __exit__(self, *exc: Any) -> None:
            if self.fd is not None and self.old is not None:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
                print("\x1b[?25h", end="", flush=True)

    def _read_byte(fd: int, timeout: float | None) -> bytes:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            return b""
        return os.read(fd, 1)

    def _read_unix(timeout: float | None) -> str | None:
        fd = sys.stdin.fileno()
        first = _read_byte(fd, timeout)
        if not first:
            return None
        if first == b"\x1b":
            seq = b""
            while len(seq) < 2:
                nxt = _read_byte(fd, 0.02)
                if not nxt:
                    break
                seq += nxt
            return _UNIX_ARROWS.get(seq.decode(errors="ignore"), "ESC")
        data = first
        if first[0] >= 0xC0:  # multi-byte UTF-8 (ä, ö…)
            need = 1 if first[0] < 0xE0 else 2 if first[0] < 0xF0 else 3
            for _ in range(need):
                data += _read_byte(fd, 0.05)
        return _normalize(data.decode("utf-8", errors="ignore"))

    def getch() -> str:
        if not interactive():
            return _fallback()
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            key = _read_unix(None)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return key or ""

    def get_key(timeout: float = 0.0) -> str | None:
        """Call inside a RawMode block. Returns a key or None."""
        if not interactive():
            return None
        return _read_unix(timeout)


def _fallback() -> str:
    try:
        raw = input()
    except EOFError:
        return "ESC"
    if not raw:
        return "ENTER"
    return raw[0]


def direction(key: str | None) -> str | None:
    """Turns arrow keys and WASD into a direction."""
    if key is None:
        return None
    if key in ARROWS:
        return key
    return WASD.get(key)
