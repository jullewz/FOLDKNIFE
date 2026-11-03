"""Network tools: IP, DNS, ping, ports, HTTP, SSL, WHOIS, subnets, downloads, sharing,
LAN chat, speed test, weather, currencies and crypto."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import http.server
import ipaddress
import json
import os
import random
import re
import secrets
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
from functools import partial
from pathlib import Path
from typing import Any

from ..core import ui
from ..core.registry import tool
from ..core.utils import NetError, http_get, http_json, http_request, quote, unique_path

# --------------------------------------------------------------------------
# IP
# --------------------------------------------------------------------------


def local_ip() -> str:
    """The machine's LAN IP address (the UDP 'connection' sends nothing)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def public_ip_info(ip: str = "") -> dict[str, Any]:
    url = f"https://ipinfo.io/{ip + '/' if ip else ''}json"
    try:
        return http_json(url, timeout=8)
    except NetError:
        if ip:
            raise
        return http_json("https://api.ipify.org?format=json", timeout=8)


# --------------------------------------------------------------------------
# DNS (small custom UDP client + DNS-over-HTTPS fallback)
# --------------------------------------------------------------------------

QTYPES = {"A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "PTR": 12, "MX": 15, "TXT": 16, "AAAA": 28, "SRV": 33, "CAA": 257}
QTYPE_NAMES = {v: k for k, v in QTYPES.items()}
RCODES = {0: "OK", 1: "format error", 2: "server failure", 3: "name does not exist (NXDOMAIN)", 4: "not supported", 5: "refused"}


def _encode_name(name: str) -> bytes:
    out = b""
    for label in name.rstrip(".").split("."):
        if label:
            enc = label.encode("idna")
            out += bytes([len(enc)]) + enc
    return out + b"\x00"


def _read_name(data: bytes, offset: int) -> tuple[str, int]:
    labels: list[str] = []
    jumped = False
    end = offset
    hops = 0
    while True:
        if offset >= len(data):
            raise ValueError("Truncated DNS response.")
        length = data[offset]
        if length & 0xC0 == 0xC0:
            if hops > 30:
                raise ValueError("DNS pointer loop.")
            ptr = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                end = offset + 2
            offset, jumped, hops = ptr, True, hops + 1
            continue
        if length == 0:
            if not jumped:
                end = offset + 1
            break
        labels.append(data[offset + 1:offset + 1 + length].decode("ascii", errors="replace"))
        offset += 1 + length
    return ".".join(labels) + ".", end


def build_query(name: str, qtype: int, qid: int) -> bytes:
    return struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + _encode_name(name) + struct.pack(">HH", qtype, 1)


def parse_response(data: bytes) -> tuple[int, list[tuple[str, str, int, str]], bool]:
    qid, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    rcode = flags & 0xF
    truncated = bool(flags & 0x0200)
    offset = 12
    for _ in range(qd):
        _, offset = _read_name(data, offset)
        offset += 4
    answers = []
    for _ in range(an):
        name, offset = _read_name(data, offset)
        rtype, _cls, ttl, rdlen = struct.unpack(">HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlen]
        start = offset
        offset += rdlen
        tname = QTYPE_NAMES.get(rtype, str(rtype))
        if rtype == 1:
            value = str(ipaddress.IPv4Address(rdata))
        elif rtype == 28:
            value = str(ipaddress.IPv6Address(rdata))
        elif rtype in (2, 5, 12):
            value = _read_name(data, start)[0]
        elif rtype == 15:
            pref = struct.unpack(">H", rdata[:2])[0]
            value = f"{pref} {_read_name(data, start + 2)[0]}"
        elif rtype == 16:
            parts, i = [], 0
            while i < len(rdata):
                ln = rdata[i]
                parts.append(rdata[i + 1:i + 1 + ln].decode("utf-8", errors="replace"))
                i += 1 + ln
            value = "".join(parts)
        elif rtype == 6:
            mname, o = _read_name(data, start)
            rname, o = _read_name(data, o)
            serial, refresh, retry, expire, minimum = struct.unpack(">IIIII", data[o:o + 20])
            value = f"{mname} {rname} serial={serial} refresh={refresh}s retry={retry}s expire={expire}s min={minimum}s"
        elif rtype == 33:
            prio, weight, port = struct.unpack(">HHH", rdata[:6])
            value = f"priority={prio} weight={weight} port={port} {_read_name(data, start + 6)[0]}"
        elif rtype == 257:
            flag, tlen = rdata[0], rdata[1]
            value = f"{flag} {rdata[2:2 + tlen].decode()} \"{rdata[2 + tlen:].decode(errors='replace')}\""
        else:
            value = rdata.hex()
        answers.append((name, tname, ttl, value))
    return rcode, answers, truncated


def dns_query(name: str, qtype: str = "A", server: str = "1.1.1.1", timeout: float = 3.0) -> tuple[int, list[tuple[str, str, int, str]]]:
    qt = QTYPES[qtype.upper()]
    qid = secrets.randbelow(65536)
    packet = build_query(name, qt, qid)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(packet, (server, 53))
            data, _ = s.recvfrom(4096)
        rcode, answers, truncated = parse_response(data)
        if truncated:
            with socket.create_connection((server, 53), timeout=timeout) as t:
                t.sendall(struct.pack(">H", len(packet)) + packet)
                length = struct.unpack(">H", _recv_exact(t, 2))[0]
                rcode, answers, _ = parse_response(_recv_exact(t, length))
        return rcode, answers
    except (OSError, socket.timeout):
        return dns_over_https(name, qtype)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise OSError("Connection closed.")
        buf += chunk
    return buf


def dns_over_https(name: str, qtype: str) -> tuple[int, list[tuple[str, str, int, str]]]:
    data = http_json(f"https://cloudflare-dns.com/dns-query?name={quote(name)}&type={qtype}",
                     headers={"Accept": "application/dns-json"})
    answers = [(a.get("name", ""), QTYPE_NAMES.get(a.get("type"), str(a.get("type"))), a.get("TTL", 0),
                str(a.get("data", "")).strip('"')) for a in data.get("Answer", [])]
    return int(data.get("Status", 0)), answers


def reverse_name(ip: str) -> str:
    return ipaddress.ip_address(ip).reverse_pointer


# --------------------------------------------------------------------------
# Ports, HTTP, SSL, WHOIS
# --------------------------------------------------------------------------

COMMON_PORTS = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3", 139: "NetBIOS",
                143: "IMAP", 443: "HTTPS", 445: "SMB", 587: "SMTP (submission)", 993: "IMAPS", 995: "POP3S",
                1883: "MQTT", 3000: "dev server", 3306: "MySQL", 3389: "Remote Desktop (RDP)", 5000: "dev server",
                5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 7777: "Terraria", 8000: "HTTP-alt", 8080: "HTTP-alt",
                8443: "HTTPS-alt", 9000: "dev server", 25565: "Minecraft", 25575: "Minecraft RCON",
                27015: "Steam/Source", 27017: "MongoDB", 32400: "Plex"}


def check_port(host: str, port: int, timeout: float = 1.0) -> float | None:
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - start) * 1000
    except OSError:
        return None


