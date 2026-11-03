"""Games: hangman, word guess, quiz, blackjack, slots, rock-paper-scissors, mastermind, memory,
nim, typing speed, mental maths, reaction test and high scores."""
from __future__ import annotations

import datetime as dt
import random
import time
from collections import Counter, defaultdict
from typing import Any

from ..core import keys, ui
from ..core.config import config, load_json, save_json
from ..core.registry import tool

# --------------------------------------------------------------------------
# High scores
# --------------------------------------------------------------------------

LOWER_IS_BETTER = {"Memory", "Reaction test", "Mastermind", "Number guess", "Word guess"}


def record_score(game: str, score: float, name: str | None = None) -> int | None:
    """Saves a score. Returns the rank (1 = best) if it made the top 10."""
    data = load_json("ennatykset", {})
    lst: list[dict[str, Any]] = data.setdefault(game, [])
    entry = {"score": score, "date": dt.date.today().isoformat(), "name": name or config().get("name") or "Player"}
    lst.append(entry)
    lst.sort(key=lambda e: e["score"], reverse=game not in LOWER_IS_BETTER)
    del lst[10:]
    save_json("ennatykset", data)
    if entry in lst:
        rank = lst.index(entry) + 1
        if ui.is_tty():
            if rank == 1 and len(lst) > 1:
                ui.success(f"NEW HIGH SCORE in {game}! 🏆")
            elif rank <= 3:
                ui.success(f"You reached #{rank} in {game}!")
        return rank
    return None


@tool("games", "games-high-scores", "High scores", "Best scores in every game", ("highscore", "high score", "pisteet", "top"))
def scores_tool() -> None:
    data = load_json("ennatykset", {})
    if not data:
        ui.info("No scores yet – go play something!")
        return
    for game, lst in sorted(data.items()):
        print(ui.c(f"\n{game}", "bold", "bright_yellow") + ui.gray("  (lower is better)" if game in LOWER_IS_BETTER else ""))
        for i, e in enumerate(lst[:5], 1):
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
            score = e["score"]
            shown = f"{score:.3f}" if isinstance(score, float) and score < 10 else str(round(score, 2))
            print(f"  {medal} {shown.rjust(10)}  {e['name']}  {ui.gray(e['date'])}")


# --------------------------------------------------------------------------
# Word lists
# --------------------------------------------------------------------------

HANGMAN_WORDS = {
    "Animals": "cat dog horse giraffe elephant crocodile penguin swan squirrel hedgehog bear lynx reindeer seal "
               "dolphin octopus chameleon tortoise parrot frog".split(),
    "Food": "pancake sandwich cinnamon licorice soup lasagne blueberry porridge meatball spaghetti "
            "cheesecake burrito doughnut hamburger icecream chocolate".split(),
    "Places": "london paris tokyo helsinki sydney toronto berlin madrid rome lisbon amsterdam "
              "iceland sahara amazon himalaya".split(),
    "Things": "computer telephone umbrella bookshelf refrigerator snowmobile bicycle kettle sauna "
              "shovel backpack guitar television candle remote".split(),
    "Sports": "hockey baseball skiing basketball football volleyball swimming orienteering "
              "curling rally badminton tennis cycling marathon".split(),
    "Misc": "aurora cottage midsummer sauna rainbow thunderstorm snowman volcano adventure detective "
            "starlight galaxy treasure pirate wizard dragon".split(),
}

GALLOWS = [
    "  ┌───┐\n  │   \n  │   \n  │   \n ═╧═",
    "  ┌───┐\n  │   O\n  │   \n  │   \n ═╧═",
    "  ┌───┐\n  │   O\n  │   │\n  │   \n ═╧═",
    "  ┌───┐\n  │   O\n  │  /│\n  │   \n ═╧═",
    "  ┌───┐\n  │   O\n  │  /│\\\n  │   \n ═╧═",
    "  ┌───┐\n  │   O\n  │  /│\\\n  │  /\n ═╧═",
    "  ┌───┐\n  │   O\n  │  /│\\\n  │  / \\\n ═╧═",
]

SANULI_WORDS = sorted({w for w in """
apple beach bread brick cabin candy chair chalk cheese cloud coral crane crown dance dream eagle earth
fairy flame float flute frost ghost giant glass grape grass heart honey horse house juice knife lemon
light magic maple melon money mouse music night ocean olive otter paint pearl piano pilot pizza plant
queen quiet radio raven river robot salad sauna scarf shark sheep shell skate sleep smile snake space
spoon storm sugar sweet table tiger toast tooth tower train trees truck water whale wheel witch world
zebra amber bacon badge baker berry blade blank board brave cable camel chess clock comet couch crisp
daisy delta dough drink elbow fable fence field flock forty frame fresh glove goose green happy jelly
joker kayak koala laser lunar mango march metal moose movie nurse onion orbit panda party peach plain
""".split() if len(w) == 5})

