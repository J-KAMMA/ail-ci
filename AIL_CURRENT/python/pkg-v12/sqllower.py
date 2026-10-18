# -*- coding: utf-8 -*-
"""sqllower.py -- stage G11: the sqlite3 module (docs/design/GENERAL_PURPOSE.md, plan row G5b).

A source-to-source pass in the manner of stdlib4.rewrite_text: `ail_syntax.python_surface` calls `rewrite_text` FIRST, before the
tuple and Optional passes (which work on the text and would otherwise rewrite the `tuple[...]` / `Optional[...]` annotations in
which the program declares its row shapes), parses the program, lowers it and unparses it. A program that does not import sqlite3
comes back as the same string. A connection and a cursor are int handles of ailsql_core.h (so they pass, are stored and returned
like any int); the pass decides from the program text which calls are sqlite3 calls (the method names `execute`, `executemany`,
`executescript`, `cursor`, `commit`, `rollback`, `fetchone`, `fetchall` mean nothing else in a program that imports sqlite3, and
`close` is taken for sqlite3 when its receiver is a name or attribute that holds a connection or a cursor) and lowers

  * `sqlite3.connect(path[, isolation_level=...])`  onto `_ail_sq_open`;
  * `X.execute(sql[, params])`, `X.executescript(sql)`, `X.cursor()` onto ONE nested expression of the
    primitives (`_ail_sq_exec(_ail_sq_bind(_ail_sq_prep(X, sql), p0))` ...): every bind returns the cursor,
    and the type of a bound value picks `bi / bf / bs / bb` in pyfunc (`None` is `bn`), because this pass
    does not know the type of an expression. Parameters are a tuple/list display, a dict display (named
    placeholders), or a name that holds a sequence (indexed with constants up to the placeholder count of a
    literal SQL text);
  * `X.executemany(sql, rows)` (a statement) onto a prepare, one implicit BEGIN and a loop of binds;
  * `X.commit()`, `X.rollback()`, `X.close()`, `c.rowcount`, `c.lastrowid`, `conn.in_transaction`,
    `conn.total_changes`;
  * `with conn:` onto `try / finally` that commits (or rolls back when the body raised);
  * `except sqlite3.Error / IntegrityError / ...` onto the exception codes 19..27 of the typed runtime;
  * the rows. SQLite rows have no static type, and this language has no `Any`, so the shape of a row is
    DECLARED by the program, in annotations that CPython ignores:

        rows: list[tuple[int, str, float]] = cur.fetchall()
        row: tuple[int, str] | None = cur.fetchone()
        n = cast(tuple[int], cur.fetchone())[0]
        pk: int
        name: Optional[str]
        for pk, name in conn.execute("select id, name from t"): ...

    A row of plain int / float / str columns is an ordinary tuple. A shape with a nullable column
    (`Optional[T]`, `T | None`) or a `bytes` column is a generated class (the typed path has no None or
    bytes inside tuples) whose indexing, unpacking, `is None` tests and printing are lowered here. The
    runtime checks every column against its declaration (RuntimeError on a mismatch).

Whatever the pass does not build is refused by name with a `write instead:` line. A program that does not
import sqlite3 is not touched, so its C stays byte for byte what it was.
"""
import ast
import copy
import os

import iterlower

# name -> (result kind, argument kinds); kinds in {'int', 'float', 'str', 'bytes'} ('any' for bind: pyfunc
# picks the primitive by the static type of the value).  The C behind them is ailsql_core.h (typed adapters
# in filert.py).  A connection or a cursor is an int handle.
SQLP = {
    '_ail_sq_open': ('int', ('str', 'int')),          # path, isolation level (-1 None, 0 "", 1 DEFERRED, 2 IMMEDIATE, 3 EXCLUSIVE)
    '_ail_sq_close': ('int', ('int',)),
    '_ail_sq_commit': ('int', ('int',)),
    '_ail_sq_rollback': ('int', ('int',)),
    '_ail_sq_cursor': ('int', ('int',)),
    '_ail_sq_prep': ('int', ('int', 'str')),          # connection -> new cursor, cursor -> reused; returns the cursor
    '_ail_sq_named': ('int', ('int',)),               # the parameters come as a dict (even an empty one)
    '_ail_sq_name': ('int', ('int', 'str')),          # the next bound value goes to this name; returns the cursor
    '_ail_sq_bi': ('int', ('int', 'int')),            # bind: return the cursor, so binds nest as one expression
    '_ail_sq_bf': ('int', ('int', 'float')),
    '_ail_sq_bs': ('int', ('int', 'str')),
    '_ail_sq_bb': ('int', ('int', 'bytes')),
    '_ail_sq_bn': ('int', ('int',)),
    '_ail_sq_bind': ('int', ('int', 'any')),          # bi / bf / bs / bb by the static type of the value (pyfunc)
    '_ail_sq_exec': ('int', ('int',)),
    '_ail_sq_mbegin': ('int', ('int',)),
    '_ail_sq_mrow': ('int', ('int',)),
    '_ail_sq_mstep': ('int', ('int',)),
    '_ail_sq_mend': ('int', ('int',)),
    '_ail_sq_script': ('int', ('int', 'str')),
    '_ail_sq_next': ('int', ('int',)),
    '_ail_sq_cols': ('int', ('int', 'int')),
    '_ail_sq_isnull': ('int', ('int', 'int')),
    '_ail_sq_ci': ('int', ('int', 'int')),
    '_ail_sq_cf': ('float', ('int', 'int')),
    '_ail_sq_cs': ('str', ('int', 'int')),
    '_ail_sq_cb': ('bytes', ('int', 'int')),
    '_ail_sq_rowcount': ('int', ('int',)),
    '_ail_sq_lastrowid': ('int', ('int',)),
    '_ail_sq_haslast': ('int', ('int',)),             # whether lastrowid is an int (a cursor that never ran execute() reads None)
    '_ail_sq_lastshow': ('str', ('int',)),            # lastrowid as print() shows it: None or the number
    '_ail_sq_intx': ('int', ('int',)),
    '_ail_sq_total': ('int', ('int',)),
    '_ail_sq_free': ('int', ('int',)),
    '_ail_sq_drop': ('int', ('int',)),                # free the cursor of `conn.execute(...)` that nobody holds (a held one is left alone)
    '_ail_sq_blen': ('int', ('int', 'int')),          # a parameter sequence of this length: ProgrammingError unless it matches
    '_ail_sq_reprb': ('str', ('bytes',)),
}

ACTIVE = False        # set once a program that uses sqlite3 has been lowered (pyfunc lists the sqlite3 exceptions then)


class SqlRefusal(ValueError):
    """A named refusal; it carries the position of the construct like the other front-end refusals."""

BUILT = ('connect(path, isolation_level=), execute / executemany / executescript with qmark or named '
         'parameters, cursor, commit, rollback, close, with conn:, fetchone, fetchall, iterating a cursor, '
         'rowcount, lastrowid, in_transaction, total_changes, Error and its subclasses')

_EXC = {'Error', 'DatabaseError', 'OperationalError', 'IntegrityError', 'ProgrammingError', 'InterfaceError',
        'DataError', 'InternalError', 'NotSupportedError'}
_TYPES = {'Connection', 'Cursor'}
_PRIM_ATTRS = {'connect', 'Connection', 'Cursor'} | _EXC
_ISO = {None: -1, '': 0, 'DEFERRED': 1, 'IMMEDIATE': 2, 'EXCLUSIVE': 3}

