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
import ast
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


def _split_params(text):
    """The top-level comma-separated C parameter declarations of a legacy signature."""
    if text.strip() == 'void':
        return []
    out, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        elif ch == ',' and depth == 0:
            out.append(text[start:i].strip())
            start = i + 1
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def _tint_fallback(P, fn, cname, ctx, result, sig, generated, tint_sig):
    """Keep a tinted C signature over a legacy int64 body.

    The callers of this function were typed against `TINT_ACTIVE` (they pass and receive
    `ail_tint`). When the IR cannot lower the function, the legacy body keeps its int64 ABI, so
    this emits `<sym>__i64` for that body and a `<sym>` wrapper with the tagged signature the
    callers already use. Internal calls to `<sym>` (recursion) go through the wrapper too, which
    is what makes a self-recursive fallback agree with itself.
    """
    params = tint_sig[0]
    ret_tint = bool(tint_sig[1])
    tint_names = {n for (n, _), t in zip(ctx.params, params) if t}
    match = re.search(r'\b%s\s*\((.*)\)\s*$' % re.escape(cname), sig, re.S)
    if match is None:
        getattr(P, 'TINT_ACTIVE', {}).pop(fn.name, None)
        getattr(P, 'TINT_ACTIVE', {}).pop(cname, None)
        return result
    decls = _split_params(match.group(1))
    wrapper_sig = sig
    for name in sorted(tint_names):
        wrapper_sig = re.sub(r'(?<!\w)(?:volatile\s+)?int64_t(\s+)v_%s(?!\w)'
                             % re.escape(name), r'ail_tint\1v_%s' % name, wrapper_sig, count=1)
    if ret_tint:
        wrapper_sig = re.sub(r'\bint64_t(\s+)%s\s*\(' % re.escape(cname),
                             r'ail_tint\1%s(' % cname, wrapper_sig, count=1)
    impl_sig = re.sub(r'\b%s\b' % re.escape(cname), cname + '__i64', sig, count=1)
    impl_body = generated.replace(sig, impl_sig, 1)
    args = []
    for decl in decls:
        name = re.search(r'([A-Za-z_]\w*)\s*$', decl).group(1)
        if name.startswith('v_') and name[2:] in tint_names:
            args.append('ail_tint_i64(%s)' % name)
        else:
            args.append(name)
    call = '%s__i64(%s)' % (cname, ', '.join(args))
    if re.search(r'\bvoid\s+%s\s*\(' % re.escape(cname), sig):
        body = '    %s;\n' % call
    elif ret_tint:
        body = '    return ail_tint_from_int64(%s);\n' % call
    else:
        body = '    return %s;\n' % call
    wrapper = '%s {\n%s}\n' % (wrapper_sig, body)
    ctx.parts.add('TINTT')
    return (wrapper_sig, impl_body + wrapper, ctx)


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


def _drop_tint(P, *names):
    """A function that stays on the legacy int64 emitter must not advertise a tagged ABI.
    TINT_ACTIVE is what call sites read; TINT_SIGS is what the IR's own call lowering reads.
    Both must forget the function, or a caller lowered earlier or later emits an `ail_tint` call
    to a function that actually returns plain int64 (an invalid initializer in the C)."""
    for _map in (getattr(P, 'TINT_ACTIVE', None), getattr(P, 'TINT_SIGS', None)):
        if _map is not None:
            for _name in names:
                _map.pop(_name, None)


