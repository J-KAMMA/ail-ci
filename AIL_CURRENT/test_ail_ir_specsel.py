"""Speculative selects (ir/passes/specsel.py, design IR_OWNERSHIP_DESIGN_v2.md section 22).

A cheap, effect-free `if` on loaded data inside a loop becomes straight-line code and selects (scar_life's
cell update). The checks:

* results equal CPython's in AIL_IR=0, 1 and verify (the IR printed, parsed and re-verified), for the
  scar_life shape (nested ifs, rule lists in struct fields, two counters), a float list, negative indices
  (Python's wrap-around still applies to a speculated read) and a `sub` counter;
* a speculated read whose index is out of range while its arm is not taken does not fail, and one whose
  arm is taken fails with IndexError exactly as before (nothing printed after it);
* a checked add in an arm is exact exactly when its arm runs: tagged ints make an overflow a big-int value,
  not a stop, and specsel leaves the tint adds alone;
* the pass fires on the scar_life shape and leaves alone: an arm with a call, an arm that writes a list,
  a test of locals only, an if outside any loop, an `and`/`or` test, and an arm whose checked add comes
  before an element read (its OverflowError must stay first).

Programs are ordinary Python (`--syntax python`): CPython is the oracle.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CELLS = '''
class Rule:
    def __init__(self, b: list[int], s: list[int]):
        self.b = b
        self.s = s


class Grid:
    def __init__(self, nxt: list[int]):
        self.nxt = nxt


def step(cur: list[int], gr: Grid, ru: Rule, w: int, h: int) -> int:
    alive = 0
    scars = 0
    for y in range(h):
        up = ((y + h - 1) % h) * w
        mid = y * w
        dn = ((y + 1) % h) * w
        for x in range(w):
            l = (x + w - 1) % w
            r = (x + 1) % w
            wt = 2 * ((cur[up + x] == 1) + (cur[dn + x] == 1) + (cur[mid + l] == 1) + (cur[mid + r] == 1)) \\
                + (cur[up + l] == 1) + (cur[up + r] == 1) + (cur[dn + l] == 1) + (cur[dn + r] == 1)
            s = cur[mid + x]
            v = 0
            if s == 1:
                if ru.s[wt] == 1:
                    v = 1
                    alive += 1
                else:
                    v = 2
                    scars -= 1
            elif s == 0:
                if ru.b[wt] == 1:
                    v = 1
                    alive += 1
            gr.nxt[mid + x] = v
    return alive * 1000000 - scars


def fpick(xs: list[float], ks: list[int]) -> float:
    t = 0.0
    for i in range(len(ks)):
        v = 0.5
        if ks[i] != 0:
            v = xs[ks[i]]
        t = t * 0.5 + v
    return t


def main() -> int:
    # (`list(range(...))`, not list literals: a literal in main makes the whole program fall back to the
    # general path, where the specsel C arm this module pins is not emitted)
    ru = Rule(list(range(13)), list(range(13)))
    gr = Grid(list(range(16)))
    print(step(list(range(16)), gr, ru, 4, 4))
    return 0


main()
'''

# the speculated read `ru.s[wt]` is out of range while its arm is not taken (s != 1); then it is taken
GUARD = '''
import sys


class Rule:
    def __init__(self, s: list[int], e: list[int]):
        self.s = s
        self.e = e


def scan(cells: list[int], ws: list[int], ru: Rule) -> int:
    n = 0
    for i in range(len(cells)):
        r = 0
        if cells[i] == 1:
            if ru.s[ws[i]] == 1:
                r = 1
                n += 1
        elif cells[i] == 2:
            if ru.e[ws[i]] == 1:
                r = 2
                n -= 1
        print(i, r)
    return n


def main() -> int:
    ru = Rule([0, 1, 1], [])
    # boundaries while the read's arm is not taken: len, -len - 1, both ends of int64, an empty list
    print("ok", scan([0, 1, 0, 1, 0, 1, 0, 0], [3, -3, -4, -1, 9223372036854775807, 2, -9223372036854775807, 0], ru))
    mode = int(sys.argv[1])
    if mode == 0:
        print("fail", scan([0, 1, 1], [3, 2, 3], ru))
    elif mode == 1:
        print("fail", scan([1, 1], [0, -4], ru))
    else:
        print("fail", scan([0, 2], [1, 0], ru))
    print("unreachable")
    return 0


main()
'''

OVERFLOW = '''
def bump(xs: list[int], start: int) -> int:
    c = start
    for i in range(len(xs)):
        if xs[i] == 1:
            c += 1
        else:
            c = c
    return c


def main() -> int:
    big = 9223372036854775805
    print(bump([0, 0, 1, 0, 1], big))
    try:
        print(bump([1, 0, 1, 1, 0], big))
    except OverflowError:
        print("overflow")
    print(bump([0, 0, 0, 0], 9223372036854775807))
    return 0


main()
'''
# add and sub in one position, `K - x` (not commutative), a three-way nest, a negative amount
EDGES = '''
def mix(xs: list[int]) -> int:
    a = 0
    b = 100
    c = 9
    for i in range(len(xs)):
        if xs[i] == 1:
            a += 3
            b -= 2
        elif xs[i] == 2:
            a -= 5
        else:
            b = 7 - b
        if xs[i] >= 2:
            c += -4
        else:
            c = c
        if xs[i] == 3:
            a = a - 1
        else:
            a = a + 2
    return a * 1000000 + b * 1000 + c


def main() -> int:
    print(mix([1, 2, 3, 0, 1, 1, 2, 3, 3, 0, 2]))
    print(mix([]))
    return 0


main()
'''

# AIL's int is int64 (OverflowError where CPython grows): the expected text is AIL's, in every mode
OVERFLOW_EXPECTED = "9223372036854775807\n9223372036854775808\n9223372036854775807\n"

# one function per shape; the pass must fire in `fires` only
SHAPES = '''
def note(x: int) -> int:
    print("note", x)
    return x


def fires(xs: list[int], ys: list[int]) -> int:
    a = 0
    b = 0
    for i in range(len(xs)):
        if xs[i] == 1:
            if ys[i] > 0:
                a += 1
            else:
                b += 1
    return a * 100 + b


def calls(xs: list[int]) -> int:
    a = 0
    for i in range(len(xs)):
        v = 0
        if xs[i] == 1:
            v = note(i)
        a += v
    return a


class Box:
    def __init__(self, ys: list[int]):
        self.ys = ys


def writes(xs: list[int], bx: Box) -> int:
    a = 0
    for i in range(len(xs)):
        v = 0
        if xs[i] == 1:
            bx.ys[i] = 5
            v = 2
        a += v
    return a


def locals_only(n: int) -> int:
    a = 0
    for i in range(n):
        v = 1
        if i > 3:
            v = 2
        a += v
    return a


def no_loop(xs: list[int]) -> int:
    v = 1
    if xs[0] == 1:
        v = xs[1]
    return v


def short(xs: list[int]) -> int:
    a = 0
    for i in range(len(xs)):
        if xs[i] < 0 or xs[i] > 5:
            a += 1
    return a


def add_first(xs: list[int], ys: list[int]) -> int:
    a = 0
    for i in range(len(xs)):
        v = 0
        w = a
        if xs[i] == 1:
            w = a + 1
            v = ys[i]
        a = w + v
    return a


def main() -> int:
    xs = [1, 0, 1, 1, 0, 1]
    ys = [3, -1, 0, 2, 5, 7]
    bx = Box([0, 0, 0, 0, 0, 0])
    print(fires(xs, ys), calls(xs), writes(xs, bx), locals_only(9), no_loop(xs), short(ys), add_first(xs, ys))
    print(bx.ys)
    return 0


main()
'''


def compile_exe(directory, text, name, ir, stats=None, env_extra=None):
    source = Path(directory, name + ".ail")
    source.write_text(text)
    exe = Path(directory, "%s_%s" % (name, ir))
    env = dict(os.environ, AIL_IR=ir, **(env_extra or {}))
    env.pop("AIL_IR_STATS", None)
    env.pop("AIL_IR_PASSES", None)
    env["AIL_NO_CACHE"] = "1"       # a cache hit would not write the stats
    if stats:
        env["AIL_IR_STATS"] = str(stats)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source), "-o", str(exe),
                            "--syntax", "python"], capture_output=True, text=True, timeout=600, env=env)
    return built, exe


class SpecSelectTests(unittest.TestCase):
    def check_oracle(self, text, name, runs=((),)):
        """CPython's stdout and success for each argument list in `runs`, in every IR mode; CPython's results."""
        results = []
        with tempfile.TemporaryDirectory() as directory:
            expected = [subprocess.run([sys.executable, "-c", text, *args], capture_output=True, text=True, timeout=120)
                        for args in runs]
            for ir in ("0", "1", "verify"):
                built, exe = compile_exe(directory, text, name, ir)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                for args, want in zip(runs, expected):
                    with self.subTest(ir=ir, args=args):
                        ran = subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=120)
                        self.assertEqual(ran.stdout, want.stdout)
                        self.assertEqual(ran.returncode != 0, want.returncode != 0, ran.stderr)
        return expected[0] if len(expected) == 1 else expected

    def stats(self, text, name):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "stats.jsonl")
            built, _exe = compile_exe(directory, text, name, "1", path)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        return {r["fn"]: r for r in rows}

    def test_cell_update_matches_cpython(self):
        self.check_oracle(CELLS, "cells")

    def test_cell_update_is_flattened(self):
        rows = self.stats(CELLS, "cells")
        self.assertEqual(rows["step"]["path"], "ir")
        self.assertGreaterEqual(rows["step"]["passes"].get("specsel", 0), 3)
        self.assertGreaterEqual(rows["fpick"]["passes"].get("specsel", 0), 1)

    def test_out_of_range_read_fails_only_when_its_arm_runs(self):
        for expected in self.check_oracle(GUARD, "guard", (("0",), ("1",), ("2",))):
            self.assertNotEqual(expected.returncode, 0)
            self.assertIn("IndexError", expected.stderr)
            self.assertIn("ok", expected.stdout)
            self.assertNotIn("unreachable", expected.stdout)
        self.assertGreaterEqual(self.stats(GUARD, "guard")["scan"]["passes"].get("specsel", 0), 1)

    def test_mixed_adds_and_subs_match_cpython(self):
        self.check_oracle(EDGES, "edges")
        # tagged ints make the adds/subtractions exact (tint ops), which specsel does not flatten
        self.assertEqual(self.stats(EDGES, "edges")["mix"]["path"], "ir")

    def test_checked_add_overflows_exactly_when_its_arm_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            for ir in ("0", "1", "verify"):
                with self.subTest(ir=ir):
                    # the exact (tagged-int) build: the overflow becomes CPython's big int, not a stop
                    built, exe = compile_exe(directory, OVERFLOW, "overflow", ir,
                                             env_extra={"AIL_UNIFIED_FORCE": "1"})
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
                    self.assertEqual((ran.returncode, ran.stdout), (0, OVERFLOW_EXPECTED), ran.stderr)
        self.assertEqual(self.stats(OVERFLOW, "overflow")["bump"]["path"], "ir")

    def test_pass_fires_only_where_safe_and_worth_it(self):
        self.check_oracle(SHAPES, "shapes")
        rows = self.stats(SHAPES, "shapes")
        self.assertGreaterEqual(rows["fires"]["passes"].get("specsel", 0), 1)
        for fn in ("calls", "writes", "locals_only", "no_loop", "short", "add_first"):
            with self.subTest(fn=fn):
                self.assertEqual(rows[fn]["path"], "ir", rows[fn].get("reason"))
                self.assertNotIn("specsel", rows[fn]["passes"])

    def test_pass_can_be_switched_off(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "cells.ail")
            source.write_text(CELLS)
            c_text = []
            for passes in (None, "mem2reg,simplify,ranges,licm,window"):
                env = dict(os.environ, AIL_IR="1")
                env.pop("AIL_IR_PASSES", None)
                if passes:
                    env["AIL_IR_PASSES"] = passes
                debug = Path(directory, "d%d" % len(c_text))
                built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                        "-o", str(Path(directory, "e%d" % len(c_text))), "--syntax", "python",
                                        "--debug-dir", str(debug)], capture_output=True, text=True, timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                c_text.append((debug / "program.c").read_text())
            self.assertIn("__builtin_expect((uint64_t)(", c_text[0])
            self.assertNotIn("(0 - (uint64_t)(", c_text[1])


if __name__ == "__main__":
    unittest.main()
