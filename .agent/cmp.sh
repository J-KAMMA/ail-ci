#!/bin/bash
# cmp.sh SRC WORKTREE: build SRC with the general path and the default build, compare with CPython.
src=$1; wt=$2; d=$(mktemp -d /tmp/cmpXXXX); cp "$src" $d/p.ail; cd $d
python3 p.ail > py.out 2> py.err; echo "cpython exit $?"
for m in g d; do
  if [ "$m" = g ]; then export AIL_UNIFIED_FORCE=1; else unset AIL_UNIFIED_FORCE; fi
  AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 "$wt/AIL_CURRENT/ail_chatgpt.py" compile p.ail --syntax python -o exe_$m > b_$m.log 2>&1 || { echo "build $m failed"; tail -5 b_$m.log; continue; }
  ./exe_$m > $m.out 2> $m.err; echo "$m exit $?"
  if diff py.out $m.out > diff_$m.txt; then echo "$m same stdout"; else echo "$m DIFF:"; head -c 2500 diff_$m.txt; echo; fi
  tail -1 $m.err
done
tail -1 py.err; echo "dir $d"
