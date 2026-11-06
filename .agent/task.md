**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does:** re-applies the accepted `pyreachs2` feature (typed `heapq.nsmallest/nlargest` select lowering, `xs.extend(reversed(...))`, `bytes`/`bytearray.__reversed__` in the runtime prelude) and adds the two claimed review fixes — a named refusal for a whole-list value into an int dict, and a live reverse iterator for `bytearray`. The report describes this accurately; it omits the invalid-C path below.

### Defect

**1. A select passed directly as an argument to a user function/method emits invalid C on the default build.**

`/tmp/rprobes/p_u1.py` (also `p_u2.py`, `p_y1.py`):
```python
import heapq

def total(xs: list[int]) -> int:
    t = 0
    for x in xs:
        t += x
    return t

def main():
    ys = [5, 2, 8]
    print(total(heapq.nsmallest(2, ys)))

main()
```
Expected (CPython): `7`. Actual: `bash ~/tools/cmp.sh` prints **`build d failed`** with gcc: `error: expected ')' before ';' token`, on generated C
`v__t4 = (v__t2 = 2LL;, ail_list_clear(&v__t3);, for (...) ail_list_push(...);, ..., total(v__t3.p, v__t3.n));`.
The base builds this and prints `7`. `p_u2.py` (a `list[str]` parameter, expected `fig`) fails the same way with `expected 'ail_str' but argument is of type 'int64_t'`; `p_y1.py` reproduces it through a method call.

Cause: the two new `_is_heapq_select` branches in `_call_user_func` (`pyfunc.py:17205-17216` and `17415-17425`) do `staged.extend(ctx.pre[before:])`, pushing raw statements that each end in `;` into `staged`; `staged` is emitted as a comma expression at `pyfunc.py:17547`. Every other entry is an expression — the correct wrapper already exists at line 17288 (`'({ %s (void)0; })' % ' '.join(...)`). Both the LIST/`array` and SLIST parameter branches need it. This is also exactly the "values reaching the code through an argument" boundary the task's self-check requires, and it was not probed.

### Claim check
- Commit `e0543e9e`: 8 files, +160/−10 — **verified**.
- Dict-store fix (fallback prints `[2, 5]`; strict names `dict of integers`) — **verified** (`p_sel_dict`, `p_x9`; strict log).
- Pre-existing `d["k"] = xs` gcc failure on base (`ail_stab_put(ail_list)`) — **verified** (`p_z1`; base `build d failed`, HEAD matches CPython).
- Live `reversed(bytearray)`: item mutation seen, append/delete/clear end the walk, `bytes` snapshot — **verified** (`p_rev_live`, `p_x5`, `p_x8`; base fails these, HEAD matches).
- `print(nsmallest(k, words))` builds on the typed path — **verified** (strict-loop build OK).
- `manifest --check` clean; `tools/diff_ids.py` absent; DEVLOG/DIFFERENCES added; nothing else changed — **verified**.
- Tests: `test_ail_pyreach_shapes`, `test_ail_python_syntax`, `test_ail_safetynet`, `test_ail_bytearray_loops`, `test_ail_bytearray_refs` — **5/5 pass** on HEAD (`-j 2`).
- "30 probes all match CPython" — **unverified**: 3 named probes (`p_sel_name_store`, `p_sel_scalar`, `p_ba_rev_live`) are not present in `/tmp/rprobes`; the 10 present do pass.

### Pre-existing (not blocking)
- Base cannot build `reversed(bytearray)`/`reversed(list)` at all (`p_x8` base exit 1, `TypeError: 'instance' object is not reversible`); HEAD matches CPython.
- Base's typed path gcc-fails `d["k"] = xs` (`p_z1`); HEAD falls back correctly.
- `iter(it) is it` claim — not checked.

### Unverified
- Speed: `perf_event_open` is denied in this container, so `tools/icount.c` cannot run. Generated C for the two gdev programs I checked (`g00_000`, `g00_010`) is byte-identical to base, so no runtime change is expected.
- Non-feature programs: `p_heap_no` (heapq ops only) and both gdev programs produce byte-identical C. Programs touching `bytes`/`bytearray` gain the prelude's new `__reversed__` (class-table slot shifts in the embedded runtime only; no change to emitted user code).

VERDICT: FIX
1. Passing `heapq.nsmallest()`/`nlargest()` directly as an argument to a user function or method whose parameter is a list or list-of-str emits invalid C on the default build (`p_u1.py`: expected `7`, actual gcc error / no binary; `p_u2.py`: expected `fig`, actual gcc error; `p_y1.py` method-call variant). Fix the two `_is_heapq_select` branches in `_call_user_func` (`pyfunc.py:17205-17216`, `17415-17425`) to wrap the moved `ctx.pre` statements in an expression (`({ ... (void)0; })`), as line 17288 already does.
[commandcode stop=end_turn turns=39 out_tokens=39582]


--- ORIGINAL TASK ---
**Re-apply an accepted change on top of the current tree.** Job `pyreachs2_rr1` was accepted, but its diff no longer applies here. Fetch it anonymously: `git fetch https://github.com/J-KAMMA/ail-ci.git job-pyreachs2_rr1-11070228`. Its change is `git diff a8b8e5a115604ded490df34af0a99e727a1501c4 FETCH_HEAD -- . ':!.agent' ':!corpus' ':!AIL_CURRENT/MANIFEST.json'`.

Apply the same change to this tree, resolving conflicts by keeping both sides' fixes. Then run `python3 tools/diff_ids.py` and `python3 tools/update_manifest.py`, run the test modules the change touches plus `test_ail_safetynet`, and commit. Change nothing else.

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
