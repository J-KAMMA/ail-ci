#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#ifndef AIL_LINK_STATE
#define AIL_LINK_STATE(type, name, init) static type name init
#endif
#ifndef AIL_LINK_EXPORT
#define AIL_LINK_EXPORT
#endif

typedef struct { int64_t *p; int64_t n, cap; } ail_list;
typedef struct {
    /* HASH-mode storage: populated only when `mode == AIL_TAB_HASH` (a permanent state entered by
       spilling once -- see ail_tab_arr_spill in TAB below -- and never left). */
    int64_t *key; int64_t *val; unsigned char *used; int64_t fill, cap;
    /* insertion-order key list, valid in EITHER mode: always exactly order[0 .. n). */
    int64_t *order; int64_t n, order_cap;
    /* ARRAY-mode storage: populated only when `mode == AIL_TAB_ARRAY`. arr_occ[k-lo]/arr_val[k-lo]
       are valid for lo <= k <= hi; both arrays are exactly hi - lo + 1 long. */
    unsigned char *arr_occ; int64_t *arr_val; int64_t lo, hi;
    /* BITS-mode storage: populated only when `mode == AIL_TAB_BITS`, a representation entered
       ONLY by an explicit ail_tab_bits_init the compiler emits from a range it proved -- never
       from key values seen at run time. `noorder` says this table's insertion order is provably
       never read (the compiler checked every use of the name), so `order` is not maintained at
       all and `n` is counted directly; it stays set if the table later spills. */
    uint64_t *bits; int64_t noorder;
    /* dirty-word watermark: bits[bwlo .. bwhi] are the only words that can be non-zero since the
       last clear (bwhi < bwlo means none are). Clearing a table therefore costs what the table
       actually USED, not what its compile-time span reserved -- without it, a wide span cleared
       in a loop is 7.8x slower than the run-time representation it replaced (range_risk.py). */
    int64_t bwlo, bwhi;
    int mode;   /* AIL_TAB_ARRAY (0, what a fresh {0} struct starts in), AIL_TAB_HASH (1),
                   or AIL_TAB_BITS (2, compile-time chosen -- see TAB below) */
} ail_tab;
/* Use MinGW's C jump to avoid Windows SEH stack unwinding after explicit ail_exc_unwind.
   This does not provide C++ exception unwinding. */
#if defined(__MINGW32__) && defined(__x86_64__) && !defined(__USE_MINGW_SETJMP_NON_SEH)
#define __USE_MINGW_SETJMP_NON_SEH 1
#endif
#include <setjmp.h>
#include <string.h>
/* try/except (SEMANTICS.md's exceptions section): a jmp_buf stack, one slot per currently-open
   `try`, shared by every function in the program the same way `ail_depth` (RECDEPTH) already is --
   an exception unwinds the real C call stack, so the bookkeeping for it has to live where the C
   stack itself is not: in static storage, not in any one function's locals.

   `ail_exc_top` is the index of the innermost ACTIVE handler, or -1 when none is: entering a `try`
   pushes (increments then installs), and the generated code pops (decrements) on every path out of
   that `try` -- normal completion, a matched `except`, or re-propagation past an unmatched one --
   before it can run any of ITS OWN code, so nesting composes correctly with no extra bookkeeping
   at the raise site.

   Generated cleanup callbacks run before longjmp, while the abandoned C frames and their local
   addresses are still live. The catcher records a marker and retains its own resources. */
#define AIL_EXC_MAX_DEPTH 64
typedef struct ail_cleanup_frame {
    struct ail_cleanup_frame *previous;
    void (*release)(void **);
    void **resources;
} ail_cleanup_frame;
AIL_LINK_STATE(ail_cleanup_frame *, ail_cleanup_top, = NULL);
AIL_LINK_STATE(ail_cleanup_frame *, ail_exc_cleanup[AIL_EXC_MAX_DEPTH], );
AIL_LINK_STATE(jmp_buf, ail_exc_stack[AIL_EXC_MAX_DEPTH], );
AIL_LINK_STATE(int, ail_exc_top, = -1);
AIL_LINK_STATE(int, ail_exc_code, = 0); /* set just before a longjmp; read once control lands */
static void ail_exc_unwind(void) {
    ail_cleanup_frame *stop = ail_exc_cleanup[ail_exc_top];
    while (ail_cleanup_top != stop) {
        ail_cleanup_frame *frame = ail_cleanup_top;
        ail_cleanup_top = frame->previous;
        frame->release(frame->resources);
    }
}
enum { AIL_EXC_VALUE = 1, AIL_EXC_ZERODIV = 2, AIL_EXC_INDEX = 3, AIL_EXC_KEY = 4, AIL_EXC_EOF = 5,
       AIL_EXC_OS = 6, AIL_EXC_RUNTIME = 7, AIL_EXC_UNICODE_DECODE = 8 };
/* Maps an EXISTING ail_die() trap message onto a catchable exception, exactly where
   SEMANTICS says doing so is coherent. Every other message -- "out of memory", "recursion depth
   exceeded", "integer overflow", and everything else this runtime already stops on -- returns 0
   and stays exactly what it always was: unconditional and uncatchable. */
static int ail_exc_kind_of(const char *w) {
    if (!strcmp(w, "min() of an empty sequence") || !strcmp(w, "max() of an empty sequence")
        || !strcmp(w, "C int8 argument out of range") || !strcmp(w, "C uint8 argument out of range")
        || !strcmp(w, "C int16 argument out of range") || !strcmp(w, "C uint16 argument out of range")
        || !strcmp(w, "C int32 argument out of range") || !strcmp(w, "C uint32 argument out of range")
        || !strcmp(w, "C bool argument out of range")
        || !strcmp(w, "C cstr contains NUL")
        || !strcmp(w, "C float32 argument out of range") || !strcmp(w, "C float32 result is not finite")
        || !strcmp(w, "bytes must be in range(0, 256)"))
        return AIL_EXC_VALUE;
    if (!strcmp(w, "division by zero") || !strcmp(w, "integer division by zero")
        || !strcmp(w, "integer modulo by zero")) return AIL_EXC_ZERODIV;
    if (!strcmp(w, "list index out of range") || !strcmp(w, "pop index out of range")
        || !strcmp(w, "pop from empty list") || !strcmp(w, "grid row index out of range")
        || !strcmp(w, "grid column index out of range") || !strcmp(w, "bytes index out of range"))
        return AIL_EXC_INDEX;
    if (!strcmp(w, "key error")) return AIL_EXC_KEY;
    if (!strcmp(w, "dictionary changed size during iteration")) return AIL_EXC_RUNTIME;
    if (!strcmp(w, "file is not valid UTF-8"))
        return AIL_EXC_UNICODE_DECODE;
    return 0;
}
static void ail_die(const char *w) {
    /* Unchanged for every program that never opens a `try`: ail_exc_top stays -1 for the whole
       run, this branch is never taken, and everything below is byte-for-byte what pkg-v6 already
       does. Only a program that DOES open a `try` pays this one extra comparison, and only on the
       failure path a trap already was -- never on the path that succeeds. */
    if (ail_exc_top >= 0) {
        int k = ail_exc_kind_of(w);
        if (k) { ail_exc_code = k; ail_exc_unwind(); longjmp(ail_exc_stack[ail_exc_top], 1); }
    }
    /* `fflush(stdout)` here is F3's correctness fix, not a new feature (DESIGN_FOUNDATION_20260914.md
       section 5): `_Exit` never flushes stdio buffers, and stdout is fully buffered whenever it is
       not a terminal -- the normal case for a judge or a pipeline. Before F3 no program could ever
       write to stdout, so this path was dead code; now a `print()` right before a trap needs its
       output to survive the trap, or it silently vanishes. Costs one call, on the already-failing
       (and uncaught) path only -- never reached by a program that does not trap, so it is
       invisible to every speed measurement in this tree (see APP_WEIGHT_AND_SPEED_20260913.md;
       none of it runs a trap). Destination and exit status are unchanged: stderr, then _Exit(1). */
    fflush(stdout); fputs(w, stderr); fputc(10, stderr); _Exit(1);
}
static void *ail_alloc(size_t n) { void *p = calloc(n, 1); if (!p) ail_die("out of memory"); return p; }
/* A program's own `raise <Name>()`, and where a converted runtime trap goes once nothing is left
   to catch it: the same two destinations ail_die already has -- longjmp to an active handler, or
   the original fatal stop -- naming the exception directly since there is no trap message to
   reuse here.

   `fflush(stdout)` before the fatal stop is the SAME F3 correctness fix `ail_die` just above
   already has, and was MISSING here until scope item 4 of AIL_TASK_stdio_20260915.md needed it:
   `int(<str>)` on bad input raises ValueError through exactly this uncaught path, and a `print()`
   that already ran before it needs its output to survive -- `_Exit` still does not flush on its
   own, this function is the other of the two places that call it directly, and a WRONG on
   whole40's stdout comparison (not merely a wrong exit status) was the untested consequence of
   leaving it out. */
static void ail_raise_named(int code) {
    if (ail_exc_top >= 0) { ail_exc_code = code; ail_exc_unwind(); longjmp(ail_exc_stack[ail_exc_top], 1); }
    static const char *ail_exc_names[] =
        {"", "ValueError", "ZeroDivisionError", "IndexError", "KeyError", "EOFError", "OSError",
         "RuntimeError", "UnicodeDecodeError"};
    fflush(stdout); fputs(ail_exc_names[code], stderr); fputc(10, stderr); _Exit(1);
}
/* stdout-dirty flag: set by every path that can leave bytes in stdout's buffer
   (ail_str_write when f==stdout, ail_print_float/ail_write_float, and the
   ail_stdout_putc/ail_fputs_stdout helpers the emitted print code calls).
   `ail_stdin_flush_stdout` (in STR) consults it before an actual OS read,
   instead of paying for a locked libc fflush call on every buffered line.
   Prompt-before-read ordering still holds when input blocks for a reply.
   `ail_die`/assert paths keep their own unconditional fflush(stdout) before
   _Exit. Lives in its OWN fragment because emitted print() code calls these
   helpers even when nothing else pulls STR (print-only programs linked
   without it until this fragment existed -- rt18). */
AIL_LINK_STATE(int, ail_stdout_dirty, = 0);
AIL_LINK_STATE(int, ail_stdout_kind, = 0);
static void ail_stdout_text(void) {
    if (ail_stdout_kind == 2) ail_raise_named(AIL_EXC_VALUE);
    ail_stdout_kind = 1;
}
static int ail_stdout_putc(int c) { ail_stdout_dirty = 1; return fputc(c, stdout); }
static int ail_fputs_stdout(const char *x) { ail_stdout_dirty = 1; return fputs(x, stdout); }
/* print(<int>)'s writer -- the typed counterpart of what the boxed path already does through
   ail__itoa (OBJ/OBJ2): '-' + decimal digits built in one stack buffer, one fwrite, no
   format-string parse. Byte-identical to printf("%lld") by construction; INT64_MIN-safe via
   the same `0ULL - (unsigned long long)v` unsigned negation ail__itoa uses (v itself is never
   negated). */
static void ail_write_int_to(int64_t v, FILE *f) {
    char b[24], tmp[24]; int64_t n = 0;
    unsigned long long u = v < 0 ? 0ULL - (unsigned long long)v : (unsigned long long)v;
    do { tmp[n++] = (char)('0' + (int)(u % 10)); u /= 10; } while (u);
    int64_t o = 0;
    if (v < 0) b[o++] = '-';
    while (n) b[o++] = tmp[--n];
    if (f == stdout) ail_stdout_dirty = 1;
    fwrite(b, 1, (size_t)o, f);
}
static void ail_write_int(int64_t v) { ail_write_int_to(v, stdout); }

/* SEMANTICS.md section 29. `str` is an immutable sequence of Unicode scalar values.
   The current typed runtime stores UTF-16 units in uint16_t slots; length, indexing,
   slicing and ordering decode surrogate pairs before applying Python's character semantics.
   ASCII-only strings may instead use compact byte storage.

   That representation was chosen from a measurement, not a preference. `oracle_str_probe.py`
   compiled BOTH candidates and ran them against CPython over 1426 cases on a 17-string corpus
   (13 non-ASCII: NFC and NFD forms, Japanese, an astral emoji, U+10FFFF):

       operation   code-point str        utf-8-byte str
       len            17 agree  0 wrong     4 agree  13 WRONG
       index          47 agree  0 wrong    25 agree  22 WRONG
       slice         206 agree  0 wrong   156 agree  50 WRONG
       eq/lt/le      867 agree  0 wrong   867 agree   0 wrong
       concat        289 agree  0 wrong   289 agree   0 wrong

   This historical measurement compared a 32-bit code-point representation with UTF-8 bytes.
   Its results do not measure the current 16-bit representation or these decoding helpers. */
#include <string.h>

typedef struct { const uint16_t *p; int64_t n; _Bool bytes; } ail_str;
/* `bytes` is 1 only for a string proven pure ASCII, whose elements are
   uint8_t. For ASCII a byte element IS the uint16 element value and the
   unit count IS the byte count, so `.n` and every read keep their
   meaning -- only the dereference width changes, and ail_chr is the one
   place that knows it. */
/* the one place that knows the element width; declared here because
   comparisons use it earlier */
static inline uint16_t ail_chr(ail_str s, int64_t i);
static inline size_t ail_str_esz(ail_str s);
static inline ail_str ail_view(ail_str s, int64_t i);
static inline void ail_str_put(uint16_t *dst, ail_str s);
static inline int64_t ail_str_next_unit(ail_str s, int64_t i) {
    uint16_t c = ail_chr(s, i);
    return (!s.bytes && c >= 0xD800 && c < 0xDC00 && i + 1 < s.n &&
            ail_chr(s, i + 1) >= 0xDC00 && ail_chr(s, i + 1) < 0xE000) ? i + 2 : i + 1;
}
static inline int64_t ail_str_prev_unit(ail_str s, int64_t end) {
    return (!s.bytes && end >= 2 &&
            ail_chr(s, end - 2) >= 0xD800 && ail_chr(s, end - 2) < 0xDC00 &&
            ail_chr(s, end - 1) >= 0xDC00 && ail_chr(s, end - 1) < 0xE000)
           ? end - 2 : end - 1;
}
static inline uint32_t ail_str_point(ail_str s, int64_t i) {
    uint32_t c = ail_chr(s, i);
    if (ail_str_next_unit(s, i) == i + 2)
        c = 0x10000u + ((c - 0xD800u) << 10) + (ail_chr(s, i + 1) - 0xDC00u);
    return c;
}
static int64_t ail_str_len_points(ail_str s) {
    if (s.bytes) return s.n;
    int64_t n = 0;
    for (int64_t i = 0; i < s.n; i = ail_str_next_unit(s, i)) n++;
    return n;
}
static int64_t ail_str_unit_at(ail_str s, int64_t point) {
    int64_t i = 0;
    while (point-- > 0 && i < s.n) i = ail_str_next_unit(s, i);
    return i;
}

/* A non-ASCII str LITERAL is emitted as a `u"..."` char16_t string literal cast to
   `const uint16_t *`, so it has STATIC storage duration -- a compound literal would have automatic
   storage and a `str` local assigned inside an `if` block would dangle the moment the block ended.
   This assertion fails the BUILD if char16_t is ever not two bytes here, rather than letting the
   cast be silently wrong. Pure-ASCII literals use an ordinary byte string and do not depend on it. */
typedef int ail__str_lit_width[(sizeof(u"a") == 2 * sizeof(uint16_t)) ? 1 : -1];

/* Both an index and a slice are VIEWS: one character may occupy one or two UTF-16 units,
   but the view still allocates nothing, exactly as `ail_bytes_slice` is for bytes. Only concatenation and
   `str(n)` allocate, into this arena, freed at return with every other container.

   `top`, `tlen` and `tcap` describe the NEWEST block only, and exist so that `s = s + t` in a loop
   can append into room already allocated instead of copying the whole accumulated string into a
   fresh buffer every time. Without them that loop is quadratic in BOTH time and memory, because
   the arena is released only at return and so every intermediate stays alive: 20,000
   single-character appends cost 809.6 ms and 764.9 MB, and 40,000 exceeded a 3 GB address-space
   cap (measured 2026-09-15; it had already taken the whole VM down twice before the cap went on).
   CPython agrees on the ANSWER at every size, which is why no judge, no fuzzer and no gate here
   had ever seen it -- all of them compare return values. */
/* FOUR append targets, not one.

   One was a defect, found 2026-09-15 by an outside review that compiled these functions with
   allocation and copy counters and measured the plainest possible program:

       s = ""; t = ""
       for i in range(n): s = s + "x"; t = t + "x"

   Growing `t` made `s` stop being the single top, so growing `s` took the allocation branch, which
   made `t` stop being top, and so on: every append copied its whole prefix and retained the old
   block. Measured 1,000 / 2,000 / 4,000 appends -> 4.0 / 16.0 / 64.1 MB copied. Quadratic, on a
   program with nothing unusual in it, while the single-accumulator case was linear and I had
   published "linear" on the strength of that one.

   A table of four, searched linearly, is the whole fix: it costs four comparisons on the append
   path and it makes any program with up to four simultaneous accumulators linear. It is not a
   general answer -- five interleaved accumulators thrash it exactly as two thrashed one, and
   `test_strgrow.py` says so rather than leaving it to be rediscovered. The alternative, a header
   before each block so any pointer could find its own capacity, cannot be used here: `ail_str.p`
   may point into the MIDDLE of a block (every slice does), so reading backwards from it is not
   sound. */
#define AIL_SARENA_TOPS 4
#define AIL_SARENA_INLINE 8
typedef struct {
    uint16_t **blk; int64_t n, cap;
    int64_t *bcap;                 /* parallel to blk: element capacity, 0 = unknown */
    uint16_t *blk0[AIL_SARENA_INLINE];   /* inline slots: first pushes cost no malloc */
    int64_t bcap0[AIL_SARENA_INLINE];
    uint16_t *top[AIL_SARENA_TOPS];
    int64_t tlen[AIL_SARENA_TOPS], tcap[AIL_SARENA_TOPS], trun[AIL_SARENA_TOPS];
    int64_t tnext;                     /* round-robin slot for the next new target */
} ail_sarena;

/* `s[i]` in Python is a one-character STR, not a number. That is the whole difference from
   `b[i]` (which is an int 0..255), and reproducing it exactly is why this returns `ail_str`. */
/* `s` ends with `suffix` starting at unit `off`. Per unit, because a
   byte-backed string's pointer offset is in BYTES while the offset here is in
   units -- memcmp over `s.p + off` would compare the wrong characters. */
/* `s` starts with `prefix`. Per unit, because a byte-backed string's elements
   are bytes and a memcmp of `n * sizeof(uint16_t)` would read past it. */
static int ail_str_prefix_eq(ail_str s, ail_str prefix) {
    if (prefix.n == 0) return 1;
    if (prefix.n > s.n) return 0;
    for (int64_t i = 0; i < prefix.n; i++) {
        if (ail_chr(s, i) != ail_chr(prefix, i)) return 0;
    }
    return 1;
}

static int ail_str_suffix_eq(ail_str s, int64_t off, ail_str suffix) {
    if (suffix.n == 0) return 1;
    if (off < 0 || off + suffix.n > s.n) return 0;
    for (int64_t i = 0; i < suffix.n; i++) {
        if (ail_chr(s, off + i) != ail_chr(suffix, i)) return 0;
    }
    return 1;
}

static ail_str ail_str_index(ail_str s, int64_t i) {
    int64_t n = ail_str_len_points(s);
    if (i < 0) i += n;                       /* Python indexes from the end */
    if (i < 0 || i >= n) ail_die("string index out of range");
    int64_t unit = ail_str_unit_at(s, i);
    ail_str r = ail_view(s, unit); r.n = ail_str_next_unit(s, unit) - unit; return r;
}

/* JavaScript String.prototype.charAt returns the empty string out of range;
   bracket indexing and codePointAt have different undefined semantics and do
   not use this helper. */
static ail_str ail_str_charat(ail_str s, int64_t i) {
    if (i < 0 || i >= s.n) return (ail_str){0, 0};
    ail_str r = ail_view(s, i); r.n = 1; return r;
}

/* The same view when the caller has ALREADY proved `0 <= i < s.n` for a UNIT offset -- which a
   `for c in s` loop has, by its own bound. The three checks in ail_str_index
   are then dead work, and on a scan they are per character: measured at 1.085x
   on a 26 MB four-pass scan. Only the loop emitter uses this; `s[i]` still
   goes through the checked form. */
static ail_str ail_str_index_nc(ail_str s, int64_t i) {
    ail_str r = ail_view(s, i); r.n = ail_str_next_unit(s, i) - i; return r;
}
static ail_str ail_str_slice(ail_str s, int64_t lo, int64_t hi) {
    /* Python clamps a slice and never raises, however far out the bounds are. */
    int64_t n = ail_str_len_points(s);
    if (lo < 0) { lo += n; if (lo < 0) lo = 0; } else if (lo > n) lo = n;
    if (hi < 0) { hi += n; if (hi < 0) hi = 0; } else if (hi > n) hi = n;
    if (hi < lo) hi = lo;
    int64_t first = ail_str_unit_at(s, lo), last = ail_str_unit_at(s, hi);
    ail_str r = ail_view(s, first); r.n = last - first; return r;
}
/* Python orders str by Unicode scalar value, then by length. Comparing UTF-16 units
   directly would put an astral character before some BMP characters in error. */
static int64_t ail_str_cmp(ail_str a, ail_str b) {
    int64_t i = 0, j = 0;
    while (i < a.n && j < b.n) {
        uint32_t x = ail_str_point(a, i), y = ail_str_point(b, j);
        if (x != y) return x < y ? -1 : 1;
        i = ail_str_next_unit(a, i);
        j = ail_str_next_unit(b, j);
    }
    return i == a.n && j == b.n ? 0 : (i == a.n ? -1 : 1);
}
/* Equality CAN use memcmp: it only ever asks whether the slot bytes are identical, which is
   endian-independent, and the lengths are compared first. */
static int64_t ail_str_eq(ail_str a, ail_str b) {
    if (a.n != b.n) return 0;
    if (a.n == 0) return 1;
    if (a.bytes == b.bytes)
        return memcmp(a.p, b.p, (size_t)a.n * ail_str_esz(a)) == 0;
    for (int64_t i = 0; i < a.n; i++)
        if (ail_chr(a, i) != ail_chr(b, i)) return 0;
    return 1;
}
static void ail__tops_clear(ail_sarena *A) {
    for (int i = 0; i < AIL_SARENA_TOPS; i++) {
        A->top[i] = 0; A->tlen[i] = A->tcap[i] = A->trun[i] = 0;
    }
    A->tnext = 0;
}
/* Sized arena blocks recycle through a small process-wide cache: the per-line malloc/
   free pair was the dominant remaining cost of the stdin path (measured by a
   scratch-buffer probe at ~1.5x of wall time). A block enters only where it would
   have been freed, so lifetimes are unchanged; unsized pushes (cap 0) still free.
   The cache is bounded so outsized blocks (a 70MB line) never linger. */
