"""Exception values that read like CPython's on the typed path (S4e): str(e), repr(e), print(e), f"{e}",
e.args and type(e).__name__.

Two halves.

* `rewrite(tree, codes_of)` runs on the program's tree before anything is compiled.  Inside the body of
  `except X as e:` it turns the ways a program shows the bound exception into reads of virtual fields
  that pyfunc already knows how to type (a str, like `e.message`):

      str(e), print(e), f"{e}", "%s" % e, "{}".format(e)   ->  e.__ail_text__
      repr(e), f"{e!r}"                                    ->  e.__ail_repr__
      type(e).__name__, e.__class__.__name__               ->  e.__ail_type__
      print(type(e)), str(type(e))                         ->  "<class '" + e.__ail_qual__ + "'>"
      str(e.args), print(e.args), f"{e.args}"              ->  e.__ail_argsrepr__
      e.args[i], len(e.args), `if e.args`                  ->  _ail_exc_arg(e, i), _ail_exc_nargs(e), ...
      isinstance(e, ValueError), type(e) is ValueError     ->  _ail_exc_isa(e, codes...) != 0, _ail_exc_is(e, code) != 0

  `ACTIVE` says whether anything was rewritten; a program that does not read the text of an exception keeps
  the exception runtime it had (the codegen pins hash it).

* `CPART` (the EXCSTR part of cruntime) and the edits it makes to the DIE block: the exception keeps the
  arguments it was built with (`ail_exarg`), the text of a trap becomes CPython's, and a KeyError keeps its key.
"""
import ast

import userexc

ACTIVE = False

TEXT, REPR, TYPE, QUAL, ARGSREPR = '__ail_text__', '__ail_repr__', '__ail_type__', '__ail_qual__', '__ail_argsrepr__'
FILENAME = '__ail_filename__'
VIRTUAL_FIELDS = (TEXT, REPR, TYPE, QUAL, ARGSREPR, FILENAME)
OS_CLASS_NAMES = ('OSError', 'FileNotFoundError', 'PermissionError', 'IsADirectoryError', 'FileExistsError', 'NotADirectoryError')
INTRINSICS = ('_ail_exc_arg', '_ail_exc_nargs', '_ail_exc_isa', '_ail_exc_is')
ATTR_INTRINSICS = ('_ail_exc_attr_s', '_ail_exc_attr_i', '_ail_exc_attr_f')


class _Handler(ast.NodeTransformer):
    def __init__(self, name, codes_of, visible=None, os_family=False):
        self.name = name
        self.codes_of = codes_of
        self.visible = visible or {}       # attributes of the user exception classes this handler names
        self.os_family = os_family         # the handler names only OSError and its subclasses: e.filename is theirs
        self.hits = 0

    # -- what a node denotes
    def is_e(self, node):
        return isinstance(node, ast.Name) and node.id == self.name and isinstance(node.ctx, ast.Load)

    def is_args(self, node):
        return isinstance(node, ast.Attribute) and node.attr == 'args' and self.is_e(node.value)

    def is_type_of_e(self, node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'type' \
                and len(node.args) == 1 and not node.keywords and self.is_e(node.args[0]):
            return True
        return isinstance(node, ast.Attribute) and node.attr == '__class__' and self.is_e(node.value)

    def field(self, attr, like):
        self.hits += 1
        return ast.copy_location(ast.Attribute(value=ast.Name(self.name, ast.Load()), attr=attr, ctx=ast.Load()), like)

    def call(self, fname, args, like):
        self.hits += 1
        return ast.copy_location(ast.Call(func=ast.Name(fname, ast.Load()), args=args, keywords=[]), like)

    def text_of(self, node, want_repr=False):
        """The str that stands for an exception-shaped operand, or None when `node` is not one."""
        if self.is_e(node):
            return self.field(REPR if want_repr else TEXT, node)
        if self.is_args(node):
            return self.field(ARGSREPR, node)
        if self.is_type_of_e(node):
            qual = self.field(QUAL, node)
            parts = [ast.Constant("<class '"), ast.FormattedValue(value=qual, conversion=-1, format_spec=None),
                     ast.Constant("'>")]
            return ast.copy_location(ast.JoinedStr(values=parts), node)
        return None

    def truth(self, node):
        """`e.args` in a condition: `_ail_exc_nargs(e) != 0`."""
        if self.is_args(node):
            test = self.call('_ail_exc_nargs', [ast.Name(self.name, ast.Load())], node)
            return ast.copy_location(ast.Compare(left=test, ops=[ast.NotEq()], comparators=[ast.Constant(0)]), node)
        return None

    # -- statements and expressions that hold a condition
    def visit_If(self, node):
        self.generic_visit(node)
        node.test = self.truth(node.test) or node.test
        return node

    def visit_While(self, node):
        self.generic_visit(node)
        node.test = self.truth(node.test) or node.test
        return node

    def visit_IfExp(self, node):
        self.generic_visit(node)
        node.test = self.truth(node.test) or node.test
        return node

    def visit_Assert(self, node):
        self.generic_visit(node)
        node.test = self.truth(node.test) or node.test
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        node.values = [self.truth(v) or v for v in node.values]
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not):
            node.operand = self.truth(node.operand) or node.operand
        return node

    # -- attribute and subscript shapes
    def visit_Attribute(self, node):
        if node.attr in ('__name__', '__qualname__') and self.is_type_of_e(node.value):
            return self.field(TYPE, node)
        if (node.attr == 'filename' and self.os_family and 'filename' not in self.visible and self.is_e(node.value)
                and isinstance(node.ctx, ast.Load)):
            return self.field(FILENAME, node)
        if node.attr in self.visible and self.is_e(node.value) and isinstance(node.ctx, ast.Load):
            index, kind = self.visible[node.attr]
            probe = self.call('_ail_exc_attr_' + ('i' if kind == 'b' else kind),
                              [ast.Name(self.name, ast.Load()), ast.Constant(index)], node)
            if kind == 'b':
                return ast.copy_location(ast.Compare(left=probe, ops=[ast.NotEq()], comparators=[ast.Constant(0)]), node)
            return probe
        return self.generic_visit(node)

    def visit_Subscript(self, node):
        if self.is_args(node.value) and not isinstance(node.slice, ast.Slice):
            index = self.visit(node.slice)
            return self.call('_ail_exc_arg', [ast.Name(self.name, ast.Load()), index], node)
        return self.generic_visit(node)

    # -- text contexts
    def visit_FormattedValue(self, node):
        if node.conversion in (115, 114) or node.conversion == -1 and node.format_spec is None:
            text = self.text_of(node.value, want_repr=node.conversion == 114)
            if text is not None:
                spec = self.visit(node.format_spec) if node.format_spec is not None else None
                return ast.copy_location(ast.FormattedValue(value=text, conversion=-1, format_spec=spec), node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Name):
            if func.id == 'print':
                node.args = [self.text_of(a) or a for a in node.args]
                return self.generic_visit(node)
            if not node.keywords:
                if func.id in ('str', 'repr') and len(node.args) == 1:
                    text = self.text_of(node.args[0], want_repr=func.id == 'repr')
                    if text is not None:
                        return text
                    arg = node.args[0]
                    if (func.id == 'str' and isinstance(arg, ast.Subscript) and self.is_args(arg.value)
                            and not isinstance(arg.slice, ast.Slice)):
                        return self.visit(arg)           # e.args[i] already reads as its text
                if func.id == 'len' and len(node.args) == 1 and self.is_args(node.args[0]):
                    return self.call('_ail_exc_nargs', [ast.Name(self.name, ast.Load())], node)
                if func.id == 'isinstance' and len(node.args) == 2 and self.is_e(node.args[0]):
                    names = node.args[1].elts if isinstance(node.args[1], ast.Tuple) else [node.args[1]]
                    if all(isinstance(n, ast.Name) for n in names):
                        codes = []
                        for n in names:
                            got = self.codes_of(n.id)
                            if got is None:
                                return self.generic_visit(node)
                            codes.extend(got)
                        probe = self.call('_ail_exc_isa', [ast.Name(self.name, ast.Load())]
                                          + [ast.Constant(c) for c in sorted(set(codes))], node)
                        return ast.copy_location(ast.Compare(left=probe, ops=[ast.NotEq()], comparators=[ast.Constant(0)]), node)
        if (isinstance(func, ast.Attribute) and func.attr == 'format' and isinstance(func.value, ast.Constant)
                and isinstance(func.value.value, str) and '!' not in func.value.value and ':' not in func.value.value):
            node.args = [self.text_of(a) or a for a in node.args]
        return self.generic_visit(node)

    def visit_Compare(self, node):
        # type(e) is ValueError / type(e) == ValueError / type(e) != ValueError
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Is, ast.Eq, ast.IsNot, ast.NotEq)):
            left, right = node.left, node.comparators[0]
            if self.is_type_of_e(right) and isinstance(left, ast.Name):
                left, right = right, left
            if self.is_type_of_e(left) and isinstance(right, ast.Name) and self.codes_of(right.id) is not None:
                code = self.codes_of(right.id, exact=True)
                if code:
                    probe = self.call('_ail_exc_is', [ast.Name(self.name, ast.Load()), ast.Constant(code)], node)
                    equal = isinstance(node.ops[0], (ast.Is, ast.Eq))
                    return ast.copy_location(ast.Compare(left=probe, ops=[ast.NotEq() if equal else ast.Eq()],
                                                         comparators=[ast.Constant(0)]), node)
        return self.generic_visit(node)

    def visit_BinOp(self, node):
        # "...%s..." % e  /  "...%s...%r..." % (e, x, ...)
        if isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            specs = _percent_specs(node.left.value)
            right = node.right
            operands = right.elts if isinstance(right, ast.Tuple) else [right]
            if len(specs) == len(operands):
                new, as_s = [], []
                for index, (spec, operand) in enumerate(zip(specs, operands)):
                    got = self.text_of(operand, want_repr=spec == 'r') if spec in ('s', 'r') else None
                    new.append(got or operand)
                    if got is not None:
                        as_s.append(index)
                if as_s:
                    node.left = ast.Constant(_percent_to_s(node.left.value, as_s))
                    node.right = (ast.copy_location(ast.Tuple(elts=new, ctx=ast.Load()), right)
                                  if isinstance(right, ast.Tuple) else new[0])
        return self.generic_visit(node)


