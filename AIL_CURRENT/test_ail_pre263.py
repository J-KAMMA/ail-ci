"""Pre-263: a constant single-argument ``int(<text>)`` beyond int64 is refused by name.

AIL integers are fixed width.  ``int("9999999999999999999")`` used to compile on both builds
and then stop with ``integer overflow``, while CPython keeps the bignum.  A call whose text is
statically known (with no explicit base, so CPython's base 10 applies) is now evaluated exactly;
a value outside int64 is refused at compile time with ``int64 constant expression out of range``,
wherever the call appears.  In-range constants, invalid literals and dynamic strings keep their
previous run-time parse.
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
    print(int("9999999999999999999"))


main()
''',
    'negative': '''def main():
    print(int("-9999999999999999999"))


main()
''',
    'bytes': '''def main():
    print(int(b"9999999999999999999"))


main()
''',
    'whitespace_underscores_plus': '''def main():
    print(int("  +9_999_999_999_999_999_999  "))


main()
''',
    'module_constant': '''DIGITS = "9999999999999999999"


def main():
    print(int(DIGITS))


main()
''',
    'module_alias': '''DIGITS = "9999999999999999999"
TEXT = DIGITS


def main():
    print(int(TEXT))


main()
''',
    'argument': '''def show(value):
    print(value)


def main():
    show(int("9999999999999999999"))


main()
''',
    'list_item': '''def main():
    print([int("9999999999999999999")][0])


main()
''',
    'attribute': '''class Box:
    value = int("9999999999999999999")


def main():
    print(Box.value)


main()
''',
    'dict_value': '''def main():
    print({"value": int("9999999999999999999")}["value"])


main()
''',
    'list_source': '''def main():
    print(int(["9999999999999999999"][0]))


main()
''',
    'dict_source': '''def main():
    print(int({"digits": "9999999999999999999"}["digits"]))


main()
''',
    'tuple_source': '''def main():
    print(int(("9999999999999999999",)[0]))


main()
''',
    'tuple_source_negative_index': '''def main():
    print(int(("1", b"9999999999999999999")[-1]))


main()
''',
    'max_plus_one': '''def main():
    print(int("9223372036854775808"))


main()
''',
    'min_minus_one': '''def main():
    print(int("-9223372036854775809"))


main()
''',
}

IN_RANGE = r'''def main():
    print(int("9223372036854775807"), int("-9223372036854775808"))
    print(int("  +10  "), int("1_0"), int(b" 42 "))
    print(int("010"), int("0010"))
    print(int(["123"][0]), int({"n": "456"}["n"]))
    print(int(DIGITS))


DIGITS = "789"


main()
'''

INVALID = r'''def show(text):
    try:
        print(text[:8], int(text))
    except ValueError as error:
        print(text[:8], type(error).__name__)


def main():
    for text in ["0x10", "  -1_0  ", "1__0", "", "z", "0b10", "+-3"]:
        show(text)


main()
'''

DYNAMIC = r'''def parse(text):
    return int(text)


def main():
    print(parse("42"), parse("-7"), parse(" 8 "))


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


class Pre263Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre263-') as directory:
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
        with tempfile.TemporaryDirectory(prefix='ail-pre263-') as directory:
            want, want_rc = _cpython(directory, slug, text)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc),
                                 '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_out_of_int64_single_argument_int_is_refused(self):
        for slug, text in OUT_OF_RANGE.items():
            self.refused(slug, text)

    def test_in_range_single_argument_int_matches_cpython(self):
        self.matches('in_range', IN_RANGE)

    def test_invalid_literal_still_matches_cpython(self):
        self.matches('invalid', INVALID)

    def test_dynamic_text_still_matches_cpython(self):
        self.matches('dynamic', DYNAMIC)


if __name__ == '__main__':
    unittest.main()
