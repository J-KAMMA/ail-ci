"""S3b: the sharing core on the IR (design section 13; rules of section 2.5).

Under the decided Python semantics `ys = xs` makes one list with two names. The lowering records
every such event as `list.share (dst, src)` instead of guessing; this module decides, with liveness
and effects computed on the IR, what each one is:

  Rule M  (move)       the source is dead afterwards on every path (including exception edges):
                       the destination takes its storage (`list.move`). A swap `t = a; a = b; b = t`
                       is three moves. Also `list.copy` of a dead source (Rule 1).
  Rule M' (move, then  the source is still read afterwards: the destination (a struct field) takes
          borrow)      the storage and the source's later uses become uses of the field's list,
                       provided nothing rebinds the field, or lets a lent view dangle, while the
                       source is live (B1), and every such use is reached only through the share.
  Rule B  (rename)     `ys = xs` with `xs` live afterwards: the uses of `ys` reached through the share
                       become uses of `xs` (or of the field list a field-sourced `ys = t.f` names),
                       provided nothing rebinds the owner while `ys` is live. One list, two names,
                       no copy and no count: Python's meaning.
  Rule X  (box)        anything else: two owners with overlapping lifetimes. The box layout and its
                       reference counts belong to stage S3e, so the function is refused (it stays on
                       the legacy emitter) and the site is reported.

The analysis works on a control-flow graph of the structured IR (an edge per instruction, plus
exception edges into every enclosing handler or finally), with places as the unit of liveness. It
replaces S3a's syntactic proof (`Lowering.rest_safe`). `resolve` runs once, at the end of lowering,
before the first verification: a surviving `list.share` is a verifier error.
"""
from . import ir as I
from . import effects as E

_LISTS = (I.T('obj', I.T('list', I.I64)), I.T('obj', I.T('list', I.F64)))
DST_OPS = ('list.reset', 'list.lit', 'list.repeat', 'list.move', 'list.call', 'list.copy', 'list.share', 'list.rt', 'list.sortperm')
WRITE_OPS = ('list.set', 'list.push', 'list.pop', 'list.clear', 'list.reserve', 'list.sort', 'list.permute',
             'rec.push', 'rec.up', 'rec.pop')
CALLS = ('call', 'list.call', 'ba.call')


class NeedsBox(Exception):
    """Rule X: the site needs a box (S3e); the message names it."""


class ValueDiffers(NeedsBox):
    """Value-semantics mode only: sharing at this site would show through a write to one of the two
    names (the legacy emitter, and so a brace-syntax file, copies there): the site becomes a copy."""


def _regions(fn):
    yield fn.body
    for ins in I.walk(fn.body):
        for r in ins.regions:
            yield r


def _delete(fn, ins):
    for r in _regions(fn):
        for k, i in enumerate(r.instrs):
            if i is ins:
                del r.instrs[k]
                return True
    return False


def _insert_before(fn, at, ins):
    for r in _regions(fn):
        for k, i in enumerate(r.instrs):
            if i is at:
                r.instrs.insert(k, ins)
                return
    raise I.IRError('instruction to insert before is not in %s' % fn.name)


