#!/usr/bin/env bash
# Where AIL's decode time goes: top 10 C functions with their share.
#
#   bash lab/infer/profile.sh [WORK] [STEPS]
#
# The profile is decode-only.  gpt2.py loads and decodes the f32 weights before
# its first forward, and at -O0 that loader is more than half of a short run,
# so the same program is profiled twice - once with an empty prompt (load
# only) and once with a one-token prompt plus STEPS (default 4) decode forwards
# - and the load-only counts are subtracted.  Every forward in the remaining
# profile is one of the two one-token forwards the benchmark measures.
#
# perf record -g is used when the kernel allows it (the GitHub runner does not:
# perf_event_paranoid=4); otherwise the run is replayed under
# valgrind --tool=callgrind.  The profile is taken on the --debug build (-g -O0,
# #line back to gpt2.py), which is what ties a C function to its AIL function.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
WORK="${1:-${RUNNER_TEMP:-/tmp}/ail-infer}"
STEPS="${2:-4}"
# valgrind's shadow memory sits on top of the program's ~1.1 GiB of doubles.
MEM_KB="${MEM_KB:-3000000}"

die() { echo "profile: $*" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [ -d "$WORK/exported" ] && [ -x "$WORK/llama-azoo/build/bin/llama-tokenize" ]; then
    echo "== weights already in $WORK (skip fetch.sh)"
else
    echo "== fetch weights and llama.cpp (idempotent)"
    bash "$HERE/fetch.sh" "$WORK" >"$TMP/fetch.log" 2>&1 \
        || { tail -20 "$TMP/fetch.log" >&2; die "fetch.sh failed"; }
fi
DATA="$WORK/exported"

echo "== build AIL --debug (line table back to gpt2.py, -g -O0)"
rm -f "$WORK/gpt2-debug"
rm -rf "$WORK/debug"
python3 -B "$ROOT/AIL_CURRENT/ail_chatgpt.py" compile "$HERE/gpt2.py" -o "$WORK/gpt2-debug" \
    --debug --debug-dir "$WORK/debug" >"$TMP/ail-debug.log" 2>&1 \
    || { cat "$TMP/ail-debug.log" >&2; die "--debug build failed"; }
[ -f "$WORK/debug/program.c" ] || die "--debug build wrote no $WORK/debug/program.c"

head -1 "$HERE/tokens.txt" >"$TMP/one.txt"
: >"$TMP/empty.txt"

MODE=""
if perf record -g -o "$TMP/probe.perf" -- true >/dev/null 2>"$TMP/perf-probe.err"; then
    MODE=perf
else
    echo "   perf unavailable ($(head -1 "$TMP/perf-probe.err")); falling back to callgrind"
    if ! command -v valgrind >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo -n apt-get install -y valgrind >"$TMP/apt.log" 2>&1 || true
    fi
    command -v valgrind >/dev/null 2>&1 \
        || die "neither perf nor valgrind is available ($(head -1 "$TMP/perf-probe.err"))"
    MODE=callgrind
fi

ulimit -v "$MEM_KB" 2>/dev/null || true

# collect TAG PROMPT STEPS -> $TMP/TAG.cnt ("value C-function", one per line)
collect() {
    local tag="$1" prompt="$2" steps="$3"
    if [ "$MODE" = perf ]; then
        perf record -q -g -o "$TMP/$tag.perf" -- "$WORK/gpt2-debug" "$DATA" "$prompt" "$steps" \
            >"$TMP/$tag.out" 2>"$TMP/$tag.err" \
            || { cat "$TMP/$tag.err" >&2; die "profiled run ($tag) failed"; }
        perf report -i "$TMP/$tag.perf" --stdio --no-children -g none --sort symbol \
            --percent-limit 0 >"$TMP/$tag.report" 2>/dev/null
        python3 - "$TMP/$tag.report" >"$TMP/$tag.cnt" <<'PY'
import re, sys
for line in open(sys.argv[1], errors="replace"):
    m = re.match(r"\s*([0-9.]+)%\s+(\S+)\s*$", line)
    if m and m.group(2) not in ("Command", "Shared", "Symbol"):
        print(m.group(1), m.group(2))
PY
    else
        valgrind --tool=callgrind --callgrind-out-file="$TMP/$tag.cg" \
            "$WORK/gpt2-debug" "$DATA" "$prompt" "$steps" \
            >"$TMP/$tag.out" 2>"$TMP/$tag.err" \
            || { tail -10 "$TMP/$tag.err" >&2; die "callgrind run ($tag) failed"; }
        # --auto=no keeps only the "Ir file:function" table; auto-annotation
        # would mix per-source-line rows into it.
        callgrind_annotate --auto=no --threshold=100 "$TMP/$tag.cg" >"$TMP/$tag.report" 2>/dev/null
        python3 - "$TMP/$tag.report" >"$TMP/$tag.cnt" <<'PY'
import re, sys
for line in open(sys.argv[1], errors="replace"):
    m = re.match(r"\s*([0-9,]+)\s+\(\s*([0-9.]+)%\)\s+(\S+)\s*(?:\[.*\])?$", line)
    if m and m.group(3) not in ("PROGRAM", "events"):
        print(m.group(1).replace(",", ""), m.group(3))
PY
    fi
}

echo "== profile ($MODE): load-only, then 1-token prompt + $STEPS decode forwards"
collect load "$TMP/empty.txt" 0
collect decode "$TMP/one.txt" "$STEPS"

echo
echo "== top 10 C functions by decode time ($MODE), mapped to gpt2.py"
python3 - "$TMP/load.cnt" "$TMP/decode.cnt" "$WORK/debug/program.c" "$HERE/gpt2.py" "$MODE" <<'PY'
import os, re, sys
load_f, dec_f, prog, src, mode = sys.argv[1:6]

def read(path):
    d = {}
    for line in open(path):
        value, name = line.split(None, 1)
        name = name.strip()
        d[name] = d.get(name, 0.0) + float(value)
    return d

load, dec = read(load_f), read(dec_f)
net = {}
for name, v in dec.items():
    rest = v - load.get(name, 0.0)
    if rest > 0:
        net[name] = rest
total = sum(net.values()) or 1

# Callgrind reports "file:function"; perf reports the bare symbol with compiler
# suffixes.  Both carry the AIL function name (linear -> linear__irl).
def norm(sym):
    base = sym.split(":")[-1]
    return re.sub(r"(\.(isra|constprop|cold|part|clone)(\.\d+)*)+$", "", base)

defs = []
for i, line in enumerate(open(src, errors="replace"), 1):
    m = re.match(r"def (\w+)\s*\(", line)
    if m:
        defs.append((m.group(1), i))
ranges = {}
for k, (name, start) in enumerate(defs):
    end = defs[k + 1][1] - 1 if k + 1 < len(defs) else max(i for i in range(1, 400))
    ranges[name] = (start, end)

lines = open(prog, errors="replace").read().splitlines()
active = [None] * len(lines)
cur = None
for i, line in enumerate(lines):
    m = re.match(r'\s*#line\s+(\d+)\s+"([^"]+)"', line)
    if m:
        cur = (m.group(2), int(m.group(1)))
    active[i] = cur

def locate(sym):
    base = norm(sym)
    ail = base[:-5] if base.endswith("__irl") else base
    if ail in ranges:
        a, b = ranges[ail]
        return "gpt2.py:%d-%d" % (a, b)
    pat = re.compile(r"^\s*(?:static\s+|inline\s+)*[A-Za-z_][A-Za-z0-9_ \t\*]*\b"
                     + re.escape(base) + r"\s*\(")
    for i, line in enumerate(lines):
        if pat.match(line):
            got = active[i]
            return "runtime (%s)" % (os.path.basename(got[0]) if got else "program.c")
    return "runtime"

rows = sorted(net.items(), key=lambda kv: -kv[1])[:10]
w = max(len(norm(n)) for n, _ in rows)
print("%-4s %-*s %7s  %s" % ("#", w, "C function", "share", "AIL source"))
for i, (name, v) in enumerate(rows, 1):
    print("%-4d %-*s %6.2f%%  %s" % (i, w, norm(name), 100.0 * v / total, locate(name)))
print()
print("share = %s after subtracting the load-only profile; symbol suffixes"
      % ("perf symbol overhead" if mode == "perf" else "callgrind Ir"))
print("(.isra/.constprop) are compiler clones; `AIL source` is the def line of the")
print("AIL function the C function came from.")
PY
