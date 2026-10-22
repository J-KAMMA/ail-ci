# job job-cov6-10220953  started 2026-10-22T00:55:34Z  worker=oc reviewer=oc (GitHub)

## worker report 0
**Report — job-cov6-10220953**

- **Census (510 gdev programs):** 53 refused before, **49 after** on both builds.
- **Implemented (library batch 6, AIL-written preludes):**
  - `ipaddress.IPv4Address` (int/bytes/string, parse errors, ordering, `packed`, address predicates, error aliases)
  - `urllib.parse`: `urlsplit`, `urlparse`, `urlunsplit`, `parse_qs`, `parse_qsl`, `quote`, `quote_plus`, `unquote`, `unquote_plus`, `urljoin`, `urlencode`
  - Unsupported names (`IPv6Address`, `IPv4Network`, `urldefrag`, …) are refused by name with notes.
- **Corpus fixed:** `g01_004`, `g01_020`, `g17_020`, `g20_020` now match CPython on both builds.
- **Probes (`bash ~/tools/cmp.sh …`):** `ip_basic`, `ip_edges`, `ip_imports`, `url_basic`, `url_edges`, `url_imports` — all same stdout on `g` and `d`. `ip_unsupported` / `url_unsupported` refused by name as expected.
- **Tests:** `test_ail_stdlib6` (new), plus `test_ail_stdlib5`, `test_ail_stdlib_batch3`, `test_ail_stdlib_batch4`, `test_ail_python_syntax`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_http`, `test_ail_re` — 10/10 passed. Manifest `--check` passes.
- **Commit:** `67c00ea` on `job-cov6-10220953` (not pushed).
[cost $0.1254, opencode tokens {"total": 9017251, "input": 372236, "output": 31685, "reasoning": 41426, "cache.write": 0, "cache.read": 8571904}]

## review 0
**Verification**
- Corpus: `g01_004`, `g01_020`, `g17_020`, `g20_020` match CPython on both builds.
- Tests on HEAD: the 10 named modules all pass; `update_manifest.py --check` passes.
- Non-user programs: `g00_000` has identical generated `program.c` and identical executable on base vs HEAD.
- Worker probes `ip_edges`, `url_edges`, `ip_imports`, `url_imports` match CPython on HEAD.
- Census: the 4-program drop is confirmed, but the absolute `53 → 49` is not reproduced by `lab/census` (base `47` refused-by-both, HEAD `43`; general path `311 → 315`), so that number is unverified.
- The new prelude is too permissive in several places; base refused some of these by name, HEAD now accepts and prints the wrong result.

**Defects** (all reproduced on both `g` and `d`)

1. `urlparse` splits `params` at the first `;` regardless of scheme or last `/`.
   Probe `/tmp/rprobes/p_url_params.py`: `urlparse("foo://h/a;b?q")` and `urlparse("http://h/a;b/c")`.
   Expected `path=/a;b params=''` and `path=/a;b/c params=''`; actual `path=/a params=b` and `path=/a params=b/c`.

2. Empty host must be `None`, not `''`.
   Probe `/tmp/rprobes/p_url_hostname.py`: `urlsplit("http://:80/").hostname`.
   Expected `None`; actual `''`.

3. Empty query with `strict_parsing=True` must return empty.
   Probe `/tmp/rprobes/p_url_strict.py`: `parse_qsl("", strict_parsing=True)` / `parse_qs(...)`.
   Expected `[]` / `{}`; actual `ValueError bad query field: ''`.

4. `encoding`/`errors` arguments are silently ignored (base refused these by name).
   Probe `/tmp/rprobes/p_url_encoding.py`: `quote("é", encoding="latin-1")`, `unquote("%E9", encoding="latin-1")`, `parse_qsl("x=%E9", encoding="latin-1")`.
   Expected `%E9`, `é`, `[('x','é')]`; actual `%C3%A9`, `�`, `[('x','�')]`.

5. `urljoin` mishandles a relative reference that is only parameters (uses `urlsplit`, not `urlparse`/parameters).
   Probe `/tmp/rprobes/p_url_join.py`: `urljoin("x", ";x")` and `urljoin("x", ";x?y#s")`.
   Expected `/;x`, `/;x?y#s`; actual `;x`, `;x?y#s`.

6. `IPv4Address` parse error text differs for octets longer than 3 characters.
   Probe `/tmp/rprobes/p_ip_errors.py`: `IPv4Address("1234.1.1.1")`.
   Expected `At most 3 characters permitted in '1234' in '1234.1.1.1'`; actual `Octet 1234 (> 255) not permitted in '1234.1.1.1'`.

VERDICT: FIX
[cost $0.0368, opencode tokens {"total": 2264751, "input": 85474, "output": 10517, "reasoning": 18616, "cache.write": 0, "cache.read": 2150144}]

## worker report 1
Fixed all six review defects in commit `d2f0462`.

