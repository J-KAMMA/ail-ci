# lab/socket — `import socket` in compiled programs (ffsock1)

Twelve blocking TCP programs on POSIX, each one starting its own peer in-process on 127.0.0.1
(or `::1` for the IPv6 program), so no external port and no `AIL_TEST_PORT` is needed. The oracle
is CPython 3.12: stdout and the exit status must match.

## Baseline (before the pass, `eabc6e8`)

`import socket` is refused, so every program builds nothing: **0/12**.

## After

`python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/socket/<program>.py -o <exe>` in the default
build, and the same with `AIL_UNIFIED_FORCE=1`, against `python3 lab/socket/<program>.py`.

| program | default | AIL_UNIFIED_FORCE=1 | notes |
|---|---|---|---|
| 01_echo_client.py | match | match | connect / accept / sendall / recv / getpeername-style addr |
| 02_echo_server_three.py | match | match | one listener serves three clients in turn |
| 03_line_protocol.py | match | match | newline-delimited text, `recv(1)` loop, `int()` of a field |
| 04_big_transfer.py | match | match | 1 MB through `send` / `recv` |
| 05_half_close.py | match | match | `shutdown(SHUT_WR)`, peer sees EOF, then replies |
| 06_timeout.py | match | match | `settimeout` / `gettimeout`, `TimeoutError` and `socket.timeout` |
| 07_refused.py | match | match | `ConnectionRefusedError`, errno, strerror, `str(e)` |
| 08_reset.py | match | match | `ConnectionResetError` after the peer closes with unread data |
| 09_with_closing.py | match | match | `with socket.socket(...)` and `with conn:` close on the way out |
| 10_ipv6.py | match | match | `AF_INET6` on `::1`, four-element `getsockname()` / `getpeername()` |
| 11_int_prefix.py | loud stop | loud stop | `int("99999999999999999999")` is beyond int64: `OverflowError: integer overflow in int()` on stderr, exit 1 |
| 12_send_partial.py | match | match | `send` returning short counts, `TCP_NODELAY`, `getpeername` |

**11/12 build and match CPython in both builds.** `11_int_prefix.py` stops loudly, which the job
allows for a value beyond int64 instead of printing CPython's 20-digit integer.

## Byte identity

Programs that do not `import socket` keep their C byte for byte (the pass returns before it touches
any compiler table). Compared with a worktree at `eabc6e8` (`cmp` printed nothing):

- `lab/compare/src/echo_pack/main.py`
- `lab/compare/src/ticket_audit/main.py`
- `lab/compare/src/scar_life/main.py`
- `lab/compare/src/berth_sim/main.py`
- `lab/compare/src/ledger_bin/main.py`
- `lab/compare/src/term_rank/main.py`

## Refusals checked

- `socket.recv_into()` — refused by name, `write instead: data = s.recv(n)`.
- `socket.sendfile()` (and sendto / recvfrom / recvmsg / sendmsg / makefile / dup / fileno /
  setblocking / getblocking) — refused by name with a `write instead:` line.
- Any other `socket.*` name — refused by name with `write instead:` and the built surface.
- `--target windows` (or `AIL_TARGET=windows`) — `import socket under --target windows is not
  built (Winsock is a later job)`, with a `write instead:` line.

## Known limits

- `getsockname()` / `getpeername()` / `accept()` must be unpacked (`a, b = s.accept()`); use the
  four-name form for an IPv6 address. The second element of `accept()` is a two-element address
  even on IPv6 (no flowinfo / scope_id there); `getsockname()` and `getpeername()` do give four.
- `print(s.gettimeout())` prints `None` or the seconds correctly; the value is an Optional wrapper,
  so `float(s.gettimeout())` directly is not built (bind it to a name first).
- `send` / `recv` carry bytes on the typed path and a latin-1 str on the general path; on the
  general path the program must already use bytes (a `b"..."` literal is enough), as with the
  other bytes preludes.
