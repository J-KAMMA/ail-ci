# DEVLOG

## 2026-10-22 — job-cov6-10221632: fix the Fraction hash regression

- `Fraction.__hash__` returns `hash(numerator)` when the denominator is 1, so an integral
  `Fraction` hashes as the equal `int` again (e.g. `Fraction(2 ** 61, 1)` and `Fraction(2 ** 61 - 1, 1)`
  hash to 1 and 0), with `-1` still canonicalised to `-2` by the runtime.
- Added the integral-hash cases to `test_ail_stdlib5` (compiled `f1` program and the direct prelude
  comparison).
- Probes `probe_fracbase` and `probe_fractionhash` match CPython on both builds for the integral
  cases (direct values, `2 ** 63 - 1` boundary, negatives, argument, list item, attribute, dict key).
  The non-integral `Fraction(1, 2)` hash remains the pre-existing declared difference.
- `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3` pass.

## 2026-10-22 — job-cov6-10221632: fix the batch-6 review defects

- `urlencode(..., doseq=True)` now expands list/tuple values in a sequence of pairs, not only in a dict
  (`[("a", ["1", "2"]), ("b", "3")]` gives `a=1&a=2&b=3`).
- `urlsplit`/`urlparse` run CPython's bracketed-netloc check: `x[::1]` and data after `]` are
  `Invalid IPv6 URL`, while `[abc]` is `"'abc' does not appear to be an IPv4 or IPv6 address"` and
  bracketed IPv4 is refused.
- `IPv4Address.is_private` uses `192.0.0.0/24` with the `192.0.0.9`/`192.0.0.10` exceptions;
  `is_global` is `not is_private and not 100.64.0.0/10`, so multicast is global.
- `IPv4Address` rejects `/` before octet parsing, and `__hash__` hashes `hex(value)`. The runtime no
  longer re-hashes the `__hash__` result of every class with `__int__`; `IntEnum.__hash__` returns
  `hash(value)` itself.
- Probes `probe_doseq`, `probe_url_brackets`, `probe_ip_fixes2` and the hash property probes match
  CPython on both builds. `test_ail_stdlib6`, `test_ail_fuzz1.HashValues` and
  `test_ail_stdlib5.CompiledPrograms` pass.

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
## 2026-10-23 - C compiler step cache (job-ctime3-10232149)

The base export already contains the content-addressed `cc` layer in
`AIL_CURRENT/python/pkg-v12/buildcache.py` (`buildcache.run_cc`, activated by `--cache`, stored under
`$AIL_CACHE` / `~/.cache/ail`, off with `AIL_NO_CACHE=1` or `--no-cache`). The task says not to add
a second cache when one already exists, so this job verifies and measures that layer and adds a
regression test for the exact reuse case:

* `test_changed_source_with_the_same_generated_c_hits_the_cc_cache` changes a typed local's name,
  which changes the merged source text (a new front-end entry) but not the generated C: the C
  compiler step is skipped and the executable is byte-identical.

Measurement on this 4-core runner, gcc 13.3, median of 5 runs, `AIL_CACHE` in a temporary
directory. "before" is `AIL_NO_CACHE=1`; "after" is a cache warm from the same C text with a new
front-end key (a renamed local), so the front end runs but the C compiler step hits. Wall time is
the whole `ail_chatgpt.py compile`; C time is the sum of the compiler wrapper's own runs (after
includes the cache's one-time toolchain probes).

| gdev program | wall before | C before | wall after | C after | outputs |
| --- | ---: | ---: | ---: | ---: | --- |
| g00_000 | 1.245 s | 0.241 s | 1.177 s | 0.013 s | identical |
| g00_002 | 1.427 s | 0.393 s | 1.186 s | 0.012 s | identical |
| g00_004 | 2.540 s | 1.418 s | 1.279 s | 0.012 s | identical |

Output SHA-256 values were equal for every before/after pair. With an unchanged source the whole
front-end cache also hits, so the compiler step is not run at all.
