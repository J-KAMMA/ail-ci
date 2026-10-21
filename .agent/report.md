Fixed and committed on `job-fuzz8-10220554` as `d1320aa`.

**Fuzz run:** 65 random iteration-tool programs on both builds:
- 46 match CPython on both builds
- 10 refused by name at compile time
- 9 remaining differences (listed below)

**Fixed 3 causes**
1. `itertools.accumulate(..., initial=None)` — None now means “not given”, matching CPython (`cruntime.ail_it_accumulate`). Covered for constant, argument, list item, attribute, dict value.
2. `sorted` / `list.sort` with `key=` and `reverse=True` — key is now called in original input order, and once for a one-element list (`cruntime.ail_list_sort`).
3. Typed-path `itertools.groupby` — reuses the look-ahead key, so it calls the key exactly once per element instead of twice at group boundaries (`itlib.Groupby`).

**Remaining differences (not fixed, recorded in `DIFFERENCES.md`)**
- negative `r` for permutations/combinations/combinations_with_replacement returns `[]` instead of `ValueError`
- `enumerate` start `None`/float/str/list accepted and misread instead of `TypeError`
- `reversed` of dict/dict-view/bytearray is a runtime `TypeError`
- `groupby` grouper repr is `<object>` instead of `<itertools._grouper ...>`
- general-path `map`/`filter`/`zip`/`enumerate` over a library iterator hits `AIL internal error: iterator: unknown kind`
- `zip_longest` >2 iterables, `starmap` non-2-arity, and `zip(strict=True)` >2 iterables are refused by name

**Verification on final commit**
- `test_ail_fuzz8.py`: 4 tests, OK (new module registered in `ail_check.MODULES`)
- Required modules: `test_ail_genlib`, `test_ail_stdlib_batch3`, `test_ail_sort_keys`, `test_ail_int_sort`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 8/8 passed
- `python3 tools/update_manifest.py --check` — exit 0
- Probes `/tmp/probes/{p_acc_none,p_sort_rev_key,p_groupby_calls,p_sort_sources,p_groupby_sources}.py` — all 5 match CPython on both builds
[cost $0.20, turns 111]
