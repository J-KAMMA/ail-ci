"""`raise X from Y` and `raise X from None` on both paths (Python surface).

The cause changes nothing a program prints except the traceback of an exception nobody catches, and an
uncaught exception prints `Type: message` here with no traceback at all (DIFFERENCES A4). So
`from Y` is dropped from the text when Y is a name, an attribute of a name, a constant or None:
evaluating it cannot fail or change anything (a handler's name is bound in its handler). A program
that reads `__cause__`, `__context__`, `__suppress_context__` or `__traceback__` keeps the `from`,
and the compilers refuse it by name. A cause of another shape (a call) is kept as well.
"""
import ast

CHAIN_ATTRS = ('__cause__', '__context__', '__suppress_context__', '__traceback__')


def rewrite(source, notes=None):
    if ' from ' not in source or 'raise' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if any(isinstance(n, ast.Attribute) and n.attr in CHAIN_ATTRS for n in ast.walk(tree)):
        return source
    lines = source.split('\n')
    edits = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Raise) and n.cause is not None and n.exc is not None):
            continue
        c = n.cause
        if not (isinstance(c, (ast.Name, ast.Constant))
                or isinstance(c, ast.Attribute) and isinstance(c.value, ast.Name)):
            continue
        if n.exc.end_lineno != c.lineno:
            continue
        line = lines[c.lineno - 1].encode('utf-8')
        start = n.exc.end_col_offset
        # `)` closing a parenthesised exception may sit between the exception and `from`
        gap = line[start:c.col_offset]
        if gap.replace(b')', b' ').strip() != b'from':
            continue
        edits.append((c.lineno - 1, start + gap.rfind(b'from'), c.end_col_offset))
    if not edits:
        return source
    by_line = {}
    for i, a, b in edits:
        by_line.setdefault(i, []).append((a, b))
    for i, spans in by_line.items():
        line = lines[i].encode('utf-8')
        for a, b in sorted(spans, reverse=True):
            line = line[:a].rstrip(b' ') + line[b:]
        lines[i] = line.decode('utf-8')
    return '\n'.join(lines)
