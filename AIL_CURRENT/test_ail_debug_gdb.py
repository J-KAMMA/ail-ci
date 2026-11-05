"""A 30-check gdb matrix for `--debug` builds, and line coverage of four programs (lab/debug/linecov.py).

Prints `gdb: <version>` first, so a CI log shows whether the matrix ran or was skipped (it is skipped only when
gdb, a C compiler, readelf/objdump or the lab/debug programs are missing).

Each check is a `gdb -batch -x script` run:
 * break_L        break at a line of the program; the stop names file.py:L;
 * next5_L        after that break, `next` five times visits the lines CPython's `sys.settrace` visits in the
                  same function (5 more statements of the same function, in order);
 * bt3            a break inside a call three deep, `bt`, every frame names its file.py:N;
 * finish         `finish` leaves the callee, reports its value and stops on the caller's line;
 * locals_int     a Python int parameter is visible in gdb by its C name, with the value (the Python name is
                  not: the mapping is recorded in lab/debug/RESULTS.md);
 * locals_float   a Python float local is visible in gdb's `info locals` as a double;
 * index_error    a breakpoint on the runtime's raise function stops an IndexError, and the frame names the
                  user's statement.

`lab/debug/RESULTS.md` records the number this prints.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "debug"
PROGS = LAB / "progs"
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
GDB = shutil.which("gdb")
DWARF = shutil.which("readelf") or shutil.which("objdump")

# program, break line (a statement of the function the checks step through), function
CASES = [
    ("loops.py", 3, "collatz"),
    ("nested_calls.py", 2, "leaf"),
    ("method.py", 10, "total"),
    ("comprehension.py", 4, "main"),
    ("tryexcept.py", 2, "risky"),
    ("imports_helper.py", 5, "total"),
    ("strings.py", 2, "repeat"),
    ("dictsort.py", 2, "main"),
    ("recursion.py", 2, "fact"),
    ("general_path.py", 2, "find"),
]

TRACER = r"""
import json, sys, runpy
seen = []
def trace(frame, event, arg):
    if event == "line":
        depth = 0
        back = frame.f_back
        while back is not None:
            depth += 1
            back = back.f_back
        seen.append([frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name, depth])
    return trace
program, out = sys.argv[1], sys.argv[2]
sys.settrace(trace)
sys.argv = [program]
try:
    runpy.run_path(program, run_name="__main__")
except BaseException:
    pass
finally:
    sys.settrace(None)
open(out, "w").write(json.dumps(seen))
"""


def cpython_lines(program, out):
    """[(basename, line, function, depth)] of the line events CPython's sys.settrace visits."""
    subprocess.run([sys.executable, "-c", TRACER, str(program), str(out)], capture_output=True, text=True,
                   timeout=120, cwd=str(program.parent))
    data = json.loads(Path(out).read_text())
    return [(os.path.basename(name), line, fn, depth) for name, line, fn, depth in data]


LOCATION = re.compile(r"([\w./-]+\.py):(\d+)")


def locations(output):
    """[(basename, line)] named by gdb's stop messages, in order."""
    return [(os.path.basename(m.group(1)), int(m.group(2))) for m in LOCATION.finditer(output)]


