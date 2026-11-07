"""Module-level constants built from pure builtins (modfold.py, job pyreach11), compared with CPython 3.12.

    STOP_WORDS = frozenset(b"an and ...".split())     LOWER = bytes.maketrans(bytes(range(65, 91)), ...)
    STOP = set(w.encode() for w in "...".split())     DIGIT_VALUE = {}; for _c in "0123456789": DIGIT_VALUE[_c] = ...

The typed path folds such an initializer to the literal it equals (same lines, same binding point) and
the existing literal rules take over. F1 checks the fold itself on the source text (fast); F2 builds
programs typed-only, default and with AIL_UNIFIED_FORCE=1 and compares stdout and exit status with
CPython, including the shapes the fold must leave alone (mutation from a function, `global`
rebinding, a read before the definition runs, ints beyond int64, shared rows).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
ON_312 = sys.version_info[:2] == (3, 12)
sys.path.insert(0, str(PKG))
import modfold  # noqa: E402


def folded(text):
    out = modfold.fold(text)
    assert out.count('\n') == text.count('\n'), 'line numbers must not move'
    return out


class FoldText(unittest.TestCase):
    """F1: what is folded, and what is left exactly as written."""

    def assertFolds(self, text, *expected):
        out = folded(text)
        for line in expected:
            self.assertIn(line, out.splitlines())

    def assertKept(self, text):
        self.assertEqual(folded(text), text)

    def test_set_of_split_read_by_membership(self):
        self.assertFolds('STOP = set("of the a".split())\ndef f(w):\n    return w in STOP\n',
                         "STOP = {'a', 'of', 'the'}")

    def test_frozenset_of_bytes_split(self):
        self.assertFolds('S = frozenset(b"b a".split())\ndef f(w):\n    return w in S or len(S) > 3\n',
                         "S = frozenset({b'a', b'b'})")

    def test_frozenset_of_str_uses_the_list_spelling(self):
        # the typed path reads a frozenset of str as `frozenset([...])` (pyfunc _module_frozenset),
        # with its own refusals by name ("'V' is a module-level frozenset")
        self.assertFolds('S = frozenset("b a".split())\ndef f(w):\n    return w in S\n',
                         "S = frozenset(['a', 'b'])")

    def test_literal_frozenset_left_alone(self):
        for text in ('U = frozenset("aé☃")\n', 'D = frozenset(["0", "1"])\n',
                     'V = frozenset("aeiou")\ndef f():\n    return len(V)\n'):
            with self.subTest(text=text):
                self.assertKept(text)

    def test_set_from_generator(self):
        self.assertFolds('S = set(w.encode() for w in "x y".split())\ndef f(w):\n    return w not in S\n',
                         "S = {b'x', b'y'}")

    def test_bytes_maketrans(self):
        out = folded('L = bytes.maketrans(bytes(range(65, 91)), bytes(range(97, 123)))\n'
                     'def f(b):\n    return b.translate(L)\n')
        self.assertTrue(out.startswith("L = b'\\x00\\x01"))
        self.assertEqual(eval(out.splitlines()[0][4:]), bytes.maketrans(bytes(range(65, 91)), bytes(range(97, 123))))

    def test_str_maketrans_read_by_translate(self):
        self.assertFolds('T = str.maketrans("AB", "ab")\ndef f(s):\n    return s.translate(T)\n',
                         'T = {65: 97, 66: 98}')

    def test_dict_filled_by_module_loop(self):
        text = ('D = {}\nfor _c in "012":\n    D[_c] = len(D)\n\ndef f(c):\n    return D[c]\n')
        out = folded(text)
        self.assertEqual(out.splitlines()[:3], ["D = {'0': 0, '1': 1, '2': 2}", '', ''])
        self.assertEqual(out.splitlines()[4:], text.splitlines()[4:])

    def test_set_filled_by_add_loop(self):
        self.assertFolds('S = set()\nfor _w in "b a".split():\n    S.add(_w.encode())\n'
                         'def f(w):\n    return w in S\n', "S = {b'a', b'b'}")

    def test_known_constant_feeds_a_later_one(self):
        self.assertFolds('U = "ABC"\nT = bytes.maketrans(U.encode(), U.lower().encode())\n'
                         'def f(b):\n    return b.translate(T)\n', 'U = "ABC"')
        self.assertTrue(folded('U = "ABC"\nT = bytes.maketrans(U.encode(), U.lower().encode())\n'
                               'def f(b):\n    return b.translate(T)\n').splitlines()[1].startswith("T = b'"))

    def test_annotation_kept(self):
        self.assertFolds('S: set[str] = set("b a".split())\ndef f(w):\n    return w in S\n',
                         "S: set[str] = {'a', 'b'}")

    # ---- left alone

    def test_list_appended_from_a_function(self):
        self.assertKept('N = list("ab")\ndef add(x):\n    N.append(x)\n')

    def test_set_added_from_a_function(self):
        self.assertKept('S = set("a b".split())\ndef mark(w):\n    S.add(w)\n')

    def test_dict_stored_from_a_function(self):
        self.assertKept('D = {}\nfor _i in range(3):\n    D[_i] = _i\ndef put(k):\n    D[k] = 0\n')

    def test_rows_changed_through_the_table(self):
        self.assertKept('D = dict(a=[1])\ndef f():\n    D["a"].append(2)\n')

    def test_rebound_reader_builtin(self):
        self.assertKept('def len(x):\n    x.append(1)\n    return 0\nL = list("ab")\ndef f():\n    return len(L)\n')

    def test_table_passed_to_a_function(self):
        self.assertKept('D = dict(a=1)\ndef g(t):\n    return t\ndef f():\n    return g(D)\n')

    def test_global_rebinding(self):
        self.assertKept('S = set("a b".split())\ndef reset():\n    global S\n    S = set()\n')

    def test_read_before_definition_runs(self):
        self.assertKept('def has(w):\n    return w in S\nprint(has("a"))\nS = set("a b".split())\n')

    def test_set_walked_in_order(self):
        self.assertKept('P = frozenset(range(40, 0, -7))\ndef f():\n    return [x for x in P]\n')

    def test_shared_rows(self):
        self.assertKept('G = [[0] * 3] * 3\ndef f():\n    return G[0]\n')

    def test_shadowed_builtin(self):
        self.assertKept('def set(x):\n    return x\nS = set("a b".split())\ndef f(w):\n    return w in S\n')

    def test_user_function_in_initializer(self):
        self.assertKept('def g():\n    return "a b"\nS = frozenset(g().split())\ndef f(w):\n    return w in S\n')

    def test_dynamic_module_access(self):
        self.assertKept('S = set("a b".split())\ndef f(w):\n    return w in globals()["S"]\n')

    def test_initializer_that_raises(self):
        self.assertKept('D = {}\nfor _c in "ab":\n    D[_c] = int(_c)\ndef f():\n    return D["a"]\n')

    def test_loop_variable_read_later(self):
        self.assertKept('D = {}\nfor c in "ab":\n    D[c] = 1\ndef f():\n    return D["a"] + len(c)\n')

    def test_step_budget(self):
        self.assertKept('D = {}\nfor _i in range(10 ** 7):\n    D[_i % 3] = _i\ndef f():\n    return D[0]\n')

    def test_size_bounds(self):
        self.assertKept('B = bytes(10 ** 9)\ndef f():\n    return B[0]\n')
        self.assertKept('L = [0] * 10 ** 9\ndef f():\n    return L[0]\n')

    def test_empty_result_not_rewritten(self):
        self.assertKept('L = list()\ndef f():\n    return len(L)\n')

    def test_semicolon_line_left_alone(self):
        self.assertKept('S = set("a b".split()); X = 1\ndef f(w):\n    return w in S\n')

    def test_off_switch(self):
        os.environ['AIL_MODFOLD'] = '0'
        try:
            self.assertKept('STOP = set("of the a".split())\ndef f(w):\n    return w in STOP\n')
        finally:
            del os.environ['AIL_MODFOLD']


MODES = ('typed', 'default', 'unified')


def build(directory, text, name, mode):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_' + mode)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_MODFOLD'):
        env.pop(key, None)
    if mode == 'typed':
        env['AIL_NO_GENERAL'] = '1'
    elif mode == 'unified':
        env['AIL_UNIFIED_FORCE'] = '1'
    command = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
               '--syntax', 'python', '-o', exe.name]
    return subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


@unittest.skipUnless(ON_312, 'the expected output is CPython 3.12 behaviour')
class FoldPrograms(unittest.TestCase):
    """F2: built programs equal CPython; the typed path takes the folded ones."""

    def same(self, text, name, modes=MODES, stdin=''):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, name + '_cpython.py')
            path.write_text(text, encoding='utf-8')
            expected = subprocess.run([sys.executable, str(path)], capture_output=True, text=True,
                                      timeout=120, input=stdin)
            for mode in modes:
                with self.subTest(mode=mode):
                    built, exe = build(directory, text, name, mode)
                    self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, input=stdin)
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                     ran.stderr[-400:])

    def test_stop_words_and_lower_table(self):
        self.same('''
import sys
STOP = set(w.encode() for w in "the a of and".split())
UP = bytes.maketrans(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ", b"abcdefghijklmnopqrstuvwxyz")
WORDS = frozenset("cat dog".split())

def count(data):
    n = 0
    for w in data.split():
        if w.translate(UP) not in STOP:
            n += 1
    return n

def main():
    data = sys.stdin.buffer.read()
    print(count(data), "cat" in WORDS, len(WORDS))

main()
''', 'stop_lower', stdin='The cat SAT on THE mat of gold\nand A dog\n')

    def test_range_length_of_a_folded_bound(self):
        # `int("...")` folds to the literal; len(range(-n, n)) past int64 must still stop loudly,
        # and an empty range is 0, never a negative difference
        self.same('''
def f(a: int, b: int) -> int:
    return len(range(a, b)) + len(range(b))

r = range(10, 3)
print(f(5, 2), f(-3, 4), len(r), len(range(-4)))
n = int("9223372036854775807")
print(len(range(0, n)))
print(len(range(-n, n)))
''', 'range_len')

    def test_digit_table_from_module_loop(self):
        self.same('''
DIGIT_VALUE = {}
for _c in "0123456789":
    DIGIT_VALUE[_c] = len(DIGIT_VALUE)
SQUARES = [i * i for i in range(10)]

def parse(s):
    v = 0
    for ch in s:
        v = v * 10 + DIGIT_VALUE[ch]
    return v

def main():
    print(parse("12345") + parse("0042"), SQUARES[7], len(DIGIT_VALUE))

main()
''', 'digit_table')

    def test_bytes_set_is_the_only_table(self):
        # cruntime BTAB carries an ail_str value array: with no str in the program it used to fail in cc
        for name, line in (('folded', 'STOP = frozenset(b"an and are as at be".split())'),
                           ('literal', "STOP = {b'an', b'and', b'are', b'as', b'at', b'be'}")):
            with self.subTest(shape=name):
                self.same(line + '''
def count(line):
    n = 0
    for w in line.split():
        if w in STOP:
            n += 1
    return n

def main():
    print(count(b"we are at an inn and be merry"))

main()
''', 'bytes_set_' + name)

    def test_inline_set_of_str_keeps_the_general_path(self):
        # census dev/t400: once RANK_VALUES folds, the typed path reached `len(set(suits))` with
        # list[str] suits and handed cc an int table; it is refused by name now and the default build
        # takes the general path
        self.same('''
RANK_VALUES: dict[str, int] = {r: i for i, r in enumerate("23456789TJQKA", start=2)}

def analyze(cards: list[str]) -> tuple[int, bool]:
    suits = [c[1] for c in cards]
    return RANK_VALUES[cards[0][0]], len(set(suits)) == 1

def main() -> None:
    print(analyze(["AS", "KS"]), analyze(["TS", "KH"]))

main()
''', 'inline_set_str', modes=('default', 'unified'))

    def test_mutation_from_a_function_is_cpythons(self):
        self.same('''
NAMES = list("abc")
SEEN = set("x y".split())
TABLE = {}
for _i in range(5):
    TABLE[_i] = _i * _i

def add(x):
    NAMES.append(x)
    SEEN.add(x)
    TABLE[9] = 81

def main():
    add("d")
    print(NAMES, "d" in SEEN, len(SEEN), TABLE[3], TABLE[9], len(TABLE))

main()
''', 'mutation', modes=('default', 'unified'))

    def test_global_rebinding_is_cpythons(self):
        self.same('''
S = set("a b".split())

def reset():
    global S
    S = set("q".split())

def main():
    print("a" in S)
    reset()
    print("a" in S, "q" in S)

main()
''', 'rebind', modes=('default', 'unified'))

    def test_read_before_definition_is_cpythons(self):
        self.same('''
def has(w):
    return w in STOP

try:
    print(has("a"))
except NameError as e:
    print("NameError", e)
STOP = set("a b c".split())

def main():
    print(has("b"))

main()
''', 'before', modes=('default', 'unified'))

    def test_big_ints_in_the_constant(self):
        # int64 is the default (owner decision 2026-10-31): a static int beyond it is refused by name, at
        # the line the program wrote it on, in every build -- the fold does not hide it in a literal
        text = '''
BIG = {}
for _k in range(3):
    BIG[_k] = 2 ** 70 + _k

def get(k):
    return BIG[k]

def main():
    print(get(1), get(2) - get(0))

main()
'''
        with tempfile.TemporaryDirectory() as directory:
            for mode in MODES:
                with self.subTest(mode=mode):
                    built, exe = build(directory, text, 'big', mode)
                    self.assertNotEqual(built.returncode, 0)
                    self.assertIn(':4:15: int64 constant out of range: 1180591620717411303424',
                                  built.stdout + built.stderr)
                    self.assertFalse(exe.exists())


if __name__ == '__main__':
    unittest.main()
