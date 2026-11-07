# emit1 — where the typed emitter's extra instructions go, and what removing each construct is worth

Measurement only; the compiler is unchanged. Every number here was produced in this job by
`lab/emit/analyze.py`, `lab/emit/classify.py` and `lab/emit/bounds.py`, on the six programs the
ticket names: `ticket_audit`, `echo_pack`, `tree_fold`, `ledger_bin`, `tally_lang`, `berth_sim`.
The design that follows from it is in `docs/design/EMIT_LEAN.md`.

## Method

* **Both builds.** `analyze.py` compiles `lab/compare/src/<task>/typed.py` with
  `AIL_CURRENT/ail_chatgpt.py compile <src> --syntax python --debug-dir` and `main.c` with
  `gcc -O2 -std=c11`, rebuilds the emitted `program.c` with the compiler's own flags
  (`-O2 -g -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd -lm`) and runs both binaries
  under `valgrind 3.22.0` callgrind (`--cache-sim=no --branch-sim=no`, Ir only). The perf input is
  `lab/roof/attrib.py:case()`, the same one `lab/roof/RESULTS.md` uses. stdout is compared
  byte-for-byte on every baseline and every hand-edited variant; all comparisons were identical.
* **Per-line attribution.** `callgrind_annotate --auto=yes --show=Ir` gives Ir per line of the
  emitted C. `analyze.py` saves every row (`line, Ir, text, function`) to `data/lines.json`. Rows
  are aligned to the emitted source: a `-- line N ---` marker sets the line, a `=>` callee row
  does not consume one (it carries the callee's inclusive cost and belongs to the call line), and
  every recorded row is checked against the text of the line it claims. The older parser advanced
  one line per output line, so it drifted by one row per call site (up to 63 lines); that shifted
  functions such as `ail_idict_check`, `ail_tab_hhas` and `ail_list_push` in `lines.json`.
* **Sub-classification.** A line in a container-invariant helper (`ail_blist_meta`, `ail_idict_check`,
  `*_check`…) takes that role: the whole body is the invariant test, and `attrib.py`'s broad `.n`
  regex false-positives on `T->table.n` inside it. Every other line first gets `attrib.py`'s check
  class (overflow, bounds, refcount, alloc/free, copies, boxing), then an emitted runtime helper's
  role by function name; a line in user code (`py_main`, `pack`, `readvar`, `ev__d`, …) is classed
  by shape: prologue/epilogue, recursion guard, one-statement-per-op temporaries, a call to a
  generic helper, width conversion, loop control. All of `data/causes.json`.
* **Bounds, not estimates.** `bounds.py` applies each `patches/*.diff` to a *copy* of the emitted
  C, rebuilds with the same flags, checks stdout against the C baseline, and re-runs callgrind.
  The saved Ir is the real bound for that construct: what the instruction stream would cost if the
  emitter stopped producing it. It says nothing about whether the compiler can prove the removal;
  `docs/design/EMIT_LEAN.md` is where that is argued.
* **Coverage.** Line rows cover 87% (`ticket_audit`), 88% (`tree_fold`), 97% (`ledger_bin`), 97%
  (`berth_sim`), 99.6% (`echo_pack`) and 100% (`tally_lang`) of the program total; the remainder is
  time inside libc (`memcpy`, `malloc`, `qsort`) attributed to no line of `program.c`.
  The C column in the per-function tables is the same line attribution over `main.c`; it excludes
  libc, which is why C's per-function Ir sums to less than the program total for `tree_fold`
  (1.75e9 of its 4.45e9 is `qsort`) and `berth_sim` (2.49e9).

## Program totals

| task | AIL Ir | C Ir | AIL/C | extra Ir | top-10 shared functions |
|---|---:|---:|---:|---:|---:|
| ticket_audit | 13,002,098,682 | 2,405,978,672 | **5.40** | 10,596,120,010 | 49.3% |
| echo_pack | 5,447,660,701 | 1,866,703,042 | **2.92** | 3,580,957,659 | 90.7% |
| tree_fold | 8,786,003,453 | 4,445,946,422 | **1.98** | 4,340,057,031 | 60.2% |
| ledger_bin | 5,233,459,925 | 2,732,522,292 | **1.92** | 2,500,937,633 | 88.2% |
| tally_lang | 19,585,728,474 | 11,900,634,258 | **1.65** | 7,685,094,216 | 98.9% |
| berth_sim | 8,289,014,320 | 5,912,490,502 | **1.40** | 2,376,523,818 | 77.1% |

The ratios reproduce `lab/roof/RESULTS.md` (5.40, 2.92, 2.04, 1.92, 1.70, 1.43) to within the
`-g`/vectorisation flags of the attribution build.

## The ten hottest emitted functions, beside the hand-written C

Ir in millions. The two columns are independent rankings (row *i* is not a paired call): a `—`
simply pads the shorter list, or marks work the C does inline, so it has no function of its own.
The C column is line attribution over `main.c` only; libc callees are not in it (so `tree_fold`'s
`qsort` does not appear, while AIL's equivalent `AIL_KEYSORT_*` expansion does).

### ticket_audit (typed source; C parses a `F {p,n}` struct passed by value)

| emitted | Ir | hand-written C | Ir |
|---|---:|---|---:|
| `ail_blist_meta` | 1,276 | `main` | 1,353 |
| `py_main` | 1,007 | `num` | 224 |
| `ail_bytes_to_int` | 505 | `val_event` | 183 |
| `rec` (user) | 496 | `syn_buyer` | 164 |
| `ail_str_catn` | 457 | `alldig` | 109 |
| `ail__utf8_validate` | 414 | `isdig` | 67 |
| `ail_stab_check` | 401 | `syn_seat` | 66 |
| `ail_bsplit_span` | 358 | `syn_event` | 14 |
| `ail_shash` | 339 | `syn_date` | 5 |
| `ail__bpay_release` | 315 | `isup` | 3 |

### echo_pack

| emitted | Ir | hand-written C | Ir |
|---|---:|---|---:|
| `pack` | 2,004 | `pack` | 1,474 |
| `ail_tab_hslot` | 1,458 | `hsh` | 256 |
| `hash_of` | 288 | `key` | 85 |
| `ail_hash` | 241 | `flush` | 33 |
| `ail_bytearray_append` | 200 | — (inlined in `pack`) | — |
| `ail_list_push` | 192 | — | — |
| `ail_tab_hhas` | 157 | — | — |
| `ail_tab_put_hit` | 155 | — | — |
| `ail_idict_check` | 144 | — | — |
| `ail_ir_view_get` | 83 | — | — |

### tree_fold

| emitted | Ir | hand-written C | Ir |
|---|---:|---|---:|
| `AIL_KEYSORT_COLS` (`?`) | 1,081 | `main` | 1,119 |
| `ail_list_push` | 668 | `pre_next` | 468 |
| `ail_pslist_push` | 623 | `parse_tree` | 417 |
| `ail__key_i64_first` | 431 | `oput` | 179 |
| `py_main` | 369 | `addchild` | 141 |
| `parse_tree` | 342 | `compute_sub` | 121 |
| `ail_list_get` | 293 | `nbadd` | 84 |
| `ail_bl_append` | 291 | `cmp` | 68 |
| `rebuild` (user) | 282 | `newnode` | 57 |
| `ail_pslist_at` | 264 | `oc` | 17 |

### ledger_bin

| emitted | Ir | hand-written C | Ir |
|---|---:|---|---:|
| `py_main` | 932 | `main` | 1,184 |
| `readvar` | 729 | `rdvar` | 881 |
| `pymod` | 557 | `hfind` | 137 |
| `ck_shl` | 555 | `lookup` | 91 |
| `ail_tab_hslot` | 466 | `cmp_id` | 58 |
| `ck_add` | 418 | `hgrow` | 4 |
| `ail_bytes_get` | 276 | `cmp_top` | 2 |
| `ck_mul` | 186 | — | — |
| `ail_list_push` | 185 | — | — |
| `AIL_KEYSORT_I64`/`_COLS` (`?`) | 169 | — (`qsort` is libc) | — |

### tally_lang

| emitted | Ir | hand-written C | Ir |
|---|---:|---|---:|
| `ev__d` | 13,065 | `ev` | 9,575 |
| `ail_list_span_get` | 2,645 | `main` | 2,256 |
| `py_run__try1` (outlined try body) | 1,993 | — (inlined in `ev`) | — |
| `ail_sarena_keep_roots` | 373 | — | — |
| `ev` | 319 | — | — |
| `AIL_NUMFIELD` (`?`) | 319 | — | — |
| `pymod` | 246 | — | — |
| `ck_shl` | 200 | — | — |
| `ck_add` | 123 | — | — |
| `popcnt` | 83 | — | — |

### berth_sim

| emitted | Ir | hand-written C | Ir |
|---|---:|---|---:|
| `AIL_KEYSORT_I64` (`?`) | 1,658 | `cmpu` | 1,036 |
| `py_main` | 990 | `rd` | 890 |
| `ail_str_to_int` | 815 | `main` | 831 |
| `ail__str_split_sep_raw` | 765 | `upop` | 375 |
| `ail_stdin_readline` | 576 | `upush` | 198 |
| `ail__sarena_keep_roots_slow` | 352 | `wpush` | 54 |
| `ail_ir_view_get` | 331 | `wpop` | 40 |
| `ail_list_push` | 285 | — (`qsort` is libc) | — |
| `ail__asc_to_int` | 271 | — | — |
| `ail__str_to_int_full` | 191 | — | — |

## Sub-classification of `other`, by cause

Ir in millions over the emitted `program.c` lines. `container-invariant`, `list-helper`,
`dict-table-helper`, `byte-string-helper`, `allocator` and `call-frame` come from the function a
line is in; the rest are line shapes inside user code. `overflow`, `bounds`, `refcount`,
`alloc/free`, `copies` are `attrib.py`'s check classes, listed for completeness — they are not part
of `other`. Sums are per column, so a cause is comparable across programs.

| cause | ticket_audit | echo_pack | tree_fold | ledger_bin | tally_lang | berth_sim | total |
|---|---:|---:|---:|---:|---:|---:|---:|
| temporaries/one-statement | 1,658 | 2,308 | 788 | 1,510 | **10,130** | 1,177 | **17,571** |
| dict-table-helper | 1,326 | **2,402** | 1,600 | 967 | 0 | 1,614 | **7,909** |
| list-helper | 1,744 | 192 | 2,147 | 187 | **2,645** | 585 | **7,500** |
| call-frame (prologue/epilogue) | 6 | 16 | 0 | 121 | **3,949** | 120 | **4,212** |
| bounds | 678 | 26 | **1,426** | 209 | 0 | 958 | 3,296 |
| byte-string-helper | 994 | 245 | 358 | 97 | 0 | **1,561** | 3,255 |
| container-invariant | **2,379** | 144 | 214 | 14 | 0 | 156 | 2,908 |
| other-user-lines | 264 | 41 | 268 | 640 | **975** | 376 | 2,565 |
| overflow | 271 | 9 | 287 | **796** | 266 | 168 | 1,798 |
| allocator | **912** | 0 | 176 | 16 | 373 | 258 | 1,735 |
| recursion-depth-guard | 0 | 0 | 0 | 0 | **988** | 0 | 988 |
| loop/condition | 193 | 43 | 73 | 10 | 7 | **513** | 839 |
| alloc/free | **399** | 1 | 213 | 29 | 0 | 180 | 822 |
| overflow-helper | 0 | 0 | 5 | **371** | 200 | 17 | 592 |
| width/int-float conversion | 9 | 0 | 61 | 97 | 53 | **325** | 545 |
| copies | **165** | 0 | 75 | 5 | 0 | 60 | 305 |
| refcount | **185** | 0 | 5 | 2 | 0 | 15 | 208 |
| call-to-generic-helper | **87** | 0 | 23 | 0 | 0 | 0 | 110 |
| exception-unwind | **26** | 0 | 0 | 0 | 0 | 0 | 26 |
| **sum** | 11,297 | 5,427 | 7,719 | 5,073 | 19,585 | 8,084 | 57,185 |

Read as a whole, the six programs say the same thing roof1 said for five: the emitted shape, not
the checks, is the cost. `temporaries/one-statement` is 30.7% of all emitted lines' Ir; add the
container/dict/string helper bodies (which are mostly the same per-element bookkeeping moved into
C functions) and the share is 63%. The checks (`bounds` + `overflow` + refcount + copies) are 10%.

## Cause catalogue, before/after, and the measured bound

Each cause below names the emitter construct, shows the emitted C before the hand edit and after,
and gives the measured Ir saved when the construct is removed from the generated C and stdout stays
byte-identical. "of extra" uses the program's real AIL−C difference above. Edits are isolated and
not additive: two edits that touch the same loop cannot both save their full amount.

### 1. Container invariant test on every element access — `ail_blist_meta`

Every `ail_blist_view`, `ail_blist_push`, `ail_blist_release`, `ail_blist_store` and
`ail_blist_retain` calls a six-compare invariant test. `ail_blist_meta` alone is 1,276M Ir in
`ticket_audit` (9.8% of the program), and the C has no equivalent: `F` is a by-value `{p,n}` view
and `syn_code` reads `f.p[0]` directly.

Before (emitted; `ail_blist_view` adds the call on top of the index):

```c
static inline void ail_blist_meta(const ail_blist *B) {
    if (__builtin_expect(!B || !B->refs || B->n < 0 || B->cap < B->n || (B->cap && !B->p) ||
            (uintmax_t)B->cap > (uintmax_t)SIZE_MAX / sizeof *B->p ||
            (uintmax_t)B->cap > (uintmax_t)PTRDIFF_MAX / sizeof *B->p, 0))
        ail_die("invalid bytes list");
}
static inline ail_bytes ail_blist_view(const ail_blist *B, int64_t i) {
    ail_blist_meta(B);
    if (__builtin_expect((uint64_t)i >= (uint64_t)B->n, 0)) ail_die("index out of range");
    return B->p[i];
}
```

After (`ticket_audit_noview.diff`, 40 constant-index calls; `ticket_audit_nometa.diff`, the test
itself):

```c
v_code = ail_bytes_decode_utf8(&v__sarena, v_f->p[0]);          /* was ail_blist_view(v_f, 0LL) */
static inline void ail_blist_meta(const ail_blist *B) { (void)B; }  /* bound only */
```

| hand edit | before Ir | after Ir | saved | % program | % extra |
|---|---:|---:|---:|---:|---:|
| `ticket_audit_nometa` (invariant test body emptied) | 13,002,099,013 | 11,634,167,277 | **1,367,931,736** | 10.52% | 12.91% |
| `ticket_audit_noview` (40 `ail_blist_view` -> `p[i]`) | 13,002,099,013 | 12,458,391,444 | **543,707,569** | 4.18% | 5.13% |

The 1,368M is the bound for the *test*, not for a safe change: the test is a memory-safety check
on a list header, and removing it is only legitimate where the header is provably a trusted local
(see `docs/design/EMIT_LEAN.md`, "Not in this split"). It is reported because it is what the
construct costs, and because it shows the check is 2.5x the price of the index+bounds call around
it.

The C counterpart (`syn_code`, `val_event`, `num`) reads the same fields with no test at all, so
this is not a check the C "gets for free" from a different algorithm: it is a check only AIL emits.

### 2. Generic dict/table probe where a specialised probe exists — `ail_tab_hslot` / `ail_idict_*`

`echo_pack` is the clearest case. `pack` builds an `idict` from key bytes to slot, and every
lookup goes through the chained `ail_idict_has/need/get/put` helpers, calling `ail_hash` per
operation. The C uses four parallel arrays (`head`, `prev`, `key`) and a four-line probe.

Before (emitted, per packet key):

```c
int64_t ir5 = ail_idict_need(&v_head, ir4);        /* hash + chain walk + epoch bookkeeping */
...
ail_idict_put(&v_head, ir4, ir8);
```

After (`echo_pack_dict2.diff`):

```c
static int64_t sp_find(const int64_t *head, const int64_t *prev, const int64_t *keys, int64_t key) {
    int64_t h = ((uint32_t)key * 2654435761u) >> 12;
    for (int64_t p = head[h]; p >= 0; p = prev[p]) if (keys[p] == key) return p;
    return -1;
}
```

| hand edit | before Ir | after Ir | saved | % program | % extra |
|---|---:|---:|---:|---:|---:|
| `echo_pack_dict2` | 5,447,661,169 | 3,520,409,975 | **1,927,251,194** | 35.4% | 53.8% |

This is the largest single bound measured in this lane. It is one program's shape (a dict keyed by
a varint), but the same generic-probe pattern is the largest `other` cause in `tree_fold`
(`dict-table-helper` 1,600M), `berth_sim` (1,614M, the keysort/qsort replacement),
`ticket_audit` (1,326M) and `ledger_bin` (967M).

### 3. Per-call recursion-depth guard — `AIL_MAX_RECURSION_DEPTH`

Emitted once per call of every depth-carrying function (`emit_c.py:763`). In `tally_lang`'s
recursive evaluator that is one compare + branch per node evaluation:

```c
static int64_t ev__d(ail_obj_Prog *v_p, int64_t v_i, int64_t ail_d) {
    if (ail_d > AIL_MAX_RECURSION_DEPTH) ail_die("maximum recursion depth exceeded");
    ...
```

After (`tally_lang_norec.diff`): the guard removed from `ev__d` only (the other functions keep
theirs).

| hand edit | before Ir | after Ir | saved | % program | % extra |
|---|---:|---:|---:|---:|---:|
| `tally_lang_norec` | 19,585,728,756 | 18,401,359,873 | **1,184,368,883** | 6.05% | 15.4% |

Related, and larger in the same function: the prologue/epilogue of `ev__d` (`call-frame` 3,949M,
20.2% of `tally_lang`). The function has enough live values that gcc saves and restores a large
callee-saved set per call. Note that the two call-frame figures are not directly comparable: gcc
splits `ev__d` into a hot `ev__d'2` specialization whose entry rows the line attribution assigns to
the `ev__d` function, so the line column (13,065M) is larger than any single summary entry, while
the C side's inlined `ev` body (9,575M) is a single function.

### 4. Overflow-checked arithmetic per Python operation — `ck_add`/`ck_mul`/`ck_shl`/`ck_sub`

The typed emitter lowers `+ - * <<` in `ck` mode to a helper call that tests overflow.
`ledger_bin`'s varint reader does four of them per byte; `pymod`'s `%` (557M, one 556M line) is the
single hottest line in the program, and `ck_shl`'s five-check body (555M) is the second.

Before (`readvar`):

```c
int64_t ir15 = ck_add(ir4, 1LL);
int64_t ir18 = ck_mul(7LL, ir17);
int64_t ir19 = ck_shl(ir16, ir18);
int64_t ir20 = ck_add(ir5, ir19);
```

After (`ledger_bin_noovf.diff`):

```c
int64_t ir15 = ((ir4) + (1LL));
int64_t ir18 = ((7LL) * (ir17));
int64_t ir19 = ((int64_t)((uint64_t)(ir16) << (uint64_t)(ir18)));
int64_t ir20 = ((ir5) + (ir19));
```

| hand edit | before Ir | after Ir | saved | % program | % extra |
|---|---:|---:|---:|---:|---:|
| `ledger_bin_noovf` | 5,233,460,211 | 4,384,684,791 | **848,775,420** | 16.2% | 33.9% |
| `ticket_audit_noovf_int` (per-digit limit test in `ail_bytes_to_int`) | 13,002,099,013 | 12,838,442,944 | **163,656,069** | 1.26% | 1.54% |

### 5. Generic byte/string helper per line — ASCII scan, split, int parse

`berth_sim` reads lines, splits them on spaces and parses ints. `ail_stdin_readline` classifies
every byte of every line as ASCII before choosing the fast path:

Before (`ail_stdin_readline`, 576M):

```c
int _ascii = 1;
for (int64_t _k = 0; _k < take; _k++) {
    if (start[_k] >= 0x80) { _ascii = 0; break; }
}
if (_ascii) { ... }
```

After (`berth_sim_noascii.diff`): the scan removed, `_ascii = 1` forced (the perf input is ASCII,
and the decoder path is unchanged for non-ASCII).

| hand edit | before Ir | after Ir | saved | % program | % extra |
|---|---:|---:|---:|---:|---:|
| `berth_sim_noascii` | 8,289,014,899 | 7,799,368,411 | **489,646,488** | 5.91% | 20.6% |

The rest of `berth_sim`'s `byte-string-helper` 1,525M is `ail_str_to_int` (815M),
`ail__str_split_sep_raw` (765M) and `ail__asc_to_int`/`ail__str_to_int_full` (462M): a generic
splitter and a generic parser called per field, where `main.c` has an inline `for` loop.

### 6. Generic sequence helpers where a direct write exists — `ail_list_pop`, `ail_list_span_get`

Before (emitted worklist pop and span reads):

```c
(void)(ail_list_pop(&v_stack, v_stack.n - 1));
...
ail_list_push(&v_w, ({ (void)0; int64_t _index = v_i;
                      ail_list_span_get((v_t)->f_w.p, (v_t)->f_w.n, _index); }));
```

After (`tree_fold_nopop.diff`, `tree_fold_nospan.diff`):

```c
(void)(--(&v_stack)->n);
ail_list_push(&v_w, (v_t)->f_w.p[v_i]);
```

| hand edit | before Ir | after Ir | saved | % program | % extra |
|---|---:|---:|---:|---:|---:|
| `tree_fold_nopop` | 8,786,004,032 | 8,557,620,257 | **228,383,775** | 2.60% | 5.26% |
| `tree_fold_nospan` (20 span reads) | 8,786,004,032 | 8,634,230,026 | **151,774,006** | 1.73% | 3.50% |
| `echo_pack_pushloop` (list init loop) | 5,447,661,169 | 5,371,292,437 | **76,368,732** | 1.40% | 2.13% |

### 7. One statement per Python operation — nested comma expressions and stack temporaries

The typed emitter gives every source operation its own `v__tN` slot and every intermediate its own
`irN` local. The result is visible in the emitted loop condition below; the C writes one boolean
expression.

Before (`echo_pack`, byte compare loop):

```c
int64_t ir66 = 0;
if (ir65) {
    int64_t ir67 = 0, ir68 = 4LL;
    for (;;) {
        int64_t ir69 = (ir68 < ir46);
        int64_t ir70 = 0;
        if (ir69) { ... ir70 = ir75; } else { ir70 = 0; }
        if (!(ir70)) { ir67 = ir68; break; }
        int64_t ir76 = ((ir68) + (1LL));
        ir68 = ir76;
    }
    ir66 = ir67;
} else { ... the same loop again ... }
```

After (`echo_pack_cmpmatch.diff`):

```c
int64_t ir66 = 4LL;
while (ir66 < ir46 && v_d.p[ir52 + ir66] == v_d.p[ir20 + ir66]) ir66++;
```

| hand edit | before Ir | after Ir | saved | % program | % extra |
|---|---:|---:|---:|---:|---:|
| `echo_pack_cmpmatch` | 5,447,661,169 | 5,265,742,555 | **181,918,614** | 3.34% | 5.08% |

This is the smallest of the shape bounds, because the `irN` locals are usually cheap; the cost is
not the temporaries as values but the branch structure built from them (see `tally_lang`'s
`ev__d`, where `temporaries/one-statement` is 10,130M).

### 8. Bounds-checked element accessors — `ail_bytes_get`, `ail_ir_view_get`, `ail_list_get`

Before/after (`tree_fold_nobget.diff`, `echo_pack_nobounds.diff`):

```c
int64_t ir82 = ail_bytes_get(v_d, ir81);       ->  int64_t ir82 = ((int64_t)(v_d).p[ir81]);
int64_t ir91 = ail_ir_view_get(ir47_p, ir47_n, ir52);  ->  int64_t ir91 = ir47_p[ir52];
```

| hand edit | before Ir | after Ir | saved | % program | % extra |
|---|---:|---:|---:|---:|---:|
| `tree_fold_nobget` | 8,786,004,032 | 8,619,057,995 | **166,946,037** | 1.90% | 3.85% |
| `echo_pack_nobounds` | 5,447,661,169 | 5,358,448,246 | **89,212,923** | 1.64% | 2.49% |

### 9. Negative: inlining the helper is not the lever

`echo_pack_ai_append.diff` marks `ail_bytearray_append` `always_inline` instead of `static inline`:
saved 4,735,684 Ir (0.09%). The helper is already inlined or its call overhead is negligible; the
cost in `echo_pack` is the probe (`dict-table-helper`) and the emitted statement shape, not the
call instruction. This is why the design below does not start with "inline more".

## The ticket's named sub-causes: measured, or not separable

The list in the task is broader than the causes with a hand-edit bound. This is what could and
could not be isolated; "attributed" is `data/causes.json`, "bound" is a hand edit that removes the
construct and keeps stdout identical.

| named sub-cause | where it is | Ir | isolated bound |
|---|---|---:|---|
| struct/string passed by value | `ail_bytes`/`ail_str` are 16-byte structs passed and returned by value; the cost sits in `byte-string-helper` | 3,255M attributed | not measured: replacing the ABI with pointers changes every message and every call site, so the hand edit would not be local |
| temporaries that block register allocation (address taken) | `v__tN` slots are declared at function scope (`int64_t v__t27 = 0;`) and assigned by each statement; `temporaries/one-statement` | 17,571M attributed | only 182M by rewriting one loop (`echo_pack_cmpmatch`); no whole-shape bound |
| repeated loads through a pointer gcc cannot prove unaliased | `(*v_data).p[...]` and `v_x->f_...` chains in `py_main`/`pack`/`ev__d`; inside `other-user-lines` | 2,565M attributed | not separated: the loads are the operands of the one-statement expressions, and removing them means rewriting the expression, not deleting a construct |
| helper calls not inlined | `ail_blist_meta` is `static inline` yet kept an out-of-line copy (1,276M); `ail_bytearray_append` forced `always_inline` | 1,276M in `ail_blist_meta` | inlining the append: **4.7M saved (negative)**, so the lever is the helper body, not the attribute |
| generic helpers where a specialised loop exists | dict probe (`echo_pack_dict2`), `ail_bytes_to_int` per digit, `ail_str_to_int`/`ail__str_split_sep_raw` | 1,927M bound; 164M bound; 490M bound | measured, causes 1, 4, 5 |
| redundant length/cap reloads | `ail_blist_meta`/`ail_tab_hslot` re-read `n`, `cap`, `used`; `ail_ir_view_get` re-reads `p,n` | inside `container-invariant` 2,908M | not separated: the reload is the expression operand; the view/accessor bound (cause 6, 952M) includes it |
| int<->float or width conversions | `width/int-float conversion` lines, mostly `(int64_t)`/`(uint32_t)` around `%`, shifts and byte loads | 545M attributed | not measured; no hand edit removes only the cast |
| exceptions/unwind state checks after calls | `ail_ir_try`, `ail_cleanup_top`, pending checks; and the outlined try body `py_run__try1` | 26M overhead lines + 1,993M in the outlined body | not measured: the body is user code (it is a `try` around the parser), not unwind overhead; the 26M is too small to isolate reliably |

## Ranking by measured Ir saved across the six programs

Isolated hand-edit bounds, largest first. `programs` counts the tasks the cause is above 1% of.

| rank | cause | measured saved | programs | bound edit |
|---:|---|---:|---:|---|
| 1 | generic dict/table probe (specialise it) | **1,927M** | 1 (`echo_pack`) | `echo_pack_dict2` |
| 2 | container invariant test on every list operation | **1,368M** | 1 (`ticket_audit`) | `ticket_audit_nometa` |
| 3 | recursive evaluator: depth guard | **1,184M** (+ 3,949M frame, attributed only) | 1 (`tally_lang`) | `tally_lang_norec` |
| 4 | overflow-checked arithmetic | **1,012M** (`848M` + `164M`) | 3 | `ledger_bin_noovf`, `ticket_audit_noovf_int` |
| 5 | generic list/sequence helpers where a direct write exists | **1,001M** | 3 | `ticket_audit_noview`, `tree_fold_nopop`, `tree_fold_nospan`, `echo_pack_pushloop` |
| 6 | bounds-checked accessors | **952M** (set overlaps 5) | 4 | `ticket_audit_noview`, `tree_fold_nobget`, `echo_pack_nobounds` |
| 7 | ASCII/UTF-8 and split/parse helpers | **490M** | 1 (`berth_sim`) | `berth_sim_noascii` |
| 8 | one-statement-per-op shape (local rewrite) | **182M** | 1 (`echo_pack`) | `echo_pack_cmpmatch` |
| — | always-inline a helper | 4.7M (negative) | 0 | `echo_pack_ai_append` |

Three cautions for the design. (a) Rank 2 is a **memory-safety check**, not an optimisation: the
measured bound is what it costs, but removing it without an escape proof would trade correctness
for 10% of one program, so `EMIT_LEAN.md` deliberately queues the three changes below it (dict
probe, recursion guard, overflow) and leaves the safe sub-step (hoist the check from read-only
views) as a follow-up gated on the same local-escape marker design 1 needs. (b) The edit bounds
overlap: `ticket_audit_noview` removes both the invariant test and the bounds test and the call,
so ranks 5 and 6 cannot both be claimed in full. (c) The ranking is per *edit*, not per *cause*:
`temporaries/one-statement` has 17,571M of attributed Ir but no hand edit removes more than 182M
of it, because a local rewrite cannot change the emitter's expression shape. The design queues
the causes with a measured, reproducible bound and treats the shape as a separate, larger lane.

## Files

* `lab/emit/analyze.py` — builds both sides, runs callgrind, writes `data/measured.json` and
  `data/lines.json` (per-line Ir).
* `lab/emit/classify.py` — sub-classifies `other`; writes `data/causes.json`.
* `lab/emit/bounds.py` + `lab/emit/patches/*.diff` — rebuilds hand-edited copies of the emitted C,
  checks stdout, writes `data/bounds.json` (and `data/bounds_meta.json` for the meta-only edit).
* `lab/emit/data/` — the JSON above. `results.json` is the earlier combined dump, kept for the
  first pass; the files the tables cite are the four named here.

Reproduce (valgrind 3.22 on `PATH`, `VALGRIND_LIB` set if unpacked):

```sh
python3 lab/emit/analyze.py
python3 lab/emit/classify.py
python3 lab/emit/bounds.py
```

Together about 12 minutes of callgrind on the 4-vCPU runner; `bounds.py` is the longer half.
