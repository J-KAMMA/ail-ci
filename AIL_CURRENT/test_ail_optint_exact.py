"""`-> int | None` (and a written `-> tuple[bool, int]`) whose int comes from `int(<text>)`: exact in the default build.

optlib lowers an Optional int result to the pair (present, value); the IR does not lower a tuple result, so the function
was compiled by the legacy int64 emitter and `int("99999999999999999999")` stopped with "integer overflow" (found in
PR #263). Such a function now takes the exact general path, like any other function the tagged lowering does not cover
(ir/driver.py). A typed-only build (AIL_NO_GENERAL=1) keeps the loud stop; a program whose int is not parsed text keeps
the typed path.

O1  default build and AIL_UNIFIED_FORCE=1 print what CPython prints, small and beyond-int64 values
O2  a typed-only build still builds the program (and stops loudly on a value beyond int64)
O3  an Optional int that does not come from text stays on the typed path
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PARSE = '''
import sys


def parse(s: str, lo: int) -> int | None:
    if not s or not all('0' <= ch <= '9' for ch in s):
        return None
    v = int(s)
    if v < lo:
        return None
    return v


def pair(s: str) -> tuple[bool, int]:
    if not s.isdigit():
        return (False, 0)
    return (True, int(s) * 3)


def main() -> None:
    toks = sys.stdin.read().split()
    total = 0
    for t in toks:
        v = parse(t, 0)
        ok, w = pair(t)
        if v is None:
            print("none", ok, w)
        else:
            total += v
            print(v, v + 1, ok, w)
    print("total", total)


main()
'''

NOT_TEXT = '''
def sign_of(n: int) -> int | None:
    if n > 0:
        return 1
    if n < 0:
        return -1
    return None


def main() -> None:
    for i in range(-2, 3):
        h = sign_of(i)
        if h is None:
            print(i, "zero")
        else:
            print(i, h)


main()
'''

INPUTS = ['12 x 7 -3\n', '99999999999999999999 18446744073709551615 18446744073709551616\n', '9223372036854775807 0\n', '']


def build(directory, text, name, extra=None):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    for k in ('AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
        env.pop(k, None)
    env.update(extra or {})
    env['AIL_NO_CACHE'] = '1'
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax', 'python',
                        '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return r, source, exe


def run(cmd, data):
    r = subprocess.run(cmd, input=data, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout


class OptionalIntExact(unittest.TestCase):
    def test_o1_matches_cpython(self):
        with tempfile.TemporaryDirectory() as d:
            for mode, extra in (('default', {}), ('force', {'AIL_UNIFIED_FORCE': '1'})):
                r, source, exe = build(d, PARSE, 'p_' + mode, extra)
                self.assertEqual(r.returncode, 0, r.stderr[-1500:])
                for data in INPUTS:
                    self.assertEqual(run([str(exe)], data), run([sys.executable, str(source)], data), (mode, data))

    def test_o2_typed_only_keeps_loud_stop(self):
        with tempfile.TemporaryDirectory() as d:
            r, source, exe = build(d, PARSE, 'p', {'AIL_NO_GENERAL': '1'})
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            self.assertEqual(run([str(exe)], INPUTS[0]), run([sys.executable, str(source)], INPUTS[0]))
            code, out = run([str(exe)], INPUTS[1])
            self.assertNotEqual(code, 0)

    def test_o3_not_text_stays_typed(self):
        with tempfile.TemporaryDirectory() as d:
            r, source, exe = build(d, NOT_TEXT, 'n')
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            self.assertNotIn('built on the general path', r.stderr)
            self.assertEqual(run([str(exe)], ''), run([sys.executable, str(source)], ''))


if __name__ == '__main__':
    unittest.main()
