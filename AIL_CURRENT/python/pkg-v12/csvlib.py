"""`csv`: reader / DictReader / writer / DictWriter, lowered onto lists and strings (library batch 4).

Called from stdlib4.py on the parsed module before any other pass looks at it, so the compiler only ever
sees ordinary code plus a few helper functions appended to the program (only the ones used):

* `csv.reader(src, ...)` parses the whole source at once, with CPython's own state machine
  (_csv.c `parse_process_char`, the same states, so quoting, doubled quotes, embedded newlines, escapes,
  `skipinitialspace`, `strict` and the end-of-data rules give the same rows). The source is `sys.stdin`
  (or any list of str lines such as `text.splitlines(True)`, `io.StringIO(text)` is not built).
  QUOTE_NONNUMERIC is refused by name (the rows are strings here; the general path builds the floats).
  The reader name becomes the list of rows plus a cursor, so `for row in reader`, `next(reader)`,
  `next(reader, None)` (the `is None` test is rewritten), `list(reader)` and comprehensions over it
  consume from the cursor exactly as the iterator does.
* `csv.DictReader(src, fieldnames=None)`: the header is the first row (or `fieldnames=`), blank rows are
  skipped, and a row is read with `row[key]` / `row.get(key, default)` / `key in row` straight from the
  cells (no dict is built); any other use of `row` builds a `dict[str, str]`. A data row that does not have
  as many fields as the header gives CPython a None value (restval) and a longer one a list under the key
  None; neither can be held here, so reading such a value is a RuntimeError naming it.
* `csv.writer(sys.stdout, ...)` / `csv.DictWriter(sys.stdout, fieldnames, ...)`: `writerow`, `writerows`
  (and `writeheader`) write the record CPython writes (QUOTE_MINIMAL / ALL / NONE, doublequote,
  escapechar, lineterminator '\\r\\n' by default, the lone empty field written as ""), through
  sys.stdout.write. QUOTE_NONNUMERIC is refused by name (the writer cannot tell a number from a str).
* `csv.Error` in an `except` clause is spelt ValueError (the helpers raise ValueError with CPython's text).
"""
import ast
import copy

import stdlib4
from iterlower import _name, _mark, _call, _locate

MINIMAL, ALL, NONNUMERIC, NONE = 0, 1, 2, 3
QUOTING = {'QUOTE_MINIMAL': MINIMAL, 'QUOTE_ALL': ALL, 'QUOTE_NONNUMERIC': NONNUMERIC, 'QUOTE_NONE': NONE}
DIALECTS = {
    'excel': dict(delimiter=',', quotechar='"', doublequote=True, skipinitialspace=False,
                  lineterminator='\r\n', quoting=MINIMAL),
    'excel-tab': dict(delimiter='\t', quotechar='"', doublequote=True, skipinitialspace=False,
                      lineterminator='\r\n', quoting=MINIMAL),
    'unix': dict(delimiter=',', quotechar='"', doublequote=True, skipinitialspace=False,
                 lineterminator='\n', quoting=ALL),
}

PARSE_SOURCE = '''
def _ail_csv_parse(lines: list[str], delim: str, quote: str, esc: str, skip: bool, doubleq: bool, strict: bool, noquote: bool) -> list[list[str]]:
    rows: list[list[str]] = []
    fields: list[str] = []
    field = ""
    state = 0
    flen = 0
    for line in lines:
        n = len(line)
        if state == 0 and not skip and esc == "":
            fast = True
            if not noquote and quote != "" and quote in line:
                fast = False
            if fast and "\\r" in line:
                fast = False
            if fast:
                nl = line.count("\\n")
                if nl > 1 or (nl == 1 and line[n - 1] != "\\n"):
                    fast = False
            if fast:
                if n > 0 and line[n - 1] == "\\n":
                    line = line[:n - 1]
                if len(line) == 0:
                    rows.append([])
                else:
                    parts = line.split(delim)
                    rows.append(parts)
                continue
        i = 0
        while i <= n:
            eol = i == n
            c = ""
            if not eol:
                c = line[i]
            i += 1
            if state == 0:
                if eol:
                    rows.append(fields)
                    fields = []
                    continue
                if c == "\\n" or c == "\\r":
                    state = 7
                    continue
                state = 1
            if state == 1:
                if eol or c == "\\n" or c == "\\r":
                    fields.append(field)
                    field = ""
                    flen = 0
                    if eol:
                        state = 0
                        rows.append(fields)
                        fields = []
                    else:
                        state = 7
                elif c == quote and not noquote:
                    state = 4
                elif c == esc:
                    state = 2
                elif c == " " and skip:
                    pass
                elif c == delim:
                    fields.append(field)
                    field = ""
                    flen = 0
                else:
                    field += c
                    flen += 1
                    state = 3
            elif state == 3:
                if eol or c == "\\n" or c == "\\r":
                    fields.append(field)
                    field = ""
                    flen = 0
                    if eol:
                        state = 0
                        rows.append(fields)
                        fields = []
                    else:
                        state = 7
                elif c == esc:
                    state = 2
                elif c == delim:
                    fields.append(field)
                    field = ""
                    flen = 0
                    state = 1
                else:
                    field += c
                    flen += 1
            elif state == 4:
                if eol:
                    pass
                elif c == esc:
                    state = 5
                elif c == quote and not noquote:
                    if doubleq:
                        state = 6
                    else:
                        state = 3
                else:
                    field += c
                    flen += 1
            elif state == 6:
                if not eol and c == quote and not noquote:
                    field += c
                    flen += 1
                    state = 4
                elif not eol and c == delim:
                    fields.append(field)
                    field = ""
                    flen = 0
                    state = 1
                elif eol or c == "\\n" or c == "\\r":
                    fields.append(field)
                    field = ""
                    flen = 0
                    if eol:
                        state = 0
                        rows.append(fields)
                        fields = []
                    else:
                        state = 7
                elif not strict:
                    field += c
                    flen += 1
                    state = 3
                else:
                    rows.append(["\\x00csv-error", "'" + delim + "' expected after '" + quote + "'"])
                    return rows
            elif state == 2:
                if eol:
                    field += "\\n"
                    flen += 1
                    state = 3
                elif c == "\\n" or c == "\\r":
                    field += c
                    flen += 1
                    state = 8
                else:
                    field += c
                    flen += 1
                    state = 3
            elif state == 5:
                if eol:
                    field += "\\n"
                else:
                    field += c
                flen += 1
                state = 4
            elif state == 7:
                if eol:
                    state = 0
                    rows.append(fields)
                    fields = []
                elif c == "\\n" or c == "\\r":
                    pass
                else:
                    rows.append(["\\x00csv-error", "new-line character seen in unquoted field - do you need to open the file with newline=''?"])
                    return rows
            elif state == 8:
                if not eol:
                    if c == "\\n" or c == "\\r":
                        fields.append(field)
                        field = ""
                        flen = 0
                        state = 7
                    elif c == esc:
                        state = 2
                    elif c == delim:
                        fields.append(field)
                        field = ""
                        flen = 0
                        state = 1
                    else:
                        field += c
                        flen += 1
                        state = 3
    if flen != 0 or state == 4:
        if strict:
            rows.append(["\\x00csv-error", "unexpected end of data"])
            return rows
        fields.append(field)
        rows.append(fields)
    return rows
'''

