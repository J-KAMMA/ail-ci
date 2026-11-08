Lane: fd-lsp
Needs: fdlsp1

# fdlsp2: LSP hover with the compiler's inferred types, never a wrong one

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** names whose hover shows the type the typed path inferred, on a 35-name probe (the five lsp1b
review names `a b c d n` plus 30 more). Today hover shows a type only for literal-only names, annotations and
signatures, so the five review names show nothing. Target: at least 25/35 shown, 0 wrong. "Right" means equal to the
`type(x).__name__` that CPython prints for that name at that line.

Base: `origin/integ` (with fdlsp1 integrated). Files you may create or edit, and no others:
- `packaging/ail_lang/lsp.py`
- `docs/LSP.md`
- `lab/lsp/hover/*.py` (new) and `lab/lsp/hover/expect.json` (new); a "Hover" section in `lab/lsp/RESULTS.md`
- `AIL_CURRENT/test_ail_lsp_hover.py` (new) and `AIL_CURRENT/tests.d/test_ail_lsp_hover.txt` (new, one line:
  `test_ail_lsp_hover`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Probe and oracle (15 min).** Write the probe: the lsp1b program (`a = 1 / 2`, `b = not 1`, `c = abs(-3.5)`,
   `d = sum([1.5, 2.5])`, `n = round(1.2)`) and 30 more names: arithmetic, calls of user functions, `len`, `range`
   loop variables, list and dict element reads, `str` methods, a name assigned twice with different types (must show
   nothing), a name in a general-path function (nothing, or only what the compiler knows there). Make the oracle with
   an instrumented copy run by CPython that prints `type(x).__name__` at each probe line. Commit, push, and open the
   PR against `integ`.
2. **Find the source of types (20 min).** Do not edit any compiler file. Try, in this order, and record in
   `RESULTS.md` what each gives: `ail_chatgpt.py check --types-used`, `check --interface`, `compile --strict --json`,
   and the typed C of `--debug --debug-dir` (the C declarations `int64_t` / `double` / list structs together with the
   `#line N "file.py"` directives). Pick the one that gives a local's type from the compiler itself. Map C types back
   to Python names only where the mapping is one-to-one (`int64_t` -> `int`, `double` -> `float`, ...). Commit and push.
3. **Implement (15 min).** Hover shows `x: float (inferred by the typed path)` when the compiler gives it, keeps
   today's certain source answers, and shows nothing otherwise. Cache the result per document version; a build runs
   only after `didSave` or 1 s idle, never per keystroke. Commit and push.
4. **Test and docs (10 min).** `test_ail_lsp_hover.py` checks all 35 against `expect.json` (shown and right, or
   nothing) and skips the compiler part without a C compiler. Register it. Update the hover paragraph in
   `docs/LSP.md`. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_lsp_hover.py` and `python3 AIL_CURRENT/test_ail_lsp.py` pass.
- At least 25/35 shown, 0 wrong, in `RESULTS.md`.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop after sub-step 2 and report if no compiler output gives local types without editing a restricted file (Appendix A
rule 8): name the smallest hook that would (file, function, about how many lines), and push the probe. Stop at once
and report if any build prints output different from CPython (or from the reference this task names) without a refusal
or a loud stop: give the program, both outputs and the commit. Never commit a change that does that. Stop when 60
minutes pass. Push what is done first.

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
- The server: `packaging/ail_lang/lsp.py` (JSON-RPC over stdio, standard library only). Its docs: `docs/LSP.md`.
  Its test: `AIL_CURRENT/test_ail_lsp.py` (scripted sessions). Hover today shows a type only when it is certain from
  the source (literal-only names, annotations, signatures); a wrong type is worse than no type (lsp1b review).
- Diagnostics come from the same `ail check` front end that `ail build` uses; never write a second checker.
- `compile SRC -o OUT --strict --json` prints `ail.strict/1` JSON: `blockers[]` with `path`, `line`, `column`,
  `function`, `statement`, `construct`, `why`, `write_instead`, `blocks_functions` (checked 2026-11-06 on integ ff12fa93).

## Owner decision (2026-11-06)

- A small, isolated edit to a restricted file (pyfunc.py, pyc.py, cli.py, ail_chatgpt.py) is allowed, but only when no other running job edits the same file. Check the open job branches before you start. Keep the edit to a minimal hook.

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
