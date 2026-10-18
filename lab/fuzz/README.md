# AIL differential fuzz lab

AIL promises the same result as CPython, or a named compile-time refusal. A refusal is fine; a
silent difference is a bug. This lab looks for silent differences.

- `gen.py` (stdlib only): `python3 gen.py SEED` prints one random, typed Python program. The same
  seed always gives the same program. It covers 64-bit int arithmetic (including overflow toward
  2**63), floats and their printing, str and bytes operations, f-strings and `%` formatting, lists
  (including `ys = xs` aliasing and mutation), dicts, sets, try/except/else/finally, while/for with
  break/continue, helper functions with recursion, and dataclasses (also aliased).
- `run.py`: for a seed range, generate, run with CPython, compile and run with
  `AIL_CURRENT/ail_chatgpt.py` twice (default path and `AIL_IR=1`), and classify each pair.
- `.github/workflows/fuzz-lab.yml`: runs it daily on 4 parallel shards (`ubuntu-24.04`, read-only
  permissions, no secrets). A red run means at least one DIFF or crash.

```
python3 lab/fuzz/run.py --start 0 --count 50 --out fuzz-out [--jobs 1] [--modes default,ir]
```

## Classes

| class | meaning | fails the job |
|---|---|---|
| same | stdout and exit code equal | no |
| refused | the AIL compiler refused with a named reason (exit 3) | no |
| overflow | AIL raised `OverflowError` where CPython grew a big int; stdout so far must be a prefix of CPython's. Declared: AIL `int` is 64-bit | no |
| timeout | the program or compiler hit the time limit | no |
| skipped | CPython itself timed out or printed too much | no |
| **DIFF** | stdout or exit code differ silently | **yes** |
| **crash** | compiler failure that is not a refusal, or the binary died on a signal | **yes** |

`--off alias,listeq,stridx` switches generator features off (list aliasing, `xs == ys`, out-of-range `s[i]`), for example to look
past a known bug that would otherwise turn every run red; the workflow has the same `off` input.

## Output

`fuzz-out/summary.md` (counts per mode, findings, top refusal reasons), `fuzz-out/results.jsonl`
(one record per seed and mode), and for every DIFF, crash or timeout a directory
`fuzz-out/findings/seedN-MODE-CLASS/` with `prog.py`, both outputs, `info.json` and `reproduce.sh`.
CI uploads these as artifacts (30 days).

## Declared differences the generator avoids

- Set iteration order: sets are only observed through `sorted()` or order-free reductions.
- Printing lists or tuples (AIL refuses it); lists are observed through `len`, `sum`, indexing.
- `OverflowError` is never caught by a generated program, so an overflow ends the run and is
  classed `overflow` instead of producing a spurious DIFF.

Generated programs are also shaped to stay inside the forms AIL builds (annotated names, one type
per name, no `for ... else`, simple f-string specs), so that most seeds exercise the compiler
instead of being refused. The refusal rate is reported in every summary.

## Findings so far (minimal reproductions)

Found by the first local runs; each reproduces with CPython versus both AIL modes.

1. List aliasing is a copy. `ys: list[int] = xs; ys.append(3)` leaves `xs` unchanged in AIL
   (CPython: `xs` sees the append; prints `3 3`, AIL prints `2 3`). Also `ys[0] = v`, `sort`, `reverse`.
2. `IndexError` from indexing a str is not catchable. `try: s[3]  except IndexError: ...` with
   `s = "abc"` exits 1 with `string index out of range` in AIL; CPython takes the handler.
3. `xs == ys` on two `list[int]` passes the type check and then fails in the C compiler
   (`incompatible types ... from type ail_list`, compiler exit 4) instead of a named refusal.

Use `--off alias,listeq,stridx` to look past these three.

## Reproducing a finding

```
python3 lab/fuzz/gen.py SEED -o prog.py && cp prog.py prog.ail
python3 prog.py
AIL_IR=1 python3 AIL_CURRENT/ail_chatgpt.py compile prog.ail --syntax python -o prog_ail && ./prog_ail
```

(Omit `AIL_IR=1` for the default path. Each finding directory has the exact script.)

## 日本語

AIL は「CPython と同じ結果、または名前付きのコンパイル時拒否」を約束しています。拒否は問題ありません。
黙って結果が違うものがバグです。このラボはそれを探します。

- `gen.py`: シード固定で再現できるランダムな型付き Python プログラムを生成します（整数の
  オーバーフロー、float の表示、str/bytes、リストの別名、dict、set、例外、ループ、再帰、
  dataclass、f-string）。
- `run.py`: シード範囲ごとに CPython と AIL（既定と `AIL_IR=1`）で実行し、
  same / refused / overflow / DIFF / crash / timeout に分類します。
- `fuzz-lab.yml`: 毎日 4 シャードで実行します。赤くなるのは DIFF か crash があった時だけで、
  拒否と宣言済みの 64 ビット overflow は件数のみです。
- DIFF が出たら `findings/` にプログラムと両方の出力、再現スクリプトが残ります。
