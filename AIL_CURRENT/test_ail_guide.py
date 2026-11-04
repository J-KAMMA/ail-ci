"""docs/guide cannot rot: every code sample in it is built by the compiler and run, and printed
output is checked against CPython 3.12.

The guide uses the tutorial's sample format (`docs/tutorial.md`,
`AIL_CURRENT/test_ail_tutorial.py`):

    <!-- sample: NAME [general] [refuse] [static] [exact] [stop] [args=A,B] -->

followed by a ```python block and the optional blocks that follow it:

    ```output    exactly what CPython prints (stdout); the AIL executable must print the same bytes
    ```stdin     text fed to the program on stdin by this test (both CPython and the AIL executable)
    ```note      lines that appear in the compiler's messages for a normal build
    ```strict    lines that appear in the messages of the same build with --strict
    ```refusal   lines that appear in the messages of a build the compiler refuses
    ```stdout    what the AIL executable prints for a stop sample
    ```stderr    lines that appear in the AIL executable's stderr for a stop sample

Rules checked for each sample (the mode is in the comment):
* default (typed path): builds with --strict, no "general path" note, stdout and exit code equal CPython's;
* general: builds without --strict and says so in a note, refuses with --strict (exit 3), output equals CPython's;
* refuse: the compiler exits 3 and builds nothing;
* static: the compiler exits 2 and builds nothing (a static big-int refusal);
* exact: builds with --exact-int, stdout and exit code equal CPython's;
* stop: builds with --strict, runs, prints the ```stdout block, exits 1, and its stderr contains the
  ```stderr lines; where CPython also fails, the AIL executable must fail too.

Paths in compiler and runtime messages are not compared: the test removes its temporary directory
prefix before it checks a shown line.
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
GUIDE = ROOT.parent / "docs" / "guide"
CHAPTERS = (
    "01-typed-and-general.md",
    "02-text-bytes-files.md",
    "03-errors-and-exit.md",
    "04-modules-and-c.md",
)
BLOCKS = re.compile(r"<!--\s*sample:\s*(\S+)([^>]*?)-->|^```(\S*)\n(.*?)^```$", re.S | re.M)
GENERAL = "built on the general path"
KINDS = ("output", "stdin", "note", "strict", "refusal", "stdout", "stderr")


def artifact(work, name):
    """The absolute file `compile ... -o name.bin` wrote (Windows may append .exe)."""
    path = Path(work) / (name + ".bin")
    if os.name == "nt" and not path.is_file() and Path(str(path) + ".exe").is_file():
        path = Path(str(path) + ".exe")
    return path


def parse(text):
    """[{name, flags, args, code, output, stdin, note, strict, refusal, stdout, stderr}] in order."""
    samples = []
    current = None
    for found in BLOCKS.finditer(text):
        if found.group(1) is not None:
            flags = found.group(2).split()
            args = []
            for flag in list(flags):
                if flag.startswith("args="):
                    args = flag[5:].split(",")
                    flags.remove(flag)
            current = {"name": found.group(1), "flags": set(flags), "args": args, "code": None,
                       "output": None, "stdin": None, "note": None, "strict": None, "refusal": None,
                       "stdout": None, "stderr": None}
            samples.append(current)
            continue
        kind, body = found.group(3), found.group(4)
        if current is None:
            continue
        if kind == "python" and current["code"] is None:
            current["code"] = body
        elif kind in KINDS and current["code"] is not None:
            current[kind] = body
    return samples


def guide_files():
    return sorted(GUIDE.glob("*.md")) if GUIDE.is_dir() else []


def guide_samples():
    samples = []
    for path in guide_files():
        samples.extend(parse(path.read_text(encoding="utf-8")))
    return samples


def chapter_samples(filename):
    path = GUIDE / filename
    return parse(path.read_text(encoding="utf-8")) if path.is_file() else []


def setUpModule():
    if not GUIDE.is_dir():
        raise unittest.SkipTest("docs/guide is not beside AIL_CURRENT (an SDK export)")
    if not (shutil.which("cc") or shutil.which("gcc") or shutil.which("clang") or os.environ.get("PIPE_CC")):
        raise unittest.SkipTest("no C compiler")


class Guide(unittest.TestCase):
    maxDiff = None

    def compile(self, work, name, extra, out):
        cmd = [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile"] + extra + [name + ".py", "-o", out]
        return subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=300)

    def invoke(self, cmd, work, stdin, env):
        options = dict(cwd=work, env=env, capture_output=True, text=True, timeout=300)
        if stdin is None:
            options["stdin"] = subprocess.DEVNULL
        else:
            options["input"] = stdin
        return subprocess.run(cmd, **options)

    def check_lines(self, block, text, what, work):
        text = text.replace(str(work) + os.sep, "")
        for line in (block or "").splitlines():
            if line.strip():
                self.assertIn(line.strip(), text, "%s: the guide shows a line the compiler did not print" % what)

    def run_sample(self, sample):
        name, flags = sample["name"], sample["flags"]
        env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
        for var in ("AIL_STRICT", "AIL_UNIFIED_FORCE", "AIL_NO_GENERAL", "AIL_EXACT_INT"):
            env.pop(var, None)
        with tempfile.TemporaryDirectory(prefix="ail-guide-") as work:
            Path(work, name + ".py").write_text(sample["code"], encoding="utf-8")
            extra = ["--gpu"] if "gpu" in flags else []
            oracle = self.invoke([sys.executable, name + ".py"] + sample["args"], work, sample["stdin"], env)
            if sample["output"] is not None:
                self.assertEqual(oracle.stdout, sample["output"], name + ": the guide's output is not what CPython prints")
            if "static" in flags:
                done = self.compile(work, name, extra + ["--strict"], name + ".bin")
                self.assertEqual(done.returncode, 2, name + ": " + done.stderr)
                self.assertFalse(Path(work, name + ".bin").exists())
                self.check_lines(sample["refusal"], done.stdout + done.stderr, name, work)
                return
            if "refuse" in flags:
                done = self.compile(work, name, extra, name + ".bin")
                self.assertEqual(done.returncode, 3, name + ": " + done.stderr)
                self.assertFalse(Path(work, name + ".bin").exists())
                self.check_lines(sample["refusal"], done.stdout + done.stderr, name, work)
                return
            if "stop" in flags:
                done = self.compile(work, name, extra + ["--strict"], name + ".bin")
                self.assertEqual(done.returncode, 0, name + ": " + done.stderr)
                ran = self.invoke([str(artifact(work, name))] + sample["args"], work, sample["stdin"], env)
                self.assertEqual(ran.stdout, sample["stdout"], name + ": stop stdout")
                self.assertEqual(ran.returncode, 1, name + ": stop exit status")
                if oracle.returncode != 0:
                    self.assertNotEqual(ran.returncode, 0, name + ": CPython fails here too")
                self.check_lines(sample["stderr"], ran.stderr, name, work)
                return
            if "exact" in flags:
                done = self.compile(work, name, extra + ["--exact-int"], name + ".bin")
                self.assertEqual(done.returncode, 0, name + ": " + done.stderr)
                ran = self.invoke([str(artifact(work, name))] + sample["args"], work, sample["stdin"], env)
                self.assertEqual(ran.stdout, oracle.stdout, name + ": exact stdout differs from CPython")
                self.assertEqual(ran.returncode, oracle.returncode, name + ": exact exit status")
                return
            if "general" in flags:
                done = self.compile(work, name, extra, name + ".bin")
                self.assertEqual(done.returncode, 0, name + ": " + done.stderr)
                self.assertIn(GENERAL, done.stderr, name)
                self.check_lines(sample["note"], done.stderr, name, work)
                strict = self.compile(work, name, extra + ["--strict"], name + ".strict")
                self.assertEqual(strict.returncode, 3, name + ": --strict must refuse\n" + strict.stderr)
                self.assertFalse(Path(work, name + ".strict").exists())
                self.check_lines(sample["strict"], strict.stdout + strict.stderr, name, work)
            else:
                done = self.compile(work, name, extra + ["--strict"], name + ".bin")
                self.assertEqual(done.returncode, 0, name + ": a typed sample must build with --strict\n" + done.stderr)
                self.assertNotIn(GENERAL, done.stderr, name)
            ran = self.invoke([str(artifact(work, name))] + sample["args"], work, sample["stdin"], env)
            self.assertEqual(ran.stdout, oracle.stdout, name + ": AIL stdout differs from CPython")
            self.assertEqual(ran.returncode, oracle.returncode)


def add(sample):
    def test(self):
        self.run_sample(sample)
    return test


for _sample in guide_samples():
    setattr(Guide, "test_sample_" + re.sub(r"\W", "_", _sample["name"]), add(_sample))


class Structure(unittest.TestCase):
    def test_every_sample_has_code_and_the_guide_has_enough_of_them(self):
        samples = guide_samples()
        print("\nguide samples: %d" % len(samples))
        self.assertGreaterEqual(len(samples), 40)
        names = [s["name"] for s in samples]
        self.assertEqual(len(names), len(set(names)), "duplicate sample names")
        for sample in samples:
            self.assertIsNotNone(sample["code"], sample["name"] + ": marker without a python block")

    def test_each_chapter_has_ten_samples(self):
        for filename in CHAPTERS:
            self.assertGreaterEqual(len(chapter_samples(filename)), 10, filename)


if __name__ == "__main__":
    unittest.main()
