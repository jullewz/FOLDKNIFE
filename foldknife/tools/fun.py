"""Fun: banners, talking animals, magic 8-ball, jokes, dice, randomiser, animations (Matrix, Game of Life,
Mandelbrot, donut, fire, clock), generators, flags and ASCII art."""
from __future__ import annotations

import datetime as dt
import math
import random
import re
import secrets
import sys
import textwrap
import time
from typing import Callable

from ..core import keys, ui
from ..core.registry import tool
from ..core.utils import offer_copy

# --------------------------------------------------------------------------
# Big font
# --------------------------------------------------------------------------

FONT: dict[str, list[str]] = {
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"], "B": ["████ ", "█   █", "████ ", "█   █", "████ "],
    "C": [" ████", "█    ", "█    ", "█    ", " ████"], "D": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"], "F": ["█████", "█    ", "████ ", "█    ", "█    "],
    "G": [" ████", "█    ", "█  ██", "█   █", " ████"], "H": ["█   █", "█   █", "█████", "█   █", "█   █"],
    "I": ["███", " █ ", " █ ", " █ ", "███"], "J": ["  ███", "    █", "    █", "█   █", " ███ "],
    "K": ["█   █", "█  █ ", "███  ", "█  █ ", "█   █"], "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"], "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "O": [" ███ ", "█   █", "█   █", "█   █", " ███ "], "P": ["████ ", "█   █", "████ ", "█    ", "█    "],
    "Q": [" ███ ", "█   █", "█ █ █", "█  █ ", " ██ █"], "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "S": [" ████", "█    ", " ███ ", "    █", "████ "], "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "U": ["█   █", "█   █", "█   █", "█   █", " ███ "], "V": ["█   █", "█   █", "█   █", " █ █ ", "  █  "],
    "W": ["█   █", "█   █", "█ █ █", "██ ██", "█   █"], "X": ["█   █", " █ █ ", "  █  ", " █ █ ", "█   █"],
    "Y": ["█   █", " █ █ ", "  █  ", "  █  ", "  █  "], "Z": ["█████", "   █ ", "  █  ", " █   ", "█████"],
    "0": [" ███ ", "█  ██", "█ █ █", "██  █", " ███ "], "1": [" ██ ", "█ █ ", "  █ ", "  █ ", "████"],
    "2": ["████ ", "    █", " ███ ", "█    ", "█████"], "3": ["████ ", "    █", " ███ ", "    █", "████ "],
    "4": ["█   █", "█   █", "█████", "    █", "    █"], "5": ["█████", "█    ", "████ ", "    █", "████ "],
    "6": [" ███ ", "█    ", "████ ", "█   █", " ███ "], "7": ["█████", "    █", "   █ ", "  █  ", "  █  "],
    "8": [" ███ ", "█   █", " ███ ", "█   █", " ███ "], "9": [" ███ ", "█   █", " ████", "    █", " ███ "],
    " ": ["   ", "   ", "   ", "   ", "   "], "!": ["█", "█", "█", " ", "█"], ".": [" ", " ", " ", " ", "█"],
    "?": ["████ ", "    █", "  ██ ", "     ", "  █  "], "-": ["    ", "    ", "████", "    ", "    "],
    ":": [" ", "█", " ", "█", " "], "+": ["     ", "  █  ", "█████", "  █  ", "     "],
    "=": ["    ", "████", "    ", "████", "    "], "'": ["█", "█", " ", " ", " "], ",": [" ", " ", " ", "█", "▀"],
    "/": ["    █", "   █ ", "  █  ", " █   ", "█    "], "#": [" █ █ ", "█████", " █ █ ", "█████", " █ █ "],
    "<": ["  █", " █ ", "█  ", " █ ", "  █"], ">": ["█  ", " █ ", "  █", " █ ", "█  "],
    "(": [" █", "█ ", "█ ", "█ ", " █"], ")": ["█ ", " █", " █", " █", "█ "], "_": ["     ", "     ", "     ", "     ", "█████"],
    "♥": [" █ █ ", "█████", "█████", " ███ ", "  █  "],
}
ACCENTS = {"Ä": ("A", " ▄ ▄ "), "Ö": ("O", " ▄ ▄ "), "Å": ("A", "  ▄  "), "Ü": ("U", " ▄ ▄ ")}


def banner_lines(text: str) -> list[str]:
    rows = [""] * 6
    for ch in text.upper():
        base, accent = ACCENTS.get(ch, (ch, None))
        glyph = FONT.get(base, FONT["?"])
        width = len(glyph[0])
        rows[0] += (accent or " " * 5).center(width)[:width] + " "
        for i in range(5):
            rows[i + 1] += glyph[i] + " "
    if not rows[0].strip():
        rows = rows[1:]
    return [r.rstrip() for r in rows]


