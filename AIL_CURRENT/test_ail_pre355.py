"""pre355: int() of an out-of-int64 float read before a later container mutation.

The rbrbpre322 review left this pre-existing difference (its r8): `items=[1e300]; a=items;
int(a[0]); a[0]=1.5` compiled on both builds and then stopped with `integer overflow`, where
CPython prints the bignum.  The static checker dropped a module container as soon as anything
mutated it, so the read before the mutation stayed unfolded.

A forward walk over the module statements now tracks the value each name denotes and refuses
the read by name (`int() of a float outside int64`, or `int64 constant expression out of range`
for out-of-range text) when it happens before the mutation.  A mutation before the read updates
the tracked value instead, so the same program still prints CPython's 1, and a call, loop or
function-body use keeps the name unfolded.  Programs are built with the general path forced and
with the default build; stdout and the exit status must match CPython.
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


def check_refused(test, name, text, wording='int() of a float outside int64'):
    with tempfile.TemporaryDirectory(prefix='ail-pre355-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(wording, message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre355-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'review_r8': '''
items=[1e300]; a=items; int(a[0]); a[0]=1.5
print(int(items[0]))
''',
    'review_r8_noop': '''
items=[1e300]; a=items; int(a[0]); a[0]=1.5
''',
    'alias_read_then_mutate': '''
items = [1e300]
a = items
int(items[0])
a[0] = 1.5
print(int(a[0]))
''',
    'nested_in_print': '''
items = [1e300]
print(int(items[0]))
items[0] = 1.5
''',
    'second_alias': '''
items = [1e300]
a = items
b = a
int(b[0])
a[0] = 1.5
print(int(items[0]))
''',
    'negative_index': '''
items = [1e300]
a = items
int(a[-1])
a[0] = 1.5
print(int(items[0]))
''',
    'dict_value': '''
d = {"v": 1e300}
a = d
int(a["v"])
a["v"] = 1.5
print(int(d["v"]))
''',
    'dict_alias': '''
d = {"v": 1e300}
e = d
int(e["v"])
e["v"] = 1.5
print(int(d["v"]))
''',
    'wrapper_argument': '''
items = [1e300]
a = items


def take(x):
    return int(x)


take(a[0])
a[0] = 1.5
print(int(items[0]))
''',
    'dict_wrapper_argument': '''
d = {"v": 1e300}
a = d


def take(x):
    return int(x)


take(a["v"])
a["v"] = 1.5
print(int(d["v"]))
''',
    'scalar_fed_list': '''
x = 1e300
items = [x]
a = items
int(a[0])
a[0] = 1.5
print(int(items[0]))
''',
    'rebind_after_read': '''
items = [1e300]
a = items
int(a[0])
items = [1.5]
print(int(items[0]))
''',
    'if_true_mutation_after': '''
items = [1e300]
a = items
int(a[0])
if True:
    a[0] = 1.5
print(int(items[0]))
''',
    'if_false_mutation_before': '''
items = [1e300]
if False:
    items[0] = 1.5
print(int(items[0]))
''',
    'nested_list': '''
rows = [[1e300]]
a = rows
int(a[0][0])
a[0][0] = 1.5
print(int(rows[0][0]))
''',
}

REFUSED_TEXT = {
    'out_of_range_text': '''
items = ["9223372036854775808"]
a = items
int(a[0])
a[0] = "1"
print(int(items[0]))
''',
}

MATCH = {
    'mutate_before_read': '''
items = [1e300]
items[0] = 1.5
print(int(items[0]))
''',
    'alias_mutate_before': '''
items = [1e300]
a = items
a[0] = 1.5
print(int(items[0]))
''',
    'mutate_in_function': '''
items = [1e300]


def change():
    global items
    items[0] = 1.5


change()
print(int(items[0]))
''',
    'in_range_after': '''
items = [1.9]
a = items
int(a[0])
a[0] = 2.5
print(int(items[0]))
''',
    'in_range_negative_after': '''
items = [1, 1.9]
a = items
int(a[-1])
a[1] = 2.5
print(int(items[1]))
''',
    'if_false_read': '''
items = [1e300]
if False:
    print(int(items[0]))
items[0] = 1.5
print(int(items[0]))
''',
    'if_true_mutation_before': '''
items = [1e300]
if True:
    items[0] = 1.5
print(int(items[0]))
''',
    'list_of_int_after': '''
items = [7]
a = items
int(a[0])
a[0] = 8
print(int(items[0]))
''',
    'class_attribute_in_range': '''
items = [1.9]


class C:
    x = items


int(C.x[0])
C.x[0] = 2.5
print(int(items[0]))
''',
    'rebind_before_read': '''
items = [1e300]
items = [1.5]
print(int(items[0]))
''',
    'append_before_read': '''
items = [1.9]
a = items
a.append(2.5)
print(int(items[0]))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatOutsideInt64MutationAfterRead(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_out_of_range_text_refused(self):
        for name, text in sorted(REFUSED_TEXT.items()):
            check_refused(self, 'refuse_' + name, text,
                          wording='int64 constant expression out of range')

    def test_matching_programs_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
