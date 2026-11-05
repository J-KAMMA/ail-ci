# job job-spec2c-11050906  started 2026-11-05T00:12:46Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Landed spec2b’s work on `job-spec2c-11050906` (integ did not already contain it). Final commits: `37ba8b11`, `2fe5b1cc`, `be885b9c`, `adcf7b4a`.

**Measurements** (base `06568d1` → head; callgrind, valgrind 3.22 extracted under `/tmp`):

| task | instructions before → after | binary bytes |
| --- | ---: | ---: |
| tally_lang | 19,988,037,073 → 19,585,727,750 (**−2.013%**) | 78,696 → 78,696 |
| berth_sim | 8,383,606,807 (unchanged) | 65,072 |
| chain_relax | 1,692,839,658 | 35,088 |
| echo_pack | 6,158,284,148 | 36,096 |
| ledger_bin | 5,390,483,896 | 61,128 |
| rail_transfer | 387,941,219 | 65,136 |
| scar_life | 356,750,945,902 | 44,728 |
| term_rank | 15,990,363,423 | 78,688 |
| ticket_audit | 13,095,191,273 | 112,552 |
| tree_fold | 8,935,993,271 | 86,544 |

The other nine tasks have byte-identical generated C and binaries, so their counts/RSS/compile times cannot move. `tally_lang` RSS stayed 1,628 KiB and compile ~2.83 s. The drop is below the old 3% bullet because the current integ base is already faster; landed under the owner’s newer “small zero-cost gain” rule. No task regressed.

**Verification:** 7 probe programs (`/tmp/probes`) match CPython on both builds, including empty/last/one-past-end `IndexError`, unequal lengths, aliasing/mutation, popcount through arg/list/attr/dict, `2**63−1`; negative popcount times out identically in CPython and both builds. `--debug-dir` mapping preserved. All 76 tally cases match. 8 targeted/test modules pass (0 failed), manifest `--check` passes. Not pushed, per rules.
[cost $0.0000, opencode tokens {"total": 5257729, "input": 215240, "output": 16904, "reasoning": 26289, "cache.write": 0, "cache.read": 4999296}]
    tool time: bash 27.0 min, edit 0.0 min
        394s bash   cat > /tmp/count9.py <<'PY' import importlib.util, random, subprocess, os, sys, time from pathlib import Path 
        224s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1800 python3 ../tools/par_check.py -j
        220s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1800 python3 ../tools/par_check.py -j
        116s bash   cat > /tmp/ctimes_alt.py <<'PY' import os, subprocess, tempfile, time, shutil, statistics from pathlib import 
        111s bash   cat > /tmp/ctimes_seq.py <<'PY' import os, subprocess, tempfile, time, shutil from pathlib import Path REPO=Pa
         89s bash   mkdir -p /tmp/meas/base /tmp/meas/head; export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/val
         82s bash   cat > /tmp/ctime2.py <<'PY' import os, subprocess, tempfile, time, shutil from pathlib import Path REPO=Path('
         71s bash   cd /tmp && export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/valgrind; timeout 600 valgrind -

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review — job-spec2c-11050906 (`work..HEAD` = 4 commits)**

**What the change really does (one line).** It adds a post-codegen textual pass `pyfunc._codegen_idioms` (run on `result`, `c_units` and `c_source_regions`) that (a) rewrites the exact generated popcount loop to a guarded SWAR popcount for `x >= 0`, keeping the original loop for negative x, and (b) merges two adjacent same-index `ail_list_span_get` reads of two fields of one struct into one shared in-range check with the two original checked reads as fallback. This matches the report; no benchmark/app or source-input edits.

**Claims checked**
- `integ` did not contain the work; HEAD's idiom block is byte-identical to `origin/job-spec2b-11032017`. Verified.
- Instruction count `tally_lang`: independently reproduced 19,988,036,404 → 19,585,727,063 (**−2.013%**), binary 78,696 → 78,696, RSS 1,628 KiB, compile ~2.63 s. Verified (report table matches the stored callgrind JSON).
- "Other nine tasks byte-identical" and "no task regressed": compiled all nine compare-lab sources on base and HEAD — generated C and binaries identical for every one. Verified.
- "7 probes match CPython on both builds; negative popcount times out identically": re-ran all; `pop_neg` returns 124 under `timeout 5` for CPython, HEAD and base. Verified.
- `--debug-dir` mapping preserved: base/head `native_report.json` both still contain `popcnt`/`ev`, with offsets shifted by the inserted lines only. Verified.
- "All 76 tally cases match": re-ran the task — 3 public + 72 hidden + perf, 0 failed. Verified.
- 8 listed test modules + `test_ail_safetynet` pass (`-j 2`); manifest `--check` passes. Verified.
- No uncommitted source edits (only the harness's untracked `.agent/pipeline.md`). Verified.

**My probes (`/tmp/rprobes`, both builds via `~/tools/cmp.sh`)**
- `pop_many.py`: popcount over 0..1024 plus 2²⁰, 2³¹−1, 2³¹, 2³², 2⁴⁰+12345, 2⁶²−1, 2⁶², 2⁶³−1 — same stdout.
- `pop_u.py` / `pop_local_u.py`: parameter/local named `u` (the SWAR temp name) — same stdout.
- `span_items.py`: structs reached via a list item, last/negative index, one-past-end raises `IndexError` — same output/exit.
- `span_dict.py`: struct reached through a dict value, first/last/negative index — same stdout.
- `no_feature2.py`: a different while-loop shape plus list access; generated C byte-identical to `/tmp/base` (also checked `no_feature.py`, `g00_000`, `g05_010`, `g22_018`, `g13_008`, `g02_012`).

**Pre-existing.** None observed; every probe matched CPython on HEAD.

**Not checked / note.** No gdev program in `~/corpus/gdev` contains either exact idiom (AST scan + textual scan), so no gdev instruction measurement was relevant; sampled gdev C is unchanged. The `tally_lang` drop is **−2.013%**, i.e. below the old “at least 3%” bullet; the report states this and lands under the task's newer owner rule (“a gain may be small if it costs nothing; land when instructions drop and nothing else gets worse”), which the measurements satisfy.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3166226, "input": 102023, "output": 9284, "reasoning": 31943, "cache.write": 0, "cache.read": 3022976}]
    tool time: bash 10.2 min
        144s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1200 python3 ../tools/par_check.py -j
        137s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1200 python3 ../tools/par_check.py -j
         87s bash   cd /tmp/base && export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/valgrind && timeout 700 pyt
         84s bash   cd /home/runner/work/ail-ci/ail-ci && export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/valgr
         54s bash   cd /tmp && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life term_rank ticket_audit 
         24s bash   cd /tmp && for p in /tmp/rprobes/*.py /tmp/probes/pop_probe.py /tmp/probes/span_probe.py /tmp/probes/span_edge
         19s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 lab/compare/run_task.py --task tally_lang --langs ai
         19s bash   cd /tmp && for t in tally_lang berth_sim; do rm -rf /tmp/th_$t /tmp/tb_$t; AIL_NO_CACHE=1 python3 /home/runner

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T02:22:47Z
