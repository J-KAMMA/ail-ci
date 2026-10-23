# job job-fuzz50-10231204  started 2026-10-23T03:05:53Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Result:** committed `0a25d1b` on `job-fuzz50-10231204`.

**First difference:** `dc11` — `a.x = 5` on `@dataclass(frozen=True)` printed `A(x=5, y=2)` on both builds; CPython raises `FrozenInstanceError`. `dc12` (`+=`) and `dc16` (direct store in `__post_init__`) were the same cause.

**Fix:** compile-time refusal in `AIL_CURRENT/ail_syntax.py` (`check_frozen_stores`). Field writes are refused by name for every receiver; `self.f` in a non-frozen class and `object.__setattr__` in `__post_init__` stay allowed.

**Probes (`~/tools/cmp.sh`, both builds):**
- Refused by name: `dc11`, `dc12`, `dc16`, `dc24` argument, `dc25` list item, `dc26` dict value, `dc27` nested field, `dc28` `setattr`/`delattr`, `dc30` `dataclasses.dataclass`, `dc31` alias, `dc33` inherited field.
- Matched CPython: `dc01`–`dc10`, `dc14`, `dc18`–`dc21`, `dc23`, `dc29`, `dc32`.
- Already refused on base: `dc13` `del`, `dc15` missing arg, `dc17` non-default order.
- Over-refused by the name rule (named refusals): `dc34` mutable class with the same field name written externally, `dc35` class attribute write `A.x = 9`.
- Still a pre-existing silent difference: `dc22` non-field write `a.extra = 7` on a frozen instance (both builds print the value; CPython raises `FrozenInstanceError`).

**Tests (final commit):** `test_ail_fuzz50` 5/5; required batch `test_ail_fuzz50, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3, test_ail_genlib, test_ail_python_syntax, test_ail_dunders, test_ail_multifile` = 8 modules, 0 failed (273s). `test_ail_silent6.DataclassEqTests` 5/5. Full `test_ail_silent6` has a pre-existing G17 failure (`Lambda` has no `lineno` in `pyboxed2`), reproduced with the original `ail_syntax.py`.

**Manifest:** `update_manifest.py` run; `--check` exit 0. No `DIFFERENCES.md`/`DEVLOG.md` exist in this export, so no record entries were added.
[cost $0.0000, opencode tokens {"total": 8228412, "input": 294777, "output": 19850, "reasoning": 34489, "cache.write": 0, "cache.read": 7879296}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `0a25d1b` (diff: `check_frozen_stores` in `ail_syntax.py`, new `test_ail_fuzz50.py`, manifest).

**Probes** (`cmp.sh`, general + default; base compared where relevant):
- `direct_frozen`, `post_init_direct`: both builds refuse by name; CPython raises. **OK**
- `factory_frozen`: list/dict mutation allowed, field reassign refused. **OK**
- `frozen_expr` (`frozen=FLAG`), `setattr_var` (non-constant name), `subclass_nonfrozen` (`B(A)` writing `self.x`), `dc22_nonfield`: both builds silently assign; **identical on base** -> pre-existing.
- `over_ext` (`m.x` on a plain mutable class while frozen `A` also has `x`), `frozen_class_attr` (`A.x = 9`), `samesrc` (mutable `Q.x` alongside frozen `P.x`): HEAD refuses by name; base compiles/runs. Over-refusal introduced, but loud, named, and disclosed.

**Claims:** commit/fix location verified. `self.f` in a non-frozen class allowed, `object.__setattr__` works, dc22 pre-existing, dc34/dc35 over-refused - verified. Claim "every receiver" is **false** for a non-dataclass subclass of a frozen class (`subclass_nonfrozen` still silent, but base is identical). Manifest `--check` exits 0; no DEVLOG/DIFFERENCES files.

**Tests:** `test_ail_fuzz50` + `test_ail_safetynet` pass; also re-ran `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_genlib`, `test_ail_python_syntax` (all ok, -j 2). Generated C for `g14_024` and a plain program is byte-identical to base (only debug paths differ), so no runtime/speed change.

Pre-existing (non-blocking): `frozen_expr`, `setattr_var`, `subclass_nonfrozen`, non-field writes on frozen instances. The name-only rule also rejects valid writes to unrelated mutable objects, but all such cases are named refusals.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1269284, "input": 64535, "output": 6657, "reasoning": 21644, "cache.write": 0, "cache.read": 1176448}]

FINAL VERDICT: ACCEPT  2026-10-23T03:43:31Z
