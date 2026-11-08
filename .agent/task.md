# pypy1: add PyPy to the rival table and the wedge benchmark

Lane: rival
Measurement only. Do not change the compiler. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap). Time budget: 90 minutes; commit and push after each sub-step.

Why: the owner decides whether AIL continues on one number, "is AIL clearly faster than PyPy on real Python code".
Neither `lab/compare_rival` nor `lab/wedge` has a PyPy column today.

## Sub-steps

1. `lab/compare_rival`: add a `pypy` row per task. Source `src/<task>/main.py`, run with PyPy 3.10 or 3.11
   (prebuilt tarball from downloads.python.org/pypy with its published sha256, or `actions/setup-python` with
   `pypy3.10`; record the exact version in `toolchains.env`). Same oracle, same perf input, median of 5, peak RSS.
   Compile time: none (write `-`); build disk: the PyPy install size, marked as interpreter. Also add a warm-up
   column: PyPy's JIT needs warm-up, so report both the plain wall time and the time of the 5th run in one process
   if the task driver allows it; if not, report plain wall time only and say so.
2. `lab/wedge`: add a PyPy arm to `measure.py` (run each corpus `run.py` under PyPy, check byte-identical output
   against the CPython expected file, median of 5). Re-run `report.py`; RESULTS.md gets PyPy/CPython and
   hybrid/PyPy and AIL-standalone/PyPy ratios.
3. Headline in both RESULTS.md files, one sentence each: on how many tasks/modules AIL (standalone and hybrid) is
   faster than PyPy, and the geometric-mean ratio. A PyPy output difference is a PyPy result, list it; do not fix
   sources for PyPy.

Files you may create or edit: `lab/compare_rival/**`, `lab/wedge/measure.py`, `lab/wedge/report.py`,
`lab/wedge/RESULTS.md`, `lab/wedge/*.json`, `.github/workflows/compare-rival.yml` if it exists there, and the
manifest files `tools/update_manifest.py` writes. Nothing under `AIL_CURRENT/` except the manifest.

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
