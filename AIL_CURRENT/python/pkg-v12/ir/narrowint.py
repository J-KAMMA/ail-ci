"""Optional 32-bit storage for proven int-list locals and class fields.

`AIL_NARROW_INT=1` selects it. The analysis is deliberately conservative: a list is
narrowed only when every use is a shape this module's runtime macros convert. Without
the variable nothing is registered, so the emitted C is exactly what it was before.
"""
import ast
import os

import cruntime

LIST = 'list'
INT = 'int'


def enabled():
    return os.environ.get('AIL_NARROW_INT', '').strip().lower() in ('1', 'true', 'yes', 'on')


RUNTIME = r'''
typedef struct {
    int32_t *p;
    int64_t *q;
    ail_len_t n, cap;
    int wide;
} ail_ilist;

static void ail_ilist_free(ail_ilist *s) {
    free(s->p);
    free(s->q);
    s->p = 0;
    s->q = 0;
    s->n = s->cap = 0;
    s->wide = 0;
}
static void ail_ilist_validate(const ail_ilist *s) {
    if (!s || s->n < 0 || s->cap < 0 || s->n > s->cap
            || (s->cap && (s->wide ? !s->q : !s->p)))
        ail_die("invalid narrowed list layout");
}
static void ail_ilist_widen(ail_ilist *s, int64_t need) {
    ail_ilist_validate(s);
    int64_t cap = s->cap;
    if (need > cap) cap = need;
    if (cap < 8) cap = 8;
    int64_t *q = (int64_t *)malloc((size_t)cap * sizeof *q);
    if (!q) ail_die("out of memory");
    for (int64_t i = 0; i < s->n; i++) q[i] = s->p[i];
    free(s->p);
    s->p = 0;
    s->q = q;
    s->cap = cap;
    s->wide = 1;
}
static void ail_ilist_reserve(ail_ilist *s, int64_t extra) {
    ail_ilist_validate(s);
    if (extra <= 0 || s->cap - s->n >= extra) return;
    if (extra > INT64_MAX - s->n) ail_die("list too long");
    int64_t need = s->n + extra;
    if (s->wide || need > INT32_MAX) {
        if (!s->wide) { ail_ilist_widen(s, need); return; }
        if (need > (int64_t)(SIZE_MAX / sizeof *s->q)) ail_die("list too long");
        int64_t cap = s->cap ? s->cap : 8;
        while (cap < need) cap = cap > INT64_MAX / 2 ? need : cap * 2;
        int64_t *q = (int64_t *)realloc(s->q, (size_t)cap * sizeof *q);
        if (!q) ail_die("out of memory");
        s->q = q;
        s->cap = cap;
        return;
    }
    if (need > (int64_t)(SIZE_MAX / sizeof *s->p)) ail_die("list too long");
    int64_t cap = s->cap ? s->cap : 8;
    while (cap < need) cap = cap > INT32_MAX / 2 ? need : cap * 2;
    int32_t *p = (int32_t *)realloc(s->p, (size_t)cap * sizeof *p);
    if (!p) ail_die("out of memory");
    s->p = p;
    s->cap = cap;
}
static __attribute__((noinline)) void ail_ilist_push_slow(ail_ilist *s, int64_t v) {
    if (s->wide) {
        if (s->n == s->cap) ail_ilist_reserve(s, 1);
        s->q[s->n++] = v;
        return;
    }
    if (((uint64_t)v + 2147483648u) <= 4294967295u) {
        ail_ilist_reserve(s, 1);
        s->p[s->n++] = (int32_t)v;
        return;
    }
    if (s->n == s->cap) ail_ilist_widen(s, s->n + 1);
    else ail_ilist_widen(s, s->cap);
    s->q[s->n++] = v;
}
static inline __attribute__((always_inline)) void ail_ilist_push(ail_ilist *s, int64_t v) {
    if (__builtin_expect(s->p && ((uint64_t)v + 2147483648u) <= 4294967295u
                         && s->n < s->cap, 1)) {
        s->p[s->n++] = (int32_t)v;
        return;
    }
    ail_ilist_push_slow(s, v);
}
static __attribute__((noinline, noreturn)) void ail_ilist_index_fail(void) {
    ail_die("list index out of range");
    __builtin_unreachable();
}
static inline __attribute__((always_inline)) int64_t ail_ilist_get(const ail_ilist *s, int64_t i) {
    if (__builtin_expect((uint64_t)i < (uint64_t)s->n && s->p, 1))
        return s->p[i];
    if (i < 0) i += s->n;
    if (i < 0 || i >= s->n) ail_ilist_index_fail();
    return s->wide ? s->q[i] : s->p[i];
}
static __attribute__((noinline)) void ail_ilist_set_slow(ail_ilist *s, int64_t i, int64_t v) {
    if (i < 0) i += s->n;
    if (i < 0 || i >= s->n) ail_die("list index out of range");
    if (s->wide) s->q[i] = v;
    else { ail_ilist_widen(s, s->n); s->q[i] = v; }
}
static inline __attribute__((always_inline)) void ail_ilist_set(ail_ilist *s, int64_t i, int64_t v) {
    if (__builtin_expect((uint64_t)i < (uint64_t)s->n && s->p
                         && ((uint64_t)v + 2147483648u) <= 4294967295u, 1)) {
        s->p[i] = (int32_t)v;
        return;
    }
    ail_ilist_set_slow(s, i, v);
}
static int64_t ail_ilist_pop(ail_ilist *s, int64_t i) {
    if (s->n == 0) ail_die("pop from empty list");
    if (i < 0) i += s->n;
    if (i < 0 || i >= s->n) ail_die("pop index out of range");
    int64_t v = s->wide ? s->q[i] : s->p[i];
    if (s->wide) for (int64_t j = i; j < s->n - 1; j++) s->q[j] = s->q[j + 1];
    else for (int64_t j = i; j < s->n - 1; j++) s->p[j] = s->p[j + 1];
    s->n--;
    return v;
}
static void ail_ilist_clear(ail_ilist *s) { s->n = 0; }
static void ail_ilist_reverse(ail_ilist *s) {
    ail_ilist_validate(s);
    for (int64_t i = 0, j = s->n - 1; i < j; ++i, --j) {
        if (s->wide) { int64_t v = s->q[i]; s->q[i] = s->q[j]; s->q[j] = v; }
        else { int32_t v = s->p[i]; s->p[i] = s->p[j]; s->p[j] = v; }
    }
}
static __attribute__((unused)) int ail__ilist_cmp32(const void *a, const void *b) {
    int32_t x = *(const int32_t *)a, y = *(const int32_t *)b;
    return (x > y) - (x < y);
}
static __attribute__((unused)) int ail__ilist_cmp64(const void *a, const void *b) {
    int64_t x = *(const int64_t *)a, y = *(const int64_t *)b;
    return (x > y) - (x < y);
}
static __attribute__((unused)) void ail_ilist_sort(ail_ilist *s) {
    if (s->n < 2) return;
    if (s->wide) qsort(s->q, (size_t)s->n, sizeof *s->q, ail__ilist_cmp64);
    else qsort(s->p, (size_t)s->n, sizeof *s->p, ail__ilist_cmp32);
}
static void ail__ilist_slice_bounds(const ail_ilist *s, int64_t lo, int64_t hi, int64_t st,
                                    int64_t *a, int64_t *b) {
    int64_t n = s->n;
    if (st == 0) ail_die("slice step cannot be zero");
    if (st > 0) {
        *a = lo < 0 ? (lo + n < 0 ? 0 : lo + n) : (lo > n ? n : lo);
        *b = hi < 0 ? (hi + n < 0 ? 0 : hi + n) : (hi > n ? n : hi);
    } else {
        *a = lo < 0 ? (lo + n < -1 ? -1 : lo + n) : (lo > n - 1 ? n - 1 : lo);
        *b = hi < 0 ? (hi + n < -1 ? -1 : hi + n) : (hi > n - 1 ? n - 1 : hi);
    }
}
static void ail_ilist_slice_from_ilist(ail_ilist *d, const ail_ilist *s,
                                       int64_t lo, int64_t hi, int64_t st) {
    int64_t a, b;
    ail__ilist_slice_bounds(s, lo, hi, st, &a, &b);
    ail_ilist_clear(d);
    for (int64_t i = a; st > 0 ? i < b : i > b; i += st)
        ail_ilist_push(d, s->wide ? s->q[i] : s->p[i]);
}
static void ail_list_slice_from_ilist(ail_list *d, const ail_ilist *s,
                                      int64_t lo, int64_t hi, int64_t st) {
    int64_t a, b;
    ail__ilist_slice_bounds(s, lo, hi, st, &a, &b);
    ail_list_clear(d);
    for (int64_t i = a; st > 0 ? i < b : i > b; i += st)
        ail_list_push(d, s->wide ? s->q[i] : s->p[i]);
}
static ail_ilist ail_ilist_from_list(const ail_list *src) {
    ail_ilist out = {0};
    int wide = 0;
    for (int64_t i = 0; i < src->n; i++)
        if (src->p[i] < INT32_MIN || src->p[i] > INT32_MAX) { wide = 1; break; }
    if (!src->n) return out;
    out.n = out.cap = src->n;
    out.wide = wide;
    if (wide) {
        out.q = (int64_t *)malloc((size_t)src->n * sizeof *out.q);
        if (!out.q) ail_die("out of memory");
        memcpy(out.q, src->p, (size_t)src->n * sizeof *out.q);
    } else {
        out.p = (int32_t *)malloc((size_t)src->n * sizeof *out.p);
        if (!out.p) ail_die("out of memory");
        for (int64_t i = 0; i < src->n; i++) out.p[i] = (int32_t)src->p[i];
    }
    return out;
}
static ail_list ail_ilist_to_list(const ail_ilist *src) {
    ail_list out = {0};
    if (!src->n) return out;
    out.p = (int64_t *)malloc((size_t)src->n * sizeof *out.p);
    if (!out.p) ail_die("out of memory");
    out.n = out.cap = src->n;
    for (int64_t i = 0; i < src->n; i++) out.p[i] = src->wide ? src->q[i] : src->p[i];
    return out;
}
static inline __attribute__((always_inline)) int64_t ail_ilist_field_get(const ail_ilist *s, int64_t i) {
    return ail_ilist_get(s, i);
}
static ail_list ail_ilist_snapshot_list(const int32_t *data, int64_t count);
static ail_list ail_ilist_snapshot_value(ail_ilist s) {
    if (!s.wide) return ail_ilist_snapshot_list(s.p, s.n);
    ail_list out = {0};
    if (!s.n) return out;
    out.p = (int64_t *)malloc((size_t)s.n * sizeof *out.p);
    if (!out.p) ail_die("out of memory");
    out.n = out.cap = s.n;
    for (int64_t i = 0; i < s.n; i++) out.p[i] = s.q[i];
    return out;
}
static ail_list ail_list_snapshot_value(ail_list s) {
    ail_list out = {0};
    if (!s.n) return out;
    out.p = (int64_t *)malloc((size_t)s.n * sizeof *out.p);
    if (!out.p) ail_die("out of memory");
    out.n = out.cap = s.n;
    memcpy(out.p, s.p, (size_t)s.n * sizeof *out.p);
    return out;
}
#define ail_list_snapshot_any(S) _Generic((S), ail_ilist: ail_ilist_snapshot_value, default: ail_list_snapshot_value)((S))
static ail_list ail_ilist_snapshot_list(const int32_t *data, int64_t count) {
    if (count < 0 || (count && !data)) ail_die("invalid narrowed list span");
    ail_list out = {0};
    if (!count) return out;
    out.p = (int64_t *)malloc((size_t)count * sizeof *out.p);
    if (!out.p) ail_die("out of memory");
    out.n = out.cap = count;
    for (int64_t i = 0; i < count; i++) out.p[i] = data[i];
    return out;
}
static void ail_obj_field_ilist_move(ail_ilist *slot, ail_ilist *value) {
    ail_ilist_free(slot);
    *slot = *value;
    *value = (ail_ilist){0};
}
static void ail_obj_field_ilist_from_move(ail_ilist *slot, ail_list *value) {
    ail_ilist_free(slot);
    *slot = ail_ilist_from_list(value);
    free(value->p);
    *value = (ail_list){0};
}
static void ail_obj_field_list_from_move(ail_list *slot, ail_ilist *value) {
    ail_list_free(slot);
    *slot = ail_ilist_to_list(value);
    ail_ilist_free(value);
}
static void ail_obj_field_ilist_from_copy(ail_ilist *slot, const ail_list *value) {
    ail_ilist_free(slot);
    *slot = ail_ilist_from_list(value);
}
static void ail_obj_field_list_from_copy(ail_list *slot, const ail_ilist *value) {
    ail_list_free(slot);
    *slot = ail_ilist_to_list(value);
}
static int64_t ail_ilist_span_len(const int32_t *data, int64_t count) {
    (void)data;
    if (count < 0) ail_die("invalid narrowed list span");
    if ((uint64_t)count > SIZE_MAX / sizeof(int32_t)) ail_die("list too long");
    return count;
}
static int64_t ail_ilist_span_get_slow(const int32_t *data, int64_t count, int64_t index) {
    if (count < 0 || (count && !data)) ail_die("invalid narrowed list span");
    if (index < 0) index += count;
    if (index < 0 || index >= count) ail_die("list index out of range");
    return data[index];
}
static inline __attribute__((always_inline)) int64_t ail_ilist_span_get(const int32_t *data, int64_t count, int64_t index) {
    if (__builtin_expect(!((uint64_t)index < (uint64_t)count), 0))
        return ail_ilist_span_get_slow(data, count, index);
    return data[index];
}
static int64_t ail_ilist_view_get(const int32_t *data, int64_t count, int64_t index) {
    return ail_ilist_span_get(data, count, index);
}
static void ail_ilist_view_set(int32_t *data, int64_t count, int64_t index, int64_t value) {
    if (index < 0) index += count;
    if (index < 0 || index >= count) ail_die("list index out of range");
    if (value < INT32_MIN || value > INT32_MAX)
        ail_die("narrowed list value out of range");
    data[index] = (int32_t)value;
}
static void ail_ilist_copy_from_list(ail_ilist *dst, const ail_list *src) {
    ail_ilist_free(dst);
    *dst = ail_ilist_from_list(src);
}
static void ail_ilist_copy_from_ilist(ail_ilist *dst, const ail_ilist *src) {
    ail_ilist_clear(dst);
    for (int64_t i = 0; i < src->n; i++)
        ail_ilist_push(dst, src->wide ? src->q[i] : src->p[i]);
}
static void ail_list_copy_from_ilist(ail_list *dst, const ail_ilist *src) {
    ail_list_clear(dst);
    for (int64_t i = 0; i < src->n; i++)
        ail_list_push(dst, src->wide ? src->q[i] : src->p[i]);
}
static void ail_ilist_extend_list(ail_ilist *s, const ail_list *src) {
    for (int64_t i = 0; i < src->n; i++) ail_ilist_push(s, src->p[i]);
}

#define ail_list_push(L, V) _Generic((L), ail_ilist*: ail_ilist_push, default: ail_list_push)((L), (V))
#define ail_list_reserve(L, N) _Generic((L), ail_ilist*: ail_ilist_reserve, default: ail_list_reserve)((L), (N))
#define ail_narrow_get(L, I) _Generic((L), ail_ilist*: ail_ilist_get, const ail_ilist*: ail_ilist_get, default: ail_list_get)((L), (I))
#define ail_narrow_set(L, I, V) _Generic((L), ail_ilist*: ail_ilist_set, default: ail_list_set)((L), (I), (V))
#define ail_list_pop(L, I) _Generic((L), ail_ilist*: ail_ilist_pop, default: ail_list_pop)((L), (I))
#define ail_list_clear(L) _Generic((L), ail_ilist*: ail_ilist_clear, default: ail_list_clear)((L))
#define ail_list_free(L) _Generic((L), ail_ilist*: ail_ilist_free, default: ail_list_free)((L))
#define ail_list_reverse(L) _Generic((L), ail_ilist*: ail_ilist_reverse, default: ail_list_reverse)((L))
#define ail_list_snapshot(D, N) _Generic((D), int32_t*: ail_ilist_snapshot_list, const int32_t*: ail_ilist_snapshot_list, default: ail_list_snapshot)((D), (N))
#define ail_list_span_len(D, N) _Generic((D), int32_t*: ail_ilist_span_len, const int32_t*: ail_ilist_span_len, default: ail_list_span_len)((D), (N))
#define ail_list_span_get(D, N, I) _Generic((D), int32_t*: ail_ilist_span_get, const int32_t*: ail_ilist_span_get, default: ail_list_span_get)((D), (N), (I))
#define ail_list_view_get(D, N, I) _Generic((D), int32_t*: ail_ilist_view_get, const int32_t*: ail_ilist_view_get, default: ail_list_view_get)((D), (N), (I))
#define ail_list_view_set(D, N, I, V) _Generic((D), int32_t*: ail_ilist_view_set, default: ail_list_view_set)((D), (N), (I), (V))
#define ail_list_copy(D, S) _Generic((D), ail_ilist*: _Generic((S), ail_ilist*: ail_ilist_copy_from_ilist, const ail_ilist*: ail_ilist_copy_from_ilist, default: ail_ilist_copy_from_list), default: _Generic((S), ail_ilist*: ail_list_copy_from_ilist, const ail_ilist*: ail_list_copy_from_ilist, default: ail_list_copy))((D), (S))
#define ail_narrow_slice_into(D, S, LO, HI, ST) _Generic((D), ail_ilist*: ail_ilist_slice_from_ilist, default: ail_list_slice_from_ilist)((D), (S), (LO), (HI), (ST))
#define ail_numfield_list_append(S, V) _Generic((S), ail_ilist*: ail_ilist_push, default: ail_numfield_list_append)((S), (V))
#define ail_numfield_list_pop(S, I) _Generic((S), ail_ilist*: ail_ilist_pop, default: ail_numfield_list_pop)((S), (I))
#define ail_numfield_list_clear(S) _Generic((S), ail_ilist*: ail_ilist_clear, default: ail_numfield_list_clear)((S))
#define ail_numfield_list_reverse(S) _Generic((S), ail_ilist*: ail_ilist_reverse, default: ail_numfield_list_reverse)((S))
#define ail_numfield_list_set(S, I, V) _Generic((S), ail_ilist*: ail_ilist_set, default: ail_numfield_list_set)((S), (I), (V))
#define ail_numfield_list_extend(S, O) _Generic((S), ail_ilist*: ail_ilist_extend_list, default: ail_numfield_list_extend)((S), (O))
#define ail_obj_field_list_move(S, V) _Generic((S), ail_ilist*: _Generic((V), ail_ilist*: ail_obj_field_ilist_move, default: ail_obj_field_ilist_from_move), default: _Generic((V), ail_ilist*: ail_obj_field_list_from_move, default: ail_obj_field_list_move))((S), (V))
#define ail_obj_field_list(S, V) _Generic((S), ail_ilist*: _Generic((V), ail_ilist*: ail_obj_field_ilist_move, default: ail_obj_field_ilist_from_copy), default: _Generic((V), ail_ilist*: ail_obj_field_list_from_copy, default: ail_obj_field_list))((S), (V))
'''


