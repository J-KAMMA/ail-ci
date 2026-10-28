"""Pre-392: int() of out-of-int64 text read from a container and converted in a wrapper.

The pre370 review recorded as pre-existing that ``show(d["k"])`` and ``show(items[0])``, with
the value read from a bound container and converted inside the helper, compiled on both builds
and then stopped with ``integer overflow`` where CPython prints the bignum.  The wrapper pass
applied only the float check to the argument reaching ``int(<parameter>)``; the int/text check
that the direct ``int(...)`` branch already makes was never applied there.  It is now, so an
out-of-int64 text (or bytes) value arriving through a dict value, a list item, an attribute, an
alias, ``dict.get``, a keyword or a wrapper chain is refused by name on both builds.

In-range text, invalid text, dynamic text, a container mutated to an in-range value, a
reassigned binding and a helper that does not convert still match CPython.  A nested container
(the item is itself a list/dict, ``int(v[0])``) keeps the pre-existing run-time limit that
pre322 documented for nested containers; it is not changed here.
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


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
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
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


BIG = '9223372036854775808'

REFUSED = {
    'dict_value': '''def show(v):
    print(int(v))


d = {"k": "9223372036854775808"}
show(d["k"])
''',
    'list_item': '''def show(v):
    print(int(v))


items = ["9223372036854775808"]
show(items[0])
''',
    'negative': '''def show(v):
    print(int(v))


d = {"k": "-9223372036854775809"}
show(d["k"])
''',
    'whitespace_underscores_plus': '''def show(v):
    print(int(v))


items = ["  +9_223_372_036_854_775_808  "]
show(items[0])
''',
    'bytes': '''def show(v):
    print(int(v))


d = {"k": b"9223372036854775808"}
show(d["k"])
''',
    'attribute': '''class Box:
    text = "9223372036854775808"


def show(v):
    print(int(v))


b = Box()
show(Box.text)
show(b.text)
''',
    'wrapper_chain': '''def ident(v):
    return v


def outer(v):
    return inner(v)


def inner(v):
    print(int(v))


d = {"k": "9223372036854775808"}
outer(ident(d["k"]))
''',
    'alias': '''def show(v):
    print(int(v))


d = {"k": "9223372036854775808"}
t = d["k"]
show(t)
''',
    'dict_get': '''def show(v):
    print(int(v))


d = {"k": "9223372036854775808"}
show(d.get("k"))
empty = {}
show(empty.get("missing", "9223372036854775808"))
''',
    'tuple_negative_index': '''def show(v):
    print(int(v))


items = ("1", "9223372036854775808")
show(items[-1])
''',
    'int_key': '''def show(v):
    print(int(v))


d = {0: "9223372036854775808"}
show(d[0])
''',
    'keyword_multi_parameter': '''def show(tag, v):
    print(tag, int(v))


d = {"k": "9223372036854775808"}
show("x", v=d["k"])
''',
    'local_container': '''def show(v):
    print(int(v))


def main():
    d = {"k": "9223372036854775808"}
    show(d["k"])


main()
''',
    'in_range_then_out_of_range': '''def show(v):
    print(int(v))


d = {"a": "7"}
show(d["a"])
show({"k": "9223372036854775808"}["k"])
''',
}

MATCHES = {
    'in_range': '''def show(v):
    print(int(v))


d = {"k": "9223372036854775807"}
items = ["-9223372036854775808"]
show(d["k"])
show(items[0])
show("  +1_0  ")
show(b" 42 ")
show(d.get("missing", "7"))
print(int("0"), int("-0"), int("+0"))
''',
    'invalid_text': '''def show(v):
    try:
        print(int(v))
    except ValueError as e:
        print("VE", e)


d = {"k": "0x10"}
show(d["k"])
items = [""]
show(items[0])
show({"x": "z"}["x"])
''',
    'mutated_to_in_range': '''def show(v):
    print(int(v))


d = {"k": "9223372036854775808"}
d["k"] = "1"
show(d["k"])
''',
    'reassigned_binding': '''def show(v):
    print(int(v))


t = "9223372036854775808"
t = "1"
show(t)
''',
    'no_conversion': '''def show(v):
    print(v)


d = {"k": "9223372036854775808"}
show(d["k"])
items = ["9223372036854775808"]
show(items[0])
''',
    'float_in_range': '''def show(v):
    print(int(v))


d = {"k": 1.5}
show(d["k"])
items = [-2.5]
show(items[0])
''',
    'dynamic_in_range': '''def show(v):
    print(int(v))


def main():
    d = {"k": "42"}
    key = "k".replace("k", "k")
    show(d[key])


main()
''',
}

FLOAT_CONTROL = '''def show(v):
    print(int(v))


d = {"k": 1e300}
show(d["k"])
'''


class Pre392Tests(unittest.TestCase):
    def check_refused(self, slug, text, message):
        with tempfile.TemporaryDirectory(prefix='ail-pre392-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                exe, built = build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (slug, general, output[-2000:]))
                self.assertIn(message, output, (slug, general, output[-2000:]))

    def check_matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre392-') as directory:
            want = cpython(directory, slug, text)
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (slug, general, (built.stdout + built.stderr)[-2000:]))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (slug, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_text_from_containers_refused(self):
        for slug, text in REFUSED.items():
            with self.subTest(slug=slug):
                self.check_refused(slug, text, 'int64 constant expression out of range')

    def test_in_range_and_dynamic_match_cpython(self):
        for slug, text in MATCHES.items():
            with self.subTest(slug=slug):
                self.check_matches(slug, text)

    def test_float_control_still_refused(self):
        self.check_refused('float_control', FLOAT_CONTROL, 'int() of a float outside int64')


if __name__ == '__main__':
    unittest.main()
