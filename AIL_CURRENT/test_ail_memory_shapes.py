"""Memory and instruction shapes of three LLM-written programs (an integer counter, a record sorter,
a string-keyed table) match CPython, and the generated C keeps the properties that make them cheap.

Regression: a `while` loop that decoded every input line into the str arena kept all of them until
the function returned (the loop was refused its per-iteration reset by `slot.get(...)` on a str-keyed
dict and by `entries[i].count += 1`; 8M lines held 380 MB), `str(n)` and a struct's str field inside
a `+` chain each cost a heap block adopted into the arena for the rest of the call, `x = s.split(..)`
built the list twice, and the str-keyed dict kept 57 bytes per slot plus a second key array.
"""
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

COUNTER = r"""
use checked_integer;
struct Entry { count: int; first: int; }

fn parse(s: str) -> int {
    if len(s) < 1 or len(s) > 18 { raise ValueError("fmt"); }
    for c in s { if c < "0" or c > "9" { raise ValueError("fmt"); } }
    return int(s);
}

fn run() -> int {
    let data = read_bytes(sys.argv[1]);
    let n = len(data);
    let slot: dict[str, int] = {};
    let entries: list[Entry] = [];
    let a = 0;
    let i = 0;
    let line = 0;
    while i <= n {
        if i == n or data[i] == 10 {
            let text = data[a:i].decode();
            let idx = slot.get(text, -1);
            if idx < 0 {
                slot[text] = len(entries);
                entries.append(Entry(1, line));
            } else {
                entries[idx].count += 1;
            }
            line += 1;
            a = i + 1;
        }
        i += 1;
    }
    entries.sort(key=lambda e: (-e.count, e.first));
    let shown = 0;
    let out = "";
    for e in entries {
        if shown >= 6 { break; }
        out += str(e.count) + " " + str(e.first) + "\n";
        shown += 1;
    }
    out += "distinct " + str(len(entries)) + "\n";
    print(out, end="");
    return 0;
}

fn main() {
    try { return run(); }
    except (ValueError, IndexError) as e { return 1; }
}
"""

RECORDS = r"""
struct Rec { name: str; age: int; agestr: str; score: int; }

fn run() -> int {
    let text = read_bytes(sys.argv[1]).decode();
    let recs: list[Rec] = [];
    let lines = text.split("\n");
    for line in lines {
        if len(line) == 0 { continue; }
        let f = line.split(",");
        recs.append(Rec(f[0], int(f[1]), f[1], int(f[2])));
    }
    recs.sort(key=lambda r: (-r.score, r.age, r.name));
    if len(recs) > 1 {
        let j = 1;
        recs[j].agestr = "A" + recs[j].agestr;
        recs[j].age += 100;
        recs[j].score = recs[j].score - 1;
    }
    let out: list[str] = [];
    for r in recs {
        out.append(r.name + "," + r.agestr + "," + str(r.score) + "," + str(0 - r.age) + "," + str(r.score // 3));
    }
    if len(out) > 0 { print("\n".join(out)); }
    return 0;
}

fn main() { return run(); }
"""

TABLE = r"""
fn main() -> int {
    let words = read_bytes(sys.argv[1]).decode("utf-8").split("\n");
    let d: dict[str, int] = {};
    let seen: list[str] = [];
    let k = 0;
    for w in words {
        if k % 5 == 3 and len(seen) > 0 {
            let victim = seen[k % len(seen)];
            if victim in d { d.pop(victim); }
        }
        if w in d { d[w] = d[w] + 1; } else { d[w] = k; seen.append(w); }
        k += 1;
    }
    let total = 0;
    let first: list[str] = [];
    for w in d.keys() {
        total += d[w] * len(w);
        if len(first) < 8 { first.append(w); }
    }
    let c = d.copy();
    c["extra"] = 7;
    d.update(c);
    print(len(d), len(c), total, "extra" in d, d.get("zz-missing", -5));
    print(",".join(first));
    d.clear();
    print(len(d), len(c), "extra" in d);
    d["again"] = 1;
    for w in c.keys() { if w in d { d[w] += 1; } else { d[w] = 2; } }
    print(len(d), d["again"], d["extra"]);
    return 0;
}
"""


