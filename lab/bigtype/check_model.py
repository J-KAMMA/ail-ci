#!/usr/bin/env python3
"""CPython-side model of the BigInt rules in docs/design/BIGINT_TYPE.md.

Every program in this directory is ordinary CPython source: the only AIL-specific
spelling is ``from ail.types import BigInt``.  This checker supplies that module
twice:

* ``--write-expected`` (and the default output check) uses ``BigInt = int``, the
  tiny pure-Python implementation the wheel ships, so the recorded output is
  plain CPython 3.12 output;
* the flow check uses ``BigInt`` as an ``int`` subclass.  Arithmetic with a
  BigInt operand returns a BigInt, a plain int stored in a BigInt place is
  recorded as a promotion, and a BigInt stored in a plain int place is checked
  and raises ``OverflowError`` outside int64.

The programs are instrumented with an in-memory AST rewrite so that every
annotated place (variable, parameter, return, field, list[BigInt] item) is a
recording point.  No program source is modified on disk.
"""

from __future__ import annotations

import argparse
import ast
import io
import runpy
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED_DIR = HERE / "expected"
I64_MIN = -(1 << 63)
I64_MAX = (1 << 63) - 1


class FlowOverflow(OverflowError):
    """The modelled AIL stop for a BigInt that does not fit a plain int place."""


class Event:
    __slots__ = ("kind", "line", "place", "value", "fits")

    def __init__(self, kind, line, place, value, fits=True):
        self.kind = kind
        self.line = line
        self.place = place
        self.value = value
        self.fits = fits

    def __str__(self):
        return "%s line %s %s = %d%s" % (
            self.kind, self.line, self.place, self.value,
            "" if self.fits else " (outside int64)")


EVENTS: list[Event] = []


def _fits_i64(value):
    return I64_MIN <= value <= I64_MAX


