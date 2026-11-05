#!/usr/bin/env python3
"""Measure the lab/race probe suite: CPython 3.12 against AIL in the default and forced builds.

    python3 lab/race/run.py [--quick]

Each ordinary probe is built twice (default, AIL_UNIFIED_FORCE=1), classified as typed parallel,
typed, general or refused, run at AIL_THREADS 1, 2, 4 and 16 (three times each) and compared with
`python3`. A build on the typed parallel path is also compiled once with ThreadSanitizer from the
kept C and run once. A hybrid probe is a helper module `<name>.py` plus a threaded CPython runner
`<name>_run.py`: the helper is built with `ail build --cpython` (that is the probe's own build), and
a copy of the runner is run from a clean directory with `PYTHONPATH` at the built output, so the
generated wrapper (not the source helper) is imported; its output is compared with CPython. The
runner is also compiled and run in the default and forced AIL builds, so every row has both
results where the general path can build the runner. The three counts and a table go to
lab/race/RESULTS.md.

Definitions from the job:
  silent race    a racy probe that runs on the typed parallel path (a shared write without the
                 lock), prints something other than CPython, or gets a TSan report;
  safe matched   a safe probe whose stdout and exit status equal CPython's at 1, 2, 4 and 16;
  safe GIL-free  a safe probe built on the typed parallel path.
"""
import argparse
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CLI = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
MEMORY = 1500000 * 1024
BUILD_TIMEOUT = 900
RUN_TIMEOUT = 300
THREADS = (1, 2, 4, 16)
RUNS = 3


def clean_env(extra=None):
    env = dict(os.environ)
    for key in ("PYTHONPATH", "AIL_THREADS", "AIL_UNIFIED_FORCE", "AIL_NO_GENERAL",
                "AIL_STRICT", "AIL_UNIFIED", "AIL_IR"):
        env.pop(key, None)
    env["AIL_NO_CACHE"] = "1"
    env["PYTHONUTF8"] = "1"
    if extra:
        env.update(extra)
    return env


def _limit():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))


def call(cmd, timeout, env, cwd=None, limit=True):
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=timeout,
                              preexec_fn=_limit if limit and os.name == "posix" else None)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(cmd, -9, exc.stdout or b"", b"timeout\n")


def text(data):
    return data.decode("utf-8", "replace")


def first_line(data):
    for line in text(data).splitlines():
        line = line.strip()
        if line and not line.startswith("{"):
            return line[:500]
    return ""


def compile_probe(src, work, force):
    exe = work / ("exe-force" if force else "exe-default")
    dbg = work / ("dbg-force" if force else "dbg-default")
    if exe.exists():
        exe.unlink()
    shutil.rmtree(dbg, ignore_errors=True)
    env = clean_env({"AIL_UNIFIED_FORCE": "1"} if force else None)
    got = call([sys.executable, "-B", str(CLI), "compile", str(src), "-o", str(exe),
                "--debug-dir", str(dbg)], BUILD_TIMEOUT, env, cwd=work)
    shown = text(got.stderr) + text(got.stdout)
    record = {"returncode": got.returncode, "text": shown, "exe": exe, "dbg": dbg}
    if got.returncode != 0:
        record["path"] = "refused"
        record["note"] = first_line(got.stderr or got.stdout)
        return record
    if force:
        record["path"] = "general (forced)"
        record["note"] = "AIL_UNIFIED_FORCE=1"
    elif "built on the general path" in shown:
        record["path"] = "general"
        record["note"] = first_line(got.stderr)
    else:
        cfile = dbg / "program.c"
        body = cfile.read_text(encoding="utf-8", errors="replace") if cfile.is_file() else ""
        record["path"] = "typed parallel" if "ail_par_run" in body else "typed"
        record["note"] = ""
    return record


def cpython_run(src, timeout=RUN_TIMEOUT, extra_env=None, cwd=None):
    env = clean_env(extra_env)
    got = call([sys.executable, "-B", str(src)], timeout, env, cwd=cwd)
    return {"returncode": got.returncode, "stdout": got.stdout, "stderr": got.stderr,
            "timeout": got.returncode == -9}


def program_run(exe, threads, runs=RUNS, extra_env=None):
    outs = []
    env = clean_env({"AIL_THREADS": str(threads)})
    if extra_env:
        env.update(extra_env)
    for _ in range(runs):
        got = call([str(exe)], RUN_TIMEOUT, env, cwd=exe.parent)
        outs.append({"returncode": got.returncode, "stdout": got.stdout, "stderr": got.stderr,
                     "timeout": got.returncode == -9})
    return outs


def matches(want, got):
    return (not got["timeout"] and got["returncode"] == want["returncode"]
            and got["stdout"] == want["stdout"])


