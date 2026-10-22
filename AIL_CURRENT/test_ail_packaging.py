"""G14: the ail-lang wheel (pyproject.toml, packaging/).

* The wheel's file list is exactly the SDK selection (MANIFEST.json sdk_files, the files ail_sdk.export_sdk
  writes) plus the `ail` command module and the dist-info; nothing private (experiments/, docs/design,
  a held-out task set, evidence/) is in it, every SDK file carries its MANIFEST pin, RECORD is right, and the version
  comes from the one source (packaging/ail_lang/__init__.py).
* Every compiler file that is pinned in the source tree is selected (an SDK that lacks one fails at the first
  program that needs it).
* A fresh venv (pip from ensurepip, no network) installs the wheel built through the PEP 517 backend and runs
  hello world, a multi-module program, a pathlib program and an FFI program like CPython 3.12 does, plus
  `ail build`, `ail check`, the missing-C-compiler message and the per-user cache directory.

The tests are skipped when the repository root with pyproject.toml is not beside this directory (an SDK export).
"""
import base64
import csv
import hashlib
import io
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
BACKEND = REPO / "packaging" / "ail_wheel_backend.py"
PRIVATE_PARTS = ("experiments", "a held-out task set", "evidence", "design", "bench", "tests")
LICENSE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")
PACKAGE_FILES = ("__init__.py", "__main__.py", "cli.py", "project.py", "lsp.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

wheel_dir = None
wheel_path = None


def setUpModule():
    global wheel_dir, wheel_path
    if not (REPO / "pyproject.toml").is_file() or not BACKEND.is_file():
        raise unittest.SkipTest("repository root with pyproject.toml is not beside AIL_CURRENT")
    wheel_dir = tempfile.mkdtemp(prefix="ail-wheel-test-")
    done = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, 'packaging'); import ail_wheel_backend as b; print(b.build_wheel(sys.argv[1]))",
         wheel_dir], cwd=REPO, capture_output=True, text=True, timeout=300)
    if done.returncode:
        raise RuntimeError("wheel build failed: " + done.stderr)
    wheel_path = Path(wheel_dir) / done.stdout.strip()


def tearDownModule():
    if wheel_dir:
        shutil.rmtree(wheel_dir, ignore_errors=True)


def source_version():
    for line in (REPO / "packaging" / "ail_lang" / "__init__.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"\'')
    raise AssertionError("no __version__")


