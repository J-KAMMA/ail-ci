**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
All gate modules pass, but I have three confirmed defects. Writing the report.

**What the change really does:** replaces setord1's blanket refusal of order-revealing set walks with an emulation of CPython 3.12's open-addressed set table (`ctab` in the boxed set, `ckey/ckind` shadow in `ail_idict`/`ail_iset`), used when every element has a deterministic CPython hash, and insertion order otherwise; removes the refusals from both compilers and rewrites the affected tests.

## Verified

- `probes`: p_int, p_del, p_float, p_none_bool, p_big2, p_lit, p_empty, p_frozen, p_ctx, p_mixed, p_plain, p_str, p_strit, p_mut, p_big, p_typed, p_ops, p_collide — all match CPython on both builds (`cmp.sh`, general and default). Typed `set[int]` iteration/pop matches; typed and untyped `set[str]` build without refusal; mutation-during-iteration and empty/negative/aliasing cases match.
- Non-set program (`p_plain`): generated program statements are identical to base `/tmp/basew` under `--debug-dir`; the only C delta is the set runtime header.
- `test_ail_setorder`, `test_ail_int_dict_set`, `test_ail_collections`, `test_ail_safetynet` pass. Gate modules `test_ail_fuzz81`, `test_ail_std_difflib`, `test_ail_std_pprint`, `test_ail_pyreach_dictrows`, `test_ail_re_value`, `test_ail_examples_algos`, `test_ail_bigint` all pass (7/7, 950s).

## Defects

1. **The change's own test fails on HEAD.** `test_ail_sets_general.test_s3` (edited in this diff) still asserts that a `for x in s` walk is *refused*; the general path now builds it. `FAIL test_ail_sets_general (28s): AssertionError: 0 == 0 : general: walk_general`. The DEVLOG claim "All 16 modules ... pass" is false.

2. **Dense int sets diverge after a rehash** (task explicitly requires collisions/growth to match). `ail_setx_ct_insert_clean` advances `i` through the 9 linear probes and then computes `i = i*5+1+perturb` from the *advanced* index; CPython steps from the original slot.
```python
s = set()
for i in range(40): s.add(i * 128)
print(list(s))
```
CPython: `[0,256,384,128,512,...,1152,4096,4224,4352,4480,4608,4736,4864,4992,1280,1408,...]`
AIL (general and default): `[0,256,384,128,512,...,1152,4096,4224,4352,4480,4608,4736,4864,4992,2432,2560,2688,1280,2816,1408,...]`
A 19-element version matches; 40 does not. `test_ail_setorder`'s "growth" case never creates a 10-slot run, so it misses this.

3. **Tuple-constant displays are not folded, so their order differs.** `_folded_set_elt` returns False for `ast.Tuple`, but CPython 3.12's AST optimizer folds tuple displays of constants and the display then folds to a frozenset constant (`merge_consts_recursive` rebuild + `SET_UPDATE`).
```python
print({(1, 2), (2, 1), (0, 0), (1, 1), (2, 2), (3, 0)})
print(list({(1, 2), (2, 1), (0, 0), (1, 1), (2, 2), (3, 0)}))
```
CPython: `{(1, 2), (2, 2), (2, 1), (0, 0), (1, 1), (3, 0)}`
AIL both builds: `{(1, 2), (2, 1), (0, 0), (1, 1), (3, 0), (2, 2)}` (the plain add-loop order). The 3-tuple case in `test_ail_setorder` happens to coincide, hiding it.

## Pre-existing

Base `/tmp/basew` also differs from CPython on the probes of defects 2 and 3 (it printed plain insertion order), so neither is a regression — but both were required by the task ("collisions, deletions and growth"; "tuples of these"), and the DIFFERENCES/DEVLOG rows claim byte-for-byte parity.

## Unverified

Instruction counts (`tools/icount.c`) on gdev programs not measured; the remaining edited test modules (fuzz27/28/36/70, gaps_api1/2, lang_gaps, modconst, pre133/245/341, corpus_findings, dict_delete, exc_str, fuzz_findings) not run for time. Worker final report was empty, so I checked the DEVLOG rows instead.

VERDICT: FIX
1. `test_ail_sets_general.test_s3` fails on HEAD — it still expects the removed refusal; update or delete it (expected build rc != 0, got 0).
2. `ail_setx_ct_insert_clean` must keep the pre-linear-probe slot for the perturb step. Probe `p_coll2` (40 × 128): expected CPython's `...4864, 4992, 1280, 1408, 1536...`, got `...4864, 4992, 2432, 2560, 2688, 1280...`.
3. `_folded_set_elt` must treat a `Tuple` of constants as foldable (CPython's AST `fold_tuple`). Probe `p_tuple` (6 int pairs): expected `{(1, 2), (2, 2), (2, 1), (0, 0), (1, 1), (3, 0)}`, got `{(1, 2), (2, 1), (0, 0), (1, 1), (3, 0), (2, 2)}`.
[commandcode stop=end_turn turns=46 out_tokens=32149]


--- ORIGINAL TASK ---
# setord2: set order — match CPython where its order is fixed; do not refuse where CPython's own order is random

Lane: setord

Start from setord1's branch, `job-setord1-11080325`. Its review was ACCEPT, but the gate run on PR
#454 was red. setord1 refuses order-revealing iteration of sets too broadly. That broke existing
correct programs and AIL's own stdlib:

- difflib.py:189;
- pprint;
- examples life.py;
- test_ail_fuzz81 (set.pop);
- test_ail_re_value;
- test_ail_pyreach_dictrows;
- test_ail_bigint (tuple output order).

## Rule (the AIL principle is "CPython-identical, or a loud refusal; never a silent difference")

- **Sets whose elements hash deterministically in CPython:** int, bool, None, float, and tuples of
  these. CPython's iteration order is fixed by its hash-table layout, so emulate it exactly:
  - the same table size and growth;
  - the same probing (perturb);
  - the same deletion dummies.

  Then iteration, `pop()`, `repr()` and `list(s)` match CPython byte for byte. Where emulation is not
  implemented for a case, refuse by name (as setord1 does) instead of printing a different order.
- **Sets that contain str or bytes:** CPython's order is random per run (PYTHONHASHSEED). No single
  order is "the CPython order", so AIL's fixed order is one valid CPython run. Do not refuse these;
  keep a deterministic order.
  - Document it in docs/spec as "iteration order of str/bytes sets is unspecified (CPython varies it
    per run); AIL's order is deterministic".
  - Tests that compare against CPython must not depend on that order.
- **Mixed sets** follow the stricter rule of their element kinds.
- **frozenset** follows the same rules.

## Work

1. Start a branch from `origin/integ` and bring setord1's work across.
2. Implement the rule above on both the typed path and the general path.
3. Re-run all the modules that failed at the gate, one after another under `ulimit -v 2500000`:
   - test_ail_fuzz81
   - test_ail_std_difflib
   - test_ail_std_pprint
   - test_ail_pyreach_dictrows
   - test_ail_re_value
   - test_ail_examples_algos
   - test_ail_bigint
   - test_ail_setorder

   Add cases to test_ail_setorder covering:
   - int sets with collisions, deletions and growth, comparing iteration, `pop()` and `repr()`
     against CPython;
   - str sets, which must build and run without refusal.
4. Report which kinds are emulated, which are refused, and the test results with times.

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
