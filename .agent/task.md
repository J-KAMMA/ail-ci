Lane: rterrfix

# relrterr4: the uncaught-error "raised near" line must not follow the CPython message in default mode (integ is red)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** failing integ test modules. relrterr3b (commit 67ebae4a, PR #368) broke these eight, which
were green before it merged:
- `test_ail_silent_diffs3`
- `test_ail_ail2py`
- `test_ail_bound_builtin`
- `test_ail_bce`
- `test_ail_cc_split`
- `test_ail_int64_default`
- `test_ail_onelang_twins`
- `test_ail_classnames`

The target is all eight green. A culprit run applied std_re and relrterr3b alone, each on top of cand-1104092750:
std_re passed and relrterr3b failed.

Base: `origin/integ`.

## What broke

An uncaught error in a default-mode build (no `--debug`) now prints a `  raised near <file>:<line>` line after the
exception line. Tests compare the last stderr line with CPython's last line, so they fail. Example from
`test_ail_silent_diffs3`:

```
expected last line: ValueError: __len__() should return >= 0
got last line:        raised near /tmp/ail-diffs3-.../len_typed.py:3
```

relrterr3b's own task said "`--debug`'s raised near line unchanged". The location line was meant for `--debug`, or
at least must not be the last line. Pick one:
- (a) print `raised near` only under `--debug`, which is the old behaviour;
- (b) print it before the exception line, the way CPython puts its traceback above the message.

Choose (b) only if no test in the eight modules expects stderr to be exactly the CPython text. Otherwise choose (a).
Either way, the last stderr line must equal CPython's last line in default mode. Keep relrterr3b's real gain:
exception names that match CPython (`KeyError: 'b'`, `IndexError: list index out of range`).

## What to do

1. **Reproduce (10 min).** Run the eight modules on `origin/integ` and on `67ebae4a^`. Record the pass counts.
2. **Fix (45 min).** The emitter is in `cruntime.py` and `ir/emit_c.py` (look for `AIL_DBG_UNCAUGHT` and
   "raised near"). Check every path: typed, general, the hybrid extension and `c_api_bridge.py`.
3. **Verify (25 min).**
   - the eight modules green;
   - relrterr3b's own tests still green: `test_ail_debug`, `test_ail_debug_flush`, `test_ail_debug_lines`,
     `test_ail_exception_context`, `test_ail_exception_values_core`, `test_ail_list_ops`, `test_ail_build_reports`,
     `test_ail_bigint`;
   - `python3 -m compileall -q -j 0 AIL_CURRENT tools`.
   Report each module's pass count before and after.

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
