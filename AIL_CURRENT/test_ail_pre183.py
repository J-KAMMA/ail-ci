"""Bytes/bytearray membership and startswith/endswith tuple members against CPython 3.12 (job pre183).

A bytes/bytearray `in` test with a non-integer, non-bytes left operand reported the
bytes-method message ("argument should be integer or bytes-like object") instead of
CPython's containment message ("a bytes-like object is required"). The receiver classes
now use a dedicated coercion that keeps the integer-byte path and names the left operand
through the bytes-like path.

A tuple passed to str.startswith/endswith may contain only str. A builtin function value
reaches the runtime as a generated FUNC object (the general path lowers `len` used as a
value to a small lambda), so the caught TypeError named it "function":

    "abc".startswith((len,))   printed "... not function"
    "abc".endswith((len,))     printed "... not function"

CPython prints "not builtin_function_or_method"; a user-defined function is still "not
function". The FUNC object now carries a builtin flag, and the error type name uses it.
The program keeps the literal tuple, a variable, an argument, a list item, a dict value
and an attribute, the scalar form, short-circuiting before the bad member, and the
invalid-window validation that still reaches the member.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BUILTIN_MEMBER = r'''class Box:
    pass


def defined() -> None:
    pass


def from_arg(member) -> None:
    try:
        print("arg-start", "abc".startswith((member,)))
        print("arg-end", "abc".endswith((member,)))
    except TypeError as e:
        print("arg", type(e).__name__, str(e))


def probe(tag: str, f) -> None:
    try:
        print(tag, f())
    except TypeError as e:
        print(tag, type(e).__name__, str(e))


def main() -> None:
    s: str = "abc"
    member = len
    box = Box()
    box.member = len
    xs = [len]
    d = {"member": len}
    probe("start", lambda: s.startswith((len,)))
    probe("end", lambda: s.endswith((len,)))
    probe("late", lambda: s.startswith(("x", len)))
    probe("hit", lambda: s.startswith(("a", len)))
    probe("end-hit", lambda: s.endswith(("c", len)))
    probe("invalid-window", lambda: s.startswith((len,), 9, 0))
    probe("empty", lambda: s.startswith((), 9, 0))
    probe("variable", lambda: s.startswith((member,)))
    probe("list-item", lambda: s.startswith((xs[0],)))
    probe("dict-value", lambda: s.startswith((d["member"],)))
    probe("attribute", lambda: s.startswith((box.member,)))
    probe("scalar", lambda: s.startswith(len))
    probe("scalar-end", lambda: s.endswith(len))
    probe("user-def", lambda: s.startswith((defined,)))
    from_arg(len)
    print("done")


main()
'''


BYTES_IN_WRONG_TYPE = r'''class Box:
    pass


def probe(tag: str, f) -> None:
    try:
        print(tag, f())
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def from_arg(tag: str, x, receiver) -> None:
    probe(tag + "-arg", lambda: x in receiver)


def main() -> None:
    b: bytes = b"abc"
    ba: bytearray = bytearray(b"abc")
    box = Box()
    box.bad = "a"
    xs = ["a"]
    d = {"bad": "a"}
    for recv_name, recv in (("b", b), ("ba", ba)):
        for tag, x in (("str", "a"), ("float", 1.5), ("none", None), ("list", [1]), ("tuple", (1,))):
            probe(recv_name + "-" + tag, lambda x=x, recv=recv: x in recv)
        probe(recv_name + "-bytes", lambda recv=recv: b"a" in recv)
        probe(recv_name + "-bytearray", lambda recv=recv: bytearray(b"a") in recv)
        probe(recv_name + "-int", lambda recv=recv: 97 in recv)
        probe(recv_name + "-int-miss", lambda recv=recv: 5 in recv)
        probe(recv_name + "-bool", lambda recv=recv: True in recv)
        probe(recv_name + "-int-big", lambda recv=recv: 1000 in recv)
        probe(recv_name + "-int-neg", lambda recv=recv: -1 in recv)
        from_arg(recv_name + "-str", "a", recv)
        probe(recv_name + "-list-item", lambda recv=recv: xs[0] in recv)
        probe(recv_name + "-dict-value", lambda recv=recv: d["bad"] in recv)
        probe(recv_name + "-attribute", lambda recv=recv: box.bad in recv)
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


class Pre183Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre183-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_builtin_function_member_type_name(self):
        self.check('builtin_member', BUILTIN_MEMBER)

    def test_bytes_contains_wrong_type_name(self):
        self.check('bytes_in_wrong_type', BYTES_IN_WRONG_TYPE)


if __name__ == '__main__':
    unittest.main()
