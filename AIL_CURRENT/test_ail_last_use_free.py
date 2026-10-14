"""Numeric lists and fresh bytes are freed right after their last use.

Every case here would read freed memory (or print a different answer) if a free were placed too
early: a use in a later loop iteration, a use in an exception handler, a slice that keeps a view of
the bytes, an alias, and a value returned from the function.
"""
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''fn scale(xs: list[float], k: float) -> list[float] {
    let out: list[float] = [];
    for x in xs { out.append(x * k); }
    return out;
}
fn total(xs: list[float]) -> float {
    let s: float = 0.0;
    for x in xs { s += x; }
    return s;
}
fn twice(b: bytes) -> bytes { return b + b; }
fn count_bytes(b: bytes) -> int { return len(b); }
fn kept_slice(path: str) -> bytes {
    let data: bytes = read_bytes(path);
    let head: bytes = data[0:3];
    return head;
}
fn pipeline(path: str) -> float {
    let data: bytes = read_bytes(path);
    let n: int = count_bytes(data);
    let xs: list[float] = [];
    for i in range(n) { xs.append(1.0 * i); }
    let ys: list[float] = scale(xs, 2.0);
    let zs: list[float] = scale(ys, 0.5);
    return total(zs);
}
fn loop_reuse() -> float {
    let acc: float = 0.0;
    let xs: list[float] = [1.0, 2.0, 3.0];
    for round in range(3) {
        let ys: list[float] = scale(xs, 1.0 * round);
        acc += total(ys);
    }
    return acc;
}
fn handler_use(path: str) -> int {
    let xs: list[int] = [1, 2, 3];
    let data: bytes = read_bytes(path);
    try {
        let k: int = count_bytes(data) // 0;
        print(k);
    } except ZeroDivisionError {
        return len(xs) + count_bytes(data);
    }
    return 0;
}
fn alias(path: str) -> int {
    let data: bytes = read_bytes(path);
    let other: bytes = data;
    let n: int = count_bytes(data);
    return n + len(other);
}
fn main() -> int {
    let path: str = sys.argv[1];
    print(pipeline(path));
    print(loop_reuse());
    print(handler_use(path));
    print(alias(path));
    print(kept_slice(path).decode());
    print(count_bytes(twice(read_bytes(path))));
    return 0;
}'''


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
