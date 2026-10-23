"""Differential fuzz round 83: sorted/reversed over strings, tuples, dict keys, ranges and generators.

Found with small programs compared against CPython on both builds:

`reversed(<generator expression>)` is a TypeError in CPython (a generator has no __len__,
__getitem__ or __reversed__). This front end materialises a generator expression eagerly as a
list, so both builds silently reversed it: `list(reversed(x for x in [1, 2, 3]))` printed
[3, 2, 1] where CPython prints "typeerror", and the empty form printed []. The same wrong answer
came out when the generator travelled through a name, an argument, a list item, an attribute or
a dict value. Materialised generator expressions now carry a `from_generator` mark on their list
backing, and `ail_iter_reversed` raises the same TypeError as CPython. A real list built from the
generator (`list(g)`, `sorted(g)`, a list comprehension) has no mark and stays reversible.

The other shapes below (stable key=len ordering, reverse=, nested lists/tuples, dict keys and
items, negative-step ranges, comprehensions) are compared with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

GEN_REVERSED = '''def show(g) -> None:
    try:
        print(list(reversed(g)))
    except TypeError:
        print("typeerror")

def main() -> None:
    show(x for x in [1, 2, 3])
    show(x for x in [])
    g = (x for x in [1, 2, 3])
    show(g)
    h = (x for x in range(0))
    show(h)
    try:
        print(list(reversed(x for x in [1, 2, 3])))
    except TypeError as e:
        print(type(e).__name__)
    try:
        for x in reversed(y for y in [1, 2, 3]):
            print(x)
    except TypeError:
        print("typeerror")
    print("done")
main()
'''

GEN_REVERSED_SLOTS = '''class Box:
    def __init__(self) -> None:
        self.v: object = [1, 2, 3]

def show(g) -> None:
    try:
        print(list(reversed(g)))
    except TypeError:
        print("typeerror")

def main() -> None:
    items: list[object] = []
    items.append(x for x in [1, 2, 3])
    show(items[0])
    d: dict[str, object] = {}
    d["g"] = (x for x in [1, 2, 3])
    show(d["g"])
    b: Box = Box()
    b.v = (x for x in [1, 2, 3])
    show(b.v)
    show(list(x for x in [1, 2, 3]))
    show(sorted(x for x in [3, 1, 2]))
    show(tuple(x for x in [1, 2, 3]))
    show([x for x in (y for y in [1, 2, 3])])
    print("done")
main()
'''

SORTED_REVERSED = '''def gen():
    yield 3
    yield 1
    yield 2

def main() -> None:
    words: list[str] = ["bbb", "a", "cc", "dd", "e"]
    print(sorted(words, key=len))
    print(sorted(words, key=len, reverse=True))
    print(sorted(["aa", "b", "cc", "d"], key=len))
    t: tuple[str, ...] = ("bb", "a", "ccc")
    print(sorted(t, key=len))
    print(list(reversed(t)))
    print(sorted("cabba"))
    print(list(reversed("cabba")))
    d: dict[str, int] = {"b": 2, "a": 1, "c": 3}
    print(sorted(d), sorted(d.keys()), sorted(d.values()))
    print(list(reversed(d.keys())))
    print(sorted(range(5)), list(reversed(range(5))))
    print(sorted(range(5, 0, -1)), list(reversed(range(5, 0, -1))))
    print(sorted(x * x for x in range(5)))
    print(sorted(gen()))
    nested: list[list[int]] = [[3], [1, 2], [9], [], [4, 5, 6], [7]]
    print(sorted(nested, key=len))
    print(sorted(nested, key=len, reverse=True))
    print(list(reversed([1, 2, 3])))
    print(list(reversed([x * x for x in range(4)])))
    g: list[int] = [x for x in [1, 2, 3]]
    print(list(reversed(g)))
main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
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
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz83Tests(unittest.TestCase):
    def same(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz83-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                got, build_err = _build_and_run(directory, name, text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_generator_expression_is_not_reversible(self):
        self.same('gen_reversed', GEN_REVERSED)
        self.same('gen_reversed_slots', GEN_REVERSED_SLOTS)

    def test_sorted_and_reversed_sequences(self):
        self.same('sorted_reversed', SORTED_REVERSED)


if __name__ == '__main__':
    unittest.main()
