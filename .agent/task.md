# wedge3b: more real libraries rewritten in Rust (breadth for wedge3)

Lane: wedge3b

Same method, rules and report format as wedge3 (read `~/agents/projects/ail/tasks/wedge3.md` if present, else
the summary here), but on two different libraries so the evidence is not from one hand-picked set:

| Pure Python | Native rewrite |
|---|---|
| pydantic v1 pure-Python (`pip install "pydantic<2" --no-binary pydantic` so it is not Cython-compiled): model validation of nested records | pydantic v2 (pydantic-core, Rust) |
| sqlparse: format and split a large SQL file | sqlglot with the Rust tokenizer (`sqlglot[rs]`), same parse/format work |

- Build the hybrid from branch `job-obs5-op1109` (observed-type work, not yet integrated):
  `git fetch origin job-obs5-op1109 && git worktree add ../obs5 FETCH_HEAD`, use `../obs5/AIL_CURRENT`; record its commit.
- Libraries are pip-installed into a venv at run time; never vendor their source. Pin versions in
  `lab/wedge3/wedge3b/requirements.txt`.
- Apply `ailc ext` (hybrid) to the library's hot module(s) copied into a temp dir; also run the observed-type
  recorder (`AIL_CURRENT/ail_observe.py`, docs/design/OBSERVED_TYPES.md on that branch) and report hybrid with and
  without observed kinds.
- Every workload's output must match CPython byte for byte; a mismatch is a bug report with a minimal repro.
- Times, median of 5, for: CPython, PyPy 3.10+ (same pure library), hybrid, native rewrite. Use `tools/icount.c`
  instruction counts too where the run is under ~30 s.
- Work under `ulimit -v 2500000`, one workload at a time. Time budget 3 h; commit and push after each library.

Report `lab/wedge3/wedge3b/RESULTS.md`: per library functions total/native, the four times, ratios hybrid/CPython,
hybrid/PyPy, hybrid/native, refusal reasons ranked by CPython time they cost, one honest headline sentence.
Commit only `lab/wedge3/wedge3b/**`.

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
