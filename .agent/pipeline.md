# job job-pre33-10240909  started 2026-10-24T00:09:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing bullet (`p_floats`): constant integer powers outside int64 are now refused at compile time on both builds, naming the power and `DIFFERENCES C?-job-pre33-10240909-1`. The recorded `(10**40,)` tuple case is covered. `p_dictrepr` (second bullet) still differs and was not changed.

Commit: `f832afb`

Tests on final commit:
- `test_ail_pre33` + `test_ail_safetynet`: 7 passed
- `test_ail_files` + `test_ail_corpus_findings3`: 20 passed, 1 skipped (no zig)

Probes (`cmp.sh`, both builds):
- Refused by name: `floats_tuple`, `a_pow`, `b_pow_var`, `d_float`, `intpow_refuse`, `intpow_tuple`, `intpow_sources`, `intpow_arg`, `intpow_attr`, `intpow_list`, `intpow_huge`, `intpow_alias`, `intpow_10_19`, `intpow_neg64`.
- Matched CPython: `c_tuple`, `e_tuple_pow`, `intpow_ok`, `intpow_float`.
- Already refused by the existing int64 literal check: `f_big_literal`.
- Still differs, untouched: `dict_slice`.

Manifest registers and pins `test_ail_pre33.py`; `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 5423017, "input": 141800, "output": 34545, "reasoning": 2512, "cache.write": 0, "cache.read": 5244160}]
    tool time: bash 11.5 min
        337s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_files test_ail_corpus_findin
        165s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre33 test_ail_safetynet > /
         77s bash   cd /tmp/probes cat > intpow_alias.py <<'EOF' def main():     x = 3**40     y = x     print(y)  main() EOF cat 
         41s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre33 2>&1 | tail -30
         21s bash   cd /tmp/probes cat > intpow_sources.py <<'EOF' class Box:     def __init__(self, v):         self.v = v   def 
         17s bash   cd /tmp/probes; WT=/home/runner/work/ail-ci/ail-ci; for p in a_pow b_pow_var c_tuple d_float e_tuple_pow f_big
         14s bash   cd /tmp/probes cat > intpow_refuse.py <<'EOF' def main():     print(10**40) main() EOF cat > intpow_tuple.py <
          9s bash   mkdir -p /tmp/probes && cat > /tmp/probes/floats_tuple.py <<'EOF' def main():     print((10**40,))     print((

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre33 (`f832afb`)

**Change.** Adds `pyfront.refuse_int_pow_overflow`, called from the IR lowerer and both general/typed Pow emitters. Constant `int ** int` whose exact result leaves int64 is refused at compile time, naming the power and `DIFFERENCES C?-job-pre33-10240909-1`.

**Probes** (`bash ~/tools/cmp.sh`, HEAD and `/tmp/base` worktree):
- `floats_tuple` (`(10**40,)`): base = runtime `integer overflow`; HEAD = named compile-time refusal on both builds. **Fixed as recorded.**
- Refused by name on both builds: `ov_list`, `ov_dict`, `pow_via_return`, `default_arg`, `floatpow` (line `float(2**63)` only), `unary_pow` (`-2**63`).
- Match CPython on both builds: `bounds` (`2**62`, `(-2)**63`, `(-2)**62`, `3**39`, `(-3)**39`, `1**1000000000`, `0**1000000000`, `(-1)**1000000001`, negative exponents), `sources` (same values via argument/list item/attribute/dict value), `bool_pow`, `2.0**63` / `2**63.0`.
- `plain_no_pow` and `bounds`: `--debug-dir` `program.c` is byte-identical to base on both builds; only `native_report.json` temp paths differ. No runtime-codegen change, so no hot-path speed concern.
- `dict_slice` (`p_dictrepr`): identical wrong `TypeError` on base and HEAD, untouched as stated.

**Tests.** `par_check.py -j 2 test_ail_pre33 test_ail_safetynet` → 2/2 ok. `test_ail_files test_ail_corpus_findings3` → 2/2 ok. `update_manifest.py --check` → rc 0; manifest pins `test_ail_pre33.py`.

**Claims.** Commit, p_floats fix, both-build refusal, p_dictrepr untouched, test results and manifest: verified. Exact worker probe files and the "7 passed"/"20 passed, 1 skipped" counts: not independently re-run/counted.

**Pre-existing (identical on base, not caused by this change):**
- `-(-2)**63` and `var_pow` (`a=10; a**40`) and `builtin_pow` (`pow(10,40)`) still stop with runtime `integer overflow`; only constant `**` BinOps are covered.
- `-2**63` mathematically fits int64 but base already overflowed at run time; HEAD now refuses it by name (no regression, named refusal allowed).

**Unverified.** No runtime speed measurement (no emitted C changed); worker's exact probe corpus.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 462424, "input": 46045, "output": 4446, "reasoning": 11549, "cache.write": 0, "cache.read": 400384}]
    tool time: bash 7.4 min
        209s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_files te
        124s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre33 te
         30s bash   cd /tmp/rprobes for p in floats_tuple bounds sources overflow_placements floatpow bool_pow nested_sign default
         15s bash   cd /tmp/rprobes cat > ov_list.py <<'EOF' def main():     xs = [10**40]     print(xs)  main() EOF cat > ov_attr
         15s bash   cd /tmp/rprobes cat > var_pow.py <<'EOF' def main():     a = 10     print((a**40,))  main() EOF cat > builtin_
         15s bash   cd /tmp/rprobes cat > unary_pow.py <<'EOF' def main():     print(-2**63)     print(-(2**63))  main() EOF cat >
         11s bash   cd /tmp/rprobes cat > dict_slice.py <<'EOF' def main():     d = {}     d[2:2] = "y"     print(d)  main() EOF c
         10s bash   cd /tmp/rprobes echo "===== nested_sign BASE ====="; bash ~/tools/cmp.sh /tmp/rprobes/nested_sign.py /tmp/base

FINAL VERDICT: ACCEPT  2026-10-24T00:35:17Z
