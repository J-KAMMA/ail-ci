"""A file_chunks loop that calls value-only functions still releases each iteration's blocks.

Values that outlive the loop (a bytes result kept in a local, a running total) must survive the
per-iteration release, and every chunk must still be read correctly.
"""
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''fn doubled(b: bytes) -> bytes { return b + b; }
fn weights(b: bytes) -> list[float] {
    let out: list[float] = [];
    for x in b { out.append(1.0 * x); }
    return out;
}
fn total(xs: list[float]) -> float {
    let s: float = 0.0;
    for x in xs { s += x; }
    return s;
}
fn main() -> int {
    let kept: bytes = b"";
    let sum: float = 0.0;
    let chunks: int = 0;
    for chunk in file_chunks(sys.argv[1], 7) {
        let twice: bytes = doubled(chunk);
        sum += total(weights(twice));
        kept = twice;
        chunks += 1;
    }
    print(chunks, sum, kept.decode());
    return 0;
}'''


class ChunkLoopReleaseTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_values_outlive_released_iterations(self):
        program = build(self, 'chunk_loop_release', SOURCE)
        text = 'abcdefghijklmnopqrstuvwxyz0123456789'
        data = self.write('input.txt', text)
        result = subprocess.run([str(program), str(data)], capture_output=True, timeout=30)
        expected = '%d %s %s\n' % (6, repr(float(2 * sum(text.encode()))), text[35:] * 2)
        self.assertEqual((result.returncode, result.stdout.decode()), (0, expected),
                         result.stderr.decode(errors='replace'))

    def test_value_struct_built_and_read_in_the_loop(self):
        source = r'''struct Reader { data: bytes; position: int; }
impl Reader {
    fn remaining(self) -> int { return len(self.data) - self.position; }
    fn next(self) -> int { let v = self.data[self.position]; self.position = self.position + 1; return v; }
    fn rest(self) -> bytes { return self.data[self.position:]; }
}
fn main() -> int {
    let total: int = 0;
    let last = Reader(b"", 0);
    let tail: bytes = b"";
    for chunk in file_chunks(sys.argv[1], 5) {
        let reader = Reader(chunk, 0);
        while reader.remaining() > 2 { total += reader.next(); }
        tail = reader.rest();
        last = reader;
    }
    print(total, tail.decode(), last.remaining());
    return 0;
}'''
        program = build(self, 'chunk_loop_struct', source)
        text = 'abcdefghijklmnopqrstuvwxyz'
        data = self.write('letters.txt', text)
        result = subprocess.run([str(program), str(data)], capture_output=True, timeout=30)
        chunks = [text[i:i + 5] for i in range(0, len(text), 5)]
        total = sum(sum(c[:max(len(c) - 2, 0)].encode()) for c in chunks)
        last = chunks[-1]
        expected = '%d %s %d\n' % (total, last[max(len(last) - 2, 0):], min(len(last), 2))
        self.assertEqual((result.returncode, result.stdout.decode()), (0, expected),
                         result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