QUIZ = [
    ("What is the capital of Finland?", "Helsinki", ["Tampere", "Turku", "Espoo"]),
    ("In which year did Finland become independent?", "1917", ["1918", "1905", "1809"]),
    ("What is the largest ocean in the world?", "Pacific Ocean", ["Atlantic Ocean", "Indian Ocean", "Arctic Ocean"]),
    ("Who wrote Romeo and Juliet?", "William Shakespeare", ["Charles Dickens", "Jane Austen", "Mark Twain"]),
    ("What is the chemical symbol for gold?", "Au", ["Ag", "Gd", "Go"]),
    ("How many planets are in the Solar System?", "8", ["7", "9", "10"]),
    ("Who composed Finlandia?", "Jean Sibelius", ["Edvard Grieg", "Antonín Dvořák", "Carl Nielsen"]),
    ("In which year did Finland join the European Union?", "1995", ["1992", "1999", "2002"]),
    ("In which year did Finland join NATO?", "2023", ["2022", "2024", "2019"]),
    ("How many bones are in the adult human body?", "206", ["186", "226", "256"]),
    ("Which gas makes up most of Earth's atmosphere?", "Nitrogen", ["Oxygen", "Carbon dioxide", "Argon"]),
    ("What is the boiling point of water at sea level?", "100 °C", ["90 °C", "110 °C", "120 °C"]),
    ("Who painted the Mona Lisa?", "Leonardo da Vinci", ["Michelangelo", "Raphael", "Vincent van Gogh"]),
    ("What is the largest planet in the Solar System?", "Jupiter", ["Saturn", "Neptune", "Earth"]),
    ("What is the longest river in the world (by most measurements)?", "Nile", ["Amazon", "Yangtze", "Mississippi"]),
    ("What is the capital of Canada?", "Ottawa", ["Toronto", "Vancouver", "Montreal"]),
    ("Who was the first President of the United States?", "George Washington", ["Thomas Jefferson", "Abraham Lincoln", "John Adams"]),
    ("Which mammal can truly fly?", "Bat", ["Flying squirrel", "Flying fish", "Hummingbird"]),
    ("How many hearts does an octopus have?", "3", ["1", "2", "4"]),
    ("What is the fastest land animal?", "Cheetah", ["Lion", "Antelope", "Ostrich"]),
    ("How many minutes are in a day?", "1440", ["1240", "1400", "1640"]),
    ("What is the capital of Japan?", "Tokyo", ["Osaka", "Kyoto", "Seoul"]),
    ("What is the capital of Australia?", "Canberra", ["Sydney", "Melbourne", "Perth"]),
    ("What do the angles of a triangle add up to?", "180°", ["90°", "270°", "360°"]),
    ("What is 12 × 12?", "144", ["124", "142", "164"]),
    ("What is pi to two decimal places?", "3.14", ["3.12", "3.16", "3.41"]),
    ("Which element combines with sodium to make table salt?", "Chlorine", ["Potassium", "Iodine", "Fluorine"]),
    ("Who received the first telephone patent in 1876?", "Alexander Graham Bell", ["Thomas Edison", "Nikola Tesla", "Guglielmo Marconi"]),
    ("What is the highest mountain in the world?", "Mount Everest", ["K2", "Mont Blanc", "Kilimanjaro"]),
    ("How many players does an ice hockey team have on the ice at once, including the goalie?", "6", ["5", "7", "11"]),
    ("In which country is the Eiffel Tower?", "France", ["Italy", "Belgium", "Spain"]),
    ("Which planet is known as the Red Planet?", "Mars", ["Venus", "Jupiter", "Mercury"]),
    ("What is the capital of Sweden?", "Stockholm", ["Gothenburg", "Malmö", "Uppsala"]),
    ("How many days are in a leap year?", "366", ["365", "364", "367"]),
    ("In which year did humans first land on the Moon?", "1969", ["1965", "1972", "1959"]),
    ("Who was the first person to walk on the Moon?", "Neil Armstrong", ["Buzz Aldrin", "Yuri Gagarin", "Michael Collins"]),
    ("What is the largest animal in the world?", "Blue whale", ["Elephant", "Whale shark", "Sperm whale"]),
    ("How many legs does a spider have?", "8", ["6", "10", "12"]),
    ("What is the chemical formula of water?", "H₂O", ["CO₂", "O₂", "H₂O₂"]),
    ("What colour is the cross on the Finnish flag?", "Blue", ["White", "Red", "Green"]),
    ("What is the capital of Norway?", "Oslo", ["Bergen", "Trondheim", "Tromsø"]),
    ("How many letters are in the English alphabet?", "26", ["24", "25", "28"]),
    ("Which has been the world's most populous country since 2023?", "India", ["China", "United States", "Indonesia"]),
    ("What is the largest organ of the human body?", "Skin", ["Liver", "Brain", "Lungs"]),
    ("What does DNA stand for?", "Deoxyribonucleic acid", ["Disodium acid", "Ribonucleic acid", "Amino acid"]),
    ("Roughly how fast does light travel in a vacuum?", "300,000 km/s", ["30,000 km/s", "3,000 km/s", "3,000,000 km/s"]),
]

