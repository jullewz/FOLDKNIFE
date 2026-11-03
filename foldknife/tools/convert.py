"""Conversions: units, number bases, colours, times, dates, calendar and data formats."""
from __future__ import annotations

import calendar
import colorsys
import configparser
import csv
import datetime as dt
import email.utils
import io
import json
import math
import re
import struct
import time
import urllib.parse
import xml.dom.minidom
import xml.etree.ElementTree as ET
from typing import Any

from ..core import ui
from ..core.registry import tool
from ..core.utils import FI_MONTHS, FI_WEEKDAYS, fi_date, offer_copy, offer_save, parse_date

# --------------------------------------------------------------------------
# Units
# --------------------------------------------------------------------------

# (category, symbol, factor to the base unit, name, aliases)
_UNIT_DATA: list[tuple[str, str, float, str, tuple[str, ...]]] = [
    ("length", "nm", 1e-9, "nanometre", ("nanometri",)), ("length", "µm", 1e-6, "micrometre", ("um", "mikrometri")),
    ("length", "mm", 1e-3, "millimetre", ("millimetres", "millimetri")), ("length", "cm", 1e-2, "centimetre", ("centimetres", "sentti", "senttimetri")),
    ("length", "dm", 0.1, "decimetre", ("desimetri",)), ("length", "m", 1.0, "metre", ("metres", "metri", "metri")),
    ("length", "km", 1000.0, "kilometre", ("kilometres", "kilsaa", "kilometri")), ("length", "in", 0.0254, "inch", ("inch", "tuumaa", '"', "tuuma")),
    ("length", "ft", 0.3048, "foot", ("feet", "foot", "jalkaa", "jalka")), ("length", "yd", 0.9144, "yard", ("jaardia", "jaardi")),
    ("length", "mi", 1609.344, "mile", ("mile", "miles", "mailia", "maili")), ("length", "nmi", 1852.0, "nautical mile", ("mpk", "meripeninkulma")),
    ("length", "pk", 10000.0, "Scandinavian mile (10 km)", ("peninkulmaa", "peninkulma")), ("length", "virsta", 1068.8, "verst (old Russian)", ()),
    ("length", "cubit", 0.5938, "cubit (old Finnish)", ()), ("length", "au", 1.495978707e11, "astronomical unit", ()),
    ("length", "ly", 9.4607304725808e15, "light year", ("valovuotta", "valovuosi")), ("length", "pc", 3.0856775814913673e16, "parsec", ("parsek",)),
    ("mass", "mg", 1e-6, "milligram", ("milligramma",)), ("mass", "g", 1e-3, "gram", ("grammaa", "gramma")),
    ("mass", "kg", 1.0, "kilogram", ("kiloa", "kilo", "kilogramma")), ("mass", "t", 1000.0, "tonne", ("tonnia", "tonni")),
    ("mass", "oz", 0.028349523125, "ounce", ("unssi",)), ("mass", "lb", 0.45359237, "pound", ("lbs", "paunaa", "pauna")),
    ("mass", "st", 6.35029318, "stone", ()), ("mass", "ct", 0.0002, "carat", ("karaatti",)),
    ("mass", "naula", 0.42507, "pound (old Finnish)", ()), ("mass", "leiviska", 8.5, "leiviskä (old Finnish weight)", ("leiviskä (old)",)),
    ("volume", "ml", 1e-3, "millilitre", ("millilitra",)), ("volume", "cl", 1e-2, "centilitre", ("senttilitra",)),
    ("volume", "dl", 0.1, "decilitre", ("decilitres", "desilitra")), ("volume", "l", 1.0, "litre", ("litraa", "litra", "litra")),
    ("volume", "m3", 1000.0, "cubic metre", ("m³", "kuutio", "kuutiometri")), ("volume", "cm3", 1e-3, "cubic centimetre", ("cm³", "cc", "kuutiosenttimetri")),
    ("volume", "tl", 0.005, "teaspoon", ("tsp", "teelusikka")), ("volume", "rkl", 0.015, "tablespoon", ("tbsp", "ruokalusikka")),
    ("volume", "cup", 0.2365882365, "cup (US)", ("kuppi",)), ("volume", "floz", 0.0295735295625, "fluid ounce (US)", ()),
    ("volume", "pint", 0.473176473, "pint (US)", ()), ("volume", "ukpint", 0.56826125, "pint (UK)", ()),
    ("volume", "gal", 3.785411784, "gallon (US)", ()), ("volume", "ukgal", 4.54609, "gallon (UK)", ()),
    ("volume", "bbl", 158.987294928, "oil barrel", ()), ("volume", "kannu", 2.617, "kannu (old Finnish)", ()),
    ("area", "mm2", 1e-6, "square millimetre", ("mm²",)), ("area", "cm2", 1e-4, "square centimetre", ("cm²",)),
    ("area", "m2", 1.0, "square metre", ("m²", "square", "squares")), ("area", "a", 100.0, "are", ("aaria", "aari")),
    ("area", "ha", 1e4, "hectare", ("hehtaaria", "hehtaari")), ("area", "km2", 1e6, "square kilometre", ("km²",)),
    ("area", "ft2", 0.09290304, "square foot", ("ft²", "sqft")), ("area", "ac", 4046.8564224, "acre", ("acre", "eekkeri")),
    ("area", "mi2", 2589988.110336, "square mile", ("mi²",)), ("area", "field", 7140.0, "football field", ()),
    ("speed", "m/s", 1.0, "metres per second", ("mps",)), ("speed", "km/h", 1 / 3.6, "kilometres per hour", ("kmh", "kph")),
    ("speed", "mph", 0.44704, "miles per hour", ()), ("speed", "kn", 0.5144444444, "knot", ("solmua", "knot", "solmu")),
    ("speed", "ft/s", 0.3048, "feet per second", ()), ("speed", "mach", 343.0, "mach (air at 20 °C)", ()),
    ("speed", "c", 299792458.0, "speed of light", ("valonnopeus",)),
    ("time", "ns", 1e-9, "nanosecond", ("nanosekunti",)), ("time", "µs", 1e-6, "microsecond", ("us", "mikrosekunti")),
    ("time", "ms", 1e-3, "millisecond", ("millisekunti",)), ("time", "s", 1.0, "second", ("sek", "sekuntia", "sekunti")),
    ("time", "min", 60.0, "minute", ("minuuttia", "minuutti")), ("time", "h", 3600.0, "hour", ("tuntia", "t", "tunti")),
    ("time", "d", 86400.0, "day", ("vrk", "päivää", "pv", "vuorokausi")), ("time", "vk", 604800.0, "week", ("viikkoa", "wk", "viikko")),
    ("time", "kk", 2629746.0, "month (average)", ("kuukautta",)), ("time", "v", 31556952.0, "year (average)", ("vuotta", "yr")),
    ("data", "bit", 0.125, "bit", ("b", "bits", "bitti")), ("data", "B", 1.0, "byte", ("tavua", "byte", "tavu")),
    ("data", "kB", 1e3, "kilobyte", ("KB", "kilotavu")), ("data", "KiB", 1024.0, "kibibyte", ("kibitavu",)),
    ("data", "MB", 1e6, "megabyte", ("megatavu",)), ("data", "MiB", 1024.0 ** 2, "mebibyte", ("mebitavu",)),
    ("data", "GB", 1e9, "gigabyte", ("gigatavu",)), ("data", "GiB", 1024.0 ** 3, "gibibyte", ("gibitavu",)),
    ("data", "TB", 1e12, "terabyte", ("teratavu",)), ("data", "TiB", 1024.0 ** 4, "tebibyte", ("tebitavu",)),
    ("data", "Mbit", 1e6 / 8, "megabit", ("Mb", "megabitti")), ("data", "Gbit", 1e9 / 8, "gigabit", ("Gb", "gigabitti")),
    ("energy", "J", 1.0, "joule", ()), ("energy", "kJ", 1e3, "kilojoule", ()), ("energy", "MJ", 1e6, "megajoule", ()),
    ("energy", "cal", 4.184, "calorie", ("kalori",)), ("energy", "kcal", 4184.0, "kilocalorie", ("kilokalori",)),
    ("energy", "Wh", 3600.0, "watt-hour", ("wattitunti",)), ("energy", "kWh", 3.6e6, "kilowatt-hour", ("kilowattitunti",)),
    ("energy", "eV", 1.602176634e-19, "electronvolt", ("elektronivoltti",)), ("energy", "BTU", 1055.05585262, "BTU", ()),
    ("power", "W", 1.0, "watt", ("watti",)), ("power", "kW", 1e3, "kilowatt", ("kilowatti",)), ("power", "MW", 1e6, "megawatt", ("megawatti",)),
    ("power", "hv", 735.49875, "horsepower (metric)", ("hk",)), ("power", "hp", 745.699872, "horsepower (UK/US)", ()),
    ("pressure", "Pa", 1.0, "pascal", ()), ("pressure", "hPa", 100.0, "hectopascal", ("hehtopascal",)), ("pressure", "kPa", 1e3, "kilopascal", ()),
    ("pressure", "MPa", 1e6, "megapascal", ()), ("pressure", "bar", 1e5, "bar", ("baari",)), ("pressure", "mbar", 100.0, "millibar", ("millibaari",)),
    ("pressure", "atm", 101325.0, "atmosphere", ()), ("pressure", "psi", 6894.757293168, "psi", ()),
    ("pressure", "mmHg", 133.322387415, "millimetre of mercury", ("elohopeamillimetri",)),
    ("angle", "rad", 1.0, "radian", ("radiaani",)), ("angle", "deg", math.pi / 180, "degree", ("°", "astetta", "aste")),
    ("angle", "grad", math.pi / 200, "gradian", ("gooni",)), ("angle", "kierros", 2 * math.pi, "turn", ("turn", "kierros")),
    ("angle", "arcmin", math.pi / 10800, "arcminute", ("kaariminuutti",)), ("angle", "arcsec", math.pi / 648000, "arcsecond", ("kaarisekunti",)),
    ("frequency", "Hz", 1.0, "hertz", ("hertsi",)), ("frequency", "kHz", 1e3, "kilohertz", ("kilohertsi",)), ("frequency", "MHz", 1e6, "megahertz", ("megahertsi",)),
    ("frequency", "GHz", 1e9, "gigahertz", ("gigahertsi",)), ("frequency", "rpm", 1 / 60, "revolutions per minute", ()),
]

