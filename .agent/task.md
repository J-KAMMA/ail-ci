**Fix one pre-existing difference from CPython.** A reviewer of job `rbrbpre126` recorded these as already present before that job:

- `p4_noniter.py`: `combinations(x, 1.0/'x'/None)` on a non-iterable raises `'int' object is not iterable` instead of CPython's index TypeError. HEAD and `/tmp/base` are identical.
- `p6_index.py`: an object with `__index__` is rejected by combinations/cwr (`TypeError`) while CPython accepts it; base returned `[]` for combinations and crashed with OOM for cwr, so the gap predates the change and HEAD removes the crash.

**Tests:** `test_ail_pre126`, `test_ail_pre101`, `test_ail_pre137` (2+6 = 8), `test_ail_safetynet`, `test_ail_files` (18 run, 1 skip), `test_ail_corpus_findings3` all pass. `update_manifest.py --check` rc=0; `ci_shards --check` flags the new module but CI's `--shard` path runs unassigned modules, and the accepted rbpre126 did not update it.

**Claims:** reapply/keep-pre137, commit `2cb7e36` (7 files), DEVLOG/DIFFERENCES row id, manifest check, absent `diff_ids.py`, test counts and the untracked `.agent/pipeline.md` are all verified. Minor: DEVLOG names the probes `pre126_r_*` while the report/files use `pre126_*`. `test_ail_pre126.py` is byte-identical to the accepted version.

**Unverified:** instruction-count speed (`icount` fails with `perf_event_open: Permission denied`); the relevant gdev programs (`g07_020`, `g06_026`, `g16_032`) produce the same output as CPython and base, and the change adds only one check per combinatorics call.

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre219.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Run `python3 tools/update_manifest.py`, then `--check`.
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
