"""An uncaught OSError subclass names its real class and CPython's message on stderr.

A whole-file open (`open(p).read()`, `for line in open(p)`, `with open(p)`, `open(p, 'rb').read()`)
used to raise the plain OSError with no text on the typed path, so a missing file printed just
`OSError` while CPython printed `FileNotFoundError: [Errno 2] No such file or directory: 'p'`.
Every program here is ordinary Python; CPython is the oracle and the last stderr line, the stdout
and the exit status must match it, on the typed path (AIL_IR=0 and 1), the default build and the
general path. The traceback frames above the last line may differ.

* The five OSError subclasses: FileNotFoundError, IsADirectoryError, PermissionError,
  NotADirectoryError, FileExistsError, through the text read, the line iteration, `with`, and the
  binary whole-file read.
* The path reaching the open as a literal, a parameter, a list item (index and negative index), an
  attribute, a dict value and a concatenation; an empty path; a path whose repr needs a double
  quote, a `\\n` escape and non-ASCII text; a path aliased by a print before the open.
* Caught: `except OSError`, `except FileNotFoundError as e: print(e)`, and both re-raise spellings
  (`raise`, `raise e`) whose last stderr line still matches CPython.
* A program that reads exception text (so the runtime words OSError itself) still names the path
  when line iteration then fails on a directory: uncaught, and in a caught `print(e)`.
"""
import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_ail_pathlib import build, oracle_env


def setUpModule():
    if sys.platform == "win32":
        raise unittest.SkipTest("the errno wording compared here is POSIX")


def last_line(data):
    text = data.decode("utf-8", "replace").rstrip("\n")
    lines = text.split("\n") if text else [""]
    return lines[-1]


def locked(d):
    p = d / "locked.txt"
    p.write_text("x", encoding="utf-8")
    p.chmod(0)


def plain(d):
    (d / "plain.txt").write_text("x", encoding="utf-8")


def here(d):
    (d / "here.txt").write_text("x", encoding="utf-8")


def body(lines):
    return "\n".join(lines) + "\nprint(main())\n"


