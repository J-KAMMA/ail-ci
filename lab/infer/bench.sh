#!/usr/bin/env bash
# Repeatable tokens-per-second benchmark: AIL gpt2.py against llama.cpp.
#
#   bash lab/infer/bench.sh [WORK] [RUNS]
#
# WORK defaults to ${RUNNER_TEMP:-/tmp}/ail-infer (weights never enter git).
# RUNS defaults to 5; the table reports medians.
#
# Both programs see the same 64 token ids (tokens.txt) and the same F32 weight
# values (exported/ made by fetch.sh).  After every one of the RUNS runs the 16
# greedy ids of AIL and llama.cpp are compared with each other and with ref.py;
# a difference prints both lists and exits non-zero (wrong output).
#
# Columns: prefill tok/s (64 tokens), decode tok/s (one forward per decoded
# token), peak RSS (/usr/bin/time -v), binary size.  llama.cpp produces the
# first of its 16 generated tokens from the prefill, so its decode row uses its
# own "eval time ... / N runs" count (15) rather than 16.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
WORK="${1:-${RUNNER_TEMP:-/tmp}/ail-infer}"
RUNS="${2:-${RUNS:-5}}"
MEM_KB="${MEM_KB:-1500000}"
STEPS=16
TOKENS="$HERE/tokens.txt"
PROMPT="$HERE/prompt.txt"

die() { echo "bench: $*" >&2; exit 2; }

case "$RUNS" in ''|*[!0-9]*|0) die "RUNS must be a positive integer" ;; esac

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 -c 'import numpy, gguf' 2>/dev/null \
    || die "need python3 numpy and gguf: python3 -m pip install numpy gguf"

echo "== fetch weights and llama.cpp (idempotent)"
bash "$HERE/fetch.sh" "$WORK" >"$TMP/fetch.log" 2>&1 \
    || { tail -20 "$TMP/fetch.log" >&2; die "fetch.sh failed"; }
DATA="$WORK/exported"
MODEL="$WORK/zenz-f32.gguf"
LLAMA_BIN="$WORK/llama-azoo/build/bin"

echo "== build AIL (default command, no --strict/--debug)"
rm -f "$WORK/gpt2"
if ! python3 -B "$ROOT/AIL_CURRENT/ail_chatgpt.py" compile "$HERE/gpt2.py" -o "$WORK/gpt2" \
        >"$TMP/ail-build.log" 2>&1; then
    cat "$TMP/ail-build.log" >&2
    die "AIL build failed"
fi
grep -F 'note:' "$TMP/ail-build.log" || true
[ -x "$WORK/gpt2" ] || die "AIL build produced no $WORK/gpt2"

echo "== prompt text must tokenize to tokens.txt"
want="$(tr -s ' \n' ' ' <"$TOKENS" | sed 's/ $//')"
got="$("$LLAMA_BIN/llama-tokenize" -m "$MODEL" --ids --no-escape -p "$(cat "$PROMPT")" 2>/dev/null \
    | tr -d '[]' | tr ',' ' ' | tr -s ' \n' ' ' | sed 's/^ //; s/ $//')"
[ "$got" = "$want" ] || die "prompt.txt tokenizes to [$got], tokens.txt is [$want]"
echo "   64 ids match"

echo "== reference (ref.py, numpy float64)"
ulimit -v "$MEM_KB" 2>/dev/null || true
python3 "$HERE/ref.py" "$DATA" "$TOKENS" "$STEPS" >"$TMP/ref.out" 2>"$TMP/ref.err" \
    || { cat "$TMP/ref.err" >&2; die "ref.py failed"; }
REF_IDS="$(sed -n 's/^greedy //p' "$TMP/ref.out")"
[ -n "$REF_IDS" ] || die "ref.py printed no greedy ids"
echo "   ref greedy: $REF_IDS"

: >"$TMP/empty.txt"

