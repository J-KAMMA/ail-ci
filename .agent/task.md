**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does.** Fixes the five review-1 `struct` defects: default/unprefixed float mode is now native, `_ail_struct_scale`'s negative branch loops over the full exponent, `pack_into` checks item count before offset and says `pack_into expected …`, `p` names itself in its wrong-type error, and non-`bytearray` buffers get CPython's read-write-buffer text. Adds three edge programs, DEVLOG/DIFFERENCES rows and refreshes the manifest. This matches the report, except the buffer guard is broader than "non-writable buffers" (below).

**Defect (caused by this change)**

1. `pack_into` now rejects writable `array.array` buffers. The new guard `isinstance(buffer, bytearray)` at `AIL_CURRENT/python/pkg-v12/prelude_struct.py:778` (module) and `:851` (`Struct.pack_into`) rejects `array.array`, which CPython accepts and which the base `work` accepted.
   Probe `/tmp/rprobes/q9_arr.py`:
   ```python
   import array, struct
   a = array.array('B', [0, 0, 0, 0])
   struct.pack_into('<i', a, 0, 7); print(list(a))
   # same via Struct.pack_into, argument, attribute, list item, dict value
   ```
   Expected (CPython and base): `[7, 0, 0, 0]` for every route.
   Actual (HEAD, both `g` and `d`): `TypeError argument must be read-write bytes-like object, not _AilArray`.
   The test's `pack_into_buffer_type` edge program does not include `array.array`, so it missed this.

**Verified**
- Default float: `q1_fmt`, `q7_float` match CPython on `g` and `d` for `'f'`, `' f'`, `'2f'`, `'10f'`, `@/=/</>/!` and `Struct`; only the declared NaN-payload rows differ.
- Subnormal: `q4_sub` matches for subnormal/normal/boundary doubles, f32 and f16; only the declared NaN-payload rows differ.
- Errors: `q5_errs` matches `pack_into expected …`, `p`/`s` wrong-type text, and count-before-offset; only the declared `0p` `SystemError`→`struct.error` row differs.
- Precedence and buffer names: `q6_prec` matches bad-format > count > buffer-type > offset, and names `None`/`Foo`/`type`/builtins/`bytes` correctly.
- `calcsize` boundary: `q2_size` matches CPython at the int64 boundary and for 20-digit counts.
- Non-struct C: `g_nostruct` `--debug-dir` `program.c` is byte-identical to `/tmp/base`.
- Tests on HEAD: `test_ail_std_struct` + `test_ail_safetynet` 2/2 pass (545 s); `update_manifest.py --check` exit 0.
- Worker probes `n_rwtype`, `n_review`, `c_packinto`, `j_buffer_routes`, `a_native`, `d_calcsize` match on both builds; `i_declared` differs only on the declared rows.

**Pre-existing (same on base)**
- `memoryview` + `struct` does not compile (type-inference refusal) on base and HEAD.
- `struct.unpack`/`unpack_from`/`Struct.unpack` reject `array.array` on base and HEAD (`q11_unpackarr`).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (worker claims pass), exhaustive subnormal sweep beyond the tested boundaries.

VERDICT: FIX

1. `pack_into` rejects `array.array`: accept `_AilArray` (or any AIL writable buffer) in both `_ail_struct_pack_into_values` and `_AilStruct.pack_into`, while still naming `bytes`/other non-writable types like CPython. Probe `/tmp/rprobes/q9_arr.py`, expected `[7, 0, 0, 0]` per route, actual `TypeError … not _AilArray`.
[cost $0.0000, opencode tokens {"total": 2159944, "input": 96994, "output": 10129, "reasoning": 18517, "cache.write": 0, "cache.read": 2034304}]
    tool time: bash 21.7 min
        547s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 --timeout 2400 test_a
        164s bash   date; cd /tmp/rprobes && for p in n_rwtype n_review c_packinto j_buffer_routes a_native d_calcsize i_declared;
         71s bash   cd /tmp/rprobes && cat > q11_unpackarr.py <<'EOF' import array import struct a = array.array('B', [7, 0, 0, 0]
         69s bash   cd /tmp/rprobes && cat > q9_arr.py <<'EOF' import array import struct  def via(b):     return b  class Box:   
         62s bash   cd /tmp/rprobes && echo "=== i_declared diff"; cat /tmp/cmp*/diff_g.txt 2>/dev/null | tail -0; ls -td /tmp/cmp
         39s bash   date; cd /tmp/rprobes && bash ~/tools/cmp.sh q4_sub.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -40
         35s bash   date; cd /tmp/rprobes && bash ~/tools/cmp.sh q5_errs.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -40
         34s bash   cd /tmp/rprobes && cat > q7_float.py <<'EOF' import struct vals = [1e40,1e308,float('inf'),float('-inf'),float


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `struct` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `struct` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/struct/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/struct/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_struct.py registered in tests.d), and compare them with CPython in the test.
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
