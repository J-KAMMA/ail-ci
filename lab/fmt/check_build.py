"""Prove that formatting an AIL source does not change its build, its output or its refusal.

Sixty programs (the ten `lab/compare/src` programs, then files spread over `lab/stdlib/*/`,
`lab/errux/progs/` and `lab/safety/`) are copied to `prog.py` in a throwaway directory and built
from that same path; then the copy is formatted in place with `ruff format` (or `black` when ruff
is absent) and built again from the same path.  Building both from one path matters: the generated
C embeds `__file__`, so two directories would differ for reasons that are not formatting.  Both
builds use

    python3 -B AIL_CURRENT/ail_chatgpt.py compile prog.py -o prog --debug-dir debug_orig
    python3 -B AIL_CURRENT/ail_chatgpt.py compile prog.py -o prog --debug-dir debug_fmt

and compared:

* `debug/program.c` after removing source line numbers (`#line` directives and the line argument of
  `AIL_DBG_SITE`),
* stdout and the exit status of the two executables on the same stdin (the first public case of the
  task for `lab/compare/src`, empty stdin otherwise),
* the refusal text with line and column numbers removed, when the compiler refuses.

It also checks that `# ail: gpu` and a PEP 263 coding line survive formatting, and that
`python3 -m ail_lang.fmt --check` gives the same answer as `ruff format --check` on all sixty.
Nothing outside a temporary directory is written; `lab/fmt/RESULTS.md` is the only file written in
the repository.

Usage (from the repository root, with ruff or black on PATH):

    python3 lab/fmt/check_build.py

Exit status is 0 when all sixty keep their C, output and refusal and all sixty check answers agree.
"""
import importlib.util
import json
import os
import random
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "RESULTS.md"
COMPILER = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
PACKAGING = ROOT / "packaging"
PYTHON = sys.executable
LIMIT_KB = 1_500_000
BUILD_TIMEOUT = 600
RUN_TIMEOUT = 20
WORKERS = 2
QUOTA = {"compare": 10, "stdlib": 20, "errux": 15, "safety": 15}

LINE_DIRECTIVE = re.compile(r"^[ \t]*#line[ \t]+\d+.*$", re.M)
DBG_SITE = re.compile(r'AIL_DBG_SITE\("([^"\n]*):\d+"\)')
REFUSAL_POSITION = re.compile(r"(?<=\.py):\d+(?::\d+)?")
TEXT_LINE = re.compile(r"\bline \d+\b")


def limit_memory():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (LIMIT_KB * 1024, LIMIT_KB * 1024))
    except (ImportError, ValueError, OSError):
        pass


def formatter():
    for name, command in (("ruff", ["ruff", "format"]), ("black", ["black"])):
        path = shutil.which(name)
        if path:
            return name, [path] + command[1:], subprocess.run([path, "--version"], capture_output=True,
                                                             text=True).stdout.strip()
    return None, None, None


def spread(paths, count):
    """Round-robin over the parent directories, so a quota covers many libraries (deterministic)."""
    groups = {}
    for path in sorted(paths):
        groups.setdefault(path.parent, []).append(path)
    picked, index = [], 0
    while len(picked) < count:
        added = False
        for group in groups.values():
            if index < len(group):
                picked.append(group[index])
                added = True
                if len(picked) >= count:
                    break
        if not added:
            break
        index += 1
    return picked


def select_programs():
    compare = sorted((ROOT / "lab/compare/src").glob("*/typed.py"))
    stdlib = spread([p for p in (ROOT / "lab/stdlib").glob("*/*.py")], QUOTA["stdlib"])
    errux = spread([p for p in (ROOT / "lab/errux/progs").glob("*.py")], QUOTA["errux"])
    safety = spread([p for p in (ROOT / "lab/safety").glob("*/*.py") if p.name != "run.py"], QUOTA["safety"])
    programs = [("compare", p, public_stdin(p.parent.name)) for p in compare]
    programs += [("stdlib", p, b"") for p in stdlib]
    programs += [("errux", p, b"") for p in errux]
    programs += [("safety", p, b"") for p in safety]
    return programs


