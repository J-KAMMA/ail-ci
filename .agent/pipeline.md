# job job-fz215-11021859  started 2026-11-02T10:05:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Result: difference does not reproduce on this tree — no changes made.**

- Reproducer saved as `/tmp/probes/fz215.py`.
- `bash ~/tools/cmp.sh /tmp/probes/fz215.py $PWD` (default): CPython exit 1, `g` and `d` both exit 1, **same stdout** (6 lines, ending `a,b,c `); both raise `ValueError: invalid literal for int() with base 10: ' pad '`.
- Same command with `AIL_IR=1`: **same stdout** on `g` and `d`, same `ValueError`.
- Actual fuzzer: `python3 lab/fuzz/run.py --start 2075907148 --count 1 --modes default,ir` → `same` 1 in default, `same` 1 in ir, **0 DIFF/crash** (32 s).

The reported cause was `int(' pad ')` not raising in AIL, letting execution continue to the line-7 print. On this tree it raises exactly like CPython 3.12.

Extra probes (`/tmp/probes/fz215_int.py`, both builds): `int()` on empty/whitespace-only/whitespace-padded/signed/unicode/underscore/hex-like/invalid strings — all **same stdout** as CPython under both default and `AIL_IR=1`. No other differences observed.
[cost $0.0000, opencode tokens {"total": 212298, "input": 33193, "output": 2968, "reasoning": 3465, "cache.write": 0, "cache.read": 172672}]
    tool time: bash 1.6 min
         32s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/fuzz/run.py --start 2075907148 --count 1 --out /tmp/fuzzchec
         30s bash   AIL_IR=1 bash ~/tools/cmp.sh /tmp/probes/fz215.py $PWD 2>&1 | tail -30
         29s bash   mkdir -p /tmp/probes && cat > /tmp/probes/fz215.py <<'PYEOF' import sys  def h0(n: int, a: int) -> int:     if
          4s bash   cat > /tmp/probes/fz215_int.py <<'PYEOF' def show(s):     try:         print(repr(s), int(s))     except Excep
          0s bash   pwd && ls -la && git log --oneline -5 && ls ~/tools 2>/dev/null && echo '---' && ls /home/runner/work/ail-ci/a
          0s bash   python3 --version; git status --short; git log --oneline -15; grep -n "fz215\|2075907148\|pad ')" DEVLOG.md | 
          0s bash   cat ~/tools/cmp.sh; echo '---'; cat tools/cmp.sh 2>/dev/null; echo '---ail_check head'; sed -n '1,80p' AIL_CUR
          0s bash   d=/tmp/cmpbgLn; echo '--- py.out'; cat -A $d/py.out; echo '--- d.out'; cat -A $d/d.out; echo '--- g.out'; cat 

FINAL VERDICT: NOCHANGE  2026-11-02T10:08:04Z  (the worker changed nothing; no review was run)
