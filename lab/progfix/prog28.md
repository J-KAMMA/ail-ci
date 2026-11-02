# prog28: typed reach of eight real programs

CPython 3.12.3, `python3 -m cProfile -s tottime`, each `main()` called repeatedly on its largest
published task input (`lab/corpus/tasks/<t>/in2.txt`) or with no input for the self-contained
`gdev` programs.  Times are tiny, so the shares below are of the profiled run (interpreter and
import builtins included); the 80% cut lists every program function that carries that share plus
the builtin it spends time in when that builtin dominates.

| program | hot function (own time) | own share | typed before | typed now | first reason before |
| --- | --- | ---: | --- | --- | --- |
| g25_040 | `main` | 32.4% (22 ms/2000) | no | no (follow-up) | `'_ail_en_Planet_all' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant` |
| g25_040 | `mass` (property) | 10.3% (7 ms/2000) | no | no (follow-up) | same module constant; `mass` also needs the generated Enum methods (`dunder method _AilIntEnum.__lt__; only __init__ is supported here, no other dunder (...)`) |
| g25_040 | `<lambda>` line 24 | 4.4% (3 ms/2000) | no | no (follow-up) | same |
| t141 | `main` | 48.2% (216 ms/2000) | no | **yes** | `'top_item' is an int and is being assigned a str; a local's kind is settled by its FIRST assignment and never changes afterwards ...` |
| t141 | `<lambda>` line 24 | 6.5% (29 ms/2000) | no | **yes** | same (`max(stock, key=...)` over a typed dict) |
| t441 | `main` | 12.4% (12 ms/2000) | yes | yes | -- |
| t441 | `<lambda>` line 15 (`f"{a}{b}"`) | 15.5% (15 ms/2000) | yes | yes | -- |
| t441 | `<lambda>` line 14 (`gcd`) | 12.4% (12 ms/2000) | yes | yes | -- |
| t441 | `<lambda>` line 13 (`a * b`) | 9.3% (9 ms/2000) | yes | yes | -- |
| g04_012 | `comb_sort` | 46.7% (14 ms/2000) | yes | yes | -- |
| g04_012 | `main` | 16.7% (5 ms/2000) | yes | yes | -- |
| t489 | `main` | 55.1% (49 ms/500) | no | no (follow-up) | `a set comprehension.` (also `import of 'unicodedata' is not available: this compiler builds only the modules it models (...)` and `unicodedata.name is not supported`) |
| g01_002 | `parse_status_counts` | 29.2% (19 ms/1000) | no | no (follow-up) | `import of 'collections' with a use that is not built: Counter, defaultdict (...), OrderedDict and deque are built for str / int / tuple keys ...` |
| g01_002 | `main` | 6.2% (4 ms/1000) | no | no (follow-up) | same, plus `the entry function cannot return checked str` |
| g22_020 | `find_two_singles` | 50.0% (3 ms/2000) | yes | yes | -- |
| g22_020 | `main` | 16.7% (1 ms/2000) | yes | yes | -- |
| g07_036 | `trim_extremes` | 27.3% (3 ms/2000) | no | **yes** | `trim_extremes() class list return type disagrees with its annotation` (the `enumerate` pair comprehension) |
| g07_036 | `main` | 9.1% (1 ms/2000) | no | **yes** | `'trimmed' is declared list; assigning int is unsupported.` |

The `gdev` programs with no input were run 2000 times; t141/t441 2000 times, g01_002 1000 times,
t489 500 times (its profile includes `unicodedata` calls).  Builtin own-time shares that make up
the rest of each 80%: t141 `max` 16.5%, `split` 13.2%, `dict.get` 8.0%, `print` 7.1%; t441
`reduce` 35.1%, `gcd` 6.2%; g04_012 `print` 23.3%, `max` 10.0%; t489 `ord` 21.3%; g01_002
`re.Pattern.match` 46.2%; g07_036 `print` 54.5%.

## Fixed here

1. **Key kind of `max`/`min` over a typed dict** (`python/pkg-v12/pyfunc.py`).  `max(stock,
   key=lambda name: stock[name])` returns the KEY of `stock`, not the key function's value.  The
   type fixed point answered INT for every bare-container `max`/`min`, so the pre-binding pass
   claimed `top_item` int and the real str assignment was refused as a rebinding.  `_etype` now
   answers the map's key kind (`_map_key_kind`) and `_is_str_expr` recognises the same shape.  The
   iterlower keyed-min/max lowering builds a synthesized holder list (`_il5_keys`) first; the
   pre-binding pass now leaves a subscript of a synthesized name to the statement that builds the
   list, so `_il5_keys[_il2_bi]` inherits the list's element kind instead of being pre-claimed
   int.  This makes t141 typed as a whole program (hot `main` and its lambda).
2. **`enumerate` pair comprehension and set literals from names**
   (`python/pkg-v12/pyfunc.py`, from the uncommitted work already in this branch).
   `[value for index, value in enumerate(values) if ...]` now builds as the existing index/value
   loop, with both names int64 and a private counter, and a `set[int]` literal whose elements are
   names (`{min_index, max_index}`) is a container binding rather than a numeric one.  This makes
   g07_036 typed as a whole program (hot `trim_extremes` and `main`).

Both changes only affect programs that were previously refused on the typed path.  The generated C
of the ten `lab/compare` tasks is byte-identical to the base commit.

## Follow-ups (left by name)

* **g25_040** needs typed `Enum` support: the generated `_AilIntEnum` methods (comparison, `name`,
  `value`, `_all`), a `@property` on an enum member, and an Enum class list as a module constant.
  Exact first refusal: `'_ail_en_Planet_all' is a module-level list of non-numbers; only an
  int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant`
  (strict also lists `dunder method _AilIntEnum.__lt__; only __init__ is supported here, no other
  dunder (...)`).
* **t489** needs `unicodedata.name` and `unicodedata.normalize` (the typed path also refuses
  `sorted({...}, key=ord)` as `a set comprehension.`), and the general path cannot build it either:
  `unicodedata.name is not supported; write instead: use the str methods (...) or
  unicodedata.category(ch), which is built`.
* **g01_002** needs the Counter use behind `counts[int(match.group("status"))] += 1`.  Exact first
  refusal: `import of 'collections' with a use that is not built: Counter, defaultdict (int, float,
  str, list, lambda: <constant>), OrderedDict and deque are built for str / int / tuple keys and
  int / float / str / tuple elements; the rest of the module is not (...)`, plus `the entry
  function cannot return checked str`.  A copy with the same Counter and a separate
  `text = match.group(1)` builds typed; only the inline `int(match.group(...))` key trips the
  collections pass.

## Probes (/tmp/probes/prog28, both builds)

`p1_maxmin_dict_key.py` (str/int keys, negative values, ties, empty with/without `default=`, key
through `abs`, dict through an argument and an alias, bounds through a list item and a class
attribute), `p2_enumerate_listcomp.py` (empty, negative, filter, slice, attribute source, copy),
`p3_set_literal_names.py` (duplicates, negative, aliasing, add), `p4_trim_variants.py` (empty,
one element, all equal, negative, duplicates, source unchanged) and `p5_t141_shapes.py` (the t141
command loop with empty/negative/removal/report cases).  All five match CPython on both `cmp.sh`
builds.
