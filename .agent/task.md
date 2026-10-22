**Integration job: combine four accepted job branches into this branch.** This repo is public, so fetch each one anonymously with `git fetch https://github.com/J-KAMMA/ail-ci.git <branch>`. The branches are: job-c169-10221631 job-cov6-10221632 job-fuzz8-10221632 job-intenum4-10221632

For each branch:
1. Its own commits are the ones after its first commit "job <name>: export of ...". Cherry-pick only those commits, leaving out any changes under `.agent/` and `corpus/`.
2. Resolve conflicts by keeping both sides' fixes.
3. Placeholder ids `C?-...` in DIFFERENCES or DEVLOG must be numbered with `python3 tools/diff_ids.py`.
4. Run `python3 tools/update_manifest.py`.

Then:
- run the full suite: `cd AIL_CURRENT && python3 ../tools/par_check.py -j 4`;
- fix only failures caused by the combination;
- commit.

The report must list, per branch:
- the commits taken;
- the conflicts and how you resolved them;
- the full-suite result, with failing modules and whether they also fail on the base.

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

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