#define AIL_BLK_CACHE_MAX 32
#define AIL_BLK_CACHE_BYTES (4u << 20)
AIL_LINK_STATE(struct { uint16_t *p; int64_t cap; }, ail__blk_cache[AIL_BLK_CACHE_MAX], );
AIL_LINK_STATE(int64_t, ail__blk_cache_n, = 0);
AIL_LINK_STATE(size_t, ail__blk_cache_bytes, = 0);
static void ail__blk_cache_put(uint16_t *p, int64_t cap) {
    size_t bytes = (size_t)cap * sizeof(uint16_t);
    if (ail__blk_cache_n >= AIL_BLK_CACHE_MAX ||
        ail__blk_cache_bytes + bytes > AIL_BLK_CACHE_BYTES) { free(p); return; }
    ail__blk_cache[ail__blk_cache_n].p = p;
    ail__blk_cache[ail__blk_cache_n].cap = cap;
    ail__blk_cache_n++; ail__blk_cache_bytes += bytes;
}
static uint16_t *ail__blk_cache_take(int64_t need) {
    int64_t best = -1;
    for (int64_t i = 0; i < ail__blk_cache_n; i++)
        if (ail__blk_cache[i].cap >= need &&
            (best < 0 || ail__blk_cache[i].cap < ail__blk_cache[best].cap)) best = i;
    if (best < 0) return 0;
    uint16_t *p = ail__blk_cache[best].p;
    ail__blk_cache_bytes -= (size_t)ail__blk_cache[best].cap * sizeof(uint16_t);
    ail__blk_cache[best] = ail__blk_cache[--ail__blk_cache_n];
    return p;
}
static void ail__blk_release(uint16_t *p, int64_t cap) {
    if (cap > 0) ail__blk_cache_put(p, cap); else free(p);
}
static void ail__sarena_arrays_free(ail_sarena *A) {
    if (A->blk && A->blk != A->blk0) free(A->blk);
    if (A->bcap && A->bcap != A->bcap0) free(A->bcap);
    A->blk = 0; A->bcap = 0; A->n = A->cap = 0;
}
static void ail_sarena_free(ail_sarena *A) {
    for (int64_t i = 0; i < A->n; i++)
        ail__blk_release(A->blk[i], A->bcap ? A->bcap[i] : 0);
    ail__sarena_arrays_free(A);
    ail__tops_clear(A);
}
/* For a proven nonescaping stdin loop, retain its current readline allocation
   and everything preceding the loop. The final target remains valid after EOF/break. */
static void ail_sarena_keep_line(ail_sarena *A, int64_t mark, const uint16_t *keep) {
    if (mark < 0 || mark > A->n) ail_die("invalid stdin arena checkpoint");
    int64_t end = A->n, write = mark;
    for (int64_t i = mark; i < end; i++) {
        if (A->blk[i] == keep) {
            A->blk[write] = A->blk[i];
            if (A->bcap) A->bcap[write] = A->bcap[i];
            write++;
        } else ail__blk_release(A->blk[i], A->bcap ? A->bcap[i] : 0);
    }
    A->n = write;
    ail__tops_clear(A);
}
/* A push does NOT clear the append targets, and getting that wrong is what made the four-slot
   table useless on its first run: every push cleared every slot, so the second accumulator's
   allocation evicted the first one's entry and the two thrashed exactly as they had with a single
   slot.

   Nothing a push does can falsify a slot. A slot is the triple (block pointer, committed length,
   capacity) for a block this function allocated; the arena never frees an individual block, no
   other producer writes into one, and allocating a NEW block somewhere else changes none of those
   three facts. Only `ail_sarena_free` invalidates a slot, and it clears them all. The single-slot
   version cleared here because its concept was "the newest block", which a later push really did
   falsify -- the concept changed, and the clearing should have gone with it. */
/* How many elements of type T can be multiplied by sizeof(T) and still be representable. Compared
   in UNSIGNED arithmetic BEFORE the multiplication, because `calloc` cannot repair a product that
   already wrapped before the allocator received it -- an outside review demonstrated exactly that
   here: a synthetic n == 2**62 - 1 gave want == 2**62 and an allocation byte count of ZERO, with
   nothing reporting it, since `-fsanitize=undefined` does not include unsigned wraparound. */
#define AIL_ELEM_LIMIT(T) ((uintmax_t)SIZE_MAX / (uintmax_t)sizeof(T))
static void ail__need_elems(int64_t n, uintmax_t limit) {
    if (n < 0 || (uintmax_t)n >= limit) ail_die("allocation too large");
}
/* The arena's block bookkeeping counts uint16 ELEMENTS: `bcap` is what the
   block cache is told on release, and what compaction and the liveness test use
   as the block's extent. A BYTE-backed block is `nb` bytes, so pushing `nb`
   elements would tell all three that it is twice its real size -- and the cache
   would hand it out again for a write of that size. This is the element count
   that is never larger than the real one. */
static inline int64_t ail_bytes_elems(int64_t nb) { return nb / 2; }

static void ail_sarena_pushn(ail_sarena *A, uint16_t *q, int64_t cap) {
    if (A->n == A->cap) {
        if (!A->cap) {
            /* First pushes use the inline slots -- a compiled function whose arena
               never exceeds them pays no array allocation at all (the stdin line
               reader is exactly that case). */
            A->blk = A->blk0; A->bcap = A->bcap0; A->cap = AIL_SARENA_INLINE;
        } else {
            /* `A->cap * 2` can overflow int64 before it is ever converted, and the byte count needs
               its own check against `sizeof *nb` rather than sizeof(uint16_t). */
            if (A->cap > INT64_MAX / 2) ail_die("allocation too large");
            int64_t c = A->cap * 2;
            ail__need_elems(c, AIL_ELEM_LIMIT(uint16_t *));
            uint16_t **nb = (uint16_t **)ail_alloc((size_t)c * sizeof *nb);
            memcpy(nb, A->blk, (size_t)A->n * sizeof *nb);
            int64_t *ncb = (int64_t *)ail_alloc((size_t)c * sizeof *ncb);
            memcpy(ncb, A->bcap, (size_t)A->n * sizeof *ncb);
            /* Free only heap arrays -- the inline slots are struct storage. */
            if (A->blk != A->blk0) free(A->blk);
            if (A->bcap != A->bcap0) free(A->bcap);
            A->blk = nb; A->bcap = ncb; A->cap = c;
        }
    }
    A->blk[A->n] = q; A->bcap[A->n] = cap; A->n++;
}
static void ail_sarena_push(ail_sarena *A, uint16_t *q) {
    ail_sarena_pushn(A, q, 0);
}
/* AIL_TASK_strcontainers_20260916.md: a plain, general-purpose "give me N owned code-point slots"
   allocator on top of `ail_sarena_push` just above -- exactly the primitive calling another
   compiled function that returns str needs for its own out-buffer (see `ail_str_return`'s
   calling convention, used at every C-to-C call site now, not only by the top-level entry
   point), freed the same way and at the same point as every other value this arena ever hands
   out: once, at this call's own return. Unlike `ail_str_cat`'s own allocation just below, this
   never tracks the result as an appendable "top" -- the caller fills it itself, in one write,
   immediately after. */
static uint16_t *ail_sarena_alloc(ail_sarena *A, int64_t n) {
    ail__need_elems(n, AIL_ELEM_LIMIT(uint16_t));
    uint16_t *q = (uint16_t *)ail_alloc((size_t)(n > 0 ? n : 1) * sizeof(uint16_t));
    ail_sarena_push(A, q);
    return q;
}
/* Only emitted for a closed set of local string roots. Copy every live view
   before freeing any backing block: slices and aliases may overlap. Earlier
   arena allocations are owned by the enclosing scope and remain untouched. */
static void ail_sarena_keep_roots(ail_sarena *A, int64_t mark, ail_str **roots, int64_t count) {
    if (mark < 0 || mark > A->n) ail_die("invalid stdin arena checkpoint");
    if (A->n == mark) return;
    /* Block-granular retention, not per-str copying. A root whose block is
       MOVED below the mark keeps the same pointer, so every view, slice,
       split field and cached iterable into that block stays valid untouched
       -- and, the part that makes this O(blocks) instead of O(bytes), an
       accumulator root like `s = s + str(i)` is a block-START root whose block
       moves once instead of being re-copied every iteration, and whose append
       "top" slot below survives so the next += still extends in place. The
       copy-everything version this replaces went quadratic on exactly that
       shape. The only roots a block move cannot preserve are ones pointing
       into the MIDDLE of an UNSIZED block (bcap 0 -- the extent is not
       recorded, so containment cannot be proven); those few still get the old
       copy while all original backing blocks are still live. */
    int64_t end = A->n, write = mark;
    /* Establish ownership of every unproven view before releasing blocks.
       Copies remain in the same arena, and duplicate entries referring to
       the same root slot see the new copy. */
    for (int64_t r = 0; r < count; r++) {
        ail_str s = *roots[r];
        if (!s.p) continue;
        int alive = 0;
        for (int64_t j = 0; j < A->n; j++) {
            if (s.p == A->blk[j]) { alive = 1; break; }
            if (A->bcap && A->bcap[j] > 0
                    && (uintptr_t)s.p > (uintptr_t)A->blk[j]
                    && ((uintptr_t)s.p - (uintptr_t)A->blk[j]) / sizeof(uint16_t)
                       < (uintmax_t)A->bcap[j]) { alive = 1; break; }
        }
        if (!alive) {
            uint16_t *np = ail_sarena_alloc(A, s.n);
            if (s.n) {
                if (s.bytes) memcpy((uint8_t *)np, (const uint8_t *)s.p, (size_t)s.n);
                else memcpy(np, s.p, (size_t)s.n * sizeof *np);
            }
            roots[r]->p = np;
        }
    }
    for (int64_t i = mark; i < end; i++) {
        int keep = 0;
        for (int64_t i2 = 0; i2 < count && !keep; i2++) {
            const uint16_t *p = roots[i2]->p;
            if (!p) continue;
            if (p == A->blk[i]) keep = 1;
            else if (A->bcap && A->bcap[i] > 0
                     && (uintptr_t)p > (uintptr_t)A->blk[i]
                     && ((uintptr_t)p - (uintptr_t)A->blk[i]) / sizeof(uint16_t)
                        < (uintmax_t)A->bcap[i]) keep = 1;
        }
        if (keep) {
            if (write != i) {
                A->blk[write] = A->blk[i];
                if (A->bcap) A->bcap[write] = A->bcap[i];
            }
            write++;
        } else {
            ail__blk_release(A->blk[i], A->bcap ? A->bcap[i] : 0);
        }
    }
    /* Preserve the newly owned copies after compacting only the original range.
       Forward moves are safe when these source/destination ranges overlap. */
    for (int64_t i = end; i < A->n; i++) {
        A->blk[write] = A->blk[i];
        if (A->bcap) A->bcap[write] = A->bcap[i];
        write++;
    }
    A->n = write;
    /* Append slots hold block POINTERS, so moved blocks keep theirs; slots
       pointing at a block that was just released must be dropped or the next
       append-in-place would write into freed memory. Everything else stays:
       keeping the accumulator's slot is what keeps `s += ...` linear here. */
    for (int i = 0; i < AIL_SARENA_TOPS; i++) {
        if (!A->top[i]) continue;
        int alive = 0;
        for (int64_t j = 0; j < A->n; j++)
            if (A->blk[j] == A->top[i]) { alive = 1; break; }
        if (!alive) { A->top[i] = 0; A->tlen[i] = A->tcap[i] = A->trun[i] = 0; }
    }
}
static ail_str ail_str_cat(ail_sarena *A, ail_str a, ail_str b) {
    if (a.n > INT64_MAX - b.n) ail_die("string too long");
    int64_t n = a.n + b.n;
    _Bool bytes = a.bytes && b.bytes;
    /* Append in place when `a` is the WHOLE of the newest block and the room is already there.
       Nothing is moved and no code point that already exists is rewritten -- only slots past
       `tlen`, which no str can be pointing at, are touched. So every older view, including one
       aliasing `a` itself and any slice of it, keeps exactly the length and exactly the contents
       it had; that is why this needs no aliasing analysis, only the two equalities below.
       `a.n == A->tlen` is the load-bearing half: a str SHORTER than the block would otherwise
       append over code points a longer alias can still see. */
    int slot = -1;
    for (int i = 0; i < AIL_SARENA_TOPS; i++)
        if (a.p == A->top[i] && a.n == A->tlen[i]) { slot = i; break; }
    /* A byte-backed top can stay in place only while the result stays byte-backed. If `b` is
       u16, promotion needs a fresh u16 block; treating the byte buffer as uint16_t here would
       write at twice the intended offset and past its allocation. */
    if (slot >= 0 && a.bytes == bytes && A->tcap[slot] - a.n > b.n) {
        if (bytes) {
            if (b.n) memcpy((uint8_t *)A->top[slot] + a.n, (const uint8_t *)b.p, (size_t)b.n);
        } else {
            ail_str_put(A->top[slot] + a.n, b);
        }
        A->tlen[slot] = n;               /* slot n is already zero: ail_alloc is calloc */
        if (A->trun[slot] < 3) A->trun[slot]++;   /* saturates; see the fresh branch below */
        ail_str r; if (bytes) r.bytes = 1; else r.bytes = 0;
        r.p = A->top[slot];  r.n = n; return r;
    }
    /* Otherwise a fresh block, and the only question is how much room to ask for.

       Doubling unconditionally on an append was measured SLOWER on k-nucleotide -- 0.82x and
       0.86x at two input sizes -- because that program builds a two-part key millions of times and
       never a third time, so every double was a calloc of room nothing would ever use. `trun`
       counts how long this chain of appends has been running, and the doubling waits until the
       third: a two-step build still allocates exactly what it uses, and a loop still becomes a
       geometric series after one extra step. */
    /* `run` SATURATES at 3. `A->trun[slot] + 1` is unbounded otherwise -- including under repeated
       concatenation with an empty string -- and nothing here distinguishes four from four billion.
       Written as a saturating compare and not as `min(trun + 1, 3)`, which computes the
       overflowing expression first. */
    int64_t run = (slot >= 0) ? (A->trun[slot] >= 3 ? 3 : A->trun[slot] + 1) : 1;
    /* The guard at the top of this function establishes `a.n + b.n <= INT64_MAX`. It does NOT
       establish `a.n + b.n + 1 <= INT64_MAX`, and at a.n == INT64_MAX with b.n == 0 the `n + 1`
       below overflowed before the doubling condition was even considered -- an outside review's
       boundary probe reported it as
           signed integer overflow: 9223372036854775807 + 1 cannot be represented in 'int64_t'.
       The element limit is checked first, in unsigned arithmetic, so the reservation of the
       terminator and the byte-count multiplication are both representable by the time they run. */
    uintmax_t lim = AIL_ELEM_LIMIT(uint16_t);
    if (lim > (uintmax_t)INT64_MAX) lim = (uintmax_t)INT64_MAX;
    if ((uintmax_t)n >= lim) ail_die("string too long");      /* must reserve one element */
    int64_t want = n + 1;
    if (run >= 3 && (uintmax_t)n < lim / 2 - 1) want = 2 * n + 2;
    ail__need_elems(want, AIL_ELEM_LIMIT(uint16_t));
    uint16_t *q;
    if (bytes) {
        uint8_t *qb = (uint8_t *)ail_alloc((size_t)want);
        if (a.n) memcpy(qb, (const uint8_t *)a.p, (size_t)a.n);
        if (b.n) memcpy(qb + a.n, (const uint8_t *)b.p, (size_t)b.n);
        q = (uint16_t *)qb;
        ail_sarena_pushn(A, q, ail_bytes_elems(want));
    } else {
        q = (uint16_t *)ail_alloc((size_t)want * sizeof(uint16_t));
        ail_str_put(q, a);
        ail_str_put(q + a.n, b);
        ail_sarena_push(A, q);
    }
    /* Reuse this chain's own slot when it had one, so a growing string keeps its place instead of
       evicting a neighbour on every reallocation. Otherwise take the slot with the SHORTEST append
       streak -- an empty one first, then the least-established chain.

       Round-robin was measured wrong, by work counters, on a program with only ONE real
       accumulator:

           s = ""
           for i in range(n): s = s + str(i) + "x"

       The one-off `str(i) + "x"` concatenations take the fresh branch with no slot of their own, so
       under round-robin they walked `tnext` around the table and periodically landed on `s`'s slot,
       evicting it and resetting its doubling progress. Bytes copied grew x3.98 per doubling --
       quadratic, in a shape real programs are full of (fasta builds a line this way). The four-slot
       table protected four NAMED accumulators from each other and did not protect one accumulator
       from a stream of temporaries that never needed protecting at all.

       `trun` already distinguishes them: a one-off has 1, an established chain saturates at 3. So
       the victim is the lowest `trun`, and temporaries evict each other.

       WHAT THIS DID NOT DO: it did not make any real program faster. All four Benchmarks
       Game programs here concatenate inside a loop, but none combines an UNBOUNDED
       accumulator with allocating temporaries -- fasta's line stops at 60 characters,
       revcomp's `seq` grows without any temporary beside it (`s[k]` is a view, not an
       allocation), and k-nucleotide's and binary-trees' `str()` temporaries sit next to
       accumulators two characters long. Measured across the two policies: byte-identical
       output and peak RSS 27.6/27.6, 54.4/54.4, 27.9/27.9, 6.5/6.4 MB -- NOT SEPARATED.
       This removed a cliff the corpus does not stand on. Re-run out/neg/ab_realprog.py. */
    int64_t k = slot;
    if (k < 0) {
        k = 0;
        for (int i = 1; i < AIL_SARENA_TOPS; i++) {
            if (A->top[i] == 0) { k = i; break; }          /* an empty slot costs nothing */
            if (A->trun[i] < A->trun[k]) k = i;
        }
    }
    A->top[k] = q; A->tlen[k] = n; A->tcap[k] = want; A->trun[k] = run;
    ail_str r; if (bytes) r.bytes = 1; else r.bytes = 0;
    r.p = q;  r.n = n; return r;
}
/* f-string/.format/%-format/concat chains of THREE OR MORE parts: one allocation, one copy
   pass, instead of the pairwise ail_str_cat chain's per-step fresh blocks (a one-off chain
   never reaches the doubling threshold, so each intermediate step re-copied the whole
   accumulated prefix). The result is registered as an appendable top exactly like a fresh
   ail_str_cat result, so a following `s = s + tail` still gets the in-place path. */
static ail_str ail_str_catn(ail_sarena *A, ail_str *parts, int64_t nparts) {
    int64_t n = 0;
    _Bool bytes = 1;
    for (int64_t i = 0; i < nparts; i++) {
        if (parts[i].n > INT64_MAX - n) ail_die("string too long");
        n += parts[i].n;
        if (!parts[i].bytes) bytes = 0;
    }
    uintmax_t lim = AIL_ELEM_LIMIT(uint16_t);
    if (lim > (uintmax_t)INT64_MAX) lim = (uintmax_t)INT64_MAX;
    if ((uintmax_t)n >= lim) ail_die("string too long");      /* must reserve one element */
    /* `s = s + a + b` in a loop is the SAME append run as `s = s + x`, and the
       pairwise form takes the in-place path below; this one used to always
       allocate, which made an accumulator quadratic -- ccat -n went 23 ms to
       2710 ms from 37 KB to 295 KB, 1621x a streaming C reference. The same two
       equalities as ail_str_cat, for the same reason: only slots past tlen are
       touched, so every older view keeps its length and its contents. */
    int slot = -1;
    if (nparts > 0 && parts[0].n > 0) {
        for (int i = 0; i < AIL_SARENA_TOPS; i++)
            if (parts[0].p == A->top[i] && parts[0].n == A->tlen[i]) {
                slot = i; break;
            }
        /* A byte first part followed by any u16 part must promote into a fresh u16 block. */
        if (slot >= 0 && parts[0].bytes == bytes && A->tcap[slot] > n) {
            uint16_t *q0 = A->top[slot];
            int64_t k0 = parts[0].n;
            for (int64_t i = 1; i < nparts; i++) {
                if (parts[i].n) {
                    if (bytes) memcpy((uint8_t *)q0 + k0, (const uint8_t *)parts[i].p, (size_t)parts[i].n);
                    else ail_str_put(q0 + k0, parts[i]);
                }
                k0 += parts[i].n;
            }
            A->tlen[slot] = n;               /* slot n is already zero */
            if (A->trun[slot] < 3) A->trun[slot]++;
            ail_str r0; if (bytes) r0.bytes = 1; else r0.bytes = 0;
            r0.p = q0;  r0.n = n; return r0;
        }
    }
    int64_t run = (slot >= 0) ? (A->trun[slot] >= 3 ? 3 : A->trun[slot] + 1) : 1;
    int64_t want = n + 1;
    if (run >= 3 && (uintmax_t)n < lim / 2 - 1) want = 2 * n + 2;
    ail__need_elems(want, lim);
    uint16_t *q;
    int64_t k = 0;
    if (bytes) {
        uint8_t *qb = (uint8_t *)ail_alloc((size_t)want);
        for (int64_t i = 0; i < nparts; i++) {
            if (parts[i].n) memcpy(qb + k, (const uint8_t *)parts[i].p, (size_t)parts[i].n);
            k += parts[i].n;
        }
        q = (uint16_t *)qb;
        ail_sarena_pushn(A, q, ail_bytes_elems(want));
    } else {
        q = (uint16_t *)ail_alloc((size_t)want * sizeof(uint16_t));
        for (int64_t i = 0; i < nparts; i++) {
            if (parts[i].n) ail_str_put(q + k, parts[i]);
            k += parts[i].n;
        }
        ail_sarena_push(A, q);
    }
    int64_t s_ = slot;
    if (s_ < 0) {
        s_ = 0;
        for (int i = 1; i < AIL_SARENA_TOPS; i++) {
            if (A->top[i] == 0) { s_ = i; break; }
            if (A->trun[i] < A->trun[s_]) s_ = i;
        }
    }
    A->top[s_] = q; A->tlen[s_] = n; A->tcap[s_] = want; A->trun[s_] = run;
    ail_str r; if (bytes) r.bytes = 1; else r.bytes = 0;
    r.p = q;  r.n = n; return r;
}
/* `str(n)` for an int -- the ONE str-producing conversion whose CPython answer can be reproduced
   exactly, because it is total, locale-free and needs no Unicode table. Every OTHER conversion
   into or out of str (case mapping, normalisation, encode/decode, formatting) is refused by name
   at compile time; `oracle_str_refusals.py` holds CPython's own answers for why.

   The digits come off the MAGNITUDE as a uint64_t, because `-v` overflows for v == INT64_MIN and
   that is precisely the value a message-building path is most likely to be handed at a boundary. */
