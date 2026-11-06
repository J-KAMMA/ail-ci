# job job-ffsock1-11061344  started 2026-11-06T04:46:41Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Fixed all nine review defects (idempotent close, zero timeout, accept timeout, gettimeout arithmetic, IPv6 unpack guard, port overflow, bytes-less recv, method scoping).

Verified: all 9 probes match CPython in both builds; `test_ail_socket` (9 tests) and `test_ail_safetynet` (5 tests) pass; manifest updated and `--check` clean. Committed as `10d2806`.
[cost $0.0000, opencode tokens {"total": 8382342, "input": 291217, "output": 22064, "reasoning": 32325, "cache.write": 0, "cache.read": 8036736}]
    tool time: bash 7.1 min, read 0.0 min
        182s bash   cd /home/runner/work/ail-ci/ail-ci; python3 AIL_CURRENT/test_ail_socket.py 2>&1 | tail -40
        157s bash   cd /home/runner/work/ail-ci/ail-ci; python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -40
         22s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/probes/*.py; do echo "===== $p"; timeout 90 bash ~/tools/cmp
         17s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p2_doubleclose p3_timeout0 p4_accept_timeout p5_gettimeout_arith 
         16s bash   cd /tmp; sed '3i x = b""' /tmp/probes/p8_recv_noliteral.py > /tmp/p8b.ail; cd /home/runner/work/ail-ci/ail-ci;
          8s bash   cat > /tmp/tbytes.ail <<'EOF' def f(x: bytes) -> int:     return len(x)  def g() -> bytes:     return _ail_sp_
          8s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/probes/*.py; do echo "===== $(basename $p)"; timeout 120 bas
          5s bash   cd /home/runner/work/ail-ci/ail-ci; python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/socklib.py' s=open(p).read(

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: ffsock1 fix (`10d2806`)

**What the diff really does.** It keeps generation-stamped socket handles (`close` idempotent, stale handles EBADF), makes `settimeout(0)` return `BlockingIOError`, accepted sockets blocking, ports out of range `OverflowError`, adds an IPv6 addr-count check for unpacking, adds a bytes-less `_IO_GENERAL_STR` splice plus a `len(recv(...))` shortcut, and restricts socket-method lowering to local socket names.

**Nine named defects.** All pass on HEAD in both builds: `p1_classmethods`, `p2_doubleclose`, `p3_timeout0`, `p4_accept_timeout`, `p5_gettimeout_arith`, `p6_ipv6_unpack`, `p8_bindbig`, `p11_recv_noliteral`, `p12_stale_handle`. Verified.

**Report claims.** Tests verified (`test_ail_socket`, `test_ail_safetynet` ok, 0 failed); `update_manifest.py --check` silent; commit `10d2806` present. "Fixed all nine" is true for the named probes but the method-scoping fix is too narrow and the timeout fix is flow-insensitive, so the underlying defects are not fully fixed.

**C identity.** `echo_pack`, `ledger_bin`, `scar_life` `--debug-dir/program.c` byte-identical to `/tmp/base`. No speed measurement needed (no gdev socket program).

**Defects**

1. Method lowering now recognises only direct names / `_FUNCS` results, so sockets reaching `.close/.sendall/.recv` through an argument, list item, attribute, dict value or user-function return regressed from building to a compile failure. Probe `n2_method_arg.py`:
   ```python
   import socket
   def shut(x):
       x.close()
   s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   shut(s)
   print("closed")
   ```
   Expected `closed`, exit 0; actual both builds: `p.ail:4:5: not in the subset: the method .close() (on a value of unknown static kind)`. Same root on `n3_method_list`, `n4_method_attr`, `n5_method_dict`, `n7_send_arg`, `n8_recv_arg`, `n11_return_sock`; all built and matched on `/tmp/base`.

2. `gettimeout()` float selection is flow-insensitive per variable name, so a `settimeout` in a dead branch changes the result. Probe `n1_cond_timeout.py`:
   ```python
   import socket
   s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   flag = False
   if flag:
       s.settimeout(1.0)
   print(s.gettimeout())
   s.close()
   ```
   Expected `None`, exit 0; actual `-1e-06`, exit 0, both builds. Base printed `None`.

**Pre-existing.** `n6_alias_timeout.py` (`t = s; t.settimeout(1.5); s.gettimeout() + 0.5`) is the same `_AilSockTimeout` `TypeError` on base and HEAD; not caused by this change.

VERDICT: FIX
1. Restore method lowering for sockets held in arguments, lists, attributes, dicts and returns (`n2`, `n3`, `n4`, `n5`, `n7`, `n8`, `n11`): expected `closed` / matching output, actual compile failure `not in the subset: the method ... (on a value of unknown static kind)`.
2. Make `gettimeout()` return `None` when the runtime timeout is blocking regardless of syntactic `settimeout` occurrences (`n1_cond_timeout.py`): expected `None`, actual `-1e-06`.
[cost $0.0000, opencode tokens {"total": 1003768, "input": 75754, "output": 7185, "reasoning": 15741, "cache.write": 0, "cache.read": 905088}]
    tool time: bash 5.4 min
        189s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; timeout 900 python3 ../tools/par_check.py -j 2 test_ail_
         46s bash   cd /tmp/base; for p in n1_cond_timeout n2_method_arg n3_method_list n4_method_attr n5_method_dict n6_alias_tim
         22s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p1_classmethods p2_doubleclose p3_timeout0 p4_accept_timeout p5_g
         18s bash   cd /home/runner/work/ail-ci/ail-ci; for p in n1_cond_timeout n2_method_arg n3_method_list n4_method_attr n5_me
         17s bash   cd /tmp/base; for p in n10_bytes_call n11_return_sock; do echo "===== BASE $p"; timeout 180 bash ~/tools/cmp.s
         16s bash   cd /tmp/rprobes && cat > n10_bytes_call.py <<'EOF' import socket srv = socket.socket(socket.AF_INET, socket.SO
          6s bash   cd /home/runner/work/ail-ci/ail-ci; name=ledger_bin; src=lab/compare/src/$name/main.ail; for t in head base; d
          6s bash   cd /home/runner/work/ail-ci/ail-ci; name=echo_pack; src=lab/compare/src/$name/main.ail; for t in head base; do
