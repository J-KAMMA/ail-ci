Lane: typeshed

# typeshed2: the general path's unboxing pass reads stub return types for stdlib calls it types as `obj` today

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap). Runs after `typeshed1` is merged (it needs `stubsigs.py`).

**Number this moves:** `unboxed_vars` summed over the programs of `lab/census/programs/` and `lab/stdlib/` that call a
stdlib function whose stub return is `int`, `float` or `bool` (`tools/typeshed_reach.py --list`, the `scalar` sites).
`unified.py` writes it per program with `AIL_UNIFIED_STATS=<file>` (`plan.stats['unboxed_vars']`). Today every
`mod.f(...)` call is `OBJ` in `unified._etype`, so `x = math.gcd(a, b)` keeps `x` boxed and every operation on it is a
runtime call. Target: `unboxed_vars` up by at least 20 over the affected programs, with zero new output differences
against CPython. Second number: instruction count of `lab/typeshed/probe_gcd.py` (new, below) with `tools/icount.c`,
before and after; target at least 1.10x fewer instructions with the same output.

Base: `origin/integ` with `typeshed1` merged. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/unified.py`: one hook in `_etype` and one in `nexpr`, each a call into the new module.
  No other change to this file.
- `AIL_CURRENT/python/pkg-v12/stubcalls.py` (new): the analysis and emission logic for stub-typed calls
- `AIL_CURRENT/python/pkg-v12/stubsigs.py` (only to add a deny list, see below)
- `lab/typeshed/probe_*.py` (new programs) and `lab/typeshed/RESULTS.md`
- `AIL_CURRENT/test_ail_stubcalls.py` (new) and `AIL_CURRENT/tests.d/test_ail_stubcalls.txt` (new, one line:
  `test_ail_stubcalls`)
- the manifest files that `tools/update_manifest.py` writes

`pyboxed2.py` and `pyfunc.py` are not edited (Appendix A rule 8). `unified.py` already gets `comp.module_names`,
`comp.from_imports` and `comp.module_aliases` through `plan.module_names` (line ~980), which is all the hook needs.

## Where it plugs in

- Analysis: `unified._etype`, the final `return OBJ` for an `ast.Call`. Before that return, and only there, call
  `stubcalls.call_type(plan, fp, n, env)`. Every hand-written rule above it keeps priority, so a stub can never override
  `len`, `int`, `round`, `_DRAWS` or any other rule that already answers. A `None` answer from the hook keeps `OBJ`.
- Emission: `unified.nexpr`, the `ast.Call` branches. A call the hook typed is emitted as the general path's own call
  (`comp._expr_plain(node, ctx)`, unchanged code, unchanged error edges) followed by a **checked** unbox, emitted by
  `stubcalls.unbox_checked`. The existing `unified.unbox` checks only `AIL_T_BIG` for ints and turns an int into a double
  for floats; that is right for `len()` but not for a stub, which is a claim about CPython and not about AIL's code. The
  checked unbox tests the exact tag: `AIL_T_INT` for `int` (then `AIL_UNBOX_CHK` as today), `AIL_T_FLOAT` for `float`
  (no int-to-float conversion: `3` and `3.0` print differently), `AIL_T_BOOL` for `bool`. A mismatch stops the program
  loudly with a message that names the call and the stub type. No corpus program may reach it; one that does is a bug in
  this job, fixed by denying that entry.

Rules for `stubcalls.call_type`:
- the callee is `m.f(...)` with `m` an imported stdlib module name (not a local, not rebound), or `f(...)` with
  `f` in `comp.from_imports`; the qualname is the module's real name (resolve `import math as m`);
- `stubsigs.lookup(qualname)` gives `ret` in `int float bool` and no `overload` flag; anything else is `None`;
- no keywords and no `*args` unless the stub's params accept them by name (keep it simple: refuse to type, return
  `None`);
- `AIL_STUBCALLS=0` turns the hook off (always `None`); the default is on;
- in exact-int mode (`unified.exact_enabled()` or `fp.exact`) an `int` stub gives `None`: big ints stay boxed;
- a deny list `stubsigs.DENY = {qualname: reason}` for entries the probes below show unsafe. Expected candidates: a
  function whose int result can leave int64 from int64 arguments where the boxed path today prints the exact big value
  (`math.factorial`, `math.comb`, `math.perm`, `math.prod`, `math.lcm`). Probe, then decide: if the boxed path
  today prints the big value, unboxing would turn it into a stop, which is a regression; deny it.

## Sub-steps

1. **Baseline (15 min).** Run `tools/typeshed_reach.py --list` on both corpora and keep the programs with a `scalar`
   site (the affected set). Build each one with `AIL_UNIFIED_STATS=before.jsonl` and `--debug-dir`, in the default
   build and with `AIL_UNIFIED_FORCE=1` (`ulimit -v 1500000`, at most 2 at a time). Record per program: typed /
   general / refused, `unboxed_vars`, CPython match. Write `lab/typeshed/probe_gcd.py`: a loop of 10^6 steps that calls
   `math.gcd`, `math.isqrt`, `math.sqrt`, `math.floor`, `math.isclose` and does arithmetic on the results, and that
   uses one construct the typed path refuses so it builds on the general path (say which one). Record its icount.
   Commit, push, open the PR against `integ`.
2. **Hook (35 min).** Write `stubcalls.py` and the two hooks. Write probes in `lab/typeshed/`:
   `probe_big.py` (`math.factorial(25)`, `math.comb(100, 50)`, `math.prod([10**9] * 3)`, `math.lcm(2**40, 3**30)`),
   `probe_shadow.py` (a local or a function named `gcd`, `import math as m`, a module attribute rebound),
   `probe_types.py` (`math.floor(2.5)` is an int, `math.sqrt(4)` is a float and prints `2.0`, `math.isqrt(10**18)`,
   `bisect.bisect_left`, `random.random` after `random.seed(1)`), and `probe_text.py` (an int parsed from
   `"99999999999999999999"` passed to `math.gcd`). Each must print what CPython prints, or stop exactly as it stopped
   before this change, in both builds. Fill `DENY` from what they show. Commit and push.
3. **Measure and test (30 min).** Build the affected set again with `AIL_UNIFIED_STATS=after.jsonl`, both builds.
   Report in `RESULTS.md`: the `unboxed_vars` sum before and after, the programs whose `program.c` changed, every
   program whose output or exit status differs from CPython before or after (the after list must not be longer), and
   the icount of `probe_gcd.py`. Check that 20 programs with no `scalar` site have byte-identical `program.c`. Compile
   time: the median of 3 compiles of each `.py` source in `lab/compare/` before and after; the change must be under 2%
   (the hook imports the table only when the program has a stdlib module call). Write `test_ail_stubcalls.py`: it builds
   the five probes in both builds and compares stdout and the exit status with `python3`, checks that
   `probe_gcd.py`'s C holds an unboxed `int64_t` for the `math.gcd` result (look for the checked-unbox marker), and
   skips without a C compiler. Register it (Appendix A rule 6), run it, run `python3 AIL_CURRENT/test_ail_unified.py`.
   Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_stubcalls.py` and `python3 AIL_CURRENT/test_ail_unified.py` pass.
