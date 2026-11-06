"""Line coverage of `--debug` builds: the executable statement lines of a program (by `ast`) against the lines of
the DWARF line table (`readelf --debug-dump=decodedline`) of its `--debug` build.

    python3 lab/debug/linecov.py [--general] [PROG.py ...]     (default: every lab/debug/progs/p*.py)
    python3 lab/debug/linecov.py --gdb                         (the 30-check gdb matrix, MATRIX below)

Executable statement lines: the first line of every `ast.stmt`, except the statements that compile to no machine
code in a compiled program -- `def`/`class` headers, `import`/`from ... import`, `pass`, `global`/`nonlocal`, a
docstring, and a `try:` header (its first body statement is the first code). Decorated defs are skipped as defs.
Modules imported from the program's directory (`from helper import f`) are measured too, against their own file
name in the line table. `--general` builds with AIL_UNIFIED_FORCE=1 (the general path); otherwise `--strict` (the
typed path or a refusal; a program the typed path refuses is built on the default path and reported as such).
Prints one row per file and a total; exit status 1 when a measured typed-path file misses a line. `stray`: lines
the table names that hold no statement (a blank line, a comment: a wrong mapping), shown, not counted.
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = HERE.parent.parent / "AIL_CURRENT" / "ail_chatgpt.py"
SKIP = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Pass, ast.Global,
        ast.Nonlocal, ast.Try)


def executable_lines(path):
    """{line} of the statements that run code, by the rule in the module docstring."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docstrings.add(id(first))
    return {node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.stmt) and not isinstance(node, SKIP) and id(node) not in docstrings}


def local_imports(path):
    """The .py files beside PATH that PATH imports."""
    out = []
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        names = [node.module] if isinstance(node, ast.ImportFrom) and node.module else \
            [a.name for a in node.names] if isinstance(node, ast.Import) else []
        for name in names:
            cand = Path(path).parent / (name.replace(".", "/") + ".py")
            if cand.is_file():
                out.append(cand)
    return out


def line_table(program):
    """{(file basename, line)} of the DWARF line table, by readelf."""
    text = subprocess.run(["readelf", "--debug-dump=decodedline", str(program)], capture_output=True,
                          text=True).stdout
    found = set()
    for match in re.finditer(r"^(\S+\.py)\s+(\d+)\s", text, re.M):
        found.add((os.path.basename(match.group(1)), int(match.group(2))))
    return found


def build(source, out, general=False, strict=True):
    """Build SOURCE with --debug into OUT. Returns (ok, path name: 'typed'/'general', log)."""
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_SERVER="0", PYTHONUTF8="1")   # (a running server keeps old modules)
    env.pop("AIL_QUIET_FALLBACK", None)
    flags = ["--debug"]
    if general:
        env["AIL_UNIFIED_FORCE"] = "1"
    else:
        env.pop("AIL_UNIFIED_FORCE", None)
        if strict:
            flags.append("--strict")
    done = subprocess.run([sys.executable, "-B", str(CLI), "compile", str(source), "-o", str(out), *flags],
                          capture_output=True, text=True, env=env, cwd=str(Path(source).parent), timeout=600)
    path = "general" if general or "general path" in done.stderr else "typed"
    return done.returncode == 0, path, done.stdout + done.stderr


def measure(source, general=False, workdir=None):
    """[(file name, path, wanted lines, missing lines)] for SOURCE and the modules it imports."""
    workdir = Path(workdir or tempfile.mkdtemp(prefix="linecov-"))
    out = workdir / (Path(source).stem + ("-g" if general else "-t"))
    ok, path, log = build(source, out, general)
    if not ok and not general:   # refused by --strict: the default build decides the path
        out = out.with_name(out.name + "d")
        ok, path, log = build(source, out, False, strict=False)
    rows = []
    if not ok:
        raise RuntimeError("build failed: %s\n%s" % (source, log[-2000:]))
    table = line_table(out)
    for f in [Path(source), *local_imports(source)]:
        want = executable_lines(f)
        have = {line for name, line in table if name == f.name}
        rows.append((f.name, path, want, sorted(want - have), sorted(have - want - header_lines(f))))
    return rows


def header_lines(path):
    """Lines a line table may name besides the statements': def/class/try headers and the lines of a
    statement written over several lines."""
    out = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.stmt):
            if isinstance(node, SKIP):
                out.add(node.lineno)
            if not hasattr(node, "body"):
                out.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        elif isinstance(node, ast.ExceptHandler):
            out.add(node.lineno)
    return out


# ---------------------------------------------------------------------------------------------- the gdb matrix
# (program, break line): `break file:N`, run, then `next` five times; the lines gdb stops on must equal the
# first five line events CPython's sys.settrace reports after line N in that frame or a caller of it
STEPS = [("p01_loops.py", 3), ("p02_nested.py", 12), ("p03_method.py", 11), ("p04_comp.py", 7),
         ("p05_try.py", 2), ("p06_import.py", 5), ("p07_general.py", 8), ("p08_locals.py", 2),
         ("p09_raise.py", 7), ("p10_strings.py", 9)]


