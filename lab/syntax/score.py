#!/usr/bin/env python3
"""Score AIL syntax-experiment submissions (stdlib only).

Layout read:   lab/syntax/runs/<model>/<variant>/<task>/attempt1.ail  (+ meta.json)
Tests:         lab/syntax/tasks/<task>/tests/<n>.in  and  <n>.out
Variants:      lab/syntax/variants.json  (status "mockup" variants are never scored)

Only attempt1.ail counts (first try). Model directories whose name starts with "_",
or whose meta.json has "sample": true, are samples and are skipped unless
--include-samples is given.

Verdict per submission: pass | compile-error | wrong-answer | runtime-error | timeout.

Token approximation (no real tokenizer, so numbers are comparable across variants
but are not billing tokens). Applied to the program text after stripping a Markdown
code fence if the model left one:
  * a newline together with the indentation after it           = 1 token
  * a run of 2+ spaces/tabs inside a line                      = 1 token
  * a single space between tokens                              = 0 (merges into the next token)
  * a word piece (letters; identifiers are split at `_` and at
    lower->Upper camelCase boundaries)                         = ceil(len / 6) tokens
  * a digit run                                                = ceil(len / 3) tokens
  * a two-character operator (-> == != <= >= += -= *= /= // ** :: => && ||) = 1 token
  * any other single character (punctuation, braces, quotes)   = 1 token
Comments and string contents are counted like code. meta.json "tokens_out", when the
model reports real output tokens, is shown as an extra column but never used for ranking.

Metrics per (model, variant):
  pass rate        = passes / submitted
  mean tokens      = mean approximate tokens over submitted attempts
  tokens per pass  = total tokens of all attempts / passes   (lower is better; "-" if no pass)
  pass per 1k tok  = pass rate * 1000 / mean tokens          (higher is better)
"""
import argparse
import json
import math
import os
import re
import resource
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
COMPILER_DIR = os.path.join(REPO, "AIL_CURRENT")
COMPILE_TIMEOUT = 180
RUN_TIMEOUT = 10

_TOKEN_RE = re.compile(
    r"\n[ \t]*"            # newline + indentation
    r"|[ \t]{2,}"          # inner run of blanks
    r"|[ \t]"              # single blank (free)
    r"|->|==|!=|<=|>=|\+=|-=|\*=|/=|//|\*\*|::|=>|&&|\|\|"
    r"|[A-Za-z]+"          # word piece
    r"|[0-9]+"             # digits
    r"|.",                 # anything else
    re.S)


def strip_fence(text):
    m = re.search(r"```[A-Za-z0-9_+-]*[ \t]*\n(.*?)```", text, re.S)
    return m.group(1) if m else text


def approx_tokens(text):
    count = 0
    # split camelCase so `readLine` is two pieces; underscores are punctuation-like separators
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    for tok in _TOKEN_RE.findall(text):
        c = tok[0]
        if c == "\n" or (c in " \t" and len(tok) >= 2):
            count += 1
        elif c in " \t":
            continue
        elif c.isalpha() and tok.isalpha():
            count += math.ceil(len(tok) / 6)
        elif tok.isdigit():
            count += math.ceil(len(tok) / 3)
        else:
            count += 1
    return count


def normalize(text):
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _limits():
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (RUN_TIMEOUT, RUN_TIMEOUT))
        resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 << 20, 16 << 20))
    except (ValueError, OSError):
        pass


def load_tasks(tasks_dir):
    tasks = {}
    for name in sorted(os.listdir(tasks_dir)):
        tdir = os.path.join(tasks_dir, name, "tests")
        if not os.path.isfile(os.path.join(tasks_dir, name, "statement.md")):
            continue
        cases = []
        for f in sorted(os.listdir(tdir)):
            if f.endswith(".in"):
                out = os.path.join(tdir, f[:-3] + ".out")
                if os.path.isfile(out):
                    cases.append((os.path.join(tdir, f), out))
        tasks[name] = cases
    return tasks


def first_line(text):
    for ln in text.strip().splitlines()[::-1]:
        if ln.strip():
            return ln.strip()[:160]
    return ""


