**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
I have what I need. The base safetynet shows the same `S4_generators_gc` failure, so that's pre-existing. Here's my report.

## What the change really does

Adds `AIL_CURRENT/stdlib/struct.py` — a pure-AIL reimplementation of CPython's `struct` (parse format → (code,count)+offsets; pack/unpack via `to_bytes`/`from_bytes`; `pack_into`/`unpack_from` with offsets; `iter_unpack`; `Struct`), plus 14 lab programs, a test module and manifest entries. No compiler/runtime file is touched. One line: **it ships a bundled `struct` stdlib module and its labs.**

## Defects (found on HEAD, absent on base)

1. **`pack` with a zero-count `p` crashes instead of returning `b''`.**
   `/tmp/rprobes/p1_zero.py` line 10: `print(struct.pack("0p", b""))`.
   Expected (CPython, exit 0): `b''` … then `b''` for `b"abc"` and `0` for `calcsize("0p")`.
   Actual: `IndexError: bytearray index out of range`, exit 1 — `_pack_into_items` does `out[pos] = n` with `pos=0` on the zero-length `bytearray(size)` when `count == 0`.

2. **Wrong error text for a repeat count with no specifier.**
   Same probe `/tmp/rprobes/p2_fmterr.py` lines 4-5: `struct.calcsize("3")`, `"<3"`.
   Expected: `struct.error: repeat count given without format specifier`.
   Actual: `struct.error: bad char in struct format`.

3. **Non-ASCII bytes format crashes with the wrong exception type.**
   `/tmp/rprobes/p2_fmterr.py` line 16: `struct.calcsize(b"\xff")`.
   Expected: caught `struct.error: bad char in struct format`.
   Actual: uncaught `UnicodeDecodeError: 'ascii' codec can't decode byte 0xff ...`, exit 1, missing output line.

4. **`unpack`/`unpack_from` silently accept a list as the buffer.**
   `/tmp/rprobes/p4_buftypes.py` lines 4-9: `struct.unpack("<i", [1,2,3,4])`, `struct.unpack_from("<i", [1,2,3,4], 0)`.
   Expected: `TypeError: a bytes-like object is required, not 'list'` (no stdout, exit 1).
   Actual: prints `(67305985,)` twice — `bytes(buffer)` converts the list of ints.

## Report claims

- L upper bound (`<L`/`>L`/`=L`/`!L`, native L, dict/list/attr/arg) — **verified** (`p5_prov_iter.py`, both builds match, including `@L` = 2**32 and `-1` errors).
- Negative offsets, `Struct.format` → str, bytearray format → TypeError, `c` exact-bytes — **verified by code + oracle** (no independent AIL probe for negative offsets).
- `iter_unpack` reads the live buffer, module and `Struct` — **verified** (`p5`, mutation between records observed).
- `test_ail_std_struct` 12/14 both builds — **verified** (OK, 327 s).
- safetynet `S4_generators_gc` fails on base too — **verified** (fails identically on `/tmp/rbase`).
- "Full branch diff is only the allowed module/program/test/manifest files" — **false**: commit `d1566c1` also adds 11 root artifacts (`alias.txt`, `bad.bin`, `cookie.txt`, `crlf.txt`, `e.txt`, `empty.txt`, `ident.txt`, `m.txt`, `mut.txt`, `n.txt`, `perm.txt`), test leftovers outside the allowed list.

## Other checks

- Alignment/size probes (`@bh @bi @si @ci @lh @xq @qQ =lL =bi @bq @lL @xs`) match CPython byte-for-byte (`p3_align.py`).
- A program not using `struct` (`lab/stdlib/getopt/01_short_options.py`) produces **identical `program.c`** on HEAD and base.
- Speed: no compiler/runtime hot path changed, so instruction counts are not applicable.
- Pre-existing: `test_ail_safetynet` `S4_generators_gc` (fails on base as well); `unpack("0p", b"")` raises `SystemError` upstream in CPython, so it is not matchable.

## Unverified

- `iter_unpack` over a `bytearray` whose length changes mid-iteration (CPython would raise `BufferError`; not probed).
- `memoryview`/non-bytes-like buffers beyond lists.

