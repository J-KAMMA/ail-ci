# fbnarrow4: slices, copies, sorts, and the default-on gate

`AIL_NARROW_INT` stays **opt-in**. The owner decision of 2026-11-06 says not to switch a default;
the numbers below are also short of the gate (the tree_fold peak target is 330 MiB, and one row is
not measured).

## New list shapes this step supports

`x[a:b]`, `x[a:b:c]` (same width as the source), `x.copy()`, `list(x)`, `x + y` (the runtime
widens on push, so no range proof is needed), `x.sort()`, `sorted(x)`, and `sorted(x)[a:b]` when
the source is narrow. A key sort column (`_ail_sk1_*`) is still a comprehension local and is not
narrowed: the key lambda reads its int lists through the ordinary subscript emitter, which works,
but the analysis does not yet treat the column itself as narrow. Widening cannot happen in a copy
or a sort (no new values), so the width carries over. Field `dep` (`t.dep[j] -= 1`) and the keyed
sort over `t.par` keep those two lists int64 (augmented index write and a lambda read).

## tree_fold (N = 3,000,000, same input as `lab/mem/NARROW.md`)

| | default | `AIL_NARROW_INT=1` | change |
|---|---:|---:|---:|
| peak RSS, `/usr/bin/time -v`, median of 3 (KiB) | 367,240 | 355,600 | **−3.17%** |
| stdout | identical on the perf input and all public cases checked | | |
| binary size (bytes) | 86,568 | 86,864 | +0.34% |

This is a GitHub Actions runner (4 cores). The target of 330 MiB is **not met**; the lists that stay
int64 are named above. `w` now narrows because `.copy()` is supported (it was the only use keeping
it int64), so the two live `w` sites (64.0 MiB in `NARROW.md`) are no longer 8-byte.

## Gate rows (not complete)

| row | result |
|---|---|
| run instructions (10 compare tasks, 6 rc programs) | **not measured** (time budget; no PMU on this runner) |
| peak RSS, none higher by >1% | only tree_fold measured (−3.17%); other 9 tasks/6 programs not run |
| binary size, none larger by >2% | only tree_fold measured (+0.34%) |
| output differences on public/hidden cases | tree_fold perf + first public cases: 0; full 55-case sweep not run |
| first 100 corpus programs unchanged | not run |
| 20 shards green | not run |

Because the gate is incomplete and one row was not measured, the default is not flipped. Fixing
`dep`, the keyed sort over `par`, the `[0] * n` locals and the augmented index writes on `sub`,
`cs`, `pos` and `cc` is the remaining work toward 330 MiB.

# fbnarrow3: `ail_ilist` for `list[int]` locals and class fields (opt-in `AIL_NARROW_INT=1`)

The typed (legacy) emitter stores a `list[int]` local or class field as `ail_ilist` when every
use of it is one of `.append(v)`, `len(x)`, an int index read or write (negative indexes as
today), `for v in x`, `x.pop()`, `x.clear()`, a whole store into a field or local of the same
kind, or a pass to a list that is itself narrowed. Anything else — a slice, `+`, `*`, `in`,
`index`, `count`, a sort with a key, `.copy()`, `.reverse()`, an augmented index write, a second
name, a store into another container, a builtin, FFI, the hybrid boundary, a lambda or a
comprehension body — keeps `ail_list`. Without the variable no list is narrowed and the emitted C
is byte-identical to the base.

An `ail_ilist` stores `int32_t` values in `p`; a value outside int32 widens the list at run time
to an `int64_t` buffer `q` (the list keeps its values exactly; it never truncates). `wide` marks
that state, and `p == NULL` in a wide list so the hot accessors test a pointer they already load.
The runtime widening is exercised by `test_ail_narrow_int.py` (int32 boundaries, a field widened
in one function and read in another).

## tree_fold: the instruction stop rule won

The first cut narrowed `tree_fold`'s `w`, `dep` and `par` fields and the matching locals and
cost **+11.35%** run instructions over the default build (callgrind `Ir` at N = 300k), because
every access carried the `p` test and every append/index write the int32 range test. That is
above the brief's +1% limit, so those lists now stay `ail_list`:

| list | use that keeps it `ail_list` |
|---|---|
| field `w` | `sub = t.w.copy()` — `.copy()` is not in the set (fbnarrow4 adds copies) |
| field `dep` | `t.dep[j] -= 1` — an augmented index write is kept int64 (still exact) |
| field `par` | `idx.sort(key=lambda i: (t.par[i], ...))` — a sort with a key / lambda body |
| local `w`, `dep`, `par` | stored into the int64 fields above, not a store of the same kind |
| local `sub` | `t.w.copy()` and a `[0] * n`-free build; not a whole empty-list binding |
| `cs`, `mp`, `ni`, `keep`, `idx` | `[0] * n`, `.copy()`, a comprehension, or a sort-key column |

The lists that do narrow in `tree_fold` are `v_stack` (`parse_tree`), `v_ord` (`rebuild`),
`v_codes` and `v_iargs` (`main`). They are all built from `.append`/index/`for in` and are not
stored into a non-narrow field.

