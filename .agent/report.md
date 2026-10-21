## Report

**Commit** `063de90` on `job-modules2-10220558` (3 files: `ail_modules.py`, `test_ail_modules2.py` 388 lines/37 tests, `MANIFEST.json`). Working tree clean except the agent's own `.agent/` files.

**What I found.** The five listed behaviours were already largely modelled by `ail_modules.py` (relative imports at every depth, literal `__all__` incl. `+=`/`.append`, `import a.b as c` binding only the alias, per-module `__name__` with guard removal, one module per dotted name). I probed ~60 multi-file layouts against CPython 3.12 before changing anything; two real divergences surfaced, both in `from m import *`:

1. `from m import *` where `m` binds a name only through a function's `global X` → AIL emitted a copy of an unbound variable, so the importer died with `NameError` at the star line; CPython binds nothing (or binds it only if that function already ran). Now refused by name with `file:line`: "`from m import *`: m.py creates 'X' only inside a function (a `global` statement)…", `write instead:` present.
2. `import *` inside a function/class was silently compiled and run; CPython raises `SyntaxError: import * only allowed at module level`. Now refused by name at the statement (`main.py:2:5: … CPython raises SyntaxError …`).

Everything else I probed either matches CPython byte-for-byte or is refused by name with the user's `file:line` (entry-file/beyond-top relative imports, unreadable `__all__`, unimported submodule attribute, effectful function-level imports, star-then-rebind).

**Tests run on the final commit** (single `par_check.py -j 2`, 403 s, 0 failed): `test_ail_modules2` (new), `test_ail_modules`, `test_ail_multifile`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. `update_manifest.py --check` → rc 0.

**Probes** (`/tmp/probes/p_*`, run on both builds: `AIL_UNIFIED_FORCE=1` and default; `cmp.sh` copies a single file so I used an equivalent multi-file wrapper): 39 layouts, all matching CPython stdout or refused by name —
- relative: `p_rel_all`, `p_rel_sibling`, `p_rel_star`, `p_rel_star_parent`, `p_lazy_rel_ok`, `p_lazy_rel_effect`(refused), `p_rel_entry_refused`, `p_rel_beyond_refused`;
- `__all__`/star: `p_all_list`, `p_all_append`, `p_all_extend`, `p_all_reexport`, `p_all_pkg_sub`, `p_all_class`, `p_all_class_reexport`, `p_star_values`, `p_star_into_pkg`, `p_all_dynamic_refused`, `p_star_global_refused`, `p_star_in_func_refused`, `p_star_in_class_refused`;
- `import a.b as c`: `p_alias_basic`, `p_alias_deep`, `p_alias_state`, `p_alias_attr_dict`, `p_alias_namespace`, `p_alias_unimported_refused`;
- `__main__` guard: `p_guard_imported`, `p_guard_else`, `p_guard_skip_missing`, `p_guard_pkg`, `p_guard_entry_and_import`;
- same module twice: `p_twice_aliases`, `p_twice_spellings`, `p_twice_relative_abs`, `p_snapshot`.

**Not verified / caveats.** (a) This CI mirror contains no DEVLOG or DIFFERENCES file (`git ls-files` has neither), so I could not add entries to them; no `C?-<branch>-N` ids were needed since no behaviour is silently different any more — the two divergences are now refusals. (b) `test_ail_modules2` is not added to `tools/ci_shards.json` (`ci_shards.py --update` left the file unchanged; CI spreads unknown modules by name) nor to `ail_check.MODULES` — same as the existing `test_ail_multifile`. (c) A star import in an imported module's *nested* `if __name__ == "__main__":` is still refused (the guard is only flattened at top level); CPython skips that dead branch.
[cost $0.15, turns 101]
