Lane: setord

# setord1: silent wrong: iterating a frozenset/set of ints prints a different order from CPython

Time budget: 90 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Why:** the owner's rule: any difference from CPython must be loud (a refusal by name or a documented
difference), never silent. The pyreach11 Opus agent found, on origin/integ (not caused by its change), that
iterating `frozenset(range(40, 0, -7))` inside a function prints a different order from CPython, in the default build
and with `AIL_UNIFIED_FORCE=1`. That is a silent wrong result.

**Do:**
1. Reproduce: `def f():\n    for x in frozenset(range(40, 0, -7)): print(x)\nf()` plus variants: `set(...)`, a set
   literal, `list(s)`, `sorted(s)` (must already match), `print(s)`, `for x in s` at module level, negative ints,
   ints past 2**31, str elements, mixed add/remove before iterating. Run each in both builds and with
   `python3 -X importtime` irrelevant; compare against CPython (`bash ~/tools/cmp.sh` or `.agent/cmp.sh`).
2. Find where order diverges (typed set table, general-path set, or the iteration lowering).
3. Fix: either iterate in CPython's exact order (CPython's int hash is the value mod 2**61-1 and its table probing
   and resize rules are fixed for a given insertion sequence; match them exactly, including after removals), or,
   where exact order cannot be guaranteed, refuse order-revealing iteration of a set by name with a rewrite hint
   (`sorted(s)`). Order-free uses (`in`, `len`, `sorted`, `min`, `max`, `sum`) must keep building.
4. Census: grep the test corpus and lab programs for set iteration that now changes behaviour; list them.

Files: the set runtime/lowering you find (search `frozenset`, set iteration in `pyfunc.py`, `collib.py`,
`cruntime.py`, `pyboxed2.py`), new `AIL_CURRENT/test_ail_setorder.py` + `AIL_CURRENT/tests.d/test_ail_setorder.txt`.
Tests: test_ail_setorder, test_ail_sets_general, test_ail_int_dict_set, test_ail_collections, test_ail_safetynet.
Report: the cause, which option you took and why, probes table (CPython vs both builds), programs affected.

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
