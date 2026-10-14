/* mix_call.h -- the mixed-mode calling convention (BRIEF_mixed_mode.md, 2026-09-16).

   STANDALONE per the brief's own gate: not `#include`d by anything yet. This is the contract the
   integration step (pyboxed2.py's call-site emission, cleared separately) is meant to build
   against, written down and validated against REAL typed-emitter output first, so that step is
   wiring known-correct pieces together rather than inventing the ABI while also wiring it in.

   Validated (2026-09-16, this pass): the C signatures assumed below were checked against actual
   `pyfunc.to_c()` output for candidates `pymix.py` selected from real test programs --
   `int64_t dotp(const int64_t *v_a, int64_t v_a_len, const int64_t *v_b, int64_t v_b_len)` for a
   `list[int], list[int] -> int` candidate, matching `pyfunc.py`'s own `signature()` table exactly
   (array kind: `const int64_t *, int64_t` pair per parameter). NOT validated here: an end-to-end
   compile and link of a typed-emitted `.c` unit together with a `pyboxed2.py`-emitted (v2 runtime)
   unit in the same binary -- see "OPEN QUESTION" at the bottom.

   ---- The mechanism, restated for this file's own scope --------------------------------------

   At a call site the boxed (general-path) caller already has -- calling some function `f` with
   boxed argument(s) -- the integration step, once cleared, emits a runtime GUARD before the
   existing boxed call:

       ail_obj __a0 = <boxed arg 0 expression>;   // ... one per parameter
       if (ail_mix_is_int(__a0) && ...) {                    // every hypothesis holds
           int64_t p0 = ail_mix_unbox_int(__a0);             // ... one unbox per parameter
           int64_t __r = f__typed(p0, ...);                  // the typed clone, mangled name below
           *out = ail_mix_box_int(__r);                      // or box_bool/box_float/box_str_result
       } else {
           st = f(cx, out, __a0, ...);           // UNCHANGED boxed call -- today's correct path
           ail_ctx_check(cx, st);
       }

   A miss costs exactly the guard's own comparisons (plus, for a list parameter, one O(n) walk --
   see `ail_mix_check_list_int`/`_float` below, which is BOTH the guard and the unboxing copy in
   one pass, so the "count it in the report" cost is one call, not two). It never trusts a value it
   has not just checked, and it never mutates the boxed heap: every unboxed buffer this header
   allocates is a fresh copy, freed by the guard's own generated cleanup after the typed call
   returns (the emitted code above, not this header, owns that `free()` -- exactly one, right after
   `*out = ...`, on both the taken and not-taken side of a list guard doesn't matter since only the
   taken side ever allocated).

   Symbol naming for the typed clone (what "mangled name" above means): `<pyname>__typed`, checked
   against `_mangle_csym`'s own `_RESERVED_CSYMS`/`ail_`-prefix rule (pyfunc.py) the same way any
   other C symbol in this pipeline is -- `<pyname>` here is the value `_mangle_csym` would already
   have produced for the ORIGINAL (boxed) function, so a name that needed `py_` still gets it,
   consistently, before `__typed` is appended; `__typed` itself cannot collide with anything
   `_mangle_csym` produces (no Python identifier contains `__typed` unless the source itself does,
   which the integration step must additionally refuse -- flagged, not silently reused).

   ---- Runtime facts this header relies on (out/boxed_rt/v2/API.md, pyboxed2.py) --------------

   - Every boxed value is `ail_obj { uint8_t tag; union { int64_t i; ail_gcobj *o; ... }; }`` with
     `tag` one of `AIL_T_UNBOUND=0, AIL_T_NONE, AIL_T_BOOL, AIL_T_INT, AIL_T_FLOAT, AIL_T_STR,
     AIL_T_LIST, ...` (API.md section 2).
   - `ail_box_int(int64_t)`, `ail_box_bool(int)` are inline, no allocation (`ail_obj2.h`).
   - `ail_box_float(ail_ctx *cx, double)` DOES allocate (a `ail_floatbox`) -- needs `cx`, unlike
     the other two; every helper below that boxes a float takes `cx` for exactly this reason.
   - `ail_float_val(ail_obj)` is the v2 runtime's own float-payload accessor -- already used this
     way at a matching call site in `pyboxed2.py` itself (line ~3078: `(obj.tag==AIL_T_FLOAT) ?
     ail_float_val(obj) : (double)obj.i`), reused here rather than re-derived.
   - `ail_view_to_str(ail_obj) -> ail_str{const int32_t *p; int64_t n;}` is zero-copy -- this is
     ALSO the typed path's own `ail_str` (API.md: "unchanged from cruntime.py"), so an `ail_str`
     parameter needs no conversion at all once the tag check passes -- just the view call.
   - `ail_vecobj { ail_gcobj hdr; ail_obj *p; int64_t n, cap; }` backs both LIST and TUPLE
     (`ail_obj2.h`); `p` is boxed elements, never a raw numeric array -- a `list[int]`/`list[float]`
     typed parameter (`const int64_t *`/`const double *`) is NEVER an alias into `p`, always a
     fresh copy (see the two check-and-copy helpers below).

   ---- CONFIRMED BLOCKER, not resolved by this pass (load-bearing -- read before integrating) --

   `cruntime.py`'s preamble and `pyboxed2.py`'s v2 runtime headers CANNOT be concatenated into one
   `.c` translation unit as `pyc.py`'s `build()` does today (one `gcc ... c.c -o out` call) the
   moment a candidate touches `str` at all -- checked directly, not assumed: `pyfunc.to_c()`'s
   ACTUAL emitted preamble for a trivial one-line str function (`return 'hi ' + name`, this pass's
   own `greet` candidate) already defines, at minimum, `ail_str_cat`, `ail_str_cmp`, `ail_str_count`,
   `ail_str_endswith`, `ail_str_eq`, `ail_str_index`, `ail_str_isdigit`, `ail_str_lower`,
   `ail_str_startswith`, `ail_str_to_float`, `ail_str_to_int`, `ail_str_upper`, `ail_str_write` --
   EVERY one of which `out/boxed_rt/v2/ail_str2.h`/`ail_obj2.h` ALSO defines, under the exact same
   name (confirmed by symbol-name diff against both files, 2026-09-16). Pasted into one `.c` file,
   `gcc` reports `redefinition of 'ail_str_cat'` (and a dozen more) before it gets anywhere near
   running anything -- this is not a hypothetical the integration step needs to go check; it WILL
   happen on the brief's own worked example the first time it tries. `str` is not a corner case
   here either -- it is one of the seven kinds the brief names and one of `pymix.py`'s five actual
   selections on this pass's test programs.

   Not a design flaw in either runtime (`ail_str` itself being "shared, unchanged", API.md, shows
   this was anticipated at the TYPE level) -- a build-graph problem with an ordinary fix: compile
   the typed clone as its OWN translation unit (its OWN copy of `cruntime.py`'s preamble, every
   helper `static` as today, so it is invisible outside that `.o`) and the boxed program as a
   SECOND translation unit (`ail_obj2.h` et al, as today), then LINK the two `.o` files -- `static`
   (internal-linkage) names never collide across separate translation units, only within one; only
   the guarded call site's own bridge function (the typed clone's outer entry -- `dotp`, `greet`,
   ...) needs external linkage so the boxed TU's call to `<name>__typed` can reach it.
   `pyc.py`'s `build()` must therefore become a two-file, link step for a mixed-mode program --
   a real change to that driver's shape, not a flag -- which is exactly why this is flagged here,
   for the integration step, rather than discovered by it. */
