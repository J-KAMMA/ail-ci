"""Tuples in the Python syntax, lowered onto what the compiler already builds.

`return a, b`, `q, r = f(x)`, `divmod`, tuple-typed locals and parameters, `t[0]`, `for i, (a, b) in
enumerate(pairs)`, `list[tuple[int, int]]`, tuple comparison and printing, `dict[tuple[int, int], int]`,
`set[tuple[int, int]]`, `heappush(h, (d, v))`, `sorted(xs, key=lambda t: (t[1], -t[0]))`.

A tuple type is a class `_AilT_<codes>` with fields f0, f1, ... (tuplegen.py), a tuple expression a constructor
call, `t[k]` a field read, an unpack a few field reads.  A dict or set that mentions a tuple becomes an
insertion-ordered open-addressing table class (tuplegen.Table: plain Python-syntax source compiled by the
ordinary typed path).  Tuples are immutable, so sharing the instance is CPython's behaviour too.  The C runtime
gets nothing new.  A program whose tuple uses are all ones the compiler already builds (literal swaps, sort-key
tuples, `%` operands, lists of numeric tuples) is returned as written, byte for byte.

Anything not built is refused by name: the source is left as written and the reason goes to `notes`.

The pass runs twice over a program: the first run (output discarded) settles what a later statement tells
about an earlier empty `[]` / `{}` and the return types of unannotated functions; the second run emits.
"""
import ast
import sys
from pathlib import Path

_here = str(Path(__file__).parent)
if _here not in sys.path:
    sys.path.insert(0, _here)

from tupcommon import *  # noqa: E402,F401,F403
from tupexpr import Exprs  # noqa: E402
from tupcalls import Calls  # noqa: E402
from tupstmt import Stmts  # noqa: E402
from tuplam import Lams  # noqa: E402

CANDIDATE_NAMES = {'tuple', 'Tuple', 'modf', 'divmod', 'zip', 'partition', 'rpartition', 'heappush', 'heappop'}


