**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review — lazymod1 (work..9f011fd)

**What the change really does:** rewrites `init_split` to resolve, transitively through user functions/aliases/classes, the module values that a lazily started module's definitions need; only statements judged pure and non-raising are emitted with the definitions, the rest stay in `_ail_init_<mod>`; effectful/state/raising cases are refused by name. Adds `test_ail_lazymod1`, edits `test_ail_modsys`, records/manifest.

**Tests (HEAD):** `test_ail_lazymod1 test_ail_modsys test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 5/5 ok, 0 failed (311s). `update_manifest.py --check` exit 0.

**Lab/compare C:** all 10 `.ail` byte-identical to base. `.py`: 5 identical + 5 fail identically (my build; worker says 7+3, minor count difference, no behaviour change).

**Claims:** standard-call/property/missing-attr/user-method refusals verified (`p_cwd`, `p_env`, `p_prop`, `p_attr_raise`, `p_method` all refused by name). Pure computed value verified (`p5_control`). Worker's `p_pure`, `p_pure_method`, `p_class_attr`, `p_settled`, `p_mutated`, `p_mutate_list` are not in `/tmp/rprobes` — unverified. Positive boundary probes through attribute/list item/dict value/argument/instance attr/negative shift all matched CPython or refused.

**Defects (introduced by the change; base refused both by name):**

1. An earlier binding of the same name is deferred and overwrites the hoisted value.
   `lib.py`: `print("lib start")` / `SIZE = 1` / `SIZE = 2` / `def f(a=SIZE): return a`
   `main.py`: `def g(): import lib; return lib.f(), lib.SIZE` / `print(g())`
   Expected CPython (and base refusal): `lib start` then `(2, 2)` (exit 0). Actual HEAD (both builds, exit 0): `lib start` then `(2, 1)` — `SIZE=1` runs later in the init function. `need_name` follows the needed statement's value dependencies only, so the earlier `SIZE=1` is left in the init body and executes after the hoisted `SIZE=2`.

2. A raising computation hidden behind an unfoldable user call is hoisted, moving the exception before earlier effects.
   `lib.py`: `print("before")` / `def base(): return {}` / `D = base()` / `X = D["b"]` / `def f(a=X): return a`
   `main.py`: `def g(): import lib; return lib.f()` / `print("calling")` / `print(g())`
   Expected CPython: stdout `calling\nbefore\n`, KeyError, exit 1. Actual HEAD (both builds): stdout empty, KeyError, exit 1 — `D` and `X` are hoisted, so `KeyError` fires at program start before `print("calling")`/`print("before")`. The raise is only detected when `fold` can evaluate the operands; `D = base()` makes `D["b"]` unfoldable, and `move_bad_expr` treats the subscript as safe.

No pre-existing output differences found; the runtime is untouched (change is compile-time; lab C unchanged).

VERDICT: FIX
1. Earlier same-name binding before the definition is deferred and overwrites the hoisted later value (`/tmp/rprobes/p1_rebind`): expected `(2, 2)`, actual `(2, 1)`.
2. Raising subscript over an unfoldable call is moved to program start, dropping earlier stdout (`/tmp/rprobes/p3_raise`): expected `calling\nbefore\n` + exit 1, actual empty stdout + exit 1.
[cost $0.0443, opencode tokens {"total": 2405384, "input": 107461, "output": 7291, "reasoning": 28360, "cache.write": 0, "cache.read": 2262272}]
    tool time: bash 11.8 min
        359s bash   cat > /tmp/labdiff.sh <<'SH' #!/bin/bash set -u HEAD=/home/runner/work/ail-ci/ail-ci BASE=/tmp/base out=/tmp/l
        312s bash   date; cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_lazymod1 test_ail_modsys test
         18s bash   for p in p6_attr p7_dict p8_listarg p9_instattr p10_neg p11_mut_after p12_arg; do echo "=== $p HEAD"; /tmp/cmp
         10s bash   date; for p in p1_rebind p2_aug p3_raise p4_mutable_import p5_control; do echo "=== $p HEAD"; /tmp/cmpdir.sh /
          5s bash   cat > /tmp/labdiff.sh <<'SH' #!/bin/bash set -u HEAD=/home/runner/work/ail-ci/ail-ci BASE=/tmp/base out=/tmp/l
          1s bash   date; for p in p1_rebind p2_aug p3_raise p4_mutable_import; do echo "=== $p BASE"; /tmp/cmpdir.sh /tmp/rprobes
          1s bash   for p in p_cwd p_env p_prop p_method p_attr_raise; do echo "=== $p HEAD"; /tmp/cmpdir.sh /tmp/rprobes/$p /home
          1s bash   mkdir -p /tmp/rprobes/p13_basehook cat > /tmp/rprobes/p13_basehook/lib.py <<'PY' print("start") class Base:   


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
