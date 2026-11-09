# job job-fbfsum1-11092016  started 2026-11-09T11:17:39Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
**fbfsum1 complete** (branch `job-fbfsum1-11092016`, 4 commits; not pushed — this runner's instructions say do not push).

**Precheck:** `lab/race/RESULTS.md` on `origin/integ` lists D2 as a follow-up job, so I proceeded.

**What I built**
- `AIL_PAR_FSUM=fixed` read in `parallel.py`; `pyfunc._par_outline` lowers a float `acc += e` to a chunk worker; new `cruntime.PARREDF` runs fixed 4096-iteration chunks on PAR's pool and combines chunk sums left to right. Each chunk starts from `-0.0`; no timed probe prefix (it would move boundaries). `PARREDF` is emitted only under the opt-in, so default `program.c` is unchanged.

**Numbers**
- Probes: 10 in `lab/race/fsum/` (ordinary, cancellation, NaN, inf, all `-0.0`, n=4095/4096/4097, 3 items at 16 threads, non-zero start). **200/200 runs** (1/2/4/16 threads × 5) bit-identical to `model.fixed_sum`.
- Without opt-in: all probes refused with stderr byte-identical to `origin/integ`; **22/22** `program.c` hashes identical (10 typed compare tasks + 12 reduce probes).
- Bench `bench_fsum.py` (200M terms): 0.17 s at 1 thread → 0.06 s at 4, **2.83x** (target 2.5x).
- Extra self-check probes through an argument, list item, dict value and attribute: 6/6 runs each match the reference; each refuses without the opt-in.
- Tests (on a clean `git archive` export, which is what CI sees): `test_ail_par_fsum` 3 OK, `test_ail_par_reduce` 3 OK, `test_ail_parallel_for` 6 OK, `test_ail_files` 18 OK (1 skipped), `test_ail_corpus_findings3` 2 OK, `test_ail_safetynet` 5 OK.
- Added the DIFFERENCES row `C?-job-fbfsum1-11092016-1` and updated the manifest.

One caveat I hit and handled in the test: the build cache key is computed from the parent's `os.environ` while the compiler bytecode is shared in-tree, so a test that set `AIL_PAR_FSUM` only in the child env could reuse a previous opt-in build. `test_ail_par_fsum` now compiles each program with `AIL_NO_CACHE=1` and its own `PYTHONPYCACHEPREFIX`; the normal CLI (env in the shell) is unaffected.
[commandcode stop=end_turn turns=231 out_tokens=131800]

## review 0 failed to run: (no final text) [cost $0.0000, opencode tokens {}]     tool time:  

## review 0
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

FINAL VERDICT: ERROR  2026-11-09T13:18:23Z
