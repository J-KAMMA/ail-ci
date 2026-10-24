**Fix one pre-existing difference from CPython.** A reviewer of job `rbfuzz94` recorded these as already present before that job:

`VERDICT: ACCEPT`
[cost $0.0173, opencode tokens {"total": 726050, "input": 60964, "output": 5526, "reasoning": 4840, "cache.write": 0, "cache.read": 654720}]
    tool time: bash 7.8 min
        343s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_fuzz
         37s bash   cd /tmp/rprobes && cat > immutable.py <<'EOF' class C:     def __init__(self):         self.v = 42         sel
         30s bash   for p in /tmp/probes/*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/a
         18s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 300 python3 -m unittest -v test_ail_fuzz94 2>&1 | ta
         13s bash   cd /tmp && for p in immutable module_def_mut mut_list; do rm -rf d1 d2 o1 o2; mkdir -p o1 o2; cp /tmp/rprobes/
          8s bash   for p in nested_class module_def_mut; do echo "== $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp/base 2
          8s bash   cd /tmp/rprobes && cat > mut_deep.py <<'EOF' def main():     for i in range(2):         def outer():          
          5s bash   cd /tmp/rprobes && cat > immutable.py <<'EOF' class C:     def __init__(self):         self.v = 42 def main():

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre117.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
