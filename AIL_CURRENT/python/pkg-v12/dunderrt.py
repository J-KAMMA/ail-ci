# -*- coding: utf-8 -*-
"""dunderrt.py -- run-time dispatch of operator special methods on the general path (library batch 5).

The general-path runtime (cruntime.OBJ2) knows the special methods the emitter binds statically
(`__eq__`, `__lt__`, `__len__`, `__getitem__`, `__contains__` on a receiver whose class the emitter
can tell, plus the per-class hooks `__repr__`, `__str__`, `__lt__`, `__iter__`, `__next__`). A program
whose classes define arithmetic or hashing special methods (`__add__`, `__neg__`, `__hash__`, `__bool__`,
`__float__`, ... ; the Fraction, Enum and namedtuple preludes do) needs the other receivers too: `a + b`
where nothing proves the class of `a`, `sum(xs)` starting from 0, `1 + x`, a dict keyed by instances.

`patch(c_text)` rewrites the generated C of such a program only: every operand-kind miss in the runtime
(`unsupported operand type(s)`, `unhashable type`, `object of type ... has no len()`, ...) asks the class
chain of an instance operand first, through per-class tables filled by the program's setup code
(`classobj.d1[]`, `classobj.d2[]`). It is on in every general-path program that has a class (a program
with no class gets the runtime text it always had); the cost is a class-table lookup on the paths that were errors, plus about 2% on
the comparison of instances.

Differences from CPython (declared): there is no `NotImplemented` (a method that cannot handle its operand
raises TypeError itself), the reflected method of a subclass is not tried first, and an exception raised
inside an `__eq__` called from a container lookup (`x in list`, a dict probe) is dropped (the comparison
counts as unequal). Instances without `__eq__` / `__hash__` compare and hash by identity.
"""

# special method -> table index; D1 = (self), D2 = (self, other)
D1 = {'__neg__': 'NEG', '__pos__': 'POS', '__abs__': 'ABS', '__hash__': 'HASH', '__bool__': 'BOOL',
      '__int__': 'INT', '__float__': 'FLOAT', '__floor__': 'FLOOR', '__ceil__': 'CEIL', '__trunc__': 'TRUNC',
      '__len__': 'LEN', '__index__': 'INDEX', '__invert__': 'INVERT'}
D2 = {'__add__': 'ADD', '__radd__': 'RADD', '__sub__': 'SUB', '__rsub__': 'RSUB', '__mul__': 'MUL',
      '__rmul__': 'RMUL', '__truediv__': 'TRUEDIV', '__rtruediv__': 'RTRUEDIV', '__floordiv__': 'FLOORDIV',
      '__rfloordiv__': 'RFLOORDIV', '__mod__': 'MOD', '__rmod__': 'RMOD', '__pow__': 'POW', '__rpow__': 'RPOW',
      '__eq__': 'EQ', '__gt__': 'GT', '__lt__': 'LT', '__le__': 'LE', '__ge__': 'GE',
      '__divmod__': 'DIVMOD', '__rdivmod__': 'RDIVMOD',
      '__round__': 'ROUND', '__getitem__': 'GETITEM', '__contains__': 'CONTAINS',
      '__delitem__': 'DELITEM', '__ne__': 'NE', '__and__': 'AND', '__rand__': 'RAND', '__or__': 'OR', '__ror__': 'ROR',
      '__xor__': 'XOR', '__rxor__': 'RXOR', '__lshift__': 'LSHIFT', '__rlshift__': 'RLSHIFT', '__rshift__': 'RSHIFT',
      '__rrshift__': 'RRSHIFT', '__format__': 'FORMAT'}
D3 = {'__setitem__': 'SETITEM'}
# an operator method that is a hook here; a program defining one of these turns the patch on
HOOKED = frozenset(D1) | frozenset(D2) | frozenset(D3)
# of those, the ones the emitter already binds for a receiver whose class it can tell (a program defining only
# these keeps the runtime text it has always had)
ALREADY_BOUND = frozenset(('__eq__', '__len__', '__getitem__', '__contains__'))

ENUMS = '''
enum { AIL_D1_NEG, AIL_D1_POS, AIL_D1_ABS, AIL_D1_HASH, AIL_D1_BOOL, AIL_D1_INT, AIL_D1_FLOAT, AIL_D1_FLOOR,
       AIL_D1_CEIL, AIL_D1_TRUNC, AIL_D1_LEN, AIL_D1_INDEX, AIL_D1_INVERT, AIL_ND1 };
enum { AIL_D2_ADD, AIL_D2_RADD, AIL_D2_SUB, AIL_D2_RSUB, AIL_D2_MUL, AIL_D2_RMUL, AIL_D2_TRUEDIV, AIL_D2_RTRUEDIV,
       AIL_D2_FLOORDIV, AIL_D2_RFLOORDIV, AIL_D2_MOD, AIL_D2_RMOD, AIL_D2_POW, AIL_D2_RPOW, AIL_D2_EQ, AIL_D2_GT,
       AIL_D2_LT, AIL_D2_LE, AIL_D2_GE, AIL_D2_DIVMOD, AIL_D2_RDIVMOD,
       AIL_D2_ROUND, AIL_D2_GETITEM, AIL_D2_CONTAINS, AIL_D2_DELITEM, AIL_D2_NE, AIL_D2_AND, AIL_D2_RAND, AIL_D2_OR,
       AIL_D2_ROR, AIL_D2_XOR, AIL_D2_RXOR, AIL_D2_LSHIFT, AIL_D2_RLSHIFT, AIL_D2_RSHIFT, AIL_D2_RRSHIFT, AIL_D2_FORMAT, AIL_ND2 };
enum { AIL_D3_SETITEM, AIL_ND3 };
typedef ail_st (*ail_d3_fn)(ail_ctx *, ail_obj *, ail_obj, ail_obj, ail_obj);
typedef ail_st (*ail_d1_fn)(ail_ctx *, ail_obj *, ail_obj);
typedef ail_st (*ail_d2_fn)(ail_ctx *, ail_obj *, ail_obj, ail_obj);
'''

