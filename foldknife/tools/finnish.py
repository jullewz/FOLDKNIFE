"""Finland tools: personal identity code, business ID, IBAN, reference numbers, bank barcode, VAT,
numbers in Finnish words, public holidays, hyphenation, phone numbers and proverbs."""
from __future__ import annotations

import datetime as dt
import random
import re

from ..core import ui
from ..core.registry import tool
from ..core.utils import FI_WEEKDAYS, fi_date, offer_copy

# --------------------------------------------------------------------------
# Personal identity code (HETU)
# --------------------------------------------------------------------------

HETU_CHECK = "0123456789ABCDEFHJKLMNPRSTUVWXY"
CENTURY = {"+": 1800, "-": 1900, "Y": 1900, "X": 1900, "W": 1900, "V": 1900, "U": 1900,
           "A": 2000, "B": 2000, "C": 2000, "D": 2000, "E": 2000, "F": 2000}
HETU_RE = re.compile(r"^(\d{2})(\d{2})(\d{2})([-+A-FU-Y])(\d{3})([0-9A-Y])$")


def hetu_info(code: str, today: dt.date | None = None) -> dict[str, str]:
    """Checks a Finnish personal identity code and returns what can be read from it. Invalid → ValueError."""
    c = code.strip().upper()
    m = HETU_RE.match(c)
    if not m:
        raise ValueError("Invalid format (correct format: DDMMYY-NNNC, e.g. 131052-308T).")
    dd, mm, yy, sign, ind, check = m.groups()
    expected = HETU_CHECK[int(dd + mm + yy + ind) % 31]
    if check != expected:
        raise ValueError(f"The check character is wrong (should be {expected}).")
    year = CENTURY[sign] + int(yy)
    try:
        born = dt.date(year, int(mm), int(dd))
    except ValueError as exc:
        raise ValueError("That date doesn't exist.") from exc
    today = today or dt.date.today()
    if born > today:
        raise ValueError("The date of birth is in the future.")
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    num = int(ind)
    if num < 2:
        raise ValueError("Individual numbers 000 and 001 aren't used.")
    return {
        "Valid": "yes ✔",
        "Date of birth": f"{fi_date(born)} ({FI_WEEKDAYS[born.weekday()]})",
        "Age": f"{age} years",
        "Sex (according to the code)": "male" if num % 2 else "female",
        "Individual number": ind + (" (temporary/artificial)" if num >= 900 else ""),
        "Century sign": sign + (" (new sign from 2023)" if sign in "YXWVUBCDEF" else ""),
    }


# --------------------------------------------------------------------------
# Business ID (Y-tunnus)
# --------------------------------------------------------------------------

def ytunnus_check(base7: str) -> int:
    weights = [7, 9, 10, 5, 8, 4, 2]
    if not re.fullmatch(r"\d{7}", base7):
        raise ValueError("The body of a business ID is 7 digits.")
    r = sum(int(d) * w for d, w in zip(base7, weights)) % 11
    if r == 1:
        raise ValueError("No valid business ID can have this body (remainder 1).")
    return 0 if r == 0 else 11 - r


def validate_ytunnus(code: str) -> str:
    c = code.strip().replace(" ", "")
    m = re.fullmatch(r"(\d{6,7})-?(\d)", c)
    if not m:
        raise ValueError("Invalid format (e.g. 1234567-1).")
    base = m.group(1).zfill(7)
    if ytunnus_check(base) != int(m.group(2)):
        raise ValueError(f"The check digit is wrong (should be {ytunnus_check(base)}).")
    return f"{base}-{m.group(2)}"


# --------------------------------------------------------------------------
# IBAN
# --------------------------------------------------------------------------

IBAN_LENGTHS = {
    "FI": 18, "SE": 24, "NO": 15, "DK": 18, "EE": 20, "LV": 21, "LT": 20, "DE": 22, "GB": 22, "IE": 22,
    "FR": 27, "ES": 24, "PT": 25, "IT": 27, "NL": 18, "BE": 16, "LU": 20, "AT": 20, "CH": 21, "PL": 28,
    "CZ": 24, "SK": 24, "HU": 28, "SI": 19, "HR": 21, "GR": 27, "CY": 28, "MT": 31, "IS": 26, "AX": 18,
    "RO": 24, "BG": 22, "LI": 21, "MC": 27, "SM": 27, "GI": 23, "TR": 26, "UA": 29,
}

