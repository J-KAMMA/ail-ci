"""Pre374: a loop read of an out-of-int64 container value before a later mutation is refused.

The pre355 review recorded as pre-existing that

    items = [1e300]
    for i in range(1):
        print(int(items[0]))
    items[0] = 1.5

compiled on both builds and then stopped with ``integer overflow``, where CPython prints the
big integer: a later mutation kept the container out of the fold, so the earlier read was
never refused.  ``_check_flow_int64_containers`` now walks the module statements in order and
refuses such a read by name when no mutation precedes it.  The same review's dict ``update``
read-before-mutation item, the two ``globals()`` key refusals and its class-attribute item are
pinned here as they behave on this tree.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre374-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre374-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


FLOAT = 'int() of a float outside int64'
RANGE = 'int64 constant expression out of range'

REFUSED = {
    'for_read_before_store': ('''
items = [1e300]
for i in range(1):
    print(int(items[0]))
items[0] = 1.5
''', FLOAT),
    'for_read_before_dict_update': ('''
d = {"k": 1e300}
for i in range(1):
    print(int(d["k"]))
d.update({"k": 1.5})
''', FLOAT),
    'straight_read_before_update': ('''
d = {"k": 1e300}
print(int(d.get("k")))
d.update({"k": 1.5})
''', FLOAT),
    'for_read_before_alias_store': ('''
items = [1e300]
a = items
for i in range(1):
    print(int(a[0]))
items[0] = 1.5
''', FLOAT),
    'for_read_nested_list': ('''
items = [1e300]
rows = [items]
for i in range(1):
    print(int(rows[0][0]))
items[0] = 1.5
''', FLOAT),
    'for_read_nested_dict': ('''
items = [1e300]
d = {"k": items}
for i in range(1):
    print(int(d["k"][0]))
items[0] = 1.5
''', FLOAT),
    'for_read_scalar_key': ('''
k = 0
items = [1e300]
for i in range(1):
    print(int(items[k]))
items[0] = 1.5
''', FLOAT),
    'for_read_negative': ('''
items = [-1e300]
for i in range(1):
    print(int(items[0]))
items[0] = 1.5
''', FLOAT),
    'for_read_two_iterations': ('''
items = [1e300]
for i in range(2):
    print(int(items[0]))
    items[0] = 1.5
''', FLOAT),
    'straight_read_before_store': ('''
items = [1e300]
print(int(items[0]))
items[0] = 1.5
''', FLOAT),
    'while_true_read_before_store': ('''
items = [1e300]
while True:
    print(int(items[0]))
    break
items[0] = 1.5
''', FLOAT),
    'for_read_boundary_2_63': ('''
items = [9223372036854775808.0]
for i in range(1):
    print(int(items[0]))
items[0] = 1.5
''', FLOAT),
    'for_read_string': ('''
items = ["9223372036854775808"]
for i in range(1):
    print(int(items[0]))
items[0] = "1"
''', RANGE),
    'for_read_bytes': ('''
items = [b"9223372036854775808"]
for i in range(1):
    print(int(items[0]))
items[0] = b"1"
''', RANGE),
    'globals_list_key': ('''
items = [1e300]
globals()["items"] = [1.5]
print(int(items[0]))
''', FLOAT),
    'globals_string_key': ('''
items = "9223372036854775808"
globals()["items"] = "1"
print(int(items))
''', RANGE),
    'class_attribute_mutation': ('''
items = [1e300]

class C:
    x = items

C.x[0] = 1.5
for i in range(1):
    print(int(items[0]))
''', FLOAT),
}

MATCH = {
    'mutation_before_loop': '''
items = [1e300]
items[0] = 1.5
for i in range(1):
    print(int(items[0]))
''',
    'alias_mutation_before_loop': '''
items = [1e300]
a = items
a[0] = 1.5
for i in range(1):
    print(int(items[0]))
''',
    'loop_mutation_before_read': '''
items = [1e300]
for i in range(1):
    items[0] = 1.5
    print(int(items[0]))
''',
    'in_range_values': '''
items = [1.9, -2.5]
for i in range(1):
    print(int(items[0]), int(items[1]))
items[0] = 9.9
''',
    'empty_list_loop': '''
items = [1e300]
for x in []:
    print(int(items[0]))
items[0] = 1.5
''',
    'range_zero': '''
items = [1e300]
for i in range(0):
    print(int(items[0]))
items[0] = 1.5
''',
    'range_variable_zero': '''
n = 0
items = [1e300]
for i in range(n):
    print(int(items[0]))
items[0] = 1.5
''',
    'nested_loop_zero': '''
items = [1e300]
for i in range(1):
    for j in range(0):
        print(int(items[0]))
items[0] = 1.5
''',
    'if_false_read': '''
items = [1e300]
if False:
    print(int(items[0]))
items[0] = 1.5
print(int(items[0]))
''',
    'if_zero_read': '''
items = [1e300]
if 0:
    print(int(items[0]))
items[0] = 1.5
print(int(items[0]))
''',
    'if_true_mutation': '''
items = [1e300]
if True:
    items[0] = 1.5
print(int(items[0]))
''',
    'sealed_alias_function': '''
items = [1e300]
alias = items

def change():
    global alias
    alias[0] = 1.5

change()
print(int(items[0]))
''',
    'pop_append_alias': '''
items = [1e300]
a = items
a.pop()
a.append(1.5)
print(int(items[0]))
''',
    'two_aliases_mutation': '''
items = [1e300]
a = items
b = a
a[0] = 1.5
for i in range(1):
    print(int(b[0]))
''',
    'straight_mutation_before': '''
items = [1e300]
items[0] = 1.5
print(int(items[0]))
''',
    'rebind_in_range': '''
items = [1e300]
items = [1.5]
for i in range(1):
    print(int(items[0]))
''',
    'loop_else_mutation': '''
items = [1e300]
for i in range(1):
    pass
else:
    items[0] = 1.5
print(int(items[0]))
''',
    'break_before_read': '''
items = [1e300]
for i in range(1):
    break
    print(int(items[0]))
items[0] = 1.5
''',
    'if_break_before_read': '''
items = [1e300]
for i in range(1):
    if True:
        break
    print(int(items[0]))
items[0] = 1.5
''',
    'if_continue_before_read': '''
items = [1e300]
for i in range(1):
    if True:
        continue
    print(int(items[0]))
items[0] = 1.5
''',
    'try_mutation_before_read': '''
items = [1e300]
try:
    items[0] = 1.5
    print(int(items[0]))
except Exception:
    pass
''',
    'lambda_after_mutation': '''
items = [1e300]
f = lambda: int(items[0])
items[0] = 1.5
print(f())
''',
    'function_argument_mutation': '''
items = [1e300]

def change(a):
    a[0] = 1.5

change(items)
for i in range(1):
    print(int(items[0]))
''',
}


class Pre374Tests(unittest.TestCase):
    def test_read_before_mutation_is_refused(self):
        for slug, (text, needle) in REFUSED.items():
            with self.subTest(case=slug):
                check_refused(self, slug, text, needle)

    def test_unchanged_routes_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
