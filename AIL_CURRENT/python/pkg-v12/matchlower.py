"""The `match` statement lowered to an if/elif chain before either path compiles the program (Python surface).

    match cmd:                               if isinstance(cmd, (list, tuple)) and len(cmd) == 2 and cmd[0] == "push":
        case ["push", n]:                        n = cmd[1]; stack.append(int(n))
            stack.append(int(n))             elif isinstance(cmd, (list, tuple)) and len(cmd) == 1 and cmd[0] == "pop":
        case ["pop"]:                            print(stack.pop())
            print(stack.pop())               elif isinstance(cmd, dict) and "op" in cmd:
        case {"op": op, **rest}:                 op = cmd["op"]; rest = {...}; ...
            ...                              elif isinstance(cmd, Point) and cmd.x == 0:
        case Point(x=0, y=y) if y > 2:  ->       y = cmd.y; ...   (the guard reads cmd.y for y)
            ...                              else:
        case _:                                  ...
            ...

The subject is evaluated once (a temporary unless it is a plain name no pattern rebinds). Each case is
one test: the structural checks CPython makes, in its order (a sequence pattern takes a list or a
tuple, never a str; a mapping pattern a dict; a class pattern `isinstance`, `__match_args__` for its
positional sub-patterns, the self-matching builtins int/str/float/... for one positional sub-pattern),
the values compared with `==` (`None`, `True`, `False` with `is`), then the guard with the names the
pattern binds replaced by the values they would be bound to. The names are bound at the start of the
case's body, so a failed case binds nothing (CPython leaves the bindings of a failed case unspecified).
The typed path decides `isinstance` of a value whose type it knows when it builds the program
(pyfunc.py `_static_isinstance`), so an if/elif chain over an int, a str, a list or a tuple costs
only the comparisons. A `__match_args__` class attribute that only the lowered patterns read is
removed. Shapes left as written (refused by name later): a class pattern of a class that is not
defined in the program, positional sub-patterns of a class without `__match_args__`, an or-pattern
whose alternatives bind different names, tab indentation, a multi-line string in a case body.
"""
import ast
import io
import re
import tokenize

SELF_MATCHING = ('bool', 'bytearray', 'bytes', 'dict', 'float', 'frozenset', 'int', 'list', 'set', 'str', 'tuple')


class _Leave(Exception):
    pass


class _Never(Exception):
    """This case cannot match any value (a class pattern names an attribute no instance has)."""


def rewrite(source, notes=None):
    if 'match' not in source or 'case' not in source:
        return source
    text = source
    left_at = set()
    for _ in range(200):
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            return source
        matches = [n for n in ast.walk(tree) if isinstance(n, ast.Match)]
        if not matches:
            break
        # innermost last in source order first: lowering one never moves an earlier one
        matches.sort(key=lambda m: (m.lineno, m.col_offset))
        done = False
        for m in reversed(matches):
            if (m.lineno, m.col_offset) in left_at:
                continue
            try:
                text = _Lower(text, tree, m).run()
                done = True
                break
            except _Leave as why:
                left_at.add((m.lineno, m.col_offset))
                note = (m.lineno, 'a match statement left as written: %s' % why.args[0]) if why.args else None
                if notes is not None and note and note not in notes:
                    notes.append(note)
                continue
            except (AttributeError, KeyError, IndexError, TypeError, ValueError):
                left_at.add((m.lineno, m.col_offset))
                continue
        if not done:
            break
    if text == source:
        return source
    return _drop_match_args(text)


def _multiline_string_lines(text):
    lines = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.STRING and tok.end[0] > tok.start[0]:
                lines.update(range(tok.start[0], tok.end[0] + 1))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        raise _Leave("a program text the tokenizer does not read")
    return lines


