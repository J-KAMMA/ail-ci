"""IR -> C for the S0 subset.

The C boundary is the legacy one, unchanged (design §1.3): the same symbol, linkage, parameter
names (`v_<name>`) and C types, so legacy and IR functions call each other directly. Arithmetic
goes through the same runtime helpers the legacy path uses (ck_add/ck_sub/ck_mul/ck_neg,
pydiv/pymod, ail_fdiv, ail_ffloormod, ail_ipow, ck_shl/ck_shlk/ck_shr), with the same
power-of-two rewrites of // and % (exact identities, see pyfunc.py), so the generated machine
code and every message on a failing check are those of the legacy path.

Each SSA value becomes one C local (`ir<N>`) assigned once; places become `v_<name>` locals
initialised to 0, as the legacy path declares its locals; constants are printed inline.
The emitter reports the runtime pieces it used (`parts`, `need`, `floor`) so the driver can
merge them into the program's runtime selection.
"""
import math
import os

from . import ir as I
from . import effects as E
from . import rtc
from .emit_text import TextEmitter, allocates_str, allocates_bytes


def ctype(t):
    if t in (I.I64, I.I1):
        return 'int64_t'
    if t == I.F64:
        return 'double'
    if t == BYTES:
        return 'ail_bytes'
    if t == I.STRV:
        return 'ail_str'
    if t.head == 'obj':
        inner = t.args[0]
        if inner.head == 'class':
            return 'ail_obj_%s *' % inner.name
        if inner.head == 'bytearray':
            return 'ail_bytearray *'
        if inner.head == 'list' and inner.args[0] == I.I64:
            return 'ail_list *'
        if inner.head == 'list' and inner.args[0] == I.F64:
            return 'ail_flist *'
    raise I.IRError('no C type for %s' % t)


BYTES = I.T('bytes')


def c_int(value):
    if value == -(1 << 63):
        return '(-9223372036854775807LL - 1LL)'
    return '%dLL' % value


def c_float(value):
    if math.isnan(value):
        return '(__builtin_nan(""))'
    if math.isinf(value):
        return '(__builtin_inf())' if value > 0 else '(-__builtin_inf())'
    return '(%r)' % value


LINKAGE_PREFIX = {
    'extern': '',
    'static': 'static\n',
    'inline_always': '__attribute__((always_inline)) static inline\n',
}

_CMP = {'eq': '==', 'ne': '!=', 'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>='}
_CK_HELPER = {'add': 'ck_add', 'sub': 'ck_sub', 'mul': 'ck_mul'}
_PLAIN = {'add': '+', 'sub': '-', 'mul': '*', 'and': '&', 'or': '|', 'xor': '^',
          'fadd': '+', 'fsub': '-', 'fmul': '*'}


def _decl(ct, name):
    return ct + name if ct.endswith('*') else '%s %s' % (ct, name)


def signature(fn, sym=None, linkage=None, byval=False):
    results = fn.results
    if len(results) > 1:
        raise I.IRError('S0 functions return at most one value')
    ret = ctype(results[0]) if results else 'void'
    abi = fn.attrs.get('abi') or ['value'] * len(fn.params)
    decls = []
    for p, n, a in zip(fn.params, fn.param_names, abi):
        if a == 'array':
            decls.append('const int64_t *v_%s, int64_t v_%s_len' % (n, n))
        elif a == 'flist':
            decls.append('ail_flist v_%s' % n)
        else:
            decls.append(_decl(ctype(p.type), 'v_' + n))
    if fn.attrs.get('ret_list') and byval:
        # IR to IR (S3b): the list leaves as the {p, n, cap} struct itself, no copy through the spill slot
        ret = 'ail_flist' if fn.attrs['ret_list'] == 'flist' else 'ail_list'
    elif fn.attrs.get('ret_list'):
        # a returned list crosses the C boundary as the legacy path hands it back (cruntime LISTRET):
        # through a buffer the caller owns, the true length as the result
        ret = 'int64_t'
        decls.append('%s *_out, int64_t _cap' % ('double' if fn.attrs['ret_list'] == 'flist' else 'int64_t'))
    params = ', '.join(decls)
    linkage = linkage or fn.attrs.get('linkage', 'extern')
    prefix = LINKAGE_PREFIX.get(linkage)
    if prefix is None:
        raise I.IRError('unknown linkage %r' % linkage)
    return '%s%s %s(%s)' % (prefix, ret, sym or fn.sym, params or 'void')


def _args_of(fn, want_out=True):
    """The parameters as C arguments, to forward them to another function of the same signature."""
    abi = fn.attrs.get('abi') or ['value'] * len(fn.params)
    out = []
    for n, a in zip(fn.param_names, abi):
        out.append('v_%s, v_%s_len' % (n, n) if a == 'array' else 'v_%s' % n)
    if fn.attrs.get('ret_list') and want_out:
        out.append('_out, _cap')
    return ', '.join(out)


def storage(t):
    """The C type a place of this IR type holds: an owned list is the inline {p, n, cap} struct."""
    if t == I.T('obj', I.T('list', I.I64)):
        return 'ail_list'
    if t == I.T('obj', I.T('list', I.F64)):
        return 'ail_flist'
    return ctype(t)


def _zero(t):
    if t == I.STRV:
        return '(ail_str){0}'
    if t == I.BYTES:
        return '(ail_bytes){0}'
    return '0.0' if t == I.F64 else '0'


def _c_literal(text):
    """A UTF-8 string as one `"\\xHH"` literal per byte (what the legacy path writes: hex escapes
    are maximal-munch in C, so every byte gets its own), and whether it is pure ASCII."""
    data = text.encode('utf-8')
    body = ''.join('"' + chr(92) + 'x%X"' % b for b in data) or '""'
    return body, len(data), int(data.isascii())


AIL_IR_EXC, AIL_IR_RET = 1, 2         # statuses of an outlined try body (cruntime.IREXC)


class _Cx(object):
    """One C function being written: the IR function itself ('top'), or the body of a `try`
    ('body'), which is outlined (design section 11: the setjmp that catches a longjmp from a
    legacy callee or a runtime trap lives in `ail_ir_try`, never in an IR function)."""

    def __init__(self, kind, loops_start, scopes_start):
        self.kind = kind
        self.lines = []
        self.loops_start = loops_start     # loops with a smaller index belong to an outer function
        self.scopes_start = scopes_start
        self.escapes = {}                  # (op, id(loop)) -> (status, op, loop)
        self.returns = False               # whether a return leaves this body


_LISTS = (I.T('obj', I.T('list', I.I64)), I.T('obj', I.T('list', I.F64)))
_BA = I.T('obj', I.T('bytearray'))


