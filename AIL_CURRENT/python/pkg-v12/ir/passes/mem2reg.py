"""mem2reg on structured regions (design §3: lower -> mem2reg -> ...).

Every `local.alloc` place whose only uses are as the place operand of `load`/`store` is promoted:
loads become the value last stored on the path, an `if` whose arms store a place yields its new
value as an extra result, and a `loop`/`for.range` whose body stores a place carries it as an
extra block argument (initial value: the value before the loop; each `continue` passes the
current value) and returns it as an extra result (each `break` passes the current value; a
`for.range` that runs out returns the carried value, as the emitter already does for carried
values). A place starts as zero, as a legacy local is declared (`T v = 0;`).

The result has no places left for scalars, so later passes (folding, ranges, LICM) see plain SSA
and the C emitter's locals become single-assignment temporaries plus loop-carried variables.
"""
from .. import ir as I


def _stored(region, promotable, out):
    for ins in I.walk(region):
        if ins.op == 'store' and ins.operands[0] in promotable:
            out.add(ins.operands[0])
    return out


class _Promoter(object):
    def __init__(self, fn, promotable, order):
        self.fn = fn
        self.promotable = promotable
        self.order = order                 # place -> index (deterministic ordering)
        self.replace = {}

    def sub(self, v):
        while v in self.replace:
            v = self.replace[v]
        return v

    def modified(self, ins):
        out = set()
        for r in ins.regions:
            _stored(r, self.promotable, out)
        return sorted(out, key=self.order.__getitem__)

    def region(self, region, env, loops, yield_places):
        kept = []
        for ins in region.instrs:
            ins.operands = [self.sub(v) for v in ins.operands]
            op = ins.op
            if op == 'local.alloc' and ins.results and ins.result in self.promotable:
                continue
            if op == 'load' and ins.operands[0] in self.promotable:
                self.replace[ins.result] = env[ins.operands[0]]
                continue
            if op == 'store' and ins.operands[0] in self.promotable:
                env[ins.operands[0]] = ins.operands[1]
                continue
            if op == 'if':
                self.do_if(ins, env, loops)
            elif op in I.LOOP_OPS:
                self.do_loop(ins, env, loops)
            elif op == 'yield':
                ins.operands = ins.operands + [env[p] for p in yield_places]
            elif op in ('break', 'continue'):
                loop, carried = loops[-1]
                ins.operands = ins.operands + [env[p] for p in carried]
            kept.append(ins)
        region.instrs = kept

    def do_if(self, ins, env, loops):
        mods = self.modified(ins)
        for r in ins.regions:
            self.region(r, dict(env), loops, mods)
        for p in mods:
            v = I.Value(p.type.pointee, hint=getattr(p, 'hint', None))
            ins.results.append(v)
            env[p] = v

    def do_loop(self, ins, env, loops):
        mods = self.modified(ins)
        body = ins.regions[0]
        ins.operands = ins.operands + [env[p] for p in mods]
        inner = dict(env)
        for p in mods:
            a = I.Value(p.type.pointee)
            body.args.append(a)
            inner[p] = a
        self.region(body, inner, loops + [(ins, mods)], ())
        for p in mods:
            v = I.Value(p.type.pointee)
            ins.results.append(v)
            env[p] = v


def run(fn):
    """Promote every promotable place of `fn` in place; returns the number promoted."""
    allocs = [ins for ins in fn.body.instrs if ins.op == 'local.alloc']
    if not allocs:
        return 0
    places = [ins.result for ins in allocs]
    bad = set()
    for ins in I.walk(fn.body):
        for k, v in enumerate(ins.operands):
            if v in places and not (ins.op in ('load', 'store') and k == 0):
                bad.add(v)
    promotable = set(p for p in places if p not in bad and p.type.pointee.is_scalar)
    if not promotable:
        return 0
    order = {p: k for k, p in enumerate(places)}
    env = {}
    zeros = []
    for ins in allocs:
        p = ins.result
        if p in promotable:
            t = p.type.pointee
            if t == I.TINT:
                z = I.Instr('const', [], [I.Value(I.I64)], {'value': 0})
                zf = I.Instr('tint.from', [z.result], [I.Value(I.TINT)], {})
                zeros.extend((z, zf))
                env[p] = zf.result
                continue
            z = I.Instr('const', [], [I.Value(t)], {'value': 0.0 if t.is_float else (False if t == I.I1 else 0)})
            zeros.append(z)
            env[p] = z.result
    promoter = _Promoter(fn, promotable, order)
    fn.body.instrs = zeros + fn.body.instrs
    promoter.region(fn.body, env, [], ())
    return len(promotable)