def register():
    if not enabled() or 'NARROWINT' in cruntime.SOURCE:
        return
    cruntime.SOURCE['NARROWINT'] = RUNTIME
    cruntime.ORDER.append('NARROWINT')
    cruntime.REQUIRES['NARROWINT'] = ['TYPES', 'DIE', 'LIST', 'NUMFIELD']
    cruntime.REQUIRES.setdefault('TYPES', []).append('NARROWINT')


def _empty_list(node):
    return isinstance(node, ast.List) and not node.elts


def _parents(node):
    parents = {}
    for parent in ast.walk(node):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _binding_value(target, value, targets, values):
    if isinstance(target, ast.Name):
        if isinstance(value, ast.Tuple):
            return None
        return value
    if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)) \
            and len(target.elts) == len(value.elts):
        return value
    return None


_NARROW_FIELDS = set()


def blocks_ir(fn, ctx):
    """The IR backend has no `ail_ilist` emitters: a function that touches a narrowed class
    field, or that has a narrowed local, must take the legacy typed emitter, which does. A
    function with neither keeps the IR path, so its C and its error texts are exactly what they
    were without the variable."""
    if not enabled():
        return False
    if getattr(ctx, 'narrow_int', ()):
        return True
    return any(isinstance(node, ast.Attribute) and node.attr in _NARROW_FIELDS
               for node in ast.walk(fn))


