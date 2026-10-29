"""Library batch 32: `unicodedata.name` / `category` / `normalize` (Unicode 15.0), compared with CPython.

Every program below is ordinary Python.  CPython 3.12 is the oracle; the compiled program must print the
same bytes on both builds -- the typed path (AIL_NO_GENERAL=1) and the default build (which may fall back
to the general path).  The data is generated from CPython by tools/gen_unicodedata.py:
categories, names (including the CJK / Khitan / Nushu and Hangul algorithmic ranges), canonical and
compatibility decompositions, combining classes and composition pairs.

Name and category run over representative code points of every category, the algorithmic-name ranges,
the decomposing characters and the unassigned/private-use code points without a name.  Normalize runs
the four forms over combining, Hangul, compatibility and singleton cases and over generated strings from
that pool.  The two-argument `name(ch, default)` form is built for a string constant default; everything
else in the module (`lookup`, `decomposition`, `combining`, `digit`, ..., `unidata_version`) and a
non-string default stay named compile-time refusals.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


# Code points with a name in Python 3.12 (the program catches ValueError for the ones without one).
POINTS = [
    0x0000, 0x0001, 0x0007, 0x0009, 0x000A, 0x000D, 0x001B, 0x001F, 0x0020, 0x0021, 0x0023, 0x0024,
    0x0030, 0x0039, 0x0041, 0x005A, 0x0061, 0x007A, 0x007B, 0x007E, 0x007F, 0x0080, 0x009F, 0x00A0,
    0x00A9, 0x00AD, 0x00B2, 0x00B5, 0x00C0, 0x00E9, 0x00F7, 0x00FF, 0x0100, 0x0130, 0x017F, 0x01C4,
    0x01F0, 0x02B0, 0x02C6, 0x0300, 0x0301, 0x0308, 0x0323, 0x0345, 0x0374, 0x0378, 0x037E, 0x0384,
    0x0391, 0x03A3, 0x03C2, 0x03D3, 0x0400, 0x0451, 0x05D0, 0x060C, 0x061C, 0x0627, 0x0660, 0x06F0,
    0x0903, 0x093F, 0x0958, 0x0B47, 0x0B3E, 0x0E33, 0x0F71, 0x0F72, 0x0F77, 0x10A0, 0x1100, 0x1161,
    0x11A8, 0x1E9B, 0x1F82, 0x2000, 0x200B, 0x2028, 0x2029, 0x20AC, 0x212B, 0x2126, 0x2190, 0x2460,
    0x24B6, 0x25CF, 0x3000, 0x3005, 0x3042, 0x30A2, 0x3400, 0x4E00, 0x9FFF, 0xA000, 0xA960, 0xAC00,
    0xAC01, 0xD7A3, 0xE000, 0xE001, 0xF900, 0xFA0E, 0xFB01, 0xFE0F, 0xFEFF, 0xFF21, 0xFF9E, 0xFFFD,
    0xFFFF, 0x10000, 0x17000, 0x18B00, 0x1B170, 0x1F600, 0x20000, 0x2A6A5, 0x2F800, 0xE0100,
]


def _source_points(points):
    """BMP points only: the general path has no non-BMP string literals."""
    return [cp for cp in points if cp <= 0xFFFF]


def name_program():
    chars = [ascii(chr(cp)) for cp in _source_points(POINTS)]
    return """import unicodedata


def main() -> None:
    chars = [%s]
    for ch in chars:
        try:
            print("N", unicodedata.name(ch))
        except ValueError:
            print("N", "NONE")
        print("C", unicodedata.category(ch))
    print("D", unicodedata.name("\\u0378", "NO NAME"))
    print("D", unicodedata.name("A", "fallback"))

