# job job-pre57-10241245  started 2026-10-24T03:56:19Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Fixed:** the pre-existing p10/p14 difference — `dict()`/`update()`/`copy()` after delete+reinsert called user `__eq__` in the wrong order/count, and source construction printed them in a different order. Base probe differs; final build matches CPython.

**Change:** track CPython 3.12 `dk_nentries`, trailing dummies and dummy index slots; use stored hashes for dict merge/copy; skip `-2` slots in dict equality; update the safetyrt defaultdict field patch. Commits: `52ed969`, `462ab2b`.

**Probes** (`bash ~/tools/cmp.sh`, both `g` and `d`, all stdout+exit match CPython; the first two also differ on the base tree):
- `pre57_update_delete_reinsert`
- `pre57_tail_pop_reinsert`
- `pre57_eq_tombstone`
- `pre57_source_order`
- `pre57_plain_boundaries`

ASan build of `pre57_eq_tombstone`: clean, output matches.

**Tests on final commit** (`-j 2`): `test_ail_pre57`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_builtin_maps`, `test_ail_sets_general` — 6 modules, 0 failed, 272 s. `update_manifest.py --check` rc 0.

**Unverified:** instruction counts (`perf_event_open` denied); wide-suite behaviour. No push.
[cost $0.0000, opencode tokens {"total": 4122586, "input": 296731, "output": 13541, "reasoning": 15834, "cache.write": 0, "cache.read": 3796480}]
    tool time: bash 13.3 min, edit 0.0 min, write 0.0 min
        277s bash   cd AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pre57 test_ail_safetynet test_ail_f
        273s bash   cd AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pre57 test_ail_safetynet test_ail_f
        101s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && cd AIL_CURRENT && timeout 1200
         28s bash   cd /tmp && for p in pre43_clean pre43_dirty pre43_update pre43_capacity pre43_tailgap pre43_nonuser; do echo "
         27s bash   cd /tmp && for p in pre43_clean pre43_dirty pre43_update pre43_capacity pre43_tailgap pre43_nonuser; do echo "
         25s bash   cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre57 2>&1 | tail -30
         23s bash   cd /tmp && for p in pre57_update_delete_reinsert pre57_tail_pop_reinsert pre57_eq_tombstone pre57_source_order
         23s bash   cd /tmp && for p in pre57_update_delete_reinsert pre57_tail_pop_reinsert pre57_eq_tombstone pre57_source_order

## review 0
[model opencode/deepseek-v4.1-flash-free]
​Reviewed `work..HEAD` (2 commits). The diff adds CPython-style `dk_nentries`/trailing-dummy/dummy-index tracking, stored-hash merge/copy, `-2` skips in equality, and updates the safetyrt struct patch. Report's general description is accurate, but the implementation has two regressions versus the base tree.

**Verification**
- Worker probes: all 5 match CPython on HEAD, both builds.
- But on base the first **four** differ, not "the first two" (`eq_tombstone` and `source_order` differ too); `plain_boundaries` matches.
- `test_ail_pre57` and `test_ail_safetynet` pass on HEAD (`-j 2`, 0 failed). `update_manifest.py --check` rc 0.
- ASan, the other four test modules, and instruction counts unverified (`perf_event_open` denied).

**Pre-existing (not blocking)**
- Fuzz scenario `n=10,hmul=32,every,update0`: HEAD and base both print `232 35 8986346 ...`, CPython `232 37 7840160 ...`.
- Broad popitem/reinsert cases also differ on both trees.

## Defects

### 1. `dict()` copy changes `__eq__` argument order after delete/reinsert (regression; base matches CPython)
`AIL_CURRENT/python/pkg-v12/cruntime.py:14450` skips AIL's `-2` dummy slots, but those dummies sit at linear-probe positions unlike CPython's perturbed slots after `ail_map_del` (`cruntime.py:15214`).

Probe `/tmp/rprobes/pre57_reg_eq.py`:
```python
class K:
    def __init__(self, v, h): self.v = v; self.h = h
    def __hash__(self): return self.h
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v

d = {}
for i in range(6): d[K(i, (i * 32) % 64)] = i
for i in (0, 2, 4): del d[K(i, (i * 32) % 64)]
for j in range(3): d[K(1000 + j, ((1000 + j) * 32) % 64)] = 1000 + j
e = dict(d)
print(d == e)
print(e == d)
```
Expected (`e == d`, CPython and base):
```
E 1 3
E 1 5
E 3 5
E 1 1001
E 3 1001
E 5 1001
E 1000 1002
```
Actual (HEAD, both builds):
```
E 1 3
E 1 5
E 3 5
E 1001 5
E 1 1001
E 3 1001
E 1000 1002
```

### 2. `dict()` misses an `__eq__` call after `popitem()` (regression; base matches CPython)
`ail_map_insert_new` tests `nentries >= usable(cap)` (`cruntime.py:15140`), but CPython tests `dk_usable <= 0`; `popitem` lowers `dk_nentries` without restoring `dk_usable`. The dict therefore keeps a different capacity, so `dict(d)` takes AIL's clone fast path and omits a collision comparison.

Probe `/tmp/rprobes/pre57_reg_pop.py`:
```python
class K:
    def __init__(self, v, h): self.v = v; self.h = h
    def __hash__(self): return self.h
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v

