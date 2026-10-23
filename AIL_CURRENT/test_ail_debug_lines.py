"""`ail build --debug` on the default (IR) typed path, and on the general path: C maps back to the user's lines.

`--debug` used to force AIL_IR=0 (the legacy lowering) to get `#line` directives, so a debug build ran a different
code generator from the shipped one. Now:

* the IR lowering records the statement each instruction came from (ir.SRC, not Instr.attrs: no pass and no
  printed text sees it) and ir/emit_c.py writes `AIL_DBG_SITE` and, before *every* C line of the statement, `#line`
  (the directive numbers the line after it, so one per statement left the second C line of a statement on N+1);
* the general path (pyboxed2.py) does the same per statement (no "raised near" report there);
* pyc's script rewrite unparses the program and the text parsed again renumbered the lines (one blank line between
  functions): the second function's statements mapped one line too early. The lines are restored (debug only);
* a release build is byte-for-byte what it was (no `#line`, no AIL_DBG_SITE); a debug build's C differs from the
  release C by those two kinds of line only (checked here with --debug-dir).

Needs a C compiler (skipped without one). The crash site is read from gdb (`break ail_die`, `bt`) when it is
installed, else from objdump's source-annotated disassembly (the call to the division helper must sit under the
user's line).
"""
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
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

# two functions, the crash in the second one after a double blank line (the renumbering case)
DIVIDE = """def double(n: int) -> int:
    return n * 2


def avg(total: int, n: int) -> int:
    scaled = double(total)
    return scaled // n


def main() -> None:
    acc = 0
    for v in [4, 2, 0]:
        acc += avg(100, v)
        print(acc)


main()
"""
# a script (top-level statements): leading blank lines, a comment, a function, then statements
SCRIPT = """

# a script
def helper(n: int) -> int:
    return 100 // n



total = 0
for i in range(3, -1, -1):
    total += helper(i)
    print(total)
"""
INDEX = """def pick(rows: list[list[int]], k: int) -> int:
    t = 0
    for r in rows:
        t += r[k]
    return t


def main() -> None:
    rows = [[1, 2, 3], [4, 5, 6]]
    print(pick(rows, 2))
    print(pick(rows, 3))


main()
"""
GENERAL = """def find(d: dict[int, int], k: int) -> int | None:
    return d.get(k)


def main() -> None:
    print(find({1: 2}, 1))
    xs = [1, 2, 3]
    i = 5
    print(xs[i])


main()
"""


def objdump_calls(exe, callee):
    """[(source line, file)] of the `call <callee>` instructions under objdump -dl's source labels."""
    text = subprocess.run(["objdump", "-dl", "--no-show-raw-insn", str(exe)], capture_output=True, text=True,
                          timeout=120).stdout
    found, here = [], None
    for line in text.splitlines():
        label = re.match(r"^(/\S+|[\w./-]+\.py):(\d+)(?: \(discriminator \d+\))?$", line)
        if label:
            here = (int(label.group(2)), label.group(1))
        elif re.search(r"\bcall\s+\w+\s+<%s>" % re.escape(callee), line):
            found.append(here)
    return found


def dwarf_lines(exe, name):
    text = subprocess.run(["objdump", "--dwarf=decodedline", str(exe)], capture_output=True, text=True,
                          timeout=120).stdout
    return {int(m.group(1)) for m in re.finditer(r"^%s\s+(\d+)\s" % re.escape(name), text, re.M)}


