"""Hashes, encodings, passwords, identifiers and encryption."""
from __future__ import annotations

import base64
import binascii
import codecs
import datetime as dt
import hashlib
import hmac
import html
import json
import math
import os
import quopri
import re
import secrets
import string
import time
import urllib.parse
import uuid
import zlib
from collections import Counter
from pathlib import Path
from typing import Callable

from ..core import ui
from ..core.registry import tool
from ..core.utils import offer_copy

# --------------------------------------------------------------------------
# Hashes
# --------------------------------------------------------------------------

ALGOS = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_256", "sha3_512",
         "blake2b", "blake2s", "crc32", "adler32"]


def hash_bytes(data: bytes, algo: str = "sha256") -> str:
    algo = algo.lower().replace("-", "_")
    if algo in ("sha3256", "sha3-256"):
        algo = "sha3_256"
    if algo == "crc32":
        return f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"
    if algo == "adler32":
        return f"{zlib.adler32(data) & 0xFFFFFFFF:08x}"
    try:
        return hashlib.new(algo, data).hexdigest()
    except ValueError as exc:
        raise ValueError(f"Unknown algorithm: {algo}. Options: {', '.join(ALGOS)}") from exc


def hash_file(path: str | Path, algo: str = "sha256",
              on_progress: Callable[[int], None] | None = None) -> str:
    algo = algo.lower().replace("-", "_")
    if algo in ("crc32", "adler32"):
        value = 0 if algo == "crc32" else 1
        fn = zlib.crc32 if algo == "crc32" else zlib.adler32
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                value = fn(block, value)
                if on_progress:
                    on_progress(len(block))
        return f"{value & 0xFFFFFFFF:08x}"
    try:
        h = hashlib.new(algo)
    except ValueError as exc:
        raise ValueError(f"Unknown algorithm: {algo}") from exc
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
            if on_progress:
                on_progress(len(block))
    return h.hexdigest()


def guess_algo(digest: str) -> str | None:
    return {8: "crc32", 32: "md5", 40: "sha1", 56: "sha224", 64: "sha256", 96: "sha384",
            128: "sha512"}.get(len(digest.strip()))


def identify_hash(value: str) -> list[str]:
    """Guesses a hash type from its format."""
    v = value.strip()
    prefixes = [("$2a$", "bcrypt"), ("$2b$", "bcrypt"), ("$2y$", "bcrypt"), ("$argon2id$", "Argon2id"),
                ("$argon2i$", "Argon2i"), ("$argon2d$", "Argon2d"), ("$6$", "SHA-512 crypt (Linux /etc/shadow)"),
                ("$5$", "SHA-256 crypt"), ("$1$", "MD5 crypt"), ("$apr1$", "Apache MD5"), ("$y$", "yescrypt"),
                ("$P$", "phpass (WordPress)"), ("$H$", "phpass (phpBB)"), ("pbkdf2_sha256$", "Django PBKDF2-SHA256"),
                ("pbkdf2_sha1$", "Django PBKDF2-SHA1"), ("sha1$", "Django SHA-1"), ("{SSHA}", "LDAP salted SHA-1"),
                ("{SHA}", "LDAP SHA-1"), ("scrypt:", "Werkzeug scrypt"), ("$scrypt$", "scrypt")]
    for prefix, name in prefixes:
        if v.startswith(prefix):
            return [name]
    if re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*", v) and v.startswith("eyJ"):
        return ["JWT token (not a hash) – decode it with the JWT tool"]
    if v.startswith("*") and re.fullmatch(r"\*[0-9A-Fa-f]{40}", v):
        return ["MySQL 4.1+ / MySQL5"]
    if re.fullmatch(r"[0-9a-fA-F]+", v):
        table = {8: ["CRC32", "Adler-32", "FNV-32"], 16: ["MySQL 3.23", "FNV-64", "half MD5"],
                 32: ["MD5", "NTLM", "MD4", "LM"], 40: ["SHA-1", "RIPEMD-160"], 48: ["Tiger-192"],
                 56: ["SHA-224", "SHA3-224"], 64: ["SHA-256", "SHA3-256", "BLAKE2s", "Keccak-256"],
                 96: ["SHA-384", "SHA3-384"], 128: ["SHA-512", "SHA3-512", "BLAKE2b", "Whirlpool"]}
        return table.get(len(v), [f"Unknown hex hash ({len(v)} chars = {len(v) * 4} bits)"])
    if re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", v):
        try:
            n = len(base64.b64decode(v + "=" * (-len(v) % 4)))
            names = {16: "MD5", 20: "SHA-1", 28: "SHA-224", 32: "SHA-256", 48: "SHA-384", 64: "SHA-512"}
            if n in names:
                return [f"{names[n]} in base64"]
        except binascii.Error:
            pass
    return ["Unknown format"]


# --------------------------------------------------------------------------
# Encodings
# --------------------------------------------------------------------------

def _b64pad(s: str) -> str:
    s = re.sub(r"\s+", "", s)
    return s + "=" * (-len(s) % 4)


def _rot47(s: str) -> str:
    return "".join(chr(33 + (ord(ch) - 33 + 47) % 94) if 33 <= ord(ch) <= 126 else ch for ch in s)


def _idna_encode(s: str) -> str:
    return ".".join(p.encode("idna").decode("ascii") if p else p for p in s.split("."))


def _idna_decode(s: str) -> str:
    return ".".join(p.encode("ascii").decode("idna") if p else p for p in s.split("."))


