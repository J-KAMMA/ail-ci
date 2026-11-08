"""fz241: a list sort with a tuple key and str ordering already match CPython.

The daily fuzzer (seed 2076514981) stopped after `print((7.0 / 18), 0.5)` with
`TypeError: '<' not supported between instances of 'object' and 'object'`, before the first
`False` from `print((len(al7) <= (i13 // -3)))`.  The trigger is
`al8.sort(key=lambda q: (-q, q))` on a list aliased through two names, with
`'abc'.lstrip() < '日本'[:-1]` in the same program.  On this tree the seed matches CPython on
both builds; this module pins the tuple-key sort, its element types, the string ordering, and
values reaching the sort through an argument, a list item, an attribute and a dict value.
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
v2: list[int] = [0, 0, 131, 131, 131, 131, 131]
al7: list[int] = v2
v2.sort()
al8: list[int] = al7
al8.append(0)
for i13 in range(-1, 3):
    al8.sort(key=lambda q: (-q, q))
    print((len(al7) <= (i13 // -3)))
print(len(v2), len(al7), len(al8), sum(v2), sum(al7), sum(al8))
'''

SORT_TYPES = '''\
xs: list[int] = [5, -2, 7, 0, 5]
xs.sort(key=lambda q: (-q, q))
print(xs)
fs: list[float] = [2.5, -0.0, 1e300, -1e-300]
fs.sort(key=lambda q: (-q, q))
print(fs)
bs: list[bool] = [True, False, True]
bs.sort(key=lambda q: (not q, q))
print(bs)
ss: list[str] = ['b', 'a', 'c', '']
ss.sort(key=lambda q: (q,))
print(ss)
rows: list[tuple[int, int]] = [(1, 2), (1, 1), (0, 9), (1, -2)]
rows.sort()
print(rows)
rows.sort(key=lambda p: (p[1], p[0]))
print(rows)
print(sorted(rows, key=lambda p: (-p[0], p[1])))
print(min(rows, key=lambda p: (p[1], -p[0])))
print(max(rows, key=lambda p: (p[1], -p[0])))
'''

STR_ORDER = '''\
text: str = 'abc'.lstrip()
other: str = '日本'[:-1]
print(text < other, text > other, text == other)


def cmp(a: str, b: str) -> bool:
    return a < b


print(cmp(text, other))
words: list[str] = [other, text]
words.sort()
print(words)
d: dict[str, str] = {"a": text, "b": other}
print(d["a"] < d["b"])
'''

ROUTES = '''\
def show(xs: list[int], k: int) -> None:
    xs.sort(key=lambda q: (q - k, -q))
    print(xs)


class Holder:
    def __init__(self, xs: list[int]) -> None:
        self.xs: list[int] = xs


show([4, 1, 3], 1)
h: Holder = Holder([9, -1, 5])
h.xs.sort(key=lambda q: (-q, q))
print(h.xs)
d: dict[str, list[int]] = {"xs": [8, 2, 6]}
d["xs"].sort(key=lambda q: (-q, q))
print(d["xs"])
grid: list[list[int]] = [[3, 1], [2, 9]]
grid.sort(key=lambda row: (row[1], row[0]))
print(grid)
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, extra):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_IR', 'AIL_EXACT_INT'):
        env.pop(key, None)
    env.update(extra)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.returncode, (built.stdout + built.stderr)
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return got, built.returncode, ''


class Fz241Tests(unittest.TestCase):
    def same(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz241-') as directory:
            want, want_rc = _cpython(directory, name, text)
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, want_rc, (name, mode, got.stderr[-1500:]))

    def test_minimized_fuzzer_seed_matches_cpython(self):
        self.same('minimal', MINIMAL)

    def test_tuple_key_sorts_over_element_types_match_cpython(self):
        self.same('sort_types', SORT_TYPES)

    def test_str_ordering_matches_cpython(self):
        self.same('str_order', STR_ORDER)

    def test_values_through_routes_match_cpython(self):
        self.same('routes', ROUTES)


if __name__ == '__main__':
    unittest.main()
