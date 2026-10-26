"""Pre-180: the `int(s, base)` ValueError message against CPython.

Found as a pre-existing difference: an invalid literal containing a non-ASCII printable
character was reported one byte at a time, so `int("\\u2469", 10)` printed
`invalid literal for int() with base 10: 'i'` (the low byte of U+2469) where CPython prints
`'\\u2469'`.  The live general-path helper built its message by casting each UTF-16 unit of
`repr(s)` to `char`; it now composes the message from the repr string itself.  Both paths
also cut the repr after 200 characters, as CPython's "%.200R" does, so a long invalid
literal matches rather than printing the whole string.  Valid Unicode decimal digits keep
parsing as before.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")


MESSAGES = r'''def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main():
    vals = ["\u2469", "\u2460", "\u2160", "h\u00e9llo", "\u4f60\u597d", "\u00e9\u00e8\u00ea",
            "1\u2469", "1_\u2469", "z\u4f60", "'", '"', "a\\b", "a\nb", "a\tb", "\x00", ""]
    for s in vals:
        for b in [0, 2, 10, 16, 36]:
            show(repr(s) + " " + str(b), lambda s=s, b=b: int(s, b))
    long_bad = "\u2469" * 300
    show("long", lambda: int(long_bad, 10))
    show("long-mixed", lambda: int("\u4f60" * 120 + "x", 16))


main()
'''

ROUTES = r'''class Box:
    def __init__(self, s, b):
        self.s = s
        self.b = b


def conv(s, b):
    return int(s, b)


def main():
    bad = "\u2469"
    xs = [bad, 16]
    d = {"s": bad, "b": 16}
    box = Box(bad, 16)
    for label, s, b in [("attr", box.s, box.b), ("list", xs[0], xs[1]), ("dict", d["s"], d["b"])]:
        try:
            print(label, int(s, b))
        except ValueError as e:
            print("caught", label, str(e))
    try:
        print(conv(bad, 16))
    except ValueError as e:
        print("caught arg", str(e))
    try:
        print(int("0x\u2469", 16))
    except ValueError as e:
        print("caught prefix", str(e))
    print(int("\u0661\u0662\u0663", 10), int("\uff11\uff12\uff13", 10), int("\u0e51\u0e52", 10))
    print(int("\u0661\u0662", 0), int(" 42 ", 10), int("+1_0", 2), int("0o17", 0))


main()
'''

TYPED = r'''def conv(s: str, b: int) -> int:
    return int(s, b)


def main() -> None:
    vals = ["\u2469", "\u4f60\u597d", "1_\u2469", "\u2160"]
    for s in vals:
        try:
            print(conv(s, 16))
        except ValueError as e:
            print("caught", str(e))
    try:
        print(conv("\u2469" * 300, 10))
    except ValueError as e:
        print("long", len(str(e)), str(e)[-5:])
        print(str(e))


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


class Pre180Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre180-') as directory:
            want, rc = _cpython(directory, slug, text)
            for general in (True, False):
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (slug, general, err))

    def test_invalid_literal_messages(self):
        self.check('messages', MESSAGES)

    def test_through_arguments_and_containers(self):
        self.check('routes', ROUTES)

    def test_typed_path_literal_cap(self):
        self.check('typed', TYPED)


if __name__ == '__main__':
    unittest.main()
