"""int(<text>, base) on the typed IR path in the default int64 mode.

Before this job the IR lowering refused `int(text, base)` outside the exact mode, so a Python-
syntax function that parsed a number kept the whole function on the legacy emitter.  The default
build now lowers a str parse through `ail_str_to_int_base`, with CPython's PyLong_FromString rules
(ASCII/Unicode whitespace and decimal digits, an optional sign, single underscores, 0x/0o/0b
prefixes for base 0 or a matching explicit base, base 0's leading-zero rule), the catchable
ValueError messages, the 4300-digit limit, and the language's loud integer-overflow stop above
int64.  Bytes with an explicit base keep the legacy emitter (the lab/compare scar_life program
parses bytes, so its generated C must not change).

The cases cover direct calls, keyword base=, values through a parameter, a list item, an
attribute, a dict value and an alias, bases supplied the same ways, both builds, every parsing
rule above, invalid literals and bases, the int64 boundaries, and the overflow stop.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

RULES = r'''def main():
    print(int('0x_ff', 16))
    print(int('0x_ff', 0))
    print(int('0b10', 16))
    print(int('0o10', 8))
    print(int('00', 0))
    print(int('0_0', 0))
    print(int('-0x10', 0))
    print(int('0X_FF', 0))
    print(int('\t\n 12\r', 10))
    print(int('１２３', 10))
    print(int('١٢٣', 10))
    print(int('z', 36))
    print(int('Z', 36))
    print(int('0b101', 0))
    print(int('0B101', 0))
    print(int('0o17', 0))
    print(int('0O17', 0))
    print(int('0x1f', 0))
    print(int('+0x1f', 0))
    print(int('  0b1_0_1  ', 0))
    print(int('0b_1_0', 2))
    for t, b in [('0x10', 10), ('010', 0), ('0_1', 0), ('_1', 10), ('1_', 10),
                 ('1__0', 10), ('+_1', 10), ('\x1c12', 10), ('1\xa02', 10),
                 ('0b', 0), ('0x', 0), ('0o', 0), ('+', 10), ('-', 10),
                 ('  ', 10), ('', 10), ('10', 37), ('10', 1), ('10', -1)]:
        try:
            print(repr(t), b, int(t, b))
        except ValueError as e:
            print(repr(t), b, type(e).__name__, str(e))


main()
'''

SHAPES = r'''class Box:
    def __init__(self, text: str, base: int):
        self.text = text
        self.base = base


def convert(text: str, base: int) -> int:
    return int(text, base)


def convert_kw(text: str, base: int) -> int:
    return int(text, base=base)


def main():
    print(convert('ff', 16))
    print(convert_kw('101', 2))
    texts = ['11', '22']
    bases = [2, 8]
    print(int(texts[0], bases[0]))
    print(int(texts[1], bases[1]))
    b = Box('777', 8)
    print(int(b.text, b.base))
    words = {'t': '101'}
    print(int(words['t'], 2))
    nums = {'b': 8}
    print(int('17', nums['b']))
    alias = texts[1]
    base_alias = bases[1]
    print(int(alias, base_alias))
    original = '  -1_0  '
    same = original
    print(int(same, 2))


main()
'''

ERRORS = r'''def main():
    for t, b in [('x', 10), ('10', 1), ('', 10), ('1_', 10), ('0x10', 10),
                 ('0b10', 0), ('1__0', 2), ('z', 35)]:
        try:
            print(repr(t), b, int(t, b))
        except ValueError as e:
            print(repr(t), b, type(e).__name__, str(e))
    for b in (10.0, '10', None, True, False):
        try:
            print(repr(b), int('10', b))
        except Exception as e:
            print(repr(b), type(e).__name__, str(e))


main()
'''

LIMIT = r'''def repeat(s: str, n: int) -> str:
    return s * n


def parse(text: str, base: int) -> int:
    return int(text, base)


def main():
    try:
        print(parse(repeat('1', 4301), 10))
    except ValueError as e:
        print(type(e).__name__, str(e))


main()
'''

IR_MAIN = r'''def main():
    print(int('ff', 16))
    print(int('0xff', 0))
    print(int('  -1_0  ', 2))
    print(int('0b101', 0))
    print(int('0o17', 0))
    print(int('z', 36))
    print(int('-9223372036854775808', 10))
    print(int('9223372036854775807', 10))
    base = 2
    s = '1010'
    print(int(s, base))
    print(int(s, base=base))


main()
'''

OVERFLOW = {
    'positive': (r'''def parse(text: str, base: int) -> int:
    return int(text, base)


def main():
    print(parse('9223372036854775807', 10))
    print(parse('9223372036854775808', 10))


main()
''', '9223372036854775807\n'),
    'negative': (r'''def parse(text: str, base: int) -> int:
    return int(text, base)


def main():
    print(parse('-9223372036854775808', 10))
    print(parse('-9223372036854775809', 10))


main()
''', '-9223372036854775808\n'),
    'hex': (r'''def parse(text: str, base: int) -> int:
    return int(text, base)


def main():
    print(parse('7fffffffffffffff', 16))
    print(parse('8000000000000000', 16))


main()
''', '9223372036854775807\n'),
    'base_zero': (r'''def parse(text: str, base: int) -> int:
    return int(text, base)


def main():
    print(parse('0x7fffffffffffffff', 0))
    print(parse('0x8000000000000000', 0))


main()
''', '9223372036854775807\n'),
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general, ir=None, debug=False):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    stats = Path(directory) / (name + '.stats')
    dbg = Path(directory) / (name + '.debug')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_IR', None)
    env.pop('AIL_IR_STATS', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    if ir is not None:
        env['AIL_IR'] = ir
        env['AIL_IR_STATS'] = str(stats)
    command = [sys.executable, '-B', CLI, 'compile', src.name,
               '--syntax', 'python', '-o', exe.name]
    if debug:
        command += ['--debug-dir', str(dbg)]
    built = subprocess.run(command, cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe, stats, dbg


def run(directory, name, text, general):
    built, exe, _, _ = build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class IntBaseTests(unittest.TestCase):
    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-intbase-') as directory:
            want, want_rc = cpython(directory, slug, text)
            for general in (True, False):
                got, err = run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, err))

    def test_parsing_rules_match_cpython(self):
        self.matches('rules', RULES)

    def test_shapes_match_cpython(self):
        self.matches('shapes', SHAPES)

    def test_invalid_literals_and_bases_match_cpython(self):
        self.matches('errors', ERRORS)

    def test_digit_limit_matches_cpython(self):
        self.matches('limit', LIMIT)

    def test_int_base_lowers_on_the_ir_path(self):
        with tempfile.TemporaryDirectory(prefix='ail-intbase-') as directory:
            built, exe, stats, dbg = build(directory, 'ir', IR_MAIN, False, ir='verify', debug=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            entries = [json.loads(line) for line in stats.read_text().splitlines()] if stats.exists() else []
            self.assertTrue(entries)
            self.assertEqual({e['path'] for e in entries}, {'ir'}, entries)
            self.assertIn('ail_str_to_int_base',
                          (dbg / 'program.c').read_text(encoding='utf-8'))

    def test_overflow_stops_loudly_on_both_builds(self):
        message = 'OverflowError: integer overflow in int()'
        with tempfile.TemporaryDirectory(prefix='ail-intbase-') as directory:
            for slug, (text, prefix) in OVERFLOW.items():
                for general in (True, False):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    built, exe, _, _ = build(directory, name, text, general)
                    self.assertEqual(built.returncode, 0, '%s\n%s' % (slug, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    stderr = got.stderr.decode('utf-8', 'replace')
                    self.assertEqual(got.returncode, 1, '%s (general=%s)\n%s' % (slug, general, stderr))
                    self.assertEqual(got.stdout.decode('utf-8'), prefix,
                                     '%s (general=%s)' % (slug, general))
                    self.assertIn(message, stderr, '%s (general=%s)' % (slug, general))


if __name__ == '__main__':
    unittest.main()
