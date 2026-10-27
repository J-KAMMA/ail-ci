"""pre360: textwrap.wrap / fill of text with a hyphen or a tab.

The pre352 review left the textwrap corpus-findings item unverified.  AIL's prelude helper
used to compile and then stop with ``RuntimeError: textwrap: text with a hyphen or a tab is
not built`` on both builds, where CPython prints a wrapped list.  CPython's default
TextWrapper expands tabs (``expandtabs(8)``), translates the remaining whitespace, splits
with its whitespace / em-dash / hyphen ``wordsep_re`` and breaks a long word after its last
hyphen; the helper now runs that algorithm.  These programs compare stdout and exit status
with CPython on the typed and the general build.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

HYPHEN_TAB = '''import textwrap
print(textwrap.wrap("a-b", 2))
print(textwrap.fill("a-b-c", 2))
print(textwrap.wrap("a\\tb", 2))
print(repr(textwrap.fill("a\\tb", 2)))
print(textwrap.wrap("well-known goof-ball", 6))
print(textwrap.fill("one two three-four five", 9))
'''

BOUNDARIES = '''import textwrap
print(textwrap.wrap("", 3))
print(textwrap.wrap("   ", 2))
print(textwrap.wrap("  lead", 3))
print(textwrap.wrap("trail  ", 3))
for w in [1, 2, 5, 70]:
    print(w, textwrap.wrap("ab-cde--fg h-i", w))
print(textwrap.wrap("ab\\tcd\\tef", 5))
print(textwrap.wrap("\\t\\tx", 4))
print(textwrap.wrap("a\\n\\tb", 4))
print(textwrap.wrap("a--b---c", 3))
print(textwrap.wrap("word -- word2", 6))
print(textwrap.wrap("x1-2y a1-b2", 4))
print(textwrap.wrap("\\u00e9-\\u00e0-ab", 3))
print(textwrap.fill("\\t  tab-led x-y", 4))
print(textwrap.wrap("a" * 12 + "-b", 5))
'''

ROUTES = '''import textwrap


def wrap_one(s: str, w: int) -> list[str]:
    return textwrap.wrap(s, w)


class Box:
    text: str = "co-op mode"

    def __init__(self, s: str) -> None:
        self.text = s


b = Box("goof-ball rule")
print(wrap_one("goof-ball", 5))
items: list[str] = ["a-b", "c\\td"]
print(textwrap.wrap(items[1], 2))
print(textwrap.wrap(b.text, 4))
vals: dict[str, str] = {"k": "x-y-z  end"}
print(textwrap.wrap(vals["k"], 3))
print(textwrap.fill("well-known", 6))
items[0] = "e-f-g"
print(textwrap.wrap(items[0], 3))
vals["k"] = "m\\tn"
print(textwrap.fill(vals["k"], 3))
b.text = "p-q-r"
print(textwrap.wrap(b.text, 2))
print(textwrap.wrap(Box.text, 3))
'''

WIDTHS = '''import textwrap
for w in [0, -1, -70]:
    try:
        textwrap.wrap("a-b", w)
    except ValueError as e:
        print("ValueError", e)
    try:
        textwrap.fill("a\\tb", w)
    except ValueError as e:
        print("ValueError", e)
'''


def random_program(seed=360):
    rng = random.Random(seed)
    lines = ['import textwrap']
    for _ in range(60):
        text = ''.join(rng.choice("ab -_1.\t\n") for _ in range(rng.randrange(0, 19)))
        width = rng.choice([1, 2, 3, 4, 5, 6, 7, 70])
        lines.append('print(textwrap.wrap(%r, %d))' % (text, width))
        lines.append('print(repr(textwrap.fill(%r, %d)))' % (text, width))
    return '\n'.join(lines) + '\n'


def compile_source(directory, name, source, general=False):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre360(unittest.TestCase):
    def compare(self, name, source, timeout=120):
        with tempfile.TemporaryDirectory() as directory:
            expected, status = run_cpython(directory, name, source)
        self.assertEqual(status, 0)
        self.assertTrue(expected)
        for general in (False, True):
            with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_source(directory, name, source, general=general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr[-3000:])
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=timeout)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)

    def test_hyphen_and_tab_match_cpython(self):
        self.compare('pre360_hyphen_tab', HYPHEN_TAB)

    def test_boundaries_match_cpython(self):
        self.compare('pre360_boundaries', BOUNDARIES)

    def test_routes_match_cpython(self):
        self.compare('pre360_routes', ROUTES)

    def test_invalid_width_matches_cpython(self):
        self.compare('pre360_widths', WIDTHS)

    def test_random_texts_match_cpython(self):
        self.compare('pre360_random', random_program())


if __name__ == '__main__':
    unittest.main()
