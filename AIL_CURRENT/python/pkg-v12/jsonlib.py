"""json.loads / json.dumps (and load / dump on stdin / stdout), lowered to typed helper functions (called
from stdlib3.py before the statements are lowered).

There are no dynamic values here, so both sides work from a type the program has written down:

* json.loads(s) needs the type it produces: the annotation of the variable it is assigned to
  (`data: dict[str, int] = json.loads(s)`), the return annotation of the function it is returned from,
  an annotated variable assigned later, or an annotated parameter of a function it is passed to. The
  types are int, float, str, bool, list[T], list[list[T]] and dict[str, T] (what the compiler holds:
  there is no dict[str, bool], dict[str, list[T]] or list[dict[...]]). The document is first checked
  by a scanner that mirrors CPython's, so every syntax error is the same ValueError with the same
  "line L column C (char P)" message (json.JSONDecodeError is spelt ValueError in an except clause);
  then it is read into the declared type. A document that is valid JSON but does not fit the declared
  type (a float for an int, an int for a float, null, a different container, an integer beyond int64,
  a lone surrogate) is a RuntimeError naming what was found: CPython would hand back a value of
  another type, and a silent coercion would print differently.
* json.dumps(x[, indent=, sort_keys=, separators=, ensure_ascii=, allow_nan=]) needs the type of x: a
  literal (dict / list / str / number / bool / None, nested), a variable with a type annotation or a
  first assignment from such a value, an element of one, or the result of a function with an annotated
  return. The text is CPython's byte for byte (the separators, ensure_ascii escapes with surrogate pairs,
  float repr, NaN / Infinity, nesting indents, empty containers as [] and {}). Other arguments
  (default=, cls=, skipkeys=) are refused by name.
"""
import ast
import copy
import json as _json
import sys
import textwrap

from iterlower import _name, _mark, _call, _locate

SCALARS = ('int', 'float', 'str', 'bool')
LEAF_LIST = ('int', 'float', 'str', 'bool')
LEAF_NEST = ('int', 'float', 'str')


def S():
    import stdlib3
    return stdlib3


def refuse(node, text):
    S().refuse(node, text)


def mangle(t):
    if t[0] in SCALARS:
        return t[0]
    if t[0] == 'list':
        return 'list_' + mangle(t[1])
    return 'dict_%s_%s' % (t[1][0], mangle(t[2]))


def render(t):
    if t[0] in SCALARS:
        return t[0]
    if t[0] == 'list':
        return 'list[%s]' % render(t[1])
    return 'dict[%s, %s]' % (t[1][0], render(t[2]))


def ann_to_type(node):
    """The type an annotation node stands for, or None."""
    if isinstance(node, ast.Name):
        name = node.id
        if name.startswith('__ail_checked_') and name.endswith('__'):
            name = name[len('__ail_checked_'):-2]
            if name == 'flist':                        # a returned list[float]
                return ('list', ('float',))
        return (name,) if name in SCALARS else None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        head = node.value.id
        if head.startswith('__ail_checked_'):          # a returned list[T] is annotated __ail_checked_list[T]
            head = head[len('__ail_checked_'):]
        if head in ('list', 'List'):
            inner = ann_to_type(node.slice)
            return ('list', inner) if inner else None
        if head in ('dict', 'Dict') and isinstance(node.slice, ast.Tuple) and len(node.slice.elts) == 2:
            key, value = ann_to_type(node.slice.elts[0]), ann_to_type(node.slice.elts[1])
            if key and value and key[0] in ('str', 'int'):
                return ('dict', key, value)
    return None


def loads_ok(t):
    """Types json.loads can produce (what the compiler can hold)."""
    if t[0] in SCALARS:
        return True
    if t[0] == 'list':
        inner = t[1]
        if inner[0] in LEAF_LIST:
            return True
        return inner[0] == 'list' and inner[1][0] in LEAF_NEST
    if t[0] == 'dict':
        return t[1][0] == 'str' and t[2][0] in LEAF_NEST
    return False


def dumps_ok(t):
    if t[0] in SCALARS:
        return True
    if t[0] == 'list':
        inner = t[1]
        if inner[0] in LEAF_LIST:
            return True
        return inner[0] == 'list' and inner[1][0] in LEAF_NEST
    if t[0] == 'dict':
        return t[1][0] in ('str', 'int') and t[2][0] in LEAF_NEST
    return False


class Options:
    def __init__(self, pad, pretty, isep, ksep, asc, srt, nan):
        self.pad, self.pretty, self.isep, self.ksep = pad, pretty, isep, ksep
        self.asc, self.srt, self.nan = asc, srt, nan

    def expr(self):
        values = [self.pad, self.pretty, self.isep, self.ksep, self.asc, self.srt, self.nan]
        return _mark(_call(ast.Name(id='_AilJo', ctx=ast.Load()), *[ast.Constant(value=v) for v in values]))


