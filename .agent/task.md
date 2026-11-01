**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review — lazymod1 (work..7e14e0a)

**What the change really does:** extends `init_split` so an earlier binding of a name a definition needs is hoisted too (recursively), refuses non-hoisted statements between hoisted bindings that read/write a hoisted name, and refuses unfoldable subscripts (except in annotations).

**Prior review defects**
1. Earlier same-name binding overwriting the hoisted value — **fixed**. `p1_rebind` now matches CPython on both builds: `lib start` / `(2, 2)`.
2. Raising subscript over an unfoldable call moved to start — **fixed**. `p3_raise` is refused by name on both builds (was base refusal).

**Tests / checks**
- `test_ail_lazymod1 test_ail_modsys test_ail_safetynet`: 3/3 ok, 0 failed (168s, HEAD).
- `update_manifest.py --check`: exit 0.
- Lab/compare: `merge_program` returns `None` for all 10 `lab/compare/src/*/main.ail`, so the merge path and their C are unchanged.

**Worker claims:** review fixes verified; added refusal tests (3 programs in the final commit) present; manifest and lab/compare claims verified. The wider 5/5 test count and the worker's other probe names were not re-run/absent.

**New defect (introduced; base matches CPython)**
1. A raising non-subscript expression in an earlier binding is still hoisted, moving the exception before earlier output. `move_bad_expr` only refuses unfoldable `Subscript`, so `effectful()` judges `SIZE = 1 // Z` (with `Z` from an unfoldable call) pure and `need_name` hoists it to program start.

   Probe `/tmp/rprobes/p_div_unfold` (`lib.py`: `print("before")`, `def zero(): return 0`, `Z = zero()`, `SIZE = 1 // Z`, `SIZE = 2`, `def f(a=SIZE): return a`; main imports `lib` in `g()` after `print("calling")`):
   - Expected CPython (and base, both builds): stdout `calling\nbefore\n`, `ZeroDivisionError`, exit 1.
   - Actual HEAD (both builds): stdout empty, `ZeroDivisionError`, exit 1.

   Same with `/tmp/rprobes/p_binop_unfold` (`SIZE = 1 + T`, `T = text()` returning `"x"`): expected `calling\nbefore\n` + `TypeError`, exit 1; actual empty stdout + `TypeError`, exit 1 (base matches CPython).

**Pre-existing (does not block):** `/tmp/rprobes/p_annot_raise` (`def f(a: D["y"] = 0)` with `D = base()`) prints an extra `0` and exits 0 on both HEAD and base, while CPython raises `KeyError`; identical on base.

**Unverified:** `test_ail_files` and `test_ail_corpus_findings3` not re-run; several worker probe names (`p1_three`, `p1_aug`, `p1_unpack`, `p1_ann`, `p1_def_before`, `p5_control`, `p_sub_*`) were not re-run this round.

VERDICT: FIX
1. Raising non-subscript expressions (e.g. `SIZE = 1 // Z`, `SIZE = 1 + T` where `Z`/`T` come from an unfoldable call) in an earlier binding are hoisted, so the exception fires at program start and earlier stdout (`calling\nbefore\n`) is lost. Probe `/tmp/rprobes/p_div_unfold` (and `p_binop_unfold`): expected `calling\nbefore\n` + exit 1, actual empty stdout + exit 1; base matches CPython. The purity/raise check must cover non-subscript expressions (or refuse such earlier bindings by name).
[cost $0.0000, opencode tokens {"total": 1611021, "input": 71802, "output": 6097, "reasoning": 27330, "cache.write": 0, "cache.read": 1505792}]
    tool time: bash 3.6 min
        170s bash   date; cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_lazymod1 test_ail_safetynet t
         13s bash   mkdir -p /tmp/rprobes/p_div_unfold /tmp/rprobes/p_binop_unfold cat > /tmp/rprobes/p_div_unfold/lib.py <<'PY' p
          8s bash   date; for p in p_def_rebind p_after_mutate p_after_alias_mut p_after_read; do echo "##### $p HEAD"; timeout 30
          5s bash   mkdir -p /tmp/rprobes/p_def_rebind_imp /tmp/rprobes/p_def_rebind_imp2 cat > /tmp/rprobes/p_def_rebind_imp/lib.
          5s bash   date; for p in p_def_rebind_imp p_def_rebind_imp2; do echo "##### $p BASE"; timeout 300 bash /tmp/cmpdir.sh /t
          5s bash   echo "=== p_annot_raise lib"; cat /tmp/rprobes/p_annot_raise/lib.py; echo "=== main"; cat /tmp/rprobes/p_annot
          4s bash   date; for p in p1_rebind p3_raise p_rebind_print p_rebind_call p_rebind_mutate p_rebind_cond_read; do echo "##
          3s bash   mkdir -p /tmp/rprobes/p_after_wrap /tmp/rprobes/p_after_const_mut cat > /tmp/rprobes/p_after_wrap/lib.py <<'PY


--- ORIGINAL TASK ---
**Coverage: lazily started modules whose definitions need values computed when the module runs.** After #307, a module imported inside a function hoists its definitions; definitions that depend on module-level computed values (e.g. gpu_vk: SIZE = 1 << N then def f(a=SIZE)) are refused. Make those values computed in the module's init before the definitions that need them, keeping CPython's order of effects. Acceptance: compare stdout and exit code with CPython on your own boundary probes; the generated C of the 10 lab/compare tasks must stay byte-identical unless the task is about them; add tests (register new modules in tests.d), run them plus test_ail_safetynet, run `python3 tools/update_manifest.py`, commit.

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
