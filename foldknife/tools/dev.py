"""Developer tools: line counter, regex, cron, gitignore, project templates, licences, HTTP requests and more."""
from __future__ import annotations

import base64
import calendar
import datetime as dt
import html
import json
import mimetypes
import os
import random
import re
import shutil
import subprocess
import sys
import textwrap
import time
import timeit
import webbrowser
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..core import ui
from ..core.registry import tool
from ..core.utils import http_request, iter_files, offer_copy, offer_save, open_path

# --------------------------------------------------------------------------
# Line counter
# --------------------------------------------------------------------------

# extension → (language, line comment, block comment start, end)
LANGS: dict[str, tuple[str, str | None, str | None, str | None]] = {
    ".py": ("Python", "#", None, None), ".pyw": ("Python", "#", None, None),
    ".js": ("JavaScript", "//", "/*", "*/"), ".mjs": ("JavaScript", "//", "/*", "*/"), ".cjs": ("JavaScript", "//", "/*", "*/"),
    ".ts": ("TypeScript", "//", "/*", "*/"), ".tsx": ("TypeScript JSX", "//", "/*", "*/"), ".jsx": ("JSX", "//", "/*", "*/"),
    ".html": ("HTML", None, "<!--", "-->"), ".htm": ("HTML", None, "<!--", "-->"), ".vue": ("Vue", "//", "<!--", "-->"),
    ".svelte": ("Svelte", "//", "<!--", "-->"), ".css": ("CSS", None, "/*", "*/"), ".scss": ("SCSS", "//", "/*", "*/"),
    ".less": ("Less", "//", "/*", "*/"), ".java": ("Java", "//", "/*", "*/"), ".kt": ("Kotlin", "//", "/*", "*/"),
    ".c": ("C", "//", "/*", "*/"), ".h": ("C/C++ header", "//", "/*", "*/"), ".cpp": ("C++", "//", "/*", "*/"),
    ".cc": ("C++", "//", "/*", "*/"), ".cxx": ("C++", "//", "/*", "*/"), ".hpp": ("C++ header", "//", "/*", "*/"),
    ".cs": ("C#", "//", "/*", "*/"), ".go": ("Go", "//", "/*", "*/"), ".rs": ("Rust", "//", "/*", "*/"),
    ".rb": ("Ruby", "#", "=begin", "=end"), ".php": ("PHP", "//", "/*", "*/"), ".swift": ("Swift", "//", "/*", "*/"),
    ".sh": ("Shell", "#", None, None), ".bash": ("Shell", "#", None, None), ".zsh": ("Shell", "#", None, None),
    ".ps1": ("PowerShell", "#", "<#", "#>"), ".bat": ("Batch", "rem", None, None), ".cmd": ("Batch", "rem", None, None),
    ".lua": ("Lua", "--", "--[[", "]]"), ".sql": ("SQL", "--", "/*", "*/"), ".json": ("JSON", None, None, None),
    ".yml": ("YAML", "#", None, None), ".yaml": ("YAML", "#", None, None), ".toml": ("TOML", "#", None, None),
    ".xml": ("XML", None, "<!--", "-->"), ".md": ("Markdown", None, None, None), ".dart": ("Dart", "//", "/*", "*/"),
    ".r": ("R", "#", None, None), ".gd": ("GDScript", "#", None, None), ".scala": ("Scala", "//", "/*", "*/"),
    ".hs": ("Haskell", "--", "{-", "-}"), ".ex": ("Elixir", "#", None, None), ".exs": ("Elixir", "#", None, None),
    ".pl": ("Perl", "#", None, None), ".jl": ("Julia", "#", "#=", "=#"), ".zig": ("Zig", "//", None, None),
    ".nim": ("Nim", "#", "#[", "]#"), ".ino": ("Arduino", "//", "/*", "*/"), ".m": ("Objective-C/MATLAB", "//", "/*", "*/"),
}


def count_lines(path: Path, lang: tuple[str, str | None, str | None, str | None]) -> tuple[int, int, int]:
    """(code, comments, blank)."""
    _, line_c, block_start, block_end = lang
    code = comment = blank = 0
    in_block = False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    blank += 1
                    continue
                if in_block:
                    comment += 1
                    if block_end and block_end in line:
                        in_block = False
                    continue
                if block_start and line.startswith(block_start):
                    comment += 1
                    if not (block_end and block_end in line[len(block_start):]):
                        in_block = True
                    continue
                if line_c and line.lower().startswith(line_c):
                    comment += 1
                    continue
                code += 1
    except OSError:
        pass
    return code, comment, blank


def cloc(root: Path) -> dict[str, list[int]]:
    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # files, code, comments, blank
    for p in iter_files(root):
        lang = LANGS.get(p.suffix.lower())
        if not lang:
            if p.name in ("Makefile", "Dockerfile"):
                lang = (p.name, "#", None, None)
            else:
                continue
        c, k, b = count_lines(p, lang)
        s = stats[lang[0]]
        s[0] += 1
        s[1] += c
        s[2] += k
        s[3] += b
    return dict(sorted(stats.items(), key=lambda kv: -kv[1][1]))


