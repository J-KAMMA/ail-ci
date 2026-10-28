"""Standard library batch 23: the `argparse` subset, compared with CPython 3.12 on both builds.

Every program below is ordinary Python. CPython is the oracle; the compiled program (AIL_IR=0 and
AIL_IR=1) prints the same stdout and exits with the same status, or the spelling is refused by name
at compile time. Built: `ArgumentParser(description=, prog=, add_help=)`, `add_argument` for long
`--name` options and positionals, `type=` int / float / str / pathlib.Path, `default=`, `required=`,
`choices=` and `help=` (ignored), and `parse_args()` from sys.argv or an explicit list. Refused by
name: short options, actions other than store, nargs, subparsers, groups and the help text.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BASIC = r'''import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="probe")
    parser.add_argument('--output', required=True)
    parser.add_argument('--n', type=int, default=3)
    parser.add_argument('--ratio', type=float, default=0.5)
    parser.add_argument('--mode', choices=('fast', 'slow'), default='fast')
    parser.add_argument('--empty', default='d')
    parser.add_argument('--optional')
    parser.add_argument('target')
    args = parser.parse_args(['--output=o.txt', '--n', '-7', '--ratio', '2.5', '--mode=slow',
                              '--empty=', '--optional', 'v', 'tail'])
    print(args.output, args.n, args.ratio, args.mode, args.empty, args.optional, args.target)
    print(args.n * 2, args.ratio + 0.25, args.mode == 'slow', args.optional is None)


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
    parser = argparse.ArgumentParser()
    parser.add_argument('--x', default='d')
    parser.add_argument('--n', type=int, default=4)
    parser.add_argument('item')
    args = parser.parse_args()
    print(args.x, args.n + 1, args.item)


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

CASES = (
    ("basic", BASIC, False, ()),
    ("path", PATH, False, ()),
    ("sys_argv", SYS_ARGV, False, ('--x=custom', '--n', '9', 'rest')),
    ("missing_required", ERRORS, True, ()),
    ("unknown_option", UNKNOWN, True, ()),
    ("expected_one", EXPECTED_ONE, True, ()),
)


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, source, exe


class Stdlib23Tests(unittest.TestCase):
    def check(self, name, text, stderr, argv, ir):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s"
                             % (name, env["AIL_IR"], built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle), *argv], capture_output=True,
                                  timeout=300)
            got = subprocess.run([str(exe), *argv], capture_output=True, timeout=300)
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


if __name__ == "__main__":
    unittest.main()
