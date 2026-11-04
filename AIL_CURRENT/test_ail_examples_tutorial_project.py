"""The six tutorial-project steps build with --strict and match CPython on two logs.

Each program in examples/tutorial_project/ is compiled, then run beside `python3` on the committed
sample.log and on a 5,000-line generated log. stdout and the exit status must agree. Step 6 also
runs two option sets and one bad option; the bad option must print the same usage line and exit 2.
The module skips when no C compiler is installed.
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
PROJECT = ROOT.parent / "examples" / "tutorial_project"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
STEPS = (1, 2, 3, 4, 5, 6)
TYPED = frozenset((1, 2, 3, 4, 5, 6))


def run_cpython(program, log, args=()):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with open(log, "rb") as stream:
        return subprocess.run([sys.executable, "-B", str(program), *args], stdin=stream,
                              capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class TutorialProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-tutorial-project-")
        cls.dir = Path(cls.temp.name)
        cls.sample = PROJECT / "sample.log"
        cls.generated = cls.dir / "generated.log"
        made = subprocess.run([sys.executable, "-B", str(PROJECT / "gen_log.py"), "4242", "5000"],
                              capture_output=True, text=True, timeout=120)
        if made.returncode != 0:
            raise AssertionError(made.stdout + made.stderr)
        cls.generated.write_text(made.stdout, encoding="utf-8")

        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        cls.binaries = {}
        for step in STEPS:
            source = PROJECT / ("step%d.py" % step)
            executable = cls.dir / ("step%d.bin" % step)
            command = [sys.executable, "-B", CLI, "compile", str(source), "-o", str(executable)]
            if step in TYPED:
                command.append("--strict")
            built = subprocess.run(command, capture_output=True, text=True, timeout=600, env=env)
            if built.returncode != 0:
                raise AssertionError("step%d did not build: %s%s" % (step, built.stdout, built.stderr))
            cls.binaries[step] = executable

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def check(self, step, log, args=()):
        expected = run_cpython(PROJECT / ("step%d.py" % step), log, args)
        with open(log, "rb") as stream:
            ran = subprocess.run([str(self.binaries[step]), *args], stdin=stream,
                                 capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.returncode, expected.returncode,
                         "step%d %s %s exit status\nCPython stderr: %s\nAIL stderr: %s"
                         % (step, log.name, list(args), expected.stderr, ran.stderr))
        self.assertEqual(ran.stdout, expected.stdout,
                         "step%d %s %s stdout" % (step, log.name, list(args)))
        return expected, ran

    def test_steps_match_cpython(self):
        for step in STEPS:
            for log in (self.sample, self.generated):
                with self.subTest(step=step, log=log.name):
                    self.check(step, log)

    def test_step6_option_sets(self):
        for args in (["--top", "3"], ["--status", "5xx", "--top", "2"]):
            with self.subTest(args=args):
                self.check(6, self.generated, args)

    def test_step6_bad_option(self):
        expected, ran = self.check(6, self.sample, ["--bogus"])
        self.assertEqual(ran.stderr, expected.stderr, "step6 bad option usage")


if __name__ == "__main__":
    unittest.main()