- `urlparse` params now follow `uses_params` + last `/`; `urljoin` uses parse/unparse semantics (`/;x`).
- Empty hostname is `None`; ports validate 0–65535.
- Empty query under `strict_parsing` returns `[]`/`{}`; `max_num_fields` matches CPython.
- `encoding`/`errors` now honoured by `quote`, `quote_plus`, `unquote`, `unquote_plus`, `parse_qs[l]`, `urlencode`.
- `IPv4Address` long-octet error now matches CPython.

Verification on the final commit:
- 18 probes (6 review + 6 new boundary + 6 prior) all match CPython on both builds.
- `g01_004`, `g01_020`, `g17_020`, `g20_020` match on both builds.
- Tests: `test_ail_stdlib6`, `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 pass.
- `update_manifest.py --check` passes.
- Census (`lab/census`, 508 programs): refused by both `47 → 43`; general `309 → 313`; 7 error records in both runs. DEVLOG corrected to these numbers.
[cost $0.0686, opencode tokens {"total": 4476015, "input": 242101, "output": 17939, "reasoning": 14887, "cache.write": 0, "cache.read": 4201088}]

## review 1 failed to run: (no final text) [cost $0.0888, opencode tokens {"total": 8108237, "input": 138678, "output": 24978, "reasoning": 48901, "cache.write": 0, "cache.read": 7895680}] (cut off after 60 minutes) 

## review 1
Reviewed `work..HEAD` (67c00ea, d2f0462). Probes are in `/tmp/rprobes/`, built with `cmp.sh` on both paths.

**Verified**
- `test_ail_stdlib6`, `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 5/5 pass.
- `update_manifest.py --check`: pass.
- Census from the saved jsonl (`/tmp/census_base.jsonl` vs `/tmp/census_head.jsonl`): typed 145, general 309→313, refused by both 47→43, 7 error records. The report's numbers are correct.
- `g01_004`, `g01_020`, `g17_020`, `g20_020`: match CPython on both builds.
- Parameters (`uses_params`/last `/`), `urljoin("/;x")`, empty hostname, ports, strict empty queries, `max_num_fields`, encoding/errors, and the long-octet error all match.
- A program with no mention of either module has byte-identical `program.c` (base vs HEAD). `import urllib.parse` with no call changes C (the import is dropped), but not its output.
- `icount` cannot run here (`perf_event_open` EPERM); non-feature executables are byte-identical, so runtime is unchanged.

**Defects**
`rv_defect_url.py`:
```python
import urllib.parse as up
print(up.urlencode([("a", ["1", "2"]), ("b", "3")], doseq=True))
try: print(up.urlsplit("http://x[::1]/"))
except ValueError as e: print("ValueError", e)
```
CPython: `a=1&a=2&b=3` / `ValueError Invalid IPv6 URL`. Both builds: `a=%5B%271%27%2C+%272%27%5D&b=3` / accepted `SplitResult(...)`.

`rv_defect_ip.py`:
```python
print(A("192.0.0.8").is_private, A("192.0.0.8").is_global)
print(A("224.0.0.1").is_global)
try: A("1.2.3.4/24")
except ValueError as e: print("ValueError", e)
```
CPython: `True False` / `True` / `ValueError Unexpected '/' in '1.2.3.4/24'`. Both builds: `False True` / `False` / `ValueError Only decimal digits permitted in '4/24' ...`.

`rv_ip_eq.py`: `hash(A("1.1.1.1")) == hash(16843009)` is `False` in CPython (hash is `hash(hex(int(ip)))`) but `True` in both builds; `1 + A(...)` also exposes `_AilIPv4Address` in the `TypeError` text.

VERDICT: FIX
1. `urlencode` ignores `doseq` for a sequence of pairs; expected `a=1&a=2&b=3`, got `a=%5B%271%27%2C+%272%27%5D&b=3`.
2. `urlsplit` does not validate bracketed netloc: `http://x[::1]/` must raise `Invalid IPv6 URL` but is accepted; `http://[abc]/` must raise `"'abc' does not appear to be an IPv4 or IPv6 address"` but is accepted.
3. `IPv4Address.is_private`/`is_global` are wrong: `192.0.0.8` should be `(True, False)` but is `(False, True)` (the code approximates `192.0.0.0/24` as `/29` + `192.0.0.170/31`), and multicast (`224.0.0.1`) should be `is_global=True` but is `False`.
4. `IPv4Address` does not reject `/` before parsing: `1.2.3.4/24` must say `Unexpected '/' in '1.2.3.4/24'`, not `Only decimal digits permitted ...`.
5. `IPv4Address.__hash__` hashes the integer; CPython hashes `hex(int(ip))`, so `hash(A("1.1.1.1")) == hash(16843009)` must be `False`, not `True`.
[cost $0.0655, opencode tokens {"total": 6078839, "input": 124563, "output": 18205, "reasoning": 30279, "cache.write": 0, "cache.read": 5905792}]

FINAL VERDICT: FIX  2026-10-22T05:07:20Z
