"""Grid index guards (ir/passes/symbounds.py, licm.py versioning; docs/design/IR_GRID_BOUNDS.md).

A loop over a grid reads `cur[up + x]`, `cur[mid + xl[x]]` with `up`, `mid` row offsets, `x` a column
index and `xl` a table of wrapped columns. LICM versions such a loop on a guard computed in front of it
from symbolic bounds (`h*w - 1 < len(cur)` for a sweep over the rows), and bytearray locals read in the
loop get spans. The checks:

* results equal CPython's in AIL_IR=0, 1 and verify for the common torus-grid shapes: bytearray
  grids with column tables and a swap of `cur`/`nxt` every generation, list[int] grids with explicit
  wrap guards (`if xl < 0: xl = w - 1`) in a struct, `% w` wrap-around;
* the fast copy runs (the reads are unchecked in the C) for the bytearray grid, and the guard is hoisted
  out of the row loop;
* an index that is out of range (a grid shorter than w*h, a column table holding a bad value, a
  table changed through a call) fails with IndexError after the same output as CPython; a byte value
  out of range still raises ValueError (the store keeps its value check), and a divisor that may be
  negative (Python's `%` is then <= 0) is guarded;
* a loop that extends a bytearray parameter it reads reads the new contents (no stale span).

Programs are ordinary Python (`--syntax python`): CPython is the oracle.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

GRID = '''
import sys


def main() -> int:
    w = int(sys.argv[1])
    h = int(sys.argv[2])
    short = int(sys.argv[3])
    bad = int(sys.argv[4])
    cur = bytearray(w * h - short)
    for i in range(w * h - short):
        if (i * 7 + i // 3) % 5 == 0:
            cur[i] = 1
    nxt = bytearray(w * h)
    xl = [0] * w
    xr = [0] * w
    for x in range(w):
        xl[x] = (x + w - 1) % w
        xr[x] = (x + 1) % w
    if bad:
        xr[w - 1] = w + bad
    for g in range(3):
        alive = 0
        for y in range(h):
            up = ((y + h - 1) % h) * w
            mid = y * w
            dn = ((y + 1) % h) * w
            for x in range(w):
                a = xl[x]
                b = xr[x]
                n = 0
                if cur[up + x] == 1:
                    n += 1
                if cur[dn + x] == 1:
                    n += 1
                if cur[mid + a] == 1:
                    n += 1
                if cur[mid + b] == 1:
                    n += 1
                if cur[up + a] == 1:
                    n += 1
                if cur[dn + b] == 1:
                    n += 1
                s = cur[mid + x]
                r = 0
                if n == 3 or (s == 1 and n == 2):
                    r = 1
                    alive += 1
                nxt[mid + x] = r
        tmp = cur
        cur = nxt
        nxt = tmp
        print(g, alive)
    return 0


sys.exit(main())
'''

GUARDS = '''
import sys


class Gr:
    def __init__(self, cur: list[int], nxt: list[int]):
        self.cur = cur
        self.nxt = nxt


def main() -> int:
    w = int(sys.argv[1])
    h = int(sys.argv[2])
    short = int(sys.argv[3])
    gr = Gr([0 for i in range(w * h - short)], [0 for i in range(w * h)])
    for i in range(w * h - short):
        gr.cur[i] = (i * 5 + i // 7) % 3
    for g in range(2):
        t = 0
        for y in range(h):
            yu = y - 1
            if yu < 0:
                yu = h - 1
            yd = y + 1
            if yd >= h:
                yd = 0
            ru = yu * w
            rc = y * w
            rd = yd * w
            for x in range(w):
                xl = x - 1
                if xl < 0:
                    xl = w - 1
                xr = x + 1
                if xr >= w:
                    xr = 0
                v = gr.cur[ru + x] + gr.cur[rd + x] + gr.cur[rc + xl] + gr.cur[rc + xr] + gr.cur[ru + xl] \\
                    + gr.cur[rd + xr]
                gr.nxt[rc + x] = v % 3
                t += v
        tmp = gr.cur
        gr.cur = gr.nxt
        gr.nxt = tmp
        print(g, t)
    return 0


sys.exit(main())
'''

TABLES = '''
import sys


def poke(xs: list[int], k: int) -> None:
    xs[0] = k


def main() -> int:
    w = int(sys.argv[1])
    m = int(sys.argv[2])
    k = int(sys.argv[3])
    v = int(sys.argv[4])
    cur = bytearray(w * 4)
    for i in range(w * 4):
        cur[i] = i % 7
    xl = [0] * w
    for x in range(w):
        xl[x] = (x + 3) % m
    poke(xl, k)
    t = 0
    for y in range(4):
        mid = y * w
        for x in range(w):
            t += cur[mid + xl[x]]
            cur[mid + x] = (cur[mid + x] + v) % 300
    print(t)
    return 0


sys.exit(main())
'''

EXTEND = '''
import sys


def grow(b: bytearray, n: int) -> int:
    t = 0
    for i in range(n):
        t += b[i]
        b.extend(b"ab")
    return t


def main() -> int:
    b = bytearray(2)
    b[0] = 5
    b[1] = 9
    print(grow(b, int(sys.argv[1])))
    print(len(b))
    return 0


sys.exit(main())
'''


def compile_exe(directory, text, name, ir, debug=None, stats=None):
    source = Path(directory, name + ".ail")
    source.write_text(text)
    exe = Path(directory, "%s_%s" % (name, ir))
    if exe.exists():
        exe.unlink()
    env = dict(os.environ, AIL_IR=ir)
    env.pop("AIL_IR_STATS", None)
    env.pop("AIL_IR_PASSES", None)
    env["AIL_NO_CACHE"] = "1"
    if stats:
        env["AIL_IR_STATS"] = str(stats)
    command = [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source), "-o", str(exe),
               "--syntax", "python"]
    if debug:
        command += ["--debug-dir", str(debug)]
    built = subprocess.run(command, capture_output=True, text=True, timeout=600, env=env)
    return built, exe


class GridBoundsTests(unittest.TestCase):
    def check_oracle(self, text, name, runs):
        """For every argument list: same stdout and the same success as CPython in every IR mode, and
        (on the IR modes) CPython's last stderr line. Returns CPython's results."""
        expected = [subprocess.run([sys.executable, "-c", text, *args], capture_output=True, text=True, timeout=120)
                    for args in runs]
        last = lambda text_: text_.strip().splitlines()[-1] if text_.strip() else ""
        with tempfile.TemporaryDirectory() as directory:
            for ir in ("0", "1", "verify"):
                built, exe = compile_exe(directory, text, name, ir)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                for args, want in zip(runs, expected):
                    with self.subTest(ir=ir, args=args):
                        ran = subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=120)
                        self.assertEqual(ran.stdout, want.stdout)
                        self.assertEqual(ran.returncode != 0, want.returncode != 0, ran.stderr)
                        if ir != "0" and want.returncode:
                            self.assertEqual(last(ran.stderr), last(want.stderr), (ir, args))
        return expected

    def c_of(self, text, name):
        with tempfile.TemporaryDirectory() as directory:
            debug = Path(directory, "dbg")
            stats = Path(directory, "stats.jsonl")
            built, _exe = compile_exe(directory, text, name, "1", debug, stats)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            rows = {json.loads(l)["fn"]: json.loads(l) for l in stats.read_text().splitlines()}
            return (debug / "program.c").read_text(), rows

    def test_bytearray_grid_matches_cpython(self):
        res = self.check_oracle(GRID, "grid", (("7", "5", "0", "0"), ("1", "1", "0", "0"), ("16", "3", "0", "0"),
                                               ("7", "5", "3", "0"), ("7", "5", "0", "2")))
        self.assertEqual([r.returncode == 0 for r in res], [True, True, True, False, False])
        self.assertIn("IndexError", res[3].stderr)
        self.assertIn("IndexError", res[4].stderr)

    def test_bytearray_grid_runs_unchecked(self):
        c, rows = self.c_of(GRID, "grid")
        self.assertEqual(rows["main"]["path"], "ir", rows["main"].get("reason"))
        self.assertGreaterEqual(rows["main"]["passes"]["versioned"], 1)
        body = c[c.index("int64_t py_main(void) {"):]
        body = body[:body.index("\n}\n")]
        # cur and nxt read and written through spans, unchecked, in the fast copy of the sweep
        self.assertRegex(body, r"\(\(int64_t\)ir\d+_p\[ir\d+\]\)")
        self.assertRegex(body, r"ir\d+_p\[ir\d+\] = \(unsigned char\)")
        # one span of cur per sweep, not one per read
        spans = re.findall(r"ail_bytearray_meta\((ir\d+)\); unsigned char \*", body)
        self.assertLessEqual(len(spans), 4, spans)

    def test_list_grid_with_explicit_wrap_guards_matches_cpython(self):
        res = self.check_oracle(GUARDS, "guards", (("6", "4", "0"), ("1", "1", "0"), ("2", "9", "0"), ("6", "4", "5")))
        self.assertEqual([r.returncode == 0 for r in res], [True, True, True, False])

    def test_list_grid_with_explicit_wrap_guards_is_versioned_symbolically(self):
        c, rows = self.c_of(GUARDS, "guards")
        self.assertGreaterEqual(rows["main"]["passes"]["versioned"], 1)
        # the guard compares w*h-based bounds with the length (not a constant from the range pass)
        self.assertNotIn("16777215LL", c)

    def test_tables_changed_through_calls_negative_divisors_and_byte_values(self):
        res = self.check_oracle(TABLES, "tables", (("5", "5", "0", "1"), ("5", "5", "9", "1"), ("5", "-3", "0", "1"),
                                                   ("5", "5", "0", "299"), ("5", "2", "1", "0")))
        self.assertEqual([r.returncode == 0 for r in res], [True, False, True, False, True])
        self.assertIn("IndexError", res[1].stderr)          # xl[0] = 9 reaches past the last row
        self.assertIn("ValueError", res[3].stderr)          # a byte value of 299

    def test_a_loop_that_extends_the_bytearray_it_reads(self):
        self.check_oracle(EXTEND, "extend", (("2",), ("5",), ("9",)))


if __name__ == "__main__":
    unittest.main()