def scan_ports(host: str, ports: list[int], timeout: float = 1.0, workers: int = 100) -> dict[int, float]:
    found: dict[int, float] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_port, host, p, timeout): p for p in ports}
        for fut in concurrent.futures.as_completed(futures):
            ms = fut.result()
            if ms is not None:
                found[futures[fut]] = ms
    return dict(sorted(found.items()))


SECURITY_HEADERS = ["Strict-Transport-Security", "Content-Security-Policy", "X-Content-Type-Options",
                    "X-Frame-Options", "Referrer-Policy", "Permissions-Policy"]


def redirect_chain(url: str, max_hops: int = 10) -> list[tuple[str, int, float, dict[str, str]]]:
    hops = []
    for _ in range(max_hops):
        start = time.perf_counter()
        status, headers, _, _ = http_request(url, method="GET", follow_redirects=False, timeout=15)
        hops.append((url, status, (time.perf_counter() - start) * 1000, headers))
        loc = next((v for k, v in headers.items() if k.lower() == "location"), None)
        if status in (301, 302, 303, 307, 308) and loc:
            url = urllib.parse.urljoin(url, loc)
        else:
            break
    return hops


def ssl_info(host: str, port: int = 443) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                version, cipher = ssock.version(), ssock.cipher()
    except ssl.SSLCertVerificationError as exc:
        return {"virhe": f"Certificate is not valid: {exc.verify_message}"}
    except OSError as exc:
        raise NetError(f"Connection failed: {exc}") from exc
    subject = dict(x[0] for x in cert.get("subject", ()))
    issuer = dict(x[0] for x in cert.get("issuer", ()))
    expires = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
    starts = dt.datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z")
    sans = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
    return {"subject": subject.get("commonName", "?"), "issuer": f"{issuer.get('organizationName', '')} {issuer.get('commonName', '')}".strip(),
            "valid_from": starts, "valid_to": expires,
            "days_left": (expires - dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)).days,
            "sans": sans, "version": version, "cipher": cipher[0] if cipher else "?"}


def whois(domain: str) -> str:
    def query(server: str, q: str) -> str:
        with socket.create_connection((server, 43), timeout=10) as s:
            s.sendall((q + "\r\n").encode("idna" if False else "utf-8"))
            chunks = []
            while True:
                data = s.recv(4096)
                if not data:
                    break
                chunks.append(data)
        return b"".join(chunks).decode("utf-8", errors="replace")

    domain = domain.strip().lower().encode("idna").decode()
    try:
        iana = query("whois.iana.org", domain)
    except OSError as exc:
        raise NetError(f"Couldn't connect to the WHOIS server: {exc}") from exc
    m = re.search(r"^refer:\s*(\S+)", iana, re.MULTILINE)
    if not m:
        return iana
    try:
        return query(m.group(1), domain)
    except OSError as exc:
        raise NetError(f"WHOIS server {m.group(1)} didn't respond: {exc}") from exc


