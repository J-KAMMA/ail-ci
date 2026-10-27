"""Pre376: int() of a class attribute read as ``self.attr`` in a method.

The pre359 review's ``r10`` probe (a method-local variable sharing the class attribute's name)
compiled on both builds and then stopped with ``integer overflow`` where CPython prints the big
integer.  The static int() fold now resolves ``self.attr`` in a plain instance method of a known
class, including a method-local variable bound from it and a list/dict/tuple item, so an
out-of-int64 value is refused by name at compile time with the existing messages.  The read is
left unknown when a subclass overrides the name, an instance store shadows it, the attribute is
mutated in place, or ``self`` is rebound; in-range values keep CPython's output.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre376-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre376-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


FLOAT = 'int() of a float outside int64'
STRING = 'int64 constant expression out of range'

REFUSED = {
    'self_attr_direct': ('''
class Box:
    text = 1e300
    def get(self):
        return int(self.text)
print(Box().get())
''', FLOAT),
    'method_local_shares_name': ('''
class Box:
    text = 1e300
    def get(self):
        text = self.text
        return int(text)
print(Box().get())
''', FLOAT),
    'method_local_string': ('''
class Box:
    text = "9223372036854775808"
    def get(self):
        text = self.text
        return int(text)
print(Box().get())
''', STRING),
    'subclass_inherits_method': ('''
class Box:
    text = 1e300
    def get(self):
        return int(self.text)
class Sub(Box):
    pass
print(Sub().get())
''', FLOAT),
    'negative': ('''
class Box:
    text = -1e300
    def get(self):
        return int(self.text)
print(Box().get())
''', FLOAT),
    'list_item': ('''
class Box:
    text = [1e300]
    def get(self):
        return int(self.text[0])
print(Box().get())
''', FLOAT),
    'dict_value': ('''
class Box:
    text = {"k": 1e300}
    def get(self):
        return int(self.text["k"])
print(Box().get())
''', FLOAT),
    'tuple_item': ('''
class Box:
    text = (1e300,)
    def get(self):
        return int(self.text[0])
print(Box().get())
''', FLOAT),
    'instance_through_argument': ('''
class Box:
    text = 1e300
    def get(self):
        return int(self.text)
def run(o):
    return o.get()
print(run(Box()))
''', FLOAT),
}

MATCH = {
    'in_range_direct': '''
class Box:
    text = 2.5
    def get(self):
        return int(self.text)
print(Box().get())
''',
    'in_range_local': '''
class Box:
    text = 2.5
    def get(self):
        text = self.text
        return int(text)
print(Box().get())
''',
    'subclass_override': '''
class Box:
    text = 1e300
    def get(self):
        return int(self.text)
class Sub(Box):
    text = 45
print(Sub().get())
''',
    'subclass_container_override': '''
class Box:
    text = [1e300]
    def get(self):
        return int(self.text[0])
class Sub(Box):
    text = [45]
print(Sub().get())
''',
    'init_store_shadows_class': '''
class Box:
    text = 1e300
    def __init__(self):
        self.text = 45
    def get(self):
        return int(self.text)
print(Box().get())
''',
    'store_after_construction': '''
class Box:
    text = 45
    def get(self):
        return int(self.text)
b = Box()
b.text = 5
print(b.get())
''',
    'mutated_container': '''
class Box:
    text = [1e300]
    def get(self):
        return int(self.text[0])
Box.text[0] = 5
print(Box().get())
''',
    'empty_string': '''
class Box:
    text = ""
    def get(self):
        return int(self.text)
print(Box().get())
''',
    'bool_attribute': '''
class Box:
    text = True
    def get(self):
        return int(self.text)
print(Box().get())
''',
    'int64_max_attribute': '''
class Box:
    text = 9223372036854775807
    def get(self):
        return int(self.text)
print(Box().get())
''',
}


class Pre376Tests(unittest.TestCase):
    def test_self_class_attribute_outside_int64_is_refused(self):
        for slug, (text, needle) in REFUSED.items():
            with self.subTest(case=slug):
                check_refused(self, slug, text, needle)

    def test_safe_self_attribute_reads_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
