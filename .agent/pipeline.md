# job job-fuzz83-10231554  started 2026-10-23T06:55:27Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

Found and fixed one silent wrong answer: `reversed()` of a generator expression.

- CPython raises `TypeError`; AIL materialised the generator expression as a list and reversed it. Empty gave `[]`; non-empty gave reversed values. The same wrong result travelled through a name, argument, list item, attribute, dict value, alias and return value.
- Fix: materialised generator-expression lists carry `from_generator`; `ail_iter_reversed` raises CPython’s `TypeError`. `list(g)`, `sorted(g)` and list comprehensions stay reversible.
- Files: `cruntime.py`, `pyboxed2.py`, `pyboxed.py` (v1), `test_ail_fuzz83.py`, `ail_check.py`, `MANIFEST.json`.

**Self-check probes** (`bash ~/tools/cmp.sh`, both builds): p1, p12, p36, p38–p51 — all same stdout as CPython. These covered empty/non-empty, direct/name/argument/list-item/attribute/dict-value/alias/return paths, list comps, `list()`, `sorted()`, `tuple()`, loops, caught TypeError, `key=len` stability, `reverse=`, dict keys/values, ranges, nesting, and a user-defined `reversed` shadow.

**Other differences seen (pre-existing, non-silent):** `reversed(dict)` and `reversed(bytes/bytearray)` raise runtime TypeError where CPython supports them; non-BMP strings and non-constant `reverse=` are refused by name.

**Tests:** `test_ail_fuzz83`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_builtin_shadowing` — 5 modules, 0 failed on final commit. `update_manifest.py --check` rc 0.

Committed as `733e7db` (plus superseded intermediate `74feb81`); no push. No `DEVLOG`/`DIFFERENCES` files exist in this worktree, so none were added.
[cost $0.0000, opencode tokens {"total": 6500024, "input": 540545, "output": 26301, "reasoning": 20346, "cache.write": 0, "cache.read": 5912832}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Change:** generator-expression lists get a `from_generator` flag; `ail_iter_reversed` raises CPython's `TypeError`. Both front ends (`pyboxed.py`, `pyboxed2.py`), runtime, test, manifest.

**Core fix verified (both builds):**
- BASE `p_direct` printed `[3, 2, 1] / [] / [4, 2, 0]`; HEAD raises `TypeError: 'generator' object is not reversible` exactly as CPython.
- HEAD matches CPython for `list(g)`, `sorted(g)`, `tuple(g)`, list comprehensions, `[*g]`, `+=`/`extend`, aliases, returns, list items, attributes, dict values (`p_copy`, `p_alias`, `p_contexts`, `p_slots`, `p_star`, `p_operators`).
- Plain sorted/reversed over str/tuple/dict/range/list/empty, `key=len` stability and `reverse=` match (`p_plain`, `p_stable`).
- Programs without genexpr: default-build `program.c` is byte-identical to base.

**Claims:** fix, affected paths, reversibility of `list()/sorted()/comprehension`, file list, 5 test modules, and `update_manifest.py --check` rc 0 all verified. Hidden probes `p1,p12,p36,p38–p51` unverified (not present). No DEVLOG/DIFFERENCES files exist, as reported.

**Pre-existing (identical on `/tmp/base`, non-blocking):**
- `list(reversed((x, x) for x in [1, 2, 3]))` still silently prints `[(3, 3), (2, 2), (1, 1)]` on both HEAD and base; the tuple pass hoists the genexpr to a plain list, bypassing the mark. Same root cause, not covered by this fix.
- `reversed(gen())` (generator function) message is `'instance' object is not reversible` vs CPython `'generator' object...` (`p_genfunc`, `p_loop_iter`).
- `reversed(dict/bytes/bytearray)` unsupported (`p_other`).

**Tests:** `test_ail_fuzz83`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_builtin_shadowing` — 0 failed.
**Speed:** `icount` could not run (`perf_event_open: Permission denied`); change is one branch plus a padded header byte, no hot-path loop.

**Defects caused by the change:** none.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1751945, "input": 156574, "output": 8030, "reasoning": 18189, "cache.write": 0, "cache.read": 1569152}]

FINAL VERDICT: ACCEPT  2026-10-23T07:37:43Z
