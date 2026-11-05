# job job-typeshed3-11051512  started 2026-11-05T06:22:18Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model commandcode/deepseek-v4.1-flash]
All work is committed and the tree is clean (the only untracked file, `.agent/pipeline.md`, is pre-existing and not mine). I did not push: the task's execution note says "Commit your work on the current branch; do not push," which overrides the earlier "push" wording, so CI was not run.

## Report

**Sub-step 1 — conflict tool** (`tools/typeshed_conflicts.py`, `lab/typeshed/CONFLICTS.md`)
Compares every entry of `unified._etype` builtin rules, `unified._DRAWS`, `pyfunc._AIL_CLOCK/_AIL_SYSINFO/_AIL_RAND`, `filelib.PRIMS`, and the annotated prelude functions of `genlib.TABLE` with `stubsigs.lookup`:
`checked 188 agree 40 conflict 15 stub_obj 133`.
All 15 conflicts have a CPython 3.12 verdict; every one is `stub` (e.g. `time.sleep` rule `int` / stub `None`, CPython `None`; `time.mktime` `int` vs `float`; io `int` vs `bool`/`None`; os `int` vs `None`). They are listed under "rule may be wrong" with source lines and probes; no rule changed.

**Sub-step 2 — whole-corpus measure** (`lab/typeshed/RESULTS.md`)
Full 1022-program double build was over the 40-min limit, so per the brief: 87 reach-affected programs + 100 random of 935 (seed 1) = 187, `AIL_UNIFIED_FORCE=1`, on vs `AIL_STUBCALLS=0`.
- built 171/187 both modes, same 16 failures
- `unboxed_vars`: **1334 off → 1420 on (+86)**; all gain in the affected set (rest 797/797, 0)
- `program.c` changed: **41**
- CPython differences: **5, identical lists on and off** (`g02_038`, `g17_030`, `getopt/11_convert_int`, `tomllib/04_datetimes`, `tomllib/09_big_int`) — all pre-existing int64/`_AilDT`/directory differences. No difference appears only with stubcalls on, so the stop rule did not trigger.
- default-build split (census, 184 classified): typed 74 / general 98 / refused 12; this lane touches no compiler file, so it cannot move.
- follow-ups: 216 distinct callees, 2026 boxed/refused sites, ranked with reason and compiler location (`stubcalls.call_type`, `qualname`, `DENY`, typeshed vendoring); top 35 listed.

**Sub-step 3 — test**
`test_ail_typeshed_conflicts.py` (3 tests) registered in `tests.d/`, manifest updated with `--check` passing.

**Tests run**: `test_ail_typeshed_conflicts` OK, `test_ail_stubcalls` OK, `test_ail_files` OK, `test_ail_corpus_findings3` OK, `test_ail_safetynet` OK (its one failure under `ulimit -v 1500000` was the cap on the GC/memory case; it passes uncapped).

**Probes** (`/tmp/probes`, via `cmp.sh`):
- `probe_conflict_types.py` — matches CPython on both builds.
- `probe_typeshed3_unbox.py` — matches CPython on both builds; `AIL_STUBCALLS=0` output identical to default.
- `probe_conflict_sleep.py` — intentionally differs (`int` vs `NoneType`), documenting the reported `time.sleep` conflict; rule left unchanged.

`git diff --stat 929e620..HEAD` = only the 5 new/edited lane files + the two `manifest.d` shards. Commits: `d761711`, `e126944`, `615b06c`.
[commandcode stop=end_turn turns=121 out_tokens=46353]

## review 0 skipped: only 28 minutes left

FINAL VERDICT: ERROR  2026-11-05T11:13:52Z
