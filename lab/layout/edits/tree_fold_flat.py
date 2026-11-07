#!/usr/bin/env python3
"""Hand edit (not a compiler change): tree_fold's keyed sort on the tree's own columns.

    python3 lab/layout/edits/tree_fold_flat.py in/program.c out/program.c

`idx.sort(key=lambda i: (par[i], -sub[i], nm[i], i))` is emitted as six n-element arrays live at
once: the index list, three key columns (`par[idx]`, `-sub[idx]`, `nm[idx]` as an `ail_slist` of
24-byte `ail_str` views), a permutation and a merge buffer. Every comparison then walks a four-entry
`ail_keycol` descriptor and dereferences three more arrays.

The hand-written C (`lab/compare/src/tree_fold/main.c:cmp`) instead compares the node columns the
tree already stores (`sub[]`, `nlen[]`, the name arena) and holds one small child array per parent.

This edit removes the key columns, the permutation, the merge buffer and the `ail_perm_apply` copy,
and sorts the index list in place with `qsort` over a comparator that reads `t->f_par`, the `sub`
vector and `t->f_nm` directly. Same order: `par` ascending, `sub` descending, name bytes, index.
"""
import sys

COMPARATOR = r'''
/* LAYOUT EDIT (lab/layout): sort the index list in place, comparing the tree's own columns.
   No key column, no permutation array, no merge buffer, no perm_apply copy. */
static ail_obj_T *ail_layout_sort_t;
static const int64_t *ail_layout_sort_sub;
static int ail_layout_cmp_idx(const void *pa, const void *pb) {
    int64_t a = *(const int64_t *)pa, b = *(const int64_t *)pb;
    int64_t pa_ = ail_layout_sort_t->f_par.p[a], pb_ = ail_layout_sort_t->f_par.p[b];
    if (pa_ != pb_) return pa_ < pb_ ? -1 : 1;
    int64_t sa = ail_layout_sort_sub[a], sb = ail_layout_sort_sub[b];
    if (sa != sb) return sa > sb ? -1 : 1;              /* -sub ascending */
    ail_str na = ail_pslist_at(&ail_layout_sort_t->f_nm, a);
    ail_str nb = ail_pslist_at(&ail_layout_sort_t->f_nm, b);
    int64_t len = na.n < nb.n ? na.n : nb.n;
    int r = len ? memcmp(na.p, nb.p, (size_t)len) : 0;
    if (r) return r;
    if (na.n != nb.n) return na.n < nb.n ? -1 : 1;
    return a < b ? -1 : (a > b);
}
'''

BEGIN = '    ail_list *ir12 = &v___ir_comp2;'
END = ('    ail_perm_apply((ir10)->p, sizeof(int64_t), (ir10)->n, (ir44)->p, (ir44)->n);\n'
       '    ail_list_free(ir44);\n')

FLAT = """    ail_layout_sort_t = v_t;
    ail_layout_sort_sub = (const int64_t *)(ir5)->p;
    qsort((ir10)->p, (size_t)(ir10)->n, sizeof(int64_t), ail_layout_cmp_idx);
    ail_list_free(ir5);
"""

# `sub` (v_sub) is freed before the key columns are built; the direct comparator reads it, so keep
# it alive until after the sort.
KEEP_SUB_OLD = """    ail_list_free(ir5);
    ail_slist *ir31 = &v___ir_comp4;
"""
KEEP_SUB_NEW = """    ail_slist *ir31 = &v___ir_comp4;
"""


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding='utf8').read()
    anchor = 'void do_sort(ail_obj_T *v_t) {'
    assert anchor in text, 'anchor for do_sort missing'
    text = text.replace(anchor, COMPARATOR + anchor, 1)
    assert KEEP_SUB_OLD in text, 'sub free site not found'
    text = text.replace(KEEP_SUB_OLD, KEEP_SUB_NEW, 1)
    begin = text.index(BEGIN)
    end = text.index(END, begin) + len(END)
    text = text[:begin] + FLAT + text[end:]
    open(dst, 'w', encoding='utf8').write(text)


if __name__ == '__main__':
    main()
