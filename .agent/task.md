**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
# Review Report

**Time:** started 10:03 UTC; probes finished before 10:30. No new runs after budget.

## What the change really does
Extends the LSP host (`packaging/ail_lang/lsp.py`) only: full-sync `didChange` (kind 1) checking buffer text, certain-only hover (annotation / single literal kind / function signature), a read-only-directory fallback using `AIL_PATH` with project lookup from the opened file, and temp-path remapping in messages. Adds `test_ail_lsp` cases and `docs/LSP.md`. It does not touch the compiler or runtime, matching the report.

## Fidelity of the re-apply
- `packaging/ail_lang/lsp.py`, `AIL_CURRENT/test_ail_lsp.py`, `docs/LSP.md` are **byte-identical** to `FETCH_HEAD` (source lsp1c job). Verified.
- `.github/workflows/agent-worker.yml` in HEAD is identical to `FETCH_HEAD` (already applied here). Verified.
- `manifest.d/66.txt` differs from `FETCH_HEAD` only in the `test_ail_list_ops.py` hash, which reflects this tree; `update_manifest.py --check` exits 0. Verified (regenerated, consistent).
- Changed files are only the five named; commit message ends with the required trailer. Verified.

## Tests (HEAD)
- `test_ail_lsp`: ok, 37 tests; the five read-only tests actually ran (uid 1001, not root). Verified.
- `test_ail_safetynet`: ok. Verified.
- `test_ail_files` / `test_ail_corpus_findings3`: not re-run by me (worker claims pass). **Unverified.**

## Probes
`/tmp/rprobes/hover_unit.py` (unit): all pass — int/float/str/bytes/bool/None; negative, complex, ellipsis, dict value, list item, attribute label and keyword label all return `None`; annotated arg; tuple unpack/aug-assign loop target absent; signature; conflicting annotations absent; incremental edit incl. UTF-16 astral range.
`/tmp/rprobes/lsp_e2e.py`: clean open, incremental `didChange` producing an error, full-replace clean, hover from unsaved buffer (`a`: `int`), attribute hover `null`, didClose+didSave hover from disk all pass. (One expected general-path Warning on a `class` without `__init__`.)
Compiler output: `plain.ail` compiled with `--debug-dir` on HEAD and `/tmp/base` gives identical `program.c` (sha256 `fbad0344…`); only temp paths in `native_report.json` differ.

## Claims in worker report
- Applied lsp1c/lsp1b to the four files — **verified**.
- `agent-worker.yml` already had the change — **verified**.
- `manifest.d/66.txt` regenerated, check clean — **verified**.
- `test_ail_lsp` 37 passed incl. R3 — **verified**.
- `test_ail_safetynet` 5 passed — **verified (module ok)**.
- `test_ail_files` 18/1 skip, `test_ail_corpus_findings3` 2 — **unverified** (not re-run).
- `tools/diff_ids.py` absent — **verified**.
- `cmp.sh` not applicable; no generated C changes — **verified**.
- Pre-existing `.agent/pipeline.md` left untracked — **verified**.

## Non-blocking observation
Hover on a name that is both assigned a literal and also defined as a function (`f = 1` + `def f(): ...`) reports the literal type even on the def line. This is inherent to the accepted upstream lsp1c logic (identical bytes), and the doc's rule ordering is ambiguous there; it is not a re-application error.

## Pre-existing
None found; the only base-vs-HEAD differences are temp-path strings.

## Speed
Not measured: the change is in the LSP host, which the compiler does not import (`cli.py` only from `cmd_lsp`); no hot code affected.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=31 out_tokens=23755]

## full suite
test_ail_argument_type_details
test_ail_check_repair_context
test_ail_collections
test_ail_source_check

## suite fix skipped: only 86 minutes left


--- ORIGINAL TASK ---
**Re-apply an accepted change on top of the current tree.** Job `lsp1c` was accepted, but its diff no longer applies here. Fetch it anonymously: `git fetch https://github.com/J-KAMMA/ail-ci.git job-lsp1c-11041449`. Its change is `git diff 2a3f77556559f340e97e2d40b253b67de63a231f FETCH_HEAD -- . ':!.agent' ':!corpus' ':!AIL_CURRENT/MANIFEST.json'`.

Apply the same change to this tree, resolving conflicts by keeping both sides' fixes. Then run `python3 tools/diff_ids.py` and `python3 tools/update_manifest.py`, run the test modules the change touches plus `test_ail_safetynet`, and commit. Change nothing else.

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
