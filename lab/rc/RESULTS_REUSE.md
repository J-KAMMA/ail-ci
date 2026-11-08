# rc4: Perceus reuse — pairs found, and what the rule reaches

Branch `job-rc4-11081105`, base `origin/integ` (rc2 and rc3 merged). rc1's `PRICE.md` says **go,
marginal and RSS-only** for rc4 and **no** for tree_fold ("rc4/rc5 do not move tree_fold"). This
report is written against that verdict, not against it.

## Verdict up front

**The rule as specified finds zero pairs in every program it was pointed at.** The six programs
named by the brief (rbtree, cfold, deriv, binarytrees, linkedlist, objscan) and the ten compare
tasks (including `tree_fold` `typed.py`) all emit **zero** `ail_obj_reuse` sites. So the measured
number this moves is **0% instructions and 0% peak RSS on all 16**, and **tree_fold is not touched
at all** — which is what rc1 predicted ("rc4/rc5 touch 22.9 MiB, 5.5% of tracked peak, below the
10% bar: rc4/rc5 do not move tree_fold").

That is a null result on the headline number. The machinery is real and correct where it fires
(pinned by `test_ail_rc_reuse.py`), and every program it does not fire on is **byte-identical** to
the `AIL_RC_REUSE=0` build, so there is nothing to regress.

## Why zero: the two independent reasons

### 1. rc1's "reuse pairs" are not class instances

rc1 priced rc4 on "a `free` immediately followed by a same-size `malloc` in the same function".
Those pairs are almost entirely **string objects**, not class instances:

| program | rc1 reuse pairs | the call site rc1 measured |
|---|---:|---|
| term_rank | 9,352,966 | `ail_str_from_int` (reuse 978,973), `ail__bl_append_slow` |
| tree_fold | 1,110,756 | `ail__bl_append_slow` (reuse 79,730 / 52,044 / 5,978,973), `ail_str_from_int` |
| ticket_audit | 293,721 | `ail__bl_append_slow`, `ail__bl_take` |
| berth_sim | 1,185 | `ail__blk_take`, `ail_list_reserve` |
| rail_transfer | 140 | `ail_list_reserve` |
| tally_lang | 10 | `ail_list_reserve` |
| binarytrees, cfold, deriv, linkedlist, objscan, rbtree | **0** | — (rc1's own table) |

The brief's rule is about "an object of class C". A string is not a class instance on this path,
and the brief explicitly forbids stretching the rule. So the population rc1 measured is out of
scope by construction, and the population the brief targets is empty.

### 2. The class-instance programs have no rebind pairs at all

The rule needs an old instance released and a same-size one created on every path afterwards in the
same function. The natural source is `p = Cls(...)` executed twice on one local. An AST scan of
every source in scope (`lab/rc/progs/*.py`, `lab/compare/src/*/typed.py`, `lab/compare/src/*/main.py`)
finds **no** local that is assigned two class constructions in one function:

- rbtree, cfold, deriv, binarytrees, linkedlist, objscan: 0.
- term_rank `typed.py` (`class St`), ticket_audit `typed.py` (`class State`), tree_fold `typed.py`
  (`class T`), berth_sim (`class Fr`), rail_transfer (`class Item`), scar_life (`class Rule`),
  tally_lang (`class Prog`, `class Lx`): 0.

Every one of these constructs its instances once, in `__init__`-driven `build`/`make` helpers that
return a new node, and never rebinds a local to a second construction. The recursion allocates a
fresh node and hands it to the caller; there is no first object to release at the second
allocation, so there is no pair.

Confirmed by codegen, not only by the scan: all six programs emit `reuse=0` with
`--debug-dir`, and on/off `program.c` are **byte-identical**:

```
binarytrees identical   cfold identical   deriv identical
linkedlist identical    objscan identical rbtree identical
```

### 3. The class functions do not even take the IR path

Independent of the above: every class-using function in these programs falls back to the legacy
emitter (`AIL_IR_STATS`), with reasons like "the result has kind ('obj', 'Node')", "parameter 'n'
may be None", "local 'root' may be None". Only `main2`/`run` takes the IR. The IR-side
`obj.init` hook can therefore never be reached for a class instance in these programs, whatever the
analysis decides. This is measured, not assumed:

```
rbtree:  is_red/rotate_left/rotate_right/insert/walk/main -> legacy, main2 -> ir
deriv:   leaf/build/deriv/size/checksum/main             -> legacy, main2 -> ir
cfold:   leaf/build/fold/py_eval/size/checksum/main      -> legacy, main2 -> ir
```

## Pairs found, program by program (step 1's list)

Observed `ail_obj_reuse` sites in the emitted `program.c` (`--debug-dir`), default build:

| # | program | class-instance pairs | reuse sites |
|---:|---|---:|---:|
| 1 | rbtree | 0 | 0 |
| 2 | cfold | 0 | 0 |
| 3 | deriv | 0 | 0 |
| 4 | binarytrees | 0 | 0 |
| 5 | linkedlist | 0 | 0 |
| 6 | objscan | 0 | 0 |
| 7 | berth_sim `typed.py` | 0 | 0 |
| 8 | chain_relax `typed.py` | 0 | 0 |
| 9 | echo_pack `typed.py` | 0 | 0 |
| 10 | ledger_bin `typed.py` | 0 | 0 |
| 11 | rail_transfer `typed.py` | 0 | 0 |
| 12 | scar_life `typed.py` | 0 | 0 |
| 13 | tally_lang `typed.py` | 0 | 0 |
| 14 | term_rank `typed.py` | 0 | 0 |
| 15 | ticket_audit `typed.py` | 0 | 0 |
| 16 | tree_fold `typed.py` | 0 | 0 |

The brief counts "the 10 compare tasks" as the ten `typed.py` files (rows 7-16); `tree_fold`
`main.py` is CPython, not AIL, so it has no emitted C to inspect.

## Pairs found where the rule does fire

A hand-written probe (a loop rebind and a straight rebind) does produce pairs, and those are the
shapes the machinery is pinned on:

| probe shape | `ail_obj_reuse` sites |
|---|---:|
| `b = Box(0)` then `for ...: b = Box(i)` | 2 (helper + 1 call) |
| `b = Box(0)` then `b = Box(1)` | 2 |
| `b = Box(0)` then `b = Box(make())` (across a call) | 0 — refused |
| `p = Box(1); q = p; p = Box(2)` (old still named) | 0 — refused |
| class with `__del__` | 0 — refused |
| `b = Box(1); h = Holder(b); b = Box(2)` (escaped into a field) | 0 — refused |
| `d["k"] = b; b = Box(2)` (escaped into a dict) | 0 — refused |
| `xs.append(b); b = Box(2)` (escaped into a list) | 0 — refused |
| different sizes (`Small` then `Big`) | 0 — refused (different class, general path) |

## Hand-checked pairs (the brief asks for 3)

1. **Loop rebind, reused.** `reuse_loop.py`. Emitted:
   `ail_obj_reuse(v_b, sizeof(ail_obj_Box)); v_b = 0; ail_obj_store_Box(&v_b, ail_new_Box(i), 1);`
   The old `v_b` is nulled *before* the constructor runs, so if `ail_new_Box` is entered the slot no
   longer names the parked cell; the constructor's `ail_obj_new` takes the parked storage back when
   the size matches. `rc == 1` is the guard, so a second reference keeps the old object alive and
   the fast path is skipped.
2. **Straight rebind, reused.** Same shape without the loop; `out = 1` matches CPython.
3. **Escaped through a field, refused.** `reuse_attr.py`. `h = Holder(b)` stores `b` into
   `h.f_b`; the analysis sees the value escape (`obj.copyref`/`field.set` on a tainted place) and
   emits nothing, so `h.b.v` stays `1` while `b.v` is `2`. Both printed, matched CPython.

## Refused shapes, one per required category

- **Across a call:** `b = Box(make())` — the constructor argument depends on a call, and a nested
  allocation would consume the parked storage before the outer constructor takes it. Refused. Also
  refused: a function containing any `try` (a release and an allocation must not cross an unwind
  frame, which could release the reused cell twice).
- **A class with `__del__`:** never reused. Note this is enforced upstream of the emitter: a class
  with any dunder beyond `__init__` is built on the general path ("built on the general path ...
  because dunder method Box.__del__"), so it cannot reach the IR `obj.init` hook at all. The
  analysis also carries an explicit `attrs['finalised']` guard for the case where one does.
- **The old object still named:** `q = p; p = Box(2)` — `rc` on the old object is 2, so the fast
  path is not taken; the analysis refuses at compile time so the branch is not even emitted.

## What changed in code

- `AIL_CURRENT/python/pkg-v12/ir/reuse.py` (new): the analysis (marking) and the switch.
- `AIL_CURRENT/python/pkg-v12/ir/emit_c.py`: the `obj.init` emit hook (4 lines of body) and the
  `Emitter.__init__` mark call (2 lines).
- `AIL_CURRENT/python/pkg-v12/pyfunc.py`: the prelude hook that adds `ail_obj_reuse` (about 25
  lines, emitted only when the program has a pair) and the reset of the per-program state.
- `AIL_CURRENT/test_ail_rc_reuse.py`, `AIL_CURRENT/tests.d/test_ail_rc_reuse.txt` (new).

`AIL_RC_REUSE=0` turns it off and is the A/B switch.

## Verification run

- 16 programs (6 `lab/rc/progs` + 10 `lab/compare/src`): all build, all match CPython, both the
  default and `AIL_UNIFIED_FORCE=1` builds.
- On/off (`AIL_RC_REUSE=0`) `program.c` **byte-identical** for all six class programs, so the
  default build cannot regress on them.
- valgrind on rbtree and cfold: **not run** — this runner has no `valgrind` (`which valgrind` is
  empty). Stated rather than claimed.
- Probes: 9 files under `/tmp/probes`, run through `~/tools/cmp.sh` (both build modes). All 9
  match CPython in both modes:

| probe | mode g (unified) | mode d (default) |
|---|---|---|
| reuse_loop.py | same | same |
| reuse_arg.py | same | same |
| reuse_attr.py | same | same |
| reuse_dict.py | same | same |
| reuse_list.py | same | same |
| reuse_del.py | same | same |
| reuse_negative.py | same | same |
| reuse_empty.py | same | same |
| diffsize.py | same | same |

## Honest note on the target

The brief asks for "rc1's halved projection for rc4 (at least 1.03x instructions or 5% lower peak
RSS on 2 programs)". **Not met, and not reachable by this rule**: the rule finds nothing to reuse in
those programs, and rc1's own halved rc4 projection was 1.007x instructions at best with RSS gains
only where string/list-buffer churn dominates. Reporting the number honestly: **0 pairs reused on
the 16 target programs, 0% change in instructions and peak RSS, tree_fold untouched.**

The measured instruction and RSS deltas were therefore not re-measured program by program: the
generated C is byte-identical with the feature on and off, so any difference would be measurement
noise, not the feature. Claiming a number there would be claiming a change that does not exist.
