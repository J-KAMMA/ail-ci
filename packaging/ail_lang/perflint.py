"""`ail check --perf`: static advice about slow algorithms in AI-written Python.

The rules are deliberately local and conservative: a report is only made when the pattern and a
list/string provenance are obvious from the source, so an agent can apply the fix without a type
checker.  Every hit is one line on stderr

    file:line:col: perf P1: <message>; fix: <fix text>

or, with `--json`, one object per hit on stdout with the keys rule, file, line, col, message, fix and
loop_line.  The exit status is 0 (advice, not an error), or 5 with --strict when there is a hit.
Parsing a source that cannot be read is a real error (exit 2) and prints no hits.
"""
import ast
import json
import sys
from pathlib import Path

RULES = {
    "P1": "list membership, index or count inside a loop",
    "P2": "list.pop(0), L.insert(0, x) or del L[0] inside a loop",
    "P3": "string += str inside a loop",
    "P4": "sorted/min/max/sum/sort of an unchanged list inside a loop",
    "P5": "nested loops comparing every pair by key",
    "P6": "L = L + [x] or L = [*L, x] inside a loop",
}

FIXES = {
    "P1": "build a set/dict once before the loop and test membership on it",
    "P2": "use collections.deque and popleft()/appendleft()",
    "P3": "collect the pieces in a list and ''.join once after the loop",
    "P4": "hoist it out of the loop",
    "P5": "group one side by key in a dict, then look up each item of the other side",
    "P6": "use L.append(x)",
}

MESSAGES = {
    "P1-in": "membership test on the list %r inside a loop (O(n) per iteration)",
    "P1-index": "list.index on %r inside a loop (O(n) per call)",
    "P1-count": "list.count on %r inside a loop (O(n) per call)",
    "P2-pop": "list.pop(0) shifts every remaining item inside a loop (O(n) per call)",
    "P2-insert": "list.insert(0, x) shifts every item inside a loop (O(n) per call)",
    "P2-del": "del L[0] shifts every remaining item inside a loop (O(n) per call)",
    "P3": "string concatenation on %s inside a loop copies the whole string (O(n^2))",
    "P4-sort": "sorting the unchanged list %r on every iteration (O(n log n) per iteration)",
    "P4-call": "%s(%s) rebuilds/reduces the unchanged list on every iteration",
    "P5": "nested loops compare every pair to match by key (O(n*m)); outer loop at line %d",
    "P6": "rebuilding the list %r with a concatenation on every iteration (O(n^2))",
}

STR_METHODS = frozenset({
    "capitalize", "casefold", "center", "expandtabs", "format", "format_map", "join", "ljust",
    "lower", "lstrip", "removeprefix", "removesuffix", "replace", "rjust", "rstrip", "strip",
    "swapcase", "title", "translate", "upper", "zfill",
})
LIST_METHODS = frozenset({"split", "rsplit", "splitlines"})
LIST_EVIDENCE = frozenset({"append", "extend", "insert", "sort", "reverse"})
MUTATORS = frozenset({
    "append", "extend", "insert", "pop", "remove", "sort", "reverse", "clear", "__delitem__",
    "__setitem__", "__iadd__", "__imul__",
})
STR_BUILTINS = frozenset({"str", "chr", "repr", "ascii", "input"})
LIST_BUILTINS = frozenset({"list", "sorted"})
SCALAR_LIST_BUILTINS = frozenset({"sorted", "min", "max", "sum"})


def _literal_zero(node):
    return isinstance(node, ast.Constant) and type(node.value) is int and node.value == 0


def _is_str_expr(node):
    return isinstance(node, (ast.Constant, ast.JoinedStr)) and (
        isinstance(node, ast.JoinedStr) or type(node.value) is str)


def _annotation_kind(node):
    """('list', element-kind) or ('str', None) or (None, None) for an annotation."""
    if isinstance(node, ast.Name):
        if node.id in ("list", "List"):
            return "list", None
        if node.id == "str":
            return "str", None
        return None, None
    if isinstance(node, ast.Subscript):
        base, _ = _annotation_kind(node.value)
        if base == "list":
            element, _ = _annotation_kind(node.slice)
            return "list", element
    return None, None


def _target_names(node):
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            names.add(child.id)
    return names


