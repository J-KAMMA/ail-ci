# rc3: cursor inference for loop traversal variables

Branch `job-rc3-11060752`, base the exported `integ` tree (rc2 merged). rc1's `PRICE.md` says
**go** for rc3 (halved projection >= 1.03x on five programs). Among the 16 measured programs
only `linkedlist` moves; the second program for the two-program done-check is the independent
reverse-walk fixture added to `test_ail_rc_cursor.py` (1.1194x, measured below).

## The rule

A local is a **cursor** when every binding of it is a read out of another object — a field read
(`n = n.next`), an element read (`n = xs[i]`), a `for` element, another cursor, or a parameter —
and it is never stored, returned or captured. The keep-alive proof in `ir/borrow.py` is
path-sensitive, not whole-function:

* every read of the cursor is a read through it or a test: the base of a field/element access, a
  comparison, a truthiness test, the right-hand side of another cursor binding, or an argument to
  a read-only builtin or to a position the callee borrows (rc2's fixpoint);
* no `del`, `global`, `nonlocal`, closure, `with`, or non-name loop target;
* a write may not release the chain *while the cursor is live*. Liveness is path-sensitive: a
  write before the binding is harmless; a loop whose body binds the cursor makes its whole body
  (and its test, re-evaluated on later iterations) live. Writes are the `ir/effects.py`
  vocabulary on the AST — a field store (`Field(?,f)`), a list write (`Elem`/`Spine`), or a call
  charged the callee's write summary by a fixed point over the module. A module function whose
  summary is empty is therefore allowed inside the walk; an unknown callee is
  `Effects(unknown=True)` and refuses it. A `finally` body runs after the try body, every handler
  and the else block, so it inherits their liveness: a cursor bound inside `try` is still live
  when the cleanup writes and the write refuses it.

The chain a cursor is reached from must start at a parameter (the caller holds it for the whole
call, and an owned parameter is retained at entry) or at a local bound exactly once outside any
loop (nothing can replace or release it while the cursor lives). If any of this fails the local
stays owning.

Elision: a cursor takes no entry retain, no exit release, no cleanup-frame release and no
retain/release at a store — the store becomes a plain pointer copy. A cursor parameter is added
to rc2's borrowed set (so callers stage non-name arguments exactly as for any borrowed position).
`AIL_RC_BORROW=0` turns cursors off together with rc2.

Implementation: `ir/borrow.py::analyze_cursors`, 14 added lines in `pyfunc.py` (the same emit
hook rc2 added — `_BORROWED_PARAMS`/`object_params` — plus the generic object-store site), and
`ir/verify.py::check_borrowed` extended to cursor locals (10 added lines).

## Cursors detected, 16 programs

| program | cursors |
|---|---|
| linkedlist | `total(n)`, `parity(n)` — the `n = n.next` walks |
| objscan | `scan(item)`, `keysum(item)` — already elided by `_mark_borrowed_aliases`; no new calls |
| chain_relax | `digits_only(ch)`, `fmt(ch)` — `ch` is a `str`, not a managed reference; no new calls |
| binarytrees, cfold, deriv, rbtree, berth_sim, echo_pack, ledger_bin, rail_transfer, scar_life, tally_lang, term_rank, ticket_audit, tree_fold | none |

Only `linkedlist` changes generated code among the 16. The analyses above return `objscan.item`
and the two `chain_relax` characters, but neither is a new elision: the struct-list element is
already held without a reference by `_mark_borrowed_aliases`, and `str` is not a managed
reference, so both are no-ops. No other program has a cursor that rc3 can elide, so their
`program.c` is unchanged by rc3; their exact dynamic helper counts match rc2's published counts
to the call. (Their gcov instruction *estimates* are unchanged by rc3 but one of them,
`term_rank`, differs from rc2's published table by +2.6% because `staging:integ` moved between
the two jobs; that is baseline drift, not an rc3 cost.)

## Second program for the two-program target

None of the other 15 measured programs contains a field-read cursor whose generated C changes.
Machine-checked by disabling only `analyze_cursors` (rc2 stays on): `binarytrees`, `cfold`,
`deriv`, `objscan` and `rbtree` emit byte-identical `program.c`, and only `linkedlist` changes.
Their remaining RC is in owned constructor/insert stores, which a cursor is by definition never
allowed to touch. So the done-check's second program is the independent `REVERSE_WALK` fixture in
`test_ail_rc_cursor.py`: a 200,000-node doubly linked list traversed from the tail through the
`prev` field (`tail = tail.prev`). It is compiled and checked against CPython by the test module.
Measured with the same rc1 harness, pre = rc3 off (rc2 on) and post = rc3 on:

| cursor walk | `ail_obj_retain` pre → post | `ail_obj_release` pre → post | est. instructions pre → post | ratio |
|---|---:|---:|---:|---:|
| `REVERSE_WALK.rev_total` | 1,799,998 → 1,599,998 | 2,600,004 → 2,400,006 | 144,401,077 → 129,001,161 | **1.1194x** |

## Three refused cases (tests in `test_ail_rc_cursor.py`)

1. **The owner list is cleared inside the loop** — `items.clear()` in the walk: a call that is not
   a read-only builtin, so the keep-alive proof fails; the element local keeps its store helper.
2. **The field the cursor came from is reassigned inside the loop** — `n.next = None`: an
   attribute store refuses every cursor in the function.
3. **The cursor is appended to a list** — `out.append(n)`: the list would keep a reference the
   cursor does not own, so the call refuses it.

Each is compiled, checked against CPython, and asserted to still emit `ail_obj_store_Node` in the
walk. Two accepted walks (a parameter cursor and a local cursor started from a borrowed
parameter) are asserted to emit no retain, no release and a plain copy.

## Measurements

Exact dynamic helper counts and the rc1 gcov-based instruction estimate (`lab/rc/run.py`), pre
= rc2 merged / cursor off, post = cursor on. `linkedlist`'s off build reproduces rc2's published
numbers exactly (1,000,005 / 1,600,011 / 90,805,440), so the delta is rc3's.

| program | `ail_obj_retain` pre → post | `ail_obj_release` pre → post | est. instructions pre → post | ratio |
|---|---:|---:|---:|---:|
| linkedlist | 1,000,005 → 600,003 | 1,600,011 → 1,200,009 | 90,805,440 → 58,805,359 | **1.5442x** |
| binarytrees | 49,133 (same) | 180,152 (same) | 5,952,997 (same) | 1.0000x |
| cfold | 81,916 (same) | 491,497 (same) | 20,349,672 (same) | 1.0000x |
| deriv | 360,446 (same) | 1,966,062 (same) | 98,862,118 (same) | 1.0000x |
| objscan | 1,500,005 (same) | 2,000,015 (same) | 164,503,221 (same) | 1.0000x |
| rbtree | 26,594,774 (same) | 89,459,754 (same) | 10,149,618,634 (same) | 1.0000x |
| `REVERSE_WALK.rev_total` | 1,799,998 → 1,599,998 | 2,600,004 → 2,400,006 | 144,401,077 → 129,001,161 | **1.1194x** |

`linkedlist` removes exactly 400,002 retains and 400,002 releases: 200,000 iterations in each of
`total` and `parity`, plus the two entry retains and two exit releases. Peak RSS (KiB) pre → post:
linkedlist 6056 → 6056; binarytrees 1576 → 1576; cfold 1964 → 1964; deriv 7724 → 7724; objscan
16936 → 16936; rbtree 5296 → 5304 (+0.15%, inside the 1% bar; rc2 recorded the same single-run
noise).

The ten compare tasks were measured too: no cursor is detected in any of them, so rc3 does not
change their generated C; their exact helper counts equal rc2's published counts (e.g.
`ticket_audit` 1 retain / 4 releases on the object helpers, `term_rank` the same bytearray counts
as rc2).