@unittest.skipUnless(CC, "no C compiler")
class DebugLines(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-debug-lines-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ, AIL_CACHE=str(self.dir / "cache"), PYTHONUTF8="1")
        for name in ("AIL_QUIET_FALLBACK", "AIL_NO_CACHE", "AIL_IR", "AIL_DEBUG", "AIL_LINE_MAP"):
            self.env.pop(name, None)

    def source(self, text, name="prog.py"):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def compile(self, source, output, *flags, env=None):
        done = subprocess.run([sys.executable, "-B", CLI, "compile", *flags, str(source), "-o", str(output)],
                              capture_output=True, text=True, encoding="utf-8", env=env or self.env, timeout=900)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done

    def run_exe(self, exe):
        return subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8", timeout=120)

    def cpython(self, source):
        return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, encoding="utf-8",
                              timeout=120)

    def paths(self, source, *flags):
        """{function: 'ir' | 'legacy'} of a build (AIL_IR_STATS)."""
        stats = self.dir / "stats.json"
        stats.unlink(missing_ok=True)
        self.compile(source, self.dir / "stats.exe", *flags,
                     env=dict(self.env, AIL_IR_STATS=str(stats), AIL_NO_CACHE="1"))
        (self.dir / "stats.exe").unlink()
        return {row["fn"]: row["path"] for row in map(json.loads, stats.read_text().splitlines())}

    def crash_line(self, source):
        """The line CPython's traceback names for the program."""
        done = self.cpython(source)
        self.assertNotEqual(done.returncode, 0)
        return int(re.findall(r'line (\d+)', done.stderr)[-1])

    # ------------------------------------------------------------------------------------------ the IR path
    def test_debug_build_uses_the_ir_not_the_legacy_lowering(self):
        source = self.source(DIVIDE)
        self.assertTrue(all(path == "ir" for path in self.paths(source, "--debug").values()))
        self.assertEqual(self.paths(source, "--debug"), self.paths(source))

    def test_the_crash_names_the_users_line(self):
        for text, name in ((DIVIDE, "divide.py"), (INDEX, "index.py"), (SCRIPT, "script.py")):
            with self.subTest(name):
                source = self.source(text, name)
                expected = self.crash_line(source)
                self.compile(source, self.dir / "debug", "--debug")
                done = self.run_exe(self.dir / "debug")
                self.assertEqual(done.returncode, 1)
                self.assertEqual(done.stdout, self.cpython(source).stdout)
                self.assertEqual(done.stderr.splitlines()[1], "  raised near %s:%d" % (source, expected), done.stderr)
                (self.dir / "debug").unlink()

    def test_debugger_and_line_table_point_at_the_users_line(self):
        source = self.source(DIVIDE, "divide.py")
        self.compile(source, self.dir / "debug", "--debug")
        if shutil.which("gdb"):
            done = subprocess.run(["gdb", "-batch", "-ex", "break ail_die", "-ex", "run", "-ex", "bt",
                                   str(self.dir / "debug")], capture_output=True, text=True, timeout=120)
            self.assertRegex(done.stdout, r"divide\.py:7\b")
            return
        if not shutil.which("objdump"):
            self.skipTest("neither gdb nor objdump is installed")
        calls = objdump_calls(self.dir / "debug", "pydiv")
        self.assertIn(7, [line for line, _ in calls], calls)       # `return scaled // n`
        self.assertTrue(all(name.endswith("divide.py") for line, name in calls if line == 7), calls)
        lines = dwarf_lines(self.dir / "debug", "divide.py")
        self.assertEqual(sorted(lines), [2, 6, 7, 12, 13, 14, 17])      # no statement on a neighbouring line

    def test_the_second_c_line_of_a_statement_keeps_its_line(self):
        # `xs = [..]` is several C lines (free, push, push, ...): none may fall on the next source line
        source = self.source("def f(n: int) -> int:\n    xs = [1, 2, 3]\n    return xs[n]\n\n\n"
                             "def main() -> None:\n    print(f(1))\n\n\nmain()\n", "multi.py")
        out = self.dir / "dbg"
        self.compile(source, out, "--debug", "--debug-dir", str(self.dir / "d"))
        text = (self.dir / "d" / "program.c").read_text()
        body = text[text.index("int64_t f(int64_t v_n)"):]
        body = body[:body.index("\n}\n")]
        after = re.findall(r'#line (\d+) "[^"]*multi\.py"\n([^\n#]*)', body)
        for number, code in after:
            if "ail_list_push" in code:
                self.assertEqual(number, "2", code)

    # ------------------------------------------------------------------------------------ the cost
    def test_release_has_no_directives_and_debug_differs_by_them_alone(self):
        for text, name in ((DIVIDE, "divide.py"), (INDEX, "index.py"), (GENERAL, "general.py")):
            with self.subTest(name):
                source = self.source(text, name)
                self.compile(source, self.dir / "rel", "--debug-dir", str(self.dir / "rel_c"))
                self.compile(source, self.dir / "dbg", "--debug", "--debug-dir", str(self.dir / "dbg_c"))
                release = (self.dir / "rel_c" / "program.c").read_text()
                debug = (self.dir / "dbg_c" / "program.c").read_text()
                self.assertNotIn("#line", release)
                self.assertNotIn("AIL_DBG_SITE(\"", release)
                self.assertIn("#line", debug)
                stripped = "\n".join(line for line in debug.splitlines()
                                     if not line.startswith("#line") and 'AIL_DBG_SITE("' not in line)
                self.assertEqual([l for l in stripped.splitlines() if l.strip()],
                                 [l for l in release.splitlines() if l.strip()])
                for each in ("rel", "dbg"):
                    (self.dir / each).unlink()
                    shutil.rmtree(self.dir / (each + "_c"))

    def test_debug_build_prints_what_cpython_prints(self):
        source = self.source(INDEX, "index.py")
        self.compile(source, self.dir / "debug", "--debug")
        done = self.run_exe(self.dir / "debug")
        expected = self.cpython(source)
        self.assertEqual((done.stdout, done.returncode), (expected.stdout, expected.returncode))

    def test_ir_round_trip_mode_accepts_a_debug_build(self):
        source = self.source(DIVIDE, "divide.py")
        self.compile(source, self.dir / "verify", "--debug", env=dict(self.env, AIL_IR="verify"))

    # ------------------------------------------------------------------------------- the general path
    def test_general_path_maps_its_c_to_the_users_lines(self):
        source = self.source(GENERAL, "general.py")
        done = self.compile(source, self.dir / "debug", "--debug")
        self.assertIn("general path", done.stderr)
        if not shutil.which("objdump"):
            self.skipTest("objdump is not installed")
        lines = dwarf_lines(self.dir / "debug", "general.py")
        self.assertTrue({2, 6, 7, 8, 9, 12} <= lines and max(lines) <= 13, sorted(lines))


    # ------------------------------------------------- a file mixing general-path and IR functions (pyboxed2 unparse)
    def test_mixed_general_and_ir_functions_keep_the_users_lines(self):
        mixed = ("def a(n: int) -> int:\n    t = 0\n    while t < n:\n        t += 1\n    else:\n        t = t + 1\n"
                 "    return t\n\n\ndef b(k: int) -> int:\n    return 10 // k\n\n\ndef main() -> None:\n"
                 "    print(a(3))\n    print(b(0))\n\n\nmain()\n")
        multi = ("def a(n: int, m: int) -> int:\n    t = 0\n    while t < n:\n        t += 1\n    else:\n"
                 "        t = t + 1\n    r = [i * 2 for i in range(n)]\n    s = sum(\n        r\n    ) // m\n"
                 "    return s\n\n\ndef b(xs: list[int], k: int) -> int:\n    total = 0\n    for x in xs:\n"
                 "        if x > 100:\n            total += x\n        elif x < 0:\n            total += x // k\n"
                 "        else:\n            total -= 1\n    return total\n\n\ndef main() -> None:\n"
                 "    print(a(3, 1))\n    print(b([1, 2, 3], 0))\n    print(b([1, -2, 3], 0))\n\n\nmain()\n")
        for text, name in ((mixed, "mixed.py"), (multi, "multi2.py")):
            with self.subTest(name):
                source = self.source(text, name)
                self.compile(source, self.dir / ("dbg_" + name), "--debug")
                done = self.run_exe(self.dir / ("dbg_" + name))
                expected = self.cpython(source)
                want = re.findall(r"line (\d+)", expected.stderr)[-1]
                self.assertRegex(done.stderr, r"raised near [^\n]*%s:%s\b" % (re.escape(name), want), done.stderr)


if __name__ == "__main__":
    unittest.main()
