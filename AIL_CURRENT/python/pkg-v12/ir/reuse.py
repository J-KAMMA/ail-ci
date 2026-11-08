"""rc4: Perceus reuse at the IR's object-allocation site (analysis and marking).

The IR's `obj.init` (lower.py) writes a freshly constructed class instance into a place. A
second `obj.init` on the same local place is the Perceus pair: the old instance is dropped by the
store that follows the new allocation, and when it is uniquely held its storage can be reused in
place for the new instance of the same size. `emit_c.py`'s `obj.init` hook asks this module
(`mark`) whether the instruction may take that fast path, and emits `ail_obj_reuse` before the
constructor when it may.

A pair is refused when:

* the function contains `try` -- a release and an allocation must not cross an exception boundary,
  and an unwind frame could release the reused storage twice;
* the class has a finaliser (`__del__`) -- CPython creates a real new object and runs it once;
* an argument depends on the old object (a `load` of the same place, directly or through other
  values), so the old object is still observed after the release;
* an argument depends on a call/comprehension -- the rule forbids crossing a call that may
  allocate, and a nested allocation would consume the parked storage first;
* the old value escapes through another name (`obj.copyref`, a return, or a call argument), so
  `rc == 1` can never hold (kept as a refused shape for the tests).

`AIL_RC_REUSE=0` turns the analysis off (the A/B switch and escape hatch).
"""
import os

from . import ir as I

_SWITCH = 'AIL_RC_REUSE'
_CALLS = frozenset(('call', 'obj.call', 'list.call', 'ba.call', 'call.indirect'))
_USED = [False]


def used():
    """Whether a reuse call was emitted in this compilation (the prelude is gated on it)."""
    return _USED[0]


def note_used():
    _USED[0] = True


def reset():
    _USED[0] = False


def enabled():
    """Whether reuse is on (`AIL_RC_REUSE=0` is the A/B switch and escape hatch)."""
    return os.environ.get(_SWITCH, '1').strip().lower() not in ('0', 'off', 'no', 'false')


def _has_try(fn):
    return any(ins.op == 'try' for ins in I.walk(fn.body))


def _finalised(fn):
    """Class names the emitter must not reuse for, from the function's own attributes.

    A class with a finaliser (`__del__`) never reaches this emitter: `pyfunc` keeps any class whose
    methods go beyond `__init__` on the general path ("built on the general path ... because dunder
    method Box.__del__"), so `mark` cannot see one. `test_ail_rc_reuse` pins that. The attribute is
    still honoured if a caller carries one, so the rule holds by construction rather than by
    relying on that confinement alone."""
    return set(fn.attrs.get('finalised') or ())


def mark(fn):
    """Mark every safe `obj.init` of `fn` with `attrs['reuse'] = True`; return the number."""
    if not enabled() or _has_try(fn):
        return 0
    insns = list(I.walk(fn.body))
    finalised = _finalised(fn)
    initialized, escaped = set(), set()
    tainted, has_call = {}, {}          # id(value) -> set(id(place)) / bool
    count = 0
    for ins in insns:
        args = [id(v) for v in ins.operands]
        places = set()
        call = ins.op in _CALLS
        for a in args:
            places |= tainted.get(a, set())
            call = call or has_call.get(a, False)
        if ins.op == 'load':
            places.add(id(ins.operands[0]))
        elif ins.op in ('obj.copyref', 'field.set', 'field.store', 'return') and places:
            escaped |= places
        elif ins.op in _CALLS and places:
            escaped |= places
        if ins.results:
            r = id(ins.results[0])
            tainted[r] = places
            has_call[r] = call
        if ins.op != 'obj.init':
            continue
        place = ins.operands[0]
        pid = id(place)
        cls = ins.attrs.get('cls')
        blocked = (pid in escaped or cls in finalised
                   or any(pid in tainted.get(id(a), ()) for a in ins.operands[1:])
                   or any(has_call.get(id(a), False) for a in ins.operands[1:]))
        if pid in initialized and not blocked:
            ins.attrs['reuse'] = True
            count += 1
        initialized.add(pid)
    return count


def pairs(fn):
    """The `obj.init` instructions of `fn` that a fresh `mark` would reuse (for reporting)."""
    mark(fn)
    return [ins for ins in I.walk(fn.body) if ins.op == 'obj.init' and ins.attrs.get('reuse')]
