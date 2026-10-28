"""The ail-lang wheel: built with pip, installed in a fresh venv, and run outside the repository."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
HELLO = 'def main() -> None:\n    print("hello, world")\n\n\nmain()\n'


def _missing_build_tools():
    return [name for name in ("setuptools", "wheel")
            if importlib.util.find_spec(name) is None]


class PackagingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = _missing_build_tools()
        if missing:
            raise unittest.SkipTest("packaging test needs " + " and ".join(missing))
        if not (REPO / "pyproject.toml").is_file():
            raise unittest.SkipTest("repository root with pyproject.toml is not beside AIL_CURRENT")
        cls.base = Path(tempfile.mkdtemp(prefix="ail-packaging-"))
        wheels = cls.base / "wheels"
        wheels.mkdir()
        built = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
             "-w", str(wheels), str(REPO)],
            cwd=cls.base, capture_output=True, text=True, timeout=900)
        if built.returncode:
            shutil.rmtree(cls.base, ignore_errors=True)
            raise RuntimeError("pip wheel failed: " + built.stderr[-2000:])
        cls.wheel = next(wheels.glob("*.whl"))
        venv = cls.base / "venv"
        made = subprocess.run([sys.executable, "-m", "venv", str(venv)],
                              capture_output=True, text=True, timeout=300)
        scripts = venv / ("Scripts" if os.name == "nt" else "bin")
        cls.python = scripts / ("python.exe" if os.name == "nt" else "python")
        cls.ail = scripts / ("ail.exe" if os.name == "nt" else "ail")
        if made.returncode or not cls.python.is_file():
            shutil.rmtree(cls.base, ignore_errors=True)
            raise unittest.SkipTest("cannot create a virtual environment: " + made.stderr[-300:])
        installed = subprocess.run(
            [str(cls.python), "-m", "pip", "install", "--no-index", "--no-deps", str(cls.wheel)],
            cwd=cls.base, capture_output=True, text=True, timeout=600)
        if installed.returncode:
            shutil.rmtree(cls.base, ignore_errors=True)
            raise RuntimeError("pip install failed: " + installed.stderr[-2000:])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "base", ""), ignore_errors=True)

    def test_wheel_has_the_compiler_and_no_repository_trees(self):
        with zipfile.ZipFile(self.wheel) as archive:
            names = set(archive.namelist())
        self.assertIn("ail_lang/ail_chatgpt.py", names)
        self.assertIn("ail_lang/ail_syntax.py", names)
        self.assertIn("ail_lang/python/pkg-v12/pyc.py", names)
        self.assertIn("ail_lang/python/pkg-v12/ir/driver.py", names)
        self.assertIn("ail_lang/stdlib/zlib.py", names)
        self.assertFalse(any(Path(name).name.startswith("test_") for name in names), names)
        self.assertNotIn("ail_lang/benchmark_current_rows.py", names)
        self.assertFalse(any(name.startswith(("ail_lang/docs/", "ail_lang/lab/", "ail_lang/bench/"))
                             for name in names), names)

    def test_compile_and_run_outside_the_repository(self):
        work = self.base / "work"
        work.mkdir()
        (work / "hello.py").write_text(HELLO, encoding="utf-8")
        built = subprocess.run(
            [str(self.ail), "compile", "hello.py", "--syntax", "python", "-o", "hello"],
            cwd=work, capture_output=True, text=True, timeout=600)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        binary = work / ("hello.exe" if os.name == "nt" else "hello")
        self.assertTrue(binary.is_file(), built.stdout + built.stderr)
        ran = subprocess.run([str(binary)], cwd=work, capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, "hello, world\n")


if __name__ == "__main__":
    unittest.main()
