"""The gdb pretty-printers: `print x` shows an AIL value as CPython 3.12's `repr(x)`.

Each `lab/debug/printers/v*.py` program has one `# repr: ...` comment; the test builds it with
`--debug`, breaks on that line and compares gdb's `print` with the comment.  A `# general` line
builds it on the general path (`AIL_UNIFIED_FORCE=1`); the comment's `expr:` names the gdb
expression for a value the general path keeps in a frame slot rather than a C local.  Skipped
without gdb or a C compiler.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGS = ROOT.parent / "lab" / "debug" / "printers"
CLI = ROOT / "ail_chatgpt.py"
PRINTER = ROOT / "tools_gdb" / "ail_gdb.py"
GDB = shutil.which("gdb")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
COMMENT = re.compile(r"#\s*repr:\s*(.*?)(?:\s+expr:\s*(\S+))?\s*$")

if GDB:
    print("gdb: " + subprocess.run([GDB, "--version"], capture_output=True, text=True).stdout.splitlines()[0])
else:
    print("gdb: not installed, the printer checks are skipped")
sys.stdout.flush()


@unittest.skipUnless(GDB and CC, "gdb or a C compiler is not installed")
class DebugPrinters(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-debug-printers-")
        self.addCleanup(self.tmp.cleanup)

    def cases(self):
        for path in sorted(PROGS.glob("v*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            break_line = expected = expr = None
            for number, line in enumerate(lines, 1):
                match = COMMENT.search(line)
                if match:
                    break_line, expected, expr = number, match.group(1), match.group(2) or "x"
                    break
            self.assertIsNotNone(break_line, "no `# repr:` line in %s" % path)
            general = any(line.strip() == "# general" for line in lines)
            yield path, break_line, expr, expected, general

    def build(self, path, general):
        out = Path(self.tmp.name) / path.stem
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_SERVER="0", PYTHONUTF8="1", LC_ALL="C.UTF-8")
        env.pop("AIL_QUIET_FALLBACK", None)
        flags = ["--debug"]
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        else:
            env.pop("AIL_UNIFIED_FORCE", None)
            flags.append("--strict")
        done = subprocess.run([sys.executable, "-B", str(CLI), "compile", str(path), "-o", str(out),
                               *flags], capture_output=True, text=True, env=env, timeout=600)
        if done.returncode != 0:
            self.fail("build failed: %s\n%s" % (path.name, (done.stdout + done.stderr)[-2000:]))
        return out

    def run_gdb(self, program, source, line, expr):
        env = dict(os.environ, PYTHONUTF8="1", LC_ALL="C.UTF-8")
        done = subprocess.run([GDB, "-batch", "-nx", "-x", str(PRINTER),
                               "-ex", "break %s:%d" % (source, line),
                               "-ex", "run", "-ex", "print %s" % expr, str(program)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=env, timeout=600)
        for text in done.stdout.splitlines():
            if text.startswith("$1 = "):
                return text[len("$1 = "):]
        self.fail("gdb printed no value for %s (%s:%d):\n%s" %
                  (program.name, source.name, line, (done.stdout + done.stderr)[-2500:]))

    def test_long_containers_and_bad_pointers(self):
        source = PROGS / "bounds_list.py"
        program = self.build(source, False)
        env = dict(os.environ, PYTHONUTF8="1", LC_ALL="C.UTF-8")
        done = subprocess.run([GDB, "-batch", "-nx", "-x", str(PRINTER),
                               "-ex", "break %s:3" % source, "-ex", "run",
                               "-ex", "print v_x",
                               "-ex", "set var v_x.p = 0", "-ex", "print v_x",
                               "-ex", "set var v_x.n = -1", "-ex", "print v_x", str(program)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=env, timeout=600)
        values = []
        for text in done.stdout.splitlines():
            match = re.match(r"^\$(\d+) = (.*)$", text)
            if match:
                values.append(match.group(2))
        self.assertEqual(len(values), 3, done.stdout + done.stderr)
        self.assertEqual(values[0], "[" + ", ".join(str(i) for i in range(100)) + ", ...]")
        self.assertEqual(values[1], "<unreadable>")
        self.assertEqual(values[2], "<unreadable>")

    def test_printers_match_python_repr(self):
        results = []
        for path, line, expr, expected, general in self.cases():
            program = self.build(path, general)
            actual = self.run_gdb(program, path, line, expr)
            results.append((path.name, general, expected, actual))
        failed = [(name, want, got) for name, _, want, got in results if want != got]
        for name, general, want, got in results:
            print("  %-4s %-22s %-22s %s" % ("ok" if want == got else "FAIL", name,
                                             ("general" if general else "typed"), got))
        self.assertEqual(failed, [], "printer mismatch: %r" % (failed,))
        self.assertGreaterEqual(len(results), 12)


if __name__ == "__main__":
    unittest.main()
