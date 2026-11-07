# EMIT_LEAN — emitting leaner typed C

Design for the measurement in `lab/emit/RESULTS.md`. That file measures, on the six programs the
ticket names, where the typed emitter's instructions are, and gives a **measured** bound for each
construct: the Ir saved when the construct is removed from a copy of the generated C, rebuilt with
the same flags, stdout byte-identical. This file ranks those bounds and specifies the three
changes worth queueing first.

No compiler was changed by this lane. Everything below is a plan with a number behind it.

## Ranking by measured Ir saved

Isolated hand edits from `lab/emit/bounds.py`, de-duplicated where two edits remove the same
instructions. `% extra` is the saved Ir as a share of that program's real AIL−C difference.

| # | cause | measured saved | program | bound edit | % of program | % extra |
|---:|---|---:|---|---|---:|---:|
| 1 | Generic int-dict/table probe where a lean probe exists | **1,927M** | echo_pack | `echo_pack_dict2` | 35.4% | 53.8% |
| 2 | Container invariant test on every list operation | **1,368M** | ticket_audit | `ticket_audit_nometa` (`data/bounds_meta.json`) | 10.5% | 12.9% |
| 3 | Recursion-depth guard checked at every function entry | **1,184M** | tally_lang | `tally_lang_norec` | 6.1% | 15.4% |
| 4 | Overflow-checked arithmetic per Python operation | **1,012M** | ledger_bin + ticket_audit | `ledger_bin_noovf` 849M + `ticket_audit_noovf_int` 164M | 16.2% / 1.3% | 33.9% / 1.5% |
| 5 | Generic list/sequence helpers where a direct write exists | **1,001M** | ticket_audit, tree_fold, echo_pack | `noview` 544M + `nopop` 228M + `nospan` 152M + `pushloop` 76M | | |
| 6 | Bounds-checked accessors (`ail_bytes_get`, `ail_list_span_get`…) | **952M** (overlaps #5/#6) | 4 programs | `tree_fold_nobget` 167M + `echo_pack_nobounds` 89M + the same calls inside `noview` | | |
| 7 | ASCII/UTF-8 classification, generic split and int parse | **490M** | berth_sim | `berth_sim_noascii` | 5.9% | 20.6% |
| 8 | One-statement-per-op shape, local rewrite of one loop | **182M** | echo_pack | `echo_pack_cmpmatch` | 3.3% | 5.1% |
| — | `always_inline` a helper | **4.7M (negative)** | echo_pack | `echo_pack_ai_append` | 0.09% | 0.13% |

Two facts set the design's priorities.

* **Rank 2 is measured but not queueable as a removal.** `ail_blist_meta` is a memory-safety
  invariant on a list header; deleting it trades correctness for 10.5% of one program. The safe
  sub-step is to hoist it from read-only views to creation/resize, which needs the same
  local-escape proof design 1 builds, so it is a follow-up rather than a step here. The three
  **queueable** changes are therefore ranks 1, 3 and 4 (designs 1, 2, 3 below).
* **Those three are safe, local changes with a measured bound.** They total 4.1e9 Ir across the six
  programs, about 13% of the 31.1e9 total extra, and they do not change the semantics of a single
  Python operation: the probe, the depth check and the arithmetic keep their meaning.
* **The shape is bigger than all of them, and no local edit bounds it.** `temporaries/one-statement`
  is 17.6e9 attributed Ir (30.7% of all emitted lines); the largest edit that removes one instance
  is 182M. Changing the expression shape means rewriting the typed emitter's expression lowering,
  not editing a helper. That is a separate, larger lane ("EMIT_SHAPE", not in this split), and it
  is where the remaining 54–100% of `other` lives.

Rank 2 is a required semantic check, not a bug. The change below does not remove it; it moves it
from every entry to the recursive edges, which is where depth can actually grow. That keeps the
same rejection boundary (see the correctness argument in step 2.2).

## Design 1 — lean int-dict probe (measured bound 1,927M)

### What produces the cost

`ir/emit_c.py:dict_op` (the method starting at line 1693) lowers every `dict.has/need/get/put` on
an int-keyed dict to a call of a generic `ail_idict_*` helper. Those helpers are implemented over
the general `ail_tab` in `cruntime.py`: `ail_idict_need` is

```c
static inline __attribute__((always_inline)) int64_t ail_idict_need(const ail_idict *T, int64_t key) {
    ail_idict_check(T); return ail_tab_need(&T->table, key);
}
```

and the hot inner loop is `cruntime.py:ail_tab_hslot` (line 5350):

```c
static inline __attribute__((always_inline)) int64_t ail_tab_hslot(const ail_tab *T, int64_t k) {
    int64_t m = T->cap - 1, i = ail_hash(k) & m;
    while (T->used[i] && !(T->used[i] == 1 && T->ent[i].key == k)) i = (i + 1) & m;
    return i;
}
```

That loop serves three table modes (bits plan, hash, ordered), tombstones (`used == 2`) and
deletion, so every probe reads two arrays (`used[]`, `ent[].key`) and tests the tombstone case.
`echo_pack`'s `ail_tab_hslot` is 1,458M Ir and `ail_hash` another 241M; the C's `key()` is a
four-line inlined hash and `pack` probes four parallel arrays directly.

### The change

Two parts, both invisible to the language:

1. **Runtime (`cruntime.py`).** Add a no-tombstone, single-array probe used only by dicts that the
   IR marks `fast`:

   ```c
   /* keys[i] == 0 means empty; no deletion, so a probe stops at the first empty slot. */
   static inline __attribute__((always_inline))
   int64_t ail_hprobe(const int64_t *keys, int64_t mask, int64_t k) {
       int64_t i = ail_hash(k) & mask;
       while (keys[i] && keys[i] != k) i = (i + 1) & mask;
       return i;
   }
   ```

   `ail_idict_need_fast`, `_has_fast`, `_put_fast`, `_get_fast` call it; the existing
   `ail_idict_*` functions keep the general table and its checks unchanged.

2. **IR + emitter (`ir/lower.py`, `ir/emit_c.py:dict_op`).** Mark a dict `fast` when, in the whole
   function, it is a local created by `{}`/`dict()`, never passed to a call, never `del`'d,
   never iterated while inserted into, and every access is `has/need/get/put` with an int key.
   `dict_op` then emits the `_fast` names; when the marker is absent it emits exactly today's
   names. The mark is a new attribute on the `dict.alloc` instruction, computed by the pass that
   already walks local containers in `ir/lower.py` (`_range_arg_int64`/`slice_bounds` live there).
   No new IR op is needed.

### Correctness

The representation of a `fast` dict is the same open-addressed key array with a distinct empty
sentinel; it preserves insertion semantics because `ail_tab`'s order list is not used by an
`idict` that is never iterated (that is part of the mark). Proof obligations:

* **CPython-identical on the corpus** — `.agent/cmp.sh` on every `corpus/**/*.py` program, both the
  default and `AIL_UNIFIED_FORCE=1` builds; every program must match stdout, stderr's last line and
  exit status, or be refused by name. The new test module drives the boundaries directly: empty
  dict, one key, a full table (growth), `get(k, default)` on a missing and a present key, a key
  whose hash collides with another, negative keys, `INT64_MIN`/`INT64_MAX` keys, a dict read after
  a resize, a dict inside a loop, and a dict that must *not* be marked fast (passed to a
  function, `del`'d, iterated) — these last cases are the control: their emitted C must be
  byte-identical to the base build.
* **icount no loss on any compare program** — build all ten `lab/compare/src/<task>` typed sources
  before and after and compare Ir with `lab/roof/measure.py` (or `tools/icount.c` on a
  hardware-PMU host); no program may regress. The expected gain is concentrated in `echo_pack`
  (1.9e9 bound) and `ledger_bin`.
* **No output difference on the hand-edited bound** — `echo_pack_dict2` already shows the bound is
  semantically neutral on the perf input; the implementation is held to the stricter corpus test.

### exe bytes

Allowed to change. Direction: the emitted C is unchanged for non-fast dicts; for fast dicts the
call sites use shorter helper names but the *runtime selection* grows by one small inline helper
(about 30 lines of C, and only when a fast dict exists). Binary size should be within noise;
`lab/compare` already records size and the task permits the change.

### Implementation steps (each ≤2 h)

| # | step | files | test |
|---:|---|---|---|
| 1.1 | Add `ail_hprobe` and the four `_fast` idict helpers, not yet selected by the emitter. | `AIL_CURRENT/python/pkg-v12/cruntime.py` (next to `ail_tab_hslot`, line 5350) | `AIL_CURRENT/test_ail_idict_fast.py` (unit: emitted C contains the helper; a probe program builds and runs) |
| 1.2 | Compute the `fast` marker in the local-container pass; add it to `dict.alloc`. | `AIL_CURRENT/python/pkg-v12/ir/lower.py` | same module: a program with a passed/iterated/deleted dict must not carry the marker |
| 1.3 | Emit `_fast` names in `dict_op` when the marker is set; keep the old path otherwise. | `AIL_CURRENT/python/pkg-v12/ir/emit_c.py` (`dict_op`, line 1693) | `AIL_CURRENT/test_ail_idict_fast.py` + `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` |
| 1.4 | Measure and record: re-run `lab/emit/analyze.py --tasks echo_pack,ledger_bin` and `lab/emit/bounds.py --only echo_pack_dict2`. | `lab/emit/` | report Ir before/after; no other compare program may lose |

## Design 2 — recursion check at the recursive edge (measured bound 1,184M)

### What produces the cost

`ir/emit_c.py:emit` (line 763) emits the guard at the **entry** of every function that carries a
depth register:

```c
if (self.depth:
    self.parts.add('RECDEPTH')
    self.line(1, 'if (ail_d > AIL_MAX_RECURSION_DEPTH) ail_die("maximum recursion depth exceeded");')
```

`tally_lang`'s `ev__d` is called once per expression node and per operator dispatch; the compare +
branch is 988M Ir by itself. Removing the line saves 1,184M (the line plus its effect on the
prologue's scheduling). The same function's frame is another 3,949M (`call-frame` in
`lab/emit/RESULTS.md`), but that is a register-pressure problem, not a removable check, and is not
part of this step.

### The change

Depth only grows on a self-call, and `ir/emit_c.py:_depth_call` (line 675) already knows which
calls those are — it rewrites a self-call of a depth function to `f__d(args, ail_d + 1)`. Move the
test there:

```c
/* at each self-call site */
(ail_d + 1 > AIL_MAX_RECURSION_DEPTH
     ? (ail_die("maximum recursion depth exceeded"), 0)
     : ev__d(v_p, ir25, ail_d + 1))
```

and keep the entry guard only for functions that can receive a depth other than 0 from outside
the depth-carrying set (the IR knows: a depth function is entered from a non-depth caller with the
literal `0`, from `ev`-style wrappers with `0`, and from itself through `_depth_call`).

Correctness is exact, not approximate: the old code rejects a call when the *callee entry* sees
`ail_d > LIMIT`; the new code rejects the *call* when `ail_d + 1 > LIMIT`. Since the only call
that can raise `ail_d` by one is that self-call, the set of call stacks rejected is identical, and
the `ail_die` happens before the callee frame exists (same message, same exit status). The
one-argument `ev` wrapper calls `ev__d(..., 0)`; no guard is needed on an entry whose depth is a
compile-time 0.

### Correctness evidence

* **CPython-identical on the corpus** — `.agent/cmp.sh` on every `corpus/**/*.py`, both builds.
* **Recursion boundary** — `AIL_CURRENT/test_ail_recursion_stop.py` must still stop at the same
  depth with the same message; a new test builds a program that recurses to `LIMIT` and one to
  `LIMIT+1` and checks that the first completes and the second stops by name. The message is the
  one CPython's `RecursionError` wording would produce (`maximum recursion depth exceeded`); the
  test asserts the *same* boundary as the base build, not merely "it fails".
* **icount no loss on any compare program** — before/after Ir for all ten typed sources;
  `tally_lang` is expected to drop by ~1.1e9 and every other program must be unchanged.

### exe bytes

Allowed to change. The guard moves from a function prologue to call sites; the C text grows by one
conditional per self-call but the function body shrinks by one branch. Net binary size is within a
few hundred bytes per function; `tally_lang` should shrink because the hot function's entry
becomes smaller.

### Implementation steps (each ≤2 h)

| # | step | files | test |
|---:|---|---|---|
| 2.1 | Emit the guard in `_depth_call` around the self-call, keeping the entry guard for now (both checks, a safe intermediate). | `AIL_CURRENT/python/pkg-v12/ir/emit_c.py` (`_depth_call`, line 675) | `AIL_CURRENT/test_ail_recdepth_edge.py` |
| 2.2 | Drop the entry guard only for depth functions whose every non-self caller passes the literal 0; keep it otherwise. Record the caller classification on the function. | `AIL_CURRENT/python/pkg-v12/ir/emit_c.py` (`emit`, line 763), `AIL_CURRENT/python/pkg-v12/ir/lower.py` (depth-call marking) | same module + `test_ail_recursion_stop.py` |
| 2.3 | Measure `lab/emit/analyze.py --tasks tally_lang` and record the drop; run the three required modules. | `lab/emit/` | `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` |

## Design 3 — overflow-checked arithmetic only where it can overflow (measured bound 1,012M)

### What produces the cost

`ir/emit_c.py:instr` lowers `add/sub/mul` in mode `ck` to `_CK_HELPER` calls (line 961), and
`cruntime.py`'s `ck_add`/`ck_sub`/`ck_mul`/`ck_shl` do the checked operation plus a branch to
`ail_die`. `ledger_bin`'s varint reader performs four per input byte: `ck_add` 111M, `ck_mul` 418M,
`ck_shl` 373M, and `ck_sub`'s `%` is the hottest line in the program at 556M; the measured bound
is 849M. `ticket_audit`'s `ail_bytes_to_int` adds another 164M for a per-digit limit test that the
C does once, at the end.

The compiler already computes int64 bounds: `ir/lower.py:394` calls
`_bigcap.local_int_bounds(fn, ...)` and uses the result to set `mode='nonneg'` for flooring
division. That is the fact this change reuses.

### The change

In the binary-op lowering (the same place that assigns `ck`), ask the existing bounds pass whether
the result is provably in `[-2^63, 2^63-1]`:

* `x + y` with `lo(x)+lo(y) >= INT64_MIN` and `hi(x)+hi(y) <= INT64_MAX`;
* `x - y`, `x * y` with the usual interval arithmetic (bail out on unknown bounds);
* `x << k` with a constant `k` and a proven bound on `x`, or with `hi(x) < 2^(63-k)`.

When proven, emit the plain operator (mode `wrap` already exists and emits
`((int64_t)((uint64_t)(a) OP (uint64_t)(b)))`, which is defined for unsigned wrap); otherwise
emit `ck_*` exactly as today. For `ail_bytes_to_int`, the runtime can prove the accumulator bound
from the loop's digit count and skip the per-digit `(limit - d) / 10` test, keeping a single final
check — this is the `ticket_audit_noovf_int` edit, and it belongs in `cruntime.py`, guarded by the
existing `int()` digit-length check.

Correctness rests on the soundness of `local_int_bounds`, not on testing: a wrong proof would
silently drop an `OverflowError`. Therefore the pass must be conservative (unknown ⇒ checked) and
the test must include the exact boundaries: `INT64_MAX + 1`, `INT64_MIN - 1`, `INT64_MAX * 2`,
`INT64_MIN * -1`, a shift that overflows only for one input, values reaching the operation through
an argument, a list item, an attribute and a dict value, and a loop accumulator that provably
stays small.

### exe bytes

Allowed to change. Direction: fewer `ck_*` helpers selected in a program that needs none, so the
runtime selection shrinks (each helper is a handful of lines and they are emitted once per
program, not per call). Programs that still need the checks emit exactly today's C.

### Implementation steps (each ≤2 h)

| # | step | files | test |
|---:|---|---|---|
| 3.1 | Add `_bounds_no_overflow(op, lo_a, hi_a, lo_b, hi_b)` to the IR package and unit-test it on the boundary table (including overflow of the bounds computation itself). | `AIL_CURRENT/python/pkg-v12/ir/lower.py` (near the `local_int_bounds` use at line 394) | `AIL_CURRENT/test_ail_ck_bounds.py` |
| 3.2 | Use it when assigning `mode` for `add/sub/mul`; emit plain ops when proven, `ck_*` otherwise. | `AIL_CURRENT/python/pkg-v12/ir/lower.py`, `AIL_CURRENT/python/pkg-v12/ir/emit_c.py` (line 961) | same module + `test_ail_overflow.py` |
| 3.3 | `ail_bytes_to_int`: hoist the per-digit limit test to one final check (with a documented digit-count guard). | `AIL_CURRENT/python/pkg-v12/cruntime.py` (`ail_bytes_to_int`, line 6015) | `test_ail_ck_bounds.py` (int() boundary: 19 digits, `-2^63`, `2^63`, leading zeros, `_`, sign only) |
| 3.4 | Measure `lab/emit/bounds.py --only ledger_bin_noovf,ticket_audit_noovf_int` equivalent on the new build; icount all ten compare programs. | `lab/emit/` | required modules + report |

## Not in this split, and why

* **Container invariant / list helpers (rank 4/5, ≈2.3e9 combined).** The measured edit is a
  *semantic* question: `ail_blist_meta` checks memory-safety invariants on data that comes from
  outside. Dropping it needs an escape/ownership proof that the payload is a trusted local, which
  is a larger analysis than this step. The safe sub-step — hoist the check to list creation and
  resize and keep it out of read-only views — is worth about 0.54e9 (`ticket_audit_noview`) and is
  a natural follow-up once design 1's "local, non-escaping" marker exists (it is the same proof).
* **ASCII/UTF-8 classification (rank 7, 490M).** `ail_stdin_readline` scans every line to choose
  the ASCII fast path. The C does not because it assumes ASCII. AIL must not assume it; the
  correct change is one classification pass per buffer, not per line, which is a runtime change
  with no measured bound yet.
* **The expression shape (17.6e9 attributed).** Larger than 1–3 combined but no local edit bounds
  it; it is the EMIT_SHAPE lane.

## Ready-to-queue task text

### Task A — `emit-lean1`: lean int-dict probe on the typed path

```
Lane: compiler. Measured bound: 1,927M Ir on echo_pack (lab/emit/RESULTS.md, cause 1).

Add a no-tombstone int-key probe and select it for dicts the IR marks fast.
1. cruntime.py: add ail_hprobe(keys, mask, k) and ail_idict_{need,has,get,put}_fast; keep every
   existing ail_idict_* function unchanged. Test: new AIL_CURRENT/test_ail_idict_fast.py.
2. ir/lower.py: mark a local dict fast when it is never passed to a call, never del'd, never
   iterated while inserted into, and all access is has/need/get/put with int keys; store the mark
   on dict.alloc. Test: the same module's control cases (passed/iterated/deleted dicts keep the
   old C, byte-identical to base).
3. ir/emit_c.py:dict_op (line 1693): emit the _fast names when marked, the current names otherwise.
4. Prove: bash .agent/cmp.sh on every corpus program (both builds); test_ail_idict_fast,
   test_ail_safetynet, test_ail_files, test_ail_corpus_findings3; icount of all ten typed compare
   programs shows no regression and echo_pack drops.
Exe bytes may change. Do not change any message or refusal.
```

### Task B — `emit-lean2`: recursion guard at the recursive edge

```
Lane: compiler. Measured bound: 1,184M Ir on tally_lang (lab/emit/RESULTS.md, cause 2).

Move the depth guard from every function entry to the self-call sites that can grow depth.
1. ir/emit_c.py:_depth_call (line 675): wrap the self-call with
   (ail_d + 1 > AIL_MAX_RECURSION_DEPTH ? (ail_die("maximum recursion depth exceeded"), 0) : ...).
   Keep the entry guard at this step (both checks).
2. ir/emit_c.py:emit (line 763) + ir/lower.py: drop the entry guard only when every non-self
   caller passes the literal 0; keep it otherwise. Test: new AIL_CURRENT/test_ail_recdepth_edge.py
   (depth LIMIT completes, LIMIT+1 stops with the same message as the base build).
3. Prove: test_ail_recdepth_edge, test_ail_recursion_stop, test_ail_safetynet, test_ail_files,
   test_ail_corpus_findings3; cmp.sh on the corpus; icount of all ten typed compare programs shows
   no regression.
Exe bytes may change. The rejection boundary must be identical to the base build.
```

### Task C — `emit-lean3`: overflow checks only where overflow is possible

```
Lane: compiler. Measured bound: 1,012M Ir (ledger_bin 849M + ticket_audit 164M;
lab/emit/RESULTS.md, cause 3).

Use the existing int64 bounds pass to emit plain add/sub/mul where the result cannot overflow.
1. ir/lower.py: add _bounds_no_overflow (interval arithmetic for + - * and constant shifts) with
   unit tests over INT64_MIN/MAX boundaries. Test: new AIL_CURRENT/test_ail_ck_bounds.py.
2. ir/lower.py + ir/emit_c.py:961: choose mode 'wrap' when proven, 'ck' otherwise (unknown =>
   checked).
3. cruntime.py:ail_bytes_to_int (line 6015): hoist the per-digit limit test to one final check,
   keeping a digit-count guard. Test: int() boundary cases (19 digits, +/-2^63, leading zeros,
   underscores, sign only).
4. Prove: test_ail_ck_bounds, test_ail_overflow, test_ail_safetynet, test_ail_files,
   test_ail_corpus_findings3; cmp.sh on the corpus (an overflow that must still raise is the
   critical case); icount of all ten typed compare programs shows no regression.
Exe bytes may change. A dropped check must be provably unreachable.
```
