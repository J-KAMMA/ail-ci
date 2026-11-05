"""G5a: `import cmd` in compiled programs (bundled stdlib/cmd.py) against CPython's cmd.

The ten programs in lab/stdlib/cmd/ subclass cmd.Cmd and use the ordinary command-loop API:
prompts and intros, do_* methods with and without arguments, do_EOF, default/unknown commands,
the default and an overridden emptyline, precmd/postcmd/preloop/postloop, help tables and
help_* methods, parseline, cmdqueue and direct onecmd calls.  Each is compiled with the default
command and run beside `python3` on the same source (feeding its .in file when it has one);
stdout and the exit status must agree.  The calculator program is exercised separately: it
stops loudly on an int beyond int64, which the task allows.

Nine of the ten programs are expected to match.  The tenth, 09_calculator.py, is built and run
only to check that the overflow is loud (non-zero exit), because CPython prints the arbitrary
precision value.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "cmd"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_hello_commands.py",
    "02_unknown_and_empty.py",
    "03_emptyline_override.py",
    "04_hooks.py",
    "05_help.py",
    "06_parseline.py",
    "07_cmdqueue.py",
    "08_onecmd.py",
    "10_aliases.py",
]
ALL = PASSING[:8] + ["09_calculator.py", "10_aliases.py"]


def stdin_for(source):
    side = source.with_suffix(".in")
    if side.is_file():
        return side.read_bytes()
    return b""


def run_cpython(path, data):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          input=data, capture_output=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibCmdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-cmd-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual(sorted(p.name for p in PROGRAMS.glob("*.py")), sorted(ALL))

    def test_programs_match_cpython(self):
        for name in PASSING:
            source = PROGRAMS / name
            data = stdin_for(source)
            work = self.dir / source.stem
            work.mkdir(exist_ok=True)
            program = work / source.name
            shutil.copyfile(source, program)
            expected = run_cpython(program, data)
            for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(program=name, build=mode):
                    env = dict(os.environ, AIL_NO_CACHE="1", **extra)
                    env.pop("PYTHONPATH", None)
                    exe = work / (source.stem + "." + mode + ".out")
                    built = subprocess.run([sys.executable, "-B", CLI, "compile",
                                            str(program), "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], cwd=str(work), input=data,
                                         capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (name, mode))

    def test_calculator_stops_loudly(self):
        source = PROGRAMS / "09_calculator.py"
        data = stdin_for(source)
        work = self.dir / source.stem
        work.mkdir(exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
            with self.subTest(build=mode):
                env = dict(os.environ, AIL_NO_CACHE="1", **extra)
                env.pop("PYTHONPATH", None)
                exe = work / ("09_calculator." + mode + ".out")
                built = subprocess.run([sys.executable, "-B", CLI, "compile",
                                        str(program), "-o", str(exe)],
                                       cwd=str(work), capture_output=True, text=True,
                                       timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], cwd=str(work), input=data,
                                     capture_output=True, timeout=120)
                self.assertNotEqual(ran.returncode, 0)
                self.assertIn(b"OverflowError", ran.stderr)


if __name__ == "__main__":
    unittest.main()
