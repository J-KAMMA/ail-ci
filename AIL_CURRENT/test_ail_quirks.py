"""Compiler quirks found by the library agents, each compared with CPython 3.12 in the default build, the
typed path alone, the IR path (AIL_IR=1) and, where the general (boxed) runtime can hold the program,
the general path alone (pyc.py --general-only).

Q1  early returns in functions whose conditions overlap (elif chains, loops, try/finally, owned values)
    and a typed clone that prints inside a general-path program (IR mode: the clone's stdout was a second
    buffer and its lines came out before everything the boxed code had printed)
Q2  a comprehension variable is local to the comprehension (compscope.py): nested comprehensions with the
    same variable name, a comprehension variable that is also a variable of the function
Q3  sum / min / max / any / all over a generator expression whose items are class instances
Q4  a module-level list or tuple of str literals (NAMES = ["a", "b"]) on the typed path
Q5  scalar Optional (`int | None`, `Optional[str]`, ...) on the typed path

The expected output of every program is what CPython 3.12 prints.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
ON_312 = sys.version_info[:2] == (3, 12)

MODES = ('default', 'typed', 'ir', 'general')


def build(directory, text, name, mode):
    """Compile `text` in one mode. Returns (completed process, executable path)."""
    source, exe = Path(directory, name + '.ail'), Path(directory, name + '_' + mode)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    if mode == 'general':
        command = [sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only']
    else:
        if mode == 'typed':
            env['AIL_NO_GENERAL'] = '1'
        if mode == 'ir':
            env['AIL_IR'] = '1'
        command = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                   '--syntax', 'python', '-o', exe.name]
    return subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=120,
                          encoding='utf-8')


@unittest.skipUnless(ON_312, 'the expected output is CPython 3.12 behaviour')
class Quirks(unittest.TestCase):
    def same(self, text, name, modes=MODES, allow=()):
        """AIL's stdout and exit status equal CPython's in every mode that builds. A mode in `allow` may
        refuse the program by name instead; at least one mode must build."""
        built_any = False
        with tempfile.TemporaryDirectory() as directory:
            expected = cpython(directory, text, name)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for mode in modes:
                with self.subTest(mode=mode):
                    built, exe = build(directory, text, name, mode)
                    if built.returncode != 0:
                        self.assertIn(mode, allow, '%s: %s' % (mode, built.stdout + built.stderr))
                        self.assertIn('not in the subset', built.stdout + built.stderr)
                        continue
                    built_any = True
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300,
                                         encoding='utf-8')
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                     ran.stderr[-400:])
        self.assertTrue(built_any)

    def refused(self, text, name, words, mode='typed'):
        """The program is refused by name (no executable) in `mode`, and the message has every word."""
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, name, mode)
            self.assertNotEqual(built.returncode, 0, 'expected a refusal')
            message = built.stdout + built.stderr
            self.assertIn('not in the subset', message)
            for word in words:
                self.assertIn(word, message)

    def test_early_returns_overlapping_conditions(self):
        text = '''
def a(x: int) -> int:
    if x > 0:
        return 1
    if x > -5:
        return 2
    if x < 3:
        return 3
    return 4

def b(x: int, y: int) -> int:
    if x > 0 and y > 0:
        return 10
    elif x > 0:
        return 20
    elif y > 0 or x > -3:
        return 30
    elif x == -10:
        return 40
    else:
        return 50

def c(xs: list[int]) -> int:
    t = 0
    for i in range(len(xs)):
        if xs[i] > 5:
            return t
        if xs[i] > 2:
            t += 100
            continue
        for j in range(3):
            if j == xs[i]:
                return t + j + 1000
        t += xs[i]
    return -t

def d(x: int) -> int:
    r = 0
    try:
        if x > 3:
            return 1
        if x > 1:
            return 2
        r = 5
    finally:
        r += 1
        print("fin", x, r)
    return r

def e(x: int) -> int:
    for i in range(5):
        try:
            if i == x:
                return i * 10
            if i > 1:
                continue
        finally:
            print("f", i)
    return -1

def main() -> None:
    for x in range(-12, 8):
        print(x, a(x), b(x, x - 2), b(-x, x))
    print(c([1, 2, 3, 0]), c([0]), c([1, 1, 1]), c([9]), c([3,3,1,1,7]))
    for x in range(6):
        print(d(x), e(x))
main()
'''
        self.same(text, 'early_returns_overlapping_conditions', modes=MODES, allow=('general',))

    def test_elif_chain_that_needs_a_tint_fallback(self):
        text = '''
def b(x: int, y: int) -> int:
    if x > 0 and y > 0:
        return 10
    elif x > 0:
        return 20
    elif y > 0 or x > -3:
        return 30
    elif x == -10:
        return 40
    else:
        return 50

def main() -> None:
    for x in range(-12, 8):
        print(x, b(x, x - 2), b(-x, x))
main()
'''
        self.same(text, 'elif_chain_tint_fallback')

    def test_recursive_optional_result_on_the_typed_path(self):
        text = '''
def fact(n: int) -> int | None:
    if n < 0:
        return None
    if n <= 1:
        return 1
    r = fact(n - 1)
    if r is None:
        return None
    return n * r

def main() -> None:
    print(fact(5))
main()
'''
        self.same(text, 'recursive_optional_typed')

    def test_early_returns_with_side_effects_and_loops(self):
        text = '''
cnt = 0

def side(x: int) -> bool:
    global cnt
    cnt += 1
    return x % 2 == 0

def f1(x: int, y: int) -> str:
    if x > 0 and side(y):
        return "a"
    if x > 5 or side(x):
        return "b"
    if y > 0:
        if x < -3:
            return "c"
        if x < 0:
            return "d"
    elif y < -3:
        return "e"
    if x == y:
        return "f"
    return "g"

def f2(n: int) -> int:
    i = 0
    while True:
        i += 1
        if i > n:
            return -1
        if i % 3 == 0 and i % 2 == 0:
            return i
        if i % 3 == 0:
            continue
        if i % 5 == 0:
            break
    return i * 100

def f3(xs: list[int], t: int) -> bool:
    for x in xs:
        if x == t:
            return True
        if x > t:
            return False
    return False

def f4(a: float, b: float) -> float:
    if a < b:
        return a
    if a < b + 1.0:
        return b
    if a > 0.0:
        return a - b
    return 0.0

def f5(s: str) -> int:
    if s.startswith("a"):
        return 1
    if "b" in s:
        return 2
    if s.startswith("ab") or len(s) > 3:
        return 3
    if s == "":
        return 4
    return 5

def f6(x: int) -> int:
    with_val = 0
    try:
        try:
            if x > 2:
                return 10
            if x > 0:
                raise ValueError("v")
        finally:
            with_val += 1
            print("inner", x)
    except ValueError:
        if x == 1:
            return 11
        return 12
    finally:
        print("outer", x, with_val)
    return 13

def f7(x: int) -> int:
    for i in range(3):
        for j in range(3):
            if i + j == x:
                return i * 10 + j
            if i * j > x:
                break
        if i == x:
            return 99
    return -1

def f8(x: int, y: int) -> int:
    if x > 0:
        if y > 0:
            return 1
    if y > 0:
        return 2
    if x > 0:
        return 3
    return 4

def f9(x: int) -> int:
    if x > 10: return 1
    elif x > 5: return 2
    if x > 7: return 3
    elif x > 2: return 4
    if x > 0: return 5
    return 6

def main() -> None:
    for x in range(-5, 12):
        for y in (-4, 0, 3, 6):
            print(x, y, f1(x, y), f8(x, y))
        print(x, f2(x), f3([1, 3, 5, 8], x), f4(x * 0.5, 2.0), f6(x % 5), f7(x), f9(x))
    for s in ["", "a", "ab", "b", "xxxx", "zz", "abc"]:
        print(s, f5(s))
    print(cnt)
main()
'''
        self.same(text, 'early_returns_with_side_effects_and_loops', modes=MODES, allow=('typed',))

    def test_early_returns_of_owned_values(self):
        text = '''
from dataclasses import dataclass


@dataclass
class P:
    a: int
    b: str


def g1(n: int) -> str:
    parts = []
    for i in range(n):
        parts.append(str(i))
    if n > 5:
        return ",".join(parts)
    if n > 2:
        return parts[-1] + "!"
    s = "x" * n
    if n > 1:
        return s + parts[0]
    return s


def g2(n: int) -> list[int]:
    out = [i * i for i in range(n)]
    if n > 6:
        return out[2:5]
    if n > 3:
        return out
    tmp = sorted(out, reverse=True)
    if n > 1:
        return tmp
    return []


def g3(n: int) -> tuple[int, str]:
    d = {}
    for i in range(n):
        d[i] = "v" + str(i)
    if n > 4:
        return (len(d), d[n - 1])
    if n > 1:
        return (n, d[0])
    return (0, "none")


def g4(n: int) -> P:
    p = P(n, "s" * n)
    if n > 3:
        return P(p.a + 1, p.b + "?")
    if n > 1:
        return p
    q = P(0, "z")
    return q


def g5(words: list[str], k: int) -> str:
    seen = set()
    for w in words:
        if w in seen:
            return w
        seen.add(w)
        if len(w) > k:
            return w.upper()
    if len(seen) > 2:
        return "many"
    return ""


def g6(xs: list[int]) -> int:
    best = None
    for x in xs:
        if x < 0:
            return -1
        if best is None or x > best:
            best = x
        if x == 7:
            return 7
    if best is None:
        return 0
    return best


def g7(n: int) -> dict[str, int]:
    m = {"a": n}
    if n > 5:
        return m
    m["b"] = n * 2
    if n > 2:
        return m
    return {}


def main() -> None:
    for n in range(9):
        print(n, g1(n), g2(n), g3(n), g4(n), g7(n))
    print(g5(["a", "b", "a"], 3), g5(["abcd"], 3), g5(["a", "b", "c"], 3), g5(["a"], 3))
    print(g6([]), g6([1, 2]), g6([1, -1]), g6([1, 7, 9]), g6([3, 9, 4]))


main()
'''
        self.same(text, 'early_returns_of_owned_values', modes=MODES, allow=('typed', 'general'))

    def test_early_returns_try_finally_for_else(self):
        text = '''
def h1(x: int) -> int:
    try:
        if x > 2:
            return 1
        if x > 0:
            return 2
        v = 10 // x
    except ZeroDivisionError:
        if x == 0:
            return 3
        return 4
    else:
        if v < -5:
            return 5
        return 6
    finally:
        print("h1", x)


def h2(x: int) -> int:
    for i in range(4):
        if i == x:
            break
        if i > x:
            return -i
    else:
        return 100
    return x * 2


def h3(x: int) -> int:
    i = 0
    while i < 10:
        i += 1
        if i == x:
            return i
        if i > x and i % 2 == 0:
            return -i
    else:
        return 0
    return 55


def h4(x: int) -> int:
    try:
        return x // (x - 2)
    except ZeroDivisionError:
        return -99
    finally:
        print("h4", x)


def h5(a: int, b: int, c: int) -> int:
    if a < b < c:
        return 1
    if a < b:
        return 2
    if b < c:
        return 3
    if a == b == c:
        return 4
    if a > b and not (b > c):
        return 5
    return 6


def h6(n: int) -> int:
    total = 0
    for i in range(n):
        for j in range(n):
            if j > i:
                break
            if (i + j) % 4 == 3:
                continue
            if i * j > 20:
                return total
            total += i * j
        if total > 30:
            return -total
    return total


def main() -> None:
    for x in range(-3, 6):
        print(x, h1(x), h2(x), h3(x), h4(x))
    for a in range(3):
        for b in range(3):
            for c in range(3):
                print(h5(a, b, c), end=" ")
    print()
    print([h6(n) for n in range(10)])


main()
'''
        self.same(text, 'early_returns_try_finally_for_else', modes=MODES, allow=('typed',))

    def test_typed_clone_that_prints_keeps_stdout_order(self):
        text = '''
def h2(x: int) -> int:
    for i in range(4):
        if i == x:
            break
    else:
        return 100
    return x * 2


def h1(x: int) -> int:
    try:
        v = 10 // x
    except ZeroDivisionError:
        return 3
    else:
        return 6
    finally:
        print("h1", x)


def main() -> None:
    print("start")
    for x in range(0, 3):
        print("loop", x)
        y = h1(x)
        print(y)


main()
'''
        self.same(text, 'typed_clone_that_prints_keeps_stdout_order', modes=MODES, allow=('typed',))

    def test_comprehension_variables_are_local_to_the_comprehension(self):
        text = '''
def f1(rows: list[list[int]]) -> list[list[int]]:
    return [[x * 2 for x in row] for row in rows]


def f2(n: int) -> list[list[int]]:
    return [[i * 10 + j for j in range(i)] for i in range(n)]


def f3(n: int) -> list[list[int]]:
    return [[i + j for i in range(n)] for j in range(n)]


def f4(n: int) -> list[int]:
    return [i for i in [i * 2 for i in range(n)] if i > 2]


def f5(n: int) -> int:
    total = 5
    xs = [total for total in range(n)]
    return total + len(xs)


def f6(n: int) -> int:
    i = 100
    ys = [[i for i in range(i2)] for i2 in range(n)]
    return i + len(ys)


def f7(n: int) -> int:
    x = 7
    a = [x for x in range(n)]
    b = sum(x for x in range(n))
    c = {x: x for x in range(n)}
    return x + len(a) + b + len(c)


def f8(rows: list[list[int]]) -> int:
    i = 3
    s = 0
    for i in range(len(rows)):
        s += sum([i for i in rows[i]])
    return s + i


def f9(n: int) -> int:
    k = 1
    t = [[k * j for k in range(3)] for j in range(n)]
    return k + len(t) + t[n - 1][2]


def main() -> None:
    print(len(f1([[1, 2], [3], []])), sum(f1([[1, 2], [3], []])[0]))
    print(sum(f2(4)[3]), sum(f3(3)[1]), sum(f4(5)))
    print(f5(3), f6(3), f7(4), f8([[1, 2], [3]]), f9(3))
    total = 5
    xs = [total for total in range(3)]
    print(total, len(xs), xs[2])


main()
'''
        self.same(text, 'comprehension_variables_are_local_to_the_comprehension', modes=MODES, allow=())

    def test_comprehension_scopes_printing_lists(self):
        text = '''
def f1(rows: list[list[int]]) -> list[list[int]]:
    return [[x * 2 for x in row] for row in rows]


def f2(n: int) -> list[list[int]]:
    return [[i * 10 + j for j in range(i)] for i in range(n)]


def f3(n: int) -> list[list[int]]:
    return [[i + j for i in range(n)] for j in range(n)]


def f4(n: int) -> list[int]:
    return [i for i in [i * 2 for i in range(n)] if i > 2]


def f5(n: int) -> int:
    total = 5
    xs = [total for total in range(n)]
    return total + len(xs)


def f6(n: int) -> int:
    i = 100
    ys = [[i for i in range(i2)] for i2 in range(n)]
    return i + len(ys)


def f7(n: int) -> int:
    x = 7
    a = [x for x in range(n)]
    b = sum(x for x in range(n))
    c = {x: x for x in range(n)}
    return x + len(a) + b + len(c)


def f8(rows: list[list[int]]) -> int:
    i = 3
    s = 0
    for i in range(len(rows)):
        s += sum([i for i in rows[i]])
    return s + i


def f9(n: int) -> int:
    k = 1
    t = [[k * j for k in range(3)] for j in range(n)]
    return k + len(t) + t[n - 1][2]


def main() -> None:
    print(f1([[1, 2], [3], []]))
    print(f2(4), f3(3), f4(5))
    print(f5(3), f6(3), f7(4), f8([[1, 2], [3]]), f9(3))
    total = 5
    xs = [total for total in range(3)]
    print(total, xs)


main()
'''
        self.same(text, 'comprehension_scopes_printing_lists', modes=MODES, allow=('typed',))

    def test_fold_over_generator_of_instances(self):
        text = '''
class Item:
    def __init__(self, v: int, w: float, tag: str) -> None:
        self.v = v
        self.w = w
        self.tag = tag


class Bag:
    def __init__(self) -> None:
        self.items: list[Item] = []


def total(rows: list[Item]) -> int:
    return sum(r.v for r in rows)


def heavy(rows: list[Item], lim: float) -> float:
    return sum(r.w for r in rows if r.w > lim)


def best(rows: list[Item]) -> int:
    return max(r.v * 2 for r in rows)


def lightest(rows: list[Item]) -> float:
    return min(r.w for r in rows if r.v > 1)


def tags(rows: list[Item]) -> int:
    return sum(len(r.tag) for r in rows)


def anybig(rows: list[Item]) -> bool:
    return any(r.v > 2 for r in rows)


def allpos(rows: list[Item]) -> bool:
    return all(r.v > 0 for r in rows)


def bagsum(b: Bag) -> int:
    return sum(i.v for i in b.items)


def main() -> None:
    rows = [Item(1, 0.5, "x"), Item(2, 1.5, "yy"), Item(3, 2.5, "zzz")]
    print(total(rows), heavy(rows, 1.0), best(rows), lightest(rows), tags(rows))
    print(anybig(rows), allpos(rows), anybig(rows[:2]), total([]))
    b = Bag()
    b.items.append(rows[0])
    b.items.append(rows[2])
    print(bagsum(b), sum(q.v for q in b.items), max(q.w for q in b.items))
    for r in rows:
        print(sum(q.v for q in rows if q.v != r.v), end=" ")
    print()
    print(sum(r.v for r in rows), r.v)


main()
'''
        self.same(text, 'fold_over_generator_of_instances', modes=MODES, allow=())

    def test_class_loop_variable_read_after_loop(self):
        # unbound.py guards a possibly-unassigned read; for a class value the guard wraps the whole attribute read
        text = '''
class Item:
    def __init__(self, v: int) -> None:
        self.v = v

    def twice(self, k: int) -> int:
        return self.v * 2 + k


def last(rows: list[Item]) -> int:
    for r in rows:
        pass
    return r.v + r.twice(1)


def main() -> None:
    print(last([Item(1), Item(4)]))
    try:
        print(last([]))
    except UnboundLocalError as e:
        print("unbound", e)


main()
'''
        self.same(text, 'class_loop_variable_read_after_loop', modes=MODES, allow=())

    def test_fold_over_dataclass_instances(self):
        text = '''
from dataclasses import dataclass


@dataclass
class Row:
    v: int
    w: float
    name: str


NAMES = ["a", "bb", "ccc"]


def total(rows: list[Row]) -> int:
    return sum(r.v for r in rows)


def totalw(rows: list[Row]) -> float:
    return sum(r.w * 2.0 for r in rows if r.v > 1)


def count_long(rows: list[Row]) -> int:
    return sum(1 for r in rows if len(r.name) > 1)


def names_len() -> int:
    n = 0
    for s in NAMES:
        n += len(s)
    return n + len(NAMES)


def main() -> None:
    rows = [Row(1, 0.5, "x"), Row(2, 1.5, "yy"), Row(3, 2.5, "zzz")]
    print(total(rows), totalw(rows), count_long(rows), names_len())
    print(sum(r.v for r in rows), NAMES[1], sum(len(s) for s in NAMES))


main()
'''
        self.same(text, 'fold_over_dataclass_instances', modes=MODES, allow=('general',))

    def test_module_level_list_of_str(self):
        text = '''
NAMES = ["a", "bb", "ccc"]
PAIRS = ("x", "y")
LIMIT = 5


def pick(i: int) -> str:
    return NAMES[i % len(NAMES)]


def count(w: str) -> int:
    c = 0
    for i in range(len(NAMES)):
        if NAMES[i] == w:
            c += 1
    return c


def join_all() -> str:
    return "-".join(NAMES)


def lens() -> list[int]:
    out = []
    for i, n in enumerate(NAMES):
        out.append(len(n) * i)
    return out


def main() -> None:
    for k in range(5):
        print(pick(k), end=" ")
    print()
    print(count("bb"), count("q"), join_all(), "bb" in NAMES, "zz" in NAMES, NAMES[-1], len(PAIRS))
    print(lens()[2], NAMES[1][0], NAMES[2] + PAIRS[1], LIMIT)
    ws = [w.upper() for w in NAMES]
    print(ws[2], len(ws))


main()
'''
        self.same(text, 'module_level_list_of_str', modes=MODES, allow=())

    def test_module_level_list_of_str_copy(self):
        text = '''
NAMES = ["a", "b"]


def main() -> None:
    ys = list(NAMES)
    ys.append("d")
    print(len(NAMES), len(ys))


main()
'''
        self.same(text, 'module_level_list_of_str_copy', modes=MODES, allow=())

    def test_optional_scalars_returns_params_locals(self):
        text = '''
from typing import Optional


def find(xs: list[int], t: int) -> int | None:
    for i in range(len(xs)):
        if xs[i] == t:
            return i
    return None


def name_of(k: int) -> Optional[str]:
    if k == 0:
        return "zero"
    if k == 1:
        return "one"
    return None


def half(x: float) -> float | None:
    if x < 0.0:
        return None
    return x / 2.0


def flag(k: int) -> bool | None:
    if k > 0:
        return True
    if k < 0:
        return False
    return None


def use(v: int | None) -> int:
    if v is None:
        return -1
    return v + 1


def main() -> None:
    xs = [5, 6, 7]
    a = find(xs, 6)
    b = find(xs, 9)
    print(a, b)
    if a is not None:
        print(a + 10)
    if b is None:
        print("none")
    print(use(a), use(b), use(None), use(3))
    best: int | None = None
    for x in xs:
        if best is None or x > best:
            best = x
    print(best)
    n = name_of(1)
    m = name_of(5)
    print(n, m, n == "one", m == None, n != None)
    if n is not None:
        print(n.upper(), len(n))
    h = half(3.0)
    g = half(-1.0)
    print(h, g, flag(1), flag(-1), flag(0))
    c: int | None = find(xs, 7)
    c2: int | None = None
    print(c == 2, c2 == None, c == c2)
    total = 0
    for k in range(4):
        r = name_of(k)
        if r is None:
            continue
        total += len(r)
    print(total)
    print(find(xs, 5) == 0, find(xs, 4) is None)


main()
'''
        self.same(text, 'optional_scalars_returns_params_locals', modes=MODES, allow=())

    def test_optional_defaults_methods_and_narrowing(self):
        text = '''
from typing import Optional


def greet(name: Optional[str] = None, times: int | None = None) -> str:
    if name is None:
        name = "world"
    n = 1 if times is None else times
    return ("hi " + name + ";") * n


def clamp(v: int | None, lo: int = 0, hi: int = 10) -> int | None:
    if v is None:
        return None
    if v < lo:
        return lo
    return v if v <= hi else hi


def parse(s: str) -> int | None:
    if s == "":
        return None
    total = 0
    for ch in s:
        if ch < "0" or ch > "9":
            return None
        total = total * 10 + (ord(ch) - 48)
    return total


def first_neg(xs: list[int]) -> int | None:
    i = 0
    while i < len(xs):
        if xs[i] < 0:
            return xs[i]
        i += 1
    return None


def fact(n: int) -> int | None:
    if n < 0:
        return None
    if n <= 1:
        return 1
    r = fact(n - 1)
    if r is None:
        return None
    return n * r


def avg(xs: list[float]) -> float | None:
    if len(xs) == 0:
        return None
    t = 0.0
    for x in xs:
        t += x
    return t / len(xs)


def ternary(k: int) -> str | None:
    return "even" if k % 2 == 0 else None


def label(v: int | None) -> str:
    if v:
        return "truthy:" + str(v)
    if v is None:
        return "none"
    return "zero"


def pair(a: int | None, b: int | None) -> int:
    if a is not None and b is not None:
        return a + b
    if a is not None:
        return a
    if b is None:
        return -1
    return b * 100


def loop_none(xs: list[int]) -> int:
    cur: int | None = None
    count = 0
    for x in xs:
        if cur is not None and x == cur:
            count += 1
        cur = x
    if cur is None:
        return -1
    return count * 1000 + cur


def swap_state(n: int) -> str:
    s: str | None = None
    for i in range(n):
        if s is None:
            s = "a"
        elif s == "a":
            s = "b"
        else:
            s = None
    return f"{s}|{s is None}|{str(s)}|{repr(s)}"


def main() -> None:
    print(greet(), greet("bob"), greet(times=2), greet(None, 3), greet(name="z", times=0))
    print(clamp(None), clamp(-3), clamp(4), clamp(50))
    print(parse("123"), parse(""), parse("12x"), parse("0"))
    print(first_neg([1, -2, 3]), first_neg([1, 2]), fact(5), fact(-1), avg([1.0, 2.0]), avg([]))
    print(ternary(2), ternary(3))
    print(label(None), label(0), label(7), pair(1, 2), pair(1, None), pair(None, None), pair(None, 2))
    print(loop_none([1, 1, 2, 2, 2]), loop_none([]))
    for n in range(5):
        print(swap_state(n))
    x = parse("77")
    if x is not None and x > 50:
        print("big", x)
    y = parse("zz")
    print(y == None, y != None, x == 77, x != 77, 77 == x, y == 3)


main()
'''
        self.same(text, 'optional_defaults_methods_and_narrowing', modes=MODES, allow=())

    def test_optional_calls_methods_try_and_merge(self):
        text = '''
class Acc:
    def __init__(self) -> None:
        self.total = 0
        self.names: list[str] = []

    def feed(self, k: int) -> None:
        v = lookup(k)
        if v is None:
            self.names.append("?")
            return
        self.total += v
        self.names.append(str(v))


def lookup(k: int) -> int | None:
    if k % 4 == 0:
        return None
    return k * 3


def word(k: int) -> str | None:
    if k < 0:
        return None
    return "w" * k


def chain(k: int, fallback: str | None = None) -> str | None:
    w = word(k)
    if w is None:
        return fallback
    if len(w) > 2:
        return w[:2] + "..."
    return w


def forward(v: int | None) -> int | None:
    return bump(v)


def bump(v: int | None) -> int | None:
    if v is None:
        return None
    return v + 1


def search(xs: list[int], t: int) -> int | None:
    lo = 0
    hi = len(xs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if xs[mid] == t:
            return mid
        if xs[mid] < t:
            lo = mid + 1
        else:
            hi = mid - 1
    return None


def tryret(s: str) -> int | None:
    try:
        return int(s)
    except ValueError:
        return None


def merge(a: int | None, b: int | None) -> int | None:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return a + b


def describe(k: int) -> str:
    r = lookup(k)
    if r is None:
        msg = "none"
    elif r > 10:
        msg = "big"
    else:
        msg = "small"
    return f"{k}:{msg}:{r}:{r if r is not None else -1}"


def main() -> None:
    acc = Acc()
    for k in range(6):
        acc.feed(k)
    print(acc.total, acc.names)
    print(chain(-1), chain(-1, "fb"), chain(2), chain(5), word(0) == "", word(-2) is None)
    print(forward(None), forward(4), bump(bump(1)))
    xs = [1, 3, 5, 7, 9]
    print(search(xs, 7), search(xs, 4), search([], 1))
    print(tryret("12"), tryret("zz"))
    print(merge(None, None), merge(1, None), merge(None, 2), merge(3, 4))
    for k in [1, 4, 5]:
        print(describe(k))
    print(lookup(3), lookup(4), word(2), word(-1))
    z = lookup(2)
    w = word(1)
    print(z, w, z == 6, w == "w")
    print(f"{z} {w} {lookup(4)}")


main()
'''
        self.same(text, 'optional_calls_methods_try_and_merge', modes=MODES, allow=())

    def test_optional_defaults_keep_their_order(self):
        text = '''
def show(a: int = 1, b: str | None = None, c: int = 3) -> str:
    out = str(a) + ":"
    if b is None:
        out += "-"
    else:
        out += b
    return out + ":" + str(c)


def two(x: float | None = None, y: bool | None = None) -> str:
    return f"{x}/{y}"


def main() -> None:
    print(show(), show(5), show(5, "q"), show(5, None, 9), show(c=7), show(b="z"), show(2, c=4))
    print(two(), two(1.5), two(None, True), two(y=False), two(0.0, None))


main()
'''
        self.same(text, 'optional_defaults_keep_their_order', modes=MODES, allow=())

    def test_optional_narrowing_after_assert(self):
        text = '''
def f(k: int) -> int | None:
    if k > 0:
        return k
    return None


def main() -> None:
    v = f(2)
    assert v is not None
    print(v + 1)


main()
'''
        self.same(text, 'optional_narrowing_after_assert', modes=MODES, allow=())

    def test_optional_narrowing_by_continue_in_while(self):
        text = '''
def f(k: int) -> int | None:
    if k % 3 == 0:
        return None
    return k * 2


def main() -> None:
    i = 0
    total = 0
    while i < 10:
        i += 1
        v = f(i)
        if v is None:
            continue
        total += v
    print(total)


main()
'''
        self.same(text, 'optional_narrowing_by_continue_in_while', modes=MODES, allow=())

    def test_optional_float(self):
        text = '''
def mean(xs: list[float]) -> float | None:
    if not xs:
        return None
    return sum(xs) / len(xs)


def main() -> None:
    m = mean([1.0, 2.5])
    n = mean([])
    print(m, n, m == 1.75, n == None)
    if m is not None:
        print(m * 2.0)


main()
'''
        self.same(text, 'optional_float', modes=MODES, allow=())

    def test_optional_bool(self):
        text = '''
def maybe(k: int) -> bool | None:
    if k == 0:
        return None
    return k > 0


def main() -> None:
    for k in range(-1, 2):
        r = maybe(k)
        if r is None:
            print("unknown")
        elif r:
            print("yes")
        else:
            print("no")
        print(r)


main()
'''
        self.same(text, 'optional_bool', modes=MODES, allow=())

    def test_optional_call_as_argument(self):
        text = '''
def f(k: int) -> int | None:
    if k > 0:
        return k
    return None


def g(v: int | None, w: int) -> int:
    if v is None:
        return w
    return v * w


def main() -> None:
    print(g(f(3), 2), g(f(0), 2), g(None, 5), g(7, 1))


main()
'''
        self.same(text, 'optional_call_as_argument', modes=MODES, allow=())

    def test_optional_arithmetic_needs_a_present_value(self):
        text = '''
def f(k: int) -> int | None:
    if k > 0:
        return k
    return None


def main() -> None:
    v = f(3)
    print(v + 1)


main()
'''
        self.same(text, 'optional_arithmetic_needs_a_present_value', allow=("typed",))
        self.refused(text, 'optional_arithmetic_needs_a_present_value', ["'v' may be None here"])

    def test_optional_method_needs_a_present_value(self):
        text = '''
def f(k: int) -> str | None:
    if k > 0:
        return "abc"
    return None


def main() -> None:
    v = f(1)
    print(v.upper())


main()
'''
        self.same(text, 'optional_method_needs_a_present_value', allow=("typed",))
        self.refused(text, 'optional_method_needs_a_present_value', ["'v' may be None here"])

    def test_optional_ordering_needs_a_present_value(self):
        text = '''
def f(k: int) -> int | None:
    if k > 0:
        return k
    return None


def main() -> None:
    v = f(2)
    print(v < 3)


main()
'''
        self.same(text, 'optional_ordering_needs_a_present_value', allow=("typed",))
        self.refused(text, 'optional_ordering_needs_a_present_value', ["'v' may be None here"])

    def test_optional_append_needs_a_present_value(self):
        text = '''
def f(k: int) -> int | None:
    if k > 0:
        return k
    return None


def main() -> None:
    xs = []
    v = f(0)
    xs.append(v)
    print(len(xs))


main()
'''
        self.same(text, 'optional_append_needs_a_present_value', allow=("typed",))
        self.refused(text, 'optional_append_needs_a_present_value', ["'v' may be None here"])

    def test_optional_loop_reassignment_drops_the_narrowing(self):
        text = '''
def f(k: int) -> int | None:
    if k > 0:
        return k
    return None


def main() -> None:
    v = f(5)
    if v is None:
        return
    for i in range(3):
        print(v + i)
        v = f(i)
        if v is None:
            break
    print(v is None)


main()
'''
        self.same(text, 'optional_loop_reassignment_drops_the_narrowing', allow=("typed",))
        self.refused(text, 'optional_loop_reassignment_drops_the_narrowing', ["'v' may be None here"])

    def test_optional_call_inside_and_is_refused(self):
        text = '''
def f(k: int) -> int | None:
    if k > 0:
        return k
    return None


def main() -> None:
    ok = True
    if ok and f(2) is None:
        print("n")
    else:
        print("y")


main()
'''
        self.same(text, 'optional_call_inside_and_is_refused', allow=("typed",))
        self.refused(text, 'optional_call_inside_and_is_refused', ['assign it to a name first'])

    def test_optional_field_is_refused(self):
        text = '''
class A:
    def __init__(self) -> None:
        self.v: int | None = None


def main() -> None:
    a = A()
    print(a.v is None)


main()
'''
        self.same(text, 'optional_field_is_refused', allow=("typed",))
        self.refused(text, 'optional_field_is_refused', ['an Optional scalar'])

    def test_optional_list_element_is_refused(self):
        text = '''
def main() -> None:
    xs: list[int | None] = [1, None]
    print(xs[1] is None)


main()
'''
        self.same(text, 'optional_list_element_is_refused', allow=("typed",))
        self.refused(text, 'optional_list_element_is_refused', ['None stored in a list'])

    def test_optional_from_dict_get_is_refused(self):
        text = '''
def f(d: dict[int, int], k: int) -> int | None:
    return d.get(k)


def main() -> None:
    print(f({1: 2}, 1), f({1: 2}, 3))


main()
'''
        self.same(text, 'optional_from_dict_get_is_refused', allow=("typed",))
        self.refused(text, 'optional_from_dict_get_is_refused', ['cannot show that `d.get(k)` is not None'])

    def test_none_in_a_tuple_keeps_the_program_unlowered(self):
        text = '''
def clamp(v: int | None) -> int | None:
    if v is None:
        return None
    return v + 1


def main() -> None:
    d = {1: 5}
    for v in (None, 3):
        r = clamp(v)
        print(r)
    w = d.get(2)
    print(clamp(w))


main()
'''
        self.same(text, 'none_in_a_tuple_keeps_the_program_unlowered', allow=("typed",))
        self.refused(text, 'none_in_a_tuple_keeps_the_program_unlowered', ['None stored in a list'])


if __name__ == "__main__":
    unittest.main()
