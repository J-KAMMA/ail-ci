# job job-perf6-10240916  started 2026-10-24T00:16:54Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `e0c214f` on `job-perf6-10240916`.

**Change**
- Counted, unfiltered int/float comprehensions now reserve once and store `list.p[list.n++] = value` directly when the element cannot call code.
- Flat float comprehensions (`+ - *`, reads, no calls/division) get `#pragma omp simd`; the build enables it with `-fopenmp-simd` while keeping `-fno-tree-slp-vectorize`.
- Binary64 decode/encode now allocate with `ail_alloc_raw` instead of zeroing `ail_alloc`.

**Before / after** (`bench/compare.py --app numeric_scale_binary --rounds 16`)
- Before: `ail/c 1.371 [1.360, 1.382] slower`
- After: `ail/c 1.252 [1.235, 1.262] slower`, `ail/base 0.897 [0.885, 0.915] faster` (~10.3% faster vs the old compiler)
- Output stayed byte-identical; ranges do not overlap.

**Probes** (`bash ~/tools/cmp.sh`, both `g` and `d` builds)
- `comp_float_basic.py`, `comp_int_basic.py`, `comp_calls.py`, `comp_sources.py`, `comp_errors.py`, `comp_loop.py` — all matched CPython.
- Coverage: empty/negative/aliased lists, slices, argument/list-item/attribute/dict-value sources, calls, filters, mid-loop exceptions, repeated loops, int and float elements.
- No `cmp.sh` probe for the codec: `float64_decode`/`encode` are AIL-only builtins. Codec behaviour was verified by `test_ail_float64_codec` and compare.py's byte-for-byte output checks.

**Tests on final commit**
- `test_ail_float64_codec`, `test_ail_list_ops`, `test_ail_scalar_list_mutations`, `test_ail_ir_s3`, `test_ail_numeric_bindings`, `test_ail_builtin_syntax_forms`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 9 modules, 0 failed.
- `tools/update_manifest.py && --check` passed.

Untracked `bench/results/*` and `.agent/pipeline.md` were left uncommitted (deletion outside `/tmp` is forbidden).
[cost $0.0000, opencode tokens {"total": 7766468, "input": 115415, "output": 45691, "reasoning": 242, "cache.write": 0, "cache.read": 7605120}]
    tool time: bash 18.2 min
        420s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_float64_codec test_ail_list_ops
        365s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_float64_codec test_ail_list_ops
         45s bash   python3 bench/compare.py --app numeric_scale_binary --rounds 16 > /tmp/baseline.txt 2>/tmp/baseline.err; tail 
         32s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" 
         32s bash   cd /home/runner/work/ail-ci/ail-ci && python3 bench/compare.py --app numeric_scale_binary --rounds 16 > /tmp/a
         32s bash   cd /home/runner/work/ail-ci/ail-ci && python3 bench/compare.py --app numeric_scale_binary --rounds 16 > /tmp/a
         29s bash   cd /home/runner/work/ail-ci/ail-ci && python3 bench/compare.py --app numeric_scale_binary --base 2ecb2ae --rou
         29s bash   cd /home/runner/work/ail-ci/ail-ci && python3 bench/compare.py --app numeric_scale_binary --rounds 16 > /tmp/f

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Review complete. Verified the change against the base worktree, CPython, targeted tests, and an independent benchmark run.

**What changed** (`e0c214f`, plus harness commit `561ac5c` adding only `bench/results/*`):
- `pyfunc.py`: counted/unfiltered int & float comprehensions now store via `c.p[c.n++] = val` when the element has no call/walrus/lambda; flat float elements get `#pragma omp simd`.
- `pyc.py` / `module_object.py`: add `-fopenmp-simd` (keeps `-fno-tree-slp-vectorize`).
- `cruntime.py`: `ail_float64_decode/encode` use `ail_alloc_raw`.

**Probes** (`bash ~/tools/cmp.sh`, g + d builds, all match CPython):
- My probes: `rA_float` (widths, ±0.0, 1e±300, subnormals, 5k-element SIMD loops, reverse/gather, alias), `rB_int` (empty, negative, range/stepped range, `//`/`%`, mid-loop `ZeroDivisionError`/`IndexError` caught, repeats), `rC_sources` (argument, attribute, list item, dict value, slice, attribute mutation between runs), `rD_repeat` (reuse/alias across loop iterations), `rE_mutate` (element call appends to the source list — correctly falls back to push), `rF_nested` (nested comprehensions).
- Worker's 6 probes re-run: all match.
- Prior leftover probes in `/tmp/rprobes` re-run: all match except `ttypes.py` (below).

**Pre-existing** (identical on `/tmp/base`): `ttypes.py` expects Python bignum `[9223372036854775807*2, ...]`; AIL reports `integer overflow` / `OverflowError`. Fixed-width-int behavior, unrelated to this diff.

**No-feature check**: `nofeat.py` compiled to byte-identical `program.c` on HEAD vs base; output identical when linked with the new flag.

**Speed** (`bench/compare.py --app numeric_scale_binary --rounds 16 --base 2ecb2ae`): `ail/c 1.249 [1.242, 1.253] slower`, `ail/base 0.901 [0.892, 0.906] faster`; before was `1.371 [1.360, 1.382]`. ≥3% gain, non-overlapping ranges. Disassembly of `scale` confirms correct 2-wide vectorization with `c.n` induction preserved (no FMA, separate mul).

**Tests** on HEAD: `test_ail_float64_codec`, `test_ail_list_ops`, `test_ail_scalar_list_mutations`, `test_ail_ir_s3`, `test_ail_numeric_bindings`, `test_ail_builtin_syntax_forms`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 9 modules, 0 failed. `tools/update_manifest.py --check` passes.

**Claim check**: allocation/store change, codec `ail_alloc_raw`, `-fopenmp-simd`, before/after numbers, byte-identical output, probes and test list — all verified. Only nit: HEAD does now track `bench/results/*` (harness commit `561ac5c`), so the "left uncommitted" sentence no longer matches; harmless.

**Unverified**: wider suite (not allowed); non-x86/big-endian hardware (byteorder only simulated); gdev icount not run — the target app was measured directly instead, and no-feature C is unchanged.

VERDICT: ACCEPT
[cost $0.0384, opencode tokens {"total": 1737116, "input": 106042, "output": 7604, "reasoning": 21934, "cache.write": 0, "cache.read": 1601536}]
    tool time: bash 8.9 min
        364s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_float64_co
         85s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/rA_float.py /tmp/rprobes/rB_int.py /tmp/rprobe
         32s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/probes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh "
         29s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 bench/compare.py --app numeric_scale_binary --rounds 16 --
          6s bash   cat > /tmp/rprobes/rE_mutate.py <<'EOF' def grow(x: int, xs: list[int]) -> int:     if len(xs) < 6:         xs
          5s bash   cat > /tmp/rprobes/rF_nested.py <<'EOF' def main() -> None:     rows: list[int] = [1, 2, 3]     print([[x * 2 
          5s bash   date; cd /home/runner/work/ail-ci/ail-ci; for m in ttypes.py; do bash ~/tools/cmp.sh /tmp/rprobes/$m /tmp/base
          2s bash   date; cd /tmp && rm -rf /tmp/dh /tmp/db; AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ai

FINAL VERDICT: ACCEPT  2026-10-24T01:19:55Z
