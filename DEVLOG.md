# DEVLOG

## 2026-10-22 — job-cov6-10220953: widen the standard library

- Census of `~/corpus/gdev` (510 programs), both compile paths: 53 refused before, 49 after.
- Added library batch 6 (`python/pkg-v12/stdlib6.py`, `prelude_ipaddress.py`,
  `prelude_urlparse.py`, hooked from `ail_syntax.python_surface`):
  - `ipaddress.IPv4Address` (int / bytes / dotted string; parse errors, ordering, `packed`, the
    address predicates, `AddressValueError` and `NetmaskValueError` as `ValueError`);
  - `urllib.parse`: `urlsplit`, `urlparse`, `urlunsplit`, `parse_qs`, `parse_qsl`, `quote`,
    `quote_plus`, `unquote`, `unquote_plus`, `urljoin`, `urlencode`. Other names are refused by name.
- The four corpus programs that needed these (`g01_004`, `g01_020`, `g17_020`, `g20_020`) now match
  CPython on both builds. Tests: `test_ail_stdlib6`.
