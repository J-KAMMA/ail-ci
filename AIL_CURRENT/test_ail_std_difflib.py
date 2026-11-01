"""Real programs that use `difflib`, compared with CPython 3.12 byte for byte.

Ten of the twelve programs in lab/stdlib/difflib build on the default path (the general path,
because the typed path does not model the import) and must print CPython's stdout and exit with
CPython's status.  The remaining two are documented follow-ups in RESULTS.md: a **kwargs call
argument and HtmlDiff.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "difflib"
PASSING = [
    "01_close_matches.py",
    "02_config_typo.py",
    "03_patch_preview.py",
    "05_context_patch.py",
    "06_ndiff_restore.py",
    "07_differ_junk.py",
    "08_seq_ratio.py",
    "09_seq_opcodes.py",
    "10_seq_grouped.py",
    "11_diff_bytes.py",
]


@unittest.skipUnless(PROGRAMS.is_dir(), "lab/stdlib/difflib is not part of this tree")
class StdlibDifflibTests(unittest.TestCase):
    def test_programs_match_cpython(self):
        for name in PASSING:
            with self.subTest(program=name), tempfile.TemporaryDirectory(prefix="ail-difflib-") as tmp:
                work = Path(tmp)
                source = work / name
                shutil.copyfile(PROGRAMS / name, source)
                exe = work / (name[:-3] + ".exe")

                want = subprocess.run([sys.executable, str(source)], cwd=work, capture_output=True, timeout=300)
                self.assertEqual(want.returncode, 0, want.stderr.decode("utf-8", "replace"))

                env = dict(os.environ, AIL_NO_CACHE="1")
                env.pop("AIL_NO_GENERAL", None)
                built = subprocess.run(
                    [sys.executable, "-B", CLI, "compile", source.name, "--syntax", "python", "-o", exe.name],
                    cwd=work,
                    capture_output=True,
                    text=True,
                    timeout=900,
                    env=env,
                )
                self.assertEqual(built.returncode, 0, built.stderr[-4000:])
                self.assertIn("general path", built.stderr)

                got = subprocess.run([str(exe)], cwd=work, capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, got.stderr.decode("utf-8", "replace"))
                if got.stdout != want.stdout:
                    a = want.stdout.decode("utf-8", "replace").splitlines()
                    b = got.stdout.decode("utf-8", "replace").splitlines()
                    for index in range(max(len(a), len(b))):
                        x = a[index] if index < len(a) else "<missing>"
                        y = b[index] if index < len(b) else "<missing>"
                        if x != y:
                            self.fail("%s line %d: CPython %r, AIL %r" % (name, index + 1, x[:300], y[:300]))
                self.assertEqual(got.stdout, want.stdout)


if __name__ == "__main__":
    unittest.main()
