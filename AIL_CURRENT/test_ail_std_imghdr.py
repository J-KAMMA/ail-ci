"""imghdr1: `import imghdr` in compiled programs (bundled stdlib/imghdr.py) against CPython's imghdr.

The ten programs in lab/stdlib/imghdr/ build image headers and print what `imghdr.what` returns:
every test in CPython's list (jpeg JFIF/Exif/raw, png, gif 87a/89a, tiff MM/II, rgb, pbm, pgm,
ppm, rast, xbm, bmp, webp, exr), bytes matching nothing, an empty `h`, `h` shorter than 32 bytes, a
file written with `open(name, "wb")` and read back by name and through a `"rb"` handle, and the
length and order of `imghdr.tests`.  Every program is compiled with the default command and with
AIL_UNIFIED_FORCE=1 and run beside `python3` on the same source; stdout and the exit status must
agree.

The bundled module drops CPython's `warnings._deprecated` call (so no DeprecationWarning) and its
`PathLike` branch, and drops the test()/testall() command-line helper; see the module docstring.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "imghdr"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_jpeg.py",
    "02_png_gif.py",
    "03_tiff.py",
    "04_netpbm.py",
    "05_misc.py",
    "06_webp_exr.py",
    "07_none.py",
    "08_short_and_empty.py",
    "09_file_paths.py",
    "10_tests_list.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibImghdrTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-imghdr-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources], PASSING)
        self.assertEqual(len(PASSING), 10)

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