def _narrow_ref(node, names):
    """A name/field expression that denotes a list already narrowed (or being narrowed)."""
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Attribute):
        return node.attr in _NARROW_FIELDS
    return False


def _carry_ok(node, names):
    """An expression whose values are all copied out of narrow lists: `.copy()`, `list(x)`,
    `sorted(x)`, `x[a:b]` / `x[a:b:c]`, and `x + y` when both sides are narrow. No new value can
    reach such a list that a narrow source did not already hold, so the width carries over."""
    if _narrow_ref(node, names):
        return True
    if isinstance(node, ast.Call):
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == 'copy'
                and not node.args and not node.keywords):
            return _carry_ok(func.value, names)
        if (isinstance(func, ast.Name) and func.id in ('list', 'sorted')
                and len(node.args) == 1 and not node.keywords):
            return _carry_ok(node.args[0], names)
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        return _carry_ok(node.value, names)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        # Either side may still be an int64 list: the runtime widens on push, so `x + y` never
        # truncates and needs no proof that both operands are narrow.
        return (_carry_ok(node.left, names)
                or isinstance(node.left, (ast.Name, ast.Attribute))) \
            and (_carry_ok(node.right, names)
                 or isinstance(node.right, (ast.Name, ast.Attribute)))
    return False


def _bound_name(parents, value):
    """True when `value` is the whole right side of an assignment to one plain name."""
    parent = parents.get(value)
    if isinstance(parent, (ast.Assign, ast.AnnAssign)) and parent.value is value:
        targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
        return len(targets) == 1 and isinstance(targets[0], ast.Name)
    return False


