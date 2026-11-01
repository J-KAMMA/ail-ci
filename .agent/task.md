**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: `work..HEAD` (`3e1d988` + `3449d08`)

**What the change really does.** Adds `typing` to the stdlib-5 gate in `ail_syntax.python_surface` and adds `python/pkg-v12/typinglib.py`: TypedDict declarations are dropped and their names read as `dict`, `cast(T, v)` becomes `v`, and (after the fix) `NewType` calls become their argument with a helper for bad arity, chained bases accepted. This matches the report.

**Probes** (`bash ~/tools/cmp.sh`, both builds, HEAD):
- Same stdout/exit: `td_ctor`, `td_routes`, `nt_values`, `nt_decl_only`, `nt_map`, `nt_annotation_typed`, `pn_td_inherit`, `pn_td_places`, `pn_import_alias`, `pn_newtype_values2`, `pn_newtype_class`, `pn_newtype_chain`, `pn_errors`.
- Differ: `nt_errors` (defect 1), `nt_shadow` (defect 2).
- Refused by name (allowed): `cast_alias`/`pn_cast_alias`, `nt_local`, `pn_typing_attr`, `pn_newtype_introspect`, `pn_places`, `pn_cast_forms`; same on base where relevant.
- `td_instance2` (`isinstance`) and `nt_undef_base` differ but are the already-documented differences in DIFFERENCES rows 1/2; base refuses both.

**C identity.** For all 10 `lab/compare/src/*/main.py`, `python_surface` output is byte-identical to `/tmp/base` (none mentions `typing`); `pn_no_typing` and `pn_any` `--debug-dir` `program.c` are identical to base. No unrelated C changed.

**Tests.** `par_check -j 2 test_ail_std_typing test_ail_safetynet` → 2 modules, 0 failed (26.9 s / 149.4 s). `update_manifest.py --check` → 0.

**Claims.** Identity calls, alias, chained base, arity `TypeError` (type only), test extension, docs and manifest: verified. “4 modules 0 failed”: only the two review-required modules were re-run (verified); `test_ail_files` / `test_ail_corpus_findings3` not re-run (unverified). “Probes match CPython”: false for the exception text — every bad NewType call prints one hardcoded message.

**Pre-existing** (also on base): `TYPE_CHECKING`/`typing.X` use refused; `cast` used as a value/alias refused; function-local NewType/TypedDict declarations refused by name; general-path `map(...).__class__.__name__` prints `iterator` (not typing-specific).

---

`VERDICT: FIX`

1. **NewType arity/keyword `TypeError` text** — `/tmp/rprobes/nt_errors.py` (`try: UserId()` / `UserId(1, 2)` / `UserId(x=1)`, printing `type(e).__name__, e`).
   Expected (CPython 3.12): `TypeError _typing._idfunc() takes exactly one argument (0 given)` / `(2 given)` / `TypeError _typing._idfunc() takes no keyword arguments`.
   Actual (both HEAD builds): `TypeError NewType() takes exactly one positional argument` three times, exit 0. `typinglib.py:126-133` hardcodes a single message; it should emit CPython's three texts based on count/keywords.

2. **TypedDict/NewType name rewrite ignores lexical scope** — `/tmp/rprobes/nt_shadow.py` (local `UserId = 5`, parameter `UserId`).
   Expected: `6`, `8`, exit 0. Actual: exit 1, empty stdout, `TypeError: unsupported operand type(s) for +: 'function' and 'int'`; base refused the program by name, so the change introduced this. `typinglib.py:60,93` rewrites every Load/call by bare name without checking for a local/parameter binding; the same cause makes `td_shadow.py` fail with the meaningless `name 'dict' is not defined`.

3. **Task coverage** — none of the 12 `lab/stdlib/typing` programs contains a caught error, although the task asks for “errors that the program catches”. The test’s only error case checks the exception type, not its text, which is why defect 1 went unnoticed. Add a caught-error program that uses/prints the error.
[cost $0.0521, opencode tokens {"total": 2973983, "input": 95884, "output": 10408, "reasoning": 38379, "cache.write": 0, "cache.read": 2829312}]
    tool time: bash 5.8 min
        151s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_std
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_std_typing test
         25s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/dbgH /tmp/dbgB && mkdir /tmp/dbgH /tmp/dbgB && AIL_NO_CACHE=1 AIL
         12s bash   cd /home/runner/work/_temp/w2 && for p in pn_td_inherit pn_td_places pn_places pn_import_alias pn_typing_attr 
         10s bash   cd /home/runner/work/_temp/w2 && for p in td_ctor td_routes nt_values nt_errors cast_alias; do echo "#########
          4s bash   cat > /tmp/rprobes/td_instance2.py <<'PY' from typing import TypedDict   class Movie(TypedDict):     title: st
          4s bash   cat > /tmp/rprobes/nt_local.py <<'PY' from typing import NewType, TypedDict   def make():     Local = NewType(
          3s bash   cd /home/runner/work/_temp/w2 && for d in lab/compare/src/*/; do f="$d/main.py"; [ -f "$f" ] || continue; pyth


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `typing` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `typing` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/typing/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/typing/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_typing.py registered in tests.d), and compare them with CPython in the test.
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
