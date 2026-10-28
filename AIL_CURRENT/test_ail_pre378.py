"""pre378: a subscript of an instance without ``__getitem__`` names its class.

The pre354 reviewer recorded as pre-existing that ``A()[1]`` (an instance of a class with
no ``__getitem__``) raised ``TypeError: 'instance' object is not subscriptable`` on both
builds, where CPython names the class: ``TypeError: 'A' object is not subscriptable``.
The runtime's tag table only knows the generic instance tag; the getitem and getslice
fallbacks now ask the value's own class name (``ail__tname_c``), the way attribute errors
already do.  A subclass names the subclass, and builtin values keep their type names.
The class object itself (``A[1]``) is a separate pre-existing difference and is not
covered here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CASES = {
    'int_key': '''
class A:
    pass

try:
    A()[1]
except TypeError as e:
    print(e)
''',
    'slice_key': '''
class A:
    pass

try:
    A()[1:2]
except TypeError as e:
    print(e)
''',
    'other_keys': '''
class A:
    pass

for key in ('k', 1.5, None, (1,)):
    try:
        A()[key]
    except TypeError as e:
        print(e)
''',
    'subclass': '''
class A:
    pass


class B(A):
    pass

try:
    B()[1]
except TypeError as e:
    print(e)
''',
    'dunder_present': '''
class A:
    def __eq__(self, other):
        return False

try:
    A()[1]
except TypeError as e:
    print(e)
''',
    'routes': '''
class A:
    pass


class Holder:
    pass


def take(x):
    try:
        x[1]
    except TypeError as e:
        print(e)


a = A()
alias = a
h = Holder()
h.a = a
box = {'a': a}
items = [a]
take(a)
take(alias)
take(h.a)
take(box['a'])
take(items[0])
''',
    'slice_routes': '''
class A:
    pass


class Holder:
    pass


def take(x):
    try:
        x[1:2]
    except TypeError as e:
        print(e)


a = A()
h = Holder()
h.a = a
box = {'a': a}
items = [a]
take(a)
take(h.a)
take(box['a'])
take(items[0])
''',
    'builtin_names': '''
for value in (5, None, 1.5, True):
    try:
        value[1]
    except TypeError as e:
        print(e)
''',
    'getitem_control': '''
class C:
    def __getitem__(self, i):
        return ('ok', i)


print(C()[3])
print(C()[-1])
''',
}

# A class name longer than the fixed buffers the fallbacks used to format into must still
# be printed whole; 33 fits the old char[64], 34 is the first that was truncated.
CASES['long_name_int'] = '''
class %(n)s:
    pass

try:
    %(n)s()[1]
except TypeError as e:
    print(e)
''' % {'n': 'B' * 40}

CASES['long_name_slice'] = '''
class %(n)s:
    pass

try:
    %(n)s()[1:2]
except TypeError as e:
    print(e)
''' % {'n': 'C' * 40}

CASES['name_lengths'] = '''
class A:
    pass


class %(f33)s:
    pass


class %(g34)s:
    pass


for value in (A(), %(f33)s(), %(g34)s()):
    try:
        value[1]
    except TypeError as e:
        print(e)
''' % {'f33': 'F' * 33, 'g34': 'G' * 34}

CASES['long_name_routes'] = '''
class %(n)s:
    pass


class Holder:
    pass


def take(x):
    try:
        x[1]
    except TypeError as e:
        print(e)


def take_slice(x):
    try:
        x[1:2]
    except TypeError as e:
        print(e)


v = %(n)s()
alias = v
h = Holder()
h.a = v
box = {'a': v}
items = [v]
take(v)
take(alias)
take(h.a)
take(box['a'])
take(items[0])
take_slice(v)
take_slice(h.a)
take_slice(box['a'])
take_slice(items[0])
''' % {'n': 'D' * 40}

CASES['long_name_subclass'] = '''
class %(b)s:
    pass


class %(s)s(%(b)s):
    pass


for value in (%(b)s(), %(s)s()):
    try:
        value[1]
    except TypeError as e:
        print(e)
    try:
        value[1:2]
    except TypeError as e:
        print(e)
''' % {'b': 'H' * 40, 's': 'I' * 40}


UNCAUGHT = '''
class Widget:
    pass

print(Widget()[1])
'''

LONG_UNCAUGHT = '''
class %(n)s:
    pass

print(%(n)s()[1])
''' % {'n': 'E' * 40}


def compile_source(directory, name, source, general):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
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
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.stderr.replace('\r\n', '\n'), ran.returncode


def last_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ''


class Pre378(unittest.TestCase):
    def test_instance_names_its_class(self):
        for slug, source in CASES.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre378-') as directory:
                expected, _, status = run_cpython(directory, 'pre378_' + slug, source)
            for general in (False, True):
                with self.subTest(slug=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre378-') as directory:
                    built, exe = compile_source(directory, 'pre378_' + slug, source, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    self.assertTrue(exe.exists(), '%s did not build' % slug)
                    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                    self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected,
                                     ran.stdout + ran.stderr)

    def test_uncaught_names_class(self):
        for slug, source in (('uncaught', UNCAUGHT), ('uncaught_long', LONG_UNCAUGHT)):
            with tempfile.TemporaryDirectory(prefix='ail-pre378-') as directory:
                expected, cpython_err, status = run_cpython(directory, 'pre378_' + slug, source)
            for general in (False, True):
                with self.subTest(slug=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre378-') as directory:
                    built, exe = compile_source(directory, 'pre378_' + slug, source, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                    self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected, ran.stdout + ran.stderr)
                    self.assertEqual(last_line(ran.stderr), last_line(cpython_err), ran.stderr)


if __name__ == '__main__':
    unittest.main()