FUNCS = '''
/* ---- operator special methods on instances (dunderrt.py) ---- */
static ail_ctx *ail__gcx;
static inline ail_st ail_iter(ail_ctx *cx, ail_obj *out, ail_obj obj);
static inline ail_st ail_next(ail_ctx *cx, ail_obj *out, ail_obj iterobj);
static inline ail_d1_fn ail_dun1(ail_obj x, int i) {
    if (x.tag != AIL_T_INST) return 0;
    for (ail_obj k = ((ail_instobj *)x.o)->cls; k.tag == AIL_T_CLASS; k = ((ail_classobj *)k.o)->base)
        if (((ail_classobj *)k.o)->d1[i]) return ((ail_classobj *)k.o)->d1[i];
    return 0;
}
static inline ail_d3_fn ail_dun3(ail_obj x, int i) {
    if (x.tag != AIL_T_INST) return 0;
    for (ail_obj k = ((ail_instobj *)x.o)->cls; k.tag == AIL_T_CLASS; k = ((ail_classobj *)k.o)->base)
        if (((ail_classobj *)k.o)->d3[i]) return ((ail_classobj *)k.o)->d3[i];
    return 0;
}
static inline ail_d2_fn ail_dun2(ail_obj x, int i) {
    if (x.tag != AIL_T_INST) return 0;
    for (ail_obj k = ((ail_instobj *)x.o)->cls; k.tag == AIL_T_CLASS; k = ((ail_classobj *)k.o)->base)
        if (((ail_classobj *)k.o)->d2[i]) return ((ail_classobj *)k.o)->d2[i];
    return 0;
}
static void ail__dun_tname(char *buf, size_t n, ail_obj x) {
    if (x.tag == AIL_T_INST) {
        ail_obj c = ((ail_instobj *)x.o)->cls;
        if (c.tag == AIL_T_CLASS) {
            ail_str s = ail_view_to_str(((ail_classobj *)c.o)->name);
            size_t k = 0;
            for (int64_t i = 0; i < s.n && k + 1 < n; i++) { uint32_t ch = (uint32_t)ail_chr(s, i); buf[k++] = ch < 128 ? (char)ch : '?'; }
            buf[k] = 0;
            /* a typed deque is a class `_AilDeque_<T>` from the collections pass, shown as CPython's deque */
            if (!strncmp(buf, "_AilDeque_", 10)) snprintf(buf, n, "%s", "collections.deque");
            return;
        }
    }
    if (x.tag == AIL_T_DICT) {
        if (((ail_gcobj *)x.o)->flags == 1) { snprintf(buf, n, "%s", "Counter"); return; }
        if (((ail_mapobj *)x.o)->dd_factory || ((ail_gcobj *)x.o)->flags == 2) {
            snprintf(buf, n, "%s", "collections.defaultdict"); return;
        }
    }
    if (x.tag == AIL_T_LIST && ((ail_gcobj *)x.o)->flags) { snprintf(buf, n, "%s", "collections.deque"); return; }
    if (x.tag == AIL_T_LIST && ((ail_gcobj *)x.o)->aux) {
        snprintf(buf, n, "%s", ((ail_gcobj *)x.o)->aux == 1 ? "dict_keys"
                               : ((ail_gcobj *)x.o)->aux == 2 ? "dict_values" : "dict_items");
        return;
    }
    snprintf(buf, n, "%s", ail_type_name(x.tag));
}
static const char *ail__dun_tname_s(ail_obj x) { static char b[80]; ail__dun_tname(b, sizeof b, x); return b; }
__attribute__((noinline, cold)) static ail_st ail_dun_noattr(ail_ctx *cx, ail_obj inst, const char *name_for_msg) {
    char b2[200], tn[80]; ail__dun_tname(tn, sizeof tn, inst);
    snprintf(b2, sizeof b2, "'%s' object has no attribute '%s'", tn, name_for_msg);
    return ail_raise_c(cx, AIL_B_ATTRIBUTEERROR, b2);
}
__attribute__((noinline)) static ail_st ail_dun_binop(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, int fwd, int rev, const char *op) {
    ail_d2_fn f = ail_dun2(a, fwd);
    if (f) return f(cx, out, a, b);
    f = ail_dun2(b, rev);
    if (f) return f(cx, out, b, a);
    char buf[240], na[80], nb[80];
    ail__dun_tname(na, sizeof na, a); ail__dun_tname(nb, sizeof nb, b);
    if (op[0] == '+' && (a.tag == AIL_T_LIST || a.tag == AIL_T_TUPLE || a.tag == AIL_T_STR
                         || !strcmp(na, "collections.deque"))) {
        const char *n = a.tag == AIL_T_TUPLE ? "tuple" : a.tag == AIL_T_STR ? "str"
                      : (!strcmp(na, "collections.deque")
                         || (a.tag == AIL_T_LIST && ((ail_gcobj *)a.o)->flags)) ? "deque" : "list";
        snprintf(buf, sizeof buf, "can only concatenate %s (not \\"%s\\") to %s", n, nb, n);
        return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
    }
    if (op[0] == '*') {
        int aseq = a.tag == AIL_T_LIST || a.tag == AIL_T_TUPLE || a.tag == AIL_T_STR
                || (a.tag == AIL_T_INST && (!strcmp(na, "bytes") || !strcmp(na, "bytearray")
                                             || !strcmp(na, "collections.deque")));
        int bseq = b.tag == AIL_T_LIST || b.tag == AIL_T_TUPLE || b.tag == AIL_T_STR
                || (b.tag == AIL_T_INST && (!strcmp(nb, "bytes") || !strcmp(nb, "bytearray")
                                             || !strcmp(nb, "collections.deque")));
        if (aseq || bseq) {
            const char *tn = aseq ? nb : na;
            snprintf(buf, sizeof buf, "can't multiply sequence by non-int of type '%s'", tn);
            return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
        }
    }
    snprintf(buf, sizeof buf, "unsupported operand type(s) for %s: '%s' and '%s'", op, na, nb);
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
static inline int ail_obj_truthy(ail_obj x);
static inline int ail_member_eq(ail_obj a, ail_obj b);
static inline int ail__is_counter(ail_obj x);
static inline ail_st ail_counter_unary(ail_ctx *cx, ail_obj *out, ail_obj a, int neg);
static inline ail_st ail_dun_pos(ail_ctx *cx, ail_obj *out, ail_obj x) {
    if (x.tag == AIL_T_INST) { ail_d1_fn f = ail_dun1(x, AIL_D1_POS); if (f) return f(cx, out, x); }
    else if (x.tag == AIL_T_INT || x.tag == AIL_T_FLOAT) { *out = x; return AIL_OK; }
    else if (x.tag == AIL_T_BOOL) { *out = ail_box_int(x.i); return AIL_OK; }
    else if (ail__is_counter(x)) return ail_counter_unary(cx, out, x, 0);
    char buf[140], tn[80]; ail__dun_tname(tn, sizeof tn, x);
    snprintf(buf, sizeof buf, "bad operand type for unary +: '%s'", tn);
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
static inline ail_st ail_dun_contains(ail_ctx *cx, int *out, ail_obj c, ail_obj item) {
    ail_d2_fn f = ail_dun2(c, AIL_D2_CONTAINS);
    if (f) { ail_obj r; ail_st st = f(cx, &r, c, item); if (st != AIL_OK) return st; *out = ail_obj_truthy(r); return AIL_OK; }
    AIL_FRAME_ENTER(cx, fr, 2);
    ail_st st = ail_iter(cx, &fr.slots[0], c);
    if (st != AIL_OK) { AIL_FRAME_LEAVE(cx, fr); return st; }
    for (;;) {
        ail_obj e; st = ail_next(cx, &e, fr.slots[0]);
        if (st == AIL_STOP) { *out = 0; AIL_FRAME_LEAVE(cx, fr); return AIL_OK; }
        if (st != AIL_OK) { AIL_FRAME_LEAVE(cx, fr); return st; }
        fr.slots[1] = e;
        if (ail_member_eq(e, item)) { *out = 1; AIL_FRAME_LEAVE(cx, fr); return AIL_OK; }
    }
}
__attribute__((noinline)) static int ail_dun_truthy(ail_obj x);
static inline int ail_truthy_u(ail_obj x) { return __builtin_expect(x.tag == AIL_T_INST, 0) ? ail_dun_truthy(x) : ail_obj_truthy(x); }
__attribute__((noinline)) static int ail_dun_truthy(ail_obj x) {
    ail_d1_fn f = ail_dun1(x, AIL_D1_BOOL);
    ail_obj r;
    if (!f) f = ail_dun1(x, AIL_D1_LEN);
    if (!f || !ail__gcx) return 1;
    if (f(ail__gcx, &r, x) != AIL_OK) return 1;
    return ail_obj_truthy(r);
}
__attribute__((noinline)) static int ail_dun_cmp_gt(ail_ctx *cx, int64_t *out, ail_obj a, ail_obj b, ail_st *stp) {
    ail_d2_fn gf = ail_dun2(a, AIL_D2_GT);
    ail_obj r;
    if (!gf) return 0;
    *stp = gf(cx, &r, a, b);
    if (*stp != AIL_OK) return 1;
    if (ail_obj_truthy(r)) { *out = 1; *stp = AIL_OK; return 1; }
    return 0;
}
__attribute__((noinline)) static int ail_dun_cmp_rev(ail_ctx *cx, int64_t *out, ail_obj a, ail_obj b, ail_st *stp) {
    (void)a;
    for (ail_obj k = ((ail_instobj *)b.o)->cls; k.tag == AIL_T_CLASS; k = ((ail_classobj *)k.o)->base) {
        ail_classobj *kc = (ail_classobj *)k.o;
        ail_obj r;
        if (!kc->lt_fn) continue;
        *stp = kc->lt_fn(cx, &r, b, a); if (*stp != AIL_OK) return 1;
        if (ail_obj_truthy(r)) { *out = 1; return *stp = AIL_OK, 1; }
        ail_d2_fn gf = ail_dun2(b, AIL_D2_GT);
        if (gf) { *stp = gf(cx, &r, b, a); if (*stp != AIL_OK) return 1; if (ail_obj_truthy(r)) { *out = -1; return *stp = AIL_OK, 1; } }
        *out = 0; *stp = AIL_OK; return 1;
    }
    return 0;
}
static inline int ail_dun_notni(ail_obj x) { (void)x; return 1; }
__attribute__((noinline)) static int ail_dun_cmp_op(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b,
                                                     int fwd, int rev, ail_st *stp) {
    ail_d2_fn f; ail_obj r;
    if (a.tag == AIL_T_INST) {
        f = ail_dun2(a, fwd);
        if (f) {
            *stp = f(cx, &r, a, b);
            if (*stp != AIL_OK) return 1;
            if (ail_dun_notni(r)) { *out = ail_box_bool(ail_obj_truthy(r)); return 1; }
        }
    }
    if (b.tag == AIL_T_INST) {
        f = ail_dun2(b, rev);
        if (f) {
            *stp = f(cx, &r, b, a);
            if (*stp != AIL_OK) return 1;
            if (ail_dun_notni(r)) { *out = ail_box_bool(ail_obj_truthy(r)); return 1; }
        }
    }
    *stp = AIL_OK;
    return 0;
}
__attribute__((noinline, cold)) static ail_st ail_dun_cmp_fail(ail_ctx *cx, ail_obj a, ail_obj b, const char *op) {
    char na[80], nb[80], buf[200];
    ail__dun_tname(na, sizeof na, a); ail__dun_tname(nb, sizeof nb, b);
    snprintf(buf, sizeof buf, "'%s' not supported between instances of '%s' and '%s'", op, na, nb);
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
/* C42: inside `==`, `!=` and `in` an exception raised by a user __eq__ called for the elements of a container is kept
   here and raised by the operator; elsewhere (index, count, remove, dict and set probes) it is still dropped */
static ail_st ail__eq_err; static int ail__eq_scope;
__attribute__((noinline)) static int ail_dun_eq_raw(ail_obj a, ail_obj b) {
    ail_d2_fn f = ail_dun2(a, AIL_D2_EQ);
    ail_obj r;
    if (f && ail__gcx) {
        if (ail__eq_scope && ail__eq_err) return 0;
        ail_st est = f(ail__gcx, &r, a, b);
        if (est != AIL_OK) { if (ail__eq_scope) ail__eq_err = est; return 0; }
        return ail_obj_truthy(r);
    }
    f = ail_dun2(b, AIL_D2_EQ);
    if (f && ail__gcx) {
        if (ail__eq_scope && ail__eq_err) return 0;
        ail_st est = f(ail__gcx, &r, b, a);
        if (est != AIL_OK) { if (ail__eq_scope) ail__eq_err = est; return 0; }
        return ail_obj_truthy(r);
    }
    return a.tag == b.tag && a.o == b.o;
}
/* `a == b` / `a != b` when an operand is an instance (C42): the user's method decides, whatever the other operand is
   (None included) and an exception it raises propagates; `!=` asks __ne__ and otherwise inverts __eq__; the reflected
   method of the right operand is the next try, identity the last. */
__attribute__((noinline)) static ail_st ail_dun_op_eq(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, int ne) {
    ail_d2_fn f; ail_obj r; ail_st st;
    for (int side = 0; side < 2; side++) {
        ail_obj x = side ? b : a, y = side ? a : b;
        if (ne && (f = ail_dun2(x, AIL_D2_NE))) return f(cx, out, x, y);
        if ((f = ail_dun2(x, AIL_D2_EQ))) {
            st = f(cx, &r, x, y); if (st != AIL_OK) return st;
            *out = ne ? ail_box_bool(!ail_truthy_u(r)) : r; return AIL_OK;
        }
    }
    int same = a.tag == b.tag && a.o == b.o;
    *out = ail_box_bool(ne ? !same : same); return AIL_OK;
}
'''

