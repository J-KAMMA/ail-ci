"""Plain-Python programs that used to fall off the typed path (lab/compare, 2026-10-30), against CPython 3.12.

P1  `bytes | None` is a scalar Optional like `int | None` (annotated parameter, return and local): absent, present
    and empty, truthiness, ==/!=, passing on.
P2  a function with no return annotation whose returns are `None` and one str / bytes / float value is read as
    `-> kind | None`; a function that mixes kinds, that returns ints, or whose result is used without a None test,
    keeps its old route and still prints what CPython prints (ints beyond int64 included).
P3  `ba += chunk` on a bytearray extends it in place (bytes and bytearray chunks, a copy of itself); `ba += ba`
    (a BufferError in CPython), a list or a str are not rewritten (the last two keep CPython's TypeError).
Programs meant to be typed run through the typed path alone (AIL_NO_GENERAL=1); the others through the default
build (typed path with the general path as the fallback).  All of them are compared with CPython on stdout and the
exit status.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_ail_nested_functions import build, run_cpython, run_exe   # noqa: E402

OPT_BYTES = '''import sys


def find(data: bytes, mark: bytes) -> bytes | None:
    i = data.find(mark)
    if i < 0:
        return None
    rest = data[i + len(mark):]
    return rest


def same(a: bytes | None, b: bytes | None) -> int:
    if a == b:
        return 1
    if a is not None and b is not None and a < b:
        return 2
    return 0


def main() -> int:
    data = sys.stdin.buffer.read()
    r1 = find(data, b"=")
    print("r1", r1 is None, len(data))
    if r1 is not None:
        print("r1 length", len(r1), r1.decode())
    if r1:
        print("truthy")
    else:
        print("falsy")
    x: bytes | None = None
    if len(data) > 3:
        x = data[:3]
    head = data[:3]
    print(x is None, x == b"", x != None, x == head)
    e = find(b"a=", b"=")
    print(e == b"", e is None, bool(e), not e)
    print(same(None, None), same(b"a", b"b"), same(b"b", b"a"), same(b"", None), same(b"", b""))
    if r1 is not None:
        bang = r1 + b"!"
        first = r1[:1]
        print(bang.decode(), first.decode(), r1.find(b"a"), r1.count(b"l"))
    return 0


sys.exit(main())
'''

RET_INT = '''import sys


def parse(s, lo, hi):
    if not s or not s.isdigit():
        return None
    v = int(s)
    if v < lo or v > hi:
        return None
    return v


def main():
    for word in sys.stdin.read().split():
        n = parse(word, 1, 100)
        if n is None:
            print("bad", word)
            continue
        print("ok", n * 2)
    return 0


sys.exit(main())
'''

RET_BYTES = '''import sys


def unpack(S):
    if len(S) < 3 or S[:2] != b"EP":
        return None
    out = bytearray()
    for b in S[2:]:
        out.append(b ^ 1)
    if len(out) > 8:
        return None
    return bytes(out)


def main():
    data = sys.stdin.buffer.read()
    res = unpack(data)
    if res is None:
        print("none")
        return 2
    print(res.decode(), len(res))
    return 0


sys.exit(main())
'''

RET_STR = '''import sys


def first_word(text: str):
    for w in text.split():
        if len(w) > 3:
            return w.upper()
    return None


def main():
    for line in sys.stdin.read().splitlines():
        w = first_word(line)
        if w is None:
            print("-")
        else:
            print(w, len(w))
    return 0


sys.exit(main())
'''

RET_MIXED = '''import sys


def f(n):
    if n < 0:
        return None
    if n == 0:
        return "zero"
    return n


def main():
    for tok in sys.stdin.read().split():
        r = f(int(tok))
        print(r)
    return 0


sys.exit(main())
'''

RET_UNCHECKED = '''import sys


def f(s):
    if not s:
        return None
    return s.upper()


def main():
    for tok in sys.stdin.read().split("|"):
        print(f(tok) + "!")
    return 0


sys.exit(main())
'''

RET_FALLS = '''import sys


def f(s):
    if s == "a":
        return None
    if s == "b":
        return "seven"


def main():
    for tok in sys.stdin.read().split():
        print(f(tok))
    return 0


sys.exit(main())
'''

BA_PLUS = '''import sys


def build(n: int) -> bytes:
    out = bytearray(b"EP1")
    out += n.to_bytes(4, "little")
    chunk = bytearray()
    for i in range(n):
        chunk.append((i * 7) & 255)
    out += chunk
    out += b"xyz"
    out += bytearray(b"Q")
    out += out[:2]
    out += out[:]
    return bytes(out)


def main() -> int:
    for n in [0, 1, 5, 300]:
        r = build(n)
        print(n, len(r), r[3], r[-1], sum(r) % 1000, r[0], r[1], r[2], r[7], r[8], r[9], r[10])
    return 0


sys.exit(main())
'''

BA_NOT_BYTES = '''import sys


def main() -> int:
    out = bytearray(b"ab")
    try:
        out += [1, 2]
    except TypeError:
        print("list refused")
    try:
        out += "cd"
    except TypeError:
        print("str refused")
    print(out.decode())
    return 0


sys.exit(main())
'''


class PyTypedGaps(unittest.TestCase):
    def check(self, name, text, stdins, typed_only, irs=('1',)):
        with tempfile.TemporaryDirectory() as tmp:
            for ir in irs:
                res, exe = build(tmp, text, name, ir=ir, typed_only=typed_only)
                self.assertEqual(res.returncode, 0, 'ir=%s build: %s' % (ir, res.stderr[-600:]))
                for stdin in stdins:
                    want = run_cpython(tmp, text, name, stdin)
                    got = run_exe(exe, stdin)
                    self.assertEqual((got.stdout, got.returncode), (want.stdout, want.returncode),
                                     'ir=%s stdin=%r' % (ir, stdin))

    def test_p1_optional_bytes_typed(self):
        self.check('optb', OPT_BYTES, ['key=val', 'a=', '', 'abcd', '==', 'zz=zz\n'], True)

    def test_p2_int_returns_are_not_inferred(self):
        # an `int(text)` beyond int64 stays exact: the function is built on the general path
        self.check('reti', RET_INT, ['5 7 x 0 100 101', '', '007 12a', '99999999999999999999 3 -4'], False)

    def test_p2_inferred_bytes_return_typed(self):
        self.check('retb', RET_BYTES, ['EPabc', 'EP', 'xx12', 'EPabcdefgh', 'EPabcdefghi', ''], True)

    def test_p2_inferred_str_return_typed(self):
        self.check('rets', RET_STR, ['a bb cccc dd\nxx yy\n\nabcde'], True)

    def test_p2_mixed_kinds_keep_their_route(self):
        self.check('retm', RET_MIXED, ['-1 0 5 12345678901234567890'], False)

    def test_p2_unchecked_use_is_still_cpythons_error(self):
        self.check('retu', RET_UNCHECKED, ['ab|c'], False)
        self.check('retu2', RET_UNCHECKED, ['ab||c'], False)

    def test_p2_function_that_can_fall_off_its_end(self):
        self.check('retf', RET_FALLS, ['a b c'], False)

    def test_p3_bytearray_augmented_add_typed(self):
        self.check('baplus', BA_PLUS, [''], True)

    def test_p3_bytearray_augmented_add_other_types_keep_cpython_errors(self):
        self.check('banot', BA_NOT_BYTES, [''], False)


if __name__ == '__main__':
    unittest.main()
