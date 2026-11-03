"""Settings and persistent storage (JSON files in the user's home folder)."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

APP_NAME = "Foldknife"
VERSION = "1.0.0"


def data_dir() -> Path:
    """Returns the data folder (FOLDKNIFE_HOME or ~/.foldknife) and creates it if needed."""
    base = os.environ.get("FOLDKNIFE_HOME")
    path = Path(base).expanduser() if base else Path.home() / ".foldknife"
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_path(name: str) -> Path:
    return data_dir() / name


def load_json(name: str, default: Any) -> Any:
    """Loads a JSON file by name (without .json). A broken file is backed up."""
    path = data_dir() / f"{name}.json"
    if not path.exists():
        return copy.deepcopy(default)
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        backup = path.with_suffix(f".broken-{int(time.time())}.json")
        try:
            path.replace(backup)
        except OSError:
            pass
        return copy.deepcopy(default)


def save_json(name: str, data: Any) -> Path:
    """Saves a JSON file atomically (temporary file first, then replace)."""
    path = data_dir() / f"{name}.json"
    fd, tmp = tempfile.mkstemp(prefix=f".{name}-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


DEFAULTS: dict[str, Any] = {
    "colors": True,
    "favorites": [],
    "recent": [],
    "name": "",
    "debug": False,
    "first_run": True,
    "runs": 0,
    "tool_counts": {},
}


class Config:
    """Application settings. Stored in config.json."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        loaded = load_json("config", {})
        if isinstance(loaded, dict):
            self.data.update(loaded)

    def save(self) -> None:
        save_json("config", self.data)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    # --- favourites and history ---
    def toggle_favorite(self, tool_id: str) -> bool:
        favs: list[str] = self.data.setdefault("favorites", [])
        if tool_id in favs:
            favs.remove(tool_id)
            self.save()
            return False
        favs.append(tool_id)
        self.save()
        return True

    def add_recent(self, tool_id: str, limit: int = 15) -> None:
        recent: list[str] = self.data.setdefault("recent", [])
        if tool_id in recent:
            recent.remove(tool_id)
        recent.insert(0, tool_id)
        del recent[limit:]
        counts: dict[str, int] = self.data.setdefault("tool_counts", {})
        counts[tool_id] = counts.get(tool_id, 0) + 1
        self.save()


_config: Config | None = None


def config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