# run_cmd OUTPREFIX CMD... : wall seconds and peak RSS (KiB) into $OUTPREFIX.{s,kib}
run_cmd() {
    local pre="$1"; shift
    local t0 t1 rc=0
    t0="$(date +%s%N)"
    /usr/bin/time -v -o "$pre.time" "$@" >"$pre.out" 2>"$pre.err" || rc=$?
    t1="$(date +%s%N)"
    printf '%d\n' $(( (t1 - t0) / 1000000 )) >"$pre.ms"
    sed -n 's/.*Maximum resident set size (kbytes): \([0-9]*\).*/\1/p' "$pre.time" >"$pre.kib"
    printf '%s\n' "$rc" >"$pre.rc"
    return 0
}

ail_ids() { sed -n 's/^greedy //p' "$1" | sed 's/^ *//; s/ *$//'; }

check_ids() { # check_ids LABEL GOT
    local label="$1" got="$2"
    if [ "$got" != "$REF_IDS" ]; then
        {
            echo "STOP: greedy ids differ ($label)"
            echo "  ref.py : $REF_IDS"
            echo "  $label: $got"
        } >&2
        exit 3
    fi
}

# median of the numbers on stdin (one per line), in the given scale
median() { python3 -c 'import statistics,sys; v=[float(x) for x in sys.stdin.read().split()]; print(statistics.median(v) if v else "nan")'; }

echo "== AIL x$RUNS"
: >"$TMP/ail.tsv"
for i in $(seq 1 "$RUNS"); do
    p="$TMP/ail-empty-$i"
    run_cmd "$p" /usr/bin/env -i "HOME=$HOME" bash -c \
        "ulimit -v $MEM_KB; exec '$WORK/gpt2' '$DATA' '$TMP/empty.txt' 0"
    [ "$(cat "$p.rc")" = 0 ] || { cat "$p.err" >&2; die "AIL load run failed (rc=$(cat "$p.rc"))"; }

    p="$TMP/ail-prompt-$i"
    run_cmd "$p" /usr/bin/env -i "HOME=$HOME" bash -c \
        "ulimit -v $MEM_KB; exec '$WORK/gpt2' '$DATA' '$TOKENS' 0"
    [ "$(cat "$p.rc")" = 0 ] || { cat "$p.err" >&2; die "AIL prefill run failed (rc=$(cat "$p.rc"))"; }

    p="$TMP/ail-full-$i"
    run_cmd "$p" /usr/bin/env -i "HOME=$HOME" bash -c \
        "ulimit -v $MEM_KB; exec '$WORK/gpt2' '$DATA' '$TOKENS' $STEPS"
    [ "$(cat "$p.rc")" = 0 ] || { cat "$p.err" >&2; die "AIL full run failed (rc=$(cat "$p.rc"))"; }
    got="$(ail_ids "$p.out")"
    check_ids "AIL run $i" "$got"

    python3 - "$TMP" "$i" >>"$TMP/ail.tsv" <<'PY'
import sys
t, i = sys.argv[1], sys.argv[2]
def ms(name):
    with open(f"{t}/{name}-{i}.ms") as f:
        return float(f.read().strip())
def kib(name):
    with open(f"{t}/{name}-{i}.kib") as f:
        return float(f.read().strip())
load, pre, full = ms("ail-empty"), ms("ail-prompt"), ms("ail-full")
print(i, load, pre - load, full - pre, kib("ail-full"))
PY
    echo "   run $i ok"
done

echo "== llama.cpp x$RUNS"
for t in 1 4; do
    : >"$TMP/llama-$t.tsv"
    for i in $(seq 1 "$RUNS"); do
        p="$TMP/llama-$t-$i"
        run_cmd "$p" bash -c \
            "ulimit -v $MEM_KB 2>/dev/null || true; exec '$LLAMA_BIN/llama-cli' \
                -m '$MODEL' -p \"\$(cat '$PROMPT')\" -n $STEPS -t $t --temp 0 --top-k 1 \
                -c 1024 -no-cnv --no-display-prompt"
        [ "$(cat "$p.rc")" = 0 ] || { tail -20 "$p.err" >&2; die "llama-cli -t $t run $i failed"; }

        # llama-cli reports times, AIL prints ids; get llama's ids by tokenizing
        # the generated text with the same model and compare them too.
        text="$(cat "$p.out")"
        ids="$("$LLAMA_BIN/llama-tokenize" -m "$MODEL" --ids --no-bos --no-escape \
            -p "$text" 2>/dev/null | tr -d '[]' | tr ',' ' ' | tr -s ' \n' ' ' | sed 's/^ //; s/ $//')"
        [ "$(wc -w <<<"$ids")" = "$STEPS" ] \
            || die "llama-cli -t $t run $i: generated ${#text} bytes -> [${ids}], expected $STEPS ids"
        check_ids "llama-cli -t $t run $i" "$ids"
        printf '%s\n' "$ids" >"$TMP/llama-$t-$i.ids"

        python3 - "$p" "$i" >>"$TMP/llama-$t.tsv" <<'PY'
