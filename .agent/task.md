**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**Change (one line).** `3cf0d72`+`b9ccb5e` add base16/base32/`encodebytes`/`decodebytes` and `altchars=`/runtime `validate=` lowering to `hashlower.py`, implement them plus a `ValueError`-subclass `Error` in `hash_prelude.py`, add 12 lab programs and `test_ail_std_base64`; this is broader than the report's "fixed five defects", but consistent with the two commits.

**Probes (both builds, `bash ~/tools/cmp.sh ... $PWD`).**
- `r_alt.py`, `r_altstr.py`, `r_alt2.py` (altchars lengths 0/1/2/3/4, bytes/str/bytearray, constant/dynamic, decode+encode): match, incl. `AssertionError: b'?'` / `"'-'"` and dynamic-str encode `TypeError`.
- `r_b32.py`, `r_b32b.py` (enc 0–11, 30 padded/unpadded/bad-padding/lowercase/invalid tokens × casefold, bytearray): match.
- `r_b64alt.py` (7 altchars incl. `++`, `//`, NUL; validate true/false with whitespace): match.
- `r_bytes.py` (encodebytes lengths 0,1,2,55,56,57,58,113,114,115; multi-line decode; bytearray; str errors): match.
- `r_routes.py`, `r_types2.py`, `r_kw.py`, `r_badtypes.py`, `r_b16.py`: two mismatches below.
- Compare tasks: generated C byte-identical on HEAD/base for the 5 that build plainly; the other 5 refuse identically on both.

**Tests.** `test_ail_std_base64`, `test_ail_crypto`, `test_ail_safetynet` on HEAD: 3 modules, 0 failed, 421s. `update_manifest.py --check`: exit 0.

**Claims.** altchars assert (both decode paths, constant str) — verified. Dynamic-str encode TypeError — verified. `decodebytes` str/non-bytes TypeError text — verified. `b32decode(bytearray)` — verified. Encoder TypeError texts (str/int) — verified. `update_manifest --check` — verified. Their 19 `rprobes` + 5 `fix_*` rerun, `test_ail_files`, `test_ail_corpus_findings3`, and “chunked_stream is general” — unverified (not rerun/inspected). Speed — not checked (no hot-path change).

**Pre-existing.** None found; both defects are in code added by this change.

**Defects.**
1. `base64.b16decode` skips its input type check for non-bytes/non-str (`/tmp/rprobes/r_b16.py`, `r_badtypes.py`, both builds). `base64.b16decode(123)` expected `te argument should be a bytes-like object or ASCII string, not 'int'`; actual `te object of type 'int' has no len()`. Same for `None`. Cause: `_ail_hl_b16d_dyn` omits `_ail_hl_need_bytes(data, 3)` that `_ail_hl_b32d_dyn` has.
2. `base64.b64encode(b"\xfb\xff", altchars=[1, 2])` silently returns `b'\x01\x028='` (`/tmp/rprobes/r_badtypes.py`, both builds). CPython expected `te a bytes-like object is required, not 'list'` (assert passes, then `bytes.maketrans` rejects the list). Cause: `_ail_hl_alt_bytes`/`_ail_hl_alt_enc_dyn` check only length, never that altchars is bytes-like, so an invalid altchars is used as character codes.

VERDICT: FIX
1. Add the bytes-like check to `_ail_hl_b16d_dyn` (probe `/tmp/rprobes/r_b16.py`, `base64.b16decode(123)` expected `argument should be a bytes-like object or ASCII string, not 'int'`, actual `object of type 'int' has no len()`).
2. Reject non-bytes-like `altchars` after the length assert (probe `/tmp/rprobes/r_badtypes.py`, `base64.b64encode(b"\xfb\xff", altchars=[1, 2])` expected `TypeError: a bytes-like object is required, not 'list'`, actual `b'\x01\x028='`).
[cost $0.0346, opencode tokens {"total": 2334414, "input": 39566, "output": 9073, "reasoning": 27343, "cache.write": 0, "cache.read": 2258432}]
    tool time: bash 18.8 min, write 0.0 min, edit 0.0 min
        441s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpgc && mkdir -p /tmp/cmpgc/src /tmp/cmpgc/head /tmp/cmpgc/base 
        240s bash   sleep 240; ps -p $(cat /tmp/rev_par.pid) -o pid,etime; wc -l /tmp/rev_par.log; tail -20 /tmp/rev_par.log; date
        175s bash   cd /tmp/rprobes && for p in r_alt r_altstr r_b16 r_b32 r_bytes r_routes; do echo "##### $p"; timeout 300 bash 
         82s bash   cd /tmp/rprobes && for p in r_alt r_b16 r_routes; do echo "##### $p"; timeout 300 bash ~/tools/cmp.sh /tmp/rpr
         53s bash   cd /tmp/rprobes && for p in r_b32b r_b64alt; do echo "##### $p"; timeout 400 bash ~/tools/cmp.sh /tmp/rprobes/
         40s bash   cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/r_types2.py /home/runner/work/_temp/w2 2>&1 | 
         36s bash   cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/r_alt2.py /home/runner/work/_temp/w2 2>&1 | gr
         35s bash   cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/r_badtypes.py /home/runner/work/_temp/w2 2>&1 


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `base64` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `base64` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/base64/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/base64/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_base64.py registered in tests.d), and compare them with CPython in the test.
- Run that test plus test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

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
