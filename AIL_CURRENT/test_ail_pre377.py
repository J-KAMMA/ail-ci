"""pre377: the general path names the class in item-error messages, as CPython does.

The pre354 reviewer recorded as pre-existing that an instance of ``class A`` without
``__getitem__`` raised ``TypeError: 'instance' object is not subscriptable`` where CPython
says ``'A'``.  The item operations built the message from the runtime tag, which is only
``instance``; they now use the runtime's existing object-to-name helper, which returns the
class's own name (and the subclass's name for a subclass).  The same cause covered item
assignment and deletion, and slicing an instance reaches the same message.  Builtin values
and instances that do define the item methods keep their previous behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CASES = {
    'instance_name': '''
class A:
    pass

a = A()
try:
    a[0]
except TypeError as e:
    print(type(e).__name__, e)
try:
    a[1:2]
except TypeError as e:
    print(type(e).__name__, e)
''',
    'routes': '''
class A:
    pass


class B(A):
    pass


class Holder:
    pass


def fetch(container, key):
    try:
        return container[key]
    except TypeError as e:
        return 'TypeError ' + str(e)


a = A()
b = B()
alias = a
holder = Holder()
holder.a = a
d = {'a': a}
xs = [a]
print(fetch(a, 0))
print(fetch(alias, 1))
print(fetch([a][0], 2))
print(fetch(holder.a, 3))
print(fetch(d['a'], 4))
print(fetch(xs[0], 5))
print(fetch(b, 0))
print(fetch(b, slice(1, 2)))
''',
    'setdel': '''
class A:
    pass

a = A()
try:
    a[0] = 1
except TypeError as e:
    print(type(e).__name__, e)
try:
    del a[0]
except TypeError as e:
    print(type(e).__name__, e)
''',
    'init_class': '''
class A:
    def __init__(self, x):
        self.x = x

a = A(5)
try:
    print(a[0])
except TypeError as e:
    print(type(e).__name__, e)
try:
    a[0] = 1
except TypeError as e:
    print(type(e).__name__, e)
try:
    del a[0]
except TypeError as e:
    print(type(e).__name__, e)
''',
    'builtins': '''
def show(obj, key):
    try:
        obj[key]
    except TypeError as e:
        print(e)


show(1, 0)
show(None, 0)
show(True, 0)
show(lambda: 1, 0)
show(3.5, 0)
show(b'x', 0)
''',
    'item_methods': '''
class C:
    def __getitem__(self, i):
        return i

    def __setitem__(self, i, v):
        print('set', i, v)

    def __delitem__(self, i):
        print('del', i)


c = C()
print(c[3])
print(c[1:2])
c[0] = 7
del c[0]
''',
    'dict_slice_control': '''
d = {1: 2}
try:
    print(d[1:2])
except KeyError as e:
    print('KeyError', e)
d[3:4] = 'x'
print(d[3:4], d[slice(3, 4)])
''',
}

UNCAUGHT = '''
class A:
    pass

print(A()[0])
'''


def compile_source(directory, name, source, general):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                          text=True, timeout=120)


def last_line(text):
    lines = [line for line in text.replace('\r\n', '\n').splitlines() if line.strip()]
    return lines[-1] if lines else ''


class Pre377(unittest.TestCase):
    def check(self, name, source, uncaught=False):
        with tempfile.TemporaryDirectory(prefix='ail-pre377-') as directory:
            want = run_cpython(directory, name, source)
            for general in (True, False):
                built, exe = compile_source(directory, name, source, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                     text=True, timeout=120)
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))
                self.assertEqual(got.stdout.replace('\r\n', '\n'), want.stdout,
                                 (name, general, got.stderr[-800:]))
                if uncaught:
                    self.assertEqual(last_line(got.stderr), last_line(want.stderr),
                                     (name, general, got.stderr[-800:]))

    def test_instance_item_errors(self):
        for name, source in CASES.items():
            with self.subTest(name=name):
                self.check(name, source)

    def test_uncaught_instance_subscript(self):
        self.check('uncaught', UNCAUGHT, uncaught=True)


if __name__ == '__main__':
    unittest.main()