static ail_str ail_str_from_int(ail_sarena *A, int64_t v) {
    uint8_t buf[24];
    int k = 0, o = 0, n;
    uint64_t m = v < 0 ? (uint64_t)0 - (uint64_t)v : (uint64_t)v;
    if (m == 0) buf[k++] = 48;
    while (m) { buf[k++] = (uint8_t)(48 + (int)(m % 10)); m /= 10; }
    n = k + (v < 0 ? 1 : 0);
    uint8_t *q = (uint8_t *)ail_alloc((size_t)n + 1);
    if (v < 0) q[o++] = 45;
    while (k) q[o++] = buf[--k];
    ail_sarena_pushn(A, (uint16_t *)q, ail_bytes_elems(n + 1));
    ail_str r; r.bytes = 1; r.p = (const uint16_t *)q;  r.n = n; return r;
}
/* Writing a str out is the ONE place a code point has to become bytes, and it is why a lone
   surrogate is refused in a literal at COMPILE time: CPython cannot encode one either
   (`'\ud800'.encode('utf-8')` raises), so there is no answer here to reproduce. Everything this
   language can build is a checked literal or decimal digits, so nothing else can reach here. */
static inline size_t ail_str_esz(ail_str s) {
    return s.bytes ? 1u : sizeof(uint16_t);
}
/* A VIEW over s from unit i: a view of a byte string is itself bytes, and
   its offset is in BYTES, so the pointer arithmetic differs with the
   width even though the unit index does not. */
static inline ail_str ail_view(ail_str s, int64_t i) {
    ail_str r; r.bytes = s.bytes; r.n = s.n - i;
    r.p = s.p ? (s.bytes ? (const uint16_t *)((const uint8_t *)s.p + i)
                         : s.p + i) : 0;
    return r;
}
/* Copy s into a uint16 destination, widening a byte string. The
   destination is always the uint16 form: every caller is building a
   result, never a view. */
static inline void ail_str_put(uint16_t *dst, ail_str s) {
    if (s.bytes) {
        for (int64_t i = 0; i < s.n; i++)
            dst[i] = (uint16_t)((const uint8_t *)s.p)[i];
    } else if (s.n) {
        memcpy(dst, s.p, (size_t)s.n * sizeof(uint16_t));
    }
}
static inline uint16_t ail_chr(ail_str s, int64_t i) {
    return s.bytes ? ((const uint8_t *)s.p)[i] : s.p[i];
}
static void ail_str_write(ail_str s, FILE *f) {
    if (f == stdout) ail_stdout_dirty = 1;
    /* `bytes` is set only where every unit is proven <0x80 (ASCII input, literals, decimal
       formatting, or concatenation of byte-backed parts), so a byte string's UTF-8 is the byte
       buffer itself: one fwrite, not s.n passes through the encoder. */
    if (s.bytes && s.n) { fwrite(s.p, 1, (size_t)s.n, f); return; }
    for (int64_t i = 0; i < s.n; i++) {
        uint32_t c = (uint32_t)ail_chr(s, i);
        if (c >= 0xD800 && c < 0xDC00 && i + 1 < s.n &&
                ail_chr(s, i + 1) >= 0xDC00 && ail_chr(s, i + 1) < 0xE000) {
            c = 0x10000u + ((c - 0xD800u) << 10) +
                ((uint32_t)ail_chr(s, i + 1) - 0xDC00u);
            i++;
        }
        /* An UNPAIRED surrogate -- what `at(i)` yields for half of an
           astral character -- is not a code point. Writing it as
           CESU-8 would put invalid UTF-8 on the stream; Node emits
           U+FFFD, so this does too. */
        if (c >= 0xD800 && c < 0xE000) c = 0xFFFDu;
        if (c < 0x80) {
            fputc((int)c, f);
        } else if (c < 0x800) {
            fputc((int)(0xC0 | (c >> 6)), f);
            fputc((int)(0x80 | (c & 0x3F)), f);
        } else if (c < 0x10000) {
            fputc((int)(0xE0 | (c >> 12)), f);
            fputc((int)(0x80 | ((c >> 6) & 0x3F)), f);
            fputc((int)(0x80 | (c & 0x3F)), f);
        } else {
            fputc((int)(0xF0 | (c >> 18)), f);
            fputc((int)(0x80 | ((c >> 12) & 0x3F)), f);
            fputc((int)(0x80 | ((c >> 6) & 0x3F)), f);
            fputc((int)(0x80 | (c & 0x3F)), f);
        }
    }
}
/* What `ail_die` could not do: a message the PROGRAM computed. `ail_die` takes a compile-time
   `const char *` and nothing else, so until `str` existed every trap in this runtime could say
   only what the RUNTIME thought went wrong, never what the program knew. `assert c, m` is the one
   surface spelling that reaches this. */
static void ail_die_str(ail_str s) {
    ail_str_write(s, stderr);
    fputc(10, stderr);
    _Exit(1);
}
/* CPython's whitespace set, ENUMERATED FROM CPYTHON over every one of the 1,114,112 code points --
   `test_wsset.py` does that enumeration on every run and compares, so this is CPython's answer and
   not a remembered table. It is 29 code points and it needs no Unicode property table at all,
   which is why these operations can AGREE with CPython rather than refuse.

   The comment that stood here until 2026-09-15 said the opposite: that matching CPython "needs a
   real Unicode property table, exactly the kind SEMANTICS.md section 31 already refuses to ship",
   and that "a program stripping NBSP or NEL disagrees with CPython here". The first half was
   wrong, and the second half describes a SILENT wrong answer that was documented in a comment and
   enforced nowhere -- while `.lower()` and `.isdigit()`, written the same day in this same file,
   both stop at run time with a named message when they reach a code point they cannot handle. A
   stated limit that nothing enforces is not a limit. */
static int ail__is_ws(uint16_t c) {
    return (c >= 0x09 && c <= 0x0D) || (c >= 0x1C && c <= 0x20)
        || c == 0x85 || c == 0xA0 || c == 0x1680
        || (c >= 0x2000 && c <= 0x200A)
        || c == 0x2028 || c == 0x2029 || c == 0x202F || c == 0x205F || c == 0x3000;
}
/* `int(<str>)` skips a DIFFERENT set: the same 29 MINUS the four information separators
   0x1C-0x1F. `'\x1c1'.split()` splits in CPython and `int('\x1c1')` raises ValueError there, so
   one shared predicate cannot serve both -- widening the single `ail__is_ws` this file used to
   have would have fixed split and strip and silently broken int() on exactly those four. */
static int ail__is_int_ws(uint16_t c) {
    return ail__is_ws(c) && !(c >= 0x1C && c <= 0x1F);
}

/* `int(<str>)` -- AIL_TASK_stdio_20260915.md scope item 4. CPython's own rule, exactly: optional
   surrounding whitespace, an optional sign, one or more decimal digits, nothing else. Anything
   that does not fit -- empty, only a sign, only whitespace, a non-digit anywhere in the middle --
   raises ValueError, through the SAME catchable path `raise ValueError()` already uses
   (`ail_raise_named`), not a hard `ail_die` crash, so `except ValueError:` around it works exactly
   as it does around a source-level `raise`. Digits are accumulated on the MAGNITUDE as a uint64_t
   for the same INT64_MIN reason `ail_str_from_int` reads off a magnitude: negating an int64_t
   overflows for exactly that one value. Values outside int64 stop as integer overflow. */
static int64_t ail_str_to_int(ail_str s) {
    int64_t i = 0, n = s.n;
    while (i < n && ail__is_int_ws(ail_chr(s, i))) i++;
    int64_t j = n;
    while (j > i && ail__is_int_ws(ail_chr(s, j - 1))) j--;
    if (i >= j) ail_raise_named(AIL_EXC_VALUE);           /* empty (or all whitespace) */
    int neg = 0;
    if (ail_chr(s, i) == 43) { i++; }                            /* '+' */
    else if (ail_chr(s, i) == 45) { neg = 1; i++; }               /* '-' */
    if (i >= j) ail_raise_named(AIL_EXC_VALUE);            /* a sign with no digits after it */
    uint64_t m = 0;
    for (; i < j; i++) {
        uint32_t c = (uint32_t)ail_chr(s, i);
        if (c < 48 || c > 57) ail_raise_named(AIL_EXC_VALUE);
        uint64_t digit = (uint32_t)(c - 48);
        uint64_t limit = (uint64_t)INT64_MAX + (uint64_t)neg;
        if (m > (limit - digit) / 10u) ail_die("integer overflow");
        m = m * 10u + digit;
    }
    return m == (uint64_t)INT64_MAX + 1u ? INT64_MIN : neg ? -(int64_t)m : (int64_t)m;
}
/* `float(<str>)` -- AIL_TASK_p3shapes_20260916.md mechanism 3, the one str-to-number conversion
   `int(<str>)` above did not already cover. CPython's `float()` accepts everything C's own
   `strtod` accepts (optional sign, digits, an optional '.', an optional exponent like `1e3`) and
   nothing it would call trailing garbage, plus the SAME surrounding whitespace `int(<str>)`
   strips -- `ail__is_ws`, not `ail__is_int_ws`: `float()` has no digit-vs-information-separator
   ambiguity to avoid, so the plain, wider set from `.strip()` is exactly CPython's own rule here,
   unlike `int(<str>)`'s narrower one just above.

   `strtod` wants a NUL-terminated byte string and `ail_str` is code points, not bytes, so the
   trimmed span is copied into a small stack buffer (or the heap, only for a str longer than that
   buffer -- ordinary numeric text never is). A code point outside plain ASCII can never be part
   of a number `strtod` would accept, so it is rejected as ValueError immediately, the same
   verdict CPython gives, rather than truncated into a byte and handed to `strtod` to reject on
   its own terms. After the call, `end` has to have consumed the WHOLE trimmed span -- a `strtod`
   that stops early ('1.5x', bare '.', bare '-') is exactly the ValueError CPython raises for the
   same text, through the same catchable path `ail_str_to_int` uses (`ail_raise_named`), so
   `except ValueError:` around `float(s)` works identically to `except ValueError:` around
   `int(s)`. */
static double ail_str_to_float(ail_str s) {
    int64_t i = 0, n = s.n;
    while (i < n && ail__is_ws(ail_chr(s, i))) i++;
    int64_t j = n;
    while (j > i && ail__is_ws(ail_chr(s, j - 1))) j--;
    if (i >= j) ail_raise_named(AIL_EXC_VALUE);           /* empty (or all whitespace) */
    int64_t len = j - i;
    char stackbuf[128];
    char *heap = len < (int64_t)sizeof stackbuf ? NULL
               : (char *)malloc((size_t)len + 1);
    if (len >= (int64_t)sizeof stackbuf && !heap) ail_die("out of memory");
    char *b = heap ? heap : stackbuf;
    for (int64_t k = 0; k < len; k++) {
        uint16_t c = ail_chr(s, i + k);
        /* 'x'/'X' is never part of any spelling CPython's float() grammar accepts (no hex
           notation there, unlike `strtod`'s own C99 hex-float extension "0x1.8p3") -- rejected
           here by name rather than let strtod parse something CPython would refuse. */
        if (c < 0 || c > 126 || c == 'x' || c == 'X') {
            if (heap) free(heap);
            ail_raise_named(AIL_EXC_VALUE);
        }
        b[k] = (char)c;
    }
    b[len] = 0;
    char *end = NULL;
    double v = strtod(b, &end);
    int consumed_all = (end == b + len);
    if (heap) free(heap);
    if (!consumed_all) ail_raise_named(AIL_EXC_VALUE);
    return v;
}
/* AIL_TASK_strops_20260915.md Part A: `.strip()`/`.lstrip()`/`.rstrip()` and `.count()`.

   The whitespace set is `ail__is_ws`, defined above beside `int(<str>)`'s own narrower one. Every
   one of these six is a VIEW -- a pointer and a length into `s`'s own buffer -- exactly like
   `ail_str_index`/`ail_str_slice` above; nothing is allocated. */
static ail_str ail_str_strip(ail_str s) {
    int64_t i = 0, j = s.n;
    while (i < j && ail__is_ws(ail_chr(s, i))) i++;
    while (j > i && ail__is_ws(ail_chr(s, j - 1))) j--;
    ail_str r = ail_view(s, i); r.n = j - i; return r;
}
static ail_str ail_str_lstrip(ail_str s) {
    int64_t i = 0;
    while (i < s.n && ail__is_ws(ail_chr(s, i))) i++;
    ail_str r = ail_view(s, i); r.n = s.n - i; return r;
}
static ail_str ail_str_rstrip(ail_str s) {
    int64_t j = s.n;
    while (j > 0 && ail__is_ws(ail_chr(s, j - 1))) j--;
    ail_str r; r.bytes = s.bytes; r.p = s.p;  r.n = j; return r;
}
/* The one-argument forms strip any code point that is a MEMBER of `chars`, never a substring match
   -- `"aabbccba".strip("ab")` strips both 'a' and 'b' off each end. Plain membership against
   `chars`' own code points, which needs no table, unlike a Unicode PROPERTY test. */
static int ail__in_str(ail_str chars, uint32_t c) {
    for (int64_t k = 0; k < chars.n; k = ail_str_next_unit(chars, k))
        if (ail_str_point(chars, k) == c) return 1;
    return 0;
}
static ail_str ail_str_strip_chars(ail_str s, ail_str chars) {
    int64_t i = 0, j = s.n;
    while (i < j && ail__in_str(chars, ail_str_point(s, i)))
        i = ail_str_next_unit(s, i);
    while (j > i && ail__in_str(chars, ail_str_point(s, ail_str_prev_unit(s, j))))
        j = ail_str_prev_unit(s, j);
    ail_str r = ail_view(s, i); r.n = j - i; return r;
}
static ail_str ail_str_lstrip_chars(ail_str s, ail_str chars) {
    int64_t i = 0;
    while (i < s.n && ail__in_str(chars, ail_str_point(s, i)))
        i = ail_str_next_unit(s, i);
    ail_str r = ail_view(s, i); r.n = s.n - i; return r;
}
static ail_str ail_str_rstrip_chars(ail_str s, ail_str chars) {
    int64_t j = s.n;
    while (j > 0 && ail__in_str(chars, ail_str_point(s, ail_str_prev_unit(s, j))))
        j = ail_str_prev_unit(s, j);
    ail_str r; r.bytes = s.bytes; r.p = s.p;  r.n = j; return r;
}
/* Replacement visits code-point boundaries and must not end a match inside a surrogate pair. */
static int ail_text_match_at(ail_str s, ail_str old, int64_t i) {
    if (old.n > s.n - i) return 0;
    int64_t end = i + old.n;
    if (!s.bytes && end > 0 && end < s.n &&
        ail_chr(s,end-1) >= 0xD800 && ail_chr(s,end-1) < 0xDC00 &&
        ail_chr(s,end) >= 0xDC00 && ail_chr(s,end) < 0xE000) return 0;
    for (int64_t k=0;k<old.n;k++)
        if (ail_chr(s,i+k) != ail_chr(old,k)) return 0;
    return 1;
}
static ail_str ail_text_replace(ail_sarena *A, ail_str s, ail_str old, ail_str replacement, int64_t count) {
    uintmax_t bound = AIL_ELEM_LIMIT(uint16_t) - 1;
    ail__need_elems(s.n,bound); ail__need_elems(old.n,bound); ail__need_elems(replacement.n,bound);
    if (count == 0) return s;
    if (count < 0) count = INT64_MAX;
    int64_t matches=0, i=0;
    while (i <= s.n && matches < count) {
        if (ail_text_match_at(s,old,i)) {
            matches++;
            if (old.n) { i+=old.n; continue; }
        }
        if (i==s.n) break;
        i=ail_str_next_unit(s,i);
    }
    if (!matches) return s;
    int64_t base=s.n-matches*old.n;
    if (replacement.n && (uintmax_t)matches > (bound-(uintmax_t)base)/(uintmax_t)replacement.n)
        ail_die("replacement string too long");
    int64_t total=base+matches*replacement.n;
    uint16_t *q=ail_sarena_alloc(A,total+1);
    int64_t out=0, done=0;
    i=0;
    while (i<=s.n && done<matches) {
        if (ail_text_match_at(s,old,i)) {
            ail_str_put(q+out,replacement); out+=replacement.n; done++;
            if (old.n) { i+=old.n; continue; }
        }
        if (i==s.n) break;
        int64_t next=ail_str_next_unit(s,i);
        while(i<next) q[out++]=ail_chr(s,i++);
    }
    ail_str tail=ail_view(s,i); tail.n=s.n-i;
    ail_str_put(q+out,tail); q[total]=0;
    return (ail_str){q,total,0};
}
/* `.count(sub)` counts non-overlapping occurrences, or code points + 1 for an empty needle. */
static int64_t ail_str_count(ail_str s, ail_str sub) {
    if (sub.n == 0) return ail_str_len_points(s) + 1;
    int64_t i = 0, cnt = 0;
    while (i + sub.n <= s.n) {
        int hit = 1;
        for (int64_t k = 0; k < sub.n; k++) if (ail_chr(s, i + k) != ail_chr(sub, k)) { hit = 0; break; }
        if (hit) { cnt++; i += sub.n; } else { i++; }
    }
    return cnt;
}
/* `.lower()` -- AIL_TASK_strops_20260915.md stage 4, ASCII only. CPython's own .lower() is a full
   Unicode case-folding table (STR_METHOD_REFUSALS' own `.upper()` message names the table
   `.upper()`/`.lower()` alike would need, and why it is not shipped). Restricted here to the one
   range that needs no table at all: ASCII 'A'-'Z' -> 'a'-'z'; every OTHER ASCII code point is
   already a correct answer unchanged (CPython's .lower() is a no-op outside 'A'-'Z' for the whole
   ASCII range). A non-ASCII code point anywhere in the receiver TRAPS, by name, rather than
   passing it through unchanged and risking the exact silent mismatch a real Unicode table would
   have caught -- str CONTENT (unlike a literal) is not visible at compile time, so this is a run
   time check, the same discipline `ail_str_to_int`'s ValueError and every other str refusal here
   already apply to what they cannot reproduce, applied as a trap (not a catchable exception --
   CPython itself raises nothing here) because there is no ValueError in real Python for this. */
static ail_str ail_str_lower(ail_sarena *A, ail_str s) {
    uint16_t *q = (uint16_t *)ail_alloc(((size_t)s.n + 1) * sizeof(uint16_t));
    for (int64_t i = 0; i < s.n; i++) {
        uint32_t c = (uint32_t)ail_chr(s, i);
        if (c > 127) ail_die(".lower() reached a non-ASCII code point; this compiler's .lower() "
                             "is ASCII-only -- no Unicode case-folding table is shipped "
                             "(SEMANTICS.md section 31)");
        q[i] = (c >= 65 && c <= 90) ? (uint16_t)(c + 32) : (uint16_t)c;
    }
    ail_sarena_push(A, q);
    ail_str r; r.bytes = 0; r.p = q;  r.n = s.n; return r;
}
/* `.upper()` -- AIL_TASK_p3idioms_20260916.md idiom 7, the mirror image of `.lower()` just above:
   ASCII-only case mapping ('a'-'z' -> 'A'-'Z', every other ASCII code point unchanged), same
   run-time trap (not a compile-time refusal, since str CONTENT is not visible at compile time) on
   any non-ASCII code point rather than silently passing it through and risking the exact mismatch
   a real Unicode table (STR_METHOD_REFUSALS' own 'upper' message: 'ß'.upper() is 'SS', two
   characters from one) would have caught. */
static ail_str ail_str_upper(ail_sarena *A, ail_str s) {
    uint16_t *q = (uint16_t *)ail_alloc(((size_t)s.n + 1) * sizeof(uint16_t));
    for (int64_t i = 0; i < s.n; i++) {
        uint32_t c = (uint32_t)ail_chr(s, i);
        if (c > 127) ail_die(".upper() reached a non-ASCII code point; this compiler's .upper() "
                             "is ASCII-only -- no Unicode case-folding table is shipped "
                             "(SEMANTICS.md section 31)");
        q[i] = (c >= 97 && c <= 122) ? (uint16_t)(c - 32) : (uint16_t)c;
    }
    ail_sarena_push(A, q);
    ail_str r; r.bytes = 0; r.p = q;  r.n = s.n; return r;
}
/* `.startswith(prefix)` / `.endswith(suffix)` -- AIL_TASK_p3idioms_20260916.md idiom 7, one str
   argument only (a tuple of prefixes stays refused by name -- `_method`'s own shape check). Both
   are views into `s`, allocate nothing, and need no table: comparing code points for exact
   equality is total and locale-free, unlike every OTHER str-searching method this compiler
   refuses (STR_METHOD_REFUSALS' 'find' group).

   Each is written directly rather than composed from `ail_str_slice` + `ail_str_eq`: that
   composition LOOKS equivalent but is not, because `ail_str_slice`'s own bounds are Python SLICE
   INDICES (already possibly negative, meaning "from the end"), and `s.n - suffix.n` is not one of
   those -- it can be genuinely negative when `suffix` is longer than `s`, and handing a slice
   function a negative LENGTH-DERIVED offset would silently ask it to apply its own from-the-end
   adjustment a second time. Comparing directly avoids relying on a coincidence in another
   function's contract. */
static int64_t ail_str_startswith(ail_str s, ail_str prefix) {
    if (prefix.n > s.n) return 0;
    return ail_str_prefix_eq(s, prefix);;
}
static int64_t ail_str_endswith(ail_str s, ail_str suffix) {
    if (suffix.n > s.n) return 0;
    int64_t off = s.n - suffix.n;
    return ail_str_suffix_eq(s, off, suffix);
}
/* `.isdigit()` -- AIL_TASK_strops_20260915.md stage 4, ASCII only. CPython's own .isdigit() is a
   Unicode PROPERTY test ('\\u0660' Arabic-Indic zero is a digit, '\\u2168' Roman numeral IX is
   numeric but not digit -- the same table `STR_METHOD_REFUSALS['isdigit']` already refuses to
   ship). Restricted to the ASCII range '0'-'9', which needs no table; an EMPTY str is False, the
   same as CPython's own `"".isdigit()`. A non-ASCII code point anywhere in the receiver TRAPS,
   the identical discipline `.lower()` just above applies -- guessing False for a non-ASCII code
   point would be silently WRONG for the Unicode digits this ASCII-only test cannot see. */
