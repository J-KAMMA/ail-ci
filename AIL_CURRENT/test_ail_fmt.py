"""`ail fmt --check` (packaging/ail_lang/fmt.py): a formatter is found, never added as a dependency.

`python3 -m ail_lang.fmt --check FILE...` answers "already formatted" (exit 0) or "would change"
(exit 1, unified diff on stdout) by running `ruff format` when ruff is on PATH, else `black`; with
neither it exits 2 and says how to install ruff.  The tests check that answer against the formatter
itself, that `--check` never writes a file, that `[fmt] line-length` in ail.toml is passed through,
and that formatting three programs (`--debug-dir`, release build) leaves `program.c` unchanged once
source line numbers are removed.

The formatter tests skip when neither ruff nor black is on PATH (neither is a dependency); the
missing-formatter test always runs and needs no formatter.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
PACKAGING = REPO / "packaging"
FMT_MODULE = PACKAGING / "ail_lang" / "fmt.py"
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
FORMATTER = shutil.which("ruff") or shutil.which("black")
FORMATTER_NAME = "ruff" if shutil.which("ruff") else ("black" if shutil.which("black") else None)
BLACK = shutil.which("black")

HAS_PACKAGING = FMT_MODULE.is_file()
NEEDS_FORMATTER = unittest.skipUnless(HAS_PACKAGING and FORMATTER,
                                      "packaging/ail_lang/fmt.py or a formatter (ruff/black) is absent")
NEEDS_BLACK = unittest.skipUnless(HAS_PACKAGING and BLACK, "black is absent")
NEEDS_COMPILER = unittest.skipUnless(CC, "no C compiler")

LINE_DIRECTIVE = re.compile(r"^[ \t]*#line[ \t]+\d+.*$", re.M)
DBG_SITE = re.compile(r'AIL_DBG_SITE\("([^"\n]*):\d+"\)')

UNFORMATTED = 'def main() -> int:\n    xs = [1, 2, 3]\n    print( "sum", sum( xs ) )\n    return 0\n\n\nmain()\n'
FORMATTED = 'def main() -> int:\n    xs = [1, 2, 3]\n    print("sum", sum(xs))\n    return 0\n\n\nmain()\n'

PROGRAMS = {
    "loop": '''def main() -> int:
    total = 0
    for i in range(4):
        total += i * i
    print( total )
    return 0


main()
''',
    "dict": '''def count(words: list[str]) -> dict[str, int]:
    seen = {}
    for w in words:
        seen[w] = seen.get(w, 0) + 1
    return seen


def main() -> int:
    for key in sorted( count( "a b a".split() ) ):
        print( key, count( "a b a".split() )[key] )
    return 0


main()
''',
    "script": '''class Box:

    def __init__(self, value: int):
        self.value = value

    def scaled(self, k: int) -> int:
        return self.value * k


def main() -> int:
    boxes = [ Box( 2 ), Box( 3 ) ]
    print( sum( b.scaled( 4 ) for b in boxes ) )
    return 0


main()
''',
}


def environment(path=None):
    env = dict(os.environ, PYTHONPATH=str(PACKAGING), PYTHONUTF8="1")
    for name in ("AIL_CACHE", "AIL_NO_CACHE", "AIL_IR", "AIL_DEBUG"):
        env.pop(name, None)
    if path is not None:
        env["PATH"] = path
    return env


def normalize_c(text, directory):
    text = LINE_DIRECTIVE.sub("", text)
    text = DBG_SITE.sub(lambda found: 'AIL_DBG_SITE("%s")' % found.group(1), text)
    return text.replace(str(directory), "<dir>")


def check(files, path=None, cwd=PACKAGING):
    return subprocess.run([sys.executable, "-m", "ail_lang.fmt", "--check", *map(str, files)],
                           cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                           env=environment(path), timeout=300)


class MissingFormatter(unittest.TestCase):
    @unittest.skipUnless(HAS_PACKAGING, "packaging/ is absent")
    def test_exit_2_and_install_hint(self):
        with tempfile.TemporaryDirectory(prefix="ail-fmt-missing-") as tmp:
            source = Path(tmp) / "prog.py"
            source.write_text(FORMATTED, encoding="utf-8")
            empty = Path(tmp) / "empty-path"
            empty.mkdir()
            done = check([source], path=str(empty))
            self.assertEqual(source.read_text(encoding="utf-8"), FORMATTED)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("ail fmt needs ruff or black on PATH: pip install ruff", done.stderr)


@NEEDS_FORMATTER
class CheckMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fmt-check-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_formatted_file_exits_0(self):
        source = self.dir / "prog.py"
        source.write_text(FORMATTED, encoding="utf-8")
        done = check([source])
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(source.read_text(encoding="utf-8"), FORMATTED)

    def test_unformatted_file_exits_1_with_diff_and_is_not_written(self):
        source = self.dir / "prog.py"
        source.write_text(UNFORMATTED, encoding="utf-8")
        done = check([source])
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("---", done.stdout)
        self.assertIn("+++", done.stdout)
        self.assertIn('print("sum", sum(xs))', done.stdout)
        self.assertEqual(source.read_text(encoding="utf-8"), UNFORMATTED)

    def test_one_unformatted_file_among_many_exits_1(self):
        good = self.dir / "good.py"
        bad = self.dir / "bad.py"
        good.write_text(FORMATTED, encoding="utf-8")
        bad.write_text(UNFORMATTED, encoding="utf-8")
        done = check([good, bad])
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("bad.py", done.stdout)
        self.assertNotIn("good.py", done.stdout)

    def test_line_length_comes_from_ail_toml(self):
        source = self.dir / "prog.py"
        source.write_text("def main() -> int:\n"
                          "    value = sum([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])\n"
                          "    print(value)\n"
                          "    return 0\n"
                          "\n"
                          "\n"
                          "main()\n", encoding="utf-8")
        self.assertEqual(check([source]).returncode, 0)
        (self.dir / "ail.toml").write_text('[fmt]\nline-length = 40\n', encoding="utf-8")
        done = check([source])
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("value = sum(", done.stdout)

    def test_line_length_from_ail_toml_above_a_relative_argument(self):
        sub = self.dir / "sub" / "deep"
        sub.mkdir(parents=True)
        source = sub / "prog.py"
        source.write_text("def main() -> int:\n"
                          "    value = sum([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])\n"
                          "    print(value)\n"
                          "    return 0\n"
                          "\n"
                          "\n"
                          "main()\n", encoding="utf-8")
        (self.dir / "ail.toml").write_text('[fmt]\nline-length = 40\n', encoding="utf-8")
        done = check(["prog.py"], cwd=sub)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("value = sum(", done.stdout)
        done = check(["deep/prog.py"], cwd=self.dir / "sub")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)

    def test_check_answers_match_the_formatter(self):
        good = self.dir / "good.py"
        bad = self.dir / "bad.py"
        good.write_text(FORMATTED, encoding="utf-8")
        bad.write_text(UNFORMATTED, encoding="utf-8")
        ours = check([good, bad])
        tool = [FORMATTER, "format"] if FORMATTER_NAME == "ruff" else [FORMATTER]
        theirs = subprocess.run(tool + ["--check", str(good), str(bad)],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(theirs.returncode, 1, theirs.stderr)
        self.assertEqual(ours.returncode, 1, ours.stdout + ours.stderr)


@NEEDS_BLACK
class BlackFallback(unittest.TestCase):
    """With only black on PATH (no ruff), `--check` still answers 0/1 and prints the diff.

    `black` rejects `--color=false`; this pins the `--no-color` spelling so a regression cannot
    hide behind the ruff path that CI normally exercises.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fmt-black-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        (self.bin / "black").symlink_to(BLACK)
        (self.bin / os.path.basename(sys.executable)).symlink_to(sys.executable)
        self.path = str(self.bin)

    def test_formatted_file_exits_0(self):
        source = self.dir / "good.py"
        source.write_text(FORMATTED, encoding="utf-8")
        done = check([source], path=self.path)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("does not take a value", done.stderr)

    def test_unformatted_file_exits_1_with_diff_and_is_not_written(self):
        source = self.dir / "bad.py"
        source.write_text(UNFORMATTED, encoding="utf-8")
        done = check([source], path=self.path)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("---", done.stdout)
        self.assertIn("+++", done.stdout)
        self.assertIn('print("sum", sum(xs))', done.stdout)
        self.assertEqual(source.read_text(encoding="utf-8"), UNFORMATTED)