# --------------------------------------------------------------------------
# Weather
# --------------------------------------------------------------------------

WIND_DIRS = {"N": "north", "NNE": "north-northeast", "NE": "northeast", "ENE": "east-northeast", "E": "east",
             "ESE": "east-southeast", "SE": "southeast", "SSE": "south-southeast", "S": "south", "SSW": "south-southwest",
             "SW": "southwest", "WSW": "west-southwest", "W": "west", "WNW": "west-northwest", "NW": "northwest",
             "NNW": "north-northwest"}


def weather_icon(code: int) -> tuple[str, str]:
    if code == 113:
        return "☀", "bright_yellow"
    if code == 116:
        return "⛅", "bright_yellow"
    if code in (119, 122):
        return "☁", "gray"
    if code in (143, 248, 260):
        return "🌫", "gray"
    if code in (200, 386, 389, 392, 395):
        return "⛈", "bright_magenta"
    if code in (179, 227, 230, 323, 326, 329, 332, 335, 338, 368, 371):
        return "❄", "bright_white"
    if code in (182, 185, 281, 284, 311, 314, 317, 320, 350, 362, 365, 374, 377):
        return "🌨", "bright_cyan"
    return "🌧", "bright_blue"


def get_weather(city: str) -> dict[str, Any]:
    return http_json(f"https://wttr.in/{quote(city)}?format=j1&lang=en", timeout=15)


def _desc(entry: dict[str, Any]) -> str:
    for key in ("lang_fi", "weatherDesc"):
        val = entry.get(key)
        if val and isinstance(val, list) and val[0].get("value"):
            return val[0]["value"]
    return ""


def show_weather(city: str) -> None:
    with ui.Spinner(f"Fetching weather: {city}"):
        data = get_weather(city)
    cur = data["current_condition"][0]
    area = data.get("nearest_area", [{}])[0]
    place = ", ".join(x[0]["value"] for x in (area.get("areaName"), area.get("country")) if x)
    icon, color = weather_icon(int(cur.get("weatherCode", 113)))
    temp = int(cur["temp_C"])
    tcolor = "bright_blue" if temp < 0 else "bright_cyan" if temp < 10 else "bright_green" if temp < 20 else "bright_red"
    ui.box([f"{ui.c(icon, color)}  {ui.c(f'{temp} °C', 'bold', tcolor)}  {_desc(cur)}",
            ui.gray(f"feels like {cur['FeelsLikeC']} °C · wind {round(int(cur['windspeedKmph']) / 3.6, 1)} m/s "
                    f"{WIND_DIRS.get(cur.get('winddir16Point', ''), '')}"),
            ui.gray(f"humidity {cur['humidity']} % · pressure {cur['pressure']} hPa · rain {cur['precipMM']} mm · UV {cur.get('uvIndex', '?')}")],
           title=place or city, color="bright_cyan")
    for day in data.get("weather", [])[:3]:
        date = dt.date.fromisoformat(day["date"])
        astro = day.get("astronomy", [{}])[0]
        hourly = day.get("hourly", [])
        mid = hourly[len(hourly) // 2] if hourly else {}
        ic, col = weather_icon(int(mid.get("weatherCode", 113)))
        rain = max((int(h.get("chanceofrain", 0)) for h in hourly), default=0)
        from ..core.utils import FI_WEEKDAYS

        sunrise, sunset = astro.get("sunrise", "?"), astro.get("sunset", "?")
        extra = ui.gray(f"chance of rain {rain} %  ☀ {sunrise} – {sunset}")
        print(f"  {FI_WEEKDAYS[date.weekday()][:2]} {date.day}.{date.month}.  {ui.c(ic, col)}  "
              f"{ui.c(day['mintempC'] + '…' + day['maxtempC'] + ' °C', 'bold')}  {extra}")
        temps = [int(h["tempC"]) for h in hourly]
        if temps:
            print("        " + ui.c(ui.sparkline(temps), "bright_cyan") + ui.gray("  (temperature 00–21)"))


# --------------------------------------------------------------------------
# Currencies and crypto
# --------------------------------------------------------------------------

def currency_rates(base: str = "EUR") -> dict[str, Any]:
    for url in (f"https://api.frankfurter.app/latest?from={base}", f"https://api.frankfurter.dev/v1/latest?base={base}"):
        try:
            return http_json(url, timeout=10)
        except NetError:
            continue
    raise NetError("Couldn't get exchange rates (frankfurter.app).")


CRYPTO_IDS = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "ripple": "XRP", "cardano": "ADA",
              "dogecoin": "DOGE", "litecoin": "LTC", "polkadot": "DOT", "tron": "TRX", "chainlink": "LINK"}


# --------------------------------------------------------------------------
# Speed test
# --------------------------------------------------------------------------