static int64_t ail_str_isdigit(ail_str s) {
    if (s.n == 0) return 0;
    for (int64_t i = 0; i < s.n; i++) {
        uint32_t c = (uint32_t)ail_chr(s, i);
        if (c > 127) ail_die(".isdigit() reached a non-ASCII code point; this compiler's "
                             ".isdigit() is ASCII-only -- no Unicode property table is shipped "
                             "(SEMANTICS.md section 31)");
        if (c < 48 || c > 57) return 0;
    }
    return 1;
}
/* Reading stdin -- AIL_TASK_stdio_20260915.md scope item 2. Three surface spellings share this:
   `sys.stdin.read()` (line_mode 0, reads to real EOF), `sys.stdin.readline()` (line_mode 1, stops
   AFTER '\\n' and KEEPS it, empty str at EOF), and `input()` (line_mode 1 again, but DROPS the
   trailing '\\n' and raises EOFError -- CPython's own distinction -- when NOTHING was read at
   all, not merely when no newline was seen: a final line with no trailing newline is not EOF,
   only a truly empty read is).

   Raw bytes first, decoded after: a UTF-8 CONTINUATION byte (0x80-0xBF) is never the ASCII byte
   10, so splitting on the raw byte before decoding answers the identical question CPython's own
   line-buffered text-mode stdin answers by decoding first.

   BRIEF_stdin_blockread.md: all three spellings pull from ONE static 64 KiB block buffer
   (`ail_stdin_fill` below), refilled by `fread` a block at a time rather than a `getchar()` call
   per byte. That buffer is shared state on purpose: `readline()`/`input()` must stop at the FIRST
   '\n' without consuming what comes after it -- a later call (another readline(), or a read()
   that drains the rest) has to see that remainder still sitting in the buffer, exactly as it
   would still sit in the C stdio stream under the old getchar() version. `sys.stdin.read()`
   (line_mode 0) drains whatever is already buffered, then keeps pulling fresh 64 KiB blocks until
   `fread` returns 0; `readline()`/`input()` (line_mode 1) scan each block for '\n' with `memchr`
   instead of testing one byte at a time. Decoding rules and error behaviour are UNCHANGED: the
   raw bytes collected here still go through `ail_utf8_decode` below exactly as before, and
   malformed UTF-8 still `ail_die`s there, not here. */
#include <unistd.h>
#include <errno.h>
typedef struct { unsigned char buf[65537]; int64_t pos, len; int eof, pending_cr; } ail_stdin_buf_t;
AIL_LINK_STATE(ail_stdin_buf_t, ail_stdin_buf, );
/* Zero has not read; one is text, two is binary. Shared across linked modules. */
AIL_LINK_STATE(int, ail_stdin_kind, = 0);
#ifdef _WIN32
/* Keep the OS fd binary (including Ctrl-Z); normalize text newlines here so a CRLF split across
   read() blocks is still one LF, as in the existing v2 stdin path. */
AIL_LINK_STATE(unsigned char, ail_stdin_raw[65536], );
#endif
static inline void ail_stdin_flush_stdout(void) {
    if (ail_stdout_dirty) {
        if (fflush(stdout) != 0) ail_die("stdout flush before stdin read failed");
        ail_stdout_dirty = 0;
    }
}
static int64_t ail_stdin_fill(void) {
    /* read(2), not fread: fread waits for a FULL block or EOF, so a program answering line by
       line said nothing until its writer closed the pipe (found 2026-09-16 by an outside
       review's probe, reproduced through a pty, judged by test_stdin_interactive.py). read()
       returns what is there -- a line from a terminal, a block from a file -- which keeps the
       block-read speed and the stream contract both. EINTR is retried; other read errors terminate explicitly rather than
       impersonating successful EOF. Catchable OSError is a separate obligation. */
    if (ail_stdin_kind == 2) ail_raise_named(AIL_EXC_VALUE);
    ail_stdin_kind = 1;
    if (ail_stdin_buf.eof) return 0;
    for (;;) {
        ssize_t got;
        ail_stdin_flush_stdout();
#ifdef _WIN32
        do { got = read(0, ail_stdin_raw, sizeof(ail_stdin_raw)); } while (got < 0 && errno == EINTR);
#else
        do { got = read(0, ail_stdin_buf.buf, 65536); } while (got < 0 && errno == EINTR);
#endif
        if (got < 0) ail_die("stdin read failed");
        ail_stdin_buf.pos = 0;
#ifdef _WIN32
        if (got == 0) {
            ail_stdin_buf.eof = 1;
            if (ail_stdin_buf.pending_cr) {
                ail_stdin_buf.pending_cr = 0;
                ail_stdin_buf.buf[0] = '\n';
                ail_stdin_buf.len = 1;
                return 1;
            }
            ail_stdin_buf.len = 0;
            return 0;
        }
        int64_t i = 0, n = 0;
        if (ail_stdin_buf.pending_cr) {
            ail_stdin_buf.buf[n++] = '\n';
            if (ail_stdin_raw[0] == '\n') i = 1;
            ail_stdin_buf.pending_cr = 0;
        }
        for (; i < got; i++) {
            unsigned char ch = ail_stdin_raw[i];
            if (ch == '\r') {
                if (i + 1 == got) { ail_stdin_buf.pending_cr = 1; break; }
                if (ail_stdin_raw[i + 1] == '\n') i++;
                ch = '\n';
            }
            ail_stdin_buf.buf[n++] = ch;
        }
        ail_stdin_buf.len = n;
        if (n) return n;
#else
        ail_stdin_buf.len = (int64_t)got;
        if (got == 0) ail_stdin_buf.eof = 1;
        return (int64_t)got;
#endif
    }
}
/* Return the byte length of one valid Unicode scalar, or zero for malformed UTF-8.
   The same check serves the materializing decoder and the fused integer readers. */
static inline int ail__utf8_one(const unsigned char *b, int64_t n, uint32_t *out) {
    if (n <= 0) return 0;
    unsigned c0 = b[0];
    uint32_t cp, min;
    int need;
    if (c0 < 0x80) { cp = c0; min = 0; need = 1; }
    else if (c0 >= 0xC2 && c0 <= 0xDF) { cp = c0 & 0x1Fu; min = 0x80; need = 2; }
    else if (c0 >= 0xE0 && c0 <= 0xEF) { cp = c0 & 0x0Fu; min = 0x800; need = 3; }
    else if (c0 >= 0xF0 && c0 <= 0xF4) { cp = c0 & 0x07u; min = 0x10000; need = 4; }
    else return 0;
    if (n < need) return 0;
    for (int k = 1; k < need; k++) {
        if ((b[k] & 0xC0) != 0x80) return 0;
        cp = (cp << 6) | (b[k] & 0x3Fu);
    }
    if (cp < min || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) return 0;
    *out = cp;
    return need;
}

static unsigned char *ail_stdin_read_raw(int stop_at_newline, int64_t *out_n, int *out_saw_nl) {
    int64_t cap = 64, n = 0;
    unsigned char *buf = (unsigned char *)ail_alloc((size_t)cap);
    int saw_nl = 0;
    for (;;) {
        if (ail_stdin_buf.pos >= ail_stdin_buf.len) {
            if (ail_stdin_fill() == 0) break;
        }
        int64_t avail = ail_stdin_buf.len - ail_stdin_buf.pos;
        unsigned char *start = ail_stdin_buf.buf + ail_stdin_buf.pos;
        int64_t take = avail;
        unsigned char *nl = NULL;
        if (stop_at_newline) {
            nl = (unsigned char *)memchr(start, '\n', (size_t)avail);
            if (nl) take = (int64_t)(nl - start) + 1;
        }
        if (n + take > cap) {
            while (n + take > cap) cap *= 2;
            unsigned char *nb = (unsigned char *)ail_alloc((size_t)cap);
            memcpy(nb, buf, (size_t)n);
            free(buf);
            buf = nb;
        }
        memcpy(buf + n, start, (size_t)take);
        n += take;
        ail_stdin_buf.pos += take;
        if (stop_at_newline && nl) { saw_nl = 1; break; }
    }
    *out_n = n;
    if (out_saw_nl) *out_saw_nl = saw_nl;
    return buf;
}
/* The one place stdin's raw octets become code points -- the mirror image of `ail_str_write`.
   `nb` bytes decode to AT MOST `nb` code points, so the output buffer is sized for that bound up
   front and never grows. Malformed UTF-8 on stdin has no CPython str to agree with (CPython's own
   text-mode stdin would raise UnicodeDecodeError, a class this language does not model), so it is
   an unconditional `ail_die`, the same "cannot reproduce it, refuse it" rule `_check_str_literal`
   already applies to a lone surrogate at compile time -- just discovered at run time here, the one
   place that is possible for input this compiler never saw until now. */
/* `bad` is the whole `ail_die` message, because two callers read from different sources
   (stdin, and since the `open(path).read()` extension a named FILE) and "stdin is not valid
   UTF-8" on a file that never touched stdin would be a lie in the one place this runtime
   reports a failure. */
static ail_str ail_utf8_decode_m(ail_sarena *A, const unsigned char *b, int64_t nb,
                                 const char *bad) {
    ail__need_elems(nb, AIL_ELEM_LIMIT(uint16_t) - 1);
    uint16_t *q = ail__blk_cache_take(nb + 1);
    if (!q) {
        q = (uint16_t *)malloc(((size_t)nb + 1) * sizeof(uint16_t));
        if (!q) ail_die("out of memory");
    }
    int64_t i = 0, o = 0;
    while (i < nb) {
        uint32_t cp;
        int need = ail__utf8_one(b + i, nb - i, &cp);
        if (!need) { free(q); ail_die(bad); return (ail_str){0, 0}; }
        if (cp > 0xFFFF) {
            uint32_t v = cp - 0x10000u;
            q[o++] = (uint16_t)(0xD800u + (v >> 10));
            q[o++] = (uint16_t)(0xDC00u + (v & 0x3FFu));
        } else {
            q[o++] = (uint16_t)cp;
        }
        i += need;
    }
    /* Recycled blocks are dirty: zero the tail the original calloc had cleared,
       so [o, nb+1) is observably identical to a fresh allocation. */
    memset(q + o, 0, ((size_t)nb + 1 - (size_t)o) * sizeof(uint16_t));
    ail_sarena_pushn(A, q, nb + 1);
    ail_str r; r.bytes = 0; r.p = q;  r.n = o; return r;
}
static ail_str ail_utf8_decode(ail_sarena *A, const unsigned char *b, int64_t nb) {
    return ail_utf8_decode_m(A, b, nb, "stdin is not valid UTF-8");
}
static ail_str ail_stdin_read(ail_sarena *A) {
    /* Read the octets first and ask afterwards whether they are ASCII. If they
       are -- the common case -- those bytes ARE the string (`bytes = 1`): one
       byte per character, no decode pass, and half the peak of the unit form.
       Only a non-ASCII octet forces the decode, and then the byte buffer is
       released as soon as the units exist. */
    int64_t cap = 65536, n = 0;
    unsigned char *b = (unsigned char *)ail_alloc((size_t)cap);
    int ascii = 1;
    for (;;) {
        if (ail_stdin_buf.pos >= ail_stdin_buf.len) {
            if (ail_stdin_fill() == 0) break;
        }
        int64_t avail = ail_stdin_buf.len - ail_stdin_buf.pos;
        const unsigned char *start = ail_stdin_buf.buf + ail_stdin_buf.pos;
        if (n + avail + 1 > cap) {
            while (n + avail + 1 > cap) cap *= 2;
            unsigned char *nb = (unsigned char *)realloc(b, (size_t)cap);
            if (!nb) ail_die("out of memory");
            b = nb;
        }
        if (ascii) {
            for (int64_t k = 0; k < avail; k++) {
                if (start[k] >= 0x80) { ascii = 0; break; }
            }
        }
        memcpy(b + n, start, (size_t)avail);
        n += avail;
        ail_stdin_buf.pos += avail;
    }
    if (ascii) {
        b[n] = 0;
        ail_sarena_pushn(A, (uint16_t *)b, ail_bytes_elems(n + 1));
        ail_str r; r.p = (const uint16_t *)b; r.n = n; r.bytes = 1; return r;
    }
    {
        ail_str d = ail_utf8_decode(A, b, n);
        free(b);
        return d;
    }
    }

static ail_str ail_stdin_readline(ail_sarena *A) {
    /* Fast path: the line ends inside the buffered block, so decode it in place;
       the raw-buffer malloc/memcpy/free round trip remains only for lines that
       span a refill boundary, which fall through to `ail_stdin_read_raw`
       unchanged. Same fill/EINTR/eof semantics and '\n'-inclusive
       result, same pos accounting -- bytes after the newline stay buffered. */
    if (ail_stdin_buf.pos >= ail_stdin_buf.len) ail_stdin_fill();
    if (ail_stdin_buf.pos < ail_stdin_buf.len) {
        unsigned char *start = ail_stdin_buf.buf + ail_stdin_buf.pos;
        int64_t avail = ail_stdin_buf.len - ail_stdin_buf.pos;
        unsigned char *nl = (unsigned char *)memchr(start, '\n', (size_t)avail);
        if (nl) {
            int64_t take = (int64_t)(nl - start) + 1;
            int _ascii = 1;
            for (int64_t _k = 0; _k < take; _k++) {
                if (start[_k] >= 0x80) { _ascii = 0; break; }
            }
            if (_ascii) {
                uint8_t *q = (uint8_t *)ail__blk_cache_take(take + 1);
                if (!q) {
                    q = (uint8_t *)malloc((size_t)take + 1);
                    if (!q) ail_die("out of memory");
                }
                memcpy(q, start, (size_t)take);
                q[take] = 0;
                ail_sarena_pushn(A, (uint16_t *)q,
                                 ail_bytes_elems(take + 1));
                ail_stdin_buf.pos += take;
                ail_str rb; rb.p = (const uint16_t *)q; rb.n = take;
                rb.bytes = 1; return rb;
            }
            ail_str r = ail_utf8_decode(A, start, take);
            ail_stdin_buf.pos += take;
            return r;
        }
    }
    {
        int64_t n;
        unsigned char *b = ail_stdin_read_raw(1, &n, 0);
        ail_str r = ail_utf8_decode(A, b, n);
        free(b);
        return r;
    }
}
/* `input()`: the ONE of the three that can raise. `n == 0` is exactly "readline() would have
   returned the empty str" -- true EOF with nothing left at all -- which is CPython's own trigger
   for EOFError, never merely "no trailing newline was seen" (a real final line with no '\\n' still
   returns that line, unchanged, the same way CPython's does). */
static ail_str ail_input(ail_sarena *A) {
    /* Same fast path as `ail_stdin_readline`, keeping input()'s own rules:
       decode drops the trailing '\n' (the `keep = n - 1` case), and the
       n == 0 EOF -> AIL_EXC_EOF raise stays on the fallback path below. */
    if (ail_stdin_buf.pos >= ail_stdin_buf.len) ail_stdin_fill();
    if (ail_stdin_buf.pos < ail_stdin_buf.len) {
        unsigned char *start = ail_stdin_buf.buf + ail_stdin_buf.pos;
        int64_t avail = ail_stdin_buf.len - ail_stdin_buf.pos;
        unsigned char *nl = (unsigned char *)memchr(start, '\n', (size_t)avail);
        if (nl) {
            int64_t take = (int64_t)(nl - start) + 1;
            ail_str r = ail_utf8_decode(A, start, take - 1);
            ail_stdin_buf.pos += take;
            return r;
        }
    }
    {
        int64_t n; int saw_nl;
        unsigned char *b = ail_stdin_read_raw(1, &n, &saw_nl);
        if (n == 0) { free(b); ail_raise_named(AIL_EXC_EOF); }
        int64_t keep = saw_nl ? n - 1 : n;
        ail_str r = ail_utf8_decode(A, b, keep);
        free(b);
        return r;
    }
}

/* Whole-file read and write_text share path conversion and one-call file lifetime.
   The path arrives as UTF-16 units in an `ail_str`; Windows opens it with _wfopen,
   while POSIX encodes it to UTF-8 for fopen.
   A code point of 0 would silently truncate the name the OS sees (CPython's own answer is
   ValueError, "embedded null byte"), so it raises that rather than open the wrong file.
   fopen/fread failures -- a missing file, a directory, a short read -- raise the catchable
   AIL_EXC_OS ("OSError"), the class CPython raises for all of them (its FileNotFoundError IS
   an OSError subclass; the two spellings share the one code here). Read content stays in
   byte storage when wholly ASCII and otherwise decodes from UTF-8; malformed UTF-8 dies
   uncatchably, the same rule stdin already has. No file object exists as a value: both
   read and write close the file within the call. */
#ifdef _WIN32
typedef wchar_t ail_path_char;
#else
typedef char ail_path_char;
#endif
static ail_path_char *ail_file_path(ail_str path) {
#ifdef _WIN32
    ail__need_elems(path.n, AIL_ELEM_LIMIT(wchar_t) - 1);
    wchar_t *wpath = (wchar_t *)ail_alloc(((size_t)path.n + 1) * sizeof(wchar_t));
    for (int64_t i = 0; i < path.n; i++) {
        uint16_t c = ail_chr(path, i);
        if (c == 0) { free(wpath); ail_raise_named(AIL_EXC_VALUE); }
        wpath[i] = (wchar_t)c;
    }
    wpath[path.n] = 0;
    return wpath;
#else
    if (path.n < 0 || path.n > (INT64_MAX - 1) / 4 || (uintmax_t)path.n > (SIZE_MAX - 1) / 4)
        ail_die("path too long");
    char *cpath = (char *)malloc((size_t)path.n * 4 + 1);
    if (!cpath) ail_die("out of memory");
    int64_t o = 0;
    for (int64_t i = 0; i < path.n; i++) {
        uint32_t c = (uint32_t)ail_chr(path, i);
        if (c == 0) { free(cpath); ail_raise_named(AIL_EXC_VALUE); }
        if (c >= 0xD800 && c < 0xE000 &&
                !(c < 0xDC00 && i + 1 < path.n &&
                  ail_chr(path, i + 1) >= 0xDC00 && ail_chr(path, i + 1) < 0xE000)) {
            c = 0xFFFDu;   /* an unpaired surrogate is not a code point */
        }
        if (c >= 0xD800 && c < 0xDC00 && i + 1 < path.n &&
                ail_chr(path, i + 1) >= 0xDC00 && ail_chr(path, i + 1) < 0xE000) {
            c = 0x10000u + ((c - 0xD800u) << 10) +
                ((uint32_t)ail_chr(path, i + 1) - 0xDC00u);
            i++;
        }
        if (c < 0x80) {
            cpath[o++] = (char)c;
        } else if (c < 0x800) {
            cpath[o++] = (char)(0xC0 | (c >> 6));
            cpath[o++] = (char)(0x80 | (c & 0x3F));
        } else if (c < 0x10000) {
            cpath[o++] = (char)(0xE0 | (c >> 12));
            cpath[o++] = (char)(0x80 | ((c >> 6) & 0x3F));
            cpath[o++] = (char)(0x80 | (c & 0x3F));
        } else {
            cpath[o++] = (char)(0xF0 | (c >> 18));
            cpath[o++] = (char)(0x80 | ((c >> 12) & 0x3F));
            cpath[o++] = (char)(0x80 | ((c >> 6) & 0x3F));
            cpath[o++] = (char)(0x80 | (c & 0x3F));
        }
    }
    cpath[o] = 0;
    return cpath;
#endif
}
/* mode: 0 read, 1 replace, 2 append; binary on every platform. */
static FILE *ail_file_open(ail_str path, int mode) {
    ail_path_char *name = ail_file_path(path);
#ifdef _WIN32
    FILE *f = _wfopen(name, mode == 2 ? L"ab" : mode == 1 ? L"wb" : L"rb");
#else
    FILE *f = fopen(name, mode == 2 ? "ab" : mode == 1 ? "wb" : "rb");
#endif
    free(name);
    if (!f) ail_raise_named(AIL_EXC_OS);
    return f;
}
typedef struct { FILE *file; unsigned char *buf; int64_t capacity; } ail_file_iter;
static ail_file_iter *ail_file_iter_open(ail_str path) {
    FILE *file = ail_file_open(path, 0);
    ail_file_iter *it = (ail_file_iter *)calloc(1, sizeof *it);
    if (!it) { fclose(file); ail_die("out of memory"); }
    it->file = file;
    return it;
}
static void ail_file_iter_close(ail_file_iter * volatile *slot) {
    ail_file_iter *it = *slot;
    *slot = NULL;
    if (!it) return;
    fclose(it->file);
    free(it->buf);
    free(it);
}
static void ail_file_iter_cleanup(void **resources) {
    ail_file_iter_close(resources[0]);
}
/* The iterator owns this FILE; it is never exposed to AIL or foreign calls. */
#if defined(__linux__)
#ifndef getc_unlocked
extern int getc_unlocked(FILE *);
#endif
static inline int ail_file_iter_read_byte(FILE *file) { return getc_unlocked(file); }
#else
static inline int ail_file_iter_read_byte(FILE *file) { return fgetc(file); }
#endif
static ail_str ail_file_iter_next(ail_sarena *A, ail_file_iter *it) {
    int64_t n = 0;
    for (;;) {
        int c = ail_file_iter_read_byte(it->file);
        if (c == EOF) {
            if (ferror(it->file)) ail_raise_named(AIL_EXC_OS);
            break;
        }
        /* Text iteration uses universal newlines, including a lone CR. */
        if (c == '\r') {
            int next = ail_file_iter_read_byte(it->file);
            if (next == EOF && ferror(it->file)) ail_raise_named(AIL_EXC_OS);
            if (next != EOF && next != '\n' && ungetc(next, it->file) == EOF)
                ail_raise_named(AIL_EXC_OS);
            c = '\n';
        }
        if (n == it->capacity) {
            if (it->capacity > INT64_MAX / 2 || (uintmax_t)it->capacity > SIZE_MAX / 2)
                ail_die("line too large");
            int64_t capacity = it->capacity ? it->capacity * 2 : 256;
            unsigned char *buf = (unsigned char *)realloc(it->buf, (size_t)capacity);
            if (!buf) ail_die("out of memory");
            it->buf = buf;
            it->capacity = capacity;
        }
        it->buf[n++] = (unsigned char)c;
        if (c == '\n') break;
    }
    return ail_utf8_decode_m(A, it->buf, n, "file is not valid UTF-8");
}
static void ail_file_decode_cleanup(void **resources) { free(resources[0]); }
static ail_str ail_file_read(ail_sarena *A, ail_str path) {
    FILE *f = ail_file_open(path, 0);
    int64_t cap = 65536, n = 0;
    unsigned char *buf = (unsigned char *)ail_alloc((size_t)cap);
    for (;;) {
        if (n == cap) {
            if (cap > INT64_MAX / 2 || (uintmax_t)cap > SIZE_MAX / 2) {
                fclose(f); free(buf); ail_die("file too large");
            }
            cap *= 2;
            unsigned char *next = (unsigned char *)realloc(buf, (size_t)cap);
            if (!next) { fclose(f); free(buf); ail_die("out of memory"); }
            buf = next;
        }
        size_t got = fread(buf + n, 1, (size_t)(cap - n), f);
        n += (int64_t)got;
        if (got == 0) break;                     /* EOF, or an error ferror() names below */
    }
    if (ferror(f)) { fclose(f); free(buf); ail_raise_named(AIL_EXC_OS); }
    fclose(f);
    int64_t ascii_end = 0;
    while (ascii_end < n && buf[ascii_end] < 0x80) ascii_end++;
    if (ascii_end == n) {
        /* All ASCII octets are valid UTF-8 and can use stdin's byte-backed str path. */
        buf[n] = 0;  /* the read loop always leaves capacity beyond n */
        ail_sarena_pushn(A, (uint16_t *)buf, ail_bytes_elems(n + 1));
        ail_str r; r.bytes = 1; r.p = (const uint16_t *)buf; r.n = n; return r;
    }
    void *resources[] = {buf};
    ail_cleanup_frame frame = {ail_cleanup_top, ail_file_decode_cleanup, resources};
    ail_cleanup_top = &frame;
    ail_str r = ail_utf8_decode_m(A, buf, n, "file is not valid UTF-8");
    ail_cleanup_top = frame.previous;
    free(buf);
    return r;
}
static void ail_file_write_text(ail_str path, ail_str text) {
    FILE *f = ail_file_open(path, 1);
    ail_str_write(text, f);
    int failed = ferror(f);
    if (fclose(f) != 0 || failed) ail_raise_named(AIL_EXC_OS);
}

