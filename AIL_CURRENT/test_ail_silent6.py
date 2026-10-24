"""Differences from CPython 3.12 that printed a different answer without a diagnostic (silent6).

S1  an int in a float slot of a tuple-lowered program (list[float] literal, append, return, annotated local) stays
    an int: the lowering used to write `0.0` into the source that the general path compiled too (corpus g17_024).
S2  a @dataclass's generated __eq__ on the general path: same class and the compared fields equal, in order (not
    identity); another class, None or a number is False; eq=False, compare=False and a user __eq__ are honoured;
    `in`, `index`, `count` and list == work (corpus g14_014).  order=True stays refused by name.
S3  float <= / >= with a NaN operand are False on the general path (they were True), != is True; the typed path
    and both IR modes agree.
S4  typed min(a, b) / max(a, b) of floats keep the first argument unless the second is smaller / larger (NaN).
Each program is run under CPython, on the general path forced (the loaded source through pyc --general-only) and
by default, under AIL_IR=0 and 1; the typed path where it builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'python' / 'pkg-v12'), str(ROOT)]
CLI = str(ROOT / 'ail_chatgpt.py')
PYC = str(ROOT / 'python' / 'pkg-v12' / 'pyc.py')
import ail_chatgpt  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-silent6-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, source):
        path = self.dir / 'cpython_main.py'
        path.write_text(source, encoding='utf-8')
        return subprocess.run([sys.executable, '-B', str(path)], capture_output=True, text=True, timeout=120).stdout

    def run_exe(self, exe, expected, label):
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.stdout, expected, label)
        self.assertEqual(ran.returncode, 0, label)

    def build(self, source, mode):
        entry = self.dir / 'main.py'
        entry.write_text(source, encoding='utf-8')
        exe = self.dir / ('out_' + mode)
        env = dict(os.environ, AIL_IR='1' if mode.endswith('1') else '0')
        env.pop('AIL_NO_GENERAL', None)
        if mode == 'general':
            text = ail_chatgpt._load_sources(entry, source_syntax='python', module_only=False, module_paths=[],
                                             local_imports=True)[0]
            gen = self.dir / 'gen.py'
            gen.write_text(text, encoding='utf-8')
            env['AIL_SURFACE'] = 'python'
            command = [sys.executable, '-B', PYC, str(exe), '--file', str(gen), '--general-only']
        else:
            if mode.startswith('typed'):
                env['AIL_NO_GENERAL'] = '1'
            command = [sys.executable, '-B', CLI, 'compile', str(entry), '--syntax', 'python', '-o', str(exe)]
        built = subprocess.run(command, cwd=self.dir, capture_output=True, text=True, timeout=900, env=env)
        return built, exe

    def same(self, source, typed=False, general=True):
        """Prints what CPython prints: general forced, default (IR 0 and 1), and the typed path when `typed`."""
        expected = self.cpython(source)
        modes = (['general'] if general else []) + ['default0', 'default1'] + (['typed0', 'typed1'] if typed else [])
        for mode in modes:
            built, exe = self.build(source, mode)
            self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
            self.run_exe(exe, expected, mode)
        return expected

    def refused_typed(self, source):
        built, _ = self.build(source, 'typed0')
        self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
        self.assertNotIn('Traceback', built.stderr)
        return built.stderr


G17_SRC = '# task: Use functools.partial to build a family of power functions and map them over a fixed base value.\nfrom functools import partial\nfrom typing import Callable\n\n\ndef power(base: float, exponent: float) -> float:\n    """Return base raised to exponent."""\n    return base ** exponent\n\n\ndef make_power_family(exponents: list[float]) -> list[Callable[[float], float]]:\n    """Build a family of power functions, one per exponent, using partial.\n\n    Each returned callable takes a base value and raises it to a fixed exponent.\n    """\n    return [partial(power, exponent=e) for e in exponents]\n\n\ndef main() -> None:\n    exponents: list[float] = [0, 1, 2, 3, 0.5, -1]\n    fixed_base: float = 2.0\n\n    family = make_power_family(exponents)\n\n    # Map each partial function over the fixed base value.\n    results: list[float] = list(map(lambda f: f(fixed_base), family))\n\n    print(f"Fixed base: {fixed_base}")\n    for e, r in zip(exponents, results):\n        print(f"  {fixed_base} ** {e} = {r}")\n\n    # Also demonstrate the partial objects directly via map.\n    squares_and_cubes = list(map(partial(power, exponent=2), [1.0, 2.0, 3.0, 4.0]))\n    print(f"Squares of [1, 2, 3, 4]: {squares_and_cubes}")\n\n\nif __name__ == "__main__":\n    main()\n'

G17_004_SRC = '# task: Use functools.partial to create a scaling function and apply it to a list of numbers with map.\nfrom functools import partial\n\n\ndef scale(factor: float, value: float) -> float:\n    return factor * value\n\n\ndef main() -> None:\n    numbers: list[float] = [1, 2, 3, 4.5, -2, 10]\n    double = partial(scale, 2)\n    triple = partial(scale, 3)\n    half = partial(scale, 0.5)\n    print("Doubled: ", list(map(double, numbers)))\n    print("Tripled: ", list(map(triple, numbers)))\n    print("Halved:  ", list(map(half, numbers)))\n\n\nif __name__ == "__main__":\n    main()\n'

SLOTS_SRC = 'def avg(xs: list[float]) -> float:\n    return sum(xs) / len(xs)\n\ndef zero() -> float:\n    return 0\n\ndef main() -> None:\n    xs: list[float] = [1, 2.5]\n    print(xs)\n    xs.append(3)\n    print(xs, avg(xs))\n    z: float = 4\n    print(z, zero())\n    t: tuple[float, float] = (1, 2)\n    print(t)\n\nmain()\n'

DC1_SRC = 'from dataclasses import dataclass, field\n\n@dataclass\nclass P:\n    x: int\n    y: int\n\n@dataclass\nclass Q:\n    x: int\n    y: int\n\n@dataclass\nclass R:\n    a: int\n    note: str = field(default="", compare=False)\n\n@dataclass(eq=False)\nclass N:\n    a: int\n\ndef main() -> None:\n    print(P(1, 2) == P(1, 2))\n    print(P(1, 2) == P(2, 1))\n    print(P(1, 2) != P(1, 2))\n    print(P(1, 2) == Q(1, 2))\n    a = P(3, 4)\n    print(a == a)\n    print(R(1, "a") == R(1, "b"))\n    print(N(1) == N(1))\n    lst = [P(1, 2), P(3, 4)]\n    print(P(3, 4) in lst)\n    print(lst == [P(1, 2), P(3, 4)])\n    print(lst.index(P(3, 4)))\n    print(P(1, 2) == 5)\n    print(P(1, 2) == None)\n\nmain()\n'

DC2_SRC = 'from dataclasses import dataclass, field\n\n@dataclass(frozen=True)\nclass A:\n    x: int\n    y: float\n\n@dataclass(frozen=True)\nclass B(A):\n    z: int = 0\n\n@dataclass\nclass Box:\n    a: A\n    items: list[int] = field(default_factory=list)\n\n@dataclass\nclass W:\n    v: float\n\n@dataclass\nclass S:\n    n: int\n    def __eq__(self, other):\n        return isinstance(other, S) and self.n % 10 == other.n % 10\n\n@dataclass(repr=False)\nclass H:\n    n: int\n\ndef main() -> None:\n    print(A(1, 2.5) == A(1, 2.5))\n    print(B(1, 2.5, 3) == B(1, 2.5, 3))\n    print(B(1, 2.5, 3) == B(1, 2.5, 4))\n    print(Box(A(1, 1.5), [1, 2]) == Box(A(1, 1.5), [1, 2]))\n    print(Box(A(1, 1.5), [1, 2]) == Box(A(1, 1.5), [1, 3]))\n    nan = float("nan")\n    w = W(nan)\n    print(w == w, W(nan) == W(nan), W(1.0) == W(1))\n    print(S(3) == S(13), S(3) != S(13))\n    print(H(1) == H(1))\n    print(A(1, 2.0) == (1, 2.0))\n    xs = [Box(A(i, 0.5)) for i in range(3)]\n    print(Box(A(2, 0.5)) in xs, xs.count(Box(A(1, 0.5))))\n    ys = [A(1, 1.0), A(2, 2.0)]\n    print(ys == [A(1, 1.0), A(2, 2.0)], ys != [A(1, 1.0)])\n    print(A(1, 1.0) is A(1, 1.0), A(1, 1.0) == A(1, 1.0))\n    print(A(1, 2.5) != A(1, 2.5), A(1, 2.5) != A(2, 2.5))\n\nmain()\n'

DC3_SRC = 'from dataclasses import dataclass\n\n@dataclass\nclass P:\n    x: int\n    y: int\n\n@dataclass\nclass Q:\n    x: int\n    y: int\n\ndef main() -> None:\n    a = P(1, 2)\n    b = P(1, 2)\n    print(a == b, a != b, a == P(2, 1))\n    print(a == Q(1, 2))\n    print(a == a)\n\nmain()\n'

DC4_SRC = 'from dataclasses import dataclass\n\n@dataclass(order=True)\nclass V:\n    a: int\n    b: int\n\ndef main() -> None:\n    print(V(1, 2) < V(1, 3), V(2, 0) >= V(1, 9), V(1, 2) == V(1, 2))\n    print(sorted([V(2, 1), V(1, 5), V(1, 2)]))\n    print(max(V(1, 1), V(0, 7)))\n\nmain()\n'

G14_SRC = '# task: Implement a dataclass Matrix2x2 supporting __add__ and __mul__ and print the results of a few operations.\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass\n\n\n@dataclass(frozen=True)\nclass Matrix2x2:\n    a: int\n    b: int\n    c: int\n    d: int\n\n    def __add__(self, other: object) -> Matrix2x2:\n        if not isinstance(other, Matrix2x2):\n            return NotImplemented\n        return Matrix2x2(\n            self.a + other.a,\n            self.b + other.b,\n            self.c + other.c,\n            self.d + other.d,\n        )\n\n    def __mul__(self, other: object) -> Matrix2x2:\n        if isinstance(other, Matrix2x2):\n            return Matrix2x2(\n                self.a * other.a + self.b * other.c,\n                self.a * other.b + self.b * other.d,\n                self.c * other.a + self.d * other.c,\n                self.c * other.b + self.d * other.d,\n            )\n        if isinstance(other, int):\n            return Matrix2x2(\n                self.a * other,\n                self.b * other,\n                self.c * other,\n                self.d * other,\n            )\n        return NotImplemented\n\n    def __rmul__(self, other: object) -> Matrix2x2:\n        if isinstance(other, int):\n            return self * other\n        return NotImplemented\n\n    def __str__(self) -> str:\n        return f"[[{self.a}, {self.b}], [{self.c}, {self.d}]]"\n\n\ndef main() -> None:\n    m1 = Matrix2x2(1, 2, 3, 4)\n    m2 = Matrix2x2(5, 6, 7, 8)\n    identity = Matrix2x2(1, 0, 0, 1)\n\n    print("m1 =", m1)\n    print("m2 =", m2)\n    print("m1 + m2 =", m1 + m2)\n    print("m1 * m2 =", m1 * m2)\n    print("m2 * m1 =", m2 * m1)\n    print("m1 * identity =", m1 * identity)\n    print("3 * m1 =", 3 * m1)\n    print("m2 * -2 =", m2 * -2)\n    print("m1 == m1 * identity:", m1 == m1 * identity)\n    print("repr:", repr(m1 + m2))\n\n\nif __name__ == "__main__":\n    main()\n'

NAN1_SRC = 'import math\n\ndef cmp(a: float, b: float) -> None:\n    print(a < b, a <= b, a > b, a >= b, a == b, a != b)\n\ndef main() -> None:\n    nan = float("nan")\n    one = 1.0\n    cmp(nan, one)\n    cmp(one, nan)\n    cmp(nan, nan)\n    cmp(one, one)\n    cmp(one, 2.0)\n    cmp(2.0, one)\n    print(nan <= 1.0, nan >= 1.0, 1.0 <= nan, 1.0 >= nan, nan != nan)\n    xs = [1.0, nan, 3.0]\n    c = 0\n    for v in xs:\n        if v <= 2.0:\n            c += 1\n        if v >= 2.0:\n            c += 10\n    print(c)\n    print(0.0 <= nan <= 1.0, one < 2.0 <= nan)\n    print(min(nan, 1.0), max(nan, 1.0), min(1.0, nan), max(1.0, nan))\n    print(not (nan <= 1.0), not (nan < 1.0))\n    print(math.isnan(nan), nan == nan)\n    i = 3\n    print(nan <= i, nan >= i, i <= nan, i >= nan, nan > i, nan != i)\n\nmain()\n'

NAN2_SRC = 'def sign(x: float, y: float) -> int:\n    if x < y:\n        return -1\n    elif x > y:\n        return 1\n    elif x == y:\n        return 0\n    return 9\n\ndef clamp(x: float, lo: float, hi: float) -> float:\n    if x <= lo:\n        return lo\n    if x >= hi:\n        return hi\n    return x\n\ndef count(xs: list[float], t: float) -> int:\n    n = 0\n    for v in xs:\n        if not (v >= t):\n            n += 1\n        if not v <= t:\n            n += 100\n    return n\n\ndef loop(x: float) -> int:\n    n = 0\n    while not (x >= 3.0):\n        n += 1\n        if n > 5:\n            break\n        x += 1.0\n    return n\n\ndef tern(a: float, b: float) -> int:\n    return 1 if a <= b else (2 if a >= b else 3)\n\ndef main() -> None:\n    nan = float("nan")\n    print(sign(nan, 1.0), sign(1.0, nan), sign(nan, nan), sign(1.0, 2.0))\n    print(clamp(nan, 0.0, 1.0), clamp(0.5, 0.0, 1.0), clamp(-1.0, 0.0, 1.0))\n    print(count([1.0, nan, 5.0], 3.0))\n    print(loop(nan), loop(0.0))\n    print(tern(nan, 1.0), tern(1.0, nan), tern(1.0, 1.0))\n    x = nan\n    flags = (x <= x, x >= x, x < x, x > x, x == x, x != x)\n    print(flags[0], flags[1], flags[2], flags[3], flags[4], flags[5])\n    ok = 0.0 <= x\n    print(ok, 1.0 >= x, x <= 1, x >= 1, 1 <= x, 1 >= x)\n    inf = float("inf")\n    print(inf <= inf, inf >= inf, -inf <= inf, inf >= nan, nan <= -inf)\n\nmain()\n'

MINMAX_SRC = 'def main() -> None:\n    nan = float("nan")\n    a = nan\n    b = 1.0\n    print(min(a, b), max(a, b), min(b, a), max(b, a))\nmain()\n'


class FloatSlotTests(Base):
    def test_corpus_g17_024(self):
        self.same(G17_SRC)

    def test_corpus_g17_004_positional_partial(self):
        self.same(G17_004_SRC)

    def test_ints_in_float_slots_stay_ints(self):
        out = self.same(SLOTS_SRC)
        self.assertIn('[1, 2.5]', out)
        self.refused_typed(SLOTS_SRC)


class DataclassEqTests(Base):
    def test_basic_and_fields(self):
        self.same(DC1_SRC)

    def test_inheritance_nesting_nan_user_eq_repr_false(self):
        self.same(DC2_SRC)

    def test_same_class_only(self):
        self.same(DC3_SRC)

    def test_corpus_g14_014(self):
        self.same(G14_SRC, general=False)

    def test_order_true_matches_cpython(self):
        # was refused by name; the general path now builds order=True (merge cov1): it must print what CPython prints
        self.same(DC4_SRC)


class NanTests(Base):
    def test_every_comparison_general_default_typed(self):
        self.same(NAN1_SRC, typed=True)

    def test_control_flow_shapes(self):
        self.same(NAN2_SRC, typed=True)

    def test_min_max_keep_the_first_argument(self):
        self.same(MINMAX_SRC, typed=True)


if __name__ == '__main__':
    unittest.main()
