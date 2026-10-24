# job job-gcroot-10241807  started 2026-10-24T09:08:26Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
Failed to fetch model list: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.
deepseek-v4.1-flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at nde (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc
DeepSeek-V4.1-Flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at nde (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

- `base_gc.c` does not exist anywhere in the repo or its history, so I audited the actual general-path runtime.
- Found a real heap-use-after-free in `statistics`: `ail2q_partials` and `ail2q_ssd_dd` kept fresh heap objects in unrooted C locals while boxing more elements. `AIL_GC_STRESS` collects at every allocation and ignores the `AIL2Z_PAUSE` threshold, so the objects were freed.
- Fixed both in `AIL_CURRENT/python/pkg-v12/statbrt.py:123` and `:177` with `AIL_ROOT1` / `AIL_ROOT_N`.
- Checked `jsonbrt.py`; its `ail_tuple_new` already roots the supplied item array, so no change was needed.
- Added `statistics_partials` regression coverage in `AIL_CURRENT/test_ail_gcstress.py:171,315`; verified it fails with the old runtime (`heap-use-after-free ... ail2q_partials`) and passes now.
- Probes `gc_stats_scalar/alias/empty/types` match CPython in both `g` and `d` builds.
- Final required tests on commit `053e68c` all pass: `test_ail_gcstress`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_gcfix`, `test_ail_gcroots` (6 modules, 0 failed).
- Manifest check passes; branch `job-gcroot-10241807` is clean apart from the pre-existing untracked `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 9570771, "input": 250471, "output": 16259, "reasoning": 20329, "cache.write": 0, "cache.read": 9283712}]
    tool time: bash 33.2 min
        746s bash   cd /home/runner/work/ail-ci/ail-ci && ls corpus/gdev/*.py | tail -n +201 | xargs -P 2 -n 1 /tmp/stress_one.sh 
        459s bash   cat > /tmp/stress_one.sh <<'SH' #!/bin/bash f="$1"; base=$(basename "$f" .py); d=$(mktemp -d /tmp/gcs-XXXXXX) 
        296s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_gcstress test_ail_safetynet test_ail_files test_
        211s bash   cat > /tmp/run_stress_safety.py <<'PY' import os, sys, subprocess, tempfile, traceback sys.path.insert(0,'/hom
         61s bash   cd AIL_CURRENT && timeout 1200 python3 -m unittest -v test_ail_gcstress 2>&1 | tail -60
         44s bash   cat > /tmp/one_stress.py <<'PY' import os,sys,subprocess,tempfile sys.path.insert(0,'/home/runner/work/ail-ci/
         39s bash   git log --all --oneline -- '*base_gc.c' | head; git log --all --oneline -- '*gc.c' | head; git ls-tree -r --na
         28s bash   mkdir -p /tmp/probes && cat > /tmp/probes/gc_stats_scalar.py <<'PY' import statistics  def main():     data = 

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change (one line):** roots the result list in `ail2q_partials` and the two-element tuple array in `ail2q_ssd` across the boxing/tuple allocations, so `-DAIL_GC_STRESS` collections cannot free them; adds a stress regression, manifest hashes and a DEVLOG entry.

**Probes** (`bash ~/tools/cmp.sh ... $PWD`, both `g`/`d`):
- p1 stats via arg, list item, attribute, dict value, tuple: **same stdout**, both builds.
- p2 empty `mean/fmean/pvariance/variance/pstdev/stdev`: **same stdout**, both builds.
- p3 negative/zero/alias/1e9-ints: same exit and error; one **pre-existing** difference (below).
- p4 no-statistics program: **same stdout**; `--debug-dir` `program.c` is byte-identical to `/tmp/base` in both `g` and `d`.
- p5 aliasing/copies/mutation: **same stdout**, both builds.
- HEAD under ASan + `-DAIL_GC_STRESS`: p1, p2, p3, p5 all **no sanitizer report**; p1 output matches CPython. Base under the same build on p1: **`heap-use-after-free ... in ail2q_partials`**.

**Tests on `053e68c`:** `test_ail_gcstress` 62s and `test_ail_safetynet` 98s, 2 modules, **0 failed**. `python3 tools/update_manifest.py --check` exits 0.

**Report claims:** `base_gc.c` absent from tree and all history — verified. Stats UAF/rooting at `statbrt.py:123,177` — verified. `jsonbrt` relies on `ail_tuple_new` rooting its item array — verified (`cruntime.py:14918`). New regression test fails on base / passes on HEAD — verified by the same-fault ASan run above, and the HEAD test's variance path also reaches the fixed `ssd`. Six-module test run, worker's own named probes, and the speed claim — **unverified**: I ran only the required two modules; `icount` cannot run here (`perf_event_open: Permission denied`). The root push/pop is O(1) per stats call, not per element.

**Pre-existing:** `statistics.mean([1000000000,999999999,-7,0])` prints `499999998` in CPython but `499999998.0` in AIL (p3, line 4). Identical on `/tmp/base`, so not caused by this change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1519151, "input": 61298, "output": 7916, "reasoning": 16849, "cache.write": 0, "cache.read": 1433088}]
    tool time: bash 3.6 min
         99s bash   date +%H:%M:%S; cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_gcstress test_ail_s
         26s bash   for p in p2_stats_empty p3_stats_neg_alias p5_stats_dup_mutate; do echo "=== $p"; timeout 600 python3 /tmp/str
         24s bash   for p in /tmp/rprobes/p*.py; do printf '\nmain()\n' >> "$p"; done for p in /tmp/rprobes/p*.py; do echo "=== $p
         19s bash   cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c && echo icount-ok rm -rf /tmp/spee
         15s bash   cat > /tmp/rprobes/p2_stats_empty.py <<'PY' import statistics   def main() -> None:     try:         print("me
         10s bash   cat > /tmp/stress_check.py <<'PY' import os, sys, subprocess, tempfile from pathlib import Path wt = Path(sys.
         10s bash   date +%H:%M:%S; timeout 900 python3 /tmp/stress_check.py "$PWD" /tmp/rprobes/p1_stats_values.py 2>&1 | tail -3
          9s bash   rm -rf /tmp/cdiff; mkdir -p /tmp/cdiff/head /tmp/cdiff/base cp /tmp/rprobes/p4_no_stats.py /tmp/cdiff/head/p.a

FINAL VERDICT: ACCEPT  2026-10-24T09:57:56Z
