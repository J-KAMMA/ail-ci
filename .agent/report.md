# job job-fdarr1-11060755  started 2026-11-05T23:05:24Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final state is committed as `16b9d1a` on `job-fdarr1-11060755` (not pushed: Appendix A forbids `push`, and the run notes say do not push, so no PR was opened).

## What now works

`ta.f32` is out of `LATER`. 1-D f32 arrays: construction (`array/zeros/full/frombytes`), indexing/slices/slice-assign, `+ - * /`, unary `-`, `abs`, `+= -= *= /=`, `sqrt exp log tanh`, `minimum/maximum/clip`, `sum`/`dot` (16-lane/1024-block order with an f32 accumulator; `acc=ta.f64` widens), `min/max/argmin/argmax`, `tolist`/`tobytes`/`repr`, `==`, `astype` f32↔f64, f32↔int32. f16/int8 and 2-D f32 are still refused by name.

Implementation: an f32 element is a binary64 list slot holding an exact binary32 value; every op computes in binary64 and rounds once. `_ail_ta3_bits`/`_ail_ta3_unbits` implement `r_f32` in integer arithmetic (nearest-even, gradual underflow, overflow→inf, canonical `7fc00000`) — no `float` arithmetic in C, no `struct` on the typed path, and f64/int32 code paths are untouched.

## Numbers

- `python3 AIL_CURRENT/test_ail_array_t3.py`: **22 tests OK**, 8/8 cases in the default build **and** `AIL_UNIFIED_FORCE=1`, stdout + exit status equal to CPython with the reference; default builds emit no "general path" note.
- `test_ail_array_t2` 23 OK, `test_ail_array_t6` 28 OK, `test_ail_array_ref` 38 OK, `test_ail_files` 18 OK (1 skip), `test_ail_corpus_findings3` 2 OK.
- `test_ail_safetynet`: 5/5 OK **without** a `ulimit`; under my own `ulimit -v 4000000` its `S4_generators_gc` case runs out of memory (it does not import `ail_array`; passes at 158 s uncapped).
- r_f32 vs `struct`: 300k random doubles, all 2047 exponents × 6 mantissas, 100k near-boundary perturbations, 1.5M f32 round trips — **0 mismatches**.
- Non-array C: 6 of the `lab/compare/src` programs build with both the pre-change and the current compiler and their `program.c` is byte-identical (the embedded absolute path aside); the other 4 fail with the same exit status in both trees.
- `git diff --stat HEAD~1`: only `array_t3_cases/*`, `test_ail_array_t3.py`, `tests.d/test_ail_array_t3.txt`, the two pkg-v12 files, TYPED_ARRAY.md's T3 lines, the 5 `manifest.d` files `update_manifest.py` wrote — plus one file I had to touch, below.

## Probes (self-check)

`/tmp/probes/check_f32.py` (rounding oracle), `probe_a.py` (array through function params/returns, aliasing `z *= z`, empty array, negative index, slice copy independence, int scalars, values from a list item), `probe_b.py` (store via `a[k] = list[k]`, list built with `append` handed to `ta.array`, n=1023 planted specials, `acc=ta.f64` vs default, min/max/clip, astype both ways). All built in both builds and matched CPython+reference exactly.

## One deviation you must know about

