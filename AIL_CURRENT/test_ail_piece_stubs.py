"""The general runtime leaves out the big int pieces a program cannot reach (biggate.PIECES), but keeps their prototypes for the
unused inline operators.  Every prototype that lost its definition gets a trapping stub (biggate.absent_stubs), so the finished C
has no function that is declared and never defined.  Before, the C compiled and linked only because `-O2` folded the dead calls
away: `-O0` failed to link (`ail_int_divmod` -> `ail_big_divmod`, `ail__round_int_big` -> `ail__int_pow`), and a runtime built as
its own unit (docs/design/COMPILE_TIME.md 2.2) could not have been.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import biggate  # noqa: E402

CC = shutil.which("cc") or shutil.which("gcc")

PROGRAM = """import sys


def format_codepoint(ch: str) -> str:
    code = ord(ch)
    return f"U+{code:04X} {ch}"


def main() -> None:
    data = sys.stdin.read()
    lines = data.splitlines()
    first = next((line for line in lines if line != ""), "")
    out = "\\n".join(format_codepoint(ch) for ch in first)
    if out:
        sys.stdout.write(out + "\\n")


if __name__ == "__main__":
    main()
"""
WANT = "U+0061 a\nU+0062 b\nU+0063 c\n"
FLAGS = ["-fno-tree-slp-vectorize", "-ffp-contract=off", "-fopenmp-simd", "-fno-asynchronous-unwind-tables"]


class Stubs(unittest.TestCase):
    def test_a_prototype_without_a_body_gets_a_stub_before_the_program(self):
        text = ("static AIL_BIGFN ail_obj ail_big_shl(ail_ctx *cx, ail_obj a, int64_t n);\n"
                "static AIL_BIGFN void ail_big_divmod(ail_ctx *cx, ail_obj *q);\n"
                "static AIL_BIGFN void ail_big_divmod(ail_ctx *cx, ail_obj *q) {\n    (void)cx;\n}\n"
                "static int unrelated(int x);\n"
                + biggate.USER_MARK + "int main(void) { return 0; }\n")
        out = biggate.absent_stubs(text)
        head, user = out.split(biggate.USER_MARK)
        self.assertIn("ail_big_shl(ail_ctx *cx, ail_obj a, int64_t n) { __builtin_trap(); }", head)
        self.assertEqual(head.count("ail_big_divmod(ail_ctx *cx, ail_obj *q)"), 2, "the defined one gets no stub")
        self.assertNotIn("unrelated(int x) {", out)
        self.assertEqual(user, "int main(void) { return 0; }\n")
        self.assertEqual(biggate.absent_stubs(out), out, "a second pass adds nothing")

    def test_a_text_with_every_body_is_unchanged(self):
        text = "static AIL_BIGFN void ail_big_divmod(ail_ctx *cx, ail_obj *q) {\n}\n" + biggate.USER_MARK + "x\n"
        self.assertEqual(biggate.absent_stubs(text), text)


@unittest.skipUnless(CC, "no C compiler")
class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        (tmp / "p.py").write_text(PROGRAM, encoding="utf-8")
        cls.exe = tmp / "p_exe"
        cls.dbg = tmp / "p_dbg"
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        cls.made = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(tmp / "p.py"),
                                   "--syntax", "python", "-o", str(cls.exe), "--debug-dir", str(cls.dbg)],
                                  capture_output=True, text=True, timeout=900, env=env)
        cls.c = cls.dbg / "program.c"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_program_is_on_the_general_path_and_runs(self):
        self.assertEqual(self.made.returncode, 0, self.made.stderr[-1500:])
        self.assertIn("ail_op_floordiv", self.c.read_text(encoding="utf-8"), "the general runtime is in the C")
        got = subprocess.run([str(self.exe)], input="abc\n", capture_output=True, text=True, timeout=60)
        self.assertEqual(got.stdout, WANT)

    def test_no_function_is_declared_and_never_defined(self):
        self.assertEqual(self.made.returncode, 0, self.made.stderr[-1500:])
        r = subprocess.run([CC, "-O2", "-Wall", "-Wno-unused-function", "-Wno-unused-variable", "-Wno-unused-but-set-variable",
                            "-Wno-unused-label", "-Wno-misleading-indentation", "-Wno-parentheses", *FLAGS, "-c", str(self.c),
                            "-o", str(Path(self.tmp.name) / "w.o")], capture_output=True, text=True, timeout=600)
        bad = [l for l in r.stderr.splitlines() if "never defined" in l or "implicit declaration" in l]
        self.assertEqual(bad, [], "\n".join(bad[:10]))

    def test_it_links_without_optimisation(self):
        self.assertEqual(self.made.returncode, 0, self.made.stderr[-1500:])
        exe0 = Path(self.tmp.name) / "p_o0"
        r = subprocess.run([CC, "-O0", "-w", *FLAGS, str(self.c), "-o", str(exe0), "-lm"], capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        got = subprocess.run([str(exe0)], input="abc\n", capture_output=True, text=True, timeout=60)
        self.assertEqual(got.stdout, WANT)


if __name__ == "__main__":
    unittest.main()
