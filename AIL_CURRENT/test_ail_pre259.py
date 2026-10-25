"""Pre-259: an out-of-int64 constant ``int(text, base)`` is refused by name.

AIL integers are fixed width.  A valid literal such as ``int("x" * 199, 36)`` (a
310-digit base-36 number) compiled and then stopped with ``integer overflow`` on both
builds, while CPython prints the bignum.  Constant text (literals, ``+``, ``*``,
bytes/bytearray constructors and single-assignment constants in the same or an
enclosing scope) and base are now folded; a value outside int64 is refused at compile
time with the existing ``int64 constant expression out of range`` wording.  Invalid
literals keep CPython's run-time ValueError, in-range values match CPython, and values
that reach the call only as unbound variables keep the fixed-width run-time trap.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OUT_OF_RANGE = {
    'direct': '''def main():
    print(int("x" * 199, 36))


main()
''',
    'bytes': '''def main():
    print(int(b"x" * 199, 36))


main()
''',
    'bytearray': '''def main():
    print(int(bytearray(b"x" * 199), 36))


main()
''',
    'concat': '''def main():
    print(int("x" * 100 + "y" * 99, 36))


main()
''',
    'base_zero': '''def main():
    print(int("0x" + "f" * 16, 0))


main()
''',
    'base_16': '''def main():
    print(int("f" * 16, 16))


main()
''',
    'decimal_long': '''def main():
    print(int("9" * 19, 10))


main()
''',
    'negative': '''def main():
    print(int("-" + "9" * 19, 10))


main()
''',
    'keyword_base': '''def main():
    print(int("x" * 199, base=36))


main()
''',
    'module_constant': '''TEXT = "x" * 199
BASE = 36


def main():
    print(int(TEXT, BASE))


main()
''',
    'argument': '''def show(value):
    print(value)


def main():
    show(int("x" * 199, 36))


main()
''',
    'list_item': '''def main():
    print([int("x" * 199, 36)][0])


main()
''',
    'attribute': '''class Box:
    value = int("x" * 199, 36)


def main():
    print(Box.value)


main()
''',
    'dict_value': '''def main():
    print({"value": int("x" * 199, 36)}["value"])


main()
''',
    'local_alias': '''def convert():
    text = "x" * 199
    alias = text
    return int(alias, 36)


def main():
    print(convert())


main()
''',
}

GLOBAL_REBOUND = {
    'module_call': '''V = "x" * 199


def reset():
    global V
    V = "1"


reset()
print(int(V, 36))
''',
    'main_call': '''V = "x" * 199


def reset():
    global V
    V = "1"


def main():
    reset()
    print(int(V, 36))


main()
''',
}

IN_RANGE = r'''def show(label, fn):
    try:
        value = fn()
        print(label, len(str(value)), str(value)[:20], str(value)[-20:])
    except Exception as e:
        print(label, type(e).__name__, str(e))


MAX_TEXT = "9223372036854775807"
MIN_TEXT = "-9223372036854775808"
BASE = 10


def convert(text, base):
    return int(text, base)


def main():
    show("max", lambda: int(MAX_TEXT, BASE))
    show("min", lambda: int(MIN_TEXT, BASE))
    show("18", lambda: int("1" * 18, 10))
    show("19", lambda: int("1" * 19, 10))
    show("base2", lambda: int("1" * 62, 2))
    show("base16", lambda: int("f" * 15, 16))
    show("base36", lambda: int("z" * 12, 36))
    show("empty", lambda: int("", 10))
    show("bad", lambda: int("z" * 199, 10))
    show("prefix", lambda: int("0x" + "f" * 14, 0))
    show("bytes", lambda: int(b"123", 10))
    show("bytearray", lambda: int(bytearray(b"123"), 10))
    show("concat", lambda: int("12" + "3", 10))
    show("argument", lambda: convert("123", 10))
    print(convert("100", 2), int(" 42 ", 10), int("ff", 16), int("1_0", 2))


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre259Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre259-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn('int64 constant expression out of range', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre259-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_out_of_range_constant_int_is_refused(self):
        for slug, text in OUT_OF_RANGE.items():
            self.refused(slug, text)

    def test_in_range_constant_int_matches_cpython(self):
        self.matches('in_range', IN_RANGE)

    def test_global_rebound_module_constant_matches_cpython(self):
        for slug, text in GLOBAL_REBOUND.items():
            self.matches(slug, text)


if __name__ == '__main__':
    unittest.main()
