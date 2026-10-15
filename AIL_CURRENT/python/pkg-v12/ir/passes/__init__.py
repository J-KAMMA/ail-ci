"""IR passes of stage S1 (design §3 pass order, restricted to what S1 lowers):

    mem2reg -> simplify (fold, CSE, DCE) -> ranges (overflow and index checks)
            -> licm (pure LICM, span hoisting, loop versioning) -> ranges -> simplify

`optimize(fn, program)` runs them on one lowered function. `AIL_IR_PASSES` (comma list, default
all) selects passes, for tests and for pricing each pass separately.
"""
import os

from .. import effects as E
from . import mem2reg, simplify, ranges, licm

ALL = ('mem2reg', 'simplify', 'ranges', 'licm')


def enabled():
    raw = os.environ.get('AIL_IR_PASSES')
    if raw is None:
        return set(ALL)
    return set(p.strip() for p in raw.split(',') if p.strip())


def optimize(fn, program, facts=None, check=None):
    """Optimise `fn` in place. `facts` carries whole-program knowledge (ranges of parameters,
    effect summaries of other IR functions); `check(fn)` (optional) runs after every pass."""
    facts = facts or {}
    on = enabled()
    stats = {}

    def after():
        if check is not None:
            check(fn)
    if 'mem2reg' in on:
        stats['promoted'] = mem2reg.run(fn)
        after()
    if 'simplify' in on:
        simplify.run(fn)
        after()
    if 'ranges' in on:
        stats.update(ranges.run(fn, facts))
        after()
    if 'licm' in on and 'mem2reg' in on:
        stats.update(licm.run(fn, facts.get('summaries')))
        after()
        if 'ranges' in on:
            second = ranges.run(fn, facts)
            stats['ck_ssa_proven'] = stats.get('ck_ssa_proven', 0) + second['ck_ssa_proven']
            stats['idx_ssa_proven'] = stats.get('idx_ssa_proven', 0) + second['idx_ssa_proven']
            after()
    if 'simplify' in on:
        simplify.run(fn)
        after()
    E.summarize_program(program)
    return stats