TEMP_UNITS = {"C": "celsius", "F": "fahrenheit", "K": "kelvin", "R": "rankine", "Re": "réaumur"}
TEMP_ALIASES = {"c": "C", "°c": "C", "celsius": "C", "f": "F", "°f": "F", "fahrenheit": "F",
                "k": "K", "kelvin": "K", "r": "R", "ra": "R", "rankine": "R", "re": "Re", "réaumur": "Re"}
FUEL_UNITS = {"l/100km": "litres / 100 km", "km/l": "km per litre", "mpg": "miles per gallon (US)",
              "ukmpg": "miles per gallon (UK)"}

UNITS: dict[str, tuple[str, float, str]] = {}
_ALIASES: dict[str, str] = {}
for cat, sym, factor, name, aliases in _UNIT_DATA:
    UNITS[sym] = (cat, factor, name)
    for a in (sym, *aliases, name):
        _ALIASES.setdefault(a, sym)
        _ALIASES.setdefault(a.lower(), sym)

CATEGORIES = sorted({c for c, *_ in _UNIT_DATA}) + ["temperature", "fuel consumption"]


def resolve_unit(text: str) -> tuple[str, str]:
    """Returns (category, symbol)."""
    t = text.strip()
    if t in TEMP_UNITS or t.lower() in TEMP_ALIASES:
        return "temperature", TEMP_UNITS.get(t) and t or TEMP_ALIASES[t.lower()]
    if t.lower() in FUEL_UNITS or t in FUEL_UNITS:
        return "fuel consumption", t.lower()
    sym = _ALIASES.get(t) or _ALIASES.get(t.lower())
    if not sym:
        raise ValueError(f"Unknown unit: {text}")
    return UNITS[sym][0], sym


def _to_kelvin(v: float, u: str) -> float:
    return {"C": v + 273.15, "F": (v + 459.67) * 5 / 9, "K": v, "R": v * 5 / 9, "Re": v * 5 / 4 + 273.15}[u]


def _from_kelvin(k: float, u: str) -> float:
    return {"C": k - 273.15, "F": k * 9 / 5 - 459.67, "K": k, "R": k * 9 / 5, "Re": (k - 273.15) * 4 / 5}[u]