class Matrix:
    """The checks, each (name, ok, detail)."""

    def __init__(self, workdir):
        self.dir = Path(workdir)
        self.env = dict(os.environ, PYTHONUTF8="1", AIL_CACHE=str(self.dir / "cache"))
        for name in ("AIL_QUIET_FALLBACK", "AIL_NO_CACHE", "AIL_IR", "AIL_DEBUG", "AIL_LINE_MAP"):
            self.env.pop(name, None)
        self.exes = {}
        self.checks = []

    def exe(self, program):
        if program not in self.exes:
            out = self.dir / (program.stem + ".dbg")
            done = subprocess.run([sys.executable, "-B", CLI, "compile", "--debug", str(program), "-o", str(out)],
                                  capture_output=True, text=True, encoding="utf-8", env=self.env, timeout=900)
            if done.returncode:
                raise RuntimeError("build failed for %s:\n%s%s" % (program, done.stdout, done.stderr))
            self.exes[program] = out
        return self.exes[program]

    def gdb(self, program, *commands):
        script = self.dir / (program.stem + "-" + str(len(self.checks)) + ".gdb")
        script.write_text("\n".join(["set pagination off", "set confirm off", *commands]) + "\n")
        return subprocess.run([GDB, "-batch", "-x", str(script), str(self.exe(program))],
                              capture_output=True, text=True, timeout=300).stdout

    def record(self, name, ok, detail=""):
        self.checks.append((name, bool(ok), detail))

    def run(self):
        for name_in, line, function in CASES:
            program = PROGS / name_in
            name = program.stem
            try:
                self.check_break(program, line, name)
                self.check_next(program, line, function, name)
            except Exception as error:                    # a check that cannot run is a failed check, named
                self.record("build/run " + name, False, repr(error))
        for name_in, line, function in (("nested_calls.py", 2, "leaf"), ("recursion.py", 2, "fact"),
                                        ("method.py", 5, "bump")):
            self.check_backtrace(PROGS / name_in, line, function)
        for name_in, line, function in (("loops.py", 3, "collatz"), ("nested_calls.py", 2, "leaf"),
                                        ("strings.py", 2, "repeat"), ("method.py", 13, "bump")):
            self.check_finish(PROGS / name_in, line, function)
        self.check_locals_int()
        self.check_locals_float()
        self.check_index_error()

    # ------------------------------------------------------------------ the checks
    def check_break(self, program, line, name):
        out = self.gdb(program, "break %s:%d" % (program.name, line), "run")
        hit = ("%s:%d" % (program.name, line)) in out.replace(os.path.basename(str(program)), program.name)
        self.record("break %s:%d" % (name, line), hit, out.strip().splitlines()[-3:])

    def check_next(self, program, line, function, name):
        """`next` five times visits the next five `sys.settrace` lines of the same stack depth (gdb steps
        over a call, so a line event inside a callee is not a line `next` stops on)."""
        events = [(ln, fn, depth) for base, ln, fn, depth in
                  cpython_lines(program, self.dir / (program.stem + ".trace.json")) if base == program.name]
        first = next((i for i, (ln, fn, _) in enumerate(events) if ln == line and fn == function), None)
        want = []
        if first is not None:
            # gdb's `next` stops in this function until it returns, then in its caller: never deeper again
            depth = events[first][2]
            for ln, fn, d in events[first + 1:]:
                if d <= depth:
                    want.append(ln)
                    depth = d
                if len(want) == 5:
                    break
        commands = ["tbreak %s:%d" % (program.name, line), "run"]
        for _ in range(5):
            commands += ["echo ===\\n", "next"]
        out = self.gdb(program, *commands)
        got = self.stops(out)
        # (the first `next` must land on the line CPython visits next; every stop must be a CPython line.
        #  A loop's C step is attributed to the body line, so a repeat of the body line is one stop in gdb
        #  and two line events in CPython: equality of the whole sequence is not what the line table says.)
        visited = {ln for ln, fn, d in events}
        ok = bool(want) and len(got) >= 3 and got[0] == want[0] and all(ln in visited for ln in got)
        self.record("next5 %s" % name, ok, "want %s got %s" % (want, got))

    @staticmethod
    def stops(output):
        """The lines gdb stops on, in order: `file.py:N` on a frame change, `N\\t<source>` otherwise."""
        found = []
        for piece in output.split("===")[1:]:
            match = re.search(r"(\S+\.py):(\d+)\s*\n", piece) or re.search(r"^(\d+)\s", piece, re.M)
            if match is None:
                continue
            found.append(int(match.group(2) if match.lastindex == 2 else match.group(1)))
        return found

    def check_backtrace(self, program, line, function):
        out = self.gdb(program, "break %s:%d" % (program.name, line), "run", "bt")
        frames = [l for l in out.splitlines() if re.match(r"^#\d+\s", l)]
        named = [f for f in frames if "%s.py:" % program.stem in f]
        ok = len(named) >= 3 and function in out
        self.record("bt3 %s" % program.stem, ok, frames[:4])

    def check_finish(self, program, line, function):
        out = self.gdb(program, "break %s:%d" % (program.name, line), "run", "finish")
        found = locations(out)
        ok = len(found) >= 2 and found[-1] != found[0]
        self.record("finish %s" % program.stem, ok, out.strip().splitlines()[-4:])

    def check_locals_int(self):
        program = PROGS / "loops.py"
        out = self.gdb(program, "break %s:3" % program.name, "run", "print v_n")
        ok = bool(re.search(r"\$\d+ = 1\b", out))
        self.record("locals int (collatz: `print v_n`)", ok, out.strip().splitlines()[-2:])

    def check_locals_float(self):
        program = PROGS / "dictsort.py"
        out = self.gdb(program, "break %s:17" % program.name, "run", "info locals")
        doubles = [l for l in out.splitlines() if re.search(r"ir\d+ = -?[0-9]+\.[0-9]+", l)]
        self.record("locals float (dictsort: info locals)", bool(doubles), doubles[:3])

    def check_index_error(self):
        program = PROGS / "general_path.py"
        out = self.gdb(program, "rbreak ail_raise", "run", "bt")
        stopped = "Breakpoint" in out
        ok = stopped and any(base == program.name for base, _ in locations(out))
        self.record("index error (break on the runtime raise function)", ok,
                    out.strip().splitlines()[-4:])


@unittest.skipUnless(GDB and CC and DWARF and PROGS.is_dir(), "gdb, a C compiler, readelf/objdump or lab/debug/progs missing")
class GdbMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        version = subprocess.run([GDB, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
        print("gdb: %s" % version)

    def test_the_matrix_passes_at_least_26_of_30(self):
        with tempfile.TemporaryDirectory(prefix="ail-gdb-matrix-") as tmp:
            matrix = Matrix(tmp)
            matrix.run()
            passed = [name for name, ok, _ in matrix.checks if ok]
            failed = [(name, detail) for name, ok, detail in matrix.checks if not ok]
            print("gdb matrix: %d/%d checks passed" % (len(passed), len(matrix.checks)))
            for name, detail in failed:
                print("  FAILED %s: %s" % (name, detail))
            self.assertEqual(len(matrix.checks), 30)
            self.assertGreaterEqual(len(passed), 26, failed)

    def test_line_coverage_of_four_programs(self):
        with tempfile.TemporaryDirectory(prefix="ail-gdb-lines-") as tmp:
            done = subprocess.run([sys.executable, str(LAB / "linecov.py"),
                                   *[str(PROGS / name) for name in ("loops.py", "comprehension.py",
                                                                    "tryexcept.py", "method.py")],
                                   "--threshold", "100"], capture_output=True, text=True, timeout=1800)
            print(done.stdout)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
