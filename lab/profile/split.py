#!/usr/bin/env python3
"""split.py -- lab only: cut a generated AIL C file into a runtime unit and a program unit.

Nothing in the compiler uses this.  It answers one question for docs/design/COMPILE_TIME.md 2.2: if the runtime were compiled
once and cached, how much gcc time does a build save, and does the program run the same number of instructions?

    split.py PROGRAM.c OUTDIR [--inline-lines N] [--marker TEXT]

The runtime part is everything before the line holding MARKER (default: the "interned attribute-name ids" comment, where the
program's own text starts on the general path).  Top level definitions of that part are classified:

  * a `static` function that is not `inline`               -> moved to the runtime unit (extern in the program unit)
  * a `static inline` function longer than N lines, or with a mutable function-local `static` -> moved too
  * any other `static inline` function                      -> stays in both units (gcc inlines it as today)
  * a mutable `static` variable                             -> defined in the runtime unit, `extern` in the program unit
  * `static const` data, types, macros, prototypes of kept functions -> copied to both

OUTDIR/rt.c is the whole runtime part with `static` removed from what moved; OUTDIR/user.c is the same text with the moved
bodies cut to prototypes, followed by the program's own text.  Both are plain C: build with the program's own flags, link both.
"""
import argparse, os, re, sys

MARKER = 'interned attribute-name ids'


def scan(text):
    """Split C text into top-level chunks [(kind, text)]; kind in pp, ws, comment, fn, decl."""
    chunks = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ' \t\r\n':
            j = i
            while j < n and text[j] in ' \t\r\n':
                j += 1
            chunks.append(('ws', text[i:j]))
            i = j
            continue
        if c == '#' and (i == 0 or text[i - 1] == '\n'):
            j = i
            while True:
                k = text.find('\n', j)
                if k < 0:
                    k = n
                    break
                if text[k - 1] == '\\':
                    j = k + 1
                    continue
                break
            chunks.append(('pp', text[i:k]))
            i = k
            continue
        if text.startswith('/*', i):
            k = text.find('*/', i + 2)
            k = n if k < 0 else k + 2
            chunks.append(('comment', text[i:k]))
            i = k
            continue
        if text.startswith('//', i):
            k = text.find('\n', i)
            k = n if k < 0 else k
            chunks.append(('comment', text[i:k]))
            i = k
            continue
        # a declaration or definition
        j = i
        depth = 0
        first_brace = None
        is_fn = False
        while j < n:
            c = text[j]
            if c == '"':
                j += 1
                while j < n and text[j] != '"':
                    j += 2 if text[j] == '\\' else 1
                j += 1
                continue
            if c == "'":
                j += 1
                while j < n and text[j] != "'":
                    j += 2 if text[j] == '\\' else 1
                j += 1
                continue
            if text.startswith('/*', j):
                k = text.find('*/', j + 2)
                j = n if k < 0 else k + 2
                continue
            if text.startswith('//', j):
                k = text.find('\n', j)
                j = n if k < 0 else k
                continue
            if c == '#' and (j == 0 or text[j - 1] == '\n') and depth == 0:
                # a preprocessor line inside a declaration at depth 0: skip it as part of the chunk
                k = text.find('\n', j)
                j = n if k < 0 else k
                continue
            if c in '({[':
                if c == '{' and depth == 0 and first_brace is None:
                    first_brace = j
                    head = re.sub(r'/\*.*?\*/', ' ', text[i:j], flags=re.S).strip()
                    head_flat = re.sub(r'__attribute__\s*\(\(.*?\)\)', ' ', head, flags=re.S).strip()
                    if head_flat.endswith(')') and '=' not in head_flat.split('(', 1)[0] \
                            and not re.match(r'(typedef|struct|union|enum)\b', head_flat):
                        is_fn = True
                depth += 1
            elif c in ')}]':
                depth -= 1
                if depth == 0 and c == '}' and is_fn:
                    j += 1
                    break
            elif c == ';' and depth == 0:
                j += 1
                break
            j += 1
        chunks.append(('fn' if is_fn else 'decl', text[i:j]))
        i = j
    return chunks


_STATIC = re.compile(r'\bstatic\b')
_INLINE = re.compile(r'\b(?:inline|__inline|__inline__)\b')
_ATTR = re.compile(r'__attribute__\s*\(\(.*?\)\)', re.S)


