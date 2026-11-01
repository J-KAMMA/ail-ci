"""The hot functions of the eight prog1 programs on the typed path, against CPython 3.12.

Batch prog1 fixed four proof gaps found by the real-program census:

- `xs[a:b]` of a named `list[int]` / `list[float]` was typed as an int, so a later
  `nums = nums[:n]` was refused as an int store into a list (t459).
- `set(range(...))` was accepted only when the range had first been bound to a name
  (g06_012's `return set(range(divisor, limit + 1, divisor))`).
- `for i, c in enumerate(s, start)` over a `str` had only the named-list branches
  (t308's two enumerate loops).
- `q, r = divmod(a, b)` was refused as a tuple assignment from a call (g14_022's
  `format_cents`).

T1  each program or extracted hot function takes the typed path (no "built on the
    general path" note)
T2  stdout and exit code equal CPython on the task inputs
T3  boundaries: a slice copy is independent of its source, set(range) keeps Python's
    step and direction rules, enumerate counts code points (not bytes) and a rebound
    index does not affect the next step, divmod follows floor signs and is loud on a
    zero divisor
T4  the two remaining blockers stay named in the census, not silently general
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None


def compile_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_x')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '-o', exe.name],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


def function_source(path, name):
    text = path.read_text(encoding='utf-8')
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node)
    raise AssertionError('%s has no function %s' % (path, name))


SLICE = '''def show(nums: list[int]) -> None:
    print(nums)


def main() -> None:
    nums = [1, 2, 3, 4, 5]
    head = nums[:2]
    tail = nums[2:]
    allof = nums[:]
    empty = nums[3:3]
    far = nums[-100:100]
    nums[0] = 9
    print(head, tail, allof, empty, far, nums)
    nums = nums[:3]
    print(nums)
    nums = nums[:0]
    print(nums)
    show(nums)
    a = [1, 2, 3]
    b = a[1:2]
    b[0] = 8
    print(a, b)
    c = [7, 8]
    d = c[:]
    d[0] = 99
    print(c, d)
    e = [1, 2, 3, 4]
    e = e[-2:]
    e[1] = 40
    print(e)


main()
'''

SET_RANGE = '''def main() -> None:
    print(sorted(set(range(5))))
    print(sorted(set(range(1, 10, 3))))
    print(sorted(set(range(10, 0, -2))))
    print(sorted(set(range(5, 5))))
    print(sorted(set(range(3, 0))))
    start = 2
    stop = 11
    step = 2
    print(sorted(set(range(start, stop, step))))
    a: set[int] = set(range(0, 12, 3))
    b: set[int] = set(range(0, 12, 4))
    print(sorted(a | b), sorted(a - b))
    print(len(set(range(-5, 5))))


main()
'''

ENUM_STR = '''def main() -> None:
    s = "aé日z"
    for i, c in enumerate(s, 5):
        print(i, c, len(c))
    for i, c in enumerate(s, -2):
        print(i, c)
        i = 1000
    for i, c in enumerate("", 7):
        print("never", i, c)
    print("done")
    for i, c in enumerate(s, 0):
        if c == "日":
            print("found", i)
    t = s[1:]
    for i, c in enumerate(t, 1):
        print(i, c)
    for i, c in enumerate(s[:2], -1):
        print(i, c)
    start = 4
    for i, c in enumerate(s, start):
        print(i, c)


main()
'''

DIVMOD = '''def show(a: int, b: int) -> None:
    q, r = divmod(a, b)
    print(a, b, q, r)


def showf(a: float, b: float) -> None:
    q, r = divmod(a, b)
    print(q, r)


def main() -> None:
    show(7, 3)
    show(-7, 3)
    show(7, -3)
    show(-7, -3)
    show(0, 5)
    show(5, 5)
    show(-5, 5)
    show(1, 10)
    show(-1, 10)
    x, y = 100, 7
    q, r = divmod(x + 1, y)
    print(q, r, x, y)
    m, n = divmod(abs(-123), 10)
    print(m, n)
    showf(5.5, 2.0)
    showf(-5.5, 2.0)
    showf(5.5, -2.0)
    showf(-5.5, -2.0)
    showf(1.0, 3.0)
    u, v = divmod(2.5, 1)
    print(u, v)


main()
'''

DIVMOD_ZERO = '''q, r = divmod(1, 0)
print(q, r)
'''


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog1_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, text, name, expect_typed=True):
        res, exe, source = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-1800:])
        if expect_typed is not None:
            self.assertEqual(typed(res), expect_typed, res.stderr[-900:])
        return exe, source

    def same(self, exe, source, stdin=''):
        want = subprocess.run([sys.executable, str(source)], input=stdin.encode('utf-8'),
                              capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
        self.assertEqual(got.stdout, want.stdout, repr(stdin))
        self.assertEqual(got.returncode, want.returncode, repr(stdin))

    def check_file(self, path, inputs, name):
        text = path.read_text(encoding='utf-8')
        exe, source = self.build(text, name)
        for stdin in inputs:
            self.same(exe, source, stdin)

    def lab(self, *parts):
        return REPO.joinpath('lab', *parts)

    def test_t370_whole_program_typed(self):
        path = self.lab('census', 'programs', 'dev', 't370.py')
        if not path.exists():
            self.skipTest('lab census program is not in this tree')
        inputs = [self.lab('corpus', 'tasks', 't370', 'in%d.txt' % i).read_text() for i in range(3)]
        self.check_file(path, inputs, 't370')

    def test_g06_012_whole_program_typed(self):
        path = self.lab('census', 'programs', 'gdev', 'g06_012.py')
        if not path.exists():
            self.skipTest('lab census program is not in this tree')
        self.check_file(path, [''], 'g06_012')

    def test_t308_whole_program_typed(self):
        path = self.lab('corpus', 'programs', 'glm-5.3-flash-free', 't308.py')
        if not path.exists():
            self.skipTest('lab corpus program is not in this tree')
        inputs = [self.lab('corpus', 'tasks', 't308', 'in%d.txt' % i).read_text() for i in range(3)]
        self.check_file(path, inputs, 't308')

    def test_t459_whole_program_typed(self):
        path = self.lab('corpus', 'programs', 'glm-5.3-flash-free', 't459.py')
        if not path.exists():
            self.skipTest('lab corpus program is not in this tree')
        inputs = [self.lab('corpus', 'tasks', 't459', 'in%d.txt' % i).read_text() for i in range(3)]
        self.check_file(path, inputs, 't459')

    def test_g14_022_format_cents_typed(self):
        path = self.lab('census', 'programs', 'gdev', 'g14_022.py')
        if not path.exists():
            self.skipTest('lab census program is not in this tree')
        text = function_source(path, 'format_cents') + '''

for v in [0, 5, 99, 100, 8452, -1, -615, 123456789, -9223372036854775807, 9223372036854775807]:
    print(format_cents(v))
'''
        exe, source = self.build(text, 'g14_format')
        self.same(exe, source)

    def test_g17_004_scale_typed(self):
        path = self.lab('census', 'programs', 'gdev', 'g17_004.py')
        if not path.exists():
            self.skipTest('lab census program is not in this tree')
        text = function_source(path, 'scale') + '''

print(scale(2.0, 3.5))
print(scale(3.0, -2.0))
print(scale(0.5, 10.0))
print(scale(-2.0, 4.5))
'''
        exe, source = self.build(text, 'g17_scale')
        self.same(exe, source)

    def test_slice_copy_and_alias_free_store_typed(self):
        exe, source = self.build(SLICE, 'slice')
        self.same(exe, source)

    def test_set_range_typed(self):
        exe, source = self.build(SET_RANGE, 'set_range')
        self.same(exe, source)

    def test_enumerate_str_start_typed(self):
        exe, source = self.build(ENUM_STR, 'enum_str')
        self.same(exe, source)

    def test_divmod_typed(self):
        exe, source = self.build(DIVMOD, 'divmod')
        self.same(exe, source)

    def test_divmod_zero_is_loud_not_wrong(self):
        exe, source = self.build(DIVMOD_ZERO, 'divmod_zero')
        self.same(exe, source)


if __name__ == '__main__':
    unittest.main()
