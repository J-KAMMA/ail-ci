"""cov29: a nested generator expression whose inner generator is consumed in place matches.

The general path materialises a generator expression when it is built.  It refused every
generator expression that contained another one, although `sum(...)`/`"".join(...)`/`any(...)`
read the inner generator whole at exactly the point CPython does.  The refusal now remains only
where the eager lowering would move an observable side effect: an inner generator saved as a
value, or an outer generator used as a for/comprehension source (its body interleaves with the
loop body).  Both builds are compared with CPython 3.12.
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
    'basic_eager': '''rows = [[1, 2], [3, 4]]
print(sum(sum(x for x in row) for row in rows))
print(" ".join(" ".join(str(v) for v in row) for row in rows))
''',
    'consumers': '''rows = [[3, 1], [2, 4]]
print(list(sum(x for x in row) for row in rows))
print(tuple(sum(x for x in row) for row in rows))
print(sorted(sum(x for x in row) for row in rows))
print(any(sum(x for x in row) > 5 for row in rows))
print(all(sum(x for x in row) > 2 for row in rows))
''',
    'next_outer': '''rows = [[1, 2], [3]]
print(next(sum(x for x in row) for row in rows))
print(next((sum(x for x in row) for row in rows), -1))
''',
    'empty_and_negative': '''rows = []
print(sum(sum(x for x in row) for row in rows))
print("|".join(" ".join(str(v) for v in row) for row in rows))
rows = [[-1, -2], [3, -4], [0]]
print(sum(sum(x for x in row) for row in rows))
print(sorted(sum(x for x in row) for row in rows))
''',
    'triple_nested': '''rows = [[[1, 2], [3]], [[4]]]
print(sum(sum(sum(z for z in y) for y in row) for row in rows))
''',
    'routes': '''def total(rows):
    return sum(sum(x for x in row) for row in rows)


class Box:
    def __init__(self, rows):
        self.rows = rows


rows = [[1, 2], [3, 4]]
item = [rows]
d = {"rows": rows}
box = Box(rows)
print(total(rows))
print(sum(sum(x for x in r) for r in item[0]))
print(sum(sum(x for x in r) for r in d["rows"]))
print(sum(sum(x for x in r) for r in box.rows))
''',
    'side_effect_order': '''def inner(x):
    print("inner", x)
    return x


def outer(row):
    print("outer", row)
    return row


rows = [[1, 2], [3]]
print(sum(sum(inner(x) for x in outer(row)) for row in rows))
''',
}

REFUSED = {
    'outer_for_source': '''for value in (sum(x for x in row) for row in [[1, 2]]):
    print(value)
''',
    'inner_saved_value': '''for value in ((y for y in row) for row in [[1], [2]]):
    print(list(value))
''',
}


class Cov29Tests(unittest.TestCase):
    def test_nested_eager_generator_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov29-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    tag = 'g' if general else 'd'
                    exe, built = build(directory, '%s_%s' % (slug, tag), text, general)
                    output = built.stdout + built.stderr
                    self.assertEqual(built.returncode, 0, (slug, general, output[-1500:]))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_interleaved_nested_generator_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov29-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    tag = 'g' if general else 'd'
                    _, built = build(directory, '%s_%s' % (slug, tag), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(NESTED, output, (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
