"""enum.Enum / IntEnum / StrEnum lowered onto classes and module-level members (library batch 5, called from stdlib5).

`class Color(Enum): RED = 1; GREEN = 2` becomes a class `Color(_AilEnum)` (prelude_enum.py) holding the methods,
followed by one instance per member (`_ail_en_Color_RED = Color("Color", "RED", 1, 0)`), the list of members, the
name table and the two lookup functions. The uses are rewritten:

    Color.RED            -> the module-level member
    Color(1)             -> _ail_en_Color_call(1)      (ValueError "1 is not a valid Color")
    Color["RED"]         -> _ail_en_Color_get("RED")   (KeyError)
    for c in Color       -> the list of members        (also list(Color), len(Color), sorted(Color), x in Color)
    Color.__members__    -> the name table (aliases included)

Members compare by identity (Enum) or by value (IntEnum, StrEnum), hash, print and repr as CPython 3.12 does. Not
built, refused by name: Flag / IntFlag, the functional API `Enum("Color", "RED GREEN")`, mixed-in bases
(`class C(str, Enum)`), members defined with `__init__` / `__new__`, `_generate_next_value_`, class methods.
Difference: `isinstance(member, int)` is False for an IntEnum member, and a member is not usable as a list index.
"""
import ast
import copy

import stdlib5
from stdlib4 import refuse

KINDS = {'Enum': '_AilEnum', 'IntEnum': '_AilIntEnum', 'StrEnum': '_AilStrEnum'}
HANDLED = {'Enum', 'IntEnum', 'StrEnum', 'auto', 'unique'}
MEMBER_REFUSED = ('__init__', '__new__', '_generate_next_value_', '__call__', '__members__', '__getitem__')


class Info:
    def __init__(self, name, kind):
        self.name = name
        self.kind = kind
        self.members = []          # (member name, variable)
        self.aliases = []          # (alias name, member variable)
        self.values = {}           # variable -> (value expression, position)

    def var(self, member):
        return '_ail_en_%s_%s' % (self.name, member)

    @property
    def all(self):
        return '_ail_en_%s_all' % self.name

    @property
    def map(self):
        return '_ail_en_%s_map' % self.name

    @property
    def call(self):
        return '_ail_en_%s_call' % self.name

    @property
    def get(self):
        return '_ail_en_%s_get' % self.name

    def attr_target(self, attr):
        for member, var in self.members:
            if member == attr:
                return var
        for alias, var in self.aliases:
            if alias == attr:
                return var
        return None


def base_kind(node, binder, enums):
    """'Enum' / 'IntEnum' / 'StrEnum' for an enum base class expression, the Info of a user enum, else None."""
    found = binder.attr(node)
    if found in KINDS:
        return found
    if isinstance(node, ast.Name) and node.id in enums:
        return enums[node.id]
    return None


def is_auto(value, binder):
    return isinstance(value, ast.Call) and binder.attr(value.func) == 'auto' and not value.args and not value.keywords


def literal(value):
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError, TypeError):
        return None


def run(tree, text):
    binder = stdlib5.take_imports(tree, 'enum', HANDLED, unknown='Enum, IntEnum, StrEnum, auto and unique are built')
    if not binder:
        return
    enums = {}
    out = []
    for stmt in tree.body:
        if not isinstance(stmt, ast.ClassDef):
            out.append(stmt)
            continue
        kinds = [base_kind(b, binder, enums) for b in stmt.bases]
        if not any(kinds):
            out.append(stmt)
            continue
        if len(stmt.bases) != 1 or stmt.keywords:
            refuse(stmt, 'enum class %s: a mixed-in base class (class %s(str, Enum)) or a class keyword is not built; '
                   'give the members plain values and compare with .value' % (stmt.name, stmt.name))
        kind = kinds[0]
        out.extend(lower_class(stmt, kind, binder, enums))
    tree.body = out
    # references
    rewriter = Uses(binder, enums)
    tree.body = [rewriter.visit(s) for s in tree.body]
    # the generated statements after each class (built last so that they are not rewritten)
    final = []
    for stmt in tree.body:
        final.append(stmt)
        if isinstance(stmt, ast.ClassDef) and stmt.name in enums and getattr(stmt, '_ail_enum_info', None) is not None:
            final.extend(generated(stmt._ail_enum_info))
    tree.body = final
    stdlib5.leftover(tree, binder, 'Enum, IntEnum, StrEnum, auto and unique are built')
    stdlib5.add_once(text, stdlib5.prelude('enum'))


