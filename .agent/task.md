Lane: fd-arr

# fdarr1: ail_array T3a, native f32 arrays: element-wise ops and fixed-order reductions, exact

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** f32 case files of a new `array_t3_cases/` that build and print exactly what CPython prints with the
reference: 0/8 today (`ta.f32` is refused by name), target 8/8 in the default build and with `AIL_UNIFIED_FORCE=1`.
f16 and int8 stay refused by name in this job.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/ailarray.py` and `AIL_CURRENT/python/pkg-v12/prelude_ailarray.py`
- `AIL_CURRENT/array_t3_cases/*` (new) and `AIL_CURRENT/test_ail_array_t3.py` (new)
- `AIL_CURRENT/tests.d/test_ail_array_t3.txt` (new, one line: `test_ail_array_t3`)
- `AIL_CURRENT/docs/design/TYPED_ARRAY.md` (status lines of T3 only)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Cases (15 min).** Write 8 case files, each with dozens of inputs per binary (TYPED_ARRAY.md 9): construction and
   the store rule (3.4: `ta.array([0.1], ta.f32)[0]` prints `0.10000000149011612`); `+ - * /` and unary `-`, `abs`
   on arrays and with Python scalars; `+= -= *= /=`; `ta.sqrt`; `ta.minimum`/`ta.maximum`; `ta.sum` and `ta.dot`
   with sizes 0, 1, 15, 16, 17, 1023, 1024, 1025, 5000 (lane and block boundaries of 3.5); `tolist`, `tobytes`,
   `repr`; `astype` f64 <-> f32 (3.4). Edge set in every float case: +-0.0, smallest subnormal and normal of f32,
   `2**24 + 1`, halfway values for the f32 rounding, inf, NaN (canonical NaN bytes per 3.1), overflow to inf.
   Run each under CPython with the reference; record "Before" (refused) in the test docstring. Commit, push, and open
   the PR against `integ`.
2. **Lowering (30 min).** Remove `f32` from `LATER`. Storage is C `float`; every op computes in binary64 and rounds
   once (3.2), never `float` arithmetic in C, and the C build keeps `-ffp-contract=off`. Reductions use exactly the
   reference's order and accumulator (3.5), not a C loop in index order. Follow the f64 code of T2 for errors and
   refusals; mixed f32/f64 operands follow 3.6 (refuse what 3.6 refuses, by name). Commit and push.
3. **Test (15 min).** `test_ail_array_t3.py` builds each case in the default build and with `AIL_UNIFIED_FORCE=1` and
   compares stdout and the exit status with CPython + reference; skips without a C compiler. Register it. Run it,
   `test_ail_array_t2.py`, `test_ail_array_t6.py` and `test_ail_array_ref.py`. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_array_t3.py` passes: 8/8 cases in both builds.
- `test_ail_array_t2.py`, `test_ail_array_t6.py`, `test_ail_array_ref.py` still pass.
- Programs that do not import `ail_array` give byte-identical C (check the `lab/compare/src` programs).
- The 20 shards pass; `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if an f32 result can only be made bit-equal by changing the reference; give the case. Stop at once and
report if any build prints output different from CPython (or from the reference this task names) without a refusal or
a loud stop: give the program, both outputs and the commit. Never commit a change that does that. Stop when 60 minutes
pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug] [--debug-dir DIR]`.
  `DIR/program.c` is the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback
  to the general path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations (`.py` files only; the `.ail` brace syntax is retired). Ints are
  int64, and overflow stops loudly. Never silent wrong output: a value AIL cannot compute exactly is refused by name
  or stops loudly.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.
- `ail_array` design: `AIL_CURRENT/docs/design/TYPED_ARRAY.md` (API table 2.1, exact rules 3.1-3.8, stages 10,
  owner decisions 12: TA1 int overflow raises `OverflowError`, TA2 IEEE for floats, TA3/TA4 one fixed 16-lane,
  1024-block order for `ta.sum`, `ta.dot` and `ta.matmul`). The reference `AIL_CURRENT/ail_array.py` run by CPython is
  the oracle; change it only for a proven bug, with a note in TYPED_ARRAY.md.
- Built on integ ff12fa93: T1 (reference), T2 (f64 and int32 1-D, `test_ail_array_t2.py`), T6 (2-D f64, exact CPU
  `ta.matmul`, `test_ail_array_t6.py`). f32, f16 and int8 are refused by name (`LATER` in
  `python/pkg-v12/ailarray.py`). The torch-like layer (`TORCH_COMPAT.md`, P1) builds on these dtypes later.

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
