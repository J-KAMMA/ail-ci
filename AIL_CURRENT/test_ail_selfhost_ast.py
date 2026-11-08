"""shast1: selfhost/src/ailast.py dumps like CPython's ast, at stage 1 and stage 2.

Stage 1 is CPython: ``ast.parse`` -> ``selfhost/ref/from_cpython.convert`` -> ``ailast.dump``, which
must equal ``ast.dump`` on 30 fixed S376 files with and without attributes (and with
``annotate_fields=False`` and ``indent``).  Stage 2 is the AIL build of
``selfhost/drv/ast_selftest.py`` (40 fixed trees built by hand), which must print what stage 1 prints.
The self-test is skipped without a C compiler.
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
import from_cpython  # noqa: E402

HAVE_CC = shutil.which(os.environ.get("PIPE_CC") or "gcc") is not None
BIG = 99999999999999999999


def fixed_files():
    lines = (REPO / "selfhost" / "CORPUS.txt").read_text(encoding="utf-8").splitlines()
    paths = [line.split("  ", 1)[1] for line in lines if line.strip()]
    return [p for p in paths[::12][:30] if (REPO / p).exists()]


def converted(path):
    tree = ast.parse((REPO / path).read_bytes(), filename=path)
    return tree, from_cpython.convert(tree)


class AstTest(unittest.TestCase):
    def test_s376_stage1_both_attribute_settings(self):
        files = fixed_files()
        self.assertGreaterEqual(len(files), 28)
        for path in files:
            with self.subTest(path=path):
                tree, nodes = converted(path)
                for include in (False, True):
                    self.assertEqual(ailast.dump(nodes, include_attributes=include),
                                     ast.dump(tree, include_attributes=include))

    def test_dump_arguments(self):
        for path in fixed_files()[:8]:
            with self.subTest(path=path):
                tree, nodes = converted(path)
                self.assertEqual(ailast.dump(nodes, False), ast.dump(tree, annotate_fields=False))
                self.assertEqual(ailast.dump(nodes, True, False, 2), ast.dump(tree, indent=2))
                self.assertEqual(ailast.dump(nodes, True, True, "\t"), ast.dump(tree, include_attributes=True, indent="\t"))

    def test_walk_and_child_order(self):
        for path in fixed_files():
            with self.subTest(path=path):
                tree, nodes = converted(path)
                self.assertEqual([n._typename for n in ailast.walk(nodes)],
                                 [type(n).__name__ for n in ast.walk(tree)])
                self.assertEqual([n._typename for n in ailast.iter_child_nodes(nodes)],
                                 [type(n).__name__ for n in ast.iter_child_nodes(tree)])
                for got, want in zip(ailast.walk(nodes), ast.walk(tree)):
                    self.assertEqual([name for name, _ in ailast.iter_fields(got)],
                                     [name for name, _ in ast.iter_fields(want)])

    def test_big_int_and_ellipsis_stage1(self):
        for source in ("x = %d\n" % BIG, "x = ...\n", "x = 0.1 + 1e16 + 1e-7 + float('inf')\n"):
            with self.subTest(source=source):
                tree = ast.parse(source)
                nodes = from_cpython.convert(tree)
                self.assertEqual(ailast.dump(nodes), ast.dump(tree))
                self.assertEqual(ailast.dump(nodes, include_attributes=True),
                                 ast.dump(tree, include_attributes=True))

    def test_big_int_is_refused_by_name_in_the_default_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "big.py"
            src.write_text("x = %d\nprint(x)\n" % BIG, encoding="utf-8")
            build = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                                    str(src), "-o", str(Path(tmp) / "big")], cwd=REPO,
                                   capture_output=True, timeout=300)
            self.assertNotEqual(build.returncode, 0)
            self.assertIn(b"int64 constant expression out of range: %d" % BIG, build.stderr)

    @unittest.skipUnless(HAVE_CC, "no C compiler")
    def test_selftest_stage2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            exe = tmp / "ast_selftest"
            env = dict(os.environ, AIL_PATH=str(SRC), AIL_NO_CACHE="1")
            build = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                                    "selfhost/drv/ast_selftest.py", "-o", str(exe)], cwd=REPO,
                                   capture_output=True, env=env, timeout=900)
            self.assertEqual(build.returncode, 0, build.stderr[-800:])
            self.assertIn(b"built on the general path", build.stderr)
            stage1 = subprocess.run([sys.executable, "-B", "selfhost/drv/ast_selftest.py"], cwd=REPO,
                                    capture_output=True, env=dict(os.environ, PYTHONPATH=str(SRC)), timeout=300)
            self.assertEqual(stage1.returncode, 0, stage1.stderr[-500:])
            stage2 = subprocess.run([str(exe)], cwd=REPO, capture_output=True, timeout=300)
            self.assertEqual(stage2.returncode, 0, stage2.stderr[-500:])
            self.assertEqual(stage2.stdout, stage1.stdout)
            self.assertEqual(stage1.stdout.count(b"\n== ") + 1, 40)

    @unittest.skipUnless(HAVE_CC, "no C compiler")
    def test_big_int_exact_stage2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "big.py"
            src.write_text("x = %d\nprint(x)\n" % BIG, encoding="utf-8")
            build = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                                    str(src), "-o", str(tmp / "big"), "--exact-int"], cwd=REPO,
                                   capture_output=True, timeout=600)
            self.assertEqual(build.returncode, 0, build.stderr[-800:])
            run = subprocess.run([str(tmp / "big")], capture_output=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr[-300:])
            self.assertEqual(run.stdout, ("%d\n" % BIG).encode())


if __name__ == "__main__":
    unittest.main()