`AIL_CURRENT/test_ail_array_t2.py` had two assertions that f32 is *refused* (`REFUSED`'s `("f32", …)` entry and the CLI refusal test compiling `ta.zeros(3, ta.f32)`). T3 makes both false, and the done-check requires t2 to still pass, so I removed the obsolete f32 entry and pointed the CLI test at `ta.f16` (3 lines). That file is outside the brief's edit list; nothing else outside the list changed.
[commandcode stop=end_turn turns=62 out_tokens=91345]

## review 0
[model commandcode/deepseek-v4.1-flash]
Done reviewing. Time used: ~19 min.

## What the change really does
Lifts f32 from `LATER` and adds a 1-D f32 dtype (`'3'`/`A3`): compiler lowering in `pkg-v12/ailarray.py` plus a 604-line runtime in `prelude_ailarray.py` (elements are binary64 list slots holding exact binary32 values; `_ail_ta3_bits/_unbits` implement r_f32 in integer code; 16-lane/1024-block sum and dot). Adds 8 case files, `test_ail_array_t3.py`, registration, T3 doc lines, manifests — and edits `test_ail_array_t2.py` (outside the brief's file list) to drop two now-false "f32 is refused" assertions. The report describes this accurately.

## Probes (all in /tmp/rprobes, both builds vs CPython+reference)
- `p1_ops`: + - * / with inf/-0/overflow arrays, reflected scalars, int/bool scalars, in-place self-alias, `abs`/`neg`, min/max/clip/NaN — **same**.
- `p2_red`: sum/dot/min/max/argmin/argmax at n = 0,1,15,16,17,1023,1024,1025,5000 with planted 1e30/-0.0; `acc=ta.f64`; empty reductions; ±inf/NaN — **same**.
- `p3_cast`: astype f32↔f64, f32↔int32 trunc/nearest/saturate, NaN/inf/overflow/`wrap`/bad-arg errors, `-0.0`, subnormals — **same**.
- `p4_misc`: slices/slice-copy/reverse-setslice/self-slice, negative index, live mutation during iteration, equality incl. NaN/-0.0, attribute/argument/dict-scalar paths — **same** after excluding pre-existing failures.
- `p5_bytes`/`p7_nan`: frombytes/tobytes/repr, 14 bit patterns, halfway store values, overflow→inf — **same** for canonical NaNs; non-canonical NaN payloads → runtime `RuntimeError` (see pre-existing).
- `p6_fn`: sqrt/exp/log/tanh edge set, mul overflow, int-scalar min/max/clip, `acc=f32` — **same**, except `acc=ta.int32` text (pre-existing).
- `p8_edge`: empty ops, slice step 0, out-of-range, builtin `list/sum/min/max/sorted`, signed-zero division, in-place shape error — **same**.
- `p9_alias`: list/bytearray copy-on-construct, overlapping and reversed setslice, function-mutation aliasing, tolist/slice/tobytes/copy independence — **same**.
- C invariance: `lab/compare/src/berth_sim/main.py` and an f64+int32 array program produce byte-identical `program.c` (path aside) on base vs HEAD.

## Tests
`python3 tools/par_check.py -j 2 test_ail_array_t3 test_ail_array_t2` → both **ok**. `test_ail_safetynet` fails only under my 4 GB `ulimit -v` (S4_generators_gc truncated); rerun without ulimit → **ok**, 180 s. `test_ail_safetynet.py` never mentions `ail_array`, so that is environmental and matches the report.

## Claims
Verified: f32 works / f16-int8-2D refused; 8/8 both builds; t2 still passes; safetynet behaviour incl. the S4 memory note; non-array C unchanged (spot-checked 2 programs); file list (plus the disclosed t2 edit); no speed-sensitive compiler change. Unverified: exact test counts (22/23/28/38/18/2), r_f32 vs `struct` 300k/1.5M figures, the other `lab/compare` programs, CI (not run).

## Pre-existing (not blockers)
- `frombytes` of a non-canonical NaN payload (`0100807f`, `ffffffff`, `0000c0ff`) prints `nan` and preserves bytes in CPython but raises `RuntimeError` in native code. The identical limitation exists for f64 on the base (`...stage T2...`), and the brief says to follow T2 for errors/refusals.
- `ta.sum/dot(a_f32, acc=ta.int32)` raises `ValueError` with text "acc= is for float arrays; int32 sums are exact" instead of the reference's "acc=int32 would narrow f32". The f64 equivalent on the base has the same mismatch.
- Typed-path refusals for an int attribute operand and a dict-value scalar (`box.vals * box.n`, `a * d["x"]`) — identical on the base for f64.

Process note: editing `test_ail_array_t2.py` is outside the brief's allowed files; it is disclosed and only deletes assertions the intended change falsifies.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=55 out_tokens=43772]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T01:27:48Z
