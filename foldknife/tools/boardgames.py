"""Board games against the AI: tic-tac-toe, connect four, minesweeper, battleship, sudoku, yatzy and reversi."""
from __future__ import annotations

import random
import time
from collections import Counter
from typing import Optional

from ..core import ui
from ..core.registry import tool
from .games import LOWER_IS_BETTER, record_score

LOWER_IS_BETTER.update({"Minesweeper (easy)", "Minesweeper (medium)", "Minesweeper (hard)",
                        "Sudoku (easy)", "Sudoku (medium)", "Sudoku (hard)", "Battleship"})

# --------------------------------------------------------------------------
# Tic-tac-toe
# --------------------------------------------------------------------------

LINES3 = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def ttt_winner(b: list[str]) -> Optional[str]:
    for a, c, d in LINES3:
        if b[a] != " " and b[a] == b[c] == b[d]:
            return b[a]
    return "tasan" if " " not in b else None


def ttt_minimax(b: list[str], player: str, me: str, alpha: int = -99, beta: int = 99) -> tuple[int, Optional[int]]:
    w = ttt_winner(b)
    if w == me:
        return 10 - b.count(" ") * 0 + b.count(" "), None
    if w and w != "tasan":
        return -10 - b.count(" "), None
    if w == "tasan":
        return 0, None
    other = "O" if player == "X" else "X"
    best_move = None
    if player == me:
        best = -99
        for i in range(9):
            if b[i] == " ":
                b[i] = player
                score, _ = ttt_minimax(b, other, me, alpha, beta)
                b[i] = " "
                if score > best:
                    best, best_move = score, i
                alpha = max(alpha, best)
                if alpha >= beta:
                    break
        return best, best_move
    best = 99
    for i in range(9):
        if b[i] == " ":
            b[i] = player
            score, _ = ttt_minimax(b, other, me, alpha, beta)
            b[i] = " "
            if score < best:
                best, best_move = score, i
            beta = min(beta, best)
            if alpha >= beta:
                break
    return best, best_move


def _ttt_draw(b: list[str]) -> None:
    def cell(i: int) -> str:
        v = b[i]
        if v == "X":
            return ui.c(" X ", "bold", "bright_cyan")
        if v == "O":
            return ui.c(" O ", "bold", "bright_red")
        return ui.gray(f" {i + 1} ")
    for r in range(3):
        print("    " + "│".join(cell(r * 3 + c) for c in range(3)))
        if r < 2:
            print("    " + ui.gray("───┼───┼───"))


@tool("games", "games-tic-tac-toe", "Tic-tac-toe", "Three in a row – against an unbeatable AI or a friend", ("tictactoe", "ristinolla", "xo"))
def tictactoe_tool() -> None:
    mode = ui.choose("Opponent", ["AI (easy)", "AI (medium)", "AI (impossible)", "A friend on the same computer"], 2)
    b = [" "] * 9
    player = "X"
    ai = "O" if ui.ask_yes_no("Do you start (X)?", True) else "X"
    while True:
        ui.clear()
        ui.header("Tic-tac-toe")
        _ttt_draw(b)
        w = ttt_winner(b)
        if w:
            if w == "tasan":
                ui.info("Draw!")
            elif mode == 3:
                ui.success(f"{w} won!")
            elif w == ai:
                ui.error("The AI won.")
            else:
                ui.success("You won! 🎉")
                record_score("Tic-tac-toe", [1, 2, 5][mode] if mode < 3 else 0)
            return
        if mode < 3 and player == ai:
            if mode == 0 or (mode == 1 and random.random() < 0.5):
                move = random.choice([i for i in range(9) if b[i] == " "])
            else:
                _, move = ttt_minimax(b, ai, ai)
            b[move] = ai  # type: ignore[index]
        else:
            n = ui.ask_int(f"Player {player}, square 1–9", None, 1, 9) - 1
            if b[n] != " ":
                continue
            b[n] = player
        player = "O" if player == "X" else "X"


# --------------------------------------------------------------------------
# Connect four
# --------------------------------------------------------------------------

C4_ROWS, C4_COLS = 6, 7


def c4_drop(board: list[list[int]], col: int, piece: int) -> Optional[int]:
    for r in range(C4_ROWS - 1, -1, -1):
        if board[r][col] == 0:
            board[r][col] = piece
            return r
    return None