SETS = r"""
fn main() -> int {
    let words = read_bytes(sys.argv[1]).decode().split("\n");
    let st = set();
    let m = {};
    let k = 0;
    for w in words {
        st.add(w);
        m[w] = len(w) + m.get(w, 0);
        if k % 4 == 3 { st.discard(words[k // 2]); }
        k += 1;
    }
    let total = 0;
    for w in st { total += len(w) + 1; }
    let mt = 0;
    for w in m { mt += m[w]; }
    print(len(st), total, len(m), mt, "w1" in st, "w1" in m);
    for w in words { if w in m and len(w) > 2 { m.pop(w); } }
    print(len(m));
    return 0;
}
"""


FLOATS = r"""
struct P { name: str; w: float; k: int; }

fn main() -> int {
    let rows = read_bytes(sys.argv[1]).decode().split("\n");
    let ps: list[P] = [];
    for line in rows {
        if len(line) == 0 { continue; }
        let f = line.split(" ");
        ps.append(P(f[0], float(f[1]), int(f[2])));
    }
    ps.sort(key=lambda p: (-p.w, p.name, -p.k));
    for p in ps { print(p.name, p.w, p.k); }
    let q = sorted(ps, key=lambda p: (p.k, p.w));
    print(q[0].name, q[len(q) - 1].name);
    return 0;
}
"""


def floats_expected(raw):
    ps = []
    for line in raw.decode().split("\n"):
        if line:
            f = line.split(" ")
            ps.append((f[0], float(f[1]), int(f[2])))
    ps.sort(key=lambda p: (-p[1], p[0], -p[2]))
    lines = ["%s %s %d" % (p[0], repr(p[1]), p[2]) for p in ps]
    q = sorted(ps, key=lambda p: (p[2], p[1]))
    lines.append("%s %s" % (q[0][0], q[-1][0]))
    return "\n".join(lines) + "\n"


def field_program(seed, steps=90):
    """A random sequence of str-field writes on four fields of two records, as AIL and as Python.
    Short texts (up to 16 bytes) live in the record itself, longer ones on the heap; the sequence
    crosses that boundary in both directions, by assignment, by append and by self-reference."""
    rng = random.Random(seed)
    words = ["", "a", "bc", "x" * 7, "y" * 15, "z" * 16, "w" * 17, "q" * 33, "\u00e9" * 8, "\u00e9" * 9,
             "\u65e5\u672c\u8a9e" * 3, "k" * 70]
    fields = [("x", "a"), ("x", "b"), ("y", "a"), ("y", "b")]
    ail, py = [], []
    for _ in range(steps):
        (o1, f1), (o2, f2) = rng.choice(fields), rng.choice(fields)
        kind = rng.randrange(7)
        lit = rng.choice(words)
        t1, t2 = "%s.%s" % (o1, f1), "%s.%s" % (o2, f2)
        if kind == 0:
            line = '%s = "%s"' % (t1, lit)
        elif kind == 1:
            line = '%s += "%s"' % (t1, lit)
        elif kind == 2:
            line = "%s = %s" % (t1, t2)
        elif kind == 3:
            line = "%s += %s" % (t1, t2)
        elif kind == 4:
            line = "%s = %s[1:9]" % (t1, t2)
        elif kind == 5:
            line = '%s = %s + "%s"' % (t1, t2, lit)
        else:
            line = '%s = ""' % t1
        ail.append(line + ";")
        py.append(line)
        ail.append("print(len(x.a), x.a, len(x.b), x.b, len(y.a), y.a, len(y.b), y.b);")
        py.append("print(len(x.a), x.a, len(x.b), x.b, len(y.a), y.a, len(y.b), y.b)")
    ail_source = ("struct R { a: str; b: str; n: int; }\nfn main() -> int {\n    let x = R(\"seed\", \"\", 1);\n"
                  "    let y = R(\"\", \"0123456789abcdef!\", 2);\n    "
                  + "\n    ".join(ail) + "\n    return 0;\n}\n")
    py_source = ("class R:\n    def __init__(self, a, b, n): self.a = a; self.b = b; self.n = n\n"
                 "x = R(\"seed\", \"\", 1)\ny = R(\"\", \"0123456789abcdef!\", 2)\n" + "\n".join(py) + "\n")
    return ail_source, py_source


