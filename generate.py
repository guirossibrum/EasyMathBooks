#!/usr/bin/env python3
"""EasyMathBooks - Kumon-style math worksheet generator.

Generates printable PDF worksheets (plus matching answer keys) for 40 levels,
from single-digit addition up to square roots and quadratic equations.

    python generate.py --list
    python generate.py --sheet 1-1
    python generate.py --level 5
    python generate.py --level 1-10 --sheets 10
    python generate.py --level all --paper a4
"""

import argparse
import math
import random
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable, Optional

from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

FONT = "Helvetica"
BOLD = "Helvetica-Bold"
M = "–"  # minus / negative sign (en dash is in the standard PDF fonts)


# --------------------------------------------------------------------------
# Problem model
# --------------------------------------------------------------------------

@dataclass
class Problem:
    markup: str                 # problem text, using the mini markup below
    answer: str                 # answer text, same markup
    kind: str = "h"             # h = "... = ____", eq = "... x = ____", stack = vertical
    stack: Optional[tuple] = None

    @property
    def key(self):
        return self.markup


def hz(text, ans):
    return Problem(text, str(ans), "h")


def eq(text, ans):
    return Problem(text, f"x = {ans}", "eq")


def st(a, op, b, ans):
    return Problem(f"{a} {op} {b}", str(ans), "stack", (a, op, b))


# --------------------------------------------------------------------------
# Mini markup renderer (works with built-in PDF fonts, no font files needed)
#   ^{...}       superscript
#   \sqrt{...}   square root        \cbrt{...}   cube root
#   \frac{n}{d}  stacked fraction
# --------------------------------------------------------------------------

def _group(s, i):
    nodes, j = _parse(s, i + 1, True)
    return nodes, j + 1


def _parse(s, i, in_group):
    nodes, buf = [], ""

    def flush():
        nonlocal buf
        if buf:
            nodes.append(("t", buf))
            buf = ""

    while i < len(s):
        ch = s[i]
        if ch == "}" and in_group:
            flush()
            return nodes, i
        if ch == "^" and s[i + 1:i + 2] == "{":
            flush()
            sub, i = _group(s, i + 1)
            nodes.append(("sup", sub))
        elif ch == "\\":
            m = re.match(r"\\([a-z]+)", s[i:])
            name = m.group(1)
            i += m.end()
            flush()
            if name in ("sqrt", "cbrt"):
                sub, i = _group(s, i)
                nodes.append(("rad", "3" if name == "cbrt" else "", sub))
            elif name == "frac":
                n, i = _group(s, i)
                d, i = _group(s, i)
                nodes.append(("frac", n, d))
            else:
                raise ValueError(f"unknown command \\{name}")
        else:
            buf += ch
            i += 1
    flush()
    return nodes, i


_cache = {}


def parse(s):
    if s not in _cache:
        _cache[s] = _parse(s, 0, False)[0]
    return _cache[s]


def _height(nodes, size):
    h = 0.72 * size
    for n in nodes:
        if n[0] == "sup":
            h = max(h, 0.42 * size + _height(n[1], size * 0.62))
        elif n[0] == "rad":
            h = max(h, _height(n[2], size) + 0.2 * size)
        elif n[0] == "frac":
            h = max(h, 0.5 * size + 0.72 * size * 0.86)
    return h


def lay(nodes, size, c=None, x=0.0, y=0.0):
    """Measure (c is None) or draw nodes at baseline (x, y); returns width."""
    w = 0.0
    for n in nodes:
        t = n[0]
        if t == "t":
            if c:
                c.setFont(FONT, size)
                c.drawString(x + w, y, n[1])
            w += stringWidth(n[1], FONT, size)
        elif t == "sup":
            ww = lay(n[1], size * 0.62, c, x + w, y + size * 0.42)
            w += ww + size * 0.03
        elif t == "rad":
            inner = lay(n[2], size)
            left = size * 0.55 if n[1] else size * 0.5
            pad = size * 0.14
            if c:
                X = x + w
                top = y + max(0.92 * size, _height(n[2], size) + 0.12 * size)
                c.setLineWidth(size * 0.065)
                c.setLineCap(0)
                p = c.beginPath()
                p.moveTo(X + left - 0.48 * size, y + 0.30 * size)
                p.lineTo(X + left - 0.40 * size, y + 0.36 * size)
                p.lineTo(X + left - 0.28 * size, y - 0.12 * size)
                p.lineTo(X + left - 0.10 * size, top)
                p.lineTo(X + left + inner + pad * 0.8, top)
                c.drawPath(p, stroke=1, fill=0)
                if n[1]:
                    c.setFont(FONT, size * 0.45)
                    c.drawString(X + 0.02 * size, y + 0.52 * size, n[1])
                lay(n[2], size, c, X + left, y)
            w += left + inner + pad
        elif t == "frac":
            fs = size * 0.86
            wn, wd = lay(n[1], fs), lay(n[2], fs)
            fw = max(wn, wd) + size * 0.3
            if c:
                X = x + w
                lay(n[1], fs, c, X + (fw - wn) / 2, y + 0.50 * size)
                lay(n[2], fs, c, X + (fw - wd) / 2, y - 0.55 * size)
                c.setLineWidth(size * 0.06)
                c.line(X + size * 0.05, y + 0.30 * size, X + fw - size * 0.05, y + 0.30 * size)
            w += fw + size * 0.05
    return w


def text_width(s, size):
    return lay(parse(s), size)


def draw_text(c, s, x, y, size):
    return lay(parse(s), size, c, x, y)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def neg(n):
    return f"{M}{-n}" if n < 0 else str(n)


def paren(n):
    return f"({neg(n)})" if n < 0 else str(n)


