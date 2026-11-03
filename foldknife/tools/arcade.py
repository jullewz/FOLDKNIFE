"""Real-time terminal games: snake, tetris, 2048 and dodge. Control with the arrow keys or WASD."""
from __future__ import annotations

import random
import sys
import time

from ..core import keys, ui
from ..core.registry import tool
from .games import record_score


def _need_terminal() -> bool:
    if not keys.interactive():
        ui.error("This game needs an interactive terminal (it won't work through a pipe or an IDE console).")
        return False
    return True


def _frame(lines: list[str]) -> None:
    """Draws the whole screen at once without flicker."""
    sys.stdout.write("\x1b[H" + "\x1b[K\n".join(lines) + "\x1b[K\n\x1b[J")
    sys.stdout.flush()


# --------------------------------------------------------------------------
# Snake
# --------------------------------------------------------------------------

OPPOSITE = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}
DELTA = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}


class SnakeGame:
    def __init__(self, w: int = 24, h: int = 16, wrap: bool = False, rng: random.Random | None = None) -> None:
        self.w, self.h, self.wrap = w, h, wrap
        self.rng = rng or random.Random()
        cx, cy = w // 2, h // 2
        self.snake = [(cx - i, cy) for i in range(3)]
        self.dir = "RIGHT"
        self.pending = "RIGHT"
        self.alive = True
        self.score = 0
        self.food = self._place_food()

    def _place_food(self) -> tuple[int, int]:
        free = [(x, y) for x in range(self.w) for y in range(self.h) if (x, y) not in self.snake]
        return self.rng.choice(free) if free else (-1, -1)

    def turn(self, d: str) -> None:
        if d in DELTA and d != OPPOSITE[self.dir]:
            self.pending = d

    def step(self) -> None:
        self.dir = self.pending
        dx, dy = DELTA[self.dir]
        hx, hy = self.snake[0]
        nx, ny = hx + dx, hy + dy
        if self.wrap:
            nx, ny = nx % self.w, ny % self.h
        if not (0 <= nx < self.w and 0 <= ny < self.h) or (nx, ny) in self.snake[:-1]:
            self.alive = False
            return
        self.snake.insert(0, (nx, ny))
        if (nx, ny) == self.food:
            self.score += 1
            self.food = self._place_food()
        else:
            self.snake.pop()

    def render(self) -> list[str]:
        body = set(self.snake[1:])
        head = self.snake[0]
        border = ui.gray("██" * (self.w + 2))
        lines = [border]
        for y in range(self.h):
            row = [ui.gray("██")]
            for x in range(self.w):
                if (x, y) == head:
                    row.append(ui.c("██", "bright_yellow"))
                elif (x, y) in body:
                    row.append(ui.c("██", "bright_green"))
                elif (x, y) == self.food:
                    row.append(ui.c("()", "bright_red"))
                else:
                    row.append("  ")
            row.append(ui.gray("██"))
            lines.append("".join(row))
        lines.append(border)
        return lines


@tool("games", "games-snake", "Snake", "Classic snake: eat apples, grow and avoid the walls (arrows/WASD, p = pause, q = quit)",
      ("snake", "mato", "arcade"))
