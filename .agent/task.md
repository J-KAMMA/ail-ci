**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
Review of `work..HEAD` (8eb3b05 + 01cf961), no edits made.

**What the change does.** Adds `Counter.subtract` lowering (typed helpers in `collib.py`, boxed runtime in `pyboxed2.py`), a tuple-keyed-mapping route for `Counter(...)` in the tuple pass, annotated `self` fields in `collib`, plus 12 lab programs and a test. This matches the report except that the subtract lowering is far broader than the two reported forms.

**Probes** (`/tmp/rprobes`, `cmp.sh`, both `g` and `d`):

| probe | CPython | AIL | base |
|---|---|---|---|
| r1 zero-arg subtract, caught | matches | matches | refused |
| r2 two-arg subtract | — | refused by name | refused |
| r3 `subtract({k:2 for k in ["a","b"]})` | correct | **wrong** | refused |
| r5 tuple-keyed dict via attr/list/dict value | correct | matches | refused |
| r6 `Counter` of dict comprehensions | correct | matches | built |
| r7 `for d in [{"a":2}]: c.subtract(d)` | correct | **wrong** | refused |
| r9 module-level `G` subtract | correct | **wrong** | refused |
| r10 tuple-keyed dict comprehension subtract | correct | **wrong** | refused |
| r11 `Counter(OrderedDict/defaultdict)` | — | refused by name | refused |
| r12 `Counter(tuple-keyed table via attr/list/dict value)` | correct | matches | built |
| r15 `c.subtract(ChainMap(...))` | correct | **wrong** | refused |

Base refuses every subtract probe that HEAD now gets wrong, so these are introduced.

**Defects**

1. `subtract` of a mapping that is not a dict display or a simple dict-bound name is treated as an iterable (subtract 1 per key instead of per value).
```python
from collections import Counter
def main() -> int:
    c = Counter("aab")
    c.subtract({k: 2 for k in ["a", "b"]})
    print(sorted(c.items()))
    return 0
main()
```
expected `[('a', 0), ('b', -1)]`; actual `[('a', 1), ('b', 0)]` (both builds). Same defect for a loop variable (`r7`: expected `[('a', 0), ('b', 1)]`, actual `[('a', 1), ('b', 1)]`), a module-level dict (`r9`: expected `[('a', 0), ('b', 0)]`, actual `[('a', 1), ('b', 0)]`), and a tuple-keyed dict comprehension (`r10`: expected `[((1,1),-2),((1,2),5),((2,2),-2)]`, actual `[((1,1),-1),((1,2),5),((2,2),-1)]`). `mapping_arg` only recognises `ast.Dict`/a name whose own assignments are all dict literals; other mapping expressions fall through to the iterable helper. Base refused these by name, so either handle or refuse them.

2. `subtract` of a `ChainMap` iterates its keys:
```python
from collections import Counter, ChainMap
def main() -> int:
    c = Counter("aab")
    c.subtract(ChainMap({"a": 2}, {"b": 3}))
    print(sorted(c.items()))
    return 0
main()
```
expected `[('a', 0), ('b', -2)]`; actual `[('a', 1), ('b', 0)]` (both builds). Base refused.

**Report claims**
- Defect 1 (dict displays, unannotated names, `dict()`, attributes, list items, dict values): verified for those forms.
- Defect 2 (tuple-keyed tables): verified for literals, names, attributes, list items and dict values; `Counter(...)` and `subtract` both match.
- "23/24 probes match, p21 refused": consistent, but the probe set does not cover the failing mapping forms above.
- Compare C: spot-checked `berth_sim`, `chain_relax --exact-int`, `ticket_audit` — byte-identical to `/tmp/base`.
- Tests: `test_ail_std_collections`, `test_ail_safetynet`, `test_ail_collections`, `test_ail_tuples` all pass on HEAD. Manifest `--check` exits 0.

**Pre-existing** (identical on base): `Counter(ChainMap)` and `Counter(module-level dict)` count keys instead of values (`r13`, `r14`).

**Unverified:** the other 4 compare tasks, `test_ail_deqctr`/`test_ail_files`/`test_ail_corpus_findings3`, and speed (no hot path is touched; helpers are emitted only when used).

VERDICT: FIX
1. Newly built `Counter.subtract` silently drops mapping values for dict comprehensions, loop variables and module-level dicts (`r3`, `r7`, `r9`, `r10`): handle them as mappings or refuse by name.
2. Newly built `Counter.subtract(ChainMap)` iterates keys (`r15`): treat every mapping type as a mapping or refuse by name.
[cost $0.0262, opencode tokens {"total": 1377479, "input": 54862, "output": 6068, "reasoning": 17349, "cache.write": 0, "cache.read": 1299200}]
    tool time: bash 10.9 min
        242s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_collections test
        173s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_collections 
        143s bash   cd /tmp && rm -rf rcdbg && mkdir -p rcdbg/head rcdbg/base for task in berth_sim chain_relax ticket_audit; do  
         32s bash   cd /tmp/rprobes && cat > r6.py <<'PY' from collections import Counter from typing import Dict def main() -> in
         20s bash   cd /tmp/rprobes && for p in r1 r2 r3 r4 r5; do echo "######## $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /hom
         19s bash   cd /tmp/rprobes && cat > r13.py <<'PY' from collections import Counter, ChainMap def main() -> int:     cm = C
          7s bash   cd /tmp/rprobes && cat > r15.py <<'PY' from collections import Counter, ChainMap def main() -> int:     c = Co
          6s bash   cd /tmp/rprobes && cat > r11.py <<'PY' from collections import Counter, ChainMap, OrderedDict, defaultdict def


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
