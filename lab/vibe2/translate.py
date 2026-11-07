#!/usr/bin/env python3
"""Translate AIL-N (lab/vibe2/NEW_SURFACE.md) to the AIL Python surface.

Line oriented and mechanical: `fn`, `let`/`var`, `match`/`case` become `def`, annotated
assignments and `if`/`elif`/`else`; the AIL-N builtins become plain Python calls; `Ok(x)`/`Err(e)`
become `(True, x)`/`(False, e)`. `translate(source)` returns `{'code', 'line_map'}` where
`line_map[i]` is the 1-based AIL-N line that produced output line i+1 (0 for the prelude), so a
message about the generated Python can be shown with the AI's line. A construct outside the
surface raises `TranslateError(line, message)`.
"""
import ast
import re

PRELUDE = '''\
import sys
import math

def __div_ceil(a: int, b: int) -> int:
    return -((-a) // b)

def __sqrt(x: float) -> float:
    return math.sqrt(x)

def __floor(x: float) -> int:
    return math.floor(x)

def __ceil(x: float) -> int:
    return math.ceil(x)

'''.splitlines()

class TranslateError(Exception):
    def __init__(self, line, message):
        super().__init__('line %d: %s' % (line, message))
        self.line, self.message = line, message

FORBIDDEN = re.compile(r'\b(print|open|input|eval|exec|getattr|setattr|type|compile|globals|'
                       r'locals|vars|__import__)\s*\(')
NO_VALUE = re.compile(r'\b(None|Optional|Any|Union)\b|\blambda\b')
LITERAL = re.compile(r'^(-?\d+(?:\.\d+)?|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|True|False)$')

def _split_strings(text):
    """(chunk, is_string) pairs; string literals are never rewritten."""
    parts, buf, i = [], [], 0
    while i < len(text):
        if text[i] in '"\'':
            if buf:
                parts.append((''.join(buf), False))
                buf = []
            j = _skip_string(text, i)
            parts.append((text[i:j], True))
            i = j
        else:
            buf.append(text[i])
            i += 1
    if buf:
        parts.append((''.join(buf), False))
    return parts

def _skip_string(text, i):
    q, j = text[i], i + 1
    while j < len(text):
        if text[j] == '\\':
            j += 2
            continue
        if text[j] == q:
            return j + 1
        j += 1
    raise TranslateError(0, 'unclosed string literal')

FSTRING_PREFIX = ('f', 'rf', 'fr')

def _has_fstring(text):
    """True when a string literal carries an f prefix (`f`, `rf` or `fr`, any case)."""
    i = 0
    while i < len(text):
        if text[i] in '"\'':
            k = i
            while k > 0 and text[k - 1].isalpha():
                k -= 1
            if text[k:i].lower() in FSTRING_PREFIX:
                return True
            i = _skip_string(text, i)
        else:
            i += 1
    return False

def _literal_key(pattern):
    """A canonical key for a match literal, so `0`/`-0`, `0`/`0.0`, `True`/`1` and `"a"`/`'a'`
    collide: a bool is an int, and Python compares an int and a float by value."""
    try:
        value = ast.literal_eval(pattern)
    except (ValueError, SyntaxError):
        return ('source', pattern)
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (int, float)):
        return ('number', value)
    return ('literal', repr(value))

def _split_args(text):
    """Split call arguments at top-level commas, ignoring strings and brackets."""
    args, depth, cur, i = [], 0, [], 0
    while i < len(text):
        ch = text[i]
        if ch in '"\'':
            j = _skip_string(text, i)
            cur.append(text[i:j])
            i = j
            continue
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        if ch == ',' and depth == 0:
            args.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    if ''.join(cur).strip():
        args.append(''.join(cur).strip())
    return args

def _match_paren(text, k):
    depth, i = 0, k
    while i < len(text):
        if text[i] in '"\'':
            i = _skip_string(text, i)
            continue
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1

def _one(args):
    if len(args) != 1:
        raise ValueError
    return args[0]

def _bad(_args):
    raise ValueError

