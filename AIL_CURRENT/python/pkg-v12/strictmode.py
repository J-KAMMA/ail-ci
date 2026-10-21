"""All the typed-path blockers of one program, found in one pass (`ail build --strict`).

The typed path stops at the first construct it refuses. This module keeps going: it compiles the
program, takes the refusal, records it, neutralises the statement (or the function) that caused it and
compiles again, until the program builds or nothing more can be taken out. The result is one record
per blocker -- where it is, what the construct is, why it is not typed, a concrete rewrite -- ranked by
how much code each one keeps off the typed path (the function it sits in plus every function that calls
it, directly or not).

Nothing here changes what the compiler emits: it only reads refusals. A refusal that is only the
consequence of an earlier one (a name the neutralised statement would have bound, a call to a
neutralised function) is dropped instead of reported.
"""
import ast
import os
import re
import sys
import time

SCHEMA = 'ail.strict/1'
MAX_BLOCKERS = 40
BUDGET_SECONDS = 120.0

_PREFIX = 'not in the subset: '
_HINT = re.compile(r'\n?\s*(?:write instead|rewrite|Rewrite)\s*:\s*', re.I)

# (pattern on the first line of the refusal, rewrite) for refusals that carry no hint of their own.
_REWRITES = (
    (r'\bdict of containers\b|dict of lists|dict of sets',
     'keep the groups in a list of structs and map each key to its index with a dict[str, int]: '
     '`idx[k] = len(groups); groups.append(G([]))`, then `groups[idx[k]].items.append(v)`'),
    (r'\|\s*None|Optional|can be None',
     'return a sentinel (-1 or "") and compare with it, or raise when there is no value; `Node | None` '
     'is built for a class type'),
    (r'\bgenerator|\byield\b',
     'build a list in a loop (`out: list[int] = []`, `out.append(x)`) and return or iterate it'),
    (r'\bclosure|nested function|nonlocal|lambda',
     'move the inner function to module level and pass what it reads as parameters'),
    (r'\bdecorator',
     'drop the decorator and call the wrapped function directly'),
    (r'\binheritance|\bsubclass|multiple bases',
     'use one class per concrete type and share code through a module-level function that takes it'),
    (r'\bglobal\b',
     'pass the value in as a parameter and return the new value instead of assigning a global'),
    (r'\bimport\b',
     'drop the import and write what you need by hand, or use a module the typed path builds '
     '(see AIL_REFERENCE_MORE.md)'),
    (r'\bstar|\*args|\*\*kwargs|keyword-only|positional arguments',
     'give the function plain positional parameters, each with a type annotation'),
    (r'\bannotat',
     'annotate it with a builtin type: int, float, str, bytes, bool, list[int], list[float], list[str], '
     'dict[str, int] or a class defined in the program'),
    (r'\bset literal|\bset\b',
     'use `s = set()` and `s.add(x)` in a loop'),
    (r'\bdict literal|\bdict\b',
     'use `d = {}` and `d[k] = v` in a loop with annotated key and value types'),
    (r'\bcomprehension',
     'write the loop out: `out: list[int] = []`, `for x in xs:`, `out.append(...)`'),
    (r'\btry\b|\bexcept\b|\braise\b|\bexception',
     'raise and catch built-in exception classes (ValueError, KeyError, ...) in a plain try/except'),
    (r'\bstr\b.*\bmethod\b|\bstr\.\w+',
     'use a str method the typed path builds (split, strip, find, replace, join, startswith, ...)'),
)
GENERIC_REWRITE = ('split the statement into simple named steps with annotated types, using only '
                   'constructs listed in AIL_REFERENCE.md')


def enabled(environ):
    """True when AIL_STRICT asks for strict mode."""
    return str(environ.get('AIL_STRICT', '')).strip().lower() not in ('', '0', 'off', 'no', 'false')


