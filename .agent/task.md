**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: ffsock1 (`import socket`)

**What the diff really does.** A tree-to-tree pass `socklib.py` (wired with two lines in `filelib.py`) rewrites `socket` calls onto `_ail_sp_sock_*` primitives; `ailsock_core.h` is a POSIX C core with a 256-slot handle table, non-blocking fds and `poll()` for timeouts; `sockrt.py` holds typed/general adapters and patches the exception/DIE tables when a socket program is compiled. It also adds 12 lab programs, `RESULTS.md` and `test_ail_socket.py`. That matches the task; no file outside the allowed list is touched (`manifest.d/*` are script-written).

**Worker report.** The report body is empty (`(no final text)`), so there are no claims to verify. I checked `RESULTS.md` instead: 11/12 match (verified — `test_ail_socket` passes), byte-identical C for 6 compare programs (**partly verified**: `echo_pack`, `scar_life`, `ledger_bin` identical to `work`; `berth_sim`/`ticket_audit` do not compile in either tree with my invocation; `term_rank` compile timed out). Its "known limit" that only the *general* path needs a bytes literal is **false**: the typed build fails too.

**Tests.** `par_check.py -j 2 test_ail_socket test_ail_safetynet` → both pass. `update_manifest.py --check` silent.

**Defects** (all compile/run on HEAD, all differ from `python3`; none exist on the base because `import socket` was refused there).

1. Any `.close/.send/.recv/.connect/...` call is lowered regardless of receiver. Probe `p1_classmethods.py`: `import socket` + `class Conn: def close(self)...; def send(self,msg)...`; `c.close(); c.send("hi")`. CPython: `conn closed / sent hi / 2 / True`, exit 0. AIL: build fails both paths — `passing ('obj', 'Conn') where _ail_sock_close() wants int` (general path also `the method .decode()`). Not a named refusal.
2. Double `close` raises. `p2_doubleclose.py`: after a session `c.close()` then `c.close(); print("twice ok")`. CPython exit 0 with `twice ok`; AIL exit 1, `OSError: [Errno 9] Bad file descriptor` (both builds). The same breaks `with s:` + explicit `s.close()`.
3. `settimeout(0)` is not non-blocking. `p3_timeout0.py`: `c.settimeout(0); c.connect(...)`. CPython `BlockingIOError / 115`; AIL prints `connected` (both builds) — it polls once and reports success when loopback connects in time. Race-dependent, and `recv` on a timed-out socket would instead raise `TimeoutError` where CPython raises `BlockingIOError`.
4. `accept()` inherits the listener timeout. `p4_accept_timeout.py`: `srv.settimeout(2.0); ... conn, addr = srv.accept(); print(conn.gettimeout()); print(conn.gettimeout() is None)`. CPython `None / True`; AIL `2.0 / False`.
5. `gettimeout()` is not a float. `p5_gettimeout_arith.py`: `t = s.gettimeout(); print(t); print(t + 0.5); print(t > 1.0)`. CPython `1.5 / 2.0 / True`, exit 0; AIL prints `1.5` then `TypeError: unsupported operand type(s) for +: '_AilSockTimeout' and 'float'`, exit 1.
6. IPv6 `getsockname()` into two names. `p6_ipv6_unpack.py`: `h, p = s.getsockname()`. CPython `ValueError` (4-tuple); AIL prints `two :: 0` (both builds).
7. Out-of-range port raises the wrong class. `p8_bindbig.py`: `s.bind(("127.0.0.1", 70000))`. CPython `OverflowError`; AIL typed `OSError`, general `ValueError` — the two builds disagree with each other and with CPython.
8. `recv` requires an incidental bytes literal. `p11_recv_noliteral.py`: connect/accept then `print(len(c.recv(0)))` (no `b"..."` anywhere). CPython `0`; AIL build fails both paths: `the name 'bytes' is not a known function/class/builtin; did you mean 'bytes'?` Adding one unused `x = b""` makes it compile. An echo loop `d = s.recv(n); s.sendall(d)` hits this.
9. Stale handles alias a new socket. `p12_stale_handle.py`: `a = ...; a.close(); b = ...; h, p = a.getsockname()`. CPython `OSError` (EBADF); AIL `stale a gives True` — the reused slot makes the closed socket read (and `close`) the new one silently.

**Speed.** Not measured: no `~/corpus/gdev` program imports socket, and a non-socket program's C is byte-identical (verified on three compare programs), so the pass cannot affect hot code. Nothing to compare with `tools/icount.c`.

**Unverified.** `term_rank` C identity (compile timed out); `berth_sim`, `ticket_audit`, `rail_transfer`, `chain_relax`, `tally_lang`, `tree_fold` C identity; the >32-user-exception / DIE-table collision path; IPv6 scope_id/flowinfo values.

