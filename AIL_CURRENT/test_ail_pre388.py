"""Pre388: a container read before a later in-place mutation is folded for int().

The pre373 review recorded as pre-existing that
``items = [1e300]; a = items; x = a[0]; a[0] = 1.5; print(int(x))`` compiled on both builds
and then stopped with ``integer overflow``, where CPython prints the big integer.  The
constant fold dropped a flat list/tuple/dict as soon as any statement in the scope mutated it,
including a mutation after the read, so the scalar bound from an item stayed unknown.  The
escape analysis now records the statement at which a container may be mutated; a scalar read
through a load-only subscript before that point keeps the literal's value and the conversion is
refused by name.  A container mutated first (directly, through an alias, a loop or a nested
definition) stays dynamic and matches CPython.

The review's second item, a list held in an instance attribute
(``c.a = [1e300]; print(int(c.a[0])); c.a[0] = 1.5``), is a separate pre-existing cause:
attribute-held containers are still not folded and both builds still stop with
``integer overflow``.  It is recorded in DIFFERENCES and not changed here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


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


def check_refused(test, name, text, needle):
    with tempfile.TemporaryDirectory(prefix='ail-pre388-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre388-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


FLOAT = 'int() of a float outside int64'
INT = 'int64 constant expression out of range'

REFUSED = {
    'recorded_list_alias': ('''
items = [1e300]
a = items
x = a[0]
a[0] = 1.5
print(int(x))
''', FLOAT),
    'direct_scalar_read': ('''
items = [1e300]
x = items[0]
items[0] = 1.5
print(int(x))
''', FLOAT),
    'dict_value': ('''
d = {"k": 1e300}
x = d["k"]
d["k"] = 1.5
print(int(x))
''', FLOAT),
    'computed_index': ('''
items = [1e300]
a = items
i = 0
x = a[i]
a[0] = 1.5
print(int(x))
''', FLOAT),
    'delete_after': ('''
items = [1e300]
a = items
x = a[0]
del a[0]
print(int(x))
''', FLOAT),
    'alias_chain': ('''
items = [1e300]
a = items
b = a
x = b[0]
a[0] = 1.5
print(int(x))
''', FLOAT),
    'tuple': ('''
items = (1e300,)
a = items
x = a[0]
print(int(x))
''', FLOAT),
    'negative': ('''
items = [-1e300]
a = items
x = a[0]
a[0] = 1.5
print(int(x))
''', FLOAT),
    'int64_boundary': ('''
items = [9223372036854775808.0]
a = items
x = a[0]
a[0] = 1.5
print(int(x))
''', FLOAT),
    'function_local': ('''
def main():
    items = [1e300]
    a = items
    x = a[0]
    a[0] = 1.5
    print(int(x))


main()
''', FLOAT),
    'call_between': ('''
items = [1e300]
def show(value):
    return value


a = items
x = a[0]
show(a)
print(int(x))
''', FLOAT),
    'print_between': ('''
items = [1e300]
a = items
x = a[0]
print(a)
print(int(x))
''', FLOAT),
    'string_item': ('''
items = ["9223372036854775808"]
x = items[0]
items[0] = "1"
print(int(x))
''', INT),
    'int_item': ('''
items = [9223372036854775808]
x = items[0]
items[0] = 1
print(int(x))
''', INT),
}

MATCH = {
    'mutated_first': '''
items = [1e300]
a = items
a[0] = 1.5
x = a[0]
print(int(x))
''',
    'mutated_through_alias_first': '''
items = [1e300]
a = items
b = a
b[0] = 1.5
x = a[0]
print(int(x))
''',
    'mutated_in_loop_first': '''
items = [1e300]
for index in [0]:
    items[0] = 1.5
x = items[0]
print(int(x))
''',
    'mutated_in_nested_definition_first': '''
items = [1e300]
def bump():
    items[0] = 1.5


bump()
x = items[0]
print(int(x))
''',
    'function_mutated_first': '''
def main():
    items = [1e300]
    a = items
    a[0] = 1.5
    x = a[0]
    print(int(x))


main()
''',
    'in_range_read_before_mutation': '''
items = [1.9]
a = items
x = a[0]
a[0] = 1e300
print(int(x))
''',
    'in_range_float_read_before_mutation': '''
items = [9.2e18]
a = items
x = a[0]
a[0] = 1.5
print(int(x))
''',
    'plain_int_list': '''
items = [1, 2]
x = items[0]
items.append(3)
print(int(x), int(items[1]))
''',
    'in_range_string_read_before_mutation': '''
items = ["12"]
x = items[0]
items[0] = "13"
print(int(x))
''',
    'inline_list_item': '''
print(int([2.9][0]))
''',
}


class Pre388Tests(unittest.TestCase):
    def test_read_before_mutation_is_refused(self):
        for slug, (text, needle) in REFUSED.items():
            with self.subTest(case=slug):
                check_refused(self, slug, text, needle)

    def test_mutated_first_and_in_range_reads_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
