# job job-pre59-10241246  started 2026-10-24T03:56:30Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing documented pre-existing difference, since the task’s `pitest` list contained no reproducible cases (`/tmp/probes/pitest2/*` and `repcon6/v04` are absent; not found in 283 remote branches or Actions history).

- Fixed `itertools.permutations` / `combinations` / `combinations_with_replacement` with negative `r`: both builds now raise `ValueError: r must be non-negative`; `r == 0`, `r > n`, and empty pools still match CPython. Row `C?-job-fuzz8-10220554-1` marked fixed.
- Commit `dadad2b`; added `test_ail_pre59.py`; DEVLOG and manifest updated, `--check` passes.
- Probes: `open_perm_neg`, `pre59_neg_r_basic`, `pre59_neg_r_sources`, `pre59_neg_r_bounds`, `pre59_neg_r_loop` — all `same stdout` on both builds.
- Tests on final commit: `test_ail_pre59`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 327s.
[cost $0.0000, opencode tokens {"total": 6455239, "input": 245467, "output": 21842, "reasoning": 11290, "cache.write": 0, "cache.read": 6176640}]
    tool time: bash 7.0 min, websearch 0.0 min
        329s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre59 test_ail_safetynet test_ail_files test_ail
         25s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre59 2>&1 | tail -30
         23s bash   mkdir -p /tmp/probes cat > /tmp/probes/pre59_neg_r_basic.py <<'PY' import itertools def show(tag, fn):     try
         12s bash   python3 - <<'PY' import json,urllib.request allr=[] for p in range(1,6):  u=f'https://api.github.com/repos/J-K
          5s bash   cat > /tmp/probes/open_perm_neg.py <<'PY' import itertools def show(tag, fn):     try:         print(tag, list
          5s bash   bash ~/tools/cmp.sh /tmp/probes/open_perm_neg.py $PWD 2>&1 | tail -30
          4s bash   mkdir -p /tmp/probes && cat > /tmp/probes/open_perm_neg.py <<'PY' import itertools for n, r in [(3, -1), (0, -
          4s bash   python3 - <<'PY' import urllib.request,subprocess,concurrent.futures,re out=subprocess.check_output(['git','ls

## review 0
[model opencode/deepseek-v4.1-flash-free]
​VERDICT: ACCEPT

**What the diff really does:** adds an `r < 0` `ValueError("r must be non-negative")` check before the "r larger than pool" early exit in `ail_it_permutations`, `ail_it_combinations` and `ail_it_combinations_wr` (`AIL_CURRENT/python/pkg-v12/cruntime.py:20120,20160,20187`); adds `test_ail_pre59.py`, a DEVLOG entry, updates the DIFFERENCES row and manifest. This matches the report.

**Probes (HEAD, both builds; base compared where different):**
- `p1_basic` negative/zero/`r==n`/`r>n`/empty pool, keyword `r`, booleans, expressions: fixed; only pre-existing `r=None` lines remain.
- `p2_sources` r via function argument, list item, attribute, dict value + valid values: both same stdout.
- `p3_catch` `try/except ValueError`, for-loop, direct call, generator input: both same stdout; base returned `[]`.
- `p6_typedloop`, `p7_direct_literal` typed/default path, unpacking, literal negative r: both same stdout.
- `p8b_width` `-1` through int64 min: both same stdout.
- `p9_alias` list mutated after snapshot: both same stdout.
- Worker's five `/tmp/probes` probes re-run: all `same stdout` on both builds.
- `p4_unrelated`: unchanged output.

**Pre-existing (identical on base, not blocking):**
- `permutations(xs, None)` / `r=None` returns `[()]` instead of CPython's full permutations (`p1_basic`).
- float/str `r` accepted then `AIL internal error: out of memory`, exit 1 (`p5_types`); CPython raises TypeError.
- Literals `2**63`/`10**19` fail at compile with `integer overflow` (`p8_wide`).

**Tests on HEAD:** `test_ail_pre59` 23.5s ok; `test_ail_safetynet` 121.2s ok (2 modules, 0 failed). `update_manifest.py --check` rc=0.

**Claims:** negative-r fix on both builds — verified; `r==0`, `r>n`, empty pools still match — verified; typed path already checked in `itlib.PoolStream` — verified (`itlib.py:546`); commit/manifest/DEVLOG — verified; pitest probes absent — verified locally.

**Unverified:** the "283 remote branches" claim; instruction-count speed (perf_event_open denied; the added branch is O(1) per call, not per element); `--debug-dir` C comparison (flag produced no files in my runs; change is runtime-only with no codegen edits).
[cost $0.0000, opencode tokens {"total": 1470983, "input": 50491, "output": 8311, "reasoning": 12782, "cache.write": 0, "cache.read": 1399399}]
    tool time: bash 4.3 min
        123s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre59 test
         30s bash   date; cd /tmp/rprobes; for p in p1_basic p2_sources p3_catch p4_unrelated p5_types; do echo "=== $p"; bash ~/t
         28s bash   date; cd /tmp/probes; for p in open_perm_neg pre59_neg_r_basic pre59_neg_r_sources pre59_neg_r_bounds pre59_ne
         17s bash   cd /tmp/rprobes; for p in p1_basic p3_catch p5_types; do echo "=== BASE $p"; bash ~/tools/cmp.sh /tmp/rprobes/
         16s bash   cd /tmp/rprobes; for p in p1_basic p3_catch p5_types; do echo "=== HEAD $p"; bash ~/tools/cmp.sh /tmp/rprobes/
         11s bash   cd /tmp/rprobes; for p in p6_typedloop p7_direct_literal; do echo "=== HEAD $p"; bash ~/tools/cmp.sh /tmp/rpro
         10s bash   cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount /home/runner/work/ail-ci/ail-ci/tools/icount.c 2>
          6s bash   cd /tmp/rprobes && cat > p8_wide.py <<'PY' import itertools def show(tag, fn):     try: print(tag, list(fn()))

FINAL VERDICT: ACCEPT  2026-10-24T04:19:31Z