HASH_CASE = '''        case AIL_T_INST: return ail_dun_hash(cx, out, x);
'''

HASH_FUNC = '''static inline ail_st ail_obj_hash(ail_ctx *cx, int64_t *out, ail_obj x);
__attribute__((noinline)) static ail_st ail_dun_hash(ail_ctx *cx, int64_t *out, ail_obj x) {
    ail_d1_fn hf = ail_dun1(x, AIL_D1_HASH);
    if (hf) {
        ail_obj hr; ail_st hst = hf(cx, &hr, x); if (hst != AIL_OK) return hst;
        if (!(hr.tag == AIL_T_INST && hr.o == x.o)) return ail_obj_hash(cx, out, hr);
    } else if (ail_dun2(x, AIL_D2_EQ) || ((ail_classobj *)((ail_instobj *)x.o)->cls.o)->dc) {
        char hb[120], hn[80]; ail__dun_tname(hn, sizeof hn, x);
        snprintf(hb, sizeof hb, "unhashable type: '%s'", hn);
        return ail_raise_c(cx, AIL_B_TYPEERROR, hb);
    }
    uint64_t hv = (uint64_t)(uintptr_t)x.o; hv ^= hv >> 33; hv *= 0xff51afd7ed558ccdULL; hv ^= hv >> 33;
    *out = (int64_t)hv; return AIL_OK;
}
'''


# runtime functions that only some programs carry (the formatter of safetyrt.py)
OPTIONAL = (
            '            uint16_t ch;\n            if (arg.tag == AIL_T_INT || arg.tag == AIL_T_BOOL) {\n',
            
            '"%%%c format: a real number is required, not %s", (char)t, ail_type_name(arg.tag)',
            '"%%%c format: an integer is required, not %s", (char)t, ail_type_name(arg.tag)',
            '"must be real number, not %s", ail_type_name(arg.tag)',
            'static inline ail_st ail2f_format(ail_ctx *cx, ail_obj *out, ail_obj x, ail_obj specobj) {\n',
            '            int64_t iv;\n            if (arg.tag == AIL_T_INT || arg.tag == AIL_T_BOOL) iv = arg.i;\n',
            '            double d;\n            if (arg.tag == AIL_T_FLOAT) d = ail_float_val(arg);\n')


def _binop_guard(fwd, rev, op):
    return ('if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) return ail_dun_binop(cx, out, a, b, '
            'AIL_D2_%s, AIL_D2_%s, "%s");\n    ' % (fwd, rev, op))


