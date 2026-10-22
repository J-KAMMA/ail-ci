"""Module-level set and dict tables on the typed path, each compared with CPython 3.12.

    STOP = {b"a", b"the"}        STOP: set[str] = {...}        WORDS = {"a", "b"}
    TABLE = {"x": 1, "y": 2}     PAIRS = {(0, 1), (2, 3)}      NAMES = {1: "one", 2: "two"}

read from any function (`in`, `for`, `len`, `d[k]`, `d.get`, `items / keys / values`, `sorted`, `sum`,
`min`, `max`, `any`, `all`). modtables.py builds the table once in the entry function and hands it down
as a hidden first parameter (one build; a table with bytes in it is a local of each reader instead).
Every program is built four ways -- the typed path alone (AIL_NO_GENERAL=1) and the default build, each
with AIL_IR=0 and AIL_IR=1 -- and its stdout and exit status must equal CPython's. The general (boxed)
path is also run on programs it can hold; it has no bytes literals, so a bytes table is refused there by
name. What could change a table or share it (`STOP.add(x)`, `T[k] = v`, `global`, `xs = STOP`,
`return STOP`, `f(STOP)`) and what would show CPython's hash order (a set of ints walked by `for`) is
refused by name.

M1  str sets: membership from nested calls, methods, recursion, defaults, comprehensions
    (also `frozenset({...})`, `set([...])` of a literal)
M2  str-keyed dicts: get, [], in, items / keys / values, insertion order
M3  other key and value kinds: int, str, float values; negative ints; duplicates; annotated tables
M4  int sets read in an order-free way
M5  bytes sets and dicts
M6  tuple keys, elements and values (lowered in the front end before the tuple pass)
M7  script shape: top-level code, sys.exit(main()), stdin
M8  refusals by name, and the program without a table is untouched
"""
import ast
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
PKG = ROOT / 'python' / 'pkg-v12'
ON_312 = sys.version_info[:2] == (3, 12)

MODES = ('typed', 'typed_ir', 'default', 'default_ir')


def build(directory, text, name, mode):
    """Compile `text` in one mode. Returns (completed process, executable path)."""
    source, exe = Path(directory, name + '.ail'), Path(directory, name + '_' + mode)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    env.pop('AIL_NO_GENERAL', None)
    env['AIL_IR'] = '1' if mode.endswith('_ir') else '0'
    if mode == 'general':
        command = [sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only']
    else:
        if mode.startswith('typed'):
            env['AIL_NO_GENERAL'] = '1'
        command = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                   '--syntax', 'python', '-o', exe.name]
    return subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def cpython(directory, text, name, stdin):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=120,
                          encoding='utf-8', input=stdin)


def c_text(text):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(PKG))
    import ail_syntax
    import pyc
    return pyc.to_c(ail_syntax.python_surface(text), strict=True, name='run', info={})


