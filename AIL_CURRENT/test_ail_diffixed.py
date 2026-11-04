"""G5d: `fixed` rows of DIFFERENCES.md that cite no test, locked by lab/diffixed probes.

Each probe in lab/diffixed/ exercises one `fixed` row of DIFFERENCES.md that names no
`test_ail_*` module and no `lab/` file.  This module builds every probe whose audit verdict
is `matches` in both builds with the default command and with `AIL_UNIFIED_FORCE=1`, runs it
beside `python3` on the same source, and requires stdout and the exit status to agree.

The probe for `C?-job-pre26-10240859-1` differs in the default build (the typed path still
quotes a numeric exception argument); it is a finding in lab/diffixed/AUDIT.md and is not
locked here until that build matches again.
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
PROBES = ROOT.parent / "lab" / "diffixed"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

MATCHES = [
    "stdtop_datekey_1",
    "C168",
    "C__job_rbpre103_10251545_1",
    "C__job_rbpre121_10251547_1",
    "C__job_pre109_10242222_1",
    "C__job_pre165_10250411_1",
    "C__job_pre166_10250412_1",
    "C__job_pre175_10250446_1",
    "C__job_pre107_10242221_1",
    "C__job_pre112_10242224_1",
    "C__job_pre124_10242349_1",
    "C__job_rbfuzz42_10240914_1",
    "C__job_pre126_10242351_1",
    "C__job_pre61_10241247_1",
    "C__job_pre68_10241806_1",
    "C__job_pre70_10241829_1",
    "C__job_qtest1_10241455_1",
    "C__job_qtest1_10241455_2",
    "C__job_qtest3_10241647_1",
    "C__job_fuzz45_10231201_1",
    "C__job_pre132_10250028_1",
    "C__job_pre133_10250028_1",
    "C__job_pre138_10250109_1",
    "C__job_pre113_10242225_1",
    "C__job_rbrbfuzz4_10262129_1",
    "C__job_rbrbfuzz4_10262129_2",
    "C__job_rbfuzz4_10240913_1",
    "C__job_rbfuzz4_10240913_2",
    "C__job_fuzz43_10231200_1",
    "C__job_rbpre57_10271816_1",
    "C__job_fuzz89_10231611_1",
    "C__diffs3_1",
    "C__diffs3_2",
]


def clean_env(force):
    env = dict(os.environ)
    for key in ("AIL_UNIFIED_FORCE", "AIL_UNIFIED", "AIL_NO_GENERAL", "PYTHONPATH",
                "AIL_EXACT_INT", "AIL_UNIFIED_EXACT", "AIL_NO_MIX"):
        env.pop(key, None)
    env["AIL_NO_CACHE"] = "1"
    if force:
        env["AIL_UNIFIED_FORCE"] = "1"
    return env


def limited(cmd):
    return ["bash", "-c", "ulimit -v 1500000; exec \"$@\"", "--"] + cmd


@unittest.skipUnless(CC, "installed C compiler required")
class DiffixedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-diffixed-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_probes_exist(self):
        for name in MATCHES:
            self.assertTrue((PROBES / (name + ".py")).is_file(), name)

    def test_probes_match_cpython(self):
        for name in MATCHES:
            source = PROBES / (name + ".py")
            for mode in ("default", "force"):
                with self.subTest(probe=name, mode=mode):
                    work = self.dir / (name + "_" + mode)
                    work.mkdir(exist_ok=True)
                    program = work / source.name
                    shutil.copyfile(source, program)
                    exe = work / "prog.out"
                    env = clean_env(mode == "force")
                    built = subprocess.run(limited([sys.executable, "-B", CLI, "compile",
                                                    str(program), "-o", str(exe)]),
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=120, env=env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = subprocess.run([sys.executable, "-B", str(program)],
                                              cwd=str(work), capture_output=True, text=True,
                                              timeout=120, env=clean_env(False))
                    ran = subprocess.run(limited([str(exe)]), cwd=str(work),
                                         capture_output=True, text=True, timeout=120, env=env)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s [%s] exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s [%s]" % (name, mode))


if __name__ == "__main__":
    unittest.main()
