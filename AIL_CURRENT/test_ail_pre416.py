"""pre416: exception subclasses name their class in item-error messages.

The pre395 reviewer recorded as pre-existing that item access on an instance of a
user exception subclass raised ``TypeError: 'exception' object is not subscriptable``
where CPython says ``'E'``.  The general path already named ordinary class instances
in these messages (pre377) but its object-to-name helper treated ``AIL_T_EXC`` as the
generic tag ``exception``.  Exception values carry a class too, so item access,
assignment and deletion now use the subclass's name.  The same route covers a class
inherited from another exception class and long names, while exceptions that define
``__getitem__`` still use their own method.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CASES = {
    'exception_name': '''
class E(Exception):
    pass

e = E('x')
try:
    e[0]
except TypeError as err:
    print(type(err).__name__, err)
try:
    e[1:2]
except TypeError as err:
    print(type(err).__name__, err)
try:
    e[0] = 1
except TypeError as err:
    print(type(err).__name__, err)
try:
    del e[0]
except TypeError as err:
    print(type(err).__name__, err)
''',
    'direct_call': '''
class E(Exception):
    pass

try:
    E()[0]
except TypeError as err:
    print(err)
try:
    E()[1:2]
except TypeError as err:
    print(err)
''',
    'routes': '''
class E(Exception):
    pass


class F(E):
    pass


class Holder:
    pass


def fetch(container, key):
    try:
        return container[key]
    except TypeError as err:
        return 'TypeError ' + str(err)


e = E('m')
f = F('m')
alias = e
holder = Holder()
holder.e = e
d = {'e': e}
xs = [e]
print(fetch(e, 0))
print(fetch(e, -1))
print(fetch(e, True))
print(fetch(e, 'x'))
print(fetch(alias, 1))
print(fetch([e][0], 2))
print(fetch(holder.e, 3))
print(fetch(d['e'], 4))
print(fetch(xs[0], 5))
print(fetch(f, 0))
print(fetch(e, slice(None)))
print(fetch(e, slice(1, 2)))
print(fetch(e, slice(-2, -1)))
print(fetch(e, slice(None, None, -1)))
print(fetch(e, slice(1, 2, 3)))
''',
    'getitem_control': '''
class E(Exception):
    def __getitem__(self, key):
        return ('get', key)

e = E('m')
print(e[0])
print(e[1:2])
''',
}


def _long_case(name):
    return ('class %s(Exception):\n    pass\n\na = %s()\n' % (name, name)
            + 'try:\n    a[0]\nexcept TypeError as e:\n    print(type(e).__name__, e)\n'
            + 'try:\n    a[1:2]\nexcept TypeError as e:\n    print(type(e).__name__, e)\n')


CASES['long_name_200'] = _long_case('A' + 'a' * 209)

UNCAUGHT = '''
class E(Exception):
    pass

print(E()[0])
'''


def compile_source(directory, name, source, general):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
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


class Pre416(unittest.TestCase):
    def check(self, name, source, uncaught=False):
        with tempfile.TemporaryDirectory(prefix='ail-pre416-') as directory:
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

    def test_exception_item_errors(self):
        for name, source in CASES.items():
            with self.subTest(name=name):
                self.check(name, source)

    def test_uncaught_exception_subscript(self):
        self.check('uncaught', UNCAUGHT, uncaught=True)


if __name__ == '__main__':
    unittest.main()
