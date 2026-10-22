# DEVLOG

## 2026-10-21 — fuzz12: bytes and bytearray

Differential fuzz round on bytes / bytearray (indexing, slicing, hex/fromhex, join/split/find,
startswith/endswith, decode/encode with errors, bytearray mutation, comparisons, repr). 55 hand
written probes plus 30 generated seed programs were built in both modes and compared with CPython.

Fixed three silent causes:

* `repr()` / `str()` of a bytearray escaped a lone single quote differently from CPython
  (`bytearray(b"\'")` vs `bytearray(b"'")`).
* `bytes.split(None, maxsplit)` / `rsplit(None, maxsplit)` stripped the whitespace on the
  unprocessed side of the remainder once the limit was reached.
* `%r` in a bytes / bytearray format unwrapped its bytes-like argument, losing the `b` prefix
  (`b"%r" % b"ab"` printed `b"'ab'"` instead of `b"b'ab'"`).

Added `AIL_CURRENT/test_ail_fuzz12.py` (both builds, CPython oracle) and registered it in
`ail_check.py`. Not fixed, listed for a later round: bytearray `+=` / `*=` rebind instead of
mutating in place (a second name does not see the change), an empty assignment to an extended
bytearray slice raises ValueError where CPython accepts it, ordering a `bytes` against an equal
`bytearray` crashes (`__lt__` is retried on the wrong receiver), decoding a non-BMP UTF-8
sequence hits the 16-bit runtime internal error, and `%b` / `%a` / mapping-key bytes formats are
not built.
