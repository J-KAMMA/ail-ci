"""Dominated duplicate element reads.

A second `span.get` / `list.get` / `bytes.get` of the same container at the same index value, when the first one
dominates it and nothing that can change a list or a span's memory runs in between, cannot fail (the first one
passed the same test on the same length) and returns the same element: its result is the first one's, and the
read goes away, bounds test and all.

What can change what a read sees or tests: anything that writes or resizes a list, calls out, or may do either
(`span.set`, `list.set/push/pop/..`, `call`, `rt`, `print`, owned-list operations, `rec.*`, `dict.*`, a store to a
module variable or a struct field, an unknown op). The rule is by whitelist: only the ops below are known to
leave every list, span and bytes value as it was; any other op between the two reads ends the first read's
availability (so a new op is never silently assumed harmless). A nested `if` or loop is inspected as a whole; one
that contains a non-whitelisted op ends the availability before it (a loop: also inside its body, for the next
iteration). Reads made inside an `if` arm or a loop body are not available after it.
"""
from .. import ir as I

# ops that neither write a list/span/bytes nor resize one, nor call anything
_HARMLESS = frozenset([
    'const', 'add', 'sub', 'mul', 'neg', 'and', 'or', 'xor', 'inv', 'shl', 'shr', 'floordiv', 'floormod', 'pow',
    'fadd', 'fsub', 'fmul', 'fdiv', 'ffloordiv', 'ffloormod', 'fpow', 'fneg', 'fabs', 'zext', 'sitofp', 'fptosi',
    'select', 'load', 'field.get', 'field.list', 'list.ref', 'list.len', 'span.of', 'span.len',
    'bytes.len', 'bytes.get', 'span.get', 'list.get', 'spec.get', 'str.lit', 'bytes.lit',
    'yield', 'break', 'continue', 'return', 'raise', 'unreachable',
] + ['cmp.' + p for p in I.CMP_PREDICATES] + [n for n in I.OPS if n.startswith('tint.')])

_READS = ('span.get', 'list.get', 'bytes.get')


def _kills(region):
    """Whether anything in `region` (nested regions included) is not known to leave memory alone."""
    for ins in I.walk(region):
        if _kill(ins):
            return True
    return False


def _kill(ins):
    """Whether this one op (not its nested regions) is not known to leave every list, span and bytes value alone."""
    if ins.op == 'store':
        # a store to a scalar place cannot touch a list; a store of anything else may rebind one
        return ins.operands[1].type not in (I.I64, I.F64, I.I1, I.TINT)
    return ins.op not in _HARMLESS and ins.op not in ('if', 'loop', 'for.range')


def _key(ins):
    return (ins.op, ins.operands[0], ins.operands[1])


def _scan(region, avail, replace):
    removed = 0
    kept = []
    for ins in region.instrs:
        ins.operands = [replace.get(v, v) for v in ins.operands]
        op = ins.op
        if op in _READS and ins.results:
            key = _key(ins)
            first = avail.get(key)
            if first is not None:
                replace[ins.results[0]] = first
                removed += 1
                continue
            avail[key] = ins.results[0]
        elif op == 'if':
            dirty = any(_kills(r) for r in ins.regions)
            for r in ins.regions:
                removed += _scan(r, dict(avail), replace)
            if dirty:
                avail.clear()
        elif op in I.LOOP_OPS:
            if _kills(ins.regions[0]):
                avail.clear()
                removed += _scan(ins.regions[0], {}, replace)
            else:
                removed += _scan(ins.regions[0], dict(avail), replace)
        elif _kill(ins):
            avail.clear()
        kept.append(ins)
    region.instrs = kept
    return removed


def run(fn):
    """Remove the dominated duplicate reads of `fn`; returns how many."""
    replace = {}
    n = _scan(fn.body, {}, replace)
    if n:
        for ins in I.walk(fn.body):
            ins.operands = [replace.get(v, v) for v in ins.operands]
            while any(v in replace for v in ins.operands):
                ins.operands = [replace.get(v, v) for v in ins.operands]
    return n
