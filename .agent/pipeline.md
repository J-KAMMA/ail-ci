# job job-limits1-11052304  started 2026-11-05T14:14:56Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Report

Fixed all three FIX defects in `docs/LIMITATIONS.md` (docs-only; no compiler touched). Committed as `5edfe93`.

**Defects verified against current code, then corrected:**

1. **Entry 15** — `J2.py` (module-level `data: dict[str, int] = json.loads(...)`) still emits `built on the general path` (rc 0). Page now says only an annotation *inside a function* works: annotated local (`J5`/`F3` build typed, no note), annotated parameter (`F2` typed), or annotated return type (`F1` typed). Module-level annotation is stated to fall back.
2. **Entry 11** — `C_sub.py` (`subprocess.run(["true"])`) builds typed, no note, `--strict` rc 0, C contains fork/execve. Replaced the false "general path" sentence with `subprocess.run` / `check_output` on the typed path; noted `Popen` is refused (`C4` rc 3).
3. **Entry 3** (+ the same false claim in "Silent differences") — `O_attr.py` (`b.v = d.items()`), `P_item.py` (dict literal), `Q_item.py` (item store), `I_list.py` (list literal) all refuse rc 3 with "name, field, item or container". The genuine gap is now described correctly: `f(d.items())` (`H_arg2`) and a returned view (`G_ret`) build on the general path with the `dict.items used as a value` note.

**Tests:**
- `test_ail_limits`: 3 tests OK (16.3s).
- `test_ail_safetynet`: 5 tests OK (188s) when run without the 1.5 GB cap; under `ulimit -v 1500000` it fails `S4_generators_gc` because the general-path interpreter runs out of memory (environmental, not caused by this docs change).
- `tools/update_manifest.py` and `--check`: rc 0, no manifest change.

**Diff:** `docs/LIMITATIONS.md` only (+18/−13); 15 probes and 15 entries unchanged.
[commandcode stop=end_turn turns=24 out_tokens=12401]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review — limits1 (work..HEAD = 5edfe93)

**What the change does (one line):** edits only `docs/LIMITATIONS.md` (+18/−13) to correct the three false entries 15, 11 and 3 (and the matching "Silent differences" sentence); no compiler, runtime, probe or test file changes.

**Diff scope:** `git diff --name-only work..HEAD` = `docs/LIMITATIONS.md` only; `update_manifest.py --check` rc 0. A plain program's `--debug-dir program.c` is byte-identical between work and HEAD (`8deba9a5…`).

**Probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh … $PWD`; base = `/tmp/base` at `work`)
- Entry 15: `J2.py` module-level `data: dict[str,int] = json.loads(...)` → general-path note, `--strict` rc 3. `J5_func.py`, `F2_param.py`, `F1_ret.py` (local / parameter / return annotation) → no note, `--strict` rc 0, CPython match. New wording exact.
- Entry 11: `C_sub.py` builds typed, no note, `--strict` rc 0, matches CPython; `program.c` contains fork/execve (4 hits). `C4_popen.py` refused rc 3 with "subprocess.Popen is not built". `K_checkoutput_text.py`/`K3_run_text.py` (text=True) typed, strict rc 0. Caveat: `check_output([...])` without `text=True` is a *named refusal* ("subprocess output or input as bytes"), not a typed build — a named refusal, not a wrong output.
- Entry 3 + silent differences: `O_attr.py` (`b.v = d.items()`), `P_item.py` (dict literal), `I_list.py` (list literal), `N_itemstore.py` (`m["k"] = d.items()`) all rc 3 "a dict view kept in a name, field, item or container". `H_arg2.py` (`f(d.items())`), `L_callstore.py` (stored inside the callee) and `G_ret.py` (returned view) build on the general path with the `dict.items used as a value` note; `G_ret` prints `[('a', 1)]` vs CPython `[('a', 1), ('b', 2)]`, exit 0 — exactly as the page now says.
- `O_fork.py` → "os.fork is not built", as the new entry-11 sentence states.
- `plain.py` matches CPython in both builds.

**Tests on HEAD** (`ulimit -v 1500000`, `par_check.py -j 2 test_ail_limits test_ail_safetynet`): `test_ail_limits` passed; `test_ail_safetynet` failed only `S4_generators_gc` (OOM of the general-path interpreter under the 1.5 GB cap). Re-run without the cap: `1 modules in 188s, 0 failed` — environmental, as reported.

**Report claims:** 1–3 verified; test_ail_limits 3 tests verified; safetynet cap behaviour verified; manifest rc 0 verified; "docs only +18/−13" verified. Nothing false.

**Pre-existing:** the `G_ret` stale view (CPython `[('a', 1), ('b', 2)]` vs AIL `[('a', 1)]`) reproduces on `/tmp/base`; disclosed on the page as the stop rule requires.

**Unverified:** nothing material. No icount run needed — compiler/runtime untouched, so instruction counts cannot change.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=32 out_tokens=11070]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T15:48:16Z
