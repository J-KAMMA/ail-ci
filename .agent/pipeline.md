# job job-fuzz35-10230816  started 2026-10-22T23:17:36Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `1b69c4d` on `job-fuzz35-10230816`.

**Cause:** dynamic `list`/`dict` element types were settled by the first inserted tuple shape and reused for later insertions. `d={}; d[(1,2)]="a"; d[()]="e"` made `d[()]` return `"a"`, and the reverse order made `()` match every key or raised `IndexError: tuple index out of range`. Fixed by refusing a second, different tuple shape in one container (`tupcalls.py:fill`), so the default build falls back to the general path and matches CPython.

**Probes (23, `/tmp/probes/t01..t23`):** 22 matched CPython on both builds; `t08_wrongtypes.py` was refused by name on both builds for tuple concatenation/repetition with a wrong type (pre-existing, not silent). Covered concat, repetition incl. negative/zero/huge, mixed-type comparison TypeErrors, count/index windows, single-element/empty/nested tuples, hashing, dict keys, wrong types, dict/list insertion order, dict values, and values arriving through an argument, list item, attribute and dict value.

**Tests on final commit:** `test_ail_fuzz35`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest updated; `--check` passes.

Note: this export has no `DIFFERENCES.md` or `DEVLOG.md`, so no record files could be updated.
[cost $0.0000, opencode tokens {"total": 4489855, "input": 103399, "output": 12879, "reasoning": 11977, "cache.write": 0, "cache.read": 4361600}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `1b69c4d` (fuzz35)**

- Diff: `tupcalls.py:fill` now refuses a second, differing tuple shape in a dynamic list/dict/set, causing a default-build fallback; adds `test_ail_fuzz35.py`; updates manifest.
- 39 probes in `/tmp/rprobes` on HEAD and `/tmp/base`: every direct mixed-tuple-shape case now matches CPython on both builds (dict/list keys, values, `get`/`pop`/`setdefault`, assignment, insert/extend, aliasing, attribute/argument/dict-value sources, iteration, sets, slicing, empty/negative/zero/nested/wrong-type cases). Base still failed 11 of these (p01, p02, p07, p08, p11, p20, p25, p29, p31, p34, p35).
- C unchanged (`--debug-dir`) for non-feature programs and same-shape tuple programs: p22, p04, g00_000, g00_004, g00_016, g10_018, g10_026.
- Tests on HEAD: `test_ail_fuzz35`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass. Manifest `--check` exits 0. No `DIFFERENCES.md`/`DEVLOG.md` in this export.
- Speed: relevant gdev/generated C is byte-identical, so instruction counts are unchanged; `icount` itself could not run (`perf_event_open: Permission denied`).
- Report claims: commit/cause, tests, manifest, and absent records verified. The t08 “refused by name” claim is unverified (t08 not present); my equivalent wrong-type concat/repetition probes produce CPython-matching `TypeError` on both builds, not a compile refusal.

**Pre-existing (identical on base):**
- p12: a list of lists of different tuple shapes still exits 1 with `IndexError: tuple index out of range` (CPython prints `[[(1, 2)], [()]] 2`).
- p30: `xs += [()]` after `xs.append((1, 2))` still exits 1 with `IndexError` (CPython prints the list).
- p33: set-of-tuples repr ordering differs from CPython; both builds emit the same reordered set.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2008528, "input": 65451, "output": 11452, "reasoning": 20201, "cache.write": 0, "cache.read": 1911424}]

FINAL VERDICT: ACCEPT  2026-10-22T23:55:29Z
