"""Paths sped up for the three largest losses to C in the 2026-10-18 all-language comparison.

* `if <test> { x += K }` on an int local is compiled as `x += K if <test> else 0` (a conditional move,
  not an unpredictable branch; scar_life's neighbour count): the legacy path (`pyfunc._if_add_fusion`)
  and the IR path (`ir/ifadd.py`) must give CPython's results, evaluate the test exactly once, and
  still raise OverflowError exactly when the add would overflow and the test holds.
* dict[int, T] / set[int] in HASH mode keep key and value in one entry and take an inline path for
  `d[k] = v` on a key already present (echo_pack's match finder): results, order and deletions must be
  CPython's, including keys at both ends of int64 and re-inserted deleted keys.
* `out.append(n % 256)`, `out.append(n // 256)`, `out.append(n >> 8)` on a named bytearray take the
  no-retain path (the divisor is a positive literal, so the argument cannot fail or free anything).
* A list field read through the span fast path (tally_lang's interpreter) keeps Python's negative
  indices and still fails on an empty or short list.

Programs are ordinary Python (`--syntax python`): CPython is the oracle, in both AIL_IR=0 and AIL_IR=1.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

COUNTERS = '''
def loud(x: int) -> bool:
    print("t", x)
    return x > 1


def count(xs: list[int], t: int) -> int:
    c = 0
    d = 100
    e = 5
    for i in range(len(xs)):
        if xs[i] > t:
            c += 3
        if xs[i] == t:
            d -= 2
        if xs[i] < 0 and t > 5:
            c += 1
        if xs[i] % 2 == 0 or xs[i] > 8:
            e += 7
        if not (xs[i] > 0):
            e -= 1
    return c * 100000 + d * 100 + e


def grid(w: int, h: int, rounds: int) -> int:
    cur = bytearray(w * h)
    nxt = bytearray(w * h)
    for i in range(w * h):
        cur[i] = 1 if (i * 7 + i // 3) % 5 < 2 else 0
    alive = 0
    for r in range(rounds):
        alive = 0
        for y in range(h):
            for x in range(w):
                n = 0
                if cur[((y + h - 1) % h) * w + x] == 1:
                    n += 2
                if cur[((y + 1) % h) * w + x] == 1:
                    n += 2
                if cur[y * w + (x + w - 1) % w] == 1:
                    n += 2
                if cur[y * w + (x + 1) % w] == 1:
                    n += 2
                s = cur[y * w + x]
                v = 0
                if (s == 1 and (n == 4 or n == 6)) or (s == 0 and n == 3):
                    v = 1
                    alive += 1
                nxt[y * w + x] = v
        tmp = cur
        cur = nxt
        nxt = tmp
    return alive


def main() -> int:
    xs = [0] * 60
    for i in range(60):
        xs[i] = (i * 37) % 11 - 3
    print(count(xs, 4), count(xs, 7), count(xs, -3), count(xs, 100))
    k = 0
    if loud(0):
        k += 5
    if loud(2):
        k += 5
    if loud(3):
        k -= 2
    print(k)
    print(grid(13, 11, 9), grid(1, 1, 3), grid(2, 5, 4))
    return 0


main()
'''

OVERFLOW = '''
def main() -> int:
    x = 9223372036854775806
    hit = 0
    for i in range(4):
        try:
            if i % 2 == 1:
                x += 3
        except OverflowError:
            hit += 1
    print(hit, x)
    y = -9223372036854775807
    try:
        if hit > 0:
            y -= 5
        print("no")
    except OverflowError:
        print("sub overflow", y)
    z = 5
    if hit > 99:
        z += 9223372036854775807
    print(z)
    return 0


main()
'''

OVERFLOW_EXPECTED = "2 9223372036854775806\nsub overflow -9223372036854775807\n5\n"

DICTS = '''
def churn(n: int) -> int:
    d: dict[int, int] = {}
    t = 0
    for i in range(n):
        k = (i * 2654435761) % 1099511627776 - 549755813888
        if i % 5 == 0:
            k = k % 97
        if k in d:
            d[k] = d[k] + i
        else:
            d[k] = i
        if i % 7 == 0:
            d[k] = d[k] * 3 % 1000003
        if i % 11 == 0 and k in d:
            del d[k]
        if i % 13 == 0:
            d[k] = i
        t = (t * 31 + len(d)) % 1000000007
    s = 0
    for k in d:
        s = (s * 131 + d[k] + k) % 1000000007
    return s * 1000 + t % 1000


def edges() -> int:
    d: dict[int, int] = {}
    lo = (-9223372036854775807) - 1
    hi = 9223372036854775807
    d[lo] = 1
    d[hi] = 2
    d[0] = 3
    d[1099511627776] = 4
    d[-1099511627776] = 5
    d[lo] = d[lo] + 10
    d[hi] = d[hi] + 20
    del d[0]
    d[0] = 30
    d[lo] = d[lo] * 2
    out = 0
    for k in d:
        out = (out * 1000003 + d[k]) % 998244353
    return out * 10 + len(d)


def members(n: int) -> int:
    s: set[int] = set()
    c = 0
    for i in range(n):
        k = (i * 40503) % 1048583 * 4096 - 17
        if k in s:
            c += 1
        s.add(k)
        s.add(k)
        if i % 9 == 0:
            s.discard(k)
    t = 0
    for k in sorted(s):
        t = (t * 7 + k) % 1000003
    return t * 1000 + c % 1000 + len(s)


def during(n: int) -> int:
    d: dict[int, int] = {}
    for i in range(n):
        d[i * 1000003] = i
    t = 0
    for k in d:
        d[k] = d[k] + 1
        t = (t + d[k] * 3) % 1000003
    return t


def main() -> int:
    print(churn(3000), churn(40000))
    print(edges())
    print(members(5000), members(60000))
    print(during(20000))
    return 0


main()
'''

BYTES = '''
def pack(n: int, m: int) -> bytes:
    out = bytearray()
    out.append(n % 256)
    out.append((n // 256) % 256)
    out.append((n // 65536) % 256)
    out.append(n >> 24)
    out.append(m // 4)
    out.append(m % 251)
    out.append((m * 3 + n) // 7 % 256)
    out.append((n + 255) >> 1 & 255)
    return bytes(out)


def main() -> int:
    ns = [0, 1, 65535, 16777216, 1234567890]
    ms = [0, 1, 40, 1000, 999]
    for i in range(5):
        b = pack(ns[i], ms[i])
        print(len(b), b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7])
    return 0


main()
'''

FIELDS = '''
class Prog:
    def __init__(self, a: list[int], b: list[int]):
        self.a = a
        self.b = b


def last(p: Prog) -> int:
    return p.a[-1] * 100 + p.a[0] + p.b[len(p.b) - 1]


def walk(p: Prog, n: int) -> int:
    t = 0
    for i in range(n):
        t = (t * 31 + p.a[i % len(p.a)] - p.b[-1 - i % len(p.b)]) % 1000003
    return t


def main() -> int:
    p = Prog([3, 5, 8, 13], [2, 4, 6])
    print(last(p), walk(p, 50))
    return 0


main()
'''

EMPTY_FIELD = '''
class Prog:
    def __init__(self, a: list[int]):
        self.a = a


def first(p: Prog) -> int:
    return p.a[0]


def main() -> int:
    p = Prog([1])
    p.a.clear()
    print(first(p))
    return 0


main()
'''


def compile_run(directory, text, name, ir):
    source = Path(directory, name + ".ail")
    source.write_text(text)
    exe = Path(directory, "%s_%s" % (name, ir))
    env = dict(os.environ, AIL_IR=ir)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source), "-o", str(exe),
                            "--syntax", "python"], capture_output=True, text=True, timeout=600, env=env)
    return built, exe


class LossPathTests(unittest.TestCase):
    def check_oracle(self, text, name):
        with tempfile.TemporaryDirectory() as directory:
            expected = subprocess.run([sys.executable, "-c", text], capture_output=True, text=True, timeout=120)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for ir in ("0", "1"):
                with self.subTest(ir=ir):
                    built, exe = compile_run(directory, text, name, ir)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual(ran.returncode, 0, ran.stderr)
                    self.assertEqual(ran.stdout, expected.stdout)

    def test_if_add_counters_match_cpython(self):
        self.check_oracle(COUNTERS, "counters")

    def test_if_add_still_traps_on_overflow(self):
        # (the legacy int64 emitter, AIL_IR=0, traps; the IR build has exact ints, so it prints what CPython prints:
        # no OverflowError at all)
        python = subprocess.run([sys.executable, "-c", OVERFLOW], capture_output=True, text=True, timeout=60)
        self.assertEqual(python.stdout, "0 9223372036854775812" + chr(10) + "no" + chr(10) + "5" + chr(10))
        with tempfile.TemporaryDirectory() as directory:
            for ir in ("0", "1"):
                with self.subTest(ir=ir):
                    built, exe = compile_run(directory, OVERFLOW, "overflow", ir)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
                    self.assertEqual(ran.returncode, 0, ran.stderr)
                    self.assertEqual(ran.stdout, OVERFLOW_EXPECTED if ir == "0" else python.stdout)

    def test_int_dict_and_set_hit_paths_match_cpython(self):
        self.check_oracle(DICTS, "dicts")

    def test_bytearray_append_of_division_by_literal(self):
        self.check_oracle(BYTES, "bytes")

    def test_list_field_negative_index(self):
        self.check_oracle(FIELDS, "fields")

    def test_empty_list_field_read_still_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            for ir in ("0", "1"):
                with self.subTest(ir=ir):
                    built, exe = compile_run(directory, EMPTY_FIELD, "emptyfield", ir)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
                    self.assertNotEqual(ran.returncode, 0)
                    self.assertEqual(ran.stdout, "")


if __name__ == "__main__":
    unittest.main()
