"""Differential fuzz round 20: int bit operations and int methods.

`int.from_bytes` on the general path converted its argument with the `bytes()` constructor rules
(`prelude_bytes._ail_b_source`), so an int became that many zero bytes and `None` became empty:
`int.from_bytes(1, "big")` and `int.from_bytes(None, "big")` printed 0 where CPython raises
TypeError. Only bytes-like objects and iterables of ints are accepted now; a str is rejected with
CPython's TypeError too. The rest of this round (bit_length, bit_count, to_bytes, shifts, and
negative and/or/xor/invert, bin/hex/oct) is compared on both builds below.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FROM_BYTES_TYPES = r'''class Box:
    def __init__(self, v: int) -> None:
        self.v: int = v


def main() -> None:
    vals: list[bytes] = [b"", b"\x00", b"\xff", b"\x80", b"\x00\x01", b"\xff\xfe"]
    for b in vals:
        for order in ["big", "little"]:
            for signed in [False, True]:
                print(len(b), order, signed, int.from_bytes(b, order, signed=signed))
    ba: bytearray = bytearray(b"\xfe\xff")
    print(int.from_bytes(ba, "big"), int.from_bytes(ba, "little", signed=True))
    for good in [[1, 2], (1, 2), [255], []]:
        print(int.from_bytes(good, "big"), int.from_bytes(good, "little"))
    d: dict[str, int] = {"v": -7}
    boxes: list[Box] = [Box(-7), Box(9)]
    print(int.from_bytes(d["v"].to_bytes(2, "little", signed=True), "little", signed=True))
    print(int.from_bytes(boxes[0].v.to_bytes(2, "big", signed=True), "big", signed=True))
    for bad in [1, None, "1", 1.5, True, False]:
        try:
            print(int.from_bytes(bad, "big"))
        except TypeError as e:
            print("TypeError", e)
    try:
        int.from_bytes(b"\x01", "middle")
    except ValueError:
        print("ValueError")


main()
'''

INT_BITS = r'''def main() -> None:
    xs: list[int] = [0, 1, -1, 5, -5, 255, 256, -256, 123456789, -123456789,
                     9223372036854775807, -9223372036854775807 - 1]
    for x in xs:
        print(x.bit_length(), x.bit_count(), bin(x), hex(x), oct(x))
        print(x & -7, x | -7, x ^ -7, ~x)
    small: list[int] = [0, 1, -1, 5, -5, 255, 256, -256, 123456789, -123456789]
    for x in small:
        for k in [0, 1, 3, 8, 31]:
            print(x << k, x >> k)
    for x in xs:
        for k in [-1, -100]:
            try:
                print(x << k)
            except ValueError:
                print("ValueError")
            try:
                print(x >> k)
            except ValueError:
                print("ValueError")
    d: dict[str, int] = {"a": -5, "b": 7}
    boxes: list[int] = [-5, 7]
    print(d["a"] & d["b"], boxes[0] | boxes[1], ~boxes[0] ^ d["b"])


main()
'''

TO_BYTES = r'''def main() -> None:
    xs: list[int] = [0, 1, -1, 5, -5, 255, 256, -256]
    for x in xs:
        for n in [0, 1, 2, 8]:
            for order in ["big", "little"]:
                for signed in [False, True]:
                    try:
                        print(x, n, order, signed, x.to_bytes(n, order, signed=signed).hex())
                    except OverflowError:
                        print(x, n, order, signed, "OverflowError")
    for n in [-1, -100]:
        try:
            print((1).to_bytes(n, "big"))
        except ValueError:
            print("ValueError")
    for order in ["middle", "", "BIG"]:
        try:
            print((1).to_bytes(1, order))
        except ValueError:
            print("ValueError")
    try:
        print((1.5).to_bytes(1, "big"))
    except AttributeError:
        print("AttributeError")


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


class Fuzz20Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz20-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_from_bytes_rejects_non_bytes(self):
        self.check('from_bytes_types', FROM_BYTES_TYPES)

    def test_int_bits(self):
        self.check('int_bits', INT_BITS)

    def test_to_bytes(self):
        self.check('to_bytes', TO_BYTES)


if __name__ == '__main__':
    unittest.main()
