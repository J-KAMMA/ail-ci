# job job-fz224-11040640  started 2026-11-03T21:40:49Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**No difference reproduced on this tree; nothing changed or committed.**

- Saved the reproducer as `/tmp/probes/fz224.py`; `python3 lab/fuzz/gen.py 2076020658` produces byte-identical source.
- `bash ~/tools/cmp.sh /tmp/probes/fz224.py $PWD`: both `g` and `d` builds `same stdout`.
- Explicit builds: `AIL_IR=0`, `AIL_IR=1`, `AIL_UNIFIED_FORCE=1` with each, and `cmpu.sh` on/off — all match CPython 3.12.3.
- `python3 lab/fuzz/run.py --start 2076020658 --count 1 --modes default,ir`: `default` 1 same, `ir` 1 same; 0 DIFF.

The old AIL output had the `h0(...)` side effects emitted twice inside the `try`/`finally`; the current base no longer does. No other differences observed.
[cost $0.0000, opencode tokens {"total": 704058, "input": 57813, "output": 5450, "reasoning": 6683, "cache.write": 0, "cache.read": 634112}]
    tool time: bash 2.8 min, write 0.0 min
         37s bash   cd /tmp/probes && d=$(mktemp -d /tmp/allcmpXXXX) && cp fz224_orig.py $d/p.ail && cd $d && python3 p.ail > py.o
         29s bash   cd /tmp/probes && for i in 1 2 3; do d=$(mktemp -d /tmp/repXXXX); cp fz224_orig.py $d/p.ail; (cd $d && python3
         22s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/fuzz/run.py --start 2076020658 --count 1 --jobs 1 --modes de
         20s bash   cd /tmp/probes && bash ~/tools/cmp.sh /tmp/probes/fz224.py /home/runner/work/ail-ci/ail-ci
         19s bash   python3 - <<'PY' import re s=open('/home/runner/work/_temp/t1/work0.md').read() m=re.search(r'```python\n(.*?)
         19s bash   cd /tmp/probes && bash ~/tools/cmpu.sh /tmp/probes/fz224_orig.py /home/runner/work/ail-ci/ail-ci
         10s bash   cd /tmp/probes && d=$(mktemp -d /tmp/pycmpXXXX) && cp fz224_orig.py $d/p.ail && cd $d && python3 p.ail > py.ou
         10s bash   cd /tmp/probes && d=$(mktemp -d /tmp/ircmpXXXX) && cp fz224.py $d/p.ail && cd $d && python3 p.ail > py.out 2>p

FINAL VERDICT: NOCHANGE  2026-11-03T21:46:09Z  (the worker changed nothing; no review was run)
