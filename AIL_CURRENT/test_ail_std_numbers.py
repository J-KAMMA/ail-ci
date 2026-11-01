"""The realistic `numbers` programs in lab/stdlib/numbers, compared with CPython 3.12.

Eleven of the twelve build in the default mode (on the general path, as the injected ABC
classes use operator methods); each must print CPython's stdout and exit with its status.
The twelfth uses a complex literal, which this runtime does not build, so it stays a named
refusal (see lab/stdlib/numbers/RESULTS.md).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "numbers"

PASSING = (
    "averages.py",
    "classify.py",
    "custom_number.py",
    "dispatch.py",
    "issubclass_report.py",
    "matrix_stats.py",
    "mixed_registry.py",
    "number_guard.py",
    "rationals.py",
    "registration.py",
    "result_kinds.py",
)

REFUSED = {
    "complex_literal.py": "a constant of type complex",
}

REGRESSIONS = {
    "fraction_subclass.py": """import numbers
from fractions import Fraction

class Half(Fraction):
    pass

def main():
    h = Half(1, 2)
    print(h, isinstance(h, numbers.Rational), isinstance(h, numbers.Real))
    print(issubclass(Half, numbers.Rational), issubclass(Half, numbers.Real))

main()
""",
    "user_named_fraction.py": """import numbers

class Fraction:
    def __init__(self, n):
        self.n = n

class Decimal:
    def __init__(self, s):
        self.s = s

def main():
    f = Fraction(1)
    d = Decimal("2")
    print(isinstance(f, numbers.Rational), isinstance(f, numbers.Real))
    print(isinstance(d, numbers.Number), isinstance(d, numbers.Real))
    print(issubclass(Fraction, numbers.Rational), issubclass(Decimal, numbers.Number))

main()
""",
    "register_timing.py": """import numbers

class A:
    pass

class B:
    pass

def setup():
    numbers.Real.register(B)

if False:
    numbers.Number.register(B)

print(isinstance(A(), numbers.Number))
print(issubclass(A, numbers.Real))
numbers.Number.register(A)
print(isinstance(A(), numbers.Number))
print(issubclass(A, numbers.Real))

def main():
    print(isinstance(B(), numbers.Real))
    setup()
    print(isinstance(B(), numbers.Real))

main()
""",
    "register_virtual.py": """import numbers

class Money:
    pass

class Sub(Money):
    pass

numbers.Real.register(Money)

print(hasattr(Money, "real"), hasattr(Money, "imag"), hasattr(Money, "conjugate"))
print(hasattr(Money(), "real"), hasattr(Money(), "imag"))
print(isinstance(Sub(), numbers.Real), issubclass(Sub, numbers.Real))
print(isinstance(Money(), numbers.Rational), isinstance(Money(), numbers.Number))
""",
    "tuple_and_nested.py": """import numbers

class A:
    pass

class B:
    pass

def main():
    a = A()
    b = B()
    print(isinstance(a, (A, B)), isinstance(1, (A, B)))
    print(isinstance(1, ((numbers.Integral,),)))
    print(isinstance(1.5, (A, (numbers.Real, B))))
    print(isinstance(b, (A, (numbers.Real, B))))

main()
""",
}

VALUE_REFUSED = "numbers.Real used as a plain value is not built"


def build(directory, name, env=None):
    exe = name[:-3]
    built = subprocess.run(
        [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", name, "--syntax", "python", "-o", exe],
        cwd=directory, capture_output=True, text=True, timeout=900,
        env=dict(os.environ, AIL_NO_CACHE="1", **(env or {})),
    )
    return built, Path(directory, exe)


class NumbersLabTests(unittest.TestCase):
    def test_passing_programs_match_cpython(self):
        for name in PASSING:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                source = Path(directory, name)
                source.write_bytes((LAB / name).read_bytes())
                built, exe = build(directory, name)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=300)
                expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=300)
                self.assertEqual(expected.returncode, 0, expected.stderr)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                 ran.stderr[:500])

    def test_review_regressions(self):
        for name, source in REGRESSIONS.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory, name)
                path.write_text(source)
                built, exe = build(directory, name)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=300)
                expected = subprocess.run([sys.executable, str(path)], capture_output=True, timeout=300)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                 ran.stderr[:500])

    def test_shadowing_and_early_register_are_refused_by_name(self):
        cases = {
            "shadow.py": ("from numbers import Number, Real\nclass A: pass\nclass B: pass\n"
                          "def f(Number, Real, x):\n    return (isinstance(x, Number), isinstance(x, Real))\n"
                          "print(f(A, B, A()))\n", "binds the name Number itself"),
            "early.py": ("import numbers\nnumbers.Real.register(A)\nclass A: pass\n"
                         "print(isinstance(A(), numbers.Real))\n",
                         "register() written before the class A is defined"),
        }
        for name, (source, wanted) in cases.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                Path(directory, name).write_text(source)
                built, exe = build(directory, name)
                self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                self.assertIn(wanted, built.stdout + built.stderr)
                self.assertFalse(exe.exists())

    def test_numbers_value_is_refused_by_name(self):
        with tempfile.TemporaryDirectory() as directory:
            name = "value_ref.py"
            Path(directory, name).write_text(
                "import numbers\n\ndef main():\n    print(numbers.Real)\n\nmain()\n")
            built, exe = build(directory, name)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(VALUE_REFUSED, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_followups_are_refused_by_name(self):
        for name, wanted in REFUSED.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                Path(directory, name).write_bytes((LAB / name).read_bytes())
                built, exe = build(directory, name)
                self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                self.assertIn(wanted, built.stdout + built.stderr)
                self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