def c4_winner(board: list[list[int]], piece: int) -> bool:
    for r in range(C4_ROWS):
        for c in range(C4_COLS):
            if board[r][c] != piece:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                if all(0 <= r + dr * k < C4_ROWS and 0 <= c + dc * k < C4_COLS and board[r + dr * k][c + dc * k] == piece
                       for k in range(4)):
                    return True
    return False


def _c4_window_score(window: list[int], piece: int) -> int:
    opp = 3 - piece
    if window.count(piece) == 4:
        return 1000
    if window.count(piece) == 3 and window.count(0) == 1:
        return 6
    if window.count(piece) == 2 and window.count(0) == 2:
        return 2
    if window.count(opp) == 3 and window.count(0) == 1:
        return -5
    return 0


def c4_evaluate(board: list[list[int]], piece: int) -> int:
    score = sum(3 for r in range(C4_ROWS) if board[r][3] == piece)
    for r in range(C4_ROWS):
        for c in range(C4_COLS - 3):
            score += _c4_window_score([board[r][c + k] for k in range(4)], piece)
    for c in range(C4_COLS):
        for r in range(C4_ROWS - 3):
            score += _c4_window_score([board[r + k][c] for k in range(4)], piece)
    for r in range(C4_ROWS - 3):
        for c in range(C4_COLS - 3):
            score += _c4_window_score([board[r + k][c + k] for k in range(4)], piece)
            score += _c4_window_score([board[r + 3 - k][c + k] for k in range(4)], piece)
    return score


def c4_valid(board: list[list[int]]) -> list[int]:
    return [c for c in (3, 2, 4, 1, 5, 0, 6) if board[0][c] == 0]


def c4_minimax(board: list[list[int]], depth: int, alpha: float, beta: float, maximizing: bool, ai: int) -> tuple[float, Optional[int]]:
    human = 3 - ai
    valid = c4_valid(board)
    if c4_winner(board, ai):
        return 1e6 + depth, None
    if c4_winner(board, human):
        return -1e6 - depth, None
    if not valid:
        return 0, None
    if depth == 0:
        return c4_evaluate(board, ai), None
    best_col = valid[0]
    if maximizing:
        value = -float("inf")
        for col in valid:
            row = c4_drop(board, col, ai)
            score, _ = c4_minimax(board, depth - 1, alpha, beta, False, ai)
            board[row][col] = 0  # type: ignore[index]
            if score > value:
                value, best_col = score, col
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value, best_col
    value = float("inf")
    for col in valid:
        row = c4_drop(board, col, human)
        score, _ = c4_minimax(board, depth - 1, alpha, beta, True, ai)
        board[row][col] = 0  # type: ignore[index]
        if score < value:
            value, best_col = score, col
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value, best_col


@tool("games", "games-connect-four", "Connect four", "Drop discs and get four in a row before the AI", ("connect four", "four in a row", "kiekot"))
def connect4_tool() -> None:
    level = ui.choose("Opponent", ["AI (easy)", "AI (medium)", "AI (hard)", "A friend on the same computer"], 1)
    depth = [1, 3, 5][level] if level < 3 else 0
    board = [[0] * C4_COLS for _ in range(C4_ROWS)]
    turn = 1
    discs = {1: ui.c("●", "bright_yellow"), 2: ui.c("●", "bright_red")}
    while True:
        ui.clear()
        ui.header("Connect four", "You " + discs[1] + ("  vs  AI " if level < 3 else "  vs  friend ") + discs[2])
        for r in range(C4_ROWS):
            print("   " + ui.blue("│") + ui.blue("│").join(f" {discs[v] if v else ' '} " for v in board[r]) + ui.blue("│"))
        print("   " + ui.blue("└" + "───┴" * (C4_COLS - 1) + "───┘"))
        print("    " + "   ".join(str(i + 1) for i in range(C4_COLS)))
        for p in (1, 2):
            if c4_winner(board, p):
                if level == 3:
                    ui.success(f"Player {p} won!")
                elif p == 1:
                    ui.success("You won! 🎉")
                    record_score("Connect four", [1, 3, 10][level])
                else:
                    ui.error("The AI won.")
                return
        if not c4_valid(board):
            ui.info("Draw – the board is full.")
            return
        if turn == 2 and level < 3:
            with ui.Spinner("The AI is thinking"):
                _, col = c4_minimax(board, depth, -float("inf"), float("inf"), True, 2)
            c4_drop(board, col, 2)  # type: ignore[arg-type]
        else:
            col = ui.ask_int(f"Player {turn}, column 1–7", None, 1, 7) - 1
            if board[0][col] != 0:
                ui.warn("That column is full.")
                time.sleep(0.7)
                continue
            c4_drop(board, col, turn)
        turn = 3 - turn


