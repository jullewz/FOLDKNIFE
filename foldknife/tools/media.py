"""Images and audio without libraries: PNG read/write, EXIF, ASCII art, image editing, generators,
colour palettes, steganography, WAV synth, melodies, morse audio, speech synthesis and metronome."""
from __future__ import annotations

import array
import colorsys
import hashlib
import math
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import time
import wave
import zlib
from pathlib import Path
from typing import Callable, Optional

from ..core import ui
from ..core.registry import tool

# --------------------------------------------------------------------------
# Image model
# --------------------------------------------------------------------------


class Image:
    """Simple RGBA image: rows = list of bytearray rows (4 bytes / pixel)."""

    def __init__(self, width: int, height: int, rows: Optional[list[bytearray]] = None) -> None:
        self.width, self.height = width, height
        self.rows = rows if rows is not None else [bytearray(width * 4) for _ in range(height)]

    def get(self, x: int, y: int) -> tuple[int, int, int, int]:
        r = self.rows[y]
        i = x * 4
        return r[i], r[i + 1], r[i + 2], r[i + 3]

    def set(self, x: int, y: int, rgba: tuple[int, ...]) -> None:
        i = x * 4
        self.rows[y][i:i + 4] = bytes((*rgba[:3], rgba[3] if len(rgba) > 3 else 255))

    def copy(self) -> "Image":
        return Image(self.width, self.height, [bytearray(r) for r in self.rows])


# --------------------------------------------------------------------------
# PNG
# --------------------------------------------------------------------------

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if not data.startswith(PNG_SIG):
        raise ValueError("Not a PNG file.")
    pos, chunks = 8, []
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        chunks.append((ctype, data[pos + 8:pos + 8 + length]))
        pos += 12 + length
        if ctype == b"IEND":
            break
    return chunks


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter(raw: bytes, width_bytes: int, height: int, bpp: int) -> list[bytearray]:
    rows: list[bytearray] = []
    prev = bytearray(width_bytes)
    pos = 0
    for _ in range(height):
        ftype = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + width_bytes])
        pos += 1 + width_bytes
        if ftype == 1:
            for i in range(bpp, width_bytes):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            line = bytearray((a + b) & 0xFF for a, b in zip(line, prev))
        elif ftype == 3:
            for i in range(width_bytes):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(width_bytes):
                left = line[i - bpp] if i >= bpp else 0
                upleft = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, prev[i], upleft)) & 0xFF
        elif ftype != 0:
            raise ValueError(f"Unknown PNG filter {ftype}.")
        rows.append(line)
        prev = line
    return rows


def read_png(path: str | Path) -> Image:
    chunks = _png_chunks(Path(path).read_bytes())
    ihdr = next(d for t, d in chunks if t == b"IHDR")
    width, height, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    if interlace:
        raise ValueError("Interlaced PNGs aren't supported – save the image without interlacing.")
    palette = next((d for t, d in chunks if t == b"PLTE"), b"")
    trns = next((d for t, d in chunks if t == b"tRNS"), b"")
    raw = zlib.decompress(b"".join(d for t, d in chunks if t == b"IDAT"))
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bits_pp = channels * depth
    width_bytes = (width * bits_pp + 7) // 8
    bpp = max(1, bits_pp // 8)
    rows = _unfilter(raw, width_bytes, height, bpp)
    img = Image(width, height)
    maxv = (1 << depth) - 1
    for y, line in enumerate(rows):
        out = img.rows[y]
        if depth == 16:
            line = bytearray(line[i] for i in range(0, len(line), 2))
            d = 8
        else:
            d = depth
        if d < 8:
            vals = []
            for byte in line:
                for shift in range(8 - d, -1, -d):
                    vals.append((byte >> shift) & ((1 << d) - 1))
            vals = vals[:width * channels]
        else:
            vals = list(line)
        for x in range(width):
            if ctype == 0:
                v = vals[x]
                g = v * 255 // maxv if d < 8 else v
                a = 0 if trns and len(trns) >= 2 and v == struct.unpack(">H", trns[:2])[0] else 255
                rgba = (g, g, g, a)
            elif ctype == 2:
                rgba = (vals[x * 3], vals[x * 3 + 1], vals[x * 3 + 2], 255)
            elif ctype == 3:
                idx = vals[x]
                rgba = (palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2], trns[idx] if idx < len(trns) else 255)
            elif ctype == 4:
                rgba = (vals[x * 2], vals[x * 2], vals[x * 2], vals[x * 2 + 1])
            else:
                rgba = tuple(vals[x * 4:x * 4 + 4])  # type: ignore[assignment]
            out[x * 4:x * 4 + 4] = bytes(rgba)
    return img


