**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change does:** adds `lab/err/` (15 triggers, 108 compile runs, two model-fix-rate JSONs, a harness) and `docs/design/AGENT_ERRORS.md`; no compiler, runtime, test, or benchmark file is touched (`git diff --stat` is docs/lab only). So C output for programs not using "the feature" is trivially unchanged, and the speed check is N/A.

**Verified**
- No source change: `git diff work..HEAD -- AIL_CURRENT tools bench` is empty.
- Collection numbers reproduce: `compile_runs.json` = 108 runs (8 vibe + 100 gdev), and per-family vibe/gdev counts match the RESULTS table exactly.
- All 15 `Replace` strings occur exactly once in their trigger (byte-for-byte, indentation included), generated probes build and match CPython on both `g` and `d` builds (`cmp.sh`), and 14/15 lose their target message; 02 keeps it — exactly as claimed.
- Fix rates reproduce from JSON: original 56/75 = 0.75, rewritten 69/75 = 0.92. The four "changed after review" messages (02, 06, 10, 14) have final text in `fixrate_rewritten.json` and differing reply metadata, i.e. a real re-run, with 02 = 0/5 and 06/10/14 = 5/5.
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: all pass on HEAD (`3 modules, 0 failed`). `tools/update_manifest.py --check` rc=0. DEVLOG has today's dated entry; DIFFERENCES uses the `C?-job-err1-11071330-1` placeholder.
- Worker report claims are accurate.

**Pre-existing (not blocking):** trigger `01_stdin_buffer` itself does not match CPython on the base compiler (`/tmp/base`, unmodified): base prints nothing and exits 1 with `AttributeError: '_AilStdinBuffer' object has no attribute 'readline'`. This is the defect the message describes, not caused by this change.

**Unverified:** the per-module "5 OK / 18 OK / 2 OK" counts (par_check prints only per-module `ok`); I did not re-run the model, only cross-checked the saved replies/totals.

**Defects found (false statements in the delivered docs, contradicted by the change's own JSON):**
1. `lab/err/RESULTS.md:177` — "02 and 11 were not fixed by any reply." False: `fixrate_original.json` 02 attempt 3 is `fixed` (1/5), and `fixrate_rewritten.json` 11 is 5/5 `fixed`. It also contradicts the §3 table (11: 0.00→1.00) and §4 ("02 is the only one that does not [lose the message]"). Expected: "02 stays at zero; 11 is fixed by the rewritten text."
2. `docs/design/AGENT_ERRORS.md:21` — "48/55 replies fixed them." Actual 53/55 (56 fixed − 3 fixed among 02/07/11/14 = 53, over the other 11 messages × 5).
3. `docs/design/AGENT_ERRORS.md:179` — "02 and 11 are compiler defects … the typed path must learn the construct." Contradicted two lines earlier and by the measured 11: 0.00→1.00 on wording alone; only 02 needs an emitter change. This misdirects implementation step 2.
4. `docs/design/AGENT_ERRORS.md:120-121` — attributes the moved 0.00/0.00/0.40 messages to "(11, 12)"; 12 was already 1.00 and did not move. Expected 07, 11, 14.
5. `lab/err/RESULTS.md:128` says "four dead ends" but names three (07, 11, 14); the fourth movement is the 05/08 failure loss. Wording fix.

VERDICT: FIX
1. RESULTS.md:177 — expected "02 stays at zero; 11 is fixed by the rewritten text", actual "02 and 11 were not fixed by any reply" (data: 02 1/5 original, 11 5/5 rewritten).
2. AGENT_ERRORS.md:21 — expected 53/55, actual 48/55 (recomputed from `fixrate_original.json`: 56−3 fixed over 55 attempts).
3. AGENT_ERRORS.md:179 — expected only 02 is the compiler-side dead end, actual names 02 and 11 (11 measured 5/5 fixed).
4. AGENT_ERRORS.md:120-121 — expected "07, 11, 14", actual includes 12 (12 unchanged at 1.00).
5. RESULTS.md:128 — expected "three dead ends" (or list 05/08 as the fourth movement), actual "four dead ends" with three named.
[commandcode stop=end_turn turns=21 out_tokens=25254]


--- ORIGINAL TASK ---
Lane: errdesign

# err1: compiler messages an AI can act on: measure the fix rate per message, then design the rewrite (measurement + design only)

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Do not change the compiler. Output: `lab/err/*` and `docs/design/AGENT_ERRORS.md`.

**Why (owner, 2026-11-07):** vibe1 (`lab/vibe/RESULTS.md`, "AIL compiler errors") found that after almost every AIL
compiler error or "built on the general path" note, the model's next round did not fix it (fix rate 0.00 on 9 of the
top 10 messages). AIL is for vibe coding; a message that an AI cannot act on is a defect.

## Measure (`lab/err/RESULTS.md`)
1. Collect the compiler's refusal and fallback messages: grep the emitter/front end for the message builders, and run
   the compiler over the vibe programs, compare `main.py` and 100 gdev programs to get the messages that actually
   fire, with counts.
2. For the 15 most frequent: a small program that triggers it; ask the same model vibe1 used (`lab/vibe/run.py`'s
   model call path, same settings) to fix the program given only the message, 5 tries each. Record: fixed (types /
   builds and output matches CPython), changed but still blocked, made it worse. That is the per-message fix rate.
3. Classify why low-rate messages fail: names an internal symbol (`_ail_l1l`), says what is wrong but not what to
   write, points at the wrong line, the fix is not expressible in plain Python, needs a type annotation the model
   does not know the syntax for, etc.

## Design (`docs/design/AGENT_ERRORS.md`)
A message format for agents: location, one-sentence cause in the user's own names, a concrete replacement snippet
built from the user's code, and a `--json` form `{"code","file","line","col","cause","fix":{"replace_range","with"}}`
so an agent can apply it. Rewrite the 15 messages in that format (as a table: old, new); re-run step 2 on the
rewritten text (fed to the model as if the compiler had printed it) to show the new fix rate. Then split the
implementation into steps of at most 2 hours with files, tests and the number each moves, as ready-to-queue task text.

## Sub-steps
1. (70 min) Collection and fix-rate measurement. Commit, push.
2. (50 min) AGENT_ERRORS.md with rewrites, re-measured fix rate, step split. Commit, push.

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
