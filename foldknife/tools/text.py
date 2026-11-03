"""Text tools: counters, conversions, cleanup, extraction, Unicode styles and Morse."""
from __future__ import annotations

import difflib
import html
import random
import re
import string
import textwrap
import unicodedata
from collections import Counter
from html.parser import HTMLParser

from ..core import ui
from ..core.registry import tool
from ..core.utils import offer_copy, offer_save

# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------

STOPWORDS = set("""
ja on ei se että oli kun mutta niin myös tai sen jos kuin ole ovat joka jotka hän me te he minä sinä
mitä nyt vain voi siitä sitä tämä tässä ne jo vielä kaikki sitten olla olen olet mikä kanssa sekä koska
ollut olisi ovat sekä eli siis mutta vaan jotta kuitenkin sillä niitä niiden heidän meidän teidän
minun sinun hänen tuo tuon nämä noita joku jokin mitään mikään missä mistä mihin kuka ketä kenen
the a an and or of to in is it that for on with as was be are this i you he she we they at by from not
but have has had were been their there them his her its our your my me will would can could do does
did so if about into than then also just more some no yes all any what which who when where how
""".split())

WORD_RE = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", re.UNICODE)


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def text_stats(text: str) -> dict[str, float]:
    ws = words(text)
    sentences = [s for s in re.split(r"[.!?…]+(?:\s|$)", text) if s.strip()]
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    letters = sum(ch.isalpha() for ch in text)
    long_words = sum(1 for w in ws if len(w) > 6)
    nw, ns = len(ws), max(1, len(sentences))
    return {
        "merkit": len(text),
        "chars_without_spaces": sum(not ch.isspace() for ch in text),
        "kirjaimet": letters,
        "numerot": sum(ch.isdigit() for ch in text),
        "sanat": nw,
        "uniikit_sanat": len({w.lower() for w in ws}),
        "lauseet": len(sentences),
        "kappaleet": len(paragraphs),
        "rivit": text.count("\n") + 1 if text else 0,
        "sanan_keskipituus": (sum(len(w) for w in ws) / nw) if nw else 0,
        "lauseen_keskipituus": nw / ns,
        "long_words": long_words,
        "lix": (nw / ns + 100 * long_words / nw) if nw else 0,
        "lukuaika_s": nw / 200 * 60,
        "puheaika_s": nw / 130 * 60,
    }


def lix_label(lix: float) -> str:
    if lix < 25:
        return "very easy (children's books)"
    if lix < 35:
        return "easy (fiction)"
    if lix < 45:
        return "medium (newspaper)"
    if lix < 55:
        return "hard (non-fiction)"
    return "very hard (bureaucracy, research)"


def top_words(text: str, n: int = 15, skip_stop: bool = True, min_len: int = 2) -> list[tuple[str, int]]:
    counter = Counter(w.lower() for w in words(text) if len(w) >= min_len and
                      (not skip_stop or w.lower() not in STOPWORDS))
    return counter.most_common(n)


# --------------------------------------------------------------------------
# Conversions
# --------------------------------------------------------------------------

def split_words(text: str) -> list[str]:
    """Splits into words also at camelCase and snake_case boundaries."""
    text = re.sub(r"([a-zäöå0-9])([A-ZÄÖÅ])", r"\1 \2", text)
    text = re.sub(r"([A-ZÄÖÅ]+)([A-ZÄÖÅ][a-zäöå])", r"\1 \2", text)
    return [w for w in re.split(r"[\s_\-./\\]+", text) if w]


CASE_MODES = {
    "upper": "UPPER CASE",
    "lower": "lower case",
    "title": "Title Case",
    "sentence": "Sentence case. Capital letters at sentence starts.",
    "camel": "camelCase",
    "pascal": "PascalCase",
    "snake": "snake_case",
    "kebab": "kebab-case",
    "constant": "CONSTANT_CASE",
    "dot": "dot.case",
    "alternating": "aLtErNaTiNg",
    "inverse": "iNVERTED cASE",
}


