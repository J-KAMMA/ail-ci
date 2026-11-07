#!/usr/bin/env python3
"""Hand edit (not a compiler change): echo_pack's 4-byte key table as a direct-mapped array.

    python3 lab/layout/edits/echo_pack_flathead.py in/program.c out/program.c

`pack()` keeps `head: dict[int, int]`, a key of four consecutive input bytes to the last position
that started with them. AIL emits that as the general `ail_idict` (an `ail_tab` in HASH mode:
`ail_hent ent[]` = 16 bytes an entry, a parallel `used[]` byte array, an insertion-order `order[]`
int64 array, plus a probe loop). `lab/compare/src/echo_pack/main.c:key()` instead buckets on 20
bits and keeps *only* a 4 MiB `uint32_t head[1<<20]` array holding the last position, chained
through `prev[]` — the program never needs insertion order, deletion, or the exact key.

This edit replaces the dict with a direct open-addressed table of 16-byte `(key, val)` slots in
the same shape the runtime already uses for `ail_hent`, plus a `used[]` byte per slot, keyed by
`ail_tab`'s own hash mix. What it removes is the `order[]` array (8 bytes an entry, written on
every insert and never read) and the general probe/array-vs-hash mode logic.

Semantics kept exactly: `has(k)` then `need(k)` then `put(k, i)` for every i, so the table only
ever grows and lookups always see the previous position. Not modelling `order` is safe only
because this table is a private local and never iterated.
"""
import sys

FLAT = r'''
/* LAYOUT EDIT (lab/layout): the pack() head table as a flat open-addressed (key, val) array.
   No insertion-order array, no ARRAY/HASH mode switch, no separate used[] for the value. */
typedef struct { int64_t key, val; int64_t used; } ail_layout_hslot;
typedef struct { ail_layout_hslot *s; int64_t cap, n; } ail_layout_htab;
static inline uint64_t ail_layout_hmix(int64_t k) {
    uint64_t h = (uint64_t)k * 0x9e3779b97f4a7c15ull;
    h ^= h >> 29;
    return h;
}
static void ail_layout_hinit(ail_layout_htab *T) { T->s = 0; T->cap = 0; T->n = 0; }
static void ail_layout_hfree(ail_layout_htab *T) { free(T->s); T->s = 0; T->cap = 0; T->n = 0; }
static void ail_layout_hgrow(ail_layout_htab *T) {
    int64_t nc = T->cap ? T->cap * 2 : 1024;
    ail_layout_hslot *q = (ail_layout_hslot *)calloc((size_t)nc, sizeof *q);
    if (!q) ail_die("out of memory");
    for (int64_t i = 0; i < T->cap; i++) {
        if (!T->s[i].used) continue;
        int64_t j = (int64_t)(ail_layout_hmix(T->s[i].key) & (uint64_t)(nc - 1));
        while (q[j].used) j = (j + 1) & (nc - 1);
        q[j] = T->s[i];
    }
    free(T->s); T->s = q; T->cap = nc;
}
static int64_t ail_layout_hfind(const ail_layout_htab *T, int64_t key) {
    if (!T->cap) return -1;
    int64_t i = (int64_t)(ail_layout_hmix(key) & (uint64_t)(T->cap - 1));
    while (T->s[i].used) {
        if (T->s[i].key == key) return i;
        i = (i + 1) & (T->cap - 1);
    }
    return -1;
}
static void ail_layout_hput(ail_layout_htab *T, int64_t key, int64_t val) {
    int64_t i = ail_layout_hfind(T, key);
    if (i >= 0) { T->s[i].val = val; return; }
    if ((T->n + 1) * 4 >= T->cap * 3) ail_layout_hgrow(T);
    i = (int64_t)(ail_layout_hmix(key) & (uint64_t)(T->cap - 1));
    while (T->s[i].used) i = (i + 1) & (T->cap - 1);
    T->s[i].key = key; T->s[i].val = val; T->s[i].used = 1; T->n++;
}
'''

# The eleven places the emitted code names the dict.
REPLACE = [
    ('    ail_idict v_head = {0};', '    ail_layout_htab v_head = {0};'),
    ('    { ail_idict_free(&v_head); ail_idict_init(&v_head); }',
     '    { ail_layout_hfree(&v_head); ail_layout_hinit(&v_head); }'),
    ('    ail_idict_free(&v_head);', '    ail_layout_hfree(&v_head);'),
]
CALLS = [
    ('(ail_idict_has(&v_head, ir40) != 0)', '(ail_layout_hfind(&v_head, ir40) >= 0)'),
    ('ail_idict_need(&v_head, ir40)', 'v_head.s[ail_layout_hfind(&v_head, ir40)].val'),
    ('(ail_idict_has(&v_head, ir128) != 0)', '(ail_layout_hfind(&v_head, ir128) >= 0)'),
    ('ail_idict_need(&v_head, ir128)', 'v_head.s[ail_layout_hfind(&v_head, ir128)].val'),
    ('ail_idict_put(&v_head, ir128, ir112);', 'ail_layout_hput(&v_head, ir128, ir112);'),
    ('(ail_idict_has(&v_head, ir150) != 0)', '(ail_layout_hfind(&v_head, ir150) >= 0)'),
    ('ail_idict_need(&v_head, ir150)', 'v_head.s[ail_layout_hfind(&v_head, ir150)].val'),
    ('ail_idict_put(&v_head, ir150, ir20);', 'ail_layout_hput(&v_head, ir150, ir20);'),
]


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding='utf8').read()
    anchor = 'typedef struct { ail_tab table; uint64_t epoch; } ail_idict;'
    assert anchor in text, 'anchor for ail_idict missing'
    text = text.replace(anchor, FLAT + anchor, 1)
    for old, new in REPLACE + CALLS:
        assert old in text, 'site not found: ' + old
        text = text.replace(old, new, 1)
    open(dst, 'w', encoding='utf8').write(text)


if __name__ == '__main__':
    main()
