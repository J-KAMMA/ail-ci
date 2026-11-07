**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the change really does.** Three commits on `work..HEAD`. They type `split`/`rsplit`/`splitlines` receivers as `str`, give P3 literal/annotation evidence when the RHS is unknown, add time-scoped alias edges (name, container literal, subscript/attribute read, mutation detection) that suppress P1/P4/P6, and add docs/tests/manifest rows. Only `perflint.py`, `docs/CLI.md`, `test_ail_perflint.py`, `DEVLOG.md`, `manifest.d/a7.txt` change; no compiler/runtime code. `cmp.sh` on `r_split.py`: both builds match CPython. HEAD also has `54e756f` (container aliases/rebinding), not mentioned in the report (which says `5665e64`).

**Review defects checked.** All three named defects are fixed:
- `r_split.py`: no P1 (was false P1 on `text`); fixed.
- `r_alias.py`, `r_alias_p1.py`, `w_alias_*`: silent on mutation through a direct/container/attribute alias; `r_alias_rebind_p1/p4`, `r_alias_looptarget`, `r_p6_alias`: behave as reported; fixed.
- `r_p3shape.py`: P3 at lines 4 and 10 for `s=""`/`s: str` + unknown `+=`; fixed.

**Claims.** Census verified exactly (`compare` 0, corpus-50 0, gdev 1 at `g15_022.py:84`, lab/corpus 0, lab/vibe 0). `update_manifest.py --check` passes. Targeted tests 2/2 pass (`test_ail_perflint`, `test_ail_safetynet`). "Suppresses only on actual mutation, not alias rebinding" is **false**: rebinding the alias inside the loop still suppresses (defect 2). The 8-probe `cmp.sh` claim and `test_ail_files`/`test_ail_corpus_findings3` rerun were not repeated.

**Blocking defects (introduced vs `work`).**
1. **Subscript reads are always treated as aliases, so copies and scalar elements suppress valid hits.**
   `v_slice_copy_p4.py`:
   ```python
   def f(items: list[int]) -> int:
       view = items[:]
       total = 0
       for i in range(3):
           view.append(i)
           total += sum(items)
       return total
   ```
   Expected P4 (`items` unchanged; `view` is a copy); actual: no hit (base: P4 at `6:18`). Same for `v_item_copy_p4.py` (`view = items[0]`, `view += 1`; expected P4, actual none; base P4 `6:18`) and `v_slice_copy_p6.py` (expected P6, actual none; base P6 `6:9`). `.copy()`/`list(items)` correctly still report, so only the `Subscript` path is wrong.
2. **Rebinding an alias inside the loop before mutating it still suppresses.**
   `v_rebind_inside_p4.py`:
   ```python
   def f(items: list[int]) -> int:
       view = items
       total = 0
       for i in range(3):
           view = []
           view.append(i)
           total += sum(items)
       return total
   ```
   Expected P4 (`items` never changes; the append touches the rebound list); actual: no hit (base: P4 at `7:18`). Likewise `v_rebind_inside_p6.py` (expected P6, actual none; base P6 `7:9`), contradicting the report's "not alias rebinding" claim.

**Pre-existing (identical on `work`; listed, not blocking).** The same aliasing class still gives wrong advice for untracked aliases: tuple unpacking (`v_tuple_unpack.py`, `v_tuple_unpack_p1.py`), `d.get` (`v_dict_get.py`), conditional (`v_ifexp.py`), loop-target capture (`v_loop_target_alias.py`), and in-loop alias creation (`v_inloop_alias_p1.py`). Applying the reported fix changes output (e.g. `13`→`9`, `found`→nothing, `0 1 2`→`1 2`). These reproduce identically on `work`.

**Unverified.** Wall-clock/`measure.py` numbers; `test_ail_files`, `test_ail_corpus_findings3`; the worker's exact 8 `cmp.sh` probes.

VERDICT: FIX
1. `v_slice_copy_p4.py` / `v_item_copy_p4.py` / `v_slice_copy_p6.py` — expected P4/P4/P6 (base reports them); actual no hit. `_edge_names` treats any `Subscript` value as an alias, so `items[:]` (a copy) and `items[0]` (an element) suppress hits on the unchanged list.
2. `v_rebind_inside_p4.py` / `v_rebind_inside_p6.py` — expected P4/P6 (base reports them); actual no hit. An alias rebound inside the loop is still assumed to alias the list, so mutating the rebound name suppresses a valid hit, contrary to the report.
[cost $0.0000, opencode tokens {"total": 937775, "input": 68517, "output": 6132, "reasoning": 26262, "cache.write": 0, "cache.read": 836864}]
    tool time: bash 1.4 min
         80s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_perflint test_ail_safetynet 2>&1 | tail -20
          1s bash   date; bash ~/tools/cmp.sh /tmp/rprobes/r_split.py $PWD 2>&1 | tail -8
          1s bash   date; python3 lab/algo/census.py 2>&1 | grep -E '^###|^\| [0-9]|^- `' | head -40
          0s bash   python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "manifest exit $?"
          0s bash   cd /tmp/rprobes cat > v_tuple_unpack_fixed.py <<'EOF' def f(items: list[int]) -> int:     view, n = items, 0  
          0s bash   cd /tmp/rprobes cat > v_inloop_alias_p1.py <<'EOF' def f(items: list[int]):     for i in range(3):         vie
          0s bash   date; pwd; git log --oneline work..HEAD; echo ---; git status --short
          0s bash   cd /tmp/rprobes cat > v_slice_copy_p4.py <<'EOF' def f(items: list[int]) -> int:     view = items[:]     total


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
