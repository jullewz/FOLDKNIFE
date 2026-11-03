"""Productivity: tasks, notes, habits, pomodoro, counters, budget, flashcards,
diary, password vault, lists, time tracking, address book and decision matrix."""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..core import ui
from ..core.config import data_path, load_json, save_json
from ..core.registry import tool
from ..core.utils import FI_WEEKDAYS, copy_to_clipboard, fi_date, parse_date

TODAY = dt.date.today


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _next_id(items: list[dict[str, Any]]) -> int:
    return max((int(i.get("id", 0)) for i in items), default=0) + 1


def _pick_numbers(raw: str, maximum: int) -> list[int]:
    """Parses '1,3-5 7' → [0,2,3,4,6] (0-based)."""
    out: list[int] = []
    for part in re.findall(r"\d+\s*-\s*\d+|\d+", raw):
        if "-" in part:
            a, b = (int(x) for x in part.split("-"))
            out.extend(range(a, b + 1))
        else:
            out.append(int(part))
    return sorted({n - 1 for n in out if 1 <= n <= maximum})


# --------------------------------------------------------------------------
# Tasks
# --------------------------------------------------------------------------

PRIO_LABEL = {1: ("!!!", "bright_red"), 2: ("!! ", "bright_yellow"), 3: ("!  ", "gray")}


def parse_quick_task(text: str, today: dt.date | None = None) -> dict[str, Any]:
    """'Buy milk !1 @tomorrow #shop' → text, priority, due date, tags."""
    prio = 2
    due = None
    tags = re.findall(r"#([\wäöå-]+)", text)
    m = re.search(r"(?<!\S)!([123])(?!\S)", text)
    if m:
        prio = int(m.group(1))
    m_due = re.search(r"(?<!\S)@(\S+)", text)
    if m_due:
        try:
            due = parse_date(m_due.group(1), today).isoformat()
        except ValueError:
            due = None
    clean = re.sub(r"(?<!\S)(![123]|@\S+|#[\wäöå-]+)(?!\S)", "", text)
    return {"text": " ".join(clean.split()), "prio": prio, "due": due, "tags": tags}


def _task_line(i: int, t: dict[str, Any]) -> str:
    mark = ui.green("✔") if t["done"] else "☐"
    label, color = PRIO_LABEL.get(t.get("prio", 2), PRIO_LABEL[2])
    text = ui.c(t["text"], "strike", "gray") if t["done"] else t["text"]
    due = ""
    if t.get("due"):
        d = dt.date.fromisoformat(t["due"])
        days = (d - TODAY()).days
        due_txt = "today" if days == 0 else "tomorrow" if days == 1 else f"{-days} d overdue" if days < 0 else fi_date(d)
        due = " " + ui.c(f"⏰ {due_txt}", "bright_red" if days < 0 and not t["done"] else "bright_yellow" if days <= 1 else "gray")
    tags = " " + ui.gray(" ".join("#" + x for x in t.get("tags", []))) if t.get("tags") else ""
    return f"  {ui.c(str(i).rjust(3), 'bright_yellow')}. {mark} {ui.c(label, color)} {text}{due}{tags}"


@tool("productivity", "prod-to-do-list", "To-do list", "Tasks with priorities, due dates and tags (quick add: Buy milk !1 @tomorrow #shop)",
      ("todo", "task", "lista", "muistilista"))
def todo_tool() -> None:
    data = load_json("tehtavat", {"tasks": []})
    tasks: list[dict[str, Any]] = data["tasks"]
    show_done = False
    filt = ""
    while True:
        visible = [t for t in sorted(tasks, key=lambda t: (t["done"], t.get("prio", 2), t.get("due") or "9999"))
                   if (show_done or not t["done"]) and (not filt or filt in t.get("tags", []) or filt in t["text"].lower())]
        ui.clear()
        open_count = sum(not t["done"] for t in tasks)
        ui.header("To-do list", f"{open_count} open · {len(tasks) - open_count} done" + (f" · filter: {filt}" if filt else ""))
        for i, t in enumerate(visible, 1):
            print(_task_line(i, t))
        if not visible:
            print(ui.gray("  (no tasks)"))
        print(ui.gray("\n  text = add · number = done/undone · d N = delete · e N = edit · "
                      "t = show done · f tag = filter · clean = remove done · Enter = back"))
        raw = input(ui.c("» ", "bright_magenta")).strip()
        if not raw:
            break
        if raw.isdigit() or re.fullmatch(r"[\d,\s-]+", raw):
            for idx in _pick_numbers(raw, len(visible)):
                t = visible[idx]
                t["done"] = not t["done"]
                t["done_at"] = _now() if t["done"] else None
        elif m := re.fullmatch(r"d\s+([\d,\s-]+)", raw):
            for idx in sorted(_pick_numbers(m.group(1), len(visible)), reverse=True):
                tasks.remove(visible[idx])
        elif m := re.fullmatch(r"e\s+(\d+)", raw):
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(visible):
                new = ui.ask("New text (you can use !1 @date #tag)", visible[idx]["text"])
                visible[idx].update(parse_quick_task(new))
        elif raw == "t":
            show_done = not show_done
        elif raw.startswith("f ") or raw == "f":
            filt = raw[2:].strip().lstrip("#").lower()
        elif raw in ("clean", "siivoa"):
            data["tasks"] = tasks = [t for t in tasks if not t["done"]]
        else:
            item = parse_quick_task(raw)
            item.update({"id": _next_id(tasks), "done": False, "created": _now(), "done_at": None})
            tasks.append(item)
        save_json("tehtavat", data)


