# job job-shdeps1-11060643  started 2026-11-05T21:44:18Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed all three review defects and committed as `3ca185a`.

**Probes (tool-level, re-run after fix)**
- `f1` `import a.b`: now modules `{a, a.b, entry}`, `entry → {a, a.b}`, rc=0.
- `f2v` `from . import CONST` in `pkg/__init__`: `pkg` eager `[]`, no self-edge, rc=0.
- `f6` `parents[99]`: rc=0, `dynamic_imports` entry with target null plus unresolved `entry: 4:nothing`.
- Fixture extended (no new files) to cover dotted imports and the package self-attribute case; added a unit test pinning the out-of-range guard.

**Tests**
- `test_ail_selfhost_deps`: 9/9 pass directly and via `par_check -j 2`.
- `test_ail_safetynet`: fails only at `S4_generators_gc` (truncated stdout), identical to the pre-existing baseline; no new failure.
- `update_manifest.py` then `--check`: rc=0.

**Graph unchanged:** eager 6 modules / 17,006 lines / 6 edges / 3 layers / 0 cycles; full 163 / 215,462 / 419 / 9 / 4 cycles; unresolved still the same 3 lines. Working tree clean except the pre-existing untracked `.agent/pipeline.md`.
[commandcode stop=end_turn turns=25 out_tokens=17383]

## review 0
[model commandcode/deepseek-v4.1-flash]
I've verified the three review defects against the current code, probed the boundaries the fix implies, and compared the real graph against the base worktree.

## What the change really does
`tools/selfhost_deps.py`: (a) `add()` now also records every resolvable parent package of a dotted import; (b) `add_from()` no longer falls through to `add(base)` when `base == module` (kills the `pkg→pkg` self-edge) and routes resolved submodules through `add()`; (c) `_path_static()` returns `None` for `ascend < 0` or `ascend > len(file_dir.parents)`, and `dynamic_imports()` yields a fifth field `lost` (literal module name) that `analyse_tree` records as an unresolved entry. Plus fixture and unit-test edits. Matches the report.

## Defects from review 1 (probes in /tmp/rprobes)
- `p1` (=f1) `import a.b`: HEAD gives modules `{a, a.b, entry}`, `entry eager ['a','a.b']`, rc 0. Base gave `{a.b, entry}`. **Fixed.**
- `p2` (=f2v) `CONST=1; from . import CONST` in `pkg/__init__`: HEAD `pkg eager []`, `self_loops []`. Base had `pkg eager ['pkg']`. **Fixed.**
- `p3` (=f6) `parents[99]`: HEAD rc 0, one `dynamic_imports` entry with `target: null`, `unresolved: [{'module':'entry','where':'4:nothing'}]`. Base: `IndexError`, rc 1. **Fixed.**

## New boundaries probed
- `p5` `import a.b.c` → `entry → [a, a.b, a.b.c]`; `p10` `from .. import x` in `pkg/sub/mod.py` → `pkg.sub.mod → [pkg, pkg.x]`, module set matches CPython's loaded `pkg*`. Correct.
- `p4` `from pkg import CONSTNAME` (attribute, not module) → `m → [pkg]`, unchanged from base. Correct.
- `p6` self-attribute in `pkg/sub/__init__` → no self-edge. `p8` `parents[0]` resolves to the file's dir. Correct.
- `p7` `parents[-1]` (valid in CPython, = filesystem root) is reported as `unresolved 4:nothing` — conservative and named, not a crash; base silently produced a bogus path. Minor, not blocking.
- Real graph: running the tool at HEAD vs `/tmp/base` on the same tree gives byte-identical JSON except `generated`/`base_commit` — no module, edge, layer, cycle or unresolved entry changed. Committed `lab/selfhost/deps.json` equals the HEAD run on the same fields.

## Report claims
- f1/f2v/f6 outcomes: **verified**. Fixture extension and new unit test: **verified** (7 files, no new ones). `update_manifest.py --check` rc 0: **verified**. Graph numbers `eager 6/17,006/6/3/0`, `full 163/215,462/419/9/4`, same 3 unresolved: **verified exactly**. Working tree clean except untracked `.agent/pipeline.md`: **verified**.
- `test_ail_selfhost_deps`: passes (9 tests). `test_ail_safetynet`: **false** as reported — it *passed* here (155 s), not failed at `S4_generators_gc`; the earlier failure was flaky. Benign.

## Pre-existing (identical on base, do not block)
- `p9` `import pkg` inside `pkg/__init__.py` still yields `pkg eager ['pkg']` and `self_loops ['pkg']` on both base and HEAD — same bug class as review defect 2, untouched by this change.
- `lab/selfhost/deps.json` `base_commit` is the parent commit `9644e14`; regenerating at HEAD writes `3ca185a` (no `origin/integ` here). Graph unaffected.

Speed: not measured — no compiler/runtime file is touched (tool-only change), so no hot path.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=20 out_tokens=16049]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T23:10:05Z
