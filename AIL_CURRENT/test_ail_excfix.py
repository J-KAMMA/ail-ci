"""C22 / C23: bare raise on the general path, and OSError subclasses by errno class, against CPython 3.12.

Each program is ordinary Python; CPython is the oracle (in a temp directory) and the compiled program must print
the same bytes.  C22 programs are built by the general path only (`pyc.py --general-only`); C23 programs are
built on the typed path (AIL_NO_GENERAL=1) and on the general path.
"""
import unittest

from test_ail_pathlib import Base

RERAISE = r"""
def g() -> None:
    try:
        raise ValueError("x")
    except ValueError:
        raise


def nested() -> None:
    try:
        try:
            raise KeyError("k")
        except KeyError:
            raise
    except KeyError as e:
        print("outer", e)
        raise


def after_other() -> None:
    try:
        raise ValueError("first")
    except ValueError:
        try:
            raise IndexError("second")
        except IndexError:
            print("handled second")
        raise


def as_name() -> None:
    try:
        raise ZeroDivisionError("zd")
    except ZeroDivisionError as e:
        print("as", e)
        raise


def in_finally() -> None:
    try:
        raise ValueError("fin")
    finally:
        print("cleanup")


def reraise_in_finally_handler() -> None:
    try:
        try:
            raise ValueError("a")
        except ValueError:
            raise
        finally:
            print("fin1")
    except ValueError as e:
        print("got", e)


def finally_with_caught() -> None:
    try:
        raise ValueError("pending")
    finally:
        try:
            raise IndexError("inner")
        except IndexError:
            print("inner handled")


def bare_in_finally() -> None:
    try:
        try:
            raise ValueError("pend")
        finally:
            try:
                raise
            except ValueError as e:
                print("reraised in finally", e)
    except ValueError as e:
        print("outer got", e)


def loop() -> None:
    for i in range(3):
        try:
            try:
                raise ValueError("i%d" % i)
            except ValueError:
                raise
        except ValueError as e:
            print("loop", e)


def handler_with_return() -> int:
    try:
        try:
            raise ValueError("r")
        except ValueError:
            raise
    except ValueError:
        return 5
    return 0


try:
    g()
except ValueError as e:
    print("caught", e)
try:
    nested()
except KeyError as e:
    print("top", e)
try:
    after_other()
except ValueError as e:
    print("first again", e)
try:
    as_name()
except ZeroDivisionError as e:
    print("zd", e)
try:
    in_finally()
except ValueError as e:
    print("fin", e)
reraise_in_finally_handler()
try:
    finally_with_caught()
except ValueError as e:
    print("pending", e)
bare_in_finally()
loop()
print(handler_with_return())
try:
    try:
        raise OSError("o")
    except OSError:
        raise
except Exception as e:
    print("exc", e)
"""

MAKEDIRS = r"""
import os
os.makedirs("d/e")
for exist_ok in (True, False):
    try:
        os.makedirs("d/e", exist_ok=exist_ok)
        print("ok", exist_ok)
    except FileExistsError:
        print("exists", exist_ok)
    except OSError:
        print("oserror", exist_ok)
open("f", "w").write("x")
try:
    os.makedirs("f", exist_ok=True)
except FileExistsError:
    print("fileexists")
try:
    os.makedirs("f/x", exist_ok=True)
except NotADirectoryError:
    print("notadir")
except OSError:
    print("oserror")
"""

OPS = (
    ("mkdir existing", 'os.mkdir("d")'),
    ("rmdir dot", 'os.rmdir(".")'),
    ("rmdir missing", 'os.rmdir("nothere")'),
    ("rmdir nonempty", 'os.rmdir("d")'),
    ("rmdir file", 'os.rmdir("f")'),
    ("remove dir", 'os.remove("d")'),
    ("remove missing", 'os.remove("nothere")'),
    ("listdir file", 'os.listdir("f")'),
    ("listdir missing", 'os.listdir("nothere")'),
    ("open dir", 'open("d").read()'),
    ("open missing", 'open("nothere").read()'),
    ("open under file", 'open("f/x").read()'),
    ("mkdir under file", 'os.mkdir("f/x")'),
    ("mkdir missing parent", 'os.mkdir("nothere/x")'),
    ("rename missing", 'os.rename("nothere", "z")'),
)


