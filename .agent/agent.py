#!/usr/bin/env python3
"""Minimal coding agent on the plain Anthropic Messages API (no Claude Code), billed to ANTHROPIC_API_KEY.

    ANTHROPIC_API_KEY=... python3 agent.py --dir ~/wt/x --prompt-file task.md --model claude-sonnet-5-5 \
        --log run.jsonl [--budget-usd 5] [--max-turns 150]

Tools: bash (cwd = --dir, timeout), read_file, write_file, edit_file. File tools refuse paths outside --dir.
Bash refuses pushes, stash, history rewrites, hard deletes, network fetches and installs; it is a guard rail,
not a sandbox, so only run this on a disposable worktree. The key is never printed or logged.
"""
import argparse, json, os, re, subprocess, sys, time, urllib.error, urllib.request

API = "https://api.anthropic.com/v1/messages"
# USD per million tokens (input, output); cache reads bill at 10% of input, cache writes at 125%.
PRICES = {"haiku": (1.0, 5.0), "sonnet": (3.0, 15.0), "opus": (5.0, 25.0)}
DENY = re.compile(r"\bgit\s+(push|stash|reset\s+--hard|rebase|filter-branch|clean)\b|\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r"
                  r"|\b(curl|wget|ssh|scp)\b|\bpip3?\s+install\b|\bnpm\s+(i|install)\b|\bapt(-get)?\b|\bsudo\b")
TOOLS = [
    {"name": "bash", "description": "Run a bash command in the work directory. Output is truncated to 8000 chars, so filter it (grep, tail, head).",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"},
                      "timeout": {"type": "integer", "description": "seconds, default 600"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read a text file (path relative to the work dir). Optional 1-based line range.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"},
                      "end": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Create or overwrite a file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace one exact, unique occurrence of old with new.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"},
                      "new": {"type": "string"}}, "required": ["path", "old", "new"]}},
]


