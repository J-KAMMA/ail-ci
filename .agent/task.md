**Fix one pre-existing difference from CPython.** A reviewer of job `pre211` recorded these as already present before that job:

- `p4_collide`: method name collides with a module function (`def run` + `class C: def run`). Default build exits 1, no `caught ValueError 'negative shift count'` / `valid 8`; general build matches. Same on base.
- `p5_dupname`: two classes define the same method name, one calling `shl`. Default build misses the handler; same on base.
- `p9_methodalias`, `p11_classval`: bound method stored as value / in list gives `AttributeError: 'C' object has no attribute 'run'` on both builds and both trees (unsupported method values, unrelated).

**Unchanged C:** `p10_nofeature`, `p12_classonly`, `p6_uncaught`, and gdev `g13_018`, `g12_036`, `g06_032` produced byte-identical `--debug-dir/program.c` on base vs HEAD; no runtime instruction-count impact expected.

**Tests:** `test_ail_pre211.py` and `test_ail_safetynet.py` pass on HEAD (2 modules, 0 failed). `update_manifest.py --check` exits 0. Commit `bc4efd4`, DEVLOG/DIFFERENCES additions match the diff.

**Claims:** r11 default-only + `AIL_NO_MIX=1` matches, r9 refused on both builds, and the fix location are verified. Worker's `pre109`, `files`, `corpus_findings3`, `mixed_bounds`, `flush_exit`, `bugs7` results were not re-run (review scope) — unverified.

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre237.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
