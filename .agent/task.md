**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
I've completed the review. Here is what I found.

## What the change really does

It adds `textDocument/definition` to the language server (`definitionProvider` + a resolver built on the existing `_scope_chain`/`_scope_info`, plus module lookup through `ail_modules.Program`), fixes comprehension first-iterable scope, UTF-16 output ranges, `except`/`match` name spans, and `import a.b` binding. No compiler/runtime file is touched, so generated C cannot change (verified: diff has no `AIL_CURRENT/ail_*`, no runtime, no `tools/`).

## Probes (all in-process `lsp.definition` queries; positions located by whole-word search)

| probe | case | expected | got |
|---|---|---|---|
| u1 | `a = A(); a.m()` / `b = A; b.m()` | `class A` method `m` | correct `A.m` |
| u1 | `_class_refs_of_value` through a local | `A` | correct |
| u2 | `f"{name}"`, `{{name}}`, `name!r` | def / null / def | correct |
| u2/u3 | f-string capture, decorator, base class `class B(A)` | def / null | correct |
| u3 | `@deco def sweet` | `deco` def, `sweet` def | correct |
| u4 | `except* … as err`, `case Point(x=px)` | `err`/`px` binding, unknown `Point` null | correct |
| u5 | CRLF file | def | correct |
| u6 | non-ASCII identifier `héllo` | def | correct |
| u7 | `import pkg.sub` vs `import pkg.sub as alt` | pkg `__init__` / `sub.py` | correct |
| u8 | keyword label `f(a=1)` | null | null |
| u9 | `global x` read/write/declaration | module `x` | correct |
| m1 | nested comprehension `[[x for x in xs] for xs in xs]` | inner iter → outer target, outer iter → module | correct |
| m2 | `case {Color.RED: v, **RED}` | `**RED` binding | **null** (missing, not wrong; duplicate-name heuristic) |
| harness2/3 | main/edge/use_pkg 40+20 positions | per `expect.json` | all match |

Base (`/tmp/base`) has no definition provider at all, so there are no pre-existing behaviour differences to compare; no probe produced a wrong location, a crash, or a wrong exit status.

Tests on HEAD: `test_ail_lsp_def` ok, `test_ail_lsp` ok, `test_ail_safetynet` ok (3 modules, 0 failed). `tools/update_manifest.py --check` → 0.

## Claim check

- comprehension iterable, `import a.b`→package, UTF-16 ranges, `except`/`match` spans — **verified**.
- 50/50, 0 wrong — **verified**; I also re-derived all 40 original expectations against the sources and they are semantically right.
- "Diff touches only lsp.py, lab probes/expect/RESULTS, the test, and manifest.d/e7.txt" — **false**: `docs/LSP.md` and `manifest.d/83.txt` also change (allowed), and four `lab/lsp/def/.ail-lsp-*.py` files are added.
- "committed as 924171e" — **false**: HEAD is `a4ed8ab "fix: uncommitted edits"`, which adds only the four temp-file copies.
- safetynet S4 failure under `ulimit` — **unverified** (it passes without the limit here; the change touches no runtime code).
- test_ail_files / test_ail_corpus_findings3 — **unverified** (not required for this change).

## Defects

1. The new test is not hermetic and commits its litter. `python3 AIL_CURRENT/test_ail_lsp_def.py` leaves generated `.ail-lsp-*.py` files in `lab/lsp/def/` (I produced two new untracked ones just running it; `Client.close` kills the server while `Server.analyse` still has an `mkstemp` sibling open). Four byte-identical copies of `main.py` were then committed in `a4ed8ab`. Expected: `git status` clean after the test and no extra files in the commit; actual: `?? lab/lsp/def/.ail-lsp-_lfvt1sc.py`, `?? lab/lsp/def/.ail-lsp-wlvb5sgt.py` after a run, and `.ail-lsp-h4irn4or/sk2g18gl/u25zw6cr/w7lhu_jw.py` committed. Fix: wait for the server to exit (or drain requests) before killing it, and delete the four committed files.

