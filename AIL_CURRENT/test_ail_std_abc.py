"""The nine buildable `abc` programs in lab/stdlib/abc, against CPython 3.12.

Every program is copied to a temporary directory, built in the default mode (with the typed
path allowed to fall back to the general path) on both AIL_IR modes, and run with empty stdin.
stdout and the exit code must match CPython's.

Three more programs in the directory are refused by name and recorded in RESULTS.md:
`virtual_subclass` (`ABC.register`), `subclasshook` (`issubclass`) and
`update_abstractmethods` (`abc.update_abstractmethods`).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "abc"

PASSING = (
    "abstract_instantiation",
    "animal",
    "cache_token",
    "codec",
    "metaclass_abcm",
    "notifications",
    "payment",
    "plugin_registry",
    "shapes",
)


class StdAbc(unittest.TestCase):
    def test_lab_programs_match_cpython(self):
        self.assertEqual(sorted(p.stem for p in PROGRAMS.glob("*.py")),
                         sorted(PASSING + ("subclasshook", "update_abstractmethods", "virtual_subclass")))
        for stem in PASSING:
            with self.subTest(program=stem), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                src = directory / (stem + ".py")
                src.write_bytes((PROGRAMS / (stem + ".py")).read_bytes())
                want = subprocess.run([sys.executable, "-B", str(src)], cwd=directory,
                                      capture_output=True, timeout=120)
                for ir in ("0", "1"):
                    exe = directory / ("exe" + ir)
                    env = dict(os.environ, AIL_IR=ir, AIL_NO_CACHE="1")
                    env.pop("AIL_NO_GENERAL", None)
                    env.pop("AIL_UNIFIED_FORCE", None)
                    built = subprocess.run(
                        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", src.name,
                         "--syntax", "python", "-o", exe.name],
                        cwd=directory, capture_output=True, text=True, timeout=900, env=env)
                    self.assertEqual(built.returncode, 0,
                                     "%s (AIL_IR=%s) did not build:\n%s\n%s"
                                     % (stem, ir, built.stdout[-3000:], built.stderr[-3000:]))
                    got = subprocess.run([str(exe)], cwd=directory, input=b"",
                                         capture_output=True, timeout=120)
                    self.assertEqual(
                        (got.returncode, got.stdout), (want.returncode, want.stdout),
                        "%s (AIL_IR=%s)\nexit %r != %r\nstderr:\n%s"
                        % (stem, ir, got.returncode, want.returncode,
                           got.stderr.decode("utf-8", "replace")[-2000:]))


if __name__ == "__main__":
    unittest.main()
