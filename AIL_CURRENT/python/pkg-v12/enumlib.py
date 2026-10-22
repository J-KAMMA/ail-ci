"""enum.Enum / IntEnum / StrEnum lowered onto classes and module-level members (library batch 5, called from stdlib5).

`class Color(Enum): RED = 1; GREEN = 2` becomes a class `Color(_AilEnum)` (prelude_enum.py) holding the methods,
followed by one instance per member (`_ail_en_Color_RED = Color("Color", "RED", 1, 0)`), the list of members, the
name table and the two lookup functions. The uses are rewritten:

    Color.RED            -> the module-level member
    Color(1)             -> _ail_en_Color_call(1)      (ValueError "1 is not a valid Color")
    Color["RED"]         -> _ail_en_Color_get("RED")   (KeyError)
    for c in Color       -> the list of members        (also list(Color), len(Color), sorted(Color), x in Color)
    Color.__members__    -> the name table (aliases included)

Members compare by identity (Enum) or by value (IntEnum, StrEnum), hash, print and repr as CPython 3.12 does.

Flag / IntFlag (prelude_flag.py): the values are worked out here (an int literal, auto(), or an expression of ints
and earlier members), the members and the canonical-member list are as above; `Color(v)` / `~` / `|` / `&` / `^` /
`in` / iteration of a member / `x in Color` are generated per class (the general path has no `type(self)(...)`),
composites are made and cached as `Flag._missing_` does (3.12: STRICT for Flag, KEEP for IntFlag, the same
error text). Not built, refused by name: a non-int or negative member value, boundary= keywords.

Not built, refused by name: the functional API `Enum("Color", "RED GREEN")`, mixed-in bases
(`class C(str, Enum)`), members defined with `__init__` / `__new__`, `_generate_next_value_`, class methods.
Difference: `isinstance(member, int)` is False for an IntEnum member, and a member is not usable as a list index.
"""
import ast
import copy

import stdlib5
from stdlib4 import refuse

KINDS = {'Enum': '_AilEnum', 'IntEnum': '_AilIntEnum', 'StrEnum': '_AilStrEnum', 'Flag': '_AilFlag',
         'IntFlag': '_AilIntFlag'}
HANDLED = {'Enum', 'IntEnum', 'StrEnum', 'Flag', 'IntFlag', 'auto', 'unique'}
FLAGS = ('Flag', 'IntFlag')
WHAT = 'Enum, IntEnum, StrEnum, Flag, IntFlag, auto and unique are built'
MEMBER_REFUSED = ('__init__', '__new__', '_generate_next_value_', '__call__', '__members__', '__getitem__')