# --------------------------------------------------------------------------
# Cron
# --------------------------------------------------------------------------

CRON_MACROS = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
               "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@hourly": "0 * * * *"}
MONTH_NAMES = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DOW_NAMES = {d: i for i, d in enumerate(["sun", "mon", "tue", "wed", "thu", "fri", "sat"])}
FI_DOW = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _cron_value(s: str, names: dict[str, int] | None) -> int:
    if names and s in names:
        return names[s]
    try:
        return int(s)
    except ValueError:
        raise ValueError(f"Unknown value: {s}") from None


def _parse_field(field: str, lo: int, hi: int, names: dict[str, int] | None = None) -> set[int]:
    values: set[int] = set()
    top = hi + 1 if hi == 6 else hi  # in weekdays 7 = Sunday
    for part in field.lower().split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
            if step < 1:
                raise ValueError("The step must be at least 1.")
        if part in ("*", "?"):
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            start, end = _cron_value(a, names), _cron_value(b, names)
        else:
            start = _cron_value(part, names)
            end = hi if step > 1 else start
        if not (lo <= start <= top and lo <= end <= top and start <= end):
            raise ValueError(f"Value {part} is not between {lo}–{hi}.")
        values.update(range(start, end + 1, step))
    return {0 if (hi == 6 and v == 7) else v for v in values}


class Cron:
    def __init__(self, expr: str) -> None:
        e = CRON_MACROS.get(expr.strip().lower(), expr.strip())
        fields = e.split()
        if len(fields) != 5:
            raise ValueError("A cron expression has 5 fields: minute hour day month weekday.")
        self.raw = fields
        self.minutes = _parse_field(fields[0], 0, 59)
        self.hours = _parse_field(fields[1], 0, 23)
        self.days = _parse_field(fields[2], 1, 31)
        self.months = _parse_field(fields[3], 1, 12, MONTH_NAMES)
        self.dows = _parse_field(fields[4], 0, 6, DOW_NAMES)
        self.dom_any = fields[2] in ("*", "?")
        self.dow_any = fields[4] in ("*", "?")

    def day_matches(self, d: dt.date) -> bool:
        dom_ok = d.day in self.days
        dow_ok = (d.isoweekday() % 7) in self.dows
        if self.dom_any and self.dow_any:
            return True
        if self.dom_any:
            return dow_ok
        if self.dow_any:
            return dom_ok
        return dom_ok or dow_ok

    def next_runs(self, start: dt.datetime, n: int = 5) -> list[dt.datetime]:
        out: list[dt.datetime] = []
        t = start.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
        limit = start + dt.timedelta(days=366 * 5)
        while len(out) < n and t < limit:
            if t.month not in self.months:
                y, m = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
                t = dt.datetime(y, m, 1)
                continue
            if not self.day_matches(t.date()):
                t = dt.datetime(t.year, t.month, t.day) + dt.timedelta(days=1)
                continue
            if t.hour not in self.hours:
                t = t.replace(minute=0) + dt.timedelta(hours=1)
                continue
            if t.minute not in self.minutes:
                t += dt.timedelta(minutes=1)
                continue
            out.append(t)
            t += dt.timedelta(minutes=1)
        return out

    def describe(self) -> str:
        m, h, d, mo, w = self.raw
        parts = []
        if m == "*" and h == "*":
            parts.append("every minute")
        elif m.startswith("*/") and h == "*":
            parts.append(f"every {m[2:]} minutes")
        elif h.startswith("*/") and m.isdigit():
            parts.append(f"every {h[2:]} hours at minute {m}")
        elif h == "*" and m.isdigit():
            parts.append(f"every hour at minute {m}")
        elif m.isdigit() and h.isdigit():
            parts.append(f"at {int(h):02d}:{int(m):02d}")
        else:
            parts.append(f"minutes {sorted(self.minutes)[:8]}, hours {sorted(self.hours)[:12]}")
        if not self.dow_any:
            names = [FI_DOW[x] + "s" for x in sorted(self.dows)]
            parts.append("weekdays: " + ", ".join(FI_DOW[x] for x in sorted(self.dows)))
        if not self.dom_any:
            parts.append("on days of the month " + ", ".join(map(str, sorted(self.days))))
        if mo != "*":
            parts.append("in months " + ", ".join(calendar.month_abbr[x] for x in sorted(self.months)))
        if self.dom_any and self.dow_any and mo == "*" and len(parts) == 1 and not parts[0].startswith(("every", "minutes")) and "every" not in parts[0]:
            parts.insert(0, "every day")
        return ", ".join(parts)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