def split_message(message, statement=None, kind=None):
    """(construct, reason, write_instead) from a refusal text; write_instead is None when it has none."""
    text = str(message or '').strip()
    first, _, rest = text.partition('\n')
    if first.startswith(_PREFIX):
        first = first[len(_PREFIX):]
    body = first + ('\n' + rest if rest else '')
    found = _HINT.search(body)
    hint = None
    if found:
        hint = body[found.end():].strip().split('\n')[0].strip()
        body = body[:found.start()].strip()
    else:
        inline = re.search(r'(?:[;.]|\s--)\s+(?:Rewrite|write|build|use|keep|return|pass|move|call|for|join)\b[^\n]*',
                           body, re.I)
        if inline and inline.start() > 12:
            hint = re.sub(r'^(?:[;.]|\s--)\s*', '', inline.group(0)).strip()
            body = body[:inline.start()].strip()
    if hint:
        hint = re.sub(r'\s*Original refusal:.*$', '', hint, flags=re.S).strip() or None
    body = ' '.join(re.sub(r'\s*Original refusal:.*$', '', body, flags=re.S).split())
    construct = None
    code = re.match(r'`([^`]+)`', body)
    head, colon, tail = body.partition(': ')
    if code:
        construct = code.group(1)
    elif colon and len(head) <= 60:
        construct = head
        body = tail.strip() or body
    else:
        cut = re.split(r'; | -- |\. | \(|, ', body, maxsplit=1)[0]
        if len(cut) <= 70:
            construct = cut
    if not construct:
        construct = ('%s `%s`' % (kind, statement) if kind and statement else (statement or body[:60]))
    return construct.strip(), body.strip(), hint


def rewrite_for(message, hint):
    if hint:
        return hint
    first = str(message).split('\n', 1)[0]
    for pattern, text in _REWRITES:
        if re.search(pattern, first, re.I):
            return text
    return GENERIC_REWRITE


# ---------------------------------------------------------------- source surgery

def _statements(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.stmt)]


def _neutralise_statement(lines, node):
    """Replace the statement's lines by `pass` (same line numbers, same indentation)."""
    first, last = node.lineno - 1, (node.end_lineno or node.lineno) - 1
    indent = ' ' * node.col_offset
    lines[first] = indent + 'pass'
    for number in range(first + 1, last + 1):
        lines[number] = ''


def _neutralise_function(lines, node):
    """Remove a function (decorators included): its lines become blank."""
    first = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
    for number in range(first, (node.end_lineno or node.lineno)):
        lines[number] = ''


def _assigned_names(node):
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
            names.add(sub.id)
        elif isinstance(sub, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            names.add(sub.name)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            for alias in sub.names:
                names.add((alias.asname or alias.name).split('.')[0])
    return names


def _is_consequence(message, gone):
    """The refusal only mentions a name the neutralised code would have defined."""
    quoted = set(re.findall(r"'([A-Za-z_]\w*)'|`([A-Za-z_]\w*)[`(]|\b([A-Za-z_]\w*)\(\)", message))
    mentioned = {part for group in quoted for part in group if part}
    return bool(mentioned & gone)


_SIMPLE = (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr, ast.Return, ast.Raise, ast.Assert, ast.Delete,
           ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)
_WORDS = ('None', 'lambda', 'yield', 'global', 'nonlocal', 'import', 'del', 'await', 'async', 'with', 'try',
          'raise', 'assert', 'print', 'input', 'open', 'sorted', 'sum', 'min', 'max')


def _locate(current, tree, message, to_c, unsupported, library, external, budget, tries=14):
    """The simple statement of `current` whose removal changes `message` (a refusal that names no
    position), or None. Candidates are the statements that contain a word the message quotes."""
    first = message.split('\n', 1)[0]
    tokens = set()
    for quoted in re.findall(r"`([^`]+)`|'([^']+)'", first):
        for part in quoted:
            tokens |= {w for w in re.findall(r'[A-Za-z_]\w*', part) if len(w) > 1}
    tokens |= {w for w in _WORDS if re.search(r'\b%s\b' % w, first)}
    if not tokens:
        return None
    lines = current.split('\n')
    scored = []
    for node in _statements(tree):
        if not isinstance(node, _SIMPLE):
            continue
        text = '\n'.join(lines[node.lineno - 1:node.end_lineno or node.lineno])
        hits = sum(1 for w in tokens if re.search(r'\b%s\b' % re.escape(w), text))
        if hits:
            scored.append((-hits, node.lineno, node))
    scored.sort(key=lambda row: (row[0], row[1]))
    started = time.monotonic()
    for _, _, node in scored[:tries]:
        if time.monotonic() - started > budget:
            break
        trial = list(lines)
        _neutralise_statement(trial, node)
        try:
            to_c('\n'.join(trial), strict=True, info={'_want_units': True, '_checked_arrays': True},
                 library=library, external=external)
        except unsupported as again:
            text = again.args[0] if again.args and isinstance(again.args[0], str) else str(again)
            if text.split('\n', 1)[0] == first:
                continue
        except Exception:
            continue
        return node
    return None


# ---------------------------------------------------------------- call graph weight

def _function_table(tree):
    table = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    table[node.name + '.' + item.name] = item
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            table.setdefault(node.name, node)
    return table


def _callees(node):
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Name):
                names.add(sub.func.id)
            elif isinstance(sub.func, ast.Attribute):
                names.add(sub.func.attr)
    return names


