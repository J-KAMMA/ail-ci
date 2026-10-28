"""cov28: a nested generator expression consumed whole at the point it is written.

The general path materialises generator expressions eagerly.  That is exact while the reader
consumes every element immediately, so an inner generator that is the sole argument of a
fully-consuming builtin (sum/list/tuple/set/dict/sorted/min/max/bytes/Counter/... or
join/extend/update) no longer keeps the nested-generator refusal.  A generator used as a
loop/comprehension source, by next() or by any()/all() can stop early and stays a named
refusal on both builds.  Every program is compared with CPython 3.12.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFUSAL = 'a generator expression nested inside another generator expression'

CASES = {}

CASES['core'] = r'''def main():
    rows = [[1, 2], [3], []]
    print(sum(sum(v for v in row) for row in rows))
    print([sum(v for v in row) for row in rows])
    print("|".join("".join(str(v) for v in row) for row in rows))
    print(list(list(v for v in row) for row in rows))
    print(tuple(tuple(v for v in row) for row in rows))
    print(sorted(sorted(v for v in row) for row in rows))
    print(len(set(frozenset(v for v in row) for row in rows)))
    print(dict((str(i), dict((j, j) for j in range(i))) for i in range(3)))
    print(min(min(v for v in row) for row in rows if row))
    print(max(max(v for v in row) for row in rows if row))


main()
'''

CASES['empty_negative'] = r'''def main():
    print(sum(sum(v for v in []) for _ in range(3)))
    print(sum(sum(v for v in range(-3, 0)) for _ in range(2)))
    print(sum(sum(v for v in range(0)) for _ in range(0)))
    try:
        print(min(min(v for v in []) for _ in range(1)))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(max(max(v for v in []) for _ in range(1)))
    except ValueError as e:
        print("ValueError", e)


main()
'''

CASES['effects'] = r'''def tick(x):
    print("tick", x)
    return x


def main():
    print(sum(sum(tick(v) for v in row) for row in [[1, 2], [3]]))
    try:
        print(sum(sum(int(s) for s in row) for row in [["1"], ["x"]]))
    except ValueError as e:
        print("caught", e)
    print("after")


main()
'''

CASES['routes'] = r'''class Box:
    def __init__(self, rows):
        self.rows = rows


def total(rows):
    return sum(sum(v for v in row) for row in rows)


def main():
    rows = [[1, 2], [3]]
    box = Box(rows)
    d = {"k": rows}
    items = [rows]
    print(total(rows))
    print(total(items[0]))
    print(total(box.rows))
    print(total(d["k"]))
    alias = rows
    print(total(alias))
    rows.append([4])
    print(total(rows))
    print(total(items[0]))
    print(total(box.rows))
    print(total(d["k"]))


main()
'''

CASES['corpus_shapes'] = r'''def main():
    quarters = ("q1", "q2")
    data = {"a": {"q1": 1, "q2": 2}, "b": {"q1": 3, "q2": 4}}
    print("".join(f"{sum(data[r][q] for r in data):>7}" for q in quarters))
    rows = [[1, 2], [3, 4]]
    print("\n".join(" ".join(str(v) for v in row) for row in rows))
    print([sum(a * b for a, b in zip(row, row)) for row in rows])


main()
'''

REFUSED = {
    'list_source': 'print(list(x for x in (y for y in [1, 2])))\n',
    'next': 'print(next(x for x in (y for y in [1, 2])))\n',
    'shadowed_sum': 'def sum(x):\n    return 0\n\n\n'
                    'print(list(sum(x for x in (y for y in [1, 2])) for _ in range(1)))\n',
    'user_join': 'class J:\n    def join(self, x):\n        return "j"\n\n\n'
                 'print(list(J().join(x for x in (y for y in [1, 2])) for _ in range(1)))\n',
}


def build(directory, text, name, unified):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_IR', None)
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                           source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=600, env=env), exe


class Cov28Tests(unittest.TestCase):
    def check(self, slug, text, unified):
        with tempfile.TemporaryDirectory(prefix='ail-cov28-') as directory:
            built, exe = build(directory, text, slug + ('_g' if unified else '_d'), unified)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            expected = subprocess.run([sys.executable, '-c', text], capture_output=True, timeout=120)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout),
                             got.stderr)

    def test_allowed_default(self):
        for slug, text in CASES.items():
            with self.subTest(slug):
                self.check(slug, text, False)

    def test_allowed_unified(self):
        for slug, text in CASES.items():
            with self.subTest(slug):
                self.check(slug, text, True)

    def test_unsafe_nested_generator_refused_by_name(self):
        for slug, text in REFUSED.items():
            with self.subTest(slug), tempfile.TemporaryDirectory(prefix='ail-cov28-r-') as directory:
                for unified in (False, True):
                    built, exe = build(directory, text, slug + ('_g' if unified else '_d'), unified)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, output)
                    self.assertFalse(exe.exists())
                    self.assertIn(REFUSAL, output)
                    self.assertNotIn('Traceback', output)


if __name__ == '__main__':
    unittest.main()