def measure_download(size: int) -> float:
    start = time.perf_counter()
    data = http_get(f"https://speed.cloudflare.com/__down?bytes={size}", timeout=60)
    took = time.perf_counter() - start
    return len(data) * 8 / took / 1e6


def measure_upload(size: int) -> float:
    payload = os.urandom(size)
    start = time.perf_counter()
    http_request("https://speed.cloudflare.com/__up", method="POST", data=payload,
                 headers={"Content-Type": "application/octet-stream"}, timeout=60)
    return size * 8 / (time.perf_counter() - start) / 1e6


def measure_latency(n: int = 5) -> list[float]:
    out = []
    for _ in range(n):
        start = time.perf_counter()
        http_get("https://speed.cloudflare.com/__down?bytes=0", timeout=10)
        out.append((time.perf_counter() - start) * 1000)
    return out


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("network", "net-my-ip", "My IP address", "LAN and public IP plus estimated location and ISP",
      ("ip", "osoite", "my ip", "operaattori"))
def my_ip_tool() -> None:
    rows: list[tuple[str, Any]] = [("Hostname", socket.gethostname()), ("LAN IP", local_ip())]
    try:
        with ui.Spinner("Fetching public IP"):
            info = public_ip_info()
        rows += [("Public IP", info.get("ip")), ("Location (estimate)", f"{info.get('city', '?')}, {info.get('region', '')} {info.get('country', '')}"),
                 ("ISP", info.get("org", "?")), ("Time zone", info.get("timezone", "?"))]
    except NetError as exc:
        rows.append(("Public IP", ui.red(str(exc))))
    ui.print_kv(rows)


@tool("network", "net-ip-info", "IP address info", "Whose IP is this? Country, city, organisation and reverse DNS",
      ("ip", "lookup", "geo", "sijainti"))
def ip_lookup_tool() -> None:
    ip = ui.ask("IP address")
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        ui.error("Not a valid IP address.")
        return
    rows: list[tuple[str, Any]] = [("Version", f"IPv{addr.version}"),
                                   ("Type", "private" if addr.is_private else "loopback" if addr.is_loopback else "public")]
    try:
        rows.append(("Reverse DNS", socket.gethostbyaddr(str(addr))[0]))
    except OSError:
        rows.append(("Reverse DNS", "-"))
    if addr.is_global:
        try:
            info = public_ip_info(str(addr))
            rows += [("Location", f"{info.get('city', '?')}, {info.get('country', '?')}"), ("Organisation", info.get("org", "?"))]
        except NetError as exc:
            rows.append(("Location", ui.red(str(exc))))
    ui.print_kv(rows)


@tool("network", "net-dns-lookup", "DNS lookup", "A, AAAA, MX, TXT, NS, CNAME, SOA, SRV, CAA and PTR – built-in DNS client",
      ("dns", "nslookup", "dig", "mx", "nimipalvelin"))
def dns_tool() -> None:
    name = ui.ask("Domain or IP", "example.com")
    server = ui.ask("DNS server", "1.1.1.1")
    try:
        ipaddress.ip_address(name)
        types = ["PTR"]
        name = reverse_name(name)
    except ValueError:
        types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "CAA"]
    rows = []
    for qt in types:
        try:
            rcode, answers = dns_query(name, qt, server)
        except (NetError, ValueError) as exc:
            rows.append((qt, "", ui.red(str(exc))))
            continue
        if rcode == 3:
            ui.error(f"The name {name} does not exist.")
            return
        for _, t, ttl, value in answers:
            rows.append((t, ttl, value))
    if rows:
        ui.table(rows, ["Type", "TTL", "Value"], max_col_width=80)
    else:
        ui.warn("No answers.")


@tool("network", "net-ping", "Ping", "Ping a server (ICMP) or measure TCP connect latency to a port",
      ("ping", "viive", "latency", "lag"))
def ping_tool() -> None:
    host = ui.ask("Address", "google.com")
    mode = ui.choose("Method", ["Normal ping", "TCP ping (port, works through firewalls)"])
    if mode == 0:
        count = ui.ask_int("How many", 4, 1, 100)
        cmd = ["ping", "-n" if os.name == "nt" else "-c", str(count), host]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding="oem" if os.name == "nt" else None, errors="replace")
        except FileNotFoundError:
            ui.error("ping command not found. Try TCP ping.")
            return
        assert proc.stdout
        for line in proc.stdout:
            print("  " + line.rstrip())
        proc.wait()
        return
    port = ui.ask_int("Port", 443, 1, 65535)
    count = ui.ask_int("How many", 5, 1, 100)
    times = []
    for i in range(count):
        ms = check_port(host, port, 3)
        if ms is None:
            print(f"  {i + 1}: {ui.red('no reply')}")
        else:
            times.append(ms)
            print(f"  {i + 1}: {ms:.1f} ms")
        time.sleep(0.4)
    if times:
        ui.info(f"min {min(times):.1f} / avg {sum(times) / len(times):.1f} / max {max(times):.1f} ms, "
                f"loss {(count - len(times)) / count * 100:.0f} %")


