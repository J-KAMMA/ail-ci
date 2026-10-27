# job job-pre360-10280242  started 2026-10-27T17:44:04Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"767759dd-0938-47eb-8190-382859db7645","context_usage_ratio":0.019626},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"1ef6575f-0887-4eff-a3b9-15e9abb83b3d","session_id":"1bc035fc-bac2-45aa-b9c0-2033bd875587"}

## worker report 0
[model qoder/DeepSeek-Flash]
Committed. Final report:

**What was reproduced.** Of the two unverified items, `test_ail_files` still passes unchanged (144 s, 0 failed). The first real difference was the textwrap corpus-findings item: `textwrap.wrap("a-b", 2)` (also `fill`, and any literal with a tab) compiled then stopped with `RuntimeError: textwrap: text with a hyphen or a tab is not built` on both builds, where CPython prints `['a-', 'b']`.

**Fix.** `_ail_tw_wrap` (AIL_CURRENT/ail_syntax.py) now runs CPython 3.12's default TextWrapper algorithm: `expandtabs(8)` with the column reset on `\n`/`\r`, whitespace translation, the `wordsep_re` whitespace/em-dash/hyphen chunking (including its two-word-char lookahead) and `_handle_long_word`'s rfind-hyphen break with the `space_left = 0` case; `width <= 0` keeps CPython's `ValueError` text. Fuzzed in CPython against `textwrap` first: 50,000 random texts (spaces, tabs, newlines, hyphens, em-dashes, digits, accented/CJK/superscript) and 30,000 more in a second sweep, widths 1–12 and 70: 0 mismatches. A no-feature program's `program.c` is byte-identical to the `work` worktree.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, general + default build):
- `p14` hyphen/tab literals: differed before; now same stdout/exit on both.
- `p15` argument, list item, class attribute, instance attribute, dict value, mutation, class-attribute read: both match.
- `p16` empty, whitespace-only, leading/trailing, widths 1/2/5/70, em-dash, digits around hyphens, `é`, tab columns, long words, `fill`: both match.
- `p17` width 0/-1/-70: caught `ValueError` text matches, both.
- `p01`, `p02`, `p07`–`p12` (newline modes, seek/tell, x/`a+`, readline, UTF-8 read, corpus builtins, strip/dedent): both match. `p03`–`p06`, `p13`: refused by name (pre-existing, untouched).
- Instruction counts **not** measured: `perf_event_paranoid` is 4.

**Tests on the final tree:** test_ail_pre360 (new, 5 tests), test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 — 4 modules, 297 s, 0 failed. DEVLOG/DIFFERENCES updated; `update_manifest.py` run and `--check` passes. Commit `07e2ff2` on `job-pre360-10280242` (1 file beyond the tested tree: the DEVLOG entry).

## review 0
[model qoder/DeepSeek-Flash]
**Review of `07e2ff2` (pre360, textwrap hyphen/tab)**

**What the change really does (one line):** it replaces the `RuntimeError` refusal for hyphen/tab text in `_ail_tw_wrap` (AIL_CURRENT/ail_syntax.py:1218) with a hand-rolled port of CPython 3.12.3's default `TextWrapper` — `expandtabs(8)` with `\n`/`\r` column reset, ASCII-whitespace translation, the `wordsep_re` whitespace/em-dash/hyphen chunker (incl. the `letter = [^\d\W]` two-char lookarounds) and `_handle_long_word`'s rfind-hyphen break — plus the `_SMALL_NOTE`/DIFFERENCES/DEVLOG/registration records. That matches the report.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, both builds), all CPython-3.12.3-identical stdout+exit:
- `p1`: 133 wrap/fill cases over 19 texts × 7 widths — hyphen runs, em/en-dash, NBSP, `a-bc-de`/`ab-cd-ef` split points, 12-char word + `-b` (the `space_left = 0` path), `-a`, `a-`, accented text. (Base: `RuntimeError: text with a hyphen or a tab is not built` — the pre-existing gap, now gone.)
- `p2`: Unicode decimal digits (U+0663/١٢), superscript `²`, CJK, combining mark, accented letters × widths 1–5 — exercises `isdecimal`/`isalnum`/`\w`-vs-`\d` boundaries; matches base's `RuntimeError` is replaced by CPython-equal output.
- `p3`: argument, list item, class attribute, instance attribute, dict value, mutation, `ValueError` text for 0/−1.
- `p5`: tab columns across `\n`/`\r`/`\x0b`/`\x0c`, leading whitespace, `fill`.
- `p4`: no-feature program — `--debug-dir` `program.c` byte-identical to `/tmp/base` (verified; helpers are emitted per use).

Additionally I differentially fuzzed the generated helper against `textwrap.wrap` in CPython: 350k cases (350k = 200k + 150k sweeps), alphabet including `-`, `--`, `!"'&.,?`, `_`, tabs/newlines/CR/VT/FF, U+00A0, U+2003, U+0301, `٣`, `²`, `é`, CJK, widths 1–12/70 — 0 mismatches.

**Tests on HEAD:** `test_ail_pre360` + `test_ail_safetynet`, 2 modules, 140 s, 0 failed. `tools/update_manifest.py --check` exits 0.

**Report claims:** algorithm description, "program.c byte-identical", "hyphen/tab item reproduced and fixed", and the route/boundary/width coverage are **verified** (by my own probes). Their fuzz numbers, their p01–p17 probe list, and "test_ail_files passes unchanged (144 s)" are **unverified** here (I did not rerun); the `test_ail_corpus_findings3` edit is docstring-only.

**Pre-existing:** none found in my probes.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` runs; instruction counts — `perf_event_paranoid` is 4 (confirms the report), and no `~/corpus/gdev` or `bench/apps` program uses textwrap, so icounts are unaffected.

No defect found.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T20:18:00Z
