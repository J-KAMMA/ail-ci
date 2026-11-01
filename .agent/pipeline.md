# job job-i64tests1-11011225  started 2026-11-01T03:28:08Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done — committed as `37efd92`.

**What changed**
- Removed the `AIL_EXACT_INT=1` `setUpModule` marks from `test_ail_pre425`, `test_ail_pre429`, `test_ail_pre433`, `test_ail_overflow_uncatchable`; int64 expectations now run in the default mode, with explicit exact-mode cases retained.
- `pre425`: default builds refuse routed wide augmented powers by name; exact builds match CPython.
- `pre429`: typed default wide `round()` is a named loud stop; forced general path raises catchable `OverflowError("integer overflow")`; constant wide `round()` is build-refused; exact matches CPython.
- `pre433`: keeps adaptive int64 refusal and adds exact-mode builds against CPython.
- `overflow_uncatchable`: runtime operands now come through `sys.argv` so the default reaches the overflow instead of refusing the constant; added an exact-mode CPython equality case.
- Added `test_ail_int64_edges` (7 tests) registered via `tests.d/test_ail_int64_edges.txt`, covering run-time power/round boundaries on typed, IR, forced-general and exact builds.
- No product code changed (`git show --name-only` has only tests, manifest pins and DEVLOG).

**Tests on final commit:** 53 run, 52 passed, 1 skipped (`windows target` — no zig). This includes the 5 targeted modules plus `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. `python3 tools/update_manifest.py --check` passes.

**Probes (`/tmp/probes`)**
- `p425_direct`, `p425_listarg`, `p425_moddict`, `p425_modattr`: default builds refused by name (`int64 constant expression out of range`); exact matches CPython.
- `p425_safe`, `p425_box_pow`, `p425_dict_pow`: match CPython in all builds.
- `p425_argv` `(2,62)`, `(-2,63)`, `(0,0)`, `(2,-3)`, `(1,100000)`, `(-1,100001)`: match CPython; `(2,63)`, `(-2,64)`: typed/general named stop, exact matches.
- `p429_catch`, `_fn`, `_top`, `_unannot`, `_catch_finally`, `_bare`, `_exception`, `_negative`, `_dynamic`: typed named loud stop, general catchable, exact matches.
- `p429_uncaught`, `_finally_only`, `_value_only`: typed named stop; general keeps stdout prefix / finally; exact matches.
- `p429_routes`: default caught (declared int64 difference), exact matches CPython.
- `p429_inrange`, `p429_nonfinite`, `p429_argv` in-range/nan/inf: match CPython in all builds.
- `p429_constant`: default build refused by name, exact matches.
- `p429_argv` `9300000000000000000.0`, `-9300000000000000000.0`, `1e20`: typed named stop, general caught, exact matches.
- `p427_catchmul`, `p427_catchmul_inline`, `p_ovf_refused`: default named overflow stop, no handler output.

No silent mismatch and no real product bug found. The old pre429 claim that both int64 builds catch is stale: under the new default the typed path stops loudly, consistent with `test_ail_int64_default` and `test_ail_overflow_uncatchable`; only the forced general path catches.
[cost $0.0000, opencode tokens {"total": 4364901, "input": 106832, "output": 21832, "reasoning": 23117, "cache.write": 0, "cache.read": 4213120}]
    tool time: bash 22.5 min, edit 0.0 min
        623s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_pre425 test_ail_pr
        183s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_pre425 test_ail_pr
        158s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_pre425 test_ail_pr
        129s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_int64_edges 2>&1 |
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 - <<'PY' from pathlib import Path p=Path('test_ail_int64_
         32s bash   cat > /tmp/probes/runmodes.sh <<'EOF' #!/bin/bash # runmodes.sh SRC [exact] src=$1; exact=$2; d=$(mktemp -d /t
         29s bash   cd /tmp/probes && cat > p425_argv.py <<'EOF' import sys  def power(b, e):     b **= e     return b  try:     p
         17s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_overflow_uncatchab

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
# Review: job i64tests1 (37efd92)

**What the diff really does:** removes the `AIL_EXACT_INT=1` `setUpModule` marks from `test_ail_pre425/429/433` and `test_ail_overflow_uncatchable`, rewrites their assertions to expect default int64 behaviour while retaining explicit exact-mode equality cases, and adds `test_ail_int64_edges` (7 tests, registered via `tests.d/`, manifest refreshed), plus DEVLOG. No product/runtime source is touched (only `test_*`, `tests.d/`, `manifest.d/`, DEVLOG).

**Checks run**
- `par_check.py -j 2 test_ail_pre425 test_ail_pre429 test_ail_pre433 test_ail_overflow_uncatchable test_ail_int64_edges test_ail_safetynet`: 6/6 modules ok (263 s).
- `python3 tools/update_manifest.py --check`: exit 0.
- Non-feature C comparison (`--debug-dir`) HEAD vs `/tmp/base` for a plain list/dict/class/power program: `program.c` identical (only temp paths in `native_report.json`).

**Probes (`/tmp/rprobes`, cmp.sh on HEAD and base)**
- `p_round_const` (`round(1e20)` literal): named refusal "not in the subset: round() ..." in both d/g; exact prints `100000000000000000000` matching CPython.
- `p_round_dynamic` (1e20 computed in a loop): typed → exit 1 `integer overflow in round()`; general → `caught 'integer overflow'`; identical on base (declared C74/A1).
- `p_round_route` (list item/attribute/dict value): both builds print `caught`, CPython prints the exact big int; identical on base (declared difference).
- `p_pow_const` (`x **= 63`): named "int64 constant expression out of range" in both builds.
- `p_pow_runtime` (argv, d/g/e/eg): 2**62, -2**63, 10**18, 0**0, 2**-3, 1**100000, (-1)**100001 match CPython; 2**63, -2**64, 10**19 are loud stops in default/general and match CPython in exact.
- `p_defpow` (default parameter `10**40`): d/g named refusal; exact matches CPython.
- `p_safe` (no feature): matches CPython; C identical to base.

**Report claims:** all verified (default-mode refusal/stop/catchable split, exact-mode equality, new module, manifest check, no product change). Module run confirms the targeted tests on HEAD; the "53 run / 1 skip" count was not independently recounted.

**Pre-existing:** wide `round()` differences (typed loud stop, general catchable/route `caught` instead of CPython's unbounded int) are present identically on `/tmp/base` and are the declared C74/A1 int64 difference; they do not block.

VERDICT: ACCEPT
[cost $0.0205, opencode tokens {"total": 942324, "input": 58409, "output": 4784, "reasoning": 10395, "cache.write": 0, "cache.read": 868736}]
    tool time: bash 4.9 min
        264s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre425 test_ail_pre42
         11s bash   for f in p_round_const p_round_dynamic p_pow_const p_safe p_round_route; do echo "===== $f"; bash ~/tools/cmp.
          7s bash   d=$(mktemp -d /tmp/rpowXXXX); cp /tmp/rprobes/p_pow_runtime.py $d/p.py; cd $d for mode in d g e eg; do   case 
          4s bash   d1=$(mktemp -d /tmp/dbghXXXXXX); d2=$(mktemp -d /tmp/dbgbXXXXXX); echo $d1 $d2 for pair in "w2:$d1" "base:$d2"
          4s bash   for f in p_round_route p_round_dynamic; do echo "===== base $f"; bash ~/tools/cmp.sh /tmp/rprobes/$f.py /tmp/b
          2s bash   cd /tmp/rprobes && cat > p_defpow.py <<'EOF' def f(x=10):     print(x**40)  f() EOF for m in d g; do   d=$(mkt
          1s bash   cd /tmp/rprobes && cat > p_round_dynamic.py <<'EOF' def grow(n: float) -> float:     v: float = n     for _ in
          1s bash   d=$(mktemp -d /tmp/rrconstEXXXX); cp /tmp/rprobes/p_round_const.py $d/p.py; cd $d; AIL_EXACT_INT=1 AIL_NO_CACH

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T05:24:08Z