ENCODINGS: dict[str, tuple[Callable[[str], str], Callable[[str], str]]] = {
    "Base64": (lambda s: base64.b64encode(s.encode()).decode(),
               lambda s: base64.b64decode(_b64pad(s)).decode("utf-8", errors="replace")),
    "Base64 URL": (lambda s: base64.urlsafe_b64encode(s.encode()).decode().rstrip("="),
                   lambda s: base64.urlsafe_b64decode(_b64pad(s)).decode("utf-8", errors="replace")),
    "Base32": (lambda s: base64.b32encode(s.encode()).decode(),
               lambda s: base64.b32decode(re.sub(r"\s+", "", s).upper() + "=" * (-len(re.sub(r'\s+', '', s)) % 8)).decode("utf-8", errors="replace")),
    "Hex (Base16)": (lambda s: s.encode().hex(),
                       lambda s: bytes.fromhex(re.sub(r"[^0-9a-fA-F]", "", s)).decode("utf-8", errors="replace")),
    "Base85": (lambda s: base64.b85encode(s.encode()).decode(),
               lambda s: base64.b85decode(s.strip()).decode("utf-8", errors="replace")),
    "Ascii85": (lambda s: base64.a85encode(s.encode()).decode(),
                lambda s: base64.a85decode(s.strip()).decode("utf-8", errors="replace")),
    "URL encoding": (lambda s: urllib.parse.quote(s, safe=""), urllib.parse.unquote),
    "HTML entities": (lambda s: html.escape(s, quote=True), html.unescape),
    "Binary": (lambda s: " ".join(f"{b:08b}" for b in s.encode()),
                lambda s: bytes(int(x, 2) for x in s.split()).decode("utf-8", errors="replace")),
    "Decimal bytes": (lambda s: " ".join(str(b) for b in s.encode()),
                       lambda s: bytes(int(x) for x in re.split(r"[\s,]+", s.strip())).decode("utf-8", errors="replace")),
    "Octal": (lambda s: " ".join(f"{b:03o}" for b in s.encode()),
                lambda s: bytes(int(x, 8) for x in s.split()).decode("utf-8", errors="replace")),
    "Unicode-escape": (lambda s: s.encode("unicode_escape").decode("ascii"),
                       lambda s: codecs.decode(s, "unicode_escape")),
    "Punycode (IDN domain)": (_idna_encode, _idna_decode),
    "Quoted-printable": (lambda s: quopri.encodestring(s.encode()).decode(),
                         lambda s: quopri.decodestring(s.encode()).decode("utf-8", errors="replace")),
    "ROT13": (lambda s: codecs.encode(s, "rot13"), lambda s: codecs.encode(s, "rot13")),
    "ROT47": (_rot47, _rot47),
}


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------

AMBIGUOUS = set("Il1O0o|`'\";:,.")
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?/~"