# --------------------------------------------------------------------------
# Notes
# --------------------------------------------------------------------------

@tool("productivity", "prod-notes", "Notes", "Write, search, pin and export notes", ("notes", "muistio", "muistiinpano"))
def notes_tool() -> None:
    data = load_json("muistiinpanot", {"notes": []})
    notes: list[dict[str, Any]] = data["notes"]
    while True:
        ui.clear()
        ui.header("Notes", f"{len(notes)} notes")
        ordered = sorted(notes, key=lambda n: n["updated"], reverse=True)
        ordered.sort(key=lambda n: not n.get("pinned"))  # stable sort: pinned first
        for i, n in enumerate(ordered, 1):
            pin = ui.yellow("📌") if n.get("pinned") else "  "
            preview = n["body"].replace("\n", " ")[:50]
            print(f"  {ui.c(str(i).rjust(3), 'bright_yellow')}. {pin} {ui.bold(n['title'][:30].ljust(30))} {ui.gray(preview)}")
        k = ui.choose_optional("Action", ["New note", "Read", "Edit / append text", "Pin / unpin",
                                           "Delete", "Search", "Export all to a Markdown file"])
        if k is None:
            return
        if k == 0:
            title = ui.ask("Title")
            body = ui.multiline("Text")
            notes.append({"id": _next_id(notes), "title": title, "body": body, "created": _now(), "updated": _now(), "pinned": False})
        elif k in (1, 2, 3, 4) and ordered:
            idx = ui.ask_int("Number", 1, 1, len(ordered)) - 1
            n = ordered[idx]
            if k == 1:
                ui.clear()
                ui.box(n["body"].splitlines() or [""], title=n["title"])
                print(ui.gray(f"  created {n['created'][:16].replace('T', ' ')} · edited {n['updated'][:16].replace('T', ' ')}"))
                ui.pause()
            elif k == 2:
                mode = ui.choose("Method", ["Append", "Replace the whole text", "Change the title"])
                if mode == 0:
                    n["body"] += "\n" + ui.multiline("Text to append")
                elif mode == 1:
                    n["body"] = ui.multiline("New text")
                else:
                    n["title"] = ui.ask("New title", n["title"])
                n["updated"] = _now()
            elif k == 3:
                n["pinned"] = not n.get("pinned")
            elif k == 4 and ui.ask_yes_no(f"Delete '{n['title']}'?", False):
                notes.remove(n)
        elif k == 5:
            q = ui.ask("Search word").lower()
            for n in notes:
                if q in n["title"].lower() or q in n["body"].lower():
                    print(f"  {ui.bold(n['title'])}: " + next((line for line in n["body"].splitlines() if q in line.lower()), "")[:80])
            ui.pause()
        elif k == 6:
            target = Path(ui.ask("File", "notes.md"))
            target.write_text("\n\n".join(f"# {n['title']}\n\n{n['body']}" for n in ordered), encoding="utf-8")
            ui.success(f"Exported: {target.resolve()}")
            ui.pause()
        save_json("muistiinpanot", data)


# --------------------------------------------------------------------------
# Habits
# --------------------------------------------------------------------------

def habit_streaks(log: dict[str, list[str]], habit: str, today: dt.date | None = None) -> tuple[int, int]:
    today = today or TODAY()
    days = sorted(dt.date.fromisoformat(d) for d, hs in log.items() if habit in hs)
    best = cur = 0
    prev = None
    for d in days:
        cur = cur + 1 if prev and (d - prev).days == 1 else 1
        best = max(best, cur)
        prev = d
    current = 0
    d = today if today.isoformat() in log and habit in log[today.isoformat()] else today - dt.timedelta(days=1)
    while d.isoformat() in log and habit in log[d.isoformat()]:
        current += 1
        d -= dt.timedelta(days=1)
    return current, best


@tool("productivity", "prod-habit-tracker", "Habit tracker", "Track daily habits, streaks and a 30-day grid", ("habit", "tapa", "streak", "putki"))
def habits_tool() -> None:
    data = load_json("tavat", {"habits": [], "log": {}})
    while True:
        ui.clear()
        today = TODAY()
        ui.header("Habit tracker", f"{FI_WEEKDAYS[today.weekday()]} {fi_date(today)}")
        days = [today - dt.timedelta(days=i) for i in range(29, -1, -1)]
        print(" " * 22 + "".join(ui.gray(d.strftime("%d")[1]) if d.day % 5 == 0 else " " for d in days))
        for i, h in enumerate(data["habits"], 1):
            cells = "".join(ui.green("■") if h in data["log"].get(d.isoformat(), []) else ui.gray("·") for d in days)
            cur, best = habit_streaks(data["log"], h, today)
            done_today = h in data["log"].get(today.isoformat(), [])
            print(f"  {ui.c(str(i).rjust(2), 'bright_yellow')}. {('✔ ' if done_today else '  ')}{h[:16].ljust(16)} {cells} "
                  f"{ui.c(f'🔥{cur}', 'bright_red') if cur else ''} {ui.gray(f'best {best}')}")
        if not data["habits"]:
            print(ui.gray("  No habits yet. Add e.g. 'Read 20 min', 'Drink 2 l of water', 'Go for a run'."))
        print(ui.gray("\n  number = mark today · + name = new habit · - number = delete · Enter = back"))
        raw = input(ui.c("» ", "bright_magenta")).strip()
        if not raw:
            return
        if raw.startswith("+"):
            name = raw[1:].strip()
            if name and name not in data["habits"]:
                data["habits"].append(name)
        elif raw.startswith("-") and raw[1:].strip().isdigit():
            idx = int(raw[1:].strip()) - 1
            if 0 <= idx < len(data["habits"]) and ui.ask_yes_no(f"Delete '{data['habits'][idx]}'?", False):
                data["habits"].pop(idx)
        else:
            for idx in _pick_numbers(raw, len(data["habits"])):
                h = data["habits"][idx]
                day = data["log"].setdefault(today.isoformat(), [])
                if h in day:
                    day.remove(h)
                else:
                    day.append(h)
        save_json("tavat", data)