_VIEW_OP_EQ = (
    'static inline ail_st ail_op_eq(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {\n'
    '    if (__builtin_expect(ail__view_kind(a) || ail__view_kind(b), 0)) { int r = 0; ail_st st = ail__view_eq(cx, &r, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(r); return AIL_OK; }\n'
    '    *out = ail_box_bool(ail_obj_eq_raw(a, b)); return AIL_OK;\n}')
_VIEW_OP_NE = (
    'static inline ail_st ail_op_ne(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {\n'
    '    if (__builtin_expect(ail__view_kind(a) || ail__view_kind(b), 0)) { int r = 0; ail_st st = ail__view_eq(cx, &r, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(!r); return AIL_OK; }\n'
    '    *out = ail_box_bool(!ail_obj_eq_raw(a, b)); return AIL_OK;\n}')


CMP_WRAPPERS = [
    ("""static inline ail_st ail_op_lt(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) { if (AIL_IS_ANYSET(a.tag) && AIL_IS_ANYSET(b.tag)) { (void)cx; *out = ail_box_bool(ail_setx_cmp(a, b, 0)); return AIL_OK; } int64_t c; ail_st st = ail_obj_cmp(cx, &c, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(c < 0); return AIL_OK; }""",
     """static inline ail_st ail_op_lt(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) { if (AIL_IS_ANYSET(a.tag) && AIL_IS_ANYSET(b.tag)) { (void)cx; *out = ail_box_bool(ail_setx_cmp(a, b, 0)); return AIL_OK; } if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) { ail_st dst; if (ail_dun_cmp_op(cx, out, a, b, AIL_D2_LT, AIL_D2_GT, &dst)) return dst; return ail_dun_cmp_fail(cx, a, b, "<"); } int64_t c; ail_st st = ail_obj_cmp(cx, &c, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(c < 0); return AIL_OK; }"""),
    ("""static inline ail_st ail_op_le(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) { if (AIL_IS_ANYSET(a.tag) && AIL_IS_ANYSET(b.tag)) { (void)cx; *out = ail_box_bool(ail_setx_cmp(a, b, 1)); return AIL_OK; } int64_t c; ail_st st = ail_obj_cmp(cx, &c, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(c < 0 || (c == 0 && !ail__nan_operand(a, b))); return AIL_OK; }""",
     """static inline ail_st ail_op_le(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) { if (AIL_IS_ANYSET(a.tag) && AIL_IS_ANYSET(b.tag)) { (void)cx; *out = ail_box_bool(ail_setx_cmp(a, b, 1)); return AIL_OK; } if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) { ail_st dst; if (ail_dun_cmp_op(cx, out, a, b, AIL_D2_LE, AIL_D2_GE, &dst)) return dst; return ail_dun_cmp_fail(cx, a, b, "<="); } int64_t c; ail_st st = ail_obj_cmp(cx, &c, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(c < 0 || (c == 0 && !ail__nan_operand(a, b))); return AIL_OK; }"""),
    ("""static inline ail_st ail_op_gt(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) { if (AIL_IS_ANYSET(a.tag) && AIL_IS_ANYSET(b.tag)) { (void)cx; *out = ail_box_bool(ail_setx_cmp(a, b, 2)); return AIL_OK; } int64_t c; ail_st st = ail_obj_cmp(cx, &c, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(c > 0); return AIL_OK; }""",
     """static inline ail_st ail_op_gt(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) { if (AIL_IS_ANYSET(a.tag) && AIL_IS_ANYSET(b.tag)) { (void)cx; *out = ail_box_bool(ail_setx_cmp(a, b, 2)); return AIL_OK; } if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) { ail_st dst; if (ail_dun_cmp_op(cx, out, a, b, AIL_D2_GT, AIL_D2_LT, &dst)) return dst; return ail_dun_cmp_fail(cx, a, b, ">"); } int64_t c; ail_st st = ail_obj_cmp(cx, &c, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(c > 0); return AIL_OK; }"""),
    ("""static inline ail_st ail_op_ge(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) { if (AIL_IS_ANYSET(a.tag) && AIL_IS_ANYSET(b.tag)) { (void)cx; *out = ail_box_bool(ail_setx_cmp(a, b, 3)); return AIL_OK; } int64_t c; ail_st st = ail_obj_cmp(cx, &c, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(c > 0 || (c == 0 && !ail__nan_operand(a, b))); return AIL_OK; }""",
     """static inline ail_st ail_op_ge(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) { if (AIL_IS_ANYSET(a.tag) && AIL_IS_ANYSET(b.tag)) { (void)cx; *out = ail_box_bool(ail_setx_cmp(a, b, 3)); return AIL_OK; } if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) { ail_st dst; if (ail_dun_cmp_op(cx, out, a, b, AIL_D2_GE, AIL_D2_LE, &dst)) return dst; return ail_dun_cmp_fail(cx, a, b, ">="); } int64_t c; ail_st st = ail_obj_cmp(cx, &c, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(c > 0 || (c == 0 && !ail__nan_operand(a, b))); return AIL_OK; }"""),
]

POW_OLD = """static inline ail_st ail_bi_pow(ail_ctx *cx, ail_obj *out, ail_obj base, ail_obj exp, int has_mod, ail_obj modv) {
    if (!has_mod) return ail_op_pow(cx, out, base, exp);
"""

POW_NEW = """static inline ail_st ail_bi_pow(ail_ctx *cx, ail_obj *out, ail_obj base, ail_obj exp, int has_mod, ail_obj modv) {
    if (!has_mod) return ail_op_pow(cx, out, base, exp);
    ail_obj oa = base, ob = exp, om = modv;
    ail_obj *pp[3] = { &base, &exp, &modv };
    for (int i = 0; i < 3; i++) if (pp[i]->tag == AIL_T_INST) {
        ail_d1_fn xf = ail_dun1(*pp[i], AIL_D1_INDEX);
        if (xf) { ail_obj v; ail_st xst = xf(cx, &v, *pp[i]); if (xst != AIL_OK) return xst; *pp[i] = v; }
    }
    if (!ail__is_intlike(base.tag) || !ail__is_intlike(exp.tag) || !ail__is_intlike(modv.tag)) {
        if (oa.tag == AIL_T_FLOAT || ob.tag == AIL_T_FLOAT || om.tag == AIL_T_FLOAT)
            return ail_raise_c(cx, AIL_B_TYPEERROR, "pow() 3rd argument not allowed unless all arguments are integers");
        char na[80], nb[80], nm[80], buf[240];
        ail__dun_tname(na, sizeof na, oa); ail__dun_tname(nb, sizeof nb, ob); ail__dun_tname(nm, sizeof nm, om);
        snprintf(buf, sizeof buf, "unsupported operand type(s) for ** or pow(): '%s', '%s', '%s'", na, nb, nm);
        return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
    }
"""

