# job job-cmpbfs1-11060647  started 2026-11-05T21:48:12Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Summary:

**Branch** `job-cmpbfs1-11060647`, two commits on base `1668526`:
- `e970474` — task spec, generator, oracle, five programs
- `5e91e5f` — `RESULTS-grid_bfs.md`

**Files** (`git diff --stat 1668526 HEAD`: exactly the 9 allowed, 1374 insertions)
`tasks/grid_bfs/{spec.md,gen.py,reference.py}`, `src/grid_bfs/{main.c,main.rs,main.go,main.py,typed.py}`, `RESULTS-grid_bfs.md`. Nothing under `lab/compare/`, no workflow, no README/results of other candidates touched.

**Run** (`ulimit -v 1500000`, all six columns, 4,002,374-byte perf input):
- Cases: 9/9 public+hidden in every column; perf output matches CPython reference, exit 0.
- `ail` (typed.py): typed path, wall 585 ms, RSS 81.6 MiB, binary 38 KiB, compile 1.77 s.
- `ail-py` (main.py): general path (note quoted in RESULTS), wall 13,064 ms, RSS 871.7 MiB, binary 167 KiB, compile 6.33 s.
- `c` 400 ms / 34.6 MiB / 16 KiB / 0.10 s; `rust` 395 ms / 35.1 MiB / 4452 KiB / 0.23 s; `go` 439 ms / 39.3 MiB / 2202 KiB / 5.45 s; `python` 10,080 ms / 255.1 MiB.
- Instructions: all `n/a` (no perf counter, no valgrind on this runner), as recorded.

**Probes:** ten malformed inputs (short/long row, bad byte, bad/out-of-range query, missing/extra line, empty, 20-digit token, `H=2001`) all give exit 2 with empty stdout in all six programs; a valid control matches. `AIL_UNIFIED_FORCE=1` builds (typed.py built without `--strict`, since the flag forces the general path) match reference on valid, huge-token and full perf. No AIL column ever printed a wrong line.

Not done: no push, open PR, or CI watch — the job rules for this runner forbid push and `origin/integ` is not present in the export; the work is committed on the current branch. No `DEVLOG`/manifest changes (explicitly excluded by the task).
[commandcode stop=end_turn turns=35 out_tokens=50494]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: cmpbfs1 (`grid_bfs` candidate task)

**What the change really does:** adds a self-contained new candidate under `lab/compare_cand` — `tasks/grid_bfs/{spec.md,gen.py,reference.py}`, the five programs in `src/grid_bfs/`, and `RESULTS-grid_bfs.md`. No compiler, runtime, test, manifest or workflow file is touched. This matches the report.

### Probes (24 inputs, all six programs vs `reference.py`)
Probe inputs (`/tmp/rprobes/in`), each run through `reference.py`, `main.py` (python), `main.c`, `main.rs`, `main.go`, `typed.py` (ail, default), `main.py` via AIL (ail-py, default and `AIL_UNIFIED_FORCE=1`):

- malformed: `empty`, `just_nl`, `missing_query`, `extra_blank`, `crlf`, `crlf_grid`, `cr_only`, `row_cr_w3`, `badbyte_hi` (0xFF), `badbyte_ascii`, `utf8`, `utf8_w1`, `hdr_double_space`, `hdr_trailing_space`, `neg_query`, `h_too_big`, `q_1e8`, `missing_query` → all exit 2, empty stdout, in every program.
- valid boundaries: `valid`, `leading_zero` (01), `many_zeros` (22-digit token = 1), `no_final_nl`, `q0_nl`, `q0_nonl`, `order` (neighbour-order-sensitive: `dist 4 seen 9`), `walls` (start wall / target wall), and a full 2000×2000 open grid (`dist 3998 seen 4000000`, queue exactly full).
- **Result: every program agreed with the reference on all of them, byte-exact.** I also ran the 4,002,374-byte perf input through all six under `ulimit -v 1500000`: all exit 0, byte-identical stdout, and also through the forced-unified ail-py build.

Note: `main.py` uses text mode (`sys.stdin.read()`, utf-8/surrogateescape) rather than the brief's `sys.stdin.buffer`. Empirically CPython's stdin does not translate `\r\n` here, and surrogateescape keeps byte lengths 1:1, so no divergence appeared — I could not construct any input where text vs bytes changes the outcome.

### Report claims
Verified: typed path (`--strict` accepts `typed.py`, same sha as default build, no fallback note); ail-py general path with the quoted note verbatim; 3/3 public + 6/6 hidden in all six columns (harness `--smoke` run); perf match; binary bytes (39024 / 170584 / 16400 / 4558336 / 2254924); compile times (1.79 / 6.38 / 0.10 / 0.23 / 5.44 s); disk (152 / 544 / 20 / 4452 / 37676 KiB); wall (582 / 12849 / 401 / 396 / 435 / 10083 ms); RSS (81.6 / 871.7 / 34.6 / 35.1 / 39.2 / 255.1 MiB); instructions `n/a` (perf_event_open "Permission denied", no valgrind); “malformed probes exit 2 in all six” (I reproduced it with wider inputs); forced build refused by name “not in the subset: general path explicitly requested”.
Unverified: the exact JSON/table produced by a full `run.py --task grid_bfs` + `merge.py` (I used `--smoke` plus manual perf runs), toolchain-install-size row, and the 20 CI shards (report says push/CI was not possible).

**Pre-existing:** none applicable — no compiler/runtime file changed, so generated C cannot move. Confirmed by compiling `log_scan/typed.py` on HEAD and on a `git worktree add /tmp/base work` build: `program.c` identical (md5 76a84b24…).

**Tests:** no test module was added or edited; `python3 ../tools/par_check.py -j 2 test_ail_safetynet` → `ok … 198s, 0 failed`.

Non-blocking deviations: `spec.md` is an expanded restatement of the prescribed paragraph rather than verbatim (semantics identical); the hidden set is 4 fixed + 2 random cases rather than 6 random ones; `main.py` uses text stdin instead of `sys.stdin.buffer`.

No defect found: no different output, crash or wrong exit status attributable to the change.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=26 out_tokens=38265]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T23:28:25Z