FI_BANKS = [  # (account prefix, bank, BIC) – approximate
    ("1", "Nordea", "NDEAFIHH"), ("2", "Nordea", "NDEAFIHH"), ("31", "Handelsbanken", "HANDFIHH"),
    ("33", "SEB", "ESSEFIHX"), ("34", "Danske Bank", "DABAFIHX"), ("36", "S-Pankki", "SBANFIHH"),
    ("37", "DNB", "DNBAFIHX"), ("38", "Swedbank", "SWEDFIHH"), ("39", "S-Pankki", "SBANFIHH"),
    ("405", "Aktia", "HELSFIHH"), ("497", "Aktia", "HELSFIHH"), ("470", "POP Pankki", "POPFFI22"),
    ("471", "POP Pankki", "POPFFI22"), ("472", "POP Pankki", "POPFFI22"), ("473", "POP Pankki", "POPFFI22"),
    ("474", "POP Pankki", "POPFFI22"), ("475", "POP Pankki", "POPFFI22"), ("476", "POP Pankki", "POPFFI22"),
    ("477", "POP Pankki", "POPFFI22"), ("478", "POP Pankki", "POPFFI22"), ("479", "Bonum Pankki", "POPFFI22"),
    ("4", "Säästöpankki", "ITELFIHH"), ("5", "OP", "OKOYFIHH"), ("6", "Ålandsbanken", "AABAFI22"),
    ("713", "Citibank", "CITIFIHX"), ("715", "Säästöpankki", "ITELFIHH"), ("717", "Bigbank", "BIGKFIH1"),
    ("799", "Holvi", "HOLVFIHH"), ("8", "Danske Bank", "DABAFIHH"),
]


def iban_normalize(iban: str) -> str:
    return re.sub(r"\s+", "", iban).upper()


def iban_mod97(s: str) -> int:
    rearranged = s[4:] + s[:4]
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(digits) % 97


def validate_iban(iban: str) -> str:
    s = iban_normalize(iban)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{8,30}", s):
        raise ValueError("Invalid format (e.g. FI21 1234 5600 0007 85).")
    expected_len = IBAN_LENGTHS.get(s[:2])
    if expected_len and len(s) != expected_len:
        raise ValueError(f"An IBAN from {s[:2]} must have {expected_len} characters (now {len(s)}).")
    if iban_mod97(s) != 1:
        raise ValueError("The check digits don't match – the account number has an error.")
    return s


def format_iban(iban: str) -> str:
    s = iban_normalize(iban)
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4))


def fi_bank(iban: str) -> tuple[str, str] | None:
    s = iban_normalize(iban)
    if not s.startswith("FI"):
        return None
    bban = s[4:]
    for prefix, name, bic in sorted(FI_BANKS, key=lambda x: -len(x[0])):
        if bban.startswith(prefix):
            return name, bic
    return None


# --------------------------------------------------------------------------
# Reference numbers
# --------------------------------------------------------------------------

def reference_check(base: str) -> int:
    weights = [7, 3, 1]
    total = sum(int(d) * weights[i % 3] for i, d in enumerate(reversed(base)))
    return (10 - total % 10) % 10


def make_reference(base: str) -> str:
    b = re.sub(r"\s+", "", base)
    if not re.fullmatch(r"\d{3,19}", b):
        raise ValueError("The base must have 3–19 digits.")
    return b + str(reference_check(b))


def validate_reference(ref: str) -> str:
    r = re.sub(r"\s+", "", ref).lstrip("0") or "0"
    if r.upper().startswith("RF"):
        return validate_rf(r)
    if not re.fullmatch(r"\d{4,20}", r):
        raise ValueError("A reference number has 4–20 digits.")
    if reference_check(r[:-1]) != int(r[-1]):
        raise ValueError(f"The check digit is wrong (should be {reference_check(r[:-1])}).")
    return r


def format_reference(ref: str) -> str:
    r = re.sub(r"\s+", "", ref)
    if r.upper().startswith("RF"):
        return " ".join(r[i:i + 4] for i in range(0, len(r), 4))
    groups = []
    while r:
        groups.insert(0, r[-5:])
        r = r[:-5]
    return " ".join(groups)


def to_rf(ref: str) -> str:
    r = validate_reference(ref)
    num = int("".join(str(int(ch, 36)) for ch in r + "RF00"))
    return f"RF{98 - num % 97:02d}{r}"


