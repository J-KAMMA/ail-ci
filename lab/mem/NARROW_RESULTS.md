# fbnarrow3: `ail_ilist` for `list[int]` locals and class fields (opt-in `AIL_NARROW_INT=1`)

The typed (legacy) emitter stores a `list[int]` local or class field as `ail_ilist` when every
use of it is one of `.append(v)`, `len(x)`, an int index read or write (negative indexes as
today), `for v in x`, `x.pop()`, `x.clear()`, a whole store into a field or local of the same
kind, or a pass to a list that is itself narrowed. Anything else — a slice, `+`, `*`, `in`,
`index`, `count`, `sort(key=...)`, a second name, a store into another container, a builtin,
FFI, the hybrid boundary, a parallel body — keeps `ail_list`. Without the variable no list is
narrowed and the emitted C is byte-identical to the base.

An `ail_ilist` stores `int32_t` values in `p`; a value outside int32 widens the list at run time
to an `int64_t` buffer `q` (the list keeps its values exactly; it never truncates). `wide` marks
that state, and `p == NULL` in a wide list so the hot accessors test a pointer they already load.

## Numbers (`tree_fold`, N = 3,000,000)

| | default | `AIL_NARROW_INT=1` | change |
|---|---:|---:|---:|
| peak RSS, median of 3 (`/usr/bin/time -v`, KiB) | 367,216 | 332,100 | **−9.57%** |
| run instructions, `Ir` at N=300k (`valgrind --tool=callgrind`) | 856,931,476 | 954,184,959 | +11.35% |
| stdout | identical on all 55 public+hidden cases and the perf input | | |

This runner has no CPU PMU (`/sys/bus/event_source/devices/cpu` is absent; `perf_event_open` is
denied), so instruction counts are callgrind `Ir` at N = 300k, as the brief requires.

The RSS target was "within 3% of fbnarrow1's emulated value" (379,132 KiB → at most 390,506 KiB):
332,100 KiB is 12.4% **below** it, so the target is met without the escape hatch. fbnarrow1's
emulated build cost 945,832,434 Ir at the same size; this build is +0.88% over that. Against the
*default* build the instructions are +11.35%: every narrowed access carries a `p` test and, on
`append`/index write, an int32 range test. That is above the brief's +1% reading, and no list was
left int64 to get there (see below); it is the dynamic widening check, not a missing operation.

## Which lists narrow

`tree_fold` (from the `--debug-dir` output): fields `f_w`, `f_dep`, `f_par`; locals `v_stack`,
`v_w`, `v_dep`, `v_par` (in `parse_tree`, `compact`, `rebuild`, `fold`), `v_ord`, `v_codes`,
`v_iargs`. The other `list[int]`s stay `ail_list` because at least one use is outside the set:
`v_cs`, `v_ni`, `v_mp`, `v_sub`, `v_keep`, `v_idx` are assigned `[0] * n`/`.copy()`/a comprehension
or are passed to a parameter that is not itself narrowed; `v_sub` also takes `t.w.copy()`; `idx`
is read as a `sort(key=...)` key column; `v_ni`/`v_mp` come out of `[0] * n` and are handed to
`counts`/`rebuild`. The ten compare tasks build with the variable set; their narrowed locals are
those only ever appended, indexed, walked, popped or cleared.

A list is *not* left int64 for range reasons: `w` in `tree_fold` reaches values that would not fit
in int32 on other inputs (folded weights), and the runtime widens it instead of stopping.

## `pyfunc.py` changed lines: 61 (50 insertions, 11 deletions)

1. `from ir import narrowint` and `ctx.narrow_int = narrowint.locals(fn, ctx, ctx.classes)`
   (the kind-selection hook beside the packed `ail_pslist` local selection).
2. Local declaration: `ail_ilist` instead of `ail_list` for a chosen local.
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
- The 10 compare tasks: 511 public+hidden cases, 0 stdout/exit differences between the narrow and
  default builds, and 0 against `reference.py` (both builds).
- Byte-identical `program.c` without the variable (`AIL_NO_CACHE=1`, `PYTHONHASHSEED=0`,
  `--debug-dir`) against a `work` worktree: the 10 compare tasks and the first 100
  `lab/corpus/programs` files.
- Probes in `/tmp/probes` (`bash ~/tools/cmp.sh <probe> $PWD` and a manual `AIL_NARROW_INT=1`
  build): `bounds`, `int64`, `field_wide`, `negative` (in the test module), `index`,
  `through_calls`, `aliasing` — all match CPython on stdout and exit status except two
  behaviours that are identical on the base: CPython's "list assignment index out of range" text
  (AIL says "list index out of range") and an int64 overflow inside `try` on the typed path.
