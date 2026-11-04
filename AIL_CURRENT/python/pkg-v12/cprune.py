"""Drop the static C a translation unit never uses before gcc parses it.

Both paths paste a fixed runtime ahead of the program (cruntime.SOURCE parts on the typed path,
cruntime.OBJ2 on the general path), and most programs call a small part of it. gcc discards an
unreferenced static function or variable without emitting anything for it, but it still lexes,
parses and type-checks it first: on the general path that is about a fifth of cc1's instructions.

`prune(text)` keeps every top-level item that is not `static` (main, the exported and the linked
symbols), every preprocessor line, every type and every item it cannot classify, then keeps a
static function, prototype or variable only when a kept item names it, transitively. A removed
item is replaced by its own newlines, so every later line keeps its number (#line, gcc's
diagnostics and native_diagnostics' source regions all count lines of this text).

Conservative by construction: a name counts as used wherever it appears outside a comment (string
literals included, so an asm or alias("...") reference keeps its target), an item whose shape is
not recognized is kept whole, a token pasted with ## keeps every candidate that could be built from
it, and a text whose braces or #if blocks do not nest cleanly is returned unchanged.
AIL_NO_PRUNE=1 turns the pass off.
"""
import bisect
import os
import re

# comments, then string and character literals (kept for identifier scanning, blanked for structure)
_LEXEME = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'', re.S)
_DIRECTIVE = re.compile(r'^[ \t]*#(?:[^\n]*\\\n)*[^\n]*', re.M)
_COND = re.compile(r'^[ \t]*#[ \t]*(if|ifdef|ifndef|elif|elifdef|elifndef|else|endif)\b', re.M)
_STRUCT = re.compile(r'[{};]')
_IDENT = re.compile(r'[A-Za-z_]\w*')
_ATTR = re.compile(r'\b(?:__attribute__|__declspec)\s*\(')
# an attribute that makes gcc keep or reach a symbol nothing in the text names. `used` stays one even
# though only this unit can name a static symbol: gcc emits a `used` function, so dropping it would
# change the object code (its callees lose a caller and inline differently)
_PINNED = re.compile(r'\b(?:constructor|destructor|used|section|weak|alias|ifunc|visibility|externally_visible)\b')
_FUNC_HEAD = re.compile(r'^[\w\s\*]*?\b(\w+)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$')
_VAR_HEAD = re.compile(r'^[\w\s\*]*?\b(\w+)\s*(?:\[[^\]]*\]\s*)*(?:=.*)?$', re.S)
_KEYWORDS = frozenset('''auto break case char const continue default do double else enum extern float for goto if
    inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void
    volatile while _Bool _Thread_local __thread __inline __inline__ __restrict __restrict__ __extension__'''.split())


def _spaces(s):
    """`s` as spaces, newlines kept: offsets and line numbers do not move."""
    return '\n'.join(' ' * len(line) for line in s.split('\n'))


def _blank(match):
    return _spaces(match.group(0))


def _blank_strings(match):
    s = match.group(0)
    if s[0] in '"\'':
        return s[0] + ' ' * (len(s) - 2) + s[-1]
    return _spaces(s)


def _attributes(head):
    """The text of each __attribute__((...)) group in `head` (all of `head` when one does not close)."""
    groups = []
    for m in _ATTR.finditer(head):
        depth, i = 1, m.end()
        while i < len(head) and depth:
            depth += {'(': 1, ')': -1}.get(head[i], 0)
            i += 1
        groups.append(head[m.end():i] if not depth else head)
    return groups


def _strip_attributes(head):
    """`head` without its __attribute__((...)) groups, or None when a group does not close."""
    while True:
        m = _ATTR.search(head)
        if not m:
            return head
        depth, i = 1, m.end()
        while i < len(head) and depth:
            depth += {'(': 1, ')': -1}.get(head[i], 0)
            i += 1
        if depth:
            return None
        head = head[:m.start()] + ' ' + head[i:]


def _top_comma(head):
    depth = 0
    for c in head:
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif c == ',' and depth == 0:
            return True
    return False


def _pinned_macros(text):
    """Macros whose expansion pins a symbol (AIL_KEEP -> __attribute__((used)))."""
    names = set()
    for m in re.finditer(r'^[ \t]*#[ \t]*define[ \t]+(\w+)((?:[^\n]*\\\n)*[^\n]*)', text, re.M):
        if _PINNED.search(m.group(2)):
            names.add(m.group(1))
    return names


