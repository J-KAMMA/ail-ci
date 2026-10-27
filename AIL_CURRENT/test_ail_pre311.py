"""pre311: int() of an out-of-int64 float read from an aliased module container.

The pre290 review left this pre-existing difference (its probe r26): a value outside int64 that
reached int() through a module-level list and an alias of that list still compiled and stopped
at run time with `integer overflow`, while CPython prints the exact big integer.  Module names
bound once to a literal container (or aliased from one) are now folded when every use is a
subscript read or a module-level alias; a mutation through the name or an alias, a call that
could mutate the object, or any other use stops the record.  The same pass also covers an
aliased dict and tuple (r33 and the tuple spelling).

Values that fit int64, containers mutated before the read (through the name, an alias or a
function), a local shadow and non-float elements keep their previous behaviour.  Programs are
built with the general path forced and with the default build; stdout and the exit status must
match CPython.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre311-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre311-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'alias_list': '''
a = [1e300]
b = a


def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(b[0]))
''',
    'alias_list_direct': '''
a = [1e300]
b = a

print(int(b[0]))
''',
    'alias_dict': '''
d = {"v": 1e300}
e = d


def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(e["v"]))
''',
    'alias_tuple': '''
a = (1e300,)
b = a


def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(b[0]))
''',
    'alias_of_alias': '''
a = [1e300]
b = a
c = b


def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(c[0]))
''',
    'negative_index': '''
a = [1e300]
b = a

print(int(b[-1]))
''',
    'argument_route': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


a = [1e300]
b = a
print(outer(b[0]))
''',
    'dict_value_route': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


d = {"v": 1e300}
e = d
print(outer(e["v"]))
''',
    'mixed_list': '''
a = [10, 1e300]
b = a

print(int(b[1]))
''',
}

MATCH = {
    'in_range_alias': '''
a = [1.9]
b = a


def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(b[0]))
''',
    'mutate_before_read': '''
a = [1e300]
a[0] = 1.5
print(int(a[0]))
''',
    'alias_mutate_before': '''
a = [1e300]
b = a
b[0] = 1.5
print(int(a[0]))
''',
    'mutate_in_function': '''
a = [1e300]


def change():
    global a
    a[0] = 1.5


change()
print(int(a[0]))
''',
    'bare_read_in_range': '''
a = [1.9]
print(a)
print(int(a[0]))
''',
    'alias_append_in_range': '''
a = [1.9]
b = a
b.append(2.5)
print(int(a[0]))
''',
    'local_shadow': '''
a = [1e300]


def f():
    a = [1.5]
    return int(a[0])


print(f())
''',
    'empty_then_append': '''
a = []
b = a
b.append(2.5)
print(int(b[0]))
''',
    'non_float': '''
a = [10, True]
print(int(a[0]), int(a[1]))
''',
    'tuple_multi_in_range': '''
a, b = 1.9, 2
print(int(a), b)
''',
    'attribute_in_range': '''
class Box:
    def __init__(self, v):
        self.v = v


print(int(Box(1.9).v))
''',
    'nested_in_range': '''
a = [[1.9]]
b = a
print(int(b[0][0]))
''',
    'container_as_argument_in_range': '''
a = [1.9]


def first(v):
    return int(v[0])


print(first(a))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatOutsideInt64AliasedContainer(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_matching_programs_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