CALL_MAP = {
    'Ok': lambda a: '(True, %s)' % _one(a),
    'Err': lambda a: '(False, %s)' % _one(a),
    'write_bytes': lambda a: 'sys.stdout.buffer.write(%s)' % _one(a),
    'write': lambda a: 'sys.stdout.write(%s)' % _one(a),
    'read_stdin_bytes': lambda a: 'sys.stdin.buffer.read(%s)' % ''.join(a),
    'read_stdin': lambda a: 'sys.stdin.read(%s)' % ''.join(a),
    'read_line': lambda a: 'sys.stdin.readline(%s)' % ''.join(a),
    'exit': lambda a: 'sys.exit(%s)' % _one(a),
    'arg_count': lambda a: '(len(sys.argv) - 1)' if not a else _bad(a),
    'arg': lambda a: 'sys.argv[1 + (%s)]' % _one(a),
    'read_file_bytes': lambda a: 'open(%s, "rb").read()' % _one(a),
    'read_file_text': lambda a: 'open(%s, "r").read()' % _one(a),
    'div_ceil': lambda a: '__div_ceil(%s)' % ', '.join(a),
    'sqrt': lambda a: '__sqrt(%s)' % _one(a),
    'floor': lambda a: '__floor(%s)' % _one(a),
    'ceil': lambda a: '__ceil(%s)' % _one(a),
}

def _rewrite_calls(text, line):
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch in '"\'':
            j = _skip_string(text, i)
            out.append(text[i:j])
            i = j
        elif ch.isalpha() or ch == '_':
            j = i
            while j < len(text) and (text[j].isalnum() or text[j] == '_'):
                j += 1
            name, k = text[i:j], j
            while k < len(text) and text[k] == ' ':
                k += 1
            if name in CALL_MAP and k < len(text) and text[k] == '(' and \
                    not (i and (text[i - 1].isalnum() or text[i - 1] in '_.')):
                m = _match_paren(text, k)
                if m < 0:
                    raise TranslateError(line, 'unclosed call to %s' % name)
                args = [_rewrite_calls(a, line) for a in _split_args(text[k + 1:m])]
                try:
                    out.append(CALL_MAP[name](args))
                except (ValueError, IndexError):
                    raise TranslateError(line, 'wrong number of arguments to %s' % name)
                i = m + 1
            else:
                out.append(text[i:j])
                i = j
        else:
            out.append(ch)
            i += 1
    return ''.join(out)

def rewrite_expr(text, line):
    if _has_fstring(text):
        raise TranslateError(line, 'not in the surface: f-strings; use str() and +')
    plain = ''.join(c if not s else ' ' for c, s in _split_strings(text))
    for pat, what in ((FORBIDDEN, '%s(...); use the operations in NEW_SURFACE.md'),
                      (NO_VALUE, '%s; use a typed value, Result, or a sentinel')):
        mm = pat.search(plain)
        if mm:
            raise TranslateError(line, 'not in the surface: ' + what % mm.group(1))
    if ':=' in plain:
        raise TranslateError(line, 'not in the surface: `:=`; write a `let`/`var` binding')
    if re.search(r'\bfor\b', plain):
        raise TranslateError(line, 'not in the surface: comprehension or generator expression; '
                             'write an explicit `for` loop')
    if '?' in plain:
        raise TranslateError(line, 'not in the surface: `?`; match the Result explicitly')
    return _rewrite_calls(text, line)

def expand_result(text, line):
    """Result[T] -> tuple[bool, T], recursively and bracket aware."""
    out, i = [], 0
    while True:
        k = text.find('Result', i)
        if k < 0:
            out.append(text[i:])
            return ''.join(out)
        if (k and (text[k - 1].isalnum() or text[k - 1] == '_')) or \
                (k + 6 < len(text) and (text[k + 6].isalnum() or text[k + 6] == '_')):
            out.append(text[i:k + 6])
            i = k + 6
            continue
        out.append(text[i:k])
        j = k + 6
        while j < len(text) and text[j] in ' \t':
            j += 1
        if j >= len(text) or text[j] != '[':
            raise TranslateError(line, 'Result needs a type parameter: Result[T]')
        depth, m = 0, j
        while m < len(text):
            if text[m] == '[':
                depth += 1
            elif text[m] == ']':
                depth -= 1
                if depth == 0:
                    break
            m += 1
        if m >= len(text):
            raise TranslateError(line, 'unclosed Result[...]')
        out.append('tuple[bool, %s]' % expand_result(text[j + 1:m], line))
        i = m + 1