LINES_SOURCE = '''
def _ail_csv_lines(text: str) -> list[str]:
    out: list[str] = []
    cur = ""
    for ch in text:
        cur += ch
        if ch == "\\n":
            out.append(cur)
            cur = ""
    if cur != "":
        out.append(cur)
    return out
'''

FAILED_SOURCE = '''
def _ail_csv_failed(rows: list[list[str]]) -> bool:
    n = len(rows)
    return n > 0 and len(rows[n - 1]) == 2 and rows[n - 1][0] == "\\x00csv-error"
'''

COL_SOURCE = '''
def _ail_csv_col(h: list[str], cells: list[str], key: str) -> str:
    k = len(h) - 1
    while k >= 0:
        if h[k] == key:
            if k >= len(cells):
                raise RuntimeError("csv.DictReader: the row has fewer fields than the header, so CPython gives the missing keys the value None (restval); None values are not built")
            return cells[k]
        k -= 1
    raise KeyError(key)


def _ail_csv_colget(h: list[str], cells: list[str], key: str, default: str) -> str:
    k = len(h) - 1
    while k >= 0:
        if h[k] == key:
            if k >= len(cells):
                raise RuntimeError("csv.DictReader: the row has fewer fields than the header, so CPython gives the missing keys the value None (restval); None values are not built")
            return cells[k]
        k -= 1
    return default


def _ail_csv_has(h: list[str], key: str) -> bool:
    for name in h:
        if name == key:
            return True
    return False
'''

DICT_SOURCE = '''
def _ail_csv_dict(h: list[str], cells: list[str]) -> dict[str, str]:
    d: dict[str, str] = {}
    if len(cells) < len(h):
        raise RuntimeError("csv.DictReader: the row has fewer fields than the header, so CPython gives the missing keys the value None (restval); None values are not built")
    if len(cells) > len(h):
        raise RuntimeError("csv.DictReader: the row has more fields than the header, so CPython collects them in a list under the key None (restkey); that is not built")
    for k in range(len(h)):
        d[h[k]] = cells[k]
    return d
'''

JOIN_SOURCE = '''
def _ail_csv_join(fields: list[str], delim: str, quote: str, esc: str, lt: str, quoting: int, doubleq: bool) -> str:
    n = len(fields)
    if n == 1 and len(fields[0]) == 0:
        if quoting == 3:
            raise ValueError("single empty field record must be quoted")
        return quote + quote + lt
    out = ""
    for k in range(n):
        f = fields[k]
        if k > 0:
            out += delim
        quoted = quoting == 1
        seg = ""
        for c in f:
            if c == delim or (esc != "" and c == esc) or (quote != "" and c == quote) or c == "\\n" or c == "\\r" or c in lt:
                if quoting == 3:
                    if esc == "":
                        raise ValueError("need to escape, but no escapechar set")
                    seg += esc
                else:
                    want = False
                    if quote != "" and c == quote:
                        if doubleq:
                            seg += quote
                        else:
                            want = True
                    elif esc != "" and c == esc:
                        want = True
                    if want:
                        if esc == "":
                            raise ValueError("need to escape, but no escapechar set")
                        seg += esc
                    else:
                        quoted = True
            seg += c
        if quoted:
            out += quote + seg + quote
        else:
            out += seg
    return out + lt
'''

SOURCES = {'failed': FAILED_SOURCE, 'parse': PARSE_SOURCE, 'lines': LINES_SOURCE, 'col': COL_SOURCE, 'dict': DICT_SOURCE,
           'join': JOIN_SOURCE}


class Dialect:
    def __init__(self):
        self.__dict__.update(DIALECTS['excel'])
        self.escapechar = None
        self.strict = False


def const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def const_bool(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (bool, int)) and not isinstance(node.value, str):
        return bool(node.value)
    return None