def sg(n):
    """Signed term for use after another term: '+ 5' or '– 5'."""
    return f"+ {n}" if n > 0 else f"{M} {-n}"


def co(k):
    return "" if k == 1 else str(k)


def rfrac(n, d):
    return f"\\frac{{{n}}}{{{d}}}"


def fr(f: Fraction):
    n, d = f.numerator, f.denominator
    if d == 1:
        return neg(n)
    if n > d:
        w, r = divmod(n, d)
        return f"{w} {rfrac(r, d)}" if r else str(w)
    return rfrac(n, d)


def has_carry(a, b):
    carry = 0
    while a or b or carry:
        s = a % 10 + b % 10 + carry
        if s >= 10:
            return True
        carry = 0
        a //= 10
        b //= 10
    return False


def has_borrow(a, b):
    borrow = 0
    while a or b:
        if a % 10 - borrow < b % 10:
            return True
        borrow = 0
        a //= 10
        b //= 10
    return False


def dec(i, dp):
    """Format scaled integer i with dp decimal places."""
    if dp == 0:
        return str(i)
    return f"{i // 10 ** dp}.{i % 10 ** dp:0{dp}d}"


def dec_strip(i, dp):
    s = dec(i, dp)
    return s.rstrip("0").rstrip(".") if "." in s else s


def square_split(k):
    """k = s*s*m with m square-free (s as large as possible)."""
    s = 1
    for t in range(2, int(math.isqrt(k)) + 1):
        if k % (t * t) == 0:
            s = t
    return s, k // (s * s)


def rad_ans(k, m):
    return str(k) if m == 1 else f"{co(k)}\\sqrt{{{m}}}"


def pm_root(k):
    s, m = square_split(k)
    return f"±{rad_ans(s, m)}"


def pick_nonzero(rng, lo, hi):
    while True:
        v = rng.randint(lo, hi)
        if v:
            return v


# --------------------------------------------------------------------------
# Generators
# --------------------------------------------------------------------------

def add_gen(ra, rb, carry=None, max_sum=None, min_sum=None, stack=False):
    def gen(rng):
        while True:
            a, b = rng.randint(*ra), rng.randint(*rb)
            if carry is not None and has_carry(a, b) != carry:
                continue
            if max_sum is not None and a + b > max_sum:
                continue
            if min_sum is not None and a + b < min_sum:
                continue
            return st(a, "+", b, a + b) if stack else hz(f"{a} + {b}", a + b)
    return gen


def sub_gen(ra, rb, borrow=None, min_diff=0, stack=False):
    def gen(rng):
        while True:
            a, b = rng.randint(*ra), rng.randint(*rb)
            if a - b < min_diff:
                continue
            if borrow is not None and has_borrow(a, b) != borrow:
                continue
            return st(a, M, b, a - b) if stack else hz(f"{a} {M} {b}", a - b)
    return gen


def mul_gen(ra, rb, stack=False):
    def gen(rng):
        a, b = rng.randint(*ra), rng.randint(*rb)
        if rng.random() < 0.5 and not stack:
            a, b = b, a
        return st(a, "×", b, a * b) if stack else hz(f"{a} × {b}", a * b)
    return gen


def div_gen(rd, rq):
    def gen(rng):
        d, q = rng.randint(*rd), rng.randint(*rq)
        return hz(f"{d * q} ÷ {d}", q)
    return gen


def div_rem_gen(rng):
    d = rng.randint(2, 9)
    while True:
        n = rng.randint(20, 999)
        if n % d:
            return hz(f"{n} ÷ {d}", f"{n // d} R {n % d}")


def mixed_add_sub_4digit(rng):
    if rng.random() < 0.5:
        return add_gen((1000, 9999), (1000, 9999), stack=True)(rng)
    return sub_gen((2000, 9999), (1000, 9999), min_diff=1, stack=True)(rng)


def frac_same_den(rng):
    d = rng.randint(3, 12)
    n1, n2 = rng.randint(1, d - 1), rng.randint(1, d - 1)
    if rng.random() < 0.5:
        return hz(f"{rfrac(n1, d)} + {rfrac(n2, d)}", fr(Fraction(n1 + n2, d)))
    if n1 == n2:
        return frac_same_den(rng)
    n1, n2 = max(n1, n2), min(n1, n2)
    return hz(f"{rfrac(n1, d)} {M} {rfrac(n2, d)}", fr(Fraction(n1 - n2, d)))


def frac_diff_den(rng):
    d1, d2 = rng.sample(range(2, 13), 2)
    a_n, b_n = rng.randint(1, d1 - 1), rng.randint(1, d2 - 1)
    fa, fb = Fraction(a_n, d1), Fraction(b_n, d2)
    if rng.random() < 0.5:
        return hz(f"{rfrac(a_n, d1)} + {rfrac(b_n, d2)}", fr(fa + fb))
    if fa == fb:
        return frac_diff_den(rng)
    if fa < fb:
        a_n, d1, b_n, d2 = b_n, d2, a_n, d1
        fa, fb = fb, fa
    return hz(f"{rfrac(a_n, d1)} {M} {rfrac(b_n, d2)}", fr(fa - fb))


def frac_mul_div(rng):
    d1, d2 = rng.randint(2, 9), rng.randint(2, 9)
    n1, n2 = rng.randint(1, d1 - 1), rng.randint(1, d2 - 1)
    f1, f2 = Fraction(n1, d1), Fraction(n2, d2)
    if rng.random() < 0.5:
        return hz(f"{rfrac(n1, d1)} × {rfrac(n2, d2)}", fr(f1 * f2))
    return hz(f"{rfrac(n1, d1)} ÷ {rfrac(n2, d2)}", fr(f1 / f2))


