**Fix one pre-existing difference from CPython.** A reviewer of job `perf6` recorded these as already present before that job:

**No-feature check**: `nofeat.py` compiled to byte-identical `program.c` on HEAD vs base; output identical when linked with the new flag.

**Speed** (`bench/compare.py --app numeric_scale_binary --rounds 16 --base 2ecb2ae`): `ail/c 1.249 [1.242, 1.253] slower`, `ail/base 0.901 [0.892, 0.906] faster`; before was `1.371 [1.360, 1.382]`. ≥3% gain, non-overlapping ranges. Disassembly of `scale` confirms correct 2-wide vectorization with `c.n` induction preserved (no FMA, separate mul).

**Tests** on HEAD: `test_ail_float64_codec`, `test_ail_list_ops`, `test_ail_scalar_list_mutations`, `test_ail_ir_s3`, `test_ail_numeric_bindings`, `test_ail_builtin_syntax_forms`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 9 modules, 0 failed. `tools/update_manifest.py --check` passes.

**Claim check**: allocation/store change, codec `ail_alloc_raw`, `-fopenmp-simd`, before/after numbers, byte-identical output, probes and test list — all verified. Only nit: HEAD does now track `bench/results/*` (harness commit `561ac5c`), so the "left uncommitted" sentence no longer matches; harmless.

**Unverified**: wider suite (not allowed); non-x86/big-endian hardware (byteorder only simulated); gdev icount not run — the target app was measured directly instead, and no-feature C is unchanged.

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre108.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