def gen_password(length: int = 16, upper: bool = True, lower: bool = True, digits: bool = True,
                 symbols: bool = True, avoid_ambiguous: bool = False) -> str:
    pools = [p for p, use in ((string.ascii_lowercase, lower), (string.ascii_uppercase, upper),
                              (string.digits, digits), (SYMBOLS, symbols)) if use]
    if avoid_ambiguous:
        pools = ["".join(ch for ch in p if ch not in AMBIGUOUS) for p in pools]
    if not pools:
        raise ValueError("Choose at least one character group.")
    if length < len(pools):
        raise ValueError(f"The length must be at least {len(pools)}.")
    chars = [secrets.choice(p) for p in pools]
    alphabet = "".join(pools)
    chars += [secrets.choice(alphabet) for _ in range(length - len(pools))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


WORDS_FI = sorted(set("""
house car cat dog forest lake river sea island mountain cliff stone sand beach pier boat sail oar
fish pike perch salmon trout herring moose bear wolf fox hare squirrel hedgehog mole beaver otter lynx reindeer
cow horse sheep goat pig hen rooster duck goose swan eagle hawk owl crow magpie woodpecker sparrow robin
apple pear plum cherry berry banana lemon orange grape melon carrot potato onion garlic pepper tomato cucumber pumpkin
bread butter cheese milk coffee tea juice honey sugar salt soup pizza pancake cookie candy jam rice pasta
noodle cake muffin waffle bagel donut toast cereal red blue green yellow purple orange black white grey pink
brown silver golden violet amber crimson teal navy olive sun moon star cloud rain snow storm wind thunder
lightning frost ice fog rainbow sunset sunrise winter spring summer autumn morning evening night midnight noon today window
door roof floor wall chair table sofa lamp mirror carpet pillow blanket kettle spoon fork knife plate bowl
cup glass bottle basket bucket ladder hammer nail screw rope chain key lock clock watch phone radio camera
piano guitar violin drum flute trumpet song dance music poem story book page letter paper pencil marker crayon
brush paint canvas castle tower bridge road street village city harbour garden park field meadow valley canyon desert
jungle volcano glacier ocean wave pebble shell coral pearl diamond ruby emerald crystal rocket planet comet galaxy robot
dragon wizard knight pirate ninja viking giant dwarf elf troll fairy ghost happy brave clever quiet gentle lucky
sunny rapid silent mighty humble fancy cosy jolly proud wild calm bold swift jump run swim climb sing
laugh smile dream think build paint cook bake sail ride skate ski fly drive walk sauna cabin lantern
compass anchor feather candle saddle tractor bicycle scooter tram train ferry wagon sledge
""".split()))


def gen_passphrase(n_words: int = 5, sep: str = "-", capitalize: bool = True, add_number: bool = True,
                   ascii_only: bool = False) -> str:
    ws = [secrets.choice(WORDS_FI) for _ in range(n_words)]
    if ascii_only:
        ws = [w.translate(str.maketrans("äöåÄÖÅ", "aoaAOA")) for w in ws]
    if capitalize:
        ws = [w.capitalize() for w in ws]
    if add_number:
        idx = secrets.randbelow(len(ws))
        ws[idx] = ws[idx] + str(secrets.randbelow(100))
    return sep.join(ws)


COMMON_PASSWORDS = set("""
123456 password 123456789 qwerty salasana 111111 12345678 abc123 1234567 password1 12345 1234567890 123123
000000 iloveyou 1234 1q2w3e4r qwertyuiop 123 monkey dragon letmein football baseball sunshine princess admin
welcome master hello freedom whatever trustno1 starwars perkele kissa koira salasana1 qwerty123 asdfgh
zxcvbnm aaaaaa passw0rd summer winter kesä talvi suomi finland jokerit tappara kärpät hifk muumi
minecraft fortnite roblox pokemon batman superman charlie michael jordan23 shadow ninja azerty
""".split())

_SEQUENCES = ["abcdefghijklmnopqrstuvwxyzåäö", "0123456789", "qwertyuiopå", "asdfghjklöä", "zxcvbnm",
              "1qaz2wsx3edc", "qazwsxedc"]


def password_strength(pw: str) -> dict[str, object]:
    feedback: list[str] = []
    pool = 0
    if any(ch.islower() for ch in pw if ch.isascii()):
        pool += 26
    if any(ch.isupper() for ch in pw if ch.isascii()):
        pool += 26
    if any(ch.isdigit() for ch in pw):
        pool += 10
    if any(not ch.isalnum() and ch.isascii() for ch in pw):
        pool += 33
    if any(not ch.isascii() for ch in pw):
        pool += 40
    entropy = len(pw) * math.log2(pool) if pool else 0.0
    low = pw.lower()
    core = re.sub(r"[\d!?.@#$%&*_-]+$", "", low)
    if low in COMMON_PASSWORDS or core in COMMON_PASSWORDS:
        entropy = min(entropy, 10)
        feedback.append("This password is on the list of common passwords – change it now!")
    if re.search(r"(.)\1\1", pw):
        entropy *= 0.8
        feedback.append("The same character repeats many times in a row.")
    for seq in _SEQUENCES:
        for i in range(len(seq) - 3):
            chunk = seq[i:i + 4]
            if chunk in low or chunk[::-1] in low:
                entropy *= 0.75
                feedback.append(f"Contains a keyboard or alphabet sequence ({chunk}).")
                break
        else:
            continue
        break
    if re.fullmatch(r"\d+", pw):
        feedback.append("Only digits – add letters and special characters.")
    if re.search(r"(19|20)\d\d", pw):
        entropy *= 0.9
        feedback.append("A year is easy to guess.")
    if len(pw) < 12:
        feedback.append("Use at least 12 characters (preferably 16+).")
    if pool and pool < 60 and len(pw) < 16:
        feedback.append("Mix upper and lower case letters, digits and special characters.")
    if entropy < 28:
        score, label = 0, "Very weak"
    elif entropy < 40:
        score, label = 1, "Weak"
    elif entropy < 60:
        score, label = 2, "Fair"
    elif entropy < 80:
        score, label = 3, "Strong"
    else:
        score, label = 4, "Very strong"
    guesses = 2 ** entropy / 2
    return {"entropy": entropy, "score": score, "label": label, "feedback": feedback,
            "offline_fast": guesses / 1e10, "offline_slow": guesses / 1e4, "online": guesses / (100 / 3600)}


def fmt_crack_time(seconds: float) -> str:
    if seconds < 1:
        return "instantly"
    units = [(365.25 * 86400 * 1e9, "billion years"), (365.25 * 86400 * 1e6, "million years"),
             (365.25 * 86400 * 1000, "thousand years"), (365.25 * 86400, "years"), (86400 * 30, "months"),
             (86400, "days"), (3600, "hours"), (60, "minutes"), (1, "seconds")]
    for size, name in units:
        if seconds >= size:
            value = seconds / size
            if value > 1e6:
                return "forever"
            return f"{ui.fi_num(value, 0 if value >= 10 else 1)} {name}"
    return "instantly"


# --------------------------------------------------------------------------
# Identifiers
# --------------------------------------------------------------------------

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def uuid7() -> uuid.UUID:
    ms = int(time.time() * 1000)
    rand = secrets.randbits(74)
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= (rand >> 62) << 64
    value |= 0b10 << 62
    value |= rand & ((1 << 62) - 1)
    return uuid.UUID(int=value)


def ulid() -> str:
    value = (int(time.time() * 1000) << 80) | secrets.randbits(80)
    return "".join(CROCKFORD[(value >> (5 * i)) & 31] for i in reversed(range(26)))


def nanoid(size: int = 21, alphabet: str = string.ascii_letters + string.digits + "_-") -> str:
    return "".join(secrets.choice(alphabet) for _ in range(size))


def uuid_info(value: str) -> list[tuple[str, str]]:
    u = uuid.UUID(value.strip())
    rows = [("Normalised", str(u)), ("Version", str(u.version)), ("Variant", u.variant)]
    if u.version == 1:
        ts = (u.time - 0x01B21DD213814000) / 1e7
        rows.append(("Created", dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")))
        rows.append(("Device MAC/node", f"{u.node:012x}"))
    if u.version == 7:
        rows.append(("Created", dt.datetime.fromtimestamp((u.int >> 80) / 1000).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]))
    rows.append(("As an integer", str(u.int)))
    return rows


# --------------------------------------------------------------------------
# JWT and HMAC
# --------------------------------------------------------------------------

def jwt_decode(token: str) -> tuple[dict, dict, str]:
    parts = token.strip().split(".")
    if len(parts) < 2:
        raise ValueError("A JWT must have at least two dot-separated parts.")

    def dec(p: str) -> dict:
        return json.loads(base64.urlsafe_b64decode(_b64pad(p)).decode("utf-8"))

    return dec(parts[0]), dec(parts[1]), parts[2] if len(parts) > 2 else ""


# --------------------------------------------------------------------------
# Encryption (PBKDF2 + BLAKE2b keystream + HMAC-SHA256, encrypt-then-MAC)
# --------------------------------------------------------------------------

MAGIC = b"FKNIFE\x01\x00"  # must stay 8 bytes: offsets below are fixed
HEADER_LEN = len(MAGIC) + 4 + 16 + 16
TAG_LEN = 32
DEFAULT_ITERATIONS = 300_000
_CHUNK = 1 << 20


def _derive(password: str, salt: bytes, iterations: int) -> tuple[bytes, bytes]:
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=64)
    return key[:32], key[32:]


class _Keystream:
    def __init__(self, key: bytes, nonce: bytes) -> None:
        self.key, self.nonce, self.counter = key, nonce, 0
        self.buffer = b""

    def take(self, n: int) -> bytes:
        parts = [self.buffer]
        have = len(self.buffer)
        while have < n:
            block = hashlib.blake2b(self.nonce + self.counter.to_bytes(8, "big"), key=self.key, digest_size=64).digest()
            self.counter += 1
            parts.append(block)
            have += 64
        data = b"".join(parts)
        self.buffer = data[n:]
        return data[:n]

    def xor(self, data: bytes) -> bytes:
        if not data:
            return b""
        ks = self.take(len(data))
        return (int.from_bytes(data, "big") ^ int.from_bytes(ks, "big")).to_bytes(len(data), "big")


def encrypt_bytes(data: bytes, password: str, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(16)
    enc_key, mac_key = _derive(password, salt, iterations)
    header = MAGIC + iterations.to_bytes(4, "big") + salt + nonce
    ct = _Keystream(enc_key, nonce).xor(data)
    tag = hmac.new(mac_key, header + ct, hashlib.sha256).digest()
    return header + ct + tag


def decrypt_bytes(blob: bytes, password: str) -> bytes:
    if len(blob) < HEADER_LEN + TAG_LEN or not blob.startswith(MAGIC):
        raise ValueError("This isn't data encrypted with Foldknife.")
    iterations = int.from_bytes(blob[8:12], "big")
    salt, nonce = blob[12:28], blob[28:44]
    enc_key, mac_key = _derive(password, salt, iterations)
    header, ct, tag = blob[:HEADER_LEN], blob[HEADER_LEN:-TAG_LEN], blob[-TAG_LEN:]
    if not hmac.compare_digest(hmac.new(mac_key, header + ct, hashlib.sha256).digest(), tag):
        raise ValueError("Wrong password or the data is corrupted.")
    return _Keystream(enc_key, nonce).xor(ct)


def encrypt_file(src: Path, dst: Path, password: str, on_progress: Callable[[int], None] | None = None) -> None:
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(16)
    enc_key, mac_key = _derive(password, salt, DEFAULT_ITERATIONS)
    header = MAGIC + DEFAULT_ITERATIONS.to_bytes(4, "big") + salt + nonce
    mac = hmac.new(mac_key, header, hashlib.sha256)
    ks = _Keystream(enc_key, nonce)
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        fout.write(header)
        for block in iter(lambda: fin.read(_CHUNK), b""):
            ct = ks.xor(block)
            mac.update(ct)
            fout.write(ct)
            if on_progress:
                on_progress(len(block))
        fout.write(mac.digest())


def decrypt_file(src: Path, dst: Path, password: str, on_progress: Callable[[int], None] | None = None) -> None:
    size = src.stat().st_size
    with open(src, "rb") as fin:
        header = fin.read(HEADER_LEN)
        if len(header) < HEADER_LEN or not header.startswith(MAGIC) or size < HEADER_LEN + TAG_LEN:
            raise ValueError("This isn't a file encrypted with Foldknife.")
        iterations = int.from_bytes(header[8:12], "big")
        salt, nonce = header[12:28], header[28:44]
        enc_key, mac_key = _derive(password, salt, iterations)
        mac = hmac.new(mac_key, header, hashlib.sha256)
        remaining = size - HEADER_LEN - TAG_LEN
        while remaining > 0:  # 1st pass: verify integrity before decrypting
            block = fin.read(min(_CHUNK, remaining))
            mac.update(block)
            remaining -= len(block)
        tag = fin.read(TAG_LEN)
        if not hmac.compare_digest(mac.digest(), tag):
            raise ValueError("Wrong password or the file is corrupted.")
        fin.seek(HEADER_LEN)
        ks = _Keystream(enc_key, nonce)
        remaining = size - HEADER_LEN - TAG_LEN
        with open(dst, "wb") as fout:
            while remaining > 0:
                block = fin.read(min(_CHUNK, remaining))
                fout.write(ks.xor(block))
                remaining -= len(block)
                if on_progress:
                    on_progress(len(block))


def encrypt_text(text: str, password: str) -> str:
    return "PKS1:" + base64.b64encode(encrypt_bytes(text.encode("utf-8"), password)).decode()


def decrypt_text(token: str, password: str) -> str:
    token = token.strip()
    if token.startswith("PKS1:"):
        token = token[5:]
    try:
        blob = base64.b64decode(_b64pad(token))
    except binascii.Error as exc:
        raise ValueError("Invalid encrypted message.") from exc
    return decrypt_bytes(blob, password).decode("utf-8")


# --------------------------------------------------------------------------
# Classical ciphers
# --------------------------------------------------------------------------

EN_ALPHA = string.ascii_lowercase
FI_ALPHA = string.ascii_lowercase + "åäö"


def caesar(text: str, shift: int, alphabet: str = EN_ALPHA) -> str:
    n = len(alphabet)
    out = []
    for ch in text:
        low = ch.lower()
        if low in alphabet:
            new = alphabet[(alphabet.index(low) + shift) % n]
            out.append(new.upper() if ch.isupper() else new)
        else:
            out.append(ch)
    return "".join(out)


def vigenere(text: str, key: str, decrypt: bool = False, alphabet: str = EN_ALPHA) -> str:
    key_idx = [alphabet.index(k) for k in key.lower() if k in alphabet]
    if not key_idx:
        raise ValueError("The key must contain letters.")
    out, j, n = [], 0, len(alphabet)
    for ch in text:
        low = ch.lower()
        if low in alphabet:
            shift = key_idx[j % len(key_idx)] * (-1 if decrypt else 1)
            new = alphabet[(alphabet.index(low) + shift) % n]
            out.append(new.upper() if ch.isupper() else new)
            j += 1
        else:
            out.append(ch)
    return "".join(out)


def atbash(text: str, alphabet: str = EN_ALPHA) -> str:
    rev = alphabet[::-1]
    out = []
    for ch in text:
        low = ch.lower()
        if low in alphabet:
            new = rev[alphabet.index(low)]
            out.append(new.upper() if ch.isupper() else new)
        else:
            out.append(ch)
    return "".join(out)


def affine(text: str, a: int, b: int, decrypt: bool = False) -> str:
    if math.gcd(a, 26) != 1:
        raise ValueError("a must be coprime with 26 (1,3,5,7,9,11,15,17,19,21,23,25).")
    inv = pow(a, -1, 26)
    out = []
    for ch in text:
        if ch.lower() in EN_ALPHA:
            x = EN_ALPHA.index(ch.lower())
            y = (inv * (x - b)) % 26 if decrypt else (a * x + b) % 26
            out.append(EN_ALPHA[y].upper() if ch.isupper() else EN_ALPHA[y])
        else:
            out.append(ch)
    return "".join(out)


def rail_fence(text: str, rails: int, decrypt: bool = False) -> str:
    if rails < 2:
        return text
    pattern = list(range(rails)) + list(range(rails - 2, 0, -1))
    idx = [pattern[i % len(pattern)] for i in range(len(text))]
    if not decrypt:
        return "".join(ch for r in range(rails) for ch, k in zip(text, idx) if k == r)
    order = sorted(range(len(text)), key=lambda i: (idx[i], i))
    result = [""] * len(text)
    for ch, pos in zip(text, order):
        result[pos] = ch
    return "".join(result)


def xor_hex(text: str, key: str) -> str:
    data, k = text.encode(), key.encode()
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data)).hex()