def dec_add_sub(rng):
    dp = rng.choice([1, 1, 2])
    hi = 10 ** dp * rng.choice([10, 100])
    a, b = rng.randint(10 ** (dp - 1) * 2, hi), rng.randint(10 ** (dp - 1) * 2, hi)
    if rng.random() < 0.5:
        return hz(f"{dec(a, dp)} + {dec(b, dp)}", dec(a + b, dp))
    if a == b:
        return dec_add_sub(rng)
    a, b = max(a, b), min(a, b)
    return hz(f"{dec(a, dp)} {M} {dec(b, dp)}", dec(a - b, dp))


def dec_mul_div(rng):
    if rng.random() < 0.5:
        a = rng.randint(2, 99)                       # tenths
        if rng.random() < 0.5:
            b = rng.randint(2, 9)
            return hz(f"{dec(a, 1)} × {b}", dec_strip(a * b, 1))
        b = rng.randint(2, 9)                        # tenths
        return hz(f"{dec(a, 1)} × {dec(b, 1)}", dec_strip(a * b, 2))
    q = rng.randint(2, 99)                           # quotient, tenths
    if rng.random() < 0.5:
        d = rng.randint(2, 9)
        return hz(f"{dec(q * d, 1)} ÷ {d}", dec_strip(q, 1))
    d = rng.randint(2, 9)                            # tenths
    return hz(f"{dec(q * d, 2)} ÷ {dec(d, 1)}", dec_strip(q, 1))


