# job job-fuzz32-10230813  started 2026-10-22T23:14:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

Fixed one silent difference: a mixed-type display (`[0, 1, "a", None, [2, "b"]]`) was typed from its first non-None element, so `print` used the typed `list[int]` repr helper. Strings lost their quotes (`[0, 1, a]`), and a leading `str` element crashed with `TypeError: argument of type 'int' is not iterable`. Conflicting element types now leave the display untyped and use the general runtime’s recursive repr. Commit `92c6658`.

**Tests**
- 11 modules passed (`fuzz32`, `safetynet`, `files`, `corpus_findings3`, `tuples`, `list_ops`, `collections`, `nested_lists`, `sort_keys`, `int_sort`, `mixed_bounds`), 0 failures.
- Re-ran the 4 required modules on the final commit: 4 passed, 0 failed.
- `python3 tools/update_manifest.py --check` passes.

**Probes (`/tmp/probes`)**
- `p02_mapfilter`, `p11_fuzz32`, `p13_alias`, `q_hetero`, `q_list`: differed on base, now same on both builds.
- `p01`, `p03`, `p06`, `p07`, `p08`, `p14`, `q_mixnum`: same on both builds.
- `p04_partial`, `p05_return_func`, `p10_nested`: refused by name on both builds.
- `p09_wrongtype`: pre-existing difference only (`TypeError` operands reported in reverse order); identical on base.
- `p12_mixmap`: dict/list cases same; raw set order differs as the documented insertion-order difference (A2), also on base.

No `DEVLOG` or `DIFFERENCES.md` file exists in this export, so no record rows were added.
[cost $0.0000, opencode tokens {"total": 8607267, "input": 447613, "output": 15513, "reasoning": 18189, "cache.write": 0, "cache.read": 8125952}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review**

Change: `seq_type` now returns untyped for conflicting display element types (except int/float/bool mixes) and for `None` when no expected element type exists. Diff is confined to `tupexpr.py`, `ail_check.py`, new `test_ail_fuzz32.py`, and MANIFEST.

**Probes (HEAD, both general+default unless noted)**
- Fixed vs base: `p11_fuzz32`, `p13_alias`, `q_hetero`, `q_list`, `p02_mapfilter`. Base shows unquoted strings / `TypeError: argument of type 'int' is not iterable` (`["a",0,1]`); HEAD matches CPython. Verified.
- New probes matching CPython on HEAD: `p_boolint` ([2,True], [True,2], int/float), `p_mixed_ops`, `p_hof_mixed`, `p_homog`, `p_none_mix`, `p_mixed_use`, `p_repr_paths` (str/repr/f-string/format, bytes, nan/inf, concat/repeat), `p_alias_iter`, `p_nested_mix`, `p_hole_append`, `p_mix_mut` (append/insert/extend/pop/sort/assign), `p_tuple_holder`, `p_dict_holder`, `p_set_ops`, `p_set_tuple_none`, `p_dict_tuple`, `p_container_elems`, `p_ann_mix`/`p_ann_mix2`/`p_ann_none`, `p_leadstr`.
- `p_matrix2`: 728 generated display lines (all list/dict pairs and triples over int/bool/float/str/bytes/None/list/tuple, mixed keys and values). HEAD matches CPython in both builds.
- Refusals by name, both builds: `p04_partial`, `p05_return_func`, `p10_nested`.

**Pre-existing (identical on `/tmp/base`)**
- `2**70` in any display: runtime `integer overflow`.
- `sorted`/`map` TypeError operand ordering (`p09_wrongtype`).
- Raw set iteration order for string/tuple elements (A2); reproduced nondeterministically on base too.
- `import functools` + `partial` on a lambda: `AttributeError: 'Lambda' object has no attribute 'lineno'`.

**Tests**
- `test_ail_fuzz32`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4/4 pass.
- Worker's other 7 modules (`tuples`, `list_ops`, `collections`, `nested_lists`, `sort_keys`, `int_sort`, `mixed_bounds`): 7/7 pass.
- `update_manifest.py --check`: exit 0.

**Speed / unchanged C**
- `--debug-dir` generated C is byte-identical to base for `g00_000`, `g10_000`, and lambda/HOF gdev `g00_022`, `g01_002`; only `native_report.json` differs. No instruction-count change for programs not using mixed displays.

**Claims**
- Mixed-display bug fixed; leading-str crash confirmed on base: verified.
- 11 test modules pass: verified.
- 4 required modules pass on final commit: verified.
- Manifest check, no DEVLOG/DIFFERENCES file: verified.
- Probe classifications p02/p11/p13/q_hetero/q_list fixed, p04/p05/p10 refused, p09/p12 pre-existing: verified. p01/p06/p07 not re-run (unverified, non-blocking).
- No blocking wrong output, crash, or regression attributable to the change found.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2619695, "input": 160158, "output": 28412, "reasoning": 5909, "cache.write": 0, "cache.read": 2425216}]

FINAL VERDICT: ACCEPT  2026-10-23T00:03:52Z
