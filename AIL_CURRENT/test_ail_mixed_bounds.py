"""Indexes in a mixed-mode typed clone are checked, and raise CPython's IndexError (uncaught: exit 1, the output
before it intact).

The clone of a numeric function (pymix.py, called from boxed code) took its list arguments as a bare pointer and a
length and indexed them without a check: `risky([1, 2, 3], 9)` read past the list and printed garbage (memory
unsafety as well as a wrong answer). pyboxed2 now compiles a clone with the checked-array flag, as the other
typed entry points have it. Each program is built by pyc.py under AIL_IR=1 and AIL_IR=0, must contain a clone
(`_mix0.c`; the float-list and str programs run boxed and only show the same answers), and must print what CPython prints with CPython's exit status. A second class builds the same programs
with AddressSanitizer + UBSan (the program's C compiled by hand with -fsanitize) and runs them.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = str(ROOT / 'python' / 'pkg-v12' / 'pyc.py')

PROGRAMS = {
    'list_positive': '''
def risky(xs: list[int], i: int) -> int:
    return xs[i]

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(risky([1, 2, 3], 1))
    print(risky([1, 2, 3], 9))
    print("never")
main()
''',
    'list_negative': '''
def risky(xs: list[int], i: int) -> int:
    return xs[i]

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(risky([1, 2, 3], -1), risky([1, 2, 3], -3))
    print(risky([1, 2, 3], -4))
    print("never")
main()
''',
    'list_len_boundary': '''
def risky(xs: list[int], i: int) -> int:
    return xs[i] + xs[i - 1]

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(risky([5, 6, 7], 2))
    print(risky([5, 6, 7], 3))
main()
''',
    'empty_list': '''
def first(xs: list[int]) -> int:
    return xs[0]

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    xs = [4]
    xs.pop()
    print(first(xs))
main()
''',
    'float_list': '''
def risky(xs: list[float], i: int) -> float:
    return xs[i] * 2.0

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(risky([1.5, 2.5], 1))
    print(risky([1.5, 2.5], 2))
main()
''',
    'str_index': '''
def code(s: str, i: int) -> int:
    return ord(s[i])

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(code("abc", 2), code("abc", -1))
    print(code("abc", 3))
main()
''',
    'str_at': '''
def at(s: str, i: int) -> str:
    return s[i]

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(at("abc", 1), at("abc", -3))
    print(at("abc", 3))
main()
''',
    'str_slice': '''
def cut(s: str, a: int, b: int) -> str:
    return s[a:b]

def lens(xs: list[int], a: int) -> int:
    return len(xs[a:]) + len(xs[:a])

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(cut("abcdef", 1, 3) + "|" + cut("abc", -2, 99) + "|" + cut("abc", 5, 7) + "|")
    print(lens([1, 2, 3, 4], 2), lens([1, 2, 3], 9), lens([1, 2, 3], -1))
    print([1, 2][5])
main()
''',
    'dict_key_in_clone': '''
def look(k: int) -> int:
    t = {1: 10, 2: 20}
    return t[k]

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(look(2))
    print(look(7))
main()
''',
    'loop_over_list': '''
def total(xs: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += xs[i]
    return s

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(total([1, 2, 3], 3))
    print(total([1, 2, 3], 5))
main()
''',
}


# not selected for a typed clone (they run boxed); kept to show the same answers
BOXED_ONLY = ('float_list', 'str_index', 'str_at', 'dict_key_in_clone')


def build(tmp, name, text, ir, flags=None):
    src = Path(tmp) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(tmp) / ('exe_%s_%s' % (name, ir))
    env = dict(os.environ, AIL_SURFACE='python', AIL_IR=ir)
    env.pop('AIL_NO_MIX', None)
    env.pop('AIL_NO_GENERAL', None)
    return src, exe, subprocess.run([sys.executable, '-B', PYC, str(exe), '--file', str(src)], cwd=tmp,
                                    capture_output=True, text=True, timeout=900, env=env)


class MixedBounds(unittest.TestCase):
    def run_all(self, names=None, sanitize=False):
        with tempfile.TemporaryDirectory(prefix='ail-mixbounds-') as tmp:
            for name, text in PROGRAMS.items():
                if names and name not in names:
                    continue
                want = subprocess.run([sys.executable, '-B', '-c', text], capture_output=True, timeout=120,
                                      env=dict(os.environ, PYTHONUTF8='1'))
                self.assertEqual(want.returncode, 1, name)
                for ir in ('1', '0'):
                    with self.subTest(program=name, ir=ir):
                        src, exe, built = build(tmp, name, text, ir)
                        self.assertEqual(built.returncode, 0, built.stderr[-1500:])
                        if name not in BOXED_ONLY:
                            self.assertTrue(list(Path(tmp).glob('exe_%s_%s_mix*.c' % (name, ir))), 'no typed clone')
                        if sanitize:
                            exe = self.sanitized(tmp, name, ir)
                        got = subprocess.run([str(exe)], cwd=tmp, capture_output=True, timeout=120,
                                             stdin=subprocess.DEVNULL,
                                             env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
                        err = got.stderr.decode('utf-8', 'replace')
                        self.assertNotIn('AddressSanitizer', err)
                        self.assertNotIn('runtime error', err)
                        self.assertEqual(got.stdout.decode(), want.stdout.decode())
                        self.assertEqual(got.returncode, 1, err[-500:])
                        self.assertTrue('index' in err or 'KeyError' in err, err)

    def sanitized(self, tmp, name, ir):
        """Rebuild the program's C units with -fsanitize=address,undefined and link them."""
        base = 'exe_%s_%s' % (name, ir)
        units = sorted(Path(tmp).glob(base + '_mix*.c')) + [Path(tmp) / (base + '.c')]
        out = Path(tmp) / (base + '_san')
        cmd = ['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-o', str(out),
               *map(str, units), '-lm', '-pthread']
        cc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if cc.returncode:
            if 'san' in cc.stderr:
                self.skipTest('gcc cannot build with sanitizers')
            self.fail(cc.stderr[-1500:])
        return out

    def test_differential(self):
        self.run_all()

    @unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('gcc'), 'sanitizers: Linux gcc')
    def test_asan_ubsan(self):
        self.run_all(sanitize=True)


if __name__ == '__main__':
    unittest.main()
