"""Typed-path class fields that hold str and lists (job fcclass1), against CPython.

A field set in `__init__` from a list literal of objects (`self.toks = [Tok(...)]`) is a `list[Tok]` field, and
an unannotated empty `self.xs = []` takes the element kind its own class's methods append to it: a str literal or
f-string makes it `list[str]`, a constructor call `X(...)` makes it `list[X]`; anything else keeps it `list[int]`
as before. A field the program gives a second kind is refused by name and the general path runs the program.

T1  fixed programs on the typed path alone (AIL_NO_GENERAL=1) print what CPython prints: list[X] from a literal,
    empty str / object lists filled by methods, an object mutated through the list, fields reassigned in a loop,
    an empty list field, a str field with code points above U+FFFF
T2  the same programs through the whole pipeline with AIL_UNIFIED_FORCE=1 match CPython, or (a str literal above
    U+FFFF, which the 16-bit general runtime lacks) stop loudly at build time
T3  refusals by name on the typed path, and the whole default pipeline still equals CPython: a str field
    assigned an int, a str-list field appended an int, a field aliased then mutated
T4  ints beyond int64 in an int field and an int-list field stop loudly (OverflowError, non-zero exit)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None


def build(directory, text, name, typed_only=True, force=False):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_t')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if typed_only:
        env['AIL_NO_GENERAL'] = '1'
    if force:
        env['AIL_UNIFIED_FORCE'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax',
                          'python', '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                         env=env)
    return res, exe


def run_cpython(directory, text, name, args=()):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source), *args], capture_output=True, text=True, timeout=300,
                          encoding='utf-8')


def run_exe(exe, args=()):
    return subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=300, encoding='utf-8')


FIXED = {}

FIXED['olist_literal'] = '''class Tok:
    def __init__(self, t: str, n: int):
        self.t = t
        self.n = n


class T:
    def __init__(self, text: str):
        self.src = text
        self.toks = [Tok("", 0)]
        self.first = [Tok("a", 1), Tok("b", 2)]

    def run(self):
        for w in self.src.split():
            self.toks.append(Tok(w, len(w)))


def main():
    t = T("ab c def")
    t.toks.pop()
    t.run()
    for k in t.toks:
        print(k.t, k.n)
    print(len(t.first), t.first[1].t)


main()
'''

FIXED['empty_filled'] = '''class P:
    def __init__(self, x: int):
        self.x = x
        self.tags = []

    def tag(self, i: int):
        self.tags.append(f"t{i}")


class W:
    def __init__(self):
        self.ps = []
        self.names = []
        self.ints = []

    def add(self, x: int):
        self.ps.append(P(x))
        self.names.append("p")
        self.ints.append(x)


def main():
    w = W()
    print(len(w.ps), w.names, w.ints)
    for i in range(4):
        w.add(i)
    for i in range(len(w.ps)):
        w.ps[i].x += 10
        w.ps[i].tag(i)
    w.ps[1].tag(9)
    for p in w.ps:
        p.x *= 2
    print([p.x for p in w.ps], [len(p.tags) for p in w.ps], w.ps[1].tags, w.names, w.ints)


main()
'''

FIXED['nested_frames'] = '''class FF:
    def __init__(self, q: str):
        self.q = q
        self.depths = [0]


class T:
    def __init__(self):
        self.frames = [FF("")]


def main():
    t = T()
    t.frames.append(FF("x"))
    t.frames[-1].depths.append(3)
    f = t.frames[0]
    f.q = "changed"
    print(len(t.frames), t.frames[-1].q, t.frames[-1].depths, t.frames[0].q)


main()
'''

FIXED['loop_reassign'] = '''import sys


class Q:
    def __init__(self, v: int):
        self.v = v


class S:
    def __init__(self):
        self.s = ""
        self.xs = [0]
        self.fs = [0.5]
        self.ws = []
        self.os = [Q(0)]

    def step(self, i: int):
        self.s = "v" + str(i)
        self.xs = [i, i + 1, i + 2]
        self.fs = [1.5, 2.5]
        self.ws = ["a", self.s]
        self.os = [Q(i), Q(i + 1)]
        self.ws.append("z")


def main():
    n = int(sys.argv[1])
    st = S()
    for i in range(n):
        st.step(i)
    print(st.s, st.xs, st.fs, st.ws, st.os[1].v)


main()
'''

FIXED['empty_fields'] = '''class E2:
    def __init__(self, k: str):
        self.k = k


class E:
    def __init__(self):
        self.xs = []
        self.ss: list[str] = []
        self.fs: list[float] = []
        self.os = []

    def add(self):
        self.os.append(E2("k"))


def main():
    e = E()
    print(e.xs, e.ss, e.fs, len(e.os), len(e.xs) == 0)
    e.add()
    print(len(e.os), e.os[0].k)
    e.xs.append(3)
    print(e.xs)


main()
'''

FIXED['astral_str'] = '''class U:
    def __init__(self, s: str):
        self.s = s
        self.parts = [s]

    def grow(self):
        self.s = self.s + "\\U0001F600"
        self.parts.append(self.s[-1])


def main():
    u = U("a\\U0001D11Eb")
    u.grow()
    print(u.s, len(u.s), u.s[1], u.parts, len(u.parts[1]), ord(u.s[-1]))
    print(u.s.upper(), u.s[::-1])


main()
'''

ARGS = {'loop_reassign': ('2000',)}
ASTRAL = {'astral_str'}

REFUSED = {}

REFUSED['str_then_int'] = ('''class M:
    def __init__(self):
        self.v = ""

    def set(self):
        self.v = 3


def main():
    m = M()
    m.set()
    print(m.v)


main()
''', 'M.v')

REFUSED['slist_then_int'] = ('''class M:
    def __init__(self):
        self.v = []

    def a(self):
        self.v.append("s")


def main():
    m = M()
    m.a()
    m.v.append(4)
    print(m.v)


main()
''', 'str')

REFUSED['alias_mutate'] = ('''class Box:
    def __init__(self):
        self.items = []
        self.name = ""

    def fill(self):
        self.items.append("a")
        self.name = "box"


def main():
    b = Box()
    b.fill()
    a = b.items
    a.append("b")
    n = b.name
    b.name = b.name + "!"
    print(b.items, a, n, b.name)


main()
''', 'second reference')

BIG = '''class N:
    def __init__(self):
        self.n = 1
        self.xs = [1]


def main():
    b = N()
    for i in range(70):
        b.n = b.n * 3
        b.xs.append(b.xs[-1] * 3)
    print(b.n, b.xs[-1])


main()
'''


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class FieldKinds(unittest.TestCase):
    def test_t1_typed_alone(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in FIXED.items():
                with self.subTest(name=name):
                    expected = run_cpython(d, text, name, ARGS.get(name, ()))
                    res, exe = build(d, text, name)
                    self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                    got = run_exe(exe, ARGS.get(name, ()))
                    self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout))

    def test_t2_unified_force(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in FIXED.items():
                with self.subTest(name=name):
                    expected = run_cpython(d, text, name, ARGS.get(name, ()))
                    res, exe = build(d, text, name + '_f', typed_only=False, force=True)
                    if name in ASTRAL:
                        if res.returncode:
                            self.assertIn("non-BMP", res.stderr)
                            continue
                    self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                    got = run_exe(exe, ARGS.get(name, ()))
                    self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout))

    def test_t3_refused_by_name(self):
        with tempfile.TemporaryDirectory() as d:
            for name, (text, needle) in REFUSED.items():
                with self.subTest(name=name):
                    res, _ = build(d, text, name)
                    self.assertNotEqual(res.returncode, 0)
                    self.assertIn(needle, res.stderr)
                    expected = run_cpython(d, text, name)
                    for force in (False, True):
                        res, exe = build(d, text, name + ('_f' if force else '_d'), typed_only=False, force=force)
                        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                        got = run_exe(exe)
                        self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout))

    def test_t4_beyond_int64_stops(self):
        with tempfile.TemporaryDirectory() as d:
            for force in (False, True):
                with self.subTest(force=force):
                    res, exe = build(d, BIG, 'big%d' % force, typed_only=False, force=force)
                    self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                    got = run_exe(exe)
                    self.assertNotEqual(got.returncode, 0)
                    self.assertIn('OverflowError', got.stderr)
                    self.assertEqual(got.stdout, '')


if __name__ == '__main__':
    unittest.main()
