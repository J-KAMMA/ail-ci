# job job-pre61-10241247  started 2026-10-24T03:54:14Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing pre39 case: `functools.partial` with bound values crashed during compilation (`'Lambda' object has no attribute 'lineno'`) on both builds. `genlib._partial` now copies the `partial()` call's source location onto every synthetic lambda. The earlier `range(x=1e300)` case is already a named compile-time refusal on this tree, so it needed no change.

Commit: `d61307a` (no push).

Tests on final commit: `test_ail_pre61`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 356 s, 0 failed. `update_manifest.py --check` passes.

Probes (both builds):
- Matched CPython: `pre61_partial_lambda`, `pre61_partial_routes2`, `pre61_partial_def`, `pre61_partial_basic`, `pre61_partial_types` (5).
- Refused by name: `pre61_partial_routes`, `pre61_partial_nested`, `pre61_partial_bad`, `pre61_partial_function_arg`, `partial_attr`, `pre61_range_kw` (6).

Not addressed: the admitted out-of-range attribute case remains pre-existing and was not probed further.
[cost $0.0000, opencode tokens {"total": 6054923, "input": 130192, "output": 13417, "reasoning": 18450, "cache.write": 0, "cache.read": 5892864}]
    tool time: bash 9.9 min, edit 0.0 min, read 0.0 min, write 0.0 min
        358s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre61 test_ail_genlib test_ail_safetynet test_ai
         47s bash   cat > /tmp/probes/pre61_partial_types.py <<'EOF' from functools import partial def join3(a, b, c):     return 
         42s bash   git add AIL_CURRENT/test_ail_pre61.py && python3 tools/update_manifest.py && python3 tools/update_manifest.py 
         28s bash   cat > /tmp/probes/rng_repr.py <<'EOF' for r in (range(3), range(1, 7), range(1, 7, 2), range(7, 1, -2), range(
         18s bash   cat > /tmp/probes/pre61_partial_routes2.py <<'EOF' from functools import partial def scale(a, b):     return a
         17s bash   for p in /tmp/probes/pre61_partial_basic.py /tmp/probes/pre61_partial_lambda.py /tmp/probes/pre61_partial_rout
         13s bash   cat > /tmp/probes/rng_misc.py <<'EOF' print(range(0, 3), range(5), range(10, 0, -2), range(0)) print(len(range
         13s bash   for p in /tmp/probes/rng_misc.py /tmp/probes/rng_index.py /tmp/probes/rng_err.py; do echo "### $p"; bash ~/too

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** Adds `ast.copy_location(..., node)` to the two synthetic lambdas built by `genlib._partial`, plus the new test module, manifest, DEVLOG and DIFFERENCES row. This matches the report.

**Probes** (`bash ~/tools/cmp.sh`, both `g`/`d`, HEAD vs `/tmp/base`):
- HEAD matches CPython where base crashes with `AttributeError: 'Lambda' object has no attribute 'lineno'` on both builds: partial of def/lambda with positional, keyword, empty, negative, bool/None/float/big-int values; values via argument, list item, dict value, attribute; global/local/parameter rebinding; list mutation and aliasing; side-effect argument evaluation; two partials on one line; all-keyword binding. Includes worker’s `pre61_partial_{basic,def,lambda,routes2,types}`.
- Refused by name on HEAD and base: non-def callable, too many bound args, nested partial, partial as map/key, keyword call through a function value; worker’s refused set reproduces.
- `range(x=1e300)` / `range(start=...)`: named refusal on base and HEAD, so already handled, not still-differing.
- Out-of-range attribute (`p24_attr_overflow.py`): runtime `integer overflow` identically on base and HEAD (pre-existing).
- No-feature programs: `program.c` identical to base for `p12_no_partial.py` and `g00_000.py`; only temp paths differ in `native_report.json`.

**Tests on HEAD:** `test_ail_pre61` + `test_ail_safetynet` 2 modules, 125 s, 0 failed; `test_ail_genlib` 42 s, 0 failed. `update_manifest.py --check` passes.

**Report claims:** fixed-case choice, the crash, the location-copy fix, the already-refused `range` case, all listed probe outcomes, and the pre-existing attribute case are **verified**. `test_ail_files` / `test_ail_corpus_findings3` results are **unverified** (not re-run per review scope). No false claims found.

**Speed:** no icount needed; generated C is unchanged for non-partial programs and the edit only adds AST locations on the partial path.

**Pre-existing:** out-of-range attribute overflow, nested partial and the other named refusals above behave identically on base.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 897843, "input": 44921, "output": 5898, "reasoning": 10416, "cache.write": 0, "cache.read": 836608}]
    tool time: bash 6.9 min
        127s bash   cd /home/runner/work/ail-ci/ail-ci; date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre61 
         56s bash   cd /home/runner/work/ail-ci/ail-ci; date; for f in /tmp/rprobes/*.py; do echo "##### $(basename $f)"; bash ~/t
         49s bash   cd /home/runner/work/ail-ci/ail-ci; date; for f in /tmp/probes/pre61_*.py /tmp/probes/partial_attr.py; do echo
         44s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; python3 ../tools/par_check.py -j 2 test_ail_genlib 2>&1 
         41s bash   cd /tmp/base; date; for f in /tmp/rprobes/*.py; do echo "##### $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD
         29s bash   cd /home/runner/work/ail-ci/ail-ci; date; for f in /tmp/rprobes/p1[3-8]*.py; do echo "##### $(basename $f)"; b
         22s bash   cat > /tmp/rprobes/p19_same_line.py <<'EOF' from functools import partial def f(a, b):     return a * b print(
         19s bash   cd /tmp/base; date; for f in /tmp/rprobes/p1[3-8]*.py; do echo "##### $(basename $f)"; bash ~/tools/cmp.sh "$f

FINAL VERDICT: ACCEPT  2026-10-24T04:20:34Z