def settrace_lines(source, line, count=5):
    """The line events CPython's sys.settrace reports in SOURCE after the first time LINE runs, as gdb's `next`
    with a breakpoint on LINE would see them: in the current frame or one it returns to (a call is stepped
    over), or on LINE in any frame (the breakpoint is hit again). COUNT of them, fewer when the program ends."""
    code = r"""
import sys, runpy
target, line, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
seen, cur = [], [None]
def outer(frame):
    f = cur[0]
    while f is not None:
        if f is frame:
            return True
        f = f.f_back
    return False
def tracer(frame, event, arg):
    if event == 'line' and frame.f_code.co_filename == target and len(seen) <= count:
        if frame.f_lineno == line or (cur[0] is not None and outer(frame)):
            if cur[0] is not None or frame.f_lineno == line:
                seen.append(frame.f_lineno)
                cur[0] = frame
    return tracer
sys.argv = [target]
sys.settrace(tracer)
try:
    runpy.run_path(target, run_name='__main__')
except BaseException:
    pass
sys.settrace(None)
sys.stderr.write('LINES ' + ' '.join(map(str, seen[1:])) + chr(10))
"""
    done = subprocess.run([sys.executable, "-c", code, str(source), str(line), str(count)], capture_output=True,
                          text=True, cwd=str(Path(source).parent), timeout=120)
    found = re.search(r"^LINES ?(.*)$", done.stderr, re.M)
    return [int(x) for x in found.group(1).split()] if found else None


def gdb(program, commands):
    """stdout of `gdb -batch -x script PROGRAM` for the COMMANDS."""
    with tempfile.NamedTemporaryFile("w", suffix=".gdb", delete=False) as f:
        f.write("set pagination off\nset confirm off\n" + "\n".join(commands) + "\n")
    try:
        done = subprocess.run(["gdb", "-batch", "-nx", "-x", f.name, str(program)], capture_output=True,
                              text=True, timeout=180, stdin=subprocess.DEVNULL)
        return done.stdout + done.stderr
    finally:
        os.unlink(f.name)


def stops(text):
    """[(file name, line, function, how)] for each place gdb stopped and printed a source line, in order: HOW is
    'break' for a breakpoint hit, 'return' when gdb printed the frame of a caller (a `next` out of a function
    lands in the caller), else 'step'."""
    out, where, how = [], None, "step"
    for line in text.splitlines():
        m = re.match(r"^(Breakpoint [\d.]+, )?(?:0x\w+ in )?([\w.]+) \(.*\) at (\S+):(\d+)$", line)
        if m:
            where, func, how = os.path.basename(m.group(3)), m.group(2), "break" if m.group(1) else "return"
            continue
        m = re.match(r"^(?:warning: )?(\d+)\t", line)
        if m and where is not None:
            out.append((where, int(m.group(1)), func, how))
            how = "step"
    return out


def next_lines(got, name, calls):
    """The lines of NAME gdb's `next`s stopped on after the breakpoint, comparable with settrace_lines: a hit
    of another location of the same breakpoint on the line it stopped on is not a step (a `for` header is
    code before the loop and at each iteration), and the stop in a caller on the line of the call it returns
    from is the middle of that statement, which CPython reports no line event for. CALLS: {function: line
    of its frame in `bt` at the first hit}."""
    out, last = [], got[0][:2] if got else None
    for f, n, func, how in got[1:]:
        if how == "break" and (f, n) == last:
            continue
        last = (f, n)
        if how == "return" and calls.get(func) == n:
            continue
        if f == name:
            out.append(n)
    return out


def section(text, mark):
    """The gdb output between `echo @@MARK` and the next mark."""
    m = re.search(r"^@@%s\n(.*?)(?=^@@|\Z)" % re.escape(mark), text, re.M | re.S)
    return m.group(1) if m else ""


