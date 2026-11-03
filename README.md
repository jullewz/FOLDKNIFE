# 🔪 Foldknife – a Python multitool

Foldknife is a command-line multitool: **226 tools in 14 categories**, about **17,000 lines** of Python –
and not a single external dependency. Everything runs on the Python standard library on Windows,
macOS and Linux.

```
███████╗ ██████╗ ██╗     ██████╗ ██╗  ██╗███╗   ██╗██╗███████╗███████╗
██╔════╝██╔═══██╗██║     ██╔══██╗██║ ██╔╝████╗  ██║██║██╔════╝██╔════╝
█████╗  ██║   ██║██║     ██║  ██║█████╔╝ ██╔██╗ ██║██║█████╗  █████╗
██╔══╝  ██║   ██║██║     ██║  ██║██╔═██╗ ██║╚██╗██║██║██╔══╝  ██╔══╝
██║     ╚██████╔╝███████╗██████╔╝██║  ██╗██║ ╚████║██║██║     ███████╗
╚═╝      ╚═════╝ ╚══════╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚═╝     ╚══════╝
```

## Quick start

1. Install **Python 3.9 or newer**: <https://www.python.org/downloads/>
   (on Windows, tick **"Add python.exe to PATH"** during installation).
2. Extract the zip into a folder.
3. Start it:
   - **Windows:** double-click `Foldknife.bat` – or run `python foldknife.py` in a terminal
   - **macOS / Linux:** `python3 foldknife.py` or `./foldknife.sh`

You get the best colours and symbols in **Windows Terminal** (the default on Windows 11).

## Usage

In the menu, pick a category by number and then a tool by number. Also:

| Key | Action |
|---|---|
| `s` | search tools by word (e.g. *password*, *image*, *game*) |
| `f` | favourites – add one in a category menu by typing `*3` |
| `r` / `m` | recently used / most used |
| `x` | surprise me (random tool) |
| `o` | settings (colours, name, backup, delete data) |
| `i` | about |
| `q` | quit |
| `Ctrl+C` | stops a tool and returns to the menu |

Text fields accept a file if you type `@path/to/file.txt`, and an empty line opens multi-line input.
You can also drag a file path into the terminal with the mouse.

### Quick commands

The most common things work straight from the command line without the menu:

```bash
python foldknife.py calc "2^10 + sqrt(16)"      # → 1028
python foldknife.py convert 10 km mi            # → 10 km = 6.213712 mi
python foldknife.py password 24 5               # five 24-character passwords
python foldknife.py hash file.zip sha256
python foldknife.py qr https://example.com      # QR code straight in the terminal
python foldknife.py weather London
python foldknife.py hetu 131052-308T            # Finnish personal identity code
python foldknife.py refnum 1234                 # Finnish payment reference number
python foldknife.py dice 4d6kh3
python foldknife.py ip
python foldknife.py list                        # all tools with their ids
python foldknife.py games-tetris                # any tool can be run by its id
```

Run `python foldknife.py --help` for the full list.

## Where is data stored?

Tasks, notes, high scores, budget, the password vault etc. are stored in `~/.foldknife`
(on Windows `C:\Users\<name>\.foldknife`). You can change the folder with the `FOLDKNIFE_HOME` environment variable.
Settings can back up everything into a zip file.

## Optional extras

Foldknife needs nothing installed, but these extend it:

- `pip install pillow` – the image tools then also handle JPEG, GIF and WEBP (PNG/BMP always work).
- `pip install tzdata` – accurate daylight saving times for the world clock on Windows.
- On Linux, text to speech needs `espeak-ng` and the clipboard needs `xclip` or `wl-clipboard`.

## A few notes

- **The password vault and file encryption** use PBKDF2 key derivation, a BLAKE2 keystream and HMAC-SHA256
  integrity checks. The construction is standard, but this is a hobby project, not audited crypto software –
  keep your most important secrets in a proper password manager.
- **The port checker and network tools** are meant for inspecting your own devices and servers.
- Tools that use the internet (weather, currencies, crypto, speed test, IP info) fetch data from free
  APIs (wttr.in, frankfurter.app, CoinGecko, Cloudflare, ipinfo.io) – they may occasionally be down.
