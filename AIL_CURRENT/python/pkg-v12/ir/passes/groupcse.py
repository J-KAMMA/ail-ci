"""One index check per parallel-list group (bce s5).

`facts['fields']['groups']` (bce s4) names sets of lists that always have the same length: the
members of a struct (a `field.list o.f`) or a function's own list locals.  A checked access
`Y[i]` to another member `g` of a group whose member `f` was already read at the same SSA index
`i` cannot be out of range at `i`: the first access either raised there, or every member was at
least as long.  The first access is rewritten into

    %n = list.len X            (or span.len, for a span over the list)
    %j = idx.norm %i, %n {kind}  -- normalises a negative index, raising exactly as X's access did
    ... X[%j] unchecked ...

and every later `Y[i]` becomes `Y[%j]` unchecked.  `%j` is in `[0, n)` and the members only ever
grow, so it stays in range; for a negative `%i` a growing group would put the element elsewhere,
so there the rewrite requires that nothing between the accesses can change a length (a group
block, a call whose summary writes the struct's lists, or an unknown call), unless the index is
a non-negative constant.

The first access keeps its error, its message and its place: `idx.norm` raises where the access
would have.  An `X` no `Y` uses is left alone (no C change without a saving).  Runs only when
`bce_enabled()`; `AIL_BCE=0` leaves the C identical to the base.
"""
from .. import effects as E
from .. import ir as I

ACCESS = ('list.get', 'list.set', 'span.get', 'span.set')
LOOPS = ('loop', 'for.range')


class _Candidate(object):
    __slots__ = ('gid', 'x_ins', 'x_region', 'kind', 'base', 'is_span', 'index', 'j', 'known_nonneg')

    def __init__(self, gid, x_ins, x_region, kind, base, is_span, index):
        self.gid = gid
        self.x_ins = x_ins
        self.x_region = x_region
        self.kind = kind
        self.base = base
        self.is_span = is_span
        self.index = index
        self.j = None
        self.known_nonneg = False


