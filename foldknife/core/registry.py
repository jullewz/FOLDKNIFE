"""Tool registry. Every tool is registered with the @tool decorator."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    color: str
    description: str


CATEGORIES: dict[str, Category] = {c.id: c for c in [
    Category("files", "Files and folders", "bright_yellow", "Find, rename, organise, compare and compress"),
    Category("text", "Text", "bright_cyan", "Counters, conversions, cleanup and text tricks"),
    Category("crypto", "Hashing and encryption", "bright_magenta", "Hashes, encodings, passwords and encryption"),
    Category("math", "Maths and calculators", "bright_green", "Calculator, primes, statistics, matrices, finance"),
    Category("convert", "Conversions", "bright_blue", "Units, number bases, colours, dates"),
    Category("finnish", "Finland tools", "bright_white", "Finnish ID code, business ID, IBAN, reference numbers, holidays"),
    Category("network", "Network", "cyan", "IP, DNS, ping, ports, weather, currencies, speed test"),
    Category("system", "System", "yellow", "Hardware, processes, timers and cleanup"),
    Category("dev", "Developer", "green", "Line counter, regex, cron, gitignore, HTTP requests"),
    Category("data", "Data (CSV, JSON, SQLite)", "blue", "Tables, statistics, queries and charts"),
    Category("productivity", "Productivity", "magenta", "Tasks, notes, budget, pomodoro"),
    Category("games", "Games", "bright_red", "Snake, minesweeper, 2048, word guess, yahtzee and more"),
    Category("fun", "Fun", "bright_magenta", "Animations, ASCII art, jokes and randomisers"),
    Category("media", "Images and sound", "bright_yellow", "Images to ASCII, QR codes, sounds, EXIF"),
]}


@dataclass
class Tool:
    id: str
    name: str
    category: str
    func: Callable[[], None]
    description: str = ""
    keywords: tuple[str, ...] = field(default_factory=tuple)

    @property
    def category_obj(self) -> Category:
        return CATEGORIES[self.category]


_TOOLS: dict[str, Tool] = {}


def tool(category: str, tool_id: str, name: str, description: str = "",
         keywords: tuple[str, ...] | list[str] = ()) -> Callable[[Callable[[], None]], Callable[[], None]]:
    """Registers a function as a tool."""
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category: {category}")

    def decorator(func: Callable[[], None]) -> Callable[[], None]:
        if tool_id in _TOOLS:
            raise ValueError(f"Tool id already in use: {tool_id}")
        _TOOLS[tool_id] = Tool(tool_id, name, category, func, description, tuple(keywords))
        return func

    return decorator


def all_tools() -> list[Tool]:
    return list(_TOOLS.values())


def get(tool_id: str) -> Tool | None:
    return _TOOLS.get(tool_id)


def in_category(category: str) -> list[Tool]:
    return [t for t in _TOOLS.values() if t.category == category]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def search(query: str, limit: int = 30) -> list[Tool]:
    """Searches tools by name, description, id and keywords."""
    words = [_norm(w) for w in query.split() if w.strip()]
    if not words:
        return []
    scored: list[tuple[int, Tool]] = []
    for t in _TOOLS.values():
        name = _norm(t.name)
        hay_desc = _norm(t.description)
        hay_kw = " ".join(_norm(k) for k in t.keywords)
        hay_id = _norm(t.id)
        score = 0
        for w in words:
            if w in name:
                score += 10 + (5 if name.startswith(w) else 0)
            elif w in hay_id:
                score += 8
            elif w in hay_kw:
                score += 6
            elif w in hay_desc:
                score += 3
            elif w in _norm(CATEGORIES[t.category].name):
                score += 1
            else:
                score = 0
                break
        if score:
            scored.append((score, t))
    scored.sort(key=lambda x: (-x[0], x[1].name))
    return [t for _, t in scored[:limit]]
