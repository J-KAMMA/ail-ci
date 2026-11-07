Lane: spec

# spec1: first draft of the AIL language specification (docs/SPEC/), with CPython-identical behaviour as a mode

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Docs only: do not change the compiler. Files: `docs/SPEC/*` (new), `docs/ROADMAP.md` (the "What AIL is for"
section only).

**Why (owner, 2026-11-07):** "we fit today's world too much; aim to be the future standard language". Decision:
the surface syntax stays Python (AIs write it best), but AIL's semantics are AIL's own, written down; "same output
as CPython" becomes a compatibility mode, not the definition. Any place AIL differs from CPython must be loud (a
refusal by name or a documented difference), never silent.

## What to write
1. `docs/SPEC/README.md`: purpose, the rule above, how the spec is versioned, and the list of chapters.
2. Inventory first: collect every semantic decision already made and scattered across the repo (grep docs/, docs/design/,
   docs/CLI.md, the compiler's refusal messages, and decisions recorded in docs: int64 default with loud overflow and
   explicit big ints, exact tagged None, fixed float sum order for arrays, recursion without CPython's 1000 limit but
   loud RecursionError, race rules D1-D5 (refuse shared int +=, ordered list buffers, keep GIL), dict views as
   snapshots refused, str vs bytes never compare, etc.). Each becomes a numbered rule with its source file.
3. Chapters (one file each, short; each rule: statement, example, what CPython does if different, status
   implemented / partly / planned, and the test or doc that proves it):
   values and types (int, float, bool, str, bytes, None, containers, records/classes); arithmetic and errors;
   evaluation order and determinism; memory and ownership (what is observable: aliasing, copies, identity);
   concurrency; modules and FFI; errors and diagnostics (the agent-readable format, see docs/design/AGENT_ERRORS.md if
   present); compatibility mode (what `--compat cpython` or the current default guarantees).
4. `docs/SPEC/OPEN.md`: the open questions where the spec must choose (for example: is `int` arbitrary precision or
   int64 by default in the spec itself; are dict iteration order and float formatting part of the spec; class
   semantics: monkey-patching, `__dict__`, dynamic attributes; `is` on values; exceptions as values or control flow;
   contracts and effect declarations syntax inside Python syntax: decorators, annotations, `assert` forms). For each:
   options, what each costs (speed, safety, AI-writability), and a recommendation. Mark them "owner decision".
5. Update the "What AIL is for" section of docs/ROADMAP.md with two sentences on the future-standard goal and a link.
   Keep any number another doc cites (test_ail_docs_why checks docs/WHY.md sources).

## Sub-steps
1. (50 min) Inventory + README. Commit, push.
2. (50 min) Chapters. Commit, push.
3. (20 min) OPEN.md + ROADMAP sentence; run test_ail_docs_why and any docs tests. Commit, push.

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
