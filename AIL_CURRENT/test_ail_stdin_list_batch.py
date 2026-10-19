"""Lists of str built inside a line loop keep every element; `int(bytes)`; named refusals.

A `for line in sys.stdin` (or `open(path)`) body that only appended to one list[str] was compiled
as an OUTPUT BATCH: every 8192 appends the list was written to stdout and emptied. That is right
only when the program prints the list one element per line right after the loop; for any other
use (`len`, `sort`, indexing) the elements leaked to stdout and vanished from the list
(`seq 1 2000000 | bug3` printed 16,384 stray lines and `len` 4234 instead of 20618, 2026-10-14).
A print inside the body was reordered after the batch, and `print("\\n".join(out))` printed an
extra blank line when the count was a multiple of 8192. The batch now needs the list printed by
the very next statement of `main` and a body that prints nothing; the flush keeps the newest
element so a final join never sees an empty list. Every program below is judged by CPython on
inputs straddling the 8192 boundary, through each line-reading path (stdin, input(), readline(),
open()) and each place a line can be kept (list, dict key, struct field, str local).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    "count_only": '''
import sys
def main() -> int:
    out: list[str] = []
    k = 0
    for line in sys.stdin:
        k += 1
        if k % 3 == 0:
            out.append(f"x{k}")
    print(k, len(out), out[0] if out else "-", out[-1] if out else "-")
    return 0
main()
''',
    "join_after": '''
import sys
def main() -> int:
    out: list[str] = []
    for line in sys.stdin:
        out.append(line.strip() + "!")
    print("\\n".join(out))
    return 0
main()
''',
    "for_print_after": '''
import sys
def main() -> int:
    out: list[str] = []
    for line in sys.stdin:
        out.append("<" + line.rstrip("\\n") + ">")
    for x in out:
        print(x)
    return 0
main()
''',
    "join_then_len": '''
import sys
def main() -> int:
    out: list[str] = []
    for line in sys.stdin:
        out.append(line.strip())
    print("\\n".join(out))
    print(len(out))
    return 0
main()
''',
    "print_in_body": '''
import sys
def main() -> int:
    out: list[str] = []
    k = 0
    for line in sys.stdin:
        k += 1
        out.append(line.strip())
        if k % 5000 == 0:
            print("tick", k)
    print("\\n".join(out))
    return 0
main()
''',
    "sorted_after": '''
import sys
def main() -> int:
    out: list[str] = []
    for line in sys.stdin:
        out.append(line.strip())
    out.sort()
    print(len(out), out[0], out[-1], out[len(out) // 2])
    return 0
main()
''',
    "dict_keys": '''
import sys
def main() -> int:
    d: dict[str, int] = {}
    for line in sys.stdin:
        w = line.strip()
        d[w] = d.get(w, 0) + len(w)
        d["k" + w[-1:]] = d.get("k" + w[-1:], 0) + 1
    t = 0
    for k, v in d.items():
        t = (t * 31 + len(k) + v) % 1000000007
    print(len(d), t, d.get("17", -1))
    return 0
main()
''',
    "split_fields": '''
import sys
def main() -> int:
    names: list[str] = []
    seen: dict[str, str] = {}
    for line in sys.stdin:
        f = line.split()
        names.append(f[0])
        seen[f[0]] = f[-1]
    c = 0
    for n in names:
        c = (c * 7 + len(n) + len(seen[n])) % 1000003
    print(len(names), len(seen), c, names[0], names[-1])
    return 0
main()
''',
    "struct_fields": '''
import sys
class Rec:
    def __init__(self, name: str, n: int):
        self.name = name
        self.n = n

def main() -> int:
    rs: list[Rec] = []
    k = 0
    for line in sys.stdin:
        k += 1
        rs.append(Rec(line.strip(), k))
    s = 0
    for r in rs:
        s = (s * 13 + len(r.name) + r.n) % 1000003
    print(len(rs), s, rs[0].name, rs[-1].name, rs[len(rs) // 2].name)
    return 0
main()
''',
    "str_field_accum": '''
import sys
class Acc:
    def __init__(self):
        self.last = ""
        self.longest = ""
        self.n = 0

def main() -> int:
    a = Acc()
    for line in sys.stdin:
        w = line.strip()
        a.n += 1
        a.last = w
        if len(w) >= len(a.longest):
            a.longest = w
    print(a.n, a.last, a.longest)
    return 0
main()
''',
    "str_locals": '''
import sys
def main() -> int:
    first = ""
    prev = ""
    longest = ""
    k = 0
    for line in sys.stdin:
        k += 1
        w = line.strip()
        if k == 1:
            first = w
        if len(w) >= len(longest):
            longest = w + "/" + prev
        prev = w
    print(k, first, prev, longest)
    return 0
main()
''',
    "input_loop": '''
def main() -> int:
    out: list[str] = []
    while True:
        try:
            s = input()
        except EOFError:
            break
        out.append(s + ".")
    print(len(out), out[0], out[-1], out[len(out) // 3])
    return 0
main()
''',
    "readline_loop": '''
import sys
def main() -> int:
    out: list[str] = []
    while True:
        s = sys.stdin.readline()
        if not s:
            break
        out.append(s.strip())
    print(len(out), out[0], out[-1], out[len(out) // 3])
    return 0
main()
''',
    "file_lines": '''
import sys
def main() -> int:
    out: list[str] = []
    for line in open(sys.argv[1]):
        out.append(line.strip())
    print(len(out), out[0], out[-1], out[len(out) // 3])
    return 0
main()
''',
    "file_join": '''
import sys
def main() -> int:
    out: list[str] = []
    for line in open(sys.argv[1]):
        out.append(line.strip())
    print("\\n".join(out))
    return 0
main()
''',
    "two_lists": '''
import sys
def main() -> int:
    a: list[str] = []
    b: list[str] = []
    for line in sys.stdin:
        w = line.strip()
        a.append(w)
        if len(w) % 2 == 0:
            b.append(w + w)
    print(len(a), len(b), a[-1], b[-1])
    return 0
main()
''',
}

# Only these may keep the bounded flush: the list is printed by the next statement.
BATCHED = {"join_after", "for_print_after", "file_join"}

CASES = (r'[b" 12\n", b"1_0", b"+7", b"-0", b"\x0b5\x0c", b"\x1c5", b"1__0", b"_1", '
         r'b"1_", b"", b" ", b"0012", b"9223372036854775807", b"-9223372036854775808", '
         r'b"\xa012", b"- 1", b"0x10", b"+", b"-", b"12a", b"\t-42\r\n", b"-_1", b"1_000_000"]')

INT_BYTES = r"""
fn parse(b: bytes) -> str {
    try {
        return str(int(b));
    } except ValueError {
        return "VE";
    }
}