def _fuel_to_l100(v: float, u: str) -> float:
    if u == "l/100km":
        return v
    if v == 0:
        raise ValueError("Can't convert from zero.")
    return {"km/l": 100 / v, "mpg": 235.214583 / v, "ukmpg": 282.480936 / v}[u]


def _fuel_from_l100(v: float, u: str) -> float:
    if u == "l/100km":
        return v
    return {"km/l": 100 / v, "mpg": 235.214583 / v, "ukmpg": 282.480936 / v}[u]


def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    cat_a, a = resolve_unit(from_unit)
    cat_b, b = resolve_unit(to_unit)
    if cat_a != cat_b:
        raise ValueError(f"The units aren't the same kind ({cat_a} vs {cat_b}).")
    if cat_a == "temperature":
        return _from_kelvin(_to_kelvin(value, a), b)
    if cat_a == "fuel consumption":
        return _fuel_from_l100(_fuel_to_l100(value, a), b)
    return value * UNITS[a][1] / UNITS[b][1]


def units_in(category: str) -> list[str]:
    if category == "temperature":
        return list(TEMP_UNITS)
    if category == "fuel consumption":
        return list(FUEL_UNITS)
    return [s for s, (c, _, _) in UNITS.items() if c == category]


def unit_name(sym: str) -> str:
    if sym in TEMP_UNITS:
        return TEMP_UNITS[sym]
    if sym in FUEL_UNITS:
        return FUEL_UNITS[sym]
    return UNITS[sym][2]


def fmt_num(v: float) -> str:
    if v == 0:
        return "0"
    if abs(v) >= 1e12 or abs(v) < 1e-4:
        mant, exp = f"{v:.6e}".split("e")
        return f"{mant.rstrip('0').rstrip('.')} × 10^{int(exp)}"
    s = f"{v:,.6f}".rstrip("0").rstrip(".")
    return s


def convert_text(text: str) -> str:
    """Quick conversion from text: '10 km mi', '72 F to C', '5.5 kg lb', '100 km/h'."""
    t = text.strip().replace("→", " ").replace("->", " ")
    m = re.match(r"^\s*(-?\d[\d\s]*(?:[.,]\d+)?(?:e[+-]?\d+)?)\s*(.*)$", t, re.IGNORECASE)
    if not m:
        raise ValueError("Use the form: 10 km mi")
    value = float(m.group(1).replace(" ", "").replace(",", "."))
    rest = [w for w in m.group(2).split() if w.lower() not in ("to", "in", "=", "on", "ksi", "into", "->")]
    if not rest:
        raise ValueError("Enter the source unit.")
    src = rest[0]
    cat, _ = resolve_unit(src)
    if len(rest) >= 2:
        dst = rest[-1]
        return f"{fmt_num(value)} {src} = {fmt_num(convert_units(value, src, dst))} {dst}"
    lines = [f"{fmt_num(value)} {src} ="]
    for u in units_in(cat):
        if u != resolve_unit(src)[1]:
            try:
                lines.append(f"  {fmt_num(convert_units(value, src, u)).rjust(22)} {u:<8} {unit_name(u)}")
            except (ValueError, ZeroDivisionError):
                pass
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Number bases
# --------------------------------------------------------------------------

DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def to_base(n: int, base: int) -> str:
    if not 2 <= base <= 36:
        raise ValueError("The base must be 2–36.")
    if n == 0:
        return "0"
    sign = "-" if n < 0 else ""
    n = abs(n)
    out = []
    while n:
        n, r = divmod(n, base)
        out.append(DIGITS[r])
    return sign + "".join(reversed(out))


def parse_int_auto(text: str, base: int | None = None) -> int:
    t = text.strip().lower().replace("_", "").replace(" ", "")
    if base:
        return int(t, base)
    if t.startswith(("0x", "-0x")):
        return int(t, 16)
    if t.startswith(("0b", "-0b")):
        return int(t, 2)
    if t.startswith(("0o", "-0o")):
        return int(t, 8)
    if t.endswith("h") and re.fullmatch(r"-?[0-9a-f]+h", t):
        return int(t[:-1], 16)
    return int(t, 10)


def group(s: str, n: int = 4, sep: str = " ") -> str:
    sign = "-" if s.startswith("-") else ""
    s = s.lstrip("-")
    s = s.rjust((len(s) + n - 1) // n * n, "0")
    return sign + sep.join(s[i:i + n] for i in range(0, len(s), n))


def twos_complement(n: int, bits: int) -> str:
    if not -(1 << (bits - 1)) <= n < (1 << bits):
        return "doesn't fit"
    return format(n & ((1 << bits) - 1), f"0{bits}b")


def float_bits(x: float) -> tuple[str, str]:
    b32 = format(struct.unpack(">I", struct.pack(">f", x))[0], "032b")
    b64 = format(struct.unpack(">Q", struct.pack(">d", x))[0], "064b")
    return f"{b32[0]} {b32[1:9]} {b32[9:]}", f"{b64[0]} {b64[1:12]} {b64[12:]}"


def roman_to_int(text: str) -> int:
    s = text.strip().upper()
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    if not s or any(ch not in vals for ch in s):
        raise ValueError("Roman numerals may only contain I, V, X, L, C, D and M.")
    total = 0
    for i, ch in enumerate(s):
        v = vals[ch]
        if i + 1 < len(s) and vals[s[i + 1]] > v:
            total -= v
        else:
            total += v
    from .mathtools import roman

    if roman(total) != s:
        raise ValueError(f"Unusual notation – the canonical form of {total} is {roman(total)}.")
    return total


# --------------------------------------------------------------------------
# Colours
# --------------------------------------------------------------------------

NAMED_COLORS = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000", "blue": "#0000ff",
    "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080", "pink": "#ffc0cb", "brown": "#a52a2a",
    "gray": "#808080", "grey": "#808080", "silver": "#c0c0c0", "gold": "#ffd700", "turquoise": "#40e0d0", "navy": "#000080",
    "sky blue": "#87ceeb", "olive": "#808000", "maroon": "#800000", "lime": "#00ff00", "cyan": "#00ffff",
    "magenta": "#ff00ff", "teal": "#008080", "coral": "#ff7f50", "salmon": "#fa8072",
    "lavender": "#e6e6fa", "beige": "#f5f5dc", "khaki": "#f0e68c", "indigo": "#4b0082", "chocolate": "#d2691e",
    "tomato": "#ff6347", "forest green": "#228b22", "mint green": "#98ff98", "finland blue": "#002f6c",
    "discord blurple": "#5865f2", "spotify green": "#1db954",
}


