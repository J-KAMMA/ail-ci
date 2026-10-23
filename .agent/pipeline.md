# job job-fuzz87-10231558  started 2026-10-23T06:59:46Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

**First wrong program:** `p02_default_capture.py` — a nested `def make(x, acc=[])` / `def tally(k, seen={})` gave a fresh mutable default per call (`[1] [2] [3]`, `{'a': 1} {'b': 1} {'a': 1}`) instead of CPython's shared object (`[1, 2, 3] ...`). Cause: the general path substitutes a deep copy of a nested def's default at each call site.

**Fix:** refuse a nested def with a literal mutable default (list/dict/set, including inside tuples) by name: `a nested def make with a mutable default (CPython evaluates the default once, when the def runs)`. Top-level mutable defaults remain supported; immutable nested defaults and late binding still match.

**Probes** (all under `/tmp/probes/`, both builds):
- SAME: p01 lambda late binding, p02a/p02b top-level defaults, p04 mutable closure, p05 aliasing, safe nested defaults in new test.
- REFUSED by name: p02/p02c/p02d nested mutable defaults, p03/p09 nonlocal counters, p06/p07/p08/p10 unsupported shapes. No silent stdout differences remained.

**Tests on final commit `386e944`:**
`test_ail_fuzz87`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` passes; CI shard updated.

Note: this export contains no `DIFFERENCES.md` or `DEVLOG.md`, so no record rows were available to update. Untracked `.agent/pipeline.md` was left untouched.
[cost $0.0000, opencode tokens {"total": 4676415, "input": 269339, "output": 11260, "reasoning": 9384, "cache.write": 0, "cache.read": 4386432}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change reviewed:** `7b25bcd` adds `_is_mutable_literal_default` and refuses nested defs whose literal default builds a list/dict/set (including inside tuples) in `pyboxed2._register_nested`. Adds `test_ail_fuzz87`, manifest hashes, CI shard.

**Probes (HEAD vs base, both builds):**
- `p01/p02/p03/p13/p26` nested list/dict/set/tuple/kw-only mutable defaults: base silently wrong (`[1] [2] [3]`), HEAD refused by name (`mutable default`). Fix verified.
- `p02a/p02b/p09` top-level mutable defaults: SAME on both. Claim verified.
- `p16/p20/p21` immutable nested defaults, `def`/default late binding: SAME on both. Claim verified.
- `p04/p05/p08` mutable closures, aliasing, dict state: SAME on both.
- `p10` no-feature and `p16` nested-immutable: `--debug-dir` `program.c` byte-identical to base.
- `p04/p22` non-literal or attribute-seeded defaults: generic named refusal, identical on base.
- `p06` bare lambda-in-loop/comprehension late binding: runtime `NameError` vs CPython `[2, 2, 2]`, identical on base (pre-existing; their `p01`, which also contains a while loop, is SAME).
- `p07` nonlocal counters, `p11` module-level def in `if`, `p25` local class: named refusals identical on base.

**Tests:** `test_ail_fuzz87`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass on `386e944` (4 modules, 0 failed). `update_manifest.py --check` passes. No `DIFFERENCES.md`/`DEVLOG.md` in the tree, as reported.

**Speed:** no generated-code change for unaffected programs; compile-time check only, no hot-path impact.

**Pre-existing (base-identical, non-blocking):** bare lambda loop/comprehension closure over loop variable errors; nonlocal-counter, nested-def-in-loop/class-in-function and generic nested-default refusals.

All worker claims checked out; no defect attributable to this change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1866478, "input": 103372, "output": 20061, "reasoning": 6341, "cache.write": 0, "cache.read": 1736704}]

FINAL VERDICT: ACCEPT  2026-10-23T07:41:46Z
