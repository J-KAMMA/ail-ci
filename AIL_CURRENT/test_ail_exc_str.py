"""S4e: the text of an exception on the typed path, compared with CPython 3.12.

`except X as e:` followed by `print(e)`, `str(e)`, `f"{e}"`, `repr(e)`, `e.args` or `type(e).__name__` used to be refused
on the typed path (and sent the program to the slow general path). Every program here is ordinary Python; CPython is the
oracle and the typed build (AIL_NO_GENERAL=1, AIL_IR=0 and 1) must print the same bytes.

* A matrix: every built-in exception class the typed runtime has, raised with 0, 1 and 2 (and more) arguments of str, int,
  float, bool and None, with strings that need quoting in a repr, caught by its own class and by `Exception`; str(e), repr(e),
  print(e), f"{e}", f"{e!r}", "%s" % e, e.args, len(e.args), e.args[0], type(e).__name__.
* OSError with an errno: the class CPython picks, `[Errno 2] No such file or directory: 'x'`, the filename, five arguments.
* KeyError: str(e) is the repr of the key.
* Traps the runtime raises: the text of int("x"), float("x"), division by zero in its three spellings and for floats, index
  errors, KeyError of a dict lookup with its key, missing files, unpacking, list.index, max([]), str.index.
* The shapes a handler shows its exception in: print with sep/end, nested handlers, finally, re-raise, a loop, text kept
  after the handler.
* User exception classes: hierarchies, `__init__` with `super().__init__(...)` and attributes of every kind, inherited
  initialisers, `except Base`, `except Exception`, isinstance, type(e).__name__, repr(e), e.args.
* sqlite3 and subprocess exceptions (where the library is there).
"""
import os
import shutil
import unittest

from test_ail_pathlib import Base

CLASS_GROUPS = (
    ("ValueError", "ZeroDivisionError", "IndexError", "KeyError"),
    ("EOFError", "RuntimeError", "AssertionError", "OverflowError", "Exception"),
    ("OSError", "FileNotFoundError"),
    ("PermissionError", "IsADirectoryError", "FileExistsError", "NotADirectoryError"),
)
OS_CLASSES = ("OSError", "FileNotFoundError", "PermissionError", "IsADirectoryError", "FileExistsError", "NotADirectoryError")

ARGS = ["", "'x'", "\"it's\"", "'say \"hi\"'", "'both \\' and \"'", "'tab\\there'", "'e\u00e9\u65e5\U0001f600'", "''", "5", "-3",
        "2.5", "True", "None", "'a', 'b'", "'a', 2", "1, 2, 3", "'x', 1.5, None, True", "0.1", "1e20", "'multi\\nline'",
        "'k' * 3", "7 * 6", "str(12) + 'z'"]
OS_ARGS = ["2, 'No such file or directory'", "13, 'Permission denied'", "99, 'weird'", "2, 'x', 'file.txt'", "17, 'exists', 'a b'",
           "21, 'is a dir'", "20, 'not a dir', \"it's\"", "'a', 'b'", "1, 'x', None", "2, 'x', 'f', 4, 'g'"]


def matrix_program(classes):
    funcs, n = [], 0
    for cls in classes:
        args = list(ARGS) + (OS_ARGS if cls in OS_CLASSES else [])
        for a in args:
            n += 1
            first_str = a[:1] in ("'", '"')
            label = ("%s(%s)" % (cls, a)).replace("\\", "\\\\").replace('"', '\\"')
            body = [
                "def case%d() -> None:" % n,
                "    print(\"%s\")" % label,
                "    try:",
                "        raise %s(%s)" % (cls, a),
                "    except %s as e:" % cls,
                "        print(str(e))",
                "        print(repr(e))",
                "        print(e)",
                "        print(f\"{e}|{e!r}|{e!s}\")",
                "        print(e.args)",
                "        print(len(e.args))",
                "        print(type(e).__name__)",
                "        print(\"%s|%r\" % (e, e))",
                "        print(\"msg: \" + str(e))",
                "        print(len(str(e)))",
            ]
            if first_str:
                body.append("        print(e.args[0])")
            body += [
                "    try:",
                "        raise %s(%s)" % (cls, a),
                "    except Exception as other:",
                "        print(type(other).__name__, other, repr(other), isinstance(other, %s), type(other) is %s)" % (cls, cls),
            ]
            funcs.append("\n".join(body))
    calls = "\n".join("case%d()" % i for i in range(1, n + 1))
    return "\n\n\n".join(funcs) + "\n\n\n" + calls + "\n"


