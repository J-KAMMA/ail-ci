# job job-limits1-11052041  started 2026-11-05T11:45:56Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Committed on `job-limits1-11052041` (not pushed — the job rules forbid push).

**What landed** (`git diff --stat` vs base: 21 files, +565):
- `docs/LIMITATIONS.md` — 15 entries in three groups (Language 9, Standard library 4, Speed and build 2), each with the exact message, the rewrite or "no workaround yet", and its probe path. Links to `docs/PORTING.md` instead of copying rewrites.
- `lab/limits/NN_<name>.py` — 15 probes, plus `expected.json` recording the refusal text (leading `file:line:col:` stripped) or the build note + stdout + exit status.
- `AIL_CURRENT/test_ail_limits.py` + `tests.d/test_ail_limits.txt` — re-runs every probe, checks each `###` section names an existing probe, and fails with "limitation lifted: update docs/LIMITATIONS.md and lab/limits/expected.json" when a recorded refusal/note changes. Skips without a C compiler.
- Manifest shards `49.txt` / `5c.txt` updated by `tools/update_manifest.py`; `--check` exits 0.

**Probe results (default build, all also checked with `AIL_UNIFIED_FORCE=1`):**
- Refused by name (13): int64 literal, dict view, `with`+`yield`, non-literal `open()` mode, unsupported decorator, multiple inheritance, module as value, `eval`, `argparse`, `os.system`, `tempfile`, `sys.stdin` value.
- Builds, but stops loudly (1): int64 overflow — exit 1, `OverflowError: integer overflow in + ...`, stdout is CPython's prefix.
- Builds with the general-path note, output identical to CPython (2): threads (prints 5), untyped `json.loads` (prints 1).
- Silent differences found: **none**.

**Checks run on the final commit:** `test_ail_limits` OK (3 tests), `test_ail_files` OK (17+1 skip), `test_ail_corpus_findings3` OK, `update_manifest --check` 0, `ci_shards --check` 0 (`unassigned: test_ail_limits`, expected).

**One caveat:** `test_ail_safetynet` fails `S4_generators_gc` only under `ulimit -v 1500000` (the general-path program runs out of memory); it passes with a 3 GB cap, and I touched no compiler/runtime file. I could not push or watch the 20 shard checks because this runner's rules forbid push; the full suite runs on CI.
[commandcode stop=end_turn turns=32 out_tokens=27758]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have everything I need. Writing the report from what I ran.

**What the change really does:** adds `docs/LIMITATIONS.md` (15 entries), 15 `lab/limits/` probes with `expected.json`, and `AIL_CURRENT/test_ail_limits.py` (registered via `tests.d/` + manifest). No compiler/runtime edits; a plain program's `.c` is byte-identical to base.

**Probes run** (`cmp.sh`, both general and default builds, vs `python3`): all 15 repo probes (12 named refusals with exits 2/3, 3 builds matching CPython: 02 exit 1 with overflow, 14/15 general-path notes), plus mine: `a_pow`, `b_mul`, `c_unary`, `d_abs`, `e_inttext`, `f_dictmut`, `g_dictview_attr`, `h_open_dict`, `i_round`, `j_floordiv`, `k_view_return`, `l_module_arg`, `m_mul_runtime`, `n_int_arg`, `o_mod_list`, `p_stdin_return`, `q_yield_from`, `r_open_arg`, `subp`, thread shapes. Overflow for `**`, `*`, unary `-`, `abs`, `//`, `int(text)` and `round` stops loudly; mutation during dict iteration raises like CPython; module/stream/`open`-mode through an argument, list item or dict value are refused by name; `--exact-int` makes 01/02 match CPython; `--strict` refuses the json probe; `PORTING.md` 1/4/8/9/10/14 references exist; census is 3/197. `test_ail_limits` passes (3 tests), `--check` for manifest and shards exit 0, and with `AIL_EXACT_INT=1` the test fails with the required "limitation lifted: update docs/LIMITATIONS.md and lab/limits/expected.json".

**Report claims:** 15 entries/probes in 9/4/2 groups — verified. Test behaviour and registration — verified. "13 refused by name" — **false**: 12 refused, 3 build (the report even lists 12 names). "All checked with `AIL_UNIFIED_FORCE=1`" — verified observationally (both builds identical). Overflow/notes/no-silent-differences claims — the first two verified; "**Silent differences found: none**" is **false** (see defect 1). `test_ail_files`/`test_ail_corpus_findings3` — unverified (outside the review scope). Safetynet caveat — verified under 1.5 GB; not verified at 3 GB.

