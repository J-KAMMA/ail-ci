# mdlite — a small Markdown subset to HTML converter

`mdlite` is a real, self-contained example app written the way a Python user
would write it: plain functions, one small class that carries the block state,
and `str` methods only — no `re`, no third-party packages, one file.

```
mdlite [FILE]
```

It reads Markdown from `FILE`, or from standard input when no file is named,
and writes HTML to standard output. It always exits 0, except when `FILE`
cannot be opened: then it prints `mdlite: cannot open FILE` on standard error
and exits 1.

## Build and run

With CPython:

```
python3 examples/mdlite/mdlite.py examples/mdlite/data/inline.md
cat examples/mdlite/data/lists.md | python3 examples/mdlite/mdlite.py
```

With AIL (default mode):

```
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/mdlite/mdlite.py -o /tmp/mdlite
/tmp/mdlite examples/mdlite/data/inline.md
```

`RESULTS.md` records which code path the build took, the numbers, and the
comparison with CPython.

## Supported Markdown

Nothing outside this list is special: it is passed through as plain text.

| Input | Output |
| --- | --- |
| `#` … `######` at the start of a line | `<h1>` … `<h6>` |
| blank line between runs of text | paragraph boundaries, `<p>` |
| `*em*` | `<em>` |
| `**strong**` | `<strong>` |
| `` `code` `` | `<code>` |
| `[text](url)` | `<a href="url">text</a>` |
| a line starting with ```` ``` ```` and an optional info string | `<pre><code class="language-x">` |
| `-` or `*` at the start of a line | bullet list, `<ul>` |
| `1.` at the start of a line | ordered list, `<ol>` |
| 2 or more leading spaces inside a list | one level of nesting |
| a line starting with `>` | one level of block quote, `<blockquote>` |
| `---` alone on a line | `<hr>` |

Two or more consecutive text lines are joined with one space into a single
paragraph. A fence without a closing fence runs to the end of the input.
Unclosed emphasis, an unmatched backtick and a link with no target stay as
literal text.

`&`, `<`, `>` and `"` are escaped as `&amp;`, `&lt;`, `&gt;` and `&quot;` in
all text and in code; non-ASCII text (Japanese, accented letters, emoji) is
copied through unchanged as UTF-8.

## Layout

- `mdlite.py` — the converter (~300 lines).
- `data/*.md` — six hand-written inputs: headings and rules, inline
  constructs (including unclosed emphasis and non-ASCII), lists and nesting,
  block quotes, fenced code (including an unclosed fence), and empty input.
- `make_big.py` — writes a 20 MB corpus from fixed-seed repeated blocks.
- `RESULTS.md` — the AIL build path and the measured comparison.
