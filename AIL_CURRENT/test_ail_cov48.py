"""cov48: a chain of generator expressions read immediately to exhaustion matches CPython.

The general path materialises a generator expression eagerly, so it used to refuse every
generator nested inside another one.  When a nested chain is read immediately and fully by a
trusted consumer (`list`, `tuple`, `set`, `sum`, a string-literal `.join`, ...), or when the
inner one is the iterable of an enclosing generator whose whole body is side effect free, eager
materialisation has the same observable order as CPython's lazy object.  Those chains build.

A chain is still refused by name when unpacking only reads a prefix, a for-clause source or a
stored value keeps the lazy object, `next`/`any`/`all` stop early, a user object's `join` may
read a prefix, or mutation during iteration could reach the inner generator.  Every accepted
program is built with the general path forced and with the default build; stdout and the exit
status must match CPython 3.12.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
NESTED = 'a generator expression nested inside another generator expression'
VALUE = 'a generator expression used as a value'

PROGRAMS = {}
PROGRAMS['join_routes'] = r'''
class Box:
    def __init__(self, rows):
        self.rows = rows


def render(rows):
    return "\n".join(" ".join(str(v) for v in row) for row in rows)


def main():
    rows = [[1, -2, 3], [], [4]]
    print(render(rows))
    print(render([[-1], [0, 8]]))
    print(render([rows]))
    box = Box([[-3, -4]])
    print(render(box.rows))
    d = {"k": [[5, 6]]}
    print(render(d["k"]))
    print(render(rows[0:2]))
    print(len("\n".join(" ".join(str(v) for v in row) for row in [])))


main()
'''
PROGRAMS['consume'] = r'''
def main():
    print(list(x for x in (y for y in range(3))))
    print(list(x * 2 for x in (y for y in range(4))))
    print(tuple(x for x in (y for y in range(3))))
    print(sum(sum(x for x in (y for y in row)) for row in [[1, 2], [], [-3]]))
    print("\n".join(x for x in (y for y in ["a", "b"])))
    print(list(x for x in (y for y in [])))


main()
'''
PROGRAMS['three_levels'] = r'''
def main():
    rows = [[1, 2], [3]]
    print(", ".join("; ".join("x" for _ in row) for row in rows))
    print(len(list(x for x in (y for y in (z for z in range(4))))))


main()
'''

REFUSED = {
    'saved_nested': 'g = (list(x for x in (y for y in range(3))) for _ in range(2))\nprint(next(g))\n',
    'next_inner_raises': 'print(list(next(1 // x for x in (y for y in [1, 0])) for _ in range(2)))\n',
    'inner_list_item': 'items = [(j for j in (k for k in range(2)))]\nprint(next(items[0]))\n',
    'for_source_raises': 'for v in (str(1 // x) for x in (y for y in [1, 0])):\n    print(v)\n',
    'saved_value': 'g = (1 // x for x in [1, 0])\nprint(next(g))\n',
    'mutation_during_iteration': (
        'xs = [1, 2, 3]\n'
        'def f(x):\n'
        '    if x == 1:\n'
        '        xs.append(4)\n'
        '    return x\n'
        'def main():\n'
        '    print(list(f(x) for x in (y for y in xs)))\n'
        'main()\n'),
    'unpack_short': (
        'def main():\n'
        '    try:\n'
        '        a, b = (x for x in (print("i", y) or y for y in range(5)))\n'
        '        print("ok", a, b)\n'
        '    except ValueError as e:\n'
        '        print("err", e)\n'
        'main()\n'),
    'custom_join_receiver': (
        'class C:\n'
        '    def join(self, it):\n'
        '        return next(it)\n'
        'def main():\n'
        '    print(C().join(x for x in (print("i", y) or y for y in range(3))))\n'
        'main()\n'),
    'unpack_nested': 'def main():\n    a, b = (x for x in (y for y in [4, 5]))\n    print(a, b)\nmain()\n',
    'starred_nested': 'def main():\n    print(*(x for x in (y for y in [1, 2, 3])))\nmain()\n',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Cov48Tests(unittest.TestCase):
    def test_fully_consumed_nested_generators_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov48-') as directory:
            for slug, text in PROGRAMS.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                       text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_unsafe_nested_generators_are_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov48-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                     text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertTrue(NESTED in output or VALUE in output,
                                    (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
