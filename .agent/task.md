You continue on the current branch, where your earlier work is committed. **Fix only these findings from the last review, nothing else:**

1. Conditional `del` now removes a live binding, producing wrong output. `m.py`: `X = 1` / `if 1 > 2:` / `    del X`; `main.py`: `X = 5` / `from m import *` / `print(X)`. CPython: `1`; HEAD default and general builds: `5` (exit 0). `_top_bindings` walks both arms of a non-literal condition and applies `del` unconditionally.
2. `except ... as X` still leaves a previously bound `X` exported. `m.py`: `X = 1` / `try:` / `    raise Exception` / `except Exception as X:` / `    pass`; `main.py`: `from m import *` / `print("ok")`. CPython: `ok`; HEAD builds then raises `NameError: name 'm__X' is not defined` (exit 1). The handler name must delete any earlier binding; the new code only avoids adding it.
3. Non-literal false branches still make a global-only name look bound. `m.py`: `def setx():` / `    global X` / `    X = 1` / `if 1 > 2:` / `    X = 2`; `main.py`: `from m import *` / `print("ok")`. CPython: `ok`; HEAD builds then raises `NameError: name 'm__X' is not defined` (exit 1). Same for `for X in range(False)` and assigning `X` inside a handler that does not run.

Probe both builds with `bash ~/tools/cmp.sh`, add each fixed case to the tests, then commit. If a finding cannot be fixed safely, refuse the construct by name at compile time instead of leaving a silent wrong answer.

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
