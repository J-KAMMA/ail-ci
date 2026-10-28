"""Library batch 8: argparse.ArgumentParser / add_argument / parse_args lowered to plain Python.

Every program is ordinary Python: CPython 3.12 is the oracle, and the compiled program (AIL_IR=0 and
AIL_IR=1) must print the same bytes and exit with the same status.  The parser and the arguments are
written directly in the program, so the parse becomes a loop over a list[str] (an explicit list or
sys.argv[1:]); there is no runtime module.  Uses outside that shape are refused by name at compile time.

Covered here: positional and optional arguments, one or several option strings (-c / --count), long
--name=value, short -cVALUE / -c=VALUE and short clusters (-vv, -qv, -vc7), an attached short value
that begins with `-` (-s-vv), `--` (whose following tokens are never cluster-expanded), a negative
number as a positional or an option value, type str / int / float / Path, literal and expression
defaults (a string default is converted as CPython does), required, choices, store_true /
store_false, and the error exits (invalid int, invalid choice, missing required, unrecognized option,
an option with no value).  Not built (named refusals): nargs, append and the other actions, an
optional with neither default= nor required=True, a second parse_args on the same parser, help
(a literal -h / --help / a help abbreviation, or add_help=True over a runtime argv), an invalid
string default, the namespace used as a value, and a parse result returned from a function.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

PROGRAMS = {}
PROGRAMS["argparse"] = r'''import argparse
from argparse import ArgumentParser
from pathlib import Path

HERE = Path("/tmp")


def show(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="demo", add_help=False)
    parser.add_argument("name")
    parser.add_argument("out", type=Path)
    parser.add_argument("--count", "-c", type=int, default=1)
    parser.add_argument("--ratio", type=float, default=0.5)
    parser.add_argument("--mode", choices=("a", "b"), default="a")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--quiet", action="store_false")
    parser.add_argument("--tag", required=True)
    args = parser.parse_args(argv)
    print(args.name, args.out, args.count, args.ratio, args.mode, args.verbose, args.quiet, args.tag)


def second(argv: list[str]) -> None:
    parser = ArgumentParser(add_help=False)
    parser.add_argument("--root", type=Path, default=HERE / "x")
    parser.add_argument("--label", default="a" + "b")
    parser.add_argument("--n", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args(args=argv)
    print(args.root, args.label, args.n)


def third(argv: list[str]) -> None:
    parser = ArgumentParser(add_help=False)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_false")
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args(argv)
    print(args.verbose, args.quiet, args.count)


def main() -> None:
    show(["x", "p", "--count", "3", "--tag", "t"])
    show(["x", "p", "--count=4", "--ratio=1.5", "--mode", "b", "--verbose", "--tag=t"])
    show(["-5", "p", "--tag", "n"])
    show(["--tag", "z", "--", "x", "p"])
    show(["x", "p", "-c3", "--tag", "s"])
    show(["x", "p", "-c=4", "--tag", "r"])
    second([])
    second(["--root", "/tmp/y", "--label", "q", "--n", "2"])
    third([])
    third(["-vv", "--cou", "3"])
    third(["-qq", "--cou=4"])


main()
'''

PROGRAMS["argparse_noargs"] = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--name", default="world")
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--ratio", type=float, default=0.25)
    parser.add_argument("--flag", action="store_true")
    parser.add_argument("--off", action="store_false")
    args = parser.parse_args()
    print(args.name, args.count, args.ratio, args.flag, args.off)


main()
'''

PROGRAMS["argparse_forms"] = r'''import argparse
from pathlib import Path


def show(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-q", "--quiet", action="store_false")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-c", "--count", type=int, default="5")
    parser.add_argument("--root", type=Path, default="/tmp/base")
    parser.add_argument("--name", default=None)
    parser.add_argument("nums", type=float)
    args = parser.parse_args(argv)
    print(args.quiet, args.verbose, args.count, args.root, repr(args.name), args.nums)


def main() -> None:
    show(["-qv", "-c7", "-.5"])
    show(["-vc=8", "--root=/tmp/x", "--name", "-", "-2.5"])
    show(["-c", "-5", "-q", "-v", "-3.5"])


main()
'''

PROGRAMS["argparse_short_value"] = r'''import argparse


def show(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-s", "--say", default="d")
    args = parser.parse_args(argv)
    print(repr(args.say))


def main() -> None:
    show(["-s-vv"])
    show(["-s=-vv"])
    show(["-s", "-5"])
    show(["-s-5"])
    show(["-s="])


main()
'''

PROGRAMS["argparse_dashdash"] = r'''import argparse


def show(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-v", action="store_true")
    parser.add_argument("val")
    args = parser.parse_args(argv)
    print(args.val, args.v)


def main() -> None:
    show(["--", "-vv"])
    show(["--", "-c7"])
    show(["-v", "--", "-vv"])


main()
'''

PROGRAMS["argparse_bad_value"] = r'''import argparse

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--name", default="x")
parser.add_argument("--tag", default="t")
args = parser.parse_args(["--name", "--tag", "v"])
print(args.name, args.tag)
'''

PROGRAMS["argparse_bad_int"] = r'''import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--count", type=int, default=1)
args = parser.parse_args(["--count", "x"])
print(args.count)
'''

PROGRAMS["argparse_bad_choice"] = r'''import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=("a", "b"), default="a")
args = parser.parse_args(["--mode", "c"])
print(args.mode)
'''

PROGRAMS["argparse_missing"] = r'''import argparse

parser = argparse.ArgumentParser()
parser.add_argument("name")
parser.add_argument("--tag", required=True)
args = parser.parse_args(["x"])
print(args.name, args.tag)
'''

PROGRAMS["argparse_unknown"] = r'''import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--count", type=int, default=1)
args = parser.parse_args(["--nope"])
print(args.count)
'''

CASES = [
    ("argparse", PROGRAMS["argparse"], [""]),
    ("argparse_noargs", PROGRAMS["argparse_noargs"], [""]),
    ("argparse_forms", PROGRAMS["argparse_forms"], [""]),
    ("argparse_short_value", PROGRAMS["argparse_short_value"], [""]),
    ("argparse_dashdash", PROGRAMS["argparse_dashdash"], [""]),
    ("argparse_bad_value", PROGRAMS["argparse_bad_value"], [""]),
    ("argparse_bad_int", PROGRAMS["argparse_bad_int"], [""]),
    ("argparse_bad_choice", PROGRAMS["argparse_bad_choice"], [""]),
    ("argparse_missing", PROGRAMS["argparse_missing"], [""]),
    ("argparse_unknown", PROGRAMS["argparse_unknown"], [""]),
]


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, inputs, ir):
        with tempfile.TemporaryDirectory() as directory:
            env = {"AIL_IR": "1" if ir else "0"}
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (name, env["AIL_IR"], built.stdout, built.stderr))
            Path(directory, "oracle.py").write_text(text, encoding="utf-8")
            for k, stdin in enumerate(inputs):
                want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))], input=stdin.encode(),
                                      capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, "%s input %d: %s" % (name, k, got.stderr[-300:]))
                if got.stdout != want.stdout:
                    a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                    for n, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            self.fail("%s input %d (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                      % (name, k, env["AIL_IR"], n + 1, x, y))
                    self.fail("%s input %d: %d lines against %d" % (name, k, len(a), len(b)))

    def test_programs_match_cpython(self):
        for name, text, inputs in CASES:
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, text, inputs, ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "nargs": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('items', nargs='*')\n"
                      "a = p.parse_args([])\nprint(a.items)\n", "argparse: add_argument(nargs=...)"),
            "nodefault": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('--name')\n"
                          "a = p.parse_args([])\nprint(a.name)\n", "neither default= nor required=True"),
            "append": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('--tag', action='append')\n"
                       "a = p.parse_args([])\nprint(a.tag)\n", "action='append'"),
            "value": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('--name', default='x')\n"
                      "a = p.parse_args([])\nprint(a)\n", "the namespace 'a' is used as a value"),
            "returned": ("import argparse\n\n\ndef parse() -> argparse.Namespace:\n    p = argparse.ArgumentParser()\n"
                         "    p.add_argument('--name', default='x')\n    return p.parse_args([])\n\n"
                         "a = parse()\nprint(a.name)\n", "the parser 'p' is used outside"),
            "dest": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('--a', dest='x', default='1')\n"
                     "p.add_argument('--b', dest='x', default='2')\na = p.parse_args([])\nprint(a.x)\n",
                     "two arguments use the destination"),
            "default": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('--n', type=int, default='bad')\n"
                        "a = p.parse_args([])\nprint(a.n)\n", "default='bad' is not a valid int"),
            "help": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('--name', default='x')\n"
                     "a = p.parse_args(['-h'])\nprint(a.name)\n", "help output (-h/--help) is not built"),
            "help_var": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('--name', default='x')\n"
                         "argv = ['-h']\na = p.parse_args(argv)\nprint(a.name)\n", "help output (-h/--help) is not built"),
            "help_abbrev": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('--name', default='x')\n"
                            "a = p.parse_args(['--he'])\nprint(a.name)\n", "help output (-h/--help) is not built"),
            "help_runtime": ("import argparse\n\np = argparse.ArgumentParser()\np.add_argument('--name', default='x')\n"
                             "a = p.parse_args()\nprint(a.name)\n", "help output (-h/--help) is not built"),
            "twice": ("import argparse\n\np = argparse.ArgumentParser(add_help=False)\np.add_argument('--x', default='a')\n"
                      "a = p.parse_args([])\nb = p.parse_args([])\nprint(a.x, b.x)\n", "parse_args() is called twice"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


class UnchangedPrograms(unittest.TestCase):
    def test_a_program_without_argparse_keeps_its_text(self):
        import stdlib5
        text = "import sys\n\nprint(sys.argv[1:])\n"
        notes = []
        self.assertIs(stdlib5.rewrite_text(text, notes), text)
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
