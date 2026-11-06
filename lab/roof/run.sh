#!/bin/bash
# roof: how close each compare program is to the hardware limit, and what limits it.
#
#   bash lab/roof/run.sh            # facts + microbenchmarks + all ten programs (about 25 min)
#   bash lab/roof/run.sh facts      # machine facts and the three microbenchmarks only
#   bash lab/roof/run.sh programs   # the ten programs only
#
# Everything is measured on the same runner in the same job: the filter (STREAM triad, pointer
# chase, clock/width) and the programs. The counters fall back to valgrind's cachegrind when the
# vCPUs expose no hardware PMU, and every table row records which method produced it.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DATA="$HERE/data"
BIN="${TMPDIR:-/tmp}/roof-bin"
mkdir -p "$DATA" "$BIN"
STAGE="${1:-all}"

facts() {
    # 1. the machine facts and the derived spec peak
    lscpu > "$DATA/lscpu.txt" 2>&1
    {
        echo "# model: $(lscpu | sed -n 's/^Model name:[[:space:]]*//p')"
        # lscpu prints Thread(s) per core, then Core(s) per socket, then Socket(s); label in that order
        echo "# threads/core,cores/socket,sockets: $(lscpu | sed -n 's/^\(Thread(s) per core\|Core(s) per socket\|Socket(s)\):[[:space:]]*//p' | paste -sd/)"
        echo "# L1d/L2/L3: $(lscpu | sed -n 's/^\(L1d\|L2\|L3\) cache:[[:space:]]*//p' | paste -sd/)"
        echo "# SIMD: $(lscpu | sed -n 's/^Flags:[[:space:]]*//p' | grep -o -w 'sse4_2\|avx\|avx2\|fma\|avx512f' | paste -sd,)"
    } > "$DATA/facts.txt"

    # 2. clock, scalar width, SIMD width
    gcc -O2 -mavx2 -mfma -std=c11 -o "$BIN/clock" "$HERE/clock.c" || return 1
    : > "$DATA/clock.txt"
    for i in 1 2 3; do "$BIN/clock" >> "$DATA/clock.txt"; echo "#" >> "$DATA/clock.txt"; done

    # 3. STREAM triad (four sizes) and pointer chase (four working sets), best of three runs
    gcc -O2 -std=c11 -o "$BIN/stream" "$HERE/stream.c" || return 1
    gcc -O2 -std=c11 -o "$BIN/chase" "$HERE/chase.c" || return 1
    GHZ=$(awk '$1=="dependent_add_ghz"{s+=$2; n++} END{printf "%.3f", s/n}' "$DATA/clock.txt")
    : > "$DATA/stream.txt"
    : > "$DATA/chase.txt"
    for i in 1 2 3; do
        "$BIN/stream" | tail -n +2 >> "$DATA/stream.txt"
        "$BIN/chase" "$GHZ" | tail -n +2 >> "$DATA/chase.txt"
    done
    awk -v ghz="$GHZ" '
        { k=$1; if (!(k in best) || $3 > best[k]) best[k]=$3 }
        END { for (k in best) printf "%s bytes: best median triad %.3f GB/s\n", k, best[k] }' "$DATA/stream.txt" \
        | sort -n > "$DATA/stream_summary.txt"
    awk -v ghz="$GHZ" '{ k=$1; if (!(k in best) || $3 < best[k]) best[k]=$3 }   # $1 in chase.txt is entries
        END { for (k in best) printf "%s entries: min %.3f ns/load = %.1f cycles at %s GHz\n", k, best[k], best[k]*ghz, ghz }' \
        "$DATA/chase.txt" | sort -n > "$DATA/chase_summary.txt"
    echo "clock: $GHZ GHz"
    cat "$DATA/stream_summary.txt" "$DATA/chase_summary.txt"
}

programs() {
    python3 "$HERE/measure.py" --out "$DATA" --runs 3 --jobs 2 "$@"
}

case "$STAGE" in
    facts) facts ;;
    programs) shift; programs "$@" ;;
    all) facts && programs ;;
    *) echo "usage: run.sh [facts|programs|all]" >&2; exit 2 ;;
esac