def validate_rf(rf: str) -> str:
    s = re.sub(r"\s+", "", rf).upper()
    if not re.fullmatch(r"RF\d{2}[0-9A-Z]{1,21}", s):
        raise ValueError("An RF reference is RFkk + up to 21 characters.")
    if iban_mod97(s) != 1:
        raise ValueError("The RF reference check digits don't match.")
    return s


# --------------------------------------------------------------------------
# Bank barcode (virtual barcode)
# --------------------------------------------------------------------------

def make_barcode(iban: str, amount: float, reference: str, due: dt.date | None) -> str:
    s = validate_iban(iban)
    if not s.startswith("FI"):
        raise ValueError("The bank barcode is made for a Finnish (FI) account.")
    if not 0 <= amount <= 999999.99:
        raise ValueError("The amount must be 0–999,999.99 €.")
    cents_total = round(amount * 100)
    euros, cents = divmod(cents_total, 100)
    date_part = due.strftime("%y%m%d") if due else "000000"
    ref = re.sub(r"\s+", "", reference).upper()
    if ref.startswith("RF"):
        rf = validate_rf(ref)
        if not rf[4:].isdigit():
            raise ValueError("Only a numeric RF reference fits in the barcode.")
        return f"5{s[2:]}{euros:06d}{cents:02d}{rf[2:4]}{rf[4:].zfill(21)}{date_part}"
    validate_reference(ref)
    return f"4{s[2:]}{euros:06d}{cents:02d}000{ref.zfill(20)}{date_part}"


def parse_barcode(code: str) -> dict[str, str]:
    c = re.sub(r"\s+", "", code)
    if not re.fullmatch(r"[45]\d{53}", c):
        raise ValueError("A virtual barcode has 54 digits and starts with 4 or 5.")
    iban = "FI" + c[1:17]
    euros, cents = int(c[17:23]), int(c[23:25])
    if c[0] == "4":
        ref = c[28:48].lstrip("0")
    else:
        ref = "RF" + c[25:27] + c[27:48].lstrip("0")
    date = c[48:54]
    due = "no due date" if date == "000000" else f"{int(date[4:6])}.{int(date[2:4])}.20{date[0:2]}"
    return {"Version": c[0] + (" (domestic reference)" if c[0] == "4" else " (RF reference)"),
            "Payee account": format_iban(iban), "Sum": f"{ui.fi_num(euros + cents / 100, 2)} €",
            "Reference": format_reference(ref), "Due date": due}


# --------------------------------------------------------------------------
# VAT
# --------------------------------------------------------------------------

VAT_RATES = [(25.5, "general rate"), (13.5, "food, restaurants, books, medicines, sports, culture, transport"),
             (10.0, "newspapers and magazines"), (0.0, "tax-free sales")]


# --------------------------------------------------------------------------
# Numbers in Finnish words
# --------------------------------------------------------------------------

ONES = ["nolla", "yksi", "kaksi", "kolme", "neljä", "viisi", "kuusi", "seitsemän", "kahdeksan", "yhdeksän"]


def _below_1000(n: int) -> str:
    h, r = divmod(n, 100)
    out = ""
    if h:
        out += "sata" if h == 1 else ONES[h] + "sataa"
    if r:
        if r < 10:
            out += ONES[r]
        elif r == 10:
            out += "kymmenen"
        elif r < 20:
            out += ONES[r - 10] + "toista"
        else:
            t, u = divmod(r, 10)
            out += ONES[t] + "kymmentä" + (ONES[u] if u else "")
    return out


def _below_million(n: int) -> str:
    th, r = divmod(n, 1000)
    out = ""
    if th:
        out += "tuhat" if th == 1 else _below_1000(th) + "tuhatta"
    if r:
        out += _below_1000(r)
    return out


def number_to_words(n: int) -> str:
    """Writes an integer in Finnish: 2026 → kaksituhattakaksikymmentäkuusi."""
    if n == 0:
        return "nolla"
    if n < 0:
        return "miinus " + number_to_words(-n)
    if n >= 10 ** 18:
        raise ValueError("Number too large (must be under a trillion).")
    parts = []
    for value, one, many in ((10 ** 12, "biljoona", "biljoonaa"), (10 ** 9, "miljardi", "miljardia"),
                             (10 ** 6, "miljoona", "miljoonaa")):
        q, n = divmod(n, value)
        if q:
            parts.append(one if q == 1 else f"{number_to_words(q)} {many}")
    if n:
        parts.append(_below_million(n))
    return " ".join(parts)