def color_banner(lines: list[str], style: str) -> list[str]:
    if style == "rainbow":
        width = max(len(r) for r in lines) or 1
        out = []
        for r in lines:
            out.append("".join(ui.rgb(ch, *ui.hsv_to_rgb(i / width, 0.8, 1)) if ch != " " else " " for i, ch in enumerate(r)))
        return out
    if style == "fire":
        n = len(lines)
        return [ui.gradient(r, (255, 230 - i * 30, 40), (220, 40 + i * 10, 20)) for i, r in enumerate(lines)] if n else lines
    if style == "ice":
        return [ui.gradient(r, (200, 240, 255), (40, 120, 255)) for r in lines]
    if style == "finland":
        return [ui.c(r, "bright_blue") for r in lines]
    return lines


# --------------------------------------------------------------------------
# Talking animals
# --------------------------------------------------------------------------

ANIMALS = {
    "cow": r"""
    \        ___
     \      (o o)_______
      \      \_/        )~
              |  ____  |
              || |  || ||
              ^^ ^  ^^ ^^""",
    "cat": r"""
    \
     \   /\_/\
        ( o.o )
         > ^ <
        /     \
       (_______)~""",
    "penguin": r"""
    \
     \    _~_
         (o o)
        /  V  \
       /(  _  )\
         ^^ ^^""",
    "ghost": r"""
    \
     \   .-.
        (o o)
        | O |
        |   |
        '~~~'""",
    "robot": r"""
    \
     \   [###]
         |o o|
         | = |
        /|   |\
         d   b""",
    "owl": r"""
    \
     \   ,___,
         {o,o}
         /)__)
         -"-"-""",
}


def speech_bubble(text: str, width: int = 40) -> list[str]:
    lines = []
    for para in text.splitlines() or [""]:
        lines.extend(textwrap.wrap(para, width) or [""])
    w = max(len(line) for line in lines)
    out = [" " + "_" * (w + 2)]
    if len(lines) == 1:
        out.append(f"< {lines[0].ljust(w)} >")
    else:
        for i, line in enumerate(lines):
            left, right = ("/", "\\") if i == 0 else ("\\", "/") if i == len(lines) - 1 else ("|", "|")
            out.append(f"{left} {line.ljust(w)} {right}")
    out.append(" " + "-" * (w + 2))
    return out


# --------------------------------------------------------------------------
# Dice and draws
# --------------------------------------------------------------------------

DICE_RE = re.compile(r"^\s*(\d*)\s*[dDnN]\s*(\d+|%)\s*(?:(k[hl])\s*(\d+))?\s*([+-]\s*\d+)?\s*$")


def roll_dice(notation: str, rng: random.Random | None = None) -> tuple[int, list[int], int]:
    """Rolls dice with notation: 3d6+2, d20, 4d6kh3 (keep the 3 highest), 2d20kl1, d%."""
    m = DICE_RE.match(notation)
    if not m:
        raise ValueError("Use the form 3d6, d20+5, 4d6kh3 or d%.")
    count = int(m.group(1) or 1)
    sides = 100 if m.group(2) == "%" else int(m.group(2))
    if not 1 <= count <= 1000 or not 2 <= sides <= 10000:
        raise ValueError("1–1000 dice, 2–10000 sides.")
    rnd = rng or secrets.SystemRandom()
    rolls = [rnd.randint(1, sides) for _ in range(count)]
    kept = rolls
    if m.group(3):
        k = min(int(m.group(4)), count)
        kept = sorted(rolls, reverse=m.group(3) == "kh")[:k]
    mod = int(m.group(5).replace(" ", "")) if m.group(5) else 0
    return sum(kept) + mod, rolls, mod


# --------------------------------------------------------------------------
# Text generators
# --------------------------------------------------------------------------

EIGHT_BALL = [
    ("It is certain.", "+"), ("The stars say yes.", "+"), ("Without a doubt!", "+"), ("Yes – right away.", "+"),
    ("Outlook good.", "+"), ("Most likely.", "+"), ("I believe so.", "+"), ("Signs point to yes.", "+"),
    ("You may rely on it.", "+"), ("Of course, don't even ask.", "+"),
    ("Ask again later.", "?"), ("Better not tell you now – it would spoil the suspense.", "?"), ("Reply hazy, shake again.", "?"),
    ("Concentrate and ask again.", "?"), ("Cannot predict now.", "?"),
    ("No.", "-"), ("My sources say no.", "-"), ("Very doubtful.", "-"), ("Outlook not so good.", "-"),
    ("Forget about it.", "-"),
]

JOKES = [
    "Why don't skeletons fight each other? – They don't have the guts.",
    "What do you call a fake noodle? – An impasta.",
    "What happens when a cow jumps on a trampoline? – You get a milkshake.",
    "What did the zero say to the eight? – Nice belt!",
    "Why did the computer go to the doctor? – It had a virus.",
    "Why is the computer always cold? – It leaves its Windows open.",
    "What is a spider's favourite place online? – The web.",
    "How many programmers does it take to change a light bulb? – None, that's a hardware problem.",
    "Why do programmers mix up Halloween and Christmas? – Because Oct 31 = Dec 25.",
    "There are 10 kinds of people in the world: those who understand binary and those who don't.",
    "A programmer goes shopping. Instructions: 'Buy a carton of milk, and if they have eggs, buy six.' He came back with six cartons of milk.",
    "Two snowmen are standing in a yard. One asks: 'Can you smell carrots too?'",
    "Why did the chicken cross the road? – To get to the other side.",
    "Teacher: 'What is 2 + 2?' Student: 'Are we buying or selling?'",
    "What did the sauna say to the stove? – You're so hot.",
    "Why does a snowman never get angry? – He's always a cool guy.",
    "Why are reindeer so good at music? – They always hit the high antlers.",
    "What did the mouse say to the keyboard? – Don't click with me!",
    "Why do library books never argue? – They each have their own shelf.",
    "Why did the hockey player bring a ladder to the game? – He wanted to play in a higher league.",
    "Why did the coffee file a police report? – It got mugged.",
    "Why are the northern lights never late? – They always shine on time.",
]

