# job job-fz221-11032207  started 2026-11-03T13:09:06Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report — fz221 / seed 2076011679**

- Saved the reproducer as `/tmp/probes/fz221.py`; `python3 lab/fuzz/gen.py 2076011679` regenerates an identical program.
- `bash ~/tools/cmp.sh /tmp/probes/fz221.py $PWD`: **g same stdout**, **d same stdout**, both exit 0.
- Also tested explicitly: `AIL_IR=1` same, `AIL_IR=0` same, `AIL_UNIFIED_FORCE=1` with `AIL_IR=1` and `AIL_IR=0` same.
- `python3 lab/fuzz/run.py --start 2076011679 --count 1 --modes default,ir`: default **1 same**, ir **1 same**, no findings.
- Ran each compiled variant 10 times: byte-identical to CPython every time.
- The difference does **not reproduce on this tree** (`412dcdf`). The historical duplicate-output cause matches the already-fixed qtest5 concat-flatten bug (leaves evaluated twice); `test_ail_qtest5` passes (2/2).
- No code or test changes made and no commit, per step 1. No other differences observed.
[cost $0.0000, opencode tokens {"total": 1212659, "input": 65721, "output": 5584, "reasoning": 8298, "cache.write": 0, "cache.read": 1133056}]
    tool time: bash 0.7 min
          9s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/fuzz221 && python3 lab/fuzz/run.py --start 2076011679 --count 1 -
          8s bash   mkdir -p /tmp/probes && cat > /tmp/probes/fz221.py <<'PYEOF' def h0(a: int, b: int) -> int:     v1: int = b   
          5s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 PYTHONPATH=. python3 -m unittest -v test_ail_qtest
          4s bash   cd /tmp/cmpGaQa && for i in $(seq 1 10); do ./exe_d > r$i.out 2>/dev/null; cmp -s py.out r$i.out || echo "d di
          4s bash   cd /tmp/probes && d=$(mktemp -d /tmp/ir0XXXX); cp fz221.py $d/p.ail; cd $d; python3 p.ail > py.out 2>py.err; f
          4s bash   cat ~/tools/cmpu.sh; cd /tmp/probes && d=$(mktemp -d /tmp/irXXXX); cp fz221.py $d/p.ail; cd $d; python3 p.ail 
          3s bash   cd /tmp/probes && d=$(mktemp -d /tmp/ir0bXXXX); cp fz221.py $d/p.ail; cd $d; python3 p.ail > py.out 2>py.err; 
          2s bash   cat > /tmp/probes/fz221_min.py <<'PYEOF' def h0(a: int) -> int:     print(7)     return a   def h1(a: int) -> 

FINAL VERDICT: NOCHANGE  2026-11-03T13:11:46Z  (the worker changed nothing; no review was run)
