"""Input windows (stage S4c-1, docs/design/IR_OWNERSHIP_DESIGN_v2.md section 16).

`data = read_stdin_bytes(n)` / `read_bytes(path)` followed by one forward scan of `data` -- a loop whose
carried position `i` is a lower bound of every index the loop (and everything after it) touches -- holds
the whole input in memory for the rest of the function. This pass turns such a read into a window
(`read_stdin_win` / `read_bytes_win`: a read-only mapping when the input is a regular file, the legacy
read otherwise) and puts `win_release(i)` at the top of each iteration: the pages behind `i` are given
back (`madvise(MADV_DONTNEED)`; a later touch reloads them from the page cache, so a wrong guess costs
time, never a different answer).

The proof that `i` bounds the scan is a greatest fixpoint over the loop body. A value is "at least `i`"
(G) when it is `i`, `len(data)` (an index at or past it touches nothing), `v + k` (k a constant >= 0) of
such a value, a `select`/`if` of such values, an induction variable whose start is, or a loop-carried value
whose start and every `continue` are. The result of `data.find(x, start)` with `start` in G is G or -1 (N);
inside the branch of `if r < 0` (and the like) that tests it, it is G. That is the shape of the usual
line scan: `e = data.find(b"\\n", pos); if e < 0: e = n; pos = e + 1`.

A read is windowed only when (all of):
  * it is executed once (not in a loop), stored to a local place that is never stored again;
  * every use of the loaded view is `bytes.len` (touches no memory), `bytes.get`, `bytes_slice`,
    `bytes_find_range`/`bytes_rfind_range` (as the haystack), and the views those produce are only
    measured, indexed, searched, converted, appended or written (never stored, carried, passed to a
    call or returned);
  * all the touches are inside one loop whose first i64 carried value (or induction variable) bounds them
    all, and which carries it monotonically;
  * for a file (`read_bytes`): that loop calls no function (nothing in it can write the file that the
    pages are read back from).
"""
import os

from .. import ir as I

_READS = {'read_stdin_bytes': 'read_stdin_win', 'read_bytes': 'read_bytes_win'}
_LOOPS = ('loop', 'for.range')
_FINDS = ('bytes_find_range', 'bytes_rfind_range')
# runtime entries that read a bytes operand (as a view) once and keep no reference to it
_TERMINAL = ('bytes_to_int', 'bytes_cat', 'write_stdout_bytes', 'bytes_decode') + _FINDS


class _Abort(Exception):
    pass


def _why(text):
    """Why a read was not windowed: appended to the file named by AIL_IR_WINDOW_DEBUG (tests, pricing)."""
    path = os.environ.get('AIL_IR_WINDOW_DEBUG')
    if path:
        with open(path, 'a') as f:
            f.write('window: %s\n' % text)


class _Index(object):
    def __init__(self, fn):
        self.uses = {}          # value -> [(instr, operand index)]
        self.res = {}           # value -> (instr, result index)
        self.arg = {}           # value -> (owner instr, argument index)
        self.encl = {}          # instr -> enclosing loops, outermost first
        self.breaks = {}        # loop -> [break instrs]
        self.conts = {}         # loop -> [continue instrs]
        self.defs = {}          # value -> defining instr (results only)
        self.ctx = {}           # instr -> values known to be >= 0 where it runs (from enclosing `if` tests)
        self._walk(fn.body, (), None, frozenset())

    def _walk(self, region, loops, owner, ctx):
        for k, a in enumerate(region.args):
            self.arg[a] = (owner, k)
        for ins in region.instrs:
            self.encl[ins] = loops
            self.ctx[ins] = ctx
            for k, v in enumerate(ins.operands):
                self.uses.setdefault(v, []).append((ins, k))
            for k, r in enumerate(ins.results):
                self.res[r] = (ins, k)
                self.defs[r] = ins
            if ins.op == 'break':
                self.breaks.setdefault(loops[-1], []).append(ins)
            elif ins.op == 'continue':
                self.conts.setdefault(loops[-1], []).append(ins)
            for b, r in enumerate(ins.regions):
                inner = ctx
                if ins.op == 'if':
                    x = self._nonneg_in(ins.operands[0], b)
                    if x is not None:
                        inner = ctx | {x}
                self._walk(r, loops + (ins,) if ins.op in _LOOPS else loops, ins, inner)

    def _nonneg_in(self, cond, branch):
        """The value that `cond` tells is >= 0 in the branch (0: then, 1: else), if it is a test of one against 0/-1."""
        d = self.defs.get(cond)
        if d is None or not d.op.startswith('cmp.'):
            return None
        pred = d.op[4:]
        x, k = d.operands
        if x.type != I.I64 or k.type != I.I64:
            return None
        kv = self.const(k)
        if not isinstance(kv, int):
            return None
        if kv == 0 and ((pred == 'lt' and branch == 1) or (pred == 'ge' and branch == 0)):
            return x
        if kv == -1 and ((pred == 'le' and branch == 1) or (pred == 'gt' and branch == 0)
                         or (pred == 'ne' and branch == 0) or (pred == 'eq' and branch == 1)):
            return x
        return None

    def const(self, v):
        d = self.defs.get(v)
        if d is not None and d.op == 'const' and not isinstance(d.attrs['value'], bool):
            return d.attrs['value']
        return None