def xor_unhex(hexstr: str, key: str) -> str:
    data, k = bytes.fromhex(re.sub(r"\s+", "", hexstr)), key.encode()
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data)).decode("utf-8", errors="replace")


def bacon(text: str) -> str:
    return " ".join(format(EN_ALPHA.index(ch), "05b").replace("0", "A").replace("1", "B")
                    for ch in text.lower() if ch in EN_ALPHA)


def unbacon(code: str) -> str:
    groups = re.findall(r"[ABab]{5}", code)
    return "".join(EN_ALPHA[int(g.upper().replace("A", "0").replace("B", "1"), 2)] for g in groups
                   if int(g.upper().replace("A", "0").replace("B", "1"), 2) < 26)


POLYBIUS = "abcdefghiklmnopqrstuvwxyz"  # i and j share a square


def polybius(text: str) -> str:
    out = []
    for ch in text.lower().replace("j", "i"):
        if ch in POLYBIUS:
            r, c = divmod(POLYBIUS.index(ch), 5)
            out.append(f"{r + 1}{c + 1}")
        elif ch == " ":
            out.append("/")
    return " ".join(out)


def unpolybius(code: str) -> str:
    out = []
    for tok in code.split():
        if tok == "/":
            out.append(" ")
        elif re.fullmatch(r"[1-5][1-5]", tok):
            out.append(POLYBIUS[(int(tok[0]) - 1) * 5 + int(tok[1]) - 1])
    return "".join(out)