MISSING_READ = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(open(\"nope_xyz\").read())",
    "    return 0",
])
MISSING_ITER = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    for line in open(\"nope_xyz\"):",
    "        print(line)",
    "    return 0",
])
MISSING_WITH = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    with open(\"nope_xyz\") as f:",
    "        print(f.read())",
    "    return 0",
])
MISSING_BINARY = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(len(open(\"nope_xyz\", \"rb\").read()))",
    "    return 0",
])
ROUTE_ARG = body([
    "def show(p: str) -> None:",
    "    print(open(p).read())",
    "def main() -> int:",
    "    print(\"before\")",
    "    show(\"nope_xyz\")",
    "    return 0",
])
ROUTE_LIST = body([
    "def main() -> int:",
    "    names = [\"a.txt\", \"nope_xyz\"]",
    "    print(\"before\")",
    "    print(open(names[1]).read())",
    "    return 0",
])
ROUTE_NEG = body([
    "def main() -> int:",
    "    names = [\"nope_xyz\"]",
    "    print(\"before\")",
    "    print(open(names[-1]).read())",
    "    return 0",
])
ROUTE_ATTR = body([
    "class C:",
    "    def __init__(self, p: str) -> None:",
    "        self.p = p",
    "def main() -> int:",
    "    c = C(\"nope_xyz\")",
    "    print(\"before\")",
    "    print(open(c.p).read())",
    "    return 0",
])
ROUTE_DICT = body([
    "def main() -> int:",
    "    d: dict[str, str] = {\"p\": \"nope_xyz\"}",
    "    print(\"before\")",
    "    print(open(d[\"p\"]).read())",
    "    return 0",
])
ROUTE_CONCAT = body([
    "def main() -> int:",
    "    base = \"nope\"",
    "    print(\"before\")",
    "    print(open(base + \"_xyz\").read())",
    "    return 0",
])
ROUTE_ALIAS = body([
    "def main() -> int:",
    "    p = \"nope_xyz\"",
    "    print(p)",
    "    print(open(p).read())",
    "    return 0",
])
EMPTY_PATH = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(open(\"\").read())",
    "    return 0",
])
UNICODE_PATH = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(open(\"na\\u00efve.txt\").read())",
    "    return 0",
])
QUOTE_PATH = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(open(\"it's.txt\").read())",
    "    return 0",
])
NEWLINE_PATH = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(open(\"a\\nb\").read())",
    "    return 0",
])
ISDIR_TEXT = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(open(\".\").read())",
    "    return 0",
])
ISDIR_BINARY = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(len(open(\".\", \"rb\").read()))",
    "    return 0",
])
ISDIR_ITER = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    for line in open(\".\"):",
    "        print(line)",
    "    return 0",
])
ISDIR_WITH = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    with open(\".\") as f:",
    "        print(f.read())",
    "    return 0",
])
NOTDIR = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(open(\"plain.txt/x\").read())",
    "    return 0",
])
PERM_TEXT = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(open(\"locked.txt\").read())",
    "    return 0",
])
PERM_BINARY = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    print(len(open(\"locked.txt\", \"rb\").read()))",
    "    return 0",
])
EXISTS = body([
    "def main() -> int:",
    "    print(\"before\")",
    "    g = open(\"here.txt\", \"x\")",
    "    print(g.read())",
    "    return 0",
])
CAUGHT_OS = body([
    "def show(p: str) -> None:",
    "    try:",
    "        print(open(p).read())",
    "    except OSError:",
    "        print(\"caught\")",
    "def main() -> int:",
    "    print(\"before\")",
    "    show(\"nope_xyz\")",
    "    print(\"after\")",
    "    return 0",
])
CAUGHT_TEXT = body([
    "def show(p: str) -> None:",
    "    try:",
    "        print(open(p).read())",
    "    except FileNotFoundError as e:",
    "        print(\"caught\", e)",
    "def main() -> int:",
    "    print(\"before\")",
    "    show(\"nope_xyz\")",
    "    return 0",
])
CAUGHT_OS_TEXT = body([
    "def show(p: str) -> None:",
    "    try:",
    "        print(open(p).read())",
    "    except OSError as e:",
    "        print(\"caught\", e)",
    "def main() -> int:",
    "    print(\"before\")",
    "    show(\"nope_xyz\")",
    "    return 0",
])
EXCSTR_THEN_ITER = body([
    "def show(p: str) -> None:",
    "    try:",
    "        print(open(p).read())",
    "    except OSError as e:",
    "        print(e)",
    "def main() -> int:",
    "    print(\"before\")",
    "    show(\"nope_xyz\")",
    "    for line in open(\".\"):",
    "        print(line)",
    "    return 0",
])
CATCH_ITER_TEXT = body([
    "def main() -> int:",
    "    try:",
    "        for line in open(\".\"):",
    "            print(line)",
    "    except OSError as e:",
    "        print(e)",
    "    return 0",
])
RERAISE = body([
    "def f() -> None:",
    "    try:",
    "        open(\"nope_xyz\").read()",
    "    except OSError:",
    "        raise",
    "def main() -> int:",
    "    print(\"before\")",
    "    f()",
    "    return 0",
])
RERAISE_E = body([
    "def f() -> None:",
    "    try:",
    "        open(\"nope_xyz\").read()",
    "    except OSError as e:",
    "        raise e",
    "def main() -> int:",
    "    print(\"before\")",
    "    f()",
    "    return 0",
])

MODES = (("typed", "0"), ("typed", "1"), ("default", "1"), ("gonly", "1"))


class Rd2(unittest.TestCase):
    def check(self, name, text, rc=1, setup=None):
        with tempfile.TemporaryDirectory(prefix="ail-rd2-") as tmp:
            tmp = Path(tmp)
            src = tmp / (name + ".py")
            src.write_text(text, encoding="utf-8")
            work = tmp / "oracle"
            work.mkdir()
            if setup:
                setup(work)
            want = subprocess.run([sys.executable, str(src)], cwd=work, capture_output=True,
                                  timeout=300, env=oracle_env())
            self.assertEqual(want.returncode, rc, want.stderr.decode())
            for mode, ir in MODES:
                exe = tmp / ("exe_%s_%s" % (mode, ir))
                built = build(src, exe, ir, mode, cwd=tmp)
                self.assertEqual(built.returncode, 0, "%s/%s: %s" % (mode, ir, built.stderr[-3000:]))
                run = tmp / ("run_%s_%s" % (mode, ir))
                run.mkdir()
                if setup:
                    setup(run)
                got = subprocess.run([str(exe)], cwd=run, capture_output=True, timeout=300)
                label = "%s AIL_IR=%s" % (mode, ir)
                self.assertEqual(got.returncode, want.returncode, "%s: %r" % (label, got.stderr[-1500:]))
                self.assertEqual(got.stdout, want.stdout, label)
                if rc:
                    self.assertEqual(last_line(got.stderr), last_line(want.stderr), label)

    def test_missing_text(self):
        self.check("missing_text", MISSING_READ)

    def test_missing_iteration(self):
        self.check("missing_iteration", MISSING_ITER)

    def test_missing_with(self):
        self.check("missing_with", MISSING_WITH)

    def test_missing_binary(self):
        self.check("missing_binary", MISSING_BINARY)

    def test_path_routes(self):
        for name, text in (("route_arg", ROUTE_ARG), ("route_list", ROUTE_LIST), ("route_neg", ROUTE_NEG),
                           ("route_attr", ROUTE_ATTR), ("route_dict", ROUTE_DICT), ("route_concat", ROUTE_CONCAT),
                           ("route_alias", ROUTE_ALIAS)):
            with self.subTest(route=name):
                self.check(name, text)

    def test_path_repr(self):
        for name, text in (("empty_path", EMPTY_PATH), ("unicode_path", UNICODE_PATH),
                           ("quote_path", QUOTE_PATH), ("newline_path", NEWLINE_PATH)):
            with self.subTest(path=name):
                self.check(name, text)

    def test_directory(self):
        self.check("isdir_text", ISDIR_TEXT)
        self.check("isdir_binary", ISDIR_BINARY)
        self.check("isdir_iter", ISDIR_ITER)
        self.check("isdir_with", ISDIR_WITH)

    def test_not_a_directory(self):
        self.check("notdir", NOTDIR, setup=plain)

    def test_permission(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root reads a mode-0 file")
        self.check("perm_text", PERM_TEXT, setup=locked)
        self.check("perm_binary", PERM_BINARY, setup=locked)

    def test_file_exists(self):
        self.check("exists", EXISTS, setup=here)

    def test_caught(self):
        self.check("caught_os", CAUGHT_OS, rc=0)
        self.check("caught_text", CAUGHT_TEXT, rc=0)
        self.check("caught_os_text", CAUGHT_OS_TEXT, rc=0)

    def test_excstr_iteration(self):
        self.check("excstr_then_iter", EXCSTR_THEN_ITER)
        self.check("catch_iter_text", CATCH_ITER_TEXT, rc=0)

    def test_reraise(self):
        self.check("reraise", RERAISE)
        self.check("reraise_e", RERAISE_E)


if __name__ == "__main__":
    unittest.main()