def _percent_specs(text):
    """The conversion letters of a %-format text, in order ('%%' is not a conversion)."""
    out, i = [], 0
    while i < len(text):
        if text[i] != '%':
            i += 1
            continue
        i += 1
        if i < len(text) and text[i] == '%':
            i += 1
            continue
        while i < len(text) and text[i] in '-+ #0123456789.':
            i += 1
        if i < len(text):
            out.append(text[i])
            i += 1
    return out


def _percent_to_s(text, indexes):
    """`text` with the conversion letter of the listed conversions (0-based, in order) set to s."""
    out, i, n = [], 0, 0
    while i < len(text):
        if text[i] != '%':
            out.append(text[i])
            i += 1
            continue
        out.append('%')
        i += 1
        if i < len(text) and text[i] == '%':
            out.append('%')
            i += 1
            continue
        while i < len(text) and text[i] in '-+ #0123456789.':
            out.append(text[i])
            i += 1
        if i < len(text):
            out.append('s' if n in indexes else text[i])
            n += 1
            i += 1
    return ''.join(out)


class _Repr(ast.NodeTransformer):
    """`repr(x)` is `f"{x!r}"`: the f-string conversion is built for every kind."""

    def visit_Call(self, node):
        self.generic_visit(node)
        if (isinstance(node.func, ast.Name) and node.func.id == 'repr' and len(node.args) == 1 and not node.keywords
                and not isinstance(node.args[0], ast.Starred)):
            field = ast.FormattedValue(value=node.args[0], conversion=114, format_spec=None)
            return ast.copy_location(ast.JoinedStr(values=[field]), node)
        return node