#ifndef AIL_MIX_CALL_H
#define AIL_MIX_CALL_H

#include <stdint.h>
#include <stdlib.h>

/* ---- guards: true iff a boxed value's RUNTIME TAG matches the hypothesis a call site made.
   Never trust the payload before the matching guard returns true. */
static inline int ail_mix_is_int(ail_obj v)   { return v.tag == AIL_T_INT; }
static inline int ail_mix_is_float(ail_obj v) { return v.tag == AIL_T_FLOAT; }
static inline int ail_mix_is_bool(ail_obj v)  { return v.tag == AIL_T_BOOL; }
static inline int ail_mix_is_str(ail_obj v)   { return v.tag == AIL_T_STR; }

/* list[int] / list[float]: the guard AND the unboxing copy in one O(n) pass -- run ONCE per call
   site, matching the brief's "do it once per call and count it in the report". Returns 0 (fall
   back to the boxed function; `*buf` is untouched or already freed) the instant ANY element's tag
   disagrees with the hypothesis -- an empty list (`v.n == 0`) trivially satisfies either
   hypothesis, `*buf` set to NULL, `*n` set to 0, since `to_c`'s own array ABI already treats a
   zero-length array/NULL pointer pair as empty (see `signature()`'s array row). The caller
   `free()`s `*buf` after the typed call returns -- this header never frees what it allocates. */