GITIGNORE = {
    "Python": "__pycache__/\n*.py[cod]\n*.egg-info/\n.eggs/\nbuild/\ndist/\n.venv/\nvenv/\nenv/\n.pytest_cache/\n.mypy_cache/\n.ruff_cache/\n.coverage\nhtmlcov/\n.ipynb_checkpoints/\n",
    "Node.js": "node_modules/\nnpm-debug.log*\nyarn-error.log*\npnpm-debug.log*\n.npm/\ndist/\nbuild/\n.next/\n.nuxt/\n.cache/\ncoverage/\n",
    "Java": "*.class\n*.jar\n*.war\ntarget/\nbuild/\n.gradle/\nout/\n*.log\n",
    "C / C++": "*.o\n*.obj\n*.exe\n*.dll\n*.so\n*.dylib\n*.a\n*.lib\nbuild/\ncmake-build-*/\nCMakeFiles/\nCMakeCache.txt\n",
    "C# / .NET": "bin/\nobj/\n*.user\n*.suo\n.vs/\n*.nupkg\nTestResults/\n",
    "Unity": "[Ll]ibrary/\n[Tt]emp/\n[Oo]bj/\n[Bb]uild/\n[Bb]uilds/\n[Ll]ogs/\n[Uu]ser[Ss]ettings/\n*.csproj\n*.sln\n*.pidb\n*.pdb\n*.mdb\n*.apk\n*.unitypackage\n",
    "Godot": ".godot/\n.import/\nexport.cfg\nexport_presets.cfg\n*.translation\n",
    "Rust": "target/\nCargo.lock\n**/*.rs.bk\n",
    "Go": "*.exe\n*.test\n*.out\nvendor/\ngo.work\n",
    "Secrets (.env)": ".env\n.env.*\n!.env.example\n*.pem\n*.key\nconfig.local.*\nsecrets.json\n",
    "VS Code": ".vscode/*\n!.vscode/settings.json\n!.vscode/extensions.json\n",
    "JetBrains": ".idea/\n*.iml\n",
    "Windows": "Thumbs.db\nehthumbs.db\nDesktop.ini\n$RECYCLE.BIN/\n*.lnk\n",
    "macOS": ".DS_Store\n.AppleDouble\n.LSOverride\n._*\n",
    "Linux": "*~\n.directory\n.Trash-*\n",
    "Discord bot": ".env\n*.db\n*.sqlite3\nlogs/\n__pycache__/\n.venv/\n",
}

LICENSES = {
    "MIT": """MIT License

Copyright (c) {year} {name}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""",
    "ISC": """ISC License

Copyright (c) {year} {name}

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
""",
    "BSD-2-Clause": """BSD 2-Clause License

Copyright (c) {year}, {name}

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
""",
    "Unlicense": """This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org>
""",
}
LICENSES["BSD-3-Clause"] = LICENSES["BSD-2-Clause"].replace("BSD 2-Clause", "BSD 3-Clause").replace(
    "   and/or other materials provided with the distribution.\n",
    "   and/or other materials provided with the distribution.\n\n"
    "3. Neither the name of the copyright holder nor the names of its\n"
    "   contributors may be used to endorse or promote products derived from\n"
    "   this software without specific prior written permission.\n")


def project_files(kind: str, name: str) -> dict[str, str]:
    pkg = re.sub(r"\W+", "_", name.lower()).strip("_") or "project"
    year = dt.date.today().year
    if kind == "python":
        return {
            "README.md": f"# {name}\n\nDescription here.\n\n## Usage\n\n```bash\npython -m {pkg}\n```\n",
            "pyproject.toml": textwrap.dedent(f"""\
                [project]
                name = "{pkg}"
                version = "0.1.0"
                description = "{name}"
                requires-python = ">=3.9"

                [project.scripts]
                {pkg} = "{pkg}.__main__:main"

                [build-system]
                requires = ["setuptools>=61"]
                build-backend = "setuptools.build_meta"
                """),
            f"src/{pkg}/__init__.py": f'"""{name}."""\n__version__ = "0.1.0"\n',
            f"src/{pkg}/__main__.py": "def main() -> None:\n    print(\"Hello world!\")\n\n\nif __name__ == \"__main__\":\n    main()\n",
            "tests/test_perus.py": f"from {pkg} import __version__\n\n\ndef test_versionn():\n    assert __version__ == \"0.1.0\"\n",
            ".gitignore": GITIGNORE["Python"],
        }
    if kind == "web":
        return {
            "index.html": textwrap.dedent(f"""\
                <!doctype html>
                <html lang="en">
                <head>
                  <meta charset="utf-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1">
                  <title>{html.escape(name)}</title>
                  <link rel="stylesheet" href="style.css">
                </head>
                <body>
                  <header><h1>{html.escape(name)}</h1></header>
                  <main>
                    <p>Welcome! Edit index.html, style.css and script.js.</p>
                    <button id="button">Click me</button>
                    <p id="counter">0</p>
                  </main>
                  <script src="script.js"></script>
                </body>
                </html>
                """),
            "style.css": ":root { --bg: #111827; --fg: #f9fafb; --accent: #f59e0b; }\n"
                         "* { box-sizing: border-box; }\nbody { margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--fg); }\n"
                         "header, main { max-width: 720px; margin: 0 auto; padding: 1.5rem; }\n"
                         "button { background: var(--accent); border: 0; padding: .7rem 1.2rem; border-radius: .5rem; font-weight: 600; cursor: pointer; }\n",
            "script.js": "let n = 0;\ndocument.getElementById('button').addEventListener('click', () => {\n"
                         "  n += 1;\n  document.getElementById('counter').textContent = n;\n});\n",
        }
    if kind == "discord":
        return {
            "bot.py": textwrap.dedent("""\
                import os

                import discord
                from discord.ext import commands

                intents = discord.Intents.default()
                intents.message_content = True
                bot = commands.Bot(command_prefix="!", intents=intents)


                @bot.event
                async def on_ready():
                    print(f"Logged in as {bot.user}")


                @bot.command()
                async def ping(ctx):
                    await ctx.send(f"Pong! {round(bot.latency * 1000)} ms")


                bot.run(os.environ["DISCORD_TOKEN"])
                """),
            "requirements.txt": "discord.py>=2.4\n",
            ".env.example": "DISCORD_TOKEN=paste-your-token-here\n",
            ".gitignore": GITIGNORE["Discord bot"],
            "README.md": f"# {name}\n\n1. `pip install -r requirements.txt`\n2. Set the DISCORD_TOKEN environment variable\n3. `python bot.py`\n",
        }
    if kind == "node":
        return {
            "package.json": json.dumps({"name": pkg.replace("_", "-"), "version": "0.1.0", "type": "module", "main": "index.js",
                                        "scripts": {"start": "node index.js"}, "license": "MIT"}, indent=2) + "\n",
            "index.js": "console.log('Hello world!');\n",
            ".gitignore": GITIGNORE["Node.js"],
            "README.md": f"# {name}\n\n```bash\nnpm start\n```\n",
            "LICENSE": LICENSES["MIT"].format(year=year, name=name),
        }
    raise ValueError(kind)