def tsan_check(build, work):
    """Build the kept typed C with ThreadSanitizer and run it once; (flag, detail)."""
    cfile = build["dbg"] / "program.c"
    if not cfile.is_file() or not shutil.which("gcc"):
        return False, "no C or gcc"
    exe = work / "exe-tsan"
    if exe.exists():
        exe.unlink()
    cc = subprocess.run(["gcc", "-O1", "-g", "-fsanitize=thread", "-o", str(exe), str(cfile),
                         "-lm", "-pthread"], capture_output=True, text=True, timeout=BUILD_TIMEOUT)
    if cc.returncode:
        return False, "gcc: " + first_line(cc.stderr.encode())
    norand = ["setarch", platform.machine(), "-R"] if shutil.which("setarch") else []
    env = clean_env({"AIL_THREADS": "4", "TSAN_OPTIONS": "halt_on_error=1"})
    got = None
    for _ in range(20):
        got = call(norand + [str(exe)], RUN_TIMEOUT, env, cwd=work, limit=False)
        err = text(got.stderr)
        if "unexpected memory mapping" not in err:
            break
    else:
        return False, "TSan cannot map shadow memory"
    err = text(got.stderr)
    if "ThreadSanitizer" in err:
        detail = next((l for l in err.splitlines() if "WARNING: ThreadSanitizer" in l),
                      "ThreadSanitizer report")
        return True, detail.strip()[:200]
    if got.returncode < 0:
        return True, "TSan binary died with signal %d: %s" % (-got.returncode, first_line(got.stderr))
    if got.returncode != 0:
        return False, "exit %d: %s" % (got.returncode, first_line(got.stderr))
    return False, ""


def probe_files():
    racy = sorted((HERE / "racy").glob("*.py"))
    safe = sorted((HERE / "safe").glob("*.py"))
    hybrid = []
    for runner in sorted((HERE / "hybrid").glob("*_run.py")):
        helper = runner.with_name(runner.name[:-len("_run.py")] + ".py")
        if helper.is_file():
            hybrid.append((helper, runner))
    return racy, safe, hybrid


def evaluate(src, kind, work_root):
    work = work_root / kind / src.stem
    work.mkdir(parents=True, exist_ok=True)
    want = cpython_run(src)
    row = {"probe": "%s/%s" % (kind, src.name), "kind": kind, "cpython": want,
           "default": None, "force": None, "tsan": "", "match_default": False,
           "match_force": False, "silent": False}
    for force in (False, True):
        build = compile_probe(src, work, force)
        key = "force" if force else "default"
        got = {"path": build["path"], "note": build["note"], "runs": {},
               "match": False, "timeout": False}
        if build["path"] != "refused":
            all_match = True
            for threads in THREADS:
                runs = program_run(build["exe"], threads)
                got["runs"][threads] = runs
                if not all(matches(want, r) for r in runs):
                    all_match = False
                if any(r["timeout"] for r in runs):
                    got["timeout"] = True
            got["match"] = all_match
        row[key] = got
        if not force:
            row["match_default"] = got["match"]
            if kind == "racy":
                row["silent"] = (got["path"] == "typed parallel") or (
                    got["path"] != "refused" and not got["match"]) or got["timeout"]
        else:
            row["match_force"] = got["match"]
        if not force and got["path"] == "typed parallel":
            flagged, detail = tsan_check(build, work)
            row["tsan"] = ("REPORT: " + detail) if flagged else (detail or "clean")
            if kind == "racy" and flagged:
                row["silent"] = True
    return row