d = {}
for i in range(21): d[K(i, (i * 3) % 64)] = i
d.popitem()
d.popitem()
d[K(2000, (2000 * 3) % 64)] = 2000
e = dict(d)
print([k.v for k in e])
```
Expected (CPython and base: one extra `E 16 2000` during `dict(d)`):
```
E 16 2000
[0, 1, ..., 18, 2000]
E 16 2000
```
Actual (HEAD, both builds; the second `E 16 2000` is missing):
```
E 16 2000
[0, 1, ..., 18, 2000]
```

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 3147160, "input": 116971, "output": 10453, "reasoning": 32692, "cache.write": 0, "cache.read": 2987044}]
    tool time: bash 7.5 min
        120s bash   find /usr -name 'dictobject.c' 2>/dev/null | head; python3 -V; ls /tmp/base57 | head; git -C /tmp/base57 log -
        101s bash   cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre57 test_ail_safetynet 2>&1 | tail
         52s bash   python3 - <<'PY' p='/tmp/gen_pre57_fuzz.py' s=open(p).read().replace('0xffffffffffffffff','0x3fffffffffffffff'
         51s bash   python3 - <<'PY' p='/tmp/gen_pre57_fuzz.py' s=open(p).read().replace('s = (s * 1000003 + (a + 7) * 131 + (b + 
         28s bash   cd /tmp && for p in pre43_clean pre43_dirty pre43_update pre43_capacity pre43_tailgap pre43_nonuser; do echo "
         27s bash   cd /tmp && for p in pre43_clean pre43_dirty pre43_update pre43_capacity pre43_tailgap pre43_nonuser; do echo "
         23s bash   cd /tmp && for p in pre57_update_delete_reinsert pre57_tail_pop_reinsert pre57_eq_tombstone pre57_source_order
         22s bash   cd /tmp && for p in pre57_update_delete_reinsert pre57_tail_pop_reinsert pre57_eq_tombstone pre57_source_order

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `d51c4e4`.

**Fixes**
- Replaced AIL’s linear dict probing with CPython’s perturbed probe sequence in lookup, insert, delete, rehash, resize, and equality; dummy slots are now allocated/reused exactly like `find_empty_slot`.
- Instance `__hash__` results are used directly (`-1` → `-2`) instead of being mixed through the int table hash.
- Added explicit `dk_usable` tracking: `popitem` lowers `nentries` without restoring the insert budget, so the next insert resizes when CPython does.
- Dict copies clone the index, including dummy slots. Added the two reviewer cases to `test_ail_pre57.py`.

**Probes** — all match CPython on both builds:
`/tmp/rprobes/pre57_reg_eq.py`, `/tmp/rprobes/pre57_reg_pop.py`, `/tmp/probes/pre57_user_hash_values.py`, `pre57_popitem_usable.py`, `pre57_eq_boundaries.py`, `pre57_int_keys.py`, `pre57_eq_style.py`, plus the existing `pre57_eq_tombstone`, `pre57_plain_boundaries`, `pre57_source_order`, `pre57_tail_pop_reinsert`, and `pre57_update_delete_reinsert`.

**Tests on final commit**: `test_ail_pre57`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` rc 0.

ASan and instruction counts remain unverified (`perf_event_open` denied).
[cost $0.0000, opencode tokens {"total": 8117398, "input": 155300, "output": 21121, "reasoning": 49905, "cache.write": 0, "cache.read": 7891072}]
    tool time: bash 11.1 min, edit 0.0 min, write 0.0 min
        215s bash   timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_pre57 test_ail_safetynet test_ail_files test_ail_corp
        214s bash   timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_pre57 test_ail_safetynet test_ail_files test_ail_corp
         57s bash   find /usr /opt /home/runner -name 'dictobject.c' 2>/dev/null | head; python3 -V; ls /usr/include/python3* 2>/d
         43s bash   cd /tmp && python3 - <<'PY' import sys print(sys.version) PY grep -rn "dk_usable\|insertion_resize\|find_empty
         24s bash   for p in /tmp/probes/pre57_update_delete_reinsert.py /tmp/probes/eq_tombstone.py /tmp/probes/source_order.py /
         19s bash   for p in /tmp/probes/pre57_eq_tombstone.py /tmp/probes/pre57_plain_boundaries.py /tmp/probes/pre57_source_orde
         10s bash   for p in /tmp/probes/pre57_eq_boundaries.py /tmp/probes/pre57_int_keys.py; do echo ==== $p; bash ~/tools/cmp.s
         10s bash   for p in /tmp/probes/pre57_user_hash_values.py /tmp/probes/pre57_popitem_usable.py; do echo ==== $p; bash ~/to

