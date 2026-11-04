#!/usr/bin/env python3
"""Convert the vendored typeshed stdlib stubs into `AIL_CURRENT/python/pkg-v12/stubsigs_table.py`.

Run from anywhere:  python3 tools/typeshed_convert.py [--check]

The table is a plain `.py` module, not JSON, because the wheel selects compiler files by suffix
(`COMPILER_SUFFIXES = (".py", ".h", ".c")` in tools/update_manifest.py).

A stub `int` means AIL's checked int64, not an unbounded int (see stubsigs.py).

Rules (see the lane brief):
  * key `module.function`, and `module.Class.method` for classes the module defines;
  * value `(ret, params, flags)`: ret in {int float bool str bytes None obj}, params a tuple of
    (name, kind, annotation_text) with kind in {pos kw star dstar};
  * `if sys.version_info >= (3, N)` is evaluated for CPython 3.12 on Linux, `if sys.platform == ...`
    for `linux`; the branch not taken is dropped;
  * every overload of a name must agree on ret, else ret is `obj` and flags is `overload`;
  * anything that is not exactly one of `int float bool str bytes None` becomes `obj` (TypeVar,
    generic, alias, Any, Literal, union, ...). Never widen a guess.
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
STDLIB = REPO / "third_party" / "typeshed" / "stdlib"
OUT = REPO / "AIL_CURRENT" / "python" / "pkg-v12" / "stubsigs_table.py"

SIMPLE = frozenset(("int", "float", "bool", "str", "bytes"))
PY_VERSION = (3, 12)
PLATFORM = "linux"


def module_files():
    """(module name, path) for every vendored stub, sorted by module name."""
    found = {}
    for path in sorted(STDLIB.rglob("*.pyi")):
        rel = path.relative_to(STDLIB)
        parts = list(rel.parts)
        if parts[-1] == "__init__.pyi":
            name = ".".join(parts[:-1])
        elif len(parts) == 1:
            name = path.stem
        else:
            name = ".".join(parts[:-1] + [path.stem])
        found[name] = path
    return sorted(found.items())


def _int_tuple(node):
    if isinstance(node, (ast.Tuple, ast.List)):
        values = []
        for item in node.elts:
            if not (isinstance(item, ast.Constant) and isinstance(item.value, int)):
                return None
            values.append(item.value)
        return tuple(values)
    return None


def _is_sys_attr(node, attr):
    return (isinstance(node, ast.Attribute) and node.attr == attr
            and isinstance(node.value, ast.Name) and node.value.id == "sys")


def eval_cond(test):
    """True/False when the test is about sys.version_info or sys.platform, else None."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        value = eval_cond(test.operand)
        return None if value is None else not value
    if isinstance(test, ast.BoolOp):
        values = [eval_cond(v) for v in test.values]
        if isinstance(test.op, ast.And):
            if any(v is False for v in values):
                return False
            return True if all(v is True for v in values) else None
        if any(v is True for v in values):
            return True
        return False if all(v is False for v in values) else None
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        left, op, right = test.left, test.ops[0], test.comparators[0]
        if _is_sys_attr(left, "version_info") or _is_sys_attr(right, "version_info"):
            left_is_version = _is_sys_attr(left, "version_info")
            other = _int_tuple(right if left_is_version else left)
            if other is None:
                return None
            current = PY_VERSION[:len(other)]
            return _compare(op, current, other) if left_is_version else _compare(op, other, current)
        if _is_sys_attr(left, "platform") and isinstance(right, ast.Constant):
            return _compare(op, PLATFORM, right.value)
        if isinstance(left, ast.Constant) and _is_sys_attr(right, "platform"):
            return _compare(op, left.value, PLATFORM)
        if (isinstance(left, ast.Call) and isinstance(left.func, ast.Attribute)
                and left.func.attr == "startswith" and _is_sys_attr(left.func.value, "platform")
                and left.args and isinstance(left.args[0], ast.Constant)):
            hit = PLATFORM.startswith(left.args[0].value)
            return hit if isinstance(op, ast.Eq) else (not hit if isinstance(op, ast.NotEq) else None)
        if (isinstance(left, ast.Call) and isinstance(left.func, ast.Attribute)
                and left.func.attr == "startswith" and _is_sys_attr(left.func.value, "version_info")):
            return None
    return None


