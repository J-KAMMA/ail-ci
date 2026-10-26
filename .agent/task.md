# bigint-fix15: attribute errors on instances name the class as 'type' ("'type' object has no attribute 'zz'") (C)

After the bigint commits "store class attributes on the class object" / "fall back to class attributes in by-name
lookups" (c079267, b13dd0d), a missing attribute on an INSTANCE reports the class-object message. CPython says
`'K' object has no attribute 'zz'`. The same confusion makes a raised `OSError(n, text)` instance in user code fail with
`AttributeError: 'type' object has no attribute 'errno'`.

## Modules
- test_ail_nonecrash (test_instance_message) -- exists only in the merge tree (/home/bluec/code/ail-wt/bigint-merge); the
  reproducer below fails on `bigint` too.
- test_ail_excfix (test_oserror_with_errno_general_is_refused_by_name): expects the general-only build of
  `raise OSError(n, text)` in a user function (USER_OSERROR in that test) to be refused by name. It now BUILDS
  (`gonly` returns 0) and then dies at run time with `'type' object has no attribute 'errno'`. Fix the bug first; then
  if the program now runs and matches CPython (printing `PermissionError 1 text 1 [Errno 1] text 1` ...), the refusal test
  is outdated (A: change it to compare with CPython), otherwise keep the refusal.

## Reproducer
`oe3.py`:
```
class K:
    pass

def ident(x):
    return x

try:
    ident(K()).zz
except AttributeError as e:
    print(e)
```
CPython: `'K' object has no attribute 'zz'`. AIL (default / general): `'type' object has no attribute 'zz'`.
Also check `K.zz` (class access: CPython says `type object 'K' has no attribute 'zz'`), a bound-method miss, `del obj.zz`,
`setattr`/`getattr(obj, "zz")`/`hasattr`, and an exception instance (`e.errno` on OSError subclasses).

## Category
C. Fixed means: message equals CPython for instance and class misses; the two modules pass (test_ail_excfix per the note above).

run the listed modules and test_ail_bigint test_ail_tint test_ail_unified before committing. For test_ail_nonecrash, re-run it in the merge tree after the integrator merges.

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