class BigInt(int):
    """An int whose arithmetic stays exact (and typed BigInt)."""

    def __new__(cls, value=0):
        return super().__new__(cls, int(value))

    @staticmethod
    def _wrap(value):
        if isinstance(value, int) and not isinstance(value, bool):
            return BigInt(value)
        return value

    def __add__(self, other):
        return self._wrap(int(self) + other)

    def __radd__(self, other):
        return self._wrap(other + int(self))

    def __sub__(self, other):
        return self._wrap(int(self) - other)

    def __rsub__(self, other):
        return self._wrap(other - int(self))

    def __mul__(self, other):
        return self._wrap(int(self) * other)

    def __rmul__(self, other):
        return self._wrap(other * int(self))

    def __floordiv__(self, other):
        return self._wrap(int(self) // other)

    def __rfloordiv__(self, other):
        return self._wrap(other // int(self))

    def __mod__(self, other):
        return self._wrap(int(self) % other)

    def __rmod__(self, other):
        return self._wrap(other % int(self))

    def __divmod__(self, other):
        q, r = divmod(int(self), other)
        return BigInt(q), BigInt(r)

    def __rdivmod__(self, other):
        q, r = divmod(other, int(self))
        return BigInt(q), BigInt(r)

    def __pow__(self, other, modulus=None):
        if modulus is None:
            return self._wrap(pow(int(self), other))
        return self._wrap(pow(int(self), other, modulus))

    def __rpow__(self, other, modulus=None):
        if modulus is None:
            return self._wrap(pow(other, int(self)))
        return self._wrap(pow(other, int(self), modulus))

    def __neg__(self):
        return BigInt(-int(self))

    def __pos__(self):
        return BigInt(int(self))

    def __abs__(self):
        return BigInt(abs(int(self)))

    def __invert__(self):
        return BigInt(~int(self))

    def __lshift__(self, other):
        return self._wrap(int(self) << other)

    def __rlshift__(self, other):
        return self._wrap(other << int(self))

    def __rshift__(self, other):
        return self._wrap(int(self) >> other)

    def __rrshift__(self, other):
        return self._wrap(other >> int(self))

    def __and__(self, other):
        return self._wrap(int(self) & other)

    def __rand__(self, other):
        return self._wrap(other & int(self))

    def __or__(self, other):
        return self._wrap(int(self) | other)

    def __ror__(self, other):
        return self._wrap(other | int(self))

    def __xor__(self, other):
        return self._wrap(int(self) ^ other)

    def __rxor__(self, other):
        return self._wrap(other ^ int(self))

    def __iadd__(self, other):
        return self + other

    def __isub__(self, other):
        return self - other

    def __imul__(self, other):
        return self * other

    def __ifloordiv__(self, other):
        return self // other

    def __imod__(self, other):
        return self % other

    def __ilshift__(self, other):
        return self << other

    def __irshift__(self, other):
        return self >> other

    def __iand__(self, other):
        return self & other

    def __ior__(self, other):
        return self | other

    def __ixor__(self, other):
        return self ^ other


def flow_big(line, place, value):
    """A plain int enters a BigInt place; an existing BigInt stays."""
    if isinstance(value, BigInt):
        return value
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        value = int(value)
        EVENTS.append(Event("promote", line, place, value, _fits_i64(value)))
        return BigInt(value)
    raise TypeError("a BigInt place got %r" % (value,))


def flow_int(line, place, value):
    """A BigInt enters a plain int place: checked, OverflowError outside int64."""
    if isinstance(value, BigInt):
        value = int(value)
        if not _fits_i64(value):
            EVENTS.append(Event("overflow", line, place, value, False))
            raise FlowOverflow(
                "BigInt %d does not fit int64 in %s (line %s)" % (value, place, line))
        EVENTS.append(Event("demote", line, place, value, True))
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not _fits_i64(int(value)):
        value = int(value)
        EVENTS.append(Event("literal-overflow", line, place, value, False))
        raise FlowOverflow(
            "integer literal %d outside int64 in %s (line %s)" % (value, place, line))
    return value


def flow_listbig(line, place, value):
    """A list[BigInt] construction/parameter: every item enters a BigInt place."""
    if value is None:
        return []
    out = []
    for index, item in enumerate(value):
        out.append(flow_big(line, "%s[%d]" % (place, index), item))
    return out


HELPERS = {
    "big": flow_big,
    "int": flow_int,
    "listbig": flow_listbig,
}

BIG = "big"
INT = "int"
LBIG = "list[big]"


def kind_of(annotation):
    if annotation is None:
        return None
    if isinstance(annotation, ast.Name):
        if annotation.id == "BigInt":
            return BIG
        if annotation.id == "int":
            return INT
    if isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name):
        if annotation.value.id == "list" and kind_of(annotation.slice) == BIG:
            return LBIG
    return None


class Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.ann = {}
        self.return_kind = None
        self.attrs = {}

    def lookup(self, name):
        scope = self
        while scope is not None:
            if name in scope.ann:
                return scope.ann[name]
            scope = scope.parent
        return None

    def attr(self, name):
        scope = self
        while scope is not None:
            if name in scope.attrs:
                return scope.attrs[name]
            scope = scope.parent
        return None


class Model(ast.NodeTransformer):
    def __init__(self, class_fields):
        self.scope = Scope()
        self.class_fields = class_fields
        self.class_stack = []

    def _call(self, helper, line, place, expr):
        return ast.Call(
            func=ast.Name(id="__flow_%s__" % helper, ctx=ast.Load()),
            args=[ast.Constant(value=line), ast.Constant(value=place), expr],
            keywords=[])

    def _wrap(self, expr, kind, line, place):
        if expr is None or kind is None:
            return expr
        helper = {BIG: "big", INT: "int", LBIG: "listbig"}[kind]
        return ast.copy_location(self._call(helper, line, place, expr), expr)

    def _target_name(self, target):
        if isinstance(target, ast.Name):
            return target.id
        if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                and target.value.id == "self"):
            return "self." + target.attr
        return None

    def _target_kind(self, target):
        if isinstance(target, ast.Name):
            return self.scope.lookup(target.id)
        if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                and target.value.id == "self"):
            return self.scope.attr(target.attr)
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
            if self.scope.lookup(target.value.id) == LBIG:
                return BIG
        return None

    def visit_Module(self, node):
        node.body = [self.visit(stmt) for stmt in node.body]
        return node

    def visit_ClassDef(self, node):
        previous = self.scope
        self.scope = Scope(previous)
        self.scope.attrs = dict(self.class_fields.get(node.name, {}))
        self.class_stack.append(node.name)
        node.body = [self.visit(stmt) for stmt in node.body]
        self.class_stack.pop()
        self.scope = previous
        return node

    def visit_FunctionDef(self, node):
        previous = self.scope
        scope = Scope(previous)
        if self.class_stack:
            scope.attrs = dict(self.class_fields.get(self.class_stack[-1], {}))
        scope.return_kind = kind_of(node.returns)
        self.scope = scope

        args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
        wrappers = []
        for arg in args:
            kind = kind_of(arg.annotation)
            if kind is None:
                continue
            scope.ann[arg.arg] = kind
            helper = {BIG: "big", INT: "int", LBIG: "listbig"}[kind]
            text = "%s = __flow_%s__(%d, %r, %s)" % (
                arg.arg, helper, node.lineno, arg.arg, arg.arg)
            statement = ast.parse(text).body[0]
            ast.copy_location(statement, node)
            wrappers.append(statement)

        body = [self.visit(stmt) for stmt in node.body]
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            node.body = [body[0]] + wrappers + body[1:]
        else:
            node.body = wrappers + body
        self.scope = previous
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_AnnAssign(self, node):
        kind = kind_of(node.annotation)
        if kind is not None:
            if isinstance(node.target, ast.Name):
                self.scope.ann[node.target.id] = kind
                node.value = self._wrap(node.value, kind, node.lineno, node.target.id)
            elif (isinstance(node.target, ast.Attribute)
                  and isinstance(node.target.value, ast.Name)
                  and node.target.value.id == "self"):
                self.scope.attrs[node.target.attr] = kind
                node.value = self._wrap(node.value, kind, node.lineno,
                                        "self." + node.target.attr)
        self.generic_visit(node)
        return node

    def visit_Assign(self, node):
        self.generic_visit(node)
        kinds = [self._target_kind(target) for target in node.targets]
        if kinds and kinds[0] is not None and all(kind == kinds[0] for kind in kinds):
            name = self._target_name(node.targets[0]) or "<target>"
            node.value = self._wrap(node.value, kinds[0], node.lineno, name)
        return node

    def visit_AugAssign(self, node):
        kind = self._target_kind(node.target)
        if kind in (BIG, INT):
            name = self._target_name(node.target) or "<target>"
            value = ast.BinOp(left=ast.copy_location(
                ast.parse(self._target_source(node.target), mode="eval").body, node.target),
                op=node.op, right=node.value)
            wrapped = self._wrap(value, kind, node.lineno, name)
            assign = ast.Assign(targets=[node.target], value=wrapped, type_comment=None)
            return ast.copy_location(assign, node)
        self.generic_visit(node)
        return node

    @staticmethod
    def _target_source(target):
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            return "self." + target.attr
        return "0"

    def visit_Return(self, node):
        self.generic_visit(node)
        if self.scope.return_kind is not None and node.value is not None:
            node.value = self._wrap(node.value, self.scope.return_kind, node.lineno, "return")
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            kind = self.scope.lookup(func.value.id)
            if kind == LBIG and func.attr in ("append", "extend", "insert"):
                if func.attr == "append" and node.args:
                    node.args[0] = self._wrap(node.args[0], BIG, node.lineno,
                                              func.value.id + ".append")
                elif func.attr == "extend" and node.args:
                    node.args[0] = self._wrap(node.args[0], LBIG, node.lineno,
                                              func.value.id + ".extend")
                elif func.attr == "insert" and len(node.args) >= 2:
                    node.args[1] = self._wrap(node.args[1], BIG, node.lineno,
                                              func.value.id + ".insert")
        return node


