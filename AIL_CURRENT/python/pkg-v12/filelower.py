# -*- coding: utf-8 -*-
"""filelower.py -- the tree pass of stage G7 (see filelib.py): `open`, `with`, `print(file=)`, iteration
over files, `os` and `os.path`, lowered onto the primitives and the prelude (filelib_prelude.py).
"""
import ast
import copy
import os

import filelib
import filelib_prelude
import iterlower

# annotations that stand for the two file classes
_TEXT_ANNOTATIONS = {'TextIO', 'TextIOWrapper'}
_BIN_ANNOTATIONS = {'BinaryIO', 'BufferedReader', 'BufferedWriter', 'BufferedRandom', 'BufferedIOBase'}

# method -> (number of arguments after which a default is filled in, the defaults)
_FILL = {'read': (0, [-1]), 'readline': (0, [-1]), 'readlines': (0, [-1]), 'seek': (1, [0])}

_OS_CONSTS_POSIX = {'sep': '/', 'linesep': '\n', 'name': 'posix', 'pathsep': ':', 'curdir': '.', 'pardir': '..',
                    'extsep': '.', 'altsep': None, 'devnull': '/dev/null'}
_OS_CONSTS_NT = {'sep': '\\', 'linesep': '\r\n', 'name': 'nt', 'pathsep': ';', 'curdir': '.', 'pardir': '..',
                 'extsep': '.', 'altsep': '/', 'devnull': 'nul'}

_PATH_CALLS = {       # os.path.NAME -> (prelude function, snippet, number of arguments)
    'exists': ('_ail_pexists', 'pexists', 1), 'isfile': ('_ail_pisfile', 'pexists', 1),
    'isdir': ('_ail_pisdir', 'pexists', 1), 'islink': ('_ail_pislink', 'pexists', 1),
    'lexists': ('_ail_plexists', 'pexists', 1),
    'basename': ('_ail_ptail', 'ptail', 1), 'dirname': ('_ail_phead', 'phead', 1),
    'abspath': ('_ail_pabspath', 'pabs', 1), 'normpath': ('_ail_pnormpath', 'pnorm', 1),
    'isabs': ('_ail_pisabs', 'pabs', 1),
}


