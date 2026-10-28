# -*- coding: utf-8 -*-
"""ex1: a Python-surface file of definitions and module constants runs nothing, like CPython.

CPython runs the file and executes each top-level statement; a `def` only binds a name and a
literal module constant has no side effect, so a file made only of those (plus imports, a
docstring, `pass`) prints nothing and exits 0.  The typed path instead treated the last `def` as
the entry point and refused it ("the first parameter must be the sequence read from the file")
or demanded a FILE/int argument, while the general path already ran only the module body.  When
the file also has at least one module-constant assignment, the typed path now emits a `main`
that runs nothing.  Pure definitions with no top-level statement keep the last-def entry
convention, and any top-level statement CPython would execute (a call, a computed assignment,
`main()` never called) keeps its previous refusal or execution.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None

SILENT = [
    ('minimal', 'LIMIT = 5\n\ndef helper(x):\n    return x + LIMIT\n'),
    ('const_only', 'LIMIT = 5\n'),
    ('numbers', 'I = -7\nF = 2.5\nS = "text"\nXS = [1, 2, 3]\nYS = (1.5, -2.5)\nSS = ["a", "b"]\n\n'
                'def helper(x):\n    return x\n'),
    ('bounds', 'BIG = 9223372036854775807\nSMALL = -9223372036854775808\nEMPTY = ""\n\n'
               'def helper(x):\n    return x\n'),
    ('annotated', 'LIMIT: int = 5\n\ndef helper(x):\n    return x + LIMIT\n'),
    ('docstring_import', '"""doc"""\nimport math\n\npass\n\nLIMIT = 5\n\n'
                         'class Box:\n    def __init__(self):\n        self.value = LIMIT\n\n'
                         'def helper(x):\n    return math.isqrt(x)\n'),
    ('folded_alias', 'LIMIT = 5\nALIAS = LIMIT\n\ndef helper(x):\n    return x\n'),
    ('zero_arg_def', 'LIMIT = 5\n\ndef show():\n    print(LIMIT)\n'),
    ('class_const', 'LIMIT = 5\n\nclass Box:\n    def __init__(self):\n        self.value = LIMIT\n\n'
                    'def helper(x):\n    return x\n'),
]

ROUTES = [
    ('call_arg', 'LIMIT = 5\n\ndef helper(x):\n    return x + LIMIT\n\nprint(helper(3))\n'),
    ('computed', 'LIMIT = 5\ntotal = LIMIT + 1\n\ndef helper(x):\n    return x\n\nprint(total)\n'),
    ('dict_attr', "LIMIT = 5\nSETTINGS = {'limit': 3}\n\nclass Box:\n    def __init__(self):\n"
                  "        self.n = LIMIT\n\ndef pick(d):\n    return d['limit']\n\n"
                  "b = Box()\nprint(pick(SETTINGS), b.n)\n"),
    ('list_item', 'NUMBERS = [10, 20, 30]\nLIMIT = 2\n\ndef at(xs, i):\n    return xs[i] + LIMIT\n\n'
                  'print(at(NUMBERS, 1))\n'),
]

DEF_TIME = 'LIMIT = 5\n\ndef helper(x=print("default")):\n    return x\n'

UNCALLED_MAIN = 'LIMIT = 5\n\ndef main():\n    print(LIMIT)\n'

DEF_ONLY = 'def helper(x):\n    return x\n'

DECORATED = 'LIMIT = 5\n\ndef deco(fn):\n    print("decorated")\n    return fn\n\n' \
            '@deco\ndef helper(x):\n    return x\n'


def build(directory, source, general, name='p'):
    path = Path(directory, name + '.py')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, name + ('_g' if general else '_d'))
    if exe.exists():
        exe.unlink()
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    done = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(path),
                           '--syntax', 'python', '-o', str(exe)],
                          cwd=directory, capture_output=True, text=True, timeout=300, env=env)
    return done, exe


def cpython(directory, source, name='ref'):
    path = Path(directory, name + '.py')
    path.write_text(source, encoding='utf-8')
    return subprocess.run([sys.executable, str(path)], cwd=directory,
                          capture_output=True, text=True, timeout=120)


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class NoModuleBody(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-ex1-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_both(self, source, name='p'):
        expected = cpython(self.dir, source, name + '_ref')
        self.assertEqual(expected.returncode, 0, expected.stderr)
        for general in (False, True):
            built, exe = build(self.dir, source, general, name)
            where = 'general' if general else 'default'
            self.assertEqual(built.returncode, 0, where + ':\n' + built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            yield where, expected, ran

    def test_definitions_and_constants_run_nothing(self):
        for name, source in SILENT:
            for where, expected, ran in self.run_both(source, name):
                self.assertEqual(ran.returncode, expected.returncode, where + '\n' + source)
                self.assertEqual(ran.stdout, expected.stdout, where + '\n' + source)
                self.assertEqual(ran.stdout, '', where + '\n' + source)

    def test_executed_top_level_statements_still_run(self):
        for name, source in ROUTES:
            for where, expected, ran in self.run_both(source, name):
                self.assertEqual(ran.returncode, expected.returncode, where + '\n' + source)
                self.assertEqual(ran.stdout, expected.stdout, where + '\n' + source)
                self.assertNotEqual(ran.stdout, '', where + '\n' + source)

    def test_default_expression_runs_at_definition_time(self):
        expected = cpython(self.dir, DEF_TIME)
        self.assertEqual(expected.stdout, 'default\n')
        for where, _, ran in self.run_both(DEF_TIME, 'defaults'):
            self.assertEqual(ran.returncode, expected.returncode, where + '\n' + ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout, where)

    def test_uncalled_main_is_still_refused(self):
        for general in (False, True):
            built, exe = build(self.dir, UNCALLED_MAIN, general, 'uncalled')
            self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn('main() is defined but never called', built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_def_only_keeps_its_entry_convention(self):
        # No top-level statement: the last-def entry convention is untouched.
        built, exe = build(self.dir, DEF_ONLY, False, 'defonly')
        self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn('the first parameter must be the sequence read from the file',
                      built.stdout + built.stderr)
        self.assertFalse(exe.exists())
        built, exe = build(self.dir, DEF_ONLY, True, 'defonly')
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.returncode, 2, ran.stderr)
        self.assertIn('usage:', ran.stderr)

    def test_decorated_definition_is_not_a_silent_noop(self):
        # The typed path does not run decorators; the no-op main must not hide that.
        built, exe = build(self.dir, DECORATED, False, 'decorated')
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.returncode, 2, ran.stderr)
        self.assertIn('usage:', ran.stderr)
        built, exe = build(self.dir, DECORATED, True, 'decorated')
        self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn('the decorator on def helper', built.stdout + built.stderr)
        self.assertFalse(exe.exists())


if __name__ == '__main__':
    unittest.main()