def lower_class(cls, kind, binder, enums):
    """The rewritten class (an `_ail_enum_info` attribute carries what to generate after it)."""
    parent = None
    if isinstance(kind, Info):
        parent = kind
        kind_name = kind.kind
        base = ast.Name(id=cls.bases[0].id, ctx=ast.Load())
        if kind.members:
            refuse(cls, 'enum class %s: %s has members, so it cannot be extended' % (cls.name, kind.name))
    else:
        kind_name = kind
        base = ast.Name(id=KINDS[kind], ctx=ast.Load())
    info = Info(cls.name, kind_name)
    body = []
    last = None
    seen_values = []               # (member var, value dump)
    index = 0
    for item in cls.body:
        target = value = None
        if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
            target, value = item.targets[0].id, item.value
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.value is not None:
            target, value = item.target.id, item.value
        if target is not None and not target.startswith('_') and not isinstance(value, (ast.Lambda,)):
            if is_auto(value, binder):
                if kind_name == 'StrEnum':
                    value = ast.Constant(value=target.lower())
                elif last is None:
                    value = ast.Constant(value=1)
                elif isinstance(last, int) and not isinstance(last, bool):
                    value = ast.Constant(value=last + 1)
                else:
                    refuse(item, 'enum class %s: auto() after a value that is not an int' % cls.name)
            lit = literal(value)
            last = lit if lit is not None else last
            dump = ast.dump(value)
            for var, other in seen_values:
                if other == dump and lit is not None:
                    info.aliases.append((target, var))
                    break
            else:
                var = info.var(target)
                info.members.append((target, var))
                seen_values.append((var, dump))
                info.values[var] = (copy.deepcopy(value), index)
                index += 1
            continue
        if isinstance(item, ast.FunctionDef) and item.name in MEMBER_REFUSED:
            refuse(item, 'enum class %s: %s is not built (members take plain values)' % (cls.name, item.name))
        if isinstance(item, ast.FunctionDef):
            for dec in item.decorator_list:
                if not (isinstance(dec, ast.Name) and dec.id in ('staticmethod',)):
                    refuse(dec, 'enum class %s: the decorator on %s is not built' % (cls.name, item.name))
        if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
            continue                              # the docstring
        body.append(item)
    decorators = []
    for dec in cls.decorator_list:
        if binder.attr(dec) == 'unique':
            continue
        refuse(dec, 'enum class %s: a class decorator is not built' % cls.name)
    new = copy.copy(cls)
    new.bases = [base]
    new.body = body or [ast.Pass()]
    new.decorator_list = decorators
    new._ail_enum_info = info
    enums[cls.name] = info
    return [new]


def generated(info):
    lines = []
    for member, var in info.members:
        value, index = info.values[var]
        lines.append('%s = %s(%r, %r, %s, %d)' % (var, info.name, info.name, member, ast.unparse(value), index))
    lines.append('%s = [%s]' % (info.all, ', '.join(var for _, var in info.members)))
    entries = ['%r: %s' % (m, v) for m, v in info.members] + ['%r: %s' % (a, v) for a, v in info.aliases]
    lines.append('%s = {%s}' % (info.map, ', '.join(entries)))
    lines.append('def %s(v):\n    for m in %s:\n        if m.value == v:\n            return m\n'
                 '    raise ValueError(repr(v) + " is not a valid %s")' % (info.call, info.all, info.name))
    lines.append('def %s(k):\n    if k in %s:\n        return %s[k]\n    raise KeyError(k)' % (info.get, info.map, info.map))
    return ast.parse('\n'.join(lines)).body


class Uses(ast.NodeTransformer):
    """Rewrite the uses of the enum classes (see the module docstring)."""

    def __init__(self, binder, enums):
        self.binder = binder
        self.enums = enums

    def enum_of(self, node):
        if isinstance(node, ast.Name) and node.id in self.enums:
            return self.enums[node.id]
        return None

    def visit_Attribute(self, node):
        info = self.enum_of(node.value)
        if info is not None and isinstance(node.ctx, ast.Load):
            if node.attr == '__members__':
                return ast.copy_location(ast.Name(id=info.map, ctx=ast.Load()), node)
            var = info.attr_target(node.attr)
            if var is not None:
                return ast.copy_location(ast.Name(id=var, ctx=ast.Load()), node)
            return node                             # a method taken from the class: left as written
        return self.generic_visit(node)

    def visit_Call(self, node):
        info = self.enum_of(node.func)
        if info is not None:
            if len(node.args) != 1 or node.keywords:
                refuse(node, 'enum %s(...): one value is built (Color(1)); the functional API is not' % info.name)
            self.generic_visit(node)
            return ast.copy_location(ast.Call(func=ast.Name(id=info.call, ctx=ast.Load()), args=node.args, keywords=[]),
                                     node)
        if isinstance(node.func, ast.Name) and node.func.id == 'isinstance' and len(node.args) == 2:
            node.args[0] = self.visit(node.args[0])
            return node
        return self.generic_visit(node)

    def visit_Subscript(self, node):
        info = self.enum_of(node.value)
        if info is not None and isinstance(node.ctx, ast.Load):
            new_slice = self.visit(node.slice)
            return ast.copy_location(ast.Call(func=ast.Name(id=info.get, ctx=ast.Load()), args=[new_slice], keywords=[]),
                                     node)
        return self.generic_visit(node)

    def visit_Name(self, node):
        info = self.enum_of(node)
        if info is not None and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Name(id=info.all, ctx=ast.Load()), node)
        return node

    def visit_arg(self, node):
        return node                                 # an annotation names the class, not its members

    def visit_ClassDef(self, node):
        node.body = [self.visit(s) for s in node.body]
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        return node

    def visit_FunctionDef(self, node):
        node.args = self.visit(node.args)
        node.body = [self.visit(s) for s in node.body]
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        return node

    def visit_AnnAssign(self, node):
        node.target = self.visit(node.target)
        if node.value is not None:
            node.value = self.visit(node.value)
        return node