SMALL = r"""
fn main() -> int {
    let lines = read_bytes(sys.argv[1]).decode().split("\n");
    let xs: list[int] = [];
    for i in range(0, 210) { xs.append(i - 3); }
    let digits = "";
    for v in xs {
        digits += str(v) + ";";
        digits += "<" + str(v) + ">" + str(v + 1) + str(-v) + "|";
    }
    print(digits);
    for line in lines {
        let f = line.split(",");
        let sizes = str(len(f)) + ":";
        for part in f { sizes += str(len(part)) + "/"; }
        let a = line[2:7];
        let b = line[-4:];
        let c = line[:-3];
        let d = line[5:2];
        let e = line[100:];
        let first = "!";
        if len(line) > 3 { first = line[3]; }
        let last = "?";
        if len(line) > 0 { last = line[-1]; }
        print(sizes, "[" + a + "]", "[" + b + "]", "[" + c + "]", "[" + d + "]", "[" + e + "]", first, last, line.find(","), len(line));
    }
    let n = len(xs);
    print(xs[0], xs[-1], xs[n - 1], xs[-n]);
    let text = read_bytes(sys.argv[1]).decode();
    let sl = text.splitlines();
    print(len(sl));
    for x in sl { print(len(x), x[:3], x[-2:], x[1:-1]); }
    let ws = text.split();
    print(len(ws), len(ws[0]), ws[len(ws) - 1], ws[1][1:]);
    for x in text.splitlines() { print(len(x) + 0, x[0:1] + "|"); }
    let data = read_bytes(sys.argv[1]);
    print(data[0], data[-1], data[len(data) - 1], data[-len(data)]);
    print(sys.argv[2]);
    if sys.argv[2] == "list-high" { print(xs[n]); }
    if sys.argv[2] == "list-low" { print(xs[-n - 1]); }
    if sys.argv[2] == "bytes-high" { print(data[len(data)]); }
    if sys.argv[2] == "bytes-low" { print(data[-len(data) - 1]); }
    return 0;
}
"""


def small_expected(raw):
    lines = raw.decode().split("\n")
    xs = [i - 3 for i in range(210)]
    digits = ""
    for v in xs:
        digits += str(v) + ";"
        digits += "<" + str(v) + ">" + str(v + 1) + str(-v) + "|"
    out = [digits]
    for line in lines:
        f = line.split(",")
        sizes = str(len(f)) + ":" + "".join(str(len(part)) + "/" for part in f)
        first = line[3] if len(line) > 3 else "!"
        last = line[-1] if line else "?"
        out.append(" ".join([sizes, "[" + line[2:7] + "]", "[" + line[-4:] + "]", "[" + line[:-3] + "]",
                             "[" + line[5:2] + "]", "[" + line[100:] + "]", first, last,
                             str(line.find(",")), str(len(line))]))
    n = len(xs)
    out.append("%d %d %d %d" % (xs[0], xs[-1], xs[n - 1], xs[-n]))
    text = raw.decode()
    sl = text.splitlines()
    out.append("%d" % len(sl))
    for x in sl:
        out.append("%d %s %s %s" % (len(x), x[:3], x[-2:], x[1:-1]))
    ws = text.split()
    out.append("%d %d %s %s" % (len(ws), len(ws[0]), ws[-1], ws[1][1:]))
    for x in sl:
        out.append("%d %s" % (len(x), x[0:1] + "|"))
    out.append("%d %d %d %d" % (raw[0], raw[-1], raw[len(raw) - 1], raw[-len(raw)]))
    return "\n".join(out) + "\n"


