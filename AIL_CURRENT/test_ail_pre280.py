"""A constant index with a wide intermediate whose result fits (job pre280).

The reviewer of job pre276 recorded that an in-range wide-intermediate index such as
``xs[2 ** 63 - 2 ** 63]`` was still refused as ``int64 index out of range: 9223372036854775808``
on both builds, while CPython evaluates the expression to 0 and prints the first item.  The
pre177 index check range-checked every step; it now folds the whole constant exactly (the
pre246 approach) and keeps the per-step refusal only when the exact fold is inconclusive or the
result still leaves int64.

The matching programs cover a list, a tuple, a str and a bytes receiver, a dict key, a negative
result, and a value reaching the subscript through a function argument, a class attribute, a
dict value, a list item and an alias, on both builds.  The programs whose exact index value
really is outside int64 build too (exact ints, bigint, BIGINT.md) and end like CPython with
IndexError and exit code 1, exception line included.  An empty list with the in-range
index raises IndexError at run time, as CPython does.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

WIDE = r'''xs = [10, 20, 30]
print(xs[2 ** 63 - 2 ** 63])
print(xs[(1 << 63) - (1 << 63)])
print(xs[(10 ** 20) // (10 ** 19) - 10])
print(xs[2 ** 63 - 2 ** 63 - 3])
print((1, 2, 3)[(1 << 63) - (1 << 63)])
print("abc"[(2 ** 63) - (2 ** 63)])
print(b"abc"[(2 ** 64) - (2 ** 64)])
print({0: "zero"}[2 ** 63 - 2 ** 63])
print(xs[(2 ** 63) % 7])
print(xs[~(2 ** 63) + 2 ** 63])
print(xs[-(2 ** 63) + 2 ** 63])
'''

ROUTES = r'''class Box:
    i = 2 ** 63 - 2 ** 63


def at(xs, i):
    return xs[i]


def main():
    xs = [10, 20, 30]
    d = {"i": 2 ** 63 - 2 ** 63}
    box = Box()
    i = 2 ** 63 - 2 ** 63
    j = i
    print(at(xs, 2 ** 63 - 2 ** 63))
    print(xs[box.i])
    print(xs[d["i"]])
    print(xs[[2 ** 63 - 2 ** 63][0]])
    print(xs[j])


main()
'''

EMPTY = '''print([][2 ** 63 - 2 ** 63])
'''

REFUSED = (
    '2 ** 63',
    '-(10 ** 20)',
    '(2 ** 62) * 4',
    '(10 ** 20) // (10 ** 19) + 10 ** 20',
)


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
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


class Pre280Tests(unittest.TestCase):
    def check(self, slug, text, rc=0, exc_line=False):
        with tempfile.TemporaryDirectory(prefix='ail-pre280-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                with self.subTest(slug=slug, general=general):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    built, exe = _build(directory, name, text, general)
                    output = built.stdout + built.stderr
                    self.assertEqual(built.returncode, 0, '%s\n%s' % (slug, output[-4000:]))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), (want, rc),
                                     '%s\n%s' % (slug, got.stderr[-2000:]))
                    if exc_line:
                        last = err.decode('utf-8', 'replace').strip().splitlines()[-1]
                        self.assertIn(last, got.stderr.decode('utf-8', 'replace'), slug)

    def test_wide_intermediate_constant_index_matches_cpython(self):
        self.check('wide', WIDE)
        self.check('routes', ROUTES)
        self.check('empty', EMPTY, rc=1)

    def test_out_of_range_constant_index_is_still_refused(self):
        # exact ints (bigint): builds and ends like CPython (IndexError, exit 1, same exception line)
        for number, expression in enumerate(REFUSED):
            self.check('out%d' % number, 'print([10, 20, 30][%s])\n' % expression, rc=1, exc_line=True)


if __name__ == '__main__':
    unittest.main()
