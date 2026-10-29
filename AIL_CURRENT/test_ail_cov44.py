"""cov44: a nested generator expression consumed in place matches CPython on both builds.

The general path materialises a generator expression eagerly.  That was refused by name for
every generator expression nested inside another one (pre42).  When the outer generator is
itself an argument of a call that reads every element at once (join, sum, list, sorted, ...)
and every inner generator is consumed the same way inside that expression, the eager lowering
runs the inner body at exactly the point CPython creates and consumes it, so the output is the
same.  This was the most frequent remaining non-import refusal in lab/corpus/programs (3
programs on each build).  A nested generator that is saved as a value, used as the iterable of
a for statement, or read by next()/any()/all() still differs and stays a named refusal.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    done = subprocess.run([sys.executable, '-B', str(CHATGPT), 'compile', src.name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)
    return exe, done


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-cov44-') as directory:
        want = cpython(directory, name, text)
        test.assertEqual(want[1], 0, text)
        for general in (True, False):
            exe, built = build(directory, '%s%d' % (name, general), text, general)
            test.assertEqual(built.returncode, 0, '%s (general=%s)\n%s'
                             % (text[:2000], general, (built.stdout + built.stderr)[-2000:]))
            got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
            test.assertEqual(got.returncode, want[1], '%s (general=%s)' % (text[:2000], general))
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                             '%s (general=%s)' % (text[:2000], general))


def check_refused(test, name, text, words):
    with tempfile.TemporaryDirectory(prefix='ail-cov44-') as directory:
        for general in (True, False):
            exe, built = build(directory, '%s%d' % (name, general), text, general)
            test.assertNotEqual(built.returncode, 0, '%s built (general=%s)' % (name, general))
            test.assertFalse(exe.exists(), '%s built (general=%s)' % (name, general))
            for word in words:
                test.assertIn(word, built.stdout + built.stderr, '%s (general=%s)' % (name, general))


PROGRAMS = {
    'join_of_join': 'rows = [[1, 2], [3], [], [4, 5, 6]]\n'
                    'print("|".join(" ".join(str(v) for v in row) for row in rows))\n',
    'sum_in_join': 'rows = [[1, 2], [3], [], [4, 5, 6]]\n'
                   'print(",".join(f"{sum(x for x in row)}:{len(row)}" for row in rows))\n',
    'sum_of_sum': 'rows = [[1, 2], [3], [], [4, 5, 6]]\n'
                  'print(sum(sum(x * 2 for x in row) for row in rows))\n',
    'sorted_of_sorted': 'rows = [[3, 1], [2], [9, 8, 7]]\n'
                        'print(sorted(sorted(v for v in row) for row in rows))\n',
    'list_of_list': 'rows = [[1, 2], [3], [], [4, 5, 6]]\n'
                    'print(list(list(x + 1 for x in row) for row in rows))\n',
    'side_effect_order': 'def src(row):\n    print("src", row)\n    return row\n\n'
                         'rows = [[1, 2], [3], []]\n'
                         'print("|".join(" ".join(str(y) for y in src(row)) for row in rows))\n'
                         'print("done")\n',
    'third_level': 'rows = [[[1, 2], [3]], [[4]]]\n'
                   'print(";".join("|".join(" ".join(str(z) for z in y) for y in x) for x in rows))\n',
    'inner_condition': 'rows = [[1, 0, 2], [3, 0], []]\n'
                       'print("|".join(" ".join(str(v) for v in row if v) '
                       'for row in rows if len(row) > 1))\n',
    'routes': 'def show(rows):\n    return " ".join("+".join(str(y) for y in row) for row in rows)\n\n'
              'class Box:\n    def __init__(self, rows):\n        self.rows = rows\n\n'
              'd = {"rows": [[1, 2], [3]]}\n'
              'xs = [[4], [5, 6]]\n'
              'b = Box([[7, 8]])\n'
              'print(show([[9, 10], []]))\n'
              'print(" ".join("+".join(str(y) for y in row) for row in xs[0:1]))\n'
              'print(" ".join("+".join(str(y) for y in row) for row in d["rows"]))\n'
              'print(" ".join("+".join(str(y) for y in row) for row in b.rows))\n',
}

REFUSED = {
    'saved_inner': 'rows = [[1, 2], [3]]\nprint(list((y for y in row) for row in rows))\n',
    'for_outer': 'def src(n):\n    print("src", n)\n    return [n]\n\n'
                 'for total in (sum(y for y in src(x)) for x in [1, 2]):\n'
                 '    print("body", total)\n',
    'next_outer': 'def src(n):\n    print("src", n)\n    return [n, n + 1]\n\n'
                  'print(next(((y for y in src(x)) for x in [1, 2]), None))\n',
    'any_outer': 'print(any((y for y in [x]) for x in [1, 2]))\n',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Cov44(unittest.TestCase):
    def test_nested_generator_consumed_in_place(self):
        for name, text in sorted(PROGRAMS.items()):
            with self.subTest(name):
                check_program(self, name, text)

    def test_unsafe_nesting_stays_a_named_refusal(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, name, text, ['generator expression', 'nested'])


if __name__ == '__main__':
    unittest.main()
