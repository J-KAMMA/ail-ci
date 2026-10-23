"""The per-function switch between the IR path and the legacy emitter (design §4.1).

    AIL_IR=0 (off/no)   legacy emitter only (the IR is never imported; C is byte-identical to the
                        pre-IR-default build); the opt-out
    AIL_IR unset or 1   (the default since 2026-10-19) every function in the S0 subset is lowered, verified and emitted from the
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
from . import emit_c, lower, passes, text, verify, walias

STATS = []
# Effect summaries of the functions already compiled through the IR in this build, by C symbol: a
# call to one of them is no longer an unknown effect (whole-program summaries; a function the
# legacy path compiled, or one compiled later, stays unknown).
SUMMARIES = {}
# C symbols of the functions already compiled through the IR that have an exception entry point
# (`<sym>__ir`, S2): an IR caller compiled later calls that entry and checks `ail_pending`.
PENDING = set()
# C symbols of the IR functions compiled so far that return a list by value (`<sym>__irl`, S3b): an IR
# caller compiled later adopts the struct without the copy through the runtime's spill slot.
LISTVAL = set()
_PROGRAM = [None]        # the program SUMMARIES belong to: its signature table (`ctx.funcs`, one
                         # object per compiled program), held so its identity cannot be reused


def _summaries(ctx):
    funcs = getattr(ctx, 'funcs', None)
    if _PROGRAM[0] is not funcs:
        _PROGRAM[0] = funcs
        SUMMARIES.clear()
        PENDING.clear()
        LISTVAL.clear()
    return SUMMARIES


def facts_for(P, fn, ctx):
    """Whole-program facts the passes may use for `fn`."""
    return {'summaries': _summaries(ctx)}


def checked_exceptions():
    """AIL_IR_EXC=checked: exceptions leave IR functions as checked return values (design 2.8);
    anything else (the default): as the legacy path raises them, by longjmp. See design doc 11."""
    return os.environ.get('AIL_IR_EXC', 'longjmp').strip().lower() == 'checked'


def mode():
    value = os.environ.get('AIL_IR', '1').strip().lower()
    if value == '':
        value = '1'                  # unset or empty: the default, the IR
    return '' if value in ('0', 'off', 'no', 'false') else value


def _record(fn_name, sym, path, reason, ctx, stats=None, extra=None):
    entry = {'fn': fn_name, 'sym': sym, 'path': path, 'reason': reason}
    if stats:
        entry['passes'] = stats
    if extra:
        entry.update(extra)
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


def _w_alias_shortcuts(ctx, fn_name, notes):
    if isinstance(getattr(ctx, 'shortcuts', None), list):
        for w in notes:
            if w.get('differs'):
                ctx.shortcuts.append({'kind': 'W-ALIAS', 'detail': '%s: `%s = %s` at line %s' % (
                    fn_name, w.get('dst'), w.get('src'), w.get('line')),
                    'evidence': 'one list with two names, and a name is written while the other is read '
                                'afterwards: Python semantics (the legacy emitter copies here)'})


def _legacy_walias(P, fn, ctx):
    """W-ALIAS sites of a function that stays on the legacy emitter (syntactic scan, walias.py)."""
    try:
        notes = walias.scan(P, fn, ctx)
    except Exception:
        return None
    if not notes:
        return None
    _w_alias_shortcuts(ctx, fn.name, notes)
    return {'walias': notes}


def apply(P, args, kwargs, result):
    """`result` is the legacy `(sig, generated, ctx)` of `_one_function(*args, **kwargs)`;
    returns it unchanged or with `generated` replaced by the IR emitter's C."""
    current = mode()
    if not current:
        return result
    I.SRC.clear()                    # --debug source positions of the previous function
    try:
        return _apply(P, args, kwargs, result, current)
    finally:
        I.SRC.clear()


def _apply(P, args, kwargs, result, current):
    sig, generated, ctx = result
    bound = inspect.signature(P._one_function_numeric_impl).bind(*args, **kwargs).arguments
    fn, cname = bound['fn'], bound['cname']
    recursive = bool(bound.get('recursive', False))
    try:
        if bound.get('is_method'):
            raise lower.NotS0('a method')
        hier = getattr(P, '_HIER', None)
        if hier:
            # docs/design/TYPED_INHERITANCE.md section 6: dispatch and subtype conversions are the
            # legacy emitter's; a function that touches a class of a hierarchy stays there
            kinds = (list(ctx.types.values()) + [k for _, k in getattr(ctx, 'params', ())]
                     + [getattr(ctx, 'ret', None)])
            touched = sorted({k[1] for k in kinds if isinstance(k, tuple) and len(k) == 2
                              and isinstance(k[1], str) and k[1] in hier})
            if touched or getattr(fn, '_ail_dispatcher', False):
                raise lower.NotS0('class %s is in an inheritance hierarchy' % (touched or [fn.name])[0])
        allow = os.environ.get('AIL_IR_FUNCS')
        if allow and fn.name not in allow.split(','):
            raise lower.NotS0('not in AIL_IR_FUNCS')
        _summaries(ctx)
        if os.environ.get("AIL_IR_AST") == fn.name:
            import ast, sys
            with open(os.environ.get("AIL_IR_AST_FILE", "/dev/stderr"), "a") as out:
                print(ast.unparse(fn), file=out)
                print("---- types:", dict(ctx.types), file=out)
        function, program = lower.lower(P, fn, ctx, sig, recursive, cname, PENDING,
                                        not bound.get('local_methods', True), _summaries(ctx))
        if not _only_cleanup_before(generated, sig):
            raise lower.NotS0('the legacy path emits helpers around this function')
        if '_stdin_broots' in generated:
            # a `for line in sys.stdin` loop whose list is only printed afterwards runs in batches with
            # the strings freed per batch (2.5 MB against 150 MB on a million lines); the IR has no such pass
            raise lower.NotS0('stdin line batching belongs to the legacy emitter')
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
        named = re.search(r'static void (ail_unwind_\w+)\(void \*\*p\) \{', generated)
        link_units = not bound.get('local_methods', True)
        new_sig, body, needs = emit_c.emit_function(function, PENDING, checked_exceptions(), _summaries(ctx),
                                                    named.group(1) if named else None,
                                                    None if link_units else LISTVAL)
        # (a function with a try has its parameters `volatile` in the legacy signature, for the
        # setjmp rule; a qualifier on a parameter does not change the type of the function)
        if new_sig != sig and ''.join(new_sig.split()) != ''.join(re.sub(r'\bvolatile\b', '', sig).split()):
            raise I.IRError('IR signature %r differs from the legacy %r' % (new_sig, sig))
        if needs['need'] and ctx.need is None:
            raise lower.NotS0('checked helpers in a non-strict build')
    except lower.NotS0 as reason:
        _record(fn.name, cname, 'legacy', str(reason), ctx, extra=_legacy_walias(P, fn, ctx))
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
    extra = {}
    sharing = getattr(function, 'sharing', None)
    if sharing and any(sharing.values()):
        extra['sharing'] = sharing
    walias = getattr(function, 'walias', None)
    if walias:
        extra['walias'] = walias
        _w_alias_shortcuts(ctx, fn.name, walias)
    _record(fn.name, cname, 'ir', '', ctx, pass_stats, extra)
    if function.effects is not None:
        _summaries(ctx)[cname] = function.effects
    if needs['pending']:
        PENDING.add(cname)
    if needs.get('byval'):
        LISTVAL.add(cname)
    return sig, body, ctx