TRAPS = r'''
def t_int(s: str) -> None:
    try:
        print(int(s))
    except ValueError as e:
        print("int", e, repr(e), e.args)


def t_flt(s: str) -> None:
    try:
        print(float(s))
    except ValueError as e:
        print("float", e)


def t_div(a: int, b: int) -> None:
    try:
        print(a // b)
    except ZeroDivisionError as e:
        print("floordiv", e)
    try:
        print(a % b)
    except ZeroDivisionError as e:
        print("mod", e)
    try:
        print(a / b)
    except ZeroDivisionError as e:
        print("div", e)


def t_fdiv(a: float, b: float) -> None:
    try:
        print(a / b)
    except ZeroDivisionError as e:
        print("fdiv", e)
    try:
        print(a // b)
    except ZeroDivisionError as e:
        print("ffloordiv", e)
    try:
        print(a % b)
    except ZeroDivisionError as e:
        print("fmod", e)


def t_idx(i: int) -> None:
    xs = [1, 2]
    try:
        print(xs[i])
    except IndexError as e:
        print("idx", e, repr(e))
    try:
        xs[i] = 3
    except IndexError as e:
        print("setidx", e)
    try:
        xs.pop(i)
    except IndexError as e:
        print("pop", e)
    fs = [1.5, 2.5]
    try:
        print(fs[i])
    except IndexError as e:
        print("fidx", e)
    try:
        fs[i] = 2.0
    except IndexError as e:
        print("fsetidx", e)


def t_empty() -> None:
    ys: list[int] = []
    try:
        ys.pop()
    except IndexError as e:
        print("emptypop", e)


def t_sidx(s: str, i: int) -> None:
    try:
        print(s[i])
    except IndexError as e:
        print("sidx", e)


def t_key(k: str) -> None:
    d = {"a": 1}
    try:
        print(d[k])
    except KeyError as e:
        print("key", e, repr(e), e.args)
    try:
        del d[k]
    except KeyError as e:
        print("delkey", e)
    try:
        d.pop(k)
    except KeyError as e:
        print("popkey", e)
    s = {"a"}
    try:
        s.remove(k)
    except KeyError as e:
        print("setremove", e)


def t_ikey(k: int) -> None:
    d = {1: 1}
    try:
        print(d[k])
    except KeyError as e:
        print("ikey", e, repr(e), e.args)
    try:
        del d[k]
    except KeyError as e:
        print("idelkey", e)


def t_open(p: str) -> None:
    try:
        f = open(p)
        print(f.read())
    except FileNotFoundError as e:
        print("fnf", e, repr(e), e.args, type(e).__name__)


def t_open2(p: str) -> None:
    try:
        f = open(p)
        print(f.read())
    except OSError as e:
        print("oserr", e, type(e).__name__)


def t_unpack(s: str) -> None:
    try:
        a, b = s.split(",")
        print(a, b)
    except ValueError as e:
        print("unpack", e)


def t_index(s: str) -> None:
    xs = [1, 2, 3]
    try:
        print(xs.index(9))
    except ValueError as e:
        print("lindex", e)
    try:
        print(s.index("zzz"))
    except ValueError as e:
        print("sindex", e)
    try:
        xs.remove(9)
    except ValueError as e:
        print("remove", e)


def t_minmax() -> None:
    ys: list[int] = []
    try:
        print(max(ys))
    except ValueError as e:
        print("max", e)
    try:
        print(min(ys))
    except ValueError as e:
        print("min", e)


def t_assert(n: int) -> None:
    try:
        assert n > 0
    except AssertionError as e:
        print("assert", repr(e), e.args)
    try:
        assert n > 0, "n must be positive: " + str(n)
    except AssertionError as e:
        print("assert", e, repr(e), e.args)


t_int("x")
t_int("")
t_int(" 12 ")
t_int("1.5")
t_int("abc def")
t_int("it's")
t_flt("abc")
t_flt("")
t_div(1, 0)
t_fdiv(1.0, 0.0)
t_idx(5)
t_idx(-5)
t_empty()
t_sidx("ab", 5)
t_key("zz")
t_key("it's")
t_ikey(7)
t_open("/nonexistent-dir/x")
t_open2("/nonexistent-dir/it's")
t_open2("/")
t_unpack("a")
t_unpack("a,b,c")
t_index("abc")
t_minmax()
t_assert(0)
'''