def parse_color(text: str) -> tuple[int, int, int]:
    t = text.strip().lower()
    if t in NAMED_COLORS:
        t = NAMED_COLORS[t]
    m = re.fullmatch(r"#?([0-9a-f]{3}|[0-9a-f]{6})", t)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    m = re.fullmatch(r"hsl\(?\s*([\d.]+)\s*,?\s*([\d.]+)%?\s*,?\s*([\d.]+)%?\s*\)?", t)
    if m:
        h, s, l = float(m.group(1)) / 360, float(m.group(2)) / 100, float(m.group(3)) / 100
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return round(r * 255), round(g * 255), round(b * 255)
    nums = re.findall(r"\d+(?:\.\d+)?", t)
    if len(nums) == 3:
        vals = [round(float(n)) for n in nums]
        if all(0 <= v <= 255 for v in vals):
            return vals[0], vals[1], vals[2]
    raise ValueError("Enter a colour like #ff8800, rgb(255,136,0), hsl(32,100%,50%) or a name.")


def to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def color_formats(rgb: tuple[int, int, int]) -> list[tuple[str, str]]:
    r, g, b = rgb
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    hv, sv, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    k = 1 - max(r, g, b) / 255
    if k < 1:
        c_, m_, y_ = ((1 - x / 255 - k) / (1 - k) for x in (r, g, b))
    else:
        c_ = m_ = y_ = 0.0
    nearest = min(NAMED_COLORS.items(), key=lambda kv: sum((a - b_) ** 2 for a, b_ in zip(parse_color(kv[1]), rgb)))
    return [("HEX", to_hex(rgb).upper()), ("RGB", f"rgb({r}, {g}, {b})"),
            ("HSL", f"hsl({h * 360:.0f}, {s * 100:.0f}%, {l * 100:.0f}%)"),
            ("HSV", f"hsv({hv * 360:.0f}, {sv * 100:.0f}%, {vv * 100:.0f}%)"),
            ("CMYK", f"cmyk({c_ * 100:.0f}%, {m_ * 100:.0f}%, {y_ * 100:.0f}%, {k * 100:.0f}%)"),
            ("Decimal (Discord)", str(r << 16 | g << 8 | b)), ("Nearest named", nearest[0])]


def rotate_hue(rgb: tuple[int, int, int], degrees: float) -> tuple[int, int, int]:
    h, l, s = colorsys.rgb_to_hls(*(x / 255 for x in rgb))
    r, g, b = colorsys.hls_to_rgb((h + degrees / 360) % 1, l, s)
    return round(r * 255), round(g * 255), round(b * 255)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def luminance(rgb: tuple[int, int, int]) -> float:
    def ch(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def swatch(rgb: tuple[int, int, int], width: int = 8) -> str:
    return ui.bg_rgb(" " * width, *rgb)


# --------------------------------------------------------------------------
# Time zones
# --------------------------------------------------------------------------

WORLD_CITIES = [("Helsinki", "Europe/Helsinki", 2), ("Stockholm", "Europe/Stockholm", 1), ("London", "Europe/London", 0),
                ("Berlin", "Europe/Berlin", 1), ("Moscow", "Europe/Moscow", 3), ("Dubai", "Asia/Dubai", 4),
                ("Delhi", "Asia/Kolkata", 5.5), ("Bangkok", "Asia/Bangkok", 7), ("Beijing", "Asia/Shanghai", 8),
                ("Tokyo", "Asia/Tokyo", 9), ("Sydney", "Australia/Sydney", 10), ("Auckland", "Pacific/Auckland", 12),
                ("Honolulu", "Pacific/Honolulu", -10), ("Los Angeles", "America/Los_Angeles", -8),
                ("Chicago", "America/Chicago", -6), ("New York", "America/New_York", -5),
                ("São Paulo", "America/Sao_Paulo", -3), ("Reykjavík", "Atlantic/Reykjavik", 0)]


def get_zone(name: str) -> dt.tzinfo:
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - tzdata may be missing on Windows
        for _, zone, offset in WORLD_CITIES:
            if zone == name:
                return dt.timezone(dt.timedelta(hours=offset), name)
        raise ValueError(f"Time zone {name} not found (install it if needed: pip install tzdata)")


def zoneinfo_ok() -> bool:
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo("Europe/Helsinki")
        return True
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# Data formats
# --------------------------------------------------------------------------

def infer(value: str) -> Any:
    v = value.strip()
    if v == "":
        return None
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if re.fullmatch(r"-?\d+", v) and not (len(v) > 1 and v.lstrip("-").startswith("0")):
        return int(v)
    if re.fullmatch(r"-?\d+[.,]\d+", v):
        return float(v.replace(",", "."))
    return v


def csv_to_json(text: str, typed: bool = True) -> list[dict[str, Any]]:
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    if typed:
        rows = [{k: infer(v) if isinstance(v, str) else v for k, v in r.items()} for r in rows]
    return rows


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}{k}."))
    elif isinstance(obj, list) and obj and all(not isinstance(x, (dict, list)) for x in obj):
        out[prefix[:-1]] = "; ".join(str(x) for x in obj)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}{i}."))
    else:
        out[prefix[:-1]] = obj
    return out


def json_to_csv(data: Any, delimiter: str = ",") -> str:
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [data])
    if not isinstance(data, list):
        raise ValueError("The JSON must be a list of objects.")
    rows = [flatten(x) if isinstance(x, (dict, list)) else {"value": x} for x in data]
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, delimiter=delimiter, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def xml_to_obj(elem: ET.Element) -> Any:
    children = list(elem)
    node: dict[str, Any] = {f"@{k}": v for k, v in elem.attrib.items()}
    if not children:
        text = (elem.text or "").strip()
        if not node:
            return text
        if text:
            node["#text"] = text
        return node
    for ch in children:
        val = xml_to_obj(ch)
        if ch.tag in node:
            if not isinstance(node[ch.tag], list):
                node[ch.tag] = [node[ch.tag]]
            node[ch.tag].append(val)
        else:
            node[ch.tag] = val
    return node


def csv_to_markdown(text: str) -> str:
    rows = csv_to_json(text, typed=False)
    if not rows:
        return ""
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(h) or "").replace("|", "\\|") for h in headers) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