class Csv:
    """One pass over the module: every function body (and the module body) is a scope."""

    def __init__(self, imports, tree, out):
        self.imports = imports
        self.tree = tree
        self.out = out                    # the helper function sources to append to the program
        self.used = set()
        self.helpers = []
        self.count = 0

    # -- plumbing ------------------------------------------------------------------------------------
    def refuse(self, node, text):
        stdlib4.refuse(node, text)

    def fresh(self, stem):
        self.count += 1
        return '_csv%d_%s' % (self.count, stem)

    def helper(self, name):
        self.used.add(name)

    def csv_attr(self, node):
        """`csv.<attr>` -> attr, else None."""
        found = self.imports.resolve(node) if isinstance(node, (ast.Attribute, ast.Name)) else None
        if found is not None and found[0] == 'csv':
            return found[1]
        return None

    def ctor_kind(self, node):
        if isinstance(node, ast.Call):
            attr = self.csv_attr(node.func)
            if attr in ('reader', 'DictReader', 'writer', 'DictWriter'):
                return attr
        return None

    # -- dialect arguments -----------------------------------------------------------------------------
    def dialect(self, call, positional, extra=()):
        """The Dialect of a reader / writer constructor call; `positional` names the parameters after
        the first, in order; `extra` names keywords that are not dialect fields (returned in a dict)."""
        what = 'csv.' + self.csv_attr(call.func)
        if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            self.refuse(call, '%s: * and ** arguments are not built' % what)
        given = {}
        if len(call.args) - 1 > len(positional):
            self.refuse(call, '%s: too many arguments' % what)
        for name, value in zip(positional, call.args[1:]):
            given[name] = value
        for keyword in call.keywords:
            if keyword.arg in given:
                self.refuse(call, '%s: %s given twice' % (what, keyword.arg))
            given[keyword.arg] = keyword.value
        known = {'dialect', 'delimiter', 'quotechar', 'escapechar', 'doublequote', 'skipinitialspace',
                 'lineterminator', 'quoting', 'strict'}
        extras = {}
        for name in list(given):
            if name in extra:
                extras[name] = given.pop(name)
            elif name not in known:
                self.refuse(call, '%s: the argument %s is not built (nor valid in CPython)' % (what, name))
        d = Dialect()
        if 'dialect' in given:
            name = const_str(given['dialect'])
            if name is None:
                attr = self.csv_attr(given['dialect'])
                name = {'excel': 'excel', 'excel_tab': 'excel-tab', 'unix_dialect': 'unix'}.get(attr)
            if name not in DIALECTS:
                self.refuse(call, '%s: dialect has to be "excel", "excel-tab" or "unix" (csv.register_dialect '
                            'and Dialect subclasses are not built)' % what)
            d.__dict__.update(DIALECTS[name])
        for name in ('delimiter', 'quotechar', 'escapechar', 'lineterminator'):
            if name in given:
                value = given[name]
                if isinstance(value, ast.Constant) and value.value is None and name in ('quotechar', 'escapechar'):
                    setattr(d, name, None)
                    continue
                text = const_str(value)
                if text is None:
                    self.refuse(call, '%s: %s= has to be a string literal' % (what, name))
                if name != 'lineterminator' and len(text) != 1:
                    self.refuse(call, '%s: "%s" must be a 1-character string (CPython raises TypeError)'
                                % (what, name))
                setattr(d, name, text)
        for name in ('doublequote', 'skipinitialspace', 'strict'):
            if name in given:
                value = const_bool(given[name])
                if value is None:
                    self.refuse(call, '%s: %s= has to be True or False' % (what, name))
                setattr(d, name, value)
        if 'quoting' in given:
            attr = self.csv_attr(given['quoting'])
            if attr not in QUOTING:
                self.refuse(call, '%s: quoting= has to be csv.QUOTE_MINIMAL, QUOTE_ALL, QUOTE_NONNUMERIC or '
                            'QUOTE_NONE' % what)
            d.quoting = QUOTING[attr]
        if d.quotechar is None and d.quoting != NONE:
            self.refuse(call, '%s: quotechar must be set if quoting enabled (CPython raises TypeError)' % what)
        return d, extras

    # -- scopes -------------------------------------------------------------------------------------------
    def run(self):
        self.scope(self.tree.body, self.tree, None)
        self.fix_except(self.tree)
        self.attach()

    def attach(self):
        """The helper functions that were used, to be appended to the program text."""
        for name in ['parse', 'failed', 'lines', 'col', 'dict', 'join']:
            if name in self.used:
                self.out.append(SOURCES[name])

    def fix_except(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                types = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
                for index, each in enumerate(types):
                    if self.csv_attr(each) == 'Error':
                        types[index] = _name('ValueError')
                if isinstance(node.type, ast.Tuple):
                    node.type.elts = types
                elif types and types[0] is not node.type:
                    node.type = types[0]

    def scope(self, body, owner, outer):
        state = Scope(owner)
        new = self.block(body, state, [])
        body[:] = new
        self.check_names(owner, state)

    def check_names(self, owner, state):
        """Every use of a reader / writer name written by the program was understood and rewritten (the
        names the rewrite wrote are marked); one that is left is a use that is not built."""
        names = set(state.readers) | set(state.writers)
        if not names:
            return
        for each in ast.walk(owner):
            if isinstance(each, ast.Name) and each.id in names and not getattr(each, '_ail_synth', False):
                kind = state.readers.get(each.id) or state.writers.get(each.id)
                self.refuse(each, 'the csv %s %s is used here in a way that is not built (a reader is built '
                            'as the iterable of a for statement or comprehension, in next() and list(); a '
                            'writer through writerow / writerows; none can be passed to a function or '
                            'stored)' % (getattr(kind, 'kind', 'object'), each.id))

    # -- statements -------------------------------------------------------------------------------------
    def block(self, stmts, state, out):
        result = []
        for stmt in stmts:
            result.extend(self.stmt(stmt, state))
        return result

    def stmt(self, s, state):
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.scope(s.body, s, state)
            return [s]
        if isinstance(s, ast.ClassDef):
            for each in s.body:
                if isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.scope(each.body, each, state)
            return [s]
        # a constructor assigned to a name
        made = self.constructor_assign(s, state)
        if made is not None:
            return made
        pre, post = [], []
        out = self.header(s, state, pre, post)
        return pre + out + post

    def constructor_assign(self, s, state):
        value = target = None
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
            target, value = s.targets[0], s.value
        elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name) and s.value is not None:
            target, value = s.target, s.value
        if value is None:
            return None
        kind = self.ctor_kind(value)
        if kind is None:
            return None
        name = target.id
        if name in state.readers or name in state.writers:
            self.refuse(s, 'the csv name %s is assigned twice; use one variable per reader / writer' % name)
        if kind in ('reader', 'DictReader'):
            return self.make_reader(name, value, kind, s, state)
        return self.make_writer(name, value, kind, s, state)

    # -- readers ---------------------------------------------------------------------------------------------
    def source_expr(self, call, pre):
        """The list[str] of lines the reader parses (statements that build it go to `pre`)."""
        if not call.args:
            self.refuse(call, 'csv.%s() needs a source' % self.csv_attr(call.func))
        src = call.args[0]
        if (isinstance(src, ast.Attribute) and src.attr == 'stdin' and isinstance(src.value, ast.Name)
                and src.value.id == 'sys'):
            var, lines = self.fresh('l'), self.fresh('lines')
            comp = ast.ListComp(elt=_name(var), generators=[ast.comprehension(
                target=_name(var, True), iter=copy.deepcopy(src), ifs=[], is_async=0)])
            pre.append(_mark(ast.Assign(targets=[_name(lines, True)], value=comp)))
            return _name(lines)
        if isinstance(src, ast.Constant):
            self.refuse(call, 'csv.reader over a str: it would walk characters; pass a list of lines '
                        '(text.splitlines(True) / sys.stdin)')
        if isinstance(src, ast.Call) and isinstance(src.func, ast.Attribute) and src.func.attr == 'StringIO':
            self.refuse(call, 'csv.reader(io.StringIO(...)) is not built: pass the lines (a list of str ending '
                        'in "\n" as text.splitlines(True) gives, or sys.stdin)')
        return copy.deepcopy(src)

    def emit_parse(self, name, call, d, pre, errs, count):
        """Statements: `name` = the parsed rows; `errs` = the csv.Error text when the parse stopped on an
        error (raised when the consumer reaches the end of the rows, where CPython's lazy reader would
        have raised it)."""
        self.helper('parse')
        self.helper('failed')
        noquote = d.quoting == NONE
        args = [self.source_expr(call, pre), ast.Constant(value=d.delimiter),
                ast.Constant(value=d.quotechar or ''), ast.Constant(value=d.escapechar or ''),
                ast.Constant(value=d.skipinitialspace), ast.Constant(value=d.doublequote),
                ast.Constant(value=d.strict), ast.Constant(value=noquote)]
        pre.append(_mark(ast.Assign(targets=[_name(name, True)], value=_call(_name('_ail_csv_parse'), *args))))
        pre.append(_mark(ast.AnnAssign(target=_name(errs, True), annotation=ast.Subscript(
            value=_name('list'), slice=_name('str'), ctx=ast.Load()), value=ast.List(elts=[], ctx=ast.Load()),
            simple=1)))
        # a parse that stopped on an error ends with one row carrying the message: it is not a row
        pre.append(_mark(ast.Assign(targets=[_name(count, True)], value=_call(_name('len'), _name(name)))))
        pre.append(_mark(ast.If(
            test=_call(_name('_ail_csv_failed'), _name(name)),
            body=[ast.AugAssign(target=_name(count, True), op=ast.Sub(), value=ast.Constant(value=1)),
                  ast.Expr(value=_call(ast.Attribute(value=_name(errs), attr='append', ctx=ast.Load()),
                                       ast.Subscript(value=ast.Subscript(value=_name(name), slice=_name(count),
                                                                         ctx=ast.Load()),
                                                     slice=ast.Constant(value=1), ctx=ast.Load())))],
            orelse=[])))

    def take_rest(self, info, pre):
        """Statements: the rows the reader has not yielded yet in a list of their own, the reader consumed
        (a csv.Error that stopped the parse is raised, as the lazy reader raises it at the end)."""
        rows, at = self.fresh('rows'), self.fresh('at')
        # annotated (the compiler walks a list of rows only when it is told the element type)
        pre.append(_mark(ast.AnnAssign(target=_name(rows, True), annotation=ast.Subscript(
            value=_name('list'), slice=ast.Subscript(value=_name('list'), slice=_name('str'), ctx=ast.Load()),
            ctx=ast.Load()), value=ast.List(elts=[], ctx=ast.Load()), simple=1)))
        pre.append(_mark(ast.Assign(targets=[_name(at, True)], value=_name(info.pos))))
        copy_row = self.fresh('cp')
        pre.append(_mark(ast.While(
            test=ast.Compare(left=_name(at), ops=[ast.Lt()], comparators=[_name(info.count)]),
            body=[ast.Assign(targets=[_name(copy_row, True)],
                             value=ast.Subscript(value=_name(info.name), slice=_name(at), ctx=ast.Load())),
                  ast.Expr(value=_call(ast.Attribute(value=_name(rows), attr='append', ctx=ast.Load()),
                                       _name(copy_row))),
                  ast.AugAssign(target=_name(at, True), op=ast.Add(), value=ast.Constant(value=1))],
            orelse=[])))
        pre.append(_mark(ast.Assign(targets=[_name(info.pos, True)], value=_name(info.count))))
        pre.append(self.err_check(info.errs))
        return rows

    def err_check(self, errs):
        """`if errs: raise ValueError(errs[0])`"""
        return _mark(ast.If(test=ast.Compare(left=_call(_name('len'), _name(errs)), ops=[ast.Gt()],
                                             comparators=[ast.Constant(value=0)]),
                            body=[ast.Raise(exc=_call(_name('ValueError'), ast.Subscript(
                                value=_name(errs), slice=ast.Constant(value=0), ctx=ast.Load())), cause=None)],
                            orelse=[]))

    def make_reader(self, name, call, kind, s, state):
        positional = ['dialect'] if kind == 'reader' else ['fieldnames', 'restkey', 'restval', 'dialect']
        d, extras = self.dialect(call, positional, extra=('fieldnames', 'restkey', 'restval')
                                 if kind == 'DictReader' else ())
        if d.quoting == NONNUMERIC:
            self.refuse(call, 'csv.QUOTE_NONNUMERIC is not built for a %s: it yields float and str '
                              '(the general path builds it)' % self.csv_attr(call.func))
        if d.quotechar is None and d.quoting != NONE:
            d.quoting = NONE
        info = Reader(name, kind, self.fresh('pos'), self.fresh('hdr') if kind == 'DictReader' else None,
                      self.fresh('errs'), self.fresh('n'))
        for key in ('restkey', 'restval'):
            if key in extras and not (isinstance(extras[key], ast.Constant) and extras[key].value is None):
                self.refuse(call, 'csv.DictReader: %s= is not built (rows with a missing or extra field give '
                            'None values and keys otherwise)' % key)
        state.readers[name] = info
        out = []
        self.emit_parse(name, call, d, out, info.errs, info.count)
        out.append(ast.Assign(targets=[_name(info.pos, True)], value=ast.Constant(value=0)))
        if kind == 'DictReader':
            fieldnames = extras.get('fieldnames')
            if fieldnames is not None and not (isinstance(fieldnames, ast.Constant) and fieldnames.value is None):
                if not isinstance(fieldnames, (ast.List, ast.Tuple, ast.Name)):
                    self.refuse(call, 'csv.DictReader: fieldnames= has to be a list display or a list name')
                if isinstance(fieldnames, ast.Tuple):
                    fieldnames = ast.List(elts=fieldnames.elts, ctx=ast.Load())
                out.append(ast.Assign(targets=[_name(info.hdr, True)], value=copy.deepcopy(fieldnames)))
            else:
                out.append(ast.AnnAssign(target=_name(info.hdr, True), annotation=ast.Subscript(
                    value=_name('list'), slice=_name('str'), ctx=ast.Load()),
                    value=ast.List(elts=[], ctx=ast.Load()), simple=1))
                head = ast.If(test=ast.Compare(left=_name(info.count), ops=[ast.Gt()],
                                               comparators=[ast.Constant(value=0)]),
                              body=[ast.Assign(targets=[_name(info.hdr, True)],
                                               value=ast.Subscript(value=_name(name), slice=ast.Constant(value=0),
                                                                   ctx=ast.Load())),
                                    ast.Assign(targets=[_name(info.pos, True)], value=ast.Constant(value=1))],
                              orelse=[])
                out.append(head)
        for each in out:
            _mark(each)
        _locate(out, s)
        return out

    def reader_of(self, node, state):
        if isinstance(node, ast.Name) and node.id in state.readers:
            return state.readers[node.id]
        return None

    # -- statement headers ------------------------------------------------------------------------------------
    def header(self, s, state, pre, post):
        """Lower the reader / writer uses in one statement; returns the statements replacing it (before
        `pre`, after `post`)."""
        if isinstance(s, ast.For):
            return self.for_stmt(s, state, pre)
        if isinstance(s, ast.While):
            self.expr(s.test, state, pre, repeated=True)
            s.body = self.block(s.body, state, [])
            s.orelse = self.block(s.orelse, state, [])
            return [s]
        if isinstance(s, ast.If):
            s.test = self.expr(s.test, state, pre)
            s.test = self.none_tests(s.test, state)
            s.body = self.block(s.body, state, [])
            s.orelse = self.block(s.orelse, state, [])
            return [s]
        if isinstance(s, (ast.With, ast.AsyncWith)):
            for item in s.items:
                item.context_expr = self.expr(item.context_expr, state, pre)
            s.body = self.block(s.body, state, [])
            return [s]
        if isinstance(s, ast.Try):
            s.body = self.block(s.body, state, [])
            for handler in s.handlers:
                handler.body = self.block(handler.body, state, [])
            s.orelse = self.block(s.orelse, state, [])
            s.finalbody = self.block(s.finalbody, state, [])
            return [s]
        # writer statements
        written = self.writer_stmt(s, state)
        if written is not None:
            return written
        nxt = self.next_none_stmt(s, state)
        if nxt is not None:
            return nxt
        for field, value in ast.iter_fields(s):
            if isinstance(value, ast.expr):
                setattr(s, field, self.none_tests(self.expr(value, state, pre), state))
            elif isinstance(value, list):
                for index, each in enumerate(value):
                    if isinstance(each, ast.expr):
                        value[index] = self.none_tests(self.expr(each, state, pre), state)
        return [s]

    def for_stmt(self, s, state, pre):
        info = self.reader_of(s.iter, state)
        ctor = self.ctor_kind(s.iter)
        if ctor in ('reader', 'DictReader'):
            # hoist the constructor to a temporary name
            temp = self.fresh('r')
            made = self.make_reader(temp, s.iter, ctor, s, state)
            s.iter = _name(temp)
            return made + self.for_stmt(s, state, pre)
        if info is None:
            # the iterable may hold a consuming use (enumerate(reader), list(reader), ...)
            if isinstance(s.iter, ast.Call) and isinstance(s.iter.func, ast.Name) and s.iter.func.id == 'enumerate' \
                    and s.iter.args and self.reader_of(s.iter.args[0], state) is not None \
                    and isinstance(s.target, ast.Tuple) and len(s.target.elts) == 2 and not s.iter.keywords:
                return self.enumerate_loop(s, state)
            s.iter = self.expr(s.iter, state, pre)
            s.body = self.block(s.body, state, [])
            s.orelse = self.block(s.orelse, state, [])
            return [s]
        if s.orelse:
            self.refuse(s, 'for ... else over a csv reader is not built')
        return self.reader_loop(s, info, s.target, s.body, state, None)

    def enumerate_loop(self, s, state):
        info = self.reader_of(s.iter.args[0], state)
        if s.orelse:
            self.refuse(s, 'for ... else over a csv reader is not built')
        start = s.iter.args[1] if len(s.iter.args) > 1 else ast.Constant(value=0)
        counter = self.fresh('i')
        index_target, row_target = s.target.elts
        if not isinstance(index_target, ast.Name):
            self.refuse(s, 'enumerate over a csv reader: the index has to be a plain name')
        pre = [ast.Assign(targets=[_name(counter, True)], value=copy.deepcopy(start))]
        bump = [ast.Assign(targets=[copy.deepcopy(index_target)], value=_name(counter)),
                ast.AugAssign(target=_name(counter, True), op=ast.Add(), value=ast.Constant(value=1))]
        for each in pre + bump:
            _mark(each)
        return pre + self.reader_loop(s, info, row_target, s.body, state, bump)

    def reader_loop(self, s, info, target, body, state, extra):
        pos = info.pos
        cond = ast.Compare(left=_name(pos), ops=[ast.Lt()], comparators=[_name(info.count)])
        take = ast.Subscript(value=_name(info.name), slice=_name(pos), ctx=ast.Load())
        bump = ast.AugAssign(target=_name(pos, True), op=ast.Add(), value=ast.Constant(value=1))
        loop_body = []
        if info.kind == 'reader':
            if not isinstance(target, (ast.Name, ast.Tuple)):
                self.refuse(s, 'for over a csv reader: the target has to be a name or a tuple of names')
            loop_body.append(ast.Assign(targets=[target], value=take))
            loop_body.append(bump)
            loop_body.extend(extra or [])
            loop_body.extend(self.block(body, state, []))
        else:
            if not isinstance(target, ast.Name):
                self.refuse(s, 'for over a csv.DictReader: the row variable has to be a plain name')
            cells = self.fresh('c')
            loop_body.append(ast.Assign(targets=[_name(cells, True)], value=take))
            loop_body.append(bump)
            loop_body.append(ast.If(test=ast.Compare(left=_call(_name('len'), _name(cells)), ops=[ast.Eq()],
                                                     comparators=[ast.Constant(value=0)]),
                                    body=[ast.Continue()], orelse=[]))
            loop_body.extend(extra or [])
            inside = {id(n) for n in ast.walk(s)}
            new_body = self.block(body, state, [])
            # row access straight from the cells, or a dict when anything else needs one
            rowname = target.id
            uses = RowUses(rowname)
            for each in new_body:
                uses.visit(each)
            outside = any(isinstance(n, ast.Name) and n.id == rowname and id(n) not in inside
                          and not getattr(n, '_ail_synth', False) for n in ast.walk(state.owner))
            if uses.other or uses.bound or outside:
                self.helper('dict')
                loop_body.append(ast.Assign(targets=[_name(rowname, True)], value=_call(
                    _name('_ail_csv_dict'), _name(info.hdr), _name(cells))))
            else:
                self.helper('col')
                new_body = [RowRewrite(rowname, info.hdr, cells).visit(each) for each in new_body]
            loop_body.extend(new_body)
        loop = ast.While(test=cond, body=loop_body, orelse=[])
        out = [loop, self.err_check(info.errs)]
        for each in out:
            _mark(each)
            ast.copy_location(each, s)
        _locate(out, s)
        return out

    # -- expressions ---------------------------------------------------------------------------------------------
    def expr(self, node, state, pre, repeated=False):
        """Rewrite reader uses inside an expression; statements that must run first go to `pre`."""
        lower = self

        class Visitor(ast.NodeTransformer):
            def __init__(self):
                self.conditional = repeated

            def guard(self, call, what):
                if self.conditional:
                    lower.refuse(call, '%s is evaluated conditionally or repeatedly here; bind it to a '
                                 'variable on a line of its own first' % what)

            def visit_Lambda(self, node):
                saved, self.conditional = self.conditional, True
                self.generic_visit(node)
                self.conditional = saved
                return node

            def visit_IfExp(self, node):
                node.test = self.visit(node.test)
                saved, self.conditional = self.conditional, True
                node.body = self.visit(node.body)
                node.orelse = self.visit(node.orelse)
                self.conditional = saved
                return node

            def visit_BoolOp(self, node):
                node.values[0] = self.visit(node.values[0])
                saved, self.conditional = self.conditional, True
                node.values[1:] = [self.visit(v) for v in node.values[1:]]
                self.conditional = saved
                return node

            def comprehension(self, node):
                first = node.generators[0]
                first.iter = self.consumed_iter(first, node)
                saved, self.conditional = self.conditional, True
                for index, gen in enumerate(node.generators):
                    if index:
                        gen.iter = self.consumed_iter(gen, node)
                    gen.ifs = [self.visit(c) for c in gen.ifs]
                if isinstance(node, ast.DictComp):
                    node.key, node.value = self.visit(node.key), self.visit(node.value)
                else:
                    node.elt = self.visit(node.elt)
                self.conditional = saved
                return node

            visit_ListComp = visit_SetComp = visit_GeneratorExp = visit_DictComp = comprehension

            def consumed_iter(self, gen, comp):
                it = gen.iter
                info = lower.reader_of(it, state)
                ctor = lower.ctor_kind(it)
                if info is None and ctor in ('reader', 'DictReader'):
                    self.guard(it, 'csv.' + ctor + '(...)')
                    temp = lower.fresh('r')
                    pre.extend(lower.make_reader(temp, it, ctor, it, state))
                    info = state.readers[temp]
                    it = _name(temp)
                if info is None:
                    return self.visit(it)
                self.guard(it, 'the csv reader ' + info.name)
                rows = lower.take_rest(info, pre)
                if info.kind == 'DictReader':
                    self.dict_generator(gen, info, rows)
                return _name(rows)

            def dict_generator(self, gen, info, rows):
                if not isinstance(gen.target, ast.Name):
                    lower.refuse(gen, 'a comprehension over a csv.DictReader: the row variable has to be a name')
                rowname = gen.target.id
                cells = lower.fresh('c')
                gen.target = _name(cells, True)
                gen.ifs.insert(0, _mark(ast.Compare(left=_call(_name('len'), _name(cells)), ops=[ast.NotEq()],
                                                    comparators=[ast.Constant(value=0)])))
                self.pending_rows.append((rowname, info, cells, gen))

            pending_rows = None

            def visit_Call(self, node):
                func = node.func
                if isinstance(func, ast.Name) and func.id in ('next', 'list') and node.args \
                        and lower.ctor_kind(node.args[0]) in ('reader', 'DictReader'):
                    ctor = lower.ctor_kind(node.args[0])
                    self.guard(node, 'csv.%s(...)' % ctor)
                    temp = lower.fresh('r')
                    pre.extend(lower.make_reader(temp, node.args[0], ctor, node, state))
                    node.args[0] = _name(temp)
                # next(reader[, default])
                if isinstance(func, ast.Name) and func.id == 'next' and node.args:
                    info = lower.reader_of(node.args[0], state)
                    if info is not None:
                        self.guard(node, 'next(%s)' % info.name)
                        return lower.next_call(node, info, pre)
                # list(reader), sorted(reader), ...
                if isinstance(func, ast.Name) and func.id in ('list', 'sorted', 'tuple', 'len') and node.args:
                    info = lower.reader_of(node.args[0], state)
                    if info is not None and func.id in ('list',):
                        self.guard(node, 'list(%s)' % info.name)
                        if info.kind != 'reader':
                            # a list of dict rows: the typed path does not hold one (the program is built on the
                            # general path); each row is the dict a `for row in reader` loop would build
                            rest = lower.take_rest(info, pre)
                            lower.helper('dict')
                            drows, cellsname = lower.fresh('drows'), lower.fresh('c')
                            pre.append(_mark(ast.Assign(targets=[_name(drows, True)], value=ast.ListComp(
                                elt=_call(_name('_ail_csv_dict'), _name(info.hdr), _name(cellsname)),
                                generators=[ast.comprehension(target=_name(cellsname, True), iter=_name(rest), ifs=[
                                    ast.Compare(left=_call(_name('len'), _name(cellsname)), ops=[ast.NotEq()],
                                                comparators=[ast.Constant(value=0)])], is_async=0)]))))
                            return _name(drows)
                        return _name(lower.take_rest(info, pre))
                ctor = lower.ctor_kind(node)
                if ctor in ('reader', 'DictReader'):
                    parent_ok = False
                    lower.refuse(node, 'csv.%s(...) is built assigned to a name, as the iterable of a for '
                                 'statement or comprehension, or as the argument of next()/list()' % ctor)
                self.generic_visit(node)
                return node

            def visit_Attribute(self, node):
                info = lower.reader_of(node.value, state)
                if info is not None:
                    if node.attr == 'fieldnames' and info.kind == 'DictReader':
                        return _name(info.hdr)
                    lower.refuse(node, '%s.%s is not built for a csv reader' % (info.name, node.attr))
                self.generic_visit(node)
                return node

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load) and node.id in state.readers:
                    lower.refuse(node, 'the csv reader %s is used as a value here; it is built as the iterable '
                                 'of a for statement or comprehension, in next() and list()' % node.id)
                return node

        v = Visitor()
        v.pending_rows = []
        out = v.visit(node)
        # DictReader comprehension rows: access straight from the cells, or build the dict
        for rowname, info, cells, gen in v.pending_rows:
            comp = self.owner_comp(out, gen)
            if comp is None:
                continue
            uses = RowUses(rowname)
            self.visit_parts(uses, comp, gen)
            if uses.other or uses.bound:
                self.helper('dict')
                rep = _mark(_call(_name('_ail_csv_dict'), _name(info.hdr), _name(cells)))
                self.apply_parts(_SubstName(rowname, rep), comp, gen)
            else:
                self.helper('col')
                self.apply_parts(RowRewrite(rowname, info.hdr, cells), comp, gen)
        return out

    def owner_comp(self, tree, gen):
        for each in ast.walk(tree):
            if isinstance(each, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)) \
                    and any(g is gen for g in each.generators):
                return each
        return None

    def parts(self, comp, gen):
        index = next(i for i, g in enumerate(comp.generators) if g is gen)
        pieces = list(gen.ifs)
        for later in comp.generators[index + 1:]:
            pieces.append(later.iter)
            pieces.extend(later.ifs)
        if isinstance(comp, ast.DictComp):
            pieces.extend([comp.key, comp.value])
        else:
            pieces.append(comp.elt)
        return pieces

    def visit_parts(self, visitor, comp, gen):
        for piece in self.parts(comp, gen)[1:]:        # [0] is the blank-row test written here
            visitor.visit(piece)

    def apply_parts(self, transformer, comp, gen):
        index = next(i for i, g in enumerate(comp.generators) if g is gen)
        gen.ifs = [gen.ifs[0]] + [transformer.visit(c) for c in gen.ifs[1:]]
        for later in comp.generators[index + 1:]:
            later.iter = transformer.visit(later.iter)
            later.ifs = [transformer.visit(c) for c in later.ifs]
        if isinstance(comp, ast.DictComp):
            comp.key, comp.value = transformer.visit(comp.key), transformer.visit(comp.value)
        else:
            comp.elt = transformer.visit(comp.elt)

    # -- next() -----------------------------------------------------------------------------------------------------
    def next_call(self, call, info, pre):
        if len(call.args) > 2 or call.keywords:
            self.refuse(call, 'next(): the arguments are the reader and an optional default')
        if info.kind != 'reader':
            self.refuse(call, 'next(%s): a dict row of a csv.DictReader cannot be taken out of the loop; loop '
                        'over the DictReader' % info.name)
        row = self.fresh('row')
        take = [ast.Assign(targets=[_name(row, True)], value=ast.Subscript(
            value=_name(info.name), slice=_name(info.pos), ctx=ast.Load())),
            ast.AugAssign(target=_name(info.pos, True), op=ast.Add(), value=ast.Constant(value=1))]
        def end_test():
            return ast.Compare(left=_name(info.pos), ops=[ast.GtE()],
                               comparators=[_name(info.count)])
        # the csv.Error that stopped the parse is raised where the lazy reader would have raised it
        pre.append(_mark(ast.If(test=end_test(), body=[self.err_check(info.errs)], orelse=[])))
        if len(call.args) == 1:
            pre.append(_mark(ast.If(test=end_test(), body=[ast.Raise(exc=_name('StopIteration'), cause=None)],
                                    orelse=[])))
            pre.extend(_mark(t) for t in take)
            return _name(row)
        default = call.args[1]
        if isinstance(default, ast.Constant) and default.value is None:
            ok = self.fresh('ok')
            pre.append(_mark(ast.Assign(targets=[_name(row, True)], value=ast.List(elts=[], ctx=ast.Load()))))
            pre[-1] = _mark(ast.AnnAssign(target=_name(row, True), annotation=ast.Subscript(
                value=_name('list'), slice=_name('str'), ctx=ast.Load()), value=ast.List(elts=[], ctx=ast.Load()),
                simple=1))
            pre.append(_mark(ast.Assign(targets=[_name(ok, True)],
                                        value=ast.UnaryOp(op=ast.Not(), operand=end_test()))))
            pre.append(_mark(ast.If(test=_name(ok), body=take, orelse=[])))
            node = _name(row)
            node._csv_none = ok
            self.last_none = ok
            return node
        row_default = self.fresh('d')
        pre.append(_mark(ast.Assign(targets=[_name(row_default, True)], value=copy.deepcopy(default))))
        pre.append(_mark(ast.If(test=end_test(), body=[ast.Assign(targets=[_name(row, True)],
                                                                  value=_name(row_default))],
                                orelse=take)))
        return _name(row)

    last_none = None

    def next_none_stmt(self, s, state):
        """`X = next(reader, None)`: remember which flag stands for "X is None"."""
        target = value = None
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
            target, value = s.targets[0], s.value
        elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name) and s.value is not None:
            target, value = s.target, s.value
        if (target is None or not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name)
                or value.func.id != 'next' or len(value.args) != 2
                or not (isinstance(value.args[1], ast.Constant) and value.args[1].value is None)):
            return None
        info = self.reader_of(value.args[0], state)
        if info is None:
            return None
        pre = []
        node = self.next_call(value, info, pre)
        ok = node._csv_none
        if target.id in state.none_vars:
            self.refuse(s, '%s is assigned from next(reader, None) twice' % target.id)
        state.none_vars[target.id] = ok
        # the annotation (X: list[str] | None) is dropped: X holds the row, or an empty list
        out = pre + [_mark(ast.Assign(targets=[_name(target.id, True)], value=node))]
        _locate(out, s)
        return out

    def none_tests(self, node, state):
        """`X is None` / `X is not None` (X from next(reader, None)) -> the flag."""
        if not state.none_vars:
            return node
        lower = self

        class Tests(ast.NodeTransformer):
            def visit_Compare(self, c):
                self.generic_visit(c)
                if (len(c.ops) == 1 and isinstance(c.left, ast.Name) and c.left.id in state.none_vars
                        and isinstance(c.comparators[0], ast.Constant) and c.comparators[0].value is None):
                    flag = _name(state.none_vars[c.left.id])
                    if isinstance(c.ops[0], ast.Is):
                        return ast.copy_location(_mark(ast.UnaryOp(op=ast.Not(), operand=flag)), c)
                    if isinstance(c.ops[0], ast.IsNot):
                        return ast.copy_location(flag, c)
                return c
        return Tests().visit(node)

    # -- writers ----------------------------------------------------------------------------------------------------
    def stringio_names(self):
        """Names the program binds to an io.StringIO (stdlib5 has turned the call into `_AilStringIO(...)`)."""
        if not hasattr(self, '_stringio'):
            self._stringio = {t.id for n in ast.walk(self.tree) if isinstance(n, ast.Assign)
                              and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                              and n.value.func.id == '_AilStringIO' for t in n.targets if isinstance(t, ast.Name)}
        return self._stringio

    def make_writer(self, name, call, kind, s, state):
        if call.args and isinstance(call.args[0], ast.Name) and call.args[0].id in self.stringio_names():
            stream = call.args[0].id            # a StringIO object: the rows are written with its write()
        elif not call.args or not (isinstance(call.args[0], ast.Attribute) and call.args[0].attr in ('stdout', 'stderr')
                                   and isinstance(call.args[0].value, ast.Name) and call.args[0].value.id == 'sys'):
            self.refuse(call, 'csv.%s(...): only sys.stdout / sys.stderr / an io.StringIO are built as the target '
                        '(collect the text and write it, or print the joined fields)' % kind)
        else:
            stream = call.args[0].attr
        positional = ['dialect'] if kind == 'writer' else ['fieldnames', 'restval', 'extrasaction', 'dialect']
        extra = ('fieldnames', 'restval', 'extrasaction') if kind == 'DictWriter' else ()
        d, extras = self.dialect(call, positional, extra=extra)
        if d.quoting == NONNUMERIC:
            self.refuse(call, 'csv.QUOTE_NONNUMERIC is not built for a writer: it quotes str and not numbers '
                        'and this compiler cannot tell them apart here; format the numbers yourself or use '
                        'QUOTE_MINIMAL / QUOTE_ALL')
        w = Writer(name, kind, d, stream)
        if kind == 'DictWriter':
            fieldnames = extras.get('fieldnames')
            if fieldnames is None:
                self.refuse(call, 'csv.DictWriter needs fieldnames')
            if isinstance(fieldnames, ast.Tuple):
                fieldnames = ast.List(elts=fieldnames.elts, ctx=ast.Load())
            if not isinstance(fieldnames, (ast.List, ast.Name)):
                self.refuse(call, 'csv.DictWriter: fieldnames has to be a list display or a list name')
            w.fieldnames = fieldnames
            w.fields = None
            if isinstance(fieldnames, ast.List):
                w.fields = [const_str(e) for e in fieldnames.elts]
                if any(f is None for f in w.fields):
                    w.fields = None
            restval = extras.get('restval')
            if restval is not None and const_str(restval) is None:
                self.refuse(call, 'csv.DictWriter: restval= has to be a string literal')
            w.restval = const_str(restval) if restval is not None else ''
            action = extras.get('extrasaction')
            w.action = const_str(action) if action is not None else 'raise'
            if w.action not in ('raise', 'ignore'):
                self.refuse(call, 'csv.DictWriter: extrasaction= has to be "raise" or "ignore"')
            if self.csv_attr(call) is None:
                pass
            holder = self.fresh('fn')
            w.holder = holder
            state.writers[name] = w
            out = [_mark(ast.Assign(targets=[_name(holder, True)], value=copy.deepcopy(fieldnames)))]
            _locate(out, s)
            return out
        state.writers[name] = w
        return [_mark(ast.Pass())]

    def emit(self, w, fields_expr, node):
        d = w.dialect
        self.helper('join')
        call = _call(_name('_ail_csv_join'), fields_expr, ast.Constant(value=d.delimiter),
                     ast.Constant(value=d.quotechar or ''), ast.Constant(value=d.escapechar or ''),
                     ast.Constant(value=d.lineterminator), ast.Constant(value=d.quoting),
                     ast.Constant(value=d.doublequote))
        if w.stream not in ('stdout', 'stderr'):
            write = ast.Expr(value=ast.Call(func=ast.Attribute(value=_name(w.stream), attr='write', ctx=ast.Load()),
                                            args=[call], keywords=[]))
            _mark(write)
            return write
        # what the surface pass makes of sys.stdout.write(text) / sys.stderr.write(text)
        keywords = [ast.keyword(arg='end', value=ast.Constant(value=''))]
        if w.stream == 'stderr':
            keywords.append(ast.keyword(arg='file', value=ast.Attribute(value=_name('sys'), attr='stderr',
                                                                        ctx=ast.Load())))
        write = ast.Expr(value=ast.Call(func=_name('print'), args=[call], keywords=keywords))
        _mark(write)
        return write

    def str_list(self, node, pre):
        """list[str] of the fields of a row expression: element-wise str() (statements that build it go
        to `pre`)."""
        if isinstance(node, (ast.List, ast.Tuple)):
            elts = []
            for e in node.elts:
                elts.append(self.as_str(e))
            return ast.List(elts=elts, ctx=ast.Load())
        source = self.bind(node, pre)
        cells, var = self.fresh('cells'), self.fresh('f')
        pre.append(_mark(ast.AnnAssign(target=_name(cells, True), annotation=ast.Subscript(
            value=_name('list'), slice=_name('str'), ctx=ast.Load()), value=ast.List(elts=[], ctx=ast.Load()),
            simple=1)))
        pre.append(_mark(ast.For(target=_name(var, True), iter=source, body=[ast.Expr(value=_call(
            ast.Attribute(value=_name(cells), attr='append', ctx=ast.Load()), self.as_str(_name(var))))],
            orelse=[])))
        return _name(cells)

    def as_str(self, e):
        if isinstance(e, ast.Constant):
            if e.value is None:
                return ast.Constant(value='')
            if isinstance(e.value, str):
                return e
        return _mark(ast.JoinedStr(values=[ast.FormattedValue(value=e, conversion=-1, format_spec=None)]))

    def bind(self, expr, pre):
        """A name holding `expr` (a statement ahead binds it unless it is a name already)."""
        if isinstance(expr, ast.Name):
            return expr
        var = self.fresh('v')
        pre.append(_mark(ast.Assign(targets=[_name(var, True)], value=expr)))
        return _name(var)

    def writer_stmt(self, s, state):
        if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
                and isinstance(s.value.func, ast.Attribute) and isinstance(s.value.func.value, ast.Name)
                and s.value.func.value.id in state.writers):
            return None
        call = s.value
        w = state.writers[call.func.value.id]
        method = call.func.attr
        if call.keywords or any(isinstance(a, ast.Starred) for a in call.args):
            self.refuse(call, '%s.%s: keyword and * arguments are not built' % (w.name, method))
        pre, out = [], []
        if w.kind == 'writer':
            if method == 'writerow' and len(call.args) == 1:
                row = self.expr(call.args[0], state, pre)
                fields = self.str_list(row, pre)
                out = pre + [self.emit(w, fields, s)]
            elif method == 'writerows' and len(call.args) == 1:
                rows = self.bind(self.expr(call.args[0], state, pre), pre)
                var, body = self.fresh('r'), []
                fields = self.str_list(_name(var), body)
                body.append(self.emit(w, fields, s))
                out = pre + [_mark(ast.For(target=_name(var, True), iter=rows, body=body, orelse=[]))]
            else:
                self.refuse(call, 'csv.writer: %s is not built (writerow, writerows are)' % method)
        else:
            if method == 'writeheader' and not call.args:
                fields = self.str_list(_name(w.holder), out)
                out.append(self.emit(w, fields, s))
            elif method == 'writerow' and len(call.args) == 1:
                row = self.expr(call.args[0], state, pre)
                out = pre + self.dict_row(w, row, s)
            elif method == 'writerows' and len(call.args) == 1:
                self.refuse(call, 'csv.DictWriter.writerows: a list of dicts is not built; loop and call '
                            'writerow')
            else:
                self.refuse(call, 'csv.DictWriter: %s is not built (writeheader, writerow are)' % method)
        _locate(out, s)
        return out

    def dict_row(self, w, row, s):
        """DictWriter.writerow(d): the row is [d.get(f, restval) for f in fieldnames]; a dict display with
        literal keys is resolved here, a dict name is read with `in` / []."""
        fields = w.fields
        if isinstance(row, ast.Dict) and fields is not None and all(const_str(k) is not None for k in row.keys if k):
            keys = [const_str(k) for k in row.keys]
            if w.action == 'raise':
                extra = [k for k in keys if k not in fields]
                if extra:
                    return [_mark(ast.Raise(exc=_call(_name('ValueError'), ast.Constant(
                        value='dict contains fields not in fieldnames: ' + ', '.join(repr(k) for k in extra))),
                        cause=None))]
            last = {}
            for key, value in zip(keys, row.values):
                last[key] = value
            elts = []
            for f in fields:
                if f in last:
                    elts.append(self.as_str(last[f]))
                else:
                    elts.append(ast.Constant(value=w.restval))
            return [self.emit(w, ast.List(elts=elts, ctx=ast.Load()), s)]
        if not isinstance(row, ast.Name):
            self.refuse(s, 'csv.DictWriter.writerow: the row has to be a dict display with literal keys or a '
                        'dict held in a variable')
        out = []
        var = self.fresh('k')
        pieces = _mark(ast.ListComp(
            elt=ast.IfExp(test=ast.Compare(left=_name(var), ops=[ast.In()], comparators=[copy.deepcopy(row)]),
                          body=self.as_str(ast.Subscript(value=copy.deepcopy(row), slice=_name(var),
                                                         ctx=ast.Load())),
                          orelse=ast.Constant(value=w.restval)),
            generators=[ast.comprehension(target=_name(var, True), iter=_name(w.holder), ifs=[], is_async=0)]))
        if w.action == 'raise':
            bad = self.fresh('x')
            out.append(_mark(ast.For(target=_name(bad, True), iter=copy.deepcopy(row), body=[ast.If(
                test=ast.Compare(left=_name(bad), ops=[ast.NotIn()], comparators=[_name(w.holder)]),
                body=[ast.Raise(exc=_call(_name('ValueError'), ast.BinOp(
                    left=ast.Constant(value='dict contains fields not in fieldnames: '), op=ast.Add(),
                    right=_call(_name('repr'), _name(bad)))), cause=None)], orelse=[])], orelse=[])))
        out.append(self.emit(w, pieces, s))
        return out


