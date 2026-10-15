"""The per-function switch between the IR path and the legacy emitter (design §4.1).

    AIL_IR unset or 0   legacy emitter only (the IR is never imported; C is byte-identical)
    AIL_IR=1            every function in the S0 subset is lowered, verified and emitted from the
                        IR; anything else, and any IR failure, falls back to the legacy emitter
    AIL_IR=verify       as 1, plus a print/parse/print round trip of every IR function, and an IR
                        failure (verifier error, emitter error, signature mismatch) raises instead
                        of falling back -- for tests
    AIL_IR_FUNCS=a,b    optional allowlist of source function names
    AIL_IR_STATS=path   append one JSON line per compiled function: {"fn", "sym", "path", "reason"}

The legacy emitter always runs first and stays the source of the C boundary: the IR function
keeps its symbol, linkage and signature (checked textually), and its runtime needs are merged
into the legacy context, so the rest of the program is compiled exactly as before.
"""
import inspect
import json
import os
import re

from . import ir as I
from . import emit_c, lower, passes, text, verify

STATS = []
# Effect summaries of the functions already compiled through the IR in this build, by C symbol: a
# call to one of them is no longer an unknown effect (whole-program summaries; a function the
# legacy path compiled, or one compiled later, stays unknown).
SUMMARIES = {}
_PROGRAM = [None]        # the program SUMMARIES belong to: its signature table (`ctx.funcs`, one
                         # object per compiled program), held so its identity cannot be reused


def _summaries(ctx):
    funcs = getattr(ctx, 'funcs', None)
    if _PROGRAM[0] is not funcs:
        _PROGRAM[0] = funcs
        SUMMARIES.clear()
    return SUMMARIES


def facts_for(P, fn, ctx):
    """Whole-program facts the passes may use for `fn`."""
    return {'summaries': _summaries(ctx)}


def mode():
    value = os.environ.get('AIL_IR', '0').strip().lower()
    return '' if value in ('', '0', 'off', 'no') else value


def _record(fn_name, sym, path, reason, ctx, stats=None):
    entry = {'fn': fn_name, 'sym': sym, 'path': path, 'reason': reason}
    if stats:
        entry['passes'] = stats
    STATS.append(entry)
    target = os.environ.get('AIL_IR_STATS')
    if target:
        with open(target, 'a') as handle:
            handle.write(json.dumps(entry) + '\n')
    if path == 'ir' and ctx is not None and isinstance(getattr(ctx, 'shortcuts', None), list):
        ctx.shortcuts.append({'kind': 'ir_s0', 'detail': fn_name,
                              'evidence': 'lowered, verified and emitted through the IR (stage S0)'})


_CLEANUP_HEAD = re.compile(r'static void (?:ail_unwind_|_ail_finally_release_)\w+\(void \*\*p\) \{[^\n]*\}\n')


def _only_cleanup_before(generated, sig):
    """Whether the legacy text is the function itself, preceded at most by its unwind/finally
    release helpers. Those free what the legacy body allocated (e.g. a string arena it opens
    for a numeric function) when an exception unwinds through it; the IR body allocates nothing,
    links no cleanup frame, and drops them with the legacy body."""
    pos = 0
    while True:
        m = _CLEANUP_HEAD.match(generated, pos)
        if not m:
            break
        pos = m.end()
    return generated.startswith(sig + ' {\n', pos)


def apply(P, args, kwargs, result):
    """`result` is the legacy `(sig, generated, ctx)` of `_one_function(*args, **kwargs)`;
    returns it unchanged or with `generated` replaced by the IR emitter's C."""
    current = mode()
    if not current:
        return result
    sig, generated, ctx = result
    bound = inspect.signature(P._one_function_numeric_impl).bind(*args, **kwargs).arguments
    fn, cname = bound['fn'], bound['cname']
    recursive = bool(bound.get('recursive', False))
    try:
        if bound.get('is_method'):
            raise lower.NotS0('a method')
        allow = os.environ.get('AIL_IR_FUNCS')
        if allow and fn.name not in allow.split(','):
            raise lower.NotS0('not in AIL_IR_FUNCS')
        function, program = lower.lower(P, fn, ctx, sig, recursive, cname)
        if not _only_cleanup_before(generated, sig):
            raise lower.NotS0('the legacy path emits helpers around this function')
        verify.check(function, program)
        checker = (lambda f: verify.check(f, program)) if current == 'verify' else None
        pass_stats = passes.optimize(function, program, facts_for(P, fn, ctx), checker)
        verify.check(function, program)
        if current == 'verify':
            printed = text.print_function(function)
            again = text.parse_function(printed)
            if text.print_function(again) != printed:
                raise I.IRError('print/parse/print round trip changed the text of %s' % fn.name)
            verify.check(again, program)
        new_sig, body, needs = emit_c.emit_function(function)
        if new_sig != sig:
            raise I.IRError('IR signature %r differs from the legacy %r' % (new_sig, sig))
        if needs['need'] and ctx.need is None:
            raise lower.NotS0('checked helpers in a non-strict build')
    except lower.NotS0 as reason:
        _record(fn.name, cname, 'legacy', str(reason), ctx)
        return result
    except Exception as error:
        if current == 'verify':
            raise
        _record(fn.name, cname, 'legacy', 'IR failure: %s: %s' % (type(error).__name__, error), ctx)
        return result
    ctx.parts.update(needs['parts'])
    ctx.floor.update(needs['floor'])
    if ctx.need is not None:
        ctx.need.update(needs['need'])
    _record(fn.name, cname, 'ir', '', ctx, pass_stats)
    if function.effects is not None:
        _summaries(ctx)[cname] = function.effects
    return sig, body, ctx
