"""diffaudit: keep the verdicts recorded in lab/diffaudit/AUDIT.md honest.

The probes are the small programs in ``lab/diffaudit/``.  A probe recorded as
``now-matches`` in both builds must keep matching CPython 3.12; a probe recorded
as ``still-differs`` must keep building and keep differing; a probe recorded as
``refused-as-said`` must keep being refused by name.  A fix therefore shows up
here as a test to update instead of passing silently.
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
PROBES = ROOT.parent / "lab" / "diffaudit"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

NOW_MATCHES = [
    "C__job_pre116_10242227_1",
    "C__job_pre116_10251611_1",
    "C__job_rbrbfuzz4_10262129_4",
    "C__job_rbfuzz4_10240913_4",
]
STILL_DIFFERS = [
    "C__job_pre388_10280828_2",
    "C__job_rbrbfuzz4_10262129_3",
    "C__job_rbrbfuzz4_10262129_5",
    "C__job_rbfuzz4_10240913_3",
    "C__job_rbfuzz4_10240913_5",
    "C__job_std_random_11011523_1",
]
REFUSED = [
    "C__job_pre134_10250029_1",
    "C__job_pre90_10242040_1",
    "C__job_rbpre54_10270147_1",
    "C__job_rbstd_math_11020651_5",
    "stdtop_decimal_1",
    "stdtop_unicodedata_1",
    "stdtop_ipaddress_1",
    "stdtop_html_1",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class DiffAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-diffaudit-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def build(self, stem, forced):
        source = PROBES / (stem + ".py")
        work = self.dir / stem / ("forced" if forced else "default")
        work.mkdir(parents=True, exist_ok=True)
        program = work / (stem + ".py")
        shutil.copyfile(source, program)
        exe = work / (stem + ".out")
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if forced:
            env["AIL_UNIFIED_FORCE"] = "1"
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                "--syntax", "python", "-o", str(exe)],
                               cwd=str(work), capture_output=True, text=True,
                               timeout=300, env=env)
        return work, env, built, exe

    def build_and_run(self, stem, forced):
        work, env, built, exe = self.build(stem, forced)
        if built.returncode != 0:
            return built, None
        return built, subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                     text=True, timeout=120, env=env)

    def test_now_matches(self):
        for stem in NOW_MATCHES:
            with self.subTest(probe=stem):
                expected = run_cpython(PROBES / (stem + ".py"))
                for forced in (False, True):
                    built, ran = self.build_and_run(stem, forced)
                    mode = "forced" if forced else "default"
                    self.assertEqual(built.returncode, 0,
                                     "%s %s build: %s" % (stem, mode, built.stderr))
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit" % (stem, mode))
                    self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (stem, mode))

    def test_still_differs(self):
        for stem in STILL_DIFFERS:
            with self.subTest(probe=stem):
                expected = run_cpython(PROBES / (stem + ".py"))
                for forced in (False, True):
                    built, ran = self.build_and_run(stem, forced)
                    mode = "forced" if forced else "default"
                    self.assertEqual(built.returncode, 0,
                                     "%s %s build: %s" % (stem, mode, built.stderr))
                    self.assertFalse(ran.returncode == expected.returncode
                                     and ran.stdout == expected.stdout,
                                     "%s %s now matches CPython; update AUDIT.md" % (stem, mode))

    def test_refused_as_said(self):
        for stem in REFUSED:
            with self.subTest(probe=stem):
                for forced in (False, True):
                    _, _, built, _ = self.build(stem, forced)
                    mode = "forced" if forced else "default"
                    self.assertNotEqual(built.returncode, 0,
                                        "%s %s now builds; update AUDIT.md" % (stem, mode))

    def test_pre138_pipeline(self):
        # The row's mechanism is pymod in the fused pipeline: the compiled tool exits 1
        # through ail_die instead of raising a catchable ZeroDivisionError.
        stem = "C__job_pre138_10250109_2"
        work, env, built, exe = self.build(stem, False)
        self.assertEqual(built.returncode, 0, built.stderr)
        feed = work / "input.bin"
        feed.write_bytes(b"\x01" + b"\x00" * 7 + b"\x00" * 8)
        ran = subprocess.run([str(exe), str(feed)], cwd=str(work), capture_output=True,
                             text=True, timeout=120, env=env)
        self.assertEqual(ran.returncode, 1)
        self.assertEqual(ran.stdout, "")
        self.assertIn("integer modulo by zero", ran.stderr)
        # A single-expression pipeline is not in the forced general-path subset.
        _, _, built_forced, _ = self.build(stem, True)
        self.assertNotEqual(built_forced.returncode, 0,
                            "forced build of the pipeline now succeeds; update AUDIT.md")

    def test_pre90_finding(self):
        stem = "C__job_pre90_10242040_2"
        expected = run_cpython(PROBES / (stem + ".py"))
        built, ran = self.build_and_run(stem, False)
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertEqual(ran.returncode, expected.returncode)
        self.assertEqual(ran.stdout, expected.stdout)
        built, ran = self.build_and_run(stem, True)
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertNotEqual(ran.returncode, expected.returncode)
        self.assertIn("AIL limit: chr_non_bmp", ran.stderr)
        self.assertNotEqual(ran.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
