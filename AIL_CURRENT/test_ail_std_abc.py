"""The nine buildable `abc` programs in lab/stdlib/abc, against CPython 3.12.

Every program is copied to a temporary directory, built in the default mode (with the typed
path allowed to fall back to the general path) on both AIL_IR modes, and run with empty stdin.
stdout and the exit code must match CPython's.

Three more programs in the directory are refused by name and recorded in RESULTS.md:
`virtual_subclass` (`ABC.register`), `subclasshook` (`issubclass`) and
`update_abstractmethods` (`abc.update_abstractmethods`).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "abc"

PASSING = (
    "abstract_instantiation",
    "animal",
    "cache_token",
    "codec",
    "metaclass_abcm",
    "notifications",
    "payment",
    "plugin_registry",
    "shapes",
)

# Review regressions: a plain (non-ABC) hierarchy stays instantiable, a non-`def` override
# implements an abstract method, and object.__new__'s "takes no arguments" check precedes the
# abstract check for a class with no __init__.
REGRESSIONS = {
    "plain": '''\
from abc import ABC, abstractmethod


class Mixin:
    @abstractmethod
    def run(self) -> str:
        return "mixin"


class Child(Mixin):
    pass


d = Child()
print("built", type(d).__name__, d.run())
try:
    Child(1)
except TypeError as exc:
    print("blocked", str(exc))
''',
    "override": '''\
import abc


class A(abc.ABC):
    @abc.abstractmethod
    def m(self) -> int:
        ...


class Value(A):
    m = 5


class Function(A):
    m = lambda self: 7


print("built", Value().m, Function().m())
''',
    "arity": '''\
from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self) -> int:
        ...


Base = Shape
try:
    Base(1)
except TypeError as exc:
    print("blocked", str(exc))


class WithInit(ABC):
    def __init__(self, x: int) -> None:
        self.x = x

    @abstractmethod
    def m(self) -> int:
        ...


class Partial(WithInit):
    pass


try:
    Partial(1, 2, 3, 4)
except TypeError as exc:
    print("blocked", str(exc))
''',
    # A metaclass that subclasses ABCMeta makes its users abstract, just as ABCMeta does.
    "meta_sub": '''\
from abc import ABCMeta, abstractmethod


class Meta(ABCMeta):
    pass


class Shape(metaclass=Meta):
    @abstractmethod
    def area(self) -> int:
        ...


try:
    Shape()
except TypeError as exc:
    print("blocked", str(exc))
else:
    print("built")
''',
    # The cache token is CPython's own positive counter, not a fake zero.
    "cache_value": '''\
import abc


token = abc.get_cache_token()
print("token", token)
print("positive", token > 0)
''',
}

# A concrete subclass inheriting an ABC guard must not swallow its own constructor binding
# errors (they used to be turned into a silently constructed object). The general path has no
# run-time arity errors for a direct call, so this is a named compile refusal, never silence.
REFUSED_REGRESSIONS = {
    "concrete_arity": ('''\
from abc import ABC, abstractmethod


class A(ABC):
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    @abstractmethod
    def m(self) -> str:
        ...


class B(A):
    def m(self) -> str:
        return "NOX"


try:
    B()
except TypeError as exc:
    print("blocked", str(exc))
''', "called without a required argument"),
}


class StdAbc(unittest.TestCase):
    def test_lab_programs_match_cpython(self):
        self.assertEqual(sorted(p.stem for p in PROGRAMS.glob("*.py")),
                         sorted(PASSING + ("subclasshook", "update_abstractmethods", "virtual_subclass")))
        for stem in PASSING:
            with self.subTest(program=stem), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                src = directory / (stem + ".py")
                src.write_bytes((PROGRAMS / (stem + ".py")).read_bytes())
                want = subprocess.run([sys.executable, "-B", str(src)], cwd=directory,
                                      capture_output=True, timeout=120)
                for ir in ("0", "1"):
                    exe = directory / ("exe" + ir)
                    env = dict(os.environ, AIL_IR=ir, AIL_NO_CACHE="1")
                    env.pop("AIL_NO_GENERAL", None)
                    env.pop("AIL_UNIFIED_FORCE", None)
                    built = subprocess.run(
                        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", src.name,
                         "--syntax", "python", "-o", exe.name],
                        cwd=directory, capture_output=True, text=True, timeout=900, env=env)
                    self.assertEqual(built.returncode, 0,
                                     "%s (AIL_IR=%s) did not build:\n%s\n%s"
                                     % (stem, ir, built.stdout[-3000:], built.stderr[-3000:]))
                    got = subprocess.run([str(exe)], cwd=directory, input=b"",
                                         capture_output=True, timeout=120)
                    self.assertEqual(
                        (got.returncode, got.stdout), (want.returncode, want.stdout),
                        "%s (AIL_IR=%s)\nexit %r != %r\nstderr:\n%s"
                        % (stem, ir, got.returncode, want.returncode,
                           got.stderr.decode("utf-8", "replace")[-2000:]))

    def test_review_regressions(self):
        for stem, source in sorted(REGRESSIONS.items()):
            with self.subTest(program=stem), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                src = directory / (stem + ".py")
                src.write_text(source, encoding="utf-8")
                want = subprocess.run([sys.executable, "-B", str(src)], cwd=directory,
                                      capture_output=True, timeout=120)
                for ir in ("0", "1"):
                    exe = directory / ("exe" + ir)
                    env = dict(os.environ, AIL_IR=ir, AIL_NO_CACHE="1")
                    env.pop("AIL_NO_GENERAL", None)
                    env.pop("AIL_UNIFIED_FORCE", None)
                    built = subprocess.run(
                        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", src.name,
                         "--syntax", "python", "-o", exe.name],
                        cwd=directory, capture_output=True, text=True, timeout=900, env=env)
                    self.assertEqual(built.returncode, 0,
                                     "%s (AIL_IR=%s) did not build:\n%s\n%s"
                                     % (stem, ir, built.stdout[-3000:], built.stderr[-3000:]))
                    got = subprocess.run([str(exe)], cwd=directory, input=b"",
                                         capture_output=True, timeout=120)
                    self.assertEqual(
                        (got.returncode, got.stdout), (want.returncode, want.stdout),
                        "%s (AIL_IR=%s)\nexit %r != %r\nstderr:\n%s"
                        % (stem, ir, got.returncode, want.returncode,
                           got.stderr.decode("utf-8", "replace")[-2000:]))


    def test_concrete_subclass_arity_is_refused(self):
        for stem, (source, message) in sorted(REFUSED_REGRESSIONS.items()):
            with self.subTest(program=stem), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                src = directory / (stem + ".py")
                src.write_text(source, encoding="utf-8")
                for ir in ("0", "1"):
                    exe = directory / ("exe" + ir)
                    env = dict(os.environ, AIL_IR=ir, AIL_NO_CACHE="1")
                    env.pop("AIL_NO_GENERAL", None)
                    env.pop("AIL_UNIFIED_FORCE", None)
                    built = subprocess.run(
                        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", src.name,
                         "--syntax", "python", "-o", exe.name],
                        cwd=directory, capture_output=True, text=True, timeout=900, env=env)
                    self.assertNotEqual(built.returncode, 0,
                                        "%s (AIL_IR=%s) built instead of refusing" % (stem, ir))
                    self.assertIn(message, built.stdout + built.stderr,
                                  "%s (AIL_IR=%s) refused without the named reason:\n%s\n%s"
                                  % (stem, ir, built.stdout[-3000:], built.stderr[-3000:]))


if __name__ == "__main__":
    unittest.main()
