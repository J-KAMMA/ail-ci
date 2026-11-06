# job job-ffsock1-11060908  started 2026-11-06T00:12:51Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
Continue if you have next steps, or stop and ask for clarification if you are unsure how to proceed.
[cost $0.0000, opencode tokens {"total": 8500396, "input": 350705, "output": 39385, "reasoning": 48738, "cache.write": 0, "cache.read": 8061568}]
    tool time: bash 3.7 min
        120s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import pathlib p=pathlib.Path('AIL_CURRENT/python/pkg-v12/so
         18s bash   cd /tmp && cat > probes/enc.py <<'EOF' def main() -> None:     s = 'hi'     b = s.encode('latin-1')     print(
         18s bash   cd /tmp && cat > probes/enc2.py <<'EOF' def _ail_sock_text_bytes(text: str) -> bytes:     return text.encode('
         17s bash   cd /tmp && cat > probes/dectest.py <<'EOF' def f(data: bytes) -> str:     return data.decode('latin-1')  def g
          6s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import pathlib p=pathlib.Path('AIL_CURRENT/python/pkg-v12/so
          5s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import pathlib p=pathlib.Path('AIL_CURRENT/python/pkg-v12/so
          5s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import pathlib p=pathlib.Path('AIL_CURRENT/python/pkg-v12/so
          5s bash   cd /tmp && cat > probes/echosrv.py <<'EOF' import socket s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, so

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

FINAL VERDICT: FIX  2026-11-06T04:19:02Z