@tool("network", "net-port-checker", "Port checker", "Which ports are open on your own machine, server or router",
      ("portti", "port", "skannaus", "minecraft", "auki"))
def ports_tool() -> None:
    ui.warn("Only scan your own devices or ones you have permission to scan.")
    host = ui.ask("Target", "127.0.0.1")
    mode = ui.choose("Ports", ["Common ports", "Specific ports", "Range (max 2048 ports)"])
    if mode == 0:
        ports = list(COMMON_PORTS)
    elif mode == 1:
        ports = [int(p) for p in re.findall(r"\d+", ui.ask("Ports separated by commas", "80,443,25565"))]
    else:
        a, b = ui.ask_int("Start", 1, 1, 65535), ui.ask_int("End", 1024, 1, 65535)
        ports = list(range(a, min(b, a + 2047) + 1))
    with ui.Spinner(f"Checking {len(ports)} ports"):
        found = scan_ports(host, ports)
    if not found:
        ui.info("No open ports found.")
        return
    ui.table([(p, COMMON_PORTS.get(p, ""), f"{ms:.0f} ms") for p, ms in found.items()], ["Port", "Service", "Latency"])


@tool("network", "net-http-check", "HTTP check", "Page status, redirects, response time and security headers",
      ("http", "status", "redirect", "otsakkeet", "headers"))
def http_tool() -> None:
    url = ui.ask("URL", "https://example.com")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    hops = redirect_chain(url)
    for u, status, ms, _ in hops:
        color = "bright_green" if status < 300 else "bright_yellow" if status < 400 else "bright_red"
        print(f"  {ui.c(str(status), 'bold', color)}  {ms:6.0f} ms  {u}")
    final_headers = hops[-1][3]
    print()
    ui.print_kv([(k, v[:100]) for k, v in final_headers.items()][:25])
    print()
    lower = {k.lower() for k in final_headers}
    for h in SECURITY_HEADERS:
        print(f"  {ui.green('✔') if h.lower() in lower else ui.red('✘')} {h}")


@tool("network", "net-ssl-certificate", "SSL certificate", "Certificate issuer, validity and days remaining", ("ssl", "tls", "https", "varmenne", "sertifikaatti"))
def ssl_tool() -> None:
    host = ui.ask("Server", "example.com").replace("https://", "").split("/")[0]
    with ui.Spinner("Connecting"):
        info = ssl_info(host)
    if "virhe" in info:
        ui.error(info["virhe"])
        return
    days = info["days_left"]
    color = "bright_green" if days > 30 else "bright_yellow" if days > 7 else "bright_red"
    ui.print_kv([("Target", info["subject"]), ("Issuer", info["issuer"]),
                 ("Valid from", info["valid_from"].strftime("%Y-%m-%d")),
                 ("Valid until", info["valid_to"].strftime("%Y-%m-%d")),
                 ("Days left", ui.c(str(days), "bold", color)), ("Protocol", info["version"]),
                 ("Cipher suite", info["cipher"]), ("Names (SAN)", ", ".join(info["sans"][:10]))])


@tool("network", "net-whois", "WHOIS", "Domain owner and registration info", ("whois", "domain", "verkkotunnus"))
def whois_tool() -> None:
    domain = ui.ask("Domain", "example.com")
    with ui.Spinner("Fetching WHOIS data"):
        text = whois(domain)
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith(("%", "#", ">>>", "NOTICE", "TERMS"))]
    ui.paginate(lines[:200])


@tool("network", "net-subnet-calculator", "Subnet calculator", "CIDR, network and broadcast address, masks, host count and splitting",
      ("subnet", "cidr", "aliverkko", "netmask", "ip"))
def subnet_tool() -> None:
    raw = ui.ask("Address (e.g. 192.168.1.10/24 or 10.0.0.1 255.255.0.0)", "192.168.1.10/24")
    parts = raw.split()
    try:
        iface = ipaddress.ip_interface(f"{parts[0]}/{parts[1]}" if len(parts) == 2 else parts[0])
    except ValueError as exc:
        ui.error(str(exc))
        return
    net = iface.network
    rows: list[tuple[str, Any]] = [("Address", str(iface.ip)), ("Network", str(net)), ("Network address", str(net.network_address))]
    if net.version == 4:
        hosts = net.num_addresses - 2 if net.prefixlen < 31 else net.num_addresses
        first = net.network_address + (1 if net.prefixlen < 31 else 0)
        last = net.broadcast_address - (1 if net.prefixlen < 31 else 0)
        cls = "A" if net.network_address < ipaddress.IPv4Address("128.0.0.0") else "B" if net.network_address < ipaddress.IPv4Address("192.0.0.0") else "C" if net.network_address < ipaddress.IPv4Address("224.0.0.0") else "D/E"
        rows += [("Broadcast", str(net.broadcast_address)), ("Subnet mask", str(net.netmask)),
                 ("Wildcard", str(net.hostmask)), ("Hosts", ui.fi_num(hosts, 0)), ("Host range", f"{first} – {last}"),
                 ("Class", cls), ("Mask in binary", ".".join(f"{int(o):08b}" for o in str(net.netmask).split(".")))]
    else:
        rows.append(("Addresses", f"2^{128 - net.prefixlen}"))
    rows.append(("Type", "private" if net.is_private else "public"))
    ui.print_kv(rows)
    if ui.ask_yes_no("Split into smaller subnets?", False):
        new = ui.ask_int("New prefix", min(net.prefixlen + 2, net.max_prefixlen), net.prefixlen + 1, net.max_prefixlen)
        subs = list(net.subnets(new_prefix=new))
        ui.paginate([f"  {s}" for s in subs[:1024]])
        ui.info(f"{len(subs)} subnets.")


