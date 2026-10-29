"""Standard library batch 37: the `argparse` subset, compared with CPython 3.12 on both builds.

Every program below is ordinary Python. CPython is the oracle; the compiled program (AIL_IR=0 and
AIL_IR=1) prints the same stdout, stderr and exit status, or the spelling is refused by name at
compile time. Built: `ArgumentParser(description=, prog=, add_help=)`, `add_argument` for long
`--name` options and positionals, `type=` int / float / str / pathlib.Path, `default=`, `required=`,
`dest=`, `choices=` and `help=` (ignored), and `parse_args()` from sys.argv or an explicit list.
Refused by name: short options, actions other than store, nargs, subparsers, groups, the help text,
`parse_args(None)` and a Namespace used as a value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BASIC = r'''import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="probe")
    parser.add_argument('--output', required=True)
    parser.add_argument('--n', type=int, default=3)
    parser.add_argument('--ratio', type=float, default=0.5)
    parser.add_argument('--mode', choices=('fast', 'slow'), default='fast')
    parser.add_argument('--empty', default='d')
    parser.add_argument('--optional')
    parser.add_argument('--base', type=Path, default=Path('a/b.txt'))
    parser.add_argument('target')
    args = parser.parse_args(['--output=o.txt', '--n', '-7', '--ratio', '-.5', '--mode=slow',
                              '--empty=', '--optional', 'v', 'tail'])
    print(args.output, args.n, args.ratio, args.mode, args.empty, args.optional, args.target)
    print(args.n * 2, args.ratio + 0.25, args.mode == 'slow', args.optional is None)
    print(str(args.base), args.base.name)


main()
'''

PATH = r'''import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=Path('a/b.txt'))
    args = parser.parse_args(['--out', '/tmp/a/b/c.txt'])
    print(str(args.out), args.out.name, args.out.suffix, args.out.parent)
    print(str(args.base), args.base.stem)


main()
'''

SYS_ARGV = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--x', default='d')
    parser.add_argument('--n', type=int, default=4)
    parser.add_argument('item')
    args = parser.parse_args()
    print(args.x, args.n + 1, args.item)


main()
'''

ROUTES = r'''import argparse


class Box:
    items: list[str]

    def __init__(self) -> None:
        self.items = ['--x', 'attr']


def parse(values: list[str]) -> str:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--x', default='d')
    args = parser.parse_args(values)
    return args.x


def main() -> None:
    box = Box()
    print(parse(['--x', 'arg']))
    print(parse(box.items))
    print(parse({'argv': ['--x', 'dict']}['argv']))
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--out-name', dest='out', default='dest')
    args = parser.parse_args(['--out-name', 'value'])
    print(args.out)


main()
'''

IMPORT_FORMS = r'''import argparse as ap
from argparse import ArgumentParser


def main() -> None:
    first = ArgumentParser(prog='prog')
    first.add_argument('--a', default='one')
    print(first.parse_args(['--a', 'two']).a)
    second = ap.ArgumentParser(prog='prog')
    second.add_argument('--b', default='three')
    print(second.parse_args(['--b', 'four']).b)


main()
'''

ERRORS = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--x', required=True)
    parser.add_argument('--y')
    args = parser.parse_args([])
    print(args.x, args.y)


main()
'''

UNKNOWN = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--x')
    args = parser.parse_args(['--z'])
    print(args.x)


main()
'''

EXPECTED_ONE = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--x')
    parser.add_argument('--y')
    args = parser.parse_args(['--x', '--y'])
    print(args.x, args.y)


main()
'''

CHOICE = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--mode', choices=('fast', 'slow'))
    args = parser.parse_args(['--mode', 'medium'])
    print(args.mode)


main()
'''

INVALID_INT = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--n', type=int)
    args = parser.parse_args(['--n', 'x'])
    print(args.n)


main()
'''

INVALID_FLOAT = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--ratio', type=float)
    args = parser.parse_args(['--ratio', 'x'])
    print(args.ratio)


main()
'''

BAD_DEFAULT = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--n', type=int, default='x')
    parser.add_argument('--req', required=True)
    args = parser.parse_args([])
    print(args.n, args.req)


main()
'''

SEPARATOR = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--mode', choices=('fast', 'slow'), default='fast')
    parser.add_argument('--x', default='d')
    args = parser.parse_args(['--x=1', '--mode', 'slow', '--', '--mode'])
    print(args.mode, args.x)


main()
'''

USAGE_ORDER = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('target')
    parser.add_argument('--x')
    parser.add_argument('--name', required=True)
    args = parser.parse_args([])
    print(args.x, args.name)


main()
'''

USAGE_WRAP = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--alpha', required=True)
    parser.add_argument('--bravo', required=True)
    parser.add_argument('--charlie', required=True)
    parser.add_argument('--delta', required=True)
    parser.add_argument('--echo', required=True)
    parser.add_argument('--foxtrot', required=True)
    parser.add_argument('input')
    args = parser.parse_args([])
    print(args.alpha, args.input)


main()
'''

SCOPES = r'''import argparse

parser = argparse.ArgumentParser(prog='prog')
parser.add_argument('--shared', default='s')


def first() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--n', type=int, default=1)
    args = parser.parse_args(['--n', '5'])
    print(args.n + 1)


def second() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--n', default='x')
    args = parser.parse_args(['--n', '7'])
    print(args.n + '!')

    def deeper() -> None:
        inner = argparse.ArgumentParser(prog='inner')
        inner.add_argument('--n', default='z')
        args2 = inner.parse_args([])
        print(args2.n + '?')

    deeper()


def shared() -> None:
    args = parser.parse_args(['--shared', 'got'])
    print(args.shared)


first()
second()
shared()
'''

CASES = (
    ("basic", BASIC, False, ()),
    ("path", PATH, False, ()),
    ("sys_argv", SYS_ARGV, False, ('--x=custom', '--n', '9', 'rest')),
    ("routes", ROUTES, False, ()),
    ("import_forms", IMPORT_FORMS, False, ()),
    ("missing_required", ERRORS, True, ()),
    ("unknown_option", UNKNOWN, True, ()),
    ("expected_one", EXPECTED_ONE, True, ()),
    ("invalid_choice", CHOICE, True, ()),
    ("invalid_int", INVALID_INT, True, ()),
    ("invalid_float", INVALID_FLOAT, True, ()),
    ("bad_default", BAD_DEFAULT, True, ()),
    ("separator", SEPARATOR, True, ()),
    ("usage_order", USAGE_ORDER, True, ()),
    ("usage_wrap", USAGE_WRAP, True, ()),
    ("scopes", SCOPES, False, ()),
)


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, source, exe


class Stdlib37Tests(unittest.TestCase):
    def check(self, name, text, stderr, argv, ir):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s"
                             % (name, env["AIL_IR"], built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle), *argv], capture_output=True,
                                  timeout=300, cwd=directory)
            got = subprocess.run([str(exe), *argv], capture_output=True, timeout=300, cwd=directory)
            self.assertEqual(got.returncode, want.returncode, "%s (AIL_IR=%s): %s"
                             % (name, env["AIL_IR"], got.stderr[-400:]))
            self.assertEqual(got.stdout, want.stdout, name)
            if stderr:
                self.assertEqual(got.stderr, want.stderr, name)

    def test_programs_match_cpython(self):
        for name, text, stderr, argv in CASES:
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, text, stderr, argv, ir)

    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_argument('--verbose', action='store_true')\n"
                     "    args = parser.parse_args([])\n"
                     "    print(args.verbose)\n\n\nmain()\n",
                     "argparse.add_argument(action=) is built only for the default 'store'")
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_argument('-x')\n"
                     "    args = parser.parse_args([])\n"
                     "    print(args.x)\n\n\nmain()\n",
                     "argparse short options are not built")
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_argument('--n', nargs='*')\n"
                     "    args = parser.parse_args([])\n"
                     "    print(args.n)\n\n\nmain()\n",
                     "argparse.add_argument(nargs=) is not built")
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_subparsers()\n"
                     "    args = parser.parse_args([])\n"
                     "    print(args)\n\n\nmain()\n",
                     "argparse.ArgumentParser.add_subparsers is not built")
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_argument('--x', default='d')\n"
                     "    args = parser.parse_args(None)\n"
                     "    print(args.x)\n\n\nmain()\n",
                     "argparse.parse_args(None) is not built")
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_argument('--x', default='d')\n"
                     "    args = parser.parse_args([])\n"
                     "    print(args)\n\n\nmain()\n",
                     "the argparse Namespace used as a value is not built")
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_argument('--n', type=int, choices=('1', '2'))\n"
                     "    args = parser.parse_args(['--n', '1'])\n"
                     "    print(args.n)\n\n\nmain()\n",
                     "argparse.add_argument(choices=) is built only with type=str")
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_argument('target', dest='name')\n"
                     "    args = parser.parse_args(['x'])\n"
                     "    print(args.name)\n\n\nmain()\n",
                     "argparse.add_argument(dest=) on a positional is not built")
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_argument('target', required=True)\n"
                     "    args = parser.parse_args(['x'])\n"
                     "    print(args.target)\n\n\nmain()\n",
                     "argparse.add_argument(required=) on a positional is not built")
        self.refused("import argparse\n\n\n"
                     "def main() -> None:\n"
                     "    parser = argparse.ArgumentParser()\n"
                     "    parser.add_argument('--x', default='d')\n"
                     "    args = parser.parse_args(['-h'])\n"
                     "    print(args.x)\n\n\nmain()\n",
                     "argparse help output (-h/--help) is not built")


if __name__ == "__main__":
    unittest.main()
