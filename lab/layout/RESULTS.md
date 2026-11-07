# layout1: why AIL's typed builds miss cache more than C, and what a flat layout would save

Measurement and design only. No compiler, runtime, test or bench file was changed. The hand edits
in `edits/` rewrite a *copy* of the emitted C, outside the compiler.

Runner: GitHub Actions 4-core VM, gcc 12, valgrind 3.22 cachegrind with the geometry of
`lab/roof` and `lab/energy` (I1 32 KiB / D1 32 KiB 8-way, L2 512 KiB 8-way, LLC 32 MiB 16-way).
AIL is built with the compiler's own flags (`measure.py:AIL_CFLAGS`, `-O2 -g`, SLP disabled) and
`main.c` with `gcc -O2 -std=c11`. Wall time is best of 5 on the same runner. Every build's stdout
is compared byte for byte with the task's CPython reference; every hand edit is additionally run
through `probe.py` on the task's public, hidden and synthetic boundary cases.

## Answer

**The tree_fold keyed sort removes the most: sorting the index list in place over the tree's own
columns, with no key columns, permutation array, merge buffer or `perm_apply` copy, removes 41.4M
LLC misses — 46.3% of AIL's LLC total and 59.5% of AIL's 69.6M excess over C — plus 34.7 MiB RSS
and 39.4 KiB of executable, and takes 8.0% off wall time.** It is safe when the key is a pure read
of columns that the sort does not mutate, the index list is the freshly built `range(n)` and does
not alias (typed-path alias refusal, `docs/spec/DIFFERENCES.md` C2), and the comparator is a total
order with the index as the final tie-break. Under those conditions the in-place sort emits the
same order as the emitted keysort; all 25 probe cases (including equal keys, one element, no sort,
deep trees, and a maximum-weight node) are byte-identical to CPython.

No other measured edit is close. echo_pack's 256 MiB `prev` chain and berth_sim's sort auxiliary
arrays each recover 4–4.4M LLC misses (7.7–53% of their own excess) but do not improve wall time;
one echo_pack candidate (dict → flat head array) is *worse* by 0.59M LLC.

## Counters

`LLC` is `DLmr + DLmw`. `excess` is AIL − C. Ratios are AIL / C.

| task | build | instructions | D1 misses | LLC misses | LLC read | LLC write | wall best s | RSS KiB | exe B |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| tree_fold | AIL typed | 8,832,402,539 | 115,287,921 | 89,562,539 | 52,960,286 | 36,602,253 | 1.108 | 367,448 | 457,024 |
| tree_fold | C | 4,445,950,651 | 22,567,307 | 19,961,085 | 12,483,254 | 7,477,831 | 0.853 | 198,116 | 48,632 |
| berth_sim | AIL typed | 8,369,041,431 | 143,455,195 | 78,429,306 | 48,130,812 | 19,382,408 | 2.094 | 245,732 | 373,848 |
| berth_sim | C | 5,912,493,375 | 68,029,030 | 21,721,047 | — | — | 1.613 | 215,596 | 30,704 |
| ticket_audit | AIL typed | 13,061,870,398 | 40,757,534 | 10,690,017 | 5,602,589 | 1,566,991 | 1.534 | 254,820 | 565,728 |
| ticket_audit | C | 2,405,987,102 | 23,387,993 | 7,286,669 | 4,132,805 | 91,581 | 0.817 | 274,472 | 40,824 |
| echo_pack | AIL typed | 5,542,706,591 | 115,254,540 | 11,183,753 | 1,640,937 | 9,397,623 | 0.783 | 354,400 | 145,880 |
| echo_pack | C | 1,923,639,210 | 74,115,958 | 3,362,238 | — | — | 0.490 | 178,792 | 28,416 |
| ledger_bin | AIL typed | 5,234,920,618 | 55,754,932 | 14,445,828 | 4,184,920 | 3,201,369 | 0.687 | 340,604 | 313,200 |
| ledger_bin | C | 2,732,941,653 | 29,823,206 | 5,823,750 | — | — | 0.469 | 216,020 | 36,672 |

