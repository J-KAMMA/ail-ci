Lane: emitdesign

# emit1: why AIL's typed C executes more instructions than hand-written C, and a design to emit leaner C (measurement + design only)

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Do not change the compiler. Output: `lab/emit/*` and `docs/design/EMIT_LEAN.md`.

**Why (owner, 2026-11-07: subtract before adding):** roof1 (`lab/roof/RESULTS.md`, section "Subtraction") found that
54-100% of the typed path's extra instructions over C are in the `other` class: the shape of the emitted code
(temporaries, reloads, one statement per Python operation), not checks. `ticket_audit` executes 5.4x C's
instructions, `echo_pack` 2.9x, `tree_fold` 2.0x, `ledger_bin` 1.9x, `tally_lang` 1.7x.

## Measure (`lab/emit/RESULTS.md`)
Reuse `lab/roof/attrib.py`. For those five programs plus `berth_sim`: take the 10 hottest emitted functions, put the
emitted C next to the matching hand-written C (`lab/compare/src/<task>/main.c`), and sub-classify the `other`
instructions by cause, with Ir per cause: e.g. struct/string passed by value, temporaries that block register
allocation (address taken), repeated loads through a pointer gcc cannot prove unaliased, helper calls not inlined
(and why: size, `noinline`, separate unit), generic helpers where a specialised loop exists (string building,
byte parsing, dict probe), redundant length/cap reloads, int<->float or width conversions, exceptions/unwind state
checks after calls. Show 2-3 concrete before/after C snippets per cause, and for each cause the Ir if it were removed
(measure by hand-editing the emitted C in a throwaway copy, rebuilding with the same flags, and checking stdout
byte-identical: that is the real bound, not an estimate).

## Design (`docs/design/EMIT_LEAN.md`)
Rank the causes by measured Ir saved across the six programs. For the top 3: what in the emitter (file:function)
produces it, the change, how correctness is proven (CPython-identical on the corpus via `.agent/cmp.sh`, icount no
loss on any compare program), and its interaction with exe bytes (allowed to change). Split each into implementation
steps of at most 2 hours with its own files, test and number, written as ready-to-queue task text at the end.

## Sub-steps
1. (70 min) Sub-classification + hand-edit bounds in RESULTS.md. Commit, push.
2. (50 min) EMIT_LEAN.md with ranking and step split. Commit, push.

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