class Flow(object):
    """The CFG, the per-instruction events on list places, and liveness."""

    def __init__(self, fn, program, summaries):
        self.fn = fn
        self.program = program
        self.summaries = summaries or {}
        self.defs = E.defs_of(fn)
        self.pnames = E.place_names(fn)
        self.succ = {}
        self.exc = {}
        self.nodes = []
        self.consumers = {}
        for ins in I.walk(fn.body):
            for v in ins.operands:
                self.consumers.setdefault(v, []).append(ins)
        self.entry = self.region(fn.body, None, ([], [], []))
        self.events()
        self.liveness()

    # ------------------------------------------------------------------ the graph
    def region(self, region, after, env):
        nxt = after
        for ins in reversed(region.instrs):
            self.link(ins, nxt, env)
            nxt = ins
        return nxt

    def link(self, ins, nxt, env):
        loops, handlers, fins = env
        op = ins.op
        self.nodes.append(ins)
        s = []
        if op == 'if':
            s = [self.region(ins.regions[0], nxt, env), self.region(ins.regions[1], nxt, env)]
        elif op in ('loop', 'for.range'):
            e = self.region(ins.regions[0], ins, (loops + [(ins, nxt)], handlers, fins))
            s = [e] + ([nxt] if op == 'for.range' else [])
        elif op == 'try':
            if ins.attrs.get('kind') == 'finally':
                fe = self.region(ins.regions[1], nxt, env)
                env2 = (loops, ([fe] if fe is not None else []) + handlers, fins + ([fe] if fe is not None else []))
                s = [self.region(ins.regions[0], fe if fe is not None else nxt, env2)]
            else:
                hs = [h for h in (self.region(r, nxt, env) for r in ins.regions[1:]) if h is not None]
                s = [self.region(ins.regions[0], nxt, (loops, hs + handlers, fins))]
        elif op == 'yield':
            s = [nxt]
        elif op == 'break':
            s = [loops[-1][1]] + fins
        elif op == 'continue':
            s = [loops[-1][0]] + fins
        elif op == 'return':
            s = list(fins)
        elif op in ('raise', 'reraise', 'unreachable'):
            s = []
        else:
            s = [nxt]
        self.succ[ins] = [x for x in s if x is not None]
        self.exc[ins] = list(handlers)

    # ------------------------------------------------------------------ events
    def place_of(self, v):
        d = self.defs.get(v)
        if d is not None and d.op == 'list.ref':
            return d.operands[0]
        return None

    def field_of(self, v):
        d = self.defs.get(v)
        if d is not None and d.op == 'field.list':
            return (d.attrs.get('cls'), d.attrs.get('name'))
        return None

    def events(self):
        self.uses, self.kills, self.writes = {}, {}, {}
        for ins in self.nodes:
            u, k, w = set(), set(), set()
            if not (ins.op == 'list.reset' and ins.attrs.get('drop')):
                for j, v in enumerate(ins.operands):
                    p = self.place_of(v)
                    if p is None:
                        continue
                    if ins.op in DST_OPS and j == 0:
                        k.add(p)
                    else:
                        u.add(p)
                        if ins.op in WRITE_OPS or (ins.op in ('list.move',) and j == 1):
                            w.add(p)
            self.uses[ins], self.kills[ins], self.writes[ins] = u, k, w

    def liveness(self):
        self.live_in = dict((n, set()) for n in self.nodes)
        self.live_out = dict((n, set()) for n in self.nodes)
        changed = True
        while changed:
            changed = False
            for n in self.nodes:
                out = set()
                for x in self.succ[n]:
                    out |= self.live_in[x]
                ex = set()
                for x in self.exc[n]:
                    ex |= self.live_in[x]
                new = self.uses[n] | (out - self.kills[n]) | ex
                self.live_out[n] = out | ex
                if new != self.live_in[n]:
                    self.live_in[n] = new
                    changed = True

    # ------------------------------------------------------------------ reachability
    def forward(self, starts, barrier=(), cut=None):
        seen = set()
        stack = [x for x in starts if x is not None]
        while stack:
            n = stack.pop()
            if n in seen or n in barrier:
                continue
            seen.add(n)
            if cut is not None and cut(n):
                continue
            stack.extend(self.succ[n])
            stack.extend(self.exc[n])
        return seen

    # ------------------------------------------------------------------ effects of calls
    def call_effects(self, ins):
        return E.instr_effects(ins, self.fn, self.program, self.pnames, self.defs, self.summaries)

    def rebinds_field(self, n, key):
        """Whether `n` may replace the list the field `key` holds."""
        if n.op in DST_OPS and n.operands and self.field_of(n.operands[0]) == key and not (
                n.op == 'list.reserve'):
            return True
        if n.op in CALLS:
            eff = self.call_effects(n)
            return eff.unknown or ('Rebind(Field(%s,%s))' % key) in eff.writes
        return False

    def spine_writes(self, n, key):
        if n.op in CALLS:
            eff = self.call_effects(n)
            return eff.unknown or ('Spine(Field(%s,%s))' % key) in eff.writes
        return False


