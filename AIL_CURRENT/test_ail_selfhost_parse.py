"""shparse1: selfhost/src/ailparse.py parses expressions like CPython's ast in eval mode.

Stage 1 compares ``ailparse.parse_expr`` with ``ast.parse(text, mode="eval")`` on 200 fixed S376
expression segments and on the edge expressions below.  Stage 2 builds ``selfhost/drv/expr_drv.py``
with AIL and requires byte-identical output with stage 1 on 20 fixed S376 expressions and the edge
expressions; it is skipped without a C compiler.
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SRC = REPO / "selfhost" / "src"
REF = REPO / "selfhost" / "ref"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REF))
import ailast  # noqa: E402
import ailparse  # noqa: E402
import expr_ref  # noqa: E402

HAVE_CC = shutil.which(os.environ.get("PIPE_CC") or "gcc") is not None

EDGE = [
    "1", "0x_1F", "1_000", "1.5E+3", ".5", "5.", "1e-5", "True", "False", "None", "...",
    "'a' 'b'", "r'\\n'", "b'\\x00b\\xff'", "rb'\\s+'", "u'x'", "'a\\\nb'", "'''a\nb'''",
    "f'a{x}b'", "f'{{}}'", "f'{x=}'", "f'{x = }'", "f'{x=:>5}'", "f'{x!r}'", "f'{x:}'",
    "f'{x:{y}.{z}f}'", "f'{x:{y!r}}'", "f'{x:%H:%M}'", "f'a' 'b' f'{x}'", "f'{x=!s:>{w}}'",
    "rf'\\{a}\\d'", "a + b * c - d / e // f % g @ h", "a << b >> c | d ^ e & f", "-x ** y",
    "x ** -y", "~x", "not a", "a or b or c", "a and b and c", "a < b <= c", "a not in b",
    "a is not b", "a if c else b if d else e", "lambda: 1", "lambda x, y=2, *a, k=3, **kw: x",
    "lambda x, /, y, *, z: y", "a.b.c", "f(1, x, k=2, *a, **b)", "a[1]", "a[1:2]", "a[:]",
    "a[::2]", "a[1:2, 3]", "a[1, 2]", "a[()]", "[1, 2, *x]", "(1, 2, *x)", "{1, 2, *x}",
    "{'a': 1, **d}", "{}", "[]", "()", "(x)", "(x,)", "[x * y for x in a for y in b if x if y]",
    "{x for x in a}", "{k: v for k, v in d.items()}", "(x for x in a)", "f(x for x in a)",
    "sum(x*x for x in a)", "[y for y in range(3) if (z := y)]", "(x := 1)", "f(x := 1)",
    "[x := 1]", "(a := 1, b)", "await foo()", "f'{x:{y:{z}}}'", "f'{ {1: 2}[1] }'",
    "f'{x = :>{w}}'", "f'{(x:=5)}'", "f'{x:>{y}{z}}'", "f'{x!r:>{y}}'",
    "f'{ x=}'", "f'{ x + y = }'", "f'{x:{{}}}'", "f'{x:a{{}}}'", "f'{x:{{a}}}'",
    "b'\\u0041'", "b'\\N{BULLET}'", "b'\\400'", "b'\\777'", "U'x'", "U'a' 'b'", "U'a' f'{x}'",
]


def fixed_files():
    paths = expr_ref.read_paths(str(REPO / "selfhost" / "CORPUS.txt"))
    return [str(REPO / p) for p in paths[::12][:30] if (REPO / p).exists()]


def stage1_one(text):
    return ailast.dump(ailparse.parse_expr(text))


def ref_one(text):
    return ast.dump(ast.parse(text, mode="eval").body, include_attributes=False)


def parseable_segments(files, want):
    out = []
    for path in files:
        for _, text in expr_ref.segments_of(path):
            try:
                ast.parse(text, mode="eval")
            except SyntaxError:
                continue
            out.append(text)
            if len(out) >= want:
                return out
    return out


def write_segments(outdir, texts):
    os.makedirs(outdir, exist_ok=True)
    listing = []
    for n, text in enumerate(texts):
        path = os.path.join(outdir, "%04d.expr" % n)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        listing.append(path)
    lst = os.path.join(outdir, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        f.write("\n".join(listing) + "\n")
    return lst


def run(cmd, env=None):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, env=env, timeout=900)


class ParseTest(unittest.TestCase):
    def test_s376_200_expressions_stage1(self):
        texts = parseable_segments(fixed_files(), 200)
        self.assertEqual(len(texts), 200)
        for text in texts:
            with self.subTest(text=text[:80]):
                self.assertEqual(stage1_one(text), ref_one(text))

    def test_edge_expressions_stage1(self):
        for text in EDGE:
            with self.subTest(text=text[:80]):
                self.assertEqual(stage1_one(text), ref_one(text))

    def test_ellipsis_and_unsupported_refusals(self):
        self.assertEqual(stage1_one("..."), ref_one("..."))
        with self.assertRaises(ailparse.ParseError) as cm:
            ailparse.parse_expr("yield x")
        self.assertTrue(str(cm.exception).startswith("ailparse:"))

    @unittest.skipUnless(HAVE_CC, "no C compiler")
    def test_stage2_matches_stage1(self):
        texts = parseable_segments(fixed_files(), 20)
        self.assertEqual(len(texts), 20)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            exe = tmp / "expr_drv"
            env = dict(os.environ, AIL_PATH=str(SRC), AIL_NO_CACHE="1")
            build = run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                         "selfhost/drv/expr_drv.py", "-o", str(exe)], env)
            self.assertEqual(build.returncode, 0, build.stderr[-800:])
            s1_files = write_segments(str(tmp / "s376"), texts)
            s1 = run([sys.executable, "-B", "selfhost/drv/expr_drv.py", s1_files],
                     dict(os.environ, PYTHONPATH=str(SRC)))
            self.assertEqual(s1.returncode, 0, s1.stderr[-500:])
            s2 = run([str(exe), s1_files])
            self.assertEqual(s2.returncode, 0, s2.stderr[-500:])
            self.assertEqual(s2.stdout, s1.stdout)
            self.assertEqual(s1.stdout.count(b"\n== ") + 1, 20)
            edge_files = write_segments(str(tmp / "edge"), EDGE)
            e1 = run([sys.executable, "-B", "selfhost/drv/expr_drv.py", edge_files],
                     dict(os.environ, PYTHONPATH=str(SRC)))
            self.assertEqual(e1.returncode, 0, e1.stderr[-500:])
            e2 = run([str(exe), edge_files])
            self.assertEqual(e2.returncode, 0, e2.stderr[-500:])
            self.assertEqual(e2.stdout, e1.stdout)


if __name__ == "__main__":
    unittest.main()