COMPLIMENTS_A = ["You are", "You really are", "I'd say you are", "Honestly, you are"]
COMPLIMENTS_B = ["more brilliant than the northern lights", "lovelier than a summer cottage beach", "faster than a fibre connection",
                 "warmer than the top bench of a sauna", "smarter than an AI", "more important than coffee on a Monday",
                 "rarer than a heatwave at midsummer", "sweeter than grandma's cinnamon buns", "tougher than sisu itself",
                 "brighter than the sun on a frosty morning"]

EXCUSE_START = ["I would have been on time, but", "I didn't do my homework because", "I was late because",
                "I didn't reply to your message because", "I forgot your birthday because", "I didn't go to the gym because"]
EXCUSE_WHO = ["my cat", "the neighbour's parrot", "the WiFi router", "the bus driver", "my grandma", "an AI", "the coffee maker",
              "the snowplough", "my phone", "my little brother", "some squirrel", "the housing committee"]
EXCUSE_DID = ["hid", "ate", "formatted", "locked", "ran off with", "updated", "messed up", "sold online", "soaked"]
EXCUSE_WHAT = ["my shoes", "my homework", "my keys", "my charger", "my alarm clock", "my whole morning", "my bike", "my beanie"]
EXCUSE_END = ["and on top of that it was raining sideways.", "and nobody believed me.", "right when I was about to leave.",
              "because it was Tuesday.", "and after that I had to go to the sauna.", "and it took three hours to sort out."]

WOULD_YOU = [
    ("live forever at a cottage without internet", "live in a city without a sauna"),
    ("be able to fly", "be able to turn invisible"),
    ("eat nothing but salty liquorice for a week", "eat nothing but Brussels sprouts for a week"),
    ("always be 10 minutes late", "always be an hour too early"),
    ("speak every language", "play every instrument"),
    ("live in an eternal summer", "live in an eternal winter"),
    ("know the future", "be able to change the past"),
    ("be the world's best ice hockey player", "be the world's best game developer"),
    ("go without your phone for a month", "go without coffee for a year"),
    ("live on a space station", "live in a submarine"),
    ("remember everything you read", "remember everything you hear"),
    ("have a dragon as a pet", "have a talking cat as a pet"),
    ("be able to breathe underwater", "be able to run 100 km/h"),
    ("be famous", "be rich but unknown"),
    ("watch only one film for the rest of your life", "listen to only one song for the rest of your life"),
    ("go to the sauna every day", "go ice swimming every day"),
]

NAME_START = ["Ka", "Lu", "Ve", "Ai", "Ta", "Il", "Ro", "Sa", "Ki", "Mi", "Va", "Tu", "Ee", "Ou", "Hi", "Ja"]
NAME_MID = ["ri", "la", "no", "ve", "ku", "si", "ma", "lo", "ta", "ne", "vi", "ra"]
NAME_END = ["nen", "la", "o", "us", "ia", "rok", "ar", "eli", "in", "a", "ion", "uu"]
TAG_ADJ = ["Lightning", "Silent", "Frozen", "Swift", "Golden", "Shadow", "Wild", "Icy", "Raging", "Goofy", "Sneaky",
           "Turbo", "Mega", "Ninja", "Cosmic", "Aurora"]
TAG_NOUN = ["Wolf", "Pike", "Bear", "Lynx", "Fox", "Owl", "Reindeer", "Eagle", "Stove", "Viking", "Dragon", "Sisu",
            "Storm", "Frost", "Thunder", "Moose"]


def make_name(rng: random.Random) -> str:
    return (rng.choice(NAME_START) + "".join(rng.choice(NAME_MID) for _ in range(rng.randint(0, 2))) + rng.choice(NAME_END)).capitalize()


# --------------------------------------------------------------------------
# Animation framework
# --------------------------------------------------------------------------

