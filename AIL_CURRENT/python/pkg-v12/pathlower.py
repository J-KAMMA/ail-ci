# -*- coding: utf-8 -*-
"""pathlower.py -- stage G10: `pathlib.Path` (docs/design/GENERAL_PURPOSE.md s4.2).

A tree-to-tree pass in the manner of filelib.py / proclib.py, run by both compile paths just before
the process and file passes. `Path` is a class of the prelude (`_AilPath`, pathlib_prelude.py) that
holds the normalized text of the path; there is no operator overloading in the compiler, so the
pass decides from the program text which expressions are paths (`Path(...)`, `Path.cwd()`, `a / b`,
`.parent`, `.with_suffix(...)`, names bound only to such values, parameters annotated `Path`, loop
variables over `iterdir()` / `glob()` / `list[Path]` ...) and lowers

  * `Path(a, b)`, `p / x`, `x / p`, `p /= x`        onto string functions that return the text of
                                                     the new path (`_AilPath(text)` where an object is needed);
  * `str(p)`, `f"{p}"`, `print(p)`, `repr(p)`, `os.fspath`, and a path as an argument of `open()`
    and of the `os` functions                        onto the text of the path;
  * `p.name .stem .suffix .suffixes .parent .parts .root .anchor .drive`
  * `exists is_file is_dir is_absolute as_posix joinpath with_name with_stem with_suffix resolve
    absolute read_text write_text read_bytes write_bytes open mkdir iterdir glob rglob unlink rmdir
    rename replace`
                                                     onto the functions of the prelude, or onto the
                                                     `open(...)` the file layer already lowers;
  * `sorted(paths)` onto CPython's ordering of paths (part by part), `p == q` onto text equality.

Whatever else a path can do is refused by name with a `write instead:` line; a path is never accepted
and then run with another meaning. A program that does not import pathlib is not touched.
"""
import ast
import copy

import iterlower

BUILT = ('Path(...), Path.cwd(), p / x, str(p), repr(p), p == q, p.name .stem .suffix .suffixes .parent .parts '
         '.root .anchor .drive, exists is_file is_dir is_absolute as_posix joinpath with_name with_stem '
         'with_suffix resolve absolute read_text write_text read_bytes write_bytes open mkdir iterdir glob '
         'rglob unlink rmdir rename replace')

_REFUSED_CLASSES = {'PurePath', 'PurePosixPath', 'PureWindowsPath', 'PosixPath', 'WindowsPath'}

_WRITE_INSTEAD = {
    'stat': 'os.path.getsize(str(p)) for the size; the rest of os.stat is not built',
    'lstat': 'os.path.islink(str(p)) for a link test',
    'touch': 'open(str(p), "a").close() creates the file when it is missing (it does not set the time)',
    'chmod': 'os.chmod(str(p), mode)',
    'home': 'os.getenv("HOME", "")',
    'expanduser': 'expand "~" yourself',
    'relative_to': 'os.path.relpath(str(p), str(base))',
    'is_relative_to': 'str(p).startswith(str(base) + "/")',
    'is_symlink': 'os.path.islink(str(p))',
    'samefile': 'compare str(a.resolve()) == str(b.resolve())',
    'walk': 'os.walk(str(p))',
    'match': 'compare p.name with the text you expect',
    'parents': 'p.parent, applied as often as you need',
    'readlink': 'resolve() follows links',
    'symlink_to': 'a link is not built',
    'hardlink_to': 'a link is not built',
    'owner': 'not built',
    'group': 'not built',
    'as_uri': 'not built',
    'with_segments': 'Path(...)',
}

_P_METHODS = {'with_name', 'with_stem', 'with_suffix', 'resolve', 'absolute', 'joinpath', 'rename', 'replace'}
_PL_METHODS = {'iterdir', 'glob', 'rglob'}
_PLAIN_METHODS = {'exists', 'is_file', 'is_dir', 'is_absolute', 'as_posix', 'read_text', 'write_text',
                  'read_bytes', 'write_bytes', 'open', 'mkdir', 'unlink', 'rmdir'}
_ALL_METHODS = _P_METHODS | _PL_METHODS | _PLAIN_METHODS
_HASHING_METHODS = {'add', 'discard', 'remove', 'get', 'setdefault', 'pop', 'index', 'count', 'update', 'union',
                    'intersection', 'difference', 'issubset', 'issuperset', 'fromkeys'}
_ATTRS = {'name', 'stem', 'suffix', 'suffixes', 'parent', 'parts', 'root', 'anchor', 'drive'}
_LAZY_OK = {'list', 'sorted', 'enumerate', 'zip', 'any', 'all', 'sum'}
_PARTS_OK = {'len', 'list', 'sorted', 'enumerate', 'reversed', 'zip', 'any', 'all', 'min', 'max', 'set', 'frozenset'}
_NO_PATHS = {'min', 'max', 'set', 'frozenset', 'tuple', 'dict', 'next', 'iter', 'map', 'filter', 'reversed'}
_OS_MODULES = {'os', 'ntpath', 'posixpath', 'io'}


# Set while a program that imports pathlib is lowered: its file errors all carry their own exception
# code (pyfunc reads this), so `except FileNotFoundError` catches FileNotFoundError and nothing else.
ACTIVE = False


class _Scope:
    def __init__(self, kind='function'):
        self.kind = kind
        self.bound = set()
        self.p = set()
        self.pl = set()


