# job job-fuzz79-10231550  started 2026-10-23T06:51:13Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed on `job-fuzz79-10231550`.

- Finding: a class with `__getitem__` but no `__iter__` failed all iteration paths (`list(s)`, `for`, comprehensions, `in`, `sum`, `min/max`, `sorted`, `zip`, `enumerate`, unpacking, `iter/next`) with `TypeError: 'instance' object is not iterable` on both builds.
- Fix: added `AIL_IT_SEQGET` to the general runtime, calling `__getitem__(0), __getitem__(1), ...`, stopping on `IndexError`, propagating other errors, and remembering exhaustion. `__iter__` takes precedence; inherited `__getitem__` works.
- Added `AIL_CURRENT/test_ail_fuzz79.py`, registered it in `ail_check.py`, updated `MANIFEST.json`; manifest check passes.
- Probes `p01`–`p26` covered builtin-subclass refusals, `super().__getitem__`, empty sequences, no `__len__`, error propagation, exhaustion, and `__iter__` precedence.
- Final tests: `test_ail_fuzz79`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass (4/4). Also ran `test_ail_dunders`, `test_ail_unified`, `test_ail_silent5`, `test_ail_virtual_dispatch` — all pass.
- Commit: `43d60cb` (`fuzz79: implement the __getitem__ sequence protocol on the general path`).

Note: `DIFFERENCES`/`DEVLOG` are absent from this CI mirror, so no entries could be added there.
[cost $0.0000, opencode tokens {"total": 8540551, "input": 742803, "output": 24485, "reasoning": 23759, "cache.write": 0, "cache.read": 7749504}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
WORKER COMMIT: `43d60cb` (5 files: `ail_check.py`, `MANIFEST.json`, `cruntime.py`, `dunderrt.py`, `test_ail_fuzz79.py`).

Probes (all run with `cmp.sh` on both builds, `/tmp/rprobes/`): `p01b_basic`, `p02_index_sub`, `p03_next_no_iter`, `p04_both`, `p05_list_sub`, `p06_dict_sub`, `p07_str_sub`, `p08_contains`, `p09_places`, `p10_mutate`, `p11_neg_types`, `p12_stopiter`, `p12b_stopiter_partial`, `p13_edges`, `p14_iterself`, `p15_inherit`.

Tests: `test_ail_fuzz79` + `test_ail_safetynet` pass; `test_ail_files` + `test_ail_corpus_findings3` pass. `update_manifest.py --check` silent (pass). `DIFFERENCES`/`DEVLOG` absent from this mirror (confirmed).

C comparison vs `/tmp/base`: a no-class program differs only by the added `AIL_IT_SEQGET` enum line; class programs differ only by the expected enum/branch/case. No behavioural change for non-users.

Speed: not measured — `perf_event_open` is denied here. No hot-path cost is plausible: the new `ail_dun2` check runs only on the previously-raising `!fn` path, and the switch gained a case without touching existing kinds.

Claim check:
- Feature works for plain/inherited/`super().__getitem__` classes, all consumers: verified (`p01b`, `p09`, `p15`).
- "Stops on IndexError, propagates other errors": **false** — CPython's sequence iterator also ends on `StopIteration` (`p12b`).
- "`__iter__` takes precedence": **false** in the `__iter__`-returns-self-without-`__next__` boundary (`p14`).
- Manifest/test/commit claims: verified.
- Builtin subclassing (`list`, `dict`, `str`) is still refused by name on base and HEAD (`p05`–`p07`); that is pre-existing and allowed by the task, but the change does not address the task's stated builtin-inheritance area, and it fixes a loud TypeError rather than a silent wrong answer.

Pre-existing (identical on base, not blocking):
- `p03`: class with `__getitem__` **and** `__next__` but no `__iter__`; CPython iterates via `__getitem__` (`[0, 10, 20]`), AIL uses `__next__` (`[-1, -2]`).
- `p13`: non-callable `__getitem__` and `__getitem__` with a default argument; AIL says not iterable, CPython defers/iterates.

VERDICT: FIX

1. `p14_iterself.py` — an `__iter__` that returns `self` with no `__next__` must not fall back to `__getitem__`.
```python
class C:
    def __iter__(self): return self
    def __getitem__(self, i):
        if i >= 2: raise IndexError
        return i
def main():
    try: print(list(C()))
    except TypeError as e: print('TypeError', e)
    try:
        it = iter(C()); print('iter ok'); print(next(it))
    except TypeError as e: print('TypeError2', e)
    print('done')
main()
```
Expected (CPython): `TypeError iter() returned non-iterator of type 'C'` / `TypeError2 iter() returned non-iterator of type 'C'` / `done`, exit 0.
Actual (both builds): `[0, 1]` / `iter ok` / `0` / `done`, exit 0 — a new silent wrong answer. Cause: the `!fn` block treats `__iter__`-returned-self-without-`__next__` like "no `__iter__`". Fix: use the `__getitem__` fallback only when no `__iter__` was defined at all; otherwise raise "iter() returned non-iterator".

2. `p12b_stopiter_partial.py` — `StopIteration` from `__getitem__` ends CPython's sequence iteration, not just `IndexError`.
```python
class S:
    def __getitem__(self, i):
        if i >= 3: raise StopIteration
        return i
def main():
    for x in S(): print(x)
    print('after')
    for x in iter(S()): print('n', x)
    print('done')
main()
```
Expected (CPython): `0 1 2 after n 0 n 1 n 2 done`, exit 0.
Actual (both builds): `0 1 2`, then uncaught `StopIteration`, exit 1. Cause: `AIL_IT_SEQGET` checks only `IndexError`. Fix: treat `StopIteration` (and subclasses) as exhaustion too, clearing it like `IndexError`.
[cost $0.0000, opencode tokens {"total": 1359599, "input": 57515, "output": 8003, "reasoning": 18433, "cache.write": 0, "cache.read": 1275648}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {"total": 1229187, "input": 105777, "output": 6372, "reasoning": 7278, "cache.write": 0, "cache.read": 1109760}]
(cut off after 60 minutes)

## review 1 failed to run: (no final text) [cost $0.0000, opencode tokens {}] (cut off after 60 minutes) 

## review 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T10:53:12Z