class _Lower:
    def __init__(self, text, tree, node):
        self.text = text
        self.tree = tree
        self.m = node
        self.lines = text.split('\n')
        self.classes = {c.name: c for c in tree.body if isinstance(c, ast.ClassDef)}
        self.taken = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        # a deque is a sequence for a sequence pattern in CPython, and not a list or a tuple here
        self.deque = any(isinstance(n, ast.alias) and n.name == 'deque' or
                         isinstance(n, ast.Attribute) and n.attr == 'deque' for n in ast.walk(tree))

    def fresh(self, base):
        k = 1
        while '%s%d' % (base, k) in self.taken:
            k += 1
        name = '%s%d' % (base, k)
        self.taken.add(name)
        return name

    def run(self):
        m = self.m
        lines = self.lines
        if '\t' in ''.join(lines[m.lineno - 1:m.end_lineno]):
            raise _Leave('tab indentation')
        strings = _multiline_string_lines(self.text)
        if any(ln in strings for ln in range(m.lineno, m.end_lineno + 1)):
            raise _Leave('a multi-line string in a case')
        indent = m.col_offset
        pad = ' ' * indent
        captured = set()
        for c in m.cases:
            for n in ast.walk(c.pattern):
                if isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
                    captured.add(n.name)
                if isinstance(n, ast.MatchMapping) and n.rest:
                    captured.add(n.rest)
        subject_src = ast.get_source_segment(self.text, m.subject)
        if subject_src is None or '\n' in subject_src:
            subject_src = ast.unparse(m.subject)
        if isinstance(m.subject, ast.Name) and m.subject.id not in captured:
            subj, head = m.subject.id, ''
        else:
            subj = self.fresh('_ail_m')
            head = '%s = %s' % (subj, subject_src)
        out = {}                     # line number -> new text (whole line)
        for ln in range(m.lineno, m.end_lineno + 1):
            out[ln] = ''
        if head:
            out[m.lineno] = pad + head
        first = True
        extra = {}                   # line number -> a line inserted before it
        for k, c in enumerate(m.cases):
            try:
                conds, binds = self.pattern(c.pattern, subj)
                never = False
            except _Never:
                conds, binds, never = ['False'], [], True
            test = ' and '.join(conds)
            if c.guard is not None and not never:
                guard = _substitute(c.guard, dict(binds))
                test = ('(%s) and (%s)' % (test, guard)) if conds else guard
            if not test:
                header = 'else:' if not first else 'if True:'
            else:
                header = ('if %s:' if first else 'elif %s:') % test
            if not test and k != len(m.cases) - 1:
                raise _Leave('an irrefutable case before the last one')        # an irrefutable case before the last one (a SyntaxError in CPython)
            first = False
            out[c.pattern.lineno] = pad + header
            if never:
                # never runs: its body (which reads the missing attribute) is not compiled
                out[c.pattern.lineno] = pad + header + ' pass' if c.body[0].lineno == c.pattern.lineno else pad + header
                for ln in range(c.body[0].lineno, c.body[-1].end_lineno + 1):
                    if ln != c.pattern.lineno:
                        out[ln] = ''
                if c.body[0].lineno != c.pattern.lineno:
                    out[c.body[0].lineno] = ' ' * (indent + 4) + 'pass'
                continue
            if c.body[0].lineno == c.pattern.lineno:
                # `case 0: return "zero"` -- the body stays on the case's line
                if c.body[-1].end_lineno != c.pattern.lineno:
                    raise _Leave('a case body that continues past the line of its case')
                raw = lines[c.pattern.lineno - 1].encode('utf-8')
                segment = raw[c.body[0].col_offset:].decode('utf-8')
                if binds:
                    segment = '; '.join('%s = %s' % (name, e) for name, e in binds) + '; ' + segment
                out[c.pattern.lineno] = pad + header + ' ' + segment
                continue
            body_col = c.body[0].col_offset
            shift = body_col - (indent + 4)
            if shift < 0:
                raise _Leave('a case body indented less than expected')
            start = c.body[0].lineno
            end = c.body[-1].end_lineno
            for ln in range(start, end + 1):
                line = lines[ln - 1]
                if line[:shift].strip():
                    raise _Leave('a line of a case body indented less than the body')
                out[ln] = line[shift:] if len(line) >= shift else line.lstrip(' ')
            if binds:
                text = '; '.join('%s = %s' % (name, e) for name, e in binds)
                b0 = c.body[0]
                simple = isinstance(b0, (ast.Expr, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Return, ast.Pass,
                                         ast.Raise, ast.Assert, ast.Delete, ast.Break, ast.Continue, ast.Global,
                                         ast.Nonlocal, ast.Import, ast.ImportFrom))
                lead = ' ' * (indent + 4)
                if simple:
                    out[start] = lead + text + '; ' + out[start][len(lead):]
                else:
                    extra[start] = lead + text
            # comment and blank lines between the cases keep their place
        new_lines = []
        for ln in range(1, len(lines) + 1):
            if ln in extra:
                new_lines.append(extra[ln])
            new_lines.append(out[ln] if ln in out else lines[ln - 1])
        return '\n'.join(new_lines)

    # -- patterns -----------------------------------------------------------------------------------------
    def has_attr(self, name, attr, acc):
        """The conditions under which a value that passed `isinstance(acc, name)` has `attr`: none when
        every instance of `name` and of its subclasses has it; an isinstance of the subclasses that have it;
        _Never when none has it. A class pattern on a missing attribute does not match in CPython."""
        below = [name]
        changed = True
        while changed:
            changed = False
            for c in self.classes.values():
                if c.name not in below and any(isinstance(b, ast.Name) and b.id in below for b in c.bases):
                    below.append(c.name)
                    changed = True
        info = {c: _class_attrs(self.classes[c], self.classes) for c in below}
        if all(attr in info[c][0] for c in below):
            return []
        if any(attr in info[c][1] or '*' in info[c][1] for c in below) or self.outside_stores(attr):
            return []            # set later or from outside: read as written (AttributeError, as declared)
        having = [c for c in below if attr in info[c][0]]
        if not having:
            raise _Never()
        return ['(%s)' % ' or '.join('isinstance(%s, %s)' % (acc, c) for c in having)]

    def outside_stores(self, attr):
        """`obj.attr = ...` or setattr() somewhere other than on a method's own first parameter."""
        for fn in ast.walk(self.tree):
            if isinstance(fn, ast.Call) and isinstance(fn.func, ast.Name) and fn.func.id == 'setattr':
                return True
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Attribute) and n.attr == attr and isinstance(n.ctx, ast.Store):
                if not (isinstance(n.value, ast.Name) and n.value.id in ('self', 'cls')):
                    return True
        return False

    def pattern(self, p, acc):
        """(conditions, bindings) for pattern `p` against the value written `acc`."""
        if isinstance(p, ast.MatchValue):
            return ['%s == %s' % (acc, _paren(ast.unparse(p.value)))], []
        if isinstance(p, ast.MatchSingleton):
            return ['%s is %r' % (acc, p.value)], []
        if isinstance(p, ast.MatchAs):
            if p.pattern is None:
                return [], ([(p.name, acc)] if p.name else [])
            conds, binds = self.pattern(p.pattern, acc)
            return conds, binds + ([(p.name, acc)] if p.name else [])
        if isinstance(p, ast.MatchOr):
            alts = [self.pattern(q, acc) for q in p.patterns]
            names = [sorted(n for n, _ in b) for _, b in alts]
            if any(n != names[0] for n in names):
                raise _Leave('an or-pattern whose alternatives bind different names')
            tests = [' and '.join(c) if c else 'True' for c, _ in alts]
            if any(t == 'True' for t in tests):
                cond = []
            else:
                cond = ['(%s)' % ' or '.join('(%s)' % t for t in tests)]
            binds = []
            for name in names[0]:
                choices = [dict(b)[name] for _, b in alts]
                if len(set(choices)) == 1:
                    binds.append((name, choices[0]))
                    continue
                e = choices[-1]
                for t, ch in reversed(list(zip(tests[:-1], choices[:-1]))):
                    e = '(%s if %s else %s)' % (ch, t, e)
                binds.append((name, e))
            return cond, binds
        if isinstance(p, ast.MatchSequence):
            if self.deque:
                raise _Leave('a sequence pattern in a program that uses collections.deque (a deque subject would '
                             'not be told from a value that is not a sequence)')
            star = [i for i, q in enumerate(p.patterns) if isinstance(q, ast.MatchStar)]
            n = len(p.patterns)
            conds = ["(isinstance(%s, list) or isinstance(%s, tuple) or isinstance(%s, range))" % (acc, acc, acc)]
            if star:
                s = star[0]
                after = n - s - 1
                if n - 1:
                    conds.append('len(%s) >= %d' % (acc, n - 1))
            else:
                s, after = None, 0
                conds.append('len(%s) == %d' % (acc, n))
            binds = []
            for i, q in enumerate(p.patterns):
                if s is not None and i == s:
                    if q.name:
                        sl = '%s[%d:]' % (acc, s) if after == 0 else '%s[%d:%d]' % (acc, s, -after)
                        binds.append((q.name, "[_ail_x for _ail_x in %s]" % sl))
                    continue
                index = i if s is None or i < s else i - n
                c, b = self.pattern(q, '%s[%d]' % (acc, index))
                conds.extend(c)
                binds.extend(b)
            return conds, binds
        if isinstance(p, ast.MatchMapping):
            conds = ['isinstance(%s, dict)' % acc]
            binds = []
            keys = []
            for key, q in zip(p.keys, p.patterns):
                ks = _paren(ast.unparse(key))
                keys.append(ks)
                conds.append('%s in %s' % (ks, acc))
                c, b = self.pattern(q, '%s[%s]' % (acc, ks))
                conds.extend(c)
                binds.extend(b)
            if p.rest:
                binds.append((p.rest, '{_ail_k: _ail_v for _ail_k, _ail_v in %s.items() if %s}'
                              % (acc, ' and '.join('_ail_k != %s' % k for k in keys) or 'True')))
            return conds, binds
        if isinstance(p, ast.MatchClass):
            if not isinstance(p.cls, ast.Name):
                raise _Leave('a class pattern whose class is not a plain name')
            name = p.cls.id
            conds = ['isinstance(%s, %s)' % (acc, name)]
            binds = []
            if name in SELF_MATCHING and name not in self.classes:
                if len(p.patterns) > 1 or p.kwd_attrs:
                    raise _Leave('more than one positional sub-pattern of a builtin class')
                if p.patterns:
                    c, b = self.pattern(p.patterns[0], acc)
                    conds.extend(c)
                    binds.extend(b)
                return conds, binds
            if name not in self.classes:
                raise _Leave('a class pattern of a class this program does not define')
            if p.patterns:
                args = _match_args(self.classes[name])
                if args is None or len(p.patterns) > len(args):
                    raise _Leave('positional sub-patterns of a class without __match_args__ (or with fewer names)')
                for attr, q in zip(args, p.patterns):
                    conds.extend(self.has_attr(name, attr, acc))
                    c, b = self.pattern(q, '%s.%s' % (acc, attr))
                    conds.extend(c)
                    binds.extend(b)
            for attr, q in zip(p.kwd_attrs, p.kwd_patterns):
                conds.extend(self.has_attr(name, attr, acc))
                c, b = self.pattern(q, '%s.%s' % (acc, attr))
                conds.extend(c)
                binds.extend(b)
            return conds, binds
        raise _Leave('this pattern shape')


