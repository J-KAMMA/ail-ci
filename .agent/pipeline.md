# job job-fuzz66-10231452  started 2026-10-23T05:53:11Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed one silent `str.format` bug and committed as `faf0744`.

**Bug:** the general-path runtime formatter parsed and then discarded the `z` format option. It silently printed `"{:z}".format(0)` → `0` and `"{:z}".format(-0.0)` → `-0.0`; CPython raises `ValueError` for int/bool/str and prints `0.0` for a rounded negative zero float.

**Fix:** keep the `z` flag in `safetyrt.py`; reject it for int/bool/str with CPython's messages; apply negative-zero coercion when the formatted float mantissa is zero. Added `test_ail_fuzz66.py` and registered it in `ail_check.py`.

**Verification (final commit):**
- Probes, all matching CPython on both g/d builds: `z1.py`, `z2.py`, `z4.py` (z matrix incl. inf/nan, widths, signs, nesting, named/attribute/list/dict/argument sources), plus regression probes `p01`, `p03`, `p04`, `p07`, `p08`, `p11`, `p13`.
- `tools/update_manifest.py --check`: OK.
- `par_check.py -j 2 test_ail_fuzz66 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed.

**Other differences seen (left unfixed):** `#` on a default-formatted huge float (`format(1e300, "#")` gives `1e+300` vs CPython `1.e+300`); default object `repr` address text; int64 overflow for `10**30`; `format_map` with a mapping lacking `__contains__`. No DEVLOG/DIFFERENCES files exist in this checkout.
[cost $0.0000, opencode tokens {"total": 5994878, "input": 125296, "output": 16122, "reasoning": 22420, "cache.write": 0, "cache.read": 5831040}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `faf0744` (str.format `z` option in `safetyrt.py`, new `test_ail_fuzz66.py`, manifest/`ail_check` registration).

**Probes (HEAD, both general and default builds unless noted)**

| Probe | Result |
|---|---|
| `/tmp/rprobes/z_sources.py` (arg/list/attr/dict/nested/fill/pad/group) | same stdout as CPython on g/d |
| `/tmp/rprobes/z_types.py` (int/bool/str/None, int with float types) | same on g/d |
| `/tmp/rprobes/z_edges.py` (`-0.0`, rounding to zero, inf/nan, `#`, `%`, upper types, widths) | same on g/d |
| `/tmp/rprobes/z_errors.py` (~1.5k spec/type combinations, messages printed) | same except pre-existing `' z'` str message (below) |
| `/tmp/rprobes/z_weird.py` (ordering of z vs invalid type/group/align, custom `__format__`) | same on g/d |
| `/tmp/rprobes/noz_format.py` (formatting without `z`) | same on g/d |
| Worker probes `z1.py`, `z2.py`, `z4.py` | same on g/d |
| Worker regressions `p01.py`, `p13.py` | same on g/d |
| `other_diffs.py` (`#` huge float, `10**30`) | differs, **identical on base** |

**Codegen:** `--debug-dir` for a program using no formatting is byte-identical to `work` (`program.c` diff empty). A formatting program differs only in the intended FMT block.

**Tests:** `test_ail_fuzz66`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`, 0 failed). `update_manifest.py --check` passes. No DEVLOG/DIFFERENCES file exists in this checkout, as reported.

**Claims:** bug/fix, int/bool/str refusals, negative-zero coercion, test registration and named probes all verified. The two "other differences" I checked are confirmed pre-existing and base-identical; `repr` address and `format_map` claims not checked (unverified, non-blocking).

**Pre-existing (not caused by this change):** `format('x', ' z')` reports "Sign not allowed..." where CPython says "Space not allowed..." (base identical); `format(1e300, '#')` → `1e+300` vs `1.e+300`; `format(10**30, 'd')` integer overflow (base identical).

**Notes (non-blocking):** `tools/ci_shards.py --check` flags `test_ail_fuzz66` unassigned; the workflow still runs unassigned modules by name. `perf_event_open` is denied on this runner, so instruction counts could not be taken; the added work is a flag check plus a zero-mantissa scan only on the formatting path, and non-format C is unchanged.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1881196, "input": 107585, "output": 9838, "reasoning": 16061, "cache.write": 0, "cache.read": 1747712}]

FINAL VERDICT: ACCEPT  2026-10-23T06:28:39Z
