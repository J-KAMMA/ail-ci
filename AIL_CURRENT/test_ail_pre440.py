"""pre440: an operand's class name in the operator TypeError matches CPython's caps.

The pre428 review recorded as pre-existing that an ordinary-instance class name longer
than 79 characters was truncated at 79 in ``unsupported operand type(s) for ...``; CPython
formats each operand with ``%.100s`` there (its ``binary_op_error``).  The helper that
builds the message had 80-byte name buffers.  It now uses CPython's cap for each of its
messages: 100 for ``unsupported operand``, 200 for ``can only concatenate`` and
``can't multiply sequence`` (the operands come from any route -- an argument, a list
item, an attribute or a dict value).

Programs are built with the general path forced and with the default build; stdout and
the exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

A120 = 'A' * 120
B121 = 'B' * 121
A250 = 'C' * 250

PROGRAMS = {
    'add_sub_mul': '''
class %s:
    pass


class %s:
    pass


for f in (lambda: %s() + %s(), lambda: %s() - %s(), lambda: %s() * %s()):
    try:
        f()
    except Exception as e:
        print(type(e).__name__, e)
''' % (A120, B121, A120, B121, A120, B121, A120, B121),
    'routes': '''
class %s:
    pass


class Holder:
    pass


def take(x, y):
    try:
        return x + y
    except Exception as e:
        return type(e).__name__ + ' ' + str(e)


obj = %s()
holder = Holder()
holder.v = obj
xs = [obj]
d = {'v': obj}
alias = obj
print(take(obj, 1))
print(take(1, obj))
print(take(alias, 1))
print(take(xs[0], 1))
print(take(holder.v, 1))
print(take(d['v'], 1))
try:
    obj + obj
except Exception as e:
    print(type(e).__name__, e)
''' % (A120, A120),
    'subclass': '''
class %s:
    pass


class %s:
    pass


class Sub(%s):
    pass


for f in (lambda: %s() + %s(), lambda: %s() + %s(), lambda: Sub() + 1):
    try:
        f()
    except Exception as e:
        print(type(e).__name__, e)
''' % (A120, B121, B121, A120, B121, B121, A120),
    'other_ops': '''
class %s:
    pass


obj = %s()
for f in (lambda: [1] + obj, lambda: (1,) + obj, lambda: "x" + obj,
          lambda: [1] * obj, lambda: obj * "x",
          lambda: divmod(obj, 2), lambda: divmod(2, obj),
          lambda: obj & 2, lambda: 2 | obj, lambda: obj ^ 2,
          lambda: obj << 1, lambda: 1 >> obj):
    try:
        f()
    except Exception as e:
        print(type(e).__name__, e)
''' % (A120, A120),
    'cap_200': '''
class %s:
    pass


obj = %s()
for f in (lambda: [1] + obj, lambda: obj * "x", lambda: obj + obj):
    try:
        f()
    except Exception as e:
        print(type(e).__name__, e)
''' % (A250, A250),
}

# the length boundary of each cap: 79/80 (the old buffer), 99/100/101 (CPython's 100)
for n in (79, 80, 99, 100, 101, 120):
    name = 'D' * n
    PROGRAMS['len_%d' % n] = '''
class %s:
    pass


try:
    %s() + 1
except Exception as e:
    print(type(e).__name__, e)
''' % (name, name)


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


class Pre440(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre440-') as directory:
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

    def test_long_operand_names(self):
        for name, text in PROGRAMS.items():
            with self.subTest(name=name):
                self.check(name, text)

    def test_no_class_c_unchanged(self):
        """A program with no class does not get the dunder runtime text at all."""
        no_class = '''
def f(x, y):
    return x + y


print(f(1, 2))
'''
        with_class = '''
class Box:
    pass


print(Box)
'''
        with tempfile.TemporaryDirectory(prefix='ail-pre440-c-') as directory:
            for general in (True, False):
                tag = 'g' if general else 'd'
                debug = Path(directory) / ('noclass_' + tag)
                built, _ = build(directory, 'noclass_' + tag, no_class, general, debug)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                text = (debug / 'program.c').read_text(encoding='utf-8')
                self.assertNotIn('char buf[400], na[201], nb[201], na100[101], nb100[101];', text)

                debug = Path(directory) / ('withclass_' + tag)
                built, _ = build(directory, 'withclass_' + tag, with_class, general, debug)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                text = (debug / 'program.c').read_text(encoding='utf-8')
                self.assertEqual(text.count('char buf[400], na[201], nb[201], na100[101], nb100[101];'), 1)


if __name__ == '__main__':
    unittest.main()
