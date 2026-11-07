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
