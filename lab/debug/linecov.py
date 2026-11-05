#!/usr/bin/env python3
"""Line coverage of a `--debug` build: the executable statement lines of a program, against the DWARF line table.

An *executable statement line* is the `lineno` of every Python statement in the file's AST, minus a `def`/`class`
header (the line the body's prologue would sit on, but a function with no tagged local has no prologue code
there), a bare string (a docstring), `pass`, `global`/`nonlocal` and `import`/`from ... import` (resolved when
the program is built, so it emits no code) -- the lines a `sys.settrace` line event visits in CPython that a
compiled program can point at.  The line table is read from the built executable with
`readelf --debug-dump=decodedline` (or `objdump --dwarf=decodedline`); a line covers a statement if the
table names `file.py:N` anywhere.

    python3 lab/debug/linecov.py PROG.py [PROG2.py ...]   # build each, report, exit 1 below --threshold
    python3 lab/debug/linecov.py --all                    # every lab/debug/progs/*.py except helper modules
    python3 lab/debug/linecov.py PROG.py --exe EXE        # measure an already-built --debug executable

Only the typed path is held to 100%; the general path (pyboxed2) is measured and reported but its known gaps are
follow-ups (RESULTS.md), so `--exe`/`--all` still print the number and the missing lines.
"""
import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CLI = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
PROGS = HERE / "progs"
HELPER_MODULES = {"helper.py"}          # imported by another program, not run on its own


def executable_lines(path):
    """{line: statement text} for the executable statement lines of a Python file."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    classes = {id(inner) for outer in ast.walk(tree) if isinstance(outer, ast.ClassDef)
               for inner in outer.body}
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt) or not hasattr(node, "lineno"):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            continue                                   # a docstring
        if isinstance(node, (ast.Pass, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.AnnAssign) and node.value is None:
            continue                                   # `x: int`: a declaration, no code
        if isinstance(node, ast.AnnAssign) and id(node) in classes:
            continue                                   # a dataclass field: class metadata, no code
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            continue
        out.setdefault(node.lineno, ast.unparse(node).splitlines()[0])
    return out


def line_table(exe):
    """{(basename, line)} from the DWARF line table of `exe`, or None without readelf/objdump."""
    for tool, args in (("readelf", ["--debug-dump=decodedline"]), ("objdump", ["--dwarf=decodedline"])):
        if not shutil.which(tool):
            continue
        text = subprocess.run([tool, *args, str(exe)], capture_output=True, text=True, timeout=300).stdout
        found = set()
        for match in re.finditer(r"^(\S+\.py)\s+(\d+)\s+0x", text, re.M):
            found.add((os.path.basename(match.group(1)), int(match.group(2))))
        if found:
            return found
    return None


def build(source, exe, debug=True):
    env = dict(os.environ, PYTHONUTF8="1", AIL_CACHE=str(Path(exe).parent / "cache"))
    for name in ("AIL_QUIET_FALLBACK", "AIL_NO_CACHE", "AIL_IR", "AIL_LINE_MAP"):
        env.pop(name, None)
    flags = ["--debug"] if debug else []
    done = subprocess.run([sys.executable, "-B", str(CLI), "compile", *flags, str(source), "-o", str(exe)],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=900)
    if done.returncode != 0:
        raise SystemExit("build failed for %s:\n%s%s" % (source, done.stdout, done.stderr))
    return done


def sources_for(program):
    """The program plus the sibling modules it imports (so an imported module's lines count too)."""
    program = Path(program)
    tree = ast.parse(program.read_text(encoding="utf-8"))
    names = {program}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(program.parent / (node.module.split(".")[0] + ".py"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(program.parent / (alias.name.split(".")[0] + ".py"))
    return [p for p in names if p.is_file()]


def measure(program, exe=None):
    """(total, covered, missing [(file, line, text)], table) for one program."""
    files = sources_for(program)
    table = line_table(exe) if exe else None
    total, covered, missing = 0, 0, []
    for path in sorted(files):
        lines = executable_lines(path)
        for line, text in sorted(lines.items()):
            total += 1
            if table is not None and (path.name, line) in table:
                covered += 1
            else:
                missing.append((path.name, line, text))
    return total, covered, missing, table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("programs", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true", help="every program in lab/debug/progs")
    parser.add_argument("--exe", type=Path, help="an already-built --debug executable (single program)")
    parser.add_argument("--threshold", type=float, default=100.0, help="fail below this percentage")
    parser.add_argument("--general", action="store_true", help="this program is on the general path (no 100%% rule)")
    args = parser.parse_args(argv)

    programs = list(args.programs)
    if args.all:
        programs += sorted(p for p in PROGS.glob("*.py") if p.name not in HELPER_MODULES)
    if not programs:
        parser.error("give a program or --all")

    failures = 0
    with tempfile.TemporaryDirectory(prefix="ail-linecov-") as tmp:
        for program in programs:
            exe = args.exe if args.exe and len(programs) == 1 else Path(tmp) / (program.stem + ".exe")
            built = args.exe is None
            if built:
                done = build(program, exe)
                general = "general path" in (done.stderr or "")
            else:
                general = args.general
            total, covered, missing, table = measure(program, exe=exe)
            if table is None:
                print("%s: no readelf/objdump, cannot measure" % program.name)
                return 2
            pct = 100.0 * covered / total if total else 100.0
            print("%s: %d/%d lines (%.1f%%)%s" % (program.name, covered, total, pct,
                                                  "  [general path]" if general else ""))
            for name, line, text in missing:
                print("    missing %s:%d  %s" % (name, line, text))
            if pct < args.threshold and not (general or args.general):
                failures += 1
            if built:
                exe.unlink(missing_ok=True)
                shutil.rmtree(exe.parent / "cache", ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
