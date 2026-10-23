# job job-pre5-10240009  started 2026-10-23T15:12:13Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `33821cb`.

- Fixed `reversed(dict)` in `cruntime.py`: new `AIL_IT_DICT_REV_KEYS` walks entries in reverse insertion order, raises `RuntimeError: dictionary changed size during iteration` on live size changes, and stops cleanly after exhaustion.
- Added `test_ail_pre5.py` and registered it in `ail_check.py`; added DEVLOG entry.
- No `DIFFERENCES` file exists in this export, so no row was added.
- `update_manifest.py --check` passes.

Probes (`cmp.sh`, both general and default builds, all `same stdout`):
`reversed_dict`, `reversed_dict_basic`, `reversed_dict_containers`, `reversed_dict_mutation`, `reversed_dict_typed`.

Tests on final commit: `test_ail_pre5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 258s.
[cost $0.0000, opencode tokens {"total": 3590275, "input": 81510, "output": 13199, "reasoning": 9230, "cache.write": 0, "cache.read": 3486336}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `33821cb` (reversed(dict))**

Reproduced the target difference on both builds (`base` raises `TypeError: 'dict' object is not reversible`; HEAD matches CPython for normal reverse iteration).

**Probes (my own, `/tmp/rprobes/`)**

| Probe | HEAD g/d | base | Notes |
|---|---|---|---|
| p1_basic | same | differs (TypeError) | order, del/update, Unicode, int/bool |
| p2_empty_edges | same | differs (TypeError) | empty, single, 1000 entries |
| p3_containers | same | differs (TypeError) | arg, list item, attribute, dict value, defaultdict |
| p4_mutation | same | differs (TypeError) | add/delete/value/size-change/exhaustion |
| p5_nofeature | same | same | no `reversed` use |
| p6_samesize | **DIFF** | differs (TypeError) | same-size mutation |
| p7_samesize_min | **DIFF** | differs (TypeError) | minimal same-size mutation |

The C diff for a program not using `reversed` consists only of the inlined runtime additions (enum, `ail_iter_reversed`, new `ail_next` case); no unexpected codegen change. Manifest `--check` passes. `test_ail_pre5` + `test_ail_safetynet`: 2 modules, 0 failed (123s).

**Defect found (both general and default builds)**

Because AIL compacts dict entries on deletion, a reverse iterator created before a same-size mutation can visit a key already visited / skip a key CPython visits. CPython checks only the size, so no `RuntimeError` is raised in this case.

Probe `/tmp/rprobes/p7_samesize_min.py`:
```python
d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
del d['a']
d['a'] = 9
print(list(it))

d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
del d['a']
d['z'] = 9
print(list(it))
```
Expected (CPython 3.12):
```
c
['b']
c
['b']
```
Actual (HEAD, `g` and `d`):
```
c
['c', 'b']
c
['c', 'b']
```
The new `test_ail_pre5.py` mutation cases only delete tail entries or clear+refill, so they miss this.

**Report claims**
- Runtime change / reverse insertion order / deletion+update order: verified.
- Size-change `RuntimeError` and post-exhaustion `StopIteration`: verified.
- `test_ail_pre5` added and registered, DEVLOG, no DIFFERENCES file, manifest check: verified.
- “4 modules, 0 failed”: partially verified (pre5+safetynet rerun, 0 failed; files/corpus not rerun per review protocol).
- Worker probe results: unverified (probe files not part of the commit).
- Speed: unverified — `tools/icount.c` fails with `perf_event_open: Permission denied` in this runner.

Pre-existing: the base `reversed(dict)` `TypeError` is the recorded difference being fixed; no other pre-existing difference reproduced.

VERDICT: FIX

1. Same-size mutation that shifts dict entries (e.g. `del d['a']; d['a']=9` or `del d['a']; d['z']=9` after one `next`) makes `reversed(d)` return `['c','b']` instead of CPython’s `['b']`, because deletion compacts AIL’s entry array and the iterator’s stored index then points at a different key (a key may even be repeated). Probe source and expected/actual are above; both `g` and `d` builds affected.
[cost $0.0000, opencode tokens {"total": 517619, "input": 30343, "output": 5038, "reasoning": 8638, "cache.write": 0, "cache.read": 473600}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `296737c`.

**Cause/fix:** `reversed(d)` used the dense `entries` index, which deletion compacts. Dicts now keep a CPython-style physical slot array (`phys`): append on insert, hole on delete, truncate on `popitem`, reset on `clear`, and compact on CPython’s `used*3` / 2/3 resize schedule. The reverse iterator walks that array, skips holes, clamps after `clear`, and makes size-mismatch `RuntimeError`s sticky.

**Probes** (`bash ~/tools/cmp.sh`, `g` and `d` builds, all `same stdout`):

| Probe | Covers |
|---|---|
| `p_samesize` | reviewer’s two minimal cases |
| `pre5_p1_basic` | order, updates, key types, Unicode |
| `pre5_p2_edges` | empty, one, 1000 entries, sizes 2–17 |
| `pre5_p3_containers` | argument, list item, attribute, dict value, defaultdict |
| `pre5_p4_mutation` | head/middle delete+insert, size changes, resize during iteration |
| `pre5_p5_clear` | clear/refill, holes, shorter physical array |
| `pre5_p6_nofeature` | unchanged dict/list behavior |
| `pre5_p7_churn` | 30 randomized churn runs across 10 dict sizes, resizes and sticky errors |
| `pre5_p8_popitem` | `popitem` + reinsert before/after first `next` |

**Tests on final commit:** `test_ail_pre5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 27 ran, 0 failed, 1 skipped (no zig for Windows target). Manifest `--check` passes; no DIFFERENCES row was added because no DIFFERENCES file exists.
[cost $0.0000, opencode tokens {"total": 5931724, "input": 125511, "output": 18073, "reasoning": 33260, "cache.write": 0, "cache.read": 5754880}]

## review 1 failed to run: (no final text) [cost $0.0000, opencode tokens {"total": 320221, "input": 39122, "output": 2356, "reasoning": 15063, "cache.write": 0, "cache.read": 263680}] (cut off after 60 minutes) 

## review 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T18:10:44Z