class GroupCSE(object):
    def __init__(self, fn, facts):
        self.fn = fn
        self.facts = facts or {}
        self.groups = (self.facts.get('fields') or {}).get('groups') or []
        self.summaries = self.facts.get('summaries') or {}
        self.defs = {r: ins for ins in I.walk(fn.body) for r in ins.results}
        self.field_groups = {}
        self.local_groups = {}
        for gid, group in enumerate(self.groups):
            if group.get('struct'):
                for member in group['members']:
                    self.field_groups[(group['struct'], member)] = gid
            elif group.get('fn') == fn.name:
                for member in group['members']:
                    self.local_groups[member] = gid
        self.rewritten = 0

    # ------------------------------------------------------------------ helpers
    def grow_only(self, gid):
        return bool(self.groups[gid].get('grow_only'))

    def _root(self, base):
        """(group id, owner SSA value, member) of a list value, or None."""
        d = self.defs.get(base)
        if d is None:
            return None
        if d.op == 'field.list':
            gid = self.field_groups.get((d.attrs.get('cls'), d.attrs.get('name')))
            if gid is not None and d.operands:
                return gid, d.operands[0], d.attrs.get('name')
            return None
        if d.op == 'list.ref':
            place = self.defs.get(d.operands[0])
            if place is not None and place.op == 'local.alloc':
                gid = self.local_groups.get(place.attrs.get('name'))
                if gid is not None:
                    return gid, d.operands[0], place.attrs.get('name')
        return None

    def access(self, ins):
        """(group id, owner, index, base, is_span) of an access, else None."""
        if ins.op not in ACCESS:
            return None
        base = ins.operands[0]
        is_span = ins.op.startswith('span.')
        if is_span:
            d = self.defs.get(base)
            if d is None or d.op != 'span.of':
                return None
            base = d.operands[0]
        root = self._root(base)
        if root is None:
            return None
        gid, owner, _member = root
        return gid, owner, ins.operands[1], base, is_span

    def _member_loc(self, gid, member):
        group = self.groups[gid]
        if group.get('struct'):
            return 'Field(%s,%s)' % (group['struct'], member)
        return 'Own(%s,%s)' % (self.fn.name, member)

    def _writes_group(self, eff, gid):
        members = self.groups[gid]['members']
        for w in eff.writes:
            if 'Spine(' not in w and 'Rebind(' not in w:
                continue
            for member in members:
                if self._member_loc(gid, member) in w:
                    return True
        return False

    def changes_length(self, ins, gid):
        """Whether `ins` may change the length of the group `gid`."""
        if ins.op == 'call':
            eff = self.summaries.get(ins.attrs.get('callee'))
            if eff is None or eff.unknown:
                return True
            return self._writes_group(eff, gid)
        eff = E.instr_effects(ins, self.fn, None, None, self.defs, self.summaries)
        return self._writes_group(eff, gid)

    def _region_changes(self, gid, region):
        for ins in region.instrs:
            if self.changes_length(ins, gid):
                return True
            for child in ins.regions:
                if self._region_changes(gid, child):
                    return True
        return False

    def _nonneg(self, index):
        d = self.defs.get(index)
        if d is not None and d.op == 'const':
            c = d.attrs.get('value')
            return isinstance(c, int) and not isinstance(c, bool) and c >= 0
        return False

    def _cross_ok(self, cand):
        """Whether the candidate survives a length change of the group between X and Y.

        A grow-only group only appends, but a *negative* index `i` normalises against X's length
        (`j = len_X + i`); if the lists grew before Y, CPython's `Y[i]` names `len_Y + i`, a
        different element.  So crossing a length change needs a provably non-negative index (j
        is then `i` itself).  Where the index may be negative, callers fall back to requiring
        that nothing between X and Y changes the group's length."""
        return self.grow_only(cand.gid) and cand.known_nonneg

    def _materialize(self, cand):
        """Rewrite `X[i]` into `j = idx.norm(i, len X)` + unchecked `X[j]`."""
        ins = cand.x_ins
        region = cand.x_region
        if cand.is_span:
            n = I.Value(I.I64, hint='gn')
            len_ins = I.Instr('span.len', [ins.operands[0]], [n])
        else:
            # `raw`: the count the checked accessor's fast path reads, without the slow-path
            # layout validation (an in-range access never runs it either)
            n = I.Value(I.I64, hint='gn')
            len_ins = I.Instr('list.len', [cand.base], [n], {'raw': True})
        j = I.Value(I.I64, hint='gj')
        norm = I.Instr('idx.norm', [cand.index, n], [j], {'kind': cand.kind})
        at = region.instrs.index(ins)
        region.instrs[at:at] = [len_ins, norm]
        ins.operands[1] = j
        ins.attrs['mode'] = 'nck'
        cand.j = j
        self.rewritten += 1

    # ------------------------------------------------------------------ walking
    def scan(self, region, avail):
        i = 0
        while i < len(region.instrs):
            ins = region.instrs[i]
            if ins.op in ACCESS and ins.attrs.get('mode') in ('ck', 'nck'):
                found = self.access(ins)
                if found is not None:
                    gid, owner, index, base, is_span = found
                    key = (gid, id(owner), id(index))
                    cand = avail.get(key)
                    if cand is not None and cand.x_ins is not ins:
                        if cand.j is None:
                            self._materialize(cand)
                        ins.operands[1] = cand.j
                        ins.attrs['mode'] = 'nck'
                    elif cand is None:
                        kind = 'read' if ins.op.endswith('.get') else 'store'
                        cand = _Candidate(gid, ins, region, kind, base, is_span, index)
                        if ins.attrs.get('mode') == 'nck':
                            # proven in [0, len) already: reuse its index as it stands
                            cand.j = index
                            cand.known_nonneg = True
                        else:
                            cand.known_nonneg = self._nonneg(index)
                        avail[key] = cand
            if ins.regions:
                for child in ins.regions:
                    keep = {}
                    for key, cand in avail.items():
                        if ins.op == 'if':
                            keep[key] = cand
                        elif ins.op in LOOPS and (self._cross_ok(cand)
                                                  or not self._region_changes(cand.gid, child)):
                            keep[key] = cand
                    self.scan(child, keep)
                # a length change in an arm or body means the group no longer tells the truth
                survivors = {}
                for key, cand in avail.items():
                    changed = any(self._region_changes(cand.gid, r) for r in ins.regions)
                    if not changed or self._cross_ok(cand):
                        survivors[key] = cand
                avail = survivors
            for key, cand in list(avail.items()):
                if cand.x_ins is ins:
                    continue
                if self.changes_length(ins, cand.gid) and not self._cross_ok(cand):
                    del avail[key]
            i = region.instrs.index(ins) + 1

    def run(self):
        if not self.groups:
            return 0
        self.scan(self.fn.body, {})
        return self.rewritten


def run(fn, facts=None):
    """Rewrite parallel-list group accesses; returns the number of checks replaced."""
    return GroupCSE(fn, facts).run()