# --------------------------------------------------------------------------
# Minesweeper
# --------------------------------------------------------------------------

COL_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


class Minesweeper:
    def __init__(self, w: int, h: int, mines: int, rng: random.Random | None = None) -> None:
        self.w, self.h, self.n_mines = w, h, mines
        self.rng = rng or random.Random()
        self.mines: set[tuple[int, int]] = set()
        self.opened: set[tuple[int, int]] = set()
        self.flags: set[tuple[int, int]] = set()
        self.started = False
        self.lost = False

    def neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx or dy) and 0 <= x + dx < self.w and 0 <= y + dy < self.h]

    def count(self, x: int, y: int) -> int:
        return sum((n in self.mines) for n in self.neighbors(x, y))

    def _place(self, safe_x: int, safe_y: int) -> None:
        forbidden = {(safe_x, safe_y), *self.neighbors(safe_x, safe_y)}
        cells = [(x, y) for x in range(self.w) for y in range(self.h) if (x, y) not in forbidden]
        self.mines = set(self.rng.sample(cells, min(self.n_mines, len(cells))))
        self.started = True

    def open(self, x: int, y: int) -> None:
        if not self.started:
            self._place(x, y)
        if (x, y) in self.flags or (x, y) in self.opened:
            return
        if (x, y) in self.mines:
            self.lost = True
            return
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in self.opened:
                continue
            self.opened.add((cx, cy))
            self.flags.discard((cx, cy))
            if self.count(cx, cy) == 0:
                stack.extend(n for n in self.neighbors(cx, cy) if n not in self.opened and n not in self.mines)

    def chord(self, x: int, y: int) -> None:
        """Opens the neighbours if the right number of flags is already around."""
        if (x, y) in self.opened and sum(n in self.flags for n in self.neighbors(x, y)) == self.count(x, y):
            for n in self.neighbors(x, y):
                if n not in self.flags:
                    self.open(*n)

    @property
    def won(self) -> bool:
        return self.started and not self.lost and len(self.opened) == self.w * self.h - len(self.mines)

    def render(self, reveal: bool = False) -> list[str]:
        num_colors = {1: "bright_blue", 2: "bright_green", 3: "bright_red", 4: "blue", 5: "red", 6: "cyan", 7: "magenta", 8: "gray"}
        lines = ["    " + " ".join(COL_LABELS[i] for i in range(self.w))]
        for y in range(self.h):
            row = []
            for x in range(self.w):
                p = (x, y)
                if reveal and p in self.mines:
                    row.append(ui.c("*", "bold", "bright_red"))
                elif p in self.flags:
                    row.append(ui.c("⚑", "bright_red"))
                elif p in self.opened:
                    n = self.count(x, y)
                    row.append(ui.c(str(n), num_colors[n]) if n else ui.gray("·"))
                else:
                    row.append(ui.gray("■"))
            lines.append(f"{y + 1:>3} " + " ".join(row))
        return lines


def _parse_cell(token: str, w: int, h: int) -> Optional[tuple[int, int]]:
    token = token.strip()
    if len(token) < 2 or token[0] not in COL_LABELS[:w] or not token[1:].isdigit():
        return None
    x, y = COL_LABELS.index(token[0]), int(token[1:]) - 1
    return (x, y) if 0 <= y < h else None


@tool("games", "games-minesweeper", "Minesweeper", "Open squares without hitting mines (e.g. C5 opens, F C5 flags)", ("minesweeper", "miinat", "logiikka"))
def minesweeper_tool() -> None:
    levels = [("easy", 9, 9, 10), ("medium", 16, 16, 40), ("hard", 30, 16, 99)]
    name, w, h, m = levels[ui.choose("Difficulty", [f"{n.capitalize()} ({a}×{b}, {c} mines)" for n, a, b, c in levels])]
    game = Minesweeper(w, h, m)
    start = None
    while True:
        ui.clear()
        ui.header("Minesweeper", f"{name} · mines {m} · flags {len(game.flags)}")
        for line in game.render(reveal=game.lost):
            print(line)
        if game.lost:
            ui.error("BOOM! You hit a mine. 💥")
            return
        if game.won:
            took = time.time() - (start or time.time())
            ui.success(f"You won in {took:.0f} s! 🎉")
            record_score(f"Minesweeper ({name})", round(took))
            return
        raw = ui.ask("Move (C5 = open, F C5 = flag, q = quit)").strip()
        if raw.lower() == "q":
            return
        flag = raw[:2].lower() in ("l ", "f ")
        cell = _parse_cell(raw[2:] if flag else raw, w, h)
        if not cell:
            continue
        if start is None and not flag:
            start = time.time()
        if flag:
            if cell in game.flags:
                game.flags.discard(cell)
            elif cell not in game.opened:
                game.flags.add(cell)
        elif cell in game.opened:
            game.chord(*cell)
        else:
            game.open(*cell)


