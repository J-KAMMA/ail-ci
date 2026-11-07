"""The agent-actionable machine form of a compiler diagnostic.

The human text is unchanged (it is the byte-for-byte `message`); this module adds the stable code,
the one-sentence cause and the literal edit an agent can apply.  Data follows
docs/design/AGENT_ERRORS.md: AIL0101..AIL0116, one family per refusal or fallback note.

Each family also has a locator: it reads the user's own source (AST plus text) and returns the
position of the construct and, where the design has one, the literal whole-line edit.  The table's
`replace`/`with` pair is only the fallback for a source the locator cannot read (an .ail file, or a
shape the design does not describe).
"""
import ast
import json
import re


FAMILIES = (
    dict(code='AIL0101', pattern='sys.stdin.buffer.readline', cause="`sys.stdin.buffer.readline` is saved in `read`, but this compiler accepts `sys.stdin.buffer.readline()` only as a direct call; the saved method fails at run time with `'...' object has no attribute 'readline'`.", replace='read = sys.stdin.buffer.readline\nprint(read().decode().strip())',
         **{'with': 'print(sys.stdin.readline().strip())'}),
    dict(code='AIL0102', pattern='_ail_l1l', cause='`b = heapq.heappop(fh)` pops a berth number from a 1-field free list, while `entry = heapq.heappop(wait1)` pops a 5-field job row; the compiler captures both pops in one temporary and a captured row must have one width.', replace='                b = heapq.heappop(fh)',
         **{'with': '                fh.sort()\n                b = fh.pop(0)'}),
    dict(code='AIL0103', pattern='comparing a str with a number', cause='this compares a str with a number; a str is never equal to a number, so the branch is always taken or never taken.', replace='if s == 1:',
         **{'with': 'if s == "1":'}),
    dict(code='AIL0104', pattern='d.get(k) with one argument', cause='`dict.get(k)` gives None for a missing key, and this compiler has no None for an int value.', replace='v = d.get(k)',
         **{'with': 'v = d.get(k, -1)'}),
    dict(code='AIL0105', pattern='dict of containers', cause='this dict holds a list as a value; a typed dict holds int, float, str or bytes, not a list.', replace='accounts[rid] = [name, initial, True]\nprint(accounts[rid][0], accounts[rid][1])',
         **{'with': 'class Account:\n    def __init__(self, name: str, initial: int, active: bool) -> None:\n        self.name = name\n        self.initial = initial\n        self.active = active\n\naccounts: dict[int, Account] = {}\naccounts[rid] = Account(name, initial, True)\nprint(accounts[rid].name, accounts[rid].initial)'}),
    dict(code='AIL0106', pattern='class list comprehensions', cause='this list comprehension builds class instances; this compiler builds comprehensions of numbers, strings and bytes only.', replace='    return [P(x) for x in xs]',
         **{'with': '    out: list[P] = []\n    for x in xs:\n        out.append(P(x))\n    return out'}),
    dict(code='AIL0107', pattern='mixes bools and numbers', cause="this dict literal puts an int and a bool in the same dict; an AIL dict has one value type. Writing `0` / `1` to match the int would change what prints (`0` instead of `False`).", replace="d = {'type': 'when', 'line': 3, 'body': [], 'has_else': False}\nprint(d['line'], d['has_else'])",
         **{'with': "class Node:\n    def __init__(self, kind: str, line: int, has_else: bool) -> None:\n        self.kind = kind\n        self.line = line\n        self.has_else = has_else\n\nd = Node('when', 3, False)\nprint(d.line, d.has_else)"}),
    dict(code='AIL0108', pattern='returns bytes on one path and a number', cause='this function returns `bytes` on one path and a number on the other; one function has one return type.', replace='    return 0',
         **{'with': '    return b"0"'}),
    dict(code='AIL0109', pattern='while-else is unsupported', cause='`while ... else:` is not supported; when the loop has no `break`, the `else` body always runs and can move after the loop.', replace='while i < 3:\n    i += 1\nelse:\n    print("done", i)',
         **{'with': 'while i < 3:\n    i += 1\nprint("done", i)'}),
    dict(code='AIL0110', pattern='nested annotation', cause='this annotation is two levels deep (a list of dicts); the typed path recognises one level of rows, `list[SomeClass]`.', replace='def sizes(records: list[dict[str, str]]) -> list[int]:\n    out = []\n    for r in records:\n        out.append(len(r))\n    return out\n\nprint(sizes([{"a": "1"}, {"b": "2", "c": "3"}]))',
         **{'with': 'class Row:\n    def __init__(self, a: str, b: str) -> None:\n        self.a = a\n        self.b = b\n\ndef sizes(records: list[Row]) -> list[int]:\n    out: list[int] = []\n    for r in records:\n        n = 1\n        if r.b:\n            n = 2\n        out.append(n)\n    return out\n\nprint(sizes([Row("1", ""), Row("2", "3")]))'}),
    dict(code='AIL0111', pattern='dunder method Fraction.__float__', cause='`float(...)` needs `Fraction.__float__`, which this compiler does not build; importing `fractions` prints this note, and the old position was inside the standard-library prelude rather than your file.', replace='from fractions import Fraction\nx = Fraction(1, 2)\nprint(float(x))',
         **{'with': 'print(1 / 2)'}),
    dict(code='AIL0112', pattern='format spec on a Decimal', cause='a format spec on a `Decimal` needs `Decimal.__format__`; this compiler applies format specs to int, float and str only. The old position was inside the `decimal` prelude rather than your file.', replace='print(f"{d:.2f}")',
         **{'with': 'print(f"{float(d):.2f}")'}),
    dict(code='AIL0113', pattern='yield: this language has no generators', cause='`yield` makes a generator, and this compiler has no generators.', replace='def gen(n: int):\n    for i in range(n):\n        yield i',
         **{'with': 'def gen(n: int) -> list[int]:\n    out: list[int] = []\n    for i in range(n):\n        out.append(i)\n    return out'}),
    dict(code='AIL0114', pattern='a tuple used where a single value is needed', cause='this comprehension builds a list of tuples in one expression; this compiler needs the list named, then the tuples appended to it.', replace='    return [(m, pow(base, -1, m)) for m in moduli]',
         **{'with': '    out: list[tuple[int, int]] = []\n    for m in moduli:\n        out.append((m, pow(base, -1, m)))\n    return out'}),
    dict(code='AIL0115', pattern='is a list parameter, which is read-only', cause="this is a `list` parameter, and parameters are read-only, so assigning an element cannot change the caller's list.", replace='def fill(arr: list[int]) -> None:\n    arr[0] = 1\n\nxs = [0, 0]\nfill(xs)',
         **{'with': 'def fill(arr: list[int]) -> list[int]:\n    out: list[int] = []\n    for x in arr:\n        out.append(x)\n    out[0] = 1\n    return out\n\nxs = [0, 0]\nxs = fill(xs)'}),
    dict(code='AIL0116', pattern='cannot tell the type of element', cause='this tuple element is an empty list or an unknown value; name its type.', replace='t = ([], n)',
         **{'with': 'xs: list[int] = []\nt = (xs, n)'}),
)