TYPING_SENTENCES = [
    "In the summer it is nice to swim and relax at the cottage.",
    "The computer did exactly what it was told, not what was wanted.",
    "In winter the lake freezes and snow covers the forests.",
    "The northern lights glowed green and red in the sky.",
    "Tomorrow I will start a new project and make it the best ever.",
    "I cycled to school even though it was pouring with rain.",
    "The programmer fixed one bug and found three new ones.",
    "At midsummer the bonfire burns on the lake shore late into the night.",
    "The cat slept on the windowsill in the sunshine all day long.",
    "The skier climbed to the top of the hill and raced down at full speed.",
    "Grandma baked cinnamon buns and the whole house smelled of spice.",
    "On the train I read a book and watched the fields rush past.",
    "The hockey game was only decided in overtime by a stunning goal.",
    "In autumn the forest is full of blueberries, lingonberries and mushrooms.",
    "The library is a quiet place where you can focus in peace.",
    "It was thirty degrees below zero and the car would not start.",
    "The teacher wrote a problem on the board that nobody could solve.",
    "We played board games until it was well past midnight.",
    "The quick brown fox jumps over the lazy dog.",
    "The coffee maker bubbled in the kitchen and the morning felt better at once.",
]


# --------------------------------------------------------------------------
# Casino balance (virtual chips)
# --------------------------------------------------------------------------

def chips() -> int:
    return int(load_json("kasino", {"chips": 1000})["chips"])


def set_chips(value: int) -> None:
    save_json("kasino", {"chips": max(0, int(value))})


def ensure_chips() -> int:
    c = chips()
    if c <= 0:
        ui.info("Out of chips – the house gives you 200 more. (It's play money.)")
        set_chips(200)
        c = 200
    return c


# --------------------------------------------------------------------------
# Hangman
# --------------------------------------------------------------------------

@tool("games", "games-hangman", "Hangman", "Guess the word one letter at a time before the man is hanged", ("hangman", "sana", "arvaus"))
def hangman_tool() -> None:
    cats = list(HANGMAN_WORDS)
    idx = ui.choose("Topic", cats + ["Random"])
    cat = random.choice(cats) if idx == len(cats) else cats[idx]
    word = random.choice(HANGMAN_WORDS[cat])
    guessed: set[str] = set()
    wrong: list[str] = []
    while True:
        ui.clear()
        ui.header(f"Hangman – {cat}")
        print(ui.c(GALLOWS[len(wrong)], "bright_yellow"))
        shown = " ".join(ch.upper() if ch in guessed or not ch.isalpha() else "_" for ch in word)
        print("\n  " + ui.bold(shown) + "\n")
        print(ui.gray("  Wrong: ") + ui.red(" ".join(wrong)))
        if all(ch in guessed or not ch.isalpha() for ch in word):
            ui.success(f"You won! The word was {word.upper()}.")
            record_score("Hangman", max(0, 100 - len(wrong) * 15 + len(word) * 2))
            return
        if len(wrong) >= len(GALLOWS) - 1:
            ui.error(f"You lost! The word was {word.upper()}.")
            return
        g = ui.ask("Letter (or the whole word)").lower()
        if len(g) > 1:
            if g == word:
                guessed.update(word)
            else:
                wrong.append(g)
        elif g in guessed or g in wrong:
            continue
        elif g in word:
            guessed.add(g)
        else:
            wrong.append(g)


# --------------------------------------------------------------------------
# Word guess
# --------------------------------------------------------------------------

def sanuli_feedback(guess: str, answer: str) -> list[str]:
    """Returns 'oikea', 'wrong place' or 'ei' for each letter."""
    result = ["ei"] * len(guess)
    remaining = Counter()
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            result[i] = "oikea"
        else:
            remaining[a] += 1
    for i, g in enumerate(guess):
        if result[i] != "oikea" and remaining[g] > 0:
            result[i] = "wrong place"
            remaining[g] -= 1
    return result


def _tile(ch: str, state: str) -> str:
    colors = {"oikea": (106, 170, 100), "wrong place": (201, 180, 88), "ei": (90, 90, 95)}
    if not ui.color_enabled():
        return {"oikea": f"[{ch}]", "wrong place": f"({ch})", "ei": f" {ch} "}[state]
    return ui.fg_bg_rgb(f" {ch.upper()} ", (255, 255, 255), colors[state])