FREQ_EN = dict(zip(EN_ALPHA, [8.2, 1.5, 2.8, 4.3, 12.7, 2.2, 2.0, 6.1, 7.0, 0.15, 0.8, 4.0, 2.4, 6.7, 7.5, 1.9,
                              0.1, 6.0, 6.3, 9.1, 2.8, 1.0, 2.4, 0.15, 2.0, 0.07]))
FREQ_FI = dict(zip(FI_ALPHA, [12.2, 0.3, 0.3, 1.0, 8.0, 0.2, 0.1, 1.8, 10.8, 2.0, 5.0, 5.8, 3.3, 8.8, 5.6, 1.7,
                              0.01, 2.9, 7.9, 9.8, 5.0, 2.5, 0.1, 0.03, 1.7, 0.05, 0.01, 3.6, 0.4]))


def chi_score(text: str, freq: dict[str, float]) -> float:
    letters = [ch for ch in text.lower() if ch in freq]
    if not letters:
        return float("inf")
    counts = Counter(letters)
    n = len(letters)
    return sum((counts.get(ch, 0) - n * p / 100) ** 2 / (n * p / 100) for ch, p in freq.items())


def crack_caesar(text: str, finnish: bool = True) -> list[tuple[int, float, str]]:
    alpha, freq = (FI_ALPHA, FREQ_FI) if finnish else (EN_ALPHA, FREQ_EN)
    results = []
    for shift in range(1, len(alpha)):
        cand = caesar(text, -shift, alpha)
        results.append((shift, chi_score(cand, freq), cand))
    results.sort(key=lambda r: r[1])
    return results


