# Debugging an AIL program

AIL compiles to C, so the C debugger is the debugger. A `--debug` build keeps the
Python source lines in the DWARF line table, gives int and float locals their
Python names, and builds at `-O0`, so gdb can break on a `.py` line, step, and
print values. `AIL_CURRENT/tools_gdb/ail_gdb.py` adds pretty-printers that show an
AIL value as CPython 3.12's `repr()` instead of the C struct behind it.

This page covers the debug build, gdb with the printers, `bt`, and what `next`
does on the typed path and the general path. The measurements and the known
failures are in [lab/debug/RESULTS.md](../lab/debug/RESULTS.md).

## Build with debug information

```sh
ail build --debug program.py -o program
# from a source checkout:
python3 -B AIL_CURRENT/ail_chatgpt.py compile program.py -o program --debug --debug-dir program.d
```

`--debug` also works with `--strict` (the typed path, or a refusal) and with the
general path (`AIL_UNIFIED_FORCE=1`). `--debug-dir DIR` keeps `DIR/program.c`,
the generated C, which is the best place to check a layout below.

## gdb and the printers

The printer script needs only gdb's own Python:

```sh
gdb -x AIL_CURRENT/tools_gdb/ail_gdb.py ./program
```

or, in a batch run:

```sh
gdb -batch -nx -x AIL_CURRENT/tools_gdb/ail_gdb.py \
    -ex 'break program.py:12' -ex run -ex 'print x' -ex bt ./program
```

The printers read memory only; they never call a function in the program. Every
loop is bounded by the value's own length field, a bad pointer prints
`<unreadable>`, and a container longer than 100 elements prints its first 100
elements and then `...`.

The locals gdb has by Python name are the int and float locals of the typed
path (`print x`). Other typed-path locals keep their C names (`print v_x`), and
the general path keeps values in its frame array (`print f.slots[2]`); see
"Where a value lives" below.

## The layouts of the 12 common kinds

These are the structs in `--debug` generated C. `typed` is the typed path;
`general` is the `ail_obj` path. The `repr` column is what the printer shows.

| kind | typed path | general path | repr |
| --- | --- | --- | --- |
| int | `int64_t` | `ail_obj{tag=AIL_T_INT, i}` | `42` |
| float | `double` | `ail_obj{tag=AIL_T_FLOAT, o=ail_floatbox*}` | `1.5` |
| bool | `int64_t` 0/1 (see the note) | `ail_obj{tag=AIL_T_BOOL, i}` | `True` |
| None | no value: `v_x=0, v_x__set=0` | `ail_obj{tag=AIL_T_NONE}` | `None` |
| str | `ail_str{const uint8_t *p; int64_t n; _Bool bytes}` (UTF-8) | `ail_obj{tag=AIL_T_STR, sv{backing, off, len}}` over `ail_strback{ail_gcobj hdr; int64_t n; uint16_t data[]}` | `'héllo'` |
| bytes | `ail_bytes{const unsigned char *p; int64_t n}` | a `bytes` instance object | `b'hi\n'` |
| list[int] | `ail_list{int64_t *p; ail_len_t n, cap}` | `ail_obj{tag=AIL_T_LIST, o=ail_vecobj*}` | `[1, 2, 3]` |
| list[float] | `ail_flist{double *p; int64_t n, cap}` | same as list | `[1.5, 2.0]` |
| list[str] | `ail_slist{ail_str *p; int64_t n, cap}` | same as list | `['a', 'b']` |
| dict[str, int] | `ail_sdict{ail_stab table; uint64_t epoch}` with `ail_stab{ail_sslot *slot; int64_t *val; ail_str *order; int64_t n, fill, cap, top}` | `ail_obj{tag=AIL_T_DICT, o=ail_mapobj*}` | `{'a': 1, 'b': 2}` |
| tuple | `ail_obj__AilT_*` (/`ail_obj_header`, `f_f0`...`f_fN`) | `ail_obj{tag=AIL_T_TUPLE, o=ail_vecobj*}` | `(1, 'x')` |
| general boxed object | - | `ail_obj{uint8_t tag; union{int64_t i; struct{ail_gcobj *backing; int64_t off, len;} sv; ail_gcobj *o;}}` | `[1, 2, 3]` |

