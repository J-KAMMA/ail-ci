"""read_stdin_bytes(n) reads until n bytes or EOF, like sys.stdin.buffer.read(n) (was one read of <= 64 KiB)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
fn main() {
    let first = read_stdin_bytes(200000);
    let second = read_stdin_bytes(5);
    let third = read_stdin_bytes(1 << 40);
    let fourth = read_stdin_bytes(10);
    print(len(first), len(second), len(third), len(fourth), first[0], first[199999], third[len(third) - 1]);
    return 0;
}
"""

LOOP = """
fn main() {
    let total = 0;
    let calls = 0;
    while true {
        let chunk = read_stdin_bytes(100000);
        if len(chunk) == 0 { break; }
        total += len(chunk);
        calls += 1;
    }
    print(total, calls);
    return 0;
}
"""


class StdinReadUntilTests(unittest.TestCase):
    def build(self, source, directory):
        src, exe = Path(directory, "p.ail"), Path(directory, "p")
        src.write_text(source)
        built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(src), "-o", str(exe)],
                               capture_output=True, text=True, timeout=600)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return exe

    def test_large_reads_cross_the_old_64k_cap_and_pipes(self):
        data = bytes(i % 251 for i in range(500000))
        with tempfile.TemporaryDirectory() as directory:
            exe = self.build(SOURCE, directory)
            # a pipe delivers in small writes; the read must not stop at the first short one
            proc = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            out, _ = proc.communicate(data)
            first, second, third = 200000, 5, 500000 - 200005
            expected = "%d %d %d 0 %d %d %d\n" % (first, second, third, data[0], data[199999], data[-1])
            self.assertEqual(out.decode(), expected)

    def test_loop_variant_sums_everything(self):
        data = b"x" * 350001
        with tempfile.TemporaryDirectory() as directory:
            exe = self.build(LOOP, directory)
            ran = subprocess.run([str(exe)], input=data, capture_output=True, timeout=60)
            self.assertEqual(ran.stdout.decode(), "350001 4\n")


if __name__ == "__main__":
    unittest.main()
