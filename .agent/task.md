**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
I have enough. Final verification of the remaining claims is done; here is my review.

**What the change really does.** Adds a new AST linter `packaging/ail_lang/perflint.py` (six rules P1–P6 over loop bodies, text/JSON output, `--strict` exit 5), wires `ail check --perf` into `packaging/ail_lang/cli.py`, and adds docs, tests/registration, manifest rows, and `lab/algo/` census+measure scripts. No compiler or runtime code is touched: `program.c` from `--debug-dir` is byte-identical between `work` and HEAD (only transient temp/cwd paths in `native_report.json` differ), and `cmp.sh` on a plain program matches CPython on both builds.

**Claims.** Census re-ran and matches exactly (compare 0/10, required 50 0/50, gdev 1/510 at `g15_022.py:84`, lab/corpus 219→0, vibe 24→0). `measure.py --runs 1` reproduces the table (all six "output identical", every after-hit `-`). Targeted tests on HEAD: `test_ail_perflint`, `test_ail_cli_args`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 pass, 0 failed. P3/P6 reset and P4 key behaviour verified by probes (`p3_reset`, `p6_reset`, `p6_loopvar`, `p4_keyvar` silent; sibling `+=` and constant keys still report). Error path verified (syntax/NUL source → exit 2, no hits).

**Defects.**

1. **`.split()` types its receiver as a list — false P1 on a string, and the published fix changes output.** `_collect_call` does `elif func.attr in LIST_METHODS: self._hint(name, "list")`, but `split` is a *str* method; the receiver is a str. Probe `/tmp/rprobes/r_split.py`:
```python
def scan(text):
    for _ in range(3):
        fields = text.split(",")
        if "b,c" in text:
            print("yes", fields)
scan("a,b,c")
```
Actual: `r_split.py:4:12: perf P1: membership test on the list 'text' ... fix: build a set/dict once ...`. Expected: nothing (`text` is a str). Applying the JSON `fix` (`in set(text)`) changes the program from 3 `yes` lines to none (verified). This is the "value through an argument / types" boundary the docs say is handled.

2. **Aliasing is not treated as loop mutation; P1/P4 advice changes output.** `for i in range(3): data.append(i); total += sum(xs)` with `data = xs` reports P4 on `sum(xs)`; hoisting takes the result from 7 to 3 (`/tmp/rprobes/r_alias.py`). Likewise `view = items; view.append(probe); if probe in items` reports P1 and the set-before-loop fix takes output from `1 2` to nothing. Expected: silent, since the named list is mutated (docs: "a name that is rebound or mutated in the loop ... not reported").

3. **P3 misses the annotated/literal string target when the RHS type is unknown (dead branch).** In `_augment_kind`, `current = self.kinds.get(name)` is always `None` because `_classify` returns early when the name is in `self.kinds`; so `s: str` / `s = ""` + `s += <unknown>` is discarded as "other". Probe `/tmp/rprobes/r_p3shape.py`: `def f(items): s = ""; for x in items: s += x` and `def k(items): s = "start"; ...` produce **no hit**, while `def h(items: list[str])` reports at line 18. Expected: P3 (the target is provably a string, so any `+=` that runs is a string concat; docs promise annotation/literal evidence). This is a false negative, not wrong advice.

**Pre-existing.** None: `perflint.py` and the `--perf` branch are new in this change; no compile-time difference exists on the base.

**Unverified.** The worker's `/tmp/probes` claim (17 compile probes) — not rerun; immaterial since no compiler code changed and my own `--debug-dir` diff is identical. Wall-clock numbers in `RESULTS.md` are environment-dependent (I reran only `--runs 1`, output equality confirmed).

VERDICT: FIX

1. Probe /tmp/rprobes/r_split.py — expected: no hit (text is a str); actual: `4:12: perf P1: membership test on the list 'text'`; applying the fix changes output from three `yes` lines to none.
2. Probes /tmp/rprobes/r_alias.py (and r_alias_p1_orig/fixed) — expected: no P4/P1 hit when the list is mutated through an alias; actual: hits whose fixes change output (7→3, `1 2`→empty).
3. Probe /tmp/rprobes/r_p3shape.py — expected: P3 for `s = ""`/`s: str` + `s += unknown`; actual: no hit (only the `list[str]` case at line 18 reports).
[commandcode stop=end_turn turns=35 out_tokens=45550]


--- ORIGINAL TASK ---
Lane: cli

# algo1: `ail check --perf`: find the slow algorithms AI-written code tends to contain, and give the fix

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).

**Why (owner, 2026-11-07):** AIL is for vibe coding. The biggest speed loss in AI-written programs is the wrong
algorithm (quadratic where linear is easy), far larger than any gap to the hardware limit. A loud, fixable report
beats a faster runtime.

**Number this moves:** in `lab/algo/RESULTS.md`, over the 10 `lab/compare/src/*/main.py` programs, the 50 corpus
programs rundiff1 uses (or any 50 from lab/corpus) and any `lab/vibe` outputs present: hits per rule, false positives
(checked by hand on each hit, say so), and for every hit where the suggested fix was applied: output identical
(byte-compare on the program's public cases) and wall time before/after at a size where it matters.

## Rules (first version; static, on the Python AST, no type inference needed beyond the obvious)
| id | pattern inside a loop over n items | fix text |
|---|---|---|
| P1 | `x in L` / `L.index(x)` / `L.count(x)` where `L` is a list | build a `set`/`dict` once before the loop |
| P2 | `L.pop(0)` / `L.insert(0, x)` / `del L[0]` | `collections.deque` |
| P3 | `s += str` building a string | collect in a list, `''.join` once |
| P4 | `sorted(...)`/`L.sort()`/`min(L)`/`max(L)`/`sum(L)` of an unchanged list inside the loop | hoist out of the loop |
| P5 | nested loops comparing every pair to find matches by key | group by key in a dict |
| P6 | `L = L + [x]` or `L = [*L, x]` | `L.append(x)` |

Each report is one line on stderr `file:line:col: perf P1: <message>; fix: <fix text>` and, with `--json`, one object
per hit `{"rule","file","line","col","message","fix","loop_line"}` so an agent can apply it. Exit code 0 always
(advice, not an error); `--strict` makes hits exit 5. Document in `docs/CLI.md` under its own heading.

Base: `origin/integ`. Files you may create or edit, and no others:
- `packaging/ail_lang/perflint.py` (new), `packaging/ail_lang/cli.py` (add the `check --perf` entry only; if `check`
  does not exist, add `ail check --perf` as a new subcommand without changing others);
- `docs/CLI.md`;
- `AIL_CURRENT/test_ail_perflint.py` (new) and its registration the way other test modules are registered;
- `lab/algo/*` (new).

## Tests
One positive and one negative case per rule (negative: the same call outside a loop, on a set, on a loop-variant list);
`--json` shape; `--strict` exit code; a program with no hits prints nothing.

## Sub-steps
1. (50 min) perflint.py + CLI + docs. Commit, push.
2. (30 min) Tests, register, run them and the existing CLI test modules. Commit, push, wait for CI.
3. (40 min) lab/algo census and before/after table. Commit, push.

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
