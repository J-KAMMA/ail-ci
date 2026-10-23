# job job-fuzz62-10231420  started 2026-10-23T05:21:11Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Found and fixed a silent recursion bug:

- Recursive `@classmethod` calls passed the class object through the instance-to-class conversion, so later frames received the class name string. `cls.__class__.__name__` printed `str` instead of `type`; other shapes segfaulted.
- Fixed receiver handling in `cruntime.py:14309` and `pyboxed2.py:8062`.
- Added `test_ail_fuzz62.py` covering recursive/mutual classmethods, subclass receivers, and common recursion shapes; registered it and pinned the manifest.

Commits: `d948baa`, `63941d6`.

Verification: `test_ail_fuzz62` and `test_ail_safetynet` pass; manifest `--check` passes. Only `.agent/pipeline.md` remains untracked.
[cost $0.0000, opencode tokens {"total": 23271482, "input": 874705, "output": 146821, "reasoning": 1764, "cache.write": 0, "cache.read": 22248192}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fuzz62 — recursive classmethod receiver

**Change:** `_self_arg` now calls `ail_classmethod_receiver()` (cruntime.py:14309), which returns a class object unchanged and converts only instances via `->cls`. Correct and minimal.

**Probes (both builds, HEAD vs `/tmp/base`)**

| Probe | HEAD | Base |
|---|---|---|
| p17 `cls.__class__.__name__` at depth 1/2 | `type`, `type` | `str`, `NoneType` (silent wrong; fixed) |
| p9 recursive/mutual classmethod, subclass receivers | correct | exit 139 |
| p3 mutual classmethods with override | correct | exit 139 |
| p7 classmethod returning `cls()` on subclass | correct | `NoneType` not callable |
| p16 classmethod recursion depth 250 | correct | exit 139 |
| p8 negative/empty accumulation | correct | correct |
| p1/p12–p15 class object via alias, argument, list item, dict value, attribute | `AttributeError: 'type' object has no attribute ...` | identical |
| p10/p11 `cls.__name__` | `AttributeError` | identical |
| p4/p5/p6 tuple getitem, caught `RecursionError`, `class L(list)` | refused by name | same |

No failure on HEAD that is absent on base. No introduced defect.

**Pre-existing (identical on base):** class-object attribute/method lookup through a variable/list/dict/attribute/parameter; `cls.__name__`; `class L(list)`; tuple getitem; catching `RecursionError`.

**Note:** a non-feature program's `--debug-dir` C differs by 3 lines — the unused `static inline` helper in the OBJ2 runtime. Output and exit status are unchanged; no codegen semantics changed.

**Claims:** all verified — receiver fix at the stated locations; `str`/`type` silent result reproduced on base and fixed; segfault shapes reproduced; test covers recursive/mutual/subclass cases; manifest check passes; only `.agent/pipeline.md` untracked.

**Tests:** `test_ail_fuzz62`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`); `update_manifest.py --check` passes.

The helper is off the hot path (classmethod call sites only), so no speed impact.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1018331, "input": 115106, "output": 7208, "reasoning": 11921, "cache.write": 0, "cache.read": 884096}]

FINAL VERDICT: ACCEPT  2026-10-23T07:08:31Z
