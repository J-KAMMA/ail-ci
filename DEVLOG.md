# DEVLOG

## 2026-10-26 - bigint-fix07 (job-bigint-fix07-10261217)

- Review 1 fixes: a module int returned from a function is now `ail_tint` (and propagates through
  wrappers), so `x *= 4; print(get())` past int64 prints exactly instead of aborting.
- Under whole-program module-int tint storage every int parameter and result of a user function is
  tagged, so a big module value also survives a call boundary; `range(n)` over a module int gets a
  tagged index.
- `& | ^` on tagged ints are exact (`ail_tint_bitop`, two's-complement, past int64); a module value
  stored into an int64 list/attribute/dict is refused by name and the default build takes the
  general path instead of aborting.
- `MANIFEST.json` refreshed; `--check` rc 0. Added two regression tests to `test_ail_globals`.
- Tests: `test_ail_globals` 34/34, `test_ail_bigint`, `test_ail_tint`, `test_ail_unified`,
  `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`).
  `test_ail_dunders`, `test_ail_nested_functions`, `test_ail_unbound` keep the same pre-existing
  failure names as base `a30dcae`.
- Probes: 13 programs under /tmp/probes (`p20_retmin`, `p20_wrap`, `p20_arg_show`,
  `p20_range`, `p20_bit`, `p20_bit_small`, `p20_bit_edges`, `p20_bool_int`,
  `p20_containers_read`, `p20_list_store`, `p20_attr_store`, `p20_dict_store`,
  `p20_append`): all match CPython on both builds, or the typed build refuses by name and the
  default build matches.


## 2026-10-25 - bigint-fix07 (job-bigint-fix07-10260546)

- Module-variable reads/writes no longer force the general path on the Python surface. `ir/driver.py`
  drops the blanket refusal and treats the local proof's unknown module-variable operand as the
  int64 static it is, so the IR lowers `global.load` / `global.store` as before the big-int work.
- `bigcap.py` uses the module literal of a `global`-written variable for a constant power when no
  other unit (and no earlier store in the same function) can have replaced it. This keeps
  `e = 2; e **= 5` on the typed path instead of marking every exponent >= 4.
- Probes: `mv1.py` prints `2` with `AIL_NO_GENERAL=1`; `test_ail_globals` 32/32. `test_ail_bigint`,
  `test_ail_tint`, `test_ail_unified`, `test_ail_safetynet`, `test_ail_files` and
  `test_ail_corpus_findings3` pass. `test_ail_dunders`, `test_ail_nested_functions` and
  `test_ail_unbound` keep the same pre-existing failures as the base commit.