def months_between(a: dt.date, b: dt.date) -> tuple[int, int, int]:
    """Whole years, months and days between dates a ≤ b."""
    if b < a:
        a, b = b, a
    total = (b.year - a.year) * 12 + (b.month - a.month)
    if add_months(a, total) > b:
        total -= 1
    days = (b - add_months(a, total)).days
    return total // 12, total % 12, days


def add_months(d: dt.date, n: int) -> dt.date:
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def working_days(a: dt.date, b: dt.date) -> int:
    from .finnish import holidays

    if b < a:
        a, b = b, a
    hol: set[dt.date] = set()
    for y in range(a.year, b.year + 1):
        hol.update(d for d, (_, off) in holidays(y).items() if off)
    n = 0
    d = a
    while d <= b:
        if d.weekday() < 5 and d not in hol:
            n += 1
        d += dt.timedelta(days=1)
    return n


def month_calendar(year: int, month: int, highlight: dict[dt.date, str] | None = None) -> list[str]:
    highlight = highlight or {}
    today = dt.date.today()
    title = f"{FI_MONTHS[month - 1].capitalize()} {year}"
    lines = [ui.bold(title.center(27)), ui.gray("wk Mo Tu We Th Fr Sa Su")]
    for week in calendar.Calendar(0).monthdatescalendar(year, month):
        wk = week[0].isocalendar()[1]
        cells = []
        for d in week:
            s = f"{d.day:>2}"
            if d.month != month:
                cells.append(ui.gray("  "))
            elif d == today:
                cells.append(ui.c(s, "reverse", "bold"))
            elif d in highlight:
                cells.append(ui.c(s, "bold", "bright_red"))
            elif d.weekday() == 6:
                cells.append(ui.red(s))
            elif d.weekday() == 5:
                cells.append(ui.yellow(s))
            else:
                cells.append(s)
        lines.append(ui.gray(f"{wk:>2}") + "  " + " ".join(cells))
    while len(lines) < 8:
        lines.append("")
    return lines


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("convert", "convert-units", "Unit converter", "Length, mass, volume, temperature, speed, data, energy… (e.g. 10 km mi)",
      ("unit", "unit", "muunna", "metri", "maili", "celsius"))
def units_tool() -> None:
    print(ui.gray("Quick form: '10 km mi', '72 F C', '5 dl cup', '100 km/h' (shows all)."))
    print(ui.gray("An empty line opens the menu, 'q' quits."))
    while True:
        raw = ui.ask("Conversion", allow_empty=True)
        if raw.lower() == "q":
            return
        if raw:
            try:
                print(ui.bold(convert_text(raw)))
            except (ValueError, ZeroDivisionError) as exc:
                ui.error(str(exc))
            continue
        cat = CATEGORIES[ui.choose("Quantity", [c.capitalize() for c in CATEGORIES])]
        units = units_in(cat)
        print(ui.gray("Units: " + ", ".join(f"{u} ({unit_name(u)})" for u in units)))
        value = ui.ask_float("Value", 1)
        src = ui.ask("From which unit", units[0])
        try:
            print(ui.bold(convert_text(f"{value} {src}")))
        except ValueError as exc:
            ui.error(str(exc))


@tool("convert", "convert-number-bases", "Number bases", "Binary, octal, decimal, hex and any base 2–36, two's complement, IEEE 754",
      ("binary", "heksa", "hex", "binary", "kantaluku", "base"))
def bases_tool() -> None:
    print(ui.gray("Prefixes are detected: 0b1010, 0x1F, 0o17. Otherwise decimal."))
    raw = ui.ask("Number")
    base_in = ui.ask("Source base (empty = automatic)", allow_empty=True)
    try:
        if re.fullmatch(r"-?\d*[.,]\d+", raw.strip()):
            x = float(raw.replace(",", "."))
            b32, b64 = float_bits(x)
            ui.print_kv([("float32", b32), ("float64", b64), ("float32 as hex", struct.pack(">f", x).hex()),
                         ("float64 as hex", struct.pack(">d", x).hex()), ("Exact value as float32", repr(struct.unpack(">f", struct.pack(">f", x))[0]))])
            return
        n = parse_int_auto(raw, int(base_in) if base_in else None)
    except ValueError as exc:
        ui.error(f"Invalid number: {exc}")
        return
    rows = [("Decimal", f"{n:,}".replace(",", " ")), ("Binary", group(to_base(n, 2))), ("Octal", to_base(n, 8)),
            ("Hex", group(to_base(n, 16).upper(), 2)), ("Base 36", to_base(n, 36)), ("Bits", str(abs(n).bit_length()))]
    if n < 0 or n < 2 ** 64:
        for bits in (8, 16, 32, 64):
            rows.append((f"{bits}-bit two's complement", group(twos_complement(n, bits), 4) if twos_complement(n, bits) != "doesn't fit" else "doesn't fit"))
    if 0 <= n < 0x110000:
        try:
            rows.append(("Unicode character", repr(chr(n))))
        except ValueError:
            pass
    ui.print_kv(rows)
    other = ui.ask("Other base 2–36 (empty = none)", allow_empty=True)
    if other.isdigit():
        print(ui.bold(f"  Base {other}: {to_base(n, int(other))}"))


@tool("convert", "convert-colours", "Colour converter and palettes", "HEX ↔ RGB ↔ HSL ↔ CMYK, shades, palettes and contrast check",
      ("colour", "color", "hex", "rgb", "paletti", "kontrasti"))
