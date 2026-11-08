"""ailast: the CPython 3.12 AST node classes S376 uses, written in AIL (plain Python both run).

A node holds exactly the fields and attributes CPython's ``ast`` gives it, in CPython's order.
``dump`` is CPython 3.12's ``ast.dump`` (``Lib/ast.py``), ``walk`` is breadth first in the order of
``ast.walk``, and ``iter_fields`` / ``iter_child_nodes`` yield like the ``ast`` functions of the same
name.  ``from_cpython.convert`` (selfhost/ref/from_cpython.py, CPython only) builds these nodes from a
CPython ``ast`` tree.

The class shape is the one lab/selfhost/probe_nodes.py found to work: class attributes hold
``_fields`` / ``_attributes`` / ``_optional`` tuples (with a class attribute ``None`` for each
optional field, as in CPython) and ``_typename`` holds the class name, because ``type(node)`` is not
in AIL's subset.  A tuple class attribute keeps the whole program on the general path, which is the
same output, only slower; see lab/selfhost/AST.md.
"""


class AST:
    _typename = "AST"
    _fields = ()
    _attributes = ()
    _optional = ()


class Add(AST):
    _typename = "Add"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class And(AST):
    _typename = "And"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class AnnAssign(AST):
    _typename = "AnnAssign"
    _fields = ('target', 'annotation', 'value', 'simple')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('value', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    value = None
    def __init__(self, target, annotation, value, simple, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.target = target
        self.annotation = annotation
        self.value = value
        self.simple = simple
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Assert(AST):
    _typename = "Assert"
    _fields = ('test', 'msg')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('msg', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    msg = None
    def __init__(self, test, msg, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.test = test
        self.msg = msg
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Assign(AST):
    _typename = "Assign"
    _fields = ('targets', 'value', 'type_comment')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('type_comment', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    type_comment = None
    def __init__(self, targets, value, type_comment, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.targets = targets
        self.value = value
        self.type_comment = type_comment
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Attribute(AST):
    _typename = "Attribute"
    _fields = ('value', 'attr', 'ctx')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, value, attr, ctx, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.attr = attr
        self.ctx = ctx
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class AugAssign(AST):
    _typename = "AugAssign"
    _fields = ('target', 'op', 'value')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, target, op, value, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.target = target
        self.op = op
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class AugLoad(AST):
    _typename = "AugLoad"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class AugStore(AST):
    _typename = "AugStore"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class BinOp(AST):
    _typename = "BinOp"
    _fields = ('left', 'op', 'right')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, left, op, right, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.left = left
        self.op = op
        self.right = right
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class BitAnd(AST):
    _typename = "BitAnd"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class BitOr(AST):
    _typename = "BitOr"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class BitXor(AST):
    _typename = "BitXor"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class BoolOp(AST):
    _typename = "BoolOp"
    _fields = ('op', 'values')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, op, values, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.op = op
        self.values = values
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Break(AST):
    _typename = "Break"
    _fields = ()
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Call(AST):
    _typename = "Call"
    _fields = ('func', 'args', 'keywords')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, func, args, keywords, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.func = func
        self.args = args
        self.keywords = keywords
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class ClassDef(AST):
    _typename = "ClassDef"
    _fields = ('name', 'bases', 'keywords', 'body', 'decorator_list', 'type_params')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, name, bases, keywords, body, decorator_list, type_params, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.name = name
        self.bases = bases
        self.keywords = keywords
        self.body = body
        self.decorator_list = decorator_list
        self.type_params = type_params
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Compare(AST):
    _typename = "Compare"
    _fields = ('left', 'ops', 'comparators')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, left, ops, comparators, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.left = left
        self.ops = ops
        self.comparators = comparators
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Constant(AST):
    _typename = "Constant"
    _fields = ('value', 'kind')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('kind', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    kind = None
    def __init__(self, value, kind, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.kind = kind
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Continue(AST):
    _typename = "Continue"
    _fields = ()
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Del(AST):
    _typename = "Del"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Delete(AST):
    _typename = "Delete"
    _fields = ('targets',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, targets, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.targets = targets
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Dict(AST):
    _typename = "Dict"
    _fields = ('keys', 'values')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, keys, values, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.keys = keys
        self.values = values
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class DictComp(AST):
    _typename = "DictComp"
    _fields = ('key', 'value', 'generators')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, key, value, generators, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.key = key
        self.value = value
        self.generators = generators
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Div(AST):
    _typename = "Div"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Eq(AST):
    _typename = "Eq"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class ExceptHandler(AST):
    _typename = "ExceptHandler"
    _fields = ('type', 'name', 'body')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('type', 'name', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    type = None
    name = None
    def __init__(self, type, name, body, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.type = type
        self.name = name
        self.body = body
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Expr(AST):
    _typename = "Expr"
    _fields = ('value',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, value, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class FloorDiv(AST):
    _typename = "FloorDiv"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class For(AST):
    _typename = "For"
    _fields = ('target', 'iter', 'body', 'orelse', 'type_comment')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('type_comment', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    type_comment = None
    def __init__(self, target, iter, body, orelse, type_comment, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.target = target
        self.iter = iter
        self.body = body
        self.orelse = orelse
        self.type_comment = type_comment
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class FormattedValue(AST):
    _typename = "FormattedValue"
    _fields = ('value', 'conversion', 'format_spec')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('format_spec', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    format_spec = None
    def __init__(self, value, conversion, format_spec, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.conversion = conversion
        self.format_spec = format_spec
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class FunctionDef(AST):
    _typename = "FunctionDef"
    _fields = ('name', 'args', 'body', 'decorator_list', 'returns', 'type_comment', 'type_params')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('returns', 'type_comment', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    returns = None
    type_comment = None
    def __init__(self, name, args, body, decorator_list, returns, type_comment, type_params, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.name = name
        self.args = args
        self.body = body
        self.decorator_list = decorator_list
        self.returns = returns
        self.type_comment = type_comment
        self.type_params = type_params
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class GeneratorExp(AST):
    _typename = "GeneratorExp"
    _fields = ('elt', 'generators')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, elt, generators, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.elt = elt
        self.generators = generators
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Global(AST):
    _typename = "Global"
    _fields = ('names',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, names, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.names = names
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Gt(AST):
    _typename = "Gt"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class GtE(AST):
    _typename = "GtE"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class If(AST):
    _typename = "If"
    _fields = ('test', 'body', 'orelse')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, test, body, orelse, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.test = test
        self.body = body
        self.orelse = orelse
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class IfExp(AST):
    _typename = "IfExp"
    _fields = ('test', 'body', 'orelse')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, test, body, orelse, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.test = test
        self.body = body
        self.orelse = orelse
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Import(AST):
    _typename = "Import"
    _fields = ('names',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, names, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.names = names
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class ImportFrom(AST):
    _typename = "ImportFrom"
    _fields = ('module', 'names', 'level')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('module', 'level', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    module = None
    level = None
    def __init__(self, module, names, level, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.module = module
        self.names = names
        self.level = level
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class In(AST):
    _typename = "In"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Invert(AST):
    _typename = "Invert"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Is(AST):
    _typename = "Is"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class IsNot(AST):
    _typename = "IsNot"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class JoinedStr(AST):
    _typename = "JoinedStr"
    _fields = ('values',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, values, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.values = values
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class LShift(AST):
    _typename = "LShift"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Lambda(AST):
    _typename = "Lambda"
    _fields = ('args', 'body')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, args, body, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.args = args
        self.body = body
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class List(AST):
    _typename = "List"
    _fields = ('elts', 'ctx')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, elts, ctx, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.elts = elts
        self.ctx = ctx
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class ListComp(AST):
    _typename = "ListComp"
    _fields = ('elt', 'generators')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, elt, generators, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.elt = elt
        self.generators = generators
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Load(AST):
    _typename = "Load"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Lt(AST):
    _typename = "Lt"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class LtE(AST):
    _typename = "LtE"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class MatMult(AST):
    _typename = "MatMult"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Mod(AST):
    _typename = "Mod"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Module(AST):
    _typename = "Module"
    _fields = ('body', 'type_ignores')
    _attributes = ()
    _optional = ()
    def __init__(self, body, type_ignores):
        self.body = body
        self.type_ignores = type_ignores

class Mult(AST):
    _typename = "Mult"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Name(AST):
    _typename = "Name"
    _fields = ('id', 'ctx')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, id, ctx, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.id = id
        self.ctx = ctx
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class NamedExpr(AST):
    _typename = "NamedExpr"
    _fields = ('target', 'value')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, target, value, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.target = target
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Nonlocal(AST):
    _typename = "Nonlocal"
    _fields = ('names',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, names, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.names = names
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Not(AST):
    _typename = "Not"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class NotEq(AST):
    _typename = "NotEq"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class NotIn(AST):
    _typename = "NotIn"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Or(AST):
    _typename = "Or"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Pass(AST):
    _typename = "Pass"
    _fields = ()
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Pow(AST):
    _typename = "Pow"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class RShift(AST):
    _typename = "RShift"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Raise(AST):
    _typename = "Raise"
    _fields = ('exc', 'cause')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('exc', 'cause', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    exc = None
    cause = None
    def __init__(self, exc, cause, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.exc = exc
        self.cause = cause
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Return(AST):
    _typename = "Return"
    _fields = ('value',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('value', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    value = None
    def __init__(self, value, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Set(AST):
    _typename = "Set"
    _fields = ('elts',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, elts, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.elts = elts
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class SetComp(AST):
    _typename = "SetComp"
    _fields = ('elt', 'generators')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, elt, generators, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.elt = elt
        self.generators = generators
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Slice(AST):
    _typename = "Slice"
    _fields = ('lower', 'upper', 'step')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('lower', 'upper', 'step', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    lower = None
    upper = None
    step = None
    def __init__(self, lower, upper, step, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.lower = lower
        self.upper = upper
        self.step = step
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Starred(AST):
    _typename = "Starred"
    _fields = ('value', 'ctx')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, value, ctx, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.ctx = ctx
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Store(AST):
    _typename = "Store"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Sub(AST):
    _typename = "Sub"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class Subscript(AST):
    _typename = "Subscript"
    _fields = ('value', 'slice', 'ctx')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, value, slice, ctx, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.slice = slice
        self.ctx = ctx
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Try(AST):
    _typename = "Try"
    _fields = ('body', 'handlers', 'orelse', 'finalbody')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, body, handlers, orelse, finalbody, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.body = body
        self.handlers = handlers
        self.orelse = orelse
        self.finalbody = finalbody
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Tuple(AST):
    _typename = "Tuple"
    _fields = ('elts', 'ctx')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, elts, ctx, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.elts = elts
        self.ctx = ctx
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class UAdd(AST):
    _typename = "UAdd"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class USub(AST):
    _typename = "USub"
    _fields = ()
    _attributes = ()
    _optional = ()
    def __init__(self):
        pass

class UnaryOp(AST):
    _typename = "UnaryOp"
    _fields = ('op', 'operand')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, op, operand, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.op = op
        self.operand = operand
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class While(AST):
    _typename = "While"
    _fields = ('test', 'body', 'orelse')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, test, body, orelse, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.test = test
        self.body = body
        self.orelse = orelse
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class With(AST):
    _typename = "With"
    _fields = ('items', 'body', 'type_comment')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('type_comment', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    type_comment = None
    def __init__(self, items, body, type_comment, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.items = items
        self.body = body
        self.type_comment = type_comment
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class Yield(AST):
    _typename = "Yield"
    _fields = ('value',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('value', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    value = None
    def __init__(self, value, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class YieldFrom(AST):
    _typename = "YieldFrom"
    _fields = ('value',)
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    def __init__(self, value, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class alias(AST):
    _typename = "alias"
    _fields = ('name', 'asname')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('asname', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    asname = None
    def __init__(self, name, asname, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.name = name
        self.asname = asname
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class arg(AST):
    _typename = "arg"
    _fields = ('arg', 'annotation', 'type_comment')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('annotation', 'type_comment', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    annotation = None
    type_comment = None
    def __init__(self, arg, annotation, type_comment, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.arg = arg
        self.annotation = annotation
        self.type_comment = type_comment
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class arguments(AST):
    _typename = "arguments"
    _fields = ('posonlyargs', 'args', 'vararg', 'kwonlyargs', 'kw_defaults', 'kwarg', 'defaults')
    _attributes = ()
    _optional = ('vararg', 'kwarg')
    vararg = None
    kwarg = None
    def __init__(self, posonlyargs, args, vararg, kwonlyargs, kw_defaults, kwarg, defaults):
        self.posonlyargs = posonlyargs
        self.args = args
        self.vararg = vararg
        self.kwonlyargs = kwonlyargs
        self.kw_defaults = kw_defaults
        self.kwarg = kwarg
        self.defaults = defaults

class comprehension(AST):
    _typename = "comprehension"
    _fields = ('target', 'iter', 'ifs', 'is_async')
    _attributes = ()
    _optional = ()
    def __init__(self, target, iter, ifs, is_async):
        self.target = target
        self.iter = iter
        self.ifs = ifs
        self.is_async = is_async

class keyword(AST):
    _typename = "keyword"
    _fields = ('arg', 'value')
    _attributes = ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
    _optional = ('arg', 'end_lineno', 'end_col_offset')
    end_lineno = None
    end_col_offset = None
    arg = None
    def __init__(self, arg, value, lineno=0, col_offset=0, end_lineno=None, end_col_offset=None):
        self.arg = arg
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

class withitem(AST):
    _typename = "withitem"
    _fields = ('context_expr', 'optional_vars')
    _attributes = ()
    _optional = ('optional_vars',)
    optional_vars = None
    def __init__(self, context_expr, optional_vars):
        self.context_expr = context_expr
        self.optional_vars = optional_vars


def iter_fields(node):
    """Yield a (field name, value) tuple for each field in node._fields that is present."""
    for field in node._fields:
        try:
            value = getattr(node, field)
        except AttributeError:
            continue
        yield field, value


def iter_child_nodes(node):
    """Yield the direct child nodes: node fields and items of fields that are lists of nodes."""
    for name, field in iter_fields(node):
        if isinstance(field, AST):
            yield field
        elif isinstance(field, list):
            for item in field:
                if isinstance(item, AST):
                    yield item


def walk(node):
    """Yield node and all descendants, breadth first, in the order CPython's ast.walk uses."""
    todo = [node]
    i = 0
    while i < len(todo):
        current = todo[i]
        i += 1
        for child in iter_child_nodes(current):
            todo.append(child)
        yield current


def dump(node, annotate_fields=True, include_attributes=False, indent=None):
    """Return a formatted dump of the tree in node, the text of CPython 3.12's ast.dump."""
    if not isinstance(node, AST):
        raise TypeError("expected AST, got " + repr(node))
    if indent is not None and not isinstance(indent, str):
        indent = " " * indent
    text = _format(node, 0, annotate_fields, include_attributes, indent)
    return text[0]


def _format(node, level, annotate_fields, include_attributes, indent):
    if indent is not None:
        level += 1
        prefix = "\n" + indent * level
        sep = ",\n" + indent * level
    else:
        prefix = ""
        sep = ", "
    if isinstance(node, AST):
        args = []
        allsimple = True
        keywords = annotate_fields
        for name in node._fields:
            try:
                value = getattr(node, name)
            except AttributeError:
                keywords = True
                continue
            if value is None and name in node._optional:
                keywords = True
                continue
            pair = _format(value, level, annotate_fields, include_attributes, indent)
            value = pair[0]
            simple = pair[1]
            allsimple = allsimple and simple
            if keywords:
                args.append(name + "=" + value)
            else:
                args.append(value)
        if include_attributes and len(node._attributes) > 0:
            for name in node._attributes:
                try:
                    value = getattr(node, name)
                except AttributeError:
                    continue
                if value is None and name in node._optional:
                    continue
                pair = _format(value, level, annotate_fields, include_attributes, indent)
                value = pair[0]
                simple = pair[1]
                allsimple = allsimple and simple
                args.append(name + "=" + value)
        if allsimple and len(args) <= 3:
            return node._typename + "(" + ", ".join(args) + ")", len(args) == 0
        return node._typename + "(" + prefix + sep.join(args) + ")", False
    if isinstance(node, list):
        if len(node) == 0:
            return "[]", True
        parts = []
        for item in node:
            parts.append(_format(item, level, annotate_fields, include_attributes, indent)[0])
        return "[" + prefix + sep.join(parts) + "]", False
    return repr(node), True