class WheelContents(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
        self.zip = zipfile.ZipFile(wheel_path)
        self.addCleanup(self.zip.close)
        self.names = set(self.zip.namelist())

    def test_file_list_is_the_sdk_selection(self):
        sdk = {"ail_lang/sdk/" + name for name in self.manifest["sdk_files"]}
        sdk |= {"ail_lang/sdk/MANIFEST.json", "ail_lang/sdk/SDK_README_JA.md"}
        sdk |= {"ail_lang/sdk/" + name for name in LICENSE_FILES}
        package = {"ail_lang/" + name for name in PACKAGE_FILES}
        info = "ail_lang-%s.dist-info/" % source_version()
        dist = {info + name for name in ("METADATA", "WHEEL", "entry_points.txt", "RECORD")}
        dist |= {info + "licenses/" + name for name in LICENSE_FILES}
        self.assertEqual(self.names - sdk - package - dist, set(), "files outside the SDK selection")
        self.assertEqual((sdk | package | dist) - self.names, set(), "selected files missing from the wheel")
        self.assertEqual(len(self.zip.namelist()), len(self.names), "duplicate members")

    def test_nothing_private_is_in_the_wheel(self):
        for name in self.names:
            parts = name.split("/")
            self.assertTrue(not set(parts) & set(PRIVATE_PARTS), name)
            self.assertNotIn("docs/design", name)
            self.assertNotIn("__pycache__", name)
        # the private trees exist in the source tree, so the check above is not vacuous
        self.assertTrue((ROOT / "evidence").exists() or (REPO / "experiments").exists())
        self.assertFalse(any(name.startswith(("experiments", "docs", "tasks", "evidence")) for name in self.names))
        selected = set(self.manifest["sdk_files"])
        for name in selected:
            self.assertTrue(not set(name.split("/")) & set(PRIVATE_PARTS), name)

    def test_every_compiler_file_is_selected(self):
        pins, selected = self.manifest["sha256"], set(self.manifest["sdk_files"])
        compiler = ROOT / "python" / "pkg-v12"
        wanted = {p.relative_to(ROOT).as_posix() for p in compiler.rglob("*")
                  if p.is_file() and p.suffix in (".py", ".h", ".c") and "__pycache__" not in p.parts}
        wanted |= {p.relative_to(ROOT).as_posix() for p in (ROOT / "stdlib").iterdir()
                   if p.suffix in (".py", ".h", ".c")}
        missing = sorted(name for name in wanted if name in pins and name not in selected)
        self.assertEqual(missing, [], "pinned compiler files missing from sdk_files")

    def test_sdk_files_carry_their_pins(self):
        pins = self.manifest["sha256"]
        for name in self.manifest["sdk_files"]:
            data = self.zip.read("ail_lang/sdk/" + name)
            self.assertEqual(hashlib.sha256(data).hexdigest(), pins[name], name)
        sdk_manifest = json.loads(self.zip.read("ail_lang/sdk/MANIFEST.json"))
        self.assertEqual(sdk_manifest["kind"], "ail_language_sdk")
        self.assertEqual(sorted(sdk_manifest["sdk_files"]), sorted(self.manifest["sdk_files"] + list(LICENSE_FILES)))

    def test_record_matches(self):
        info = "ail_lang-%s.dist-info/" % source_version()
        rows = list(csv.reader(io.StringIO(self.zip.read(info + "RECORD").decode("utf-8"))))
        self.assertEqual({row[0] for row in rows}, self.names)
        for name, digest, size in rows:
            if name.endswith("RECORD"):
                continue
            data = self.zip.read(name)
            expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            self.assertEqual((digest, size), (expected, str(len(data))), name)

    def test_one_version_source(self):
        info = "ail_lang-%s.dist-info/" % source_version()
        metadata = self.zip.read(info + "METADATA").decode("utf-8")
        self.assertIn("\nName: ail-lang\n", metadata)
        self.assertIn("\nVersion: %s\n" % source_version(), metadata)
        self.assertIn("ail = ail_lang.cli:main", self.zip.read(info + "entry_points.txt").decode("utf-8"))
        pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('dynamic = ["version"]', pyproject)
        self.assertNotIn("\nversion =", pyproject)
        self.assertEqual(wheel_path.name, "ail_lang-%s-py3-none-any.whl" % source_version())

    def test_license_metadata_and_files(self):
        info = "ail_lang-%s.dist-info/" % source_version()
        metadata = self.zip.read(info + "METADATA").decode("utf-8")
        header = metadata.split("\n\n", 1)[0].splitlines()
        self.assertIn("License-Expression: MIT OR Apache-2.0", header)
        for name in LICENSE_FILES:
            self.assertIn("License-File: " + name, header)
            self.assertEqual(self.zip.read(info + "licenses/" + name), (REPO / name).read_bytes())
            self.assertEqual(self.zip.read("ail_lang/sdk/" + name), (REPO / name).read_bytes())
        pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('license = "MIT OR Apache-2.0"', pyproject)
        self.assertIn('license-files = ["LICENSE-APACHE", "LICENSE-MIT"]', pyproject)
        self.assertEqual(hashlib.sha256((REPO / "LICENSE-APACHE").read_bytes()).hexdigest(),
                         "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")

    def test_build_is_reproducible(self):
        with tempfile.TemporaryDirectory() as other:
            done = subprocess.run(
                [sys.executable, "-c",
                 "import sys; sys.path.insert(0, 'packaging'); import ail_wheel_backend as b; print(b.build_wheel(sys.argv[1]))",
                 other], cwd=REPO, capture_output=True, text=True, timeout=300)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual((Path(other) / done.stdout.strip()).read_bytes(), wheel_path.read_bytes())

    def test_sdist_is_refused(self):
        done = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'packaging'); import ail_wheel_backend as b; b.build_sdist('.')"],
            cwd=REPO, capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("wheel only", done.stderr)


HELLO = 'def main() -> None:\n    print("hello, world")\n\nmain()\n'

SHAPES = '''SCALE = 3


def area(w: int, h: int) -> int:
    return w * h
'''

MULTI = '''import shapes
from shapes import area as rect_area


def main() -> None:
    print(rect_area(3, 4) * shapes.SCALE)
    print(shapes.area(5, 6))


main()
'''

PATHS = '''from pathlib import Path


def main() -> None:
    root = Path("work")
    root.mkdir(parents=True, exist_ok=True)
    f = root / "a.txt"
    f.write_text("hello\\n")
    print(f.name, f.stem, f.suffix, f.parent, f.read_text().strip(), f.exists())
    names: list[str] = []
    for q in sorted(root.iterdir()):
        names.append(q.name)
    print(names)


main()
'''

