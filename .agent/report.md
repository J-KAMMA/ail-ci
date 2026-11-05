# job job-ctimes3-11060034  started 2026-11-05T15:36:19Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## ctimes3 report

**Cause.** `_check_int64_routed_augmented_powers`'s inner `scan` was called 1191 times on tally_lang (21 functions × many argument environments) and re-derived env-independent per-function data on every call: `_function_local_int_constants`, `_binding_counts`, two `_walk_own_scope` passes and `loop_scope_nodes`. That was 0.90 s of a 1.38 s profiled load (chain_relax: 0.032 s of 0.145 s). Three other checks also did full setup on trees with none of their target shape.

**Fix** (`ail_chatgpt.py`, `_load_sources` helpers only):
- cache the per-function static data by `id(function)` inside the routed check (1191 scans → 21 analyses);
- early return in both augmented-power checks when there is no `**=`, in the pow check when there is no `**`/`pow` name, and in the int-base check when there is no `int(...)` call.

All are pure short-circuits: same outputs, same refusal messages.

**Numbers** (`_load_sources`, median of 3; after via `lab/profile/run.py --no-profile`):

| task | before | after | ratio |
|---|---:|---:|---:|
| tally_lang | 0.3157 | 0.0647 | **4.88x** |
| berth_sim | 0.0536 | 0.0297 | 1.80x |
| chain_relax | 0.0334 | 0.0218 | 1.53x |
| echo_pack | 0.0426 | 0.0207 | 2.06x |
| ledger_bin | 0.0683 | 0.0323 | 2.11x |
| rail_transfer | 0.0949 | 0.0442 | 2.15x |
| scar_life | 0.0525 | 0.0261 | 2.01x |
| term_rank | 0.0554 | 0.0271 | 2.04x |
| ticket_audit | 0.1106 | 0.0562 | 1.97x |
| tree_fold | 0.1277 | 0.0553 | 2.31x |

Recorded runner base 0.946 s → ~0.19 s projected, inside the 0.30 s target.

**Verification.**
- Dump hashes over 10 `typed.py` + 10 `main.py` + first 200 corpus programs: **0 differences / 220** (text, contracts, unit map, notes, source map, and refusal messages/positions).
- `program.c` from `compile --debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`: **10/10 identical** hashes.
- Refusals identical to base: direct `b **= 40` and routed `power(10, 40)` → `int64 constant expression out of range: 1000…000`; `b **= 2` builds.
- Tests: `test_ail_load_sources_same` (new, registered in `tests.d`), `test_ail_ctime`, `test_ail_modules`, `test_ail_build_cache` (42), `test_ail_files`, `test_ail_corpus_findings3` pass. `test_ail_safetynet` has one failure, `S4_generators_gc`, which fails identically on the unmodified base — pre-existing and unrelated.
- Instruction counts could not be taken: `perf_event_open` is denied and valgrind is absent on this runner. Wall time is the evidence used (noted in `CTIME_LOAD.md`).

**Probes** (`bash ~/tools/cmp.sh`, general `AIL_UNIFIED_FORCE=1` and default builds):
- `p1_direct_aug` `/**=` out of range → refused by name (both builds); `p2_routed_aug` through a function argument → refused by name.
- `p3_aug_in_range` (positive and negative base) → matches CPython; `p12_plain` unary minus/plain powers → matches.
- `p4_pow_big` → refused; `p5_pow_fit` (`2**62`, `1**0`, `-2**3`, `2**-1`, `0**0`) → matches; `p6_pow_alias` (`p = pow`) → matches.
- `p7_int_big` → refused; `p8_int_fit` (decimal, whitespace, negative, hex, zero) → matches; `p9_int_empty` (`int("")` then a 40-digit text) → refused by name at the large constant.
- `p10_containers` (pow via list item, dict value, class attribute, literal subscript) → matches.
- `p11_shadowed` (user `pow`/`int`) → refused by name (`int` shadows the built-in type), same message on base.

