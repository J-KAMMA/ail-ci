**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: binascii lane

**What the change really does.** Adds a bundled AIL-source stdlib `AIL_CURRENT/stdlib/binascii.py` (hex/base64/crc32/crc_hqx), 12 lab programs + RESULTS.md, one test module, and manifest rows. No compiler or runtime file is touched. The worker's final text is empty; I verified against RESULTS.md.

**Probes** (`/tmp/rprobes/p1..p9`, each run with `cmp.sh` in both builds; all matched CPython unless listed):
- `p2_b64.py` (base64 encode/decode, strict mode, junk, padding), `p3_crc.py` (crc32 values −2⁶³…2⁶³−1, crc_hqx 0…2¹⁶+3), `p4_paths.py` (list/dict/attr/arg, mutate after hexlify/a2b/crc), `p5_unhex.py`, `p9_pad.py` (10 padding corners): identical to CPython, exit 0 both builds.
- `p6_nofeature.py`: generated C identical HEAD vs base 2adbd4e (`--debug-dir`, `diff` clean).
- Probe 1 and 8 differ; see defects.

**Defects found**

1. **Internal separator sentinel is a real byte string** (`b"\x00AIL_NO_SEP\x00"`, `_sep_byte` compares with `==`). `p1_hexsep.py`: `binascii.hexlify(b"ab", bytearray(b"\x00AIL_NO_SEP\x00"))`; `p8_edge.py`: same with bytes. Expected CPython 3.12.3: `ValueError: sep must be length 1.`, exit 1. Actual both builds: `sent b'6162'`, exit 0. A user value is silently reinterpreted as "no separator".
2. **`_typename` has no `float`**. `p7_more.py`: `hexlify(b"abc", b"-", 2.0)` -> expected `TypeError: 'float' object cannot be interpreted as an integer`, actual `'object' object cannot be interpreted as an integer`; same for `crc32(b"abc", 2.5)` and `crc_hqx(b"abc", 2.5)`.
3. **`bytes_per_sep` is not range-checked as a C int**. `p7_more.py`: `hexlify(b"abc", b"-", 2**31)` -> expected `OverflowError: Python int too large to convert to C int`, actual `b'616263'`, exit 0 (same for 2⁶³−1). Silently wrong output.
4. **Non-ASCII `str` separator**. `p7_more.py`: `hexlify(b"abc", "\u0100", 1)` -> expected `ValueError: sep must be ASCII.`, actual `ValueError: byte must be in range(0, 256)` (also `"\u20ac"`).
5. **Argument validation order**. `p8_edge.py`: `hexlify(b"abc", 5, 2.0)` -> expected the float `TypeError` above, actual `TypeError: object of type 'int' has no len()` (the sep check runs before the C-level `bytes_per_sep` conversion).

**Report claims**
- 11/12 build and match CPython in both builds: **verified** — `par_check -j 2 test_ail_std_binascii test_ail_safetynet`: `ok test_ail_std_binascii 514.3s`.
- `11_crc_big` stops loudly with overflow: **verified** by the module's own assertion (test passes).
- Default build takes the general path: **verified**, but the stated reason is wrong: the compiler printed `AIL_CURRENT/stdlib/binascii.py:45:5 ... because \`is None\` on something that is never None`, not "typed path cannot raise TypeError".
- "Every error text exactly CPython's": **false** (defects 2, 4, 5).
- crc32/crc_hqx mask value to 32/16 bits: **verified** (p3).
- Only listed files changed; manifest `--check` clean: **verified** (`19 files, +760`).
- Bench wall-times, "Before 0/12" (spot-checked only 01), 20 shards/PR checks: **unverified**.

**Pre-existing**
- `test_ail_safetynet` fails `S4_generators_gc` (`'5530537\n'` vs the longer expected output) identically on base 2adbd4e with the same `ulimit` — not caused by this change.
- Stray probes left in `/tmp/rprobes` (`p_zlib.py`, `p_libm.py`, …) are from an earlier session; their diffs are CPython's missing `ail_ffi`, unrelated.

Performance: not checked — no compiler/runtime code changed (no hot path).

VERDICT: FIX

1. `hexlify(b"ab", bytearray(b"\x00AIL_NO_SEP\x00"))` / same with bytes: expected `ValueError: sep must be length 1.` (exit 1), actual `b'6162'` (exit 0) — sentinel collision in `_sep_byte`.
2. `hexlify(b"abc", b"-", 2.0)`, `crc32(b"abc", 2.5)`, `crc_hqx(b"abc", 2.5)`: expected `'float' object cannot be interpreted as an integer`, actual `'object' object cannot be interpreted as an integer` — `_typename` lacks `float`.
3. `hexlify(b"abc", b"-", 2**31)`: expected `OverflowError: Python int too large to convert to C int`, actual `b'616263'` (exit 0) — `bytes_per_sep` not range-checked.
4. `hexlify(b"abc", "\u0100", 1)`: expected `ValueError: sep must be ASCII.`, actual `byte must be in range(0, 256)`.
5. `hexlify(b"abc", 5, 2.0)`: expected the float `TypeError`, actual `object of type 'int' has no len()` — argument check order differs from CPython.
[commandcode stop=end_turn turns=40 out_tokens=32429]


