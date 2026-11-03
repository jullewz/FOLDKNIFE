"""Command line interface: python foldknife.py [command] [arguments]."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from . import ui
from .config import APP_NAME, VERSION, config
from .registry import CATEGORIES, all_tools, get, in_category, search
from .utils import NetError


def _need(args: list[str], n: int, usage: str) -> bool:
    if len(args) < n:
        ui.error(f"Usage: python foldknife.py {usage}")
        return False
    return True


def q_list(args: list[str]) -> int:
    for cat in CATEGORIES.values():
        tools = sorted(in_category(cat.id), key=lambda t: t.id)
        if not tools:
            continue
        print(ui.c(f"\n{cat.name} ({len(tools)})", "bold", cat.color))
        for t in tools:
            print(f"  {ui.c(t.id.ljust(22), 'bright_yellow')} {t.name} {ui.gray('– ' + t.description)}")
    print(ui.gray(f"\nTotal {len(all_tools())} tools. Run: python foldknife.py <id>"))
    return 0


def q_search(args: list[str]) -> int:
    if not _need(args, 1, "search <words>"):
        return 1
    hits = search(" ".join(args))
    if not hits:
        ui.warn("No matches.")
        return 1
    for t in hits:
        print(f"  {ui.c(t.id.ljust(22), 'bright_yellow')} {t.name} {ui.gray('– ' + t.description)}")
    return 0


def q_calc(args: list[str]) -> int:
    if not _need(args, 1, 'calc "2*(3+4)"'):
        return 1
    from ..tools.mathtools import evaluate, format_result

    try:
        print(format_result(evaluate(" ".join(args))))
    except Exception as exc:  # noqa: BLE001
        ui.error(str(exc))
        return 1
    return 0


def q_convert(args: list[str]) -> int:
    if not _need(args, 1, "convert 10 km mi"):
        return 1
    from ..tools.convert import convert_text

    try:
        print(convert_text(" ".join(args)))
    except Exception as exc:  # noqa: BLE001
        ui.error(str(exc))
        return 1
    return 0


def q_hash(args: list[str]) -> int:
    if not _need(args, 1, "hash <file or text> [algorithm]"):
        return 1
    from ..tools.crypto import hash_bytes, hash_file

    algo = args[1] if len(args) > 1 else "sha256"
    p = Path(args[0])
    try:
        digest = hash_file(p, algo) if p.is_file() else hash_bytes(args[0].encode("utf-8"), algo)
    except ValueError as exc:
        ui.error(str(exc))
        return 1
    print(f"{algo}: {digest}")
    return 0


def q_password(args: list[str]) -> int:
    from ..tools.crypto import gen_password

    length = int(args[0]) if args and args[0].isdigit() else 20
    count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    for _ in range(count):
        print(gen_password(length))
    return 0


def q_uuid(args: list[str]) -> int:
    import uuid

    n = int(args[0]) if args and args[0].isdigit() else 1
    for _ in range(n):
        print(uuid.uuid4())
    return 0


def q_ip(args: list[str]) -> int:
    from ..tools.network import local_ip, public_ip_info

    print(f"Local IP: {local_ip()}")
    try:
        data = public_ip_info()
        print(f"Public IP:  {data.get('ip')} ({data.get('city', '?')}, {data.get('country', '?')})")
    except NetError as exc:
        ui.warn(str(exc))
    return 0


def q_qr(args: list[str]) -> int:
    if not _need(args, 1, "qr <text>"):
        return 1
    from ..tools.qr import encode_text, render_terminal

    print(render_terminal(encode_text(" ".join(args))))
    return 0


def q_b64(args: list[str]) -> int:
    import base64

    if not _need(args, 1, "b64 <text>"):
        return 1
    print(base64.b64encode(" ".join(args).encode()).decode())
    return 0


def q_b64d(args: list[str]) -> int:
    import base64

    if not _need(args, 1, "b64d <base64>"):
        return 1
    try:
        print(base64.b64decode("".join(args) + "===").decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        ui.error(f"Invalid base64: {exc}")
        return 1
    return 0


def q_weather(args: list[str]) -> int:
    from ..tools.network import show_weather

    show_weather(" ".join(args) or "Helsinki")
    return 0


def q_hetu(args: list[str]) -> int:
    if not _need(args, 1, "hetu <Finnish personal identity code>"):
        return 1
    from ..tools.finnish import hetu_info

    try:
        info = hetu_info(args[0])
    except ValueError as exc:
        ui.error(str(exc))
        return 1
    ui.print_kv(info)
    return 0


def q_ref(args: list[str]) -> int:
    if not _need(args, 1, "refnum <base number>"):
        return 1
    from ..tools.finnish import make_reference, format_reference

    try:
        print(format_reference(make_reference(args[0])))
    except ValueError as exc:
        ui.error(str(exc))
        return 1
    return 0


def q_dice(args: list[str]) -> int:
    from ..tools.fun import roll_dice

    try:
        total, rolls, mod = roll_dice(args[0] if args else "1d6")
    except ValueError as exc:
        ui.error(str(exc))
        return 1
    print(f"{rolls} {'+' if mod >= 0 else '-'} {abs(mod)} = {total}" if mod else f"{rolls} = {total}")
    return 0


def q_coin(args: list[str]) -> int:
    import secrets

    print(secrets.choice(["Heads", "Tails"]))
    return 0


def q_run(args: list[str]) -> int:
    if not _need(args, 1, "run <tool-id>"):
        return 1
    return run_by_id(args[0])


QUICK: dict[str, tuple[Callable[[list[str]], int], str]] = {
    "list": (q_list, "list all tools"),
    "search": (q_search, "search tools"),
    "calc": (q_calc, 'calculator: calc "sqrt(2)*10"'),
    "convert": (q_convert, "units: convert 10 km mi"),
    "hash": (q_hash, "checksum: hash file.zip sha256"),
    "password": (q_password, "passwords: password 24 5"),
    "pw": (q_password, ""),
    "uuid": (q_uuid, "UUIDs: uuid 3"),
    "ip": (q_ip, "your IP address"),
    "qr": (q_qr, "QR code in the terminal: qr https://example.com"),
    "b64": (q_b64, "base64 encode"),
    "b64d": (q_b64d, "base64 decode"),
    "weather": (q_weather, "weather: weather London"),
    "hetu": (q_hetu, "check a Finnish personal identity code"),
    "refnum": (q_ref, "Finnish payment reference from a base number"),
    "dice": (q_dice, "dice: dice 3d6+2"),
    "coin": (q_coin, "heads or tails"),
    "run": (q_run, "run a tool by id"),
    # Finnish aliases (hidden)
    "lista": (q_list, ""), "haku": (q_search, ""), "laske": (q_calc, ""), "muunna": (q_convert, ""),
    "salasana": (q_password, ""), "weather": (q_weather, ""), "saa": (q_weather, ""), "viite": (q_ref, ""),
    "noppa": (q_dice, ""), "kolikko": (q_coin, ""),
}


def run_by_id(tool_id: str) -> int:
    from .app import run_tool

    t = get(tool_id)
    if not t:
        ui.error(f"Unknown tool: {tool_id}")
        hits = search(tool_id.replace("-", " "))
        if hits:
            print("Did you mean: " + ", ".join(h.id for h in hits[:5]))
        return 1
    run_tool(t, pause_after=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    quick_help = "\n".join(f"  {name:<10} {desc}" for name, (_, desc) in QUICK.items() if desc)
    parser = argparse.ArgumentParser(
        prog="foldknife",
        description=f"{APP_NAME} – a Python multitool. Without a command the menu opens.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Quick commands:\n{quick_help}\n\nAny tool can be run by id, e.g. python foldknife.py files-duplicates",
    )
    parser.add_argument("command", nargs="?", help="quick command or tool id")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="command arguments")
    parser.add_argument("--no-color", "--ei-varit", dest="no_color", action="store_true", help="no colours")
    parser.add_argument("--version", "--versio", dest="version", action="store_true", help="show version")
    parser.add_argument("--debug", action="store_true", help="show error tracebacks")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    cfg = config()
    ui.init_terminal(color=False if ns.no_color else None)
    if not cfg.get("colors", True):
        ui.set_color(False)
    if ns.debug:
        cfg.data["debug"] = True

    from ..tools import LOAD_ERRORS, load_all

    load_all()
    if LOAD_ERRORS and cfg.get("debug"):
        for mod, exc in LOAD_ERRORS.items():
            ui.warn(f"Could not load module {mod}: {exc}")

    if ns.version:
        print(f"{APP_NAME} {VERSION} – {len(all_tools())} tools")
        return 0
    if not ns.command:
        from .app import run_interactive

        return run_interactive()
    cmd = ns.command.lower()
    try:
        if cmd in QUICK:
            return QUICK[cmd][0](ns.args)
        return run_by_id(cmd)
    except KeyboardInterrupt:
        print()
        return 130
    except NetError as exc:
        ui.error(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
