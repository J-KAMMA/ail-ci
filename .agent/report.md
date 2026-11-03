# job job-spec2b-11032017  started 2026-11-03T11:18:27Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Cherry-picked `3e3ca704`, resolved only the DEVLOG/manifest conflicts, regenerated the manifest, re-verified, and committed as `aefa849` + `cedbeff` on `job-spec2b-11032017`. No code fixes were needed.

**Instructions (callgrind; base `8c2374a` → head)**

| task | before | after | delta |
| --- | ---: | ---: | ---: |
| tally_lang | 21,658,123,783 | 20,936,425,206 | **-3.332%** |
| berth_sim | 8,383,603,495 | 8,383,603,495 | 0 |
| chain_relax | 1,692,838,109 | 1,692,838,109 | 0 |
| echo_pack | 6,158,280,824 | 6,158,280,824 | 0 |
| ledger_bin | 5,390,483,239 | 5,390,483,239 | 0 |
| rail_transfer | 387,938,152 | 387,938,152 | 0 |
| scar_life | 356,750,942,696 | 356,750,942,696 | 0 |
| term_rank | 15,990,360,094 | 15,990,360,094 | 0 |
| ticket_audit | 13,095,520,634 | 13,095,520,634 | 0 |
| tree_fold | 10,362,321,298 | 10,362,321,298 | 0 |

`tally_lang`: binary `74,648 → 74,688` bytes, RSS `1,496 → 1,496 KiB`, compile `4.52 → 4.41 s` (fair alternating build alone: `4.381 → 4.330 s`). Other tasks keep identical bytes/instructions; RSS differences were noise. Full table is in the top DEVLOG entry.

**Probes** (`/tmp/probes`, both builds vs CPython): `pop_probe` and `span_probe` match CPython; covered empty list, last index, one-past-end `IndexError`, unequal-length lists in one loop, negative indices, and popcount via argument/list item/attribute/dict value. `pop_neg` times out identically in CPython and both builds.