| task | Ir x C | LLC x C | D1 x C | wall x C | excess LLC |
|---|---:|---:|---:|---:|---:|
| tree_fold | 1.99 | 4.49 | 5.11 | 1.30 | 69,601,454 |
| berth_sim | 1.42 | 3.61 | 2.11 | 1.30 | 56,708,259 |
| ticket_audit | 5.43 | 1.47 | 1.74 | 1.88 | 3,403,348 |
| echo_pack | 2.88 | 3.33 | 1.56 | 1.60 | 7,821,515 |
| ledger_bin | 1.92 | 2.48 | 1.87 | 1.46 | 8,622,078 |

Five-program excess: 146.2M LLC misses.

### Note on the 106.1M in energy1

`lab/energy/RESULTS.md` (roof1) records tree_fold AIL as 9.053e9 instructions and 106.1M LLC
misses. The row here is 8.832e9 and 89.6M. The perf input is the same 27,877,476 bytes, and this
tree's C build reproduces roof1's C row (4.445951e9 vs 4.445951e9 Ir, 19.961M LLC, 0.01%), so the
input and the C side are unchanged. The AIL side differs because roof1 measured a binary emitted by
an older compiler; this branch (`b75efd2`, an export of `staging:integ`) emits 8.832e9 Ir. The
difference is emitted-code drift, not a measurement difference. All rankings below use the numbers
measured on this commit.

## Step 1: how each hot structure is laid out

Sizes are `sizeof` on x86-64 from the emitted `program.c` and `main.c`: `ail_obj_header` 8 B
(`uint32 refs; uint16 cls; uint16 drop`), `ail_list` 24 B (`int64* p; int64 n, cap`),
`ail_str` 24 B (`ptr, len, bool` padded), `ail_pslist` 80 B, `ail_hent` 16 B, `ail_sslot` 8 B.

### tree_fold

| | AIL typed | C (`lab/compare/src/tree_fold/main.c`) |
|---|---|---|
| tree object | one heap `ail_obj_T` of 160 B: 8 B header + 80 B `ail_pslist f_nm` + three 24 B `ail_list`s (`w`, `dep`, `par`) | no object; the tree *is* seven parallel `int`/`ll` arrays (`fst,lst,nxt,par,nlen,noff,wt`) plus one name arena `nb[]` |
| node | inline in the columns: 8 B name prefix per node + text, 8 B `w`, 8 B `dep`, 8 B `par` | 32 B/node across the arrays (5×int + 1×unsigned + 1×ll); name is `noff`+`nlen` into `nb`, **not** a 24 B `ail_str` per node |
| children | `f_dep` is an `ail_list` of parent indices; every traversal calls `ail_list_get` / `ail_pslist_at` through a checked accessor | `fst/lst/nxt` linked list, one pointer chase, no bounds check |
| sort temporaries | six n-element arrays live at once: `counts`, `sub`, an index copy, `idx`, two int64 key columns (`par` and `-sub`), plus an `ail_slist` of 24 B `ail_str` name views, a permutation array and a merge buffer; then `ail_perm_apply` copies the list through another buffer. Comparator walks a 32 B `ail_keycol` descriptor and dereferences three more arrays per comparison | `qsort` over one index array; the comparator reads `par[]`, `sub[]` and the name arena directly. One array, no permutation, no copy |
| refcounts / padding | header word on the one object; `ail_str` pads 8 B per name view | none; no per-node header |