def write_png(path: str | Path, width: int, height: int, rows: list[bytes], mode: str = "RGBA") -> Path:
    ctype = {"L": 0, "RGB": 2, "RGBA": 6}[mode]

    def chunk(t: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    out = PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, ctype, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    path = Path(path)
    path.write_bytes(out)
    return path


def save_image(img: Image, path: str | Path) -> Path:
    return write_png(path, img.width, img.height, [bytes(r) for r in img.rows], "RGBA")


# --------------------------------------------------------------------------
# BMP and PPM
# --------------------------------------------------------------------------

def read_bmp(path: str | Path) -> Image:
    data = Path(path).read_bytes()
    if data[:2] != b"BM":
        raise ValueError("Not a BMP file.")
    offset = struct.unpack("<I", data[10:14])[0]
    width, height = struct.unpack("<ii", data[18:26])
    bpp = struct.unpack("<H", data[28:30])[0]
    comp = struct.unpack("<I", data[30:34])[0]
    if bpp not in (24, 32) or comp not in (0, 3):
        raise ValueError("Only uncompressed 24/32-bit BMPs are supported.")
    top_down = height < 0
    height = abs(height)
    stride = (width * bpp // 8 + 3) & ~3
    img = Image(width, height)
    for row in range(height):
        y = row if top_down else height - 1 - row
        base = offset + row * stride
        out = img.rows[y]
        for x in range(width):
            i = base + x * (bpp // 8)
            b, g, r = data[i], data[i + 1], data[i + 2]
            a = data[i + 3] if bpp == 32 and comp == 3 else 255
            out[x * 4:x * 4 + 4] = bytes((r, g, b, a))
    return img


def read_ppm(path: str | Path) -> Image:
    data = Path(path).read_bytes()
    tokens = re.findall(rb"\S+", re.sub(rb"#[^\n]*", b"", data[:200]))
    if tokens[0] != b"P6":
        raise ValueError("Only binary PPM (P6) is supported.")
    width, height, maxval = int(tokens[1]), int(tokens[2]), int(tokens[3])
    header_end = data.index(tokens[3], 2) + len(tokens[3]) + 1
    pix = data[header_end:]
    img = Image(width, height)
    scale = 255 / maxval
    for y in range(height):
        out = img.rows[y]
        for x in range(width):
            i = (y * width + x) * 3
            out[x * 4:x * 4 + 4] = bytes((int(pix[i] * scale), int(pix[i + 1] * scale), int(pix[i + 2] * scale), 255))
    return img


def load_image(path: str | Path) -> Image:
    """Loads an image. Uses Pillow if installed (JPEG etc.), otherwise the built-in PNG/BMP/PPM reader."""
    path = Path(path)
    try:
        from PIL import Image as PILImage  # type: ignore[import-not-found]

        with PILImage.open(path) as im:
            im = im.convert("RGBA")
            w, h = im.size
            raw = im.tobytes()
            return Image(w, h, [bytearray(raw[y * w * 4:(y + 1) * w * 4]) for y in range(h)])
    except ImportError:
        pass
    head = path.read_bytes()[:8]
    if head.startswith(PNG_SIG):
        return read_png(path)
    if head.startswith(b"BM"):
        return read_bmp(path)
    if head.startswith(b"P6"):
        return read_ppm(path)
    if head.startswith(b"\xff\xd8"):
        raise ValueError("JPEG pixels need the Pillow library (pip install pillow) – or save the image as PNG.")
    raise ValueError("Unknown image format (supported: PNG, BMP, PPM; with Pillow also JPEG, GIF, WEBP).")


# --------------------------------------------------------------------------
# Image info and EXIF
# --------------------------------------------------------------------------

def image_size(path: str | Path) -> tuple[str, int, int]:
    data = Path(path).read_bytes()
    if data.startswith(PNG_SIG):
        w, h = struct.unpack(">II", data[16:24])
        return "PNG", w, h
    if data[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", data[6:10])
        return "GIF", w, h
    if data[:2] == b"BM":
        w, h = struct.unpack("<ii", data[18:26])
        return "BMP", w, abs(h)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return "WEBP", w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L":
            b = data[21:25]
            w = 1 + (((b[1] & 0x3F) << 8) | b[0])
            h = 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return "WEBP", w, h
        if kind == b"VP8X":
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            return "WEBP", w, h
    if data[:2] == b"\xff\xd8":
        pos = 2
        while pos < len(data) - 9:
            if data[pos] != 0xFF:
                pos += 1
                continue
            marker = data[pos + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                pos += 2
                continue
            length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[pos + 5:pos + 9])
                return "JPEG", w, h
            pos += 2 + length
    raise ValueError("Couldn't detect the image size.")


EXIF_TAGS = {0x010F: "Make", 0x0110: "Model", 0x0112: "Direction", 0x0131: "Software", 0x0132: "Modified",
             0x013B: "Artist", 0x8298: "Copyright", 0x9003: "Taken", 0x829A: "Exposure time", 0x829D: "Aperture (f)",
             0x8827: "ISO", 0x920A: "Focal length (mm)", 0xA434: "Lens", 0xA002: "Width", 0xA003: "Height",
             0x9209: "Flash", 0xA405: "Focal length 35 mm"}
GPS_TAGS = {1: "LatRef", 2: "Lat", 3: "LonRef", 4: "Lon", 5: "AltRef", 6: "Alt", 29: "Day"}
_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}


def _parse_ifd(tiff: bytes, offset: int, endian: str, names: dict[int, str]) -> tuple[dict[str, object], dict[int, int]]:
    out: dict[str, object] = {}
    pointers: dict[int, int] = {}
    if offset + 2 > len(tiff):
        return out, pointers
    count = struct.unpack(endian + "H", tiff[offset:offset + 2])[0]
    for i in range(count):
        e = offset + 2 + i * 12
        if e + 12 > len(tiff):
            break
        tag, typ, n = struct.unpack(endian + "HHI", tiff[e:e + 8])
        size = _TYPE_SIZE.get(typ, 1) * n
        data = tiff[e + 8:e + 12] if size <= 4 else tiff[struct.unpack(endian + "I", tiff[e + 8:e + 12])[0]:][:size]
        if tag in (0x8769, 0x8825):
            pointers[tag] = struct.unpack(endian + "I", tiff[e + 8:e + 12])[0]
            continue
        if tag not in names:
            continue
        try:
            if typ == 2:
                val: object = data[:n].split(b"\x00")[0].decode("utf-8", errors="replace").strip()
            elif typ == 3:
                vals = struct.unpack(endian + "H" * n, data[:2 * n])
                val = vals[0] if n == 1 else vals
            elif typ in (4, 9):
                vals = struct.unpack(endian + ("I" if typ == 4 else "i") * n, data[:4 * n])
                val = vals[0] if n == 1 else vals
            elif typ in (5, 10):
                fmt = "I" if typ == 5 else "i"
                nums = struct.unpack(endian + fmt * (2 * n), data[:8 * n])
                rats = [nums[k] / nums[k + 1] if nums[k + 1] else 0 for k in range(0, len(nums), 2)]
                val = rats[0] if n == 1 else rats
            else:
                val = data[:n]
        except struct.error:
            continue
        out[names[tag]] = val
    return out, pointers


def read_exif(path: str | Path) -> dict[str, object]:
    data = Path(path).read_bytes()
    if data[:2] != b"\xff\xd8":
        return {}
    pos = 2
    while pos < len(data) - 4:
        if data[pos] != 0xFF:
            break
        marker = data[pos + 1]
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if marker == 0xE1 and data[pos + 4:pos + 10] == b"Exif\x00\x00":
            tiff = data[pos + 10:pos + 2 + length]
            endian = "<" if tiff[:2] == b"II" else ">"
            ifd0 = struct.unpack(endian + "I", tiff[4:8])[0]
            info, ptrs = _parse_ifd(tiff, ifd0, endian, EXIF_TAGS)
            if 0x8769 in ptrs:
                sub, _ = _parse_ifd(tiff, ptrs[0x8769], endian, EXIF_TAGS)
                info.update(sub)
            if 0x8825 in ptrs:
                gps, _ = _parse_ifd(tiff, ptrs[0x8825], endian, GPS_TAGS)
                try:
                    def dms(v: object) -> float:
                        d, m, s = v  # type: ignore[misc]
                        return d + m / 60 + s / 3600
                    lat = dms(gps["Lat"]) * (-1 if str(gps.get("LatRef", "N")).startswith("S") else 1)
                    lon = dms(gps["Lon"]) * (-1 if str(gps.get("LonRef", "E")).startswith("W") else 1)
                    info["GPS location"] = f"{lat:.6f}, {lon:.6f}  (https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f})"
                    if "Alt" in gps:
                        info["Altitude (m)"] = round(float(gps["Alt"]), 1)  # type: ignore[arg-type]
                except (KeyError, TypeError, ValueError):
                    pass
            return info
        if marker == 0xDA:
            break
        pos += 2 + length
    return {}


def strip_metadata(src: str | Path, dst: str | Path) -> int:
    """Removes EXIF/XMP/IPTC data from a JPEG or text chunks from a PNG. Returns the number of removed parts."""
    data = Path(src).read_bytes()
    removed = 0
    if data.startswith(PNG_SIG):
        out = bytearray(PNG_SIG)
        pos = 8
        while pos < len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            ctype = data[pos + 4:pos + 8]
            if ctype in (b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"):
                removed += 1
            else:
                out += data[pos:pos + 12 + length]
            pos += 12 + length
        Path(dst).write_bytes(bytes(out))
        return removed
    if data[:2] != b"\xff\xd8":
        raise ValueError("JPEG and PNG images are supported.")
    out = bytearray(b"\xff\xd8")
    pos = 2
    while pos < len(data):
        if data[pos] != 0xFF:
            raise ValueError("Broken JPEG.")
        marker = data[pos + 1]
        if marker == 0xDA:
            out += data[pos:]
            break
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        segment = data[pos:pos + 2 + length]
        if marker in (0xE1, 0xED) or (0xE2 <= marker <= 0xEF and marker != 0xEE):
            removed += 1
        else:
            out += segment
        pos += 2 + length
    Path(dst).write_bytes(bytes(out))
    return removed


# --------------------------------------------------------------------------
# Image editing
# --------------------------------------------------------------------------

def resize(img: Image, new_w: int, new_h: int, smooth: bool = True) -> Image:
    out = Image(new_w, new_h)
    sx, sy = img.width / new_w, img.height / new_h
    for y in range(new_h):
        row = out.rows[y]
        fy = (y + 0.5) * sy - 0.5
        y0 = max(0, min(img.height - 1, int(math.floor(fy))))
        y1 = min(img.height - 1, y0 + 1)
        wy = fy - math.floor(fy) if smooth else 0
        for x in range(new_w):
            fx = (x + 0.5) * sx - 0.5
            x0 = max(0, min(img.width - 1, int(math.floor(fx))))
            if not smooth:
                row[x * 4:x * 4 + 4] = img.rows[min(img.height - 1, int(y * sy))][min(img.width - 1, int(x * sx)) * 4:][:4]
                continue
            x1 = min(img.width - 1, x0 + 1)
            wx = fx - math.floor(fx)
            a, b, c, d = img.get(x0, y0), img.get(x1, y0), img.get(x0, y1), img.get(x1, y1)
            row[x * 4:x * 4 + 4] = bytes(int(a[k] * (1 - wx) * (1 - wy) + b[k] * wx * (1 - wy) + c[k] * (1 - wx) * wy + d[k] * wx * wy)
                                         for k in range(4))
    return out


def map_pixels(img: Image, fn: Callable[[int, int, int, int], tuple[int, int, int, int]]) -> Image:
    out = Image(img.width, img.height)
    for y in range(img.height):
        src, dst = img.rows[y], out.rows[y]
        for x in range(img.width):
            i = x * 4
            dst[i:i + 4] = bytes(fn(src[i], src[i + 1], src[i + 2], src[i + 3]))
    return out


def clamp8(v: float) -> int:
    return 0 if v < 0 else 255 if v > 255 else int(v)


def grayscale(img: Image) -> Image:
    return map_pixels(img, lambda r, g, b, a: (int(0.299 * r + 0.587 * g + 0.114 * b),) * 3 + (a,))  # type: ignore[return-value]


def invert(img: Image) -> Image:
    return map_pixels(img, lambda r, g, b, a: (255 - r, 255 - g, 255 - b, a))


def sepia(img: Image) -> Image:
    return map_pixels(img, lambda r, g, b, a: (clamp8(r * .393 + g * .769 + b * .189), clamp8(r * .349 + g * .686 + b * .168),
                                               clamp8(r * .272 + g * .534 + b * .131), a))


def brightness_contrast(img: Image, brightness: float = 0, contrast: float = 1.0) -> Image:
    return map_pixels(img, lambda r, g, b, a: (clamp8((r - 128) * contrast + 128 + brightness),
                                               clamp8((g - 128) * contrast + 128 + brightness),
                                               clamp8((b - 128) * contrast + 128 + brightness), a))


def threshold(img: Image, level: int = 128) -> Image:
    return map_pixels(img, lambda r, g, b, a: ((255,) * 3 if 0.299 * r + 0.587 * g + 0.114 * b >= level else (0,) * 3) + (a,))  # type: ignore[return-value]


def flip(img: Image, horizontal: bool = True) -> Image:
    if not horizontal:
        return Image(img.width, img.height, [bytearray(r) for r in reversed(img.rows)])
    out = []
    for r in img.rows:
        px = [r[i:i + 4] for i in range(0, len(r), 4)]
        out.append(bytearray(b"".join(reversed(px))))
    return Image(img.width, img.height, out)


def rotate90(img: Image, clockwise: bool = True) -> Image:
    out = Image(img.height, img.width)
    for y in range(img.height):
        for x in range(img.width):
            nx, ny = (img.height - 1 - y, x) if clockwise else (y, img.width - 1 - x)
            out.rows[ny][nx * 4:nx * 4 + 4] = img.rows[y][x * 4:x * 4 + 4]
    return out


def crop(img: Image, x: int, y: int, w: int, h: int) -> Image:
    x, y = max(0, x), max(0, y)
    w, h = min(w, img.width - x), min(h, img.height - y)
    return Image(w, h, [bytearray(img.rows[yy][x * 4:(x + w) * 4]) for yy in range(y, y + h)])


def box_blur(img: Image, radius: int = 2) -> Image:
    def blur_rows(rows: list[bytearray], width: int) -> list[bytearray]:
        out = []
        for r in rows:
            new = bytearray(len(r))
            for c in range(4):
                vals = r[c::4]
                acc = sum(vals[0:min(width, radius + 1)])
                cnt = min(width, radius + 1)
                for x in range(width):
                    new[x * 4 + c] = acc // cnt
                    right, left = x + radius + 1, x - radius
                    if right < width:
                        acc += vals[right]
                        cnt += 1
                    if left >= 0:
                        acc -= vals[left]
                        cnt -= 1
            out.append(new)
        return out

    horiz = Image(img.width, img.height, blur_rows(img.rows, img.width))
    vert = rotate90(horiz)
    vert = Image(vert.width, vert.height, blur_rows(vert.rows, vert.width))
    return rotate90(vert, clockwise=False)


def pixelate(img: Image, block: int = 8) -> Image:
    small = resize(img, max(1, img.width // block), max(1, img.height // block), smooth=True)
    return resize(small, img.width, img.height, smooth=False)


# --------------------------------------------------------------------------
# Image to terminal
# --------------------------------------------------------------------------

ASCII_RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


def to_ascii(img: Image, width: int = 80, invert_ramp: bool = False, color: bool = False) -> list[str]:
    height = max(1, int(img.height / img.width * width * 0.5))
    small = resize(img, width, height)
    ramp = ASCII_RAMP if not invert_ramp else ASCII_RAMP[::-1]
    lines = []
    for y in range(height):
        out = []
        for x in range(width):
            r, g, b, a = small.get(x, y)
            lum = (0.299 * r + 0.587 * g + 0.114 * b) * a / 255
            ch = ramp[min(len(ramp) - 1, int(lum / 256 * len(ramp)))]
            out.append(ui.rgb(ch, r, g, b) if color else ch)
        lines.append("".join(out))
    return lines


def to_blocks(img: Image, width: int = 80) -> list[str]:
    height = max(2, int(img.height / img.width * width) // 2 * 2)
    small = resize(img, width, height)
    lines = []
    for y in range(0, height, 2):
        out = []
        for x in range(width):
            t, b = small.get(x, y), small.get(x, y + 1)
            out.append(f"\x1b[38;2;{t[0]};{t[1]};{t[2]};48;2;{b[0]};{b[1]};{b[2]}m▀")
        lines.append("".join(out) + "\x1b[0m")
    return lines


# --------------------------------------------------------------------------
# Generators and palettes
# --------------------------------------------------------------------------

def gradient_image(w: int, h: int, c1: tuple[int, int, int], c2: tuple[int, int, int], direction: str = "horizontal") -> Image:
    img = Image(w, h)
    for y in range(h):
        row = img.rows[y]
        for x in range(w):
            t = x / max(1, w - 1) if direction == "horizontal" else y / max(1, h - 1) if direction == "vertical" else (x + y) / max(1, w + h - 2)
            row[x * 4:x * 4 + 4] = bytes((int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t), int(c1[2] + (c2[2] - c1[2]) * t), 255))
    return img


def mandelbrot_image(w: int, h: int, max_iter: int = 64, on_row: Callable[[], None] | None = None) -> Image:
    img = Image(w, h)
    scale = 3.2 / w
    for y in range(h):
        row = img.rows[y]
        ci = (y - h / 2) * scale
        for x in range(w):
            cr = (x - w * 0.65) * scale
            zr = zi = 0.0
            i = 0
            while zr * zr + zi * zi <= 4 and i < max_iter:
                zr, zi = zr * zr - zi * zi + cr, 2 * zr * zi + ci
                i += 1
            if i == max_iter:
                rgb = (0, 0, 0)
            else:
                smooth = i + 1 - math.log(max(1e-9, math.log(max(1e-9, math.sqrt(zr * zr + zi * zi))))) / math.log(2)
                r, g, b = colorsys.hsv_to_rgb((0.6 + smooth / max_iter * 2) % 1, 0.8, 1.0)
                rgb = (int(r * 255), int(g * 255), int(b * 255))
            row[x * 4:x * 4 + 4] = bytes((*rgb, 255))
        if on_row:
            on_row()
    return img


def identicon(text: str, size: int = 250, grid: int = 5) -> Image:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    hue = digest[0] / 255
    r, g, b = colorsys.hls_to_rgb(hue, 0.5, 0.65)
    color = (int(r * 255), int(g * 255), int(b * 255))
    bg = (240, 240, 240)
    cells = [[False] * grid for _ in range(grid)]
    half = (grid + 1) // 2
    bit = 0
    for y in range(grid):
        for x in range(half):
            on = (digest[1 + bit // 8] >> (bit % 8)) & 1 == 1
            cells[y][x] = cells[y][grid - 1 - x] = on
            bit += 1
    margin = size // 10
    cell = (size - 2 * margin) // grid
    img = Image(size, size)
    for y in range(size):
        row = img.rows[y]
        for x in range(size):
            cx, cy = (x - margin) // cell, (y - margin) // cell
            on = 0 <= cx < grid and 0 <= cy < grid and x >= margin and y >= margin and cells[cy][cx]
            row[x * 4:x * 4 + 4] = bytes((*(color if on else bg), 255))
    return img


def plasma(w: int, h: int, seed: int = 0) -> Image:
    rng = random.Random(seed)
    a, b, c = rng.uniform(0.02, 0.06), rng.uniform(0.02, 0.06), rng.uniform(0.01, 0.04)
    img = Image(w, h)
    for y in range(h):
        row = img.rows[y]
        for x in range(w):
            v = math.sin(x * a) + math.sin(y * b) + math.sin((x + y) * c) + math.sin(math.hypot(x - w / 2, y - h / 2) * a)
            r, g, bb = colorsys.hsv_to_rgb((v / 8 + 0.5) % 1, 0.75, 1)
            row[x * 4:x * 4 + 4] = bytes((int(r * 255), int(g * 255), int(bb * 255), 255))
    return img


def dominant_colors(img: Image, k: int = 6, iterations: int = 12, seed: int = 1) -> list[tuple[tuple[int, int, int], float]]:
    rng = random.Random(seed)
    step = max(1, int(math.sqrt(img.width * img.height / 6000)))
    pixels = [img.get(x, y)[:3] for y in range(0, img.height, step) for x in range(0, img.width, step) if img.get(x, y)[3] > 128]
    if not pixels:
        return []
    centers = rng.sample(pixels, min(k, len(pixels)))
    assign = [0] * len(pixels)
    for _ in range(iterations):
        for i, p in enumerate(pixels):
            assign[i] = min(range(len(centers)), key=lambda c: (p[0] - centers[c][0]) ** 2 + (p[1] - centers[c][1]) ** 2 + (p[2] - centers[c][2]) ** 2)
        new = []
        for c in range(len(centers)):
            members = [pixels[i] for i in range(len(pixels)) if assign[i] == c]
            if members:
                new.append(tuple(sum(m[j] for m in members) // len(members) for j in range(3)))
            else:
                new.append(rng.choice(pixels))
        centers = new  # type: ignore[assignment]
    counts = [assign.count(c) for c in range(len(centers))]
    total = len(pixels)
    return sorted(((tuple(centers[c]), counts[c] / total) for c in range(len(centers))), key=lambda t: -t[1])  # type: ignore[misc]


# --------------------------------------------------------------------------
# Steganography (LSB)
# --------------------------------------------------------------------------

STEG_MAGIC = b"FKST"


def steg_capacity(img: Image) -> int:
    return img.width * img.height * 3 // 8 - len(STEG_MAGIC) - 4


def steg_hide(img: Image, message: str) -> Image:
    payload = message.encode("utf-8")
    data = STEG_MAGIC + struct.pack(">I", len(payload)) + payload
    if len(data) * 8 > img.width * img.height * 3:
        raise ValueError(f"The message is too long – the image fits {steg_capacity(img)} bytes.")
    out = img.copy()
    bits = ((byte >> (7 - i)) & 1 for byte in data for i in range(8))
    for y in range(out.height):
        row = out.rows[y]
        for x in range(out.width):
            for c in range(3):
                try:
                    bit = next(bits)
                except StopIteration:
                    return out
                i = x * 4 + c
                row[i] = (row[i] & 0xFE) | bit
    return out


def steg_reveal(img: Image) -> Optional[str]:
    def bit_stream():  # type: ignore[no-untyped-def]
        for y in range(img.height):
            row = img.rows[y]
            for x in range(img.width):
                for c in range(3):
                    yield row[x * 4 + c] & 1

    stream = bit_stream()

    def read_bytes(n: int) -> bytes:
        out = bytearray()
        for _ in range(n):
            v = 0
            for _ in range(8):
                v = (v << 1) | next(stream)
            out.append(v)
        return bytes(out)

    try:
        if read_bytes(4) != STEG_MAGIC:
            return None
        length = struct.unpack(">I", read_bytes(4))[0]
        if length > img.width * img.height:
            return None
        return read_bytes(length).decode("utf-8", errors="replace")
    except StopIteration:
        return None


# --------------------------------------------------------------------------
# Audio
# --------------------------------------------------------------------------

SAMPLE_RATE = 44100
NOTE_OFFSETS = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2, "H": 2}


def note_freq(note: str) -> float:
    m = re.fullmatch(r"([A-Ha-h])([#b]?)(-?\d)", note.strip())
    if not m:
        raise ValueError(f"Unknown note: {note} (e.g. C4, F#5, Bb3)")
    semis = NOTE_OFFSETS[m.group(1).upper()] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)
    semis += (int(m.group(3)) - 4) * 12
    return 440.0 * 2 ** (semis / 12)


def synth(freq: float, duration: float, wave_type: str = "sine", volume: float = 0.5, sr: int = SAMPLE_RATE,
          fade: float = 0.01) -> array.array:
    n = int(duration * sr)
    out = array.array("h")
    amp = 32767 * max(0.0, min(1.0, volume))
    fade_n = max(1, int(fade * sr))
    rng = random.Random(0)
    for i in range(n):
        t = i / sr
        phase = (t * freq) % 1.0
        if wave_type == "sine":
            v = math.sin(2 * math.pi * phase)
        elif wave_type == "square":
            v = 1.0 if phase < 0.5 else -1.0
        elif wave_type == "saw":
            v = 2 * phase - 1
        elif wave_type == "triangle":
            v = 4 * abs(phase - 0.5) - 1
        else:
            v = rng.uniform(-1, 1)
        env = min(1.0, i / fade_n, (n - i) / fade_n)
        out.append(int(v * amp * env))
    return out


def silence(duration: float, sr: int = SAMPLE_RATE) -> array.array:
    return array.array("h", bytes(int(duration * sr) * 2))


def write_wav(path: str | Path, samples: array.array, sr: int = SAMPLE_RATE, channels: int = 1) -> Path:
    path = Path(path)
    data = samples.tobytes() if sys.byteorder == "little" else _swap16(samples)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data)
    return path


def _swap16(samples: array.array) -> bytes:
    s = array.array("h", samples)
    s.byteswap()
    return s.tobytes()


def read_wav(path: str | Path) -> tuple[array.array, int, int]:
    """Returns (16-bit interleaved samples, sample rate, channels)."""
    with wave.open(str(path), "rb") as w:
        ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 2:
        s = array.array("h")
        s.frombytes(raw)
        if sys.byteorder != "little":
            s.byteswap()
    elif width == 1:
        s = array.array("h", ((b - 128) << 8 for b in raw))
    elif width == 3:
        s = array.array("h", (int.from_bytes(raw[i + 1:i + 3], "little", signed=True) for i in range(0, len(raw), 3)))
    elif width == 4:
        s = array.array("h", (int.from_bytes(raw[i:i + 4], "little", signed=True) >> 16 for i in range(0, len(raw), 4)))
    else:
        raise ValueError("Unknown sample size.")
    return s, sr, ch


def melody(notes: str, bpm: int = 120, wave_type: str = "triangle", volume: float = 0.4) -> array.array:
    """Note notation: 'C4/4 D4/4 E4/2 R/4' (/4 = quarter, /8 = eighth, R = rest, . dotted)."""
    beat = 60 / bpm
    out = array.array("h")
    for tok in notes.split():
        m = re.fullmatch(r"([A-Ha-hRr][#b]?-?\d?)(?:/(\d+)(\.)?)?", tok)
        if not m:
            raise ValueError(f"I don't understand: {tok}")
        length = 4 / int(m.group(2) or 4) * beat * (1.5 if m.group(3) else 1)
        if m.group(1).upper().startswith("R"):
            out.extend(silence(length))
        else:
            out.extend(synth(note_freq(m.group(1)), length * 0.92, wave_type, volume))
            out.extend(silence(length * 0.08))
    return out


MELODIES = {
    "Ukko Nooa (Finnish folk song)": "C4/4 C4/4 C4/4 E4/4 D4/4 D4/4 D4/4 F4/4 E4/4 E4/4 D4/4 D4/4 C4/2 R/4 "
                 "E4/4 E4/4 E4/4 E4/4 G4/4 F4/4 D4/4 D4/4 F4/4 F4/4 F4/4 F4/4 A4/4 G4/4 E4/4 E4/4 "
                 "C4/4 C4/4 C4/4 E4/4 D4/4 D4/4 D4/4 F4/4 E4/4 E4/4 D4/4 D4/4 C4/2",
    "Frère Jacques": "C4/4 D4/4 E4/4 C4/4 C4/4 D4/4 E4/4 C4/4 E4/4 F4/4 G4/2 E4/4 F4/4 G4/2 "
                    "G4/8 A4/8 G4/8 F4/8 E4/4 C4/4 G4/8 A4/8 G4/8 F4/8 E4/4 C4/4 C4/4 G3/4 C4/2 C4/4 G3/4 C4/2",
    "Twinkle Twinkle Little Star": "C4/4 C4/4 G4/4 G4/4 A4/4 A4/4 G4/2 F4/4 F4/4 E4/4 E4/4 D4/4 D4/4 C4/2 "
                            "G4/4 G4/4 F4/4 F4/4 E4/4 E4/4 D4/2 G4/4 G4/4 F4/4 F4/4 E4/4 E4/4 D4/2 "
                            "C4/4 C4/4 G4/4 G4/4 A4/4 A4/4 G4/2 F4/4 F4/4 E4/4 E4/4 D4/4 D4/4 C4/2",
    "Scale": "C4/8 D4/8 E4/8 F4/8 G4/8 A4/8 B4/8 C5/4 R/8 C5/8 B4/8 A4/8 G4/8 F4/8 E4/8 D4/8 C4/4",
    "Victory fanfare": "C4/8 E4/8 G4/8 C5/4. G4/8 C5/2",
}


def morse_wav(text: str, path: str | Path, wpm: int = 18, freq: float = 700) -> Path:
    from .text import morse_encode

    unit = 1.2 / wpm
    out = array.array("h")
    for ch in morse_encode(text):
        if ch == ".":
            out.extend(synth(freq, unit, "sine", 0.5, fade=0.004))
            out.extend(silence(unit))
        elif ch == "-":
            out.extend(synth(freq, unit * 3, "sine", 0.5, fade=0.004))
            out.extend(silence(unit))
        elif ch == " ":
            out.extend(silence(unit * 2))
        elif ch == "/":
            out.extend(silence(unit * 2))
    return write_wav(path, out)


def play_file(path: str | Path) -> bool:
    try:
        if os.name == "nt":
            import winsound

            winsound.PlaySound(str(path), winsound.SND_FILENAME)
            return True
        for cmd in (["afplay"], ["aplay", "-q"], ["paplay"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd + [str(path)], check=False)
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def speak(text: str, save_to: Optional[str] = None, voice: Optional[str] = None) -> bool:
    if os.name == "nt":
        safe = text.replace("'", "''")
        script = "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        if voice:
            script += f"$s.SelectVoice('{voice.replace(chr(39), chr(39) * 2)}'); "
        if save_to:
            script += f"$s.SetOutputToWaveFile('{str(Path(save_to).resolve()).replace(chr(39), chr(39) * 2)}'); "
        script += f"$s.Speak('{safe}')"
        return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True).returncode == 0
    if sys.platform == "darwin":
        cmd = ["say"] + (["-v", voice] if voice else []) + (["-o", save_to] if save_to else []) + [text]
        return subprocess.run(cmd).returncode == 0
    for prog in ("espeak-ng", "espeak"):
        if shutil.which(prog):
            cmd = [prog, "-v", voice or "en"] + (["-w", save_to] if save_to else []) + [text]
            return subprocess.run(cmd, capture_output=True).returncode == 0
    if shutil.which("spd-say") and not save_to:
        return subprocess.run(["spd-say", "-l", "en", text]).returncode == 0
    return False


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

def _ask_image() -> tuple[Path, Image]:
    path = ui.ask_path("Image (PNG, BMP; with Pillow also JPEG)", kind="file")
    with ui.Spinner("Reading the image"):
        img = load_image(path)
    ui.info(f"{img.width} × {img.height} pixels")
    return path, img


@tool("media", "media-image-info", "Image info and EXIF", "Size, format and the data the camera stored – including GPS location if present",
      ("exif", "metadata", "kuva", "gps", "kamera"))
def image_info_tool() -> None:
    path = ui.ask_path("Image", kind="file")
    try:
        fmt, w, h = image_size(path)
    except ValueError as exc:
        ui.error(str(exc))
        return
    rows: list[tuple[str, object]] = [("Format", fmt), ("Size", f"{w} × {h} px ({w * h / 1e6:.1f} Mpx)"),
                                      ("Aspect ratio", f"{w / math.gcd(w, h):g}:{h / math.gcd(w, h):g}" if w and h else "-"),
                                      ("File size", ui.fmt_bytes(path.stat().st_size))]
    exif = read_exif(path)
    for k, v in exif.items():
        if k == "Exposure time" and isinstance(v, float) and 0 < v < 1:
            v = f"1/{round(1 / v)} s"
        elif isinstance(v, float):
            v = round(v, 2)
        rows.append((k, v))
    ui.print_kv(rows)
    if "GPS location" in exif:
        ui.warn("The image contains a GPS location! Remove it before sharing (tool: Remove metadata).")
    elif fmt == "JPEG" and not exif:
        ui.info("The image has no EXIF data.")


@tool("media", "media-remove-metadata", "Remove metadata (EXIF/GPS)", "Removes location, camera and other hidden data from an image before sharing",
      ("exif", "gps", "yksityisyys", "metadata", "poista"))
def strip_tool() -> None:
    src = ui.ask_path("Image (JPEG or PNG)", kind="file")
    dst = Path(ui.ask("Save as", str(src.with_name(src.stem + "-clean" + src.suffix))))
    try:
        n = strip_metadata(src, dst)
    except ValueError as exc:
        ui.error(str(exc))
        return
    ui.success(f"Removed {n} metadata sections → {dst} ({ui.fmt_bytes(src.stat().st_size)} → {ui.fmt_bytes(dst.stat().st_size)})")


@tool("media", "media-image-to-ascii", "Image to terminal / ASCII art", "Show an image as colour blocks in the terminal or convert it to ASCII characters",
      ("ascii", "kuva", "terminaali", "taide"))
def ascii_tool() -> None:
    _, img = _ask_image()
    mode = ui.choose("Style", ["Colour blocks (most detailed)", "Coloured ASCII characters", "ASCII black and white (dark background)",
                               "ASCII black and white (light background)"], 0)
    width = ui.ask_int("Width in characters", min(100, ui.term_width() - 2), 10, 400)
    with ui.Spinner("Converting"):
        if mode == 0:
            lines = to_blocks(img, width) if ui.color_enabled() else to_ascii(img, width)
        else:
            lines = to_ascii(img, width, invert_ramp=mode == 3, color=mode == 1)
    for line in lines:
        print(line)
    if mode >= 2 and ui.ask_yes_no("Save as a text file?", False):
        target = Path(ui.ask("File", "ascii.txt"))
        target.write_text("\n".join(lines), encoding="utf-8")
        ui.success(f"Saved: {target.resolve()}")


@tool("media", "media-image-editor", "Image editor", "Resize, crop, rotate, mirror, greyscale, sepia, blur, pixelate and brightness",
      ("kuva", "resize", "rajaa", "suodatin", "editori"))
def image_edit_tool() -> None:
    path, img = _ask_image()
    ops = ["Resize", "Crop", "Rotate 90° clockwise", "Rotate 90° counter-clockwise", "Mirror horizontally",
           "Mirror vertically", "Greyscale", "Sepia", "Negative", "Blur", "Pixelate",
           "Brightness and contrast", "Threshold (pure black/white)"]
    while True:
        k = ui.choose_optional(f"Action ({img.width}×{img.height})", ops)
        if k is None:
            break
        with ui.Spinner("Processing"):
            if k == 0:
                pass
            elif k == 2:
                img = rotate90(img)
            elif k == 3:
                img = rotate90(img, clockwise=False)
            elif k == 4:
                img = flip(img, True)
            elif k == 5:
                img = flip(img, False)
            elif k == 6:
                img = grayscale(img)
            elif k == 7:
                img = sepia(img)
            elif k == 8:
                img = invert(img)
        if k == 0:
            w = ui.ask_int("New width", img.width // 2, 1, 10000)
            h = ui.ask_int("New height", max(1, round(img.height * w / img.width)), 1, 10000)
            with ui.Spinner("Scaling"):
                img = resize(img, w, h)
        elif k == 1:
            x, y = ui.ask_int("Left edge x", 0, 0, img.width - 1), ui.ask_int("Top edge y", 0, 0, img.height - 1)
            w, h = ui.ask_int("Width", img.width - x, 1), ui.ask_int("Height", img.height - y, 1)
            img = crop(img, x, y, w, h)
        elif k == 9:
            r = ui.ask_int("Radius", 3, 1, 50)
            with ui.Spinner("Blurring"):
                img = box_blur(img, r)
        elif k == 10:
            b = ui.ask_int("Block size", 10, 2, 200)
            with ui.Spinner("Pixelating"):
                img = pixelate(img, b)
        elif k == 11:
            br = ui.ask_float("Brightness (-255…255)", 20, -255, 255)
            ct = ui.ask_float("Contrast (0.5 = less, 1.5 = more)", 1.2, 0, 5)
            with ui.Spinner("Adjusting"):
                img = brightness_contrast(img, br, ct)
        elif k == 12:
            lvl = ui.ask_int("Threshold 0–255", 128, 0, 255)
            with ui.Spinner("Processing"):
                img = threshold(img, lvl)
        ui.success("Done.")
    target = Path(ui.ask("Save as PNG", str(path.with_name(path.stem + "-edited.png"))))
    save_image(img, target)
    ui.success(f"Saved: {target.resolve()}")


@tool("media", "media-image-generator", "Image generator", "Gradients, Mandelbrot images, plasma and an avatar from text (identicon)",
      ("generoi", "taustakuva", "avatar", "identicon", "fraktaali"))
def generator_tool() -> None:
    from .convert import parse_color

    k = ui.choose("Image", ["Gradient", "Mandelbrot fractal", "Plasma", "Avatar from text (identicon)"])
    try:
        if k == 0:
            w, h = ui.ask_int("Width", 1920, 1, 8000), ui.ask_int("Height", 1080, 1, 8000)
            c1, c2 = parse_color(ui.ask("Colour 1", "#ff6a00")), parse_color(ui.ask("Colour 2", "#ee0979"))
            direction = ["horizontal", "vertical", "diagonal"][ui.choose("Direction", ["Horizontal", "Vertical", "Diagonal"], 2)]
            with ui.Spinner("Drawing"):
                img = gradient_image(w, h, c1, c2, direction)
            name = "liukuvari.png"
        elif k == 1:
            w = ui.ask_int("Width", 800, 50, 4000)
            h = ui.ask_int("Height", 600, 50, 4000)
            it = ui.ask_int("Iterations (more = sharper, slower)", 64, 16, 1000)
            with ui.ProgressBar(h, "Counting") as pb:
                img = mandelbrot_image(w, h, it, pb.update)
            name = "mandelbrot.png"
        elif k == 2:
            w, h = ui.ask_int("Width", 800, 1, 4000), ui.ask_int("Height", 600, 1, 4000)
            with ui.Spinner("Drawing"):
                img = plasma(w, h, random.randint(0, 9999))
            name = "plasma.png"
        else:
            text = ui.ask("Text (e.g. a username)", "foldknife")
            img = identicon(text, ui.ask_int("Size (px)", 256, 32, 2048))
            name = f"avatar-{re.sub(r'[^a-z0-9]+', '-', text.lower()) or 'x'}.png"
    except ValueError as exc:
        ui.error(str(exc))
        return
    target = Path(ui.ask("Save", name))
    save_image(img, target)
    ui.success(f"Saved: {target.resolve()}")
    if ui.color_enabled() and ui.ask_yes_no("Show a preview in the terminal?", True):
        for line in to_blocks(img, min(80, ui.term_width() - 2)):
            print(line)


@tool("media", "media-image-colours", "Colours from an image", "Picks an image's dominant colours as HEX codes (k-means)", ("paletti", "colours", "palette", "hex"))
def palette_tool() -> None:
    _, img = _ask_image()
    k = ui.ask_int("How many colours", 6, 2, 16)
    with ui.Spinner("Analysing colours"):
        colors = dominant_colors(img, k)
    for rgb, share in colors:
        hexcode = "#{:02x}{:02x}{:02x}".format(*rgb)
        print(f"  {ui.bg_rgb('      ', *rgb)}  {hexcode}  rgb{rgb}  {share * 100:5.1f} %")


@tool("media", "media-steganography", "Hide a message in an image", "Hides text invisibly in a PNG image's pixels (LSB) and reads it back",
      ("steganografia", "salainen", "piilota", "lsb"))
def steg_tool() -> None:
    mode = ui.choose("Action", ["Hide a message", "Read a hidden message"])
    path, img = _ask_image()
    if mode == 0:
        ui.info(f"The image fits {steg_capacity(img)} bytes of text.")
        msg = ui.get_text("Secret message")
        try:
            with ui.Spinner("Hiding"):
                out = steg_hide(img, msg)
        except ValueError as exc:
            ui.error(str(exc))
            return
        target = Path(ui.ask("Save as PNG (not JPEG – it destroys the message)", str(path.with_name(path.stem + "-secret.png"))))
        save_image(out, target)
        ui.success(f"Message hidden: {target.resolve()}")
    else:
        with ui.Spinner("Looking for a message"):
            msg = steg_reveal(img)
        if msg is None:
            ui.warn("No message hidden with Foldknife was found in the image.")
        else:
            ui.box(msg.splitlines() or [""], title="Hidden message")


@tool("media", "media-tone-generator", "Tone generator", "Sine, square, saw, triangle or noise to a WAV file (test tones too)",
      ("sound", "wav", "taajuus", "tone", "syntetisaattori"))
def tone_tool() -> None:
    waves = ["sine", "square", "saw", "triangle", "noise"]
    wt = waves[ui.choose("Waveform", waves, 0)]
    freq = ui.ask_float("Frequency (Hz)", 440, 20, 20000) if wt != "noise" else 0
    dur = ui.ask_float("Duration (s)", 2, 0.05, 600)
    vol = ui.ask_float("Volume (0–1)", 0.4, 0, 1)
    sweep = wt != "noise" and ui.ask_yes_no("Frequency sweep to another frequency?", False)
    end = ui.ask_float("End frequency (Hz)", 2000, 20, 20000) if sweep else freq
    with ui.Spinner("Synthesising"):
        if sweep:
            samples = array.array("h")
            steps = 100
            for i in range(steps):
                f = freq * (end / freq) ** (i / steps)
                samples.extend(synth(f, dur / steps, wt, vol, fade=0.0005))
        else:
            samples = synth(freq, dur, wt, vol)
    target = Path(ui.ask("Save", f"{wt}-{int(freq)}hz.wav" if freq else "noise.wav"))
    write_wav(target, samples)
    ui.success(f"Saved: {target.resolve()}")
    if ui.ask_yes_no("Play it?", True) and not play_file(target):
        ui.warn("Playback failed – open the file in a media player.")


@tool("media", "media-melody-composer", "Melody composer", "Write notes (C4/4 D4/4 E4/2) or pick a ready folk song – makes a WAV",
      ("melodia", "nuotit", "musiikki", "melody", "wav"))
def melody_tool() -> None:
    names = list(MELODIES) + ["Your own melody"]
    idx = ui.choose("Melody", names, 0)
    if idx == len(MELODIES):
        print(ui.gray("E.g.: C4/4 E4/4 G4/4 C5/2 R/4   (/4 quarter, /8 eighth, R rest, F#4, Bb3, dot = dotted)"))
        notes = ui.ask("Notes")
    else:
        notes = MELODIES[names[idx]]
    bpm = ui.ask_int("Tempo (BPM)", 110, 30, 300)
    waves = ["triangle", "sine", "square", "saw"]
    wt = waves[ui.choose("Sound", ["Soft (triangle)", "Clean (sine)", "8-bit (square)", "Harsh (saw)"], 0)]
    try:
        with ui.Spinner("The composer is at work"):
            samples = melody(notes, bpm, wt)
    except ValueError as exc:
        ui.error(str(exc))
        return
    target = Path(ui.ask("Save", "melody.wav"))
    write_wav(target, samples)
    ui.success(f"Saved: {target.resolve()} ({len(samples) / SAMPLE_RATE:.1f} s)")
    if ui.ask_yes_no("Play it?", True) and not play_file(target):
        ui.warn("Playback failed – open the file in a media player.")


@tool("media", "media-wav-editor", "WAV editor", "Info, reverse, speed, volume, normalise and trim",
      ("wav", "sound", "audio", "leikkaa", "takaperin"))
def wav_tool() -> None:
    path = ui.ask_path("WAV file", kind="file")
    try:
        samples, sr, ch = read_wav(path)
    except (wave.Error, ValueError, EOFError) as exc:
        ui.error(f"Could not read the file: {exc}")
        return
    frames = len(samples) // ch
    peak = max((abs(s) for s in samples), default=0)
    ui.print_kv([("Duration", f"{frames / sr:.2f} s"), ("Sample rate", f"{sr} Hz"), ("Channels", ch),
                 ("Peak", f"{peak / 32768 * 100:.0f} % ({20 * math.log10(max(1, peak) / 32768):.1f} dBFS)")])
    k = ui.choose_optional("Edit", ["Reverse", "Speed up / slow down (also changes pitch)", "Volume",
                                       "Normalise (to maximum)", "Trim", "Convert to mono"])
    if k is None:
        return
    with ui.Spinner("Processing") if k in (0, 3, 5) else _nullctx():
        if k == 0:
            fr = [samples[i:i + ch] for i in range(0, len(samples), ch)]
            out = array.array("h", [v for f in reversed(fr) for v in f])
        elif k == 1:
            factor = ui.ask_float("Factor (2 = double speed, 0.5 = half)", 1.5, 0.1, 10)
            n_out = int(frames / factor)
            out = array.array("h")
            for i in range(n_out):
                pos = i * factor
                j = int(pos)
                t = pos - j
                for c in range(ch):
                    a = samples[min(frames - 1, j) * ch + c]
                    b = samples[min(frames - 1, j + 1) * ch + c]
                    out.append(int(a + (b - a) * t))
        elif k == 2:
            g = ui.ask_float("Factor (0.5 = quieter, 2 = louder)", 1.5, 0, 20)
            out = array.array("h", (max(-32768, min(32767, int(s * g))) for s in samples))
        elif k == 3:
            g = 32767 / max(1, peak)
            out = array.array("h", (int(s * g) for s in samples))
        elif k == 4:
            a = ui.ask_float("Start (s)", 0, 0, frames / sr)
            b = ui.ask_float("End (s)", frames / sr, a, frames / sr)
            out = samples[int(a * sr) * ch:int(b * sr) * ch]
        else:
            out = array.array("h", (sum(samples[i:i + ch]) // ch for i in range(0, len(samples), ch)))
            ch = 1
    target = Path(ui.ask("Save", str(path.with_name(path.stem + "-edited.wav"))))
    write_wav(target, out, sr, ch)
    ui.success(f"Saved: {target.resolve()}")


class _nullctx:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *a: object) -> None:
        return None


@tool("media", "media-text-to-speech", "Text to speech", "Reads text aloud (Windows, macOS or espeak voices) and can save it",
      ("tts", "puhe", "aloud", "lue", "speech"))
def tts_tool() -> None:
    text = ui.get_text("Text to read")
    voice = None
    if os.name == "nt" and ui.ask_yes_no("Show the installed voices?", False):
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer)."
                              "GetInstalledVoices() | % { $_.VoiceInfo.Name + ' (' + $_.VoiceInfo.Culture + ')' }"],
                             capture_output=True, text=True, errors="replace").stdout
        voices = [line.strip() for line in out.splitlines() if line.strip()]
        if voices:
            pick = ui.choose("Voice", voices)
            voice = voices[pick].rsplit(" (", 1)[0]
    save = ui.ask("Save to an audio file (empty = just read aloud)", allow_empty=True) or None
    with ui.Spinner("Speaking"):
        ok = speak(text, save, voice)
    if ok:
        ui.success("Done." + (f" Saved: {save}" if save else ""))
    else:
        ui.error("No speech synthesis found. On Linux: sudo apt install espeak-ng")


@tool("media", "media-metronome", "Metronome", "A beat at the chosen BPM or tap the tempo with Enter", ("metronomi", "bpm", "tempo", "rytmi"))
def metronome_tool() -> None:
    if ui.choose("Mode", ["Metronome", "Tap tempo"]) == 1:
        print(ui.gray("Press Enter in time at least 4 times, q + Enter quits."))
        taps = []
        while True:
            if input().strip().lower() == "q":
                break
            taps.append(time.perf_counter())
            if len(taps) >= 2:
                intervals = [b - a for a, b in zip(taps[-8:], taps[-7:])]
                avg = sum(intervals) / len(intervals)
                if avg > 0.05:
                    print(ui.bold(f"  ≈ {60 / avg:.0f} BPM"))
        return
    bpm = ui.ask_int("BPM", 100, 20, 400)
    beats = ui.ask_int("Beats per bar", 4, 1, 16)
    interval = 60 / bpm
    print(ui.gray("Ctrl+C stops."))
    n = 0
    next_t = time.perf_counter()
    try:
        while True:
            accent = n % beats == 0
            dots = "".join(ui.c("●", "bright_red" if i == 0 else "bright_yellow") if i == n % beats else ui.gray("○") for i in range(beats))
            print(f"\r  {dots}  {bpm} BPM ", end="", flush=True)
            if os.name == "nt":
                try:
                    import winsound

                    winsound.Beep(1500 if accent else 1000, 40)
                except Exception:  # noqa: BLE001
                    pass
            else:
                print("\a", end="", flush=True)
            n += 1
            next_t += interval
            time.sleep(max(0.0, next_t - time.perf_counter()))
    except KeyboardInterrupt:
        print()
