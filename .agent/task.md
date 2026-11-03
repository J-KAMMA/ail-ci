Lane: frontend

**Finish onelangs3 from its existing work; do not redo it.** The first run (branch `job-onelangs3-11031207`) finished the implementation, then its review hung for 60 minutes with no output, which looks like a model limit, so it got no verdict. Start by cherry-picking that branch's work commit (the commit "job onelangs3: converter meaning rules and corpus baseline"):

```
git fetch origin job-onelangs3-11031207
git log --oneline origin/job-onelangs3-11031207
git cherry-pick (the commit "job onelangs3: converter meaning rules and corpus baseline")
```

Then verify it against the original task below: re-run its measurements and its tests, check the boundary cases, and fix anything that is wrong. Report the numbers again. Time budget: 60 minutes.


**Owner decisions (2026-11-03):** AIL is one language, Python syntax plus optional annotations. The compare-lab `ail` column may use the converted annotated `typed.py` when its C is identical, and the plain `main.py` stays as its own row. The brace front end is removed before the 0.1 tag. AIL-only built-ins are spelled `from ail import ...`.

# onelang s3: converter meaning rules (R1 bool results, R2 stored containers) and the corpus check

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** over the 137 entry programs of `AIL_CURRENT/language_examples` (built as written, no extra
flags), the converted files today give: 14 byte-identical C, 22 identical after undoing module renames, 14 small
differences, 8 that fall to the general path, 9 refused, 70 that need extra build inputs. Target: 0 refused and 0
general-path falls among the 67 buildable entries; every buildable entry `identical` or `identical-renamed`, or listed
with its C diff and equal output on its inputs.

Base: `origin/integ` after onelang s2 merged.

## Sub-steps

1. **`identical-renamed`** in `tools/ail2py.py --check`: when the C differs, undo `merge_program`'s module renames in
   the converted C (every `<m>__` prefix for each module `m` of the `use` closure, also inside longer identifiers such
   as `ail_obj_<m>__S`, `ail_unwind_<m>__f`, `v_<m>__X`), sort the top-level declaration lines of both files if order
   is all that differs, and compare again. Print `identical-renamed` on equality. Commit, push.
2. **Corpus script** `tools/ail2py_corpus.py`: copies `language_examples` to two temp dirs, converts every brace `.ail`
   in the second (modules too), builds each entry both ways with `-j 2` (threads), writes a JSON report
   (`stem, result, first differing C line, last stderr line`) and prints the counts. Commit, push.
3. **R1**: brace `-> int` returning a bool. In a function whose brace result is `int`, wrap each `return E` in
   `int(E)` when `E` is a `Compare`, a `BoolOp` whose operands are all such, a `not` expression, `True`/`False`, or a
   call of a function declared `-> bool`. The compiler's own hint for these files says exactly this (`write instead:
   int(c == ' ' or ...)`). Check the six refused json/tcp/record entries and the `*_in_range` general-path entries
   (binary_cursor_main, binary_fields_main, binary_replace_main, binary_search_main, record_policy_example) become
   `identical`/`identical-renamed`. Commit, push.
4. **R2**: a container stored in a second place. Cases: csv_float_group_main, csv_stream_main, csv_table_main
   (`result.append(csv_stream.CsvRow(row, fields))` then `fields` changes), binary_buffer_example
   (`shared = packet.data`), collection_state_example (`saved = named_counters.named_counters_snapshot(counts)`),
   handle_list_main (`values: list[bytearray] = [buffer]`). For each, read the brace build's C to see whether it
   copies, moves or shares. Where it copies, the converter writes `.copy()` (lists, dicts, sets; `bytes(x)` stays as is)
   at that argument; where it shares, leave the source alone and list the entry (the Python path is then the correct
   CPython meaning; compare the outputs of both binaries on the entry's inputs from its test module and record them).
   Only write `.copy()` from a rule that names the brace construct (struct constructor argument, `let a = b` of a
   container local, list literal of a container local); never per file. Commit, push.
5. Report: run the corpus script, commit `tools/ail2py_corpus_baseline.json` (the report), push.

## Done-check

`python3 -B tools/ail2py_corpus.py` prints, for the 67 buildable entries: `py-refused 0`, no entry whose converted build
says `built on the general path` while the `.ail` build is typed, and every other entry `identical` or
`identical-renamed` or listed in the JSON with equal outputs. compare-lab ten still `identical`. `tools/par_check.py -j 2
test_ail_ail2py` passes; all 20 shards pass.

## Stop rule

Stop if: an R2 case shows the brace typed path silently differs from what its own test expects (report it; it is a
brace bug, not a converter job); R1/R2 need a compiler change; a compiler change outside the files named here would be needed; any compare-lab `program.c` changes; any listed test module fails for a reason the base did not have; or 80 minutes pass. Push what is green and report. Do not touch `.github/workflows`.

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

## Appendix C: measured probe (2026-11-03)

Small C differences seen were renames: `int64_t checksum(...)` vs `int64_t codepoint_checksum_core__checksum(...)`,
`v_ERROR_PREFIX` vs `v_filter_rules__ERROR_PREFIX`, `ail_obj_Rectangle` vs a renamed struct, declaration order in
config_batch / integer_quantiles (4-line diffs). Refusal texts seen:
`not in the subset: the result of record_report._report_positive() is declared int, but row.value > 0 is a bool
(Python would keep the bool and print True / False)` and `line 176: result.append(csv_stream.CsvRow(row, fields))
makes a second reference to the same container ... write instead: store fields.copy()`.

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