def percent_gen(rng):
    p = rng.choice([5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 80, 90])
    base = 20 * rng.randint(1, 25)
    return hz(f"{p}% of {base}", p * base // 100)


def neg_add_sub(rng):
    while True:
        a, b = pick_nonzero(rng, -20, 20), pick_nonzero(rng, -20, 20)
        if a > 0 and b > 0:
            continue
        if rng.random() < 0.5:
            return hz(f"{neg(a)} + {paren(b)}", neg(a + b))
        return hz(f"{neg(a)} {M} {paren(b)}", neg(a - b))


def neg_mul_div(rng):
    while True:
        a, b = pick_nonzero(rng, -12, 12), pick_nonzero(rng, -12, 12)
        if abs(a) < 2 or abs(b) < 2 or (a > 0 and b > 0):
            continue
        if rng.random() < 0.5:
            return hz(f"{paren(a)} × {paren(b)}", neg(a * b))
        return hz(f"{paren(a * b)} ÷ {paren(b)}", neg(a))


def order_of_ops(rng):
    while True:
        a, b, c, d = (rng.randint(2, 12) for _ in range(4))
        t = rng.randrange(7)
        if t == 0:
            s = f"{a} + {b} × {c}"
        elif t == 1:
            s = f"({a} + {b}) × {c}"
        elif t == 2:
            s = f"{a} × {b} {M} {c}"
        elif t == 3:
            s = f"{a} + {b} × {c} {M} {d}"
        elif t == 4:
            if a <= b:
                continue
            s = f"({a} {M} {b}) × ({c} + {d})"
        elif t == 5:
            b, c = rng.randint(2, 9), rng.randint(2, 9)
            s = f"{b * c} ÷ {b} + {a}"
        else:
            s = f"{a} × ({b} + {c}) {M} {d}"
        v = eval(s.replace("×", "*").replace("÷", "//").replace(M, "-"))
        if v >= 0:
            return hz(s, v)


def powers_basic(rng):
    t = rng.randrange(5)
    if t == 0:
        b, e = rng.randint(2, 15), 2
    elif t == 1:
        b, e = rng.randint(2, 10), 3
    elif t == 2:
        b, e = 2, rng.randint(4, 10)
    elif t == 3:
        b, e = 3, rng.randint(4, 5)
    else:
        b, e = 10, rng.randint(2, 6)
    return hz(f"{b}^{{{e}}}", b ** e)


def powers_rules(rng):
    t = rng.randrange(6)
    a = rng.randint(2, 5)
    if t == 0:
        m, n = rng.randint(1, 3), rng.randint(1, 3)
        return hz(f"{a}^{{{m}}} × {a}^{{{n}}}", a ** (m + n))
    if t == 1:
        m = rng.randint(3, 6)
        n = rng.randint(1, m - 1)
        return hz(f"{a}^{{{m}}} ÷ {a}^{{{n}}}", a ** (m - n))
    if t == 2:
        a, m, n = rng.randint(2, 3), rng.randint(2, 3), rng.randint(2, 3)
        return hz(f"({a}^{{{m}}})^{{{n}}}", a ** (m * n))
    if t == 3:
        a = rng.randint(2, 50)
        return hz(f"{a}^{{0}}", 1)
    if t == 4:
        n = rng.randint(1, 3)
        return hz(f"{a}^{{{M}{n}}}", rfrac(1, a ** n))
    n = rng.randint(2, 4)
    return hz(f"({M}{a})^{{{n}}}", neg((-a) ** n))


def roots_perfect(rng):
    r = rng.random()
    if r < 0.65:
        k = rng.randint(2, 20)
        return hz(f"\\sqrt{{{k * k}}}", k)
    if r < 0.85:
        k = rng.randint(2, 10)
        return hz(f"\\cbrt{{{k ** 3}}}", k)
    while True:
        a, b = rng.randint(1, 11), rng.randint(2, 12)
        if a < b and math.gcd(a, b) == 1:
            return hz(f"\\sqrt{{{rfrac(a * a, b * b)}}}", rfrac(a, b))


def roots_simplify(rng):
    k, m = rng.randint(2, 9), rng.choice([2, 3, 5, 6, 7, 10, 11])
    return hz(f"\\sqrt{{{k * k * m}}}", rad_ans(k, m))


def roots_arith(rng):
    t = rng.randrange(4)
    m = rng.choice([2, 3, 5, 6, 7])
    if t == 0:
        a, b = rng.randint(1, 9), rng.randint(1, 9)
        r = f"{co(a)}\\sqrt{{{m}}}"
        s = f"{co(b)}\\sqrt{{{m}}}"
        if rng.random() < 0.5:
            return hz(f"{r} + {s}", rad_ans(a + b, m))
        if a == b:
            return roots_arith(rng)
        a, b = max(a, b), min(a, b)
        return hz(f"{co(a)}\\sqrt{{{m}}} {M} {co(b)}\\sqrt{{{m}}}", rad_ans(a - b, m))
    if t == 1:
        k, j = rng.randint(1, 5), rng.randint(1, 5)
        if rng.random() < 0.5:
            return hz(f"\\sqrt{{{k * k * m}}} + \\sqrt{{{j * j * m}}}", rad_ans(k + j, m))
        if k == j:
            return roots_arith(rng)
        k, j = max(k, j), min(k, j)
        return hz(f"\\sqrt{{{k * k * m}}} {M} \\sqrt{{{j * j * m}}}", rad_ans(k - j, m))
    if t == 2:
        p, q = rng.randint(1, 5), rng.randint(1, 5)
        return hz(f"\\sqrt{{{m * p * p}}} × \\sqrt{{{m * q * q}}}", m * p * q)
    b, q = rng.choice([2, 3, 5, 6, 7, 8, 10]), rng.randint(2, 9)
    return hz(f"\\sqrt{{{b * q * q}}} ÷ \\sqrt{{{b}}}", q)


def eq_one_step(rng):
    x = pick_nonzero(rng, -10, 20)
    t = rng.randrange(4)
    if t == 0:
        b = rng.randint(1, 20)
        return eq(f"x + {b} = {neg(x + b)}", neg(x))
    if t == 1:
        b = rng.randint(1, 20)
        return eq(f"x {M} {b} = {neg(x - b)}", neg(x))
    a = rng.randint(2, 12)
    if t == 2:
        return eq(f"{a}x = {neg(a * x)}", neg(x))
    return eq(f"x ÷ {a} = {neg(x)}", neg(a * x))


def eq_two_step(rng):
    t = rng.randrange(4)
    a = rng.randint(2, 9)
    x = pick_nonzero(rng, -10, 12)
    if t == 0:
        b = pick_nonzero(rng, -15, 15)
        return eq(f"{a}x {sg(b)} = {neg(a * x + b)}", neg(x))
    if t == 1:
        b = pick_nonzero(rng, -12, 12)
        return eq(f"\\frac{{x}}{{{a}}} {sg(b)} = {neg(x + b)}", neg(a * x))
    if t == 2:
        b = pick_nonzero(rng, -9, 9)
        return eq(f"{a}(x {sg(b)}) = {neg(a * (x + b))}", neg(x))
    b = rng.randint(1, 30)
    return eq(f"{b} {M} {a}x = {neg(b - a * x)}", neg(x))


def eq_both_sides(rng):
    x = pick_nonzero(rng, -10, 12)
    if rng.random() < 0.6:
        while True:
            a = rng.randint(2, 9)
            c = rng.randint(1, a - 1)
            b = pick_nonzero(rng, -15, 15)
            d = (a - c) * x + b
            if d:
                return eq(f"{co(a)}x {sg(b)} = {co(c)}x {sg(d)}", neg(x))
    a, d = rng.randint(1, 8), rng.randint(1, 8)
    b = rng.randint(1, 15)
    c = (a + d) * x - b
    return eq(f"{co(a)}x {M} {b} = {neg(c)} {M} {co(d)}x", neg(x))


def eq_square(rng):
    t = rng.randrange(5)
    if t == 0:
        s, m = rng.randint(2, 15), 1
    elif t == 1:
        s, m = rng.randint(2, 6), rng.choice([2, 3, 5, 6, 7])
    else:
        s, m = rng.randint(2, 12), rng.choice([1, 1, 2, 3, 5])
    k = s * s * m
    if t in (0, 1):
        return eq(f"x^{{2}} = {k}", pm_root(k))
    if t == 2:
        a = rng.randint(1, 30)
        return eq(f"x^{{2}} {M} {a} = {k}", pm_root(k + a))
    if t == 3:
        c = rng.randint(2, 5)
        return eq(f"{c}x^{{2}} = {c * k}", pm_root(k))
    a = rng.randint(1, 30)
    return eq(f"x^{{2}} + {a} = {k + a}", pm_root(k))


def eq_factoring(rng):
    r1, r2 = pick_nonzero(rng, -9, 9), pick_nonzero(rng, -9, 9)
    b, c = -(r1 + r2), r1 * r2
    s = "x^{2}"
    if b:
        s += f" {'+' if b > 0 else M} {co(abs(b))}x"
    s += f" {sg(c)} = 0"
    roots = sorted({r1, r2})
    return eq(s, ", ".join(neg(r) for r in roots))


# --------------------------------------------------------------------------
# Levels
# --------------------------------------------------------------------------

@dataclass
class Level:
    num: int
    title: str
    gen: Callable
    cols: int = 3
    row_h: float = 40
    size: float = 15


LEVELS = [
    Level(1, "Addition: single digits (sums to 9)", add_gen((1, 8), (1, 8), max_sum=9, stack=True), 5, 86, 18),
    Level(2, "Addition: single digits (sums to 18)", add_gen((2, 9), (2, 9), min_sum=10, stack=True), 5, 86, 18),
    Level(3, "Subtraction: single digits", sub_gen((2, 9), (1, 8), stack=True), 5, 86, 18),
    Level(4, "Subtraction: teens minus single digits", sub_gen((11, 18), (2, 9), stack=True), 5, 86, 18),
    Level(5, "Addition: 2-digit + 1-digit (no carrying)", add_gen((10, 98), (1, 8), carry=False, stack=True), 5, 86, 18),
    Level(6, "Addition: 2-digit + 1-digit (carrying)", add_gen((10, 99), (2, 9), carry=True, stack=True), 5, 86, 18),
    Level(7, "Subtraction: 2-digit - 1-digit", sub_gen((10, 99), (1, 9), stack=True), 5, 86, 18),
    Level(8, "Addition: 2-digit + 2-digit (no carrying)", add_gen((10, 89), (10, 89), carry=False, stack=True), 4, 95, 20),
    Level(9, "Addition: 2-digit + 2-digit (carrying)", add_gen((10, 99), (10, 99), carry=True, stack=True), 4, 95, 20),
    Level(10, "Subtraction: 2-digit - 2-digit", sub_gen((20, 99), (10, 98), min_diff=1, stack=True), 4, 95, 20),
    Level(11, "Addition: 3-digit + 3-digit", add_gen((100, 899), (100, 899), stack=True), 4, 95, 20),
    Level(12, "Subtraction: 3-digit - 3-digit", sub_gen((200, 999), (100, 998), min_diff=1, stack=True), 4, 95, 20),
    Level(13, "Addition and subtraction: 4-digit", mixed_add_sub_4digit, 4, 95, 20),
    Level(14, "Multiplication: tables of 2 to 5", mul_gen((2, 5), (2, 9), stack=True), 5, 86, 18),
    Level(15, "Multiplication: tables up to 12", mul_gen((2, 12), (2, 12), stack=True), 5, 86, 18),
    Level(16, "Multiplication: 2-digit x 1-digit", mul_gen((11, 99), (2, 9), stack=True), 4, 95, 20),
    Level(17, "Multiplication: 2-digit x 2-digit", mul_gen((11, 99), (11, 99), stack=True), 4, 130, 20),
    Level(18, "Multiplication: 3-digit x 2-digit", mul_gen((101, 999), (11, 99), stack=True), 4, 140, 20),
    Level(19, "Division: basic facts", div_gen((2, 9), (2, 9))),
    Level(20, "Division: larger numbers, no remainder", div_gen((2, 9), (11, 99))),
    Level(21, "Division: with remainders", div_rem_gen),
    Level(22, "Fractions: same denominator", frac_same_den, 3, 46),
    Level(23, "Fractions: different denominators", frac_diff_den, 3, 46),
    Level(24, "Fractions: multiply and divide", frac_mul_div, 3, 46),
    Level(25, "Decimals: add and subtract", dec_add_sub, 2),
    Level(26, "Decimals: multiply and divide", dec_mul_div),
    Level(27, "Percentages", percent_gen),
    Level(28, "Negative numbers: add and subtract", neg_add_sub),
    Level(29, "Negative numbers: multiply and divide", neg_mul_div),
    Level(30, "Order of operations", order_of_ops, 2, 40),
    Level(31, "Exponents: squares, cubes, powers", powers_basic),
    Level(32, "Exponents: rules and negative powers", powers_rules, 3, 46),
    Level(33, "Square roots and cube roots", roots_perfect, 3, 46),
    Level(34, "Simplifying square roots", roots_simplify, 3, 46),
    Level(35, "Square-root arithmetic", roots_arith, 2, 46),
    Level(36, "Algebra: one-step equations", eq_one_step, 2, 40),
    Level(37, "Algebra: two-step equations", eq_two_step, 2, 46),
    Level(38, "Algebra: variables on both sides", eq_both_sides, 2, 40),
    Level(39, "Equations with squares (x squared)", eq_square, 2, 46),
    Level(40, "Quadratic equations: factoring", eq_factoring, 2, 40),
]

LEVEL_BY_NUM = {lv.num: lv for lv in LEVELS}


def sheet_code(level_num, variant):
    return f"{int(level_num)}-{int(variant)}"


def parse_sheet_code(code):
    text = str(code).strip()
    parts = text.split("-")
    if len(parts) != 2:
        raise ValueError(f"Sheet code must look like 1-1, got {code!r}")
    try:
        level_num, variant = int(parts[0]), int(parts[1])
    except ValueError as e:
        raise ValueError(f"Sheet code must look like 1-1, got {code!r}") from e
    if variant < 1:
        raise ValueError("Sheet variant must be 1 or greater")
    if level_num not in LEVEL_BY_NUM:
        raise ValueError(f"Unknown level {level_num}. Valid levels are 1-{len(LEVELS)}.")
    return level_num, variant


def rng_for_sheet(level_num, variant):
    """Stable RNG for a sheet code such as 1-1. Independent of other sheets."""
    return random.Random(f"EasyMathBooks:{int(level_num)}-{int(variant)}")


@dataclass
class GeneratedSheet:
    code: str
    level: int
    variant: int
    problem_count: int
    pdf_path: Path
    answers_path: Optional[Path]


# --------------------------------------------------------------------------
# PDF drawing
# --------------------------------------------------------------------------

MARGIN = 40
GREY = (0.45, 0.45, 0.45)
HEADER_H = 160
FOOTER_H = 28


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def grid_rows(page_h, row_h):
    return int((page_h - HEADER_H - FOOTER_H) // row_h)


def blank(c, x0, x1, y):
    c.setLineWidth(0.8)
    c.setStrokeGray(0.25)
    c.line(x0, y - 2, x1, y - 2)
    c.setStrokeGray(0)


def draw_header(c, W, H_, level, code, count, student_name=None, motif=None):
    c.setFillColorRGB(*GREY)
    c.setFont(FONT, 9)
    c.drawString(MARGIN, H_ - 30, "EasyMathBooks")
    c.drawRightString(W - MARGIN - (50 if motif else 0), H_ - 30, f"Sheet {code}")
    c.setFillGray(0)
    c.setFont(BOLD, 15)
    c.drawString(MARGIN, H_ - 50, f"Level {level.num}")
    c.setFont(FONT, 12)
    title = level.title.replace(" x ", " × ").replace(" - ", f" {M} ")
    if motif:
        while stringWidth(title, FONT, 12) > W-2*MARGIN-130 and len(title) > 4:
            title = title[:-4] + "..."
    c.drawString(MARGIN + 74, H_ - 50, title)

    c.setFont(BOLD, 11)
    y = H_ - 80
    c.drawString(MARGIN, y, "Name:")
    if student_name:
        c.setFont(FONT, 12)
        c.drawString(MARGIN + 40, y, student_name)
        c.setFont(BOLD, 11)
    else:
        blank(c, MARGIN + 38, W - MARGIN - 150, y)
    c.drawString(W - MARGIN - 135, y, "Date:")
    blank(c, W - MARGIN - 100, W - MARGIN, y)

    y = H_ - 108
    c.drawString(MARGIN, y, "Time:")
    blank(c, MARGIN + 36, MARGIN + 96, y)
    c.setFont(FONT, 10)
    c.drawString(MARGIN + 100, y, "min")
    blank(c, MARGIN + 124, MARGIN + 184, y)
    c.drawString(MARGIN + 188, y, "sec")
    c.setFont(BOLD, 11)
    c.drawString(W - MARGIN - 135, y, "Score:")
    blank(c, W - MARGIN - 90, W - MARGIN - 52, y)
    c.setFont(FONT, 11)
    c.drawString(W - MARGIN - 46, y, f"/ {count}")

    c.setLineWidth(1.2)
    c.line(MARGIN, H_ - 122, W - MARGIN, H_ - 122)


LABEL_OFF = 28


def instruction(level):
    n = level.num
    if n in (1, 2, 5, 6, 8, 9, 11):
        return "Add."
    if n in (3, 4, 7, 10, 12):
        return "Subtract."
    if n == 13:
        return "Add or subtract."
    if 14 <= n <= 18:
        return "Multiply."
    if 19 <= n <= 21:
        return "Divide."
    if n == 27:
        return "Find the percentage."
    if n == 30:
        return "Follow the order of operations."
    if 31 <= n <= 32:
        return "Calculate the powers."
    if n == 33:
        return "Find the roots."
    if n == 34:
        return "Simplify the square roots."
    if n == 35:
        return "Calculate."
    if n >= 36:
        return "Solve for x."
    return "Calculate."


def draw_diamond(c, cx, cy, r):
    p = c.beginPath()
    p.moveTo(cx - r, cy)
    p.lineTo(cx, cy + r)
    p.lineTo(cx + r, cy)
    p.lineTo(cx, cy - r)
    p.close()
    c.setFillGray(0)
    c.drawPath(p, stroke=0, fill=1)


def draw_label(c, num, x, y):
    c.setFillGray(0)
    c.setFont(FONT, 10.5)
    c.drawString(x, y, f"({num})")


def draw_stack(c, p, x, y_top, level, label_off=LABEL_OFF, hint=None, solved=False, boxes_bottom=False):
    """Vertical problem with one box per answer digit (or the solved answer)."""
    size = level.size
    cw = size * 0.95
    a, op, b = p.stack
    n = max(len(str(a)), len(str(b)))
    R = x + label_off + 18 + n * cw
    ya = y_top - 24
    yb = ya - size * 1.15
    yl = yb - 6
    c.setFillGray(0)
    c.setFont(FONT, size)
    for val, y in ((a, ya), (b, yb)):
        for j, ch in enumerate(reversed(str(val))):
            c.drawCentredString(R - (j + 0.5) * cw, y, ch)
    c.drawString(R - n * cw - 14, yb, op)
    c.setLineWidth(1)
    c.line(R - n * cw - 18, yl, R + 2, yl)
    ans = p.answer
    if solved:
        for k, ch in enumerate(ans):
            c.drawCentredString(R - (len(ans) - k - 0.5) * cw, yl - size - 2, ch)
        return
    bh = size * 1.25
    top = (y_top - level.row_h + bh + 10) if boxes_bottom else (yl - 7)
    for k, ch in enumerate(ans):
        cx = R - (len(ans) - k - 0.5) * cw
        c.setFillGray(0.96)
        c.setStrokeGray(0.6)
        c.setLineWidth(0.8)
        c.rect(cx - cw / 2 + 1, top - bh, cw - 2, bh, stroke=1, fill=1)
        c.setStrokeGray(0)
        if hint is not None and k in hint:
            c.setFillGray(0.5)
            c.setFont(FONT, size)
            c.drawCentredString(cx, top - bh + size * 0.28, ch)
    c.setFillGray(0)


def draw_problem(c, p, num, x, y_top, col_w, level, hint=None):
    size = level.size
    if p.kind == "stack":
        draw_label(c, num, x, y_top - 24)
        draw_stack(c, p, x, y_top, level, hint=hint, boxes_bottom=level.row_h > 100)
        return
    base = y_top - level.row_h * 0.62
    draw_label(c, num, x, base)
    left = x + LABEL_OFF
    w = draw_text(c, p.markup, left, base, size)
    c.setFont(FONT, size)
    if p.kind == "eq":
        gx = left + w + 16
        c.drawString(gx, base, "x =")
        start = gx + stringWidth("x =", FONT, size) + 6
    else:
        c.drawString(left + w + 5, base, "=")
        start = left + w + 5 + stringWidth("=", FONT, size) + 6
    blank(c, start, x + col_w - 14, base)


NOTE_NAMES = {"+": "Addition", M: "Subtraction", "×": "Multiplication"}


def draw_note(c, W, top, level, example):
    x = MARGIN
    c.setLineWidth(0.8)
    c.rect(x, top - 20, 38, 16, stroke=1, fill=0)
    c.setFont(FONT, 9)
    c.drawString(x + 6, top - 15, "Note")
    c.setFont(FONT, 11)
    c.drawString(x + 62, top - 16, f"({NOTE_NAMES[example.stack[1]]})")
    draw_stack(c, example, x + 40, top - 16, level, label_off=0, solved=True)


def note_h(level):
    return round(level.size * 5)


CONT_TOP = 44      # top margin on continuation pages (no header)


def page_capacity(level, page_h, first, note):
    avail = page_h - (HEADER_H if first else CONT_TOP) - FOOTER_H
    if first and note:
        avail -= note_h(level)
    return int(avail // level.row_h) * level.cols


def draw_footer(c, W, level, code, page, pages):
    c.setFillColorRGB(*GREY)
    c.setFont(FONT, 8.5)
    if pages > 1:
        text = f"EasyMathBooks · Level {level.num} · Sheet {code} · Page {page} of {pages}"
    else:
        text = f"EasyMathBooks · Level {level.num} · Sheet {code}"
    c.drawCentredString(W / 2, 14, text)
    c.setFillGray(0)


def draw_sheet(c, W, H_, level, code, pages, example=None, hints=False, student_name=None, motif=None):
    total = sum(len(p) for p in pages)
    col_w = (W - 2 * MARGIN) / level.cols
    start = 0
    for pi, problems in enumerate(pages):
        if motif:
            from worksheet_style import draw_stationery
            draw_stationery(c, W, H_, motif)
        if pi == 0:
            draw_header(c, W, H_, level, code, total, student_name, motif)
            draw_diamond(c, MARGIN + 5, H_ - 138, 4.5)
            c.setFont(FONT, 12)
            c.drawString(MARGIN + 16, H_ - 142, instruction(level))
            top = H_ - HEADER_H + 4
            if example is not None:
                draw_note(c, W, top, level, example)
                top -= note_h(level)
        else:
            top = H_ - CONT_TOP + 8
        for i, p in enumerate(problems):
            r, k = divmod(i, level.cols)   # numbered left to right
            hint = None
            if hints and pi == 0 and p.kind == "stack" and i < 3 and len(p.answer) > 1:
                n = len(p.answer)
                hint = [set(range(n)), set(range(n - 1)), {n - 1}][i]
            draw_problem(c, p, start + i + 1, MARGIN + k * col_w, top - r * level.row_h, col_w, level, hint)
        draw_footer(c, W, level, code, pi + 1, len(pages))
        start += len(problems)
        c.showPage()


def draw_answers(c, W, H_, level, code, problems):
    cols = 3 if level.cols < 4 else 4
    col_w = (W - 2 * MARGIN) / cols
    tall = any("\\frac" in p.markup or "\\frac" in p.answer for p in problems)
    row_h = 40 if tall else 28
    rows_pp = int((H_ - 92 - 40) // row_h) + 1
    chunks = [problems[i:i + rows_pp * cols] for i in range(0, len(problems), rows_pp * cols)]
    size = 11 if cols == 4 else 12
    start = 0
    for chunk in chunks:
        c.setFillColorRGB(*GREY)
        c.setFont(FONT, 9)
        c.drawString(MARGIN, H_ - 30, "EasyMathBooks  ·  Answer key")
        c.setFillGray(0)
        c.setFont(BOLD, 15)
        c.drawString(MARGIN, H_ - 52, f"Level {level.num} – Sheet {code}")
        c.setLineWidth(1.2)
        c.line(MARGIN, H_ - 64, W - MARGIN, H_ - 64)
        for i, p in enumerate(chunk):
            r, k = divmod(i, cols)
            x = MARGIN + k * col_w
            y = H_ - 92 - r * row_h
            draw_label(c, start + i + 1, x, y)
            w = draw_text(c, p.markup, x + LABEL_OFF, y, size)
            sep = "   " if p.kind == "eq" else " = "
            c.setFont(FONT, size)
            c.drawString(x + LABEL_OFF + w, y, sep)
            w += stringWidth(sep, FONT, size)
            c.setFont(BOLD, size)
            draw_text(c, p.answer, x + LABEL_OFF + w, y, size)
        start += len(chunk)
        c.showPage()


# --------------------------------------------------------------------------
# Sheet creation
# --------------------------------------------------------------------------

def make_sheet(level, rng, count, book_seen):
    page = {}
    tries = 0
    limit = max(count, 1) * 200
    while len(page) < count and tries < limit:
        tries += 1
        p = level.gen(rng)
        if p.key in page:
            continue
        if p.key in book_seen and tries < limit // 2:
            continue   # prefer problems not already used on earlier sheets
        page[p.key] = p
    book_seen.update(page)
    return list(page.values())


def pick_example(level, rng):
    saved = rng.getstate()
    kind = level.gen(rng).kind
    rng.setstate(saved)
    if kind != "stack":
        return None
    return level.gen(rng)


def plan_sheet(level, variant, pagesize, examples=True, pages=1):
    """Build the problem list for a sheet code. Same code always yields the same problems."""
    rng = rng_for_sheet(level.num, variant)
    _, page_h = pagesize
    example = pick_example(level, rng) if examples else None
    book_seen = set()
    if example is not None:
        book_seen.add(example.key)
    page_count = max(1, int(pages))
    counts = [
        page_capacity(level, page_h, pi == 0, example is not None)
        for pi in range(page_count)
    ]
    probs = make_sheet(level, rng, sum(counts), book_seen)
    chunks, pos = [], 0
    for n in counts:
        chunk = probs[pos:pos + n]
        if chunk:
            chunks.append(chunk)
        pos += n
    if not chunks:
        chunks = [[]]
    return chunks, example


def preview_sheet(level, variant, pagesize, examples=True, pages=1):
    chunks, example = plan_sheet(level, variant, pagesize, examples, pages)
    return {
        "code": sheet_code(level.num, variant),
        "problem_count": sum(len(ch) for ch in chunks),
        "pages": len(chunks),
        "has_example": example is not None,
    }


def generate_one(level, variant, outdir, pagesize, answers=True, examples=True,
                 pages=1, student_name=None, motif=None):
    """Write one worksheet PDF (and optional answer key) for sheet code like 1-1."""
    code = sheet_code(level.num, variant)
    chunks, example = plan_sheet(level, variant, pagesize, examples, pages)
    problems = [p for ch in chunks for p in ch]
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    base = f"Level_{level.num:02d}_{code}_{slug(level.title)}"
    if student_name:
        base += f"_{slug(student_name)}"
    if motif:
        base += f"_motif-{motif}"
    path = outdir / f"{base}.pdf"
    W, H_ = pagesize
    c = canvas.Canvas(str(path), pagesize=pagesize, invariant=1)
    c.setTitle(f"EasyMathBooks Sheet {code}: {level.title}")
    draw_sheet(c, W, H_, level, code, chunks, example,
               hints=examples, student_name=student_name, motif=motif)
    c.save()
    apath = None
    if answers:
        apath = outdir / f"{base}_answers.pdf"
        c = canvas.Canvas(str(apath), pagesize=pagesize, invariant=1)
        c.setTitle(f"EasyMathBooks Sheet {code} answers")
        draw_answers(c, W, H_, level, code, problems)
        c.save()
    return GeneratedSheet(code, level.num, variant, len(problems), path, apath)


def generate_codes(codes, outdir, pagesize, answers=True, examples=True,
                   pages=1, student_name=None):
    out = []
    for code in codes:
        level_num, variant = parse_sheet_code(code)
        out.append(generate_one(
            LEVEL_BY_NUM[level_num], variant, outdir, pagesize,
            answers=answers, examples=examples, pages=pages,
            student_name=student_name,
        ))
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_levels(spec):
    if spec.lower() == "all":
        return [lv.num for lv in LEVELS]
    nums = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            nums.extend(range(int(a), int(b) + 1))
        else:
            nums.append(int(part))
    bad = [n for n in nums if n not in LEVEL_BY_NUM]
    if bad:
        raise SystemExit(f"Unknown level(s): {bad}. Use --list to see levels 1-{len(LEVELS)}.")
    return nums


def parse_sheet_list(spec):
    codes = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            parse_sheet_code(part)
        except ValueError as e:
            raise SystemExit(str(e))
        codes.append(part.replace(" ", ""))
    if not codes:
        raise SystemExit("No sheet codes given.")
    return codes


def paper_size(name):
    return A4 if name == "a4" else letter


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Generate Kumon-style math worksheets as PDF. "
                    "Sheet codes look like 1-1 (level 1, variant 1) and always reprint the same problems."
    )
    ap.add_argument("--sheet", help='sheet code(s): "1-1" or "1-1,1-2,5-3"')
    ap.add_argument("-l", "--level", help='levels to generate: "5", "1-10", "3,7,12" or "all"')
    ap.add_argument("-n", "--sheets", type=int, default=1,
                    help="variants per level when using --level, as 1..N (default 1)")
    ap.add_argument("--start-variant", type=int, default=1,
                    help="first variant number when using --level (default 1)")
    ap.add_argument("-o", "--out", default="output", help="output folder (default ./output)")
    ap.add_argument("-p", "--pages", type=int, default=1, help="pages per sheet (default 1, filled to capacity)")
    ap.add_argument("--paper", choices=["letter", "a4"], default="letter")
    ap.add_argument("--name", help="fill the Name line on the worksheet")
    ap.add_argument("--no-examples", action="store_true", help="no Note box / hint digits")
    ap.add_argument("--no-answers", action="store_true", help="skip the answer-key PDFs")
    ap.add_argument("--list", action="store_true", help="list all levels and exit")
    args = ap.parse_args(argv)

    if args.list or (not args.level and not args.sheet):
        for lv in LEVELS:
            print(f"{lv.num:>3}  {lv.title}")
        if not args.level and not args.sheet:
            print("\nExamples:")
            print("  python generate.py --sheet 1-1")
            print("  python generate.py --level 1 --sheets 5      # sheets 1-1 through 1-5")
            print("  python generate.py --level 1-10 --sheets 2")
        return 0

    if args.sheets < 1:
        raise SystemExit("--sheets must be at least 1")
    if args.start_variant < 1:
        raise SystemExit("--start-variant must be at least 1")
    if args.pages < 1:
        raise SystemExit("--pages must be at least 1")

    if args.sheet:
        codes = parse_sheet_list(args.sheet)
    else:
        start = args.start_variant
        codes = [
            sheet_code(n, start + i)
            for n in parse_levels(args.level)
            for i in range(args.sheets)
        ]

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    pagesize = paper_size(args.paper)
    for result in generate_codes(
        codes, outdir, pagesize,
        answers=not args.no_answers,
        examples=not args.no_examples,
        pages=args.pages,
        student_name=args.name,
    ):
        print(result.pdf_path)
        if result.answers_path:
            print(result.answers_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