#: A refusal whose construct has no family in the table still gets a machine record.
UNCATALOGUED = 'AIL0000'


_LOCATION = re.compile(r'^(?:note|error): (?P<path>.+):(?P<line>\d+):(?P<col>\d+): ')
_BARE_LOCATION = re.compile(r'^(?P<path>.+):(?P<line>\d+):(?P<col>\d+): ')


def family(message):
    """The family a human diagnostic belongs to, or None for a message not in the table."""
    text = str(message or '')
    for item in FAMILIES:
        if item['pattern'] in text:
            return item
    return None


def _lines(source):
    return str(source or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')


def _parse(text):
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError):
        return None


def _segment(text, node):
    try:
        return ast.get_source_segment(text, node)
    except (AttributeError, TypeError, ValueError):
        return None


def _indent(line):
    return len(line) - len(line.lstrip())


def _parents(tree):
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    return parent


def _statement(node, parent):
    while node is not None and not isinstance(node, ast.stmt):
        node = parent.get(node)
    return node


def _apply(lines, first, last, edits):
    """The `with` text for `lines[first-1:last]` after `edits` (line -> [(start, end, text)])."""
    block = list(lines[first - 1:last])
    for number in sorted(edits, reverse=True):
        index = number - first
        if not 0 <= index < len(block):
            continue
        line = block[index]
        for start, end, text in sorted(edits[number], key=lambda edit: edit[0], reverse=True):
            line = line[:start] + text + line[end:]
        block[index] = line
    return '\n'.join(block)


def _fix(first, last, with_text, line=None, col=None, cause=None, force_position=False):
    first_line = with_text.split('\n')[0]
    return dict(fix={'replace_range': [first, last], 'with': with_text},
                line=first if line is None else line,
                col=(_indent(first_line) + 1 if col is None else col),
                cause=cause, force_position=force_position)


def _position(text):
    for pattern in (_LOCATION, _BARE_LOCATION):
        found = pattern.match(str(text or ''))
        if found:
            return found.group('path'), int(found.group('line')), int(found.group('col'))
    return None


def _find(source, block):
    """(first_line, last_line, column) of a literal block in source, 1-based, or None."""
    if not source or not block:
        return None
    lines, wanted = _lines(source), block.split('\n')
    for index in range(len(lines) - len(wanted) + 1):
        if lines[index:index + len(wanted)] == wanted:
            first = wanted[0]
            return index + 1, index + len(wanted), len(first) - len(first.lstrip()) + 1
    return None


# ------------------------------------------------------------------------------ family locators


def _stdin_replacement(text, call, parent):
    """The text that replaces `read()` and its `.decode()` / `.strip()` calls, or None.

    Only the shape the design describes is accepted: the saved method is called with no arguments
    and then, directly on the result, `.decode()` and optionally `.strip()`.  The decode is
    required, because `buffer.readline` gives bytes and the replacement gives a str."""
    if call.args or call.keywords:
        return None
    applied = []
    cursor = call
    while True:
        attribute = parent.get(cursor)
        if not isinstance(attribute, ast.Attribute) or attribute.value is not cursor:
            break
        caller = parent.get(attribute)
        if not (isinstance(caller, ast.Call) and caller.func is attribute
                and not caller.args and not caller.keywords):
            return None
        applied.append(attribute.attr)
        cursor = caller
    if applied not in (['decode'], ['decode', 'strip']):
        return None
    text_out = 'sys.stdin.readline()'
    if 'strip' in applied:
        text_out += '.strip()'
    return cursor, text_out


