"""The S0 verifier (design §2.5.5, structural part).

Checked for every function:
  * types are well formed (§2.2) and, at stage S0, scalar or places of scalars;
  * SSA: every value is defined exactly once and every use is in scope (defined earlier in the
    same region or in an enclosing one, a block argument of an enclosing region, or a parameter);
  * every op is known; ops of later stages are refused by name and stage;
  * operand/result counts and types per op;
  * every region ends in exactly one terminator and has no other; `yield` only directly in an
    `if` region and matching its results; `break`/`continue` only inside a loop, matching the
    loop's results / carried values; `return` matching the function's results;
  * block arguments: a `loop` body takes the carried values, a `for.range` body takes the i64
    index then the carried values;
  * `local.alloc` only in the function's top region; `load`/`store` through places of the right
    element type;
  * calls match the callee's signature (an IR function of the program or a declared extern);
  * the declared effect summary, if any, covers what the body may do.
Ownership rules (owners consumed once, borrows B1-B4, box counts) apply to owned values, which
S0 does not have; they arrive with S3.
"""
from . import ir as I
from . import effects as E

S0_TYPES = frozenset([I.I1, I.I64, I.F64])
# S1 adds read-only bytes views and numeric lists / struct objects reached through borrows
S1_TYPES = S0_TYPES | frozenset([I.T('bytes'), I.T('obj', I.T('list', I.I64)),
                                 I.T('obj', I.T('list', I.F64)), I.T('span', I.I64), I.T('span', I.F64),
                                 I.T('span', I.T('u8')), I.T('obj', I.T('bytearray'))])


