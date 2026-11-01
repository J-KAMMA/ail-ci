**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
Review of `work..HEAD` (78e47ce + 5870fc0 + b3458ec), no edits made.

**What the change does.** Extends the `Counter.subtract` fixes: infers plain dicts/comprehensions and their `keys()/values()/items()`, keeps module-level dicts and unannotated `self.field` dicts in the type environment, routes ChainMap arguments through `items()` (typed `for` loop or new `ail__counter_subtract_pairs`), adds key/value checks for Counter/defaultdict/OrderedDict stores and `update`, and sends untypable `subtract` arguments to a named refusal. The report describes this, but omits the new `chainmap_call` name-binding logic and the new refusals for previously buildable unknown-argument calls.

**Probes** (`/tmp/rprobes`, `cmp.sh`, g+d). HEAD matches CPython on both builds: p_review (r3/r7/r9/r10), p_chainmap (direct, duplicate maps, empty), p_cmname, p_cmtuple, p_cmalias, p_cmfloat, p_argdict, p_container, p_selfattr, p_views, p_emptyctr, p_alias, p_negempty, p_float, p_bool, p_dictcompname, p_stores, p_keyrepr*/p_storerepr*/p_updaterepr*, q_listdict/q_values/q_items/q_dictcomp/q_mutate. Named refusals (acceptable): p_argcm (base silently wrong), p_dictcall, p_unkmap, p_unkiter, p_unkdrop, p_unkexpr, p_argplain.

New refusals where base built and matched: p_unkiter (`c.subtract(ident([...]))`), p_unkexpr (`c.subtract("aab".split("b"))`, `c.subtract(tuple("aab"))`). These are named refusals, so not blocking, but they falsify the report's "left to the general path" claim.

**Defect (new).** A ChainMap reaching the newly lowered name path through more than one assignment is checked against the *last* assignment but executed with the runtime value. In a branch, the check passes on int keys while the runtime map has str keys, and the raw `subtract_chainmap` loop stores a str key in an int-typed Counter, printing it unquoted:
```python
from collections import Counter, ChainMap
def main() -> int:
    c = Counter({1: 2})
    cm = ChainMap({"a": 3})
    if len(c) == 2:
        cm = ChainMap({1: 4})
    c.subtract(cm)
    print(c)
    return 0
main()
```
expected `Counter({1: 2, 'a': -3})`; actual `Counter({1: 2, a: -3})` (both builds). Base gives `Counter({1: 2, 'a': -1})`, also wrong but differently, so this is not a pre-existing identical difference; the new name lowering introduced the unquoted-key output. Same with a plain reassignment after the call (`p_cmreassign`). `chainmap_call` should refuse when a name has more than one binding (or the binding is not the immediate one).

**Report claims.** Defect 1/2 fixed: verified by p_review/p_chainmap. "Key switches are named refusals": not observed — `Counter({1:2})` with a str key via `subtract`/`update`/`c[k]=v` builds and matches CPython's quoted repr (outcome correct, wording false). "Only pre-existing q25/l4 differ": false (p_cmbranch, plus the new refusals above). Tests: `test_ail_std_collections`, `test_ail_safetynet`, `test_ail_collections`, `test_ail_tuples` all pass on HEAD under `-j 2`; manifest `--check` exits 0. Compare C spot-checked `berth_sim`, `term_rank`, `ticket_audit`: `program.c` byte-identical to `/tmp/base` (other 7 unverified).

**Pre-existing** (same on base): p_argplain refusal. **Unverified:** the other 7 compare tasks, `test_ail_deqctr`/`test_ail_files`/`test_ail_corpus_findings3`, and speed (no hot runtime path added; helpers are emitted only when used).

VERDICT: FIX
1. `Counter.subtract(cm)` silently stores a str key in an int-typed Counter when `cm` has multiple assignments and the last one matches the Counter but the runtime one does not (`p_cmbranch`, `p_cmreassign`): expected `Counter({1: 2, 'a': -3})`, actual `Counter({1: 2, a: -3})`; refuse such a name by name or bind only a single assignment.
[cost $0.0369, opencode tokens {"total": 1652894, "input": 70754, "output": 10469, "reasoning": 25687, "cache.write": 0, "cache.read": 1545984}]
    tool time: bash 9.1 min, write 0.0 min
        186s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1400 python3 ../tools/par_check.py -j 2 test_a
        128s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
         65s bash   cd /tmp/rprobes && for f in p_*.py; do echo "######## $f"; bash ~/tools/cmp.sh /tmp/rprobes/$f /home/runner/wo
         25s bash   cd /tmp/rprobes && for f in q_listdict.py q_values.py q_items.py q_dictcomp.py q_mutate.py; do echo "######## 
         19s bash   cd /tmp && rm -rf cdiff && mkdir -p cdiff/h cdiff/b for t in berth_sim term_rank ticket_audit; do   python3 /h
         17s bash   cd /tmp/rprobes && for f in p_emptyctr.py p_dictcall.py p_updatekey.py p_bool.py p_dictcompname.py; do echo "#
         16s bash   cd /tmp/rprobes && for f in p_unkiter.py p_unkmap.py; do echo "#### $f"; for wt in /home/runner/work/ail-ci/ai
         14s bash   cd /tmp/rprobes && for f in p_cmfloat.py p_cmtuple.py p_cmname.py p_cmalias.py; do echo "######## $f"; bash ~/


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `collections` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `collections` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/collections/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/collections/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_collections.py registered in tests.d), and compare them with CPython in the test.
- Run that test plus test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

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
