**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: ffdocs1 (docs site + link checker)

**What the change really does:** adds two stdlib-only Python tools — `tools/docs_links.py` (relative-link and heading-anchor checker for Markdown and built HTML) and `tools/docs_site.py` (Markdown→HTML static site with sidebar, search index, inline theme/search script, light/dark CSS) — plus `test_ail_docs_site.py`, its `tests.d` entry, manifest rows, `site/` in `.gitignore`, and one broken-link fix in `docs/spec/DIFFERENCES.md`. No compiler or runtime file is touched, so no AIL program's C can change and `cmp.sh` probes do not apply.

**Claims checked**
- Three previous defects fixed: **verified** (table→heading with no blank line; GitHub ids keep inline-code underscores and suffix duplicates from `-1`; reference definitions and raw `href`/`src` are checked).
- `DIFFERENCES.html` has both `differences-from-cpython` / `-1`: **verified**.
- Real tree 28 Markdown, 0 broken; site 29 HTML, 0 broken; 177 fenced blocks, 0 unconverted: **verified** with the tools.
- `test_ail_docs_site` 4/4: **verified**. `update_manifest.py --check`: **verified**.
- Safetynet `S4_generators_gc` fails under `ulimit -v 1500000`: **verified on HEAD, and identically on base** → pre-existing/environmental, not caused here. I did not re-run it without the cap.
- docsrun code-block count: **unverified/omitted** — the report never gives the task's "blocks docsrun already checks against the total" (docsrun covers 19 of the 177 docs blocks; README's block is outside `docs/`).

**Defect**

1. The generated site leaves relative links that escape the site root, so the published pages contain dead links, and the HTML checker silently skips exactly those.
   Probe `/tmp/rprobes/p2` (`a.md` contains `[outside](../outside.md)`; `/tmp/rprobes/outside.md` exists):
   ```
   python3 tools/docs_links.py /tmp/rprobes/p2      -> 0 broken, rc 0
   python3 tools/docs_site.py  /tmp/rprobes/p2 -o S -> rc 0, no warning
   grep href S/a.html                               -> href="../outside.md"
   (S/../outside.md does not exist -> 404 when published)
   python3 tools/docs_links.py --site S             -> 0 broken, rc 0
   ```
   Expected: the generator either publishes/rewrites the target or reports it as an unconverted construct (exit 1), since the task requires rendered pages with 0 broken links and nothing "dropped silently". Actual: `rc 0` and a link pointing outside the site. The real tree has **28 such hrefs** (`WHY.html` → `../lab/...`, `MIGRATING.html` → `../lab/...` and `../AIL_CURRENT/...`, `tutorial.html` → `../DIFFERENCES.md`), including `spec/DIFFERENCES.html` → `../../AIL_CURRENT/AIL_REFERENCE.md`, a link this very change introduced.

**Non-blocking observations (not in docs, so not defects today):** `## Head ##` keeps its closing hashes (`id="head-"`, text `Head ##`); `***x***` emits crossed tags `<strong><em>x</strong></em>`.

VERDICT: FIX
1. Generated-site relative links that leave the site root are emitted verbatim and never checked or warned (28 in `docs/`, one added by this change). Probe `/tmp/rprobes/p2`: expected a warning/exit 1 (or a resolving link); actual `docs_site` rc 0, `docs_links --site` rc 0, `a.html` has `href="../outside.md"` resolving to a nonexistent `/tmp/outside.md`.
[commandcode stop=end_turn turns=30 out_tokens=42602]


--- ORIGINAL TASK ---
Lane: ff-docs

# ffdocs1: a static docs website generated from `docs/`, with every internal link and code block checked

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** pages of `docs/` (with `docs/spec/` and `docs/design/`) rendered to HTML with 0 broken
internal links and 0 broken anchors. Today there is no site, and links are not checked. The target is all pages, 0
broken links, and a count of code blocks that `lab/docsrun` already checks against the total.

Base: `origin/integ`. Files you may create or edit, and no others:
- `tools/docs_site.py` (new): `python3 tools/docs_site.py docs -o site/`; standard library only (no new dependency):
  a Markdown subset converter for what `docs/` uses (headings with anchors, tables, fenced code with a language class,
  lists, emphasis, inline code, links), a sidebar from the file tree, a page per file, a search index as one JSON file
  and a small inline script, light and dark styles, no external fonts or scripts
- `tools/docs_links.py` (new): checks every relative link and `#anchor` in `docs/`; exit 1 with file:line on a break
- `docs/` files: only to fix broken links the checker finds (no text changes beyond the link)
- `AIL_CURRENT/test_ail_docs_site.py` (new), `tests.d` entry, `.gitignore` (add `site/`)

Publishing (GitHub Pages) needs a workflow edit and the owner's approval: not in this job. Write the steps in the
tool's docstring.

## Sub-steps

1. **Link checker (15 min).** Run it on `docs/`; record the count of broken links. Commit, push, open the PR.
2. **Generator (30 min).** Render every page; the generated site passes the same link check (HTML links); a page whose
   Markdown the converter cannot handle is listed, never dropped silently.
3. **Test (15 min).** The test runs both tools on `docs/` and fails on any broken link or unconverted construct.

## Done-check

- Broken links before and after are recorded (after: 0); every page renders; the test passes; the 20 shards pass.

## Stop rule

Stop if fixing a link would change the meaning of a sentence; list it instead. Stop when 60 minutes pass. Push
first.

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

- Workflow (.github/workflows) changes: write the exact steps into a doc; the maintainer opens the PR and the owner approves it.

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
