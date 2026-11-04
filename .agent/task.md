Lane: hash

# std_hashlib: twelve hashlib/hmac programs on the typed path, and sha256 throughput against CPython

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** `lab/stdlib/hashlib/` programs that build on the TYPED path and print exactly what CPython prints:
not measured today (no such directory) -> at least 10/12. Second number: seconds to sha256 a 256 MiB stdin, AIL binary
against `python3` (OpenSSL) and `sha256sum`.

Base: `origin/integ`. Files you may edit: `AIL_CURRENT/python/pkg-v12/hashlower.py` (the typed lowering of `hashlib`,
`hmac`, `secrets`; read its docstring: the object is the class `_AilHash`), `AIL_CURRENT/python/pkg-v12/hash_prelude.py`,
`AIL_CURRENT/python/pkg-v12/ailhash_core.h` (self-contained C: md5, sha1, sha2, sha3, blake2; SHA-NI paths
`ailhs_sha256_blocks_ni` at about line 287), new `lab/stdlib/hashlib/`, new `AIL_CURRENT/test_ail_std_hashlib.py`, new
`AIL_CURRENT/tests.d/test_ail_std_hashlib.txt`. Do not change what `hashlower.py` does for `base64` or `int.to_bytes`
(other tests own them). Do not edit `filert.py`, `safetyrt.py`, `cruntime.py` or any file in Appendix A rule 8. Read
`AIL_CURRENT/test_ail_crypto.py` for what is tested today.

## Sub-steps

1. **Programs (20 min).** Write 12 programs in `lab/stdlib/hashlib/`, 15-50 lines each, as a user would write them:
   file checksum of stdin read in 64 KiB chunks with `update` (`sys.stdin.buffer`); `hexdigest` of the same text in md5,
   sha1, sha256, sha512, sha3_256; `hashlib.new(name)` over a list of names, plus an unknown name caught as `ValueError`
   (print the message); `blake2b(digest_size=20, key=..., person=...)` and `blake2s`; `copy()` of a running hash;
   `digest_size`, `block_size`, `name`; `hmac.new(key, msg, "sha256").hexdigest()` and `hmac.compare_digest`;
   `hashlib.pbkdf2_hmac("sha256", pw, salt, 10000, dklen=32).hex()`; a content-addressed store (dict from hexdigest to
   bytes); a Merkle root over 1000 leaves; `int.from_bytes(sha256(...).digest()[:8], "big")` (beyond int63: check it does
   not stop); empty input for every algorithm. Give each program an input file in `lab/stdlib/hashlib/data/` where it
   reads stdin. Run each with `python3`. Commit, push, open the PR against `integ`.
2. **Census (10 min).** Build each with the default command and with `AIL_UNIFIED_FORCE=1`; write
   `lab/stdlib/hashlib/RESULTS.md` (program, typed / general / refused, equal to CPython, first stderr line). Commit.
3. **Fixes (25 min).** Fix the most common refusal or difference first, in the files above only. Each fix makes a program
   typed and equal, or makes a difference equal. Refuse loudly, by name, what you do not build. Rebuild all 12 after each
   fix and update the table; commit.
4. **Throughput and test (20 min).** `head -c 268435456 /dev/urandom > /tmp/big.bin`; time (median of 3) the checksum
   program's AIL binary, `python3` on the same program, and `sha256sum`, all on `/tmp/big.bin` (not in git). Record in
   `RESULTS.md` with whether SHA-NI was used (`grep -o sha_ni /proc/cpuinfo | head -1`). Write
   `test_ail_std_hashlib.py` (model: `test_ail_std_statistics.py`): `PASSING` build and match CPython, `TYPED` must have
   no general-path note, `REFUSED` keep a named text. Register it (Appendix A rule 6). Run
   `python3 tools/par_check.py -j 2 test_ail_std_hashlib test_ail_crypto test_ail_std_base64`. Push.

## Done-check

>= 10/12 typed and equal to CPython; the throughput row is written; `test_ail_crypto` and `test_ail_std_base64` still
pass; 20 shards pass.

## Stop rule

A fix that needs a file outside the list: write it as a finding with the refusal text and go on. If fewer than 10 are
typed at 65 minutes, stop fixing, finish step 4 with what passes, and report the number. Stop at 80 minutes; push what is
done.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. Turning a
   correct program into a refusal or a stop is a regression. When a new fast path cannot handle a case, keep the old route.
2. Probe ints beyond int64 wherever ints come from text, fields or arithmetic. Run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, and compare both with `python3`.
3. Push early and open the PR against `integ`. Wait for all 20 `shard` checks on your head commit
   (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `origin/integ` (or from one unmerged PR at most; never from a PR that is itself stacked).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: add `AIL_CURRENT/tests.d/<module>.txt` (one line: the module name), `git add` every new file, run
   `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, tag, publish, change repository settings, cancel runs, or edit
   `.github/workflows`.
8. Files owned by busy lanes; do NOT edit them: `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`,
   `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `pyc.py`, `buildcache.py`, `pyboxed2.py`, `packaging/ail_lang/cli.py`.
   Also do not edit `DEVLOG.md` or `AIL_CURRENT/DEVLOG.md` (integration writes them). If a fix needs one of these files,
   do not make it: write a finding (file, function, what is needed, the refusal text) in your results file and go on.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC.py -o OUT [--syntax python] [--strict] [--exact-int]
  [--debug-dir DIR]`. `-o` must not exist yet. The default build tries the typed path first; when it falls back it prints
  `note: ... built on the general path` on stderr. No such note = typed. `--strict` = typed path or refuse.
  `DIR/program.c` is the generated C. Use `AIL_NO_CACHE=1` for timings.
- One test module: `python3 tools/par_check.py -j 2 test_ail_<name>`.
- Model test file: `AIL_CURRENT/test_ail_std_statistics.py` (build each program in a temp dir, run it, compare stdout and
  exit code with `python3 <program>`).
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount PROG ARGS < input`. If `perf_event_open` is refused, run `sudo sysctl -w kernel.perf_event_paranoid=1`
  once; if it is still refused, use the median of 5 wall times and say so in the results.
- The oracle is CPython 3.12 (`python3`). Peak RSS: `/usr/bin/time -v PROG` ("Maximum resident set size").
- AIL is Python syntax plus optional annotations. Ints are int64 by default and overflow stops loudly;
  `--exact-int` gives exact ints.

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
