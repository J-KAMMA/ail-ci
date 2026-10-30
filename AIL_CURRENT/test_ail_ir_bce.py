"""Check elimination in the IR (ir/passes/tintnarrow.py, the narrowing step of ir/passes/ranges.py, the loop-versioning
fix in ir/passes/licm.py).

* every program of bce_cases/ runs in the default build, in AIL_IR=verify (the IR printed, parsed and re-verified) and in
  AIL_UNIFIED_FORCE=1 with the same stdout, exit status and last stderr line as CPython. They cover what a removed check
  must never change: the last iteration, a list that shrinks, grows, is cleared or slice-assigned inside the loop,
  aliasing, negative indexes, a loop variable that leaves int64, big ints from input, and sums that overflow int64;
* `while k < full: ... k += 16` (the lane loop of ta.dot) is compiled with a plain int64 `k` (tint_demoted > 0) and every
  function of the cases stays on the IR path (a loop-versioning bug once made the IR of a kernel invalid, and the
  function silently went back to the legacy emitter);
* a tagged value that does not provably fit int64 stays tagged: its exact result is printed.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "bce_cases"
NAMES = sorted(p.stem for p in CASES.glob("p*.py"))
STDIN = {"p06_input_big": "1 2 9223372036854775807 -9223372036854775808 123456789012345678901234567890\n"}


def compile_exe(directory, source, ir="1", stats=None, extra=None):
    exe = Path(directory, "%s_%s_%s" % (source.stem, ir, "u" if extra else "d"))
    env = dict(os.environ, AIL_IR=ir, AIL_NO_CACHE="1", **(extra or {}))
    env.pop("AIL_IR_STATS", None)
    env.pop("AIL_IR_PASSES", None)
    if stats:
        env["AIL_IR_STATS"] = str(stats)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source), "-o", str(exe),
                            "--syntax", "python"] + (["--no-cache"] if stats else []), capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def last_line(text):
    lines = text.strip().splitlines()
    return lines[-1] if lines else ""


class CheckEliminationTests(unittest.TestCase):
    def oracle(self, name, ir, extra=None):
        source = CASES / (name + ".py")
        stdin = STDIN.get(name, "")
        want = subprocess.run([sys.executable, str(source)], input=stdin, capture_output=True, text=True, timeout=120)
        with tempfile.TemporaryDirectory() as directory:
            built, exe = compile_exe(directory, source, ir, extra=extra)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.stdout, want.stdout)
        self.assertEqual(ran.returncode, want.returncode, ran.stderr)
        self.assertEqual(last_line(ran.stderr), last_line(want.stderr))

    def test_cases_match_cpython_default_build(self):
        for name in NAMES:
            with self.subTest(case=name):
                self.oracle(name, "1")

    def test_cases_match_cpython_verified_ir(self):
        for name in NAMES:
            with self.subTest(case=name):
                self.oracle(name, "verify")

    def test_cases_match_cpython_unified_forced(self):
        for name in NAMES:
            with self.subTest(case=name):
                self.oracle(name, "1", {"AIL_UNIFIED_FORCE": "1"})

    def stats(self, name):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "stats.jsonl")
            built, _exe = compile_exe(directory, CASES / (name + ".py"), "1", path)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        return {r["fn"]: r for r in rows}

    def test_lane_loop_gets_a_plain_int64_index(self):
        rows = self.stats("p09_lane_shape")
        self.assertEqual(rows["lanes"]["path"], "ir", rows["lanes"])
        self.assertGreater(rows["lanes"]["passes"].get("tint_demoted", 0), 0, rows["lanes"])

    def test_loop_versioning_keeps_functions_on_the_ir_path(self):
        for name in ("p07_version_tail", "p01_last_iter", "p09_lane_shape"):
            rows = self.stats(name)
            for fn, row in rows.items():
                if fn.startswith("_ail_") or fn == "main":
                    continue
                with self.subTest(case=name, fn=fn):
                    self.assertEqual(row["path"], "ir", row)

    def test_matmul_kernel_stays_on_the_ir_path(self):
        # the "tail skipped" shape of the kernel once made loop versioning leave a stale yield: the verifier rejected the
        # function and it went back to the legacy emitter (20x the instructions)
        rows = self.stats("q10_matmul")
        self.assertEqual(rows["_ail_tam_mmk"]["path"], "ir", rows["_ail_tam_mmk"])


if __name__ == "__main__":
    unittest.main()
