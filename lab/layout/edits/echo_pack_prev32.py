#!/usr/bin/env python3
"""Hand edit (not a compiler change): echo_pack's `prev` list at its natural element width.

    python3 lab/layout/edits/echo_pack_prev32.py in/program.c out/program.c

`prev = [-1 for _ in range(n)]` is a `list[int]`, so the typed build makes it an `ail_list` of
`int64_t`: for echo_pack's 32,000,000-byte perf input that is a 256 MiB array. Every stored value
is a position in `d` (0 .. n-1), and n is a run-time length, so int64 is the only safe width the
compiler can assume. `lab/compare/src/echo_pack/main.c` stores the same chain in `uint32_t *prev`,
128 MiB.

This edit stores the chain in `int32_t` and reads it through a checked accessor, so the arithmetic
and the -1 sentinel are unchanged; only the bytes touched per element halve. It is legal here only
because every index is < 2^31, which the perf input satisfies and a general compiler cannot
assume without a range proof (see RESULTS.md for the condition).
"""
import sys

OLD_INIT_TAIL = """    ail_list *ir16 = &v_prev;
    { ail_list ir17 = *(ir14); *(ir14) = (ail_list){0}; ail_list_free(ir16); *(ir16) = ir17; }
"""

NEW_INIT = """    int32_t *ir16 = v_prev;
    if (ir1 > INT32_MAX) ail_die("list too long for the int32 chain");
    ir16 = (int32_t *)malloc((size_t)(ir1 > 0 ? ir1 : 1) * sizeof *ir16);
    if (!ir16) ail_die("out of memory");
    v_prev = ir16;
    for (int64_t ir15 = 0LL; ir15 < ir1; ir15 += 1) ir16[ir15] = -1;
"""

# two shapes of the block: the `[-1]*n` push loop, or (after echo_pack_uncond.py) a bare length set
OLD_INITS = [
    """    ail_list *ir14 = &v___ir_comp1;
    ail_list_free(ir14);
    ail_list_reserve(ir14, ir1);
    for (int64_t ir15 = 0LL; ir15 < ir1; ir15 += 1) {
        ail_list_push(ir14, -1LL);
    }
""" + OLD_INIT_TAIL,
    """    ail_list *ir14 = &v___ir_comp1;
    ail_list_free(ir14);
    ail_list_reserve(ir14, ir1);
    (ir14)->n = ir1;
""" + OLD_INIT_TAIL,
]

OLD_DECL = '    ail_list v_prev = {0};'
NEW_DECL = '    int32_t *v_prev = 0; (void)v_prev;'

READ = 'int64_t *ir47_p = (ir16)->p; int64_t ir47_n = ir47_p ? (ir16)->n : 0;'
READ_NEW = 'const int32_t *ir47_p = ir16; int64_t ir47_n = ir1;'

WRITE = 'int64_t *ir110_p = (ir16)->p; int64_t ir110_n = ir110_p ? (ir16)->n : 0;'
WRITE_NEW = 'int32_t *ir110_p = ir16; int64_t ir110_n = ir1;'

GET_OLD = 'ail_ir_view_get(ir47_p, ir47_n, ir52)'
GET_NEW = '((uint64_t)(ir52) < (uint64_t)(ir47_n) ? (int64_t)ir47_p[ir52] : (ail_die("list index out of range"), (int64_t)0))'

FREE_OLD = '    ail_list_free(&v_prev);'
FREE_NEW = '    free(v_prev); v_prev = 0;'

STORE_OLD = '(ir16)->p[ir20] = ir152;'
STORE_NEW = 'v_prev[ir20] = (int32_t)ir152;'

FREE2_OLD = '    ail_list_free(ir16);\n'
FREE2_NEW = '    /* v_prev is freed once, by the pointer it now is */\n'

# the function's cleanup frame frees v_prev as a list; with a raw array it must free the pointer
UNWIND_OLD = ("static void ail_unwind_pack(void **p) { ail_idict_free((ail_idict *)p[0]); "
              "ail_bytearray_release(*(ail_bytearray **)p[1]); ail_list_free((ail_list *)p[2]); "
              "ail_list_free((ail_list *)p[3]); }")
UNWIND_NEW = ("static void ail_unwind_pack(void **p) { ail_idict_free((ail_idict *)p[0]); "
              "ail_bytearray_release(*(ail_bytearray **)p[1]); free(*(void **)p[2]); "
              "ail_list_free((ail_list *)p[3]); }")


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding='utf8').read()
    pairs = [(UNWIND_OLD, UNWIND_NEW), (OLD_DECL, NEW_DECL),
             (READ, READ_NEW), (WRITE, WRITE_NEW), (GET_OLD, GET_NEW), (FREE_OLD, FREE_NEW),
             (STORE_OLD, STORE_NEW), (FREE2_OLD, FREE2_NEW)]
    hit = [old for old in OLD_INITS if old in text]
    assert hit, 'the prev construction block was not found'
    pairs.insert(0, (hit[0], NEW_INIT))
    for old, new in pairs:
        assert old in text, 'site not found: ' + old[:80]
        text = text.replace(old, new, 1)
    open(dst, 'w', encoding='utf8').write(text)


if __name__ == '__main__':
    main()
