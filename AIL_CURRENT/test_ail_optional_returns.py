"""Optional results of unannotated functions (python/pkg-v12/optlib.py `annotate_none_returns`), against CPython 3.12.

A module-level function without a return annotation that returns None on some path and one scalar kind (int, float,
str, bool) on the others -- or only passes on the result of such a function -- is lowered as if it were written
`-> <kind> | None`: a present flag and the value. Every use of its result is proved present or the whole program
is refused by name on the typed path (the default build then takes the general path, which raises what CPython
raises).

R1  unit: which functions are inferred, and which are left alone (mixed kinds, decorated, generators, fall-off)
R2  unit: a program the Optional lowering refuses with the inference is lowered as before the inference existed
R3  truthiness: None, 0, '', 0.0 and False are told apart; `== None`, `!= None`, `is None`, `is not None`
R4  None returned through two calls; None through a loop-carried variable (the loop head sees it present)
R5  a use that may be None (`<`, `+`) is refused on the typed path and raises CPython's TypeError text on the
    general path; None in a list, mixed kinds, a bytes result stay on their old route and agree with CPython
R6  int(<text>) results beyond int64 stay exact in the default build and with AIL_UNIFIED_FORCE=1
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
from test_ail_nested_functions import build, run_cpython, run_exe   # noqa: E402
import optlib   # noqa: E402

HAVE_CC = shutil.which('gcc') is not None


def inferred(text):
    tree = ast.parse(text)
    optlib.annotate_none_returns(tree)
    return {n.name: ast.unparse(n.returns) for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.returns is not None}


class Inference(unittest.TestCase):
    def test_kinds(self):
        got = inferred('''
def a(n: int):
    if n < 0:
        return None
    return n

def b(s: str):
    if not s:
        return
    return s.lower()

def c(x: float):
    if x < 0.0:
        return None
    return x / 2.0

def d(n: int):
    if n < 0:
        return None
    return n > 3

def e(n: int):
    return a(n)

def f(n: int):
    if n:
        return e(n)
    return None
''')
        self.assertEqual(got, {'a': 'int | None', 'b': 'str | None', 'c': 'float | None', 'd': 'bool | None',
                               'e': 'int | None', 'f': 'int | None'})

    def test_left_alone(self):
        got = inferred('''
import functools

def mixed(n: int):
    if n < 0:
        return None
    if n == 0:
        return "zero"
    return n

def unknown(n):
    if n < 0:
        return None
    return n

@functools.cache
def decorated(n: int):
    if n < 0:
        return None
    return n

def gen(n: int):
    if n < 0:
        return None
    yield n

def falls(n: int):
    if n > 0:
        return n

def nothing(n: int):
    return None

def twice(n: int):
    return n

def twice(n: int):
    if n < 0:
        return None
    return n

def has_nested(n: int):
    def inner():
        return 1
    if n < 0:
        return None
    return n

def annotated(n: int) -> int:
    return n
''')
        self.assertEqual(got, {'annotated': 'int'})

    def test_refused_with_the_inference_is_lowered_as_before(self):
        text = '''def known(n: int) -> int | None:
    if n < 0:
        return None
    return n


def guess(n: int):
    if n < 0:
        return None
    return n


def main() -> None:
    k = known(3)
    if k is None:
        return
    print(k + 1)
    g = guess(2)
    print(g + 1)


main()
'''
        out = optlib.rewrite(text, [])
        self.assertIn('tuple[bool, int]', out)          # `known` is still lowered
        self.assertIn('def guess(n: int):', out)         # `guess` kept its source: `g + 1` may be None
        self.assertNotIn('def guess(n: int) -> tuple', out)
        notes = []
        optlib.rewrite(text, notes)
        self.assertEqual(len(notes), 1)
        self.assertIn("'g' may be None here", notes[0][1])


def program(body, tail='main()'):
    return 'import sys\n\n\n' + body.strip('\n') + '\n\n\n' + tail + '\n'


TRUTH = program('''
def nonneg(n: int):
    if n < 0:
        return None
    return n


def lower(s: str, k: int):
    if k < 0:
        return None
    return s.lower()


def half(x: float):
    if x < 0.0:
        return None
    return x / 2.0


def positive(n: int):
    if n < 0:
        return None
    return n > 0


def show_str(s: str, k: int) -> None:
    t = lower(s, k)
    if t is None:
        print("str none")
    elif t:
        print("str truthy", t)
    else:
        print("str empty but present", len(t))


def main() -> None:
    for n in [-1, 0, 7]:
        r = nonneg(n)
        if r is None:
            print("int none")
        elif r:
            print("int truthy", r)
        else:
            print("int falsy but present", r)
        print(r is None, r is not None, r == None, r != None)
        if not r:
            print("not r")
    show_str("", 1)
    show_str("AbC", 2)
    show_str("", -1)
    show_str("x", 0)
    for x in [-1.0, 0.0, 3.0]:
        h = half(x)
        if h is None:
            print("float none")
        elif h:
            print("float truthy", h)
        else:
            print("float zero but present", h)
    for n in [-1, 0, 5]:
        p = positive(n)
        if p is None:
            print("bool none")
        elif p:
            print("bool true")
        else:
            print("bool false but present")
''')

TWO_CALLS = program('''
def inner(n: int):
    if n % 3 == 0:
        return None
    return n * 2


def middle(n: int):
    return inner(n)


def outer(n: int):
    if n > 8:
        return None
    return middle(n + 1)


def main() -> None:
    total = 0
    for n in range(12):
        r = outer(n)
        if r is None:
            print(n, "none")
            continue
        total = total + r
        print(n, r)
    print(total)
''')

LOOP_CARRIED = program('''
def parse(s: str, lo: int, hi: int):
    if not s or not all("0" <= ch <= "9" for ch in s):
        return None
    v = int(s)
    if v < lo or v > hi:
        return None
    return v


def main() -> None:
    n = parse("12", 1, 100)
    seed = parse("7", 0, 1000)
    if n is None or seed is None:
        return
    x = seed
    acc = 0
    for i in range(n):
        x = (x * 31 + 7) % 1000003
        acc = acc + x
    print(acc, x)
    bad = parse("x1", 0, 5)
    print(bad is None, parse("", 0, 5) is None, parse("9", 0, 5) is None, parse("5", 0, 5))
''')

NONE_IN_LOOP = program('''
def find(xs: list[int], t: int):
    for i in range(len(xs)):
        if xs[i] == t:
            return i
    return None


def main() -> None:
    xs = [4, 8, 15, 16, 23, 42]
    cur = find(xs, 15)
    if cur is None:
        return
    steps = 0
    while steps < 4:
        cur = cur + 1
        steps = steps + 1
        nxt = find(xs, 100 + cur)
        if nxt is None:
            continue
        cur = nxt
    print(cur, steps)
    k = find(xs, 99)
    print(k is None, find(xs, 4))
''')

MAYBE_LT = program('''
def find(xs: list[int], t: int):
    for i in range(len(xs)):
        if xs[i] == t:
            return i
    return None


def main() -> None:
    r = find([1, 2, 3], 9)
    try:
        print(r < 3)
    except TypeError as e:
        print("TypeError", e)
    try:
        print(r + 1)
    except TypeError as e:
        print("TypeError", e)
    try:
        print(-r)
    except TypeError as e:
        print("TypeError", e)
    print(r)
''')

LISTS = program('''
def main() -> None:
    xs = [None, 3, None]
    print(xs, xs[0] is None, xs[1] is None)
    grid = [None] * 3
    grid[1] = 5
    print(grid)
''')

MIXED = program('''
def mixed(n: int):
    if n < 0:
        return None
    if n == 0:
        return "zero"
    return n


def main() -> None:
    print(mixed(-1), mixed(0), mixed(4))
''')

BIG = program('''
def parse(s: str, lo: int, hi: int):
    if not s or not all("0" <= ch <= "9" for ch in s):
        return None
    v = int(s)
    if v < lo or v > hi:
        return None
    return v


def main() -> None:
    for s in ["5", "9223372036854775807", "9223372036854775808", "99999999999999999999", "18446744073709551615", "x", ""]:
        r = parse(s, 0, 18446744073709551615)
        if r is None:
            print(s, "none")
        else:
            print(s, r, r * 3)
''')


def run_default(tmp, text, name, unified_force=False, args=()):
    source, exe = Path(tmp, name + '.py'), Path(tmp, name + ('_f' if unified_force else '_d'))
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_NO_GENERAL', None)
    if unified_force:
        env['AIL_UNIFIED_FORCE'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax',
                          'python', '-o', exe.name], cwd=tmp, capture_output=True, text=True, timeout=900, env=env)
    return res, exe


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Programs(unittest.TestCase):
    def agree(self, text, name, typed):
        """CPython == default build == AIL_UNIFIED_FORCE=1; the typed-only build accepts the program (typed) or
        refuses it by name (typed is a substring of the refusal)."""
        with tempfile.TemporaryDirectory(prefix='ail-optret-') as tmp:
            want = run_cpython(tmp, text, name)
            self.assertEqual(want.returncode, 0, want.stderr)
            for force in (False, True):
                res, exe = run_default(tmp, text, name, force)
                self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), 'unified_force=%s' % force)
            if typed is True:
                for ir in ('0', '1'):
                    res, exe = build(tmp, text, name, ir=ir)
                    self.assertEqual(res.returncode, 0, 'IR=%s\n%s' % (ir, res.stderr[-2000:]))
                    got = run_exe(exe)
                    self.assertEqual((got.returncode, got.stdout), (0, want.stdout), 'typed IR=%s' % ir)
            else:
                res, _ = build(tmp, text, name)
                self.assertNotEqual(res.returncode, 0, 'the typed path was expected to refuse this')
                self.assertIn(typed, res.stderr + res.stdout)
        return want.stdout

    def test_truthiness_and_comparisons_with_none(self):
        out = self.agree(TRUTH, 'truth', True)
        self.assertIn('int falsy but present 0', out)
        self.assertIn('str empty but present 0', out)
        self.assertIn('bool false but present', out)

    def test_none_through_two_calls(self):
        self.agree(TWO_CALLS, 'two', True)

    def test_loop_carried_value_is_present_at_the_loop_head(self):
        self.agree(LOOP_CARRIED, 'loop', True)

    def test_a_variable_that_may_become_none_in_a_loop_is_not_assumed_present(self):
        self.agree(NONE_IN_LOOP, 'noneloop', 'may be None')

    def test_use_that_may_be_none_raises_cpythons_error(self):
        out = self.agree(MAYBE_LT, 'maybe', 'may be None')
        self.assertIn("TypeError '<' not supported between instances of 'NoneType' and 'int'", out)
        self.assertIn("TypeError unsupported operand type(s) for +: 'NoneType' and 'int'", out)
        self.assertIn("TypeError bad operand type for unary -: 'NoneType'", out)

    def test_none_in_lists_and_mixed_kinds_keep_their_route(self):
        self.agree(LISTS, 'lists', 'the constant None')
        self.agree(MIXED, 'mixed', 'something else on another')

    def test_int_from_text_beyond_int64_is_exact(self):
        out = self.agree(BIG, 'big', 'beyond int64')
        self.assertIn('18446744073709551615 18446744073709551615 55340232221128654845', out)


if __name__ == '__main__':
    unittest.main()