/* Fused byte-domain reader for the whole-function idiom `_match_stdin_int_reader`
   recognises in pyfunc.py:
       line = sys.stdin.readline(); if len(line) == 0: return EOF
       token = line[:-1] if line.endswith('\n') else line
       if len(token) == 0 or len(token) > max_chars: return ERR
       digits = token[1:] if token[0] in '+-' else token
       if len(digits) == 0 or any non-ASCII-digit in digits: return ERR
       return ERR if int(token) outside [lo, hi] else int(token)
   It reads the SAME buffered stdin `ail_stdin_readline` does -- same flush before
   an OS read, same fill/EINTR/eof, same first-'\n' split, same "no bytes at all" EOF
   -- but never materialises the int32 string: bytes stay in the stdin block (the
   rare spanning line still comes through `ail_stdin_read_raw`, freed below), so
   there is no decode write, no arena block, no arena free for the line at all.
   UTF-8 is validated across the WHOLE line FIRST, before any of the checks, which
   is the same order the original ran them in (decode ran on the entire line before
   the length test could see it), so malformed input still dies with the same
   message instead of falling into a validation error. The `> max_chars` test is a
   BYTE count where the source counted code points: a token holding any multi-byte
   code point fails the ASCII-digit test regardless, and every failure path returns
   the same err_code, so the two counts can never disagree observably. The value is
   accumulated in uint64 exactly as `ail_str_to_int` does, so even a source with a
   very large max_chars wraps identically. */
static int64_t ail__stdin_readline_i64(int64_t max_chars, int64_t lo, int64_t hi,
                                       int64_t eof_code, int64_t err_code, int ws_mode) {
    if (ail_stdin_buf.pos >= ail_stdin_buf.len) ail_stdin_fill();
    const unsigned char *b = NULL;
    int64_t nb = 0;
    int borrowed = 0;
    if (ail_stdin_buf.pos < ail_stdin_buf.len) {
        unsigned char *start = ail_stdin_buf.buf + ail_stdin_buf.pos;
        int64_t avail = ail_stdin_buf.len - ail_stdin_buf.pos;
        unsigned char *nl = (unsigned char *)memchr(start, '\n', (size_t)avail);
        if (nl) {
            b = start;
            nb = (int64_t)(nl - start) + 1;
            ail_stdin_buf.pos += nb;
            borrowed = 1;
        }
    }
    if (!borrowed) {
        int64_t n;
        unsigned char *raw = ail_stdin_read_raw(1, &n, 0);
        if (n == 0) { free(raw); return eof_code; }
        b = raw; nb = n;
    }
    /* word-at-a-time: any word with a high bit drops to the byte validator for
       that position (which consumes the whole multibyte sequence or dies);
       all-ASCII words skip eight bytes per iteration. Same accept set. */
    for (int64_t i = 0; i < nb; ) {
        while (i + 8 <= nb) {
            uint64_t w;
            memcpy(&w, b + i, 8);
            if (w & 0x8080808080808080ULL) break;
            i += 8;
        }
        if (i >= nb) break;
        uint32_t cp;
        int need = ail__utf8_one(b + i, nb - i, &cp);
        if (!need) goto badutf8;
        i += need;
    }
    {
        int64_t tn = nb;
        int64_t i = 0;
        int neg = 0;
        uint64_t m = 0;
        if (ws_mode == 0) {
            if (tn > 0 && b[tn - 1] == '\n') tn--;
        } else {
            /* ws modes (line.strip()/lstrip()/rstrip()): strip ail__is_ws code points.
               The line passed whole-line UTF-8 validation above, so edge bytes decode
               cleanly; a stripped code point advances by its own length. */
            if (ws_mode & 1) {
                while (i < tn) {
                    unsigned c0 = b[i];
                    uint32_t cp; int cl;
                    if (c0 < 0x80) { cp = (uint16_t)c0; cl = 1; }
                    else if ((c0 & 0xE0) == 0xC0) { cp = ((c0 & 31) << 6) | (b[i + 1] & 63); cl = 2; }
                    else if ((c0 & 0xF0) == 0xE0) { cp = ((c0 & 15) << 12) | ((b[i + 1] & 63) << 6) | (b[i + 2] & 63); cl = 3; }
                    else { cp = ((c0 & 7) << 18) | ((b[i + 1] & 63) << 12) | ((b[i + 2] & 63) << 6) | (b[i + 3] & 63); cl = 4; }
                    if (cp > 0xFFFF || !ail__is_ws((uint16_t)cp)) break;
                    i += cl;
                }
            }
            if (ws_mode & 2) {
                while (tn > i) {
                    int64_t j = tn - 1;
                    int64_t cl; uint32_t cp;
                    while (j > i && (b[j] & 0xC0) == 0x80) j--;
                    cl = tn - j;
                    if (cl == 1) cp = b[j];
                    else if (cl == 2) cp = ((b[j] & 31) << 6) | (b[j + 1] & 63);
                    else if (cl == 3) cp = ((b[j] & 15) << 12) | ((b[j + 1] & 63) << 6) | (b[j + 2] & 63);
                    else cp = ((b[j] & 7) << 18) | ((b[j + 1] & 63) << 12) | ((b[j + 2] & 63) << 6) | (b[j + 3] & 63);
                    if (cp > 0xFFFF || !ail__is_ws((uint16_t)cp)) break;
                    tn = j;
                }
            }
        }
        if (tn - i <= 0 || tn - i > max_chars) goto err;
        if (b[i] == 43) i += 1;
        else if (b[i] == 45) { neg = 1; i += 1; }
        if (i >= tn) goto err;
        for (; i < tn; i++) {
            unsigned c = b[i];
            if (c < 48 || c > 57) goto err;
            m = m * 10u + (uint64_t)(c - 48);
        }
        {
            int64_t v = neg ? -(int64_t)m : (int64_t)m;
            if (v < lo || v > hi) goto err;
            if (!borrowed) free((void *)b);
            return v;
        }
    }
err:
    if (!borrowed) free((void *)b);
    return err_code;
badutf8:
    if (!borrowed) free((void *)b);
    ail_die("stdin is not valid UTF-8");
    return 0;
}

/* Loop-fused sibling of `ail__stdin_readline_i64`, for `_match_stdin_while_int_loop`
   (pyfunc.py): the stdin-parse `while` loop. Same buffered read, same whole-line
   UTF-8 validation, same trim modes -- but reports a STATUS, because the source
   loop's failure sites carry their own bodies which the caller replays verbatim:
       0 = ok, *out holds the parsed value
       1 = EOF (no bytes at all -- same as the shared reader's empty read)
       2 = token empty, or token longer than max_chars       (`len(token)` site)
       3 = no digits after an optional '+'/'-' sign          (`len(digits)` site)
       4 = a non-ASCII-digit code point in digits            (`for c in digits` site)
   The `len(token)` test counts CODE POINTS, not bytes: the source's len()
   measured characters, and a multi-byte sequence is one character. The line
   already passed whole-line UTF-8 validation, so a non-continuation byte marks
   exactly one code point -- counting them over the token span is exact. (The
   whole-function sibling can use a byte count instead only because its every
   failure shares a single code, so the difference is unobservable there.) */
static int ail__stdin_readline_i64_st(int64_t *out, int64_t max_chars, int ws_mode) {
    if (ail_stdin_buf.pos >= ail_stdin_buf.len) ail_stdin_fill();
    const unsigned char *b = NULL;
    int64_t nb = 0;
    int borrowed = 0;
    if (ail_stdin_buf.pos < ail_stdin_buf.len) {
        unsigned char *start = ail_stdin_buf.buf + ail_stdin_buf.pos;
        int64_t avail = ail_stdin_buf.len - ail_stdin_buf.pos;
        unsigned char *nl = (unsigned char *)memchr(start, '\n', (size_t)avail);
        if (nl) {
            b = start;
            nb = (int64_t)(nl - start) + 1;
            ail_stdin_buf.pos += nb;
            borrowed = 1;
        }
    }
    if (!borrowed) {
        int64_t n;
        unsigned char *raw = ail_stdin_read_raw(1, &n, 0);
        if (n == 0) { free(raw); return 1; }
        b = raw; nb = n;
    }
    for (int64_t i = 0; i < nb; ) {
        while (i + 8 <= nb) {
            uint64_t w;
            memcpy(&w, b + i, 8);
            if (w & 0x8080808080808080ULL) break;
            i += 8;
        }
        if (i >= nb) break;
        uint32_t cp;
        int need = ail__utf8_one(b + i, nb - i, &cp);
        if (!need) goto badutf8;
        i += need;
    }
    {
        int64_t tn = nb;
        int64_t i = 0;
        int neg = 0;
        uint64_t m = 0;
        if (ws_mode == 0) {
            if (tn > 0 && b[tn - 1] == '\n') tn--;
        } else {
            if (ws_mode & 1) {
                while (i < tn) {
                    unsigned c0 = b[i];
                    uint32_t cp; int cl;
                    if (c0 < 0x80) { cp = (uint16_t)c0; cl = 1; }
                    else if ((c0 & 0xE0) == 0xC0) { cp = ((c0 & 31) << 6) | (b[i + 1] & 63); cl = 2; }
                    else if ((c0 & 0xF0) == 0xE0) { cp = ((c0 & 15) << 12) | ((b[i + 1] & 63) << 6) | (b[i + 2] & 63); cl = 3; }
                    else { cp = ((c0 & 7) << 18) | ((b[i + 1] & 63) << 12) | ((b[i + 2] & 63) << 6) | (b[i + 3] & 63); cl = 4; }
                    if (cp > 0xFFFF || !ail__is_ws((uint16_t)cp)) break;
                    i += cl;
                }
            }
            if (ws_mode & 2) {
                while (tn > i) {
                    int64_t j = tn - 1;
                    int64_t cl; uint32_t cp;
                    while (j > i && (b[j] & 0xC0) == 0x80) j--;
                    cl = tn - j;
                    if (cl == 1) cp = b[j];
                    else if (cl == 2) cp = ((b[j] & 31) << 6) | (b[j + 1] & 63);
                    else if (cl == 3) cp = ((b[j] & 15) << 12) | ((b[j + 1] & 63) << 6) | (b[j + 2] & 63);
                    else cp = ((b[j] & 7) << 18) | ((b[j + 1] & 63) << 12) | ((b[j + 2] & 63) << 6) | (b[j + 3] & 63);
                    if (cp > 0xFFFF || !ail__is_ws((uint16_t)cp)) break;
                    tn = j;
                }
            }
        }
        {
            int64_t tcp = 0;
            for (int64_t j = i; j < tn; j++)
                if ((b[j] & 0xC0) != 0x80) tcp++;
            if (tcp <= 0 || tcp > max_chars) goto len_fail;
        }
        if (b[i] == 43) i += 1;
        else if (b[i] == 45) { neg = 1; i += 1; }
        if (i >= tn) goto nodig_fail;
        for (; i < tn; i++) {
            unsigned c = b[i];
            if (c < 48 || c > 57) goto nondig_fail;
            m = m * 10u + (uint64_t)(c - 48);
        }
        *out = neg ? -(int64_t)m : (int64_t)m;
        if (!borrowed) free((void *)b);
        return 0;
    }
len_fail:
    if (!borrowed) free((void *)b);
    return 2;
nodig_fail:
    if (!borrowed) free((void *)b);
    return 3;
nondig_fail:
    if (!borrowed) free((void *)b);
    return 4;
badutf8:
    if (!borrowed) free((void *)b);
    ail_die("stdin is not valid UTF-8");
    return 0;
}

/* `sys.argv` -- the command line. Every Computer Language Benchmarks Game task is specified
   as `program N`, and every published implementation in every language reads it that way; a
   compiler that cannot is one whose programs can only ever be run at a single size.

   Two operations exist and no others: `len(sys.argv)` and `sys.argv[i]`. The second produces
   a str, so `int(sys.argv[1])` goes through the SAME `ail_str_to_int` a source-level
   `int(<str>)` uses -- optional whitespace, optional sign, decimal digits, ValueError for
   anything else, exactly where CPython raises it. `strtoll` would have answered 0 for `abc`
   and for the empty string, silently, which is the whole failure this avoids.

   AIL_ARGV_SET is defined HERE rather than by the main builders, and every main template
   carries an `#ifndef` default of nothing. The runtime is emitted above main, so a program
   that used sys.argv gets the call and one that did not gets an empty macro -- with no
   Python-side condition that could fall out of step with which parts were emitted.

   A program built with a main of its own -- a measurement harness, say -- never defines the
   macro, leaves these zero, and `sys.argv[1]` then raises IndexError: wrong LOUDLY, which is
   the only acceptable way for this to be wrong. On Windows the CRT's narrow argv uses the
   active code page, so read GetCommandLineW once and convert each requested argument from
   UTF-16 to UTF-8 instead. The parsed Windows arguments live until process exit. */
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>
AIL_LINK_STATE(int, ail_argc_g, = 0);
AIL_LINK_STATE(LPWSTR *, ail_wargv_g, = 0);
static void ail_argv_set(int argc, char **argv) {
    (void)argc; (void)argv;
    ail_wargv_g = CommandLineToArgvW(GetCommandLineW(), &ail_argc_g);
    if (!ail_wargv_g) ail_die("command line conversion failed");
}
#else
AIL_LINK_STATE(int, ail_argc_g, = 0);
AIL_LINK_STATE(char **, ail_argv_g, = 0);
static void ail_argv_set(int argc, char **argv) { ail_argc_g = argc; ail_argv_g = argv; }
#endif
#define AIL_ARGV_SET ail_argv_set(argc, argv);
static int64_t ail_argv_len(void) { return (int64_t)ail_argc_g; }
static ail_str ail_argv_get(ail_sarena *A, int64_t i) {
    if (i < 0) i += (int64_t)ail_argc_g;            /* Python indexes from the end */
    if (i < 0 || i >= (int64_t)ail_argc_g) ail_raise_named(AIL_EXC_INDEX);
#ifdef _WIN32
    int nb = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, ail_wargv_g[i], -1,
                                 NULL, 0, NULL, NULL);
    if (nb <= 0) ail_die("command line conversion failed");
    unsigned char *b = (unsigned char *)ail_alloc((size_t)nb);
    if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, ail_wargv_g[i], -1,
                            (char *)b, nb, NULL, NULL) != nb) {
        free(b);
        ail_die("command line conversion failed");
    }
    ail_str value = ail_utf8_decode(A, b, nb - 1);
    free(b);
    return value;
#else
    const unsigned char *b = (const unsigned char *)ail_argv_g[i];
    int64_t nb = 0;
    while (b[nb]) nb++;
    return ail_utf8_decode(A, b, nb);
#endif
}

static inline __attribute__((always_inline)) void ail_list_push(ail_list *L, int64_t v) {
    if (L->n == L->cap) {
        int64_t c = L->cap ? L->cap * 2 : 8;
        int64_t *q = (int64_t *)realloc(L->p, (size_t)c * sizeof *q);
        if (!q) ail_die("out of memory");
        L->p = q; L->cap = c;
    }
    L->p[L->n++] = v;
}
static int64_t ail_list_get(const ail_list *L, int64_t i) {
    if (i < 0) i += L->n;
    if (i < 0 || i >= L->n) ail_die("list index out of range");
    return L->p[i];
}
static void ail_list_set(ail_list *L, int64_t i, int64_t v) {
    if (i < 0) i += L->n;
    if (i < 0 || i >= L->n) ail_die("list index out of range");
    L->p[i] = v;
}
static int64_t ail_list_has(const ail_list *L, int64_t v) {
    for (int64_t i = 0; i < L->n; i++) if (L->p[i] == v) return 1;
    return 0;
}
/* `ys.pop()` and `ys.pop(i)`. A negative index counts from the end, exactly as `ail_list_get`
   already does; an empty list (or an index that stays out of range after that normalisation)
   traps, matching Python's IndexError on both shapes -- "pop from empty list" and "pop index out
   of range" are kept as two messages because the empty case is the one CPython itself names
   differently. The shift is O(n) in the worst case (`pop(0)`, a queue's front), which is the same
   cost Python's own list.pop pays for the same shape; nothing here claims a deque's O(1). */
static int64_t ail_list_pop(ail_list *L, int64_t i) {
    if (L->n == 0) ail_die("pop from empty list");
    if (i < 0) i += L->n;
    if (i < 0 || i >= L->n) ail_die("pop index out of range");
    int64_t v = L->p[i];
    for (int64_t j = i; j < L->n - 1; j++) L->p[j] = L->p[j + 1];
    L->n--;
    return v;
}
/* `ys = []` on a name that already holds a list: Python makes a fresh empty list, and the
   cheapest identical behaviour here is to forget the contents and keep the buffer. */
static void ail_list_clear(ail_list *L) { L->n = 0; }
static void ail_list_free(ail_list *L) { free(L->p); L->p = 0; L->n = L->cap = 0; }

/* `d = s[lo:hi:st]` -- a copy of the slice, with CPython's own clamping (slice.indices).
   Omitted bounds are resolved by the caller, which knows the step's sign at compile time:
   st > 0 -> lo = 0, hi = n;  st < 0 -> lo = n - 1, hi = -(n + 1) (clamps to -1, meaning
   "down to and including index 0"). st == 0 is refused at compile time and never reaches
   here. */
static void ail_list_slice_into(ail_list *d, const ail_list *s,
                                int64_t lo, int64_t hi, int64_t st) {
    int64_t n = s->n, i, a, b;
    if (st == 0) ail_die("slice step cannot be zero");
    if (st > 0) {
        a = lo < 0 ? (lo + n < 0 ? 0 : lo + n) : (lo > n ? n : lo);
        b = hi < 0 ? (hi + n < 0 ? 0 : hi + n) : (hi > n ? n : hi);
        for (i = a; i < b; i += st) ail_list_push(d, s->p[i]);
    } else {
        a = lo < 0 ? (lo + n < -1 ? -1 : lo + n) : (lo > n - 1 ? n - 1 : lo);
        b = hi < 0 ? (hi + n < -1 ? -1 : hi + n) : (hi > n - 1 ? n - 1 : hi);
        for (i = a; i > b; i += st) ail_list_push(d, s->p[i]);
    }
}
/* `reachable = nxt` -- a plain list rebound to another plain list. This copies the elements into
   `dst`'s OWN buffer rather than aliasing `src`'s pointer: every list-typed local here is freed
   individually, on its own, at every return (see `to_c`'s `owned` pass in pyfunc.py), so two
   locals sharing one buffer would double-free the moment both went out of scope. Clearing first
   makes this correct whether `dst` is a fresh local or one being rebound for the second time
   around a loop, exactly like `ail_list_push` after `ail_list_clear` elsewhere in this file. */
static void ail_list_copy(ail_list *dst, const ail_list *src) {
    ail_list_clear(dst);
    for (int64_t i = 0; i < src->n; i++) ail_list_push(dst, src->p[i]);
}

/* memcmp and memcpy are used below and the generated preamble carries only stdint, stdio
   and stdlib, so this block brings its own header. It is emitted only when a program
   reaches bytes, so a program that does not is unchanged byte for byte. */
#include <string.h>

/* The type is Python's `bytes`, not its `str`, and that is the whole design decision.
   `bytes` is an immutable sequence of integers 0..255: `b[i]` is an int, iterating yields ints,
   a slice is another `bytes`. That is exactly the shape this runtime already holds, and -- the
   reason it was chosen -- it keeps CPython as the judge, because the same source runs there
   unchanged. `str` makes `s[i]` a one-character string, which needs the recursive string type the
   STR block below now builds. The claim that this costs the oracle was MEASURED on 2026-09-14
   (`oracle_str_probe.py`) before a line of it was written, and is false: over 1426 cases on a
   17-string corpus, 13 of them non-ASCII, a CODE POINT str agrees with CPython on every single
   one. What it costs is four bytes per character and one more indirection -- not the judge.
   `str` does NOT replace this type and the two never meet: `bytes` is octets (`b[i]` is an int),
   `str` is text (`s[i]` is a one-character str), and every operation that would mix them is
   refused by name at compile time. See SEMANTICS.md section 29. */
typedef struct { const unsigned char *p; int64_t n; } ail_bytes;

/* A slice is a view: the bytes it points at are immutable and outlive the call, so `b[1:]` builds
   nothing, matching how array slices already work here. Only concatenation allocates, and what it
   allocates belongs to this arena, freed at return like every other container. */
typedef struct { unsigned char **blk; int64_t n, cap; } ail_barena;

