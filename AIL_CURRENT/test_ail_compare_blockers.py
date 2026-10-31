"""Constructs that kept the compare-lab Python programs off the typed path (`compile --strict` refused them),
now built, each compared with CPython on boundary inputs.

T1  step slices and contiguous slices of a list of bytes (`sys.stdin.buffer.read().split()`) walked by a
    comprehension, `map(int, ...)`, `sum` / `min` / `max` / `sorted` / `list`: positive, negative, zero (a
    ValueError) and larger-than-len steps, empty lists, bounds past either end
T2  `buf += chunk` on a bytearray is `buf.extend(chunk)` (bytes and bytearray operands)
T3  `for v in reversed(xs)` and `ys.extend(reversed(xs))` over a list, empty or not; a body that changes the
    list keeps the original route
T4  `del name` of a local nothing reads afterwards
T5  a `def` inside a `for` / `while` body: a pure helper is hoisted, one that reads a loop local is lifted
T6  an unannotated helper returning a tuple built from its parameters, typed by what its callers pass
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'


def run_cpython(source, stdin):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'prog.py'
        path.write_text(source, encoding='utf-8')
        result = subprocess.run([sys.executable, '-I', str(path)], input=stdin, capture_output=True, timeout=120)
    return result.returncode, result.stdout


class CompareBlockerTests(unittest.TestCase):
    def build(self, source, strict=True):
        """The compiled program's path; the build must succeed, on the typed path when strict."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        src = Path(tmp.name) / 'prog.py'
        src.write_text(source, encoding='utf-8')
        out = Path(tmp.name) / 'prog'
        cmd = [sys.executable, str(CLI), 'compile', '--syntax', 'python', str(src), '-o', str(out)]
        if strict:
            cmd.insert(3, '--strict')
        env = dict(os.environ, AIL_QUIET_FALLBACK='1')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return out

    def agree(self, source, inputs, strict=True):
        exe = self.build(source, strict)
        for stdin in inputs:
            data = stdin.encode()
            expected = run_cpython(source, data)
            got = subprocess.run([str(exe)], input=data, capture_output=True, timeout=120)
            self.assertEqual((got.returncode, got.stdout), expected, 'stdin %r' % stdin)

    # -- T1 -------------------------------------------------------------------------------------------
    def test_t1_bytes_list_slices(self):
        source = '''import sys


def main():
    data = sys.stdin.buffer.read().split()
    n = len(data)
    a = int(data[0]) if n else 0
    b = int(data[1]) if n > 1 else 0
    c = int(data[2]) if n > 2 else 1
    ids = list(map(int, data[a:b:c if c else 1]))
    print(ids)
    print([int(t) for t in data[::2]])
    print([int(t) for t in data[1::3]])
    print([int(t) for t in data[::-1]])
    print([int(t) for t in data[-2::-2]])
    print(sum(int(t) for t in data[1:]))
    print(sum(map(int, data[::2])), max(map(int, data)), min(map(int, data[1:])))
    print(sorted(map(int, data[::3])))
    print([int(t) * 2 for t in data[100::5]], [int(t) for t in data[2:1]])
    print([int(t) for t in data if int(t) > 3])
    print(len([int(t) for t in data[::7]]), [t.decode() for t in data[:3]])
    try:
        z = list(map(int, data[::c - c]))
        print(z)
    except ValueError as e:
        print("ValueError", e)


main()
'''
        inputs = ['1 5 2 8 9 3 7 2 1 6 4', '0 3 1 4 4 4', '3 0 -1 1 2 3 4 5 6', '2 9 100 5 6 7 8 9 10 11 12 13',
                  '-3 99 2 1 2 3 4 5', '5 0 -2 9 8 7 6 5 4 3', '0 1 1 5']
        self.agree(source, inputs)

    def test_t1_empty_input(self):
        source = '''import sys


def main():
    data = sys.stdin.buffer.read().split()
    print([int(t) for t in data[::2]], list(map(int, data[1::2])), sum(int(t) for t in data[::-1]))


main()
'''
        self.agree(source, ['', '   \n', '4', '4 5'])

    # -- T2 -------------------------------------------------------------------------------------------
    def test_t2_bytearray_augmented_add(self):
        source = '''import sys


def main():
    data = sys.stdin.buffer.read()
    out = bytearray()
    out += data[1:4]
    out += (7).to_bytes(2, "big")
    out += bytes([65, 66])
    more = bytearray(b"xy")
    out += more
    out += b""
    out += data[100:]
    out += b"zz"
    sys.stdout.buffer.write(bytes(out))
    print(len(out), out[0], out[-1])


main()
'''
        self.agree(source, ['hello world', 'abcdef'])

    # -- T3 -------------------------------------------------------------------------------------------
    def test_t3_reversed_lists(self):
        source = '''import sys


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0]) if data else 0
    order = [int(t) for t in data[1:1 + n]]
    words = [t.decode() for t in data[1 + n:]]
    st = []
    st.extend(reversed(order))
    acc = 0
    for v in reversed(order):
        acc = acc * 31 + v
    out = []
    for w in reversed(words):
        out.append(w.upper())
    empty = []
    for z in reversed(empty):
        acc += 1000
    last = -1
    for v in reversed(order):
        last = v
        if v == 20:
            break
    print(acc, st, " ".join(out), last)


main()
'''
        self.agree(source, ['4 10 20 30 40 foo bar baz', '0', '', '1 7', '3 20 1 2 x', '2 5 6'])

    def test_t3_reversed_loop_that_changes_the_list_keeps_python_behaviour(self):
        source = '''import sys


def main():
    data = sys.stdin.buffer.read().split()
    xs = [int(t) for t in data]
    seen = []
    for v in reversed(xs):
        seen.append(v)
        if len(xs) > 1:
            xs.pop()
    print(seen, xs)


main()
'''
        self.agree(source, ['1 2 3 4', '5'], strict=False)

    # -- T4 -------------------------------------------------------------------------------------------
    def test_t4_del_of_a_local_nobody_reads_again(self):
        source = '''import sys


def main():
    data = sys.stdin.buffer.read().split()
    xs = [int(t) for t in data]
    tmp = [x * 2 for x in xs]
    total = sum(tmp)
    del tmp
    del data
    big = [1, 2, 3]
    del big
    print(total, len(xs))


main()
'''
        self.agree(source, ['1 2 3', ''])

    def test_t4_del_in_a_loop_or_before_a_later_read_is_kept(self):
        source = '''import sys


def main():
    data = sys.stdin.buffer.read().split()
    xs = [int(t) for t in data]
    for i in range(2):
        tmp = [x + i for x in xs]
        print(sum(tmp))
        del tmp
    del xs
    try:
        print(xs)
    except NameError:
        print("gone")


main()
'''
        self.agree(source, ['1 2 3'], strict=False)

    # -- T5 -------------------------------------------------------------------------------------------
    def test_t5_def_inside_a_loop(self):
        source = '''import sys


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    k = int(data[1])
    total = 0
    acc = []
    for gi in range(1, n + 1):
        a = gi * k
        b = gi + k

        def mix(x, y, z, w):
            s1 = x ^ y
            c1 = x & y
            s2 = z ^ w
            return s1 ^ s2 ^ c1 ^ (z & w) ^ (s1 & s2)

        o0 = mix(a, b, gi, k)
        d0 = mix(b, a, k, gi)
        total += o0 * 3 + d0 + a
        acc.append(o0 ^ d0)
    i = 0
    while i < 3:
        def bump(v):
            return v + i * k

        total += bump(i)
        i += 1
    print(total, sum(acc))


main()
'''
        self.agree(source, ['7 3', '0 5', '1 0', '4 -2'])

    # -- T6 -------------------------------------------------------------------------------------------
    def test_t6_helper_returning_a_tuple_of_its_parameters(self):
        source = '''import sys


def count4(x, y, z, w):
    s1 = x ^ y
    c1 = x & y
    s2 = z ^ w
    c2 = z & w
    kk = s1 & s2
    return s1 ^ s2, c1 ^ c2 ^ kk, c1 & c2


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    k = int(data[1])
    total = 0
    for gi in range(1, n + 1):
        a = gi * k
        b = gi + k
        o0, o1, o2 = count4(a, b, gi, k)
        d0, d1, d2 = count4(b, a, k, gi)
        total += o0 + o1 * 3 + o2 * 5 + d0 - d1 + d2 + a
    print(total)


main()
'''
        self.agree(source, ['7 3', '0 5', '3 -4'])

    def test_t6_def_in_loop_returning_a_tuple(self):
        source = '''import sys


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    k = int(data[1])
    total = 0
    for gi in range(1, n + 1):
        a = gi * k
        b = gi + k

        def count4(x, y, z, w):
            s1 = x ^ y
            c1 = x & y
            s2 = z ^ w
            c2 = z & w
            kk = s1 & s2
            return s1 ^ s2, c1 ^ c2 ^ kk, c1 & c2

        o0, o1, o2 = count4(a, b, gi, k)
        d0, d1, d2 = count4(b, a, k, gi)
        total += o0 + o1 * 3 + o2 * 5 + d0 - d1 + d2 + a
    print(total)


main()
'''
        self.agree(source, ['7 3', '0 5'])

    def test_t6_parameter_with_two_kinds_of_callers_is_not_guessed(self):
        # f gets an int from one call and a float from another: no type is chosen for x
        source = '''import sys


def f(x):
    return x, x


def main():
    data = sys.stdin.buffer.read().split()
    a, b = f(int(data[0]))
    c, d = f(float(data[1]))
    print(a, b, c, d)


main()
'''
        self.agree(source, ['3 4'], strict=False)


if __name__ == '__main__':
    unittest.main()
