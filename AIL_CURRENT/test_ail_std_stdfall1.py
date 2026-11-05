"""stdfall1: fnmatch, reprlib and sched as bundled stdlib modules.

The programs in lab/stdlib/{fnmatch,reprlib,sched}/ use the modules the way ordinary code does.
Each passing program is compiled with the default command and with AIL_UNIFIED_FORCE=1, then run
beside `python3` on the same source; stdout and the exit status must agree.  Two programs are
expected to be refused by the compiler (a big int beyond int64 and a decorator on a method), so the
passing set is 16 of the 18.
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
LAB = ROOT.parent / "lab" / "stdlib"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "fnmatch/01_basic_patterns.py",
    "fnmatch/02_brackets.py",
    "fnmatch/03_filter.py",
    "fnmatch/04_translate.py",
    "fnmatch/05_bytes.py",
    "fnmatch/06_paths_and_case.py",
    "reprlib/01_long_list.py",
    "reprlib/02_dict_nested.py",
    "reprlib/03_strings.py",
    "reprlib/05_custom_limits.py",
    "sched/01_events.py",
    "sched/02_priorities.py",
    "sched/03_cancel.py",
    "sched/04_queue.py",
    "sched/05_nonblocking.py",
    "sched/06_enterabs_kwargs.py",
]

REFUSED = [
    "reprlib/04_big_ints.py",
    "reprlib/06_recursive.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


def compile_program(program, exe, force):
    env = dict(os.environ, AIL_NO_CACHE="1")
    env.pop("PYTHONPATH", None)
    if force:
        env["AIL_UNIFIED_FORCE"] = "1"
    else:
        env.pop("AIL_UNIFIED_FORCE", None)
    return subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                           "--syntax", "python", "-o", str(exe)],
                          cwd=str(program.parent), capture_output=True, text=True,
                          timeout=600, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibStdfall1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-stdfall1-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_program_sets(self):
        found = sorted(str(p.relative_to(LAB)) for p in LAB.glob("*/*.py")
                       if p.parent.name in ("fnmatch", "reprlib", "sched"))
        self.assertEqual(found, sorted(PASSING + REFUSED))

    def test_programs_match_cpython(self):
        for relative in PASSING:
            source = LAB / relative
            with self.subTest(program=relative):
                work = self.dir / source.parent.name / source.stem
                work.mkdir(parents=True, exist_ok=True)
                program = work / source.name
                shutil.copyfile(source, program)
                expected = run_cpython(program)
                for mode, force in (("default", False), ("unified", True)):
                    exe = work / (source.stem + "." + mode + ".out")
                    built = compile_program(program, exe, force)
                    self.assertEqual(built.returncode, 0,
                                     "%s %s build\n%s%s" % (relative, mode,
                                                            built.stdout, built.stderr))
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (relative, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout,
                                     "%s %s stdout" % (relative, mode))


if __name__ == "__main__":
    unittest.main()
