"""pre64: a bare annotation at module level evaluates its annotation expression.

CPython evaluates the annotation of `x: expr` at module and class level even though the
statement binds no value, so a call in `expr` is observable. The source pass used to drop
that expression, so `x: note('module')` printed nothing. A module-level annotation whose
whole expression is a call is now run as an expression statement, after the subexpressions
CPython evaluates for an attribute target's value or a subscript target's value and
index/slice. A class body is not run as code by this compiler, and a call nested in a larger
annotation cannot be split out without changing short-circuit evaluation, so both are refused
by name instead of silently losing the side effect. Function-local annotations are not
evaluated, as in CPython, and `from __future__ import annotations` turns evaluation off
everywhere.

Both builds (default and AIL_UNIFIED_FORCE=1) are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODULE_LEVEL = r'''def note(tag):
    print('annotation', tag)

x: note('module')

class Holder:
    pass

holder = Holder()
holder.value: note('attribute')
items = [0]
items[0]: note('subscript')

plain: int
names: list[str]
mapping: dict[str, int]

print('after')


def local():
    y: note('local')
    print('inside')


local()
'''

NESTED_CALL = r'''def note():
    print('side')


x: note() if True else int
print('after')
'''

CLASS_CALL = r'''def note():
    print('side')

class Holder:
    value: note()

print('after')
'''

TARGET_ORDER = r'''state = {'x': 0}

class Holder:
    pass

def note(tag):
    print('note', tag)

def touch(value):
    state['x'] = value
    return 0

def make(value):
    state['x'] = value
    return Holder()

items = [10]
items[touch(5)]: note(state['x'])
make(7).value: note(state['x'])

def lower():
    print('lower')
    return 0

def upper():
    print('upper')
    return 1

items[lower():upper()]: note('slice')
print('after')
'''

WALRUS_TARGET = r'''class Holder:
    pass

def note(value):
    print('note', value)

(h := Holder()).value: note(h is not None)
print('after')
'''

OBJECT_TARGET = r'''class Box:
    def __getitem__(self, index):
        print('getitem', index)
        return 7

def obj():
    print('obj')
    return Box()

def idx():
    print('idx')
    return 3

def note(tag):
    print('note', tag)

obj()[idx()]: note('subscript')
obj().value: note('attribute')
print('after')
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
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
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


class Pre64BareAnnotationTests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre64-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def check_refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre64-') as directory:
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNone(got, '%s (general=%s) built instead of being refused' % (text[:2000], general))
                self.assertIn('bare annotation', build_err, (text[:2000], general, build_err))

    def test_module_level_annotation_is_evaluated(self):
        self.check('module_level', MODULE_LEVEL)

    def test_target_subexpressions_are_evaluated(self):
        self.check('target_order', TARGET_ORDER)

    def test_walrus_target_is_evaluated(self):
        self.check('walrus_target', WALRUS_TARGET)

    def test_object_and_index_targets_are_evaluated(self):
        self.check('object_target', OBJECT_TARGET)

    def test_class_body_call_is_refused(self):
        self.check_refused('class_call', CLASS_CALL)

    def test_nested_call_is_refused(self):
        self.check_refused('nested_call', NESTED_CALL)


if __name__ == '__main__':
    unittest.main()
