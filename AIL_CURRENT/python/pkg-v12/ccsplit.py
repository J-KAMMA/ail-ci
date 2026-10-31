"""Split the typed program's single C translation unit into several, so gcc compiles them in parallel.

gcc's -O2 time on a generated program grows with the statements left in its user functions, and one
translation unit uses one core. `plan()` takes the pieces `pyfunc._to_c_once` recorded (`info['c_split']`:
the shared declarations, every user function's prototype, every user function's text) and returns
N C sources:

* the runtime and the prototypes (the "declarations") are in every unit;
* every `static` user function (small inlined helpers, methods) is in every unit, so gcc keeps inlining
  it where it is called;
* every other user function is in exactly one unit. A function with a single caller travels with that
  caller (gcc inlines it there), the groups are spread over the units by size, largest first, with ties
  broken by position: the assignment depends on the program text alone;
* run-time state lives in one unit. `AIL_LINK_STATE(type, name, init)` becomes the definition there and
  `extern type name` elsewhere, and a file-scope mutable `static` variable (the object pool) is defined
  without `static` in that unit and declared `extern` in the others. `AIL_LINK_EXPORT` is `static`.

Anything the plan cannot show to be safe returns None and the caller builds one unit, as before.
"""
import os
import re

# below this many characters of movable user code, gcc's time is dominated by the shared runtime that
# every unit parses again, and splitting does not pay (tiny programs build in one unit)
MIN_MOVABLE = int(os.environ.get('AIL_CC_SPLIT_MIN') or 30000)
# the heaviest unit must hold at most this share of the movable code, or the split cannot pay
MAX_SHARE = 0.70

_COMMENT = re.compile(r'/\*.*?\*/|//[^\n]*', re.S)
_STATIC_AT_COL0 = re.compile(r'^static\b', re.M)
_STOP = re.compile(r'[;{]')
_INDENTED_STATIC = re.compile(r'^[ \t]+static\s+(?!const\b)(?!inline\b)([^;(){]*?)\b(\w+)\s*(?:\[[^\]]*\])?\s*(?:=[^;]*)?;', re.M)
# per-unit scratch buffers of a header function: independent in every unit by design
_BENIGN_LOCAL_STATIC = frozenset({'scratch', 'scratch_cap'})
_NAME_BEFORE_PAREN = re.compile(r'(\w+)\s*\(')
_ATTRIBUTE = re.compile(r'__attribute__\(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)\)')


def _comment_spans(text):
    return [(m.start(), m.end()) for m in _COMMENT.finditer(text)]


def _in_spans(spans, pos):
    lo, hi = 0, len(spans)
    while lo < hi:
        mid = (lo + hi) // 2
        if spans[mid][1] <= pos:
            lo = mid + 1
        else:
            hi = mid
    return lo < len(spans) and spans[lo][0] <= pos


def _share_state(declarations):
    """The file-scope mutable `static` variables of the declarations as (start, end, owner_text,
    extern_text) replacements, or None when one cannot be shared with certainty."""
    spans = _comment_spans(declarations)
    found = []
    for m in _STATIC_AT_COL0.finditer(declarations):
        start = m.start()
        if _in_spans(spans, start):
            continue
        stop = _STOP.search(declarations, start)
        if stop is None:
            return None
        head = declarations[start:stop.start()]
        if '\n#' in head:                 # a preprocessor line inside the statement: not a plain declaration
            return None
        end = stop.end()
        if stop.group() == '{':
            if '=' not in head:
                continue                  # a function definition
            if re.search(r'\bconst\b', head) and '*' not in head:
                continue                  # a read-only table: a private copy per unit is the same table
            end = _brace_end(declarations, stop.start())
            if end is None:
                return None
        # a statement ending in ';': a prototype, a typedef-like declaration or a variable
        cut = head.find('=')
        decl = head if cut < 0 else head[:cut]
        if re.match(r'static\s+(?:inline\b|__attribute__)', decl):
            continue
        if re.search(r'\w\s*\(', decl) and not re.search(r'\(\s*\*', decl):
            continue                      # a function prototype
        if re.search(r'\bconst\b', decl) and '*' not in decl:
            continue                      # read-only data is replicated
        if cut >= 0 and ',' in decl and not re.search(r'\[[^\]]*,', decl):
            return None                   # several declarators with an initialiser
        if cut >= 0 and re.search(r'\[\s*\]', decl):
            return None                   # `x[] = {...}`: its size comes from the initialiser
        rest = decl[len('static'):].strip()
        found.append((start, end, declarations[start + len('static'):end].lstrip(), 'extern ' + rest + ';'))
    return found