_ORD = ["nollas", "ensimmäinen", "toinen", "kolmas", "neljäs", "viides", "kuudes", "seitsemäs", "kahdeksas", "yhdeksäs"]
_ORD_STEM = ["", "yhdes", "kahdes", "kolmas", "neljäs", "viides", "kuudes", "seitsemäs", "kahdeksas", "yhdeksäs"]


def ordinal_words(n: int) -> str:
    """Ordinal in Finnish words (1–999,999): 21 → kahdeskymmenesensimmäinen."""
    if not 0 < n < 1_000_000:
        raise ValueError("Ordinals 1–999,999.")

    def below_1000(x: int, final: bool) -> str:
        h, r = divmod(x, 100)
        out = ""
        if h:
            out += "sadas" if h == 1 else _ORD_STEM[h] + "sadas"
        if r:
            if r < 10:
                out += _ORD[r] if final else _ORD_STEM[r]
            elif r == 10:
                out += "kymmenes"
            elif r < 20:
                out += _ORD_STEM[r - 10] + "toista"
            else:
                t, u = divmod(r, 10)
                out += _ORD_STEM[t] + "kymmenes" + (_ORD[u] if u else "")
        return out

    th, r = divmod(n, 1000)
    out = ""
    if th:
        out += "tuhannes" if th == 1 else below_1000(th, False) + "tuhannes"
    if r:
        out += below_1000(r, True)
    return out


def money_words(amount: float) -> str:
    cents_total = round(amount * 100)
    euros, cents = divmod(abs(cents_total), 100)
    out = f"{number_to_words(euros)} {'euro' if euros == 1 else 'euroa'}"
    if cents:
        out += f" {number_to_words(cents)} {'sentti' if cents == 1 else 'senttiä'}"
    return ("miinus " if cents_total < 0 else "") + out


# --------------------------------------------------------------------------
# Public holidays
# --------------------------------------------------------------------------

def easter(year: int) -> dt.date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def _sat_between(year: int, month: int, day: int) -> dt.date:
    d = dt.date(year, month, day)
    return d + dt.timedelta(days=(5 - d.weekday()) % 7)


def holidays(year: int) -> dict[dt.date, tuple[str, bool]]:
    """Finnish public holidays, celebrations and flag days: {date: (name, is_day_off)}."""
    e = easter(year)
    midsummer = _sat_between(year, 6, 20)
    days: dict[dt.date, tuple[str, bool]] = {}

    def add(d: dt.date, name: str, off: bool = False) -> None:
        if d in days:
            old_name, old_off = days[d]
            days[d] = (f"{old_name} · {name}", old_off or off)
        else:
            days[d] = (name, off)

    add(dt.date(year, 1, 1), "New Year's Day", True)
    add(dt.date(year, 1, 6), "Epiphany", True)
    add(dt.date(year, 2, 5), "J. L. Runeberg Day")
    add(dt.date(year, 2, 6), "Sámi National Day")
    add(dt.date(year, 2, 14), "Valentine's Day (Friendship Day)")
    add(dt.date(year, 2, 28), "Kalevala Day, Day of Finnish Culture")
    add(e - dt.timedelta(days=49), "Shrove Sunday")
    add(e - dt.timedelta(days=47), "Shrove Tuesday")
    add(dt.date(year, 3, 19), "Minna Canth Day, Day of Equality")
    add(_last_weekday(year, 3, 6), "Daylight saving time starts (clocks forward)")
    add(e - dt.timedelta(days=7), "Palm Sunday")
    add(e - dt.timedelta(days=3), "Maundy Thursday")
    add(e - dt.timedelta(days=2), "Good Friday", True)
    add(e, "Easter Sunday", True)
    add(e + dt.timedelta(days=1), "Easter Monday", True)
    add(dt.date(year, 4, 9), "Mikael Agricola Day, Day of the Finnish Language")
    add(dt.date(year, 4, 27), "National Veterans' Day")
    add(dt.date(year, 4, 30), "May Day Eve")
    add(dt.date(year, 5, 1), "May Day (Vappu), Day of Finnish Labour", True)
    add(dt.date(year, 5, 9), "Europe Day")
    add(dt.date(year, 5, 12), "J. V. Snellman Day, Day of Finnish Heritage")
    add(_nth_weekday(year, 5, 6, 2), "Mother's Day")
    add(_nth_weekday(year, 5, 6, 3), "Remembrance Day")
    add(e + dt.timedelta(days=39), "Ascension Day", True)
    add(e + dt.timedelta(days=49), "Pentecost", True)
    add(dt.date(year, 6, 4), "Flag Day of the Finnish Defence Forces")
    add(midsummer - dt.timedelta(days=1), "Midsummer Eve", True)
    add(midsummer, "Midsummer Day, Day of the Finnish Flag", True)
    add(dt.date(year, 7, 6), "Eino Leino Day, Day of Poetry and Summer")
    add(_last_weekday(year, 8, 5), "Day of Finnish Nature")
    add(dt.date(year, 10, 10), "Aleksis Kivi Day, Day of Finnish Literature")
    add(dt.date(year, 10, 24), "United Nations Day")
    add(_last_weekday(year, 10, 6), "Daylight saving time ends (clocks back)")
    add(_sat_between(year, 10, 31), "All Saints' Day", True)
    add(dt.date(year, 11, 6), "Finnish Swedish Heritage Day")
    add(_nth_weekday(year, 11, 6, 2), "Father's Day")
    add(dt.date(year, 11, 20), "Day of Children's Rights")
    add(dt.date(year, 12, 6), "Independence Day", True)
    add(dt.date(year, 12, 8), "Jean Sibelius Day, Day of Finnish Music")
    add(dt.date(year, 12, 24), "Christmas Eve", True)
    add(dt.date(year, 12, 25), "Christmas Day", True)
    add(dt.date(year, 12, 26), "Boxing Day (St Stephen's Day)", True)
    add(dt.date(year, 12, 31), "New Year's Eve")
    return dict(sorted(days.items()))


