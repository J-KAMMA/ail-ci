"""Differential round 59: list slice assignment, and list repr after a slice stores another type.

Found with small programs compared against CPython on both builds:

`b: list[int]` with `b[1:2] = "ab"` keeps the str elements, as CPython does; when the same
function also assigns a tuple of ints to a slice of `b`, the list is statically a list[int] and
the generated list-repr helper formatted each element with `str(x)`. A str element then printed
unquoted: `[1, a, b, 3]` where CPython prints `[1, 'a', 'b', 3]`. The helper now uses `repr(x)`,
which is the same text for int/float/bool and quotes a str that reached a slot of another static
type. The slice programs below (extended and negative steps, None bounds, slice objects, delete,
length mismatch, sources through arguments / items / attributes / dict values) keep the area
compared with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MIXED_REPR = r'''def main() -> None:
    b: list[int] = [1, 2, 3]
    try:
        b[1:2] = "ab"
        print(b)
    except Exception as e:
        print(type(e).__name__, str(e))
    b = [1, 2, 3]
    try:
        b[1:2] = (10, 11)
        print(b)
    except Exception as e:
        print(type(e).__name__, str(e))
    t: list[int] = [1, 2, 3]
    t[1:2] = "xy"
    t[1:2] = (4, 5)
    print(t, (t[0], t[1]), [t[1:3]])
    print([1, 2, 3], (1, 2, 3), [], (), [True], (1.5, -0.0))

main()
'''

EXTENDED = r'''def main() -> None:
    a: list[int] = [0, 1, 2, 3, 4, 5]
    a[::2] = [10, 11, 12]
    print(a)
    a[::-1] = [20, 21, 22, 23, 24, 25]
    print(a)
    a[1::3] = [30, 31]
    print(a)
    a[::-2] = [40, 41, 42]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    a[3:1:-1] = [8, 9]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    a[1000000000000:] = [9]
    a[-1000000000000:1000000000000] = [7]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    a[::2] = "abc"
    print(a)
    a[::2] = [1, 2, 3]
    print(a)
    a[1:5:2] = (u for u in [6, 7])
    print(a)

main()
'''

DELETES = r'''def main() -> None:
    a: list[int] = [0, 1, 2, 3, 4, 5]
    del a[1:3]
    print(a)
    del a[::2]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    del a[::-1]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    del a[-100:100]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    del a[4:1]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    del a[1:100:2]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    del a[100::-2]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    del a[None:None:-2]
    print(a)
    a = []
    del a[::2]
    print(a)

main()
'''

NONE_OBJECT = r'''def main() -> None:
    a: list[int] = [0, 1, 2, 3, 4, 5]
    a[None:None] = [9]
    print(a)
    a[None:None:None] = [7, 8]
    print(a)
    a[None:2] = []
    print(a)
    a[2:None] = [1]
    print(a)
    a = [0, 1, 2, 3, 4, 5]
    a[slice(None, None, -1)] = [0, 1, 2, 3, 4, 5]
    print(a)
    a[slice(1, None, None)] = [5]
    print(a)
    del a[slice(None, None, 2)]
    print(a)
    del a[slice(None, 1)]
    print(a)
    del a[slice(2, None, 2)]
    print(a)

main()
'''

SOURCES = r'''class Box:
    xs: list[int]

    def __init__(self) -> None:
        self.xs = [0, 1, 2, 3, 4]


def mutate(a: list[int], lo: int, hi: int, step: int, vals: list[int]) -> None:
    a[lo:hi:step] = vals
    print(a)


def main() -> None:
    a: list[int] = [0, 1, 2, 3, 4, 5, 6, 7]
    b: list[int] = [9, 8]
    a[1:5:2] = b
    print(a)
    mutate(a, 0, 4, 1, [100, 101])
    d: dict[str, list[int]] = {"v": [5, 6, 7, 8]}
    d["v"][1:3] = [66]
    print(d)
    holder: list[list[int]] = [[1, 2, 3, 4]]
    holder[0][::2] = [10, 20]
    print(holder)
    box: Box = Box()
    box.xs[1:3] = [55, 66, 77]
    print(box.xs)
    src: list[int] = [11, 22, 33]
    a[2:2] = src
    src[0] = 999
    print(a)
    print(src)

main()
'''

ERRORS = r'''def attempt(a: list[int], v: list[int]) -> None:
    try:
        a[::2] = v
        print("ok", a)
    except Exception as e:
        print(type(e).__name__, str(e))


def main() -> None:
    a: list[int] = [0, 1, 2, 3, 4, 5]
    attempt(a, [9])
    attempt(a, [9, 8, 7, 6])
    try:
        a[::0] = [1]
    except Exception as e:
        print(type(e).__name__, str(e))
    b: list[int] = [1, 2, 3]
    try:
        b[1:2] = 5
    except Exception as e:
        print(type(e).__name__, str(e))
    b = [1, 2, 3]
    b[1:2] = (x for x in [7, 8])
    print(b)
    a = []
    try:
        a[::2] = [1]
    except Exception as e:
        print(type(e).__name__, str(e))
    print(a)

main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz59Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz59-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_repr_after_slice_stores_another_type(self):
        self.check('mixed_repr', MIXED_REPR)

    def test_extended_and_negative_steps(self):
        self.check('extended', EXTENDED)

    def test_deletes_with_steps(self):
        self.check('deletes', DELETES)

    def test_none_bounds_and_slice_objects(self):
        self.check('none_object', NONE_OBJECT)

    def test_sources_arguments_items_attributes_dicts(self):
        self.check('sources', SOURCES)

    def test_length_and_type_errors(self):
        self.check('errors', ERRORS)


if __name__ == '__main__':
    unittest.main()
