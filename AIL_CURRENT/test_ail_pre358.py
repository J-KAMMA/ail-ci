"""Pre358: int() of a statically known dict.get() result is refused when it leaves int64.

A reviewer of pre338 left ``d = {"k": "9223372036854775808"}; print(int(d.get("k")))`` open:
both builds compiled it and then stopped with ``integer overflow`` where CPython prints the big
integer.  The int64 constant fold now reads ``dict.get`` with a constant key (and an optional
constant default), and a module-level dict literal whose only uses are subscript reads or
``.get`` calls stays foldable.  Dicts mutated in place, an instance attribute holding the dict,
and dynamic keys or values keep the pre-existing route and are not folded.
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
    and last stderr line (the int64-era tests refused these programs by name)."""
    with tempfile.TemporaryDirectory(prefix='ail-pre358-') as directory:
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


def check_refused(test, name, text, needle):
    with tempfile.TemporaryDirectory(prefix='ail-pre358-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre358-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'dict_get': '''
d = {"k": "9223372036854775808"}
print(int(d.get("k")))
''',
    'inline_get': '''
print(int({"k": "9223372036854775808"}.get("k")))
''',
    'negative': '''
d = {"k": "-9223372036854775809"}
print(int(d.get("k")))
''',
    'bytes': '''
d = {"k": b"9223372036854775808"}
print(int(d.get("k")))
''',
    'whitespace': '''
d = {"k": "  +9_223_372_036_854_775_808  "}
print(int(d.get("k")))
''',
    'default': '''
d = {"k": "1"}
print(int(d.get("missing", "9223372036854775808")))
''',
    'empty_default': '''
d = {}
print(int(d.get("missing", "-9223372036854775809")))
''',
    'alias': '''
d = {"k": "9223372036854775808"}
e = d
print(int(e.get("k")))
''',
    'key_from_list': '''
keys = ["k"]
d = {"k": "9223372036854775808"}
print(int(d.get(keys[0])))
''',
    'key_from_dict': '''
names = {"key": "k"}
d = {"k": "-9223372036854775809"}
print(int(d.get(names["key"])))
''',
    'key_from_attribute': '''
class Keys:
    name = "k"

d = {"k": "9223372036854775808"}
print(int(d.get(Keys.name)))
''',
}

FLOAT = {
    'float_value': '''
d = {"k": 1e300}
print(int(d.get("k")))
''',
    'float_default': '''
d = {}
print(int(d.get("missing", -1e300)))
''',
}

MATCH = {
    'in_range': '''
d = {"k": "42", "n": "-7"}
print(int(d.get("k")))
print(int(d.get("n")))
print(int(d.get("missing", "5")))
''',
    'int_value': '''
d = {"k": 42}
print(int(d.get("k")))
''',
    'boundaries': '''
d = {"hi": "9223372036854775807", "lo": "-9223372036854775808"}
print(int(d.get("hi")))
print(int(d.get("lo")))
print(int(d.get("missing", "-9223372036854775808")))
print(int(d.get("hi", "9223372036854775809")))
''',
    'default_unused': '''
d = {"k": "6"}
print(int(d.get("k", "9223372036854775808")))
''',
    'mutated_subscript': '''
d = {"k": "9223372036854775808"}
d["k"] = "12"
print(int(d.get("k")))
''',
    'mutated_update': '''
d = {"k": "9223372036854775808"}
d.update({"k": "-13"})
print(int(d.get("k")))
''',
    'dynamic_value': '''
import sys
d = {"k": sys.argv[1] if len(sys.argv) > 1 else "9"}
print(int(d.get("k")))
''',
    'instance_attribute_dict_mutated': '''
class Box:
    d = {"k": "9223372036854775808"}

b = Box()
b.d["k"] = "1"
print(int(b.d.get("k")))
''',
    'invalid_text': '''
d = {"k": "12x"}
try:
    print(int(d.get("k")))
except ValueError as error:
    print("ValueError", str(error))
''',
}


class Pre358Tests(unittest.TestCase):
    def test_static_dict_get_out_of_int64_is_refused(self):
        for slug, text in REFUSED.items():
            with self.subTest(case=slug):
                check_exact(self, slug, text)
        for slug, text in FLOAT.items():
            with self.subTest(case=slug):
                check_exact(self, slug, text)

    def test_in_range_mutated_and_dynamic_routes_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
