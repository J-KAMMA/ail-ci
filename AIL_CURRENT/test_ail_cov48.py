"""cov48: a chain of generator expressions read to exhaustion matches CPython on both builds.

The general path materialises a generator expression eagerly, so it used to refuse every
generator nested inside another one.  When every generator in the chain is read to exhaustion
by the construct around it (`join`, `list`, `tuple`, `sum`, `sorted`, a `for` source, `*`, an
unpacking target), eager materialisation has the same observable point as CPython's lazy
object: the inner generator is created and consumed while the outer element is evaluated, and
nothing outside can observe the difference.  Those chains now build.

A chain is still refused by name when a generator is only read for a prefix (`next`, `any`,
`all`) or stored as a value: there eager materialisation would run an element CPython never
reaches, so the saved/lazy refusal stays.  Every program is built with the general path forced
and with the default build; stdout and the exit status must match CPython 3.12.
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
    print(sum(x * 2 for x in (y for y in range(5))))
    print(list(x for x in (y for y in range(3))))
    print(tuple(x for x in (y for y in [-1, 0, 1])))
    print(sorted([x for x in (y for y in [3, 1, 2])]))
    print("|".join(str(x) for x in (y for y in [])))
    print(*[x for x in (y for y in [7, 8])])


main()
'''
PROGRAMS['three_levels'] = r'''
def main():
    rows = [[1, 2], [3]]
    print("\n".join(" ".join(str(v) for v in row) for row in (r for r in rows)))
    print(len(list(x for x in (y for y in (z for z in range(4))))))


main()
'''

REFUSED = {
    'saved_nested': 'g = (list(x for x in (y for y in range(3))) for _ in range(2))\nprint(next(g))\n',
    'next_inner_raises': 'print(list(next(1 // x for x in (y for y in [1, 0])) for _ in range(2)))\n',
    'inner_list_item': 'items = [(j for j in (k for k in range(2)))]\nprint(next(items[0]))\n',
    'for_source_raises': 'for v in (str(1 // x) for x in (y for y in [1, 0])):\n    print(v)\n',
    'saved_value': 'g = (1 // x for x in [1, 0])\nprint(next(g))\n',
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

    def test_prefix_consumed_nested_generators_are_refused(self):
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