def evaluate_hybrid(helper, runner, work_root):
    work = work_root / "hybrid" / helper.stem
    work.mkdir(parents=True, exist_ok=True)
    helper_dir = helper.parent
    # Run a copy of the runner from a directory that does not hold the helper source.  Python
    # puts a script's own directory first on sys.path, so running the runner in place would
    # import the source helper and silently skip the built extension.
    driver = work / runner.name
    shutil.copyfile(runner, driver)
    want = cpython_run(driver, extra_env={"PYTHONPATH": str(helper_dir)}, cwd=work)
    row = {"probe": "hybrid/%s" % helper.name, "runner": "hybrid/%s" % runner.name,
           "kind": "hybrid", "cpython": want, "default": None, "force": None,
           "hybrid": None, "tsan": "-", "silent": False,
           "match_default": False, "match_force": False}
    # The runner is an ordinary threaded program: record its default and forced AIL result too.
    for force in (False, True):
        build = compile_probe(runner, work, force)
        key = "force" if force else "default"
        got = {"path": build["path"], "note": build["note"], "runs": {},
               "match": False, "timeout": False}
        if build["path"] != "refused":
            all_match = True
            for threads in THREADS:
                runs = program_run(build["exe"], threads,
                                   extra_env={"PYTHONPATH": str(helper_dir)})
                got["runs"][threads] = runs
                if not all(matches(want, r) for r in runs):
                    all_match = False
                if any(r["timeout"] for r in runs):
                    got["timeout"] = True
            got["match"] = all_match
        row[key] = got
        row["match_default" if not force else "match_force"] = got["match"]
    out = work / "out"
    shutil.rmtree(out, ignore_errors=True)
    env = clean_env()
    built = call([sys.executable, "-B", str(CLI), "build", "--cpython", str(helper),
                  "-o", str(out)], BUILD_TIMEOUT, env, cwd=work)
    hybrid = {"path": "hybrid", "accelerated": [], "loaded": False,
              "note": "the helper and the runner copy are separate modules", "runs": [],
              "match": False}
    if built.returncode != 0:
        hybrid = {"path": "refused", "accelerated": [], "loaded": False,
                  "note": first_line(built.stderr or built.stdout), "runs": [], "match": False}
    else:
        report_path = out / "build.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        hybrid["accelerated"] = report.get("accelerated", [])
        # Prove the run imports the generated wrapper (which binds the native module), not the
        # source helper: the same sys.path and cwd the runner gets.
        probe = ("import %s as m; print(getattr(m, '_ail_hybrid_native', None) is not None)"
                 % helper.stem)
        loaded = call([sys.executable, "-B", "-c", probe], RUN_TIMEOUT,
                      clean_env({"PYTHONPATH": str(out)}), cwd=work)
        hybrid["loaded"] = text(loaded.stdout).strip() == "True"
        got = call([sys.executable, "-B", str(driver)], RUN_TIMEOUT,
                   clean_env({"PYTHONPATH": str(out)}), cwd=work)
        hybrid["runs"] = [{"returncode": got.returncode, "stdout": got.stdout,
                           "stderr": got.stderr, "timeout": got.returncode == -9}]
        hybrid["match"] = matches(want, {"returncode": got.returncode, "stdout": got.stdout,
                                         "timeout": got.returncode == -9})
    row["hybrid"] = hybrid
    return row


def build_command(row, key):
    if row["kind"] == "hybrid":
        if key == "hybrid":
            return ("python3 AIL_CURRENT/ail_chatgpt.py build --cpython lab/race/%s "
                    "-o /tmp/race-out/%s" % (row["probe"], Path(row["probe"]).stem))
        prefix = "AIL_UNIFIED_FORCE=1 " if key == "force" else ""
        return ("%spython3 AIL_CURRENT/ail_chatgpt.py compile lab/race/%s -o /tmp/race-out/%s"
                % (prefix, row["runner"], Path(row["runner"]).stem))
    prefix = "AIL_UNIFIED_FORCE=1 " if key == "force" else ""
    return ("%spython3 AIL_CURRENT/ail_chatgpt.py compile lab/race/%s -o /tmp/race-out/%s"
            % (prefix, row["probe"], Path(row["probe"]).stem))


