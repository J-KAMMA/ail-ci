# memsafe2: hostile input must not corrupt memory in compiled programs

Untrusted data reaches the C runtime through input parsing. Attack it the way a fuzzer would, with the sanitizers on
(`AIL_EXTRA_CFLAGS='-fsanitize=address,undefined -fno-sanitize-recover=undefined -g -fno-omit-frame-pointer'`; see
`AIL_CURRENT/test_ail_gcstress.py` for how tests build with it).

1. Write small AIL programs (typed and general path) that read stdin or a file and push it through the runtime's
   parsing and text paths: `int(s)` and `int(s, base)` (huge, signed, underscores, whitespace, non-ASCII digits),
   `float(s)`, `str.split/strip/replace/find/join/format/encode`, slicing with computed indices, `bytes`/`bytearray`
   ops, `ord/chr`, `json`-like hand parsing, dict keys from input, and reading very long lines and binary or invalid
   UTF-8 input.
2. Write `tools/input_fuzz.py`: a mutation fuzzer (Python only, no new dependencies) that feeds each program random and
   mutated inputs (empty, 1 MB lines, NUL bytes, invalid UTF-8, extreme numbers) for a fixed time budget, and records
   any sanitizer report, crash (signal), hang (>10 s), or output that differs from CPython running the same program.
   Seeded and reproducible.
3. Fix every root cause in the runtime or the generated code. A differing output that is a documented difference is
   fine; anything else is a bug: fix it or record it in docs/spec/DIFFERENCES.md with a reproducer.
4. Add `AIL_CURRENT/test_ail_hostile_input.py` holding the programs and the crashing or differing inputs found
   (each as a regression case) plus a short seeded fuzz run (under 3 minutes); register it (tools/update_manifest.py).
5. Run it, `test_ail_safetynet`, and every module whose code you changed.

Report: inputs tried, findings by root cause, fixes, what is left.
Do not edit benchmark sources or expected outputs to make anything pass.

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
