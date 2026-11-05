"""`docs/FFI_QUICK.md`: every numbered step's code is the file it names, and its command and output are real.

The page marks its blocks with `<!-- ffi-quick: ... -->` on the line before the fence:

    file PATH       the block must equal examples/PATH byte for byte (the C files and generated module)
    program PATH    the same, for the step's AIL program; the step's command builds and runs it
    command         a shell block, run with bash in a temporary copy of the checkout
    output          its stdout, compared byte for byte with the command's stdout

The command runs in a temporary directory holding a symlink to `AIL_CURRENT/` and a copy of
`examples/ffi_quick/`, so the `-o` targets and the generated shared library land there, not in the checkout.
Each program is also run under `python3` (the ctypes path) and must print the same output the page shows.

The module is skipped, with the missing piece named, when the runner has no C compiler or no `-lm`.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CLI = HERE / "ail_chatgpt.py"
PAGE = REPO / "docs" / "FFI_QUICK.md"
QUICK = REPO / "examples" / "ffi_quick"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

FENCE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,})(?P<lang>[^\s`]*)\s*$")
CLOSING = re.compile(r"^ {0,3}`{3,}\s*$")
MARKER = re.compile(r"^<!--\s*ffi-quick:\s*(?P<action>\S+)(?:\s+(?P<arg>.*?))?\s*-->$")
STEP = re.compile(r"^##\s+Step\s+(?P<number>\d+)\b")


def have_lib(name):
    if not CC:
        return False
    done = subprocess.run([CC, "-x", "c", "-", "-l" + name, "-o", os.devnull],
                          input="int main(void){return 0;}\n", capture_output=True, text=True)
    return done.returncode == 0


def missing_reason():
    if not CC:
        return "installed C compiler required"
    if not have_lib("m"):
        return "-lm is not installed"
    return None


class Block:
    def __init__(self, line, lang, body, action, argument):
        self.line, self.lang, self.body = line, lang, body
        self.action, self.argument = action, argument

    @property
    def where(self):
        return "docs/FFI_QUICK.md:%d" % self.line


class Step:
    def __init__(self, number):
        self.number = number
        self.files = []
        self.programs = []
        self.commands = []
        self.outputs = []


def parse():
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    steps, current = [], None
    index = 0
    while index < len(lines):
        found = STEP.match(lines[index])
        if found:
            current = Step(int(found.group("number")))
            steps.append(current)
            index += 1
            continue
        fence = FENCE.match(lines[index])
        if not fence:
            index += 1
            continue
        start = index + 1
        end = start
        while end < len(lines) and not CLOSING.match(lines[end]):
            end += 1
        if end >= len(lines):
            raise AssertionError("docs/FFI_QUICK.md:%d: fenced block is not closed" % start)
        marker = None
        if index > 0:
            marker = MARKER.match(lines[index - 1].strip())
        body = "\n".join(lines[start:end]) + ("\n" if end > start else "")
        if marker and current is not None:
            block = Block(start, fence.group("lang").lower(), body,
                          marker.group("action"), (marker.group("arg") or "").strip())
            if block.action == "file":
                current.files.append(block)
            elif block.action == "program":
                current.programs.append(block)
            elif block.action == "command":
                current.commands.append(block)
            elif block.action == "output":
                current.outputs.append(block)
        index = end + 1
    return steps


def workspace(directory):
    """The checkout a command sees: AIL_CURRENT symlinked, examples/ffi_quick copied (commands write there)."""
    work = Path(directory)
    (work / "examples").mkdir()
    shutil.copytree(QUICK, work / "examples" / "ffi_quick")
    os.symlink(HERE, work / "AIL_CURRENT", target_is_directory=True)
    return work


def environment():
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", AIL_NO_CACHE="1")
    env.pop("PYTHONPATH", None)
    return env


class FFIQuickDocs(unittest.TestCase):
    maxDiff = None

    def test_page_has_eight_steps_with_code_command_and_output(self):
        steps = parse()
        self.assertGreaterEqual(len(steps), 8, "docs/FFI_QUICK.md needs at least 8 numbered steps")
        self.assertEqual([step.number for step in steps], list(range(1, len(steps) + 1)),
                         "step numbers must run 1..N in order")
        for step in steps:
            with self.subTest(step=step.number):
                self.assertEqual(len(step.programs), 1, "step %d: one `program` block" % step.number)
                self.assertEqual(len(step.commands), 1, "step %d: one `command` block" % step.number)
                self.assertEqual(len(step.outputs), 1, "step %d: one `output` block" % step.number)

    def test_blocks_are_the_files_byte_for_byte(self):
        steps = parse()
        for step in steps:
            for block in step.files + step.programs:
                with self.subTest(step=step.number, block=block.where):
                    self.assertTrue(block.argument, "%s: marker needs a path" % block.where)
                    source = (REPO / block.argument).resolve()
                    self.assertTrue(source.is_file(), "%s: missing %s" % (block.where, block.argument))
                    self.assertEqual(block.body, source.read_text(encoding="utf-8"),
                                     "%s: block is not %s byte for byte" % (block.where, block.argument))

    def test_commands_build_and_print_the_documented_output(self):
        reason = missing_reason()
        if reason:
            self.skipTest(reason)
        steps = parse()
        for step in steps:
            with self.subTest(step=step.number):
                self.run_step(step)

    def run_step(self, step):
        program = step.programs[0]
        command = step.commands[0]
        expected = step.outputs[0].body
        with tempfile.TemporaryDirectory(prefix="ail-ffi-quick-%d-" % step.number) as directory:
            work = workspace(directory)
            env = environment()
            local = work / program.argument
            self.assertTrue(local.is_file(), "step %d: %s is not in examples/ffi_quick/"
                            % (step.number, program.argument))
            done = subprocess.run(["bash", "-e", "-u", "-o", "pipefail", "-c", command.body],
                                  cwd=work, capture_output=True, text=True, timeout=600, env=env)
            self.assertEqual(done.returncode, 0, "step %d command failed:\nstdout:\n%s\nstderr:\n%s"
                             % (step.number, done.stdout[-2000:], done.stderr[-2000:]))
            self.assertEqual(done.stdout, expected,
                             "step %d: command output is not the page's output block" % step.number)
            python = subprocess.run([sys.executable, "-B", str(local)], cwd=work, capture_output=True,
                                    text=True, timeout=180,
                                    env=dict(env, PYTHONPATH=str(HERE)))
            self.assertEqual(python.returncode, 0, "step %d under python3:\n%s"
                             % (step.number, python.stderr[-2000:]))
            self.assertEqual(python.stdout, expected,
                             "step %d: the ctypes path and the page disagree" % step.number)


if __name__ == "__main__":
    unittest.main()
