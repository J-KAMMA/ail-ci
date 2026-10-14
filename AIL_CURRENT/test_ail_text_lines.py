"""Line-oriented text processing in the style the reference recommends (`for line in sys.stdin`,
`line.split()`, `split("|")`, `int(x)`, f-strings), checked against CPython, plus the copies and
the retention this style used to pay for:

* `s.split()` scans ASCII bytes through a class table and allocates its vector once at the exact
  size (it decoded every byte and grew the vector by realloc); non-ASCII whitespace (U+00A0,
  U+3000, U+2028, U+0085, the 0x1C-0x1F separators) still splits exactly as in CPython, and more
  than 32 pieces take the count-then-fill path.
* `len(s.encode())` is the str's byte length, with no copy.
* `x == y.lower()` / `y.upper() != x` compare against the mapped text without building it when y
  is ASCII (non-ASCII text such as "ß".upper() == "SS" still maps).
* `d.get(k, "").split()` on a str->str dict keeps the ASCII flag of the value it copies.
* `print(f"...")` writes the pieces through one stack buffer instead of joining them in
  the arena.
* A loop whose body calls a void error helper (`fail(n, why)` that raises), bumps a numeric field
  list (`st.counts[i] += 1`) or iterates `text.split("\\n")` now resets its str arena each
  iteration: before, every iteration's temporaries stayed resident until the function returned
  (an LLM-written ticket audit held 960 MB instead of 330 MB).

Aliasing: split pieces stored into a list and a dict must outlive the line they came from.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = r"""
struct Tally { counts: list[int]; extra: int; }
fn fail(n: int, why: str) -> void { raise ValueError(f"line {n}: {why}"); }
fn note(msg: str) -> void { print("note", msg); }
fn main() {
    let kinds: dict[str, str] = {"add": "name qty", "del": "name", "many": "a b c d e f g h i j k l m n o p q r s t u v w x y z aa bb cc dd ee ff gg hh"};
    let keep: list[str] = [];
    let first: dict[str, str] = {};
    let order: list[str] = [];
    let st = Tally([0, 0, 0, 0], 0);
    let n = 0;
    for line in sys.stdin {
        n += 1;
        let f = line.split();
        if len(f) == 0 { print(n, "blank", len(line.encode()), len(line)); continue; }
        let ks = kinds.get(f[0], "").split();
        st.counts[len(f) % 4] += 1;
        st.extra += len(line.encode()) - len(line);
        if f[0] == f[0].upper() { st.counts[0] += 1; }
        if f[0].lower() == "add" { print("ADD-ish", f[0]); }
        if "del" != f[0].lower() { st.extra += 1; }
        keep.append(f[len(f) - 1]);
        if f[0] not in first { first[f[0]] = f[len(f) - 1]; order.append(f[0]); }
        if f[0] == "bad" {
            try { fail(n, f[1]); } except ValueError as e { print("caught", e.message); }
        }
        if len(f) > 1 and f[1] != f[1].lower() { note(f[1]); }
        print(n, len(f), "|".join(f), len(ks), len(line.encode()));
    }
    print(len(keep), "|".join(keep));
    for k in order { print(k, first[k]); }
    print(st.counts[0], st.counts[1], st.counts[2], st.counts[3], st.extra);
    let probes = ["", "   ", "  a\tb\n", " x　y z w", "a\x1cb\x1dc\x1ed\x1fe", "\x85q\x85", "é bé é",
                  " m n o p q", "Â ", "x​y", "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32",
                  "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 　 34 é"];
    for s in probes {
        let p = s.split();
        print(len(p), "[" + "][".join(p) + "]", len(s.encode()));
    }
    let cases = ["abc", "ABC", "Abc", "straße", "STRASSE", "ß", "SS", "İ", "i̇", "ΣΣ", "σς", ""];
    for a in cases {
        for b in cases {
            if a == b.lower() { print("lower", a, b); }
            if b.upper() == a { print("upper", a, b); }
            if a != b.upper() and b.lower() != a { st.extra += 1; }
        }
    }
    print(st.extra);
    let big = "y" * 700;
    print(f"");
    print(f"{st.extra:>8}|{big}|\u00e9{len(keep)}");
    print(f"{big}{big}");
    print(f"n={n} last={keep[len(keep) - 1]}");
}
"""

PYTHON = r'''
import sys

class Tally:
    def __init__(self, counts, extra): self.counts, self.extra = counts, extra

def fail(n, why): raise ValueError(f"line {n}: {why}")
def note(msg): print("note", msg)

def main():
    kinds = {"add": "name qty", "del": "name", "many": "a b c d e f g h i j k l m n o p q r s t u v w x y z aa bb cc dd ee ff gg hh"}
    keep, first, order = [], {}, []
    st = Tally([0, 0, 0, 0], 0)
    n = 0
    for line in sys.stdin:
        n += 1
        f = line.split()
        if len(f) == 0:
            print(n, "blank", len(line.encode()), len(line)); continue
        ks = kinds.get(f[0], "").split()
        st.counts[len(f) % 4] += 1
        st.extra += len(line.encode()) - len(line)
        if f[0] == f[0].upper(): st.counts[0] += 1
        if f[0].lower() == "add": print("ADD-ish", f[0])
        if "del" != f[0].lower(): st.extra += 1
        keep.append(f[len(f) - 1])
        if f[0] not in first:
            first[f[0]] = f[len(f) - 1]; order.append(f[0])
        if f[0] == "bad":
            try:
                fail(n, f[1])
            except ValueError as e:
                print("caught", str(e))
        if len(f) > 1 and f[1] != f[1].lower(): note(f[1])
        print(n, len(f), "|".join(f), len(ks), len(line.encode()))
    print(len(keep), "|".join(keep))
    for k in order: print(k, first[k])
    print(st.counts[0], st.counts[1], st.counts[2], st.counts[3], st.extra)
    probes = ["", "   ", "  a\tb\n", " x　y z w", "a\x1cb\x1dc\x1ed\x1fe", "\x85q\x85", "é bé é",
              " m n o p q", "Â ", "x​y", "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32",
              "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 　 34 é"]
    for s in probes:
        p = s.split()
        print(len(p), "[" + "][".join(p) + "]", len(s.encode()))
    cases = ["abc", "ABC", "Abc", "straße", "STRASSE", "ß", "SS", "İ", "i̇", "ΣΣ", "σς", ""]
    for a in cases:
        for b in cases:
            if a == b.lower(): print("lower", a, b)
            if b.upper() == a: print("upper", a, b)
            if a != b.upper() and b.lower() != a: st.extra += 1
    print(st.extra)
    big = "y" * 700
    print(f"")
    print(f"{st.extra:>8}|{big}|\u00e9{len(keep)}")
    print(f"{big}{big}")
    print(f"n={n} last={keep[len(keep) - 1]}")

main()
'''

INPUT = ("add apple 3\n  DEL   pear\n\nADD Kiwi 9\nbad Reason\nmany " + " ".join("t%d" % i for i in range(40))
         + "\nété café crème\n\tTabs\tAND\tSpaces  \nbad second\nzz\x1cyy　ww\n"
         + "".join("w%d %s v%d\n" % (i, "Up" if i % 3 else "lo", i * 7) for i in range(300)) + "last line no newline")

# A ticket-audit-shaped loop written inline: a void error helper, a numeric field list bump, a
# per-line f-string and `len(line.encode())`, iterating `text.split("\n")`.
INLINE = r"""
struct St { seen: list[int]; }
fn fail(n: int, why: str) -> void { raise ValueError(f"line {n}: {why}"); }
fn run(text: str) -> int {
    let st = St([0, 0, 0]);
    let n = 0;
    let total = 0;
    let last = "";
    for line in text.split("\n") {
        n += 1;
        if len(line.encode()) != len(line) { fail(n, "not ascii"); }
        let f = line.split("|");
        let key = f"{f[0]}:{len(f)}";
        if key == "x:1" { fail(n, "x"); }
        st.seen[len(f) % 3] += 1;
        total += len(key);
        last = key;
    }
    print(last);
    return total * 1000 + st.seen[0] * 100 + st.seen[1] * 10 + st.seen[2];
}
fn main() {
    let parts: list[str] = [];
    for i in range(int(sys.argv[1])) { parts.append(f"a{i % 7}|b|c{i}" if i % 5 else f"q{i}"); }
    let text = "\n".join(parts);
    print(run(text));
    for bad in ["ok|1\né|2", "ok\nx\nz"] {
        try { print(run(bad)); } except ValueError as e { print(e.message); }
    }
}
"""

INLINE_PY = r'''
import sys
def fail(n, why): raise ValueError(f"line {n}: {why}")
def run(text):
    seen = [0, 0, 0]; n = 0; total = 0; last = ""
    for line in text.split("\n"):
        n += 1
        if len(line.encode()) != len(line): fail(n, "not ascii")
        f = line.split("|")
        key = f"{f[0]}:{len(f)}"
        if key == "x:1": fail(n, "x")
        seen[len(f) % 3] += 1
        total += len(key)
        last = key
    print(last)
    return total * 1000 + seen[0] * 100 + seen[1] * 10 + seen[2]
parts = [f"a{i % 7}|b|c{i}" if i % 5 else f"q{i}" for i in range(int(sys.argv[1]))]
print(run("\n".join(parts)))
for bad in ["ok|1\né|2", "ok\nx\nz"]:
    try:
        print(run(bad))
    except ValueError as e:
        print(str(e))
'''


def build(directory, text, name="p"):
    source, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "-debug")
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug / "program.c"


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r"\n[\w *]+ %s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


def peak_rss_kb(argv):
    """Peak RSS of one run, from GNU time when present (None otherwise)."""
    if not Path("/usr/bin/time").exists():
        return None
    ran = subprocess.run(["/usr/bin/time", "-f", "%M", *argv], capture_output=True, text=True, timeout=120)
    return int(ran.stderr.strip().splitlines()[-1])


class TextLinesTests(unittest.TestCase):
    def test_stdin_lines_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, SOURCE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            oracle = Path(directory, "oracle.py")
            oracle.write_text(PYTHON, encoding="utf-8")
            data = INPUT.encode("utf-8")
            ran = subprocess.run([str(exe)], input=data, capture_output=True, timeout=60)
            expected = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], input=data,
                                      capture_output=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout.decode("utf-8"), expected.stdout.decode("utf-8"))
            out = ran.stdout.decode("utf-8")
            for word in ("caught line 5: Reason", "note Kiwi", "ADD-ish ADD", "upper SS ß", "lower straße straße"):
                self.assertIn(word, out)
            body = body_of(c_file.read_text(), "py_main")
            self.assertNotIn("ail_str_encode_utf8(", body)      # len(line.encode()) copies nothing
            self.assertNotIn("ail_str_lower(", body)            # x == y.lower() maps without a copy
            self.assertNotIn("ail_str_upper(", body)
            self.assertIn("ail_str_eq_casemap(", body)
            self.assertIn("ail_stdout_parts(", body)            # print(f"...") joins nothing

    def test_inline_loop_resets_its_arena_each_line(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, INLINE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            oracle = Path(directory, "oracle.py")
            oracle.write_text(INLINE_PY, encoding="utf-8")
            for count in ("1", "7", "2000"):
                with self.subTest(count=count):
                    ran = subprocess.run([str(exe), count], capture_output=True, timeout=60)
                    expected = subprocess.run([sys.executable, "-X", "utf8", str(oracle), count],
                                              capture_output=True, timeout=60)
                    self.assertEqual(ran.returncode, 0, ran.stderr)
                    self.assertEqual(ran.stdout.decode("utf-8"), expected.stdout.decode("utf-8"))
            body = body_of(c_file.read_text(), "py_run")
            self.assertIn("ail_sarena_keep_roots(", body)       # the per-line checkpoint
            self.assertNotIn("ail_str_encode_utf8(", body)
            # Memory stays O(one line) rather than O(input): 40x the lines must not cost 40x the RSS.
            small, large = peak_rss_kb([str(exe), "20000"]), peak_rss_kb([str(exe), "800000"])
            if small is not None:
                # the joined text and its split vector are O(input) in both; the per-line
                # f-strings were the extra ~40 bytes x 800k that this bounds
                self.assertLess(large - small, 120 * 1024, (small, large))


if __name__ == "__main__":
    unittest.main()