# --------------------------------------------------------------------------
# Pomodoro
# --------------------------------------------------------------------------

@tool("productivity", "prod-pomodoro-timer", "Pomodoro timer", "25 min of work, 5 min break, a long break after every fourth – plus stats",
      ("pomodoro", "keskittyminen", "focus", "opiskelu"))
def pomodoro_tool() -> None:
    stats = load_json("pomodoro", {"days": {}})
    today_count = stats["days"].get(TODAY().isoformat(), 0)
    ui.info(f"{today_count} pomodoros done today.")
    week = [stats["days"].get((TODAY() - dt.timedelta(days=i)).isoformat(), 0) for i in range(6, -1, -1)]
    print(ui.gray("  Last 7 days: ") + ui.c(ui.sparkline(week) if any(week) else "–", "bright_red"))
    work = ui.ask_int("Work period (min)", 25, 1, 180)
    short = ui.ask_int("Short break (min)", 5, 1, 60)
    long_ = ui.ask_int("Long break (min)", 15, 1, 120)
    rounds = ui.ask_int("How many pomodoros", 4, 1, 20)
    from .system import _alarm_sound

    for r in range(1, rounds + 1):
        print(ui.c(f"\n🍅 Pomodoro {r}/{rounds} – focus!", "bold", "bright_red"))
        ui.countdown_bar(work * 60, "Work ")
        stats["days"][TODAY().isoformat()] = stats["days"].get(TODAY().isoformat(), 0) + 1
        save_json("pomodoro", stats)
        _alarm_sound(2)
        if r == rounds:
            break
        is_long = r % 4 == 0
        print(ui.c(f"☕ {'Long' if is_long else 'Short'} break – get up and stretch.", "bold", "bright_green"))
        ui.countdown_bar((long_ if is_long else short) * 60, "Break")
        _alarm_sound(1)
        input(ui.gray("Enter starts the next period…"))
    ui.success(f"Done! {stats['days'][TODAY().isoformat()]} pomodoros today in total.")


# --------------------------------------------------------------------------
# Day counters
# --------------------------------------------------------------------------

def _next_occurrence(d: dt.date, today: dt.date) -> dt.date:
    try:
        cand = d.replace(year=today.year)
    except ValueError:
        cand = dt.date(today.year, 3, 1)
    return cand if cand >= today else cand.replace(year=today.year + 1)


@tool("productivity", "prod-day-counters", "Day counters", "How many days until Christmas, holidays or a birthday?", ("countdown", "joulu", "loma", "days"))
def countdowns_tool() -> None:
    from .finnish import holidays

    data = load_json("laskurit", {"events": []})
    while True:
        ui.clear()
        today = TODAY()
        hol = holidays(today.year) | holidays(today.year + 1)
        builtin = []
        for name in ("Christmas Eve", "New Year's Day", "Midsummer Eve", "May Day (Vappu), Day of Finnish Labour", "Easter Sunday"):
            d = min((d for d, (n, _) in hol.items() if n.startswith(name) and d >= today), default=None)
            if d:
                builtin.append((name.split(",")[0], d, False))
        own = []
        for e in data["events"]:
            d = dt.date.fromisoformat(e["date"])
            if e.get("yearly"):
                d = _next_occurrence(d, today)
            own.append((e["name"], d, True))
        rows = sorted(own + builtin, key=lambda x: x[1])
        ui.header("Day counters", fi_date(today))
        for name, d, mine in rows:
            days = (d - today).days
            when = "TODAY! 🎉" if days == 0 else f"{days} days" if days >= 0 else f"{-days} days ago"
            weeks = f"({days // 7} wk {days % 7} d)" if days >= 7 else ""
            print(f"  {ui.c(when.rjust(12), 'bold', 'bright_green' if days <= 7 else 'bright_cyan')} {ui.gray(weeks.ljust(14))} "
                  f"{name} {ui.gray(fi_date(d))}{'' if mine else ui.gray(' ·')}")
        k = ui.choose_optional("Action", ["Add your own counter", "Delete your own counter"])
        if k is None:
            return
        if k == 0:
            name = ui.ask("Name (e.g. Summer holiday)")
            try:
                d = parse_date(ui.ask("Date"))
            except ValueError as exc:
                ui.error(str(exc))
                ui.pause()
                continue
            yearly = ui.ask_yes_no("Repeats every year (e.g. a birthday)?", False)
            data["events"].append({"name": name, "date": d.isoformat(), "yearly": yearly})
        elif data["events"]:
            idx = ui.choose("To delete", [e["name"] for e in data["events"]])
            data["events"].pop(idx)
        save_json("laskurit", data)


# --------------------------------------------------------------------------
# Budget
# --------------------------------------------------------------------------