# --------------------------------------------------------------------------
# Hyphenation
# --------------------------------------------------------------------------

VOWELS = set("aeiouyäöå")
DIPHTHONGS = {"ai", "ei", "oi", "ui", "yi", "äi", "öi", "au", "eu", "iu", "ou", "ey", "iy", "äy", "öy"}
FIRST_ONLY = {"ie", "uo", "yö"}


def hyphenate_word(word: str, sep: str = "-") -> str:
    low = word.lower()
    if len(low) < 2:
        return word
    breaks: set[int] = set()
    syllable = 0
    nucleus = 0  # number of vowels in the current syllable nucleus
    seen_vowel = False
    for i, ch in enumerate(low):
        if ch in VOWELS:
            if i > 0 and low[i - 1] in VOWELS:
                pair = low[i - 1] + ch
                joinable = nucleus == 1 and (pair[0] == pair[1] or pair in DIPHTHONGS or
                                             (pair in FIRST_ONLY and syllable == 0))
                if joinable:
                    nucleus += 1
                else:
                    breaks.add(i)
                    syllable += 1
                    nucleus = 1
            else:
                nucleus = 1
            seen_vowel = True
        else:
            if i + 1 < len(low) and low[i + 1] in VOWELS and seen_vowel and i > 0:
                breaks.add(i)
                syllable += 1
                nucleus = 0
            elif not ch.isalpha():
                seen_vowel = False
                nucleus = 0
    out = []
    for i, ch in enumerate(word):
        if i in breaks:
            out.append(sep)
        out.append(ch)
    return "".join(out)


def hyphenate(text: str, sep: str = "-") -> str:
    return re.sub(r"[A-Za-zÅÄÖåäöÉéÜü]+", lambda m: hyphenate_word(m.group(0), sep), text)


# --------------------------------------------------------------------------
# Phone numbers and spelling alphabets
# --------------------------------------------------------------------------

def normalize_phone(raw: str) -> tuple[str, str]:
    s = re.sub(r"[^\d+]", "", raw)
    if s.startswith("00"):
        s = "+" + s[2:]
    if s.startswith("+358"):
        national = "0" + s[4:]
    elif s.startswith("358") and len(s) >= 10:
        national = "0" + s[3:]
    elif s.startswith("0"):
        national = s
    elif s.startswith("+"):
        return s, s
    else:
        raise ValueError("Enter the number as 040 123 4567 or +358 40 123 4567.")
    if not 6 <= len(national) <= 12:
        raise ValueError("The number has the wrong number of digits.")
    e164 = "+358" + national[1:]
    if national.startswith(("04", "050")):
        pre = 3
    elif national[1] in "235689" and national[:3] not in ("020", "029", "030"):
        pre = 2
    else:
        pre = 3
    rest = national[pre:]
    formatted = national[:pre] + " " + (rest[:3] + " " + rest[3:] if len(rest) > 5 else rest)
    return e164, formatted.strip()