# --------------------------------------------------------------------------
# Other helpers
# --------------------------------------------------------------------------

def hexdump(data: bytes, offset: int = 0, width: int = 16) -> list[str]:
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hexpart = " ".join(f"{b:02x}" for b in chunk)
        hexpart = hexpart[:width * 3 // 2 - 1] + " " + hexpart[width * 3 // 2 - 1:] if len(chunk) > width // 2 else hexpart
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{ui.gray(f'{offset + i:08x}')}  {hexpart.ljust(width * 3)}  {ui.cyan(asc)}")
    return lines


SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$")


def parse_semver(v: str) -> tuple[int, int, int, tuple[Any, ...], str]:
    m = SEMVER_RE.match(v.strip())
    if not m:
        raise ValueError(f"Not semver: {v} (e.g. 1.4.2 or 2.0.0-beta.1)")
    pre = tuple(int(x) if x.isdigit() else x for x in m.group(4).split(".")) if m.group(4) else ()
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), pre, m.group(5) or ""


def semver_key(v: str) -> tuple[Any, ...]:
    major, minor, patch, pre, _ = parse_semver(v)
    pre_key = tuple((0, x) if isinstance(x, int) else (1, x) for x in pre)
    return (major, minor, patch, 1 if not pre else 0, pre_key)


FI_FIRST = ["Aino", "Eetu", "Emma", "Elias", "Sofia", "Leo", "Olivia", "Oliver", "Aada", "Onni", "Helmi", "Väinö",
            "Linnea", "Eino", "Ella", "Toivo", "Lilja", "Leevi", "Venla", "Niilo", "Pihla", "Joel", "Iida", "Matti",
            "Anni", "Juha", "Maria", "Mikko", "Laura", "Jari", "Sanna", "Timo", "Kaisa", "Antti", "Heidi", "Pekka"]
FI_LAST = ["Korhonen", "Virtanen", "Mäkinen", "Nieminen", "Mäkelä", "Hämäläinen", "Laine", "Heikkinen", "Koskinen",
           "Järvinen", "Lehtonen", "Lehtinen", "Saarinen", "Salminen", "Heinonen", "Niemi", "Heikkilä", "Kinnunen",
           "Salonen", "Turunen", "Salo", "Laitinen", "Tuominen", "Rantanen", "Karjalainen", "Jokinen", "Mattila",
           "Savolainen", "Lahtinen", "Ahonen"]
FI_CITIES = [("Helsinki", "00"), ("Espoo", "02"), ("Tampere", "33"), ("Vantaa", "01"), ("Oulu", "90"), ("Turku", "20"),
             ("Jyväskylä", "40"), ("Kuopio", "70"), ("Lahti", "15"), ("Pori", "28"), ("Joensuu", "80"),
             ("Lappeenranta", "53"), ("Hämeenlinna", "13"), ("Vaasa", "65"), ("Rovaniemi", "96"), ("Seinäjoki", "60")]
FI_STREETS = ["Mannerheimintie", "Hämeenkatu", "Kauppakatu", "Koulukatu", "Rantatie", "Kirkkokatu", "Puistokatu",
              "Asemakatu", "Koivukuja", "Mäntytie", "Kuusitie", "Pajutie", "Myllytie", "Satamakatu"]