@unittest.skipUnless(ON_312, 'the expected output is CPython 3.12 behaviour')
class ModuleTables(unittest.TestCase):
    def same(self, text, name, modes=MODES, stdin='', general=False):
        """AIL's stdout and exit status equal CPython's in every mode (and, with `general`, on the
        general path too)."""
        with tempfile.TemporaryDirectory() as directory:
            expected = cpython(directory, text, name, stdin)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for mode in tuple(modes) + (('general',) if general else ()):
                with self.subTest(mode=mode):
                    built, exe = build(directory, text, name, mode)
                    self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300,
                                         encoding='utf-8', input=stdin)
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                     ran.stderr[-400:])

    def refused(self, text, name, words, mode='typed'):
        """The program is refused by name (no executable) in `mode`, and the message has every word."""
        with tempfile.TemporaryDirectory() as directory:
            built, exe = build(directory, text, name, mode)
            self.assertNotEqual(built.returncode, 0, 'expected a refusal')
            message = built.stdout + built.stderr
            self.assertIn('not in the subset', message)
            for word in words:
                self.assertIn(word, message)
            self.assertFalse(exe.exists())

    # ------------------------------------------------------------------ M1 str sets

    def test_str_set_nested_calls(self):
        self.same('''
STOP = {"a", "the", "of"}

def is_stop(w: str) -> bool:
    return w in STOP

def keep(ws: list[str]) -> list[str]:
    out: list[str] = []
    for w in ws:
        if not is_stop(w):
            out.append(w)
    return out

def count(ws: list[str]) -> int:
    return len(keep(ws)) * 10 + len(STOP)

def main() -> None:
    ws = ["the", "cat", "of", "a", "dog", "dog"]
    print(count(ws), len(keep(ws)), is_stop("zz"), is_stop("a"))
    print("a" not in STOP, "q" not in STOP)

main()
''', 'str_set_nested_calls', general=True)

    def test_str_set_walked_in_order_free_ways(self):
        self.same('''
STOP = {"a", "the", "of", "zebra"}

def main() -> None:
    print(len(STOP))
    for w in sorted(STOP):
        print(w)
    n = 0
    for w in STOP:
        n += len(w)
    print(n, "zebra" in STOP)

main()
''', 'str_set_walked', general=True)

    def test_more_reads_of_a_str_set_build_on_the_general_path(self):
        # min / sum / any / all / list / set over a set[str] are not on the typed path (a parameter has
        # the same limit); the default build falls back and must still equal CPython
        self.same('''
STOP = {"a", "the", "of", "zebra"}

def main() -> None:
    print(len(STOP), min(STOP), max(STOP), sorted(STOP))
    print(sum(len(w) for w in STOP), any(len(w) > 4 for w in STOP), all(len(w) > 0 for w in STOP))
    print(sorted([w for w in STOP if len(w) == 1]), ",".join(sorted(STOP)))
    print(len(set(STOP)), len(list(STOP)), len(STOP.copy()), len(sorted(STOP)))

main()
''', 'str_set_more', modes=('default', 'default_ir'), general=True)

    def test_str_set_methods_recursion_defaults(self):
        self.same('''
STOP = {"a", "the"}
LIM = {"x": 3, "y": 4}

class Counter:
    def __init__(self, n: int):
        self.n = n

    def hit(self, w: str) -> int:
        return (1 if w in STOP else 0) + LIM.get(w, 0) + self.n

def weight(w: str, k: int = 3) -> int:
    return k + (1 if w in STOP else 0)

def depth(ws: list[str], i: int) -> int:
    if i >= len(ws):
        return 0
    return (1 if ws[i] in STOP else 0) + depth(ws, i + 1)

def total(ws: list[str]) -> int:
    t = 0
    for w in ws:
        t += weight(w) + weight(w, 7)
    return t

def main() -> None:
    c = Counter(5)
    print(c.hit("a"), c.hit("x"), c.hit("q"))
    print(weight("a"), weight("b", 1), weight(w="the", k=0))
    print(depth(["a", "b", "the", "c", "a"], 0), total(["a", "x"]))

main()
''', 'str_set_methods_recursion_defaults', general=True)

    def test_recursive_entry_reads_the_table(self):
        self.same('''
STOP = {"a", "the"}

def solve(n: int) -> int:
    if n <= 0:
        return 0
    return (1 if "a" in STOP else 0) + solve(n - 1)

def main() -> None:
    print(solve(4))
    print(solve(0))

main()
''', 'recursive_entry', general=True)

    def test_table_is_built_once(self):
        text = '''
STOP = {"zebra", "yak"}

def f(w: str) -> int:
    return 1 if w in STOP else 0

def g(ws: list[str]) -> int:
    t = 0
    for w in ws:
        t += f(w)
    return t

def main() -> None:
    n = 0
    for i in range(100):
        n += g(["zebra", "dog"])
    print(n)

main()
'''
        c = c_text(text)
        literal = '"' + '""'.join('\\x%02X' % ord(ch) for ch in 'yak') + '"'
        self.assertEqual(c.count(literal), 1, 'the table is built in one place')
        self.assertRegex(c, r'int64_t f\(const ail_sset \*v_STOP, ail_str v_w\)')
        self.same(text, 'table_built_once', modes=('typed', 'default'))

    def test_set_operators_make_a_new_set(self):
        self.same('''
STOP = {"a", "the", "of"}

def extra(w: str) -> int:
    more = STOP | {w}
    both = STOP & {"a", "q"}
    return len(more) * 10 + len(both)

def main() -> None:
    print(extra("a"), extra("zz"), len(STOP))

main()
''', 'set_operators')

    def test_frozenset_and_set_of_a_literal(self):
        self.same('''
STOP = frozenset({"a", "the"})
WORDS = set(["x", "y", "x"])
EVEN = frozenset((2, 4, 6))

def f(w: str) -> int:
    return (1 if w in STOP else 0) + (10 if w in WORDS else 0) + len(WORDS)

def main() -> None:
    print(f("a"), f("x"), f("q"), 4 in EVEN, 5 in EVEN, len(EVEN), len(STOP))

main()
''', 'frozenset_tables')

    # ------------------------------------------------------------------ M2 dicts

    def test_str_dict_reads(self):
        self.same('''
TABLE = {"x": 1, "y": 2, "z": 30}

def score(k: str) -> int:
    return TABLE.get(k, -1) + (TABLE[k] if k in TABLE else 0)

def weighted() -> int:
    t = 0
    for k, v in TABLE.items():
        t += v * len(k)
    return t

def main() -> None:
    print(score("x"), score("q"), weighted(), len(TABLE), sum(TABLE.values()), max(TABLE.values()))
    for k, v in TABLE.items():
        print(k, v)
    for k in TABLE:
        print(k, TABLE[k])
    for k in sorted(TABLE):
        print(k)
    for k in TABLE.keys():
        print(k)
    for v in TABLE.values():
        print(v)
    print(sorted(TABLE, key=lambda k: -TABLE[k])[0], "y" in TABLE, "w" not in TABLE)

main()
''', 'str_dict_reads', general=True)

    def test_two_tables_and_a_threaded_chain(self):
        self.same('''
STOP = {"a", "the"}
LIM = {"x": 3, "y": 4}

def score(w: str) -> int:
    return LIM.get(w, 0) + (10 if w in STOP else 0)

def total(ws: list[str]) -> int:
    t = 0
    for w in ws:
        t += score(w)
    return t

def outer(ws: list[str]) -> int:
    return total(ws) + len(STOP) + len(LIM)

def main() -> None:
    print(total(["a", "x", "y", "q", "the"]), score("y"), outer(["x"]))

main()
''', 'two_tables_chain', general=True)

    # ------------------------------------------------------------------ M3 kinds

    def test_other_key_and_value_kinds(self):
        self.same('''
NAMES = {1: "one", 2: "two", 10: "ten", -5: "neg"}
CODES = {"a": "alpha", "b": "beta"}
RATE = {"x": 1.5, "y": 2.25}
SQ = {1: 1, 2: 4, 3: 9, 3: 99}

def show(i: int) -> str:
    return NAMES.get(i, "?") + CODES.get("a", "-")

def rate(k: str) -> float:
    return RATE[k] * 2.0

def main() -> None:
    print(show(1), show(5), show(-5), rate("y"), SQ[3], SQ.get(9, 0), len(SQ))
    for k in NAMES:
        print(k, NAMES[k])
    for k, v in RATE.items():
        print(k, v)

main()
''', 'other_kinds', general=True)

    def test_annotated_tables_and_duplicates(self):
        self.same('''
STOP: set[str] = {"a", "the", "a"}
TABLE: dict[str, int] = {"x": 1, "y": 2, "x": 9}
LOW = {-3, 0, 7, 7}

def f(w: str) -> int:
    return TABLE.get(w, 0) + (1 if w in STOP else 0)

def main() -> None:
    print(f("x"), f("a"), f("y"), len(STOP), len(TABLE), len(LOW), -3 in LOW)
    for v in sorted(LOW):
        print(v)

main()
''', 'annotated_duplicates', general=True)

    # ------------------------------------------------------------------ M4 int sets

    def test_int_set_order_free(self):
        self.same('''
PRIMES = {2, 3, 5, 7, 11, 13, 100, 64, 33}

def is_prime(n: int) -> bool:
    return n in PRIMES

def main() -> None:
    c = 0
    for i in range(20):
        if is_prime(i):
            c += i
    print(c, sorted(PRIMES)[1], max(PRIMES), sum(PRIMES), len(PRIMES), min(PRIMES))
    print(sum(x * x for x in PRIMES), any(x > 99 for x in PRIMES), all(x > 1 for x in PRIMES))
    for p in sorted(PRIMES):
        print(p)

main()
''', 'int_set_order_free', general=True)

    # ------------------------------------------------------------------ M5 bytes

    def test_bytes_set_and_dict(self):
        self.same('''
STOP = {b"a", b"the", b"\\x00z"}
D = {b"k": 7, b"j": 9}

def is_stop(w: bytes) -> bool:
    return w in STOP

def look(w: bytes) -> int:
    n = 0
    if is_stop(w):
        n += 100
    return n + D.get(w, 0) + (D[w] if w in D else 0)

def total(ws: list[bytes]) -> int:
    t = 0
    for w in ws:
        t += look(w)
    return t

def main() -> None:
    print(total([b"a", b"k", b"j", b"zz", b"the", b"\\x00z"]), len(STOP), len(D), b"j" in D, b"q" in STOP)
    n = 0
    for w in STOP:
        n += len(w)
    for k in D:
        n += D[k]
    print(n)

main()
''', 'bytes_tables')

    def test_bytes_table_on_the_general_path(self):
        # (refused by name until the general path gained bytes; now it must match CPython)
        text = '''
STOP = {b"a", b"the"}

def f(w: bytes) -> int:
    return 1 if w in STOP else 0

def main() -> None:
    print(f(b"a"), f(b"x"))

main()
'''
        with tempfile.TemporaryDirectory() as directory:
            built, exe = build(directory, text, 'bytes_general', 'general')
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            want = cpython(directory, text, 'bytes_general', '')
            self.assertEqual((ran.returncode, ran.stdout), (want.returncode, want.stdout))

    # ------------------------------------------------------------------ M6 tuples

    def test_tuple_tables(self):
        self.same('''
PAIRS = {(0, 1), (2, 3), (-1, 5)}
GRID = {(0, 1): 5, (1, 0): 7}
LABEL = {"a": (1, 2), "b": (3, 4)}
WORDS = {("x", 1), ("y", 2)}

def has(a: int, b: int) -> bool:
    return (a, b) in PAIRS

def g(a: int, b: int) -> int:
    return GRID.get((a, b), 0)

def lab(k: str) -> int:
    t = LABEL[k]
    return t[0] * 10 + t[1]

def main() -> None:
    n = 0
    for i in range(-2, 5):
        for j in range(0, 6):
            if has(i, j):
                n += i * 10 + j
    print(n, len(PAIRS), g(0, 1), g(1, 1), len(GRID), lab("a"), lab("b"), ("y", 2) in WORDS, ("y", 3) in WORDS)

main()
''', 'tuple_tables')

    # ------------------------------------------------------------------ M7 script shapes

    def test_script_with_top_level_code_and_stdin(self):
        self.same('''
import sys

STOP = {"a", "the"}
LIM = {"x": 3}

def keep(w: str) -> int:
    return LIM.get(w, 1) if w not in STOP else 0

def main() -> int:
    t = 0
    for line in sys.stdin:
        for w in line.split():
            t += keep(w)
    print(t)
    return 0

sys.exit(main())
''', 'script_stdin', stdin='the x cat a\nx x dog\n', general=True)

    def test_top_level_statements_read_the_table(self):
        self.same('''
STOP = {"a", "the"}

def keep(w: str) -> bool:
    return w not in STOP

words = ["a", "dog", "the", "cat"]
n = 0
for w in words:
    if keep(w):
        n += 1
print(n, len(STOP), "a" in STOP)
''', 'script_top_level')

    # ------------------------------------------------------------------ M8 refusals

    def test_changes_are_refused_by_name(self):
        for name, body, words in (
                ('add', 'STOP.add(w)', ['STOP.add(...)', 'change a table every other function reads']),
                ('update', 'STOP.update([w])', ['STOP.update(...)']),
                ('setitem', 'T[w] = 5', ['T[w]', 'change a table every other function reads']),
                ('delitem', 'del T[w]', ['T[w]']),
                ('global', 'global STOP\n    STOP = {w}', ['global STOP'])):
            text = '''
STOP = {"a", "the"}
T = {"a": 1}

def f(w: str) -> int:
    %s
    return 1

def main() -> None:
    print(f("z"), len(STOP), len(T))

main()
''' % body
            with self.subTest(change=name):
                self.refused(text, 'change_' + name, words)

    def test_sharing_is_refused_by_name(self):
        for name, define, setup, words in (
                ('alias', '', 's = STOP\n    s.add("q")\n    print(len(STOP))', ['`s = STOP`', 'second reference']),
                ('return', 'def give() -> set[str]:\n    return STOP\n\n', 'print(len(give()))', ['`return STOP`']),
                # handed to a function that only reads it, the table is built (test_ail_typed_blockers2 T3)
                ('argument', 'def show(s: set[str]) -> int:\n    s.add("x")\n    return len(s)\n\n',
                 'print(show(STOP))', ['`show(STOP)`']),
                ('display', '', 'xs = [STOP]\n    print(len(xs))', ['`[STOP]`'])):
            text = '''
STOP = {"a", "the"}

%sdef main() -> None:
    %s

main()
''' % (define, setup)
            with self.subTest(share=name):
                self.refused(text, 'share_' + name, words)

    def test_int_set_walked_in_hash_order_is_refused(self):
        for name, use in (('for', 'for x in PRIMES:\n        print(x)'),
                          ('list', 'print(len(list(PRIMES)), list(PRIMES)[0])'),
                          ('comprehension', 'print([x for x in PRIMES][0])')):
            text = '''
PRIMES = {2, 3, 5, 7, 11, 64, 33}

def main() -> None:
    %s

main()
''' % use
            with self.subTest(use=name):
                self.refused(text, 'hash_order_' + name, ['hash order', 'sorted(PRIMES)'])

    def test_nested_def_and_module_level_change_are_refused(self):
        self.refused('''
STOP = {"a", "the"}

def f(w: str) -> int:
    def inner(x: str) -> int:
        return 1 if x in STOP else 0
    return inner(w)

def main() -> None:
    print(f("a"))

main()
''', 'nested_def', ['nested def', "'STOP'"])
        self.refused('''
STOP = {"a", "the"}
STOP.add("zz")

def f(w: str) -> int:
    return 1 if w in STOP else 0

def main() -> None:
    print(f("zz"))

main()
''', 'module_level_change', ['changes at module level', "'STOP'"])

    def test_tables_that_are_not_literals_keep_their_refusal(self):
        for name, table in (('mixed', 'STOP = {"a", 1}'), ('empty', 'STOP = {}'),
                            ('bool', 'STOP = {"a": True}'), ('floats', 'STOP = {1.5, 2.5}'),
                            ('computed', 'STOP = {w for w in ["a"]}')):
            text = '''
%s

def f(w: str) -> int:
    return 1 if w in STOP else 0

def main() -> None:
    print(f("a"))

main()
''' % table
            with self.subTest(table=name):
                self.refused(text, 'not_literal_' + name, ["'STOP'", 'build it in main()'] if name not in ('computed', 'empty') else [])

    def test_a_parameter_with_the_tables_name_is_its_own(self):
        self.same('''
STOP = {"a", "the"}

def f(w: str, STOP: set[str]) -> int:
    return 1 if w in STOP else 0

def main() -> None:
    print(f("a", {"a"}), f("a", {"b"}), len(STOP))

main()
''', 'own_parameter', modes=('typed', 'default'))

    def test_a_program_without_a_table_is_untouched(self):
        sys.path.insert(0, str(PKG))
        import modtables
        text = 'LIMIT = 3\nNAMES = ["a", "b"]\n\ndef f(x: int) -> int:\n    return x + LIMIT\n\nprint(f(1))\n'
        self.assertIs(modtables.rewrite_text(text), text)
        tree = ast.parse(text)
        before = ast.dump(tree)
        modtables.rewrite(tree, ValueError)
        self.assertEqual(ast.dump(tree), before)

    def test_reference_card_names_the_feature(self):
        card = (ROOT / 'AIL_REFERENCE.md').read_text(encoding='utf-8')
        self.assertLessEqual(len(card), 3500)
        self.assertRegex(card, r'STOP = \{')


if __name__ == '__main__':
    unittest.main()
