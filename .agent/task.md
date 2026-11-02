Lane: docs

**Publish the language comparison table, wins and losses alike (owner decision 2026-11-02: 全部そのまま載せる).**

**What this changes:** a user can find AIL's measured standing against C, Rust, Go, Nim and Python from the README in one click. Today the README is only a CI-mirror note, and the table exists only as a compare-lab artifact.

1. Add `tools/compare_publish.py`. It reads a compare-lab `compare-report.json` (the report job's artifact) and writes `docs/COMPARISON.md`. The document contains:
   - the AIL commit and the date;
   - the per-task scorecard against Rust and against the best other language;
   - the geomean rows;
   - the toolchain versions;
   - the method section, unchanged.

   Every column goes in, wins and losses: instructions, RSS, binary size, compile time, build disk and wall time. The AIL (py src) table goes in too, with its refusals. Put no adjectives in the generated text, only numbers and W/L.
2. Generate `docs/COMPARISON.md` from the latest successful compare-lab run on integ. Find it with `gh run list -R J-KAMMA/ail-ci -w compare-lab --branch integ -L 1`, then download it with `gh run download <id> -n compare-report`. If the runner cannot download it, ask nothing. Commit the generator, and generate from a small fixture JSON that you write under `tools/testdata/` from the numbers below. Note the fixture in the doc header.

   Numbers from run 41393616319, commit 4f1245b. Each pair is AIL / Rust:
   - wall ms: berth_sim 2472/1470, chain_relax 1256/1037, echo_pack 934/1895, ledger_bin 840/2833, rail_transfer 862/48, scar_life 16696/29534, tally_lang 1548/1640, term_rank 2260/2925, ticket_audit 1887/4248, tree_fold 1866/1783;
   - binary KiB: AIL 34–102, Rust 4450–4518;
   - compile s: AIL 1.87–11.17, Rust 0.19–0.56;
   - RSS MiB, for the tasks where AIL loses: berth_sim 239.2/187.7, ledger_bin 337.0/273.8, tree_fold 464.6/314.9, echo_pack 346.1/344.6.
3. In README.md, add a short "How AIL compares" section linking docs/COMPARISON.md. Give one line per column with the win count against Rust, in the form "AIL is smaller in binary size on 10/10 tasks; slower to compile on 10/10". State it plainly.
4. Add a unit test for the generator on the fixture, register it through tests.d, and run `python3 tools/update_manifest.py`.

Commit and push after each sub-step.

**Stop rule:** do not edit any number by hand in the doc. Everything in it comes from the generator.

Time budget: 60 minutes.

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
