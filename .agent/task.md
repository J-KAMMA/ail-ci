**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does.** Adds a new `struct` implementation (`python/pkg-v12/prelude_struct.py` + `structlib.py`) wired into the batch-5 stdlib rewriter, 12 lab programs and a test; the second commit changes five prelude behaviours and declares two differences. This matches the report, though the report understates that the whole module is new.

**Defects**

1. **Default (unprefixed) `f` float mode is wrong.** Probe:
   ```python
   import struct
   print(struct.pack('f', 1e40).hex())
   print(struct.Struct('f').pack(1e40).hex())
   ```
   Expected both `0000807f`; actual both `OverflowError: float too large to pack with f format` on `g` and `d`. `' f'`, `'10f'`, `'2f'` fail likewise. `_ail_struct_native_of` treats only empty/`@` as native, but CPython's default order is `@`. The report's "pack_into native float mode" fix covers explicit `@` only.

2. **Double subnormal unpack is off by 2^51.** Probe:
   ```python
   import struct
   d = b'\x01' + b'\x00' * 7
   print(struct.unpack('<d', d))
   print(struct.pack('<d', struct.unpack('<d', d)[0]).hex())
   ```
   Expected `(5e-324,)` / `0100000000000000`; actual `(1.1125369292536007e-308,)` / `0000000000000800`. `_ail_struct_scale`'s negative branch subtracts only `512+256+...+1 = 1023`, so exponent `-1074` keeps a residue of 51. All subnormal doubles are affected. Copying the helper into a probe gives the same wrong value under CPython too, so it is the prelude algorithm, not an AIL float limitation.

3. **`pack_into` wrong item-count text.** Probe:
   ```python
   import struct
   for call in (lambda: struct.pack_into('<i', bytearray(4), 0),
                lambda: struct.Struct('<i').pack_into(bytearray(4), 0)):
       try: call()
       except Exception as e: print(type(e).__name__, e)
   ```
   Expected `error pack_into expected 1 items for packing (got 0)` (both); actual `error pack expected 1 items for packing (got 0)` (both). Also, with an invalid negative offset plus a wrong count, CPython reports the count first, AIL reports the offset.

4. **`p` wrong-type error names `s`.** Probe `struct.pack('4p', 'abc')`; expected `error argument for 'p' must be a bytes object`, actual `error argument for 's' must be a bytes object`.

5. **`pack_into` into immutable bytes text (minor).** Probe `struct.Struct('<i').pack_into(b'0123', 0, 1)`; expected `TypeError argument must be read-write bytes-like object, not bytes`, actual `TypeError 'bytes' object does not support item assignment`.

Also noted: `unpack('0p', b'')` returns `(b'',)` where CPython 3.12 raises `SystemError`; `calcsize('999999999999999999999i')` raises `OverflowError` where CPython raises `struct.error: total struct size too long`.

**Report claims**
- `p` clamp, negative-zero sign, repeat-count whitespace, deep negative-offset messages: **verified** (`p3`, `p4`, `p1`, `p8`).
- Declared uint64 difference: **verified**; `AIL_EXACT_INT=1` matches CPython (`p9`).
- 12 programs build and match: **verified** by `test_ail_std_struct`.
- `test_ail_std_struct` + `test_ail_safetynet` on HEAD: **verified**, 2/2 passed, 372 s.
- `update_manifest.py --check`: **verified**, exit 0.
- "probes match CPython": **unverified** (not re-run) and **contradicted** on the boundaries above.
- "pack_into native float fix": **incomplete** (defect 1).
- No `lab/compare` source imports `struct`: **verified**; generated C for a non-struct program, including one with `struct` in the source text, is byte-identical to base `work`.

**Pre-existing:** none observed. The base has no `struct`, and plain float arithmetic matches on both base and HEAD.

**Unverified:** `test_ail_stdlib5`, `test_ail_files`, `test_ail_corpus_findings3` (not re-run); exact `lab/compare` builds (`src/main.py` is not standalone-buildable); gdev instruction counts (no runtime hot path for non-struct programs).

VERDICT: FIX
[cost $0.0468, opencode tokens {"total": 2293657, "input": 86673, "output": 14720, "reasoning": 30856, "cache.write": 0, "cache.read": 2161408}]
    tool time: bash 11.8 min, read 0.0 min
        373s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_std_stru
        119s bash   python3 - <<'EOF' p='/tmp/rprobes/p3_offsets.py' s=open(p).read() s=s.replace("""            if fmt.endswith('
         43s bash   cd /tmp/rprobes && for p in p1_floats p2_ints p3_offsets p4_parser; do echo "===== $p"; bash ~/tools/cmp.sh /t
         34s bash   cat > /tmp/rprobes/p7_subnorm.py <<'EOF' import struct  def scale(m: float, ex: int) -> float:     r = m     k
         33s bash   cd /tmp && rm -rf cH cB && mkdir cH cB && cd /home/runner/work/_temp/w2 && AIL_NO_CACHE=1 python3 AIL_CURRENT/
         32s bash   cd /tmp/cmpIePw && cat > /tmp/rprobes/p6_minsub.py <<'EOF' import math import struct  data = b'\x01' + b'\x00'
         31s bash   python3 - <<'EOF' p='/tmp/rprobes/p8_offsets2.py' s=open(p).read() s=s.replace("""        b2 = bytearray(10)  
         14s bash   cat > /tmp/rprobes/p9_uint64.py <<'EOF' import struct for fmt in ['Q', 'L', 'N', 'P']:     data = b'\x00' * 7 


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
