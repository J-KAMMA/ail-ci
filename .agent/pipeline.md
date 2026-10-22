# job job-fuzz28-10230629  started 2026-10-22T21:30:33Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Commit `745ca79` on `job-fuzz28-10230629`.

**Fixed:** the general path silently dropped a computed class-body attribute read through the class (`C.ys` where `ys` is a comprehension), raising `AttributeError` after printing nothing. It now refuses that read by name at compile time with a targeted message. Instance reads, comprehension shadowing, and literal class attributes still match CPython.

**Probes:** 22 scoping programs in `/tmp/probes`. 18 matched CPython on both builds or were intended refusals; `p21`/`p24` (the first diffs) now refuse both builds; `p25` also refuses (CPython raises NameError). Probes covering values via alias, function argument, list item, dict value, or field still show the pre-existing general-path `AttributeError`; verified identical on the base worktree, so not caused by this change.

**Tests on final commit:** `test_ail_fuzz28`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass (`par_check.py -j 2`). Extra targeted checks: `test_ail_dunders`, `test_ail_typed_inherit`, `test_ail_fuzz3n`, `test_ail_globals`, `test_ail_nested_functions`, `test_ail_unbound`, `test_ail_builtin_shadowing` pass; `test_ail_fuzz1` fails only because `tools/difffuzz.py` is absent from this export (pre-existing).

`python3 tools/update_manifest.py --check` passes. No `DEVLOG`/`DIFFERENCES` files exist in this export, so no records were added.
[cost $0.0000, opencode tokens {"total": 8505747, "input": 147681, "output": 24470, "reasoning": 33692, "cache.write": 0, "cache.read": 8299904}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review — fuzz28: class-attribute read through the class**

Change: `pyboxed2.py` now raises a named `Unsupported` for a non-constant class attribute read through the class; new `test_ail_fuzz28.py`, `ail_check` registration, manifest updated.

**Probes (HEAD, both builds; base where a difference appeared)**
- `p1`/`p24` (`C.ys` comprehension): base raised runtime `AttributeError`; HEAD refuses by name on both builds. CPython prints the list.
- `p2`–`p5`, `p7`, `p9`: other computed class attrs, including via function call/inheritance — named refusal on HEAD; base raised runtime `AttributeError` (p7/p9 refuse earlier with pre-existing `name 'x' is not defined`).
- `p19` (read in dead `if False:`): base ran correctly, HEAD refuses by name — allowed named refusal.
- `p6`/`p17`: literal attributes, `None`, negatives — literal reads still match; `-2**63`/bytes remain pre-existing refusals.
- `p8`, `p10`: subclass override and duplicate assignment — match CPython on both builds.
- `p13`–`p18`: instance, list-item, dict-value, attribute, closure and literal reads — match CPython.
- `p11`/`p12`/worker `q_alias`/`q_attr`: class object through alias, argument, list, dict, attribute still gives the same pre-existing `AttributeError` on HEAD and base.
- `p20`: list class attr with `__init__`: default build works; forced general path refuses (named).
- `p21`: tuple class attr: default build prints `[1, 2]` instead of `(1, 2)` on both HEAD and base (pre-existing).

**Claims**
- Verified: silent `AttributeError` cause; named refusal on both builds for p21/p24/p25; instance/shadow/literal paths unchanged; alias/argument/list/dict/attribute differences pre-existing; 4/4 targeted tests pass (`-j 2`); `update_manifest.py --check` passes; no DEVLOG/DIFFERENCES files exist.
- Unverified: the extra targeted modules and the `test_ail_fuzz1`/`difffuzz.py` claim (not run).
- Nuance: the message mentions `bytes` though bytes literals are rejected earlier; dead-code reads now also refuse.

**Pre-existing:** `p6` int64 boundary literal, `p7`/`p9` class-body comprehension referencing a nonconstant class variable, `p11`/`p12`/`q_alias`/`q_attr` class-object aliasing, `p21` tuple class attr on the typed path.

**Speed:** no runtime code change; generated `program.c` is byte-identical HEAD vs base for feature-free `p16` and for constant-read `p18` on the general path.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1553880, "input": 56510, "output": 6892, "reasoning": 16430, "cache.write": 0, "cache.read": 1474048}]

FINAL VERDICT: ACCEPT  2026-10-22T22:07:26Z