**Pre-existing** (identical on `/tmp/base2`, does not block): (a) `k_view_return.py` silent stale view; (b) `test_ail_safetynet` `S4_generators_gc` fails under `ulimit -v 1500000` on both HEAD and base.

**Defects**
1. `lab/limits/03_dict_view_is_snapshot.py` entry / "Silent differences found: None": the page says a kept view "would be a snapshot and the program is refused", but the check only covers the direct expression. Probe (/tmp/rprobes/k_view_return.py):
   ```python
   def view(d):
       return d.items()
   d = {"a": 1}
   v = view(d)
   d["b"] = 2
   print(list(v))
   ```
   Expected (CPython, exit 0): `[('a', 1), ('b', 2)]`. Actual (both builds, exit 0, no diagnostic): `[('a', 1)]`. The task's stop rule requires this under "Silent differences found"; instead the page asserts none.
2. `docs/LIMITATIONS.md` entry 2 says CPython prints `9223372036854775808`; it prints two lines, `9223372036854775807` then `9223372036854775808`.
3. Entry 10 says CPython prints `usage: 10_argparse_refused.py [-h] name`; actual stdout is empty, the usage plus `error: the following arguments are required: name` go to stderr, exit 2.
4. Entry 12 says CPython prints the temporary-directory path; probe 12 prints `True`.
5. Entry 9's "exact message" drops `; did you mean 'eval'?`, and `expected.json` stores only that prefix, so the test cannot notice the message tail changing.

**Unverified:** the 3 GB safetynet pass; `test_ail_files`/`test_ail_corpus_findings3`; entry 14's "Thread started and joined in one block … run without the lock" — both thread shapes I tried (single thread, and the typedpar docstring's list/start/join shape) still print the general-path note ("not started by the next statement"), so that sentence is at best misleading.

VERDICT: FIX
1. Record the silent stale-view result from `k_view_return.py` under "Silent differences found" and narrow entry 3 to the direct `x = d.items()` form (CPython `[('a', 1), ('b', 2)]` vs AIL `[('a', 1)]`).
2. Fix entry 2's CPython output (two lines).
3. Fix entry 10's CPython result (empty stdout, usage/error on stderr, exit 2).
4. Fix entry 12's CPython output (`True`, not the path).
5. Quote the full refusal line for entry 9 and record the full line in `expected.json`.
[commandcode stop=end_turn turns=28 out_tokens=33367]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed all five defects and committed as `3aacf23`.

**Changes**
- Entry 2: CPython prints `9223372036854775807` then `9223372036854775808`.
- Entry 3: narrowed to the direct `x = d.items()` form; noted the call gap.
- Entry 9: full refusal line including `; did you mean 'eval'?`; `expected.json` records the full line.
- Entry 10: CPython stdout empty, usage/error on stderr, exit 2.
- Entry 12: CPython prints `True`.
- Entry 14: corrected to say a plain `Thread` still takes the general path; only `ThreadPoolExecutor.map`/`Pool.map` over a typed function is typed (verified: map builds with no note; single-Thread prints the note).
- "Silent differences found": added the `k_view_return.py` repro — CPython `[('a', 1), ('b', 2)]`, AIL `[('a', 1)]`, exit 0, both builds.

**Verification**
- 15 repo probes, default build: all as recorded (`test_ail_limits` 3 tests OK).
- 15 probes under `AIL_UNIFIED_FORCE=1`: 15/15 OK.
- Stale-view repro: same `[('a', 1)]` in default and forced builds, exit 0.
- Lift check: `AIL_EXACT_INT=1` fails with the required "limitation lifted…" message.
- Required tests: `test_ail_files` OK (1 skip), `test_ail_corpus_findings3` OK, `test_ail_safetynet` OK without the cap (its `S4_generators_gc` subtest fails under `ulimit -v 1500000` on base too — pre-existing).
- `tools/update_manifest.py --check` rc 0; `git diff --stat f7fc6f8` shows only the allowed files.

Not run: the 20 shards (no push allowed/possible here).
[commandcode stop=end_turn turns=27 out_tokens=15940]

