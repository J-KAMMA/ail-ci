"""Pre-existing CPython difference: bytes/bytearray membership with a non-index object.

`x in b` and `b.__contains__(x)` accept an int in 0..255 or a bytes-like object.
For any other value CPython raises:

    TypeError: a bytes-like object is required, not 'str'

Both builds used the shared substring helper, whose CPython wording belongs to
find/index/count/replace ("argument should be integer or bytes-like object"), so
a str, float, None, list or user-class item printed the wrong message.  Membership
now has its own conversion; `find` and the other search methods keep their message
(non-index start/stop bounds are a separate, still open difference).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MEMBERSHIP = r'''class Marker:
    pass

class Box:
    pass

def call_contains(b, x):
    return b.__contains__(x)

def show(tag, f):
    try:
        print(tag, f())
    except Exception as e:
        print(tag, type(e).__name__, str(e))

def each(tag, b, xs):
    for x in xs:
        try:
            print(tag, repr(x), b.__contains__(x))
        except Exception as e:
            print(tag, repr(x), type(e).__name__, str(e))

def main():
    b = b"abc"
    ba = bytearray(b"abc")
    empty = b""
    show("str", lambda: b.__contains__("a"))
    show("in-str", lambda: "a" in b)
    show("float", lambda: b.__contains__(1.0))
    show("none", lambda: b.__contains__(None))
    show("list", lambda: b.__contains__(["a"]))
    show("marker", lambda: b.__contains__(Marker()))
    show("ba-str", lambda: ba.__contains__("a"))
    show("ba-in-str", lambda: "a" in ba)
    show("arg-str", lambda: call_contains(b, "a"))
    show("empty-str", lambda: empty.__contains__("a"))
    xs = ["a"]
    show("list-item", lambda: b.__contains__(xs[0]))
    box = Box()
    box.v = "a"
    show("attr", lambda: b.__contains__(box.v))
    d = {"k": "a"}
    show("dict", lambda: b.__contains__(d["k"]))
    each("bytes", b, [97, 0, 255, 256, -1, True, False, b"a", b"", b"bc", bytearray(b"a"), bytearray(b"")])
    each("bytearray", ba, [97, 0, 255, 256, -1, True, False, b"a", b"", b"bc", bytearray(b"a"), bytearray(b"")])
    each("empty", empty, [97, b"", b"a"])

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


class Pre114Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre114-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_bytes_membership_type_error(self):
        self.check('bytes_membership', MEMBERSHIP)


if __name__ == '__main__':
    unittest.main()