- `unboxed_vars` over the affected set rises by at least 20; the list of CPython differences is not longer than before.
- `probe_gcd.py`: icount before/after in `RESULTS.md`, at least 1.10x fewer instructions, same output.
- 20 unaffected programs have byte-identical `program.c`; compile time within 2% on `lab/compare/`.
- `unified.py`'s diff is the two hooks only (`git diff origin/integ -- AIL_CURRENT/python/pkg-v12/unified.py` under 15
  lines).
- The 20 shards pass.

## Stop rule

Stop and report if the affected set has fewer than 10 programs that build on the general path (the gain would be
too small to show; give the count and the typed / general split). Stop and report if `probe_gcd.py` gains less than
1.05x: give the icount and the generated C of the loop body. Stop if a hook needs an edit to `pyboxed2.py`; name the
missing piece. Stop when 80 minutes pass. Push what is done first.

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes (pyreach, frontend) own them. Do
   not edit `DEVLOG.md` either: put your notes in the files this task names.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet. A fallback to the general path prints `note: ... built on the general path
  ...` on stderr. `AIL_UNIFIED_FORCE=1` forces the general path.
- `unified.py` (default on, `AIL_UNIFIED=0` opts out): `_etype` (~line 2096) is the lattice `int float bool obj`;
  `nexpr` (~line 2511) emits a proven value; `unbox` (~line 2345) and `_unbox_rv` read a boxed value; `Conflict`
  demotes a function to boxed and recompiles; `record` writes `AIL_UNIFIED_STATS`. `AIL_UNBOX_CHK` is in `cruntime.py`
  (~line 17567). Tags: `AIL_T_INT`, `AIL_T_FLOAT`, `AIL_T_BOOL`, `AIL_T_BIG`.
- Speed claims are judged by `tools/icount.c` instruction counts with the output unchanged, not by wall time.
- CPython 3.12 is the oracle.

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