def write_results(rows, elapsed, args):
    racy = [r for r in rows if r["kind"] == "racy"]
    safe = [r for r in rows if r["kind"] == "safe"]
    silent = [r for r in racy if r["silent"]]
    safe_matched = [r for r in safe if r["match_default"]]
    safe_free = [r for r in safe if r["default"] and r["default"]["path"] == "typed parallel"]
    lines = []
    lines.append("# Race probe suite: measured %s" % ("today" if not args.quick else "today (quick)"))
    lines.append("")
    lines.append("`python3 lab/race/run.py`. CPython %s; the default AIL build and "
                 "`AIL_UNIFIED_FORCE=1`; hybrid probes built with `ail build --cpython`; "
                 "`AIL_THREADS` 1, 2, 4, 16, three runs each."
                 % platform.python_version())
    lines.append("")
    lines.append("## Today")
    lines.append("")
    lines.append("| count | value |")
    lines.append("|---|---|")
    lines.append("| silent races | **%d** |" % len(silent))
    lines.append("| safe matched | **%d** of %d |" % (len(safe_matched), len(safe)))
    lines.append("| safe GIL-free | **%d** of %d |" % (len(safe_free), len(safe)))
    lines.append("")
    if silent:
        lines.append("### Silent races (named first)")
        lines.append("")
        for r in silent:
            why = []
            if r["default"]["path"] == "typed parallel":
                why.append("built on the typed parallel path (shared write, no lock)")
            if not r["match_default"]:
                why.append("output differs from CPython at some AIL_THREADS")
            if r["tsan"].startswith("REPORT"):
                why.append("ThreadSanitizer: " + r["tsan"][len("REPORT: "):])
            lines.append("- `%s`: %s." % (r["probe"], "; ".join(why) or "see table"))
            lines.append("  - build: `%s`" % build_command(r, "default"))
    else:
        lines.append("No racy probe was a silent race: every one was refused by name or built on "
                     "the general path under the lock, printed CPython's output, and passed TSan "
                     "where it had a typed parallel build.")
    lines.append("")
    lines.append("## Per-probe table")
    lines.append("")
    lines.append("| probe | kind | default path | default match | force path | force match | hybrid | TSan |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        d, f, h = r["default"], r["force"], r.get("hybrid")
        if h:
            hybrid = "accelerated %s; %s; match %s" % (
                ", ".join(h.get("accelerated", [])) or "none",
                "extension loaded" if h.get("loaded") else "extension NOT loaded",
                "yes" if h.get("match") else "no")
        else:
            hybrid = "-"
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["probe"], r["kind"], d["path"] if d else "-",
            ("yes" if r["match_default"] else "no"), f["path"] if f else "-",
            ("yes" if r["match_force"] else "no"),
            hybrid, r["tsan"] or "-"))
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Paths: `typed parallel` is the lock-free `_ail_par_range` build (its C holds "
                 "`ail_par_run`); `general` is the `note: ... built on the general path ...` build "
                 "under one lock; `refused` is a compile-time refusal by name.")
    lines.append("- `force` is `AIL_UNIFIED_FORCE=1`, which the job asks for as the second build. "
                 "It forces the general path for every program, so it is a soundness check rather "
                 "than a second typed build.")
    lines.append("- A racy probe is counted silent if its default build is typed parallel, if any "
                 "run differs from CPython, or if ThreadSanitizer reports on it.")
    lines.append("- `safe GIL-free` counts safe probes whose default build is the typed parallel "
                 "path; it is the count later steps raise.")
    lines.append("- Each hybrid row is a helper module `<name>.py` built with `python3 -B "
                 "AIL_CURRENT/ail_chatgpt.py build --cpython lab/race/hybrid/<name>.py -o <out>`, "
                 "plus the threaded CPython runner `<name>_run.py`. `run.py` copies the runner to "
                 "a directory that does not hold the helper, so `import <name>` reaches the "
                 "generated wrapper and its native module; the `extension loaded` column proves "
                 "that. The runner's stdout and exit status are compared with CPython.")
    lines.append("- The default and forced columns also compile and run the same runner copy in the "
                 "ordinary AIL builds, so every row has both. Two hybrid runners build there; "
                 "`hybrid_bytearray_run.py` is refused by both with `general path: join() called "
                 "with too many positional arguments` (a `bytearray` subscript in a thread body), "
                 "so that row's match is measured from the hybrid build, where `checksum` stays in "
                 "CPython and only `tagged` is accelerated.")
    refused = [r for r in rows
               if any(r.get(k) and r[k]["path"] == "refused" for k in ("default", "force"))]
    if refused:
        lines.append("")
        lines.append("### Refusals (by name)")
        lines.append("")
        for r in refused:
            for k in ("default", "force"):
                got = r.get(k)
                if got and got["path"] == "refused":
                    note = got.get("note", "").replace(str(ROOT) + os.sep, "")
                    lines.append("- `%s` (%s): `%s`" % (r["probe"], k, note))
    lines.append("")
    lines.append("Elapsed: %.0f s. %d rows (%d racy, %d safe, %d hybrid)." % (
        elapsed, len(rows), len(racy), len(safe), len(rows) - len(racy) - len(safe)))
    lines.append("")
    (HERE / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="build and run once instead of three times")
    ap.add_argument("--out", default="", help="keep build products in this directory")
    args = ap.parse_args()
    global RUNS
    if args.quick:
        RUNS = 1
    import time
    started = time.time()
    racy, safe, hybrid = probe_files()
    rows = []
    with tempfile.TemporaryDirectory(prefix="ail-race-", dir=args.out or None) as tmp:
        work_root = Path(tmp)
        for src in racy:
            rows.append(evaluate(src, "racy", work_root))
        for src in safe:
            rows.append(evaluate(src, "safe", work_root))
        for helper, runner in hybrid:
            rows.append(evaluate_hybrid(helper, runner, work_root))
    write_results(rows, time.time() - started, args)
    silent = sum(1 for r in rows if r.get("silent"))
    safe_matched = sum(1 for r in rows if r["kind"] == "safe" and r["match_default"])
    safe_free = sum(1 for r in rows if r["kind"] == "safe" and r["default"]
                    and r["default"]["path"] == "typed parallel")
    print("silent races: %d" % silent)
    print("safe matched: %d of %d" % (safe_matched, sum(1 for r in rows if r["kind"] == "safe")))
    print("safe GIL-free: %d of %d" % (safe_free, sum(1 for r in rows if r["kind"] == "safe")))
    print("wrote", HERE / "RESULTS.md")


if __name__ == "__main__":
    main()