class Info:
    def __init__(self, name, kind):
        self.name = name
        self.kind = kind
        self.members = []          # (member name, variable)
        self.aliases = []          # (alias name, member variable)
        self.map_order = []        # (name, variable) in definition order, aliases included (__members__)
        self.values = {}           # variable -> (value expression, position)
        self.order = []            # a Flag class: the variables in definition order, an alias repeating its member
        self.ints = {}             # a Flag class: variable -> its int value
        self.names = []            # a Flag class: the name of each entry of `order`
        self.attrs = set()         # the other names of the class body (its methods, its plain class attributes)

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
    binder = stdlib5.take_imports(tree, 'enum', HANDLED, unknown=WHAT)
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
    flags = False
    for stmt in tree.body:
        final.append(stmt)
        if isinstance(stmt, ast.ClassDef) and stmt.name in enums and getattr(stmt, '_ail_enum_info', None) is not None:
            info = stmt._ail_enum_info
            if info.kind in FLAGS:
                stmt.body.extend(flag_methods(info, stmt))
                final.extend(generated_flag(info))
                flags = True
            else:
                final.extend(generated(info))
    tree.body = final
    stdlib5.leftover(tree, binder, WHAT)
    stdlib5.add_once(text, stdlib5.prelude('enum'))
    if flags:
        stdlib5.add_once(text, stdlib5.prelude('flag'))


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
    seen_values = []               # (member var, literal value, value dump)
    unique = any(binder.attr(dec) == 'unique' for dec in cls.decorator_list)
    flag_env, flag_by_value, flag_values = {}, {}, []
    index = 0
    for item in cls.body:
        target = value = None
        if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
            target, value = item.targets[0].id, item.value
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.value is not None:
            target, value = item.target.id, item.value
        if target is not None and not target.startswith('_') and not isinstance(value, (ast.Lambda,)) \
                and kind_name in FLAGS:
            if is_auto(value, binder):
                number = 1 if not flag_values else 2 ** max(flag_values).bit_length()
            else:
                number = const_int(value, flag_env, cls)
            if number < 0:
                refuse(item, 'enum class %s: %s has the negative value %d; a flag value is not negative here'
                       % (cls.name, target, number))
            if number >= 1 << 63:
                refuse(item, 'enum class %s: %s is %d, past the 63 bits an int holds on the general path'
                       % (cls.name, target, number))
            flag_env[target] = number
            if number in flag_by_value:
                if unique:
                    refuse(item, 'enum class %s: @unique with a duplicate value (%s aliases another member) is not built; '
                           'give each member a distinct value' % (cls.name, target))
                info.aliases.append((target, flag_by_value[number]))
                info.order.append(flag_by_value[number])
            else:
                var = info.var(target)
                info.members.append((target, var))
                info.values[var] = (ast.Constant(value=number), index)
                info.ints[var] = number
                info.order.append(var)
                flag_by_value[number] = var
                flag_values.append(number)
                index += 1
            info.names.append(target)
            continue
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
            for var, other_lit, other_dump in seen_values:
                # CPython aliases equal values, not only equal source text: `A = 0; B = False`, `A = 1; B = 1.0`.
                same = (lit == other_lit) if lit is not None and other_lit is not None else other_dump == dump
                if same:
                    if unique:
                        refuse(item, 'enum class %s: @unique with a duplicate value (%s aliases another member) is not '
                               'built; give each member a distinct value' % (cls.name, target))
                    info.aliases.append((target, var))
                    info.map_order.append((target, var))
                    break
            else:
                var = info.var(target)
                info.members.append((target, var))
                info.map_order.append((target, var))
                seen_values.append((var, lit, dump))
                info.values[var] = (copy.deepcopy(value), index)
                index += 1
            continue
        if isinstance(item, ast.FunctionDef) and item.name in MEMBER_REFUSED:
            refuse(item, 'enum class %s: %s is not built (members take plain values)' % (cls.name, item.name))
        if isinstance(item, ast.FunctionDef):
            for dec in item.decorator_list:
                if not (isinstance(dec, ast.Name) and dec.id in ('staticmethod', 'property')):
                    refuse(dec, 'enum class %s: the decorator on %s is not built' % (cls.name, item.name))
        if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
            continue                              # the docstring
        body.append(item)
    decorators = []
    for dec in cls.decorator_list:
        if binder.attr(dec) == 'unique':
            continue
        refuse(dec, 'enum class %s: a class decorator is not built' % cls.name)
    for item in body:
        if isinstance(item, ast.FunctionDef):
            info.attrs.add(item.name)
        for tgt in item.targets if isinstance(item, ast.Assign) else [item.target] if isinstance(item, ast.AnnAssign) else []:
            if isinstance(tgt, ast.Name):
                info.attrs.add(tgt.id)
    new = copy.copy(cls)
    new.bases = [base]
    new.body = body or [ast.Pass()]
    new.decorator_list = decorators
    new._ail_enum_info = info
    enums[cls.name] = info
    return [new]


