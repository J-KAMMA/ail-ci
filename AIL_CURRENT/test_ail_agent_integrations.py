"""The agent-facing AIL material: llms.txt, the Claude/AGENTS snippets, the MCP server, the guide.

* every command in llms.txt runs from a source checkout and through the `ail` wrapper;
* llms.txt stays in llmstxt.org shape, under 150 lines, with resolving local links;
* the MCP tools run on three example files (typed, fallback, refused) and the stdio JSON-RPC loop
  answers initialize / tools/list / tools/call;
* the guide's worked example: the strict build refuses `slow.py` with AIL0103, applying the published
  fix produces `fixed.py`, the rebuild passes, and the native output equals CPython's.
"""
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CLI = HERE / "ail_chatgpt.py"
LLMS = REPO / "llms.txt"
SKILL = REPO / "integrations" / "claude-code" / "skills" / "ailc" / "SKILL.md"
AGENTS = REPO / "integrations" / "AGENTS.md"
MCP = REPO / "integrations" / "mcp" / "ailc_mcp.py"
MCP_EXAMPLES = REPO / "integrations" / "mcp" / "examples"
GUIDE = REPO / "docs" / "AGENT_GUIDE.md"
GUIDE_SLOW = REPO / "examples" / "agent_guide" / "slow.py"
GUIDE_FIXED = REPO / "examples" / "agent_guide" / "fixed.py"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
HEADERS = (Path(sysconfig.get_paths().get("include", "/nonexistent")) / "Python.h").is_file()
SHELL_BLOCK = re.compile(r"^```(?:sh|bash|shell)\n(.*?)^```\s*$", re.M | re.S)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\((?P<link>[^)]+)\)")


def hybrid_available():
    return bool(CC) and HEADERS


