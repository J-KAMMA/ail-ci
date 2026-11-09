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
    "f'{x:{{}}{{}}}'", "f'{x:{y}{{}}}'", "f'{x:a{{}}{{}}}'", "f'{x:{{}}{{}}{{}}}'",
    "f'{x}' ''", "'' f'{x}'", "f'{x}' '' f'{y}'", "f'{x}' u'' 'a'", "'a' u'a' f'{x}'",
    "a[*b]", "a[*b,]", "a[*b, c]",
    "b'\\u0041'", "b'\\N{BULLET}'", "b'\\400'", "b'\\777'", "U'x'", "U'a' 'b'", "U'a' f'{x}'",
]

REFUSED = [
    "(*a)", "lambda /: 1", "lambda /, x: 1", "lambda *, : 1", "lambda *,: 1",
    "lambda *, **kw: 1", "lambda x, /, /: 1", "yield x",
]

# shparse2 snippets: 5 S376-legal modules and 15 that CPython's ast.parse rejects.  The test only
# requires that ailparse.parse and ast.parse agree on error versus no error (messages may differ).
SNIPPETS = [
    "return 1\n",
    "yield 1\n",
    "x = 1; y = 2\n",
    "if x: pass\nelif y: pass\nelse: pass\n",
    "with a as b, c as d: pass\n",
    "x = (1\n",
    "if x:\npass\n",
    "def f(:\n    pass\n",
    "x =\n",
    "1 +\n",
    "x = 1 +\n",
    "if x:\n    pass\n  else:\n    pass\n",
    "x = 'unterminated\n",
    "for x in:\n    pass\n",
    "def f():\n",
    "class C(:\n    pass\n",
    "try:\n    pass\n",
    "with x as:\n    pass\n",
    "import\n",
    "from import x\n",
]

# Reviewer boundary cases.  BOUNDARY_VALID must dump like `ast.parse`; BOUNDARY_INVALID must be
# rejected where `ast.parse` rejects it, and BOUNDARY_REFUSED names constructs this step refuses by
# name although CPython accepts them (they have zero occurrences in S376).
BOUNDARY_VALID = [
    "del a, b[0], c.d\n",
    "del a[0], b.c\n",
    "del (a, b)\n",
    "x: int = 1\n",
    "(x): int = 1\n",
    "(x): int\n",
    "a.b: int = 1\n",
    "a[0]: int = 1\n",
    "with (): pass\n",
    "with (a as b, c as d): pass\n",
    "try:\n    pass\nexcept* E as e:\n    pass\n",
    "type = 5\n",
    "type(x)\n",
]
BOUNDARY_INVALID = [
    "x y\n",
    "1 2\n",
    "print() print()\n",
    "x = 1 y = 2\n",
    "a, b: int = 1, 2\n",
    "a, b += 1\n",
    "from . import ()\n",
    "try:\n    pass\nexcept E:\n    pass\nexcept* F:\n    pass\n",
    "\ufeffx = 1\n",
    "x = 1\n\ufeff",
    "x\u200b = 1\n",
    "\U0001f642 = 1\n",
]
BOUNDARY_REFUSED = [
    "type X = int\n",
    "type X[T] = int\n",
    "match x:\n    case 1:\n        pass\n",
    "def f[T](x):\n    pass\n",
    "class C[T]:\n    pass\n",
    "caf\u00e9 = 1\n",
    "\u2167 = 1\n",
]


def module_dump_ail(path):
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    return ailast.dump(ailparse.parse(text))


def module_dump_ref(path):
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    return ast.dump(ast.parse(text, filename=path), include_attributes=False)

