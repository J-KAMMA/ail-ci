# job job-relrterr-11030727  started 2026-11-02T22:27:54Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `6385a32` on `job-relrterr-11030727` (not pushed, per runner instructions).

- Default typed build now prints `Name: message` plus `  raised near file:line`; caught exceptions and exit codes unchanged.
- New `test_ail_runtime_error_names` covers index/key/zero/recursion/pop/explicit-raise and a caught `IndexError`, default and `AIL_UNIFIED_FORCE=1` (unified recursion skipped: still segfaults).
- Gate modules, required tests (`safetynet`, `files`, `corpus_findings3`), and pin-updated modules all pass.
- Binary growth on the 10 compare tasks: +4,336 to +20,632 bytes; before/after values are in `DEVLOG.md`. This exceeds the original 512-byte budget because the owner decision adds a per-statement site string.
- Icount could not be measured here: `perf_event_open` is denied (`perf_event_paranoid=4`) and valgrind/callgrind is unavailable. All 20 `/tmp/probes` cases matched CPython stdout/exit except the known unified recursion segfault.
[cost $0.0363, opencode tokens {"total": 3082305, "input": 74337, "output": 10621, "reasoning": 16355, "cache.write": 0, "cache.read": 2980992}]
    tool time: bash 9.4 min
        187s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_a
        186s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_runtime_error_names test_ail_sa
         84s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 tools/par_check.py -j 2 test_ail_runtime_erro
         48s bash   cat > /tmp/probes/sizes.py <<'PY' import os, subprocess, sys, tempfile, json from pathlib import Path REPO=Pat
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/cases/*.py; do echo "######## $(basename $p)"; bash
          8s bash   python3 - <<'PY' from pathlib import Path p=Path('/home/runner/work/ail-ci/ail-ci/AIL_CURRENT/test_ail_runtime
          7s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 tools/par_check.py -j 2 test_ail_runtime_erro
          6s bash   mkdir -p /tmp/probes && cat > /tmp/probes/run.py <<'PY' import os, subprocess, sys, tempfile from pathlib impo

## review 0 failed to run:           0s bash   git worktree add /tmp/base work >/dev/null 2>&1 || echo exists; git rev-parse work; sed -n '1,120p' AIL_CURREN           0s bash   cd /home/runner/work/ail-ci/ail-ci; grep -rn "fflush(stdout); fputs(w, stderr); AIL_DBG_UNCAUGHT" AIL_CURRENT  (cut off after 60 minutes) 

## review 0
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-11-03T01:47:36Z