# --------------------------------------------------------------------------
# Battleship
# --------------------------------------------------------------------------

SHIPS = [("Carrier", 5), ("Battleship", 4), ("Cruiser", 3), ("Submarine", 3), ("Destroyer", 2)]


def place_ships(rng: random.Random, size: int = 10) -> dict[tuple[int, int], int]:
    occupied: dict[tuple[int, int], int] = {}
    for idx, (_, length) in enumerate(SHIPS):
        while True:
            horiz = rng.random() < 0.5
            x = rng.randrange(size - (length - 1 if horiz else 0))
            y = rng.randrange(size - (0 if horiz else length - 1))
            cells = [(x + i, y) if horiz else (x, y + i) for i in range(length)]
            if all(c not in occupied for c in cells):
                for c in cells:
                    occupied[c] = idx
                break
    return occupied


class BattleAI:
    def __init__(self, rng: random.Random, size: int = 10) -> None:
        self.rng, self.size = rng, size
        self.tried: set[tuple[int, int]] = set()
        self.targets: list[tuple[int, int]] = []

    def pick(self) -> tuple[int, int]:
        while self.targets:
            t = self.targets.pop()
            if t not in self.tried and 0 <= t[0] < self.size and 0 <= t[1] < self.size:
                return t
        candidates = [(x, y) for x in range(self.size) for y in range(self.size) if (x, y) not in self.tried and (x + y) % 2 == 0]
        if not candidates:
            candidates = [(x, y) for x in range(self.size) for y in range(self.size) if (x, y) not in self.tried]
        return self.rng.choice(candidates)

    def result(self, cell: tuple[int, int], hit: bool, sunk: bool) -> None:
        self.tried.add(cell)
        if hit and not sunk:
            x, y = cell
            self.targets.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
        if sunk:
            self.targets.clear()


def _bs_board(ships: dict[tuple[int, int], int], shots: dict[tuple[int, int], bool], show_ships: bool) -> list[str]:
    lines = ["   " + " ".join("ABCDEFGHIJ")]
    for y in range(10):
        row = []
        for x in range(10):
            p = (x, y)
            if p in shots:
                row.append(ui.c("✖", "bright_red") if shots[p] else ui.c("○", "bright_blue"))
            elif show_ships and p in ships:
                row.append(ui.c("■", "bright_white"))
            else:
                row.append(ui.gray("·"))
        lines.append(f"{y + 1:>2} " + " ".join(row))
    return lines


