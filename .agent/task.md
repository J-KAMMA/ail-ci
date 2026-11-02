**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 0
[model opencode-go/deepseek-v4.1-flash]
Review of `work..HEAD` (`0ee1265`).

**What the change really does:** registers `random` in the tuple pass (`modalias`/`fromnames`) and types `random.choice(list_of_tuples)` as the list's element tuple, so `dx, dy = random.choice(moves)` becomes field reads and the program stays on the typed path. It also adds the prog19 table and tests.

**Claims checked**
- g11_018 whole program typed, both IR, matches CPython: **verified** (probe `p0_g11_018`, plus `AIL_NO_GENERAL=1` IR 0/1; base refuses with `tuple assignment from Subscript`).
- g00_038, t128, g11_012 already typed: **verified** (strict builds match CPython).
- **t030 already typed: FALSE.** Default build emits `note: ...t030.py:7:5: built on the general path ... because (int(x) for x in data[1:1 + n]) cannot be walked inline here...`; strict refuses with the same named error. Base emits the identical note and binary. Its hot function `main` is not typed and no follow-up was recorded.
- g10 / t078 / g14 follow-ups and messages: **verified** (g10 6:1 module-table error, t078 5:5 `ord()`, g14 87:5 `json.loads`; g14 also says general path cannot build).
- 10 lab/compare AIL C byte-identical; 6 Python C identical; 4 Python refusals identical: **verified** (compiled all under HEAD and base).
- Tests (`prog19`, `tuples`, `genlib`, `safetynet`): **verified**, 4/4 passed. `test_ail_files`, `test_ail_corpus_findings3`, profiles, and icount: **unverified** (not rerun; `perf_event_open` denied on this runner).

**Probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh` with general and default builds): `p0_g11_018`, `p1_basic`, `p2_places` (param/alias/list item/dict value), `p3_boundaries` (empty/IndexError, negative, float), `p4_scalars`, `p5_mutate` (append/delete during loop), `p6_value` (tuple value, len/index), `p7_nofeature`, `p8_shapes` (2/3/nested tuples, list-of-list), `p10_use`, `p11_direct` (attribute/list item/dict/return), `p12_err` (unpack mismatch ValueError), `p13_alias_import`, `p14_fromfuncs` (bare `seed/randint/shuffle/sample`). All matched CPython on both builds; no C change for p7/random programs without `choice`. `p9_contexts` (nested genexpr) refuses by name identically on base (pre-existing).

**Pre-existing:** t078's compiled program gives `AIL internal error: stdin code point above U+FFFF in the 16-bit v2 runtime` while CPython prints the characters — identical on base. `p9_contexts` nested-generator refusal also identical on base.

VERDICT: FIX
1. `lab/progfix/prog19.md` row for `dev/t030.py` is false and no follow-up is recorded. Repro: `AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile lab/census/programs/dev/t030.py --syntax python -o /tmp/t030`. Expected (per report): no general-path note / "already typed". Actual: `note: ...t030.py:7:5: built on the general path (about 20x slower) because (int(x) for x in data[1:1 + n]) cannot be walked inline here; bind it to a name first...`; with `AIL_NO_GENERAL=1`: `not in the subset: (int(x) for x in data[1:1 + n]) cannot be walked inline here...`. Record t030 as not typed with this reason (or fix it), as the task requires for every hot function.
[cost $0.0249, opencode tokens {"total": 1452936, "input": 57670, "output": 9325, "reasoning": 10837, "cache.write": 0, "cache.read": 1375104}]
    tool time: bash 17.0 min
        569s bash   cd /tmp && rm -rf cmpC && mkdir -p cmpC/head cmpC/base && for d in /home/runner/work/_temp/w2/lab/compare/src/
        270s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_
         62s bash   cd /tmp && rm -rf nfC && mkdir nfC && for src in /tmp/rprobes/p7_nofeature.py /home/runner/work/_temp/w2/lab/c
         54s bash   cd /tmp/rprobes && for p in p0_g11_018 p1_basic p2_places p3_boundaries p4_scalars p5_mutate p6_value p7_nofea
         12s bash   cd /tmp/rprobes && cat > p11_direct.py <<'EOF' import random from typing import Tuple  class Board:     def __
          9s bash   cd /tmp && rm -rf eight && mkdir eight && cd eight && W=/home/runner/work/_temp/w2; for p in dev/t030 gdev/g00
          7s bash   cd /tmp/rprobes && cat > p12_err.py <<'EOF' import random from typing import Tuple  def main() -> None:     ra
          6s bash   cd /tmp/rprobes && cat > p14_fromfuncs.py <<'EOF' from random import seed, randint, random, shuffle, sample, u

## fix round skipped: only 40 minutes left


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/census/programs/dev/t030.py`
- `lab/census/programs/gdev/g00_038.py`
- `lab/census/programs/gdev/g10_036.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t078.py`
- `lab/census/programs/dev/t128.py`
- `lab/census/programs/gdev/g11_012.py`
- `lab/census/programs/gdev/g14_016.py`
- `lab/census/programs/gdev/g11_018.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog19.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog19.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

Run `python3 tools/update_manifest.py`, then only the new test module, the test modules of the files you touched, and `test_ail_safetynet`. Then commit.

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