def _contains_name(node, name):
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def _names_in(node):
    """Loaded names of a comparison, ignoring subscript indices: a[i-1] contributes `a`, not `i`.

    Pairwise matching compares items (or their keys); a dynamic-programming table compares values at
    two independent positions, which is the algorithm, not a lookup that a dict could replace.
    """
    names = set()
    stack = [node]
    while stack:
        one = stack.pop()
        if isinstance(one, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(one, ast.Subscript):
            stack.append(one.value)
            continue
        if isinstance(one, ast.Name) and isinstance(one.ctx, ast.Load):
            names.add(one.id)
        stack.extend(ast.iter_child_nodes(one))
    return names


def _indexed_loop(node):
    """A loop over range()/enumerate()/zip() positions rather than over the items themselves."""
    call = getattr(node, "iter", None)
    return (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id in ("range", "enumerate", "zip"))


def _walk_no_scopes(nodes):
    """Every node under `nodes`, without entering a nested function, lambda or class body."""
    stack = list(nodes)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(node))


class Scope(object):
    """The list/str provenance of the names of one module, function or class body."""

    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
        self.kinds = {}
        self.elements = {}
        self.bindings = {}
        self.augments = {}
        self.loop_targets = {}
        self.explicit = {}
        self.evidence = {}
        self.touched = set()
        self._alias_edges = {}
        self._alias_cache = {}
        self._collect()
        self._collect_aliases()
        self._resolve()

    def _collect_aliases(self):
        """Undirected edges between names bound directly to one another (`view = items`)."""
        for name, values in self.bindings.items():
            for value in values:
                if isinstance(value, ast.Name) and value.id != name:
                    self._alias_edges.setdefault(name, set()).add(value.id)
                    self._alias_edges.setdefault(value.id, set()).add(name)

    def aliases(self, name):
        """`name` and every name that is the same object through a direct assignment."""
        cached = self._alias_cache.get(name)
        if cached is not None:
            return cached
        seen = {name}
        stack = [name]
        while stack:
            current = stack.pop()
            for other in self._alias_edges.get(current, ()):
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        self._alias_cache[name] = seen
        return seen

    def kind(self, name):
        if name in self.kinds:
            return self.kinds[name]
        if name in self.touched:
            return None
        if self.parent is not None:
            return self.parent.kind(name)
        return None

    def element(self, name):
        if name in self.kinds:
            return self.elements.get(name) if self.kinds[name] == "list" else None
        if name in self.touched:
            return None
        if self.parent is not None:
            return self.parent.element(name)
        return None

    def _touch(self, name):
        self.touched.add(name)
        self.bindings.setdefault(name, [])

    def _hint(self, name, kind):
        self._touch(name)
        self.explicit.setdefault(name, set()).add(kind)

    def _bind(self, name, value):
        self._touch(name)
        self.bindings.setdefault(name, []).append(value)

    def _collect_arguments(self, arguments):
        for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
            kind, element = _annotation_kind(arg.annotation) if arg.annotation is not None else (None, None)
            if kind:
                self._hint(arg.arg, kind)
                if element:
                    self.elements[arg.arg] = element
        for arg in (arguments.vararg, arguments.kwarg):
            if arg is not None and arg.annotation is not None:
                kind, element = _annotation_kind(arg.annotation)
                if kind:
                    self._hint(arg.arg, kind)
                    if element:
                        self.elements[arg.arg] = element

    def _collect(self):
        node = self.node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._collect_arguments(node.args)
        elif isinstance(node, ast.Lambda):
            self._collect_arguments(node.args)
        body = getattr(node, "body", [])
        if not isinstance(body, list):
            body = [body]
        for statement in body:
            self._collect_statement(statement)

    def _collect_statement(self, node):
        stack = [node]
        while stack:
            one = stack.pop()
            if isinstance(one, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(one, ast.Assign):
                for target in one.targets:
                    self._collect_target(target, one.value)
            elif isinstance(one, ast.AnnAssign):
                kind, element = _annotation_kind(one.annotation)
                if isinstance(one.target, ast.Name):
                    if kind:
                        self._hint(one.target.id, kind)
                        if element:
                            self.elements[one.target.id] = element
                    if one.value is not None:
                        self._bind(one.target.id, one.value)
                    else:
                        self._touch(one.target.id)
                elif one.value is not None:
                    self._collect_mutation(one.target)
            elif isinstance(one, ast.AugAssign):
                if isinstance(one.target, ast.Name):
                    self._touch(one.target.id)
                    self.augments.setdefault(one.target.id, []).append(one)
                else:
                    self._collect_mutation(one.target)
            elif isinstance(one, (ast.For, ast.AsyncFor)):
                for name in _target_names(one.target):
                    self._touch(name)
                    self.loop_targets.setdefault(name, []).append(one.iter)
            elif isinstance(one, ast.NamedExpr):
                if isinstance(one.target, ast.Name):
                    self._bind(one.target.id, one.value)
            elif isinstance(one, ast.With):
                for item in one.items:
                    if isinstance(item.optional_vars, ast.Name):
                        self._touch(item.optional_vars.id)
            elif isinstance(one, ast.Delete):
                for target in one.targets:
                    for name in _target_names(target):
                        self._hint(name, "other")
                    self._collect_mutation(target)
            elif isinstance(one, ast.Call):
                self._collect_call(one)
            stack.extend(ast.iter_child_nodes(one))

    def _collect_target(self, target, value):
        if isinstance(target, ast.Name):
            self._bind(target.id, value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for name in _target_names(target):
                self._touch(name)
                self.bindings.setdefault(name, []).append(None)
        else:
            self._collect_mutation(target)

    def _collect_mutation(self, target):
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            self._hint(target.value.id, "other")

    def _collect_call(self, call):
        func = call.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            return
        name = func.value.id
        if func.attr in LIST_EVIDENCE:
            self._hint(name, "list")
        elif func.attr in STR_METHODS:
            self._hint(name, "str")
        elif func.attr in LIST_METHODS:
            # split/rsplit/splitlines return a list, but their receiver is a string.
            self._hint(name, "str")
        elif func.attr == "copy":
            self._touch(name)

    def _resolve(self):
        for _ in range(32):
            changed = False
            for name in self.touched:
                candidate, element = self._classify(name)
                if candidate is not None and self.kinds.get(name) != candidate:
                    self.kinds[name] = candidate
                    if element:
                        self.elements[name] = element
                    changed = True
            if not changed:
                break
        # A name whose bindings never settled is not a proven list or str.
        for _ in range(4):
            changed = False
            for name in self.touched:
                if name not in self.kinds:
                    self.kinds[name] = "other"
                    changed = True
            if not changed:
                break

    def _classify(self, name):
        if name in self.kinds:
            return self.kinds[name], self.elements.get(name)
        kinds = set(self.explicit.get(name, ()))
        element = None
        unknown = False
        for value in self.bindings.get(name, ()):
            if value is None:
                unknown = True
                continue
            kind, one_element = self._expr_kind(value)
            if kind is None:
                unknown = True
            else:
                kinds.add(kind)
                if kind == "list" and one_element:
                    element = one_element
        for node in self.augments.get(name, ()):
            current = kinds.pop() if len(kinds) == 1 else None
            if current is not None:
                kinds.add(current)
            kind, one_element = self._augment_kind(name, node, current)
            if kind is None:
                unknown = True
            else:
                kinds.add(kind)
                if kind == "list" and one_element:
                    element = one_element
        for iterable in self.loop_targets.get(name, ()):
            kind, one_element = self._expr_kind(iterable)
            if kind == "str":
                kinds.add("str")
            elif kind == "list":
                element_kind = self.element(iterable.id) if isinstance(iterable, ast.Name) else one_element
                kinds.add(element_kind or "other")
            else:
                unknown = True
        if unknown:
            return None, None
        if len(kinds) == 1:
            return kinds.pop(), element
        if len(kinds) > 1:
            return "other", None
        return None, None

    def _augment_kind(self, name, node, current=None):
        if not isinstance(node.op, ast.Add):
            return "other", None
        if current is None:
            current = self.kinds.get(name)
        kind, element = self._expr_kind(node.value)
        if current == "str":
            return "str", None
        if current == "list":
            return "list", element
        if kind == "str":
            return "str", None
        if kind == "list":
            return "list", element
        return None, None

    def _expr_kind(self, node):
        if node is None:
            return None, None
        if isinstance(node, ast.Constant):
            return ("str", None) if type(node.value) is str else (None, None)
        if isinstance(node, ast.JoinedStr):
            return "str", None
        if isinstance(node, (ast.List, ast.ListComp)):
            element = None
            if isinstance(node, ast.List) and node.elts:
                kinds = set()
                for item in node.elts:
                    kind, _ = self._expr_kind(item)
                    if kind:
                        kinds.add(kind)
                if len(kinds) == 1:
                    element = kinds.pop()
            return "list", element
        if isinstance(node, ast.Name):
            kind = self.kind(node.id)
            return (kind, self.element(node.id)) if kind else (None, None)
        if isinstance(node, ast.Attribute):
            return None, None
        if isinstance(node, ast.Subscript):
            kind, element = self._expr_kind(node.value)
            if kind == "str":
                return "str", None
            if kind == "list":
                return ((element or None), None)
            return None, None
        if isinstance(node, ast.BinOp):
            left_kind, left_element = self._expr_kind(node.left)
            right_kind, right_element = self._expr_kind(node.right)
            if isinstance(node.op, ast.Add):
                if left_kind == "str" or right_kind == "str":
                    return "str", None
                if left_kind == "list":
                    return "list", left_element or right_element
                if right_kind == "list":
                    return "list", right_element or left_element
                return None, None
            if isinstance(node.op, ast.Mult):
                if left_kind == "list" and isinstance(node.right, ast.Constant):
                    return "list", left_element
                if right_kind == "list" and isinstance(node.left, ast.Constant):
                    return "list", right_element
                if left_kind == "str" and isinstance(node.right, ast.Constant):
                    return "str", None
                if right_kind == "str" and isinstance(node.left, ast.Constant):
                    return "str", None
                return None, None
            if isinstance(node.op, ast.Mod) and left_kind == "str":
                return "str", None
            return None, None
        if isinstance(node, ast.IfExp):
            left_kind, left_element = self._expr_kind(node.body)
            right_kind, right_element = self._expr_kind(node.orelse)
            if left_kind == right_kind:
                return left_kind, left_element or right_element
            return None, None
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in LIST_BUILTINS:
                    return "list", None
                if func.id in STR_BUILTINS:
                    return "str", None
                return None, None
            if isinstance(func, ast.Attribute):
                kind, element = self._expr_kind(func.value)
                if func.attr in LIST_METHODS:
                    return "list", "str" if func.attr != "splitlines" else None
                if func.attr == "copy" and kind == "list":
                    return "list", element
                if func.attr == "join" and kind == "str":
                    return "str", None
                if func.attr in STR_METHODS and kind == "str":
                    return "str", None
            return None, None
        return None, None


class Loop(object):
    def __init__(self, node, body, test=None):
        self.node = node
        self.body = body
        self.test = test


def _loop_parts(loop):
    parts = list(loop.body)
    if loop.test is not None:
        parts.append(loop.test)
    return parts


def _loop_target_names(node):
    names = set()
    if isinstance(node, (ast.For, ast.AsyncFor)):
        names |= _target_names(node.target)
    elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        for generator in node.generators:
            names |= _target_names(generator.target)
    return names


def _loop_touches(loop, name, ignore=None, accumulate=None, aliases=()):
    """Whether this loop rebinds or mutates `name` in its own iteration (nested scopes excluded).

    `ignore` skips the hit being checked.  `accumulate(node, name)` marks bindings that are the
    accumulation pattern itself (e.g. `s += x`): those grow the value, they do not reset it.
    `aliases` are other names bound to the same object, so mutating one mutates all of them.
    """
    for current in (name, *(alias for alias in aliases if alias != name)):
        if _loop_touches_one(loop, current, ignore, accumulate):
            return True
    return False


def _loop_touches_one(loop, name, ignore=None, accumulate=None):
    if name in _loop_target_names(loop.node):
        return True
    for node in _walk_no_scopes(_loop_parts(loop)):
        if node is ignore or (accumulate is not None and accumulate(node, name)):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = getattr(node, "targets", None) or [getattr(node, "target", None)]
            for target in targets:
                if target is not None and _contains_name(target, name):
                    return True
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            if _contains_name(node.target, name):
                return True
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for generator in node.generators:
                if _contains_name(generator.target, name):
                    return True
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) \
                        and target.value.id == name:
                    return True
                if _contains_name(target, name):
                    return True
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                    and func.value.id == name and func.attr in MUTATORS:
                return True
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) \
                and isinstance(node.value, ast.Name) and node.value.id == name:
            return True
    return False


