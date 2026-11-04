# job job-porting1-11050047  started 2026-11-04T15:52:11Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Commit `1be17d2` on `job-porting1-11050047`; not pushed (the runner rules say "do not push", and pushing is listed as forbidden).

## What landed

- `docs/PORTING.md` — intro (CPython-output-or-refusal rule, refusal shape, `--strict`, general-path note) plus **14** entries, each with the exact refusal text (`prog.py` path), a `before` program, a natural `after` rewrite, and why.
- `AIL_CURRENT/language_examples/porting/` — 28 files (`<name>_before.py` / `<name>_after.py`).
- `AIL_CURRENT/test_ail_porting_docs.py` + `AIL_CURRENT/tests.d/test_ail_porting_docs.txt` (registered via `tests.d`, not the `ail_check.py` tuple).
- Manifest shards `63.txt`, `bb.txt`; `tools/update_manifest.py --check` passes.

## Verified

- All 14 `before` programs refused in the default build: 11 exit **3**, 3 exit **2** (`mixed_import`, `import_assigned`, `int_beyond_int64`).
- All 14 `after` programs build in the default mode and match CPython 3.12 stdout + exit status (also checked standalone in `/tmp/final` before wiring the test).
- `test_ail_porting_docs`: 4/4 pass (~20–40 s, builds at most 2 at a time).
- Required modules: `test_ail_files` OK (18, 1 skip), `test_ail_corpus_findings3` OK (2). `test_ail_safetynet` OK **without** the memory cap; under `ulimit -v 1500000` its `S4_generators_gc` OOMs (it allocates ~2M strings), which is the cap, not a regression.
- `git diff --stat 20a55a3` shows only the allowed files (33 files, 855 insertions).
- CI shards were not run: no push.

## Findings for the PR description (couldn't open it)

Refusals with no `file:line:` prefix:
- `not in the subset: a dict view kept in a name, field, item or container (`x = d.items()`, line 3): ...` (also truncated mid-word at 657 chars)
- `not in the subset: the decorator on def bump (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)`
- `not in the subset: a required keyword-only parameter name in def greet (this cut requires every keyword-only parameter to have a default)`

Confusing / no useful hint:
- `print_value`: `print_value_before.py:2:5: not in the subset: 'print' is read before it is assigned (the general path could not build this program either); general path: name 'print' is not defined` — `print` is a builtin, not "undefined" or "unassigned".
- `type_as_value`: `... call to type(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one ...; general path: the name 'type' is not a known function/class/builtin; did you mean 'type'?` — the hint repeats the name; no mention of `isinstance`.
- A module read through a local alias: `module_value_before.py:5:5: not in the subset: 'math' is read before it is assigned (the general path could not build this program either); general path: the module math used as a plain value` — misattributes the module read to the alias under assignment.
- `os_stat`: the first stderr line is truncated mid-word at 619 chars (`... split splitext absp`), with the "(the general path could not build this program either); general path: ..." suffix duplicating the whole message.
- `nested_class`, `module_value`, `caught_non_exception`, `keyword_only`: refusal names the construct but gives no rewording hint.

Non-refusal notes seen while probing (not in the page):
- `class_const_list_item` general-path note exposes a mangled symbol: `because 'Box__SIZE' is a module-level name assigned to a Subscript ...`.
- `starred_call_arg` general-path note gives a wrong reason: `because add() is missing a value for argument 'b'` for `add(*args)`.

## Dropped candidates (built, so not refusals)

`with` around `yield`, `*args`/starred call, class-level constant from a list item, `import re; re = 1`, local import inside a function, `match`, `global`, f-string `=`: all compile via the general path today, so they don't fit "refused in the default mode".
[commandcode stop=end_turn turns=47 out_tokens=43850]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does:** adds `docs/PORTING.md` with 14 refusal/rewrite pairs, 28 example programs under `language_examples/porting/`, a docs-consistency test registered through `tests.d`, and the matching manifest pins. No compiler, runtime or stdlib file is touched — the diff matches the report.

**Probes** (all in `/tmp/rprobes`, `bash ~/tools/cmp.sh <probe> $PWD`):

| Probe | Result |
|---|---|
| all 14 `*_after.py` programs | general path + default build both exit 0 and match CPython stdout |
| `nofeature.py` (feature unused) | generated `program.c` identical HEAD vs `/tmp/base` when built in the same dir |
| `kwdefault.py` (`def greet(*, name="ada")`) | builds on the default path and matches CPython — supports entry 6's claim |
| `multiblock.py` (two blockers, `--strict`) | lists both blockers, each with `write instead:` — supports the intro claim |
| `isinstance_note.py` | matches CPython both paths |

I also compiled all 14 `*_before.py`: 11 exit 3, 3 exit 2 (`mixed_import`, `import_assigned`, `int_beyond_int64`); each first stderr line contains the documented text, and the base compiler gives the same refusal (refusals are pre-existing, not introduced).

**Tests:** `par_check.py -j 2 test_ail_porting_docs test_ail_safetynet` → both ok, 0 failed. Manifest `--check` exits 0. `git diff --name-only work..HEAD` contains only the allowed paths (33 files, 855 insertions).

**Report claims:** entry count 14, 28 files, before-refusal counts, after-matches-CPython, test pass, manifest pins, and scope are all **verified**. `test_ail_files`/`test_ail_corpus_findings3` results are **unverified** (not rerun per review scope). CI shards and the 1.5 GB OOM remark are **unverified** (nothing pushed).

**Non-blocking documentation imprecision:** entry 2 says “Split it into one line per module, as the message's `write instead:` line says”, but the actual hint is “one `import` line for the local modules”. Entry 12's “`isinstance(value, int)` says the same thing” is exact only for non-bool ints (`type(True) is int` is `False`, `isinstance(True, int)` is `True`); the shown probe is correct.

No defect caused by the change; no pre-existing output differences found.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=27 out_tokens=29985]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T17:41:25Z