DIVMOD_OLD = """static inline ail_st ail_bi_divmod(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {
    if (ail__is_num(a.tag) && ail__is_num(b.tag)) {
        if (a.tag == AIL_T_FLOAT || b.tag == AIL_T_FLOAT) {
            if (ail__as_double(b) == 0.0) return ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "float divmod()");
        }
    } else {
        char buf[96]; snprintf(buf, sizeof buf, "unsupported operand type(s) for divmod(): '%s' and '%s'", ail_type_name(a.tag), ail_type_name(b.tag));
        return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
    }
    AIL_FRAME_ENTER(cx, fr, 2);
    ail_st st = ail_op_floordiv(cx, &fr.slots[0], a, b);
    if (st != AIL_OK) { AIL_FRAME_LEAVE(cx, fr); return st; }
    st = ail_op_mod(cx, &fr.slots[1], a, b);
    if (st != AIL_OK) { AIL_FRAME_LEAVE(cx, fr); return st; }
    ail_obj pr[2]; pr[0] = fr.slots[0]; pr[1] = fr.slots[1];
    *out = ail_tuple_new(cx, pr, 2);
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}"""

DIVMOD_NEW = """static inline ail_st ail_bi_divmod(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {
    ail_obj oa = a, ob = b;
    ail_d2_fn f; ail_obj r; ail_st st;
    if (a.tag == AIL_T_INST) {
        f = ail_dun2(a, AIL_D2_DIVMOD);
        if (f) { st = f(cx, &r, a, b); if (st != AIL_OK) return st; if (ail_dun_notni(r)) { *out = r; return AIL_OK; } }
    }
    if (b.tag == AIL_T_INST) {
        f = ail_dun2(b, AIL_D2_RDIVMOD);
        if (f) { st = f(cx, &r, b, a); if (st != AIL_OK) return st; if (ail_dun_notni(r)) { *out = r; return AIL_OK; } }
    }
    if (ail__is_num(a.tag) && ail__is_num(b.tag)) {
        if (a.tag == AIL_T_FLOAT || b.tag == AIL_T_FLOAT) {
            if (ail__as_double(b) == 0.0) return ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "float divmod()");
        }
    } else {
        char na[80], nb[80], buf[200];
        ail__dun_tname(na, sizeof na, oa); ail__dun_tname(nb, sizeof nb, ob);
        snprintf(buf, sizeof buf, "unsupported operand type(s) for divmod(): '%s' and '%s'", na, nb);
        return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
    }
    AIL_FRAME_ENTER(cx, fr, 2);
    st = ail_op_floordiv(cx, &fr.slots[0], a, b);
    if (st != AIL_OK) { AIL_FRAME_LEAVE(cx, fr); return st; }
    st = ail_op_mod(cx, &fr.slots[1], a, b);
    if (st != AIL_OK) { AIL_FRAME_LEAVE(cx, fr); return st; }
    ail_obj pr[2]; pr[0] = fr.slots[0]; pr[1] = fr.slots[1];
    *out = ail_tuple_new(cx, pr, 2);
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}"""