# --------------------------------------------------------------------------
# Invisible message (zero-width characters)
# --------------------------------------------------------------------------

ZW0, ZW1, ZW_MARK = "​", "‌", "⁠"


def zw_hide(cover: str, secret: str) -> str:
    bits = "".join(f"{b:08b}" for b in secret.encode("utf-8"))
    payload = ZW_MARK + "".join(ZW1 if b == "1" else ZW0 for b in bits) + ZW_MARK
    pos = min(1, len(cover))
    return cover[:pos] + payload + cover[pos:]


def zw_reveal(text: str) -> str | None:
    m = re.search(f"{ZW_MARK}([{ZW0}{ZW1}]+){ZW_MARK}", text)
    raw = m.group(1) if m else "".join(ch for ch in text if ch in (ZW0, ZW1))
    if not raw or len(raw) % 8:
        return None
    bits = "".join("1" if ch == ZW1 else "0" for ch in raw)
    data = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    return data.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

def _ask_secret(prompt: str, confirm: bool = False) -> str:
    import getpass

    while True:
        try:
            pw = getpass.getpass(ui.c("? ", "bright_magenta") + ui.c(prompt, "bold") + " ")
        except Exception:  # noqa: BLE001 - getpass does not work everywhere
            pw = input(prompt + ": ")
        if not pw:
            ui.warn("The password can't be empty.")
            continue
        if confirm:
            again = getpass.getpass(ui.c("? ", "bright_magenta") + ui.c("Password again", "bold") + " ")
            if again != pw:
                ui.error("The passwords don't match.")
                continue
        return pw


@tool("crypto", "crypto-hash", "Hashes of text", "MD5, SHA-1, SHA-256, SHA-512, SHA-3, BLAKE2, CRC32…",
      ("hash", "md5", "sha256", "tiiviste"))
def hash_text_tool() -> None:
    text = ui.get_text()
    data = text.encode("utf-8")
    ui.print_kv([(a.upper().replace("_", "-"), hash_bytes(data, a)) for a in ALGOS])


@tool("crypto", "crypto-file-checksum", "File checksum", "Compute or verify a downloaded file's SHA-256/MD5",
      ("checksum", "hash", "lataus", "eheys"))
def hash_file_tool() -> None:
    path = ui.ask_path("File", kind="file")
    expected = ui.ask("Expected checksum (empty = just compute)", allow_empty=True).strip().lower()
    algo = guess_algo(expected) if expected else None
    algos = [algo] if algo else ["md5", "sha1", "sha256", "sha512"]
    size = path.stat().st_size
    results = {}
    for a in algos:
        with ui.ProgressBar(size, a.upper(), byte_mode=True) as pb:
            results[a] = hash_file(path, a, pb.update)
    ui.print_kv([(a.upper(), d) for a, d in results.items()])
    if expected:
        if expected in results.values():
            ui.success("Checksum matches – the file is intact.")
        else:
            ui.error("Checksum does NOT match! The file may be corrupted or modified.")


@tool("crypto", "crypto-encodings", "Encodings", "Base64, Base32, hex, URL, HTML, binary, punycode, ROT13…",
      ("base64", "url", "hex", "binary", "encode", "decode"))
def encode_tool() -> None:
    names = list(ENCODINGS)
    direction = ui.choose("Direction", ["Encode", "Decode"])
    idx = ui.choose("Encoding", names + ["All at once (encode)"])
    text = ui.get_text()
    if idx == len(names):
        for name in names:
            try:
                print(f"{ui.c(name.ljust(22), 'bright_cyan')} {ENCODINGS[name][0](text)}")
            except Exception as exc:  # noqa: BLE001
                print(f"{ui.c(name.ljust(22), 'bright_cyan')} {ui.red(str(exc))}")
        return
    try:
        result = ENCODINGS[names[idx]][direction](text)
    except Exception as exc:  # noqa: BLE001
        ui.error(f"Failed: {exc}")
        return
    print(ui.bold(result))
    offer_copy(result)


@tool("crypto", "crypto-password-generator", "Password generator", "Strong random passwords using the secrets module",
      ("password", "salasana", "generaattori"))
def password_tool() -> None:
    length = ui.ask_int("Length", 20, 4, 512)
    count = ui.ask_int("How many", 5, 1, 100)
    symbols = ui.ask_yes_no("Include special characters?", True)
    ambiguous = ui.ask_yes_no("Avoid look-alike characters (l, 1, O, 0)?", False)
    pws = [gen_password(length, symbols=symbols, avoid_ambiguous=ambiguous) for _ in range(count)]
    st = password_strength(pws[0])
    for pw in pws:
        print("  " + ui.bold(pw))
    ui.info(f"Entropy about {st['entropy']:.0f} bits – {st['label']}.")
    offer_copy(pws[0])


@tool("crypto", "crypto-passphrase-generator", "Passphrase generator", "Easy to remember passphrases",
      ("passphrase", "diceware", "muistettava"))
