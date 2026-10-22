"""Bytes / bytearray silent differences found by the fuzz12 probes, against CPython 3.12.

Each program is built twice (default build and AIL_UNIFIED_FORCE=1) and must print what CPython
prints with the same exit status.

1. `repr()`/`str()` of a bytearray whose value holds only single quotes: CPython keeps the
   double-quoted inner bytes repr but still escapes the quote (`bytearray(b"\\'")`); AIL printed
   `bytearray(b"'")`. The bytes repr is unchanged (`b"'"`).
2. `bytes.split(None, maxsplit)` / `rsplit(None, maxsplit)` when the limit is reached: CPython
   keeps the whitespace on the unprocessed side of the remainder (`b"  a b  ".split(None, 0)`
   is `[b'a b  ']`, `rsplit` gives `[b'  a b']`); AIL stripped both ends.
3. `%r` in a bytes / bytearray format: CPython reprs the bytes-like object the argument still is
   (`b"%r" % b"ab"` is `b"b'ab'"`); AIL had unwrapped the argument to its bare bytes and printed
   `b"'ab'"`. `%s` / `%b` still unwrap, and a `*` width or precision keeps its own int argument.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')
MODES = ({}, {'AIL_UNIFIED_FORCE': '1'})

REPR = r'''
def show(x: bytearray) -> None:
    print(repr(x), str(x), repr(bytes(x)))


class B:
    def __init__(self, a: bytearray) -> None:
        self.a = a


def main() -> None:
    vals = [bytearray(b"'"), bytearray(b'"'), bytearray(b"'\x00"), bytearray(b"'\\\""),
            bytearray(b"\\\\'"), bytearray(b"a'b\"c"), bytearray(bytearray(b"\t\n\r\x7f\x80\xff")),
            bytearray(b""), bytearray(b"abc"), bytearray(b"\\")]
    for x in vals:
        show(x)
    d = {}
    d[b"k"] = bytearray(b"'")
    print(repr(d[b"k"]), repr(d[b"k"] + b"x"))
    b = B(bytearray(b"'\x01"))
    print(repr(b.a), str(b.a), repr(bytes(b.a)))


main()
'''

SPLIT = r'''
def sp(t: bytes, n: int) -> list[bytes]:
    return t.split(None, n)


def rsp(t: bytes, n: int) -> list[bytes]:
    return t.rsplit(None, n)


class H:
    def __init__(self, t: bytes) -> None:
        self.t = t


def main() -> None:
    vals = [b"", b" ", b"  ", b"\t\n", b" a", b"a ", b"  a  b  ", b"a b c", b"\ta\r\n b\t", b" a "]
    for t in vals:
        for n in (-2, -1, 0, 1, 2, 3):
            print(sp(t, n), rsp(t, n))
    h = H(b"  x  y  ")
    print(h.t.split(None, 0), h.t.rsplit(None, 0), h.t.split(None, 1), h.t.rsplit(None, 1))
    parts = [b"  a b  ", b"c d  "]
    print(parts[0].split(None, 0), parts[1].rsplit(None, 0))
    table = {b"k": b"  p q  "}
    print(table[b"k"].split(None, 0), table[b"k"].rsplit(None, 0))


main()
'''

PERCENT = r'''
class C:
    def __init__(self) -> None:
        self.v = b"ab"
        self.q = bytearray(b"cd")


def main() -> None:
    x = b"ab"
    y = bytearray(b"cd")
    print(b"%r" % (x,), b"%r" % (y,))
    print(b"%s %r" % (x, y), b"%r %s" % (y, x))
    print(b"%r" % (b"'",), b"%r" % (b'"',), b"%r" % (b"'\x00",))
    print(b"%r" % (b"",), b"%r" % (b"abc",))
    print(b"%%r %r" % (x,), b"%d %r" % (3, x))
    print(b"%*r" % (5, x), b"%-5r|" % (x,), b"%.*r" % (3, x))
    print(b"%r" % (b"x".replace(b"x", b"yz"),))
    xs = [b"ab", bytearray(b"cd")]
    print(b"%r %r" % (xs[0], xs[1]))
    d = {b"k": b"ab", b"q": bytearray(b"cd")}
    print(b"%r %r" % (d[b"k"], d[b"q"]))
    c = C()
    print(b"%r %r" % (c.v, c.q))
    print(b"%s" % (x,), b"%s" % (y,))
    print(b"%r" % (b"ab" + b"c",), b"%r" % (bytearray(b"ab") + b"c",))
main()
'''


class Fuzz12(unittest.TestCase):
    def same_as_cpython(self, text, name):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz12-') as directory:
            directory = Path(directory)
            source = directory / (name + '.py')
            source.write_text(text, encoding='utf-8')
            expected = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120)
            for mode, extra in enumerate(MODES):
                exe = directory / ('%s_%d' % (name, mode))
                env = dict(os.environ, AIL_NO_CACHE='1', **extra)
                built = subprocess.run([sys.executable, '-B', CLI, 'compile', str(source),
                                        '--syntax', 'python', '-o', str(exe)],
                                       cwd=directory, capture_output=True, text=True, timeout=900, env=env)
                self.assertEqual(built.returncode, 0, 'mode %d: %s' % (mode, built.stdout + built.stderr))
                ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                 'mode %d: %s' % (mode, ran.stderr.decode(errors='replace')))

    def test_bytearray_repr_escapes_a_single_quote(self):
        self.same_as_cpython(REPR, 'repr')

    def test_whitespace_split_keeps_the_remainder_whitespace(self):
        self.same_as_cpython(SPLIT, 'split')

    def test_percent_r_keeps_the_bytes_repr_prefix(self):
        self.same_as_cpython(PERCENT, 'percent')


if __name__ == '__main__':
    unittest.main()
