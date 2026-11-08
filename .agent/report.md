# job job-stdfall2c-11081553  started 2026-11-08T06:56:02Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed as `31c6e73` (not pushed).

**Fixes**
- `copy.deepcopy(x, memo)`: removed the process-global `_memo_links` / `d[len(d)]` side table. Each copied object now gets an integer identity token plus one keep-alive list stored *inside the caller's dict*; `memo.clear()` no longer returns stale copies and pre-existing keys are never overwritten. `len(memo)` grows by the same two entries per object as CPython, and all module-added keys are ints.
- `marshal`: restored all six lab programs to `marshal.dumps(x)` (no program edit). `version` is now required and positional-only, so CPython's default v4 is a **build-time** named refusal (`marshal.dumps() called without a required argument version`); explicit v0/1/2 stay byte-exact, explicit 3/4 is a named `ValueError`. Also added the missing reader for version-0/1 text floats (`f`), so `loads(dumps(x, 0/1))` round-trips.

**Probes** (default + `AIL_UNIFIED_FORCE=1`, both match CPython)
`q_copy_memo_clear`, `q_copy_memo_keys` (now `x y 4 [7]`), `q_copy_memo_reuse`, `q_copy_memo_nested`, plus clear/reuse-same-object, equal-distinct objects, atomic no-entry, and non-int-key deletion. `marshal.dumps(x, 0/1/2)` byte/round-trip probe matches; v3/4 lines are the named refusal.

**Tests on final commit** (`par_check -j 2`): `test_ail_std_stdfall2`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` clean.

`RESULTS.md` now records **After: 9/18** (copy 4/6, timeit 5/6, marshal 0/6): the six marshal programs are build-time refusals because v4 depends on CPython refcounts/interned bits and cannot be made exact. `test_ail_third_party_notices` and `test_ail_std_stdfall1` do not exist on this tree, as the review noted.
[cost $0.0000, opencode tokens {"total": 11636749, "input": 152269, "output": 23649, "reasoning": 54111, "cache.write": 0, "cache.read": 11406720}]
    tool time: bash 42.1 min, edit 0.0 min, read 0.0 min
        444s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 -B tools/par_check.py -j 2 test_ail_std_stdfa
        353s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 -B tools/par_check.py -j 2 test_ail_std_stdfa
        344s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 -B tools/par_check.py -j 2 test_ail_std_stdfa
        195s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; python3 -B test_ail_std_stdfall2.py 2>&1 
        177s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q_copy_memo_clear q_copy_memo_keys q_copy_memo_reuse q_copy_mem
        176s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py >/dev/null 2>&1; for p in q_copy_memo_c
        120s bash   ls -la /tmp/probes/ /tmp 2>/dev/null | head -60; find / -name 'q_copy_memo*' 2>/dev/null | head
        120s bash   cd /home/runner/work/ail-ci/ail-ci && for d in copy timeit marshal; do for f in lab/stdlib/$d/*.py; do echo "=

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review 2

**What the change really does:** `copy.deepcopy(x, memo)` drops the process-global `_memo_links` table and keeps its memo state (integer token key + one keep-alive list of originals) inside the caller's dict; `marshal.dumps`/`dump` make `version` a required positional-only argument (so the CPython v4 default is a build-time named refusal), restore the six lab programs to `marshal.dumps(x)`, and add a reader for version-0/1 text floats.

**Verified (probes in `/tmp/rprobes`, both builds, `cmp.sh`):**
- `q1_clear` (`memo.clear()` then reuse): `[1]` / `[1, 2]` — matches CPython (old stale `[1]` gone).
- `q2_keys` (`{2:"x",5:"y"}`, `deepcopy([7],m)`): `x y 4 [7]` — matches CPython; pre-existing keys intact.
- `q8_len` (`[[7]]`): `x y 5 [[7]]` — length growth matches CPython's `memo[id(x)]`+`_keep_alive` pattern.
- `q3_reuse`, `q4_clear_indep`, `q10_distinct`, `q11_listval`, `q13_atomic`, `q9_negkey` (-3e6 key): all match CPython.
- `q5_cycle` (self-list/self-dict), `q6_shared`, `q12_tuples` (shared/aliased tuple): all match CPython.
- `qm1_default`: both builds stop at build time with `not in the subset: marshal.dumps() called without a required argument version`. `qm3_kw`: CPython itself raises `TypeError: ... takes no keyword arguments`; HEAD gives a named build refusal. Consistent.
- `qm2_v012`, `qm6_bounds` (int32/int64 boundaries, ±inf, -0.0, 1e300, UTF-8, bytes, containers × v0/1/2): byte-exact hex and round-trip match CPython.
- `qm4_explicit4`: named `ValueError ... version 4 needs ... refcount ... pass version=2`; acceptable loud refusal.
- No-feature probe `nofeat2`: `--debug-dir/program.c` byte-identical between HEAD and `/tmp/base`.
- `par_check -j 2 test_ail_std_stdfall2 test_ail_safetynet`: 2 modules, 0 failed. `update_manifest.py --check` clean. `test_ail_third_party_notices`/`test_ail_std_stdfall1` absent as the review said.
- Report claims: memo side-table removal, clear/reuse, key preservation, len growth, int keys, restored programs, build-time v4 refusal, v0–2 byte-exactness, v3/4 named refusal, v0/1 float reader — all **verified**. Exact worker probe files and the two extra test modules (`test_ail_files`, `test_ail_corpus_findings3`) — **unverified** (not rerun per instructions).
- Wording nit: "two entries per object" is really 2 for the first object and 1 for each later one (same total as CPython); behaviour is correct.

**Defects:** none caused by this change.

**Pre-existing:** `marshal.loads(b"")` EOFError text and non-int `version` argument validation differ; unchanged reader/`_version`. Also `dumps(x, version=...)` keyword is now a build refusal, but CPython itself rejects keywords, so this is not a regression.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, CI shards, the worker's exact probe filenames. Speed not applicable (no compiler/runtime/bench file, and no gdev program uses `copy`/`marshal`).

**Note:** `DEVLOG.md` is outside the original allowed-file list but is required by the "Rules for every job"; content is consistent with observed behaviour.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1208953, "input": 63892, "output": 6164, "reasoning": 22097, "cache.write": 0, "cache.read": 1116800}]
    tool time: bash 9.6 min
        199s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 900 python3 -B tools/par_check.py -j 2 test_a
        152s bash   cd /home/runner/work/ail-ci/ail-ci for p in q1_clear q2_keys q3_reuse q4_clear_indep q5_cycle q6_shared q7_emp
         64s bash   cd /home/runner/work/ail-ci/ail-ci cat > /tmp/rprobes/q9_negkey.py <<'EOF' import copy m = {-3000000: 1} a = c
         63s bash   cd /home/runner/work/ail-ci/ail-ci for p in qm1_default qm2_v012 qm3_kw qm4_explicit4 qnofeat; do   echo "====
         25s bash   cd /home/runner/work/ail-ci/ail-ci cat > /tmp/rprobes/qm6_bounds.py <<'EOF' import marshal vals = [2**31-1, 2*
         23s bash   cd /home/runner/work/ail-ci/ail-ci cat > /tmp/rprobes/q13_atomic.py <<'EOF' import copy m = {} for x in (5, -0
         22s bash   cd /home/runner/work/ail-ci/ail-ci cat > /tmp/rprobes/q12_tuples.py <<'EOF' import copy a = [1] t = (a,) x = [
         21s bash   cd /home/runner/work/ail-ci/ail-ci # Build HEAD once to inspect actual memo dict behavior via a probe printing

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T09:22:23Z
