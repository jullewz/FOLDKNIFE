"""System tools: hardware, processes, disks, timers, shutdown, benchmark and cleanup."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import getpass
import hashlib
import json
import locale
import math
import os
import platform
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from ..core import ui
from ..core.registry import tool
from ..core.utils import copy_to_clipboard, paste_from_clipboard, parse_duration, parse_time_of_day

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"


def _run(cmd: list[str], timeout: float = 5.0) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout)
        enc = "oem" if IS_WIN else (locale.getpreferredencoding(False) or "utf-8")
        return out.stdout.decode(enc, errors="replace")
    except (OSError, subprocess.TimeoutExpired, LookupError):
        return ""


# --------------------------------------------------------------------------
# Hardware info
# --------------------------------------------------------------------------

def cpu_name() -> str:
    if IS_WIN:
        try:
            import winreg

            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            return platform.processor()
    if IS_MAC:
        return _run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip() or platform.processor()
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith(("model name", "hardware", "processor\t: arm")):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def memory() -> tuple[int, int] | None:
    """(total memory, free memory) in bytes."""
    if IS_WIN:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return int(stat.ullTotalPhys), int(stat.ullAvailPhys)
        return None
    if IS_MAC:
        total = int(_run(["sysctl", "-n", "hw.memsize"]).strip() or 0)
        vm = _run(["vm_stat"])
        page = int(re.search(r"page size of (\d+)", vm).group(1)) if "page size" in vm else 4096  # type: ignore[union-attr]
        free = sum(int(m) for m in re.findall(r"Pages (?:free|inactive|speculative):\s+(\d+)", vm)) * page
        return (total, free) if total else None
    try:
        info = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines() if ":" in line)
        total = int(info["MemTotal"].split()[0]) * 1024
        avail = int(info.get("MemAvailable", info["MemFree"]).split()[0]) * 1024
        return total, avail
    except (OSError, KeyError, ValueError):
        return None


def uptime_seconds() -> float | None:
    if IS_WIN:
        import ctypes

        ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong  # type: ignore[attr-defined]
        return ctypes.windll.kernel32.GetTickCount64() / 1000  # type: ignore[attr-defined]
    if IS_MAC:
        m = re.search(r"sec = (\d+)", _run(["sysctl", "-n", "kern.boottime"]))
        return time.time() - int(m.group(1)) if m else None
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except OSError:
        return None


def battery() -> str | None:
    if IS_WIN:
        import ctypes

        class SPS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]

        s = SPS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)) and s.BatteryFlag != -128 and s.BatteryLifePercent != -1:  # type: ignore[attr-defined]
            return f"{s.BatteryLifePercent} % ({'plugged in' if s.ACLineStatus == 1 else 'on battery'})"
        return None
    if IS_MAC:
        m = re.search(r"(\d+)%;\s*([\w ]+);", _run(["pmset", "-g", "batt"]))
        return f"{m.group(1)} % ({m.group(2)})" if m else None
    for bat in Path("/sys/class/power_supply").glob("BAT*"):
        try:
            cap = (bat / "capacity").read_text().strip()
            st = (bat / "status").read_text().strip()
            return f"{cap} % ({ {'Charging': 'charging', 'Discharging': 'on battery', 'Full': 'full'}.get(st, st) })"
        except OSError:
            continue
    return None


def disks() -> list[tuple[str, int, int, int]]:
    """(drive, size, used, free)."""
    mounts: list[str] = []
    if IS_WIN:
        mounts = [f"{chr(c)}:\\" for c in range(ord("A"), ord("Z") + 1) if os.path.exists(f"{chr(c)}:\\")]
    elif IS_MAC:
        mounts = ["/"] + [str(p) for p in Path("/Volumes").glob("*") if p.is_dir()]
    else:
        real = {"ext2", "ext3", "ext4", "xfs", "btrfs", "vfat", "exfat", "ntfs", "ntfs3", "fuseblk", "zfs", "f2fs", "apfs", "hfs"}
        try:
            for line in Path("/proc/mounts").read_text().splitlines():
                parts = line.split()
                if len(parts) > 2 and parts[2] in real and parts[1] not in mounts:
                    mounts.append(parts[1].replace("\\040", " "))
        except OSError:
            mounts = ["/"]
        if not mounts:
            mounts = ["/"]
    out = []
    for m in mounts:
        try:
            u = shutil.disk_usage(m)
            out.append((m, u.total, u.used, u.free))
        except OSError:
            continue
    return out


def gpu_names() -> list[str]:
    if IS_WIN:
        out = _run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"], timeout=8)
        return [line.strip() for line in out.splitlines() if line.strip()]
    if IS_MAC:
        return re.findall(r"Chipset Model: (.+)", _run(["system_profiler", "SPDisplaysDataType"], timeout=10))
    if shutil.which("lspci"):
        return [line.split(": ", 1)[-1] for line in _run(["lspci"]).splitlines() if "VGA" in line or "3D controller" in line]
    return []


def screen_size() -> str | None:
    if IS_WIN:
        try:
            import ctypes

            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            user32.SetProcessDPIAware()
            return f"{user32.GetSystemMetrics(0)} × {user32.GetSystemMetrics(1)}"
        except Exception:  # noqa: BLE001
            return None
    return None


def os_name() -> str:
    if IS_WIN:
        build = platform.version()
        name = "Windows 11" if platform.release() == "10" and int(build.split(".")[-1] or 0) >= 22000 else f"Windows {platform.release()}"
        return f"{name} (build {build})"
    if IS_MAC:
        return f"macOS {platform.mac_ver()[0]}"
    try:
        info = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
        return info.get("PRETTY_NAME", "Linux").strip('"') + f" (kernel {platform.release()})"
    except OSError:
        return f"{platform.system()} {platform.release()}"


# --------------------------------------------------------------------------
# Processes
# --------------------------------------------------------------------------

def list_processes() -> list[tuple[int, str, int, float | None]]:
    """(pid, name, memory in bytes, cpu %)."""
    procs = []
    if IS_WIN:
        import csv as _csv
        import io

        out = _run(["tasklist", "/fo", "csv", "/nh"], timeout=10)
        for row in _csv.reader(io.StringIO(out)):
            if len(row) >= 5:
                mem = int(re.sub(r"\D", "", row[4]) or 0) * 1024
                procs.append((int(row[1]), row[0], mem, None))
    else:
        out = _run(["ps", "-Ao", "pid=,pcpu=,rss=,comm="], timeout=10)
        for line in out.splitlines():
            parts = line.split(None, 3)
            if len(parts) == 4:
                try:
                    procs.append((int(parts[0]), os.path.basename(parts[3]), int(parts[2]) * 1024, float(parts[1])))
                except ValueError:
                    continue
    procs.sort(key=lambda p: -p[2])
    return procs


def kill_process(pid: int, force: bool = False) -> bool:
    if IS_WIN:
        cmd = ["taskkill", "/PID", str(pid)] + (["/F"] if force else [])
        return subprocess.run(cmd, capture_output=True).returncode == 0
    import signal

    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# Benchmark (module-level functions so multiprocessing works on Windows)
# --------------------------------------------------------------------------

def bench_int(n: int = 3_000_000) -> float:
    start = time.perf_counter()
    total = 0
    for i in range(n):
        total += i * i % 7
    return time.perf_counter() - start


def bench_float(n: int = 1_000_000) -> float:
    start = time.perf_counter()
    acc = 0.0
    for i in range(n):
        x = i * 0.001
        acc += math.sin(x) * math.cos(x) + math.sqrt(x)
    return time.perf_counter() - start


def bench_sieve(n: int = 3_000_000) -> float:
    start = time.perf_counter()
    flags = bytearray([1]) * (n + 1)
    for i in range(2, int(n ** 0.5) + 1):
        if flags[i]:
            flags[i * i::i] = bytearray(len(range(i * i, n + 1, i)))
    sum(flags)
    return time.perf_counter() - start


def bench_sort(n: int = 500_000) -> float:
    rng = random.Random(1)
    data = [rng.random() for _ in range(n)]
    start = time.perf_counter()
    data.sort()
    sorted(data, reverse=True)
    return time.perf_counter() - start


def bench_hash(mb: int = 200) -> float:
    block = b"\xab" * (1 << 20)
    start = time.perf_counter()
    h = hashlib.sha256()
    for _ in range(mb):
        h.update(block)
    h.hexdigest()
    return time.perf_counter() - start


def bench_json(n: int = 20_000) -> float:
    obj = [{"id": i, "nimi": f"user {i}", "pisteet": [i, i * 2, i * 3], "aktiivinen": i % 2 == 0} for i in range(n)]
    start = time.perf_counter()
    for _ in range(3):
        json.loads(json.dumps(obj))
    return time.perf_counter() - start


BENCHMARKS = [("Integers", bench_int, 0.35), ("Floats", bench_float, 0.25), ("Prime sieve", bench_sieve, 0.12),
              ("Sorting", bench_sort, 0.25), ("SHA-256 200 MB", bench_hash, 0.45), ("JSON", bench_json, 0.30)]


def _multi_worker(_: int) -> float:
    return bench_int(2_000_000)


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("system", "sys-system-info", "System info", "OS, CPU, memory, GPU, battery and uptime",
      ("system", "laitteisto", "pc", "specs", "cpu", "ram"))
def sysinfo_tool() -> None:
    with ui.Spinner("Collecting info"):
        mem = memory()
        up = uptime_seconds()
        gpus = gpu_names()
        bat = battery()
        cpu = cpu_name()
    rows: list[tuple[str, Any]] = [
        ("Operating system", os_name()), ("Hostname", socket.gethostname()), ("User", getpass.getuser()),
        ("Processor", cpu), ("Cores / threads", os.cpu_count()), ("Architecture", platform.machine()),
    ]
    if mem:
        total, free = mem
        used_pct = (total - free) / total * 100
        rows.append(("Memory", f"{ui.fmt_bytes(total)} ({used_pct:.0f} % used, {ui.fmt_bytes(free)} free)"))
    for g in gpus:
        rows.append(("Graphics card", g))
    res = screen_size()
    if res:
        rows.append(("Screen resolution", res))
    if up:
        rows.append(("Uptime", ui.fmt_duration(up) + f" (booted {dt.datetime.fromtimestamp(time.time() - up):%Y-%m-%d %H:%M})"))
    if bat:
        rows.append(("Battery", bat))
    rows += [("Python", f"{platform.python_version()} ({platform.python_implementation()})"),
             ("Python interpreter", sys.executable), ("Encoding", locale.getpreferredencoding(False))]
    ui.print_kv(rows)
    print()
    for mount, total, used, free in disks():
        frac = used / total if total else 0
        width = 30
        bar = ui.c("█" * int(frac * width), "bright_red" if frac > 0.9 else "bright_yellow" if frac > 0.75 else "bright_green") + ui.gray("░" * (width - int(frac * width)))
        print(f"  {mount[:20].ljust(20)} {bar} {frac * 100:3.0f} %  {ui.fmt_bytes(free)} free / {ui.fmt_bytes(total)}")


@tool("system", "sys-processes", "Processes", "Programs using the most memory, search and kill", ("process", "task manager", "taskkill", "ps"))
def processes_tool() -> None:
    with ui.Spinner("Fetching processes"):
        procs = list_processes()
    filt = ui.ask("Filter by name (empty = top 25)", allow_empty=True).lower()
    shown = [p for p in procs if filt in p[1].lower()] if filt else procs[:25]
    ui.table([(pid, name[:40], ui.fmt_bytes(mem), f"{cpu:.1f}" if cpu is not None else "-") for pid, name, mem, cpu in shown],
             ["PID", "Name", "Memory", "CPU %"], align=[">", "<", ">", ">"])
    ui.info(f"{len(procs)} processes in total, memory {ui.fmt_bytes(sum(p[2] for p in procs))}.")
    pid_raw = ui.ask("PID of the process to kill (empty = none)", allow_empty=True)
    if pid_raw.isdigit():
        pid = int(pid_raw)
        name = next((p[1] for p in procs if p[0] == pid), "?")
        if ui.confirm_danger(f"Killing {name} (PID {pid}). Unsaved data will be lost."):
            force = ui.ask_yes_no("Force it (if the program isn't responding)?", False)
            ui.success("Killed.") if kill_process(pid, force) else ui.error("Couldn't kill it (permissions?).")


@tool("system", "sys-disk-drives", "Disk drives", "Size and free space of all drives", ("levy", "disk", "asema", "free space"))
def disks_tool() -> None:
    rows = []
    for mount, total, used, free in disks():
        rows.append((mount, ui.fmt_bytes(total), ui.fmt_bytes(used), ui.fmt_bytes(free), f"{used / total * 100:.0f} %" if total else "-"))
    ui.table(rows, ["Drive", "Size", "Used", "Free", "Full"], align=["<", ">", ">", ">", ">"])


@tool("system", "sys-environment", "Environment variables and PATH", "Shows variables and checks that PATH folders exist",
      ("env", "path", "environment", "muuttuja"))
def env_tool() -> None:
    mode = ui.choose("Show", ["PATH folders", "All environment variables", "Search for a variable"])
    if mode == 0:
        seen = set()
        for p in os.environ.get("PATH", "").split(os.pathsep):
            if not p:
                continue
            exists = os.path.isdir(p)
            dup = p.lower() in seen
            seen.add(p.lower())
            mark = ui.green("✔") if exists else ui.red("✘ missing")
            print(f"  {mark} {p}" + (ui.yellow("  (duplicate)") if dup else ""))
    else:
        q = ui.ask("Search word", allow_empty=True).lower() if mode == 2 else ""
        rows = [(k, v[:80]) for k, v in sorted(os.environ.items()) if q in k.lower() or q in v.lower()]
        ui.table(rows, ["Variable", "Value"], max_col_width=80)


@tool("system", "sys-stopwatch", "Stopwatch", "Enter = lap, q + Enter = stop", ("stopwatch", "kello", "lap", "ajanotto"))
def stopwatch_tool() -> None:
    input(ui.gray("Press Enter to start…"))
    start = last = time.perf_counter()
    laps = []
    print(ui.gray("Running. Enter = lap, q + Enter = stop."))
    while True:
        cmd = input().strip().lower()
        now = time.perf_counter()
        laps.append((now - last, now - start))
        last = now
        lap, total = laps[-1]
        print(f"  {ui.c(f'#{len(laps)}', 'bright_yellow')} lap {ui.bold(_clock(lap))}   total {_clock(total)}")
        if cmd == "q":
            break
    if len(laps) > 1:
        best = min(range(len(laps)), key=lambda i: laps[i][0])
        ui.info(f"Fastest lap #{best + 1}: {_clock(laps[best][0])}, average {_clock(sum(lp for lp, _ in laps) / len(laps))}")


def _clock(sec: float) -> str:
    m, s = divmod(sec, 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:05.2f}" if h else f"{m:02d}:{s:05.2f}"


def _alarm_sound(times: int = 5) -> None:
    for _ in range(times):
        if IS_WIN:
            try:
                import winsound

                winsound.Beep(880, 300)
                winsound.Beep(1320, 300)
                continue
            except Exception:  # noqa: BLE001
                pass
        print("\a", end="", flush=True)
        time.sleep(0.6)


@tool("system", "sys-timer", "Timer", "Egg timer: 5 min, 1h30min, 90s… beeps at the end", ("timer", "ajastin", "munakello", "countdown"))
def timer_tool() -> None:
    try:
        seconds = parse_duration(ui.ask("Duration (e.g. 5, 10min, 1h 30min, 90s)", "5min"))
    except ValueError as exc:
        ui.error(str(exc))
        return
    label = ui.ask("Label (optional)", allow_empty=True)
    ui.countdown_bar(seconds, label or "⏳")
    ui.box([ui.c(f"TIME'S UP! {label}", "bold", "bright_red")], color="bright_red")
    _alarm_sound()


@tool("system", "sys-alarm-clock", "Alarm clock", "Sounds an alarm at a set time (keep the window open)", ("alarm", "alarm", "kello"))
def alarm_tool() -> None:
    try:
        t = parse_time_of_day(ui.ask("Alarm time (HH:MM)", "07:00"))
    except ValueError as exc:
        ui.error(str(exc))
        return
    now = dt.datetime.now()
    target = dt.datetime.combine(now.date(), t)
    if target <= now:
        target += dt.timedelta(days=1)
    ui.info(f"Alarm {target:%Y-%m-%d at %H:%M} – in {ui.fmt_duration((target - now).total_seconds())}. Ctrl+C cancels.")
    ui.countdown_bar((target - now).total_seconds(), "⏰")
    ui.box([ui.c("WAKE UP! ⏰", "bold", "bright_yellow")], color="bright_yellow")
    _alarm_sound(10)


@tool("system", "sys-scheduled-shutdown", "Scheduled shutdown", "Shut down or restart the computer on a timer – or cancel it",
      ("shutdown", "sammuta", "restart", "ajastus"))
def shutdown_tool() -> None:
    k = ui.choose("Action", ["Shut down on a timer", "Restart on a timer", "Cancel a scheduled shutdown"])
    if k == 2:
        cmd = ["shutdown", "/a"] if IS_WIN else ["shutdown", "-c"]
        try:
            res = subprocess.run(cmd, capture_output=True)
        except OSError:
            ui.error("shutdown command not found.")
            return
        ui.success("Schedule cancelled.") if res.returncode == 0 else ui.warn("Nothing to cancel (or missing permissions).")
        return
    try:
        seconds = parse_duration(ui.ask("How soon (e.g. 30min, 2h)", "60min"))
    except ValueError as exc:
        ui.error(str(exc))
        return
    when = dt.datetime.now() + dt.timedelta(seconds=seconds)
    if not ui.confirm_danger(f"The computer {'shuts down' if k == 0 else 'restarts'} at {when:%H:%M}. Save your work in time."):
        return
    if IS_WIN:
        cmd = ["shutdown", "/s" if k == 0 else "/r", "/t", str(int(seconds))]
    else:
        cmd = ["shutdown", "-h" if k == 0 else "-r", f"+{max(1, round(seconds / 60))}"]
    try:
        res = subprocess.run(cmd, capture_output=True)
    except OSError:
        ui.error("shutdown command not found.")
        return
    if res.returncode == 0:
        ui.success("Scheduled. You can cancel it from the same tool.")
    else:
        ui.error("Didn't work – Linux/macOS often need sudo.")


@tool("system", "sys-benchmark", "Benchmark", "Measures CPU speed with Python and gives a score (single and all cores)",
      ("benchmark", "nopeus", "testi", "cpu"))
def benchmark_tool() -> None:
    ui.info("The test takes about 10–30 seconds.")
    scores = []
    for name, fn, ref in BENCHMARKS:
        with ui.Spinner(name):
            took = min(fn() for _ in range(2))
        score = ref / took * 1000
        scores.append(score)
        print(f"  {name.ljust(16)} {took * 1000:8.0f} ms   {ui.c(f'{score:6.0f} pts', 'bright_cyan')}")
    single = math.exp(sum(math.log(s) for s in scores) / len(scores))
    cores = os.cpu_count() or 1
    multi = None
    if cores > 1 and ui.ask_yes_no(f"Run the multi-core test ({cores} processes)?", True):
        with ui.Spinner("Multi-core test"):
            t0 = time.perf_counter()
            with concurrent.futures.ProcessPoolExecutor(max_workers=cores) as pool:
                list(pool.map(_multi_worker, range(cores)))
            wall = time.perf_counter() - t0
        single_time = bench_int(2_000_000)
        speedup = single_time * cores / wall
        multi = single * speedup
        print(f"  {'Multi-core'.ljust(16)} {wall * 1000:8.0f} ms   {ui.c(f'{multi:6.0f} pts', 'bright_cyan')}  ({speedup:.1f}× speedup)")
    ui.box([ui.c(f"Single-core: {single:.0f} points", "bold", "bright_green")] +
           ([ui.c(f"Multi-core: {multi:.0f} points", "bold", "bright_green")] if multi else []) +
           [ui.gray("1000 pts ≈ a typical 2020s laptop")], title="Result")
    from .games import record_score

    record_score("Benchmark", int(single))


@tool("system", "sys-python-packages", "Python packages", "Installed Python libraries and their versions", ("pip", "paketti", "kirjasto", "python"))
def packages_tool() -> None:
    from importlib import metadata

    q = ui.ask("Filter (empty = all)", allow_empty=True).lower()
    rows = sorted({(d.metadata["Name"] or "?", d.version) for d in metadata.distributions()}, key=lambda r: r[0].lower())
    rows = [r for r in rows if q in r[0].lower()]
    ui.paginate([f"  {name.ljust(36)} {ui.gray(ver)}" for name, ver in rows])
    ui.info(f"{len(rows)} packages · Python {platform.python_version()} · {sys.executable}")


@tool("system", "sys-terminal-test", "Terminal test", "Does your terminal support colours, Unicode and emoji?", ("terminal", "colours", "unicode", "konsoli"))
def terminal_tool() -> None:
    ui.print_kv([("Size", f"{ui.term_width()} × {ui.term_height()}"), ("Encoding", sys.stdout.encoding),
                 ("Interactive", "yes" if ui.is_tty() else "no"), ("TERM", os.environ.get("TERM", "-")),
                 ("Windows Terminal", "yes" if os.environ.get("WT_SESSION") else "no")])
    print("\n16 colours:")
    print("  " + "".join(ui.c(" ██ ", 30 + i) for i in range(8)))
    print("  " + "".join(ui.c(" ██ ", 90 + i) for i in range(8)))
    print("256 colours:")
    for row in range(6):
        print("  " + "".join(ui.fg256("█", 16 + row * 36 + i) for i in range(36)))
    print("Truecolor:")
    print("  " + ui.rainbow("█" * 72))
    print("Unicode: accents ÅÄÖ åäö · boxes ┌─┬─┐ ╭─╮ · braille ⣿⡇⠿ · emoji 🔪🐻🌲❄️ · kanji 日本")


@tool("system", "sys-temp-file-cleanup", "Temp file cleanup", "Deletes old files from the temp folder and frees space",
      ("temp", "siivous", "clean", "roskat"))
def temp_clean_tool() -> None:
    tmp = Path(tempfile.gettempdir())
    days = ui.ask_int("Delete files older than N days", 7, 1)
    cutoff = time.time() - days * 86400
    files = []
    for root, _dirs, names in os.walk(tmp):
        for n in names:
            p = Path(root) / n
            try:
                st = p.stat()
                if st.st_mtime < cutoff:
                    files.append((p, st.st_size))
            except OSError:
                continue
    total = sum(s for _, s in files)
    ui.info(f"The folder {tmp} has {len(files)} files older than {days} days ({ui.fmt_bytes(total)}).")
    if not files or not ui.ask_yes_no("Delete them? (files in use are skipped)", False):
        return
    removed = freed = 0
    for p, s in files:
        try:
            p.unlink()
            removed += 1
            freed += s
        except OSError:
            pass
    for root, dirs, _ in os.walk(tmp, topdown=False):
        for d in dirs:
            try:
                (Path(root) / d).rmdir()
            except OSError:
                pass
    ui.success(f"Deleted {removed} files, freed {ui.fmt_bytes(freed)}.")


@tool("system", "sys-hosts-file", "Hosts file", "Shows the active entries in the hosts file", ("hosts", "dns", "esto"))
def hosts_tool() -> None:
    path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/drivers/etc/hosts" if IS_WIN else Path("/etc/hosts")
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        ui.error(f"Couldn't read: {exc}")
        return
    active = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    ui.info(f"{path} – {len(active)} active entries")
    for line in active[:300]:
        print("  " + line)


@tool("system", "sys-clipboard-tools", "Clipboard tools", "Clean up, transform or clear clipboard text", ("clipboard", "clipboard", "copy", "paste"))
def clipboard_tool() -> None:
    text = paste_from_clipboard()
    if text is None:
        ui.error("Couldn't read the clipboard on this machine.")
        return
    preview = text[:300] + ("…" if len(text) > 300 else "")
    ui.box(preview.splitlines()[:12] or [ui.gray("(empty)")], title=f"Clipboard · {len(text)} characters")
    ops = ["Remove extra spaces and blank lines", "Join into one line", "UPPERCASE", "lowercase",
           "Remove formatting (plain text)", "Clear the clipboard"]
    k = ui.choose_optional("Action", ops)
    if k is None:
        return
    if k == 0:
        new = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if line.strip())
    elif k == 1:
        new = " ".join(text.split())
    elif k == 2:
        new = text.upper()
    elif k == 3:
        new = text.lower()
    elif k == 4:
        new = text
    else:
        new = ""
    if copy_to_clipboard(new):
        ui.success("Clipboard updated.")
    else:
        ui.error("Couldn't write to the clipboard.")
