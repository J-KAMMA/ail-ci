"""stdstat1: `import stat` in compiled programs (bundled stdlib/stat.py) against CPython's stat.

The twelve programs in lab/stdlib/stat/ use only fixed mode integers (os.stat is not built): file
kind predicates, S_IMODE/S_IFMT, filemode on regular, directory, symlink, character, block, fifo,
socket, setuid, setgid and sticky modes, the S_I* permission constants with | and &, the ST_*
indices, UF_*/SF_* flags, a 4096-mode filemode checksum, and a mode beyond int64.

Every passing program is compiled with the default command and with AIL_UNIFIED_FORCE=1 and run
beside `python3` on the same source; stdout and the exit status must agree.  09_beyond_int64.py
builds typed but stops loudly when the runtime int64 overflow is reached, so it is not compared
(see lab/stdlib/stat/RESULTS.md).  The default and --strict builds must reach the typed path.

A pure-Python check compares the bundled filemode(m) with CPython's for every m in
range(0, 0o200000).
"""
import importlib.util
import os
import shutil
import stat as cpython_stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "stat"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

NAMES = ["01_file_kinds.py", "02_imode_ifmt.py", "03_filemode_basic.py",
         "04_special_bits.py", "05_permission_constants.py", "06_stat_indices.py",
         "07_flags.py", "08_filemode_loop.py", "09_beyond_int64.py",
         "10_filemode_expected.py", "11_kind_names.py", "12_permission_report.py"]

# 09_beyond_int64.py stops loudly at the int64 overflow, as CPython's ints are unbounded.
PASSING = [name for name in NAMES if name != "09_beyond_int64.py"]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


class StdlibStatPureTests(unittest.TestCase):
    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in sorted(PROGRAMS.glob("*.py"))], NAMES)

    def test_filemode_matches_cpython(self):
        spec = importlib.util.spec_from_file_location("ail_bundled_stat",
                                                      ROOT / "stdlib" / "stat.py")
        bundled = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bundled)
        for mode in range(0, 0o200000):
            if bundled.filemode(mode) != cpython_stat.filemode(mode):
                self.fail("filemode(%d): %r != %r"
                          % (mode, bundled.filemode(mode), cpython_stat.filemode(mode)))
        self.assertEqual(bundled.S_IFMT(0o104755), cpython_stat.S_IFMT(0o104755))
        self.assertEqual(bundled.S_IMODE(0o104755), cpython_stat.S_IMODE(0o104755))


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibStatBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-stat-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def build(self, source, name, forced=False, strict=False):
        work = self.dir / (name + ("-general" if forced else "") + ("-strict" if strict else ""))
        work.mkdir(exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        exe = work / (source.stem + ".out")
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if forced:
            env["AIL_UNIFIED_FORCE"] = "1"
        cmd = [sys.executable, "-B", CLI, "compile", str(program),
               "--syntax", "python", "-o", str(exe)]
        if strict:
            cmd.append("--strict")
        built = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True,
                               timeout=600, env=env)
        return built, program, exe

    def assert_program(self, source, forced=False):
        tag = "general" if forced else "default"
        built, program, exe = self.build(source, source.stem, forced=forced)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        if not forced:
            self.assertNotIn("built on the general path", built.stderr,
                             "%s did not use the typed path" % source.name)
        expected = run_cpython(program)
        ran = subprocess.run([str(exe)], cwd=str(program.parent), capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(ran.returncode, expected.returncode,
                         "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                         % (source.name, tag, expected.stderr, ran.stderr))
        self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (source.name, tag))

    def test_programs_match_cpython(self):
        for name in PASSING:
            source = PROGRAMS / name
            with self.subTest(program=name):
                self.assert_program(source)
            with self.subTest(program=name, build="general"):
                self.assert_program(source, forced=True)

    def test_typed_programs_build_strict(self):
        for name in NAMES:
            source = PROGRAMS / name
            with self.subTest(program=name):
                built, _program, _exe = self.build(source, source.stem, strict=True)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertNotIn("built on the general path", built.stderr)


if __name__ == "__main__":
    unittest.main()
