"""Maths: safe calculator, graphs, equations, primes, statistics, matrices and finance."""
from __future__ import annotations

import ast
import cmath
import math
import operator
import random
import re
import statistics
import time
from fractions import Fraction
from typing import Any, Callable

from ..core import ui
from ..core.registry import tool

Number = Any  # int | float | Fraction | complex

# --------------------------------------------------------------------------
# Safe expression evaluation (AST, no eval())
# --------------------------------------------------------------------------


class CalcError(ValueError):
    pass


_state = {"degrees": False}



_EN_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
            "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_EN_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_EN_SCALES = [(10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")]


def english_number_words(n: int) -> str:
    """12345 -> 'twelve thousand three hundred forty-five'."""
    if n < 0:
        return "minus " + english_number_words(-n)
    if n < 20:
        return _EN_ONES[n]
    if n < 100:
        return _EN_TENS[n // 10] + ("-" + _EN_ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return _EN_ONES[n // 100] + " hundred" + (" " + english_number_words(n % 100) if n % 100 else "")
    for size, name in _EN_SCALES:
        if n >= size:
            return english_number_words(n // size) + " " + name + (" " + english_number_words(n % size) if n % size else "")
    return str(n)

def _to_rad(x: float) -> float:
    return math.radians(x) if _state["degrees"] else x


def _from_rad(x: float) -> float:
    return math.degrees(x) if _state["degrees"] else x


def _factorial(n: Number) -> int:
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    if isinstance(n, Fraction) and n.denominator == 1:
        n = int(n)
    if not isinstance(n, int) or n < 0:
        raise CalcError("Factorial is only defined for non-negative integers.")
    if n > 20000:
        raise CalcError("Factorial too large (max 20000!).")
    return math.factorial(n)


def _log(x: float, base: float | None = None) -> float:
    return math.log10(x) if base is None else math.log(x, base)


def _fib(n: int) -> int:
    n = int(n)
    if n < 0 or n > 100000:
        raise CalcError("fib(n): 0 ≤ n ≤ 100000")
    a, b = 0, 1
    for bit in bin(n)[2:]:
        c = a * (2 * b - a)
        d = a * a + b * b
        a, b = (d, c + d) if bit == "1" else (c, d)
    return a


def _isprime(n: Number) -> int:
    return int(is_prime(int(n)))


FUNCS: dict[str, Callable[..., Any]] = {
    "sqrt": lambda x: cmath.sqrt(x) if (isinstance(x, (int, float, Fraction)) and x < 0) else math.sqrt(x),
    "cbrt": lambda x: math.copysign(abs(float(x)) ** (1 / 3), float(x)),
    "root": lambda x, n: math.copysign(abs(float(x)) ** (1 / float(n)), float(x)),
    "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil, "trunc": math.trunc,
    "exp": math.exp, "ln": math.log, "log": _log, "lg": math.log10, "log10": math.log10, "log2": math.log2,
    "sin": lambda x: math.sin(_to_rad(x)), "cos": lambda x: math.cos(_to_rad(x)),
    "tan": lambda x: math.tan(_to_rad(x)), "cot": lambda x: 1 / math.tan(_to_rad(x)),
    "asin": lambda x: _from_rad(math.asin(x)), "acos": lambda x: _from_rad(math.acos(x)),
    "atan": lambda x: _from_rad(math.atan(x)), "atan2": lambda y, x: _from_rad(math.atan2(y, x)),
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "factorial": _factorial, "fact": _factorial, "gcd": math.gcd, "lcm": math.lcm,
    "comb": math.comb, "ncr": math.comb, "perm": math.perm, "npr": math.perm,
    "hypot": math.hypot, "min": min, "max": max,
    "sum": lambda *a: sum(a), "avg": lambda *a: sum(a) / len(a), "mean": lambda *a: sum(a) / len(a),
    "median": lambda *a: statistics.median(a), "deg": math.degrees, "rad": math.radians,
    "fib": _fib, "isprime": _isprime, "sign": lambda x: (x > 0) - (x < 0),
    "rand": random.random, "randint": random.randint, "frac": lambda x: Fraction(x).limit_denominator(10 ** 6),
}

CONSTS: dict[str, Number] = {"pi": math.pi, "π": math.pi, "e": math.e, "tau": math.tau,
                             "phi": (1 + 5 ** 0.5) / 2, "inf": math.inf, "i": 1j, "j": 1j}


def _safe_pow(a: Number, b: Number) -> Number:
    if isinstance(a, (int, Fraction)) and isinstance(b, int):
        if abs(a) > 1 and b > 0:
            bits = b * math.log2(abs(float(a)))
            if bits > 200_000:
                raise CalcError("The result would be too large (over 60,000 digits).")
    try:
        return a ** b
    except OverflowError as exc:
        raise CalcError("Overflow – the result is too large.") from exc


_BINOPS: dict[type, Callable[[Number, Number], Number]] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: _safe_pow,
}


def preprocess(expr: str) -> str:
    """Converts human-friendly notation into a Python expression."""
    s = expr.strip()
    s = (s.replace("^", "**").replace("×", "*").replace("·", "*").replace("÷", "/").replace("−", "-")
         .replace("√", "sqrt").replace("²", "**2").replace("³", "**3"))
    if not re.search(r"[A-Za-z_]\w*\s*\(", s):  # no function calls → a comma is a decimal separator
        s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*%(?!\s*[\w(.])", r"(\1/100)", s)
    s = re.sub(r"(\d+)!(?!=)", r"factorial(\1)", s)
    # Implicit multiplication: 2(3+4), (1+2)(3+4), 2x, 3pi – but not log10(…), 1e5 or 0x1F
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?=\()", r"\1*", s)
    s = re.sub(r"\)\s*(?=\()", ")*", s)
    s = re.sub(r"\b(\d+(?:\.\d+)?)(?=[A-Za-zπ])(?![eE][+-]?\d)(?![xXbBoO][0-9a-fA-F])", r"\1*", s)
    s = re.sub(r"\)\s*(?=[A-Za-zπ\d])", ")*", s)
    return s


def evaluate(expr: str, variables: dict[str, Number] | None = None, exact: bool = False) -> Number:
    """Evaluates an expression safely. exact=True uses fractions for exact arithmetic."""
    variables = variables or {}
    src = preprocess(expr)
    if not src:
        raise CalcError("Empty expression.")
    if len(src) > 2000:
        raise CalcError("Expression too long.")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as exc:
        raise CalcError(f"The expression isn't valid (position {exc.offset}).") from exc

    def visit(node: ast.AST) -> Number:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float, complex)):
                raise CalcError("Only numbers are allowed.")
            if exact and isinstance(node.value, float):
                return Fraction(repr(node.value))
            if exact and isinstance(node.value, int):
                return Fraction(node.value)
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and exact and isinstance(right, Fraction) and right.denominator == 1:
                right = int(right)
            try:
                return _BINOPS[type(node.op)](left, right)
            except ZeroDivisionError as exc:
                raise CalcError("Division by zero.") from exc
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = visit(node.operand)
            return -v if isinstance(node.op, ast.USub) else +v
        if isinstance(node, ast.Name):
            if node.id in variables:
                return variables[node.id]
            if node.id in CONSTS:
                return CONSTS[node.id]
            raise CalcError(f"Unknown name: {node.id}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.keywords:
                raise CalcError("Keyword arguments aren't supported.")
            fn = FUNCS.get(node.func.id.lower())
            if fn is None:
                raise CalcError(f"Unknown function: {node.func.id}")
            args = [visit(a) for a in node.args]
            if node.func.id.lower() not in ("frac", "abs", "min", "max", "sum", "avg", "mean", "median"):
                args = [float(a) if isinstance(a, Fraction) and node.func.id.lower() not in
                        ("factorial", "fact", "gcd", "lcm", "comb", "ncr", "perm", "npr", "fib", "isprime", "round", "floor", "ceil", "trunc")
                        else (int(a) if isinstance(a, Fraction) and a.denominator == 1 else a) for a in args]
            try:
                return fn(*args)
            except (ValueError, TypeError) as exc:
                raise CalcError(f"{node.func.id}: {exc}") from exc
            except OverflowError as exc:
                raise CalcError("Overflow.") from exc
        raise CalcError("The expression contains something I can't calculate.")

    result = visit(tree)
    if isinstance(result, complex) and abs(result.imag) < 1e-12:
        result = result.real
    return result


def format_result(value: Number, decimals: int = 12) -> str:
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return format_result(int(value))
        return f"{value.numerator}/{value.denominator} (≈ {format_result(float(value))})"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        digits = len(str(abs(value)))
        if digits > 40:
            s = str(value)
            return f"{s[:20]}…{s[-10:]} ({digits} digits)"
        return ui.fi_num(value, 0) if digits > 4 else str(value)
    if isinstance(value, complex):
        re_, im = format_result(value.real), format_result(abs(value.imag))
        return f"{re_} {'+' if value.imag >= 0 else '-'} {im}i"
    if isinstance(value, float):
        if math.isnan(value):
            return "undefined (NaN)"
        if math.isinf(value):
            return "infinity" if value > 0 else "-infinity"
        if value == int(value) and abs(value) < 1e15:
            return format_result(int(value))
        s = f"{value:.{decimals}g}"
        if "e" in s:
            mant, exp = s.split("e")
            return f"{mant} × 10^{int(exp)}"
        return s
    return str(value)


# --------------------------------------------------------------------------
# Primes and number theory
# --------------------------------------------------------------------------

def is_prime(n: int) -> bool:
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for p in small:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in small:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _pollard_rho(n: int) -> int:
    if n % 2 == 0:
        return 2
    while True:
        y, c, m = random.randrange(1, n), random.randrange(1, n), 128
        g = r = q = 1
        x = ys = y
        while g == 1:
            x = y
            for _ in range(r):
                y = (y * y + c) % n
            k = 0
            while k < r and g == 1:
                ys = y
                for _ in range(min(m, r - k)):
                    y = (y * y + c) % n
                    q = q * abs(x - y) % n
                g = math.gcd(q, n)
                k += m
            r *= 2
        if g == n:
            g = 1
            while g == 1:
                ys = (ys * ys + c) % n
                g = math.gcd(abs(x - ys), n)
        if g != n:
            return g


def factorize(n: int) -> dict[int, int]:
    """Prime factors as {prime: exponent}."""
    if n < 1:
        raise ValueError("Only positive integers can be factored.")
    factors: dict[int, int] = {}
    for p in (2, 3, 5):
        while n % p == 0:
            factors[p] = factors.get(p, 0) + 1
            n //= p
    i, step = 7, [4, 2, 4, 2, 4, 6, 2, 6]
    k = 0
    while i * i <= n and i < 100_000:
        while n % i == 0:
            factors[i] = factors.get(i, 0) + 1
            n //= i
        i += step[k % 8]
        k += 1
    stack = [n] if n > 1 else []
    while stack:
        m = stack.pop()
        if m == 1:
            continue
        if is_prime(m):
            factors[m] = factors.get(m, 0) + 1
            continue
        d = _pollard_rho(m)
        stack.extend([d, m // d])
    return dict(sorted(factors.items()))


_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def format_factors(f: dict[int, int]) -> str:
    return " · ".join(f"{p}{str(e).translate(_SUP) if e > 1 else ''}" for p, e in f.items()) or "1"


def divisors(n: int) -> list[int]:
    divs = [1]
    for p, e in factorize(n).items():
        divs = [d * p ** k for d in divs for k in range(e + 1)]
    return sorted(divs)


def sieve(limit: int) -> list[int]:
    if limit < 2:
        return []
    flags = bytearray([1]) * (limit + 1)
    flags[0:2] = b"\x00\x00"
    for i in range(2, int(limit ** 0.5) + 1):
        if flags[i]:
            flags[i * i::i] = bytearray(len(range(i * i, limit + 1, i)))
    return [i for i, f in enumerate(flags) if f]


def next_prime(n: int) -> int:
    n = max(2, n + 1)
    while not is_prime(n):
        n += 1
    return n


def is_square(n: int) -> bool:
    return n >= 0 and math.isqrt(n) ** 2 == n


def roman(n: int) -> str:
    if not 0 < n < 4000:
        raise ValueError("Roman numerals: 1–3999")
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"),
            (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = []
    for v, s in vals:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def collatz(n: int, limit: int = 100000) -> list[int]:
    seq = [n]
    while n != 1 and len(seq) < limit:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        seq.append(n)
    return seq


def number_facts(n: int) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [("Parity", "even" if n % 2 == 0 else "odd")]
    if n > 1:
        rows.append(("Prime", "yes ✔" if is_prime(n) else "no"))
        if n < 10 ** 30:
            rows.append(("Prime factors", format_factors(factorize(n))))
    if 0 < n < 10 ** 15:
        divs = divisors(n)
        s = sum(divs) - n
        rows.append(("Divisors", f"{len(divs)}" + (f": {', '.join(map(str, divs))}" if len(divs) <= 24 else "")))
        rows.append(("Sum of divisors", f"{s} → " + ("perfect number!" if s == n else "abundant number" if s > n else "deficient number")))
    if n >= 0:
        rows.append(("Square", f"yes ({math.isqrt(n)}²)" if is_square(n) else "no"))
        root3 = round(n ** (1 / 3)) if n < 10 ** 45 else 0
        rows.append(("Cube", f"yes ({root3}³)" if root3 ** 3 == n else "no"))
        rows.append(("Triangular number", "yes" if is_square(8 * n + 1) else "no"))
        rows.append(("Fibonacci number", "yes" if is_square(5 * n * n + 4) or is_square(5 * n * n - 4) else "no"))
    digits = str(abs(n))
    rows.append(("Palindrome", "yes" if digits == digits[::-1] else "no"))
    rows.append(("Digit sum", str(sum(map(int, digits)))))
    if n > 0:
        rows.append(("Armstrong number", "yes" if sum(int(d) ** len(digits) for d in digits) == n else "no"))
        rows.append(("Harshad number", "yes" if n % sum(map(int, digits)) == 0 else "no"))
    rows.append(("Binary", bin(n)))
    rows.append(("Hex", hex(n)))
    rows.append(("Octal", oct(n)))
    if 0 < n < 4000:
        rows.append(("Roman", roman(n)))
    if 0 < n < 10 ** 6:
        rows.append(("Collatz steps", str(len(collatz(n)) - 1)))
    try:
        from .finnish import number_to_words

        if abs(n) < 10 ** 15:
            rows.append(("In words", english_number_words(n)))
    except Exception:  # noqa: BLE001
        pass
    return rows


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------

def parse_numbers(text: str) -> list[float]:
    tokens = [t for t in re.split(r"[;\s]+", text.strip()) if t]
    out: list[float] = []
    for tok in tokens:
        tok = tok.strip()
        if tok.count(",") > 1 or (tok.endswith(",") and tok[:-1].replace(".", "").lstrip("-").isdigit()):
            parts = [p for p in tok.split(",") if p]
        else:
            parts = [tok]
        for p in parts:
            p = p.replace(",", ".") if "." not in p else p
            try:
                out.append(float(p))
            except ValueError:
                raise ValueError(f"Not a number: {p!r}") from None
    return out


def quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        raise ValueError("No values.")
    pos = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def describe(values: list[float]) -> list[tuple[str, float | str]]:
    vals = sorted(values)
    n = len(vals)
    mean = sum(vals) / n
    rows: list[tuple[str, float | str]] = [("Count", n), ("Sum", sum(vals)), ("Average", mean),
                                          ("Median", statistics.median(vals))]
    modes = statistics.multimode(vals)
    rows.append(("Mode", ", ".join(format_result(m) for m in modes[:5]) if len(modes) < n else "no repeats"))
    rows += [("Min", vals[0]), ("Max", vals[-1]), ("Range", vals[-1] - vals[0])]
    if n > 1:
        rows += [("Standard deviation (sample)", statistics.stdev(vals)), ("Standard deviation (population)", statistics.pstdev(vals)),
                 ("Variance (sample)", statistics.variance(vals))]
        q1, q3 = quantile(vals, 0.25), quantile(vals, 0.75)
        iqr = q3 - q1
        rows += [("Lower quartile Q1", q1), ("Upper quartile Q3", q3), ("Interquartile range", iqr)]
        outliers = [v for v in vals if v < q1 - 1.5 * iqr or v > q3 + 1.5 * iqr]
        rows.append(("Outliers", ", ".join(format_result(v) for v in outliers[:10]) or "no"))
        if mean:
            rows.append(("Coefficient of variation", f"{statistics.stdev(vals) / abs(mean) * 100:.1f} %"))
    if all(v > 0 for v in vals):
        rows += [("Geometric mean", statistics.geometric_mean(vals)),
                 ("Harmonic mean", statistics.harmonic_mean(vals))]
    return rows


# --------------------------------------------------------------------------
# Matrices (exact fractions)
# --------------------------------------------------------------------------

Matrix = list[list[Fraction]]


def parse_matrix(text: str) -> Matrix:
    rows = [r for r in re.split(r"[;\n]", text.strip()) if r.strip()]
    m = [[Fraction(x.replace(",", ".")) for x in re.split(r"[\s,]+", r.strip()) if x] for r in rows]
    if not m or any(len(r) != len(m[0]) for r in m):
        raise ValueError("All rows must have the same number of values.")
    return m


def mat_str(m: Matrix) -> list[str]:
    cells = [[format_result(v) if not isinstance(v, Fraction) or v.denominator == 1 else f"{v.numerator}/{v.denominator}"
              for v in row] for row in m]
    w = max(len(c) for row in cells for c in row)
    n = len(cells)
    out = []
    for i, row in enumerate(cells):
        left, right = ("⎡", "⎤") if i == 0 else ("⎣", "⎦") if i == n - 1 else ("⎢", "⎥")
        if n == 1:
            left, right = "[", "]"
        out.append(left + " ".join(c.rjust(w) for c in row) + right)
    return out


def mat_mul(a: Matrix, b: Matrix) -> Matrix:
    if len(a[0]) != len(b):
        raise ValueError("A's column count must equal B's row count.")
    return [[sum((a[i][k] * b[k][j] for k in range(len(b))), Fraction(0)) for j in range(len(b[0]))] for i in range(len(a))]


def transpose(m: Matrix) -> Matrix:
    return [list(r) for r in zip(*m)]


def rref(m: Matrix) -> tuple[Matrix, int]:
    a = [row[:] for row in m]
    rows, cols = len(a), len(a[0])
    r = 0
    for c in range(cols):
        pivot = next((i for i in range(r, rows) if a[i][c] != 0), None)
        if pivot is None:
            continue
        a[r], a[pivot] = a[pivot], a[r]
        pv = a[r][c]
        a[r] = [x / pv for x in a[r]]
        for i in range(rows):
            if i != r and a[i][c] != 0:
                f = a[i][c]
                a[i] = [x - f * y for x, y in zip(a[i], a[r])]
        r += 1
        if r == rows:
            break
    return a, r


def determinant(m: Matrix) -> Fraction:
    n = len(m)
    if any(len(r) != n for r in m):
        raise ValueError("The determinant needs a square matrix.")
    a = [row[:] for row in m]
    det = Fraction(1)
    for c in range(n):
        pivot = next((i for i in range(c, n) if a[i][c] != 0), None)
        if pivot is None:
            return Fraction(0)
        if pivot != c:
            a[c], a[pivot] = a[pivot], a[c]
            det = -det
        det *= a[c][c]
        for i in range(c + 1, n):
            f = a[i][c] / a[c][c]
            a[i] = [x - f * y for x, y in zip(a[i], a[c])]
    return det


def inverse(m: Matrix) -> Matrix:
    n = len(m)
    if determinant(m) == 0:
        raise ValueError("The matrix isn't invertible (determinant is 0).")
    aug = [row[:] + [Fraction(int(i == j)) for j in range(n)] for i, row in enumerate(m)]
    red, _ = rref(aug)
    return [row[n:] for row in red]


def solve_linear(aug: Matrix) -> tuple[str, list[Fraction] | None]:
    n = len(aug[0]) - 1
    red, rank = rref(aug)
    for row in red:
        if all(v == 0 for v in row[:-1]) and row[-1] != 0:
            return "no solution", None
    coef_rank = sum(1 for row in red if any(v != 0 for v in row[:-1]))
    if coef_rank < n:
        return "infinitely many solutions", None
    return "a unique solution", [red[i][-1] for i in range(n)]


def solve_quadratic(a: float, b: float, c: float) -> list[complex | float]:
    if a == 0:
        if b == 0:
            raise ValueError("Not an equation (a = b = 0).")
        return [-c / b]
    d = b * b - 4 * a * c
    if d >= 0:
        s = math.sqrt(d)
        return sorted({(-b - s) / (2 * a), (-b + s) / (2 * a)})
    s = cmath.sqrt(d)
    return [(-b - s) / (2 * a), (-b + s) / (2 * a)]


# --------------------------------------------------------------------------
# Graph (braille characters)
# --------------------------------------------------------------------------

_BRAILLE = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]]
PLOT_COLORS = ["bright_cyan", "bright_yellow", "bright_magenta", "bright_green", "bright_red"]


def make_func(expr: str) -> Callable[[float], float]:
    def f(x: float) -> float:
        v = evaluate(expr, {"x": x})
        if isinstance(v, complex):
            raise CalcError("complex result")
        return float(v)
    return f


def plot(exprs: list[str], x_min: float, x_max: float, width: int = 70, height: int = 20,
         y_range: tuple[float, float] | None = None) -> list[str]:
    funcs = [make_func(e) for e in exprs]
    dots_w, dots_h = width * 2, height * 4
    xs = [x_min + i * (x_max - x_min) / (dots_w - 1) for i in range(dots_w)]
    series: list[list[float | None]] = []
    for f in funcs:
        ys: list[float | None] = []
        for x in xs:
            try:
                y = f(x)
                ys.append(y if math.isfinite(y) else None)
            except (CalcError, ValueError, ZeroDivisionError, OverflowError):
                ys.append(None)
        series.append(ys)
    finite = sorted(y for s in series for y in s if y is not None)
    if not finite:
        raise CalcError("The function has no values in this range.")
    if y_range:
        y_lo, y_hi = y_range
    else:
        y_lo, y_hi = quantile(finite, 0.02), quantile(finite, 0.98)
        if y_hi - y_lo < 1e-9:
            y_lo, y_hi = y_lo - 1, y_hi + 1
        pad = (y_hi - y_lo) * 0.08
        y_lo, y_hi = y_lo - pad, y_hi + pad
    grid = [[0] * width for _ in range(height)]
    owner = [[-1] * width for _ in range(height)]

    def to_row(y: float) -> int:
        return int(round((y_hi - y) / (y_hi - y_lo) * (dots_h - 1)))

    def setdot(dx: int, dy: int, idx: int) -> None:
        if 0 <= dx < dots_w and 0 <= dy < dots_h:
            cy, cx = dy // 4, dx // 2
            grid[cy][cx] |= _BRAILLE[dy % 4][dx % 2]
            owner[cy][cx] = idx

    for idx, ys in enumerate(series):
        prev = None
        for dx, y in enumerate(ys):
            if y is None:
                prev = None
                continue
            row = to_row(y)
            if prev is not None and abs(row - prev) < dots_h:
                lo, hi = sorted((prev, row))
                for r in range(lo, hi + 1):
                    setdot(dx, r, idx)
            else:
                setdot(dx, row, idx)
            prev = row
    axis_row = to_row(0) // 4 if y_lo <= 0 <= y_hi else None
    axis_col = int(round((0 - x_min) / (x_max - x_min) * (dots_w - 1))) // 2 if x_min <= 0 <= x_max else None
    lines = []
    label_w = 10
    for r in range(height):
        chars = []
        for cidx in range(width):
            bits = grid[r][cidx]
            if bits:
                chars.append(ui.c(chr(0x2800 + bits), PLOT_COLORS[owner[r][cidx] % len(PLOT_COLORS)]))
            elif r == axis_row and cidx == axis_col:
                chars.append(ui.gray("┼"))
            elif r == axis_row:
                chars.append(ui.gray("─"))
            elif cidx == axis_col:
                chars.append(ui.gray("│"))
            else:
                chars.append(" ")
        label = format_result(round(y_hi, 4)) if r == 0 else format_result(round(y_lo, 4)) if r == height - 1 else ""
        lines.append(ui.gray(label.rjust(label_w)[:label_w]) + " " + "".join(chars))
    left = format_result(round(x_min, 4))
    right = format_result(round(x_max, 4))
    lines.append(" " * (label_w + 1) + ui.gray(left + " " * max(1, width - len(left) - len(right)) + right))
    return lines


def find_roots(f: Callable[[float], float], a: float, b: float, samples: int = 2000) -> list[float]:
    roots: list[float] = []
    xs = [a + i * (b - a) / samples for i in range(samples + 1)]
    prev_x, prev_y = None, None
    for x in xs:
        try:
            y = f(x)
        except (CalcError, ValueError, ZeroDivisionError, OverflowError):
            prev_x = prev_y = None
            continue
        if abs(y) < 1e-14:
            roots.append(x)
        elif prev_y is not None and prev_y * y < 0:
            lo, hi, flo = prev_x, x, prev_y
            for _ in range(200):
                mid = (lo + hi) / 2
                fm = f(mid)
                if (fm < 0) == (flo < 0):
                    lo, flo = mid, fm
                else:
                    hi = mid
            root = (lo + hi) / 2
            if abs(f(root)) < 1e-6 * max(1.0, abs(prev_y)):
                roots.append(root)
        prev_x, prev_y = x, y
    dedup: list[float] = []
    for r in sorted(roots):
        if not dedup or abs(r - dedup[-1]) > 1e-9 * max(1, abs(r)):
            dedup.append(r)
    return dedup


def simpson(f: Callable[[float], float], a: float, b: float, n: int = 10000) -> float:
    if n % 2:
        n += 1
    h = (b - a) / n
    s = f(a) + f(b)
    for i in range(1, n):
        s += (4 if i % 2 else 2) * f(a + i * h)
    return s * h / 3


# --------------------------------------------------------------------------
# Finance
# --------------------------------------------------------------------------

def annuity_payment(principal: float, annual_rate: float, months: int) -> float:
    r = annual_rate / 100 / 12
    if r == 0:
        return principal / months
    return principal * r / (1 - (1 + r) ** -months)


def loan_schedule(principal: float, annual_rate: float, months: int, kind: str = "annuity") -> list[tuple[int, float, float, float]]:
    """Returns yearly rows (year, payments, interest, remaining)."""
    r = annual_rate / 100 / 12
    balance = principal
    pay = annuity_payment(principal, annual_rate, months)
    rows = []
    year_pay = year_int = 0.0
    for m in range(1, months + 1):
        interest = balance * r
        principal_part = (pay - interest) if kind == "annuity" else principal / months
        payment = principal_part + interest
        balance = max(0.0, balance - principal_part)
        year_pay += payment
        year_int += interest
        if m % 12 == 0 or m == months:
            rows.append(((m + 11) // 12, year_pay, year_int, balance))
            year_pay = year_int = 0.0
    return rows


def savings_growth(initial: float, monthly: float, annual_rate: float, years: int) -> list[tuple[int, float, float]]:
    """(year, invested, value) – compounded monthly."""
    r = annual_rate / 100 / 12
    value, invested = initial, initial
    rows = []
    for m in range(1, years * 12 + 1):
        value = value * (1 + r) + monthly
        invested += monthly
        if m % 12 == 0:
            rows.append((m // 12, invested, value))
    return rows


# --------------------------------------------------------------------------
# School grades
# --------------------------------------------------------------------------

def parse_grade(token: str) -> float:
    t = token.strip().replace(",", ".")
    m = re.fullmatch(r"(\d+)\s*(½|\+|-|\.5|\.25|\.75)?", t)
    if not m:
        return float(t)
    base = int(m.group(1))
    mod = m.group(2) or ""
    return base + {"": 0, "½": 0.5, ".5": 0.5, "+": 0.25, "-": -0.25, ".25": 0.25, ".75": 0.75}[mod]


def grade_label(value: float) -> str:
    q = round(value * 4) / 4
    base = math.floor(q + 0.25)
    frac = q - base
    if abs(frac) < 1e-9:
        return str(base)
    if abs(frac - 0.25) < 1e-9:
        return f"{base}+"
    if abs(frac + 0.25) < 1e-9:
        return f"{base}-"
    return f"{math.floor(q)}½"


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@tool("math", "math-calculator", "Calculator", "Functions, variables, ans, degrees/radians, fractions, factorial, percentages",
      ("calculator", "laske", "laskin", "calc"))
def calculator_tool() -> None:
    variables: dict[str, Number] = {}
    history: list[str] = []
    exact = False
    print(ui.gray("E.g.: 2^10, sqrt(2)*3, sin(30), 15% * 200, 5!, x = 3, 2x + 1, log(1000), ln(e), fib(100)"))
    print(ui.gray("Commands: :deg, :rad, :exact (fractions), :vars, :history, :functions, empty = quit"))
    while True:
        mode = ("DEG" if _state["degrees"] else "RAD") + (" EXACT" if exact else "")
        try:
            raw = input(ui.c(f"[{mode}] ", "gray") + ui.c("» ", "bright_green")).strip()
        except EOFError:
            break
        if not raw:
            break
        if raw.startswith(":"):
            cmd = raw[1:].lower()
            if cmd in ("aste", "deg"):
                _state["degrees"] = True
            elif cmd in ("rad", "radiaani"):
                _state["degrees"] = False
            elif cmd in ("tarkka", "murto", "exact"):
                exact = not exact
            elif cmd in ("muuttujat", "vars"):
                ui.print_kv({k: format_result(v) for k, v in variables.items()} or {"(no variables)": ""})
            elif cmd in ("historia", "hist", "history"):
                for h in history[-20:]:
                    print("  " + h)
            elif cmd in ("funktiot", "f", "functions"):
                print(ui.gray(", ".join(sorted(FUNCS))))
                print(ui.gray("Constants: pi, e, tau, phi, inf, i"))
            continue
        m = re.fullmatch(r"([A-Za-z_]\w*)\s*=\s*(?!=)(.+)", raw)
        try:
            if m:
                name = m.group(1)
                if name in FUNCS or name in CONSTS:
                    raise CalcError(f"The name {name} is reserved.")
                value = evaluate(m.group(2), variables, exact)
                variables[name] = value
                print(ui.c(f"  {name} = {format_result(value)}", "bright_cyan"))
            else:
                value = evaluate(raw, variables, exact)
                variables["ans"] = value
                text = format_result(value)
                print(ui.c("  = ", "gray") + ui.c(text, "bold", "bright_white"))
                history.append(f"{raw} = {text}")
        except CalcError as exc:
            ui.error(str(exc))
        except (TypeError, ValueError, OverflowError) as exc:
            ui.error(f"Failed: {exc}")


@tool("math", "math-function-plotter", "Function plotter", "Plots a function in the terminal, e.g. sin(x); x^2/10",
      ("plot", "graafi", "kuvaaja", "funktio"))
def plot_tool() -> None:
    print(ui.gray("Several functions separated by semicolons: sin(x); cos(x). The variable is x."))
    exprs = [e.strip() for e in ui.ask("f(x)", "sin(x)").split(";") if e.strip()]
    x_min = ui.ask_float("x from", -10)
    x_max = ui.ask_float("x to", 10)
    if x_max <= x_min:
        ui.error("The end must be larger.")
        return
    width = max(30, min(120, ui.term_width() - 14))
    try:
        for line in plot(exprs, x_min, x_max, width, 22):
            print(line)
    except CalcError as exc:
        ui.error(str(exc))
        return
    for i, e in enumerate(exprs):
        print("  " + ui.c("■", PLOT_COLORS[i % len(PLOT_COLORS)]) + f" {e}")
    f = make_func(exprs[0])
    roots = find_roots(f, x_min, x_max)
    if roots:
        ui.info("Zeros (" + exprs[0] + "): " + ", ".join(format_result(round(r, 8)) for r in roots[:12]))


@tool("math", "math-equation-solver", "Equation solver", "Quadratic equations, systems of equations and f(x) = 0 numerically",
      ("equation", "quadratic", "system", "ratkaise"))
def equations_tool() -> None:
    kind = ui.choose("Type", ["ax² + bx + c = 0", "System of linear equations", "Any f(x) = 0"])
    if kind == 0:
        a, b, c = ui.ask_float("a", 1), ui.ask_float("b", 0), ui.ask_float("c", -4)
        try:
            roots = solve_quadratic(a, b, c)
        except ValueError as exc:
            ui.error(str(exc))
            return
        if a:
            d = b * b - 4 * a * c
            ui.info(f"Discriminant D = {format_result(d)} → "
                    + ("two real roots" if d > 0 else "a double root" if d == 0 else "complex roots"))
            ui.info(f"Vertex: ({format_result(-b / (2 * a))}, {format_result(c - b * b / (4 * a))})")
        for i, r in enumerate(roots, 1):
            print(ui.bold(f"  x{i} = {format_result(r)}"))
    elif kind == 1:
        n = ui.ask_int("How many unknowns", 2, 1, 10)
        print(ui.gray(f"Enter each equation's coefficients and constant: e.g. '2 1 | 5' means 2x + 1y = 5"))
        aug = []
        for i in range(n):
            raw = ui.ask(f"Equation {i + 1}")
            nums = parse_matrix(raw.replace("|", " "))[0]
            if len(nums) != n + 1:
                ui.error(f"{n + 1} numbers needed.")
                return
            aug.append(nums)
        status, sol = solve_linear(aug)
        if sol is None:
            ui.warn(f"The system has {status}.")
            return
        names = "xyzwuvabcd"
        for name, v in zip(names, sol):
            print(ui.bold(f"  {name} = {format_result(v)}"))
    else:
        expr = ui.ask("f(x)", "x^3 - 2x - 5")
        a, b = ui.ask_float("Search range from", -100), ui.ask_float("to", 100)
        roots = find_roots(make_func(expr), a, b)
        if not roots:
            ui.warn("No zeros found in this range.")
        for r in roots:
            print(ui.bold(f"  x ≈ {format_result(round(r, 12))}"))


@tool("math", "math-primes-and-factors", "Primes and factors", "Is it prime? Factorisation, next prime, list of primes",
      ("prime", "alkuluku", "factors", "faktorointi"))
def primes_tool() -> None:
    mode = ui.choose("Action", ["Check and factorise", "Primes in a range", "Next prime", "n-th prime"])
    if mode == 0:
        n = ui.ask_int("Number", 360, 1)
        t = time.perf_counter()
        f = factorize(n)
        print(ui.bold(f"  {n} = {format_factors(f)}"))
        ui.info(("It's a prime!" if is_prime(n) else "Not a prime.") + ui.gray(f"  ({(time.perf_counter() - t) * 1000:.1f} ms)"))
    elif mode == 1:
        a = ui.ask_int("From", 1, 0)
        b = ui.ask_int("To", 200, a, 50_000_000)
        primes = [p for p in sieve(b) if p >= a]
        ui.info(f"{len(primes)} primes.")
        ui.paginate([" ".join(str(p).rjust(len(str(b))) for p in primes[i:i + 12]) for i in range(0, min(len(primes), 5000), 12)])
    elif mode == 2:
        n = ui.ask_int("Number", 1000)
        print(ui.bold(f"  Next prime: {next_prime(n)}"))
    else:
        k = ui.ask_int("n", 1000, 1, 1_000_000)
        limit = max(30, int(k * (math.log(k) + math.log(math.log(k + 2)) + 2)))
        print(ui.bold(f"  Prime number {k} is {sieve(limit)[k - 1]}"))


@tool("math", "math-number-properties", "Number properties", "Everything about a number: divisors, square, Fibonacci, Roman numerals, words…",
      ("number", "luku", "ominaisuudet", "faktat"))
def number_tool() -> None:
    n = ui.ask_int("Integer", 28)
    ui.print_kv(number_facts(n))


@tool("math", "math-statistics", "Statistics calculator", "Mean, median, standard deviation, quartiles, outliers and histogram",
      ("tilasto", "keskiarvo", "mediaani", "hajonta", "statistics"))
def stats_tool() -> None:
    text = ui.get_text("Numbers (separated by spaces, one per line or @file)")
    try:
        values = parse_numbers(text)
    except ValueError as exc:
        ui.error(str(exc))
        return
    if not values:
        ui.error("No numbers.")
        return
    ui.print_kv([(k, format_result(v) if isinstance(v, (int, float)) else v) for k, v in describe(values)])
    if len(values) > 1:
        print()
        print(ui.gray("Sorted: ") + ui.c(ui.sparkline(values), "bright_cyan"))
        lo, hi = min(values), max(values)
        bins = min(12, max(3, int(math.sqrt(len(values)))))
        width = (hi - lo) / bins or 1
        counts = [0] * bins
        for v in values:
            counts[min(bins - 1, int((v - lo) / width))] += 1
        ui.bar_chart([(f"{format_result(round(lo + i * width, 3))}–", c) for i, c in enumerate(counts)])


@tool("math", "math-percentages", "Percentage calculator", "Percentages, changes, discounts and increases",
      ("prosentti", "alennus", "ale", "muutos", "%"))
def percent_tool() -> None:
    kinds = ["What is X % of Y?", "What percentage of Y is X?", "Percentage change A → B",
             "Add X % to Y", "Subtract X % from Y (discount)", "Original price before a discount",
             "Percent vs. percentage point"]
    k = ui.choose("Calculation", kinds)
    f = lambda v: format_result(round(v, 6))  # noqa: E731
    if k == 0:
        x, y = ui.ask_float("X (%)"), ui.ask_float("Y")
        print(ui.bold(f"  {f(x)} % of {f(y)} is {f(x / 100 * y)}"))
    elif k == 1:
        x, y = ui.ask_float("X"), ui.ask_float("Y")
        if y == 0:
            ui.error("Y can't be zero.")
            return
        print(ui.bold(f"  {f(x)} is {f(x / y * 100)} % of {f(y)}"))
    elif k == 2:
        a, b = ui.ask_float("Start value A"), ui.ask_float("End value B")
        if a == 0:
            ui.error("The start value can't be zero.")
            return
        ch = (b - a) / abs(a) * 100
        print(ui.bold(f"  Change {'+' if ch >= 0 else ''}{f(ch)} % ({'+' if b >= a else ''}{f(b - a)})"))
        if b:
            print(ui.gray(f"  Getting back to the start needs a {f((a - b) / b * 100)} % change."))
    elif k == 3:
        x, y = ui.ask_float("X (%)"), ui.ask_float("Y")
        print(ui.bold(f"  {f(y)} + {f(x)} % = {f(y * (1 + x / 100))}"))
    elif k == 4:
        x, y = ui.ask_float("Discount (%)"), ui.ask_float("Price")
        print(ui.bold(f"  New price {f(y * (1 - x / 100))} (you save {f(y * x / 100)})"))
    elif k == 5:
        price, x = ui.ask_float("Discounted price"), ui.ask_float("Discount (%)")
        if x >= 100:
            ui.error("The discount must be under 100 %.")
            return
        print(ui.bold(f"  The original price was {f(price / (1 - x / 100))}"))
    else:
        a, b = ui.ask_float("Old percentage"), ui.ask_float("New percentage")
        print(f"  The change is {ui.bold(f(b - a) + ' percentage points')}")
        if a:
            print(f"  …but relatively {ui.bold(f((b - a) / a * 100) + ' %')}")


@tool("math", "math-matrices", "Matrix calculator", "Determinant, inverse, product, transpose, rank – with exact fractions",
      ("matriisi", "determinantti", "inverse", "matrix"))
def matrix_tool() -> None:
    print(ui.gray("Enter the matrix row by row separated by semicolons: 1 2; 3 4"))
    ops = ["Determinant", "Inverse matrix", "Transpose", "Product A·B", "Sum A+B", "Rank and row echelon form"]
    op = ui.choose("Action", ops)
    try:
        a = parse_matrix(ui.ask("A", "1 2; 3 4"))
        if op == 0:
            print(ui.bold(f"  det(A) = {format_result(determinant(a))}"))
            return
        if op == 1:
            result = inverse(a)
        elif op == 2:
            result = transpose(a)
        elif op in (3, 4):
            b = parse_matrix(ui.ask("B", "5 6; 7 8"))
            if op == 3:
                result = mat_mul(a, b)
            else:
                if len(a) != len(b) or len(a[0]) != len(b[0]):
                    raise ValueError("The matrices must be the same size.")
                result = [[x + y for x, y in zip(r1, r2)] for r1, r2 in zip(a, b)]
        else:
            result, rank = rref(a)
            ui.info(f"Rank = {rank}")
    except (ValueError, ZeroDivisionError) as exc:
        ui.error(str(exc))
        return
    for line in mat_str(result):
        print("  " + line)


@tool("math", "math-geometry", "Geometry", "Areas, perimeters, volumes and Pythagoras",
      ("pinta-ala", "tilavuus", "circle", "kolmio", "pythagoras"))
def geometry_tool() -> None:
    shapes = ["Circle", "Rectangle", "Triangle (base and height)", "Triangle (three sides)", "Trapezoid",
              "Regular polygon", "Cube", "Cuboid", "Sphere", "Cylinder", "Cone",
              "Square pyramid", "Pythagoras (missing side)"]
    s = ui.choose("Format", shapes)
    fr = lambda v: format_result(round(v, 8))  # noqa: E731
    pi = math.pi
    if s == 0:
        r = ui.ask_float("Radius")
        ui.print_kv([("Area", fr(pi * r * r)), ("Perimeter", fr(2 * pi * r)), ("Diameter", fr(2 * r))])
    elif s == 1:
        a, b = ui.ask_float("Width"), ui.ask_float("Height")
        ui.print_kv([("Area", fr(a * b)), ("Perimeter", fr(2 * (a + b))), ("Diagonal", fr(math.hypot(a, b)))])
    elif s == 2:
        a, h = ui.ask_float("Base"), ui.ask_float("Height")
        ui.print_kv([("Area", fr(a * h / 2))])
    elif s == 3:
        a, b, c = ui.ask_float("a"), ui.ask_float("b"), ui.ask_float("c")
        if a + b <= c or a + c <= b or b + c <= a:
            ui.error("These sides don't make a triangle.")
            return
        p = (a + b + c) / 2
        area = math.sqrt(p * (p - a) * (p - b) * (p - c))
        ang = lambda x, y, z: math.degrees(math.acos((y * y + z * z - x * x) / (2 * y * z)))  # noqa: E731
        ui.print_kv([("Area (Heron)", fr(area)), ("Perimeter", fr(a + b + c)),
                     ("Angles", f"{fr(ang(a, b, c))}°, {fr(ang(b, a, c))}°, {fr(ang(c, a, b))}°")])
    elif s == 4:
        a, b, h = ui.ask_float("Base a"), ui.ask_float("Base b"), ui.ask_float("Height")
        ui.print_kv([("Area", fr((a + b) / 2 * h))])
    elif s == 5:
        n, a = ui.ask_int("Sides", 6, 3), ui.ask_float("Side length")
        ui.print_kv([("Area", fr(n * a * a / (4 * math.tan(pi / n)))), ("Perimeter", fr(n * a)),
                     ("Interior angle", fr((n - 2) * 180 / n) + "°")])
    elif s == 6:
        a = ui.ask_float("Edge")
        ui.print_kv([("Volume", fr(a ** 3)), ("Area", fr(6 * a * a)), ("Space diagonal", fr(a * math.sqrt(3)))])
    elif s == 7:
        a, b, c = ui.ask_float("Length"), ui.ask_float("Width"), ui.ask_float("Height")
        ui.print_kv([("Volume", fr(a * b * c)), ("Area", fr(2 * (a * b + a * c + b * c))),
                     ("Space diagonal", fr(math.sqrt(a * a + b * b + c * c)))])
    elif s == 8:
        r = ui.ask_float("Radius")
        ui.print_kv([("Volume", fr(4 / 3 * pi * r ** 3)), ("Area", fr(4 * pi * r * r))])
    elif s == 9:
        r, h = ui.ask_float("Base radius"), ui.ask_float("Height")
        ui.print_kv([("Volume", fr(pi * r * r * h)), ("Lateral area", fr(2 * pi * r * h)),
                     ("Total surface area", fr(2 * pi * r * (r + h))), ("Volume in litres (cm)", fr(pi * r * r * h / 1000))])
    elif s == 10:
        r, h = ui.ask_float("Base radius"), ui.ask_float("Height")
        sl = math.hypot(r, h)
        ui.print_kv([("Volume", fr(pi * r * r * h / 3)), ("Slant height", fr(sl)), ("Total surface area", fr(pi * r * (r + sl)))])
    elif s == 11:
        a, h = ui.ask_float("Base side"), ui.ask_float("Height")
        slant = math.hypot(a / 2, h)
        ui.print_kv([("Volume", fr(a * a * h / 3)), ("Total surface area", fr(a * a + 2 * a * slant))])
    else:
        print(ui.gray("Leave the unknown side empty (c is the hypotenuse)."))
        vals = {k: ui.ask(k, allow_empty=True) for k in ("a", "b", "c")}
        try:
            known = {k: ui.parse_number(v) for k, v in vals.items() if v}
            if "c" not in known:
                print(ui.bold(f"  c = {fr(math.hypot(known['a'], known['b']))}"))
            else:
                other = known.get("a", known.get("b"))
                missing = "b" if "a" in known else "a"
                print(ui.bold(f"  {missing} = {fr(math.sqrt(known['c'] ** 2 - other ** 2))}"))
        except (KeyError, ValueError, TypeError):
            ui.error("Enter exactly two sides (and the hypotenuse must be the longest).")


@tool("math", "math-combinatorics", "Combinatorics and probability", "Factorial, nCr, nPr, lottery odds and the birthday paradox",
      ("kombinaatio", "permutaatio", "lotto", "probability", "ncr"))
def combinatorics_tool() -> None:
    kinds = ["n! (factorial)", "Combinations nCr", "Permutations nPr", "Lottery odds",
             "Birthday paradox", "Dice sum probabilities"]
    k = ui.choose("Calculation", kinds)
    if k == 0:
        n = ui.ask_int("n", 10, 0, 20000)
        print(ui.bold("  " + format_result(math.factorial(n))))
    elif k in (1, 2):
        n, r = ui.ask_int("n", 40, 0), ui.ask_int("r", 7, 0)
        val = math.comb(n, r) if k == 1 else math.perm(n, r)
        print(ui.bold(f"  {format_result(val)}"))
        if k == 1:
            print(ui.gray(f"  With repetition (multisets): {format_result(math.comb(n + r - 1, r))}"))
    elif k == 3:
        games = [("Lotto (Finland) 7/40", math.comb(40, 7)), ("Eurojackpot 5/50 + 2/12", math.comb(50, 5) * math.comb(12, 2)),
                 ("Viking Lotto 6/48 + 1/5", math.comb(48, 6) * 5), ("Coin lands heads 20 times in a row", 2 ** 20),
                 ("Lightning strike (per year, approx.)", 1_000_000)]
        for name, odds in games:
            print(f"  {name.ljust(28)} 1 : {ui.fi_num(odds, 0)}")
        print(ui.gray("  If you play one line a week, the Lotto jackpot would take on average "
                      f"{ui.fi_num(math.comb(40, 7) / 52, 0)} years."))
    elif k == 4:
        n = ui.ask_int("People in the room", 23, 1, 400)
        p = 1.0
        for i in range(n):
            p *= (365 - i) / 365
        print(ui.bold(f"  Probability that two share a birthday: {(1 - p) * 100:.2f} %"))
    else:
        dice, sides = ui.ask_int("Dice", 2, 1, 20), ui.ask_int("Sides", 6, 2, 100)
        dist = {0: 1}
        for _ in range(dice):
            nxt: dict[int, int] = {}
            for s, c in dist.items():
                for f in range(1, sides + 1):
                    nxt[s + f] = nxt.get(s + f, 0) + c
            dist = nxt
        total = sides ** dice
        ui.bar_chart([(str(s), c / total * 100) for s, c in sorted(dist.items())][:60],
                     value_fmt=lambda v: f"{v:.2f} %")


@tool("math", "math-loan-calculator", "Loan calculator", "Monthly payment, interest and schedule (annuity or straight-line)",
      ("laina", "asuntolaina", "korko", "annuiteetti", "monthly payment"))
def loan_tool() -> None:
    principal = ui.ask_float("Loan amount (€)", 150000, 1)
    rate = ui.ask_float("Annual interest incl. margin (%)", 4.0, 0)
    years = ui.ask_int("Loan term (years)", 25, 1, 60)
    months = years * 12
    pay = annuity_payment(principal, rate, months)
    ann = loan_schedule(principal, rate, months, "annuity")
    eq = loan_schedule(principal, rate, months, "equal")
    total_int_ann = sum(r[2] for r in ann)
    total_int_eq = sum(r[2] for r in eq)
    ui.print_kv([
        ("Monthly payment (annuity)", f"{ui.fi_num(pay)} €"),
        ("Total interest (annuity)", f"{ui.fi_num(total_int_ann)} €"),
        ("Straight-line 1st payment", f"{ui.fi_num(principal / months + principal * rate / 1200)} €"),
        ("Total interest (straight-line)", f"{ui.fi_num(total_int_eq)} €"),
        ("Total repaid (annuity)", f"{ui.fi_num(principal + total_int_ann)} €"),
    ])
    if ui.ask_yes_no("Show the yearly payment schedule?", False):
        ui.table([(y, ui.fi_num(p), ui.fi_num(i), ui.fi_num(b)) for y, p, i, b in ann],
                 ["Year", "Payments €", "Interest €", "Remaining €"], align=[">", ">", ">", ">"])
    print(ui.gray("  This is an estimate and doesn't include bank fees."))


@tool("math", "math-savings-calculator", "Savings and investment calculator", "Compound interest: how monthly savings grow over the years",
      ("savings", "sijoitus", "compound interest", "rahasto"))
def savings_tool() -> None:
    initial = ui.ask_float("Starting capital (€)", 1000, 0)
    monthly = ui.ask_float("Monthly saving (€)", 100, 0)
    rate = ui.ask_float("Expected annual return (%)", 6.0)
    years = ui.ask_int("Years", 20, 1, 80)
    rows = savings_growth(initial, monthly, rate, years)
    step = max(1, len(rows) // 15)
    ui.table([(y, ui.fi_num(inv, 0), ui.fi_num(val, 0), ui.fi_num(val - inv, 0)) for y, inv, val in rows[::step]] +
             ([(rows[-1][0], ui.fi_num(rows[-1][1], 0), ui.fi_num(rows[-1][2], 0), ui.fi_num(rows[-1][2] - rows[-1][1], 0))]
              if (len(rows) - 1) % step else []),
             ["Year", "Invested €", "Value €", "Return €"], align=[">", ">", ">", ">"])
    print(ui.gray("Value over time: ") + ui.c(ui.sparkline([v for _, _, v in rows]), "bright_green"))
    print(ui.gray("  Returns aren't guaranteed, and taxes, fees and inflation aren't included."))


@tool("math", "math-bmi", "Body mass index (BMI)", "Calculates an adult's BMI", ("bmi", "painoindeksi"))
def bmi_tool() -> None:
    w = ui.ask_float("Weight (kg)", min_value=1)
    h = ui.ask_float("Height (cm)", min_value=50) / 100
    bmi = w / (h * h)
    cats = [(18.5, "underweight"), (25, "normal weight"), (30, "overweight"), (35, "obese (class I)"),
            (40, "obese (class II)"), (999, "obese (class III)")]
    label = next(name for lim, name in cats if bmi < lim)
    print(ui.bold(f"  BMI = {bmi:.1f} ({label})"))
    print(ui.gray("  BMI is a rough measure and ignores muscle mass. Under 18s use age-adjusted BMI."))


@tool("math", "math-number-sequences", "Number sequences", "Fibonacci, Collatz, Pascal's triangle, squares, triangular numbers, Catalan numbers",
      ("fibonacci", "collatz", "pascal", "jono"))
def sequences_tool() -> None:
    kinds = ["Fibonacci", "Collatz (3n+1)", "Pascal's triangle", "Square numbers", "Triangular numbers", "Powers of two",
             "Catalan numbers", "Factorials"]
    k = ui.choose("Sequence", kinds)
    if k == 1:
        n = ui.ask_int("Starting number", 27, 1)
        seq = collatz(n)
        print(", ".join(map(str, seq[:300])))
        ui.info(f"{len(seq) - 1} steps, largest value {max(seq)}")
        print(ui.c(ui.sparkline(seq[:200]), "bright_cyan"))
        return
    if k == 2:
        rows = ui.ask_int("Rows", 12, 1, 30)
        row = [1]
        w = len(str(math.comb(rows - 1, (rows - 1) // 2))) + 1
        for i in range(rows):
            print(" " * ((rows - i - 1) * w // 2) + "".join(str(x).center(w) for x in row))
            row = [1] + [row[j] + row[j + 1] for j in range(len(row) - 1)] + [1]
        return
    n = ui.ask_int("How many terms", 20, 1, 1000)
    gens: dict[int, Callable[[int], int]] = {
        0: _fib, 3: lambda i: i * i, 4: lambda i: i * (i + 1) // 2, 5: lambda i: 2 ** i,
        6: lambda i: math.comb(2 * i, i) // (i + 1), 7: math.factorial,
    }
    start = 1 if k in (3, 4) else 0
    seq = [gens[k](i) for i in range(start, start + n)]
    ui.paginate([f"{ui.gray(str(i).rjust(4))}  {v}" for i, v in enumerate(seq, start)])


@tool("math", "math-times-tables", "Times tables and practice", "A colourful times table and a timed multiplication quiz",
      ("kertotaulu", "kertolasku", "harjoitus", "visa"))
def times_table_tool() -> None:
    mode = ui.choose("Action", ["Show the times table", "Practise (10 questions)"])
    if mode == 0:
        n = ui.ask_int("Size", 10, 2, 20)
        w = len(str(n * n)) + 1
        print(" " * w + "".join(ui.c(str(j).rjust(w), "bold", "bright_yellow") for j in range(1, n + 1)))
        for i in range(1, n + 1):
            cells = []
            for j in range(1, n + 1):
                v = str(i * j).rjust(w)
                cells.append(ui.c(v, "bright_cyan") if i == j else v)
            print(ui.c(str(i).rjust(w), "bold", "bright_yellow") + "".join(cells))
        return
    hi = ui.ask_int("Largest factor", 10, 2, 20)
    score, start = 0, time.time()
    for q in range(1, 11):
        a, b = random.randint(2, hi), random.randint(2, hi)
        ans = ui.ask(f"{q}/10: {a} × {b} =")
        if ans.strip() == str(a * b):
            score += 1
            ui.success("Correct!")
        else:
            ui.error(f"Wrong, the right answer is {a * b}.")
    took = time.time() - start
    print(ui.bold(f"\n  {score}/10 correct in {ui.fmt_duration(took)}"))
    from .games import record_score

    record_score("Times table quiz", score * 100 - int(took))


@tool("math", "math-calculus", "Derivative and integral", "Numerical derivative, integral, extrema and area",
      ("derivaatta", "integraali", "extremum", "analyysi"))
def calculus_tool() -> None:
    expr = ui.ask("f(x)", "x^3 - 3x")
    f = make_func(expr)
    mode = ui.choose("Calculate", ["Derivative at a point", "Definite integral", "Extrema in a range"])
    try:
        if mode == 0:
            x0 = ui.ask_float("x", 1)
            h = 1e-5
            d1 = (f(x0 + h) - f(x0 - h)) / (2 * h)
            d2 = (f(x0 + h) - 2 * f(x0) + f(x0 - h)) / (h * h)
            ui.print_kv([("f(x)", format_result(round(f(x0), 10))), ("f'(x)", format_result(round(d1, 8))),
                         ("f''(x)", format_result(round(d2, 4))),
                         ("Tangent", f"y = {format_result(round(d1, 6))}x + {format_result(round(f(x0) - d1 * x0, 6))}")])
        elif mode == 1:
            a, b = ui.ask_float("Lower bound", 0), ui.ask_float("Upper bound", 1)
            val = simpson(f, a, b)
            area = simpson(lambda x: abs(f(x)), a, b)
            ui.print_kv([("∫ f(x) dx", format_result(round(val, 10))), ("Area |f|", format_result(round(area, 10)))])
        else:
            a, b = ui.ask_float("From", -3), ui.ask_float("To", 3)
            h = 1e-6
            crit = find_roots(lambda x: (f(x + h) - f(x - h)) / (2 * h), a, b, 3000)
            pts = [(a, f(a)), (b, f(b))] + [(x, f(x)) for x in crit]
            for x in crit:
                d2 = (f(x + 1e-4) - 2 * f(x) + f(x - 1e-4)) / 1e-8
                kind = "minimum" if d2 > 0 else "maximum" if d2 < 0 else "saddle point?"
                print(f"  x = {format_result(round(x, 8))}: {kind}, f = {format_result(round(f(x), 8))}")
            lo = min(pts, key=lambda p: p[1])
            hi = max(pts, key=lambda p: p[1])
            ui.info(f"Largest value in range: {format_result(round(hi[1], 8))} (x = {format_result(round(hi[0], 6))})")
            ui.info(f"Smallest value in range: {format_result(round(lo[1], 8))} (x = {format_result(round(lo[0], 6))})")
    except (CalcError, ValueError, ZeroDivisionError, OverflowError) as exc:
        ui.error(str(exc))


@tool("math", "math-grade-average", "Grade average", "Finnish school grades (8+, 9-, 7½) and credit-weighted averages",
      ("keskiarvo", "arvosana", "todistus", "koulu", "opintopiste"))
def grades_tool() -> None:
    mode = ui.choose("Scale", ["Finnish school (4–10, e.g. 8+ 9- 7½)", "University 1–5 with credits (5:5 4:10)"])
    raw = ui.ask("Grades separated by spaces")
    try:
        if mode == 0:
            vals = [parse_grade(t) for t in raw.split()]
            avg = sum(vals) / len(vals)
            ui.print_kv([("Grades", len(vals)), ("Average", f"{avg:.2f}"), ("As notation", grade_label(avg)),
                         ("Best / worst", f"{grade_label(max(vals))} / {grade_label(min(vals))}")])
        else:
            pairs = [t.split(":") for t in raw.split()]
            total_w = sum(float(w.replace(",", ".")) for _, w in pairs)
            avg = sum(float(g) * float(w.replace(",", ".")) for g, w in pairs) / total_w
            ui.print_kv([("Credits", ui.fi_num(total_w, 1)), ("Weighted average", f"{avg:.2f}")])
    except (ValueError, ZeroDivisionError, IndexError):
        ui.error("I didn't understand the grades. E.g.: 8 9- 7½ 10 or 5:5 4:10")