@tool("games", "games-battleship", "Battleship", "Sink the AI's fleet before it sinks yours", ("battleship", "laivat", "sotapeli"))
def battleship_tool() -> None:
    rng = random.Random()
    mine, theirs = place_ships(rng), place_ships(rng)
    my_shots: dict[tuple[int, int], bool] = {}
    ai_shots: dict[tuple[int, int], bool] = {}
    ai = BattleAI(rng)
    msg = ""
    shots_fired = 0
    while True:
        ui.clear()
        ui.header("Battleship", "✖ hit · ○ miss")
        left = _bs_board(theirs, my_shots, False)
        right = _bs_board(mine, ai_shots, True)
        print("   " + ui.bold("Enemy waters".ljust(23)) + "      " + ui.bold("Your fleet"))
        for a, b in zip(left, right):
            print(" " + ui.pad(a, 24) + "      " + b)
        if msg:
            print("\n" + msg)
        sunk_theirs = [i for i in range(len(SHIPS)) if all(my_shots.get(c) for c, s in theirs.items() if s == i)]
        sunk_mine = [i for i in range(len(SHIPS)) if all(ai_shots.get(c) for c, s in mine.items() if s == i)]
        if len(sunk_theirs) == len(SHIPS):
            ui.success(f"You sank the whole fleet in {shots_fired} shots! ⚓")
            record_score("Battleship", shots_fired)
            return
        if len(sunk_mine) == len(SHIPS):
            ui.error("The AI sank your fleet.")
            return
        raw = ui.ask("Fire (e.g. B7, q = quit)").strip().upper()
        if raw == "Q":
            return
        if len(raw) < 2 or raw[0] not in "ABCDEFGHIJ" or not raw[1:].isdigit() or not 1 <= int(raw[1:]) <= 10:
            continue
        cell = ("ABCDEFGHIJ".index(raw[0]), int(raw[1:]) - 1)
        if cell in my_shots:
            msg = ui.yellow("You already fired there.")
            continue
        shots_fired += 1
        hit = cell in theirs
        my_shots[cell] = hit
        msg = ui.green("Hit!") if hit else ui.gray("Miss.")
        if hit and all(my_shots.get(c) for c, s in theirs.items() if s == theirs[cell]):
            msg = ui.c(f"You sank an enemy ship: {SHIPS[theirs[cell]][0]}!", "bold", "bright_green")
        target = ai.pick()
        ai_hit = target in mine
        ai_shots[target] = ai_hit
        sunk = ai_hit and all(ai_shots.get(c) for c, s in mine.items() if s == mine[target])
        ai.result(target, ai_hit, sunk)
        coord = f"{'ABCDEFGHIJ'[target[0]]}{target[1] + 1}"
        msg += "   " + (ui.red(f"The AI hit {coord}!" + (f" {SHIPS[mine[target]][0]} sank." if sunk else ""))
                        if ai_hit else ui.gray(f"The AI missed ({coord})."))


# --------------------------------------------------------------------------
# Sudoku
# --------------------------------------------------------------------------

def sudoku_candidates(grid: list[int], i: int) -> set[int]:
    r, c = divmod(i, 9)
    used = {grid[r * 9 + k] for k in range(9)} | {grid[k * 9 + c] for k in range(9)}
    br, bc = r // 3 * 3, c // 3 * 3
    used |= {grid[(br + a) * 9 + bc + b] for a in range(3) for b in range(3)}
    return set(range(1, 10)) - used


def sudoku_solve(grid: list[int], count_limit: int = 1, rng: random.Random | None = None) -> tuple[int, Optional[list[int]]]:
    """Returns (number of solutions up to count_limit, first solution)."""
    g = grid[:]
    solutions = 0
    first: Optional[list[int]] = None

    def rec() -> bool:
        nonlocal solutions, first
        best_i, best_c = -1, None
        for i in range(81):
            if g[i] == 0:
                cands = sudoku_candidates(g, i)
                if not cands:
                    return False
                if best_c is None or len(cands) < len(best_c):
                    best_i, best_c = i, cands
                    if len(cands) == 1:
                        break
        if best_i == -1:
            solutions += 1
            if first is None:
                first = g[:]
            return solutions >= count_limit
        order = list(best_c)  # type: ignore[arg-type]
        if rng:
            rng.shuffle(order)
        for v in order:
            g[best_i] = v
            if rec():
                return True
        g[best_i] = 0
        return False

    rec()
    return solutions, first


def sudoku_generate(clues: int = 32, rng: random.Random | None = None) -> tuple[list[int], list[int]]:
    rng = rng or random.Random()
    _, full = sudoku_solve([0] * 81, rng=rng)
    assert full
    puzzle = full[:]
    cells = list(range(81))
    rng.shuffle(cells)
    filled = 81
    for i in cells:
        if filled <= clues:
            break
        saved = puzzle[i]
        puzzle[i] = 0
        n, _ = sudoku_solve(puzzle, 2)
        if n != 1:
            puzzle[i] = saved
        else:
            filled -= 1
    return puzzle, full


def sudoku_lines(grid: list[int], given: list[int], wrong: set[int] | None = None) -> list[str]:
    wrong = wrong or set()
    lines = ["     1 2 3   4 5 6   7 8 9"]
    for r in range(9):
        if r % 3 == 0:
            lines.append("   " + ui.gray("+-------+-------+-------+"))
        cells = []
        for c in range(9):
            i = r * 9 + c
            v = grid[i]
            if c % 3 == 0:
                cells.append(ui.gray("|"))
            if not v:
                cells.append(ui.gray("·"))
            elif given[i]:
                cells.append(ui.bold(str(v)))
            elif i in wrong:
                cells.append(ui.c(str(v), "bold", "bright_red"))
            else:
                cells.append(ui.c(str(v), "bright_cyan"))
        lines.append(f" {r + 1} " + " ".join(cells) + " " + ui.gray("|"))
    lines.append("   " + ui.gray("+-------+-------+-------+"))
    return lines


