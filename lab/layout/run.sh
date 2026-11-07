#!/bin/bash
# layout: why AIL's typed builds miss cache more than the hand-written C, and what a flat layout
# would save. Measurement and design only; the compiler is unchanged.
#
#   bash lab/layout/run.sh              # baselines + the hand edits (about 20 min)
#   bash lab/layout/run.sh baseline     # baselines only
#   bash lab/layout/run.sh edits        # baselines + hand edits
#   bash lab/layout/run.sh analyze      # rewrite data/analysis.json and print the tables
#
# valgrind is not on the GitHub image; ensure_valgrind unpacks it under $TMPDIR (the same trick
# lab/energy/run.sh uses) and never writes the repository.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="$HERE/data"
TMP="${TMPDIR:-/tmp}"
mkdir -p "$DATA"

ensure_valgrind() {
    command -v valgrind >/dev/null && return 0
    local dst="$TMP/layout-valgrind"
    if [ ! -x "$dst/usr/bin/valgrind" ]; then
        mkdir -p "$dst/deb" || return 1
        ( cd "$dst/deb" && apt-get download valgrind >/dev/null 2>&1 &&
          dpkg-deb -x ./*.deb "$dst" ) || return 1
    fi
    export PATH="$dst/usr/bin:$PATH"
    export VALGRIND_LIB="$dst/usr/libexec/valgrind"
    command -v valgrind >/dev/null
}

ensure_valgrind || { echo "warning: valgrind unavailable; every counter will be null" >&2; }

case "${1:-all}" in
    baseline) python3 "$HERE/measure.py" --out "$DATA" --runs 5 --jobs 2 ;;
    edits|all) python3 "$HERE/measure.py" --out "$DATA" --runs 5 --jobs 2 --variants ;;
    analyze) python3 "$HERE/analyze.py" --print ;;
    *) echo "usage: run.sh [baseline|edits|analyze]" >&2; exit 2 ;;
esac
