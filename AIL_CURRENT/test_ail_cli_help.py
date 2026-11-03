"""The `ail` command's help: every subcommand answers --help with exit 0, and the top-level help
names them all.  The command lives in packaging/ail_lang/cli.py, outside the SDK export."""
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
PACKAGING = REPO / "packaging"

COMMANDS = (
    "run", "build", "check", "new", "lsp",
    "compile", "compile-module", "compile-library", "compile-c",
    "api", "api-builtin", "context", "edit",
    "doctor", "integrity", "cache", "export-sdk",
)


def run_cli(*args):
    env = dict(os.environ, PYTHONPATH=str(PACKAGING), AIL_SDK_DIR=str(ROOT),
               AIL_SERVER="0", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-B", "-m", "ail_lang", *args], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=120)


class CliHelpTests(unittest.TestCase):
    def setUp(self):
        if not (PACKAGING / "ail_lang" / "cli.py").is_file():
            self.skipTest("packaging/ail_lang is not beside AIL_CURRENT (an SDK export)")

    def test_help_lists_every_subcommand(self):
        done = run_cli("--help")
        self.assertEqual(done.returncode, 0, done.stderr)
        for command in COMMANDS:
            with self.subTest(command=command):
                self.assertRegex(done.stdout, r"(?m)^  %s\b" % re.escape(command))
        self.assertIn("--version", done.stdout)
        self.assertIn("experimental", done.stdout)
        self.assertNotIn("brace", done.stdout.lower())

    def test_every_subcommand_help_exits_zero(self):
        for command in COMMANDS:
            with self.subTest(command=command):
                done = run_cli(command, "--help")
                self.assertEqual(done.returncode, 0, done.stderr)
                text = done.stdout + done.stderr
                self.assertIn("usage:", text.lower())
                self.assertNotIn("brace", text.lower())

    def test_no_arguments_and_unknown_command_are_usage_errors(self):
        for args in ((), ("no-such-command",)):
            with self.subTest(args=args):
                done = run_cli(*args)
                self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
                self.assertIn("usage:", done.stderr.lower())

    def test_version(self):
        done = run_cli("--version")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertRegex(done.stdout.strip(), r"^ailc \d+\.\d+")


if __name__ == "__main__":
    unittest.main()
