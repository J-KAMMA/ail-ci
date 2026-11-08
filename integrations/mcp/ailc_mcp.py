"""A minimal stdio MCP server for the AIL compiler (ailc).

Tools
  ailc_check(path)             compile diagnostics as JSON (no C build)
  ailc_build(path)             build a native executable; return its path or the diagnostics
  ailc_explain(path, function) why a function stays on CPython in the hybrid build

The server speaks JSON-RPC 2.0 on stdin/stdout (the MCP stdio transport). It uses only the
Python standard library; the optional `mcp` package is imported lazily inside `serve()` and,
when it is installed, provides the same three tools through its own server loop. There is no
network access.

Run it with the compiler from this checkout:

    python3 integrations/mcp/ailc_mcp.py

Set AILC_COMPILER to another ail_chatgpt.py, or AIL_SDK_DIR to a directory that contains it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.0"

TOOLS = [
    {
        "name": "ailc_check",
        "description": "Type/source-check an AIL or Python source file and return its diagnostics as JSON. "
                       "This does not invoke the C compiler.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "source file to check"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ailc_build",
        "description": "Build a native executable with ailc. Returns the artifact path on success, or the "
                       "compiler diagnostics (including agent_diagnostics with fixes) on failure.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "source file to build"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ailc_explain",
        "description": "Explain why one top-level function stays on CPython. Uses `build --cpython` and reads "
                       "the hybrid report; an accelerated function reports on_cpython=false.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "source file to analyse"},
                "function": {"type": "string", "description": "top-level function name"},
            },
            "required": ["path", "function"],
            "additionalProperties": False,
        },
    },
]


def compiler() -> Path:
    """The compiler entry point: AILC_COMPILER, then AIL_SDK_DIR, then this checkout."""
    configured = os.environ.get("AILC_COMPILER")
    if configured:
        return Path(configured).expanduser()
    sdk = os.environ.get("AIL_SDK_DIR")
    if sdk:
        return Path(sdk).expanduser() / "ail_chatgpt.py"
    return ROOT / "AIL_CURRENT" / "ail_chatgpt.py"


def _source(path) -> Path:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError("not a file: %s" % path)
    return source


def _run(args, cwd, timeout=600):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    command = [sys.executable, "-B", str(compiler()), *map(str, args)]
    return subprocess.run(command, cwd=str(cwd), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _json_report(text):
    """The last JSON object printed on stdout, or None."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def ailc_check(path: str) -> dict:
    """Diagnostics from `ail_chatgpt.py check`, as the ail.check/1 JSON report."""
    try:
        source = _source(path)
        done = _run(["check", str(source)], source.parent)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {"ok": False, "error": str(error)}
    report = _json_report(done.stdout)
    if report is None:
        return {"ok": False, "exit": done.returncode, "error": (done.stderr or done.stdout).strip()}
    report["ok"] = report.get("status") == "passed" and done.returncode == 0
    report["exit"] = done.returncode
    return report


def ailc_build(path: str) -> dict:
    """Build a native executable; the artifact path on success, diagnostics on failure."""
    try:
        source = _source(path)
        directory = Path(tempfile.mkdtemp(prefix="ailc-mcp-build-"))
        artifact = directory / (source.stem or "program")
        done = _run(["compile", "--json", str(source), "-o", str(artifact)], source.parent)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {"ok": False, "error": str(error)}
    report = _json_report(done.stdout) or {}
    result = {
        "ok": done.returncode == 0,
        "exit": done.returncode,
        "artifact": str(artifact) if done.returncode == 0 else None,
        "status": report.get("status"),
        "diagnostics": report.get("diagnostics") or [],
        "agent_diagnostics": report.get("agent_diagnostics") or [],
    }
    if done.returncode != 0:
        result["stderr"] = done.stderr.strip()
        result["report"] = report
    return result


def ailc_explain(path: str, function: str) -> dict:
    """Why `function` stays on CPython in the hybrid build (or that it was accelerated)."""
    try:
        source = _source(path)
        if not function or not function.isidentifier():
            return {"ok": False, "error": "function must be a top-level identifier"}
        directory = Path(tempfile.mkdtemp(prefix="ailc-mcp-explain-"))
        out = directory / "hybrid"
        done = _run(["build", "--cpython", str(source), "-o", str(out)], source.parent)
        report_path = out / "build.json"
        if not report_path.is_file():
            return {"ok": False, "exit": done.returncode,
                    "error": (done.stderr or done.stdout).strip() or "the hybrid build wrote no build.json"}
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {"ok": False, "error": str(error)}
    accelerated = list(report.get("accelerated") or [])
    rejected = dict(report.get("rejected") or {})
    if function in accelerated:
        return {"ok": True, "function": function, "on_cpython": False,
                "reason": None, "accelerated": accelerated, "rejected": rejected}
    if function in rejected:
        return {"ok": True, "function": function, "on_cpython": True,
                "reason": rejected[function], "accelerated": accelerated, "rejected": rejected}
    return {"ok": False, "function": function,
            "error": "no top-level function %r in %s" % (function, source),
            "accelerated": accelerated, "rejected": sorted(rejected)}


CALL = {
    "ailc_check": ailc_check,
    "ailc_build": ailc_build,
    "ailc_explain": ailc_explain,
}


def call_tool(name, arguments):
    arguments = arguments or {}
    if name not in CALL:
        return {"ok": False, "error": "unknown tool: %s" % name}, True
    try:
        result = CALL[name](**arguments)
    except TypeError as error:
        return {"ok": False, "error": "bad arguments for %s: %s" % (name, error)}, True
    except Exception as error:                       # a tool must never kill the server loop
        return {"ok": False, "error": "%s: %s" % (type(error).__name__, error)}, True
    return result, not result.get("ok", True)


def _tool_result(result, is_error):
    return {
        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
        "structuredContent": result,
        "isError": bool(is_error),
    }


def _respond(message):
    method = message.get("method")
    identifier = message.get("id")
    if method == "initialize":
        params = message.get("params") or {}
        result = {
            "protocolVersion": params.get("protocolVersion") or "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ailc", "version": VERSION},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params") or {}
        use, is_error = call_tool(params.get("name"), params.get("arguments"))
        result = _tool_result(use, is_error)
    elif method in ("notifications/initialized", "notifications/cancelled"):
        return None
    else:
        return {"jsonrpc": "2.0", "id": identifier,
                "error": {"code": -32601, "message": "method not found: %s" % method}}
    return {"jsonrpc": "2.0", "id": identifier, "result": result}


def serve_stdio():
    """The stdlib JSON-RPC loop used when the optional mcp package is not installed."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError as error:
            reply = {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "parse error: %s" % error}}
        else:
            reply = _respond(message)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def _serve_sdk():
    """The same tools through the optional `mcp` package (imported only when this is called)."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("ailc")
    for tool in TOOLS:
        function = CALL[tool["name"]]
        server.add_tool(function, name=tool["name"], description=tool["description"])
    server.run()


def serve():
    if os.environ.get("AILC_MCP_NO_SDK") != "1":
        try:
            _serve_sdk()
            return
        except ImportError:
            pass
    serve_stdio()


if __name__ == "__main__":
    serve()
