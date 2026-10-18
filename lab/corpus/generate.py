#!/usr/bin/env python3
"""Ask an OpenCode model for one Python program per task (first reply only, no retries).

    OPENCODE_BIN=/path/to/opencode OPENCODE_DATA=/path/to/data-dir       python3 generate.py opencode/glm-5.3-flash-free [--budget 21600] [--limit N]

Programs go to programs/<model>/tNNN.py; one JSON line per attempt is appended to
programs/<model>/status.jsonl (status: ok | empty | no-code | timeout). Re-running skips tasks already answered (--redo-empty asks the empty and timed-out ones again).
OPENCODE_BIN may point to a Windows .exe when running under WSL; OPENCODE_DATA then is a Windows path
and is exported through WSLENV so the CLI keeps its own state directory.
"""
import argparse, json, os, random, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIMIT = 300
CODE = re.compile(r"```(?:python|py|Python)?[ \t]*\n(.*?)```", re.S)


def extract(reply):
    blocks = CODE.findall(reply)
    if blocks:
        return max(blocks, key=len) if len(blocks) > 1 and "def main" not in blocks[0] else blocks[0]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--budget", type=float, default=21600, help="wall-clock seconds before stopping")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--redo-empty", action="store_true", help="forget earlier empty or timeout attempts and ask again")
    ap.add_argument("--backoff", type=float, default=900, help="seconds to wait when the service refuses the free tier")
    a = ap.parse_args()
    exe = os.environ["OPENCODE_BIN"]
    data = os.environ.get("OPENCODE_DATA")
    env = dict(os.environ)
    if data:
        env.update(XDG_DATA_HOME=data, XDG_STATE_HOME=data, WSLENV="XDG_DATA_HOME/w:XDG_STATE_HOME/w")
    work = os.environ.get("OPENCODE_CWD") or str(HERE / ".empty")
    os.makedirs(work, exist_ok=True)
    short = a.model.split("/")[-1]
    out = HERE / "programs" / short
    out.mkdir(parents=True, exist_ok=True)
    tids = sorted(p.name for p in (HERE / "tasks").iterdir())
    random.Random(7).shuffle(tids)  # categories get covered evenly if the budget runs out
    last = {}  # task -> status of its last attempt, from status.jsonl
    sj = out / "status.jsonl"
    for line in (sj.read_text().splitlines() if sj.exists() else []):
        j = json.loads(line)
        last[j["task"]] = j["status"]
    t0 = time.time()
    done = n = 0
    for tid in tids:
        if tid in last and (not a.redo_empty or last[tid] in ("ok", "no-code")):
            continue
        if time.time() - t0 > a.budget or (a.limit and n >= a.limit):
            break
        n += 1
        prompt = (HERE / "tasks" / tid / "prompt.md").read_text(encoding="utf-8")
        t1 = time.time()
        try:
            r = subprocess.run([exe, "run", "--model", a.model, prompt], cwd=work, env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=LIMIT, stdin=subprocess.DEVNULL)
            reply = r.stdout
            status = "empty" if not reply.strip() else "ok"
            if status == "empty" and "free tier can only" in (r.stderr or "") + r.stdout:
                status = "blocked"  # the service refused the request: not a model reply
        except subprocess.TimeoutExpired:
            reply, status = "", "timeout"
        if status == "blocked":
            print(tid, "blocked by the service; waiting", a.backoff, "s", flush=True)
            time.sleep(a.backoff)
            if time.time() - t0 > a.budget:
                break
            tids.append(tid)  # try this task again later
            continue
        code = extract(reply) if reply else None
        if status == "ok" and code is None:
            status = "no-code"
        if code is not None:
            (out / (tid + ".py")).write_text(code, encoding="utf-8")
        with open(out / "status.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"task": tid, "status": status, "seconds": round(time.time() - t1, 1)}) + "\n")
        print(tid, status, round(time.time() - t1), flush=True)


main()
