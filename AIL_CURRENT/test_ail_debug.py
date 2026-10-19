"""`ail build --debug` / `ail_chatgpt.py compile --debug` (AIL_DEBUG=1): a program gdb can step through.

* -g -O0, and a `#line N "file.py"` before every statement, so the debug info maps machine code back to the
  Python lines (checked in the DWARF line table with readelf/objdump, or with gdb when it is installed);
* an uncaught exception prints its CPython-compatible message and then `  raised near file:line` (the last
  statement that began to run, which is the raise site for a raise statement and for a runtime trap);
  without --debug stderr is exactly what it was (the bare message), and a debug build prints what a normal build
  prints on stdout;
* the build cache keeps debug and normal builds apart; imported modules map to their own file and line;
* the general path has no line mapping, and `ail build --debug` says so.

Needs a C compiler (skipped without one). The `ail` command tests are skipped when packaging/ is not beside this
directory.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGING = ROOT.parent / "packaging"
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

RAISER = """def pick(n: int) -> int:
    xs = [1, 2, 3]
    return xs[n]


def main() -> None:
    print("start")
    print(pick(7))


main()
"""
EXPLICIT = """def check(n: int) -> int:
    if n > 2:
        raise ValueError("too big: " + str(n))
    return n


def main() -> None:
    total = 0
    for i in range(5):
        total += check(i)
    print(total)


main()
"""
WORK = """def collatz(n: int) -> int:
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps


def main() -> None:
    words = {}
    for i in range(1, 30):
        words[str(i)] = collatz(i)
    best = 0
    for key in sorted(words):
        if words[key] > best:
            best = words[key]
    print(best, len(words), "-".join(sorted(words)[:4]))


