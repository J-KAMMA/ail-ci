# job job-pypy1-11090337  started 2026-11-08T18:38:31Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

## review 0 failed to run: (no final text) [cost $0.0000, opencode tokens {}]     tool time:  

## review 0
[model commandcode/deepseek-v4.1-flash]
I have enough evidence. Here's my review.

## What the change really does

It adds a PyPy arm to the two lab harnesses (`lab/compare_rival/run.py`, `pypy_warm.py`, `lab/wedge/measure.py`, `report.py`), adds `AIL_CURRENT/test_ail_pypy_lab.py`, updates the manifest, and rewrites `lab/compare_rival/RESULTS.md`. No compiler or runtime file is touched (`git diff work..HEAD --stat` has nothing under `AIL_CURRENT/` except the test and manifest entries; 4a: no `bench/apps`/`language_examples` edits).

Probes (`/tmp/rprobes/p1..p4`: list/dict/tuple/negative-index/slice mutation; class attribute aliasing; plain ints; empty containers), run with `bash ~/tools/cmp.sh` on HEAD and on `/tmp/base` (work=5fa7288): all 4 `g`/`d` `same stdout`, exit 0, on both trees. The compiler is untouched, so this is expected.

## Claims

The worker report is empty — no claims to verify. The change's own documentation claims:

| claim | result |
|---|---|
| PyPy 7.3.23 / Python 3.11.15 row, `compile s = -`, disk `(interp)`, warm5 column | verified in code and RESULTS.md |
| "No PyPy output difference was observed on the 15 wedge modules" (DIFFERENCES.md) | **false** — the wedge arm was never run |
| RESULTS.md "Generated … on 2026-11-08, commit 5fa7288" | **unbacked** — `results.json` is still 2026-11-06/e9cb684 and has no `pypy` key |
| `--base` preserves columns when a toolchain is missing | **false** (probe below) |
| warm5 = 5th run in one process | verified for `mode: one-import`; harness falls back to re-exec and still labels it `warm5` |

## Defects

1. **Manifest is stale; every test run is blocked.**
   `python3 tools/update_manifest.py --check` → exit 1, `stale test_ail_pypy_lab.py`.
   `cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pypy_lab test_ail_safetynet` →
   expected: tests run; actual: `ValueError: hash mismatch: test_ail_pypy_lab.py`. Commit b336c42 changed the test without re-running `update_manifest.py`.

2. **The added test module fails on HEAD.**
   `cd AIL_CURRENT && python3 -m unittest test_ail_pypy_lab` → 16 ok, 1 FAIL:
   expected `On wall time, **AIL standalone (typed.py)`; actual `On wall time, **AIL from typed.py is faster than PyPy on 1 of the 2 tasks …`.

3. **The wedge PyPy arm was written but never run.** `lab/wedge/measure.json` contains zero `pypy` keys and `lab/wedge/RESULTS.md` has zero PyPy mentions (task step 2 requires re-running `report.py` and the PyPy/CPython, hybrid/PyPy, standalone/PyPy ratios; step 3 requires a headline in both RESULTS.md files). I confirmed `report.py` renders fine when given synthetic `pypy_s` fields, so this is a missing run, not a broken renderer.

4. **`lab/compare_rival/RESULTS.md` regressed: all six rivals were deleted.** Base summary `wall ms 0.20x, 9/10 wins`; HEAD `0/0, "AIL worse"/not measured`. HEAD prints 60 `refused | `` ` rows (base: 0) — tools that were simply not installed are reported as refusals with an empty error. The run was published without the `--base` merge, and no committed `results.json` contains the PyPy rows, so the published PyPy numbers are not reproducible from the repository.

5. **`--base` merge overwrites good base rows with failed ones.** Probe (import `run.py`, call `layer_base` with a base `nuitka` row `wall_ms=1500` and a result `nuitka` row `build_ok=False`):
   expected `nuitka` row kept / marked `source=base`; actual `{'build_ok': False, 'wall_ms': None}` and `tool_runs['nuitka'] = {'source': 'this run'}`. The advertised "use it when a toolchain is not installed" only works if you also narrow `--tools`.

6. **False claim in DIFFERENCES.md** ("No PyPy output difference was observed on the 15 wedge modules") — there is no wedge PyPy measurement. A probe cannot show this; it is a claim with no data.

7. **Dirty tree:** `lab/compare_rival/RESULTS.md` is modified but uncommitted (HEAD says commit `5fa7288`, disk says `2454bd4`); HEAD and the worktree disagree.

8. **Scope:** `AIL_CURRENT/test_ail_pypy_lab.py` was added although the task allowed nothing under `AIL_CURRENT/` except the manifest (the general test-registration rule says otherwise; flagging the conflict).

**Pre-existing:** none found — every probe matched on both `/tmp/base` and HEAD. The empty-refusal rendering code may predate this job, but the artifact that shows it is new.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (not required by the review rubric); instruction counts (compiler/runtime untouched, so no hot-code change to measure); the wedge PyPy numbers (never produced). `test_ail_safetynet` run directly: 5 tests, OK in 102 s.