def colors_tool() -> None:
    mode = ui.choose("Action", ["Convert a colour and show palettes", "Contrast check (accessibility)", "Gradient between two colours"])
    try:
        if mode == 0:
            rgb = parse_color(ui.ask("Colour", "#ff8800"))
            print(swatch(rgb, 24))
            ui.print_kv(color_formats(rgb))
            print()
            for label, cols in (("Complementary", [rgb, rotate_hue(rgb, 180)]),
                                ("Analogous", [rotate_hue(rgb, -30), rgb, rotate_hue(rgb, 30)]),
                                ("Triad", [rgb, rotate_hue(rgb, 120), rotate_hue(rgb, 240)]),
                                ("Lighter", [mix(rgb, (255, 255, 255), t / 5) for t in range(5)]),
                                ("Darker", [mix(rgb, (0, 0, 0), t / 5) for t in range(5)])):
                print(f"{ui.gray(label.ljust(12))} " + " ".join(swatch(c, 4) + " " + to_hex(c) for c in cols))
        elif mode == 1:
            fg = parse_color(ui.ask("Text colour", "#777777"))
            bg = parse_color(ui.ask("Background colour", "#ffffff"))
            ratio = contrast_ratio(fg, bg)
            print("  " + ui.fg_bg_rgb("  Sample text – Foldknife 123  ", fg, bg))
            ui.print_kv([("Contrast ratio", f"{ratio:.2f}:1"),
                         ("WCAG AA (normal text ≥ 4.5)", ui.green("OK") if ratio >= 4.5 else ui.red("fails")),
                         ("WCAG AA (large text ≥ 3)", ui.green("OK") if ratio >= 3 else ui.red("fails")),
                         ("WCAG AAA (≥ 7)", ui.green("OK") if ratio >= 7 else ui.red("fails"))])
        else:
            a = parse_color(ui.ask("Start colour", "#ff0080"))
            b = parse_color(ui.ask("End colour", "#00c0ff"))
            steps = ui.ask_int("Steps", 8, 2, 40)
            cols = [mix(a, b, i / (steps - 1)) for i in range(steps)]
            print("".join(swatch(c, 4) for c in cols))
            for c in cols:
                print("  " + swatch(c, 2) + " " + to_hex(c))
            offer_copy(", ".join(to_hex(c) for c in cols))
    except ValueError as exc:
        ui.error(str(exc))


@tool("convert", "convert-timestamps", "Unix timestamps", "Timestamp ↔ date, ISO 8601, RFC 2822 and milliseconds",
      ("timestamp", "unix", "epoch", "aikaleima", "iso"))
def timestamp_tool() -> None:
    now = time.time()
    ui.print_kv([("Now (seconds)", int(now)), ("Now (milliseconds)", int(now * 1000)),
                 ("ISO 8601", dt.datetime.now().astimezone().isoformat(timespec="seconds"))])
    raw = ui.ask("Timestamp or date (e.g. 1700000000 or 2026-12-24 18:00)", allow_empty=True)
    if not raw:
        return
    try:
        if re.fullmatch(r"-?\d{1,16}(\.\d+)?", raw.strip()):
            v = float(raw)
            if abs(v) > 1e11:
                v /= 1000
            local = dt.datetime.fromtimestamp(v).astimezone()
        else:
            parts = raw.split()
            d = parse_date(parts[0])
            t = dt.time(0, 0)
            if len(parts) > 1:
                hh, mm, *ss = (int(x) for x in re.split(r"[:.]", parts[1]))
                t = dt.time(hh, mm, ss[0] if ss else 0)
            local = dt.datetime.combine(d, t).astimezone()
    except (ValueError, OverflowError, OSError) as exc:
        ui.error(str(exc))
        return
    utc = local.astimezone(dt.timezone.utc)
    ui.print_kv([("Local time", f"{FI_WEEKDAYS[local.weekday()]} {local:%Y-%m-%d %H:%M:%S} ({local.tzname()})"),
                 ("UTC", f"{utc:%Y-%m-%d %H:%M:%S}"), ("Unix (s)", int(local.timestamp())),
                 ("Unix (ms)", int(local.timestamp() * 1000)), ("ISO 8601", local.isoformat(timespec="seconds")),
                 ("RFC 2822", email.utils.format_datetime(local)),
                 ("Discord timestamp", f"<t:{int(local.timestamp())}:F>  (relative: <t:{int(local.timestamp())}:R>)"),
                 ("Relative to now", ("in the future " if local.timestamp() > now else "") + ui.fmt_duration(abs(local.timestamp() - now)) + ("" if local.timestamp() > now else " ago"))])


@tool("convert", "convert-date-calculator", "Date calculator", "Difference, working days, adding, week number, weekday and age",
      ("date", "age", "viikkonumero", "working days", "date"))
