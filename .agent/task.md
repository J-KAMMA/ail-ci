**`chr()` of a non-BMP code point on the general path: a named refusal/limit instead of an internal error.**

Background: an old job (`pre20`, accepted but its diff no longer applies) found that in an untyped (general-path) program `chr(0x1F600)` ends with `AIL internal error: chr() non-BMP code point requires 32-bit strings` (still in integ `cruntime.py` near line 19016, pinned by `test_ail_pre36.py`). The general runtime stores UTF-16 code units, so a code point above U+FFFF cannot be represented. The typed/default path represents these characters and already matches CPython; do not change it.

Reproducer (compare with CPython 3.12 on both builds; reach the value directly, through an argument, a list item, an attribute and a dict value):

```python
print(chr(0x1F600))            # literal argument
n = int(input()) if False else 0x1F600
print(len(chr(n)))             # value only known at run time
print(chr(0xFFFF) == "￿") # BMP boundary must keep working
```

Fix: a literal non-BMP argument is refused at build time by name (`chr() of the non-BMP code point U+1F600 ...`), and a value only known at run time stops with a named `AIL limit: chr_non_bmp` instead of an internal error. U+FFFF stays accepted and chr()'s ValueError range errors are unchanged. Update `test_ail_pre36.py` for the new wording. First re-check today's integ: if the general path now handles non-BMP characters correctly, change nothing and say so. If the refusal text should use an existing limit helper, follow the style of the pre267 non-BMP `bytes.decode()` refusal already on integ.

Start from today's integ, read `git log --oneline -40` first, and do not reuse the old diff (old branch: `out/ci/pre20.branch` in the agents folder, reference only).

Add a CPython-compared test module `AIL_CURRENT/test_ail_repre20.py` registered in `ail_check.py` MODULES, run `python3 tools/update_manifest.py`, then only that module, the modules of the files you touched, and `test_ail_safetynet`. Commit.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Run `python3 tools/update_manifest.py`, then `--check`.
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
