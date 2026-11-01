# job job-std_collections-11020410  started 2026-11-01T19:10:44Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `e39c388`.

**Defect confirmed:** `p_cmbranch` and `p_cmreassign` printed `Counter({1: 2, a: -3})` on HEAD vs CPython's `Counter({1: 2, 'a': -3})` on both builds.

**Fix:** `collib.py:chainmap_call` now accepts only a direct `ChainMap(...)` call or a name bound exactly once by a `ChainMap(...)` display and not also a parameter. Any other ChainMap name is refused by name, so the default build falls back to the general path, which matches CPython.

**Probes** (`/tmp/probes/fix/`, both builds):
- Match CPython: `p_cmbranch`, `p_cmreassign`, `p_cmname`, `p_cmdirect`, `p_cmsingle_str`, `p_cmalias`, `p_cmmixed`, `p_cmbranchsingle`, `p_keyswitch_store`, `p_keyswitch_update`, `p_keyswitch_subtract`.
- Refused by name: `p_cmparam` (ChainMap parameter).

**Verification:**
- `test_ail_std_collections`, `test_ail_collections`, `test_ail_tuples`, `test_ail_deqctr`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 7 modules, 0 failed.
- Re-ran `test_ail_std_collections` + `test_ail_safetynet` on the final commit: 0 failed.
- `term_rank` `program.c` byte-identical to HEAD; manifest `--check` exits 0.
[cost $0.0000, opencode tokens {"total": 2972999, "input": 66197, "output": 7784, "reasoning": 14538, "cache.write": 0, "cache.read": 2884480}]
    tool time: bash 11.8 min, edit 0.0 min, read 0.0 min
        438s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_std
        132s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_std
         45s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/term_head /tmp/term_fixed && cp /tmp/collib_head.py AIL_CURR
         37s bash   mkdir -p /tmp/probes/fix && cat > /tmp/probes/fix/p_keyswitch_store.py <<'EOF' from collections import Counter
         19s bash   mkdir -p /tmp/probes/fix && cat > /tmp/probes/fix/p_cmbranch.py <<'EOF' from collections import Counter, Chain
         16s bash   cd /tmp/probes/fix && for f in p_cmbranch.py p_cmreassign.py p_cmname.py; do echo "######## $f"; bash ~/tools/
         13s bash   cd /tmp/probes/fix && for f in p_cmname.py p_cmsingle_str.py p_cmdirect.py p_cmbranch.py; do echo "######## $f
          6s bash   cat > /tmp/probes/fix/p_cmreassign.py <<'EOF' from collections import Counter, ChainMap def main() -> int:    

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change does.** In `AIL_CURRENT/python/pkg-v12/collib.py`, `chainmap_call` now takes the inferred type, collects `Assign`/`AnnAssign` bindings for a `Name`, counts `Store` occurrences of that name in the function, and returns `_CM_AMBIGUOUS` for a parameter or a name not bound exactly once by a `ChainMap(...)` call; `ctr_subtract` then refuses such names by name. Plus manifest hash and DEVLOG. This matches the report, with two unmentioned details: `AnnAssign` bindings are now recognised, and nested `def`/`class` bodies are excluded from the store count.

**Probes** (`/tmp/rprobes`, both builds; worker probes `/tmp/probes/fix` re-run too).
- HEAD matches CPython on g+d: `p_cmbranch`, `p_cmreassign`, `p_cmreassign2`, `p_cmcallpos`, `p_cmannassign`, `p_cmloopvar`, `p_cmshadow`, `p_cmternary`, `p_cmargchain`, `p_nofeature`; worker `p_cmalias`, `p_cmbranch`, `p_cmbranchsingle`, `p_cmdirect`, `p_cmmixed`, `p_cmname`, `p_cmreassign`, `p_cmsingle_str`, `p_keyswitch_store/_subtract/_update`.
- Named refusals, identical on base: `p_cmparam`, `p_cmderived`, `p_cmnested`, `p_cmnested2` (acceptable).
- Base reproduces the review defect: `p_cmbranch`, `p_cmreassign2`, `p_cmcallpos` print `Counter({1: -2, a: -3})` (unquoted) vs CPython `'a'`; HEAD fixes all three.

**Claims.** Defect confirmed and fixed: verified. Probe list: verified (p_cmparam is a named refusal, not a general-path match, so the report's "default build falls back to the general path" overstates that probe). Tests: all 7 claimed modules pass (`test_ail_std_collections`, `test_ail_collections`, `test_ail_tuples`, `test_ail_deqctr`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`), 0 failed. Manifest `--check` exits 0. Compare tasks: all 10 checked; `berth_sim`, `echo_pack`, `ledger_bin`, `term_rank`, `ticket_audit` byte-identical; `chain_relax`/`rail_transfer` byte-identical with `--exact-int`; the other 5 fail identically on base and HEAD (same log, no C).

**Pre-existing** (identical on base): `p_cmmapsmut` (`cm = ChainMap({1: 4}); cm.maps[0] = {"a": 5}` prints `Counter({1: 2, a: -5})`, expected `'a'`), and the refusals `p_cmparam`/`p_cmderived`/`p_cmnested*`. Also not covered by the new store count: a nonlocal rebinding in a nested function (those programs are already refused identically on base).

**Unverified:** speed (compile-time-only change, no hot runtime path); wider suite (not run per instructions).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 781046, "input": 29565, "output": 6159, "reasoning": 17898, "cache.write": 0, "cache.read": 727424}]
    tool time: bash 16.9 min
        244s bash   date; cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cdiff && mkdir -p /tmp/cdiff/h /tmp/cdiff/b && for t i
        193s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
        149s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 800 python3 ../tools/par_check.py -j 2 test_ai
        136s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         91s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 700 python3 ../tools/par_check.py -j 2 test_ai
         47s bash   ls /tmp/probes/fix; for f in /tmp/probes/fix/p_*.py; do echo "### HEAD $(basename $f)"; bash ~/tools/cmp.sh $f
         45s bash   date; cd /tmp/rprobes && for f in p_*.py; do echo "######## BASE $f"; bash ~/tools/cmp.sh /tmp/rprobes/$f /tmp
         41s bash   date; cd /tmp/rprobes && for f in p_*.py; do echo "######## HEAD $f"; bash ~/tools/cmp.sh /tmp/rprobes/$f /hom

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T21:03:44Z
