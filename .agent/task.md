# wedge3: real code, using libraries that were rewritten in Rust

> (2026-11-09) Build the hybrid from branch `job-obs5-op1109`, not from your base: it holds the observed-type work
> (obs1-obs5: methods, list returns, container params, C entry), which is not integrated yet. Do
> `git fetch origin job-obs5-op1109 && git worktree add ../obs5 FETCH_HEAD` and use `../obs5/AIL_CURRENT` for every
> hybrid build; record its commit in RESULTS.md. Also run the observed-type recorder (`AIL_CURRENT/ail_observe.py`,
> see docs/design/OBSERVED_TYPES.md there) on each library's workload and report hybrid with and without observed
> kinds. Commit only lab/wedge3/** on your own job branch.

Lane: hybrid-real


Up to now, every proof has used self-written code. This job measures the hybrid build (`ailc ext`) on real open-source
pure-Python libraries that the community rewrote in Rust because they were slow. Each pair is a measured
"Rust rewrite" baseline:

| Pure Python | Rust rewrite |
|---|---|
| networkx algorithms (shortest paths, pagerank) | rustworkx |
| jsonschema validation | jsonschema-rs |
| chardet | charset-normalizer / cchardet |
| tomli | rtoml |
| python-markdown or mistune | a Rust renderer (pulldown-cmark binding) |
| difflib / python-Levenshtein pure fallback | rapidfuzz |

Pick at least 5 pairs that install on Linux x86-64 from PyPI wheels.

## Rules

- **Do not vendor library source into the repository.**
  - lab/wedge3/ holds only the scripts, pinned versions (requirements.txt) and results.
  - Libraries are pip-installed into a venv at run time.
- **Hot paths:** use each library's own benchmark or a realistic workload that runs 1–5 s on CPython.
- **What to build:** apply `ailc ext` to the library's hot module or modules, copied into a temporary directory.
- **Output must not change:** the output of every workload must match CPython byte for byte. Any mismatch is a bug
  report with a minimal repro, not a result.
- Work under `ulimit -v 2500000`, one workload at a time.

## Report (lab/wedge3/RESULTS.md)

- Per library:
  - functions total;
  - functions native;
  - the time of CPython, PyPy 3.10+ (the pure-Python library run unchanged), the hybrid build and the Rust rewrite
    (medians of 5);
  - the hybrid/CPython, hybrid/PyPy and hybrid/Rust ratios.
- Refusal reasons, ranked by the CPython time they cost.
- 2-hour task texts for the top 5 reasons.
- One honest headline sentence: how far "compile it" is from "rewrite it in Rust" today.

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
