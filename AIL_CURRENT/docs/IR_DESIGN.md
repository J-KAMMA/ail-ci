# An ownership-aware IR for AIL: design and migration plan

Status: design only. Nothing here is implemented. Written 2026-10-12 against branch `utf8-str`,
HEAD 17477fd. All numbers are user-space instruction counts from `tools/icount.c`. Wall time on
the development machine varies up to 3x, so it is not used anywhere in this document.

## 0. Premise and the price

The premise comes from the last ~15 commits (b424153 .. 17477fd). Each commit added one
ownership special case to `python/pkg-v12/pyfunc.py`:

- `_scan_borrowed_params` / `_BORROWED_PARAMS` and the staging rule in `_call_user_func`
- `_borrowable_owner` and its users (`_attr_assign_inner`, `ail_obj_field_str_append`,
  `_map_key(borrow=True)`, `_map_read_pointer`)
- `_map_upsert` and `_stab_add_plan`
- the `_bytearray_method` append path, `byte0_names`, and the keep_roots skip.

Each one is correct only for the AST shape it matches. Together they cut csv_sum-ail-1 from
3.85 G to 2.50 G. The goal here is to replace them with one general analysis over an IR that
makes ownership explicit.

Before building anything, we priced the work (rule: `speed-claims`). For two LLM-written
programs, we hand-wrote the C that an ideal ownership-aware backend would emit for the *same*
AIL program. The algorithm, the runtime prelude and all AIL semantics stay the same: UTF-8
code-point strings, the overflow checks the program spells, ValueError/OSError exit paths, and
refcounts where an object is shared. Each version produces output identical to `expected.out`
and passes every hidden, example and perf case: word_top 24/24, csv_sum 30/30. Each is also
clean under ASan + UBSan + LeakSanitizer on all of those cases. The files are in
`~/scratch/ir/` (`wt_main_ideal.c`, `cs_ideal_body.c`, and the build scripts `build_wt.sh`,
`build_cs.sh`, `abl_wt.sh`, `abl_cs.sh`).

| program          | current AIL | ideal backend, same runtime | C      | Rust   |
|------------------|-------------|-----------------------------|--------|--------|
| word_top-ail-1   | 1.27 G      | **0.51 G** (2.5x less)      | 0.24 G | 0.55 G |
| csv_sum-ail-1    | 2.50 G      | **0.80 G** (3.1x less)      | 0.34 G | 1.18 G |

Peak RSS did not change: word_top 13.2 MB, csv_sum 21.7 MB. The binaries got smaller: word_top
43.7 KB to 31.1 KB, csv_sum 49.1 KB to 36.1 KB.

### Where the difference comes from, measured by ablation

**word_top** (1.27 G to 0.51 G). Each step below was measured cumulatively, starting from the
generated C:

| mechanism                                                                    | cost     |
|------------------------------------------------------------------------------|----------|
| `volatile` frame-cell locals, forced on the whole of `main` by one `try` around the file read | 0.089 G |
| `ail_sarena_keep_roots` per character                                        | 0.055 G  |
| `len(w) > 0` computed as a code-point count instead of `w.n > 0`             | 0.054 G  |
| per-character view construction (`ail_str_index_nc`, `ail_str_next_unit` through cells), checked `chr(ord(c)+32)` | 0.15 G |
| **`w += c` on an arena str (`ail_str_cat` adjacency and top-slot paths, `ail_str_from_cp`) instead of a uniquely owned growable buffer** | **0.41 G** |

The remaining 0.51 G is mostly runtime, and an IR does not touch it. About half the samples are
in the `ail_stab` dict: `ail_str_eq` and its `memcmp`, `ail_stab_free_slot`, `ail_shash`, and
`ail_stab_check`. `ail_stab_check` alone is 0.074 G (removing it gives 0.436 G). The rest is
UTF-8 validation plus the copy in `ail_utf8_decode_error`.

**csv_sum** (2.50 G to 0.80 G). Each mechanism was put back into the ideal version one at a
time:

| mechanism put back                                                           | cost     |
|------------------------------------------------------------------------------|----------|
| `p.field += c` through `ail_obj_field_str_append`: a str field has no capacity, so `malloc_usable_size` runs on every append, and the buffer is lost on `p.field = ""` | **+0.73 G** |
| Copy semantics on str field assignment (`p.key = p.field` mallocs a copy and frees the old one; `p.x = ""` frees), instead of reusing the destination's capacity | **+0.48 G** |
| Both of the above together                                                   | +1.17 G  |
| `parse_int64_decimal(p.val)` copying the argument (`ail_str_return_owned` + `ail_str_adopt`) instead of borrowing it | +0.16 G |
| The callee's own arena, keep_roots per character, and cleanup frame          | +0.067 G |
| retain/release of `p.groups` and `Group` temporaries in `end_record`         | +0.089 G |
| The cleanup frame in `end_record`                                            | +0.005 G |
| All of the above together                                                    | 2.34 G   |

The remaining 0.17 G is the heap-allocated, refcounted `P` and its stores, plus calls that
were not inlined.

### What the price says

1. The bound is real: 2.5x and 3.1x less. In both programs the ideal backend uses fewer
   instructions than Rust.
2. **Refcounting and cleanup frames are a small part of it.** retain/release plus frames come
   to about 0.1 G of the 1.7 G csv gap (6%). Volatile cells are 0.09 G of the 0.76 G word_top
   gap.
3. **String ownership is most of it.** That means:
   - uniquely owned strings with a known capacity that are mutated in place
   - borrowed string arguments
   - no arena or roots for values that do not need them.

   This is 1.33 G of 1.7 G on csv_sum and 0.47 G of 0.76 G on word_top.
4. Of that, about 1.2 G on csv_sum does not need an IR at all. Str fields are already uniquely
   owned, because every field read copies (that is current AIL semantics). Giving str fields a
   capacity and reusing it on assignment is a representation change. On the reconstruction it
   takes 2.34 G to 1.13 G. The word_top accumulator is different: it is a local, and proving
   it unique needs alias and ownership analysis. That is where the IR pays.
5. Even the ideal versions stay 2.1x (word_top) and 2.4x (csv) above C. That gap is in the
   runtime (`ail_stab`, decode), not in code generation.

The plan below is therefore scoped to **string ownership first**. The other analyses come
after it, because they are worth less.

## 1. Where the IR sits

The current pipeline:

`ail_syntax.translate` turns AIL into Python text, then `pyc.to_c`, then
`pyfunc._to_c_once`. `_to_c_once` runs the whole-program scans (`_scan_module_consts`,
`_scan_borrowed_params`, kind propagation, the recursion call graph). Then, for each function,
`_one_function_numeric_impl` builds a `Ctx` (about 85 fields), emits the body with
`_stmts` / `_stmt` / `_stmt_inner` / `_expr` and helpers such as `_str_value`, `_for`,
`_call_user_func` and `_attr_assign_inner`, and assembles the frees and the cleanup frame. The
cleanup frame comes from the `owned`, `owned_objs`, `object_params`, `object_refs` lists,
`frame_cells_needed` and `frees`, near `object_params`.

The new pipeline adds one branch inside `_one_function_numeric_impl`. It runs after `ctx` is
fully built (`ctx.types`, `ctx.kind`, `ctx.locals`, classes, `ctx.freeable_objs`) and before
`body = _stmts(fn.body, ctx, 1)`:

```
if ir_enabled and ir.supported(fn, ctx):          # syntactic + kind check, no side effects
    try:
        body, frees, decls = ir.compile_function(fn, ctx, sigs, summaries)
    except ir.Unsupported:
        body = None                                # fall back, whole function
if body is None:
    body = _stmts(fn.body, ctx, 1)                 # existing path, unchanged
```

New code goes in `python/pkg-v12/ir/`:

| file             | contents                                    |
|------------------|---------------------------------------------|
| `ir.py`          | data types                                  |
| `lower.py`       | AST to IR                                   |
| `verify.py`      | ownership typestate checker                 |
| `passes/*.py`    | one module per pass in section 3            |
| `emit_c.py`      | IR to C                                     |
| `summaries.py`   | whole-program effect and escape summaries, computed once in `_to_c_once` next to `_scan_borrowed_params` |

New runtime pieces, such as an owned string with capacity, become ordinary `cruntime.py`
sections (`ORDER` / `SOURCE` / `REQUIRES`) selected through `ctx.parts`. The IR emitter marks
parts the same way the old emitter does.