def public_stdin(task):
    """The first public case of `lab/compare/tasks/<task>/gen.py`, as bytes."""
    path = ROOT / "lab/compare/tasks" / task / "gen.py"
    if not path.is_file():
        return b""
    spec = importlib.util.spec_from_file_location("fmt_gen_" + task, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    public, _hidden, _perf = module.cases(random.Random(0))
    return public[0][1]


def run(command, cwd, stdin, timeout):
    start = time.time()
    try:
        done = subprocess.run(command, cwd=str(cwd), input=stdin, capture_output=True, timeout=timeout)
        return done.returncode, done.stdout, done.stderr, time.time() - start, False
    except subprocess.TimeoutExpired as expired:
        return None, expired.stdout or b"", expired.stderr or b"", time.time() - start, True


def normalize_c(text, directory):
    text = LINE_DIRECTIVE.sub("", text)
    text = DBG_SITE.sub(lambda found: 'AIL_DBG_SITE("%s")' % found.group(1), text)
    return text.replace(str(directory), "<dir>")


def normalize_refusal(text, directory):
    text = text.replace(str(directory), "<dir>")
    text = REFUSAL_POSITION.sub(":<loc>", text)
    return TEXT_LINE.sub("line <n>", text)


def refusal_text(stderr):
    lines = [line for line in stderr.decode("utf-8", "replace").splitlines()
             if line.strip() and not line.strip().startswith("note:")]
    return "\n".join(lines)


def run_case(kind, source, stdin, work, tool):
    """Copy, format, build and compare one program. Returns a per-program record."""
    name = "%s/%s" % (source.parent.name, source.name) if kind != "errux" else "errux/" + source.name
    record = {"kind": kind, "name": name, "source": str(source.relative_to(ROOT)), "formatted": None,
              "c": "-", "run": "-", "ok": False, "note": ""}
    text = source.read_bytes()
    program = work / "prog.py"
    program.write_bytes(text)

    def build(label):
        rc, out, err, _elapsed, timed_out = run(
            [PYTHON, "-B", str(COMPILER), "compile", "prog.py", "-o", "prog",
             "--debug-dir", "debug_" + label],
            work, b"", BUILD_TIMEOUT)
        return {"rc": rc, "stdout": out, "stderr": err, "timed_out": timed_out,
                "fallback": b"general path" in err,
                "c": (work / ("debug_" + label) / "program.c")}

    left = build("orig")
    if left["timed_out"]:
        record["note"] = "build of the original timed out"
        return record
    if left["rc"] == 0:
        shutil.copy2(work / "prog", work / "prog_orig")
        (work / "prog").unlink()

    format_rc, _format_out, format_err, _elapsed, timed_out = run(tool + ["prog.py"], work, b"", 300)
    if timed_out or format_rc is None:
        record["note"] = "formatter timed out"
        return record
    if format_rc >= 2:
        record["note"] = "formatter failed: " + format_err.decode("utf-8", "replace").strip()[:200]
        return record
    record["formatted"] = program.read_bytes() != text

    right = build("fmt")
    if right["timed_out"]:
        record["note"] = "build of the formatted copy timed out"
        return record
    if left["rc"] != right["rc"]:
        record["note"] = "build status differs: %s vs %s" % (left["rc"], right["rc"])
        return record
    if left["rc"] != 0:
        left_text = normalize_refusal(refusal_text(left["stderr"]), work)
        right_text = normalize_refusal(refusal_text(right["stderr"]), work)
        record["run"] = "refusal"
        if left_text != right_text:
            record["note"] = "refusal differs:\n  %s\n  %s" % (left_text, right_text)
            return record
        record["ok"] = True
        record["c"] = "n/a"
        return record

    if left["fallback"] != right["fallback"]:
        record["note"] = "fallback note differs"
        return record
    if not left["c"].is_file() or not right["c"].is_file():
        record["note"] = "no program.c in the debug directory"
        return record
    c_left = left["c"].read_text(encoding="utf-8", errors="replace")
    c_right = right["c"].read_text(encoding="utf-8", errors="replace")
    if normalize_c(c_left, work) != normalize_c(c_right, work):
        record["c"] = "CHANGED"
        record["note"] = "program.c differs"
        return record
    record["c"] = "same"

    left_run = run([str(work / "prog_orig")], work, stdin, RUN_TIMEOUT)
    right_run = run([str(work / "prog")], work, stdin, RUN_TIMEOUT)
    if left_run[4] or right_run[4]:
        record["run"] = "timeout"
        record["note"] = "run timed out"
        return record
    if left_run[0] != right_run[0] or left_run[1] != right_run[1]:
        record["run"] = "CHANGED"
        record["note"] = "exit %s/%s, stdout %d/%d bytes" % (left_run[0], right_run[0],
                                                             len(left_run[1]), len(right_run[1]))
        return record
    record["run"] = "same"
    record["ok"] = True
    return record


def check_mode_agreement(programs, tool):
    """`ail fmt --check` answers must equal `ruff format --check` on all sixty programs."""
    rows = []
    for _kind, source, _stdin in programs:
        ruff = run(tool + ["--check", str(source)], ROOT, b"", 120)
        fmt = run([PYTHON, "-m", "ail_lang.fmt", "--check", str(source)], PACKAGING, b"", 120)
        ruff_answer = {0: "formatted", 1: "would change"}.get(ruff[0], "error %s" % ruff[0])
        fmt_answer = {0: "formatted", 1: "would change"}.get(fmt[0], "error %s" % fmt[0])
        rows.append((source.relative_to(ROOT), ruff_answer, fmt_answer, ruff_answer == fmt_answer))
    return rows


def marker_check(tool, work):
    """`# ail: gpu` and a PEP 263 coding line must survive formatting."""
    program = work / "markers.py"
    program.write_text(
        "# -*- coding: utf-8 -*-\n"
        "def squares(a: list[float]) -> list[float]:\n"
        "    # ail: gpu\n"
        "    ys = [x * x - 1.0 for x in a]  # ail: gpu\n"
        "    return ys\n", encoding="utf-8")
    rc, _out, err, _elapsed, _timed = run(tool + ["markers.py"], work, b"", 120)
    text = program.read_text(encoding="utf-8")
    return {"rc": rc, "error": err.decode("utf-8", "replace").strip(),
            "coding": text.splitlines()[0].lower().replace(" ", "") == "#-*-coding:utf-8-*-",
            "gpu": text.count("# ail: gpu") == 2, "text": text}


def main():
    limit_memory()
    name, tool, version = formatter()
    if not name:
        print("no ruff or black on PATH", file=sys.stderr)
        return 2
    programs = select_programs()
    if len(programs) != 60:
        print("expected 60 programs, selected %d" % len(programs), file=sys.stderr)
        return 2
    work_root = Path(tempfile.mkdtemp(prefix="ail-fmt-build-"))
    records = []
    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = []
            for index, (kind, source, stdin) in enumerate(programs):
                directory = work_root / ("p%02d" % index)
                directory.mkdir()
                futures.append(pool.submit(run_case, kind, source, stdin, directory, tool))
            for future in futures:
                records.append(future.result())
        markers = marker_check(tool, work_root)
        agreement = check_mode_agreement(programs, tool)
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    changed = [r for r in records if not r["ok"]]
    agree = sum(1 for row in agreement if row[3])
    marker_ok = markers["coding"] and markers["gpu"]
    total = len(records)
    lines = [
        "# Formatting does not change the build",
        "",
        "Generated by `python3 lab/fmt/check_build.py` on %s." % time.strftime("%Y-%m-%d"),
        "",
        "Formatter pin: `%s` (`%s`). The test venv is throwaway; neither formatter is a dependency." %
        (version, name),
        "",
        "Selection: %d programs (the ten `lab/compare/src` programs and a round-robin spread over "
        "`lab/stdlib/*/`, `lab/errux/progs/` and `lab/safety/`)." % total,
        "",
        "| # | program | rewritten | program.c | stdout + status | verdict |",
        "|---:|---|---|---|---|---|",
    ]
    for index, record in enumerate(records, 1):
        verdict = "same" if record["ok"] else "**FAIL: %s**" % record["note"].replace("\n", " ")
        lines.append("| %d | `%s` | %s | %s | %s | %s |" % (
            index, record["source"], "yes" if record["formatted"] else "no",
            record["c"], record["run"], verdict))
    lines += [
        "",
        "## Result",
        "",
        "* **%d of %d** programs changed their generated C, stdout or exit status, or their refusal text."
        % (len(changed), total),
        "* **%d of %d** `ail fmt --check` answers equal `%s format --check`." % (agree, len(agreement), name),
        "* `# ail: gpu` and the PEP 263 coding line survive formatting: **%s**."
        % ("yes" if marker_ok else "NO"),
        "",
        "```",
        markers["text"].rstrip(),
        "```",
        "",
        "## Check-mode agreement",
        "",
        "| program | `%s format --check` | `ail fmt --check` | equal |" % name,
        "|---|---|---|---|",
    ]
    for source, ruff_answer, fmt_answer, equal in agreement:
        lines.append("| `%s` | %s | %s | %s |" % (source, ruff_answer, fmt_answer, "yes" if equal else "**no**"))
    lines.append("")

    if changed:
        lines += ["## Failures", ""]
        for record in changed:
            lines += ["### `%s`" % record["source"], "", "```", record["note"], "```", ""]
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print("C/output/refusal changed: %d of %d" % (len(changed), total))
    print("check answers equal: %d of %d" % (agree, len(agreement)))
    print("markers: coding=%s gpu=%s" % (markers["coding"], markers["gpu"]))
    if changed or agree != len(agreement) or not marker_ok:
        for record in changed:
            print("FAIL %s: %s" % (record["source"], record["note"].replace("\n", " ")))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
