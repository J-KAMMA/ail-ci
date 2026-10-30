# -*- coding: utf-8 -*-
"""`object` as the builtin name: a sentinel, an isinstance target, a base class (called from ail_syntax.python_surface).

* `object()` is a fresh object that is equal only to itself (`marker = object()`, `x is marker`, a default argument
  `def f(x=_unset)`, `d.get(k, marker)`). It becomes an instance of a class `_ail_object` with no attributes.
* `isinstance(x, object)` and `isinstance(x, (int, object))` are true for every value: `x` is still evaluated, the
  call becomes `_ail_true(x, 0)`.
* `class C(object):` already builds; it is left as it is.

Every other use of the name `object` (an attribute `object.__new__`, `issubclass`, `object` stored or passed, a call with
arguments, a program that binds the name itself) leaves the whole program as written: nothing here is guessed, and the
compiler then refuses the name with its own message and the note below. The instance of `_ail_object` prints
`<__main__._ail_object object at ...>` and `type(x).__name__` says `_ail_object`; CPython prints
`<object object at ...>` with an address, so no program can depend on that text, but `type(m).__name__` does differ
(DIFFERENCES.md); a program that reads `type(x).__name__` or `x.__class__.__name__` is therefore left as written.
"""
import ast
import re

CLASS = 'class _ail_object: pass'
TRUE = 'def _ail_true(x, t): return True'


def _bound(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del)):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, ast.arg) and node.arg == name:
            return True
        if isinstance(node, ast.alias) and (node.asname or node.name).split('.')[0] == name:
            return True
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return True
        if isinstance(node, ast.ExceptHandler) and node.name == name:
            return True
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name == name:
            return True
    return False


def rewrite(source, notes=None):
    if not re.search(r'\bobject\b', source):
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    loads = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == 'object' and isinstance(n.ctx, ast.Load)]
    if not loads or _bound(tree, 'object'):
        return source
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node
    lines = source.splitlines(True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def offset(lineno, col):
        return starts[lineno - 1] + len(lines[lineno - 1].encode('utf8')[:col].decode('utf8', 'replace'))

    def span(node):
        return offset(node.lineno, node.col_offset), offset(node.end_lineno, node.end_col_offset)

    edits, calls, need_class, need_true, bad = [], set(), False, False, []
    isinstance_ok = not _bound(tree, 'isinstance')
    for node in loads:
        up = parent.get(id(node))
        if isinstance(up, ast.ClassDef) and node in up.bases and len(up.bases) == 1 and not up.keywords:
            continue
        if isinstance(up, ast.Call) and up.func is node and not up.args and not up.keywords:
            edits.append(span(node) + ('_ail_object',))
            need_class = True
            continue
        holder = up
        if isinstance(up, ast.Tuple) and isinstance(parent.get(id(up)), ast.Call):
            holder = parent[id(up)]
            slot = up
        else:
            slot = node
        if (isinstance(holder, ast.Call) and isinstance(holder.func, ast.Name) and holder.func.id == 'isinstance'
                and isinstance_ok and len(holder.args) == 2 and not holder.keywords and holder.args[1] is slot):
            if id(holder) not in calls:
                calls.add(id(holder))
                edits.append(span(holder.func) + ('_ail_true',))
                edits.append(span(holder.args[1]) + ('0',))
                need_true = True
            continue
        bad.append(node)
    if bad:
        if notes is not None:
            for node in bad:
                notes.append((node.lineno, "`object` used as a value: only `object()` (a sentinel), "
                              "`isinstance(x, object)` and `class C(object)` are built.\n"
                              "  write instead: `class Marker: pass` and `marker = Marker()` for a sentinel"))
        return source
    if not edits:
        return source
    if need_class:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ('__name__', '__qualname__') and (
                    isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == 'type' or isinstance(node.value, ast.Attribute)
                    and node.value.attr == '__class__'):
                if notes is not None:
                    notes.append((node.lineno, "`object()` here would print its type name as _ail_object, CPython "
                                  "prints object.\n  write instead: `class Marker: pass` and `marker = Marker()`, "
                                  "and print the name of that class"))
                return source
    # the new definitions go on blank lines between the module's statements when there are any (so no line moves)
    wanted = ([CLASS] if need_class else []) + ([TRUE] if need_true else [])
    taken = set()
    for n in tree.body:
        taken.update(range(n.lineno, n.end_lineno + 1))
    running = [n.lineno for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                                                 ast.Import, ast.ImportFrom))
               and not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    before = min(running) if running else len(lines) + 1        # code that runs while the module starts
    blank = [i for i in range(1, before) if i not in taken and not lines[i - 1].strip()]
    out = source
    for start, end, text in sorted(edits, reverse=True):
        out = out[:start] + text + out[end:]
    if len(blank) >= len(wanted):
        # blank lines are consecutive lines of `out` too: the edits did not add or remove a line
        out_lines = out.splitlines(True)
        for i, text in zip(blank, wanted):
            out_lines[i - 1] = text + '\n'
        return ''.join(out_lines)
    return '\n'.join(wanted) + '\n' + out