class _Lowerer(ast.NodeTransformer):
    def __init__(self, tree, Unsupported, general=False):
        self.tree = tree
        self.U = Unsupported
        self.general = general         # the general path: no whole-file intrinsics to leave alone
        self.mods = {}                 # local name -> 'os' | 'os.path' | 'io'
        self.names = {}                # local name -> 'os.getcwd', 'os.path.join' ...
        self.import_nodes = []
        self.need = set()
        self.user_defs = set()
        self.user_attrs = set()
        self.scopes = [{}]
        self.counter = 0
        self.files_active = False
        self.walk_dirs = set()         # names bound as the `dirs` of an os.walk loop
        self.hoist = []                # assignments to put before the statement being lowered
        self.windows = filelib.target_windows()

    # ---- helpers -----------------------------------------------------------------------------
    def refuse(self, node, text):
        error = self.U(text)
        error.source_line = getattr(node, 'lineno', None)
        raise error

    def fresh(self, stem):
        self.counter += 1
        return '_ail_%s%d' % (stem, self.counter)

    @staticmethod
    def N(id_, store=False):
        if os.environ.get('AIL_G7_NOMARK'):
            return ast.Name(id=id_, ctx=ast.Store() if store else ast.Load())
        return iterlower._name(id_, store)

    @staticmethod
    def C(value):
        if isinstance(value, int) and not isinstance(value, bool) and value < 0:
            # the parser never yields a negative Constant; the compiler reads -1 as USub(1)
            return ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=-value))
        return ast.Constant(value=value)

    def call(self, func, *args):
        if isinstance(func, str):
            func = self.N(func)
        return ast.Call(func=func, args=list(args), keywords=[])

    @staticmethod
    def method(obj, name, *args):
        return ast.Call(func=ast.Attribute(value=obj, attr=name, ctx=ast.Load()), args=list(args), keywords=[])

    def located(self, stmts, origin):
        iterlower._locate(stmts, origin)
        for each in stmts:
            ast.fix_missing_locations(each)
        return stmts

    def at(self, node, origin):
        ast.copy_location(node, origin)
        ast.fix_missing_locations(node)
        return node

    # ---- scanning ----------------------------------------------------------------------------
    def scan(self):
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'os':
                        self.mods[alias.asname or 'os'] = 'os'
                    elif alias.name == 'os.path':
                        if alias.asname:
                            self.mods[alias.asname] = 'os.path'
                        else:
                            self.mods['os'] = 'os'
                    elif alias.name in ('io', 'ntpath', 'posixpath'):
                        self.mods[alias.asname or alias.name] = alias.name
                if any(a.name in ('os', 'os.path', 'io', 'ntpath', 'posixpath') for a in node.names):
                    self.import_nodes.append(node)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module in ('os', 'os.path', 'io', 'ntpath', 'posixpath'):
                for alias in node.names:
                    if alias.name == '*':
                        self.refuse(node, 'from %s import *: name what you use' % node.module)
                    local = alias.asname or alias.name
                    if node.module == 'os' and alias.name == 'path':
                        self.mods[local] = 'os.path'
                    else:
                        self.names[local] = '%s.%s' % (node.module, alias.name)
                self.import_nodes.append(node)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.user_defs.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for each in ast.walk(target):
                        if isinstance(each, ast.Name):
                            self.user_defs.add(each.id)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, ast.FunctionDef):
                        self.user_attrs.add(member.name)
                    elif isinstance(member, ast.Assign):
                        for each in ast.walk(member.targets[0]):
                            if isinstance(each, ast.Name):
                                self.user_attrs.add(each.id)
                    elif isinstance(member, ast.AnnAssign):
                        for each in ast.walk(member.target):
                            if isinstance(each, ast.Name):
                                self.user_attrs.add(each.id)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                self.user_attrs.add(node.attr)

    def qual(self, node):
        """The dotted name behind `os.path.join`, `osp.join`, `join` ... through the imports, else None."""
        if isinstance(node, ast.Name):
            if node.id in self.names:
                return self.names[node.id]
            if node.id in self.mods:
                return self.mods[node.id]
            return None
        if isinstance(node, ast.Attribute):
            inner = self.qual(node.value)
            if inner is not None:
                return inner + '.' + node.attr
        return None

    def is_open(self, node):
        if not isinstance(node, ast.Call):
            return False
        if isinstance(node.func, ast.Name):
            return (node.func.id == 'open' and 'open' not in self.user_defs and 'open' not in self.names) \
                or self.names.get(node.func.id) == 'io.open'
        return self.qual(node.func) == 'io.open'

    def wants(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and self.is_open(node):
                return True
            if isinstance(node, (ast.Attribute, ast.Name)):
                name = self.qual(node)
                if name is not None and name.startswith(('os.', 'io.', 'ntpath.', 'posixpath.')) and name != 'os.cpu_count':
                    return True
        return False

    def path_name(self, qualname):
        """(flavor, function) for os.path.X, ntpath.X and posixpath.X, else None."""
        if qualname is None:
            return None
        for prefix, flavor in (('os.path.', 'nt' if self.windows else 'posix'), ('ntpath.', 'nt'), ('posixpath.', 'posix')):
            if qualname.startswith(prefix) and '.' not in qualname[len(prefix):]:
                return flavor, qualname[len(prefix):]
        return None

    # ---- open() ------------------------------------------------------------------------------
    def open_parts(self, node):
        """(mode text, kind, argument expressions) of an open() call."""
        order = ['file', 'mode', 'buffering', 'encoding', 'errors', 'newline', 'closefd', 'opener']
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            self.refuse(node, 'open() with * or ** arguments is not built.\n  write instead: name each argument')
        if len(node.args) > len(order):
            self.refuse(node, 'open() takes at most 8 arguments')
        given = dict(zip(order, node.args))
        for keyword in node.keywords:
            if keyword.arg not in order:
                self.refuse(node, "open() got an unexpected keyword argument '%s'" % keyword.arg)
            if keyword.arg in given:
                self.refuse(node, "open() got multiple values for argument '%s'" % keyword.arg)
            given[keyword.arg] = keyword.value
        if 'file' not in given:
            self.refuse(node, "open() missing required argument 'file'")
        mode = given.get('mode')
        if mode is None:
            mode_text = 'r'
        elif isinstance(mode, ast.Constant) and isinstance(mode.value, str):
            mode_text = mode.value
        else:
            self.refuse(node, 'open() with a mode that is not a string literal: the file kind (text or '
                              'binary) has to be known when the program is built.\n'
                              '  write instead: open(path, "r") or open(path, "rb") with the mode written out')
        closefd = given.get('closefd')
        if closefd is not None and not (isinstance(closefd, ast.Constant) and closefd.value is True):
            self.refuse(node, 'open(closefd=...) is not built')
        if given.get('opener') is not None and not (isinstance(given['opener'], ast.Constant) and given['opener'].value is None):
            self.refuse(node, 'open(opener=...) is not built')
        return mode_text, ('bin' if 'b' in mode_text else 'text'), given

    def optional_text(self, node, expr, what):
        """(value expression, present flag) of an encoding / errors / newline argument."""
        if expr is None or (isinstance(expr, ast.Constant) and expr.value is None):
            return self.C(''), self.C(0)
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return copy.deepcopy(expr), self.C(1)
        if isinstance(expr, ast.Name):
            return copy.deepcopy(expr), self.C(1)
        self.refuse(node, 'open(%s=...) must be a string literal or a name' % what)

    def lower_open(self, node):
        mode_text, kind, given = self.open_parts(node)
        path = given['file']
        buffering = given.get('buffering', self.C(-1))
        if kind == 'bin':
            self.need.add('bin_io')
        else:
            self.need.add('text_io')
        enc, hasenc = self.optional_text(node, given.get('encoding'), 'encoding')
        err, haserr = self.optional_text(node, given.get('errors'), 'errors')
        nl, hasnl = self.optional_text(node, given.get('newline'), 'newline')
        encattr = copy.deepcopy(enc)
        if isinstance(enc, ast.Constant) and enc.value:
            canonical = filelib.canonical_encoding(enc.value)
            if canonical is None:
                self.refuse(node, "open(encoding=%r): only utf-8, ascii and latin-1 are built.\n"
                                  "  write instead: encoding='utf-8' (read the bytes with 'rb' and decode them "
                                  "yourself for another encoding)" % enc.value)
            enc = self.C(canonical)
        if isinstance(err, ast.Constant) and err.value and err.value not in ('strict', 'replace', 'ignore'):
            self.refuse(node, "open(errors=%r): only 'strict', 'replace' and 'ignore' are built" % err.value)
        if isinstance(nl, ast.Constant) and nl.value not in ('', '\n', '\r', '\r\n') and hasnl.value == 1:
            self.refuse(node, 'open(newline=%r) is not a valid newline value' % nl.value)
        args = [path, self.C(mode_text), buffering, enc, hasenc, err, haserr, nl, hasnl]
        if kind == 'text':
            args.append(encattr)
            return self.call('_ail_open_text', *args)
        return self.call('_ail_open_bin', *args)

    def open_kind(self, node):
        return self.open_parts(node)[1]

    # ---- file variables per scope -----------------------------------------------------------
    def own_nodes(self, body):
        """Nodes of one scope (not of the functions, lambdas and classes inside it)."""
        pending = list(body)
        while pending:
            node = pending.pop()
            yield node
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                pending.extend(ast.iter_child_nodes(node))

    def annotation_kind(self, ann):
        if ann is None:
            return None
        name = None
        if isinstance(ann, ast.Name):
            name = ann.id
            if name.startswith('__ail_checked_') and name.endswith('__'):      # a return annotation, as the surface writes it
                name = name[len('__ail_checked_'):-2]
        elif isinstance(ann, ast.Attribute):
            name = ann.attr
        elif isinstance(ann, ast.Subscript):
            base = ann.value.id if isinstance(ann.value, ast.Name) else getattr(ann.value, 'attr', None)
            if base == 'IO' and isinstance(ann.slice, ast.Name):
                return {'str': 'text', 'bytes': 'bin'}.get(ann.slice.id)
            return None
        if name in _TEXT_ANNOTATIONS:
            return 'text'
        if name in _BIN_ANNOTATIONS:
            return 'bin'
        return None

    def collect_files(self, body, args=None):
        """name -> 'text' | 'bin' for the names this scope binds exactly once, to an open() call or as a
        `with open() as` target, and for parameters annotated as files."""
        stores = {}
        opened = {}                      # name -> [kinds of the open() bindings]
        kinds = {}
        for node in self.own_nodes(body):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                stores[node.id] = stores.get(node.id, 0) + 1
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                    and self.is_open(node.value):
                opened.setdefault(node.targets[0].id, []).append(self.open_kind(node.value))
            elif isinstance(node, ast.With):
                for item in node.items:
                    if isinstance(item.optional_vars, ast.Name) and self.is_open(item.context_expr):
                        opened.setdefault(item.optional_vars.id, []).append(self.open_kind(item.context_expr))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                kind = self.annotation_kind(node.annotation)
                if kind:
                    opened.setdefault(node.target.id, []).append(kind)
        # a name is a file when every binding of it in this scope is an open() (or an annotation) of one kind
        out = {name: found[0] for name, found in opened.items()
               if len(set(found)) == 1 and stores.get(name, 0) <= len(found)}
        if args is not None:
            for arg in args.posonlyargs + args.args + args.kwonlyargs:
                kind = self.annotation_kind(arg.annotation)
                if kind:
                    out[arg.arg] = kind
        return out

    def file_kind(self, node):
        if isinstance(node, ast.Name):
            for scope in reversed(self.scopes):
                if node.id in scope:
                    return scope[node.id]
        if self.is_open(node):
            return self.open_kind(node)
        return None

    # ---- statements --------------------------------------------------------------------------
    def visit_Module(self, node):
        mixed = self.mixed_names([s for s in node.body if not isinstance(s, (ast.FunctionDef, ast.ClassDef))])
        if mixed:
            node.body = self.split_mixed(node.body, mixed)
        self.scopes[0] = self.collect_files(node.body)
        node.body = self.block(node.body)
        return node

    def block(self, stmts):
        out = []
        for stmt in stmts:
            saved, self.hoist = self.hoist, []
            new = self.visit(stmt)
            pre, self.hoist = self.hoist, saved
            if pre:
                out.extend(self.located(pre, stmt))
            if new is None:
                continue
            if isinstance(new, list):
                out.extend(new)
            else:
                out.append(new)
        return out

    def lines_of(self, file_node):
        """`f.readlines()` of a file, bound to a name before the statement (the compiler walks and copies names)."""
        name = self.fresh('ls')
        self.hoist.append(ast.Assign(targets=[self.N(name, True)],
                                     value=self.method(self.visit(file_node), 'readlines', self.C(-1))))
        return self.N(name)

    def visit_FunctionDef(self, node):
        mixed = self.mixed_names(node.body)
        if mixed:
            node.body = self.split_mixed(node.body, mixed)
        self.scopes.append(self.collect_files(node.body, node.args))
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            arg.annotation = self.annotate(arg.annotation)
        node.returns = self.annotate(node.returns)
        node.body = self.block(node.body)
        self.scopes.pop()
        return node

    def annotate(self, ann):
        kind = self.annotation_kind(ann)
        if kind == 'text':
            self.need.add('text_io')
            return self.at(self.N('_AilTextIO'), ann)
        if kind == 'bin':
            self.need.add('bin_io')
            return self.at(self.N('_AilBinaryIO'), ann)
        return ann

    def visit_ClassDef(self, node):
        node.body = self.block(node.body)
        return node

    def visit_AnnAssign(self, node):
        node.annotation = self.annotate(node.annotation)
        if node.value is not None:
            node.value = self.visit(node.value)
        return node

    def visit_Assign(self, node):
        # head, tail = os.path.split(p) / root, ext = os.path.splitext(p)
        pn = self.path_name(self.qual(node.value.func)) if isinstance(node.value, ast.Call) else None
        if len(node.targets) == 1 and isinstance(node.targets[0], (ast.Tuple, ast.List)) \
                and pn is not None and pn[1] in ('split', 'splitext'):
            target = node.targets[0]
            if len(target.elts) != 2:
                self.refuse(node, '%s returns two values' % self.qual(node.value.func))
            call = node.value
            if len(call.args) != 1 or call.keywords:
                self.refuse(node, '%s takes one argument' % self.qual(call.func))
            arg = self.visit(call.args[0])
            temp = self.fresh('p')
            first, second, need = self.pair_functions(pn)
            self.need.update(need)
            stmts = [ast.Assign(targets=[self.N(temp, True)], value=arg),
                     ast.Assign(targets=[target.elts[0]], value=self.call(first, self.N(temp))),
                     ast.Assign(targets=[target.elts[1]], value=self.call(second, self.N(temp)))]
            return self.located(stmts, node)
        # dirs[:] = [...] of an os.walk loop: the list is emptied and refilled (a slice assignment is not built)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript) \
                and isinstance(node.targets[0].value, ast.Name) and node.targets[0].value.id in self.walk_dirs \
                and isinstance(node.targets[0].slice, ast.Slice) and node.targets[0].slice.lower is None \
                and node.targets[0].slice.upper is None and node.targets[0].slice.step is None:
            name = node.targets[0].value.id
            temp, item = self.fresh('d'), self.fresh('x')
            stmts = [ast.Assign(targets=[self.N(temp, True)], value=self.visit(node.value)),
                     ast.While(test=ast.Compare(left=self.call('len', self.N(name)), ops=[ast.Gt()], comparators=[self.C(0)]),
                               body=[ast.Expr(value=self.method(self.N(name), 'pop'))], orelse=[]),
                     ast.For(target=self.N(item, True), iter=self.N(temp), orelse=[], type_comment=None,
                             body=[ast.Expr(value=self.method(self.N(name), 'append', self.N(item)))])]
            return self.located(stmts, node)
        # os.environ[k] = v
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript) \
                and self.qual(node.targets[0].value) == 'os.environ':
            key = self.visit(node.targets[0].slice)
            value = self.visit(node.value)
            return self.located([ast.Assign(targets=[self.N('_ail_u', True)],
                                            value=self.call('_ail_os_setenv', key, value))], node)
        return self.generic_visit(node)

    def visit_Delete(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript) \
                and self.qual(node.targets[0].value) == 'os.environ':
            key = self.visit(node.targets[0].slice)
            return self.located([ast.Assign(targets=[self.N('_ail_u', True)],
                                            value=self.call('_ail_os_unsetenv', key))], node)
        return self.generic_visit(node)

    def visit_Expr(self, node):
        value = node.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == 'print' \
                and any(k.arg == 'file' for k in value.keywords) and 'print' not in self.user_defs:
            return self.lower_print_file(node, value)
        node.value = self.visit(value)
        value = node.value
        # a primitive that returns its status: keep the value in a throwaway local
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in filelib.PRIMS \
                and filelib.PRIMS[value.func.id][0] == 'int':
            return self.located([ast.Assign(targets=[self.N('_ail_u', True)], value=value)], node)
        return node

    def lower_print_file(self, node, call):
        target = None
        sep = end = flush = None
        for keyword in call.keywords:
            if keyword.arg == 'file':
                target = keyword.value
            elif keyword.arg == 'sep':
                sep = keyword.value
            elif keyword.arg == 'end':
                end = keyword.value
            elif keyword.arg == 'flush':
                flush = keyword.value
            else:
                self.refuse(node, "print() got an unexpected keyword argument '%s'" % keyword.arg)
        if any(isinstance(a, ast.Starred) for a in call.args):
            self.refuse(node, 'print(*args, file=...) is not built.\n  write instead: name the values')
        root = target
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id == 'sys':
            node.value = self.generic_visit(call)         # sys.stdout / sys.stderr: the existing spelling
            return node
        if isinstance(target, ast.Constant) and target.value is None:
            node.value = self.generic_visit(call)
            return node
        target = self.visit(target)
        values = []
        sep_expr = self.visit(sep) if sep is not None and not (isinstance(sep, ast.Constant) and sep.value is None) else self.C(' ')
        end_expr = self.visit(end) if end is not None and not (isinstance(end, ast.Constant) and end.value is None) else self.C('\n')
        parts = []
        for index, arg in enumerate(call.args):
            if index:
                parts.append(self.fmt(sep_expr))
            parts.append(self.fmt(self.visit(arg)))
        parts.append(self.fmt(end_expr))
        joined = ast.JoinedStr(values=parts)
        stmts = [ast.Expr(value=self.method(target, 'write', joined))]
        if flush is not None and not (isinstance(flush, ast.Constant) and flush.value is False):
            stmts.append(ast.Expr(value=self.method(copy.deepcopy(target), 'flush')))
        return self.located(stmts, node)

    @staticmethod
    def fmt(expr):
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return ast.Constant(value=expr.value)
        return ast.FormattedValue(value=expr, conversion=-1, format_spec=None)

    def visit_With(self, node):
        items = node.items
        body = self.block(node.body)
        # innermost first
        for item in reversed(items):
            context = item.context_expr
            if self.is_open(context):
                kind = self.open_kind(context)
                context = self.visit(context)
                target = item.optional_vars
                if target is None:
                    name = self.fresh('w')
                    target = self.N(name, True)
                    shown = self.N(name)
                elif isinstance(target, ast.Name):
                    shown = self.N(target.id)
                else:
                    self.refuse(node, 'with open(...) as %s: bind the file to a plain name.\n'
                                      '  write instead: `with open(path) as f:`' % type(target).__name__.lower())
            elif isinstance(context, ast.Name) and self.file_kind(context):
                target = None
                shown = self.N(context.id)
            elif self.general:
                item.context_expr = self.visit(item.context_expr)
                body = [ast.With(items=[item], body=body, type_comment=None)]      # a manager: withlib.py lowers it
                continue
            else:
                self.refuse(node, 'a `with` statement other than `with open(path) as f:` or `with f:` on a file '
                                  'variable; there are no other context managers.\n'
                                  '  write instead: `with open(path) as f:` or try/finally')
            close = ast.Expr(value=self.method(shown, 'close'))
            guarded = ast.Try(body=body, handlers=[], orelse=[], finalbody=[close])
            stmts = []
            if target is not None:
                stmts.append(ast.Assign(targets=[target], value=context))
            stmts.append(guarded)
            body = stmts
        return self.located(body, node)

    def visit_Try(self, node):
        return self.generic_visit(node)

    # ---- for loops ---------------------------------------------------------------------------
    def file_expr_for_loop(self, it):
        """(file expression, enumerate start or None, is_enumerate) when a for loop iterates a file."""
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'enumerate' \
                and 'enumerate' not in self.user_defs and 1 <= len(it.args) <= 2 and not it.keywords:
            inner = it.args[0]
            if self.file_kind(inner):
                return inner, (it.args[1] if len(it.args) == 2 else self.C(0)), True
            return None
        if self.file_kind(it):
            return it, None, False
        return None

    def legacy_open(self, node):
        """`open(path)` / `open(path, 'r')` with nothing else: the typed path reads it line by line itself."""
        if self.general or not self.is_open(node) or node.keywords or not 1 <= len(node.args) <= 2:
            return False
        if len(node.args) == 2:
            mode = node.args[1]
            return isinstance(mode, ast.Constant) and mode.value == 'r'
        return True

    def visit_For(self, node):
        if self.legacy_open(node.iter):
            node.iter.args = [self.visit(a) for a in node.iter.args]       # the typed path reads it line by line itself
            node.body = self.block(node.body)
            node.orelse = self.block(node.orelse)
            return node
        found = self.file_expr_for_loop(node.iter)
        if found is not None:
            return self.lower_file_loop(node, *found)
        if isinstance(node.iter, ast.Call) and self.qual(node.iter.func) == 'os.walk':
            return self.lower_walk(node)
        return self.generic_visit(node)

    def lower_file_loop(self, node, file_node, start, enumerated):
        opened = self.is_open(file_node)
        kind = self.file_kind(file_node)
        file_expr = self.visit(file_node)
        if opened:
            name = self.fresh('f')
            holder, shown = self.N(name, True), self.N(name)
        else:
            holder = None
            shown = file_expr
        line = self.fresh('l')
        stmts = []
        target = node.target
        counter = None
        if enumerated:
            if not (isinstance(target, ast.Tuple) and len(target.elts) == 2):
                self.refuse(node, 'for ... in enumerate(file): the target has to be (index, line)')
            counter = self.fresh('i')
            stmts.append(ast.Assign(targets=[self.N(counter, True)], value=self.visit(start)))
            index_target, line_target = target.elts
        else:
            line_target = target
        head = [ast.Assign(targets=[self.N(line, True)], value=self.method(copy.deepcopy(shown), '_next'))]
        stop = self.block(node.orelse) + [ast.Break()]
        head.append(ast.If(test=ast.Compare(left=self.call('len', self.N(line)), ops=[ast.Eq()],
                                            comparators=[self.C(0)]),
                           body=stop, orelse=[]))
        head.append(ast.Assign(targets=[line_target], value=self.N(line)))
        if enumerated:
            head.append(ast.Assign(targets=[index_target], value=self.N(counter)))
            head.append(ast.AugAssign(target=self.N(counter, True), op=ast.Add(), value=self.C(1)))
        loop = ast.While(test=self.C(True), body=head + self.block(node.body), orelse=[])
        if opened:
            stmts.insert(0, ast.Assign(targets=[holder], value=file_expr))
            stmts.append(ast.Try(body=[loop], handlers=[], orelse=[],
                                 finalbody=[ast.Expr(value=self.method(copy.deepcopy(shown), 'close'))]))
        else:
            stmts.append(loop)
        return self.located(stmts, node)

    def lower_walk(self, node):
        call = node.iter
        target = node.target
        if not (isinstance(target, ast.Tuple) and len(target.elts) == 3
                and all(isinstance(e, ast.Name) for e in target.elts)):
            self.refuse(node, 'os.walk() is built in `for root, dirs, files in os.walk(top):`')
        if len(call.args) != 1 or call.keywords:
            self.refuse(node, 'os.walk(top) takes the top directory only (topdown, no followlinks / onerror)')
        self.need.update(('walk', 'pjoin'))
        top = self.visit(call.args[0])
        walker = self.fresh('walk')
        root, dirs, files = target.elts
        self.walk_dirs.add(dirs.id)
        stmts = [ast.Assign(targets=[self.N(walker, True)], value=self.call('_AilWalk', top)),
                 ast.Assign(targets=[dirs], value=ast.List(elts=[], ctx=ast.Load()))]
        head = [ast.Assign(targets=[copy.deepcopy(root)], value=ast.Attribute(value=self.N(walker), attr='root', ctx=ast.Load())),
                ast.Assign(targets=[copy.deepcopy(dirs)], value=self.method(self.N(walker), 'dirs')),
                ast.Assign(targets=[copy.deepcopy(files)], value=self.method(self.N(walker), 'files'))]
        test = self.method(self.N(walker), 'advance', ast.Name(id=dirs.id, ctx=ast.Load()))
        loop = ast.While(test=test, body=head + self.block(node.body), orelse=self.block(node.orelse))
        stmts.append(loop)
        return self.located(stmts, node)

    def visit_comprehension(self, node):
        node.target = self.visit(node.target)
        if self.file_kind(node.iter):
            node.iter = self.lines_of(node.iter)
        else:
            node.iter = self.visit(node.iter)
        node.ifs = [self.visit(c) for c in node.ifs]
        return node

    # ---- expressions -------------------------------------------------------------------------
    def visit_Attribute(self, node):
        name = self.qual(node)
        if name is not None and isinstance(node.ctx, ast.Load):
            consts = _OS_CONSTS_NT if self.windows else _OS_CONSTS_POSIX
            if name == 'os.path.sep':
                return self.at(self.C(consts['sep']), node)
            if name == 'os.path.altsep':
                return self.at(self.C(consts['altsep']), node)
            if name.startswith('os.') and name[3:] in consts and '.' not in name[3:]:
                if consts[name[3:]] is None:
                    self.refuse(node, 'os.%s is None on this target; there is no None str here' % name[3:])
                return self.at(self.C(consts[name[3:]]), node)
        node = self.generic_visit(node)
        if self.files_active and isinstance(node, ast.Attribute) and node.attr == 'closed' \
                and isinstance(node.ctx, ast.Load) and 'closed' not in self.user_attrs:
            return self.at(self.method(node.value, '_closed'), node)
        return node

    def visit_Subscript(self, node):
        base = self.qual(node.value)
        if base == 'os.environ' and isinstance(node.ctx, ast.Load):
            self.need.add('environ')
            return self.at(self.call('_ail_environ_item', self.visit(node.slice)), node)
        pn = self.path_name(self.qual(node.value.func)) if isinstance(node.value, ast.Call) else None
        if pn is not None and pn[1] in ('split', 'splitext') \
                and isinstance(node.slice, ast.Constant) and node.slice.value in (0, 1, -1, -2):
            call = node.value
            if len(call.args) != 1 or call.keywords:
                self.refuse(node, '%s takes one argument' % self.qual(call.func))
            first, second, need = self.pair_functions(pn)
            self.need.update(need)
            return self.at(self.call(first if node.slice.value % 2 == 0 else second, self.visit(call.args[0])), node)
        return self.generic_visit(node)

    def visit_Compare(self, node):
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)) \
                and self.qual(node.comparators[0]) == 'os.environ':
            self.need.add('environ')
            test = self.call('_ail_environ_has', self.visit(node.left))
            if isinstance(node.ops[0], ast.NotIn):
                test = ast.UnaryOp(op=ast.Not(), operand=test)
            return self.at(test, node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        # the os family, before the children: the arguments are lowered by the handler
        name = self.qual(func)
        if name is not None and name.startswith(('os.', 'ntpath.', 'posixpath.')) and name != 'os.cpu_count' \
                and not self.is_open(node):
            return self.at(self.lower_os(node, name), node)
        if self.is_open(node):
            node.args = [self.visit(a) for a in node.args]
            for keyword in node.keywords:
                keyword.value = self.visit(keyword.value)
            return self.at(self.lower_open(node), node)
        # open(...).read() and friends on a temporary: CPython closes the file at once
        if isinstance(func, ast.Attribute) and self.is_open(func.value):
            opener = func.value
            if not self.general and func.attr == 'read' and not node.args and not node.keywords \
                    and not opener.keywords and len(opener.args) == 1:
                opener.args = [self.visit(a) for a in opener.args]
                return node                       # open(path).read(): the whole-file intrinsic
            return self.at(self.lower_once(node), node)
        node = self.generic_visit(node)
        func = node.func
        if isinstance(func, ast.Name):
            return self.lower_builtin(node)
        if isinstance(func, ast.Attribute):
            return self.fill_method(node)
        return node

    def lower_builtin(self, node):
        func = node.func.id
        if func in self.user_defs:
            return node
        if func == 'next' and node.args and self.file_kind(node.args[0]):
            if len(node.args) == 1:
                return self.method(node.args[0], '_next_value')
            if len(node.args) == 2:
                return self.method(node.args[0], '_next_default', node.args[1])
        if func in ('list', 'sorted', 'set', 'tuple', 'frozenset') and len(node.args) == 1 and self.file_kind(node.args[0]):
            node.args[0] = self.lines_of(node.args[0])
        return node

    def fill_method(self, node):
        func = node.func
        attr = func.attr
        if attr == 'join' and len(node.args) == 1 and self.file_kind(node.args[0]):
            node.args[0] = self.lines_of(node.args[0])
            return node
        if attr not in _FILL or not self.files_active:
            return node
        root = func.value
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id == 'sys':
            return node
        known = self.file_kind(func.value) is not None
        if attr in self.user_attrs and not known:
            return node
        position, defaults = _FILL[attr]
        if node.keywords or len(node.args) < position or len(node.args) > position + len(defaults):
            return node
        for value in defaults[len(node.args) - position:]:
            node.args.append(self.C(value))
        return node

    def lower_once(self, node):
        """`open(...).read()` / `.readline()` / `.readlines()` / `.write(s)` / `.writelines(...)`."""
        opener = node.func.value
        attr = node.func.attr
        mode_text, kind, given = self.open_parts(opener)
        node.args = [self.visit(a) for a in node.args]
        if node.keywords:
            self.refuse(node, 'open(...).%s() with keyword arguments is not built' % attr)
        lowered = self.lower_open(self.visit_open_children(opener)).args
        if attr in ('read', 'readline', 'readlines'):
            if len(node.args) > 1:
                self.refuse(node, 'open(...).%s() takes at most one argument' % attr)
            arg = node.args[0] if node.args else self.C(-1)
            self.need.add('text_once' if kind == 'text' else 'bin_once')
            return self.call('_ail_%s_once_%s' % ('text' if kind == 'text' else 'bin', attr), *lowered, arg)
        if attr == 'write':
            if len(node.args) != 1:
                self.refuse(node, 'open(...).write() takes one argument')
            self.need.add('text_once' if kind == 'text' else 'bin_once')
            return self.call('_ail_%s_once_write' % ('text' if kind == 'text' else 'bin'), *lowered, node.args[0])
        if attr == 'close':
            return self.method(self.lower_open(self.visit_open_children(opener)), 'close')
        self.refuse(node, 'open(...).%s(): a file that is opened and used once is built for read, readline, '
                          'readlines and write.\n  write instead: `with open(path) as f:` and use f' % attr)

    def visit_open_children(self, opener):
        opener.args = [self.visit(a) for a in opener.args]
        for keyword in opener.keywords:
            keyword.value = self.visit(keyword.value)
        return opener

    # ---- os ----------------------------------------------------------------------------------
    def bind(self, node, params, defaults=None, required=1):
        """Positional / keyword arguments of an os call by parameter name."""
        defaults = defaults or {}
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            self.refuse(node, '%s with * or ** arguments is not built' % self.qual(node.func))
        if len(node.args) > len(params):
            self.refuse(node, '%s takes at most %d arguments' % (self.qual(node.func), len(params)))
        got = dict(zip(params, node.args))
        for keyword in node.keywords:
            if keyword.arg not in params:
                self.refuse(node, "%s got an unexpected keyword argument '%s' (dir_fd, follow_symlinks ... "
                                  "are not built)" % (self.qual(node.func), keyword.arg))
            if keyword.arg in got:
                self.refuse(node, "%s got multiple values for argument '%s'" % (self.qual(node.func), keyword.arg))
            got[keyword.arg] = keyword.value
        out = []
        for index, param in enumerate(params):
            if param in got:
                out.append(self.visit(got[param]))
            elif param in defaults:
                out.append(self.C(defaults[param]))
            elif index < required:
                self.refuse(node, "%s() missing required argument '%s'" % (self.qual(node.func), param))
            else:
                out.append(None)
        return out

    def pair_functions(self, pn):
        flavor, fn = pn
        if flavor == 'nt':
            if fn == 'split':
                return '_ail_nthead', '_ail_nttail', ('nt_split',)
            return '_ail_ntroot', '_ail_ntext', ('nt_ext',)
        if fn == 'split':
            return '_ail_phead', '_ail_ptail', ('phead', 'ptail')
        return '_ail_proot', '_ail_pext', ('pext',)

    def lower_path(self, node, flavor, fn):
        nt = flavor == 'nt'
        if fn == 'join':
            if not node.args or node.keywords:
                self.refuse(node, 'os.path.join() takes positional string arguments')
            self.need.add('nt_join' if nt else 'pjoin')
            args = [self.visit(a) for a in node.args]
            if nt:
                result = self.call('_ail_ntjoin_init', args[0])
                for each in args[1:]:
                    result = self.call('_ail_ntjoin_step', result, each)
                return self.call('_ail_ntjoin_end', result)
            result = args[0]
            for each in args[1:]:
                result = self.call('_ail_pjoin', result, each)
            return result
        table = {
            'exists': ('_ail_pexists', ('pexists',)), 'isfile': ('_ail_pisfile', ('pexists',)),
            'isdir': ('_ail_pisdir', ('pexists',)), 'islink': ('_ail_pislink', ('pexists',)),
            'lexists': ('_ail_plexists', ('pexists',)),
            'getsize': ('_ail_os_getsize', ()),
            'basename': ('_ail_nttail', ('nt_split',)) if nt else ('_ail_ptail', ('ptail',)),
            'dirname': ('_ail_nthead', ('nt_split',)) if nt else ('_ail_phead', ('phead',)),
            'abspath': ('_ail_ntabspath', ('nt_abs',)) if nt else ('_ail_pabspath', ('pabs',)),
            'normpath': ('_ail_ntnormpath', ('nt_norm',)) if nt else ('_ail_pnormpath', ('pnorm',)),
            'isabs': ('_ail_ntisabs', ('nt_abs',)) if nt else ('_ail_pisabs', ('pabs',)),
        }
        if fn in table:
            func, need = table[fn]
            self.need.update(need)
            (arg,) = self.bind(node, ('filename' if fn == 'getsize' else 'path',), {}, required=1)
            return self.call(func, arg)
        if fn == 'relpath' and not nt:
            self.need.add('prel')
            path, start = self.bind(node, ('path', 'start'), {'start': '.'}, required=1)
            return self.call('_ail_prelpath', path, start)
        if fn in ('split', 'splitext'):
            (arg,) = self.bind(node, ('p',), {}, required=1)
            first, second, need = self.pair_functions((flavor, fn))
            self.need.update(need)
            self.need.add('nt_split_pair' if nt and fn == 'split' else 'nt_ext_pair' if nt else 'psplit_pair' if fn == 'split' else 'psplitext_pair')
            return self.call({'_ail_phead': '_ail_psplit_pair', '_ail_proot': '_ail_psplitext_pair',
                              '_ail_nthead': '_ail_ntsplit_pair', '_ail_ntroot': '_ail_ntsplitext_pair'}[first], arg)
        self.refuse(node, '%s.%s is not built. Built: join exists isfile isdir islink lexists getsize basename dirname '
                          'split splitext abspath normpath isabs%s' % ('ntpath' if nt else 'os.path', fn,
                                                                          '' if nt else ' relpath'))

    def lower_os(self, node, name):
        pn = self.path_name(name)
        if pn is not None:
            return self.lower_path(node, *pn)
        simple = {
            'os.getcwd': ('_ail_os_getcwd', (), {}),
            'os.chdir': ('_ail_os_chdir', ('path',), {}),
            'os.mkdir': ('_ail_os_mkdir', ('path', 'mode'), {'mode': 0o777}),
            'os.rmdir': ('_ail_os_rmdir', ('path',), {}),
            'os.remove': ('_ail_os_unlink', ('path',), {}),
            'os.unlink': ('_ail_os_unlink', ('path',), {}),
            'os.chmod': ('_ail_os_chmod', ('path', 'mode'), {}),
            'os.rename': ('_ail_os_rename', ('src', 'dst'), {}),
            'os.replace': ('_ail_os_replace', ('src', 'dst'), {}),
            'os.path.getsize': ('_ail_os_getsize', ('filename',), {}),
        }
        if name in simple:
            func, params, defaults = simple[name]
            args = self.bind(node, params, defaults, required=len(params) - len([p for p in params if p in defaults]))
            return self.call(func, *args)
        if name == 'os.listdir':
            self.need.add('listdir')
            (path,) = self.bind(node, ('path',), {'path': '.'}, required=0)
            return self.call('_ail_listdir', path)
        if name == 'os.makedirs':
            self.need.update(('makedirs', 'phead', 'ptail', 'pexists'))
            n, mode, exist_ok = self.bind(node, ('name', 'mode', 'exist_ok'), {'mode': 0o777, 'exist_ok': False}, required=1)
            return self.call('_ail_makedirs', n, mode, exist_ok)
        if name == 'os.getenv' or name == 'os.environ.get':
            self.need.add('environ')
            if name == 'os.environ.get':
                key, default = self.bind(node, ('key', 'default'), {}, required=1)
            else:
                key, default = self.bind(node, ('key', 'default'), {}, required=1)
            if default is None:
                self.refuse(node, '%s(key) without a default returns None, and there is no None str.\n'
                                  '  write instead: %s(key, "") and test for the empty string' % (name, name))
            return self.call('_ail_environ_get', key, default)


        if name == 'os.environ':
            self.refuse(node, 'os.environ is built for os.environ[key], os.environ.get(key, default), '
                              '`key in os.environ`, os.environ[key] = value and del os.environ[key]; '
                              'it cannot be iterated or copied')
        if name == 'os.walk':
            self.refuse(node, 'os.walk() is built in `for root, dirs, files in os.walk(top):`')
        self.refuse(node, '%s is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir '
                          'rename replace getenv environ walk, os.sep linesep name curdir, and os.path join '
                          'exists isfile isdir islink getsize basename dirname split splitext abspath normpath '
                          'isabs relpath' % name)

    # ---- the driver --------------------------------------------------------------------------
    def run(self):
        self.files_active = any(isinstance(n, ast.Call) and self.is_open(n) for n in ast.walk(self.tree)) \
            or any(self.annotation_kind(getattr(n, 'annotation', None)) for n in ast.walk(self.tree))
        self.visit(self.tree)
        self.leftovers()
        for node in self.import_nodes:
            if node in self.tree.body:
                index = self.tree.body.index(node)
                self.tree.body[index] = self.at(ast.Pass(), node)
        self.inject()
        ast.fix_missing_locations(self.tree)

    def leftovers(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and (node.id in self.mods or node.id in self.names):
                shown = self.qual(node)
                if shown == 'os.cpu_count':
                    continue
                self.refuse(node, '%s used here is not built. Built: os.getcwd chdir listdir mkdir makedirs '
                                  'remove unlink rmdir rename replace getenv environ walk, os.sep linesep '
                                  'name curdir, and the os.path functions join exists isfile isdir islink '
                                  'getsize basename dirname split splitext abspath normpath isabs relpath' % shown)

    @staticmethod
    def surface(source):
        """The prelude is written like a user program, so it gets what a user program gets from the
        Python surface (checked return annotations, ...)."""
        try:
            import sys
            top = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if top not in sys.path:
                sys.path.append(top)
            from ail_syntax import python_surface
        except ImportError:
            return source
        return python_surface(source, [])

    def inject(self):
        order = []
        seen = set()

        def add(name):
            if name in seen:
                return
            seen.add(name)
            for need in filelib_prelude.SNIPPETS[name][1]:
                add(need)
            order.append(name)

        for name in sorted(self.need):
            add(name)
        statements = []
        for name in order:
            source = self.surface(filelib_prelude.SNIPPETS[name][0])
            parsed = ast.parse(source)
            for each in ast.walk(parsed):
                if 'lineno' in getattr(each, '_attributes', ()):
                    each.lineno = 1
                    each.end_lineno = 1
                    each.col_offset = 0
                    each.end_col_offset = 0
                if isinstance(each, ast.Name):
                    each._ail_synth = True
            statements.extend(parsed.body)
        body = self.tree.body
        index = 0
        while index < len(body) and (
                isinstance(body[index], (ast.Import, ast.ImportFrom, ast.Pass))
                or (isinstance(body[index], ast.Expr) and isinstance(body[index].value, ast.Constant))):
            index += 1
        self.tree.body = body[:index] + statements + body[index:]

    # ---- one name, two kinds of file ------------------------------------------------------------
    def mixed_names(self, body):
        """Names that a scope binds to a text file at one place and to a binary file at another: the
        compiler gives a variable one class, so each binding gets a name of its own."""
        kinds = {}
        for node in self.own_nodes(body):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                    and self.is_open(node.value):
                kinds.setdefault(node.targets[0].id, set()).add(self.open_kind(node.value))
            elif isinstance(node, ast.With):
                for item in node.items:
                    if isinstance(item.optional_vars, ast.Name) and self.is_open(item.context_expr):
                        kinds.setdefault(item.optional_vars.id, set()).add(self.open_kind(item.context_expr))
        return {name for name, found in kinds.items() if len(found) > 1}

    def rename_in(self, nodes, mapping):
        for node in self.own_nodes(nodes):
            if isinstance(node, ast.Name) and node.id in mapping:
                node.id = mapping[node.id]

    def split_mixed(self, stmts, mixed, current=None):
        current = dict(current or {})
        for stmt in stmts:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) \
                    and stmt.targets[0].id in mixed and self.is_open(stmt.value):
                self.rename_in([stmt.value], current)
                alias = self.fresh('f' + self.open_kind(stmt.value))
                current[stmt.targets[0].id] = alias
                stmt.targets[0].id = alias
                continue
            if isinstance(stmt, ast.With):
                inner = dict(current)
                for item in stmt.items:
                    self.rename_in([item.context_expr], inner)
                    if isinstance(item.optional_vars, ast.Name) and item.optional_vars.id in mixed \
                            and self.is_open(item.context_expr):
                        alias = self.fresh('f' + self.open_kind(item.context_expr))
                        inner[item.optional_vars.id] = alias
                        item.optional_vars.id = alias
                stmt.body = self.split_mixed(stmt.body, mixed, inner)
                continue
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try)):
                head = [stmt.test] if isinstance(stmt, (ast.If, ast.While)) else [stmt.iter] if isinstance(stmt, ast.For) else []
                self.rename_in(head, current)
                for field in ('body', 'orelse', 'finalbody'):
                    if getattr(stmt, field, None):
                        setattr(stmt, field, self.split_mixed(getattr(stmt, field), mixed, current))
                for handler in getattr(stmt, 'handlers', []):
                    handler.body = self.split_mixed(handler.body, mixed, current)
                continue
            self.rename_in([stmt], current)
        return stmts