@tool("games", "games-sudoku", "Sudoku", "Play generated sudokus (unique solution) or solve your own", ("sudoku", "numerot", "logiikka"))
def sudoku_tool() -> None:
    mode = ui.choose("Action", ["Play", "Solve your own sudoku"])
    if mode == 1:
        print(ui.gray("Enter 81 characters row by row (blanks as 0 or .), e.g. one row at a time."))
        raw = ""
        while len(raw) < 81:
            line = input("  ")
            raw += "".join(ch for ch in line if ch.isdigit() or ch == ".")
        grid = [int(ch) if ch.isdigit() else 0 for ch in raw[:81]]
        with ui.Spinner("Solving"):
            n, sol = sudoku_solve(grid, 2)
        if not sol:
            ui.error("There is no solution.")
            return
        for line in sudoku_lines(sol, grid):
            print(line)
        if n > 1:
            ui.warn("The sudoku has more than one solution – here is one of them.")
        return
    levels = [("easy", 40), ("medium", 32), ("hard", 26)]
    name, clues = levels[ui.choose("Difficulty", [n.capitalize() for n, _ in levels], 1)]
    with ui.Spinner("Generating a sudoku"):
        puzzle, solution = sudoku_generate(clues)
    grid = puzzle[:]
    wrong: set[int] = set()
    start = time.time()
    hints = 0
    while True:
        ui.clear()
        ui.header("Sudoku", f"{name} · row column number, e.g. 537 · 530 clears · ? hint · t check · r solution · q quit")
        for line in sudoku_lines(grid, puzzle, wrong):
            print(line)
        if grid == solution:
            took = time.time() - start + hints * 60
            ui.success(f"Solved in {ui.fmt_duration(time.time() - start)}! 🎉" + (f" ({hints} hints, +1 min each)" if hints else ""))
            record_score(f"Sudoku ({name})", round(took))
            return
        raw = ui.ask("Move").strip().lower().replace(" ", "")
        wrong.clear()
        if raw == "q":
            return
        if raw == "?":
            empty = [i for i in range(81) if grid[i] != solution[i]]
            i = random.choice(empty)
            grid[i] = solution[i]
            hints += 1
        elif raw == "t":
            wrong = {i for i in range(81) if grid[i] and grid[i] != solution[i]}
            if not wrong:
                ui.success("No mistakes so far.")
                time.sleep(0.8)
        elif raw == "r":
            grid = solution[:]
            for line in sudoku_lines(grid, puzzle):
                print(line)
            ui.info("Here is the solution.")
            return
        elif len(raw) == 3 and raw.isdigit() and raw[0] != "0" and raw[1] != "0":
            i = (int(raw[0]) - 1) * 9 + int(raw[1]) - 1
            if puzzle[i]:
                ui.warn("You can't change a given number.")
                time.sleep(0.7)
            else:
                grid[i] = int(raw[2])


# --------------------------------------------------------------------------
# Yatzy
# --------------------------------------------------------------------------

YATZY_CATS = ["Ones", "Twos", "Threes", "Fours", "Fives", "Sixes", "One pair", "Two pairs",
              "Three of a kind", "Four of a kind", "Small straight", "Large straight", "Full house", "Chance", "Yatzy"]


def yatzy_score(cat: str, dice: list[int]) -> int:
    c = Counter(dice)
    if cat in YATZY_CATS[:6]:
        n = YATZY_CATS.index(cat) + 1
        return n * c[n]
    pairs = sorted((v for v, k in c.items() if k >= 2), reverse=True)
    if cat == "One pair":
        return pairs[0] * 2 if pairs else 0
    if cat == "Two pairs":
        return (pairs[0] + pairs[1]) * 2 if len(pairs) >= 2 else 0
    if cat == "Three of a kind":
        v = max((v for v, k in c.items() if k >= 3), default=0)
        return v * 3
    if cat == "Four of a kind":
        v = max((v for v, k in c.items() if k >= 4), default=0)
        return v * 4
    if cat == "Small straight":
        return 15 if sorted(dice) == [1, 2, 3, 4, 5] else 0
    if cat == "Large straight":
        return 20 if sorted(dice) == [2, 3, 4, 5, 6] else 0
    if cat == "Full house":
        return sum(dice) if sorted(c.values()) == [2, 3] else 0
    if cat == "Chance":
        return sum(dice)
    if cat == "Yatzy":
        return 50 if len(c) == 1 else 0
    raise ValueError(cat)


