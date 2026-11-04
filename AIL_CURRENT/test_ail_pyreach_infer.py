"""Python-syntax reach, s3: local kind inference for plain sources.

I1  `with open(path, 'rb') as f: data = f.read()` (also inside `try:`) gives `data` bytes, so
    `.split(b'\\n')` is a list of bytes, each element is bytes, and a bytes regex accepts it.
    Without an explicit mode (and with `'r'`) the same shape is a str.
I2  An unannotated helper parameter takes its kind from the call sites: `fail(1, 'header')`,
    `fail(ln, 'syntax')` give `n: int, cat: str` when every site agrees per position.
I3  A helper that returns a `"%..." % v` string, possibly after `s = s[1:]` reassignments, has
    return kind str, so `"sum " + fmt(total)` adopts it as an owned str.
I4  `out = []` that is later only appended str values (a `%` format with a tuple right side and
    `"..." + str_helper(x)`) is a list of str.
I5  `list(map(int, X.split()))` and walking a list produced by `bytes.split()` are int / bytes.
I6  A name rebound in a loop body (`sl = st_lines[s]` before, `sl = st_lines[u]` inside) does not
    become the "possibly unbound" ternary when both bindings precede every read on all paths.

Every inferred kind is still checked at each use: a use that disagrees is a refusal by name.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None


OPEN_RB = '''import sys
import re

R = re.compile(rb'[A-Z]{3}')


def main():
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except Exception:
        return 2
    lines = data.split(b'\\n')
    n = 0
    for ln in lines:
        if R.fullmatch(ln):
            n += 1
        if len(ln) > 0:
            n += ln[0] % 7
    sys.stdout.write("%d %d\\n" % (n, len(data)))
    return 0


sys.exit(main())
'''

OPEN_TEXT = '''import sys
import re

R = re.compile(r'[A-Z]{3}')


def main():
    with open(sys.argv[1]) as f:
        data = f.read()
    lines = data.split('\\n')
    n = 0
    for ln in lines:
        if R.fullmatch(ln):
            n += 1
        if len(ln) > 0:
            n += ord(ln[0]) % 7
    sys.stdout.write("%d %d\\n" % (n, len(data)))
    return 0


sys.exit(main())
'''

PARAMS_AGREE = '''import sys

CODES = {'header': 2, 'syntax': 3, 'value': 4}


def fail(n, cat):
    sys.stdout.write("line %d: %s\\n" % (n, cat))
    sys.stdout.flush()
    return CODES[cat]


def main():
    if sys.argv[1] == 'a':
        return fail(1, 'header')
    if sys.argv[1] == 'b':
        return fail(10, 'syntax')
    return fail(100, 'value')


sys.exit(main())
'''

PARAMS_MIXED = '''import sys


def show(x, y):
    sys.stdout.write("[%s %s]\\n" % (x, y))
    return 0


def main():
    show(7, 'a')
    show('text', 'b')
    return 0


sys.exit(main())
'''

FALLOFF_CONCAT = '''import sys


def maybe(flag):
    if flag:
        return "yes"


def main():
    x = "a" + maybe(0)
    sys.stdout.write(x + "\\n")
    return 0


sys.exit(main())
'''

FALLOFF_LEN = '''import sys


def maybe(flag):
    if flag:
        return "yes"


def main():
    n = len(maybe(0))
    sys.stdout.write("%d\\n" % n)
    return 0


sys.exit(main())
'''

FMT_HELPER = '''import sys


def fmt(v):
    s = "%.9f" % v
    if s.startswith("-") and s[1:2] == "0":
        s = s[1:]
    return s


def main():
    total = -0.0
    energy = 3.25
    out = "sum " + fmt(total)
    out = out + " energy " + fmt(energy)
    sys.stdout.write(out + "\\n")
    return 0


sys.exit(main())
'''

STR_LIST = '''import sys


def money(c):
    return "%d.%02d" % (c // 100, c % 100)


def main():
    out = []
    n = 3
    revenue = 12345
    out.append("venues %d events %d" % (5, n))
    out.append("revenue " + money(revenue))
    out.append("%s=%d" % ("total", revenue))
    sys.stdout.write("\\n".join(out) + "\\n")
    return 0


sys.exit(main())
'''

MAP_INT = '''import sys


def main():
    raw = sys.stdin.buffer.read().split()
    data = list(map(int, raw))
    total = 0
    for v in data:
        total += v
    sys.stdout.write("%d %d\\n" % (len(data), total))
    return 0


sys.exit(main())
'''

LOOP_REBIND = '''import sys


def main():
    st_lines = [[1, 2], [3], [4, 5, 6]]
    s = 0
    sl = st_lines[s]
    total = 0
    for u in range(len(st_lines)):
        sl = st_lines[u]
        for x in sl:
            total += x
    sys.stdout.write("%d %d\\n" % (total, len(sl)))
    return 0


sys.exit(main())
'''


def build_source(tmp, name, source, flags=()):
    exe = Path(tmp) / name
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '--strict', *flags, '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def build_probe(tmp, name, source, unified, flags=()):
    exe = Path(tmp) / (name + ('_unified' if unified else '_default'))
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    env.pop('AIL_NO_GENERAL', None)
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', *flags, '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def run(exe, args=(), stdin=None):
    return subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=120,
                          input=stdin)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class PyreachInfer(unittest.TestCase):
    def _fixture(self, tmp):
        path = Path(tmp) / 'fixture.txt'
        path.write_text('ABC\nDEFG\nXYZ\n', encoding='utf8')
        return str(path)

    def _typed(self, name, text, expected, args=(), stdin=None, fixture=False):
        with tempfile.TemporaryDirectory(prefix='ail-s3-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            run_args = (self._fixture(tmp),) if fixture else args
            reference = subprocess.run([sys.executable, str(source), *run_args],
                                       capture_output=True, text=True, timeout=120, input=stdin)
            self.assertEqual(reference.stdout, expected, name)
            result, exe = build_source(tmp, name, source)
            self.assertEqual(result.returncode, 0, (name, result.stderr[-3000:]))
            got = run(exe, run_args, stdin)
            self.assertEqual(got.returncode, reference.returncode, name)
            self.assertEqual(got.stdout, expected, name)
            for unified in (False, True):
                result, exe = build_probe(tmp, name, source, unified)
                self.assertEqual(result.returncode, 0, (name, unified, result.stderr[-3000:]))
                got = run(exe, run_args, stdin)
                self.assertEqual(got.returncode, reference.returncode, (name, unified))
                self.assertEqual(got.stdout, expected, (name, unified))

    def test_open_binary_read_split(self):
        self._typed('open_rb', OPEN_RB, '13 13\n', fixture=True)

    def test_open_text_read_split(self):
        self._typed('open_text', OPEN_TEXT, '13 13\n', fixture=True)

    def test_helper_params_from_agreeing_call_sites(self):
        self._typed('params_a', PARAMS_AGREE, 'line 1: header\n', args=('a',))
        self._typed('params_b', PARAMS_AGREE, 'line 10: syntax\n', args=('b',))
        self._typed('params_c', PARAMS_AGREE, 'line 100: value\n', args=('c',))

    def test_helper_params_mixed_call_sites(self):
        # Disagreeing call sites keep the by-name refusal under --strict (the task's own gate);
        # the general path still matches CPython for both arguments.
        with tempfile.TemporaryDirectory(prefix='ail-s3-') as tmp:
            source = Path(tmp) / 'mixed.py'
            source.write_text(PARAMS_MIXED, encoding='utf8')
            result, exe = build_source(tmp, 'mixed', source)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('passing str', result.stderr)
            for unified in (False, True):
                result, exe = build_probe(tmp, 'mixed', source, unified)
                self.assertEqual(result.returncode, 0, (unified, result.stderr[-3000:]))
                for arg in ('i', 's'):
                    reference = subprocess.run([sys.executable, str(source), arg],
                                               capture_output=True, text=True, timeout=120)
                    got = run(exe, (arg,))
                    self.assertEqual(got.returncode, reference.returncode, (unified, arg))
                    self.assertEqual(got.stdout, reference.stdout, (unified, arg))

    def test_str_helper_that_can_fall_off_end(self):
        # A helper with a str return on one path and an implicit None on another is Optional[str],
        # which the typed path does not have.  It must be refused by name under --strict, never
        # compiled as an owned str (CPython raises TypeError on the fall-through value); the
        # default and unified builds match CPython.
        for name, text in (('falloff_concat', FALLOFF_CONCAT), ('falloff_len', FALLOFF_LEN)):
            with tempfile.TemporaryDirectory(prefix='ail-s3-') as tmp:
                source = Path(tmp) / (name + '.py')
                source.write_text(text, encoding='utf8')
                reference = subprocess.run([sys.executable, str(source)], capture_output=True,
                                           text=True, timeout=120)
                self.assertEqual(reference.returncode, 1, name)
                self.assertEqual(reference.stdout, '', name)
                result, exe = build_source(tmp, name, source)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('can fall off the end', result.stderr, name)
                for unified in (False, True):
                    result, exe = build_probe(tmp, name, source, unified)
                    self.assertEqual(result.returncode, 0, (name, unified, result.stderr[-3000:]))
                    got = run(exe)
                    self.assertEqual(got.returncode, reference.returncode, (name, unified))
                    self.assertEqual(got.stdout, reference.stdout, (name, unified))

    def test_percent_format_helper_returns_str(self):
        self._typed('fmt_helper', FMT_HELPER, 'sum 0.000000000 energy 3.250000000\n')

    def test_str_list_from_percent_appends(self):
        self._typed('str_list', STR_LIST, 'venues 5 events 3\nrevenue 123.45\ntotal=12345\n')

    def test_map_int_over_bytes_split(self):
        self._typed('map_int', MAP_INT, '2 46\n', stdin='12 34\n')

    def test_map_int_beyond_int64(self):
        stdin = '12 99999999999999999999999\n'
        with tempfile.TemporaryDirectory(prefix='ail-s3-') as tmp:
            source = Path(tmp) / 'map_big.py'
            source.write_text(MAP_INT, encoding='utf8')
            reference = subprocess.run([sys.executable, str(source)], capture_output=True,
                                       text=True, timeout=120, input=stdin)
            self.assertEqual(reference.stdout, '2 100000000000000000000011\n')
            result, exe = build_probe(tmp, 'map_big', source, False)
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            got = run(exe, stdin=stdin)
            self.assertEqual(got.returncode, 1)
            self.assertIn('OverflowError', got.stderr)
            result, exe = build_probe(tmp, 'map_big_exact', source, False, ('--exact-int',))
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            got = run(exe, stdin=stdin)
            self.assertEqual(got.returncode, reference.returncode)
            self.assertEqual(got.stdout, reference.stdout)

    def test_loop_rebound_name(self):
        self._typed('loop_rebind', LOOP_REBIND, '21 3\n')


if __name__ == '__main__':
    unittest.main()
