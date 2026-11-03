**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
**Change.** Converts `LANGUAGE_QUICKSTART_JA.md` fences/prose to Python syntax, adds `test_ail_reference_docs.py`, and inlines helpers from brace modules into eight examples.

**Claims checked**
- Prose brace spellings removed: **mostly verified**, but false for the contract paragraph (`:182`, `:196-197` still teaches brace-only rules).
- 35/38 whole programs compile: **verified**; 3 skips are `make`, `number_batch`, `byte_search_core`.
- Those 3 are pre-existing refusals: **false for `byte_search_core`** (base brace block builds/runs; HEAD Python block refuses).
- “Test compiles every quickstart whole program”: **false**; it `skipTest`s the three refusals, hiding the new one.
- Probe outputs (`3\n7`, `01 02`, `AIL\x01\x02`, `日本語||😀`): **verified** by running the standalone examples.
- Manifest/`git diff --check`: **verified**.
- “6 modules, 0 failed”: **false on this runner**; `test_ail_safetynet` fails `S4_generators_gc`, but identically on `/tmp/base`, so pre-existing.
- `test_ail_reference_docs`, `test_ail_quickstart_docs`, `test_ail_reference_examples`: **verified pass**.

**Pre-existing**
- `test_ail_safetynet` `S4_generators_gc`: general path prints only `5530537`, CPython prints 6 lines. Same on base.
- `make` and `number_batch` examples refuse on base too.

**Unverified.** Full 20 shards, `test_ail_files`, `test_ail_corpus_findings3`, base 33/37 count, speed (docs-only).

VERDICT: FIX

1. `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md:7276` — the converted `byte_search_core` whole program no longer builds. It now uses `from byte_search_core import *`, but `language_examples/byte_search_core.ail` is still brace syntax.
   Probe (doc block, built with `--syntax python --object byte_native.o`):
   ```python
   from byte_search_core import *
   from ail import read_bytes
   import sys
   def main() -> int:
       if len(sys.argv) != 2: return 2
       data = read_bytes(sys.argv[1])
       print(find_byte(data, 0, 0, len(data)))
       return 0
   if __name__ == "__main__": sys.exit(main())
   ```
   Expected: builds and runs (the base brace block with `use byte_search_core;` builds and prints `-1`, exit 0). Actual: `module 'byte_search_core' is byte_search_core.ail, which is written in the brace syntax`. The new test hides this with `skipTest`.

2. `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md:391-414` — inlining `environment_config` changed `env_int` from `parse_int64_text` to `int`, so out-of-int64 input no longer raises `ValueError` as the text says.
   Probe:
   ```python
   def env_int(name: str, default: int) -> int:
       return int(get_env(name, str(default)))
   def main() -> int:
       print(env_int('AIL_CONFIG_COUNT', 1)); return 0
   ```
   Run with `AIL_CONFIG_COUNT=9223372036854775808`.
   Expected: `ValueError` (base brace block using `environment_config` prints `ValueError`). Actual: `OverflowError: integer overflow in int() ...`, exit 1. The example is `# run: no`, so the test only compiles it.

3. `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md:182,196-197` — the rewritten contract section still teaches brace-only rules that are false for the `assert` form it now recommends. It says a contract assert is not caught by `try`, must be the first statement, and that `_ail_result` always names the return value.
   Probe:
   ```python
   def f(n: int) -> int:
       assert n >= 0, 'requires failed in f: n >= 0'
       return n
   def main() -> int:
       try:
           print(f(-1))
       except AssertionError as e:
           print('caught', e)
       return 0
   ```
   Expected per text: not caught, exit 1 with `requires failed...`. Actual: prints `caught requires failed in f: n >= 0`, exit 0. Likewise an `assert` in the middle or inside an `if` compiles and runs, contrary to the compile-time-refusal sentence.
