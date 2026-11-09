Lane: strrt

# nonbmp1: text above U+FFFF (emoji) must work, not stop

Time budget: 120 minutes. Follow `.agent/` rules.

**Found by vibe3 (2026-11-10):** AI-written AIL programs that read emoji input stop with
`AIL internal error: decode: a code point above U+FFFF in the 16-bit v2 runtime` (`todo_file` both seeds, `log_levels`
seed 1 public case). Python, Rust and Go handle the same input. Emoji in user text is ordinary in app-like programs,
so this is a correctness gap, not a niche.

1. Find where the v2 runtime fixes strings at 16-bit units (`AIL_CURRENT/python/pkg-v12/cruntime.py`,
   `pyboxed2.py`, `safetyrt.py`). Write a short note in the PR: options (32-bit units for strings that need it,
   chosen per string at decode time like CPython's flexible representation; or always 32-bit), their memory and
   icount cost on the existing string benchmarks.
2. Implement the option with no icount loss on ASCII/BMP-only programs (measure with `tools/icount.c`). Results must
   be CPython-identical for `len`, indexing, slicing, `ord`/`chr`, `encode('utf-8')`, `upper`/`lower` on emoji and
   mixed text.
3. Add tests with emoji input on stdin, in literals and from files; reuse `lab/vibe/programs3c/*todo_file*` as one
   case. Run the string tests, `test_ail_safetynet`, `tools/update_manifest.py --check`.

If step 2 does not fit the budget, land step 1 plus a loud, clear message (not "internal error") and stop.

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
