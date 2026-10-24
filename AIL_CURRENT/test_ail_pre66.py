"""Non-BMP chr() on the 16-bit general path.

The boxed general path stores strings as UTF-16 units.  It now represents a
non-BMP chr() value as a surrogate pair, so printing, length/ord, indexing,
slicing, iteration, comparison, containers and the common str search methods
all agree with CPython.  Non-BMP string literals are still refused by name on
that path; the typed/default path keeps its existing behaviour.  BMP,
out-of-range and wrong-type chr() behaviour is unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LITERAL_REFUSAL = 'a non-BMP string literal in the 16-bit v2 runtime'

NON_BMP = '''s = chr(0x1F600)
print(s)
print(len(s), ord(s), repr(s))
print(s[0], s[-1], s[0:1], s[1:], s[::-1])
print(list(s), list(reversed(s)), s == chr(0x1F600))
s = s + "x" + chr(0x10000) + "y"
print(s, len(s), [ord(c) for c in s])
print(s.find("x"), s.rfind("x"), s.find("y"), s.rfind("y"))
print(s.find(chr(0x1F600)), s.rfind(chr(0x10000)))
print(s.find(""), s.rfind(""), s.count(""))
print(s.startswith(chr(0x1F600)), s.endswith("y"))
print(s.count("x"), s.count("x", 2), s.startswith("x", 1), s.endswith("x", 0, 2))
print(repr(chr(0x10FFFF)), repr(chr(0x10000)))
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
BMP_CARRIERS = '''class C:
    pass


def via_arg(n) -> None:
    print(chr(n))


def main() -> None:
    n = 0xFFFF
    xs = [0x80]
    d = {"n": 0x7F}
    c = C()
    c.n = 0
    print(chr(n), chr(xs[0]), chr(d["n"]), chr(c.n))
    via_arg(0xE000)


main()
'''


def _run_cpython(directory, text, name):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True,
                          env=dict(os.environ, PYTHONUTF8='1'), timeout=120)


def _build(directory, text, name, general):
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


def _compile(directory, text, name, general):
    built, exe = _build(directory, text, name, general)
    return built, exe


class Pre66Tests(unittest.TestCase):
    def refused_literal(self, general):
        text = "print('\\U0001f600')\n"
        with tempfile.TemporaryDirectory(prefix='ail-pre66-') as directory:
            built, exe = _compile(directory, text, 'literal', general)
            self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn(LITERAL_REFUSAL, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def compare(self, text, name, general, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre66-') as directory:
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
            self.compare(NON_BMP, 'non_bmp', general)
            self.compare(CARRIERS, 'carriers', general)

    def test_bmp_and_out_of_range_unchanged(self):
        for general in (True, False):
            self.compare(BMP, 'bmp', general)
            self.compare(OUT_OF_RANGE, 'out_of_range', general)
            self.compare(WRONG_TYPE, 'wrong_type', general)

    def test_bmp_at_runtime_through_carriers(self):
        for general in (True, False):
            self.compare(BMP_CARRIERS, 'bmp_carriers', general)


if __name__ == '__main__':
    unittest.main()
