"""`for c in s` over a str matches CPython: ASCII, mixed, non-BMP, empty, break/continue, loops that do
and do not allocate, and `len(s)` compared with 0/1 (the byte-length shortcut).

Each input line goes through several loops (allocation-free scans, an accumulator, a reversal that
allocates every step, the loop variable read after the loop, a nested loop) and the printed fields
are compared with the same computation in Python.
"""
import random
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''fn digits_only(s: str) -> int {
    if len(s) == 0 { return -1; }
    for c in s {
        if c < "0" or c > "9" { return -2; }
    }
    return 1;
}
fn ord_sum(s: str) -> int {
    let t = 0;
    for c in s {
        let o = ord(c);
        if o > 127 { t += 1000; } else { t += o; }
    }
    return t;
}
fn skip_stop(s: str) -> int {
    let n = 0;
    for c in s {
        if c == "x" { continue; }
        if c == "!" { break; }
        n += 1;
    }
    return n;
}
fn lower_ascii(s: str) -> str {
    let w = "";
    for c in s {
        if c >= "A" and c <= "Z" { w += chr(ord(c) + 32); } else { w += c; }
    }
    return w;
}
fn word_count(s: str) -> int {
    let w = "";
    let n = 0;
    for c in s {
        if c == " " {
            if len(w) > 0 { n += 1; w = ""; }
        } else {
            w += c;
        }
    }
    if len(w) > 0 { n += 1; }
    return n;
}
fn reversed_text(s: str) -> str {
    let r = "";
    for c in s { r = c + r; }
    return r;
}
fn last_char(s: str) -> str {
    let last = "";
    for c in s { last = c; }
    return last;
}
fn widths(s: str) -> str {
    let out = "";
    for c in s {
        out += str(len(c)) + str(len(c.encode()));
    }
    return out;
}
fn nested(s: str) -> int {
    let n = 0;
    for a in s {
        for b in s {
            if a == b { n += 1; }
        }
    }
    return n;
}
fn guarded(s: str) -> int {
    let n = 0;
    try {
        for c in s {
            let d: int = ord(c) - 48;
            if d < 0 or d > 9 { raise ValueError; }
            n = n * 10 + d;
            if n > 1000000000 { break; }
        }
    } except ValueError {
        return -7;
    }
    return n;
}
fn flags(s: str) -> str {
    let f = "";
    if len(s) > 0 { f += "a"; }
    if len(s) == 0 { f += "b"; }
    if len(s) != 0 { f += "c"; }
    if len(s) <= 0 { f += "d"; }
    if len(s) >= 1 { f += "e"; }
    if len(s) < 1 { f += "f"; }
    if 0 < len(s) { f += "g"; }
    if 1 > len(s) { f += "h"; }
    if 0 == len(s) { f += "i"; }
    if len(s) == 1 { f += "j"; }
    if len(s) > 1 { f += "k"; }
    return f;
}
fn main() -> int {
    let text: str = read_bytes(sys.argv[1]).decode("utf-8");
    let out: list[str] = [];
    for line in text.split("\n") {
        out.append(str(digits_only(line)) + "\t" + str(ord_sum(line)) + "\t" + str(skip_stop(line)) + "\t"
                   + lower_ascii(line) + "\t" + str(word_count(line)) + "\t" + reversed_text(line) + "\t"
                   + last_char(line) + "\t" + widths(line) + "\t" + str(nested(line)) + "\t" + flags(line) + "\t" + str(guarded(line)));
    }
    write_stdout_bytes("\n".join(out).encode("utf-8"));
    return 0;
}'''

PIECES = ['a', 'Z', 'x', '!', ' ', '0', '9', '7', 'é', 'Ω', '日', '😀', '\U00010400', '́', 'ß', 'K', 'q', '\t']


def expected(line):
    digits = -1 if not line else (1 if all('0' <= c <= '9' for c in line) else -2)
    ord_sum = sum(1000 if ord(c) > 127 else ord(c) for c in line)
    n = 0
    for c in line:
        if c == 'x':
            continue
        if c == '!':
            break
        n += 1
    lowered = ''.join(chr(ord(c) + 32) if 'A' <= c <= 'Z' else c for c in line)
    words = sum(1 for _ in [w for w in line.split(' ') if w])
    widths = ''.join('%d%d' % (len(c), len(c.encode())) for c in line)
    nested = sum(1 for a in line for b in line if a == b)
    f = ''
    size = len(line)
    for flag, cond in zip('abcdefghijk', (size > 0, size == 0, size != 0, size <= 0, size >= 1, size < 1,
                                          0 < size, 1 > size, 0 == size, size == 1, size > 1)):
        if cond:
            f += flag
    g = 0
    for c in line:
        d = ord(c) - 48
        if d < 0 or d > 9:
            g = -7
            break
        g = g * 10 + d
        if g > 1000000000:
            break
    return '\t'.join((str(digits), str(ord_sum), str(n), lowered, str(words), line[::-1],
                      line[-1:], widths, str(nested), f, str(g)))


class StrIterFastTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def check(self, program, lines):
        path = self.root / 'iter.txt'
        path.write_bytes('\n'.join(lines).encode('utf-8'))
        result = subprocess.run([str(program), str(path)], capture_output=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        got = result.stdout.decode('utf-8').split('\n')
        want = [expected(line) for line in lines]
        self.assertEqual(len(got), len(want))
        bad = [(lines[i], got[i], want[i]) for i in range(len(want)) if got[i] != want[i]]
        self.assertFalse(bad, bad[:5])

    def test_matches_cpython(self):
        program = build(self, 'str_iter_fast', SOURCE)
        fixed = ['', 'a', 'x', '!', 'abc', '12345', '0', '日', '😀', 'é', 'aé日😀z', 'xx!xx', 'Hello World  ',
                 ' a  b ', 'ABC xyz', '😀😀😀', 'é', '9' * 40, 'x' * 20 + '!' + 'y',
                 'The Quick BROWN fox', 'ÀÉÎ ÕÜ',
                 '123', '000', '1234567890123', '12a3', '٣']
        self.check(program, fixed)
        rng = random.Random(20261012)
        ascii_only = [''.join(rng.choice(PIECES[:8] + [' ', 'K', 'q']) for _ in range(rng.randrange(0, 30)))
                      for _ in range(300)]
        self.check(program, ascii_only)
        mixed = [''.join(rng.choice(PIECES) for _ in range(rng.randrange(0, 24))) for _ in range(600)]
        self.check(program, mixed)

    def test_long_text(self):
        program = build(self, 'str_iter_fast_long', SOURCE)
        rng = random.Random(7)
        line = ''.join(rng.choice(PIECES) for _ in range(900))
        self.check(program, [line, 'ab ' * 300, line[::-1]])


if __name__ == '__main__':
    unittest.main()
