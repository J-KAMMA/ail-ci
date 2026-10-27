"""pre387: an int() read before a later mutation of the container is refused.

The reviewer of pre374 left that job's worker probes p09-p20 unverified.  The first one that
still differs on the integration tree is its p10 shape: a statically known out-of-int64
container value read before a later mutation of the container

    d = {"k": 1e300}
    print(int(d.get("k")))
    d.update({"k": 1.5})

compiles on both builds and then stops with ``integer overflow``, where CPython prints the big
integer.  ``_check_flow_int64_containers`` now walks the module statements in source order with
a small read-only model (a flat or nested literal container, a simple alias, a scalar) and
refuses the read by name.  Any statement it cannot model -- a call, loop, dead branch or
mutation -- drops the names it mentions first, so a read after a mutation, a mutating sibling,
a dead ``if`` expression or an escaping alias still matches CPython.  No code is generated
differently: the pass only raises.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

FLOAT = 'int() of a float outside int64'
RANGE = 'int64 constant expression out of range'

REFUSED = {
    'get_before_update': ('''
d = {"k": 1e300}
print(int(d.get("k")))
d.update({"k": 1.5})
''', FLOAT),
    'subscript_before_store': ('''
d = {"k": 1e300}
print(int(d["k"]))
d["k"] = 1.5
''', FLOAT),
    'alias_get_before_update': ('''
d = {"k": 1e300}
a = d
print(int(a.get("k")))
d.update({"k": 1.5})
''', FLOAT),
    'list_alias_before_store': ('''
items = [1e300]
a = items
print(int(a[0]))
items[0] = 1.5
''', FLOAT),
    'nested_before_store': ('''
d = {"k": [1e300]}
print(int(d["k"][0]))
d["k"][0] = 1.5
''', FLOAT),
    'negative_index': ('''
items = [1e300]
print(int(items[-1]))
items[0] = 1.5
''', FLOAT),
    'tuple_rebound': ('''
items = (1e300, 1.5)
print(int(items[0]))
items = (1.5, 2.5)
print(int(items[0]))
''', FLOAT),
    'big_string_before_update': ('''
d = {"k": "9223372036854775808"}
print(int(d.get("k")))
d.update({"k": "1"})
''', RANGE),
    'empty_dict_default': ('''
d = {}
print(int(d.get("k", 1e300)))
d.update({"k": 1.5})
''', FLOAT),
    'scalar_listed_in_dict': ('''
x = 1e300
d = {"k": x}
print(int(d.get("k")))
d.update({"k": 1.5})
''', FLOAT),
    'read_before_called_mutation': ('''
items = [1e300]


def clear(a):
    a[0] = 1.5


print(int(items[0]))
clear(items)
''', FLOAT),
    'alias_chain': ('''
items = [1e300]
a = items
b = a
print(int(b[0]))
a[0] = 1.5
''', FLOAT),
}

MATCH = {
    'update_before_read': '''
d = {"k": 1e300}
d.update({"k": 1.5})
print(int(d.get("k")))
''',
    'store_before_read': '''
d = {"k": 1e300}
d["k"] = 1.5
print(int(d["k"]))
''',
    'alias_after_update': '''
d = {"k": 1e300}
a = d
d.update({"k": 1.5})
print(int(a.get("k")))
''',
    'alias_store_before_read': '''
items = [1e300]
a = items
a[0] = 1.5
print(int(items[0]))
''',
    'nested_store_before_read': '''
d = {"k": [1e300]}
d["k"][0] = 1.5
print(int(d["k"][0]))
''',
    'mutating_sibling': '''
items = [1e300]


def change(a):
    a[0] = 1.5


print(change(items), int(items[0]))
''',
    'inrange': '''
items = [1e18]
print(int(items[0]))
items[0] = 1.5
''',
    'int64_max': '''
items = [9223372036854775807]
print(int(items[0]))
items[0] = 0
''',
    'dead_ifexp': '''
items = [1e300]
x = int(items[0]) if False else 0
items[0] = 1.5
print(x)
''',
    'dead_and': '''
items = [1e300]
x = 0 and int(items[0])
items[0] = 1.5
print(x)
''',
    'dict_print_update': '''
d = {"k": 1e300}
print(d.update({"k": 1.5}), int(d["k"]))
''',
    'list_insert': '''
items = [1e300]
print(items.insert(0, 1.5), int(items[0]))
''',
    'boolop_alias': '''
items = [1e300]
e = items or []
e[0] = 1.5
print(int(items[0]))
''',
    'loop_alias': '''
items = [1e300]
for e in [items]:
    e[0] = 1.5
    print(int(items[0]))
items[0] = 2.5
''',
    'constructor_alias': '''
class Box:
    def __init__(self, v):
        self.v = v


items = [1e300]
b = Box(items)
b.v[0] = 1.5
print(int(items[0]))
''',
    'call_result_alias': '''
items = [1e300]
e = list((items,))[0]
e[0] = 1.5
print(int(items[0]))
''',
    'scalar_get_after_update': '''
d = {"k": 1e300}
d.update({"k": 1.5})
a = d.get("k")
print(int(a))
''',
    'nested_extract_alias': '''
d = {"k": [1e300]}
a = d["k"]
a[0] = 1.5
print(int(d["k"][0]))
''',
    'ifexp_alias': '''
items = [1e300]
e = items if items else []
e[0] = 1.5
print(int(items[0]))
''',
    'str_inrange': '''
d = {"k": "1"}
print(int(d.get("k")))
d.update({"k": "2"})
''',
    'if_mutation_before': '''
items = [1e300]
if True:
    items[0] = 1.5
print(int(items[0]))
''',
    'while_mutation_before': '''
items = [1e300]
while True:
    items[0] = 1.5
    break
print(int(items[0]))
''',
    'try_mutation_before': '''
items = [1e300]
try:
    items[0] = 1.5
except Exception:
    pass
print(int(items[0]))
''',
    'alias_rebound': '''
items = [1e300]
a = items
items = [1.5]
a[0] = 2.5
print(int(items[0]))
''',
    'rebind_inrange_first': '''
items = [1.5]
print(int(items[0]))
items = [1e300]
''',
    'rebind_store_before_read': '''
items = [1e300]
items = [1.5]
items[0] = 2.5
print(int(items[0]))
''',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


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
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True,
                               timeout=900, env=env)


class Pre387Tests(unittest.TestCase):
    def check_refused(self, name, text, needle):
        with tempfile.TemporaryDirectory(prefix='ail-pre387-') as directory:
            for general in (True, False):
                _, built = build(directory, name + ('g' if general else 'd'), text, general)
                message = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, (name, general, message[-1200:]))
                self.assertIn(needle, message, (name, general, message[-1200:]))
                self.assertNotIn('integer overflow', message, (name, general, message[-1200:]))

    def check_program(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre387-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want.stdout,
                                 (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_read_before_mutation_is_refused(self):
        for name, (text, needle) in REFUSED.items():
            self.check_refused(name, text, needle)

    def test_mutation_before_read_matches_cpython(self):
        for name, text in MATCH.items():
            self.check_program(name, text)


if __name__ == '__main__':
    unittest.main()