def animate(render: Callable[[int, int, int], list[str]], fps: float = 15, max_frames: int | None = None) -> None:
    """Runs an animation until the user presses a key (or Ctrl+C)."""
    w, h = ui.term_width(), ui.term_height() - 2
    if not keys.interactive():
        for line in render(0, min(w, 80), min(h, 20)):
            print(line)
        return
    ui.clear()
    frame = 0
    with keys.RawMode():
        try:
            while max_frames is None or frame < max_frames:
                start = time.time()
                lines = render(frame, w, h)
                sys.stdout.write("\x1b[H" + "\n".join(lines[:h]) + "\x1b[J")
                sys.stdout.write(f"\n\x1b[2m(press any key to stop)\x1b[0m")
                sys.stdout.flush()
                frame += 1
                if keys.get_key(max(0.0, 1 / fps - (time.time() - start))) is not None:
                    break
        except KeyboardInterrupt:
            pass
    print()


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("fun", "fun-ascii-banner", "ASCII banner", "Big coloured letters in the terminal – accented letters too", ("banner", "figlet", "big text", "ascii"))
def banner_tool() -> None:
    text = ui.ask("Text", "FOLDKNIFE")
    styles = ["rainbow", "fire", "ice", "finland", "no colours"]
    style = styles[ui.choose("Style", styles, 0)]
    lines = banner_lines(text)
    print()
    for line in color_banner(lines, style):
        print("  " + line)
    print()
    offer_copy("\n".join(lines))


@tool("fun", "fun-talking-animal", "Talking animal", "A cow, cat, penguin or robot says whatever you want", ("cowsay", "cow", "sanoo"))
def cowsay_tool() -> None:
    names = list(ANIMALS)
    animal = names[ui.choose("Animal", names, 0)]
    text = ui.ask("What does it say?", "Mooo! Foldknife is the best.")
    out = speech_bubble(text) + ANIMALS[animal].splitlines()[1:]
    print(ui.c("\n".join(out), "bright_yellow"))
    offer_copy("\n".join(out))


@tool("fun", "fun-magic-8-ball", "Magic 8-ball", "Ask a yes/no question – the ball knows", ("8ball", "magic", "ennustus", "kysymys"))
def eightball_tool() -> None:
    while True:
        q = ui.ask("Your question (empty = quit)", allow_empty=True)
        if not q:
            return
        if ui.is_tty():
            with ui.Spinner("The ball is spinning"):
                time.sleep(1.2)
        answer, kind = secrets.choice(EIGHT_BALL)
        color = {"+": "bright_green", "?": "bright_yellow", "-": "bright_red"}[kind]
        ui.box([ui.c(answer, "bold", color)], title="🎱", color=color)


@tool("fun", "fun-jokes", "Jokes", "Puns and programmer jokes", ("vitsi", "joke", "huumori"))
def jokes_tool() -> None:
    pool = JOKES[:]
    random.shuffle(pool)
    for joke in pool:
        if " – " in joke:
            q, a = joke.split(" – ", 1)
            print("\n  " + ui.bold(q))
            input(ui.gray("  [Enter]…"))
            print("  " + ui.c(a, "bright_yellow"))
        else:
            print("\n  " + ui.bold(joke))
        if not ui.ask_yes_no("More?", True):
            return


@tool("fun", "fun-dice", "Dice", "RPG dice: 3d6, d20+5, 4d6kh3, d% – with visual dice", ("dice", "noppa", "d20", "roolipeli"))
def dice_tool() -> None:
    faces = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    while True:
        raw = ui.ask("Roll (e.g. 2d6, d20+3, 4d6kh3, empty = quit)", allow_empty=True)
        if not raw:
            return
        try:
            total, rolls, mod = roll_dice(raw)
        except ValueError as exc:
            ui.error(str(exc))
            continue
        sides = 100 if "%" in raw else int(DICE_RE.match(raw).group(2))  # type: ignore[union-attr]
        shown = " ".join(ui.c(faces[r], "bright_yellow") if sides == 6 else ui.c(f"[{r}]", "bright_yellow") for r in rolls[:60])
        crit = ""
        if sides == 20 and len(rolls) == 1:
            crit = ui.green(" CRITICAL HIT!") if rolls[0] == 20 else ui.red(" Critical fail!") if rolls[0] == 1 else ""
        print(f"  {shown}" + (f" {'+' if mod >= 0 else '-'} {abs(mod)}" if mod else "") + f"  = {ui.bold(str(total))}{crit}")


