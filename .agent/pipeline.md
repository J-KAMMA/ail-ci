# job job-rbprog18_rr1-11051321  started 2026-11-05T04:22:01Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `4e43f756` on `job-rbprog18_rr1-11051321`.

**Cause:** the prog18 typed reach lowered `sorted(list_of_tuples)` to typed KEYSORT; its float-column NaN check raised a bare `ValueError`, so `test_ail_refuzz95::r_tuple` lost the required `refuzz95` name on the default build.

**Fix:** `AIL_CURRENT/python/pkg-v12/cruntime.py` KEYSORT now raises the same named `ValueError` as `ail_list_sort`. Kept the prog18 change and its test; updated docs/DIFFERENCES and manifest only.

**Probes (12, both builds, `/tmp/probes/`):**
- Match CPython: `p1_nanfree_tuple`, `p10_nan_elsewhere`, `p12_empty_negative`.
- Refused by name: `p2_nan_tuple_direct`, `p3_nan_tuple_reverse`, `p4_nan_second_field`, `p5_nan_keyfn`, `p6_nan_arg`, `p7_nan_listitem`, `p8_nan_attribute`, `p9_nan_dictvalue`, `p11_float_list_nan`.
- p6's default build says `ValueError` without the refuzz95 text; it is still refused by name, and is not one of the test's named-message cases.

**Final-commit tests:** `test_ail_refuzz95`, `test_ail_unified`, `test_ail_prog18`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6/6 modules, 0 failures. `update_manifest.py --check` passes. No push.
[cost $0.0000, opencode tokens {"total": 7277861, "input": 326930, "output": 11273, "reasoning": 14090, "cache.write": 0, "cache.read": 6925568}]
    tool time: bash 20.2 min, edit 0.0 min, read 0.0 min
        554s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_refuzz95 test_ail_
        484s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_refuzz95 test_ail_
         64s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_refuzz95 2>&1 | tail -60
         63s bash   cd /tmp/probes && mkdir -p results && for p in p*.py; do echo "===== $p ====="; timeout 600 bash ~/tools/cmp.s
          8s bash   cd /tmp/rt && for m in g d; do if [ "$m" = g ]; then export AIL_UNIFIED_FORCE=1; else unset AIL_UNIFIED_FORCE;
          8s bash   mkdir -p /tmp/probes /tmp/rt && cd /tmp/rt && cat > r_tuple.py <<'EOF' nan = float("nan") print(sorted([(1.0, 
          8s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 120 git fetch --quiet origin integ:refs/remotes/origin/integ && 
          8s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add -f /tmp/base 7e68aa6e >/tmp/wt.log 2>&1; echo rc=$?; ta

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `4e43f756` (work `3540fdc5`..HEAD)**

**What the change really does:** In `KEYSORT` (`python/pkg-v12/cruntime.py`), the float-column NaN stop now raises a `ValueError` carrying the same ``refuzz95`` message as the boxed `ail_list_sort`, instead of a bare `ail_raise_named`; the test change is docstring/comment only (no assertion or `NAMED`-set weakening); DEVLOGs, one DIFFERENCES row and the manifest are updated. Matches the report.

**Probes (15 own, `/tmp/rprobes`, both builds, HEAD vs `/tmp/rbasewt`):**
- Match CPython: `p1` NaN-free/reverse tuples, `p10` NaN elsewhere, `p11` empty/1-tuple/reverse/-inf/±0.0, `p12` int sort, `p14` NaN element with non-NaN key, `p15` constant int key, `p13`-adjacent no-key cases.
- Refused by name: `p2` NaN first tuple field, `p3` NaN second field, `p4` key lambda, `p5` tuple `.sort()`, `p6` argument, `p7` list item, `p8` attribute, `p9` float list, `p13` tuple-returning key lambda.
- HEAD: every probe matches CPython or stops with `ValueError`; all NaN-key cases now carry `refuzz95` except `p6` default build, which still says bare `ValueError` (allowed; not a test `NAMED` case).
- Base: `p2`, `p4`, `p6`, `p13` default build said bare `ValueError`; confirmed the exact regression by running the base test — it fails `('r_tuple', False, b'ValueError\n')` missing `refuzz95`.
- No-feature program (no sort) emits byte-identical C on both builds; `--debug-dir` diff shows only `native_report.json` temp paths.
- No false refusal: `p14`/`p15` (NaN value, non-NaN key) match CPython on both builds.

**Tests/report claims:**
- `test_ail_refuzz95`, `test_ail_safetynet`: pass on HEAD (`2 modules, 0 failed`); base fails as claimed. Verified.
- `update_manifest.py --check`: rc=0. Verified.
- Worker's 12 probes: verified all listed outcomes (including `p6`'s bare default-build `ValueError`). Verified.
- Worker's 6-module claim: 2 of 6 re-run and pass; `test_ail_unified`, `test_ail_prog18`, `test_ail_files`, `test_ail_corpus_findings3` not re-run (review scope says targeted modules + safetynet only). Unverified, not contradicted.
- Speed: not measured; change only constructs the message on the existing NaN failure path, no hot-path change.

**Pre-existing:** none blocking. The only differences found on base are the bare-`ValueError` messages this change is meant to fix.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 671387, "input": 38444, "output": 4755, "reasoning": 9436, "cache.write": 0, "cache.read": 618752}]
    tool time: bash 7.7 min
        191s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_refuzz95 test_ail_safetynet 2>&1 | 
         87s bash   cd /tmp/rprobes && for p in p*.py; do echo "===== $p ====="; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/$p /
         86s bash   cd /tmp/rprobes && for p in p*.py; do echo "===== $p ====="; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/$p /
         64s bash   cd /tmp/probes && for p in p*.py; do printf '%s: ' "$p"; timeout 300 bash ~/tools/cmp.sh /tmp/probes/$p /home/
         14s bash   cd /tmp/rbasewt/AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_refuzz95.Refuzz95Tests.test_nan_sor
         11s bash   cat > /tmp/rprobes/p14_nan_element_nonkey.py <<'EOF' nan = float("nan") print(sorted([(nan, "a"), (1.0, "b"), 
         10s bash   mkdir -p /tmp/rprobes/nf && cd /tmp/rprobes/nf && cat > p.py <<'EOF' xs = [1, 2, 3] d = {"a": xs} print(sum(xs
          0s bash   mkdir -p /tmp/rprobes /tmp/rbasewt; git worktree add -f /tmp/rbasewt work 2>&1 | tail -3; git -C /tmp/rbasewt 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T06:11:02Z
