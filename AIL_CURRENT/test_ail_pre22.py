"""Pre22: a `with` whose body yields in the same function is refused by name on both builds.

CPython runs the suspended body when the generator is closed and passes GeneratorExit to __exit__.
The general path's generator close finishes the fiber without running its frames, so a compiled
program would silently skip __exit__; the construct is refused instead of answered differently.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

WITH_YIELD = r'''class CM:
    def __enter__(self):
        print("enter")
        return self

    def __exit__(self, t, e, tb):
        print("exit", t, e)
        return False


def gen():
    with CM():
        yield 1


g = gen()
print(next(g))
g.close()
print("closed")
'''

WITHOUT_YIELD = r'''class CM:
    def __enter__(self):
        print("enter")
        return self

    def __exit__(self, t, e, tb):
        print("exit", t, e)
        return False


def gen():
    with CM():
        print("setup")
    yield 1
    with CM():
        print("done")


print(list(gen()))
'''


def build(directory, text, name, unified):
    source = Path(directory, name + '.ail')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                           '--syntax', 'python', '-o', name + '.exe'], cwd=directory,
                          capture_output=True, text=True, timeout=600, env=env)


class WithYield(unittest.TestCase):
    def test_refused_by_name(self):
        for unified in (True, False):
            with self.subTest(unified=unified), tempfile.TemporaryDirectory() as directory:
                built = build(directory, WITH_YIELD, 'wy', unified)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, output)
                self.assertIn('`with` around a `yield`', output)
                self.assertIn('GeneratorExit', output)

    def test_with_beside_yield_still_runs(self):
        expected = 'enter\nsetup\nexit None None\nenter\ndone\nexit None None\n[1]\n'
        for unified in (True, False):
            with self.subTest(unified=unified), tempfile.TemporaryDirectory() as directory:
                built = build(directory, WITHOUT_YIELD, 'wn', unified)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(Path(directory, 'wn.exe'))], capture_output=True, text=True, timeout=60)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertEqual(ran.stdout, expected)


if __name__ == '__main__':
    unittest.main()
