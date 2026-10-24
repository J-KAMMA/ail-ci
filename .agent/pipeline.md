# job job-pre47-10241039  started 2026-10-24T01:39:54Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Fixed the first still-differing case and committed on `job-pre47-10241039`.

**Change**
- Added constant integer-expression folding/refusal in `pyfront.fold_int_constants`, called before both code paths.
- `-(-2)**63` is now refused at compile time by name; `-2**63`, `2**63-1`, and other in-range constants fold to one int64 literal.
- General emitters now accept the `INT64_MIN` unary spelling.
- Updated `SEMANTICS.md`, `DEVLOG.md`, `DIFFERENCES.md`, `ail_check.py`, manifest, and added `test_ail_pre47.py`.

**Probes (both builds)**
- Match CPython: `in_range_consts`, `float_pow`, `min_literal`, `ctx_arg`, `ctx_list`, `ctx_attr`, `ctx_dict`.
- Refused by name: `neg_pow_const`, `two_63`, `ten_40`, `neg_two_64`, `shift_63`, `cancel_out`, `assign_out`, `too_large`, `ctx_arg_refuse`.
- Known remaining, unchanged: `var_pow`, `builtin_pow`, and variable/list/attribute/dict sources still stop with runtime `integer overflow`.

**Tests on final commit**
- `test_ail_pre47`: passed
- `test_ail_safetynet`: passed
- `test_ail_files`: passed
- `test_ail_corpus_findings3`: passed
- 4 modules, 333s, 0 failed.

