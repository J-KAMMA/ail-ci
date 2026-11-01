# job job-fz210-11011834  started 2026-11-01T09:43:02Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report — fz210 (seed 2075807758): NOT REPRODUCED; no changes made.**

- Saved the exact program as `/tmp/probes/fz210.py`; `lab/fuzz/gen.py 2075807758` reproduces the same text (identical).
- `bash ~/tools/cmp.sh` on this tree: both builds exit 1 with the same stdout as CPython (`IndexError: list index out of range`).
- Actual fuzz runner for the seed: `default` and `ir` both classified `same` (2/2), 0 DIFF/crash.
- Explicit builds: `AIL_IR=0`, `AIL_IR=1`, `AIL_UNIFIED_FORCE=1 AIL_IR=0` all match CPython's exit 1 and stdout.

**Cause of the stale finding:** it is the already-fixed try/`else` handler-scope bug (`DIFFERENCES C?-job-fz1-10281147-1`). The old emitter copied `else` into the `try` body, so the `IndexError` from `v6[3]` in `else` was caught by `except IndexError` and printed `a,b,c False`. This tree's `test_ail_fz1.py` already covers it (`index_outer`).

**Minimized probes (all match CPython on both cmp.sh builds):**
- `/tmp/probes/fz210_min.py` — direct `try/except IndexError/else` with `v6[3]` → both exit 1.
- `/tmp/probes/fz210_min_outer.py` — exception in `else` reaches the outer handler → both exit 0, same stdout.
- `/tmp/probes/fz210_min_arg.py` — same through a function argument/list item → both exit 1.

`test_ail_fz1`: 1 test, OK, 17s. Working tree unchanged (only the pre-existing untracked `.agent/pipeline.md`); nothing committed. Other differences observed: none.
[cost $0.0000, opencode tokens {"total": 533753, "input": 40461, "output": 4275, "reasoning": 6201, "cache.write": 0, "cache.read": 482816}]
    tool time: bash 1.8 min
         30s bash   cd /tmp && rm -rf fz210run && python3 /home/runner/work/ail-ci/ail-ci/lab/fuzz/run.py --start 2075807758 --cou
         27s bash   mkdir -p /tmp/probes && cat > /tmp/probes/fz210.py <<'PYEOF' def h0(xs: list[int]) -> int:     t: int = 0     
         17s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_fz1 2>&1 | tail -5; echo "rc=${PIPESTATUS[0]}"
         15s bash   cd /tmp && d=$(mktemp -d /tmp/ir0XXXX); cp /tmp/probes/fz210.py $d/p.ail; cd $d; python3 p.ail > py.out 2>py.e
         14s bash   cd /tmp && d=$(mktemp -d /tmp/irXXXX); cp /tmp/probes/fz210.py $d/p.ail; cd $d; python3 p.ail > py.out 2>py.er
          6s bash   mkdir -p /tmp/probes cat > /tmp/probes/fz210_min.py <<'PY' def main() -> int:     v6: list[int] = [3] * 2     
          0s bash   pwd && ls -la && git status && git branch --show-current && ls ~/tools 2>/dev/null
          0s bash   git show --stat HEAD | head -50; git show HEAD:.agent/pipeline.md 2>/dev/null | head -30; cat .agent/pipeline.

FINAL VERDICT: NOCHANGE  2026-11-01T09:47:02Z  (the worker changed nothing; no review was run)
