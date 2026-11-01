**Decimal must work in the default int64 mode.** Since #284 ints are int64 by default and overflow stops. The Decimal prelude computes with 10 ** prec (prec 28), so `Decimal(1) / Decimal(3)` stops with "OverflowError: integer overflow in **" unless --exact-int is given. Decimal is a library; the user never asked for big ints, so this is wrong.

Fix: the Decimal (and Fraction, if it has the same problem) prelude code must use exact ints internally in every mode, while user code stays int64. Prefer the existing mixed / per-function exact-int machinery (intmode.py, bigcap.py) over a global switch. User-visible ints that come out of Decimal (int(d), d.as_tuple()) follow the user mode: they stop loudly if they exceed int64 in the default mode.

Acceptance:
- In the default mode these print the same as CPython: `Decimal(1)/Decimal(3)`, `Decimal("2").sqrt()`, `Decimal("10.50")*Decimal("3")`, `Decimal(2) ** 100`, `getcontext().prec = 50` then a division, `Decimal("1e30") + 1`.
- The tests marked exact only because of Decimal (test_ail_stdtop1) pass again without AIL_EXACT_INT=1.
- No change in run icount on lab/compare tasks that do not use Decimal: the generated C must be byte-identical for those tasks.
- Run the touched test modules plus test_ail_int64_default and test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
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