main()
"""
BLOCKER = ("def find(d: dict[int, int], k: int) -> int | None:\n    return d.get(k)\n\n\n"
           "def main() -> None:\n    print(find({1: 2}, 1))\n\n\nmain()\n")


@unittest.skipUnless(CC, "no C compiler")
class Debug(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-debug-test-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ, AIL_CACHE=str(self.dir / "cache"), PYTHONUTF8="1")
        self.env.pop("AIL_QUIET_FALLBACK", None)
        self.env.pop("AIL_NO_CACHE", None)

    def source(self, text, name="prog.py"):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def compile(self, source, output, *flags, env=None):
        done = subprocess.run([sys.executable, "-B", CLI, "compile", *flags, str(source), "-o", str(output)],
                              capture_output=True, text=True, encoding="utf-8", env=env or self.env, timeout=600)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done

    def run_program(self, program):
        return subprocess.run([str(program)], capture_output=True, text=True, encoding="utf-8", timeout=120)

    def test_runtime_trap_names_the_statement(self):
        source = self.source(RAISER)
        self.compile(source, self.dir / "plain")
        self.compile(source, self.dir / "debug", "--debug")
        plain, debug = self.run_program(self.dir / "plain"), self.run_program(self.dir / "debug")
        self.assertEqual((plain.returncode, plain.stdout, plain.stderr), (1, "start\n", "list index out of range\n"))
        self.assertEqual((debug.returncode, debug.stdout), (1, "start\n"))
        self.assertEqual(debug.stderr, "list index out of range\n  raised near %s:3\n" % source)

    def test_raise_statement_names_its_line(self):
        source = self.source(EXPLICIT)
        self.compile(source, self.dir / "debug", "--debug")
        done = self.run_program(self.dir / "debug")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stderr, "ValueError: too big: 3\n  raised near %s:3\n" % source)

    def test_a_caught_exception_prints_nothing_extra(self):
        source = self.source(EXPLICIT.replace("total += check(i)",
                                              "try:\n            total += check(i)\n        except ValueError:\n"
                                              "            total += 100"))
        self.compile(source, self.dir / "debug", "--debug")
        done = self.run_program(self.dir / "debug")
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "203\n", ""))

    def test_the_output_is_the_same_as_cpython_and_a_normal_build(self):
        source = self.source(WORK)
        expected = subprocess.run([sys.executable, "-B", str(source)], capture_output=True, text=True).stdout
        self.compile(source, self.dir / "plain")
        self.compile(source, self.dir / "debug", "--debug")
        self.assertEqual(self.run_program(self.dir / "plain").stdout, expected)
        self.assertEqual(self.run_program(self.dir / "debug").stdout, expected)

    def test_debug_and_normal_builds_do_not_share_cache_entries(self):
        source = self.source(RAISER)
        for name, flags in (("a", ()), ("b", ("--debug",)), ("c", ()), ("d", ("--debug",))):
            self.compile(source, self.dir / name, *flags)
        sizes = {name: (self.dir / name).stat().st_size for name in "abcd"}
        self.assertEqual((sizes["a"], sizes["b"]), (sizes["c"], sizes["d"]))
        self.assertGreater(sizes["b"], sizes["a"])
        self.assertEqual(self.run_program(self.dir / "c").stderr, "list index out of range\n")
        self.assertIn("raised near", self.run_program(self.dir / "d").stderr)

    def line_table(self, program):
        """{(file, line)} from the DWARF line table, by readelf or objdump."""
        for tool, args in (("readelf", ["--debug-dump=decodedline"]), ("objdump", ["--dwarf=decodedline"])):
            if shutil.which(tool):
                text = subprocess.run([tool, *args, str(program)], capture_output=True, text=True).stdout
                found = set()
                for match in re.finditer(r"^(\S+\.py)\s+(\d+)\s", text, re.M):
                    found.add((match.group(1), int(match.group(2))))
                if found:
                    return found
        return None

    def test_dwarf_line_table_points_at_the_python_lines(self):
        source = self.source(RAISER)
        self.compile(source, self.dir / "debug", "--debug")
        if shutil.which("gdb"):
            done = subprocess.run(["gdb", "-batch", "-ex", "break prog.py:3", "-ex", "run", "-ex", "bt 1",
                                   str(self.dir / "debug")], capture_output=True, text=True, timeout=120)
            self.assertIn("prog.py:3", done.stdout)
            return
        lines = self.line_table(self.dir / "debug")
        if lines is None:
            self.skipTest("neither gdb, readelf nor objdump is installed")
        self.assertTrue({("prog.py", 2), ("prog.py", 3), ("prog.py", 7), ("prog.py", 8)} <= lines, sorted(lines))
        self.compile(source, self.dir / "plain")
        self.assertFalse(self.line_table(self.dir / "plain"))

    def test_an_imported_module_maps_to_its_own_file(self):
        self.source("def pick(n: int) -> int:\n    xs = [1, 2, 3]\n    return xs[n]\n", "helper.py")
        main = self.source("from helper import pick\n\n\ndef main() -> None:\n    print(pick(5))\n\n\nmain()\n",
                           "main.py")
        self.compile(main, self.dir / "debug", "--debug")
        done = self.run_program(self.dir / "debug")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stderr.splitlines()[1], "  raised near %s:3" % (self.dir / "helper.py"))

    def test_link_option_is_in_the_cache_key(self):
        source = self.source("print(1)\n")
        self.compile(source, self.dir / "ok", "--link", "m")
        done = subprocess.run([sys.executable, "-B", CLI, "compile", "--link", "ail_no_such_library", str(source),
                               "-o", str(self.dir / "bad")], capture_output=True, text=True, env=self.env, timeout=600)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("ail_no_such_library", done.stdout + done.stderr)


@unittest.skipUnless(CC and (PACKAGING / "ail_lang" / "cli.py").is_file(), "no C compiler, or packaging/ is absent")
class DebugCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-debug-cli-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def ail(self, *args):
        env = dict(os.environ, PYTHONPATH=str(PACKAGING), AIL_SDK_DIR=str(ROOT), PYTHONUTF8="1",
                   AIL_CACHE=str(self.dir / "cache"))
        env.pop("AIL_QUIET_FALLBACK", None)
        env.pop("AIL_NO_CACHE", None)
        return subprocess.run([sys.executable, "-B", "-m", "ail_lang", *args], cwd=self.dir, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=600)

    def test_build_debug_end_to_end(self):
        source = self.dir / "prog.py"
        source.write_text(RAISER, encoding="utf-8")
        done = self.ail("build", "--debug", "prog.py", "-o", "prog_debug")
        self.assertEqual(done.returncode, 0, done.stderr)
        crash = subprocess.run([str(self.dir / "prog_debug")], capture_output=True, text=True)
        self.assertIn("raised near %s:3" % source, crash.stderr)
        done = self.ail("build", "prog.py", "-o", "prog_plain")
        self.assertEqual(done.returncode, 0, done.stderr)
        crash = subprocess.run([str(self.dir / "prog_plain")], capture_output=True, text=True)
        self.assertEqual(crash.stderr, "list index out of range\n")

    def test_general_path_debug_build_says_there_is_no_line_mapping(self):
        source = self.dir / "slow.py"
        source.write_text(BLOCKER, encoding="utf-8")
        done = self.ail("build", "--debug", "slow.py", "-o", "slow_debug")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("built on the general path", done.stderr)
        self.assertIn("no line mapping", done.stderr)
        self.assertEqual(subprocess.run([str(self.dir / "slow_debug")], capture_output=True, text=True).stdout, "2\n")


if __name__ == "__main__":
    unittest.main()
