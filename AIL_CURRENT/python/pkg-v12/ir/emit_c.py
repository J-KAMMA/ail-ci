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


def ctype(t):
    if t in (I.I64, I.I1):
        return 'int64_t'
    if t == I.F64:
        return 'double'
    if t == BYTES:
        return 'ail_bytes'
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


def signature(fn):
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
    params = ', '.join(decls)
    prefix = LINKAGE_PREFIX.get(fn.attrs.get('linkage', 'extern'))
    if prefix is None:
        raise I.IRError('unknown linkage %r' % fn.attrs.get('linkage'))
    return '%s%s %s(%s)' % (prefix, ret, fn.sym, params or 'void')


class Emitter(object):
    def __init__(self, fn):
        self.fn = fn
        self.names = {}
        self.defs = E.defs_of(fn)
        self.lines = []
        self.count = 0
        self.parts = set()
        self.need = set()
        self.floor = set()
        self.labels = 0
        self.span_names = {}
        abi = fn.attrs.get('abi') or ['value'] * len(fn.params)
        for p, n, a in zip(fn.params, fn.param_names, abi):
            self.names[p] = 'v_' + n
            if a == 'array':
                self.span_names[p] = ('((int64_t *)v_%s)' % n, 'v_%s_len' % n)
            elif a == 'flist':
                self.span_names[p] = ('v_%s.p' % n, 'v_%s.n' % n)

    # ------------------------------------------------------------------ naming
    def fresh(self, v):
        self.count += 1
        self.names[v] = 'ir%d' % self.count
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
            return self.names[v]
        except KeyError:
            raise I.IRError('value used before it was emitted: %r' % (v,))

    def line(self, depth, text):
        self.lines.append('    ' * depth + text)

    def use(self, *helpers):
        self.need.update(helpers)
        self.need.add('ail_die')

    # ------------------------------------------------------------------ function
    def emit(self):
        fn = self.fn
        sig = signature(fn)
        params = set(fn.param_names)
        for ins in fn.body.instrs:
            if ins.op == 'local.alloc':
                name = ins.attrs['name']
                c = ('l_' if name in params else 'v_') + name
                self.names[ins.result] = c
                self.line(1, '%s %s = 0;' % (ctype(ins.result.type.pointee), c))
        if fn.attrs.get('recursive'):
            self.parts.add('RECDEPTH')
        self.region(fn.body, 1, None)
        return sig, '%s {\n%s\n}\n' % (sig, '\n'.join(self.lines))

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
            return
        if op == 'span.len':
            return self.assign_new(depth, ins.result, self.span_names[ins.operands[0]][1])
        if op in ('span.get', 'span.set'):
            elem = ins.operands[0].type.args[0]
            f = 'flist' if elem == I.F64 else 'list'
            self.parts.add('NUMVIEW')
            sp, sn = self.span_names[ins.operands[0]][:2]
            if op == 'span.get':
                if ins.attrs.get('mode') == 'nck':
                    return self.assign_new(depth, ins.result, '%s[%s]' % (sp, o[1]))
                return self.assign_new(depth, ins.result, 'ail_%s_view_get(%s, %s, %s)' % (f, sp, sn, o[1]))
            if ins.attrs.get('mode') == 'nck':
                return self.line(depth, '%s[%s] = %s;' % (sp, o[1], o[2]))
            return self.line(depth, 'ail_%s_view_set(%s, %s, %s, %s);' % (f, sp, sn, o[1], o[2]))
        if op in ('list.len', 'list.get', 'list.set', 'list.push', 'list.pop', 'list.clear'):
            return self.list_op(ins, depth, o)
        if op == 'call':
            abi = ins.attrs.get('abi') or ['value'] * len(o)
            parts = []
            for v, text, a in zip(ins.operands, o, abi):
                if a == 'array':
                    parts.append('%s, %s_len' % (text, text))
                else:
                    parts.append(text)
            text = '%s(%s)' % (ins.attrs['callee'], ', '.join(parts))
            if ins.results:
                return self.assign_new(depth, ins.result, text)
            return self.line(depth, text + ';')
        if op == 'rt':
            callee = ins.attrs['callee']
            if callee == 'ail_depth_enter':
                self.parts.add('RECDEPTH')
                return self.line(depth, 'if (++ail_depth > AIL_MAX_RECURSION_DEPTH) '
                                        'ail_die("recursion depth exceeded");')
            if callee == 'ail_depth_leave':
                return self.line(depth, 'ail_depth--;')
            raise I.IRError('no C for runtime entry %r' % callee)
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
        if op == 'break':
            loop = self.loops[-1]
            if loop.op == 'for.range':
                # a for.range's results are its carried variables: a break stores its values there
                args = loop.regions[0].args[1:]
                self.parallel_assign(depth, [self.names[a] for a in args], o, [a.type for a in args])
                return self.line(depth, 'break;')
            for r, v in zip(loop.results, o):
                self.line(depth, '%s = %s;' % (self.names[r], v))
            return self.line(depth, 'break;')
        if op == 'continue':
            loop = self.loops[-1]
            args = loop.regions[0].args[1:] if loop.op == 'for.range' else loop.regions[0].args
            self.parallel_assign(depth, [self.names[a] for a in args], o, [a.type for a in args])
            keep = os.environ.get('AIL_IR_TRAILING_CONTINUE', 'loop,for.range')
            if owner is loop and loop.regions[0].instrs[-1] is ins and loop.op not in keep.split(','):
                return          # the end of the C loop body continues anyway (and a trailing
                                # `continue;` changes GCC's block layout: +1 jump per iteration)
            return self.line(depth, 'continue;')
        if op == 'return':
            return self.line(depth, 'return %s;' % o[0] if o else 'return;')
        if op == 'unreachable':
            return self.line(depth, '__builtin_unreachable();')
        raise I.IRError('no C for op %s' % op)

    def list_op(self, ins, depth, o):
        """Numeric list fields reached through a struct borrow, with the legacy path's own
        helpers (same checks, same messages): ail_list_span_* reads, ail_numfield_* writes."""
        op = ins.op
        elem = ins.operands[0].type.args[0].args[0]
        f = 'flist' if elem == I.F64 else 'list'
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
            self.line(depth, '%s %s = 0;' % (ctype(r.type), self.fresh(r)))

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
        self.line(depth, 'for (;;) {')
        self.region(ins.regions[0], depth + 1, ins)
        self.line(depth, '}')
        self.leave_loop()

    def emit_for(self, ins, depth, o):
        lo, hi, step = o[:3]
        body = ins.regions[0]
        self.enter_loop(ins, depth)
        for a, v in zip(body.args[1:], o[3:]):
            self.line(depth, '%s %s = %s;' % (ctype(a.type), self.fresh(a), v))
        index = self.fresh(body.args[0])
        if self.const_of(ins.operands[2]) == 1:
            self.line(depth, 'for (int64_t %s = %s; %s < %s; %s += 1) {' % (index, lo, index, hi, index))
        else:
            self.parts.add('RANGEITER')
            count, k = 'ir%d' % (self.count + 1), 'ir%d' % (self.count + 2)
            self.count += 2
            self.line(depth, 'int64_t %s = ail_range_count(%s, %s, %s);' % (count, lo, hi, step))
            self.line(depth, 'for (int64_t %s = 0; %s < %s; %s++) {' % (k, k, count, k))
            self.line(depth + 1, 'int64_t %s = ail_range_value(%s, %s, %s);' % (index, lo, step, k))
        self.region(body, depth + 1, ins)
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


def emit_function(fn):
    """(signature text, function definition text, runtime needs {'parts','need','floor'})."""
    em = Emitter(fn)
    sig, text = em.emit()
    return sig, text, {'parts': em.parts, 'need': em.need, 'floor': em.floor}