def rewrite_type(text, line):
    mm = NO_VALUE.search(text)
    if mm:
        raise TranslateError(line, 'not in the surface: %s' % mm.group(0))
    text = expand_result(text, line)
    if '?' in text:
        raise TranslateError(line, 'not in the surface: Optional `?`; use Result[T]')
    return text

def _split_params(params, line):
    out, depth, cur = [], 0, []
    for ch in params:
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    if ''.join(cur).strip():
        out.append(''.join(cur))
    res, names = [], []
    for p in out:
        p = p.strip()
        if not p:
            continue
        if ':' not in p:
            raise TranslateError(line, 'every parameter needs a type: %r' % p)
        name, typ = p.split(':', 1)
        names.append(name.strip())
        res.append('%s: %s' % (name.strip(), rewrite_type(typ.strip(), line)))
    return ', '.join(res), names

def translate(source):
    src_lines = source.splitlines()
    out = [(text, 0) for text in PRELUDE]
    contexts, counter = [], [0]
    top = {'declared': set(), 'immutable': set()}
    active = [top]

    def lookup(name):
        for frame in reversed(active):
            if name in frame['declared']:
                return frame
        return None

    def close_match(ctx):
        if ctx.get('closed') or (ctx.get('has_ok') and ctx.get('has_err')):
            return
        raise TranslateError(ctx['line'], 'match is not exhaustive; add a final `case _:` arm '
                             '(or one Ok and one Err arm for a Result)')

    def emit(text, ai_line, at=None):
        for piece in text.split('\n'):
            out.append((' ' * at + piece if at is not None else piece, ai_line))

    for no, raw in enumerate(src_lines, 1):
        if '\t' in raw:
            raise TranslateError(no, 'indent with two spaces per level, not tabs')
        stripped = raw.strip()
        if not stripped or stripped.startswith('#'):
            out.append((raw, no))
            continue
        indent = len(raw) - len(raw.lstrip(' '))
        if indent % 2:
            raise TranslateError(no, 'indent must be a multiple of two spaces')
        pad = ' ' * indent
        while contexts and indent <= contexts[-1]['base']:
            close_match(contexts.pop())
        if indent == 0:
            del active[1:]          # a top-level statement ends any function scope

        m = re.match(r'^match\s+(.+?):$', stripped)
        if m:
            counter[0] += 1
            ctx = {'base': indent, 'temp': '__m%d' % counter[0], 'first': True, 'case': None,
                   'closed': False, 'line': no, 'arms': set(), 'has_ok': False, 'has_err': False}
            emit('%sif True:\n%s  %s = %s' % (pad, pad, ctx['temp'], rewrite_expr(m.group(1), no)), no)
            contexts.append(ctx)
            continue

        m = re.match(r'^case\s+(.+?):$', stripped)
        if m:
            if not contexts:
                raise TranslateError(no, 'case outside a match')
            ctx = contexts[-1]
            if ctx.get('closed'):
                raise TranslateError(no, 'case after `case _`; `_` must be the last arm')
            if indent != ctx['base'] + 2:
                raise TranslateError(no, 'case must be indented two spaces under match')
            pat, bind, kw = m.group(1).strip(), None, 'if' if ctx['first'] else 'elif'
            if pat == '_':
                key = ('default',)
            elif LITERAL.match(pat):
                key = ('literal', _literal_key(pat))
            else:
                cm = re.match(r'^(Ok|Err)\(\s*([A-Za-z_]\w*)\s*\)$', pat)
                if not cm:
                    raise TranslateError(no, 'unsupported match pattern %r; use a literal, Ok(v), '
                                         'Err(e) or _' % pat)
                key = ('ok' if cm.group(1) == 'Ok' else 'err',)
            if key in ctx['arms']:
                raise TranslateError(no, 'duplicate case arm %r; each pattern may appear once' % pat)
            ctx['arms'].add(key)
            if pat == '_':
                if ctx['first']:
                    raise TranslateError(no, 'case _ must be last')
                emit(pad + 'else:', no)
                ctx['closed'] = True
            elif LITERAL.match(pat):
                emit('%s%s %s == %s:' % (pad, kw, ctx['temp'], pat), no)
                ctx['first'] = False
            else:
                val = 'True' if cm.group(1) == 'Ok' else 'False'
                if val == 'True':
                    ctx['has_ok'] = True
                else:
                    ctx['has_err'] = True
                emit('%s%s %s[0] == %s:' % (pad, kw, ctx['temp'], val), no)
                ctx['first'] = False
                bind = cm.group(2)
            if bind:
                emit('%s = %s[1]' % (bind, ctx['temp']), no, at=indent + 2)
            continue

        m = re.match(r'^fn\s+([A-Za-z_]\w*)\s*\((.*)\)\s*->\s*(.+?):$', stripped)
        if m:
            if indent != 0:
                raise TranslateError(no, 'not in the surface: nested function; define it at top level')
            params, names = _split_params(m.group(2), no)
            active.append({'declared': set(names), 'immutable': set()})
            emit('%sdef %s(%s) -> %s:' % (pad, m.group(1), params,
                                          rewrite_type(m.group(3).strip(), no)), no)
            continue
        if re.match(r'^fn\s', stripped):
            raise TranslateError(no, 'fn needs the form `fn name(a: T) -> R:`')

        m = re.match(r'^(let|var)\s+([A-Za-z_]\w*)\s*:\s*(.+?)\s*=\s*(.*)$', stripped)
        if m:
            kind, name, typ, expr = m.groups()
            if not expr.strip():
                raise TranslateError(no, 'a binding needs an initializer')
            emit('%s%s: %s = %s' % (pad, name, rewrite_type(typ.strip(), no),
                                    rewrite_expr(expr, no)), no)
            active[-1]['declared'].add(name)
            if kind == 'let':
                active[-1]['immutable'].add(name)
            continue
        if re.match(r'^(let|var)\b', stripped):
            raise TranslateError(no, 'bindings are written `let name: Type = expr` or '
                                 '`var name: Type = expr`')

        m = re.match(r'^([A-Za-z_]\w*)\s*=\s*(.*)$', stripped)
        if m:
            name = m.group(1)
            frame = lookup(name)
            if frame is None:
                raise TranslateError(no, 'declare the binding first with `let %s: Type = ...` or '
                                     '`var %s: Type = ...`' % (name, name))
            if name in frame['immutable']:
                raise TranslateError(no, '%r is a let binding and cannot be reassigned; declare it '
                                     'with var' % name)
            emit('%s%s = %s' % (pad, name, rewrite_expr(m.group(2), no)), no)
            continue

        m = re.match(r'^for\s+([A-Za-z_]\w*)\s*:\s*(.+?)\s+in\s+(.+):$', stripped)
        if m:
            active[-1]['declared'].add(m.group(1))
            emit('%sfor %s in %s:' % (pad, m.group(1), rewrite_expr(m.group(3), no)), no)
            continue
        if re.match(r'^for\s', stripped):
            raise TranslateError(no, 'write `for name: Type in iterable:` and do not unpack the '
                                 'for target; index the items instead')

        m = re.match(r'^(if|elif|while)\s+(.+):$', stripped)
        if m:
            emit('%s%s %s:' % (pad, m.group(1), rewrite_expr(m.group(2), no)), no)
            continue

        m = re.match(r'^return\s*(.*)$', stripped)
        if m:
            expr = m.group(1).strip()
            emit(pad + ('return ' + rewrite_expr(expr, no) if expr else 'return'), no)
            continue
        if stripped in ('break', 'continue', 'pass'):
            emit(pad + stripped, no)
            continue

        if re.match(r'^(async\s+)?def\b', stripped):
            raise TranslateError(no, 'not in the surface: `def`; write `fn name(a: T) -> R:`')
        if re.match(r'^(import|from|class|try|except|finally|raise|assert|with|global|nonlocal|'
                    r'async|await|yield|del)\b', stripped) or stripped.startswith('@'):
            raise TranslateError(no, 'not in the surface: `%s`' % stripped.split()[0].rstrip(':'))
        if re.search(r'(\+=|-=|\*=|/=|%=|//=|\*\*=)($|\s)', stripped):
            raise TranslateError(no, 'not in the surface: augmented assignment; write `x = x + 1`')
        emit(pad + rewrite_expr(stripped, no), no)          # bare expression / call

    while contexts:
        close_match(contexts.pop())
    code = '\n'.join(text for text, _ in out) + '\n'
    return {'code': code, 'line_map': [ai for _, ai in out]}

def map_line(line_map, py_line):
    """Map a 1-based generated-Python line back to the AIL-N line (0 if unknown)."""
    return line_map[py_line - 1] if 1 <= py_line <= len(line_map) else 0