class Json:
    def __init__(self, imports, tree):
        self.imports = imports
        self.tree = tree
        self.loads_types = {}          # mangled -> type
        self.slow_types = {}           # mangled -> type: loaded in place, the scanner + parser only as the fallback
        self.params = set()
        self.temps = 0
        self.dumps_types = {}
        self.uses_dumps = False
        self.functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.env = {}
        self.fn = None

    # -- finding json names ---------------------------------------------------------------------------
    def jname(self, call):
        if isinstance(call, ast.Call):
            found = self.imports.resolve(call.func)
            if found and found[0] == 'json':
                return found[1]
        return None

    def run(self):
        self.collect_env(self.tree, module=True)
        self.tree = Resolver(self).visit(self.tree)
        self.except_names()
        self.add_helpers()

    def except_names(self):
        """json.JSONDecodeError is the ValueError the scanner raises."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                node.type = self.fix_exception(node.type)

    def fix_exception(self, node):
        if isinstance(node, ast.Tuple):
            node.elts = [self.fix_exception(e) for e in node.elts]
            return node
        found = self.imports.resolve(node)
        if found and found[0] == 'json' and found[1] in ('JSONDecodeError', 'decoder.JSONDecodeError'):
            return ast.copy_location(ast.Name(id='ValueError', ctx=ast.Load()), node)
        return node

    # -- the types the program has written down ---------------------------------------------------------
    def collect_env(self, scope, module=False):
        env = {}
        self.params = set()
        if isinstance(scope, ast.FunctionDef):
            self.params = {arg.arg for arg in (*scope.args.args, *scope.args.kwonlyargs)}
            for arg in (*scope.args.args, *scope.args.kwonlyargs):
                t = ann_to_type(arg.annotation) if arg.annotation is not None else None
                if t:
                    env[arg.arg] = t
        body = scope.body
        stack = list(body)
        while stack:
            node = stack.pop(0)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                t = ann_to_type(node.annotation)
                if t:
                    env[node.target.id] = t
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.stmt):
                    stack.append(child)
        self.env = env
        if not module:
            self.infer_assigned(scope)
        return env

    def infer_assigned(self, scope):
        """A name's type from its first plain assignment (a literal, or an expression of known type)."""
        for node in ast.walk(scope):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in self.env:
                    continue
                t = self.infer(node.value)
                if t and t[0] in ('int', 'float', 'str', 'bool', 'list', 'dict'):
                    self.env[name] = t
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id not in self.env:
                t = self.infer(node.iter)
                if t and t[0] == 'list':
                    self.env[node.target.id] = t[1]
                elif t == ('str',):
                    self.env[node.target.id] = ('str',)
                elif isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) \
                        and node.iter.func.id == 'range':
                    self.env[node.target.id] = ('int',)

    def infer(self, node):
        """The type of an expression: ('int',) ... ('list', T) ('dict', K, V), ('none',), or the markers
        ('arr',) / ('obj',) for a display whose elements are not of one type; None when unknown."""
        if isinstance(node, ast.Constant):
            v = node.value
            if v is None:
                return ('none',)
            if isinstance(v, bool):
                return ('bool',)
            if isinstance(v, int):
                return ('int',)
            if isinstance(v, float):
                return ('float',)
            if isinstance(v, str):
                return ('str',)
            return None
        if isinstance(node, ast.JoinedStr):
            return ('str',)
        if isinstance(node, ast.Name):
            return self.env.get(node.id)
        if isinstance(node, ast.List):
            kinds = [self.infer(e) for e in node.elts]
            if any(k is None for k in kinds):
                return None
            if kinds and all(k == kinds[0] for k in kinds) and kinds[0][0] in ('int', 'float', 'str', 'bool', 'list'):
                if dumps_ok(('list', kinds[0])):
                    return ('list', kinds[0])
            return ('arr',)
        if isinstance(node, ast.Dict):
            if any(k is None or not isinstance(k, ast.Constant) or not isinstance(k.value, str) for k in node.keys):
                return None
            kinds = [self.infer(v) for v in node.values]
            if any(k is None for k in kinds):
                return None
            if kinds and all(k == kinds[0] for k in kinds) and kinds[0][0] in LEAF_NEST:
                return ('dict', ('str',), kinds[0])
            return ('obj',)
        if isinstance(node, ast.Subscript):
            base = self.infer(node.value)
            if isinstance(node.slice, ast.Slice):
                return base if base and base[0] in ('list', 'str') else None
            if base and base[0] == 'list':
                return base[1]
            if base and base[0] == 'dict':
                return base[2]
            if base == ('str',):
                return ('str',)
            return None
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                if f.id in ('len', 'int', 'ord', 'round') and f.id != 'round':
                    return ('int',)
                if f.id == 'round':
                    return ('int',) if len(node.args) == 1 else ('float',)
                if f.id in ('str', 'chr', 'repr'):
                    return ('str',)
                if f.id == 'float':
                    return ('float',)
                if f.id == 'bool':
                    return ('bool',)
                if f.id in ('abs', 'min', 'max', 'sum') and len(node.args) == 1:
                    t = self.infer(node.args[0])
                    if t and t[0] == 'list':
                        return t[1]
                    return t
                if f.id in ('abs', 'min', 'max') and len(node.args) == 2:
                    a, b = self.infer(node.args[0]), self.infer(node.args[1])
                    return a if a == b else (('float',) if {a, b} == {('int',), ('float',)} else None)
                if f.id in ('sorted', 'list') and node.args:
                    t = self.infer(node.args[0])
                    return t if t and t[0] == 'list' else None
                if f.id in self.functions:
                    return ann_to_type(self.functions[f.id].returns)
            if isinstance(f, ast.Attribute) and f.attr in ('upper', 'lower', 'strip', 'lstrip', 'rstrip', 'replace',
                                                           'title', 'capitalize', 'join', 'format', 'zfill'):
                return ('str',)
            return None
        if isinstance(node, ast.BinOp):
            a, b = self.infer(node.left), self.infer(node.right)
            if a is None or b is None:
                return None
            if isinstance(node.op, ast.Div):
                return ('float',) if a[0] in ('int', 'float') and b[0] in ('int', 'float') else None
            if a[0] in ('int', 'float') and b[0] in ('int', 'float'):
                return ('float',) if 'float' in (a[0], b[0]) else ('int',)
            if a == b == ('str',) and isinstance(node.op, ast.Add):
                return ('str',)
            if isinstance(node.op, ast.Mod) and a == ('str',):
                return ('str',)
            return None
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return ('bool',)
            return self.infer(node.operand)
        if isinstance(node, (ast.Compare,)):
            return ('bool',)
        if isinstance(node, ast.BoolOp):
            kinds = [self.infer(v) for v in node.values]
            return kinds[0] if all(k == kinds[0] for k in kinds) else None
        if isinstance(node, ast.IfExp):
            a, b = self.infer(node.body), self.infer(node.orelse)
            return a if a == b else None
        if isinstance(node, ast.ListComp) and len(node.generators) == 1:
            gen = node.generators[0]
            if isinstance(gen.target, ast.Name):
                saved = self.env.get(gen.target.id)
                it = self.infer(gen.iter)
                if it and it[0] == 'list':
                    self.env[gen.target.id] = it[1]
                elif it == ('str',):
                    self.env[gen.target.id] = ('str',)
                elif isinstance(gen.iter, ast.Call) and isinstance(gen.iter.func, ast.Name) and gen.iter.func.id == 'range':
                    self.env[gen.target.id] = ('int',)
                else:
                    return None
                elt = self.infer(node.elt)
                if saved is None:
                    self.env.pop(gen.target.id, None)
                else:
                    self.env[gen.target.id] = saved
                if elt and dumps_ok(('list', elt)):
                    return ('list', elt)
            return None
        return None

    # -- json.loads --------------------------------------------------------------------------------------
    def loads_check(self, call, t):
        """Refuses what json.loads cannot produce; the mangled name of type t."""
        if not loads_ok(t):
            refuse(call, 'json.loads into %s is not built (built: int, float, str, bool, list[T] of those, '
                   'list[list[T]] of int / float / str, dict[str, T] of int / float / str)' % render(t))
        if len(call.args) != 1 or call.keywords or isinstance(call.args[0], ast.Starred):
            refuse(call, 'json.loads(s) takes the text only (object_hook=, parse_float=... are not built)')
        return mangle(t)

    def loads_call(self, call, t):
        """The call of the typed loader for `json.loads(s)` producing type t."""
        key = self.loads_check(call, t)
        self.loads_types[key] = t
        new = _call(ast.Name(id='_ail_js_loads_' + key, ctx=ast.Load()), call.args[0])
        return ast.copy_location(_mark(new), call)

    # -- the C fast path: the text parsed straight into the declared container ------------------------------
    def fast_intrinsic(self, t):
        """The _ail_jf_ call that fills a container local of type t from the text in place (1: done, 0: the
        text is not plain -- run the scanner and the typed parsers), or None."""
        if t[0] == 'list' and t[1][0] in ('int', 'float', 'str'):
            return {'int': '_ail_jf_ints', 'float': '_ail_jf_floats', 'str': '_ail_jf_strs'}[t[1][0]]
        if t[0] == 'dict' and t[1][0] == 'str' and t[2][0] in ('int', 'float', 'str'):
            return {'int': '_ail_jf_dict_int', 'float': '_ail_jf_dict_float', 'str': '_ail_jf_dict_str'}[t[2][0]]
        return None

    def nest_intrinsic(self, t):
        """The _ail_jf_ call that reads list[list[str]] into a flat list of the strings and the row ends."""
        if t[0] == 'list' and t[1][0] == 'list' and t[1][1][0] == 'str':
            return '_ail_jf_nest_strs'
        return None

    def row_intrinsic(self, t):
        """The _ail_jf_ call that reads one row of list[list[int]] / list[list[float]] at a position."""
        if t[0] == 'list' and t[1][0] == 'list' and t[1][1][0] in ('int', 'float'):
            return {'int': '_ail_jf_row_ints', 'float': '_ail_jf_row_floats'}[t[1][1][0]]
        return None

    def fresh(self, stem):
        self.temps += 1
        return '_ail_%s%d' % (stem, self.temps)

    def in_place(self, target, t, annotation, text, origin):
        """Statements that load `text` (a name or a constant) into the local `target` of type t, or None:
            target: T = []
            if _ail_jf_ints(text, target) == 0:
                target = <scanner and typed parser>"""
        intrinsic = self.fast_intrinsic(t)
        if intrinsic is None or target in self.params:
            return None
        key = mangle(t)
        self.slow_types[key] = t
        empty = ast.List(elts=[], ctx=ast.Load()) if t[0] == 'list' else ast.Dict(keys=[], values=[])
        if annotation is not None:
            init = ast.AnnAssign(target=_name(target, store=True), annotation=copy.deepcopy(annotation), value=empty,
                                 simple=1)
        else:
            init = ast.Assign(targets=[_name(target, store=True)], value=empty)
        test = ast.Compare(left=_call(_name(intrinsic), copy.deepcopy(text), _name(target)), ops=[ast.Eq()],
                           comparators=[ast.Constant(value=0)])
        slow = ast.Assign(targets=[_name(target, store=True)],
                          value=_call(_name('_ail_js_slow_' + key), copy.deepcopy(text)))
        statements = [init, ast.If(test=test, body=[slow], orelse=[])]
        _mark(ast.Module(body=statements, type_ignores=[]))
        for each in statements:
            ast.copy_location(each, origin)
        _locate(statements, origin)
        return statements

    def as_loads(self, call):
        """json.loads(s) / json.load(stdin) as a (loads call node) or None."""
        name = self.jname(call)
        if name == 'loads':
            return call
        if name == 'load':
            if len(call.args) != 1 or call.keywords:
                refuse(call, 'json.load(f) takes the file only')
            source = call.args[0]
            text = self.read_of(source, call)
            return ast.copy_location(ast.Call(func=ast.Attribute(value=ast.Name(id='json', ctx=ast.Load()), attr='loads',
                                                                 ctx=ast.Load()), args=[text], keywords=[]), call)
        return None

    def read_of(self, source, call):
        if (isinstance(source, ast.Attribute) and source.attr == 'stdin' and isinstance(source.value, ast.Name)
                and source.value.id == 'sys'):
            return ast.parse('sys.stdin.read()', mode='eval').body
        if isinstance(source, ast.Name) or (isinstance(source, ast.Call) and isinstance(source.func, ast.Name)
                                            and source.func.id == 'open'):
            return ast.Call(func=ast.Attribute(value=source, attr='read', ctx=ast.Load()), args=[], keywords=[])
        refuse(call, 'json.load(f): f has to be sys.stdin, open(path) or a file variable')

    # -- json.dumps --------------------------------------------------------------------------------------
    def options(self, call, skip=0):
        what = 'json.dumps'
        known = ('indent', 'sort_keys', 'separators', 'ensure_ascii', 'allow_nan', 'skipkeys', 'check_circular')
        opts = {}
        for keyword in call.keywords:
            if keyword.arg not in known:
                refuse(call, '%s(..., %s=...) is not built (built: indent, sort_keys, separators, ensure_ascii, '
                       'allow_nan)' % (what, keyword.arg))
            opts[keyword.arg] = keyword.value

        def literal(name, default, kinds):
            if name not in opts:
                return default
            node = opts[name]
            if isinstance(node, ast.Constant) and isinstance(node.value, kinds):
                return node.value
            refuse(call, 'json.dumps: %s= has to be a literal %s' % (name, ' or '.join(k.__name__ for k in kinds)))
        indent = literal('indent', None, (int, str, type(None)))
        sort_keys = literal('sort_keys', False, (bool,))
        asc = literal('ensure_ascii', True, (bool,))
        nan = literal('allow_nan', True, (bool,))
        if literal('skipkeys', False, (bool,)):
            refuse(call, 'json.dumps(skipkeys=True) is not built')
        literal('check_circular', True, (bool,))
        separators = None
        if 'separators' in opts:
            node = opts['separators']
            if isinstance(node, ast.Constant) and node.value is None:
                separators = None
            elif (isinstance(node, (ast.Tuple, ast.List)) and len(node.elts) == 2
                    and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts)):
                separators = (node.elts[0].value, node.elts[1].value)
            else:
                refuse(call, 'json.dumps: separators= has to be a literal pair of strings')
        if isinstance(indent, bool):
            indent = int(indent)
        pretty = indent is not None
        pad = ''
        if isinstance(indent, int):
            pad = ' ' * indent if indent > 0 else ''
        elif isinstance(indent, str):
            pad = indent
        if separators is not None:
            isep, ksep = separators
        else:
            isep, ksep = (',' if pretty else ', '), ': '
        return Options(pad, 1 if pretty else 0, isep, ksep, 1 if asc else 0, 1 if sort_keys else 0, 1 if nan else 0)

    def dumps_expr(self, call):
        if len(call.args) < 1 or isinstance(call.args[0], ast.Starred):
            refuse(call, 'json.dumps(obj, ...) needs the object as the first argument')
        if len(call.args) > 1:
            refuse(call, 'json.dumps: pass indent= and the others by keyword')
        opts = self.options(call)
        self.uses_dumps = True
        return ast.copy_location(self.emit(call.args[0], opts, 0, call), call)

    def text_const(self, value):
        return ast.Constant(value=value)

    def emit(self, node, o, lvl, origin):
        """An expression for the JSON text of `node`, nested `lvl` containers deep."""
        pieces = self.pieces(node, o, lvl, origin)
        merged = []
        for kind, value in pieces:
            if merged and merged[-1][0] == 'c' and kind == 'c':
                merged[-1] = ('c', merged[-1][1] + value)
            else:
                merged.append((kind, value))
        result = None
        for kind, value in merged:
            part = ast.Constant(value=value) if kind == 'c' else value
            result = part if result is None else ast.BinOp(left=result, op=ast.Add(), right=part)
        return result if result is not None else ast.Constant(value='')

    def const_text(self, value, o):
        return _json.dumps(value, ensure_ascii=bool(o.asc), allow_nan=True)

    def pieces(self, node, o, lvl, origin):
        # a literal
        if isinstance(node, ast.Constant):
            v = node.value
            if v is None or isinstance(v, (bool, int, float, str)):
                return [('c', self.const_text(v, o))]
            refuse(node, 'json.dumps of this constant is not built')
        if isinstance(node, ast.Dict):
            return self.object_pieces(node, o, lvl, origin)
        if isinstance(node, ast.List):
            return self.array_pieces(node, o, lvl, origin)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) \
                and isinstance(node.operand.value, (int, float)) and not isinstance(node.operand.value, bool):
            return [('c', self.const_text(-node.operand.value, o))]
        t = self.infer(node)
        if t is None:
            refuse(node, 'json.dumps of %s: the type of this value is not known here -- bind it to a variable with a '
                   'type annotation (`xs: list[int] = ...`) or use a literal; built: int, float, str, bool, None, '
                   'list[T], list[list[T]], dict[str, T] and dict[int, T] (T int / float / str) and literal '
                   'dicts / lists of those' % ast.unparse(node)[:40])
        return self.typed_piece(node, t, o, lvl, origin)

    def typed_piece(self, node, t, o, lvl, origin):
        kind = t[0]
        if kind == 'none':
            return [('c', 'null')]
        if kind == 'int':
            return [('e', _call(ast.Name(id='str', ctx=ast.Load()), node))]
        if kind == 'bool':
            return [('e', ast.IfExp(test=node, body=ast.Constant(value='true'), orelse=ast.Constant(value='false')))]
        if kind == 'float':
            return [('e', _call(ast.Name(id='_ail_jd_float', ctx=ast.Load()), node, o.expr()))]
        if kind == 'str':
            return [('e', _call(ast.Name(id='_ail_jd_str', ctx=ast.Load()), node, o.expr()))]
        if kind in ('arr', 'obj'):
            return self.pieces(node, o, lvl, origin)
        if not dumps_ok(t):
            refuse(node, 'json.dumps of %s is not built' % render(t))
        key = mangle(t)
        self.dumps_types[key] = t
        return [('e', _call(ast.Name(id='_ail_jd_' + key, ctx=ast.Load()), node, o.expr(), ast.Constant(value=lvl)))]

    def nl(self, o, lvl):
        return '\n' + o.pad * lvl

    def array_pieces(self, node, o, lvl, origin):
        if not node.elts:
            return [('c', '[]')]
        if any(isinstance(e, ast.Starred) for e in node.elts):
            refuse(node, 'json.dumps of a list display with * is not built')
        out = [('c', '[' + (self.nl(o, lvl + 1) if o.pretty else ''))]
        sep = o.isep + (self.nl(o, lvl + 1) if o.pretty else '')
        for index, element in enumerate(node.elts):
            if index:
                out.append(('c', sep))
            out.extend(self.pieces(element, o, lvl + 1, origin))
        out.append(('c', (self.nl(o, lvl) if o.pretty else '') + ']'))
        return out

    def object_pieces(self, node, o, lvl, origin):
        if not node.keys:
            return [('c', '{}')]
        entries = {}
        for key, value in zip(node.keys, node.values):
            if key is None:
                refuse(node, 'json.dumps of a dict display with ** is not built')
            if not (isinstance(key, ast.Constant) and isinstance(key.value, (str, int)) and not isinstance(key.value, bool)):
                refuse(node, 'json.dumps of a dict display needs str (or int) literal keys')
            entries[key.value] = value                       # a repeated key keeps its first place, the last value
        kinds = {type(k) for k in entries}
        if len(kinds) > 1:
            refuse(node, 'json.dumps of a dict with str and int keys together is a TypeError in CPython when sorted')
        items = list(entries.items())
        if o.srt:
            items.sort(key=lambda item: item[0])
        out = [('c', '{' + (self.nl(o, lvl + 1) if o.pretty else ''))]
        sep = o.isep + (self.nl(o, lvl + 1) if o.pretty else '')
        for index, (key, value) in enumerate(items):
            if index:
                out.append(('c', sep))
            out.append(('c', self.const_text(str(key), o) + o.ksep))
            out.extend(self.pieces(value, o, lvl + 1, origin))
        out.append(('c', (self.nl(o, lvl) if o.pretty else '') + '}'))
        return out

    # -- helper text ---------------------------------------------------------------------------------------
    def add_helpers(self):
        if not self.loads_types and not self.slow_types and not self.dumps_types and not self.uses_dumps:
            return
        import jsonrt
        parts = []
        every = {**self.slow_types, **self.loads_types}
        if every:
            parts.append(jsonrt.LOADS)
        if self.uses_dumps or self.dumps_types:
            parts.append(jsonrt.DUMPS)
        for key, t in self.loads_types.items():
            parts.append(self.loader_text(key, t))
        for key, t in self.slow_types.items():
            parts.append(self.slow_text(key, t))
        needed = set(every.values())
        for t in every.values():
            for sub in self.loader_deps(t):
                needed.add(sub)
        for sub in sorted(needed - set(every.values()), key=mangle):
            parts.append(self.parser_text(sub))
        for t in every.values():
            parts.append(self.parser_text(t))
        dump_needed = {}
        for key, t in self.dumps_types.items():
            dump_needed[key] = t
            if t[0] == 'list' and t[1][0] == 'list':
                dump_needed[mangle(t[1])] = t[1]
        for key in sorted(dump_needed):
            parts.append(self.dumper_text(dump_needed[key]))
        text = '\n\n\n'.join(dict.fromkeys(parts))
        surface = sys.modules.get('ail_syntax')
        if surface is None:
            import importlib.util
            import pathlib
            path = pathlib.Path(__file__).resolve().parents[2] / 'ail_syntax.py'
            if path.exists():
                spec = importlib.util.spec_from_file_location('ail_syntax', path)
                surface = importlib.util.module_from_spec(spec)
                sys.modules['ail_syntax'] = surface
                spec.loader.exec_module(surface)
        if surface is not None:
            text = surface.python_surface(text)       # the helpers are Python-syntax source like the program
        module = ast.parse(text)
        for stmt in module.body:
            _mark(stmt)
            for each in ast.walk(stmt):
                if 'lineno' in getattr(each, '_attributes', ()):
                    each.lineno = each.end_lineno = 1
                    each.col_offset = each.end_col_offset = 0
        body = self.tree.body
        index = 0
        while index < len(body) and (isinstance(body[index], (ast.Import, ast.ImportFrom))
                                     or (isinstance(body[index], ast.Expr) and isinstance(body[index].value, ast.Constant))):
            index += 1
        self.tree.body = body[:index] + module.body + body[index:]

    def loader_deps(self, t):
        if t[0] == 'list' and t[1][0] == 'list':
            return [t[1]]
        return []

    def slow_text(self, key, t):
        """The scanner and the typed parser: CPython's errors, and every document the fast path declines."""
        return textwrap.dedent('''
            def _ail_js_slow_%s(s: str) -> %s:
                p = _ail_js_check(s)
                return %s(p)
        ''' % (key, render(t), self.parser_name(t)))

    def loader_text(self, key, t):
        """json.loads(s) as a function: the C fast path first, then the scanner and the typed parser."""
        intrinsic = self.fast_intrinsic(t)
        if intrinsic is not None:
            attempt = textwrap.dedent('''
                    out: %s = %s
                    if %s(s, out) == 1:
                        return out
            ''' % (render(t), '[]' if t[0] == 'list' else '{}', intrinsic))
        elif self.row_intrinsic(t) is not None:
            inner = t[1][1]
            attempt = textwrap.dedent('''
                    out: %s = []
                    pos = _ail_jf_rows_open(s)
                    more = 0
                    if pos >= 0:
                        more = 1
                    while more == 1:
                        row: list[%s] = []
                        st = %s(s, pos, row)
                        if st < 0:
                            pos = -1
                            more = 0
                        else:
                            out.append(row)
                            pos = st >> 1
                            more = st & 1
                    if pos != -1:
                        return out
            ''' % (render(t), inner[0], self.row_intrinsic(t)))
        elif self.nest_intrinsic(t) is not None:
            inner = t[1][1]
            attempt = textwrap.dedent('''
                    flat: list[%s] = []
                    offs: list[int] = []
                    if %s(s, flat, offs) == 1:
                        out: %s = []
                        j = 0
                        k = 0
                        n = len(offs)
                        while k < n:
                            end = offs[k]
                            row: list[%s] = []
                            while j < end:
                                row.append(flat[j])
                                j += 1
                            out.append(row)
                            k += 1
                        return out
            ''' % (inner[0], self.nest_intrinsic(t), render(t), inner[0]))
        else:
            return self.slow_text(key, t).replace('_ail_js_slow_', '_ail_js_loads_', 1)
        head = 'def _ail_js_loads_%s(s: str) -> %s:' % (key, render(t))
        tail = '    p = _ail_js_check(s)\n    return %s(p)\n' % self.parser_name(t)
        return '\n' + head + '\n' + textwrap.indent(attempt.strip('\n'), '    ') + '\n' + tail

    def parser_name(self, t):
        if t[0] in SCALARS:
            return '_ail_js_pv_' + t[0]
        if t[0] == 'list':
            return '_ail_js_pl_' + mangle(t[1])
        return '_ail_js_pd_' + mangle(t)[5:]

    def parser_text(self, t):
        if t[0] in SCALARS:
            return ''
        name = self.parser_name(t)
        if t[0] == 'list':
            inner = t[1]
            elem = self.parser_name(inner)
            return textwrap.dedent('''
                def %s(p: _AilJp) -> %s:
                    out: %s = []
                    b = p.b
                    if b[p.i] != 91:
                        _ail_js_mismatch(p, "an array")
                    p.i = _ail_js_ws(p, p.i + 1)
                    if b[p.i] == 93:
                        p.i += 1
                        return out
                    while True:
                        out.append(%s(p))
                        p.i = _ail_js_ws(p, p.i)
                        c = b[p.i]
                        p.i = _ail_js_ws(p, p.i + 1)
                        if c == 93:
                            break
                    return out
            ''' % (name, render(t), render(t), elem))
        elem = self.parser_name(t[2])
        return textwrap.dedent('''
            def %s(p: _AilJp) -> %s:
                out: %s = {}
                b = p.b
                if b[p.i] != 123:
                    _ail_js_mismatch(p, "an object")
                p.i = _ail_js_ws(p, p.i + 1)
                if b[p.i] == 125:
                    p.i += 1
                    return out
                while True:
                    key = _ail_js_pv_str(p)
                    p.i = _ail_js_ws(p, p.i)
                    p.i = _ail_js_ws(p, p.i + 1)
                    out[key] = %s(p)
                    p.i = _ail_js_ws(p, p.i)
                    c = b[p.i]
                    p.i = _ail_js_ws(p, p.i + 1)
                    if c == 125:
                        break
                return out
        ''' % (name, render(t), render(t), elem))

    def item_text(self, t, var, indent):
        """Statements (as text) appending the JSON of the value held in `var` of type t to `out`."""
        if t[0] == 'int':
            return 'out += str(%s)' % var
        if t[0] == 'bool':
            return 'out += "true" if %s else "false"' % var
        if t[0] == 'float':
            return 'out += _ail_jd_float(%s, o)' % var
        if t[0] == 'str':
            return 'out += _ail_jd_str(%s, o)' % var
        return 'out += _ail_jd_%s(%s, o, lvl + 1)' % (mangle(t), var)

    OPTS = 'o.pad, o.pretty, o.isep, o.ksep, o.asc, o.srt, o.nan'

    def leaf_lines(self, leaf, var, lvl):
        """Statements (as lines) appending the JSON of the flat list in `var` (leaf type `leaf`) to the buffer."""
        name = {'int': '_ail_jdc_ints', 'bool': '_ail_jdc_bools', 'float': '_ail_jdc_floats', 'str': '_ail_jdc_strs'}[leaf]
        if leaf == 'float':
            return ['st = %s(%s, %s, %s)' % (name, var, self.OPTS, lvl), 'if st != 0:', '    _ail_jd_bad(st)']
        return ['%s(%s, %s, %s)' % (name, var, self.OPTS, lvl)]

    def dumper_text(self, t):
        """The helper for json.dumps of a container: the C appenders of cruntime JDCORE write the text into one
        buffer (jsonrt.py); a str-keyed dict or a flat list is one call, a nested list a loop over its rows."""
        key = mangle(t)
        flat = t[0] == 'list' and t[1][0] in ('int', 'float', 'str', 'bool')
        nested = t[0] == 'list' and t[1][0] == 'list'
        sdict = t[0] == 'dict' and t[1][0] == 'str'
        if not (flat or nested or sdict):
            return self.dumper_text_ast(t)
        if flat:
            body = self.leaf_lines(t[1][0], 'xs', 'lvl')
            head = 'def _ail_jd_%s(xs: %s, o: _AilJo, lvl: int) -> str:' % (key, render(t))
        elif sdict:
            leaf = t[2][0]
            name = {'int': '_ail_jdc_dict_int', 'float': '_ail_jdc_dict_float', 'str': '_ail_jdc_dict_str'}[leaf]
            if leaf == 'float':
                body = ['st = %s(d, %s, lvl)' % (name, self.OPTS), 'if st != 0:', '    _ail_jd_bad(st)']
            else:
                body = ['%s(d, %s, lvl)' % (name, self.OPTS)]
            head = 'def _ail_jd_%s(d: %s, o: _AilJo, lvl: int) -> str:' % (key, render(t))
        else:
            leaf = t[1][1][0]
            row = self.leaf_lines(leaf, 'v', 'lvl + 1')
            lines = [
                'n = len(xs)',
                'if n == 0:',
                '    return "[]"',
                '_ail_jdc_begin()',
                '_ail_jdc_lit("[")',
                'nl = ""',
                'sep = o.isep',
                'if o.pretty != 0:',
                '    nl = "\\n" + _ail_jd_pad(o.pad, lvl + 1)',
                '    _ail_jdc_lit(nl)',
                '    sep = o.isep + nl',
                'i = 0',
                'while i < n:',
                '    if i > 0:',
                '        _ail_jdc_lit(sep)',
                '    v = xs[i]',
            ] + ['    ' + line for line in row] + [
                '    i += 1',
                'if o.pretty != 0:',
                '    _ail_jdc_lit("\\n" + _ail_jd_pad(o.pad, lvl))',
                '_ail_jdc_lit("]")',
            ]
            body = lines
            head = 'def _ail_jd_%s(xs: %s, o: _AilJo, lvl: int) -> str:' % (key, render(t))
        if not nested:
            body = ['_ail_jdc_begin()'] + body
        body = body + ['return _ail_jdc_result()']
        return '\n' + head + '\n' + ''.join('    ' + line + '\n' for line in body)

    def dumper_text_ast(self, t):
        """The helper written in the typed subset itself (the dict[int, T] case)."""
        key = mangle(t)
        if t[0] == 'list':
            inner = t[1]
            return textwrap.dedent('''
                def _ail_jd_%s(xs: %s, o: _AilJo, lvl: int) -> str:
                    n = len(xs)
                    if n == 0:
                        return "[]"
                    out = "["
                    sep = o.isep
                    if o.pretty != 0:
                        nl = "\\n" + _ail_jd_pad(o.pad, lvl + 1)
                        out += nl
                        sep = o.isep + nl
                    i = 0
                    while i < n:
                        if i > 0:
                            out += sep
                        v = xs[i]
                        %s
                        i += 1
                    if o.pretty != 0:
                        out += "\\n" + _ail_jd_pad(o.pad, lvl)
                    return out + "]"
            ''' % (key, render(t), self.item_text(inner, 'v', 6)))
        kt, vt = t[1], t[2]
        key_expr = '_ail_jd_str(k, o)' if kt[0] == 'str' else '\'"\' + str(k) + \'"\''
        return textwrap.dedent('''
            def _ail_jd_%s(d: %s, o: _AilJo, lvl: int) -> str:
                if len(d) == 0:
                    return "{}"
                ks: list[%s] = []
                for key in d:
                    ks.append(key)
                if o.srt != 0:
                    ks = sorted(ks)
                out = "{"
                sep = o.isep
                if o.pretty != 0:
                    nl = "\\n" + _ail_jd_pad(o.pad, lvl + 1)
                    out += nl
                    sep = o.isep + nl
                i = 0
                while i < len(ks):
                    if i > 0:
                        out += sep
                    k = ks[i]
                    out += %s + o.ksep
                    v = d[k]
                    %s
                    i += 1
                if o.pretty != 0:
                    out += "\\n" + _ail_jd_pad(o.pad, lvl)
                return out + "}"
        ''' % (key, render(t), kt[0], key_expr, self.item_text(vt, 'v', 5)))


