#!/usr/bin/env python3
"""Import graph of the compiler front end that ``ail_chatgpt.py compile`` loads.

    python3 tools/selfhost_deps.py [--root DIR] [--entry FILE] [--out FILE] [--json]

Files are read with ``ast`` only; nothing is imported or executed.  Import forms resolved:
``import x``, ``import x.y as z``, ``from x import y``, ``from . import y`` and relative
parents (``from .. import x``).  Imports that run at import time -- the module body and
module-level ``if``/``try``/``with``/``class`` statements -- are ``eager``; imports inside
function or lambda bodies are marked ``lazy``.  Standard-library imports are recorded per
module and not followed.

Imports built dynamically are found too: ``importlib.util.spec_from_file_location`` with a
path built from ``Path(__file__)`` (optionally ``.resolve()`` / ``.parents[N]``), ``ROOT``
or a preceding ``name = ... / 'part.py'`` assignment, plus ``__import__('x')`` /
``importlib.import_module('x')`` with a literal name.  Those become lazy edges and are listed
under ``dynamic_imports`` in the JSON.

Both graphs are reported: ``eager`` (import-time imports only) and ``full`` (eager + lazy).
For each graph the tool computes strongly connected components (Tarjan), a layer per
component (0 = a leaf, no imports out of the component) and a leaf-first order (by layer,
then name: dependencies before their dependents, and a cycle stays together).

The default run writes ``lab/selfhost/deps.json`` (schema ``ail.selfhost_deps/1``).
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "ail.selfhost_deps/1"
STDLIB = set(getattr(sys, "stdlib_module_names", ()))


# --------------------------------------------------------------------------- resolution


class Resolver:
    """Maps a dotted module name to a file inside the roots Python would search."""

    def __init__(self, root: Path):
        self.root = root
        if (root / "AIL_CURRENT").is_dir():
            self.search = [root / "AIL_CURRENT", root / "AIL_CURRENT" / "python" / "pkg-v12"]
        else:
            self.search = [root]
        self.search = [p for p in self.search if p.is_dir()]
        self.cache: dict[str, Path | None] = {}

    def resolve(self, dotted: str) -> Path | None:
        if not dotted:
            return None
        if dotted in self.cache:
            return self.cache[dotted]
        parts = dotted.split(".")
        found = None
        for base in self.search:
            stem = base.joinpath(*parts)
            for cand in (stem.with_suffix(".py"), stem / "__init__.py"):
                if cand.is_file():
                    found = cand
                    break
            if found is not None:
                break
        self.cache[dotted] = found
        return found

    def module_name(self, path: Path) -> str | None:
        target = path.resolve()
        best = None
        for base in self.search:
            try:
                rel = target.relative_to(base.resolve())
            except ValueError:
                continue
            if best is None or len(base.parts) > len(best[0].parts):
                best = (base, rel)
        if best is None:
            return None
        parts = list(best[1].with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) if parts else None

    def is_package(self, dotted: str) -> bool:
        path = self.resolve(dotted)
        return path is not None and path.name == "__init__.py"


# --------------------------------------------------------------------------- imports


def _is_path_call(n) -> bool:
    return isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id == "Path")
        or (isinstance(n.func, ast.Attribute) and n.func.attr == "Path")) and bool(n.args)


def _from_file(n) -> bool:
    """True when an expression is rooted in ``Path(__file__)``, ``__file__`` or ``ROOT``/``HERE``/``BASE``."""
    if isinstance(n, ast.Name) and n.id in ("__file__", "ROOT", "HERE", "BASE"):
        return True
    if _is_path_call(n):
        return _from_file(n.args[0])
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
            and n.func.attr in ("resolve", "absolute", "expanduser") and not n.args:
        return _from_file(n.func.value)
    if isinstance(n, ast.Attribute) and n.attr == "parent":
        return _from_file(n.value)
    if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Attribute) and n.value.attr == "parents":
        return _from_file(n.value.value)
    return False


def _path_static(node, file_dir: Path):
    """Evaluate ``Path(__file__).parent / 'a' / 'b.py'``, ``Path(__file__).resolve().parents[2] / 'x.py'``
    and ``ROOT / 'a/b.py'``."""
    parts: list[str] = []
    base = None
    ascend = 0

    def walk(n):
        nonlocal base, ascend
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            walk(n.left)
            walk(n.right)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            parts.append(n.value)
        elif isinstance(n, ast.Call) and _is_path_call(n):
            walk(n.args[0])
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in ("resolve", "absolute", "expanduser") and not n.args:
            walk(n.func.value)
        elif isinstance(n, ast.Subscript) and isinstance(n.value, ast.Attribute) and n.value.attr == "parents":
            slice_node = n.slice
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, int) \
                    and _from_file(n.value.value):
                base = "file"
                ascend = slice_node.value
        elif isinstance(n, ast.Attribute) and n.attr == "parent":
            if _from_file(n.value):
                base = "file"
        elif isinstance(n, ast.Name) and n.id in ("ROOT", "HERE", "BASE"):
            base = "file"  # ROOT = Path(__file__).resolve().parent in these modules

    walk(node)
    if base is None or not parts:
        return None
    directory = file_dir.parents[ascend - 1] if ascend else file_dir
    return directory.joinpath(*parts)


def _enclosing_scope(tree, lineno: int):
    """Innermost function of ``tree`` whose body contains ``lineno`` (``tree`` otherwise)."""
    best = tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", None) or node.lineno
            if node.lineno <= lineno <= end and (best is tree or node.lineno >= best.lineno):
                best = node
    return best


def _assigned_expr(tree, name: str, lineno: int):
    """The value of the last plain ``name = expr`` before ``lineno`` in the enclosing scope, if any."""
    scope = _enclosing_scope(tree, lineno)
    best = None
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name \
                and node.lineno <= lineno:
            if best is None or node.lineno > best.lineno:
                best = node
    return best.value if best is not None else None


def dynamic_imports(tree, file_path: Path):
    """Yield (line, form, shown value, resolved path or None) for every dynamic import."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name == "spec_from_file_location":
            path = None
            shown = ""
            if len(node.args) >= 2:
                arg = node.args[1]
                expr = arg
                if isinstance(expr, ast.Name):
                    expr = _assigned_expr(tree, expr.id, node.lineno) or expr
                path = _path_static(expr, file_path.parent)
                try:
                    shown = ast.unparse(arg)
                except Exception:
                    shown = "<unparsed>"
            yield node.lineno, "spec_from_file_location", shown, path
        elif name in ("__import__", "import_module") and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                yield node.lineno, name, arg.value, None
            else:
                try:
                    shown = ast.unparse(arg)
                except Exception:
                    shown = "<unparsed>"
                yield node.lineno, name, shown, None


