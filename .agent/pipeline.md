# job job-bigbench1-11041237  started 2026-11-04T03:39:20Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Two commits on `job-bigbench1-11041237` (not pushed, per the runner instruction):

- `6fddabc` — 5 annotated programs in `lab/bigbench/`; all build with `--exact-int` and match CPython 5/5.
- `1dd28cc` — measurement, profiling, single-limb multiply fast path, and `RESULTS.md`.

Results: geomean AIL/CPython ratio **1.1009 → 0.9990** (9.3% better); no program slower by >1%. `perf_event_open` was denied (`paranoid=4`, no root), so the Appendix B median-of-9 wall-time fallback was used. Profile via `gprof` showed `ail_bn_mul_school` at 66.7% for pidigits; the fix adds an `nb == 1` pass. RSS growth with spigot length: 10.9 MB at 500 digits → 12.7 MB at 8000.

Tests: `test_ail_bigint` (458 s), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass. Probes for big × small (including `2**32-1`, zero, negative, list/attribute/dict paths, both unified modes) match CPython. The 20 CI shards were not run because the job does not push.
[cost $0.0000, opencode tokens {"total": 2103900, "input": 38981, "output": 13706, "reasoning": 16781, "cache.write": 0, "cache.read": 2034432}]
    tool time: bash 18.9 min, write 0.0 min, edit 0.0 min
        463s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_co
        460s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_bigint 2>&1 | tail -40
         51s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/final_measure.py <<'PY' import os, resource, statistics, subproces
         38s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/measure_after.py <<'PY' import os, resource, statistics, subproces
         35s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/measure.py <<'PY' import os, resource, statistics, subprocess, sys
         28s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/rssgrow && python3 - <<'PY' from pathlib import Path s = Path('
         14s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/bb && mkdir -p /tmp/bb && for p in pidigits fib_big fact_mod powm
          9s bash   mkdir -p /tmp/probes && cd /home/runner/work/_temp/w2 && cat > /tmp/probes/bn_mul_small.py <<'PY' class Box:  

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Verification complete. Here's my report.

## What the change really does

`1dd28cc` adds an `nb == 1` fast path to `ail_bn_mul_school` (one direct pass, no `memset`, no read-modify-write), plus the `manifest.d/6a.txt` hash refresh; `6fddabc` adds five `lab/bigbench/` programs and `RESULTS.md`. That matches the report.

## Probes (`/tmp/rprobes/`, HEAD vs CPython, both build modes via `cmp.sh`/worker's `cmp_exact.sh`)

| probe | content | result |
|---|---|---|
| p1_sources | big×small from arg, list item, attribute, dict value; m = 0,1,2^31,2^32−1,2^32,2^32+1,−1,−(2^32−1) | same stdout g+d |
| p2_carry | max-limb a=2^64−1, 4096-bit run, 300× chained ×3, divmod after | same g+d |
| p3_alias | `*=` , list/dict/attribute overwritten after copy, tuple/str rebind | same g+d |
| p4_typed | typed path loop with big×small, negative, arg-passed operands | same g+d |
| p5_nobig | int64-only program | same g+d |
| s4.py | safetynet S4 generator program | base and HEAD identical (5 lines, ~68 s, 1.28 GB) |

All C-core cases are also covered by `test_ail_bigint.test_core_operations` (4000 random pairs, 1–20000 bits). No defect found: `o[na]` writes exactly the allocated `na+nb`=na+1 limbs; the 64-bit carry bound holds; `b[0]=0`, `na=0` and non-normalised inputs are all handled.

`--debug-dir` on a non-big-int program: generated C differs **only** in the embedded `ail_bn_mul_school` body (the runtime is emitted unconditionally). Output identical.

## Tests

`test_ail_bigint`: **ok 584.3 s, 0 failed**. `test_ail_safetynet` failed once in my run only because I wrapped it in `ulimit -v 1500000`: S4 peaks at 1.28 GB and truncates. Run without that limit it passes, and the base binary behaves identically — harness artifact, not a defect. `update_manifest.py --check` passes.

## Report claims

- 5/5 programs equal to CPython, all general path — **verified** (rebuilt all five with `--exact-int`; all matched, all printed the general-path note).
- Speed-up keeps outputs, only `bigint_core.py` changed, geomean improves, no program >1% slower — **verified** on a quiet machine by CPU-time medians, pinned, interleaved: pidigits 270→188 ms, fact_mod 23.2→21.1, fib +0.5%, collatz −1.5%, powmod 1282→1257 (my earlier +5–26% readings were contention from the other agent's suite on this shared runner; base-vs-base swung 1311–1935 ms in the same window). Quiet numbers reproduce the worker's table within a few percent; ratio geomean ≈0.99.
- `perf_event_open` denied (paranoid=4) — verified; valgrind absent — verified.
- 20 shards not run — consistent with the no-push runner instruction.
- Exact ms columns, gprof profile, RSS-growth table, compile-time/binary-size columns — **unverified** (profile artefacts not kept; I did not rebuild the N-digit variants).

## Pre-existing

None found.

## Not checked

Instruction counts (no perf), the 20 CI shards, the profile and RSS tables.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=51 out_tokens=40259]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T06:03:24Z
