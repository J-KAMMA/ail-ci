"""Bound methods of builtin objects taken as values: `iskeyword = frozenset(kw).__contains__`,
`add = seen.add`, `j = ",".join`, `g = d.get`, `up = str.upper`.

CPython hands out a bound (or unbound) builtin method; the general path has no such value, and the
attribute read used to fail at run time with `AttributeError: 'frozenset' object has no attribute
'__contains__'` where CPython has a working callable.  This pass runs on the user's tree before the
preludes are added and rewrites each such read, which is not itself called, into a closure that makes
the same call:

    recv.add                  ->  (lambda _bmr: lambda _bma: _bmr.add(_bma))(recv)
    str.upper (not an arg)    ->  lambda _bmr: _bmr.upper()

The receiver is evaluated once, when the attribute is read, as CPython does.  The call inside the
closure is an ordinary method call, so it dispatches on the receiver's run-time type exactly as a
written-out call would.  Only the methods in TABLE are rewritten, with the arities CPython documents
for the common forms; a call with a different argument count is a TypeError from the closure (loud).

Not rewritten (left to the existing paths): a name some class of the program defines or assigns
(a user method or a field), a read through an imported module, a read in call position, and
`str.lower` / `len` style references handed to a call as an argument (map / sorted key= already
handle those).  A bound method of a literal or constructor receiver whose name is a builtin method
but is not in TABLE is refused at compile time with a hint.
"""
import ast

# name -> (parameters after the receiver, call text on _bmr); an optional parameter is `p=None`
TABLE = {
    '__contains__': ('_bma', '_bma in _bmr'),
    '__len__': ('', 'len(_bmr)'),
    '__getitem__': ('_bma', '_bmr[_bma]'),
    # list
    'append': ('_bma', '_bmr.append(_bma)'),
    'extend': ('_bma', '_bmr.extend(_bma)'),
    'insert': ('_bma, _bmb', '_bmr.insert(_bma, _bmb)'),
    'reverse': ('', '_bmr.reverse()'),
    'sort': ('', '_bmr.sort()'),
    # list / set / dict / str / tuple shared
    'remove': ('_bma', '_bmr.remove(_bma)'),
    'index': ('_bma', '_bmr.index(_bma)'),
    'count': ('_bma', '_bmr.count(_bma)'),
    'clear': ('', '_bmr.clear()'),
    'copy': ('', '_bmr.copy()'),
    'update': ('_bma', '_bmr.update(_bma)'),
    # set
    'add': ('_bma', '_bmr.add(_bma)'),
    'discard': ('_bma', '_bmr.discard(_bma)'),
    'union': ('_bma', '_bmr.union(_bma)'),
    'intersection': ('_bma', '_bmr.intersection(_bma)'),
    'difference': ('_bma', '_bmr.difference(_bma)'),
    'issubset': ('_bma', '_bmr.issubset(_bma)'),
    'issuperset': ('_bma', '_bmr.issuperset(_bma)'),
    'isdisjoint': ('_bma', '_bmr.isdisjoint(_bma)'),
    # dict
    'get': ('_bma, _bmb=None', '_bmr.get(_bma, _bmb)'),
    'setdefault': ('_bma, _bmb=None', '_bmr.setdefault(_bma, _bmb)'),
    'keys': ('', '_bmr.keys()'),
    'values': ('', '_bmr.values()'),
    'items': ('', '_bmr.items()'),
    # str
    'join': ('_bma', '_bmr.join(_bma)'),
    'upper': ('', '_bmr.upper()'),
    'lower': ('', '_bmr.lower()'),
    'title': ('', '_bmr.title()'),
    'capitalize': ('', '_bmr.capitalize()'),
    'casefold': ('', '_bmr.casefold()'),
    'swapcase': ('', '_bmr.swapcase()'),
    'strip': ('_bma=None', '_bmr.strip() if _bma is None else _bmr.strip(_bma)'),
    'lstrip': ('_bma=None', '_bmr.lstrip() if _bma is None else _bmr.lstrip(_bma)'),
    'rstrip': ('_bma=None', '_bmr.rstrip() if _bma is None else _bmr.rstrip(_bma)'),
    'split': ('_bma=None', '_bmr.split() if _bma is None else _bmr.split(_bma)'),
    'splitlines': ('', '_bmr.splitlines()'),
    'startswith': ('_bma', '_bmr.startswith(_bma)'),
    'endswith': ('_bma', '_bmr.endswith(_bma)'),
    'replace': ('_bma, _bmb', '_bmr.replace(_bma, _bmb)'),
    'find': ('_bma', '_bmr.find(_bma)'),
    'rfind': ('_bma', '_bmr.rfind(_bma)'),
    'zfill': ('_bma', '_bmr.zfill(_bma)'),
    'isdigit': ('', '_bmr.isdigit()'),
    'isalpha': ('', '_bmr.isalpha()'),
    'isalnum': ('', '_bmr.isalnum()'),
    'isspace': ('', '_bmr.isspace()'),
    'isupper': ('', '_bmr.isupper()'),
    'islower': ('', '_bmr.islower()'),
}

