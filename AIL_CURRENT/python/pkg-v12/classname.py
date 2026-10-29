"""F2: the printed name of a class in a program merged from several modules (ail_modules.py).

The merge renames a class of module `p.m` to `p__m__Config` so that two modules can both define `Config`;
CPython prints `Config` (repr, `__name__`, exception text) and `p.m.Config` where it prints the module
too (`<class 'p.m.Config'>`, the uncaught-exception line). The front end tells this compiler the mapping in
AIL_CLASS_NAMES, a JSON object `{merged name: [class name, module name]}`. The variable is absent for a
single-file program and for a merge without a non-entry class, and then every function here is the identity:
the generated C of such a program does not change.
"""
import json
import os

ENV = 'AIL_CLASS_NAMES'
_cache = [None, {}]


def _table():
    raw = os.environ.get(ENV)
    if raw != _cache[0]:
        try:
            table = {k: (v[0], v[1]) for k, v in json.loads(raw).items()} if raw else {}
        except (ValueError, TypeError, AttributeError, IndexError, KeyError):
            table = {}
        _cache[0], _cache[1] = raw, table
    return _cache[1]


def active():
    return bool(_table())


def display(ident):
    """The name CPython prints for the class whose identifier in the merged program is `ident`."""
    entry = _table().get(ident)
    return entry[0] if entry else ident


def module(ident):
    entry = _table().get(ident)
    return entry[1] if entry else '__main__'


def qualified(ident):
    """`mod.Name` for a class of a non-entry module; the bare name for an entry class (`__main__`)."""
    entry = _table().get(ident)
    return '%s.%s' % (entry[1], entry[0]) if entry else ident



# (old, new) pairs applied to a C runtime text when the program has a renamed class: a class object also
# keeps its module, and the places that print a class with its module use it. The old text is exact; a
# pair whose old text is absent from a given fragment is skipped (the same pairs serve several fragments).
_PATCHES = (
    (" } ail_classobj;",
     " const char *module; /* F2: the module of a class of an imported module, else 0 */ } ail_classobj;"),
    ("""            fputs(c->builtin_id >= 0 ? "<class '" : "<class '__main__.", f);
""",
     """            fputs(c->builtin_id >= 0 ? "<class '" : (c->module ? "<class '" : "<class '__main__."), f);
            if (c->module) { fputs(c->module, f); fputc('.', f); }
"""),
    ("""        ail_classobj *c = (ail_classobj *)cx->exc.cls.o;
        ail_str_write(ail_view_to_str(c->name), stderr);
        if (cx->exc.msg.sv.len) {""",
     """        ail_classobj *c = (ail_classobj *)cx->exc.cls.o;
        if (c->module) { fputs(c->module, stderr); fputc('.', stderr); }
        ail_str_write(ail_view_to_str(c->name), stderr);
        if (cx->exc.msg.sv.len) {"""),
    ("""        if (ii->cls.tag == AIL_T_CLASS) ail_str_write(ail_view_to_str(((ail_classobj *)ii->cls.o)->name), stderr);
""",
     """        if (ii->cls.tag == AIL_T_CLASS) {
            if (((ail_classobj *)ii->cls.o)->module) { fputs(((ail_classobj *)ii->cls.o)->module, stderr); fputc('.', stderr); }
            ail_str_write(ail_view_to_str(((ail_classobj *)ii->cls.o)->name), stderr);
        }
"""),
    ("""    if (strcmp(name_for_msg, "__name__") == 0) { *out = ((ail_classobj *)cls.o)->name; return AIL_OK; }
""",
     """    if (strcmp(name_for_msg, "__name__") == 0) { *out = ((ail_classobj *)cls.o)->name; return AIL_OK; }
    if (strcmp(name_for_msg, "__qualname__") == 0) { *out = ((ail_classobj *)cls.o)->name; return AIL_OK; }
    if (strcmp(name_for_msg, "__module__") == 0) {
        ail_classobj *mc = (ail_classobj *)cls.o;
        *out = ail_str_from_cstr(cx, mc->builtin_id >= 0 ? "builtins" : mc->module ? mc->module : "__main__");
        return AIL_OK;
    }
"""),
    ("""        fputs("Exception in thread:\n", stderr);
        ail_str_write(ail_view_to_str(c->name), stderr);""",
     """        fputs("Exception in thread:\n", stderr);
        if (c->module) { fputs(c->module, stderr); fputc('.', stderr); }
        ail_str_write(ail_view_to_str(c->name), stderr);"""),
)


# `type(a) is type(b)` compares the run-time class names; with renamed classes two classes can print one name,
# so the comparison reads this: "module.Name" for a class of an imported module, else what `__name__` reads
TYPE_IDENT_C = r'''
static inline ail_st ail_type_ident_of(ail_ctx *cx, ail_obj *out, ail_obj x) {
    if (x.tag == AIL_T_INST || x.tag == AIL_T_EXC) {
        ail_obj c = ((ail_instobj *)x.o)->cls;
        if (c.tag == AIL_T_CLASS && ((ail_classobj *)c.o)->module) {
            ail_classobj *cc = (ail_classobj *)c.o;
            char nb[1024], b[1100];
            ail_class_name_c(c, nb, sizeof nb);
            snprintf(b, sizeof b, "%s.%s", cc->module, nb);
            *out = ail_str_from_cstr(cx, b);
            return AIL_OK;
        }
    }
    return ail_type_name_of(cx, out, x);
}
'''


def patch_runtime(text):
    """`text` with the module-aware class printing of _PATCHES; unchanged when no class was renamed."""
    if not active():
        return text
    for old, new in _PATCHES:
        if old in text:
            text = text.replace(old, new)
    return text
