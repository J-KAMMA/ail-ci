"""Pre-269: a constant index may pass through an out-of-int64 step and still fit.

CPython's ints are unbounded, so ``del a[2**63 * 0]`` and ``del a[(1 << 63) >> 62]``
delete an ordinary element.  The front-end's constant-index pass used to stop at the first
int64-exceeding step and refused both with ``int64 index out of range``.  The whole index is
now folded with the same size budget as the other constant checks, and only the exact final
value is range-checked; a final value that still leaves int64 is an exact big integer
(bigint, BIGINT.md) and ends like CPython (IndexError, exit 1) instead of being refused.

The cases below cover list/str/bytes/tuple/dict reads, list and dict deletion, the INT64
boundaries reached through a wider intermediate, an empty list, a negative result, and values
reaching the subscript through an argument, a list item, an attribute, a dict value and an
alias on both cmp.sh builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IN_RANGE = '''def take(seq, i):
    del seq[i]


def at(seq, i):
    return seq[i]


class Box:
    i = (1 << 63) >> 62


def local_del():
    xs = [0, 1, 2, 3, 4]
    j = (1 << 63) >> 62
    del xs[j]
    return xs


a = [0, 1, 2, 3, 4]
del a[2**63 * 0]
print("del-zero", a)
a = [0, 1, 2, 3, 4]
del a[(1 << 63) >> 62]
print("del-shift", a)
a = list(range(20))
del a[(10**20) // (10**19)]
print("del-div", a)
a = [0, 1, 2, 3, 4]
del a[(1 << 63) - (1 << 63) + 3]
print("del-add", a)
a = [0, 1, 2, 3, 4]
del a[-(1 << 63) >> 62]
print("del-negative", a)
a = [0, 1, 2, 3, 4]
take(a, (1 << 63) >> 62)
print("arg-del", a)
a = [0, 1, 2, 3, 4]
del a[[(1 << 63) >> 62][0]]
print("item-del", a)
a = [0, 1, 2, 3, 4]
del a[Box().i]
print("attr-del", a)
a = [0, 1, 2, 3, 4]
del a[{"i": (1 << 63) >> 62}["i"]]
print("dict-del", a)
a = [0, 1, 2, 3, 4]
i = 2**63 * 0
del a[i]
print("alias-del", a)
print("local-del", local_del())
empty = []
try:
    del empty[2**63 * 0]
    print("empty-ok")
except IndexError:
    print("empty-index")
print("read-list", at([10, 20, 30, 40, 50], (1 << 63) >> 62))
print("read-str", "abcde"[(1 << 63) >> 62])
print("read-bytes", b"abcde"[(1 << 63) >> 62])
print("read-tuple", (10, 20, 30, 40, 50)[(1 << 63) >> 62])
print("read-dict", {0: "zero", 2: "two"}[(1 << 63) >> 62])
d = {0: "zero", 2: "two"}
del d[(1 << 63) >> 62]
print("dict-after-del", d)
MIN = -(1 << 63)
MAX = (1 << 63) - 1
bounds = {MIN: "min", MAX: "max"}
print("bound-min", bounds[-(1 << 63)])
print("bound-max", bounds[((1 << 64) - 1) >> 1])
'''

REFUSED = {
    'shift': 'xs = [1, 2, 3]\ndel xs[1 << 63]\nprint(xs)\n',
    'shift_plus_one': 'xs = [1, 2, 3]\ndel xs[(1 << 63) + 1]\nprint(xs)\n',
    'power_times_one': 'xs = [1, 2, 3]\ndel xs[2**63 * 1]\nprint(xs)\n',
    'division': 'xs = [1, 2, 3]\ndel xs[(10**20) // 1]\nprint(xs)\n',
    'below_min': 'd = {}\nprint(d[-(1 << 63) - 1])\n',
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
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
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-4000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), ''


class Pre269Tests(unittest.TestCase):
    def test_in_range_through_wide_intermediate_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre269-') as directory:
            want, want_rc, err = _cpython(directory, 'in_range', IN_RANGE)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                mode = 'g' if general else 'd'
                with self.subTest(mode=mode):
                    got, build_err = _run(directory, 'in_range_' + mode, IN_RANGE, general)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)

    def test_out_of_int64_index_still_refused_by_name(self):
        # exact ints (bigint): the index beyond int64 builds; it ends like CPython (IndexError, exit 1)
        with tempfile.TemporaryDirectory(prefix='ail-pre269-') as directory:
            for label, text in REFUSED.items():
                want, want_rc, err = _cpython(directory, 'ref_' + label, text)
                for general in (True, False):
                    mode = 'g' if general else 'd'
                    with self.subTest(label=label, mode=mode):
                        got, build_err = _run(directory, '%s_%s' % (label, mode), text, general)
                        self.assertIsNotNone(got, build_err)
                        self.assertEqual(got, (want, want_rc), build_err)


if __name__ == '__main__':
    unittest.main()