static inline int ail_mix_check_list_int(ail_obj v, int64_t **buf, int64_t *n) {
    if (v.tag != AIL_T_LIST) return 0;
    ail_vecobj *L = (ail_vecobj *)v.o;
    int64_t *out = L->n ? (int64_t *)malloc((size_t)L->n * sizeof *out) : NULL;
    if (L->n && !out) return 0;
    for (int64_t i = 0; i < L->n; i++) {
        if (L->p[i].tag != AIL_T_INT) { free(out); return 0; }
        out[i] = L->p[i].i;
    }
    *buf = out; *n = L->n;
    return 1;
}
static inline int ail_mix_check_list_float(ail_obj v, double **buf, int64_t *n) {
    if (v.tag != AIL_T_LIST) return 0;
    ail_vecobj *L = (ail_vecobj *)v.o;
    double *out = L->n ? (double *)malloc((size_t)L->n * sizeof *out) : NULL;
    if (L->n && !out) return 0;
    for (int64_t i = 0; i < L->n; i++) {
        ail_obj e = L->p[i];
        if (e.tag == AIL_T_FLOAT) out[i] = ail_float_val(e);
        else if (e.tag == AIL_T_INT) out[i] = (double)e.i;   /* int elt in a float[] list: legal
                                                                  Python, legal C widening */
        else { free(out); return 0; }
    }
    *buf = out; *n = L->n;
    return 1;
}
/* list[str]: NOT provided here. `to_c`'s own `ail_slist` ABI (an owning spine of `ail_str`s,
   `signature()`'s SLIST row) needs an owning copy built element-by-element through
   `ail_view_to_str`, which is real code, not a one-liner like the two numeric cases above -- left
   for the integration step, which will have an actual `list[str]` candidate to write it against
   (none of `pymix.py`'s current selections need it; see the report). */

/* ---- unbox: only ever called after the matching guard above returned true. */
static inline int64_t ail_mix_unbox_int(ail_obj v)   { return v.i; }
static inline int     ail_mix_unbox_bool(ail_obj v)  { return (int)v.i; }
static inline double  ail_mix_unbox_float(ail_obj v) { return ail_float_val(v); }
static inline ail_str ail_mix_unbox_str(ail_obj v)   { return ail_view_to_str(v); }

/* ---- box: the KIND used here is the call site's RETURN HYPOTHESIS (pymix.py's `ret`/
   `is_bool_ret`), never re-derived from the raw C value -- `to_c` has no separate `bool` kind
   (SEMANTICS.md: a Python bool is a plain int64 everywhere in the typed emitter), so a
   `is_bool_ret` candidate's typed body returns a bare 0/1 `int64_t` that MUST still be boxed
   `AIL_T_BOOL`, not `AIL_T_INT` -- `str(True)` is `"True"`, not `"1"`; boxing it wrong is exactly
   the silent-wrong-answer class of bug the guard exists to make impossible, and it would not be
   caught by any guard check (the MISMATCH here is on the way OUT, after the typed call already
   ran correctly). */
