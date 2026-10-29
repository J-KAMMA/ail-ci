"""F2: per-module class names (docs: ail-design/f2-classnames.md).

Two modules may each define `class Config` / `class Error`: the merge (ail_modules.py) mangles a class of an
imported module like a function (`b__Config`), and `python/pkg-v12/classname.py` gives every place that prints
a class name the name CPython prints: repr, `type(x).__name__`, `__name__`, `__qualname__`, `__module__`,
exception text, the uncaught-exception line (`b.Error: boom`), `<class 'b.Config'>`, dataclass and enum repr and
the class label of a defaultdict. Identity stays per class: `isinstance`, `except`, `type(a) is type(b)`.

Each program below is a set of files. CPython runs `python3 main.py` as the oracle; the compiled program must
print the same bytes, exit with the same status and end stderr with the same line, with the legacy path
(AIL_IR=0), the IR path (AIL_IR=1) and, for the general programs, the general path forced
(AIL_UNIFIED_FORCE=1). The typed program is built with AIL_NO_GENERAL=1, so the typed path must take it.
A single-file program is untouched: its build sees no AIL_CLASS_NAMES.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
sys.path.insert(0, str(ROOT / "python" / "pkg-v12"))


def write(directory, files):
    for name, text in files.items():
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def last_line(data):
    lines = data.decode("utf-8", "replace").strip().splitlines()
    return lines[-1] if lines else ""


GENERAL = {
    'a.py': '''from dataclasses import dataclass


@dataclass
class Config:
    n: int

    def show(self):
        return "a.Config(%d)" % self.n


class Error(Exception):
    pass


def make(n):
    return Config(n)


def fail(msg):
    raise Error(msg)
''',

    'b.py': '''import a
from dataclasses import dataclass


@dataclass
class Config:
    s: str

    def show(self):
        return "b.Config(" + self.s + ")"


class Error(Exception):
    pass


class Sub(a.Error):
    pass


def make(s):
    return Config(s)


def fail(msg):
    raise Error(msg)


def fail_sub(msg):
    raise Sub(msg)
''',

    'main.py': '''import a
import b


def main():
    x = a.Config(1)
    y = b.Config("x")
    print(repr(x))
    print(repr(y))
    print(x)
    print(type(x).__name__, type(y).__name__)
    print(x.__class__.__name__, y.__class__.__name__)
    print(x.show(), y.show())
    print(isinstance(x, a.Config), isinstance(x, b.Config), isinstance(y, a.Config), isinstance(y, b.Config))
    print(type(x) is type(y), type(x) is type(a.make(2)))
    try:
        a.fail("one")
    except a.Error as e:
        print(str(e), repr(e), type(e).__name__, e.__class__.__name__)
    try:
        b.fail("two")
    except b.Error as e:
        print(str(e), repr(e), type(e).__name__)
    try:
        try:
            b.fail("three")
        except a.Error as e:
            print("wrong catch")
    except b.Error as e:
        print("right catch", repr(e))
    try:
        b.fail_sub("four")
    except a.Error as e:
        print("sub caught", repr(e), type(e).__name__)
    print(a.Config.__name__, b.Config.__name__)
    print(a.Config, b.Config)
    print(a.Error, b.Error, b.Sub)
    print(a.Config.__qualname__)
    print(a.Config.__module__, b.Error.__module__)
    z = a.make(5)
    print(z == a.Config(5), z == x)
    raise b.Error("boom")


main()
''',

}

TYPED = {
    'a.py': '''from dataclasses import dataclass


@dataclass
class Config:
    n: int


class Error(Exception):
    pass


def make(n: int) -> Config:
    return Config(n)


def fail(msg: str, go: bool) -> int:
    if go:
        raise Error(msg)
    return 0
''',

    'b.py': '''import a
from dataclasses import dataclass


@dataclass
class Config:
    s: str


class Error(Exception):
    pass


class Sub(a.Error):
    pass


def make(s: str) -> Config:
    return Config(s)


def fail(msg: str, go: bool) -> int:
    if go:
        raise Error(msg)
    return 0


def fail_sub(msg: str, go: bool) -> int:
    if go:
        raise Sub(msg)
    return 0
''',

    'main.py': '''import a
import b


def main() -> int:
    x = a.Config(1)
    y = b.Config("x")
    print(x)
    print(y)
    print(repr(x), repr(y))
    print(type(x).__name__, type(y).__name__)
    print(isinstance(x, a.Config), isinstance(x, b.Config), isinstance(y, a.Config), isinstance(y, b.Config))
    print(x == a.make(1))
    try:
        a.fail("one", True)
    except a.Error as e:
        print(str(e), repr(e), type(e).__name__)
    try:
        b.fail("two", True)
    except b.Error as e:
        print(str(e), repr(e), type(e).__name__)
    try:
        try:
            b.fail("three", True)
        except a.Error:
            print("wrong catch")
    except b.Error as e:
        print("right catch", repr(e))
    try:
        b.fail_sub("four", True)
    except a.Error as e:
        print("sub caught", repr(e), type(e).__name__)
    b.fail("boom", True)
    return 0


if __name__ == "__main__":
    main()
''',

}

MIXED = {
    'a.py': '''from enum import Enum
from dataclasses import dataclass


class Color(Enum):
    RED = 1
    GREEN = 2


@dataclass
class Config:
    n: int


class Error(Exception):
    pass


class Plain:
    def __init__(self, v):
        self.v = v


class Blank:
    pass
''',

    'b.py': '''import a
from enum import Enum
from dataclasses import dataclass


class Color(Enum):
    RED = 10
    BLUE = 20


@dataclass
class Config(a.Config):
    s: str = "d"


class Error(a.Error):
    pass


class Plain:
    def __init__(self, v):
        self.v = v


class Blank:
    pass
''',

    'p/__init__.py': '''''',

    'p/m.py': '''from dataclasses import dataclass


@dataclass
class Config:
    z: float


class Error(ValueError):
    pass
''',

    'main.py': '''import a
import b
import p.m
from collections import defaultdict


def show(label, v):
    print(label, v)


def main():
    show("enum", [a.Color.RED, b.Color.RED, b.Color.BLUE])
    show("enum str", [str(a.Color.GREEN), str(b.Color.BLUE)])
    show("enum name", [type(a.Color.RED).__name__, type(b.Color.RED).__name__])
    show("is", [a.Color.RED is b.Color.RED, a.Color.RED == a.Color.RED])
    c = b.Config(1, "q")
    show("sub", [repr(c), isinstance(c, a.Config), isinstance(c, b.Config), isinstance(a.Config(1), b.Config)])
    show("pkg", [repr(p.m.Config(1.5)), p.m.Config, p.m.Error, type(p.m.Config(2.0)).__name__])
    show("plain", [type(a.Plain(1)).__name__, type(b.Plain(2)).__name__, isinstance(a.Plain(1), b.Plain)])
    show("plain is", type(a.Plain(1)) is type(b.Plain(1)))
    show("plain is2", type(a.Plain(1)) is type(a.Plain(2)))
    show("dd", [defaultdict(a.Blank), defaultdict(b.Blank)])
    try:
        raise b.Error("be")
    except a.Error as e:
        show("caught", [repr(e), str(e), type(e).__name__, isinstance(e, b.Error)])
    try:
        raise a.Error("ae")
    except b.Error as e:
        show("wrong", repr(e))
    except a.Error as e:
        show("right", repr(e))
    try:
        raise p.m.Error("pe")
    except ValueError as e:
        show("value", [repr(e), type(e).__name__])

    print("done")


main()
''',

}

THREAD = {
    'b.py': '''class Error(Exception):
    pass


def work():
    raise Error("in thread")
''',

    'main.py': '''import threading
import b


def main():
    t = threading.Thread(target=b.work)
    t.start()
    t.join()
    print("done")


main()
''',

}

ENTRY = {
    'a.py': '''from dataclasses import dataclass


@dataclass
class Config:
    n: int


class Error(Exception):
    pass
''',

    'main.py': '''from dataclasses import dataclass
from a import Config as AConfig, Error as AError


@dataclass
class Config:
    s: str


class Error(Exception):
    pass


def main():
    x = Config("e")
    y = AConfig(2)
    print(x, y, type(x).__name__, type(y).__name__)
    print(Config, AConfig)
    print(isinstance(x, AConfig), isinstance(y, Config), isinstance(y, AConfig))
    try:
        raise AError("a")
    except Error:
        print("wrong")
    except AError as e:
        print("right", repr(e))
    try:
        raise Error("m")
    except AError:
        print("wrong")
    except Error as e:
        print("right", repr(e))
    raise AError("last")


main()
''',

}

REFUSED = {
    'a.py': '''class Config:
    def __init__(self):
        self.x = 1

    def __getattr__(self, name):
        return 5

    def __class_getitem__(cls, k):
        return k


class Meta(type):
    pass


class Weird(metaclass=Meta):
    pass
''',

    'main.py': '''import a


def main():
    print(a.Config().x)
    print(a.Weird())


main()
''',

}


class ClassNames(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-classnames-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def same_as_cpython(self, files, typed=False, irs=("0", "1"), force_general=False, exit_status=None):
        write(self.dir, files)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        want = subprocess.run([sys.executable, "-B", "main.py"], cwd=self.dir, capture_output=True, timeout=60, env=env)
        if exit_status is not None:
            self.assertEqual(want.returncode, exit_status, want.stderr.decode())
        for ir in irs:
            exe = self.dir / ("out_ir" + ir)
            if exe.exists():
                exe.unlink()
            build_env = dict(os.environ, AIL_IR=ir, AIL_NO_CACHE="1")
            for key in ("AIL_NO_GENERAL", "AIL_UNIFIED_FORCE", "AIL_PATH", "AIL_CLASS_NAMES"):
                build_env.pop(key, None)
            if typed:
                build_env["AIL_NO_GENERAL"] = "1"
            if force_general:
                build_env["AIL_UNIFIED_FORCE"] = "1"
            built = subprocess.run([sys.executable, "-B", CLI, "compile", "main.py", "-o", str(exe)], cwd=self.dir,
                                   capture_output=True, text=True, timeout=600, env=build_env)
            self.assertEqual(built.returncode, 0, "AIL_IR=%s: %s" % (ir, built.stderr))
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout.decode(), want.stdout.decode(), "AIL_IR=%s" % ir)
            self.assertEqual(ran.returncode, want.returncode, "AIL_IR=%s" % ir)
            self.assertEqual(last_line(ran.stderr), last_line(want.stderr), "AIL_IR=%s" % ir)
        return want

    def test_general_two_modules(self):
        """Config / Error in both modules: repr, type names, identity, except, class repr, __qualname__,
        __module__, the uncaught `b.Error: boom` line."""
        want = self.same_as_cpython(GENERAL, exit_status=1)
        self.assertIn("<class 'a.Config'> <class 'b.Config'>", want.stdout.decode())
        self.assertEqual(last_line(want.stderr), "b.Error: boom")

    def test_general_forced(self):
        self.same_as_cpython(GENERAL, irs=("1",), force_general=True, exit_status=1)

    def test_typed_two_modules(self):
        """The typed path: dataclass repr, exception text, `except a.Error` taking `b.Sub`, `b.Error: boom`."""
        want = self.same_as_cpython(TYPED, typed=True, exit_status=1)
        self.assertEqual(last_line(want.stderr), "b.Error: boom")

    def test_enum_subclass_package_defaultdict(self):
        """Enums named alike, a subclass named like its base, a package module (`p.m`), a defaultdict of a class."""
        want = self.same_as_cpython(MIXED, exit_status=0)
        self.assertIn("<class 'p.m.Config'>", want.stdout.decode())

    def test_thread_uncaught(self):
        want = self.same_as_cpython(THREAD, exit_status=0)
        self.assertEqual(last_line(want.stderr), "b.Error: in thread")

    def test_entry_and_module_class_with_one_name(self):
        """The entry's own `Config` / `Error` keep their names (`__main__`); the module's are told apart."""
        want = self.same_as_cpython(ENTRY, exit_status=1)
        self.assertEqual(last_line(want.stderr), "a.Error: last")

    def test_refusal_names_the_class_not_the_mangled_name(self):
        write(self.dir, REFUSED)
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("AIL_NO_GENERAL", None)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", "main.py", "-o", str(self.dir / "out")], cwd=self.dir,
                               capture_output=True, text=True, timeout=300, env=env)
        self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
        self.assertIn("a.Meta", built.stderr)
        self.assertNotIn("a__Meta", built.stderr)
        self.assertNotIn("Traceback", built.stderr)

    def test_registry(self):
        import classname
        old = os.environ.pop("AIL_CLASS_NAMES", None)
        try:
            self.assertFalse(classname.active())
            self.assertEqual(classname.display("Config"), "Config")
            self.assertEqual(classname.module("Config"), "__main__")
            self.assertEqual(classname.qualified("Config"), "Config")
            runtime = "typedef struct { int x; } ail_classobj;"
            self.assertEqual(classname.patch_runtime(runtime), runtime)      # a single-module program's C is untouched
            os.environ["AIL_CLASS_NAMES"] = '{"p__m__Config": ["Config", "p.m"]}'
            self.assertTrue(classname.active())
            self.assertEqual(classname.display("p__m__Config"), "Config")
            self.assertEqual(classname.module("p__m__Config"), "p.m")
            self.assertEqual(classname.qualified("p__m__Config"), "p.m.Config")
            self.assertEqual(classname.display("Other"), "Other")
            self.assertIn("const char *module;", classname.patch_runtime(" } ail_classobj;"))
        finally:
            os.environ.pop("AIL_CLASS_NAMES", None)
            if old is not None:
                os.environ["AIL_CLASS_NAMES"] = old

    def test_single_file_program_gets_no_class_table(self):
        import ail_chatgpt
        self.assertEqual(ail_chatgpt._class_names_env(None), "")
        import ail_modules
        write(self.dir, {"main.py": "class C:\n    pass\n\n\nprint(C)\n"})
        self.assertIsNone(ail_modules.merge_program(self.dir / "main.py", (self.dir / "main.py").read_text()))
        write(self.dir, {"u.py": "def f():\n    return 1\n", "main.py": "import u\nprint(u.f())\n"})
        merged = ail_modules.merge_program(self.dir / "main.py", (self.dir / "main.py").read_text())
        self.assertEqual(merged.classes, {})           # functions only: no class table, so the build is unchanged
        write(self.dir, {"u.py": "class K:\n    pass\n", "main.py": "import u\nprint(u.K)\n"})
        merged = ail_modules.merge_program(self.dir / "main.py", (self.dir / "main.py").read_text())
        self.assertEqual(merged.classes, {"u__K": ("K", "u")})
        self.assertEqual(merged.names["u__K"], "u.K")


if __name__ == "__main__":
    unittest.main()