def judge(job):
    """job = (model, variant, task, attempt_path, cases). Returns result dict."""
    model, variant, task, path, cases = job
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    src = strip_fence(raw)
    res = {"model": model, "variant": variant, "task": task,
           "tokens": approx_tokens(src), "verdict": None, "detail": ""}
    meta_path = os.path.join(os.path.dirname(path), "meta.json")
    try:
        with open(meta_path, encoding="utf-8") as fh:
            res["real_tokens"] = json.load(fh).get("tokens_out")
    except (OSError, ValueError):
        res["real_tokens"] = None
    with tempfile.TemporaryDirectory(prefix="ailsyn-") as tmp:
        sp = os.path.join(tmp, task + ".ail")
        exe = os.path.join(tmp, "prog")
        with open(sp, "w", encoding="utf-8") as fh:
            fh.write(src)
        try:
            cp = subprocess.run(
                [sys.executable, os.path.join(COMPILER_DIR, "ail_chatgpt.py"), "compile", sp, "-o", exe],
                cwd=COMPILER_DIR, capture_output=True, text=True, timeout=COMPILE_TIMEOUT)
        except subprocess.TimeoutExpired:
            res.update(verdict="compile-error", detail="compiler timeout")
            return res
        if cp.returncode != 0 or not os.path.isfile(exe):
            res.update(verdict="compile-error", detail=first_line(cp.stderr or cp.stdout))
            return res
        for i, (inp, outp) in enumerate(cases, 1):
            with open(inp, "rb") as fi, open(outp, encoding="utf-8") as fo:
                expected = normalize(fo.read())
                try:
                    rp = subprocess.run([exe], stdin=fi, capture_output=True, cwd=tmp,
                                        timeout=RUN_TIMEOUT, preexec_fn=_limits)
                except subprocess.TimeoutExpired:
                    res.update(verdict="timeout", detail=f"test {i}")
                    return res
            got = normalize(rp.stdout.decode("utf-8", "replace"))
            if rp.returncode != 0:
                res.update(verdict="runtime-error",
                           detail=f"test {i}: exit {rp.returncode} {first_line(rp.stderr.decode('utf-8', 'replace'))}")
                return res
            if got != expected:
                res.update(verdict="wrong-answer", detail=f"test {i}")
                return res
    res["verdict"] = "pass"
    return res


def discover(runs_dir, variants, tasks, include_samples):
    jobs, skipped = [], []
    if not os.path.isdir(runs_dir):
        return jobs, skipped
    for model in sorted(os.listdir(runs_dir)):
        mdir = os.path.join(runs_dir, model)
        if not os.path.isdir(mdir):
            continue
        is_sample_dir = model.startswith("_")
        for variant in sorted(os.listdir(mdir)):
            vdir = os.path.join(mdir, variant)
            if not os.path.isdir(vdir):
                continue
            for task in sorted(os.listdir(vdir)):
                attempt = os.path.join(vdir, task, "attempt1.ail")
                if not os.path.isfile(attempt):
                    continue
                sample = is_sample_dir
                try:
                    with open(os.path.join(vdir, task, "meta.json"), encoding="utf-8") as fh:
                        sample = sample or bool(json.load(fh).get("sample"))
                except (OSError, ValueError):
                    pass
                tag = f"{model}/{variant}/{task}"
                if sample and not include_samples:
                    skipped.append((tag, "sample"))
                elif variant not in variants:
                    skipped.append((tag, "unknown variant"))
                elif variants[variant]["status"] != "supported":
                    skipped.append((tag, f"variant is {variants[variant]['status']}"))
                elif task not in tasks:
                    skipped.append((tag, "unknown task"))
                else:
                    jobs.append((model, variant, task, attempt, tasks[task]))
    return jobs, skipped


