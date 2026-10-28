**Build a small language server for AIL (diagnostics only).**

Add `tools/ail_lsp.py`: a Language Server Protocol server over stdio, Python standard library only (no pip packages). It handles `initialize`, `initialized`, `shutdown`, `exit`, `textDocument/didOpen`, `didChange` (full sync), `didSave` and `didClose`. On open/save (and on change, debounced to 500 ms) it writes the document to a temporary file and runs the compiler's check on it (`python3 AIL_CURRENT/ail_chatgpt.py check <file> --syntax python`; read `ail_chatgpt.py`'s `check` parser for the exact flags and output format). It turns each refusal or error the compiler prints into an LSP `Diagnostic` with the right line and column (the compiler's messages carry a position; find the format in `ail_source_context.py` / the check output), severity Error, source `ail`. A clean check publishes an empty diagnostics list. Never execute the user's program.

Add `AIL_CURRENT/test_ail_lsp.py` (register it in `ail_check.py` MODULES) that starts the server as a subprocess, speaks JSON-RPC with Content-Length framing, opens one clean file and one file with a known refusal (pick one the current compiler refuses by name), and checks the published diagnostics (empty for the clean file; one diagnostic with the expected line for the other), then shuts down cleanly.

Add a short section "Editor support" to `README.md` saying how to start it. Run `python3 tools/update_manifest.py`, run only `test_ail_lsp` and `test_ail_safetynet`, then commit. Do not change the compiler.

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
