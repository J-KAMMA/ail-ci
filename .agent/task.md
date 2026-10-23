**Integration job: add these accepted job branches to this branch, one by one.** This repo is public, so fetch each branch anonymously: `git fetch https://github.com/J-KAMMA/ail-ci.git <branch>`. Branches:
- job-c169-10221631
- job-cov6-10221632
- job-fuzz20-10230625
- job-fuzz21-10230420
- job-fuzz22-10230420
- job-fuzz23-10230421
- job-fuzz24-10230422
- job-fuzz27-10230628
- job-fuzz28-10230629
- job-fuzz29-10230630
- job-fuzz30-10230631
- job-fuzz31-10230632
- job-fuzz32-10230813
- job-fuzz33-10230814
- job-fuzz35-10230816

For each branch:
1. Its own commits are the ones after its first commit "job <name>: export of ...". Leave out commits that touch only `.agent/` or `corpus/`. Cherry-pick the rest, leaving out any changes under `.agent/` and `corpus/`.
2. On a conflict, keep both sides' fixes. If one branch cannot be combined safely, skip it and say why.
3. Number placeholder ids `C?-...` in DIFFERENCES and DEVLOG with `python3 tools/diff_ids.py`.
4. Run `python3 tools/update_manifest.py`, then commit.

At the end:
- run the full suite once: `cd AIL_CURRENT && python3 ../tools/par_check.py -j 4`;
- fix only failures caused by combining the branches;
- commit.

Report per branch whether it was taken or skipped. Report the full-suite result: failing modules, and whether each also fails on the base.

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
