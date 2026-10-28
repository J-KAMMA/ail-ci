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


MATCH = {
    'recorded_list_alias_exact': '''
items = [1e300]
a = items
x = a[0]
a[0] = 1.5
print(int(x))
''',
    'direct_scalar_read_exact': '''
items = [1e300]
x = items[0]
items[0] = 1.5
print(int(x))
''',
    'dict_value_exact': '''
d = {"k": 1e300}
x = d["k"]
d["k"] = 1.5
print(int(x))
''',
    'computed_index_exact': '''
items = [1e300]
a = items
i = 0
x = a[i]
a[0] = 1.5
print(int(x))
''',
    'delete_after_exact': '''
items = [1e300]
a = items
x = a[0]
del a[0]
print(int(x))
''',
    'alias_chain_exact': '''
items = [1e300]
a = items
b = a
x = b[0]
a[0] = 1.5
print(int(x))
''',
    'tuple_exact': '''
items = (1e300,)
a = items
x = a[0]
print(int(x))
''',
    'negative_exact': '''
items = [-1e300]
a = items
x = a[0]
a[0] = 1.5
print(int(x))
''',
    'int64_boundary_exact': '''
items = [9223372036854775808.0]
a = items
x = a[0]
a[0] = 1.5
print(int(x))
''',
    'function_local_exact': '''
def main():
    items = [1e300]
    a = items
    x = a[0]
    a[0] = 1.5
    print(int(x))


main()
''',
    'call_between_exact': '''
items = [1e300]
def show(value):
    return value


a = items
x = a[0]
show(a)
print(int(x))
''',
    'print_between_exact': '''
items = [1e300]
a = items
x = a[0]
print(a)
print(int(x))
''',
    'string_item_exact': '''
items = ["9223372036854775808"]
x = items[0]
items[0] = "1"
print(int(x))
''',
    'int_item_exact': '''
items = [9223372036854775808]
x = items[0]
items[0] = 1
print(int(x))
''',
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


# Under exact ints (biggate.ON) the moved cases are not int64 refusals: int() of the item is an exact
# big int, so they must print what CPython prints (they were refusals on the int64-only build).


class Pre388Tests(unittest.TestCase):
    def test_mutated_first_and_in_range_reads_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