def _where(share):
    a = share.attrs
    return '`%s = %s`%s' % (a.get('dst', '?'), a.get('src', '?'),
                            (' at line %s' % a['line']) if a.get('line') else '')


class Resolver(object):
    def __init__(self, fn, program, summaries, value=False):
        self.fn = fn
        self.program = program
        self.summaries = summaries
        self.value = value           # value semantics: a share that could be observed becomes a copy
        self.stats = dict(copies_inserted=0, moves=0, field_moves=0, takes=0, renames=0, field_borrows=0, copies_moved=0, boxes=0)
        self.alias_of = {}           # a place that became a borrower -> the place it now names
        self.alias_roots = set()     # roots whose index proofs (legacy, by name) no longer hold
        self.walias = []

    def run(self, loops):
        fn = self.fn
        guard = 0
        while True:
            guard += 1
            if guard > 10000:
                raise I.IRError('ownership analysis did not settle')
            work = [i for i in I.walk(fn.body) if i.op in ('list.share', 'list.copy')]
            pending = [i for i in work if i.op == 'list.share' or self.copy_is_move_candidate(i)]
            if not pending:
                break
            flow = Flow(fn, self.program, self.summaries)
            ins = pending[0]
            if ins.op == 'list.copy':
                self.resolve_copy(flow, ins)
            elif self.value:
                self.resolve_value(flow, ins)
            else:
                self.resolve_share(flow, ins)
        self.fix_drops()
        self.check_loops(loops)
        self.downgrade_proofs()
        return self

    # ------------------------------------------------------------------ explicit copies (Rule 1)
    def copy_is_move_candidate(self, ins):
        return not ins.attrs.get('kept')

    def resolve_copy(self, flow, ins):
        dref, sref = ins.operands
        D, X = flow.place_of(dref), flow.place_of(sref)
        if X is not None and D is not X and X not in flow.live_out[ins]:
            ins.op = 'list.move'            # Rule 1: nothing can observe the source afterwards
            self.stats['copies_moved'] += 1
            return
        ins.attrs['kept'] = True

    # ------------------------------------------------------------------ value semantics (option A)
    def resolve_value(self, flow, s):
        """A brace-syntax file keeps value semantics until S6: `dst = src` means a copy. The cheap
        shapes keep their meaning without one (same place, dead source: a move; a field taken out
        and rebound), a rename or borrow stays only when no write through either name can be seen
        through the other; everything else, and every site the sharing rules refuse (Rule X), is the
        copy that value semantics implies. (Every check that raises does so before the IR is edited.)"""
        try:
            return self.resolve_share(flow, s)
        except NeedsBox as box:
            D, X = self.target(flow, s.operands[0]), self.target(flow, s.operands[1])
            if D[0] == '?':
                raise
            if any(T[0] == 'F' and T[2] not in self.fn.params for T in (D, X)):
                # the IR does not hoist the field lists of a struct local yet (the copy, and the loop
                # reading them, cost more than the legacy emitter's in-place moves: grid_life-ail-3
                # +5% instructions); the function stays on the legacy emitter, which has value semantics
                raise NeedsBox('%s (a field list of a struct local is left to the legacy emitter)' % box)
            differs = isinstance(box, ValueDiffers) or self.copy_differs(flow, s)
            self.note(s, 'copy', differs)
            s.op = 'list.copy'
            s.attrs = {'dst': s.attrs.get('dst', '?'), 'line': s.attrs.get('line', 0)}
            self.stats['copies_inserted'] += 1

    def field_written(self, flow, n, key):
        if n.op == 'list.reset' and n.attrs.get('drop'):
            return False
        eff = flow.call_effects(n)
        tag = 'Field(%s,%s)' % key
        return eff.unknown or any(w in ('Elem(%s)' % tag, 'Spine(%s)' % tag, 'Rebind(%s)' % tag)
                                  for w in eff.writes)

    def copy_differs(self, flow, s):
        """W-ALIAS for a share turned into a copy: some name is written while the other can be read
        afterwards (a rough, report-only test)."""
        D = self.target(flow, s.operands[0])
        X = self.target(flow, s.operands[1])
        reach = flow.forward(flow.succ[s])
        for n in reach:
            if n is s:
                continue
            for a, b in ((D, X), (X, D)):
                if a[0] == 'P' and a[1] in flow.writes[n] and (b[0] != 'P' or b[1] in flow.live_out[n]):
                    return True
                if a[0] == 'F' and self.field_written(flow, n, a[1]) and (b[0] != 'P' or b[1] in flow.live_out[n]):
                    return True
        return False

    def field_write_seen(self, flow, reach, s, key, place):
        """Value mode: a write to the field's list at some node while `place` is read afterwards."""
        for n in reach:
            if n is s:
                continue
            if self.field_written(flow, n, key) and (place in flow.live_out[n] or place in flow.uses[n]):
                return True
        return False

    # ------------------------------------------------------------------ list.share
    def target(self, flow, v):
        p = flow.place_of(v)
        if p is not None:
            return ('P', p)
        key = flow.field_of(v)
        if key is not None:
            d = flow.defs[v]
            return ('F', key, d.operands[0], d)
        return ('?',)

    def resolve_share(self, flow, s):
        D = self.target(flow, s.operands[0])
        X = self.target(flow, s.operands[1])
        names = _where(s)
        if D[0] == '?':
            raise NeedsBox('%s: the destination is not a local or field list' % names)
        if X[0] == '?':
            raise NeedsBox('%s: a read-only list parameter or a list that is not owned here is shared '
                           '(its owner is the caller)' % names)
        if D[0] == 'P' and X[0] == 'P':
            if D[1] is X[1]:
                _delete(self.fn, s)
                return
            if X[1] not in flow.live_out[s]:
                s.op = 'list.move'
                s.attrs = {}
                self.stats['moves'] += 1
                return
            return self.rename(flow, s, D[1], X, names, 'P')
        if D[0] == 'F' and X[0] == 'P':
            if X[1] not in flow.live_out[s]:
                s.op = 'list.move'
                s.attrs = {}
                self.stats['field_moves'] += 1
                return
            return self.move_then_borrow(flow, s, D, X[1], names)
        if D[0] == 'P' and X[0] == 'F':
            if self.taken(flow, s, X[1], X[2]):
                s.op = 'list.move'
                s.attrs = {}
                self.stats['takes'] += 1
                return
            return self.rename(flow, s, D[1], X, names, 'F')
        if D[1] == X[1] and D[2] is X[2]:
            _delete(self.fn, s)
            return
        if self.taken(flow, s, X[1], X[2]):
            s.op = 'list.move'
            s.attrs = {}
            self.stats['takes'] += 1
            return
        raise NeedsBox('%s: two struct fields would hold one list' % names)

    # -- Rule M (take): the field is rebound before anything reads it
    def reads_field(self, flow, n, key):
        for j, v in enumerate(n.operands):
            if flow.field_of(v) == key and not (n.op in DST_OPS and j == 0):
                return True
        if n.op in CALLS:
            eff = flow.call_effects(n)
            if eff.unknown:
                return True
            tag = 'Field(%s,%s)' % key
            return any(tag in w for w in eff.reads | eff.writes)
        return False

    def may_raise(self, flow, n):
        if n.op in ('raise', 'reraise'):
            return True
        eff = flow.call_effects(n) if n.op != 'try' else E.UNKNOWN
        return bool(eff.unknown or eff.raises)

    def taken(self, flow, s, key, base):
        """Whether the field `key` of `base`, whose list a take at `s` moves out, is rebound (by a
        destination operation on that very object) on every path before anything reads it, with
        nothing in between that can raise and no exit (the field is empty meanwhile)."""
        holder = self.object_place(flow, base)
        if holder is None:
            return False
        seen = set()
        stack = list(flow.succ[s])
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            if n.op in DST_OPS and n.operands and flow.field_of(n.operands[0]) == key \
                    and self.object_place(flow, flow.defs[n.operands[0]].operands[0]) is holder:
                # the rebinding itself: it must not read the emptied field (`s.f = s.f[:]`), and a call
                # that raises would leave the field empty
                if any(flow.field_of(v) == key for v in n.operands[1:]):
                    return False
                if n.op == 'list.call' and self.may_raise(flow, n):
                    return False
                continue
            if n.op == 'try' or self.reads_field(flow, n, key) or self.may_raise(flow, n):
                return False
            if holder is not base and n.op in ('store', 'obj.copyref', 'obj.init') and n.operands[0] is holder:
                return False        # the struct local names another object before the field is rebound
            if n.op in ('return', 'raise', 'reraise', 'unreachable') or not flow.succ[n]:
                return False
            stack.extend(flow.succ[n])
        return True

    def object_place(self, flow, base):
        """What identifies the object whose field a take empties: a struct parameter (its value), or
        the place of the struct local `base` was loaded from (`taken` refuses a store to that place
        before the rebinding, so every load of it on the way names the same object). None otherwise."""
        if base in self.fn.params:
            return base
        d = flow.defs.get(base)
        if d is not None and d.op == 'load' and d.operands:
            a = flow.defs.get(d.operands[0])
            t = d.operands[0].type.pointee
            if a is not None and a.op == 'local.alloc' and t.head == 'obj' and t.args[0].head == 'class':
                return d.operands[0]
        return None

    # -- the set of uses of `place` reached through the share
    def reached_uses(self, flow, s, place, names):
        reach = flow.forward(flow.succ[s], cut=lambda n: place in flow.kills[n])
        U = set(n for n in reach if n is not s and place in flow.uses[n])
        starts = [flow.entry]
        for k in flow.nodes:
            if k is not s and place in flow.kills[k]:
                starts.extend(flow.succ[k])
        bypass = flow.forward(starts, barrier=(s,))
        if U & bypass:
            raise NeedsBox('%s: a use of the second name can be reached without the assignment '
                           '(two owners on different paths)' % names)
        return reach, U

    def refs_to_rewrite(self, flow, s, place, reach, U, names):
        out = []
        for d in flow.defs.values():
            if d.op != 'list.ref' or d.operands[0] is not place:
                continue
            via = []
            for c in flow.consumers.get(d.result, ()):
                if c.op in DST_OPS and c.operands[0] is d.result:
                    continue
                if (c.op == 'list.reset' and c.attrs.get('drop')) or c is s:
                    continue
                via.append(c)
            inside = [c for c in via if c in U]
            if not inside:
                continue
            if len(inside) != len(via) or d not in reach:
                raise NeedsBox('%s: a borrow of the list is taken before the assignment and used after it' % names)
            out.append((d, inside))
        return out

    def observable(self, flow, s, reach, a, b):
        """W-ALIAS: some name is written while the other is read afterwards (where legacy copies, the
        two meanings differ)."""
        for n in reach:
            if n is s:
                continue
            if (a in flow.writes[n] and b in flow.live_out[n]) or (b in flow.writes[n] and a in flow.live_out[n]):
                return True
        return False

    def note(self, s, kind, differs):
        a = s.attrs
        self.walias.append(dict(line=a.get('line'), dst=a.get('dst'), src=a.get('src'), rule=kind,
                                differs=bool(differs)))

    # -- Rule B: the destination place is renamed to the owner
    def rename(self, flow, s, Dp, X, names, kind):
        reach, U = self.reached_uses(flow, s, Dp, names)
        refs = self.refs_to_rewrite(flow, s, Dp, reach, U, names)
        if kind == 'P':
            Xp = X[1]
            for n in reach:
                if n is not s and Xp in flow.kills[n] and Dp in flow.live_out[n]:
                    raise NeedsBox('%s: the first name is reassigned while the second is still used' % names)
            differs = self.observable(flow, s, reach, Dp, Xp)
        else:
            key, base = X[1], X[2]
            holder = self.object_place(flow, base)
            if holder is None:
                raise NeedsBox('%s: the object holding the list is not a parameter or a struct local' % names)
            if holder is not base:
                # a struct local: it must keep naming the same object (and so keep it alive) while
                # the second name is in use
                for n in reach:
                    if n is not s and n.op in ('store', 'obj.copyref', 'obj.init') and n.operands[0] is holder \
                            and (Dp in flow.live_in[n] or Dp in flow.live_out[n]):
                        raise NeedsBox('%s: the struct local is reassigned while the second name is still used'
                                       % names)
            self.check_field_borrow(flow, s, Dp, reach, key, names)
            for d, inside in refs:
                if any(c.op == 'return' for c in inside):
                    raise NeedsBox('%s: a list a struct field holds is also returned' % names)
            differs = any(Dp in flow.writes[n] for n in reach if n is not s) or any(
                flow.rebinds_field(n, key) for n in reach if n is not s and Dp in flow.live_out[n])
            if self.value and not differs:
                differs = self.field_write_seen(flow, reach, s, key, Dp)
        if self.value and differs:
            raise ValueDiffers('%s: a write through one name can be seen through the other' % names)
        for d, inside in refs:
            if kind == 'P':
                d.operands = [X[1]]
            else:
                obj = X[2]
                if obj not in self.fn.params:
                    # the object of a struct local is loaded again where the borrow is taken (the load
                    # at the share may sit in a region that does not enclose the uses)
                    load = I.Instr('load', [flow.defs[obj].operands[0]], [I.Value(obj.type)])
                    _insert_before(self.fn, d, load)
                    obj = load.result
                d.op = 'field.list'
                d.operands = [obj]
                d.attrs = {'cls': X[1][0], 'name': X[1][1]}
        _delete(self.fn, s)
        self.alias_of[Dp] = X[1] if kind == 'P' else None
        self.alias_roots.add(self.root_of_target(X))
        self.note(s, 'rename' if kind == 'P' else 'field-borrow', differs)
        self.stats['renames' if kind == 'P' else 'field_borrows'] += 1

    def root_of_target(self, X):
        if X[0] == 'P':
            return 'Own(%s,%s)' % (self.fn.name, self.fn_place_name(X[1]))
        return 'Field(%s,%s)' % X[1]

    def fn_place_name(self, p):
        return E.place_names(self.fn).get(p, '?')

    # -- Rule M': the field takes the storage, the source's later uses name the field
    def move_then_borrow(self, flow, s, D, Xp, names):
        key, base, dref_def = D[1], D[2], D[3]
        if base not in self.fn.params:
            raise NeedsBox('%s: the object holding the list is not a parameter' % names)
        reach, U = self.reached_uses(flow, s, Xp, names)
        refs = self.refs_to_rewrite(flow, s, Xp, reach, U, names)
        self.check_field_borrow(flow, s, Xp, reach, key, names)
        for d, inside in refs:
            if any(c.op == 'return' for c in inside):
                raise NeedsBox('%s: a list a struct field holds is also returned' % names)
        differs = any(Xp in flow.writes[n] for n in reach if n is not s)
        if self.value and not differs:
            differs = self.field_write_seen(flow, reach, s, key, Xp)
        if self.value and differs:
            raise ValueDiffers('%s: a write through one name can be seen through the other' % names)
        for d, inside in refs:
            d.op = 'field.list'
            d.operands = [base]
            d.attrs = {'cls': key[0], 'name': key[1]}
        self.alias_roots.add('Field(%s,%s)' % key)
        self.note(s, 'move-borrow', differs)
        s.op = 'list.move'
        s.attrs = {}
        self.stats['field_moves'] += 1
        self.stats['field_borrows'] += 1

    def check_field_borrow(self, flow, s, borrower, reach, key, names):
        """B1 against a field: while `borrower` is live the field's list is neither replaced nor
        resized behind a lent view."""
        for n in reach:
            if n is s:
                continue
            if borrower not in flow.live_in[n] and borrower not in flow.uses[n]:
                continue
            if n.op in CALLS:
                if borrower in flow.live_in[n] and (flow.rebinds_field(n, key) or flow.spine_writes(n, key)):
                    raise NeedsBox('%s: a call may replace or resize the field list while the second name '
                                   'is in use' % names)
            elif flow.rebinds_field(n, key) and borrower in flow.live_out[n]:
                raise NeedsBox('%s: the field is reassigned while the second name is still used' % names)

    # ------------------------------------------------------------------ afterwards
    def fix_drops(self):
        """Renaming changes where a list dies: a drop the lowering placed at a name's last mention
        is wrong for the list that name now shares. Drops of the places involved are deleted while
        the list is live, or move to the place that really holds it."""
        if not self.alias_of:
            return
        flow = Flow(self.fn, self.program, self.summaries)
        involved = set(self.alias_of)
        for p in list(self.alias_of.values()):
            if p is not None:
                involved.add(p)
        for n in list(flow.nodes):
            if not (n.op == 'list.reset' and n.attrs.get('drop')):
                continue
            p = flow.place_of(n.operands[0])
            if p is None or p not in involved:
                continue
            after = flow.live_out[n]
            owner = p
            seen = set()
            while owner in self.alias_of and self.alias_of[owner] is not None and owner not in seen:
                seen.add(owner)
                owner = self.alias_of[owner]
            if p in after:
                _delete(self.fn, n)
            elif owner is not p:
                if owner in after:
                    _delete(self.fn, n)
                else:
                    ref = I.Instr('list.ref', [owner], [I.Value(owner.type.pointee)])
                    for r in _regions(self.fn):
                        for k, i in enumerate(r.instrs):
                            if i is n:
                                r.instrs.insert(k, ref)
                                n.operands = [ref.result]
                                break

    def check_loops(self, loops):
        """`for x in xs` was lowered as an indexed loop over a length read once: the body must not
        resize or replace that list, by any of its names or through a call."""
        if not loops:
            return
        defs = E.defs_of(self.fn)
        places = E.place_names(self.fn)
        for loop, base in loops:
            if loop not in list(I.walk(self.fn.body)):
                continue
            root = E._root(base, self.fn, defs)
            for ins in I.walk(loop.regions[0]):
                if ins.op in WRITE_OPS and ins.op not in ('list.set',) or ins.op in DST_OPS:
                    if ins.operands and E._root(ins.operands[0], self.fn, defs) in (root, 'Any'):
                        raise NeedsBox('a loop over a list whose body resizes or rebinds it (through another name)')
                    if ins.op == 'list.move' and E._root(ins.operands[1], self.fn, defs) in (root, 'Any'):
                        raise NeedsBox('a loop over a list whose body moves it away')
                if ins.op in CALLS and root.startswith('Field('):
                    eff = E.instr_effects(ins, self.fn, self.program, places, defs, self.summaries)
                    if eff.unknown or any(w in (('Spine(%s)' % root), ('Rebind(%s)' % root)) for w in eff.writes):
                        raise NeedsBox('a loop over a field list whose body calls code that may resize it')

    def downgrade_proofs(self):
        """Index proofs the legacy front end made by name (`nck`) assumed no other name resizes the
        list; on a shared list that is not so. Only the checked form is kept there."""
        if not self.alias_roots:
            return
        defs = E.defs_of(self.fn)
        for ins in I.walk(self.fn.body):
            if ins.op in ('list.get', 'list.set') and ins.attrs.get('mode') == 'nck' and not ins.attrs.get('iter'):
                if E._root(ins.operands[0], self.fn, defs) in self.alias_roots:
                    ins.attrs['mode'] = 'ck'


def resolve(fn, program, summaries=None, loops=(), value=False):
    """Resolve every `list.share` and `list.copy` in `fn`; raises NeedsBox (Rule X). Returns the
    Resolver (stats, W-ALIAS notes). `value`: value semantics (brace-syntax files, until S6): a share
    whose two names could tell the difference becomes a copy instead of a rename or a refusal."""
    r = Resolver(fn, program, summaries, value)
    return r.run(list(loops))
