"""Real programs from `lab/stdlib/re/` that use `re`, built and compared with CPython on both IR builds.

The programs are ordinary Python (log parsing, validation, templating, CSV fields, tokenizing, phone and
date normalisation, redaction and URL rewriting).  Each one is run by CPython as the oracle and by the
compiled program; stdout and the exit code must agree.  `log_summary.py` stays a named refusal (it uses
`m.groupdict()`), which is recorded in `lab/stdlib/re/RESULTS.md`.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "re"

PASSING = (
    "config_parse",
    "csv_fields",
    "date_normalize",
    "email_check",
    "ip_validate",
    "phone_fix",
    "redact",
    "template_render",
    "tokenizer",
    "url_rewrite",
    "word_count",
)


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, source, exe


class StdRePrograms(unittest.TestCase):
    def test_programs_match_cpython(self):
        if not PROGRAMS.is_dir():
            self.skipTest("lab/stdlib/re is not present")
        for name in PASSING:
            program = PROGRAMS / (name + ".py")
            self.assertTrue(program.is_file(), program)
            text = program.read_text(encoding="utf-8")
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                oracle = Path(directory, "oracle.py")
                oracle.write_text(text, encoding="utf-8")
                want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True,
                                      timeout=300)
                for ir in ("0", "1"):
                    built, _, exe = compile_python(directory, text, name + ir, AIL_IR=ir)
                    self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (
                        name, ir, built.stdout, built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                    self.assertEqual(got.returncode, want.returncode,
                                     "%s (AIL_IR=%s)\n%s" % (
                                         name, ir, got.stderr.decode("utf-8", "replace")))
                    if got.stdout != want.stdout:
                        want_lines, got_lines = want.stdout.splitlines(), got.stdout.splitlines()
                        for line, (a, b) in enumerate(zip(want_lines, got_lines), 1):
                            if a != b:
                                self.fail("%s (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                          % (name, ir, line, b, a))
                        self.fail("%s (AIL_IR=%s): output lengths differ" % (name, ir))


    def test_match_tuple_receiver_evaluated_once(self):
        text = (
            "import re\n"
            "calls = [0]\n"
            "def get():\n"
            "    calls[0] += 1\n"
            "    return re.search(r\"(?P<x>a)(b)\", \"ab\")\n"
            "print(get().group(1, 2))\n"
            "print(calls[0])\n"
            "calls[0] = 0\n"
            "print(get().span())\n"
            "print(calls[0])\n"
            "calls[0] = 0\n"
            "print(get().span(\"x\"))\n"
            "print(calls[0])\n"
            "calls[0] = 0\n"
            "print(get().group(\"x\", 2, 0))\n"
            "print(calls[0])\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True,
                                  timeout=300)
            for ir in ("0", "1"):
                built, _, exe = compile_python(directory, text, "sideeffect" + ir, AIL_IR=ir)
                self.assertEqual(built.returncode, 0, "side effect (AIL_IR=%s)\n%s%s" % (
                    ir, built.stdout, built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, got.stderr.decode("utf-8", "replace"))
                self.assertEqual(got.stdout, want.stdout, "side effect (AIL_IR=%s)" % ir)


    def test_tuple_on_non_match_receiver(self):
        # a span()/group(a, b) tuple on a receiver that is not a Match: the build must terminate and the
        # program must raise what CPython raises (AttributeError), not hang the typed front end.
        text = (
            "import re\n"
            "print(re.search(r\"(a)\", \"a\").span(0))\n"
            "print(re.search(r\"(a)\", \"a\").group(0, 1))\n"
            "n = None\n"
            "try:\n"
            "    print(n.span())\n"
            "except AttributeError:\n"
            "    print(\"AttributeError\")\n"
            "try:\n"
            "    print(n.group(0, 0))\n"
            "except AttributeError:\n"
            "    print(\"AttributeError\")\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True,
                                  timeout=300)
            for ir in ("0", "1"):
                built, _, exe = compile_python(directory, text, "nonmatch" + ir, AIL_IR=ir)
                self.assertEqual(built.returncode, 0, "non-match (AIL_IR=%s)\n%s%s" % (
                    ir, built.stdout, built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, got.stderr.decode("utf-8", "replace"))
                self.assertEqual(got.stdout, want.stdout, "non-match (AIL_IR=%s)" % ir)


if __name__ == "__main__":
    unittest.main()
