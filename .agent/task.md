**Fix one pre-existing difference from CPython.** A reviewer of job `pre59` recorded these as already present before that job:

- `permutations(xs, None)` / `r=None` returns `[()]` instead of CPython's full permutations (`p1_basic`).
- float/str `r` accepted then `AIL internal error: out of memory`, exit 1 (`p5_types`); CPython raises TypeError.
- Literals `2**63`/`10**19` fail at compile with `integer overflow` (`p8_wide`).

**Tests on HEAD:** `test_ail_pre59` 23.5s ok; `test_ail_safetynet` 121.2s ok (2 modules, 0 failed). `update_manifest.py --check` rc=0.

**Claims:** negative-r fix on both builds — verified; `r==0`, `r>n`, empty pools still match — verified; typed path already checked in `itlib.PoolStream` — verified (`itlib.py:546`); commit/manifest/DEVLOG — verified; pitest probes absent — verified locally.

**Unverified:** the "283 remote branches" claim; instruction-count speed (perf_event_open denied; the added branch is O(1) per call, not per element); `--debug-dir` C comparison (flag produced no files in my runs; change is runtime-only with no codegen edits).
[cost $0.0000, opencode tokens {"total": 1470983, "input": 50491, "output": 8311, "reasoning": 12782, "cache.write": 0, "cache.read": 1399399}]
    tool time: bash 4.3 min
        123s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre59 test
         30s bash   date; cd /tmp/rprobes; for p in p1_basic p2_sources p3_catch p4_unrelated p5_types; do echo "=== $p"; bash ~/t
         28s bash   date; cd /tmp/probes; for p in open_perm_neg pre59_neg_r_basic pre59_neg_r_sources pre59_neg_r_bounds pre59_ne
         17s bash   cd /tmp/rprobes; for p in p1_basic p3_catch p5_types; do echo "=== BASE $p"; bash ~/tools/cmp.sh /tmp/rprobes/
         16s bash   cd /tmp/rprobes; for p in p1_basic p3_catch p5_types; do echo "=== HEAD $p"; bash ~/tools/cmp.sh /tmp/rprobes/
         11s bash   cd /tmp/rprobes; for p in p6_typedloop p7_direct_literal; do echo "=== HEAD $p"; bash ~/tools/cmp.sh /tmp/rpro
         10s bash   cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount /home/runner/work/ail-ci/ail-ci/tools/icount.c 2>
          6s bash   cd /tmp/rprobes && cat > p8_wide.py <<'PY' import itertools def show(tag, fn):     try: print(tag, list(fn()))

FINAL VERDICT: ACCEPT  2026-10-24T04:19:31Z

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre101.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