static int64_t ail_bytes_get(ail_bytes b, int64_t i) {
    if (i < 0) i += b.n;                       /* Python indexes from the end */
    if (i < 0 || i >= b.n) ail_die("bytes index out of range");
    return (int64_t)b.p[i];
}
static ail_bytes ail_bytes_slice(ail_bytes b, int64_t lo, int64_t hi) {
    /* Python clamps a slice and never raises, however far out the bounds are. */
    if (lo < 0) { lo += b.n; if (lo < 0) lo = 0; } else if (lo > b.n) lo = b.n;
    if (hi < 0) { hi += b.n; if (hi < 0) hi = 0; } else if (hi > b.n) hi = b.n;
    if (hi < lo) hi = lo;
    ail_bytes r; r.p = b.p + lo; r.n = hi - lo; return r;
}
static int64_t ail_bytes_cmp(ail_bytes a, ail_bytes b) {
    /* Lexicographic on unsigned byte values, then on length -- Python's rule. memcmp compares
       unsigned, which is why it is the right primitive and signed `char` comparison would not be. */
    int64_t n = a.n < b.n ? a.n : b.n;
    int c = n ? memcmp(a.p, b.p, (size_t)n) : 0;
    if (c) return c < 0 ? -1 : 1;
    return a.n == b.n ? 0 : (a.n < b.n ? -1 : 1);
}
static int64_t ail_bytes_eq(ail_bytes a, ail_bytes b) {
    return a.n == b.n && (a.n == 0 || memcmp(a.p, b.p, (size_t)a.n) == 0);
}
static int64_t ail_bytes_find_range(ail_bytes h, ail_bytes nd, int64_t start, int64_t end) {
    if (h.n < 0 || (uintmax_t)h.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)h.n > (uintmax_t)PTRDIFF_MAX || (h.n && !h.p) ||
            nd.n < 0 || (uintmax_t)nd.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)nd.n > (uintmax_t)PTRDIFF_MAX || (nd.n && !nd.p))
        ail_die("invalid bytes span");
    if (start < 0) { start += h.n; if (start < 0) start = 0; }
    if (end < 0) { end += h.n; if (end < 0) end = 0; } else if (end > h.n) end = h.n;
    if (start > h.n || end < start) return -1;
    if (!nd.n) return start;
    if (nd.n > end - start) return -1;
    for (int64_t i = start; i <= end - nd.n; ++i)
        if (memcmp(h.p + i, nd.p, (size_t)nd.n) == 0) return i;
    return -1;
}
static int64_t ail_bytes_find(ail_bytes h, ail_bytes nd, int64_t start) {
    return ail_bytes_find_range(h, nd, start, h.n);
}
static int64_t ail_bytes_rfind_range(ail_bytes h, ail_bytes nd, int64_t start, int64_t end) {
    if (h.n < 0 || (uintmax_t)h.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)h.n > (uintmax_t)PTRDIFF_MAX || (h.n && !h.p) ||
            nd.n < 0 || (uintmax_t)nd.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)nd.n > (uintmax_t)PTRDIFF_MAX || (nd.n && !nd.p))
        ail_die("invalid bytes span");
    if (start < 0) { start += h.n; if (start < 0) start = 0; }
    if (end < 0) { end += h.n; if (end < 0) end = 0; } else if (end > h.n) end = h.n;
    if (start > h.n || end < start) return -1;
    if (!nd.n) return end;
    if (nd.n > end - start) return -1;
    for (int64_t i = end - nd.n;; --i) {
        if (memcmp(h.p + i, nd.p, (size_t)nd.n) == 0) return i;
        if (i == start) return -1;
    }
}
static int64_t ail_bytes_count_range(ail_bytes h, ail_bytes nd, int64_t start, int64_t end) {
    if (h.n < 0 || (uintmax_t)h.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)h.n > (uintmax_t)PTRDIFF_MAX || (h.n && !h.p) ||
            nd.n < 0 || (uintmax_t)nd.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)nd.n > (uintmax_t)PTRDIFF_MAX || (nd.n && !nd.p))
        ail_die("invalid bytes span");
    if (start < 0) { start += h.n; if (start < 0) start = 0; }
    if (end < 0) { end += h.n; if (end < 0) end = 0; } else if (end > h.n) end = h.n;
    if (start > h.n || end < start) return 0;
    if (!nd.n) {
        if (end - start == INT64_MAX) ail_die("bytes count overflow");
        return end - start + 1;
    }
    if (nd.n > end - start) return 0;
    int64_t count = 0;
    for (int64_t i = start; i <= end - nd.n;) {
        if (memcmp(h.p + i, nd.p, (size_t)nd.n) == 0) { ++count; i += nd.n; }
        else ++i;
    }
    return count;
}
static int64_t ail_bytes_startswith_range(ail_bytes h, ail_bytes nd, int64_t start, int64_t end) {
    if (h.n < 0 || (uintmax_t)h.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)h.n > (uintmax_t)PTRDIFF_MAX || (h.n && !h.p) ||
            nd.n < 0 || (uintmax_t)nd.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)nd.n > (uintmax_t)PTRDIFF_MAX || (nd.n && !nd.p))
        ail_die("invalid bytes span");
    if (start < 0) { start += h.n; if (start < 0) start = 0; }
    if (end < 0) { end += h.n; if (end < 0) end = 0; } else if (end > h.n) end = h.n;
    if (start > h.n || end < start) return 0;
    if (!nd.n) return 1;
    if (nd.n > end - start) return 0;
    return memcmp(h.p + start, nd.p, (size_t)nd.n) == 0;
}
static int64_t ail_bytes_endswith_range(ail_bytes h, ail_bytes nd, int64_t start, int64_t end) {
    if (h.n < 0 || (uintmax_t)h.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)h.n > (uintmax_t)PTRDIFF_MAX || (h.n && !h.p) ||
            nd.n < 0 || (uintmax_t)nd.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)nd.n > (uintmax_t)PTRDIFF_MAX || (nd.n && !nd.p))
        ail_die("invalid bytes span");
    if (start < 0) { start += h.n; if (start < 0) start = 0; }
    if (end < 0) { end += h.n; if (end < 0) end = 0; } else if (end > h.n) end = h.n;
    if (start > h.n || end < start) return 0;
    if (!nd.n) return 1;
    if (nd.n > end - start) return 0;
    return memcmp(h.p + (end - nd.n), nd.p, (size_t)nd.n) == 0;
}
static void ail_barena_free(ail_barena *A) {
    for (int64_t i = 0; i < A->n; i++) free(A->blk[i]);
    free(A->blk); A->blk = 0; A->n = A->cap = 0;
}
/* Both allocators below hand a fresh block to the arena the same way -- grow-by-doubling, then
   record the pointer so `ail_barena_free` reaches it -- so that bookkeeping is written once. */
static void ail_barena_push(ail_barena *A, unsigned char *q) {
    if (A->n == A->cap) {
        int64_t c = A->cap ? A->cap * 2 : 8;
        unsigned char **nb = (unsigned char **)ail_alloc((size_t)c * sizeof *nb);
        if (A->n) memcpy(nb, A->blk, (size_t)A->n * sizeof *nb);
        free(A->blk); A->blk = nb; A->cap = c;
    }
    A->blk[A->n++] = q;
}
/* Unsized byte blocks cannot prove ownership of interior views. Snapshot and
   copy every live root before freeing the original range, preserving aliases. */
static void ail_barena_keep_roots(ail_barena *A, int64_t mark, ail_bytes **roots, int64_t count) {
    if (!A || A->n < 0 || A->cap < A->n || mark < 0 || mark > A->n || count < 0 ||
            (A->n && !A->blk) || (count && !roots) ||
            (uintmax_t)count > (uintmax_t)SIZE_MAX / sizeof *roots ||
            (uintmax_t)count > (uintmax_t)SIZE_MAX / sizeof(ail_bytes) ||
            count > INT64_MAX - A->n ||
            (uintmax_t)(A->n + count) > (uintmax_t)SIZE_MAX / sizeof *A->blk)
        ail_die("invalid bytes arena checkpoint");
    for (int64_t r = 0; r < count; ++r) {
        if (!roots[r] || roots[r]->n < 0 ||
                (uintmax_t)roots[r]->n > (uintmax_t)SIZE_MAX ||
                (roots[r]->n && !roots[r]->p))
            ail_die("invalid bytes root span");
    }
    if (A->n == mark) return;
    int64_t end = A->n, needed = end + count;
    ail_bytes *saved = count ? (ail_bytes *)ail_alloc((size_t)count * sizeof *saved) : NULL;
    for (int64_t r = 0; r < count; ++r) saved[r] = *roots[r];
    if (needed > A->cap) {
        unsigned char **blk = (unsigned char **)ail_alloc((size_t)needed * sizeof *blk);
        if (end) memcpy(blk, A->blk, (size_t)end * sizeof *blk);
        free(A->blk); A->blk = blk; A->cap = needed;
    }
    for (int64_t r = 0; r < count; ++r) {
        ail_bytes b = saved[r];
        unsigned char *q = (unsigned char *)ail_alloc(b.n ? (size_t)b.n : 1);
        if (b.n) memcpy(q, b.p, (size_t)b.n);
        ail_barena_push(A, q);
        *roots[r] = (ail_bytes){q, b.n};
    }
    free(saved);
    for (int64_t i = mark; i < end; ++i) free(A->blk[i]);
    for (int64_t i = 0; i < count; ++i) A->blk[mark + i] = A->blk[end + i];
    A->n = mark + count;
}
static ail_bytes ail_bytes_zeros(ail_barena *A, int64_t n) {
    if (n < 0) ail_raise_named(AIL_EXC_VALUE);
    if ((uintmax_t)n > (uintmax_t)SIZE_MAX || (uintmax_t)n > (uintmax_t)PTRDIFF_MAX)
        ail_die("bytes too long");
    if (!n) return (ail_bytes){NULL, 0};
    unsigned char *q = (unsigned char *)ail_alloc((size_t)n);
    ail_barena_push(A, q);
    return (ail_bytes){q, n};
}
static ail_bytes ail_bytes_copy(ail_barena *A, ail_bytes data) {
    if (data.n < 0 || (uintmax_t)data.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)data.n > (uintmax_t)PTRDIFF_MAX || (data.n && !data.p))
        ail_die("invalid bytes span");
    if (!data.n) return (ail_bytes){NULL, 0};
    unsigned char *q = (unsigned char *)ail_alloc((size_t)data.n);
    memcpy(q, data.p, (size_t)data.n);
    ail_barena_push(A, q);
    return (ail_bytes){q, data.n};
}
static ail_bytes ail_bytes_repeat(ail_barena *A, ail_bytes data, int64_t count) {
    if (data.n < 0 || (uintmax_t)data.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)data.n > (uintmax_t)PTRDIFF_MAX || (data.n && !data.p))
        ail_die("invalid bytes span");
    if (count <= 0 || !data.n) return (ail_bytes){NULL, 0};
    if (count > INT64_MAX / data.n ||
            (uintmax_t)count > (uintmax_t)PTRDIFF_MAX / (uintmax_t)data.n ||
            (uintmax_t)count > (uintmax_t)SIZE_MAX / (uintmax_t)data.n)
        ail_die("bytes too long");
    int64_t n = data.n * count;
    unsigned char *q = (unsigned char *)ail_alloc((size_t)n);
    for (int64_t i = 0; i < n; i += data.n) memcpy(q + i, data.p, (size_t)data.n);
    ail_barena_push(A, q);
    return (ail_bytes){q, n};
}
static void ail_bytes_replace_cleanup(void **resources) { free(resources[0]); }
static ail_bytes ail_bytes_replace(ail_barena *A, ail_bytes h, ail_bytes old, ail_bytes repl, int64_t count) {
    ail_bytes spans[] = {h, old, repl};
    for (size_t k = 0; k < sizeof spans / sizeof *spans; ++k)
        if (spans[k].n < 0 || (uintmax_t)spans[k].n > (uintmax_t)SIZE_MAX ||
                (uintmax_t)spans[k].n > (uintmax_t)PTRDIFF_MAX || (spans[k].n && !spans[k].p))
            ail_die("invalid bytes span");
    uintmax_t limit = (uintmax_t)INT64_MAX;
    if (limit > (uintmax_t)SIZE_MAX) limit = (uintmax_t)SIZE_MAX;
    if (limit > (uintmax_t)PTRDIFF_MAX) limit = (uintmax_t)PTRDIFF_MAX;
    uintmax_t maximum = count < 0 ? UINTMAX_MAX : (uintmax_t)count, matches = 0;
    if (!count || old.n > h.n || (!old.n && !repl.n)) {
        matches = 0; /* Unchanged nonempty results still own a fresh arena block. */
    } else if (!old.n) {
        /* n+1 can exceed INT64_MAX, so insertion counts stay unsigned until the size guard. */
        matches = (uintmax_t)h.n + 1;
        if (matches > maximum) matches = maximum;
    } else {
        for (int64_t i = 0; i <= h.n - old.n && matches < maximum;)
            if (!memcmp(h.p + i, old.p, (size_t)old.n)) { ++matches; i += old.n; }
            else ++i;
    }
    uintmax_t base = (uintmax_t)h.n - matches * (uintmax_t)old.n;
    if (repl.n && matches > (limit - base) / (uintmax_t)repl.n)
        ail_die("bytes too long");
    int64_t n = (int64_t)(base + matches * (uintmax_t)repl.n);
    if (!n) return (ail_bytes){NULL, 0};
    /* ail_barena_push doubles its pointer table; check that arithmetic before allocating q. */
    if (!A || A->n < 0 || A->cap < A->n || (A->cap && !A->blk) ||
            (uintmax_t)A->cap > (uintmax_t)SIZE_MAX / sizeof *A->blk ||
            (uintmax_t)A->cap > (uintmax_t)PTRDIFF_MAX / sizeof *A->blk ||
            (A->n == A->cap && A->cap && (A->cap > INT64_MAX / 2 ||
                (uintmax_t)A->cap > (uintmax_t)SIZE_MAX / sizeof *A->blk / 2 ||
                (uintmax_t)A->cap > (uintmax_t)PTRDIFF_MAX / sizeof *A->blk / 2)))
        ail_die("bytes arena too long");
    unsigned char *q = (unsigned char *)ail_alloc((size_t)n);
    int64_t i = 0, out = 0;
    uintmax_t done = 0;
    if (!old.n) {
        while (done < matches) {
            memcpy(q + out, repl.p, (size_t)repl.n); out += repl.n; ++done;
            if (i < h.n) q[out++] = h.p[i++];
        }
    } else {
        while (i <= h.n - old.n && done < matches) {
            if (!memcmp(h.p + i, old.p, (size_t)old.n)) {
                if (repl.n) memcpy(q + out, repl.p, (size_t)repl.n);
                out += repl.n; i += old.n; ++done;
            } else q[out++] = h.p[i++];
        }
    }
    if (i < h.n) memcpy(q + out, h.p + i, (size_t)(h.n - i));
    void *resources[] = {q};
    ail_cleanup_frame frame = {ail_cleanup_top, ail_bytes_replace_cleanup, resources};
    ail_cleanup_top = &frame;
    ail_barena_push(A, q);
    ail_cleanup_top = frame.previous;
    return (ail_bytes){q, n};
}
static ail_bytes ail_bytes_translate(ail_barena *A, ail_bytes h, ail_bytes table, ail_bytes delete) {
    ail_bytes spans[] = {h, table, delete};
    for (size_t k = 0; k < sizeof spans / sizeof *spans; ++k)
        if (spans[k].n < 0 || (uintmax_t)spans[k].n > (uintmax_t)SIZE_MAX ||
                (uintmax_t)spans[k].n > (uintmax_t)PTRDIFF_MAX || (spans[k].n && !spans[k].p))
            ail_die("invalid bytes span");
    if (table.n != 256) ail_raise_named(AIL_EXC_VALUE);
    unsigned char deleted[256] = {0};
    for (int64_t i = 0; i < delete.n; ++i) deleted[delete.p[i]] = 1;
    int64_t n = 0;
    for (int64_t i = 0; i < h.n; ++i) n += !deleted[h.p[i]];
    if (!n) return (ail_bytes){NULL, 0};
    if (!A || A->n < 0 || A->cap < A->n || (A->cap && !A->blk) ||
            (uintmax_t)A->cap > (uintmax_t)SIZE_MAX / sizeof *A->blk ||
            (uintmax_t)A->cap > (uintmax_t)PTRDIFF_MAX / sizeof *A->blk ||
            (A->n == A->cap && A->cap && (A->cap > INT64_MAX / 2 ||
                (uintmax_t)A->cap > (uintmax_t)SIZE_MAX / sizeof *A->blk / 2 ||
                (uintmax_t)A->cap > (uintmax_t)PTRDIFF_MAX / sizeof *A->blk / 2)))
        ail_die("bytes arena too long");
    unsigned char *q = (unsigned char *)ail_alloc((size_t)n);
    int64_t out = 0;
    for (int64_t i = 0; i < h.n; ++i)
        if (!deleted[h.p[i]]) q[out++] = table.p[h.p[i]];
    void *resources[] = {q};
    ail_cleanup_frame frame = {ail_cleanup_top, ail_bytes_replace_cleanup, resources};
    ail_cleanup_top = &frame;
    ail_barena_push(A, q);
    ail_cleanup_top = frame.previous;
    return (ail_bytes){q, n};
}
static ail_bytes ail_bytes_remove_edge(ail_barena *A, ail_bytes h, ail_bytes affix, int suffix) {
    ail_bytes spans[] = {h, affix};
    for (size_t k = 0; k < sizeof spans / sizeof *spans; ++k)
        if (spans[k].n < 0 || (uintmax_t)spans[k].n > (uintmax_t)SIZE_MAX ||
                (uintmax_t)spans[k].n > (uintmax_t)PTRDIFF_MAX || (spans[k].n && !spans[k].p))
            ail_die("invalid bytes span");
    if (suffix != 0 && suffix != 1) ail_die("invalid bytes edge flag");
    int64_t start = 0, n = h.n;
    if (affix.n && affix.n <= h.n &&
            !memcmp(h.p + (suffix ? h.n - affix.n : 0), affix.p, (size_t)affix.n)) {
        n -= affix.n;
        if (!suffix) start = affix.n;
    }
    if (!n) return (ail_bytes){NULL, 0};
    if (!A || A->n < 0 || A->cap < A->n || (A->cap && !A->blk) ||
            (uintmax_t)A->cap > (uintmax_t)SIZE_MAX / sizeof *A->blk ||
            (uintmax_t)A->cap > (uintmax_t)PTRDIFF_MAX / sizeof *A->blk ||
            (A->n == A->cap && A->cap && (A->cap > INT64_MAX / 2 ||
                (uintmax_t)A->cap > (uintmax_t)SIZE_MAX / sizeof *A->blk / 2 ||
                (uintmax_t)A->cap > (uintmax_t)PTRDIFF_MAX / sizeof *A->blk / 2)))
        ail_die("bytes arena too long");
    unsigned char *q = (unsigned char *)ail_alloc((size_t)n);
    memcpy(q, h.p + start, (size_t)n);
    void *resources[] = {q};
    ail_cleanup_frame frame = {ail_cleanup_top, ail_bytes_replace_cleanup, resources};
    ail_cleanup_top = &frame;
    ail_barena_push(A, q);
    ail_cleanup_top = frame.previous;
    return (ail_bytes){q, n};
}
static ail_bytes ail_bytes_cat(ail_barena *A, ail_bytes a, ail_bytes b) {
    if (a.n > INT64_MAX - b.n) ail_die("bytes too long");
    int64_t n = a.n + b.n;
    unsigned char *q = (unsigned char *)ail_alloc((size_t)n + 1);
    if (a.n) memcpy(q, a.p, (size_t)a.n);
    if (b.n) memcpy(q + a.n, b.p, (size_t)b.n);
    ail_barena_push(A, q);
    ail_bytes r; r.p = q; r.n = n; return r;
}
/* `bytes([v])` -- a one-byte `bytes` object built from a single int, the primitive `str(n)`-style
   int-to-bytes code needs and has no other way to reach: nothing here parses or formats decimal
   digits, so a program builds each digit's byte itself (typically by selecting among byte
   literals) and this turns that one int into the one-byte value concatenation can then chain. The
   range check is Python's own: `bytes([256])` raises there too. */
static ail_bytes ail_bytes_one(ail_barena *A, int64_t v) {
    if (v < 0 || v > 255) ail_die("bytes must be in range(0, 256)");
    unsigned char *q = (unsigned char *)ail_alloc(1);
    q[0] = (unsigned char)v;
    ail_barena_push(A, q);
    ail_bytes r; r.p = q; r.n = 1; return r;
}
static ail_bytes ail_bytes_from_ints(ail_barena *A, const int64_t *p, int64_t n) {
    if (n < 0 || (uint64_t)n > SIZE_MAX / sizeof(int64_t) || (!p && n))
        ail_die("invalid integer bytes span");
    for (int64_t i = 0; i < n; ++i)
        if (p[i] < 0 || p[i] > 255) ail_die("bytes must be in range(0, 256)");
    unsigned char *q = (unsigned char *)ail_alloc(n ? (size_t)n : 1);
    for (int64_t i = 0; i < n; ++i) q[i] = (unsigned char)p[i];
    ail_barena_push(A, q);
    return (ail_bytes){q, n};
}

