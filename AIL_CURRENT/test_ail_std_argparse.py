"""The bundled `argparse` module: the twelve realistic CLI programs in lab/stdlib/argparse.

Ten of them build in the default mode and on the forced general path (AIL_UNIFIED_FORCE=1), and each
run prints exactly what CPython prints (stdout and exit code, plus stderr when the run succeeds) for
normal use, defaults, nargs / append / count / const actions, choices, type conversion, help and the
error exits.
`errtool` (a caught SystemExit) and `subcmd` (add_subparsers) are refused by name; those two are the
follow-ups recorded in lab/stdlib/argparse/RESULTS.md.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "argparse"


CASES = {
    "backup": [
        ([], None), (["a", "b"], None),
        (["src", "dst", "--level", "2", "--exclude", "x", "--exclude", "y", "-q"], None),
        (["a", "b", "--level", "9"], None), (["a"], None),
        (["a", "b", "-c", "--exclude", ".git"], None), (["a", "b", "--exclude"], None),
        (["a", "b", "--level"], None), (["a", "b", "--level=x"], None),
        (["--", "a", "b"], None), (["a", "b", "--help"], None),
    ],
    "calc": [
        ([], None), (["1"], None), (["1", "2.5", "3"], None),
        (["--op", "mul", "2", "3", "4"], None), (["--op", "add", "1", "x"], None),
        (["4", "5", "extra", "--zzz"], None), (["--op", "pow", "1", "2"], None),
        (["--op=add", "1", "2"], None), (["-1", "-2.5"], None),
        (["--", "1", "2"], None), (["--help"], None),
    ],
    "config": [
        ([], None), (["--json", "-o", "out"], None), (["--yaml", "--name", "x"], None),
        (["--json", "--yaml"], None), (["--version"], None), (["--help"], None),
        (["--json=1"], None), (["-o"], None), (["--name=z"], None),
    ],
    "greet": [
        ([], None), (["Bob"], None),
        (["Bob", "--greeting", "Hi", "--times", "2", "--excited"], None),
        (["Bob", "--times", "0"], None), (["Bob", "--times", "x"], None),
        (["--greeting", "Hi"], None), (["--", "Bob"], None), (["Bob", "--times", "-2"], None),
        (["Bob", "--times=-1"], None), (["Bob", "--excited=false"], None), (["--help"], None),
    ],
    "helpfmt": [
        ([], None), (["app.tar"], None),
        (["app.tar", "-e", "prod", "--dry-run", "--retries", "5"], None),
        (["app.tar", "-e", "test"], None), (["app.tar", "--verbose"], None),
        (["app.tar", "--dry-run=false"], None), (["app.tar", "--retries", "x"], None),
        (["--", "app.tar"], None), (["--help"], None),
    ],
    "scan": [
        ([], None), (["-v", "-v", "--color", "always", "a", "b"], None), (["-vvv", "x"], None),
        (["--color", "sometimes"], None), (["--", "-x"], None), (["-x"], None),
        (["--color=never", "p"], None), (["-vx"], None), (["-v=2"], None), (["--help"], None),
    ],
    "search": [
        (["--pattern", "x", "q", "r"], None),
        (["--pattern", "x", "--path", "a", "--path", "b", "--limit", "2", "--mode", "full", "one"], None),
        (["q"], None), (["--pattern", "x"], None), (["--pattern", "x", "--limit", "z", "q"], None),
        (["--pattern=x", "--limit=0", "q"], None), (["--pattern", "x", "--mode=slow", "q"], None),
        (["--", "--pattern", "x"], None), (["--help"], None),
    ],
    "server": [
        ([], None), (["-H", "0.0.0.0", "-p", "9000", "--workers", "8", "--debug", "--tag", "a", "--tag", "b"], None),
        (["--workers", "--debug"], None), (["--log-level", "trace"], None), (["-p", "x"], None),
        (["-p0"], None), (["--workers=5"], None), (["--tag", "--tag"], None), (["-Hh"], None),
        (["--", "x"], None), (["--help"], None),
    ],
    "tag": [
        ([], None), (["rec"], None),
        (["rec", "label", "--pair", "k", "v", "--tag", "a", "--tag", "b", "-vv", "--color"], None),
        (["rec", "--pair", "k"], None), (["rec", "--pair", "k", "v", "--tag=a"], None),
        (["-vvv", "rec"], None), (["--color", "rec"], None), (["rec", "--color=red"], None),
        (["--", "rec"], None), (["--help"], None),
    ],
    "words": [
        ([], "a b a C c\n"), (["--top", "2"], "a b a C c\n"),
        (["--ignore-case", "--top", "2"], "a b a C c\n"), (["--separator", ":"], "x y x\n"),
        (["f1", "f2"], "a\n"), (["--top", "x"], "a\n"), (["--"], ""),
        (["--", "-f"], "a\n"), (["--help"], "a\n"),
    ],
}

REFUSED = {
    "errtool": "a caught exception type SystemExit",
    "subcmd": "the method .add_subparsers()",
}


def compile_program(directory, name, forced_general):
    exe = Path(directory) / (name + ".py")
    env = dict(os.environ, AIL_NO_CACHE="1")
    if forced_general:
        env["AIL_UNIFIED_FORCE"] = "1"
    built = subprocess.run(
        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
         str(PROGRAMS / (name + ".py")), "--syntax", "python", "-o", str(exe)],
        capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run(command, args, stdin):
    return subprocess.run(command + args, input=stdin, capture_output=True, text=True, timeout=120)


class ArgparsePrograms(unittest.TestCase):
    def test_built_programs_match_cpython(self):
        for forced_general in (False, True):
            with self.subTest(forced_general=forced_general), tempfile.TemporaryDirectory() as directory:
                for name, cases in CASES.items():
                    built, exe = compile_program(directory, name, forced_general)
                    self.assertEqual(built.returncode, 0, "%s\n%s%s" % (name, built.stdout, built.stderr))
                    source = PROGRAMS / (name + ".py")
                    for args, stdin in cases:
                        with self.subTest(program=name, args=args):
                            want = run([sys.executable, str(source)], args, stdin)
                            got = run([str(exe)], args, stdin)
                            self.assertEqual(got.returncode, want.returncode, got.stderr[-400:])
                            self.assertEqual(got.stdout, want.stdout)
                            if want.returncode == 0:
                                self.assertEqual(got.stderr, want.stderr)

    def test_refusals_name_the_feature(self):
        for name, wanted in REFUSED.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_program(directory, name, False)
                shown = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + name)
                self.assertIn(wanted, shown)
                self.assertIn("write instead:", shown)
                self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