class Emitter(TextEmitter):
    def __init__(self, fn, pending=(), checked=False, summaries=None, unwind_name=None, listval=None):
        self.fn = fn
        # callees with a by-value list entry `<sym>__irl` (S3b); None: separately linked units, none
        self.listval = frozenset(listval or ())
        self.allow_byval = listval is not None
        # the helper that frees what a longjmp unwinds over: the name the legacy path chose for its own
        # (unique among the program's symbols), else one derived from the function's symbol
        self.unwind_name = unwind_name
        self.checked = checked                  # exceptions as checked returns, else the legacy longjmp
        self.names = {}
        self.defs = E.defs_of(fn)
        self.count = 0
        self.parts = set()
        self.need = set()
        self.floor = set()
        self.labels = 0
        self.span_names = {}
        self.pending = frozenset(pending)       # callees with an exception entry point `<sym>__ir`
        ops = list(I.walk(fn.body))
        # an exception can leave this function pending: it raises, or calls a function that can
        # (a try can hand on an exception that nothing in it names, whatever raised it)
        self.is_pending = checked and any(i.op in ('raise', 'reraise', 'try')
                                          or (i.op == 'call' and i.attrs.get('callee') in self.pending)
                                          for i in ops)
        self.frame = any(i.op == 'try' for i in ops)
        self.byval = bool(fn.attrs.get('ret_list')) and not self.is_pending and not self.frame and self.allow_byval
        self.pre = 'fr->' if self.frame else ''
        self.text_init(fn)
        self.cx = _Cx('top', 0, 0)
        self.lines = self.cx.lines
        self.owner = {}                         # value -> the C function that defines it
        self.scopes = []                        # cleanup actions of the enclosing handlers
        self.aux = []                           # outlined try bodies and helpers, written first
        self.tries = 0
        self.next_status = 3
        self.retained = [self.pre + 'v_' + n for n in fn.attrs.get('retain', ())]
        # the lists this function owns (S3a): one place each, freed at every exit; a cleanup frame
        # links them so a longjmp over this function frees them too -- only when something in the
        # function can raise (or call something that can); otherwise there is no edge to clean
        self.owned = [(self.pre + 'v_' + i.attrs['name'],
                       'bytearray' if i.result.type.pointee == _BA else
                       'flist' if i.result.type.pointee == _LISTS[1] else 'list')
                      for i in fn.body.instrs
                      if i.op == 'local.alloc' and (i.result.type.pointee in _LISTS or i.result.type.pointee == _BA)]
        for i in fn.body.instrs:
            if i.op == 'local.alloc' and i.result.type.pointee.head == 'obj' \
                    and i.result.type.pointee.args[0].head == 'class':
                self.owned.append((self.pre + 'v_' + i.attrs['name'], 'obj'))
        if self.needs_sar:
            self.owned.append((self.sar, 'sarena'))
        if self.needs_bar:
            self.owned.append((self.bar, 'barena'))
        if self.owned:
            eff = E.body_effects(fn, None, summaries)
            self.owned_can_raise = bool(eff.unknown or eff.raises)
        else:
            self.owned_can_raise = False
        self.link = bool(self.retained) or self.owned_can_raise
        self.span_own = set()                   # spans over an owned list (their failures are the legacy die)
        abi = fn.attrs.get('abi') or ['value'] * len(fn.params)
        for p, n, a in zip(fn.params, fn.param_names, abi):
            self.names[p] = self.pre + 'v_' + n
            if a == 'array':
                self.span_names[p] = ('((int64_t *)%sv_%s)' % (self.pre, n), '%sv_%s_len' % (self.pre, n))
            elif a == 'flist':
                self.span_names[p] = ('%sv_%s.p' % (self.pre, n), '%sv_%s.n' % (self.pre, n))

    # ------------------------------------------------------------------ naming
    def fresh(self, v):
        self.count += 1
        self.names[v] = 'ir%d' % self.count
        self.owner[v] = self.cx
        return self.names[v]

    def const_of(self, v):
        ins = self.defs.get(v)
        return ins.attrs.get('value') if ins is not None and ins.op == 'const' else None

    def ref(self, v):
        ins = self.defs.get(v)
        if ins is not None and ins.op == 'const':
            value = ins.attrs['value']
            if v.type == I.F64:
                return c_float(value)
            if v.type == I.I1:
                return '1' if value else '0'
            return c_int(value)
        try:
            name = self.names[v]
        except KeyError:
            raise I.IRError('value used before it was emitted: %r' % (v,))
        if self.owner.get(v, self.cx) is not self.cx:
            raise I.IRError('value %s is used in a try body but defined outside it' % name)
        return name

    def line(self, depth, text):
        self.cx.lines.append('    ' * depth + text)

    def use(self, *helpers):
        self.need.update(helpers)
        self.need.add('ail_die')

    # ------------------------------------------------------------------ function
    def frame_struct(self):
        """The frame of a function with a `try`: its parameters, its places and the value of an early
        `return` from a try body, in memory, so the outlined bodies share them."""
        fn = self.fn
        fields = []
        abi = fn.attrs.get('abi') or ['value'] * len(fn.params)
        for p, n, a in zip(fn.params, fn.param_names, abi):
            if a == 'array':
                fields.append('const int64_t *v_%s; int64_t v_%s_len;' % (n, n))
            elif a == 'flist':
                fields.append('ail_flist v_%s;' % n)
            else:
                fields.append('%s;' % _decl(ctype(p.type), 'v_' + n))
        params = set(fn.param_names)
        for ins in fn.body.instrs:
            if ins.op == 'local.alloc':
                name = ins.attrs['name']
                fields.append('%s;' % _decl(storage(ins.result.type.pointee), ('l_' if name in params else 'v_') + name))
        fields.extend(self.text_fields())
        if fn.results and not fn.attrs.get('ret_list'):
            fields.append('%s;' % _decl(ctype(fn.results[0]), 'ret'))
        fields.append('char _unused;')
        return 'struct %s__fr { %s };\n' % (fn.sym, ' '.join(fields))

    def emit(self):
        fn = self.fn
        sig = signature(fn)
        params = set(fn.param_names)
        sym = fn.sym
        ir_sig = signature(fn, sym + '__ir', 'static') if self.is_pending else sig
        if self.byval:
            ir_sig = signature(fn, sym + '__irl', 'static', byval=True)
        abi = fn.attrs.get('abi') or ['value'] * len(fn.params)
        if self.frame:
            self.aux.append(self.frame_struct())
            self.line(1, 'struct %s__fr fr_ = {0};' % sym)
            self.line(1, 'struct %s__fr *fr = &fr_;' % sym)
            for n, a in zip(fn.param_names, abi):
                if a == 'array':
                    self.line(1, 'fr->v_%s = v_%s; fr->v_%s_len = v_%s_len;' % (n, n, n, n))
                else:
                    self.line(1, 'fr->v_%s = v_%s;' % (n, n))
        for ins in fn.body.instrs:
            if ins.op == 'local.alloc':
                name = ins.attrs['name']
                c = self.pre + ('l_' if name in params else 'v_') + name
                self.names[ins.result] = c
                if not self.frame:
                    if ins.result.type.pointee in _LISTS or ins.result.type.pointee in (I.STRV, I.BYTES):
                        self.line(1, '%s %s = {0};' % (storage(ins.result.type.pointee), c))
                    else:
                        self.line(1, '%s %s = 0;' % (ctype(ins.result.type.pointee), c))
        self.text_decls(1)
        self.text_parts()
        if fn.attrs.get('recursive'):
            self.parts.add('RECDEPTH')
        if any(kind in ('list', 'flist') for _, kind in self.owned):
            self.parts.update(('LIST', 'IRLIST'))
            if any(kind == 'flist' for _, kind in self.owned):
                self.parts.update(('FLIST', 'IRFLIST'))
        if any(kind == 'bytearray' for _, kind in self.owned):
            self.parts.add('BYTEARRAY')
        if self.link:
            # a bytearray parameter kept across calls (the legacy path retains it too) and the lists
            # this function owns: released at every exit, and by the cleanup frame when a longjmp
            # unwinds over this function
            self.parts.add('DIE')
            steps = []
            for k, name in enumerate(self.retained):
                self.parts.add('BYTEARRAY')
                steps.append('ail_bytearray_release(*(ail_bytearray **)p[%d]);' % k)
            for k, (name, kind) in enumerate(self.owned, len(self.retained)):
                if kind == 'bytearray':
                    steps.append('ail_bytearray_release(*(ail_bytearray **)p[%d]);' % k)
                elif kind == 'obj':
                    steps.append('ail_obj_release(*(void **)p[%d]);' % k)
                else:
                    steps.append('ail_%s_free((ail_%s *)p[%d]);' % (kind, kind, k))
            unwind = self.unwind_name or 'ail_unwind_ir_%s' % sym
            self.aux.append('static void %s(void **p) { %s }\n' % (unwind, ' '.join(steps)))
            for name in self.retained:
                self.line(1, 'ail_bytearray_retain(%s);' % name)
            cargs = ['(void *)(&%s)' % n for n in self.retained] + ['(void *)(&%s)' % n for n, _ in self.owned]
            self.line(1, 'void *v__cargs[] = {%s};' % ', '.join(cargs))
            self.line(1, 'ail_cleanup_frame v__cf = {ail_cleanup_top, %s, v__cargs};' % unwind)
            self.line(1, 'ail_cleanup_top = &v__cf;')
        if self.is_pending or self.frame:
            self.parts.add('IREXC')
        self.region(fn.body, 1, None)
        text = '%s {\n%s\n}\n' % (ir_sig, '\n'.join(self.cx.lines))
        out = ''.join(self.aux) + text
        if self.byval:
            kind = 'flist' if fn.attrs['ret_list'] == 'flist' else 'list'
            self.parts.update(('FLIST', 'FLISTRET') if kind == 'flist' else ('LIST', 'LISTRET'))
            out += ('%s {\n    ail_%s r = %s__irl(%s);\n    int64_t n = ail_%s_return(&r, _out, _cap);\n'
                    '    ail_%s_free(&r);\n    return n;\n}\n'
                    % (sig, kind, sym, _args_of(fn, False), kind, kind))
        if self.is_pending:
            call = '%s__ir(%s)' % (sym, _args_of(fn))
            if fn.results:
                body = ('    %s r = %s;\n    if (__builtin_expect(ail_pending, 0)) ail_ir_rethrow();\n'
                        '    return r;\n' % ('int64_t' if fn.attrs.get('ret_list') else ctype(fn.results[0]), call))
            else:
                body = '    %s;\n    if (__builtin_expect(ail_pending, 0)) ail_ir_rethrow();\n' % call
            out += '%s {\n%s}\n' % (sig, body)
        return sig, out

    # ------------------------------------------------------------------ exits
    def leaves(self, depth, crossing):
        """Run the cleanup of every enclosing handler scope of this C function that `crossing`
        selects, innermost first."""
        for sc in reversed(self.scopes[self.cx.scopes_start:]):
            if crossing(sc):
                self.line(depth, sc['leave'])

    def epilogue(self, depth):
        if self.link:
            self.line(depth, 'ail_cleanup_top = v__cf.previous;')
        for name in self.retained:
            self.line(depth, 'ail_bytearray_release(%s);' % name)
        for name, kind in self.owned:
            if kind == 'bytearray':
                self.line(depth, 'ail_bytearray_release(%s);' % name)
            elif kind == 'obj':
                self.line(depth, 'ail_obj_release(%s);' % name)
            else:
                self.line(depth, 'ail_%s_free(&%s);' % (kind, name))

    def exit_return(self, depth, value, in_frame=False):
        self.leaves(depth, lambda sc: True)
        if self.cx.kind == 'top':
            if self.byval and value is not None:
                # the list leaves by value: the result takes the storage, the place is left empty
                kind = 'flist' if self.fn.attrs['ret_list'] == 'flist' else 'list'
                self.line(depth, 'ail_%s ir_ret = *(%s); *(%s) = (ail_%s){0};' % (kind, value, value, kind))
                value = 'ir_ret'
            elif self.fn.attrs.get('ret_list') and value is not None:
                # the list leaves through the caller's buffer (LISTRET), then every owned list goes
                self.parts.add('FLISTRET' if self.fn.attrs['ret_list'] == 'flist' else 'LISTRET')
                self.line(depth, 'int64_t ir_ret = ail_%s_return(%s, _out, _cap);'
                          % ('flist' if self.fn.attrs['ret_list'] == 'flist' else 'list', value))
                value = 'ir_ret'
            if in_frame:
                value = 'fr->ret' if self.fn.results else None
            if value is not None and self.fn.results == [I.STRV]:
                self.parts.update(('STR', 'STRRET'))
                self.line(depth, 'ail_str ir_ret = ail_str_return_owned(%s);' % value)
                value = 'ir_ret'
            if value is not None and self.fn.results == [I.BYTES]:
                # (the caller adopts the block into its bytes arena: the result must be a heap copy)
                self.parts.update(('BYTES', 'BYTESRET'))
                self.line(depth, 'ail_bytes ir_ret = ail_bytes_return_owned(%s);' % value)
                value = 'ir_ret'
            if value is not None and self.fn.results == [_BA]:
                # the result is the caller's own reference: take it before the owners let go
                self.parts.add('BYTEARRAY')
                self.line(depth, 'ail_bytearray_retain(%s);' % value)
            self.epilogue(depth)
            self.line(depth, 'return %s;' % value if value is not None else 'return;')
        else:
            if value is not None and not in_frame:
                self.line(depth, 'fr->ret = %s;' % value)
            self.cx.returns = True
            self.line(depth, 'return %d;' % AIL_IR_RET)

    def exit_exc(self, depth):
        """Leave the current construct with an exception pending (it has been set up already)."""
        self.leaves(depth, lambda sc: True)
        if not self.checked:
            # the legacy way out: re-raise what is in flight (unwind frames, longjmp to the
            # innermost handler: this function's own try shim, or a legacy one)
            self.line(depth, 'ail_raise_current();')
            self.line(depth, '__builtin_unreachable();')
        elif self.cx.kind == 'top':
            if self.fn.attrs.get('recursive'):
                self.line(depth, 'ail_depth--;')
            self.epilogue(depth)
            self.line(depth, 'return %s;' % _zero(self.fn.results[0]) if self.fn.results else 'return;')
        else:
            self.line(depth, 'return %d;' % AIL_IR_EXC)

    def escape(self, depth, op, loop):
        """break/continue to a loop outside this try body: leave the body with a status that the
        code after the try turns back into the break/continue."""
        key = (op, id(loop))
        if key not in self.cx.escapes:
            self.cx.escapes[key] = (self.next_status, op, loop)
            self.next_status += 1
        self.leaves(depth, lambda sc: True)
        self.line(depth, 'return %d;' % self.cx.escapes[key][0])

    def pending_check(self, depth):
        if os.environ.get('AIL_IR_NO_PENDING_CHECK'):
            return
        self.line(depth, 'if (__builtin_expect(ail_pending, 0)) {')
        self.exit_exc(depth + 1)
        self.line(depth, '}')

    def region(self, region, depth, owner):
        """`owner` is the instruction whose region this is (None for the function body)."""
        for ins in region.instrs:
            self.instr(ins, depth, owner)

    def assign_new(self, depth, v, expr):
        self.line(depth, '%s = %s;' % (_decl(ctype(v.type), self.fresh(v)), expr))

    # ------------------------------------------------------------------ instructions
    def instr(self, ins, depth, owner):
        op = ins.op
        o = [self.ref(v) for v in ins.operands] if op not in ('local.alloc', 'const') else []
        if op in ('local.alloc', 'const'):
            return
        if op in ('add', 'sub', 'mul'):
            if ins.attrs.get('mode') == 'ck':
                helper = _CK_HELPER[op]
                self.use(helper)
                return self.assign_new(depth, ins.result, '%s(%s, %s)' % (helper, o[0], o[1]))
            if ins.attrs.get('mode') == 'wrap':
                return self.assign_new(depth, ins.result, '((int64_t)((uint64_t)(%s) %s (uint64_t)(%s)))'
                                       % (o[0], _PLAIN[op], o[1]))
            return self.assign_new(depth, ins.result, '((%s) %s (%s))' % (o[0], _PLAIN[op], o[1]))
        if op in ('and', 'or', 'xor', 'fadd', 'fsub', 'fmul'):
            return self.assign_new(depth, ins.result, '(%s %s %s)' % (o[0], _PLAIN[op], o[1]))
        if op == 'neg':
            if ins.attrs.get('mode') == 'ck':
                self.use('ck_neg')
                return self.assign_new(depth, ins.result, 'ck_neg(%s)' % o[0])
            return self.assign_new(depth, ins.result, '(-%s)' % o[0])
        if op == 'fneg':
            return self.assign_new(depth, ins.result, '(-%s)' % o[0])
        if op == 'inv':
            return self.assign_new(depth, ins.result, '(~%s)' % o[0])
        if op in ('floordiv', 'floormod'):
            d = self.const_of(ins.operands[1])
            if isinstance(d, int) and d > 0 and d & (d - 1) == 0:
                # Python's flooring // and % by a positive power of two are exactly an arithmetic
                # shift and a mask on two's complement (the legacy path's rewrite, pyfunc.py).
                if op == 'floordiv':
                    return self.assign_new(depth, ins.result, '((%s) >> %d)' % (o[0], d.bit_length() - 1))
                return self.assign_new(depth, ins.result, '((%s) & %dLL)' % (o[0], d - 1))
            if ins.attrs.get('mode') == 'nonneg':
                # the range pass proved the dividend >= 0 and the divisor is a positive constant:
                # C's truncating / and % equal Python's flooring ones there
                return self.assign_new(depth, ins.result, '((%s) %s %s)' % (o[0], '/' if op == 'floordiv' else '%', o[1]))
            helper = 'pydiv' if op == 'floordiv' else 'pymod'
            self.floor.add(helper)
            return self.assign_new(depth, ins.result, '%s(%s, %s)' % (helper, o[0], o[1]))
        if op == 'pow':
            self.parts.update(('DIE', 'IPOW'))
            return self.assign_new(depth, ins.result, 'ail_ipow(%s, %s)' % (o[0], o[1]))
        if op == 'fdiv':
            self.parts.update(('DIE', 'FDIV'))
            return self.assign_new(depth, ins.result, 'ail_fdiv(%s, %s)' % (o[0], o[1]))
        if op in ('ffloordiv', 'ffloormod'):
            self.parts.add('FFLOORMOD')
            return self.assign_new(depth, ins.result, 'ail_ffloormod(%s, %s, %d)'
                                   % (o[0], o[1], int(op == 'ffloormod')))
        if op == 'fpow':
            self.parts.add('FPOW')
            if self.const_of(ins.operands[1]) == 0.5:
                return self.assign_new(depth, ins.result, 'ail_fsqrt(%s)' % o[0])
            return self.assign_new(depth, ins.result, 'pow(%s, %s)' % (o[0], o[1]))
        if op in ('shl', 'shr'):
            if ins.attrs.get('mode') != 'ck':
                return self.assign_new(depth, ins.result, '(%s %s %s)' % (o[0], '<<' if op == 'shl' else '>>', o[1]))
            k = self.const_of(ins.operands[1])
            if op == 'shl' and isinstance(k, int) and 0 <= k < 64:
                self.use('ck_shlk')
                return self.assign_new(depth, ins.result, 'ck_shlk(%s, %d)' % (o[0], k))
            helper = 'ck_shl' if op == 'shl' else 'ck_shr'
            self.use(helper)
            return self.assign_new(depth, ins.result, '%s(%s, %s)' % (helper, o[0], o[1]))
        if op.startswith('cmp.'):
            return self.assign_new(depth, ins.result, '(%s %s %s)' % (o[0], _CMP[op[4:]], o[1]))
        if op == 'select':
            return self.assign_new(depth, ins.result, '(%s ? %s : %s)' % tuple(o))
        if op == 'zext':
            return self.assign_new(depth, ins.result, o[0])
        if op == 'sitofp':
            return self.assign_new(depth, ins.result, '((double)(%s))' % o[0])
        if op == 'fptosi':
            self.parts.add('DIE')
            self.line(depth, 'if (!(%s >= -9223372036854775808.0 && %s < 9223372036854775808.0)) '
                             'ail_raise_named(AIL_EXC_VALUE);' % (o[0], o[0]))
            return self.assign_new(depth, ins.result, '(int64_t)%s' % o[0])
        if op == 'load':
            return self.assign_new(depth, ins.result, o[0])
        if op == 'store':
            return self.line(depth, '%s = %s;' % (o[0], o[1]))
        if op == 'bytes.len':
            return self.assign_new(depth, ins.result, '(%s).n' % o[0])
        if op == 'bytes.get':
            self.parts.add('BYTES')
            if ins.attrs.get('mode') == 'nck':
                return self.assign_new(depth, ins.result, '((int64_t)(%s).p[%s])' % (o[0], o[1]))
            return self.assign_new(depth, ins.result, 'ail_bytes_get(%s, %s)' % (o[0], o[1]))
        if op == 'field.get':
            return self.assign_new(depth, ins.result, '(%s)->f_%s' % (o[0], ins.attrs['name']))
        if op == 'field.set':
            return self.line(depth, '(%s)->f_%s = %s;' % (o[0], ins.attrs['name'], o[1]))
        if op == 'field.list':
            return self.assign_new(depth, ins.result, '(&(%s)->f_%s)' % (o[0], ins.attrs['name']))
        if op == 'span.of' and ins.result.type == I.T('span', I.T('u8')):
            name = self.fresh(ins.result)
            self.parts.add('BYTEARRAY')
            self.line(depth, 'ail_bytearray_meta(%s); unsigned char *%s_p = (%s)->p; int64_t %s_n = (%s)->n;'
                      % (o[0], name, o[0], name, o[0]))
            self.span_names[ins.result] = (name + '_p', name + '_n', o[0])
            return
        if op in ('ba.len', 'ba.get', 'ba.set', 'ba.push'):
            self.parts.add('BYTEARRAY')
            B = o[0]
            if op == 'ba.len':
                return self.assign_new(depth, ins.result, 'ail_bytearray_len(%s)' % B)
            if op == 'ba.get':
                if ins.attrs.get('mode') == 'nck':
                    return self.assign_new(depth, ins.result, '((int64_t)(%s)->p[%s])' % (B, o[1]))
                return self.assign_new(depth, ins.result, 'ail_bytearray_get(%s, %s)' % (B, o[1]))
            if op == 'ba.set':
                if ins.attrs.get('mode') == 'nck':
                    return self.line(depth, '(%s)->p[%s] = (unsigned char)(%s);' % (B, o[1], o[2]))
                return self.line(depth, 'ail_bytearray_set(%s, %s, %s);' % (B, o[1], o[2]))
            return self.line(depth, 'ail_bytearray_append(%s, %s);' % (B, o[1]))
        if op in ('span.get', 'span.set') and ins.operands[0].type == I.T('span', I.T('u8')):
            sp, sn, B = self.span_names[ins.operands[0]]
            if op == 'span.get':
                if ins.attrs.get('mode') == 'nck':
                    return self.assign_new(depth, ins.result, '((int64_t)%s[%s])' % (sp, o[1]))
                return self.assign_new(depth, ins.result, '((uint64_t)(%s) < (uint64_t)%s ? (int64_t)%s[%s] : '
                                       'ail__bytearray_get_slow(%s, %s))' % (o[1], sn, sp, o[1], B, o[1]))
            if ins.attrs.get('mode') == 'nck':
                return self.line(depth, '%s[%s] = (unsigned char)(%s);' % (sp, o[1], o[2]))
            return self.line(depth, 'if ((uint64_t)(%s) < (uint64_t)%s && (uint64_t)(%s) <= 255) %s[%s] = '
                                    '(unsigned char)(%s); else ail__bytearray_set_slow(%s, %s, %s);'
                             % (o[1], sn, o[2], sp, o[1], o[2], B, o[1], o[2]))
        if op == 'span.of':
            elem = ins.result.type.args[0]
            name = self.fresh(ins.result)
            ct = 'double' if elem == I.F64 else 'int64_t'
            self.parts.add('NUMVIEW')
            self.line(depth, '%s *%s_p = (%s)->p; int64_t %s_n = %s_p ? (%s)->n : 0;'
                      % (ct, name, o[0], name, name, o[0]))
            self.span_names[ins.result] = (name + '_p', name + '_n')
            d = self.defs.get(ins.operands[0])
            if d is not None and d.op == 'list.ref':
                self.span_own.add(ins.result)
            return
        if op == 'span.len':
            return self.assign_new(depth, ins.result, self.span_names[ins.operands[0]][1])
        if op in ('span.get', 'span.set'):
            elem = ins.operands[0].type.args[0]
            f = 'flist' if elem == I.F64 else 'list'
            sp, sn = self.span_names[ins.operands[0]][:2]
            if ins.operands[0] in self.span_own:
                # a span over a list this function owns fails as the legacy owned list does
                self.parts.update(('LIST', 'IRLIST') if f == 'list' else ('FLIST', 'IRFLIST'))
                view = 'ail_ir_view' if f == 'list' else 'ail_ir_fview'
            else:
                self.parts.add('NUMVIEW')
                view = 'ail_%s_view' % f
            if op == 'span.get':
                if ins.attrs.get('mode') == 'nck':
                    return self.assign_new(depth, ins.result, '%s[%s]' % (sp, o[1]))
                return self.assign_new(depth, ins.result, '%s_get(%s, %s, %s)' % (view, sp, sn, o[1]))
            if ins.attrs.get('mode') == 'nck':
                return self.line(depth, '%s[%s] = %s;' % (sp, o[1], o[2]))
            return self.line(depth, '%s_set(%s, %s, %s, %s);' % (view, sp, sn, o[1], o[2]))
        if op in ('list.len', 'list.get', 'list.set', 'list.push', 'list.pop', 'list.clear'):
            return self.list_op(ins, depth, o)
        if op == 'list.ref':
            return self.assign_new(depth, ins.result, '&' + self.names[ins.operands[0]])
        if op == 'field.ba':
            return self.assign_new(depth, ins.result, '(%s)->f_%s' % (o[0], ins.attrs['name']))
        if op == 'ba.extend_lit':
            self.parts.add('BYTEARRAY')
            data = ins.attrs['data']
            lit = ''.join('"' + chr(92) + 'x%X"' % b for b in data) or '""'
            return self.line(depth, 'ail_bytearray_extend(%s, (ail_bytes){(const unsigned char *)(%s), %d});'
                             % (o[0], lit, len(data)))
        if op == 'obj.init':
            cls = ins.attrs['cls']
            return self.line(depth, 'ail_obj_store_%s(&%s, ail_new_%s(%s), 1);' % (cls, o[0], cls, ', '.join(o[1:])))
        if op == 'obj.copyref':
            return self.line(depth, 'ail_obj_store_%s(&%s, %s, 0);' % (ins.operands[1].type.args[0].name, o[0], o[1]))
        if op == 'ba.extend':
            self.parts.add('BYTEARRAY')
            return self.line(depth, 'ail_bytearray_extend(%s, %s);' % (o[0], o[1]))
        if op == 'ba.call':
            self.parts.add('BYTEARRAY')
            checked = ins.attrs['callee'] in self.pending or (ins.attrs['callee'] == self.fn.sym and self.is_pending)
            text = '%s%s(%s)' % (ins.attrs['callee'], '__ir' if checked else '', ', '.join(o[1:]))
            if checked:
                self.parts.add('IREXC')
                self.count += 1
                t = 'ir%d' % self.count
                self.line(depth, 'ail_bytearray *%s = %s;' % (t, text))
                self.pending_check(depth)
                return self.line(depth, 'ail_bytearray_store(&%s, %s, 1);' % (o[0], t))
            return self.line(depth, 'ail_bytearray_store(&%s, %s, 1);' % (o[0], text))
        if op in ('ba.new', 'ba.drop', 'ba.clear', 'ba.write'):
            self.parts.add('BYTEARRAY')
            if op == 'ba.new':
                return self.line(depth, 'ail_bytearray_store(&%s, ail_bytearray_new(%s), 1);' % (o[0], o[1]))
            if op == 'ba.drop':
                return self.line(depth, 'ail_bytearray_store(&%s, NULL, 1);' % o[0])
            if op == 'ba.clear':
                return self.line(depth, 'ail_bytearray_clear(%s);' % o[0])
            self.parts.add('STDIO')
            return self.line(depth, 'ail_stdout_write_bytes(ail_bytearray_span(%s));' % o[0])
        if op in ('list.reset', 'list.repeat', 'list.lit', 'list.reserve', 'list.move', 'list.copy'):
            return self.list_replace(ins, depth, o)
        if op in ('call', 'list.call'):
            abi = ins.attrs.get('abi') or ['value'] * len(o)
            if op == 'list.call':
                abi = [None] + list(abi)
            parts = []
            for v, text, a in zip(ins.operands, o, abi):
                if a is None:
                    continue
                if a in ('array', 'flist') and v in self.defs and self.defs[v].op in ('list.ref', 'field.list'):
                    # an owned (or field) list handed to a read-only list parameter: the callee gets
                    # the data pointer and length (an int list) or the {p, n, cap} struct (a float list)
                    parts.append('(%s)->p, (%s)->n' % (text, text) if a == 'array' else '*(%s)' % text)
                elif a == 'array':
                    if v in self.span_names and v not in self.names:
                        parts.append('%s, %s' % self.span_names[v][:2])
                    else:
                        parts.append('%s, %s_len' % (text, text))
                else:
                    parts.append(text)
            callee = ins.attrs['callee']
            # a callee with an exception entry point is called through it and its result checked;
            # any other (legacy, or an IR function that cannot raise) by its own name -- if that is
            # the wrapper of an IR function compiled later, a raise comes back as a legacy raise
            checked = callee in self.pending or (callee == self.fn.sym and self.is_pending)
            if checked:
                self.parts.add('IREXC')
            if op == 'list.call':
                # a list-returning callee hands its list back through a buffer (LISTRET); with none
                # given, the whole list waits in the runtime's spill slot and is adopted right after
                dst = ins.operands[0]
                flist = dst.type == _LISTS[1]
                kind = 'flist' if flist else 'list'
                if callee in self.listval or (callee == self.fn.sym and self.byval):
                    # IR to IR: the callee hands its list back by value
                    self.parts.update(('FLIST', 'IRFLIST') if flist else ('LIST', 'IRLIST'))
                    self.count += 1
                    n = 'ir%d' % self.count
                    self.line(depth, 'ail_%s %s = %s__irl(%s);' % (kind, n, callee, ', '.join(parts)))
                    self.line(depth, '{ ail_%s_free(%s); *(%s) = %s; }' % (kind, o[0], o[0], n))
                    return
                parts.append('NULL, 0')
                self.parts.update(('FLIST', 'FLISTRET', 'IRFLIST') if flist else ('LIST', 'LISTRET', 'IRLIST'))
                self.count += 1
                n = 'ir%d' % self.count
                text = '%s%s(%s)' % (callee, '__ir' if checked else '', ', '.join(parts))
                self.line(depth, 'int64_t %s = %s;' % (n, text))
                if checked:
                    self.parts.add('IREXC')
                    self.pending_check(depth)
                kind = 'flist' if flist else 'list'
                self.line(depth, '{ ail_%s _r = ail_%s_adopt_return(%s); ail_%s_free(%s); *(%s) = _r; }'
                          % (kind, kind, n, kind, o[0], o[0]))
                return
            text = '%s%s(%s)' % (callee, '__ir' if checked else '', ', '.join(parts))
            adopt = None
            if ins.results and ins.result.type == I.STRV:
                adopt = 'ail_str_adopt(&%s, %%s)' % self.sar
                self.parts.update(('STR', 'STRRET'))
            elif ins.results and ins.result.type == I.BYTES:
                adopt = 'ail_bytes_adopt(&%s, %%s)' % self.bar
                self.parts.update(('BYTES', 'BYTESRET'))
            if ins.results:
                self.assign_new(depth, ins.result, text if adopt is None or checked else adopt % text)
            else:
                self.line(depth, text + ';')
            if checked:
                self.pending_check(depth)
                if adopt is not None:
                    self.line(depth, '%s = %s;' % (self.names[ins.result], adopt % self.names[ins.result]))
            return
        if op == 'rt':
            callee = ins.attrs['callee']
            if callee == 'ail_depth_enter':
                self.parts.add('RECDEPTH')
                return self.line(depth, 'if (++ail_depth > AIL_MAX_RECURSION_DEPTH) '
                                        'ail_die("recursion depth exceeded");')
            if callee == 'ail_depth_leave':
                return self.line(depth, 'ail_depth--;')
            return self.emit_rt(ins, depth, o)
        if op == 'str.lit':
            return self.emit_str_lit(ins, depth)
        if op == 'bytes.lit':
            return self.emit_bytes_lit(ins, depth)
        if op == 'print':
            return self.emit_print(ins, depth, o)
        if op == 'if':
            return self.emit_if(ins, depth, o[0])
        if op == 'loop':
            return self.emit_loop(ins, depth, o)
        if op == 'for.range':
            return self.emit_for(ins, depth, o)
        if op == 'yield':
            for r, v in zip(owner.results, o):
                self.line(depth, '%s = %s;' % (self.names[r], v))
            return
        if op in ('break', 'continue'):
            loop = self.loops[-1]
            index = len(self.loops) - 1
            if index < self.cx.loops_start:
                # the loop belongs to the function around this try body
                carried = loop.regions[0].args[1:] if loop.op == 'for.range' else loop.regions[0].args
                if o or (op == 'continue' and carried) or (op == 'break' and loop.results and loop.op != 'for.range'):
                    raise I.IRError('%s with values out of a try body' % op)
                return self.escape(depth, op, loop)
            self.leaves(depth, lambda sc: sc['nloops'] > index)
            if op == 'break':
                if loop.op == 'for.range':
                    # a for.range's results are its carried variables: a break stores its values there
                    args = loop.regions[0].args[1:]
                    self.parallel_assign(depth, [self.names[a] for a in args], o, [a.type for a in args])
                    return self.line(depth, 'break;')
                for r, v in zip(loop.results, o):
                    self.line(depth, '%s = %s;' % (self.names[r], v))
                return self.line(depth, 'break;')
            args = loop.regions[0].args[1:] if loop.op == 'for.range' else loop.regions[0].args
            self.parallel_assign(depth, [self.names[a] for a in args], o, [a.type for a in args])
            # (S4a, measured over the 40 programs: omitting the trailing `continue;` everywhere is -8.140% instructions
            # against -8.128% for keeping it, and it is the only setting with no program above +1% -- the
            # while-loops of fannkuch_redux and relaxation-4 gain a jump per iteration with it. S1 had kept it
            # for both loop ops; AIL_IR_TRAILING_CONTINUE=loop,for.range restores that.)
            keep = os.environ.get('AIL_IR_TRAILING_CONTINUE', '')
            if owner is loop and loop.regions[0].instrs[-1] is ins and loop.op not in keep.split(','):
                return          # the end of the C loop body continues anyway (and a trailing
                                # `continue;` changes GCC's block layout: +1 jump per iteration)
            return self.line(depth, 'continue;')
        if op == 'return':
            if not self.scopes and self.cx.kind == 'top' and not self.retained and not self.owned \
                    and self.fn.results not in ([I.STRV], [I.BYTES]):
                return self.line(depth, 'return %s;' % o[0] if o else 'return;')
            return self.exit_return(depth, o[0] if o else None)
        if op == 'raise':
            return self.raise_op(ins, depth)
        if op == 'reraise':
            self.parts.add('IREXC')
            if not self.checked:
                self.line(depth, 'ail_reraise();')
                return self.line(depth, '__builtin_unreachable();')
            self.line(depth, 'ail_ir_reraise();')
            return self.exit_exc(depth)
        if op == 'try':
            return self.emit_try(ins, depth)
        if op == 'unreachable':
            return self.line(depth, '__builtin_unreachable();')
        raise I.IRError('no C for op %s' % op)

    # ------------------------------------------------------------------ exceptions (S2)
    def raise_op(self, ins, depth):
        code, form = ins.attrs['code'], ins.attrs['form']
        self.parts.add('IREXC')
        self.exception_parts([code])
        if form == 'msg':
            body, n, ascii_ = _c_literal(ins.attrs['msg'])
            new = 'ail_exception_new(%d, (const uint8_t *)(%s), %d, %d)' % (code, body, n, ascii_)
        else:
            new = 'ail_exception_new(%d, NULL, 0, 0)' % code
        if not self.checked:
            # exactly what the legacy path writes: the raise takes over the new exception and
            # longjmps (or ends the program when no handler is open)
            if form == 'name':
                self.line(depth, 'ail_raise_named(%d);' % code)
            else:
                self.line(depth, 'ail_raise_value_adopt(%s);' % new)
            return self.line(depth, '__builtin_unreachable();')
        if form == 'name':
            self.line(depth, 'ail_ir_raise_named(%d);' % code)
        elif form == 'new':
            self.line(depth, 'ail_ir_raise_new(%d, NULL, 0, 0);' % code)
        else:
            body, n, ascii_ = _c_literal(ins.attrs['msg'])
            self.line(depth, 'ail_ir_raise_new(%d, (const uint8_t *)(%s), %d, %d);' % (code, body, n, ascii_))
        self.exit_exc(depth)

    def exception_parts(self, codes):
        # AssertionError (9) and OverflowError (10) exist in the DIE block only when asked for
        if any(c >= 9 for c in codes):
            self.parts.add('ASSERTEXC')
        if 10 in codes:
            self.parts.update(('ASSERTEXC', 'OVERFLOWEXC'))

    def exit_to(self, depth, op, loop):
        """Carry out a break/continue (of a loop outside the try body that returned it)."""
        index = next(k for k, l in enumerate(self.loops) if l is loop)
        if index < self.cx.loops_start:
            return self.escape(depth, op, loop)
        self.leaves(depth, lambda sc: sc['nloops'] > index)
        self.line(depth, 'break;' if op == 'break' else 'continue;')

    def dispatch_exits(self, depth, st, body):
        """After a try body that did not run to its end nor raise: its early exits."""
        if body.returns:
            self.line(depth, 'if (%s == %d) {' % (st, AIL_IR_RET))
            self.exit_return(depth + 1, None, in_frame=True)
            self.line(depth, '}')
        for code, op, loop in sorted(body.escapes.values(), key=lambda e: e[0]):
            self.line(depth, 'if (%s == %d) {' % (st, code))
            self.exit_to(depth + 1, op, loop)
            self.line(depth, '}')

    def emit_try(self, ins, depth):
        """A `try` is a call of its outlined body under `ail_ir_try` (the one setjmp, in the
        runtime), then ordinary C: the handlers (catch) or the finally body and the exit the body
        asked for (finally). An exception that no handler takes leaves this function pending."""
        self.parts.add('IREXC')
        kind = ins.attrs['kind']
        sym = self.fn.sym
        self.tries += 1
        n = self.tries
        fname = '%s__try%d' % (sym, n)
        parent = self.cx
        body = _Cx('body', len(self.loops), len(self.scopes))
        self.cx = body
        try:
            self.region(ins.regions[0], 1, ins)
        finally:
            self.cx = parent
        self.aux.append('\n'.join(
            ['static int %s(void *frv) {' % fname,
             '    struct %s__fr *fr = (struct %s__fr *)frv;' % (sym, sym)]
            + body.lines + ['    return 0;', '}', '']))
        st = 'st%d' % n
        self.line(depth, 'int %s = ail_ir_try(%s, fr);' % (st, fname))
        if kind == 'catch':
            self.exception_parts([c for cs in ins.attrs['codes'] for c in cs])
            self.line(depth, 'if (%s == AIL_IR_EXC) {' % st)
            self.line(depth + 1, 'int code%d = ail_exc_code;' % n)
            for k, (codes, region) in enumerate(zip(ins.attrs['codes'], ins.regions[1:])):
                wanted = []
                for c in codes:
                    wanted.append(c)
                    if c == 1:
                        wanted.append(8)           # a ValueError handler also takes UnicodeDecodeError
                cond = ' || '.join('code%d == %d' % (n, c) for c in wanted)
                self.line(depth + 1, '%s (%s) {' % ('if' if k == 0 else '} else if', cond))
                hs = 'hs%d_%d' % (n, k)
                if self.checked:
                    self.line(depth + 2, 'ail_pending = 0;')
                self.line(depth + 2, 'ail_handled_scope %s; ail_handled_enter(&%s, code%d);' % (hs, hs, n))
                self.scopes.append({'leave': 'ail_handled_leave(&%s);' % hs, 'nloops': len(self.loops)})
                try:
                    self.region(region, depth + 2, ins)
                finally:
                    self.scopes.pop()
                if region.instrs[-1].op == 'yield':
                    self.line(depth + 2, 'ail_handled_leave(&%s);' % hs)
            self.line(depth + 1, '} else {')
            self.exit_exc(depth + 2)               # no handler names it: it stays pending
            self.line(depth + 1, '}')
            self.line(depth, '} else if (%s != 0) {' % st)
            self.dispatch_exits(depth + 1, st, body)
            self.line(depth, '}')
            return
        ex, hs = 'ex%d' % n, 'hs%d' % n
        self.line(depth, 'ail_exception *%s = NULL; ail_handled_scope %s; %s.resources[0] = NULL;' % (ex, hs, hs))
        self.line(depth, 'if (%s == AIL_IR_EXC) { %s = ail_ir_take(); ail_handled_enter(&%s, %s->code); }'
                  % (st, ex, hs, ex))
        self.scopes.append({'leave': 'ail_exception_release(%s);' % ex, 'nloops': len(self.loops)})
        self.scopes.append({'leave': 'ail_handled_leave(&%s);' % hs, 'nloops': len(self.loops)})
        try:
            self.region(ins.regions[1], depth, ins)
        finally:
            self.scopes.pop()
            self.scopes.pop()
        self.line(depth, 'ail_handled_leave(&%s);' % hs)
        self.line(depth, 'if (%s) {' % ex)
        if self.checked:
            self.line(depth + 1, 'ail_ir_raise_value(%s);' % ex)
            self.exit_exc(depth + 1)
        else:
            self.line(depth + 1, 'ail_raise_value_adopt(%s);' % ex)
            self.line(depth + 1, '__builtin_unreachable();')
        self.line(depth, '} else if (%s != 0) {' % st)
        self.dispatch_exits(depth + 1, st, body)
        self.line(depth, '}')

    def list_op(self, ins, depth, o):
        """Numeric list fields reached through a struct borrow, with the legacy path's own
        helpers (same checks, same messages): ail_list_span_* reads, ail_numfield_* writes."""
        op = ins.op
        elem = ins.operands[0].type.args[0].args[0]
        f = 'flist' if elem == I.F64 else 'list'
        d = self.defs.get(ins.operands[0])
        if d is not None and d.op == 'list.ref':
            return self.owned_list_op(ins, depth, o, f)
        self.parts.update(('NUMFIELD', 'NUMFIELDMUT', 'LIST'))
        if elem == I.F64:
            self.parts.add('FLIST')
        L = o[0]
        if op == 'list.len':
            return self.assign_new(depth, ins.result, 'ail_%s_span_len((%s)->p, (%s)->n)' % (f, L, L))
        if op == 'list.get':
            if ins.attrs.get('mode') == 'nck':
                return self.assign_new(depth, ins.result, '((%s)->p[%s])' % (L, o[1]))
            return self.assign_new(depth, ins.result, 'ail_%s_span_get((%s)->p, (%s)->n, %s)' % (f, L, L, o[1]))
        if op == 'list.set':
            if ins.attrs.get('mode') == 'nck':
                return self.line(depth, '(%s)->p[%s] = %s;' % (L, o[1], o[2]))
            return self.line(depth, 'ail_numfield_%s_set(%s, %s, %s);' % (f, L, o[1], o[2]))
        if op == 'list.push':
            return self.line(depth, 'ail_numfield_%s_append(%s, %s);' % (f, L, o[1]))
        if op == 'list.pop':
            if ins.results:
                return self.assign_new(depth, ins.result, 'ail_numfield_%s_pop(%s, -1LL)' % (f, L))
            return self.line(depth, '(void)ail_numfield_%s_pop(%s, -1LL);' % (f, L))
        if op == 'list.clear':
            return self.line(depth, 'ail_numfield_%s_clear(%s);' % (f, L))
        raise I.IRError('no C for %s' % op)

    def owned_list_op(self, ins, depth, o, f):
        """Element access, growth and shrinking of a list this function owns: the legacy helpers
        (`ail_list_*`: same messages), with the checked get/set always inlined."""
        op = ins.op
        self.parts.update(('LIST', 'IRLIST') if f == 'list' else ('FLIST', 'IRFLIST'))
        L = o[0]
        ir = 'ail_ir_%s' % f
        if op == 'list.len':
            return self.assign_new(depth, ins.result, '((int64_t)(%s)->n)' % L)
        if op == 'list.get':
            if ins.attrs.get('mode') == 'nck':
                return self.assign_new(depth, ins.result, '((%s)->p[%s])' % (L, o[1]))
            return self.assign_new(depth, ins.result, '%s_get(%s, %s)' % (ir, L, o[1]))
        if op == 'list.set':
            if ins.attrs.get('mode') == 'nck':
                return self.line(depth, '(%s)->p[%s] = %s;' % (L, o[1], o[2]))
            return self.line(depth, '%s_set(%s, %s, %s);' % (ir, L, o[1], o[2]))
        if op == 'list.push':
            return self.line(depth, 'ail_%s_push(%s, %s);' % (f, L, o[1]))
        if op == 'list.pop':
            if ins.results:
                return self.assign_new(depth, ins.result, 'ail_%s_pop(%s, -1LL)' % (f, L))
            return self.line(depth, '(void)ail_%s_pop(%s, -1LL);' % (f, L))
        if op == 'list.clear':
            return self.line(depth, 'ail_%s_clear(%s);' % (f, L))
        raise I.IRError('no C for %s' % op)

    def list_replace(self, ins, depth, o):
        """The operations that replace the content of an owned list (the old content is freed)."""
        op = ins.op
        f = 'flist' if ins.operands[0].type == _LISTS[1] else 'list'
        self.parts.update(('LIST', 'IRLIST') if f == 'list' else ('FLIST', 'IRFLIST'))
        L = o[0]
        if op == 'list.reset':
            return self.line(depth, 'ail_%s_free(%s);' % (f, L))
        if op == 'list.reserve':
            return self.line(depth, 'ail_%s_reserve(%s, %s);' % (f, L, o[1]))
        if op == 'list.repeat':
            self.count += 1
            n, i = 'ir%d' % self.count, 'ir%d' % (self.count + 1)
            self.count += 1
            self.line(depth, '{ int64_t %s = %s; ail_%s_free(%s); if (%s > 0) { ail_%s_reserve(%s, %s); '
                             'for (int64_t %s = 0; %s < %s; %s++) (%s)->p[%s] = %s; (%s)->n = %s; } }'
                      % (n, o[2], f, L, n, f, L, n, i, i, n, i, L, i, o[1], L, n))
            return
        if op == 'list.lit':
            self.line(depth, '{ ail_%s_free(%s);%s }' % (
                f, L, ''.join(' ail_%s_push(%s, %s);' % (f, L, v) for v in o[1:])))
            return
        if op == 'list.copy':
            # the source is read in full before the destination's old content is freed, so a source
            # that is (part of) the destination's own list is fine
            src = ins.operands[1]
            if src in self.span_names:
                sp, sn = self.span_names[src][:2]
            else:
                sp, sn = '(%s)->p' % o[1], '(%s)->n' % o[1]
            self.count += 1
            t, n, i = 'ir%d' % self.count, 'ir%d' % (self.count + 1), 'ir%d' % (self.count + 2)
            self.count += 2
            ct = 'double' if f == 'flist' else 'int64_t'
            self.line(depth, '{ ail_%s %s = {0}; const %s *%s_s = %s; int64_t %s = %s; ail_%s_reserve(&%s, %s); '
                             'for (int64_t %s = 0; %s < %s; %s++) %s.p[%s] = %s_s[%s]; %s.n = %s; '
                             'ail_%s_free(%s); *(%s) = %s; }'
                      % (f, t, ct, t, sp, n, sn, f, t, n, i, i, n, i, t, i, t, i, t, n, f, o[0], o[0], t))
            return
        if op == 'list.move':
            self.count += 1
            t = 'ir%d' % self.count
            self.line(depth, '{ ail_%s %s = *(%s); *(%s) = (ail_%s){0}; ail_%s_free(%s); *(%s) = %s; }'
                      % (f, t, o[1], o[1], f, f, L, L, t))
            return
        raise I.IRError('no C for %s' % op)

    loops = ()
    exit_labels = {}

    def parallel_assign(self, depth, targets, sources, types):
        if not targets:
            return
        if len(targets) == 1:
            self.line(depth, '%s = %s;' % (targets[0], sources[0]))
            return
        temps = []
        for t, s, ty in zip(targets, sources, types):
            self.count += 1
            temps.append('ir%d' % self.count)
            self.line(depth, '%s %s = %s;' % (ctype(ty), temps[-1], s))
        for t, tmp in zip(targets, temps):
            self.line(depth, '%s = %s;' % (t, tmp))

    def declare_results(self, ins, depth):
        for r in ins.results:
            self.line(depth, '%s %s = %s;' % (ctype(r.type), self.fresh(r),
                                              '{0}' if r.type in (I.STRV, I.BYTES) else '0'))

    @staticmethod
    def only_yield(region):
        return len(region.instrs) == 1 and region.instrs[0].op == 'yield' and not region.instrs[0].operands

    def emit_if(self, ins, depth, cond):
        self.declare_results(ins, depth)
        then, other = ins.regions
        if self.only_yield(then) and not self.only_yield(other):
            self.line(depth, 'if (!(%s)) {' % cond)
            self.region(other, depth + 1, ins)
            self.line(depth, '}')
            return
        self.line(depth, 'if (%s) {' % cond)
        self.region(then, depth + 1, ins)
        if self.only_yield(other):
            self.line(depth, '}')
            return
        self.line(depth, '} else {')
        self.region(other, depth + 1, ins)
        self.line(depth, '}')

    def enter_loop(self, ins, depth):
        if ins.op != 'for.range':
            self.declare_results(ins, depth)
        self.loops = list(self.loops) + [ins]

    def leave_loop(self):
        self.loops = self.loops[:-1]

    def emit_loop(self, ins, depth, inits):
        self.enter_loop(ins, depth)
        for a, v in zip(ins.regions[0].args, inits):
            self.line(depth, '%s %s = %s;' % (ctype(a.type), self.fresh(a), v))
        tag = self.open_loop_roots(ins, depth)
        self.line(depth, 'for (;;) {')
        if tag:
            self.reset_roots(tag, depth + 1)
        self.region(ins.regions[0], depth + 1, ins)
        self.line(depth, '}')
        if tag:
            self.line(depth, '}')
        self.leave_loop()

    def emit_for(self, ins, depth, o):
        lo, hi, step = o[:3]
        body = ins.regions[0]
        self.enter_loop(ins, depth)
        for a, v in zip(body.args[1:], o[3:]):
            self.line(depth, '%s %s = %s;' % (ctype(a.type), self.fresh(a), v))
        index = self.fresh(body.args[0])
        tag = self.open_loop_roots(ins, depth)
        if self.const_of(ins.operands[2]) == 1:
            self.line(depth, 'for (int64_t %s = %s; %s < %s; %s += 1) {' % (index, lo, index, hi, index))
        else:
            self.parts.add('RANGEITER')
            count, k = 'ir%d' % (self.count + 1), 'ir%d' % (self.count + 2)
            self.count += 2
            self.line(depth, 'int64_t %s = ail_range_count(%s, %s, %s);' % (count, lo, hi, step))
            self.line(depth, 'for (int64_t %s = 0; %s < %s; %s++) {' % (k, k, count, k))
            self.line(depth + 1, 'int64_t %s = ail_range_value(%s, %s, %s);' % (index, lo, step, k))
        if tag:
            self.reset_roots(tag, depth + 1)
        self.region(body, depth + 1, ins)
        self.line(depth, '}')
        if tag:
            self.line(depth, '}')
        for r, a in zip(ins.results, body.args[1:]):
            self.names[r] = self.names[a]       # whether it ran out or broke, the carried variables
        self.leave_loop()

    @staticmethod
    def _own_exits(region):
        """break/continue instructions of the loop whose body is `region` (not nested loops')."""
        for i in region.instrs:
            if i.op in ('break', 'continue'):
                yield i
            if i.op == 'if':
                for r in i.regions:
                    for x in Emitter._own_exits(r):
                        yield x


def emit_function(fn, pending=(), checked=False, summaries=None, unwind_name=None, listval=None):
    """(signature text, function definition text, runtime needs {'parts','need','floor',
    'pending'}). `pending` lists the callees that have an exception entry point; the result's
    `pending` says whether this function has one too (then its text defines `<sym>__ir` and, under
    the function's own name, the wrapper legacy callers use)."""
    em = Emitter(fn, pending, checked, summaries, unwind_name, listval)
    sig, text = em.emit()
    return sig, text, {'parts': em.parts, 'need': em.need, 'floor': em.floor, 'pending': em.is_pending,
                       'byval': em.byval}
