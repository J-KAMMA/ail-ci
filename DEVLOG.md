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
## 2026-10-22 - fuzz8 review 2 fixes (job-fuzz8-10221632)

1. `_attribute_kind` / `_attribute_container` now add the attribute to the recursion guard `seen`
   and return `None` on a cycle instead of recursing forever.  `b.x = b.x + 1` (or `b.x = b.x`)
   together with `itertools.accumulate(..., initial=b.x)` or `groupby([b.x, ...])` no longer aborts
   every build with `RecursionError`; the typed path declines and the default build falls back,
   matching CPython (`[2, 3.5]`, `1 [1, 1]` / `2 [2]`).
2. Corrected `DIFFERENCES.md` row `C?-job-fuzz8-10221632-2`: mutable-element groupby keys do not
   run on a typed recompute.  `--strict` refuses the pattern (`'_ilN_gc' is read before it is
   assigned`) and the default build uses the general path.

`AIL_CURRENT/test_ail_fuzz8.py` covers self-referential and cross-name attribute cycles through
arguments, list items, dict values, nested attributes and groupby.  Probes:
`/tmp/probes/attr_cycle_acc.py`, `attr_cycle_self.py`, `attr_cycle_groupby.py`,
`attr_cycle_two_names.py`, `attr_cycle_nested.py`, `attr_cycle_float.py`,
`attr_cycle_dict_list.py`.

## 2026-10-22 - fuzz8 review fixes (job-fuzz8-10221632)

1. `itertools.groupby` no longer reuses a stale look-ahead key for a list of mutable elements.
   The typed path still declines that pattern (`--strict`: `'_ilN_gc' is read before it is
   assigned`) and the default build falls back to the general path, which matches CPython.
   Scalar/str element lists stay on the typed path and call the key once per element.  Probe
   `gb_cache_regress_len.py` prints `1 3` / `3 1`.
2. `itertools.accumulate(xs, initial=v)` on the typed path is refused by name when the types of
   `v` and the elements differ.  One-argument `round()` is now classified as `int` through local
   bindings, list items, attributes and dict values, so the float-list probe falls back to the
   general path and prints `[2, 3.5, 6.0]` instead of `[2.0, 3.5, 6.0]`.

`AIL_CURRENT/test_ail_fuzz8.py` has both cases; the typed groupby/accumulate modules, safetynet,
files and corpus_findings3 pass on the final commit.


## 2026-10-21 - fuzz8: iteration tools (job-fuzz8-10220554)

Ran 65 small differential programs over chain / islice / product / permutations / combinations /
combinations_with_replacement / accumulate / groupby / zip_longest / starmap / enumerate /
zip(strict=) / sorted / min / max / reversed / map / filter, each through `bash ~/tools/cmp.sh`
on the default build and `AIL_UNIFIED_FORCE=1`.  Fixed three causes (all now in
`AIL_CURRENT/test_ail_fuzz8.py`, with probes in `/tmp/probes`):

1. `itertools.accumulate(..., initial=None)` now treats None as "not given", as CPython 3.12 does
   (`cruntime.ail_it_accumulate`).  Constant, argument, list-item, attribute and dict-value routes
   are tested.
2. `sorted` / `list.sort` call their key on the input in the original order even for
   `reverse=True`, and call it once for a one-element list (`cruntime.ail_list_sort`).  Before, the
   elements were reversed before the key calls, which only showed with a key that has a side effect.
3. The typed path's `itertools.groupby` reuses the look-ahead key, so it calls the key exactly once
   per element instead of twice on each group boundary (`itlib.Groupby`).

Remaining differences found are recorded in `DIFFERENCES.md`; they were not fixed in this job.
