# job job-fuzz44-10231200  started 2026-10-23T03:01:38Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Completed and committed as `618fb1f` on `job-fuzz44-10231200`.

- Fixed list mutators used as values: typed path now refuses by name instead of emitting void C calls; statement mutations stay typed, including struct-field lists.
- Added `test_ail_fuzz44.py`, DEVLOG entry, manifest/shard updates.
- All tests pass: `test_ail_fuzz44`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_list_ops`, `test_ail_scalar_list_mutations`, `test_ail_list_expression_extend`, `test_ail_fuzz_findings`; all probes match CPython on both builds.
- Working tree clean except untracked `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 8911909, "input": 284624, "output": 25129, "reasoning": 20908, "cache.write": 0, "cache.read": 8581248}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `618fb1f` — list mutation methods used as values**

**Diff read.** `_method` now refuses `append/clear/extend/reverse/sort` in expression position; `_stmt_inner` routes bare-name scalar-list statement calls through the typed emitter. Plus tests/manifest/DEVLOG.

**Probes** (in `/tmp/rprobes`, both builds via `cmp.sh`, compared to CPython):
- Isolated value forms: `p21_is_none_append`, `p23_{reverse,extend,sort,clear,remove,insert}_none` — HEAD matches CPython on general and default.
- Self-extend (int/float/str, annotated, slice/reversed sources), struct/dict/nested receivers: `p3,p6,p10` — match.
- remove-first-match/aliasing, copy vs slice, nested equality, cross-int/float equality, mutation during iteration: `p5,p11,p12,p27,p28` — match.
- Nested/tuple/bytes/handle receivers, class methods named append/reverse/sort, parameter lists, field statements: `p2b,p4,p13,p24,p25,p26` — match.
- No-mutator program C diff vs base via `--debug-dir`: `program.c` identical (only temp paths in `native_report.json`).

**Tests.** `test_ail_fuzz44` + `test_ail_safetynet` on HEAD: 2/2 pass (121 s). Manifest `--check` passes.

**Claims.**
- “Typed path refuses by name instead of emitting void C”: verified (`p14/p15/p16`: base default build exit 4, HEAD exit 0 + named note).
- “Statement mutations stay typed, including struct-field lists”: verified (`p24` with `AIL_NO_GENERAL=1` builds and prints `[1, 2, 3] [0.5, 1.5] ['b', 'a']`).
- “All probes/tests pass”: the named modules pass; `test_ail_files`, `test_ail_corpus_findings3`, list-op modules not re-run (marked unverified).
- Worker’s diagnosis is incomplete: the real silent case is `p21`: `a=[1,2]; print(a.append(3) is None)` → CPython/HEAD `True`, base default `False` (it was a silent wrong answer, not only a C compile failure).

**Speed.** `perf_event_open` is denied on this runner, so instruction counts could not be taken. The only C change for plain statements is dropping `(void)(...)` around the same calls (`p9_statements`), so no speed change is expected.

**Defect**
1. The added regression test does not cover the case the task asked for. Against base, `python3 -m unittest test_ail_fuzz44` gives **4/5 pass**; only the diagnostic-text test fails. Every correctness program in it contains a construct (`xs.clear()` with value use, dict-value extent) that forces the general path on base and masks the typed-path bug. An isolated probe such as `xs = [1,2]; print(xs.append(3) is None)` is expected to be `True`; base default prints `False`, HEAD prints `True`. The test module should include that isolated append/reverse/sort/extend case so it fails on base.

VERDICT: FIX

1. Add an isolated `is None` value-form case for `append`/`reverse`/`sort`/`extend` to `test_ail_fuzz44.py` (currently all its correctness programs pass on the base commit because an unrelated construct triggers the general path). Probe: `a=[1,2]; print(a.append(3) is None)` — expected `True`; base default build prints `False`; HEAD prints `True`.
[cost $0.0000, opencode tokens {"total": 3889010, "input": 82449, "output": 14090, "reasoning": 23639, "cache.write": 0, "cache.read": 3768832}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer defect and committed as `c3a5d06`.

- Added isolated `is None` value-form cases for `append`, `reverse`, `sort`, `extend` to `test_ail_fuzz44.py`.
- Confirmed against base: those 4 cases fail on the default build (`False` vs CPython `True`); on HEAD they pass.
- Probes in `/tmp/probes` (`p_append`, `p_reverse`, `p_sort`, `p_extend`, `p_clear`, `p_value_none`): all match CPython on both general and default builds.
- Required tests on final commit: `test_ail_fuzz44`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 31 tests, OK (1 skipped), 214 s.
- `tools/update_manifest.py --check` passes.
- DEVLOG entry added; no new compiler change or DIFFERENCES row.
[cost $0.0000, opencode tokens {"total": 362112, "input": 20405, "output": 3104, "reasoning": 3627, "cache.write": 0, "cache.read": 334976}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed `618fb1f` and `c3a5d06` (`git diff work..HEAD`).

**Probes** (`/tmp/rprobes`, `g` = general, `d` = default):
- Value-form isolation: `rv_iso_unannot`, `rv_iso_annot`, `rv_clear_value`, `rv_self_extend_value`, `rv_sort_kw_value` — HEAD `g`/`d` match CPython. On base `d` prints `False` for append/reverse/sort/extend/clear/self-extend on annotated lists; HEAD prints `True`. Fix confirmed.
- Statement forms: `rv_self_extend`, `rv_stmt_typed`, `rv_nested_typed_stmt`, `rv_tuple_stmt`, `rv_param_stmt`, `rv_param_reverse`, `rv_annot_iter`, `rv_extend_iterables` — HEAD `g`/`d` match; `--strict` builds and runs, so the typed statement path is retained.
- Receiver paths: `rv_attr_value`, `rv_attr_value_all`, `rv_item_value`, `rv_dict_value`, `rv_param_value`, `rv_handle_reverse/extend/clear/sort`, `rv_handle_dict`, `rv_value_receivers` — HEAD matches; these already matched on base.
- Remove/insert/iteration/equality: `rv_remove_insert_value`, `rv_value_types`, `rv_mutation_iter` — HEAD matches; no new difference.
- User class methods named `append`/`clear`/`reverse`/`extend`/`sort` used as values still build and run under `--strict` (`rv_user_method`).
- Unrelated code: `rv_plain`, `g00_000`, `g00_002` — `--debug-dir` `program.c` byte-identical HEAD vs `/tmp/base`.

Non-blocking observation: the refusal is keyed on any bare `Name` receiver, so `--strict` reports `print(d.clear())` as `list.clear() returns None`; base already refused `dict.clear` (different wording), and default `g`/`d` output is correct.

**Tests/checks:** `test_ail_fuzz44` ok 33.8s, `test_ail_safetynet` ok 119.1s, 0 failed; `tools/update_manifest.py --check` rc=0.

**Claims:** commit `c3a5d06`, four isolated cases added, base-fails/HEAD-passes, worker probe list on HEAD `g`/`d`, DEVLOG and no new DIFFERENCES row, manifest — verified. Test-count claim (31 tests across four modules) partially verified: only the two required review modules were rerun. Speed claim unverified: `perf_event_open` is denied in this runner; the change is compile-time dispatch only, with no runtime code change.

Pre-existing: none blocking.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2419794, "input": 148691, "output": 10328, "reasoning": 29351, "cache.write": 0, "cache.read": 2231424}]

FINAL VERDICT: ACCEPT  2026-10-23T04:23:48Z
