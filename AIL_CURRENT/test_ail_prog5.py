"""Hot functions of the prog5 programs that now take the typed path, against CPython 3.12.

The typed path is the default `compile --syntax python` build (the note "built on the general
path" means it was not taken).  A program that builds typed compiles every hot function in it.

T1  gdev g07_022 (consecutive groups) builds typed after the nested-list pass learned the
    `rows = []; rows.append([...])` shape iterlower leaves behind (and `groupby` pairs).
T2  gdev g06_014 (str sets) builds typed after `set(s)` over a str and `set(a) & set(b)`.
T3  t243 and g18_038 stay on the typed path.
T4  a `Callable[[], None]` / `Callable[[Exception], str]` pair builds typed.
T5  stdout and exit status equal CPython on ordinary, empty and boundary inputs.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / 'lab'
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

CALLABLE = '''from typing import Callable


def fail() -> None:
    raise ValueError("boom")


def noop() -> None:
    return None


def label(exc: Exception) -> str:
    return "caught"


def run(trigger: Callable[[], None], recover: Callable[[Exception], str]) -> str:
    try:
        trigger()
    except ValueError as exc:
        return recover(exc)
    return "none"


def main() -> None:
    print(run(fail, label))
    print(run(noop, label))


if __name__ == "__main__":
    main()
'''

ROWS = '''def build(n: int) -> list[list[int]]:
    rows: list[list[int]] = []
    for i in range(n):
        rows.append([i, i + 1, -i])
    return rows


def total(rows: list[list[int]]) -> int:
    t = 0
    for row in rows:
        for value in row:
            t += value
    return t


def main() -> None:
    for n in (0, 1, 2, 5):
        rows = build(n)
        print(n, total(rows), len(rows))
        for row in rows:
            print(row)
    rows = build(3)
    alias = rows
    alias[0].append(99)
    print(total(rows), rows[0][0], len(rows[0]))


if __name__ == "__main__":
    main()
'''


def compile_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_x')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_SERVER='0')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                          source.name, '-o', exe.name], cwd=directory, capture_output=True,
                         text=True, timeout=900, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog5_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, text, name):
        res, exe, source = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-800:])
        return exe, source

    def same(self, exe, source, stdin=''):
        want = subprocess.run([sys.executable, str(source)], input=stdin.encode('utf-8'),
                              capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True,
                             timeout=300)
        self.assertEqual(got.stdout, want.stdout, repr(stdin))
        self.assertEqual(got.returncode, want.returncode, repr(stdin))

    def check_program(self, relative, name, inputs=('',)):
        path = LAB / relative
        if not path.is_file():
            self.skipTest('lab is not part of this tree')
        text = path.read_text(encoding='utf-8')
        exe, source = self.build(text, name)
        for stdin in inputs:
            self.same(exe, source, stdin)

    def test_groupby_nested_list_typed(self):
        self.check_program('census/programs/gdev/g07_022.py', 'g07_022')

    def test_set_of_str_typed(self):
        self.check_program('census/programs/gdev/g06_014.py', 'g06_014')

    def test_stdin_dp_typed(self):
        self.check_program('corpus/programs/deepseek-v4.1-flash-free/t243.py', 't243',
                           ('3 3\n123\n456\n789\n', '1 1\n7\n', '2 4\n1234\n5678\n'))

    def test_deque_maxlen_typed(self):
        self.check_program('census/programs/gdev/g18_038.py', 'g18_038')

    def test_callable_exception_typed(self):
        exe, source = self.build(CALLABLE, 'callable')
        self.same(exe, source)

    def test_rows_appended_typed(self):
        exe, source = self.build(ROWS, 'rows')
        self.same(exe, source)


class CallableAnnotation(unittest.TestCase):
    def test_python_spellings_exception_and_none(self):
        import ast
        sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
        try:
            import callable_types
            for text, params, result in (
                    ('Callable[[], None]', (), 'noret'),
                    ('Callable[[Exception], str]', ('exception',), 'str')):
                kind = callable_types.parse(ast.parse(text, mode='eval').body)
                self.assertEqual(callable_types.unpack(kind), (params, result))
                self.assertEqual(callable_types.parse(
                    ast.parse(callable_types.annotation(kind), mode='eval').body), kind)
        finally:
            sys.path.pop(0)


if __name__ == '__main__':
    unittest.main()