DEFAULT_CATEGORIES = ["Food", "Housing", "Transport", "Entertainment", "Clothes", "Health", "Bills", "Hobbies", "Savings", "Other"]


@tool("productivity", "prod-budget", "Budget and expenses", "Record income and expenses, see a monthly summary by category",
      ("budjetti", "raha", "kulut", "talous", "menot"))
def budget_tool() -> None:
    data = load_json("budjetti", {"entries": [], "categories": DEFAULT_CATEGORIES, "limits": {}})
    while True:
        ui.clear()
        month = TODAY().strftime("%Y-%m")
        this = [e for e in data["entries"] if e["date"].startswith(month)]
        inc = sum(e["amount"] for e in this if e["amount"] > 0)
        exp = -sum(e["amount"] for e in this if e["amount"] < 0)
        ui.header("Budget", f"{TODAY():%m/%Y}: income {ui.fi_num(inc)} € · expenses {ui.fi_num(exp)} € · "
                              f"balance {ui.fi_num(inc - exp)} €")
        k = ui.choose_optional("Action", ["Add an expense", "Add income", "Monthly summary", "Latest transactions",
                                           "Set a monthly limit for a category", "Delete a transaction", "Export to CSV"])
        if k is None:
            return
        if k in (0, 1):
            amount = ui.ask_float("Amount (€)", min_value=0.01)
            cat = data["categories"][ui.choose("Category", data["categories"])] if k == 0 else "Income"
            note = ui.ask("Description", allow_empty=True)
            try:
                d = parse_date(ui.ask("Day", "today"))
            except ValueError:
                d = TODAY()
            data["entries"].append({"date": d.isoformat(), "amount": round(-amount if k == 0 else amount, 2), "category": cat, "note": note})
            lim = data["limits"].get(cat)
            if k == 0 and lim:
                used = -sum(e["amount"] for e in data["entries"] if e["category"] == cat and e["date"].startswith(month) and e["amount"] < 0)
                if used > lim:
                    ui.warn(f"{cat}: monthly limit {ui.fi_num(lim)} € exceeded ({ui.fi_num(used)} €)!")
                    ui.pause()
        elif k == 2:
            raw = ui.ask("Month (YYYY-MM)", month)
            entries = [e for e in data["entries"] if e["date"].startswith(raw)]
            by_cat: dict[str, float] = defaultdict(float)
            for e in entries:
                if e["amount"] < 0:
                    by_cat[e["category"]] += -e["amount"]
            items = sorted(by_cat.items(), key=lambda kv: -kv[1])
            ui.bar_chart(items, value_fmt=lambda v: f"{ui.fi_num(v)} €", color="bright_red")
            for cat, used in items:
                lim = data["limits"].get(cat)
                if lim:
                    pct = used / lim * 100
                    print(f"  {cat}: {pct:.0f} % of the {ui.fi_num(lim)} € limit" + (ui.red("  EXCEEDED") if pct > 100 else ""))
            ui.pause()
        elif k == 3:
            last = sorted(data["entries"], key=lambda e: e["date"], reverse=True)[:30]
            ui.table([(fi_date(dt.date.fromisoformat(e["date"])), e["category"], e["note"][:30],
                       ui.c(ui.fi_num(e["amount"]), "bright_green" if e["amount"] > 0 else "bright_red")) for e in last],
                     ["Day", "Category", "Description", "€"], align=["<", "<", "<", ">"])
            ui.pause()
        elif k == 4:
            cat = data["categories"][ui.choose("Category", data["categories"])]
            data["limits"][cat] = ui.ask_float("Monthly limit (€, 0 = remove)", data["limits"].get(cat, 0), 0)
            if not data["limits"][cat]:
                data["limits"].pop(cat)
        elif k == 5 and data["entries"]:
            last = sorted(data["entries"], key=lambda e: e["date"], reverse=True)[:20]
            idx = ui.choose("To delete", [f"{e['date']} {e['category']} {e['amount']} € {e['note']}" for e in last])
            data["entries"].remove(last[idx])
        elif k == 6:
            target = Path(ui.ask("File", "budget.csv"))
            with open(target, "w", encoding="utf-8-sig", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["date", "amount", "category", "description"])
                for e in sorted(data["entries"], key=lambda e: e["date"]):
                    w.writerow([e["date"], str(e["amount"]), e["category"], e["note"]])
            ui.success(f"Exported: {target.resolve()}")
            ui.pause()
        save_json("budjetti", data)


# --------------------------------------------------------------------------
# Flashcards (Leitner)
# --------------------------------------------------------------------------

def card_due(card: dict[str, Any], today: dt.date) -> bool:
    return dt.date.fromisoformat(card.get("next", today.isoformat())) <= today


def review_card(card: dict[str, Any], correct: bool, today: dt.date) -> None:
    box = card.get("box", 1)
    box = min(5, box + 1) if correct else 1
    card["box"] = box
    card["next"] = (today + dt.timedelta(days=2 ** (box - 1) if correct else 0)).isoformat()


@tool("productivity", "prod-flashcards", "Flashcards", "Learn vocabulary and facts with the Leitner box system",
      ("flashcard", "kortit", "sanasto", "opiskelu", "koe"))
