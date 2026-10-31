"""docs/tutorial.md cannot rot: every code sample in it is built by the compiler and run, and printed output is checked.

The tutorial marks a sample with an HTML comment right before its ```python block:

    <!-- sample: NAME [general] [refuse] [gpu] [args=A,B] -->

and attaches what it shows to the sample with the blocks that follow it:

    ```output    exactly what CPython prints (stdout); the AIL executable must print the same bytes
    ```note      lines that appear in the compiler's messages for a normal build (the "built on the general path" note)
    ```strict    lines that appear in the messages of the same build with --strict
    ```refusal   lines that appear in the messages of a build the compiler refuses

Rules checked for each sample (the mode is in the comment):
* default (typed path): builds with --strict, no "general path" note, stdout and exit code equal CPython's;
* general: builds without --strict and says so in a note, refuses with --strict (exit 3), output equals CPython's;
* refuse: the compiler exits 3 and builds nothing;
* gpu: built with --gpu (a CPU replay where no Vulkan device exists), output equals CPython's.

Two ways to run it:
* from a checkout (default): uses ail_chatgpt.py beside this file; skipped when docs/tutorial.md is not there (SDK export);
* against an installed wheel: AIL_TUTORIAL_AIL=/path/to/venv/bin/ail uses `ail build`, and the CPython oracle imports
  ail_ffi / ail_array from the installed SDK (the CI job `wheel` does this).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TUTORIAL = ROOT.parent / "docs" / "tutorial.md"
INSTALLED = os.environ.get("AIL_TUTORIAL_AIL")
BLOCKS = re.compile(r"<!--\s*sample:\s*(\S+)([^>]*?)-->|^```(\S*)\n(.*?)^```$", re.S | re.M)
GENERAL = "built on the general path"


def parse(text):
    """[{name, flags, args, code, output, note, strict, refusal}] in document order."""
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
                       "output": None, "note": None, "strict": None, "refusal": None}
            samples.append(current)
            continue
        kind, body = found.group(3), found.group(4)
        if current is None:
            continue
        if kind == "python" and current["code"] is None:
            current["code"] = body
        elif kind in ("output", "note", "strict", "refusal") and current["code"] is not None:
            current[kind] = body
    return samples


def source_root():
    if INSTALLED:
        done = subprocess.run([INSTALLED, "doctor"], capture_output=True, text=True, timeout=120)
        return Path(json.loads(done.stdout)["source_root"])
    return ROOT


def tutorial_samples():
    return parse(TUTORIAL.read_text(encoding="utf-8")) if TUTORIAL.is_file() else []


def setUpModule():
    if not TUTORIAL.is_file():
        raise unittest.SkipTest("docs/tutorial.md is not beside AIL_CURRENT (an SDK export)")
    if not (INSTALLED or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang") or os.environ.get("PIPE_CC")):
        raise unittest.SkipTest("no C compiler")


class Tutorial(unittest.TestCase):
    maxDiff = None

    def compile(self, work, name, extra, out):
        if INSTALLED:
            cmd = [INSTALLED, "build"] + extra + [name + ".py", "-o", out]
        else:
            cmd = [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile"] + extra + [name + ".py", "-o", out]
        return subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=300)

    def check_lines(self, block, text, what):
        for line in (block or "").splitlines():
            if line.strip():
                self.assertIn(line.strip(), text, "%s: the tutorial shows a line the compiler did not print" % what)

    def run_sample(self, sample):
        name, flags = sample["name"], sample["flags"]
        env = dict(os.environ, PYTHONPATH=str(source_root()), PYTHONDONTWRITEBYTECODE="1")
        for var in ("AIL_STRICT", "AIL_UNIFIED_FORCE", "AIL_NO_GENERAL"):
            env.pop(var, None)
        with tempfile.TemporaryDirectory(prefix="ail-tutorial-") as work:
            Path(work, name + ".py").write_text(sample["code"], encoding="utf-8")
            extra = ["--gpu"] if "gpu" in flags else []
            oracle = subprocess.run([sys.executable, name + ".py"] + sample["args"], cwd=work, env=env,
                                    capture_output=True, text=True, timeout=300)
            if sample["output"] is not None:
                self.assertEqual(oracle.stdout, sample["output"], name + ": the tutorial's output is not what CPython prints")
            if "refuse" in flags:
                done = self.compile(work, name, extra, name + ".bin")
                self.assertEqual(done.returncode, 3, name + ": " + done.stderr)
                self.assertFalse(Path(work, name + ".bin").exists())
                self.check_lines(sample["refusal"], done.stdout + done.stderr, name)
                return
            if "general" in flags:
                done = self.compile(work, name, extra, name + ".bin")
                self.assertEqual(done.returncode, 0, name + ": " + done.stderr)
                self.assertIn(GENERAL, done.stderr, name)
                self.check_lines(sample["note"], done.stderr, name)
                strict = self.compile(work, name, extra + ["--strict"], name + ".strict")
                self.assertEqual(strict.returncode, 3, name + ": --strict must refuse\n" + strict.stderr)
                self.assertFalse(Path(work, name + ".strict").exists())
                self.check_lines(sample["strict"], strict.stdout + strict.stderr, name)
            else:
                done = self.compile(work, name, extra + ["--strict"], name + ".bin")
                self.assertEqual(done.returncode, 0, name + ": a typed sample must build with --strict\n" + done.stderr)
                self.assertNotIn(GENERAL, done.stderr, name)
            ran = subprocess.run(["./" + name + ".bin"] + sample["args"], cwd=work, capture_output=True, text=True, timeout=300)
            self.assertEqual(ran.stdout, oracle.stdout, name + ": AIL stdout differs from CPython")
            self.assertEqual(ran.returncode, oracle.returncode, name)


def add(sample):
    def test(self):
        self.run_sample(sample)
    return test


for _sample in tutorial_samples():
    setattr(Tutorial, "test_sample_" + re.sub(r"\W", "_", _sample["name"]), add(_sample))


class Structure(unittest.TestCase):
    def test_every_sample_has_code_and_the_tutorial_has_enough_of_them(self):
        samples = tutorial_samples()
        self.assertGreaterEqual(len(samples), 8)
        names = [s["name"] for s in samples]
        self.assertEqual(len(names), len(set(names)), "duplicate sample names")
        for sample in samples:
            self.assertIsNotNone(sample["code"], sample["name"] + ": marker without a python block")

    def test_the_tutorial_covers_the_promised_topics(self):
        text = TUTORIAL.read_text(encoding="utf-8")
        for word in ("--strict", "general path", "ail_ffi", "# ail: gpu", "upcoming"):
            self.assertTrue(word.lower() in text.lower(), "the tutorial no longer mentions " + word)


if __name__ == "__main__":
    unittest.main()