def collect_class_fields(tree):
    fields = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        found = {}
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                kind = kind_of(stmt.annotation)
                if kind is not None:
                    found[stmt.target.id] = kind
        for sub in ast.walk(node):
            if (isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Attribute)
                    and isinstance(sub.target.value, ast.Name)
                    and sub.target.value.id == "self"):
                kind = kind_of(sub.annotation)
                if kind is not None:
                    found[sub.target.attr] = kind
        fields[node.name] = found
    return fields


def _install_ail_types(cls):
    ail = sys.modules.get("ail")
    if ail is None:
        ail = types.ModuleType("ail")
        ail.__path__ = []
        sys.modules["ail"] = ail
    module = types.ModuleType("ail.types")
    module.BigInt = cls
    module.__all__ = ["BigInt"]
    sys.modules["ail.types"] = module
    ail.types = module


def run_plain(path):
    _install_ail_types(int)
    output = io.StringIO()
    with redirect_stdout(output):
        runpy.run_path(str(path), run_name="__main__")
    return output.getvalue()


def run_model(path):
    _install_ail_types(BigInt)
    EVENTS.clear()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    tree = Model(collect_class_fields(tree)).visit(tree)
    ast.fix_missing_locations(tree)
    code = compile(tree, str(path), "exec")
    namespace = {
        "__name__": "__main__",
        "__file__": str(path),
        "__builtins__": __builtins__,
        "BigInt": BigInt,
    }
    for name, helper in HELPERS.items():
        namespace["__flow_%s__" % name] = helper
    output = io.StringIO()
    raised = None
    with redirect_stdout(output):
        try:
            exec(code, namespace)
        except FlowOverflow as exc:
            raised = exc
        except Exception as exc:  # a real failure is reported, not hidden
            raised = exc
    return output.getvalue(), list(EVENTS), raised