def const_int(node, env, cls):
    """The int a Flag member's value expression stands for (int literals, earlier members, | & ^ + - * << >> ~)."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Invert, ast.USub, ast.UAdd)):
        v = const_int(node.operand, env, cls)
        return ~v if isinstance(node.op, ast.Invert) else -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        a, b = const_int(node.left, env, cls), const_int(node.right, env, cls)
        op = node.op
        if isinstance(op, ast.BitOr):
            return a | b
        if isinstance(op, ast.BitAnd):
            return a & b
        if isinstance(op, ast.BitXor):
            return a ^ b
        if isinstance(op, ast.Add):
            return a + b
        if isinstance(op, ast.Sub):
            return a - b
        if isinstance(op, ast.Mult):
            return a * b
        if isinstance(op, ast.LShift) and 0 <= b < 4096:
            return a << b
        if isinstance(op, ast.RShift) and 0 <= b < 4096:
            return a >> b
    refuse(node, 'enum class %s: a Flag member\'s value is built when it is an int literal, auto(), or an expression of '
           'ints and earlier members (| & ^ + - * << >> ~)' % cls.name)


def flag_facts(info):
    """(flag mask, singles mask, all bits, the canonical (name, var) pairs, iterate by definition order?)"""
    fm = sm = 0
    canonical = []
    for name, var in info.members:
        value = info.ints[var]
        fm |= value
        if value and value & (value - 1) == 0:
            sm |= value
            canonical.append((name, var))
    ab = 2 ** fm.bit_length() - 1
    values = [info.ints[var] for _, var in canonical]
    return fm, sm, ab, canonical, values != sorted(values)


def flag_methods(info, cls):
    """The operators of a Flag class (they construct members of this very class, so they are written per class)."""
    n = info.name
    keep = info.kind == 'IntFlag'
    fm, sm, ab, canonical, by_def = flag_facts(info)
    mk = '_ail_en_%s_call' % n
    lines = []
    for sym, name, op in (('|', 'or', '|'), ('&', 'and', '&'), ('^', 'xor', '^')):
        direct = ['    def __%s__(self, other):' % name,
                  '        if isinstance(other, %s):' % n,
                  '            return %s(self.value %s other.value)' % (mk, op)]
        reflected = ['    def __r%s__(self, other):' % name]
        if keep:
            direct += ['        if isinstance(other, int):',
                       '            return %s(self.value %s other)' % (mk, op),
                       '        if isinstance(other, _AilIntEnum):',
                       '            return %s(self.value %s other.value)' % (mk, op)]
            reflected += ['        if isinstance(other, int):',
                          '            return %s(other %s self.value)' % (mk, op),
                          '        if isinstance(other, _AilIntEnum):',
                          '            return %s(other.value %s self.value)' % (mk, op)]
        direct += ['        raise TypeError("unsupported operand type(s) for %s: \'%s\' and \'" + _ail_en_tname(other) + "\'")'
                   % (op, n)]
        reflected += ['        raise TypeError("unsupported operand type(s) for %s: \'" + _ail_en_tname(other) + "\' and \'%s\'")'
                      % (op, n)]
        lines += direct + reflected
    lines += ['    def __invert__(self):',
              '        return %s(%s)' % (mk, '~self.value' if keep else '%d & ~self.value' % sm),
              '    def __contains__(self, other):',
              '        if not isinstance(other, %s):' % n,
              '            raise TypeError("unsupported operand type(s) for \'in\': \'" + _ail_en_tname(other) + "\' and \'%s\'")' % n,
              '        return other.value & self.value == other.value',
              '    def __iter__(self):',
              '        return iter(_ail_en_%s_iter(self.value))' % n]
    have = {item.name for item in cls.body if isinstance(item, ast.FunctionDef)}
    out = []
    for item in ast.parse('class _X:\n' + '\n'.join(lines)).body[0].body:
        if item.name not in have:
            out.append(item)
    return out


def generated_flag(info):
    n = info.name
    keep = info.kind == 'IntFlag'
    fm, sm, ab, canonical, by_def = flag_facts(info)
    lines = []
    for member, var in info.members:
        value, _ = info.values[var]
        number = info.ints[var]
        lines.append('%s = %s(%r, %r, %d, %d)' % (var, n, n, member, number, number))
    by_value = {}
    for _, var in info.members:
        by_value.setdefault(info.ints[var], var)
    lines.append('_ail_en_%s_v2m = {%s}' % (n, ', '.join('%d: %s' % (k, v) for k, v in by_value.items())))
    lines.append('%s = [%s]' % (info.all, ', '.join(var for _, var in canonical)))
    lines.append('_ail_en_%s_mm = [%s]' % (n, ', '.join(info.order)))
    lines.append('%s = {%s}' % (info.map, ', '.join('%r: %s' % (nm, v) for nm, v in zip(info.names, info.order))))
    lines.append('def %s(k):\n    if k in %s:\n        return %s[k]\n    raise KeyError(k)' % (info.get, info.map, info.map))
    lines.append('def _ail_en_%s_has(v):\n    return isinstance(v, %s) or v in _ail_en_%s_v2m' % (n, n, n))
    order = {info.ints[var]: i for i, (_, var) in enumerate(canonical)}
    lines.append('_ail_en_%s_ord = {%s}' % (n, ', '.join('%d: %d' % kv for kv in order.items())))
    sort = ''
    if by_def:
        sort = ('    for i in range(1, len(out)):\n        m = out[i]\n        j = i - 1\n'
                '        while j >= 0 and _ail_en_%s_ord[out[j].value] > _ail_en_%s_ord[m.value]:\n'
                '            out[j + 1] = out[j]\n            j = j - 1\n        out[j + 1] = m\n' % (n, n))
    lines.append('def _ail_en_%s_iter(value):\n    out = []\n    num = value & %d\n    while num:\n'
                 '        b = num & (~num + 1)\n        out.append(_ail_en_%s_v2m.get(b))\n        num = num ^ b\n%s    return out'
                 % (n, fm, n, sort))
    lines.append('def %s(v):\n    if isinstance(v, %s):\n        return v\n    if not isinstance(v, int):\n'
                 '        raise ValueError(repr(v) + " is not a valid %s")\n    if v in _ail_en_%s_v2m:\n'
                 '        return _ail_en_%s_v2m[v]\n    return _ail_en_%s_missing(v)' % (info.call, n, n, n, n, n))
    if keep:
        boundary = ('    if not (~%d <= value <= %d) or value & %d != 0:\n        if value < 0:\n'
                    '            half = 1 << (value.bit_length() - 1)\n'
                    '            value = max(%d, half - 1 + half) + value + 1\n' % (ab, ab, ab ^ fm, ab))
        unknown_raise = ''
        strict_name = ''
    else:
        boundary = ('    if not (~%d <= value <= %d) or value & %d != 0:\n'
                    '        max_bits = max(value.bit_length(), %d)\n'
                    '        raise ValueError("<flag \'%s\'> invalid value " + repr(value) + "\\n    given " + '
                    '_ail_en_bin(value, max_bits) + "\\n  allowed " + _ail_en_bin(%d, max_bits))\n'
                    % (ab, ab, ab ^ fm, fm.bit_length(), n, fm))
        unknown_raise = ('    if unknown != 0:\n        raise ValueError("%s(" + repr(value) + ") -->  unknown values " + '
                         'repr(unknown) + " [" + bin(unknown) + "]")\n' % n)
        strict_name = ('        elif (value ^ combined) != 0:\n            raise ValueError("<flag \'%s\'>: no members with value "'
                       ' + repr(value ^ combined))\n' % n)
    lines.append(
        'def _ail_en_%(n)s_missing(value):\n'
        '    neg_value = 0\n    negative = False\n'
        '%(boundary)s'
        '    if value < 0:\n        neg_value = value\n        negative = True\n        value = %(ab)d + value + 1\n'
        '    unknown = value & %(nfm)d\n    aliases = value & %(nsm)d\n    member_value = value & %(sm)d\n'
        '%(unknown_raise)s'
        '    name = None\n'
        '    if member_value != 0 or aliases != 0:\n'
        '        members = _ail_en_%(n)s_iter(member_value)\n'
        '        combined = 0\n'
        '        for m in members:\n            combined = combined | m.value\n'
        '        if aliases != 0:\n'
        '            value = member_value | aliases\n'
        '            for pm in _ail_en_%(n)s_mm:\n'
        '                found = False\n'
        '                for m in members:\n                    if m is pm:\n                        found = True\n'
        '                if not found and pm.value != 0 and pm.value & value == pm.value:\n'
        '                    members.append(pm)\n                    combined = combined | pm.value\n'
        '        unknown = value ^ combined\n'
        '        name = "|".join([m.name for m in members])\n'
        '        if combined == 0:\n            name = None\n'
        '%(strict_name)s'
        '        elif unknown != 0:\n            name = name + "|" + repr(unknown)\n'
        '    pseudo = %(n)s("%(n)s", name, value, value)\n'
        '    if value not in _ail_en_%(n)s_v2m:\n        _ail_en_%(n)s_v2m[value] = pseudo\n'
        '    pseudo = _ail_en_%(n)s_v2m[value]\n'
        '    if negative:\n        _ail_en_%(n)s_v2m[neg_value] = pseudo\n'
        '    return pseudo'
        % dict(n=n, boundary=boundary, ab=ab, nfm=~fm, nsm=~sm, sm=sm, unknown_raise=unknown_raise,
               strict_name=strict_name))
    return ast.parse('\n'.join(lines)).body


def generated(info):
    lines = []
    for member, var in info.members:
        value, index = info.values[var]
        lines.append('%s = %s(%r, %r, %s, %d)' % (var, info.name, info.name, member, ast.unparse(value), index))
    lines.append('%s = [%s]' % (info.all, ', '.join(var for _, var in info.members)))
    entries = ['%r: %s' % (m, v) for m, v in info.map_order]
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
            if node.attr in info.attrs or node.attr.startswith('__'):
                return node                         # a method taken from the class: left as written
            return ast.copy_location(ast.Call(func=ast.Name(id='_ail_en_noattr', ctx=ast.Load()),
                                              args=[ast.Constant(value=info.name), ast.Constant(value=node.attr)],
                                              keywords=[]), node)
        return self.generic_visit(node)

    def _member_attr(self, node):
        """(info, member) for `Enum.MEMBER` (the base of an assignment target), else None."""
        if isinstance(node, ast.Attribute):
            info = self.enum_of(node.value)
            if info is not None and info.attr_target(node.attr) is not None:
                return info, node.attr
        return None

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr in ('value', 'name'):
                found = self._member_attr(target.value)
                if found is not None:
                    refuse(target, 'enum member %s.%s: setting .%s is not built; a member is immutable'
                           % (found[0].name, found[1], target.attr))
        return self.generic_visit(node)

    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Attribute) and node.target.attr in ('value', 'name'):
            found = self._member_attr(node.target.value)
            if found is not None:
                refuse(node.target, 'enum member %s.%s: setting .%s is not built; a member is immutable'
                       % (found[0].name, found[1], node.target.attr))
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

    def visit_Compare(self, node):
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            info = self.enum_of(node.comparators[0])
            if info is not None and info.kind in FLAGS:
                has = ast.Call(func=ast.Name(id='_ail_en_%s_has' % info.name, ctx=ast.Load()),
                               args=[self.visit(node.left)], keywords=[])
                if isinstance(node.ops[0], ast.NotIn):
                    has = ast.UnaryOp(op=ast.Not(), operand=has)
                return ast.copy_location(has, node)
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
