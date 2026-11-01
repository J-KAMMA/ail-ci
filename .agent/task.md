**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** `tuplib.py` now records call-site argument types for unannotated parameters (positional and keyword), keeps an agreed tuple-containing type by spelling it as an annotation to force the typed path, re-runs lowering up to 4 rounds, and guards parameters the body rebinds and functions with unsettled tuple returns. Runtime/C is untouched.

**Probes (30, /tmp/rprobes/tup):** 25 match CPython on both builds. 5 differ on HEAD but match on base (`/tmp/rbase`), i.e. caused by this change. Worker's `v01`–`v11` re-run: 11/11 match on both builds. `a4` (required kw-only) is a named refusal; `c13` is a CPython `SyntaxError`.

**Defects (HEAD differs, base matches):**

1. Default argument values are not considered by inference.
```
def g(t="x"):
    return t
def main():
    print(g((1, "a")))
    print(g())
main()
```
Expected `(1, 'a')` then `x`, rc 0. Actual `(1, 'a')` then `IndexError: string index out of range`, rc 1. Same with `def g(t=None)` (expected `None`, actual `TypeError: 'NoneType' object is not subscriptable`). The sole call site `g((1,"a"))` annotates `t` as `(int,str)`, so the default is stored/returned as a tuple class.

2. `return None` / bare `return` is dropped before the mixed-return guard.
```
def g(t, flag):
    if flag:
        return t
    return None
def main():
    print(g((1, "a"), True))
    print(g((1, "a"), False))
main()
```
Expected `(1, 'a')` then `None`, rc 0. Actual `(1, 'a')` then `TypeError: 'NoneType' object is not subscriptable`, rc 1. `seen = [t for t in self.rets if t not in (None, 'none')]` hides the `None` path, so `rets_out` is set to the tuple and `mixed_ret` is never consulted. Same for `return` with no value and for `return t[0], t[1]` on the other branch (`c1`, `c2`, `d5`).

**Claims:**
- Reassignment guard: verified (`b2`/`b3`/`b4`, `v01`–`v05` match; inferred type not used).
- Mixed tuple return guard: **false for `None`/bare `return`** (defect 2); verified for non-`None` mixed returns (`c3`, `v06`–`v10`).
- Tests: verified, 6 modules, 0 failed (`test_ail_tuple_reach`, `test_ail_tuples`, `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
- `update_manifest.py --check`: verified (clean).
- lab/compare C: verified — 17 builds byte-identical, the 3 `.py` failures identical on base.
- p07/r06: unverified (not re-run).
- No pre-existing differences found; runtime ownership not touched, so no extra 4b probe needed. Speed not relevant (generated C identical on the lab corpus; compile-time-only change).

VERDICT: FIX
[cost $0.0276, opencode tokens {"total": 1191378, "input": 84682, "output": 7051, "reasoning": 12285, "cache.write": 0, "cache.read": 1087360}]
    tool time: bash 10.0 min
        247s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 700 python3 ../tools/par_check.py -j 2 test_ail_tup
        169s bash   cd /tmp && rm -rf lc_head lc_base && mkdir -p lc_head lc_base W2=/home/runner/work/_temp/w2 run() { local wt=$
         82s bash   date; cd /tmp/rprobes/tup && rm -f /tmp/rprobes_tup_head.log; for p in *.py; do echo "=== $p"; bash ~/tools/cm
         30s bash   date; cd /tmp/probes && for p in v0*.py v1*.py; do r=$(bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/_t
         25s bash   cd /tmp && rm -rf lc_head lc_base && mkdir -p lc_head lc_base W2=/home/runner/work/_temp/w2 run() { # wt outdi
         19s bash   for p in c1_mixed_none_annotated c2_return_none_bare d1_default_str d3_default_none d5_mixed_none a4_kwonly c1
         10s bash   for p in c1_mixed_none_annotated c2_return_none_bare d1_default_str d3_default_none d5_mixed_none; do d=$(mkte
          9s bash   date; cd /tmp && for p in b2_loop_rebind b3_aug_rebind b4_nested_rebind a2_method c1_mixed_none_annotated d1_d


--- ORIGINAL TASK ---
**Coverage: heterogeneous tuples.** Tuples mixing types, e.g. (int, str, float), returned from functions, unpacked, stored in lists and dicts, compared and sorted, used as dict keys. Measure 25 probe programs: refused / general / typed, write docs/design/TUPLE_REACH.md, then make the top pattern build on the typed path. Acceptance: compare stdout and exit code with CPython on your own boundary probes; the generated C of the 10 lab/compare tasks must stay byte-identical unless the task is about them; add tests (register new modules in tests.d), run them plus test_ail_safetynet, run `python3 tools/update_manifest.py`, commit.

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
