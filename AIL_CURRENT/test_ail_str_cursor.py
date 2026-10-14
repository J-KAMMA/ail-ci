"""Cursor-backed s[i], s[a:b] and len(s) on a str that never changes give CPython's answers.

The cursor moves forwards and backwards; these programs read non-ASCII text in forward, backward
and pseudo-random orders with negative and out-of-range indexes and slice bounds, through a
parameter and a once-assigned local, and compare every printed value with Python. Linear time is
checked by a size that took 18 s when every index rescanned the text.
"""
import random
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''fn walk(text: str, seed: int) -> str {
    let out: list[str] = [];
    let n: int = len(text);
    let x: int = seed;
    for k in range(3 * n + 3) {
        x = (x * 1103515245 + 12345) % 2147483648;
        let i: int = x % (2 * n + 3) - n - 1;
        if i >= -n and i < n { out.append(text[i]); } else { out.append("|"); }
        let a: int = (x // 7) % (2 * n + 5) - n - 2;
        let b: int = (x // 11) % (2 * n + 5) - n - 2;
        out.append("[" + text[a:b] + "]");
    }
    for i in range(n) { out.append(text[n - 1 - i]); }
    for i in range(n) { out.append(text[i]); }
    return "".join(out);
}
fn main() -> int {
    let text: str = read_bytes(sys.argv[1]).decode("utf-8");
    print(walk(text, int(sys.argv[2])));
    print(len(text), text[0:0], text[2:], text[:-3]);
    return 0;
}'''

BIG = r'''fn count(text: str) -> int {
    let n: int = 0;
    for i in range(len(text)) { if text[i] == "a" { n += 1; } }
    return n;
}
fn main() -> int {
    let parts: list[str] = [];
    for i in range(int(sys.argv[1])) { parts.append("aé"); }
    let text: str = "".join(parts);
    print(count(text));
    return 0;
}'''

ALPHABET = ['a', 'b', 'é', '日', '😀', '́', ',', '\n']


def model(text, seed):
    out = []
    n = len(text)
    x = seed
    for _ in range(3 * n + 3):
        x = (x * 1103515245 + 12345) % 2147483648
        i = x % (2 * n + 3) - n - 1
        out.append(text[i] if -n <= i < n else '|')
        a = (x // 7) % (2 * n + 5) - n - 2
        b = (x // 11) % (2 * n + 5) - n - 2
        out.append('[' + text[a:b] + ']')
    out.extend(text[n - 1 - i] for i in range(n))
    out.extend(text[i] for i in range(n))
    return ''.join(out)


class StrCursorTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_random_access_matches_cpython(self):
        program = build(self, 'str_cursor', SOURCE)
        rng = random.Random(20261011)
        for case in range(150):
            text = ''.join(rng.choice(ALPHABET) for _ in range(rng.randrange(0, 30)))
            seed = rng.randrange(1, 10 ** 6)
            path = self.root / 'text.txt'
            path.write_bytes(text.encode('utf-8'))
            result = subprocess.run([str(program), str(path), str(seed)], capture_output=True, timeout=30)
            expected = '%s\n%d  %s %s\n' % (model(text, seed), len(text), text[2:], text[:-3])
            self.assertEqual((result.returncode, result.stdout.decode()), (0, expected), repr(text))

    def test_linear_time(self):
        program = build(self, 'str_cursor_big', BIG)
        result = subprocess.run([str(program), '400000'], capture_output=True, timeout=20)
        self.assertEqual((result.returncode, result.stdout), (0, b'400000\n'))


if __name__ == '__main__':
    unittest.main()
