"""The lab/stdlib/csv programs that build: the compiled stdout and exit code equal CPython's.

Each program is ordinary Python using the csv module the way typical code does (reader / writer,
DictReader / DictWriter, dialect options, quoting modes, files, StringIO, empty input and the errors
the program catches). The compiler may take either path; only the output is compared.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
PROGRAMS = (
    "basic_roundtrip",
    "dialect_options",
    "dict_reader",
    "dict_writer",
    "empty_and_none",
    "error_handling",
    "file_roundtrip",
    "nonnumeric",
    "quoting_modes",
)


def build(directory, name, source=None, **extra):
    source = Path(source) if source is not None else REPO / "lab" / "stdlib" / "csv" / (name + ".py")
    exe = Path(directory) / name
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source),
         "--syntax", "python", "-o", str(exe)],
        cwd=directory, capture_output=True, text=True, timeout=900,
        env=dict(os.environ, AIL_NO_CACHE="1", **extra),
    )
    return result, source, exe


class StdCsvPrograms(unittest.TestCase):
    def test_programs_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in PROGRAMS:
                with self.subTest(program=name):
                    built, source, exe = build(directory, name)
                    self.assertEqual(built.returncode, 0, "%s\n%s%s" % (name, built.stdout, built.stderr))
                    want = subprocess.run([sys.executable, "-X", "utf8", str(source)], cwd=directory,
                                          capture_output=True, timeout=300)
                    got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=300)
                    self.assertEqual(got.returncode, want.returncode, name)
                    self.assertEqual(got.stdout, want.stdout, name)

    def check_source(self, text, name, **extra):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / (name + ".py")
            source.write_text(text, encoding="utf-8")
            built, source, exe = build(directory, name, source, **extra)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            want = subprocess.run([sys.executable, "-X", "utf8", str(source)], cwd=directory,
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode)
            self.assertEqual(got.stdout, want.stdout)

    def test_literal_stringio_list_reader(self):
        text = 'import csv, io\nprint(list(csv.reader(io.StringIO("a,b\\n"))))\n'
        self.check_source(text, "literal_list_reader")

    def test_file_reader_is_lazy(self):
        text = ('import csv, os\n'
                'p = "review_file.tmp"\n'
                'with open(p, "w", newline="") as f:\n'
                '    f.write("a,b\\nc,d\\n")\n'
                'f = open(p, newline="")\n'
                'r = csv.reader(f)\n'
                'with open(p, "w", newline="") as g:\n'
                '    g.write("x,y\\n")\n'
                'print(list(r))\n'
                'f.close()\n'
                'os.remove(p)\n')
        self.check_source(text, "lazy_file_reader")


if __name__ == "__main__":
    unittest.main()