def fn_name(head):
    flat = _ATTR.sub(' ', head)
    m = re.search(r'([A-Za-z_]\w*)\s*\(', flat)
    return m.group(1) if m else None


def strip_words(head, words=(_STATIC, _INLINE)):
    for rx in words:
        head = rx.sub('', head, count=1)
    return head


def classify(chunks, inline_lines):
    """-> (moved function names, mutable static variable names)"""
    moved, data = set(), set()
    for kind, t in chunks:
        if kind == 'fn':
            head = t[:t.index('{')]
            hflat = _ATTR.sub(' ', re.sub(r'/\*.*?\*/', ' ', head, flags=re.S))
            if not _STATIC.search(hflat.split('(', 1)[0]):
                continue
            name = fn_name(hflat)
            if not name:
                continue
            inl = bool(_INLINE.search(hflat.split('(', 1)[0]))
            body = t[len(head):]
            if 'always_inline' in head:
                continue
            local_static = re.search(r'\bstatic\b(?![^;]*\bconst\b)', body) is not None
            if not inl or local_static or (inline_lines is not None and t.count('\n') > inline_lines):
                moved.add(name)
        elif kind == 'decl':
            flat = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S).strip()
            if not _STATIC.match(flat) or re.match(r'static\s+(?:const\s+)?(?:struct|union|enum)\b[^;{]*;$', flat) and '(' in flat:
                continue
            pre = flat.split('=', 1)[0]
            if '(' in pre and not re.search(r'\(\s*\*', pre):
                continue                      # a prototype
            if re.search(r'\bconst\b', pre) and '*' not in pre:
                continue                      # constant data: a copy in each unit is harmless
            m = re.search(r'([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*$', pre.strip().rstrip(';').strip())
            if m:
                data.add(m.group(1))
    return moved, data


def build(prelude, inline_lines):
    chunks = scan(prelude)
    moved, data = classify(chunks, inline_lines)
    rt, hdr = [], []
    nfn = ndata = 0
    for kind, t in chunks:
        if kind == 'fn':
            head = t[:t.index('{')]
            hflat = _ATTR.sub(' ', re.sub(r'/\*.*?\*/', ' ', head, flags=re.S))
            name = fn_name(hflat)
            if name in moved and _STATIC.search(hflat.split('(', 1)[0]):
                nfn += 1
                h2 = strip_words(head)
                rt.append(h2 + t[len(head):])
                hdr.append(h2.rstrip() + ';')
                continue
        elif kind == 'decl':
            flat = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S).strip()
            if _STATIC.match(flat):
                pre = flat.split('=', 1)[0]
                if '(' in pre and not re.search(r'\(\s*\*', pre):
                    # a prototype: drop `static inline` when the function moved
                    name = fn_name(pre)
                    if name in moved:
                        t2 = strip_words(t)
                        rt.append(t2)
                        hdr.append(t2)
                        continue
                else:
                    m = re.search(r'([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*$', pre.strip().rstrip(';').strip())
                    if m and m.group(1) in data:
                        ndata += 1
                        rt.append(_STATIC.sub('', t, count=1))
                        decl = _STATIC.sub('extern', pre.strip().rstrip(';'), count=1)
                        hdr.append(decl + ';')
                        continue
        rt.append(t)
        hdr.append(t)
    return ''.join(rt), ''.join(hdr), nfn, ndata


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('program')
    ap.add_argument('out')
    ap.add_argument('--inline-lines', type=int, default=None)
    ap.add_argument('--marker', default=MARKER)
    a = ap.parse_args()
    text = open(a.program, encoding='utf-8', newline='').read()
    k = text.find(a.marker)
    if k < 0:
        sys.exit('marker not found: ' + a.marker)
    k = text.rfind('\n', 0, k) + 1
    prelude, user = text[:k], text[k:]
    rt, hdr, nfn, ndata = build(prelude, a.inline_lines)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'rt.c'), 'w', encoding='utf-8', newline='') as f:
        f.write(rt)
    with open(os.path.join(a.out, 'user.c'), 'w', encoding='utf-8', newline='') as f:
        f.write(hdr + user)
    print('moved %d functions, %d variables; runtime %d B, program unit %d B (full %d B)'
          % (nfn, ndata, len(rt), len(hdr) + len(user), len(text)))


if __name__ == '__main__':
    main()
