# Ready-to-queue tasks (each is an implementation step of 2 hours or less)

Each task follows the measured ranking in `RESULTS.md`. Each has its own guard test, and each is
safe to land on its own; the numbers quoted are the hand-edit measurements, not projections.

---

## T1. Sort an index list in place over the object's own columns (tree_fold sort)

**Files:** `AIL_CURRENT/` sort lowering (`ail_keysort_perm` / `ail_perm_apply` emission, the
`list.sort` / `sorted(key=)` path). No runtime change.

**What:** when the key is a tuple of plain column reads (`obj.f_a[i]`, `obj.f_b[i]`,
`obj.f_c[i]`, `i`) and the sorted value is the local `range(n)` list, emit an in-place sort of that
index list with a comparator that reads the columns directly. Do not build the key columns, the
`ail_slist` of `ail_str` views, the permutation array or the merge buffer, and do not call
`ail_perm_apply`.

**Measured:** tree_fold −41.43M LLC (59.5% of its 69.6M excess), −88.5 ms wall (8.0%),
−34.7 MiB RSS, −39.4 KiB executable.

**Safety (docs/spec/DIFFERENCES.md):** key is a pure read of columns not mutated by the sort; the
index list is the fresh local `range(n)`, not aliased (C2 alias refusal makes this checkable); the
comparator is a total order with the index as the final tie-break, matching the emitted stable
keysort; columns stay alive until after the sort.

**Guard test — `test_ail_layout_sort`:** sort `(par, -sub, name)` tuples with duplicate keys and
check the order equals CPython (stability and index tie-break), on empty, one-element, all-equal
and deep trees; sort a list whose keys are read through a parameter, a list item, an attribute and
a dict value; include a key that is *not* a plain column read (a call) and assert it still takes
the old path. Run on both builds. Also keep the boundary cases
`boundary/sort-single`, `boundary/sort-none`, `boundary/all-equal-sub` from
`lab/layout/probe.py` in the test.

**Time:** ~2 h.

---

## T2. Single-key sorts: drop the key-column copy and permutation

**Files:** `AIL_CURRENT/` sort lowering, single-key path only.

**What:** for `ord.sort(key=lambda i: keys[i])` where `keys` is a read-only list, emit an in-place
merge sort of the index list that compares `keys[src[i]]` directly. Remove the copy of the key
column, the permutation array and the `perm_apply` pass; keep the emitted merge order and the
index tie-break.

**Measured:** berth_sim −4.39M LLC (7.7% of its 56.7M excess), −4.6 ms wall, −22.4 MiB RSS,
−18.9 KiB executable. Explicitly **not** enough to close berth's gap: the remaining sort cost
(44.2M) is the random read of the key column, which needs key+index packing (a separate change
with a width range proof) and is not part of this task.

**Safety:** one key column, read-only during the sort; index list is the local `range(n)`, not
aliased (C2); ties break on the index exactly as the emitted stable sort does; keys compare
without side effects. Same escape conditions as T1.

**Guard test — `test_ail_layout_keysort`:** single-key sorts with all-equal keys, descending keys,
one element, empty; keys reached through an argument, a list item, an attribute and a dict value;
an aliased index list (must be refused by name or take the old path); the ordered result of
`lab/compare/src/berth_sim/main.py` on `boundary/all-same-keys` (valid `S=3` header) and
`boundary/two-ships-same-arrival`. Both builds.

**Time:** ~1.5 h.

---

## T3. Remove the redundant `[-1] * n` fill when every element is overwritten

**Files:** `AIL_CURRENT/` list-comprehension lowering (`[x for _ in range(n)]` whose result is a
fresh local and every index is stored before it is read).

**What:** skip the per-element fill when the comprehension result is a fresh local, nothing reads
it between construction and the first store, and every element is written before it is read. Keep
the int64 element type; combine with T4 only if its range proof lands.

**Measured:** echo_pack −3.92M LLC (50.2% of its 7.82M excess), −10.4 MiB RSS; wall time is
unchanged within the 5-run spread, so this is a memory/energy change, not a speed claim.

**Safety:** local escape/mutation proof — the list does not escape the block, no call between the
comprehension and the first store can read it, and the store index covers `0..n-1`; C2's
copy-on-store does not apply because the list is not stored. Also fuse `k in d` followed by
`d[k]` on the miss path only when the dict is not mutated between the two operations.

**Guard test — `test_ail_layout_fill`:** comprehension result read before the store, a slice of
`n` (not all indices written), an aliased/escaped list, `n = 0`, and the `has`/`need` fusion with
a dict mutated between the probe and the lookup; each must either match CPython or take the old
path. Both builds.

**Time:** ~1.5 h.

---

## T4. (Conditional) int32 element width for a list used only as checked indices

**Files:** `AIL_CURRENT/` list type inference, only with a range proof.

**What:** store a `list[int]` in int32 when every element is a value in `[-1, 2**31)` proved at
the store sites (e.g. positions into a buffer of known length) and every read goes through the
checked accessor. Otherwise keep int64.

**Measured:** echo_pack `prev32` −4.15M LLC (53.1% of its excess), −124.9 MiB RSS, −5.8 KiB
executable. Wall time is not improved (1.3% slower in best-of-5), so this is an RSS/traffic
change only.

**Safety:** requires the range proof above; without it the change is the alias/escape hazard of
narrowing (a negative or ≥2**31 value must be refused by name, not truncated). Keep the bounds
check on every read.

**Guard test — `test_ail_layout_width`:** values at `-1`, `0`, `2**31-1`, `2**31` and `-2**31`
through a parameter, a list item, an attribute and a dict value; negative and very large indices;
an empty list; assert the `2**31` boundary falls back to int64 or is refused by name. Both builds.

**Time:** ~2 h. Queue only after T3 (they overlap on the same array and are not additive).