def yatzy_total(card: dict[str, int]) -> tuple[int, int, int]:
    upper = sum(card.get(cat, 0) for cat in YATZY_CATS[:6])
    bonus = 50 if upper >= 63 else 0
    return upper, bonus, sum(card.values()) + bonus


DICE_FACES = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]


@tool("games", "games-yatzy", "Yatzy", "Nordic Yatzy for 1–4 players: roll, hold dice and collect points", ("yatzy", "jatsi", "nopat", "yahtzee"))
def yatzy_tool() -> None:
    n_players = ui.ask_int("Players", 1, 1, 4)
    names = [ui.ask(f"Player {i + 1} name", f"Player {i + 1}") for i in range(n_players)]
    cards: list[dict[str, int]] = [{} for _ in names]
    for _round in range(len(YATZY_CATS)):
        for p, name in enumerate(names):
            dice = [random.randint(1, 6) for _ in range(5)]
            throws = 1
            while True:
                ui.clear()
                ui.header(f"Yatzy – {name}", f"roll {throws}/3")
                print("   " + "   ".join(f"{i + 1}:{ui.c(DICE_FACES[d] + ' ' + str(d), 'bold', 'bright_yellow')}" for i, d in enumerate(dice)))
                if throws == 3:
                    break
                keep = ui.ask("Hold dice by number (e.g. 135), Enter = reroll all, s = score now", allow_empty=True)
                if keep.lower() in ("s", "k"):
                    break
                kept = {int(ch) - 1 for ch in keep if ch in "12345"}
                dice = [d if i in kept else random.randint(1, 6) for i, d in enumerate(dice)]
                throws += 1
            free = [c for c in YATZY_CATS if c not in cards[p]]
            options = [f"{c.ljust(12)} {ui.gray(str(yatzy_score(c, dice)).rjust(3) + ' p')}" for c in free]
            pick = free[ui.choose("Score in", options)]
            cards[p][pick] = yatzy_score(pick, dice)
    ui.clear()
    rows = []
    for c in YATZY_CATS:
        rows.append([c] + [card.get(c, 0) for card in cards])
        if c == "Sixes":
            rows.append([ui.gray("Bonus (≥63)")] + [yatzy_total(card)[1] for card in cards])
    rows.append([ui.bold("Total")] + [ui.bold(str(yatzy_total(card)[2])) for card in cards])
    ui.table(rows, ["Category"] + names, align=["<"] + [">"] * len(names))
    totals = [yatzy_total(card)[2] for card in cards]
    winner = names[totals.index(max(totals))]
    ui.success(f"{winner} won with {max(totals)} points!" if n_players > 1 else f"Score: {totals[0]}")
    for name, t in zip(names, totals):
        record_score("Yatzy", t, name)


# --------------------------------------------------------------------------
# Reversi
# --------------------------------------------------------------------------

REV_DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
REV_WEIGHTS = [
    [100, -20, 10, 5, 5, 10, -20, 100], [-20, -50, -2, -2, -2, -2, -50, -20], [10, -2, 1, 1, 1, 1, -2, 10],
    [5, -2, 1, 0, 0, 1, -2, 5], [5, -2, 1, 0, 0, 1, -2, 5], [10, -2, 1, 1, 1, 1, -2, 10],
    [-20, -50, -2, -2, -2, -2, -50, -20], [100, -20, 10, 5, 5, 10, -20, 100]]


def rev_new() -> list[list[int]]:
    b = [[0] * 8 for _ in range(8)]
    b[3][3] = b[4][4] = 2
    b[3][4] = b[4][3] = 1
    return b


def rev_flips(b: list[list[int]], r: int, c: int, p: int) -> list[tuple[int, int]]:
    if b[r][c]:
        return []
    out = []
    for dr, dc in REV_DIRS:
        line = []
        rr, cc = r + dr, c + dc
        while 0 <= rr < 8 and 0 <= cc < 8 and b[rr][cc] == 3 - p:
            line.append((rr, cc))
            rr, cc = rr + dr, cc + dc
        if line and 0 <= rr < 8 and 0 <= cc < 8 and b[rr][cc] == p:
            out.extend(line)
    return out


def rev_moves(b: list[list[int]], p: int) -> dict[tuple[int, int], list[tuple[int, int]]]:
    moves = {}
    for r in range(8):
        for c in range(8):
            f = rev_flips(b, r, c, p)
            if f:
                moves[(r, c)] = f
    return moves