[cost $0.0000, opencode tokens {"total": 2995535, "input": 87733, "output": 10173, "reasoning": 24925, "cache.write": 0, "cache.read": 2872704}]
    tool time: bash 4.4 min
         98s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 900 python3 ../tools/par_check.py
         96s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 900 python3 -B test_ail_safetynet
         48s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 1700 python3 ../tools/par_check.p
          7s bash   cd /home/runner/work/ail-ci/ail-ci && sed -i "s|HERE=pathlib.Path('AIL_CURRENT')|HERE=pathlib.Path('AIL_CURREN
          3s bash   cat > /tmp/rprobes/one_s4.py <<'PY' import sys, unittest sys.path.insert(0, '.') import test_ail_safetynet as 
          2s bash   mkdir -p /tmp/rprobes/pre && cd /tmp/rprobes/pre && printf 'fn main() -> int {\n    let a = make(0, 0, 3, 4);\
          1s bash   mkdir -p /tmp/rprobes/envorig && cd /tmp/rprobes/envorig && AIL_PATH=/tmp/base/AIL_CURRENT/language_examples p
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import re,pathlib t=pathlib.Path('AIL_CURRENT/LANGUAGE_


--- ORIGINAL TASK ---
Lane: oldocs

**Owner decisions (2026-11-03):** AIL is one language, Python syntax plus optional annotations. The compare-lab `ail` column may use the converted annotated `typed.py` when its C is identical, and the plain `main.py` stays as its own row. The brace front end is removed before the 0.1 tag. AIL-only built-ins are spelled `from ail import ...`.

# onelang s13: `LANGUAGE_QUICKSTART_JA.md` in Python syntax

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md` (7,322 lines, 186 brace lines) has no brace code; its
whole-program blocks build and print what the text says. Japanese prose is kept; only sentences that teach brace-only
rules are rewritten (in Japanese, same tone) or removed.

Base: `origin/integ` after onelang s12 merged (uses `tools/ail2py_docs.py` and `test_ail_reference_docs.py` from s12).

## Sub-steps

1. Run `tools/ail2py_docs.py` on the file; review the listed blocks by hand. Commit, push, open the PR.
2. Prose: search for `let`, `fn `, `struct`, `impl`, `;`, `{`, `波括弧`, `セミコロン`, `ブロック構文`; rewrite each such
   rule for Python syntax or delete it. Commit and push after each 1,500 lines of the file.
3. Add the file to `test_ail_reference_docs.py`. If `test_ail_quickstart_docs.py` reads this file, run it too. Commit,
   push.

## Done-check

`grep -cE "^\s*(fn |let |struct |impl )" AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md` is 0; `test_ail_reference_docs` and
`test_ail_quickstart_docs` pass; all 20 shards pass.

## Stop rule

Stop at 80 minutes with what is green pushed (the file is long: a half-converted file is acceptable if the doc test
passes on the converted part and the PR says which line it reached); a compiler change outside the files named here would be needed; any compare-lab `program.c` changes; any listed test module fails for a reason the base did not have; or 80 minutes pass. Push what is green and report. Do not touch `.github/workflows`.

## Appendix A: standing rules

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `--check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, or edit
   `.github/workflows`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--syntax python] [--strict] [--debug-dir DIR]`;
  `DIR/program.c` is the generated C; `--strict` = typed path or refuse. `-o` must not exist yet.
- Brace front end: `AIL_CURRENT/ail_syntax.py` `detect()` (about line 206) and `translate()` (about line 285), which
  turns brace text into annotated Python text (`-> R` becomes `-> __ail_checked_R__`). `python_surface()` (about line
  4101) maps Python spellings onto the compiler's built-ins. The per-file loader is `load()` in
  `AIL_CURRENT/ail_chatgpt.py` (about lines 4908-5190; `syntax == 'ail'` branches there are brace-only checks).
- `use m` resolves `AIL_CURRENT/language_examples/m.ail` (`standard = ROOT / 'language_examples'`, about line 4897 of
  ail_chatgpt.py). Python `from m import *` is merged by `AIL_CURRENT/ail_modules.py` `merge_program`, which renames
  `m.f` to `m__f` in the C.
- The converter (onelang s1-s3): `python3 tools/ail2py.py SRC.ail [-o OUT.py] [--check [--flags "..."]]`; `--check`
  prints `identical` / `identical-renamed` / `differ ...` / `py-refused ...` / `both-fail`.
- compare-lab: `lab/compare/src/<task>/main.ail` (brace) and `main.py` (plain CPython program; the pyreach line works on
  these); `lab/compare/run_task.py` (`LANGS`, `SOURCE` map about line 33, `build_cmd` about line 58,
  `EXACT_INT_TASKS = ('rail_transfer', 'chain_relax')`, cold builds with a fresh `AIL_CACHE`, `compile_s` = median).
  Tasks: berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit tree_fold.
- Census of 2026-11-03 (integ f6d5825c): 391 tracked `.ail` (268 `AIL_CURRENT/language_examples`, of which 262 brace and
  137 entry programs; 10 compare-lab; 109 `lab/syntax/runs` experiment records; 4 `lab/flags/programs`, Python text);
  147 test modules embed brace sources (699 `fn main(`), 37 test modules read `language_examples/`, 46 hash
  `pyfunc.to_c(...)` codegen pins.

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