### Coexistence rules

- **Granularity is the whole function.** Mixing the two emitters inside one function would make
  the IR's ownership state agree with the old emitter's implicit state (`ctx.pre`, staged
  temporaries, frame cells, `loop_reset`). That is exactly the brittleness we are removing. One
  later exception may be allowed: an opaque scalar expression. If `_expr` returns a scalar,
  touches no resource-typed subexpression, and leaves `ctx.pre` and the temporary set unchanged
  (checked by snapshot), the IR may embed its C text as an `opaque` instruction with borrowed
  operands.
- **The ABI does not change.** IR functions and old-path functions call each other, so an IR
  function keeps the old C signature exactly:
  - borrowed struct parameters per `_BORROWED_PARAMS`
  - str parameters as views
  - owned str/bytes returns per `owned_str_fns` / `owned_bytes_fns`
  - the `ail_cleanup_top` / `ail_exc_top` protocol.

  A different convention, for example passing an owned str with capacity, is allowed only for a
  function whose callers are all IR-compiled. That is milestone M5.
- **There is a flag.** `info['_experimental_ir']` defaults to False, like the existing
  `_experimental_*` flags read at the top of `_to_c_once`. Under it sits a per-function
  allowlist, so a regression can be bisected to one function. `native_report.json` already lists
  every function (`"mapped"`); add `"ir": true/false` so coverage is measurable.

### What stays identical

- Program behaviour: stdout bytes, exit code and stderr message stay identical in both modes.
  `ail_check.py` (513 tests) runs twice: flag off and flag on.
- Generated C with the flag off: byte-identical. The codegen pins in `tools/codegen_diff.py`
  (`PIN_SOURCES`) must not move while the IR is behind the flag.
- Generated C with the flag on: a separate pin set. A pin moves only in a commit whose
  `codegen_diff.py --pins` diff shows the intended change.
- The emitter is deterministic: no dict or set iteration order leaks into the output, and
  temporaries are numbered in program order.

## 2. The IR

### 2.1 Shape: structured SSA (regions + block arguments)

AIL control flow is structured: `if` / `elif` / `else`, `while`, `for`, `break`, `continue`,
`return`, `try` / `except` / `finally`, `raise`. So the IR keeps that structure as nested
regions, like MLIR `scf`, and uses SSA inside them:

- A `Func` has a body region.
- A region is a list of instructions. Some instructions (`if`, `loop`, `try`) own sub-regions.
- Every value is defined once. Loop-carried locals are region arguments (`loop` has
  `iter_args`, as in `scf.while`). `if` yields values. `break` and `continue` carry the current
  values of the loop-carried locals.
- Mutable memory is not SSA. Struct fields, list elements, dict entries and arena storage are
  **places**, accessed with explicit `load`, `borrow`, `store` and `append` instructions that
  carry effects.

Why this shape:

- SSA gives use-def chains and exact last uses. Today `_last_use_free_points` approximates last
  use by moving the point out to the outermost loop.
- Regions keep C emission structural. The C reads like today's, the `codegen_diff` diffs stay
  reviewable, and gcc sees the same loop shapes.