def _edits():
    """(old, new) text replacements, each applied to exactly one place of the runtime."""
    e = []
    # tables in the class object
    e.append(('typedef struct { ail_gcobj hdr; ail_obj name /* STR */; ail_obj base /* CLASS or NONE */; int builtin_id;',
              ENUMS + 'typedef struct { ail_gcobj hdr; ail_obj name /* STR */; ail_obj base /* CLASS or NONE */; int builtin_id;'))
    e.append(('ail_st (*lt_fn)(ail_ctx *, ail_obj *, ail_obj, ail_obj); /* user __lt__ (self, other), or 0 */ } ail_classobj;',
              'ail_st (*lt_fn)(ail_ctx *, ail_obj *, ail_obj, ail_obj); /* user __lt__ (self, other), or 0 */\n'
              '                 ail_st (*d1[AIL_ND1])(ail_ctx *, ail_obj *, ail_obj); /* operator methods (self), dunderrt.py */\n'
              '                 ail_st (*d2[AIL_ND2])(ail_ctx *, ail_obj *, ail_obj, ail_obj); /* operator methods (self, other) */\n'
              '                 ail_st (*d3[AIL_ND3])(ail_ctx *, ail_obj *, ail_obj, ail_obj, ail_obj); /* (self, key, value) */ } ail_classobj;'))
    e.append(('c->iter_iter = 0; c->iter_next = 0; c->repr_fn = 0; c->str_fn = 0; c->lt_fn = 0;',
              'c->iter_iter = 0; c->iter_next = 0; c->repr_fn = 0; c->str_fn = 0; c->lt_fn = 0;\n'
              '    memset(c->d1, 0, sizeof c->d1); memset(c->d2, 0, sizeof c->d2); memset(c->d3, 0, sizeof c->d3);'))
    # truthiness and equality
    # ail_obj_truthy itself is left alone (the runtime's own tests stay as small as they were); bool() and `not` ask the class here,
    # and the conditions of the program's own code are rewritten in patch()
    e.append(('static inline ail_obj ail_to_bool(ail_obj x) { return ail_box_bool(ail_obj_truthy(x)); }',
              'static inline ail_obj ail_to_bool(ail_obj x) { return ail_box_bool(ail_truthy_u(x)); }'))
    e.append(('static inline ail_obj ail_op_not(ail_obj a) { return ail_box_bool(!ail_obj_truthy(a)); }',
              'static inline ail_obj ail_op_not(ail_obj a) { return ail_box_bool(!ail_truthy_u(a)); }'))
    e.append(('static inline int ail_obj_eq_raw(ail_obj a, ail_obj b) {\n',
              'static inline int ail_obj_eq_raw(ail_obj a, ail_obj b) {\n'
              '    if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) return ail_dun_eq_raw(a, b);\n'))
    e.append((_VIEW_OP_EQ,
              'static inline ail_st ail_op_eq(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {\n'
              '    if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) return ail_dun_op_eq(cx, out, a, b, 0);\n'
              '    if (__builtin_expect(ail__view_kind(a) || ail__view_kind(b), 0)) { int r = 0; ail_st st = ail__view_eq(cx, &r, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(r); return AIL_OK; }\n'
              '    int sv_scope = ail__eq_scope; ail_st sv_err = ail__eq_err; ail__eq_scope = 1; ail__eq_err = 0;\n'
              '    int eq = ail_obj_eq_raw(a, b);\n'
              '    ail_st e = ail__eq_err; ail__eq_scope = sv_scope; ail__eq_err = sv_err; if (e) return e;\n'
              '    *out = ail_box_bool(eq); return AIL_OK;\n}'))
    e.append((_VIEW_OP_NE,
              'static inline ail_st ail_op_ne(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {\n'
              '    if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) return ail_dun_op_eq(cx, out, a, b, 1);\n'
              '    if (__builtin_expect(ail__view_kind(a) || ail__view_kind(b), 0)) { int r = 0; ail_st st = ail__view_eq(cx, &r, a, b); if (st != AIL_OK) return st; *out = ail_box_bool(!r); return AIL_OK; }\n'
              '    int sv_scope = ail__eq_scope; ail_st sv_err = ail__eq_err; ail__eq_scope = 1; ail__eq_err = 0;\n'
              '    int eq = ail_obj_eq_raw(a, b);\n'
              '    ail_st e = ail__eq_err; ail__eq_scope = sv_scope; ail__eq_err = sv_err; if (e) return e;\n'
              '    *out = ail_box_bool(!eq); return AIL_OK;\n}'))
    e.append(('            for (int64_t i = 0; i < v->n; i++) if (ail_member_eq(v->p[i], item)) { *out = 1; return AIL_OK; }\n'
              '            *out = 0; return AIL_OK;\n',
              '            int sv_scope = ail__eq_scope; ail_st sv_err = ail__eq_err; ail__eq_scope = 1; ail__eq_err = 0;\n'
              '            int found = 0;\n'
              '            for (int64_t i = 0; i < v->n && !ail__eq_err; i++) if (ail_member_eq(v->p[i], item)) { found = 1; break; }\n'
              '            ail_st e = ail__eq_err; ail__eq_scope = sv_scope; ail__eq_err = sv_err; if (e) return e;\n'
              '            *out = found; return AIL_OK;\n'))
    # a slice of an instance: there are no slice objects, so __getitem__ cannot be given one (named, not "not subscriptable")
    e.append(('    char buf[64]; snprintf(buf, sizeof buf, "\'%s\' object is not subscriptable", ail_type_name(c.tag));\n'
              '    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);\n}\n\n/* ====',
              '    if (c.tag == AIL_T_INST && ail_dun2(c, AIL_D2_GETITEM))\n'
              '        return ail_raise_c(cx, AIL_B_NOTIMPLEMENTEDERROR, "slicing an instance through __getitem__ is not supported: this path has no slice objects");\n'
              '    char buf[64]; snprintf(buf, sizeof buf, "\'%s\' object is not subscriptable", ail_type_name(c.tag));\n'
              '    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);\n}\n\n/* ===='))
    # hashing
    e.append(('        default: {\n            char buf[64]; snprintf(buf, sizeof buf, "unhashable type: \'%s\'", ail_type_name(x.tag));\n'
              '            return ail_raise_c(cx, AIL_B_TYPEERROR, buf);\n        }\n    }\n}\nstatic inline ail_st ail_obj_cmp(',
              HASH_CASE + '        default: {\n            char buf[64]; snprintf(buf, sizeof buf, "unhashable type: \'%s\'", ail_type_name(x.tag));\n'
              '            return ail_raise_c(cx, AIL_B_TYPEERROR, buf);\n        }\n    }\n}\nstatic inline ail_st ail_obj_cmp('))
    # hash() of an instance whose class has __hash__ is that method's int (CPython: -1 becomes -2), not the table hash
    e.append(('static inline ail_st ail_pyhash_inst(ail_ctx *cx, int64_t *out, ail_obj x) { return ail_obj_hash(cx, out, x); }\n',
              'static inline ail_st ail_pyhash_inst(ail_ctx *cx, int64_t *out, ail_obj x) {\n'
              '    ail_d1_fn hf = ail_dun1(x, AIL_D1_HASH);\n'
              '    if (!hf) return ail_obj_hash(cx, out, x);\n'
              '    ail_obj hr; ail_st hst = hf(cx, &hr, x); if (hst != AIL_OK) return hst;\n'
              '    if (hr.tag == AIL_T_INT || hr.tag == AIL_T_BOOL) {\n'
              '        int64_t hv = hr.i;\n'
              '        *out = hv == -1 ? -2 : hv; return AIL_OK;\n    }\n'
              '    return ail_raise_c(cx, AIL_B_TYPEERROR, "__hash__ method should return an integer");\n}\n'))
    # ordering: a on the left with no < answer (its > may answer), or the instance on the right (out of line, so that the
    # comparison of two instances, the hot case of a sort, keeps its size)
    e.append(('            if (b.tag == AIL_T_INST) { st = kc->lt_fn(cx, &r, b, a); if (st != AIL_OK) return st; if (ail_obj_truthy(r)) { *out = 1; return AIL_OK; } }\n'
              '            *out = 0; return AIL_OK;\n        }\n    }\n',
              '            if (b.tag == AIL_T_INST) { st = kc->lt_fn(cx, &r, b, a); if (st != AIL_OK) return st; if (ail_obj_truthy(r)) { *out = 1; return AIL_OK; } }\n'
              '            else { ail_st gst; if (ail_dun_cmp_gt(cx, out, a, b, &gst)) return gst; }\n'
              '            *out = 0; return AIL_OK;\n        }\n    }\n'
              '    if (b.tag == AIL_T_INST && a.tag != AIL_T_INST) { ail_st rst; if (ail_dun_cmp_rev(cx, out, a, b, &rst)) return rst; }\n'))
    # (an attribute of a value that is not an instance is an AttributeError: cruntime's ail_inst_getattr checks the tag itself)
    # str() of an instance: the first class of the chain that defines __str__ wins, whether or not a class below it defines
    # __repr__ (object.__str__ only falls back to repr when no class defines __str__)
    e.append(('            if (kc->repr_fn) break;\n        }\n    }\n    ail_obj_write_repr(cx, x, f);',
              '        }\n    }\n    ail_obj_write_repr(cx, x, f);'))
    # arithmetic
    e.append(('    char buf[96]; snprintf(buf, sizeof buf, "unsupported operand type(s) for +: \'%s\' and \'%s\'"',
              '    ' + _binop_guard('ADD', 'RADD', '+') + 'char buf[96]; snprintf(buf, sizeof buf, "unsupported operand type(s) for +: \'%s\' and \'%s\'"'))
    e.append(('    char buf[96]; snprintf(buf, sizeof buf, "unsupported operand type(s) for -: \'%s\' and \'%s\'"',
              '    ' + _binop_guard('SUB', 'RSUB', '-') + 'char buf[96]; snprintf(buf, sizeof buf, "unsupported operand type(s) for -: \'%s\' and \'%s\'"'))
    e.append(('    char buf[96]; snprintf(buf, sizeof buf, "unsupported operand type(s) for *: \'%s\' and \'%s\'"',
              '    ' + _binop_guard('MUL', 'RMUL', '*') + 'char buf[96]; snprintf(buf, sizeof buf, "unsupported operand type(s) for *: \'%s\' and \'%s\'"'))
    for sym, fwd, rev in (('//', 'FLOORDIV', 'RFLOORDIV'), ('%', 'MOD', 'RMOD'), ('/', 'TRUEDIV', 'RTRUEDIV'),
                          ('**', 'POW', 'RPOW')):
        e.append(('    return ail_raise_c(cx, AIL_B_TYPEERROR, "unsupported operand type(s) for %s");' % sym,
                  '    ' + _binop_guard(fwd, rev, sym) + 'return ail_raise_c(cx, AIL_B_TYPEERROR, "unsupported operand type(s) for %s");' % sym))
    # bitwise operators and ~ on an instance (Flag / IntFlag classes, user __or__ ...)
    e.append(('static inline ail_st ail__bit_logic(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, char op) {\n',
              'static inline ail_st ail__bit_logic(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, char op) {\n'
              '    if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) return op == \'&\' ? ail_dun_binop(cx, out, a, b, AIL_D2_AND, AIL_D2_RAND, "&")'
              ' : op == \'|\' ? ail_dun_binop(cx, out, a, b, AIL_D2_OR, AIL_D2_ROR, "|") : ail_dun_binop(cx, out, a, b, AIL_D2_XOR, AIL_D2_RXOR, "^");\n'))
    e.append(('static inline ail_st ail_op_lshift(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {\n',
              'static inline ail_st ail_op_lshift(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {\n'
              '    if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) return ail_dun_binop(cx, out, a, b, AIL_D2_LSHIFT, AIL_D2_RLSHIFT, "<<");\n'))
    e.append(('static inline ail_st ail_op_rshift(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {\n',
              'static inline ail_st ail_op_rshift(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {\n'
              '    if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) return ail_dun_binop(cx, out, a, b, AIL_D2_RSHIFT, AIL_D2_RRSHIFT, ">>");\n'))
    e.append(('static inline ail_st ail_op_invert(ail_ctx *cx, ail_obj *out, ail_obj a) {\n',
              'static inline ail_st ail_op_invert(ail_ctx *cx, ail_obj *out, ail_obj a) {\n'
              '    if (a.tag == AIL_T_INST) { ail_d1_fn f = ail_dun1(a, AIL_D1_INVERT); if (f) return f(cx, out, a); }\n'))
    # format(x, spec) / f"{x:spec}" of an instance whose class defines __format__ (an Enum / Flag member does)
    e.append(('static inline ail_st ail_obj_format(ail_ctx *cx, ail_obj *out, ail_obj x, ail_obj specobj) {\n',
              'static inline ail_st ail_obj_format(ail_ctx *cx, ail_obj *out, ail_obj x, ail_obj specobj) {\n'
              '    if (x.tag == AIL_T_INST) { ail_d2_fn ff = ail_dun2(x, AIL_D2_FORMAT); if (ff) return ff(cx, out, x, specobj); }\n'))
    e.append(('static inline ail_st ail2f_format(ail_ctx *cx, ail_obj *out, ail_obj x, ail_obj specobj) {\n',
              'static inline ail_st ail2f_format(ail_ctx *cx, ail_obj *out, ail_obj x, ail_obj specobj) {\n'
              '    if (x.tag == AIL_T_INST) { ail_d2_fn ff = ail_dun2(x, AIL_D2_FORMAT); if (ff) return ff(cx, out, x, specobj); }\n'))
    # `%d` / `%x` / `%f` of an instance (an IntEnum / IntFlag member): int() / index() / float() of it, as PyUnicode_Format does
    e.append(('            int64_t iv;\n            if (arg.tag == AIL_T_INT || arg.tag == AIL_T_BOOL) iv = arg.i;\n',
              '            int64_t iv;\n'
              '            if (arg.tag == AIL_T_INST) {\n'
              '                int dec = t == \'d\' || t == \'i\' || t == \'u\';\n'
              '                ail_d1_fn cf = dec ? ail_dun1(arg, AIL_D1_INT) : 0;\n'
              '                if (!cf) cf = ail_dun1(arg, AIL_D1_INDEX);\n'
              '                if (!cf && dec) cf = ail_dun1(arg, AIL_D1_TRUNC);\n'
              '                if (cf) { ail_obj cv; st = cf(cx, &cv, arg); if (st != AIL_OK) goto fail; arg = cv; }\n'
              '            }\n'
              '            if (arg.tag == AIL_T_INT || arg.tag == AIL_T_BOOL) iv = arg.i;\n'))
    e.append(('            double d;\n            if (arg.tag == AIL_T_FLOAT) d = ail_float_val(arg);\n',
              '            double d;\n'
              '            if (arg.tag == AIL_T_INST) {\n'
              '                ail_d1_fn cf = ail_dun1(arg, AIL_D1_FLOAT); if (!cf) cf = ail_dun1(arg, AIL_D1_INDEX);\n'
              '                if (cf) { ail_obj cv; st = cf(cx, &cv, arg); if (st != AIL_OK) goto fail; arg = cv; }\n'
              '            }\n'
              '            if (arg.tag == AIL_T_FLOAT) d = ail_float_val(arg);\n'))
    e.append(('"%%%c format: a real number is required, not %s", (char)t, ail_type_name(arg.tag)',
              '"%%%c format: a real number is required, not %s", (char)t, ail__dun_tname_s(arg)'))
    e.append(('"%%%c format: an integer is required, not %s", (char)t, ail_type_name(arg.tag)',
              '"%%%c format: an integer is required, not %s", (char)t, ail__dun_tname_s(arg)'))
    e.append(('"must be real number, not %s", ail_type_name(arg.tag)',
              '"must be real number, not %s", ail__dun_tname_s(arg)'))
    e.append(('            uint16_t ch;\n            if (arg.tag == AIL_T_INT || arg.tag == AIL_T_BOOL) {\n',
              '            uint16_t ch;\n            if (arg.tag == AIL_T_INST) { ail_d1_fn cf = ail_dun1(arg, AIL_D1_INDEX); if (cf) { ail_obj cv; st = cf(cx, &cv, arg); if (st != AIL_OK) goto fail; arg = cv; } }\n            if (arg.tag == AIL_T_INT || arg.tag == AIL_T_BOOL) {\n'))
    # the add in front of the dispatch helpers: they must be visible before ail_op_add
    e.append(('/* sum(): CPython 3.12 builtin_sum_impl.', '/* sum(): CPython 3.12 builtin_sum_impl.'))
    # unary and builtin conversions
    e.append(('    char buf[64]; snprintf(buf, sizeof buf, "bad operand type for unary -: \'%s\'", ail_type_name(a.tag));',
              '    if (a.tag == AIL_T_INST) { ail_d1_fn f = ail_dun1(a, AIL_D1_NEG); if (f) return f(cx, out, a); }\n'
              '    char buf[64]; snprintf(buf, sizeof buf, "bad operand type for unary -: \'%s\'", ail_type_name(a.tag));'))
    e.append(('    char buf[64]; snprintf(buf, sizeof buf, "bad operand type for abs(): \'%s\'", ail_type_name(x.tag));',
              '    if (x.tag == AIL_T_INST) { ail_d1_fn f = ail_dun1(x, AIL_D1_ABS); if (f) return f(cx, out, x); }\n'
              '    char buf[64]; snprintf(buf, sizeof buf, "bad operand type for abs(): \'%s\'", ail_type_name(x.tag));'))
    e.append(('            case AIL_T_STR: base = 10; break;\n            default: {\n                char buf[128]; snprintf(buf, sizeof buf, "int() argument must be',
              '            case AIL_T_STR: base = 10; break;\n'
              '            case AIL_T_INST: {\n'
              '                ail_d1_fn f = ail_dun1(x, AIL_D1_INT); if (!f) f = ail_dun1(x, AIL_D1_INDEX); if (!f) f = ail_dun1(x, AIL_D1_TRUNC);\n'
              '                if (f) return f(cx, out, x);\n'
              '            }\n            /* fall through */\n'
              '            default: {\n                char buf[128]; snprintf(buf, sizeof buf, "int() argument must be'))
    e.append(('        case AIL_T_STR: break;\n        default: {\n            char buf[96]; snprintf(buf, sizeof buf, "float() argument must be',
              '        case AIL_T_STR: break;\n'
              '        case AIL_T_INST: {\n'
              '            ail_d1_fn f = ail_dun1(x, AIL_D1_FLOAT); if (!f) f = ail_dun1(x, AIL_D1_INDEX);\n'
              '            if (f) { ail_obj r; ail_st st = f(cx, &r, x); if (st != AIL_OK) return st; if (r.tag == AIL_T_INT) r = ail_box_float(cx, (double)r.i); *out = r; return AIL_OK; }\n'
              '        }\n        /* fall through */\n'
              '        default: {\n            char buf[96]; snprintf(buf, sizeof buf, "float() argument must be'))
    e.append(("        default: { char buf[80]; snprintf(buf, sizeof buf, \"int() argument must be a string or a number, not '%s'\", ail_type_name(x.tag));",
              "        case AIL_T_INST: {\n"
              "            ail_d1_fn f = ail_dun1(x, AIL_D1_INT); if (!f) f = ail_dun1(x, AIL_D1_INDEX); if (!f) f = ail_dun1(x, AIL_D1_TRUNC);\n"
              "            if (f) return f(cx, out, x);\n"
              "        }\n"
              "        /* fall through */\n"
              "        default: { char buf[80]; snprintf(buf, sizeof buf, \"int() argument must be a string or a number, not '%s'\", ail_type_name(x.tag));"))
    e.append(("        default: { char buf[80]; snprintf(buf, sizeof buf, \"float() argument must be a string or a number, not '%s'\", ail_type_name(x.tag));",
              "        case AIL_T_INST: {\n"
              "            ail_d1_fn f = ail_dun1(x, AIL_D1_FLOAT); if (!f) f = ail_dun1(x, AIL_D1_INDEX);\n"
              "            if (f) { ail_obj r; ail_st st = f(cx, &r, x); if (st != AIL_OK) return st; if (r.tag == AIL_T_INT) r = ail_box_float(cx, (double)r.i); *out = r; return AIL_OK; }\n"
              "        }\n"
              "        /* fall through */\n"
              "        default: { char buf[80]; snprintf(buf, sizeof buf, \"float() argument must be a string or a number, not '%s'\", ail_type_name(x.tag));"))
    for old, new in CMP_WRAPPERS:
        e.append((old, new))
    # divmod(a, b): __divmod__ / __rdivmod__ decide first (CPython never uses __floordiv__ / __mod__ for it,
    # nor does it coerce a plain __index__ object); _AilIntEnum provides both methods, and the error names
    # the original operands.
    e.append((DIVMOD_OLD, DIVMOD_NEW))
    e.append((POW_OLD, POW_NEW))
    e.append(('static inline ail_st ail_bi_round(ail_ctx *cx, ail_obj *out, ail_obj x, int has_n, int64_t n) {\n',
              'static inline ail_st ail_bi_round(ail_ctx *cx, ail_obj *out, ail_obj x, int has_n, int64_t n) {\n'
              '    if (x.tag == AIL_T_INST) { ail_d2_fn f = ail_dun2(x, AIL_D2_ROUND); if (f) return f(cx, out, x, has_n ? ail_box_int(n) : ail_box_none()); }\n'))
    for fn, key in (('floor', 'FLOOR'), ('ceil', 'CEIL'), ('trunc', 'TRUNC')):
        e.append(('static inline ail_st ail_math_%s(ail_ctx *cx, ail_obj *out, ail_obj x) {\n' % fn,
                  'static inline ail_st ail_math_%s(ail_ctx *cx, ail_obj *out, ail_obj x) {\n'
                  '    if (x.tag == AIL_T_INST) { ail_d1_fn f = ail_dun1(x, AIL_D1_%s); if (f) return f(cx, out, x); }\n' % (fn, key)))
    # container protocol on an instance the emitter could not resolve
    e.append(('        default: { char buf[64]; snprintf(buf, sizeof buf, "object of type \'%s\' has no len()"',
              '        case AIL_T_INST: { ail_d1_fn f = ail_dun1(x, AIL_D1_LEN); if (f) return f(cx, out, x); }\n        /* fall through */\n'
              '        default: { char buf[64]; snprintf(buf, sizeof buf, "object of type \'%s\' has no len()"'))
    e.append(('        default: { char buf[64]; snprintf(buf, sizeof buf, "argument of type \'%s\' is not iterable"',
              '        case AIL_T_INST: return ail_dun_contains(cx, out, c, item);\n'
              '        default: { char buf[64]; snprintf(buf, sizeof buf, "argument of type \'%s\' is not iterable"'))
    e.append(('static inline ail_st ail_op_getitem(ail_ctx *cx, ail_obj *out, ail_obj c, ail_obj key) {\n',
              'static inline ail_st ail_op_getitem(ail_ctx *cx, ail_obj *out, ail_obj c, ail_obj key) {\n'
              '    if (key.tag == AIL_T_INST && (c.tag == AIL_T_LIST || c.tag == AIL_T_TUPLE || c.tag == AIL_T_STR)) {   /* __index__ */\n'
              '        ail_d1_fn xf = ail_dun1(key, AIL_D1_INDEX);\n'
              '        if (xf) { ail_obj ik; ail_st xst = xf(cx, &ik, key); if (xst != AIL_OK) return xst; key = ik; }\n'
              '    }\n'))
    e.append(('    char buf[64]; snprintf(buf, sizeof buf, "\'%s\' object does not support item assignment", ail_type_name(c.tag));',
              '    if (c.tag == AIL_T_INST) { ail_d3_fn f = ail_dun3(c, AIL_D3_SETITEM); if (f) { ail_obj r; return f(cx, &r, c, key, val); } }\n'
              '    char buf[64]; snprintf(buf, sizeof buf, "\'%s\' object does not support item assignment", ail_type_name(c.tag));'))
    e.append(('    char buf[64]; snprintf(buf, sizeof buf, "\'%s\' object doesn\'t support item deletion", ail_type_name(c.tag));',
              '    if (c.tag == AIL_T_INST) { ail_d2_fn f = ail_dun2(c, AIL_D2_DELITEM); if (f) { ail_obj r; return f(cx, &r, c, key); } }\n'
              '    char buf[64]; snprintf(buf, sizeof buf, "\'%s\' object doesn\'t support item deletion", ail_type_name(c.tag));'))
    e.append(('        default: { char buf[64]; snprintf(buf, sizeof buf, "\'%s\' object is not subscriptable"',
              '        case AIL_T_INST: { ail_d2_fn f = ail_dun2(c, AIL_D2_GETITEM); if (f) return f(cx, out, c, key); }\n        /* fall through */\n'
              '        default: { char buf[64]; snprintf(buf, sizeof buf, "\'%s\' object is not subscriptable"'))
    return e


