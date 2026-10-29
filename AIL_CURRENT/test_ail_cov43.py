"""cov43: a nested generator expression matches CPython when every level is fully consumed in place.

A generator expression nested inside another one was refused unconditionally (except inside
any/all): materialising the inner one eagerly was not the same as CPython's lazy evaluation.  When
the inner expression is an argument of a call that reads every element before returning (join,
sum, list, sorted, ...) and the outer expression is consumed the same way, the materialisation
point is the same one CPython uses, so these programs now match.  An inner expression that is
saved as a value, passed to next() (one element only) or read in a condition is still refused by
name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
MESSAGE = 'a generator expression nested inside another generator expression'


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


MATCHING = {
    'join_join': 'rows = [[1, 2], [3, 4], [5, 6]]\n'
                 'print("\\n".join(" ".join(str(v) for v in row) for row in rows))\n',
    'join_empty': 'rows = []\n'
                  'print("\\n".join(" ".join(str(v) for v in row) for row in rows))\n'
                  'print("\\n".join(" ".join(str(v) for v in row) for row in [[]]))\n',
    'join_sum': 'rows = [[1, 2, 3], [4, 5, 6]]\n'
                'print("|".join(str(sum(r[i] for r in rows)) for i in range(3)))\n'
                'print("|".join(str(sum(r[i] for r in rows)) for i in range(0)))\n',
    'three_levels': 'cube = [[[1, 2], [3]], [[4], [5, 6]]]\n'
                    'print("\\n".join("|".join(",".join(str(z) for z in plane) for plane in row) '
                    'for row in cube))\n',
    'tuple_rows': 'rows = [(1, 2), (3, 4)]\n'
                  'print("\\n".join(",".join(str(v) for v in row) for row in rows))\n',
    'negative': 'print("\\n".join(" ".join(str(v) for v in row) for row in [[-1, -2], [-3, -4]]))\n',
    'argument': 'def render(rows):\n'
                '    return "\\n".join(" ".join(str(v) for v in row) for row in rows)\n'
                'print(render([[10, 20], [30]]))\n',
    'list_item': 'groups = [[[1, 2], [3]], [[4]]]\n'
                 'print("\\n".join(" ".join(str(v) for v in row) for row in groups[0]))\n',
    'attribute': 'class Box:\n'
                 '    def __init__(self, rows):\n'
                 '        self.rows = rows\n'
                 '    def text(self):\n'
                 '        return "/".join("+".join(str(v) for v in row) for row in self.rows)\n'
                 'print(Box([[1, 2], [3]]).text())\n',
    'dict_value': 'd = {"rows": [[1, 2], [3, 4]]}\n'
                  'print("\\n".join(" ".join(str(v) for v in row) for row in d["rows"]))\n',
    'sorted_inner': 'rows = [["b", "a"], ["d", "c"]]\n'
                    'print("\\n".join(" ".join(sorted(v for v in row)) for row in rows))\n',
    'list_consumer': 'rows = [[1, 2], [3]]\n'
                     'print(list(list(str(v) for v in row) for row in rows))\n',
}

REFUSED = {
    'saved_inner': 'rows = [[1, 2], [3, 4]]\n'
                   'g = (list(str(v) for v in row) for row in rows)\n'
                   'print(list(g))\n',
    'saved_outer': 'rows = [[1, 2], [3, 4]]\n'
                   'g = (" ".join(str(v) for v in row) for row in rows)\n'
                   'print(list(g))\n',
    'next_inner': 'rows = [[1, 2], [3, 4]]\n'
                  'print("\\n".join(str(next(str(v) for v in row)) for row in rows))\n',
    'inner_in_condition': 'rows = [[1, 2], [3, 4]]\n'
                          'print("\\n".join(str(v) for row in rows for v in row '
                          'if (x for x in [0])))\n',
}


class Cov43Tests(unittest.TestCase):
    def test_fully_consumed_nested_genexps_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov43-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                       text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_partial_or_saved_nested_genexps_are_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov43-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                     text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(MESSAGE, output, (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
