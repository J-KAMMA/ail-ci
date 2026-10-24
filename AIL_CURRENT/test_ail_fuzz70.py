"""Early exits and control: `assert` messages keep their object in `AssertionError.args`.

`assert cond, msg` raises `AssertionError(msg)` in CPython, so `e.args` is `(msg,)` for every
message type, and `str(e)` is `str(msg)`. The general path used to pass only `str(msg)` as the
argument (a tuple message became its quoted text in `e.args`), and a mixed-mode typed clone of a
helper that asserts could raise where the surrounding boxed `try` did not catch it. Both now match
CPython; the nested `return` / `break` / `sys.exit` cases in the same programs are controls.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ASSERT_MESSAGE_OBJECTS = r"""class Msg:
    def __init__(self, n):
        self.n = n

    def __str__(self):
        return "msg-%d" % self.n

    def __repr__(self):
        return "Msg(%d)" % self.n


def check(x):
    assert x > 0, "x must be positive"
    return x * 2


def main():
    print(check(3))
    for v in (0, -5):
        try:
            check(v)
        except AssertionError as e:
            print("AssertionError", str(e), e.args)
    try:
        assert False, ("a", 1)
    except AssertionError as e:
        print("tuple", str(e), e.args)
    try:
        assert False
    except AssertionError as e:
        print("bare", repr(str(e)), e.args)
    for m in (None, True, False, 0, 7, -3, 2.5, "text", "", (), [1, 2], {"k": 3}, {4, 5}, Msg(9)):
        try:
            assert False, m
        except AssertionError as e:
            print(repr(str(e)), repr(e.args), repr(e))


main()
"""

ASSERT_MIXED_HELPER = r"""def check(x):
    assert x > 0, "x must be positive"
    return x * 2


def scan(xs):
    for i, x in enumerate(xs):
        for j in range(3):
            if x == j:
                return (i, j)
            assert x >= 0, ("negative", x, i, j)
    return None


def main():
    print(check(3))
    for v in (0, -5):
        try:
            check(v)
        except AssertionError as e:
            print("AssertionError", str(e), e.args)
    try:
        assert False, ("a", 1)
    except AssertionError as e:
        print("tuple", str(e), e.args)
    print(scan([]), scan([1, 2]))
    try:
        scan([0, 1, -5])
    except AssertionError as e:
        print("scan", str(e), e.args)


main()
"""

EARLY_CONTROL = r"""import sys


def find(grid, target):
    for i in range(len(grid)):
        for j in range(len(grid[i])):
            if grid[i][j] == target:
                return (i, j)
    return (-1, -1)


def scan(xs, limit):
    i = 0
    out = []
    while True:
        if i >= len(xs):
            break
        x = xs[i]
        i += 1
        if x < 0:
            continue
        out.append(x)
        if sum(out) > limit:
            break
    return out, i


def main():
    grid = [[1, 2, 3], [4, 5, 6], [], [7]]
    for t in (1, 5, 7, 99, -3):
        print(t, find(grid, t))
    for xs, lim in (([1, 2, 3, 4, 5], 6), ([], 0), ([-1, -2], 0), ([10**9, 1], 10**9)):
        print(scan(xs, lim))
    sys.exit(0)


main()
"""

CASES = [
    ('assert_message_objects', ASSERT_MESSAGE_OBJECTS),
    ('assert_mixed_helper_nested_control', ASSERT_MIXED_HELPER),
    ('early_control_returns_break_exit0', EARLY_CONTROL),
]


def build_and_run(directory, text, name, ir, force_general=False):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_IR='1' if ir else '0', AIL_NO_CACHE='1')
    if force_general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=600, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected


class Fuzz70(unittest.TestCase):
    def check(self, slug, text, ir, force_general=False):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = build_and_run(directory, text, slug, ir, force_general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                             ran.stderr)

    def test_cases_default(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug + '_d', text, False)

    def test_cases_ir(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug + '_ir', text, True)

    def test_general_path_assert_args(self):
        slug, text = CASES[0]
        self.check(slug + '_g', text, False, force_general=True)


if __name__ == '__main__':
    unittest.main()
