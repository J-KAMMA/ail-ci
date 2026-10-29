"""struct: pack, unpack, unpack_from, calcsize and error for the integer formats and x padding.

The format must be a literal string known at compile time; floats, half floats, pascal strings,
chars, bools, strings, the Struct class and pack_into are refused by name here. The supported
calls are lowered to prelude_struct.py, which builds and reads bytes with int.to_bytes /
int.from_bytes.
"""
import ast

SUPPORTED = set("0123456789 \t\n@=<>!bBhHiIlLqQnNP?xcs")
FLOATS = set("fde")
CODES = set("bBhHiIlLqQnNP?xcs")


class Refused(ValueError):
    def __init__(self, line, text):
        ValueError.__init__(self, text)
        self.line = line
        self.text = text


def _refuse(node, text):
    error = Refused(getattr(node, "lineno", 1), text)
    error.source_line = getattr(node, "lineno", 1)
    error.source_column = getattr(node, "col_offset", 0) + 1
    raise error


def _check_buffer(node, value):
    if isinstance(value, (ast.List, ast.Tuple, ast.Dict, ast.Set, ast.JoinedStr)):
        _refuse(node, "struct: the buffer must be bytes or a bytearray, not a list, tuple, dict, set or str")
    if isinstance(value, ast.Constant) and not isinstance(value.value, bytes):
        _refuse(node, "struct: the buffer must be bytes or a bytearray")


def _check_format(node, fmt):
    if not isinstance(fmt, ast.Constant) or not isinstance(fmt.value, str):
        _refuse(node, "struct: the format string must be a literal known at compile time")
    text = fmt.value
    pos = 0
    first = True
    native = True
    while pos < len(text):
        ch = text[pos]
        if ch in " \t\n":
            pos += 1
            continue
        if ch in "@=<>!":
            if not first:
                _refuse(node, "struct: a byte-order character is only allowed at the start of the format")
            first = False
            if ch in "=<>!":
                native = False
            pos += 1
            continue
        first = False
        if ch >= "0" and ch <= "9":
            pos += 1
            continue
        if ch in FLOATS or ch == "p":
            _refuse(node, "struct format code %r is not built: only b B h H i I l L q Q n N P and x "
                          "are built (no floats or pascal strings)" % ch)
        if ch in "?cs":
            _refuse(node, "struct format code %r is not built: only integer formats (b B h H i I l L q Q "
                          "n N P) and x padding are built" % ch)
        if ch in "nNP" and not native:
            _refuse(node, "struct format code %r needs the native byte order (no <, >, ! or = prefix)" % ch)
        if ch not in CODES:
            _refuse(node, "struct format code %r is not built" % ch)
        pos += 1


def _format_items(node, fmt):
    text = fmt.value
    pos = 0
    items = []
    while pos < len(text):
        ch = text[pos]
        if ch in " \t\n":
            pos += 1
            continue
        if ch in "@=<>!":
            pos += 1
            continue
        start = pos
        while pos < len(text) and "0" <= text[pos] <= "9":
            pos += 1
        count = 1 if pos == start else int(text[start:pos])
        if pos >= len(text):
            _refuse(node, "struct: repeat count given without format specifier")
        ch = text[pos]
        pos += 1
        if ch == "x":
            continue
        if ch == "s":
            items.append("s")
        elif ch == "c":
            items.extend(["s"] * count)
        elif ch == "?":
            items.extend(["?"] * count)
        else:
            items.extend(["i"] * count)
    return items


