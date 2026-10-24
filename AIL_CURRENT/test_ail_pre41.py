"""pre41: a generator expression used as the iterable of an any()/all() genexpr.

The general path materialised the inner generator expression eagerly, so the
elements after the deciding one were produced anyway.  Laziness of a nested
generator cannot be modelled by the current emitter, so this shape is refused by
name at compile time instead of answering differently from CPython.  A generator
expression over a list, a range, an argument or a list comprehension is still
built (those iterables are eager in CPython too).

Both builds must either match CPython's stdout and exit status or refuse with the
name below.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSAL = 'iterable is itself a generator expression'


def cpython(directory, text):
    src = Path(directory) / 'p_cpython.py'
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, text, general):
    src = Path(directory) / 'p.ail'
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_g' if general else 'exe_d')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                src.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


NESTED = [
    ('direct_any', 'def main():\n    print(any(x for x in (y for y in [0, 1, 2])))\n\n\nmain()\n'),
    ('direct_all_empty', 'def main():\n    print(all(x for x in (y for y in [])))\n\n\nmain()\n'),
    ('filtered', 'def main():\n    print(all(x for x in (y for y in range(-2, 3)) if x > 0))\n\n\nmain()\n'),
    ('second_clause', 'def main():\n'
                      '    rows = [[0, 1], [2]]\n'
                      '    print(any(x for row in rows for x in (v for v in row)))\n\n\nmain()\n'),
    ('argument', 'def take(xs):\n    return any(x for x in (y for y in xs))\n\n\n'
                 'def main():\n    print(take([0, 1, 2]))\n\n\nmain()\n'),
    ('attribute', 'class Box:\n    def __init__(self, xs):\n        self.xs = xs\n\n\n'
                  'def main():\n    b = Box([0, 1])\n'
                  '    print(any(x for x in (y for y in b.xs)))\n\n\nmain()\n'),
    ('dict_value', 'def main():\n    d = {"k": [0, 1]}\n'
                   '    print(all(x for x in (y for y in d["k"])))\n\n\nmain()\n'),
    ('list_item', 'def main():\n    xs = [[0, 1], [2, 3]]\n'
                  '    print(any(x for x in (y for y in xs[0])))\n\n\nmain()\n'),
]

PLAIN = r'''def take(xs):
    return any(v > 1 for v in xs)


def main():
    print(any(x > 1 for x in [0, 2, 3]))
    print(all(x > 0 for x in [1, 2]))
    print(any(x for x in []), all(x for x in []))
    print(any(x for x in range(-1, 2)))
    print(take([0, 2]))
    print(any(x for x in [y for y in [0, 1, 2]]))
    print(all(x for x in [y for y in [1, 2]]))


main()
'''


class Pre41Tests(unittest.TestCase):
    def test_nested_generator_iterable_is_refused_by_name(self):
        for slug, program in NESTED:
            with self.subTest(slug), tempfile.TemporaryDirectory(prefix='ail-pre41-') as directory:
                for general in (True, False):
                    exe, built = build(directory, program, general)
                    self.assertNotEqual(built.returncode, 0, 'general=%s\n%s' % (general, built.stdout))
                    self.assertFalse(exe.exists())
                    self.assertIn(REFUSAL, built.stdout + built.stderr, 'general=%s' % general)
                    self.assertNotIn('Traceback', built.stdout + built.stderr)

    def test_eager_iterables_still_build_and_match(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre41-') as directory:
            want = cpython(directory, PLAIN)
            for general in (True, False):
                exe, built = build(directory, PLAIN, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], 'general=%s' % general)
                self.assertEqual(got.returncode, want[1], 'general=%s' % general)


if __name__ == '__main__':
    unittest.main()
