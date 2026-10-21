Done. Summary of the work and verification:

**Fuzz run:** 117 small exception programs (`/tmp/fz/p01–p112`, `q1–q5`) plus 13 probes in `/tmp/probes/`, each run with `bash ~/tools/cmp.sh` (both builds) against CPython 3.12.

**Fixed causes (2):**
1. **Boxed `repr()` of a KeyError double-quoted the message** (`KeyError("'k'")` vs `KeyError('k')`; hit `raise KeyError(s)`, KeyError from a missing dict key, KeyError raised in `__exit__` and re-raised by `@contextmanager`). The runtime stores `repr(key)` as a KeyError's message (correct for `str(e)`), so `cruntime`'s exception-repr now writes a KeyError's message as-is, and `safetyrt.patch_exc` keeps that when it prints `args`.
2. **`assert cond, 5` lost the message object** (`repr(e)` was `AssertionError('5')`, `e.args == ('5',)`): `pyfunc._assert_stmt` now builds `AssertionError(msg)` with the object, and `pyboxed2` keeps it via `ail2x_raise_builtin`. Fixed on both builds for int/negative/huge/float/bool/None/str.

**Tests:** new `test_ail_fuzz7.py` (5 tests / 24 builds: the fixed KeyError and AssertionError cases + a 11-program ordering/with/contextmanager guard), registered in `ail_check.py`. On the final commit `c6a95b6`: test_ail_fuzz7, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3, test_ail_exc_str, test_ail_exception_context, test_ail_exception_values_app/_core/_resources/_aggregate_objects, test_ail_reraise, test_ail_raise_from, test_ail_silent5, test_ail_fuzz_findings, test_ail_record_initializers, test_ail_numeric_bindings — all OK. (`test_ail_fuzz1` has 2 environment-only failures: `tools/difffuzz.py` is not in this export; unrelated.) `update_manifest.py` run, `--check` exit 0.

**Probes (all with cmp.sh, both builds):** `key_repr_raise` (keys via variable/list item/dict value/attribute, empty/quote/backslash/negative/tuple/None), `key_repr_missing`, `key_repr_exit`, `key_repr_cm`, `key_repr_args`, `ke_subclass_str`, `ke_bytes`, `assert_args_types` (int 0/negative/1e6/float/bool/None/empty str, via function argument), `assert_args_places` (list item, dict value, attribute), `assert_int_after`, `assert_int_after2/3`, `ass_float` — all match CPython on both builds **except** `assert_int_after{,2,3}`: typed-path `e.args[0]` is always a str (`"1.5" * 2`), identical on the base commit (residual, see below).

**Residual causes (not fixed, listed as required):**
1. Eager message/`__str__` at raise: `__str__` side effects/order (p49), a non-str `__str__` escaping the handler (p37), `e.args = ...` after construction not changing `str(e)` (p96 builtin args assignment, p106 user/builtin) — the eager evaluation is documented in `userexc.py`.
2. `e.args[i]` on the typed path is always a str, whatever the real argument type.
3. Boxed KeyError from a missing dict key still carries no args: `e.args[0]` is the quoted message (repr is fixed).
4. Bare `raise` with no active exception re-raises the last exception instead of `RuntimeError: No active exception to reraise` (needs thread-global handled state the boxed path does not keep).
5. `__del__` is accepted but never run at exit (p34).

**Records:** this export contains no `DEVLOG`/`DIFFERENCES` file (`git ls-files` shows only `AIL_CURRENT/docs/IR_DESIGN.md` under docs), so I did not invent those paths to avoid an add/add conflict on merge; the two fixed causes and the residuals above are documented in the `test_ail_fuzz7.py` docstring. No push/stash/rebase/reset; single commit on `job-fuzz7-10220552`.
[cost $0.34, turns 181]
