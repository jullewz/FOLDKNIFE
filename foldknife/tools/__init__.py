"""Tool modules. Each module registers its tools when imported."""
from __future__ import annotations

import importlib

MODULES = [
    "files", "text", "crypto", "mathtools", "convert", "finnish",
    "network", "system", "dev", "data", "productivity",
    "games", "arcade", "boardgames", "fun", "media", "qr",
]

LOAD_ERRORS: dict[str, BaseException] = {}
_loaded = False


def load_all() -> None:
    """Imports all tool modules. A broken module doesn't crash the program."""
    global _loaded
    if _loaded:
        return
    for name in MODULES:
        try:
            importlib.import_module(f"{__name__}.{name}")
        except Exception as exc:  # noqa: BLE001
            LOAD_ERRORS[name] = exc
    _loaded = True
