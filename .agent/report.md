# job job-fz217-11021900  started 2026-11-02T10:09:01Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Result: not reproducible on this tree — nothing changed, no commit.**

- `lab/fuzz/run.py --start 2075907694 --count 1 --modes default,ir`: both modes classified `overflow`, **0 DIFF**. Original line 12 giant integer is byte-identical to CPython.
- `/tmp/probes/fz217.py` via `cmp.sh`: line 12 now matches; the only later stop is the declared int64 `round()` overflow (`OverflowError: integer overflow in round()`), already recorded (C?-job-fz2 / pre429).
- Explicit `AIL_IR=0` and `AIL_IR=1` builds also match the reported line.
- Probes `/tmp/probes/fz217_min.py` (direct/argument/list/attribute/dict, negative, width) and `fz217_bounds.py` (`1e77`, `1e308`, `.600f`, `%.600f`, wide width): all same stdout on general and default builds.
- Existing `test_ail_fuzz71.py` (the prior buffer-truncation fix) passes: 2 tests, OK.
- Other differences seen: only the documented int64 `round()` overflow; no other silent difference.
[cost $0.0000, opencode tokens {"total": 823400, "input": 93150, "output": 4606, "reasoning": 6796, "cache.write": 0, "cache.read": 718848}]
    tool time: bash 1.2 min
         16s bash   python3 lab/fuzz/run.py --start 2075907694 --count 1 --modes default,ir --out /tmp/fuzz217 --jobs 1 2>&1 | tai
         14s bash   python3 -B AIL_CURRENT/test_ail_fuzz71.py 2>&1 | tail -20
         12s bash   d=$(mktemp -d /tmp/cmpir0XXXX); cp /tmp/probes/fz217.py $d/p.ail; cd $d; python3 p.ail > py.out 2> py.err; ech
         12s bash   mkdir -p /tmp/probes; cat > /tmp/probes/fz217.py <<'PYEOF' def h0(n: int, a: int) -> int:     if n <= 0:      
         11s bash   cat > /tmp/probes/fz217_bounds.py <<'PYEOF' def fmt(x: float, spec: str) -> str:     return format(x, spec)   
          5s bash   cat > /tmp/probes/fz217_min.py <<'PYEOF' class B:     def __init__(self, x: float) -> None:         self.x: fl
          0s bash   git log --oneline -10 work; echo ---; git log --oneline -10 origin/job-fz217-11021900; echo ---; git show --st
          0s bash   cat ~/tools/cmp.sh; echo ---; cat ~/tools/cmpu.sh; echo ---; ls AIL_CURRENT/tests.d 2>/dev/null | head; echo -

FINAL VERDICT: NOCHANGE  2026-11-02T10:12:21Z  (the worker changed nothing; no review was run)