def _classify(head, pinned=frozenset()):
    """(kind, name) for a static top-level item from its cleaned header, else None (kept)."""
    head = head.strip()
    if pinned and pinned.intersection(_IDENT.findall(head)) or any(_PINNED.search(a) for a in _attributes(head)):
        return None
    head = _strip_attributes(head)
    if head is None:
        return None
    head = head.strip()
    words = _IDENT.findall(head.split('(', 1)[0].split('=', 1)[0].split('[', 1)[0])
    if 'static' not in words or 'typedef' in words or 'volatile' in words:
        return None
    m = _FUNC_HEAD.match(head)
    if m and m.group(1) not in _KEYWORDS:
        return 'func', m.group(1)
    if '(' in head.split('=', 1)[0]:
        return None
    decl = head.split('=', 1)[0]
    if ',' in decl:
        return None
    m = _VAR_HEAD.match(head)
    if m and m.group(1) not in _KEYWORDS and not m.group(1)[0].isdigit():
        return 'var', m.group(1)
    return None


def _conditionals_nest(text):
    """True when every #if in `text` closes in `text` and no #else/#elif sits at its top level."""
    depth = 0
    for m in _COND.finditer(text):
        kind = m.group(1)
        if kind.startswith('if'):
            depth += 1
        elif kind == 'endif':
            depth -= 1
            if depth < 0:
                return False
        elif depth == 0:
            return False
    return depth == 0


def _local_directives(lines):
    """True when the directives inside an item end with it: its #if blocks nest, and every macro it
    #defines it also #undefs (anything else, #line or #include, would change the text after it)."""
    if not _conditionals_nest('\n'.join(lines)):
        return False
    live = set()
    for line in lines:
        if _COND.match(line):
            continue
        m = re.match(r'[ \t]*#[ \t]*(define|undef)[ \t]+(\w+)', line)
        if not m:
            return False
        if m.group(1) == 'define':
            live.add(m.group(2))
        elif m.group(2) in live:
            live.discard(m.group(2))
        else:
            return False
    return not live


# a function-like macro invoked at top level on a line of its own (a definition generator), ahead of
# the function header the scan would otherwise glue it to
_INVOKE = re.compile(r'\s*(\w+)\s*\([^()]*(?:\([^()]*\)[^()]*)*\)[ \t]*\n')


def _items(struct, pinned=frozenset()):
    """Top-level items of the structure text as (start, body_start, end, terminator) spans, or None."""
    items = []
    start, depth, open_at = 0, 0, None
    for m in _STRUCT.finditer(struct):
        c = m.group(0)
        if c == '{':
            if depth == 0:
                open_at = m.start()
            depth += 1
        elif c == '}':
            depth -= 1
            if depth < 0:
                return None
            if depth == 0:
                # a function body ends at its brace; an initializer or a type waits for its ';'
                head = struct[start:open_at].strip()
                is_func = _FUNC_HEAD.match((_strip_attributes(head) or '').strip())
                if not is_func:
                    # `GEN(a, b)\nGEN(c, d)\nstatic T f(...) {`: the invocations are items of their own
                    cut, pos = [], start
                    while True:
                        inv = _INVOKE.match(struct, pos, open_at)
                        if not inv or inv.group(1) in pinned:
                            break
                        cut.append(inv.end())
                        pos = inv.end()
                    if cut and _FUNC_HEAD.match((_strip_attributes(struct[pos:open_at].strip()) or '').strip()):
                        for e in cut:
                            items.append((start, None, e, ')'))
                            start = e
                        is_func = True
                if is_func:
                    items.append((start, open_at, m.end(), '}'))
                    start, open_at = m.end(), None
        elif depth == 0:
            items.append((start, open_at, m.end(), ';'))
            start, open_at = m.end(), None
    if depth:
        return None
    return items


def _pasted(lexed):
    """Fragments glued with ## in the #define lines: (prefixes, suffixes), or None when a paste joins
    only macro parameters (the name it builds appears nowhere whole, so no candidate can be judged)."""
    pre, suf = set(), set()
    for d in _DIRECTIVE.finditer(lexed):
        line = d.group(0)
        if '##' not in line:
            continue
        m = re.match(r'[ \t]*#[ \t]*define[ \t]+\w+(?:\(([^)]*)\))?', line)
        if not m:
            return None
        params = set(re.findall(r'\w+|\.\.\.', m.group(1) or ''))
        params.add('__VA_ARGS__')
        for chain in re.finditer(r'\w+(?:\s*##\s*\w+)+', line):
            parts = re.split(r'\s*##\s*', chain.group(0))
            fixed = [x for x in parts if x not in params]
            if not fixed:
                return None
            # the literal pieces of a pasted name: it starts with the first, ends with the last
            if parts[0] not in params:
                pre.add(parts[0])
            if parts[-1] not in params:
                suf.add(parts[-1])
            if parts[0] in params and parts[-1] in params:
                return None
    return pre, suf