class _Lowerer(ast.NodeTransformer):
    def __init__(self, tree, Unsupported, general=False):
        self.tree = tree
        self.U = Unsupported
        self.general = general
        self.cls_names = set()          # local names of pathlib.Path
        self.mod_names = set()          # local names of the module pathlib
        self.os_names = set()           # local names of os / io / posixpath ...
        self.from_os = set()            # names imported from those modules
        self.import_nodes = []
        self.need = set()
        self.used = False
        self.user_defs = set()
        self.p_attrs = set()
        self.pl_attrs = set()
        self.p_returns = set()          # names of functions annotated -> Path
        self.pl_returns = set()
        self.scopes = []
        self.fn_scopes = {}
        self.lazy_ok = set()
        self.parts_ok = set()
        self.sigs = {}                  # name -> [(FunctionDef, is a method)] of the user's own functions
        self.ann_snapshot = {}          # id(FunctionDef) -> ({parameter: kind}, return kind), taken before any annotation is rewritten

    # ---- helpers -----------------------------------------------------------------------------
    def refuse(self, node, text):
        if 'write instead:' not in text:
            text += '\n  write instead: use what is built: ' + BUILT
        error = self.U(text)
        error.source_line = getattr(node, 'lineno', None)
        raise error

    @staticmethod
    def N(id_):
        return iterlower._name(id_)

    @staticmethod
    def C(value):
        return ast.Constant(value=value)

    def call(self, func, *args):
        if isinstance(func, str):
            import pathlib_prelude
            if func in pathlib_prelude.FUNCTIONS:
                self.need.add(func)
            func = self.N(func)
        return ast.Call(func=func, args=list(args), keywords=[])

    @staticmethod
    def attr(value, name):
        return ast.Attribute(value=value, attr=name, ctx=ast.Load())

    def at(self, node, origin):
        ast.copy_location(node, origin)
        for each in ast.walk(node):
            if 'lineno' in getattr(each, '_attributes', ()) and not hasattr(each, 'lineno'):
                ast.copy_location(each, origin)
        return node

    def obj(self, text):
        self.need.add('pl_class')
        return self.call('_AilPath', text)

    def fn(self, name, needs, *args):
        return self.call(name, *args)

    # ---- scanning ----------------------------------------------------------------------------
    def scan(self):
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in self.tree.body:
                names = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
                if any(n and n.split('.')[0] == 'pathlib' for n in names):
                    self.refuse(node, 'import pathlib at the top of the file, not inside a function or block')
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split('.')[0]
                    if alias.name == 'pathlib':
                        self.mod_names.add(alias.asname or 'pathlib')
                        self.import_nodes.append(node)
                    elif alias.name.startswith('pathlib.'):
                        self.refuse(node, 'import pathlib.%s is not built' % alias.name.split('.', 1)[1])
                    elif root in _OS_MODULES:
                        self.os_names.add(alias.asname or root)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                if node.module == 'pathlib':
                    for alias in node.names:
                        if alias.name == '*':
                            self.refuse(node, 'from pathlib import *: name what you use')
                        if alias.name == 'Path':
                            self.cls_names.add(alias.asname or 'Path')
                        elif alias.name in _REFUSED_CLASSES:
                            self.refuse(node, 'pathlib.%s is not built. Built: pathlib.Path\n'
                                              '  write instead: Path (the class of this platform)' % alias.name)
                        else:
                            self.refuse(node, 'pathlib.%s is not built. Built: pathlib.Path' % alias.name)
                    self.import_nodes.append(node)
                elif node.module and node.module.split('.')[0] in _OS_MODULES:
                    for alias in node.names:
                        self.from_os.add(alias.asname or alias.name)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.user_defs.add(node.name)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, ast.FunctionDef):
                        if member.name == '__init__':
                            self.sigs.setdefault(node.name, []).append((member, True))
                        else:
                            self.sigs.setdefault(member.name, []).append((member, True))
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                self.sigs.setdefault(node.name, []).append((node, False))
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                params = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                self.ann_snapshot[id(node)] = ({a.arg: self.ann_kind(a.annotation) for a in params},
                                               self.ann_kind(node.returns))
        self.used = bool(self.cls_names or self.mod_names)
        return self.used

    # ---- annotations -------------------------------------------------------------------------
    def is_path_class(self, node):
        """Whether `node` names the class pathlib.Path."""
        if isinstance(node, ast.Name):
            return node.id in self.cls_names
        if isinstance(node, ast.Attribute) and node.attr == 'Path' and isinstance(node.value, ast.Name):
            return node.value.id in self.mod_names
        return False

    @staticmethod
    def unchecked(name):
        if name.startswith('__ail_checked_') and name.endswith('__'):
            return name[len('__ail_checked_'):-2]
        return name

    def ann_kind(self, ann):
        """'P' for Path, 'PL' for list[Path], else None."""
        if ann is None:
            return None
        if self.is_path_class(ann):
            return 'P'
        if isinstance(ann, ast.Name):
            inner = self.unchecked(ann.id)
            if inner != ann.id and inner in self.cls_names:
                return 'P'
            return None
        if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
            base = self.unchecked(ann.value.id)
            if base == '__ail_checked_list':
                base = 'list'
            if base == 'list' and self.ann_kind(ann.slice) == 'P':
                return 'PL'
        return None

    def mentions_path(self, ann):
        return ann is not None and any(self.is_path_class(n) or (isinstance(n, ast.Name) and (
            n.id in self.cls_names or self.unchecked(n.id) in self.cls_names)) for n in ast.walk(ann))

    def fix_ann(self, ann, where):
        if ann is None or not self.mentions_path(ann):
            return ann
        kind = self.ann_kind(ann)
        if kind == 'P':
            if isinstance(ann, ast.Name) and ann.id != self.unchecked(ann.id):
                return self.at(self.N('__ail_checked__AilPath__'), ann)
            return self.at(self.N('_AilPath'), ann)
        if kind == 'PL':
            if ann.value.id.startswith('__ail_checked_'):
                return self.at(ast.Subscript(value=self.N(ann.value.id), slice=self.N('_AilPath'), ctx=ast.Load()), ann)
            return self.at(ast.Subscript(value=self.N('list'), slice=self.N('_AilPath'), ctx=ast.Load()), ann)
        if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
            # Path | None
            ann.left = self.fix_ann(ann.left, where)
            ann.right = self.fix_ann(ann.right, where)
            return ann
        if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name) and ann.value.id == 'Optional':
            ann.slice = self.fix_ann(ann.slice, where)
            return ann
        self.refuse(ann, 'a Path inside %s is not built: a path is held in a plain variable, a field, a parameter, '
                         'a return value or a list[Path]; it is not a dict key, a set member or a tuple element.\n'
                         '  write instead: keep str(p) in the dict or set, or a list[Path]' % where)

    # ---- inference ---------------------------------------------------------------------------
    def lookup(self, name, kind):
        """Whether `name` (as the innermost scope that binds it sees it) is a path ('P') or a list of paths ('PL')."""
        for scope in reversed(self.scopes):
            if scope.kind == 'class':
                continue
            if name in scope.bound:
                return name in (scope.p if kind == 'P' else scope.pl)
        return False

    def user_func_kind(self, func):
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name in self.p_returns:
            return 'P'
        if name in self.pl_returns:
            return 'PL'
        return None

    def isP(self, e):
        if isinstance(e, ast.Name):
            return self.lookup(e.id, 'P')
        if isinstance(e, ast.Call):
            f = e.func
            if self.is_path_class(f):
                return True
            if isinstance(f, ast.Attribute):
                if self.is_path_class(f.value) and f.attr == 'cwd':
                    return True
                if f.attr in _P_METHODS and self.isP(f.value):
                    return True
            if isinstance(f, (ast.Name, ast.Attribute)) and self.user_func_kind(f) == 'P' \
                    and not (isinstance(f, ast.Attribute) and f.attr in _ALL_METHODS):
                return True
            return False
        if isinstance(e, ast.BinOp):
            return isinstance(e.op, ast.Div) and (self.isP(e.left) or self.isP(e.right))
        if isinstance(e, ast.Attribute):
            if e.attr == 'parent' and self.isP(e.value):
                return True
            return e.attr in self.p_attrs and not self.isP(e.value) and not self.is_path_class(e.value)
        if isinstance(e, ast.Subscript):
            return not isinstance(e.slice, ast.Slice) and self.isPL(e.value)
        if isinstance(e, ast.IfExp):
            return self.isP(e.body) and self.isP(e.orelse)
        return False

    def isPL(self, e):
        if isinstance(e, ast.Name):
            return self.lookup(e.id, 'PL')
        if isinstance(e, ast.Call):
            f = e.func
            if isinstance(f, ast.Attribute) and f.attr in _PL_METHODS and self.isP(f.value):
                return True
            if isinstance(f, ast.Name) and f.id in ('list', 'sorted', 'reversed') and len(e.args) >= 1 \
                    and f.id not in self.user_defs and self.isPL(e.args[0]):
                return True
            if isinstance(f, (ast.Name, ast.Attribute)) and self.user_func_kind(f) == 'PL' \
                    and not (isinstance(f, ast.Attribute) and f.attr in _ALL_METHODS):
                return True
            return False
        if isinstance(e, (ast.ListComp, ast.GeneratorExp)):
            return self.comp_elt_is_path(e)
        if isinstance(e, ast.List):
            return bool(e.elts) and all(self.isP(x) for x in e.elts)
        if isinstance(e, ast.Subscript):
            return isinstance(e.slice, ast.Slice) and self.isPL(e.value)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            return self.isPL(e.left) and self.isPL(e.right)
        if isinstance(e, ast.Attribute):
            return e.attr in self.pl_attrs
        return False

    def comp_elt_is_path(self, e):
        scope = _Scope('comp')
        self.scopes.append(scope)
        try:
            for gen in e.generators:
                self.bind_comp_target(scope, gen)
            return self.isP(e.elt)
        finally:
            self.scopes.pop()

    def bind_comp_target(self, scope, gen):
        target = gen.target
        names = [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]
        paths = set()
        if isinstance(target, ast.Name) and self.isPL(gen.iter):
            paths.add(target.id)
        elif isinstance(target, ast.Tuple) and len(target.elts) == 2 and isinstance(target.elts[1], ast.Name) \
                and isinstance(gen.iter, ast.Call) and isinstance(gen.iter.func, ast.Name) \
                and gen.iter.func.id == 'enumerate' and len(gen.iter.args) >= 1 and self.isPL(gen.iter.args[0]):
            paths.add(target.elts[1].id)
        for name in names:
            scope.bound.add(name)
            scope.p.discard(name)
        scope.p.update(paths)

    # ---- the bindings of a scope ---------------------------------------------------------------
    def bindings(self, body):
        """(name, kind, payload) for every binding in one scope."""
        out = []
        stack = list(body)
        while stack:
            n = stack.pop()
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        out.append((t.id, 'assign', n.value))
                    else:
                        for each in ast.walk(t):
                            if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Store):
                                out.append((each.id, 'other', None))
            elif isinstance(n, ast.AnnAssign):
                if isinstance(n.target, ast.Name):
                    out.append((n.target.id, 'ann', n))
            elif isinstance(n, ast.AugAssign):
                if isinstance(n.target, ast.Name):
                    out.append((n.target.id, 'aug', n))
            elif isinstance(n, ast.For):
                t = n.target
                if isinstance(t, ast.Name):
                    out.append((t.id, 'for', n.iter))
                elif isinstance(t, ast.Tuple) and len(t.elts) == 2 and isinstance(t.elts[1], ast.Name) \
                        and isinstance(n.iter, ast.Call) and isinstance(n.iter.func, ast.Name) \
                        and n.iter.func.id == 'enumerate' and len(n.iter.args) >= 1:
                    if isinstance(t.elts[0], ast.Name):
                        out.append((t.elts[0].id, 'other', None))
                    out.append((t.elts[1].id, 'for', n.iter.args[0]))
                else:
                    for each in ast.walk(t):
                        if isinstance(each, ast.Name):
                            out.append((each.id, 'other', None))
                stack.extend(n.body + n.orelse)
            elif isinstance(n, ast.With):
                for item in n.items:
                    if item.optional_vars is not None:
                        for each in ast.walk(item.optional_vars):
                            if isinstance(each, ast.Name):
                                out.append((each.id, 'other', None))
                stack.extend(n.body)
            elif isinstance(n, (ast.If, ast.While)):
                stack.extend(n.body + n.orelse)
            elif isinstance(n, ast.Try):
                stack.extend(n.body + n.orelse + n.finalbody)
                for handler in n.handlers:
                    if handler.name:
                        out.append((handler.name, 'other', None))
                    stack.extend(handler.body)
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                out.append((n.name, 'other', None))
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for alias in n.names:
                    out.append(((alias.asname or alias.name).split('.')[0], 'other', None))
        return out

    def solve(self, scope, body, args):
        binds = {}
        for name, kind, payload in self.bindings(body):
            binds.setdefault(name, []).append((kind, payload))
        scope.bound = set(binds)
        seeds_p, seeds_pl, params = set(), set(), set()
        if args is not None:
            for arg in args.posonlyargs + args.args + args.kwonlyargs:
                scope.bound.add(arg.arg)
                params.add(arg.arg)
                kind = self.ann_kind(arg.annotation)
                if kind == 'P':
                    seeds_p.add(arg.arg)
                elif kind == 'PL':
                    seeds_pl.add(arg.arg)
            for extra in (args.vararg, args.kwarg):
                if extra is not None:
                    scope.bound.add(extra.arg)
        starts = {n for n in binds if n not in params and all(k != 'other' for k, _ in binds[n])}
        scope.p = starts | seeds_p
        scope.pl = starts | seeds_pl

        def ok(name, seeds, valid):
            if name in params and name not in seeds:
                return False
            if name not in params and not binds.get(name):
                return False
            return all(valid(name, k, pl) for k, pl in binds.get(name, []))

        for _ in range(8):
            new_p = {n for n in scope.p if ok(n, seeds_p, self.valid_p)}
            new_pl = {n for n in scope.pl if ok(n, seeds_pl, self.valid_pl)}
            both = new_p & new_pl
            new_p -= both
            new_pl -= both
            if new_p == scope.p and new_pl == scope.pl:
                break
            scope.p, scope.pl = new_p, new_pl

    def valid_p(self, name, kind, payload):
        if kind == 'assign':
            return self.isP(payload)
        if kind == 'ann':
            return self.ann_kind(payload.annotation) == 'P'
        if kind == 'aug':
            return isinstance(payload.op, ast.Div)
        if kind == 'for':
            return self.isPL(payload)
        return False

    def valid_pl(self, name, kind, payload):
        if kind == 'assign':
            return self.isPL(payload)
        if kind == 'ann':
            return self.ann_kind(payload.annotation) == 'PL'
        if kind == 'aug':
            return isinstance(payload.op, ast.Add) and self.isPL(payload.value)
        return False

    def infer_all(self):
        """Fixed point over the module scope, every function scope, the fields and the return types."""
        functions = [n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)]
        self.p_returns, self.pl_returns = set(), set()
        names_seen = {}
        for f in functions:
            kind = self.ann_kind(f.returns)
            names_seen.setdefault(f.name, set()).add(kind)
        for name, kinds in names_seen.items():
            if kinds == {'P'}:
                self.p_returns.add(name)
            elif kinds == {'PL'}:
                self.pl_returns.add(name)
        for _ in range(4):
            before = (set(self.p_attrs), set(self.pl_attrs))
            self.fn_scopes = {}
            module = _Scope('module')
            self.scopes = [module]
            self.solve(module, [s for s in self.tree.body if not isinstance(s, (ast.FunctionDef, ast.ClassDef))], None)
            self.module_scope = module
            attr_values = {}
            self.solve_functions(self.tree.body, [module], attr_values)
            self.scopes = [module]
            # the module-level statements may assign attributes too
            self.collect_attrs([s for s in self.tree.body if not isinstance(s, (ast.FunctionDef, ast.ClassDef))], attr_values)
            self.p_attrs = {a for a, kinds in attr_values.items() if kinds == {'P'}}
            self.pl_attrs = {a for a, kinds in attr_values.items() if kinds == {'PL'}}
            if before == (self.p_attrs, self.pl_attrs):
                break
        self.scopes = [self.module_scope]

    def solve_functions(self, body, outer, attr_values):
        for node in self.defs_in(body):
            if isinstance(node, ast.ClassDef):
                for member in node.body:       # @dataclass fields: `root: Path`
                    if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                        attr_values.setdefault(member.target.id, set()).add(self.ann_kind(member.annotation) or 'other')
                self.solve_functions(node.body, outer, attr_values)
                continue
            scope = _Scope('function')
            self.scopes = outer + [scope]
            self.solve(scope, node.body, node.args)
            self.fn_scopes[id(node)] = scope
            self.collect_attrs(node.body, attr_values)
            self.solve_functions(node.body, outer + [scope], attr_values)

    @staticmethod
    def defs_in(body):
        """The defs and classes written in these statements, looking into blocks but not into defs."""
        found = []
        stack = list(reversed(body))
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                found.append(n)
            elif isinstance(n, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                children = list(n.body) + list(getattr(n, 'orelse', [])) + list(getattr(n, 'finalbody', []))
                for handler in getattr(n, 'handlers', []):
                    children.extend(handler.body)
                stack.extend(reversed(children))
        return found

    def collect_attrs(self, body, attr_values):
        stack = list(body)
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                continue
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Attribute):
                        kind = 'P' if self.isP(n.value) else 'PL' if self.isPL(n.value) else 'other'
                        attr_values.setdefault(t.attr, set()).add(kind)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Attribute):
                kind = self.ann_kind(n.annotation) or 'other'
                attr_values.setdefault(n.target.attr, set()).add(kind)
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Attribute):
                if not isinstance(n.op, ast.Div) or not self.isP(n.target):
                    attr_values.setdefault(n.target.attr, set()).add('other')
            stack.extend(ast.iter_child_nodes(n))

    def makes_path(self, e):
        """Whether `e` builds a new path (as opposed to reading a name, a field or a list element)."""
        if isinstance(e, ast.Call):
            f = e.func
            if self.is_path_class(f):
                return True
            if isinstance(f, ast.Attribute):
                if self.is_path_class(f.value) and f.attr == 'cwd':
                    return True
                return f.attr in _P_METHODS and self.isP(f.value)
            return False
        if isinstance(e, ast.BinOp):
            return isinstance(e.op, ast.Div) and (self.isP(e.left) or self.isP(e.right))
        if isinstance(e, ast.Attribute):
            return e.attr == 'parent' and self.isP(e.value)
        return False

    # ---- text of a path ------------------------------------------------------------------------
    def strarg(self, e):
        return self.pstr(e) if self.isP(e) else self.visit(e)

    def fold_join(self, parts):
        """posixpath.join over already-lowered string expressions."""
        self.need.add('pjoin')
        result = parts[0]
        for each in parts[1:]:
            result = self.call('_ail_pjoin', result, each)
        return result

    def pstr(self, e):
        """The text (a str expression) of the path-valued expression `e` (an original node)."""
        if isinstance(e, ast.Call):
            f = e.func
            if self.is_path_class(f):
                return self.at(self.path_ctor(e), e)
            if isinstance(f, ast.Attribute) and self.is_path_class(f.value) and f.attr == 'cwd':
                if e.args or e.keywords:
                    self.refuse(e, 'Path.cwd() takes no arguments')
                return self.at(self.call('_ail_os_getcwd'), e)
            if isinstance(f, ast.Attribute) and f.attr in _P_METHODS and self.isP(f.value):
                return self.at(self.p_method(e, f.attr), e)
        elif isinstance(e, ast.BinOp) and isinstance(e.op, ast.Div):
            return self.at(self.call('_ail_pl_joins', self.strarg(e.left), self.strarg(e.right)), e)
        elif isinstance(e, ast.Attribute) and e.attr == 'parent' and self.isP(e.value):
            return self.at(self.call('_ail_pl_parent', self.pstr(e.value)), e)
        return self.at(self.attr(self.visit(e), 's'), e)

    def pobj(self, e):
        """The `_AilPath` object for the path-valued expression `e`."""
        if self.makes_path(e):
            return self.at(self.obj(self.pstr(e)), e)
        return self.visit(e)

    def path_ctor(self, e):
        if e.keywords:
            self.refuse(e, 'Path() takes positional arguments only')
        if any(isinstance(a, ast.Starred) for a in e.args):
            self.refuse(e, 'Path(*args) is not built.\n  write instead: name each part')
        if not e.args:
            return self.C('.')
        parts = [self.strarg(a) for a in e.args]
        return self.call('_ail_pl_norm', self.fold_join(parts))

    def bind(self, node, name, params, defaults=None, required=0):
        """Positional / keyword arguments of a method call by parameter name (original nodes)."""
        defaults = defaults or {}
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            self.refuse(node, 'Path.%s() with * or ** arguments is not built.\n  write instead: name each argument' % name)
        if len(node.args) > len(params):
            self.refuse(node, 'Path.%s() takes at most %d arguments.\n  write instead: p.%s(%s)'
                        % (name, len(params), name, ', '.join(params)))
        got = dict(zip(params, node.args))
        for keyword in node.keywords:
            if keyword.arg not in params:
                self.refuse(node, "Path.%s() got an unexpected keyword argument '%s' (it is not built; built: %s).\n"
                                  "  write instead: leave it out; the default is what is built"
                            % (name, keyword.arg, ', '.join(params) or 'none'))
            if keyword.arg in got:
                self.refuse(node, "Path.%s() got multiple values for argument '%s'" % (name, keyword.arg))
            got[keyword.arg] = keyword.value
        for index, param in enumerate(params):
            if index < required and param not in got:
                self.refuse(node, "Path.%s() missing required argument '%s'.\n  write instead: p.%s(%s)"
                            % (name, param, name, ', '.join(params[:required])))
        return got

    def p_method(self, e, name):
        """The text of a method call that returns a path."""
        recv = self.pstr(e.func.value)
        if name in ('with_name', 'with_stem', 'with_suffix'):
            got = self.bind(e, name, ('x',), required=1)
            arg = self.strarg(got['x'])
            if name == 'with_name':
                return self.fn('_ail_pl_with_name', ('pl_edit',), recv, arg)
            if name == 'with_stem':
                return self.fn('_ail_pl_with_stem', ('pl_edit',), recv, arg)
            return self.fn('_ail_pl_with_suffix', ('pl_edit',), recv, arg)
        if name == 'resolve':
            got = self.bind(e, name, ('strict',))
            strict = got.get('strict')
            if strict is not None and not (isinstance(strict, ast.Constant) and strict.value is False):
                self.refuse(e, 'Path.resolve(strict=True) is not built.\n'
                               '  write instead: check p.exists() first, then p.resolve()')
            return self.fn('_ail_pl_resolve', ('pl_resolve',), recv)
        if name == 'absolute':
            self.bind(e, name, ())
            return self.fn('_ail_pl_absolute', ('pl_fs',), recv)
        if name == 'joinpath':
            if e.keywords:
                self.refuse(e, 'Path.joinpath() takes positional arguments only')
            parts = [recv] + [self.strarg(a) for a in e.args]
            return self.call('_ail_pl_norm', self.fold_join(parts))
        # rename / replace
        got = self.bind(e, name, ('target',), required=1)
        target = self.strarg(got['target'])
        return self.fn('_ail_pl_rename' if name == 'rename' else '_ail_pl_replace', ('pl_fs',), recv, target)

    # ---- expression visitors -------------------------------------------------------------------
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.cls_names:
            self.refuse(node, 'the class Path used as a value is not built: it is built for Path(...), Path.cwd() '
                              'and annotations.\n  write instead: call Path(...) where you need a path')
        return node

    def visit_BinOp(self, node):
        if self.makes_path(node):
            return self.pobj(node)
        if isinstance(node.op, ast.Mod) and (self.isP(node.left) or self.isP(node.right)
                                              or (isinstance(node.right, ast.Tuple) and any(self.isP(x) for x in node.right.elts))):
            self.refuse(node, '% formatting of a path is not built.\n  write instead: an f-string, f"{p}", or str(p)')
        return self.generic_visit(node)

    def visit_AugAssign(self, node):
        if isinstance(node.op, ast.Div) and self.isP(node.target):
            binop = ast.BinOp(left=copy.deepcopy(node.target), op=ast.Div(), right=node.value)
            ast.copy_location(binop, node)
            new = ast.Assign(targets=[node.target], value=self.pobj(binop))
            return self.at(new, node)
        if isinstance(node.target, ast.Name) and self.lookup(node.target.id, 'PL') and isinstance(node.op, ast.Add):
            return self.generic_visit(node)
        return self.generic_visit(node)

    def visit_Compare(self, node):
        has_path = self.isP(node.left) or any(self.isP(c) for c in node.comparators)
        if has_path:
            if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq)) \
                    and self.isP(node.left) and self.isP(node.comparators[0]):
                return self.at(ast.Compare(left=self.pstr(node.left), ops=node.ops,
                                           comparators=[self.pstr(node.comparators[0])]), node)
            if all(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops):
                return self.generic_visit(node)
            self.refuse(node, 'this comparison of a path is not built: == and != between two paths are.\n'
                              '  write instead: p == Path(text) for equality, sorted(paths) for the order, '
                              'str(p) < str(q) to compare the text')
        if self.isPL(node.left) or any(self.isPL(c) for c in node.comparators):
            self.refuse(node, 'a comparison or membership test on a list of paths is not built.\n'
                              '  write instead: compare the text, str(p) in [str(q) for q in paths]')
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)) and self.is_parts(comparator):
                self.parts_ok.add(id(comparator))
        return self.generic_visit(node)

    def is_parts(self, e):
        return isinstance(e, ast.Attribute) and e.attr == 'parts' and self.isP(e.value)

    def visit_JoinedStr(self, node):
        values = []
        for v in node.values:
            if isinstance(v, ast.FormattedValue) and self.isP(v.value):
                if v.format_spec is not None:
                    self.refuse(v, 'a format spec on a path (f"{p:...}") is not built: CPython refuses it too.\n'
                                   '  write instead: f"{str(p):...}"')
                text = self.pstr(v.value)
                if v.conversion == ord('r'):
                    text = self.call('_ail_pl_repr', text)
                elif v.conversion == ord('a'):
                    self.refuse(v, '!a on a path is not built')
                values.append(self.at(ast.FormattedValue(value=text, conversion=-1, format_spec=None), v))
            elif isinstance(v, ast.FormattedValue) and self.isPL(v.value) and not self.is_lazy(v.value):
                if v.format_spec is not None or v.conversion == ord('a'):
                    self.refuse(v, 'a format spec on a list of paths is not built.\n'
                                   '  write instead: a loop over the paths')
                values.append(self.at(ast.FormattedValue(
                    value=self.fn('_ail_pl_reprs', ('pl_core',), self.visit(v.value)), conversion=-1, format_spec=None), v))
            else:
                values.append(self.visit(v))
        node.values = values
        return node

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Load):
            if self.makes_path(node):
                return self.pobj(node)
            if self.is_path_class(node.value):
                self.refuse(node, 'Path.%s is not built. Built: Path(...) and Path.cwd()' % node.attr)
            if self.isP(node.value):
                return self.at(self.path_attr(node), node)
        return self.generic_visit(node)

    def path_attr(self, node):
        name = node.attr
        recv = self.pstr(node.value)
        if name == 'name':
            return self.fn('_ail_pl_name', ('pl_core',), recv)
        if name == 'stem':
            return self.fn('_ail_pl_stem', ('pl_core',), recv)
        if name == 'suffix':
            return self.fn('_ail_pl_suffix', ('pl_core',), recv)
        if name == 'suffixes':
            return self.fn('_ail_pl_suffixes', ('pl_core',), recv)
        if name in ('root', 'anchor'):
            return self.fn('_ail_pl_root', ('pl_core',), recv)
        if name == 'drive':
            return self.C('')
        if name == 'parts':
            if id(node) not in self.parts_ok:
                self.refuse(node, 'p.parts is a tuple in CPython and a list here, so it is built where the two '
                                  'behave the same: iterating it, indexing it with one number, len(p.parts), '
                                  'list(p.parts), sorted(), `x in p.parts` and "/".join(p.parts).\n'
                                  '  write instead: list(p.parts) (a list, whose slices and printing are lists)')
            return self.fn('_ail_pl_parts', ('pl_core',), recv)
        if name in _WRITE_INSTEAD or name in ('parents', 'name'):
            self.refuse(node, 'Path.%s is not built.\n  write instead: %s' % (name, _WRITE_INSTEAD.get(name, 'not built')))
        self.refuse(node, 'Path.%s is not built. Built: %s' % (name, BUILT))

    def no_hash(self, node, what):
        self.refuse(node, 'a path as %s is not built: it would have to be hashed, and the hash of a path is not built.\n'
                          '  write instead: use str(p) as the key or member, and Path(text) when you need the path back' % what)

    def visit_Dict(self, node):
        if any(k is not None and self.isP(k) for k in node.keys):
            self.no_hash(node, 'a dict key')
        return self.generic_visit(node)

    def visit_Set(self, node):
        if any(self.isP(e) for e in node.elts):
            self.no_hash(node, 'a set member')
        return self.generic_visit(node)

    def visit_Subscript(self, node):
        if self.isP(node.slice):
            self.no_hash(node, 'a subscript (a dict key or an index)')
        if self.is_parts(node.value):
            if isinstance(node.slice, ast.Slice):
                self.refuse(node, 'a slice of p.parts is a tuple in CPython.\n'
                                  '  write instead: list(p.parts)[a:b]')
            self.parts_ok.add(id(node.value))
        return self.generic_visit(node)

    def visit_Call(self, node):
        f = node.func
        # the class itself, and the methods that make paths
        if self.makes_path(node):
            return self.pobj(node)
        if isinstance(f, ast.Attribute) and self.is_path_class(f.value):
            self.refuse(node, 'Path.%s() is not built. Built: Path(...) and Path.cwd()%s' % (
                f.attr, '\n  write instead: %s' % _WRITE_INSTEAD[f.attr] if f.attr in _WRITE_INSTEAD else ''))
        if isinstance(f, ast.Attribute) and self.isP(f.value):
            return self.at(self.method_value(node), node)
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Constant) and isinstance(f.value.value, str) \
                and f.attr == 'format':
            node.args = [self.strarg(a) if self.isP(a) else self.visit(a) for a in node.args]
            node.keywords = [ast.keyword(arg=k.arg, value=self.strarg(k.value) if self.isP(k.value) else self.visit(k.value))
                             for k in node.keywords]
            return node
        if isinstance(f, ast.Attribute) and f.attr == 'join' and node.args and self.is_parts(node.args[0]):
            self.parts_ok.add(id(node.args[0]))
        if isinstance(f, ast.Attribute) and f.attr == 'sort' and self.isPL(f.value):
            self.refuse(node, 'list.sort() on a list of paths is not built.\n'
                              '  write instead: paths = sorted(paths)')
        if isinstance(f, ast.Name) and f.id not in self.user_defs:
            lowered = self.builtin_call(node, f.id)
            if lowered is not None:
                return lowered
        if isinstance(f, ast.Attribute) and f.attr == 'fspath' and isinstance(f.value, ast.Name) \
                and f.value.id in self.os_names and len(node.args) == 1 and not node.keywords:
            return self.at(self.strarg(node.args[0]), node)        # os.fspath(p) is the text of the path
        if self.fspath_site(f):
            node.func = self.visit(node.func)
            node.args = [self.strarg(a) for a in node.args]
            for keyword in node.keywords:
                keyword.value = self.strarg(keyword.value)
            return node
        if isinstance(f, ast.Attribute) and f.attr in _HASHING_METHODS and not self.isP(f.value) \
                and any(self.isP(a) for a in node.args):
            self.no_hash(node, 'an argument of %s()' % f.attr)
        # paths handed to anything else stay objects; lazy lists are checked by their own visit
        self.check_call_args(node)
        return self.generic_visit(node)

    def check_call_args(self, node):
        """A path handed to a user function has to meet a parameter annotated Path (a list of paths: list[Path])."""
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        defs = self.sigs.get(name)
        if not defs or (isinstance(f, ast.Attribute) and f.attr in _ALL_METHODS):
            return
        kinds = []
        for a in node.args:
            kinds.append('P' if self.isP(a) else 'PL' if self.isPL(a) else None)
        named = {k.arg: ('P' if self.isP(k.value) else 'PL' if self.isPL(k.value) else None) for k in node.keywords if k.arg}
        if not any(kinds) and not any(named.values()):
            return
        for fn, is_method in defs:
            params = fn.args.posonlyargs + fn.args.args
            if is_method and params and params[0].arg == 'self':
                params = params[1:]
            elif is_method and not isinstance(f, ast.Name):
                params = params[1:]
            for index, kind in enumerate(kinds):
                if kind is not None and index < len(params):
                    self.need_param(node, fn, params[index], kind)
            for pname, kind in named.items():
                if kind is not None:
                    for param in params + fn.args.kwonlyargs:
                        if param.arg == pname:
                            self.need_param(node, fn, param, kind)

    def need_param(self, node, fn, param, kind):
        if self.ann_snapshot[id(fn)][0].get(param.arg) == kind:
            return
        shown = 'Path' if kind == 'P' else 'list[Path]'
        self.refuse(node, "a path is passed to parameter '%s' of %s(), which is not annotated %s.\n"
                          "  write instead: annotate it, def %s(%s: %s, ...): the program text is how a path is "
                          "known to be one (or pass str(p) to a str parameter)"
                    % (param.arg, fn.name if fn.name != '__init__' else 'the constructor', shown, fn.name, param.arg, shown))

    def check_returns(self, node):
        """A function that returns a path says so in its annotation (callers rely on it)."""
        kind = self.ann_snapshot[id(node)][1]
        stack = list(node.body)
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(n, ast.Return) and n.value is not None:
                found = 'P' if self.isP(n.value) else 'PL' if self.isPL(n.value) else None
                if found is not None and kind != found:
                    shown = 'Path' if found == 'P' else 'list[Path]'
                    self.refuse(n, "%s() returns a path without saying so.\n"
                                   "  write instead: def %s(...) -> %s:" % (node.name, node.name, shown))
            stack.extend(ast.iter_child_nodes(n))

    def fspath_site(self, f):
        if isinstance(f, ast.Name):
            return f.id == 'open' and f.id not in self.user_defs or f.id in self.from_os
        root = f
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            if root.id in self.os_names:
                return True
            if root.id in self.from_os and isinstance(f, ast.Attribute):
                return True
        return False

    def builtin_call(self, node, name):
        args = node.args
        if name == 'str' and len(args) == 1 and not node.keywords and self.isP(args[0]):
            return self.pstr(args[0])
        if name == 'repr' and len(args) == 1 and not node.keywords and self.isP(args[0]):
            return self.at(self.call('_ail_pl_repr', self.pstr(args[0])), node)
        if name in ('str', 'repr') and len(args) == 1 and not node.keywords and self.isPL(args[0]) \
                and not self.is_lazy(args[0]):
            return self.at(self.fn('_ail_pl_reprs', ('pl_core',), self.visit(args[0])), node)
        if name in ('str', 'repr') and len(args) == 1 and self.is_lazy(args[0]):
            self.refuse(node, '%s() of p.iterdir() / p.glob() is not built: CPython shows a generator.\n'
                              '  write instead: %s(list(p.iterdir()))' % (name, name))
        if name == 'print':
            keep = []
            for a in args:
                if self.isP(a):
                    keep.append(self.pstr(a))
                elif self.is_lazy(a):
                    self.refuse(node, 'print() of p.iterdir() / p.glob() is not built: CPython shows a generator.\n'
                                      '  write instead: print(list(p.iterdir())) or print(sorted(p.iterdir()))')
                elif self.isPL(a):
                    keep.append(self.fn('_ail_pl_reprs', ('pl_core',), self.visit(a)))
                else:
                    keep.append(self.visit(a))
            node.args = keep
            node.keywords = [self.visit(k) for k in node.keywords]
            return node
        if name == 'sorted' and args and (self.isPL(args[0]) or self.is_lazy(args[0])):
            reverse = self.C(False)
            for keyword in node.keywords:
                if keyword.arg == 'reverse':
                    reverse = self.visit(keyword.value)
                else:
                    self.refuse(node, 'sorted(paths, %s=...) is not built: paths sort as CPython sorts them, part by part.\n'
                                      '  write instead: sorted(paths), or sorted(p.name for p in paths)' % (keyword.arg or '**'))
            if len(args) != 1:
                self.refuse(node, 'sorted() takes one iterable')
            self.mark_lazy(args[0])
            return self.at(self.call('_ail_pl_sorted', self.visit(args[0]), reverse), node)
        if name in _NO_PATHS and args and (self.isPL(args[0]) or self.is_lazy(args[0])):
            self.refuse(node, '%s() of paths is not built.\n  write instead: apply it to the names, '
                              'e.g. %s(p.name for p in paths), or use sorted(paths)' % (name, name))
        if name in _LAZY_OK and args:
            for a in args:
                self.mark_lazy(a)
        if name in _PARTS_OK:
            for a in args:
                if self.is_parts(a):
                    self.parts_ok.add(id(a))
        if name == 'isinstance' and len(args) == 2 and any(self.is_path_class(n) for n in ast.walk(args[1])):
            self.refuse(node, 'isinstance(x, Path) is not built: a path is known by the program text.')
        if name in ('hash', 'id') and args and (self.isP(args[0])):
            self.refuse(node, '%s() of a path is not built' % name)
        return None

    def is_lazy(self, e):
        return isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr in _PL_METHODS \
            and self.isP(e.func.value)

    def mark_lazy(self, e):
        if self.is_lazy(e):
            self.lazy_ok.add(id(e))

    def method_value(self, node):
        """A method call on a path whose result is not a path."""
        name = node.func.attr
        recv_node = node.func.value
        if name in _PL_METHODS:
            if id(node) not in self.lazy_ok:
                self.refuse(node, 'p.%s() is an iterator in CPython and a list here, so it is built where the two '
                                  'behave the same: a for loop, a comprehension, or inside list(), sorted(), '
                                  'enumerate(), any() ...\n  write instead: for q in p.%s(): ... or entries = '
                                  'sorted(p.%s())' % (name, name, name))
            recv = self.pstr(recv_node)
            if name == 'iterdir':
                self.bind(node, name, ())
                return self.fn('_ail_pl_iterdir', ('pl_fs',), recv)
            got = self.bind(node, name, ('pattern',), required=1)
            pattern = self.strarg(got['pattern'])
            return self.fn('_ail_pl_glob' if name == 'glob' else '_ail_pl_rglob', ('pl_glob',), recv, pattern)
        if name in _PLAIN_METHODS:
            return self.plain_method(node, name, recv_node)
        if name in _P_METHODS:
            return self.pobj(node)
        if name in _WRITE_INSTEAD:
            self.refuse(node, 'Path.%s() is not built.\n  write instead: %s' % (name, _WRITE_INSTEAD[name]))
        self.refuse(node, 'Path.%s() is not built. Built: %s' % (name, BUILT))

    def open_call(self, node, recv, mode, extra):
        call = ast.Call(func=self.N('open'), args=[recv, self.C(mode)], keywords=extra)
        return self.at(call, node)

    def plain_method(self, node, name, recv_node):
        recv = self.pstr(recv_node)
        if name in ('exists', 'is_file', 'is_dir'):
            self.bind(node, name, ())
            fn = {'exists': '_ail_pl_exists', 'is_file': '_ail_pl_isfile', 'is_dir': '_ail_pl_isdir'}[name]
            return self.fn(fn, ('pl_fs',), recv)
        if name == 'is_absolute':
            self.bind(node, name, ())
            return self.fn('_ail_pl_isabs', ('pl_core',), recv)
        if name == 'as_posix':
            self.bind(node, name, ())
            return recv
        if name == 'read_text':
            got = self.bind(node, name, ('encoding', 'errors'))
            kws = [ast.keyword(arg=k, value=self.visit(got[k])) for k in ('encoding', 'errors') if k in got]
            return self.at(ast.Call(func=self.attr(self.open_call(node, recv, 'r', kws), 'read'), args=[], keywords=[]), node)
        if name == 'write_text':
            got = self.bind(node, name, ('data', 'encoding', 'errors', 'newline'), required=1)
            kws = [ast.keyword(arg=k, value=self.visit(got[k])) for k in ('encoding', 'errors', 'newline') if k in got]
            return self.at(ast.Call(func=self.attr(self.open_call(node, recv, 'w', kws), 'write'),
                                    args=[self.visit(got['data'])], keywords=[]), node)
        if name == 'read_bytes':
            self.bind(node, name, ())
            return self.at(ast.Call(func=self.attr(self.open_call(node, recv, 'rb', []), 'read'), args=[], keywords=[]), node)
        if name == 'write_bytes':
            got = self.bind(node, name, ('data',), required=1)
            return self.at(ast.Call(func=self.attr(self.open_call(node, recv, 'wb', []), 'write'),
                                    args=[self.visit(got['data'])], keywords=[]), node)
        if name == 'open':
            order = ('mode', 'buffering', 'encoding', 'errors', 'newline')
            got = self.bind(node, name, order)
            mode = got.get('mode')
            args = [recv]
            if mode is not None:
                args.append(self.visit(mode))
            keywords = [ast.keyword(arg=k, value=self.visit(got[k])) for k in order[1:] if k in got]
            if 'buffering' not in got:
                keywords.insert(0, ast.keyword(arg='buffering', value=self.C(-1)))     # keeps open() off the legacy intrinsics
            call = ast.Call(func=self.N('open'), args=args, keywords=keywords)
            return self.at(call, node)
        if name == 'mkdir':
            got = self.bind(node, name, ('mode', 'parents', 'exist_ok'))
            mode = self.visit(got['mode']) if 'mode' in got else self.C(511)
            parents = self.visit(got['parents']) if 'parents' in got else self.C(False)
            exist_ok = self.visit(got['exist_ok']) if 'exist_ok' in got else self.C(False)
            return self.fn('_ail_pl_mkdir', ('pl_fs',), recv, mode, parents, exist_ok)
        if name == 'unlink':
            got = self.bind(node, name, ('missing_ok',))
            flag = self.visit(got['missing_ok']) if 'missing_ok' in got else self.C(False)
            return self.fn('_ail_pl_unlink', ('pl_fs',), recv, flag)
        if name == 'rmdir':
            self.bind(node, name, ())
            return self.call('_ail_os_rmdir', recv)
        self.refuse(node, 'Path.%s() is not built' % name)

    # ---- statements ----------------------------------------------------------------------------
    def visit_For(self, node):
        self.mark_lazy(node.iter)
        if self.is_parts(node.iter):
            self.parts_ok.add(id(node.iter))
        it = node.iter
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'enumerate' and it.args:
            self.mark_lazy(it.args[0])
        return self.generic_visit(node)

    def comp(self, node):
        scope = _Scope('comp')
        self.scopes.append(scope)
        try:
            for gen in node.generators:
                self.mark_lazy(gen.iter)
                if self.is_parts(gen.iter):
                    self.parts_ok.add(id(gen.iter))
                it = gen.iter
                if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'enumerate' and it.args:
                    self.mark_lazy(it.args[0])
                original = copy.copy(gen)
                gen.iter = self.visit(gen.iter)
                self.bind_comp_target(scope, original)
                gen.ifs = [self.visit(c) for c in gen.ifs]
            if isinstance(node, ast.DictComp):
                if self.isP(node.key):
                    self.no_hash(node, 'a dict key')
                node.key = self.visit(node.key)
                node.value = self.visit(node.value)
            else:
                node.elt = self.visit(node.elt)
        finally:
            self.scopes.pop()
        return node

    def visit_ListComp(self, node):
        return self.comp(node)

    def visit_GeneratorExp(self, node):
        return self.comp(node)

    def visit_SetComp(self, node):
        scope_check = self.comp_elt_is_path(node) if isinstance(node, ast.SetComp) else False
        if scope_check:
            self.no_hash(node, 'a set member')
        return self.comp(node)

    def visit_DictComp(self, node):
        return self.comp(node)

    def visit_Lambda(self, node):
        scope = _Scope('function')
        scope.bound = {a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
        self.scopes.append(scope)
        try:
            node.body = self.visit(node.body)
        finally:
            self.scopes.pop()
        return node

    def visit_FunctionDef(self, node):
        scope = self.fn_scopes.get(id(node))
        if scope is None:
            scope = _Scope('function')
            self.solve(scope, node.body, node.args)
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            arg.annotation = self.fix_ann(arg.annotation, 'a parameter annotation')
        node.returns = self.fix_ann(node.returns, 'a return annotation')
        self.scopes.append(scope)
        try:
            self.check_returns(node)
        finally:
            self.scopes.pop()
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        node.args.kw_defaults = [self.visit(d) if d is not None else None for d in node.args.kw_defaults]
        self.scopes.append(scope)
        try:
            node.body = self.block(node.body)
        finally:
            self.scopes.pop()
        return node

    def visit_ClassDef(self, node):
        scope = _Scope('class')
        self.scopes.append(scope)
        try:
            node.body = self.block(node.body)
        finally:
            self.scopes.pop()
        return node

    def visit_AnnAssign(self, node):
        node.annotation = self.fix_ann(node.annotation, 'an annotation')
        if node.value is not None:
            node.value = self.visit(node.value)
        node.target = self.visit(node.target)
        return node

    def block(self, stmts):
        out = []
        for stmt in stmts:
            new = self.visit(stmt)
            if new is None:
                continue
            if isinstance(new, list):
                out.extend(new)
            else:
                out.append(new)
        return out

    def visit_Module(self, node):
        node.body = self.block(node.body)
        return node

    # ---- the driver ----------------------------------------------------------------------------
    def run(self):
        self.infer_all()
        self.scopes = [self.module_scope]
        self.visit(self.tree)
        for node in self.import_nodes:
            if node in self.tree.body:
                index = self.tree.body.index(node)
                self.tree.body[index] = self.at(ast.Pass(), node)
        ast.fix_missing_locations(self.tree)


def rewrite_tree(tree, Unsupported, general=False):
    """Lower pathlib.Path in `tree` (in place). Returns the set of prelude snippets the program needs, or
    None when the program does not import pathlib."""
    global ACTIVE
    ACTIVE = False
    lowerer = _Lowerer(tree, Unsupported, general)
    if not lowerer.scan():
        return None
    ACTIVE = True
    import filelib
    if filelib.target_windows():
        lowerer.refuse(lowerer.import_nodes[0], 'pathlib is built for POSIX targets only (the paths of this platform are '
                                                'ntpath paths, whose parsing is not built).\n'
                                                '  write instead: os.path.join / os.path.basename ... on str')
    import filelib_prelude
    import pathlib_prelude
    pathlib_prelude.register()
    filelib_prelude.SNIPPETS['pl_class'] = (pathlib_prelude.CLASS_GENERAL if general else pathlib_prelude.CLASS_PLAIN, ())
    lowerer.run()
    return lowerer.need