FI_SPELLING = {
    "A": "Aarne", "B": "Bertta", "C": "Celsius", "D": "Daavid", "E": "Eemeli", "F": "Faarao", "G": "Gideon",
    "H": "Heikki", "I": "Iivari", "J": "Jussi", "K": "Kalle", "L": "Lauri", "M": "Matti", "N": "Niilo",
    "O": "Otto", "P": "Paavo", "Q": "Kuu", "R": "Risto", "S": "Sakari", "T": "Tyyne", "U": "Urho",
    "V": "Vihtori", "W": "Wiski", "X": "Äksä", "Y": "Yrjö", "Z": "Tseta", "Å": "Åke", "Ä": "Äiti", "Ö": "Öljy",
}
NATO = {
    "A": "Alfa", "B": "Bravo", "C": "Charlie", "D": "Delta", "E": "Echo", "F": "Foxtrot", "G": "Golf",
    "H": "Hotel", "I": "India", "J": "Juliett", "K": "Kilo", "L": "Lima", "M": "Mike", "N": "November",
    "O": "Oscar", "P": "Papa", "Q": "Quebec", "R": "Romeo", "S": "Sierra", "T": "Tango", "U": "Uniform",
    "V": "Victor", "W": "Whiskey", "X": "X-ray", "Y": "Yankee", "Z": "Zulu",
    "0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six", "7": "Seven",
    "8": "Eight", "9": "Niner",
}

PROVERBS = [
    "The morning is wiser than the evening.", "Learning never tips you into the ditch.", "Slow and steady brings good things.", "The work praises its maker.",
    "He who reaches for the spruce falls into the juniper.", "Your own land is a strawberry, other lands are blueberries.",
    "Better late than never.", "Diligence beats even hard luck.", "No smoke without fire.",
    "He who digs a pit for another falls into it himself.", "Speech is silver, silence is golden.",
    "He who asks won't get lost.", "The forest answers the way you shout into it.", "The apple doesn't fall far from the tree.",
    "Many a cake is pretty on top.", "When you plaster, it splashes.", "The dog that the stick hits is the one that yelps.",
    "Empty barrels rattle the loudest.", "A bird in the hand is worth ten on the branch.", "Necessity knows no law.",
    "A rolling stone gathers no moss.", "If you have luck, keep it hidden.", "A cat lives on thanks.",
    "No one is born a blacksmith.", "Self-praise stinks.", "What you learn young, you know when old.",
    "Envy takes even the fish from the water.", "Don't lick it before it drops.", "Quality, not quantity.",
    "The fool works hard, the wise gets by with less.", "Love doesn't rust.", "It's hard to make something out of nothing.",
    "Harmony makes room.", "Accidents don't come with a bell around their neck.", "Too many cooks spoil the soup.",
    "Appetite grows with eating.", "Well planned is half done.", "Crying won't help at the market.",
    "Who will lift the cat's tail if not the cat itself.", "Ask the spruce you live under.",
    "The grass is always greener on the other side of the fence.", "You never know whose axe ends up in church.",
]


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("finnish", "fi-hetu", "Personal identity code", "Checks a Finnish personal identity code and shows date of birth and age (incl. the new 2023 century signs)",
      ("hetu", "identity code", "sotu"))
def hetu_tool() -> None:
    code = ui.ask("Personal identity code")
    try:
        ui.print_kv(hetu_info(code))
    except ValueError as exc:
        ui.error(f"Invalid: {exc}")
    print(ui.gray("  The check runs only on your machine, nothing is sent anywhere."))


@tool("finnish", "fi-business-id", "Business ID", "Checks a Finnish business ID (Y-tunnus) or computes the check digit for a body", ("y-tunnus", "yritys", "ytunnus"))
def ytunnus_tool() -> None:
    code = ui.ask("Business ID (or 7-digit body)")
    try:
        if re.fullmatch(r"\d{7}", code.strip()):
            print(ui.bold(f"  {code.strip()}-{ytunnus_check(code.strip())}"))
        else:
            ui.success(f"Valid: {validate_ytunnus(code)}")
    except ValueError as exc:
        ui.error(str(exc))