def load_mcp():
    spec = importlib.util.spec_from_file_location("ailc_mcp_under_test", MCP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shell_commands(text):
    commands = []
    for block in SHELL_BLOCK.findall(text):
        for line in block.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append(line)
    return commands


class LlmsTxt(unittest.TestCase):
    def setUp(self):
        self.text = LLMS.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()

    def test_shape_and_length(self):
        self.assertLessEqual(len(self.lines), 150, "llms.txt must stay under 150 lines")
        self.assertTrue(self.lines[0].startswith("# "), "llms.txt must start with a level-1 title")
        first = next(line for line in self.lines[1:] if line.strip())
        self.assertTrue(first.startswith("> "), "the title must be followed by a one-line blockquote")
        for heading in ("## When to use AIL", "## When not to use AIL", "## Commands", "## Docs"):
            self.assertIn(heading, self.text)
        self.assertIn("--json", self.text)
        self.assertIn("--strict", self.text)
        # Features that do not exist in this build are deliberately absent from the docs.
        self.assertNotIn("ailc ext", self.text)
        self.assertNotIn("--why", self.text)

    def test_local_links_resolve(self):
        failures = []
        for number, line in enumerate(self.lines, 1):
            for match in LINK.finditer(line):
                target = match.group("link").strip()
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                path = (LLMS.parent / target.split("#", 1)[0]).resolve()
                if not path.exists():
                    failures.append("line %d: %s" % (number, target))
        self.assertFalse(failures, "\n".join(failures))

    def test_every_command_runs(self):
        commands = shell_commands(self.text)
        self.assertGreaterEqual(len(commands), 8, commands)
        with tempfile.TemporaryDirectory(prefix="ail-llms-") as tmp:
            work = Path(tmp)
            (work / "prog.py").write_text(
                "def main() -> None:\n    print('hello')\n\n\nmain()\n", encoding="utf-8")
            (work / "AIL_CURRENT").symlink_to(HERE, target_is_directory=True)
            bindir = work / "bin"
            bindir.mkdir()
            wrapper = bindir / "ail"
            wrapper.write_text(
                "#!/bin/sh\n"
                "export PYTHONPATH=%s\n"
                "export AIL_SDK_DIR=%s\n"
                "export AIL_CACHE=%s\n"
                "exec %s -m ail_lang \"$@\"\n"
                % (shlex.quote(str(REPO / "packaging")), shlex.quote(str(HERE)),
                   shlex.quote(str(work / "cache")), shlex.quote(sys.executable)),
                encoding="utf-8")
            wrapper.chmod(0o755)
            env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                       PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
            for command in commands:
                if "--cpython" in command and not hybrid_available():
                    continue
                with self.subTest(command=command):
                    done = subprocess.run(shlex.split(command), cwd=work, env=env, capture_output=True,
                                          text=True, timeout=600)
                    self.assertEqual(done.returncode, 0,
                                     "%s\nstdout:\n%s\nstderr:\n%s"
                                     % (command, done.stdout[-2000:], done.stderr[-2000:]))
            for name in ("hello", "hello_strict", "hello_wrapper"):
                self.assertTrue((work / name).is_file(), name)
            if hybrid_available():
                self.assertTrue((work / "hello_fast").is_dir())


class AgentSnippets(unittest.TestCase):
    def test_skill_and_agents_cover_the_workflow(self):
        skill = SKILL.read_text(encoding="utf-8")
        agents = AGENTS.read_text(encoding="utf-8")
        for text, name in ((skill, "SKILL.md"), (agents, "AGENTS.md")):
            self.assertTrue(text.startswith("---") or text.startswith("# "), name)
            for needle in ("compile --strict --json", "agent_diagnostics", "fix.replace_range",
                           "run --diff", "build --cpython", "CPython"):
                self.assertIn(needle, text, "%s lacks %r" % (name, needle))
            self.assertNotIn("ailc ext", text)
            self.assertNotIn("--why", text)
        self.assertIn("name: ailc", skill)
        self.assertIn("description:", skill)
        guide = GUIDE.read_text(encoding="utf-8")
        self.assertNotIn("ailc ext", guide)
        self.assertNotIn("--why", guide)


class McpTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mcp = load_mcp()
        cls.paths = {name: MCP_EXAMPLES / (name + ".py") for name in ("typed", "mutates", "refused")}

    def test_check_build_and_explain_on_three_examples(self):
        expected = {
            "typed": {"check_ok": True, "function": "add", "on_cpython": False},
            "mutates": {"check_ok": False, "function": "push", "on_cpython": True,
                        "reason": "list parameter"},
            "refused": {"check_ok": False, "function": "countdown", "on_cpython": True,
                        "reason": "while-else"},
        }
        for name, path in self.paths.items():
            with self.subTest(example=name):
                check = self.mcp.ailc_check(str(path))
                self.assertEqual(check.get("schema"), "ail.check/1")
                self.assertEqual(check.get("ok"), expected[name]["check_ok"], check)
                self.assertIsInstance(check.get("diagnostics"), list)
                self.assertIsInstance(check.get("exit"), int)

                build = self.mcp.ailc_build(str(path))
                self.assertTrue(build.get("ok"), build)
                artifact = Path(build["artifact"])
                self.assertTrue(artifact.is_file(), artifact)
                self.assertEqual(artifact.parent.parent, Path(tempfile.gettempdir()),
                                 "the artifact must stay under /tmp")
                if name == "typed":
                    self.assertEqual(build.get("agent_diagnostics"), [])
                else:
                    self.assertTrue(build.get("agent_diagnostics"), build)

                explain = self.mcp.ailc_explain(str(path), expected[name]["function"])
                self.assertTrue(explain.get("ok"), explain)
                self.assertEqual(explain.get("on_cpython"), expected[name]["on_cpython"], explain)
                if expected[name]["on_cpython"]:
                    self.assertIn(expected[name]["reason"], explain.get("reason") or "")
                else:
                    self.assertIsNone(explain.get("reason"))
                    self.assertIn(expected[name]["function"], explain.get("accelerated") or [])

    def test_unknown_function_is_reported(self):
        result = self.mcp.ailc_explain(str(self.paths["typed"]), "not_a_function")
        self.assertFalse(result.get("ok"), result)
        self.assertIn("not_a_function", result.get("error", ""))

    def test_stdio_protocol(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2024-11-05", "capabilities": {}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "ailc_check", "arguments": {"path": str(self.paths["typed"])}}},
        ]
        payload = "".join(json.dumps(request) + "\n" for request in requests)
        env = dict(os.environ, AILC_MCP_NO_SDK="1", AIL_SDK_DIR=str(HERE),
                   PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        done = subprocess.run([sys.executable, str(MCP)], input=payload, capture_output=True, text=True,
                              timeout=600, env=env)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        replies = {}
        for line in done.stdout.splitlines():
            if not line.strip():
                continue
            message = json.loads(line)
            replies[message.get("id")] = message
        self.assertEqual(sorted(replies), [1, 2, 3], done.stdout)
        self.assertEqual(replies[1]["result"]["serverInfo"]["name"], "ailc")
        names = [tool["name"] for tool in replies[2]["result"]["tools"]]
        self.assertEqual(names, ["ailc_check", "ailc_build", "ailc_explain"])
        content = replies[3]["result"]["content"][0]
        report = json.loads(content["text"])
        self.assertEqual(report.get("schema"), "ail.check/1")
        self.assertTrue(report.get("ok"), report)


class WorkedExample(unittest.TestCase):
    def test_guide_names_the_example_files(self):
        text = GUIDE.read_text(encoding="utf-8")
        for needle in ("slow.py", "fixed.py", "AIL0103", "ail.strict/1", "--strict --json",
                       "4.63", "0.16", "28.9x"):
            self.assertIn(needle, text)
        self.assertTrue(GUIDE_SLOW.is_file())
        self.assertTrue(GUIDE_FIXED.is_file())

    def test_refusal_fix_and_cpython_match(self):
        with tempfile.TemporaryDirectory(prefix="ail-guide-") as tmp:
            work = Path(tmp)
            out = work / "slow.bin"
            env = dict(os.environ, AIL_NO_CACHE="1", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
            refused = subprocess.run(
                [sys.executable, "-B", str(CLI), "compile", "--strict", "--json", "--syntax", "python",
                 str(GUIDE_SLOW), "-o", str(out)],
                cwd=work, env=env, capture_output=True, text=True, timeout=600)
            self.assertEqual(refused.returncode, 3, refused.stderr[-2000:])
            report = json.loads(refused.stdout.strip().splitlines()[-1])
            self.assertEqual(report.get("schema"), "ail.strict/1", report)
            self.assertEqual(report.get("status"), "refused")
            diagnostics = report.get("agent_diagnostics") or []
            self.assertEqual([item.get("code") for item in diagnostics], ["AIL0103"], report)
            fix = diagnostics[0]["fix"]
            self.assertEqual(fix["replace_range"], [8, 8])

            lines = GUIDE_SLOW.read_text(encoding="utf-8").splitlines(keepends=True)
            first, last = fix["replace_range"]
            fixed = "".join(lines[:first - 1] + [fix["with"] + "\n"] + lines[last:])
            self.assertEqual(fixed, GUIDE_FIXED.read_text(encoding="utf-8"))

            built = work / "fixed.bin"
            passed = subprocess.run(
                [sys.executable, "-B", str(CLI), "compile", "--strict", "--json", "--syntax", "python",
                 str(GUIDE_FIXED), "-o", str(built)],
                cwd=work, env=env, capture_output=True, text=True, timeout=600)
            self.assertEqual(passed.returncode, 0, passed.stderr[-2000:])
            self.assertEqual(json.loads(passed.stdout.strip().splitlines()[-1]).get("status"), "passed")

            want = subprocess.run([sys.executable, str(GUIDE_FIXED)], cwd=work, capture_output=True,
                                  text=True, timeout=600, env=env)
            got = subprocess.run([str(built)], cwd=work, capture_output=True, text=True, timeout=600,
                                 env=env)
            self.assertEqual(got.returncode, want.returncode, got.stderr[-1000:])
            self.assertEqual(got.stdout, want.stdout)


if __name__ == "__main__":
    unittest.main()
