# job job-fz219-11031401  started 2026-11-03T05:01:38Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report: fz219**

**Result: no change committed** (the reported DIFF no longer reproduces).

**Verification**
- `cmp.sh /tmp/probes/fz219.py` on this tree: both builds stop at compile time with the named refusal `p.ail:122:36: int64 constant out of range: 85070591730234615847396907784232501249` (the `-9223372036854775807 ** 2` literal). This is an allowed compile-time refusal, not the reported DIFF.
- With only that unrelated literal replaced by `"0"`, default, `AIL_IR=1`, forced-general and forced-general+IR all print `-67`, `118`, `-6` exactly like CPython 3.12. The later difference is only the documented int64 shift `OverflowError` (`lab/fuzz/run.py` classifies it `overflow`, not DIFF).
- With `AIL_EXACT_INT=1`, the whole original program is byte-identical to CPython (`stdout` and exit code 1).
- Root cause was already fixed: an exception raised in a `try`'s `else` was caught by that try's own `except`. That is `DIFFERENCES.md` row `C?-job-fz1-10281147-1`, locked by `test_ail_fz1` (ran: 1 test, OK).

**Probes run (all match CPython on both `cmp.sh` builds)**
- `/tmp/probes/fz219_min.py` — minimized try/else + outer handler, dict value.
- `/tmp/probes/fz219_arg.py` — list item, attribute and dict value routes.
- `/tmp/probes/fz219_types.py` — `ZeroDivisionError`, `IndexError`, `AssertionError`, `ValueError`.
- `/tmp/probes/fz219_exactint.py` — finally after the else failure.

**Other differences seen (pre-existing, not silent)**
- The out-of-int64 constant is rejected at compile time instead of run time; allowed by AIL's "same result or named refusal" contract.
- The later `v5 <<= 9` produces the declared int64 `OverflowError` (`overflow` class).

No files were changed; `git status` shows only the pipeline’s `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 1549596, "input": 88891, "output": 6257, "reasoning": 15984, "cache.write": 0, "cache.read": 1438464}]
    tool time: bash 1.3 min
         22s bash   cd /tmp/t219 && python3 - <<'PY' s=open('p.ail').read() s=s.replace('("%03d" % (-9223372036854775807 ** 2))','
         19s bash   cd /tmp/t219 && for cfg in "g:AIL_UNIFIED_FORCE=1" "gir:AIL_UNIFIED_FORCE=1 AIL_IR=1"; do name=${cfg%%:*}; env
         14s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_fz1 2>&1 | tail 
         10s bash   cd /tmp && rm -rf t219 && mkdir t219 && cp /tmp/probes/fz219.py t219/p.ail && cd t219 && python3 p.ail > py.ou
          8s bash   mkdir -p /tmp/probes && cat > /tmp/probes/fz219_min.py <<'PY' def f(d):     try:         for i in range(1):   
          2s bash   mkdir -p /tmp/probes && cat > /tmp/probes/fz219.py <<'PYEOF' import sys  def h0(n: int, a: int) -> int:     if
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/fuzz/gen.py 2076003115 -o /tmp/t219/gen.py && diff -q /tmp/t
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git log --oneline | head -30 && echo === && grep -n "fz219\|fz216\|C?-" 

FINAL VERDICT: NOCHANGE  2026-11-03T05:05:18Z  (the worker changed nothing; no review was run)
