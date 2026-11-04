#!/usr/bin/env python3
"""Measure how much of a real library `ail_bindgen.py` covers from its installed header.

    python3 examples/ffi/bindgen/measure.py            # the default parser
    python3 examples/ffi/bindgen/measure.py --cpp      # with --cpp (preprocess the header first)

For each library the denominator is the set of exported functions that the header declares:

  zlib   the `T` symbols of `libz.so.1` (`nm -D --defined-only`) whose name appears in `zlib.h`;
  libm   the `math.h` functions that take only `double` parameters and return `double`, kept
         only when `nm -D` shows the name in `libm.so.6`.

The numerator is what a compiler accepts: every `@extern` stub the generator writes is put in a
small program on its own, with a call whose arguments follow the stub's annotations, and the
program is compiled with `ail_chatgpt.py compile`. The header check (`_Static_assert(_Generic(
&symbol, ...))` in the adapter C file, ail_ffi_lower.py) runs for every declaration in the module,
so one stub per program is what turns a build failure into a statement about that stub. Groups of
stubs are tried together and split on failure, so a run needs few builds when most are accepted.

Nothing here writes outside a temporary directory.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
ROOT = REPO / "AIL_CURRENT"
CLI = ROOT / "ail_chatgpt.py"
BINDGEN = ROOT / "ail_bindgen.py"
CC = None

SKIP = re.compile(r'^# skipped (\w+): (.*)$')
STUB = re.compile(r'@extern\([^)]*\)\n(def \w+\(.*?\) -> [^:]+): \.\.\.', re.S)


def run(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, **kw)


def preprocess(header, extra=()):
    """The `cc -E` text of `#include <header>`, with the `# N "file"` marker lines dropped."""
    done = run([CC, "-E", "-x", "c", "-", *extra], input="#include <%s>\n" % header)
    if done.returncode:
        raise SystemExit("cc -E %s failed:\n%s" % (header, done.stderr))
    return "\n".join(line for line in done.stdout.splitlines() if not line.startswith("#"))


def library(soname):
    """The path of a shared library, through the compiler's own search path."""
    done = run([CC, "-print-file-name=%s" % soname])
    path = Path(done.stdout.strip())
    if done.returncode == 0 and path.is_absolute() and path.is_file():
        return path
    import ctypes.util
    found = ctypes.util.find_library(soname.split(".")[0][3:])
    return Path(found) if found else None


def nm(path, only_t=False):
    done = run(["nm", "-D", "--defined-only", str(path)])
    names = set()
    for line in done.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        kind, name = parts[1], parts[2].split("@")[0]
        if kind == "A" or (only_t and kind != "T"):
            continue
        names.add(name)
    return names


def zlib_denominator():
    lib = library("libz.so.1")
    if lib is None:
        return None
    text = Path("/usr/include/zlib.h").read_text(encoding="utf-8", errors="replace")
    return {n for n in nm(lib, only_t=True) if re.search(r"\b%s\s*\(" % re.escape(n), text)}


DOUBLE_DECL = re.compile(r"extern\s+double\s+([A-Za-z_]\w*)\s*\(([^()]*)\)[^;]*;")


def libm_denominator():
    lib = library("libm.so.6")
    if lib is None:
        return None
    text = re.sub(r"\s+", " ", preprocess("math.h"))
    names = set()
    for match in DOUBLE_DECL.finditer(text):
        name, params = match.group(1), match.group(2).strip()
        if name.startswith("__"):
            continue
        params = [] if params in ("", "void") else [p.strip() for p in params.split(",")]
        if all(re.fullmatch(r"double(\s+\w+)?", p) for p in params):
            names.add(name)
    return names & nm(lib)


def generate(header, cpp, link):
    """Run ail_bindgen.py and split its output into stub blocks and skip reasons."""
    with tempfile.TemporaryDirectory(prefix="ail-bindgen-measure-") as directory:
        out = Path(directory) / "stubs.py"
        argv = [sys.executable, "-B", str(BINDGEN), header, "--header-name", Path(header).name,
                "--link", link, "-o", str(out)]
        if cpp:
            argv.append("--cpp")
        done = run(argv)
        if done.returncode:
            raise SystemExit("ail_bindgen.py failed:\n" + done.stderr)
        text = out.read_text(encoding="utf-8")
    blocks, skipped = [], []
    for line in text.splitlines():
        match = SKIP.match(line)
        if match:
            skipped.append(match.group(2))
    for match in STUB.finditer(text):
        block = match.group(0).replace("\n", "\n", 1)
        name = re.search(r"def (\w+)\(", match.group(1)).group(1)
        blocks.append((name, block))
    return blocks, skipped


ARGUMENTS = {
    "c_bool": "False",
    "c_double": "0.0", "c_float": "0.0",
    "c_char_p": 'b""', "c_mut_char_p": 'b""',
    "bytes": 'b""', "c_const_void_p": 'b""',
    "bytearray": "bytearray(64)", "c_mut_void_p": "bytearray(64)",
    "c_void_p": "0",
}


