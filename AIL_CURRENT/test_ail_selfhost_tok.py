"""shtok1: selfhost/src/ailtok.py gives the tokens of CPython's tokenize, at stage 1 and stage 2.

Stage 0 is selfhost/ref/tok_ref.py (CPython's ``tokenize``), stage 1 is selfhost/drv/tok_drv.py
under CPython, stage 2 is the AIL build of the same driver.  Stage 1 must equal stage 0 on 30
fixed S376 files and on the edge-case snippets below; stage 2 must equal stage 1 on 5 of the files
and on the snippets (skipped without a C compiler).
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import token
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SRC = REPO / "selfhost" / "src"
sys.path.insert(0, str(SRC))
import ailtok  # noqa: E402

HAVE_CC = shutil.which(os.environ.get("PIPE_CC") or "gcc") is not None

EDGE = {
    "fstrings": "a = f'a{{b}}c{x!r:>{w}} d'\nb = f'{x:{y}.{z}f}' f\"{'q'}\" f'{x=}' f'{ x = }'\n"
                "c = f\"{d[\"k\"]}\" + f'{a!=b}' + f'{x:=5}' + f'{lambda: 1}'\n"
                "d = f'{f\"{y}\"}' f'''a\n{x}\nb''' f'{x:%H:%M}' f'\\N{DASH}{y}' rf'\\{a}\\d'\n"
                "e = f'{x:}' f'{x!s}' f'{{}}' f'}}{{' f'{{{x}}}' F'{x}' Rf'{x}' fR'''{\na\n}'''\n",
    "prefixes": "s = rb'\\x' + Rb'''t\nu''' + u'k' + B\"x\" + bR'y' + BR'z' + r'\\'' + \"\"\"q\"\"\"\n"
                "t = 'a\\\nb' + '''\\''''\n",
    "continuation": "x = (1,\n  2)\\\n  + 3\ny = [\n\n  # c\n  4,\n]\nz = 1 \\\n\n",
    "indent": "if a:\n\tif b:\n\t\tc\n\td\n# x\nif e:\n        f\n        # g\n  \n\x0c\nh\n",
    "crlf": "x = 1\r\nif x:\r\n    y = '''a\r\nb''' # c\r\n\r\nz = 2\r\n",
    "non_ascii": "\u00e9t\u00e9 = '\u65e5\u672c'\n\u5909\u6570 = 1  # \u30b3\u30e1\u30f3\u30c8\nclass \u00c7a: pass\n",
    "numbers": "x = 0x_1F + 1_000j + 1e-5 + 1.5E+3J + .5 + 5. + 0o17 + 0b1 + 0_0 + 1_0.0_1e1_0 + 1if y else 2\n",
    "operators": "(y := 3)\ndef f(a, /, *b, **c) -> int: ...\nx **= 2; x //= 3; x >>= 1; x <<= 1; x @= m; x != y; x->y if 0 else x\n",
    "eof_comment": "def f():\n    return 1\n# trailing",
    "no_final_newline": "if a:\n    x = 1",
    "ws_last_line": "x\n   ",
    "empty": "",
    "blank": "\n",
}


def ref_dump(text):
    return ["%s %d,%d %d,%d %r" % (token.tok_name[t.exact_type], t.start[0], t.start[1], t.end[0], t.end[1],
                                   t.string) for t in tokenize.generate_tokens(io.StringIO(text).readline)]


def cand_dump(text):
    return [ailtok.dump_line(t) for t in ailtok.tokenize(text)]


def fixed_files():
    lines = (REPO / "selfhost" / "CORPUS.txt").read_text(encoding="utf-8").splitlines()
    paths = [line.split("  ", 1)[1] for line in lines if line.strip()]
    pick = paths[::12][:29]
    crlf = "AIL_CURRENT/python/pkg-v12/test_all.py"
    if crlf in paths and crlf not in pick:
        pick.append(crlf)
    return [p for p in pick if (REPO / p).exists()]


def run(cmd, list_path, env=None):
    return subprocess.run(cmd + [str(list_path)], cwd=REPO, capture_output=True, env=env, timeout=600)


class TokTest(unittest.TestCase):
    def test_edge_cases_stage1(self):
        for name, text in EDGE.items():
            with self.subTest(name=name):
                self.assertEqual(cand_dump(text), ref_dump(text))

    def test_fixed_files_stage1(self):
        files = fixed_files()
        self.assertGreaterEqual(len(files), 28)
        with tempfile.TemporaryDirectory() as tmp:
            lst = Path(tmp) / "files.list"
            lst.write_text("\n".join(files) + "\n", encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(SRC))
            a = run([sys.executable, "selfhost/ref/tok_ref.py"], lst)
            b = run([sys.executable, "selfhost/drv/tok_drv.py"], lst, env)
            self.assertEqual(a.returncode, 0, a.stderr[-500:])
            self.assertEqual(b.returncode, 0, b.stderr[-500:])
            self.assertEqual(a.stdout.count(b"\n== ") + 1, len(files))
            self.assertEqual(b.stdout, a.stdout)

    def test_lone_carriage_return_is_refused(self):
        with self.assertRaises(ailtok.TokError):
            ailtok.tokenize("x = 1\ry = 2\n")

    @unittest.skipUnless(HAVE_CC, "no C compiler")
    def test_stage2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            exe = tmp / "tok_drv"
            env = dict(os.environ, AIL_PATH=str(SRC))
            build = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                                    "selfhost/drv/tok_drv.py", "-o", str(exe)], cwd=REPO,
                                   capture_output=True, env=env, timeout=900)
            self.assertEqual(build.returncode, 0, build.stderr[-800:])
            files = fixed_files()[:5]
            for name, text in EDGE.items():
                p = tmp / ("edge_%s.py" % name)
                with open(p, "w", encoding="utf-8", newline="") as f:
                    f.write(text)
                files.append(str(p))
            lst = tmp / "files.list"
            lst.write_text("\n".join(files) + "\n", encoding="utf-8")
            s1 = run([sys.executable, "selfhost/drv/tok_drv.py"], lst, dict(os.environ, PYTHONPATH=str(SRC)))
            s2 = run([str(exe)], lst)
            self.assertEqual(s1.returncode, 0, s1.stderr[-500:])
            self.assertEqual(s2.returncode, 0, s2.stderr[-500:])
            self.assertEqual(s2.stdout, s1.stdout)


if __name__ == "__main__":
    unittest.main()