TRAPS_MORE = r'''
import heapq
import math


def t_range() -> None:
    try:
        for i in range(0, 5, 0):
            print(i)
    except ValueError as e:
        print("range", e)


def t_chr(n: int) -> None:
    try:
        print(chr(n))
    except ValueError as e:
        print("chr", e)


def t_split(s: str) -> None:
    try:
        print(len(s.split("")))
    except ValueError as e:
        print("split", e)


def t_math(x: float) -> None:
    try:
        print(math.sqrt(x))
    except ValueError as e:
        print("sqrt", e)
    try:
        print(math.log(x))
    except ValueError as e:
        print("log", e)


def t_heap() -> None:
    h: list[int] = []
    try:
        print(heapq.heappop(h))
    except IndexError as e:
        print("heappop", e)


def t_setpop() -> None:
    s: set[int] = set()
    try:
        s.pop()
    except KeyError as e:
        print("setpop", e)


def t_intfloat(x: float) -> None:
    try:
        print(int(x))
    except OverflowError as e:
        print("intinf", e)
    except ValueError as e:
        print("intnan", e)


def t_del(i: int) -> None:
    xs = [1, 2]
    try:
        del xs[i]
    except IndexError as e:
        print("del", e)


def t_input() -> None:
    try:
        print(input())
    except EOFError as e:
        print("eof", e, repr(e))


def t_int_base(s: str) -> None:
    try:
        print(int(s, 16))
    except ValueError as e:
        print("hex", e)


def t_str_index(s: str) -> None:
    try:
        print(s.index("q"))
    except ValueError as e:
        print("sindex", e)
    try:
        print(s.rindex("q"))
    except ValueError as e:
        print("srindex", e)


t_range()
t_chr(1114112)
t_chr(-1)
t_split("abc")
t_math(-1.0)
t_math(0.0)
t_heap()
t_setpop()
t_intfloat(float("inf"))
t_intfloat(float("nan"))
t_del(5)
t_input()
t_int_base("zz")
t_str_index("abc")
'''

CONTEXTS = r'''
import sys


def parse(s: str) -> int:
    try:
        return int(s)
    except ValueError as e:
        print("bad input:", e, sep=" | ", end="!\n")
        return -1


def kept(items: list[str]) -> list[str]:
    errors: list[str] = []
    for item in items:
        try:
            if item == "":
                raise ValueError("empty item")
            if item == "k":
                raise KeyError(item)
            print(int(item))
        except (ValueError, KeyError) as err:
            errors.append(str(err))
            errors.append(f"[{err!r}]")
    return errors


def nested() -> None:
    try:
        try:
            raise ValueError("inner", 1)
        except ValueError as e:
            print("inner caught", e)
            raise RuntimeError("outer from " + str(e.args[0]))
    except RuntimeError as e:
        print("outer caught", e, repr(e))
    finally:
        print("finally runs")


def again() -> None:
    try:
        try:
            raise IndexError("idx")
        except IndexError as e:
            print("first", e)
            raise
    except IndexError as e:
        print("second", e, type(e).__name__)


def sequence(n: int) -> str:
    try:
        if n == 0:
            raise ZeroDivisionError("zero")
        if n == 1:
            raise OSError(2, "gone", "a.txt")
        if n == 2:
            raise KeyError("a")
        return "fine"
    except ZeroDivisionError as e:
        return "zd:" + str(e)
    except OSError as e:
        return "os:" + str(e) + ":" + str(e.errno) + ":" + e.strerror
    except Exception as e:
        return "other:" + repr(e)


def format_all(n: int) -> None:
    try:
        raise ValueError("fmt %d" % n, n)
    except ValueError as e:
        print("{} and {}".format(e, n))
        print("%s / %s" % (e, n))
        print("%r" % (e,))
        print(f"{e!s:>3}"[:0] + f"<{e}>")
        print(str(e).upper(), len(str(e)), str(e)[:4], "fmt" in str(e))
        print(e.args[0] + "!", int(e.args[1]) + 1)
        if e.args:
            print("has args", len(e.args))
        print("none" if not e.args else "some")


def to_stderr() -> None:
    try:
        raise RuntimeError("to stderr")
    except RuntimeError as e:
        print(e, file=sys.stderr)
        print("stdout still works", e)


def typed() -> None:
    try:
        raise FileNotFoundError(2, "No such file or directory", "nofile")
    except OSError as e:
        print(type(e).__name__, type(e).__qualname__, e.__class__.__name__, type(e))
        print(isinstance(e, FileNotFoundError), isinstance(e, (KeyError, OSError)), isinstance(e, KeyError))
        print(type(e) is OSError, type(e) == FileNotFoundError, type(e) != FileNotFoundError)


print(parse("12"), parse("zz"))
for line in kept(["1", "", "k", "x"]):
    print(line)
nested()
again()
for i in range(4):
    print(sequence(i))
format_all(3)
to_stderr()
typed()
'''