VERDICT: FIX
1. `struct.pack("0p", b"")` / `pack("0p", b"abc")` → expected `b''`, actual `IndexError: bytearray index out of range` (probe `/tmp/rprobes/p1_zero.py`).
2. `calcsize("3")` / `calcsize("<3")` → expected `repeat count given without format specifier`, actual `bad char in struct format` (`/tmp/rprobes/p2_fmterr.py`).
3. `calcsize(b"\xff")` → expected `struct.error: bad char in struct format`, actual uncaught `UnicodeDecodeError` (`/tmp/rprobes/p2_fmterr.py`).
4. `unpack("<i", [1,2,3,4])` and `unpack_from("<i", [1,2,3,4], 0)` → expected `TypeError`, actual `(67305985,)` printed (`/tmp/rprobes/p4_buftypes.py`).
5. Housekeeping: `d1566c1` commits 11 stray root artifacts outside the allowed file list, contradicting the report.
[commandcode stop=end_turn turns=29 out_tokens=28826]


--- ORIGINAL TASK ---
Lane: stdstruct

# struct1: `import struct` for int and bytes formats, shipped as AIL source (`AIL_CURRENT/stdlib/struct.py`)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs in `lab/stdlib/struct/` that build in the default mode and print what CPython prints,
with the same exit status. Today it is 0/14: `struct.pack` is refused with `not in the subset: class.pack (not yet
published in NAMES_library.json)` (probe of 2026-11-05). The target is at least 11/14. `struct` is how small CLI tools
read and write binary records.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/struct.py` (new)
- `lab/stdlib/struct/*.py` (14 new programs) and `lab/stdlib/struct/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_struct.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_struct.txt` (new, one line:
  `test_ail_std_struct`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit any compiler file: not `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
`ir/*`, `parallel.py`, `typedpar.py`, `ail_chatgpt.py`, `buildcache.py` or `cli.py`.

How it works: a module file in `AIL_CURRENT/stdlib/` is found by `import struct` (see Appendix B). CPython's `struct` is a
C module (`_struct`), so write the module from its documented behaviour. Follow `AIL_CURRENT/stdlib/getopt.py` and
`AIL_CURRENT/test_ail_std_getopt.py` as models.

## Sub-steps

1. **Programs and baseline (15 min).** Write 14 programs in `lab/stdlib/struct/`, each 10-40 lines of Python 3.12. Cover:
   - byte orders `<`, `>`, `!`, `=` and `@` (native sizes and alignment on x86-64 Linux), and a repeat count (`"3h"`);
   - codes `x c b B ? h H i I l L q Q n N s p`;
   - `pack`, `unpack`, `calcsize`, `pack_into` and `unpack_from` on a `bytearray` with an offset, `iter_unpack`, and the
     `Struct` class with `.size` and `.format`;
   - the edges: `q` at both ends of int64, `Q` at `2**64 - 1` (beyond int64: print what CPython prints, or stop loudly);
   - each error, caught as `except struct.error as e:` and printed as `str(e)`: a value out of range for `h`, a buffer of
     the wrong length for `unpack`, a bad format char, the wrong number of arguments;
   - 2 programs with `e`, `f` and `d`.
   Build each with the default command and record the first refusal line in `RESULTS.md` under "Before". Commit, push, and
   open the PR against `integ`.
2. **The module (30 min).** Write `AIL_CURRENT/stdlib/struct.py`: parse the format once into (code, count) items, then pack
   ints with shifts and masks into `bytes`, and unpack with `int.from_bytes`-style loops. `error` is a class derived from
   `Exception`. Every error text must be exactly CPython's (for example `'h' format requires -32768 <= number <= 32767`
   and `unpack requires a buffer of 4 bytes`); print each one with `python3` first and copy it. The float codes `e`, `f`,
   `d` are optional: if the bit-exact conversion does not fit in the time, raise
   `NotImplementedError("struct: float formats are not built yet")` and say so in the module docstring. Add annotations
   where they help the typed path. Commit and push.
3. **Make the programs pass (20 min).** Build all 14 again. Fix the module, never the programs, until at least 11 build
   and match. A refusal that needs a compiler file goes into `RESULTS.md` as a follow-up, with the exact text. Commit and
   push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_struct.py` (copy the structure of `test_ail_std_getopt.py`): it
   builds every passing program and compares stdout and the exit status with `python3`, in the default build and with
   `AIL_UNIFIED_FORCE=1`. It skips when there is no C compiler. Register it (Appendix A rule 6) and run it. Fill
   `RESULTS.md` under "After" (typed, general or refused per program). Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_struct.py` passes.
- At least 11 of the 14 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled `struct.py` is not picked up by `import struct` (the compiler may treat the name `struct`
specially); give the exact message. Also stop if fewer than 7 programs can pass without editing a compiler file; name each
blocking refusal. Stop on any output that differs from CPython without a loud stop. Stop when 80 minutes pass. Push what
is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
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
