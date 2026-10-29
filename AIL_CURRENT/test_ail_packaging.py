"""The ail-lang wheel: built with pip, installed in a fresh venv, and run outside the repository."""
import hashlib
import importlib.util
import json
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
UNPACKAGED = {
    "python/pkg-v12/bench.py",
    "python/pkg-v12/test_all.py",
    "python/pkg-v12/test_pipeline.py",
}
PACKAGE_EXTRAS = {"MANIFEST.json", "LICENSE-APACHE", "LICENSE-MIT"}


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
        cls.source_manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
        cls.selected = set(cls.source_manifest["sdk_files"]) - UNPACKAGED
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

    def _wheel_files(self):
        with zipfile.ZipFile(self.wheel) as archive:
            return {name[len("ail_lang/"):]: archive.read(name)
                    for name in archive.namelist() if name.startswith("ail_lang/")}

    def _run(self, *args, cwd=None):
        return subprocess.run([str(self.ail), *map(str, args)], cwd=cwd or self.base,
                              capture_output=True, text=True, timeout=600)

    def test_wheel_has_exactly_the_selected_sdk_files(self):
        files = self._wheel_files()
        self.assertEqual(set(files), self.selected | PACKAGE_EXTRAS)
        pins = self.source_manifest["sha256"]
        for name in sorted(self.selected):
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), pins[name], name)
        self.assertIn("python/pkg-v12/SEMANTICS.md", files)
        self.assertIn("python/pkg-v12/ir/driver.py", files)
        self.assertIn("stdlib/zlib.py", files)
        self.assertFalse(any(Path(name).name.startswith("test_") for name in files), files)

    def test_installed_manifest_describes_the_installed_files(self):
        files = self._wheel_files()
        installed = json.loads(files["MANIFEST.json"])
        self.assertEqual(set(installed["sdk_files"]), self.selected)
        self.assertEqual(set(installed["sha256"]), self.selected)
        self.assertFalse(UNPACKAGED & set(installed["sdk_files"]))
        for name, digest in installed["sha256"].items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), digest, name)

    def test_compile_and_run_outside_the_repository(self):
        work = self.base / "work"
        work.mkdir()
        (work / "hello.py").write_text(HELLO, encoding="utf-8")
        built = self._run("compile", "hello.py", "--syntax", "python", "-o", "hello", cwd=work)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        binary = work / ("hello.exe" if os.name == "nt" else "hello")
        self.assertTrue(binary.is_file(), built.stdout + built.stderr)
        ran = subprocess.run([str(binary)], cwd=work, capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, "hello, world\n")

    def test_installed_cli_reads_its_runtime_files(self):
        api = self._run("api-builtin", "abs")
        self.assertEqual(api.returncode, 0, api.stderr)
        report = json.loads(api.stdout)
        self.assertEqual(report["schema"], "ail.builtin_api/1")
        self.assertIn("abs", [entry["symbol"] for entry in report["entries"]])
        integrity = self._run("integrity")
        self.assertEqual(integrity.returncode, 0, integrity.stdout + integrity.stderr)
        report = json.loads(integrity.stdout)
        self.assertEqual(report["status"], "verified", report["mismatches"])
        self.assertEqual(report["mismatches"], [])

    def test_installed_export_sdk_is_complete(self):
        output = self.base / "exported"
        exported = self._run("export-sdk", "-o", output)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        manifest = json.loads((output / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "ail_language_sdk")
        self.assertEqual(set(manifest["sdk_files"]),
                         self.selected | {"LICENSE-APACHE", "LICENSE-MIT"})
        self.assertTrue((output / "python/pkg-v12/SEMANTICS.md").is_file())
        for name in PACKAGE_EXTRAS - {"MANIFEST.json"}:
            self.assertEqual((output / name).read_bytes(), (REPO / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
