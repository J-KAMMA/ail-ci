Lane: bench

**Add the Python compilers Codon, mypyc and Nuitka to compare-lab (owner, 2026-11-04).** AIL's claim is "write Python, get Rust-level speed and a small binary". So its real rivals are the tools that already compile Python. Today's table compares against C, Rust and the other languages, plus CPython, but not against these three. Find out where AIL stands against them.

1. **Find compare-lab.** Locate its runner, its task list and the workflow that runs it daily. Add the three tools as new columns:
   - Pin an exact version of each and install it in the runner job, not on the PC.
   - **Codon:** compile the task's Python source with `codon build -release`.
   - **mypyc:** compile with mypyc and run it through CPython. Record honestly that the result is a CPython extension and needs CPython.
   - **Nuitka:** build with `--standalone --onefile` for the binary and disk columns.
   - Every tool compiles the same `.py` source AIL compiles (the annotated version from onelangs4), with the same algorithm. Do not rewrite a task to help one tool.
2. **Check the output matches CPython** byte for byte on each task's test inputs.
   - If a tool cannot build a task, or prints something different, record that, with the error text or the first differing line. Count it as a loss, not as a skipped row.
   - Codon's int is 64-bit, as AIL's is. Note any task where that changes the output.
3. **Measure each task and tool:** wall time (median of 3), instruction count where the runner can count it, compile time, binary bytes, disk used by the build, and peak RSS. Use the method compare-lab already uses for the existing columns.
4. **Report the numbers.** Report the results as a table in `docs/` next to the existing comparison, with the tool versions and the date. Add one short paragraph saying, per metric, where AIL wins and where it loses. Do not change the compiler in this job.

Commit and push after each step. Keep a single process under 1.5 GB of memory (`ulimit -v 1500000` where it fits).

**Stop rule:** if a tool does not install on the runner within 15 minutes of trying, record why and go on with the other two.

Time budget: 80 minutes. If all three do not fit, finish one tool completely (install, check, measure, report) before starting the next.

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