#include <limits.h>
static ail_bytes ail_file_read_bytes_range(ail_barena *A, ail_str path, int64_t offset, int64_t size) {
    if (offset < 0 || size < 0 || (uintmax_t)size > SIZE_MAX)
        ail_raise_named(AIL_EXC_VALUE);
#ifndef _WIN32
    if ((uintmax_t)offset > LONG_MAX) ail_raise_named(AIL_EXC_VALUE);
#endif
    FILE *f = ail_file_open(path, 0);
#ifdef _WIN32
    int seek_failed = _fseeki64(f, offset, SEEK_SET);
#else
    int seek_failed = fseek(f, (long)offset, SEEK_SET);
#endif
    if (seek_failed) { fclose(f); ail_raise_named(AIL_EXC_OS); }
    int64_t cap = size < 65536 ? size : 65536, n = 0;
    unsigned char *buf = cap ? (unsigned char *)malloc((size_t)cap) : NULL;
    if (cap && !buf) { fclose(f); ail_die("out of memory"); }
    while (n < size) {
        if (n == cap) {
            cap += cap < size - cap ? cap : size - cap;
            unsigned char *next = (unsigned char *)realloc(buf, (size_t)cap);
            if (!next) { fclose(f); free(buf); ail_die("out of memory"); }
            buf = next;
        }
        size_t got = fread(buf + n, 1, (size_t)(cap - n), f);
        n += (int64_t)got;
        if (!got) break;
    }
    int failed = ferror(f);
    if (fclose(f) != 0 || failed) { free(buf); ail_raise_named(AIL_EXC_OS); }
    if (!n) { free(buf); return (ail_bytes){NULL, 0}; }
    ail_barena_push(A, buf);
    return (ail_bytes){buf, n};
}
static ail_bytes ail_file_read_bytes(ail_barena *A, ail_str path) {
    FILE *f = ail_file_open(path, 0);
    int64_t cap = 65536, n = 0;
    unsigned char *buf = (unsigned char *)malloc((size_t)cap);
    if (!buf) { fclose(f); ail_die("out of memory"); }
    for (;;) {
        if (n == cap) {
            if (cap > INT64_MAX / 2 || (uintmax_t)cap > SIZE_MAX / 2) {
                fclose(f); free(buf); ail_die("file too large");
            }
            cap *= 2;
            unsigned char *next = (unsigned char *)realloc(buf, (size_t)cap);
            if (!next) { fclose(f); free(buf); ail_die("out of memory"); }
            buf = next;
        }
        size_t got = fread(buf + n, 1, (size_t)(cap - n), f);
        n += (int64_t)got;
        if (!got) break;
    }
    int failed = ferror(f);
    if (fclose(f) != 0 || failed) { free(buf); ail_raise_named(AIL_EXC_OS); }
    ail_barena_push(A, buf);
    return (ail_bytes){buf, n};
}
static void ail_file_write_bytes(ail_str path, ail_bytes data, int mode) {
    if (data.n < 0 || (uint64_t)data.n > SIZE_MAX) ail_die("bytes too long");
    FILE *f = ail_file_open(path, mode);
    int failed = data.n && fwrite(data.p, 1, (size_t)data.n, f) != (size_t)data.n;
    if (fclose(f) != 0 || failed) ail_raise_named(AIL_EXC_OS);
}

/* A bytes pool: the SAME shape as the nested-container pool above (POOL), but its entries are
   `ail_bytes` views instead of `ail_list` structs. Putting a `bytes` value inside a `list` needs a
   way for an int64 slot to *mean* a bytes value, the same way POOL lets one mean another container
   -- every bytes value that is ever stored inside a list (a literal element, or an argument to
   `.append`) becomes one entry here, and what travels through the list's int64 slot is this entry's
   HANDLE -- its position in this pool -- never the bytes value itself.

   An entry OWNS NOTHING: it is a `{p, n}` view, exactly like any other `ail_bytes` (see BYTES
   above), so copying a handle only ever copies an integer index, never the bytes it names. What a
   view points at -- a string literal (static duration) or a concatenation result already living in
   this call's `ail_barena` -- outlives this pool the same way it already outlives any other
   `ail_bytes` local, and is freed (if it is ever freed at all) by that arena, once, independently of
   when this pool is freed. Freeing this pool only ever frees the array of entries itself.

   A `set` or `dict` keyed by bytes does NOT go through this pool: see BTAB below for why a bytes
   key needs content hashing rather than a handle, and so uses a different table entirely rather
   than this indirection.
*/
typedef struct { ail_bytes *items; int64_t n, cap; } ail_bpool;
static int64_t ail_bpool_alloc(ail_bpool *P, ail_bytes b) {
    if (P->n == P->cap) {
        int64_t c = P->cap ? P->cap * 2 : 8;
        ail_bytes *q = (ail_bytes *)realloc(P->items, (size_t)c * sizeof *q);
        if (!q) ail_die("out of memory");
        P->items = q; P->cap = c;
    }
    P->items[P->n] = b;
    return P->n++;
}
static ail_bytes ail_bpool_at(const ail_bpool *P, int64_t h) {
    if (h < 0 || h >= P->n) ail_die("invalid bytes handle");
    return P->items[h];
}
static void ail_bpool_free(ail_bpool *P) { free(P->items); P->items = 0; P->n = P->cap = 0; }

/* Pieces are immutable views into the compiler-owned receiver snapshot. */
static void ail_bsplit_span(ail_bytes b) {
    if (b.n < 0 || (uintmax_t)b.n > (uintmax_t)SIZE_MAX ||
            (uintmax_t)b.n > (uintmax_t)PTRDIFF_MAX || (b.n && !b.p))
        ail_die("invalid bytes span");
}
static void ail_bsplit_meta(const void *p, int64_t n, int64_t cap, size_t width) {
    if (n < 0 || cap < n || (cap && !p) ||
            (uintmax_t)cap > (uintmax_t)SIZE_MAX / width ||
            (uintmax_t)cap > (uintmax_t)PTRDIFF_MAX / width)
        ail_die("invalid bytes container");
}
static void ail_bsplit_growth(int64_t n, int64_t cap, size_t width) {
    if (n == INT64_MAX || (n == cap && cap && (cap > INT64_MAX / 2 ||
            (uintmax_t)cap > (uintmax_t)SIZE_MAX / width / 2 ||
            (uintmax_t)cap > (uintmax_t)PTRDIFF_MAX / width / 2)))
        ail_die("bytes container too long");
}
static void ail_bsplit_cleanup(void **resources) {
    ail_list *L = (ail_list *)resources[0];
    ail_bpool *P = (ail_bpool *)resources[1];
    free(L->p); P->n = *(int64_t *)resources[2];
}
static void ail_bsplit_piece(ail_list *L, ail_bpool *P, ail_bytes h, int64_t start, int64_t end) {
    ail_bsplit_growth(L->n, L->cap, sizeof *L->p);
    ail_bsplit_growth(P->n, P->cap, sizeof *P->items);
    int64_t handle = ail_bpool_alloc(P, (ail_bytes){h.p ? h.p + start : NULL, end - start});
    ail_list_push(L, handle);
}
static int ail_bsplit_space(unsigned char c) { return c == 32 || (c >= 9 && c <= 13); }
static ail_list ail_bytes_split(ail_bpool *P, ail_bytes h, ail_bytes sep, int64_t maxsplit, int whitespace) {
    ail_bsplit_span(h); ail_bsplit_span(sep);
    if (whitespace != 0 && whitespace != 1) ail_die("invalid bytes split mode");
    if (!whitespace && !sep.n) ail_raise_named(AIL_EXC_VALUE);
    if (!P) ail_die("invalid bytes pool");
    ail_bsplit_meta(P->items, P->n, P->cap, sizeof *P->items);
    ail_list L = {0};
    int64_t checkpoint = P->n;
    void *resources[] = {&L, P, &checkpoint};
    ail_cleanup_frame frame = {ail_cleanup_top, ail_bsplit_cleanup, resources};
    ail_cleanup_top = &frame;
    uintmax_t limit = maxsplit < 0 ? UINTMAX_MAX : (uintmax_t)maxsplit, done = 0;
    int64_t start = 0, i = 0;
    if (whitespace) {
        while (i < h.n && ail_bsplit_space(h.p[i])) ++i;
        while (i < h.n) {
            start = i;
            if (done == limit) { ail_bsplit_piece(&L, P, h, start, h.n); break; }
            while (i < h.n && !ail_bsplit_space(h.p[i])) ++i;
            ail_bsplit_piece(&L, P, h, start, i); ++done;
            while (i < h.n && ail_bsplit_space(h.p[i])) ++i;
        }
    } else {
        while (sep.n <= h.n && i <= h.n - sep.n && done < limit) {
            if (!memcmp(h.p + i, sep.p, (size_t)sep.n)) {
                ail_bsplit_piece(&L, P, h, start, i);
                i += sep.n; start = i; ++done;
            } else ++i;
        }
        ail_bsplit_piece(&L, P, h, start, h.n);
    }
    ail_cleanup_top = frame.previous;
    return L;
}
static ail_bytes ail_bytes_join(ail_barena *A, ail_bytes sep, const ail_list *L, const ail_bpool *P) {
    ail_bsplit_span(sep);
    if (!L || !P) ail_die("invalid bytes join container");
    ail_bsplit_meta(L->p, L->n, L->cap, sizeof *L->p);
    ail_bsplit_meta(P->items, P->n, P->cap, sizeof *P->items);
    uintmax_t limit = (uintmax_t)INT64_MAX, total = 0;
    if (limit > (uintmax_t)SIZE_MAX) limit = (uintmax_t)SIZE_MAX;
    if (limit > (uintmax_t)PTRDIFF_MAX) limit = (uintmax_t)PTRDIFF_MAX;
    for (int64_t i = 0; i < L->n; ++i) {
        ail_bytes b = ail_bpool_at(P, L->p[i]); ail_bsplit_span(b);
        if (i) {
            if ((uintmax_t)sep.n > limit - total) ail_die("bytes too long");
            total += (uintmax_t)sep.n;
        }
        if ((uintmax_t)b.n > limit - total) ail_die("bytes too long");
        total += (uintmax_t)b.n;
    }
    if (!A) ail_die("invalid bytes arena");
    ail_bsplit_meta(A->blk, A->n, A->cap, sizeof *A->blk);
    if (!total) return (ail_bytes){NULL, 0};
    ail_bsplit_growth(A->n, A->cap, sizeof *A->blk);
    unsigned char *q = (unsigned char *)ail_alloc((size_t)total);
    int64_t out = 0;
    for (int64_t i = 0; i < L->n; ++i) {
        ail_bytes b = P->items[L->p[i]];
        if (i && sep.n) { memcpy(q + out, sep.p, (size_t)sep.n); out += sep.n; }
        if (b.n) { memcpy(q + out, b.p, (size_t)b.n); out += b.n; }
    }
    void *resources[] = {q};
    ail_cleanup_frame frame = {ail_cleanup_top, ail_bytes_replace_cleanup, resources};
    ail_cleanup_top = &frame;
    ail_barena_push(A, q);
    ail_cleanup_top = frame.previous;
    return (ail_bytes){q, (int64_t)total};
}

/* Checked helpers return an owned copy before releasing their arena. */
static ail_bytes ail_bytes_return_owned(ail_bytes b) {
    if (b.n < 0 || (uintmax_t)b.n > SIZE_MAX) ail_die("bytes too long");
    unsigned char *q = (unsigned char *)ail_alloc((size_t)(b.n > 0 ? b.n : 1));
    if (b.n > 0) memcpy(q, b.p, (size_t)b.n);
    return (ail_bytes){q, b.n};
}
static ail_bytes ail_bytes_adopt(ail_barena *A, ail_bytes b) {
    ail_barena_push(A, (unsigned char *)b.p);
    return b;
}
/* A returned `bytes` value is handed back exactly the way a returned `list` already is (see
   `ail_list_return` above): through a buffer the *caller* supplies, because a pointer into this
   function's own memory -- whether a view into a parameter or something this function's own arena
   built -- has no safe representation to cross the return with. At most `cap` bytes are written,
   never one more even when `cap` is 0, and what comes back is the value's *true* length whether or
   not it fit, so a buffer that turns out too small is detectable rather than overrun and a retry
   with exactly that much room is always safe -- nothing has been mutated by the attempt. The copy
   happens here, inside the `return` expression, before the free-at-return pass (`_rewrite_returns`)
   frees this function's arena right after -- so a value built by concatenation is fully copied out
   before the memory it pointed into is released, and a view into a parameter was never this
   function's to free in the first place. */
static int64_t ail_bytes_return(ail_bytes b, unsigned char *out, int64_t cap) {
    int64_t m = b.n < cap ? b.n : cap;
    if (m > 0) memcpy(out, b.p, (size_t)m);
    return b.n;
}
static int64_t ck_add(int64_t a, int64_t b) {
    int64_t r; if (__builtin_add_overflow(a, b, &r)) ail_die("integer overflow");
    return r;
}
static int64_t ck_sub(int64_t a, int64_t b) {
    int64_t r; if (__builtin_sub_overflow(a, b, &r)) ail_die("integer overflow");
    return r;
}
static int64_t ck_mul(int64_t a, int64_t b) {
    int64_t r; if (__builtin_mul_overflow(a, b, &r)) ail_die("integer overflow");
    return r;
}
typedef struct { size_t refs; void (*drop)(void *); } ail_obj_header;
static void *ail_obj_retain(void *value) {
    if (value) {
        ail_obj_header *h = value;
        if (!h->refs || h->refs == SIZE_MAX) abort();
        h->refs++;
    }
    return value;
}
static void ail_obj_release(void *value) {
    if (value) {
        ail_obj_header *h = value;
        if (!h->refs) abort();
        if (!--h->refs) { if (h->drop) h->drop(value); free(value); }
    }
}
typedef struct { ail_obj_header header; int64_t n, cap; void **p; } ail_olist;
static int64_t ail_olist_len(ail_olist *v) {
    if (!v) ail_die("unbound struct list");
    return v->n;
}
static void ail_olist_clear(ail_olist *v) {
    int64_t n = ail_olist_len(v);
    v->n = 0;
    for (int64_t i = 0; i < n; i++) ail_obj_release(v->p[i]);
}
static void ail_olist_drop(void *value) {
    ail_olist *v = value;
    ail_olist_clear(v);
    free(v->p);
}
static ail_olist *ail_olist_new(void) {
    ail_olist *v = calloc(1, sizeof *v);
    if (!v) ail_die("out of memory");
    v->header.refs = 1;
    v->header.drop = ail_olist_drop;
    return v;
}
static ail_olist *ail_olist_store(ail_olist * volatile *slot, ail_olist *value, int adopt) {
    if (!adopt) ail_obj_retain(value);
    ail_obj_release(*slot);
    *slot = value;
    return value;
}
static int64_t ail_olist_index(ail_olist *v, int64_t i) {
    int64_t n = ail_olist_len(v);
    if (i < 0) i += n;
    if (i < 0 || i >= n) ail_raise_named(AIL_EXC_INDEX);
    return i;
}
static void *ail_olist_get(ail_olist *v, int64_t i) {
    return v->p[ail_olist_index(v, i)];
}
static void ail_olist_push(ail_olist *v, void *element) {
    ail_olist_len(v);
    if (v->n == v->cap) {
        int64_t limit = SIZE_MAX / sizeof *v->p > INT64_MAX ? INT64_MAX : (int64_t)(SIZE_MAX / sizeof *v->p);
        if (v->cap >= limit) ail_die("struct list capacity overflow");
        int64_t cap = v->cap > limit / 2 ? limit : v->cap ? v->cap * 2 : 8;
        if (cap > limit) cap = limit;
        void **p = realloc(v->p, (size_t)cap * sizeof *p);
        if (!p) ail_die("out of memory");
        v->p = p;
        v->cap = cap;
    }
    v->p[v->n++] = ail_obj_retain(element);
}
static void ail_olist_extend(ail_olist *v, ail_olist *source) {
    int64_t n = ail_olist_len(source);
    ail_olist_len(v);
    int64_t limit = SIZE_MAX / sizeof *v->p > INT64_MAX ? INT64_MAX : (int64_t)(SIZE_MAX / sizeof *v->p);
    if (n > limit - v->n) ail_die("struct list capacity overflow");
    /* Read the original prefix through the current buffer, including self-extension. */
    for (int64_t i = 0; i < n; i++) ail_olist_push(v, source->p[i]);
}
static int64_t ail_olist_slice_bound(int64_t value, int64_t n, int64_t step) {
    if (value < 0) value += n;
    int64_t last = step < 0 ? n - 1 : n;
    if (value < 0) return step < 0 ? -1 : 0;
    return value > last ? last : value;
}
static void ail_olist_slice(ail_olist *v, ail_olist *source, int has_lo, int64_t lo,
                            int has_hi, int64_t hi, int64_t step) {
    int64_t n = ail_olist_len(source);
    if (!step) ail_raise_named(AIL_EXC_VALUE);
    lo = has_lo ? ail_olist_slice_bound(lo, n, step) : step < 0 ? n - 1 : 0;
    hi = has_hi ? ail_olist_slice_bound(hi, n, step) : step < 0 ? -1 : n;
    uint64_t stride = step < 0 ? UINT64_C(0) - (uint64_t)step : (uint64_t)step;
    uint64_t span = step < 0 ? (lo > hi ? (uint64_t)(lo - hi) : 0)
                             : (hi > lo ? (uint64_t)(hi - lo) : 0);
    uint64_t count = span ? 1 + (span - 1) / stride : 0;
    if (count > SIZE_MAX / sizeof *v->p) ail_die("struct list capacity overflow");
    for (uint64_t i = 0; i < count; i++) {
        ail_olist_push(v, source->p[lo]);
        /* Only advance when another valid index exists, including INT64_MIN steps. */
        if (i + 1 < count) lo += step;
    }
}
static void ail_olist_reverse(ail_olist *v) {
    int64_t n = ail_olist_len(v);
    for (int64_t i = 0, j = n - 1; i < j; i++, j--) {
        void *element = v->p[i];
        v->p[i] = v->p[j];
        v->p[j] = element;
    }
}
static void ail_olist_sort(ail_olist *v, const int64_t *spec, int64_t keys,
                           int (*compare)(void *, void *, const int64_t *, int64_t)) {
    int64_t n = ail_olist_len(v);
    if (n < 2) return;
    if ((uint64_t)n > SIZE_MAX / sizeof *v->p) ail_die("struct list capacity overflow");
    void **buffer = malloc((size_t)n * sizeof *buffer);
    if (!buffer) ail_die("out of memory");
    void **source = v->p, **target = buffer;
    for (int64_t width = 1; width < n; width = width > n / 2 ? n : width * 2) {
        for (int64_t lo = 0; lo < n;) {
            int64_t mid = lo + (width < n - lo ? width : n - lo);
            int64_t hi = mid + (width < n - mid ? width : n - mid);
            int64_t left = lo, right = mid, out = lo;
            while (left < mid && right < hi) {
                target[out++] = compare(source[right], source[left], spec, keys) < 0
                    ? source[right++] : source[left++];
            }
            while (left < mid) target[out++] = source[left++];
            while (right < hi) target[out++] = source[right++];
            lo = hi;
        }
        void **swap = source; source = target; target = swap;
    }
    if (source != v->p) memcpy(v->p, source, (size_t)n * sizeof *v->p);
    free(buffer);
}
static void ail_olist_set(ail_olist *v, int64_t i, void *element) {
    i = ail_olist_index(v, i);
    ail_obj_retain(element);
    ail_obj_release(v->p[i]);
    v->p[i] = element;
}
static void *ail_olist_pop(ail_olist *v, int64_t i) {
    i = ail_olist_index(v, i);
    void *element = v->p[i];
    v->n--;
    memmove(v->p + i, v->p + i + 1, (size_t)(v->n - i) * sizeof *v->p);
    return element;
}
static void ail_obj_field_bytes(ail_bytes *slot, ail_bytes value) {
    ail_bytes copy = ail_bytes_return_owned(value);
    free((void *)slot->p);
    *slot = copy;
}
typedef struct {
    ail_obj_header _ail_header;
    ail_bytes f_data;
    int64_t f_position;
} ail_obj_BinaryCursor;
static int ail_olist_compare_BinaryCursor(void *left, void *right, const int64_t *spec, int64_t keys) {
    ail_obj_BinaryCursor *a = left, *b = right;
    for (int64_t k = 0; k < keys; k++) {
        int order = 0;
        switch (spec[k * 2]) { case 0: order = ail_bytes_cmp(a->f_data, b->f_data); break; case 1: order = (a->f_position > b->f_position) - (a->f_position < b->f_position); break; }
        if (order) return spec[k * 2 + 1] < 0 ? (order < 0 ? 1 : -1) : (order < 0 ? -1 : 1);
    }
    return 0;
}
static void ail_olist_sort_BinaryCursor(ail_olist *v, const int64_t *spec, int64_t keys) {
    int64_t n = ail_olist_len(v);
    if ((uint64_t)n > SIZE_MAX / sizeof *v->p) ail_die("struct list capacity overflow");
    
    ail_olist_sort(v, spec, keys, ail_olist_compare_BinaryCursor);
}
static void ail_obj_drop_BinaryCursor(void *value) {
    ail_obj_BinaryCursor *v_self = value;
    free((void *)v_self->f_data.p);
}
static void ail_obj_ctor_cleanup_BinaryCursor(void **p) {
    ail_obj_release(p[0]);
}
static ail_obj_BinaryCursor *ail_new_BinaryCursor(ail_bytes v_data, int64_t v_position) {
    ail_obj_BinaryCursor *v_self = (ail_obj_BinaryCursor *)calloc(1, sizeof(ail_obj_BinaryCursor));
    if (!v_self) { fprintf(stderr, "out of memory\n"); exit(1); }
    v_self->_ail_header.refs = 1;
    v_self->_ail_header.drop = ail_obj_drop_BinaryCursor;
    void *resources[] = {v_self};
    ail_cleanup_frame frame = {ail_cleanup_top, ail_obj_ctor_cleanup_BinaryCursor, resources};
    ail_cleanup_top = &frame;
    ail_obj_field_bytes(&v_self->f_data, v_data);
    v_self->f_position = v_position;
    ail_cleanup_top = frame.previous;
    return v_self;
}
static ail_obj_BinaryCursor *ail_obj_store_BinaryCursor(ail_obj_BinaryCursor * volatile *slot, ail_obj_BinaryCursor *value, int adopt) {
    if (!adopt) ail_obj_retain(value);
    ail_obj_release(*slot);
    *slot = value;
    return value;
}
static
void BinaryCursor__seek(ail_obj_BinaryCursor *v_self, int64_t v_position);
static
void BinaryCursor__reset(ail_obj_BinaryCursor *v_self);
__attribute__((always_inline)) static inline
int64_t BinaryCursor__remaining(ail_obj_BinaryCursor *v_self);
static
ail_bytes BinaryCursor__take(ail_obj_BinaryCursor *v_self, int64_t v_count);
static
ail_bytes BinaryCursor__peek(ail_obj_BinaryCursor *v_self, int64_t v_count);
__attribute__((always_inline)) static inline
int64_t BinaryCursor__skip(ail_obj_BinaryCursor *v_self, int64_t v_count);
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u8(ail_obj_BinaryCursor *v_self);
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u16_le(ail_obj_BinaryCursor *v_self);
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u16_be(ail_obj_BinaryCursor *v_self);
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u32_le(ail_obj_BinaryCursor *v_self);
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u32_be(ail_obj_BinaryCursor *v_self);
ail_bytes binary_cursor_slice(ail_bytes v_data, int64_t v_offset, int64_t v_count);
ail_bytes binary_cursor_rejoin(ail_bytes v_data, int64_t v_first, int64_t v_second);
int64_t py_main(void);
int64_t run(void);
static void ail_unwind_BinaryCursor__seek(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); }
static
void BinaryCursor__seek(ail_obj_BinaryCursor *v_self, int64_t v_position) {
    int64_t v__t1 = 0;
    int64_t v__t2 = 0;
    int64_t v__t3 = 0;
    int64_t v__t4 = 0;
    int64_t v__t5 = 0;
    ail_obj_BinaryCursor *v__t6 = 0;
    int64_t v__exc_base = ail_exc_top;
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__t6)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__seek, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    if ((((((v__t1 = v_position), (v__t2 = 0LL), (v__t1 < v__t2)))) != 0 || ((((v__t3 = v_position), (v__t4 = ((v_self)->f_data).n), (v__t3 > v__t4)))) != 0)) {
        ail_raise_named(1);
    }
    v__t5 = v_position;
    ail_obj_store_BinaryCursor(&v__t6, v_self, 0);
    v__t6->f_position = v__t5;
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t6); ail_exc_top = v__exc_base; return;
}