def _class_attrs(cls, classes, seen=()):
    """(attributes every instance of `cls` has, attributes some instance may get later), told from the
    class body, the stores to `self.x` in `__init__` (and the other methods), and the bases."""
    sure, later = set(), set()
    for st in cls.body:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sure.add(st.name)
            for n in ast.walk(st):
                if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store) and isinstance(n.value, ast.Name) \
                        and st.args.args and n.value.id == st.args.args[0].arg:
                    (sure if st.name == '__init__' else later).add(n.attr)
        elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
            sure.add(st.target.id)
        elif isinstance(st, ast.Assign):
            sure.update(t.id for t in st.targets if isinstance(t, ast.Name))
    for b in cls.bases:
        if isinstance(b, ast.Name) and b.id in classes and b.id not in seen:
            s2, l2 = _class_attrs(classes[b.id], classes, seen + (cls.name,))
            sure |= s2
            later |= l2
        elif not (isinstance(b, ast.Name) and b.id == 'object'):
            later.add('*')        # a base of unknown shape
    return sure, later


def _paren(text):
    return text if re.fullmatch(r'[\w.]+|-?\d[\w.]*|\'[^\'\\]*\'|"[^"\\]*"', text) else '(%s)' % text


def _match_args(cls):
    """The attribute names of `__match_args__` (a literal tuple of str in the class body), or the fields
    of a @dataclass in order; None when the class has neither."""
    for s in cls.body:
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name) \
                and s.targets[0].id == '__match_args__':
            v = s.value
            if isinstance(v, (ast.Tuple, ast.List)) and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                                                            for e in v.elts):
                return [e.value for e in v.elts]
            return None
    if any((isinstance(d, ast.Name) and d.id == 'dataclass') or
           (isinstance(d, ast.Attribute) and d.attr == 'dataclass') or
           (isinstance(d, ast.Call) and ast.unparse(d.func).endswith('dataclass')) for d in cls.decorator_list):
        return [s.target.id for s in cls.body if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)]
    return None