@tool("fun", "fun-randomiser", "Randomiser", "Draw a winner, split teams, flip a coin, lottery numbers or a random number", ("arvonta", "random", "joukkueet", "lotto", "kolikko"))
def picker_tool() -> None:
    k = ui.choose("Action", ["Pick one from a list", "Shuffle the order", "Split into teams", "Flip a coin",
                              "Random number", "Lotto line (7/40)", "Eurojackpot line (5/50 + 2/12)", "Yes or no?"])
    rnd = secrets.SystemRandom()
    if k in (0, 1, 2):
        items = [x.strip() for x in re.split(r"[,\n]", ui.get_text("Options separated by commas or one per line")) if x.strip()]
        if not items:
            ui.error("No options.")
            return
        if k == 0:
            if ui.is_tty():
                for i in range(15):
                    print(f"\r  🎲 {rnd.choice(items)[:40].ljust(40)}", end="", flush=True)
                    time.sleep(0.04 + i * 0.012)
                print("\r" + " " * 50 + "\r", end="")
            ui.box([ui.c(rnd.choice(items), "bold", "bright_green")], title="Winner")
        elif k == 1:
            rnd.shuffle(items)
            for i, x in enumerate(items, 1):
                print(f"  {i}. {x}")
        else:
            n = ui.ask_int("How many teams", 2, 2, max(2, len(items)))
            rnd.shuffle(items)
            for t in range(n):
                print(ui.c(f"\nTeam {t + 1}", "bold", ["bright_red", "bright_blue", "bright_green", "bright_yellow", "bright_magenta"][t % 5]))
                for x in items[t::n]:
                    print("  • " + x)
    elif k == 3:
        res = rnd.choice(["HEADS", "TAILS"])
        ui.box([ui.c(res, "bold", "bright_yellow")], title="🪙")
    elif k == 4:
        a, b = ui.ask_int("From", 1), ui.ask_int("To", 100)
        print(ui.bold(f"  {rnd.randint(min(a, b), max(a, b))}"))
    elif k == 5:
        print(ui.bold("  " + "  ".join(str(n) for n in sorted(rnd.sample(range(1, 41), 7)))))
        print(ui.gray("  (just a random line – it doesn't improve your odds)"))
    elif k == 6:
        main = sorted(rnd.sample(range(1, 51), 5))
        stars = sorted(rnd.sample(range(1, 13), 2))
        print(ui.bold("  " + "  ".join(map(str, main))) + ui.yellow("   ★ " + "  ".join(map(str, stars))))
    else:
        ui.box([ui.c(rnd.choice(["YES", "NO"]), "bold", "bright_cyan")])


