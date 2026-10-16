# AIL syntax A/B lab

Goal: choose AIL syntax variants by measurement. A language meant to be written by LLMs should
maximise **first-try pass rate** per **token spent**. Generation is done by hand with free models
(for example GLM or DeepSeek in OpenCode). GitHub Actions compiles, tests and scores whatever is
committed under `runs/`. No API keys exist anywhere in this repository or its workflows.

## Layout

```
lab/syntax/
  variants.json        variant list; status "supported" or "mockup"
  prompts/             _common.md (shared rules) + one notes file per variant
  tasks/<task>/        statement.md, tests/<n>.in, tests/<n>.out   (13 small tasks)
  runs/<model>/<variant>/<task>/attempt1.ail   + meta.json         (submissions)
  make_prompt.py       builds the self-contained prompt for a (variant, task)
  save_run.py          stores a reply as a submission
  score.py             compile, test, count tokens, write the Markdown table
```

Tasks cover numeric loops (`collatz_steps`, `prime_count`, `fib_mod`), lists (`running_max`,
`rotate_list`, `dedup_sorted`), dicts (`word_freq`, `group_sum`), strings (`caesar`,
`palindrome_lines`), records (`inventory_report`, `bank_ledger`) and errors (`safe_sum`,
`bank_ledger`). Tests feed stdin and compare stdout (trailing whitespace ignored); the exit
status must be 0.

## Variants (round 1: type annotations)

| variant | style | status |
|---|---|---|
| `ail-brace` | current AIL: `fn f(a: int) -> int { }`, `let x: int = 0;` | supported |
| `pep484` | Python surface: `def f(a: int) -> int:`, `x: int = 0`, `@dataclass` | supported (the compiler accepts it today) |
| `ts-like` | `fn f(a: int): int { }` | **mock-up**: the compiler rejects it (`invalid fn header`), so it is never scored |

A mock-up may still be prompted and committed under `runs/`; the scorer lists it as skipped. To
add a variant: write `prompts/<name>.md`, add it to `variants.json`, and mark it `mockup` until
the compiler accepts it. Keep the notes equivalent in content across variants (same facts, only
the syntax differs) so the comparison measures syntax, not documentation.

## Scoring

`python3 lab/syntax/score.py [--include-samples] [--out table.md] [-j 4]` compiles each
`attempt1.ail` with `AIL_CURRENT/ail_chatgpt.py compile`, runs every test (10 s limit per
test, CPU and memory limits), and writes a Markdown report. Verdicts: pass, compile-error,
wrong-answer, runtime-error, timeout. Only the first attempt counts; a missing task is simply
"not submitted" (the table shows `submitted/total`).

Per (model, variant): pass rate, mean tokens, **tokens per pass** (all tokens spent divided by
passes; lower is better) and **pass per 1k tokens** (pass rate x 1000 / mean tokens; higher is
better). Tokens are an approximation with a simple documented tokenizer (see the top of
`score.py`): words about 6 characters per token, digits 3 per token, each punctuation
character or two-character operator 1, a newline plus its indentation 1, single spaces free.
It is the same for every variant, so it ranks fairly, but it is not a billing count. If you
know the real output tokens, pass `--tokens` to `save_run.py`; they appear in an extra column.

Samples live in `runs/_sample/` (directory starts with `_` and `meta.json` says `"sample": true`).
They exercise the pipeline (two passes, one deliberate wrong answer, one mock-up) and are
excluded from real results; CI scores them in a separate step, labelled as a pipeline check.

CI runs `.github/workflows/syntax-lab.yml` on pushes and pull requests that touch
`lab/syntax/**`, and on manual dispatch. It uploads the table as the `syntax-scores` artifact and
shows it in the job summary. It runs submitted programs, so it has read-only repository access,
no secrets, and per-test limits.

Fairness rules for generation: one fresh session per (variant, task); paste only the prompt; take
the first reply; do not fix or retry; use the same model settings for every variant.

## 日本語: OpenCodeでの手順

1. プロンプトを作る(リポジトリの外に出す)。
   `python3 lab/syntax/make_prompt.py --all ~/syntax-prompts`
   `~/syntax-prompts/<variant>/<task>.md` ができる(`ts-like` は対象外)。1件だけなら
   `python3 lab/syntax/make_prompt.py pep484 caesar`。
2. OpenCodeを **空のディレクトリ** で開く(このリポジトリの中で開かない。他のタスクや提出物を
   モデルに見せないため)。モデル(GLM、DeepSeekなど)を選ぶ。
3. 1つのプロンプトごとに **新しいセッション** で、`.md` の中身をそのまま貼る。最初の返答だけを
   使う(直させない、やり直さない)。バリアント間で設定(温度など)を揃える。
4. 返答のコードをファイルに保存して取り込む。
   `python3 lab/syntax/save_run.py glm-4.6 pep484 caesar --file reply.txt --tokens 412`
   (`--tokens` は表示されていれば。`--file` を省くと標準入力から読む。コードフェンスは付いたままでよい。)
   保存先は `lab/syntax/runs/<モデル名>/<variant>/<task>/attempt1.ail` と `meta.json`。
   既にあると上書きしない(初回だけを数えるため)。
5. 手元で採点するなら `python3 lab/syntax/score.py`。
6. コミットして push、PRを開く。
   `git add lab/syntax/runs && git commit -m "runs: glm-4.6 pep484" && git push`
   Actionsの `syntax-lab` が走り、ジョブのSummaryと成果物 `syntax-scores` に表が出る。
   全バリアント×全タスクは 2 variant × 13 task = 26回/モデル。
