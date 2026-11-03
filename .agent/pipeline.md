# job job-fz222-11040639  started 2026-11-03T21:39:52Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report: fz222 — no change needed**

The reported silent difference does not reproduce on this tree (`staging:integ`, `adaaeeb`).

Verification:
- Saved reproducer to `/tmp/probes/fz222.py`; regenerated with `lab/fuzz/gen.py 2076019435` and confirmed byte-identical.
- `bash ~/tools/cmp.sh /tmp/probes/fz222.py $PWD`: CPython exit 1, general (`g`) exit 1, default (`d`) exit 1; **same stdout** on both AIL builds. Both also print `ValueError: invalid literal for int() with base 10: '1e-07'` like CPython.
- Separate `AIL_IR=1` build: exit 1, **same stdout**.
- `python3 lab/fuzz/run.py --start 2076019435 --count 1 --modes default,ir`: **default 1 same / 0 DIFF, ir 1 same / 0 DIFF** (28 s).

Additional probes (all match CPython on general, default, and `AIL_IR=1`):
- `/tmp/probes/fz222_near.py`: `int(str(v))` for `±1e-7`, `0.0`, `-0.0`, `±1.5`, `1e20`, `1e-320`, inf, nan, plus literal/text forms — same.
- `/tmp/probes/fz222_routes.py`: same operation on an argument, list items, attribute, and dict values — same; no refusals.

Other differences seen: none. No files changed, no commit made.
[cost $0.0000, opencode tokens {"total": 314305, "input": 16999, "output": 4769, "reasoning": 2873, "cache.write": 0, "cache.read": 289664}]
    tool time: bash 1.4 min
         28s bash   python3 lab/fuzz/run.py --start 2076019435 --count 1 --out /tmp/fzrun222 --modes default,ir --jobs 2 2>&1 | ta
         26s bash   mkdir -p /tmp/probes && cat > /tmp/probes/fz222.py <<'PYEOF' import sys  def h0(n: int, a: int) -> int:     if
         13s bash   d=$(mktemp -d /tmp/cmpirXXXX); cp /tmp/probes/fz222.py $d/p.ail; cd $d; python3 p.ail > py.out 2>py.err; echo 
          6s bash   cat > /tmp/probes/fz222_routes.py <<'PYEOF' class H:     def __init__(self, v: float) -> None:         self.v 
          5s bash   cat > /tmp/probes/fz222_routes.py <<'PYEOF' import sys  class H:     def __init__(self, v: float) -> None:    
          3s bash   cat > /tmp/probes/fz222_near.py <<'PYEOF' def show(label, fn):     try:         print(label, fn())     except 
          0s bash   pwd && ls -la && git status && git branch --show-current && ls ~/tools 2>/dev/null
          0s bash   grep -rn "invalid literal\|int(\|ParseIntError\|parse::<" AIL_CURRENT --include='*.rs' | grep -i "literal\|flo

FINAL VERDICT: NOCHANGE  2026-11-03T21:42:32Z  (the worker changed nothing; no review was run)