def convert_case(text: str, mode: str) -> str:
    if mode == "upper":
        return text.upper()
    if mode == "lower":
        return text.lower()
    if mode == "title":
        return " ".join(w[:1].upper() + w[1:].lower() for w in text.split(" "))
    if mode == "sentence":
        out = text.lower()
        return re.sub(r"(^\s*|[.!?]\s+)([^\W\d_])", lambda m: m.group(1) + m.group(2).upper(), out)
    if mode == "alternating":
        res, up = [], False
        for ch in text:
            if ch.isalpha():
                res.append(ch.upper() if up else ch.lower())
                up = not up
            else:
                res.append(ch)
        return "".join(res)
    if mode == "inverse":
        return text.swapcase()
    parts = split_words(text)
    if mode == "camel":
        return (parts[0].lower() + "".join(p[:1].upper() + p[1:].lower() for p in parts[1:])) if parts else ""
    if mode == "pascal":
        return "".join(p[:1].upper() + p[1:].lower() for p in parts)
    if mode == "snake":
        return "_".join(p.lower() for p in parts)
    if mode == "kebab":
        return "-".join(p.lower() for p in parts)
    if mode == "constant":
        return "_".join(p.upper() for p in parts)
    if mode == "dot":
        return ".".join(p.lower() for p in parts)
    raise ValueError(f"Unknown style: {mode}")


_FI_TRANSLIT = str.maketrans({"ä": "a", "ö": "o", "å": "a", "Ä": "A", "Ö": "O", "Å": "A",
                              "ß": "ss", "æ": "ae", "ø": "o", "œ": "oe"})


def slugify(text: str, sep: str = "-") -> str:
    text = text.translate(_FI_TRANSLIT)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", sep, text).strip(sep).lower()
    return re.sub(re.escape(sep) + "{2,}", sep, text)


def reverse_text(text: str, mode: str = "chars") -> str:
    if mode == "words":
        return "\n".join(" ".join(reversed(line.split(" "))) for line in text.split("\n"))
    if mode == "lines":
        return "\n".join(reversed(text.split("\n")))
    if mode == "each_word":
        return " ".join(w[::-1] for w in text.split(" "))
    return text[::-1]


def line_ops(text: str, op: str) -> str:
    lines = text.split("\n")
    if op == "sort":
        lines.sort(key=lambda s: s.lower())
    elif op == "sort_desc":
        lines.sort(key=lambda s: s.lower(), reverse=True)
    elif op == "sort_num":
        def key(s: str) -> tuple[int, float, str]:
            m = re.search(r"-?\d+(?:[.,]\d+)?", s)
            return (0, float(m.group().replace(",", ".")), s) if m else (1, 0.0, s)
        lines.sort(key=key)
    elif op == "sort_len":
        lines.sort(key=len)
    elif op == "unique":
        seen, out = set(), []
        for line in lines:
            if line not in seen:
                seen.add(line)
                out.append(line)
        lines = out
    elif op == "unique_ci":
        seen, out = set(), []
        for line in lines:
            k = line.strip().lower()
            if k not in seen:
                seen.add(k)
                out.append(line)
        lines = out
    elif op == "shuffle":
        random.shuffle(lines)
    elif op == "number":
        w = len(str(len(lines)))
        lines = [f"{str(i).rjust(w)}. {line}" for i, line in enumerate(lines, 1)]
    elif op == "unnumber":
        lines = [re.sub(r"^\s*\d+[.)]\s?", "", line) for line in lines]
    elif op == "strip_empty":
        lines = [line for line in lines if line.strip()]
    elif op == "trim":
        lines = [line.strip() for line in lines]
    elif op == "dupes_only":
        counts = Counter(lines)
        lines = [line for line, c in counts.items() if c > 1]
    elif op == "join":
        return ", ".join(line.strip() for line in lines if line.strip())
    else:
        raise ValueError(op)
    return "\n".join(lines)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def strip_html(text: str) -> str:
    parser = _TextExtractor()
    parser.feed(text)
    out = "".join(parser.parts)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def clean_text(text: str, smart_quotes: bool = True, collapse_spaces: bool = True,
               strip_lines: bool = True, max_blank: int = 1, remove_zero_width: bool = True) -> str:
    if remove_zero_width:
        text = re.sub("[​‌‍⁠﻿]", "", text)
    if smart_quotes:
        text = (text.replace("“", '"').replace("”", '"').replace("„", '"').replace("’", "'")
                .replace("‘", "'").replace("–", "-").replace("—", "-").replace("…", "...").replace(" ", " "))
    if collapse_spaces:
        text = re.sub(r"[ \t]{2,}", " ", text)
    if strip_lines:
        text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{" + str(max_blank + 2) + ",}", "\n" * (max_blank + 1), text)
    return text.strip()