def _binding_ok(value, names):
    return _empty_list(value) or _carry_ok(value, names)


def _local_bindings_ok(name, fn, names):
    seen = False
    for node in ast.walk(fn):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if value is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id == name:
                    if not _binding_ok(value, names):
                        return False
                    seen = True
                elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)) \
                        and len(target.elts) == len(value.elts):
                    for t, v in zip(target.elts, value.elts):
                        if isinstance(t, ast.Name) and t.id == name:
                            if not _binding_ok(v, names):
                                return False
                            seen = True
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            for t in ast.walk(node.target):
                if isinstance(t, ast.Name) and t.id == name:
                    return False
        elif isinstance(node, (ast.AugAssign, ast.NamedExpr)):
            target = node.target if isinstance(node, ast.AugAssign) else node.target
            if isinstance(target, ast.Name) and target.id == name:
                return False
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return False
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    for t in ast.walk(item.optional_vars):
                        if isinstance(t, ast.Name) and t.id == name:
                            return False
        elif isinstance(node, ast.ExceptHandler) and node.name == name:
            return False
    return seen


_LOCAL_METHODS = frozenset(('append', 'pop', 'clear'))
_PARALLEL_NODES = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _local_use_ok(node, name, parents, names):
    parent = parents.get(node)
    grand = parents.get(parent)
    if isinstance(parent, ast.Subscript) and parent.value is node:
        if isinstance(grand, ast.AugAssign) and grand.target is parent:
            return False
        if isinstance(parent.slice, ast.Slice):
            return _bound_name(parents, parent)
        return True
    if isinstance(parent, ast.Call):
        if parent.func is node:
            return False
        if (isinstance(parent.func, ast.Name) and parent.func.id == 'len'
                and not parent.keywords and len(parent.args) == 1 and parent.args[0] is node):
            return True
        if (isinstance(parent.func, ast.Name) and parent.func.id in ('list', 'sorted')
                and len(parent.args) == 1 and not parent.keywords and parent.args[0] is node):
            return _bound_name(parents, parent)
        return False
    if isinstance(parent, ast.Attribute) and parent.value is node:
        if parent.attr == 'copy':
            return (isinstance(grand, ast.Call) and grand.func is parent
                    and not grand.args and not grand.keywords and _bound_name(parents, grand))
        if parent.attr == 'sort':
            return (isinstance(grand, ast.Call) and grand.func is parent
                    and not grand.args and not grand.keywords)
        return (parent.attr in _LOCAL_METHODS and isinstance(grand, ast.Call)
                and grand.func is parent and not grand.keywords)
    if isinstance(parent, ast.For) and parent.iter is node:
        return True
    if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Add) \
            and (parent.left is node or parent.right is node):
        return _bound_name(parents, parent)
    if isinstance(parent, (ast.Assign, ast.AnnAssign)) and parent.value is node:
        targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
        return all(isinstance(t, ast.Attribute) and t.attr in _NARROW_FIELDS
                   for t in targets)
    if isinstance(parent, ast.Attribute) and parent.value is node:
        return False
    return False


