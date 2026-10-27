"""Pre356: int() of a module dict item read through dict.get() is refused when it leaves int64.

A reviewer of pre338 left ``TABLE = {"k": "9223372036854775808"}; int(TABLE.get("k"))`` open:
both builds compiled it and then stopped with ``integer overflow`` where CPython prints the big
integer.  The constant folder now resolves ``.get()`` on a module-level literal dict (and the
existing subscript route) when the dict is only read that way, so the static int() checker
refuses this route by name too.  In-range values, defaults, INT64 boundaries, mutated or
rebound dicts and programs that only read the dict keep CPython's behaviour.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre356-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre356-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'dict_get': '''
TABLE = {"k": "9223372036854775808"}
print(int(TABLE.get("k")))
''',
    'dict_get_negative': '''
TABLE = {"k": "-9223372036854775809"}
print(int(TABLE.get("k")))
''',
    'dict_get_bytes': '''
TABLE = {b"k": b"9223372036854775808"}
print(int(TABLE.get(b"k")))
''',
    'dict_get_int_value': '''
TABLE = {"k": 9223372036854775808}
print(int(TABLE.get("k")))
''',
    'dict_get_default': '''
TABLE = {"a": "1"}
print(int(TABLE.get("missing", "9223372036854775808")))
''',
    'dict_get_present_default': '''
TABLE = {"k": "9223372036854775808"}
print(int(TABLE.get("k", "0")))
''',
    'dict_get_alias': '''
TABLE = {"k": "9223372036854775808"}
ALIAS = TABLE
print(int(ALIAS.get("k")))
''',
    'dict_get_tuple_key': '''
TABLE = {(1, 2): "9223372036854775808"}
print(int(TABLE.get((1, 2))))
''',
    'dict_get_duplicate_key': '''
TABLE = {"k": "1", "k": "9223372036854775808"}
print(int(TABLE.get("k")))
''',
    'dict_get_attribute_value': '''
class Box:
    text = "9223372036854775808"


TABLE = {"k": Box.text}
print(int(TABLE.get("k")))
''',
    'dict_get_list_item_value': '''
items = ["9223372036854775808"]
TABLE = {"k": items[0]}
print(int(TABLE.get("k")))
''',
    'dict_subscript': '''
TABLE = {"k": "9223372036854775808"}
print(int(TABLE["k"]))
''',
}

MATCH = {
    'dict_get_in_range': '''
TABLE = {"k": "42"}
print(int(TABLE.get("k")))
''',
    'dict_get_default_in_range': '''
TABLE = {"a": "1"}
print(int(TABLE.get("missing", "7")))
''',
    'dict_get_boundaries': '''
TABLE = {"hi": "9223372036854775807", "lo": "-9223372036854775808"}
print(int(TABLE.get("hi")), int(TABLE.get("lo")))
''',
    'dict_get_whitespace': '''
TABLE = {"k": " 1_000 ", "other": "+45"}
print(int(TABLE.get("k")), int(TABLE.get("other")))
''',
    'dict_get_text_only': '''
TABLE = {"k": "9223372036854775808"}
print(TABLE.get("k"), TABLE.get("missing"), len(TABLE))
''',
    'dict_get_mutated': '''
TABLE = {"k": "9223372036854775808"}
TABLE["k"] = "5"
print(int(TABLE.get("k")))
''',
    'dict_get_mutated_after': '''
TABLE = {"k": "42"}
print(int(TABLE.get("k")))
TABLE["k"] = "43"
print(int(TABLE.get("k")))
''',
    'dict_get_alias_mutated': '''
TABLE = {"k": "5"}
ALIAS = TABLE
ALIAS["k"] = "6"
print(int(TABLE.get("k")))
''',
    'dict_get_global_mutation': '''
TABLE = {"k": "5"}


def bump():
    global TABLE
    TABLE["k"] = "7"


bump()
print(int(TABLE.get("k")))
''',
    'dict_get_rebound': '''
TABLE = {"k": "9223372036854775808"}
TABLE = {"k": "1"}
print(int(TABLE.get("k")))
''',
    'plain_get': '''
TABLE = {"a": 1, (1, 2): "t"}
print(TABLE.get("a"), TABLE.get("b"), TABLE.get("b", 9), TABLE.get((1, 2)))
''',
    'local_get': '''
def read():
    table = {"a": "5"}
    return int(table.get("a"))


print(read())
''',
    'other_method': '''
TABLE = {"k": "5"}
print(int(TABLE.pop("k")))
''',
}


class Pre356Tests(unittest.TestCase):
    def test_out_of_int64_dict_get_is_refused(self):
        for slug, text in REFUSED.items():
            with self.subTest(case=slug):
                check_refused(self, slug, text, 'int64 constant expression out of range')

    def test_in_range_and_mutated_dict_routes_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
