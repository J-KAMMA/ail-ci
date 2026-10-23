# Development log

## 2026-10-23 -- integration: fix the batch-6 review defects

- Added `python/pkg-v12/stdlib6.py`, `python/pkg-v12/prelude_ipaddress.py` and
  `python/pkg-v12/prelude_urlparse.py` to `MANIFEST.json`'s `sdk_files`, so the exported SDK carries
  the stdlib6 entry point and the prelude files its `prelude()` reads.
- Registered `test_ail_fuzz29` and `test_ail_fuzz35` in `AIL_CURRENT/ail_check.MODULES`; they were the
  only added fuzz modules missing from the suite.

## 2026-10-23 -- integration: take the accepted c169/cov6/fuzz20-35 branches

- Added the accepted job branches `job-c169-10221631`, `job-cov6-10221632`,
  `job-fuzz20-10230625`, `job-fuzz21-10230420`, `job-fuzz22-10230420`, `job-fuzz23-10230421`,
  `job-fuzz24-10230422`, `job-fuzz27-10230628`, `job-fuzz28-10230629`, `job-fuzz29-10230630`,
  `job-fuzz30-10230631`, `job-fuzz31-10230632`, `job-fuzz32-10230813`, `job-fuzz33-10230814` and
  `job-fuzz35-10230816` on top of this export, one commit per branch.
- `.agent/` and `corpus/` changes from those branches were left out.  The per-job ledger variants
  (`DEVLOG.md`, `DIFFERENCES.md`, `AIL_CURRENT/docs/spec/`) were merged into `docs/spec/` and their
  placeholder ids numbered with `tools/diff_ids.py` (new C170-C173).
- The only code overlap needing a manual merge was `pyboxed2.py`: fuzz28 refuses a computed class
  attribute read through the class, while fuzz29 shares class attributes through module-lifetime
  slots.  Both are kept: ordinary computed class attributes (including `x + 1`, `list(source)` and
  `make()`) are read through the shared definition-time slot; a class-body comprehension read
  through the class is still refused by name, as fuzz28 requires.

## 2026-10-22 -- job-fuzz21-10230420: CPython unpack error text

- fuzz21 (unpacking): the general path's `UNPACK_SEQUENCE` errors now use CPython's wording and
  counts -- `too many values to unpack (expected N)`, `not enough values to unpack (expected N, got M)`,
  `(expected at least N, got M)` for a starred target, and `cannot unpack non-iterable X object`.
  Added `AIL_CURRENT/test_ail_fuzz21.py` and registered it in `ail_check.MODULES`.

## 2026-10-22 -- job-fuzz20-10230625: int.from_bytes source type

- fuzz20: `int.from_bytes` on the general path converted its argument with the `bytes()` constructor
  rules, so `int.from_bytes(1, "big")` and `int.from_bytes(None, "big")` returned 0 where CPython
  raises TypeError. Only bytes-like objects and iterables of ints are accepted now; a str is
  rejected with CPython's TypeError too (`test_ail_fuzz20.py`).

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

## 2026-10-22 -- C169 review fix: self-referential receivers no longer recurse

Passing the same `seen` set through `value_class`/`attribute_class` into `name_class` makes a
receiver that is re-bound through its own attribute (`b = b.other`, or a chain of such bindings)
resolve to unknown instead of restarting the walk with a fresh set and overflowing the stack.
The general path then answers CPython's result; the typed-only build refuses the self-referential
class by name.  `test_ail_c169.py` adds the cycle case for both general/default builds and asserts
the typed path's named refusal.

## 2026-10-22 -- C169 review fixes: receiver class and rebinding in typed bounds

The typed list lowering now resolves an `obj.field` index bound against the receiver's visible
class -- a parameter/local annotation, constructor assignment, alias or `self` field chain -- and
falls back when it cannot.  It no longer accepts any class's same-named field, which made a float
field look like an int when another class declared that name as int.  `index_name_kind` now treats
tuple, starred, with, except, import, walrus, comprehension and nested-definition bindings as
unknown instead of reusing an earlier int assignment.  `test_ail_c169.py` builds the typed-lowering
case with `AIL_NO_GENERAL=1` (so it no longer silently exercises the general fallback) and adds
regression cases for class-field receivers and tuple/starred bindings.

## 2026-10-22 -- C169 review fixes: typed list.index bounds and long __index__ names

The default typed list lowering now classifies `list.index` start/stop bounds: visibly int/bool
bounds keep the fast loop, visibly non-index ones (None, float, str, ...) raise the slice-index
TypeError, and anything else (including objects with `__index__`) goes to the general path, which
performs CPython's full conversion.  A local typed list therefore no longer coerces a float bound.
`__index__ returned non-int (type ...)` now formats the complete type name: the general runtime grows
its name buffer to the class name's length and the bound check sizes the message accordingly.
`test_ail_c169.py` gained local typed-list, int64-width and long-name cases.

## 2026-10-22 -- C169: list.index / tuple.index bounds

Closed C169.  The general path now evaluates a start/stop bound once, converts an instance through
`__index__`, and raises CPython 3.12's slice-index TypeError for `None`, floats, strs and other
non-index values (including `__index__` returning a non-int).  The same check covers list, tuple and
deque; str's own None-as-default behaviour is unchanged.  New tests: `AIL_CURRENT/test_ail_c169.py`.
