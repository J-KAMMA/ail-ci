**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
**What the change actually does:** adds two measurement-only scripts (`lab/profile/pred_probe.py`, `lab/profile/ccheck.py`) and their report/data (`CTIME_PRED.md`, `CTIME_PRED.json`). No file under `AIL_CURRENT/`, `pyfunc.py`, runtime or C emitter is touched, so no program semantics change — the diff is exactly the four new lab files.

**Verified**
- `pred_probe.py` reproduces the committed numbers: re-running `--tasks echo_pack` on HEAD gave calls/repeats/changed identical to the JSON for all 8 predicates (`_etype` 95153/92172/16513, `_map_kind` 122210/119229/0, `type_of` 301359/301104/83893), and cacheable after the documented `fe_own/probe_own` scaling matches to ~0.1%.
- Whole-record consistency: a fresh `ccheck --check` builds (220/220) matched every `c`/`exe`/`rc` hash; only one refusal hash differs (defect 1).
- Probe is observe-only: `pred_probe --tasks tree_fold --debug` produced `sha256(program.c)=36cc65e7…`, the same as the no-probe/`typed.py` build recorded in `byte_identity`.
- `test_ail_safetynet`: pass (256 s, `-j 2`). No test modules were added/edited.
- JSON has all 10 tasks × 8 predicates with calls/repeats/changed/cacheable; per-task saving/projection/halved arithmetic recomputes exactly; ends with the no-go at 1.0052x best halved (the 1.03x rule fails by a wide margin). Decision is sound and robust to the probe's timing inflation.

**Defects**
1. The committed `byte_identity` record is stale relative to the final `ccheck.py`. Commit c9d747e added `ailc-<tmp>` normalization, but the record was made by the older version. Reproduce: JSON row `lab/corpus/programs/glm-5.3-flash-free/t131.py`, expected refusal `e968cda8…` (HEAD), actual fresh build `998da936…`; `python3 lab/profile/ccheck.py --check` on HEAD therefore prints `MISMATCH … t131.py refusal` and exits 1 instead of `all 220 inputs identical`. (My initial `--check` passed only because a stray `ccheck --base` rewrote the working-tree JSON at 23:50:35; not run by me, left uncommitted.)
2. `CTIME_PRED.md` §5 prose contradicts its own table: it says eligible cacheable "0.222 s" and net "0.106 s (0.34%)", but the listed-predicate savings column (0.146 s, 1.0048x pooled / 0.474%) correspond to 0.262 s cacheable (0.1176 `_map_kind` + 0.1444 `_is_owned_bytes_call`). Expected 0.262/0.474%, actual 0.222/0.34%.
3. Minor: §2 says the wrapper inflates own time "about a microsecond per call"; measured inflation is 0.8 µs (`type_of`) to 12.9 µs (`_etype`) per call. Scaling makes this non-blocking.

**Notes:** `_param_kinds` keys on `id()` of dict/tuple arguments, so it can only under-count repeats; with 0 repeats anyway the conclusion is unaffected. §1's "halved 1.123x" is carried from `CTIME_CUT.md` as instructed. Commit trailers on 64211aa/3d61a4e name "Claude Sonnet 5.5" while the worker header shows deepseek attempts — unverifiable which model authored, flagging only.

**Pre-existing:** none identified (no compiler change).

**Unverified:** berth_sim/chain_relax/tally_lang sub-step runs; the 200-corpus changed-repeat rows (probe outputs not committed — only aggregates); CI shards / PR (remote branch is still at the base, so nothing was pushed).

VERDICT: FIX
1. Regenerate `byte_identity` with the final `ccheck.py` and commit it: probe `lab/profile/ccheck.py --check` on HEAD, expected `all 220 inputs identical` / exit 0, actual `MISMATCH lab/corpus/programs/glm-5.3-flash-free/t131.py refusal` / exit 1 (recorded `e968cda8…`, fresh `998da936…`).
2. Correct `CTIME_PRED.md` §5: expected eligible cacheable 0.262 s / net 0.146 s (0.474% of wall), actual text says 0.222 s / 0.106 s (0.34%).
[commandcode stop=end_turn turns=50 out_tokens=40162]


--- ORIGINAL TASK ---
Lane: fa-ctpred

> Re-run of ctpred1, whose GitHub run was lost (no verdict 6.5 h after dispatch). If its branch job-ctpred1-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.
Needs: ctimes1 ctimes3