fn main() {
    let cases = %s;
    let out = "";
    for c in cases { out = out + parse(c) + ","; }
    print(out);
    let line = b"id=123;n=-45;\n";
    print(int(line[3:6]) + int(line[9:12]));
    let s = 0;
    for w in b"10 20  30\n-5".split() { s += int(w); }
    print(s);
}
""" % CASES

INT_BYTES_PY = r"""
def parse(b):
    try:
        return str(int(b))
    except ValueError:
        return "VE"

out = ""
for c in %s:
    out = out + parse(c) + ","
print(out)
line = b"id=123;n=-45;\n"
print(int(line[3:6]) + int(line[9:12]))
print(sum(int(w) for w in b"10 20  30\n-5".split()))
""" % CASES


REFUSALS = [
    ('fn main() { let g: list[list[bytes]] = []; print(len(g)); }',
     ["let g: list[list[bytes]]", "rows of int, float, str or a struct", "list of structs"]),
    ('fn main() { let d: dict[bytes, int] = {}; print(len(d)); }',
     ["let d: dict[bytes,int]", "keys must be str or int", ".decode()"]),
]


def build(directory, text, name, syntax=None):
    source = Path(directory) / (name + ".ail")
    source.write_text(text)
    exe = Path(directory) / name
    debug = Path(directory) / (name + "-debug")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug),
                            *(["--syntax", syntax] if syntax else [])],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug / "program.c"


def lines(n):
    return "".join("%d %s\n" % (i, "w" * (i % 7) + str(i * 7919 % 100003)) for i in range(1, n + 1))


class StdinListBatchTests(unittest.TestCase):
    def test_line_loops_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, text in PROGRAMS.items():
                with self.subTest(program=name):
                    built, exe, c_file = build(directory, text, name, syntax="python")
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertEqual("_stdin_broots" in c_file.read_text(), name in BATCHED)
                    reference = Path(directory) / (name + "_ref.py")
                    reference.write_text(text)
                    for n in (3, 8192, 8193, 16384, 20001):
                        data = lines(n)
                        args = []
                        if "argv" in text:
                            data_file = Path(directory) / "in.txt"
                            data_file.write_text(data)
                            args = [str(data_file)]
                        ran = subprocess.run([str(exe), *args], input=data, capture_output=True,
                                             text=True, timeout=60)
                        expected = subprocess.run([sys.executable, str(reference), *args],
                                                  input=data, capture_output=True, text=True,
                                                  timeout=60)
                        self.assertEqual(expected.returncode, 0, expected.stderr)
                        self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout),
                                         "%s with %d lines" % (name, n))

    def test_int_of_bytes_matches_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, INT_BYTES, "intbytes")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn("ail_bytes_to_int(", c_file.read_text())
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", INT_BYTES_PY],
                                      capture_output=True, text=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)

    def test_refusals_name_the_construct(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, (text, needles) in enumerate(REFUSALS):
                with self.subTest(text=text):
                    built, exe, _ = build(directory, text, "r%d" % index)
                    self.assertNotEqual(built.returncode, 0)
                    self.assertFalse(exe.exists())
                    message = built.stdout + built.stderr
                    for needle in needles:
                        self.assertIn(needle, message)
                    self.assertNotIn("on a str is not built", message)


if __name__ == "__main__":
    unittest.main()
