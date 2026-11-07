#!/usr/bin/env python3
"""Hand edit (not a compiler change): tree_fold's sort with the key columns kept.

    python3 lab/layout/edits/tree_fold_directcmp.py in/program.c out/program.c

The control for `tree_fold_flat.py`: the *same* direct comparator over the tree's own columns, but
the emitted key columns, the `ail_slist` of name views and the permutation array are still built
(they are simply not read). The difference between this variant and `flat` is therefore the cost of
building and freeing those columns, not of using them — it splits the 41.4M LLC saving into
"comparator no longer walks four descriptors plus three gathers" and "the columns are never built".
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tree_fold_flat as F  # noqa: E402

OLD = """    { ail_keycol _kc[4] = {{0, (const void *)(ir19)->p, (ir19)->n}, {0, (const void *)(ir29)->p, (ir29)->n}, {2, (const void *)(ir42)->p, (ir42)->n}, {0, (const void *)(ir10)->p, (ir10)->n}}; ail_keysort_perm(ir44, _kc, 4, 0); }
    ail_list_free(ir19);
    ail_list_free(ir29);
    ail_slist_free(ir42);
    ail_perm_apply((ir10)->p, sizeof(int64_t), (ir10)->n, (ir44)->p, (ir44)->n);
    ail_list_free(ir44);
"""

NEW = """    ail_layout_sort_t = v_t;
    ail_layout_sort_sub = (const int64_t *)(ir5)->p;
    qsort((ir10)->p, (size_t)(ir10)->n, sizeof(int64_t), ail_layout_cmp_idx);
    ail_list_free(ir19);
    ail_list_free(ir29);
    ail_slist_free(ir42);
    ail_list_free(ir44);
"""


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding='utf8').read()
    anchor = 'void do_sort(ail_obj_T *v_t) {'
    assert anchor in text, 'anchor for do_sort missing'
    text = text.replace(anchor, F.COMPARATOR + anchor, 1)
    assert F.KEEP_SUB_OLD in text, 'sub free site not found'
    text = text.replace(F.KEEP_SUB_OLD, F.KEEP_SUB_NEW, 1)
    assert OLD in text, 'sort site not found'
    text = text.replace(OLD, NEW, 1)
    open(dst, 'w', encoding='utf8').write(text)


if __name__ == '__main__':
    main()