def _brace_end(text, at):
    """The offset just past the `;` that follows the brace group opening at `at`, or None."""
    depth, i, n = 0, at, len(text)
    while i < n:
        c = text[i]
        if c == chr(34) or c == chr(39):
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == chr(92) else 1
            i = j
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                rest = text[i + 1:i + 40].lstrip()
                return i + 1 + (len(text[i + 1:i + 40]) - len(rest)) + 1 if rest.startswith(';') else None
        i += 1
    return None


def _items(text):
    """The top-level items of C `text` (function definitions and `;`-terminated declarations), or None
    when the text is not that. Skips comments, string and character literals and preprocessor lines."""
    items, start, depth, i, n = [], 0, 0, 0, len(text)
    header_end = None
    while i < n:
        c = text[i]
        if c == '/' and text.startswith('/*', i):
            j = text.find('*/', i + 2)
            if j < 0:
                return None
            i = j + 2
            continue
        if c == '/' and text.startswith('//', i):
            j = text.find(chr(10), i)
            i = n if j < 0 else j
            continue
        if c == '#' and text[start:i].strip() == '':
            j = i
            while True:
                k = text.find(chr(10), j)
                if k < 0:
                    return None
                if text[k - 1] != chr(92):
                    break
                j = k + 1
            return None                       # a preprocessor line inside a helper prefix: leave it alone
        if c == chr(34) or c == chr(39):
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == chr(92) else 1
            i = j + 1
            continue
        if c in '({[':
            if c == '{' and depth == 0 and header_end is None:
                header_end = i
            depth += 1
        elif c in ')}]':
            depth -= 1
            if depth < 0:
                return None
            if c == '}' and depth == 0 and header_end is not None \
                    and text[start:header_end].rstrip().endswith(')'):
                items.append(text[start:i + 1])
                start, header_end = i + 1, None
        elif c == ';' and depth == 0:
            items.append(text[start:i + 1])
            start, header_end = i + 1, None
        i += 1
    if depth or text[start:].strip():
        return None
    return items


def _prefix_functions(prefix):
    """The names of the `static` functions a user function's own prefix defines, or None when the
    prefix holds anything else (data, a non-static function, a type)."""
    # include-guarded type definitions (`#ifndef X / #define X / typedef ...; / #endif`) may sit in a prefix
    guards = re.compile(r'^[ \t]*#[ \t]*(?:ifndef|define|endif)\b[^\n]*\n', re.M)
    items = _items(guards.sub('', prefix))
    if items is None:
        return None
    names = []
    for item in items:
        brace = item.find('{')
        if brace < 0:
            return None
        tag = re.match(r'\s*(?:struct|union)\s+(\w+)\s*$', item[:brace])
        if tag and item.rstrip().endswith('};'):
            names.append(tag.group(1))       # a frame type the function's own helpers share
            continue
        alias = re.match(r'\s*typedef\s+(?:struct|union)\s*\w*\s*$', item[:brace])
        if alias and item.rstrip().endswith(';'):
            names.append(re.findall(r'\w+', item[item.rindex('}') + 1:])[-1])   # a type name other functions may use
            continue
        bare = _ATTRIBUTE.sub(' ', item[:brace])
        fn = _movable_name(bare)
        if fn is None or not re.search(r'\bstatic\b', bare[:bare.index(fn)]):
            return None
        names.append(fn)
    return names


def _movable_name(head):
    """The C name a user function's prototype declares."""
    last = None
    for m in _NAME_BEFORE_PAREN.finditer(head):
        last = m.group(1)
        break
    return last


last_reason = None
last_detail = None


def _no(code):
    global last_reason
    last_reason = code
    return None