def locals(fn, ctx, classes=None):
    if not enabled() or os.environ.get('AIL_NARROW_LOCALS','1')=='0':
        return frozenset()
    register()
    excluded = set()
    for attr in ('bool_lists', 'flist', 'strlist', 'packed_slist', 'nlist', 'blist',
                 'tstride', 'srowtypes', 'rowof', 'handles', 'ndict', 'optional',
                 'stdin_unbound', 'gridparam'):
        excluded.update(getattr(ctx, attr, ()) or ())
    bindings = getattr(ctx, 'local_bindings', ()) or ()
    parents = _parents(fn)

    def usable(name, names):
        ok = True
        for node in ast.walk(fn):
            if isinstance(node, _PARALLEL_NODES):
                if any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node)):
                    return False
            if not (isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)):
                continue
            if not _local_use_ok(node, name, parents, names):
                return False
        return ok

    candidates = [name for name in bindings
                  if name not in ctx.kind and name not in excluded and name not in ctx.modconsts
                  and ctx.types.get(name) == LIST]
    out = set()
    changed = True
    while changed:
        changed = False
        for name in candidates:
            if name in out:
                continue
            if not _local_bindings_ok(name, fn, out):
                continue
            if usable(name, out):
                out.add(name)
                changed = True
    return frozenset(out)