def call(body):
    data = json.dumps(body).encode()
    for attempt in range(8):
        req = urllib.request.Request(API, data=data, headers={
            "x-api-key": KEY, "anthropic-version": "2023-06-01",
            "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 529) and attempt < 7:
                time.sleep(min(60, 5 * 2 ** attempt)); continue
            raise SystemExit(f"API error {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError):
            if attempt < 7:
                time.sleep(10); continue
            raise


KEY = ""
SESSION = "ail-%d-%d" % (os.getpid(), int(time.time()))
# Tool shells never see the key or other credentials.
TOOL_ENV = {k: v for k, v in os.environ.items()
            if k not in ("ANTHROPIC_API_KEY", "OPENCODE_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN",
                         "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "WSLENV")}


def inside(root, p):
    full = os.path.realpath(os.path.join(root, p))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError(f"path outside the work dir: {p}")
    return full


def run_tool(root, name, a):
    try:
        if name == "bash":
            cmd = a["command"]
            if DENY.search(cmd):
                return "refused: this command is not allowed here (push/stash/rewrite/hard delete/network/install)"
            p = subprocess.run(["bash", "-lc", cmd], cwd=root, capture_output=True, text=True,
                               timeout=a.get("timeout") or 600, errors="replace", env=TOOL_ENV)
            out = (p.stdout + p.stderr)
            if len(out) > 8000:   # every turn resends the history: keep tool output short
                out = out[:3000] + f"\n... [{len(out) - 6000} chars cut; grep or tail for the part you need] ...\n" + out[-3000:]
            return f"{out}\n[exit {p.returncode}]"
        path = inside(root, a["path"])
        if name == "read_file":
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            s, e = (a.get("start") or 1), (a.get("end") or len(lines))
            text = "".join(f"{i}\t{l}" for i, l in enumerate(lines[s - 1:e], s))
            return text[:40000] + ("\n[truncated; use start/end]" if len(text) > 40000 else "")
        if name == "write_file":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(a["content"])
            return "written"
        if name == "edit_file":
            with open(path, encoding="utf-8") as f:
                text = f.read()
            n = text.count(a["old"])
            if n != 1:
                return f"refused: old text found {n} times (must be exactly once)"
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.replace(a["old"], a["new"], 1))
            return "edited"
    except subprocess.TimeoutExpired:
        return "timed out"
    except Exception as e:  # report tool failures to the model instead of dying
        return f"error: {e}"
    return f"unknown tool {name}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True); ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--model", default="claude-sonnet-5-5"); ap.add_argument("--log", required=True)
    ap.add_argument("--budget-usd", type=float, default=5.0); ap.add_argument("--max-turns", type=int, default=150)
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--key-file", help="read the API key from this file and delete it (CI: keeps the key out of "
                                       "the process environment, which child shells could read in /proc)")
    ap.add_argument("--provider", choices=("anthropic", "openai"), default="anthropic",
                    help="openai: any OpenAI-compatible chat-completions endpoint (OpenCode, DeepSeek, ...)")
    ap.add_argument("--base-url", help="openai provider: endpoint base, e.g. https://host/v1")
    ap.add_argument("--price-in", type=float, default=0.3, help="openai provider: USD per million input tokens")
    ap.add_argument("--price-out", type=float, default=1.2, help="openai provider: USD per million output tokens")
    args = ap.parse_args()
    global KEY
    env_key = "OPENCODE_API_KEY" if args.provider == "openai" else "ANTHROPIC_API_KEY"
    if args.key_file:
        with open(args.key_file, encoding="utf-8-sig") as f:   # -sig: PowerShell pipes add a BOM
            KEY = f.read().strip().lstrip("\ufeff")
        os.unlink(args.key_file)
    else:
        KEY = os.environ.get(env_key, "")
    if not KEY:
        raise SystemExit(f"no API key ({env_key} or --key-file)")
    if args.provider == "openai" and not args.base_url:
        raise SystemExit("--base-url is required with --provider openai")
    root = os.path.realpath(os.path.expanduser(args.dir))
    pin, pout = next((v for k, v in PRICES.items() if k in args.model), PRICES["opus"])
    system = (f"Today is {time.strftime('%Y-%m-%d')}; use this date in logs, never a guess. "
              f"You are a careful software engineer working alone in {root}. Use the tools to inspect, edit and test. "
              "Be economical: grep before reading, read only the lines you need. When the task is done, reply with "
              "a short final report and no tool call.")
    with open(os.path.expanduser(args.prompt_file), encoding="utf-8") as f:
        prompt = f.read()
    log = open(os.path.expanduser(args.log), "a", encoding="utf-8")
    if args.provider == "openai":
        return run_openai(args, root, system, prompt, log)
    msgs = [{"role": "user", "content": prompt}]
    cost = 0.0
    for turn in range(args.max_turns):
        # Cache the whole prefix: mark the last block of the newest message.
        last = msgs[-1]["content"]
        if isinstance(last, str):
            msgs[-1]["content"] = last = [{"type": "text", "text": last}]
        for m in msgs[:-1]:
            if isinstance(m["content"], list):
                for b in m["content"]:
                    b.pop("cache_control", None)
        last[-1]["cache_control"] = {"type": "ephemeral"}
        r = call({"model": args.model, "max_tokens": args.max_tokens, "system": system, "tools": TOOLS,
                  "messages": msgs})
        u = r.get("usage", {})
        cost += (u.get("input_tokens", 0) * pin + u.get("cache_read_input_tokens", 0) * pin * 0.1
                 + u.get("cache_creation_input_tokens", 0) * pin * 1.25 + u.get("output_tokens", 0) * pout) / 1e6
        msgs.append({"role": "assistant", "content": r["content"]})
        log.write(json.dumps({"turn": turn, "cost": round(cost, 4), "content": r["content"]}) + "\n"); log.flush()
        uses = [b for b in r["content"] if b["type"] == "tool_use"]
        if not uses:
            print("".join(b.get("text", "") for b in r["content"] if b["type"] == "text"))
            break
        results = []
        for b in uses:
            out = run_tool(root, b["name"], b["input"])
            results.append({"type": "tool_result", "tool_use_id": b["id"], "content": out})
            log.write(json.dumps({"turn": turn, "tool": b["name"], "input": b["input"], "out": out[:2000]}) + "\n")
        if cost >= args.budget_usd:
            results.append({"type": "text", "text": "Budget reached: stop now and give your final report."})
        msgs.append({"role": "user", "content": results})
        if cost >= args.budget_usd * 1.2:
            print(f"stopped: budget ${cost:.2f}"); break
    print(f"[cost ${cost:.2f}, turns {turn + 1}]")


def call_openai(base_url, body):
    """POST an OpenAI-compatible /chat/completions request (OpenCode, DeepSeek and similar), with the same retries."""
    data = json.dumps(body).encode()
    url = base_url.rstrip("/") + "/chat/completions"
    for attempt in range(14):   # OpenCode Go returns short 503 bursts: keep trying for about 12 minutes
        # OpenCode Go asks clients to name themselves and send a stable per-conversation session id
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": "Bearer " + KEY, "content-type": "application/json",
            "User-Agent": "ail-agent/1.0", "x-opencode-session": SESSION})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 529) and attempt < 13:
                time.sleep(min(60, 5 * 2 ** attempt)); continue
            raise SystemExit(f"API error {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError):
            if attempt < 13:
                time.sleep(15); continue
            raise


def run_openai(args, root, system, prompt, log):
    """The same tool loop over the OpenAI chat-completions tool-call format."""
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                "parameters": t["input_schema"]}} for t in TOOLS]
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    cost = 0.0
    for turn in range(args.max_turns):
        r = call_openai(args.base_url, {"model": args.model, "max_tokens": args.max_tokens, "tools": tools,
                                        "messages": msgs})
        u = r.get("usage", {})
        hit = u.get("prompt_cache_hit_tokens", 0) or (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        cost += ((u.get("prompt_tokens", 0) - hit) * args.price_in + hit * args.price_in * 0.1
                 + u.get("completion_tokens", 0) * args.price_out) / 1e6
        m = r["choices"][0]["message"]
        keep = {"role": "assistant", "content": m.get("content") or ""}
        # DeepSeek thinking mode: the reasoning must be sent back with the turn, or the next call fails with 400
        # (always present, even empty: a single turn without it makes every later call fail)
        keep["reasoning_content"] = m.get("reasoning_content") or ""
        if m.get("tool_calls"):
            keep["tool_calls"] = m["tool_calls"]
        msgs.append(keep)
        log.write(json.dumps({"turn": turn, "cost": round(cost, 4), "message": keep}) + "\n"); log.flush()
        calls = m.get("tool_calls") or []
        if not calls:
            print(m.get("content") or "")
            break
        for c in calls:
            try:
                a = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError as e:
                out = f"error: tool arguments are not JSON: {e}"
            else:
                out = run_tool(root, c["function"]["name"], a)
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": out})
            log.write(json.dumps({"turn": turn, "tool": c["function"]["name"], "out": out[:2000]}) + "\n")
        if cost >= args.budget_usd:
            msgs.append({"role": "user", "content": "Budget reached: stop now and give your final report."})
        if cost >= args.budget_usd * 1.2:
            print(f"stopped: budget ${cost:.2f}"); break
    print(f"[cost ${cost:.2f}, turns {turn + 1}]")


if __name__ == "__main__":
    main()