_MODULE_REFUSED = {
    'Row': 'row_factory and sqlite3.Row are not built\n  write instead: plain tuples, with the shape declared '
           '(rows: list[tuple[int, str]] = cur.fetchall())',
    'register_adapter': 'adapters are not built\n  write instead: convert the value yourself before you bind it',
    'register_converter': 'converters are not built\n  write instead: convert the column yourself after you read it',
    'PARSE_DECLTYPES': 'detect_types is not built', 'PARSE_COLNAMES': 'detect_types is not built',
    'Binary': 'sqlite3.Binary is not built\n  write instead: bytes(...)',
    'Date': 'the date/time adapters are not built\n  write instead: str(...) of the value, bound as text',
    'Time': 'the date/time adapters are not built\n  write instead: str(...) of the value, bound as text',
    'Timestamp': 'the date/time adapters are not built\n  write instead: str(...) of the value, bound as text',
    'Warning': 'sqlite3.Warning is not built',
    'version': 'sqlite3.version is not built', 'sqlite_version': 'sqlite3.sqlite_version is not built',
    'version_info': 'sqlite3.version_info is not built', 'sqlite_version_info': 'sqlite3.sqlite_version_info is not built',
    'complete_statement': 'sqlite3.complete_statement is not built',
    'enable_callback_tracebacks': 'callbacks are not built', 'enable_shared_cache': 'shared cache is not built',
    'SQLITE_OK': 'the SQLITE_ constants are not built',
}
_METHOD_REFUSED = {
    'fetchmany': 'fetchmany is not built\n  write instead: fetchall(), or fetchone() in a loop',
    'create_function': 'user-defined SQL functions are not built\n  write instead: compute in your program after you read the rows',
    'create_aggregate': 'user-defined aggregates are not built\n  write instead: compute in your program after you read the rows',
    'create_window_function': 'user-defined window functions are not built',
    'create_collation': 'collations are not built', 'set_authorizer': 'authorizers are not built',
    'set_progress_handler': 'progress handlers are not built', 'set_trace_callback': 'trace callbacks are not built',
    'iterdump': 'iterdump is not built\n  write instead: select the rows and write them yourself',
    'backup': 'backup is not built', 'interrupt': 'interrupt is not built', 'blobopen': 'blobs are read as bytes columns',
    'enable_load_extension': 'extensions are not built', 'load_extension': 'extensions are not built',
    'setinputsizes': 'setinputsizes is a no-op in CPython; leave it out', 'setoutputsize': 'setoutputsize is a no-op in CPython; leave it out',
    'getlimit': 'limits are not built', 'setlimit': 'limits are not built', 'serialize': 'serialize is not built',
    'deserialize': 'deserialize is not built', 'getconfig': 'not built', 'setconfig': 'not built',
}
_ATTR_REFUSED = {
    'row_factory': 'row_factory is not built\n  write instead: plain tuples, with the shape declared '
                   '(rows: list[tuple[int, str]] = cur.fetchall())',
    'text_factory': 'text_factory is not built', 'isolation_level': 'isolation_level can only be given to connect()\n'
                    '  write instead: sqlite3.connect(path, isolation_level=None)',
    'description': 'cursor.description is not built\n  write instead: name the columns in your SELECT, or '
                   'select name from pragma_table_info(\'t\')',
    'arraysize': 'arraysize is not built', 'connection': 'cursor.connection is not built\n  write instead: keep the connection in a variable',
    'autocommit': 'the autocommit attribute (3.12) is not built\n  write instead: sqlite3.connect(path, isolation_level=None)',
    'sqlite_errorcode': 'sqlite_errorcode is not built', 'sqlite_errorname': 'sqlite_errorname is not built',
}
_CONNECT_KW_REFUSED = {
    'timeout': 'timeout= is not built (the busy timeout is the default, 5 seconds)',
    'detect_types': 'detect_types= is not built', 'check_same_thread': 'check_same_thread= is not built',
    'factory': 'factory= is not built', 'cached_statements': 'cached_statements= is not built',
    'uri': 'uri= is not built', 'autocommit': 'autocommit= (3.12) is not built\n  write instead: isolation_level=None',
}

_SCALARS = {'int': 'i', 'float': 'f', 'str': 's', 'bytes': 'b'}
_SCALAR_NAMES = {'i': 'int', 'f': 'float', 's': 'str', 'b': 'bytes'}


class _Shape:
    """The declared columns of a row: a tuple of (letter, nullable)."""

    def __init__(self, cols):
        self.cols = tuple(cols)
        self.sig = ''.join(c.upper() if null else c for c, null in self.cols)
        # a plain tuple holds int / float / str; a nullable or bytes column needs the generated class
        self.native = all(not null and c != 'b' for c, null in self.cols)

    def __len__(self):
        return len(self.cols)

    def tuple_text(self):
        return 'tuple[%s]' % ', '.join(_SCALAR_NAMES[c] if not null else 'Optional[%s]' % _SCALAR_NAMES[c]
                                       for c, null in self.cols)

    def py_type(self):
        """The annotation text of one row as the compiler gets it."""
        if self.native:
            return 'tuple[%s]' % ', '.join(_SCALAR_NAMES[c] for c, _ in self.cols)
        return '_AilSqRow_' + self.sig


class _Scope:
    def __init__(self, parent, node=None):
        self.parent = parent
        self.node = node
        self.kinds = {}         # name -> 'conn' | 'cur'
        self.decl = {}          # name -> (rk, shape): rk in 'row' 'rows' 'orow'
        self.ret = None         # the declared return shape of the function: (rk, shape)
        self.ret_kind = None

    def find(self, table, name):
        s = self
        while s is not None:
            if name in getattr(s, table):
                return getattr(s, table)[name]
            s = s.parent
        return None


def _is_none(node):
    return isinstance(node, ast.Constant) and node.value is None


def count_params(sql):
    """The number of parameters SQLite finds in a literal SQL text (bare ? and ?NNN, :name @name $name)."""
    n = 0                       # largest index
    names = {}
    i, size = 0, len(sql)
    while i < size:
        c = sql[i]
        if c in '\'"`':
            j = sql.find(c, i + 1)
            while j != -1 and j + 1 < size and sql[j + 1] == c:
                j = sql.find(c, j + 2)
            i = size if j == -1 else j + 1
        elif c == '[':
            j = sql.find(']', i + 1)
            i = size if j == -1 else j + 1
        elif c == '-' and sql.startswith('--', i):
            j = sql.find('\n', i)
            i = size if j == -1 else j + 1
        elif c == '/' and sql.startswith('/*', i):
            j = sql.find('*/', i + 2)
            i = size if j == -1 else j + 2
        elif c == '?':
            j = i + 1
            while j < size and sql[j].isdigit():
                j += 1
            n = max(n, int(sql[i + 1:j])) if j > i + 1 else n + 1
            i = j
        elif c in ':@$':
            j = i + 1
            while j < size and (sql[j].isalnum() or sql[j] in '_$'):
                j += 1
            if j > i + 1:
                name = sql[i:j]
                if name not in names:
                    n += 1
                    names[name] = n
            i = max(j, i + 1)
        else:
            i += 1
    return n


