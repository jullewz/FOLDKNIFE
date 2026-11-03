"""QR code generator without libraries (ISO/IEC 18004): numeric, alphanumeric and byte modes,
versions 1–40, error correction levels L/M/Q/H, Reed–Solomon and mask selection by penalty score."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..core import ui
from ..core.registry import tool
from ..core.utils import offer_copy

Matrix = list[list[bool]]

ECL_INDEX = {"L": 0, "M": 1, "Q": 2, "H": 3}
ECL_FORMAT_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}

ECC_CODEWORDS_PER_BLOCK = [
    [-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
    [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28],
    [-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
    [-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
]
NUM_ERROR_CORRECTION_BLOCKS = [
    [-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25],
    [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49],
    [-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68],
    [-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81],
]

ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"


# --------------------------------------------------------------------------
# Reed–Solomon GF(256)
# --------------------------------------------------------------------------

def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z & 0xFF


def rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(len(result)):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < len(result):
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


# --------------------------------------------------------------------------
# Capacity and segments
# --------------------------------------------------------------------------

def raw_data_modules(ver: int) -> int:
    result = (16 * ver + 128) * ver + 64
    if ver >= 2:
        numalign = ver // 7 + 2
        result -= (25 * numalign - 10) * numalign - 55
        if ver >= 7:
            result -= 36
    return result


def data_codewords(ver: int, ecl: str) -> int:
    e = ECL_INDEX[ecl]
    return raw_data_modules(ver) // 8 - ECC_CODEWORDS_PER_BLOCK[e][ver] * NUM_ERROR_CORRECTION_BLOCKS[e][ver]


def _char_count_bits(mode: str, ver: int) -> int:
    idx = 0 if ver <= 9 else 1 if ver <= 26 else 2
    return {"numeric": (10, 12, 14), "alnum": (9, 11, 13), "byte": (8, 16, 16)}[mode][idx]


def make_segment(text: str) -> tuple[str, int, list[int]]:
    """Returns (mode, character count, data bits) for the best single mode."""
    bits: list[int] = []

    def put(value: int, n: int) -> None:
        bits.extend((value >> i) & 1 for i in reversed(range(n)))

    if text and text.isdigit() and text.isascii():
        for i in range(0, len(text), 3):
            chunk = text[i:i + 3]
            put(int(chunk), len(chunk) * 3 + 1)
        return "numeric", len(text), bits
    if text and all(ch in ALNUM for ch in text):
        for i in range(0, len(text) - 1, 2):
            put(ALNUM.index(text[i]) * 45 + ALNUM.index(text[i + 1]), 11)
        if len(text) % 2:
            put(ALNUM.index(text[-1]), 6)
        return "alnum", len(text), bits
    data = text.encode("utf-8")
    for b in data:
        put(b, 8)
    return "byte", len(data), bits


MODE_INDICATOR = {"numeric": 0x1, "alnum": 0x2, "byte": 0x4}


# --------------------------------------------------------------------------
# Building the QR code
# --------------------------------------------------------------------------

class QRCode:
    def __init__(self, version: int, ecl: str, codewords: list[int], mask: Optional[int] = None) -> None:
        self.version = version
        self.ecl = ecl
        self.size = version * 4 + 17
        self.modules: Matrix = [[False] * self.size for _ in range(self.size)]
        self.is_function = [[False] * self.size for _ in range(self.size)]
        self._draw_function_patterns()
        all_codewords = self._add_ecc_and_interleave(codewords)
        self._draw_codewords(all_codewords)
        if mask is None:
            best_penalty = None
            for m in range(8):
                self._apply_mask(m)
                self._draw_format_bits(m)
                p = self._penalty()
                if best_penalty is None or p < best_penalty:
                    mask, best_penalty = m, p
                self._apply_mask(m)  # XOR again = undo
        self.mask = mask
        self._apply_mask(mask)  # type: ignore[arg-type]
        self._draw_format_bits(mask)  # type: ignore[arg-type]

    # --- function patterns ---
    def _set_function(self, x: int, y: int, dark: bool) -> None:
        self.modules[y][x] = dark
        self.is_function[y][x] = True

    def _draw_function_patterns(self) -> None:
        for i in range(self.size):
            self._set_function(6, i, i % 2 == 0)
            self._set_function(i, 6, i % 2 == 0)
        self._draw_finder(3, 3)
        self._draw_finder(self.size - 4, 3)
        self._draw_finder(3, self.size - 4)
        pos = self._alignment_positions()
        n = len(pos)
        for i in range(n):
            for j in range(n):
                if (i == 0 and j == 0) or (i == 0 and j == n - 1) or (i == n - 1 and j == 0):
                    continue
                self._draw_alignment(pos[i], pos[j])
        self._draw_format_bits(0)
        self._draw_version()

    def _draw_finder(self, x: int, y: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                dist = max(abs(dx), abs(dy))
                xx, yy = x + dx, y + dy
                if 0 <= xx < self.size and 0 <= yy < self.size:
                    self._set_function(xx, yy, dist not in (2, 4))

    def _draw_alignment(self, x: int, y: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self._set_function(x + dx, y + dy, max(abs(dx), abs(dy)) != 1)

    def _alignment_positions(self) -> list[int]:
        if self.version == 1:
            return []
        numalign = self.version // 7 + 2
        step = 26 if self.version == 32 else (self.version * 4 + numalign * 2 + 1) // (numalign * 2 - 2) * 2
        result = [self.size - 7 - i * step for i in range(numalign - 1)] + [6]
        return sorted(result)

    def _draw_format_bits(self, mask: int) -> None:
        data = ECL_FORMAT_BITS[self.ecl] << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412

        def bit(i: int) -> bool:
            return ((bits >> i) & 1) != 0

        for i in range(6):
            self._set_function(8, i, bit(i))
        self._set_function(8, 7, bit(6))
        self._set_function(8, 8, bit(7))
        self._set_function(7, 8, bit(8))
        for i in range(9, 15):
            self._set_function(14 - i, 8, bit(i))
        for i in range(8):
            self._set_function(self.size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self._set_function(8, self.size - 15 + i, bit(i))
        self._set_function(8, self.size - 8, True)

    def _draw_version(self) -> None:
        if self.version < 7:
            return
        rem = self.version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = self.version << 12 | rem
        for i in range(18):
            dark = ((bits >> i) & 1) != 0
            a = self.size - 11 + i % 3
            b = i // 3
            self._set_function(a, b, dark)
            self._set_function(b, a, dark)

    # --- data ---
    def _add_ecc_and_interleave(self, data: list[int]) -> list[int]:
        e = ECL_INDEX[self.ecl]
        num_blocks = NUM_ERROR_CORRECTION_BLOCKS[e][self.version]
        ecc_len = ECC_CODEWORDS_PER_BLOCK[e][self.version]
        raw = raw_data_modules(self.version) // 8
        num_short = num_blocks - raw % num_blocks
        short_len = raw // num_blocks
        divisor = rs_divisor(ecc_len)
        blocks: list[list[int]] = []
        k = 0
        for i in range(num_blocks):
            length = short_len - ecc_len + (0 if i < num_short else 1)
            dat = data[k:k + length]
            k += length
            ecc = rs_remainder(dat, divisor)
            if i < num_short:
                dat = dat + [-1]  # placeholder for short blocks
            blocks.append(dat + ecc)
        result = []
        for i in range(len(blocks[0])):
            for j, blk in enumerate(blocks):
                if i != short_len - ecc_len or j >= num_short:
                    result.append(blk[i])
        return result

    def _draw_codewords(self, data: list[int]) -> None:
        i = 0
        total_bits = len(data) * 8
        right = self.size - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(self.size):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = self.size - 1 - vert if upward else vert
                    if not self.is_function[y][x] and i < total_bits:
                        self.modules[y][x] = ((data[i >> 3] >> (7 - (i & 7))) & 1) != 0
                        i += 1
            right -= 2

    def _apply_mask(self, mask: int) -> None:
        funcs = [
            lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
            lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
            lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
            lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
        ]
        f = funcs[mask]
        for y in range(self.size):
            row, frow = self.modules[y], self.is_function[y]
            for x in range(self.size):
                if not frow[x] and f(x, y):
                    row[x] = not row[x]

    def _penalty(self) -> int:
        size, m = self.size, self.modules
        score = 0
        lines = [m[y] for y in range(size)] + [[m[y][x] for y in range(size)] for x in range(size)]
        pat1 = [True, False, True, True, True, False, True, False, False, False, False]
        pat2 = pat1[::-1]
        for line in lines:
            run, prev = 0, None
            for v in line:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + run - 5
                    run, prev = 1, v
            if run >= 5:
                score += 3 + run - 5
            padded = [False] * 4 + list(line) + [False] * 4
            for i in range(len(padded) - 10):
                window = padded[i:i + 11]
                if window == pat1 or window == pat2:
                    score += 40
        for y in range(size - 1):
            for x in range(size - 1):
                c = m[y][x]
                if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    score += 3
        dark = sum(sum(row) for row in m)
        total = size * size
        k = (abs(dark * 20 - total * 10) + total - 1) // total - 1
        score += k * 10
        return score


def encode_text(text: str, ecl: str = "M", min_version: int = 1, mask: Optional[int] = None,
                boost: bool = True) -> Matrix:
    """Encodes text into a QR matrix (True = dark module)."""
    return encode(text, ecl, min_version, mask, boost).modules


def encode(text: str, ecl: str = "M", min_version: int = 1, mask: Optional[int] = None, boost: bool = True) -> QRCode:
    ecl = ecl.upper()
    if ecl not in ECL_INDEX:
        raise ValueError("Error correction level: L, M, Q or H.")
    mode, count, data_bits = make_segment(text)
    version = None
    for v in range(min_version, 41):
        needed = 4 + _char_count_bits(mode, v) + len(data_bits)
        if count < (1 << _char_count_bits(mode, v)) and needed <= data_codewords(v, ecl) * 8:
            version = v
            break
    if version is None:
        raise ValueError("The text is too long for a QR code (max about 2900 bytes at level L).")
    used = 4 + _char_count_bits(mode, version) + len(data_bits)
    if boost:
        for better in ("M", "Q", "H"):
            if ECL_INDEX[better] > ECL_INDEX[ecl] and used <= data_codewords(version, better) * 8:
                ecl = better
    bits: list[int] = []

    def put(value: int, n: int) -> None:
        bits.extend((value >> i) & 1 for i in reversed(range(n)))

    put(MODE_INDICATOR[mode], 4)
    put(count, _char_count_bits(mode, version))
    bits.extend(data_bits)
    capacity = data_codewords(version, ecl) * 8
    bits.extend([0] * min(4, capacity - len(bits)))
    bits.extend([0] * (-len(bits) % 8))
    pad = 0xEC
    while len(bits) < capacity:
        put(pad, 8)
        pad ^= 0xEC ^ 0x11
    codewords = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    return QRCode(version, ecl, codewords, mask)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def render_terminal(matrix: Matrix, border: int = 2, invert: bool | None = None) -> str:
    """With half block characters: two module rows per text line."""
    size = len(matrix)
    full = size + border * 2

    def dark(x: int, y: int) -> bool:
        x -= border
        y -= border
        return 0 <= x < size and 0 <= y < size and matrix[y][x]

    lines = []
    use_color = ui.color_enabled() and invert is None
    for y in range(0, full, 2):
        row = []
        for x in range(full):
            top, bottom = dark(x, y), dark(x, y + 1) if y + 1 < full else False
            if use_color:
                fg = "30" if top else "97"
                bg = "40" if bottom else "107"
                row.append(f"\x1b[{fg};{bg}m▀")
            else:
                if invert is False:
                    top, bottom = not top, not bottom
                light_top, light_bottom = not top, not bottom
                row.append("█" if light_top and light_bottom else "▀" if light_top else "▄" if light_bottom else " ")
        lines.append("".join(row) + ("\x1b[0m" if use_color else ""))
    return "\n".join(lines)


def to_svg(matrix: Matrix, border: int = 4, dark: str = "#000000", light: str = "#ffffff") -> str:
    size = len(matrix)
    parts = [f"M{x + border},{y + border}h1v1h-1z" for y in range(size) for x in range(size) if matrix[y][x]]
    full = size + border * 2
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {full} {full}" '
            f'shape-rendering="crispEdges">\n<rect width="100%" height="100%" fill="{light}"/>\n'
            f'<path d="{" ".join(parts)}" fill="{dark}"/>\n</svg>\n')


def to_png(matrix: Matrix, path: str | Path, scale: int = 10, border: int = 4,
           dark: tuple[int, int, int] = (0, 0, 0), light: tuple[int, int, int] = (255, 255, 255)) -> Path:
    from .media import write_png

    size = len(matrix)
    full = (size + border * 2) * scale
    rows = []
    for py in range(full):
        y = py // scale - border
        row = bytearray()
        for px in range(full):
            x = px // scale - border
            row += bytes(dark if 0 <= x < size and 0 <= y < size and matrix[y][x] else light)
        rows.append(bytes(row))
    return write_png(path, full, full, rows, "RGB")


def wifi_payload(ssid: str, password: str, security: str = "WPA", hidden: bool = False) -> str:
    def esc(s: str) -> str:
        return "".join("\\" + ch if ch in "\\;,:\"" else ch for ch in s)
    sec = security.upper() if password else "nopass"
    return f"WIFI:T:{sec};S:{esc(ssid)};P:{esc(password)};H:{'true' if hidden else 'false'};;"


def vcard_payload(name: str, phone: str = "", email: str = "", org: str = "", url: str = "") -> str:
    parts = name.split()
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:{parts[-1] if parts else ''};{' '.join(parts[:-1])}", f"FN:{name}"]
    if org:
        lines.append(f"ORG:{org}")
    if phone:
        lines.append(f"TEL:{phone}")
    if email:
        lines.append(f"EMAIL:{email}")
    if url:
        lines.append(f"URL:{url}")
    lines.append("END:VCARD")
    return "\n".join(lines)


@tool("media", "media-qr", "QR code generator", "Links, WiFi passwords, contacts and text as a QR code – to the terminal, PNG or SVG",
      ("qr", "qr-koodi", "wifi", "linkki", "viivakoodi"))
def qr_tool() -> None:
    kinds = ["Text or link", "WiFi network (guests join by scanning)", "Contact (vCard)", "Email",
             "Phone number", "Text message", "Location (coordinates)"]
    k = ui.choose("Payload", kinds)
    if k == 0:
        payload = ui.ask("Text / URL", "https://www.python.org")
    elif k == 1:
        ssid = ui.ask("Network name (SSID)")
        pw = ui.ask("Password (empty = open network)", allow_empty=True)
        payload = wifi_payload(ssid, pw, "WPA", ui.ask_yes_no("Hidden network?", False))
    elif k == 2:
        payload = vcard_payload(ui.ask("Name"), ui.ask("Phone", allow_empty=True), ui.ask("Email", allow_empty=True),
                                ui.ask("Organisation", allow_empty=True), ui.ask("Website", allow_empty=True))
    elif k == 3:
        from urllib.parse import quote

        payload = f"mailto:{ui.ask('Address')}?subject={quote(ui.ask('Subject', allow_empty=True))}&body={quote(ui.ask('Message', allow_empty=True))}"
    elif k == 4:
        payload = "tel:" + ui.ask("Number").replace(" ", "")
    elif k == 5:
        payload = f"SMSTO:{ui.ask('Number').replace(' ', '')}:{ui.ask('Message', allow_empty=True)}"
    else:
        payload = f"geo:{ui.ask_float('Latitude', 60.1699)},{ui.ask_float('Longitude', 24.9384)}"
    ecl = "LMQH"[ui.choose("Error correction", ["L (7 %)", "M (15 %, recommended)", "Q (25 %)", "H (30 %)"], 1)]
    try:
        qr = encode(payload, ecl)
    except ValueError as exc:
        ui.error(str(exc))
        return
    print()
    print(render_terminal(qr.modules))
    ui.info(f"Version {qr.version} ({qr.size}×{qr.size}), level {qr.ecl}, mask {qr.mask}, {len(payload.encode())} bytes")
    fmt = ui.choose_optional("Save as", ["PNG image", "SVG vector image"])
    if fmt == 0:
        path = to_png(qr.modules, ui.ask("File", "qr.png"), ui.ask_int("Module size in pixels", 10, 1, 50))
        ui.success(f"Saved: {Path(path).resolve()}")
    elif fmt == 1:
        target = Path(ui.ask("File", "qr.svg"))
        target.write_text(to_svg(qr.modules), encoding="utf-8")
        ui.success(f"Saved: {target.resolve()}")
    if k == 0:
        offer_copy(payload)