def rewrite_text(source):
    if "struct" not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    aliases = {}
    names = {}
    imports = []
    body = []
    found = False
    for node in tree.body:
        if isinstance(node, ast.Import):
            rest = []
            for alias in node.names:
                if alias.name == "struct":
                    aliases[alias.asname or "struct"] = "struct"
                    imports.append(node)
                    found = True
                else:
                    rest.append(alias)
            if rest:
                node.names = rest
                body.append(node)
            continue
        if isinstance(node, ast.ImportFrom) and not node.level and node.module == "struct":
            found = True
            imports.append(node)
            for alias in node.names:
                local = alias.asname or alias.name
                if alias.name in ("pack", "unpack", "unpack_from", "calcsize"):
                    names[local] = alias.name
                elif alias.name == "error":
                    names[local] = "error"
                else:
                    _refuse(node, "struct.%s is not built: only pack, unpack, unpack_from, calcsize and error are" % alias.name)
            continue
        body.append(node)
    tree.body = body
    if not found:
        return source

    def module_attr(node):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
            return node.attr
        return None

    class Replace(ast.NodeTransformer):
        counter = 0
        pending = []

        def visit(self, node):
            if isinstance(node, ast.stmt):
                saved = self.pending
                self.pending = []
                node = ast.NodeTransformer.visit(self, node)
                pending = self.pending
                self.pending = saved
                if pending:
                    return pending + [node]
                return node
            return ast.NodeTransformer.visit(self, node)

        def visit_Attribute(self, node):
            if module_attr(node) == "error":
                return ast.copy_location(ast.Name(id="_AilStructError", ctx=ast.Load()), node)
            if module_attr(node) is not None and module_attr(node) not in ("pack", "unpack", "unpack_from", "calcsize", "error"):
                _refuse(node, "struct.%s is not built: only pack, unpack, unpack_from, calcsize and error are" % module_attr(node))
            return self.generic_visit(node)

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load) and names.get(node.id) == "error":
                return ast.copy_location(ast.Name(id="_AilStructError", ctx=node.ctx), node)
            if isinstance(node.ctx, ast.Load) and node.id in names and names[node.id] != "error":
                return ast.copy_location(ast.Name(id="_ail_struct_" + names[node.id], ctx=node.ctx), node)
            return node

        def visit_Call(self, node):
            func = node.func
            what = None
            if module_attr(func) in ("pack", "unpack", "unpack_from", "calcsize"):
                what = module_attr(func)
            elif isinstance(func, ast.Name) and names.get(func.id) in ("pack", "unpack", "unpack_from", "calcsize"):
                what = names[func.id]
            if what is None:
                return self.generic_visit(node)
            if not node.args:
                _refuse(node, "struct.%s: the format string must be a literal known at compile time" % what)
            _check_format(node, node.args[0])
            if what == "calcsize":
                if len(node.args) != 1 or node.keywords:
                    _refuse(node, "struct.calcsize takes one format argument")
                new = ast.Call(func=ast.Name(id="_ail_struct_size", ctx=ast.Load()),
                               args=[self.visit(node.args[0])], keywords=[])
                return ast.copy_location(new, node)
            if what == "pack":
                if node.keywords:
                    _refuse(node, "struct.pack takes positional values only")
                if any(isinstance(a, ast.Starred) for a in node.args[1:]):
                    _refuse(node, "struct.pack: *values is not built; spell the values")
                wrapped = []
                for argument in node.args[1:]:
                    value = self.visit(argument)
                    if isinstance(value, ast.Constant) and isinstance(value.value, bool):
                        value = ast.copy_location(ast.Constant(value=1 if value.value else 0), value)
                    wrapped.append(ast.Call(func=ast.Name(id="_ail_struct_int_arg", ctx=ast.Load()),
                                            args=[value], keywords=[]))
                value_list = ast.List(elts=wrapped, ctx=ast.Load())
                new = ast.Call(func=ast.Name(id="_ail_struct_pack", ctx=ast.Load()),
                               args=[self.visit(node.args[0]), value_list], keywords=[])
                return ast.copy_location(new, node)
            if what == "unpack":
                if len(node.args) != 2 or node.keywords:
                    _refuse(node, "struct.unpack takes a format and a buffer")
                kinds = _format_items(node, node.args[0])
                if not kinds:
                    _refuse(node, "struct: unpack of a format with no values is not built")
                _check_buffer(node, node.args[1])
                data = ast.Call(func=ast.Name(id="bytes", ctx=ast.Load()), args=[self.visit(node.args[1])], keywords=[])
                offset = ast.Constant(value=0)
                from_unpack = False
                fmt = self.visit(node.args[0])
            else:
                if len(node.args) not in (2, 3) or node.keywords:
                    _refuse(node, "struct.unpack_from takes a format, a buffer and an optional offset")
                kinds = _format_items(node, node.args[0])
                if not kinds:
                    _refuse(node, "struct: unpack of a format with no values is not built")
                _check_buffer(node, node.args[1])
                data = ast.Call(func=ast.Name(id="bytes", ctx=ast.Load()), args=[self.visit(node.args[1])], keywords=[])
                offset = self.visit(node.args[2]) if len(node.args) == 3 else ast.Constant(value=0)
                from_unpack = True
                fmt = self.visit(node.args[0])
            self.counter = self.counter + 1
            result_name = "_ail_struct_result_" + str(self.counter)
            unpacked = ast.Call(func=ast.Name(id="_ail_struct_unpack", ctx=ast.Load()),
                                args=[fmt, data, offset, ast.Constant(value=from_unpack)], keywords=[])
            self.pending.append(ast.copy_location(
                ast.Assign(targets=[ast.Name(id=result_name, ctx=ast.Store())], value=unpacked), node))
            elements = [ast.Subscript(value=ast.Name(id=result_name, ctx=ast.Load()),
                                      slice=ast.Constant(value=index), ctx=ast.Load())
                        for index in range(len(kinds))]
            return ast.copy_location(ast.Tuple(elts=elements, ctx=ast.Load()), node)

    replacer = Replace()
    tree.body = [replacer.visit(stmt) for stmt in tree.body]
    from stdlib5 import prelude, insert_after_imports
    insert_after_imports(tree, prelude("struct"))
    ast.fix_missing_locations(tree)
    return ast.unparse(tree).rstrip("\n") + "\n"