- The **Finland tools** category (identity code, business ID, IBAN, reference numbers, bank barcodes, VAT,
  number words, holidays, hyphenation, proverbs) is specific to Finland; the VAT calculator uses the rates
  in force from 1 Jan 2026 (25.5 %, 13.5 %, 10 %).

## Adding your own tool

Create a new file `foldknife/tools/mine.py`, add the module name to the `MODULES` list in `foldknife/tools/__init__.py`
and write:

```python
from ..core import ui
from ..core.registry import tool


@tool("fun", "fun-greeting", "Greeting", "Says hello", ("hello", "hi"))
def greeting() -> None:
    name = ui.ask("What's your name?", "friend")
    ui.success(f"Hello, {name}!")
```

UI helpers (`ui.ask`, `ui.ask_int`, `ui.choose`, `ui.table`, `ui.box`, `ui.bar_chart`, `ui.Spinner`…)
live in `foldknife/core/ui.py`.

## Tests

```bash
python -m unittest discover tests
```

## All tools

### Files and folders (18)

- **Back up a folder** (`files-backup`) – Compresses a folder into a timestamped zip file
- **Bulk rename** (`files-bulk-rename`) – Rename dozens of files at once with a preview
- **Compare files** (`files-compare-files`) – Are two files identical? Shows the differences line by line
- **Compare folders** (`files-compare-folders`) – Which files are missing or differ between two folders
- **Disk usage** (`files-disk-usage`) – Where did the space go? Folder sizes as a chart
- **Empty folders** (`files-empty-folders`) – Finds and deletes empty folders
- **File info** (`files-file-info`) – Size, times, permissions, SHA-256 and the real type
- **File search** (`files-file-search`) – Find by name, size and age (e.g. *.mp4;*.mkv)
- **Find duplicates** (`files-find-duplicates`) – Finds files with identical content and frees up space
- **Folder tree** (`files-folder-tree`) – Draws a folder's structure as a tree
- **Largest files** (`files-largest-files`) – Shows the biggest files in a folder
- **Mirror a folder** (`files-mirror`) – Copies new and changed files to another folder (one-way)
- **Organise by type** (`files-organise-by-type`) – Moves files into subfolders: Images, Videos…
- **Recently modified** (`files-recently-modified`) – Which files have changed recently
- **Search text in files** (`files-grep`) – Searches a word or regex in all text files
- **Split / join a file** (`files-split-join`) – Split a big file into parts (e.g. for Discord's limit) and join them back
- **Statistics by extension** (`files-extension-stats`) – How many and how much space each file type takes
- **Zip tools** (`files-zip-tools`) – Compress, extract and list zip archives safely

### Text (18)

- **Character counter and limits** (`text-char-limits`) – Does the text fit in a tweet, an SMS or a Discord message?
- **Character info** (`text-character-info`) – Unicode name, code point, UTF-8 bytes and category for every character
- **Clean text** (`text-clean-text`) – Removes extra spaces, HTML, invisible characters and smart quotes
- **Compare texts** (`text-compare-texts`) – Shows the differences between two texts word by word or line by line
- **Extract from text** (`text-extract`) – Emails, links, phone numbers, hashtags, IPs…
- **Fancy fonts (Unicode)** (`text-fancy-fonts`) – 𝗕𝗼𝗹𝗱, 𝓈𝒸𝓇𝒾𝓅𝓉, ⓒⓘⓡⓒⓛⓔⓢ, ｗｉｄｅ, ʇxǝʇ uʍop ǝpısdn – for Discord and social media
- **Find and replace** (`text-find-replace`) – Replace text normally or with regex (also in a file)
- **Fix broken characters (mojibake)** (`text-fix-mojibake`) – Turns 'cafÃ©' back into 'café'
- **Letter case and programming styles** (`text-case`) – UPPER, lower, camelCase, snake_case, kebab-case…
- **Line tools** (`text-line-tools`) – Sort, deduplicate, shuffle, number and clean lines
- **Lorem ipsum and nonsense** (`text-lorem-ipsum`) – Filler text in Latin or as silly English sentences
- **Morse code** (`text-morse-code`) – Text to Morse and back
- **Palindromes and anagrams** (`text-palindromes`) – Is the text a palindrome? Are the words anagrams of each other?
- **Reverse text** (`text-reverse-text`) – Characters, words or lines backwards
- **Text statistics** (`text-statistics`) – Characters, words, sentences, reading time and LIX readability
- **URL slug and file name** (`text-slug`) – Turns text into a clean URL or file name
- **Word frequencies** (`text-word-frequencies`) – The most common words and their share as a chart
- **Wrap and align** (`text-wrap`) – Wraps text to a given width and aligns it left, right or centre

### Hashing and encryption (15)

- **Caesar cracker** (`crypto-caesar-cracker`) – Breaks a Caesar cipher with letter frequencies and shows all shifts
- **Classical ciphers** (`crypto-classical-ciphers`) – Caesar, ROT13, Vigenère, Atbash, Affine, rail fence, XOR, Bacon, Polybius
- **Encodings** (`crypto-encodings`) – Base64, Base32, hex, URL, HTML, binary, punycode, ROT13…
- **Encrypt a file with a password** (`crypto-encrypt-file`) – Encrypt or decrypt a file (PBKDF2 + keystream + HMAC)
- **Encrypt a message** (`crypto-encrypt-message`) – Encrypts text to send to a friend (both need Foldknife)
- **File checksum** (`crypto-file-checksum`) – Compute or verify a downloaded file's SHA-256/MD5
- **Hash identifier** (`crypto-hash-identifier`) – Guesses a hash type (MD5, SHA-1, bcrypt, Argon2…)
- **Hashes of text** (`crypto-hash`) – MD5, SHA-1, SHA-256, SHA-512, SHA-3, BLAKE2, CRC32…
- **HMAC signature** (`crypto-hmac-signature`) – Compute a message HMAC (e.g. verifying webhooks)
- **Invisible message** (`crypto-invisible-message`) – Hides a secret message as invisible characters inside normal text
- **JWT decoder** (`crypto-jwt-decoder`) – Shows the contents and expiry of a JSON Web Token
- **Passphrase generator** (`crypto-passphrase-generator`) – Easy to remember passphrases
- **Password generator** (`crypto-password-generator`) – Strong random passwords using the secrets module
- **Password strength** (`crypto-password-strength`) – Estimates how fast a password could be cracked
- **UUID, ULID and tokens** (`crypto-ids-and-tokens`) – UUID v1/v4/v7, ULID, NanoID, API keys and PIN codes

### Maths and calculators (17)

- **Body mass index (BMI)** (`math-bmi`) – Calculates an adult's BMI
- **Calculator** (`math-calculator`) – Functions, variables, ans, degrees/radians, fractions, factorial, percentages
- **Combinatorics and probability** (`math-combinatorics`) – Factorial, nCr, nPr, lottery odds and the birthday paradox
- **Derivative and integral** (`math-calculus`) – Numerical derivative, integral, extrema and area
- **Equation solver** (`math-equation-solver`) – Quadratic equations, systems of equations and f(x) = 0 numerically
- **Function plotter** (`math-function-plotter`) – Plots a function in the terminal, e.g. sin(x); x^2/10
- **Geometry** (`math-geometry`) – Areas, perimeters, volumes and Pythagoras
- **Grade average** (`math-grade-average`) – Finnish school grades (8+, 9-, 7½) and credit-weighted averages
- **Loan calculator** (`math-loan-calculator`) – Monthly payment, interest and schedule (annuity or straight-line)
- **Matrix calculator** (`math-matrices`) – Determinant, inverse, product, transpose, rank – with exact fractions
- **Number properties** (`math-number-properties`) – Everything about a number: divisors, square, Fibonacci, Roman numerals, words…
- **Number sequences** (`math-number-sequences`) – Fibonacci, Collatz, Pascal's triangle, squares, triangular numbers, Catalan numbers
- **Percentage calculator** (`math-percentages`) – Percentages, changes, discounts and increases
- **Primes and factors** (`math-primes-and-factors`) – Is it prime? Factorisation, next prime, list of primes
- **Savings and investment calculator** (`math-savings-calculator`) – Compound interest: how monthly savings grow over the years
- **Statistics calculator** (`math-statistics`) – Mean, median, standard deviation, quartiles, outliers and histogram
- **Times tables and practice** (`math-times-tables`) – A colourful times table and a timed multiplication quiz

### Conversions (12)

- **Calendar** (`convert-calendar`) – Month or year view with week numbers and Finnish public holidays
- **Colour converter and palettes** (`convert-colours`) – HEX ↔ RGB ↔ HSL ↔ CMYK, shades, palettes and contrast check
- **Data formats** (`convert-data-formats`) – CSV ↔ JSON, JSON formatting and validation, XML, INI, query string, Markdown table
- **Date calculator** (`convert-date-calculator`) – Difference, working days, adding, week number, weekday and age
- **Kitchen measures** (`convert-kitchen-measures`) – Decilitres to grams, US cups, spoons and oven temperatures
- **Number bases** (`convert-number-bases`) – Binary, octal, decimal, hex and any base 2–36, two's complement, IEEE 754
- **Roman numerals** (`convert-roman-numerals`) – MMXXVI ↔ 2026
- **Running pace and race times** (`convert-running-pace`) – Pace ↔ speed and predictions for 5 km, 10 km, half marathon, marathon
- **Trip cost calculator** (`convert-trip-cost`) – How much a car trip costs on petrol or electricity, and per passenger
- **Unit converter** (`convert-units`) – Length, mass, volume, temperature, speed, data, energy… (e.g. 10 km mi)
- **Unix timestamps** (`convert-timestamps`) – Timestamp ↔ date, ISO 8601, RFC 2822 and milliseconds
- **World clock and time zones** (`convert-world-clock`) – What time is it in different cities, and converting a time between zones

### Finland tools (12)

- **Bank barcode** (`fi-bank-barcode`) – Create or decode an invoice virtual barcode (54 digits)
- **Business ID** (`fi-business-id`) – Checks a Finnish business ID (Y-tunnus) or computes the check digit for a body
- **Finnish holidays & flag days** (`fi-holidays`) – Public holidays, flag days, Easter, Midsummer and DST for a year
- **Finnish hyphenation** (`fi-hyphenation`) – Splits Finnish text into syllables (ka-la-kuk-ko)
- **Finnish proverbs** (`fi-proverbs`) – A random Finnish proverb (in English translation) or search by word
- **IBAN account number** (`fi-iban`) – Checks an IBAN, formats it and shows the Finnish bank and BIC code
- **Numbers to Finnish words** (`fi-number-words`) – 2026 → kaksituhattakaksikymmentäkuusi, also ordinals and money amounts
- **Personal identity code** (`fi-hetu`) – Checks a Finnish personal identity code and shows date of birth and age (incl. the new 2023 century signs)
- **Phone numbers** (`fi-phone-numbers`) – Formats Finnish phone numbers and makes the international form
- **Reference numbers** (`fi-reference-numbers`) – Create and check Finnish reference numbers, make series and convert to RF format
- **Spelling alphabets** (`fi-spelling-alphabets`) – Spells text for the phone: Aarne, Bertta, Celsius… (and NATO)
- **VAT calculator** (`fi-vat-calculator`) – Finnish VAT 25.5 %, 13.5 % and 10 % – gross ↔ net

### Network (21)

- **Crypto prices** (`net-crypto-prices`) – Bitcoin, Ethereum, Solana… in euros and dollars (CoinGecko)
- **Currency converter** (`net-currency-converter`) – European Central Bank daily rates (e.g. 100 EUR USD)
- **DNS lookup** (`net-dns-lookup`) – A, AAAA, MX, TXT, NS, CNAME, SOA, SRV, CAA and PTR – built-in DNS client
- **Download a file** (`net-download`) – Downloads a file from a URL with a progress bar
- **HTTP check** (`net-http-check`) – Page status, redirects, response time and security headers
- **Internet speed test** (`net-speed-test`) – Download and upload speed plus latency (Cloudflare)
- **IP address info** (`net-ip-info`) – Whose IP is this? Country, city, organisation and reverse DNS
- **LAN-chat** (`net-lan-chat`) – Chat with friends on the same network – one hosts, the others join
- **MAC address vendor** (`net-mac-vendor`) – Who made the network card (start of the MAC address)
- **My IP address** (`net-my-ip`) – LAN and public IP plus estimated location and ISP
- **Ping** (`net-ping`) – Ping a server (ICMP) or measure TCP connect latency to a port
- **Port checker** (`net-port-checker`) – Which ports are open on your own machine, server or router
- **Share a folder on the LAN** (`net-share-folder`) – Starts an HTTP server – friends and phones download with a browser (QR code)
- **Site monitor** (`net-site-monitor`) – Monitor site status and response time in real time
- **SSL certificate** (`net-ssl-certificate`) – Certificate issuer, validity and days remaining
- **Subnet calculator** (`net-subnet-calculator`) – CIDR, network and broadcast address, masks, host count and splitting
- **Traceroute** (`net-traceroute`) – Shows the route and the latency at each hop
- **URL parser** (`net-url-parser`) – Splits a URL into parts and decodes query parameters
- **Wake-on-LAN** (`net-wake-on-lan`) – Wakes a LAN computer with a magic packet
- **Weather** (`net-weather`) – Current weather and a three-day forecast for any city
- **WHOIS** (`net-whois`) – Domain owner and registration info

### System (14)

- **Alarm clock** (`sys-alarm-clock`) – Sounds an alarm at a set time (keep the window open)
- **Benchmark** (`sys-benchmark`) – Measures CPU speed with Python and gives a score (single and all cores)
- **Clipboard tools** (`sys-clipboard-tools`) – Clean up, transform or clear clipboard text
- **Disk drives** (`sys-disk-drives`) – Size and free space of all drives
- **Environment variables and PATH** (`sys-environment`) – Shows variables and checks that PATH folders exist
- **Hosts file** (`sys-hosts-file`) – Shows the active entries in the hosts file
- **Processes** (`sys-processes`) – Programs using the most memory, search and kill
- **Python packages** (`sys-python-packages`) – Installed Python libraries and their versions
- **Scheduled shutdown** (`sys-scheduled-shutdown`) – Shut down or restart the computer on a timer – or cancel it
- **Stopwatch** (`sys-stopwatch`) – Enter = lap, q + Enter = stop
- **System info** (`sys-system-info`) – OS, CPU, memory, GPU, battery and uptime
- **Temp file cleanup** (`sys-temp-file-cleanup`) – Deletes old files from the temp folder and frees space
- **Terminal test** (`sys-terminal-test`) – Does your terminal support colours, Unicode and emoji?
- **Timer** (`sys-timer`) – Egg timer: 5 min, 1h30min, 90s… beeps at the end

### Developer (17)

- **.gitignore generator** (`dev-gitignore`) – Builds a .gitignore file for the chosen languages and tools
- **Code line counter** (`dev-line-counter`) – Counts a project's code, comment and blank lines per language
- **Code timing** (`dev-code-timing`) – Measures how long a Python expression takes with timeit
- **Cron explainer** (`dev-cron-explainer`) – Explains a cron expression in plain English and shows the next run times
- **Encoding and line endings** (`dev-encoding`) – Detects a file's encoding and converts to UTF-8 or switches CRLF ↔ LF
- **File → data URI** (`dev-data-uri`) – Converts an image or file into a base64 data URI for HTML/CSS
- **Git statistics** (`dev-git-statistics`) – Commits by author and weekday plus the most-changed files
- **Hex view** (`dev-hex-view`) – Shows a file's bytes as hex and text (like xxd)
- **HTTP request (mini Postman)** (`dev-http-request`) – Send a GET/POST/PUT/DELETE request with headers and see the response
- **Licence generator** (`dev-licence-generator`) – MIT, ISC, BSD-2, BSD-3 or Unlicense as a ready LICENSE file
- **Markdown → HTML** (`dev-markdown-to-html`) – Converts a Markdown file into a clean HTML page and opens it in the browser
- **Project templates** (`dev-project-templates`) – Creates a ready skeleton: Python package, website, Discord bot or Node.js
- **Regex tester** (`dev-regex-tester`) – Test regular expressions: matches, groups and replacement, coloured
- **Test data generator** (`dev-test-data-generator`) – Made-up Finnish people as CSV or JSON for testing
- **TODO finder** (`dev-todo-finder`) – Finds TODO, FIXME, HACK and XXX markers in code
- **Version numbers (semver)** (`dev-version-numbers`) – Compare versions and bump major/minor/patch
- **Who is using a port?** (`dev-port-owner`) – Finds out which program listens on a port (e.g. 3000 or 8080)

### Data (CSV, JSON, SQLite) (10)

- **Combine CSV files** (`data-combine-csv-files`) – Stacks files with the same shape or joins them on a key column
- **CSV column statistics** (`data-csv-column-statistics`) – Types, blanks, sums, averages and most common values for every column
- **CSV viewer** (`data-csv-viewer`) – Opens a CSV or Excel CSV file as a table (also with ; separators)
- **Excel ↔ CSV** (`data-excel-to-csv`) – Reads an .xlsx file into CSV or makes an .xlsx from CSV – without Excel or libraries
- **Filter and sort CSV** (`data-filter-and-sort-csv`) – Filter rows by conditions, sort and save to a new file
- **Grouping (pivot)** (`data-grouping`) – Sums, averages and counts per group – like an Excel pivot table
- **JSON diff** (`data-json-diff`) – Shows added, removed and changed fields between two JSONs
- **JSON viewer and query** (`data-json-viewer`) – Shows JSON as a colourful tree and fetches values by path (users[*].name)
- **SQLite browser** (`data-sqlite-browser`) – Opens a .db file: tables, schema, SQL queries and CSV export
- **Terminal charts** (`data-terminal-charts`) – Bar, line and pie charts from your own numbers or CSV columns

### Productivity (13)

- **Address book** (`prod-address-book`) – Contacts, upcoming birthdays and export to your phone (vCard)
- **Budget and expenses** (`prod-budget`) – Record income and expenses, see a monthly summary by category
- **Day counters** (`prod-day-counters`) – How many days until Christmas, holidays or a birthday?
- **Decision matrix** (`prod-decision-matrix`) – Hard choice? Score the options with weighted criteria
- **Diary** (`prod-diary`) – Daily entries, mood and search
- **Flashcards** (`prod-flashcards`) – Learn vocabulary and facts with the Leitner box system
- **Habit tracker** (`prod-habit-tracker`) – Track daily habits, streaks and a 30-day grid
- **Lists** (`prod-lists`) – Shopping lists, films to watch, gift ideas – any lists you can tick off
- **Notes** (`prod-notes`) – Write, search, pin and export notes
- **Password vault** (`prod-password-vault`) – Encrypted store for logins – protected by a master password (PBKDF2 + HMAC)
- **Pomodoro timer** (`prod-pomodoro-timer`) – 25 min of work, 5 min break, a long break after every fourth – plus stats
- **Time tracker** (`prod-time-tracker`) – Clock projects and tasks – reports for the day, week and all time
- **To-do list** (`prod-to-do-list`) – Tasks with priorities, due dates and tags (quick add: Buy milk !1 @tomorrow #shop)

### Games (27)

- **2048** (`games-2048`) – Merge equal numbers and aim for the 2048 tile (arrows or WASD)
- **Battleship** (`games-battleship`) – Sink the AI's fleet before it sinks yours
- **Blackjack** (`games-blackjack`) – Get close to 21 against the dealer – with play chips
- **Connect four** (`games-connect-four`) – Drop discs and get four in a row before the AI
- **Dodge** (`games-dodge`) – Dodge the falling rocks for as long as you can (← →)
- **Hangman** (`games-hangman`) – Guess the word one letter at a time before the man is hanged
- **High scores** (`games-high-scores`) – Best scores in every game
- **Higher or lower** (`games-higher-or-lower`) – Guess whether the next card is higher or lower – how long a streak?
- **Mastermind** (`games-mastermind`) – Crack the four-colour code in ten tries
- **Memory** (`games-memory`) – Find the pairs in a 4×4 grid in as few moves as possible
- **Mental maths sprint** (`games-mental-maths-sprint`) – Solve as many sums as you can in 60 seconds
- **Minesweeper** (`games-minesweeper`) – Open squares without hitting mines (e.g. C5 opens, F C5 flags)
- **Number guess** (`games-number-guess`) – Guess the computer's number – or let the computer guess yours
- **Reaction test** (`games-reaction-test`) – Press as soon as the screen turns green – measures your reaction time
- **Reversi (Othello)** (`games-reversi`) – Flip the opponent's discs to your colour – the AI loves corners
- **Rock, paper, scissors** (`games-rock-paper-scissors`) – The AI learns your play style – lizard–Spock version too
- **Slot machine** (`games-slot-machine`) – Spin the reels with play chips – three of a kind wins
- **Snake** (`games-snake`) – Classic snake: eat apples, grow and avoid the walls (arrows/WASD, p = pause, q = quit)
- **Stick game (Nim)** (`games-stick-game`) – Take sticks from the piles – whoever takes the last stick wins. The AI knows the maths!
- **Sudoku** (`games-sudoku`) – Play generated sudokus (unique solution) or solve your own
- **Tetris** (`games-tetris`) – Falling blocks – fill the lines! (arrows, space drops, p pause)
- **Tic-tac-toe** (`games-tic-tac-toe`) – Three in a row – against an unbeatable AI or a friend
- **Trivia quiz** (`games-trivia-quiz`) – General knowledge quiz: Finland, nature, science and the world
- **Typing speed test** (`games-typing-speed-test`) – How many words per minute can you type?
- **Word guess** (`games-word-guess`) – Wordle-style game: guess the five-letter word in six tries
- **Word scramble** (`games-word-scramble`) – Guess the word from scrambled letters – hints cost points
- **Yatzy** (`games-yatzy`) – Nordic Yatzy for 1–4 players: roll, hold dice and collect points

### Fun (19)

- **ASCII art gallery** (`fun-ascii-art-gallery`) – Small ASCII drawings to copy into messages
- **ASCII banner** (`fun-ascii-banner`) – Big coloured letters in the terminal – accented letters too
- **Big clock** (`fun-big-clock`) – Full-screen digital clock
- **Campfire** (`fun-campfire`) – A warm fire effect in the terminal (needs colours)
- **Compliment generator** (`fun-compliment-generator`) – Brighten the day – for yourself or a friend
- **Dice** (`fun-dice`) – RPG dice: 3d6, d20+5, 4d6kh3, d% – with visual dice
- **Excuse generator** (`fun-excuse-generator`) – For when you need a creative explanation (don't use it for real 😉)
- **Game of Life** (`fun-game-of-life`) – Conway's cellular automaton: random start or classic patterns
- **Jokes** (`fun-jokes`) – Puns and programmer jokes
- **Magic 8-ball** (`fun-magic-8-ball`) – Ask a yes/no question – the ball knows
- **Mandelbrot fractal** (`fun-mandelbrot-fractal`) – Explore the fractal: arrows move, + and - zoom
- **Matrix rain** (`fun-matrix-rain`) – Green code rain like in the film
- **Name generator** (`fun-name-generator`) – Fantasy names, gamer tags and band names
- **Nordic flags** (`fun-nordic-flags`) – The flags of Finland, Sweden, Norway, Denmark, Iceland and Åland in colour
- **Rainbow text** (`fun-rainbow-text`) – Colour text as a rainbow or a gradient in the terminal
- **Randomiser** (`fun-randomiser`) – Draw a winner, split teams, flip a coin, lottery numbers or a random number
- **Spinning donut** (`fun-spinning-donut`) – A 3D torus in ASCII – the classic demo effect
- **Talking animal** (`fun-talking-animal`) – A cow, cat, penguin or robot says whatever you want
- **Would you rather?** (`fun-would-you-rather`) – Tough choices to ponder with friends

### Images and sound (13)

- **Colours from an image** (`media-image-colours`) – Picks an image's dominant colours as HEX codes (k-means)
- **Hide a message in an image** (`media-steganography`) – Hides text invisibly in a PNG image's pixels (LSB) and reads it back
- **Image editor** (`media-image-editor`) – Resize, crop, rotate, mirror, greyscale, sepia, blur, pixelate and brightness
- **Image generator** (`media-image-generator`) – Gradients, Mandelbrot images, plasma and an avatar from text (identicon)
- **Image info and EXIF** (`media-image-info`) – Size, format and the data the camera stored – including GPS location if present
- **Image to terminal / ASCII art** (`media-image-to-ascii`) – Show an image as colour blocks in the terminal or convert it to ASCII characters
- **Melody composer** (`media-melody-composer`) – Write notes (C4/4 D4/4 E4/2) or pick a ready folk song – makes a WAV
- **Metronome** (`media-metronome`) – A beat at the chosen BPM or tap the tempo with Enter
- **QR code generator** (`media-qr`) – Links, WiFi passwords, contacts and text as a QR code – to the terminal, PNG or SVG
- **Remove metadata (EXIF/GPS)** (`media-remove-metadata`) – Removes location, camera and other hidden data from an image before sharing
- **Text to speech** (`media-text-to-speech`) – Reads text aloud (Windows, macOS or espeak voices) and can save it
- **Tone generator** (`media-tone-generator`) – Sine, square, saw, triangle or noise to a WAV file (test tones too)
- **WAV editor** (`media-wav-editor`) – Info, reverse, speed, volume, normalise and trim