def _substitute(guard, binds):
    """The guard with the names a pattern binds replaced by the values they would be bound to.

    A name a nested scope rebinds (a lambda parameter, a comprehension target) is left as it is, and
    the rest of that scope is substituted: `case [x] if all(x == 9 for x in [1, 2])` keeps the
    comprehension's own x, while `case x if (lambda y: y == x)(v)` substitutes the free x."""
    tree = ast.parse(ast.unparse(guard), mode='eval')

    def targets(node):
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}

    class Sub(ast.NodeTransformer):
        def __init__(self):
            self.shadow = frozenset()

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load) and node.id in binds and node.id not in self.shadow:
                return ast.parse(binds[node.id], mode='eval').body
            return node

        def _visit(self, node, shadow):
            old = self.shadow
            self.shadow = frozenset(shadow)
            try:
                return self.visit(node)
            finally:
                self.shadow = old

        def visit_Lambda(self, node):
            node.args.defaults = [self.visit(d) for d in node.args.defaults]
            node.args.kw_defaults = [self.visit(d) if d is not None else None for d in node.args.kw_defaults]
            args = node.args
            params = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
            if args.vararg:
                params.add(args.vararg.arg)
            if args.kwarg:
                params.add(args.kwarg.arg)
            node.body = self._visit(node.body, self.shadow | params)
            return node

        def _comprehension(self, node, values):
            shadow = self.shadow
            for gen in node.generators:
                gen.iter = self._visit(gen.iter, shadow)
                shadow = shadow | targets(gen.target)
                gen.ifs = [self._visit(cond, shadow) for cond in gen.ifs]
            for attr in values:
                setattr(node, attr, self._visit(getattr(node, attr), shadow))
            return node

        def visit_ListComp(self, node):
            return self._comprehension(node, ('elt',))

        visit_SetComp = visit_ListComp
        visit_GeneratorExp = visit_ListComp

        def visit_DictComp(self, node):
            return self._comprehension(node, ('key', 'value'))

    return ast.unparse(Sub().visit(tree).body)


def _drop_match_args(text):
    """`__match_args__ = (...)` in a class body that nothing else reads becomes `pass` (the typed path
    has no tuple class attributes; the lowered patterns read the attributes themselves)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    uses = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == '__match_args__']
    if uses:
        return text
    lines = text.split('\n')
    for c in tree.body:
        if not isinstance(c, ast.ClassDef):
            continue
        for s in c.body:
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name) \
                    and s.targets[0].id == '__match_args__':
                lines[s.lineno - 1] = ' ' * s.col_offset + 'pass'
                for ln in range(s.lineno + 1, s.end_lineno + 1):
                    lines[ln - 1] = ''
    return '\n'.join(lines)
