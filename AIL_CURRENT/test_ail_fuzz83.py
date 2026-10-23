"""Differential fuzz round 83: sorted/reversed over strings, tuples, dict keys, ranges and generators.

Found with small programs compared against CPython on both builds:

`reversed(<generator expression>)` is a TypeError in CPython (a generator has no __len__,
__getitem__ or __reversed__). This front end materialises a generator expression eagerly as a
list, so both builds silently reversed it: `list(reversed(x for x in [1, 2, 3]))` printed
[3, 2, 1] where CPython prints "typeerror", and the empty form printed []. A name bound to a
generator expression in the same scope had the same wrong answer. The front end now refuses
`reversed()` of a generator expression by name, before either emitter sees it.

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

GEN_REVERSED_DIRECT = '''def main() -> None:
    try:
        print(list(reversed(x for x in [1, 2, 3])))
    except TypeError:
        print("typeerror")
    try:
        print(list(reversed((y * 2 for y in range(4)))))
    except TypeError:
        print("typeerror")
    try:
        print(list(reversed((z for z in []))))
    except TypeError:
        print("typeerror")
main()
'''

GEN_REVERSED_NAME = '''def main() -> None:
    g = (x for x in [1, 2, 3])
    try:
        print(list(reversed(g)))
    except TypeError:
        print("typeerror")
    h = (y for y in [])
    try:
        print(list(reversed(h)))
    except TypeError:
        print("typeerror")
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


def _build(directory, name, text, general):
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
    return built, exe


class Fuzz83Tests(unittest.TestCase):
    def refused(self, text, word):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz83-') as directory:
            for general in (True, False):
                built, _ = _build(directory, 'gen_reversed_%s' % ('g' if general else 'd'), text, general)
                self.assertNotEqual(built.returncode, 0, 'built a program CPython rejects')
                self.assertIn(word, built.stdout + built.stderr)

    def same(self, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz83-') as directory:
            want, want_rc, err = _cpython(directory, 'same', text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                name = 'same_%s' % ('g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want,
                                 'general=%s\n%s' % (general, text[:2000]))
                self.assertEqual(got.returncode, 0)

    def test_generator_expression_is_not_reversible(self):
        for text in (GEN_REVERSED_DIRECT, GEN_REVERSED_NAME):
            self.refused(text, 'generator expression')

    def test_sorted_and_reversed_sequences(self):
        self.same(SORTED_REVERSED)


if __name__ == '__main__':
    unittest.main()