def patch(text):
    """The generated C with the operator-method dispatch added to the general-path runtime."""
    for old, new in _edits():
        if old == new:
            continue
        count = text.count(old)
        if count == 0 and old in OPTIONAL:
            continue
        if count != 1:
            raise RuntimeError('dunderrt: %d places match %r' % (count, old[:70]))
        text = text.replace(old, new)
    # the helpers go in front of the first user: ail_obj_eq_raw's (needs ail_obj_truthy declared above it)
    anchor = 'static inline int ail_obj_eq_raw(ail_obj a, ail_obj b) {\n'
    if text.count(anchor) != 1:
        raise RuntimeError('dunderrt: no unique anchor for the helpers')
    text = text.replace(anchor, FUNCS + HASH_FUNC + anchor, 1)
    # the conditions of the program's own code (if / while / and / or / ?:) ask the class of an instance
    mark = '/* ---- interned attribute-name ids ---- */'
    k = text.find(mark)
    if k < 0:
        raise RuntimeError('dunderrt: no start of the program text')
    return text[:k] + text[k:].replace('ail_obj_truthy(', 'ail_truthy_u(')


def install(cls_global, cls_methods, all_params_of):
    """C statements for the program's setup code: the tables of one class."""
    lines = []
    for name, key in D1.items():
        info = cls_methods.get(name)
        if info and len(all_params_of(info)) == 1:
            lines.append('    ((ail_classobj *)%s.o)->d1[AIL_D1_%s] = %s;\n' % (cls_global, key, info['cname']))
    for name, key in D2.items():
        info = cls_methods.get(name)
        if info and len(all_params_of(info)) == 2:
            lines.append('    ((ail_classobj *)%s.o)->d2[AIL_D2_%s] = %s;\n' % (cls_global, key, info['cname']))
    for name, key in D3.items():
        info = cls_methods.get(name)
        if info and len(all_params_of(info)) == 3:
            lines.append('    ((ail_classobj *)%s.o)->d3[AIL_D3_%s] = %s;\n' % (cls_global, key, info['cname']))
    return lines
