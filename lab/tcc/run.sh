#!/bin/sh
# Reproduce the quick-run probe: install both tcc versions, then measure.
#
#   sh lab/tcc/run.sh [--out /tmp/tcc.json] [--runs 3] [--corpus 50]
#
# tcc 0.9.27 is the Ubuntu 24.04 package; tcc 0.9.28rc is built from the
# upstream mob branch at the commit lab/tccdev used.  Nothing here changes the
# compiler, the runtime or a default build: run.py only ever invokes tcc.
set -eu

REPO=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TCC_UPSTREAM=${TCC_UPSTREAM:-/tmp/tcc-install/bin/tcc}
TCC_COMMIT=${TCC_COMMIT:-e23dabe}

if ! command -v tcc >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq tcc
fi

if [ ! -x "$TCC_UPSTREAM" ]; then
    rm -rf /tmp/tinycc
    git clone -q https://github.com/TinyCC/tinycc.git /tmp/tinycc
    git -C /tmp/tinycc checkout -q "$TCC_COMMIT"
    ( cd /tmp/tinycc && ./configure --prefix=/tmp/tcc-install && make -j 2 && make install )
fi

echo "apt tcc:      $(tcc -v 2>&1 | head -1)"
echo "upstream tcc: $("$TCC_UPSTREAM" -v 2>&1 | head -1)"
echo "gcc:          $(gcc --version | head -1)"

cd "$REPO"
exec python3 lab/tcc/run.py --tcc-apt "$(command -v tcc)" --tcc-upstream "$TCC_UPSTREAM" \
    --excerpts lab/tcc "$@"