def prune(text):
    if os.environ.get('AIL_NO_PRUNE') or 'static' not in text:
        return text
    comments = []                                   # (start, end) of every comment, in order

    def _comment(m):
        if m.group(0)[0] == '/':
            comments.append(m.span())
            return _blank(m)
        return m.group(0)
    ident = _LEXEME.sub(_comment, text)             # comments as spaces, literals kept
    lexed = _LEXEME.sub(_blank_strings, text)       # comments and literal contents as spaces
    struct = _DIRECTIVE.sub(_blank, lexed)          # ... and the preprocessor lines too
    if re.search(r'^[ \t]*#[ \t]*include[ \t]*"', lexed, re.M):
        return text     # a header this pass cannot read may name anything (AIL_V2_INCLUDE_ABS=1)
    pinned = _pinned_macros(lexed)
    items = _items(struct, pinned)
    if items is None:
        return text
    candidates = {}           # name -> [span index]
    spans = []
    for start, body, end, term in items:
        # a directive line inside the item's own text: keep the item unless its #if blocks nest
        lead = start
        # leading whitespace, comments and top-level directives before the item are not part of it
        last_dir = None
        for d in _DIRECTIVE.finditer(lexed, start, body if body is not None else end):
            if struct[start:d.start()].strip():
                break
            last_dir = d.end()
        if last_dir is not None:
            lead = last_dir
        kind = None
        inner = [d.group(0) for d in _DIRECTIVE.finditer(lexed, lead, end)]
        if term == ')':
            pass        # a macro invocation: what it defines is not visible here
        elif inner and not _local_directives(inner):
            pass        # a #define/#line/... inside the item outlives it; a split #if cannot be cut
        elif term == '}':
            kind = _classify(struct[lead:body], pinned)
            kind = kind if kind and kind[0] == 'func' else None
        elif body is None:
            head = struct[lead:end - 1]
            if not _top_comma(head):
                kind = _classify(head, pinned)
        else:
            # `static T x[] = { ... };` alone: the brace must be the initializer and close the item
            head = struct[lead:body]
            tail = struct[lead:end].rsplit('}', 1)[1]
            if '=' in head and tail.strip() == ';' and not _top_comma(head):
                kind = _classify(head + '0', pinned)
        kind = kind if kind and kind[0] in ('func', 'var') else None
        if kind is None:
            continue
        # the comments ahead of the item go with it, but a cut never starts inside a comment
        # (one opened on the directive line before it, `#define X 1 /* ... \n ... */`)
        k = bisect.bisect_right(comments, (lead, len(text))) - 1
        if k >= 0 and comments[k][0] < lead < comments[k][1]:
            lead = comments[k][1]
        lead_ws = lead
        while lead_ws < end and text[lead_ws] in ' \t\n':
            lead_ws += 1
        candidates.setdefault(kind[1], []).append(len(spans))
        spans.append((lead_ws, end))
    if not spans:
        return text
    # Everything outside the candidates is a root, except a #define's body: it names something only
    # where the macro is expanded, so it counts once the macro's own name is used. The line itself
    # always stays (and so does every #undef), so the preprocessor sees the same text.
    order = sorted(spans)
    starts = [a for a, _ in order]
    macros = {}                                     # macro name -> identifiers its bodies name
    blanks = []
    for d in _DIRECTIVE.finditer(lexed):
        k = bisect.bisect_right(starts, d.start()) - 1
        if k >= 0 and d.start() < order[k][1]:
            continue                                # inside a candidate: goes with it
        m = re.match(r'[ \t]*#[ \t]*(define|undef)[ \t]+(\w+)', d.group(0))
        if m:
            if m.group(1) == 'define':
                macros.setdefault(m.group(2), set()).update(_IDENT.findall(ident, d.start() + m.end(), d.end()))
            blanks.append(d.span())
    roots = []
    pos = 0
    for a, b in sorted(order + blanks):
        roots.append(ident[pos:a])
        pos = max(pos, b)
    roots.append(ident[pos:])
    used = set(_IDENT.findall(' '.join(roots)))
    used.update(n for n in candidates if n in macros)    # `#define f g` then `static int f(...)`: f is g
    pasted = _pasted(lexed)
    if pasted is None:
        return text
    pre, suf = pasted
    if pre or suf:
        for name in candidates:
            if any(name.startswith(p) for p in pre) or any(name.endswith(s) for s in suf):
                used.add(name)
    kept = set()
    seen = set()
    work = [n for n in used if n in candidates or n in macros]
    while work:
        name = work.pop()
        if name in seen:
            continue
        seen.add(name)
        refs = set(macros.get(name, ()))
        if name in candidates:
            kept.add(name)
            for i in candidates[name]:
                refs.update(_IDENT.findall(ident, *spans[i]))
        work.extend(r for r in refs if r not in seen and (r in candidates or r in macros))
    drop = sorted(spans[i] for name, idx in candidates.items() if name not in kept for i in idx)
    if not drop:
        return text
    out, pos = [], 0
    for s, e in drop:
        out.append(text[pos:s])
        out.append('\n' * text.count('\n', s, e))
        pos = e
    out.append(text[pos:])
    return ''.join(out)
