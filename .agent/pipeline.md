# job job-shdeps1-11060318  started 2026-11-05T18:19:48Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Summary with numbers:

**Graph (measured, nothing compiled or edited):**
- Full graph (eager + lazy): **163 modules, 215,462 lines, 417 edges, 9 layers, 6 cycles** (sizes 4, 13, 2, 2, 40, 5 = 66 modules in cycles)
- Eager graph (top-level imports only): **5 modules, 16,234 lines, 5 edges, 3 layers, 0 cycles**
- Largest cycle: 40 modules incl. `ail_syntax`, `pyfunc`, `pyc`, `ir.driver`, `cruntime`; entry itself is in the 5-module `ail_chatgpt`/`ail_server` cycle
- Top in-degree: `ir` 19, `ir.ir` 18, `iterlower` 17, `stdlib4` 17, `pyfront` 15
- First 20 leaf-first: none accepted by the typed-path census (its 21 accepted functions live in 6 deeper prelude files)

**Stop-rule checks:** 3 of ~963 import targets unresolved (0.3%): `ail_chatgpt.py:6311/6314/6318` import nonexistent `ail_http_*`. 20 dynamic import sites listed in `deps.json` and `DEPS.md`; none hides an edge — resolved targets are already reachable, the rest are stdlib or static-import fallbacks (`ail_server` line 374's tuple loop targets are all present).

**Files:** `tools/selfhost_deps.py`, `lab/selfhost/deps.json`, `lab/selfhost/DEPS.md`, 7-file `lab/selfhost/deps_fixture/`, `AIL_CURRENT/test_ail_selfhost_deps.py`, `AIL_CURRENT/tests.d/test_ail_selfhost_deps.txt`, plus the two manifest shards. `git diff --stat HEAD~2` shows only those.

**Tests on final commit:** new test OK (6 tests); `test_ail_files` OK (1 skip); `test_ail_corpus_findings3` OK; `test_ail_safetynet` OK when run without the shell's 1.5 GB `ulimit` — under the cap it OOM-stops the heavy `S4_generators_gc` case (pre-existing, none of my files are compiler sources). Two commits on `job-shdeps1-11060318`; no push, per the job rules, so the 20 shard checks were not run.
[commandcode stop=end_turn turns=58 out_tokens=39492]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: shdeps1 (import graph of the compiler front end)

**What the change really does:** adds `tools/selfhost_deps.py` (an `ast`-only import-graph + Tarjan/SCC + layering tool), its `deps.json`/`DEPS.md` output, a 7-file fixture, a fixture-pinned test registered in `tests.d/`, and two manifest shards. No compiler or runtime file is touched. Matches the report's description.

**Probes** (in `/tmp/rprobes/`, base at `/tmp/base` = 9326971):
- `p1.py` (list slice after append, dict value, arg) → both builds match CPython; generated C byte-identical to base (4848 lines).
- `p2.py` (`2**62*4`) → named int64 refusal on both HEAD and base → pre-existing.
- `g1/` tool probes: empty file, self-import, `from . import *`, relative import past root, class-body import, non-UTF8 bytes, nested `try` import, import-time `if __name__ == '__main__'` block → no crash; self-loops, unresolved and layers reported sanely.
- Full independent `ast` cross-check of all 163 modules (`import a.b` → parent package inits): 0 missing, 0 spurious edges.
- Simulated the two dropped dynamic edges → cycle count and 86/163 order positions change (the defect below).

**Claims checked:** counts 163/215,462/417/9/6, eager 5/16,234/5/3/0, top in-degree (`ir` 19, `ir.ir` 18, `iterlower` 17, `stdlib4` 17, `pyfront` 15), census (21 accepted in exactly the 6 named files, none in the first 20), 3 unresolved at `ail_chatgpt.py:6311/6314/6318`, 425+535+3 = 963, "no self-loops", `update_manifest.py --check` rc=0, `git diff --stat` = only the 14 allowed files, 2 commits, no push — all **verified**. `test_ail_selfhost_deps` runs 6/6 OK. "None of the 20 dynamic sites hides an edge" is **false** (below). `test_ail_files`/`test_ail_corpus_findings3` not re-run (**unverified**). `test_ail_safetynet` fails at `S4_generators_gc` under the 1.5 GB cap — the identical failure occurs on `/tmp/base` (130 s), so **pre-existing**.

**Defects:**
1. Two real import-time edges are dropped, so the headline cycle count is wrong. `tools/selfhost_deps.py` follows `spec_from_file_location` sites elsewhere but `_path_static` cannot evaluate `.resolve().parents[2]`, so the `ail_syntax` fallbacks at `jsonlib.py:633` and `stdlib4.py:58` produce no edge, and `DEPS.md` labels both "already imported statically" — neither file imports `ail_syntax` (0 static imports, only `sys.modules.get` + load-by-path).
   - Probe: add `jsonlib→ail_syntax` and `stdlib4→ail_syntax` to the JSON's own edge set and re-run `analyse()`.
   - Expected (tool's stated policy): cycles `[2, 2, 60, 5]` = **4**; layer sizes `62, 22, 7, 3, 60, 2, 1, 1, 5`.
   - Actual in `deps.json`/`DEPS.md`: cycles `[4, 13, 2, 2, 40, 5]` = **6**; layer sizes `62, 26, 20, 6, 40, 2, 1, 1, 5`; 20 modules sit up to 3 layers higher than they should, and 86 of the 163 leaf-first positions change.
2. Minor: the eager graph is documented as "what runs at import time", but imports under module-level `if`/`try`/`class` bodies are binned lazy; `ail_chatgpt.py:8` (`if __name__ == "__main__": import ail_server`) executes on the documented `compile` invocation, so the real load-time graph is 6 modules / 17,006 lines, not 5 / 16,234.

**Pre-existing:** `p2.py` int64 overflow refusal; `test_ail_safetynet` `S4_generators_gc` failure under `ulimit -v 1500000` (same on base).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, CI shards (not run per instructions).

VERDICT: FIX

1. `tools/selfhost_deps.py` drops the two `sys.modules`/load-by-path dependencies on `ail_syntax` (`AIL_CURRENT/python/pkg-v12/jsonlib.py:627-635`, `stdlib4.py:54-60`) because `_path_static` cannot parse `Path(__file__).resolve().parents[2]`, and `DEPS.md` wrongly calls them "already imported statically". Probe: re-run `analyse()` on `deps.json`'s edge set plus `jsonlib→ail_syntax` and `stdlib4→ail_syntax`. Expected: 4 cycles (`2,2,60,5`), layer sizes `62,22,7,3,60,2,1,1,5`. Actual: 6 cycles (`4,13,2,2,40,5`), layer sizes `62,26,20,6,40,2,1,1,5`, 20 modules mislayered and 86/163 leaf-first positions shifted.
[commandcode stop=end_turn turns=40 out_tokens=29382]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Done. Fixed both review defects, regenerated the report/JSON, added regression tests, and committed (`6cf41f6`).

**Fixes**
1. **Dropped dynamic edges.** `tools/selfhost_deps.py` now evaluates `Path(__file__).resolve().parents[N] / 'x.py'` (and `pathlib.Path`), plus a preceding `name = ...` assignment, so the `ail_syntax` load-by-path fallbacks at `jsonlib.py:633` and `stdlib4.py:58` resolve. Both edges are now in `deps.json`.
2. **Eager graph scope.** Imports in module-level `if`/`try`/`with`/`class` bodies now count as eager; only function/lambda bodies are lazy. This includes `ail_server` via `ail_chatgpt.py`'s `__main__` guard.

**Result vs. review expectation**
- Full: 163 modules, 215,462 lines, 419 edges, 9 layers, cycles `[2, 2, 60, 5]` (was `[4,13,2,2,40,5]`), layer sizes `62,22,7,3,60,2,1,1,5` ✓
- Eager: 6 modules, 17,006 lines (was 5 / 16,234) ✓
- Edge diff vs. previous commit: exactly `+jsonlib→ail_syntax`, `+stdlib4→ail_syntax`; nothing removed.
- `DEPS.md` corrected (counts, cycles, layer sizes, dynamic-import prose) and `base_commit` pinned to the export `9326971`.

**Tests (final commit)**
- `test_ail_selfhost_deps`: 8/8 OK (added 2 path-resolution regressions)
- `test_ail_files`: 18 OK (1 skipped)
- `test_ail_corpus_findings3`: 2 OK
- `test_ail_safetynet`: fails at `S4_generators_gc` under `ulimit -v 1500000` (truncated output) — same pre-existing failure the reviewer reproduced on base; no compiler/runtime files were touched.
- `update_manifest.py --check` rc=0; `git diff --stat 9326971` shows only the 14 permitted files. Not pushed (push is forbidden).
[commandcode stop=end_turn turns=46 out_tokens=30794]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: shdeps1 dependency-graph tool

**What the change really does:** adds an offline `ast`-only import-graph tool (`tools/selfhost_deps.py`), its generated JSON/report, a 7-file fixture with a test, and manifest entries. No compiler/runtime file is touched, nothing is compiled. That matches the report.

**Verification**
- Re-ran the tool: output matches `lab/selfhost/deps.json` exactly except `base_commit` (fresh run writes `6cf41f6` = HEAD, not the recorded export `9326971`; `origin/integ` is absent in this checkout). Not a graph error, but `Reproduce: python3 tools/selfhost_deps.py` does not reproduce that field.
- Captured numbers all verified: full 163 modules / 215,462 lines / 419 edges / 9 layers / cycles `[2,2,60,5]`; eager 6 / 17,006 / 6 edges / 3 layers / no cycles; layer sizes `62,22,7,3,60,2,1,1,5`; `ail_syntax` 5,811 lines; 20 dynamic imports, 16 with targets; 3 unresolved lines are real missing modules.
- Wrote an independent scanner: edge sets and eager/lazy classification agree on all 153 statically reachable modules (only the intentional dynamic edges differ). Independent Kosaraju/Kahn check reproduces every `layer_full` and the four cycle sizes.
- Cycle-merge claim verified: dropping the two `ail_syntax` dynamic edges gives cycles `[2,2,4,5,13,40]`.
- In-degree top-15, census (21 accepted in exactly the six named files), and "none of the first 20 accepted" verified.
- `test_ail_selfhost_deps` passes (`par_check -j 2`). `update_manifest.py --check` rc=0; diff limited to the 14 permitted files.
- `test_ail_safetynet` fails on HEAD at `S4_generators_gc` (truncated stdout) and fails identically on `/tmp/base` → **pre-existing**.

**Probes (tool boundaries, /tmp/rprobes)**
- `f5`: imports in module-level `class`/`try` bodies eager, in a function lazy — correct (the scope fix works).
- `f3`: `import alpha as al`, `from pkg import leaf as lf` — correct.
- `f1` (`import a.b`, both files exist) — CPython loads `a` and `a.b`; tool lists only `a.b`, omitting module `a`.
- `f4` (`import pkg.mod`) — `pkg/__init__.py` omitted for the same reason.
- `f2v` (`pkg/__init__.py`: `CONST = 1` then `from . import CONST`) — CPython imports cleanly; tool reports `pkg eager ['pkg']`, a spurious self-edge.
- `f6` (`Path(__file__).resolve().parents[99] / 'nothing.py'`) — tool exits with an uncaught `IndexError` traceback instead of an unresolved entry.

Neither resolution bug changes the current real numbers (no front-end module uses `import pkg.sub`; every relative import names a submodule), but both are wrong graphs on valid input, and the fixture does not cover either.

**Verdict defects**
1. Dotted import drops the parent package. Probe `/tmp/rprobes/f1/entry.py` = `import a.b`, with `a/__init__.py`, `a/b.py`. CPython executes `a/__init__.py`, so `a` is reachable. Expected modules `{a, a.b, entry}` with `entry→a`; actual `{a.b, entry}`.
2. `from . import NAME` in a package's own `__init__` creates a self-loop. Probe `/tmp/rprobes/f2v` → expected `pkg` eager `[]`; actual `pkg` eager `['pkg']` (a non-existent edge, and `self_loops` would report it).
3. (Minor) `_path_static` crashes on an out-of-range `parents[N]`. Probe `/tmp/rprobes/f6/entry.py` → expected an unresolved `nothing` entry; actual `IndexError`, rc=1.

**Unverified:** `test_ail_files` and `test_ail_corpus_findings3` (not re-run per review instructions); CI status (worker says not pushed). Speed not measured — no compiler/runtime code path is touched.

VERDICT: FIX
1. `import a.b` omits reachable parent package `a` (probe `/tmp/rprobes/f1`: expected modules `a`, `a.b`, `entry`; actual `a.b`, `entry`).
2. `from . import NAME` in `pkg/__init__.py` yields a spurious `pkg→pkg` edge (probe `/tmp/rprobes/f2v`: expected `pkg` eager `[]`; actual `['pkg']`).
3. Out-of-range `parents[N]` in `spec_from_file_location` raises `IndexError` instead of an unresolved target (probe `/tmp/rprobes/f6`: expected unresolved entry/rc=0; actual traceback, rc=1).
[commandcode stop=end_turn turns=52 out_tokens=43704]

FINAL VERDICT: FIX  2026-11-05T19:34:22Z
