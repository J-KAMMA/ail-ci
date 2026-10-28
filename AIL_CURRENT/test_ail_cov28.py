"""cov28: a nested generator expression consumed whole at the point it is written.

The general path materialises generator expressions eagerly.  That is exact only while the reader
consumes every element without an element-based failure before the end, so an inner generator that
is the sole argument of list/tuple/sorted, or of join on a string literal, no longer keeps the
nested-generator refusal.  A consumer that can raise mid-iteration (sum, min, max, bytes,
bytearray, set, frozenset, dict) and a generator used as a loop/comprehension source, by next()
or by any()/all() stays a named refusal on both builds.  Every program is compared with CPython
3.12.
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
    rows = [[3, 1, 2], [5], []]
    print([list(v for v in row) for row in rows])
    print([tuple(v for v in row) for row in rows])
    print([sorted(v for v in row) for row in rows])
    print(len(list(list(v for v in row) for row in rows)))
    print(tuple(tuple(v for v in row) for row in rows))
    print(sorted(sorted(v for v in row) for row in rows))
    print("\n".join(" ".join(str(v) for v in row) for row in rows))
    print("|".join("".join(str(v) for v in row) for row in [["a", "b"], ["c"]]))
    print(list(sorted(str(v) for v in row) for row in rows))
    print(tuple(list(v * 2 for v in row) for row in rows))


main()
'''

CASES['empty_negative'] = r'''def main():
    print([list(v for v in []) for _ in range(3)])
    print([tuple(v for v in range(-3, 0)) for _ in range(2)])
    print([sorted(v for v in range(0)) for _ in range(0)])
    print("\n".join(" ".join(str(v) for v in row) for row in [[], [], []]))
    print(list(list(v for v in range(-2, 0)) for _ in range(2)))


main()
'''

CASES['effects'] = r'''def tick(x):
    print("tick", x)
    return x


def main():
    print(list(list(tick(v) for v in row) for row in [[1, 2], [3]]))
    try:
        print(list(list(int(s) for s in row) for row in [["1"], ["x"], ["3"]]))
    except ValueError:
        print("caught ValueError")
    try:
        print(sorted(sorted(int(s) for s in row) for row in [["2"], ["x"], ["3"]]))
    except ValueError:
        print("caught ValueError")
    print("\n".join(" ".join(str(tick(v)) for v in row) for row in [[1], [2]]))
    print("after")


main()
'''

CASES['routes'] = r'''class Box:
    def __init__(self, rows):
        self.rows = rows


def reshape(rows):
    return [sorted(v for v in row) for row in rows]


def main():
    rows = [[3, 1], [2]]
    box = Box(rows)
    d = {"k": rows}
    items = [rows]
    print(reshape(rows))
    print(reshape(items[0]))
    print(reshape(box.rows))
    print(reshape(d["k"]))
    alias = rows
    print(reshape(alias))
    rows.append([4, 0])
    print(reshape(rows))
    print(reshape(items[0]))
    print(reshape(box.rows))
    print(reshape(d["k"]))


main()
'''

CASES['corpus_shapes'] = r'''def main():
    rows = [[1, 2], [3, 4]]
    print("\n".join(" ".join(str(v) for v in row) for row in rows))
    data = {"a": [[1, 2], [3]], "b": [[4]]}
    print("\n".join("\n".join(" ".join(str(v) for v in row) for row in data[k])
                    for k in sorted(data)))
    print(list(list(v for v in row) for row in rows))


main()
'''

REFUSED = {
    'list_source': 'print(list(x for x in (y for y in [1, 2])))\n',
    'next': 'print(next(x for x in (y for y in [1, 2])))\n',
    'shadowed_sorted': 'def sorted(x):\n    return x\n\n\n'
                       'print(list(sorted(x for x in (y for y in [1, 2])) for _ in range(1)))\n',
    'user_join': 'class J:\n    def join(self, x):\n        return "j"\n\n\n'
                 'print(list(J().join(x for x in (y for y in [1, 2])) for _ in range(1)))\n',
    'sum_mid_iteration': 'def f(v):\n    print("f", v)\n    return str(v)\n\n\n'
                         'print(list(sum(f(v) for v in row) for row in [[1], [2]]))\n',
    'min_mid_iteration': 'print(list(min(v for v in row) for row in [[1, 2]]))\n',
    'set_mid_iteration': 'print(list(set(v for v in row) for row in [[1, [2]]]))\n',
    'bytes_mid_iteration': 'print(list(bytes(v for v in row) for row in [[65, 300]]))\n',
    'dict_mid_iteration': 'print(list(dict(v for v in row) for row in [[(1, 2)]]))\n',
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