HIERARCHY = r'''
class AppError(Exception):
    pass


class NotFound(AppError):
    def __init__(self, key: str, code: int = 404):
        super().__init__(f"missing {key}")
        self.key = key
        self.code = code


class Tooth(NotFound):
    pass


class Bad(ValueError):
    """doc"""

    def __init__(self, msg: str, level: float, fatal: bool = False):
        super().__init__(msg, level)
        self.msg = msg
        self.level = level
        self.fatal = fatal


class Plain(Exception):
    def __init__(self, a, b):
        self.a = a


class Quiet(RuntimeError):
    def __init__(self):
        super().__init__()


class Deep(NotFound):
    def __init__(self, key: str, depth: int):
        super().__init__(key + "!", 500 + depth)
        self.depth = depth


class Counted(AppError):
    def __init__(self, n):
        super().__init__("count", n)
        self.n = n
        self.twice = n * 2


def look(k: str) -> int:
    if k == "x":
        raise NotFound(k)
    if k == "t":
        raise Tooth("tt", 3)
    if k == "d":
        raise Deep("dd", 2)
    if k == "b":
        raise Bad("careful", 2.5, True)
    if k == "p":
        raise Plain(1, "two")
    if k == "q":
        raise Quiet()
    if k == "a":
        raise AppError("plain app", 7)
    if k == "v":
        raise ValueError("really")
    if k == "e":
        raise Exception("generic")
    if k == "c":
        raise Counted(21)
    return len(k)


def run(k: str) -> None:
    try:
        print("ok", look(k))
    except NotFound as e:
        print("NotFound", e, repr(e), e.args, e.key, e.code, type(e).__name__)
    except Bad as e:
        print("Bad", e, repr(e), e.args, e.msg, e.level, e.fatal, type(e).__name__)
    except Plain as e:
        print("Plain", e, repr(e), e.args, e.a)
    except Counted as e:
        print("Counted", e, repr(e), e.args, e.n, e.twice)
    except (Quiet, AppError) as e:
        print("QA", e, repr(e), e.args, type(e).__name__, isinstance(e, AppError), isinstance(e, RuntimeError))
    except ValueError as e:
        print("VE", e, repr(e), isinstance(e, ValueError), type(e) is ValueError)
    except Exception as e:
        print("EX", e, repr(e), type(e).__name__, isinstance(e, Exception))


for k in ["zz", "x", "t", "d", "b", "p", "q", "a", "v", "e", "c"]:
    run(k)


def base(k: str) -> None:
    try:
        look(k)
    except AppError as e:
        print("AppError caught", type(e).__name__, str(e), len(e.args))
    except Exception as e:
        print("other", type(e).__name__, str(e))
    finally:
        print("fin", k)


for k in ["x", "t", "a", "v", "q", "c"]:
    base(k)


def rethrow(k: str) -> None:
    try:
        look(k)
    except NotFound as e:
        print("log", e)
        raise


try:
    rethrow("d")
except Deep as e:
    print("deep", e.key, e.code, e.depth, e)

try:
    raise Deep("w", 1)
except NotFound as e:
    print("deep as notfound", e.key, e.code, e)


def build(k: str) -> Exception:
    return NotFound(k, 1)


try:
    raise build("made")
except NotFound as e:
    print("built", e, e.code)

try:
    try:
        raise Tooth("t2", 9)
    except Tooth as e:
        raise Counted(e.code)
except AppError as e:
    print(type(e).__name__, e)

try:
    raise AppError
except AppError as e:
    print(repr(e), e.args, str(e) == "")
'''

