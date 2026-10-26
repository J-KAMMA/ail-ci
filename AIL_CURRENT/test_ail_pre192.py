"""Pre-192: the `int(bytearray, base)` ValueError names a bytes repr, like CPython.

The review of job memsafe2 recorded a pre-existing difference: `int(bytearray(b"x"), 10)`
printed `...: bytearray(b'x')` where CPython prints `...: b'x'`.  CPython converts the
bytearray for the parse and formats the message with the bytes repr, while the prelude's
`_ail_int2` (and `bytearray.__int__`) used `repr()` of the bytearray.  The message now uses
the same bytes repr for both arguments, including CPython's 200-character `%.200R` cut.

The cases below are direct calls and values reaching the conversion through an argument, a
list item, an attribute, a dict value and an alias, plus empty, packed, non-ASCII, quoted,
escaped, long, valid and `bytes` inputs, on both builds.
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


def conv(v, b):
    return int(v, b)


def conv1(v):
    return int(v)


def main():
    bad = bytearray(b"x")
    alias = bad
    good = bytearray(b"0xff")
    empty = bytearray()
    packed = bytearray([0, 1, 9, 10, 13, 32, 39, 34, 92, 127, 128, 255])
    xs = [bad, empty, packed, good]
    d = {"bad": bad, "good": good, "b": 16}
    box = Box(bad, 10)
    for b in (0, 2, 8, 10, 16, 36):
        show("direct-" + str(b), lambda b=b: int(bytearray(b"x"), b))
        show("conv-" + str(b), lambda b=b: conv(bytearray(b"x"), b))
        show("list-" + str(b), lambda b=b: int(xs[0], b))
        show("attr-" + str(b), lambda b=b: int(box.v, b))
        show("dict-" + str(b), lambda b=b: int(d["bad"], b))
        show("alias-" + str(b), lambda b=b: int(alias, b))
        show("packed-" + str(b), lambda b=b: int(packed, b))
        show("empty-" + str(b), lambda b=b: int(empty, b))
        show("good-" + str(b), lambda b=b: int(good, b))
        show("bytes-" + str(b), lambda b=b: int(b"x", b))
        show("basearg-" + str(b), lambda b=b: int(bytearray(b"x"), xs[0] and b))
    show("n-direct", lambda: int(bytearray(b"x")))
    show("n-conv", lambda: conv1(bytearray(b"x")))
    show("n-list", lambda: int(xs[0]))
    show("n-attr", lambda: int(box.v))
    show("n-dict", lambda: int(d["bad"]))
    show("n-alias", lambda: int(alias))
    show("n-packed", lambda: int(packed))
    show("n-good", lambda: int(good))
    show("n-bytes", lambda: int(b"x"))
    show("bytes-good", lambda: int(b"10"))
    show("neg", lambda: int(bytearray(b"-12"), 10))
    show("ws", lambda: int(bytearray(b"  12  "), 10))
    show("under", lambda: int(bytearray(b"1_0"), 2))
    show("prefix", lambda: int(bytearray(b"0b11"), 0))
    show("nonascii", lambda: int(bytearray(b"12\xff"), 10))
    show("quote", lambda: int(bytearray(b"a'b"), 10))
    show("dquote", lambda: int(bytearray(b'a"b'), 10))
    show("esc", lambda: int(bytearray(b"'\\\n\t\r"), 10))
    show("float-ba", lambda: float(bytearray(b"x")))
    for n in (199, 200, 201, 300):
        v = bytearray(b"x" * n)
        show("long" + str(n), lambda v=v: int(v, 10))
        show("nlong" + str(n), lambda v=v: int(v))
        show("blong" + str(n), lambda n=n: int(b"x" * n, 10))
    show("long-mixed", lambda: int(bytearray(b"1" * 100 + b"x" + b"2" * 150), 10))
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


class Pre192Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre192-') as directory:
            want = _cpython(directory, slug, text)
            for general in (True, False):
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                          text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, err))

    def test_bytearray_int_message(self):
        self.check('bytearray_int', PROGRAM)


if __name__ == '__main__':
    unittest.main()
