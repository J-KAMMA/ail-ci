"""Executable reproducibility: the same source in two build setups gives one byte-identical binary.

`lab/repro/RESULTS.md` records the whole-corpus measurement.  This test is the ratchet for it:
five small programs are built twice, once in a short path and once in a longer one, with a
different TMPDIR, HOME and SOURCE_DATE_EPOCH, and the sha256 of the executable and of the
generated C must agree.  The five come from the complete-corpus run recorded in that document;
when a difference is fixed, add its row there and to PROGRAMS here.

Skips without a C compiler (the compiler links `program.c` with it).
"""
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PROGRAMS = (
    ("stdlib/bisect/alias_import.py", "lab/stdlib/bisect/alias_import.py"),
    ("stdlib/heapq/closest_points.py", "lab/stdlib/heapq/closest_points.py"),
    ("examples/tutorial_project/step1.py", "examples/tutorial_project/step1.py"),
    ("examples/algos/rpn.py", "examples/algos/rpn.py"),
    ("compare/echo_pack", "lab/compare/src/echo_pack/main.py"),
)


def setup_environment(tmp, home, epoch, seed):
    env = {key: value for key, value in os.environ.items()
           if key not in ("AIL_CACHE", "AIL_NO_CACHE", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE",
                          "PYTHONHASHSEED", "TMPDIR", "HOME", "SOURCE_DATE_EPOCH")}
    env.update(AIL_NO_CACHE="1", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONHASHSEED=str(seed), TMPDIR=str(tmp), HOME=str(home),
               SOURCE_DATE_EPOCH=str(epoch))
    return env


def build(source, work, tmp, home, epoch, seed):
    work.mkdir(parents=True, exist_ok=True)
    program = work / source.name
    shutil.copyfile(source, program)
    out = work / "prog"
    done = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                           "-o", str(out), "--debug-dir", str(work / "debug")],
                          cwd=str(work), env=setup_environment(tmp, home, epoch, seed),
                          capture_output=True, text=True, timeout=900)
    return done, out, work / "debug" / "program.c"


def digest(data):
    return hashlib.sha256(data).hexdigest()


@unittest.skipUnless(CC, "installed C compiler required")
class ReproducibleBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-repro-test-")
        cls.dir = Path(cls.temp.name)
        cls.short = cls.dir / "a" / "x"
        cls.long = cls.dir / "b" / "longer" / "path" / "x"
        cls.tmp_a = cls.dir / "a" / "tmp"
        cls.tmp_b = cls.dir / "b" / "tmp"
        cls.home_a = cls.dir / "a" / "home"
        cls.home_b = cls.dir / "b" / "home"
        for path in (cls.short, cls.long, cls.tmp_a, cls.tmp_b, cls.home_a, cls.home_b):
            path.mkdir(parents=True, exist_ok=True)
        cls.builds = {}
        for name, relative in PROGRAMS:
            source = (REPO / relative).resolve()
            work = name.replace("/", "_")
            short = build(source, cls.short / work, cls.tmp_a, cls.home_a, 1000000000, 0)
            long = build(source, cls.long / work, cls.tmp_b, cls.home_b, 2000000000, 1)
            runs = []
            for root, built in ((cls.short / work, short), (cls.long / work, long)):
                done, exe, _ = built
                if done.returncode != 0:
                    runs.append(None)
                    continue
                ran = subprocess.run([str(exe.resolve())], cwd=str(root), input=b"",
                                     capture_output=True, timeout=120)
                runs.append((ran.returncode, ran.stdout))
            cls.builds[name] = (short, long, runs)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_same_source_gives_one_executable(self):
        for name, _ in PROGRAMS:
            first, first_exe, first_c = self.builds[name][0]
            second, second_exe, second_c = self.builds[name][1]
            with self.subTest(program=name):
                self.assertEqual(first.returncode, 0, first.stderr[-2000:])
                self.assertEqual(second.returncode, 0, second.stderr[-2000:])
                self.assertTrue(first_c.is_file(), "no program.c in the short-path build")
                self.assertTrue(second_c.is_file(), "no program.c in the long-path build")
                self.assertEqual(digest(first_c.read_bytes()), digest(second_c.read_bytes()),
                                 "program.c differs between the two build setups")
                self.assertEqual(digest(first_exe.read_bytes()), digest(second_exe.read_bytes()),
                                 "the executable differs between the two build setups")

    def test_both_setups_run_the_same(self):
        for name, _ in PROGRAMS:
            runs = self.builds[name][2]
            with self.subTest(program=name):
                self.assertEqual(runs[0], runs[1], "the two builds print or exit differently")


def load_checker():
    path = REPO / "tools" / "repro_check.py"
    spec = importlib.util.spec_from_file_location("ail_repro_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CheckerTests(unittest.TestCase):
    def test_absolute_path_in_uint16_literal_is_named(self):
        checker = load_checker()
        left = (b"static struct { int64_t n; uint16_t d[6]; } _lit1 = { 6, "
                b"{ 47, 116, 109, 112, 47, 97, 47, 120, 46, 112, 121 } };\n")
        right = (b"static struct { int64_t n; uint16_t d[18]; } _lit1 = { 18, "
                 b"{ 47, 116, 109, 112, 47, 98, 47, 108, 111, 110, 103, 101, 114, 47, 120, 46, 112, 121 } };\n")
        self.assertEqual(
            checker.classify_c(left, right, left.decode().strip(), right.decode().strip()),
            "absolute path")

    def test_ffi_path_hash_in_a_symbol_is_named(self):
        checker = load_checker()
        left = b"int64_t ffi_put_7a7acd(ail_bytearray *v_dst);\n"
        right = b"int64_t ffi_put_093756(ail_bytearray *v_dst);\n"
        self.assertEqual(
            checker.classify_c(left, right, left.decode().strip(), right.decode().strip()),
            "absolute path hash")

    def test_ffi_entry_c_is_compared_instead_of_missing_program_c(self):
        checker = load_checker()
        with tempfile.TemporaryDirectory() as name:
            debug = Path(name)
            (debug / "entry.c").write_bytes(b"int main(void) { return 0; }\n")
            self.assertEqual(checker.generated_c(debug),
                             ("entry.c", b"int main(void) { return 0; }\n"))
            (debug / "entry.c").unlink()
            self.assertEqual(checker.generated_c(debug), (None, None))

    def test_one_sided_build_failure_is_a_difference(self):
        checker = load_checker()
        good = {"returncode": 0, "stderr": "", "binary": b"ELF", "program_c": b"int main(void){}\n"}
        bad = {"returncode": 1, "stderr": "refused", "binary": None, "program_c": None}

        class Root:
            def __truediv__(self, other):
                return self

            def mkdir(self, *args, **kwargs):
                pass

        def fake_build(source, work, setup):
            return good if setup[2] == checker.EPOCH_A else bad

        with mock.patch.object(checker, "build", side_effect=fake_build), \
                mock.patch.object(checker, "run_binary", return_value=None):
            row = checker.one("probe/one-sided", REPO / "examples" / "algos" / "rpn.py",
                              Root(), Root())
        self.assertEqual(row["status"], "diff")
        self.assertTrue(row["one_sided"])
        self.assertTrue(row["built_a"])
        self.assertFalse(row["built_b"])


if __name__ == "__main__":
    unittest.main()
