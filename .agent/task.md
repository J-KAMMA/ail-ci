**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
I have enough evidence. Writing the report.

**What the change really does.** It adds only `lab/wedge3/wedge3d/**` (harness, two workload drivers, pinned requirements, `results.json`, `RESULTS.md`, `DEVLOG.md`); no AIL compiler, runtime, or test file changes. It measures the `job-obs5-op1109` hybrid at commit `69e2dcd0` on python-dateutil and ahocorapy against CPython, PyPy, and native rewrites (ciso8601, ahocorasick_rs), and ranks the hybrid's refusal reasons.

**Verified (ran/reproduced myself)**
- `git diff work..HEAD` is only `lab/wedge3/wedge3d/**`; `AIL_CURRENT`, `tools`, `bench` untouched, so no base comparison applies.
- Rebuilt both hot modules at `69e2dcd0`: `accelerated: []`, rejected 56 and 17 — reproduces the "0 accelerated" headline. A trivial typed module does accelerate (`add`), so the build path is not broken.
- Counts: independently AST-counted installed modules -> dateutil `58 / 2 / 54`, ahocorapy `17 / 0 / 17`.
- `normalise_reason` now yields `"method: calls a method that stays in CPython"`; refusals.reasons in `results.json` contains it. `refusal_ranking` on a fresh cProfile run gives `hot_self_s` 2.451/2.687 (dateutil/aho), same rows as committed 2.473/2.680, and no `re/_parser` entries; the excluded `re` total is 0.000355 s, matching the DEVLOG's 0.00036.
- Full-size workload outputs are byte-identical to CPython for both libraries (50,000 dates; 100,000 repeats, 19,205,994-byte text, 500 matches). Saved edge-probe outputs are md5-identical across CPython/PyPy/native/hybrid/obs.
- Observed path end-to-end on ahocorapy: annotate keeps 17 defs, annotated run output equals CPython, rebuild gives 0 accelerated.
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: `par_check -j 2` -> 3 modules, 0 failed; worker logs confirm 5 / 18+1 skip / 2.
- `perf_event_open` really is denied (`paranoid=4`), so the missing icount column is legitimate.
- Report/`results.json` times and ratios are arithmetically consistent; medians are the median of the five listed runs.
- `update_manifest.py --check` exits 0.

**Defect**
1. `RESULTS.md` §1 says the 50,000-string date workload includes "±14:00 offsets". The generator `workloads/date_parse.py:make_strings` uses `off = (i*37) % 1440 - 720`, so offsets are only `-11:57 .. +11:56`; ±14:00 appears solely in `/tmp/probes/w3d_date_edges.py`. Probe `/tmp/rprobes/w3d_offsets.py` output: `offset strings=12500 min=-11:57 max=+11:56`, `has +14:00: False  has -14:00: False`. Expected per the report: ±14:00 offsets in the workload; actual: none. One-line report fix; no measured number or conclusion changes.

**Pre-existing.** None applicable — no AIL source is modified and the lab directory is new.

**Unverified.** I did not re-run the five-repetition wall timings (I verified the stored times are medians and reproduced outputs/builds/refusals); the dateutil annotate step was not re-run (only aho).

VERDICT: FIX
1. Fix the false workload-coverage sentence in `RESULTS.md` §1: state the actual offset range (`-11:57 .. +11:56`, or "up to ±12:00"), or extend `make_strings` to reach ±14:00. Probe `/tmp/rprobes/w3d_offsets.py` expected ±14:00 present, actual `min=-11:57 max=+11:56`, no ±14:00.
[commandcode stop=end_turn turns=42 out_tokens=67003]


--- ORIGINAL TASK ---
# wedge3d: more real libraries rewritten in Rust (breadth for wedge3)

Lane: wedge3d

Same method, rules and report format as wedge3 (read `~/agents/projects/ail/tasks/wedge3.md` if present, else
the summary here), but on two different libraries so the evidence is not from one hand-picked set:

| Pure Python | Native rewrite |
|---|---|
| python-dateutil `parser.parse` over many date strings | whenever (Rust) or `ciso8601` (C) parsing the same strings; say which |
| pyahocorasick-free pure Aho-Corasick (`ahocorapy`): many-pattern search over a text | `daachorse` / `ahocorasick_rs` (Rust) |

- Build the hybrid from branch `job-obs5-op1109` (observed-type work, not yet integrated):
  `git fetch origin job-obs5-op1109 && git worktree add ../obs5 FETCH_HEAD`, use `../obs5/AIL_CURRENT`; record its commit.
- Libraries are pip-installed into a venv at run time; never vendor their source. Pin versions in
  `lab/wedge3/wedge3d/requirements.txt`.
- Apply `ailc ext` (hybrid) to the library's hot module(s) copied into a temp dir; also run the observed-type
  recorder (`AIL_CURRENT/ail_observe.py`, docs/design/OBSERVED_TYPES.md on that branch) and report hybrid with and
  without observed kinds.
- Every workload's output must match CPython byte for byte; a mismatch is a bug report with a minimal repro.
- Times, median of 5, for: CPython, PyPy 3.10+ (same pure library), hybrid, native rewrite. Use `tools/icount.c`
  instruction counts too where the run is under ~30 s.
- Work under `ulimit -v 2500000`, one workload at a time. Time budget 3 h; commit and push after each library.

Report `lab/wedge3/wedge3d/RESULTS.md`: per library functions total/native, the four times, ratios hybrid/CPython,
hybrid/PyPy, hybrid/native, refusal reasons ranked by CPython time they cost, one honest headline sentence.
Commit only `lab/wedge3/wedge3d/**`.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