def rewrite(tree, codes_of):
    """Rewrite the handlers of `tree` in place; sets ACTIVE."""
    global ACTIVE
    ACTIVE = False
    if not any(isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == 'repr' for n in ast.walk(tree)):
        _Repr().visit(tree)
        ast.fix_missing_locations(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.name:
            names = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
            os_family = all(isinstance(n, ast.Name) and n.id in OS_CLASS_NAMES for n in names)
            pass_ = _Handler(node.name, codes_of, userexc.visible_attrs(node.type), os_family)
            node.body = [pass_.visit(stmt) for stmt in node.body]
            if pass_.hits:
                ACTIVE = True
    if ACTIVE:
        ast.fix_missing_locations(tree)


# ---------------------------------------------------------------------------------------------------------
# The C side.  `DIE_EDITS` are applied to the DIE block (after the OSEXC struct edit, which they build on);
# `OSEXC_EDITS` to the OSEXC part; `CPART` is the EXCSTR part.

DIE_EDITS = (
    # the exception keeps the arguments it was built with, the length of its strerror, and the key of a KeyError
    ('    _Bool has_err;\n} ail_exception;\n',
     '    _Bool has_err;\n'
     '    int64_t se_len;\n'
     '    struct ail_exarg *xargs;\n'
     '    int32_t nargs;\n'
     '    _Bool has_args;\n'
     '    _Bool os_text;\n'
     '    struct ail_exarg *xattrs;\n'
     '    int32_t nattrs;\n'
     '    struct ail_exarg *xtext;\n'
     '    struct ail_exarg *xfn;\n'
     '} ail_exception;\n'
     '/* one argument of an exception: str(e), repr(e) and e.args read them (kind 0 str, 1 int, 2 float, 3 bool, 4 None) */\n'
     'typedef struct ail_exarg { int kind; int64_t i; double f; const uint8_t *p; int64_t n; _Bool bytes; } ail_exarg;\n'
     'static void ail_exc_free_extra(ail_exception *v) {\n'
     '    if (v->xargs) {\n'
     '        for (int32_t k = 0; k < v->nargs; k++) free((void *)v->xargs[k].p);\n'
     '        free(v->xargs);\n'
     '    }\n'
     '    if (v->xattrs) {\n'
     '        for (int32_t k = 0; k < v->nattrs; k++) free((void *)v->xattrs[k].p);\n'
     '        free(v->xattrs);\n'
     '    }\n'
     '    if (v->xtext) { free((void *)v->xtext->p); free(v->xtext); }\n'
     '    if (v->xfn) { free((void *)v->xfn->p); free(v->xfn); }\n'
     '}\n'
     'AIL_LINK_STATE(ail_exception *, ail_pending_exc, = NULL);   /* the exception a trap is about to throw (a KeyError with its key) */\n'
     'static void ail_key_error_i(int64_t k);\n'
     'static void ail_key_error_s(const uint8_t *p, int64_t n);\n'
     'static void ail_key_error_b(const uint8_t *p, int64_t n);\n'),
    ('{ free((void *)value->p); free(value); }',
     '{ free((void *)value->p); ail_exc_free_extra(value); free(value); }'),
    # a trap becomes the exception CPython raises there, text included
    ('    if (!strcmp(w, "file is not valid UTF-8"))\n        return AIL_EXC_UNICODE_DECODE;\n    return 0;\n}\n',
     '    if (!strcmp(w, "file is not valid UTF-8"))\n        return AIL_EXC_UNICODE_DECODE;\n    return 0;\n}\n'
     '/* CPython 3.12\'s text for the traps that become catchable exceptions. */\n'
     'static const char *ail_die_text(int k, const char *w) {\n'
     '    if (!strcmp(w, "min() of an empty sequence")) return "min() iterable argument is empty";\n'
     '    if (!strcmp(w, "max() of an empty sequence")) return "max() iterable argument is empty";\n'
     '    if (!strcmp(w, "integer division by zero")) return "integer division or modulo by zero";\n'
     '    if (!strcmp(w, "grid row index out of range") || !strcmp(w, "grid column index out of range")) return "list index out of range";\n'
     '    if (!strcmp(w, "bytes index out of range")) return "index out of range";\n'
     '    if (k == AIL_EXC_KEY || k == AIL_EXC_UNICODE_DECODE) return NULL;\n'
     '    return w;\n'
     '}\n'
     'static ail_exception *ail_die_value(int k, const char *w) {\n'
     '    if ((k == AIL_EXC_KEY || k == AIL_EXC_UNICODE_DECODE) && ail_pending_exc) {\n'
     '        ail_exception *v = ail_pending_exc;\n'
     '        ail_pending_exc = NULL;\n'
     '        return v;\n'
     '    }\n'
     '    const char *t = ail_die_text(k, w);\n'
     '    return ail_exception_new(k, (const uint8_t *)t, t ? (int64_t)strlen(t) : 0, 1);\n'
     '}\n'),
    ('        if (k) { ail_exception_store(&ail_exc_value, NULL, 1); ail_exc_code = k; ail_exc_unwind(); ail_exc_throw(); }',
     '        if (k) { ail_exception_store(&ail_exc_value, ail_die_value(k, w), 1); ail_exc_code = k; ail_exc_unwind(); ail_exc_throw(); }'),
    ('    if (!strcmp(w, "list index out of range") || !strcmp(w, "pop index out of range")\n',
     '    if (!strcmp(w, "list index out of range") || !strcmp(w, "list assignment index out of range")\n        || !strcmp(w, "pop index out of range")\n'),
    ('    if (!strcmp(w, "division by zero") || !strcmp(w, "integer division by zero")\n        || !strcmp(w, "integer modulo by zero")) return AIL_EXC_ZERODIV;',
     '    if (!strcmp(w, "division by zero") || !strcmp(w, "integer division by zero")\n        || !strcmp(w, "integer modulo by zero") || !strcmp(w, "float division by zero")\n'
     '        || !strcmp(w, "float floor division by zero") || !strcmp(w, "float modulo")) return AIL_EXC_ZERODIV;'),
    # a runtime-raised exception that names only its class gets the text CPython gives that class's usual cause
    ('    ail_exception_store(&ail_exc_value, ail_exception_new(code, NULL, 0, 1), 1);\n    ail_exc_code = code;\n',
     '    ail_exception_store(&ail_exc_value, ail_named_value(code), 1);\n    ail_exc_code = code;\n'),
    ('static void ail_raise_named(int code) {\n',
     'static ail_exception *ail_named_value(int code) {\n'
     '    const char *t = code == AIL_EXC_ZERODIV ? "division by zero" : code == AIL_EXC_INDEX ? "list index out of range"\n'
     '                  : code == AIL_EXC_EOF ? "EOF when reading a line" : NULL;\n'
     '    return ail_exception_new(code, (const uint8_t *)t, t ? (int64_t)strlen(t) : 0, 1);\n'
     '}\n'
     '/* raise a built-in exception with a fixed message (CPython\'s wording of a trap) */\n'
     'static void ail_raise_msg(int code, const char *t) {\n'
     '    ail_raise_value_adopt(ail_exception_new(code, (const uint8_t *)t, (int64_t)strlen(t), 1));\n'
     '}\n'
     'static void ail_raise_unpack(int64_t got, int64_t want) {\n'
     '    char buf[96];\n'
     '    if (got < want) snprintf(buf, sizeof buf, "not enough values to unpack (expected %lld, got %lld)", (long long)want, (long long)got);\n'
     '    else snprintf(buf, sizeof buf, "too many values to unpack (expected %lld)", (long long)want);\n'
     '    ail_raise_msg(AIL_EXC_VALUE, buf);\n'
     '}\n'
     'static const char *ail_exception_qualname(int code) { return ail_exception_name(code); }\n'
     'static void ail_raise_named(int code) {\n'),
)

OSEXC_EDITS = (
    ('    value->se_off = h;\n    value->has_err = 1;\n',
     '    value->se_off = h;\n    value->se_len = text.n;\n    value->has_err = 1;\n'),
    ('return (ail_str){value->p + value->se_off, value->n - value->se_off, value->bytes};',
     'return (ail_str){value->p + value->se_off, value->se_len, value->bytes};'),
)


CLASS_NAMES = ['', 'ValueError', 'ZeroDivisionError', 'IndexError', 'KeyError', 'EOFError', 'OSError', 'RuntimeError',
               'UnicodeDecodeError', 'AssertionError', 'OverflowError', 'FileNotFoundError', 'PermissionError',
               'IsADirectoryError', 'FileExistsError', 'NotADirectoryError', 'UnsupportedOperation', 'CalledProcessError',
               'TimeoutExpired', 'sqlite3.Error', 'sqlite3.DatabaseError', 'sqlite3.OperationalError',
               'sqlite3.IntegrityError', 'sqlite3.ProgrammingError', 'sqlite3.InterfaceError', 'sqlite3.DataError',
               'sqlite3.InternalError', 'sqlite3.NotSupportedError', 'Exception']


def classes_table(text):
    """The DIE block (with whatever code splices it has) taking the codes of `Exception` and of the user classes."""
    import re
    reserved = ['', 'URLError', 'HTTPError'] if userexc.reserved() else []           # codes 29 (spare), 30, 31: urllib (G12)
    names = CLASS_NAMES + reserved + list(userexc.NAMES)
    last = len(names) - 1
    quoted = ', '.join('"%s"' % n for n in names)
    shown = len(CLASS_NAMES) + len(reserved)
    qualified = ', '.join('"%s"' % (('urllib.error.' + n if n else n) if len(CLASS_NAMES) <= i < shown else n if i < shown else '__main__.' + n)
                          for i, n in enumerate(names))
    function, count = re.subn(r'static const char \*ail_exception_name\(int code\) \{.*?\n\}\n',
                              lambda m: ('static const char *ail_exception_name(int code) {\n    static const char *names[] =\n        {%s};\n'
                                         '    return code >= 1 && code <= %d ? names[code] : "RuntimeError";\n}\n' % (quoted, last)),
                              text, count=1, flags=re.S)
    if count != 1:
        raise AssertionError('DIE block changed; update exctext.classes_table')
    text = function
    text, count = re.subn(r'code > \d+ \|\| n < 0', 'code > %d || n < 0' % last, text)
    if count != 1:
        raise AssertionError('DIE block changed; update exctext.classes_table (ail_exception_new)')
    text, count = re.subn(r'if \(code < 1 \|\| code > \d+\) code = AIL_EXC_RUNTIME;', 'if (code < 1 || code > %d) code = AIL_EXC_RUNTIME;' % last, text)
    if count != 1:
        raise AssertionError('DIE block changed; update exctext.classes_table (ail_raise_named)')
    old = 'static const char *ail_exception_qualname(int code) { return ail_exception_name(code); }\n'
    if old in text:
        text = text.replace(old, 'static const char *ail_exception_qualname(int code) {\n    static const char *names[] =\n        {%s};\n'
                                 '    return code >= 1 && code <= %d ? names[code] : "RuntimeError";\n}\n' % (qualified, last))
    return text


def apply(text, edits, what):
    for old, new in edits:
        if text.count(old) != 1:
            raise AssertionError('%s changed; update exctext: %r' % (what, old))
        text = text.replace(old, new)
    return text


# Edits to other runtime parts, made only for a program that reads the text of an exception: the traps that
# CPython words with the offending value say it.
PART_EDITS = {
    'STR': (
        # a text that is not UTF-8 raises UnicodeDecodeError('utf-8', data, start, end, reason) with CPython's range and wording
        ('static ail_str ail_utf8_decode_error(ail_sarena *A, const unsigned char *b, int64_t nb,\n',
         'static void ail_exc_utf8_fail(const unsigned char *b, int64_t nb, const char *bad, int code);\n'
         'static ail_str ail_utf8_decode_error(ail_sarena *A, const unsigned char *b, int64_t nb,\n'),
        ('        if (error_code && ail_exc_top >= 0) ail_raise_named(error_code);\n        ail_die(bad);\n',
         '        ail_exc_utf8_fail(b, nb, bad, error_code);\n        if (error_code && ail_exc_top >= 0) ail_raise_named(error_code);\n        ail_die(bad);\n'),
        ('static int64_t ail__str_to_int_full(ail_str s);\n',
         'static void ail_exc_int_fail(ail_str s) __attribute__((noreturn));\n'
         'static void ail_exc_float_fail(ail_str s) __attribute__((noreturn));\n'
         'static int64_t ail__str_to_int_full(ail_str s);\n'),
        # an OSError raised for a path says which (legacy whole-file reads and writes)
        ('static void ail_file_fail(int err) {\n', 'static void ail_exc_os_fail(int err, ail_str path);\nstatic void ail_file_fail(int err) {\n'),
        ('    if (!f) ail_file_fail(open_errno);\n    return f;', '    if (!f) ail_exc_os_fail(open_errno, path);\n    return f;'),
        ('free(buf); ail_file_fail(read_errno); }', 'free(buf); ail_exc_os_fail(read_errno, path); }'),
        ('    if (rc == 1) ail_raise_named(AIL_EXC_VALUE);\n    if (rc == 2) ail_die("integer overflow");\n    return v;\n}\n/* `float(<str>)`',
         '    if (rc == 1) ail_exc_int_fail(s);\n    if (rc == 2) ail_die("integer overflow");\n    return v;\n}\n/* `float(<str>)`'),
        ('    int rc = ail__asc_to_float(b, len, &v);\n    if (b != stackbuf) free(b);\n    if (rc) ail_raise_named(AIL_EXC_VALUE);\n    return v;\n}\n/* AIL_TASK_strops_20260915.md Part A',
         '    int rc = ail__asc_to_float(b, len, &v);\n    if (b != stackbuf) free(b);\n    if (rc) ail_exc_float_fail(s);\n    return v;\n}\n/* AIL_TASK_strops_20260915.md Part A'),
    ),
    'FILEIO': (
        # an OSError of the file layer carries its errno and the length of its strerror (e.args is (errno, strerror))
        ('    ail_raise_value_adopt(ail_exception_new(code, (const uint8_t *)ailf_e.msg, (int64_t)strlen(ailf_e.msg),\n'
         '                                            (_Bool)ailt_ascii(ailf_e.msg)));\n}\n',
         '    ail_exception *value = ail_exception_new(code, (const uint8_t *)ailf_e.msg, (int64_t)strlen(ailf_e.msg),\n'
         '                                             (_Bool)ailt_ascii(ailf_e.msg));\n'
         '    if (ailf_e.kind == AILF_E_OS && ailf_e.err) {\n'
         '        const char *why = strerror(ailf_e.err);\n'
         '        char head[48];\n'
         '        value->err = ailf_e.err; value->has_err = 1;\n'
         '        value->se_off = snprintf(head, sizeof head, "[Errno %d] ", ailf_e.err);\n'
         '        value->se_len = (int64_t)strlen(why ? why : "Unknown error");\n'
         '        if (ailf_e.has_fn1) ail_exception_set_filename(value, (ail_str){(const uint8_t *)ailf_e.fn1, (int64_t)strlen(ailf_e.fn1), (_Bool)ailt_ascii(ailf_e.fn1)});\n'
         '    }\n'
         '    ail_raise_value_adopt(value);\n}\n'),
    ),
    'UTF8CODEC': (
        ('        if (ail_exc_top >= 0) ail_raise_named(AIL_EXC_UNICODE_DECODE);\n        ail_die("bytes are not valid UTF-8");\n        return (ail_str){0, 0, 0};',
         '        ail_exc_utf8_fail(b.p, b.n, "bytes are not valid UTF-8", AIL_EXC_UNICODE_DECODE);\n'
         '        if (ail_exc_top >= 0) ail_raise_named(AIL_EXC_UNICODE_DECODE);\n        ail_die("bytes are not valid UTF-8");\n        return (ail_str){0, 0, 0};'),
    ),
    'UTF8LINES': (
        ('            if (ail_exc_top >= 0) ail_raise_named(AIL_EXC_UNICODE_DECODE);\n            ail_die("bytes are not valid UTF-8");\n            return;',
         '            ail_exc_utf8_fail(b.p, b.n, "bytes are not valid UTF-8", AIL_EXC_UNICODE_DECODE);\n'
         '            if (ail_exc_top >= 0) ail_raise_named(AIL_EXC_UNICODE_DECODE);\n            ail_die("bytes are not valid UTF-8");\n            return;'),
        ('invalid_utf8_points:\n    if (ail_exc_top >= 0) ail_raise_named(AIL_EXC_UNICODE_DECODE);',
         'invalid_utf8_points:\n    ail_exc_utf8_fail(b.p, b.n, "bytes are not valid UTF-8", AIL_EXC_UNICODE_DECODE);\n    if (ail_exc_top >= 0) ail_raise_named(AIL_EXC_UNICODE_DECODE);'),
        ('            if (ail_exc_top >= 0) ail_raise_named(AIL_EXC_UNICODE_DECODE);\n            ail_die("bytes are not valid UTF-8");\n            return 0;',
         '            ail_exc_utf8_fail(b.p, b.n, "bytes are not valid UTF-8", AIL_EXC_UNICODE_DECODE);\n'
         '            if (ail_exc_top >= 0) ail_raise_named(AIL_EXC_UNICODE_DECODE);\n            ail_die("bytes are not valid UTF-8");\n            return 0;'),
    ),
    'LIST': (
        ('static void ail_list_set(ail_list *L, int64_t i, int64_t v) {\n'
         '    if (__builtin_expect((uint64_t)i >= (uint64_t)L->n, 0)) {      /* the in-range case is one compare */\n'
         '        if (i < 0) i += L->n;\n'
         '        if (i < 0 || i >= L->n) ail_die("list index out of range");',
         'static void ail_list_set(ail_list *L, int64_t i, int64_t v) {\n'
         '    if (__builtin_expect((uint64_t)i >= (uint64_t)L->n, 0)) {      /* the in-range case is one compare */\n'
         '        if (i < 0) i += L->n;\n'
         '        if (i < 0 || i >= L->n) ail_die("list assignment index out of range");'),
    ),
    'FLIST': (
        ('static void ail_flist_set(ail_flist *L, int64_t i, double v) {\n'
         '    if (__builtin_expect((uint64_t)i >= (uint64_t)L->n, 0)) {      /* the in-range case is one compare */\n'
         '        if (i < 0) i += L->n;\n'
         '        if (i < 0 || i >= L->n) ail_die("list index out of range");',
         'static void ail_flist_set(ail_flist *L, int64_t i, double v) {\n'
         '    if (__builtin_expect((uint64_t)i >= (uint64_t)L->n, 0)) {      /* the in-range case is one compare */\n'
         '        if (i < 0) i += L->n;\n'
         '        if (i < 0 || i >= L->n) ail_die("list assignment index out of range");'),
    ),
    'FILESIZE': (
        ('    if (!ok) ail_file_fail(stat_errno);\n', '    if (!ok) ail_exc_os_fail(stat_errno, path);\n'),
    ),
    'BINARYFILE': (
        ('    if (!F->fp) { free(F); ail_file_fail(open_errno); }\n', '    if (!F->fp) { free(F); ail_exc_os_fail(open_errno, path); }\n'),
    ),
}
PART_EDITS['STRWIN'] = (
    ('    int64_t r = ail_str_find_in(s, sub, has_lo, lo, has_hi, hi);\n    if (r < 0) ail_raise_named(AIL_EXC_VALUE);',
     '    int64_t r = ail_str_find_in(s, sub, has_lo, lo, has_hi, hi);\n    if (r < 0) ail_raise_msg(AIL_EXC_VALUE, "substring not found");'),
    ('    int64_t r = ail_str_rfind_in(s, sub, has_lo, lo, has_hi, hi);\n    if (r < 0) ail_raise_named(AIL_EXC_VALUE);',
     '    int64_t r = ail_str_rfind_in(s, sub, has_lo, lo, has_hi, hi);\n    if (r < 0) ail_raise_msg(AIL_EXC_VALUE, "substring not found");'),
)


def _key_error_calls(text):
    """Every `ail_die("key error")` in a function that has the key as a parameter says which key."""
    import re
    headers = list(re.finditer(r'^static[^\n;]*?\(([^)]*)\)\s*\{', text, re.M))
    out, pos = [], 0
    for m in re.finditer(r'ail_die\("key error"\)', text):
        header = None
        for h in headers:
            if h.start() < m.start():
                header = h
            else:
                break
        call = None
        if header is not None:
            for param in header.group(1).split(','):
                param = param.strip()
                name = param.rsplit(' ', 1)[-1].lstrip('*')
                if name not in ('k', 'key'):
                    continue
                if param.startswith('int64_t '):
                    call = 'ail_key_error_i(%s)' % name
                elif param.startswith('ail_str '):
                    call = 'ail_key_error_s(%s.p, %s.n)' % (name, name)
                elif param.startswith('ail_bytes '):
                    call = 'ail_key_error_b(%s.p, %s.n)' % (name, name)
        out.append(text[pos:m.start()])
        out.append(call or m.group(0))
        pos = m.end()
    out.append(text[pos:])
    return ''.join(out)


# wording of the ValueErrors a few runtime parts raise (every occurrence)
PART_REPLACE_ALL = {
    'RANGEITER': (('    if (!step) ail_raise_named(AIL_EXC_VALUE);', '    if (!step) ail_raise_msg(AIL_EXC_VALUE, "range() arg 3 must not be zero");'),),
    'CHRSTR': (('        ail_raise_named(AIL_EXC_VALUE);\n    uint8_t *q = ail_sarena_alloc(A, 5);',
                '        ail_raise_msg(AIL_EXC_VALUE, "chr() arg not in range(0x110000)");\n    uint8_t *q = ail_sarena_alloc(A, 5);'),),
    'SLIST': (('if (sep.n == 0) ail_raise_named(AIL_EXC_VALUE);', 'if (sep.n == 0) ail_raise_msg(AIL_EXC_VALUE, "empty separator");'),),
    'SPLITN': (('if (sep.n == 0) ail_raise_named(AIL_EXC_VALUE);', 'if (sep.n == 0) ail_raise_msg(AIL_EXC_VALUE, "empty separator");'),),
}


def part_edit(part, text):
    """The runtime part `part` as a program that reads exception text needs it."""
    if part in PART_EDITS and PART_EDITS[part]:
        text = apply(text, PART_EDITS[part], 'the %s part' % part)
    for old, new in PART_REPLACE_ALL.get(part, ()):
        if old not in text:
            raise AssertionError('the %s part changed; update exctext: %r' % (part, old))
        text = text.replace(old, new)
    if 'ail_die("key error")' in text and part != 'EXCSTR':
        text = _key_error_calls(text)
    return text


CFLOAT ='#define AIL_EXC_FLOAT 1   /* a float among the arguments of an exception: its text needs the float printer */\n'

CPART = r'''
/* ---- EXCSTR: exception values that read like CPython's ---------------------------------------------------
   An exception holds the arguments it was built with (ail_exarg); str(e), repr(e) and e.args read them:
     str(e):   no argument "", one argument str(arg) (a KeyError: repr(arg)), more: the repr of the tuple
     repr(e):  Name(repr(arg), ...)            e.args: (arg, ...)
   An exception built without arguments (a trap, a runtime message) has the message as its only argument,
   or none when the message is empty; an OSError with an errno has (errno, strerror). */
static ail_exarg ail_exarg_s(ail_str s) {
    ail_exarg a; memset(&a, 0, sizeof a);
    a.kind = 0; a.p = s.p; a.n = s.n; a.bytes = s.bytes; return a;
}
static ail_exarg ail_exarg_i(int64_t v) { ail_exarg a; memset(&a, 0, sizeof a); a.kind = 1; a.i = v; return a; }
static ail_exarg ail_exarg_f(double v) { ail_exarg a; memset(&a, 0, sizeof a); a.kind = 2; a.f = v; return a; }
static ail_exarg ail_exarg_b(int64_t v) { ail_exarg a; memset(&a, 0, sizeof a); a.kind = 3; a.i = v != 0; return a; }
static ail_exarg ail_exarg_none(void) { ail_exarg a; memset(&a, 0, sizeof a); a.kind = 4; return a; }
static const char *ail_exc_class_name(int code) {
    const char *n = ail_exception_name(code);
    const char *d = strrchr(n, '.');
    return d ? d + 1 : n;
}
static ail_str ail__exc_lit(const char *s) { return (ail_str){(const uint8_t *)s, (int64_t)strlen(s), 1}; }
static int64_t ail_exc_nargs(const ail_exception *e) {
    if (e->has_args) return e->nargs;
    if (e->has_err) return 2;
    return e->n > 0 ? 1 : 0;
}
static ail_exarg ail_exc_arg(const ail_exception *e, int64_t i) {
    if (e->has_args) return e->xargs[i];
    ail_exarg a; memset(&a, 0, sizeof a);
    if (e->has_err) {
        if (i == 0) { a.kind = 1; a.i = e->err; }
        else { a.p = e->p + e->se_off; a.n = e->se_len; a.bytes = e->bytes; }
        return a;
    }
    a.p = e->p; a.n = e->n; a.bytes = e->bytes;
    return a;
}
/* repr(bytes): b'...', a quote that is not in the text, \\ \t \n \r and \xNN for the rest that is not printable ASCII */
static ail_str ail__bytes_repr(ail_sarena *A, const uint8_t *p, int64_t n) {
    static const char hex[] = "0123456789abcdef";
    int has_sq = 0, has_dq = 0;
    for (int64_t i = 0; i < n; i++) { if (p[i] == '\'') has_sq = 1; else if (p[i] == '"') has_dq = 1; }
    int quote = (has_sq && !has_dq) ? '"' : '\'';
    uint8_t *q = ail_sarena_alloc(A, 3 + 4 * n);
    int64_t o = 0;
    q[o++] = 'b'; q[o++] = (uint8_t)quote;
    for (int64_t i = 0; i < n; i++) {
        uint8_t c = p[i];
        if (c == (uint8_t)quote || c == '\\') { q[o++] = '\\'; q[o++] = c; }
        else if (c == '\t') { q[o++] = '\\'; q[o++] = 't'; }
        else if (c == '\n') { q[o++] = '\\'; q[o++] = 'n'; }
        else if (c == '\r') { q[o++] = '\\'; q[o++] = 'r'; }
        else if (c < 32 || c >= 127) { q[o++] = '\\'; q[o++] = 'x'; q[o++] = (uint8_t)hex[c >> 4]; q[o++] = (uint8_t)hex[c & 15]; }
        else q[o++] = c;
    }
    q[o++] = (uint8_t)quote;
    return (ail_str){q, o, 1};
}
/* str(arg) (repr == 0) or repr(arg) (repr == 1) of one argument; a str argument comes back as a view of the
   exception's own storage */
static ail_str ail__exc_piece(const ail_exarg *a, int repr, ail_sarena *A) {
    switch (a->kind) {
    case 0: { ail_str s = {a->p, a->n, a->bytes}; return repr ? ail_fmt_repr_str(A, s) : s; }
    case 1: return ail_str_from_int(A, a->i);
    case 2:
#ifdef AIL_EXC_FLOAT
    { char buf[64]; ail_fmt_float(buf, sizeof buf, a->f);
      int m = (int)strlen(buf); uint8_t *q = ail_sarena_alloc(A, m); memcpy(q, buf, (size_t)m);
      return (ail_str){q, m, 1}; }
#else
        return ail__exc_lit("nan");
#endif
    case 3: return ail__exc_lit(a->i ? "True" : "False");
    case 5: return ail__bytes_repr(A, a->p, a->n);
    default: return ail__exc_lit("None");
    }
}
static ail_str ail__exc_join(const ail_exception *e, const char *open, const char *close, int trailing, ail_sarena *A) {
    int64_t n = ail_exc_nargs(e);
    ail_str parts[40]; int64_t k = 0;
    if (n > 16) n = 16;
    parts[k++] = ail__exc_lit(open);
    for (int64_t i = 0; i < n; i++) {
        if (i) parts[k++] = ail__exc_lit(", ");
        ail_exarg a = ail_exc_arg(e, i);
        parts[k++] = ail__exc_piece(&a, 1, A);
    }
    if (trailing && n == 1) parts[k++] = ail__exc_lit(",");
    parts[k++] = ail__exc_lit(close);
    return ail_str_catn(A, parts, k);
}
/* e.args as text: "('x',)", "()", "(1, 'a')" */
static ail_str ail_exc_argsrepr(const ail_exception *e, ail_sarena *A) { return ail__exc_join(e, "(", ")", 1, A); }
/* repr(e): ValueError('x'), ValueError(), OSError(2, 'No such file or directory') */
static ail_str ail_exc_repr(const ail_exception *e, ail_sarena *A) {
    ail_str parts[2];
    parts[0] = ail__exc_lit(ail_exc_class_name(e->code));
    parts[1] = ail__exc_join(e, "(", ")", 0, A);
    return ail_str_catn(A, parts, 2);
}
/* str(e), copied into the arena (the exception may be released before the text is) */
static ail_str ail__exc_unicode_text(const ail_exception *e, ail_sarena *A);
static ail_str ail_exc_text(const ail_exception *e, ail_sarena *A) {
    if (e->xtext) return ail_exception_string_copy((ail_str){e->xtext->p, e->xtext->n, e->xtext->bytes}, A);   /* a user __str__ */
    if (e->code == AIL_EXC_UNICODE_DECODE && e->has_args && e->nargs == 5 && e->xargs[1].kind == 5 && e->xargs[2].kind == 1
        && e->xargs[3].kind == 1) return ail__exc_unicode_text(e, A);
    if (e->has_err || e->os_text) return ail_exception_string_copy((ail_str){e->p, e->n, e->bytes}, A);
    int64_t n = ail_exc_nargs(e);
    if (n == 0) return (ail_str){NULL, 0, 1};
    if (n == 1) {
        ail_exarg a = ail_exc_arg(e, 0);
        ail_str s = ail__exc_piece(&a, e->code == AIL_EXC_KEY, A);
        return a.kind == 0 && e->code != AIL_EXC_KEY ? ail_exception_string_copy(s, A) : s;
    }
    return ail_exc_argsrepr(e, A);
}
/* type(e).__name__ and its module-qualified form */
static ail_str ail_exc_typename(const ail_exception *e) { return ail__exc_lit(ail_exc_class_name(e->code)); }
static ail_str ail_exc_qualname(const ail_exception *e) { return ail__exc_lit(ail_exception_qualname(e->code)); }
/* the attributes a user exception class sets in __init__ (userexc.py), by index; kind 7 marks a slot never set */
static void ail_exception_set_attr(ail_exception *v, int idx, ail_exarg a) {
    if (idx >= v->nattrs) {
        struct ail_exarg *grown = (struct ail_exarg *)realloc(v->xattrs, (size_t)(idx + 1) * sizeof(ail_exarg));
        if (!grown) ail_die("out of memory");
        for (int k = v->nattrs; k <= idx; k++) { memset(&grown[k], 0, sizeof(ail_exarg)); grown[k].kind = 7; }
        v->xattrs = grown; v->nattrs = idx + 1;
    }
    free((void *)v->xattrs[idx].p);
    v->xattrs[idx] = a;
    if (a.kind == 0 && a.n > 0) {
        uint8_t *q = (uint8_t *)malloc((size_t)a.n);
        if (!q) ail_die("out of memory");
        ail_str_put(q, (ail_str){a.p, a.n, a.bytes});
        v->xattrs[idx].p = q;
    } else v->xattrs[idx].p = NULL;
}
/* an owned copy of a str in a slot of the exception */
static void ail__exc_set_slot(struct ail_exarg **slot, ail_str s) {
    if (*slot) { free((void *)(*slot)->p); free(*slot); }
    *slot = (struct ail_exarg *)calloc(1, sizeof(ail_exarg));
    if (!*slot) ail_die("out of memory");
    (*slot)->kind = 0; (*slot)->n = s.n; (*slot)->bytes = s.bytes;
    if (s.n > 0) {
        uint8_t *q = (uint8_t *)malloc((size_t)s.n);
        if (!q) ail_die("out of memory");
        ail_str_put(q, s);
        (*slot)->p = q;
    }
}
/* the text of a user class's __str__, computed when the exception is built */
static void ail_exception_set_text(ail_exception *v, ail_str s) { ail__exc_set_slot(&v->xtext, s); }
/* e.filename of an OSError built with (or raised for) a file name */
static void ail_exception_set_filename(ail_exception *v, ail_str s) { ail__exc_set_slot(&v->xfn, s); }
static ail_str ail_exc_filename(const ail_exception *e, ail_sarena *A) {
    if (!e->xfn) ail_raise_msg(AIL_EXC_RUNTIME, "this OSError carries no filename in a compiled program");
    return ail_exception_string_copy((ail_str){e->xfn->p, e->xfn->n, e->xfn->bytes}, A);
}
static const ail_exarg *ail__exc_attr(const ail_exception *e, int64_t idx) {
    if (idx < 0 || idx >= e->nattrs || e->xattrs[idx].kind == 7)
        ail_raise_msg(AIL_EXC_RUNTIME, "this exception has no such attribute in a compiled program");
    return &e->xattrs[idx];
}
static int64_t ail_exc_attr_i(const ail_exception *e, int64_t idx) {
    const ail_exarg *a = ail__exc_attr(e, idx);
    return a->kind == 2 ? (int64_t)a->f : a->i;
}
static double ail_exc_attr_f(const ail_exception *e, int64_t idx) {
    const ail_exarg *a = ail__exc_attr(e, idx);
    return a->kind == 2 ? a->f : (double)a->i;
}
static ail_str ail_exc_attr_s(const ail_exception *e, int64_t idx, ail_sarena *A) {
    const ail_exarg *a = ail__exc_attr(e, idx);
    return ail_exception_string_copy((ail_str){a->p, a->n, a->bytes}, A);
}
/* e.args[i] as a str; a non-str argument reads as its text.  IndexError past the end, as for a tuple. */
static ail_str ail_exc_argstr(const ail_exception *e, int64_t i, ail_sarena *A) {
    int64_t n = ail_exc_nargs(e);
    if (i < 0) i += n;
    if (i < 0 || i >= n) {
        static const char m[] = "tuple index out of range";
        ail_raise_value_adopt(ail_exception_new(AIL_EXC_INDEX, (const uint8_t *)m, (int64_t)sizeof m - 1, 1));
    }
    ail_exarg a = ail_exc_arg(e, i);
    ail_str s = ail__exc_piece(&a, 0, A);
    return a.kind == 0 ? ail_exception_string_copy(s, A) : s;
}
/* the message of an exception built from arguments: what str(e) would be, kept in p/n for e.message and for the
   report of an uncaught exception (a single str argument is the message itself) */
static void ail__exc_set_message(ail_exception *v) {
    ail_sarena A; memset(&A, 0, sizeof A);
    ail_str s = {NULL, 0, 1};
    if (v->nargs == 1 && v->xargs[0].kind == 0) s = (ail_str){v->xargs[0].p, v->xargs[0].n, v->xargs[0].bytes};
    else if (v->nargs >= 1) s = ail_exc_text(v, &A);
    if (s.n > 0) {
        uint8_t *q = (uint8_t *)malloc((size_t)s.n);
        if (!q) ail_die("out of memory");
        ail_str_put(q, s);
        v->p = q; v->n = s.n; v->bytes = s.bytes;
    }
    ail_sarena_free(&A);
}
/* an exception built from arguments (copied) */
static ail_exception *ail_exception_new_args(int code, int nargs, const ail_exarg *a) {
    ail_exception *v = ail_exception_new(code, NULL, 0, 1);
    v->has_args = 1; v->nargs = nargs;
    if (nargs > 0) {
        v->xargs = (struct ail_exarg *)calloc((size_t)nargs, sizeof(ail_exarg));
        if (!v->xargs) ail_die("out of memory");
        for (int k = 0; k < nargs; k++) {
            v->xargs[k] = a[k];
            if ((a[k].kind == 0 || a[k].kind == 5) && a[k].n > 0) {
                uint8_t *q = (uint8_t *)malloc((size_t)a[k].n);
                if (!q) ail_die("out of memory");
                ail_str_put(q, (ail_str){a[k].p, a[k].n, a[k].bytes});
                v->xargs[k].p = q;
            } else v->xargs[k].p = NULL;
        }
    }
    ail__exc_set_message(v);
    return v;
}
/* OSError(errno, strerror[, filename]) and its subclasses: "[Errno N] strerror" and ": 'filename'" in str(e), and
   (errno, strerror) as e.args.  OSError(...) itself becomes the subclass CPython picks for the errno. */
static ail_exception *ail_exception_new_oserr(int code, int64_t err, ail_str text, int has_fn, ail_str fn) {
    if (code == AIL_EXC_OS) {
        switch (err) {
        case ENOENT: code = AIL_EXC_FNF; break;
        case EACCES: case EPERM: code = AIL_EXC_PERM; break;
        case EISDIR: code = AIL_EXC_ISDIR; break;
        case EEXIST: code = AIL_EXC_EXIST; break;
        case ENOTDIR: code = AIL_EXC_NOTDIR; break;
        default: break;
        }
    }
    ail_sarena A; memset(&A, 0, sizeof A);
    char head[48];
    int h = snprintf(head, sizeof head, "[Errno %lld] ", (long long)err);
    ail_str tail = {NULL, 0, 1};
    if (has_fn) {
        ail_str r = ail_fmt_repr_str(&A, fn);
        ail_str parts[2] = {ail__exc_lit(": "), r};
        tail = ail_str_catn(&A, parts, 2);
    }
    int64_t total = (int64_t)h + text.n + tail.n;
    uint8_t *buf = (uint8_t *)malloc((size_t)(total > 0 ? total : 1));
    if (!buf) ail_die("out of memory");
    memcpy(buf, head, (size_t)h);
    if (text.n > 0) ail_str_put(buf + h, text);
    if (tail.n > 0) ail_str_put(buf + h + text.n, tail);
    ail_exception *v = ail_exception_new(code, buf, total, text.bytes && tail.bytes);
    free(buf);
    ail_sarena_free(&A);
    v->err = err; v->se_off = h; v->se_len = text.n; v->has_err = 1;
    if (has_fn) ail_exception_set_filename(v, fn);
    return v;
}
/* OSError(a, b[, filename[, winerror[, filename2]]]) with arguments of any kind (CPython parses two to five): str(e)
   is "[Errno a] b", then ": 'filename'" and " -> 'filename2'"; args is (a, b) when a filename is given, else all of them. */
static ail_exception *ail_exception_new_oserr_args(int code, int nargs, const ail_exarg *a) {
    if (code == AIL_EXC_OS && a[0].kind == 1) {
        switch (a[0].i) {
        case ENOENT: code = AIL_EXC_FNF; break;
        case EACCES: case EPERM: code = AIL_EXC_PERM; break;
        case EISDIR: code = AIL_EXC_ISDIR; break;
        case EEXIST: code = AIL_EXC_EXIST; break;
        case ENOTDIR: code = AIL_EXC_NOTDIR; break;
        default: break;
        }
    }
    int has_fn = nargs >= 3 && a[2].kind != 4;
    ail_exception *v = ail_exception_new_args(code, has_fn ? 2 : nargs, a);
    ail_sarena A; memset(&A, 0, sizeof A);
    ail_str parts[8]; int k = 0;
    parts[k++] = ail__exc_lit("[Errno ");
    parts[k++] = ail__exc_piece(&a[0], 0, &A);
    parts[k++] = ail__exc_lit("] ");
    parts[k++] = ail__exc_piece(&a[1], 0, &A);
    if (has_fn) {
        parts[k++] = ail__exc_lit(": "); parts[k++] = ail__exc_piece(&a[2], 1, &A);
        if (nargs >= 5 && a[4].kind != 4) { parts[k++] = ail__exc_lit(" -> "); parts[k++] = ail__exc_piece(&a[4], 1, &A); }
    }
    ail_str text = ail_str_catn(&A, parts, k);
    free((void *)v->p);
    uint8_t *q = (uint8_t *)malloc((size_t)(text.n > 0 ? text.n : 1));
    if (!q) ail_die("out of memory");
    ail_str_put(q, text);
    v->p = q; v->n = text.n; v->bytes = text.bytes; v->os_text = 1;
    ail_sarena_free(&A);
    if (has_fn && a[2].kind == 0) ail_exception_set_filename(v, (ail_str){a[2].p, a[2].n, a[2].bytes});
    return v;
}
/* a KeyError: str(e) is the repr of the key */
static void ail__key_error(ail_exarg a) {
    if (ail_exc_top >= 0) {
        ail_exception_store(&ail_pending_exc, ail_exception_new_args(AIL_EXC_KEY, 1, &a), 1);
    }
    ail_die("key error");
}
static void ail_key_error_i(int64_t k) { ail__key_error(ail_exarg_i(k)); }
static void ail_key_error_s(const uint8_t *p, int64_t n) { ail__key_error(ail_exarg_s((ail_str){p, n, 0})); }
static void ail_key_error_b(const uint8_t *p, int64_t n) { ail_exarg a = ail_exarg_s((ail_str){p, n, 0}); a.kind = 5; ail__key_error(a); }
/* int(<str>) and float(<str>) on text that is not a number: CPython's ValueError and its wording */
static void ail__exc_value_error(const char *head, ail_str s) {
    ail_sarena A; memset(&A, 0, sizeof A);
    ail_str parts[2] = {ail__exc_lit(head), ail_fmt_repr_str(&A, s)};
    ail_str m = ail_str_catn(&A, parts, 2);
    ail_exception *v = ail_exception_new(AIL_EXC_VALUE, m.p, m.n, m.bytes);
    ail_sarena_free(&A);
    ail_raise_value_adopt(v);
    __builtin_unreachable();
}
/* CPython's strict UTF-8 decoder: where the first error is (start, end) and why */
#define AIL__CONT(x) (((x) & 0xC0) == 0x80)
static int ail__utf8_error(const unsigned char *b, int64_t nb, int64_t *start, int64_t *end, const char **reason) {
    int64_t s = 0;
    while (s < nb) {
        unsigned c = b[s];
        int64_t rem = nb - s, e = 0;
        const char *why = NULL;
        if (c < 0x80) { s++; continue; }
        if (c < 0xE0) {
            if (c < 0xC2) { why = "invalid start byte"; e = s + 1; }
            else if (rem < 2) { why = "unexpected end of data"; e = nb; }
            else if (!AIL__CONT(b[s + 1])) { why = "invalid continuation byte"; e = s + 1; }
            else { s += 2; continue; }
        } else if (c < 0xF0) {
            if (rem < 3) {
                unsigned c2 = rem >= 2 ? b[s + 1] : 0;
                if (rem >= 2 && (!AIL__CONT(c2) || (c2 < 0xA0 ? c == 0xE0 : c == 0xED))) { why = "invalid continuation byte"; e = s + 1; }
                else { why = "unexpected end of data"; e = nb; }
            } else {
                unsigned c2 = b[s + 1], c3 = b[s + 2];
                if (!AIL__CONT(c2) || (c == 0xE0 && c2 < 0xA0) || (c == 0xED && c2 >= 0xA0)) { why = "invalid continuation byte"; e = s + 1; }
                else if (!AIL__CONT(c3)) { why = "invalid continuation byte"; e = s + 2; }
                else { s += 3; continue; }
            }
        } else if (c > 0xF4) { why = "invalid start byte"; e = s + 1; }
        else if (rem < 4) {
            unsigned c2 = rem >= 2 ? b[s + 1] : 0;
            if (rem >= 2 && (!AIL__CONT(c2) || (c2 < 0x90 ? c == 0xF0 : c == 0xF4))) { why = "invalid continuation byte"; e = s + 1; }
            else if (rem >= 3 && !AIL__CONT(b[s + 2])) { why = "invalid continuation byte"; e = s + 2; }
            else { why = "unexpected end of data"; e = nb; }
        } else {
            unsigned c2 = b[s + 1], c3 = b[s + 2], c4 = b[s + 3];
            if (!AIL__CONT(c2) || (c2 < 0x90 ? c == 0xF0 : c == 0xF4)) { why = "invalid continuation byte"; e = s + 1; }
            else if (!AIL__CONT(c3)) { why = "invalid continuation byte"; e = s + 2; }
            else if (!AIL__CONT(c4)) { why = "invalid continuation byte"; e = s + 3; }
            else { s += 4; continue; }
        }
        *start = s; *end = e; *reason = why;
        return 1;
    }
    return 0;
}
/* a text that is not valid UTF-8, caught: UnicodeDecodeError('utf-8', data, start, end, reason). `code` is the exception
   to raise, or 0 for a trap (a whole-file read) that ail_die turns into the pending exception. */
static void ail_exc_utf8_fail(const unsigned char *b, int64_t nb, const char *bad, int code) {
    int64_t start = 0, end = 0;
    const char *reason = "";
    if (ail_exc_top < 0 || !(code || !strcmp(bad, "file is not valid UTF-8")) || !ail__utf8_error(b, nb, &start, &end, &reason)) return;
    ail_exarg a[5];
    a[0] = ail_exarg_s(ail__exc_lit("utf-8"));
    a[1] = ail_exarg_s((ail_str){b, nb, 0}); a[1].kind = 5;
    a[2] = ail_exarg_i(start);
    a[3] = ail_exarg_i(end);
    a[4] = ail_exarg_s(ail__exc_lit(reason));
    ail_exception *v = ail_exception_new_args(AIL_EXC_UNICODE_DECODE, 5, a);
    if (code) ail_raise_value_adopt(v);
    ail_exception_store(&ail_pending_exc, v, 1);
}
/* str(e) of a UnicodeDecodeError built by ail_exc_utf8_fail */
static ail_str ail__exc_unicode_text(const ail_exception *e, ail_sarena *A) {
    const ail_exarg *a = e->xargs;
    int64_t cap = a[0].n + a[4].n + 160;
    uint8_t *q = ail_sarena_alloc(A, cap);
    int64_t o;
    if (a[3].i == a[2].i + 1 && a[2].i >= 0 && a[2].i < a[1].n)
        o = snprintf((char *)q, (size_t)cap, "'%.*s' codec can't decode byte 0x%02x in position %lld: %.*s", (int)a[0].n, a[0].p,
                     (unsigned)a[1].p[a[2].i], (long long)a[2].i, (int)a[4].n, a[4].p);
    else
        o = snprintf((char *)q, (size_t)cap, "'%.*s' codec can't decode bytes in position %lld-%lld: %.*s", (int)a[0].n, a[0].p,
                     (long long)a[2].i, (long long)a[3].i - 1, (int)a[4].n, a[4].p);
    return (ail_str){q, o, 1};
}
/* an OSError for `path` with the errno of a failed open / read / stat: str(e) is "[Errno N] why: 'path'" */
static void ail_exc_os_fail(int err, ail_str path) {
    const char *why = strerror(err);
    ail_raise_value_adopt(ail_exception_new_oserr(AIL_EXC_OS, err, ail__exc_lit(why ? why : "Unknown error"), 1, path));
    __builtin_unreachable();
}
static void ail_exc_int_fail(ail_str s) { ail__exc_value_error("invalid literal for int() with base 10: ", s); }
static void ail_exc_float_fail(ail_str s) { ail__exc_value_error("could not convert string to float: ", s); }
'''