class _Checker(object):
    def __init__(self, fn, program, stage):
        self.fn = fn
        self.program = program
        self.stage = stage
        self.errors = []
        self.defined = set()

    def err(self, where, msg):
        self.errors.append('%s: %s: %s' % (self.fn.name, where, msg))

    def check_type(self, t, where):
        errs = I.type_errors(t)
        for e in errs:
            self.err(where, e)
        if errs:
            return
        base = t.pointee if t.is_place else t
        if self.stage == 'S0' and base not in S0_TYPES:
            self.err(where, 'type %s is not in the S0 subset (i1, i64, f64 and places of them)' % t)
        elif self.stage == 'S1' and base not in S1_TYPES and not (
                base.head == 'obj' and base.args[0].head == 'class'):
            self.err(where, 'type %s is not in the S1 subset' % t)

    def define(self, v, where):
        if not isinstance(v, I.Value):
            self.err(where, 'not a value: %r' % (v,))
            return
        if v in self.defined:
            self.err(where, 'value %r defined more than once' % (v,))
        self.defined.add(v)
        self.check_type(v.type, where)

    # ------------------------------------------------------------------ structure
    def run(self):
        fn = self.fn
        for t in fn.results:
            self.check_type(t, 'result type')
        scope = set()
        for p in fn.params:
            self.define(p, 'parameter')
            scope.add(p)
        if len(fn.param_names) != len(fn.params):
            self.err('signature', '%d parameter names for %d parameters'
                     % (len(fn.param_names), len(fn.params)))
        if fn.body.args:
            self.err('body', 'the function body takes no block arguments (parameters are separate)')
        self.region(fn.body, scope, [('func', None)], top=True)
        if fn.effects is not None:
            actual = E.summarize(fn, self.program)
            if not fn.effects.covers(actual):
                self.err('effects', 'declared summary %r does not cover the body %r'
                         % (fn.effects, actual))
        return self.errors

    def region(self, region, scope, stack, top=False):
        """`stack` lists the enclosing region owners innermost last: ('func'|'if'|op, instr)."""
        scope = set(scope)
        for a in region.args:
            self.define(a, 'block argument')
            scope.add(a)
        if not region.instrs:
            self.err(stack[-1][0], 'empty region (a region ends in a terminator)')
            return
        for k, ins in enumerate(region.instrs):
            last = k == len(region.instrs) - 1
            where = '%s #%d' % (ins.op, k)
            if not isinstance(ins, I.Instr):
                self.err(where, 'not an instruction')
                continue
            self.instr(ins, scope, stack, where, top)
            term = ins.op in I.OPS and I.OPS[ins.op][3]
            if term and not last:
                self.err(where, 'terminator in the middle of a region')
            if last and not term:
                self.err(where, 'region does not end in a terminator')
            for r in ins.results:
                scope.add(r)

    def instr(self, ins, scope, stack, where, top):
        op = ins.op
        if op in I.RESERVED:
            self.err(where, 'op %s belongs to stage %s, not %s' % (op, I.RESERVED[op], self.stage))
            return
        if op not in I.OPS:
            self.err(where, 'unknown op %r' % op)
            return
        nmin, nmax, nregions, _term = I.OPS[op]
        for v in ins.operands:
            if v not in scope:
                self.err(where, 'operand %r is not defined in scope' % (v,))
        if len(ins.operands) < nmin or (nmax is not None and len(ins.operands) > nmax):
            self.err(where, 'wrong number of operands (%d)' % len(ins.operands))
            return
        if nregions == -1:
            if not ins.regions:
                self.err(where, 'expected at least one region')
                return
        elif len(ins.regions) != nregions:
            self.err(where, 'expected %d region(s), found %d' % (nregions, len(ins.regions)))
            return
        for r in ins.results:
            self.define(r, where)
        getattr(self, 'op_' + op.replace('.', '_'), self.op_generic)(ins, scope, stack, where, top)

    # ------------------------------------------------------------------ helpers
    def want(self, where, cond, msg):
        if not cond:
            self.err(where, msg)
        return cond

    def nresults(self, ins, where, n):
        return self.want(where, len(ins.results) == n, 'expected %d result(s), found %d'
                         % (n, len(ins.results)))

    def types(self, vals):
        return [v.type for v in vals]

    # ------------------------------------------------------------------ ops
    def op_generic(self, ins, scope, stack, where, top):
        self.err(where, 'no typing rule for %s' % ins.op)

    def op_const(self, ins, scope, stack, where, top):
        if not self.nresults(ins, where, 1):
            return
        t, value = ins.result.type, ins.attrs.get('value')
        if t == I.I1:
            self.want(where, isinstance(value, bool), 'i1 constant must be true or false')
        elif t.is_int:
            ok = isinstance(value, int) and not isinstance(value, bool)
            if self.want(where, ok, 'integer constant expected, found %r' % (value,)) and t == I.I64:
                self.want(where, -(1 << 63) <= value < (1 << 63), 'constant out of i64 range')
        elif t.is_float:
            self.want(where, isinstance(value, float), 'float constant expected, found %r' % (value,))
        else:
            self.err(where, 'constants are scalars in S0')

    def _binary(self, ins, where, operand_types, result):
        if not self.nresults(ins, where, 1):
            return
        a, b = ins.operands
        self.want(where, a.type == b.type and a.type in operand_types,
                  'operands must be the same type of %s, found %s, %s'
                  % ('/'.join(map(str, operand_types)), a.type, b.type))
        want = result if result is not None else a.type
        self.want(where, ins.result.type == want, 'result must be %s, found %s' % (want, ins.result.type))

    def _mode(self, ins, where, modes=I.ARITH_MODES):
        mode = ins.attrs.get('mode')
        self.want(where, mode in modes, 'mode must be one of %s, found %r' % ('/'.join(modes), mode))

    def op_int_binary(self, ins, scope, stack, where, top):
        if ins.op in ('and', 'or', 'xor'):
            return self._binary(ins, where, (I.I64, I.I1), None)
        self._mode(ins, where, ('ck', 'nonneg') if ins.op in ('floordiv', 'floormod') else I.ARITH_MODES)
        if ins.attrs.get('mode') == 'nonneg':
            d = E.const_value(ins.operands[1], E.defs_of(self.fn))
            self.want(where, isinstance(d, int) and not isinstance(d, bool) and d > 0,
                      'mode nonneg needs a positive constant divisor')
        self._binary(ins, where, (I.I64,), I.I64)

    def op_float_binary(self, ins, scope, stack, where, top):
        self._binary(ins, where, (I.F64,), I.F64)

    def op_neg(self, ins, scope, stack, where, top):
        self._mode(ins, where)
        self._unary(ins, where, I.I64, I.I64)

    def op_inv(self, ins, scope, stack, where, top):
        self._unary(ins, where, I.I64, I.I64)

    def op_fneg(self, ins, scope, stack, where, top):
        self._unary(ins, where, I.F64, I.F64)

    def op_zext(self, ins, scope, stack, where, top):
        self._unary(ins, where, I.I1, I.I64)

    def op_sitofp(self, ins, scope, stack, where, top):
        self._unary(ins, where, I.I64, I.F64)

    def op_fptosi(self, ins, scope, stack, where, top):
        self._mode(ins, where, ('ck',))
        self._unary(ins, where, I.F64, I.I64)

    def _unary(self, ins, where, src, dst):
        if not self.nresults(ins, where, 1):
            return
        self.want(where, ins.operands[0].type == src, 'operand must be %s, found %s'
                  % (src, ins.operands[0].type))
        self.want(where, ins.result.type == dst, 'result must be %s, found %s' % (dst, ins.result.type))

    def op_cmp(self, ins, scope, stack, where, top):
        self._binary(ins, where, (I.I64, I.F64, I.I1), I.I1)

    def op_select(self, ins, scope, stack, where, top):
        if not self.nresults(ins, where, 1):
            return
        c, a, b = ins.operands
        self.want(where, c.type == I.I1, 'select condition must be i1')
        self.want(where, a.type == b.type == ins.result.type, 'select arms and result must agree')

    def op_local_alloc(self, ins, scope, stack, where, top):
        self.want(where, top, 'local.alloc only in the function body region')
        if self.nresults(ins, where, 1):
            self.want(where, ins.result.type.is_place, 'local.alloc yields a place')
        self.want(where, isinstance(ins.attrs.get('name'), str) and ins.attrs['name'].isidentifier(),
                  'local.alloc needs a name')

    def op_load(self, ins, scope, stack, where, top):
        if not self.nresults(ins, where, 1):
            return
        p = ins.operands[0]
        if self.want(where, p.type.is_place, 'load from a non-place'):
            self.want(where, ins.result.type == p.type.pointee, 'load result type mismatch')

    def op_store(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        p, v = ins.operands
        if self.want(where, p.type.is_place, 'store to a non-place'):
            self.want(where, v.type == p.type.pointee, 'store of %s into place<%s>'
                      % (v.type, p.type.pointee))

    def op_call(self, ins, scope, stack, where, top):
        sym = ins.attrs.get('callee')
        sig = self.program.callee_type(sym) if self.program is not None else None
        if not self.want(where, sig is not None, 'call to unknown function %r' % (sym,)):
            return
        params, results = sig.args[0].args, sig.args[1].args
        self.want(where, list(self.types(ins.operands)) == list(params),
                  'arguments (%s) do not match %s' % (', '.join(map(str, self.types(ins.operands))), sig))
        self.want(where, list(self.types(ins.results)) == list(results),
                  'results do not match %s' % sig)

    def op_rt(self, ins, scope, stack, where, top):
        entry = E.RUNTIME.get(ins.attrs.get('callee'))
        if not self.want(where, entry is not None, 'unknown runtime entry %r' % ins.attrs.get('callee')):
            return
        params, results, _ = entry
        self.want(where, tuple(self.types(ins.operands)) == tuple(params), 'runtime argument mismatch')
        self.want(where, tuple(self.types(ins.results)) == tuple(results), 'runtime result mismatch')

    def _index_mode(self, ins, where):
        self.want(where, ins.attrs.get('mode') in I.INDEX_MODES,
                  'index mode must be one of %s' % '/'.join(I.INDEX_MODES))

    def op_bytes_len(self, ins, scope, stack, where, top):
        self._unary(ins, where, I.T('bytes'), I.I64)

    def op_bytes_get(self, ins, scope, stack, where, top):
        self._index_mode(ins, where)
        if self.nresults(ins, where, 1):
            b, i = ins.operands
            self.want(where, b.type == I.T('bytes') and i.type == I.I64, 'bytes.get takes (bytes, i64)')
            self.want(where, ins.result.type == I.I64, 'bytes.get yields i64')

    def _list_elem(self, v):
        t = v.type
        if t.head == 'obj' and t.args[0].head == 'list':
            return t.args[0].args[0]
        return None

    def op_list_len(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            self.want(where, self._list_elem(ins.operands[0]) is not None, 'list.len of a non-list')
            self.want(where, ins.result.type == I.I64, 'list.len yields i64')

    def op_list_get(self, ins, scope, stack, where, top):
        self._index_mode(ins, where)
        if self.nresults(ins, where, 1):
            elem = self._list_elem(ins.operands[0])
            self.want(where, elem is not None and ins.operands[1].type == I.I64, 'list.get takes (list, i64)')
            self.want(where, ins.result.type == elem, 'list.get yields the element type')

    def op_list_set(self, ins, scope, stack, where, top):
        self._index_mode(ins, where)
        self.nresults(ins, where, 0)
        elem = self._list_elem(ins.operands[0])
        self.want(where, elem is not None and ins.operands[1].type == I.I64
                  and ins.operands[2].type == elem, 'list.set takes (list, i64, element)')

    def op_list_push(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        elem = self._list_elem(ins.operands[0])
        self.want(where, elem is not None and ins.operands[1].type == elem, 'list.push takes (list, element)')

    def op_list_pop(self, ins, scope, stack, where, top):
        elem = self._list_elem(ins.operands[0])
        self.want(where, elem is not None, 'list.pop of a non-list')
        if self.nresults(ins, where, 1):
            self.want(where, ins.result.type == elem, 'list.pop yields the element type')

    def op_list_clear(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        self.want(where, self._list_elem(ins.operands[0]) is not None, 'list.clear of a non-list')

    def op_field_list(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            o = ins.operands[0].type
            self.want(where, o.head == 'obj' and o.args[0].head == 'class', 'field.list of a non-object')
            self.want(where, self._list_elem(ins.result) is not None, 'field.list yields a list borrow')

    def _span_elem(self, v):
        """The element type a span op reads or writes (a byte reads as i64)."""
        if v.type.head != 'span':
            return None
        return I.I64 if v.type.args[0] == I.T('u8') else v.type.args[0]

    def _is_ba(self, v):
        return v.type == I.T('obj', I.T('bytearray'))

    def op_span_of(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            src = ins.operands[0]
            elem = I.T('u8') if self._is_ba(src) else self._list_elem(src)
            self.want(where, elem is not None and ins.result.type == I.T('span', elem),
                      'span.of takes a list or bytearray and yields span<element>')

    def op_ba_len(self, ins, scope, stack, where, top):
        self._unary(ins, where, I.T('obj', I.T('bytearray')), I.I64)

    def op_ba_get(self, ins, scope, stack, where, top):
        self._index_mode(ins, where)
        if self.nresults(ins, where, 1):
            self.want(where, self._is_ba(ins.operands[0]) and ins.operands[1].type == I.I64
                      and ins.result.type == I.I64, 'ba.get takes (bytearray, i64) and yields i64')

    def op_ba_set(self, ins, scope, stack, where, top):
        self._index_mode(ins, where)
        self.nresults(ins, where, 0)
        self.want(where, self._is_ba(ins.operands[0]) and ins.operands[1].type == I.I64
                  and ins.operands[2].type == I.I64, 'ba.set takes (bytearray, i64, i64)')

    def op_ba_push(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        self.want(where, self._is_ba(ins.operands[0]) and ins.operands[1].type == I.I64,
                  'ba.push takes (bytearray, i64)')

    def op_span_len(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            self.want(where, self._span_elem(ins.operands[0]) is not None and ins.result.type == I.I64,
                      'span.len takes a span and yields i64')

    def op_span_get(self, ins, scope, stack, where, top):
        self._index_mode(ins, where)
        if self.nresults(ins, where, 1):
            elem = self._span_elem(ins.operands[0])
            self.want(where, elem is not None and ins.operands[1].type == I.I64 and ins.result.type == elem,
                      'span.get takes (span, i64) and yields the element')

    def op_span_set(self, ins, scope, stack, where, top):
        self._index_mode(ins, where)
        self.nresults(ins, where, 0)
        elem = self._span_elem(ins.operands[0])
        self.want(where, elem is not None and ins.operands[1].type == I.I64 and ins.operands[2].type == elem,
                  'span.set takes (span, i64, element)')

    def op_field_get(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            o = ins.operands[0].type
            self.want(where, o.head == 'obj' and o.args[0].head == 'class', 'field.get of a non-object')
            self.want(where, isinstance(ins.attrs.get('name'), str), 'field.get needs a name')

    def op_field_set(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        o = ins.operands[0].type
        self.want(where, o.head == 'obj' and o.args[0].head == 'class', 'field.set of a non-object')
        self.want(where, isinstance(ins.attrs.get('name'), str), 'field.set needs a name')

    def op_if(self, ins, scope, stack, where, top):
        self.want(where, ins.operands[0].type == I.I1, 'if condition must be i1')
        for r in ins.regions:
            self.want(where, not r.args, 'if regions take no block arguments')
            self.region(r, scope, stack + [('if', ins)])

    def op_loop(self, ins, scope, stack, where, top):
        carried = self.types(ins.operands)
        body = ins.regions[0]
        self.want(where, self.types(body.args) == carried,
                  'loop body arguments must match the carried values')
        self.region(body, scope, stack + [('loop', ins)])

    def op_for_range(self, ins, scope, stack, where, top):
        lo, hi, step = ins.operands[:3]
        self.want(where, lo.type == hi.type == step.type == I.I64, 'for.range bounds must be i64')
        carried = self.types(ins.operands[3:])
        body = ins.regions[0]
        self.want(where, self.types(body.args) == [I.I64] + carried,
                  'for.range body arguments must be (i64, carried values...)')
        self.region(body, scope, stack + [('for.range', ins)])

    def _innermost_loop(self, stack):
        for kind, owner in reversed(stack):
            if kind in I.LOOP_OPS:
                return owner
            if kind not in ('if', 'try', 'handler', 'finally'):
                return None
        return None

    def op_yield(self, ins, scope, stack, where, top):
        kind, owner = stack[-1]
        if kind in ('try', 'handler', 'finally'):
            self.want(where, not ins.operands, 'a try region yields no values')
            return
        if not self.want(where, kind == 'if', 'yield outside an if or try region'):
            return
        self.want(where, self.types(ins.operands) == self.types(owner.results),
                  'yield (%s) does not match the if results (%s)'
                  % (', '.join(map(str, self.types(ins.operands))),
                     ', '.join(map(str, self.types(owner.results)))))

    def op_break(self, ins, scope, stack, where, top):
        loop = self._innermost_loop(stack)
        if not self.want(where, loop is not None, 'break outside a loop'):
            return
        self.want(where, self.types(ins.operands) == self.types(loop.results),
                  'break values do not match the loop results')

    def op_continue(self, ins, scope, stack, where, top):
        loop = self._innermost_loop(stack)
        if not self.want(where, loop is not None, 'continue outside a loop'):
            return
        carried = loop.operands if loop.op == 'loop' else loop.operands[3:]
        self.want(where, self.types(ins.operands) == self.types(carried),
                  'continue values do not match the carried values')

    def op_return(self, ins, scope, stack, where, top):
        self.want(where, self.types(ins.operands) == list(self.fn.results),
                  'return (%s) does not match the function results (%s)'
                  % (', '.join(map(str, self.types(ins.operands))),
                     ', '.join(map(str, self.fn.results))))

    def op_unreachable(self, ins, scope, stack, where, top):
        pass

    # ------------------------------------------------------------------ exceptions (S2)
    def op_raise(self, ins, scope, stack, where, top):
        code, name, form = ins.attrs.get('code'), ins.attrs.get('name'), ins.attrs.get('form')
        self.want(where, isinstance(code, int) and not isinstance(code, bool) and 1 <= code <= 10,
                  'raise needs an exception code 1..10')
        self.want(where, isinstance(name, str) and name.isidentifier(), 'raise needs an exception name')
        self.want(where, form in ('name', 'new', 'msg'),
                  'raise form is name (raise E), new (raise E()) or msg (raise E("..."))')
        self.want(where, (form == 'msg') == isinstance(ins.attrs.get('msg'), str),
                  'raise msg is a string exactly for the msg form')

    def op_reraise(self, ins, scope, stack, where, top):
        self.want(where, any(kind == 'handler' for kind, _ in stack),
                  'reraise outside an except handler')

    def op_try(self, ins, scope, stack, where, top):
        kind = ins.attrs.get('kind')
        if not self.want(where, kind in ('catch', 'finally'), 'try kind must be catch or finally'):
            return
        self.nresults(ins, where, 0)
        if kind == 'finally':
            self.want(where, len(ins.regions) == 2, 'a finally try has a body and a finally region')
        else:
            codes = ins.attrs.get('codes')
            ok = (isinstance(codes, list) and len(codes) == len(ins.regions) - 1 and len(codes) >= 1
                  and all(isinstance(c, list) and c and all(isinstance(x, int) and not isinstance(x, bool)
                                                            and 1 <= x <= 10 for x in c) for c in codes))
            self.want(where, ok, 'a catch try lists the exception codes of every handler')
            if ok:
                flat = [x for c in codes for x in c]
                self.want(where, len(flat) == len(set(flat)), 'an exception code is named by two handlers')
        for k, r in enumerate(ins.regions):
            self.want(where, not r.args, 'try regions take no block arguments')
            role = 'try' if k == 0 else ('finally' if kind == 'finally' else 'handler')
            self.region(r, scope, stack + [(role, ins)])


for _name in I.INT_BINARY:
    setattr(_Checker, 'op_' + _name, _Checker.op_int_binary)
for _name in I.FLOAT_BINARY:
    setattr(_Checker, 'op_' + _name, _Checker.op_float_binary)
for _pred in I.CMP_PREDICATES:
    setattr(_Checker, 'op_cmp_' + _pred, _Checker.op_cmp)


def verify_function(fn, program=None, stage='S1'):
    """A list of error messages (empty when the function is well formed)."""
    return _Checker(fn, program, stage).run()


def verify_program(program, stage='S1'):
    errors = []
    for sym in sorted(program.functions):
        errors.extend(verify_function(program.functions[sym], program, stage))
    return errors


def check(fn_or_program, program=None, stage='S1'):
    """Raise IRError with every message if the function or program is malformed."""
    if isinstance(fn_or_program, I.Program):
        errors = verify_program(fn_or_program, stage)
    else:
        errors = verify_function(fn_or_program, program, stage)
    if errors:
        raise I.IRError('\n'.join(errors))
