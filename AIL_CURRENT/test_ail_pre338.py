"""Pre338: int() of a class attribute read through an instance builds and matches CPython when it leaves int64.

A reviewer of pre315 left ``class Box: text = "9223372036854775808"; b = Box(); int(b.text)``
open: both builds compiled it and then stopped with ``integer overflow`` where CPython prints
the big integer.  The static int() checker now also refuses a statically known string, bytes or
int value whose conversion leaves int64, so the class-attribute-through-an-instance route was
refused by name; under exact ints it now builds on both builds and matches CPython.  In-range values, invalid text, INT64 boundaries, mutated instances and the
list/dict/argument routes keep CPython's output.
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


def cpython_last_line(directory, name, text):
    src = Path(directory) / (name + '_cpython_full.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    lines = done.stderr.decode('utf-8', 'replace').strip().splitlines()
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, (lines[-1] if lines else '')


def check_exact(test, name, text):
    """Exact ints: a value beyond int64 builds on both builds and matches CPython's stdout, exit code
    and last stderr line."""
    with tempfile.TemporaryDirectory(prefix='ail-pre338-') as directory:
        want = cpython_last_line(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, (name, general, (built.stdout + built.stderr)[-1200:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            err = got.stderr.decode('utf-8', 'replace')
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, err[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, err[-800:]))
            if want[2]:
                test.assertIn(want[2], err, (name, general))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre338-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'class_attribute_instance': '''
class Box:
    text = "9223372036854775808"

b = Box()
print(int(b.text))
''',
    'class_attribute_instance_negative': '''
class Box:
    text = "-9223372036854775809"

b = Box()
print(int(b.text))
''',
    'class_attribute_instance_bytes': '''
class Box:
    text = b"9223372036854775808"

b = Box()
print(int(b.text))
''',
    'class_attribute_instance_alias': '''
class Box:
    text = "9223372036854775808"

D = Box
b = D()
print(int(b.text))
''',
    'class_attribute_instance_list_item': '''
class Box:
    text = "9223372036854775808"

items = [Box()]
print(int(items[0].text))
''',
    'class_attribute_instance_dict_value': '''
class Box:
    text = "9223372036854775808"

table = {"box": Box()}
print(int(table["box"].text))
''',
    'class_attribute_instance_argument': '''
class Box:
    text = "9223372036854775808"


def identity(value):
    return value


b = Box()
print(int(identity(b.text)))
''',
    'init_attribute': '''
class Box:
    def __init__(self):
        self.text = "9223372036854775808"

b = Box()
print(int(b.text))
''',
}

FLOAT = {
    'class_attribute_float': '''
class Box:
    value = 1e300

b = Box()
print(int(b.value))
''',
}

MATCH = {
    'in_range': '''
class Box:
    text = "45"

b = Box()
print(int(b.text))
''',
    'boundaries': '''
class Box:
    high = "9223372036854775807"
    low = "-9223372036854775808"

b = Box()
print(int(b.high), int(b.low))
''',
    'whitespace': '''
class Box:
    text = " 1_000 "
    other = "+45"

b = Box()
print(int(b.text), int(b.other))
''',
    'mutated_instance': '''
class Box:
    text = "9223372036854775808"

b = Box()
b.text = "5"
print(int(b.text))
''',
    'mutated_alias': '''
class Box:
    text = "9223372036854775808"

b = Box()
alias = b
alias.text = "5"
print(int(b.text))
''',
    'init_shadows_class': '''
class Box:
    text = "9223372036854775808"

    def __init__(self):
        self.text = "5"


b = Box()
print(int(b.text))
''',
    'class_int_in_range': '''
class Box:
    text = 45

b = Box()
print(int(b.text))
''',
    'invalid_text': '''
class Box:
    text = "12x"

b = Box()
print(int(b.text))
''',
    'empty_text': '''
class Box:
    text = ""

b = Box()
print(int(b.text))
''',
}


class Pre338Tests(unittest.TestCase):
    def test_out_of_int64_class_attribute_through_instance_matches_cpython(self):
        for slug, text in REFUSED.items():
            with self.subTest(case=slug):
                check_exact(self, slug, text)
        for slug, text in FLOAT.items():
            with self.subTest(case=slug):
                check_exact(self, slug, text)

    def test_in_range_invalid_and_mutated_routes_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