def _touches(info, view, out, place):
    """Collect (first index touched, the touching instruction) for every use of the whole buffer `view` into
    `out`; raise _Abort for a use the pass does not understand."""
    for ins, k in info.uses.get(view, ()):
        op = ins.op
        if op == 'bytes.len':
            continue
        if op == 'bytes.get' and k == 0:
            out.append((ins.operands[1], ins))
            continue
        if op == 'rt':
            callee = ins.attrs.get('callee')
            if callee == 'bytes_slice' and k == 0:
                out.append((ins.operands[1], ins))
                _derived(info, ins.result, set(), place)
                continue
            if callee in _FINDS and k == 0:
                out.append((ins.operands[2], ins))
                continue
        raise _Abort('use %s of the buffer' % op)


def _derived(info, view, seen, place):
    """A part of the buffer: it may only be consumed in place, or kept in a local bytes place (a `line = data[i:j]`)
    whose own reads are consumed in place. (A part read in a later iteration than the one that made it is a touch
    behind the position; that costs a reload, not a wrong answer, and the loops of this corpus do not.)"""
    if view in seen:
        return
    seen.add(view)
    for ins, k in info.uses.get(view, ()):
        op = ins.op
        if op == 'store' and k == 1 and ins.operands[0] is not place and ins.operands[0].type == I.place(I.BYTES):
            for u, j in info.uses.get(ins.operands[0], ()):
                if u.op == 'load' and j == 0:
                    _derived(info, u.result, seen, place)
                elif not (u.op == 'store' and j == 0):
                    raise _Abort('use %s of a place that holds a part of the buffer' % u.op)
            continue
        if op in ('bytes.len', 'bytes.get') and k == 0:
            continue
        if op == 'ba.extend' and k == 1:
            continue
        if op == 'rt':
            callee = ins.attrs.get('callee')
            if callee == 'bytes_slice' and k == 0:
                _derived(info, ins.result, seen, place)
                continue
            if callee in _TERMINAL:
                continue
        raise _Abort('use %s of a part of the buffer' % op)


