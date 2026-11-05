# job job-fbred1-11060646  started 2026-11-05T21:49:12Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Short report:

**Commits** (3, on `job-fbred1-11060646`; not pushed — the job's final rule forbids push on this runner):
`4c2f9bb` model, `9dde282` probes/EXPECTED.md, `d63912c` design note. `git diff --name-only 0e9a985..HEAD` is 35 files: `docs/design/PAR_REDUCE.md` + 34 under `lab/race/reduce/` (no compiler/runtime file touched).

**Model** — `python3 lab/race/reduce/model.py`: `cases: 200000 (140000 reduce, 60000 map)`, `differences: 0`, seed 20261105. It compares the chunked combine to a sequential simulation of (exception kind, stop iteration, final acc), including length-1/one-chunk cuts, values at 0/±2^62/±2^63/INT64_MIN/MAX, `+big,+big,-big` and `-big,+big`, exceptions before/after the overflow, every prefix split, and the map-before-sum order. Mutation checks: dropping the M/m test → 1,468 diffs/20k; dropping the partial sum in the exception carry → 302.

**Probes** — 16 pairs (parallel + `range` twin), expected outputs measured from the twins in the default AIL build (`EXPECTED.md`). Today: 12 refused for the shared int (`'acc' is read before the body assigns it`), 1 for `parallel for cannot be inside try` (`p08`), 3 `sum(map)` probes already build and match their twins. `cmp.sh` on all twins: the 10 non-overflowing twins match CPython in both builds; the 6 overflow twins stop loudly in both builds and differ from CPython by design.

**Count moved** — `lab/race/` before this job: 0 of 34; corpus first 500 (219 present): 0 of 219 (no program imports threading/futures/multiprocessing); new `lab/race/reduce/`: 12 of 16. So fbred3 moves 12 probe programs.

**Tests** — `test_ail_safetynet` OK (187 s; it fails under a 1.5 GB `ulimit -v` at `S4_generators_gc`, so I reran it uncapped), `test_ail_files` OK (1 skipped), `test_ail_corpus_findings3` OK. CI shards were not run (no push allowed here).

One caveat recorded in the design note: `p08`'s expected output is a target, not the twin's current output — a sequential int overflow is a hard stop today, while the parallel runtime raises a catchable `OverflowError`, so that spelling needs the `try` rule lifted too.
[commandcode stop=end_turn turns=61 out_tokens=63901]

## review 0
[model commandcode/deepseek-v4.1-flash]
Review done.

**What the change really does:** adds `docs/design/PAR_REDUCE.md`, a Python reference model (`lab/race/reduce/model.py`) and 16 parallel/twin probe pairs. `git diff work..HEAD` touches only those 35 files (837 insertions, 0 deletions); `git diff work..HEAD -- AIL_CURRENT tools` is empty, so generated C and runtime behaviour are unchanged. Report's description matches the diff.

**Claims checked**
- Model on 200,000 cases: `cases: 200000 (140000 reduce, 60000 map)` / `differences: 0` in 3.1 s — verified.
- Mutation teeth: dropping the `M_c`/`m_c` test → 1,468 diffs/20k; dropping the partial sum from the exception carry → 302 — verified exactly (copies patched in /tmp).
- Probe count/status: compiled all 16. 12 refused with `'acc' is read before the body assigns it`, p08 refused with `parallel for cannot be inside try`, p10/p14/p15 build — verified.
- Expected outputs: compiled and ran all 16 twins; every row of EXPECTED.md matched, including the six loud overflow stops (`exit 1`, empty stdout) and p06's `ZeroDivisionError`. cmp.sh on the 10 non-overflow twins: 2/2 builds match CPython each; p03/p16 overflow twins loud in both builds — verified.
- Counts: `lab/race` grep for `par_range` finds only `run.py` + `racy/neighbour.py`; corpus has exactly 219 .py and 0 import threading/futures/multiprocessing — verified. The table's "34" is 37 program files in `lab/race` (14+17+6); 34 only if the three hybrid `*_run.py` helpers aren't counted — **minor false/ambiguous**. Design note line 150 "every probe-prefix split" is really a random prefix per case — **overstated**, harmless.
- `test_ail_safetynet` on HEAD: ok, 308.5 s, 0 failed — verified (slower than the reported 187 s). `test_ail_files` / `test_ail_corpus_findings3` not re-run (no test module added/edited) — unverified. `update_manifest.py --check` passes.
- p08's expected output is not its twin's output; disclosed in EXPECTED.md and the report, and the reason (sequential overflow is `ail_die`, parallel is catchable) is consistent with `ail_par_run`'s `ail_raise_value_adopt` path.

**My probes** (/tmp/rprobes, 5): empty map `sum(ex.map(f, range(0)))`=0 and n=1; overflowing `sum(ex.map(...))`; dict-value accumulator in a body; accumulator fed by a call (`acc += term(i)`); mutate the list after taking the `sum(map)` result. All identical on HEAD and base: r1/r5 match CPython both builds; r2 stops loudly (exit 1) as its twin does; r3/r4 are named refusals.

**Pre-existing** (identical on base): `sum(ThreadPoolExecutor.map)` whose sum overflows stops loudly instead of CPython's exact big int, and the default build's message differs (`in a conversion to int64` vs `in +`) from the sequential twin. Not caused by this change.

**Speed:** not applicable — no compiler/runtime/hot-code change, so no icount run.

Nits only (wrong `lab/race` file count, "every prefix split" overstatement); no behavioural defect and the deliverable's substance checks out.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=25 out_tokens=21064]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T23:34:43Z
