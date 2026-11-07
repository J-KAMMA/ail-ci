#!/usr/bin/env python3
"""Hand edit (not a compiler change): echo_pack writes its `prev` chain unconditionally.

    python3 lab/layout/edits/echo_pack_uncond.py in/program.c out/program.c

`prev[i] = head[k2] if k2 in head else -1` is emitted as *two* dict lookups on the miss path:
`ail_idict_has` (a probe that ends at the vacant slot) and then `ail_idict_need` (a second probe
of the same key, because the emitter does not fuse them). `prev` is initialised to -1 by a
`[-1 for _ in range(n)]` loop that fills 256 MiB, so the conditional store is also redundant:
the slot already holds -1.

The edit (a) drops the fill and (b) makes the store unconditional with one probe
(`has ? need : -1`). It is the layout `lab/compare/src/echo_pack/main.c` uses:
`prev[ins] = head[k]; head[k] = ins;` — one read of the old value, one store.

Safe when `prev` is freshly built by a comprehension in the same block and nothing writes it
between construction and this loop (here: it is a local of `pack`, and the comprehension is two
statements earlier), so the -1 fill cannot be observed.
"""
import sys

OLD_FILL = """    ail_list *ir14 = &v___ir_comp1;
    ail_list_free(ir14);
    ail_list_reserve(ir14, ir1);
    for (int64_t ir15 = 0LL; ir15 < ir1; ir15 += 1) {
        ail_list_push(ir14, -1LL);
    }
"""
NEW_FILL = """    ail_list *ir14 = &v___ir_comp1;
    ail_list_free(ir14);
    ail_list_reserve(ir14, ir1);
    (ir14)->n = ir1;
"""

STORE1_OLD = """                    if (ir129) {
                        int64_t ir130 = ail_idict_need(&v_head, ir128);
                        ir110_p[ir112] = ir130;
                    }
                    ail_idict_put(&v_head, ir128, ir112);"""
STORE1_NEW = """                    int64_t ir130 = ir129 ? ail_idict_need(&v_head, ir128) : -1LL;
                    ir110_p[ir112] = ir130;
                    ail_idict_put(&v_head, ir128, ir112);"""

STORE2_OLD = """                if (ir151) {
                    int64_t ir152 = ail_idict_need(&v_head, ir150);
                    (ir16)->p[ir20] = ir152;
                }
                ail_idict_put(&v_head, ir150, ir20);"""
STORE2_NEW = """                int64_t ir152 = ir151 ? ail_idict_need(&v_head, ir150) : -1LL;
                (ir16)->p[ir20] = ir152;
                ail_idict_put(&v_head, ir150, ir20);"""


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding='utf8').read()
    for old, new in [(OLD_FILL, NEW_FILL), (STORE1_OLD, STORE1_NEW), (STORE2_OLD, STORE2_NEW)]:
        assert old in text, 'site not found: ' + old[:80]
        text = text.replace(old, new, 1)
    open(dst, 'w', encoding='utf8').write(text)


if __name__ == '__main__':
    main()