def _compare(op, a, b):
    if isinstance(op, ast.Gt):
        return a > b
    if isinstance(op, ast.GtE):
        return a >= b
    if isinstance(op, ast.Lt):
        return a < b
    if isinstance(op, ast.LtE):
        return a <= b
    if isinstance(op, ast.Eq):
        return a == b
    if isinstance(op, ast.NotEq):
        return a != b
    return None


def ret_of(annotation):
    if annotation is None:
        return "obj"
    if isinstance(annotation, ast.Constant) and annotation.value is None:
        return "None"
    if isinstance(annotation, ast.Name):
        if annotation.id == "None":
            return "None"
        if annotation.id in SIMPLE:
            return annotation.id
    return "obj"


def params_of(fn):
    args = fn.args
    out = []
    positional = list(getattr(args, "posonlyargs", [])) + list(args.args)
    for index, arg in enumerate(positional):
        if index == 0 and arg.arg in ("self", "cls"):
            continue
        kind = "pos" if index < len(getattr(args, "posonlyargs", [])) else "kw"
        out.append((arg.arg, kind, _text(arg.annotation)))
    if args.vararg is not None:
        out.append((args.vararg.arg, "star", _text(args.vararg.annotation)))
    for arg in args.kwonlyargs:
        out.append((arg.arg, "kw", _text(arg.annotation)))
    if args.kwarg is not None:
        out.append((args.kwarg.arg, "dstar", _text(args.kwarg.annotation)))
    return tuple(out)


