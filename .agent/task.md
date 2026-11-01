**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does:** Adds `array` general-path prelude behaviour (index bounds, `fromlist`, slices, delete, `+`/`+=`/`*`/`*=`, comparisons, error texts), rewrites `array(...)` with keywords to `_ail_arr_bad_kw()`, and enables an op-aware `__le__`/`__ge__`/`__gt__` dispatch (`dunderrt.py`, `pyboxed2.py`) for programs containing `_AilArray`. Adds 12 lab programs, RESULTS.md, `test_ail_std_array`, docs/manifest. Broadly matches the report.

**Probes** (all on HEAD and `/tmp/base` with `cmp.sh`; HEAD `g` and `d` agreed unless noted):
- `p_idx`, `p_idxnone`: same stdout as CPython.
- `p_from`, `p_from2`: same stdout.
- `p_slice`, `p_ext`: same stdout except `type(a[1:4]).__name__` (`_AilArray` vs `array`; base returned a plain list).
- `p_cmp`, `p_cmp2`, `p_cmp3`: same except reflected non-array-left comparisons (below).
- `p_typecode2`: widths/`x`/`w`/kw forms match; variable `f`/`u` and non-str typecodes still differ (base same).
- `p_mul`: same except `'x' * a` message.
- `p_kweval`: **new wrong behaviour** (defect 1).
- `p_user`, `p_sub`, `p_neq`, `p_refl`: user-class ordering/eq edge cases; differences are identical on base except the array-ordering messages noted below.

**Defects**
1. `/tmp/rprobes/p_kweval.py` — the keyword rewrite drops all argument evaluation. `array("i", boom(), bad=1)` where `boom()` raises `ValueError`: expected `ValueError boom`, actual `TypeError array.array() takes no keyword arguments`. Side effects are also lost: `array("i", note(), bad=1)` with `note()` printing `evaluated` should print `evaluated` then `TypeError`; HEAD prints only `TypeError`. Base refused this by name (acceptable), so the change caused it. Fix: keep the arguments and let a `*args/**kwargs` helper raise.
2. `/tmp/rprobes/p_cmp.py` — reflected ordering regressed: `[1] <= a`, `>=`, `>`, `<` expected e.g. `TypeError '<=' not supported between instances of 'list' and 'array.array'`; actual all four `TypeError '<' not supported between instances of 'array.array' and 'list'`. Base named the right operator/order (but `_AilArray`); the new `__le__/__ge__/__gt__` methods changed it to the wrong one.
3. `/tmp/rprobes/p_mul.py` — `'x' * array('i',[1])` expected `can't multiply sequence by non-int of type 'array.array'`; actual names `'str'` (new `__rmul__`). Base named `_AilArray`, i.e. the right operand.

**Pre-existing** (base differed too): reflected custom-class ordering `a <= R()` raises instead of calling `R.__ge__`; comparing with `R()` names `object` after the change but `R` before; variable `'f'`/`'u'` and non-str typecodes at run time; `type(a[:]).__name__` leaks `_AilArray`.

**Claims verified:** index sentinel/`None`/non-int; `fromlist` genexpr/tuple/array rejection; extended-slice `array` text; operator naming via parameter/list item/attribute/dict; typecode text without `w` (CPython 3.12.3); all 9 required modules 0 failed (`test_ail_std_array`, `test_ail_safetynet`, `test_ail_dunders`, `test_ail_cmp_classname`, `test_ail_array_ref`, `test_ail_array_t2`, `test_ail_stdlib5`, `test_ail_files`, `test_ail_corpus_findings3`); `update_manifest.py --check`; all 10 `lab/compare/.../main.ail` generated `program.c` byte-identical to base. **Unverified:** the `main.py` builds and the worker's `/tmp/probes` files.

VERDICT: FIX
[cost $0.0489, opencode tokens {"total": 2196776, "input": 89375, "output": 13837, "reasoning": 35068, "cache.write": 0, "cache.read": 2058496}]
    tool time: bash 12.5 min
        251s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_dunders t
        169s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_files tes
        156s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_std_array
         36s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cgall && mkdir -p /tmp/cgall && cat > /tmp/cgall/one.sh <<'EOF' #
         22s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/rout/head4 && for p in p_idxnone p_from2 p_ext p_cmp p_cmp3 p_k
         20s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/rout/head && for p in p_idx p_from p_slice p_cmp p_user p_typec
         15s bash   cat > /tmp/rprobes/p_typecode2.py <<'EOF' from array import array  def show(tag, fn):     try:         print(t
         14s bash   cat > /tmp/rprobes/p_from.py <<'EOF' from array import array  def gen():     yield 1     yield 2  def show(tag


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `array` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `array` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/array/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/array/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_array.py registered in tests.d), and compare them with CPython in the test.
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
