"""CPython 3.12's argument-count TypeError text of the built-in methods, for `recv.m(*xs)` where the
count is known only at run time. Generated from CPython 3.12 (each message re-derived from the
interpreter): METHODS maps a method name to {family: (style, min, max)}; a method absent from it
is refused by name when called with a starred argument. Families and styles are the numbers below."""

FAMILIES = ['', 'list', 'deque', 'tuple', 'str', 'dict', 'set', 'Counter', 'defaultdict']      # index = the ail2_star_fam() result at run time (0: not one of these)
STYLES = {5: "TYPE.m expected at most N argument, got n", 1: 'exactly one argument', 2: 'no arguments', 3: "old-style takes at least/at most", 4: 'expected ... got'}

METHODS = {
    'rotate': {2: (5, 0, 1)},
    'append': {1: (1, 1, 1), 2: (1, 1, 1)},
    'appendleft': {2: (1, 1, 1)},
    'popleft': {2: (2, 0, 0)},
    'extend': {1: (1, 1, 1), 2: (1, 1, 1)},
    'insert': {1: (4, 2, 2), 2: (3, 2, 2)},
    'pop': {1: (4, 0, 1), 2: (2, 0, 0), 5: (4, 1, 2), 6: (2, 0, 0), 7: (4, 1, 2), 8: (4, 1, 2)},
    'remove': {1: (1, 1, 1), 2: (1, 1, 1), 6: (1, 1, 1)},
    'discard': {6: (1, 1, 1)},
    'add': {6: (1, 1, 1)},
    'index': {1: (4, 1, 3), 2: (3, 1, 3), 3: (4, 1, 3), 4: (3, 1, 3)},
    'count': {1: (1, 1, 1), 2: (1, 1, 1), 3: (1, 1, 1), 4: (3, 1, 3)},
    'reverse': {1: (2, 0, 0), 2: (2, 0, 0)},
    'clear': {1: (2, 0, 0), 2: (2, 0, 0), 5: (2, 0, 0), 6: (2, 0, 0), 7: (2, 0, 0), 8: (2, 0, 0)},
    'get': {5: (4, 1, 2), 7: (4, 1, 2), 8: (4, 1, 2)},
    'setdefault': {5: (4, 1, 2), 7: (4, 1, 2), 8: (4, 1, 2)},
    'keys': {5: (2, 0, 0), 7: (2, 0, 0), 8: (2, 0, 0)},
    'values': {5: (2, 0, 0), 7: (2, 0, 0), 8: (2, 0, 0)},
    'items': {5: (2, 0, 0), 7: (2, 0, 0), 8: (2, 0, 0)},
    'symmetric_difference': {6: (1, 1, 1)},
    'issubset': {6: (1, 1, 1)},
    'issuperset': {6: (1, 1, 1)},
    'isdisjoint': {6: (1, 1, 1)},
    'popitem': {5: (2, 0, 0), 7: (2, 0, 0), 8: (2, 0, 0)},
    'symmetric_difference_update': {6: (1, 1, 1)},
    'split': {4: (3, 0, 2)},
    'splitlines': {4: (3, 0, 1)},
    'join': {4: (1, 1, 1)},
    'strip': {4: (4, 0, 1)},
    'lstrip': {4: (4, 0, 1)},
    'rstrip': {4: (4, 0, 1)},
    'lower': {4: (2, 0, 0)},
    'upper': {4: (2, 0, 0)},
    'replace': {4: (4, 2, 3)},
    'startswith': {4: (3, 1, 3)},
    'endswith': {4: (3, 1, 3)},
    'find': {4: (3, 1, 3)},
    'rfind': {4: (3, 1, 3)},
    'isdigit': {4: (2, 0, 0)},
    'isalpha': {4: (2, 0, 0)},
    'istitle': {4: (2, 0, 0)},
    'isascii': {4: (2, 0, 0)},
    'isidentifier': {4: (2, 0, 0)},
    'partition': {4: (1, 1, 1)},
    'rpartition': {4: (1, 1, 1)},
    'rsplit': {4: (3, 0, 2)},
    'ljust': {4: (4, 1, 2)},
    'rjust': {4: (4, 1, 2)},
    'center': {4: (4, 1, 2)},
    'title': {4: (2, 0, 0)},
    'capitalize': {4: (2, 0, 0)},
    'swapcase': {4: (2, 0, 0)},
    'isupper': {4: (2, 0, 0)},
    'islower': {4: (2, 0, 0)},
    'isalnum': {4: (2, 0, 0)},
    'isspace': {4: (2, 0, 0)},
    'isnumeric': {4: (2, 0, 0)},
    'isdecimal': {4: (2, 0, 0)},
    'casefold': {4: (2, 0, 0)},
    'zfill': {4: (1, 1, 1)},
    'expandtabs': {4: (3, 0, 1)},
    'removeprefix': {4: (1, 1, 1)},
    'removesuffix': {4: (1, 1, 1)},
    'extendleft': {2: (1, 1, 1)},
    'rindex': {4: (3, 1, 3)},
}

C = r'''
static int ail2_star_fam(ail_obj x) {
    switch (x.tag) {
        case AIL_T_LIST: return ((ail_gcobj *)x.o)->flags ? 2 : 1;
        case AIL_T_TUPLE: return 3;
        case AIL_T_STR: return 4;
        case AIL_T_DICT: return ((ail_gcobj *)x.o)->flags == 1 ? 7 : (((ail_mapobj *)x.o)->dd_factory || ((ail_gcobj *)x.o)->flags == 2) ? 8 : 5;
        case AIL_T_SET: return 6;
        default: return 0;
    }
}
/* AttributeError of a method the receiver's type does not have */
__attribute__((noinline, cold)) static ail_st ail2_star_noattr(ail_ctx *cx, int fam, const char *m) {
    static const char *const tns[] = {"", "list", "collections.deque", "tuple", "str", "dict", "set", "Counter", "collections.defaultdict"};
    char buf[200];
    snprintf(buf, sizeof buf, "'%s' object has no attribute '%s'", tns[fam], m);
    return ail_raise_c(cx, AIL_B_ATTRIBUTEERROR, buf);
}
/* the argument-count TypeError of a built-in method (style: 1 exactly one, 2 no arguments, 3 old-style, 4 clinic, 5 `T.m expected at most`) */
__attribute__((noinline, cold)) static ail_st ail2_star_arity(ail_ctx *cx, int fam, const char *m, int style, int mn, int mx, int n) {
    static const char *const tns[] = {"", "list", "deque", "tuple", "str", "dict", "set", "Counter", "defaultdict"};
    char buf[200], num[40];
    const char *tn = tns[fam];
    int k = n < mn ? mn : mx;
    snprintf(num, sizeof num, "%d argument%s", k, k == 1 ? "" : "s");
    if (style == 1) snprintf(buf, sizeof buf, "%s.%s() takes exactly one argument (%d given)", tn, m, n);
    else if (style == 2) snprintf(buf, sizeof buf, "%s.%s() takes no arguments (%d given)", tn, m, n);
    else if (style == 3) snprintf(buf, sizeof buf, "%s() takes %s %s (%d given)", m, mn == mx ? "exactly" : n < mn ? "at least" : "at most", num, n);
    else if (style == 5) snprintf(buf, sizeof buf, "%s.%s expected at most %d argument%s, got %d", tn, m, mx, mx == 1 ? "" : "s", n);
    else snprintf(buf, sizeof buf, "%s expected %s%s, got %d", m, mn == mx ? "" : n < mn ? "at least " : "at most ", num, n);
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
'''
