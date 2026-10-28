"""Pre418: a stored item of a class/instance container is folded in source order.

The pre401 review recorded that a function or lambda body was checked when it was
defined, so a module-level store into a known container that ran before the call was
invisible: ``class C: v = [1e300]`` / ``def f(): print(int(C.v[0]))`` / ``C.v[0] =
1.5`` / ``f()`` refused both builds with ``int() of a float outside int64`` where
CPython prints ``1``.  The same happened for a literal list in ``__init__``, an
attribute rebind and list/dict method calls.

The int() checker now applies module-level container stores in source order and
checks a module function or lambda body at its call site instead of at its
definition, so stores that ran before the call are seen.  A read that runs before a
later store keeps the existing named refusal.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre418-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre418-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


MATCH = {
    'instance_literal_function': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()


def f():
    print(int(c.v[0]))


c.v[0] = 1.5
f()
''',
    'class_literal_function': '''
class C:
    v = [1e300]


def f():
    print(int(C.v[0]))


C.v[0] = 1.5
f()
''',
    'class_store_before_comprehension': '''
class C:
    v = [1e300]

C.v[0] = 1.5
ys = [int(C.v[0]) for _ in range(1)]
print(ys)
''',
    'instance_literal_comprehension': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()


def f():
    return [int(c.v[0]) for _ in range(1)]


c.v[0] = 1.5
print(f())
''',
    'lambda_container': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()
f = lambda: print(int(c.v[0]))
c.v[0] = 1.5
f()
''',
    'nested_function_after_store': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()


def f():
    print(int(c.v[0]))


def g():
    f()


c.v[0] = 1.5
g()
''',
    'dict_value': '''
class C:
    def __init__(self):
        self.d = {"k": 1e300}

c = C()


def f():
    print(int(c.d["k"]))


c.d["k"] = 1.5
f()
''',
    'alias_store': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()
d = c


def f():
    print(int(c.v[0]))


d.v[0] = 1.5
f()
''',
    'negative_index': '''
class C:
    def __init__(self):
        self.v = [0.0, 1e300, 2.0]

c = C()


def f():
    print(int(c.v[-1]))


c.v[-1] = 1.5
f()
''',
    'insert_at_zero': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()


def f():
    print(int(c.v[0]))


c.v.insert(0, 1.5)
f()
''',
    'dynamic_store': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()


def f():
    print(int(c.v[0]))


i = 0
c.v[i] = 1.5
f()
''',
    'in_range_before_and_after': '''
class C:
    def __init__(self):
        self.v = [1.5]

c = C()
print(int(c.v[0]))
c.v[0] = 2.5
print(int(c.v[0]))
''',
    'argument_list_and_dict_routes': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()
c.v[0] = 1.5
xs = [c.v[0]]
d = {"k": c.v[0]}


def take(x):
    print(int(x))


take(xs[0])
take(d["k"])
take(c.v[0])
''',
    'scalar_attribute_control': '''
class C:
    def __init__(self, v):
        self.v = v

c = C(1.5)
c.v = 1e300


def f():
    print(int(c.v))


c.v = 2.5
f()
''',
    'scalar_function_control': '''
class C:
    def __init__(self, v):
        self.v = v

c = C(1e300)


def f():
    print(int(c.v))


c.v = 1.5
f()
''',
}

REFUSED = {
    'read_before_store_in_function': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()


def f():
    print(int(c.v[0]))


f()
c.v[0] = 1.5
''',
    'read_before_store_class_function': '''
class C:
    v = [1e300]


def f():
    print(int(C.v[0]))


f()
C.v[0] = 1.5
''',
    'read_before_store_module': '''
class C:
    v = [1e300]

c = C()
print(int(c.v[0]))
c.v[0] = 1.5
''',
    'read_before_store_nested': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()


def f():
    print(int(c.v[0]))


def g():
    f()


g()
c.v[0] = 1.5
''',
    'read_before_store_comprehension': '''
class C:
    v = [1e300]

ys = [int(C.v[0]) for _ in range(1)]
C.v[0] = 1.5
print(ys)
''',
    'append_keeps_old_first_item': '''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()
c.v.append(1e300)


def f():
    print(int(c.v[0]))


c.v.append(1.5)
f()
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class StoredContainerItemPre418(unittest.TestCase):
    def test_store_before_call_is_folded_in_order(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, name, text)

    def test_read_before_store_keeps_named_refusal(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, name, text)


if __name__ == '__main__':
    unittest.main()