def split_params(text):
    parts, depth, current, quote = [], 0, [], None
    for ch in text:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return parts


def call_line(name, definition):
    """A call of `name` with one simple value per parameter; None when the types defeat the table."""
    inside = definition[definition.index("(") + 1:definition.rindex(")")]
    args = []
    for param in split_params(inside):
        if not param:
            continue
        annotation = param.split(":", 1)[1].strip() if ":" in param else ""
        if annotation.startswith("length("):
            continue                     # the length is taken from the buffer argument
        if annotation in ARGUMENTS:
            args.append(ARGUMENTS[annotation])
        elif annotation in ("ptr(c_void_p)", "cptr(c_void_p)") or re.fullmatch(r"(c?ptr)\(c_\w+\)", annotation):
            args.append("bytearray(64)")
        elif annotation.startswith("c_"):
            args.append("0")
        else:
            return None
    return "%s(%s)" % (name, ", ".join(args))


def build_probe(work, blocks):
    """Compile one program holding `blocks` and calling each; (ok, last error line)."""
    lines = ["from ail_ffi import *", "link(%r)" % work["link"], ""]
    calls = []
    for _, block in blocks:
        lines.append(block)
        lines.append("")
        name = re.search(r"def (\w+)\(", block).group(1)
        call = call_line(name, block)
        if call is not None:
            calls.append(call)
    if not calls:
        calls.append("print()")
    lines.append("")
    lines.append("def main():")
    lines.extend("    %s" % c for c in calls)
    lines.extend(["", "main()", ""])
    work["counter"] += 1
    source = work["dir"] / ("probe%d.py" % work["counter"])
    out = work["dir"] / ("probe%d.out" % work["counter"])
    source.write_text("\n".join(lines), encoding="utf-8")
    done = run([sys.executable, "-B", str(CLI), "compile", str(source), "-o", str(out)],
               timeout=300, env=dict(__import__("os").environ, AIL_NO_CACHE="1"))
    if done.returncode == 0:
        return True, None
    tail = [l for l in (done.stderr or done.stdout).strip().splitlines() if l.strip()]
    return False, (tail[-1] if tail else "build failed")


def probe(work, blocks, accepted, rejected):
    """Bisect: a group that builds is all accepted; a single failure is that stub's reason."""
    if not blocks:
        return
    ok, error = build_probe(work, blocks)
    if ok:
        accepted.extend(name for name, _ in blocks)
    elif len(blocks) == 1:
        rejected.append((blocks[0][0], error))
    else:
        middle = len(blocks) // 2
        probe(work, blocks[:middle], accepted, rejected)
        probe(work, blocks[middle:], accepted, rejected)


def measure(name, header, denominator, cpp):
    blocks, skipped = generate(header, cpp, "z" if name == "zlib" else "m")
    relevant = [(n, b) for n, b in blocks if n in denominator]
    work = dict(dir=Path(tempfile.mkdtemp(prefix="ail-bindgen-probes-")), link="z" if name == "zlib" else "m",
                counter=0)
    accepted, rejected = [], []
    try:
        probe(work, relevant, accepted, rejected)
    finally:
        shutil.rmtree(work["dir"], ignore_errors=True)
    return dict(name=name, denominator=len(denominator), emitted=len(relevant), accepted=len(accepted),
                extra=len(blocks) - len(relevant), skipped=skipped, rejected=rejected)


def table(rows):
    out = ["| library | denominator | emitted | accepted | share |", "|---|---|---|---|---|"]
    for row in rows:
        share = 100.0 * row["accepted"] / row["denominator"] if row["denominator"] else 0.0
        out.append("| %s | %d | %d | %d | %.1f%% |" % (row["name"], row["denominator"], row["emitted"],
                                                       row["accepted"], share))
    return "\n".join(out)


def main(argv=None):
    global CC
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cpp", action="store_true", help="pass --cpp to ail_bindgen.py")
    args = ap.parse_args(argv)
    CC = __import__("os").environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
    if not CC:
        raise SystemExit("no C compiler (set PIPE_CC)")
    rows = []
    for name, header, find in (("zlib", "/usr/include/zlib.h", zlib_denominator),
                               ("libm", "/usr/include/math.h", libm_denominator)):
        if not Path(header).is_file():
            print("%s: %s is not installed, skipped" % (name, header), file=sys.stderr)
            continue
        denominator = find()
        if not denominator:
            print("%s: no lib%s.so.1, skipped" % (name, name[-1]), file=sys.stderr)
            continue
        rows.append(measure(name, header, denominator, args.cpp))
    print(table(rows))
    print()
    for row in rows:
        reasons = {}
        for reason in row["skipped"]:
            key = re.sub(r"'[^']*'", "'...'", reason)
            reasons[key] = reasons.get(key, 0) + 1
        print("%s: %d stubs outside the denominator (%s)" % (row["name"], row["extra"],
              "float/long double variants of math.h" if row["name"] == "libm" else "none"))
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1])[:6]:
            print("  skipped %4d  %s" % (count, reason))
        for name, error in row["rejected"][:8]:
            print("  rejected %-20s %s" % (name, error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
