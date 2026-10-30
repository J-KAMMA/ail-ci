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
import re

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
    ("""            fputs("<__main__.", f); ail_str_write(ail_view_to_str(c->name), f); fprintf(f, " object at %p>", (void *)ii);
""",
     """            fputs("<", f); fputs(c->module ? c->module : "__main__", f); fputc('.', f); ail_str_write(ail_view_to_str(c->name), f);
            fprintf(f, " object at %p>", (void *)ii);
"""),
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


_TN_CALL = re.compile(r'ail_type_name\((\w+)\.tag\)')
_TN_DEF = '\nstatic inline const char *ail_type_name(uint8_t t) {\n'
_TN_CAP = re.compile(r'\bchar (\w+)\[(\d+)\]')


def patch_error_names(text):
    """The run-time error texts that print a type name ("'<' not supported between instances of 'P' and 'P'",
    "'P' object is not iterable", "unsupported operand type(s) ...", int()/float()/ord() arguments, ...) name
    the user's class, as CPython does, in a program that has a class.  The base runtime names only the tag
    ("instance"); this pass asks the value itself (`ail__tname_c`), after the other runtime patches ran, so
    it also covers their fallback texts.  A program with no class keeps the runtime text it always had."""
    if text.find('static inline const char *ail__tname_c(ail_obj x) {') < 0 or text.find(_TN_DEF) < 0:
        return text
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if ('ail_type_name(' in line and 'ail_str_from_cstr' not in line and 'return ail_type_name(x.tag);' not in line
                and 'snprintf(buf, n, "%s", ail_type_name(x.tag));' not in line):
            lines[i] = _TN_CALL.sub(r'ail__tname_c(\1)', line)
        if 'ail__dun_tname_s(' in line and 'static const char *ail__dun_tname_s' not in line:
            lines[i] = lines[i].replace('ail__dun_tname_s(', 'ail__tname_c(')
    out = []
    for i, line in enumerate(lines):
        if 'ail__tname_c(' in line or (i + 1 < len(lines) and 'ail__tname_c(' in lines[i + 1] and 'char ' in line):
            # a class name has no fixed bound: the message buffers that hold one are big enough for a few
            line = _TN_CAP.sub(lambda m: m.group(0) if int(m.group(2)) >= 512 or m.group(1) in ('tnbuf', 'nb')
                               else 'char %s[512]' % m.group(1), line)   # tnbuf: CPython's own %.200s cap
        out.append(line)
    text = '\n'.join(out)
    for old, new in _TN_WORDING:
        text = text.replace(old, new)
    text = text.replace('char b2[200], tn[80]; ail__dun_tname(tn, sizeof tn, inst);',
                        'char b2[512], tn[400]; ail__dun_tname(tn, sizeof tn, inst);')
    # the first users (the dunder helpers) sit above the definition of ail__tname_c
    if '\n} ail_obj;\n' not in text:
        return text
    text = text.replace('\n} ail_obj;\n', '\n} ail_obj;\nstatic inline const char *ail__tname_c(ail_obj x);\n', 1)
    return text


# wording the generic runtime texts get wrong for any operand, and the format texts that name the operand's class
_FMT_INST = ('{ if (x.tag == AIL_T_INST) { char fb[512]; snprintf(fb, sizeof fb, "unsupported format string passed to %s.__format__", '
             'ail__tname_c(x)); return ail_raise_c(cx, AIL_B_TYPEERROR, fb); } '
             'return ail_raise_c(cx, AIL_B_TYPEERROR, "unsupported format string passed to ')
_TN_WORDING = (
    ("int() argument must be a string or a number, not '%s'",
     "int() argument must be a string, a bytes-like object or a real number, not '%s'"),
    ("float() argument must be a string or a number, not '%s'",
     "float() argument must be a string or a real number, not '%s'"),
    # pow: CPython names the operator `** or pow()`
    ("\"unsupported operand type(s) for %s: '%s' and '%s'\", op,",
     "\"unsupported operand type(s) for %s: '%s' and '%s'\", (op[0] == '*' && op[1] == '*' && !op[2]) ? \"** or pow()\" : op,"),
    ('return ail_raise_c(cx, AIL_B_TYPEERROR, "unsupported format string passed to non-int");',
     _FMT_INST + 'non-int"); }'),
    ('return ail_raise_c(cx, AIL_B_TYPEERROR, "unsupported format string passed to non-float");',
     _FMT_INST + 'non-float"); }'),
    ('if (specobj.tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "format() argument 2 must be str");',
     'if (specobj.tag != AIL_T_STR) { char fb[512]; snprintf(fb, sizeof fb, "format() argument 2 must be str, not %s", '
     'ail__tname_c(specobj)); return ail_raise_c(cx, AIL_B_TYPEERROR, fb); }'),
)
