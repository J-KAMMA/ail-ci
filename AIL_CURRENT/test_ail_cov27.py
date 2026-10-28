"""Coverage 27: a generator expression nested inside another generator expression.

The general path materialises a generator expression eagerly.  A nested generator that is an
argument of a call which reads every element (sum, str.join, ...) is observationally the same
when materialised there, so those programs now build and match CPython.  A nested generator
that is saved as a value (the outer element, an outer iterable, next/any/all, ...) keeps its
named compile-time refusal.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['fstring_join'] = r'''def main():
    quarters = ("q1", "q2")
    data = {"north": {"q1": 0, "q2": 959}, "south": {"q1": 89, "q2": 0}}
    regions = sorted(data)
    print("".join(f"{q:>7}" for q in quarters) + f"{'total':>7}")
    for region in regions:
        print(f"{region:<7}" + "".join(f"{data[region][q]:>7}" for q in quarters) + f"{sum(data[region][q] for q in quarters):>7}")
    grand = sum(data[r][q] for r in regions for q in quarters)
    print(f"{'TOTAL':<7}" + "".join(f"{sum(data[r][q] for r in regions):>7}" for q in quarters) + f"{grand:>7}")
main()
'''
PROGRAMS['nested_join_repr'] = r'''class Matrix:
    def __init__(self):
        self.rows = [[1, 2], [3, 4]]
    def __repr__(self):
        return "\n".join(" ".join(str(v) for v in row) for row in self.rows)
def main():
    print(Matrix())
main()
'''
PROGRAMS['sum_zip_empty_negative'] = r'''def main():
    a = [[1, 2], [3, 4]]
    b = [[5, 6], [7, 8]]
    print(list(sum(x * y for x, y in zip(r, c)) for c in zip(*b) for r in a))
    rows = [[], [1], []]
    print(sum(sum(v for v in row) for row in rows))
    print("|".join("".join(str(v) for v in row) for row in rows))
    vals = [[-1, -2], [-(2 ** 62), 2 ** 62 - 1]]
    print(sum(sum(v for v in row) for row in vals))
    print(max(max(v for v in row) for row in vals))
main()
'''
PROGRAMS['routes'] = r'''class Box:
    def __init__(self, rows):
        self.rows = rows
def total(rows):
    return sum(sum(v * 2 for v in row) for row in rows)
def main():
    a = [[1, 2], [3]]
    print(total(a))
    items = [[[4, 5], [6]]]
    print(total(items[0]))
    b = Box([[7], [8, 9]])
    print(total(b.rows))
    d = {"k": [[10], [11, 12]]}
    print(total(d["k"]))
    total_alias = total
    print(total_alias(a) + total_alias(b.rows))
main()
'''
PROGRAMS['alias_result'] = r'''def main():
    rows = [[1, 2], [3, 4]]
    total = sum(sum(v for v in row) for row in rows)
    alias = total
    print(alias, alias * 2)
main()
'''

REFUSED = r'''def main():
    rows = [[1, 2], [3]]
    gens = ((y for y in row) for row in rows)
    print([list(g) for g in gens])
main()
'''

SHADOWED_SUM = r'''def main():
    log = []
    def side(i):
        log.append(i); return i
    def mysum(it):
        for v in it: return v
        return 0
    sum = mysum
    rows = [[1, 2], [3, 4]]
    print(list(sum(side(v) for v in row) for row in rows))
    print(log)
main()
'''

SHADOWED_JOIN = r'''log = []
def side(i):
    log.append(i); return str(i)
class C:
    def __init__(self): self.first = ""
    def join(self, it):
        for v in it:
            self.first = v; return v
        return "z"
def main():
    c = C()
    print(list(c.join(side(v) for v in row) for row in [[1,2],[3,4]]))
    print(log)
main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
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


class NestedGeneratorCoverage(unittest.TestCase):
    def check(self, slug, text, general):
        with tempfile.TemporaryDirectory(prefix='ail-cov27-') as directory:
            want = _cpython(directory, slug, text)
            got, err = _build_and_run(directory, slug, text, general)
            self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
            self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, err))

    def test_programs_default(self):
        for slug, text in sorted(PROGRAMS.items()):
            with self.subTest(slug):
                self.check(slug, text, False)

    def test_programs_unified(self):
        for slug, text in sorted(PROGRAMS.items()):
            with self.subTest(slug):
                self.check(slug, text, True)

    def assert_refused(self, slug, text, substring=None):
        with tempfile.TemporaryDirectory(prefix='ail-cov27-') as directory:
            for general in (True, False):
                got, message = _build_and_run(directory, '%s%d' % (slug, general), text, general)
                self.assertIsNone(got, '%s built (general=%s)\n%s' % (slug, general, message))
                self.assertIn('not in the subset', message)
                if substring is not None:
                    self.assertIn(substring, message)

    def test_nested_generator_value_is_refused(self):
        self.assert_refused('refuse', REFUSED, 'nested')

    def test_local_shadowing_of_a_consumer_name_is_refused(self):
        self.assert_refused('shadow_sum', SHADOWED_SUM)

    def test_user_method_named_like_a_consumer_is_refused(self):
        self.assert_refused('shadow_join', SHADOWED_JOIN)


if __name__ == '__main__':
    unittest.main()
