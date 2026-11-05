"""Every fenced code block in the user-facing docs is run, parsed, or skipped with a reason.

The four files are README.md, docs/FFI.md, docs/LSP.md and docs/INSTALL.md. A block is covered in
one of these ways:

* an unmarked ```python block is a whole program: it is run under CPython, built with
  `ail_chatgpt.py compile --syntax python`, and the executable's stdout and exit status must match;
* an FFI block marked `<!-- docs-test: ffi examples/ffi/NAME.py -->` must be made of excerpts of
  that whole example, which is then run under CPython and as an AIL executable (the same comparison
  as test_ail_ffi_examples.py);
* an unmarked ```sh block runs through the checkout in a temporary directory. `ail` is the
  packaging/ail_lang entry point, `AIL_CURRENT/` and `examples/` are made visible from the checkout,
  and a trailing one-word `# output` comment is compared with stdout;
* an unmarked ```json block is parsed with json.loads;
* any other block needs `<!-- docs-test: skip REASON -->` on the line before its opening fence.

An unmarked block of an unknown language fails, so a new example cannot be added silently.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CLI = HERE / "ail_chatgpt.py"
PACKAGING = REPO / "packaging"
DOCS = (
    REPO / "README.md",
    REPO / "docs" / "FFI.md",
    REPO / "docs" / "LSP.md",
    REPO / "docs" / "INSTALL.md",
)
FENCE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,})(?P<lang>[^\s`]*)\s*$")
CLOSING = re.compile(r"^ {0,3}`{3,}\s*$")
MARKER = re.compile(r"^<!--\s*docs-test:\s*(?P<action>\S+)(?:\s+(?P<arg>.*?))?\s*-->$")
SHELL_LANGS = {"sh", "bash", "shell", "console"}
PYTHON_LANGS = {"python", "python3", "py"}
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


class Block:
    def __init__(self, path, line, lang, body, marker):
        self.path = path
        self.line = line
        self.lang = lang
        self.body = body
        self.marker = marker
        self.action = None
        self.argument = None
        if marker:
            found = MARKER.match(marker)
            self.action = found.group("action")
            self.argument = (found.group("arg") or "").strip()

    @property
    def where(self):
        return "%s:%d" % (self.path.relative_to(REPO), self.line)

    @property
    def kind(self):
        if self.action == "skip":
            return "skip"
        if self.action == "ffi":
            return "ffi"
        if self.action in ("python", "shell", "json"):
            return self.action
        if self.action:
            return "unknown-marker"
        if self.lang in PYTHON_LANGS:
            return "python"
        if self.lang in SHELL_LANGS:
            return "shell"
        if self.lang == "json":
            return "json"
        return "unknown"


def parse(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks = []
    index = 0
    while index < len(lines):
        found = FENCE.match(lines[index])
        if not found:
            index += 1
            continue
        fence, lang = found.group("fence"), found.group("lang").lower()
        start = index + 1
        end = start
        while end < len(lines) and not CLOSING.match(lines[end]):
            end += 1
        if end >= len(lines):
            raise AssertionError("%s:%d: fenced block is not closed" % (path.relative_to(REPO), start))
        marker = None
        if index > 0:
            previous = lines[index - 1].strip()
            if previous.startswith("<!-- docs-test:"):
                if not MARKER.match(previous):
                    raise AssertionError("%s:%d: malformed docs-test marker: %s"
                                         % (path.relative_to(REPO), index, previous))
                marker = previous
        body = "\n".join(lines[start:end]) + ("\n" if end > start else "")
        blocks.append(Block(path, start, lang, body, marker))
        index = end + 1
    return blocks


def all_blocks():
    return [block for path in DOCS for block in parse(path)]


def have_header(name):
    if not CC:
        return False
    done = subprocess.run([CC, "-E", "-x", "c", "-", "-o", os.devnull],
                          input="#include <%s>\n" % name, capture_output=True, text=True)
    return done.returncode == 0


def have_lib(name):
    if not CC:
        return False
    done = subprocess.run([CC, "-x", "c", "-", "-l" + name, "-o", os.devnull],
                          input="int main(void){return 0;}\n", capture_output=True, text=True)
    return done.returncode == 0


def missing_reason(source_text):
    if not CC:
        return "installed C compiler required"
    headers = sorted(set(re.findall(r'header="([^"]+)"', source_text)))
    libraries = set()
    for call in re.findall(r"\blink\(([^)]*)\)", source_text):
        libraries.update(re.findall(r'"([^"]+)"', call))
    for name in headers:
        if not have_header(name):
            return "%s is not installed" % name
    for name in sorted(libraries):
        if not have_lib(name):
            return "-l%s is not installed" % name
    return None


def shell_environment(work):
    bindir = work / "bin"
    bindir.mkdir()
    wrapper = bindir / "ail"
    wrapper.write_text(
        "#!/bin/sh\n"
        "export PYTHONPATH=%s\n"
        "export AIL_SDK_DIR=%s\n"
        "export AIL_CACHE=%s\n"
        "exec %s -m ail_lang \"$@\"\n"
        % (shlex.quote(str(PACKAGING)), shlex.quote(str(HERE)),
           shlex.quote(str(work / "cache")), shlex.quote(sys.executable)),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    for name in ("AIL_CURRENT", "examples"):
        link = work / name
        if not link.exists():
            link.symlink_to(REPO / name, target_is_directory=True)
    return dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")


def expected_shell_output(body):
    """One-word trailing comments are the output the block shows (`ail run --strict fib.py  # 12586269025`)."""
    lines = []
    for line in body.splitlines():
        if line.lstrip().startswith("#"):
            continue
        found = re.search(r"\s#\s*(\S+)\s*$", line)
        if found and not found.group(1).startswith("-"):
            lines.append(found.group(1))
    return lines


class DocsBlocks(unittest.TestCase):
    maxDiff = None

    def run_python(self, block):
        with tempfile.TemporaryDirectory(prefix="ail-docs-python-") as directory:
            work = Path(directory)
            source = work / "program.py"
            source.write_text(block.body, encoding="utf-8")
            env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
            want = subprocess.run([sys.executable, "-B", str(source)], cwd=work, capture_output=True,
                                  text=True, timeout=120, env=env)
            executable = work / "program"
            build_env = dict(env, AIL_NO_CACHE="1")
            build_env.pop("AIL_NO_GENERAL", None)
            built = subprocess.run(
                [sys.executable, "-B", str(CLI), "compile", "--syntax", "python", str(source),
                 "-o", str(executable)],
                cwd=work, capture_output=True, text=True, timeout=600, env=build_env,
            )
            self.assertEqual(built.returncode, 0, "%s did not compile:\n%s%s"
                             % (block.where, built.stdout[-1500:], built.stderr[-1500:]))
            got = subprocess.run([str(executable)], cwd=work, capture_output=True, text=True,
                                 timeout=120, env=env)
            self.assertEqual(got.returncode, want.returncode,
                             "%s exit status; stderr: %s" % (block.where, got.stderr[-1500:]))
            self.assertEqual(got.stdout, want.stdout, "%s stdout differs from CPython" % block.where)

    def run_ffi(self, block):
        relative = block.argument
        self.assertTrue(relative, "%s: ffi marker needs an examples/ffi/ path" % block.where)
        source = (REPO / relative).resolve()
        self.assertEqual(source.parent, (REPO / "examples" / "ffi").resolve(),
                         "%s: ffi example must live under examples/ffi/" % block.where)
        self.assertTrue(source.is_file(), "%s: missing %s" % (block.where, relative))
        text = source.read_text(encoding="utf-8")
        for chunk in re.split(r"\n\s*\n", block.body):
            if chunk.strip():
                self.assertIn(chunk.strip(), text, "%s: block text is not in %s" % (block.where, relative))
        reason = missing_reason(text)
        if reason:
            self.skipTest(reason)
        with tempfile.TemporaryDirectory(prefix="ail-docs-ffi-") as directory:
            work = Path(directory)
            local = work / source.name
            shutil.copyfile(source, local)
            env = dict(os.environ, PYTHONPATH=str(HERE), PYTHONDONTWRITEBYTECODE="1",
                       PYTHONUTF8="1")
            want = subprocess.run([sys.executable, "-B", str(local)], cwd=work, capture_output=True,
                                  text=True, timeout=180, env=env)
            self.assertEqual(want.returncode, 0, "%s under CPython:\n%s"
                             % (relative, want.stderr[-1500:]))
            executable = work / (source.stem + ".out")
            build_env = dict(env, AIL_NO_CACHE="1")
            built = subprocess.run(
                [sys.executable, "-B", str(CLI), "compile", str(local), "-o", str(executable)],
                cwd=work, capture_output=True, text=True, timeout=600, env=build_env,
            )
            self.assertEqual(built.returncode, 0, "%s did not compile:\n%s%s"
                             % (relative, built.stdout[-1500:], built.stderr[-1500:]))
            got = subprocess.run([str(executable)], cwd=work, capture_output=True, text=True,
                                 timeout=180, env=env)
            self.assertEqual(got.returncode, want.returncode, "%s exit status; stderr: %s"
                             % (relative, got.stderr[-1500:]))
            self.assertEqual(got.stdout, want.stdout, "%s stdout differs from CPython" % relative)
            self.assertEqual(got.stderr, want.stderr, "%s stderr differs from CPython" % relative)

    def run_shell(self, block):
        with tempfile.TemporaryDirectory(prefix="ail-docs-shell-") as directory:
            work = Path(directory)
            env = shell_environment(work)
            script = work / "block.sh"
            script.write_text(block.body, encoding="utf-8")
            done = subprocess.run(["bash", "-e", "-u", "-o", "pipefail", str(script)],
                                  cwd=work, capture_output=True, text=True, timeout=600, env=env)
            self.assertEqual(done.returncode, 0, "%s failed:\nstdout:\n%s\nstderr:\n%s"
                             % (block.where, done.stdout[-2000:], done.stderr[-2000:]))
            expected = expected_shell_output(block.body)
            if expected:
                self.assertEqual(done.stdout.splitlines(), expected,
                                 "%s printed something other than the documented output" % block.where)

    def test_every_block_is_run_parsed_or_skipped(self):
        blocks = all_blocks()
        self.assertTrue(blocks, "no fenced blocks were found in the four docs")
        for block in blocks:
            with self.subTest(block=block.where):
                self.assertIn(block.kind, {"skip", "ffi", "python", "shell", "json"},
                              "%s: unmarked %r block; add a docs-test marker" % (block.where, block.lang))
                if block.kind == "skip":
                    self.assertTrue(block.argument, "%s: skip marker needs a reason" % block.where)
                    self.assertGreaterEqual(len(block.argument.split()), 3,
                                            "%s: skip reason is too short" % block.where)
                if block.kind == "ffi":
                    self.assertTrue(block.argument, "%s: ffi marker needs a path" % block.where)

    def test_python_blocks_match_cpython(self):
        for block in all_blocks():
            if block.kind == "python":
                with self.subTest(block=block.where):
                    self.run_python(block)

    def test_ffi_blocks_match_cpython(self):
        for block in all_blocks():
            if block.kind == "ffi":
                with self.subTest(block=block.where):
                    self.run_ffi(block)

    def test_shell_blocks_run(self):
        for block in all_blocks():
            if block.kind == "shell":
                with self.subTest(block=block.where):
                    self.run_shell(block)

    def test_json_blocks_parse(self):
        found = 0
        for block in all_blocks():
            if block.kind == "json":
                found += 1
                with self.subTest(block=block.where):
                    json.loads(block.body)
        self.assertGreater(found, 0, "docs/LSP.md no longer has a JSON block")

    def test_skip_blocks_are_counted(self):
        skipped = [block for block in all_blocks() if block.kind == "skip"]
        self.assertTrue(skipped, "the docs should mark the blocks that cannot run")
        for block in skipped:
            self.assertTrue(block.argument, "%s: skip marker needs a reason" % block.where)


if __name__ == "__main__":
    unittest.main()
