"""Interactive main menu, category menus, search and settings."""
from __future__ import annotations

import datetime as dt
import random
import shutil
import sys
import time
import traceback
import zipfile
from pathlib import Path

from . import ui
from .config import APP_NAME, VERSION, config, data_dir
from .registry import CATEGORIES, Category, Tool, all_tools, get, in_category, search
from .utils import NetError, open_path

# Letters in ANSI Shadow style; the logo is assembled from these so the rows line up.
_LETTERS = {
    "F": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "██║     ", "╚═╝     "],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "L": ["██╗     ", "██║     ", "██║     ", "██║     ", "███████╗", "╚══════╝"],
    "D": ["██████╗ ", "██╔══██╗", "██║  ██║", "██║  ██║", "██████╔╝", "╚═════╝ "],
    "K": ["██╗  ██╗", "██║ ██╔╝", "█████╔╝ ", "██╔═██╗ ", "██║  ██╗", "╚═╝  ╚═╝"],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
    "I": ["██╗", "██║", "██║", "██║", "██║", "╚═╝"],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
}

TIPS = [
    "Quick commands work directly: python foldknife.py calc \"2^10 + sqrt(2)\"",
    "Mark a tool as a favourite by typing a star and its number, e.g. *3",
    "Text fields accept a file too: @C:\\path\\file.txt",
    "Ctrl+C stops a tool and returns to the menu.",
    "Search (s) also finds tools by keywords, e.g. 'password' or 'image'.",
    "All your data is stored in ~/.foldknife – back it up from Settings.",
    "python foldknife.py list shows every tool's id.",
    "Game high scores are in the Games menu under High scores.",
    "You can drag a file path into the terminal with the mouse.",
    "In the calculator 'ans' means the previous result.",
]


def logo_lines(word: str = "FOLDKNIFE") -> list[str]:
    rows = [""] * 6
    for ch in word:
        for i, part in enumerate(_LETTERS[ch]):
            rows[i] += part
    return rows


def print_logo() -> None:
    rows = logo_lines()
    if shutil.get_terminal_size((80, 24)).columns < len(rows[0]) + 4:
        print("  " + ui.bold(ui.c("FOLDKNIFE", "bright_yellow")))
        return
    for i, row in enumerate(rows):
        start = (255, 190, 60)
        end = (230, 70, 50)
        shade = 1.0 - i * 0.07
        print("  " + ui.gradient(row, tuple(int(v * shade) for v in start),  # type: ignore[arg-type]
                                 tuple(int(v * shade) for v in end)))  # type: ignore[arg-type]


def greeting() -> str:
    hour = dt.datetime.now().hour
    if 5 <= hour < 10:
        text = "Good morning"
    elif 10 <= hour < 17:
        text = "Good afternoon"
    elif 17 <= hour < 22:
        text = "Good evening"
    else:
        text = "Good night"
    name = config().get("name")
    return f"{text}{', ' + name if name else ''}!"


# --------------------------------------------------------------------------
# Running a tool
# --------------------------------------------------------------------------

def run_tool(t: Tool, pause_after: bool = True) -> None:
    cfg = config()
    ui.clear()
    ui.header(t.name, t.description, color=t.category_obj.color)
    try:
        t.func()
    except KeyboardInterrupt:
        print()
        ui.warn("Interrupted.")
    except EOFError:
        print()
        ui.warn("Input ended.")
    except NetError as exc:
        ui.error(str(exc))
    except Exception as exc:  # noqa: BLE001 - shown to the user nicely
        ui.error(f"Unexpected error: {exc.__class__.__name__}: {exc}")
        if cfg.get("debug"):
            traceback.print_exc()
        else:
            print(ui.gray("(Debug tracebacks can be enabled in Settings.)"))
    finally:
        ui.show_cursor()
    cfg.add_recent(t.id)
    if pause_after:
        try:
            ui.pause()
        except KeyboardInterrupt:
            print()


def _tool_line(i: int, t: Tool, favs: set[str], name_w: int) -> str:
    star = ui.yellow("★") if t.id in favs else " "
    desc_w = max(10, ui.term_width() - name_w - 12)
    return (f" {star}{ui.c(str(i).rjust(3), 'bright_yellow')}) {ui.pad(t.name, name_w)} "
            f"{ui.gray(ui.truncate(t.description, desc_w))}")


