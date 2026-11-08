**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review: stdfall2c (copy/timeit/marshal fix round)

**What the change really does:** `marshal.dumps` now only writes CPython's v0–2 bytes and refuses v3/4 (the six marshal lab programs were edited to pass `version=2`); `copy` refuses class instances of any kind and re-implements the caller's memo as a module-global `_memo_links` side table keyed by `len(dict)`; `timeit` drops the `number < 0` check; `copy/02` gains frozenset/big-int lines.

**Verified**
- `p_copy_frozen2`, `p_copy_frozen`, `p_copy_tuple_bigint`: same stdout in both builds (frozenset always-new + memo, big-int tuple memo).
- `q_marshal_v012` (all int64 boundaries, bools, None, ±0.0, 1e300, inf, UTF-8, bytes, containers × versions 0/1/2) and `q_marshal_negzero2`: identical to CPython in both builds. v0–2 really is exact.
- `q_timeit_neg` (`number=-1`, `repeat=-1`): same as CPython.
- `q_copy_bytearray_alias`, `q_copy_tuple_sizes` (lengths 0/1/5, nested): same.
- No-feature probe `q_nofeat`: `--debug-dir/program.c` byte-identical to `/tmp/base`; it doesn't use the feature.
- `par_check -j 2 test_ail_std_stdfall2 test_ail_safetynet`: 2 modules, 0 failed. `update_manifest.py --check` clean. `test_ail_third_party_notices`/`test_ail_std_stdfall1` indeed absent.
- Report's "v4 is a named ValueError refusal, programs use version=2": true, but it is a **run-time** refusal (the test builds then runs), not the build-time named refusal the fix instruction asked for; and the lab programs were edited instead of the module (task step 3: "fix the modules, never the programs").

**Defects (caused by this change; base matches CPython)**
1. `copy.deepcopy(x, memo_dict)` returns stale copies after the caller clears/reuses the dict. `q_copy_memo_clear.py`: CPython/base `[1] [1, 2]`, HEAD `[1] [1]`. `_memo_links` is a process-global registry that survives `memo.clear()`, so `_memo_get` finds an old entry that the caller's dict no longer holds. Silent wrong value; base was correct, so this is a regression.
2. `copy.deepcopy(x, memo_dict)` corrupts the caller's dict. `q_copy_memo_keys.py` (`m={2:"x",5:"y"}`): CPython `x y 4 [7]`, HEAD `[[7]] y 2 [7]` — `_memo_put`/`_memo_keepalive` write with `d[len(d)]`, overwriting key 2 and leaving the wrong entry count. Consequence of the same design: the dict itself is never read, so pre-seeded `memo[id(x)] = copy` entries are ignored (could not probe: that program fails to build on base too — type-inference note `tuple(...) (a tuple of a run-time length)`).
   Fix direction: key the caller's dict by `id(obj)` and look it up there; keep only the CPython keep-alive entry; delete the global `_memo_links` (it also leaks every memoised object forever).

**Pre-existing (unchanged by this diff)**
- `marshal.loads(b"")` → `EOFError: marshal data too short` vs CPython `EOF read where object expected` (`q_marshal_loadsv4.py`; reader string untouched).
- `marshal.dumps(x, None/2.0/"2"/5)` argument validation differs (ValueError "version 4…" vs CPython TypeError; v5 accepted as 4 by CPython) — loud, not silent (`q_marshal_verargs.py`).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, CI shards; pre-seeded memo semantics (no compiling probe); speed not applicable — no compiler/runtime/bench file is touched.

