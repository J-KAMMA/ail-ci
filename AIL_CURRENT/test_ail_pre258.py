"""Bytes/bytearray membership with an object that has ``__index__`` (job pre258).

The reviewer of job pre183 recorded that ``Idx(97) in b"abc"`` still raised the bytes-like
TypeError on both builds, while CPython converts the left operand through ``__index__``: 97
selects the byte, -1 and 256 raise ``ValueError: byte must be in range(0, 256)``.  When the
conversion fails (a non-int result or an exception), CPython clears the error and falls back to
the buffer path, so a plain object gets the bytes-like TypeError naming its own type.  The
containment helper now tries the index conversion first and keeps the bytes-like path as the
fallback.  The program checks bytes and bytearray receivers, the value through an argument, a
list item, a dict value and an attribute, the ``__contains__`` method, bool results and the
fallback cases.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INDEX_MEMBERS = r'''class Idx:
    def __init__(self, v) -> None:
        self.v = v

    def __index__(self) -> int:
        return self.v


class Box:
    pass


def probe(tag: str, f) -> None:
    try:
        print(tag, f())
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def via_arg(tag: str, x, recv) -> None:
    try:
        print(tag, x in recv)
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def main() -> None:
    b: bytes = b"abc"
    ba: bytearray = bytearray(b"abc")
    box = Box()
    box.i = Idx(97)
    xs = [Idx(5)]
    d = {"i": Idx(256)}
    for recv_name, recv in (("b", b), ("ba", ba)):
        for v in (0, 97, 255, 256, -1):
            probe(recv_name + "-v" + str(v), lambda v=v, recv=recv: Idx(v) in recv)
        via_arg(recv_name + "-arg", Idx(97), recv)
        probe(recv_name + "-list", lambda recv=recv: xs[0] in recv)
        probe(recv_name + "-dict", lambda recv=recv: d["i"] in recv)
        probe(recv_name + "-attr", lambda recv=recv: box.i in recv)
        probe(recv_name + "-method", lambda recv=recv: recv.__contains__(Idx(99)))
    print("done")


main()
'''

INDEX_FALLBACKS = r'''class Bad:
    def __index__(self):
        return "x"


class Raise:
    def __index__(self):
        raise RuntimeError("boom")


class BoolIdx:
    def __index__(self):
        return True


class Plain:
    pass


def probe(tag: str, f) -> None:
    try:
        print(tag, f())
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def main() -> None:
    b: bytes = b"abc"
    ba: bytearray = bytearray(b"abc")
    for recv_name, recv in (("b", b), ("ba", ba)):
        for tag, obj in (("bad", Bad()), ("raise", Raise()), ("bool", BoolIdx()), ("plain", Plain())):
            probe(recv_name + "-" + tag, lambda obj=obj, recv=recv: obj in recv)
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


class Pre258Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre258-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_index_operand_selects_byte(self):
        self.check('index_members', INDEX_MEMBERS)

    def test_failed_index_falls_back_to_bytes_like(self):
        self.check('index_fallbacks', INDEX_FALLBACKS)


if __name__ == '__main__':
    unittest.main()