def fake_person(rng: random.Random) -> dict[str, Any]:
    first, last = rng.choice(FI_FIRST), rng.choice(FI_LAST)
    city, prefix = rng.choice(FI_CITIES)
    trans = str.maketrans("äöåÄÖÅ", "aoaAOA")
    born = dt.date(1950, 1, 1) + dt.timedelta(days=rng.randint(0, 365 * 55))
    return {"first_name": first, "last_name": last,
            "email": f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}@example.com".translate(trans),
            "phone": f"+358 40 {rng.randint(100, 999)} {rng.randint(1000, 9999)}",
            "street": f"{rng.choice(FI_STREETS)} {rng.randint(1, 120)}", "postcode": f"{prefix}{rng.randint(100, 999)}",
            "city": city, "birthdate": born.isoformat(), "username": f"{first.lower()}{rng.randint(10, 9999)}".translate(trans),
            "balance": round(rng.uniform(-500, 10000), 2)}


def markdown_to_html(md: str) -> str:
    """Lightweight Markdown converter: headings, bold, italics, code, links, images, lists, quotes."""
    def inline(text: str) -> str:
        text = html.escape(text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", text)
        text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
        return text

    out: list[str] = []
    lines = md.splitlines()
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            flush()
            lang = line[3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            out.append(f'<pre><code class="{html.escape(lang)}">' + html.escape("\n".join(code)) + "</code></pre>")
        elif m := re.match(r"^(#{1,6})\s+(.*)", line):
            flush()
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif re.match(r"^\s*([-*_])\s*\1\s*\1[\s\1]*$", line):
            flush()
            out.append("<hr>")
        elif re.match(r"^\s*[-*+]\s+", line) or re.match(r"^\s*\d+[.)]\s+", line):
            flush()
            ordered = bool(re.match(r"^\s*\d+[.)]\s+", line))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines) and (re.match(r"^\s*[-*+]\s+", lines[i]) or re.match(r"^\s*\d+[.)]\s+", lines[i])):
                items.append("<li>" + inline(re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", lines[i])) + "</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        elif line.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip("> "))
                i += 1
            out.append("<blockquote>" + inline(" ".join(quote)) + "</blockquote>")
            continue
        elif not line.strip():
            flush()
        else:
            para.append(line.strip())
        i += 1
    flush()
    return "\n".join(out)


HTML_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body{{max-width:760px;margin:2rem auto;padding:0 1rem;font:16px/1.65 system-ui,sans-serif;color:#1f2933;background:#fbfbf8}}
code{{background:#eef0f2;padding:.1em .35em;border-radius:4px}} pre{{background:#1f2933;color:#e5e7eb;padding:1rem;overflow:auto;border-radius:8px}}
pre code{{background:none;color:inherit}} blockquote{{border-left:4px solid #f59e0b;margin:0;padding-left:1rem;color:#52606d}}
img{{max-width:100%}} a{{color:#b45309}}
</style></head><body>
{body}
</body></html>
"""


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("dev", "dev-line-counter", "Code line counter", "Counts a project's code, comment and blank lines per language",
      ("cloc", "rivit", "koodi", "loc"))
def cloc_tool() -> None:
    root = ui.ask_path("Project folder", kind="dir", default=".")
    with ui.Spinner("Counting lines"):
        stats = cloc(root)
    if not stats:
        ui.info("No known source files found.")
        return
    rows = [(lang, f, c, k, b) for lang, (f, c, k, b) in stats.items()]
    total = [sum(r[i] for r in rows) for i in range(1, 5)]
    rows.append((ui.bold("Total"), *[ui.bold(str(t)) for t in total]))
    ui.table(rows, ["Language", "Files", "Code", "Comments", "Blank"], align=["<", ">", ">", ">", ">"])
    ui.bar_chart([(lang, v[1]) for lang, v in list(stats.items())[:10]])


@tool("dev", "dev-todo-finder", "TODO finder", "Finds TODO, FIXME, HACK and XXX markers in code", ("todo", "fixme", "hack"))
def todo_tool() -> None:
    root = ui.ask_path("Project folder", kind="dir", default=".")
    rx = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG|OPTIMIZE)\b[:\s]*(.*)", re.IGNORECASE)
    counts: Counter[str] = Counter()
    lines = []
    for p in iter_files(root, extensions=list(LANGS)):
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                for no, line in enumerate(fh, 1):
                    m = rx.search(line)
                    if m:
                        tag = m.group(1).upper()
                        counts[tag] += 1
                        color = "bright_red" if tag in ("FIXME", "BUG") else "bright_yellow"
                        lines.append(f"{ui.c(tag.ljust(8), color)} {ui.gray(f'{p.relative_to(root)}:{no}')}  {m.group(2).strip()[:100]}")
        except OSError:
            continue
    ui.paginate(lines)
    ui.info(", ".join(f"{k}: {v}" for k, v in counts.most_common()) or "No markers – tidy!")


@tool("dev", "dev-regex-tester", "Regex tester", "Test regular expressions: matches, groups and replacement, coloured",
      ("regex", "regexp", "regular expression", "pattern"))
def regex_tool() -> None:
    pattern = ui.ask("Pattern", r"(\w+)@(\w+)\.com")
    flags_raw = ui.ask("Flags (i = ignore case, m = multiline, s = dot matches newline, x = verbose)", allow_empty=True)
    flags = 0
    for ch, fl in (("i", re.IGNORECASE), ("m", re.MULTILINE), ("s", re.DOTALL), ("x", re.VERBOSE)):
        if ch in flags_raw.lower():
            flags |= fl
    try:
        rx = re.compile(pattern, flags)
    except re.error as exc:
        ui.error(f"Invalid pattern: {exc}")
        return
    text = ui.get_text("Test text")
    matches = list(rx.finditer(text))
    highlighted = rx.sub(lambda m: ui.c(m.group(0), "bold", "reverse", "bright_green"), text)
    print(highlighted)
    ui.info(f"{len(matches)} matches, {rx.groups} groups")
    for i, m in enumerate(matches[:50], 1):
        groups = " ".join(f"{ui.gray(str(j))}={g!r}" for j, g in enumerate(m.groups(), 1))
        named = " ".join(f"{ui.gray(k)}={v!r}" for k, v in m.groupdict().items())
        print(f"  {i}. {m.group(0)!r} @ {m.start()}–{m.end()}  {groups} {named}")
    repl = ui.ask("Replacement (empty = skip, \\1 = group 1)", allow_empty=True)
    if repl:
        print(ui.bold(rx.sub(repl, text)))


@tool("dev", "dev-cron-explainer", "Cron explainer", "Explains a cron expression in plain English and shows the next run times",
      ("cron", "crontab", "ajastus", "schedule"))
def cron_tool() -> None:
    print(ui.gray("Format: minute hour day month weekday  (e.g. */15 9-17 * * 1-5, @daily)"))
    try:
        cron = Cron(ui.ask("Cron expression", "30 7 * * 1-5"))
    except ValueError as exc:
        ui.error(str(exc))
        return
    print(ui.bold("  " + cron.describe()))
    from ..core.utils import FI_WEEKDAYS

    for t in cron.next_runs(dt.datetime.now(), 10):
        print(f"  {FI_WEEKDAYS[t.weekday()][:3]} {t:%Y-%m-%d %H:%M}")


@tool("dev", "dev-gitignore", ".gitignore generator", "Builds a .gitignore file for the chosen languages and tools", ("git", "gitignore", "ignore"))
def gitignore_tool() -> None:
    names = list(GITIGNORE)
    for i, n in enumerate(names, 1):
        print(f"  {ui.c(str(i).rjust(2), 'bright_yellow')}) {n}")
    raw = ui.ask("Choose numbers separated by commas", "1,10,11,13")
    chosen = [names[int(x) - 1] for x in re.findall(r"\d+", raw) if 0 < int(x) <= len(names)]
    content = "".join(f"# {n}\n{GITIGNORE[n]}\n" for n in chosen)
    print(content)
    target = Path(ui.ask("Save to a file", ".gitignore"))
    if target.exists() and not ui.ask_yes_no("The file already exists. Append to the end?", True):
        return
    with open(target, "a", encoding="utf-8") as fh:
        fh.write(content)
    ui.success(f"Saved: {target.resolve()}")


@tool("dev", "dev-project-templates", "Project templates", "Creates a ready skeleton: Python package, website, Discord bot or Node.js",
      ("template", "pohja", "scaffold", "projekti", "uusi"))
def project_tool() -> None:
    kinds = [("python", "Python package (pyproject, src, tests)"), ("web", "Website (HTML, CSS, JS)"),
             ("discord", "Discord bot (discord.py)"), ("node", "Node.js project")]
    k = kinds[ui.choose("Template", [x[1] for x in kinds])][0]
    name = ui.ask("Project name", "New project")
    base = Path(ui.ask("Folder", re.sub(r"\W+", "-", name.lower()).strip("-") or "project"))
    if base.exists() and any(base.iterdir()):
        ui.error("The folder already exists and isn't empty.")
        return
    for rel, content in project_files(k, name).items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print("  " + ui.green("+") + " " + str(p))
    ui.success(f"Project created in {base.resolve()}")
    if k == "web" and ui.ask_yes_no("Open in a browser?", True):
        webbrowser.open((base / "index.html").resolve().as_uri())


@tool("dev", "dev-licence-generator", "Licence generator", "MIT, ISC, BSD-2, BSD-3 or Unlicense as a ready LICENSE file", ("license", "lisenssi", "mit"))
def license_tool() -> None:
    names = list(LICENSES)
    lic = names[ui.choose("Licence", names, 0)]
    name = ui.ask("Copyright holder", os.environ.get("USERNAME") or os.environ.get("USER") or "Name")
    text = LICENSES[lic].format(year=dt.date.today().year, name=name)
    print(text)
    target = Path(ui.ask("Save", "LICENSE"))
    if target.exists() and not ui.ask_yes_no("Overwrite the existing one?", False):
        return
    target.write_text(text, encoding="utf-8")
    ui.success(f"Saved: {target.resolve()}")


@tool("dev", "dev-http-request", "HTTP request (mini Postman)", "Send a GET/POST/PUT/DELETE request with headers and see the response",
      ("api", "rest", "postman", "curl", "http"))
def http_request_tool() -> None:
    methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]
    method = methods[ui.choose("Method", methods, 0)]
    url = ui.ask("URL", "https://httpbin.org/anything")
    headers: dict[str, str] = {}
    print(ui.gray("Headers as Name: value, an empty line ends."))
    while True:
        line = input("  ").strip()
        if not line:
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    body = None
    if method in ("POST", "PUT", "PATCH"):
        raw = ui.get_text("Body (JSON or text)")
        if raw.strip():
            body = raw.encode("utf-8")
            if raw.strip().startswith(("{", "[")) and "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
    start = time.perf_counter()
    status, resp_headers, data, final = http_request(url, method, body, headers, timeout=30)
    took = (time.perf_counter() - start) * 1000
    color = "bright_green" if status < 300 else "bright_yellow" if status < 400 else "bright_red"
    print(ui.c(f"\n{status}", "bold", color) + ui.gray(f"  {took:.0f} ms · {ui.fmt_bytes(len(data))} · {final}"))
    ui.print_kv(list(resp_headers.items())[:20])
    print()
    text = data.decode("utf-8", errors="replace")
    try:
        text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, ValueError):
        pass
    ui.paginate(text.splitlines()[:2000])
    offer_save(text, "response.json")


@tool("dev", "dev-hex-view", "Hex view", "Shows a file's bytes as hex and text (like xxd)", ("hex", "hexdump", "xxd", "binary"))
def hexdump_tool() -> None:
    path = ui.ask_path("File", kind="file")
    offset = ui.ask_int("Start offset (byte)", 0, 0)
    length = ui.ask_int("How many bytes", 512, 1, 1 << 20)
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read(length)
    ui.paginate(hexdump(data, offset))


@tool("dev", "dev-encoding", "Encoding and line endings", "Detects a file's encoding and converts to UTF-8 or switches CRLF ↔ LF",
      ("encoding", "utf-8", "crlf", "lf", "bom"))
def encoding_tool() -> None:
    path = ui.ask_path("File", kind="file")
    data = path.read_bytes()
    bom = "UTF-8 BOM" if data.startswith(b"\xef\xbb\xbf") else "UTF-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "no"
    try:
        data.decode("utf-8")
        enc = "UTF-8"
    except UnicodeDecodeError:
        enc = "not UTF-8 (probably Windows-1252 / Latin-1)"
    crlf, lf = data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")
    ui.print_kv([("Encoding", enc), ("BOM", bom), ("CRLF line endings", crlf), ("LF line endings", lf)])
    k = ui.choose_optional("Conversion", ["Convert to UTF-8 (without BOM)", "Line endings LF (Unix)", "Line endings CRLF (Windows)"])
    if k is None:
        return
    text = ui.read_text_file(path)
    if k == 1:
        text = text.replace("\r\n", "\n")
    elif k == 2:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    target = Path(ui.ask("Save as", str(path)))
    if target == path and not ui.ask_yes_no("Overwrite the original?", False):
        return
    with open(target, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    ui.success(f"Saved: {target}")


@tool("dev", "dev-version-numbers", "Version numbers (semver)", "Compare versions and bump major/minor/patch", ("semver", "versio", "version"))
def semver_tool() -> None:
    k = ui.choose("Action", ["Sort versions", "Bump a version"])
    try:
        if k == 0:
            vs = re.split(r"[\s,]+", ui.ask("Versions", "1.10.0 1.2.0 1.2.0-beta.2 1.2.0-alpha 2.0.0").strip())
            ordered = sorted(vs, key=semver_key)
            print("  " + "  <  ".join(ordered))
        else:
            v = ui.ask("Current version", "1.4.2")
            major, minor, patch, pre, _ = parse_semver(v)
            ui.print_kv([("Major (breaking change)", f"{major + 1}.0.0"), ("Minor (new feature)", f"{major}.{minor + 1}.0"),
                         ("Patch (fix)", f"{major}.{minor}.{patch + 1}"),
                         ("Pre-release", f"{major}.{minor}.{patch + 1}-beta.1" if not pre else f"{major}.{minor}.{patch}-" +
                          ".".join(str(x) for x in pre[:-1]) + ("." if len(pre) > 1 else "") + str(pre[-1] + 1 if isinstance(pre[-1], int) else f"{pre[-1]}.1"))])
    except ValueError as exc:
        ui.error(str(exc))


@tool("dev", "dev-test-data-generator", "Test data generator", "Made-up Finnish people as CSV or JSON for testing",
      ("fake", "testidata", "mock", "data", "generaattori"))
def fake_data_tool() -> None:
    n = ui.ask_int("Rows", 20, 1, 100000)
    fmt = ui.choose("Format", ["CSV", "JSON"])
    seed = ui.ask("Seed (empty = random)", allow_empty=True)
    rng = random.Random(int(seed) if seed.isdigit() else None)
    rows = [fake_person(rng) for _ in range(n)]
    if fmt == 0:
        import csv
        import io

        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)
        text = buf.getvalue()
    else:
        text = json.dumps(rows, ensure_ascii=False, indent=2)
    ui.paginate(text.splitlines()[:30])
    print(ui.gray("  All data is made up; emails use example.com addresses."))
    offer_save(text, f"testdata.{'csv' if fmt == 0 else 'json'}")


@tool("dev", "dev-markdown-to-html", "Markdown → HTML", "Converts a Markdown file into a clean HTML page and opens it in the browser",
      ("markdown", "md", "html", "readme"))
def markdown_tool() -> None:
    md = ui.get_text("Markdown")
    title = next((line.lstrip("# ").strip() for line in md.splitlines() if line.startswith("#")), "Document")
    page = HTML_PAGE.format(title=html.escape(title), body=markdown_to_html(md))
    target = Path(ui.ask("Save", "document.html"))
    target.write_text(page, encoding="utf-8")
    ui.success(f"Saved: {target.resolve()}")
    if ui.ask_yes_no("Open in a browser?", True):
        webbrowser.open(target.resolve().as_uri())


@tool("dev", "dev-data-uri", "File → data URI", "Converts an image or file into a base64 data URI for HTML/CSS",
      ("data uri", "base64", "kuva", "inline"))
def datauri_tool() -> None:
    path = ui.ask_path("File", kind="file")
    if path.stat().st_size > 5 * 1024 * 1024 and not ui.ask_yes_no("The file is over 5 MB. Continue?", False):
        return
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    uri = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    print(ui.gray(f"  {len(uri)} characters: ") + uri[:120] + "…")
    offer_copy(uri)
    offer_save(uri, path.name + ".txt")


@tool("dev", "dev-git-statistics", "Git statistics", "Commits by author and weekday plus the most-changed files",
      ("git", "commit", "tilasto", "repo"))
def git_tool() -> None:
    if not shutil.which("git"):
        ui.error("Git is not installed.")
        return
    repo = ui.ask_path("Git repository", kind="dir", default=".")
    log = subprocess.run(["git", "-C", str(repo), "log", "--pretty=format:%an|%ad", "--date=short"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if log.returncode != 0:
        ui.error("The folder is not a git repository.")
        return
    entries = [line.split("|") for line in log.stdout.splitlines() if "|" in line]
    ui.info(f"{len(entries)} commits, first {entries[-1][1] if entries else '-'}, latest {entries[0][1] if entries else '-'}")
    ui.bar_chart(Counter(a for a, _ in entries).most_common(10))
    from ..core.utils import FI_WEEKDAYS

    days = Counter(dt.date.fromisoformat(d).weekday() for _, d in entries)
    print()
    ui.bar_chart([(FI_WEEKDAYS[i], days.get(i, 0)) for i in range(7)], color="bright_magenta")
    files = subprocess.run(["git", "-C", str(repo), "log", "--name-only", "--pretty=format:"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    print(ui.bold("\nMost-changed files:"))
    for f, c in Counter(x for x in files.splitlines() if x.strip()).most_common(10):
        print(f"  {str(c).rjust(5)}  {f}")


@tool("dev", "dev-code-timing", "Code timing", "Measures how long a Python expression takes with timeit", ("timeit", "benchmark", "nopeus", "python"))
def timeit_tool() -> None:
    stmt = ui.ask("Python expression", "sum(range(1000))")
    setup = ui.ask("Setup (optional)", "pass")
    try:
        timer = timeit.Timer(stmt, setup)
        n, total = timer.autorange()
        best = min(timer.repeat(repeat=5, number=n)) / n
    except Exception as exc:  # noqa: BLE001 - user code can fail in any way
        ui.error(f"Error in code: {exc}")
        return
    unit, val = ("ns", best * 1e9) if best < 1e-6 else ("µs", best * 1e6) if best < 1e-3 else ("ms", best * 1e3) if best < 1 else ("s", best)
    print(ui.bold(f"  {val:.3f} {unit} / run") + ui.gray(f"  ({n} loops × 5 rounds, best)"))


@tool("dev", "dev-port-owner", "Who is using a port?", "Finds out which program listens on a port (e.g. 3000 or 8080)",
      ("port", "portti", "varattu", "netstat", "lsof"))
def port_owner_tool() -> None:
    port = ui.ask_int("Port", 8080, 1, 65535)
    if os.name == "nt":
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, encoding="oem", errors="replace").stdout
        pids = {line.split()[-1] for line in out.splitlines() if f":{port} " in line and ("LISTENING" in line or "KUUNTELEE" in line)}
        for pid in pids:
            info = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                                  encoding="oem", errors="replace").stdout.strip()
            print(f"  PID {pid}: {info.split(',')[0].strip(chr(34)) if info else '?'}")
        if not pids:
            ui.info("Nobody is listening on the port.")
        return
    cmd = ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"] if shutil.which("lsof") else ["ss", "-ltnp", f"sport = :{port}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = res.stdout.strip()
    print(out if out else ui.gray("  Nobody is listening on the port (or sudo is needed to see other users' processes)."))