@tool("network", "net-url-parser", "URL parser", "Splits a URL into parts and decodes query parameters", ("url", "linkki", "parametrit", "query"))
def url_tool() -> None:
    url = ui.ask("URL")
    p = urllib.parse.urlsplit(url)
    ui.print_kv([("Protocol", p.scheme), ("Host", p.hostname or ""), ("Port", p.port or "(default)"),
                 ("User", p.username or "-"), ("Password", "***" if p.password else "-"),
                 ("Path", urllib.parse.unquote(p.path)), ("Fragment", p.fragment or "-")])
    params = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    if params:
        ui.table(params, ["Parameter", "Value"], max_col_width=70)
        tracking = [k for k, _ in params if k.lower().startswith(("utm_", "fbclid", "gclid", "si", "igsh", "mc_"))]
        if tracking:
            clean = urllib.parse.urlunsplit(p._replace(query=urllib.parse.urlencode([(k, v) for k, v in params if k not in tracking])))
            ui.info("With tracking parameters removed:")
            print("  " + ui.bold(clean))


@tool("network", "net-download", "Download a file", "Downloads a file from a URL with a progress bar", ("download", "lataa", "wget", "curl"))
def download_tool() -> None:
    url = ui.ask("URL")
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "Foldknife/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except Exception as exc:  # noqa: BLE001
        raise NetError(f"Download failed: {exc}") from exc
    with resp:
        cd = resp.headers.get("Content-Disposition", "")
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
        name = urllib.parse.unquote(m.group(1)) if m else (Path(urllib.parse.urlsplit(resp.geturl()).path).name or "download")
        target = unique_path(Path(ui.ask("Save as", name)))
        total = int(resp.headers.get("Content-Length") or 0) or None
        with open(target, "wb") as fh, ui.ProgressBar(total, "Downloading", byte_mode=True) as pb:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
                pb.update(len(chunk))
    ui.success(f"Saved: {target.resolve()} ({ui.fmt_bytes(target.stat().st_size)})")


@tool("network", "net-share-folder", "Share a folder on the LAN", "Starts an HTTP server – friends and phones download with a browser (QR code)",
      ("http server", "jaa", "share", "lan", "puhelin"))