static void ail_unwind_BinaryCursor__reset(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); }
static
void BinaryCursor__reset(ail_obj_BinaryCursor *v_self) {
    ail_obj_BinaryCursor *v__t1 = 0;
    int64_t v__t2 = 0;
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__t1)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__reset, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    (ail_obj_store_BinaryCursor(&v__t1, v_self, 0), v__t2 = 0LL, BinaryCursor__seek(v__t1, v__t2));
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); return;
}

static void ail_unwind_BinaryCursor__remaining(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); }
__attribute__((always_inline)) static inline
int64_t BinaryCursor__remaining(ail_obj_BinaryCursor *v_self) {
    int64_t v__t1 = 0;
    int64_t v__t2 = 0;
    int64_t v__t3 = 0;
    int64_t v__t4 = 0;
    int64_t v__t5 = 0;
    int64_t v__t6 = 0;
    int64_t v__exc_base = ail_exc_top;
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__remaining, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    if ((((((v__t1 = (v_self)->f_position), (v__t2 = 0LL), (v__t1 < v__t2)))) != 0 || ((((v__t3 = (v_self)->f_position), (v__t4 = ((v_self)->f_data).n), (v__t3 > v__t4)))) != 0)) {
        ail_raise_named(1);
    }
    { int64_t _r1 = ((v__t5 = ((v_self)->f_data).n), (v__t6 = (v_self)->f_position), ck_sub(v__t5, v__t6)); ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_exc_top = v__exc_base; return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_exc_top = v__exc_base; return 0;
}

static void ail_unwind_BinaryCursor__take(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); ail_barena_free(p[2]); }
static
ail_bytes BinaryCursor__take(ail_obj_BinaryCursor *v_self, int64_t v_count) {
    int64_t v_available = 0;
    int64_t v__t1 = 0;
    int64_t v__t2 = 0;
    int64_t v__t3 = 0;
    int64_t v__t4 = 0;
    ail_bytes v__t5 = {0};
    int64_t v__t6 = 0;
    int64_t v__t7 = 0;
    int64_t v__t8 = 0;
    int64_t v__t9 = 0;
    ail_bytes v_selected = {0};
    int64_t v__t10 = 0;
    int64_t v__t11 = 0;
    int64_t v__t12 = 0;
    ail_obj_BinaryCursor *v__t13 = 0;
    ail_barena v__barena = {0};
    int64_t v__exc_base = ail_exc_top;
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__t13), (void *)(&v__barena)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__take, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    v_available = BinaryCursor__remaining(v_self);
    if ((((((v__t1 = v_count), (v__t2 = 0LL), (v__t1 < v__t2)))) != 0 || ((((v__t3 = v_count), (v__t4 = v_available), (v__t3 > v__t4)))) != 0)) {
        ail_raise_named(1);
    }
    v_selected = ({ v__t5 = ail_bytes_adopt(&v__barena, ail_bytes_return_owned(ail_bytes_adopt(&v__barena, ail_bytes_return_owned((v_self)->f_data)))); v__t6 = (v_self)->f_position; v__t9 = ((v__t7 = (v_self)->f_position), (v__t8 = v_count), ck_add(v__t7, v__t8)); ail_bytes_slice(v__t5, v__t6, v__t9); });
    v__t12 = ((v__t10 = (v_self)->f_position), (v__t11 = v_count), ck_add(v__t10, v__t11));
    ail_obj_store_BinaryCursor(&v__t13, v_self, 0);
    v__t13->f_position = v__t12;
    { ail_bytes _r1 = ail_bytes_return_owned(v_selected); ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t13); ail_barena_free(&v__barena); ail_exc_top = v__exc_base; return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t13); ail_barena_free(&v__barena); ail_exc_top = v__exc_base; return (ail_bytes){0};
}

static void ail_unwind_BinaryCursor__peek(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_barena_free(p[1]); }
static
ail_bytes BinaryCursor__peek(ail_obj_BinaryCursor *v_self, int64_t v_count) {
    int64_t v_available = 0;
    int64_t v__t1 = 0;
    int64_t v__t2 = 0;
    int64_t v__t3 = 0;
    int64_t v__t4 = 0;
    ail_bytes v__t5 = {0};
    int64_t v__t6 = 0;
    int64_t v__t7 = 0;
    int64_t v__t8 = 0;
    int64_t v__t9 = 0;
    ail_barena v__barena = {0};
    int64_t v__exc_base = ail_exc_top;
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__barena)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__peek, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    v_available = BinaryCursor__remaining(v_self);
    if ((((((v__t1 = v_count), (v__t2 = 0LL), (v__t1 < v__t2)))) != 0 || ((((v__t3 = v_count), (v__t4 = v_available), (v__t3 > v__t4)))) != 0)) {
        ail_raise_named(1);
    }
    { ail_bytes _r1 = ail_bytes_return_owned(({ v__t5 = ail_bytes_adopt(&v__barena, ail_bytes_return_owned(ail_bytes_adopt(&v__barena, ail_bytes_return_owned((v_self)->f_data)))); v__t6 = (v_self)->f_position; v__t9 = ((v__t7 = (v_self)->f_position), (v__t8 = v_count), ck_add(v__t7, v__t8)); ail_bytes_slice(v__t5, v__t6, v__t9); })); ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_barena_free(&v__barena); ail_exc_top = v__exc_base; return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_barena_free(&v__barena); ail_exc_top = v__exc_base; return (ail_bytes){0};
}

static void ail_unwind_BinaryCursor__skip(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); }
__attribute__((always_inline)) static inline
int64_t BinaryCursor__skip(ail_obj_BinaryCursor *v_self, int64_t v_count) {
    int64_t v_available = 0;
    int64_t v__t1 = 0;
    int64_t v__t2 = 0;
    int64_t v__t3 = 0;
    int64_t v__t4 = 0;
    int64_t v__t5 = 0;
    int64_t v__t6 = 0;
    int64_t v__t7 = 0;
    ail_obj_BinaryCursor *v__t8 = 0;
    int64_t v__exc_base = ail_exc_top;
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__t8)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__skip, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    v_available = BinaryCursor__remaining(v_self);
    if ((((((v__t1 = v_count), (v__t2 = 0LL), (v__t1 < v__t2)))) != 0 || ((((v__t3 = v_count), (v__t4 = v_available), (v__t3 > v__t4)))) != 0)) {
        ail_raise_named(1);
    }
    v__t7 = ((v__t5 = (v_self)->f_position), (v__t6 = v_count), ck_add(v__t5, v__t6));
    ail_obj_store_BinaryCursor(&v__t8, v_self, 0);
    v__t8->f_position = v__t7;
    { int64_t _r1 = (v_self)->f_position; ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t8); ail_exc_top = v__exc_base; return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t8); ail_exc_top = v__exc_base; return 0;
}

static void ail_unwind_BinaryCursor__read_u8(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); ail_barena_free(p[2]); }
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u8(ail_obj_BinaryCursor *v_self) {
    ail_obj_BinaryCursor *v__t1 = 0;
    int64_t v__t2 = 0;
    ail_bytes v_value = {0};
    ail_barena v__barena = {0};
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__t1), (void *)(&v__barena)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__read_u8, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    v_value = ail_bytes_adopt(&v__barena, (ail_obj_store_BinaryCursor(&v__t1, v_self, 0), v__t2 = 1LL, BinaryCursor__take(v__t1, v__t2)));
    { int64_t _r1 = ail_bytes_get(v_value, 0LL); ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return 0;
}

static void ail_unwind_BinaryCursor__read_u16_le(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); ail_barena_free(p[2]); }
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u16_le(ail_obj_BinaryCursor *v_self) {
    ail_obj_BinaryCursor *v__t1 = 0;
    int64_t v__t2 = 0;
    ail_bytes v_value = {0};
    int64_t v__t3 = 0;
    int64_t v__t4 = 0;
    int64_t v__t5 = 0;
    int64_t v__t6 = 0;
    ail_barena v__barena = {0};
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__t1), (void *)(&v__barena)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__read_u16_le, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    v_value = ail_bytes_adopt(&v__barena, (ail_obj_store_BinaryCursor(&v__t1, v_self, 0), v__t2 = 2LL, BinaryCursor__take(v__t1, v__t2)));
    { int64_t _r1 = ((v__t5 = ail_bytes_get(v_value, 0LL)), (v__t6 = ((v__t3 = ail_bytes_get(v_value, 1LL)), (v__t4 = 256LL), ck_mul(v__t3, v__t4))), ck_add(v__t5, v__t6)); ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return 0;
}

static void ail_unwind_BinaryCursor__read_u16_be(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); ail_barena_free(p[2]); }
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u16_be(ail_obj_BinaryCursor *v_self) {
    ail_obj_BinaryCursor *v__t1 = 0;
    int64_t v__t2 = 0;
    ail_bytes v_value = {0};
    int64_t v__t3 = 0;
    int64_t v__t4 = 0;
    int64_t v__t5 = 0;
    int64_t v__t6 = 0;
    ail_barena v__barena = {0};
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__t1), (void *)(&v__barena)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__read_u16_be, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    v_value = ail_bytes_adopt(&v__barena, (ail_obj_store_BinaryCursor(&v__t1, v_self, 0), v__t2 = 2LL, BinaryCursor__take(v__t1, v__t2)));
    { int64_t _r1 = ((v__t5 = ((v__t3 = ail_bytes_get(v_value, 0LL)), (v__t4 = 256LL), ck_mul(v__t3, v__t4))), (v__t6 = ail_bytes_get(v_value, 1LL)), ck_add(v__t5, v__t6)); ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return 0;
}

static void ail_unwind_BinaryCursor__read_u32_le(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); ail_barena_free(p[2]); }
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u32_le(ail_obj_BinaryCursor *v_self) {
    ail_obj_BinaryCursor *v__t1 = 0;
    int64_t v__t2 = 0;
    ail_bytes v_value = {0};
    int64_t v__t3 = 0;
    int64_t v__t4 = 0;
    int64_t v__t5 = 0;
    int64_t v__t6 = 0;
    int64_t v__t7 = 0;
    int64_t v__t8 = 0;
    int64_t v__t9 = 0;
    int64_t v__t10 = 0;
    int64_t v__t11 = 0;
    int64_t v__t12 = 0;
    int64_t v__t13 = 0;
    int64_t v__t14 = 0;
    ail_barena v__barena = {0};
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__t1), (void *)(&v__barena)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__read_u32_le, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    v_value = ail_bytes_adopt(&v__barena, (ail_obj_store_BinaryCursor(&v__t1, v_self, 0), v__t2 = 4LL, BinaryCursor__take(v__t1, v__t2)));
    { int64_t _r1 = ((v__t13 = ((v__t9 = ((v__t5 = ail_bytes_get(v_value, 0LL)), (v__t6 = ((v__t3 = ail_bytes_get(v_value, 1LL)), (v__t4 = 256LL), ck_mul(v__t3, v__t4))), ck_add(v__t5, v__t6))), (v__t10 = ((v__t7 = ail_bytes_get(v_value, 2LL)), (v__t8 = 65536LL), ck_mul(v__t7, v__t8))), ck_add(v__t9, v__t10))), (v__t14 = ((v__t11 = ail_bytes_get(v_value, 3LL)), (v__t12 = 16777216LL), ck_mul(v__t11, v__t12))), ck_add(v__t13, v__t14)); ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return 0;
}

static void ail_unwind_BinaryCursor__read_u32_be(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); ail_barena_free(p[2]); }
__attribute__((always_inline)) static inline
int64_t BinaryCursor__read_u32_be(ail_obj_BinaryCursor *v_self) {
    ail_obj_BinaryCursor *v__t1 = 0;
    int64_t v__t2 = 0;
    ail_bytes v_value = {0};
    int64_t v__t3 = 0;
    int64_t v__t4 = 0;
    int64_t v__t5 = 0;
    int64_t v__t6 = 0;
    int64_t v__t7 = 0;
    int64_t v__t8 = 0;
    int64_t v__t9 = 0;
    int64_t v__t10 = 0;
    int64_t v__t11 = 0;
    int64_t v__t12 = 0;
    int64_t v__t13 = 0;
    int64_t v__t14 = 0;
    ail_barena v__barena = {0};
    ail_obj_retain(v_self);
    void *v__cleanup_args[] = {(void *)(&v_self), (void *)(&v__t1), (void *)(&v__barena)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_BinaryCursor__read_u32_be, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    v_value = ail_bytes_adopt(&v__barena, (ail_obj_store_BinaryCursor(&v__t1, v_self, 0), v__t2 = 4LL, BinaryCursor__take(v__t1, v__t2)));
    { int64_t _r1 = ((v__t13 = ((v__t11 = ((v__t7 = ((v__t3 = ail_bytes_get(v_value, 0LL)), (v__t4 = 16777216LL), ck_mul(v__t3, v__t4))), (v__t8 = ((v__t5 = ail_bytes_get(v_value, 1LL)), (v__t6 = 65536LL), ck_mul(v__t5, v__t6))), ck_add(v__t7, v__t8))), (v__t12 = ((v__t9 = ail_bytes_get(v_value, 2LL)), (v__t10 = 256LL), ck_mul(v__t9, v__t10))), ck_add(v__t11, v__t12))), (v__t14 = ail_bytes_get(v_value, 3LL)), ck_add(v__t13, v__t14)); ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v_self); ail_obj_release(v__t1); ail_barena_free(&v__barena); return 0;
}

static void ail_unwind_binary_cursor_slice(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); ail_obj_release(*(ail_obj_BinaryCursor **)p[2]); ail_obj_release(*(ail_obj_BinaryCursor **)p[3]); ail_barena_free(p[4]); }
ail_bytes binary_cursor_slice(ail_bytes v_data, int64_t v_offset, int64_t v_count) {
    ail_bytes v__t1 = {0};
    int64_t v__t2 = 0;
    ail_obj_BinaryCursor *v__t3 = 0;
    ail_obj_BinaryCursor *v_cursor = 0;
    ail_obj_BinaryCursor *v__t4 = 0;
    int64_t v__t5 = 0;
    ail_obj_BinaryCursor *v__t6 = 0;
    int64_t v__t7 = 0;
    ail_barena v__barena = {0};
    void *v__cleanup_args[] = {(void *)(&v__t3), (void *)(&v_cursor), (void *)(&v__t4), (void *)(&v__t6), (void *)(&v__barena)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_binary_cursor_slice, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    ail_obj_store_BinaryCursor(&v_cursor, ail_obj_store_BinaryCursor(&v__t3, (v__t1 = v_data, v__t2 = 0LL, ail_new_BinaryCursor(v__t1, v__t2)), 1), 0);
    (ail_obj_store_BinaryCursor(&v__t4, v_cursor, 0), v__t5 = v_offset, BinaryCursor__skip(v__t4, v__t5));
    { ail_bytes _r1 = ail_bytes_return_owned(ail_bytes_adopt(&v__barena, (ail_obj_store_BinaryCursor(&v__t6, v_cursor, 0), v__t7 = v_count, BinaryCursor__take(v__t6, v__t7)))); ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v__t3); ail_obj_release(v_cursor); ail_obj_release(v__t4); ail_obj_release(v__t6); ail_barena_free(&v__barena); return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v__t3); ail_obj_release(v_cursor); ail_obj_release(v__t4); ail_obj_release(v__t6); ail_barena_free(&v__barena); return (ail_bytes){0};
}

static void ail_unwind_binary_cursor_rejoin(void **p) { ail_list_free(p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); ail_obj_release(*(ail_obj_BinaryCursor **)p[2]); ail_obj_release(*(ail_obj_BinaryCursor **)p[3]); ail_obj_release(*(ail_obj_BinaryCursor **)p[4]); ail_barena_free(p[5]); ail_bpool_free(p[6]); }
ail_bytes binary_cursor_rejoin(ail_bytes v_data, int64_t v_first, int64_t v_second) {
    ail_bytes v__t1 = {0};
    int64_t v__t2 = 0;
    ail_obj_BinaryCursor *v__t3 = 0;
    ail_obj_BinaryCursor *v_cursor = 0;
    ail_obj_BinaryCursor *v__t4 = 0;
    int64_t v__t5 = 0;
    ail_bytes v_left = {0};
    ail_obj_BinaryCursor *v__t6 = 0;
    int64_t v__t7 = 0;
    ail_bytes v_right = {0};
    ail_bytes v__t8 = {0};
    ail_list v__t9 = {0};
    ail_bytes v__t10 = {0};
    ail_bytes v__t11 = {0};
    ail_barena v__barena = {0};
    ail_bpool v__bpool = {0};
    int64_t v__exc_base = ail_exc_top;
    void *v__cleanup_args[] = {(void *)(&v__t9), (void *)(&v__t3), (void *)(&v_cursor), (void *)(&v__t4), (void *)(&v__t6), (void *)(&v__barena), (void *)(&v__bpool)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_binary_cursor_rejoin, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    ail_obj_store_BinaryCursor(&v_cursor, ail_obj_store_BinaryCursor(&v__t3, (v__t1 = v_data, v__t2 = 0LL, ail_new_BinaryCursor(v__t1, v__t2)), 1), 0);
    v_left = ail_bytes_adopt(&v__barena, (ail_obj_store_BinaryCursor(&v__t4, v_cursor, 0), v__t5 = v_first, BinaryCursor__take(v__t4, v__t5)));
    v_right = ail_bytes_adopt(&v__barena, (ail_obj_store_BinaryCursor(&v__t6, v_cursor, 0), v__t7 = v_second, BinaryCursor__take(v__t6, v__t7)));
    { ail_bytes _r1 = ail_bytes_return_owned(({ v__t8 = ail_bytes_copy(&v__barena, (ail_bytes){(const unsigned char *)"", 0}); ail_list_clear(&v__t9); v__t10 = ail_bytes_copy(&v__barena, v_left); ail_list_push(&v__t9, ail_bpool_alloc(&v__bpool, v__t10)); v__t11 = ail_bytes_copy(&v__barena, v_right); ail_list_push(&v__t9, ail_bpool_alloc(&v__bpool, v__t11)); ail_bytes_join(&v__barena, v__t8, &v__t9, &v__bpool); })); ail_cleanup_top = v__cleanup_frame.previous; ail_list_free(&v__t9); ail_obj_release(v__t3); ail_obj_release(v_cursor); ail_obj_release(v__t4); ail_obj_release(v__t6); ail_barena_free(&v__barena); ail_bpool_free(&v__bpool); ail_exc_top = v__exc_base; return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_list_free(&v__t9); ail_obj_release(v__t3); ail_obj_release(v_cursor); ail_obj_release(v__t4); ail_obj_release(v__t6); ail_barena_free(&v__barena); ail_bpool_free(&v__bpool); ail_exc_top = v__exc_base; return (ail_bytes){0};
}

static void ail_unwind_py_main(void **p) { ail_obj_release(*(ail_obj_BinaryCursor **)p[0]); ail_obj_release(*(ail_obj_BinaryCursor **)p[1]); ail_sarena_free(p[2]); ail_barena_free(p[3]); }
int64_t py_main(void) {
    ail_bytes v__t1 = {0};
    int64_t v__t2 = 0;
    ail_obj_BinaryCursor *v__t3 = 0;
    ail_obj_BinaryCursor *v_cursor = 0;
    int64_t v_total = 0;
    int64_t v__t4 = 0;
    int64_t v__t5 = 0;
    int64_t v__t6 = 0;
    int64_t v__t7 = 0;
    int64_t v__t8 = 0;
    int64_t v__t9 = 0;
    ail_sarena v__sarena = {0};
    ail_barena v__barena = {0};
    int64_t v__exc_base = ail_exc_top;
    void *v__cleanup_args[] = {(void *)(&v__t3), (void *)(&v_cursor), (void *)(&v__sarena), (void *)(&v__barena)};
    ail_cleanup_frame v__cleanup_frame = {ail_cleanup_top, ail_unwind_py_main, v__cleanup_args};
    ail_cleanup_top = &v__cleanup_frame;
    ail_obj_store_BinaryCursor(&v_cursor, ail_obj_store_BinaryCursor(&v__t3, (v__t1 = ail_file_read_bytes(&v__barena, ail_argv_get(&v__sarena, 1LL)), v__t2 = 0LL, ail_new_BinaryCursor(v__t1, v__t2)), 1), 0);
    v_total = 0LL;
    {
        int64_t _wmark1 = v__sarena.n;
        ail_str *_wroots1[] = {};
        while ((((v__t4 = BinaryCursor__remaining(v_cursor)), (v__t5 = 0LL), (v__t4 > v__t5)))) {
            ail_sarena_keep_roots(&v__sarena, _wmark1, _wroots1, 0);
            v_total = ((v__t6 = v_total), (v__t7 = BinaryCursor__read_u8(v_cursor)), ck_add(v__t6, v__t7));
        }
    }
    v__t8 = v_total;
    ail_stdout_text();
    ail_write_int((int64_t)(v__t8));
    ail_stdout_putc(10);
    v__t9 = (v_cursor)->f_position;
    ail_stdout_text();
    ail_write_int((int64_t)(v__t9));
    ail_stdout_putc(10);
    { int64_t _r1 = 0LL; ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v__t3); ail_obj_release(v_cursor); ail_sarena_free(&v__sarena); ail_barena_free(&v__barena); ail_exc_top = v__exc_base; return _r1; }
    ail_cleanup_top = v__cleanup_frame.previous; ail_obj_release(v__t3); ail_obj_release(v_cursor); ail_sarena_free(&v__sarena); ail_barena_free(&v__barena); ail_exc_top = v__exc_base; return 0;
}

int64_t run(void) {
    exit((int)(py_main()));
    return 0LL;
    return 0;
}
#define AIL_ARGC_MIN 1
#define AIL_USAGE "usage: tool\n"
#define AIL_CALL run()

#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif


#ifndef AIL_ARGV_SET
#define AIL_ARGV_SET
#endif
int main(int argc, char **argv) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_TEXT);
    _setmode(_fileno(stderr), _O_TEXT);
#endif
    AIL_ARGV_SET
    if (argc < AIL_ARGC_MIN) { fputs(AIL_USAGE, stderr); return 2; }
    AIL_CALL;
    return 0;
}
