"""Python-syntax reach, s4: slice/call unpacking, per-branch kind splits and ASCII/latin-1 decode.

U1  `a, b, c = xs[1:]` (and `xs[:2]`, `xs[-2:]`, `xs[1:-1]`) unpacks an int, float, str or bytes
    list with CPython's clamping and its catchable ValueError when the length disagrees.
U2  `a, b, c = helper()` unpacks a fixed-arity numeric tuple return through the existing
    `_return_tuple` ABI, with the same run-time arity check.
U3  A local bound to different kinds in two branches of one if/elif chain, and never read after
    it, is split into one local per branch; a read after the chain still refuses.
U4  `bytes.decode("ascii")` succeeds below 0x80, raises the catchable UnicodeDecodeError above
    it, and the uncaught path prints CPython's message.
U5  `bytes.decode("latin-1")` maps every byte to U+0000..U+00FF (two UTF-8 bytes from 0x80 up).
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


SLICE_UNPACK = '''def main():
    parts = [10, 20, 30, 40]
    a, b, c = parts[1:]
    print(a, b, c)
    x, y = parts[-2:]
    print(x, y)
    p, q = parts[1:3]
    print(p, q)

    fs = [1.5, 2.5, 3.5]
    u, v, w = fs[:]
    print(u, v, w)

    words = "ab,cd,ef".split(",")
    m, n = words[1:]
    print(m, n)

    raw = b"V|Paris|100".split(b"|")
    code, name, cap = raw[0:]
    print(code.decode("ascii"), name.decode("ascii"), cap.decode("ascii"))


main()
'''

SLICE_EMPTY = '''def main():
    empty = []
    try:
        a, b = empty[0:]
        print("no")
    except ValueError:
        print("short")
    long = [1, 2, 3]
    try:
        a, b = long[0:]
        print("no")
    except ValueError:
        print("long")
    clamped = [7, 8]
    a, b = clamped[0:9]
    print(a, b)
    a, b = clamped[-9:9]
    print(a, b)


main()
'''

CALL_UNPACK = '''def triple(n: int):
    return n, n + 1, n + 2

def scaled(n: float):
    return n * 1.5, n * 2.5

def main():
    a, b, c = triple(5)
    print(a, b, c)
    x, y = scaled(2.0)
    print(x, y)
    q, r, s = triple(2)
    print(q, r, s)


main()
'''

KIND_SPLIT = '''def main():
    for i in range(3):
        if i == 0:
            cents = b"123"
            print(cents.decode("ascii"))
        elif i == 1:
            cents = 45
            print(cents + 1)
        else:
            cents = "s"
            print(cents)


main()
'''

KIND_READ_AFTER = '''def main():
    if 1 == 0:
        x = b"aa"
    else:
        x = 3
    print(x)


main()
'''

KIND_LOOP = '''def main():
    total = 0
    for word in ["1", "2", "3"]:
        total = total + int(word)
        print(total)
    for word in [10, 20]:
        print(word + total)


main()
'''

DECODE_ASCII = '''def main():
    b = b"hello"
    s = b.decode("ascii")
    print(s)
    print(len(s))

    vals = [b"", b"abc", b"\\x7f", b"\\x80", b"a\\xffb"]
    i = 0
    while i < len(vals):
        try:
            print(vals[i].decode("ascii"))
        except UnicodeDecodeError:
            print("bad")
        i += 1


main()
'''

DECODE_ASCII_UNCAUGHT = '''def main():
    print("before")
    s = b"\\xff".decode("ascii")
    print(s)


main()
'''

DECODE_ASCII_CAUGHT_TEXT = '''def main():
    try:
        b"\\xff".decode("ascii")
    except ValueError as e:
        print("valueerror", str(e))
    try:
        b"ab\\x80cd".decode("ascii")
    except UnicodeDecodeError as e:
        print("unicode", str(e))


main()
'''

DECODE_ASCII_CAUGHT_EXPECTED = (
    "valueerror 'ascii' codec can't decode byte 0xff in position 0: ordinal not in range(128)\n"
    "unicode 'ascii' codec can't decode byte 0x80 in position 2: ordinal not in range(128)\n"
)

def _all_bytes_literal():
    return ''.join('\\x%02x' % value for value in range(256))


DECODE_LATIN1 = '''def main():
    raw = b"''' + _all_bytes_literal() + '''"
    s = raw.decode("latin-1")
    print(len(s))
    print(s[0], s[127], s[128], s[255])
    print(len(b"\\xc3\\xa9".decode("latin1")))
    print(b"\\xc3\\xa9".decode("iso-8859-1") == b"\\xc3\\xa9".decode("latin_1"))


main()
'''


def build_source(tmp, name, source):
    exe = Path(tmp) / name
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '--strict', '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def build_probe(tmp, name, source, unified):
    exe = Path(tmp) / (name + ('_unified' if unified else '_default'))
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    env.pop('AIL_NO_GENERAL', None)
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def run(exe):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class PyreachUnpack(unittest.TestCase):
    def _typed(self, name, text, expected):
        with tempfile.TemporaryDirectory(prefix='ail-s4-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            reference = subprocess.run([sys.executable, str(source)], capture_output=True,
                                       text=True, timeout=120)
            self.assertEqual(reference.stdout, expected, name)
            result, exe = build_source(tmp, name, source)
            self.assertEqual(result.returncode, 0, (name, result.stderr[-3000:]))
            got = run(exe)
            self.assertEqual(got.returncode, reference.returncode, name)
            self.assertEqual(got.stdout, expected, name)

    def _both(self, name, text, expected):
        with tempfile.TemporaryDirectory(prefix='ail-s4-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            for unified in (False, True):
                result, exe = build_probe(tmp, name, source, unified)
                self.assertEqual(result.returncode, 0, (name, unified, result.stderr[-3000:]))
                got = run(exe)
                self.assertEqual(got.stdout, expected, (name, unified))

    def test_slice_unpack(self):
        self._typed('slice_unpack', SLICE_UNPACK,
                    '20 30 40\n30 40\n20 30\n1.5 2.5 3.5\ncd ef\nV Paris 100\n')

    def test_slice_unpack_clamps_and_checks_length(self):
        self._typed('slice_empty', SLICE_EMPTY, 'short\nlong\n7 8\n7 8\n')

    def test_call_tuple_unpack(self):
        self._typed('call_unpack', CALL_UNPACK, '5 6 7\n3.0 5.0\n2 3 4\n')

    def test_if_branch_kind_split(self):
        self._typed('kind_split', KIND_SPLIT, '123\n46\ns\n')

    def test_kind_split_refuses_read_after_chain(self):
        with tempfile.TemporaryDirectory(prefix='ail-s4-') as tmp:
            source = Path(tmp) / 'kind_after.py'
            source.write_text(KIND_READ_AFTER, encoding='utf8')
            result, exe = build_source(tmp, 'kind_after', source)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('being assigned', result.stderr)

    def test_loop_kind_split_still_works(self):
        self._typed('kind_loop', KIND_LOOP, '1\n3\n6\n16\n26\n')

    def test_ascii_decode(self):
        self._typed('decode_ascii', DECODE_ASCII,
                    'hello\n5\n\nabc\n\x7f\nbad\nbad\n')

    def test_ascii_decode_uncaught_message(self):
        with tempfile.TemporaryDirectory(prefix='ail-s4-') as tmp:
            source = Path(tmp) / 'decode_uncaught.py'
            source.write_text(DECODE_ASCII_UNCAUGHT, encoding='utf8')
            reference = subprocess.run([sys.executable, str(source)], capture_output=True,
                                       text=True, timeout=120)
            result, exe = build_source(tmp, 'decode_uncaught', source)
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            got = run(exe)
            self.assertEqual(got.returncode, reference.returncode)
            self.assertEqual(got.stdout, 'before\n')
            self.assertIn("can't decode byte 0xff", got.stderr)

    def test_ascii_decode_caught_message(self):
        self._typed('decode_caught', DECODE_ASCII_CAUGHT_TEXT, DECODE_ASCII_CAUGHT_EXPECTED)
        self._both('decode_caught', DECODE_ASCII_CAUGHT_TEXT, DECODE_ASCII_CAUGHT_EXPECTED)

    def test_latin1_decode_covers_all_bytes(self):
        self._typed('decode_latin1', DECODE_LATIN1, '256\n\x00 \x7f \x80 \xff\n2\nTrue\n')

    def test_decode_probes_match_both_builds(self):
        self._both('both_ascii', DECODE_ASCII,
                   'hello\n5\n\nabc\n\x7f\nbad\nbad\n')
        self._both('both_latin1', DECODE_LATIN1, '256\n\x00 \x7f \x80 \xff\n2\nTrue\n')


if __name__ == '__main__':
    unittest.main()