--- ORIGINAL TASK ---
Lane: binascii

> Re-run of binascii2, whose GitHub run was lost (no verdict 7.4 h after dispatch). If its branch job-binascii2-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

# binascii2: `import binascii` written in AIL (`AIL_CURRENT/stdlib/binascii.py`): hex, base64, crc32, crc_hqx

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** programs in `lab/stdlib/binascii/` that build in the default mode and print what CPython
prints, with the same exit status. On `integ` today it is 0/12: `binascii.hexlify(...)` is refused with
`not in the subset: binascii.hexlify (not yet published in NAMES_library.json)`. The target is at least 10/12.
CPython's binascii is written in C, so this module is new AIL code (library policy: small spec libraries in-house,
AIL-written). The spec is CPython 3.12's behaviour, checked by the programs.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/binascii.py` (new)
- `lab/stdlib/binascii/*.py` (12 programs) and `lab/stdlib/binascii/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_binascii.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_binascii.txt` (new, one line:
  `test_ail_std_binascii`)
- the manifest files that `tools/update_manifest.py` writes

A probe on 2026-11-04: a hand-written `hexlify` and bit-by-bit `crc32` over `bytes` built and matched CPython, on the
general path only because the program printed a `bytes` value (`print() of bytes is unsupported` on the typed path).
Programs that print `.decode()` or `.hex()` results can stay typed.

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs in `lab/stdlib/binascii/`, each 15-40 lines of ordinary
   Python 3.12. Together they cover:
   - `hexlify` / `b2a_hex` with and without `sep` and `bytes_per_sep` (positive and negative), `unhexlify` /
     `a2b_hex` of `bytes` and of an ASCII `str`, upper-case digits;
   - `b2a_base64` with `newline=True` and `newline=False`, `a2b_base64` with and without `strict_mode=True`, input with
     whitespace and junk characters (non-strict mode skips them), short and long input;
   - `crc32` over chunks with a running value (must equal one call over the whole data, and `zlib.crc32`), `crc_hqx`;
   - errors caught as `except binascii.Error as e:` and printed with `str(e)`: odd-length hex, a non-hex digit,
     incorrect padding, the "number of data characters ... cannot be 1 more than a multiple of 4" message; and
     `binascii.Error` caught as `ValueError`;
   - `crc32(data, value)` with a negative value and a value beyond 32 bits, and beyond int64 (`2**64 + 5`): print
     what CPython prints, or let the program stop if the value cannot be held;
   - a small file-checksum tool that reads a fixed byte string in 4 KiB blocks and prints the CRC as `%08x`.
   Build each with the default command; record typed, general or refused, with the first refusal line, in
   `RESULTS.md` under "Before (integ <short sha>)". Commit, push, and open the PR against `integ`.
2. **The module (25 min).** Write `AIL_CURRENT/stdlib/binascii.py`: `Error(ValueError)`, `Incomplete(Exception)`,
   `hexlify`, `b2a_hex`, `unhexlify`, `a2b_hex`, `b2a_base64`, `a2b_base64`, `crc32` (table-driven, polynomial
   0xEDB88320, table built once at import), `crc_hqx` (CCITT, polynomial 0x1021). Accept `bytes`, `bytearray` and, where
   CPython does (`a2b_*`), an ASCII `str`. Every error text must be exactly CPython's: run each error case under
   `python3` and copy the text. Annotate parameters (`data: bytes`, `crc: int`) where it helps the typed path. Leave
   out `b2a_uu`, `a2b_uu`, `b2a_qp`, `a2b_qp`; list them in the module docstring as not provided. Commit and push.
3. **Make the programs pass (20 min).** Build all 12 again in the default build and with `AIL_UNIFIED_FORCE=1`. Fix the
   module, never the programs, until at least 10 build and match. A refusal that needs a compiler file goes into
   `RESULTS.md` as a follow-up with the exact text. No regressions: run
   `python3 tools/par_check.py -j 2 test_ail_std_shlex test_ail_zlib test_ail_std_base64` (skip names that do not exist
   on your base; list the test modules with `ls AIL_CURRENT/tests.d | grep -E 'base64|zlib'`). Commit and push.
4. **Bench and test (15 min).** Record instructions (Appendix B) of `crc32` over 16 MiB of LCG bytes, AIL against
   `python3` with the same program (CPython calls its C binascii, so a loss is expected; record it as is), and the
   same for `hexlify` of 4 MiB. Write `AIL_CURRENT/test_ail_std_binascii.py`, copying the structure of
   `AIL_CURRENT/test_ail_std_shlex.py`: it builds every passing program and compares stdout and the exit status with
   `python3`, in both builds, and skips when there is no C compiler. Register it (Appendix A rule 6), run it, fill
   `RESULTS.md` under "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_binascii.py` passes.
- At least 10 of the 12 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table and the two instruction counts.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled `binascii.py` is not picked up by `import binascii`, or if it changes how `base64` or
`zlib` programs build; give the exact message. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (Follow C:\Users\bluec\ail-work\agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not
   edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`; `AIL_CURRENT/stdlib/zlib.py`.
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount PROG ARGS`. If `perf_event_open` is refused, use the median of 5 wall times and say so.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