def share_tool() -> None:
    folder = ui.ask_path("Folder to share", kind="dir", default=".")
    port = ui.ask_int("Port", 8000, 1024, 65535)
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))

    class QuietHandler(handler.func):  # type: ignore[misc,name-defined]
        def log_message(self, fmt: str, *args: Any) -> None:
            print(ui.gray(f"  {self.client_address[0]} → {self.path}"))

    try:
        server = http.server.ThreadingHTTPServer(("0.0.0.0", port), partial(QuietHandler, directory=str(folder)))
    except OSError as exc:
        ui.error(f"Couldn't open the port: {exc}")
        return
    url = f"http://{local_ip()}:{port}/"
    ui.success(f"Sharing {folder.resolve()}")
    print("  Open in a browser: " + ui.bold(url))
    try:
        from .qr import encode_text, render_terminal

        print(render_terminal(encode_text(url)))
    except Exception:  # noqa: BLE001
        pass
    ui.warn("Everyone on the same network can download the folder's files. Ctrl+C stops.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    ui.info("Sharing stopped.")


@tool("network", "net-lan-chat", "LAN-chat", "Chat with friends on the same network – one hosts, the others join",
      ("chat", "lan", "keskustelu", "viesti"))
def chat_tool() -> None:
    mode = ui.choose("Role", ["Start a chat (host)", "Join a chat"])
    nick = ui.ask("Nickname", os.environ.get("USERNAME") or os.environ.get("USER") or "anonymous")[:20]
    port = ui.ask_int("Port", 5050, 1024, 65535)
    if mode == 0:
        clients: dict[socket.socket, str] = {}
        lock = threading.Lock()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("0.0.0.0", port))
        except OSError as exc:
            ui.error(f"Couldn't open the port: {exc}")
            return
        srv.listen()

        def broadcast(msg: str, skip: socket.socket | None = None) -> None:
            with lock:
                for c in list(clients):
                    if c is not skip:
                        try:
                            c.sendall((msg + "\n").encode())
                        except OSError:
                            clients.pop(c, None)

        def handle(conn: socket.socket) -> None:
            f = conn.makefile("r", encoding="utf-8", errors="replace")
            name = (f.readline().strip() or "guest")[:20]
            with lock:
                clients[conn] = name
            broadcast(f"*** {name} joined ***")
            print(ui.gray(f"*** {name} joined ***"))
            for line in f:
                line = line.strip()
                if line:
                    print(f"{ui.c(name, 'bright_cyan')}: {line}")
                    broadcast(f"{name}: {line}", conn)
            with lock:
                clients.pop(conn, None)
            broadcast(f"*** {name} left ***")
            print(ui.gray(f"*** {name} left ***"))

        def accept_loop() -> None:
            while True:
                try:
                    conn, _ = srv.accept()
                except OSError:
                    return
                threading.Thread(target=handle, args=(conn,), daemon=True).start()

        threading.Thread(target=accept_loop, daemon=True).start()
        ui.success(f"Chat running: friends join at {local_ip()} port {port}")
        print(ui.gray("Type a message and press Enter. An empty line or Ctrl+C quits."))
        try:
            while True:
                msg = input()
                if not msg:
                    break
                broadcast(f"{nick}: {msg}")
        finally:
            broadcast("*** server closed ***")
            srv.close()
        return
    host = ui.ask("Server IP address")
    try:
        sock = socket.create_connection((host, port), timeout=5)
    except OSError as exc:
        ui.error(f"Connection failed: {exc}")
        return
    sock.settimeout(None)
    sock.sendall((nick + "\n").encode())

    def receive() -> None:
        f = sock.makefile("r", encoding="utf-8", errors="replace")
        for line in f:
            print("\r" + line.rstrip())
        print(ui.gray("Connection closed."))

    threading.Thread(target=receive, daemon=True).start()
    ui.success("You joined the chat. An empty line quits.")
    try:
        while True:
            msg = input()
            if not msg:
                break
            sock.sendall((msg + "\n").encode())
    finally:
        sock.close()


@tool("network", "net-speed-test", "Internet speed test", "Download and upload speed plus latency (Cloudflare)",
      ("speedtest", "nopeus", "mbps", "netti", "yhteys"))
def speed_tool() -> None:
    try:
        with ui.Spinner("Measuring latency"):
            lat = measure_latency(5)
        ui.info(f"Latency: {sorted(lat)[len(lat) // 2]:.0f} ms (jitter {max(lat) - min(lat):.0f} ms)")
        results = []
        for size in (1_000_000, 10_000_000, 25_000_000):
            with ui.Spinner(f"Download test {size // 1_000_000} MB"):
                mbps = measure_download(size)
            results.append(mbps)
            print(f"  ↓ {size // 1_000_000:>2} MB: {mbps:7.1f} Mbit/s")
        down = max(results)
        with ui.Spinner("Upload test"):
            up = measure_upload(5_000_000)
        print(f"  ↑  5 MB: {up:7.1f} Mbit/s")
    except NetError as exc:
        ui.error(str(exc))
        return
    ui.box([ui.c(f"↓ {down:.1f} Mbit/s", "bold", "bright_green") + "   " + ui.c(f"↑ {up:.1f} Mbit/s", "bold", "bright_cyan"),
            ui.gray(f"A 4K movie needs about 25 Mbit/s · HD game streaming about 15 Mbit/s")], title="Result")


@tool("network", "net-weather", "Weather", "Current weather and a three-day forecast for any city",
      ("weather", "weather", "ennuste", "temperature"))
def weather_tool() -> None:
    show_weather(ui.ask("City", "Helsinki"))


@tool("network", "net-currency-converter", "Currency converter", "European Central Bank daily rates (e.g. 100 EUR USD)",
      ("valuutta", "kurssi", "dollari", "euro", "currency"))
def currency_tool() -> None:
    raw = ui.ask("Conversion (e.g. 100 EUR USD)", "100 EUR USD")
    m = re.fullmatch(r"\s*([\d\s.,]+)\s*([A-Za-z]{3})\s*(?:to|in|->)?\s*([A-Za-z]{3})?\s*", raw)
    if not m:
        ui.error("Use the format: 100 EUR USD")
        return
    amount = float(m.group(1).replace(" ", "").replace(",", "."))
    base, target = m.group(2).upper(), (m.group(3) or "").upper()
    with ui.Spinner("Fetching rates"):
        data = currency_rates(base)
    rates = data.get("rates", {})
    ui.info(f"Rates {data.get('date', '')} (ECB)")
    if target:
        if target not in rates:
            ui.error(f"Currency {target} not found.")
            return
        print(ui.bold(f"  {ui.fi_num(amount)} {base} = {ui.fi_num(amount * rates[target], 4)} {target}"))
        return
    popular = ["USD", "SEK", "NOK", "DKK", "GBP", "CHF", "JPY", "PLN", "EUR", "CAD", "AUD", "CNY", "TRY", "THB"]
    ui.table([(c, ui.fi_num(amount * rates[c], 2)) for c in popular if c in rates], [base + " →", "Count"], align=["<", ">"])