main()
""" % ", ".join(chars)


NORMALIZE_EDGE = [
    "", "abc", "e\u0301", "\u00e9", "A\u030a", "\u1e9b\u0323", "\ufb01", "\uff21", "\u2460",
    "\uac00", "\u1100\u1161", "\u0f77", "\u212b", "\u03d3", "\u0958", "\u1f82", "a\u0301\u0323",
    "\u0b47\u0b3e", "\u0f71\u0f72", "x\u0301\u0302\u0303", "\u0345\u0301", "\u0301\u0300",
    "\u0e33", "\u2474", "\u2488", "\u1e9b", "\u01c4", "\u1fef", "\u2adc", "\u304c",
]


def normalize_texts():
    pool = [chr(cp) for cp in _source_points(POINTS) if unicodedata_is_interesting(chr(cp))]
    rng = random.Random(3200)
    texts = list(NORMALIZE_EDGE)
    for _ in range(140):
        n = rng.randint(0, 8)
        texts.append("".join(rng.choice(pool) for _ in range(n)))
    return texts


def unicodedata_is_interesting(ch):
    import unicodedata
    return unicodedata.combining(ch) != 0 or unicodedata.decomposition(ch) != "" or ch in " \u1100\u1161\u11a8"


def normalize_program():
    texts = [ascii(text) for text in normalize_texts()]
    return """import unicodedata


def main() -> None:
    forms = ["NFC", "NFD", "NFKC", "NFKD"]
    texts = [%s]
    for form in forms:
        for text in texts:
            print(form, repr(unicodedata.normalize(form, text)))
    print("empty", repr(unicodedata.normalize("NFC", "")))

main()
""" % ", ".join(texts)


IMPORT_PROGRAM = """import unicodedata as ud
from unicodedata import name, category, normalize


def main() -> None:
    print(ud.name("A"), name("B"), ud.category("A"), category("\\u00e9"))
    print(repr(ud.normalize("NFC", "e\\u0301")), repr(normalize("NFD", "\\u00e9")))
    print(ud.name("\\u0378", "none"))

main()
"""

ERROR_PROGRAM = """import unicodedata


def main() -> None:
    try:
        unicodedata.name("\\u0378")
    except ValueError as e:
        print("name", str(e))
    try:
        unicodedata.normalize("BAD", "x")
    except ValueError as e:
        print("form", str(e))
    print(unicodedata.name("\\u0378", "missing"))
    print(unicodedata.normalize("NFC", ""))

main()
"""


class Stdlib32Tests(unittest.TestCase):
    def run_both(self, text, name):
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, name + "_oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            self.assertEqual(want.returncode, 0, want.stderr[-800:])
            for label, env in (("typed", {"AIL_NO_GENERAL": "1"}), ("default", {})):
                with self.subTest(build=label):
                    built, source, exe = compile_python(directory, text, name + "_" + label, **env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                    self.assertEqual(got.returncode, 0, got.stderr[-800:])
                    self.assertEqual(got.stdout, want.stdout,
                                     "%s build differs:\n%s" % (label, got.stderr[-800:]))

    def refused(self, text, wanted, name="refused", **env):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name, **env)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    def test_names_and_categories_match_cpython(self):
        self.run_both(name_program(), "unicodedata_name")

    def test_normalize_matches_cpython(self):
        self.run_both(normalize_program(), "unicodedata_normalize")

    def test_import_forms_match_cpython(self):
        self.run_both(IMPORT_PROGRAM, "unicodedata_imports")

    def test_errors_match_cpython(self):
        self.run_both(ERROR_PROGRAM, "unicodedata_errors")

    def test_refusals_are_named(self):
        for label, env in (("typed", {"AIL_NO_GENERAL": "1"}), ("default", {})):
            with self.subTest(build=label):
                self.refused('import unicodedata\n\n\ndef main() -> None:\n'
                             '    print(unicodedata.lookup("LATIN CAPITAL LETTER A"))\n\n\nmain()\n',
                             "unicodedata.lookup is not built", name="lookup_" + label, **env)
                self.refused('import unicodedata\n\n\ndef main() -> None:\n'
                             '    print(unicodedata.unidata_version)\n\n\nmain()\n',
                             "unicodedata.unidata_version is not built", name="version_" + label, **env)
                self.refused('import unicodedata\n\n\ndef main() -> None:\n'
                             '    print(unicodedata.name("\\u0378", None))\n\n\nmain()\n',
                             "unicodedata.name default must be a string constant", name="default_" + label, **env)


if __name__ == "__main__":
    unittest.main()
