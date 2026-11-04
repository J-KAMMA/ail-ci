**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 0
[model commandcode/deepseek-v4.1-flash]
I've reviewed the re-application, compared it byte-for-byte with the accepted job, and run the targeted tests plus my own probes. Here is the report.

## What the change really does

Documentation + test only: adds `docs/guide/` (README + 4 chapters, 43 samples), `AIL_CURRENT/test_ail_guide.py` (builds/runs every sample, compares stdout+exit with CPython), registers `tests.d/test_ail_guide.txt`, removes the `GH_MODELS_TOKEN`/`ghm.key` plumbing from `.github/workflows/agent-worker.yml`, adds a DEVLOG entry, regenerates `manifest.d/51.txt`+`94.txt`. No compiler, runtime, or I/O change. This matches the report.

## Fidelity to the accepted change

All 8 changed content files (`docs/guide/*.md`, `test_ail_guide.py`, `tests.d/test_ail_guide.txt`, `agent-worker.yml`) are byte-identical to `b796a01..job-guide1-11041926`; both `manifest.d` files are identical too. The only extra file is the required DEVLOG entry. Manifest `--check` exits 0.

## Tests on HEAD (`-j 2`)

`test_ail_guide` + `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3`: 4/4 OK, 0 failed (902 s). `test_ail_guide` alone: `Ran 45 tests ... OK`, `guide samples: 43`.

## My probes (`/tmp/rprobes/`, HEAD vs `/tmp/rbase` = `work`)

| probe | result |
|---|---|
| p1 provenance overflow (list item, attribute, dict value) | documented `OverflowError ... --exact-int gives exact ints`, exit 1; identical on base |
| p2 typed list/floor division (feature not used) | same stdout/exit as CPython, both builds |
| p3 uncaught ZeroDivisionError | same stdout, exit 1 as CPython |
| p4 argv IndexError (no args) | same stdout, exit 1 as CPython |
| p5 list/bytes slice then mutate source | same stdout as CPython |

Generated C for p2 is identical HEAD vs base after normalizing the temp-dir path in `AIL_DBG_SITE`.

## Report claims

- 43 samples / 45 guide tests / docs set — **verified**
- workflow patch applied cleanly, identical to accepted — **verified**
- `tools/diff_ids.py` absent — **verified**
- no DIFFERENCES row needed (no compiler/runtime change) — **verified**
- `update_manifest.py --check` passes — **verified**
- 4 modules pass — **verified**
- 22 probes — **partially verified**: 22 `p_*.py` exist in `/tmp/probes`; I did not re-run the worker's probes. Note the DEVLOG entry says "Probes (17 ...)", which contradicts the report's 22.

Not checked: individual test counts of the three non-guide modules; the worker's probe outputs.

**Pre-existing:** none affecting the compiler. `p1` divergence from CPython is the documented int64-stop behaviour and is identical on the base. `.agent/pipeline.sh` still mentions `ghm.key` (dead branch, outside the diff scope and present in the accepted change).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=33 out_tokens=12922]

## full suite
test_ail_argument_type_details
test_ail_check_repair_context
test_ail_collections
test_ail_source_check

## suite fix skipped: only 127 minutes left


--- ORIGINAL TASK ---
**Re-apply an accepted change on top of the current tree.** Job `guide1` was accepted, but its diff no longer applies here. Fetch it anonymously: `git fetch https://github.com/J-KAMMA/ail-ci.git job-guide1-11041926`. Its change is `git diff b796a01aaa75c91908e7c1bed5f009f6c45adb81 FETCH_HEAD -- . ':!.agent' ':!corpus' ':!AIL_CURRENT/MANIFEST.json'`.

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