_FIELD_METHODS = frozenset(('append', 'pop', 'clear'))
_FIELD_BLOCK_METHODS = frozenset(('sort', 'extend', 'count', 'index', 'insert', 'remove'))


def _field_use_ok(node, attr, parents):
    parent = parents.get(node)
    grand = parents.get(parent)
    if isinstance(parent, ast.Subscript) and parent.value is node:
        if isinstance(parent.ctx, ast.Del):
            return False
        if isinstance(parent.slice, ast.Slice):
            return _bound_name(parents, parent)
        if isinstance(grand, ast.AugAssign) and grand.target is parent:
            return False
        return True
    if isinstance(parent, ast.Call):
        if parent.func is node:
            return False
        if (isinstance(parent.func, ast.Name) and parent.func.id == 'len'
                and not parent.keywords and len(parent.args) == 1 and parent.args[0] is node):
            return True
        if (isinstance(parent.func, ast.Name) and parent.func.id in ('list', 'sorted')
                and len(parent.args) == 1 and not parent.keywords and parent.args[0] is node):
            return _bound_name(parents, parent)
        return False
    if isinstance(parent, ast.Attribute) and parent.value is node:
        if parent.attr == 'copy':
            return (isinstance(grand, ast.Call) and grand.func is parent
                    and not grand.args and not grand.keywords and _bound_name(parents, grand))
        if parent.attr == 'sort':
            return (isinstance(grand, ast.Call) and grand.func is parent
                    and not grand.args and not grand.keywords)
        if parent.attr in _FIELD_BLOCK_METHODS:
            return False
        return (parent.attr in _FIELD_METHODS and isinstance(grand, ast.Call)
                and grand.func is parent and not grand.keywords)
    if isinstance(parent, ast.For) and parent.iter is node:
        return True
    if isinstance(parent, (ast.Assign, ast.AnnAssign)):
        targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
        if parent.value is node:
            return all(isinstance(t, ast.Attribute) for t in targets)
        return any(t is node for t in targets)
    if isinstance(parent, (ast.If, ast.While)) and parent.test is node:
        return True
    return False


