**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does.** It extends typed-path inference in three places: tuple/list targets bound from same-shape tuple/list expressions (`iterlower.py`), conditional expressions whose branches are numeric lists (`_numeric_field_kind`), and unannotated int-keyed set operators (`& | - ^`), including a scan that keeps str/bytes-keyed sets on the general path.

**Probes.** I wrote and ran 144 probes in `/tmp/rprobes` on HEAD and, where they failed or exercised the new path, on a fresh `/tmp/rbase23` worktree at `work`. Coverage: empty/negative/int64/bool/float/tuple/mixed sets; all four operators; aliases, mutation, rebinding, iteration; conditionals with empty/mixed/list-var/field/float branches; tuple/list targets with slices, literals, comprehensions, calls, starred/nested/mismatched targets; values through arguments, list items, attributes and dict values. All matched CPython except one new defect below. One new failure was found; several failures were identical on base (listed under Pre-existing).

**Tests.** `test_ail_prog23` and `test_ail_safetynet` pass (41 s / 169 s); additionally `test_ail_sets_general` and `test_ail_tuples` pass. `tools/update_manifest.py --check` passes.

**Claim check.**
- t115/t143: base `--strict` refuses (with the reported messages), HEAD `--strict` succeeds — verified.
- g02_026, t102, t069, g18_030 already typed on base — verified.
- g15_004/g25_026 first reasons are exactly as reported — verified.
- All ten `lab/compare` generated `program.c` files byte-identical to base — verified.
- “Both changes affect only programs that previously were refused”: **false** — the probe below was accepted via the general fallback before and now fails to build.
- Worker’s 49 probes and profiling timings: **unverified** (not re-run; no exact copy checked).

**Pre-existing (identical on base).** Float-keyed unannotated sets print ints (`set_call_float`); bool-set repr/order differs; `set(map(str,...))`, `set()`+`.add(str)`, shadowed `set` cases fail in both builds; unsorted set printing/iteration order differs in both builds; mixed int/float conditional list fails C compilation in both builds.

**Unverified.** Instruction counts (`tools/icount.c`) — `perf_event_open` returned “Permission denied” on this runner. Profile percentages were not recomputed.

VERDICT: FIX
1. A name first bound to a str-keyed unannotated set and later rebound to an int set-operator result makes the default build emit invalid C (general build and CPython are correct; base succeeds). Probe `/tmp/rprobes/rebind_strset_to_intset_op.py`:
   ```python
   def run() -> None:
       c = set(["x", "y"])
       print(sorted(c))
       a = set([1, 2])
       b = set([2, 3])
       c = a & b
       print(sorted(c))
   run()
   ```
   Expected (CPython, and base default build): `['x', 'y']` then `[2]`. Actual (HEAD default build): compilation fails with `incompatible type for argument 2 of 'ail_tab_put'` (`expected 'int64_t' ... argument is of type 'ail_str'`); the forced typed set result does not account for the destination name’s existing `ail_stab` binding. Same failure with the str binding in a branch (`/tmp/rprobes/rebind_strset_branch_then_op.py`) and with `|`, `-`, `^`; the reverse order (int set then str set operator) is fine.
[cost $0.0804, opencode tokens {"total": 7224272, "input": 153594, "output": 21595, "reasoning": 39035, "cache.write": 0, "cache.read": 7010048}]
    tool time: bash 21.5 min, write 0.0 min
        209s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_sets_general 
        170s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_prog23 test_a
        126s bash   mkdir -p /tmp/rprobes/out; cd /home/runner/work/_temp/w2; ls /tmp/rprobes/*.py | grep -v gen.py | xargs -P2 -I
        125s bash   cd /tmp/rbase23; ls /tmp/rprobes/*.py | grep -v gen.py | xargs -P2 -I{} bash -c 'n=$(basename {} .py); bash ~/
         91s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmphead /tmp/cmpbase && mkdir -p /tmp/cmphead /tmp/cmpbase && for
         77s bash   python3 /tmp/rprobes/gen9.py; cd /home/runner/work/_temp/w2; for n in strset_split strset_literal_list strset_
         63s bash   python3 /tmp/rprobes/gen11.py; cd /home/runner/work/_temp/w2; for n in rebind_strset_to_intset_literal rebind_
         61s bash   python3 /tmp/rprobes/gen4.py; cd /home/runner/work/_temp/w2; for n in set_add_str set_add_bytes set_add_int se

## fix round skipped: only -29 minutes left


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/census/programs/gdev/g02_026.py`
- `lab/census/programs/dev/t102.py`
- `lab/corpus/programs/glm-5.3-flash-free/t069.py`
- `lab/census/programs/gdev/g15_004.py`
- `lab/census/programs/gdev/g25_026.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t115.py`
- `lab/census/programs/gdev/g18_030.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t143.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog23.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog23.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

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
