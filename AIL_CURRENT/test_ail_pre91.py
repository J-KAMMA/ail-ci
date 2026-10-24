"""Non-BMP strings on the 16-bit general path.

The boxed general path stores strings as UTF-16 units.  A non-BMP chr() or
"%c"/format(..., "c") value is represented as a surrogate pair, so width,
indexing, slicing, iteration, comparison, containers, searching, padding and
printing agree with CPython.  Non-BMP string literals remain refused by name
on that path.  BMP, out-of-range and wrong-type behaviour is unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LITERAL_REFUSAL = 'a non-BMP string literal in the 16-bit v2 runtime'

BASIC = '''em = chr(0x1F600)
mu = chr(0x1D11E)
s = "a" + em + "b" + mu + "c"
print(s)
print(len(s), [ord(c) for c in s])
print(s[0], s[1], s[2], s[3], s[4], s[-1], s[-3])
print(repr(s[:]), repr(s[1:]), repr(s[:-1]), repr(s[1:4]), repr(s[1:4:2]))
print(repr(s[::-1]), repr(s[-1:-6:-1]), repr(s[::3]), repr(s[5:]), repr(s[9:]))
print(repr(s[4:2]), len(s[4:2]), s[4:2] == "")
print(repr(s[-2:-4:-1]), len(s[-2:-4:-1]))
print(repr(s[2:2]), len(s[2:2]))
print(repr(chr(0x10000)), repr(chr(0x10FFFF)))
print([s], (s,), {"k": chr(0x10FFFF)})
print(sorted([chr(0x10000), chr(0xFFFF), chr(0x1F600)]))
print("".join([s, "z"]))
'''
CARRIERS = '''class C:
    pass


def via_arg(n) -> None:
    t = chr(n)
    print(t, len(t), ord(t), repr(t))


def main() -> None:
    n = 0x1F600
    xs = [0x1F600]
    d = {"n": 0x10000}
    c = C()
    c.n = 0x10FFFF
    print(chr(n), chr(xs[0]), chr(d["n"]), chr(c.n))
    via_arg(n)
    print(chr(xs[0]) + "x")


main()
'''
BMP = '''print(chr(0), chr(0x7f), chr(0x80), chr(0xD7FF), chr(0xE000), chr(0xFFFF))
'''
OUT_OF_RANGE = '''for v in [-1, 0x110000, 0x1F600 + 0x100000]:
    try:
        print(chr(v))
    except Exception as e:
        print(type(e).__name__, e)
'''
WRONG_TYPE = '''for v in [65.0, "65", None, [65]]:
    try:
        print(chr(v))
    except Exception as e:
        print(type(e).__name__, e)
'''
SLICE_REVERSE = '''s = "a" + chr(0x1F600) + "bc"
for a, b, c in [(4, 1, -1), (3, 1, -1), (1, 4, 2), (0, 4, 3), (-1, -5, -2), (3, 3, -1), (2, 0, -2)]:
    t = s[a:b:c]
    print(repr(t), len(t), t == "")
print(repr(s[3:1]), len(s[3:1]), s[3:1] == "")
print(repr(s[2:1]), repr(s[1:3]))
def sl(s, a, b) -> None:
    t = s[a:b]
    print(repr(t), t == "", len(t), bool(t))
    print(repr(t + "x"), len(t + "x"))


sl("abcdef", 4, 2)
sl("abcdef", 10, 2)
sl("abcdef", -2, -4)
sl("", 0, 0)
'''
PAD = '''em = chr(0x1F600)
s = em + "!"
for w in (1, 2, 3, 4, 5):
    print(repr(s.ljust(w)), len(s.ljust(w)))
    print(repr(s.rjust(w)), len(s.rjust(w)))
    print(repr(s.center(w)), len(s.center(w)))
    print(repr(s.zfill(w)), len(s.zfill(w)))
print(repr(("-" + em).zfill(4)), len(("-" + em).zfill(4)))
print(repr(("+" + em + "!").zfill(5)), len(("+" + em + "!").zfill(5)))
print(repr((em + "!").ljust(4, em)), len((em + "!").ljust(4, em)))
print(repr((em + "!").center(4, em)), len((em + "!").center(4, em)))
for w in (1, 2, 4, 5):
    print(repr("%*s" % (w, s)), len("%*s" % (w, s)))
    print(repr("{:>{w}}".format(s, w=w)), len("{:>{w}}".format(s, w=w)))
    print(repr(f"{s:^{w}}"), len(f"{s:^{w}}"))
print(repr("%.1s" % s), len("%.1s" % s))
print(repr("%.2s" % s), len("%.2s" % s))
print(repr("{:.1}".format(s)), len("{:.1}".format(s)))
print(repr("{:.2}".format(s)), len("{:.2}".format(s)))
u = "a" + chr(0x10000) + "b"
print(repr("%4s" % u), len("%4s" % u))
print(repr("%.2s" % u), len("%.2s" % u))
'''
PERCENT_C = '''em = chr(0x1F600)
mu = chr(0x1D11E)
print(repr("%c" % 0), repr("%c" % 0xFFFF), repr("%c" % 0x10000))
print(repr("%c" % 0x1F600), repr("%c" % 0x10FFFF), repr("%c" % em))
print(repr("%5c" % 0x1F600), repr("%-5c" % em), repr("%5c" % 65))
print(repr("%c" % "A"), repr("%c" % mu))
print(repr(format(0x1F600, "c")), repr(format(0x10FFFF, "c")))
print(repr(format(65, "c")), repr(format(0x10000, "c")))
for v in (-1, 0x110000):
    try:
        print("%c" % v)
    except Exception as e:
        print(type(e).__name__, e)
for v in ("ab", "", 65.0, None):
    try:
        print("%c" % v)
    except Exception as e:
        print(type(e).__name__, e)
for v in (-1, 0x110000):
    try:
        print(format(v, "c"))
    except Exception as e:
        print(type(e).__name__, e)
'''
ITERATION = '''em = chr(0x1F600)
mu = chr(0x1D11E)
s = "a" + em + "b" + mu
print(list(s), [ord(c) for c in s], "".join(reversed(s)))
print([c for c in s])
print([(i, c) for i, c in enumerate(s)])
print(list(zip(s, range(10))))
print(list(map(ord, s)))
print(list(filter(lambda c: ord(c) > 100, s)))
total = ""
for c in s:
    total += c
print(total, len(total))
print(sorted(s), max(s) == mu, min(s) == "a")
'''
SEARCH = '''em = chr(0x1F600)
mu = chr(0x1D11E)
s = "a" + em + "b" + mu + "c" + em
print(s.find(em), s.find(em, 2), s.rfind(em), s.rfind(em, 0, 3))
print(s.count(em), s.count(""), em in s, mu in s)
print(s.startswith("a" + em), s.endswith(mu + "c" + em))
print(s.startswith(em, 1), s.endswith("b", 0, 3))
print(s.index(mu), s.rindex(em))
print(s.find(""), s.rfind(""), s.count(""), s.find("", 2), s.rfind("", 2, 4))
print(s.split(em), s.rsplit(em), s.split(em, 1))
print(s.partition(em), s.rpartition(em))
print("-".join([em, mu, "x"]), em.join([mu, "x"]))
print(s.replace(em, "X"), s.replace(em, mu), s.replace(em, ""))
print(s.strip(em), s.lstrip(em), s.rstrip(em))
'''
COMPARE = '''em = chr(0x1F600)
mu = chr(0x1D11E)
a = "a" + em
b = "a" + mu
print(a == b, a < b, b > a, em < mu, em == chr(0x1F600))
xs = [mu, em, "a", "A", em + "x"]
print(sorted(xs))
print(sorted(xs, reverse=True))
d = {em: 1, mu: 2, "a": 3}
print(d[em], d[mu], len(d), list(d))
print(em in d, mu in d, "a" in d)
'''
REPR = '''em = chr(0x1F600)
mu = chr(0x1D11E)
print(repr(em), repr("a" + em + "b"), repr(mu))
print([em, mu], (em, mu), {em: 1, mu: 2})
print(str([em]), str((mu,)))
print(repr("x" + chr(0x10FFFF) + "y"))
print(repr(["a" + chr(0x10000)]), repr({chr(0x10FFFF): chr(0x1F600)}))
'''


def _run_cpython(directory, text, name):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True,
                          env=dict(os.environ, PYTHONUTF8='1'), timeout=120)


def _compile(directory, text, name, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Pre91Tests(unittest.TestCase):
    def refused_literal(self, general):
        text = "print('\\U0001f600')\n"
        with tempfile.TemporaryDirectory(prefix='ail-pre91-') as directory:
            built, exe = _compile(directory, text, 'literal', general)
            self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn(LITERAL_REFUSAL, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def compare(self, text, name, general, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre91-') as directory:
            want = _run_cpython(directory, text, name)
            self.assertEqual(want.returncode, rc, want.stderr.decode('utf-8', 'replace'))
            built, exe = _compile(directory, text, name, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
            self.assertEqual(got.returncode, rc, got.stderr.decode('utf-8', 'replace'))
            self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want.stdout.replace(b'\r\n', b'\n'))

    def test_non_bmp_literal_still_refused_on_general_path(self):
        self.refused_literal(True)
        self.compare("print('\\U0001f600')\n", 'literal_default', False)

    def test_non_bmp_chr_matches_cpython(self):
        for general in (True, False):
            self.compare(BASIC, 'basic', general)
            self.compare(CARRIERS, 'carriers', general)

    def test_bmp_and_out_of_range_unchanged(self):
        for general in (True, False):
            self.compare(BMP, 'bmp', general)
            self.compare(OUT_OF_RANGE, 'out_of_range', general)
            self.compare(WRONG_TYPE, 'wrong_type', general)

    def test_slice_with_start_after_stop(self):
        for general in (True, False):
            self.compare(SLICE_REVERSE, 'slice_reverse', general)

    def test_code_point_widths(self):
        for general in (True, False):
            self.compare(PAD, 'pad', general)

    def test_percent_c_and_format_c(self):
        for general in (True, False):
            self.compare(PERCENT_C, 'percent_c', general)

    def test_iteration_and_reversed(self):
        for general in (True, False):
            self.compare(ITERATION, 'iteration', general)

    def test_search_split_and_join(self):
        for general in (True, False):
            self.compare(SEARCH, 'search', general)

    def test_compare_sort_and_containers(self):
        for general in (True, False):
            self.compare(COMPARE, 'compare', general)

    def test_repr(self):
        for general in (True, False):
            self.compare(REPR, 'repr', general)


if __name__ == '__main__':
    unittest.main()