- A full CFG would need structure recovery for no gain, because AIL has no goto.
- Plain non-SSA three-address code was rejected: ownership transfer ("this value is consumed
  here") needs a single definition to attach to.

### 2.2 Types

| IR type             | today's kind            | C                                          |
|---------------------|-------------------------|--------------------------------------------|
| `i64`               | INT (checked)           | `int64_t` + `ck_*`                         |
| `f64`, `bool`       | FLT, bool               | `double`, `int64_t`                        |
| `str`               | STR                     | `ail_str {p, n, bytes}`                    |
| `ostr` (new)        | owned str with capacity | `ail_ostr {p, n, cap, bytes}` (runtime M0) |
| `bytes`             | BYTES                   | `ail_bytes`                                |
| `bytearray`         | BYTEARRAY (refcounted)  | existing                                   |
| `struct S`          | `('obj', S)`            | `ail_obj_S *` (refcounted), or a stack/inline struct after escape analysis |
| `list[i64]` / `list[str]` / `list[S]` | LIST / SLIST / olist | `ail_list` / `ail_slist` / `ail_olist *` |
| `dict[str,i64]` etc. | MAPS kinds (`sdict`, ...) | existing                                  |
| `exc`               | EXCEPTION               | `ail_exception *`                          |

The first IR subset (M1) covers `i64`, `bool`, `str`, `ostr`, `struct`, `list[str]`,
`list[S]`, `dict[str,i64]`, `exc`. That is what the LLM-written programs use.

### 2.3 Ownership states

Every SSA value of a resource type has exactly one state, and the verifier checks it:

- **`own`**: this value must be consumed exactly once on every path, exceptional paths
  included. Consumed means moved, stored with `consume`, released, or returned. For objects it
  is one refcount. For `ostr` and containers it is one unique heap buffer.
- **`own unique`**: `own`, plus no other reference to the same storage exists. Only a
  `unique` value, or a place holding one, may be mutated in place: `append`, an in-place
  `assign`, or reuse of its capacity.
- **`borrow(p)`**: valid while place or value `p` is live and not written. Never released. The
  verifier rejects a write to `p`, or a call whose summary may write `p`, while the borrow is
  live.
- **`view(A)`**: a `str`/`bytes` view whose storage belongs to arena `A`, or is immortal: a
  literal, or the decoded input text owned for the whole function. It is valid until
  `arena.release(A, …)` stops listing it as a root, or until the function returns.

Places carry their invariant from the type:

- A struct `str` field holds an `own unique` string. That is today's invariant: reads copy.
- A `dict[str, _]` owns its keys. It copies a key on first insert (`ail_stab_key_dup`), so a
  key operand is always `borrow`.
- A `list[S]` element holds one refcount.

### 2.4 Instructions (subset)

```
v = const i64 7 | const str "…"            literals are view(immortal)
v = add.ck a, b | sub.ck | mul.ck | neg.ck  checked; ck failure = ail_die (not a raise)
v = cmp.lt a, b | …
v = str.index_cp s, k     -> borrow(s)      code point at byte offset k
v = str.byte0 s, k        -> i64            first byte, the byte0_names fact
v = str.len_cp s | str.len_bytes s
v = str.copy s            -> own unique ostr      (Python copy semantics, explicit)
v = str.to_view s         -> view(A)               (copy into arena A)
v = str.cat a, b          -> own unique ostr
    str.append  place|v, s                         requires unique
    str.assign  place, s                           in place: capacity reuse when unique
    str.reset   place                              p = "" : length 0, keep capacity
v = obj.new S(args…)      -> own                   args: consume or copy per field
v = field.borrow o, f     -> borrow(o.f)
v = field.load o, f       -> i64 | f64             scalars
    field.store o, f, v, consume|copy
v = retain x -> own ;  release x ;  v = move x ;  drop x
v = list.get l, i -> borrow(l[i]) ;  list.push l, v (consume) ;  v = list.len l
v = dict.get d, k, dflt ; dict.put d, k, v ; v = dict.upsert d, k -> slot ; dict.add d, k, add, miss
v = call f(args…)                               per-param mode from summaries: borrow|own
    raise e (consume)                           may_raise
    arena.mark A -> m ; arena.release A, m, roots…
regions: if c {…} else {…} -> yields ; loop(iter_args) {…} ; try {…} except K {…} … finally {…}
```

Every instruction has an **effect**:

- `pure`
- `reads(places)` / `writes(places)`
- `allocates(arena)`
- `may_raise(kinds)`
- `dies`, for `ail_die` paths such as `ck_*` overflow and OOM. Unlike a raise, these never
  unwind and need no cleanup.

The `may_raise` sets come from the runtime catalogue. For example, `list.get` raises
IndexError, `dict.need` raises KeyError, `parse_int64_decimal` raises ValueError, and file and
decode helpers raise OSError and ValueError. For user calls the set comes from callee
summaries.

### 2.5 Exceptions and cleanup

Exceptions keep today's mechanism: setjmp/longjmp, `ail_exc_stack`, and a `ail_cleanup_frame`
chain. What changes is how much of it is emitted.

- At each `may_raise` instruction, the **cleanup set** is the set of `own` values and owned
  places that are live there. Liveness includes values a handler region reads.
- A function needs a cleanup frame only if some cleanup set is non-empty and the raise can
  propagate out of the function. If the raise is always caught inside the function, the
  handler's normal-path releases cover it. The frame's release list is the union of the
  cleanup sets, not every resource-typed local as today (`ail_unwind_end_record` releases 20
  slots).
- `volatile` (the setjmp rule) applies only to SSA values that are defined before a `try`,
  redefined inside its body, and live into a handler or after the `try` on the exceptional path.
  Today `ctx.exc_frame` puts every resource local of the function into a calloc'd volatile cell
  struct (`frame_cells_needed`). In word_top that turned the whole word loop into volatile loads
  (0.089 G) because of one `try` around the file read.
- `finally` lowers to a region duplicated on the normal, break/continue/return and exceptional
  exits. That matches `_finally_unwind` / `_finally_release_returns` today.
- `ail_handled_scope` (bare `raise` inside a handler) is emitted only when the handler contains
  a bare `raise` or calls a function whose summary may re-raise.

## 3. Passes

Each pass rewrites IR, and `verify.py` runs after every pass in tests. For each pass below:
what it does, what it replaces in `pyfunc.py`, why it is sound, and what it is worth on the two
programs.

### P1. Conservative lowering (`lower.py`)

Lowering emits every copy Python semantics needs and every retain the old path does:

- `str.copy` on each field read
- `retain` on each `list.get` of a struct
- a staged copy for every argument
- one cleanup frame with everything
- `arena.release` with all str locals as roots in every loop.

The result should run about as fast as the old path did before the special cases. It is the
correctness baseline: every later pass only removes or weakens instructions. Soundness comes
from the old path's rules, written as IR.

### P2. Effect summaries and borrow inference

For each function, compute:

- which parameter places it may write (`p.f`, `p.l[*]`, `p.d[*]`)
- whether it stores a parameter into the heap or returns it (escape)
- its `may_raise` set.

Summaries are iterated to a fixpoint over the call graph `_to_c_once` already builds.
Recursive SCCs are treated conservatively.

Then, for each `str.copy`, `retain` or staged argument, the source becomes a `borrow` if the
source place is not written during the result's live range. That covers direct stores and
calls whose summary writes it.

**Replaces:**
- `_scan_borrowed_params` / `_BORROWED_PARAMS` and the staging branch in `_call_user_func` (the
  `_borrowable_owner` test and the "a borrowed struct parameter does not retain itself" case)
- `_borrowable_owner` in `_attr_assign_inner` and `_map_key(borrow=True)`
- `_map_read_pointer` ("no call can run between taking the pointer and the lookup", which
  becomes the general effect rule)
- borrowed element fields (`test_ail_borrowed_element_fields`)
- the 17477fd and af9247a cases.

**Soundness:** a borrow is valid iff no write to its source happens while it is live. The
verifier checks this per path. Summaries over-approximate writes, so an unknown or external
callee writes everything. `opaque` expressions only read.

**Worth:** csv_sum `parse_int64_decimal(p.val)` is +0.16 to 0.20 G. Most of the retain traffic
is already gone today, thanks to the special cases.

### P3. Retain/release pair elimination

After P2, a `retain x` whose result is released on every path, with no possible release of the
source in between, is deleted. So is `ail_obj_store_*(&tmp, …)` chain plumbing. Example: the
six `ail_olist_store` and five Group retains per `end_record` call in csv_sum.

**Soundness:** the refcount is never observable, because AIL has no `sys.getrefcount` and drop
order affects no output. An object stays alive while any borrow of it lives, because its owning
place is not written (P2's invariant).

**Worth:** 0.089 G on csv_sum.

### P4. Last-use moves

A `str.copy v`, `retain v` or `copy` of a container, where `v` is `own` and dead afterwards on
every path, becomes `move v`. A `field.store … copy` of a last use becomes `consume`.

**Replaces:**
- `_last_use_free_points` / `_last_use_frees` (numeric-list frees)
- the move-on-last-use patches for maps (`move_map_last_use`)
- `ail_sdict_take` / `ail_sdict_replace` plumbing.

**Soundness:** SSA liveness is exact for values. A move is legal because nothing reads `v`
afterwards, and the verifier checks single consumption.

### P5. Unique ownership and in-place mutation (the large one)

Strings that can be uniquely owned get the `ostr` representation (capacity, in-place append):

- str locals that are only built by `+=`, assigned from copies or literals, and passed as
  borrows
- every struct str field.

`str.cat(place, s)` with `place` unique becomes `str.append` (amortized, no realloc probe).
`place = ""` becomes `str.reset`, which keeps the capacity. `place = other` becomes
`str.assign`, which copies into the existing capacity instead of malloc + free. A dict insert
borrows the `ostr` as an `ail_str` view.

**Replaces:**
- `ail_obj_field_str_append` and its `malloc_usable_size` probe (a5b70df)
- the inline in-place append and the sarena "top slot" machinery (`AIL_SARENA_TOPS`, 71b5b5e)
- the adjacency trick in `ail_str_cat` for accumulators (afac91c)
- the `_bytearray_method` append fast path. A bytearray is the same thing for bytes.

**Soundness:** `unique` is established at definition: `str.copy`, `str.cat` results and
`obj.new` fields are fresh. It is preserved by the verifier, which rejects any instruction
creating a second `own` or a stored alias of a unique value: an alias must be a `borrow`, and a
borrow blocks mutation while it is live. Field uniqueness is today's language invariant (field
reads copy), so for fields P5 needs no analysis, only the representation.

**Worth:** word_top 0.41 G (the `w` accumulator). csv_sum 1.17 G (field append plus field
assignment).

### P6. Arena roots and view lifetimes

A `str.to_view` allocation in arena `A` inside a loop is live across the back edge only if it
flows into a loop-carried region argument. `arena.release(A, mark, roots)` gets exactly those
values as roots. If no allocation in the body reaches a loop-carried value, the release is
dropped from the loop entirely. Owned `ostr` locals (P5) never live in the arena.

**Replaces:** the `_froots` lists and the `ctx.loop_reset` keep_roots prologue in `_for` and
`_stmts`, the keep_roots skip in 71b5b5e, and the per-call arena in leaf functions that
allocate nothing (`parse_int64_decimal`, `parse_col`).

**Soundness:** a view is only read while its SSA value is live, and a release keeps the blocks
of every live root. This is today's `ail__sarena_keep_roots_slow` contract, with the root set
computed instead of listed by hand.

**Worth:** word_top 0.055 G. csv_sum about 0.05 G, inside the 0.067 G callee figure.

### P7. Escape analysis for structs

An `obj.new S` whose result is never:
- stored into a heap place,
- returned,
- passed to a parameter whose summary escapes it,
- or captured by a lambda

becomes a stack struct (or SSA scalars, after field promotion) with no header or refcount. Its
owned fields are dropped at scope exit and listed in the cleanup set for raises.

**Replaces:** `_mark_freeable_objects` / `ctx.freeable_objs`, and part of
`_borrow_leaf_self`.

**Soundness:** no reference outlives the frame, because escape is over-approximated by the
summaries.

**Worth:** csv_sum's `P`, part of the 0.17 G residual. Small on these programs. It matters more
for programs that allocate a struct per record.

### P8. Cleanup-frame and volatile elision

This uses the cleanup sets from §2.5:
- No frame when every cleanup set is empty. That covers `end_field`, `parse_int64_decimal`
  after P6, and `parse_col`.
- A narrowed release list otherwise.
- `volatile` only on handler-live values.

**Replaces:** `frame_cells_needed`, `experimental_trim_borrowed_exc_base`,
`experimental_private_try_scalars`, and the "not owned and not owned_objs and not exc_frame …"
conditions around `_borrow_leaf_self`.

**Soundness:** an unwind releases exactly the values that are owned and live at the raise
point. Anything else is either already consumed or not yet defined. The setjmp rule only
concerns automatics modified between setjmp and longjmp and read afterwards, which is exactly
the handler-live set.

**Worth:** word_top 0.089 G (volatile). csv_sum 0.005 G (frames).

### P9. Dict and list access fusion

Value numbering on `(container value, key value)` with memory effects:
- `dict.get d,k` then `dict.put d,k,(that + c)` with no intervening write to `d` becomes
  `dict.add`
- `k in d` then `d[k]` becomes one probe (`dict.upsert`)
- repeated `list.get l,i` becomes one load.

**Replaces:** `_map_upsert`, `_stab_add_plan`, and the ce42b96 fusion. They are already
present, so the gain on these programs is zero. The point is to stop matching AST shapes.

**Soundness:** both lookups see the same dict state, because there is no write in between
(effects). Insertion-order semantics are unchanged: `upsert` inserts at the same point the
`put` would.

### P10. Value facts

Light range and fact propagation on SSA values:
- `len_cp(s) > 0` becomes `s.n > 0`
- `byte0` facts from `str.index_cp` (replaces `byte0_names`)
- `ck_add` elision on proven ranges (`ord(c)+32` with `c` in `[65,90]`)
- `ascii` flags.

**Worth:** word_top 0.054 G (`len_points`).

## 4. Verifier and test strategy

`verify.py` is an ownership typestate checker, run after every pass in all tests and in
`--debug-dir` builds. It checks:

- each `own` is consumed exactly once on every path, including each `may_raise` edge into
  handlers and out of the function
- no use after move
- borrows do not outlive their source, and their source is not written while they are live
- only `unique` places are mutated in place
- views are not used after the release of a mark they are not a root of.

The verifier is the safety argument for every pass: a pass may be clever, but its output must
verify. Pass bugs then show up at compile time in tests, not as heap corruption.

Testing has five parts.

1. **Dual compile.** Every `ail_check.py` test, every hidden and example case of the LLM
   programs, and the bench apps (`bench/compare.py`) run with the IR flag off and on. stdout,
   exit code and stderr must match. With the flag off, the C must match the previous commit
   byte for byte.
2. **Differential testing against Python.** AIL translates to Python, so CPython is the oracle.
   This extends the existing pattern (`test_ail_utf8_stream_fuzz.py`) with two generators:
   - A grammar-based generator of small programs inside the IR subset: structs with str, int
     and dict fields; `+=` on str locals and fields; `try`/`raise`; calls passing
     fields and elements; loops with `break` and `continue`.
   - Random inputs (UTF-8 including 4-byte sequences, CRLF, empty fields).

   Each program is checked as: CPython output equals IR binary output, which equals old-path
   binary output.
3. **Sanitizers.** ASan + UBSan + LeakSanitizer on the IR-mode build of everything in (1) and
   (2), including error exits. The leak check covers raise paths, as the hand-written prototype
   showed: its first version leaked the exception payload on `raise`.
4. **Benchmarks.** `tools/icount` on the six LLM programs (`private-runs/*-ail-*`) and the
   bench apps, plus peak RSS and binary size (the user's rule: judge on RSS and size too). An
   IR-mode count more than 1% above flag-off fails, unless the commit message names it.
5. **Pins.** The flag-off pins stay frozen. The flag-on pins follow the rule in §1.

## 5. Staged migration

Each milestone lands as one or more commits. Its gain is stated against the measured ablations
in §0 and must be re-measured on landing.

**M0. `ostr` str fields, without the IR.** Effort: 3 to 5 days.
- Change the representation of struct str fields to `ail_ostr {p, n, cap, bytes}`, in
  cruntime `OBJ` plus the field emitters in `_attr_assign_inner` / `ail_new_*`. Field append
  uses the capacity. Field assignment copies into the existing capacity. `= ""` resets the
  length.
- Sound without analysis, because field strings are already unique.
- Expected: csv_sum-ail-1 about 2.50 G to 1.3 G. The reconstruction measured 2.34 G to
  1.13 G, so the expected real gain is about 1.2 G. It also helps every LLM program that keeps
  a "current field" string in a struct, the struct-of-parser-state pattern that AIL_REFERENCE section 7 leads to.
- Exit: `ail_check` passes, the 148 hidden tests pass, icount and RSS are recorded.
- This is per-construct work. It is included because P5 needs the representation anyway, and
  it pays before any IR exists.

**M1. IR skeleton with conservative lowering, flag-gated.** Effort: 3 to 4 weeks.
- `ir.py`, `lower.py` (P1), `emit_c.py` and `verify.py` for the subset: `i64`, `bool`,
  `str` / `ostr`, structs, `list[str]`, `list[S]`, `dict[str,i64]`, `for c in s`,
  `while` / `for range`, `if`, `try` / `except` / `raise`, calls between subset functions,
  `print`, `sys.argv`, `read_bytes().decode()`, and `sorted(d.items(), key=…)` through the
  existing runtime calls.
- Per-function fallback, per §1.
- Target: every user function of word_top-ail-1/2 and csv_sum-ail-1/2 compiles through the IR.
  json_get may fall back.
- Exit: all hidden tests pass in IR mode; `ail_check` passes with the flag on; the verifier is
  clean.
- Performance is measured but does not gate. IR mode is expected to be slower than current
  here, because P1 is conservative.

**M2. P2 + P3 + P8 (borrows, pair elimination, frames and volatile).** Effort: 2 to 3 weeks.
- Exit: IR-mode instruction counts are at or below flag-off on all six LLM programs and the
  bench apps. That means the IR subsumes the special cases for subset functions.
- Expected gain beyond current, from §0: word_top about 0.09 G (volatile); csv_sum about
  0.25 G (borrowed argument plus callee frame and arena).

**M3. P4 + P5 + P6 (moves, unique in-place strings, arena roots).** Effort: 2 to 3 weeks.
- Expected: word_top 1.27 G to about 0.6 G (accumulator 0.41 G plus keep_roots 0.055 G);
  csv_sum to about 0.9 G (whatever M0 left).
- Exit: within 15% of the hand-written bound (0.51 G / 0.80 G). Sanitizer-clean on the fuzz
  corpus.

**M4. P7 + P9 + P10 (escape, fusion, facts).** Effort: 2 weeks.
- Expected: about 0.05 to 0.2 G per program. Small on these two programs.
- Exit: the hand-written bound is reached within 5%, or the remaining difference is explained
  by named mechanisms.

**M5. Delete special cases and widen the subset.** Ongoing.
- For every `pyfunc.py` special case whose functions are all IR-covered, delete it and keep the
  counts.
- Widen to bytes / bytearray (json_get), methods, lambdas, `list[i64]`, and other dict kinds.
- Allow IR-only calling conventions (owned `ostr` arguments and returns) between IR functions.
- Exit per case: the deletion changes no IR-mode count and no test result.

Total to M4: about 10 to 14 weeks of focused work. That is an estimate, not a measurement.

## 6. Risks, and what would make us stop

- **Most of the csv gain does not need an IR.** M0 alone is expected to take about 1.2 G of
  csv_sum's 1.7 G. If, after M0, the LLM programs are within about 25% of the hand-written
  bound, stop after M2. The IR's remaining value would then be maintainability (deleting the
  special cases), which has to be argued separately from speed.
- **The gap to C is the runtime.** The ideal versions still spend about half their
  instructions in `ail_stab` and in UTF-8 decode/copy. Examples: `ail_stab_check` on every
  probe (0.074 G); no stored hash, so equal-length keys always reach `memcmp`; separate
  `key` / `val` / `used` / `order` arrays. Closing the 2x to C is a dict and decode project.
  If beating C on these tasks is the goal, that project may come before M3.
- **Two emitters during migration.** Every language change during M1 to M5 has to land in both
  paths. Mitigation: freeze new syntax in the subset during M1 and M2. Stop if M2's exit
  criterion (IR at or below current) is not met within 2x its estimate.
- **Semantic drift.** Python copy semantics, evaluation order with side-effecting arguments
  (the reason for `_call_user_func` staging), exceptions mid-statement, and `finally`. The
  verifier plus three-way differential tests are the gate. Stop widening the subset if fuzzing
  keeps finding IR-only miscompiles at a rate that does not fall.
- **Compile time.** Summaries and fixpoints run over whole programs. Track `compile` time on
  the largest test programs. Budget: +20%.
- **The measured bound is for two programs.** json_get is algorithmic: it re-parses per query,
  so it was not priced. The bound says nothing about numeric or array programs, which pyfunc
  already compiles close to C. Re-price before widening M5 to them.

## 7. Reproducing the price

```
cd ~/scratch/ir
bash base.sh        # compile both programs with the current compiler, check output
bash build_wt.sh    # word_top ideal: output check + icount
bash build_cs.sh    # csv_sum ideal: output check, icount, all hidden/example/perf cases
bash abl_wt.sh      # word_top cumulative ablations (a1..a3) and the stab_check variant
bash wt2.sh         # word_top with an arena accumulator instead of an owned buffer
python3 mk_t.py && bash abl_cs.sh   # csv_sum single-mechanism toggles (-DR_*)
bash san.sh         # ASan/UBSan/LSan on both ideal programs, all cases
```