def summary(events):
    counts = {"promote-int64": 0, "promote-big": 0, "demote": 0,
              "overflow": 0, "literal-overflow": 0}
    for event in events:
        if event.kind == "promote":
            counts["promote-int64" if event.fits else "promote-big"] += 1
        elif event.kind in counts:
            counts[event.kind] += 1
    return counts


# The flow each program is written to exercise.  A program with a non-zero
# overflow count is the one that must stop loudly; its program text catches the
# OverflowError so the traced run still exits 0.
EXPECTED_FLOWS = {
    "01_factorial.py": {"promote-int64": 1, "promote-big": 0, "demote": 0,
                        "overflow": 0, "literal-overflow": 0},
    "02_fibonacci.py": {"promote-int64": 2, "promote-big": 0, "demote": 0,
                        "overflow": 0, "literal-overflow": 0},
    "03_modpow.py": {"promote-int64": 1, "promote-big": 1, "demote": 0,
                     "overflow": 0, "literal-overflow": 0},
    "04_counter_field.py": {"promote-int64": 2, "promote-big": 1, "demote": 0,
                            "overflow": 0, "literal-overflow": 0},
    "05_list_sums.py": {"promote-int64": 3, "promote-big": 2, "demote": 0,
                        "overflow": 0, "literal-overflow": 0},
    "06_mix_divmod.py": {"promote-int64": 0, "promote-big": 1, "demote": 0,
                         "overflow": 0, "literal-overflow": 0},
    "07_str_int_roundtrip.py": {"promote-int64": 0, "promote-big": 2, "demote": 0,
                                "overflow": 0, "literal-overflow": 0},
    "08_bigint_to_int_param.py": {"promote-int64": 0, "promote-big": 1, "demote": 0,
                                  "overflow": 1, "literal-overflow": 0},
    "09_literal_and_demotion.py": {"promote-int64": 0, "promote-big": 1, "demote": 1,
                                   "overflow": 0, "literal-overflow": 0},
    "10_bigint_param_return.py": {"promote-int64": 1, "promote-big": 1, "demote": 0,
                                  "overflow": 0, "literal-overflow": 0},
    "11_bitops_compare.py": {"promote-int64": 0, "promote-big": 2, "demote": 0,
                             "overflow": 0, "literal-overflow": 0},
    "12_list_largest_sum.py": {"promote-int64": 1, "promote-big": 2, "demote": 0,
                               "overflow": 0, "literal-overflow": 0},
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-expected", action="store_true",
                        help="write expected/<program>.txt from a plain CPython run")
    parser.add_argument("--show-flows", action="store_true",
                        help="print every recorded flow")
    parser.add_argument("programs", nargs="*", help="only these program file names")
    args = parser.parse_args(argv)

    paths = sorted(HERE.glob("[0-9][0-9]_*.py"))
    if args.programs:
        wanted = set(args.programs)
        paths = [path for path in paths if path.name in wanted]

    if args.write_expected:
        EXPECTED_DIR.mkdir(exist_ok=True)
        for path in paths:
            output = run_plain(path)
            (EXPECTED_DIR / (path.stem + ".txt")).write_text(output, encoding="utf-8")
            print("wrote", EXPECTED_DIR / (path.stem + ".txt"))
        return 0

    failures = 0
    for path in paths:
        expected_path = EXPECTED_DIR / (path.stem + ".txt")
        expected = expected_path.read_text(encoding="utf-8") if expected_path.exists() else None
        plain = run_plain(path)

        output, events, raised = run_model(path)
        counts = summary(events)
        expected_counts = EXPECTED_FLOWS.get(path.name)
        flow_ok = counts == expected_counts
        output_ok = expected is not None and plain == expected
        if not output_ok:
            failures += 1
        if not flow_ok:
            failures += 1
        verdict = "OK" if output_ok and flow_ok else "FAIL"
        print("%s %s  output=%s flows=%s" % (
            verdict, path.name,
            "match" if output_ok else "MISMATCH",
            "match" if flow_ok else "MISMATCH %r != %r" % (counts, expected_counts)))
        if args.show_flows or not flow_ok:
            for event in events:
                print("    ", event)
            if raised is not None:
                print("     raised:", type(raised).__name__, raised)
        if not output_ok:
            print("     expected stdout:", repr(expected))
            print("     plain stdout:   ", repr(plain))

    print("%d/%d programs classified as the rules predict" % (
        len(paths) - failures if failures <= len(paths) else 0, len(paths)))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
