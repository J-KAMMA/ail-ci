"""`input().split()` + `int(f[k])` in a stdin loop: the fast runtime path matches CPython.

A per-line `let f = input().split(); t += int(f[0]) + ...` loop used to pay 453 instructions for
`input()`, 350 for `.split()` and 345 for the four `int()` calls (86 per field) on q0.in. The
runtime now copies and classifies an ASCII line in one pass, splits ASCII text with the class
table alone (no `ail__ws_width` decode), reuses the list spine across iterations, releases the
one-block line in `ail_sarena_keep_roots` without the general walk, and parses a 1-18 digit
token inline.

Every case below is judged by CPython 3.12 on the same bytes, in the default build and with
AIL_UNIFIED_FORCE=1: the split probe covers tabs, CRLF, leading/trailing blanks, empty lines, a
last line without `\\n`, more than 32 fields and non-ASCII whitespace (U+3000 splits, U+00A0
does not); the int probe covers `-0`, `+5`, `007`, 18/19/20 digits and both int64 ends. Invalid
UTF-8 and EOF inside the loop stop with CPython's exception name and an exit status of 1, and a
value of 2**70 is the loud overflow stop in the default and forced-general builds and the exact
value under --exact-int.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SPLIT = r'''
def main():
    n = int(input())
    for i in range(n):
        f = input().split()
        if len(f) == 0:
            print("0|")
        else:
            print(str(len(f)) + "|" + f[0] + "|" + f[-1])
main()
'''

INTS = r'''
def main():
    n = int(input())
    for i in range(n):
        f = input().split()
        print(int(f[0]) + int(f[1]) + int(f[2]) + int(f[3]))
main()
'''

FORTY = " ".join("v%d" % k for k in range(40))

SPLIT_CASES = {
    "tabs": "3\na\tb\tc\nd e\t f\n\t\n",
    "crlf": "2\r\na b c\r\nd e f\r\n",
    "blanks": "3\n   a b   \n  \t x y \t \n \n",
    "empty_lines": "4\n\na b\n\nc\n",
    "no_final_newline": "2\na b c\nd e f",
    "forty_fields": "2\n%s\n%s\n" % (FORTY, FORTY),
    "u3000": "3\na\u3000b c\nx y\u3000z\n\u3000\u3000q\n",
    "u00a0_is_not_whitespace": "3\na\u00a0b c\nd e f\nx\u00a0\u00a0y\n",
    "one_field": "2\nsolo\nsolo\r\n",
}

INT_CASES = {
    "signs_and_padding": "4\n-0 0 0 0\n+5 1 0 0\n007 0 0 0\n-0042 1 0 0\n",
    "eighteen_digits": "2\n999999999999999999 1 0 0\n-999999999999999999 0 0 0\n",
    "nineteen_digits": "2\n1 1 0 0\n9999999999999999999 1 0 0\n",
    "twenty_digits": "2\n1 1 0 0\n12345678901234567890 1 0 0\n",
    "int64_min": "2\n1 1 0 0\n-9223372036854775808 0 0 0\n",
    "int64_max_plus_one": "2\n1 1 0 0\n9223372036854775808 0 0 0\n",
    "two_pow_70": "2\n1 1 0 0\n1180591620717411303424 1 0 0\n",
}

# the last line of these is beyond int64: the default build stops there, --exact-int prints it
OVERFLOW = {"nineteen_digits", "twenty_digits", "int64_max_plus_one", "two_pow_70"}

INVALID_UTF8 = b"1\nx \xff y\n"
EOF_IN_LOOP = b"3\na b c\n"


def env_for(mode):
    env = dict(os.environ)
    for key in ('AIL_UNIFIED_FORCE', 'AIL_EXACT_INT', 'AIL_BIGINT', 'AIL_NO_GENERAL',
                'AIL_UNIFIED', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    env['AIL_NO_CACHE'] = '1'
    if mode == 'force':
        env['AIL_UNIFIED_FORCE'] = '1'
    if mode == 'exact':
        env['AIL_EXACT_INT'] = '1'
    return env


def build(directory, text, name, mode='default'):
    source = Path(directory, name + '.py')
    source.write_text(text)
    exe = Path(directory, name + '_' + mode)
    args = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
            '--syntax', 'python', '-o', exe.name]
    if mode == 'default':
        args.append('--strict')
    made = subprocess.run(args, cwd=directory, capture_output=True, text=True, timeout=900,
                          env=env_for(mode))
    return made, exe


def run(exe, payload):
    r = subprocess.run([str(exe)], input=payload, capture_output=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def cpython(directory, text, payload):
    source = Path(directory, 'ref.py')
    source.write_text(text)
    r = subprocess.run([sys.executable, str(source)], input=payload, capture_output=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


class StdinSplitFastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exe = {}
        for mode in ('default', 'force'):
            made, exe = build(cls.tmp.name, SPLIT, 'split', mode)
            if made.returncode:
                raise AssertionError('split %s did not build: %s' % (mode, made.stdout + made.stderr))
            cls.exe['split', mode] = exe
        for mode in ('default', 'force', 'exact'):
            made, exe = build(cls.tmp.name, INTS, 'ints', mode)
            if made.returncode:
                raise AssertionError('ints %s did not build: %s' % (mode, made.stdout + made.stderr))
            cls.exe['ints', mode] = exe

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_default_build_is_typed_and_uses_the_rebinding_split(self):
        c_file = Path(self.tmp.name) / 'split.c'
        built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                str(Path(self.tmp.name) / 'split.py'), '--syntax', 'python',
                                '--strict', '-o', str(Path(self.tmp.name) / 'split_chk'),
                                '--debug-dir', str(Path(self.tmp.name) / 'dbg')],
                               capture_output=True, text=True, timeout=900, env=env_for('default'))
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        c_file = Path(self.tmp.name) / 'dbg' / 'program.c'
        text = c_file.read_text()
        self.assertIn('ail_str_split_ws_into(', text)
        self.assertIn('ail_str_to_int(', text)

    def test_split_cases_match_cpython(self):
        for name, payload in SPLIT_CASES.items():
            expected = cpython(self.tmp.name, SPLIT, payload.encode('utf-8'))
            self.assertEqual(expected[0], 0, expected[2])
            for mode in ('default', 'force'):
                with self.subTest(case=name, mode=mode):
                    got = run(self.exe['split', mode], payload.encode('utf-8'))
                    self.assertEqual((got[0], got[1]), (0, expected[1]),
                                     '%s %s: %r' % (name, mode, got[2][-400:]))

    def test_int_cases_match_cpython(self):
        for name, payload in INT_CASES.items():
            expected = cpython(self.tmp.name, INTS, payload.encode('ascii'))
            self.assertEqual(expected[0], 0, expected[2])
            kept = expected[1].splitlines(keepends=True)
            for mode in ('default', 'force'):
                with self.subTest(case=name, mode=mode):
                    got = run(self.exe['ints', mode], payload.encode('ascii'))
                    if name in OVERFLOW:
                        # both builds stop loudly at the value beyond int64, with the lines
                        # before it printed exactly as CPython prints them
                        self.assertEqual(got[0], 1)
                        self.assertEqual(got[1], b''.join(kept[:-1]))
                        self.assertIn(b'OverflowError', got[2])
                    else:
                        self.assertEqual((got[0], got[1]), (0, expected[1]),
                                         '%s %s: %r' % (name, mode, got[2][-400:]))

    def test_exact_int_prints_the_big_values(self):
        for name in sorted(OVERFLOW):
            payload = INT_CASES[name].encode('ascii')
            expected = cpython(self.tmp.name, INTS, payload)
            with self.subTest(case=name):
                got = run(self.exe['ints', 'exact'], payload)
                self.assertEqual((got[0], got[1]), (0, expected[1]),
                                 '%s exact: %r' % (name, got[2][-400:]))

    def test_invalid_utf8_stops_with_unicode_decode_error(self):
        # CPython's stdin decodes with errors='surrogateescape' and keeps going with lone
        # surrogates; a str here cannot hold them, so this is the documented stop (C?-diffs3-3),
        # not an equality case: exit 1, nothing printed, CPython's strict-mode message.
        for mode in ('default', 'force'):
            with self.subTest(mode=mode):
                got = run(self.exe['split', mode], INVALID_UTF8)
                self.assertEqual(got[0], 1)
                self.assertEqual(got[1], b'')
                self.assertIn(b'UnicodeDecodeError', got[2])

    def test_eof_inside_the_loop_stops_with_eof_error(self):
        expected = cpython(self.tmp.name, SPLIT, EOF_IN_LOOP)
        self.assertEqual(expected[0], 1)
        self.assertEqual(expected[1], b'3|a|c\n')
        for mode in ('default', 'force'):
            with self.subTest(mode=mode):
                got = run(self.exe['split', mode], EOF_IN_LOOP)
                self.assertEqual(got[0], 1)
                self.assertEqual(got[1], expected[1])
                self.assertIn(b'EOFError', got[2])


if __name__ == '__main__':
    unittest.main()
