**Fix one pre-existing difference from CPython.** A reviewer of job `fuzz54` recorded these as already present before that job:

- `xs[10**20]`: AIL exits 1 with `integer overflow`; CPython raises `IndexError` on stderr (stdout/exit match).
- Huge ints (`10**30`) in mixed and homogeneous lists: both AIL builds exit 1.
- `format(True)` prints `1` instead of `True` (`p41`).

**Tests:** `test_ail_fuzz54`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` on HEAD: 4 modules, 0 failed in 247s.

**Claims:** commit, code description, registrations, manifest check (`--check` rc 0), and absence of DIFFERENCES/DEVLOG verified. The 7-module/463s and `test_ail_strict` results and the named /tmp probes were not reproducible here (not in tree), so unverified. One claim is inaccurate: the added `test_ail_fuzz54` program does **not** reproduce the bug on base — base's tuple pass hits an unrelated `AttributeError` and falls back, so the test passes without the fix. A forcing tuple is needed (above). This is a weak regression test, not a behavioural defect.

**Speed:** `perf_event_open` is denied in this runner, so icount failed. `program.c` is byte-identical between HEAD and base for `g00_008`, `g01_010`, `g01_034`, and for a no-feature program, so hot-code codegen is unchanged.

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre177.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