@tool("games", "games-word-guess", "Word guess", "Wordle-style game: guess the five-letter word in six tries", ("wordle", "sanuli", "sana"))
def sanuli_tool() -> None:
    answer = random.choice(SANULI_WORDS)
    rows: list[str] = []
    letters: dict[str, str] = {}
    rank = {"ei": 0, "wrong place": 1, "oikea": 2}
    for attempt in range(1, 7):
        ui.clear()
        ui.header("Word guess", "green = right place · yellow = wrong place · grey = not in the word")
        for r in rows:
            print("   " + r)
        for _ in range(6 - len(rows)):
            print("   " + ui.gray(" · " * 5))
        print()
        for line in ("qwertyuiop", "asdfghjkl", "zxcvbnm"):
            print("   " + "".join(_tile(ch, letters[ch]) if ch in letters else f" {ch.upper()} " for ch in line))
        while True:
            guess = ui.ask(f"Guess {attempt}/6").lower().strip()
            if len(guess) == 5 and guess.isalpha():
                break
            ui.warn("Enter a five-letter word.")
        fb = sanuli_feedback(guess, answer)
        rows.append("".join(_tile(ch, st) for ch, st in zip(guess, fb)))
        for ch, st in zip(guess, fb):
            if ch not in letters or rank[st] > rank[letters[ch]]:
                letters[ch] = st
        if guess == answer:
            ui.clear()
            for r in rows:
                print("   " + r)
            ui.success(f"Correct on try {attempt}! 🎉")
            record_score("Word guess", attempt)
            return
    ui.clear()
    for r in rows:
        print("   " + r)
    ui.error(f"Not this time. The word was {answer.upper()}.")


# --------------------------------------------------------------------------
# Quiz
# --------------------------------------------------------------------------

@tool("games", "games-trivia-quiz", "Trivia quiz", "General knowledge quiz: Finland, nature, science and the world", ("quiz", "visa", "trivia", "kysymykset"))
def quiz_tool() -> None:
    n = ui.ask_int("How many questions", 10, 3, len(QUIZ))
    questions = random.sample(QUIZ, n)
    score = streak = best_streak = 0
    start = time.time()
    for i, (q, right, wrong) in enumerate(questions, 1):
        opts = [right] + wrong
        random.shuffle(opts)
        print(ui.c(f"\n{i}/{n}. {q}", "bold"))
        choice = ui.choose("Answer", opts)
        if opts[choice] == right:
            streak += 1
            best_streak = max(best_streak, streak)
            score += 10 + min(streak, 5) * 2
            ui.success("Correct!" + (f" Streak {streak} 🔥" if streak >= 3 else ""))
        else:
            streak = 0
            ui.error(f"Wrong – the right answer: {right}")
    took = time.time() - start
    ui.box([ui.bold(f"{score} points"), f"Longest streak {best_streak}", ui.gray(f"time taken {ui.fmt_duration(took)}")], title="Result")
    record_score("Trivia quiz", score)