| `tree_fold` (N = 3,000,000) | default | `AIL_NARROW_INT=1` | change |
|---|---:|---:|---:|
| peak RSS, `/usr/bin/time -v` (KiB) | 367,304 | 367,320 | +0.00% |
| run instructions, N=3000 (`ptrace` single-step count) | 8,721,379 | 8,608,126 | **−1.30%** |
| run instructions, N=300 (`ptrace` single-step count) | 1,113,047 | 1,105,591 | −0.67% |
| stdout | identical on all 55 public+hidden cases and the perf input | | |

This runner has no CPU PMU (`perf_event_open` is denied) and no valgrind, so the instruction
numbers are a real single-step instruction count at smaller N, not a gcov estimate. The ratio is
stable from N=300 to N=3000. The RSS target (within 3% of fbnarrow1's emulated 379,132 KiB) is
**not** met by this build: the three big fields stay int64 for the uses in the table above, so
the peak is the default peak. This is the brief's stop-rule escape: the offending lists are named
here and their blocking uses are recorded.

## The other nine compare tasks

511 public+hidden cases: narrow output and exit status equal both the default build and each
task's CPython `reference.py`; 0 differences. Peak RSS (one `/usr/bin/time -v` run per build,
narrow vs default, KiB):

| task | default | narrow | change |
|---|---:|---:|---:|
| berth_sim | 245,604 | 247,664 | +0.84% |
| chain_relax | 3,896 | 3,828 | −1.75% |
| echo_pack | 354,272 | 354,216 | −0.02% |
| ledger_bin | 338,024 | 337,152 | −0.26% |
| rail_transfer | 28,812 | 28,696 | −0.40% |
| scar_life | 17,536 | 17,664 | +0.73% |
| tally_lang | 1,500 | 1,504 | +0.27% |
| term_rank | 160,912 | 144,952 | −9.92% |
| ticket_audit | 254,736 | 254,244 | −0.19% |

Every row is within 1% of default. The rows that rise are a few KiB of noise on small processes;
none of the nine is worse than default by more than 0.84%.

## `pyfunc.py` changed lines: 62 (51 insertions, 11 deletions)

1. `from ir import narrowint` and `ctx.narrow_int = narrowint.locals(fn, ctx, ctx.classes)`
   (the kind-selection hook beside the packed `ail_pslist` local selection).
2. Local declaration: `ail_ilist` instead of `ail_list` for a chosen local — both the plain
   automatic and the `try` frame-cell declaration (a narrowed local that a `try` region owns is
   a frame cell too, so its cell must have the narrowed type).
3. Index read: `ail_narrow_get`, index write: `ail_narrow_set` (two sites).
4. `for v in x` over a chosen local: `ail_ilist_get` element read in `_iter_plan` and in the
   plain-`for` emitter.
5. `_numeric_snapshot`: `__auto_type` source and `ail_list_snapshot_any(_source)` so a wide field
   snapshot is read from `q`.
6. Field index read: `ail_ilist_field_get(&owner->f_x, i)` for a chosen field.
7. Field declarations in `_class_c_decls`; `_narrow_field` helper and its use in
   `_guard_plain_list`, `_guard_field_key`, `_span_cache_plan`, `_numeric_field_move_out`
   (the arena passes must not take a `p`/`n` span of a list that may be wide).
8. `narrowint.prepare(...)` in `_to_c_once`, and `narrowint.blocks_ir(...)` in
   `_one_function_finish` (only a function that touches a narrowed **field** must stay on the
   legacy emitter; IR has no `ail_ilist` code, so a local-only function keeps IR and is unchanged).

## Checks

- `python3 AIL_CURRENT/test_ail_narrow_int.py`: 9 tests, OK (int32 boundaries, int64 limits, a
  stop beyond int64 with the same `OverflowError: integer overflow in +` text, a field widened in
  one function and read in another, negative indexes, the IndexError texts, a list through two
  calls, an empty list). Every program is built with the variable unset, set, and with
  `AIL_UNIFIED_FORCE=1`, and compared with CPython.
- `python3 AIL_CURRENT/test_ail_safetynet.py`: 5 tests, OK.
- `python3 AIL_CURRENT/test_ail_files.py`: 18 tests, OK (1 skipped).
  `python3 AIL_CURRENT/test_ail_corpus_findings3.py`: 2 tests, OK.
- The 10 compare tasks: 511 public+hidden cases, 0 stdout/exit differences between the narrow and
  default builds, and 0 against `reference.py` (both builds).
- Probes in `/tmp/probes` (`bash ~/tools/cmp.sh <probe> $PWD` and a manual `AIL_NARROW_INT=1`
  build): `int64`, `field_wide`, `index`, `through_calls`, `aliasing`, and `p19_try_for` (a
  narrowed local owned by a `try` frame cell, then `for v in xs`) — all match CPython on stdout
  and exit status except two behaviours that are identical on the base: CPython's "list
  assignment index out of range" text (AIL says "list index out of range") and an int64 overflow
  inside `try` on the typed path.
- Byte-identical `program.c` without the variable: the only `pyfunc.py` change on the default
  path is guarded by `v in ctx.narrow_int`, which is empty when `enabled()` is false; the
  `narrowint.py` analysis returns immediately without the variable. Spot-checked
  `tree_fold` with `--debug-dir`, `AIL_NO_CACHE=1`, `PYTHONHASHSEED=0` (same hash as the
  pre-change build).
