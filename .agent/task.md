**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 2 (final)

**What the change really does:** fixes the prior review's three defects in the `abc` pass: `get_cache_token()` is now a compile-time-read exact value only for `abc`-only imports (otherwise a named refusal), `ABCMeta` subclasses used as metaclasses are recognised, and only a class's *own* guard raises before `__init__` binding, so concrete subclasses that inherit a guard no longer swallow arity errors. As before, it also touches `pyboxed2._call_class` / `boxclosure.call_value` for all class-value dispatch whenever a guard exists.

**Probes (`/tmp/rprobes4`, `cmp.sh`, both builds; base `/tmp/base`)**
- Match CPython both builds: `cache_simple`, `cache_alias`, `cache_from`, `cache_future` (token 24, positive, stable); `meta_sub`, `meta_sub2` (exact `Can't instantiate abstract class ...`); `valid_concrete`, `own_init_concrete_valid`, `route_direct`, `route_list`, `route_dict`, `route_arg`.
- Named refusal, both builds: `cache_other`, `cache_nested_import`, `cache_ref`, `cache_dynamic`, `cache_monkey`, `cache_alias_value`, `cache_register`, `cache_update_abs`; `arity_concrete`, `arity_custom_own_init` (`B() called without a required argument x`).
- Collateral regression (caused by change, named refusal): `lambda_regress` — an ABC subclass with a required `__init__` passed to a factory plus a zero-arg lambda. Base built it and matched (`5`); HEAD refuses `B() called without a required argument x`, because `class_values` makes every zero-arg value call speculatively try `_call_class(B, [])`. This is a named refusal, so acceptable under the probe rule, but it is a real coverage loss worth noting.
- Pre-existing (identical wrong output/refusal on base): `meta_type` (`Meta Meta` vs `type type`), `meta_init_print` (missing metaclass `__init__` prints), `meta_abc_base`, `plain_value_arity`.

**Tests / checks**
- `test_ail_std_abc`, `test_ail_safetynet`: 2/2 pass (134 s).
- `python3 tools/update_manifest.py --check`: exit 0.
- `lab/compare`: not rebuilt this round; grep shows no `main.ail` mentioning `abc`, and the guarded code is inert without a generated guard, so C is unaffected (consistent with commit `7a6e7f9`'s 10/10).

**Report claims**
- cache-token exactness and named refusal for other imports: verified (probes above).
- prior arity/meta review cases now refuse or match: verified.
- final commit `2195906`, 4/4 tests, manifest: commit/manifest verified; I ran only the 2 edited/relevant modules (files/corpus not edited, not re-run).
- `lab/compare` unaffected: verified by inspection/reasoning, not rebuilt.
- No crash or silent difference found from the change; metaclass recognition improves `Shape()` from silently built (base) to the exact abstract error.

**Non-blocking note:** `lambda_regress` shows the inherited-guard re-raise in `boxclosure.call_value` also fires for unreachable speculative class-value branches; it is still a named refusal, never silence.

VERDICT: ACCEPT
[cost $0.0316, opencode tokens {"total": 1283651, "input": 69600, "output": 7809, "reasoning": 21474, "cache.write": 0, "cache.read": 1184768}]
    tool time: bash 3.5 min
        135s bash   date && cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_std_abc tes
         20s bash   cd /tmp/rprobes4 && cat > route_direct.py <<'EOF' from abc import ABC, abstractmethod class A(ABC):     @abstr
         13s bash   cd /tmp/rprobes4 && cat > bisect_a.py <<'EOF' from abc import ABC, abstractmethod class A(ABC):     @abstractm
          7s bash   cd /tmp/rprobes3 && for p in meta_abc_base.py plain_value_arity.py; do echo "===== $p ====="; for wt in /home/
          5s bash   cd /tmp/rprobes4 && cat > valid_concrete.py <<'EOF' from abc import ABC, abstractmethod  class A(ABC):     @ab
          5s bash   cd /tmp/rprobes4 && for p in arity_concrete.py arity_custom_own_init.py meta_sub.py meta_sub2.py; do echo "===
          4s bash   cd /tmp/rprobes4 && cat > meta_init_print.py <<'EOF' from abc import ABCMeta, abstractmethod   class Meta(ABCM
          4s bash   cd /tmp/rprobes4 && for p in cache_alias.py cache_from.py cache_future.py cache_other.py cache_nested_import.p

## full suite
test_ail_quirks

## worker report (suite fix)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `8dad2a6`.

- Cause: `test_ail_quirks` passes raw `@dataclass` source straight to the general path, which built classes without the generated `__init__`, causing runtime `TypeError`.
- Fix: `pyboxed2` now refuses a raw `@dataclass` by name instead of silently building a broken class. Preprocessed dataclass sources still work.
- Verified: `test_ail_quirks`, `test_ail_std_abc`, `test_ail_silent6.DataclassEqTests`, `test_ail_safetynet` all pass; manifest check clean.
[cost $0.0333, opencode tokens {"total": 2671576, "input": 129938, "output": 4881, "reasoning": 5557, "cache.write": 0, "cache.read": 2531200}]
    tool time: bash 7.2 min, edit 0.0 min
        140s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_safetynet 2>&1 | tail -30
        125s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_quirks 2>&1 | tail -80
         82s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_quirks 2>&1 | tail -40
         45s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_std_abc 2>&1 | tail -30
         29s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_silent6.DataclassEqTests 2>&1 | tail -30
         10s bash   cd /tmp/orig/AIL_CURRENT && python3 -m unittest -q test_ail_quirks.Quirks.test_fold_over_dataclass_instances t
          2s bash   git worktree add --detach /tmp/orig origin/job-std_abc-11020347 >/dev/null && cd /tmp/orig/AIL_CURRENT && pyth
          1s bash   cd AIL_CURRENT && mkdir -p /tmp/qk && cat > /tmp/qk/t.py <<'EOF' from dataclasses import dataclass  @dataclass

## full suite again
test_ail_genlib


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `abc` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `abc` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/abc/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/abc/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_abc.py registered in tests.d), and compare them with CPython in the test.
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