Measured consequence: `do_sort` alone is 38.5M LLC (43% of AIL's 89.6M). The sort's key columns,
name views, permutation and merge buffer are the extra misses; the tree columns themselves are
close to the C layout.

### berth_sim

| | AIL typed | C |
|---|---|---|
| records | `ail_obj_Fr` (8 B header + 3×24 B `ail_list` = 80 B) per frigate, and one `ail_list` per record column; every read goes through `ail_ir_view_get` (checked) | `uint32` arrays `id,arr,cargo,op`, `uint8` `sz,pr`; a berth is an index into them |
| sort | `ord.sort(key=...)` emits `keys` + a copy of `keys` + an index list + a permutation array + a merge buffer, five n-element arrays; comparator reads `key[perm[i]]` (3 dependent loads) | packs key and index in one 8 B word, `ord[i] = ((u64)arr[i] << 22) | i`, and `qsort`s that one array |
| priority queue | `ail_list` of int64 per class plus checked get/push | packed `u64` keys in 8 B `WE`/`u64` arrays (`key = (pr<<60)|(arr<<30)|id`) |
| object headers / padding | 8 B header per `Fr`; 24 B list headers; `WE` 16 B with padding (C also has this one) | no object header; arrays only |

`ail_keysort_perm` is 44.1M LLC (56% of AIL's 78.4M). The edit below shows that this is **not** the
permutation array: sorting the index list in place still costs 44.2M in the new comparator. The
misses are the random reads of the key column in comparison order. Only the auxiliary arrays
(4.4M) are removable without packing key and index together.

### ticket_audit

| | AIL typed | C |
|---|---|---|
| venue / event tables | `State` object with `ail_sdict vidx` (string intern: `ail_sslot` 8 B + `val` 8 B + `order[]` 24 B per entry + `fill/cap/top`), `ail_idict evidx`, five `ail_list` columns per table and `ail_sset seats` | fixed arrays `ev_venue/ev_price/ev_sold[]` and `ev_bits[]`, indexed by the venue code `(A..Z)`; no hash, no intern |
| strings | each token is an `ail_str` view, but field names go through the string-interning `ail_sdict` for equality | `F { const char *p; size_t n; }` slices of the input buffer; `memcmp` against a literal |
| fields | every `list[...]`/`int` field is a separate `ail_list` in the `State` object (16 fields, ~400 B object) | one allocation per column, fixed size `NV`/`NE` |
| refcounts / padding | 8 B object header; `ail_str` 24 B padded; `ail_sslot` 8 B | no header, no padded string object |

The intern table is 5.77M of the 10.69M AIL LLC (54%): `ail__stab_compact` 1.87M,
`ail_stab_lookup` 1.11M, `ail_stab_place` 0.97M, `ail_stab_free` 0.93M, `ail_stab_reslot` 0.58M,
`ail_stab_put` 0.31M. C pays 4.22M total and never interns. **No hand edit was measured for this
cause**, so no saving is claimed.

### echo_pack

| | AIL typed | C |
|---|---|---|
| `prev` chain | `list[int]` → `ail_list` of **int64**: 8 B per position, 256 MiB for the 32M-byte input; filled by `[-1 for _ in range(n)]` (32M pushes), then stored through a checked `ail_ir_view_get/set` | `uint32_t *prev`, 4 B per position, 128 MiB, `memset`-free (written before read) |
| `head` table | `dict[int,int]` → `ail_idict` (`ail_tab` in HASH mode): 16 B `ail_hent` per entry, a `used[]` byte per slot, and an insertion-order `order[]` int64 per entry that this program never reads, plus array/hash mode switching | a direct-mapped `uint32_t head[1<<20]` (4 MiB) keyed by 20 bits of the four bytes, chained through `prev[]` |
| lookup | `has(k)` then `need(k)`: two probes of the same key on the miss path; the unconditional store also fills `-1` first and tests membership before storing | one read `head[k]`, one store `head[k]=i`, `prev[i]=old` |
| output | `ail_bytearray_append` per byte | direct `o[on++]` |
| headers / padding / temporaries | 8 B `ail_bytearray` header/refcount; `ail_hent` 16 B vs a 4 B array slot; `ail_str` views | none |

The `prev` fill and the `pack` loop are 4.0M + 4.4M of the 11.2M AIL LLC. The `head` dict adds
1.5M (`ail_tab_hgrow/hput/hslot/hash_rearray/order_append`).

### ledger_bin

| | AIL typed | C |
|---|---|---|
| records | `ail_list` columns plus an `ail_obj_Rd` (8 B header + 16 B `ail_bytes` + two int64 = 40 B); every field read is `ail_list_get` / `ail_bytes_get` with a bounds check | one `Rec` array (32 B/record: `int op; size_t off; uint32 a,b,c`) and one `Acct` array (32 B/account: `uint32 id; int shut; int64 bal; size_t name_off; int name_len`) |
| accounts | `ail_idict` (`ail_tab`: 16 B entries + `used[]` + insertion `order[]`), checked accessor | `size_t ht[]` open-addressed table of indices into the `Acct` array |
| bytes | `ail_bytes` + a checked getter per byte in `readvar` | direct `buf[p++]` |
| headers / padding | 8 B header on `Rd`; 24 B list headers; `ail_hent` 16 B | no header; `Acct`/`Rec` pad to 32 B |

`ail_list_push` 2.53M + `ail_ir_list_get` 1.50M + `ail_bytes_get` 0.92M + `readvar` 0.92M =
5.87M of 14.45M (41%). **No hand edit was measured**, so no saving is claimed.

## Step 2: per-structure attribution

Per-structure LLC misses from the annotated source (`analyze.py`), AIL then C. The attributed total
is below the cachegrind total because lines outside a detected function or in inlined library code
are not charged; the coverage is given.

### tree_fold — attributed 78.05M / 89.56M (87%)

| data structure | LLC read | LLC write | total | share |
|---|---:|---:|---:|---:|
| inlined lines (`code:?`, mostly the sort) | 10,348,049 | 10,987,260 | 21,335,309 | 27.3% |
| `ail_list_push` | 11 | 11,103,098 | 11,103,109 | 14.2% |
| `ail__key_i64_first` | 7,348,936 | 4 | 7,348,940 | 9.4% |
| `runtime:ail_list` | 4,928,934 | 1,214,816 | 6,143,750 | 7.9% |
| `ail_list_span_get` | 5,630,593 | 0 | 5,630,593 | 7.2% |
| `ail_keysort_perm` | 2,178,455 | 1,214,796 | 3,393,251 | 4.3% |
| `ail_pslist_at` | 2,656,453 | 2 | 2,656,455 | 3.4% |
| `py_main` | 2,393,543 | 3 | 2,393,546 | 3.1% |
| `ail_list_get` | 2,372,692 | 0 | 2,372,692 | 3.0% |
| `ck_add` | 2,240,339 | 0 | 2,240,339 | 2.9% |

C, for comparison: `main` 6.56M, `compute_sub` 4.64M, `pre_next` 4.14M, `parse_tree` 1.12M,
`newnode` 0.65M, `cmp` 0.61M — 18.5M attributed of 19.96M (93%).

### berth_sim — per function (the per-class `code:?` is the same inlined lines)

| function | LLC | share of AIL |
|---|---:|---:|
| `ail_keysort_perm` | 44,050,526 | 56.2% |
| `py_main` (record columns, checked `ir_view_get`) | 22,712,585 | 29.0% |
| `???` (inlined runtime) | 9,216,325 | 11.8% |
| `ail_perm_apply` (two sites) | 2,449,452 | 3.1% |

C: `main` 16.63M (84.7%) + `cmpu` 1.24M + `rd` 1.26M.

### ticket_audit — attributed 7.17M / 10.69M (67%)

`ail__stab_compact` 1.87M (26.1%), `ail_stab_lookup` 1.11M (15.5%), `py_main` 0.97M (13.5%),
`ail_stab_place` 0.97M (13.5%), `ail_stab_free` 0.93M (13.0%), `ail_stab_reslot` 0.58M (8.1%),
`ail_stab_put` 0.31M (4.4%), `ail_str_eq` 0.18M. C is 4.22M in `main`, no intern.

### echo_pack — attributed 11.04M / 11.18M (99%)

`pack` 4.43M (40.1%; read 0.50M, write 3.93M), `ail_list_push` 4.00M (36.2%, all writes — the
`prev` fill), `ail_tab_hgrow` 0.84M (7.6%), `hash_of` 0.50M (4.5%), `ail_tab_hput` 0.30M,
`ail_tab_hslot` 0.27M, `ail_bytearray_append` 0.23M, `runtime:ail_tab` 0.23M,
`ail_tab_hash_rearray` 0.12M, `ail_tab_order_append` 0.11M. C is effectively 2 LLC misses.

### ledger_bin — attributed 7.39M / 14.45M (51%)

`ail_list_push` 2.53M (34.2%, writes), `ail_ir_list_get` 1.50M (20.3%), `ail_bytes_get` 0.92M,
`readvar` 0.92M, `py_main` 0.51M, `ail_slist_push` 0.28M, `ail_tab_hgrow` 0.16M,
`ail_slist_get` 0.14M, `ail_sarena_free` 0.09M, `ail_sarena_pushn` 0.09M.

## Step 3: hand edits and measured deltas

Each edit is a fresh copy of the emitted `program.c` (`edits/<task>_<label>.py`), built with the
same flags. `Δ` columns are `AIL − variant`, so **positive LLC/instructions = the edit removes
them**, and negative wall = faster. "excess" is AIL − C. `probe.py` compares every case with
CPython (public + hidden + synthetic boundaries); all listed variants match on every case.

| task | edit | Δ LLC | % of AIL LLC | % of excess | Δ instructions | Δ wall ms | Δ RSS KiB | Δ exe B | probe |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| tree_fold | `flat` — direct comparator, no columns/perm/buffer/`perm_apply` | **41,434,366** | 46.3% | 59.5% | −237,507,620 (more) | −88.5 (−8.0%) | −35,572 | −40,384 | 25/25 same |
| tree_fold | `directcmp` — direct comparator, columns still built | 34,451,856 | 38.5% | 49.5% | −684,592,201 (more) | −5.1 (−0.5%) | −12,616 | −26,832 | 25/25 same |
| berth_sim | `directsort` — in-place index sort against the key column | 4,392,754 | 5.6% | 7.7% | −20,564,372 (more) | −4.6 (−0.2%) | −22,912 | −19,344 | 31/31 same |
| echo_pack | `prev32` — `prev` as int32 instead of int64 | 4,151,562 | 37.1% | 53.1% | +530,824,232 (fewer) | +10.1 (+1.3%) | −124,940 | −5,840 | 25/25 same |
| echo_pack | `uncond` — no `-1` fill, one probe on the miss path | 3,923,535 | 35.1% | 50.2% | +252,112,831 (fewer) | +19.1 (+2.4%) | −10,436 | −392 | 25/25 same |
| echo_pack | `both` — `uncond` then `prev32` | 4,132,285 | 36.9% | 52.8% | +480,415,264 (fewer) | +20.8 (+2.7%) | −124,944 | −3,208 | 25/25 same |
| echo_pack | `flathead` — dict → direct open-addressed `(key,val)` array | **−588,066** | −5.3% | −7.5% | +55,849,824 (fewer) | +125.2 (+16.0%) | +16,628 | −29,280 | 25/25 same |

Notes on the edits:

* **tree_fold `flat` vs `directcmp`.** Both use the same direct comparator. `directcmp` still builds
  the three key columns, the name-view list and the permutation (it just does not read them), so the
  difference is the cost of building/freeing the columns: 34.45M vs 41.43M, i.e. 6.98M. The
  comparator itself (no four-entry descriptor, no three gathers) is the larger part.
* **berth_sim `directsort` is honest but small.** The edit removes the permutation array, the key
  copy and `perm_apply`, yet the new `ail_layout_sort_idx` still costs 44.2M: the sort reads
  `key[src[i]]` in permuted order, which is the same random-access pattern. Only 4.39M of the
  56.7M excess is the auxiliary arrays. C's win comes from packing key+index into one 8 B word, not
  from removing an array. The two earlier variants tried (a 16 B `(key,index)` record: 92.2M LLC;
  `qsort` over the index list: 35.1M LLC but +2.17e9 instructions) are recorded in the script.
* **echo_pack edits are not additive.** `uncond` (3.92M) and `prev32` (4.15M) touch the same array;
  `both` recovers 4.13M, not their sum. `prev32`'s replacement initialisation re-introduces an
  int32 fill (~2.1M in inlined `?`), which cancels `uncond`'s saving. The wall deltas of all three
  are within the 5-run spread (AIL 0.783–0.812 s; `prev32` 0.793–0.880 s), so **no wall-time
  improvement is claimed for echo_pack** even though the memory traffic falls. The saving is an
  energy/traffic result.
* **`flathead` is worse** and is rejected: the program's 4 MiB direct-mapped array beats a 16 B-entry
  general hash table on this access pattern, and the hand edit's 16 B `(key,val,used)` slot is
  larger than the C array slot.

Probe coverage (`lab/layout/probe.py`; each case is CPython vs the edited C, stdout and rc):
perf + every public + every hidden case + the synthetic boundaries in `probe.py:EXTRA`
(empty, one element, all-equal keys, max width, deep chain, sort none/single). All 7 variants:
same on every case. The `berth_sim` `all-same-keys` boundary was wrong on the first run — it
declared `S=1` and supplied three ships, which the original AIL (and CPython differ on) — and was
corrected to `S=3`; with the valid header CPython, the original AIL and the edit are identical.

## Step 4: ranked candidate compiler changes (measured only)

Ordered by measured LLC saving. The Amdahl ceiling is the measured wall fraction extrapolated to
the whole AIL−C LLC gap: `ceiling = (Δwall / wall) / (ΔLLC / excess)`, `speedup = 1/(1-ceiling)`.
It is an extrapolation, not a measurement; the measured wall column is the measurement.

### 1. tree_fold-style keyed sort: compare the existing columns, do not build key columns

* **Programs:** tree_fold (and any `list.sort`/`sorted` whose key is a tuple of plain column reads
  on an object that the sort does not mutate).
* **Measured:** −41.43M LLC (59.5% of the 69.6M excess), −88.5 ms wall (−8.0%), −34.7 MiB RSS,
  −39.4 KiB exe. The comparator-only part is 34.45M; not building the columns adds 6.98M.
* **Safe when (docs/spec/DIFFERENCES.md):** the key expression reads `f_*` columns and plain
  builtins only, and those columns are not written by the key or by any code the sort calls
  (AIL's typed path has no user-visible mutation during a builtin sort); the sorted object is the
  freshly built index list of `range(n)`, which is not aliased and does not escape (the typed-path
  alias refusal, C2 `aliasrefuse.py`, and the copy-on-store rule make that checkable); the
  comparator is a total order, with the index as the last tie-break, so the order equals the
  emitted stable keysort; the columns stay alive until after the sort (the `flat` edit moves
  `ail_list_free(sub)` past the sort). It is **not** safe if the key is a call, if the key reads a
  column that the sort or a `__lt__` can mutate, or if the list is aliased (the typed path refuses
  aliasing by name rather than copying, C2).
* **RSS / size:** −34.7 MiB RSS, −39.4 KiB executable on this program.
* **Amdahl:** measured 8.0% for 59.5% of the gap; ceiling 13.4% → **1.155x** if the whole AIL−C LLC
  gap were closed (upper bound).

### 2. berth_sim-style keyed sort: sort the index list in place

* **Programs:** berth_sim, and single-key sorts that currently materialise a key column + copy +
  permutation + merge buffer.
* **Measured:** −4.39M LLC (7.7% of berth's excess), −4.6 ms wall (−0.2%), −22.4 MiB RSS,
  −18.9 KiB exe. The remaining 44.2M in the sort is the random key-column read, so this change
  only removes the auxiliary arrays.
* **Safe when:** one key column, read-only during the sort; the index list is the local `range(n)`
  (not aliased, C2); the sort is stable or ties break on the index exactly as the emitted sort
  does; keys compare without side effects. Same escape/alias conditions as #1. Packing key and
  index into one word (what C does) is a *different* change and needs a range proof for the
  key width; it is not measured here.
* **RSS / size:** −22.4 MiB RSS, −18.9 KiB exe.
* **Amdahl:** 0.2% wall for 7.7% of the gap; ceiling 2.8% → **1.029x**.

### 3. echo_pack `prev` chain: natural element width and no redundant fill

* **Programs:** echo_pack's `prev` chain, and lists built by a `[-1 for _ in range(n)]`
  comprehension whose elements are immediately overwritten.
* **Measured:** `prev32` −4.15M LLC (53.1% of echo_pack's excess), −124.9 MiB RSS, −5.8 KiB exe;
  `uncond` −3.92M (50.2%), −10.4 MiB RSS. Combined `both` 4.13M (the two overlap; not additive).
  Wall time does **not** improve (within run spread).
* **Safe when:** for `prev32`, a range proof shows every stored value and every index is in
  `[-1, 2**31)`, and every read is through a checked accessor (the edit keeps the bounds check);
  without that proof the compiler must keep int64. For the fill removal, the comprehension result
  is a fresh local that nothing reads between construction and the first store, and every element
  is written before it is read (`prev[i]` is stored for every `i` the loop reaches). This is a
  local escape/mutation proof; C2's copy-on-store does not apply because the list does not escape.
  The dict probe fusion additionally needs no mutation of the dict between `has` and `need`.
* **RSS / size:** −124.9 MiB RSS (int32), −5.8 KiB exe.
* **Amdahl:** no measured wall gain (`prev32` is 1.3% *slower* in best-of-5), so the wall-time
  bound is **1.0x**; the gain is memory traffic/energy. Do not claim a speedup.

### Rejected

* **echo_pack `flathead` (dict → direct open-addressed array):** −588k worse LLC, +125 ms wall,
  +16.6 MiB RSS. Reject for this program; the access pattern favours the 4 MiB direct-mapped array,
  and the general slot is larger.

### Identified but not measured (no gain claimed)

* **ticket_audit string interning (`ail_sdict`):** 5.77M of 10.69M AIL LLC. C slices the input and
  does not intern. A compiler change would have to prove that every token is a view of one buffer
  and that the dict is only used for equality — plausible here (`F {p,n}` slices), but no hand edit
  was built, so no saving is projected.
* **ledger_bin checked list/bytes accessors and column lists:** 5.87M of 14.45M. C stores a fixed
  `Rec`/`Acct` array and reads bytes directly. Merging `ail_list` columns into one record array is
  a plausibly large change, but no hand edit was measured.

## Reproduce

```sh
bash lab/layout/run.sh                 # baselines + edits (~20 min), writes data/layout.json
python3 lab/layout/analyze.py          # rewrites data/analysis.json
python3 lab/layout/analyze.py --print  # prints the tables above
python3 lab/layout/probe.py tree_fold flat
python3 lab/layout/probe.py echo_pack prev32
```

`run.sh` unpacks valgrind under `$TMPDIR` if it is not on `PATH` and never writes the repository.
`data/layout.json` and `data/analysis.json` are generated from the committed `edits/*.py`; the
labels in the JSON are the script suffixes (`tree_fold`: `flat`, `directcmp`; `berth_sim`:
`directsort`; `echo_pack`: `both`, `flathead`, `prev32`, `uncond`).
