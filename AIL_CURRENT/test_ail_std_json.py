"""The `json` stdlib lab programs: the ones that build must print CPython's stdout and exit code.

`lab/stdlib/json/` holds twelve realistic programs that use json.dumps / json.loads / json.load /
json.dump / json.JSONDecodeError, the common keyword arguments and error handling. Two of them are
named refusals (json.JSONEncoder with cls=, and json.dump / json.load on a file); the other ten build
in the default mode and are run here next to CPython in a fresh directory, because some of them read
or write a JSON file in the working directory. The program text is never changed: the compiled
binary and CPython run the same source.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "json"

CASES = [
    ("01_config_roundtrip", b""),
    ("02_api_response", b""),
    ("03_jsonl_stats", b""),
    ("05_decoder_hooks", b""),
    ("06_stdio_typed", b"[1, 2, 3]\n"),
    ("07_decode_error", b""),
    ("08_nested_typed", b""),
    ("09_numbers", b""),
    ("10_unicode_text", b""),
    ("11_pretty_options", b""),
]


def run(path, data, cwd):
    return subprocess.run([str(path)], input=data, cwd=cwd, capture_output=True, timeout=300)


class StdJsonPrograms(unittest.TestCase):
    def test_passing_programs_match_cpython(self):
        for name, data in CASES:
            source = PROGRAMS / (name + ".py")
            self.assertTrue(source.is_file(), source)
            with tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                build = directory / "build"
                oracle_dir = directory / "oracle"
                run_dir = directory / "run"
                for each in (build, oracle_dir, run_dir):
                    each.mkdir()
                text = source.read_text(encoding="utf-8")
                (build / (name + ".py")).write_text(text, encoding="utf-8")
                (oracle_dir / (name + ".py")).write_text(text, encoding="utf-8")
                exe = build / name
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
                for key in ("AIL_NO_GENERAL", "AIL_STRICT", "AIL_UNIFIED_FORCE", "AIL_IR"):
                    env.pop(key, None)
                built = subprocess.run(
                    [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", name + ".py",
                     "--syntax", "python", "-o", name],
                    cwd=build, capture_output=True, text=True, timeout=900, env=env)
                self.assertEqual(built.returncode, 0, "%s\n%s%s" % (name, built.stdout, built.stderr))
                if not exe.exists():
                    exe = exe.with_suffix(".exe")
                want = subprocess.run(
                    [sys.executable, "-X", "utf8", name + ".py"], input=data, cwd=oracle_dir,
                    capture_output=True, timeout=300)
                got = run(exe, data, run_dir)
                self.assertEqual(got.returncode, want.returncode,
                                 "%s\n%s" % (name, got.stderr.decode("utf-8", "replace")))
                if got.stdout != want.stdout:
                    want_lines, got_lines = want.stdout.splitlines(), got.stdout.splitlines()
                    for line, (a, b) in enumerate(zip(want_lines, got_lines), 1):
                        if a != b:
                            self.fail("%s line %d:\n  compiled: %r\n  CPython:  %r"
                                      % (name, line, b, a))
                    self.fail("%s: output lengths differ" % name)


if __name__ == "__main__":
    unittest.main()
