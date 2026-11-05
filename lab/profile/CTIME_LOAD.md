# ctimes3: `_load_sources` on tally_lang

Base: `origin/integ` after ctimes2.  The only compiler edit is in `AIL_CURRENT/ail_chatgpt.py`,
inside `_load_sources` and four helpers that no other caller uses.

## 1. The cause

`cProfile` around one `_load_sources` call on `lab/compare/src/tally_lang/main.ail`, the same
arguments `compile` passes (`local_imports=True`, `notes`, `source_map`):

| task | profiled total | `_check_int64_routed_augmented_powers` | its `scan` | `scan` calls |
|---|---:|---:|---:|---:|
| tally_lang | 1.382 s | 0.898 s | 0.837 s | 1191 |
| chain_relax | 0.145 s | 0.032 s | 0.020 s | 14 |

The function is `_check_int64_routed_augmented_powers` (line ~3561): it follows the call graph
from module-scope calls to find an augmented power `b **= e` that constant arguments reach.  Its
inner `scan(function, env, depth, seen)` is entered once per (function, argument environment), and
tally_lang's mutually recursive parser gives 1191 of those over 21 functions.  Every entry redid
the env-independent work for that function: `_function_local_int_constants` (113 calls, 0.295 s
cumulative), `_binding_counts`, two `_walk_own_scope` passes and `loop_scope_nodes`.  With 7.8
million function calls in the profiled load, this one recursive walk was 65% of the load.

Two more checks paid their full setup on a tree that contains none of the shape they look for:
tally_lang (like all ten compare tasks and every `lab/corpus/programs` file) has no `**=` and no
`pow(`/`**`, yet `_check_int64_augmented_powers` (0.027 s), `_check_int64_routed_augmented_powers`
(0.028 s) and `_check_int64_pow_constants` (0.017 s) each built their maps first.  No other file
or function outside `ail_chatgpt.py` is involved.

## 2. The fix

1. `_check_int64_routed_augmented_powers`: cache the per-function static data
   (`_function_local_int_constants`, `_scope_parameters`, `_binding_counts`, the stored-name
   positions, `loop_scope_nodes`, `_walk_own_scope`'s node list) by `id(function)` inside the
   call.  Directory entry: `static_info`.  1191 scans now do 21 analyses: 0.316 -> 0.150 s.
2. Both augmented-power checks return before any setup when `ast.walk` finds no
   `AugAssign` with `ast.Pow`; that is the only node either one can refuse, so the result and
   every message are unchanged.
3. `_check_int64_pow_constants` returns when the tree has no `BinOp` with `ast.Pow` and no
   `Name('pow')`; every rule in it is rooted in one of those, so again nothing can be refused.
4. `_check_int64_int_base_constants` returns when there is no `Call` to `Name('int')`.

## 3. `_load_sources` seconds, before and after (median of 3)

"before" is a direct `_load_sources` call measured on this runner from a copy of the base file;
"after" is `lab/profile/run.py --no-profile --runs 3`, which times the function in the real parent
build.  Both are seconds.

| task | before | after | ratio |
|---|---:|---:|---:|
| berth_sim | 0.0536 | 0.0297 | 1.80x |
| chain_relax | 0.0334 | 0.0218 | 1.53x |
| echo_pack | 0.0426 | 0.0207 | 2.06x |
| ledger_bin | 0.0683 | 0.0323 | 2.11x |
| rail_transfer | 0.0949 | 0.0442 | 2.15x |
| scar_life | 0.0525 | 0.0261 | 2.01x |
| **tally_lang** | **0.3157** | **0.0647** | **4.88x** |
| term_rank | 0.0554 | 0.0271 | 2.04x |
| ticket_audit | 0.1106 | 0.0562 | 1.97x |
| tree_fold | 0.1277 | 0.0553 | 2.31x |

A real `compile` run (the harness's own load timer) gave tally_lang 0.3105 s base and 0.1410 s
after the memoisation alone; the shape guards took the direct measurement to 0.0663 s.

On the recorded runner (`CTIME_2026-11.md`: tally_lang 0.946 s, wall 5.359 s) a 4.88x cut puts
`_load_sources` near 0.19 s, inside the 0.30 s target.  The base share was 17.7% (Amdahl 1.21x);
after it is about 3.5% of wall on this runner (0.0647 of 1.8335 s).  The recorded-runner wall
would fall by ~0.75 s, 1.16x on tally_lang and ~1.02x pooled over the ten.

## 4. Verification

* **Dump hashes, 0 differences.**  A dump over the 10 `typed.py`, the 10 `main.py` and the first
  200 `lab/corpus/programs` files (220 inputs) hashes the merged text, the contracts flag, the
  unit map, the notes and the source map, and records refused programs by exception type,
  message, line and column.  Base and after are identical on all 220 rows.
* **`program.c`, 0 of 10 changed.**  `compile --debug-dir` with `PYTHONHASHSEED=0` and
  `AIL_NO_CACHE=1` for all ten tasks: the base and after `program.c` SHA-256 are equal per task
  (berth_sim `1c2847...`, chain_relax `22c017...`, echo_pack `791707...`, ledger_bin `33c5ba...`,
  rail_transfer `c04f5e...`, scar_life `fec79b...`, tally_lang `7e7357...`, term_rank `534ba6...`,
  ticket_audit `34d333...`, tree_fold `3f3245...`).
* **Refusals.**  A direct `b **= 40` and a routed `power(10, 40)` are still refused with
  `int64 constant expression out of range: 1000...000` on both base and after; `b **= 2` still
  builds.
* **Instruction count.**  `tools/icount.c` builds, but `perf_event_open` is denied on this runner
  and valgrind is not installed, so no instruction counts were available; the wall numbers above
  are the evidence used.
* **Tests.**  `test_ail_load_sources_same` (new, registered by
  `AIL_CURRENT/tests.d/test_ail_load_sources_same.txt`), `test_ail_ctime`,
  `test_ail_modules` and `test_ail_build_cache` pass (42 tests), as do `test_ail_files` and
  `test_ail_corpus_findings3`.  `test_ail_safetynet` has one failure, `S4_generators_gc`; it
  fails the same way on the unmodified base file, so it is pre-existing and unrelated.
