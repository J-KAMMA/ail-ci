Lane: diffaudit

# diffaudit1: re-check every open entry of DIFFERENCES.md on today's integ, each with a probe program

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** DIFFERENCES.md entries whose status has been re-checked by a committed probe program on
today's integ. Today 0. `DIFFERENCES.md` is a table `| id | area | difference | status |` with about 370 rows; on
2026-11-04, 17 rows had status `open`, and about 15 more had `refused`, `declared` or an empty status. Target: every
`open` row and every row with an empty status has a probe and a verdict, and the release notes can say how many
known differences remain. A row that is `open` but now matches CPython is stale; a row whose behaviour has changed
in another way is a finding (zero silent differences is a release goal).

Base: `origin/integ`. Files you may create or edit, and no others:
- `lab/diffaudit/*.py` (one probe per audited row), `lab/diffaudit/AUDIT.md` (new), `lab/diffaudit/audit.py` (new)
- `AIL_CURRENT/test_ail_diffaudit.py` (new) and `AIL_CURRENT/tests.d/test_ail_diffaudit.txt` (new, one line:
  `test_ail_diffaudit`)
- `DIFFERENCES.md`: ONLY the status cell of rows you proved stale (sub-step 3). No other change to that file.
- the manifest files that `tools/update_manifest.py` writes
Do not change the compiler or the runtime. A difference you find is recorded, not fixed.

## Sub-steps

1. **The list (10 min).** Write `lab/diffaudit/audit.py`. It parses `DIFFERENCES.md` and prints every row whose status
   cell (trimmed) is `open`, empty, `refused` or starts with `declared`, as `id | area | status`. Put the list, with
   its count per status, in `AUDIT.md`. Commit, push, and open the PR against `integ`.
2. **Probes (35 min).** Work through the `open` rows first, then the empty-status rows, then `refused`, then
   `declared`. For each row write `lab/diffaudit/<slug>.py` (the slug is the id with characters other than
   `[A-Za-z0-9_]` replaced by `_`), 5-30 lines, that shows the difference the row's text describes, using the row's
   own example where it gives one. Start the file with a comment that quotes the row id. `audit.py --run` builds each
   probe in the default build and with `AIL_UNIFIED_FORCE=1` (in a temp dir, `AIL_NO_CACHE=1`, timeout 120 s, at most 2
   builds at a time, `ulimit -v 1500000`), runs it, runs `python3` on it, and gives one verdict per build:
   - `still-differs`: AIL's output or exit status differs from CPython's in the way the row says;
   - `refused-as-said`: the build is refused, and the row says it is refused;
   - `now-matches`: stdout and the exit status equal CPython's (the row may be stale);
   - `differs-otherwise`: it differs, but not as the row says. This is a finding: put it at the top of `AUDIT.md` with
     both outputs;
   - `no-repro`: the row's text is not enough to write a probe; say why in one line.
   Where a row is about ints, add a second probe line with a value beyond int64 (rule 2). Commit and push every 10
   probes.
3. **Stale rows (10 min).** For each `open` or empty-status row with `now-matches` in BOTH builds, change only its
   status cell in `DIFFERENCES.md` to `fixed;lab/diffaudit/<slug>.py`. Leave `refused` and `declared` rows as they
   are, even when they now match; list them in `AUDIT.md` under "Owner to decide". Commit and push.
4. **Test and report (15 min).** Write `AIL_CURRENT/test_ail_diffaudit.py`, copying the build-and-compare structure of
   `AIL_CURRENT/test_ail_std_shlex.py`: for every probe with verdict `now-matches`, it asserts AIL equals CPython in
   both builds (a regression check); for every `still-differs` probe it asserts the build still succeeds or is still
   refused as recorded (so a fix shows up as a test to update, not silently). Skip when there is no C compiler. Keep
   the test under 4 minutes on one core: if it would be longer, test only the `now-matches` set. Register it
   (Appendix A rule 6) and run `python3 tools/par_check.py -j 2 test_ail_diffaudit`. Finish `AUDIT.md`: the table
   (id, area, old status, verdict default, verdict forced, probe file) and the counts. Commit, push, and wait for CI.

## Done-check

- Every `open` and empty-status row has a probe file and a verdict in `AUDIT.md`, or a `no-repro` line.
- `python3 AIL_CURRENT/test_ail_diffaudit.py` passes.
- `git diff origin/integ -- DIFFERENCES.md` changes only status cells, and only of rows proved `now-matches` in
  both builds.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

If a probe build hangs or uses more than 1.5 GB, mark it `timeout` and go on. Stop when 80 minutes pass: push what is
done, with the count of rows audited out of the total, and the `differs-otherwise` findings first.

## Appendix A: standing rules (Follow C:\Users\bluec\ail-work\agent-brief-rules.md)

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not
   edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--syntax python] [--strict] [--exact-int]
  [--debug-dir DIR]`. `-o` must not exist yet. The default build tries the typed path first; when it falls back it
  prints `note: ... built on the general path` on stderr. `AIL_UNIFIED_FORCE=1` forces the unified path.
- AIL is Python syntax plus optional annotations. Ints are int64 by default and overflow stops loudly;
  `--exact-int` gives exact ints. A row about `--exact-int` is probed with that flag as well.
- One test module: `python3 tools/par_check.py -j 2 test_ail_<name>`.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a row is about error text.

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