def dates_tool() -> None:
    kinds = ["Days between two dates", "Add or subtract time", "Weekday and week number",
             "Age calculator", "What day is it in N days?"]
    k = ui.choose("Calculation", kinds)
    try:
        if k == 0:
            a = parse_date(ui.ask("Start date", "today"))
            b = parse_date(ui.ask("End date", f"24.12.{dt.date.today().year}"))
            days = (b - a).days
            y, m, d = months_between(a, b)
            ui.print_kv([("Days", ui.fi_num(abs(days), 0)), ("In weeks", f"{abs(days) // 7} wk {abs(days) % 7} d"),
                         ("As calendar time", f"{y} y {m} mo {d} d"), ("Working days (Mon–Fri, no holidays)", working_days(a, b)),
                         ("In hours", ui.fi_num(abs(days) * 24, 0))])
        elif k == 1:
            base = parse_date(ui.ask("Date", "today"))
            n = ui.ask_int("Amount (negative subtracts)", 30)
            unit = ui.choose("Unit", ["days", "weeks", "months", "years"])
            res = (base + dt.timedelta(days=n) if unit == 0 else base + dt.timedelta(weeks=n) if unit == 1
                   else add_months(base, n) if unit == 2 else add_months(base, 12 * n))
            print(ui.bold(f"  {FI_WEEKDAYS[res.weekday()]} {fi_date(res)}"))
        elif k == 2:
            d = parse_date(ui.ask("Date", "today"))
            iso = d.isocalendar()
            ui.print_kv([("Weekday", FI_WEEKDAYS[d.weekday()]), ("Week number", iso[1]),
                         ("Day of the year", f"{d.timetuple().tm_yday}. / {366 if calendar.isleap(d.year) else 365}"),
                         ("Leap year", "yes" if calendar.isleap(d.year) else "no")])
        elif k == 3:
            born = parse_date(ui.ask("Date of birth (YYYY-MM-DD)"))
            today = dt.date.today()
            y, m, d = months_between(born, today)
            days = (today - born).days
            nxt = born.replace(year=today.year) if (born.month, born.day) != (2, 29) else dt.date(today.year, 3, 1)
            if nxt < today:
                nxt = nxt.replace(year=today.year + 1)
            milestone = ((days // 1000) + 1) * 1000
            ui.print_kv([("Age", f"{y} years {m} months {d} days"), ("Days lived", ui.fi_num(days, 0)),
                         ("Hours lived (approx.)", ui.fi_num(days * 24, 0)), ("Born on a", FI_WEEKDAYS[born.weekday()]),
                         ("Next birthday", f"{fi_date(nxt)} (in {(nxt - today).days} days)"),
                         (f"{ui.fi_num(milestone, 0)} days celebration", fi_date(born + dt.timedelta(days=milestone)))])
        else:
            n = ui.ask_int("Days", 100)
            res = dt.date.today() + dt.timedelta(days=n)
            print(ui.bold(f"  {FI_WEEKDAYS[res.weekday()]} {fi_date(res)} (week {res.isocalendar()[1]})"))
    except ValueError as exc:
        ui.error(str(exc))


@tool("convert", "convert-calendar", "Calendar", "Month or year view with week numbers and Finnish public holidays",
      ("kalenteri", "calendar", "holidays", "viikot"))
def calendar_tool() -> None:
    from .finnish import holidays

    today = dt.date.today()
    raw = ui.ask("Month and year (e.g. 12 2026) or a year (2026)", f"{today.month} {today.year}")
    parts = raw.split()
    try:
        if len(parts) == 1:
            year = int(parts[0])
            hol = holidays(year)
            hl = {d: n for d, (n, off) in hol.items()}
            for start in range(1, 13, 3):
                blocks = [month_calendar(year, m, hl) for m in range(start, start + 3)]
                for row in zip(*blocks):
                    print("   ".join(ui.pad(r, 27) for r in row))
                print()
            return
        month, year = int(parts[0]), int(parts[1])
    except ValueError:
        ui.error("Enter e.g. '12 2026'.")
        return
    hol = holidays(year)
    hl = {d: n for d, (n, _) in hol.items()}
    for line in month_calendar(year, month, hl):
        print("  " + line)
    for d, (name, off) in sorted(hol.items()):
        if d.month == month:
            print(f"  {ui.c(f'{d.year}-{d.month:02d}-{d.day:02d}', 'bright_red' if off else 'bright_blue')} {name}"
                  + (ui.gray(" (day off)") if off else ""))


@tool("convert", "convert-world-clock", "World clock and time zones", "What time is it in different cities, and converting a time between zones",
      ("time zone", "kello", "timezone", "world clock"))
def world_clock_tool() -> None:
    if not zoneinfo_ok():
        ui.warn("The time zone database is missing – daylight saving is ignored. Fix: pip install tzdata")
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for city, zone, _ in WORLD_CITIES:
        local = now.astimezone(get_zone(zone))
        off = local.utcoffset() or dt.timedelta()
        hours = off.total_seconds() / 3600
        day = "" if local.date() == now.astimezone(get_zone("Europe/Helsinki")).date() else (
            " (tomorrow)" if local.date() > now.astimezone(get_zone("Europe/Helsinki")).date() else " (yesterday)")
        rows.append((city, local.strftime("%H:%M") + day, f"UTC{'+' if hours >= 0 else ''}{hours:g}"))
    ui.table(rows, ["City", "Time", "Difference"])
    if ui.ask_yes_no("Convert a specific time?", False):
        names = [c for c, _, _ in WORLD_CITIES]
        src = WORLD_CITIES[ui.choose("From", names, 0)][1]
        tstr = ui.ask("Time (HH:MM)", "12:00")
        hh, mm = (int(x) for x in re.split(r"[:.]", tstr))
        base = dt.datetime.combine(dt.date.today(), dt.time(hh, mm), tzinfo=get_zone(src))
        for city, zone, _ in WORLD_CITIES:
            print(f"  {city.ljust(14)} {base.astimezone(get_zone(zone)):%H:%M}")


@tool("convert", "convert-roman-numerals", "Roman numerals", "MMXXVI ↔ 2026", ("roman", "roomalainen"))
def roman_tool() -> None:
    from .mathtools import roman

    raw = ui.ask("Number or Roman numeral", "2026")
    try:
        if raw.strip().isdigit():
            print(ui.bold(f"  {raw} = {roman(int(raw))}"))
        else:
            print(ui.bold(f"  {raw.upper()} = {roman_to_int(raw)}"))
    except ValueError as exc:
        ui.error(str(exc))


@tool("convert", "convert-data-formats", "Data formats", "CSV ↔ JSON, JSON formatting and validation, XML, INI, query string, Markdown table",
      ("json", "csv", "xml", "ini", "muotoile", "validoi"))
def formats_tool() -> None:
    kinds = ["CSV → JSON", "JSON → CSV", "JSON: format / validate", "JSON: minify to one line", "XML → formatted",
             "XML → JSON", "INI → JSON", "Query string ↔ JSON", "CSV → Markdown table"]
    k = ui.choose("Conversion", kinds)
    text = ui.get_text("Input")
    try:
        if k == 0:
            result = json.dumps(csv_to_json(text), ensure_ascii=False, indent=2)
        elif k == 1:
            result = json_to_csv(json.loads(text))
        elif k in (2, 3):
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:
                lines = text.splitlines()
                ui.error(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
                if 0 < exc.lineno <= len(lines):
                    print("  " + lines[exc.lineno - 1])
                    print("  " + " " * (exc.colno - 1) + ui.red("^"))
                return
            result = json.dumps(obj, ensure_ascii=False, indent=2 if k == 2 else None,
                                separators=None if k == 2 else (",", ":"))
            ui.success("The JSON is valid.")
        elif k == 4:
            result = xml.dom.minidom.parseString(text.encode()).toprettyxml(indent="  ")
            result = "\n".join(line for line in result.splitlines() if line.strip())
        elif k == 5:
            root = ET.fromstring(text)
            result = json.dumps({root.tag: xml_to_obj(root)}, ensure_ascii=False, indent=2)
        elif k == 6:
            cp = configparser.ConfigParser()
            cp.read_string(text)
            result = json.dumps({s: dict(cp[s]) for s in cp.sections()}, ensure_ascii=False, indent=2)
        elif k == 7:
            t = text.strip()
            if t.startswith("{"):
                result = urllib.parse.urlencode(json.loads(t), doseq=True)
            else:
                q = t.split("?", 1)[-1]
                parsed = urllib.parse.parse_qs(q, keep_blank_values=True)
                result = json.dumps({k_: v[0] if len(v) == 1 else v for k_, v in parsed.items()}, ensure_ascii=False, indent=2)
        else:
            result = csv_to_markdown(text)
    except (ValueError, ET.ParseError, configparser.Error, csv.Error) as exc:
        ui.error(f"Conversion failed: {exc}")
        return
    ui.paginate(result.splitlines())
    offer_copy(result)
    offer_save(result, "result.json" if k in (0, 2, 3, 5, 6) else "result.txt")


KITCHEN = [("wheat flour", 60), ("rye flour", 55), ("graham flour", 60), ("oat flakes", 35), ("sugar", 85),
           ("icing sugar", 55), ("brown sugar", 75), ("butter / margarine (melted)", 90), ("milk", 103), ("water", 100),
           ("cream", 100), ("honey / syrup", 140), ("rice", 85), ("cocoa powder", 40), ("salt", 125),
           ("potato starch", 70), ("almond (ground)", 40), ("raisins", 60), ("grated cheese", 40), ("baking powder", 85)]


@tool("convert", "convert-kitchen-measures", "Kitchen measures", "Decilitres to grams, US cups, spoons and oven temperatures",
      ("resepti", "dl", "gramma", "kuppi", "leivonta", "uuni"))
def kitchen_tool() -> None:
    k = ui.choose("Conversion", ["Decilitres ↔ grams", "US cups and spoons ↔ decilitres", "Oven temperature °F ↔ °C"])
    if k == 0:
        idx = ui.choose("Ingredient", [n for n, _ in KITCHEN])
        name, g_per_dl = KITCHEN[idx]
        if ui.choose("Direction", ["dl → g", "g → dl"]) == 0:
            dl = ui.ask_float("Decilitres", 1)
            print(ui.bold(f"  {fmt_num(dl)} dl of {name} ≈ {fmt_num(dl * g_per_dl)} g"))
        else:
            g = ui.ask_float("Grams", 100)
            print(ui.bold(f"  {fmt_num(g)} g of {name} ≈ {fmt_num(g / g_per_dl)} dl"))
        print(ui.gray("  Values are approximate – flours pack differently."))
    elif k == 1:
        rows = [("1 cup (US)", "2.37 dl"), ("3/4 cup", "1.8 dl"), ("2/3 cup", "1.6 dl"), ("1/2 cup", "1.2 dl"),
                ("1/3 cup", "0.8 dl"), ("1/4 cup", "0.6 dl"), ("1 tbsp", "15 ml = 1 tbsp"), ("1 tsp", "5 ml = 1 tsp"),
                ("1 fl oz", "30 ml"), ("1 stick butter", "113 g"), ("1 lb", "454 g"), ("1 oz", "28 g")]
        ui.table(rows, ["American", "Metric"])
        cups = ui.ask_float("Convert cups to decilitres (0 = skip)", 0)
        if cups:
            print(ui.bold(f"  {fmt_num(cups)} cup = {fmt_num(cups * 2.365882)} dl"))
    else:
        rows = [(f, round((f - 32) * 5 / 9)) for f in (250, 275, 300, 325, 350, 375, 400, 425, 450, 475)]
        ui.table([(f"{f} °F", f"{c} °C", f"gas {max(1, round((c - 121) / 14) + 1) if c > 121 else '½'}") for f, c in rows],
                 ["Fahrenheit", "Celsius", "Gas mark"])


@tool("convert", "convert-running-pace", "Running pace and race times", "Pace ↔ speed and predictions for 5 km, 10 km, half marathon, marathon",
      ("juoksu", "tahti", "pace", "maraton", "lenkki"))
def pace_tool() -> None:
    from ..core.utils import parse_duration

    k = ui.choose("Calculation", ["Distance and time → pace and speed", "Pace → speed", "Speed → pace"])

    def fmt_pace(sec_per_km: float) -> str:
        m, s = divmod(round(sec_per_km), 60)
        return f"{m}:{s:02d} min/km"

    def fmt_time(sec: float) -> str:
        h, rem = divmod(round(sec), 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    try:
        if k == 0:
            km = ui.ask_float("Distance (km)", 10)
            raw = ui.ask("Time (e.g. 52:30 or 1:45:00)", "50:00")
            parts = [int(p) for p in raw.split(":")]
            sec = parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1] if len(parts) == 2 else parse_duration(raw)
            pace = sec / km
            ui.print_kv([("Pace", fmt_pace(pace)), ("Speed", f"{fmt_num(km / sec * 3600)} km/h")])
            print(ui.c("\nPredictions (Riegel's formula):", "bold"))
            for name, dist in (("5 km", 5), ("10 km", 10), ("Half marathon", 21.0975), ("Marathon", 42.195)):
                t = sec * (dist / km) ** 1.06
                print(f"  {name.ljust(13)} {fmt_time(t).rjust(8)}   ({fmt_pace(t / dist)})")
        elif k == 1:
            raw = ui.ask("Pace min/km (e.g. 5:30)", "5:30")
            m, s = (int(x) for x in raw.split(":"))
            print(ui.bold(f"  {fmt_num(3600 / (m * 60 + s))} km/h"))
        else:
            kmh = ui.ask_float("Speed km/h", 12)
            print(ui.bold(f"  {fmt_pace(3600 / kmh)}"))
    except (ValueError, IndexError, ZeroDivisionError):
        ui.error("Check the input (time as mm:ss or h:mm:ss).")


@tool("convert", "convert-trip-cost", "Trip cost calculator", "How much a car trip costs on petrol or electricity, and per passenger",
      ("bensa", "polttoaine", "fuel consumption", "electric car", "matka"))
def trip_tool() -> None:
    km = ui.ask_float("Distance (km, round trip if needed)", 400, 0)
    kind = ui.choose("Power source", ["Petrol / diesel", "Electric"])
    if kind == 0:
        cons = ui.ask_float("Consumption (l/100 km)", 6.5, 0)
        price = ui.ask_float("Fuel price (€/l)", 1.85, 0)
        amount = km * cons / 100
        unit = "l"
    else:
        cons = ui.ask_float("Consumption (kWh/100 km)", 17, 0)
        price = ui.ask_float("Electricity price (€/kWh)", 0.25, 0)
        amount = km * cons / 100
        unit = "kWh"
    people = ui.ask_int("Passengers", 1, 1, 9)
    cost = amount * price
    ui.print_kv([("Total consumption", f"{fmt_num(amount)} {unit}"), ("Total cost", f"{ui.fi_num(cost)} €"),
                 ("Per person", f"{ui.fi_num(cost / people)} €"), ("Cost per kilometre", f"{ui.fi_num(cost / km * 100, 2)} c/km" if km else "-")])