def import_targets(node: ast.AST, module: str, is_pkg: bool, resolver: Resolver):
    """Return (resolved names, stdlib names, unresolved spellings) for one import node."""
    resolved: list[str] = []
    stdlib: list[str] = []
    unresolved: list[str] = []

    def add(dotted: str):
        if resolver.resolve(dotted):
            resolved.append(dotted)
        elif dotted.split(".")[0] in STDLIB:
            stdlib.append(dotted)
        else:
            unresolved.append(dotted)

    def add_from(base: str, name: str):
        if name == "*":
            add(base)
            return
        sub = f"{base}.{name}" if base else name
        if resolver.resolve(sub):
            resolved.append(sub)
            if base and base != module and resolver.is_package(base):
                resolved.append(base)
        else:
            add(base)

    if isinstance(node, ast.Import):
        for alias in node.names:
            add(alias.name)
        return resolved, stdlib, unresolved

    if node.level:
        pkg_parts = module.split(".") if is_pkg else module.split(".")[:-1]
        drop = node.level - 1
        if drop:
            pkg_parts = pkg_parts[:-drop] if drop <= len(pkg_parts) else []
        base_parts = list(pkg_parts)
        if node.module:
            base_parts.extend(node.module.split("."))
        base = ".".join(base_parts)
        if not base:
            unresolved.append("." * node.level + (node.module or ""))
            return resolved, stdlib, unresolved
        for alias in node.names:
            add_from(base, alias.name)
        return resolved, stdlib, unresolved

    base = node.module or ""
    for alias in node.names:
        add_from(base, alias.name)
    return resolved, stdlib, unresolved