def flashcards_tool() -> None:
    data = load_json("kortit", {"decks": {}})
    while True:
        ui.clear()
        today = TODAY()
        ui.header("Flashcards")
        names = list(data["decks"])
        for i, n in enumerate(names, 1):
            cards = data["decks"][n]
            due = sum(card_due(c, today) for c in cards)
            print(f"  {ui.c(str(i).rjust(2), 'bright_yellow')}. {n.ljust(24)} {len(cards):4} cards  {ui.c(f'{due} due', 'bright_green' if due else 'gray')}")
        k = ui.choose_optional("Action", ["Practise", "New deck", "Add cards", "Import from CSV (question;answer)",
                                           "Browse a deck", "Delete a deck"])
        if k is None:
            return
        if k == 1:
            name = ui.ask("Deck name", "Spanish words")
            data["decks"].setdefault(name, [])
        elif names:
            deck_name = names[ui.choose("Deck", names)] if len(names) > 1 else names[0]
            deck = data["decks"][deck_name]
            if k == 0:
                due = [c for c in deck if card_due(c, today)]
                if not due:
                    ui.success("Everything reviewed for today! 🎉")
                    ui.pause()
                    continue
                import random

                random.shuffle(due)
                right = 0
                for i, c in enumerate(due, 1):
                    ui.clear()
                    ui.box([ui.bold(c["q"])], title=f"{i}/{len(due)} · box {c.get('box', 1)}")
                    input(ui.gray("Enter shows the answer…"))
                    print("  " + ui.c(c["a"], "bold", "bright_green"))
                    ok = ui.ask_yes_no("Did you get it right?", True)
                    right += ok
                    review_card(c, ok, today)
                    save_json("kortit", data)
                ui.success(f"{right}/{len(due)} correct.")
                ui.pause()
            elif k == 2:
                print(ui.gray("Format: question ; answer  (an empty line ends)"))
                while True:
                    line = input("  ").strip()
                    if not line:
                        break
                    if ";" in line:
                        q, a = line.split(";", 1)
                        deck.append({"q": q.strip(), "a": a.strip(), "box": 1, "next": today.isoformat()})
            elif k == 3:
                path = ui.ask_path("CSV file", kind="file")
                for row in csv.reader(ui.read_text_file(path).splitlines(), delimiter=";"):
                    if len(row) >= 2 and row[0].strip():
                        deck.append({"q": row[0].strip(), "a": row[1].strip(), "box": 1, "next": today.isoformat()})
                ui.success(f"The deck now has {len(deck)} cards.")
                ui.pause()
            elif k == 4:
                ui.table([(c["q"][:40], c["a"][:40], c.get("box", 1), c.get("next", "")) for c in deck],
                         ["Question", "Answer", "Box", "Next"])
                ui.pause()
            elif k == 5 and ui.ask_yes_no(f"Delete the deck '{deck_name}'?", False):
                del data["decks"][deck_name]
        save_json("kortit", data)


# --------------------------------------------------------------------------
# Diary
# --------------------------------------------------------------------------

MOODS = {1: "😞", 2: "🙁", 3: "😐", 4: "🙂", 5: "😄"}


@tool("productivity", "prod-diary", "Diary", "Daily entries, mood and search", ("journal", "diary", "mieliala", "diary"))
def journal_tool() -> None:
    data = load_json("paivakirja", {"entries": {}})
    while True:
        ui.clear()
        entries = data["entries"]
        moods = [entries.get((TODAY() - dt.timedelta(days=i)).isoformat(), {}).get("mood") for i in range(29, -1, -1)]
        ui.header("Diary", f"{len(entries)} entries")
        if any(moods):
            print(ui.gray("  Mood 30 d: ") + "".join(MOODS.get(m, ui.gray("·")) if m else ui.gray("·") for m in moods[-14:]))
        k = ui.choose_optional("Action", ["Write today's entry", "Read an entry", "Browse the latest", "Search"])
        if k is None:
            return
        if k == 0:
            key = TODAY().isoformat()
            e = entries.get(key, {"text": "", "mood": None})
            if e["text"]:
                ui.box(e["text"].splitlines(), title="Already written today")
            text = ui.multiline("What happened today?")
            mood = ui.ask_int("Mood 1–5 (1 = bad, 5 = great)", e.get("mood") or 3, 1, 5)
            e["text"] = (e["text"] + "\n" + text).strip()
            e["mood"] = mood
            e["updated"] = _now()
            entries[key] = e
        elif k == 1:
            try:
                d = parse_date(ui.ask("Day", "yesterday"))
            except ValueError as exc:
                ui.error(str(exc))
                ui.pause()
                continue
            e = entries.get(d.isoformat())
            if e:
                ui.box(e["text"].splitlines(), title=f"{FI_WEEKDAYS[d.weekday()]} {fi_date(d)} {MOODS.get(e.get('mood'), '')}")
            else:
                ui.info("No entry for that day.")
            ui.pause()
        elif k == 2:
            for key in sorted(entries, reverse=True)[:10]:
                e = entries[key]
                d = dt.date.fromisoformat(key)
                print(ui.c(f"\n{FI_WEEKDAYS[d.weekday()]} {fi_date(d)} {MOODS.get(e.get('mood'), '')}", "bold", "bright_cyan"))
                print("  " + e["text"][:300].replace("\n", "\n  "))
            ui.pause()
        else:
            q = ui.ask("Search word").lower()
            for key in sorted(entries, reverse=True):
                if q in entries[key]["text"].lower():
                    line = next(x for x in entries[key]["text"].splitlines() if q in x.lower())
                    print(f"  {ui.c(key, 'bright_cyan')}: {line[:90]}")
            ui.pause()
        save_json("paivakirja", data)


