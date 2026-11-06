**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: ffbig0 (docs + lab probes only)

**What the change really does:** adds `docs/design/BIGINT_TYPE.md`, 12 CPython-runnable `lab/bigtype/*.py` programs with `expected/`, and `lab/bigtype/check_model.py` (an AST-instrumented CPython flow model). No compiler or runtime file is touched (`git diff --name-only work..HEAD` = `docs/`, `lab/`).

**Verified**
- All 12 programs run on CPython 3.12 with a real `ail.types.BigInt = int` stub and match `expected/` byte-for-byte.
- `check_model.py`: 12/12 `OK`; no model run raises unexpectedly; flow counts equal the note's table.
- Prior review defect 2 is fixed: probes `xs[0] = big` (list[int]) records `overflow`, as do an unannotated parameter, an annotated `-> int` return with a BigInt value, and nested/starred unpack targets.
- No-feature program `/tmp/rprobes/plain.py`: `--debug-dir program.c` is byte-identical HEAD vs `/tmp/base` (work).
- Cited `pyfunc.py` lines 38742, 38806, 38834–38838, 38989, 39019 all exist as described.
- `tools/update_manifest.py --check` exit 0; `icount` really is unavailable (`perf_event_paranoid=4`); CPU cost numbers roughly reproduce.
- `test_ail_safetynet` passes on HEAD without the memory cap (255 s). Under `ulimit -v 1500000` `S4_generators_gc` truncates, but identically on base → pre-existing.

**Defects**
1. **Wrong file in the implementation map.** §5 names `AIL_CURRENT/python/pkg-v12/ail_modules.py`; that path does not exist — the resolver is `AIL_CURRENT/ail_modules.py` (`BUNDLED_DIR` at line 85). Expected: ffbig1 edits the real resolver; actual: following the note creates/edits a non-existent path.
2. **The proposed `pyfunc.py` hook crashes for ordinary units.** The note binds `_bigunit = intmode.exact_scope(_f.name)` = `None` for an ordinary unit, then uses `_bigunit.param(n)` / `_bigunit.ret` unguarded in the `_params`/`_ret` expressions. Probe (`/tmp/rprobes/p_hook_none.py`, the note's expression with `_bigunit=None`, `_all_tint=False`): expected `False` (the unit stays int64); actual `AttributeError: 'NoneType' object has no attribute 'param'`. Once the loop gate is widened, every unmarked function in a BigInt program hits this. Needs `_bigunit is not None and …` or a null-object marks return.

**Unverified:** `test_ail_files` / `test_ail_corpus_findings3` (not re-run per instructions); "not pushed" (n/a on this runner).

VERDICT: FIX
1. `AIL_CURRENT/python/pkg-v12/ail_modules.py` does not exist; the note must name `AIL_CURRENT/ail_modules.py`.
2. The note's one `pyfunc.py` hook dereferences `_bigunit` (documented as `None` for an ordinary unit) unguarded; probe `p_hook_none.py` gives `AttributeError` where the ordinary unit should take the int64 path.
[commandcode stop=end_turn turns=30 out_tokens=50268]


--- ORIGINAL TASK ---
Lane: ff-bigint

# ffbig0: design an explicit big-integer type for Python syntax (design note and probes only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs in `lab/bigtype/` with a written plan. Today a program that needs exact big ints
for one variable must use `--exact-int` for the whole program (about 20x slower, LIMITATIONS 1-2). fcbig1 covers
constants proven safe; nothing lets a user mark one variable as exact. The target is
`docs/design/BIGINT_TYPE.md`, 12 lab programs with CPython output, and a reference checker.

Base: `origin/integ`. Files you may create or edit, and no others:
- `docs/design/BIGINT_TYPE.md` (new)
- `lab/bigtype/*.py` (12 new), `lab/bigtype/expected/*.txt`
- `lab/bigtype/check_model.py` (new: a CPython-side checker that runs each program with `BigInt` as a subclass of
  `int` that records where an int64 value flows into it and where a `BigInt` flows back into a plain `int`)

The note must propose, with the alternatives and their cost:
1. **Spelling** that CPython runs unchanged, for example `from ail.types import BigInt` with `BigInt = int` in a tiny
   pure-Python module shipped in the wheel, used only as an annotation (`x: BigInt = 1`, parameters, returns, fields,
   `list[BigInt]`).
2. **Rules.** Arithmetic with a `BigInt` operand is exact; the result is `BigInt`. Storing a `BigInt` into a plain
   `int` place is checked and stops loudly with `OverflowError` outside int64. A literal beyond int64 is allowed only
   in a `BigInt` place.
3. **Runtime.** Reuse the exact-int representation of `--exact-int`; name the files in `cruntime.py` and the IR that
   hold it; give the cost per operation from 3 icount probes.
4. **Interaction** with fcbig1's proof route and with `--exact-int` (which keeps meaning "every int").
5. **Owner decisions** needed, each with a recommendation.

## Sub-steps

1. **Programs (20 min).** Factorial, Fibonacci beyond 2**63, a modular-power checker, a big counter field in a class,
   a list of BigInt sums, mixing BigInt and int in `//` and `%`, `str()`/`int()` round trips of 40-digit text, a
   BigInt passed to a plain `int` parameter (must stop loudly). Commit, push, open the PR.
2. **Checker (15 min).** `check_model.py` lists every flow; it must agree with the rules on 12/12.
3. **Note (25 min).** As above.

## Done-check

- 12 programs with CPython output; the checker classifies 12/12 as the rules predict.
- The note names the files ffbig1 changes and the one hook it needs in `pyfunc.py`.

## Stop rule

Stop if no spelling runs unchanged on CPython 3.12 without a third-party package. Stop when 60 minutes pass.
Push first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed. Never silent wrong output: stop and report the moment
   any program prints something CPython does not.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`, unless this task names the file and
   the one minimal hook it may add there (owner decision 3 of 2026-11-06: only when no other running job edits that
   file). Do not edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task
   names, plus the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly. Release builds use
  gcc -O2.
- Library policy: a small spec library is written in AIL (`AIL_CURRENT/stdlib/*.py`, found by `ail_modules.py`
  `BUNDLED_DIR`); TLS, signatures and SQLite go through proven native libraries.
- Runtime-backed modules follow `AIL_CURRENT/python/pkg-v12/proclib.py` (stage G8, subprocess): a tree-to-tree pass
  plus a C core header (`ailproc_core.h`), wired by two lines in `filelib.py` (`PRIMS.update(...)` near line 66 and
  `rewrite_tree(...)` near line 152). A program that does not import the module must produce byte-identical C.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.
- Speed claims: instruction counts with `tools/icount.c`, output unchanged.

## Owner decision (2026-11-06)

- BigInt spelling: `from ail.types import BigInt`; under CPython, `BigInt = int`. One minimal pyfunc.py hook is allowed, but only when no other running job edits that file.

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
