"""fz244: a keyed `list.sort()` over int64-boundary values matches CPython.

The daily fuzzer (seed 2076520850, CPython 3.12) doubled a list built as
`[min(v1, b), b]` with `b = 9223372036854775807` twenty times and called
`v3.sort(key=lambda q: (-q, q))`.  At that fuzz run AIL stopped inside the sort with
`TypeError: '<' not supported between instances of 'object' and 'int'`, so the `True`
of `h0(91, 4) >= 255` (stdout line 30) was missing (`DIFF|cpython='True' ail='<end>'`).

On this tree the seed never reaches that code: the unreachable
`-9223372036854775807 << 1` constant in a `except ZeroDivisionError` arm is outside
int64 and is refused by name on both builds, so the fuzz runner counts it `refused`
rather than DIFF; with `--exact-int` the whole program matches CPython byte for byte.
This module pins that refusal, the exact-int route, and the minimized sort (ints at
the int64 boundaries, duplicates, a float list, an untyped list, and the list reached
through an argument, a list item, an attribute and a dict value) on the default and
IR builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODES = (
    ('default', {}),
    ('default_ir', {'AIL_IR': '1'}),
)

MINIMAL = '''\
def h0(a: int, b: int) -> int:
    v3: list[int] = [min(-1, b), b]
    w4: int = 0
    while w4 < 8:
        w4 += 1
        v3 += v3
    v3.sort(key=lambda q: (-q, q))
    if (255 > (a * a)):
        return (a - 41)
    return ((b // a) + len(v3))


print((h0(91, 4) >= 255))
print((h0(91, 9223372036854775807) >= 255))
'''

SEED_SHAPE = """\
def h0(a: int, b: int) -> int:
    v1: int = f'{(abs(123456.789) ** 0.5):.2f}{abs(0.3):>10.1f}'.find('x')
    v3: list[int] = [min(v1, b), b]
    w4: int = 0
    while w4 < 5:
        w4 += 1
        w5: int = 0
        while w5 < 4:
            w5 += 1
            v3 += v3
            print((max(a, w5) * (w4 ** 0)))
    v3.sort(key=lambda q: (-q, q))
    if (255 > (a * a)):
        return (a - 41)
    return ((b // a) + len(v3))


print((h0(91, 4) >= 255))
"""

OTHER_TYPES = '''\
b: int = 9223372036854775807
v: list[int] = [b, -1, b, 0, -1, 0]
v.sort(key=lambda q: (-q, q))
print(v)
f: list[float] = [1.5, -2.25, 1e308, -0.0, 1.5]
f.sort(key=lambda q: (-q, q))
print(f)
o: list[object] = [2.5, 1, -3]
o.sort(key=lambda q: (-q, q))
print(o)
t: list[int] = [5, 1, 4, 2, 3]
t.sort(key=lambda q: (-q, q, 'x'))
print(t)
'''

ROUTES = '''\
def sort_arg(xs: list[int]) -> list[int]:
    xs.sort(key=lambda q: (-q, q))
    return xs


class Holder:
    def __init__(self) -> None:
        self.v: list[int] = [9223372036854775807, -1, 0, -9223372036854775807]


h: Holder = Holder()
d: dict[str, list[int]] = {"k": [5, -5, 9223372036854775807, 0]}
box: list[list[int]] = [[3, 1, 2, -4]]
print(sort_arg(h.v))
print(h.v)
d["k"].sort(key=lambda q: (-q, q))
print(d["k"])
box[0].sort(key=lambda q: (-q, q))
print(box[0])
'''

SHIFT = '''\
v: list[int] = [30, (-9223372036854775807 << 1)]
print(v)
'''

SEED = '''\
def h0(a: int, b: int) -> int:
    v1: int = f'{(abs(123456.789) ** 0.5):.2f}{abs(0.3):>10.1f}'.find('x')
    v2: str = '3.5'[0:4].replace('l', '-')
    v3: list[int] = [min(v1, b), b]
    w4: int = 0
    while w4 < 5:
        w4 += 1
        w5: int = 0
        while w5 < 4:
            w5 += 1
            v3 += v3
            v6: dict[str, int] = {}
            v6['a'] = 13
            v6['dd'] = -7
            v6['b'] = 29
            print((max(a, w5) * (w4 ** 0)))
        v7: dict[str, int] = {}
        v7['dd'] = 19
        v7['a'] = 84
        v7['c'] = 73
        try:
            if (('ab' * 3).endswith(' ')):
                assert (((a - w4) <= b) or (a == 10)), "boom"
        except AssertionError:
            print(-5)
        else:
            print(7)
    v8: bytes = b"12"[-2:-1]
    v3.sort(key=lambda q: (-q, q))
    if (255 > (a * a)):
        return (a - 41)
    return ((b // a) + len(v3))


def main() -> int:
    print((69 ^ 66))
    print(((abs(3.0) ** 0.5) * 1.25))
    try:
        v9: float = max(float(50), 1.25)
        if ((not (18 > (35 ** 2))) or ('abc'[1:2].endswith('he'))):
            v10: int = ((88 - 51) + 49)
        else:
            v11: int = ((58 ** 1) // (abs(91) + 1))
            print(64)
        v12: list[int] = [(9223372036854775807 % (abs(12) + 1)), 23]
    except ZeroDivisionError:
        v13: list[int] = [30, (-9223372036854775807 << 1), max(19, 81), 53]
    except ValueError:
        print('日本')
        v14: str = f'#{(77 / 8):>10.1f}'
    else:
        print((38 >> 11))
    finally:
        print(282)
    try:
        if ((((71 & 16) > 3) or ('ab'[:-1] >= 'a,b,c'[:2])) or ('AbCd' in 'café'[:])):
            for i15 in range(9, -2, -1):
                w16: int = 0
                while w16 < 5:
                    w16 += 1
                    print((abs((1e10 + 123456.789)) ** 0.5))
                    if ((-1 > 3) or 'x'.isupper()):
                        break
                    print(100.75)
                v17: bool = ((i15 > h0((i15 - i15), 9223372036854775807)) and (('café' * 0).endswith('a')))
            for i18 in range(5, 1, -1):
                print('AbCd'.lower()[-2:-1])
        elif ((' pad ' + ' pad ').endswith('he')):
            try:
                print(abs(61))
            except ValueError:
                print(-28)
        else:
            v19: str = ('q q' + 'x'.strip())
            try:
                print((h0((40 + 51), len(v19)) >= 255))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-34)
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-43)
    return 0


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=300,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, extra, flags=()):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_IR', 'AIL_EXACT_INT'):
        env.pop(key, None)
    env.update(extra)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', *flags, '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.returncode, (built.stdout + built.stderr)
    got = subprocess.run([str(exe)], capture_output=True, timeout=300, cwd=directory)
    return got, built.returncode, ''


class Fz244Tests(unittest.TestCase):
    def same(self, name, text, flags=()):
        with tempfile.TemporaryDirectory(prefix='ail-fz244-') as directory:
            want, want_rc = _cpython(directory, name, text)
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode, flags=flags):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra,
                                                        flags)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, want_rc, (name, mode, got.stderr[-1500:]))

    def refused(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz244-') as directory:
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNone(got, (name, mode, err[-3000:]))
                    self.assertNotEqual(build_rc, 0, (name, mode))
                    self.assertIn('int64', err, (name, mode))
                    self.assertNotIn('Traceback', err, (name, mode))

    def test_minimized_sort_matches_cpython(self):
        self.same('minimal', MINIMAL)

    def test_seed_shape_matches_cpython(self):
        self.same('seed_shape', SEED_SHAPE)

    def test_other_types_match_cpython(self):
        self.same('other_types', OTHER_TYPES)

    def test_values_through_routes_match_cpython(self):
        self.same('routes', ROUTES)

    def test_constant_shift_beyond_int64_is_refused_by_name(self):
        self.refused('shift', SHIFT)

    def test_seed_is_refused_by_name_and_not_a_silent_difference(self):
        with tempfile.TemporaryDirectory(prefix='ail-fz244-') as directory:
            for mode, extra in MODES:
                with self.subTest(mode=mode):
                    got, build_rc, err = _build_and_run(directory, 'seed_' + mode, SEED, extra)
                    self.assertIsNone(got, (mode, err[-3000:]))
                    self.assertEqual(build_rc, 3, (mode, err[-3000:]))
                    self.assertIn('overflows int64', err, (mode, err[-3000:]))
                    self.assertNotIn('Traceback', err, (mode, err[-3000:]))

    def test_seed_with_exact_int_matches_cpython(self):
        self.same('seed_exact', SEED, flags=('--exact-int',))


if __name__ == '__main__':
    unittest.main()