## review 1
[model opencode/deepseek-v4.1-flash-free]
Review report

**What the change really does.** It replaces the dict key-table's linear probing/rehash-on-delete with CPython 3.12's perturbed probing, dummy index slots, `dk_nentries`/`dk_usable`/trailing-dummy accounting, stored-hash merges/clones, and direct instance `__hash__` results; it also updates safetyrt's struct text and adds `test_ail_pre57.py`. This matches the worker report.

**Probes** (all in `/tmp/rprobes`, run with `bash ~/tools/cmp.sh <p> $PWD`; both builds):
- `r1_sizes.py` — 16 sizes × 4 hash schemes, delete/reinsert, `dict`/`copy`/`update`/equality: both builds match CPython. On `/tmp/base` both builds DIFF (missing `E` calls), confirming the target pre-existing difference is actually fixed.
- `r2_popitem.py` — 15 sizes × 3 hash schemes × 3 delete/pop/insert patterns: match.
- `r3_hashes.py` — `__hash__` = -1, -2, 0, 1, 2, 31, 32, 63, 2^31, 2^62, -2^63: match.
- `r4_boundaries.py` — empty/missing/negative-int keys, clear+reuse, 40-key deletes: match.
- `r5_alias.py` — dirty dict through argument/list item/attribute/dict value; copy independence after source mutation; mutation-during-iteration RuntimeError: match.
- `r6_rand1/2/3.py` — 3×220 deterministic random set/del/pop/copy/update/eq ops: match.
- `r7_eqdirty.py` — dirty vs dirty with different histories, both equality directions, dict/update/copy: match.
- `r8_upd_dirty.py` — update into dirty targets, empty dirty sources/targets: match.
- `r9_copy_mutate.py` — mutate a copy made from a dirty dict (del/insert/pop): match.
- Re-ran worker's `pre57_reg_eq.py`, `pre57_reg_pop.py`: match.

**Tests.** `test_ail_pre57` (32s), `test_ail_safetynet` (102s), `test_ail_files` (111s), `test_ail_corpus_findings3` (175s): 4 modules, 0 failed. `update_manifest.py --check` rc 0.

**Claims.** Probing/find_empty_slot, direct `__hash__` (-1→-2), `dk_usable` tracking, clone-with-dummies, and the two added test cases: all verified in the diff and by probes. Test/manifest claims verified. Worker's full probe list not rerun, but independent probes cover the same areas. No codegen file changed; only the embedded runtime differs for programs not using the feature.

**Speed.** `perf_event_open` is denied (confirmed), so `tools/icount.c` cannot run. Wall-clock on a 30k-key insert/lookup/delete/reinsert benchmark: HEAD 2.39–2.41s vs base 2.21–2.25s (~8%), not a large slowdown.

**Pre-existing.** None observed on HEAD. The base-tree difference on `r1_sizes.py` is the one this change fixes.

**Unverified.** ASan; instruction counts; the worker's remaining listed probes were not individually rerun.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 4398359, "input": 223577, "output": 11673, "reasoning": 54693, "cache.write": 0, "cache.read": 4108416}]
    tool time: bash 5.2 min, write 0.0 min, edit 0.0 min
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup timeout 1500 python3 ../tools/par_check.py -j 2 test_a
        103s bash   mkdir -p /tmp/rprobes /tmp/rlogs; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup timeout 1500 python3
         14s bash   cd /tmp/bh && for i in 1 2 3; do /usr/bin/time -f "head %e" ./exe_head >/dev/null; done; cd /tmp/bb && for i i
         13s bash   cd /home/runner/work/ail-ci/ail-ci; for p in r6_rand1 r6_rand2; do (bash ~/tools/cmp.sh /tmp/rprobes/$p.py "$P
         13s bash   cd /home/runner/work/ail-ci/ail-ci; for p in r6_rand3 r7_eqdirty; do (bash ~/tools/cmp.sh /tmp/rprobes/$p.py "
          6s bash   cd /home/runner/work/ail-ci/ail-ci; bash ~/tools/cmp.sh /tmp/rprobes/r8_upd_dirty.py "$PWD" > /tmp/rlogs/r8.he
          6s bash   cd /home/runner/work/ail-ci/ail-ci; bash ~/tools/cmp.sh /tmp/rprobes/r9_copy_mutate.py "$PWD" > /tmp/rlogs/r9.
          6s bash   cd /home/runner/work/ail-ci/ail-ci; bash ~/tools/cmp.sh /tmp/rprobes/r5_alias.py "$PWD" > /tmp/rlogs/r5_alias.

FINAL VERDICT: ACCEPT  2026-10-24T05:04:40Z
