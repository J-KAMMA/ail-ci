# memsafe1: every compiled program must run clean under AddressSanitizer and UBSan

AIL compiles Python to C, so a memory-safety bug in generated code or in the C runtime is a security bug (out-of-bounds
write, use-after-free, integer UB). A few modules already build with sanitizers: see `SAN` and `AIL_EXTRA_CFLAGS` in
`AIL_CURRENT/test_ail_gcstress.py` and `test_ail_gcfix.py`. Extend that to a sweep.

1. Write `tools/san_sweep.py`: build each program the existing tests and examples compile (the case corpus the test
   modules use, `language_examples/`, and 200 programs from the differential fuzz generator the fuzz tests use) with
   `AIL_EXTRA_CFLAGS='-fsanitize=address,undefined -fno-sanitize-recover=undefined -g -fno-omit-frame-pointer'`, on both
   the typed and the general path where a program supports both, run it with the same input the test gives, and record
   every sanitizer report (program, path, first report line). It must finish within 20 minutes; sample if it would not.
2. Run it. For each distinct report: find the root cause in the generated code or runtime and fix it there (never by
   silencing the sanitizer, never by excluding the program). If a fix is too large, record it in docs/spec/DIFFERENCES.md
   as a known memory-safety defect with a reproducer, and say so in your report.
3. Add `AIL_CURRENT/test_ail_sanitize.py`: a fixed set of at least 40 programs covering what the sweep touched (strings,
   lists, dicts, slicing, int overflow paths, bigint, exceptions, closures, classes, file and stdin input) that must run
   clean under the sanitizers on both paths; register it like other test modules (tools/update_manifest.py).
4. Run `test_ail_sanitize`, `test_ail_gcstress`, `test_ail_safetynet` and every module whose code you changed.

Report: the number of programs swept, the reports found (distinct root causes), what you fixed, what is left.
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