class Reader:
    def __init__(self, name, kind, pos, hdr, errs, count):
        self.name, self.kind, self.pos, self.hdr, self.errs, self.count = name, kind, pos, hdr, errs, count


class Writer:
    def __init__(self, name, kind, dialect, stream):
        self.name, self.kind, self.dialect, self.stream = name, kind, dialect, stream


class Scope:
    def __init__(self, owner):
        self.owner = owner
        self.readers = {}
        self.writers = {}
        self.none_vars = {}


class RowUses(ast.NodeVisitor):
    """How the row variable of a DictReader loop is used: only as row[k], row.get(k, d), k in row."""

    def __init__(self, name):
        self.name = name
        self.other = False
        self.bound = False
        self.ok_nodes = set()

    def visit(self, node):
        # first mark the recognised uses, then flag every other Name use
        for each in ast.walk(node):
            if isinstance(each, ast.Subscript) and isinstance(each.value, ast.Name) and each.value.id == self.name \
                    and isinstance(each.ctx, ast.Load) and not isinstance(each.slice, ast.Slice):
                self.ok_nodes.add(id(each.value))
            elif isinstance(each, ast.Call) and isinstance(each.func, ast.Attribute) \
                    and isinstance(each.func.value, ast.Name) and each.func.value.id == self.name \
                    and each.func.attr == 'get' and len(each.args) == 2 and not each.keywords:
                self.ok_nodes.add(id(each.func.value))
            elif isinstance(each, ast.Compare) and len(each.ops) == 1 and isinstance(each.ops[0], (ast.In, ast.NotIn)) \
                    and isinstance(each.comparators[0], ast.Name) and each.comparators[0].id == self.name:
                self.ok_nodes.add(id(each.comparators[0]))
        for each in ast.walk(node):
            if isinstance(each, ast.Name) and each.id == self.name:
                if not isinstance(each.ctx, ast.Load):
                    self.bound = True
                elif id(each) not in self.ok_nodes:
                    self.other = True
            elif isinstance(each, ast.arg) and each.arg == self.name:
                self.bound = True