def _loc_stdin_buffer(text, lines, tree, item):
    if tree is None:
        return None
    saved = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Attribute)):
            chain = []
            cursor = node.value
            while isinstance(cursor, ast.Attribute):
                chain.append(cursor.attr)
                cursor = cursor.value
            chain.reverse()
            if chain[-2:] == ['buffer', 'readline']:
                saved[node.targets[0].id] = node
    parent = _parents(tree)
    for name, assign in saved.items():
        if assign.end_lineno != assign.lineno:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == name):
                continue
            statement = _statement(node, parent)
            if statement is None or statement.lineno <= assign.lineno:
                continue
            # the design's edit prints the line; a call used as a value would change what runs
            if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Name)
                    and statement.value.func.id == 'print' and len(statement.value.args) == 1
                    and not statement.value.keywords):
                return dict(line=statement.lineno, col=_indent(lines[statement.lineno - 1]) + 1,
                            fix=None, cause=None, force_position=True, no_fallback=True)
            replaced = _stdin_replacement(text, node, parent)
            if replaced is None or replaced[0] is not statement.value.args[0]:
                return dict(line=statement.lineno, col=_indent(lines[statement.lineno - 1]) + 1,
                            fix=None, cause=None, force_position=True, no_fallback=True)
            _outer, replacement = replaced
            # the edit removes the saved name: every other use of it would stop building
            allowed = {id(node.func)}
            for target in assign.targets:
                allowed.add(id(target))
            others = [inner for inner in ast.walk(tree)
                      if isinstance(inner, ast.Name) and inner.id == name and id(inner) not in allowed]
            if others:
                return dict(line=statement.lineno, col=_indent(lines[statement.lineno - 1]) + 1,
                            fix=None, cause=None, force_position=True, no_fallback=True)
            edits = {statement.lineno: [(statement.value.args[0].col_offset,
                                         statement.value.args[0].end_col_offset, replacement)]}
            block = _apply(lines, assign.lineno, statement.end_lineno, edits)
            # `with_text` must reproduce every line of the range: drop the saved-method line, which
            # the replacement text already covers, and keep the lines the user wrote between it and
            # the call byte for byte
            with_text = '\n'.join(block.split('\n')[1:])
            return _fix(assign.lineno, statement.end_lineno, with_text,
                        line=statement.lineno, col=_indent(lines[statement.lineno - 1]) + 1)
    return None