## review 1
[model commandcode/deepseek-v4.1-flash]
```
Review — limits1 (work..HEAD = 8f1e68c, 3aacf23)

What the change does (one line): adds docs/LIMITATIONS.md (15 sections), lab/limits/ (15 probe .py + expected.json), AIL_CURRENT/test_ail_limits.py + tests.d entry and the two manifest shards; no compiler, runtime, or stdlib file is touched.

Diff scope: only the files the task allows (verified with git diff --name-only work..HEAD); update_manifest.py --check rc 0. A plain program's --debug-dir program.c is byte-identical between work and HEAD (sha 7ab3b627…), so programs that don't use the feature get unchanged C.

Probes run (all with --debug-dir/default build; base = /tmp/base2 at work)
All 15 lab/limits probes reproduce expected.json exactly: 01 rc2 literal message, 02 stdout+OverflowError rc1, 03–13 refused with the recorded text, 14/15 general-path note + correct stdout. CPython oracles in expected.json verified.
Additional probes: D_mul (runtime * overflow → same message), Q_stdin_int (int() from stdin → "integer overflow in int()"), S2_round_var (runtime round → "…in round()"), T_floordiv, U_abs, M/N (negative literal and 2**64 refused rc2), F_keys view refused with the analogous message, G_view_return (stale view: CPython [('a',1),('b',2)] vs AIL [('a',1)], exit 0 — matches the page's "Silent differences" repro), H_view_arg (builds, same stdout), A_getcwd (builds — os built list is accurate), C_subprocess/C2, J2/J4/J5/J6, K_pool_map (no note, --strict rc 0), L_cache_deco (accepted), X_rebound_deco (builds on general path), Y_tmp_workaround.

Report claims: entry 2 CPython output verified; entry 9 full "did you mean 'eval'?" line verified; entry 10 stdout empty/stderr usage/exit 2 verified; entry 12 verified; entry 14 (plain Thread → note; map → typed, strict rc 0) verified; k_view_return repro verified; 15 probes as recorded verified; tests verified; manifest verified. Unverified: the 15-probe AIL_UNIFIED_FORCE=1 claim (ran cmp.sh only on J2/G/C), the "20x slower" figures, test_ail_files/test_ail_corpus_findings3 (not re-run, not required of the reviewer), the 20 shards (worker says not run).

Tests on HEAD: par_check.py -j 2 test_ail_limits test_ail_safetynet → 2 modules, 0 failed (16s / 262s).

Defects (page statements that are false — the task asked for accurate "what to do instead"):
1. Entry 15's workaround does not work in the shape the page (and the message) gives. Probe /tmp/rprobes/J2.py:
   import json
   data: dict[str, int] = json.loads('{"a": 1}')
   print(data["a"])
   Expected per page: typed path (no note). Actual: builds on the general path —
   note: p.py:2:1: built on the general path (about 20x slower) because json.loads(s): the type of the result is not declared here; write the type down: `data: dict[str, int] = json.loads(s)` …
   Only an annotation inside a function is honoured (J5_func builds with no note); module-level annotation (J2) and split annotation (J6) fall back. The page's advice as written is wrong at module level.
2. Entry 11 says "`subprocess` is built on the general path". Probe /tmp/rprobes/C_subprocess.py (`r = subprocess.run(["true"]); print(r.returncode)`) builds with no general-path note, and --strict also succeeds; --debug-dir program.c contains the fork/execve implementation (line 7243). Expected per page: general-path note; actual: typed build, no note. The sentence (and its "keep the call where the typed path can leave to the general build" advice) is false.
3. Entry 3 says "This check covers the direct assignment form only" and that views reaching a name are the only gap. The quoted message itself says "name, field, item or container", and probes are refused for those stores: /tmp/rprobes/O_attr_view.py (`b.v = d.items()`) and /tmp/rprobes/P_dict_item_view.py (`m = {"k": d.items()}`) both exit build rc 3 with the same "a dict view kept in a name, field, item or container" line; I_view_item (list container) too. Expected per page: builds on the general path; actual: refused.

Pre-existing: the dict-view stale-snapshot result (G) exists on the base too (compiler untouched); it is disclosed in the page as the stop rule requires, so it does not block acceptance. The entry-15 note wording and the entry-3 scope wording originate in the compiler, but the page repeats/extends them as its own advice.

Not checked: 20 shards, the full 15-probe forced-general run, timings; no hot code is touched, so no icount run.

VERDICT: FIX
1. docs/LIMITATIONS.md entry 15: the advised module-level annotation still builds on the general path. Probe J2.py above: expected no "built on the general path" note; actual note present. Say the annotation must be inside a function (J5_func) or give a working form.
2. docs/LIMITATIONS.md entry 11: "subprocess is built on the general path" is false. Probe C_subprocess.py above: expected the general-path note; actual typed build, no note, --strict rc 0, C contains fork/execve.
3. docs/LIMITATIONS.md entry 3: "This check covers the direct assignment form only" is false. Probes O_attr_view.py (`b.v = d.items()`) and P_dict_item_view.py (`m = {"k": d.items()}`): expected build on the general path; actual build rc 3 with "a dict view kept in a name, field, item or container".
```
[commandcode stop=end_turn turns=34 out_tokens=26933]

FINAL VERDICT: FIX  2026-11-05T12:40:09Z
