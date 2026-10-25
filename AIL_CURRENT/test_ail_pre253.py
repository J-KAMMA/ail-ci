"""Pre-253: a constant ``int(<text>, base)`` beyond int64 is refused by name.

AIL integers are fixed width.  ``int("1" * 5000, 2)`` used to compile on both builds and
then stop at run time with ``integer overflow``, while CPython keeps the bignum.  A call whose
text and base are both statically known is now evaluated exactly; a value outside int64 is
refused at compile time with ``int64 constant expression out of range``, wherever the call
appears.  In-range constants and dynamic strings keep their previous run-time parse.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OUT_OF_RANGE = {
    'example': '''def main():
    print(int("1" * 5000, 2))


main()
''',
    'keyword': '''def main():
    print(int("1" * 5000, base=2))


main()
''',
    'bytes': '''def main():
    print(int(b"1" * 5000, 2))


main()
''',
    'negative': '''def main():
    print(int("-" + "1" * 5000, 2))


main()
''',
    'module_constant': '''DIGITS = "1" * 5000


def main():
    print(int(DIGITS, 2))


main()
''',
    'argument': '''def show(value):
    print(value)


def main():
    show(int("1" * 5000, 2))


main()
''',
    'list_item': '''def main():
    print([int("1" * 5000, 2)][0])


main()
''',
    'attribute': '''class Box:
    value = int("1" * 5000, 2)


def main():
    print(Box.value)


main()
''',
    'dict_value': '''def main():
    print({"value": int("1" * 5000, 2)}["value"])


main()
''',
    'list_source': '''def main():
    print(int(["1" * 5000][0], 2))


main()
''',
    'dict_source': '''def main():
    print(int({"digits": "1" * 5000}["digits"], 2))


main()
''',
    'base16': '''def main():
    print(int("f" * 5000, 16))


main()
''',
    'prefixed': '''def main():
    print(int("0b" + "1" * 5000, 0))


main()
''',
    'max_plus_one': '''def main():
    print(int("9223372036854775808", 10))


main()
''',
}

IN_RANGE = r'''def main():
    print(int("1" * 18, 2), int("f" * 15, 16), int("9" * 18, 10))
    print(int("0b" + "1" * 62, 0), int("-" + "1" * 18, 2))
    print(int("  -1_0  ", 2), int(b"0xff", 16), int("z", 36))
    print(int("-9223372036854775808", 10), int("9223372036854775807", 10))
    print(int(["1" * 18][0], 2), int({"digits": "f" * 15}["digits"], 16))
    for base in [0, 2, 8, 10, 16, 36]:
        print(base, int("10", base))


main()
'''

INVALID = r'''def show(label, value, base):
    try:
        print(label, int(value, base))
    except ValueError as error:
        print(label, type(error).__name__, str(error)[:60])


def main():
    show("base-one", "1" * 5000, 1)
    show("base-high", "1" * 5000, 37)
    show("bad-digit", "x" * 5000, 2)
    show("digit-limit", "0" * 4301, 3)
    show("bad-base0", "0" * 4301 + "z", 0)


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


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


class Pre253Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre253-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn('int64 constant expression out of range', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertNotIn('integer overflow', output,
                                 '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre253-') as directory:
            want, want_rc = _cpython(directory, slug, text)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc),
                                 '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_out_of_int64_constant_int_base_is_refused(self):
        for slug, text in OUT_OF_RANGE.items():
            self.refused(slug, text)

    def test_in_range_constant_int_base_matches_cpython(self):
        self.matches('in_range', IN_RANGE)

    def test_invalid_literal_and_base_still_match_cpython(self):
        self.matches('invalid', INVALID)


if __name__ == '__main__':
    unittest.main()