def _ctor_defs(body, name, out):
    """Collect the `name` defs in a class body, following version/platform branches."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            out.append(node)
        elif isinstance(node, ast.If):
            value = eval_cond(node.test)
            if value is False:
                _ctor_defs(node.orelse, name, out)
            elif value is True:
                _ctor_defs(node.body, name, out)
            else:
                _ctor_defs(node.body, name, out)
                _ctor_defs(node.orelse, name, out)
        elif isinstance(node, ast.Try):
            _ctor_defs(node.body, name, out)
            for handler in node.handlers:
                _ctor_defs(handler.body, name, out)
            _ctor_defs(node.orelse, name, out)
            _ctor_defs(node.finalbody, name, out)


def ctor_params(node):
    """Parameters of a class's constructor: `__init__`, else `__new__`.

    typeshed puts the constructor of immutable classes (`datetime.date`, `Decimal`, ...)
    in `__new__`, and overloads it. Between overloads take the one with the most
    parameters so `deque(iterable, maxlen=...)` is not reduced to `maxlen` alone.
    A class that defines neither inherits one; `()` is the best the stub says.
    """
    for name in ("__init__", "__new__"):
        defs = []
        _ctor_defs(node.body, name, defs)
        if defs:
            best = max(defs, key=lambda fn: len(params_of(fn)))
            return params_of(best)
    return ()


def _text(annotation):
    if annotation is None:
        return ""
    try:
        return ast.unparse(annotation)
    except Exception:
        return ""


def _is_overload(fn):
    for dec in fn.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == "overload":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "overload":
            return True
    return False


class Collector:
    def __init__(self):
        self.groups = {}
        self.classes = {}      # module-level `Class(...)` -> params of __init__, ret `obj`
        self.aliases = []      # (target name, base name, attr) from `seed = _inst.seed`
        self.vartypes = {}     # `_inst: Random` -> {'_inst': 'Random'}
        self.reexports = []    # (local, source module, source name) from `from _csv import reader`
        self.stars = []        # source modules of `from _heapq import *`
        self.name_aliases = []  # (target, source) from `bisect = bisect_right`

    def add(self, qualname, fn):
        self.groups.setdefault(qualname, []).append((ret_of(fn.returns), params_of(fn), _is_overload(fn)))

    def walk(self, body, prefix=""):
        for node in body:
            if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                if not prefix:
                    for alias in node.names:
                        if alias.name == "*":
                            self.stars.append(node.module)
                        else:
                            self.reexports.append((alias.asname or alias.name, node.module, alias.name))
                continue
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                    and isinstance(node.annotation, ast.Name):
                self.vartypes[node.target.id] = node.annotation.id
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Attribute) \
                    and isinstance(node.value.value, ast.Name):
                self.aliases.append((node.targets[0].id, node.value.value.id, node.value.attr))
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Name):
                self.name_aliases.append((node.targets[0].id, node.value.id))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if prefix and node.name.startswith("_"):
                    continue
                self.add(prefix + node.name, node)
            elif isinstance(node, ast.ClassDef):
                if not prefix:
                    self.classes[node.name] = ctor_params(node)
                self.walk(node.body, prefix + node.name + ".")
            elif isinstance(node, ast.If):
                value = eval_cond(node.test)
                if value is False:
                    self.walk(node.orelse, prefix)
                elif value is True:
                    self.walk(node.body, prefix)
                else:
                    self.walk(node.body, prefix)
                    self.walk(node.orelse, prefix)
            elif isinstance(node, ast.Try):
                self.walk(node.body, prefix)
                for handler in node.handlers:
                    self.walk(handler.body, prefix)
                self.walk(node.orelse, prefix)
                self.walk(node.finalbody, prefix)

    def table(self):
        out = {}
        for qualname, entries in self.groups.items():
            plain = [e for e in entries if not e[2]]
            rets = {e[0] for e in entries}
            if plain:
                ret, params, _ = plain[-1]
                flags = "overload" if len(entries) > 1 and len(rets) > 1 else ""
            else:
                ret, params, _ = entries[0]
                if len(rets) == 1:
                    flags = "overload" if len(entries) > 1 else ""
                else:
                    ret, flags = "obj", "overload"
            out[qualname] = (ret, params, flags)
        for name, params in self.classes.items():
            out.setdefault(name, ("obj", params, ""))
        for target, base, attr in self.aliases:
            if target in out:
                continue
            source = out.get(self.vartypes.get(base, base) + "." + attr)
            if source is not None:
                out[target] = source
        for target, source in self.name_aliases:
            if target not in out and source in out:
                out[target] = out[source]
        return out


def build():
    own = {}
    collectors = {}
    for module, path in module_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        collector = Collector()
        collector.walk(tree.body)
        collectors[module] = collector
        own[module] = collector.table()
    # Re-exports (`from _csv import reader`, `from _heapq import *`) and `bisect = bisect_right`.
    # Resolve in a few passes so a chain through an intermediate module settles.
    for _ in range(3):
        for module, collector in collectors.items():
            out = own[module]
            for local, src, name in collector.reexports:
                if local not in out and name in own.get(src, {}):
                    out[local] = own[src][name]
            for src in collector.stars:
                for name, value in own.get(src, {}).items():
                    out.setdefault(name, value)
            for target, source in collector.name_aliases:
                if target not in out and source in out:
                    out[target] = out[source]
    table = {}
    for module, entries in own.items():
        for name, value in entries.items():
            table[module + "." + name] = value
    return table


def _literal(value):
    """Compact deterministic literal for a nested tuple/string (no spaces after commas)."""
    if isinstance(value, tuple):
        if len(value) == 1:
            return "(" + _literal(value[0]) + ",)"
        return "(" + ",".join(_literal(item) for item in value) + ")"
    return repr(value)


def render(table):
    lines = [
        '"""Generated by tools/typeshed_convert.py. Do not edit.',
        "",
        "Source: third_party/typeshed (see third_party/typeshed/VERSION.md).",
        "A stub `int` means AIL's checked int64, not an unbounded int.",
        '"""',
        "",
        "SIGS = {",
    ]
    for key in sorted(table):
        lines.append("    %s:%s," % (_literal(key), _literal(table[key])))
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main():
    text = render(build())
    check = "--check" in sys.argv[1:]
    if check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("stubsigs_table.py is stale; run tools/typeshed_convert.py")
            return 1
        print("stubsigs_table.py is up to date")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s (%d bytes, %d entries)" % (OUT.relative_to(REPO), len(text.encode()), len(build())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