# ctpred1: how much of the pyfunc type/kind predicate time is repeated work with an unchanged answer (measure only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the cacheable seconds of the `pyfunc` predicates on the 10 compare tasks. These are the own
time of the calls that repeat an earlier call on the same node and arguments AND return the same answer. Unknown
today. ctimes2 (`lab/profile/CTIME_CUT.md`) priced the predicates (`_etype`, `_is_str_expr`, `_is_slist_expr`,
`Ctx.type_of`, `_param_kinds`, `_map_kind`, ...) as the largest front-end cost. It built nothing, because
`pyfunc.py` was outside its file list. This job decides whether ctpred2 builds a memo cache, and for which
predicates. No compiler file is edited.

## Price (speed-claims rule; already measured, repeat it in `CTIME_PRED.md`)

- Share: 6.731 s pooled own time, 21.9% of pooled cold wall (30.795 s, CTIME_FE.md); full Amdahl bound 1.280x;
  halved 1.123x. The tasks at or above 1.10x halved are berth_sim 1.200, chain_relax 1.205, echo_pack 1.320 and
  ledger_bin 1.108.
- That bound assumes the predicates become free. A cache removes only repeated calls with an unchanged answer, and
  it adds a lookup to every call. With a cacheable fraction `f` of predicate own time, and a lookup cost `L` seconds
  per call times `n` calls, the saving is `f * own - L * n`. Measure `L` with `timeit` on a dict keyed by `id(node)`.
  The projection is `1 / (1 - saving / wall)`; halve the gain.
- Go rule for ctpred2: the halved projection is at least 1.03x on at least 3 tasks. Otherwise the predicate line
  stops here.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/profile/pred_probe.py`: wraps the predicates from outside, in the child process (through `sitecustomize` in a
  temp directory, as `lab/selfhost/hot_functions.py` does), and never edits `pyfunc.py`
- `lab/profile/ccheck.py`: the byte-identity check (Appendix B) over the 10 `typed.py`, the 10 `main.py`, the first
  200 sorted `lab/corpus/programs/*/*.py`, and `docs/design/alias_study/trans`. It stores the C, executable and refusal
  hashes. ctimes2's brief specified it, and ctimes2 stopped before writing it.
- `lab/profile/CTIME_PRED.md`, `lab/profile/CTIME_PRED.json`

## Sub-steps

1. **Probe (25 min).** For each predicate, `pred_probe.py` records per call: the key (`id(node)`, the other
   arguments if hashable, else "unhashable", and `id(ctx)`), the own time, and the result as `repr`. It keeps every
   node alive for the run, so ids are not reused. It counts calls, distinct keys, repeats, and repeats whose result
   differs from the first answer (a "changed" repeat means the predicate reads state that changes during the build,
   so a plain cache is wrong for it). Run it on berth_sim, chain_relax and tally_lang. Commit, push, and open the PR
   against `integ`.
2. **All 10 and `ccheck.py` (20 min).** Run all 10 tasks with `ulimit -v 1500000`. Also run the 200 corpus programs,
   counting changed repeats only. Write `ccheck.py` and run it once on the base to record the hashes. Commit and push.
3. **Price (15 min).** `CTIME_PRED.md`: per predicate, calls, the repeat share, changed repeats, cacheable seconds,
   and the lookup cost. Per task: the saving, the projection and the halved projection. End with the go or no-go and
   the list of predicates for ctpred2. A predicate is listed only if it has 0 changed repeats over all 210 inputs,
   ordered by cacheable seconds. Commit, push, and wait for CI.

## Done-check

- `CTIME_PRED.json` has a row for all 10 tasks, with each predicate's calls, repeats, changed repeats and cacheable
  seconds.
- `CTIME_PRED.md` ends with a go or no-go under the rule above, with the numbers.
- `python3 lab/profile/ccheck.py --base` writes hashes for every input; the 20 shards pass; the diff shows only the
  listed files.

## Stop rule

Stop if the wrapper changes the generated C of a task (compare `program.c` with and without it): the probe must
observe only. Stop when 60 minutes pass, and push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do
   not edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus
   the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet.
- Compile-time numbers: `lab/profile/run.py` (cold builds, `--fe-profile`, `--no-profile`, `--runs N`);
  `lab/profile/CTIME_2026-11.md` (phase shares), `CTIME_FE.md` (ctimes1, function and module rows),
  `CTIME_CUT.md` (ctimes2, the price of the pyfunc predicates). Instruction counts come from `tools/icount.c`. Timing on
  this laptop is noisy, so icount judges and wall time is reported as a median of 3 on the GitHub runner.
- Byte identity: build with `--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`, `AIL_SERVER=0` and a fresh `AIL_CACHE`;
  compare `sha256(program.c)`, `sha256(executable)` and the refusal text of refused programs.
- Speed-claims rule: before any edit, write the phase share, the Amdahl bound and the projection, then halve the
  projection, because this repo's estimates overshot 2-3x (2.5x estimated, 0.88x measured). A step whose halved
  projection is under 1.03x is not built.

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
