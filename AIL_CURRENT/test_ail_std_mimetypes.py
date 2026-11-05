"""mimetypes1: `import mimetypes` in compiled programs (bundled stdlib/mimetypes.py) against CPython.

The ten programs in lab/stdlib/mimetypes/ call `mimetypes.init([])` and then use the module the
way small file and web tools do: `guess_type` on plain names, paths, upper-case suffixes, the
compressed suffixes (`.tar.gz`, `.tgz`, `.svgz`, ... with their encodings), unknown suffixes, names
with no suffix and `http://` / `https://` / `ftp://` / `data:` URLs; `guess_type(..., strict=False)`;
`guess_extension` and `guess_all_extensions`; module-level `add_type` and then a lookup; a
`MimeTypes` instance (`add_type`, `guess_type`) with its `types_map` sizes and entries.

Every program is compiled with the default command and with AIL_UNIFIED_FORCE=1 and run beside
`python3` on the same source; stdout and the exit status must agree.  Both sides read the same
machine files (`knownfiles`, e.g. /etc/mime.types) through `init([])`, as CPython does, so the
answers follow the machine on both sides.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "mimetypes"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_plain_names.py",
    "02_paths.py",
    "03_upper_suffix.py",
    "04_encoding.py",
    "05_svgz.py",
    "06_unknown.py",
    "07_http_url.py",
    "08_strict_false.py",
    "09_extensions.py",
    "10_add_type_instance.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibMimetypesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-mimetypes-test-")
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