class _Lowerer(ast.NodeTransformer):
    def __init__(self, tree, Unsupported, general=False):
        self.tree = tree
        self.U = Unsupported
        self.general = general
        self.mod_names = set()          # local names of the module sqlite3
        self.from_names = {}            # local name -> attribute of sqlite3 it was imported as
        self.cast_names = set()         # local names of typing.cast
        self.typing_names = set()
        self.import_nodes = []
        self.user_defs = set()
        self.user_methods = set()        # names of methods the program defines in its own classes
        self.used = False
        self.shapes = {}                # sig -> _Shape
        self.helpers = {}               # helper name -> list of ast statements, in order of first need
        self.classes = {}
        self.counter = 0
        self.scope = None
        self.scopes = {}                # id(FunctionDef) -> _Scope
        self.module_scope = _Scope(None)
        self.attr_kinds = {}            # attribute name -> 'conn' | 'cur'
        self.func_kinds = {}            # function name -> 'conn' | 'cur' (return annotation)
        self.exc_ok = False

    # ---- helpers ---------------------------------------------------------------------------
    def refuse(self, node, text):
        if 'write instead:' not in text:
            text += '\n  write instead: use what is built: ' + BUILT
        error = self.U(text)
        error.source_line = getattr(node, 'lineno', None) or 1
        error.source_column = getattr(node, 'col_offset', 0) or 0
        raise error

    @staticmethod
    def N(id_, store=False):
        return iterlower._name(id_, store)

    @staticmethod
    def C(value):
        return ast.Constant(value=value)

    def call(self, func, *args):
        if isinstance(func, str):
            func = self.N(func)
        return ast.Call(func=func, args=list(args), keywords=[])

    def at(self, node, origin):
        if origin is None:
            return node
        for each in ast.walk(node):
            if 'lineno' in getattr(each, '_attributes', ()):
                if not hasattr(each, 'lineno'):
                    ast.copy_location(each, origin)
        return node

    def temp(self):
        self.counter += 1
        return '_ail_sq_t%d' % self.counter

    @staticmethod
    def uc(name):
        if name.startswith('__ail_checked_') and name.endswith('__'):
            return name[len('__ail_checked_'):-2]
        if name == '__ail_checked_list':
            return 'list'
        return name

    # ---- imports ---------------------------------------------------------------------------
    def scan(self):
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in self.tree.body:
                names = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
                if any(n and n.split('.')[0] == 'sqlite3' for n in names):
                    self.refuse(node, 'import sqlite3 at the top of the file, not inside a function or block')
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'sqlite3':
                        self.mod_names.add(alias.asname or 'sqlite3')
                        self.import_nodes.append(node)
                    elif alias.name.startswith('sqlite3.'):
                        self.refuse(node, 'import %s is not built' % alias.name)
                    elif alias.name == 'typing':
                        self.typing_names.add(alias.asname or 'typing')
            elif isinstance(node, ast.ImportFrom) and not node.level:
                if node.module == 'sqlite3':
                    for alias in node.names:
                        if alias.name == '*':
                            self.refuse(node, 'from sqlite3 import *: name what you use')
                        if alias.name in _MODULE_REFUSED:
                            self.refuse(node, 'sqlite3.%s: %s' % (alias.name, _MODULE_REFUSED[alias.name]))
                        if alias.name not in _PRIM_ATTRS:
                            self.refuse(node, 'sqlite3.%s is not built.' % alias.name)
                        self.from_names[alias.asname or alias.name] = alias.name
                    self.import_nodes.append(node)
                elif node.module == 'sqlite3.dbapi2':
                    self.refuse(node, 'sqlite3.dbapi2 is not built')
                elif node.module == 'typing':
                    for alias in node.names:
                        if alias.name == 'cast':
                            self.cast_names.add(alias.asname or 'cast')
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.user_defs.add(node.name)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.user_methods.add(member.name)
        return bool(self.mod_names or self.from_names)

    def ours(self, name, recv):
        """Whether `recv.name(...)` is a sqlite3 call: the name means nothing else unless the program has a method of
        that name, and then the receiver has to be known to hold a connection or a cursor."""
        return name not in self.user_methods or self.kind_of(recv) is not None

    def sq_attr(self, node):
        """The sqlite3 attribute a Name / Attribute denotes (`connect`, `Error`, ...), else None."""
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in self.mod_names:
            return node.attr
        if isinstance(node, ast.Name) and node.id in self.from_names:
            return self.from_names[node.id]
        return None

    def is_cast(self, func):
        # (typing imports are dropped by an earlier pass, so the name is all there is to go by)
        if isinstance(func, ast.Name):
            return func.id == 'cast' and 'cast' not in self.user_defs or func.id in self.cast_names
        return isinstance(func, ast.Attribute) and func.attr == 'cast' and isinstance(func.value, ast.Name)             and func.value.id in ('typing', 't') | self.typing_names

    # ---- annotations -----------------------------------------------------------------------
    def col_of(self, ann):
        """(letter, nullable) of one column annotation, or None."""
        if isinstance(ann, ast.Name):
            letter = _SCALARS.get(self.uc(ann.id))
            return (letter, False) if letter else None
        if isinstance(ann, ast.Subscript):
            head = ann.value
            if (isinstance(head, ast.Name) and head.id == 'Optional') or (
                    isinstance(head, ast.Attribute) and head.attr == 'Optional'):
                inner = self.col_of(ann.slice)
                return (inner[0], True) if inner and not inner[1] else None
        if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
            if _is_none(ann.right):
                inner = self.col_of(ann.left)
            elif _is_none(ann.left):
                inner = self.col_of(ann.right)
            else:
                return None
            return (inner[0], True) if inner and not inner[1] else None
        return None

    def tuple_of(self, ann):
        """The _Shape of `tuple[T0, T1, ...]` / `Tuple[...]`, or None."""
        if not isinstance(ann, ast.Subscript):
            return None
        head = ann.value
        name = head.id if isinstance(head, ast.Name) else head.attr if isinstance(head, ast.Attribute) else None
        if name is None or self.uc(name) not in ('tuple', 'Tuple'):
            return None
        elts = ann.slice.elts if isinstance(ann.slice, ast.Tuple) else [ann.slice]
        cols = []
        for e in elts:
            col = self.col_of(e)
            if col is None:
                return None
            cols.append(col)
        return self.shape(cols)

    def shape(self, cols):
        s = _Shape(cols)
        return self.shapes.setdefault(s.sig, s)

    def decl_of(self, ann):
        """(rk, shape) when `ann` declares a row ('row'), a list of rows ('rows') or an optional row ('orow')."""
        if ann is None:
            return None
        shape = self.tuple_of(ann)
        if shape is not None:
            return ('row', shape)
        if isinstance(ann, ast.Subscript):
            head = ann.value
            name = head.id if isinstance(head, ast.Name) else head.attr if isinstance(head, ast.Attribute) else None
            if name is not None and self.uc(name) in ('list', 'List'):
                shape = self.tuple_of(ann.slice)
                if shape is not None:
                    return ('rows', shape)
            if name == 'Optional':
                shape = self.tuple_of(ann.slice)
                if shape is not None:
                    return ('orow', shape)
        if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
            if _is_none(ann.right):
                shape = self.tuple_of(ann.left)
            elif _is_none(ann.left):
                shape = self.tuple_of(ann.right)
            else:
                shape = None
            if shape is not None:
                return ('orow', shape)
        return None

    def handle_kind(self, ann):
        """'conn' / 'cur' when `ann` is sqlite3.Connection / sqlite3.Cursor."""
        attr = self.sq_attr(ann)
        if attr == 'Connection':
            return 'conn'
        if attr == 'Cursor':
            return 'cur'
        return None

    def ann_text(self, rk, shape):
        t = shape.py_type()
        if rk == 'row':
            return t
        if rk == 'rows':
            return 'list[%s]' % t
        return '%s | None' % t

    def fix_ann(self, ann):
        """The annotation as the compiler should get it: handles are int, a non-native row is its class."""
        if ann is None:
            return None
        if self.handle_kind(ann):
            self.used = True
            return self.at(self.N('int'), ann)
        d = self.decl_of(ann)
        if d is not None:
            rk, shape = d
            if shape.native:
                # a plain tuple shape keeps its annotation (minus the Optional spelling of nothing)
                return ann
            self.need_row_class(shape)
            self.used = True
            return self.at(ast.parse(self.ann_text(rk, shape), mode='eval').body, ann)
        # containers of handles: list[sqlite3.Connection], Optional[...] and the like
        if isinstance(ann, ast.Subscript):
            ann.slice = self.fix_ann(ann.slice)
        elif isinstance(ann, ast.BinOp):
            ann.left = self.fix_ann(ann.left)
            ann.right = self.fix_ann(ann.right)
        elif isinstance(ann, ast.Tuple):
            ann.elts = [self.fix_ann(e) for e in ann.elts]
        return ann

    # ---- scopes and kinds ------------------------------------------------------------------
    def build_scopes(self):
        """One _Scope per function (and the module), with the kinds of the names that hold handles and the
        shapes the program declares for its names."""
        records = []                       # (scope, key, value expr), key = ('name', id) | ('attr', id)

        def walk(body, scope):
            for stmt in body:
                for node in self.statements(stmt):
                    self.record(node, scope, records)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        inner = _Scope(scope, node)
                        self.scopes[id(node)] = inner
                        for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                            self.declare(inner, a.arg, a.annotation)
                        if node.returns is not None:
                            k = self.handle_kind(node.returns)
                            if k:
                                self.func_kinds[node.name] = k
                            inner.ret = self.decl_of(node.returns)
                        walk(node.body, inner)
                    elif isinstance(node, ast.ClassDef):
                        walk(node.body, scope)

        walk(self.tree.body, self.module_scope)
        changed = True
        while changed:
            changed = False
            for scope, key, value in records:
                kind = self.kind_of(value, scope)
                if kind is None:
                    continue
                if key[0] == 'name':
                    if key[1] not in scope.kinds:
                        scope.kinds[key[1]] = kind
                        changed = True
                elif key[1] not in self.attr_kinds:
                    self.attr_kinds[key[1]] = kind
                    changed = True

    def statements(self, stmt):
        """`stmt` and every statement nested in it that belongs to the same scope."""
        out = [stmt]
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return out
        for field in ('body', 'orelse', 'finalbody'):
            for child in getattr(stmt, field, []) or []:
                out.extend(self.statements(child))
        for h in getattr(stmt, 'handlers', []) or []:
            for child in h.body:
                out.extend(self.statements(child))
        return out

    def declare(self, scope, name, ann):
        k = self.handle_kind(ann) if ann is not None else None
        if k:
            scope.kinds[name] = k
        d = self.decl_of(ann)
        if d is not None:
            scope.decl[name] = d

    def record(self, node, scope, records):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    records.append((scope, ('name', t.id), node.value))
                elif isinstance(t, ast.Attribute):
                    records.append((scope, ('attr', t.attr), node.value))
        elif isinstance(node, ast.AnnAssign):
            t = node.target
            if isinstance(t, ast.Name):
                self.declare(scope, t.id, node.annotation)
                if node.value is not None:
                    records.append((scope, ('name', t.id), node.value))
            elif isinstance(t, ast.Attribute):
                k = self.handle_kind(node.annotation)
                if k:
                    self.attr_kinds[t.attr] = k
                if node.value is not None:
                    records.append((scope, ('attr', t.attr), node.value))
        elif isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name):
                    records.append((scope, ('name', item.optional_vars.id), item.context_expr))
        elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            pass

    def kind_of(self, e, scope=None):
        """'conn' / 'cur' when the expression holds a connection / a cursor, else None."""
        scope = scope or self.scope
        if isinstance(e, ast.Call):
            f = e.func
            attr = self.sq_attr(f)
            if attr == 'connect':
                return 'conn'
            if isinstance(f, ast.Attribute):
                if f.attr == 'cursor':
                    return 'cur'
                if f.attr in ('execute', 'executemany', 'executescript'):
                    return 'cur'
            if isinstance(f, ast.Name) and f.id in self.func_kinds and f.id not in self.from_names:
                return self.func_kinds[f.id]
            return None
        if isinstance(e, ast.Name):
            found = scope.find('kinds', e.id) if scope is not None else None
            return found
        if isinstance(e, ast.Attribute):
            return self.attr_kinds.get(e.attr)
        if isinstance(e, ast.IfExp):
            a, b = self.kind_of(e.body, scope), self.kind_of(e.orelse, scope)
            return a if a == b else None
        return None

    def is_temp_cursor(self, e):
        """A cursor that is the result of a call (`conn.execute(...)`, used at once): the caller drops it after use."""
        return (isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute)
                and e.func.attr in ('execute', 'executescript') and self.ours(e.func.attr, e.func.value))

    # ---- row classes and helper functions --------------------------------------------------
    def need_row_class(self, shape):
        key = '_AilSqRow_' + shape.sig
        if key in self.classes:
            return key
        args = ['self']
        body = []
        for k, (letter, null) in enumerate(shape.cols):
            args.append('c%d: %s' % (k, _SCALAR_NAMES[letter]))
            body.append('self.c%d = c%d' % (k, k))
            if null:
                args.append('n%d: bool' % k)
                body.append('self.n%d = n%d' % (k, k))
        text = 'class %s:\n    def __init__(%s):\n%s\n' % (key, ', '.join(args), '\n'.join('        ' + b for b in body))
        self.classes[key] = ast.parse(text).body
        return key

    def helper(self, name, text):
        if name not in self.helpers:
            self.helpers[name] = ast.parse(text).body
        return name

    def row_fn(self, shape):
        """The function that reads the current row of a cursor as one row of `shape`."""
        name = '_ail_sq_row_' + shape.sig
        if name in self.helpers:
            return name
        n = len(shape)
        lines = []
        if shape.native:
            lines.append('def %s(c: int) -> %s:' % (name, shape.py_type()))
            lines.append('    _ail_sq_cols(c, %d)' % n)
            for k, (letter, _) in enumerate(shape.cols):
                lines.append('    v%d: %s = _ail_sq_c%s(c, %d)' % (k, _SCALAR_NAMES[letter], letter, k))
            lines.append('    return (%s%s)' % (', '.join('v%d' % k for k in range(n)), ',' if n == 1 else ''))
        else:
            cls = self.need_row_class(shape)
            lines.append('def %s(c: int) -> %s:' % (name, cls))
            lines.append('    _ail_sq_cols(c, %d)' % n)
            args = []
            for k, (letter, null) in enumerate(shape.cols):
                t = _SCALAR_NAMES[letter]
                zero = {'i': '0', 'f': '0.0', 's': '""', 'b': 'b""'}[letter]
                if null:
                    lines.append('    n%d: bool = _ail_sq_isnull(c, %d) != 0' % (k, k))
                    lines.append('    v%d: %s = %s' % (k, t, zero))
                    lines.append('    if not n%d:' % k)
                    lines.append('        v%d = _ail_sq_c%s(c, %d)' % (k, letter, k))
                    args.extend(['v%d' % k, 'n%d' % k])
                else:
                    lines.append('    v%d: %s = _ail_sq_c%s(c, %d)' % (k, t, letter, k))
                    args.append('v%d' % k)
            lines.append('    return %s(%s)' % (cls, ', '.join(args)))
        return self.helper(name, '\n'.join(lines) + '\n')

    def all_fn(self, shape):
        name = '_ail_sq_all_' + shape.sig
        if name in self.helpers:
            return name
        row = self.row_fn(shape)
        t = shape.py_type()
        text = ('def %s(c: int, free: int) -> list[%s]:\n    out: list[%s] = []\n    while _ail_sq_next(c) > 0:\n'
                '        out.append(%s(c))\n    if free != 0:\n        _ail_sq_drop(c)\n    return out\n') % (name, t, t, row)
        return self.helper(name, text)

    def one_fn(self, shape, strict):
        name = '_ail_sq_%s_%s' % ('one1' if strict else 'one', shape.sig)
        if name in self.helpers:
            return name
        row = self.row_fn(shape)
        t = shape.py_type()
        if strict:
            text = ('def %s(c: int, free: int) -> %s:\n    if _ail_sq_next(c) > 0:\n        r = %s(c)\n'
                    '        if free != 0:\n            _ail_sq_drop(c)\n        return r\n'
                    '    if free != 0:\n        _ail_sq_drop(c)\n'
                    '    raise RuntimeError("sqlite3: fetchone() found no row; declare the result Optional "'
                    '"(row: tuple[...] | None = cur.fetchone())")\n') % (name, t, row)
        else:
            text = ('def %s(c: int, free: int) -> %s | None:\n    if _ail_sq_next(c) > 0:\n        r = %s(c)\n'
                    '        if free != 0:\n            _ail_sq_drop(c)\n        return r\n'
                    '    if free != 0:\n        _ail_sq_drop(c)\n    return None\n') % (name, t, row)
        return self.helper(name, text)

    def col_fn(self, letter):
        """An Optional reader of one column (int / float / str): None for a NULL."""
        t = _SCALAR_NAMES[letter]
        name = '_ail_sq_o' + letter
        text = ('def %s(c: int, i: int) -> %s | None:\n    if _ail_sq_isnull(c, i) != 0:\n        return None\n'
                '    v: %s = _ail_sq_c%s(c, i)\n    return v\n') % (name, t, t, letter)
        return self.helper(name, text)

    def get_fn(self, shape, k):
        """The Optional accessor of nullable column k of a row class."""
        letter = shape.cols[k][0]
        name = '_ail_sq_get_%s_%d' % (shape.sig, k)
        cls = self.need_row_class(shape)
        t = _SCALAR_NAMES[letter]
        text = ('def %s(r: %s) -> %s | None:\n    if r.n%d:\n        return None\n    v: %s = r.c%d\n    return v\n'
                % (name, cls, t, k, t, k))
        return self.helper(name, text)

    def repr_fn(self, shape, many):
        cls = self.need_row_class(shape)
        one = '_ail_sq_repr_' + shape.sig
        if one not in self.helpers:
            lines = ['def %s(r: %s) -> str:' % (one, cls), '    out: str = "("']
            for k, (letter, null) in enumerate(shape.cols):
                v = 'r.c%d' % k
                shown = {'i': 'f"{%s}"', 'f': 'f"{%s!r}"', 's': 'f"{%s!r}"', 'b': '_ail_sq_reprb(%s)'}[letter] % v
                if k:
                    lines.append('    out = out + ", "')
                if null:
                    lines.extend(['    if r.n%d:' % k, '        out = out + "None"', '    else:', '        out = out + ' + shown])
                else:
                    lines.append('    out = out + ' + shown)
            lines.append('    out = out + ",)"' if len(shape) == 1 else '    out = out + ")"')
            lines.append('    return out')
            self.helper(one, '\n'.join(lines) + '\n')
        if not many:
            return one
        name = '_ail_sq_repr_list_' + shape.sig
        if name not in self.helpers:
            text = ('def %s(rows: list[%s]) -> str:\n    out: str = "["\n    for i in range(len(rows)):\n'
                    '        if i > 0:\n            out = out + ", "\n        out = out + %s(rows[i])\n'
                    '    return out + "]"\n') % (name, cls, one)
            self.helper(name, text)
        return name

    # ---- row expressions -------------------------------------------------------------------
    def rowinfo(self, e):
        """(rk, shape) when the (original) expression `e` is a row / list of rows / optional row the program declared."""
        if isinstance(e, ast.Name):
            return self.scope.find('decl', e.id)
        if isinstance(e, ast.Subscript):
            inner = self.rowinfo(e.value)
            if inner is not None and inner[0] == 'rows':
                return ('rows', inner[1]) if isinstance(e.slice, ast.Slice) else ('row', inner[1])
        if isinstance(e, ast.Call) and self.is_cast(e.func) and len(e.args) == 2 and self.fetch_call(e.args[1]) is not None:
            return self.decl_of(e.args[0])
        return None

    def pure(self, e):
        return isinstance(e, ast.Name) or (isinstance(e, ast.Attribute) and self.pure(e.value)) or isinstance(e, ast.Constant)

    def col_index(self, node, shape):
        """The constant column index of a Subscript of a row, else a refusal."""
        sl = node.slice
        if isinstance(sl, ast.UnaryOp) and isinstance(sl.op, ast.USub) and isinstance(sl.operand, ast.Constant) \
                and isinstance(sl.operand.value, int) and not isinstance(sl.operand.value, bool):
            k = -sl.operand.value
        elif isinstance(sl, ast.Constant) and isinstance(sl.value, int) and not isinstance(sl.value, bool):
            k = sl.value
        else:
            self.refuse(node, 'a row with a nullable or bytes column is indexed with a constant\n'
                              '  write instead: row[0], row[1] ... or unpack it: a, b = row')
        if k < 0:
            k += len(shape)
        if not 0 <= k < len(shape):
            self.refuse(node, 'column index out of range for a row of %d columns' % len(shape))
        return k

    def column(self, row_expr, shape, k, node):
        """A read of column k of a non-native row (an expression yielding the value, or an Optional)."""
        letter, null = shape.cols[k]
        if not null:
            return self.at(ast.Attribute(value=row_expr, attr='c%d' % k, ctx=ast.Load()), node)
        if letter == 'b':
            self.refuse(node, 'a nullable bytes column cannot be held in a variable here (bytes | None is not built)\n'
                              '  write instead: test it, row[%d] is None, and read it only in the other branch' % k)
        return self.at(self.call(self.get_fn(shape, k), row_expr), node)

    def show(self, row_expr, shape, k, node):
        """A str expression for printing column k of a non-native row."""
        letter, null = shape.cols[k]
        v = ast.Attribute(value=copy.deepcopy(row_expr), attr='c%d' % k, ctx=ast.Load())
        if letter == 'b':
            shown = self.call('_ail_sq_reprb', v)
        elif letter in 'if':
            shown = ast.JoinedStr(values=[ast.FormattedValue(value=v, conversion=-1, format_spec=None)])
        else:
            shown = v
        if null:
            flag = ast.Attribute(value=copy.deepcopy(row_expr), attr='n%d' % k, ctx=ast.Load())
            shown = ast.IfExp(test=flag, body=self.C('None'), orelse=shown)
        return self.at(shown, node)

    def row_use(self, node):
        """For a Subscript of a non-native row: (row expression visited, shape, k) or None."""
        if isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
            info = self.rowinfo(node.value)
            if info is not None and info[0] in ('row', 'orow') and not info[1].native:
                return info
        return None

    # ---- expression lowering ---------------------------------------------------------------
    def binds(self, c, params, sql, origin):
        """Chain the binds of `params` onto the cursor expression `c`."""
        if params is None:
            return c
        if isinstance(params, (ast.Tuple, ast.List)):
            for e in params.elts:
                if isinstance(e, ast.Starred):
                    self.refuse(e, '*args in the parameters is not built\n  write instead: list the values')
                c = self.bind_one(c, e)
            return c
        if isinstance(params, ast.Dict):
            c = self.call('_ail_sq_named', c)
            for key, value in zip(params.keys, params.values):
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    self.refuse(params, 'named parameters need a dict display with string literal keys\n'
                                        '  write instead: {"name": value, ...}, or ? placeholders and a tuple')
                c = self.bind_one(self.call('_ail_sq_name', c, self.C(key.value)), value)
            return c
        if self.pure(params) or isinstance(params, ast.Subscript):
            if isinstance(params, ast.Name) and self.holds_dict(params.id):
                self.refuse(params, 'named parameters held in a dict variable are not built (the keys have to be known when the program is built)\n'
                                    '  write instead: the dict display in the call, execute("... :a, :b", {"a": x, "b": y})')
            if sql is None:
                self.refuse(params, 'parameters held in a variable need the SQL text as a string literal in the same call\n'
                                    '  write instead: execute("... ?, ?", (a, b)) with the values listed')
            n = count_params(sql)
            c = self.call('_ail_sq_blen', c, self.call('len', self.visit(copy.deepcopy(params))))
            for k in range(n):
                c = self.call('_ail_sq_bind', c, ast.Subscript(value=self.visit(copy.deepcopy(params)), slice=self.C(k), ctx=ast.Load()))
            return c
        self.refuse(params, 'parameters must be a tuple or list display, a dict display, or a name\n'
                            '  write instead: assign them to a name first')

    def holds_dict(self, name):
        """Whether the program assigns a dict display to `name` or annotates it as a dict."""
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Assign) and isinstance(n.value, (ast.Dict, ast.DictComp)) \
                    and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
                return True
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == name:
                ann = n.annotation
                head = ann.value if isinstance(ann, ast.Subscript) else ann
                if isinstance(head, ast.Name) and self.uc(head.id) in ('dict', 'Dict'):
                    return True
            if isinstance(n, ast.arg) and n.arg == name and n.annotation is not None:
                ann = n.annotation
                head = ann.value if isinstance(ann, ast.Subscript) else ann
                if isinstance(head, ast.Name) and self.uc(head.id) in ('dict', 'Dict'):
                    return True
        return False

    def bind_one(self, c, e):
        e = self.visit(e)
        if _is_none(e):
            return self.call('_ail_sq_bn', c)
        return self.call('_ail_sq_bind', c, e)

    def sql_text(self, node):
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    def lower_execute(self, node):
        """X.execute(sql[, params]) as one expression yielding the cursor."""
        a = node.args
        if node.keywords or not a or len(a) > 2 or any(isinstance(x, ast.Starred) for x in a):
            self.refuse(node, 'execute(sql[, parameters]) takes the SQL and at most one parameters argument')
        recv = self.visit(node.func.value)
        sql = self.visit(a[0])
        c = self.call('_ail_sq_prep', recv, sql)
        c = self.binds(c, a[1] if len(a) == 2 else None, self.sql_text(a[0]), node)
        return self.at(self.call('_ail_sq_exec', c), node)

    def lower_executemany(self, node, recv_node=None):
        """X.executemany(sql, rows) as statements; returns (statements, cursor temp name)."""
        a = node.args
        if node.keywords or len(a) != 2 or any(isinstance(x, ast.Starred) for x in a):
            self.refuse(node, 'executemany(sql, rows) takes the SQL and the rows')
        sql_node, rows = a
        sql = self.sql_text(sql_node)
        recv = self.visit(node.func.value)
        t = self.temp()
        stmts = [self.at(ast.Assign(targets=[self.N(t, True)], value=self.call('_ail_sq_prep', recv, self.visit(sql_node))), node),
                 self.at(ast.Expr(value=self.call('_ail_sq_mbegin', self.N(t))), node)]
        if isinstance(rows, (ast.List, ast.Tuple)) and all(isinstance(r, (ast.Tuple, ast.List)) for r in rows.elts) and rows.elts:
            for r in rows.elts:
                stmts.append(self.at(ast.Expr(value=self.call('_ail_sq_mrow', self.N(t))), node))
                stmts.append(self.at(ast.Expr(value=self.call('_ail_sq_mstep', self.binds(self.N(t), r, sql, node))), node))
        elif isinstance(rows, (ast.List, ast.Tuple)) and not rows.elts:
            pass                                  # no rows: the implicit BEGIN only
        else:
            if isinstance(rows, ast.Dict) or (isinstance(rows, (ast.List, ast.Tuple)) and any(isinstance(r, ast.Dict) for r in rows.elts)):
                self.refuse(rows, 'executemany with named parameters is not built\n  write instead: ? placeholders and tuples')
            if sql is None:
                self.refuse(sql_node, 'executemany needs the SQL text as a string literal here\n'
                                      '  write instead: executemany("insert into t values (?, ?)", rows)')
            n = count_params(sql)
            r = self.temp()
            it = self.visit(rows)
            if isinstance(it, ast.GeneratorExp):
                it = ast.ListComp(elt=it.elt, generators=it.generators)
            chain = self.call('_ail_sq_blen', self.N(t), self.call('len', self.N(r)))
            for k in range(n):
                chain = self.call('_ail_sq_bind', chain, ast.Subscript(value=self.N(r), slice=self.C(k), ctx=ast.Load()))
            body = [self.at(ast.Expr(value=self.call('_ail_sq_mrow', self.N(t))), node),
                    self.at(ast.Expr(value=self.call('_ail_sq_mstep', chain)), node)]
            stmts.append(self.at(ast.For(target=self.N(r, True), iter=it, body=body, orelse=[]), node))
        stmts.append(self.at(ast.Expr(value=self.call('_ail_sq_mend', self.N(t))), node))
        return stmts, t

    def fetch_call(self, node):
        """`X.fetchone()` / `X.fetchall()` (no arguments): returns (method, receiver node) or None."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ('fetchone', 'fetchall') \
                and self.ours(node.func.attr, node.func.value):
            if node.args or node.keywords:
                self.refuse(node, '%s() takes no arguments' % node.func.attr)
            return node.func.attr, node.func.value
        return None

    def lower_fetch(self, node, rk, shape, strict=False):
        method, recv_node = self.fetch_call(node)
        if method == 'fetchall' and rk != 'rows':
            self.refuse(node, 'fetchall() gives a list of rows\n  write instead: rows: list[tuple[...]] = cur.fetchall()')
        if method == 'fetchone' and rk == 'rows':
            self.refuse(node, 'fetchone() gives one row\n  write instead: row: tuple[...] | None = cur.fetchone()')
        free = self.C(1 if self.is_temp_cursor(recv_node) else 0)
        recv = self.visit(recv_node)
        fn = self.all_fn(shape) if method == 'fetchall' else self.one_fn(shape, strict or rk == 'row')
        self.used = True
        return self.at(self.call(fn, recv, free), node)

    def needs_shape(self, node):
        self.refuse(node, '%s() needs the shape of the rows, declared in an annotation (CPython ignores it)\n'
                          '  write instead: rows: list[tuple[int, str]] = cur.fetchall()   or   '
                          'row: tuple[int, str] | None = cur.fetchone()   or   cast(tuple[int], cur.fetchone())[0]'
                    % node.func.attr)

    # ---- visitors: names, attributes, calls ------------------------------------------------
    def visit_Attribute(self, node):
        attr = self.sq_attr(node)
        if attr is not None and isinstance(node.value, ast.Name):
            if attr in _MODULE_REFUSED:
                self.refuse(node, 'sqlite3.%s: %s' % (attr, _MODULE_REFUSED[attr]))
            self.refuse(node, 'sqlite3.%s used as a value is not built (only calls of connect, annotations, and '
                              'except clauses name the module)' % attr)
        if node.attr in _ATTR_REFUSED and node.attr not in self.user_attr_names() and self.kind_of(node.value) is not None:
            self.refuse(node, _ATTR_REFUSED[node.attr])
        if node.attr in ('rowcount', 'lastrowid', 'in_transaction', 'total_changes') and isinstance(node.ctx, ast.Load) \
                and node.attr not in self.user_attr_names():
            prim = {'rowcount': '_ail_sq_rowcount', 'lastrowid': '_ail_sq_lastrowid', 'in_transaction': '_ail_sq_intx',
                    'total_changes': '_ail_sq_total'}[node.attr]
            self.used = True
            value = self.call(prim, self.visit(node.value))
            if node.attr == 'in_transaction':
                value = ast.Compare(left=value, ops=[ast.NotEq()], comparators=[self.C(0)])
            return self.at(value, node)
        return self.generic_visit(node)

    def handle_names(self):
        names = set()
        scopes = [self.module_scope] + list(self.scopes.values())
        for s in scopes:
            names.update(s.kinds)
        return names

    def user_attr_names(self):
        """Attribute names the program gives to its own objects (so `x.description` is not taken for a cursor's)."""
        if not hasattr(self, '_uan'):
            names = set(self.user_methods)
            for n in ast.walk(self.tree):
                if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store):
                    if not (isinstance(n.value, ast.Name) and n.value.id in self.handle_names()):
                        names.add(n.attr)
                elif isinstance(n, ast.ClassDef):
                    for member in n.body:
                        if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                            names.add(member.target.id)
                        elif isinstance(member, ast.Assign):
                            names.update(t.id for t in member.targets if isinstance(t, ast.Name))
            self._uan = names
        return self._uan

    def visit_Name(self, node):
        if node.id in self.from_names and isinstance(node.ctx, ast.Load):
            attr = self.from_names[node.id]
            if attr not in ('connect',):
                self.refuse(node, '%s (sqlite3.%s) used as a value is not built' % (node.id, attr))
        return node

    def visit_Call(self, node):
        f = node.func
        attr = self.sq_attr(f)
        if attr == 'connect':
            return self.lower_connect(node)
        if attr in _MODULE_REFUSED:
            self.refuse(node, 'sqlite3.%s: %s' % (attr, _MODULE_REFUSED[attr]))
        if attr is not None and attr not in _EXC | _TYPES:
            self.refuse(node, 'sqlite3.%s is not built' % attr)
        if attr in _EXC:
            return self.exc_ctor(node, attr)
        if self.is_cast(f) and len(node.args) == 2 and not node.keywords:
            inner = node.args[1]
            if self.fetch_call(inner) is not None:
                d = self.decl_of(node.args[0])
                if d is None:
                    self.refuse(node, 'cast() of a fetch needs a row shape: cast(tuple[int, str], cur.fetchone())')
                if self.fetch_call(inner)[0] == 'fetchone' and d[0] == 'orow':
                    return self.lower_fetch(inner, 'orow', d[1])
                return self.lower_fetch(inner, d[0], d[1], strict=True)
        if isinstance(f, ast.Attribute):
            name = f.attr
            if name in _METHOD_REFUSED and self.ours(name, f.value) and self.is_sql_receiver(f.value, name):
                self.refuse(node, _METHOD_REFUSED[name])
            if self.ours(name, f.value):
                if name == 'execute':
                    self.used = True
                    return self.lower_execute(node)
                if name == 'executescript':
                    if node.keywords or len(node.args) != 1:
                        self.refuse(node, 'executescript(sql) takes the script')
                    self.used = True
                    return self.at(self.call('_ail_sq_script', self.visit(f.value), self.visit(node.args[0])), node)
                if name == 'cursor':
                    if node.args or node.keywords:
                        self.refuse(node, 'cursor() takes no arguments here (cursor factories are not built)')
                    self.used = True
                    return self.at(self.call('_ail_sq_cursor', self.visit(f.value)), node)
                if name == 'executemany':
                    self.refuse(node, 'executemany is built as a statement, not inside an expression\n'
                                      '  write instead: conn.executemany(sql, rows) on a line of its own (the cursor: cur = conn.executemany(...))')
                if name in ('commit', 'rollback'):
                    if node.args or node.keywords:
                        self.refuse(node, '%s() takes no arguments' % name)
                    self.used = True
                    return self.at(self.call('_ail_sq_' + name, self.visit(f.value)), node)
                if name == 'close' and not node.args and not node.keywords and self.kind_of(f.value) is not None:
                    self.used = True
                    return self.at(self.call('_ail_sq_close', self.visit(f.value)), node)
                if name in ('fetchone', 'fetchall'):
                    self.needs_shape(node)
        # print / str / repr / len of rows with a nullable or bytes column
        if isinstance(f, ast.Name) and f.id not in self.user_defs:
            if f.id in ('print', 'str', 'repr', 'len', 'format'):
                lowered = self.row_builtin(node)
                if lowered is not None:
                    return lowered
        return self.generic_visit(node)

    def is_sql_receiver(self, recv, name):
        return name in ('create_function', 'create_aggregate', 'create_window_function', 'create_collation',
                        'set_authorizer', 'set_progress_handler', 'set_trace_callback', 'iterdump', 'backup',
                        'interrupt', 'blobopen', 'enable_load_extension', 'load_extension', 'fetchmany',
                        'setinputsizes', 'setoutputsize', 'getlimit', 'setlimit', 'serialize', 'deserialize',
                        'getconfig', 'setconfig') and (self.kind_of(recv) is not None or name in (
                            'create_function', 'create_aggregate', 'create_collation', 'fetchmany', 'iterdump'))

    def lower_connect(self, node):
        a = node.args
        kws = {k.arg: k.value for k in node.keywords}
        if any(k.arg is None for k in node.keywords):
            self.refuse(node, '**kwargs in connect() is not built')
        for k in kws:
            if k in _CONNECT_KW_REFUSED:
                self.refuse(node, _CONNECT_KW_REFUSED[k])
        if len(a) > 1 or any(isinstance(x, ast.Starred) for x in a):
            self.refuse(node, 'connect(database, isolation_level=...) takes the database as its one positional argument')
        path = a[0] if a else kws.pop('database', None)
        if path is None:
            self.refuse(node, 'connect() needs the database path (a str) or ":memory:"')
        iso = kws.pop('isolation_level', None)
        if kws:
            self.refuse(node, 'connect(%s=) is not built' % sorted(kws)[0])
        level = ''
        if iso is not None:
            if isinstance(iso, ast.Constant) and (iso.value is None or isinstance(iso.value, str)) and iso.value in _ISO:
                level = iso.value
            else:
                self.refuse(iso, "isolation_level must be None, '', 'DEFERRED', 'IMMEDIATE' or 'EXCLUSIVE' (a literal)")
        self.used = True
        return self.at(self.call('_ail_sq_open', self.visit(path), self.C(_ISO[level])), node)

    def exc_ctor(self, node, attr):
        return self.at(ast.Call(func=self.N('sqlite3_' + attr), args=[self.visit(x) for x in node.args], keywords=[]), node)

    def exc_name(self, node):
        """The exception name an `except` / `raise` expression denotes, as the typed runtime spells it."""
        attr = self.sq_attr(node)
        if attr in _EXC:
            self.used = True
            return self.at(self.N('sqlite3_' + attr), node)
        return None

    def visit_ExceptHandler(self, node):
        if node.type is not None:
            if isinstance(node.type, ast.Tuple):
                node.type.elts = [self.exc_name(e) or self.visit(e) for e in node.type.elts]
            else:
                node.type = self.exc_name(node.type) or self.visit(node.type)
        node.body = self.visit_list(node.body)
        return node

    def visit_Raise(self, node):
        if node.exc is not None:
            attr = self.sq_attr(node.exc)
            if attr in _EXC:
                node.exc = self.at(ast.Call(func=self.N('sqlite3_' + attr), args=[], keywords=[]), node.exc)
                self.used = True
                return node
        return self.generic_visit(node)

    def visit_list(self, stmts):
        out = []
        for s in stmts:
            r = self.visit(s)
            if r is None:
                continue
            if isinstance(r, list):
                out.extend(r)
            else:
                out.append(r)
        return out

    # ---- visitors: subscripts and printing of rows ----------------------------------------
    def visit_Subscript(self, node):
        info = self.row_use(node)
        if info is not None:
            k = self.col_index(node, info[1])
            return self.column(self.visit(node.value), info[1], k, node)
        return self.generic_visit(node)

    def row_builtin(self, node):
        """print / str / repr / len of a non-native row, of a list of them, or of a nullable column."""
        f = node.func.id
        if node.keywords and f != 'print':
            return None
        if f == 'len' and len(node.args) == 1:
            info = self.rowinfo(node.args[0])
            if info is not None and info[0] == 'row' and not info[1].native:
                return self.at(self.C(len(info[1])), node)
            return None
        changed = False
        args = []
        for arg in node.args:
            new = self.shown(arg)
            changed = changed or new is not None
            args.append(new if new is not None else arg)
        if not changed:
            return None
        self.used = True
        args = [self.visit(a) if a is arg else a for a, arg in zip(args, node.args)]
        return self.at(ast.Call(func=node.func, args=args, keywords=[self.visit(k) for k in node.keywords]), node)

    def shown(self, e):
        """A str expression for printing `e` when it is a non-native row / list of rows / nullable column, else None."""
        info = self.rowinfo(e)
        if info is not None and not info[1].native:
            rk, shape = info
            if rk == 'row':
                return self.at(self.call(self.repr_fn(shape, False), self.visit(e)), e)
            if rk == 'rows':
                return self.at(self.call(self.repr_fn(shape, True), self.visit(e)), e)
            if self.pure(e):                      # an optional row: None, or the row
                test = ast.Compare(left=self.visit(copy.deepcopy(e)), ops=[ast.Is()], comparators=[self.C(None)])
                return self.at(ast.IfExp(test=test, body=self.C('None'),
                                         orelse=self.call(self.repr_fn(shape, False), self.visit(copy.deepcopy(e)))), e)
            return None
        use = self.row_use(e)
        if use is not None:
            shape = use[1]
            k = self.col_index(e, shape)
            if shape.cols[k][1] or shape.cols[k][0] == 'b':
                return self.show(self.visit(e.value), shape, k, e)
        if self.is_lastrowid(e):
            self.used = True
            return self.at(self.call('_ail_sq_lastshow', self.visit(e.value)), e)
        return None

    def is_lastrowid(self, e):
        return isinstance(e, ast.Attribute) and e.attr == 'lastrowid' and isinstance(e.ctx, ast.Load) \
            and 'lastrowid' not in self.user_attr_names()

    def visit_JoinedStr(self, node):
        values = []
        for v in node.values:
            if isinstance(v, ast.FormattedValue):
                new = self.shown(v.value) if v.format_spec is None and v.conversion in (-1, 115, 114) else None
                if new is not None:
                    v = ast.FormattedValue(value=new, conversion=-1, format_spec=None)
                    self.used = True
                else:
                    info = self.rowinfo(v.value)
                    use = self.row_use(v.value)
                    if (info is not None and not info[1].native) or (
                            use is not None and (use[1].cols[self.col_index(v.value, use[1])][1])):
                        self.refuse(v.value, 'a row or a nullable column in an f-string takes no format spec or conversion\n'
                                             '  write instead: f"{row}" or f"{row[1]}"')
                    v = self.visit(v)
            values.append(v)
        node.values = values
        return node

    def visit_Compare(self, node):
        # row[k] is None / is not None / == None / != None on a nullable column: the flag
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)):
            left, right = node.left, node.comparators[0]
            for col, other in ((left, right), (right, left)):
                if self.is_lastrowid(col) and _is_none(other):
                    positive = isinstance(node.ops[0], (ast.Is, ast.Eq))
                    self.used = True
                    test = ast.Compare(left=self.call('_ail_sq_haslast', self.visit(col.value)),
                                       ops=[ast.Eq() if positive else ast.NotEq()], comparators=[self.C(0)])
                    return self.at(test, node)
                use = self.row_use(col)
                if use is not None and _is_none(other):
                    shape = use[1]
                    k = self.col_index(col, shape)
                    positive = isinstance(node.ops[0], (ast.Is, ast.Eq))
                    self.used = True
                    if not shape.cols[k][1]:
                        return self.at(self.C(not positive), node)
                    flag = ast.Attribute(value=self.visit(col.value), attr='n%d' % k, ctx=ast.Load())
                    return self.at(flag if positive else ast.UnaryOp(op=ast.Not(), operand=flag), node)
        return self.generic_visit(node)

    # ---- visitors: statements --------------------------------------------------------------
    def visit_FunctionDef(self, node):
        scope = self.scopes.get(id(node))
        saved = self.scope
        self.scope = scope or saved
        a = node.args
        for arg in a.posonlyargs + a.args + a.kwonlyargs:
            arg.annotation = self.fix_ann(arg.annotation)
        node.returns = self.fix_ann(node.returns)
        node.body = self.visit_list(node.body)
        self.scope = saved
        return node

    def visit_ClassDef(self, node):
        node.body = self.visit_list(node.body)
        return node

    def visit_Expr(self, node):
        v = node.value
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == 'executemany' \
                and self.ours('executemany', v.func.value):
            self.used = True
            stmts, t = self.lower_executemany(v)
            stmts.append(self.at(ast.Expr(value=self.call('_ail_sq_drop', self.N(t))), node))
            return stmts
        new = self.visit(v)
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr in ('execute', 'executescript') \
                and self.ours(v.func.attr, v.func.value):
            new = self.call('_ail_sq_drop', new)         # nobody can hold the cursor of `conn.execute(...)` on a line of its own
        return ast.copy_location(ast.Expr(value=new), node)

    def declared(self, target):
        if isinstance(target, ast.Name):
            return self.scope.find('decl', target.id)
        return None

    def visit_Assign(self, node):
        v = node.value
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == 'executemany' \
                and self.ours('executemany', v.func.value) and len(node.targets) == 1:
            self.used = True
            stmts, t = self.lower_executemany(v)
            stmts.append(self.at(ast.Assign(targets=node.targets, value=self.N(t)), node))
            return stmts
        fetch = self.fetch_call(v)
        if fetch is not None:
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                d = self.declared(node.targets[0])
                if d is None:
                    self.needs_shape(v)
                node.value = self.lower_fetch(v, d[0], d[1])
                node.targets = [self.visit(node.targets[0])]
                return node
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple):
                return self.unpack_fetch(node, v)
            self.needs_shape(v)
        # a, b = row  for a non-native row
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple):
            info = self.rowinfo(v)
            if info is not None and info[0] == 'row' and not info[1].native:
                return self.unpack_row(node.targets[0], v, info[1], node)
        # row = rows[i] / row = other   (a name that is not declared takes the shape of its source)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            info = self.rowinfo(v)
            if info is not None and self.scope.find('decl', node.targets[0].id) is None:
                self.scope.decl[node.targets[0].id] = info
        return self.generic_visit(node)

    def unpack_fetch(self, node, call):
        """a, b = cur.fetchone()  with the targets declared as scalars."""
        target = node.targets[0]
        method, recv = self.fetch_call(call)
        if method != 'fetchone':
            self.needs_shape(call)
        shape = self.shape_of_targets(target)
        if shape is None:
            self.needs_shape(call)
        t = self.temp()
        free = 1 if self.is_temp_cursor(recv) else 0
        stmts = [self.at(ast.Assign(targets=[self.N(t, True)], value=self.visit(recv)), node),
                 self.at(ast.If(test=ast.Compare(left=self.call('_ail_sq_next', self.N(t)), ops=[ast.LtE()], comparators=[self.C(0)]),
                                body=[self.at(ast.Raise(exc=self.call('RuntimeError', self.C('sqlite3: fetchone() found no row to unpack')), cause=None), node)],
                                orelse=[]), node)]
        stmts.append(self.at(ast.Expr(value=self.call('_ail_sq_cols', self.N(t), self.C(len(shape)))), node))
        stmts.extend(self.assign_columns(target.elts, self.N(t), shape, node))
        if free:
            stmts.append(self.at(ast.Expr(value=self.call('_ail_sq_drop', self.N(t))), node))
        self.used = True
        return stmts

    def shape_of_targets(self, target):
        """The shape implied by the declared scalar annotations of the names of a tuple target."""
        cols = []
        for e in target.elts:
            if not isinstance(e, ast.Name):
                return None
            d = self.col_decl(e.id)
            if d is None:
                return None
            cols.append(d)
        return self.shape(cols)

    def col_decl(self, name):
        s = self.scope
        while s is not None:
            c = getattr(s, 'coldecl', {}).get(name)
            if c is not None:
                return c
            s = s.parent
        return None

    def assign_columns(self, targets, cursor, shape, node):
        out = []
        for k, tgt in enumerate(targets):
            letter, null = shape.cols[k]
            if null and letter == 'b':
                self.refuse(tgt, 'a nullable bytes column cannot be held in a variable (bytes | None is not built)\n'
                                 '  write instead: read it as a non-nullable bytes column, or test `isnull` in SQL: '
                                 'select ifnull(col, x\'\') ...')
            if null:
                value = self.call(self.col_fn(letter), copy.deepcopy(cursor), self.C(k))
            else:
                value = self.call('_ail_sq_c' + letter, copy.deepcopy(cursor), self.C(k))
            out.append(self.at(ast.Assign(targets=[self.visit(tgt)], value=value), node))
        return out

    def unpack_row(self, target, value, shape, node):
        if any(not isinstance(e, ast.Name) for e in target.elts) or len(target.elts) != len(shape):
            self.refuse(node, 'unpacking a row of %d columns needs %d plain names' % (len(shape), len(shape)))
        t = self.temp()
        stmts = [self.at(ast.Assign(targets=[self.N(t, True)], value=self.visit(value)), node)]
        for k, tgt in enumerate(target.elts):
            stmts.append(self.at(ast.Assign(targets=[self.visit(tgt)], value=self.column(self.N(t), shape, k, node)), node))
        self.used = True
        return stmts

    def visit_AnnAssign(self, node):
        d = self.decl_of(node.annotation)
        col = self.col_of(node.annotation) if not isinstance(node.target, ast.Attribute) else None
        if isinstance(node.target, ast.Name):
            if col is not None and node.value is None:
                if not hasattr(self.scope, 'coldecl'):
                    self.scope.coldecl = {}
                self.scope.coldecl[node.target.id] = col
                self.used = True
                return None                      # a bare `name: int` / `name: Optional[str]` only declares a column type
            if d is not None:
                self.scope.decl[node.target.id] = d
                if node.value is None:
                    self.used = True
                    return None                  # a bare row declaration
                fetch = self.fetch_call(node.value)
                if fetch is not None:
                    node.annotation = self.fix_ann(node.annotation)
                    node.value = self.lower_fetch(node.value, d[0], d[1])
                    node.target = self.visit(node.target)
                    return node
            elif self.handle_kind(node.annotation) and node.value is None:
                self.used = True
                return None
        node.annotation = self.fix_ann(node.annotation)
        if node.value is not None:
            node.value = self.visit(node.value)
        return node

    def visit_Return(self, node):
        if node.value is not None and self.fetch_call(node.value) is not None and self.scope.ret is not None:
            node.value = self.lower_fetch(node.value, self.scope.ret[0], self.scope.ret[1])
            return node
        if node.value is not None and self.fetch_call(node.value) is not None:
            self.needs_shape(node.value)
        return self.generic_visit(node)

    def visit_For(self, node):
        it = node.iter
        cursor_loop = self.is_cursor_expr(it)
        rows_info = self.rowinfo(it)
        if cursor_loop:
            return self.lower_cursor_loop(node)
        if rows_info is not None and rows_info[0] == 'rows' and not rows_info[1].native:
            return self.lower_rows_loop(node, rows_info[1])
        if rows_info is not None and rows_info[0] == 'rows':
            # a plain list of tuples: the loop variable is a row of that shape
            if isinstance(node.target, ast.Name) and self.scope.find('decl', node.target.id) is None:
                self.scope.decl[node.target.id] = ('row', rows_info[1])
        return self.generic_visit(node)

    def is_cursor_expr(self, e):
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr in ('execute', 'executescript') \
                and self.ours(e.func.attr, e.func.value):
            return True
        return self.kind_of(e) == 'cur' and not isinstance(e, ast.Call)

    def lower_cursor_loop(self, node):
        if node.orelse:
            self.refuse(node, 'for/else over a cursor is not built')
        target = node.target
        it = node.iter
        free = self.is_temp_cursor(it)
        cname = self.temp()
        if isinstance(target, ast.Name):
            d = self.scope.find('decl', target.id)
            if d is None or d[0] != 'row':
                self.refuse(node, 'iterating a cursor needs the shape of the rows, declared before the loop (CPython ignores it)\n'
                                  '  write instead: row: tuple[int, str]  (a line of its own, above the loop), then '
                                  'for row in cur.execute(...)  -- or declare the columns: pk: int, name: str, then '
                                  'for pk, name in cur.execute(...)')
            shape = d[1]
            head = [self.at(ast.Assign(targets=[self.N(cname, True)], value=self.visit(it)), node)]
            assign = self.at(ast.Assign(targets=[self.visit(target)], value=self.call(self.row_fn(shape), self.N(cname))), node)
            body_pre = [assign]
        elif isinstance(target, ast.Tuple):
            shape = self.shape_of_targets(target)
            if shape is None:
                self.refuse(node, 'iterating a cursor with unpacking needs a declared type for every name, on lines of their own above '
                                  'the loop\n  write instead: pk: int, name: Optional[str], then for pk, name in cur.execute(...)')
            head = [self.at(ast.Assign(targets=[self.N(cname, True)], value=self.visit(it)), node)]
            body_pre = [self.at(ast.Expr(value=self.call('_ail_sq_cols', self.N(cname), self.C(len(shape)))), node)]
            body_pre.extend(self.assign_columns(target.elts, self.N(cname), shape, node))
        else:
            self.refuse(node, 'iterating a cursor needs a name or a tuple of names as the loop target')
        test = ast.Compare(left=self.call('_ail_sq_next', self.N(cname)), ops=[ast.Gt()], comparators=[self.C(0)])
        loop = self.at(ast.While(test=test, body=body_pre + self.visit_list(node.body), orelse=[]), node)
        out = head + [loop]
        if free:
            out.append(self.at(ast.Expr(value=self.call('_ail_sq_drop', self.N(cname))), node))
        self.used = True
        return out

    def lower_rows_loop(self, node, shape):
        target = node.target
        if isinstance(target, ast.Name):
            self.scope.decl.setdefault(target.id, ('row', shape))
            return self.generic_visit(node)
        if isinstance(target, ast.Tuple):
            t = self.temp()
            body = []
            if len(target.elts) != len(shape) or any(not isinstance(e, ast.Name) for e in target.elts):
                self.refuse(node, 'unpacking a row of %d columns needs %d plain names' % (len(shape), len(shape)))
            for k, tgt in enumerate(target.elts):
                body.append(self.at(ast.Assign(targets=[self.visit(tgt)], value=self.column(self.N(t), shape, k, node)), node))
            node.target = self.N(t, True)
            node.iter = self.visit(node.iter)
            node.body = body + self.visit_list(node.body)
            node.orelse = self.visit_list(node.orelse)
            self.used = True
            return node
        return self.generic_visit(node)

    def visit_With(self, node):
        handled = []
        for item in node.items:
            e = item.context_expr
            if self.kind_of(e) == 'conn' or (isinstance(e, ast.Call) and self.sq_attr(e.func) == 'connect'):
                handled.append(item)
            elif isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr in ('cursor', 'execute'):
                self.refuse(node, 'a cursor is not a context manager in sqlite3 (CPython raises); use a connection: with conn:')
        if not handled:
            return self.generic_visit(node)
        if len(node.items) != 1:
            self.refuse(node, 'a with statement over a connection takes one item\n  write instead: nest the with statements')
        item = node.items[0]
        for n in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if isinstance(n, (ast.Return, ast.Break, ast.Continue)):
                self.refuse(n, '%s inside `with conn:` is not built (the commit would be skipped)\n'
                               '  write instead: leave the with block first, then %s' % (
                                   type(n).__name__.lower(), type(n).__name__.lower()))
        self.used = True
        conn = self.temp()
        ok = self.temp()
        pre = []
        if isinstance(item.optional_vars, ast.Name):
            pre.append(self.at(ast.Assign(targets=[self.visit(item.optional_vars)], value=self.visit(item.context_expr)), node))
            conn_expr = lambda: self.N(item.optional_vars.id)
        elif item.optional_vars is not None:
            self.refuse(node, 'with ... as needs a plain name')
        else:
            pre.append(self.at(ast.Assign(targets=[self.N(conn, True)], value=self.visit(item.context_expr)), node))
            conn_expr = lambda: self.N(conn)
        pre.append(self.at(ast.Assign(targets=[self.N(ok, True)], value=self.C(False)), node))
        body = self.visit_list(node.body) + [self.at(ast.Assign(targets=[self.N(ok, True)], value=self.C(True)), node)]
        final = ast.If(test=self.N(ok), body=[ast.Expr(value=self.call('_ail_sq_commit', conn_expr()))],
                       orelse=[ast.Expr(value=self.call('_ail_sq_rollback', conn_expr()))])
        trying = self.at(ast.Try(body=body, handlers=[], orelse=[], finalbody=[self.at(final, node)]), node)
        return pre + [trying]

    def visit_ListComp(self, node):
        return self.comp(node)

    visit_SetComp = visit_GeneratorExp = visit_ListComp

    def comp(self, node):
        saved = dict(self.scope.decl)
        for gen in node.generators:
            info = self.rowinfo(gen.iter)
            if info is not None and info[0] == 'rows' and isinstance(gen.target, ast.Name):
                self.scope.decl[gen.target.id] = ('row', info[1])
        out = self.generic_visit(node)
        self.scope.decl.clear()
        self.scope.decl.update(saved)
        return out

    # ---- the pass --------------------------------------------------------------------------
    def run(self):
        self.build_scopes()
        self.scope = self.module_scope
        body = []
        for stmt in self.tree.body:
            if stmt in self.import_nodes:
                continue
            r = self.visit(stmt)
            if r is None:
                continue
            body.extend(r if isinstance(r, list) else [r])
        classes = [s for cls in self.classes.values() for s in cls]
        funcs = [s for fn in self.helpers.values() for s in fn]
        # after a docstring / __future__ imports, before everything else
        at = 0
        while at < len(body) and (isinstance(body[at], ast.ImportFrom) and body[at].module == '__future__'
                                  or isinstance(body[at], ast.Expr) and isinstance(getattr(body[at], 'value', None), ast.Constant)):
            at += 1
        self.tree.body = body[:at] + classes + funcs + body[at:]
        for n in ast.walk(self.tree):               # a block that held only a declaration we dropped
            for field in ('body', 'finalbody'):
                v = getattr(n, field, None)
                if isinstance(v, list) and not v and not isinstance(n, ast.Module):
                    v.append(ast.Pass())
        ast.fix_missing_locations(self.tree)


def rewrite_text(source, notes=None):
    """The program text with sqlite3 lowered onto the primitives. It runs from ail_syntax.python_surface BEFORE the tuple and
    Optional passes (they work on the text), because the row shapes are declared in `tuple[...]` and `Optional[...]`
    annotations. A program that does not import sqlite3 comes back untouched (the same string)."""
    global ACTIVE
    ACTIVE = False
    if 'sqlite3' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    lowerer = _Lowerer(tree, SqlRefusal)
    if not lowerer.scan():
        return source
    if os.environ.get('AIL_TARGET'):
        lowerer.refuse(lowerer.import_nodes[0], 'sqlite3 links the system libsqlite3, which a cross build (--target) does not have\n'
                       '  write instead: build on the machine that runs the program (no --target)')
    lowerer.run()
    ACTIVE = lowerer.used
    text = ast.unparse(tree)
    if os.environ.get('AIL_SQL_DUMP'):
        import sys
        print(text, file=sys.stderr)
    return text