def _apply(P, args, kwargs, result, current):
    sig, generated, ctx = result
    bound = inspect.signature(P._one_function_numeric_impl).bind(*args, **kwargs).arguments
    fn, cname = bound['fn'], bound['cname']
    recursive = bool(bound.get('recursive', False))
    _py = os.environ.get('AIL_SURFACE') == 'python'

    _user_methods = set(getattr(ctx, 'user_method_names', ()))
    _attr_calls = [n for n in ast.walk(fn)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    if _py and any(n.func.attr in _user_methods for n in _attr_calls):
        from pyfront import Unsupported
        if not os.environ.get('AIL_NO_GENERAL'):
            raise Unsupported('%s() calls a user method, which the tagged-int lowering does not type' % fn.name)
    _io_names = {'open', 'write_text', 'write_bytes', 'read_text', 'read_bytes', 'file_chunks'}
    _file_helpers = getattr(P, '_FILE_HELPER_NAMES', ())
    _io_like = any(isinstance(n, (ast.With, ast.AsyncWith)) for n in ast.walk(fn)) or any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and (n.func.id in _io_names or n.func.id in _file_helpers
             or n.func.id.startswith('_ail_nt_'))
        for n in ast.walk(fn))
    _library_call = any(n.func.attr not in _user_methods for n in _attr_calls) or any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and (n.func.id.startswith(('_ail_', '_Ail')) or n.func.id in _io_names
             or n.func.id in getattr(ctx, 'prelude_names', ()))
        for n in ast.walk(fn)) or any(isinstance(n, (ast.With, ast.AsyncWith)) for n in ast.walk(fn))
    if _py and not _io_like:
        for _n in ast.walk(fn):
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) and (_n.func.id in ('int', '_ail_int2') or _n.func.id.endswith(('str_to_int', 'bytes_to_int'))) and _n.args:
                try:
                    _k = P._etype(_n.args[0], ctx)
                except Exception:
                    _k = None
                if _k == P.STR or _k == P.BYTES:
                    from pyfront import Unsupported
                    if not os.environ.get('AIL_NO_GENERAL'):
                        raise Unsupported('%s() parses an int from text, which the tagged-int lowering does not cover'
                                          % fn.name)
    if _py and not _library_call and (getattr(ctx, 'numeric_tokens', None) or getattr(ctx, 'numeric_assignments', None)):
        from pyfront import Unsupported
        if not os.environ.get('AIL_NO_GENERAL'):
            raise Unsupported('%s() mixes int and float bindings, which the tagged-int lowering does not cover'
                              % fn.name)
    # B2b: a function whose ints are not locally proven needs the IR's tagged-int lowering. If the
    # IR cannot lower it, the typed path must not fall back to the legacy int64 emitter: raise so
    # pyc.build tries the exact general path.
    # A module variable is not a local the local proof can type: the proof treats every read of one
    # as an unknown operand. Its C storage is still the int64 static (checked on every store), so
    # that failure is not an int operation that needs the tagged lowering.
    _module_vars = set(getattr(getattr(ctx, 'modconsts', None), 'vars', {}) or ())
    _uses_module_var = bool(getattr(ctx, 'gdecl', None)) or any(
        isinstance(n, ast.Name) and n.id in _module_vars for n in ast.walk(fn))
    _needs_tint = False
    _proof = None
    try:
        import bigcap
        if not _py:
            raise RuntimeError
        _d = bigcap._Defined(set(getattr(ctx, 'funcs', {})) | set(getattr(ctx, 'classes', {})))
        _d.classes = frozenset(getattr(ctx, 'classes', {}))
        _proven = bigcap.proven_int_names(fn, _d)
        _bounds = bigcap.local_int_bounds(fn, _d)
        _names = set(bigcap._lp_params(fn)) | set(bigcap._lp_locals(fn.body))
        _params = dict(getattr(ctx, 'params', ()))
        _tint_names = {n for n in _names if n not in _proven and
                       (getattr(ctx, 'types', {}).get(n) == P.INT or _params.get(n) == P.INT)}
        _proof = bigcap._lp_reason([fn], None, _d)
        # "an operand not proven int or float" is what an untyped GLOBAL (a module-level float the
        # function only reads) produces; it is not an int operation. Let that shape keep the
        # legacy typed emitter (a no-int program must not take the general path).
        _int_failure = (_proof is not None and 'not proven int or float' not in _proof
                        and any(w in _proof for w in ('int', 'operand', 'shift', 'power', 'overflow')))
        if _uses_module_var:
            _int_failure = False
        _needs_tint = bool(_tint_names) or _int_failure
        _no_tint_locals = not _tint_names
        if _io_like or fn.name.startswith(('_Ail', '_ail')):
            _needs_tint = False
    except Exception:
        _needs_tint = False
        _no_tint_locals = False
    _has_tint_call = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and (getattr(P, 'TINT_SIGS', {}).get(n.func.id) or ((), 0))[1]
        for n in ast.walk(fn))
    # A call result the proof cannot bound has no named local to tag. When the IR can lower the
    # function, TINT_SIGS gives its result the tagged type and the return checks the conversion.
    # A build with the general path available still uses it: the typed path cannot hold a result
    # above int64 in a list/dict/field, and dropping to the general path is what keeps such a
    # program exact. Only a typed-only build (AIL_NO_GENERAL) has no exact alternative, and there
    # the function keeps the legacy emitter if the IR cannot lower it.
    _call_result_proof = (_proof or '').startswith('a call result not proven to fit int64')
    _typed_only = bool(os.environ.get('AIL_NO_GENERAL')) or getattr(P, 'GENERAL_BLOCKED', False)
    if _py and _needs_tint and _no_tint_locals and not _has_tint_call \
            and not (_call_result_proof and _typed_only) \
            and not (_proof or '').startswith(('it calls ', 'it contains ')):
        from pyfront import Unsupported
        if not os.environ.get('AIL_NO_GENERAL'):
            raise Unsupported('%s() has an int operation the local proof cannot bound, but no tagged local (%s)'
                              % (fn.name, _proof))
    _sig = getattr(P, 'TINT_SIGS', {}).get(fn.name) if _py else None
    if _sig and (any(_sig[0]) or _sig[1]) and not _io_like:
        _needs_tint = True
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
            import sys
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
        if bound.get('static_helpers') and not new_sig.startswith(('static', '__attribute__')):
            new_sig = 'static' + chr(10) + new_sig
        # (a function with a try has its parameters `volatile` in the legacy signature, for the
        # setjmp rule; a qualifier on a parameter does not change the type of the function)
        if new_sig != sig and ''.join(new_sig.split()) != ''.join(re.sub(r'\bvolatile\b', '', sig).split()) \
                and not _needs_tint:
            raise I.IRError('IR signature %r differs from the legacy %r' % (new_sig, sig))
        if needs['need'] and ctx.need is None:
            raise lower.NotS0('checked helpers in a non-strict build')
    except lower.NotS0 as reason:
        _record(fn.name, cname, 'legacy', str(reason), ctx, extra=_legacy_walias(P, fn, ctx))
        if _uses_module_var and getattr(P, 'GLOBAL_INT_TINT', False):
            # The module ints are `ail_tint` statics this pass; the legacy int64 emitter cannot
            # share them. The whole program takes the exact general path instead of mixing two
            # representations of one variable.
            from pyfront import Unsupported
            raise Unsupported('%s() needs the tagged-int lowering for its module variables: %s'
                              % (fn.name, reason))
        _tinted_sig = bool(_sig and (any(_sig[0]) or _sig[1]))
        if _needs_tint and (_tinted_sig or 'has kind (' not in str(reason)) \
                and not _call_result_proof \
                and not fn.name.startswith(('_Ail', '_ail')) \
                and not os.environ.get('AIL_NO_GENERAL'):
            from pyfront import Unsupported
            raise Unsupported('%s() needs the tagged-int lowering, which does not cover it: %s'
                              % (fn.name, reason))
        if _py and _tinted_sig:
            # The function's callers were typed for the tagged signature. Keep that decision at
            # the C boundary by wrapping the int64 legacy body, instead of leaving the callers
            # passing ail_tint to an int64_t prototype.
            return _tint_fallback(P, fn, cname, ctx, result, sig, generated, _sig)
        _drop_tint(P, fn.name, cname)
        return result
    except Exception as error:
        if current == 'verify':
            raise
        _record(fn.name, cname, 'legacy', 'IR failure: %s: %s' % (type(error).__name__, error), ctx)
        _tinted_sig = bool(_sig and (any(_sig[0]) or _sig[1]))
        if _needs_tint and not os.environ.get('AIL_NO_GENERAL') \
                and not fn.name.startswith(('_Ail', '_ail')):
            from pyfront import Unsupported
            raise Unsupported('%s() needs the tagged-int lowering, which does not cover it: %s'
                              % (fn.name, error))
        if _py and _tinted_sig:
            return _tint_fallback(P, fn, cname, ctx, result, sig, generated, _sig)
        _drop_tint(P, fn.name, cname)
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
    return (new_sig if _needs_tint else sig), body, ctx
