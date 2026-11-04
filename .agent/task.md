Lane: frontend

# sdkdiag1: the type error in a `.ail` call points at the call again (smoke test is red)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** `AIL_CURRENT/test_ail_sdk.py` passes 31/31 (today 30/31). This failure keeps the `smoke` job
red, and a red smoke job skips all 20 test shards on every PR into integ. So this is a release blocker.

Base: `origin/integ`. PR #376 (hotfix-encoding-1104) fixes a separate break, a PEP 263 comment in
`binary_numbers.py`. If it has not merged yet, cherry-pick its commit first, so that `compileall` runs.

## The failure

`test_relocated_json_source_check_without_c_compiler` (around line 640) checks this source:

```
# 日本語😀
fn take(x:int)->int {return x;}
fn main()->int {return take("wrong");}
```

with `ail_chatgpt.py check <file> --interface`. The test expects the first diagnostic to be:
- at `line 3, column 17`, with `function 'main'` and `location_kind 'source_statement'`;
- with `type_details == {operation:'argument', callee:'take', parameter:'x', parameter_index:0, expected:'int', actual:'str'}`.

Today it reports `line 2, column 1`, `location_kind 'function_declaration'`, with the message
"'x' is annotated int in the source, but the caller also supplies str; refusing rather than silently choosing one."
That is the message from the general (pyfunc) path. The diagnostic now points at the declaration, not at the call,
which is worse for an LLM repair loop. The test was green at d1afe1f8 (PR #359) and red from ec5e1eda (#361) on.
Suspects are the brace-to-Python conversion jobs merged in between, onelangs5b (d43faf32) and onelangs12b (2640361d).
Confirm the culprit with `git bisect` on the single test before changing anything.

## What to do

1. **Bisect (15 min).** Run the single test with
   `python3 test_ail_sdk.py SdkTests.test_relocated_json_source_check_without_c_compiler` and find the first bad commit.
2. **Fix (45 min).** Restore the call-site diagnostic: the right line and column, the right `location_kind`, and the
   `type_details` argument record. Do this whether the `.ail` input is now converted to Python first or not:
   map the location back to the original `.ail` line and column. Do not weaken the test. Do not change the
   expected numbers unless the bisect shows the test itself was wrong, and say so in the PR if it was.
   `AIL_CURRENT/test_ail_argument_type_details.py` covers the same records; it must stay green.
3. **Verify (20 min).**
   - `test_ail_sdk.py` 31/31;
   - `test_ail_argument_type_details.py`;
   - the test modules that the files you touched belong to;
   - `python3 -m compileall -q -j 0 AIL_CURRENT tools`.
   Report each module's pass count before and after.

Files: only the diagnostic or location-mapping code your bisect points at, plus tests. Do not edit `test_ail_sdk.py`
expectations.

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