def _starred_list(node, name):
    if not isinstance(node, ast.List):
        return False
    return any(isinstance(item, ast.Starred) and isinstance(item.value, ast.Name)
               and item.value.id == name for item in node.elts)


def _list_plus(node, name):
    return (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)
            and isinstance(node.left, ast.Name) and node.left.id == name
            and isinstance(node.right, ast.List))


def _is_p3_accumulation(node, name):
    return (isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add)
            and isinstance(node.target, ast.Name) and node.target.id == name)


def _is_p6_accumulation(node, name):
    if not isinstance(node, ast.Assign):
        return False
    if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
        return False
    return _list_plus(node.value, name) or _starred_list(node.value, name)


def _keyword_values(call):
    """The `key` and `reverse` expressions of a sort call; these must not change per iteration."""
    return [keyword.value for keyword in call.keywords if keyword.arg in ("key", "reverse")]


def _loop_dependent(loops, nodes, scope=None):
    """Whether any expression reads a name that changes between iterations."""
    names = set()
    for node in nodes:
        names |= {child.id for child in ast.walk(node)
                  if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)}
    if not names:
        return False
    for loop in loops:
        if names & _loop_target_names(loop.node):
            return True
        for name in names:
            aliases = scope.aliases(name) if scope is not None else ()
            if _loop_touches(loop, name, aliases=aliases):
                return True
    return False