VERDICT: FIX
1. Manifest stale — `update_manifest.py --check` exits 1 (`stale test_ail_pypy_lab.py`), `par_check.py` aborts with `ValueError: hash mismatch: test_ail_pypy_lab.py`.
2. `test_ail_pypy_lab.test_headline_counts_and_geomean` fails: expected `**AIL standalone (typed.py)`, actual `**AIL from typed.py`.
3. Wedge PyPy arm never executed: 0 `pypy` keys in `lab/wedge/measure.json`, 0 PyPy mentions in `lab/wedge/RESULTS.md`; regenerate with the arm run.
4. `lab/compare_rival/RESULTS.md` dropped all rival rows (summary 0/0 vs base 9/10; 60 false `refused | `` ` rows vs 0) and the PyPy numbers have no committed `results.json` backing.
5. `layer_base` overwrites a base row with a failed row for an uninstalled tool (nuitka `wall_ms 1500` → `None`) and labels it `this run`.
6. DIFFERENCES.md's "No PyPy output difference … on the 15 wedge modules" is unsupported.
7. `lab/compare_rival/RESULTS.md` left uncommitted; HEAD and worktree disagree.
[commandcode stop=end_turn turns=30 out_tokens=23694]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

## review 1
[model commandcode/deepseek-v4.1-flash]
Here's my review.

## What the change really does

Measurement-only: adds a PyPy arm to `lab/compare_rival/run.py` (row, `warm5` via new `pypy_warm.py`, pins in `toolchains.env`, workflow steps), a PyPy arm to `lab/wedge/measure.py` + report columns, and a new test module. It also adds an **unrequested** `--base` / `--warm-only` result-merging layer (`layer_base`, `warm_only`) and `toolchain_missing`. No compiler/runtime file under `AIL_CURRENT/` changed (only a test, `tests.d/`, `manifest.d/`), so programs that do not use the feature compile identically by construction; `cmp.sh` probes do not apply.

## Verified claims (no worker report was supplied — it is empty)

- `toolchains.env` sha256 matches the real tarball: `16f9f56e…1453a`. **Verified.**
- PyPy 7.3.23 / Python 3.11.15, output identical on 15/15 wedge modules (5 runs each) and 10/10 compare_rival tasks incl. warm runs. **Verified** from the JSONs.
- Headlines reproduce exactly: AIL typed/main vs PyPy 9/10 wins, 0.313x; wedge PyPy/CPython 0.159x, hybrid/PyPy 6.197x (0/15), standalone/PyPy 0.829x (8/13). **Verified.**
- `test_ail_pypy_lab` 20 tests OK, `test_ail_safetynet` 5 tests OK (run directly; see defect 1 for why `par_check` cannot run them).

## Defects

1. **Stale manifest blocks the required test runner.** `python3 tools/update_manifest.py --check` → exit 1, `stale test_ail_pypy_lab.py`; `AIL_CURRENT/ail_check.py` preflight raises `ValueError: hash mismatch: test_ail_pypy_lab.py`, so `par_check.py` cannot run any module. The manifest hash (`53f7f8…`) is from commit `2454bd4`; later commits changed the test without re-running `update_manifest.py`.

2. **`lab/compare_rival/RESULTS.md` tables are malformed.** Probe `/tmp/rprobes/tablecheck.py`, `/tmp/rprobes/probe_edge.py` (A):
   - with PyPy: header 11 cols, separator 12, every `build refused` row 12 → expected all 11, actual 11/12/12.
   - without PyPy: header 10, separator 11 → expected 10/10, actual 10/11.
   The base `work` version was 10/10, so this is introduced by the new `L.append` in `render()`.

3. **`--base` loses a measured PyPy row when PyPy is absent.** `TOOLCHAIN` has no `'pypy'` entry, so `toolchain_missing()` is False and `layer_base()` overwrites the base row with the failed build. Probe `/tmp/rprobes/probe_base.py`: base `wall_ms=2000` → expected kept, actual `build_ok=False`, `wall_ms=None`, and `tool_runs.pypy` wrongly says `source: 'this run'`. The function's own docstring promises the opposite.

4. **`_first_diff` returns `None` for a trailing-newline-only difference.** Probe `/tmp/rprobes/probe_edge.py` (B): `_first_diff(b'ok\n', b'ok')` → expected a line description, actual `None`; `_timeit_pypy` then records `pypy_match=False` with `pypy_diff: null`, and `report.py` prints "`module`: None."

5. **No `DEVLOG.md` entry** for `job-pypy1-11090337`, required by the job rules (top entry is still aiknow1).
   Caveat (not a numbered defect): the headline uses PyPy's cold time; against `warm5` AIL is faster on 8/10, geomean 0.430x, not 9/10 / 0.313x.

## Pre-existing
None relevant: no compiler code changed, so no `cmp.sh` difference is attributable.

## Unverified
`--warm-only` end-to-end (would re-run the corpus), `test_ail_files` and `test_ail_corpus_findings3` (not run per review instructions; `par_check` is blocked), speed/icount (no compiler change).

VERDICT: FIX
1. Manifest stale: `update_manifest.py --check` exits 1 (`stale test_ail_pypy_lab.py`) and `par_check.py` preflight raises `ValueError: hash mismatch: test_ail_pypy_lab.py`; expected clean check and runnable tests.
2. `render()` table columns: with PyPy header 11 / separator 12 / refused rows 12 (expected 11/11/11); without PyPy header 10 / separator 11 (expected 10/10). Probe `/tmp/rprobes/probe_edge.py` A.
3. `layer_base` with PyPy missing: base row `wall_ms=2000` expected kept; actual `build_ok=False, wall_ms=None`, `tool_runs.pypy.source='this run'`. Probe `/tmp/rprobes/probe_base.py`.
4. `_first_diff(b'ok\n', b'ok')` expected a diff line, actual `None`, yielding `pypy_diff: null` with `pypy_match=False`.
5. Missing `DEVLOG.md` entry for this job.
[commandcode stop=end_turn turns=26 out_tokens=29100]

FINAL VERDICT: FIX  2026-11-08T21:52:09Z