def passphrase_tool() -> None:
    n = ui.ask_int("Words", 5, 3, 12)
    sep = ui.ask("Separator", "-")
    ascii_only = ui.ask_yes_no("ASCII only?", False)
    phrases = [gen_passphrase(n, sep, ascii_only=ascii_only) for _ in range(5)]
    for p in phrases:
        print("  " + ui.bold(p))
    bits = n * math.log2(len(WORDS_FI)) + math.log2(100 * n)
    ui.info(f"Word list has {len(WORDS_FI)} words → about {bits:.0f} bits of entropy.")
    offer_copy(phrases[0])


@tool("crypto", "crypto-password-strength", "Password strength", "Estimates how fast a password could be cracked", ("password", "vahvuus", "murto"))
def strength_tool() -> None:
    pw = _ask_secret("Password (not shown on screen)")
    st = password_strength(pw)
    colors = ["bright_red", "bright_red", "bright_yellow", "bright_green", "bright_green"]
    meter = "█" * (st["score"] + 1) * 4 + "░" * (4 - st["score"]) * 4  # type: ignore[operator]
    print(ui.c(meter, colors[st["score"]]) + "  " + ui.c(st["label"], "bold", colors[st["score"]]))  # type: ignore[index]
    ui.print_kv([
        ("Length", len(pw)),
        ("Entropy", f"{st['entropy']:.1f} bits"),
        ("Crack time (fast hash, GPU)", fmt_crack_time(st["offline_fast"])),  # type: ignore[arg-type]
        ("Crack time (slow hash, bcrypt)", fmt_crack_time(st["offline_slow"])),  # type: ignore[arg-type]
        ("Crack time (online, 100/h)", fmt_crack_time(st["online"])),  # type: ignore[arg-type]
    ])
    for f in st["feedback"]:  # type: ignore[attr-defined]
        ui.warn(f)
    if not st["feedback"]:
        ui.success("Good password!")


@tool("crypto", "crypto-ids-and-tokens", "UUID, ULID and tokens", "UUID v1/v4/v7, ULID, NanoID, API keys and PIN codes",
      ("uuid", "guid", "token", "ulid", "nanoid", "pin"))
def ids_tool() -> None:
    kinds = ["UUID v4 (random)", "UUID v7 (time ordered)", "UUID v1 (time + device)", "ULID", "NanoID",
             "Hex token (32 bytes)", "URL-safe token", "PIN code", "Inspect an existing UUID"]
    idx = ui.choose("Type", kinds)
    if idx == 8:
        try:
            ui.print_kv(uuid_info(ui.ask("UUID")))
        except ValueError:
            ui.error("Invalid UUID.")
        return
    count = ui.ask_int("How many", 5, 1, 1000)
    gens: list[Callable[[], str]] = [
        lambda: str(uuid.uuid4()), lambda: str(uuid7()), lambda: str(uuid.uuid1()), ulid, nanoid,
        lambda: secrets.token_hex(32), lambda: secrets.token_urlsafe(32),
    ]
    if idx == 7:
        digits = ui.ask_int("Digits", 4, 3, 12)
        values = ["".join(secrets.choice(string.digits) for _ in range(digits)) for _ in range(count)]
    else:
        values = [gens[idx]() for _ in range(count)]
    for v in values:
        print("  " + v)
    offer_copy("\n".join(values))


@tool("crypto", "crypto-jwt-decoder", "JWT decoder", "Shows the contents and expiry of a JSON Web Token", ("jwt", "token", "bearer"))
def jwt_tool() -> None:
    token = ui.ask("JWT")
    try:
        header, payload, sig = jwt_decode(token)
    except (ValueError, json.JSONDecodeError, binascii.Error) as exc:
        ui.error(f"Not a valid JWT: {exc}")
        return
    print(ui.c("Header", "bold", "bright_cyan"))
    print(json.dumps(header, indent=2, ensure_ascii=False))
    print(ui.c("Payload", "bold", "bright_cyan"))
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    now = time.time()
    for claim, label in (("iat", "Issued"), ("nbf", "Valid from"), ("exp", "Expires")):
        if isinstance(payload.get(claim), (int, float)):
            when = dt.datetime.fromtimestamp(payload[claim]).strftime("%Y-%m-%d %H:%M:%S")
            extra = ""
            if claim == "exp":
                extra = ui.red(" (EXPIRED)") if payload[claim] < now else ui.green(
                    f" (valid for {ui.fmt_duration(payload[claim] - now)})")
            print(f"{ui.gray(label + ':')} {when}{extra}")
    ui.warn("The signature wasn't verified – don't trust the contents blindly.")


@tool("crypto", "crypto-hmac-signature", "HMAC signature", "Compute a message HMAC (e.g. verifying webhooks)", ("hmac", "allekirjoitus", "webhook"))
def hmac_tool() -> None:
    key = ui.ask("Key")
    msg = ui.get_text("Message")
    for algo in ("sha256", "sha1", "sha512", "md5"):
        d = hmac.new(key.encode(), msg.encode(), algo).digest()
        print(f"{ui.c(('HMAC-' + algo.upper()).ljust(12), 'bright_cyan')} {d.hex()}")
    print(f"{ui.c('base64 (256)'.ljust(12), 'bright_cyan')} "
          f"{base64.b64encode(hmac.new(key.encode(), msg.encode(), 'sha256').digest()).decode()}")


@tool("crypto", "crypto-encrypt-file", "Encrypt a file with a password", "Encrypt or decrypt a file (PBKDF2 + keystream + HMAC)",
      ("encrypt", "decrypt", "salaa", "pura"))
