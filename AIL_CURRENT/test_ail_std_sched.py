"""sched1: `import sched` in compiled programs (bundled stdlib/sched.py) against CPython's sched.

The ten programs in lab/stdlib/sched/ exercise `enter`/`enterabs` with `argument=`, priority
ordering, FIFO ordering for equal time and priority, `cancel` of a pending event and of one
already run (caught as ValueError), `empty()` and `queue`, `run(blocking=False)` returning the
next event time, an action that schedules another event, an action that raises and a later
`run()` resuming, float times, and times at and beyond int64.  Every program supplies a fake
clock as `sched.scheduler(timefunc, delayfunc)`, so no output depends on the real clock.

Each passing program is compiled with the default command and with AIL_UNIFIED_FORCE=1 and run
beside `python3` on the same source; stdout and the exit status must agree.

01_enter_and_enterabs.py is refused because it passes a function with defaults as a first-class
value (compiler follow-up, see lab/stdlib/sched/RESULTS.md).  10_time_beyond_int64.py is refused
because `2 ** 63` is beyond int64; CPython prints it and the compiler stops loudly.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "sched"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "02_priority_and_fifo.py",
    "03_cancel_pending.py",
    "04_cancel_already_run.py",
    "05_queue_and_empty.py",
    "06_blocking_false.py",
    "07_reschedule_inside.py",
    "08_exception_then_resume.py",
    "09_float_times.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibSchedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-sched-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources],
                         ["01_enter_and_enterabs.py", "02_priority_and_fifo.py",
                          "03_cancel_pending.py", "04_cancel_already_run.py",
                          "05_queue_and_empty.py", "06_blocking_false.py",
                          "07_reschedule_inside.py", "08_exception_then_resume.py",
                          "09_float_times.py", "10_time_beyond_int64.py"])
        self.assertEqual(len(PASSING), 8)

    def test_programs_match_cpython(self):
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        for source in self.sources:
            if source.name not in PASSING:
                continue
            for mode in ("default", "forced-general"):
                with self.subTest(program=source.name, build=mode):
                    work = self.dir / (source.stem + "-" + mode)
                    work.mkdir(exist_ok=True)
                    program = work / source.name
                    shutil.copyfile(source, program)
                    exe = work / (source.stem + ".out")
                    env = dict(base)
                    if mode == "forced-general":
                        env["AIL_UNIFIED_FORCE"] = "1"
                    else:
                        env.pop("AIL_UNIFIED_FORCE", None)
                    built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                            "--syntax", "python", "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = run_cpython(program)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, source.name + " " + mode)


if __name__ == "__main__":
    unittest.main()
