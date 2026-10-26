"""Differential fuzz round 58: invalid int()/float() messages keep non-ASCII repr text.

Found with small programs compared against CPython on both builds:

`int(s, base)` on the general path built the ValueError text by narrowing each UTF-16
unit of `repr(s)` to one `char`.  A non-ASCII code point whose low byte happened to be
printable was silently replaced by that byte: `int("\u2469", 10)` reported
"invalid literal for int() with base 10: 'i'" where CPython reports the circled digit,
and a surrogate pair could be split.  The same construction was used by the general
builtin-value path and by the `float(s)` message.  The messages are now built as
str + repr, so both builds agree with CPython and the whole repr is kept.

The plain `int(s)` path and the typed path already matched; these programs keep them
compared too.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INVALID_INT_REPR = r'''def main() -> None:
    cases = ["\u2469", "\u2460", "\u2473", "\u00b2", "\u00b9", "\u0661x", "\uff11x",
             "x\u2469y", "'\u2469\"", "\u2469" * 120]
    for s in cases:
        for b in [0, 2, 8, 10, 16, 36]:
            try:
                print(repr(s), b, int(s, b))
            except ValueError as e:
                print(repr(s), b, "ValueError", e)
    print("done")


main()
'''

INVALID_INT_SOURCES = r'''class Box:
    def __init__(self, v):
        self.v = v


def show(s: str, b: int) -> None:
    try:
        print(int(s, b))
    except ValueError as e:
        print("VE", e)


def main() -> None:
    bad = "\u2469"
    box = Box("\u2469")
    xs = ["\u2469", "\u00b2"]
    d = {"bad": "\u2469", "sup": "\u00b2"}
    show(bad, 10)
    show(xs[0], 10)
    show(xs[1], 10)
    show(box.v, 10)
    show(d["bad"], 10)
    show(d["sup"], 16)
    try:
        print(int("\u2469"))
    except ValueError as e:
        print("no-base", e)
    print("done")


main()
'''

INVALID_FLOAT_REPR = r'''def show(s: str) -> None:
    try:
        print(float(s))
    except ValueError as e:
        print("VE", e)


def main() -> None:
    for s in ["x", "\u2469", "\u00b2", "\u0661x", "1.2.3", "x" * 300, "1.2x\u2469"]:
        show(s)
    print("done")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


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
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz58Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz58-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_invalid_int_literal_keeps_non_ascii_repr(self):
        self.check('invalid_int_repr', INVALID_INT_REPR)

    def test_invalid_int_literal_reached_from_sources(self):
        self.check('invalid_int_sources', INVALID_INT_SOURCES)

    def test_invalid_float_literal_keeps_non_ascii_repr(self):
        self.check('invalid_float_repr', INVALID_FLOAT_REPR)


if __name__ == '__main__':
    unittest.main()
