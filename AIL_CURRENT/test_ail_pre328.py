# -*- coding: utf-8 -*-
"""pre328: slicing an instance through __getitem__ after a compound rebinding.

The pre323 reviewer recorded this as a pre-existing difference: a user-class slice whose
bound comes from a `for`, `with` or tuple-unpacking target (or an argument, list item,
attribute or dict value) compiled and then stopped with
`NotImplementedError: slicing an instance through __getitem__ is not supported: this path
has no slice objects`, while CPython passes a real slice object to __getitem__.

The general path now asks for the slice-object build whenever a slice target is not a
known str/list/tuple and any class defines __getitem__, so the runtime checks the value's
tag: an instance gets a slice object, everything else keeps the ordinary slice path.  The
bounds are evaluated exactly once, in whichever branch runs.  Both builds match CPython
for direct instances after for/with/tuple rebinding and for every route, including empty,
negative and dynamic (None) bounds and bounds with side effects.  A constant index or
slice step outside int64 is still refused by name.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None

MATCHING = {
    'direct_and_if': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)
print(C()[1:2])
a = [1, 2, 3]
if True:
    a = C()
print(a[1:2])
''',
    'for_rebinding': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)
a = [1, 2, 3]
for a in [C()]:
    pass
print(a[1:2])
print(a[-2:])
''',
    'with_rebinding': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)
class W:
    def __enter__(self):
        return C()
    def __exit__(self, *a):
        return False
a = [1, 2, 3]
with W() as a:
    pass
print(a[1:2])
''',
    'tuple_rebinding': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)
a = [1, 2, 3]
a, b = C(), None
print(a[1:2])
''',
    'routes': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)
def take(x):
    return x
c = C()
print(take(c)[1:2])
print([c][0][1:2])
class Box:
    def __init__(self):
        self.v = c
print(Box().v[1:2])
print({'k': c}['k'][1:2])
''',
    'dynamic_bounds': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)
def cut(x, a, b, c):
    return x[a:b:c]
print(cut(C(), None, None, None))
print(cut(C(), 1, None, -1))
print(cut([0, 1, 2, 3, 4], 1, 4, 2))
print(cut('abcdef', None, 3, None))
print(cut(b'abcdef', 2, None, None))
print(cut((0, 1, 2, 3), None, None, -1))
print(cut(bytearray(b'abcdef'), 1, 5, 2))
print(cut(range(10), 2, 8, 2))
''',
    'empty_and_negative': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)
def cut(x):
    return x[2:1]
print(cut(C()))
print(cut([]))
print(cut(''))
print(cut(()))
for x in [C()]:
    pass
print(x[2:1])
print(x[-3:-1])
''',
    'bounds_once': '''
class C:
    def __getitem__(self, i):
        print('getitem', i.start, i.stop, i.step)
        return i.start
count = 0
def bound(tag):
    global count
    count += 1
    print(tag, count)
    return 1
def make():
    return C()
print('result', make()[bound('lo'):bound('hi')])
''',
}

REFUSED = {
    'direct_huge_index': 'a = [1, 2, 3]\nprint(a[2**63])\n',
    'direct_huge_read': (
        'class C:\n    def __getitem__(self, i):\n'
        '        return (i.start, i.stop, i.step)\n'
        'print(C()[2**63:])\n'),
    'huge_step': (
        'class C:\n    def __getitem__(self, i):\n'
        '        return (i.start, i.stop, i.step)\n'
        'print(C()[::2**100])\n'),
    'argument_route': (
        'def take(x):\n    return x\n'
        'class C:\n    def __getitem__(self, i):\n'
        '        return (i.start, i.stop, i.step)\n'
        'print(take(C())[2**63:])\n'),
    'list_item_route': (
        'class C:\n    def __getitem__(self, i):\n'
        '        return (i.start, i.stop, i.step)\n'
        'c = C()\nprint([c][0][2**63:])\n'),
    'attribute_route': (
        'class C:\n    def __getitem__(self, i):\n'
        '        return (i.start, i.stop, i.step)\n'
        'class Box:\n    def __init__(self):\n        self.v = C()\n'
        'print(Box().v[2**63:])\n'),
    'dict_value_route': (
        'class C:\n    def __getitem__(self, i):\n'
        '        return (i.start, i.stop, i.step)\n'
        'c = C()\nprint({"k": c}["k"][2**63:])\n'),
}


def build(directory, source, general, name='p'):
    path = Path(directory, name + '.py')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(path),
                           '--syntax', 'python', '-o', str(exe)],
                          cwd=directory, capture_output=True, text=True, timeout=300, env=env), exe


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class InstanceSliceAfterRebinding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre328-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_routes_and_rebindings_match_cpython(self):
        for name, source in MATCHING.items():
            ref = Path(self.dir, name + '_ref.py')
            ref.write_text(source, encoding='utf-8')
            expected = subprocess.run([sys.executable, str(ref)], capture_output=True, timeout=60)
            for general in (False, True):
                where = '%s %s' % (name, 'general' if general else 'default')
                built, exe = build(self.dir, source, general, name)
                self.assertEqual(built.returncode, 0,
                                 where + ':\n' + built.stdout + built.stderr + '\n' + source)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
                self.assertEqual(ran.returncode, expected.returncode, where + '\n' + source)
                self.assertEqual(ran.stdout, expected.stdout, where + '\n' + source)

    def test_out_of_int64_bounds_are_still_refused_by_name(self):
        for name, source in REFUSED.items():
            for general in (False, True):
                where = '%s %s' % (name, 'general' if general else 'default')
                built, _ = build(self.dir, source, general, name)
                self.assertNotEqual(built.returncode, 0, where + ' built:\n' + source)
                text = built.stdout + built.stderr
                self.assertIn('int64', text, where + ':\n' + text)
                self.assertNotIn('integer overflow', text, where)
                self.assertNotIn('internal error', text, where)


if __name__ == '__main__':
    unittest.main()
