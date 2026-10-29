**csv: the typed `csvlib` reader must not return str cells for `quoting=csv.QUOTE_NONNUMERIC`.**

Background: an old job (`csv1`, accepted but its diff no longer applies) found that the typed `csvlib` reader accepts `csv.QUOTE_NONNUMERIC` but returns every cell as a str, where CPython converts unquoted numeric fields to float. The CI-version part of that job (escapechar-leading fields numeric under QUOTE_NONNUMERIC) is already on integ (dadfa5cb); do not redo it.

Reproducer (compare with CPython 3.12 on both builds; the source must be a literal list so the default build takes the typed path, and also reach the rows through an argument, a list item, an attribute and a dict value):

```python
import csv
rows = list(csv.reader(['1,2.5,"a",b', '3,,"4"'], quoting=csv.QUOTE_NONNUMERIC))
print(rows)   # CPython: [[1.0, 2.5, 'a', ...]] -- unquoted numbers become float
```

Fix: either refuse the construct by name at compile time in `csvlib.py` (`csv.QUOTE_NONNUMERIC is not built for a reader: it yields float and str; the general path builds it`) so the general path, which converts the numbers, takes the program, or build the floats exactly. First check whether today's integ already does this; if it does, change nothing and say so. Never leave a silent difference.

Start from today's integ (`git fetch origin; refs/remotes/origin/integ`), do not reuse the old diff (old branch: `out/ci/csv1.branch` in the agents folder, only for reference).

Add a CPython-compared test module `AIL_CURRENT/test_ail_recsv1.py` registered in `ail_check.py` MODULES, run `python3 tools/update_manifest.py`, then only that module, the modules of the files you touched, and `test_ail_safetynet`. Commit.

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
