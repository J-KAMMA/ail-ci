**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model qoder/DeepSeek-Flash]
**What the change really does (one line):** It re-applies the accepted `reex24` change — `pyc.py` now inspects each definition header and the module top-level of a Python-surface file (`_literal_value`, `_effect_free_annotation`, `_effect_free_node`, `_definitions_only_shape`), refusing a definitions-only module whose def/class runs code at load by name ("runs code at load time"), plus a probing `ail_testenv.rustc()` shared by two Rust tests. The re-applied `pyc.py` hunks are identical to `git diff d4c28d0 FETCH_HEAD`; `ail_testenv.py` and `test_ail_reex24.py` are byte-identical to the fetched branch.

### Defect (change-caused)

1. **`_literal_value` trusts any user call whose name starts with `_AilT_`.** `pyc.py:1218-1225` accepts `_AilT_*(...)` with literal args as a pure literal because the surface emits such calls for tuple defaults. A user function named with that prefix at module level is then classified effect-free, `_python_runs_nothing(source, True)` picks the no-op `main` (`pyc.py:1594`), and the **default build silently drops the call's output**.

   Probe `/tmp/rprobes/p_ailt_const.py`:
   ```python
   def _AilT_evil(n):
       print("evil called", n)
       return n

   K = _AilT_evil(1)
   ```
   - CPython (and both HEAD and base builds' general path): `evil called 1`, rc 0.
   - HEAD default build: **empty stdout, rc 0** (`cmp.sh`: `d exit 0`, `d DIFF: 1d0 < evil called 1`).
   - Base (`/tmp/base_w2`, 1ccf615): both builds print `evil called 1`.
   This is exactly the silent loss the change exists to prevent, and it is reachable without touching the feature's examples. A fix should accept the `_AilT_*` spelling only for names the surface itself generated (or require the callee not to be a user def in the module).

### Claim checks
- DIFFERENCES header restored; vs `d4c28d0` purely additive 30 rows / 0 removed — **verified** (lines 1-4 byte-equal to both `d4c28d0` and `FETCH_HEAD`; 30 inserted lines, all table rows; 0 deletions).
- Commit `8d1f064`, 1 file, +4 lines — **verified**.
- `update_manifest.py --check` rc 0 — **verified**.
- Working tree clean except untracked `.agent/pipeline.md` — **verified**.
- "9 modules, 957 s, rc 0" — **partially verified**: on HEAD I re-ran the 4 required modules (`test_ail_reex24`, `test_ail_c_export`, `test_ail_cratebridge`, `test_ail_safetynet`): 384 s, 0 failed. The other 5 were not re-run per the review rules.
- Probe matrix (28 match / 15 refused / tool-mode opt-out) — **spot-verified** by re-running the leftover `/tmp/rprobes` set: effect-free shapes match, decorator/user-annotation/non-literal-default cases emit the new refusal name on both builds; `AIL_TOOL_MODE=1` on the decorated module compiles rc 0. Not exhaustively re-run.
- "`pyc.py` is byte-identical to the fetched original" — **false** as written: `git diff --stat FETCH_HEAD -- pyc.py` shows 235 insertions/26 deletions. The substantive claim is true: the re-applied change diff is hunk-for-hunk identical (only index hashes and offsets differ), so the noted boundary is the original change's own.
- `tools/diff_ids.py` absent in this tree and `FETCH_HEAD` — **verified** (the task's instruction could not be run).

### Pre-existing (identical on `/tmp/base_w2`; not blocking)
- `p_ann_bare_then_list.py` (`Y: int` + `Z: list[int] = []` + def): uncaught `AttributeError: 'NoneType' object has no attribute '_fields'` in fastwalk.py:32, both builds on both trees.
- `p_r_import_this.py`: both trees/builds print nothing where CPython prints the Zen (import side effects are not modelled).
- `p_class_subclass.py` (`class C(Base)` with an echoing `__init_subclass__`): both trees/builds silently drop `sub`; `_effect_free_node` ignores class bases/keywords.
- `p_empty.py`: default build refuses by name on both; `p_async.py`: named refusal on both.
- Change-noted but acceptable: `D = {}` then `D["k"] = 1` (`p_ann_mutate.py`) built rc 0 on base but is now a **named** default-build refusal ("a function with no parameters…"); the general path still matches CPython. Named refusals are acceptable.

### Unverified
- The other 5 test modules the report lists; the full 44-probe matrix; gdev instruction counts (the change is compile-time only; no runtime/hot path touched).
- Note: `/tmp/base` is not a worktree of this repo; base comparisons used the registered `/tmp/base_w2` at `work` (1ccf615). No-feature C check: `hello.ail` and a Python-surface `print("hi")` produce byte-identical `program.c` on HEAD vs base.

VERDICT: FIX

1. `_literal_value` (`AIL_CURRENT/python/pkg-v12/pyc.py:1218`) treats any call to a name starting with `_AilT_` as an effect-free literal. With `def _AilT_evil(n): print("evil called", n); return n` and `K = _AilT_evil(1)` (`/tmp/rprobes/p_ailt_const.py`), the default build emits the no-op `main` and prints nothing (rc 0), expected `evil called 1` (rc 0) as CPython and the general build print; base prints it on both builds. Accept the `_AilT_*` spelling only for surface-generated names, or exclude a callee that is a module `def`.


--- ORIGINAL TASK ---
**Re-apply an accepted change on top of the current tree.** Job `reex24` was accepted, but its diff no longer applies here. Fetch it anonymously: `git fetch https://github.com/J-KAMMA/ail-ci.git job-reex24-10300433`. Its change is `git diff d4c28d044275ec49ca2a852f965029ab2bf799b3 FETCH_HEAD -- . ':!.agent' ':!corpus' ':!AIL_CURRENT/MANIFEST.json'`.

Apply the same change to this tree, resolving conflicts by keeping both sides' fixes. Then run `python3 tools/diff_ids.py` and `python3 tools/update_manifest.py`, run the test modules the change touches plus `test_ail_safetynet`, and commit. Change nothing else.

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
