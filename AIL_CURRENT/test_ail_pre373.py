"""pre373: int() of an out-of-int64 float read before a later container mutation.

The pre355 review recorded as pre-existing its p20: a module container holding a float
outside int64 was mutated after an ``int()`` read of it, so `_safe_module_containers`
dropped the container for the whole program and the earlier read stayed unfolded; both
builds then stopped at run time with ``integer overflow`` where CPython prints the big
integer.  A straight-line walk now tracks each module name's container in statement
order and refuses the read by name.  Expressions are walked in evaluation order, so a
mutation that runs earlier in the same statement (``a.pop(0)``, a user call,
``dict.update``) is applied or clears the state before a later ``int()`` operand is
checked; a mutation before the read updates the shared container (aliases included), so
those programs still match CPython; anything whose effect is not known (a branch, loop,
function or class body, import, walrus or unsupported store) drops the walk state and
leaves the pre-existing run-time stop.  Programs are built with the general path forced
and with the default build.
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

REFUSAL = 'int() of a float outside int64'

REFUSED = {
    'read_before_store': '''
items = [1e300]
a = items
print(int(a[0]))
a[0] = 1.5
''',
    'alias_read_before': '''
items = [1e300]
a = items
int(a[0])
a[0] = 1.5
print(int(items[0]))
''',
    'alias_chain': '''
items = [1e300]
a = items
b = a
int(b[0])
items[0] = 1.5
''',
    'dict_value': '''
d = {"v": 1e300}
a = d
int(a["v"])
d["v"] = 1.5
''',
    'negative_index': '''
items = [2.5, 1e300]
a = items
int(a[-1])
a[0] = 1.5
''',
    'multi_target_alias': '''
items = [1e300]
a = b = items
int(a[0])
b[0] = 1.5
''',
    'tuple_alias': '''
t = (1e300, 2.5)
a = t
print(int(a[0]))
''',
    'append_before_read': '''
items = [1e300]
a = items
a.append(1.5)
print(int(items[0]))
''',
    'wrapper_argument': '''
items = [1e300]
a = items
def take(x):
    return int(x)
take(a[0])
a[0] = 1.5
''',
    'list_item_route': '''
inner = [1e300]
rows = [inner]
a = rows[0]
int(a[0])
inner[0] = 1.5
''',
    'assignment_value': '''
items = [1e300]
a = items
x = int(a[0])
a[0] = 1.5
''',
    'empty_dict_store': '''
d = {}
d["v"] = 1e300
print(int(d["v"]))
''',
    'variable_index': '''
items = [1e300]
a = items
i = 0
int(a[i])
a[0] = 1.5
''',
    'constructor_attribute': '''
class C:
    def __init__(self):
        self.a = [1e300]
c = C()
print(int(c.a[0]))
''',
    'read_before_pop_same_statement': '''
items = [1e300]
a = items
print(int(a[0]), a.pop(0))
''',
    'read_before_user_call_same_statement': '''
items = [1e300]
def change():
    items[0] = 1.5
    return 0
print(int(items[0]), change())
''',
    'update_other_key_before_read': '''
d = {"v": 1e300}
a = d
print(d.update(w=2), int(a["v"]))
''',
    'count_before_read': '''
items = [1e300]
a = items
print(a.count(0), int(a[0]))
a[0] = 1.5
''',
    'get_before_read': '''
d = {"v": 1e300}
a = d
print(d.get("v"), int(a["v"]))
d["v"] = 1.5
''',
    'dict_pop_default_missing': '''
d = {"v": 1e300}
a = d
print(a.pop("w", 9), int(a["v"]))
d["v"] = 1.5
''',
}

MATCH = {
    'mutate_before_read': '''
items = [1e300]
a = items
a[0] = 1.5
print(int(items[0]))
''',
    'dict_mutate_before': '''
d = {"v": 1e300}
a = d
a["v"] = 1.5
print(int(d["v"]))
''',
    'negative_mutate_before': '''
items = [2.5, 1e300]
a = items
a[-1] = 1.5
print(int(items[-1]))
''',
    'multi_target_mutate': '''
items = [1e300]
a = b = items
a[0] = 1.5
print(int(b[0]))
''',
    'append_index0': '''
items = [1.9]
a = items
a.append(2.5)
print(int(items[0]))
''',
    'append_negative': '''
items = [1.9]
a = items
a.append(2.5)
print(int(items[-1]))
''',
    'pop_append': '''
items = [1e300]
a = items
a.pop()
a.append(1.5)
print(int(items[0]))
''',
    'function_mutation': '''
items = [1e300]
def change():
    global items
    items[0] = 1.5
change()
print(int(items[0]))
''',
    'if_false_read': '''
items = [1e300]
if False:
    print(int(items[0]))
items[0] = 1.5
print(int(items[0]))
''',
    'deferred_lambda': '''
items = [1e300]
f = lambda: int(items[0])
f = lambda: 0
print(f())
items[0] = 1.5
''',
    'empty_comprehension': '''
items = [1e300]
rows = [int(items[0]) for _ in range(0)]
items[0] = 1.5
print(rows)
''',
    'ifexp_false': '''
items = [1e300]
x = int(items[0]) if False else 0
items[0] = 1.5
print(x)
''',
    'boolop_short': '''
items = [1e300]
x = False and int(items[0])
items[0] = 1.5
print(x)
''',
    'walrus_rebind': '''
a = [1e300]
print((a := [1.5]))
print(int(a[0]))
''',
    'in_range_before': '''
items = [1.9]
a = items
int(a[0])
a[0] = 2.5
print(int(items[0]))
''',
    'empty_append': '''
items = []
a = items
a.append(1.5)
print(int(items[0]))
''',
    'variable_index_store': '''
items = [1e300]
a = items
i = 0
a[i] = 1.5
print(int(items[0]))
''',
    'no_feature': '''
xs = [1, 2, 3]
print(sum(xs), len(xs))
''',
    'pop_before_read': '''
items = [1e300, 1.5]
a = items
print(a.pop(0), int(a[0]))
''',
    'user_call_before_read': '''
items = [1e300]
def change():
    items[0] = 1.5
    return 0
print(change(), int(items[0]))
''',
    'update_before_read': '''
d = {"v": 1e300}
print(d.update(v=1.5), int(d["v"]))
''',
    'negative_pop_before_read': '''
items = [2.5, 1e300]
a = items
print(a.pop(1), int(a[-1]))
''',
    'dict_pop_get_after': '''
d = {"v": 1e300}
a = d
print(a.pop("v"), int(d.get("v", 1)))
''',
    'variable_pop_index': '''
items = [1e300, 1.5]
a = items
i = 0
print(a.pop(i), int(a[0]))
''',
    'update_dict_argument': '''
d = {"v": 1e300}
a = d
x = {"v": 1.5}
print(a.update(x), int(d["v"]))
''',
    'list_item_pop': '''
inner = [1e300, 2.5]
rows = [inner]
a = rows[0]
print(a.pop(0), int(a[0]))
''',
    'width_boundary_pop': '''
items = [9.3e18, 1.5]
a = items
print(a.pop(0), int(a[0]))
''',
}


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
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name],
                               cwd=directory, capture_output=True, text=True, timeout=900,
                               env=env)


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Pre373(unittest.TestCase):
    def test_read_before_mutation_is_refused_by_name(self):
        for general in (False, True):
            for slug, source in REFUSED.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre373-') as directory:
                    exe, built = build(directory, slug, source, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output))
                    self.assertFalse(exe.exists(), (slug, general))
                    self.assertIn(REFUSAL, output, (slug, general, output[-1200:]))
                    self.assertNotIn('integer overflow', output, (slug, general))
                    self.assertNotIn('Traceback', output, (slug, general))

    def test_mutation_before_read_matches_cpython(self):
        for general in (False, True):
            for slug, source in MATCH.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre373-') as directory:
                    want, want_rc = cpython(directory, slug, source)
                    exe, built = build(directory, slug, source, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout,
                                                           built.stderr))
                    ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, want_rc, (slug, general, ran.stderr[-800:]))
                    self.assertEqual(ran.stdout.replace(b'\r\n', b'\n'), want,
                                     (slug, general, ran.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()
