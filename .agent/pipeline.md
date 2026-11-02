# job job-rbstd_decimal-11021359  started 2026-11-02T05:06:15Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Committed `ce8a7df` on `job-rbstd_decimal-11021359`.

- Re-applied the accepted `std_decimal` diff; resolved `dunderrt.py`/`pyboxed2.py` conflicts by keeping both `ordering`/`array_prelude` and `reversed_`; fixed the concatenated `DIFFERENCES.md` rows and DEVLOG entry.
- `tools/diff_ids.py` does not exist in this tree (noted in prior DEVLOG entries); `tools/update_manifest.py` ran, `--check` exits 0.
- Probes (8, all match CPython on both g and d builds): `dec_roundtrip`, `dec_reversed`, `dec_reversed_user`, `dec_tuple_types`, `dec_routes`, `dec_rev_routes`, `dec_rev_inherit`, `dec_boundary`.
- Tests on final commit: `test_ail_std_decimal`, `test_ail_stdtop1`, `test_ail_dunders`, `test_ail_bytearray_decimal`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7 modules, 0 failed.
[cost $0.0175, opencode tokens {"total": 1307502, "input": 46921, "output": 5397, "reasoning": 5776, "cache.write": 0, "cache.read": 1249408}]
    tool time: bash 20.0 min
        938s bash   python3 ../tools/par_check.py -j 2 test_ail_std_decimal test_ail_stdtop1 test_ail_dunders test_ail_bytearray_d
        262s bash   cat > /tmp/probes/dec_boundary.py <<'EOF' from decimal import Decimal  def rt(d):     return Decimal(d.as_tupl
          0s bash   git status --short; echo "---"; python3 tools/update_manifest.py --check; echo "manifest check exit:$?"; git l
          0s bash   python3 tools/update_manifest.py --check; echo "EXIT:$?"; git add AIL_CURRENT/manifest.d AIL_CURRENT/MANIFEST.
          0s bash   python3 tools/update_manifest.py 2>&1 | tail -30; echo "EXIT:${PIPESTATUS[0]}"; git status --short | grep -E '
          0s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-std_decimal-11020505 2>&1 | tail -20; echo "EXIT:$?"; git 
          0s bash   git status --short | head -50; echo "=== diff stat staged ==="; git diff --cached --stat | tail -8; echo "=== 
          0s bash   grep -rn "diff_ids" . --exclude-dir=.git 2>/dev/null | head; echo ---; ls .agent 2>/dev/null; echo ---; git ls

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: re-apply accepted `std_decimal` change

**What the change really does.** Re-applies the accepted `std_decimal` work: `Decimal.as_tuple()` returns a `_DecTuple` with the tuple protocol and round-trips via `Decimal(t)`; the int64 default keeps Decimal coefficients in an arbitrary-precision `_DecInt`; `reversed(instance)` asks a class's `__reversed__` through the general path, installed only when a class defines it. The merge also keeps this tree's `ordering` / `array_prelude` fixes.

**Compatibility check.** `prelude_decimal.py` and `stdtop.py` are byte-identical to the accepted job's result (`FETCH_HEAD`); `dunderrt.py` and `pyboxed2.py` contain both the accepted `reversed_` changes and this tree's `ordering`/`array_prelude`/bisect changes. No unrelated source edits.

**Probes (all in /tmp/rprobes, both `g` and `d`):**
- `dec_tuple_basic`, `dec_tuple_routes`, `dec_float_exact`, `dec_big_ops`, `dec_big_hash`, `dec_reversed_user`, `dec_both_features`: same stdout/exit as CPython.
- `dec_big_arith`, `dec_int64_edge`: same stdout/exit (`InvalidOperation` from `sqrt`/division, matching CPython).
- `dec_reversed_decimal`: stdout differs only in `reversed(...).__class__.__name__` (`iterator` vs `reversed`), also on base → pre-existing.
- `dec_exp_boundary`: `Decimal("1e-1000000000000000000")` rejected by AIL where CPython accepts; base rejects it too (`base_exp2`) → pre-existing.
- `dec_tuple_errors`: compile-time refusal for an out-of-int64 source literal; base refuses identically (`base_bigexp`) → pre-existing.
- `dec_big_int_hash`: `int(huge Decimal)` stops loudly with `OverflowError`, no wrapping — declared in DIFFERENCES.
- Re-ran the worker's 8 probes (`dec_roundtrip`, `dec_reversed`, `dec_reversed_user`, `dec_tuple_types`, `dec_routes`, `dec_rev_routes`, `dec_rev_inherit`, `dec_boundary`): all match CPython on both builds.

**No-feature C.** `--debug-dir` output for a plain program and an ordering program is identical to `/tmp/base` (only report paths differ).

**Tests.** `test_ail_std_decimal test_ail_stdtop1 test_ail_dunders test_ail_bytearray_decimal test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 7 modules, 0 failed (718 s). `tools/update_manifest.py --check` exits 0; `tools/diff_ids.py` indeed absent.

**Claims.** Re-application/conflict resolution, missing `diff_ids.py`, manifest check, 8 probes, and 7 passing modules: verified. “Exact-int mode matches”: unverified (cmp.sh covers only `g`/`d`). DEVLOG diff also removes one blank line (cosmetic, not a defect).

**Pre-existing differences:** reversed-iterator `__class__.__name__`; exponent `-1000000000000000000` refusal; int64 source-literal refusal. None caused by this change.

**Speed:** `tools/icount.c` builds, but `perf_event_open` is denied in this runner, so instruction counts were not measured; the non-feature generated C is unchanged and the decimal prelude is identical to the accepted change.

VERDICT: ACCEPT
[cost $0.0277, opencode tokens {"total": 1575009, "input": 71246, "output": 7960, "reasoning": 12923, "cache.write": 0, "cache.read": 1482880}]
    tool time: bash 28.2 min, write 0.0 min
        719s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_decimal test_ail_stdtop1 test_ail_dunders te
        325s bash   mkdir -p /tmp/rprobes/out; for p in /tmp/rprobes/*.py; do b=$(basename "$p" .py); echo "===== $b"; bash ~/tool
        251s bash   for b in dec_roundtrip dec_reversed dec_reversed_user dec_tuple_types dec_routes dec_rev_routes dec_rev_inheri
        124s bash   for p in dec_exp_boundary dec_big_ops; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py "$PWD" > /tm
         79s bash   cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c 2>&1 | tail -2; for who in head ba
         51s bash   bash ~/tools/cmp.sh /tmp/rprobes/dec_both_features.py "$PWD" > /tmp/rprobes/out/dec_both_features.log 2>&1; ca
         48s bash   bash ~/tools/cmp.sh /tmp/rprobes/dec_big_int_hash.py "$PWD" > /tmp/rprobes/out/dec_big_int_hash.log 2>&1; cat 
         47s bash   bash ~/tools/cmp.sh /tmp/rprobes/dec_big_hash.py "$PWD" > /tmp/rprobes/out/dec_big_hash.log 2>&1; cat /tmp/rpr

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T07:36:36Z