FFI = '''from ail_ffi import *


@extern(lib="c", header="string.h", symbol="strlen")
def c_strlen(s: c_char_p) -> c_size_t: ...


@extern(lib="c", header="stdlib.h", symbol="abs")
def c_abs(x: c_int) -> c_int: ...


@extern(lib="m", header="math.h", symbol="sqrt")
def c_sqrt(x: c_double) -> c_double: ...


def main() -> None:
    print(c_strlen("héllo"), c_abs(-7), c_sqrt(2.25))


main()
'''


@unittest.skipUnless(CC, "no C compiler on this machine")
class InstalledWheel(unittest.TestCase):
    """The wheel in a fresh venv. pip comes from ensurepip (bundled with Python); nothing is downloaded."""

    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="ail-venv-test-"))
        venv = cls.base / "venv"
        made = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True, text=True, timeout=300)
        scripts = venv / ("Scripts" if os.name == "nt" else "bin")
        cls.python = scripts / ("python.exe" if os.name == "nt" else "python")
        cls.ail = scripts / ("ail.exe" if os.name == "nt" else "ail")
        if made.returncode or not cls.python.is_file():
            shutil.rmtree(cls.base, ignore_errors=True)
            raise unittest.SkipTest("cannot create a venv with pip offline: " + made.stderr[-200:])
        # Build through pip (the PEP 517 path of `pip install ail-lang` from this tree), then install offline.
        built = cls.base / "built"
        done = subprocess.run([str(cls.python), "-m", "pip", "wheel", "--no-deps", "--no-index", "-q",
                               "-w", str(built), str(REPO)], capture_output=True, text=True, timeout=600)
        if done.returncode:
            shutil.rmtree(cls.base, ignore_errors=True)
            raise unittest.SkipTest("pip wheel failed offline: " + done.stderr[-300:])
        cls.pip_wheel = next(built.glob("*.whl"))
        done = subprocess.run([str(cls.python), "-m", "pip", "install", "--no-deps", "--no-index", "-q",
                               str(cls.pip_wheel)], capture_output=True, text=True, timeout=600)
        if done.returncode:
            raise RuntimeError("pip install failed: " + done.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="ail-prog-", dir=self.base))
        self.cache = self.dir / "cache"

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AIL_NO_CACHE", "AIL_CACHE", "PYTHONPATH", "XDG_CACHE_HOME", "AIL_EXTRA_CFLAGS")}
        env.update(AIL_CACHE=str(self.cache), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        env.update(extra)
        return env

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf-8")

    def ail_run(self, *args, env=None, cwd=None):
        return subprocess.run([str(self.ail), *args], cwd=cwd or self.dir, env=env or self.env(),
                              capture_output=True, text=True, encoding="utf-8", timeout=300)

    def cpython(self, name, **extra):
        oracle = self.dir / "oracle"
        oracle.mkdir(exist_ok=True)
        for item in self.dir.glob("*.py"):
            shutil.copy(item, oracle / item.name)
        done = subprocess.run([sys.executable, name], cwd=oracle, env=self.env(**extra),
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_version_and_integrity(self):
        done = self.ail_run("--version")
        self.assertEqual(done.stdout.strip(), "ail-lang " + source_version())
        done = self.ail_run("integrity")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["status"], "verified")
        done = subprocess.run([str(self.python), "-m", "ail_lang", "--version"], capture_output=True, text=True)
        self.assertEqual(done.stdout.strip(), "ail-lang " + source_version())

    def test_hello_run_build_check(self):
        self.write("hello.py", HELLO)
        done = self.ail_run("run", "hello.py")
        self.assertEqual((done.returncode, done.stdout), (0, "hello, world\n"), done.stderr)
        done = self.ail_run("build", "hello.py", "-o", "hello_bin")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        binary = self.dir / ("hello_bin.exe" if os.name == "nt" else "hello_bin")
        self.assertEqual(subprocess.run([str(binary)], capture_output=True, text=True).stdout, "hello, world\n")
        done = self.ail_run("check", "hello.py")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(json.loads(done.stdout)["status"], "passed")
        self.write("bad.py", "def main() -> int:\n    return \"x\" + 1\n")
        done = self.ail_run("check", "bad.py")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(json.loads(done.stdout)["status"], "failed")

    def test_run_passes_arguments_and_exit_status(self):
        self.write("args.py", 'import sys\n\n\ndef main() -> None:\n    print(len(sys.argv))\n    sys.exit(3)\n\nmain()\n')
        done = self.ail_run("run", "args.py", "one", "two")
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertEqual(done.stdout, "3\n")

    def test_multi_module_program(self):
        self.write("shapes.py", SHAPES)
        self.write("main.py", MULTI)
        done = self.ail_run("run", "main.py")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, self.cpython("main.py"))
        self.assertEqual(done.stdout, "36\n30\n")

    def test_pathlib_program(self):
        if sys.platform == "win32":
            self.skipTest("pathlib is built for POSIX targets")
        self.write("paths.py", PATHS)
        done = self.ail_run("run", "paths.py")
        self.assertEqual(done.returncode, 0, done.stderr)
        shutil.rmtree(self.dir / "work", ignore_errors=True)
        self.assertEqual(done.stdout, self.cpython("paths.py"))
        self.assertIn("a.txt a .txt work hello True", done.stdout)

    def test_ffi_program(self):
        if sys.platform == "win32":
            self.skipTest("the libc/libm names are POSIX")
        self.write("ffi.py", FFI)
        done = self.ail_run("run", "ffi.py")
        self.assertEqual(done.returncode, 0, done.stderr)
        sdk = Path(subprocess.run([str(self.python), "-c", "import ail_lang, pathlib; print(pathlib.Path(ail_lang.__file__).parent / 'sdk')"],
                                  capture_output=True, text=True).stdout.strip())
        self.assertEqual(done.stdout, self.cpython("ffi.py", PYTHONPATH=str(sdk)))
        self.assertEqual(done.stdout, "6 7 1.5\n")

    def test_no_c_compiler_message(self):
        self.write("hello.py", HELLO)
        empty = self.dir / "empty-path"
        empty.mkdir()
        env = self.env(PATH=str(empty))
        env.pop("PIPE_CC", None)
        env.pop("AIL_ZIG", None)
        for command in ("run", "build"):
            done = subprocess.run([str(self.python), "-m", "ail_lang", command, "hello.py"], cwd=self.dir, env=env,
                                  capture_output=True, text=True, encoding="utf-8", timeout=120)
            self.assertEqual(done.returncode, 2, done.stdout)
            self.assertIn("no C compiler found", done.stderr)
            for name in ("cc", "clang", "gcc", "zig"):
                self.assertIn(name, done.stderr)
        done = subprocess.run([str(self.python), "-m", "ail_lang", "run", "hello.py"], cwd=self.dir,
                              env=dict(env, PIPE_CC=str(empty / "missing-cc")), capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("does not resolve", done.stderr)
        # type checking needs no C compiler
        done = subprocess.run([str(self.python), "-m", "ail_lang", "check", "hello.py"], cwd=self.dir, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    @unittest.skipIf(os.name == "nt", "the build cache is off on Windows")
    def test_cache_is_per_user(self):
        self.write("hello.py", HELLO)
        home = self.dir / "home"
        home.mkdir()
        env = self.env(HOME=str(home))
        env.pop("AIL_CACHE")
        env.pop("XDG_CACHE_HOME", None)
        if sys.platform == "darwin":
            expected = home / "Library" / "Caches" / "ail"
        else:
            expected = home / ".cache" / "ail"
        done = self.ail_run("cache", "path", env=env)
        self.assertEqual(Path(done.stdout.strip()), expected, done.stderr)
        done = self.ail_run("run", "hello.py", env=env)
        self.assertEqual(done.stdout, "hello, world\n", done.stderr)
        self.assertTrue(expected.is_dir())
        self.assertEqual(expected.stat().st_mode & 0o022, 0)
        stats = json.loads(self.ail_run("cache", "stats", env=env).stdout)
        self.assertGreater(stats["entries"], 0, stats)
        # a second run is served from the cache and prints the same
        self.assertEqual(self.ail_run("run", "hello.py", env=env).stdout, "hello, world\n")
        # a cache directory that another user owns is not used
        if os.geteuid() != 0:
            other = self.dir / "root-cache"
            other.mkdir()
            code = ("import os, sys; sys.argv=['ail']; from ail_lang import cli; "
                    "os.geteuid = lambda: os.stat(%r).st_uid + 1; "
                    "env = {'AIL_CACHE': %r}; cli.prepare_cache(env); print(env.get('AIL_NO_CACHE'))" % (str(other), str(other)))
            done = subprocess.run([str(self.python), "-c", code], capture_output=True, text=True)
            self.assertEqual(done.stdout.strip(), "1", done.stderr)


if __name__ == "__main__":
    unittest.main()