def snake_tool() -> None:
    if not _need_terminal():
        return
    wrap = ui.ask_yes_no("Wrap-around walls?", False)
    game = SnakeGame(min(30, max(12, (ui.term_width() - 4) // 2 - 1)), min(20, max(10, ui.term_height() - 6)), wrap)
    ui.clear()
    paused = False
    with keys.RawMode():
        while game.alive:
            delay = max(0.05, 0.16 - game.score * 0.004)
            end = time.time() + delay
            while True:
                left = end - time.time()
                if left <= 0:
                    break
                k = keys.get_key(left)
                if k in ("q", "ESC"):
                    game.alive = False
                    break
                if k == "p":
                    paused = not paused
                d = keys.direction(k)
                if d:
                    game.turn(d)
            if not game.alive:
                break
            if not paused:
                game.step()
            _frame(game.render() + [f"  Score: {ui.bold(str(game.score))}   " + ui.gray("arrows/WASD · p pause · q quit") +
                                    (ui.yellow("  PAUSED") if paused else "")])
    print(ui.c(f"\nGame over! Score: {game.score}", "bold", "bright_red"))
    record_score("Snake", game.score)


# --------------------------------------------------------------------------
# Tetris
# --------------------------------------------------------------------------

PIECES = {
    "I": ([(0, 1), (1, 1), (2, 1), (3, 1)], (0, 200, 220)),
    "O": ([(1, 0), (2, 0), (1, 1), (2, 1)], (230, 200, 0)),
    "T": ([(1, 0), (0, 1), (1, 1), (2, 1)], (170, 60, 200)),
    "S": ([(1, 0), (2, 0), (0, 1), (1, 1)], (60, 200, 60)),
    "Z": ([(0, 0), (1, 0), (1, 1), (2, 1)], (220, 50, 50)),
    "J": ([(0, 0), (0, 1), (1, 1), (2, 1)], (50, 90, 230)),
    "L": ([(2, 0), (0, 1), (1, 1), (2, 1)], (240, 140, 20)),
}


def rotate(cells: list[tuple[int, int]], kind: str) -> list[tuple[int, int]]:
    if kind == "O":
        return cells
    size = 4 if kind == "I" else 3
    return [(size - 1 - y, x) for x, y in cells]


class Tetris:
    W, H = 10, 20

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.board: list[list[tuple[int, int, int] | None]] = [[None] * self.W for _ in range(self.H)]
        self.score = self.lines = 0
        self.level = 1
        self.over = False
        self.bag: list[str] = []
        self.next_kind = self._draw()
        self._spawn()

    def _draw(self) -> str:
        if not self.bag:
            self.bag = list(PIECES)
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def _spawn(self) -> None:
        self.kind = self.next_kind
        self.next_kind = self._draw()
        self.cells = list(PIECES[self.kind][0])
        self.x, self.y = 3, 0
        if self._collides(self.cells, self.x, self.y):
            self.over = True

    def _collides(self, cells: list[tuple[int, int]], ox: int, oy: int) -> bool:
        for cx, cy in cells:
            x, y = cx + ox, cy + oy
            if x < 0 or x >= self.W or y >= self.H:
                return True
            if y >= 0 and self.board[y][x] is not None:
                return True
        return False

    def move(self, dx: int) -> None:
        if not self._collides(self.cells, self.x + dx, self.y):
            self.x += dx

    def rotate(self) -> None:
        new = rotate(self.cells, self.kind)
        for kick in (0, -1, 1, -2, 2):
            if not self._collides(new, self.x + kick, self.y):
                self.cells, self.x = new, self.x + kick
                return

    def soft_drop(self) -> bool:
        if not self._collides(self.cells, self.x, self.y + 1):
            self.y += 1
            return True
        self._lock()
        return False

    def hard_drop(self) -> None:
        dist = 0
        while not self._collides(self.cells, self.x, self.y + 1):
            self.y += 1
            dist += 1
        self.score += dist * 2
        self._lock()

    def ghost_y(self) -> int:
        y = self.y
        while not self._collides(self.cells, self.x, y + 1):
            y += 1
        return y

    def _lock(self) -> None:
        color = PIECES[self.kind][1]
        for cx, cy in self.cells:
            if 0 <= cy + self.y < self.H:
                self.board[cy + self.y][cx + self.x] = color
        full = [r for r in range(self.H) if all(self.board[r])]
        for r in full:
            del self.board[r]
            self.board.insert(0, [None] * self.W)
        if full:
            self.lines += len(full)
            self.score += [0, 100, 300, 500, 800][len(full)] * self.level
            self.level = 1 + self.lines // 10
        self._spawn()

    def render(self) -> list[str]:
        active = {(cx + self.x, cy + self.y) for cx, cy in self.cells}
        gy = self.ghost_y()
        ghost = {(cx + self.x, cy + gy) for cx, cy in self.cells}
        color = PIECES[self.kind][1]
        nxt_cells = set(PIECES[self.next_kind][0])
        nxt_color = PIECES[self.next_kind][1]
        side = ["", ui.bold("NEXT"), "", "", "", "", ui.bold(f"Score {self.score}"), f"Lines {self.lines}",
                f"Level {self.level}", "", ui.gray("← → move"), ui.gray("↑ rotate"), ui.gray("↓ drop"),
                ui.gray("space"), ui.gray("  = hard drop"), ui.gray("p pause, q quit")]
        for yy in range(2):
            side[2 + yy] = "".join(ui.rgb("██", *nxt_color) if (xx, yy) in nxt_cells else "  " for xx in range(4))
        lines = [ui.gray("╔" + "══" * self.W + "╗")]
        for y in range(self.H):
            row = []
            for x in range(self.W):
                if (x, y) in active:
                    row.append(ui.rgb("██", *color))
                elif self.board[y][x]:
                    row.append(ui.rgb("██", *self.board[y][x]))  # type: ignore[misc]
                elif (x, y) in ghost:
                    row.append(ui.gray("░░"))
                else:
                    row.append(ui.gray(" ·"))
            lines.append(ui.gray("║") + "".join(row) + ui.gray("║") + "  " + (side[y] if y < len(side) else ""))
        lines.append(ui.gray("╚" + "══" * self.W + "╝"))
        return lines


@tool("games", "games-tetris", "Tetris", "Falling blocks – fill the lines! (arrows, space drops, p pause)", ("tetris", "palikat", "arcade"))
def tetris_tool() -> None:
    if not _need_terminal():
        return
    game = Tetris()
    ui.clear()
    paused = False
    with keys.RawMode():
        next_tick = time.time()
        while not game.over:
            interval = max(0.08, 0.8 - (game.level - 1) * 0.07)
            k = keys.get_key(max(0.0, min(0.05, next_tick - time.time())))
            if k in ("q", "ESC"):
                break
            if k == "p":
                paused = not paused
            if not paused and k:
                d = keys.direction(k)
                if d == "LEFT":
                    game.move(-1)
                elif d == "RIGHT":
                    game.move(1)
                elif d == "UP":
                    game.rotate()
                elif d == "DOWN":
                    game.soft_drop()
                    game.score += 1
                elif k == " ":
                    game.hard_drop()
                    next_tick = time.time() + interval
            if not paused and time.time() >= next_tick:
                game.soft_drop()
                next_tick = time.time() + interval
            _frame(game.render() + ([ui.yellow("  PAUSED")] if paused else [""]))
    print(ui.c(f"\nGame over! Score {game.score}, lines {game.lines}", "bold", "bright_red"))
    record_score("Tetris", game.score)


# --------------------------------------------------------------------------
# 2048
# --------------------------------------------------------------------------

def merge_line(line: list[int]) -> tuple[list[int], int]:
    """Slides and merges a row to the left. Returns (new row, points gained)."""
    tiles = [v for v in line if v]
    out: list[int] = []
    gained = 0
    i = 0
    while i < len(tiles):
        if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
            out.append(tiles[i] * 2)
            gained += tiles[i] * 2
            i += 2
        else:
            out.append(tiles[i])
            i += 1
    return out + [0] * (len(line) - len(out)), gained


def move_board(board: list[list[int]], direction: str) -> tuple[list[list[int]], int, bool]:
    n = len(board)
    gained = 0
    new = [row[:] for row in board]
    for i in range(n):
        if direction in ("LEFT", "RIGHT"):
            line = board[i][:] if direction == "LEFT" else board[i][::-1]
        else:
            line = [board[r][i] for r in range(n)]
            if direction == "DOWN":
                line = line[::-1]
        merged, g = merge_line(line)
        gained += g
        if direction in ("RIGHT", "DOWN"):
            merged = merged[::-1]
        for j in range(n):
            if direction in ("LEFT", "RIGHT"):
                new[i][j] = merged[j]
            else:
                new[j][i] = merged[j]
    return new, gained, new != board


def can_move(board: list[list[int]]) -> bool:
    return any(move_board(board, d)[2] for d in ("UP", "DOWN", "LEFT", "RIGHT"))


TILE_COLORS = {0: (60, 58, 50), 2: (238, 228, 218), 4: (237, 224, 200), 8: (242, 177, 121), 16: (245, 149, 99),
               32: (246, 124, 95), 64: (246, 94, 59), 128: (237, 207, 114), 256: (237, 204, 97), 512: (237, 200, 80),
               1024: (237, 197, 63), 2048: (237, 194, 46)}


def _render_2048(board: list[list[int]], score: int) -> list[str]:
    lines = [ui.bold(f"  2048   score {score}"), ""]
    for row in board:
        for part in range(3):
            cells = []
            for v in row:
                bg = TILE_COLORS.get(v, (60, 58, 60))
                fg = (119, 110, 101) if v in (2, 4) else (249, 246, 242)
                text = (str(v) if v else "").center(8) if part == 1 else " " * 8
                cells.append(ui.fg_bg_rgb(text, fg, bg) if ui.color_enabled() else f"[{text}]")
            lines.append("  " + " ".join(cells))
        lines.append("")
    lines.append(ui.gray("  arrows/WASD move · q quits"))
    return lines


@tool("games", "games-2048", "2048", "Merge equal numbers and aim for the 2048 tile (arrows or WASD)", ("2048", "laatat", "puzzle"))
def game2048_tool() -> None:
    board = [[0] * 4 for _ in range(4)]

    def spawn() -> None:
        empty = [(r, c) for r in range(4) for c in range(4) if not board[r][c]]
        if empty:
            r, c = random.choice(empty)
            board[r][c] = 4 if random.random() < 0.1 else 2

    spawn()
    spawn()
    score = 0
    won = False
    ui.clear()
    while True:
        _frame(_render_2048(board, score)) if keys.interactive() else print("\n".join(_render_2048(board, score)))
        if not can_move(board):
            print(ui.c("  No more moves!", "bold", "bright_red"))
            break
        k = keys.getch()
        if k in ("q", "ESC"):
            break
        d = keys.direction(k)
        if not d:
            continue
        new, gained, changed = move_board(board, d)
        if changed:
            board[:] = new
            score += gained
            spawn()
        if not won and any(2048 in row for row in board):
            won = True
            _frame(_render_2048(board, score)) if keys.interactive() else None
            ui.success("2048! You won – you can keep going.")
            time.sleep(1.5)
    ui.info(f"Score {score}, biggest tile {max(max(r) for r in board)}")
    record_score("2048", score)


# --------------------------------------------------------------------------
# Dodge
# --------------------------------------------------------------------------

@tool("games", "games-dodge", "Dodge", "Dodge the falling rocks for as long as you can (← →)", ("dodge", "dodge", "arcade"))
def dodge_tool() -> None:
    if not _need_terminal():
        return
    w, h = 21, 16
    px = w // 2
    rocks: list[list[int]] = []
    ticks = 0
    ui.clear()
    alive = True
    with keys.RawMode():
        while alive:
            delay = max(0.04, 0.12 - ticks * 0.0002)
            end = time.time() + delay
            while (left := end - time.time()) > 0:
                k = keys.get_key(left)
                d = keys.direction(k)
                if k in ("q", "ESC"):
                    alive = False
                    break
                if d == "LEFT":
                    px = max(0, px - 1)
                elif d == "RIGHT":
                    px = min(w - 1, px + 1)
            if not alive:
                break
            ticks += 1
            for r in rocks:
                r[1] += 1
            rocks = [r for r in rocks if r[1] < h]
            if random.random() < min(0.9, 0.25 + ticks / 600):
                rocks.append([random.randrange(w), 0])
            if any(r == [px, h - 1] for r in rocks):
                alive = False
            grid = [["  "] * w for _ in range(h)]
            for x, y in rocks:
                grid[y][x] = ui.c("◆ ", "bright_red")
            grid[h - 1][px] = ui.c("▲ ", "bright_green")
            _frame([ui.gray("┌" + "──" * w + "┐")] + [ui.gray("│") + "".join(row) + ui.gray("│") for row in grid] +
                   [ui.gray("└" + "──" * w + "┘"), f"  Time {ticks / 10:.1f} · score {ticks}"])
    print(ui.c(f"\nHit! Score {ticks}", "bold", "bright_red"))
    record_score("Dodge", ticks)