# --------------------------------------------------------------------------
# Blackjack
# --------------------------------------------------------------------------

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def new_deck(n: int = 4) -> list[tuple[str, str]]:
    deck = [(r, s) for _ in range(n) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck


def hand_value(hand: list[tuple[str, str]]) -> tuple[int, bool]:
    """(value, is it 'soft', i.e. an ace counts as 11)."""
    total = aces = 0
    for r, _ in hand:
        if r == "A":
            aces += 1
            total += 11
        elif r in ("J", "Q", "K"):
            total += 10
        else:
            total += int(r)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


def show_cards(hand: list[tuple[str, str]], hide_first: bool = False) -> str:
    out = []
    for i, (r, s) in enumerate(hand):
        if hide_first and i == 0:
            out.append(ui.c("[??]", "gray"))
        else:
            out.append(ui.c(f"[{r}{s}]", "bright_red" if s in "♥♦" else "bright_white"))
    return " ".join(out)


@tool("games", "games-blackjack", "Blackjack", "Get close to 21 against the dealer – with play chips", ("blackjack", "21", "kortit", "kasino"))
def blackjack_tool() -> None:
    deck = new_deck()
    while True:
        bank = ensure_chips()
        print(ui.c(f"\nChips: {bank}", "bold", "bright_yellow"))
        bet = ui.ask_int("Bet (0 = quit)", min(50, bank), 0, bank)
        if bet == 0:
            return
        if len(deck) < 20:
            deck = new_deck()
        player, dealer = [deck.pop(), deck.pop()], [deck.pop(), deck.pop()]
        doubled = False
        while True:
            pv, _ = hand_value(player)
            print(f"  Dealer: {show_cards(dealer, hide_first=True)}")
            print(f"  You:    {show_cards(player)}  = {ui.bold(str(pv))}")
            if pv >= 21:
                break
            opts = ["Hit", "Stand"] + (["Double"] if len(player) == 2 and bank >= bet * 2 else [])
            act = ui.choose("Move", opts)
            if act == 0:
                player.append(deck.pop())
            elif act == 1:
                break
            else:
                bet *= 2
                doubled = True
                player.append(deck.pop())
                break
        pv, _ = hand_value(player)
        natural = pv == 21 and len(player) == 2 and not doubled
        if pv <= 21:
            while True:
                dv, soft = hand_value(dealer)
                if dv < 17:
                    dealer.append(deck.pop())
                else:
                    break
        dv, _ = hand_value(dealer)
        print(f"  Dealer: {show_cards(dealer)}  = {ui.bold(str(dv))}")
        print(f"  You:    {show_cards(player)}  = {ui.bold(str(pv))}")
        if pv > 21:
            ui.error(f"Bust – you lost {bet}.")
            bank -= bet
        elif natural and not (dv == 21 and len(dealer) == 2):
            win = int(bet * 1.5)
            ui.success(f"BLACKJACK! You won {win}.")
            bank += win
        elif dv > 21 or pv > dv:
            ui.success(f"You won {bet}!")
            bank += bet
        elif pv == dv:
            ui.info("Push – your bet is returned.")
        else:
            ui.error(f"The dealer won – you lost {bet}.")
            bank -= bet
        set_chips(bank)
        record_score("Casino (chips)", bank)


# --------------------------------------------------------------------------
# Slot machine
# --------------------------------------------------------------------------

SLOT_SYMBOLS = [("🍒", 30, 3), ("🍋", 25, 4), ("🍊", 20, 5), ("🍇", 12, 8), ("🔔", 7, 15), ("⭐", 4, 30), ("💎", 2, 75)]


def spin_reels(rng: random.Random | None = None) -> list[str]:
    rng = rng or random
    symbols = [s for s, _, _ in SLOT_SYMBOLS]
    weights = [w for _, w, _ in SLOT_SYMBOLS]
    return rng.choices(symbols, weights=weights, k=3)


def slot_payout(reels: list[str], bet: int) -> int:
    mult = {s: m for s, _, m in SLOT_SYMBOLS}
    if reels[0] == reels[1] == reels[2]:
        return bet * mult[reels[0]]
    if reels.count("🍒") == 2:
        return bet * 2
    if "🍒" in reels and len(set(reels)) == 3 and reels[0] == "🍒":
        return bet
    return 0


@tool("games", "games-slot-machine", "Slot machine", "Spin the reels with play chips – three of a kind wins", ("slots", "kolikkopeli", "jackpot"))
def slots_tool() -> None:
    print(ui.gray("  Payouts: " + "  ".join(f"{s}{s}{s}×{m}" for s, _, m in SLOT_SYMBOLS) + "  🍒🍒×2  🍒 first×1"))
    while True:
        bank = ensure_chips()
        bet = ui.ask_int(f"Chips {bank}. Bet (0 = quit)", min(10, bank), 0, bank)
        if bet == 0:
            return
        bank -= bet
        final = spin_reels()
        if ui.is_tty():
            for i in range(12):
                frame = final[:i // 4] + spin_reels()[i // 4:]
                print(f"\r   ┃ {' │ '.join(frame)} ┃", end="", flush=True)
                time.sleep(0.06 + i * 0.01)
        print(f"\r   ┃ {' │ '.join(final)} ┃")
        win = slot_payout(final, bet)
        if win:
            bank += win
            ui.success(f"WIN {win}! " + ("💰" * min(5, win // bet)))
        else:
            print(ui.gray("   No win."))
        set_chips(bank)
        record_score("Casino (chips)", bank)


# --------------------------------------------------------------------------
# Higher or lower
# --------------------------------------------------------------------------

@tool("games", "games-higher-or-lower", "Higher or lower", "Guess whether the next card is higher or lower – how long a streak?", ("hilo", "kortti", "arvaus"))
def hilo_tool() -> None:
    deck = new_deck(1)
    values = {r: i for i, r in enumerate(RANKS[1:] + ["A"], 2)}
    current = deck.pop()
    streak = 0
    while deck:
        print(f"\n  Card: {show_cards([current])}   streak {ui.bold(str(streak))}")
        g = ui.choose("The next one is", ["Higher", "Lower", "Quit"])
        if g == 2:
            break
        nxt = deck.pop()
        a, b = values[current[0]], values[nxt[0]]
        print(f"  Next: {show_cards([nxt])}")
        if a == b:
            ui.info("Same value – moving on.")
        elif (b > a) == (g == 0):
            streak += 1
            ui.success("Correct!")
        else:
            ui.error("Wrong!")
            break
        current = nxt
    ui.info(f"Streak: {streak}")
    record_score("Higher or lower", streak)


# --------------------------------------------------------------------------
# Rock, paper, scissors (learning AI)
# --------------------------------------------------------------------------

RPS_BEATS = {"rock": ["scissors", "lizard"], "paper": ["rock", "spock"], "scissors": ["paper", "lizard"],
             "lizard": ["paper", "spock"], "spock": ["rock", "scissors"]}
RPS_EMOJI = {"rock": "✊", "paper": "✋", "scissors": "✌", "lizard": "🦎", "spock": "🖖"}


class RPSBrain:
    """Predicts the player's next move from the previous move (Markov chain)."""

    def __init__(self, moves: list[str]) -> None:
        self.moves = moves
        self.trans: dict[str, Counter[str]] = defaultdict(Counter)
        self.last: str | None = None

    def choose(self) -> str:
        if self.last and self.trans[self.last]:
            predicted = self.trans[self.last].most_common(1)[0][0]
            counters = [m for m in self.moves if predicted in RPS_BEATS[m]]
            if counters and random.random() < 0.8:
                return random.choice(counters)
        return random.choice(self.moves)

    def observe(self, move: str) -> None:
        if self.last:
            self.trans[self.last][move] += 1
        self.last = move


@tool("games", "games-rock-paper-scissors", "Rock, paper, scissors", "The AI learns your play style – lizard–Spock version too", ("rps", "rock", "scissors", "spock"))
def rps_tool() -> None:
    spock = ui.ask_yes_no("Play with the lizard–Spock expansion?", False)
    moves = list(RPS_BEATS) if spock else ["rock", "paper", "scissors"]
    rounds = ui.ask_int("How many rounds", 10, 1, 100)
    brain = RPSBrain(moves)
    me = ai = 0
    for r in range(1, rounds + 1):
        print(ui.gray(f"\nRound {r}/{rounds} · you {me} – {ai} AI"))
        pick = moves[ui.choose("Your pick", [f"{RPS_EMOJI[m]} {m}" for m in moves])]
        comp = brain.choose()
        brain.observe(pick)
        print(f"  You {RPS_EMOJI[pick]}  vs  {RPS_EMOJI[comp]} AI ({comp})")
        if pick == comp:
            ui.info("Draw.")
        elif comp in RPS_BEATS[pick]:
            me += 1
            ui.success("You won the round!")
        else:
            ai += 1
            ui.error("The AI won the round.")
    ui.box([ui.bold(f"You {me} – {ai} AI"), "You won! 🎉" if me > ai else "Draw." if me == ai else "The AI read you like a book… 🤖"])
    record_score("Rock-paper-scissors", me - ai)


# --------------------------------------------------------------------------
# Number guess
# --------------------------------------------------------------------------

@tool("games", "games-number-guess", "Number guess", "Guess the computer's number – or let the computer guess yours", ("number", "arvaa", "luku"))
def guess_tool() -> None:
    mode = ui.choose("Mode", ["You guess", "The computer guesses your number"])
    hi = [50, 100, 1000, 1_000_000][ui.choose("Difficulty", ["1–50", "1–100", "1–1000", "1–1 000 000"], 1)]
    if mode == 0:
        target = random.randint(1, hi)
        tries = 0
        last_diff = None
        while True:
            g = ui.ask_int(f"Guess (1–{hi})", None, 1, hi)
            tries += 1
            if g == target:
                ui.success(f"Correct! {tries} tries.")
                if hi == 100:
                    record_score("Number guess", tries)
                return
            diff = abs(g - target)
            temp = ""
            if last_diff is not None:
                temp = ui.red(" getting warmer 🔥") if diff < last_diff else ui.cyan(" getting colder ❄") if diff > last_diff else ""
            last_diff = diff
            print(("  Higher ↑" if g < target else "  Lower ↓") + temp)
    lo, top, tries = 1, hi, 0
    print(ui.gray(f"Think of a number between 1–{hi}."))
    while lo <= top:
        g = (lo + top) // 2
        tries += 1
        ans = ui.choose(f"Is your number {g}?", ["Correct!", "Higher", "Lower"])
        if ans == 0:
            ui.success(f"I guessed it in {tries} tries 😎")
            return
        if ans == 1:
            lo = g + 1
        else:
            top = g - 1
    ui.warn("Looks like you cheated 🤔 – the answers contradicted each other.")


# --------------------------------------------------------------------------
# Mastermind
# --------------------------------------------------------------------------

MM_COLORS = ["bright_red", "bright_green", "bright_yellow", "bright_blue", "bright_magenta", "bright_cyan"]


def mm_score(guess: list[int], code: list[int]) -> tuple[int, int]:
    exact = sum(g == c for g, c in zip(guess, code))
    common = sum((Counter(guess) & Counter(code)).values())
    return exact, common - exact


@tool("games", "games-mastermind", "Mastermind", "Crack the four-colour code in ten tries", ("mastermind", "koodi", "logiikka"))
def mastermind_tool() -> None:
    code = [random.randint(1, 6) for _ in range(4)]
    print(ui.gray("Colours 1–6: ") + " ".join(ui.c(f"{i + 1}●", MM_COLORS[i]) for i in range(6)))
    print(ui.gray("● = right colour in the right place, ○ = right colour in the wrong place"))
    for attempt in range(1, 11):
        raw = ui.ask(f"Guess {attempt}/10 (e.g. 1234)").replace(" ", "")
        if len(raw) != 4 or not all(ch in "123456" for ch in raw):
            ui.warn("Enter four digits between 1–6.")
            continue
        guess = [int(ch) for ch in raw]
        exact, partial = mm_score(guess, code)
        pegs = ui.bold("●" * exact) + "○" * partial
        print("   " + " ".join(ui.c("●", MM_COLORS[g - 1]) for g in guess) + "   " + pegs)
        if exact == 4:
            ui.success(f"You cracked the code on try {attempt}!")
            record_score("Mastermind", attempt)
            return
    ui.error("Out of tries. The code was " + " ".join(ui.c(f"{g}●", MM_COLORS[g - 1]) for g in code))


# --------------------------------------------------------------------------
# Memory
# --------------------------------------------------------------------------

@tool("games", "games-memory", "Memory", "Find the pairs in a 4×4 grid in as few moves as possible", ("memory", "parit", "muisti"))
def memory_tool() -> None:
    symbols = list("🍎🍌🍇🍓🍒🥝🍍🥥") if ui.color_enabled() else list("ABCDEFGH")
    cards = symbols * 2
    random.shuffle(cards)
    found = [False] * 16
    moves = 0
    rows = "ABCD"

    def pos(token: str) -> int | None:
        token = token.strip().upper()
        if len(token) == 2 and token[0] in rows and token[1] in "1234":
            return rows.index(token[0]) * 4 + int(token[1]) - 1
        return None

    def draw(reveal: set[int]) -> None:
        print("     1   2   3   4")
        for r in range(4):
            cells = []
            for c in range(4):
                i = r * 4 + c
                cells.append(f" {cards[i]} " if found[i] or i in reveal else ui.gray(" ▒▒"))
            print(f"  {rows[r]} " + " ".join(cells))

    while not all(found):
        ui.clear()
        ui.header("Memory", f"moves {moves} · pairs found {sum(found) // 2}/8")
        draw(set())
        a = pos(ui.ask("First card (e.g. A1)"))
        if a is None or found[a]:
            continue
        ui.clear()
        draw({a})
        b = pos(ui.ask("Second card"))
        if b is None or b == a or found[b]:
            continue
        moves += 1
        ui.clear()
        draw({a, b})
        if cards[a] == cards[b]:
            found[a] = found[b] = True
            ui.success("A pair!")
            time.sleep(0.6)
        else:
            time.sleep(1.4)
    ui.success(f"All pairs found in {moves} moves!")
    record_score("Memory", moves)


# --------------------------------------------------------------------------
# Nim
# --------------------------------------------------------------------------

def nim_best_move(piles: list[int]) -> tuple[int, int]:
    x = 0
    for p in piles:
        x ^= p
    if x:
        for i, p in enumerate(piles):
            if p ^ x < p:
                return i, p - (p ^ x)
    i = max(range(len(piles)), key=lambda k: piles[k])
    return i, 1


@tool("games", "games-stick-game", "Stick game (Nim)", "Take sticks from the piles – whoever takes the last stick wins. The AI knows the maths!", ("nim", "tikut", "logiikka"))
def nim_tool() -> None:
    piles = [random.randint(2, 7) for _ in range(random.choice([3, 4]))]
    hard = ui.ask_yes_no("Hard AI (plays perfectly)?", False)
    turn = 0
    while any(piles):
        print()
        for i, p in enumerate(piles, 1):
            print(f"  {i}: {ui.c('|' * p, 'bright_yellow')} ({p})")
        if turn == 0:
            i = ui.ask_int("Pile", None, 1, len(piles)) - 1
            if piles[i] == 0:
                ui.warn("The pile is empty.")
                continue
            n = ui.ask_int("How many sticks", 1, 1, piles[i])
            piles[i] -= n
        else:
            if hard or random.random() < 0.6:
                i, n = nim_best_move(piles)
            else:
                i = random.choice([k for k, p in enumerate(piles) if p])
                n = random.randint(1, piles[i])
            piles[i] -= n
            print(ui.cyan(f"  The AI took {n} from pile {i + 1}."))
        if not any(piles):
            if turn == 0:
                ui.success("You took the last stick – you win!")
                record_score("Nim", 1)
            else:
                ui.error("The AI took the last stick.")
            return
        turn ^= 1


# --------------------------------------------------------------------------
# Typing speed, mental maths, reaction, word scramble
# --------------------------------------------------------------------------

def typing_result(target: str, typed: str, seconds: float) -> tuple[float, float]:
    """(words per minute, accuracy %)."""
    import difflib

    ratio = difflib.SequenceMatcher(None, target, typed).ratio()
    words = len(typed) / 5
    wpm = words / (seconds / 60) if seconds > 0 else 0.0
    return wpm * ratio, ratio * 100


@tool("games", "games-typing-speed-test", "Typing speed test", "How many words per minute can you type?", ("typing", "wpm", "typing"))
def typing_tool() -> None:
    rounds = ui.ask_int("How many sentences", 3, 1, 10)
    total_wpm = total_acc = 0.0
    for sentence in random.sample(TYPING_SENTENCES, rounds):
        print("\n  " + ui.c(sentence, "bold", "bright_cyan"))
        input(ui.gray("  Enter starts…"))
        start = time.perf_counter()
        typed = input("  » ")
        took = time.perf_counter() - start
        wpm, acc = typing_result(sentence, typed, took)
        total_wpm += wpm
        total_acc += acc
        print(f"  {ui.bold(f'{wpm:.0f} words/min')} · accuracy {acc:.0f} % · {took:.1f} s")
    avg = total_wpm / rounds
    ui.box([ui.bold(f"Average {avg:.0f} words/min"), f"accuracy {total_acc / rounds:.0f} %",
            ui.gray("An average typist does about 40, a fast one 70+.")], title="Result")
    record_score("Typing speed (WPM)", round(avg, 1))


@tool("games", "games-mental-maths-sprint", "Mental maths sprint", "Solve as many sums as you can in 60 seconds", ("matikka", "laskut", "nopeus", "aivot"))
def mental_math_tool() -> None:
    level = ui.choose("Level", ["Easy (+ −)", "Normal (+ − ×)", "Hard (+ − × ÷ big numbers)"], 1)
    end = time.time() + 60
    right = wrong = 0
    while time.time() < end:
        op = random.choice("+-" if level == 0 else "+-*" if level == 1 else "+-*/")
        hi = 20 if level == 0 else 50 if level == 1 else 200
        a, b = random.randint(1, hi), random.randint(1, hi if op in "+-" else 12 if level < 2 else 25)
        if op == "/":
            a = a * b
        if op == "-" and b > a and level == 0:
            a, b = b, a
        answer = {"+": a + b, "-": a - b, "*": a * b, "/": a // b}[op]
        left = int(end - time.time())
        raw = input(f"  {ui.gray(f'[{left:2d}s]')} {a} {op.replace('*', '×').replace('/', '÷')} {b} = ")
        if time.time() > end:
            print(ui.gray("  Time's up!"))
            break
        if raw.strip().lstrip("-").isdigit() and int(raw) == answer:
            right += 1
        else:
            wrong += 1
            print(ui.red(f"    the right answer was {answer}"))
    score = right * (1 + level) - wrong
    ui.box([ui.bold(f"{right} right, {wrong} wrong"), f"Score: {score}"], title="Time!")
    record_score("Mental maths sprint", score)


@tool("games", "games-reaction-test", "Reaction test", "Press as soon as the screen turns green – measures your reaction time", ("reaktio", "nopeus", "refleksit"))
def reaction_tool() -> None:
    times = []
    for r in range(1, 6):
        print(ui.c(f"\nRound {r}/5: wait…", "bold", "bright_red"))
        delay = random.uniform(1.5, 5.0)
        if keys.interactive():
            with keys.RawMode():
                start_wait = time.perf_counter()
                early = False
                while time.perf_counter() - start_wait < delay:
                    if keys.get_key(0.01) is not None:
                        early = True
                        break
                if early:
                    ui.warn("Too early! Round discarded.")
                    continue
                print(ui.c("  ███ NOW! ███", "bold", "bright_green"), flush=True)
                t0 = time.perf_counter()
                while keys.get_key(0.001) is None:
                    pass
                took = time.perf_counter() - t0
        else:
            time.sleep(delay)
            print(ui.c("  NOW! (press Enter)", "bold", "bright_green"))
            t0 = time.perf_counter()
            input()
            took = time.perf_counter() - t0
        times.append(took)
        print(f"  {ui.bold(f'{took * 1000:.0f} ms')}")
    if times:
        avg = sum(times) / len(times)
        verdict = "lightning fast ⚡" if avg < 0.22 else "good 👍" if avg < 0.3 else "average" if avg < 0.4 else "sleepy 😴"
        ui.box([ui.bold(f"Average {avg * 1000:.0f} ms – {verdict}"), ui.gray(f"best {min(times) * 1000:.0f} ms")], title="Result")
        record_score("Reaction test", round(avg, 3))


@tool("games", "games-word-scramble", "Word scramble", "Guess the word from scrambled letters – hints cost points", ("anagrammi", "sana", "sekoitus"))
def scramble_tool() -> None:
    pool = [w for ws in HANGMAN_WORDS.values() for w in ws if 5 <= len(w) <= 11]
    score = 0
    for r in range(1, 11):
        word = random.choice(pool)
        letters = list(word)
        while "".join(letters) == word:
            random.shuffle(letters)
        hints = 0
        while True:
            print(f"\n  {r}/10: " + ui.bold(" ".join(ch.upper() for ch in letters)) + ui.gray(f"   ({len(word)} letters)"))
            g = ui.ask("Word (? = hint, - = skip)").lower()
            if g == "?":
                hints += 1
                print("  Hint: " + ui.cyan(word[:hints].upper() + "_" * (len(word) - hints)))
                if hints >= len(word) - 1:
                    ui.info(f"The word was {word.upper()}")
                    break
                continue
            if g == "-":
                ui.info(f"The word was {word.upper()}")
                break
            if g == word:
                pts = max(1, 10 - hints * 3)
                score += pts
                ui.success(f"Correct! +{pts}")
                break
            ui.error("Not that one.")
    ui.box([ui.bold(f"{score} points")], title="Result")
    record_score("Word scramble", score)