VERDICT: FIX
1. `copy.deepcopy(x, memo)` stale after `memo.clear()` — probe `q_copy_memo_clear.py`: expected `[1] [1, 2]`, actual `[1] [1]` (base is correct; regression).
2. `copy.deepcopy(x, memo)` overwrites caller keys / wrong length — probe `q_copy_memo_keys.py`: expected `x y 4 [7]`, actual `[[7]] y 2 [7]`.
3. The marshal lab programs were edited to `dumps(x, 2)` instead of fixing the module/recording the refusal; the v3/4 refusal is at run time, not build time (task step 3 / review item 5's "build time" standard).
[commandcode stop=end_turn turns=54 out_tokens=40524]


--- ORIGINAL TASK ---
Lane: stdfall

> Continuation of stdfall2. Antigravity finished step 1 only (18 lab programs + baseline RESULTS.md, 0/18) on branch ag-stdfall2 (commit 8a739174e) and then ran out of quota; PR #416 is open but has no modules yet. Start from origin/integ, cherry-pick 8a739174e, then do steps 2-4 below. Do not open a new PR.

# stdfall2: `copy`, `timeit` (CPython) and `marshal` (PyPy lib_pypy) in compiled programs, shipped as AIL source

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on stdfall1 merged (same lane, same notice entries) and on relnotice1 merged.

**Number this moves:** programs in `lab/stdlib/{copy,timeit,marshal}/` that build in the default mode and print what
CPython prints, with the same exit status. Today 0/18. Probe on integ 18703a92 (2026-11-05), default build:
- `copy.copy` and `copy.deepcopy` -> `not in the subset: copy.copy (not yet published in NAMES_library.json)`;
- `timeit.default_timer` -> `not in the subset: timeit.default_timer (not yet published in NAMES_library.json)`;
- `marshal.loads` -> `not in the subset: marshal.loads (not yet published in NAMES_library.json)`.
The target is at least 14/18, with at least 4/6 for `copy` and `timeit`. `marshal` is the trial of a lib_pypy (MIT)
source: CPython's `marshal` is C, PyPy's `lib_pypy/_marshal.py` is pure Python. If its bytes differ from CPython's
`marshal.dumps`, it ships only `loads` of the formats that match, or not at all (see Stop rule).

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/copy.py`, `AIL_CURRENT/stdlib/timeit.py`, `AIL_CURRENT/stdlib/marshal.py` (new)
- `AIL_CURRENT/stdlib/LICENSE-PYPY-MIT.txt` (new: PyPy's `LICENSE` file text, MIT part, copied verbatim with its
  copyright lines, from the same PyPy revision the code comes from)
- `lab/stdlib/{copy,timeit,marshal}/*.py` (6 new programs each) and `lab/stdlib/stdfall2/RESULTS.md` (new)
- `THIRD_PARTY_NOTICES.md`: one entry per new file
- `AIL_CURRENT/test_ail_std_stdfall2.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_stdfall2.txt` (new)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Programs and baseline (15 min).** 6 programs per module, 10-30 lines each:
   - `copy`: `copy.copy`/`deepcopy` of nested lists, dicts, tuples, sets, a user class (with and without
     `__copy__`/`__deepcopy__`), a list that contains itself (the memo), shared sub-objects stay shared in the copy;
   - `timeit`: `default_timer()` difference is a float `>= 0`; `Timer(callable).timeit(number=3)` and
     `.repeat(repeat=2, number=2)` with a callable that counts its calls (print the count and `type()` of the result,
     never the time); `timeit.timeit(callable, number=5)`. String statements need `exec`: a program using one must
     be refused by name, not run differently;
   - `marshal`: `marshal.loads(marshal.dumps(x))` for ints (with `2**70`), floats, strings, bytes, lists, tuples,
     dicts, None/True/False; print `marshal.dumps(x).hex()` too, which is CPython's exact byte layout (version 4).
   Build each; record "Before" in `RESULTS.md`. Commit, push, open the PR against `integ`.
2. **The modules (30 min).**
   - `copy.py` and `timeit.py` from CPython 3.12 source (`inspect.getsource`), first docstring line
     `Derived from CPython 3.12 Lib/<name>.py; PSF License, see stdlib/LICENSE-PSF.txt.` Rewrite only what is
     refused (the census blocker for `copy` is `'weakref' is imported and also assigned`); keep behaviour and
     messages. `timeit` keeps only the callable form; a string `stmt` raises at build time with a named refusal.
   - `marshal.py` from PyPy's `lib_pypy/_marshal.py` on a Python 3 branch (for example `py3.10`), pinned to one
     commit hash written in the docstring: `Derived from PyPy lib_pypy/_marshal.py @ <hash>; MIT License, see
     stdlib/LICENSE-PYPY-MIT.txt.` Compare its `dumps` bytes with CPython's for every program value first; where
     they differ, make it match CPython (CPython is the oracle) or refuse that type by name.
   Add the entries to `THIRD_PARTY_NOTICES.md`. Commit and push.
3. **Make the programs pass (20 min).** Build all 18 again; fix the modules, never the programs. Write each
   compiler-side refusal into `RESULTS.md` as a follow-up with its exact text. Commit and push.
4. **Test (15 min).** `test_ail_std_stdfall2.py` as in stdfall1 (default build and `AIL_UNIFIED_FORCE=1`, compare
   with `python3`). Register it (Appendix A rule 6). Run it, `test_ail_third_party_notices` and
   `test_ail_std_stdfall1`. Fill "After". Commit, push, wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_stdfall2.py` and `test_ail_third_party_notices` pass.
- At least 14 of the 18 programs build and match CPython in both builds (at least 4/6 for `copy` and `timeit`).
- Every `marshal.dumps` that ships gives CPython's bytes on all 6 programs.
- The 20 shards pass; `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop on any wrong output against CPython (stdout, exit status, `dumps` bytes) in either build: record it in
`RESULTS.md` first, then fix the module or refuse that use. If PyPy's license text or the source revision cannot be
pinned in 5 minutes, drop `marshal` and say so; never guess a license. Stop when 80 minutes pass. Push what is done
first.

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
   `pyc.py`, `optlib.py`, `buildcache.py`, `pyboxed2.py`, `unified.py`, `stubcalls.py`, or
   `packaging/ail_lang/cli.py`. Do not edit `DEVLOG.md`. Edit only the files this task names, plus the manifest files
   that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`.
- `AIL_CURRENT/stdlib/*.py` modules are found by `import X` after the program's own directory and `AIL_PATH`
  (`ail_modules.py`, `BUNDLED_DIR`). A bundled file shadows AIL's own model of the same module name, so bundle only
  modules with no model (all three here). Examples: `stdlib/getopt.py`, `test_ail_std_shlex.py`, and stdfall1's files.
- PyPy is MIT; CPython is PSF-2.0. Both may be copied with attribution; `THIRD_PARTY_NOTICES.md` is the record.
- CPython 3.12 is the oracle.

## Owner decision (2026-11-05)

- PyPy's MIT code (marshal) may be bundled, with its notice in stdlib/LICENSE-PYPY-MIT.txt, also listed in THIRD_PARTY_NOTICES.md.

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