CLASS_ATTRIBUTES = r'''
class HTTPError(Exception):
    status = 500
    reason = "server error"


class NotFound(HTTPError):
    status = 404
    reason = "not found"

    def __str__(self) -> str:
        return f"{self.status} {self.reason}"


class Teapot(HTTPError):
    status: int = 418

    def __init__(self, brew: str = "tea", strength: int = 1):
        super().__init__("short and stout", brew)
        self.brew = brew
        self.strength = strength


class Loud(ValueError):
    level = 3.5
    shout = True


def go(k: int) -> None:
    try:
        if k == 0:
            raise HTTPError("plain")
        if k == 1:
            raise NotFound("missing page", 7)
        if k == 2:
            raise Teapot()
        if k == 3:
            raise Teapot("coffee", strength=3)
        if k == 4:
            raise Loud("quiet", 1)
        if k == 5:
            raise Teapot(strength=2)
        print("fine")
    except Teapot as e:
        print("teapot", e.status, e.reason, e.brew, e.strength, e, repr(e), e.args)
    except HTTPError as e:
        print("http", e.status, e.reason, e, repr(e), e.args, type(e).__name__)
    except Loud as e:
        print("loud", e.level, e.shout, e, repr(e))


for i in range(7):
    go(i)
'''

INIT_ORDER_AND_FILENAME = r'''
import sys


class ValidationError(Exception):
    def __init__(self, message, field="name", code=400):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


def check(name: str) -> None:
    try:
        if name == "":
            raise ValidationError("empty")
        if name == "x":
            raise ValidationError("too short", "x", 422)
        print("ok", name)
    except ValidationError as err:
        print(err.message, err.field, err.code, err, err.args)


for n in ["", "x", "fine"]:
    check(n)


def opener(p: str) -> None:
    try:
        open(p)
    except FileNotFoundError as e:
        print(e.filename, e.errno, e.strerror, e)
    except OSError as e:
        print("os", e.filename, e.errno)


opener("/nonexistent/dir/file.txt")
opener("/")
try:
    raise FileNotFoundError(2, "nope", "a b.txt")
except OSError as e:
    print(e.filename, e)
'''

STRING_METHOD = r'''
class Shown(Exception):
    def __init__(self, name: str, n: int):
        super().__init__(name, n)
        self.name = name
        self.n = n

    def __str__(self) -> str:
        return f"{self.name} #{self.n}"


class Sub(Shown):
    pass


for k in range(2):
    try:
        if k:
            raise Sub("sub", k)
        raise Shown("shown", 7)
    except Shown as e:
        print(e, str(e), repr(e), e.args, f"<{e}>", "%s" % e, e.name, e.n)
'''


UNICODE = r'''
def f1(path: str) -> None:
    try:
        with open(path) as fh:
            print(fh.read())
    except UnicodeDecodeError as e:
        print("file", e, repr(e), type(e).__name__, e.args)
    except Exception as e:
        print("other", type(e).__name__, e)


def f2(b: bytes) -> None:
    try:
        print(b.decode())
    except UnicodeDecodeError as e:
        print("bytes", e, repr(e), type(e).__name__)
    except ValueError as e:
        print("value", e, type(e).__name__)


def f3(b: bytes) -> None:
    try:
        print(b.decode("utf-8"))
    except ValueError as e:
        print("viaValueError", e, type(e).__name__, isinstance(e, ValueError))


with open("bad.bin", "wb") as w:
    w.write(b"ab\xffcd")
f1("bad.bin")
f2(b"xy\xc3")
f2(b"\xe3\x81")
f2(b"\xe0\x80\x80")
f2(b"\xf4\x90\x80\x80")
f2(b"\xf0\x9f\x98")
f2(b"ok \xc3\xa9")
f3(b"\xff\xfe")
f3(b"a\xed\xa0\x80")
'''


