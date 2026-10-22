# DEVLOG

## 2026-10-22 — job-cov6-10220953: fix the batch-6 review defects

- `urlparse` now splits `params` only for `uses_params` schemes and only after the last `/`;
  `urljoin` uses `urlparse`/`urlunparse` semantics, so a parameters-only reference joins to `/;x`.
- `urlsplit` returns `None` for an empty host and validates the port range; `parse_qs[l]` returns
  empty for an empty query under `strict_parsing` and matches CPython's `max_num_fields` check.
- `quote`, `quote_plus`, `unquote`, `unquote_plus`, `parse_qs[l]` and `urlencode` honour
  `encoding`/`errors` instead of ignoring them.
- `IPv4Address` reports CPython's "At most 3 characters permitted in ..." for long octets before the
  >255 check.
- Re-ran the six review probes and the boundary probes (`probe_url_params`, `probe_url_host`,
  `probe_url_strict`, `probe_url_encoding`, `probe_url_join`, `probe_ip_errors`): all match CPython on
  both builds. The four affected corpus programs still match on both builds.
- Corrected census (this machine, `lab/census/programs/gdev`, 508 programs, 7 error records in both
  runs): refused by both paths 47 → 43; general path 309 → 313; typed path unchanged at 145.

## 2026-10-22 — job-cov6-10220953: widen the standard library

- Census: refused by both paths 47 before, 43 after (`lab/census/programs/gdev`, 508 programs;
  general path 309 → 313). The earlier "53 → 49 of 510" figure was not reproducible.
- Added library batch 6 (`python/pkg-v12/stdlib6.py`, `prelude_ipaddress.py`,
  `prelude_urlparse.py`, hooked from `ail_syntax.python_surface`):
  - `ipaddress.IPv4Address` (int / bytes / dotted string; parse errors, ordering, `packed`, the
    address predicates, `AddressValueError` and `NetmaskValueError` as `ValueError`);
  - `urllib.parse`: `urlsplit`, `urlparse`, `urlunsplit`, `parse_qs`, `parse_qsl`, `quote`,
    `quote_plus`, `unquote`, `unquote_plus`, `urljoin`, `urlencode`. Other names are refused by name.
- The four corpus programs that needed these (`g01_004`, `g01_020`, `g17_020`, `g20_020`) now match
  CPython on both builds. Tests: `test_ail_stdlib6`.
