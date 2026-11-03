# job job-fz220-11032207  started 2026-11-03T13:08:06Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

- **Reproducer:** Confirmed on this tree (default, general, and `AIL_IR=1`): `cmp.sh` showed AIL stopping at the int64 round boundary while CPython printed `100000000000000000000`. The fuzzer already classifies the seed as declared `overflow` (fz2), but the raw output still differed.
- **Minimized construct:** one-argument `round()` of a constant float expression outside int64, e.g. `round(1e10 * 1e10)`.
- **Fix:** extended the pre54 boundary refusal to fold constant numeric expressions (`+ - * / // % **`, unary signs; depth/size caps). Such programs are now refused by name; runtime values keep the declared overflow contract; `--exact-int` still matches CPython.
- **Tests:** `test_ail_fz220` (7 tests) plus `test_ail_fz2`, `test_ail_pre429`, `test_ail_int64_edges`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **52 run, all OK, 1 skipped** (Windows target, no zig).
- **Fuzz seed 2076011178:** now `refused` in default and IR modes, **0 DIFF**.
- **Probes:** `fz220_min`, `_neg`, `_div`, `_bounds`, `_edge`, `_in`, `_routes` — wide constant expressions refused by name; in-range/non-finite/zero-division match CPython; arg/list/attr/dict runtime values match CPython under exact ints and stay inside the declared overflow contract otherwise.
- **Other differences seen:** none.
- **Commit:** `87a75fe`
[cost $0.0000, opencode tokens {"total": 2967367, "input": 101852, "output": 11615, "reasoning": 17420, "cache.write": 0, "cache.read": 2836480}]
    tool time: bash 14.0 min
        591s bash   python3 -m unittest -v test_ail_fz220 test_ail_fz2 test_ail_pre429 test_ail_int64_edges test_ail_safetynet tes
         63s bash   cat > /tmp/probes/fz220_edge.py <<'PY' for v in (1e308 * 10, 1.0 / 0.0, 1e-320 * 1e-10, (2.0 ** 62) - 2.0 ** 6
         53s bash   python3 -m unittest -v test_ail_fz220 2>&1 | tail -25
         51s bash   python3 -m unittest -v test_ail_fz220 2>&1 | tail -60
         50s bash   python3 - <<'PY' import pathlib p = pathlib.Path('AIL_CURRENT/test_ail_fz220.py') s = p.read_text() s = s.repl
         10s bash   cat > /tmp/probes/fz220_min.py <<'PY' print(round(1e10 * 1e10)) PY cat > /tmp/probes/fz220_neg.py <<'PY' print
          8s bash   mkdir -p /tmp/probes && cat > /tmp/probes/fz220.py <<'PYEOF' import sys  from dataclasses import dataclass   @
          5s bash   for f in fz220_min fz220_neg fz220_div fz220_in fz220_bounds fz220_routes; do echo "=== $f"; bash ~/tools/cmp.

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `87a75fe` (work..HEAD)**

**What the diff really does:** extends `_refuse_round_at_int64_boundary` in `AIL_CURRENT/python/pkg-v12/pyc.py` so a one-arg `round(<constant numeric expr>)` is folded (literals, unary `+/-`, `+ - * / // % **`, depth 32, int-size cap) when the expression contains a float literal, and refused by name when the folded value is `<= -2**63` or `>= 2**63`. Adds `test_ail_fz220.py`, `tests.d` registration, DEVLOG, DIFFERENCES, manifest shards. This matches the report; no bench/example edits.

**Probes (`bash ~/tools/cmp.sh`, HEAD + base; IR checked separately):**
- `p1` `round(1e10*1e10)`: HEAD refused by name in default/general/IR; base DIFF (overflow). **Fixed as claimed.**
- full `/tmp/probes/fz220.py` seed: HEAD refused default/general/IR; base DIFF at round overflow. **Fixed as claimed.**
- `p2` in-range constants (`1e5*1e10`, `(1e10*1e10)/1e10`, `(2.0**62)-2.0**62`, `-2.5*1e15`, subnormal, `1e20-1e20`, `1e20/1e20`, `1e20*0`, `1e20**0`, `0.1+0.2`, ±`9223372036854774784.0`): HEAD same stdout as CPython in all modes.
- `p4` no-feature program: HEAD same as CPython; `--debug-dir` `program.c` **byte-identical** to base.
- `p5`/worker routes (argument, list item, attribute, dict value `1e20`): HEAD == base, exit 1 with `integer overflow in round()`; declared int64 contract, not caused by the change.
- `p6` `round(10 ** -1000000000 * 1.0)`, `p11` NaN expression, worker `fz220_edge`: same as CPython; no hang.
- `p3` `round(10**20/1)`: HEAD == base, named `int64 constant out of range` (no float literal); pre-existing.
- Exact-int (`AIL_EXACT_INT=1`) on `p1`, `p2`, `p5`: all same as CPython, as claimed.
- Note (not a defect): HEAD now refuses `round(-(2.0**63))` / `round(-(2.0**62)*2.0)`, which base compiled and matched CPython. This is the documented lower-boundary rule (rounded value `-2**63`, where `abs`/`-`/`* -1` cannot be represented), and a named compile-time refusal is acceptable; the same rule already refused the literal `-9223372036854775808.0`.

**Tests:** `cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fz220 test_ail_safetynet` -> `2 modules, 0 failed`. `python3 tools/update_manifest.py --check` -> rc 0. Commit message has the required trailer.

**Claim check:** reproducer/minimized construct, fold extension + caps, runtime overflow contract, exact-int parity, seed refused in default+IR, probes listed: **verified**. Test-count claim (52/1 skipped across 6 modules): **unverified** (only the required fz220+safetynet re-run). "Other differences: none": **verified** for the probes above; the only other diffs I saw are pre-existing (`p3` int64 constant refusal, `p5` declared runtime overflow).

**Pre-existing:** `round(10**20/1)` -> named `int64 constant out of range` on both HEAD and base; wide runtime values -> `integer overflow in round()` on both.

**Unverified:** independent re-run of `test_ail_fz2`, `test_ail_pre429`, `test_ail_int64_edges`, `test_ail_files`, `test_ail_corpus_findings3`; `fz220_huge` (CPython itself is intractable computing `10**10**9`; HEAD/base both refuse it quickly as `int64 constant expression out of range`). Speed: not applicable — compile-time-only check, generated C unchanged.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1126240, "input": 32384, "output": 6592, "reasoning": 24608, "cache.write": 0, "cache.read": 1062656}]
    tool time: bash 8.5 min
        204s bash   cd /home/runner/work/ail-ci/ail-ci; for f in fz220_edge fz220_huge fz220_bounds fz220_div fz220_neg; do echo "
        145s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_fz22
        120s bash   cd /home/runner/work/ail-ci/ail-ci; echo "HEAD huge:"; timeout 120 bash ~/tools/cmp.sh /tmp/probes/fz220_huge.
          9s bash   cd /home/runner/work/ail-ci/ail-ci; echo "=== HEAD fz220.py"; timeout 300 bash ~/tools/cmp.sh /tmp/probes/fz22
          7s bash   cat > /tmp/rprobes/p7_intmin.py <<'PY' print(round(-(2.0 ** 63))) PY cat > /tmp/rprobes/p8_intmin_lit.py <<'PY
          5s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/p1_min /tmp/rprobes/p2_inrange /tmp/rprobes/p3_noflo
          4s bash   cd /home/runner/work/ail-ci/ail-ci for f in p1_min p2_inrange p5_routes; do   d=$(mktemp -d /tmp/exXXXX); cp /
          4s bash   cat > /tmp/rprobes/p10_intpow.py <<'PY' print(round((2 ** 63) / 2.0)) PY cat > /tmp/rprobes/p11_nan.py <<'PY' 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-03T14:56:27Z
