"""Python-syntax reach, s8: Optional values beyond scalar locals.

O1  An unannotated helper whose returns are `None` and one int is inferred `int | None`; callers
    narrow it with `is None` / `is not None`, print it (`None`), and the 30-digit probe compares
    before converting so the int64 default never overflows.
O2  `d.get(k)` with one argument on a dict of scalars is a flag + value pair: hit and miss, `is
    None` / `is not None`, `print`, bool and float values.
O3  `xs = [None] * n` rows become a list of rows plus a present bit: setting a row, appending to
    it after an `is None` test, `print`, and growing the list with `.append([])`.
O4  A loop variable that is also an Optional local (`for a in rows:` after `a = f()`) stores
    present values into the value half and marks the flag each iteration.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None


PARSE = '''import sys


def parse(s, lo, hi):
    if not s or not all('0' <= ch <= '9' for ch in s):
        return None
    if len(s) > 18:
        return None
    v = int(s)
    if v < lo or v > hi:
        return None
    return v


def main():
    for s in ["", "abc", "5", "123456789012345678901234567890"]:
        print(parse(s, 0, 100))
    n = parse("5", 0, 100)
    t = parse("7", 0, 100)
    if n is None or t is None:
        print("bad")
        return 1
    print(n + t)
    return 0


sys.exit(main())
'''

DICT_GET = '''def main():
    d = {"a": 10, "b": 20}
    v = d.get("a")
    if v is None:
        print("miss")
    else:
        print(v + 1)
    w = d.get("z")
    if w is not None:
        print(w)
    else:
        print("none")
    print(d.get("b"))
    flags = {1: True, 2: False}
    t = flags.get(1)
    if t is None:
        print("missing")
    else:
        print(t)

main()
'''

SLOTS = '''def main():
    xs = [None] * 3
    for i in range(3):
        if xs[i] is None:
            xs[i] = [i]
        else:
            xs[i].append(i)
    for i in range(3):
        if xs[i] is not None:
            print(xs[i])
    ys = [None] * 2
    ys[1] = [7]
    if ys[0] is None:
        print("empty")
    if ys[1] is not None:
        print(ys[1])
    adj = [None] * 2
    adj.append([])
    if adj[2] is not None:
        adj[2].append(5)
    print(len(adj))
    if adj[2] is not None:
        print(adj[2])


main()
'''

UNLOWERED = '''def isabsent(v):
    return v is None


def main():
    a = [None] * 2
    print(a[0])
    a[1] = [9]
    print(a[1])
    b = [None] * 2
    print(b[0] == None)
    print(bool(b[0]))
    c = [None] * 2
    row = c[0]
    print(row is None)
    try:
        row.append(3)
        print("appended")
    except AttributeError:
        print("attribute-error")
    d = [None] * 2
    print(isabsent(d[0]))
    d[0] = [1]
    print(isabsent(d[0]))
    e = [None] * 3
    e[1] = [5]
    del e[0]
    print(len(e))
    for i in range(len(e)):
        print(e[i] is None, e[i])


main()
'''

SLOT_VALUES = '''def main():
    xs = [None] * 3
    xs[1] = [1]
    a = xs[0] is None
    b = xs[1] is not None
    c = xs[2] is None or xs[0] is None
    print(a, b, c)
    print(xs[0] is None)
    ys = [None] * 1
    ys[0] = [1]
    ys.append(None)
    print(len(ys), ys[-2] is None, ys[-1] is None)


main()
'''

UNSAFE_ROWS = '''G = None


def setup():
    global G
    G = [None] * 2
    G[0] = [1]


def read():
    print(G[1])
    print(len(G))


def idx():
    print("idx")
    return 0


def non_simple():
    xs = [None] * 3
    xs[idx()] = [1]
    if xs[0] is not None:
        print(xs[0])


def chained():
    xs = [None] * 3
    ys = None
    xs[0] = ys = [4]
    if xs[0] is None:
        print("none")
    else:
        print(xs[0], ys)


setup()
read()
non_simple()
chained()
'''

OPTIONAL_LOOP = '''def parse(s):
    if s == "":
        return None
    return int(s)


def main():
    total = 0
    for x in ["1", "2", ""]:
        a = parse(x)
        if a is None:
            continue
        total += a
    for a in [3, 4]:
        total += a
    print(total)


main()
'''


def build_source(tmp, name, source, flags=()):
    exe = Path(tmp) / name
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '--strict', *flags, '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def build_probe(tmp, name, source, unified, flags=()):
    exe = Path(tmp) / (name + ('_unified' if unified else '_default'))
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    env.pop('AIL_NO_GENERAL', None)
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', *flags, '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def run(exe, args=(), stdin=None):
    return subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=120,
                          input=stdin)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class PyreachOptRet(unittest.TestCase):
    def _typed(self, name, text, expected):
        with tempfile.TemporaryDirectory(prefix='ail-s8-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            reference = subprocess.run([sys.executable, str(source)],
                                       capture_output=True, text=True, timeout=120)
            self.assertEqual(reference.stdout, expected, name)
            result, exe = build_source(tmp, name, source)
            self.assertEqual(result.returncode, 0, (name, result.stderr[-3000:]))
            got = run(exe)
            self.assertEqual(got.returncode, reference.returncode, name)
            self.assertEqual(got.stdout, expected, name)
            for unified in (False, True):
                result, exe = build_probe(tmp, name, source, unified)
                self.assertEqual(result.returncode, 0, (name, unified, result.stderr[-3000:]))
                got = run(exe)
                self.assertEqual(got.returncode, reference.returncode, (name, unified))
                self.assertEqual(got.stdout, expected, (name, unified))

    def _matches_cpython(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-s8r-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            reference = subprocess.run([sys.executable, str(source)],
                                       capture_output=True, text=True, timeout=120)
            for unified in (False, True):
                result, exe = build_probe(tmp, name, source, unified)
                self.assertEqual(result.returncode, 0, (name, unified, result.stderr[-3000:]))
                got = run(exe)
                self.assertEqual(got.returncode, reference.returncode, (name, unified))
                self.assertEqual(got.stdout, reference.stdout, (name, unified))

    def test_unlowered_row_uses_keep_cpython_semantics(self):
        self._matches_cpython('unlowered', UNLOWERED)

    def test_unannotated_int_or_none_return(self):
        self._typed('parse', PARSE, 'None\nNone\n5\nNone\n12\n')

    def test_one_argument_dict_get(self):
        self._typed('dict_get', DICT_GET, '11\nnone\n20\nTrue\n')

    def test_none_slots_with_present_bit(self):
        self._typed('slots', SLOTS, '[0]\n[1]\n[2]\nempty\n[7]\n3\n[5]\n')

    def test_slot_guards_in_values_and_append_none(self):
        self._typed('slot_values', SLOT_VALUES, 'True True True\nTrue\n2 False True\n')

    def test_unsafe_row_shapes_refuse_or_fall_back(self):
        self._matches_cpython('unsafe_rows', UNSAFE_ROWS)

    def test_optional_loop_variable_reused(self):
        self._typed('optloop', OPTIONAL_LOOP, '10\n')


if __name__ == '__main__':
    unittest.main()
