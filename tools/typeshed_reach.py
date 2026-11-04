#!/usr/bin/env python3
"""Count stdlib call sites whose callee has a known signature in the vendored typeshed table.

Usage:  python3 tools/typeshed_reach.py PATH... [--list] [--unknown]

`PATH` is a file or a directory (walked for `*.py`).

Default output: first line `total known scalar`, then one line per vendored module
(`module total known scalar`), sorted.

`--list` prints `file:line qualname ret` for every stdlib call site (`ret` is `?` when the callee has no
entry in the table). `--unknown` prints the unknown call sites grouped by qualname with a reason.

A name that the program rebinds is not treated as a stdlib call (scope-insensitive: if any binding of the
name exists, the import is dropped).
"""
import ast
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
STDLIB = REPO / "third_party" / "typeshed" / "stdlib"
sys.path.insert(0, str(REPO / "AIL_CURRENT" / "python" / "pkg-v12"))

from stubsigs import lookup  # noqa: E402


def vendored_modules():
    names = set()
    for path in STDLIB.iterdir():
        if path.is_dir():
            names.add(path.name)
        elif path.suffix == ".pyi":
            names.add(path.stem)
    return names


MODULES = vendored_modules()


def binding_names(tree):
    """Every name the program binds anywhere (conservative, scope-insensitive)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if not isinstance(node, ast.ClassDef):
                args = node.args
                for arg in (list(getattr(args, "posonlyargs", [])) + list(args.args)
                            + list(args.kwonlyargs)):
                    names.add(arg.arg)
                if args.vararg is not None:
                    names.add(args.vararg.arg)
                if args.kwarg is not None:
                    names.add(args.kwarg.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
    return names


def imports_of(tree, rebound):
    """local name -> qualname, for the stdlib modules this program imports."""
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in MODULES:
                    continue
                local = alias.asname or top
                if local not in rebound:
                    found[local] = local if alias.asname else top
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            top = node.module.split(".")[0]
            if top not in MODULES:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                if local not in rebound:
                    found[local] = node.module + "." + alias.name
    return found


def resolve(func, imports):
    chain = []
    node = func
    while isinstance(node, ast.Attribute):
        chain.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name) and node.id in imports:
        return ".".join([imports[node.id]] + list(reversed(chain)))
    return None


def scan(tree, imports):
    """Yield (line, qualname, ret) for every stdlib call site; ret is None when unknown."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        qualname = resolve(node.func, imports)
        if qualname is not None:
            entry = lookup(qualname)
            yield node.lineno, qualname, (entry[0] if entry else None)
            continue
        # `re.compile(...).match(...)`: a method of an object a stdlib call returned
        inner = node.func.value if isinstance(node.func, ast.Attribute) else None
        if isinstance(inner, ast.Call):
            base = resolve(inner.func, imports)
            if base is not None and lookup(base) is not None:
                yield node.lineno, base + "(...)." + node.func.attr, None


def reason(qualname):
    if "(...)." in qualname:
        return "method of returned object"
    return "not in table (star import / re-export / not stubbed)"


def files(paths):
    for name in paths:
        path = Path(name)
        if path.is_dir():
            yield from sorted(path.rglob("*.py"))
        elif path.suffix == ".py":
            yield path


def main(argv):
    listing = "--list" in argv
    unknown = "--unknown" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print("usage: typeshed_reach.py PATH... [--list] [--unknown]", file=sys.stderr)
        return 2
    totals = Counter()
    per_module = {}
    rows = []
    unknown_rows = []
    for path in files(paths):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError:
            continue
        imports = imports_of(tree, binding_names(tree))
        for line, qualname, ret in scan(tree, imports):
            module = qualname.split(".")[0]
            bucket = per_module.setdefault(module, Counter())
            bucket["total"] += 1
            totals["total"] += 1
            if ret is None:
                unknown_rows.append((str(path), line, qualname, reason(qualname)))
            else:
                bucket["known"] += 1
                totals["known"] += 1
                if ret in ("int", "float", "bool"):
                    bucket["scalar"] += 1
                    totals["scalar"] += 1
                rows.append((str(path), line, qualname, ret))
            if listing:
                print("%s:%d %s %s" % (path, line, qualname, ret if ret is not None else "?"))
    if listing:
        return 0
    if unknown:
        counts = Counter(q for _, _, q, _ in unknown_rows)
        for qualname, count in counts.most_common():
            why = next(r for _, _, q, r in unknown_rows if q == qualname)
            print("%4d %s  (%s)" % (count, qualname, why))
        return 0
    print("%d %d %d" % (totals["total"], totals["known"], totals["scalar"]))
    for module in sorted(per_module):
        b = per_module[module]
        print("%s %d %d %d" % (module, b["total"], b["known"], b["scalar"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
