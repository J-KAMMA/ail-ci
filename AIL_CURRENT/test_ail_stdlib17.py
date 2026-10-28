"""Library batch 17: `argparse.ArgumentParser`, compared with CPython 3.12 on both builds.

The supported spelling is ordinary Python: `ArgumentParser(prog=..., description=..., add_help=...,
allow_abbrev=...)`; `add_argument` with literal names, action="store" (the default), no `nargs`,
`type` in str / int / float / bool / pathlib.Path, `default`, `required`, `choices`, `help`,
`metavar` and `dest`; and `parse_args()` (or `parse_args(sequence)`).  The parser and the result
behave like CPython's: short and long options, `--name=value`, unique long-option abbreviations,
attached short values (`-n5`), negative-number values, `--`, repeated options, defaults, required
arguments, choices, conversion errors, usage/help text, exit status 2 on an error and a Namespace
whose attributes are the argument destinations (repr, equality and vars agree; reading a name that
is not a destination is refused).  `type=Path` returns the existing pathlib `_AilPath`, as other
pathlib programs do.

Everything else is a named refusal at compile time.  The programs below are run by CPython and by
the compiled program (AIL_IR=0 and AIL_IR=1) with the same argv; stdout, stderr and exit status
must agree.  The refusal test builds nothing.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name, ir):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    env = dict(os.environ, AIL_IR="1" if ir else "0")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1200, env=env)
    return built, source, exe


MAIN = r'''import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="prog", description="demo parser")
    parser.add_argument("input", help="the input file")
    parser.add_argument("--output", "-o", type=Path, required=True, help="where to write")
    parser.add_argument("--level", "-l", type=int, choices=(1, 2, 3), default=1, help="level of things")
    parser.add_argument("--label", default="none")
    parser.add_argument("--ratio", type=float)
    parser.add_argument("--order")
    args = parser.parse_args()
    print(args.input, args.output, args.output.name, args.output.parent)
    print(args.level, args.label, args.ratio, args.order)


main()
'''

EXPLICIT = r'''from argparse import ArgumentParser


class Holder:
    def __init__(self) -> None:
        self.seen = 0


def show(namespace, holder) -> None:
    holder.seen = holder.seen + 1
    print(namespace.name, namespace.count, holder.seen)
    namespace.count = namespace.count + 1
    print(namespace.count)


def main() -> None:
    parser = ArgumentParser(prog="p", add_help=False)
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("name")
    first = parser.parse_args(["bob", "--count", "7"])
    show(first, Holder())
    print(first.count)
    second = parser.parse_args(["carol"])
    print(second.name, second.count)


main()
'''

DASH = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="p", add_help=False)
    parser.add_argument("value")
    args = parser.parse_args()
    print(args.value)


main()
'''

PATHS = r'''import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="p", add_help=False)
    parser.add_argument("--p", type=Path, default="a/b.txt")
    parser.add_argument("--q", type=Path, default=Path("c/d.txt"))
    parser.add_argument("--n", type=int, default="12")
    parser.add_argument("--flag", type=bool, default="")
    args = parser.parse_args()
    print(args.p, args.p.name, args.p.parent, args.q, args.n, args.flag)


main()
'''

PATHNONE = r'''import argparse
from pathlib import Path


class Holder:
    def __init__(self) -> None:
        self.ns = None


def show(ns) -> None:
    print(ns.out)
    print(ns.out is None)
    if ns.out is not None:
        print(ns.out.name, ns.out.parent)


def main() -> None:
    parser = argparse.ArgumentParser(prog="p", add_help=False)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--other", type=Path, default=None)
    first = parser.parse_args([])
    show(first)
    print(first)
    second = parser.parse_args(["--out", "x/y.txt", "--other="])
    show(second)
    print(second)
    items = [second]
    d = {"k": second}
    holder = Holder()
    holder.ns = second
    print(items[0].out, items[0].out.name)
    print(d["k"].out, d["k"].out.parent)
    print(holder.ns.out, holder.ns.out.suffix)
    print(second.out == Path("x/y.txt"))


main()
'''

PATHCHOICES = r'''import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="p", add_help=False)
    parser.add_argument("--out", type=Path, choices=(Path("a"), Path("b")), default=Path("a"))
    parser.add_argument("--none", type=Path, choices=(Path("a"), Path("b")))
    first = parser.parse_args([])
    print(first.out, first.none)
    print(first)
    second = parser.parse_args(["--out", "b", "--none", "a"])
    print(second)


main()
'''

NAMESPACE = r'''import argparse


def show(value) -> None:
    print(value)


def main() -> None:
    parser = argparse.ArgumentParser(prog="p", add_help=False)
    parser.add_argument("--a", default="d")
    parser.add_argument("pos")
    first = parser.parse_args(["x"])
    show(first)
    print(first)
    print(first == parser.parse_args(["x"]))
    print(first == parser.parse_args(["y"]))
    print(vars(first))
    print(first.a, first.pos)


main()
'''

NEGATIVE = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="p", add_help=False)
    parser.add_argument("-1", dest="one")
    parser.add_argument("-x", type=int)
    parser.add_argument("value")
    args = parser.parse_args(["-1", "a", "-x", "-5", "v"])
    print(args.one, args.x, args.value)


main()
'''

ABBREV = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="p", add_help=False, allow_abbrev=False)
    parser.add_argument("--foobar")
    parser.add_argument("--foobaz")
    parser.add_argument("--other")
    args = parser.parse_args(["--foobar", "1", "--oth", "2"])
    print(args.foobar, args.foobaz, args.other)


main()
'''

LONGHELP = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="verylongprogramname", description="This is a rather long description that should wrap across more than one line because it keeps going and going with many words in it.")
    parser.add_argument("inputfile", help="the input file which has a very long help text that also needs to wrap across more than one line for sure")
    parser.add_argument("--output-file-name", "-o", type=str, help="where to write the output, also long enough to wrap around the eighty column limit maybe")
    parser.add_argument("--short", metavar="X", help="short one")
    parser.parse_args(["-h"])


main()
'''

CASES = [
    ("main", MAIN, [
        ["in.txt", "--output", "out.txt"],
        ["in.txt", "-o", "dir/out.json", "-l", "2", "--label=hi", "--ratio", "2.5"],
        ["--out", "x.json", "in.txt"],
        ["in.txt", "--output=o.txt", "--level=3", "--label", ""],
        ["in.txt", "-o", "x", "-l1", "--ratio", "-5"],
        ["in.txt", "-o", "x", "--label", "a", "--label", "b"],
        ["in.txt", "-o", "x", "--"],
        ["in.txt", "-o", "x", "--", "-weird"],
        [],
        ["in.txt"],
        ["in.txt", "-o"],
        ["in.txt", "-o", "x", "--bogus"],
        ["in.txt", "-o", "x", "--level", "9"],
        ["in.txt", "-o", "x", "--level", "x"],
        ["in.txt", "-o", "x", "--o", "z"],
        ["-h"],
        ["--help"],
        ["--help=x"],
        ["-h=x"],
        ["--help="],
    ]),
    ("explicit", EXPLICIT, [
        [],
        ["-h"],
    ]),
    ("dash", DASH, [
        ["--", "-weird"],
        ["-5"],
        ["--", "--"],
    ]),
    ("paths", PATHS, [
        [],
        ["--p", "x/y.json", "--n", "007", "--flag", "false"],
    ]),
    ("pathnone", PATHNONE, [
        [],
        ["--out", "x/y.txt", "--other="],
    ]),
    ("pathchoices", PATHCHOICES, [
        [],
        ["--out", "b", "--none", "a"],
        ["--out", "c"],
        ["--out", "a", "--none", "c"],
    ]),
    ("namespace", NAMESPACE, [
        [],
    ]),
    ("negative", NEGATIVE, [
        [],
        ["-1", "b", "-x", "7", "-5"],
    ]),
    ("abbrev", ABBREV, [
        ["--foobar", "1", "--oth", "2"],
        ["--foo", "1"],
        ["--foob", "1"],
    ]),
    ("longhelp", LONGHELP, [
        ["-h"],
    ]),
]


class ArgparseTests(unittest.TestCase):
    def compare(self, name, text, argv, ir):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, "p_" + name, ir)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s"
                             % (name, ir, built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            expected = subprocess.run([sys.executable, str(oracle), *argv], capture_output=True, timeout=300)
            ran = subprocess.run([str(exe), *argv], capture_output=True, timeout=300)
            label = "%s %r (AIL_IR=%s)" % (name, argv, ir)
            self.assertEqual(ran.returncode, expected.returncode, label + "\n" + ran.stderr.decode(errors="replace"))
            self.assertEqual(ran.stdout, expected.stdout, label)
            self.assertEqual(ran.stderr, expected.stderr, label)

    def test_programs_match_cpython_on_both_builds(self):
        for name, text, argvs in CASES:
            for ir in (False, True):
                for argv in argvs:
                    with self.subTest(program=name, argv=argv, ir=ir):
                        self.compare(name, text, argv, ir)

    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused", False)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_unbuilt_uses_are_named_refusals(self):
        cases = {
            "action": ('import argparse\n\np = argparse.ArgumentParser()\n'
                       'p.add_argument("--verbose", action="store_true")\n', "argparse.add_argument(action="),
            "nargs": ('import argparse\n\np = argparse.ArgumentParser()\n'
                      'p.add_argument("files", nargs="*")\n', "argparse.add_argument(nargs=...)"),
            "type": ('import argparse\n\np = argparse.ArgumentParser()\n'
                     'p.add_argument("--x", type=len)\n', "argparse.add_argument(type=...)"),
            "known": ('import argparse\n\np = argparse.ArgumentParser()\n'
                      'p.parse_known_args([])\n', "parse_known_args"),
            "namespace": ('import argparse\n\nn = argparse.Namespace()\nprint(n)\n', "argparse.Namespace"),
            "dynamic": ('import argparse\nimport sys\n\np = argparse.ArgumentParser()\n'
                        'p.add_argument(sys.argv[1])\n', "needs a literal argument name"),
            "action_return": ('import argparse\n\np = argparse.ArgumentParser()\n'
                              'a = p.add_argument("--x")\n', "the action returned by argparse.add_argument() is not built"),
            "mixed": ('import argparse\n\np = argparse.ArgumentParser()\n'
                      'p.add_argument("pos", "--x")\n', "cannot mix positional and option names"),
            "namespace_read": ('import argparse\n\np = argparse.ArgumentParser()\n'
                               'p.add_argument("--x")\n'
                               'n = p.parse_args([])\nprint(n.missing)\n',
                               "argparse Namespace has no argument destination 'missing'"),
            "namespace_getattr": ('import argparse\n\np = argparse.ArgumentParser()\n'
                                  'p.add_argument("--x")\n'
                                  'n = p.parse_args([])\nprint(getattr(n, "x"))\n',
                                  "argparse Namespace getattr() is not built"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


if __name__ == "__main__":
    unittest.main()
