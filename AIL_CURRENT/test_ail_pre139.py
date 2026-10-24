"""pre139: a non-BMP chr() value on the general (16-bit v2) path, against CPython.

The general path stores strings as UTF-16 units. `chr(0x1F600)` used to die with an
internal error there, while the default build matched CPython. It now stores a
surrogate pair, and the point-based string operations (print/repr/len/ord/index/
slice/iterate/compare/find/count/startswith/endswith/pad/replace) see one code point.
A non-BMP *literal* stays refused by name in this runtime; only the value reaching
chr() at run time is handled. Format width/precision, expandtabs and %c/%s also
count code points, and len()/index keep the O(1) path for backings with no pair.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
sys.path.insert(0, str(ROOT))


def surface(text):
    import ail_syntax
    return ail_syntax.fold_constants(ail_syntax.python_surface(text))


def build_general(directory, text, name):
    source, exe = Path(directory, name + '_g.ail'), Path(directory, name + '_g')
    source.write_text(surface(text), encoding='utf-8')
    env = dict(os.environ, AIL_IR='0', AIL_NO_CACHE='1', AIL_SURFACE='python')
    env.pop('AIL_NO_GENERAL', None)
    res = subprocess.run([sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only'],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe


def build_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_d')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0')
    env.pop('AIL_NO_GENERAL', None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax',
                          'python', '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe


TEXT = '''class Box:
    def __init__(self, v):
        self.v = v


def pick(xs, i):
    return xs[i]


def main():
    n = 0x1F600
    s = chr(n)
    print(s)
    print(len(s), ord(s), repr(s))
    xs = [n]
    print(chr(xs[0]))
    d = {"k": n}
    print(chr(d["k"]))
    b = Box(n)
    print(chr(b.v))
    print(chr(pick(xs, 0)))
    print([s], {"k": s}, (s,))
    print(s[0], s[-1], s[:], s[::-1])
    total = 0
    for c in s:
        total += ord(c)
    print(total, list(reversed(s)))
    print(s < chr(0x10FFFF), chr(0xFFFF) < chr(0x10000))
    print(s.find(s), s.count(s), s.startswith(s), s.endswith(s))
    print(s.ljust(3, "."), s.rjust(3, "."), s.center(3, "."))
    print(s.replace("", "-"))
    # widths and precision count code points, not UTF-16 units
    print(f"{s:>3}", len(f"{s:>3}"))
    print(f"{s:^4}", len(f"{s:^4}"))
    print("{:>3}".format(s), format(s, ">3"))
    mixed = "a" + s + "b"
    print(f"{mixed:^7}|", f"{mixed:.2}", len(f"{mixed:.2}"))
    # expandtabs advances one column per code point
    print(len((s + "\tx").expandtabs()), (s + "\tx").expandtabs())
    print(len((s + s + "\tx").expandtabs(4)))
    # %c accepts a one-code-point str (a surrogate pair is one character)
    print("%c" % s, "%3c|" % s, "%c" % 0x1F600)
    # len() and indexing stay exact on a large BMP string
    print(len("abcdefghij" * 20000), ("abcdefghij" * 20000)[-1])


main()
'''


class NonBmpChr(unittest.TestCase):
    def check(self, text, name, default):
        with tempfile.TemporaryDirectory() as d:
            res, exe = (build_default if default else build_general)(d, text, name)
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            src = Path(d, name + '_cpython.py')
            src.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, str(src)], cwd=d, capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], cwd=d, capture_output=True, timeout=300)
            self.assertEqual(got.stdout.decode('utf-8', 'replace'), want.stdout.decode('utf-8', 'replace'), name)
            self.assertEqual(got.returncode, want.returncode, (name, got.stderr[-500:]))

    def test_general_path(self):
        self.check(TEXT, 'pre139_g', default=False)

    def test_default_build(self):
        self.check(TEXT, 'pre139_d', default=True)


if __name__ == '__main__':
    unittest.main()
