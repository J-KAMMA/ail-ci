"""CPython stdlib `datetime`: twelve realistic programs, built in the default mode.

The programs live in lab/stdlib/datetime. Nine of them build and must print exactly what
CPython prints, with the same exit code: invoice dates and weekend adjustment, ISO log
timestamps, sprint planning, age arithmetic, a dict keyed by date, timedelta arithmetic,
fixed-offset time zones, strptime formats, and combining dates with times. The three that
stay refused are named by the compiler: time.fromisoformat, isocalendar() and timetuple().
RESULTS.md records each result and the first refusal message.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "datetime"

BUILT = [
    "age_calculator",
    "birthday_parser",
    "duration_report",
    "invoice_due",
    "log_timestamps",
    "meeting_slots",
    "sprint_plan",
    "timesheet",
    "workday_schedule",
]

REFUSED = {
    "calendar_export": ["datetime.time.fromisoformat is not built"],
    "epoch_convert": [".timetuple() returns a struct_time"],
    "iso_week": [".isocalendar() returns a named tuple"],
}


def compile_python(directory, source, name, **env):
    exe = Path(directory, name)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "--syntax", "python", "-o", str(exe)], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, exe


class StdDatetime(unittest.TestCase):
    def test_built_programs_match_cpython(self):
        for name in BUILT:
            with self.subTest(program=name), tempfile.TemporaryDirectory(prefix="ail-dt-") as directory:
                source = PROGRAMS / (name + ".py")
                self.assertTrue(source.is_file(), source)
                env = dict(os.environ)
                env.pop("AIL_NO_GENERAL", None)
                env.pop("AIL_UNIFIED_FORCE", None)
                env.pop("AIL_CLOCK", None)
                built, exe = compile_python(directory, source, name, **env)
                self.assertEqual(built.returncode, 0,
                                 "%s did not build\n%s%s" % (name, built.stdout[-2000:], built.stderr[-2000:]))
                want = subprocess.run([sys.executable, "-X", "utf8", str(source)], capture_output=True,
                                      timeout=300, env=dict(os.environ, PYTHONUTF8="1"))
                got = subprocess.run([str(exe)], capture_output=True, timeout=300,
                                     env=dict(os.environ, PYTHONUTF8="1"))
                self.assertEqual(got.returncode, want.returncode, (name, got.stderr[-1000:]))
                if got.stdout != want.stdout:
                    a = want.stdout.decode("utf-8", "replace").splitlines()
                    b = got.stdout.decode("utf-8", "replace").splitlines()
                    for i in range(max(len(a), len(b))):
                        x = a[i] if i < len(a) else "<none>"
                        y = b[i] if i < len(b) else "<none>"
                        if x != y:
                            self.fail("%s line %d: CPython %r, AIL %r" % (name, i + 1, x[:300], y[:300]))

    def test_refused_programs_are_named(self):
        for name, needles in REFUSED.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory(prefix="ail-dt-") as directory:
                source = PROGRAMS / (name + ".py")
                self.assertTrue(source.is_file(), source)
                env = dict(os.environ)
                env.pop("AIL_NO_GENERAL", None)
                env.pop("AIL_UNIFIED_FORCE", None)
                built, exe = compile_python(directory, source, name, **env)
                self.assertNotEqual(built.returncode, 0, built.stdout)
                self.assertFalse(exe.exists())
                self.assertNotIn("Traceback", built.stderr)
                for needle in needles:
                    self.assertIn(needle, built.stderr)


if __name__ == "__main__":
    unittest.main()
