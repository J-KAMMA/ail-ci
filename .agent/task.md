**Fix one pre-existing difference from CPython.** A reviewer of job `pre329` recorded these as already present before that job:

- Item 2: `del ps[-1]` on a list of tuples does not remove the element (`n6`, worker `p04/p08`).
- Item 3: no-try typed/nested deletion on the default build prints the message without the `IndexError:` prefix (`p01–p03`, `p05/p06`).
- Outer nested index `del xs[9][0]` still prints bare `IndexError` on the default build (`n4`; base identical).
- Other uncaught traps in the default no-text path now show raw trap wording: `KeyError: key error` vs CPython `KeyError: 'missing'` (`f5/f6`), `ZeroDivisionError: integer division by zero` vs `... or modulo by zero` (`f7`), `IndexError: bytes index out of range` vs `index out of range` (`f9`). Base printed only the class name for these, so they are pre-existing mismatches, not match→mismatch regressions.

**Unverified.** `test_ail_pre272`, `test_ail_files`, `test_ail_corpus_findings3` (not re-run per review rules); slice-delete probes; instruction counts (`perf_event_open` unavailable). Changed code is on the failure path only.

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre341.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