def plan(split, body, main, units, *, strip=None):
    """N C sources (the first one defines the run-time state and holds `main`) that together build the
    program `body + main`, or None when the program should stay one unit."""
    global last_detail
    if units < 2 or split is None:
        return _no(1)
    declarations, heads, bodies = split
    if strip is not None:
        declarations = strip(declarations)
        bodies = [strip(b) for b in bodies]
    if declarations + '\n'.join(bodies) != body:
        return _no(2)
    if '#line' in body or len(heads) != len(bodies):
        return _no(3)
    for m in _INDENTED_STATIC.finditer(declarations):
        if m.group(2) not in _BENIGN_LOCAL_STATIC:
            return _no(4)
    replacements = _share_state(declarations)
    if replacements is None:
        return _no(5)

    n = len(bodies)
    static = [False] * n
    name = [None] * n
    cut = [0] * n
    for i, (head, text) in enumerate(zip(heads, bodies)):
        bare = _ATTRIBUTE.sub(' ', head)
        name[i] = _movable_name(bare)
        if name[i] is None:
            return _no(7)
        static[i] = bool(re.search(r'\bstatic\b', bare[:bare.index(name[i])]))
        at = text.find(head + ' {\n')
        if at < 0 and not static[i]:
            # the definition may spell a parameter's qualifiers differently from the prototype
            m = re.search(r'^(?!static\b)[A-Za-z_][^\n]*\b%s\([^\n]*\) \{$' % re.escape(name[i]), text, re.M)
            at = m.start() if m else -1
        if at < 0 and not static[i]:
            last_detail = (head[:200], text[:300])
            return _no(6)
        cut[i] = max(at, 0)
    movable = [i for i in range(n) if not static[i]]
    weight = {i: len(bodies[i]) for i in movable}
    total = sum(weight.values())
    if len(movable) < 2 or total < MIN_MOVABLE:
        return _no(8)

    # helper functions defined in a function's own prefix travel with it; one that another function
    # also names cannot be moved on its own
    shared_prefix = set()
    for i in movable:
        prefix = bodies[i][:cut[i]]
        if not prefix:
            continue
        helpers = _prefix_functions(prefix)
        if helpers is None:
            last_detail = (name[i], prefix[:600])
            return _no(9)
        for helper in helpers:
            word = re.compile(r'\b%s\b' % re.escape(helper))
            if any(word.search(bodies[j]) for j in range(n) if j != i) or word.search(main):
                shared_prefix.add(i)      # another function calls the helper: every unit gets the prefix
                break

    # Largest first onto the lightest unit; ties by position, so the plan depends on the text alone.
    order_fns = sorted(movable, key=lambda i: (-weight[i], i))
    bins = [[0, k, []] for k in range(units)]
    for i in order_fns:
        b = min(bins, key=lambda x: (x[0], x[1]))
        b[0] += weight[i]
        b[2].append(i)
    used = [b for b in bins if b[2]]
    last_detail = (total, max(b[0] for b in used))
    if len(used) < 2 or max(b[0] for b in used) > MAX_SHARE * total:
        return _no(11)
    # the lightest unit defines the shared state and holds `main`
    main_bin = min(used, key=lambda x: (x[0], x[1]))

    owner_bin = main_bin[1]
    owner_decl = _rewrite(declarations, replacements, 2)
    other_decl = _rewrite(declarations, replacements, 3)
    out = []
    order = sorted(used, key=lambda b: (b[1] != owner_bin, b[1]))
    for b in order:
        mine = set(b[2])
        is_owner = b[1] == owner_bin
        if is_owner:
            head = ('#define AIL_LINK_STATE(type, name, init) type name init\n'
                    '#define AIL_LINK_EXPORT static\n' + owner_decl)
        else:
            head = ('#define AIL_LINK_STATE(type, name, init) extern type name\n'
                    '#define AIL_LINK_EXPORT static\n' + other_decl)
        parts = []
        for i in range(n):
            if static[i] or i in mine:
                parts.append(bodies[i])
            elif i in shared_prefix:
                parts.append(bodies[i][:cut[i]])
        out.append(head + '\n'.join(parts) + ('\n' + main if is_owner else '\n'))
    return out


def _rewrite(declarations, replacements, column):
    pieces, last = [], 0
    for item in replacements:
        pieces.append(declarations[last:item[0]])
        pieces.append(item[column])
        last = item[1]
    pieces.append(declarations[last:])
    return ''.join(pieces)


def duplicate_state(object_paths):
    """Names of mutable file-local data defined in more than one object file (state that a unit
    would silently copy), or None when `nm` cannot say."""
    import subprocess
    seen, dup = {}, set()
    for path in object_paths:
        try:
            r = subprocess.run(['nm', '--defined-only', str(path)], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        if r.returncode:
            return None
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[1] in ('b', 'd', 'B', 'D', 'C') and '.' not in parts[2]:
                if parts[2] in seen and seen[parts[2]] != path:
                    dup.add(parts[2])
                seen.setdefault(parts[2], path)
    return dup
