# job job-pre108-10251451  started 2026-10-25T05:51:57Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":335,"duration_api_ms":205,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":326,"duration_api_ms":202,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `8c3c841`.

- Cause: the pre108 check rejected any out-of-int64 *subexpression*, breaking pre113 whole-expression folds and pre97's own `maxsplit` refusal.
- Fix: evaluate the outermost all-int expression exactly (4096-bit bound) and refuse only when the result is out of int64; leave `str.split`/`rsplit` maxsplit arguments to pre97's lowering.

Tests on the final commit:
- `test_ail_pre108 test_ail_typed_tuples test_ail_safetynet test_ail_files test_ail_corpus_findings3`: **39 tests OK, 1 skipped** (497 s).
- Reconstructed checkout with the pre97/pre113 branch changes overlaid (same base; those tests are absent locally): `test_ail_pre97 test_ail_pre113 test_ail_typed_tuples`: **15 tests OK** (66.6 s).

Probes, all on that reconstructed checkout, each build `g` and `d`:
- 6 refusal probes via argument, list item, attribute, dict value, power and unary boundary: refused by name.
- `pre113_cancel`, `pre113_value_paths`, `pre97_maxsplit_inrange`, `pre108_float_unaffected`: matched CPython.
- `pre97_maxsplit_over`: refused with pre97's maxsplit name; `pre97_maxsplit_literal`: refused as `int64 literal out of range`.