# Format specs CPython's own 3.12 patch releases do not agree on.  `ailparse` reproduces the tree of
# the version lab/selfhost/PARSE.md pins (3.12.0-3.12.3), so the expected dump is written here
# instead of taken from the running interpreter; 3.12.4 and later moved an escaped `{{` out of a
# format spec into literal text of the enclosing f-string (`f'{x:{{}}}'` becomes `[FormattedValue(
# Dict())]` where 3.12.3 has `[Constant(''), FormattedValue(Dict()), Constant('')]`, and
# `f'{x:{{}}{{}}}'` keeps a literal `'}'`).  Every entry evaluates to the same string on both.
REF_PINS = {
    "f'{x:{{}}}'":
        "JoinedStr(values=[FormattedValue(value=Name(id='x', ctx=Load()), conversion=-1, "
        "format_spec=JoinedStr(values=[Constant(value=''), FormattedValue(value=Dict(keys=[], "
        "values=[]), conversion=-1), Constant(value='')]))])",
    "f'{x:{{a}}}'":
        "JoinedStr(values=[FormattedValue(value=Name(id='x', ctx=Load()), conversion=-1, "
        "format_spec=JoinedStr(values=[Constant(value=''), FormattedValue(value=Set(elts=[Name("
        "id='a', ctx=Load())]), conversion=-1), Constant(value='')]))])",
    "f'{x:{{}}{{}}}'":
        "JoinedStr(values=[FormattedValue(value=Name(id='x', ctx=Load()), conversion=-1, "
        "format_spec=JoinedStr(values=[Constant(value=''), FormattedValue(value=Dict(keys=[], "
        "values=[]), conversion=-1), Constant(value=''), FormattedValue(value=Dict(keys=[], "
        "values=[]), conversion=-1), Constant(value='')]))])",
    "f'{x:{y}{{}}}'":
        "JoinedStr(values=[FormattedValue(value=Name(id='x', ctx=Load()), conversion=-1, "
        "format_spec=JoinedStr(values=[FormattedValue(value=Name(id='y', ctx=Load()), conversion=-1), "
        "Constant(value=''), FormattedValue(value=Dict(keys=[], values=[]), conversion=-1), "
        "Constant(value='')]))])",
    "f'{x:a{{}}{{}}}'":
        "JoinedStr(values=[FormattedValue(value=Name(id='x', ctx=Load()), conversion=-1, "
        "format_spec=JoinedStr(values=[Constant(value='a'), FormattedValue(value=Dict(keys=[], "
        "values=[]), conversion=-1), Constant(value=''), FormattedValue(value=Dict(keys=[], "
        "values=[]), conversion=-1), Constant(value='')]))])",
    "f'{x:{{}}{{}}{{}}}'":
        "JoinedStr(values=[FormattedValue(value=Name(id='x', ctx=Load()), conversion=-1, "
        "format_spec=JoinedStr(values=[Constant(value=''), FormattedValue(value=Dict(keys=[], "
        "values=[]), conversion=-1), Constant(value=''), FormattedValue(value=Dict(keys=[], "
        "values=[]), conversion=-1), Constant(value=''), FormattedValue(value=Dict(keys=[], "
        "values=[]), conversion=-1), Constant(value='')]))])",
}


def fixed_files():
    paths = expr_ref.read_paths(str(REPO / "selfhost" / "CORPUS.txt"))
    return [str(REPO / p) for p in paths[::12][:30] if (REPO / p).exists()]


def _strip_empty_constants(dump):
    """Drop CPython's format-spec empty `Constant` nodes so a patch release's spelling is not compared.

    CPython 3.12.0-3.12.3 (the version lab/selfhost/PARSE.md was measured on) gives a format spec an
    empty `Constant(value='')` before each `{{` group and at the end of a spec that ends in a
    replacement field; 3.12.4-3.12.16 dropped or moved some of them (`f'{x:{{}}}'` is
    `[Constant(''), FormattedValue(Dict()), Constant('')]` on 3.12.3 but `[FormattedValue(Dict())]`
    on 3.12.16, and `f'{x:{{}}{{}}}'` keeps a literal `'}'` on 3.12.16 where 3.12.3 has a second
    `{{` group). Both spellings evaluate the same, and `ailparse` reproduces the documented 3.12.3
    tree, so the comparison ignores them instead of pinning one patch release.
    """
    if "Constant(value='')" not in dump:
        return dump
    empty = "Constant(value='')"
    out, i = [], 0
    while True:
        j = dump.find(empty, i)
        if j < 0:
            out.append(dump[i:])
            return "".join(out)
        k = j
        while k > i and dump[k - 1] == " ":
            k -= 1
        if k > i and dump[k - 1] == ",":
            out.append(dump[i:k - 1])
            i = j + len(empty)
        elif dump[j + len(empty):].lstrip().startswith(","):
            out.append(dump[i:j])
            rest = dump[j + len(empty):]
            trimmed = rest.lstrip()
            i = j + len(empty) + (len(rest) - len(trimmed)) + 1
        else:
            out.append(dump[i:j])
            i = j + len(empty)