CLASSES = ("FileNotFoundError", "FileExistsError", "IsADirectoryError", "NotADirectoryError", "PermissionError",
           "InterruptedError", "BlockingIOError", "ChildProcessError", "ConnectionError", "ProcessLookupError",
           "TimeoutError", "OSError")


def hierarchy_program(classes):
    out = ["import os", "", 'os.mkdir("d")', 'open("d/inner", "w").write("x")', 'open("f", "w").write("x")']
    for label, stmt in OPS:
        out.append("try:")
        out.append("    " + stmt)
        out.append('    print("%s", "ok")' % label)
        for cls in classes:
            out.append("except %s:" % cls)
            out.append('    print("%s", "%s")' % (label, cls))
    for label, stmt in OPS:
        for cls in classes:
            out.append("try:")
            out.append("    " + stmt)
            out.append("except %s:" % cls)
            out.append('    print("%s", "only", "%s")' % (label, cls))
            if cls != "OSError":
                out.append("except OSError:")
                out.append('    print("%s", "not", "%s")' % (label, cls))
    out += ["try:", '    os.rmdir(".")', "except FileNotFoundError:", '    print("fnf")', "except OSError:",
            '    print("os")']
    return "\n".join(out) + "\n"


# OSError(errno, strerror) built by the program (G4 raises it for an FFI errno failure): .errno, .strerror, str(e)
# and the errno-picked subclass, on a name bound by `except OSError as e`
USER_OSERROR = r"""
def show(n: int, text: str) -> None:
    try:
        raise OSError(n, text)
    except FileNotFoundError as e:
        print("FileNotFoundError", e.errno, e.strerror, str(e))
    except PermissionError as e:
        print("PermissionError", e.errno, e.strerror, str(e))
    except IsADirectoryError as e:
        print("IsADirectoryError", e.errno, str(e))
    except FileExistsError as e:
        print("FileExistsError", e.errno, str(e))
    except NotADirectoryError as e:
        print("NotADirectoryError", e.errno, str(e))
    except OSError as e:
        print("OSError", e.errno, e.strerror, str(e))


def main():
    for n in (1, 2, 13, 17, 20, 21, 33, 0, -1, 99999):
        show(n, "text " + str(n))
    show(2, "")
    show(2, "café 日本")
    try:
        raise OSError(2, "again")
    except OSError as e:
        print(e.errno, e.strerror)
        print(str(e) + "!")

main()
"""

TYPED_CLASSES = CLASSES[:5] + ("OSError",)      # the exception names the typed path has
HIERARCHY_TYPED = hierarchy_program(TYPED_CLASSES)
HIERARCHY = hierarchy_program(CLASSES)


class Excfix(Base):
    def test_c22_bare_raise_general(self):
        self.compare("reraise", RERAISE, mode="gonly", irs=("1",))

    def test_c22_makedirs_general(self):
        self.compare("makedirs", MAKEDIRS, mode="gonly", irs=("1",))

    def test_c23_hierarchy_typed(self):
        self.compare("hier", HIERARCHY_TYPED, mode="typed", irs=("1",))

    def test_c23_hierarchy_general(self):
        self.compare("hier_g", HIERARCHY, mode="gonly", irs=("1",))

    def test_oserror_with_errno_typed(self):
        self.compare("userr", USER_OSERROR, mode="typed", irs=("0", "1"))

    def test_oserror_with_errno_general_is_refused_by_name(self):
        # the general path has no errno on its exceptions yet; it says so rather than print another text
        self.refused(USER_OSERROR, "raising OSError with more than one argument", mode="gonly")

    def test_errno_of_other_classes_is_refused_on_the_typed_path(self):
        body = ("def main():\n    try:\n        raise ValueError('x')\n    except ValueError as e:\n"
                "        print(%s)\n\nmain()\n")
        for expr in ("e.errno", "e.strerror", "str(e)"):
            with self.subTest(expr):
                self.refused(body % expr, "is built only on a name bound by `except OSError as e`")


if __name__ == "__main__":
    unittest.main()