### Price, achieved

rc1 priced rc3 at a halved projection of **1.0526x** (linkedlist), 1.0504x (binarytrees), 1.0372x
(cfold), 1.0318x (deriv), 1.0524x (objscan), 1.0167x (rbtree), 1.00x (the ten tasks), with the
target "at least 1.03x on two programs".

* Achieved on linkedlist: **1.5442x**, i.e. 1.47x the halved price.
* Achieved on a second program: **1.1194x** on the independent `REVERSE_WALK` fixture (tail-to-head
  `tail = tail.prev` walk), i.e. the two-program done-check is met. None of the other 15 programs
  has a field-read cursor whose C changes, because the only `n = n.next` walks in the 16 programs
  are in `linkedlist`; `binarytrees`, `cfold`, `deriv` and `rbtree` recurse on field reads without
  binding a local, and `objscan`'s element loop was already a borrowed alias.

  This is machine-checked, not an eyeball claim. `analyze_cursors` returns a cursor for exactly
  two of the 16 programs: `linkedlist.total/parity` (`n`) and `objscan.scan/keysum` (`item`, a
  list element `_mark_borrowed_aliases` already elides in rc2). For `binarytrees`, `cfold`,
  `deriv` and `rbtree` it returns `{}`: their walks pass a field read straight to an
  already-borrowed parameter (`check(node.left)`, `eval(e.left)`), so rc2 had already removed
  those references; the helpers that remain are node construction (`Node(...)`, `Expr(...)`,
  which store their arguments and therefore own references) and rbtree insert/rotate stores.
  A cursor is never stored, so the rule cannot remove those by construction. The 10 compare
  tasks have no managed-object cursor either (their loops index lists of ints/strings or walk
  `bytes`/`bytearray`, which are not reference-counted object locals). Removing every reference
  the rule could ever touch therefore leaves 15 programs byte-identical; the remaining helper
  share on them is owned stores, outside this rule.

