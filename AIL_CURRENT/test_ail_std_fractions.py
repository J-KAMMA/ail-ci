"""The 12 real `fractions` programs in lab/stdlib/fractions, against CPython 3.12.

Each source is copied into a temporary directory, built with the default command
(`compile X.py --syntax python`, so the typed path may fall back to the general path)
and run with the same stdin as CPython.  stdout and the exit code must be identical.
The unit-conversion program is run twice: with empty stdin and with a small input.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "fractions"

INPUTS = {
    "unit_convert": [
        b"",
        b"12 inch\n1/2 foot\n3 yard\n1 mile\n\nbad line here\n9.5 inch\n1/0 foot\n7 mile\n",
    ],
}


def cases():
    found = {p.stem: p for p in sorted(PROGRAMS.glob("*.py"))}
    for stem in INPUTS:
        assert stem in found, "missing lab program %s.py" % stem
    return found


class FractionsPrograms(unittest.TestCase):
    def test_lab_programs_match_cpython(self):
        for stem, source in cases().items():
            with self.subTest(program=stem), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                src = directory / (stem + ".py")
                src.write_bytes(source.read_bytes())
                exe = directory / "exe"
                built = subprocess.run(
                    [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", src.name,
                     "--syntax", "python", "-o", exe.name],
                    cwd=directory, capture_output=True, text=True, timeout=900,
                    env=dict(os.environ, AIL_NO_CACHE="1"))
                self.assertEqual(built.returncode, 0,
                                 "%s did not build:\n%s\n%s" % (stem, built.stdout, built.stderr))
                for stdin in INPUTS.get(stem, [b""]):
                    want = subprocess.run([sys.executable, "-B", src.name], cwd=directory,
                                          input=stdin, capture_output=True, timeout=120)
                    got = subprocess.run([str(exe)], cwd=directory, input=stdin,
                                         capture_output=True, timeout=120)
                    self.assertEqual(
                        (got.returncode, got.stdout), (want.returncode, want.stdout),
                        "%s with stdin %r\nexit %r != %r\nstderr:\n%s" % (
                            stem, stdin, got.returncode, want.returncode,
                            got.stderr.decode("utf-8", "replace")))

    def test_round_keyword_boundaries(self):
        source = r"""from fractions import Fraction


def num():
    print("eval number")
    return 2.5


def dig():
    print("eval ndigits")
    return 1


f = Fraction(1, 3)
print(round(number=f), round(number=f, ndigits=2), round(ndigits=3, number=f))
print(round(12345, ndigits=-2), round(number=2.5, ndigits=1))
print(round(number=num(), ndigits=dig()))
print(round(ndigits=dig(), number=num()))
print(round(num(), ndigits=dig()))
"""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            src = directory / "round_kw.py"
            src.write_text(source)
            built = subprocess.run(
                [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", src.name,
                 "--syntax", "python", "-o", "exe"], cwd=directory, capture_output=True,
                text=True, timeout=900, env=dict(os.environ, AIL_NO_CACHE="1"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            want = subprocess.run([sys.executable, "-B", src.name], cwd=directory,
                                  capture_output=True, timeout=120)
            got = subprocess.run([str(directory / "exe")], cwd=directory,
                                 capture_output=True, timeout=120)
            self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout))

            bad = directory / "round_missing.py"
            bad.write_text("print(round(ndigits=2))\n")
            refused = subprocess.run(
                [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", bad.name,
                 "--syntax", "python", "-o", "bad"], cwd=directory, capture_output=True,
                text=True, timeout=900, env=dict(os.environ, AIL_NO_CACHE="1"))
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("round() missing required argument number", refused.stdout + refused.stderr)


if __name__ == "__main__":
    unittest.main()