Committed as `32c0c3d` on `job-ctimes3-11060034`; no push (the runner instruction forbids it), so no PR was opened. Manifest updated and `update_manifest.py --check` exits 0.
[commandcode stop=end_turn turns=91 out_tokens=55430]

## review 0
[model commandcode/deepseek-v4.1-flash]
## ctimes3 review

**What the diff really does.** In `AIL_CURRENT/ail_chatgpt.py` only: (a) `_check_int64_routed_augmented_powers.scan` now gets per-function env-independent data (`_function_local_int_constants`, `_scope_parameters`, `_binding_counts`, store positions, `loop_scope_nodes`, `_walk_own_scope` list) from a `static_info` cache keyed by `id(function)`; (b) four checks (`_check_int64_pow_constants`, `_check_int64_augmented_powers`, `_check_int64_routed_augmented_powers`, `_check_int64_int_base_constants`) return early when `ast.walk` finds none of the node shapes they can refuse. That matches the report. The added early returns are sound: every refusal in those functions is rooted in `BinOp/Pow`, `Name('pow')`, `AugAssign/Pow` or `Call(Name('int'))` (checked `_check_augmented_power_scope`, the pow `check()`/wrapper paths and the int-base loop), and the cached data is read-only and env-independent.

**Probes** (`bash ~/tools/cmp.sh`, HEAD vs `/tmp/base`, both builds): `p1_routed_ok`, `p2_routed_list`, `p3_attr`, `p4_loop`, `p5_plain`, `p6_int_edges`, `p7_int_big`, `p8_aug_direct`, `p9_unrelated`, `p10_alias`, `p11_multi_env`, `p12_aug_in_range`, `p13_mixed_env`, `p14_module_loop`, `p15_user_pow`, `p16_int_nested`, `p17_alias_chain`, `p18_class`. Every probe is byte-identical to base: matching stdout, identical refusal text/line:col, or identical pre-existing runtime `OverflowError` (p18). No divergence found.

**Equivalence/size checks**
- `_load_sources` dump (merged text, contracts, unit map, notes, source map, refusal type/msg/line/col) over 340 inputs (10 tasks × typed/main, 200 corpus, 120 language_examples): **identical**.
- `program.c` (`--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`): **10/10 identical** to base; hashes match the report (tally `7e7357…`, etc.).
- Unrelated/no-feature probes and 3 gdev programs: generated C identical.

**Speed** (`lab/profile/run.py --no-profile --runs 3`, `_load_sources`): base→HEAD tally_lang 0.3033→0.0663 s, chain_relax 0.0333→0.0215, tree_fold 0.1200→0.0547; 8 gdev files all faster (g00_010 0.907→0.578 s). Base profile: `_check_int64_routed_augmented_powers` 0.840 s of 1.314 s; HEAD total 0.250 s, `_function_local_int_constants` calls 1007→46. No regression measured; target (≤0.30 s) met.

**Tests**: `test_ail_load_sources_same` passes and its three pinned digests were really taken from the base tree (recomputed). `test_ail_safetynet`: `S4_generators_gc` fails identically on base → pre-existing. `tools/update_manifest.py --check` exits 0. Instruction counts unavailable here as reported (`perf_event_paranoid=4`, no valgrind).

**Report claims**: cause, fix, dump hashes, 10 C hashes, refusals, manifest and the perf/valgrind limitation — verified. "1191 scans → 21 analyses" — the 21 is not what I measured (46 calls remain overall); the routed check is no longer in the profile top list, so the substance holds but that figure is unverified. `test_ail_ctime`, `test_ail_modules`, `test_ail_build_cache`, `test_ail_files`, `test_ail_corpus_findings3` — unverified (not run, per review limits).

**Pre-existing**: `test_ail_safetynet::S4_generators_gc` (missing output after the first print) fails the same way on unmodified `work`; probe p18 (`OverflowError: integer overflow in **`) is also identical on base. Neither blocks.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=53 out_tokens=28934]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T17:30:51Z