import re, sys
p, i = sys.argv[1], sys.argv[2]
err = open(p + ".err", errors="replace").read()
def field(pat):
    m = re.search(pat, err)
    if not m:
        sys.exit("could not parse llama.cpp report: " + pat)
    return float(m.group(1)), int(m.group(2))
pms, pn = field(r"prompt eval time\s*=\s*([0-9.]+) ms /\s*(\d+)\s*tokens?")
ems, en = field(r"\beval time\s*=\s*([0-9.]+) ms /\s*(\d+)\s*runs?")
print(i, pms, pn, ems, en, float(open(p + ".kib").read()))
PY
        echo "   t=$t run $i ok: $(sed -n 's/.*prompt eval time.*/&/p' "$p.err" | tail -1 | sed 's/^.*prompt eval/prompt eval/')"
    done
done

echo
echo "== table (medians of $RUNS, one thread unless labelled)"
python3 - "$TMP" "$WORK" "$RUNS" "$STEPS" <<'PY'
import os, statistics, sys
t, work, runs, steps = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
def med(rows, col):
    return statistics.median(r[col] for r in rows)
ail = [tuple(map(float, l.split())) for l in open(t + "/ail.tsv")]
llama = {th: [tuple(map(float, l.split())) for l in open(f"{t}/llama-{th}.tsv")] for th in (1, 4)}
gib = 1024 * 1024
def mib(k): return k / 1024

rows = []
load = med(ail, 1) / 1000
pre = med(ail, 2) / 1000
dec = med(ail, 3) / 1000
rows.append(("AIL (`gpt2.py`, default build)", 1,
             64 / pre, steps / dec, med(ail, 4), os.path.getsize(work + "/gpt2")))
for th in (1, 4):
    r = llama[th]
    pms, pn, ems, en = med(r, 1), med(r, 2), med(r, 3), med(r, 4)
    label = "llama.cpp `llama-cli`" + (" (context row, not headline)" if th != 1 else "")
    rows.append((label, th, pn / (pms / 1000), en / (ems / 1000), med(r, 5),
                 os.path.getsize(work + "/llama-azoo/build/bin/llama-cli")))

print(f"{'program':52s} {'thr':>3s} {'prefill tok/s':>13s} {'decode tok/s':>12s} "
      f"{'peak RSS':>10s} {'binary':>12s}")
print("-" * 108)
for name, th, p, d, kib, size in rows:
    print(f"{name:52s} {th:3d} {p:13.2f} {d:12.2f} {mib(kib):9.0f}M {size:12,d} B")
print()
print(f"AIL phase medians: load {load:.2f} s, prefill 64 tokens {pre:.3f} s "
      f"({pre / 64 * 1000:.1f} ms/token), decode {steps} forwards {dec:.3f} s "
      f"({dec / steps * 1000:.1f} ms/forward)")
for th in (1, 4):
    r = llama[th]
    print(f"llama.cpp -t {th}: prefill {med(r, 1) / med(r, 2):.3f} ms/token, "
          f"decode {med(r, 3) / med(r, 4):.3f} ms/forward "
          f"(prefill eval {int(med(r, 2))} tokens, decode eval {int(med(r, 4))} runs)")
print()
print("decode tok/s counts one forward pass per number: AIL runs "
      f"{steps} decode forwards for {steps} tokens, llama.cpp gets its first "
      f"token from the prefill and so reports {int(med(llama[1], 4))}.")
print("greedy ids: equal to ref.py and llama.cpp on all "
      f"{runs} runs, both -t 1 and -t 4.")
PY