class Linter(object):
    def __init__(self, filename):
        self.filename = str(filename)
        self.hits = []
        self.scope = None

    def run(self, tree):
        self._visit_scope(tree, None)
        self.hits.sort(key=lambda hit: (hit["line"], hit["col"], hit["rule"]))
        return self.hits

    def _visit_scope(self, node, parent):
        previous = self.scope
        self.scope = Scope(node, parent)
        if isinstance(node, ast.Module):
            self._visit_statements(node.body, [])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            self._visit_statements(node.body, [])
        elif isinstance(node, ast.Lambda):
            self._visit(node.body, [])
        else:
            self._visit_statements(getattr(node, "body", []), [])
        self.scope = previous

    def _visit_statements(self, statements, loops):
        for statement in statements:
            self._visit(statement, loops)

    def _visit(self, node, loops):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            self._visit_scope(node, self.scope)
            return
        if isinstance(node, (ast.For, ast.AsyncFor)):
            self._visit(node.target, loops)
            self._visit(node.iter, loops)
            if loops:
                self._maybe_pairwise(loops[-1].node, node, node.body)
            loop = Loop(node, node.body)
            self._visit_statements(node.body, loops + [loop])
            self._visit_statements(node.orelse, loops)
            return
        if isinstance(node, ast.While):
            loop = Loop(node, node.body, test=node.test)
            self._visit(node.test, loops + [loop])
            self._visit_statements(node.body, loops + [loop])
            self._visit_statements(node.orelse, loops)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for generator in node.generators:
                self._visit(generator.iter, loops)
            loop = Loop(node, [node])
            inner = loops + [loop]
            if isinstance(node, ast.DictComp):
                self._visit(node.key, inner)
                self._visit(node.value, inner)
            else:
                self._visit(node.elt, inner)
            for generator in node.generators:
                for condition in generator.ifs:
                    self._visit(condition, inner)
            return
        if loops:
            self._detect(node, loops)
        for child in ast.iter_child_nodes(node):
            self._visit(child, loops)

    def _add(self, rule, node, message, loop_line):
        self.hits.append({
            "rule": rule,
            "file": self.filename,
            "line": node.lineno,
            "col": node.col_offset + 1,
            "message": message,
            "fix": FIXES[rule],
            "loop_line": loop_line,
        })

    def _detect(self, node, loops):
        loop = loops[-1]
        scope = self.scope
        loop_line = loop.node.lineno
        if isinstance(node, ast.Compare):
            for op, comparator in zip(node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comparator, ast.Name):
                    name = comparator.id
                    if scope.kind(name) == "list" \
                            and not _loop_touches(loop, name, aliases=scope.aliases(name)):
                        self._add("P1", node, MESSAGES["P1-in"] % name, loop_line)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                name = func.value.id
                if scope.kind(name) == "list":
                    if func.attr == "index" \
                            and not _loop_touches(loop, name, aliases=scope.aliases(name)):
                        self._add("P1", node, MESSAGES["P1-index"] % name, loop_line)
                    elif func.attr == "count" \
                            and not _loop_touches(loop, name, aliases=scope.aliases(name)):
                        self._add("P1", node, MESSAGES["P1-count"] % name, loop_line)
                    elif func.attr == "pop" and node.args and _literal_zero(node.args[0]):
                        self._add("P2", node, MESSAGES["P2-pop"], loop_line)
                    elif func.attr == "insert" and len(node.args) >= 2 and _literal_zero(node.args[0]):
                        self._add("P2", node, MESSAGES["P2-insert"], loop_line)
                    elif func.attr == "sort" \
                            and not _loop_touches(loop, name, ignore=node,
                                                  aliases=scope.aliases(name)) \
                            and not _loop_dependent(loops, _keyword_values(node), scope):
                        self._add("P4", node, MESSAGES["P4-sort"] % name, loop_line)
            elif isinstance(func, ast.Name) and func.id in SCALAR_LIST_BUILTINS and node.args:
                argument = node.args[0]
                if isinstance(argument, ast.Name) and scope.kind(argument.id) == "list" \
                        and not _loop_touches(loop, argument.id,
                                              aliases=scope.aliases(argument.id)) \
                        and not _loop_dependent(loops, _keyword_values(node), scope):
                    self._add("P4", node, MESSAGES["P4-call"] % (func.id, argument.id), loop_line)
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) \
                        and _literal_zero(target.slice) and scope.kind(target.value.id) == "list":
                    self._add("P2", node, MESSAGES["P2-del"], loop_line)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.op, ast.Add):
                target = node.target
                if isinstance(target, ast.Name):
                    target_name = "`%s`" % target.id
                    is_str = scope.kind(target.id) == "str" or scope._expr_kind(node.value)[0] == "str"
                elif isinstance(target, ast.Attribute):
                    target_name = "`%s.%s`" % (getattr(target.value, "id", "?"), target.attr)
                    is_str = scope._expr_kind(node.value)[0] == "str"
                else:
                    target_name, is_str = "", False
                if is_str:
                    suppressed = (isinstance(target, ast.Name)
                                  and _loop_touches(loop, target.id, ignore=node,
                                                    accumulate=_is_p3_accumulation))
                    if not suppressed:
                        self._add("P3", node, MESSAGES["P3"] % target_name, loop_line)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if (_list_plus(node.value, target.id) or _starred_list(node.value, target.id)) \
                            and not _loop_touches(loop, target.id, ignore=node,
                                                  accumulate=_is_p6_accumulation):
                        self._add("P6", node, MESSAGES["P6"] % target.id, loop_line)

    def _maybe_pairwise(self, outer, inner, body):
        if not isinstance(inner, ast.For) or not isinstance(outer, ast.For):
            return
        outer_names = _target_names(outer.target)
        inner_names = _target_names(inner.target)
        if not outer_names or not inner_names:
            return
        # Two indexed loops comparing values at their two positions is dynamic programming, not a
        # search for matching items by key.
        if _indexed_loop(outer) and _indexed_loop(inner):
            return
        for node in _walk_no_scopes(body):
            if not isinstance(node, ast.If):
                continue
            for child in _walk_no_scopes([node.test]):
                if not isinstance(child, ast.Compare):
                    continue
                for op, comparator in zip(child.ops, child.comparators):
                    if not isinstance(op, ast.Eq):
                        continue
                    left = _names_in(child.left)
                    right = _names_in(comparator)
                    if (left & outer_names and right & inner_names) or \
                            (right & outer_names and left & inner_names):
                        self._add("P5", inner, MESSAGES["P5"] % outer.lineno, outer.lineno)
                        return


def lint_source(source, filename="<string>"):
    """All hits in this source, in source order; raises SyntaxError for a source that does not parse."""
    tree = ast.parse(source, filename=str(filename))
    return Linter(filename).run(tree)


def lint_file(path):
    path = Path(path)
    return lint_source(path.read_text(encoding="utf-8"), path)


def format_hit(hit):
    return "%s:%d:%d: perf %s: %s; fix: %s" % (
        hit["file"], hit["line"], hit["col"], hit["rule"], hit["message"], hit["fix"])


def main(files, json_output=False, strict=False):
    hits, failed = [], False
    for path in files:
        try:
            hits.extend(lint_file(path))
        except (OSError, UnicodeError, SyntaxError) as error:
            failed = True
            print("%s: %s" % (path, error), file=sys.stderr)
    if json_output:
        for hit in hits:
            print(json.dumps(hit, ensure_ascii=False))
    else:
        for hit in hits:
            print(format_hit(hit), file=sys.stderr)
    if failed:
        return 2
    return 5 if strict and hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
