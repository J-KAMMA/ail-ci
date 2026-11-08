Lane: rc

# rc4: Perceus reuse: a node dropped with RC==1 is reused in place for a same-size allocation in the same function

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on rc3 merged (or rc2, if rc1 said no-go for rc3), and on rc1's `PRICE.md` saying "go" for rc4. Otherwise
stop and report.

**Number this moves:** peak RSS and run instructions of the `lab/rc/progs` rbtree, cfold, deriv and binarytrees
programs, and of `tree_fold` (`typed.py` and `main.py`). Targets: rc1's halved projection for rc4 (at least 1.03x
instructions or 5% lower peak RSS on 2 programs); no program more than 0.3% worse in instructions or 1% higher in
peak RSS. For tree_fold, report the number honestly: rc1 says whether reuse can touch it at all; do not stretch the
rule to reach it. (Koka's authors note that reuse can RAISE peak memory, because a cell is held until reused: watch
for it.)

**The rule.** In one function, when an object of class C is released and, on every path after that release and
before any call that may allocate or observe it, an object of a class with the same allocation size is created:
- emit `if (rc == 1)` reuse the memory in place (release its fields first, then initialise the new object in it);
  else release as before and allocate;
- never across a call, a yield, a `try` boundary, or a loop back edge;
- object identity: CPython makes a new object, and `id()`/`is` of the old one are dead at that point (the old
  reference is gone), so reuse is invisible. If the old object is still reachable through any name, rc is not 1 and
  the fast path is not taken.
- `__del__`: a class with `__del__` (or a weakref to it, if supported) is never reused.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/ir/reuse.py` (new): finds release/allocate pairs and rewrites them;
- the object-allocation emit site rc1 named, a hook of at most 30 lines (if it is in `pyfunc.py`, busy: at most 20
  lines in one function, never `to_c` or `_etype`; rebase on `origin/integ` just before each push);
- the C prelude part that defines object allocation (`ail_obj_*`), adding one `ail_obj_reuse` helper of at most 25
  lines, wherever rc1 names it (`pyfunc.py` prelude or `cruntime.py`: if `cruntime.py`, keep it one isolated block);
- `lab/rc/RESULTS_REUSE.md` (new), `AIL_CURRENT/test_ail_rc_reuse.py` (new),
  `AIL_CURRENT/tests.d/test_ail_rc_reuse.txt` (new);
- the manifest files that `tools/update_manifest.py` writes.
`AIL_RC_REUSE=0` turns it off for A/B runs.

## Sub-steps

1. **Find pairs (30 min).** `ir/reuse.py` with the rewrite off: list the pairs found in the 6 programs and the 10
   compare tasks in `RESULTS_REUSE.md`. Hand-check 3 and write 3 refused shapes (across a call, a class with
   `__del__`, the old object still named). Commit, push, open the PR.
2. **Reuse (30 min).** Turn it on. Verify as in rc2 step 2 (16 programs, 10 `main.py`, 200 corpus programs, against
   `python3` and the `AIL_RC_REUSE=0` build, default and `AIL_UNIFIED_FORCE=1`); valgrind on rbtree and cfold at a
   small size (no invalid access, no new leak); rc2's and rc3's tests. Commit and push.
3. **Measure and test (20 min).** Peak RSS (median of 3) and instructions before/after. `test_ail_rc_reuse.py`: the 3
   refused shapes and 2 reused ones, against `python3`, and a check that `ail_obj_reuse` appears in `program.c` only
   for the reused ones. Register it. Fill price/achieved. Commit, push, wait for CI.

## Done-check

- 0 output differences against `python3` and the `AIL_RC_REUSE=0` build over all inputs, both build modes.
- valgrind clean on 2 programs.
- At least 1.03x instructions or 5% lower peak RSS on 2 programs; none worse by more than 0.3% / 1%.
- The listed tests and the 20 shards pass.

## Stop rule

Stop on any wrong output against CPython or the `AIL_RC_REUSE=0` gcc build, any valgrind invalid access, or any
program whose peak RSS rises by more than 1%: record it first, then exclude that shape. Stop when 80 minutes pass.
Push what is done first.

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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `optlib.py`, `ir/passes/*`, `parallel.py`,
   `typedpar.py`, `unified.py`, `stubcalls.py` or `buildcache.py`. In `pyfunc.py` and `cruntime.py` touch only the
   hook and helper named above. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`.
- Source of the technique: Reinking et al., "Perceus", PLDI 2021 (Koka, Apache-2.0); Ullrich and de Moura, "Counting
  Immutable Beans", IFL 2019 (`reset`/`reuse`). Ideas only; no code is copied.
- Instruction counts: `tools/icount.c`. Peak RSS: `/usr/bin/time -v`. For allocation-heavy changes compare
  `CYCLES=1` medians too: `rep movsb` and page faults hide from instruction counts.

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