@tool("network", "net-crypto-prices", "Crypto prices", "Bitcoin, Ethereum, Solana… in euros and dollars (CoinGecko)",
      ("bitcoin", "krypto", "ethereum", "crypto", "btc"))
def crypto_prices_tool() -> None:
    ids = ",".join(CRYPTO_IDS)
    with ui.Spinner("Fetching prices"):
        data = http_json(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=eur,usd&include_24hr_change=true")
    rows = []
    for cid, sym in CRYPTO_IDS.items():
        d = data.get(cid)
        if not d:
            continue
        ch = d.get("eur_24h_change") or 0
        rows.append((sym, cid.capitalize(), ui.fi_num(d["eur"], 2 if d["eur"] > 1 else 5), ui.fi_num(d["usd"], 2 if d["usd"] > 1 else 5),
                     ui.c(f"{ch:+.2f} %", "bright_green" if ch >= 0 else "bright_red")))
    ui.table(rows, ["Symbol", "Name", "EUR", "USD", "24 h"], align=["<", "<", ">", ">", ">"])
    print(ui.gray("  Data: CoinGecko. Not investment advice."))


@tool("network", "net-site-monitor", "Site monitor", "Monitor site status and response time in real time", ("uptime", "monitor", "vahti", "seuranta"))
def monitor_tool() -> None:
    urls = [u if u.startswith("http") else "https://" + u for u in
            ui.ask("URLs separated by commas", "https://example.com, https://www.google.com").replace(" ", "").split(",") if u]
    interval = ui.ask_int("Check interval (s)", 30, 5, 3600)
    stats = {u: [0, 0, []] for u in urls}  # successes, total, latencies
    print(ui.gray("Ctrl+C stops."))
    try:
        while True:
            print(ui.gray(dt.datetime.now().strftime("%H:%M:%S")))
            for u in urls:
                start = time.perf_counter()
                try:
                    status, *_ = http_request(u, timeout=10)
                    ok = status < 400
                except NetError:
                    status, ok = 0, False
                ms = (time.perf_counter() - start) * 1000
                s = stats[u]
                s[1] += 1
                if ok:
                    s[0] += 1
                    s[2].append(ms)
                up = s[0] / s[1] * 100
                print(f"  {ui.green('●') if ok else ui.red('●')} {u[:50].ljust(50)} {status or '---'} {ms:6.0f} ms  "
                      f"{ui.gray(f'{up:.0f} % up')}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print()
    for u, (ok, total, lat) in stats.items():
        if total:
            print(f"  {u}: {ok}/{total} ok, avg latency {sum(lat) / len(lat) if lat else 0:.0f} ms")


@tool("network", "net-wake-on-lan", "Wake-on-LAN", "Wakes a LAN computer with a magic packet", ("wol", "wake", "wake"))
def wol_tool() -> None:
    mac = ui.ask("Target machine MAC address (e.g. AA:BB:CC:DD:EE:FF)")
    clean = re.sub(r"[^0-9a-fA-F]", "", mac)
    if len(clean) != 12:
        ui.error("A MAC address must have 12 hex characters.")
        return
    packet = b"\xff" * 6 + bytes.fromhex(clean) * 16
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(packet, ("255.255.255.255", 9))
    except OSError as exc:
        ui.error(f"Sending failed: {exc}")
        return
    ui.success("Magic packet sent. Wake-on-LAN must be enabled in the target's BIOS.")


@tool("network", "net-traceroute", "Traceroute", "Shows the route and the latency at each hop", ("traceroute", "tracert", "reitti"))
def traceroute_tool() -> None:
    host = ui.ask("Target", "google.com")
    import shutil

    if os.name == "nt":
        cmd = ["tracert", "-d", "-h", "30", host]
    elif shutil.which("traceroute"):
        cmd = ["traceroute", "-n", host]
    elif shutil.which("tracepath"):
        cmd = ["tracepath", "-n", host]
    else:
        ui.error("traceroute or tracepath not found.")
        return
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="oem" if os.name == "nt" else None, errors="replace")
    assert proc.stdout
    for line in proc.stdout:
        print("  " + line.rstrip())
    proc.wait()


@tool("network", "net-mac-vendor", "MAC address vendor", "Who made the network card (start of the MAC address)", ("mac", "valmistaja", "vendor"))
def mac_tool() -> None:
    mac = ui.ask("MAC address")
    try:
        vendor = http_get(f"https://api.macvendors.com/{quote(mac)}", timeout=10).decode()
        print(ui.bold(f"  {vendor}"))
    except NetError:
        ui.warn("Vendor not found (or the MAC is randomised for privacy).")
    first = int(re.sub(r"[^0-9a-fA-F]", "", mac)[:2] or "0", 16)
    if first & 2:
        ui.info("Locally administered address – often a phone's random MAC.")
