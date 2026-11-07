#!/usr/bin/env python3
"""Hand edit (not a compiler change): flat-layout berth_sim's keyed sorts.

    python3 lab/layout/edits/berth_sim_directsort.py in/program.c out/program.c

`ord.sort(key=lambda i: keys[i])` is emitted as five n-element int64 arrays live at once: `keys`,
a copy of `keys` in list order, the index list, a permutation array and a merge buffer, and
`ail_perm_apply` then copies the list through one more malloc'd buffer. Every comparison reads
`key[perm[i]]`: three dependent loads (perm slot, then the index, then the key) instead of one.

`lab/compare/src/berth_sim/main.c` packs key and index into one 8-byte word
(`ord[i] = ((u64)arr[i] << 22) | i`) and qsorts that one array.

This edit keeps the emitted bottom-up merge sort (same order, same stability) but sorts the index
list **in place** by reading the key column directly, so the permutation array, the copy of the key
column and the `perm_apply` pass all disappear. Ties break on the index, which is what the emitted
sort produces from an initial `range(n)`.

Two variants were measured first and are worse than this one:
  * a 16-byte (key, index) record array: 92.2M LLC against 78.4M — doubling the record costs more
    than the indirection it saves;
  * `qsort` over the index list: 35.1M LLC but +2.17e9 instructions, because qsort's indirect
    comparison loses the inlined merge.
"""
import sys

COMPARATOR = r'''
/* LAYOUT EDIT (lab/layout): merge-sort the index list in place against the key column.
   No copy of the key column, no permutation array, no perm_apply copy. */
static const int64_t *ail_layout_sort_key;
static void ail_layout_sort_idx(int64_t *a, int64_t *buf, int64_t n) {
    if (n < 2) return;
    const int64_t *key = ail_layout_sort_key;
    int64_t *src = a, *dst = buf;
    const int64_t RUN = 8;
    for (int64_t lo = 0; lo < n; lo += RUN) {
        int64_t hi = lo + RUN < n ? lo + RUN : n;
        for (int64_t i = lo + 1; i < hi; i++) {
            int64_t v = src[i], kv = key[v], j = i;
            while (j > lo && kv < key[src[j - 1]]) { src[j] = src[j - 1]; j--; }
            src[j] = v;
        }
    }
    for (int64_t width = RUN; width < n; width *= 2) {
        for (int64_t lo = 0; lo < n; lo += 2 * width) {
            int64_t mid = lo + width < n ? lo + width : n;
            int64_t hi = lo + 2 * width < n ? lo + 2 * width : n;
            int64_t i = lo, j = mid, o = lo;
            if (mid < hi && key[src[mid]] < key[src[mid - 1]]) {
                while (i < mid && j < hi)
                    dst[o++] = (key[src[j]] < key[src[i]]) ? src[j++] : src[i++];
            }
            while (i < mid) dst[o++] = src[i++];
            while (j < hi) dst[o++] = src[j++];
        }
        int64_t *t = src; src = dst; dst = t;
    }
    if (src != a) memcpy(a, src, (size_t)n * sizeof *a);
}
'''

SITES = [
    ("""    ail_list *ir76 = &v__ail_sk1_p;
    ail_list_free(ir76);
    { ail_keycol _kc[1] = {{0, (const void *)(ir74)->p, (ir74)->n}}; ail_keysort_perm(ir76, _kc, 1, 0); }
    ail_list_free(ir74);
    ail_perm_apply((ir65)->p, sizeof(int64_t), (ir65)->n, (ir76)->p, (ir76)->n);
    ail_list_free(ir76);
""",
     """    ail_layout_sort_key = (const int64_t *)(ir74)->p;
    { int64_t *lbuf = (int64_t *)malloc((size_t)((ir65)->n > 0 ? (ir65)->n : 1) * sizeof *lbuf);
      if (!lbuf) ail_die("out of memory");
      ail_layout_sort_idx((ir65)->p, lbuf, (ir65)->n);
      free(lbuf); }
    ail_list_free(ir74);
"""),
    ("""    ail_list *ir897 = &v__ail_sk2_p;
    ail_list_free(ir897);
    { ail_keycol _kc[1] = {{0, (const void *)(ir895)->p, (ir895)->n}}; ail_keysort_perm(ir897, _kc, 1, 0); }
    ail_list_free(ir895);
    ail_perm_apply((ir884)->p, sizeof(int64_t), (ir884)->n, (ir897)->p, (ir897)->n);
    ail_list_free(ir897);
""",
     """    ail_layout_sort_key = (const int64_t *)(ir895)->p;
    { int64_t *lbuf = (int64_t *)malloc((size_t)((ir884)->n > 0 ? (ir884)->n : 1) * sizeof *lbuf);
      if (!lbuf) ail_die("out of memory");
      ail_layout_sort_idx((ir884)->p, lbuf, (ir884)->n);
      free(lbuf); }
    ail_list_free(ir895);
"""),
]


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding='utf8').read()
    anchor = 'static void ail_keysort_perm(ail_list *out, const ail_keycol *given, int nc, int rev) {'
    assert anchor in text, 'anchor for ail_keysort_perm missing'
    text = text.replace(anchor, COMPARATOR + anchor, 1)
    for old, new in SITES:
        assert old in text, 'sort site not found:\n' + old[:160]
        text = text.replace(old, new, 1)
    open(dst, 'w', encoding='utf8').write(text)


if __name__ == '__main__':
    main()