def scan(tree, module: str, is_pkg: bool, resolver: Resolver):
    eager: set[str] = set()
    lazy: set[str] = set()
    stdlib: set[str] = set()
    unresolved: list[str] = []

    def take(node, bucket):
        got, std, bad = import_targets(node, module, is_pkg, resolver)
        bucket.update(got)
        stdlib.update(std)
        for b in bad:
            unresolved.append(f"{node.lineno}:{b}")

    eager_ids: set[int] = set()

    def module_scope(nodes):
        """Imports that run at import time: module body plus nested ``if``/``try``/``with``/``class``
        statements, but not function or lambda bodies."""
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                eager_ids.add(id(node))
                take(node, eager)
                continue
            module_scope(ast.iter_child_nodes(node))

    module_scope(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and id(node) not in eager_ids:
            take(node, lazy)
    return eager, lazy, stdlib, unresolved


# --------------------------------------------------------------------------- graph


def sccs(nodes, adjacency):
    """Tarjan.  Components come out dependencies-first (reverse topological order)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    out: list[list[str]] = []
    counter = [0]
    sys.setrecursionlimit(max(10000, len(nodes) * 10 + 1000))

    def strong(v: str):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in sorted(adjacency.get(v, ())):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            out.append(sorted(comp))

    for v in sorted(nodes):
        if v not in index:
            strong(v)
    return out


def analyse(nodes, adjacency):
    comps = sccs(nodes, adjacency)
    comp_of: dict[str, int] = {}
    for cid, comp in enumerate(comps):
        for node in comp:
            comp_of[node] = cid
    succ: dict[int, set[int]] = {cid: set() for cid in range(len(comps))}
    for src, targets in adjacency.items():
        for dst in targets:
            if src in comp_of and dst in comp_of and comp_of[src] != comp_of[dst]:
                succ[comp_of[src]].add(comp_of[dst])
    layer: dict[int, int] = {}
    for cid, comp in enumerate(comps):  # successors already computed
        layer[cid] = 0 if not succ[cid] else 1 + max(layer[s] for s in succ[cid])
    order = sorted(nodes, key=lambda n: (layer[comp_of[n]], n))
    cycles = [comp for comp in comps if len(comp) > 1]
    self_loops = sorted(n for n in nodes if n in adjacency.get(n, ()))
    layer_sizes: dict[int, int] = {}
    for cid in range(len(comps)):
        layer_sizes[layer[cid]] = layer_sizes.get(layer[cid], 0) + len(comps[cid])
    return {
        "components": comps,
        "component_of": comp_of,
        "layer_of": layer,
        "layer_count": (max(layer.values()) + 1) if layer else 0,
        "layer_sizes": [layer_sizes[i] for i in sorted(layer_sizes)],
        "cycles": cycles,
        "self_loops": self_loops,
        "leaf_first_order": order,
    }


def closure(entry, adjacency):
    seen = {entry}
    stack = [entry]
    while stack:
        node = stack.pop()
        for nxt in adjacency.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


# --------------------------------------------------------------------------- main


def base_commit(root: Path) -> str | None:
    for ref in ("origin/integ", "HEAD"):
        try:
            out = subprocess.run(["git", "rev-parse", ref], cwd=root, capture_output=True,
                                 text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if out.returncode == 0:
            return out.stdout.strip()
    return None


def analyse_tree(root: Path, entry: Path):
    resolver = Resolver(root)
    entry_name = resolver.module_name(entry)
    if entry_name is None:
        raise SystemExit(f"entry {entry} is not under a search root of {root}")

    records: dict[str, dict] = {}
    todo = [entry]
    seen = set()
    while todo:
        path = todo.pop()
        name = resolver.module_name(path)
        if name is None or name in seen:
            continue
        seen.add(name)
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            raise SystemExit(f"cannot parse {path}: {exc}")
        is_pkg = path.name == "__init__.py"
        eager, lazy, stdlib, unresolved = scan(tree, name, is_pkg, resolver)
        dynamic = []
        for line, form, value, dyn_path in dynamic_imports(tree, path):
            if form == "spec_from_file_location":
                target_name = resolver.module_name(dyn_path) if dyn_path is not None and dyn_path.is_file() else None
            else:
                target_name = value if resolver.resolve(value) else None
            dynamic.append({
                "line": line,
                "form": form,
                "value": value,
                "module": target_name,
            })
            if target_name and target_name != name:
                lazy.add(target_name)
        records[name] = {
            "name": name,
            "path": path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path),
            "lines": len(source.splitlines()),
            "functions": [n.name for n in tree.body
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
            "classes": [n.name for n in tree.body if isinstance(n, ast.ClassDef)],
            "eager": eager,
            "lazy": lazy,
            "stdlib": stdlib,
            "dynamic": dynamic,
            "unresolved": unresolved,
        }
        for target in eager | lazy:
            target_path = resolver.resolve(target)
            if target_path is not None and target not in seen:
                todo.append(target_path)

    full_adj = {name: rec["eager"] | rec["lazy"] for name, rec in records.items()}
    eager_adj = {name: set(rec["eager"]) for name, rec in records.items()}
    full_nodes = closure(entry_name, full_adj)
    eager_nodes = closure(entry_name, eager_adj)

    full = analyse(full_nodes, full_adj)
    eager = analyse(eager_nodes, eager_adj)

    for name, rec in records.items():
        rec["in_degree_full"] = sum(1 for src, dsts in full_adj.items() if name in dsts and src != name)
        rec["in_degree_eager"] = sum(1 for src, dsts in eager_adj.items() if name in dsts and src != name)
        rec["component_full"] = full["component_of"].get(name)
        rec["component_eager"] = eager["component_of"].get(name)
        rec["layer_full"] = full["layer_of"].get(full["component_of"].get(name)) if name in full_nodes else None
        rec["layer_eager"] = eager["layer_of"].get(eager["component_of"].get(name)) if name in eager_nodes else None
        rec["eager"] = sorted(rec["eager"])
        rec["lazy"] = sorted(rec["lazy"])
        rec["stdlib"] = sorted(rec["stdlib"])

    modules = [records[n] for n in sorted(full_nodes, key=lambda s: (records[s]["path"], s))]
    total_lines = sum(records[n]["lines"] for n in full_nodes)
    eager_lines = sum(records[n]["lines"] for n in eager_nodes)

    graph_info = {}
    for label, result, nodes, lines in (("eager", eager, eager_nodes, eager_lines),
                                        ("full", full, full_nodes, total_lines)):
        graph_info[label] = {
            "modules": len(nodes),
            "edges": sum(len(full_adj[n] if label == "full" else eager_adj[n]) for n in nodes),
            "lines": lines,
            "layers": result["layer_count"],
            "layer_sizes": result["layer_sizes"],
            "cycles": result["cycles"],
            "self_loops": result["self_loops"],
            "leaf_first_order": result["leaf_first_order"],
        }

    dynamic_places = [{"container": name, "line": item["line"], "form": item["form"],
                       "value": item["value"], "target": item["module"]}
                      for name, rec in sorted(records.items()) for item in rec["dynamic"]]
    unresolved = [{"module": name, "where": where}
                  for name, rec in sorted(records.items()) for where in rec["unresolved"]]
    return {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_commit": base_commit(root),
        "root": ".",
        "entry": entry.relative_to(root).as_posix(),
        "search_roots": [p.relative_to(root).as_posix() if p.is_relative_to(root) else str(p)
                         for p in resolver.search],
        "module_count": {"eager": len(eager_nodes), "full": len(full_nodes)},
        "total_lines": {"eager": eager_lines, "full": total_lines},
        "modules": modules,
        "graphs": graph_info,
        "dynamic_imports": dynamic_places,
        "unresolved": unresolved,
    }


def main(argv=None) -> int:
    here = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--root", default=str(here), help="repository root or fixture root")
    ap.add_argument("--entry", default=None, help="entry file (default AIL_CURRENT/ail_chatgpt.py)")
    ap.add_argument("--out", default=None, help="output JSON (default lab/selfhost/deps.json)")
    ap.add_argument("--json", action="store_true", help="write the JSON to stdout instead")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        ap.error(f"--root {root} is not a directory")
    entry = Path(args.entry) if args.entry else root / "AIL_CURRENT" / "ail_chatgpt.py"
    if not entry.is_absolute():
        entry = root / entry
    entry = entry.resolve()
    if not entry.is_file():
        ap.error(f"entry {entry} is not a file")

    result = analyse_tree(root, entry)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json:
        sys.stdout.write(text)
        stream = sys.stderr
    else:
        out = Path(args.out) if args.out else root / "lab" / "selfhost" / "deps.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
        stream = sys.stdout
    for label in ("eager", "full"):
        g = result["graphs"][label]
        print(f"{label}: modules={g['modules']} lines={g['lines']} edges={g['edges']} "
              f"layers={g['layers']} cycles={len(g['cycles'])}", file=stream)
    unresolvable = len(result["unresolved"])
    print(f"dynamic imports: {len(result['dynamic_imports'])}; unresolved: {unresolvable}",
          file=stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