def matrix(workdir, progs=None):
    """[(check name, passed, detail)] of the 30 checks (fewer when PROGS restricts the step checks)."""
    workdir = Path(workdir)
    built = {}

    def exe(name):
        if name not in built:
            src = HERE / "progs" / name
            out = workdir / ("gdb-" + Path(name).stem)
            general = name == "p07_general.py"
            ok, _, log = build(src, out, general, strict=not general)
            if not ok:
                raise RuntimeError("build failed: %s\n%s" % (name, log[-2000:]))
            built[name] = out
        return built[name]

    checks = []
    for name, line in STEPS:
        if progs is not None and name not in progs:
            continue
        text = gdb(exe(name), ["break %s:%d" % (name, line), "run", "echo @@bt\\n", "bt", "echo @@next\\n"]
                   + ["next"] * 10)
        calls = {fn: int(n) for fn, n in re.findall(r"^#\d+\s+(?:0x\w+ in )?(\w+) \(.*\) at \S+:(\d+)$",
                                                     section(text, "bt"), re.M)}
        got = stops(text.split("@@bt")[0] + text.split("@@next\n", 1)[-1])
        checks.append(("break %s:%d" % (name, line), got[:1] and got[0][:2] == (name, line), "stops %s" % got[:1]))
        want = settrace_lines(HERE / "progs" / name, line)
        seen = next_lines(got, name, calls)[:len(want or ())]
        checks.append(("next x5 %s:%d" % (name, line), bool(want) and seen == want,
                       "gdb %s, settrace %s" % (seen, want)))
    if progs is not None and "p02_nested.py" not in progs:
        return checks
    # a call 3 deep: inner <- middle <- outer <- main
    text = gdb(exe("p02_nested.py"), ["break p02_nested.py:2", "run", "bt"])
    frames = re.findall(r"^#\d+\s+(?:0x\w+ in )?(\w+) \(.*?\) at (\S+)$", text, re.M)
    user = [(fn, os.path.basename(at)) for fn, at in frames if fn not in ("main", "run")]
    checks.append(("bt 3 deep: inner:2 middle:7 outer:12 main:17, each file.py:N",
                   bool(user) and all(re.fullmatch(r"p02_nested\.py:\d+", at) for _, at in user)
                   and user[:4] == [("inner", "p02_nested.py:2"), ("middle", "p02_nested.py:7"),
                                    ("outer", "p02_nested.py:12"), ("py_main", "p02_nested.py:17")], str(user)))
    text = gdb(exe("p02_nested.py"), ["break p02_nested.py:3", "run", "finish"])
    back = re.search(r"^middle \(.*\) at \S*p02_nested\.py:7$", text, re.M) is not None
    value = re.search(r"^Value returned is \$\d+ = (\S+)$", text, re.M)
    checks.append(("finish from inner returns to middle:7 with 11", back and bool(value) and value.group(1) == "11",
                   "back in middle:7 %s, value %s" % (back, value.group(1) if value else "not shown")))
    # locals: an int and a float, by their Python names
    # (one gdb run each: an error in a `-x` script, `No symbol "k"`, ends the script)
    text = gdb(exe("p08_locals.py"), ["break p08_locals.py:5", "run", "echo @@locals\\n", "info locals"])
    names = re.findall(r"^(\w+) = ", section(text, "locals"), re.M)
    checks.append(("info locals names k, g, r", {"k", "g", "r"} <= set(names), " ".join(names)))
    for var, val in (("n", "42"), ("f", "1.5"), ("k", "43"), ("g", "3")):
        text = gdb(exe("p08_locals.py"), ["break p08_locals.py:5", "run", "echo @@print\\n", "print " + var])
        out = section(text, "print").strip()
        missing = re.search(r'No symbol "\w+" in current context', out)
        out = missing.group(0) if missing else out
        checks.append(("print %s == %s" % (var, val), re.fullmatch(r"\$\d+ = %s" % re.escape(val), out) is not None,
                       out[:60]))
    # an IndexError: a breakpoint on the runtime's raise function
    text = gdb(exe("p09_raise.py"), ["break ail_die", "run", "bt"])
    checks.append(("IndexError stops in ail_die", re.search(r"^Breakpoint \d+, ail_die \(", text, re.M) is not None,
                   "list index out of range" in text and "message shown" or text[-200:]))
    checks.append(("IndexError bt names p09_raise.py:2 in pick",
                   re.search(r"\bpick \(.*\) at \S*p09_raise\.py:2$", text, re.M) is not None, ""))
    # an imported module's line
    text = gdb(exe("p06_import.py"), ["break p06_helper.py:2", "run", "bt 2"])
    checks.append(("break in the imported module p06_helper.py:2",
                   re.search(r"scale \(.*\) at \S*p06_helper\.py:2$", text, re.M) is not None, ""))
    return checks


def main(argv):
    if "--gdb" in argv:
        print("gdb: " + subprocess.run(["gdb", "--version"], capture_output=True, text=True).stdout.splitlines()[0])
        with tempfile.TemporaryDirectory(prefix="gdbmatrix-") as tmp:
            checks = matrix(tmp)
        for name, ok, detail in checks:
            print("%-4s %-50s %s" % ("ok" if ok else "FAIL", name, detail))
        print("gdb checks %d/%d" % (sum(ok for _, ok, _ in checks), len(checks)))
        return 0
    general = "--general" in argv
    progs = [Path(a) for a in argv if not a.startswith("--")] or sorted((HERE / "progs").glob("p[0-9][0-9]_*.py"))
    progs = [p for p in progs if not p.stem.endswith("_helper")]
    tot_want = tot_have = 0
    typed_missing = 0
    with tempfile.TemporaryDirectory(prefix="linecov-") as tmp:
        for prog in progs:
            for name, path, want, missing, stray in measure(prog, general, tmp):
                tot_want += len(want)
                tot_have += len(want) - len(missing)
                if path == "typed":
                    typed_missing += len(missing)
                print("%-18s %-7s %3d/%-3d missing: %-10s stray: %s" % (
                    name, path, len(want) - len(missing), len(want), missing or "-", stray or "-"))
    print("total %d/%d (%.1f%%)" % (tot_have, tot_want, 100.0 * tot_have / max(tot_want, 1)))
    return 1 if typed_missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