@tool("finnish", "fi-iban", "IBAN account number", "Checks an IBAN, formats it and shows the Finnish bank and BIC code",
      ("iban", "tilinumero", "bic", "pankki"))
def iban_tool() -> None:
    raw = ui.ask("IBAN")
    try:
        s = validate_iban(raw)
    except ValueError as exc:
        ui.error(str(exc))
        return
    rows = [("Valid", "yes ✔"), ("Formatted", format_iban(s)), ("Country", s[:2])]
    bank = fi_bank(s)
    if bank:
        rows += [("Bank (estimate)", bank[0]), ("BIC", bank[1])]
    ui.print_kv(rows)
    offer_copy(format_iban(s))


@tool("finnish", "fi-reference-numbers", "Reference numbers", "Create and check Finnish reference numbers, make series and convert to RF format",
      ("viite", "viitenumero", "lasku", "rf"))
def reference_tool() -> None:
    k = ui.choose("Action", ["Create a reference number from a base", "Check a reference number", "Create a series of reference numbers",
                               "Convert to an international RF reference"])
    try:
        if k == 0:
            ref = make_reference(ui.ask("Base (e.g. customer number)", "1234"))
            print(ui.bold(f"  {format_reference(ref)}"))
            offer_copy(ref)
        elif k == 1:
            ref = validate_reference(ui.ask("Reference number"))
            ui.success(f"Valid: {format_reference(ref)}")
        elif k == 2:
            start = ui.ask_int("First base", 1000, 100)
            count = ui.ask_int("How many", 10, 1, 10000)
            refs = [make_reference(str(start + i)) for i in range(count)]
            ui.paginate([format_reference(r) for r in refs])
            offer_copy("\n".join(refs))
        else:
            rf = to_rf(ui.ask("Domestic reference number"))
            print(ui.bold(f"  {format_reference(rf)}"))
            offer_copy(rf)
    except ValueError as exc:
        ui.error(str(exc))


@tool("finnish", "fi-bank-barcode", "Bank barcode", "Create or decode an invoice virtual barcode (54 digits)",
      ("viivakoodi", "lasku", "virtuaaliviivakoodi", "pankki"))
def barcode_tool() -> None:
    k = ui.choose("Action", ["Create a barcode", "Decode a barcode"])
    try:
        if k == 0:
            iban = ui.ask("Payee IBAN")
            amount = ui.ask_float("Amount (€)", 0)
            ref = ui.ask("Reference number (or RF reference)")
            due_raw = ui.ask("Due date (empty = none)", allow_empty=True)
            from ..core.utils import parse_date

            code = make_barcode(iban, amount, ref, parse_date(due_raw) if due_raw else None)
            print(ui.bold(f"  {code}"))
            offer_copy(code)
        else:
            ui.print_kv(parse_barcode(ui.ask("Virtual barcode")))
    except ValueError as exc:
        ui.error(str(exc))


@tool("finnish", "fi-vat-calculator", "VAT calculator", "Finnish VAT 25.5 %, 13.5 % and 10 % – gross ↔ net",
      ("alv", "vat", "vero", "vat"))
def vat_tool() -> None:
    for rate, desc in VAT_RATES:
        print(f"  {ui.c(f'{rate:g} %'.rjust(7), 'bright_yellow')}  {ui.gray(desc)}")
    print(ui.gray("  (rates from 1 Jan 2026 – check vero.fi for current rates)"))
    k = ui.choose("The given price is", ["Net (VAT 0 %)", "Gross"])
    price = ui.ask_float("Price (€)", 100)
    rows = []
    for rate, _ in VAT_RATES[:3]:
        if k == 0:
            net, gross = price, price * (1 + rate / 100)
        else:
            gross, net = price, price / (1 + rate / 100)
        rows.append((f"{rate:g} %", ui.fi_num(net), ui.fi_num(gross - net), ui.fi_num(gross)))
    ui.table(rows, ["VAT rate", "Net €", "VAT €", "Gross €"], align=["<", ">", ">", ">"])


@tool("finnish", "fi-number-words", "Numbers to Finnish words", "2026 → kaksituhattakaksikymmentäkuusi, also ordinals and money amounts",
      ("sanoin", "numerot", "kuitti", "shekki", "ordinal"))
