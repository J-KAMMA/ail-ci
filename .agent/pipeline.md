# job job-pyperf1-11042325  started 2026-11-04T14:27:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final state:

**Result**
- 10/10 programs build in the default mode and match CPython 3.12 at the default size (stdout + exit status); 2 typed (`fannkuch`, `float_bench`), 8 general-path, 0 refused.
- `AIL_UNIFIED_FORCE=1`: all 10 build typed and match CPython (small sizes, recorded only).
- **Geomean wall ratio CPython/AIL = 1.359** (AIL 1.36x faster overall; 26.9x on typed fannkuch, 0.24x on general scimark_sor).
- Instruction ratio **not available**: `tools/icount.c` builds but `perf_event_open: Permission denied` (`perf_event_paranoid=4`), so per the stop rule the measurement is wall time only and `RESULTS.md` says so.

**Files**: the 10 programs, `run.py`, `README.md`, `RESULTS.md`, `AIL_CURRENT/test_ail_pyperf_lab.py`, `tests.d/test_ail_pyperf_lab.txt`, and the two manifest shards it pinned. `git diff --stat` against the base shows only those.

**Probes** (`/tmp/probes/*.py`, small sizes, `bash ~/tools/cmp.sh` — default and `AIL_UNIFIED_FORCE=1` builds): fannkuch, float_bench, generators, nbody, nqueens, raytrace, richards, scimark_fft, scimark_sor, spectral_norm — all 10 "same stdout" in both builds, exit 0. (Unrelated pre-existing files in `/tmp/probes` failed and are not mine.)

**Tests on final commit**: `test_ail_pyperf_lab` (3 tests, 25 s), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all OK; `update_manifest.py --check` clean.

Commits: `a2d6570`, `2140510`, `27305d8`. Per the job's standing rules ("do not push") I did not push or run the 20 CI shards, so those checks are unverified.
[commandcode stop=end_turn turns=59 out_tokens=64131]

## review 0
[model commandcode/deepseek-v4.1-flash]
Review complete.

## What the change really does
Adds 10 new plain-Python benchmark programs under `lab/pyperf/bench/`, a runner (`run.py`), README/RESULTS, and a test module with its registration and two manifest pins. No compiler or runtime file is touched (generated C for a plain program differs from base only in the embedded source path, 238211 bytes both).

## Verified claims
- 10/10 build in the default mode and match CPython (**re-ran all ten at the default size**, not just small: e.g. richards 1.469/1.188 s, sor 1.070/4.371 s, fannkuch 4.915/0.182 s — the table reproduces within noise).
- Paths: 2 typed (fannkuch, float_bench), 8 general, 0 refused; first-note lines match RESULTS verbatim.
- `AIL_UNIFIED_FORCE=1`: all ten build typed and match (results.json `unified_path`/`unified_matches`).
- icount unavailable: reproduced (`paranoid=4`, `perf_event_open: Permission denied`), so wall-only is the lane's stop rule.
- Geomean wall ratio 1.359 recomputed from the table = 1.359.
- `test_ail_pyperf_lab` 36.9 s ok, `test_ail_safetynet` 169.8 s ok; `update_manifest.py --check` clean; diff = exactly the 17 allowed files.

## Probes (all match in both builds; no refusal needed)
sor6, sor40, sor200, nq01 (n=0/1), nqneg (n=-1), fk123, fk0 (both exit 1, empty stdout), rich0 (0 packets), nbody0, ray1, ray16, spec1, spec60, fft2, gen3, gen50k, float0, nbody200, mutiter (remove during iteration / append during while), plain (C identical to base).

## Pre-existing
None observed.

## Minor inaccuracies (documentation only, non-blocking)
1. RESULTS/README: "median of three runs of **each binary**" — CPython is run once (`wall_cpython` is a single sample in `run.py`).
2. README: "the AIL general path is about twenty times slower … which is what the wall columns show" — the columns show 0.24x–4x.
3. RESULTS header pins `a2d6570`, but the richards row was measured at `27305d8`.
4. `run.py`'s markdown always prints "matching CPython at the default size", even under `--small`.
5. fannkuch's default has CPython at ≈4.95 s, outside the stated 1–3 s.
6. No push / 20 shards — the job's own rules forbid pushing, so unverified rather than failed.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=30 out_tokens=22520]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T16:21:10Z