Minor notes: `_module_member_location` is dead code; the `docs/LSP.md` phrase "or an instance" overclaims (`a = helper.Picker(); a.m()` returns null — safe, but the doc says otherwise).

## Pre-existing

None observed.

VERDICT: FIX

1. `test_ail_lsp_def.py` leaves `.ail-lsp-*.py` temp files in `lab/lsp/def/` on every run, and four such copies were committed in `a4ed8ab` (a commit the report does not mention). Expected: a clean working tree after the test and only the listed files in the diff; actual: two untracked `.ail-lsp-*.py` files after a run plus the four committed copies `.ail-lsp-h4irn4or.py`, `.ail-lsp-sk2g18gl.py`, `.ail-lsp-u25zw6cr.py`, `.ail-lsp-w7lhu_jw.py`.
[commandcode stop=end_turn turns=36 out_tokens=45251]


--- ORIGINAL TASK ---
Lane: fd-lsp

# fdlsp1: LSP go-to-definition (`textDocument/definition`) for .py files

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** correct definition answers on a 40-position probe. Today `ail lsp` does not answer
`textDocument/definition` (0/40). Target: at least 36/40 correct and 0 wrong. A wrong location is worse than none:
when the target is not certain, answer `null`.

Base: `origin/integ`. Files you may create or edit, and no others:
- `packaging/ail_lang/lsp.py`
- `docs/LSP.md`
- `lab/lsp/def/*.py` (new probe files), `lab/lsp/def/expect.json` (new) and `lab/lsp/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_lsp_def.py` (new) and `AIL_CURRENT/tests.d/test_ail_lsp_def.txt` (new, one line:
  `test_ail_lsp_def`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Probe (15 min).** Write 4-6 small `.py` files in `lab/lsp/def/` (a main program, a helper module beside it, a
   module in a directory put on `AIL_PATH`, and one that imports a bundled module from `AIL_CURRENT/stdlib/`).
   Write `expect.json`: 40 cursor positions (file, line, character) and the expected target (file, line, character) or
   `null`. Cover: a local with one binding, a local with two bindings in one scope (answer every binding), a
   parameter, a global read inside a function, `global` and `nonlocal`, a function, a class, a method through
   `self.m()`, `from helper import pick`, `import helper` then `helper.pick`, a bundled module name, a
   comprehension variable, a name inside a string or comment (`null`), an attribute of an unknown object (`null`),
   a builtin (`null`). Record "Before": 0/40. Commit, push, and open the PR against `integ`.
2. **Implement (25 min).** Add `definitionProvider: true` and the handler. Reuse the scope code already in `lsp.py`
   (`_scope_chain`, `_scope_info`, `_name_at`); do not build a second resolver. Imports follow the compiler's
   search order: the program's directory, then `AIL_PATH`, then the bundled `AIL_CURRENT/stdlib/` (see
   `AIL_CURRENT/ail_modules.py`, `BUNDLED_DIR`); import that function rather than copying it if `lsp.py` can.
   Use the open buffer's text, not the file on disk, for open documents. Commit and push.
3. **Measure (10 min).** Score all 40; fix `lsp.py` until at least 36 are right and none is wrong. Commit and push.
4. **Test and docs (10 min).** `test_ail_lsp_def.py` runs a scripted session over the probe files and checks every
   position in `expect.json`. Register it (Appendix A rule 6). Add a `textDocument/definition` row to the table in
   `docs/LSP.md`. Fill `RESULTS.md` "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_lsp_def.py` and `python3 AIL_CURRENT/test_ail_lsp.py` pass.
- At least 36/40 correct, 0 wrong, in `RESULTS.md`.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if the existing scope code in `lsp.py` cannot resolve imports without copying the module search; say
what is missing. Stop at once and report if any build prints output different from CPython (or from the reference this
task names) without a refusal or a loud stop: give the program, both outputs and the commit. Never commit a change
that does that. Stop when 60 minutes pass. Push what is done first.

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