VERDICT: FIX
1. Method lowering must key on the receiver being a socket (p1_classmethods.py) — expected `conn closed / sent hi / 2 / True`, actual compile error `_ail_sock_close() wants int`.
2. `close()` must be idempotent (p2_doubleclose.py) — expected exit 0 with `twice ok`, actual exit 1 `OSError: [Errno 9] Bad file descriptor`.
3. `settimeout(0)` must not wait (p3_timeout0.py) — expected `BlockingIOError / 115`, actual `connected`.
4. Accepted sockets must be blocking (p4_accept_timeout.py) — expected `None / True`, actual `2.0 / False`.
5. `gettimeout()` must return a float (p5_gettimeout_arith.py) — expected `1.5 / 2.0 / True`, actual `TypeError` on `t + 0.5`, exit 1.
6. IPv6 `getsockname()`/`getpeername()` are 4-tuples (p6_ipv6_unpack.py) — expected `ValueError`, actual `two :: 0`.
7. Port range error class (p8_bindbig.py) — expected `OverflowError`, actual `OSError` (typed) / `ValueError` (general).
8. `recv` must not require a bytes literal (p11_recv_noliteral.py) — expected `0`, actual build failure `the name 'bytes' is not a known function/class/builtin`.
9. Closed handles must stay closed, not alias a new socket (p12_stale_handle.py) — expected `OSError`, actual `stale a gives True`.
[commandcode stop=end_turn turns=32 out_tokens=32670]

## fix round skipped: only 48 minutes left


--- ORIGINAL TASK ---
Lane: ff-io

# ffsock1: `import socket` in compiled programs: blocking TCP client and server on POSIX

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs in `lab/socket/` that build in the default mode and print what CPython prints, with
the same exit status. Today it is 0/12: `import socket` is refused. The target is at least 10/12. Sockets are the
base of every network tool in the P4 niche and of asyncio (ffasync2) later.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/socklib.py` (new: the tree pass, like `proclib.py`)
- `AIL_CURRENT/python/pkg-v12/ailsock_core.h` (new: the C core) and `AIL_CURRENT/python/pkg-v12/sockrt.py` (new:
  the typed adapters, like the G8 part of `filert.py`)
- `AIL_CURRENT/python/pkg-v12/filelib.py`: two hook lines only, next to the `proclib` ones
- `lab/socket/*.py` (12 new programs) and `lab/socket/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_socket.py` and `AIL_CURRENT/tests.d/test_ail_socket.txt` (new)

Scope: `socket.socket(AF_INET|AF_INET6, SOCK_STREAM)`, `with`, `connect`, `bind`, `listen`, `accept`, `sendall`,
`send`, `recv(n)`, `recv_into` is refused by name, `close`, `shutdown`, `settimeout`/`gettimeout`, `setsockopt` with
`SO_REUSEADDR` and `TCP_NODELAY`, `getsockname`, `getpeername`, `socket.create_connection`, `socket.create_server`,
`gethostname`, and `gethostbyname` for `localhost` and numeric addresses. Errors: `ConnectionRefusedError`,
`ConnectionResetError`, `BrokenPipeError`, `TimeoutError` (`socket.timeout` is the same class), `OSError` with
CPython's errno text. `--target windows` refuses `import socket` by name (Winsock is a later job). Every name outside
the scope is refused by name with a `write instead:` line.

## Sub-steps

1. **Programs and baseline (15 min).** 12 programs, 15-40 lines each. Each one starts its own peer in-process where
   it needs one, or connects to a port given in `AIL_TEST_PORT`: echo client, echo server serving 3 clients in turn,
   a line protocol, a 1 MB transfer, half-close with `shutdown(SHUT_WR)`, timeout on a silent peer, refused connect,
   reset by peer, `with` closing, IPv6 loopback, an int length prefix parsed with `int()` of `"99999999999999999999"`
   (beyond int64: print what CPython prints or stop loudly). Record the baseline in `RESULTS.md`. Commit, push, open
   the PR against `integ`.
2. **C core and pass (25 min).** Write `ailsock_core.h` (EINTR loops, `MSG_NOSIGNAL`, `poll` for timeouts) and the
   pass. Programs that do not import socket must give byte-identical C: check with 5 compare-lab programs.
3. **Test (20 min).** `test_ail_socket.py` runs each passing program against a CPython peer on 127.0.0.1 only, in the
   default build and with `AIL_UNIFIED_FORCE=1`; it skips without a C compiler. Fill "After" in `RESULTS.md`.

## Done-check

- At least 10/12 programs build and match CPython in both builds; `python3 AIL_CURRENT/test_ail_socket.py` passes.
- The C of 5 compare-lab programs is byte-identical to `origin/integ` (`cmp` prints nothing).
- The 20 shards pass; `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop on any program that prints output different from CPython. Stop if the hook needs a file outside the list; name
the file and the line. Stop when 60 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed. Never silent wrong output: stop and report the moment
   any program prints something CPython does not.
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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`, unless this task names the file and
   the one minimal hook it may add there (owner decision 3 of 2026-11-06: only when no other running job edits that
   file). Do not edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task
   names, plus the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly. Release builds use
  gcc -O2.
- Library policy: a small spec library is written in AIL (`AIL_CURRENT/stdlib/*.py`, found by `ail_modules.py`
  `BUNDLED_DIR`); TLS, signatures and SQLite go through proven native libraries.
- Runtime-backed modules follow `AIL_CURRENT/python/pkg-v12/proclib.py` (stage G8, subprocess): a tree-to-tree pass
  plus a C core header (`ailproc_core.h`), wired by two lines in `filelib.py` (`PRIMS.update(...)` near line 66 and
  `rewrite_tree(...)` near line 152). A program that does not import the module must produce byte-identical C.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.
- Speed claims: instruction counts with `tools/icount.c`, output unchanged.

## Owner decision (2026-11-06)

- Sockets on Windows (Winsock) are out of scope for v1: refuse by name.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
