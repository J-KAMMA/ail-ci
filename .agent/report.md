# job job-pre21-10240310  started 2026-10-23T18:10:35Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the pre-existing float `%` signed-zero difference: `0.0 % -3.0` / `-0.0 % 3.0` kept `fmod`'s dividend sign in the boxed runtime and the unified inline path. Both now use `copysign(0.0, divisor)`, matching the typed path.

Commits: `64f3cd0`, `100a873`. Manifest `--check` clean.

Tests on final commit `100a873`: `test_ail_pre21`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (4/4, 153s).

Probes, both builds, all matched CPython: `mod_sign`, `mod_float`, `mod_chain`, `mod_aug`, `mod_arith`, `mod_edges`, `mod_zero_runtime`, `mod_zero_vars`, `mod_zero_more`, `mod_aliases`, `mod_nonzero_containers`, `test_zero_sign`. `mod_int64` was refused by name on the general build (`integer literal outside int64 range`); the default build matched.
[cost $0.0000, opencode tokens {"total": 3495884, "input": 94303, "output": 12249, "reasoning": 15252, "cache.write": 0, "cache.read": 3374080}]
    tool time: bash 7.9 min
        197s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre21 test_ail_safetynet test_a
        154s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre21 test_ail_safetynet test_a
         37s bash   cat > /tmp/probes/mod_edges.py <<'EOF' vals = [-9, -5, -3, -2, -1, 0, 1, 2, 3, 5, 9] for a in vals:     for b 
         28s bash   cat > /tmp/probes/mod_zero_more.py <<'EOF' def m(a, b):     return a % b print(divmod(0.0, -3.0)) print(divmod
         16s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' from pathlib import Path p = Path('AIL_CURRENT/python/
          8s bash   mkdir -p /tmp/probes && cat > /tmp/probes/mod_sign.py <<'EOF' print(7 % 3) print(-7 % 3) print(7 % -3) print(-
          8s bash   cat > /tmp/probes/mod_edges.py <<'EOF' vals = [-9, -5, -3, -2, -1, 0, 1, 2, 3, 5, 9] for a in vals:     for b 
          6s bash   cat > /tmp/probes/mod_zero_runtime.py <<'EOF' def m(a, b):     return a % b print(m(0.0, -3.0)) print(m(-0.0, 

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed commits `64f3cd0`, `100a873` (`git diff work..HEAD`).

**Change**
Float `%` zero remainders now take the divisor's sign (`copysign(0.0, y)`) in `ail_obj_mod`, `ail_op_mod`, and unified's inline fast path, matching `ail_ffloormod`.

**Probes (both builds, vs CPython 3.12)**
- p1_zero_routes: literals, variables, args, list/attr/dict, `repr` — same
- p2_int_operand: float/int mixed, bool — same
- p3_nonzero: negative/fractional/exact multiples — same
- p5_divmod_floor: `divmod`, `//`, `%`, signed zeros — same
- p6_subnormal: min subnormal / max double — same
- p7_untyped_boxes: arg/list/attr/dict routes — same
- p8_math_fmod: `math.fmod` still keeps dividend sign — same
- p9_nonfinite: inf/nan combos — same
- Worker probes `mod_zero_runtime`, `mod_zero_more` — same

Base `/tmp/base` differs on p1 and p5 (e.g. `0.0 % -3.0` gives `0.0`, `divmod(0.0,-3.0)` gives `(0.0, -0.0)`), so this is a genuine pre-existing difference now fixed. Default-build `--debug-dir` C for a non-feature program is byte-identical; general build differs only in the fixed shared runtime prelude.

**Pre-existing / not blocking**
- `tools/ci_shards.py --check` reports `test_ail_fuzz20`, `test_ail_fuzz22` unassigned on base too (plus new `test_ail_pre21`; CI spreads unassigned modules by name).
- Speed: `perf_event_open` is denied in this container, so instruction counts could not be measured; the change only adds a branch to float `%`.

**Tests on HEAD**: `test_ail_pre21` + `test_ail_safetynet` pass (2/2, 76s). `update_manifest.py --check` clean.

**Claims**: signed-zero fix, affected paths, commits, manifest — verified. All-probe match — spot-verified. `test_ail_files` / `test_ail_corpus_findings3` pass and `mod_int64` refusal — not rerun (out of review scope) / unverified.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1724825, "input": 55955, "output": 7915, "reasoning": 15131, "cache.write": 0, "cache.read": 1645824}]
    tool time: bash 2.2 min
         77s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre21 test
         20s bash   cd /tmp/rprobes && for p in p1_zero_routes p2_int_operand p3_nonzero p5_divmod_floor p6_subnormal p7_untyped_b
          9s bash   cd /home/runner/work/ail-ci/ail-ci && cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icoun
          7s bash   cd /tmp/rprobes && for p in p1_zero_routes p5_divmod_floor; do echo "===== BASE $p ====="; bash ~/tools/cmp.sh
          7s bash   ls /tmp/probes 2>/dev/null | head -30; echo ===; for f in /tmp/probes/mod_zero_runtime.py /tmp/probes/mod_zero
          4s bash   cd /tmp && rm -rf dbg2 && mkdir -p dbg2 && cd /tmp/dbg2 && AIL_UNIFIED_FORCE=1 AIL_NO_CACHE=1 AIL_QUIET_FALLBA
          4s bash   cd /tmp/rprobes && cat > p9_nonfinite.py <<'EOF' import math  def m(a, b):     return a % b  inf = math.inf na
          3s bash   cd /tmp/rprobes && cat > p8_math_fmod.py <<'EOF' import math  def m(a, b):     return a % b  print(repr(math.f

FINAL VERDICT: ACCEPT  2026-10-23T18:29:16Z
