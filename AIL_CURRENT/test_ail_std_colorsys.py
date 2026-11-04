"""G5b: `import colorsys` in compiled programs (bundled stdlib/colorsys.py) against CPython.

The programs in lab/stdlib/colorsys/ use all six public conversion functions on primaries,
greys, the 0.0/1.0 edges, hues at and just below 1.0, out-of-range inputs, int arguments, a
palette generator and hue sorting.  Each source is compiled with the default command and with
AIL_UNIFIED_FORCE=1, then run beside `python3` on the same source; stdout and the exit status
must agree.  The default build must keep at least nine of the twelve coverage programs and the
pixel benchmark on the typed path (no `built on the general path` note).
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "colorsys"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

EXPECTED = ["01_rgb_to_yiq.py", "02_yiq_to_rgb.py", "03_rgb_to_hls.py", "04_hls_to_rgb.py",
            "05_rgb_to_hsv.py", "06_hsv_to_rgb.py", "07_round_trip_yiq.py",
            "08_round_trip_hls.py", "09_round_trip_hsv.py", "10_greys_and_edges.py",
            "11_palette.py", "12_sort_by_hue.py", "bench_pixels.py"]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=300, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibColorsysTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-colorsys-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources], EXPECTED)

    def _build(self, source, work, forced):
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if forced:
            env["AIL_UNIFIED_FORCE"] = "1"
        else:
            env.pop("AIL_UNIFIED_FORCE", None)
        program = work / source.name
        exe = work / (source.stem + ("_g.out" if forced else ".out"))
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                "--syntax", "python", "-o", str(exe)],
                               cwd=str(work), capture_output=True, text=True,
                               timeout=600, env=env)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return built, exe

    def test_programs_match_cpython(self):
        typed = []
        general = []
        for source in self.sources:
            with self.subTest(program=source.name):
                work = self.dir / source.stem
                work.mkdir(exist_ok=True)
                program = work / source.name
                shutil.copyfile(source, program)
                expected = run_cpython(program)
                for forced in (False, True):
                    built, exe = self._build(source, work, forced)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=300)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s exit (forced=%s)\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, forced, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout,
                                     "%s stdout (forced=%s)" % (source.name, forced))
                    if not forced:
                        if "built on the general path" in built.stderr:
                            general.append(source.name)
                        else:
                            typed.append(source.name)
        coverage_typed = [name for name in typed if name != "bench_pixels.py"]
        self.assertGreaterEqual(len(coverage_typed), 9,
                                "typed coverage programs: %r; general: %r" % (typed, general))
        self.assertIn("bench_pixels.py", typed, "benchmark fell off the typed path")
        self.assertEqual(sorted(typed + general), EXPECTED)


if __name__ == "__main__":
    unittest.main()
