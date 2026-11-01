**Measure first: would a fast C compiler (tcc) for development builds close the cold-compile gap with Rust? (owner request 2026-11-01).** This task measures and prices only. Do not change any default.

Background: AIL loses to Rust on cold compile time, 4.3–4.8 s against 0.4–0.5 s, on the 10 lab/compare tasks. The idea is a dev build mode that compiles the generated C with tcc (TinyCC). Release builds stay on gcc -O2.

**Step 1, setup.** Install tcc in the runner. Use `apt-get install tcc`, or build tinycc from source if the package is missing or too old. Record the version.

**Step 2, compile-time breakdown.** For each of the 10 lab/compare tasks, measure a cold build with the current default (gcc -O2). Split the wall time into:
- the AIL front end, meaning Python up to the emitted C;
- the C compile;
- the link.

Use `time`, plus the compiler's own timing if it has any. Give the median of 5 runs. This share decides what any C compiler swap can win at most, so state the Amdahl bound per task (the speed-claims rule).

**Step 3, tcc build.** Compile the same generated C with tcc and link it. Record for each task:
- whether it compiles at all. If not, give the first error. Our C may use GCC extensions such as vector extensions, `__builtin_*` or statement expressions. List each one and say whether it can be guarded with `#ifdef __TINYC__` and a portable fallback;
- the C compile time and the total build time against gcc -O2;
- the run time of the tcc binary against the gcc -O2 binary;
- whether stdout and the exit code are identical to the gcc build on the task's inputs. Also run the task's own checks.

**Step 4, the front end.** If Step 2 shows the front end dominates, a C compiler swap cannot reach Rust's time. In that case also measure the existing resident server mode (#300, now the default after srvdef1): its cold and warm builds with gcc and with tcc. Say which combination gets closest to 0.5 s.

**Step 5, the report.** Write docs/design/TCC_DEV.md. End it with:
- the per-task table;
- the bound against the measured gain;
- the list of GCC-only constructs and the cost of the guards;
- a recommendation: build a `--dev` tcc mode or not, and what else would be needed to reach about 0.5 s cold.

Rules:
- Note the runner noise: give medians and spreads.
- Do not change default compiler behaviour or any test expectation.
- Commit the doc and the measurement scripts, kept under lab/tccdev/.

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