Commits: `79ed918` and manifest pin `a96f58e`. Working tree only has untracked `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 8167558, "input": 280166, "output": 58306, "reasoning": 350, "cache.write": 0, "cache.read": 7828736}]
    tool time: bash 8.5 min, write 0.0 min
        335s bash   python3 tools/par_check.py -j 2 test_ail_pre47 test_ail_safetynet test_ail_files test_ail_corpus_findings3
         40s bash   mkdir -p /tmp/probes2; for e in 'print(-2**63)' 'print(2**63)' 'print(2**64)' 'print(10**40)' 'print(-(-2)**63
         24s bash   for p in two_63 ten_40 neg_two_64 too_large shift_63 cancel_out assign_out; do echo ===$p===; bash ~/tools/cmp
         20s bash   python3 -B AIL_CURRENT/test_ail_pre47.py -v
         17s bash   for p in ctx_arg ctx_list ctx_attr ctx_dict ctx_arg_refuse; do echo ===$p===; bash ~/tools/cmp.sh /tmp/probes/
         17s bash   for p in too_large source_var source_list source_attr source_dict; do echo ===$p===; bash ~/tools/cmp.sh /tmp/
         13s bash   mkdir -p /tmp/probes && printf 'print(-(-2)**63)\n' > /tmp/probes/neg_pow_const.py && printf 'a=10\nprint(a**4
         10s bash   for p in neg_pow_const var_pow builtin_pow; do echo ===$p===; bash ~/tools/cmp.sh /tmp/probes/$p.py $PWD; done

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre47 constant integer expressions

**What the change really does.** Adds an AST pre-pass `pyfront.fold_int_constants` that rewrites every purely constant int expression to one int64 literal, or raises a named refusal when the exact value is out of int64 (or exceeds a 4096-bit intermediate bound). It runs in `to_c` and `_build_unshadowed`; `pyboxed`/`pyboxed2` also learn the `-9223372036854775808` spelling.

**Probes run on HEAD (both builds) and on base `/tmp/base`.** All these match CPython: `min_literal` (`-2**63`, `(-2)**63`, `2**63-1`), `fstring`, `unicode_same_line`, `unicode_prefix`, `multiline`, `defaults`, `ann_default`, `slices2`, `range_min`, `attr_min`, `ctx_min`, `min_contexts2`, `min_default`, `containers`, `unary`, `fold_more`, `pow_neg`, `div_float`, `add_float`, `method`, `truth`, `bool_pow`, `neg_exp`, `plain_arith`, `syntaxctx`. Refused by name on both builds: `neg_pow`, `compare`, `floatctx`, `both`, `mixed_refuse`, `dead`, `shift_cancel`. Base differs for the fixed case exactly as reported: `neg_pow` base = runtime `integer overflow`, HEAD = named compile refusal; `min_literal` base = overflow, HEAD = CPython output.

**Defect (new): pipeline emitter does not accept folded INT64_MIN.**
Probe `/tmp/pipe/pipe.ail`: `sum((-2**63) for x in xs)`, run with a data file holding one int64 `0`.

- CPython: `xs=[0]; print(sum((-2**63) for x in xs))` → `-9223372036854775808`.
- HEAD: `python3 AIL_CURRENT/ail_chatgpt.py compile pipe.ail --syntax python -o exe` exits 0; `./exe data.bin` prints `integer overflow`, exits 1.
- Base: compile exits 3 with named refusal `not in the subset: BinOp` (acceptable).

Cause: `to_c` folds before `to_pipeline_c`, but `pyfront._c_expr` still emits `ck_neg(9223372036854775808)` for the folded literal, which traps. The change patched `pyboxed`, `pyboxed2` and `pyfunc`, but not the pipeline emitter. So the report claim “General emitters now accept the INT64_MIN unary spelling” is false for this path. Same failure for `sum(x+(-2**63) for x in xs)`, `sum(-1<<63 for x in xs)`, `max((-2**63) for x in xs)`.

**Pre-existing / newly reachable (not blocking).**
- `[1,2] * (2**63-1)` segfaults on HEAD (exit 139) vs CPython `MemoryError`; base with the same value written `[1,2] * 9223372036854775807` also segfaults, so the runtime list-repeat bug is pre-existing.
- Pipeline `sum(x + (-9223372036854775808) for x in xs)` traps identically on base; the pipeline INT64_MIN gap is latent there.
- `(1<<100000)>>100000` and `(2**5000)>>5000` are exactly `1` but refused by the 4096-bit bound; named refusal is allowed, but the message “its exact value does not fit” is false and the report claim “when the exact value fits” is not universal.
- Dead-code `if False: print(2**63)` now refuses (base matched CPython); named refusal is allowed.

**Claim check.** Fold pass added/called: verified. `-(-2)**63` refused by name: verified. `-2**63` / `2**63-1` fold correctly: verified. “Other in-range constants fold when exact value fits”: false for the >4096-bit intermediates above. “General emitters accept INT64_MIN”: false for pipeline. `var_pow`/`builtin_pow` still runtime-overflow: verified. Tests: `test_ail_pre47` 20.1s pass, `test_ail_safetynet` 123.3s pass on HEAD.

**Unverified.** `test_ail_files`, `test_ail_corpus_findings3`; icount speed; worker’s exact probe corpus; variable/list/attribute/dict pow sources.

**Defects**
1. Pipeline path: `sum((-2**63) for x in xs)` with `xs=[0]` — expected `-9223372036854775808`, actual `integer overflow` / exit 1; base refused by name. Fix `_c_expr` to emit `INT64_MIN` (or refuse the pipeline construct by name).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 2014809, "input": 96369, "output": 8337, "reasoning": 38615, "cache.write": 0, "cache.read": 1871488}]
    tool time: bash 6.0 min
        125s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         43s bash   cd /tmp/rprobes && printf 'print((-7)//2, 7//-2, -7%%2, 2**62+2**62, 3**30, (2**63-1)//3)\n' > arith2.py && pr
         31s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in min_literal neg_pow fstring unicode_prefix defaults sli
         31s bash   date; cd /tmp/base && for p in shift_cancel compare floatctx dead neg_pow min_literal both mixed_refuse; do ec
         25s bash   cd /tmp/base && for p in listmul_max listmul_min; do echo "=== $p BASE ==="; timeout 300 bash ~/tools/cmp.sh /
         22s bash   cd /tmp/rprobes && printf 'print(-1 << 63)\nprint("ab" * (-2**63))\nprint([1,2] * (-2**63))\nprint((1 << 63) >
         22s bash   cd /tmp/rprobes && printf 'print((2**63)//2)\nprint((2**63)%%10)\nprint((-2**63)%%10)\nprint((1<<62)*2-1)\npri
         21s bash   cd /tmp/base && echo '=== edges BASE ==='; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/edges.py /tmp/base 2>&

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the review defect and committed as `b41ba17`.

**Change:** `pyfront._c_expr` now emits folded INT64_MIN as `(-9223372036854775807LL - 1)` instead of `ck_neg(9223372036854775808)`, covering the pipeline path. Added pipeline cases to `test_ail_pre47.py`, plus DEVLOG/DIFFERENCES/manifest updates.

**Probes** (`bash ~/tools/cmp.sh`, both default and general builds):
- Match CPython: `min_script`, `min_boundary` (INT64_MIN through variable, list item, tuple, attribute, dict, argument, arithmetic).
- Refused by name on both builds: `min_refuse_pow`, `min_refuse_negpow`, `min_refuse_arg`, `min_refuse_list`, `min_refuse_attr`, `min_refuse_dict`.
- Still runtime `integer overflow` as pre-existing: `var_pow`, `builtin_pow`.

**Pipeline probes** (default and strict; 12 behaviours + 3 refusals): all 30 checks pass. Covered `sum((-2**63) ...)`, `x + (-2**63)`, `-1 << 63`, `max`, guarded folds, direct INT64_MIN spelling, empty input, INT64_MAX, and out-of-range refusals. The exact review probe via `ail_chatgpt.py compile` now prints `-9223372036854775808`, exit 0.

**Tests on final commit:** `test_ail_pre47`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 209s, 0 failed. Manifest `--check` passes. No speed measurement made.
[cost $0.0202, opencode tokens {"total": 740500, "input": 72428, "output": 5316, "reasoning": 7012, "cache.write": 0, "cache.read": 655744}]
    tool time: bash 4.1 min, edit 0.0 min, write 0.0 min
        210s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pre47 test_ail_saf
         17s bash   cd /tmp/probes && for p in min_script min_boundary min_refuse_pow min_refuse_negpow min_refuse_arg min_refuse_
          8s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 -B -m unittest -q test_ail_pre47 2>&1 | 
          7s bash   cd /tmp/probes && timeout 900 python3 -B run_pipe.py 2>&1 | tail -40
          0s bash   mkdir -p /tmp/pipe_final && cd /tmp/pipe_final && printf 'sum((-2**63) for x in xs)\n' > pipe.ail && python3 -
          0s bash   cd /tmp/probes/pipe && printf 'sum((-2**63) for x in xs)\n' > pipe_neg_pow.ail && python3 -c "import struct;op
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -8
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does**

Adds `pyfront.fold_int_constants`, called from both `pyc.to_c` and `_build_unshadowed`: it folds purely constant integer AST expressions to one int64 literal, refuses out-of-int64 results by name, and teaches the pipeline/general emitters the `-9223372036854775808` spelling. Tests/docs/manifest accompany it. This matches the report.

**Probes** (own, `/tmp/rprobes`, `bash ~/tools/cmp.sh`, both builds unless noted)

- `p1_arith`, `p18_negops`, `p19_shifts`, `p21_minforms`: all match CPython (INT64_MIN arithmetic, negative `//`/`%`, shifts, `(-2)**63`, `-(2**63)`).
- `p2a_cancel`: `(2**63)-(2**63)`, `//`, `%`, `^`, `&` all match; cancellation works.
- `p3_min_direct`, `p10_contexts`, `p11_default`, `p12_slice`, `p13_index`, `p22_pow_min`: direct/folded INT64_MIN through argument, list, tuple, dict, attribute, default, range, slicing, indexing, `pow`, `str`, comparisons — all match CPython on both builds; base refused or overflowed these.
- `p15b_unicode`, `p20_multiline`: folding with multibyte text and multi-line expressions matches.
- `p5/p6/min_refuse_*`: out-of-range constants refused by name on both builds; `-(-2)**63` refused by name (allowed).
- Pipeline: worker's `run_pipe.py` — all 30 checks pass; own `run_pipe.sh` (direct, arithmetic, floor, guard, empty, refusals) passes default; general pipeline refuses as before.
- Non-feature C: scripts `n1`–`n3` emit byte-identical C to `/tmp/base` (`--emit-c`).
- `p4_intermediate`: `(1 << 5000) >> 5000` is refused with the "overflows int64" message although its value is 1. This is an over-refusal from the 4096-bit intermediate cap; it is a named refusal, so allowed by the rules, though the message is misleading.