EXTRACTORS = {
    "email": ("Email addresses", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    "url": ("Links", re.compile(r"https?://[^\s<>\"')\]]+")),
    "phone": ("Phone numbers", re.compile(r"(?:\+358|0)[\s-]?\d{1,3}[\s-]?\d{3}[\s-]?\d{2,4}")),
    "number": ("Numbers", re.compile(r"-?\d+(?:[.,]\d+)?")),
    "hashtag": ("Hashtags", re.compile(r"#[\wäöåÄÖÅ]+")),
    "mention": ("Mentions (@)", re.compile(r"(?<![\w@])@[\w.]+")),
    "ip": ("IP addresses", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    "date": ("Dates", re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")),
    "emoji": ("Emojis", re.compile("[\U0001F300-\U0001FAFF☀-➿]")),
}


def extract(text: str, kind: str, unique: bool = True) -> list[str]:
    found = EXTRACTORS[kind][1].findall(text)
    if unique:
        seen: dict[str, None] = {}
        for f in found:
            seen.setdefault(f, None)
        return list(seen)
    return found


def fix_mojibake(text: str) -> str:
    """Fixes wrongly decoded characters (e.g. 'Ã¤' → 'ä', 'â€™' → '’')."""
    markers = ("Ã", "Â", "â€", "Ã¶", "Ã¤")
    for _ in range(3):
        if not any(m in text for m in markers):
            break
        fixed = None
        for enc in ("cp1252", "latin-1"):
            try:
                fixed = text.encode(enc).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        if fixed is None or fixed == text:
            break
        text = fixed
    return text


def is_palindrome(text: str) -> bool:
    cleaned = [ch.lower() for ch in text if ch.isalnum()]
    return bool(cleaned) and cleaned == cleaned[::-1]


def is_anagram(a: str, b: str) -> bool:
    norm = lambda s: sorted(ch.lower() for ch in s if ch.isalnum())  # noqa: E731
    return norm(a) == norm(b) and bool(norm(a))


# --------------------------------------------------------------------------
# Unicode styles
# --------------------------------------------------------------------------

def _math_map(upper: int, lower: int | None, digits: int | None = None,
              exceptions: dict[str, str] | None = None) -> dict[str, str]:
    m = {chr(65 + i): chr(upper + i) for i in range(26)}
    if lower is not None:
        m.update({chr(97 + i): chr(lower + i) for i in range(26)})
    if digits is not None:
        m.update({chr(48 + i): chr(digits + i) for i in range(10)})
    m.update(exceptions or {})
    return m


FANCY: dict[str, dict[str, str]] = {
    "bold": _math_map(0x1D400, 0x1D41A, 0x1D7CE),
    "italic": _math_map(0x1D434, 0x1D44E, None, {"h": "ℎ"}),
    "bold italic": _math_map(0x1D468, 0x1D482),
    "script": _math_map(0x1D49C, 0x1D4B6, None, {
        "B": "ℬ", "E": "ℰ", "F": "ℱ", "H": "ℋ", "I": "ℐ", "L": "ℒ", "M": "ℳ", "R": "ℛ",
        "e": "ℯ", "g": "ℊ", "o": "ℴ"}),
    "bold script": _math_map(0x1D4D0, 0x1D4EA),
    "fraktur": _math_map(0x1D504, 0x1D51E, None, {"C": "ℭ", "H": "ℌ", "I": "ℑ", "R": "ℜ", "Z": "ℨ"}),
    "double-struck": _math_map(0x1D538, 0x1D552, 0x1D7D8, {
        "C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ"}),
    "sans bold": _math_map(0x1D5D4, 0x1D5EE, 0x1D7EC),
    "sans italic": _math_map(0x1D608, 0x1D622),
    "monospace": _math_map(0x1D670, 0x1D68A, 0x1D7F6),
    "wide (vaporwave)": {**_math_map(0xFF21, 0xFF41, 0xFF10), " ": "　", "!": "！", "?": "？", ".": "．"},
    "circles": {**_math_map(0x24B6, 0x24D0), **{str(i): chr(0x2460 + i - 1) for i in range(1, 10)}, "0": "⓪"},
    "black circles": _math_map(0x1F150, None),
    "squares": _math_map(0x1F130, None),
    "small caps": dict(zip("abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ")),
    "superscript": {**dict(zip("abcdefghijklmnopqrstuvwxyz", "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᑫʳˢᵗᵘᵛʷˣʸᶻ")),
                   **dict(zip("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾"))},
}

_FLIP = dict(zip(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,'\"?!()[]{}<>_&;",
    "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz∀ᗺƆᗡƎℲ⅁HIſʞ˥WNOԀΌᴚS⊥∩ΛMX⅄ZƖᄅƐㄣϛ9ㄥ860˙',„¿¡)(][}{><‾⅋؛",
))


def fancy(text: str, style: str) -> str:
    table = FANCY[style]
    upper_only = style in ("black circles", "squares")
    lower_only = style in ("kapiteelit", "superscript")
    out = []
    for ch in unicodedata.normalize("NFD", text):
        key = ch.upper() if upper_only else ch.lower() if lower_only and ch not in table else ch
        out.append(table.get(key, ch))
    return "".join(out)


def upside_down(text: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFD", text):
        if ch == "̈":
            out.append("̤")  # dots up → down
        else:
            out.append(_FLIP.get(ch, ch))
    # reverse the order so combining marks stay after their letter
    clusters: list[str] = []
    for ch in out:
        if unicodedata.combining(ch) and clusters:
            clusters[-1] += ch
        else:
            clusters.append(ch)
    return "".join(reversed(clusters))


def decorate(text: str, mark: str) -> str:
    return "".join(ch + mark if not ch.isspace() else ch for ch in text)


def zalgo(text: str, intensity: int = 3, seed: int | None = None) -> str:
    rng = random.Random(seed)
    marks = [chr(c) for c in range(0x300, 0x370)]
    return "".join(ch + "".join(rng.choice(marks) for _ in range(rng.randint(1, intensity)))
                   if not ch.isspace() else ch for ch in text)


def regional(text: str) -> str:
    out = []
    for ch in text.lower():
        if "a" <= ch <= "z":
            out.append(chr(0x1F1E6 + ord(ch) - 97))
        elif ch == " ":
            out.append("   ")
        else:
            out.append(ch)
    return " ".join(out)


def all_styles(text: str) -> list[tuple[str, str]]:
    rows = [(name, fancy(text, name)) for name in FANCY]
    rows += [("upside down", upside_down(text)), ("strikethrough", decorate(text, "̶")),
             ("underlined", decorate(text, "̲")), ("zalgo", zalgo(text, 2, seed=1)),
             ("discord letters", regional(text))]
    return rows


# --------------------------------------------------------------------------
# Morse
# --------------------------------------------------------------------------

MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....",
    "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.",
    "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "Å": ".--.-", "Ä": ".-.-", "Ö": "---.", "Ü": "..--",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
    "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--", "/": "-..-.",
    "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...", ";": "-.-.-.", "=": "-...-",
    "+": ".-.-.", "-": "-....-", "_": "..--.-", '"': ".-..-.", "$": "...-..-", "@": ".--.-.",
}
MORSE_REV = {v: k for k, v in MORSE.items()}


def morse_encode(text: str) -> str:
    out = []
    for word in text.upper().split():
        out.append(" ".join(MORSE[ch] for ch in word if ch in MORSE))
    return " / ".join(out)


def morse_decode(code: str) -> str:
    code = code.replace("_", "-").replace("·", ".").replace("−", "-").replace("—", "-")
    words_ = re.split(r"\s*/\s*|\s{3,}", code.strip())
    return " ".join("".join(MORSE_REV.get(sym, "�") for sym in w.split()) for w in words_ if w)


# --------------------------------------------------------------------------
# Lorem and nonsense
# --------------------------------------------------------------------------

LOREM_WORDS = """lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut
labore et dolore magna aliqua enim ad minim veniam quis nostrud exercitation ullamco laboris nisi aliquip
ex ea commodo consequat duis aute irure in reprehenderit voluptate velit esse cillum fugiat nulla pariatur
excepteur sint occaecat cupidatat non proident sunt culpa qui officia deserunt mollit anim id est laborum
""".split()

FI_SUBJECTS = ["The cat", "Grandma", "A reindeer", "The sauna elf", "The teacher", "A moose", "Neighbour Pete", "A little squirrel",
               "The robot", "The coffee maker", "The bus driver", "A bunny", "The snowman", "A pirate", "The programmer", "A bear"]
FI_VERBS = ["ate", "threw", "painted", "sang to", "forgot", "invented", "built", "fixed", "lost",
            "found", "hid", "sold", "bought", "hugged", "borrowed", "danced with"]
FI_OBJECTS = ["a cinnamon bun", "the socks", "the cottage", "a computer", "a snowmobile", "a coffee cup", "a guitar",
              "a snow shovel", "a pizza", "a book", "a bicycle", "a sausage", "the skis", "a fishing rod"]
FI_PLACES = ["behind the sauna", "at the shopping mall", "by the lake", "in Lapland", "in the middle of the night",
             "at the bus stop", "on the cottage pier", "in the school yard", "at the market", "deep in the forest"]
FI_ENDINGS = ["and everyone clapped.", "and nobody noticed a thing.", "because it was Tuesday.",
              "and laughed about it.", "even though it was sleeting.", "and won a prize for it.", "completely by accident."]


def lorem(paragraphs: int = 3, sentences: int = 5, seed: int | None = None) -> str:
    rng = random.Random(seed)
    out = []
    for p in range(paragraphs):
        sents = []
        for s in range(sentences):
            n = rng.randint(6, 14)
            ws = [rng.choice(LOREM_WORDS) for _ in range(n)]
            if p == 0 and s == 0:
                ws = "lorem ipsum dolor sit amet".split() + ws[5:]
            sent = " ".join(ws)
            sents.append(sent[0].upper() + sent[1:] + ".")
        out.append(" ".join(sents))
    return "\n\n".join(out)


def finnish_nonsense(sentences: int = 5, seed: int | None = None) -> str:
    rng = random.Random(seed)
    return " ".join(f"{rng.choice(FI_SUBJECTS)} {rng.choice(FI_VERBS)} {rng.choice(FI_OBJECTS)} "
                    f"{rng.choice(FI_PLACES)} {rng.choice(FI_ENDINGS)}" for _ in range(sentences))


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("text", "text-statistics", "Text statistics", "Characters, words, sentences, reading time and LIX readability",
      ("laske", "word count", "character count", "lix"))
def stats_tool() -> None:
    text = ui.get_text()
    st = text_stats(text)
    ui.print_kv([
        ("Characters", ui.fi_num(st["merkit"], 0)),
        ("…without spaces", ui.fi_num(st["chars_without_spaces"], 0)),
        ("Words", ui.fi_num(st["sanat"], 0)),
        ("Distinct words", ui.fi_num(st["uniikit_sanat"], 0)),
        ("Sentences", st["lauseet"]),
        ("Paragraphs", st["kappaleet"]),
        ("Rows", st["rivit"]),
        ("Average word length", ui.fi_num(st["sanan_keskipituus"], 1) + " chars"),
        ("Average sentence length", ui.fi_num(st["lauseen_keskipituus"], 1) + " words"),
        ("Reading time (200 words/min)", ui.fmt_duration(st["lukuaika_s"])),
        ("Speaking time (130 words/min)", ui.fmt_duration(st["puheaika_s"])),
        ("LIX readability", f"{st['lix']:.0f} – {lix_label(st['lix'])}"),
    ])
    common = top_words(text, 10)
    if common:
        print()
        ui.info("Most common words:")
        ui.bar_chart(common, color="bright_magenta")


@tool("text", "text-case", "Letter case and programming styles", "UPPER, lower, camelCase, snake_case, kebab-case…",
      ("case", "camel", "snake", "isot"))
def case_tool() -> None:
    text = ui.get_text()
    rows = [(label, convert_case(text, mode)) for mode, label in CASE_MODES.items()]
    for i, (label, result) in enumerate(rows, 1):
        print(f"{ui.c(str(i).rjust(2), 'bright_yellow')}) {ui.gray(label.ljust(44))} {result}")
    idx = ui.ask_int("Number to copy (0 = none)", 0, 0, len(rows))
    if idx:
        offer_copy(rows[idx - 1][1])


@tool("text", "text-reverse-text", "Reverse text", "Characters, words or lines backwards", ("reverse", "takaperin"))
def reverse_tool() -> None:
    text = ui.get_text()
    modes = [("chars", "Characters backwards"), ("words", "Words backwards"), ("lines", "Lines backwards"),
             ("each_word", "Each word backwards")]
    idx = ui.choose("Method", [m[1] for m in modes])
    result = reverse_text(text, modes[idx][0])
    print(ui.bold(result))
    offer_copy(result)


@tool("text", "text-line-tools", "Line tools", "Sort, deduplicate, shuffle, number and clean lines",
      ("sort", "lajittele", "tuplat", "uniq"))
def lines_tool() -> None:
    text = ui.get_text("Text (lines)")
    ops = [("sort", "Alphabetical A→Z"), ("sort_desc", "Reverse alphabetical"), ("sort_num", "Numeric order"),
           ("sort_len", "By length"), ("unique", "Remove duplicate lines"), ("unique_ci", "Remove duplicates (ignore case)"),
           ("dupes_only", "Show only duplicates"), ("shuffle", "Shuffle randomly"), ("number", "Number the lines"),
           ("unnumber", "Remove line numbers"), ("strip_empty", "Remove empty lines"), ("trim", "Trim spaces from line ends"),
           ("join", "Join into one line with commas")]
    idx = ui.choose("Action", [o[1] for o in ops])
    result = line_ops(text, ops[idx][0])
    print()
    ui.paginate(result.split("\n"))
    ui.info(f"{len(text.splitlines())} lines → {len(result.splitlines())} lines")
    offer_copy(result)
    offer_save(result, "lines.txt")


@tool("text", "text-find-replace", "Find and replace", "Replace text normally or with regex (also in a file)",
      ("replace", "regex", "korvaa"))
def replace_tool() -> None:
    text = ui.get_text()
    find = ui.ask("Find")
    repl = ui.ask("Replace with (empty = delete)", allow_empty=True)
    use_rx = ui.ask_yes_no("Regex?", False)
    ignore = ui.ask_yes_no("Ignore case?", False)
    flags = re.IGNORECASE if ignore else 0
    try:
        rx = re.compile(find if use_rx else re.escape(find), flags)
        result, n = rx.subn(repl if use_rx else repl.replace("\\", "\\\\"), text)
    except re.error as exc:
        ui.error(f"Invalid regex: {exc}")
        return
    print()
    ui.paginate(result.split("\n"))
    ui.success(f"{n} replacements.")
    offer_copy(result)
    offer_save(result, "korvattu.txt")


@tool("text", "text-clean-text", "Clean text", "Removes extra spaces, HTML, invisible characters and smart quotes",
      ("clean", "html", "spaces"))
def clean_tool() -> None:
    text = ui.get_text()
    if "<" in text and ">" in text and ui.ask_yes_no("Remove HTML tags?", True):
        text = html.unescape(strip_html(text))
    result = clean_text(text, smart_quotes=ui.ask_yes_no("Turn smart quotes into plain ones?", True))
    print()
    print(result)
    ui.info(f"{len(text)} → {len(result)} characters")
    offer_copy(result)


@tool("text", "text-extract", "Extract from text", "Emails, links, phone numbers, hashtags, IPs…",
      ("extract", "email", "url", "linkit"))
def extract_tool() -> None:
    text = ui.get_text()
    keys = list(EXTRACTORS)
    idx = ui.choose("What to extract", [EXTRACTORS[k][0] for k in keys] + ["All"])
    kinds = keys if idx == len(keys) else [keys[idx]]
    collected = []
    for k in kinds:
        items = extract(text, k)
        if items or len(kinds) == 1:
            print(ui.c(f"\n{EXTRACTORS[k][0]} ({len(items)})", "bold", "bright_cyan"))
            for it in items:
                print("  " + it)
            collected.extend(items)
    if collected:
        offer_copy("\n".join(collected))


@tool("text", "text-compare-texts", "Compare texts", "Shows the differences between two texts word by word or line by line",
      ("diff", "ero", "vertaa"))
def diff_tool() -> None:
    a = ui.get_text("First text")
    b = ui.get_text("Second text")
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    ui.info(f"Similarity {ratio * 100:.1f} %")
    wa, wb = re.findall(r"\S+|\s+", a), re.findall(r"\S+|\s+", b)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb).get_opcodes():
        if op == "equal":
            out.append("".join(wa[i1:i2]))
        if op in ("delete", "replace"):
            out.append(ui.c("".join(wa[i1:i2]), "strike", "bright_red"))
        if op in ("insert", "replace"):
            out.append(ui.c("".join(wb[j1:j2]), "underline", "bright_green"))
    print("".join(out))


@tool("text", "text-slug", "URL slug and file name", "Turns text into a clean URL or file name",
      ("slug", "url", "tiedostonimi"))
def slug_tool() -> None:
    text = ui.ask("Text")
    for label, sep in (("Slug", "-"), ("With underscores", "_"), ("With dots", ".")):
        print(f"{ui.gray(label.ljust(14))} {ui.bold(slugify(text, sep))}")
    offer_copy(slugify(text))


@tool("text", "text-lorem-ipsum", "Lorem ipsum and nonsense", "Filler text in Latin or as silly English sentences",
      ("lorem", "filler", "placeholder"))
def lorem_tool() -> None:
    kind = ui.choose("Type", ["Lorem ipsum (Latin)", "Silly nonsense"])
    if kind == 0:
        result = lorem(ui.ask_int("Paragraphs", 3, 1, 50), ui.ask_int("Sentences per paragraph", 5, 1, 30))
    else:
        result = finnish_nonsense(ui.ask_int("Sentences", 5, 1, 100))
    print()
    print(result)
    offer_copy(result)


@tool("text", "text-fancy-fonts", "Fancy fonts (Unicode)", "𝗕𝗼𝗹𝗱, 𝓈𝒸𝓇𝒾𝓅𝓉, ⓒⓘⓡⓒⓛⓔⓢ, ｗｉｄｅ, ʇxǝʇ uʍop ǝpısdn – for Discord and social media",
      ("fontti", "font", "discord", "nimimerkki", "fancy"))
def fancy_tool() -> None:
    text = ui.ask("Text")
    rows = all_styles(text)
    for i, (name, result) in enumerate(rows, 1):
        print(f"{ui.c(str(i).rjust(2), 'bright_yellow')}) {ui.gray(name.ljust(20))} {result}")
    idx = ui.ask_int("Number to copy (0 = none)", 0, 0, len(rows))
    if idx:
        offer_copy(rows[idx - 1][1])


@tool("text", "text-character-info", "Character info", "Unicode name, code point, UTF-8 bytes and category for every character",
      ("unicode", "merkki", "emoji", "koodipiste"))
def charinfo_tool() -> None:
    text = ui.ask("Text (e.g. an emoji or special character)")
    rows = []
    for ch in text[:80]:
        name = unicodedata.name(ch, "(unnamed)")
        rows.append((ch if ch.isprintable() else "·", f"U+{ord(ch):04X}", name.title(),
                     ch.encode("utf-8").hex(" ").upper(), unicodedata.category(ch)))
    ui.table(rows, ["Character", "Code", "Name", "UTF-8", "Class"], max_col_width=45)


@tool("text", "text-fix-mojibake", "Fix broken characters (mojibake)", "Turns 'cafÃ©' back into 'café'",
      ("mojibake", "mojibake", "encoding", "encoding"))
def mojibake_tool() -> None:
    text = ui.get_text("Broken text")
    fixed = fix_mojibake(text)
    if fixed == text:
        ui.info("I didn't find anything to fix.")
    else:
        print(ui.bold(fixed))
        offer_copy(fixed)


@tool("text", "text-palindromes", "Palindromes and anagrams", "Is the text a palindrome? Are the words anagrams of each other?",
      ("palindromi", "anagrammi", "saippuakauppias"))
def anagram_tool() -> None:
    mode = ui.choose("Check", ["Palindrome (e.g. racecar)", "Anagrams (e.g. 'listen' and 'silent')"])
    if mode == 0:
        text = ui.ask("Text")
        if is_palindrome(text):
            ui.success("It's a palindrome! Same forwards and backwards.")
        else:
            ui.warn("Not a palindrome.")
            print(ui.gray("Backwards: ") + text[::-1])
    else:
        a, b = ui.ask("First"), ui.ask("Second")
        if is_anagram(a, b):
            ui.success("They are anagrams!")
        else:
            ca = Counter(ch.lower() for ch in a if ch.isalnum())
            cb = Counter(ch.lower() for ch in b if ch.isalnum())
            ui.warn("They are not anagrams.")
            if ca - cb:
                print("  Only in the first: " + "".join(sorted((ca - cb).elements())))
            if cb - ca:
                print("  Only in the second: " + "".join(sorted((cb - ca).elements())))


@tool("text", "text-wrap", "Wrap and align", "Wraps text to a given width and aligns it left, right or centre",
      ("wrap", "tasaus", "leveys"))
def wrap_tool() -> None:
    text = ui.get_text()
    width = ui.ask_int("Line width", 60, 10, 300)
    align = ui.choose("Alignment", ["Left", "Right", "Centre", "Justify"])
    out = []
    for para in re.split(r"\n\s*\n", text):
        lines = textwrap.wrap(" ".join(para.split()), width)
        for i, line in enumerate(lines):
            if align == 1:
                line = line.rjust(width)
            elif align == 2:
                line = line.center(width).rstrip()
            elif align == 3 and i < len(lines) - 1:
                ws = line.split()
                gaps = len(ws) - 1
                if gaps:
                    spaces = width - sum(len(w) for w in ws)
                    q, r = divmod(spaces, gaps)
                    line = "".join(w + " " * (q + (1 if j < r else 0)) for j, w in enumerate(ws[:-1])) + ws[-1]
            out.append(line)
        out.append("")
    result = "\n".join(out).rstrip()
    print(result)
    offer_copy(result)


@tool("text", "text-word-frequencies", "Word frequencies", "The most common words and their share as a chart", ("frekvenssi", "sanapilvi", "most common"))
def freq_tool() -> None:
    text = ui.get_text()
    n = ui.ask_int("How many words", 25, 1, 200)
    skip = ui.ask_yes_no("Skip common filler words (and, the, is…)?", True)
    total = len(words(text)) or 1
    rows = top_words(text, n, skip)
    ui.bar_chart(rows, value_fmt=lambda v: f"{int(v)} ({v / total * 100:.1f} %)")


@tool("text", "text-morse-code", "Morse code", "Text to Morse and back",
      ("morse", "telegraph", "sos"))
def morse_tool() -> None:
    mode = ui.choose("Direction", ["Text → Morse", "Morse → text"])
    if mode == 0:
        text = ui.ask("Text")
        code = morse_encode(text)
        print(ui.bold(code))
        offer_copy(code)
        if ui.ask_yes_no("Save as an audio file (WAV)?", False):
            from .media import morse_wav

            path = morse_wav(text, ui.ask("File", "morse.wav"))
            ui.success(f"Saved: {path}")
    else:
        code = ui.ask("Morse (dots, dashes, word gap /)")
        print(ui.bold(morse_decode(code)))


@tool("text", "text-char-limits", "Character counter and limits", "Does the text fit in a tweet, an SMS or a Discord message?",
      ("raja", "twitter", "tekstiviesti", "sms", "discord"))
def limits_tool() -> None:
    text = ui.get_text()
    n = len(text)
    gsm = set(string.ascii_letters + string.digits + " \n\r@£$¥èéùìòÇØøÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ!\"#¤%&'()*+,-./:;<=>?¡ÄÖÑÜ§¿äöñüà")
    is_gsm = all(ch in gsm for ch in text)
    per = (160, 153) if is_gsm else (70, 67)
    sms = 1 if n <= per[0] else -(-n // per[1])
    limits = [("Text message", f"{sms} message{'s' if sms != 1 else ''} ({'GSM' if is_gsm else 'Unicode'} charset)"),
              ("X / Twitter (280)", "fits" if n <= 280 else f"{n - 280} too many"),
              ("Discord message (2000)", "fits" if n <= 2000 else f"{n - 2000} too many"),
              ("Discord Nitro (4000)", "fits" if n <= 4000 else f"{n - 4000} too many"),
              ("Instagram caption (2200)", "fits" if n <= 2200 else f"{n - 2200} too many"),
              ("Meta description (160)", "fits" if n <= 160 else f"{n - 160} too many"),
              ("Bytes as UTF-8", ui.fi_num(len(text.encode("utf-8")), 0))]
    ui.info(f"{n} characters")
    ui.print_kv(limits)