@tool("fun", "fun-matrix-rain", "Matrix rain", "Green code rain like in the film", ("matrix", "animaatio", "koodi", "sade"))
def matrix_tool() -> None:
    chars = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉ0123456789ABCDEFZ:.=*+-<>"
    state: dict[str, list[float]] = {}

    def render(frame: int, w: int, h: int) -> list[str]:
        cols = w // 2
        drops = state.setdefault("drops", [random.uniform(-h, 0) for _ in range(cols)])
        speeds = state.setdefault("speeds", [random.uniform(0.3, 1.0) for _ in range(cols)])
        if len(drops) < cols:
            drops.extend(random.uniform(-h, 0) for _ in range(cols - len(drops)))
            speeds.extend(random.uniform(0.3, 1.0) for _ in range(cols - len(speeds)))
        grid = [["  "] * cols for _ in range(h)]
        for c in range(cols):
            head = int(drops[c])
            for t in range(18):
                y = head - t
                if 0 <= y < h:
                    ch = random.choice(chars) if t == 0 or random.random() < 0.1 else chars[(y * 7 + c * 13 + frame // 3) % len(chars)]
                    if t == 0:
                        grid[y][c] = ui.rgb(ch, 220, 255, 220) + " "
                    else:
                        g = max(40, 255 - t * 13)
                        grid[y][c] = ui.rgb(ch, 0, g, 60) + " "
            drops[c] += speeds[c]
            if head - 18 > h:
                drops[c] = random.uniform(-10, 0)
                speeds[c] = random.uniform(0.3, 1.0)
        return ["".join(row) for row in grid]

    animate(render, fps=20)


def life_step(cells: set[tuple[int, int]], w: int, h: int, wrap: bool = True) -> set[tuple[int, int]]:
    counts: dict[tuple[int, int], int] = {}
    for x, y in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    nx, ny = x + dx, y + dy
                    if wrap:
                        nx, ny = nx % w, ny % h
                    elif not (0 <= nx < w and 0 <= ny < h):
                        continue
                    counts[(nx, ny)] = counts.get((nx, ny), 0) + 1
    return {p for p, n in counts.items() if n == 3 or (n == 2 and p in cells)}


LIFE_PATTERNS = {
    "Glider": [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)],
    "R-pentomino": [(1, 0), (2, 0), (0, 1), (1, 1), (1, 2)],
    "Gosper glider gun": [(24, 0), (22, 1), (24, 1), (12, 2), (13, 2), (20, 2), (21, 2), (34, 2), (35, 2), (11, 3), (15, 3),
                       (20, 3), (21, 3), (34, 3), (35, 3), (0, 4), (1, 4), (10, 4), (16, 4), (20, 4), (21, 4), (0, 5), (1, 5),
                       (10, 5), (14, 5), (16, 5), (17, 5), (22, 5), (24, 5), (10, 6), (16, 6), (24, 6), (11, 7), (15, 7), (12, 8), (13, 8)],
    "Pulsar": [(x, y) for x in (2, 3, 4, 8, 9, 10) for y in (0, 5, 7, 12)] + [(x, y) for y in (2, 3, 4, 8, 9, 10) for x in (0, 5, 7, 12)],
}


@tool("fun", "fun-game-of-life", "Game of Life", "Conway's cellular automaton: random start or classic patterns", ("conway", "life", "solut", "automaatti"))
def life_tool() -> None:
    names = ["Random"] + list(LIFE_PATTERNS)
    choice = ui.choose("Starting state", names, 0)
    state: dict[str, object] = {}

    def render(frame: int, w: int, h: int) -> list[str]:
        gw, gh = w, h * 2
        if "cells" not in state:
            if choice == 0:
                state["cells"] = {(x, y) for x in range(gw) for y in range(gh) if random.random() < 0.25}
            else:
                pat = LIFE_PATTERNS[names[choice]]
                ox, oy = gw // 2 - 18 if choice == 3 else gw // 2 - 6, gh // 2 - 6
                state["cells"] = {(x + ox, y + oy) for x, y in pat}
        cells = state["cells"]  # type: ignore[assignment]
        lines = []
        for row in range(h):
            out = []
            for x in range(gw):
                top, bottom = (x, row * 2) in cells, (x, row * 2 + 1) in cells  # type: ignore[operator]
                out.append("█" if top and bottom else "▀" if top else "▄" if bottom else " ")
            lines.append(ui.c("".join(out), "bright_green"))
        state["cells"] = life_step(cells, gw, gh)  # type: ignore[arg-type]
        return lines

    animate(render, fps=12)


def mandelbrot_frame(cx: float, cy: float, scale: float, w: int, h: int, max_iter: int = 80) -> list[str]:
    lines = []
    for row in range(h):
        out = []
        y0 = cy + (row - h / 2) * scale * 2
        for col in range(w):
            x0 = cx + (col - w / 2) * scale
            x = y = 0.0
            i = 0
            while x * x + y * y <= 4 and i < max_iter:
                x, y = x * x - y * y + x0, 2 * x * y + y0
                i += 1
            if i == max_iter:
                out.append(" ")
            else:
                t = i / max_iter
                r, g, b = ui.hsv_to_rgb(0.66 + t * 3, 0.85, min(1.0, t * 4))
                out.append(ui.rgb("█", r, g, b) if ui.color_enabled() else " .:-=+*#%@"[min(9, int(t * 10))])
        lines.append("".join(out))
    return lines


@tool("fun", "fun-mandelbrot-fractal", "Mandelbrot fractal", "Explore the fractal: arrows move, + and - zoom", ("fraktaali", "mandelbrot", "matematiikka"))
def mandelbrot_tool() -> None:
    cx, cy, scale = -0.6, 0.0, 3.0 / max(40, ui.term_width())
    if not keys.interactive():
        for line in mandelbrot_frame(cx, cy, 3.0 / 80, 80, 24):
            print(line)
        return
    ui.clear()
    with keys.RawMode():
        while True:
            w, h = ui.term_width(), ui.term_height() - 2
            lines = mandelbrot_frame(cx, cy, scale, w, h, max_iter=min(400, int(80 + math.log10(3 / w / scale + 1) * 60)))
            sys.stdout.write("\x1b[H" + "\n".join(lines) + f"\n\x1b[2marrows = move · + / - = zoom · q = quit · centre {cx:.6f} {cy:+.6f}i\x1b[0m\x1b[J")
            sys.stdout.flush()
            k = keys.get_key(3600)
            d = keys.direction(k)
            if k in ("q", "ESC", None):
                break
            if d == "LEFT":
                cx -= scale * w / 6
            elif d == "RIGHT":
                cx += scale * w / 6
            elif d == "UP":
                cy -= scale * h / 3
            elif d == "DOWN":
                cy += scale * h / 3
            elif k in ("+", "="):
                scale /= 1.8
            elif k in ("-", "_"):
                scale *= 1.8
    print()


def donut_frame(a: float, b: float, w: int = 80, h: int = 24) -> list[str]:
    """Spinning torus: own implementation with lighting and a depth buffer."""
    out = [" "] * (w * h)
    zbuf = [0.0] * (w * h)
    shades = ".,-~:;=!*#$@"
    ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
    k1 = min(w, h * 2) * 0.35
    theta = 0.0
    while theta < 2 * math.pi:
        ct, st = math.cos(theta), math.sin(theta)
        phi = 0.0
        while phi < 2 * math.pi:
            cp, sp = math.cos(phi), math.sin(phi)
            cx = 2 + ct  # R2 + R1 cos θ
            x = cx * (cb * cp + sa * sb * sp) - st * ca * sb
            y = cx * (sb * cp - sa * cb * sp) + st * ca * cb
            z = 5 + ca * cx * sp + st * sa
            ooz = 1 / z
            xp = int(w / 2 + k1 * ooz * x * 2)
            yp = int(h / 2 - k1 * ooz * y)
            lum = cp * ct * sb - ca * ct * sp - sa * st + cb * (ca * st - ct * sa * sp)
            if 0 <= xp < w and 0 <= yp < h and lum > 0:
                idx = xp + yp * w
                if ooz > zbuf[idx]:
                    zbuf[idx] = ooz
                    out[idx] = shades[min(11, int(lum * 8))]
            phi += 0.02
        theta += 0.07
    return ["".join(out[r * w:(r + 1) * w]) for r in range(h)]


@tool("fun", "fun-spinning-donut", "Spinning donut", "A 3D torus in ASCII – the classic demo effect", ("donut", "3d", "animaatio", "demo"))
def donut_tool() -> None:
    def render(frame: int, w: int, h: int) -> list[str]:
        lines = donut_frame(frame * 0.07, frame * 0.03, min(w, 100), min(h, 40))
        return [ui.c(line, "bright_yellow") for line in lines]

    animate(render, fps=20)


FIRE_PALETTE = [(7, 7, 7), (31, 7, 7), (47, 15, 7), (71, 15, 7), (87, 23, 7), (103, 31, 7), (119, 31, 7), (143, 39, 7),
                (159, 47, 7), (175, 63, 7), (191, 71, 7), (199, 71, 7), (223, 79, 7), (223, 87, 7), (223, 87, 7),
                (215, 95, 7), (215, 103, 15), (207, 111, 15), (207, 119, 15), (207, 127, 15), (207, 135, 23),
                (199, 135, 23), (199, 143, 23), (199, 151, 31), (191, 159, 31), (191, 159, 31), (191, 167, 39),
                (191, 167, 39), (191, 175, 47), (183, 175, 47), (183, 183, 47), (183, 183, 55), (207, 207, 111),
                (223, 223, 159), (239, 239, 199), (255, 255, 255)]


@tool("fun", "fun-campfire", "Campfire", "A warm fire effect in the terminal (needs colours)", ("fire", "fire", "nuotio", "animaatio"))
def fire_tool() -> None:
    state: dict[str, list[int]] = {}

    def render(frame: int, w: int, h: int) -> list[str]:
        fh = h * 2
        px = state.setdefault("px", [0] * (w * fh))
        if len(px) != w * fh:
            px[:] = [0] * (w * fh)
        top = len(FIRE_PALETTE) - 1
        for x in range(w):
            px[(fh - 1) * w + x] = top
        for y in range(1, fh):
            for x in range(w):
                src = y * w + x
                decay = random.randint(0, 2)
                dst = src - w - decay + 1
                if 0 <= dst < len(px):
                    px[dst] = max(0, px[src] - (decay & 1))
        lines = []
        for row in range(h):
            out = []
            for x in range(w):
                a = FIRE_PALETTE[px[row * 2 * w + x]]
                b = FIRE_PALETTE[px[(row * 2 + 1) * w + x]]
                out.append(f"\x1b[38;2;{a[0]};{a[1]};{a[2]};48;2;{b[0]};{b[1]};{b[2]}m▀")
            lines.append("".join(out) + "\x1b[0m")
        return lines

    if not ui.color_enabled():
        ui.warn("The fire needs colours.")
        return
    animate(render, fps=24)


@tool("fun", "fun-big-clock", "Big clock", "Full-screen digital clock", ("clock", "kello", "aika"))
def clock_tool() -> None:
    def render(frame: int, w: int, h: int) -> list[str]:
        now = dt.datetime.now()
        lines = banner_lines(now.strftime("%H:%M:%S"))
        colored = [ui.gradient(line, (80, 200, 255), (200, 120, 255)) for line in lines]
        from ..core.utils import FI_WEEKDAYS

        date = f"{FI_WEEKDAYS[now.weekday()]} {now.day}.{now.month}.{now.year}"
        pad_top = max(0, (h - 8) // 2)
        width = max(len(line) for line in lines)
        left = " " * max(0, (w - width) // 2)
        return [""] * pad_top + [left + c for c in colored] + ["", " " * max(0, (w - len(date)) // 2) + ui.bold(date)]

    animate(render, fps=4)


@tool("fun", "fun-name-generator", "Name generator", "Fantasy names, gamer tags and band names", ("nimi", "gamertag", "nickname", "band"))
def names_tool() -> None:
    rng = random.Random()
    k = ui.choose("Type", ["Fantasy names", "Gamer tags", "Band names"])
    for _ in range(10):
        if k == 0:
            print("  " + make_name(rng) + " " + ui.gray("the " + rng.choice(["guardian", "singer", "smith", "witch", "knight", "wanderer"]) +
                                                    " " + rng.choice(["of the North", "of the Cliffs", "of the Storm", "of the Fells", "of the Lakeshore", "of the Moon"])))
        elif k == 1:
            print("  " + rng.choice(TAG_ADJ) + rng.choice(TAG_NOUN) + str(rng.choice(["", rng.randint(1, 99), rng.randint(1990, 2026)])))
        else:
            adj = rng.choice(["The Grumpy", "The Raging", "The Silent", "The Electric", "The Rusty", "The Cosmic", "The Sleepless", "The Frozen"])
            noun = rng.choice(["Sauna Stoves", "Pikes", "Snowmen", "Robots", "Northern Lights", "Cottagers", "Cinnamon Buns", "Hedgehogs"])
            print("  " + ui.bold(f"{adj} {noun}"))


@tool("fun", "fun-excuse-generator", "Excuse generator", "For when you need a creative explanation (don't use it for real 😉)", ("tekosyy", "excuse", "selitys"))
def excuse_tool() -> None:
    rng = random.Random()
    while True:
        text = (f"{rng.choice(EXCUSE_START)} {rng.choice(EXCUSE_WHO)} {rng.choice(EXCUSE_DID)} "
                f"{rng.choice(EXCUSE_WHAT)} {rng.choice(EXCUSE_END)}")
        ui.box([text], color="bright_magenta")
        if not ui.ask_yes_no("Another?", True):
            offer_copy(text)
            return


@tool("fun", "fun-compliment-generator", "Compliment generator", "Brighten the day – for yourself or a friend", ("kehu", "compliment", "piristys"))
def compliment_tool() -> None:
    name = ui.ask("For whom? (empty = you)", allow_empty=True)
    text = f"{(name + ', ') if name else ''}{random.choice(COMPLIMENTS_A).lower() if name else random.choice(COMPLIMENTS_A)} {random.choice(COMPLIMENTS_B)}! ✨"
    ui.box([ui.c(text, "bold", "bright_yellow")])
    offer_copy(text)


@tool("fun", "fun-would-you-rather", "Would you rather?", "Tough choices to ponder with friends", ("would you rather", "kumpi", "valinta", "seurapeli"))
def would_you_tool() -> None:
    pool = WOULD_YOU[:]
    random.shuffle(pool)
    for a, b in pool:
        print(ui.c("\nWould you rather…", "bold"))
        print(f"  {ui.c('A', 'bright_cyan')}) {a}")
        print(f"  {ui.c('B', 'bright_magenta')}) {b}")
        if not ui.ask_yes_no("Next?", True):
            return


FLAGS = {
    "Finland": ((255, 255, 255), (0, 47, 108)), "Sweden": ((0, 106, 167), (254, 204, 0)),
    "Norway": ((186, 12, 47), (0, 32, 91)), "Denmark": ((198, 12, 48), (255, 255, 255)),
    "Iceland": ((2, 82, 156), (220, 30, 53)), "Åland": ((0, 82, 147), (211, 45, 39)),
}


def nordic_flag(name: str, unit: int = 2) -> list[str]:
    bg, cross = FLAGS[name]
    outline = {"Norway": (255, 255, 255), "Iceland": (255, 255, 255), "Åland": (255, 205, 0)}.get(name)
    cols, rows = [5, 3, 10], [4, 3, 4]
    w, h = sum(cols), sum(rows)
    lines = []
    for y in range(h):
        line = []
        for x in range(w):
            in_cross = cols[0] <= x < cols[0] + cols[1] or rows[0] <= y < rows[0] + rows[1]
            inner = (cols[0] + 1 <= x < cols[0] + cols[1] - 1) or (rows[0] + 1 <= y < rows[0] + rows[1] - 1)
            if outline and in_cross and not inner:
                color = outline
            elif in_cross:
                color = cross
            else:
                color = bg
            line.append(ui.bg_rgb(" " * unit, *color))
        lines.append("".join(line))
    return lines


@tool("fun", "fun-nordic-flags", "Nordic flags", "The flags of Finland, Sweden, Norway, Denmark, Iceland and Åland in colour", ("lippu", "finland", "flag"))
def flags_tool() -> None:
    if not ui.color_enabled():
        ui.warn("Flags need colours.")
        return
    for name in FLAGS:
        print(ui.bold(f"\n  {name}"))
        for line in nordic_flag(name):
            print("  " + line)


ART = {
    "Coffee cup": r"""
      ( (
       ) )
    ........
    |      |]
    \      /
     `----'""",
    "Cottage and sauna": r"""
           (  )
            ) (
       ____|  |____
      /            \
     /   COTTAGE    \
    |  []  ____  []  |
    |     |    |     |
    |_____|____|_____|""",
    "Spruce": r"""
         *
        /.\
       /..'\
       /'.'\
      /.''.'\
      /.'.'.\
     /'.''.'.\
     ^^^[_]^^^""",
    "Heart": r"""
      ****   ****
    ****** ******
    *************
     ***********
       *******
         ***
          *""",
    "Sun": r"""
        \  |  /
      '. \ | / .'
     --- (   ) ---
      .' / | \ '.
        /  |  \ """,
    "Owl": r"""
       ,___,
       (O,O)
       /)__)
      --"-"--""",
}


@tool("fun", "fun-ascii-art-gallery", "ASCII art gallery", "Small ASCII drawings to copy into messages", ("ascii", "taide", "piirros"))
def gallery_tool() -> None:
    names = list(ART)
    for i, n in enumerate(names):
        print(ui.c(f"\n{i + 1}. {n}", "bold", "bright_yellow"))
        print(ui.c(ART[n].strip("\n"), ["bright_cyan", "bright_yellow", "bright_green", "bright_red", "bright_yellow", "bright_white"][i % 6]))
    idx = ui.ask_int("Number to copy (0 = none)", 0, 0, len(names))
    if idx:
        offer_copy(ART[names[idx - 1]].strip("\n"))


@tool("fun", "fun-rainbow-text", "Rainbow text", "Colour text as a rainbow or a gradient in the terminal", ("rainbow", "colour", "gradient"))
def rainbow_tool() -> None:
    text = ui.ask("Text", "Good day, Foldknife user!")
    print("  " + ui.rainbow(text))
    print("  " + ui.gradient(text, (255, 80, 80), (80, 120, 255)))
    print("  " + ui.gradient(text, (255, 220, 0), (255, 0, 140)))
    if ui.is_tty() and ui.ask_yes_no("Animate?", True):
        try:
            for i in range(60):
                print("\r  " + ui.rainbow(text, i / 30), end="", flush=True)
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        print()
