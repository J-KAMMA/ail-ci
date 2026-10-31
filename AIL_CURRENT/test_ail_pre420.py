"""pre420: a list/tuple index error names an instance's class, not the tag ``instance``.

CPython builds the subscription TypeError from the key type's name: ``list indices must be
integers or slices, not C``.  The general path used ``ail_type_name(key.tag)``, which answers
``instance`` for a user-class value without ``__index__``, so both builds printed
``not instance``.  The message now goes through the runtime's object-to-name helper
(``ail__tname_c``), which returns the class's own name (and the subclass's), and the text is
built in a dynamically sized buffer capped at 200 characters like CPython's ``%.200s``.

A value that does define ``__index__`` still indexes normally, and non-instance keys
(``float``, ``str``, ``None``) keep CPython's text.  A non-int ``__index__`` return is a
separate pre-existing cause and is not checked here.

Programs are built with the general path forced and with the default build; stdout and the
exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

_LONG = 'K' * 210

PROGRAMS = {
    'no_index': '''
class C:
    pass


class D(C):
    pass


def at(x):
    return x


a = [10, 20, 30]
t = (1, 2, 3)
c = C()
d = D()
box = C()
box.k = d
holder = {"k": c}
items = [c, d]

for key in (c, d, at(c), items[0], box.k, holder["k"]):
    try:
        print(a[key])
    except TypeError as exc:
        print(type(exc).__name__, exc)
    try:
        print(t[key])
    except TypeError as exc:
        print(type(exc).__name__, exc)

try:
    print([][c])
except TypeError as exc:
    print(type(exc).__name__, exc)
try:
    print(()[d])
except TypeError as exc:
    print(type(exc).__name__, exc)


class WithIndex:
    def __index__(self):
        return 1


print(a[WithIndex()])
print(t[WithIndex()])

for key in (1.5, "x", None):
    try:
        print(a[key])
    except TypeError as exc:
        print(type(exc).__name__, exc)
''',
    'long_name': '''
class %s:
    pass


class E(Exception):
    pass


k = %s()
for cont in ([1], (1,)):
    for key in (k, E()):
        try:
            print(cont[key])
        except TypeError as exc:
            print(len(str(exc)), exc)
''' % (_LONG, _LONG),
}


def run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace('\r\n', '\n'), done.returncode


def build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Pre420(unittest.TestCase):
    def test_index_error_names_the_class(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre420-') as directory:
            for name, text in PROGRAMS.items():
                want, status = run_cpython(directory, name, text)
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        built, exe = build(directory, name, text, general)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                                             cwd=directory)
                        self.assertEqual(ran.returncode, status, ran.stderr[-1200:])
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), want, ran.stderr[-1200:])


if __name__ == '__main__':
    unittest.main()