DECODE = r"""
fn width(b: bytes) -> int {
    let s = b.decode();
    return len(s) * 1000 + len(s.split(" "));
}

fn dec(b: bytes) -> str { return b.decode(); }

fn words(b: bytes) -> list[str] { return b.decode().split(" "); }

fn run() -> int {
    let data = read_bytes(sys.argv[1]);
    let text = data.decode();
    let n = len(data);
    let total = 0;
    let a = 0;
    let i = 0;
    let longest = "";
    while i <= n {
        if i == n or data[i] == 10 {
            let piece = data[a:i].decode();
            total += len(piece);
            if len(piece) > len(longest) { longest = piece; }
            a = i + 1;
        }
        i += 1;
    }
    print(len(text), total, longest, width(data), width(data[1:]));
    print(text.upper() == text, text.find("e"), text[-5:], text[2:6]);
    let w = words(read_bytes(sys.argv[1]));
    let d = dec(read_bytes(sys.argv[1]));
    print(len(w), w[0], w[len(w) - 1], d == text, len(d));
    return 0;
}

fn main() -> int {
    try { return run(); }
    except UnicodeDecodeError { print("not utf-8"); return 3; }
}
"""


def decode_expected(raw):
    try:
        text = raw.decode()
    except UnicodeDecodeError:
        return "not utf-8\n", 3
    total, longest = 0, ""
    for piece in text.split("\n"):
        total += len(piece)
        if len(piece) > len(longest):
            longest = piece
    def width(b):
        s = b.decode()
        return len(s) * 1000 + len(s.split(" "))
    try:
        w2 = width(raw[1:])
    except UnicodeDecodeError:
        return "not utf-8\n", 3
    first = "%d %d %s %d %d\n" % (len(text), total, longest, width(raw), w2)
    second = "%s %d %s %s\n" % (text.upper() == text, text.find("e"), text[-5:], text[2:6])
    w = text.split(" ")
    third = "%d %s %s %s %d\n" % (len(w), w[0], w[-1], True, len(text))
    return first + second + third, 0


def counter_expected(raw):
    slot, count, first = {}, [], []
    for line, text in enumerate(raw.decode().split("\n")):
        if text in slot:
            count[slot[text]] += 1
        else:
            slot[text] = len(count)
            count.append(1)
            first.append(line)
    order = sorted(range(len(count)), key=lambda e: (-count[e], first[e]))
    lines = ["%d %d" % (count[e], first[e]) for e in order[:6]]
    lines.append("distinct %d" % len(count))
    return "\n".join(lines) + "\n"


