#!/bin/bash
# energy: joules per run of every compare program (AIL typed/main.py, C, Rust, CPython) and how far
# each row is from the Landauer floor.
#
#   bash lab/energy/run.sh            # probe for RAPL, then build and measure every row (about 30 min)
#   bash lab/energy/run.sh probe      # machine facts and the energy-counter probe only
#   bash lab/energy/run.sh measure    # measure the rows (cachegrind from lab/roof/data + Rust/CPython here)
#
# No compiler change. Counters are valgrind cachegrind because the GitHub vCPUs expose no hardware
# PMU; if RAPL is readable (perf power/energy-pkg or /sys/class/powercap) the measured column is
# filled, otherwise it stays `n/a`. The model column is always the published-energy estimate.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DATA="$HERE/data"
TMP="${TMPDIR:-/tmp}"
mkdir -p "$DATA"

ensure_valgrind() {
    # The GitHub image does not ship valgrind, but the Ubuntu archive is reachable and the tools can
    # be unpacked without root. The repo is never written: everything goes under TMPDIR.
    command -v valgrind >/dev/null && return 0
    local dst="$TMP/energy-valgrind"
    if [ ! -x "$dst/usr/bin/valgrind" ]; then
        mkdir -p "$dst/deb" || return 1
        ( cd "$dst/deb" && apt-get download valgrind >/dev/null 2>&1 &&
          dpkg-deb -x ./*.deb "$dst" ) || return 1
    fi
    export PATH="$dst/usr/bin:$PATH"
    export VALGRIND_LIB="$dst/usr/libexec/valgrind"
    command -v valgrind >/dev/null
}

probe() {
    {
        echo "# runner $(date -u +%FT%TZ)"
        echo "# cpu $(lscpu | sed -n 's/^Model name:[[:space:]]*//p')"
        echo "# threads/core,cores/socket,sockets: $(lscpu | sed -n 's/^\(Thread(s) per core\|Core(s) per socket\|Socket(s)\):[[:space:]]*//p' | paste -sd/)"
        echo "# L1d/L2/L3: $(lscpu | sed -n 's/^\(L1d\|L2\|L3\) cache:[[:space:]]*//p' | paste -sd/)"
        echo
        echo "## perf power/energy-pkg"
        perf stat -e power/energy-pkg/ -- true 2>&1 | tail -6
        echo
        echo "## /sys/class/powercap"
        if compgen -G '/sys/class/powercap/*/energy_uj' >/dev/null || compgen -G '/sys/class/powercap/*/*/energy_uj' >/dev/null; then
            for f in /sys/class/powercap/*/energy_uj /sys/class/powercap/*/*/energy_uj; do
                [ -f "$f" ] && printf '%s: %s\n' "$f" "$(cat "$f" 2>&1)"
            done
        else
            echo "absent"
        fi
        echo
        echo "## /dev/cpu/*/msr"
        ls -l /dev/cpu/*/msr 2>&1 | head -4
        echo
        echo "## tools"
        echo "perf: $(perf --version 2>&1)"
        echo "valgrind: $(valgrind --version 2>&1)"
        echo "cg_annotate: $(command -v cg_annotate || echo missing)"
        echo
        echo "## conclusion"
        if perf stat -e power/energy-pkg/ -- true >/dev/null 2>&1; then
            echo "RAPL via perf power/energy-pkg"
        elif compgen -G '/sys/class/powercap/*/energy_uj' >/dev/null || compgen -G '/sys/class/powercap/*/*/energy_uj' >/dev/null; then
            echo "RAPL via /sys/class/powercap"
        else
            echo "no readable package-energy counter: J measured = n/a (no value is invented)"
        fi
    } > "$DATA/probe.txt" 2>&1
    cat "$DATA/probe.txt"
}

ensure_valgrind || echo "warning: valgrind/cachegrind unavailable; Rust and CPython counters will be null" >&2

case "${1:-all}" in
    probe) probe ;;
    measure) python3 "$HERE/measure.py" --out "$DATA" --runs 3 --jobs 2 --merge ;;
    all) probe && python3 "$HERE/measure.py" --out "$DATA" --runs 3 --jobs 2 --merge ;;
    *) echo "usage: run.sh [probe|measure|all]" >&2; exit 2 ;;
esac