class RowRewrite(ast.NodeTransformer):
    def __init__(self, name, hdr, cells):
        self.name, self.hdr, self.cells = name, hdr, cells

    def row(self, node):
        return isinstance(node, ast.Name) and node.id == self.name

    def visit_Subscript(self, node):
        self.generic_visit(node)
        if self.row(node.value) and isinstance(node.ctx, ast.Load) and not isinstance(node.slice, ast.Slice):
            return ast.copy_location(_mark(_call(_name('_ail_csv_col'), _name(self.hdr), _name(self.cells),
                                                 node.slice)), node)
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Attribute) and self.row(node.func.value) and node.func.attr == 'get' \
                and len(node.args) == 2:
            return ast.copy_location(_mark(_call(_name('_ail_csv_colget'), _name(self.hdr), _name(self.cells),
                                                 node.args[0], node.args[1])), node)
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)) and self.row(node.comparators[0]):
            test = _mark(_call(_name('_ail_csv_has'), _name(self.hdr), node.left))
            if isinstance(node.ops[0], ast.NotIn):
                test = _mark(ast.UnaryOp(op=ast.Not(), operand=test))
            return ast.copy_location(test, node)
        return node


class _SubstName(ast.NodeTransformer):
    def __init__(self, name, replacement):
        self.name, self.replacement = name, replacement

    def visit_Name(self, node):
        if node.id == self.name and isinstance(node.ctx, ast.Load):
            return copy.deepcopy(self.replacement)
        return node