def sets_expected(raw):
    words = raw.decode().split("\n")
    st, m = set(), {}
    for k, w in enumerate(words):
        st.add(w)
        m[w] = len(w) + m.get(w, 0)
        if k % 4 == 3:
            st.discard(words[k // 2])
    total = sum(len(w) + 1 for w in st)
    lines = ["%d %d %d %d %s %s" % (len(st), total, len(m), sum(m.values()), "w1" in st, "w1" in m)]
    for w in words:
        if w in m and len(w) > 2:
            m.pop(w)
    lines.append("%d" % len(m))
    return "\n".join(lines) + "\n"


def records_expected(raw):
    recs = []
    for line in raw.decode().split("\n"):
        if not line:
            continue
        f = line.split(",")
        recs.append((f[0], int(f[1]), f[1], int(f[2])))
    recs.sort(key=lambda r: (-r[3], r[1], r[0]))
    if len(recs) > 1:
        name, age, agestr, score = recs[1]
        recs[1] = (name, age + 100, "A" + agestr, score - 1)
    out = ["%s,%s,%d,%d,%d" % (r[0], r[2], r[3], -r[1], r[3] // 3) for r in recs]
    return "\n".join(out) + "\n" if out else ""


def table_expected(raw):
    d, seen, k = {}, [], 0
    for w in raw.decode().split("\n"):
        if k % 5 == 3 and seen:
            victim = seen[k % len(seen)]
            if victim in d:
                d.pop(victim)
        if w in d:
            d[w] += 1
        else:
            d[w] = k
            seen.append(w)
        k += 1
    total = sum(v * len(w) for w, v in d.items())
    first = list(d)[:8]
    c = dict(d)
    c["extra"] = 7
    d.update(c)
    lines = ["%d %d %d %s %d" % (len(d), len(c), total, "extra" in d, d.get("zz-missing", -5)),
             ",".join(first)]
    d.clear()
    lines.append("%d %d %s" % (len(d), len(c), "extra" in d))
    d["again"] = 1
    for w in c:
        if w in d:
            d[w] += 1
        else:
            d[w] = 2
    lines.append("%d %d %d" % (len(d), d["again"], d["extra"]))
    return "\n".join(lines) + "\n"


class MemoryShapeTests(unittest.TestCase):
    def build(self, directory, source):
        src, exe, debug = Path(directory, "p.ail"), Path(directory, "p"), Path(directory, "debug")
        src.write_text(source)
        built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(src),
                                "-o", str(exe), "--debug-dir", str(debug)],
                               capture_output=True, text=True, timeout=300)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return exe, (debug / "program.c").read_text()

    def run_on(self, exe, directory, raw):
        data = Path(directory, "input.bin")
        data.write_bytes(raw)
        ran = subprocess.run([str(exe), str(data)], capture_output=True, timeout=60)
        return ran.returncode, ran.stdout.decode()

    def test_counter_loop_resets_its_arena_and_matches_cpython(self):
        rng = random.Random(7)
        inputs = [b"", b"5", b"5\n", b"1\n1\n1\n2\n2\n3\n", b"\n\n7\n",
                  ("\n".join(str(rng.randrange(0, 40)) for _ in range(3000))).encode(),
                  ("\n".join(str(rng.randrange(-10 ** 17, 10 ** 17)) for _ in range(800))
                   + "\n").encode()]
        with tempfile.TemporaryDirectory() as directory:
            exe, program = self.build(directory, COUNTER)
            # The loop decodes one line per iteration into the arena; it must be reset at the top of
            # each iteration (a checkpoint with no live roots), not kept until the function returns.
            self.assertRegex(program, r"_wroots\d+\[\] = \{NULL\}")
            self.assertIn("ail_sarena_keep_roots(&v__sarena, _wmark", program)
            for raw in inputs:
                code, out = self.run_on(exe, directory, raw)
                self.assertEqual(code, 0)
                self.assertEqual(out, counter_expected(raw), raw[:40])

    def test_records_concat_uses_views_and_matches_cpython(self):
        rng = random.Random(11)
        names = ["bob", "al", "émile", "\U0001f600", "a b", "zed", "", "x" * 30]
        lines = []
        for _ in range(400):
            lines.append("%s,%d,%d" % (rng.choice(names) or "n", rng.randrange(0, 99),
                                       rng.choice([0, -1, 1, 7, -9223372036854775807, 9223372036854775807,
                                                   rng.randrange(-10 ** 9, 10 ** 9)])))
        inputs = [b"", b"a,1,2\n", ("\n".join(lines) + "\n").encode(), ("\n".join(lines)).encode()]
        with tempfile.TemporaryDirectory() as directory:
            exe, program = self.build(directory, RECORDS)
            self.assertIn("ail_str_from_int_buf(", program)
            self.assertNotRegex(program, r"ail_str_adopt\(&v__sarena, ail_str_return_owned\(\(v_r\)->f_name\)\)")
            # `recs[j].f = ...` writes the element through the list's reference, without a retain.
            self.assertRegex(program, r"\(\(ail_obj_Rec \*\)ail_olist_get\(v_recs, v_j\)\)->f_agestr")
            # `let f = line.split(",")` moves the fresh list into `f`; it is not copied a second time.
            self.assertNotIn("ail_slist _source", program)
            for raw in inputs:
                code, out = self.run_on(exe, directory, raw)
                self.assertEqual(code, 0)
                self.assertEqual(out, records_expected(raw), raw[:40])

    def test_string_table_with_deletes_matches_cpython(self):
        rng = random.Random(5)
        words = ["w%d" % rng.randrange(0, 700) for _ in range(6000)] + ["", "é", "\U0001f600", "w1"]
        rng.shuffle(words)
        inputs = [b"a", ("\n".join(words)).encode(), ("\n".join(words[:30])).encode(),
                  ("\n".join("k%d" % i for i in range(5000))).encode()]
        with tempfile.TemporaryDirectory() as directory:
            exe, _ = self.build(directory, TABLE)
            for raw in inputs:
                code, out = self.run_on(exe, directory, raw)
                self.assertEqual(code, 0)
                self.assertEqual(out, table_expected(raw), raw[:40])

    def test_str_sets_and_untyped_dicts_match_cpython(self):
        rng = random.Random(3)
        words = ["w%d" % rng.randrange(0, 900) for _ in range(5000)] + ["", "\u00e9", "w1", "ab"]
        rng.shuffle(words)
        inputs = [b"", b"w1\nw2\nw3\nw1\nab\nw22\n\nw1\n", ("\n".join(words)).encode(),
                  ("\n".join("key-%d" % i for i in range(9000))).encode()]
        with tempfile.TemporaryDirectory() as directory:
            exe, _ = self.build(directory, SETS)
            for raw in inputs:
                code, out = self.run_on(exe, directory, raw)
                self.assertEqual(code, 0)
                self.assertEqual(out, sets_expected(raw), raw[:40])

    def test_float_and_descending_sort_keys_match_cpython(self):
        rng = random.Random(9)
        lines = ["n%d %s %d" % (rng.randrange(0, 30), rng.choice(["0.5", "1.25", "-2.5", "3.0", "1e3", "-0.0", "0.0"]),
                               rng.randrange(-3, 4)) for _ in range(300)]
        inputs = [("a 1.5 1\n").encode(), ("\n".join(lines) + "\n").encode()]
        with tempfile.TemporaryDirectory() as directory:
            exe, program = self.build(directory, FLOATS)
            # One comparator per key list, written out: no key loop or field switch at run time.
            self.assertRegex(program, r"ail_olist_cmp_P_1d_0a_2d\(")
            self.assertRegex(program, r"ail_olist_cmp_P_2a_1a\(")
            for raw in inputs:
                code, out = self.run_on(exe, directory, raw)
                self.assertEqual(code, 0)
                self.assertEqual(out, floats_expected(raw), raw[:40])

    def test_short_str_fields_live_in_the_record_and_match_cpython(self):
        for seed in (1, 2):
            ail_source, py_source = field_program(seed)
            with tempfile.TemporaryDirectory() as directory:
                exe, program = self.build(directory, ail_source)
                self.assertIn("f_a_inl[16]", program)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
                expected = subprocess.run([sys.executable, "-c", py_source], capture_output=True, timeout=60)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertEqual(ran.stdout.decode(), expected.stdout.decode(), seed)

    def test_small_ints_slices_splits_and_indexes_match_cpython(self):
        lines = ["", ",", ",,,", "a,b,c", "x" * 120 + ",y", ",".join("f%d" % i for i in range(20)),
                 "caf\u00e9,\u65e5\u672c\u8a9e,x", "plain text no commas", "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15",
                 "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16", "abcdefghij", "\u00e9" * 120]
        raw = ("\n".join(lines)).encode()
        with tempfile.TemporaryDirectory() as directory:
            exe, program = self.build(directory, SMALL)
            data = Path(directory, "input.bin")
            data.write_bytes(raw)
            ran = subprocess.run([str(exe), str(data), "ok"], capture_output=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout.decode(), small_expected(raw) + "ok\n")
            for case in ("list-high", "list-low", "bytes-high", "bytes-low"):
                ran = subprocess.run([str(exe), str(data), case], capture_output=True, timeout=60)
                self.assertNotEqual(ran.returncode, 0, case)
                self.assertIn(b"index out of range", ran.stderr, case)
                self.assertTrue(ran.stdout.decode().endswith(case + "\n"), case)

    def test_decoded_text_is_a_view_of_the_input_and_validates_like_cpython(self):
        inputs = [b"a", b"hello world\nsecond line here\n", "caf\u00e9 \u65e5\u672c\u8a9e\n\U0001f600 end".encode(),
                  b"ab\xff", b"abc\xc3", b"\xed\xa0\x80 surrogate", b"\xc0\x80", b"\xf4\x90\x80\x80", b"x\n" * 3000,
                  "\u00e9".encode() + b"a b c", b""[:0] + b"e"]
        with tempfile.TemporaryDirectory() as directory:
            exe, program = self.build(directory, DECODE)
            self.assertEqual(program.count("ail_bytes_decode_utf8_view(") - 1, 5)   # five uses and the definition
            for raw in inputs:
                code, out = self.run_on(exe, directory, raw)
                want, want_code = decode_expected(raw)
                self.assertEqual((code, out), (want_code, want), raw[:30])


if __name__ == "__main__":
    unittest.main()
