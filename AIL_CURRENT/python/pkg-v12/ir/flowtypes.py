"""Flow-sensitive kinds of the names the legacy front end calls "int-or-float bindings" (stage S4a).

The legacy emitter gives a local that holds an int at one point of a function and a float at another a
dynamically tagged cell (`{int, float, floating}`), and every name that depends on one of those a cell
as well. The IR needs no cell: at every point of the function a name has one kind or the function is
refused. This module computes the kind of each such name at the start of every statement by a forward
analysis over the structured AST (if/else join, loops to a fixed point), asking the legacy front end
for the kind of every right-hand side (`_etype`) with the names set to the kinds they hold there. A
name that is read while it may hold either kind makes the function stay on the legacy emitter.

The analysis is what SSA name splitting does at the source level: afterwards each (name, kind) pair
is a place of its own, `mem2reg` promotes the places, and the arithmetic is plain typed arithmetic.
"""
import ast


class Ambiguous(Exception):
    """A tracked name is read while it may hold either kind (or none): the function is refused."""


def _union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, frozenset()) | v
    return out


class Flow(object):
    def __init__(self, P, fn, ctx, tracked):
        self.P = P
        self.fn = fn
        self.ctx = ctx
        self.tracked = set(tracked)
        self.snap = {}                 # id(stmt) -> {name: frozenset of kinds} at the start of the statement
        self.kinds_ever = {n: set() for n in self.tracked}
        self.loops = []                # [(break states, continue states)]
        self.saved_types = {}

    # ------------------------------------------------------------------ expression kinds under a state
    def _set_types(self, state):
        ctx = self.ctx
        for n in self.tracked:
            kinds = state.get(n, frozenset())
            if len(kinds) == 1:
                ctx.types[n] = next(iter(kinds))

    def reads(self, node, state):
        """Names of `node` that are tracked must hold exactly one kind."""
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in self.tracked:
                if len(state.get(n.id, frozenset())) != 1:
                    raise Ambiguous('%r is read while it may hold %s' % (
                        n.id, ' or '.join(sorted(state.get(n.id, frozenset()))) or 'no value'))

    def etype(self, node, state):
        self.reads(node, state)
        self._set_types(state)
        try:
            return self.P._etype(node, self.ctx)
        except Exception as error:
            raise Ambiguous('no kind for %s: %s' % (type(node).__name__, error))

    # ------------------------------------------------------------------ statements
    def run(self):
        P, fn, ctx = self.P, self.fn, self.ctx
        saved = {n: ctx.types.get(n) for n in self.tracked}
        try:
            state = {n: frozenset() for n in self.tracked}
            for name, kind in ctx.params:
                if name in self.tracked and kind in (P.INT, P.FLT):
                    state[name] = frozenset([kind])
                    self.kinds_ever[name].add(kind)
            self.block(fn.body, state)
        finally:
            for n, t in saved.items():
                if t is None:
                    ctx.types.pop(n, None)
                else:
                    ctx.types[n] = t
        return self.snap

    def block(self, body, state):
        for s in body:
            if state is None:
                return None
            state = self.stmt(s, state)
        return state

    def assign(self, name, kind, state):
        if name in self.tracked:
            if kind not in (self.P.INT, self.P.FLT):
                raise Ambiguous('%r is assigned a value of kind %r' % (name, kind))
            state = dict(state)
            state[name] = frozenset([kind])
            self.kinds_ever[name].add(kind)
        return state

    def stmt(self, s, state):
        P = self.P
        self.snap[id(s)] = dict(state)
        if isinstance(s, ast.Assign):
            if len(s.targets) != 1:
                raise Ambiguous('chained assignment')
            kind = self.etype(s.value, state)
            t = s.targets[0]
            if isinstance(t, ast.Name):
                return self.assign(t.id, kind, state)
            self.reads(t, state)
            return state
        if isinstance(s, ast.AnnAssign):
            if s.value is None:
                return state
            kind = self.etype(s.value, state)
            if isinstance(s.target, ast.Name):
                return self.assign(s.target.id, kind, state)
            return state
        if isinstance(s, ast.AugAssign):
            fake = ast.BinOp(left=ast.Name(id=s.target.id, ctx=ast.Load()) if isinstance(s.target, ast.Name)
                             else s.target, op=s.op, right=s.value)
            ast.copy_location(fake, s)
            kind = self.etype(fake, state)
            if isinstance(s.target, ast.Name):
                return self.assign(s.target.id, kind, state)
            self.reads(s.target, state)
            return state
        if isinstance(s, ast.Expr):
            self.reads(s.value, state)
            return state
        if isinstance(s, (ast.Pass,)):
            return state
        if isinstance(s, ast.Return):
            if s.value is not None:
                self.reads(s.value, state)
            return None
        if isinstance(s, ast.Raise):
            if s.exc is not None:
                self.reads(s.exc, state)
            return None
        if isinstance(s, ast.Assert):
            self.reads(s.test, state)
            if s.msg is not None:
                self.reads(s.msg, state)
            return state
        if isinstance(s, ast.If):
            self.reads(s.test, state)
            a = self.block(s.body, dict(state))
            b = self.block(s.orelse, dict(state))
            return _union(a, b)
        if isinstance(s, ast.While):
            return self.loop(s, state, None)
        if isinstance(s, ast.For):
            return self.loop(s, state, s.target)
        if isinstance(s, ast.Break):
            self.loops[-1][0].append(dict(state))
            return None
        if isinstance(s, ast.Continue):
            self.loops[-1][1].append(dict(state))
            return None
        if isinstance(s, ast.Try):
            for n in ast.walk(ast.Module(body=s.body + [x for h in s.handlers for x in h.body] + s.orelse
                                         + s.finalbody, type_ignores=[])):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in self.tracked:
                    raise Ambiguous('%r is assigned inside a try' % n.id)
            end = self.block(s.body, dict(state))
            out = end
            for h in s.handlers:
                out = _union(out, self.block(h.body, dict(state)))
            if s.orelse and end is not None:
                out = _union(out if out is not end else None, self.block(s.orelse, dict(end)))
            if s.finalbody and out is not None:
                out = self.block(s.finalbody, out)
            return out
        raise Ambiguous('statement %s' % type(s).__name__)

    def target_kind(self, it, state):
        P = self.P
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range':
            return P.INT
        kind = self.etype(it, state)
        if kind in (P.BYTES, P.BYTEARRAY, P.LIST, 'array'):
            return P.INT
        if kind in (P.FLIST,):
            return P.FLT
        return kind

    def loop(self, s, entry, target):
        P = self.P
        if s.orelse:
            raise Ambiguous('loop else')
        head = dict(entry)
        for _ in range(8):
            self.loops.append(([], []))
            if target is None:
                self.reads(s.test, head)
                body_in = dict(head)
            else:
                if not isinstance(target, ast.Name):
                    raise Ambiguous('loop target')
                self.reads(s.iter, head)
                body_in = self.assign(target.id, self.target_kind(s.iter, head), dict(head))
            end = self.block(s.body, body_in)
            breaks, conts = self.loops.pop()
            new = dict(entry)
            for st in [end] + conts:
                new = _union(new, st)
            if new == head:
                out = dict(head)
                for b in breaks:
                    out = _union(out, b)
                return out
            head = new
        raise Ambiguous('no fixed point')