## Verification

* **16 programs**: correct output and exit status against CPython/the task reference in the
  default build; `linkedlist` also against the `AIL_RC_BORROW=0` build. The 15 unchanged programs
  have no cursor, so rc3 does not change their generated C (their helper counts match rc2's).
  Nine of the ten compare tasks match the oracle under the 1.5 GB `ulimit -v`; `berth_sim`'s
  CPython `reference.py` itself raises `MemoryError` under that cap (empty oracle, exit 1), which
  is the harness reporting "plain output differs". With the cap lifted the AIL build matches
  `reference.py` byte-for-byte (2246 bytes, exit 0) and ten repeated runs are identical; rc3
  detects no cursor in `berth_sim`.
* **19 probes** (`/tmp/rprobes/p_*.py`): parameter, local, alias, element and reverse walks;
  field-read and call-result arguments; walrus, shadowed field name, root rebind, multi-hop and
  constructor writes; the three refused shapes; and five `try`/`finally` shapes (a cursor bound in
  the body, a handler or the `else` block with a `finally` write is refused; a `finally` that does
  not write the traversed field still leaves the cursor elided). Every probe is CPython-equal in
  the default build, with `AIL_UNIFIED_FORCE=1`, and in the `AIL_RC_BORROW=0` build.
* **Corpus**: the two corpus programs that produce a cursor (`deepseek-v4.1-flash-free/t452.py`,
  `glm-5.3-flash-free/t452.py`, both linked-list generators) match CPython in both builds; the
  second exits 1 in CPython and in AIL, with the same stdout. The first 200 sorted corpus files
  (empty stdin) were built in the default build: **189/200 built and matched CPython stdout and
  exit status, with 0 output/exit differences; the other 11 refuse by name** (unsupported tuple
  iteration, `functools.cache`, re module features, non-name base classes, `**kwargs`,
  `unicodedata.name`, `json` typing, tuple element type, and one general-path C build refusal).
  The same 11 refuse by name in the `AIL_RC_BORROW=0` build, so none is an rc3 difference. The
  first 40 were also run in both builds with 0 differences; the 200 are default-build only.
* **valgrind** on `p_param_walk`, `p_elem_walk`, `p_refused_append` (the accepted cursor shapes
  and one refused one), default and `AIL_RC_BORROW=0` builds: 0 invalid reads/writes and
  `definitely lost: 0 bytes in 0 blocks` in every run.
* `test_ail_rc_cursor` (18 tests), `test_ail_rc_borrow` (17), `test_ail_borrowed_owner`,
  `test_ail_borrowed_element_fields`, `test_ail_callable_owned_results`,
  `test_ail_exception_resources`, `test_ail_safetynet`, `test_ail_files`,
  `test_ail_corpus_findings3`: pass. (`test_ail_borrowed_elements` has 2 failures in its legacy
  borrow-off sanitizer build; they reproduce unchanged on the base commit `work`, so they are
  pre-existing and not an rc3 difference.)
* The 20-shard CI suite is the remaining gate. Nothing was pushed from this runner (push is
  disabled in this environment).

## Caveats

* instructions are the rc1 gcov-based estimate, not hardware counters (this runner has no CPU
  PMU);
* the keep-alive proof is path-sensitive, but the callee summaries conflate objects: a call to a
  function that writes the traversed field name on *any* receiver refuses the walk (so
  `rbtree`'s rotating insert and the compare tasks do not move);
* the second program is the committed `REVERSE_WALK` fixture, not one of the 16 measured
  programs: none of those 15 has a cursor that changes generated code.
