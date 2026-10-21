**Commit:** `9c780de` on `job-fuzz4-10220602` (records in root `DEVLOG.md` / `DIFFERENCES.md`; manifest and shard checks pass).

**Fuzzing:** 240 generated programs (dict ordering/churn, set algebra/subset churn, range churn, comprehension/update/delete templates) plus 50+ hand-written edge programs, each run with `bash ~/tools/cmp.sh` on both builds.

**Fixed 2 causes (limit 3):**
1. Dict methods re-hashed stored keys. `pop`/`setdefault` now hash once; `update(other_dict)`, `copy`, `popitem`, and `dict(d)` reuse stored hashes; empty-dict `pop` takes CPython’s no-hash fast path. Both runtimes updated.
2. Dict/set literals on the general path now evaluate all key/value/element expressions before hashing/inserting, matching CPython 3.12 `BUILD_MAP`/`BUILD_SET` (e.g. an unhashable early key no longer suppresses later side effects). The typed literal path has no user `__hash__` keys.

**Tests added:** `AIL_CURRENT/test_ail_fuzz4.py` (3 tests: hash counts, empty-pop/copy/popitem, literal ordering), registered in `ail_check`, `MANIFEST`, and CI shards.

**Final-commit tests (0 failures):** `test_ail_fuzz4`, `test_ail_int_dict_set`, `test_ail_dict_delete`, `test_ail_dict_upsert`, `test_ail_builtin_maps`, `test_ail_freestanding`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. A broader 15-module run on the parent commit (same code, docs-only last commit) also passed, including `test_ail_collections`, `test_ail_sets_general`, `test_ail_silent1/2`, `test_ail_gaps_api2`, `test_ail_unified`.

**Self-check probes in `/tmp/probes` (all match CPython on both builds):**
- `p1_hash_places.py` — pop/setdefault/update/copy/popitem/dict through argument, list item, attribute, dict value: same.
- `p2_hash_edges.py` — collisions, negative keys, missing/default, empty: same.
- `p3_literal_order.py` — unhashable keys + later side effects, custom hash: same.
- `p4_literal_nested.py` — nested literals; both end with the same uncaught `TypeError`, same stdout/exit.
- `p5_builtin_dicts.py` — ordinary int/str dict/set/frozenset operations: same.
- `p6_alias_copy.py` — aliases, copy/update, containers: same.
- `p7_hash_popitem.py` — collisions, copy, repeated popitem: same.
- `p8_empty.py` — empty-dict pop/get/setdefault/update/popitem: same.

**Listed as remaining, not fixed:** same-size dict mutation during live iteration still differs between paths/declared structural rule; `reversed(dict)` and `dict | dict` stop at runtime; `dict(d)` may call a user `__eq__` a different number of times than CPython for some internal table shapes. `test_ail_fuzz1` could not run because `difffuzz` is absent from this snapshot; it is not a required module.
[cost $0.53, turns 199]