static inline ail_obj ail_mix_box_int(int64_t v)                { return ail_box_int(v); }
static inline ail_obj ail_mix_box_bool(int v)                    { return ail_box_bool(v); }
static inline ail_obj ail_mix_box_float(ail_ctx *cx, double v)   { return ail_box_float(cx, v); }
/* str RESULT: deliberately not given a one-line helper. The typed emitter's OWN str-return ABI
   (`signature()`'s STR row) is `int64_t <len>` plus an OUT buffer `int32_t *_out, int64_t _cap`
   the CALLER supplies -- never a single `ail_str` value the way a str PARAMETER is. Boxing a
   str-returning typed_inline function's result needs either a fixed generously-sized `_cap` at
   the call site or the two-call length-then-fill probe `to_c`'s own entry-point driver already
   uses for exactly this ABI -- both are per-call-site code, not a fixed-signature helper this
   header can give once. Left for the integration step. */

/* ---- str across the boundary (2026-10-11). The typed path stores str as UTF-8 bytes; this
   general-path runtime still stores UTF-16 units. The two `ail_str` typedefs have the same layout
   ({pointer, int64 length, _Bool}), so a typed clone is handed a struct whose pointer is really
   UTF-8 bytes and whose length is a byte count, built here and freed by the call site. */
static inline ail_str ail_mix_unbox_str_utf8(ail_obj v, void **owned) {
    ail_str s = ail_view_to_str(v);
    uint8_t *q = (uint8_t *)malloc((size_t)(s.n > 0 ? s.n : 1) * 3);
    if (!q) ail_die("out of memory");
    int64_t o = 0;
    _Bool ascii = 1;
    for (int64_t i = 0; i < s.n; i++) {
        uint32_t c = ail_chr(s, i);
        if (c >= 0xD800 && c < 0xDC00 && i + 1 < s.n && ail_chr(s, i + 1) >= 0xDC00 && ail_chr(s, i + 1) < 0xE000)
            c = 0x10000u + ((c - 0xD800u) << 10) + ((uint32_t)ail_chr(s, ++i) - 0xDC00u);
        if (c < 0x80) { q[o++] = (uint8_t)c; continue; }
        ascii = 0;
        if (c < 0x800) q[o++] = (uint8_t)(0xC0 | (c >> 6));
        else if (c < 0x10000) { q[o++] = (uint8_t)(0xE0 | (c >> 12)); q[o++] = (uint8_t)(0x80 | ((c >> 6) & 63)); }
        else { q[o++] = (uint8_t)(0xF0 | (c >> 18)); q[o++] = (uint8_t)(0x80 | ((c >> 12) & 63)); q[o++] = (uint8_t)(0x80 | ((c >> 6) & 63)); }
        q[o++] = (uint8_t)(0x80 | (c & 63));
    }
    *owned = q;
    ail_str r; r.p = (const void *)q; r.n = o; r.bytes = ascii; return r;
}
/* A typed clone's str result (valid UTF-8 bytes) -> a boxed UTF-16 str. */
static inline ail_obj ail_mix_box_utf8(ail_ctx *cx, const uint8_t *p, int64_t n) {
    int64_t units = 0;
    for (int64_t i = 0; i < n; i++)
        if ((p[i] & 0xC0) != 0x80) units += p[i] >= 0xF0 ? 2 : 1;
    ail_strbuild b = ail_str_buf(cx, units);
    int64_t o = 0;
    for (int64_t i = 0; i < n;) {
        uint32_t c = p[i];
        int w = c < 0x80 ? 1 : c < 0xE0 ? 2 : c < 0xF0 ? 3 : 4;
        if (w == 2) c = ((c & 0x1Fu) << 6) | (p[i + 1] & 0x3Fu);
        else if (w == 3) c = ((c & 0x0Fu) << 12) | ((p[i + 1] & 0x3Fu) << 6) | (p[i + 2] & 0x3Fu);
        else if (w == 4) c = ((c & 0x07u) << 18) | ((p[i + 1] & 0x3Fu) << 12) | ((p[i + 2] & 0x3Fu) << 6) | (p[i + 3] & 0x3Fu);
        if (c >= 0x10000) {
            b.buf[o++] = (uint16_t)(0xD800u + ((c - 0x10000u) >> 10));
            b.buf[o++] = (uint16_t)(0xDC00u + ((c - 0x10000u) & 0x3FFu));
        } else b.buf[o++] = (uint16_t)c;
        i += w;
    }
    return ail_str_buf_done(b, units);
}

#endif /* AIL_MIX_CALL_H */