def _field_move_out(fn, attr):
    for parent in ast.walk(fn):
        for field in ('body', 'orelse', 'finalbody'):
            stmts = getattr(parent, field, None)
            if not isinstance(stmts, list):
                continue
            for index in range(len(stmts) - 1):
                first, second = stmts[index], stmts[index + 1]
                if not isinstance(first, (ast.Assign, ast.AnnAssign)):
                    continue
                value = first.value
                if not (isinstance(value, ast.Attribute) and value.attr == attr):
                    continue
                targets = first.targets if isinstance(first, ast.Assign) else [first.target]
                if not (isinstance(second, ast.Assign) and len(second.targets) == 1):
                    continue
                store = second.targets[0]
                if isinstance(store, ast.Attribute) and store.attr == attr \
                        and isinstance(store.value, ast.Name) and isinstance(value.value, ast.Name) \
                        and store.value.id == value.value.id:
                    if not any(isinstance(t, ast.Attribute) and t.attr == attr for t in targets):
                        return True
    return False


def _field_used_in_parallel(fn, attr):
    for node in ast.walk(fn):
        if isinstance(node, _PARALLEL_NODES):
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and child.attr == attr:
                    return True
    return False


def prepare(fns, classes, classdefs):
    global _NARROW_FIELDS
    _NARROW_FIELDS = set()
    if not enabled():
        return
    register()
    if not classes or os.environ.get('AIL_NARROW_FIELDS','1')=='0':
        return
    names = set()
    for info in classes.values():
        for field, kind in info.field_types.items():
            if kind == LIST:
                names.add(field)
    blocked = set()
    for fn in fns:
        parents = _parents(fn)
        if any(_field_used_in_parallel(fn, field) for field in names):
            blocked.update(field for field in names if _field_used_in_parallel(fn, field))
        if any(_field_move_out(fn, field) for field in names):
            blocked.update(field for field in names if _field_move_out(fn, field))
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and node.attr in names:
                if not _field_use_ok(node, node.attr, parents):
                    blocked.add(node.attr)
    for info in classes.values():
        info.narrow_fields = {field for field, kind in info.field_types.items()
                              if kind == LIST and field not in blocked}
        _NARROW_FIELDS.update(info.narrow_fields)
    register()


register()
