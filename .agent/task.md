# wedge4: hybrid-native methods and inferred return kinds (the top 2 remaining refusals)

Lane: hybrid
Needs: wedge2

wedge2 (integrated) made indexing native and named every refusal; there are no silent refusals left. It moved the
native share only from 24.7% to 29.9% (29/97 functions in lab/wedge), and gave no speedup. The top remaining refusal
reasons, by profiled self time, are:

| Reason | Share |
|---|---|
| not-a-top-level-function (methods, nested functions) | 20.9% |
| unresolved-return | 20.4% |
| call-can-raise | 13.0% |
| unresolved parameter kinds (`node`, `adj`, `words`, `data`) | ~29% together |

Real libraries are mostly classes, so methods matter most for the coming wedge3 run on real libraries.

## Work, in this order

Stop after each step that lands cleanly.

1. **Methods.** Let a method of a plain class (no metaclass, no `__slots__` tricks, no `__getattr__`) go native when
   its body passes the existing safety gate.
   - `self` attribute reads and writes go through the CPython object. Keep it correct first; fast comes later.
   - Nested functions that capture nothing count the same as top-level functions.
2. **unresolved-return.** Infer the return kind from every `return` in the function, where all of them agree. Where
   they do not agree, refuse by name, as today.
3. **Unresolved parameter kinds.** Use the call sites inside the module and the parameter annotations, when present.
   Never guess: a parameter whose kind cannot be proven stays on CPython.

## Rules

- Output must match CPython byte for byte. Anything not proven stays on CPython with a named reason.
- Do not change the default (non-hybrid) build.

## Tests

Add tests to the hybrid test modules covering:
- methods: attribute reads and writes, a method calling a method, and an exception raised inside a method;
- returns of mixed kinds;
- annotated and unannotated parameters.

Run them one after another under `ulimit -v 2500000`.

## Report

- the native share before and after on lab/wedge;
- the hybrid/CPython ratio for each module;
- the new top refusal reasons;
- test results with times.

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