def stage1_one(text):
    return _strip_empty_constants(ailast.dump(ailparse.parse_expr(text)))


def ref_one(text):
    if text in REF_PINS:
        return _strip_empty_constants(REF_PINS[text])
    dump = ast.dump(ast.parse(text, mode="eval").body, include_attributes=False)
    return _strip_empty_constants(dump)


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


def corpus_segments(want):
    """`want` fixed S376 segments; widen past the 30-file stride if a corpus edit made it short."""
    texts = parseable_segments(fixed_files(), want)
    if len(texts) < want:
        paths = expr_ref.read_paths(str(REPO / "selfhost" / "CORPUS.txt"))
        texts = parseable_segments([str(REPO / p) for p in paths if (REPO / p).exists()], want)
    return texts


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
        texts = corpus_segments(200)
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

    def test_invalid_syntax_refused(self):
        for text in REFUSED:
            with self.subTest(text=text):
                with self.assertRaises(ailparse.ParseError) as cm:
                    ailparse.parse_expr(text)
                self.assertTrue(str(cm.exception).startswith("ailparse:"))

    def test_s376_30_modules_stage1(self):
        files = fixed_files()
        self.assertEqual(len(files), 30)
        for path in files:
            with self.subTest(path=path):
                self.assertEqual(module_dump_ail(path), module_dump_ref(path))

    def test_error_snippets_agree_with_ast(self):
        for text in SNIPPETS:
            with self.subTest(text=text[:60]):
                py_err = False
                try:
                    ast.parse(text)
                except SyntaxError:
                    py_err = True
                ail_err = False
                try:
                    ailparse.parse(text)
                except SyntaxError:
                    ail_err = True
                self.assertEqual(ail_err, py_err)

    def test_review_boundaries_stage1(self):
        for text in BOUNDARY_VALID:
            with self.subTest(text=text[:60]):
                self.assertEqual(ailast.dump(ailparse.parse(text)),
                                 ast.dump(ast.parse(text), include_attributes=False))
        for text in BOUNDARY_INVALID:
            with self.subTest(text=text[:60]):
                with self.assertRaises(SyntaxError):
                    ast.parse(text)
                with self.assertRaises(SyntaxError):
                    ailparse.parse(text)
        for text in BOUNDARY_REFUSED:
            with self.subTest(text=text[:60]):
                ast.parse(text)
                with self.assertRaises(SyntaxError) as cm:
                    ailparse.parse(text)
                self.assertIn("not supported", str(cm.exception))

    @unittest.skipUnless(HAVE_CC, "no C compiler")
    def test_stage2_matches_stage1(self):
        texts = corpus_segments(20)
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

    @unittest.skipUnless(HAVE_CC, "no C compiler")
    def test_stage2_modules_match_stage1(self):
        files = fixed_files()
        self.assertEqual(len(files), 30)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            exe = tmp / "parse_drv"
            env = dict(os.environ, AIL_PATH=str(SRC), AIL_NO_CACHE="1")
            build = run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                         "selfhost/drv/parse_drv.py", "-o", str(exe)], env)
            self.assertEqual(build.returncode, 0, build.stderr[-800:])
            lst = tmp / "files.txt"
            with open(lst, "w", encoding="utf-8") as f:
                f.write("\n".join(files) + "\n")
            s1 = run([sys.executable, "-B", "selfhost/drv/parse_drv.py", str(lst)],
                     dict(os.environ, PYTHONPATH=str(SRC)))
            self.assertEqual(s1.returncode, 0, s1.stderr[-500:])
            s2 = run([str(exe), str(lst)])
            self.assertEqual(s2.returncode, 0, s2.stderr[-500:])
            self.assertEqual(s2.stdout, s1.stdout)
            self.assertEqual(s1.stdout.count(b"\n== ") + 1, 30)


if __name__ == "__main__":
    unittest.main()
