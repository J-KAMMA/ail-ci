"""AIL projects (packaging/ail_lang/project.py and cli.py): `ail new`, ail.toml / [tool.ail], and the
no-argument `ail build` / `ail run` / `ail check`.

* the config is read from ail.toml or [tool.ail] of pyproject.toml (ail.toml wins); unknown keys, wrong types, a
  missing entry and bad link names are refused by name; the Python 3.10 reader gives what tomllib gives;
* `ail new NAME` writes ail.toml, src/main.py and .gitignore, and refuses an existing directory;
* `ail build` in a project (also from a subdirectory) writes build/NAME, again over the old one; `--debug` writes
  build/NAME-debug; `ail run` builds to a temporary file and runs; `ail check` checks the entry;
* `link = [...]` reaches the linker (a missing library fails the link by name) and `strict = true` stops a
  program that would run on the slow general path.

Building needs a C compiler (skipped without one). Skipped when packaging/ is not beside this directory.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGING = ROOT.parent / "packaging"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
BLOCKER = ("def find(d: dict[int, int], k: int) -> int | None:\n    return d.get(k)\n\n\n"
           "def main() -> None:\n    print(find({1: 2}, 1))\n\n\nmain()\n")


def setUpModule():
    if not (PACKAGING / "ail_lang" / "project.py").is_file():
        raise unittest.SkipTest("packaging/ail_lang is not beside AIL_CURRENT")
    sys.path.insert(0, str(PACKAGING))


def tearDownModule():
    if str(PACKAGING) in sys.path:
        sys.path.remove(str(PACKAGING))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-project-test-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def ail(self, *args, cwd=None, env=None):
        environment = dict(os.environ, PYTHONPATH=str(PACKAGING), AIL_SDK_DIR=str(ROOT), PYTHONUTF8="1",
                           AIL_CACHE=str(self.dir / "cache"))
        environment.pop("AIL_NO_CACHE", None)
        environment.update(env or {})
        return subprocess.run([sys.executable, "-B", "-m", "ail_lang", *args], cwd=cwd or self.dir, env=environment,
                              capture_output=True, text=True, encoding="utf-8", timeout=600)

    def write(self, name, text):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class Config(Base):
    def setUp(self):
        super().setUp()
        from ail_lang import project
        self.project = project
        self.write("src/main.py", "print(1)\n")

    def load(self, text, name="ail.toml"):
        path = self.write(name, text)
        return self.project.load(path)

    def test_a_full_config(self):
        (self.dir / "lib").mkdir()
        loaded = self.load('name = "demo"\nentry = "src/main.py"\nlink = ["z", "m"]\nstrict = true\n'
                           'module_path = ["lib"]\n')
        self.assertEqual((loaded.name, loaded.link, loaded.strict), ("demo", ["z", "m"], True))
        self.assertEqual(loaded.entry, (self.dir / "src" / "main.py").resolve())
        self.assertEqual(loaded.build_options(), ["-I", str((self.dir / "lib").resolve()), "--link", "z", "--link", "m"])
        self.assertEqual(loaded.output, self.dir.resolve() / "build" / "demo")

    def test_defaults(self):
        loaded = self.load('entry = "src/main.py"\n')
        self.assertEqual((loaded.link, loaded.strict, loaded.module_path), ([], False, []))
        self.assertEqual(loaded.name, self.dir.name)

    def test_refusals_name_the_problem(self):
        cases = [
            ('entry = "src/main.py"\nstrcit = true\n', "unknown key 'strcit'"),
            ('name = "x"\n', "entry is required"),
            ('entry = "src/missing.py"\n', "is not an existing"),
            ('entry = "src/main.py"\nstrict = "yes"\n', "strict must be true or false"),
            ('entry = "src/main.py"\nlink = "z"\n', "link must be a list"),
            ('entry = "src/main.py"\nlink = ["-lz; rm"]\n', "plain library names"),
            ('entry = "src/main.py"\nname = "9bad"\n', "name '9bad'"),
            ('entry = "src/main.py"\nmodule_path = ["nowhere"]\n', "is not a directory"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                with self.assertRaises(self.project.ProjectError) as raised:
                    self.load(text)
                self.assertIn(expected, str(raised.exception))

    def test_pyproject_and_precedence(self):
        self.write("pyproject.toml", '[project]\nname = "other"\n\n[tool.ail]\nentry = "src/main.py"\nlink = ["m"]\n')
        found = self.project.find(self.dir / "src")
        self.assertEqual((found.config_file.name, found.link), ("pyproject.toml", ["m"]))
        self.write("ail.toml", 'entry = "src/main.py"\nlink = ["z"]\n')
        self.assertEqual(self.project.find(self.dir / "src").link, ["z"])

    def test_a_pyproject_without_tool_ail_is_skipped(self):
        self.write("pyproject.toml", '[project]\nname = "other"\n')
        nested = self.dir / "inner"
        self.write("inner/ail.toml", 'entry = "../src/main.py"\n')
        self.assertEqual(self.project.find(nested).config_file.parent, nested.resolve())

    def test_the_python_310_reader_matches_tomllib(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest("no tomllib: the subset reader is the reader")
        text = ('# comment\nname = "a#b"   # trailing\nentry = \'src/main.py\'\nstrict = true\nn = 3\n'
                'link = [\n  "z",   # zlib\n  "m",\n]\n\n[tool.ail]\nmodule_path = ["a", "b"]\n')
        self.assertEqual(self.project._read_toml_subset(text, "t"), tomllib.loads(text))
        with self.assertRaises(self.project.ProjectError):
            self.project._read_toml_subset("link = [\n  1,\n", "t")


class Scaffold(Base):
    def test_new_writes_a_project_that_loads(self):
        done = self.ail("new", "hello_app")
        self.assertEqual(done.returncode, 0, done.stderr)
        root = self.dir / "hello_app"
        self.assertTrue((root / "ail.toml").is_file() and (root / "src" / "main.py").is_file())
        self.assertEqual((root / ".gitignore").read_text(), "build/\n")
        from ail_lang import project
        loaded = project.find(root)
        self.assertEqual((loaded.name, loaded.strict, loaded.link), ("hello_app", False, []))

    def test_new_refuses_an_existing_directory_and_a_bad_name(self):
        (self.dir / "taken").mkdir()
        done = self.ail("new", "taken")
        self.assertEqual(done.returncode, 2)
        self.assertIn("already exists", done.stderr)
        done = self.ail("new", "1-bad")
        self.assertEqual(done.returncode, 2)
        self.assertIn("must start with a letter", done.stderr)
        self.assertEqual(self.ail("new").returncode, 2)

    def test_check_works_without_a_c_compiler_and_needs_a_project_otherwise(self):
        self.assertEqual(self.ail("new", "chk").returncode, 0)
        done = self.ail("check", cwd=self.dir / "chk" / "src")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('"status": "passed"', done.stdout)
        empty = self.dir / "empty"
        empty.mkdir()
        done = self.ail("check", cwd=empty)
        self.assertEqual(done.returncode, 2)
        self.assertIn("ail new NAME", done.stderr)


@unittest.skipUnless(CC, "no C compiler")
class Build(Base):
    def new(self, name="demo"):
        self.assertEqual(self.ail("new", name).returncode, 0)
        return self.dir / name

    def test_build_writes_the_program_again_and_from_a_subdirectory(self):
        root = self.new()
        for where in (root, root / "src", root):
            done = self.ail("build", cwd=where)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("built", done.stdout)
            self.assertNotIn('"sha256"', done.stdout)
        program = root / "build" / "demo"
        self.assertEqual(subprocess.run([str(program)], capture_output=True, text=True).stdout, "hello from demo\n")
        self.assertEqual([p.name for p in (root / "build").iterdir()], ["demo"])      # no temporary left behind

    def test_run_and_debug_build(self):
        root = self.new("runner")
        done = self.ail("run", cwd=root)
        self.assertEqual((done.returncode, done.stdout), (0, "hello from runner\n"), done.stderr)
        self.assertFalse((root / "build").exists())
        done = self.ail("build", "--debug", cwd=root)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((root / "build" / "runner-debug").is_file())

    def test_explicit_output_and_file_mode_still_work(self):
        root = self.new("plain")
        out = self.dir / "elsewhere"
        done = self.ail("build", "-o", str(out), cwd=root)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(out.is_file())
        source = self.write("single.py", "print(2 + 3)\n")
        done = self.ail("run", str(source))
        self.assertEqual((done.returncode, done.stdout), (0, "5\n"), done.stderr)

    def test_link_reaches_the_linker(self):
        root = self.new("linked")
        config = root / "ail.toml"
        config.write_text(config.read_text().replace("link = []", 'link = ["ail_no_such_library"]'))
        done = self.ail("build", cwd=root)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("ail_no_such_library", done.stdout + done.stderr)
        config.write_text(config.read_text().replace('"ail_no_such_library"', '"m"'))
        done = self.ail("build", cwd=root)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_strict_stops_a_general_path_program(self):
        root = self.new("strictly")
        (root / "src" / "main.py").write_text(BLOCKER, encoding="utf-8")
        done = self.ail("build", cwd=root)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("general path", done.stderr)
        self.assertEqual(subprocess.run([str(root / "build" / "strictly")], capture_output=True, text=True).stdout,
                         "2\n")
        config = root / "ail.toml"
        config.write_text(config.read_text().replace("strict = false", "strict = true"))
        done = self.ail("build", cwd=root)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("int | None", done.stdout + done.stderr)
        self.assertIn("write instead:", done.stdout + done.stderr)

    def test_a_broken_config_is_reported_not_built(self):
        root = self.new("broken")
        (root / "ail.toml").write_text('entry = "src/main.py"\nstrcit = true\n')
        done = self.ail("build", cwd=root)
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown key 'strcit'", done.stderr)


if __name__ == "__main__":
    unittest.main()