**Pre-existing (same on `/tmp/base`)**

- `a=10; a**40` and `pow(10,40)`: runtime `integer overflow` (report says this).
- `x = -2**63; -x`: runtime `integer overflow`; `abs(INT64_MIN)` traps.

**Tests**

`test_ail_pre47` (8.4s) and `test_ail_safetynet` (103.3s): 2 modules, 0 failed. Manifest `--check` passes. I did not re-run `test_ail_files` or `test_ail_corpus_findings3` (the review instruction limits re-runs to changed modules plus safetynet), so those two report claims are unverified. No runtime speed measurement; non-feature emitted C is unchanged, so no regression is plausible from this diff. Library/`c_api` and direct `pyfunc.to_c` entry points bypass the fold; unchanged from base, out of the task's cmp.sh scope, not probed.

Every report claim I could check is verified; the only imprecision is the 4096-bit over-refusal above, which is an allowed named refusal, not a wrong result.

VERDICT: ACCEPT
[cost $0.0554, opencode tokens {"total": 2698355, "input": 139405, "output": 8486, "reasoning": 36416, "cache.write": 0, "cache.read": 2514048}]
    tool time: bash 3.4 min
        105s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_
         14s bash   cd /tmp/rprobes && cat > p12_slice.py <<'EOF' xs = [1, 2, 3] print(xs[-2**63:]) print(xs[:-2**63]) print(xs[-2
         12s bash   cd /tmp/probes && for p in min_script min_boundary min_refuse_pow min_refuse_negpow min_refuse_arg min_refuse_
         11s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > p1_arith.py <<'EOF' print((-2**63) + 1) print((-2**63) * 1) 
         11s bash   cd /tmp/rprobes && for f in p5_refusals p6_refuse_neg; do echo "=== base $f ==="; timeout 300 bash ~/tools/cmp
          9s bash   cd /tmp/rprobes && cat > p10_contexts.py <<'EOF' for i in range(-2**63, -2**63 + 3):     print(i) print(str(-2
          9s bash   cd /tmp/rprobes && cat > p16_varpow.py <<'EOF' a = 10 print(a**40) EOF cat > p17_builtinpow.py <<'EOF' print(p
          7s bash   cd /tmp/probes && timeout 600 python3 -B run_pipe.py 2>&1 | tail -8

FINAL VERDICT: ACCEPT  2026-10-24T02:37:35Z