**Tests:** all 76 tally cases match CPython; `test_ail_span_cache`, `test_ail_numeric_loops`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 31 tests pass, 1 skipped. Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 2644106, "input": 78589, "output": 10417, "reasoning": 14812, "cache.write": 0, "cache.read": 2540288}]
    tool time: bash 67.8 min
       1709s bash   export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/valgrind; python3 /tmp/measure_spec2.py /ho
        912s bash   export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/valgrind; python3 /tmp/measure_spec2.py /tm
        840s bash   export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/valgrind; python3 /tmp/measure_spec2.py /tm
        500s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest test_ail_span_cache test_ail_numeric_loops test_ail_safet
         44s bash   python3 - <<'PY' import importlib.util, tempfile, statistics, shutil from pathlib import Path roots={'base':Pa
         19s bash   cd AIL_CURRENT && python3 - <<'PY' import importlib.util, sys, json, tempfile from pathlib import Path root=Pa
         17s bash   d=$(mktemp -d /tmp/negXXXX); cp /tmp/probes/pop_neg.py $d/p.py; cd $d; for m in g d; do if [ "$m" = g ]; then 
          8s bash   git fetch origin job-spec2-11031052 && git log --oneline origin/job-spec2-11031052 | head -20

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** Adds a `to_c` post-pass (`_codegen_idioms`) that (a) rewrites the exact popcount loop to `if (x >= 0) return __builtin_popcountll(x);` and keeps the loop as the negative-value fallback, and (b) merges two adjacent same-index `ail_list_span_get` field reads into one shared bounds check with the two original checked reads as fallback. This matches the report.

**Verified**
- Diff `work..HEAD` = only `pyfunc.py`, `manifest.d/45.txt`, `DEVLOG.md`; no tests or benchmarks edited.
- All probes in `/tmp/rprobes` (plus the worker's) match CPython on both builds: `no_feature`, `pop_edge`, `pop_attr_dict`, `span_edge`, `span_mut`, `span_container`, `span_single`, `pop_probe`, `span_probe`. Covers popcount 0..2^63-1 via arg/list/attr/dict; span empty, last, one-past, negative, unequal lengths, aliasing, mutation, list-of-struct.
- Negative popcount: CPython, base and head all time out (rc 124); fallback retained.
- `no_feature` and `echo_pack` generated C are byte-identical to base (`/tmp/spec2base`); echo_pack binary bytes identical.
- Independent callgrind on `tally_lang`: **21,658,123,110 → 20,936,424,533 (−3.333%)**; RSS 1496→1496 KiB; compile 4.336→4.318 s. Claim confirmed.
- All 76 tally cases match (3 public + 72 hidden + perf correctness via `run_task`).
- Targeted tests pass (5 modules, 0 failed); manifest `--check` passes.

**Defects**
1. **Adoption gate failed on binary bytes.** `tally_lang` grew 74,648 → 74,688 bytes (+40). The task says adopt only if no compare-lab task gets worse in binary bytes; it does. (`run_task`/`stat`; stripped size is coincidentally still 67,800, but the reported built binary is larger.)
2. **`--debug-dir` mapping regression.** Functions containing either idiom lose their generated-C mapping because `_codegen_idioms` is applied to `info['c_units']` but not `info['c_source_regions']`, which `native_diagnostics.generated` prefers. Probe `pop_edge.py`: base `popcnt mapped=True c_line_start=3988`, head `mapped=False`. Probe `span_edge.py`: base `get mapped=True c_line_start=3516`, head `mapped=False`. Expected mapping preserved; actual lost.

**Pre-existing:** none found (both builds matched CPython; feature-free C unchanged).

**Unverified:** instruction counts for the other eight compare-lab tasks (only worker's numbers; I confirmed echo_pack C is identical, so its count cannot move).

VERDICT: FIX
1. tally_lang binary bytes 74,648 → 74,688 (+40) violates the explicit "no compare-lab task gets worse in … binary bytes" gate; expected ≤74,648. Revert or shrink the emitted code until the built binary does not grow.
2. `--debug-dir` native report loses `mapped=True` for `popcnt`/`get` on `pop_edge.py`/`span_edge.py` (base: mapped at lines 3988/3516; head: unmapped). Apply `_codegen_idioms` to `c_source_regions` as well, or stop using pre-rewrite bodies for diagnostic mapping.
[cost $0.0000, opencode tokens {"total": 3107379, "input": 83557, "output": 9949, "reasoning": 31473, "cache.write": 0, "cache.read": 2982400}]
    tool time: bash 12.2 min
        334s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_span_cac
        304s bash   cd /tmp && rm -f /tmp/m_head.json /tmp/m_base.json && export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/u
         23s bash   cd /tmp && rm -rf eppair && mkdir eppair && cd eppair && cp /home/runner/work/ail-ci/ail-ci/lab/compare/src/ec
         21s bash   cd /tmp/rprobes && for f in no_feature.py pop_edge.py pop_attr_dict.py span_edge.py span_mut.py /tmp/probes/po
         10s bash   cd /tmp && cat > /tmp/check_tally.py <<'PY' import importlib.util, sys, tempfile, shutil from pathlib import P
         10s bash   cd /tmp && rm -rf neg && mkdir neg && cd neg && cp /tmp/probes/pop_neg.py p.py && for w in head base; do if [ 
          5s bash   cd /tmp/stripsz && nm -a base 2>/dev/null | sed 's/^[0-9a-f]*//' | sort > nb.txt; nm -a head 2>/dev/null | sed
          5s bash   cd /tmp/rprobes && cat > span_container.py <<'EOF' class P:     def __init__(self, a: list[int], b: list[int])

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `12efd14`.

**Fixes**
- Replaced the `__builtin_popcountll` fast path with inline SWAR popcount. The builtin pulled in libgcc `__popcountdi2` (+40 bytes); `tally_lang` is now **74,648 → 74,648 bytes**.
- Applied `_codegen_idioms` to `c_source_regions` too. `--debug-dir` again maps `popcnt`/`ev` (all 22 functions mapped); the unified build was already unmapped at base.

**Measurements (tally_lang, callgrind)**
- Instructions: **21,658,122,794 → 20,933,098,586 (−3.348%)**
- Binary: **74,648 → 74,648 bytes**
- RSS: **1,496 → 1,496 KiB**
- Compile: **4.378 → 4.380 s** (3 alternating pairs)
- Other nine tasks: generated C byte-identical, same binary sizes, so instructions unchanged; the DEVLOG table carries their before/after numbers.

**Probes** — 11 programs, both builds, 22/22 match CPython, 0 diffs: `pop_probe`, `pop_swar`, `pop_attr_dict`, `pop_edge`, `span_probe`, `span_recheck`, `span_edge`, `span_mut`, `span_container`, `span_single`, `no_feature`. Covers empty/last/one-past-end, unequal lengths, negative indices, aliasing/mutation, popcount via argument/list/attr/dict, `2**63−1`, alternating-bit masks. Negative popcount times out (`rc=124`) in CPython and both builds.

**Tests on final commit** — 8 modules, 0 failed: span_cache, numeric_loops, native_diagnostics, build_reports, nested_lists, safetynet, files, corpus_findings3. All 76 tally cases match. Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 3881654, "input": 89293, "output": 14668, "reasoning": 13085, "cache.write": 0, "cache.read": 3764608}]
    tool time: bash 13.1 min, edit 0.0 min
        280s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_span_cache test_
        124s bash   cd /tmp && VALGRIND_LIB=/tmp/vg/usr/libexec/valgrind /tmp/vg/usr/bin/valgrind --tool=callgrind --cache-sim=no 
        119s bash   cd /tmp && VALGRIND_LIB=/tmp/vg/usr/libexec/valgrind /tmp/vg/usr/bin/valgrind --version && VALGRIND_LIB=/tmp/v
         50s bash   cd /tmp && rm -rf tall_fix && mkdir -p tall_fix && for t in berth_sim chain_relax echo_pack ledger_bin rail_tr
         49s bash   cd /tmp && rm -rf tall_base tall_fix && mkdir -p tall_base tall_fix && for t in berth_sim chain_relax echo_pac
         32s bash   cd /tmp && for f in /tmp/probes/pop_probe.py /tmp/probes/pop_swar.py /tmp/probes/span_probe.py /tmp/probes/spa
         26s bash   cd /tmp && python3 - <<'PY' import os,subprocess,tempfile,time,statistics,shutil runs={'base':[],'fix':[]} src
         26s bash   cd /tmp && rm -rf negfix && mkdir negfix && cp /tmp/probes/pop_neg.py negfix/p.ail && cd negfix && timeout -k 

## review 1 failed to run: [cost $0.0000, opencode tokens {}]     tool time:  (cut off after 60 minutes) 

## review 1
[model commandcode/deepseek-v4.1-flash]
(no final text)
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-11-03T14:53:35Z