# builtin method names that exist but are not in TABLE (variadic, keyword or type-dependent forms)
_OTHER = frozenset({'pop', 'popitem', 'fromkeys', 'format', 'format_map', 'encode', 'decode', 'partition',
                    'rpartition', 'rsplit', 'center', 'ljust', 'rjust', 'expandtabs', 'translate',
                    'maketrans', 'isdecimal', 'isnumeric', 'isidentifier', 'isprintable', 'istitle',
                    'removeprefix', 'removesuffix', 'symmetric_difference', 'intersection_update',
                    'difference_update', 'symmetric_difference_update', 'rindex', 'hex', 'to_bytes',
                    'from_bytes', 'bit_length', 'is_integer', 'as_integer_ratio', 'conjugate'})

_TYPES = frozenset({'str', 'list', 'dict', 'set', 'frozenset', 'tuple'})
_CONSTRUCTORS = frozenset({'list', 'dict', 'set', 'frozenset', 'str', 'tuple', 'sorted'})


def _root(node):
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.value if not isinstance(node, ast.Call) else node.func
    return node


def _user_names(tree):
    """Names a class of the program defines or assigns, fields assigned anywhere, imported names,
    and every name the program binds (a shadowed `str` is not the builtin)."""
    attrs, bound, imported, classes = set(), set(), set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef):
            classes.add(n.name)
            bound.add(n.name)
            for st in n.body:
                if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    attrs.add(st.name)
                elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    attrs.add(st.target.id)
                elif isinstance(st, ast.Assign):
                    for t in st.targets:
                        for m in ast.walk(t):
                            if isinstance(m, ast.Name):
                                attrs.add(m.id)
        elif isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del)):
            attrs.add(n.attr)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.add(n.name)
            for a in n.args.args + n.args.kwonlyargs + n.args.posonlyargs:
                bound.add(a.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            bound.add(n.id)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                imported.add((a.asname or a.name).split('.')[0])
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'setattr' \
                and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str):
            attrs.add(n.args[1].value)
    return attrs, bound, imported, classes


class _Rewrite(ast.NodeTransformer):
    def __init__(self, attrs, bound, imported, classes, refuse):
        self.attrs, self.bound, self.imported, self.classes = attrs, bound, imported, classes
        self.refuse = refuse
        self.called = set()
        self.args_of_call = set()

    def prepare(self, tree):
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                self.called.add(id(n.func))
                for a in n.args:
                    self.args_of_call.add(id(a))
                for k in n.keywords:
                    self.args_of_call.add(id(k.value))

    def visit_Attribute(self, node):
        if not isinstance(node.ctx, ast.Load) or id(node) in self.called:
            return self.generic_visit(node)
        attr = node.attr
        if attr in self.attrs:
            # a class of the program also uses this name: which one a read means is decided at run time
            if (attr in TABLE or attr in _OTHER) and self._literal_receiver(node.value):
                self.refuse(node, attr)
            return self.generic_visit(node)
        recv = node.value
        root = _root(recv)
        if isinstance(root, ast.Name) and (root.id in self.imported or root.id in self.classes):
            return self.generic_visit(node)
        if attr not in TABLE:
            if attr in _OTHER and self._literal_receiver(recv):
                self.refuse(node, attr)
            return self.generic_visit(node)
        params, body = TABLE[attr]
        unbound = (isinstance(recv, ast.Name) and recv.id in _TYPES and recv.id not in self.bound)
        if unbound:
            if id(node) in self.args_of_call:
                return self.generic_visit(node)     # map(str.upper, ...), key=str.lower: handled already
            text = 'lambda _bmr%s: %s' % (', ' + params if params else '', body)
            new = ast.parse(text, mode='eval').body
        else:
            recv = self.visit(recv)
            new = ast.parse('(lambda _bmr: (lambda %s: %s))(None)' % (params, body), mode='eval').body
        for n in ast.walk(new):
            ast.copy_location(n, node)
        if not unbound:
            new.args[0] = recv
        ast.fix_missing_locations(new)
        return new

    @staticmethod
    def _literal_receiver(recv):
        if isinstance(recv, (ast.List, ast.Set, ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp)):
            return True
        if isinstance(recv, ast.Constant) and isinstance(recv.value, (str, bytes)):
            return True
        return (isinstance(recv, ast.Call) and isinstance(recv.func, ast.Name)
                and recv.func.id in _CONSTRUCTORS)


def rewrite_tree(tree, Unsupported):
    """Rewrite, in place, the bound builtin methods taken as values in `tree`."""
    def refuse(node, attr):
        exc = Unsupported(
            '.%s taken as a value from a builtin object (a bound method of a list, dict, set or str)\n'
            '  write instead: a def or lambda that makes the call, e.g. `lambda x: obj.%s(x)`' % (attr, attr))
        exc.source_line = getattr(node, 'lineno', None)
        raise exc

    attrs, bound, imported, classes = _user_names(tree)
    rw = _Rewrite(attrs, bound, imported, classes, refuse)
    rw.prepare(tree)
    rw.visit(tree)
    ast.fix_missing_locations(tree)