@NEEDS_FORMATTER
@NEEDS_COMPILER
class BuildEquality(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fmt-build-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def format_copy(self, path):
        tool = [FORMATTER, "format"] if FORMATTER_NAME == "ruff" else [FORMATTER]
        done = subprocess.run(tool + [str(path)], capture_output=True, text=True, encoding="utf-8",
                              env=environment(), timeout=300)
        self.assertIn(done.returncode, (0, 1), done.stdout + done.stderr)

    def build(self, directory):
        done = subprocess.run([sys.executable, "-B", CLI, "compile", "prog.py", "-o", "prog",
                               "--debug-dir", "debug"],
                              cwd=str(directory), capture_output=True, text=True, encoding="utf-8",
                              env=environment(), timeout=900)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return (directory / "debug" / "program.c").read_text(encoding="utf-8", errors="replace")

    def run_program(self, directory):
        done = subprocess.run([str(directory / "prog")], cwd=str(directory), capture_output=True,
                              timeout=120, env=environment())
        return done.returncode, done.stdout

    def test_three_programs_keep_their_c_and_output(self):
        for label, text in PROGRAMS.items():
            with self.subTest(program=label):
                original = self.dir / label / "orig"
                changed = self.dir / label / "fmt"
                original.mkdir(parents=True)
                changed.mkdir(parents=True)
                (original / "prog.py").write_text(text, encoding="utf-8")
                (changed / "prog.py").write_text(text, encoding="utf-8")
                self.format_copy(changed / "prog.py")
                self.assertNotEqual((changed / "prog.py").read_text(encoding="utf-8"), text,
                                    "the sample should exercise a formatter")
                c_original = self.build(original)
                c_changed = self.build(changed)
                self.assertEqual(normalize_c(c_original, original), normalize_c(c_changed, changed), label)
                self.assertEqual(self.run_program(original), self.run_program(changed), label)


if __name__ == "__main__":
    unittest.main()