class Resolver(ast.NodeTransformer):
    """Replaces every json call by its typed form, tracking the annotations in scope."""
    def __init__(self, js):
        self.js = js
        self.fn_stack = []

    def visit_FunctionDef(self, node):
        js = self.js
        saved_env, saved_fn = js.env, js.fn
        js.collect_env(node)
        js.fn = node
        self.fn_stack.append(node)
        node = self.generic_visit(node)
        self.fn_stack.pop()
        js.env, js.fn = saved_env, saved_fn
        return node

    def typed_loads(self, value, t, owner):
        """`value` is a json.loads / load call to produce type t (or not): returns the replacement or None."""
        js = self.js
        if isinstance(value, ast.Call):
            loads = js.as_loads(value)
            if loads is not None:
                loads.args = [self.visit(a) for a in loads.args]
                if t is None:
                    refuse(value, 'json.loads(s): the type of the result is not declared here; write the type '
                           'down: `data: dict[str, int] = json.loads(s)` (the types are int, float, str, bool, '
                           'list[T], list[list[T]], dict[str, T])')
                return js.loads_call(loads, t)
        return None

    def load_in_place(self, node, target, t, annotation):
        """`target: T = json.loads(text)` / `target = json.loads(text)` inside a function, as statements that
        fill the local container directly (no copy of the result): the list of statements, or None."""
        js = self.js
        value = node.value
        if not (self.fn_stack and isinstance(value, ast.Call) and t is not None and js.fast_intrinsic(t) is not None
                and target not in js.params):
            return None
        loads = js.as_loads(value)
        if loads is None:
            return None
        loads.args = [self.visit(a) for a in loads.args]
        js.loads_check(loads, t)
        if len(loads.args) != 1:
            return None
        text = loads.args[0]
        statements = []
        if not isinstance(text, (ast.Name, ast.Constant)):
            temp = js.fresh('jt')
            statements.append(ast.copy_location(_mark(ast.AnnAssign(target=_name(temp, store=True), annotation=_name('str'),
                                                                    value=text, simple=1)), node))
            text = _name(temp)
        statements.extend(js.in_place(target, t, annotation, text, node))
        return statements

    def visit_AnnAssign(self, node):
        if node.value is not None:
            t = ann_to_type(node.annotation)
            if isinstance(node.target, ast.Name):
                statements = self.load_in_place(node, node.target.id, t, node.annotation)
                if statements is not None:
                    return statements
            replacement = self.typed_loads(node.value, t, node)
            if replacement is not None:
                node.value = replacement
                return node
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            t = self.js.env.get(node.targets[0].id)
            statements = self.load_in_place(node, node.targets[0].id, t, None)
            if statements is not None:
                return statements
            replacement = self.typed_loads(node.value, t, node)
            if replacement is not None:
                node.value = replacement
                return node
        return self.generic_visit(node)

    def visit_Return(self, node):
        if node.value is not None and self.fn_stack:
            t = ann_to_type(self.fn_stack[-1].returns) if self.fn_stack[-1].returns is not None else None
            replacement = self.typed_loads(node.value, t, node)
            if replacement is not None:
                node.value = replacement
                return node
        return self.generic_visit(node)

    def visit_Expr(self, node):
        js = self.js
        call = node.value
        if isinstance(call, ast.Call) and js.jname(call) == 'dump':
            if len(call.args) != 2 or any(isinstance(a, ast.Starred) for a in call.args):
                refuse(call, 'json.dump(obj, fp) takes the object and the file')
            fp = call.args[1]
            if not (isinstance(fp, ast.Attribute) and fp.attr == 'stdout' and isinstance(fp.value, ast.Name)
                    and fp.value.id == 'sys'):
                refuse(call, 'json.dump(obj, fp): fp has to be sys.stdout (use f.write(json.dumps(obj)) for a file)')
            dumps = ast.Call(func=ast.Attribute(value=ast.Name(id='json', ctx=ast.Load()), attr='dumps', ctx=ast.Load()),
                             args=[self.visit(call.args[0])], keywords=[self.visit(k) for k in call.keywords])
            text = js.dumps_expr(dumps)
            return ast.copy_location(ast.Expr(value=ast.Call(
                func=ast.Name(id='print', ctx=ast.Load()), args=[text],
                keywords=[ast.keyword(arg='end', value=ast.Constant(value=''))])), node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        js = self.js
        name = js.jname(node)
        if name == 'dumps':
            node.args = [self.visit(a) for a in node.args]
            node.keywords = [self.visit(k) for k in node.keywords]
            return js.dumps_expr(node)
        if name in ('loads', 'load'):
            # a call argument of a user function with an annotated parameter
            refuse(node, 'json.%s(s): the type of the result is not declared here; write the type down: '
                   '`data: dict[str, int] = json.loads(s)` (the types are int, float, str, bool, list[T], '
                   'list[list[T]], dict[str, T])' % name)
        if isinstance(node.func, ast.Name) and node.func.id in js.functions and not node.keywords:
            fn = js.functions[node.func.id]
            params = fn.args.args
            args = []
            for index, arg in enumerate(node.args):
                replacement = None
                if index < len(params) and params[index].annotation is not None:
                    replacement = self.typed_loads(arg, ann_to_type(params[index].annotation), node)
                args.append(replacement if replacement is not None else self.visit(arg))
            node.args = args
            return node
        return self.generic_visit(node)