def render(results, skipped, tasks, variants, include_samples):
    out = ["# AIL syntax experiment: scores", ""]
    if include_samples:
        out += ["> Samples included (pipeline check). Not real results.", ""]
    groups = {}
    for r in results:
        groups.setdefault((r["model"], r["variant"]), []).append(r)
    if not groups:
        out += ["No scorable submissions yet.", ""]
    else:
        rows = []
        for (model, variant), rs in groups.items():
            n = len(rs)
            passes = sum(r["verdict"] == "pass" for r in rs)
            total_tok = sum(r["tokens"] for r in rs)
            mean_tok = total_tok / n
            real = [r["real_tokens"] for r in rs if isinstance(r["real_tokens"], int)]
            rows.append({
                "model": model, "variant": variant, "n": n, "passes": passes,
                "rate": passes / n, "mean": mean_tok,
                "tpp": (total_tok / passes) if passes else None,
                "ppk": (passes / n) * 1000 / mean_tok if mean_tok else 0.0,
                "real": (sum(real) / len(real)) if len(real) == n else None})
        rows.sort(key=lambda x: (-x["ppk"], x["model"], x["variant"]))
        out += [f"Tasks available: {len(tasks)}. Only `attempt1.ail` counts.", "",
                "| model | variant | submitted | pass rate | mean tokens (approx) | tokens per pass | pass per 1k tokens | mean real tokens |",
                "|---|---|---|---|---|---|---|---|"]
        for x in rows:
            out.append("| {model} | {variant} | {n}/{T} | {passes}/{n} ({pct:.0f}%) | {mean:.0f} | {tpp} | {ppk:.2f} | {real} |".format(
                model=x["model"], variant=x["variant"], n=x["n"], T=len(tasks), passes=x["passes"],
                pct=100 * x["rate"], mean=x["mean"],
                tpp=f"{x['tpp']:.0f}" if x["tpp"] else "-", ppk=x["ppk"],
                real=f"{x['real']:.0f}" if x["real"] is not None else "-"))
        out += ["", "## Per task", "",
                "Legend: ok = pass, CE = compile error, WA = wrong answer, RE = runtime error, TO = timeout, . = not submitted.", ""]
        names = list(tasks)
        out.append("| model | variant | " + " | ".join(names) + " |")
        out.append("|---|---|" + "---|" * len(names))
        code = {"pass": "ok", "compile-error": "CE", "wrong-answer": "WA", "runtime-error": "RE", "timeout": "TO"}
        for x in rows:
            by = {r["task"]: code[r["verdict"]] for r in groups[(x["model"], x["variant"])]}
            out.append(f"| {x['model']} | {x['variant']} | " + " | ".join(by.get(t, ".") for t in names) + " |")
        bad = [r for r in results if r["verdict"] != "pass"]
        if bad:
            out += ["", "## Failures", ""]
            for r in sorted(bad, key=lambda r: (r["model"], r["variant"], r["task"])):
                out.append(f"- `{r['model']}/{r['variant']}/{r['task']}`: {r['verdict']} {r['detail']}".rstrip())
        out.append("")
    mock = [f"`{k}` ({v['status']})" for k, v in variants.items() if v["status"] != "supported"]
    if mock:
        out += ["Variants excluded from scoring: " + ", ".join(mock) + ".", ""]
    if skipped:
        out += ["<details><summary>Skipped submissions ({})</summary>".format(len(skipped)), ""]
        out += [f"- `{t}`: {why}" for t, why in skipped]
        out += ["", "</details>", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", default=os.path.join(HERE, "runs"))
    ap.add_argument("--out", help="write the Markdown table here as well as stdout")
    ap.add_argument("--include-samples", action="store_true")
    ap.add_argument("-j", type=int, default=4, help="parallel compiles (default 4, max 8)")
    a = ap.parse_args()
    with open(os.path.join(HERE, "variants.json"), encoding="utf-8") as fh:
        variants = json.load(fh)
    tasks = load_tasks(os.path.join(HERE, "tasks"))
    jobs, skipped = discover(a.runs, variants, tasks, a.include_samples)
    with ThreadPoolExecutor(max_workers=max(1, min(a.j, 8))) as ex:
        results = list(ex.map(judge, jobs))
    md = render(results, skipped, tasks, variants, a.include_samples)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(md)
    print(md)


if __name__ == "__main__":
    main()
