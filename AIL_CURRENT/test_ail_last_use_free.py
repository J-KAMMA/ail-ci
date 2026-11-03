"""Numeric lists and fresh bytes are freed right after their last use.

Every case here would read freed memory (or print a different answer) if a free were placed too
early: a use in a later loop iteration, a use in an exception handler, a slice that keeps a view of
the bytes, an alias, and a value returned from the function.
"""
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = """from ail import read_bytes
import sys

def scale(xs: list[float], k: float) -> list[float]:
    out: list[float] = []
    for x in xs:
        out.append(x * k)
    return out

def total(xs: list[float]) -> float:
    s: float = 0.0
    for x in xs:
        s += x
    return s

def twice(b: bytes) -> bytes:
    return b + b

def count_bytes(b: bytes) -> int:
    return len(b)

def kept_slice(path: str) -> bytes:
    data: bytes = read_bytes(path)
    head: bytes = data[0:3]
    return head

def pipeline(path: str) -> float:
    data: bytes = read_bytes(path)
    n: int = count_bytes(data)
    xs: list[float] = []
    for i in range(n):
        xs.append(1.0 * i)
    ys: list[float] = scale(xs, 2.0)
    zs: list[float] = scale(ys, 0.5)
    return total(zs)

def loop_reuse() -> float:
    acc: float = 0.0
    xs: list[float] = [1.0, 2.0, 3.0]
    for round in range(3):
        ys: list[float] = scale(xs, 1.0 * round)
        acc += total(ys)
    return acc

def handler_use(path: str) -> int:
    xs: list[int] = [1, 2, 3]
    data: bytes = read_bytes(path)
    try:
        k: int = count_bytes(data) // 0
        print(k)
    except ZeroDivisionError:
        return len(xs) + count_bytes(data)
    return 0

def alias(path: str) -> int:
    data: bytes = read_bytes(path)
    other: bytes = data
    n: int = count_bytes(data)
    return n + len(other)

def main() -> int:
    path: str = sys.argv[1]
    print(pipeline(path))
    print(loop_reuse())
    print(handler_use(path))
    print(alias(path))
    print(kept_slice(path).decode())
    print(count_bytes(twice(read_bytes(path))))
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""


class LastUseFreeTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_freed_values_are_never_seen_again(self):
        program = build(self, 'last_use_free', SOURCE)
        data = self.write('input.txt', 'abcdefgh')
        result = subprocess.run([str(program), str(data)], capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stdout.decode()),
                         (0, '28.0\n18.0\n11\n16\nabc\n16\n'), result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