DEVLOG and DIFFERENCES updated; `tools/update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 8961151, "input": 163603, "output": 14392, "reasoning": 40500, "cache.write": 0, "cache.read": 8742656}]
    tool time: bash 14.1 min
        497s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre108 test_ail_typed_tuples test_ail_safetynet test_ail_fil
         67s bash   cp AIL_CURRENT/ail_chatgpt.py /tmp/integ/AIL_CURRENT/ail_chatgpt.py && cd /tmp/integ/AIL_CURRENT && python3 -m
         41s bash   cp AIL_CURRENT/ail_chatgpt.py /tmp/integ/AIL_CURRENT/ail_chatgpt.py && cd /tmp/integ/AIL_CURRENT && python3 -m
         38s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre113 test_ail_pre97 test_ail_typed_tuples 2>&1 | tail -80
         36s bash   cd /tmp/integ/AIL_CURRENT && python3 -m unittest -q test_ail_typed_tuples 2>&1 | tail -80
         28s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_typed_tuples 2>&1 | tail -60
         28s bash   cd /tmp/integ/AIL_CURRENT && python3 -m unittest -q test_ail_typed_tuples 2>&1 | tail -40
         20s bash   cd /tmp/integ && for p in /tmp/probes/pre108_refuse_arg.py /tmp/probes/pre108_refuse_list.py /tmp/probes/pre10

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** `_constant_int` now folds the outer constant int expression exactly (FloorDiv/Mod/bitwise/invert included) with a 4096-bit cap, checks only the outermost candidate, and skips every node under a `.split`/`.rsplit` maxsplit argument. This matches the report's description, but the deferral is broader than "str.split maxsplit" and the size cap creates a refusal hole the report does not mention.

**Defects**

1. **Constant expressions over 4096 bits are no longer refused and trap at run time.**
   - `/tmp/rprobes/huge_shift_fit.py`: `print((2 ** 5000) >> 4999)`
     CPython: stdout `2`, exit 0. Base: named compile refusal (`int64 constant expression out of range`). HEAD and the reconstructed integration tree: build OK, no stdout, stderr `integer overflow`, exit 1.
   - `/tmp/rprobes/huge_div_fit.py`: `print((10 ** 5000) // (10 ** 4999))` — CPython `10`, exit 0; HEAD/integration runtime `integer overflow`, exit 1.
   - `print(2 ** 5000)` behaves the same; base refused by name.
   - Cause: `AIL_CURRENT/ail_chatgpt.py:97-183` returns `None` for anything over 4096 bits, so no candidate reaches the refusal; pre113 also cannot fold it, and the runtime traps. The DIFFERENCES row still promises a named refusal for constant expressions.

2. **`.split`/`.rsplit` deferral applies to every receiver and to the whole maxsplit subtree, so non-`str` and non-pure-int cases escape both checks.**
   - `/tmp/rprobes/split_method.py`:
     ```python
     class C:
         def split(self, sep: str, n: int) -> None:
             print(n)
     def main() -> None:
         C().split(" ", 10 ** 30)
     main()
     ```
     CPython: prints `1000000000000000000000000000000`, exit 0. Base: named compile refusal (acceptable). HEAD and integration reconstruction: compile OK, runtime `integer overflow`, exit 1.
   - `"a b c".split(" ", [10 ** 30][0])` and `"a b c".split(" ", 10 ** 30 if True else 0)`: base named refusal; HEAD/integration runtime `integer overflow` because pre97 only folds a pure constant maxsplit.
   - Cause: `AIL_CURRENT/ail_chatgpt.py:186-228` keys only on the attribute name and defers `ast.walk(count)` instead of the maxsplit expression pre97 actually owns.

**Checks**
- HEAD: `par_check -j 2 test_ail_pre108 test_ail_typed_tuples test_ail_safetynet` -> 3 modules, 0 failed (138 s); `test_ail_files test_ail_corpus_findings3` -> 0 failed (203 s).
- Reconstructed integration tree: `test_ail_pre97 test_ail_pre113 test_ail_typed_tuples` -> 15 tests OK (67 s).
- Non-feature program: `--debug-dir` `program.c` identical between base and HEAD (only temp paths differ).
- Report claims about the cause, tests and manifest (`--check` passes) are verified; the "refuse only when the result is out of int64" claim is false above 4096 bits.

**Not counted:** on this local worktree (without pre113) `print(2 ** 100 - 2 ** 100)` traps, but the reconstructed integration tree prints `0`; this is the known branch dependency, not a separate target defect.

**Unverified:** speed (front-end-only change), worker's individual probes, and the wider suite.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1096738, "input": 56685, "output": 4683, "reasoning": 22762, "cache.write": 0, "cache.read": 1012608}]
    tool time: bash 8.7 min
        205s bash   cd AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findi
        140s bash   cd AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pre108 test_ail_typed_tuple
         67s bash   cd /tmp/integ/AIL_CURRENT && date && timeout 1200 python3 -m unittest -q test_ail_pre97 test_ail_pre113 test_a
         29s bash   cd /tmp/rprobes && for p in huge_pow huge_shift_fit huge_div_fit maxsplit_list maxsplit_tuple maxsplit_call ma
         21s bash   cd /tmp/rprobes && cat > split_method.py <<'EOF' class C:     def split(self, sep: str, n: int) -> None:      
         16s bash   cd /tmp/rprobes && for p in huge_pow huge_shift_fit huge_div_fit cancel_small invert_over; do echo "=== $p HEA
         16s bash   cd /tmp/rprobes && for p in huge_shift_fit huge_div_fit maxsplit_list cancel_small; do echo "=== $p INTEG"; ti
         14s bash   cd /tmp/rprobes && cat > invert_cancel.py <<'EOF' print(~(-(2 ** 63) - 1)) EOF cat > invert_cancel2.py <<'EOF'

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `c9e10b8`.

- Oversized constant expressions now reach the named `int64 constant expression out of range` refusal instead of the runtime trap.
- Maxsplit deferral is narrowed to the constant maxsplit of a literal `str.split`/`rsplit`; non-str receivers and non-constant maxsplit expressions stay under the generic check.

Probes, both builds:
- Huge pow/shift/floor-div/mod/mult/negative/cancel and huge values via argument, list item, attribute, dict value: refused by name on both builds.
- Non-str `.split`/`.rsplit`, str split with list/tuple item, if-expression, call, keyword list, and bytes split: refused by the generic name on both builds.
- Literal str split with huge maxsplit: refused with the maxsplit name; literal above int64: `int64 literal out of range`.
- Float/in-range probe: matched CPython on both builds.
- On the reconstructed pre97/pre113 integration tree, cancellation/value-path and in-range maxsplit probes matched CPython; out-of-range maxsplit probes were refused by name.

Tests on final commit:
- `test_ail_pre108 test_ail_typed_tuples test_ail_safetynet`: 3 modules, 0 failed.
- `test_ail_files test_ail_corpus_findings3`: 2 modules, 0 failed.
- Integration `test_ail_pre97 test_ail_pre113 test_ail_typed_tuples`: 15 tests OK.
- `tools/update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 2017871, "input": 159773, "output": 10821, "reasoning": 16621, "cache.write": 0, "cache.read": 1830656}]
    tool time: bash 15.2 min, write 0.0 min, edit 0.0 min
        212s bash   cd AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findi
        207s bash   cd AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findi
        128s bash   cd AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pre108 test_ail_typed_tuple
        124s bash   cd AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pre108 test_ail_typed_tuple
         67s bash   cp AIL_CURRENT/ail_chatgpt.py /tmp/integ/AIL_CURRENT/ail_chatgpt.py && cd /tmp/integ/AIL_CURRENT && timeout 12
         45s bash   cp AIL_CURRENT/ail_chatgpt.py /tmp/integ/AIL_CURRENT/ail_chatgpt.py && cd /tmp/integ/AIL_CURRENT && timeout 12
         45s bash   cp AIL_CURRENT/ail_chatgpt.py /tmp/integ/AIL_CURRENT/ail_chatgpt.py && cd /tmp/integ/AIL_CURRENT && timeout 12
         13s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_pre108 2>&1 | tail -30

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the diff does.** Rewrites the front-end int64 constant check to evaluate the *outermost* all-int expression exactly (4096-bit cap, plus new unary `~` support), refuse constants too large to evaluate, and give the constant maxsplit of a literal `str.split`/`rsplit` its own refusal name. The report omits the new `~` folding and that the "outermost" rule relies on the lowering folding the same expression.

**Probes** (`/tmp/rprobes`, `cmp.sh`, both builds; base `/tmp/base`, integration reconstruction `/tmp/integ`):
- `p4 2**5000`, `p5 (2**5000)>>4999`, `p6 (10**5000)//(10**4999)`, `p7 2**5000` via argument: both builds refuse `int64 constant expression out of range: constant expression too large to evaluate`. Matches report.
- `p8 "a b c".split(" ", 10**30)`: maxsplit refusal on both builds (CPython `OverflowError`). Matches.
- `p9` str variable receiver and `p10` non-str `.split`: generic int64 refusal (base identical).
- `p1`/`p2`/`p3`/`p11`/`p12` (literal cancellation, value paths, in-range maxsplit): match CPython on `/tmp/integ`; on this worktree they compile and trap because pre113's exact folding is not present here (base refused). Not defects for the merge target.
- `p21`, `p18`, `p19`, `p13`: defects below.
- `--debug-dir` for a program not using the feature: generated C identical to base (only `native_report.json` differs).

**Tests.** HEAD: `test_ail_pre108`+`test_ail_safetynet` 0 failed (13.5 s / 123.1 s); `test_ail_typed_tuples` 10 tests OK; `update_manifest.py --check` rc 0. `/tmp/integ`: `test_ail_pre97`+`test_ail_pre113` 5 tests OK.

**Claims.** Oversized-constant and maxsplit claims: verified. In-range/cancellation on the integration tree: false for module-constant cancellation (`p21`) and `~` (`p13`). `test_ail_files`/`test_ail_corpus_findings3`: unverified. Integration `test_ail_typed_tuples` copy: unverified (HEAD copy passes). Some worker maxsplit list/tuple/if-expression/call/bytes probes: unverified. Speed: not run (compile-time-only change).

**Pre-existing.** The HEAD-only runtime traps for literal whole-expression folds (`p1`/`p2`/`p11`/`p12`) are expected because pre113 folding is absent from this worktree; they match on integration.

VERDICT: FIX
1. Module constants are resolved by the new checker but not by the lowering's `int_constant`, so an out-of-range intermediate is skipped as "covered" by a fitting parent and then traps at run time. Probe `p21_max_cancel.py`:
   `MAX = 9223372036854775807` / `print(MAX + 1 - 1)` / `print(MAX * 2 // 2)`.
   Expected CPython: `9223372036854775807` twice, exit 0. Actual on HEAD and `/tmp/integ`, both builds: exit 1, empty stdout, `integer overflow`. Base refused by name. Same root cause: `p18` (`BIG * 2 - 1`, expected `9223372036854775807`, actual trap) and `p19` (`"a b c".split(" ", BIG * 2 - 1)`, expected `['a', 'b', 'c']`, actual trap).
2. The new `~` support in `_constant_int` lets an expression pass when its outer value fits, but the lowering does not fold `ast.Invert`, so an out-of-int64 operand is evaluated at run time. Probe `p13_invert_cancel.py`:
   `print(~(2 ** 63) + 2 ** 63)` / `print(~(2 ** 63 - 1) + 2 ** 63)`.
   Expected CPython: `-1` and `0`, exit 0. Actual on HEAD and `/tmp/integ`, both builds: exit 1, empty stdout, `integer overflow`. Base refused by name.
[cost $0.0000, opencode tokens {"total": 1739249, "input": 144980, "output": 7320, "reasoning": 36741, "cache.write": 0, "cache.read": 1550208}]
    tool time: bash 3.9 min, read 0.0 min
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         27s bash   cd /home/runner/work/ail-ci/ail-ci && ls AIL_CURRENT/test_ail_typed_tuples.py 2>&1; python3 tools/update_manif
         18s bash   cd /tmp/integ/AIL_CURRENT && date && timeout 1500 python3 -m unittest -q test_ail_pre97 test_ail_pre113 2>&1 |
         11s bash   cd /tmp/rprobes && date && printf '%s\n' p1_fold_inrange p2_fold_mixed p3_fold_identity p4_huge_pow p5_huge_sh
          9s bash   cd /tmp/rprobes && date && printf '%s\n' p1_fold_inrange p2_fold_mixed p3_fold_identity p11_inrange_maxsplit p
          8s bash   cd /tmp/rprobes && cat > p15_module_cancel.py <<'EOF' A = 2 ** 62   def main() -> None:     print(A * 2 - A * 
          8s bash   cd /tmp/rprobes && cat > p18_module_fit.py <<'EOF' BIG = 4611686018427387904   def main() -> None:     print(B
          7s bash   cd /tmp/rprobes && cat > p21_max_cancel.py <<'EOF' MAX = 9223372036854775807   def main() -> None:     print(M

FINAL VERDICT: FIX  2026-10-25T07:00:54Z