def tool_list_menu(title: str, tools: list[Tool], subtitle: str = "", color: str = "bright_cyan",
                   empty_msg: str = "No tools.") -> None:
    """Shows a list of tools and runs the chosen one. Returns when the user goes back."""
    cfg = config()
    while True:
        ui.clear()
        ui.header(title, subtitle or None, color=color)
        if not tools:
            ui.info(empty_msg)
            ui.pause()
            return
        favs = set(cfg.get("favorites", []))
        name_w = min(34, max(ui.visible_len(t.name) for t in tools))
        for i, t in enumerate(tools, 1):
            print(_tool_line(i, t, favs, name_w))
        print()
        print(ui.gray("  number = open · *number = toggle favourite · Enter = back"))
        try:
            raw = input(ui.c("» ", "bright_magenta")).strip()
        except EOFError:
            return
        if raw in ("", "0", "q", "b"):
            return
        if raw.startswith("*") and raw[1:].isdigit():
            idx = int(raw[1:]) - 1
            if 0 <= idx < len(tools):
                added = cfg.toggle_favorite(tools[idx].id)
                ui.success(("Added to favourites: " if added else "Removed from favourites: ") + tools[idx].name)
                time.sleep(0.6)
            continue
        if raw.isdigit() and 1 <= int(raw) <= len(tools):
            run_tool(tools[int(raw) - 1])
            continue
        hits = search(raw)
        if hits:
            tools_for_search = hits
            tool_list_menu(f"Search: {raw}", tools_for_search, f"{len(hits)} matches")
        else:
            ui.error("Unknown choice.")
            time.sleep(0.6)


def category_menu(cat: Category) -> None:
    tools = sorted(in_category(cat.id), key=lambda t: t.name.lower())
    tool_list_menu(cat.name, tools, f"{cat.description} · {len(tools)} tools", cat.color)


def search_menu() -> None:
    query = ui.ask("Search term (e.g. password, image, game)")
    hits = search(query)
    if not hits:
        ui.warn("No matches. Try another word.")
        ui.pause()
        return
    tool_list_menu(f"Search: {query}", hits, f"{len(hits)} matches")


def favorites_menu() -> None:
    cfg = config()
    tools = [t for t in (get(i) for i in cfg.get("favorites", [])) if t]
    tool_list_menu("Favourites", tools, "Mark a favourite in a category menu: *number",
                   "bright_yellow", "No favourites yet. Add one in a category menu by typing *number.")


def recent_menu() -> None:
    cfg = config()
    tools = [t for t in (get(i) for i in cfg.get("recent", [])) if t]
    tool_list_menu("Recently used", tools, color="bright_blue", empty_msg="You haven't used any tools yet.")


def popular_menu() -> None:
    counts: dict[str, int] = config().get("tool_counts", {})
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    tools = [t for t in (get(i) for i, _ in ranked) if t][:20]
    tool_list_menu("Most used", tools, color="bright_green", empty_msg="No usage statistics yet.")


# --------------------------------------------------------------------------
# Settings and info
# --------------------------------------------------------------------------

def count_own_lines() -> tuple[int, int]:
    """Counts the lines and files of Foldknife's own source code."""
    root = Path(__file__).resolve().parent.parent
    files = list(root.rglob("*.py"))
    lines = 0
    for f in files:
        try:
            with f.open("rb") as fh:
                lines += sum(1 for _ in fh)
        except OSError:
            pass
    return lines, len(files)


def about() -> None:
    ui.clear()
    print_logo()
    lines, files = count_own_lines()
    tools = all_tools()
    ui.print_kv([
        ("Version", VERSION),
        ("Tools", f"{len(tools)} tools, {len(CATEGORIES)} categories"),
        ("Source code", f"{ui.fi_num(lines, 0)} lines in {files} files"),
        ("Python", sys.version.split()[0]),
        ("Data folder", str(data_dir())),
        ("Dependencies", "none – only the Python standard library"),
    ])
    print()
    rows = [(cat.name, len(in_category(cat.id))) for cat in CATEGORIES.values()]
    ui.bar_chart(rows, color="bright_yellow")
    print()
    ui.pause()


def backup_data() -> None:
    src = data_dir()
    target = Path.home() / f"foldknife-backup-{dt.datetime.now():%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(src))
    ui.success(f"Backup saved: {target}")