def candidate(tree):
    """Cheap test: could this program use anything this pass lowers?"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and isinstance(node.ctx, ast.Load):
            return True
        if isinstance(node, ast.Name) and node.id in CANDIDATE_NAMES:
            return True
        if isinstance(node, ast.Attribute) and node.attr in CANDIDATE_NAMES:
            return True
        if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple):
            return True
        if isinstance(node, ast.Lambda):
            return True
    return False


class Lower(Stmts, Calls, Lams, Exprs):
    def __init__(self, source, hints=None, rets=None):
        self.source = source
        self.tree = ast.parse(source)
        self.gen = G.Gen()
        self.hints = {} if hints is None else hints
        self.rets_in = {} if rets is None else rets
        self.rets_out = {}
        self.forced = False
        self.quiet = 0
        self.nohoist = 0
        self.fresh_names = set()
        self.errors = []
        self.counter = 0
        self.names = {n.id for n in ast.walk(self.tree) if isinstance(n, ast.Name)} | {
            n.arg for n in ast.walk(self.tree) if isinstance(n, ast.arg)}
        self.classes = {}
        self.ctor_fields = {}
        self.methods = {}
        self.funcs = {}
        self.sigs = {}
        self.consts = {}
        self.rowconst = {}
        self.tupconst = {}
        self.modalias = {}
        self.fromnames = {}
        self.env = {}
        self.alias = {}
        self.pre = []
        self.pending = []
        self.rets = []
        self.cur = None
        self.fnkey = '<module>'
        self.lam_alias = {}
        self.lamdefs = []
        self.lam_counter = 0
        self.specs = {}
        self.pristine = {}
        self.binds = {}

    # ------------------------------------------------------------------------------------------
    def collect(self):
        tree = self.tree
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self.classes[node.name] = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in ('heapq', 'math', 'sys', 'functools', 'bisect'):
                        self.modalias[a.asname or a.name] = a.name
            elif isinstance(node, ast.ImportFrom) and node.module in ('heapq', 'math', 'functools', 'bisect'):
                for a in node.names:
                    self.fromnames[a.asname or a.name] = (node.module, a.name)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.pristine[node.name] = fresh_copy(node)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self.collect_class(node)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.funcs[node.name] = self.make_sig(node, None)

    def make_sig(self, fn, owner):
        sig = Sig(fn, owner)
        args = fn.args
        plain = [*args.posonlyargs, *args.args]
        ndef = len(args.defaults)
        for i, a in enumerate(plain):
            if owner and i == 0:
                t = ('cls', owner)
            else:
                try:
                    t = self.sig_ann(a.annotation)
                except Refused as exc:
                    self.errors.append(exc.args[0])
                    t = None
            sig.params.append((a.arg, t, i >= len(plain) - ndef))
        for a, dflt in zip(args.kwonlyargs, args.kw_defaults):
            try:
                t = self.ann(a.annotation)
            except Refused as exc:
                self.errors.append(exc.args[0])
                t = None
            sig.params.append((a.arg, t, dflt is not None))
        try:
            sig.ret = self.sig_ann(fn.returns) if fn.returns is not None else None
        except Refused as exc:
            self.errors.append(exc.args[0])
        key = (owner or '') + '.' + fn.name
        if fn.returns is None and key in self.rets_in:
            sig.ret = self.rets_in[key]
        self.sigs[id(fn)] = sig
        return sig

    def collect_class(self, node):
        name = node.name
        fields = self.classes[name]
        dataclass = any((isinstance(d, ast.Name) and d.id == 'dataclass') or
                        (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'dataclass')
                        or (isinstance(d, ast.Attribute) and d.attr == 'dataclass') for d in node.decorator_list)
        order = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                try:
                    fields[item.target.id] = self.ann(item.annotation)
                except Refused as exc:
                    self.errors.append(exc.args[0])
                order.append((item.target.id, fields.get(item.target.id)))
        init = next((i for i in node.body if isinstance(i, ast.FunctionDef) and i.name == '__init__'), None)
        if init is not None:
            sig = self.make_sig(init, name)
            self.methods[(name, '__init__')] = sig
            params = {p[0]: p[1] for p in sig.params}
            self.ctor_fields[name] = [(p[0], p[1]) for p in sig.params[1:]]
            for sub in ast.walk(init):
                if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Attribute) \
                        and isinstance(sub.targets[0].value, ast.Name) and sub.targets[0].value.id == 'self':
                    v = sub.value
                    fields.setdefault(sub.targets[0].attr, params.get(v.id) if isinstance(v, ast.Name) else None)
                elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Attribute):
                    try:
                        fields[sub.target.attr] = self.ann(sub.annotation)
                    except Refused:
                        pass
        elif dataclass or order:
            self.ctor_fields[name] = order
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name != '__init__':
                self.methods[(name, item.name)] = self.make_sig(item, name)

    # ------------------------------------------------------------------------------------------
    def function(self, fn, owner=None):
        sig = self.sigs[id(fn)]
        self.cur = sig
        self.fnkey = (owner or '') + '.' + fn.name
        self.env = {}
        self.alias = {}
        self.lam_alias = {}
        self.scan_binds(fn)
        self.rets = []
        self.pending = []
        args = fn.args
        plain = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        for a, p in zip(plain, sig.params):
            if a.annotation is not None:
                try:
                    a.annotation, t = self.sig_map_ann(a.annotation)
                except Refused as exc:
                    self.errors.append(exc.args[0])
                    continue
                if is_tuple(t) or is_table(t) or (isinstance(t, tuple) and t[0] == 'opt' and has_tuple(t)):
                    self.force()
            self.env[a.arg] = p[1]
        try:
            args.defaults = [self.exv(d, p[1])[0] for d, p in zip(
                args.defaults, sig.params[len(args.posonlyargs) + len(args.args) - len(args.defaults):])]
        except Refused as exc:
            self.errors.append(exc.args[0])
        if fn.returns is not None:
            try:
                fn.returns, rt = self.sig_map_ann(fn.returns)
                if is_tuple(rt) or is_table(rt) or (isinstance(rt, tuple) and rt[0] == 'opt' and has_tuple(rt)):
                    self.force()
            except Refused as exc:
                self.errors.append(exc.args[0])
        fn.body = self.stmts(fn.body)
        if fn.returns is None:
            seen = [t for t in self.rets if t not in (None, 'none')]
            if seen and all(known(t) for t in seen) and len({code(t) for t in seen}) == 1 and has_tuple(seen[0]):
                self.rets_out[self.fnkey] = seen[0]
                if self.fnkey in self.rets_in:
                    self.use_type(seen[0])
                    fn.returns = ast.parse(ann_text(seen[0]), mode='eval').body
                    self.force()
        for key, t in self.pending:
            dt = deep(t)
            if dt is not None and known(dt):
                self.hints[key] = dt
        self.cur = None

    def class_(self, node):
        name = node.name
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                try:
                    item.annotation, t = self.map_ann(item.annotation)
                    if has_tuple(t):
                        self.force()
                    if item.value is not None:
                        item.value = self.exv(item.value, t, 'row')[0]
                except Refused as exc:
                    self.errors.append(exc.args[0])
            elif isinstance(item, ast.FunctionDef):
                self.function(item, name)

    def module_stmt(self, node):
        """Module-level statements other than def / class."""
        if isinstance(node, ast.ImportFrom) and node.module == 'functools' and all(
                a.name == 'reduce' for a in node.names):
            return []
        if isinstance(node, ast.Import) and all(a.name == 'functools' for a in node.names):
            return []
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return [node]
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            return self.module_assign(node)
        self.cur = None
        self.fnkey = '<module>'
        self.env = {}
        self.alias = {}
        return self.stmts([node])

    def module_assign(self, node):
        nm = node.targets[0].id
        v = node.value
        cols = None
        if isinstance(v, ast.List) and v.elts and all(isinstance(e, ast.Tuple) for e in v.elts):
            cols = [e.elts for e in v.elts]
        elif isinstance(v, ast.Tuple) and v.elts:
            cols = [v.elts]
        if cols is not None:
            arity = len(cols[0])
            ok = all(len(c) == arity for c in cols) and arity >= 1
            types = []
            if ok:
                for i in range(arity):
                    ts = set()
                    for c in cols:
                        e = c[i]
                        k = e.operand if isinstance(e, ast.UnaryOp) and isinstance(e.op, (ast.USub, ast.UAdd)) else e
                        if isinstance(k, ast.Constant) and type(k.value) in (int, float):
                            ts.add(type(k.value))
                        else:
                            ok = False
                    if ok and len(ts) != 1:
                        ok = False
                    if ok:
                        types.append(INT if ts == {int} else FLT)
            if not ok:
                self.errors.append((node.lineno, 'a module-level tuple constant must be numbers only, one type per '
                                    'position (DIRS = [(0, 1), (1, 0)]); build other tuples inside a function'))
                return [node]
            if isinstance(v, ast.List) and not rowconst_in_place(self.tree, nm):
                # kept as columns, the list is rebuilt wherever it is used as a value: a function that
                # changes it, or a name bound to it, would change a copy (DIFFERENCES C68)
                self.errors.append((node.lineno, 'the module-level list %s is passed, bound or returned as a value; '
                                    'a list of number tuples is built here only when it is read in place (for, '
                                    '%s[i], len(%s)); build it in main() and pass it down' % (nm, nm, nm)))
                return [node]
            t = ('tuple', tuple(types))
            self.force()
            self.use_type(t)
            out = []
            for i in range(arity):
                col = ast.List(elts=[c[i] for c in cols], ctx=ast.Load()) if isinstance(v, ast.List) else c[i]
                out.append(ast.Assign(targets=[ast.Name(id='%s__c%d' % (nm, i), ctx=ast.Store())], value=col,
                                      lineno=node.lineno))
            if isinstance(v, ast.List):
                self.rowconst[nm] = t
                self.consts[nm] = ('list', t)
                self.gen.rowconst(nm, t)
            else:
                self.tupconst[nm] = t
                self.consts[nm] = t
            return out
        self.cur = None
        self.fnkey = '<module>'
        self.env = {}
        t = self.typeof(v)
        if t is not None and has_tuple(t):
            self.errors.append((node.lineno, 'a module-level constant holding tuples must be a literal list of '
                                'number tuples (DIRS = [(0, 1), (1, 0)]); build other tuples inside a function'))
        self.consts[nm] = t
        return [node]

    def process(self):
        self.collect()
        body = []
        for node in self.tree.body:
            try:
                if isinstance(node, ast.FunctionDef):
                    self.function(node)
                    body.append(node)
                elif isinstance(node, ast.ClassDef):
                    self.class_(node)
                    body.append(node)
                else:
                    body.extend(self.module_stmt(node))
            except Refused as exc:
                self.errors.append(exc.args[0])
                body.append(node)
        while self.lamdefs:
            node = self.lamdefs.pop(0)
            try:
                self.function(node)
            except Refused as exc:
                self.errors.append(exc.args[0])
            body.append(node)
        self.tree.body = body

    def text(self):
        ast.fix_missing_locations(self.tree)
        out = ast.unparse(self.tree)
        helpers = self.gen.source()
        return out.rstrip('\n') + ('\n\n\n' + helpers if helpers else '') + '\n'


def rewrite(source, notes=None):
    """The program with its tuples lowered; the source as written when no tuple use needs it (or when one is not
    built -- the reason is then added to `notes`)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not candidate(tree):
        return source
    try:
        first = Lower(source)
        first.process()
        second = Lower(source, first.hints, first.rets_out)
        second.process()
        if second.errors:
            # the compiler refuses the program with its own message; these name what was not built
            if notes is not None:
                notes.extend(sorted(set(second.errors)))
            return source
        if not second.forced:
            return source
        return second.text()
    except Refused as exc:
        if notes is not None:
            notes.append(exc.args[0])
        return source
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, RecursionError, AssertionError) as exc:
        if notes is not None:
            notes.append((1, 'the tuple rewrite could not handle this program (%s: %s); simplify the tuple use '
                          'or report it' % (type(exc).__name__, exc)))
        return source


if __name__ == '__main__':
    src = Path(sys.argv[1]).read_text(encoding='utf-8')
    notes = []
    out = rewrite(src, notes)
    print(out)
    for n in notes:
        print('NOTE', n, file=sys.stderr)