# --------------------------------------------------------------------------
# Password vault
# --------------------------------------------------------------------------

VAULT_FILE = "holvi.dat"


def vault_load(password: str) -> dict[str, Any]:
    from .crypto import decrypt_bytes

    path = data_path(VAULT_FILE)
    if not path.exists():
        return {"entries": []}
    return json.loads(decrypt_bytes(path.read_bytes(), password).decode("utf-8"))


def vault_save(data: dict[str, Any], password: str) -> None:
    from .crypto import encrypt_bytes

    path = data_path(VAULT_FILE)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(encrypt_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"), password))
    tmp.replace(path)


@tool("productivity", "prod-password-vault", "Password vault", "Encrypted store for logins – protected by a master password (PBKDF2 + HMAC)",
      ("password manager", "salasana", "holvi", "tunnukset", "vault"))
def vault_tool() -> None:
    from .crypto import _ask_secret, gen_password

    exists = data_path(VAULT_FILE).exists()
    if not exists:
        ui.info("Creating a new vault. The master password can't be recovered – if you forget it, the data is lost.")
    master = _ask_secret("Master password", confirm=not exists)
    try:
        with ui.Spinner("Opening the vault"):
            data = vault_load(master)
    except ValueError:
        ui.error("Wrong master password.")
        return
    while True:
        ui.clear()
        entries: list[dict[str, Any]] = data["entries"]
        ui.header("Password vault", f"{len(entries)} logins · stored encrypted")
        for i, e in enumerate(sorted(entries, key=lambda e: e["name"].lower()), 1):
            print(f"  {ui.c(str(i).rjust(3), 'bright_yellow')}. {ui.bold(e['name'][:24].ljust(24))} {e.get('user', '')[:30].ljust(30)} {ui.gray(e.get('url', '')[:30])}")
        ordered = sorted(entries, key=lambda e: e["name"].lower())
        k = ui.choose_optional("Action", ["Add a login", "Copy password to clipboard", "Show details", "Edit", "Delete",
                                           "Change master password"])
        if k is None:
            return
        if k == 0:
            e = {"name": ui.ask("Service (e.g. Discord)"), "user": ui.ask("Username / email", allow_empty=True),
                 "url": ui.ask("Address", allow_empty=True)}
            if ui.ask_yes_no("Generate a strong password automatically?", True):
                e["password"] = gen_password(ui.ask_int("Length", 20, 8, 128))
                print("  Password: " + ui.bold(e["password"]))
            else:
                e["password"] = _ask_secret("Password")
            e["note"] = ui.ask("Note", allow_empty=True)
            e["updated"] = _now()
            entries.append(e)
        elif k in (1, 2, 3, 4) and ordered:
            e = ordered[ui.ask_int("Number", 1, 1, len(ordered)) - 1]
            if k == 1:
                if copy_to_clipboard(e["password"]):
                    ui.success("Copied! Clear the clipboard after use.")
                else:
                    ui.warn("The clipboard isn't available.")
                ui.pause()
            elif k == 2:
                ui.print_kv([("Service", e["name"]), ("Symbol", e.get("user", "")), ("Address", e.get("url", "")),
                             ("Password", "•" * len(e["password"])), ("Note", e.get("note", "")),
                             ("Updated", e.get("updated", "")[:16].replace("T", " "))])
                if ui.ask_yes_no("Show the password?", False):
                    print("  " + ui.bold(e["password"]))
                ui.pause()
            elif k == 3:
                for field, label in (("name", "Service"), ("user", "Symbol"), ("url", "Address"), ("note", "Note")):
                    e[field] = ui.ask(label, e.get(field, ""), allow_empty=True)
                if ui.ask_yes_no("Change the password?", False):
                    e["password"] = gen_password(20) if ui.ask_yes_no("Generate?", True) else _ask_secret("New password")
                e["updated"] = _now()
            elif k == 4 and ui.ask_yes_no(f"Delete '{e['name']}'?", False):
                entries.remove(e)
        elif k == 5:
            master = _ask_secret("New master password", confirm=True)
            ui.success("Master password changed.")
            ui.pause()
        with ui.Spinner("Saving"):
            vault_save(data, master)


# --------------------------------------------------------------------------
# Lists
# --------------------------------------------------------------------------

@tool("productivity", "prod-lists", "Lists", "Shopping lists, films to watch, gift ideas – any lists you can tick off",
      ("lista", "kauppalista", "ostoslista", "checklist"))
def lists_tool() -> None:
    data = load_json("listat", {"lists": {}})
    while True:
        ui.clear()
        names = list(data["lists"])
        ui.header("Lists")
        for i, n in enumerate(names, 1):
            items = data["lists"][n]
            checked = sum(1 for x in items if x["checked"])
            print(f"  {ui.c(str(i).rjust(2), 'bright_yellow')}. {n} {ui.gray(f'({checked}/{len(items)})')}")
        raw = ui.ask("Open by number, '+ name' creates a new one, '- number' deletes (Enter = back)", allow_empty=True)
        if not raw:
            return
        if raw.startswith("+"):
            data["lists"].setdefault(raw[1:].strip() or "New list", [])
        elif raw.startswith("-") and raw[1:].strip().isdigit():
            idx = int(raw[1:].strip()) - 1
            if 0 <= idx < len(names) and ui.ask_yes_no(f"Delete '{names[idx]}'?", False):
                del data["lists"][names[idx]]
        elif raw.isdigit() and 1 <= int(raw) <= len(names):
            _edit_list(data, names[int(raw) - 1])
        save_json("listat", data)


def _edit_list(data: dict[str, Any], name: str) -> None:
    items = data["lists"][name]
    while True:
        ui.clear()
        ui.header(name)
        for i, it in enumerate(items, 1):
            mark = ui.green("☑") if it["checked"] else "☐"
            text = ui.c(it["text"], "strike", "gray") if it["checked"] else it["text"]
            print(f"  {ui.c(str(i).rjust(3), 'bright_yellow')}. {mark} {text}")
        print(ui.gray("\n  text = add (several with commas) · numbers = tick · clean = remove ticked · Enter = back"))
        raw = input(ui.c("» ", "bright_magenta")).strip()
        if not raw:
            return
        if re.fullmatch(r"[\d,\s-]+", raw):
            for idx in _pick_numbers(raw, len(items)):
                items[idx]["checked"] = not items[idx]["checked"]
        elif raw in ("clean", "siivoa"):
            items[:] = [it for it in items if not it["checked"]]
        else:
            for part in raw.split(","):
                if part.strip():
                    items.append({"text": part.strip(), "checked": False})
        save_json("listat", data)


# --------------------------------------------------------------------------
# Time tracking
# --------------------------------------------------------------------------

def _duration(e: dict[str, Any]) -> float:
    end = dt.datetime.fromisoformat(e["end"]) if e.get("end") else dt.datetime.now()
    return (end - dt.datetime.fromisoformat(e["start"])).total_seconds()


@tool("productivity", "prod-time-tracker", "Time tracker", "Clock projects and tasks – reports for the day, week and all time",
      ("time tracking", "work hours", "tunnit", "projekti", "kellotus"))
def timetrack_tool() -> None:
    data = load_json("tyoaika", {"active": None, "entries": []})
    while True:
        ui.clear()
        act = data["active"]
        sub = (f"RUNNING: {act['project']} / {act['task']} – {ui.fmt_duration(_duration(act))}" if act else "No timer running")
        ui.header("Time tracker", sub, color="bright_green" if act else "bright_cyan")
        k = ui.choose_optional("Action", ["Start", "Quit", "Report", "Add manually", "Export to CSV"])
        if k is None:
            save_json("tyoaika", data)
            return
        if k == 0:
            if act:
                act["end"] = _now()
                data["entries"].append(act)
            projects = sorted({e["project"] for e in data["entries"]})
            if projects:
                print(ui.gray("  Previous projects: " + ", ".join(projects[:10])))
            data["active"] = {"project": ui.ask("Project", projects[-1] if projects else "School"),
                              "task": ui.ask("Task", "work"), "start": _now()}
        elif k == 1 and act:
            act["end"] = _now()
            data["entries"].append(act)
            data["active"] = None
            ui.success(f"Logged {ui.fmt_duration(_duration(act))}.")
            ui.pause()
        elif k == 2:
            period = ui.choose("Period", ["Today", "This week", "This month", "All"])
            now = dt.datetime.now()
            start = {0: dt.datetime.combine(now.date(), dt.time()),
                     1: dt.datetime.combine(now.date() - dt.timedelta(days=now.weekday()), dt.time()),
                     2: dt.datetime(now.year, now.month, 1), 3: dt.datetime(1970, 1, 1)}[period]
            totals: dict[str, float] = defaultdict(float)
            for e in data["entries"] + ([act] if act else []):
                if dt.datetime.fromisoformat(e["start"]) >= start:
                    totals[e["project"]] += _duration(e)
            ui.bar_chart(sorted(totals.items(), key=lambda kv: -kv[1]), value_fmt=ui.fmt_duration, color="bright_green")
            ui.info(f"Total {ui.fmt_duration(sum(totals.values()))}")
            ui.pause()
        elif k == 3:
            project = ui.ask("Project")
            task = ui.ask("Task", "work")
            try:
                d = parse_date(ui.ask("Day", "today"))
            except ValueError:
                d = TODAY()
            hours = ui.ask_float("Hours", 1, 0.01, 24)
            start = dt.datetime.combine(d, dt.time(9))
            data["entries"].append({"project": project, "task": task, "start": start.isoformat(),
                                    "end": (start + dt.timedelta(hours=hours)).isoformat()})
        elif k == 4:
            target = Path(ui.ask("File", "tyoaika.csv"))
            with open(target, "w", encoding="utf-8-sig", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["project", "task", "start", "end", "hours"])
                for e in data["entries"]:
                    w.writerow([e["project"], e["task"], e["start"], e.get("end", ""), f"{_duration(e) / 3600:.2f}"])
            ui.success(f"Exported: {target.resolve()}")
            ui.pause()
        save_json("tyoaika", data)


# --------------------------------------------------------------------------
# Address book
# --------------------------------------------------------------------------

def to_vcard(c: dict[str, Any]) -> str:
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{c['name']}"]
    parts = c["name"].split()
    lines.append(f"N:{parts[-1] if parts else ''};{' '.join(parts[:-1])};;;")
    if c.get("phone"):
        lines.append(f"TEL;TYPE=CELL:{c['phone']}")
    if c.get("email"):
        lines.append(f"EMAIL:{c['email']}")
    if c.get("address"):
        lines.append(f"ADR:;;{c['address']};;;;")
    if c.get("birthday"):
        lines.append(f"BDAY:{c['birthday']}")
    if c.get("note"):
        lines.append(f"NOTE:{c['note']}")
    lines.append("END:VCARD")
    return "\r\n".join(lines)


@tool("productivity", "prod-address-book", "Address book", "Contacts, upcoming birthdays and export to your phone (vCard)",
      ("yhteystiedot", "contacts", "osoitekirja", "vcard", "birthdays"))
def contacts_tool() -> None:
    data = load_json("yhteystiedot", {"contacts": []})
    while True:
        ui.clear()
        contacts: list[dict[str, Any]] = sorted(data["contacts"], key=lambda c: c["name"].lower())
        ui.header("Address book", f"{len(contacts)} contacts")
        for i, c in enumerate(contacts, 1):
            print(f"  {ui.c(str(i).rjust(3), 'bright_yellow')}. {ui.bold(c['name'][:26].ljust(26))} {c.get('phone', '')[:18].ljust(18)} {ui.gray(c.get('email', ''))}")
        k = ui.choose_optional("Action", ["Add", "Show / edit", "Delete", "Search", "Upcoming birthdays", "Export to a vCard file (.vcf)"])
        if k is None:
            return
        if k == 0:
            c = {f: ui.ask(label, allow_empty=f != "name") for f, label in (("name", "Name"), ("phone", "Phone"), ("email", "Email"),
                                                                             ("address", "Address"))}
            bday = ui.ask("Birthday (YYYY-MM-DD, optional)", allow_empty=True)
            try:
                c["birthday"] = parse_date(bday).isoformat() if bday else ""
            except ValueError:
                c["birthday"] = ""
            c["note"] = ui.ask("Note", allow_empty=True)
            data["contacts"].append(c)
        elif k in (1, 2) and contacts:
            c = contacts[ui.ask_int("Number", 1, 1, len(contacts)) - 1]
            if k == 1:
                ui.print_kv([(lbl, c.get(f, "")) for f, lbl in (("name", "Name"), ("phone", "Phone"), ("email", "Email"),
                                                                 ("address", "Address"), ("birthday", "Birthday"), ("note", "Note"))])
                if ui.ask_yes_no("Edit?", False):
                    for f, lbl in (("name", "Name"), ("phone", "Phone"), ("email", "Email"), ("address", "Address"), ("note", "Note")):
                        c[f] = ui.ask(lbl, c.get(f, ""), allow_empty=True)
            elif ui.ask_yes_no(f"Delete {c['name']}?", False):
                data["contacts"].remove(c)
        elif k == 3:
            q = ui.ask("Search word").lower()
            for c in contacts:
                if any(q in str(v).lower() for v in c.values()):
                    print(f"  {ui.bold(c['name'])} {c.get('phone', '')} {c.get('email', '')}")
            ui.pause()
        elif k == 4:
            today = TODAY()
            upcoming = []
            for c in contacts:
                if c.get("birthday"):
                    b = dt.date.fromisoformat(c["birthday"])
                    nxt = _next_occurrence(b, today)
                    upcoming.append(((nxt - today).days, c["name"], nxt.year - b.year, nxt))
            for days, name, age, nxt in sorted(upcoming)[:15]:
                print(f"  {('today!' if days == 0 else f'{days} d').rjust(8)}  {name} turns {age} ({fi_date(nxt)})")
            ui.pause()
        elif k == 5:
            target = Path(ui.ask("File", "contacts.vcf"))
            target.write_text("\r\n".join(to_vcard(c) for c in contacts) + "\r\n", encoding="utf-8")
            ui.success(f"Exported {len(contacts)} contacts: {target.resolve()}")
            ui.pause()
        save_json("yhteystiedot", data)


# --------------------------------------------------------------------------
# Decision matrix
# --------------------------------------------------------------------------

def decision_scores(options: list[str], criteria: list[tuple[str, int]], scores: dict[tuple[int, int], float]) -> list[tuple[str, float]]:
    max_total = sum(w for _, w in criteria) * 10 or 1
    totals = []
    for oi, opt in enumerate(options):
        total = sum(scores.get((oi, ci), 0) * w for ci, (_, w) in enumerate(criteria))
        totals.append((opt, total / max_total * 100))
    return sorted(totals, key=lambda kv: -kv[1])


@tool("productivity", "prod-decision-matrix", "Decision matrix", "Hard choice? Score the options with weighted criteria",
      ("decision", "valinta", "vertailu", "decision"))
def decision_tool() -> None:
    options = [o.strip() for o in ui.ask("Options separated by commas", "Phone A, Phone B, Phone C").split(",") if o.strip()]
    criteria = []
    print(ui.gray("Give the criteria and their importance 1–5 (an empty name ends)."))
    while True:
        name = ui.ask("Criterion", allow_empty=True)
        if not name:
            break
        criteria.append((name, ui.ask_int("Importance 1–5", 3, 1, 5)))
    if not options or not criteria:
        ui.warn("At least one option and one criterion are needed.")
        return
    scores: dict[tuple[int, int], float] = {}
    for ci, (cname, _) in enumerate(criteria):
        print(ui.c(f"\n{cname}", "bold", "bright_cyan"))
        for oi, opt in enumerate(options):
            scores[(oi, ci)] = ui.ask_float(f"  {opt} (0–10)", 5, 0, 10)
    result = decision_scores(options, criteria, scores)
    print()
    ui.bar_chart(result, value_fmt=lambda v: f"{v:.0f} / 100", color="bright_green")
    ui.success(f"Winner: {result[0][0]}")