def settings_menu() -> None:
    cfg = config()
    while True:
        ui.clear()
        ui.header("Settings", f"Data folder: {data_dir()}")
        opts = [
            f"Colours: {ui.green('on') if cfg.get('colors', True) else ui.red('off')}",
            f"Your name in the greeting: {cfg.get('name') or ui.gray('(not set)')}",
            f"Debug tracebacks: {ui.green('on') if cfg.get('debug') else ui.gray('off')}",
            "Clear recently used",
            "Open data folder",
            "Back up all data to a zip file",
            ui.red("Delete all saved data"),
        ]
        choice = ui.choose_optional("Choice", opts)
        if choice is None:
            return
        if choice == 0:
            cfg.set("colors", not cfg.get("colors", True))
            ui.set_color(cfg.get("colors"))
        elif choice == 1:
            cfg.set("name", ui.ask("Your name", allow_empty=True))
        elif choice == 2:
            cfg.set("debug", not cfg.get("debug"))
        elif choice == 3:
            cfg.set("recent", [])
            ui.success("Cleared.")
            time.sleep(0.5)
        elif choice == 4:
            if not open_path(data_dir()):
                ui.info(str(data_dir()))
                ui.pause()
        elif choice == 5:
            backup_data()
            ui.pause()
        elif choice == 6:
            if ui.confirm_danger("This deletes tasks, notes, high scores and settings."):
                shutil.rmtree(data_dir(), ignore_errors=True)
                cfg.data.clear()
                cfg.load()
                ui.success("All data deleted.")
                ui.pause()


def first_run() -> None:
    cfg = config()
    if not cfg.get("first_run", True):
        return
    ui.clear()
    print_logo()
    ui.box([
        ui.bold("Welcome to Foldknife!"),
        "",
        f"It includes {len(all_tools())} tools in {len(CATEGORIES)} categories.",
        "Choose with a number, search with s and go back with Enter.",
        "Ctrl+C stops a tool and takes you back to the menu.",
    ], title="First start", color="bright_yellow")
    name = ui.ask("What should I call you? (Enter = skip)", allow_empty=True)
    cfg.data["name"] = name
    cfg.data["first_run"] = False
    cfg.save()


# --------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------

def main_menu() -> None:
    cfg = config()
    cats = [cat for cat in CATEGORIES.values() if in_category(cat.id)]
    tip = random.choice(TIPS)
    while True:
        ui.clear()
        print_logo()
        total = len(all_tools())
        print(ui.gray(f"  Python multitool · {total} tools · v{VERSION}"))
        print("  " + ui.bold(greeting()))
        print()
        half = (len(cats) + 1) // 2
        col_w = 34
        for i in range(half):
            left = cats[i]
            line = (f"  {ui.c(str(i + 1).rjust(2), 'bright_yellow')}) "
                    f"{ui.pad(ui.c(left.name, left.color), col_w - 8)}"
                    f"{ui.gray(str(len(in_category(left.id))).rjust(3))}")
            j = i + half
            if j < len(cats):
                right = cats[j]
                line = ui.pad(line, col_w + 6) + (
                    f"   {ui.c(str(j + 1).rjust(2), 'bright_yellow')}) "
                    f"{ui.pad(ui.c(right.name, right.color), col_w - 8)}"
                    f"{ui.gray(str(len(in_category(right.id))).rjust(3))}")
            print(line)
        print()
        menu = [("s", "Search"), ("f", "Favourites"), ("r", "Recent"), ("m", "Most used"),
                ("x", "Surprise me"), ("o", "Settings"), ("i", "About"), ("q", "Quit")]
        print("  " + "   ".join(f"{ui.c(k, 'bright_magenta')}) {v}" for k, v in menu))
        print()
        print(ui.gray(f"  Tip: {tip}"))
        try:
            raw = input(ui.c("\n» ", "bright_magenta")).strip().lower()
        except EOFError:
            raw = "q"
        if raw in ("q", "quit", "exit"):
            break
        if raw.isdigit() and 1 <= int(raw) <= len(cats):
            category_menu(cats[int(raw) - 1])
        elif raw == "s":
            search_menu()
        elif raw == "f":
            favorites_menu()
        elif raw == "r":
            recent_menu()
        elif raw == "m":
            popular_menu()
        elif raw == "x":
            run_tool(random.choice(all_tools()))
            tip = random.choice(TIPS)
        elif raw == "o":
            settings_menu()
        elif raw == "i":
            about()
        elif raw:
            t = get(raw)
            if t:
                run_tool(t)
            else:
                hits = search(raw)
                if hits:
                    tool_list_menu(f"Search: {raw}", hits, f"{len(hits)} matches")
                else:
                    ui.error("Unknown choice.")
                    time.sleep(0.6)


def run_interactive() -> int:
    cfg = config()
    cfg.data["runs"] = int(cfg.get("runs", 0)) + 1
    cfg.save()
    try:
        first_run()
        main_menu()
    except KeyboardInterrupt:
        print()
    ui.show_cursor()
    print(ui.c("Bye! 👋", "bright_yellow"))
    return 0