def file_crypt_tool() -> None:
    mode = ui.choose("Action", ["Encrypt a file", "Decrypt an encrypted file"])
    src = ui.ask_path("File", kind="file")
    if mode == 0:
        dst = Path(ui.ask("Encrypted file", str(src) + ".enc"))
        pw = _ask_secret("Password", confirm=True)
        with ui.ProgressBar(src.stat().st_size, "Encrypting", byte_mode=True) as pb:
            encrypt_file(src, dst, pw, pb.update)
        ui.success(f"Encrypted: {dst}")
        ui.warn("If you forget the password, the file can never be opened.")
        if ui.ask_yes_no("Delete the original?", False):
            src.unlink()
    else:
        default = str(src)[:-4] if str(src).endswith(".enc") else str(src) + ".dec"
        dst = Path(ui.ask("Decrypted file", default))
        pw = _ask_secret("Password")
        try:
            with ui.Spinner("Verifying and decrypting"):
                decrypt_file(src, dst, pw)
        except ValueError as exc:
            ui.error(str(exc))
            return
        ui.success(f"Decrypted: {dst}")


@tool("crypto", "crypto-encrypt-message", "Encrypt a message", "Encrypts text to send to a friend (both need Foldknife)",
      ("encrypt", "viesti", "salainen"))
def message_crypt_tool() -> None:
    mode = ui.choose("Action", ["Encrypt a message", "Decrypt a message"])
    if mode == 0:
        text = ui.get_text("Message")
        result = encrypt_text(text, _ask_secret("Password", confirm=True))
        print(ui.bold(result))
        offer_copy(result)
    else:
        token = ui.ask("Encrypted message (PKS1:…)")
        try:
            print(ui.bold(decrypt_text(token, _ask_secret("Password"))))
        except ValueError as exc:
            ui.error(str(exc))


@tool("crypto", "crypto-classical-ciphers", "Classical ciphers", "Caesar, ROT13, Vigenère, Atbash, Affine, rail fence, XOR, Bacon, Polybius",
      ("caesar", "vigenere", "atbash", "cipher", "salakirjoitus"))
def classic_tool() -> None:
    ciphers = ["Caesar (shift)", "Vigenère (keyword)", "Atbash (mirror)", "Affine", "Rail fence",
               "XOR as hex", "Bacon's cipher", "Polybius square"]
    idx = ui.choose("Method", ciphers)
    decrypt = ui.choose("Direction", ["Encrypt", "Decode"]) == 1
    text = ui.get_text()
    finnish = idx in (0, 1, 2) and ui.ask_yes_no("Use the Finnish alphabet (with å, ä, ö)?", False)
    alpha = FI_ALPHA if finnish else EN_ALPHA
    try:
        if idx == 0:
            shift = ui.ask_int("Move", 3)
            result = caesar(text, -shift if decrypt else shift, alpha)
        elif idx == 1:
            result = vigenere(text, ui.ask("Keyword"), decrypt, alpha)
        elif idx == 2:
            result = atbash(text, alpha)
        elif idx == 3:
            result = affine(text, ui.ask_int("a", 5), ui.ask_int("b", 8), decrypt)
        elif idx == 4:
            result = rail_fence(text, ui.ask_int("Rails", 3, 2, 50), decrypt)
        elif idx == 5:
            key = ui.ask("Key")
            result = xor_unhex(text, key) if decrypt else xor_hex(text, key)
        elif idx == 6:
            result = unbacon(text) if decrypt else bacon(text)
        else:
            result = unpolybius(text) if decrypt else polybius(text)
    except ValueError as exc:
        ui.error(str(exc))
        return
    print(ui.bold(result))
    offer_copy(result)


@tool("crypto", "crypto-caesar-cracker", "Caesar cracker", "Breaks a Caesar cipher with letter frequencies and shows all shifts",
      ("caesar", "murto", "crack", "frekvenssi"))
def caesar_crack_tool() -> None:
    text = ui.get_text("Encrypted text")
    finnish = ui.ask_yes_no("Is the original text Finnish (instead of English)?", False)
    results = crack_caesar(text, finnish)
    best = results[0]
    ui.success(f"Most likely shift {best[0]}:")
    print(ui.bold(best[2]))
    print()
    if ui.ask_yes_no("Show all shifts?", False):
        for shift, score, cand in sorted(results):
            print(f"{ui.gray(str(shift).rjust(2))} {cand[:100]}")
    print()
    ui.info("Letter frequencies:")
    counts = Counter(ch for ch in text.lower() if ch.isalpha())
    ui.bar_chart(counts.most_common(12), color="bright_magenta")


@tool("crypto", "crypto-invisible-message", "Invisible message", "Hides a secret message as invisible characters inside normal text",
      ("steganografia", "piilota", "zero width", "salainen"))
def zero_width_tool() -> None:
    mode = ui.choose("Action", ["Hide a message", "Reveal a message"])
    if mode == 0:
        cover = ui.ask("Visible text", "Hi! How are you?")
        secret = ui.ask("Secret message")
        result = zw_hide(cover, secret)
        print(ui.bold(result))
        ui.info(f"Looks like {len(cover)} characters but contains {len(result)}.")
        offer_copy(result)
    else:
        text = ui.get_text("Text containing the message")
        found = zw_reveal(text)
        if found:
            ui.success("Hidden message:")
            print(ui.bold(found))
        else:
            ui.warn("No hidden message found.")


@tool("crypto", "crypto-hash-identifier", "Hash identifier", "Guesses a hash type (MD5, SHA-1, bcrypt, Argon2…)",
      ("hash", "identify", "tunnista"))
def identify_tool() -> None:
    value = ui.ask("Hash")
    guesses = identify_hash(value)
    ui.info("Possible types:")
    for g in guesses:
        print("  " + ui.bold(g))
