"""Pre-212: `int(bytes_or_bytearray, base=...)` follows CPython.

The review of job pre192 recorded a pre-existing difference: a keyword `base=` with a
bytes-like first argument raised `TypeError: int() can't convert non-string with explicit
base` on both builds, where CPython parses the bytes (`int(b"10", base=10) == 10`) and uses
the bytes repr in the invalid-literal message.  The general-path rewrite that routes
`int(x, base)` through `_ail_int2` only matched the positional form, so the keyword form
never reached the bytes-aware parser.  The rewrite now also covers `int(x, base=...)`; the
bytes path validates the base before parsing (CPython checks the base range first), and the
boxed runtime validates the base range before the argument type check.

The cases below cover direct calls and values reaching the conversion through an argument,
a list item, an attribute, a dict value and an alias, bases supplied the same ways, both
bytes forms, empty/signed/whitespace/underscore/prefix/non-ASCII/quote/control/long inputs,
the repr cut, invalid base types and ranges, and the positional and str forms, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''class Box:
    def __init__(self, v, b):
        self.v = v
        self.b = b


def show(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def conv(v, base):
    return int(v, base=base)


def conv2(v):
    return int(v, base=10)


def note(label, value):
    print("eval", label)
    return value


def main():
    bad = bytearray(b"x")
    alias = bad
    good = bytearray(b"0xff")
    empty = bytearray()
    packed = bytearray([0, 1, 9, 10, 13, 32, 39, 34, 92, 127, 128, 255])
    xs = [b"10", bytearray(b"10"), b"x", bytearray(b"x"), empty, packed]
    d = {"bytes": b"0xff", "ba": good, "base": 16, "bad": bad}
    box = Box(bytearray(b"101"), 2)
    bases = [0, 2, 8, 10, 16, 36]
    for b in bases:
        show("direct-bytes-" + str(b), lambda b=b: int(b"10", base=b))
        show("direct-ba-" + str(b), lambda b=b: int(bytearray(b"10"), base=b))
        show("arg-bytes-" + str(b), lambda b=b: conv(b"10", b))
        show("arg-ba-" + str(b), lambda b=b: conv(bytearray(b"10"), b))
        show("list-bytes-" + str(b), lambda b=b: int(xs[0], base=b))
        show("list-ba-" + str(b), lambda b=b: int(xs[1], base=b))
        show("dict-bytes-" + str(b), lambda b=b: int(d["bytes"], base=b))
        show("dict-ba-" + str(b), lambda b=b: int(d["ba"], base=b))
        show("attr-ba-" + str(b), lambda b=b: int(box.v, base=b))
        show("alias-ba-" + str(b), lambda b=b: int(alias, base=b))
        show("basearg-" + str(b), lambda b=b: int(b"10", base=xs[0] and b))
        show("baselist-" + str(b), lambda b=b: int(b"10", base=[b, 2][0]))
        show("basedict-" + str(b), lambda b=b: int(b"10", base={"b": b}["b"]))
        show("baseattr-" + str(b), lambda b=b: int(b"10", base=box.b if b == 2 else b))
        show("bad-bytes-" + str(b), lambda b=b: int(b"x", base=b))
        show("bad-ba-" + str(b), lambda b=b: int(bytearray(b"x"), base=b))
        show("long-" + str(b), lambda b=b: int(b"!" * 201, base=b))
    show("bytes-good", lambda: int(b"10", base=10))
    show("ba-good", lambda: int(bytearray(b"10"), base=10))
    show("good-arg", lambda: conv2(b"10"))
    show("n-bytes-bad", lambda: int(b"x", base=10))
    show("n-ba-bad", lambda: int(bytearray(b"x"), base=10))
    show("n-packed", lambda: int(packed, base=10))
    show("n-empty", lambda: int(empty, base=10))
    show("neg", lambda: int(b"-12", base=10))
    show("ws", lambda: int(bytearray(b"  12  "), base=10))
    show("under", lambda: int(b"1_0", base=2))
    show("prefix", lambda: int(bytearray(b"0b11"), base=0))
    show("prefix16", lambda: int(b"0xff", base=16))
    show("nonascii", lambda: int(bytearray(b"12\xff"), base=10))
    show("quote", lambda: int(b"a'b", base=10))
    show("dquote", lambda: int(bytearray(b'a"b'), base=10))
    show("control", lambda: int(b"1\x1c2", base=10))
    show("esc", lambda: int(bytearray(b"'\\\n\t\r"), base=10))
    for n in (198, 199, 200, 201, 202, 300):
        show("long" + str(n), lambda n=n: int(b"x" * n, base=10))
        show("longba" + str(n), lambda n=n: int(bytearray(b"x" * n), base=10))
        show("longmix" + str(n), lambda n=n: int(b"1" * 100 + b"x" * n + b"2" * 100, base=10))
    for b in (-1, 1, 37, 100):
        show("range-pos-" + str(b), lambda b=b: int(b"10", b))
        show("range-kw-" + str(b), lambda b=b: int(b"10", base=b))
        show("range-bad-" + str(b), lambda b=b: int(b"x", base=b))
        show("range-str-" + str(b), lambda b=b: int("10", base=b))
    show("base-none", lambda: int(b"10", base=None))
    show("base-str", lambda: int(b"10", base="10"))
    show("base-float", lambda: int(b"10", base=10.0))
    show("x-int-badbase", lambda: int(10, base=1))
    show("x-float-badbase", lambda: int(1.5, base=1))
    show("x-none-badbase", lambda: int(None, base=1))
    show("x-int", lambda: int(10, base=10))
    show("x-float", lambda: int(1.5, base=10))
    show("x-none", lambda: int(None, base=10))
    show("str-kw", lambda: int("10", base=10))
    show("str-bad-kw", lambda: int("x", base=10))
    show("order", lambda: int(note("x", b"10"), base=note("base", 10)))
    print("done")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre212Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre212-') as directory:
            want = _cpython(directory, slug, text)
            for general in (True, False):
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                          text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, err))

    def test_int_bytes_keyword_base(self):
        self.check('int_bytes_kwbase', PROGRAM)


if __name__ == '__main__':
    unittest.main()