def rev_apply(b: list[list[int]], move: tuple[int, int], flips: list[tuple[int, int]], p: int) -> list[list[int]]:
    nb = [row[:] for row in b]
    nb[move[0]][move[1]] = p
    for r, c in flips:
        nb[r][c] = p
    return nb


def rev_eval(b: list[list[int]], p: int) -> int:
    score = 0
    for r in range(8):
        for c in range(8):
            if b[r][c] == p:
                score += REV_WEIGHTS[r][c]
            elif b[r][c] == 3 - p:
                score -= REV_WEIGHTS[r][c]
    score += 5 * (len(rev_moves(b, p)) - len(rev_moves(b, 3 - p)))
    return score


def rev_search(b: list[list[int]], p: int, depth: int, alpha: float, beta: float, me: int) -> tuple[float, Optional[tuple[int, int]]]:
    moves = rev_moves(b, p)
    if depth == 0 or (not moves and not rev_moves(b, 3 - p)):
        return rev_eval(b, me), None
    if not moves:
        return rev_search(b, 3 - p, depth - 1, alpha, beta, me)[0], None
    best_move = None
    if p == me:
        best = -float("inf")
        for mv, fl in moves.items():
            val, _ = rev_search(rev_apply(b, mv, fl, p), 3 - p, depth - 1, alpha, beta, me)
            if val > best:
                best, best_move = val, mv
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best, best_move
    best = float("inf")
    for mv, fl in moves.items():
        val, _ = rev_search(rev_apply(b, mv, fl, p), 3 - p, depth - 1, alpha, beta, me)
        if val < best:
            best, best_move = val, mv
        beta = min(beta, best)
        if alpha >= beta:
            break
    return best, best_move


@tool("games", "games-reversi", "Reversi (Othello)", "Flip the opponent's discs to your colour – the AI loves corners", ("othello", "reversi", "lautapeli"))
def reversi_tool() -> None:
    depth = [1, 2, 4][ui.choose("AI", ["Easy", "Medium", "Hard"], 1)]
    b = rev_new()
    turn = 1
    msg = ""
    while True:
        my_moves, ai_moves = rev_moves(b, 1), rev_moves(b, 2)
        ui.clear()
        black = sum(row.count(1) for row in b)
        white = sum(row.count(2) for row in b)
        ui.header("Reversi", f"You ● {black} – {white} ○ AI")
        print("    " + " ".join("abcdefgh"))
        for r in range(8):
            cells = []
            for c in range(8):
                v = b[r][c]
                if v == 1:
                    cells.append(ui.c("●", "bright_white"))
                elif v == 2:
                    cells.append(ui.c("○", "bright_red"))
                elif turn == 1 and (r, c) in my_moves:
                    cells.append(ui.c("·", "bright_green"))
                else:
                    cells.append(ui.gray("·"))
            print(f" {r + 1}  " + " ".join(cells))
        if msg:
            print(msg)
        if not my_moves and not ai_moves:
            if black > white:
                ui.success(f"You won {black}–{white}! 🎉")
                record_score("Reversi", black - white)
            elif black < white:
                ui.error(f"The AI won {white}–{black}.")
            else:
                ui.info("Draw!")
            return
        if turn == 1:
            if not my_moves:
                msg = ui.yellow("You have no moves – the turn passes.")
                turn = 2
                continue
            raw = ui.ask("Move (e.g. d3, green dots = legal, q = quit)").strip().lower()
            if raw == "q":
                return
            if len(raw) != 2 or raw[0] not in "abcdefgh" or raw[1] not in "12345678":
                continue
            mv = (int(raw[1]) - 1, "abcdefgh".index(raw[0]))
            if mv not in my_moves:
                msg = ui.red("Illegal move.")
                continue
            b = rev_apply(b, mv, my_moves[mv], 1)
            msg = ""
            turn = 2
        else:
            if not ai_moves:
                msg = ui.yellow("The AI has no moves.")
                turn = 1
                continue
            with ui.Spinner("The AI is thinking"):
                _, mv = rev_search(b, 2, depth, -float("inf"), float("inf"), 2)
            mv = mv or next(iter(ai_moves))
            b = rev_apply(b, mv, ai_moves[mv], 2)
            msg = ui.gray(f"The AI played {'abcdefgh'[mv[1]]}{mv[0] + 1}.")
            turn = 1