def _bounded_by(info, loop, c, touches, lens):
    """Whether every `touches` (value, instruction) is >= `c` (the loop's carried position at the start
    of the iteration) or past the end of the buffer, and the loop carries `c` monotonically."""
    region = loop.regions[0]
    cand = set()
    finds = set()
    for ins in I.walk(region):
        for r in ins.results:
            if r.type == I.I64:
                (finds if ins.op == 'rt' and ins.attrs.get('callee') in _FINDS else cand).add(r)
        for sub in ins.regions:
            for a in sub.args:
                if a.type == I.I64:
                    cand.add(a)
    for a in region.args:
        if a.type == I.I64:
            cand.add(a)
    good = set(cand)
    good.add(c)
    good.update(lens)
    neg = set()                 # find results whose start is in `good`: -1 or in `good`

    def ok(v, ctx=frozenset()):
        return v in good or (v in neg and v in ctx)

    def nonneg_const(v):
        k = info.const(v)
        return isinstance(k, int) and k >= 0

    def holds(v):
        if v is c or v in lens:
            return True
        if v in info.arg:
            owner, k = info.arg[v]
            if owner is None or owner.op not in _LOOPS or owner is loop:
                return False
            ctx = info.ctx[owner]
            if owner.op == 'loop':
                return (ok(owner.operands[k], ctx)
                        and all(ok(x.operands[k], info.ctx[x]) for x in info.conts.get(owner, ())))
            if k == 0:
                step = info.const(owner.operands[2])
                return ok(owner.operands[0], ctx) and isinstance(step, int) and step > 0
            return (ok(owner.operands[3 + k - 1], ctx)
                    and all(ok(x.operands[k - 1], info.ctx[x]) for x in info.conts.get(owner, ())))
        ins = info.defs.get(v)
        if ins is None:
            return False
        ctx = info.ctx[ins]
        k = info.res[v][1]
        if ins.op == 'add':
            a, b = ins.operands
            return (ok(a, ctx) and nonneg_const(b)) or (ok(b, ctx) and nonneg_const(a))
        if ins.op == 'select':
            return ok(ins.operands[1], ctx) and ok(ins.operands[2], ctx)
        if ins.op == 'if':
            for r in ins.regions:
                if r.instrs and r.instrs[-1].op == 'yield' and not ok(r.instrs[-1].operands[k], info.ctx[r.instrs[-1]]):
                    return False
            return True
        if ins.op == 'loop':
            return all(ok(x.operands[k], info.ctx[x]) for x in info.breaks.get(ins, ()))
        if ins.op == 'for.range':
            return (ok(ins.operands[3 + k], ctx)
                    and all(ok(x.operands[k], info.ctx[x]) for x in info.conts.get(ins, ()))
                    and all(ok(x.operands[k], info.ctx[x]) for x in info.breaks.get(ins, ())))
        return False

    def find_ok(r):
        ins = info.defs[r]
        return ok(ins.operands[2], info.ctx[ins])

    changed = True
    while changed:
        changed = False
        neg = set(r for r in finds if find_ok(r))
        for v in list(good):
            if v is not c and v not in lens and not holds(v):
                good.discard(v)
                changed = True
    if not all(ok(idx, info.ctx[ins]) for idx, ins in touches):
        return False
    if loop.op == 'loop':
        pos = region.args.index(c)
        return all(ok(x.operands[pos], info.ctx[x]) for x in info.conts.get(loop, ()))
    step = info.const(loop.operands[2])
    return c is region.args[0] and isinstance(step, int) and step > 0


def _plan(info, fn, read):
    """(loop, position value) for the read's window, or None."""
    top = fn.body.instrs
    users = info.uses.get(read.result, ())
    if len(users) != 1 or users[0][0].op != 'store' or users[0][1] != 1 or users[0][0] not in top:
        _why('the read is not stored once at the top of the function')
        return None
    place = users[0][0].operands[0]
    if place.type != I.place(I.BYTES):
        _why('not a bytes place')
        return None
    touches = []
    lens = set()
    try:
        for ins, k in info.uses.get(place, ()):
            if ins.op == 'store' and k == 0:
                if ins is not users[0][0]:
                    _why('the place is stored again')
                    return None
            elif ins.op == 'load' and k == 0:
                _touches(info, ins.result, touches, place)
                for u, j in info.uses.get(ins.result, ()):
                    if u.op == 'bytes.len':
                        lens.add(u.result)
            else:
                _why('the place is used by %s' % ins.op)
                return None
    except _Abort as e:
        _why('%s' % e)
        return None
    if not touches:
        return None
    # the loops that enclose every touch
    chains = [info.encl[ins] for _, ins in touches]
    common = []
    for level in zip(*chains):
        if all(level[0] is x for x in level):
            common.append(level[0])
        else:
            break
    for loop in common:
        region = loop.regions[0]
        cands = [region.args[0]] if loop.op == 'for.range' else list(region.args)
        for c in cands:
            if c.type != I.I64:
                continue
            if _bounded_by(info, loop, c, touches, lens):
                if read.attrs['callee'] == 'read_bytes' and any(i.op == 'call' for i in I.walk(region)):
                    continue
                return loop, c
    _why('no loop bounds the scan')
    return None


def run(fn):
    """Window every read of `fn` that qualifies; returns how many."""
    info = _Index(fn)
    reads = [ins for ins in fn.body.instrs
             if ins.op == 'rt' and ins.attrs.get('callee') in _READS]
    made = 0
    for read in reads:
        plan = _plan(info, fn, read)
        if plan is None:
            continue
        loop, c = plan
        made += 1
        read.attrs['win'] = made
        read.attrs['callee'] = _READS[read.attrs['callee']]
        rel = I.Instr('rt', [c], [], {'callee': 'win_release', 'win': made})
        loop.regions[0].instrs.insert(0, rel)
    return made
