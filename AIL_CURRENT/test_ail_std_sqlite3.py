"""The sqlite3 programs of lab/stdlib/sqlite3: each passing program is compiled in the default mode and
must print what CPython prints (stdout and exit code).

The programs cover qmark and named parameters, executemany and aggregates, fetchone loops, `with conn:`,
IntegrityError, rowcount / lastrowid, NULLs, unicode, REAL repr, int64 boundaries, executescript and a JOIN.
The default build takes every one of them on the typed path (no `general path` note). Unsupported features
stay refused by name, and the general path refuses sqlite3 with its own named message.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "sqlite3"
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = (
    "01_basic_crud.py",
    "02_named_params.py",
    "03_bulk_aggregate.py",
    "04_fetchone_loop.py",
    "05_transactions.py",
    "06_unique_error.py",
    "07_rowcount_lastrowid.py",
    "08_nulls.py",
    "09_unicode.py",
    "10_reals_repr.py",
    "11_bigints.py",
    "12_join_script.py",
)

REFUSED = {
    "fetchmany.py": (
        "import sqlite3\n\n\ndef main() -> None:\n    conn = sqlite3.connect(':memory:')\n"
        "    cur = conn.execute('select 1')\n    cur.fetchmany(1)\n\n\nmain()\n",
        "fetchmany is not built",
    ),
    "row_factory.py": (
        "import sqlite3\n\n\ndef main() -> None:\n    conn = sqlite3.connect(':memory:')\n"
        "    conn.row_factory = sqlite3.Row\n\n\nmain()\n",
        "row_factory is not built",
    ),
}


def missing_reason():
    """Why this module cannot run here, or None."""
    try:
        import sqlite3  # noqa: F401  (the oracle)
    except ImportError:
        return "CPython's sqlite3 module (the oracle) is not available"
    if not CC:
        return "no C compiler"
    probe = '#include <sqlite3.h>\nint main(void) { return sqlite3_libversion_number() > 0 ? 0 : 1; }\n'
    with tempfile.TemporaryDirectory(prefix="ail-std-sqlite-probe-") as tmp:
        source = Path(tmp) / "probe.c"
        source.write_text(probe)
        done = subprocess.run([CC, str(source), "-o", str(Path(tmp) / "probe"), "-lsqlite3"],
                              capture_output=True, text=True)
        if done.returncode:
            return "libsqlite3 development files (sqlite3.h and -lsqlite3) are not installed"
    return None


def setUpModule():
    reason = missing_reason()
    if reason:
        raise unittest.SkipTest(reason)


def build_source(directory, name, text, env_extra=None):
    Path(directory, name).write_text(text, encoding="utf-8")
    exe = Path(directory) / name[:-3]
    env = dict(os.environ, AIL_NO_CACHE="1")
    env.pop("PYTHONPATH", None)
    env.update(env_extra or {})
    built = subprocess.run(
        [sys.executable, "-B", CLI, "compile", name, "--syntax", "python", "-o", str(exe)],
        cwd=directory, capture_output=True, text=True, timeout=900, env=env,
    )
    return built, exe


def compile_program(directory, name):
    return build_source(directory, name, (LAB / name).read_text(encoding="utf-8"))


class SqliteLabTests(unittest.TestCase):
    def test_passing_programs_match_cpython(self):
        for name in PASSING:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_program(directory, name)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertNotIn("general path", built.stderr, name)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=300)
                expected = subprocess.run([sys.executable, str(LAB / name)], capture_output=True, timeout=300)
                self.assertEqual(expected.returncode, 0, expected.stderr)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                 ran.stderr[:500])

    def test_unsupported_features_stay_refused_by_name(self):
        for name, (source, wanted) in REFUSED.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                built, exe = build_source(directory, name, source)
                self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertIn(wanted, built.stderr)
                self.assertFalse(exe.exists())

    def test_the_general_path_refuses_sqlite3_by_name(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe = build_source(
                directory, "basic.py",
                (LAB / "01_basic_crud.py").read_text(encoding="utf-8"),
                env_extra={"AIL_UNIFIED_FORCE": "1"},
            )
            self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn("sqlite3 is built in typed code only", built.stderr)
            self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