Notes:

* The typed path's `ail_str` is a view of UTF-8 bytes. Its `bytes` flag is 1 only
  for pure ASCII, where one unit is one character. The general path's `ail_obj`
  string is a view (`sv`) of 16-bit code units in a `ail_strback`; the `ail_str`
  type it uses at its boundary is `{const uint16_t *p; int64_t n; _Bool bytes}`,
  and a `bytes` flag there means the backing is really `uint8_t` data.
* A typed `bool` is still an `int64_t` 0/1 at run time, so gdb cannot tell
  `True` from the int `1`; the printer shows `1`. The bool row above is measured
  on the general path, where `ail_obj` has a `AIL_T_BOOL` tag. Likewise a typed
  `None` is a compile-time "unset" flag, not a C value; use the general path to
  see `None`.
* The typed `ail_sdict` keeps insertion order in `table.order[0 .. top)`. A
  deleted entry is a hole (`order[j].n < 0`); its value is `table.val[j]`.
* General-path containers are also insertion ordered: a list/tuple is
  `ail_vecobj{ail_obj *p; int64_t n, cap}`, a dict is
  `ail_mapobj{ail_mapentry *entries; int64_t n, cap; ...}`, and a set is
  `ail_setobj{ail_setentry *ent; int64_t n, ..., used}` with UNBOUND holes.

## Where a value lives

`test_ail_debug_lines` and `test_ail_debug_gdb` cover the line table and the
following behaviour; the details are in `lab/debug/RESULTS.md`.

* Typed path, no `try`: an int or float local has a C variable of its Python
  name. `info locals` shows `k`, `g`, `r`, and `print x` works. The mirror is
  only for int and float, and a `for` target, tuple target, loop-carried value,
  C keyword or name that could clash is left in its IR variable.
* Typed path, other locals: use the C name. Strings and containers are `v_x`;
  compiler temporaries are `ir1`, `ir2`, ...; legacy-path locals are `v_<name>`.
* General path: locals live in the frame's `ail_obj` slots, not in C variables
  with Python names by default. At a breakpoint in `f`, `print f.slots[2]`
  prints the value in slot 2 (the index is in `--debug-dir`/`program.c`).

## `bt` and `next`

`bt` names the Python file and line of each frame, for example
`inner at p02_nested.py:2`, `middle at p02_nested.py:7`, `outer at
p02_nested.py:12`, `main at p02_nested.py:17`. An uncaught AIL exception stops
in the runtime's `ail_die`, whose message is the Python exception text; `bt`
then still names the function that raised (`pick at p09_raise.py:2`).

On the typed path `next` follows the statement lines CPython's `sys.settrace`
reports, with the gaps recorded in `RESULTS.md`: a `try` body is outlined into
another C function, so `next` steps over its first line; one legacy-emitter
statement that spans three C lines maps the second and third to later lines;
and a call in a debug build is still `always_inline`, so `finish` does not show
a returned value. On the general path the line table is 100% complete; the
same three `next`/`finish` gaps apply only to the typed path's `try` and
straight-line lowering.

## Known gaps (from fddbg1's `lab/debug/RESULTS.md`)

* Typed path: 76/77 statement lines in the line table; the missing one is the
  `__init__` body inside `ail_new_<Class>` (`p03_method.py:3`), lowered by
  `pyfunc.py` and outside this lane.
* Typed `next` from `p05_try.py:2`: the `try` body is outlined, so `next`
  steps over line 3; `step` reaches it.
* Typed `next` from `p10_strings.py:9`: the legacy emitter writes one `#line`
  for a statement spread over three C lines.
* Typed `finish` inside a call: `always_inline` is kept in debug builds, so
  gdb shows no "Value returned".
* The Ubuntu 24.04 runner image has no gdb; the gdb tests skip there and print
  `gdb: not installed`. The printer test uses the same skip.

## Tests

```sh
python3 AIL_CURRENT/test_ail_debug_printers.py   # 12 kinds + bounds/bad pointer
python3 AIL_CURRENT/test_ail_debug_gdb.py        # fddbg1's matrix + line coverage
```