def _blocked(tree, function):
    """(lines, names): the function and every function that reaches it through calls."""
    table = _function_table(tree)
    short = {}
    for name, node in table.items():
        short.setdefault(name.split('.')[-1], []).append(name)
    calls = {name: _callees(node) for name, node in table.items()}
    start = function if function in table else None
    if start is None:
        return 0, []
    blocked = {start}
    changed = True
    targets = {start.split('.')[-1], start}
    if start.endswith('.__init__'):
        targets.add(start.split('.')[0])          # a constructor call `Node(...)` reaches __init__
    while changed:
        changed = False
        for name, callees in calls.items():
            if name not in blocked and callees & targets:
                blocked.add(name)
                targets |= {name.split('.')[-1], name}
                if name.endswith('.__init__'):
                    targets.add(name.split('.')[0])
                changed = True
    lines = sum((table[name].end_lineno or table[name].lineno) - table[name].lineno + 1 for name in blocked)
    module_calls = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef, ast.Import, ast.ImportFrom)):
            if _callees(node) & targets:
                module_calls += (node.end_lineno or node.lineno) - node.lineno + 1
    order = sorted(blocked, key=lambda name: table[name].lineno)
    return lines + module_calls, order


# ---------------------------------------------------------------- the collector

def collect(text, to_c, unsupported, *, library=False, external=None, max_blockers=MAX_BLOCKERS,
            budget=BUDGET_SECONDS, reword=None):
    """The blockers of `text`: a list of dicts, ranked, empty when the program builds on the typed path.

    to_c / unsupported are pyfunc.to_c and pyfunc.Unsupported (passed in so this module imports nothing
    from the compiler). Line numbers are those of `text`."""
    started = time.monotonic()
    lead = len(text) - len(text.lstrip('\n'))      # to_c strips the text: keep the numbering of ours
    current = text[lead:]
    original_tree = None
    try:
        original_tree = ast.parse(text.strip())
    except SyntaxError:
        pass
    blockers, gone, removed_functions = [], set(), set()
    stopped = None
    for _ in range(max_blockers * 3):
        if time.monotonic() - started > budget:
            stopped = 'time budget used up'
            break
        try:
            to_c(current, strict=True, info={'_want_units': True, '_checked_arrays': True},
                 library=library, external=external)
            break
        except unsupported as error:
            refusal = error
        except (RecursionError, MemoryError):
            stopped = 'the compiler gave up on a later part of the program'
            break
        message = refusal.args[0] if refusal.args and isinstance(refusal.args[0], str) else str(refusal)
        if reword is not None:
            message = reword(message)
        line = getattr(refusal, 'source_line', None)
        function = getattr(refusal, 'source_function', None)
        if os.environ.get('AIL_STRICT_DEBUG'):
            print('strict-debug: line=%r function=%r %s' % (line, function, message.split('\n', 1)[0][:200]),
                  file=sys.stderr)
        try:
            tree = ast.parse(current)
        except SyntaxError:
            blockers.append(_record(message, None, function, None, lead))
            stopped = 'the program no longer parses after removing a refused construct'
            break
        lines = current.split('\n')
        target = None
        if isinstance(line, int):
            candidates = [node for node in _statements(tree) if node.lineno == line]
            # the innermost statement starting on that line (a `for` header and its body never share one)
            target = candidates[-1] if candidates else None
        table = _function_table(tree)
        owner = None
        if isinstance(target, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = target
            target = None
        if target is None and owner is None and function in table:
            owner = table[function]
        if target is None and owner is None:
            # no position: find the statement whose removal changes the refusal
            target = _locate(current, tree, message, to_c, unsupported, library, external,
                             max(0.0, budget - (time.monotonic() - started)))
        if target is None and owner is None:
            # still unknown: report it once and stop
            blockers.append(_record(message, line, function, None, lead))
            stopped = 'a refusal without a position; fix it and run --strict again for the rest'
            break
        node = target or owner
        consequence = bool(blockers) and (_is_consequence(message, gone)
                                          or isinstance(node, (ast.Import, ast.ImportFrom)))
        if not consequence:
            if len(blockers) >= max_blockers:
                stopped = 'more than %d blockers; fix these and run --strict again' % max_blockers
                break
            blockers.append(_record(message, node.lineno, function or _enclosing(tree, node), node, lead,
                                    snippet=lines[node.lineno - 1]))
        if target is not None:
            gone |= _assigned_names(target)
            owner_name = function or _enclosing(tree, target)
            if owner_name:
                gone.add(owner_name.split('.')[-1])       # its return value is no longer what it was
            _neutralise_statement(lines, target)
        else:
            gone |= {owner.name}
            removed_functions.add(owner.name)
            _neutralise_function(lines, owner)
        current = '\n'.join(lines)
    else:
        stopped = stopped or 'stopped after too many rounds'
    # weights from the program as written
    tree = original_tree
    for blocker in blockers:
        if tree is not None and blocker.get('function'):
            lines_blocked, names = _blocked(tree, blocker['function'])
            blocker['blocks_lines'] = lines_blocked
            blocker['blocks_functions'] = names
        else:
            blocker['blocks_lines'] = blocker.pop('_span', 1)
            blocker['blocks_functions'] = []
        blocker.pop('_span', None)
    blockers.sort(key=lambda b: (-b['blocks_lines'], b['line'] if b['line'] is not None else 10 ** 9))
    for rank, blocker in enumerate(blockers, 1):
        blocker['rank'] = rank
    return blockers, stopped


def _enclosing(tree, node):
    best = None
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.lineno <= node.lineno <= (fn.end_lineno or fn.lineno):
            if best is None or fn.lineno >= best.lineno:
                best = fn
    return best.name if best is not None else None


_KINDS = ((ast.Return, 'return'), (ast.For, 'for loop'), (ast.While, 'while loop'), (ast.If, 'if'),
          (ast.Assign, 'assignment'), (ast.AugAssign, 'assignment'), (ast.AnnAssign, 'assignment'),
          (ast.Expr, 'call'), (ast.FunctionDef, 'def'), (ast.ClassDef, 'class'), (ast.Try, 'try'),
          (ast.With, 'with'), (ast.Import, 'import'), (ast.ImportFrom, 'import'), (ast.Raise, 'raise'))


def _record(message, line, function, node, lead, snippet=None):
    kind = next((name for cls, name in _KINDS if isinstance(node, cls)), None)
    construct, reason, hint = split_message(message, ' '.join(snippet.split())[:80] if snippet else None, kind)
    record = {
        'line': (line + lead) if isinstance(line, int) else None,
        'column': (node.col_offset + 1) if node is not None else None,
        'function': function,
        'statement': ' '.join(snippet.split())[:140] if snippet else None,
        'construct': construct,
        'why': reason,
        'write_instead': rewrite_for(message, hint),
        'message': str(message).strip(),
    }
    if node is not None:
        record['_span'] = (node.end_lineno or node.lineno) - node.lineno + 1
    return record
