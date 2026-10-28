"""pre421: list/tuple index errors name the class of a non-index key.

The pre411 review recorded as pre-existing that ``Box(Bad())`` used as a list or tuple
index said ``not instance`` where CPython says ``not Box``.  The general runtime built the
message from the value's tag (``instance``); it now uses the existing object-to-name helper,
which returns the class's own name (and the subclass's name), capped at CPython's 200
characters.  The same text is used by a list item store and deletion.

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

PROGRAMS = {
    'getitem_routes': '''
class Bad:
    pass


class Box:
    def __init__(self, v):
        self.v = v


class Sub(Box):
    pass


class Holder:
    pass


def take(x):
    try:
        return [10, 20][x]
    except Exception as e:
        return type(e).__name__ + ' ' + str(e)


def taket(x):
    try:
        return (10, 20)[x]
    except Exception as e:
        return type(e).__name__ + ' ' + str(e)


b = Box(Bad())
s = Sub(Bad())
alias = b
h = Holder()
h.b = b
xs = [b]
d = {'b': b}
print(take(b))
print(take(s))
print(taket(b))
print(take(alias))
print(take(xs[0]))
print(take(h.b))
print(take(d['b']))
try:
    [10, 20][b]
except Exception as e:
    print(type(e).__name__, e)
try:
    (10, 20)[s]
except Exception as e:
    print(type(e).__name__, e)
''',
    'setdel': '''
class Box:
    pass


b = Box()
try:
    xs = [10, 20]
    xs[b] = 30
except Exception as e:
    print(type(e).__name__, e)
try:
    xs = [10, 20]
    del xs[b]
except Exception as e:
    print(type(e).__name__, e)
''',
    'builtin_keys': '''
class Marker:
    pass


def show(recv, key):
    try:
        recv[key]
    except Exception as e:
        print(type(e).__name__, e)


show([], 1.5)
show((), "x")
show([1], None)
show([1], [2])
show([1], {'a': 1})
show([1], (2,))
show([1], b"x")
show([1], len)
''',
}

LONG_NAME = 'A' + 'a' * 209
PROGRAMS['long_name'] = '''
class %s:
    pass


obj = %s()
try:
    [1, 2][obj]
except Exception as e:
    print(type(e).__name__, e)
try:
    (1, 2)[obj]
except Exception as e:
    print(type(e).__name__, e)
try:
    xs = [1, 2]
    xs[obj] = 3
except Exception as e:
    print(type(e).__name__, e)
try:
    xs = [1, 2]
    del xs[obj]
except Exception as e:
    print(type(e).__name__, e)
''' % (LONG_NAME, LONG_NAME)


def build(directory, name, text, general, debug_dir=None):
    path = Path(directory) / (name + '.ail')
    path.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    command = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
               '--syntax', 'python', '-o', exe.name]
    if debug_dir is not None:
        command += ['--debug-dir', str(debug_dir)]
    built = subprocess.run(command, cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Pre421(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre421-') as directory:
            py = Path(directory) / (name + '_cpython.py')
            py.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', py.name], cwd=directory,
                                  capture_output=True, text=True, timeout=120)
            for general in (True, False):
                built, exe = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                     text=True, timeout=120)
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))
                self.assertEqual(got.stdout.replace('\r\n', '\n'), want.stdout,
                                 (name, general, got.stderr[-800:]))

    def test_list_tuple_index_names(self):
        for name, text in PROGRAMS.items():
            with self.subTest(name=name):
                self.check(name, text)

    def test_no_class_c_keeps_base_index_text(self):
        """The class-name text is emitted only for a source that writes a class.

        A no-class general-path program must keep base's C for list/tuple indexing; adding
        it unconditionally changed the generated C of every such program (pre421 review).
        """
        no_class = '''
def f(xs, i):
    print(xs[i], xs[-1], len(xs))
    xs[i] = 9
    print(xs)
    del xs[0]
    print(xs)


f([1, 2, 3], 1)
'''
        with_class = '''
class Box:
    pass


def f(xs, i):
    print(xs[i], xs[-1], len(xs))
    xs[i] = 9
    print(xs)
    del xs[0]
    print(xs)


f([1, 2, 3], 1)
print(Box)
'''
        with tempfile.TemporaryDirectory(prefix='ail-pre421-c-') as directory:
            for general in (True, False):
                tag = 'g' if general else 'd'
                debug = Path(directory) / ('noclass_' + tag)
                built, _ = build(directory, 'noclass_' + tag, no_class, general, debug)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                text = (debug / 'program.c').read_text(encoding='utf-8')
                self.assertIn('ail_type_name(key.tag)', text)
                self.assertNotIn('snprintf(tnbuf, sizeof tnbuf, "%s", ail__tname_c(key));', text)

                debug = Path(directory) / ('withclass_' + tag)
                built, _ = build(directory, 'withclass_' + tag, with_class, general, debug)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                text = (debug / 'program.c').read_text(encoding='utf-8')
                self.assertEqual(
                    text.count('snprintf(tnbuf, sizeof tnbuf, "%s", ail__tname_c(key));'), 3)


if __name__ == '__main__':
    unittest.main()