def words_tool() -> None:
    raw = ui.ask("Number or money amount", "2026")
    try:
        if re.search(r"[.,]", raw):
            amount = float(raw.replace(" ", "").replace(",", "."))
            result = money_words(amount)
            print(ui.bold("  " + result))
        else:
            n = int(raw.replace(" ", ""))
            result = number_to_words(n)
            print(ui.bold("  " + result))
            if 0 < n < 1_000_000:
                print(ui.gray("  As ordinal: ") + ordinal_words(n))
            print(ui.gray("  As money: ") + money_words(n))
        offer_copy(result)
    except ValueError as exc:
        ui.error(str(exc))


@tool("finnish", "fi-holidays", "Finnish holidays & flag days", "Public holidays, flag days, Easter, Midsummer and DST for a year",
      ("holiday", "liputus", "juhannus", "easter", "loma", "daylight saving"))
def holidays_tool() -> None:
    year = ui.ask_int("Year", dt.date.today().year, 1583, 4099)
    today = dt.date.today()
    rows = []
    for d, (name, off) in holidays(year).items():
        when = f"{FI_WEEKDAYS[d.weekday()][:2]} {d.day}.{d.month}."
        mark = ui.red("day off") if off else ""
        line_name = ui.bold(name) if off else name
        if d == today:
            line_name = ui.c(name + "  ← today", "bright_green", "bold")
        rows.append((when, line_name, mark))
    ui.table(rows, ["Day", "Holiday", ""], max_col_width=60)
    upcoming = [(d, n) for d, (n, off) in holidays(today.year).items() if d >= today and off]
    if upcoming and year == today.year:
        d, n = upcoming[0]
        ui.info(f"Next day off: {n} {fi_date(d)} (in {(d - today).days} days)")


@tool("finnish", "fi-hyphenation", "Finnish hyphenation", "Splits Finnish text into syllables (ka-la-kuk-ko)", ("tavu", "tavutus", "hyphen"))
def hyphen_tool() -> None:
    text = ui.get_text()
    result = hyphenate(text)
    print(ui.bold(result))
    print(ui.gray("  Rule-based hyphenation can get compound words and derivations wrong."))
    offer_copy(result)


@tool("finnish", "fi-phone-numbers", "Phone numbers", "Formats Finnish phone numbers and makes the international form",
      ("puhelin", "numero", "+358", "gsm"))
def phone_tool() -> None:
    text = ui.get_text("Number(s), one per line")
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            e164, nat = normalize_phone(line)
            print(f"  {nat.ljust(16)} {ui.c(e164, 'bright_cyan')}")
        except ValueError as exc:
            print(f"  {line.strip().ljust(16)} {ui.red(str(exc))}")


@tool("finnish", "fi-spelling-alphabets", "Spelling alphabets", "Spells text for the phone: Aarne, Bertta, Celsius… (and NATO)",
      ("tavaus", "aakkoset", "nato", "puhelin", "aarne"))
def spelling_tool() -> None:
    text = ui.ask("Text (e.g. a name or licence plate)")
    rows = []
    for ch in text.upper():
        if ch == " ":
            rows.append(("␣", "(space)", "(space)"))
        elif ch in FI_SPELLING or ch in NATO:
            rows.append((ch, FI_SPELLING.get(ch, {"0": "nolla", "1": "yksi", "2": "kaksi", "3": "kolme", "4": "neljä",
                                                  "5": "viisi", "6": "kuusi", "7": "seitsemän", "8": "kahdeksan",
                                                  "9": "yhdeksän"}.get(ch, ch)), NATO.get(ch, "-")))
        else:
            rows.append((ch, ch, ch))
    ui.table(rows, ["Character", "Finnish", "NATO"])


@tool("finnish", "fi-proverbs", "Finnish proverbs", "A random Finnish proverb (in English translation) or search by word",
      ("sananlasku", "viisaus", "mietelause"))
def proverb_tool() -> None:
    q = ui.ask("Search word (empty = random)", allow_empty=True).lower()
    hits = [p for p in PROVERBS if q in p.lower()] if q else [random.choice(PROVERBS)]
    if not hits:
        ui.warn("No matches.")
    for p in hits:
        ui.box([ui.c(p, "bold", "bright_yellow")], color="yellow")