def _bindings(tree):
    """name -> the values bound to it (None for a binding that is not a simple value).

    A name with exactly one entry, bound to a constant or a literal, can be read statically; a name
    bound more than once (or by a loop, a parameter, a `with`, an item store) cannot."""
    values = {}

    def add(name, value):
        values.setdefault(name, []).append(value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        add(name.id, node.value if isinstance(target, ast.Name) else None)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                add(node.target.id, node.value)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            add(node.target.id, None)
        elif isinstance(node, ast.For):
            for name in ast.walk(node.target):
                if isinstance(name, ast.Name):
                    add(name.id, None)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = (list(node.args.args) + list(node.args.posonlyargs)
                         + list(node.args.kwonlyargs))
            if node.args.kwarg is not None:
                arguments.append(node.args.kwarg)
            if node.args.vararg is not None:
                arguments.append(node.args.vararg)
            for argument in arguments:
                add(argument.arg, None)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            for name in ast.walk(node.optional_vars):
                if isinstance(name, ast.Name):
                    add(name.id, None)
    return values


_MISSING = object()


def _constant_of(node, bindings):
    """The Python value of a constant expression, or `_MISSING` when it cannot be read statically."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        operand = _constant_of(node.operand, bindings)
        if isinstance(operand, (int, float, complex)) and not isinstance(operand, bool):
            return -operand if isinstance(node.op, ast.USub) else operand
        return _MISSING
    if isinstance(node, ast.Name):
        found = bindings.get(node.id)
        if found and len(found) == 1 and isinstance(found[0], ast.Constant):
            return found[0].value
    return _MISSING


def _loc_str_number(text, lines, tree, item):
    if tree is None:
        return None
    bindings = _bindings(tree)
    strings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for target in targets:
                    if isinstance(target, ast.Name):
                        strings.add(target.id)

    def is_number(node):
        return (isinstance(node, ast.Constant) and isinstance(node.value, (int, float, complex))
                and not isinstance(node.value, bool))

    def is_string(node):
        return ((isinstance(node, ast.Constant) and isinstance(node.value, str))
                or (isinstance(node, ast.Name) and node.id in strings))

    offending = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        for operator, right in zip(node.ops, node.comparators):
            if isinstance(operator, (ast.Eq, ast.NotEq)):
                if is_number(right) and is_string(left):
                    offending.append((node, right, left, operator))
                elif is_number(left) and is_string(right):
                    offending.append((node, left, right, operator))
            left = right
    if not offending:
        return None
    key = (_segment(text, offending[0][2]) or '', type(offending[0][3]).__name__)
    chosen = [entry for entry in offending
              if (_segment(text, entry[2]) or '', type(entry[3]).__name__) == key]
    other = _segment(text, chosen[0][2]) or 'this value'
    number = _segment(text, chosen[0][1]) or '1'
    always = 'True' if isinstance(chosen[0][3], ast.NotEq) else 'False'
    cause = ('`%s` is a str and `%s` is a number; a str is never equal to a number, so this '
             'comparison is always %s.' % (other, number, always))
    # A str is never equal to a number, so the comparison's value is the constant `False` (`Eq`) or
    # `True` (`NotEq`) whatever the str holds.  Two edits keep that exactly: write the number as a
    # string when the str provably differs from that text (the design's edit), and otherwise replace
    # the comparison with the constant itself.  A chained or multi-line comparison gets no edit.
    safe = True
    edits = {}
    constant = []
    for node, literal, string_side, operator in chosen:
        value = _constant_of(string_side, bindings)
        if node.lineno != node.end_lineno or len(node.ops) != 1:
            safe = False
            continue
        if isinstance(value, str) and value != str(literal.value):
            edits.setdefault(literal.lineno, []).append(
                (literal.col_offset, literal.end_col_offset, json.dumps(str(literal.value))))
        else:
            constant.append(node)
    if not safe:
        return dict(line=chosen[0][0].lineno, col=chosen[0][0].col_offset + 1, fix=None,
                    cause=cause, force_position=True, no_fallback=True)
    first = min(node.lineno for node, _number, _other, _op in chosen)
    last = max(node.end_lineno for node, _number, _other, _op in chosen)
    lines_out = _apply(lines, first, last, edits).split('\n')
    for node in constant:
        answer = 'False' if isinstance(node.ops[0], ast.Eq) else 'True'
        index = node.lineno - first
        if not 0 <= index < len(lines_out):
            return dict(line=chosen[0][0].lineno, col=chosen[0][0].col_offset + 1, fix=None,
                        cause=cause, force_position=True, no_fallback=True)
        line = lines_out[index]
        lines_out[index] = line[:node.col_offset] + answer + line[node.end_col_offset:]
    return _fix(first, last, '\n'.join(lines_out), cause=cause)


def _dict_literals(tree, bindings):
    """name -> the Constant keys of the dict literal bound once to it, or None when unknown.

    `None` also when the name is written through an item store: the literal is no longer the whole
    truth about which keys are present."""
    literals = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Name) and len(bindings.get(target.id) or ()) == 1:
                    keys = []
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant):
                            keys.append(key.value)
                        else:
                            keys = None
                            break
                    literals[target.id] = keys
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                    literals[target.value.id] = None
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                    literals[target.value.id] = None
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ('pop', 'popitem', 'clear', 'setdefault', 'update') \
                and isinstance(node.func.value, ast.Name):
            literals[node.func.value.id] = None
    return literals


def _loc_dict_get(text, lines, tree, item):
    if tree is None:
        return None
    bindings = _bindings(tree)
    literals = _dict_literals(tree, bindings)
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == 'get' and len(node.args) == 1 and not node.keywords]
    if not calls:
        return None
    calls.sort(key=lambda node: (node.lineno, node.col_offset))
    # `d.get(k, -1)` prints `-1` where CPython prints `None`, so an edit is published only when the
    # key is provably in the dict the receiver names, read straight from a literal that nothing else
    # touches; otherwise the position and cause alone
    safe = True
    literal_targets = set()
    receivers = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            literal_targets.update(id(target) for target in node.targets)
    for node in calls:
        receiver = node.func.value
        if not isinstance(receiver, ast.Name):
            safe = False
            continue
        keys = literals.get(receiver.id)
        if keys is None:
            safe = False
            continue
        key = _constant_of(node.args[0], bindings)
        if key is _MISSING or key not in set(keys):
            safe = False
            continue
        if node.lineno != node.end_lineno:
            safe = False
        receivers.setdefault(receiver.id, set()).add(id(receiver))
    for name, allowed in receivers.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id != name or id(node) in allowed:
                continue
            if id(node) not in literal_targets:
                safe = False
    defaults = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            kind = '-1'
            for value in node.value.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    kind = '""'
                elif isinstance(value, ast.Constant) and isinstance(value.value, float) and kind == '-1':
                    kind = '0.0'
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defaults[target.id] = kind
    call = _segment(text, calls[0]) or 'd.get(k)'
    cause = '`%s` gives None for a missing key, and this compiler has no None for an int value.' % call
    if not safe:
        return dict(line=calls[0].lineno, col=calls[0].col_offset + 1, fix=None, cause=cause,
                    force_position=True, no_fallback=True)
    edits = {}
    for node in calls:
        name = node.func.value.id
        edits.setdefault(node.end_lineno, []).append(
            (node.end_col_offset - 1, node.end_col_offset - 1, ', ' + defaults.get(name, '-1')))
    first = calls[0].lineno
    last = max(node.end_lineno for node in calls)
    return _fix(first, last, _apply(lines, first, last, edits), line=calls[0].lineno,
                col=calls[0].col_offset + 1, cause=cause)


def _loc_class_comprehension(text, lines, tree, item):
    if tree is None:
        return None
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.ListComp):
            continue
        comprehension = node.value
        element = comprehension.elt
        if not (isinstance(element, ast.Call) and isinstance(element.func, ast.Name)):
            continue
        if len(comprehension.generators) != 1:
            continue
        generator = comprehension.generators[0]
        if not isinstance(generator.target, ast.Name):
            continue
        class_name = element.func.id
        if class_name not in classes:
            return dict(line=node.lineno, col=node.col_offset + 1, fix=None, cause=None,
                        force_position=True)
        iterator = _segment(text, generator.iter) or 'values'
        element_text = _segment(text, element) or '%s(x)' % class_name
        indent = ' ' * node.col_offset
        with_text = '\n'.join((
            indent + 'out: list[%s] = []' % class_name,
            indent + 'for %s in %s:' % (generator.target.id, iterator),
            indent + '    out.append(%s)' % element_text,
            indent + 'return out'))
        cause = ('`%s` is a list comprehension that builds `%s` instances; this compiler builds '
                 'comprehensions of numbers, strings and bytes only.' % (element_text, class_name))
        return _fix(node.lineno, node.end_lineno, with_text, line=node.lineno,
                    col=node.col_offset + 1, cause=cause)
    return None


def _loc_bool_number(text, lines, tree, item):
    if tree is None:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        kinds = set()
        for value in node.values:
            if isinstance(value, ast.Constant):
                if isinstance(value.value, bool):
                    kinds.add('bool')
                elif isinstance(value.value, (int, float, complex)):
                    kinds.add('number')
        if kinds == {'bool', 'number'}:
            return dict(line=node.lineno, col=node.col_offset + 1, fix=None,
                        cause='this dict literal mixes bools and numbers; an AIL dict has one value '
                              'type. Writing `0` / `1` would change what prints.', force_position=True)
    return None


def _is_bytes(node, names=()):
    if isinstance(node, ast.Constant):
        return isinstance(node.value, bytes)
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.BinOp):
        return _is_bytes(node.left, names) or _is_bytes(node.right, names)
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == 'encode':
            return True
        if isinstance(func, ast.Name) and func.id == 'bytes':
            return True
    return False


def _loc_bytes_return(text, lines, tree, item):
    if tree is None:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        byte_names = set()
        for inner in ast.walk(node):
            if isinstance(inner, ast.Assign) and inner.value is not None and _is_bytes(inner.value):
                for target in inner.targets:
                    if isinstance(target, ast.Name):
                        byte_names.add(target.id)
        returns = [inner for inner in ast.walk(node)
                   if isinstance(inner, ast.Return) and inner.value is not None]
        bytes_returns = [inner for inner in returns if _is_bytes(inner.value, byte_names)]
        number_returns = [inner for inner in returns
                          if isinstance(inner.value, ast.Constant)
                          and isinstance(inner.value.value, (int, float, complex))
                          and not isinstance(inner.value.value, bool)]
        if not bytes_returns or not number_returns:
            continue
        number_returns.sort(key=lambda inner: (inner.lineno, inner.col_offset))
        chosen = number_returns[0]
        value = chosen.value.value
        indent = ' ' * chosen.col_offset
        cause = ('`%s` returns `bytes` on one path and the number `%s` on another; one function has '
                 'one return type.' % (node.name, value))
        return _fix(chosen.lineno, chosen.end_lineno, indent + 'return b"%s"' % value,
                    line=chosen.lineno, col=chosen.col_offset + 1, cause=cause, force_position=True)
    return None


def _loc_while_else(text, lines, tree, item):
    if tree is None:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.While) or not node.orelse:
            continue
        if any(isinstance(inner, ast.Break) for inner in ast.walk(node)):
            continue
        end_body = node.body[-1].end_lineno if node.body else node.lineno
        base = _indent(lines[node.lineno - 1]) if node.lineno <= len(lines) else 0
        block = list(lines[node.lineno - 1:end_body])
        dedented = []
        for line in lines[node.orelse[0].lineno - 1:node.orelse[-1].end_lineno]:
            if line.startswith(' ' * (base + 4)):
                dedented.append(line[base + 4:])
            elif line.strip():
                dedented.append(line.lstrip())
            else:
                dedented.append(line)
        return _fix(node.lineno, node.orelse[-1].end_lineno, '\n'.join(block + dedented),
                    line=node.lineno, col=node.col_offset + 1)
    return None


def _nested_annotation(node):
    if not isinstance(node, ast.Subscript):
        return False
    return any(isinstance(inner, ast.Subscript) for inner in ast.walk(node.slice))


def _loc_nested_annotation(text, lines, tree, item):
    if tree is None:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = (list(node.args.args) + list(node.args.posonlyargs)
                         + list(node.args.kwonlyargs))
            for argument in arguments:
                if _nested_annotation(argument.annotation):
                    return dict(line=node.lineno, col=node.col_offset + 1, fix=None, cause=None,
                                force_position=True)
        if isinstance(node, ast.AnnAssign) and _nested_annotation(node.annotation):
            return dict(line=node.lineno, col=node.col_offset + 1, fix=None, cause=None,
                        force_position=True)
    return None


def _loc_fraction(text, lines, tree, item):
    if tree is None:
        return None
    imports = [node for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom) and node.module == 'fractions']
    if not imports:
        return None
    import_line = imports[0].lineno
    calls = sorted((node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'float' and len(node.args) == 1),
                   key=lambda node: (node.lineno, node.col_offset))
    if not calls:
        return dict(line=import_line, col=1, fix=None, cause=None, force_position=True)
    call = calls[0]
    fallback = dict(line=call.lineno, col=call.col_offset + 1, fix=None, cause=None,
                    force_position=True, no_fallback=True)
    argument = call.args[0]
    if not isinstance(argument, ast.Name):
        return fallback
    # The edit removes the `fractions` import and the `Fraction(...)` assignment, so both must be
    # plain top-level lines and nothing else may use them.
    if (len(imports) != 1 or imports[0].end_lineno != imports[0].lineno
            or imports[0].col_offset != 0):
        return fallback
    assignment = None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and node.col_offset == 0
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                and node.value.func.id == 'Fraction'
                and any(isinstance(target, ast.Name) and target.id == argument.id
                        for target in node.targets)):
            assignment = node
            break
    if assignment is None or assignment.lineno <= import_line:
        return fallback
    statement = _statement(call, _parents(tree))
    if (statement is None or statement not in tree.body or tree.body[-1] is not statement
            or statement.col_offset != 0 or call.lineno != statement.lineno
            or call.end_lineno != statement.end_lineno):
        # the value came through an argument, or code after the call still needs `Fraction`:
        # name the call site but publish no edit that could break the build or change output
        return fallback
    names = {alias.asname or alias.name for alias in imports[0].names}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == argument.id and node is not argument:
            if not (isinstance(node.ctx, ast.Store) and node.lineno == assignment.lineno):
                return fallback
        elif isinstance(node, ast.Name) and node.id in names:
            if not (node is assignment.value.func):
                return fallback
    arguments = list(assignment.value.args)
    if not arguments or len(arguments) > 2:
        return fallback
    for value in arguments:
        if not (isinstance(value, ast.Constant) and isinstance(value.value, int)
                and not isinstance(value.value, bool)):
            return fallback
    texts = [_segment(text, value) for value in arguments]
    if not all(texts):
        return fallback
    expression = '%s / %s' % (texts[0], texts[1]) if len(texts) == 2 else 'float(%s)' % texts[0]
    edits = {call.lineno: [(call.col_offset, call.end_col_offset, expression)]}
    block = _apply(lines, import_line, statement.end_lineno, edits)
    # `with` replaces the whole range, so every line the user wrote between the import and the call
    # must appear in it; the import and the assignment are the two lines the edit removes.
    dropped = {import_line, assignment.lineno}
    kept = [line for number, line in enumerate(block.split('\n'), import_line)
            if number not in dropped]
    cause = ('`float(...)` needs `Fraction.__float__`, which this compiler does not build; importing '
             '`fractions` prints this note, and the old position was inside the standard-library '
             'prelude rather than your file.')
    return _fix(import_line, statement.end_lineno, '\n'.join(kept), line=call.lineno,
                col=call.col_offset + 1, cause=cause, force_position=True)


def _references(node, names):
    return any(isinstance(inner, ast.Name) and inner.id in names for inner in ast.walk(node))


def _decimal_names(tree):
    """Names bound to a `Decimal(...)` value, directly or through arithmetic on one."""
    roots = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == 'Decimal'):
            roots.update(target.id for target in node.targets if isinstance(target, ast.Name))
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None \
                    and _references(node.value, roots):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id not in roots:
                        roots.add(target.id)
                        changed = True
    return roots


def _loc_decimal(text, lines, tree, item):
    if tree is None:
        return None
    imports = [node for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom) and node.module == 'decimal']
    if not imports:
        return None
    parent = _parents(tree)
    roots = _decimal_names(tree)
    first_value = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.FormattedValue):
            continue
        if node.format_spec is None or not isinstance(node.value, ast.Name):
            continue
        if first_value is None:
            first_value = node.value
        if node.value.id not in roots:
            continue
        statement = _statement(node, parent)
        if statement is None or node.value.lineno != node.value.end_lineno:
            continue
        edits = {node.value.lineno: [
            (node.value.col_offset, node.value.col_offset, 'float('),
            (node.value.end_col_offset, node.value.end_col_offset, ')')]}
        with_text = _apply(lines, statement.lineno, statement.end_lineno, edits)
        cause = ('a format spec on a `Decimal` needs `Decimal.__format__`; this compiler applies '
                 'format specs to int, float and str only. The old position was inside the `decimal` '
                 'prelude rather than your file.')
        return _fix(statement.lineno, statement.end_lineno, with_text, line=node.value.lineno,
                    col=node.value.col_offset + 1, cause=cause, force_position=True)
    if first_value is not None:
        # a format spec in a program that imported `decimal`, but this value is not Decimal-derived
        return dict(line=first_value.lineno, col=first_value.col_offset + 1, fix=None, cause=None,
                    force_position=True)
    return None


def _loc_yield(text, lines, tree, item):
    if tree is None:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yields = [inner for inner in ast.walk(node) if isinstance(inner, ast.Yield)]
        if not yields:
            continue
        body = [statement for statement in node.body
                if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
                        and isinstance(statement.value.value, str))]
        chosen = yields[0]
        if (len(body) == 1 and isinstance(body[0], ast.For) and len(body[0].body) == 1
                and isinstance(body[0].body[0], ast.Expr)
                and isinstance(body[0].body[0].value, ast.Yield)
                and isinstance(body[0].target, ast.Name)):
            loop = body[0]
            annotation = _segment(text, node.returns) if node.returns is not None else None
            if annotation and annotation.startswith('list[') and annotation.endswith(']'):
                element = annotation[5:-1]
            elif isinstance(loop.iter, ast.Call) and isinstance(loop.iter.func, ast.Name) \
                    and loop.iter.func.id == 'range':
                element = 'int'
            else:
                # the element type cannot be named from this source: no edit that must build
                return dict(line=chosen.lineno, col=chosen.col_offset + 1, fix=None, cause=None,
                            force_position=True)
            body_indent = ' ' * (node.col_offset + 4)
            yielded = _segment(text, loop.body[0].value.value) or 'x'
            iterator = _segment(text, loop.iter) or 'values'
            signature = lines[node.lineno - 1]
            colon = signature.rfind(':')
            if colon < 0:
                continue
            signature = signature[:colon] + ' -> list[%s]' % element + signature[colon:]
            with_text = '\n'.join((
                signature,
                body_indent + 'out: list[%s] = []' % element,
                body_indent + 'for %s in %s:' % (loop.target.id, iterator),
                body_indent + '    out.append(%s)' % yielded,
                body_indent + 'return out'))
            return _fix(node.lineno, node.end_lineno, with_text, line=chosen.lineno,
                        col=chosen.col_offset + 1, force_position=True)
    return None


def _loc_tuple(text, lines, tree, item):
    if tree is None:
        return None
    parent = _parents(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.ListComp):
            continue
        comprehension = node.value
        if not isinstance(comprehension.elt, ast.Tuple) or len(comprehension.generators) != 1:
            continue
        generator = comprehension.generators[0]
        if not isinstance(generator.target, ast.Name):
            continue
        function = parent.get(node)
        annotation = None
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and function.returns is not None:
            annotation = _segment(text, function.returns)
        if not (annotation and annotation.startswith('list[') and annotation.endswith(']')):
            # without the declared row type the generated annotation could not build
            return dict(line=node.lineno, col=node.col_offset + 1, fix=None, cause=None,
                        force_position=True)
        element = annotation[5:-1]
        iterator = _segment(text, generator.iter) or 'values'
        element_text = _segment(text, comprehension.elt) or '(a, b)'
        indent = ' ' * node.col_offset
        with_text = '\n'.join((
            indent + 'out: list[%s] = []' % element,
            indent + 'for %s in %s:' % (generator.target.id, iterator),
            indent + '    out.append(%s)' % element_text,
            indent + 'return out'))
        cause = ('this comprehension builds a list of tuples in one expression; this compiler needs '
                 'the list named, then the tuples appended to it.')
        return _fix(node.lineno, node.end_lineno, with_text, line=node.lineno,
                    col=node.col_offset + 1, cause=cause, force_position=True)
    return None


def _loc_list_parameter(text, lines, tree, item):
    if tree is None:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        parameters = {argument.arg for argument in
                      list(node.args.args) + list(node.args.posonlyargs) + list(node.args.kwonlyargs)
                      if isinstance(argument.annotation, ast.Subscript)}
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Assign):
                continue
            for target in inner.targets:
                if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                        and target.value.id in parameters):
                    return dict(line=inner.lineno, col=inner.col_offset + 1, fix=None, cause=None,
                                force_position=True)
    return None


def _loc_container_dict(text, lines, tree, item):
    if tree is None:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Subscript) and isinstance(node.value, (ast.List, ast.Set, ast.Dict)):
                return dict(line=node.lineno, col=node.col_offset + 1, fix=None, cause=None,
                            force_position=True)
    return None


_LOCATORS = {
    'AIL0101': _loc_stdin_buffer,
    'AIL0103': _loc_str_number,
    'AIL0104': _loc_dict_get,
    'AIL0105': _loc_container_dict,
    'AIL0106': _loc_class_comprehension,
    'AIL0107': _loc_bool_number,
    'AIL0108': _loc_bytes_return,
    'AIL0109': _loc_while_else,
    'AIL0110': _loc_nested_annotation,
    'AIL0111': _loc_fraction,
    'AIL0112': _loc_decimal,
    'AIL0113': _loc_yield,
    'AIL0114': _loc_tuple,
    'AIL0115': _loc_list_parameter,
}


#: Families whose edit is a claim about the user's values, not just about the construct: the table's
#: literal block is safe only for the trigger program it was copied from, so a source that parses and
#: that the locator cannot vouch for gets the position and the cause and no edit at all.
_AUTHORITATIVE = frozenset(('AIL0101', 'AIL0103', 'AIL0104', 'AIL0111'))


def _locate(item, source_text, lines):
    """(record or None, whether the source parsed as Python)."""
    if not source_text:
        return None, False
    locate = _LOCATORS.get(item['code'])
    tree = _parse(source_text)
    if locate is None:
        return None, tree is not None
    found = locate(source_text, lines, tree, item)
    if found is None and tree is not None and item['code'] in _AUTHORITATIVE:
        found = dict(fix=None, no_fallback=True)
    return found, tree is not None


# ------------------------------------------------------------------------------ public objects


def diagnostic(message, source_text=None, path=None, line=None, col=None, severity=None):
    """The JSON-ready object for one diagnostic, or None when the message is not in the table.

    `message` is copied byte for byte.  The position and the literal edit come from the user's own
    source; a location that names a prelude is replaced by the construct the note is about.
    """
    text = str(message or '')
    item = family(text)
    if item is None:
        return None
    lines = _lines(source_text) if source_text is not None else []
    found = _position(text)
    if found:
        parsed_path, parsed_line, parsed_col = found
        path = parsed_path if path is None else path
        line = parsed_line if line is None else line
        col = parsed_col if col is None else col

    located, parsed = _locate(item, source_text, lines)
    located = located or {}
    cause = located.get('cause') or item['cause']
    if located.get('line') is not None and (located.get('force_position')
                                            or line is None
                                            or (lines and line > len(lines))):
        line, col = located['line'], located.get('col', 1)

    fix = located.get('fix')
    # The table's literal `replace`/`with` pair is used only when the whole block occurs in the
    # user's source exactly as the design publishes it; a locator that decided no edit is safe sets
    # `no_fallback`, since a range it computed itself could span lines its `with` does not contain.
    if fix is None and source_text is not None and not located.get('no_fallback'):
        where = _find(source_text, item['replace'])
        if where is not None:
            start, end, column = where
            fix = {'replace_range': [start, end], 'with': item['with']}
            if line is None or (lines and line > len(lines)):
                line, col = start, column
    if fix is not None and lines:
        first, last = fix['replace_range']
        if not (1 <= first <= last <= len(lines)):
            fix = None
        elif line is None or line > len(lines):
            line, col = first, _indent(lines[first - 1]) + 1

    if severity is None:
        severity = 'error' if text.startswith('error:') or 'not in the subset:' in text else 'note'
    result = dict(code=item['code'], severity=severity, file=None if path is None else str(path),
                  line=line, col=col, cause=cause, message=text)
    if fix is not None:
        result['fix'] = fix
    return result


def _refusal_position(text, source_text):
    """(line, col) of a refusal that names its construct but carries no location."""
    if not source_text:
        return None, None
    lines = _lines(source_text)
    head = str(text or '').split('\n', 1)[0]
    head = re.sub(r'^not in the subset:\s*', '', head)
    patterns = ((r'^async def\b', r'\basync\s+def\b'),
                (r'^await\b', r'\bawait\b'),
                (r'^yield\b', r'\byield\b'),
                (r'^(?:class|inheritance)', r'^\s*class\s+\w+'),
                (r'^a decorator', r'^\s*@'),
                (r'^(?:lambda|a lambda)', r'\blambda\b'),
                (r'^while.{0,10}else', r'^\s*while\b'),
                (r'^with\b', r'^\s*with\b'),
                (r'^try\b', r'^\s*try\b'),
                (r'^raise\b', r'\braise\b'),
                (r'^global\b', r'\bglobal\b'),
                (r'^nonlocal\b', r'\bnonlocal\b'))
    for refusal, wanted in patterns:
        if re.match(refusal, head):
            compiled = re.compile(wanted)
            for number, line in enumerate(lines, 1):
                if line.lstrip().startswith('#'):
                    continue
                at = compiled.search(line)
                if at:
                    return number, at.start() + 1
    return None, None


def refusal(message, source_text=None, path=None, line=None, col=None):
    """A machine record for any refusal: the family object when there is one, else a generic error.

    A refusal from a construct the table does not catalogue still names a position and a cause so an
    agent never sees an empty `agent_diagnostics` on a failed build."""
    item = family(message)
    if item is not None:
        return diagnostic(message, source_text=source_text, path=path, line=line, col=col,
                          severity='error')
    text = str(message or '')
    found = _position(text)
    if found:
        path = found[0] if path is None else path
        line = found[1] if line is None else line
        col = found[2] if col is None else col
    if line is None or col is None:
        found_line, found_col = _refusal_position(text, source_text)
        line = found_line if line is None else line
        col = found_col if col is None else col
    if (line is None or col is None) and source_text is not None \
            and not str(source_text).strip():
        # an empty file has no construct to name, but the docs promise a position: the file start
        line = 1 if line is None else line
        col = 1 if col is None else col
    head = text.split('\n', 1)[0]
    head = re.sub(r'^[^:]{0,400}:\d+:\d+:\s*', '', head)
    head = re.sub(r'^(?:note|error):\s*', '', head)
    head = re.sub(r'^not in the subset:\s*', '', head)
    cause = head.strip().rstrip('.') + '.' if head.strip() else 'this construct is not in the typed subset.'
    write = re.search(r'write instead:\s*(.+)', text)
    if write:
        cause += ' Write instead: ' + ' '.join(write[1].split()) + '.'
    return dict(code=UNCATALOGUED, severity='error', file=None if path is None else str(path),
                line=line, col=col, cause=cause, message=text)