class ExcStr(Base):
    def test_unicode_decode_error(self):
        self.compare("unicode", UNICODE, mode="typed")

    def test_matrix_values_and_errors(self):
        for classes in CLASS_GROUPS:
            with self.subTest(classes=classes):
                self.compare("matrix_" + "_".join(c.lower() for c in classes), matrix_program(classes), mode="typed")

    def test_traps(self):
        self.compare("traps", TRAPS, mode="typed")

    def test_more_traps(self):
        self.compare("traps_more", TRAPS_MORE, mode="typed")

    def test_contexts(self):
        self.compare("contexts", CONTEXTS, mode="typed")

    def test_user_classes(self):
        self.compare("hierarchy", HIERARCHY, mode="typed")

    def test_init_order_defaults_and_filename(self):
        self.compare("initorder", INIT_ORDER_AND_FILENAME, mode="typed")

    def test_user_class_attributes(self):
        self.compare("classattrs", CLASS_ATTRIBUTES, mode="typed")

    def test_user_str_method(self):
        self.compare("strmethod", STRING_METHOD, mode="typed")

    def test_subprocess_text(self):
        program = r'''
import subprocess


def f(cmd: list[str]) -> None:
    try:
        r = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("ok", r.returncode)
    except subprocess.CalledProcessError as e:
        print("cpe", e, type(e).__name__, e.returncode)
    except FileNotFoundError as e:
        print("fnf", e, repr(e), type(e).__name__)


f(["true"])
f(["false"])
f(["definitely-not-a-command-xyz"])
'''
        if not shutil.which("true") or not shutil.which("false"):
            self.skipTest("no true / false commands")
        self.compare("subproc", program, mode="typed")

    def test_sqlite_text(self):
        import test_ail_sqlite
        reason = test_ail_sqlite.missing_reason()
        if reason:
            self.skipTest(reason)
        program = r'''
import sqlite3


def f(sql: str) -> None:
    con = sqlite3.connect(":memory:")
    try:
        con.execute(sql)
    except sqlite3.OperationalError as e:
        print("op", e, repr(e), type(e).__name__, e.args)
    except sqlite3.Error as e:
        print("err", e, repr(e), type(e).__name__)
    con.close()


def g() -> None:
    try:
        raise sqlite3.IntegrityError("manual", 5)
    except sqlite3.DatabaseError as e:
        print("db", e, repr(e), type(e).__name__, e.args, type(e))
    try:
        raise sqlite3.ProgrammingError()
    except sqlite3.Error as e:
        print("pe", e, repr(e), type(e).__name__)


f("select * from nothing")
f("selec 1")
g()
'''
        self.compare("sqlite_text", program, mode="typed")

    def test_bytes_in_fstrings_and_list_index_text(self):
        # f"{b}" and f"{b!r}" of bytes are CPython's repr; list[bytes].index builds its text with one
        program = r"""
def main() -> None:
    b = b"a\x00\xff'q"
    c = b"it's"
    d = b'say "hi"'
    xs: list[bytes] = [b"x"]
    print(f"{b} {b!r} {c} {d!s} [{b[1:3]}]")
    try:
        xs.index(b"zz\n")
    except ValueError as e:
        print(str(e))


main()
"""
        self.compare("bytes_fstring", program, mode="typed")

    def test_refusals_stay_by_name(self):
        # what is still outside the built surface is refused with a reason, never compiled to a different answer
        body = ("def main():\n    try:\n        raise ValueError('x')\n    except ValueError as e:\n"
                "        print(%s)\n\nmain()\n")
        for expr in ("e.args[1:]", "e.errno"):
            with self.subTest(expr):
                self.refused(body % expr)
        self.refused("class E(Exception):\n    def helper(self):\n        return 1\n\ntry:\n    raise E('x')\nexcept E as e:\n"
                     "    print(e)\n", "user-defined exception class")


if __name__ == "__main__":
    unittest.main()
