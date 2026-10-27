"""Pre359: int() of an inherited class attribute outside int64 is refused by name.

The pre337 review recorded as pre-existing that ``int(Sub().text)`` on a subclass of a class
whose class attribute is a float outside int64 compiled and then stopped with ``integer
overflow``, where CPython prints the big integer.  The class-attribute fold now follows a single
plain base (also through a base alias and a chain), so an inherited class or instance attribute
reaches the static int() check.  The same review's ``xs.__setitem__`` lambda route is already
refused by name on both builds and is pinned here as a named refusal.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre359-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre359-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'subclass_instance': ('''
class Box:
    text = 1e300

class Sub(Box):
    pass

b = Sub()
print(int(b.text))
''', 'int() of a float outside int64'),
    'subclass_class': ('''
class Box:
    text = 1e300

class Sub(Box):
    pass

print(int(Sub.text))
''', 'int() of a float outside int64'),
    'inheritance_chain': ('''
class Box:
    text = 1e300

class Mid(Box):
    pass

class Sub(Mid):
    pass

print(int(Sub().text))
''', 'int() of a float outside int64'),
    'base_alias': ('''
class Box:
    text = 1e300

Alias = Box

class Sub(Alias):
    pass

print(int(Sub.text))
''', 'int() of a float outside int64'),
    'subclass_alias': ('''
class Box:
    text = 1e300

class Sub(Box):
    pass

Alias = Sub
print(int(Alias.text))
''', 'int() of a float outside int64'),
    'override_out_of_range': ('''
class Box:
    text = 2.5

class Sub(Box):
    text = 9.3e18

print(int(Sub.text))
''', 'int() of a float outside int64'),
    'inherited_init_parameter': ('''
class Box:
    def __init__(self, v):
        self.v = v

class Sub(Box):
    pass

print(int(Sub(1e300).v))
''', 'int() of a float outside int64'),
    'negative': ('''
class Box:
    text = -1e300

class Sub(Box):
    pass

print(int(Sub().text))
''', 'int() of a float outside int64'),
    'module_constant': ('''
V = 1e300

class Box:
    text = V

class Sub(Box):
    pass

print(int(Sub.text))
''', 'int() of a float outside int64'),
    'inherited_string': ('''
class Box:
    text = "9223372036854775808"

class Sub(Box):
    pass

print(int(Sub().text))
''', 'int64 constant expression out of range'),
    'list_item': ('''
class Box:
    text = [1e300]

class Sub(Box):
    pass

print(int(Sub().text[0]))
''', 'int() of a float outside int64'),
    'dict_value': ('''
class Box:
    text = {"k": 1e300}

class Sub(Box):
    pass

print(int(Sub().text["k"]))
''', 'int() of a float outside int64'),
    'argument': ('''
class Box:
    text = 1e300

class Sub(Box):
    pass

def convert(x):
    return int(x)

print(convert(Sub().text))
''', 'int() of a float outside int64'),
    'local': ('''
class Box:
    text = 1e300

class Sub(Box):
    pass

v = Sub().text
print(int(v))
''', 'int() of a float outside int64'),
    'lambda_setitem': ('''
bump = lambda xs: xs.__setitem__(0, 1.5)
a = [1e300]
bump(a)

def convert(items):
    return int(items[0])

print(convert(a))
''', '.__setitem__'),
}

MATCH = {
    'subclass_override_in_range': '''
class Box:
    text = 1e300

class Sub(Box):
    text = 45

b = Sub()
print(int(b.text), int(Sub.text))
''',
    'subclass_float_in_range': '''
class Box:
    text = 1.5

class Sub(Box):
    pass

b = Sub()
print(int(b.text), int(Sub.text))
''',
    'inherited_init_parameter_in_range': '''
class Box:
    def __init__(self, v):
        self.v = v

class Sub(Box):
    pass

print(int(Sub(2.5).v))
''',
    'own_init_override': '''
class Box:
    def __init__(self, v):
        self.v = v

class Sub(Box):
    def __init__(self):
        self.v = 2.5

print(int(Sub().v))
''',
    'plain_class': '''
class Box:
    text = 2.5

b = Box()
print(int(b.text))
''',
    'unrelated_base_in_range': '''
class Base:
    other = 3

class Sub(Base):
    text = 2.5

print(int(Sub().text))
''',
}


class Pre359Tests(unittest.TestCase):
    def test_inherited_out_of_int64_attribute_is_refused(self):
        for slug, (text, needle) in REFUSED.items():
            with self.subTest(case=slug):
                check_refused(self, slug, text, needle)

    def test_in_range_and_own_attributes_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
