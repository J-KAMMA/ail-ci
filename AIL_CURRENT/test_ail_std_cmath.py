"""The twelve real `cmath` programs in lab/stdlib/cmath, against CPython 3.12.

Each source is copied into a temporary directory, built with the default command
(`compile X.py --syntax python`, so the typed path may fall back to the general path) and run;
stdout and the exit code must be identical to CPython's.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "cmath"

PROGRAMS = (
    "branch_cuts.py",
    "error_handling.py",
    "filter_response.py",
    "impedance.py",
    "inverse_trig.py",
    "log_transform.py",
    "mandelbrot.py",
    "phasors.py",
    "quadratic.py",
    "rotation.py",
    "trig_identities.py",
    "wave_superposition.py",
)


REGRESSIONS = '''\
import cmath


def show(label, f):
    try:
        print(label, repr(f()))
    except Exception as e:
        print(label, type(e).__name__ + ": " + str(e))


show("pow inf", lambda: (2+0j) ** float("inf"))
show("pow -inf", lambda: (2+0j) ** float("-inf"))
show("pow nan", lambda: (2+0j) ** float("nan"))
show("zero -1", lambda: 0j ** -1)
show("zero -1j", lambda: 0j ** (-1j))
show("zero nan", lambda: 0j ** float("nan"))
show("log base 1", lambda: cmath.log(2.0, 1.0))
show("log base 1j", lambda: cmath.log(2.0, 1j))
show("complex real kw", lambda: complex(real=1+2j))
show("complex two args", lambda: complex(1+2j, 3))
show("complex two complex", lambda: complex(1+2j, 3+4j))
show("complex imag kw", lambda: complex(imag=1+2j))
show("rect complex", lambda: cmath.rect(1+0j, 0.0))
show("rect str", lambda: cmath.rect("1", 0.0))
show("isclose 3pos", lambda: cmath.isclose(1.0, 1.0, 1e-9))
show("isclose kw", lambda: cmath.isclose(1.0, 1.0, rel_tol=1e-9))
show("bad ++1j", lambda: complex("++1j"))
show("bad 1++2j", lambda: complex("1++2j"))
show("complex str,2", lambda: complex("1", 2))
show("complex 1,str", lambda: complex(1, "2"))
show("sqrt str", lambda: cmath.sqrt("4"))
show("log base kw", lambda: cmath.log(8.0, base=2.0))
show("exp z kw", lambda: cmath.exp(z=1.0))
show("signs", lambda: repr(complex(-0.0, -0.0)))
show("signs phase", lambda: cmath.phase(complex(-0.0, -0.0)))
'''


class CmathLabTests(unittest.TestCase):
    def test_review_regressions(self):
        with tempfile.TemporaryDirectory() as directory:
            name = "regressions.py"
            Path(directory, name).write_text(REGRESSIONS, encoding="utf-8")
            built = subprocess.run(
                [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", name,
                 "--syntax", "python", "-o", "regressions"],
                cwd=directory, capture_output=True, text=True, timeout=900,
                env=dict(os.environ, AIL_NO_CACHE="1"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(Path(directory, "regressions"))], cwd=directory,
                                 capture_output=True, timeout=300)
            expected = subprocess.run([sys.executable, name], cwd=directory,
                                      capture_output=True, timeout=300)
            self.assertEqual((ran.returncode, ran.stdout),
                             (expected.returncode, expected.stdout), ran.stderr[:500])

    def test_programs_match_cpython(self):
        for name in PROGRAMS:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                source = Path(directory, name)
                source.write_text((LAB / name).read_text(encoding="utf-8"), encoding="utf-8")
                exe = name[:-3]
                built = subprocess.run(
                    [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", name,
                     "--syntax", "python", "-o", exe],
                    cwd=directory, capture_output=True, text=True, timeout=900,
                    env=dict(os.environ, AIL_NO_CACHE="1"))
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(Path(directory, exe))], cwd=directory,
                                     capture_output=True, timeout=300)
                expected = subprocess.run([sys.executable, name], cwd=directory,
                                          capture_output=True, timeout=300)
                self.assertEqual((ran.returncode, ran.stdout),
                                 (expected.returncode, expected.stdout), ran.stderr[:500])


if __name__ == "__main__":
    unittest.main()
