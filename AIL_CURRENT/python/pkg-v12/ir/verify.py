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
from . import rtc

_LIST_I64 = I.T('obj', I.T('list', I.I64))
_LIST_F64 = I.T('obj', I.T('list', I.F64))
_LIST_STR = I.T('obj', I.T('list', I.STRV))
_BA = I.T('obj', I.T('bytearray'))


class _Listy(object):
    """The owned-list types: lists of int, float, str, and lists of scalar records."""
    def __contains__(self, t):
        return t in (_LIST_I64, _LIST_F64, _LIST_STR) or I.rec_elem(t) is not None


_LISTY = _Listy()
S0_TYPES = frozenset([I.I1, I.I64, I.F64])
# S1 adds read-only bytes views and numeric lists / struct objects reached through borrows
S1_TYPES = S0_TYPES | frozenset([I.T('bytes'), I.T('obj', I.T('list', I.I64)),
                                 I.T('obj', I.T('list', I.F64)), I.T('span', I.I64), I.T('span', I.F64),
                                 I.T('span', I.T('u8')), I.T('obj', I.T('bytearray')), I.STRV,
                                 I.T('obj', I.T('list', I.STRV))])


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
        elif self.stage == 'S1' and base not in S1_TYPES and I.rec_elem(base) is None and base != I.DICT_II and base != I.PLIST and not (
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
        if not self.errors:
            self.check_spans()
            self.check_ownership()
        if fn.effects is not None:
            actual = E.summarize(fn, self.program)
            if not fn.effects.covers(actual):
                self.err('effects', 'declared summary %r does not cover the body %r'
                         % (fn.effects, actual))
        return self.errors

    # ------------------------------------------------------------------ ownership of lists (S3a)
    _RESIZERS = ('list.push', 'list.pop', 'list.clear', 'list.reset', 'list.repeat', 'list.lit',
                 'list.reserve', 'list.move', 'list.call', 'list.copy', 'list.rt', 'list.sortperm',
                 'rec.push', 'rec.pop')

    def _resizes(self, ins, root, defs):
        """Whether `ins` may change the length or storage of the list rooted at `root` (an owned
        local: only an operation naming that very list can; a call cannot, it has no way to name it)."""
        if ins.op not in self._RESIZERS:
            return False
        refs = ins.operands[:2] if ins.op in ('list.move', 'list.copy') else ins.operands[:1]
        return any(E._root(r, self.fn, defs) in (root, 'Any') for r in refs)

    def check_ownership(self):
        """The invariants of S3a's single-owner lists: a list reference (borrow) lives only as the
        operand of the instruction that uses it -- it is never stored, carried by a loop, yielded
        by a region or selected -- so no second owner exists; the function lists its owned places."""
        fn = self.fn
        listy = _LISTY
        places = []
        for ins in I.walk(fn.body):
            if ins.op == 'local.alloc' and ins.result.type.pointee in listy:
                places.append(ins.attrs.get('name'))
            if ins.op in ('store', 'load') and ins.operands[0].type.is_place \
                    and ins.operands[0].type.pointee in listy:
                self.err(ins.op, 'an owned list is changed by list.* operations, never loaded or stored')
            if ins.op == 'local.alloc' and ins.result.type.pointee in (_BA, I.DICT_II):
                places.append(ins.attrs.get('name'))
            if ins.op in ('store', 'load') and ins.operands[0].type.is_place and ins.operands[0].type.pointee == I.DICT_II:
                self.err(ins.op, 'an owned dictionary is changed by dict.* operations, never loaded or stored')
            if ins.op == 'store' and ins.operands[0].type.is_place and ins.operands[0].type.pointee == _BA:
                self.err(ins.op, 'an owned bytearray is replaced by ba.new, never stored (the reference count)')
            carried = []
            if ins.op in ('yield', 'break', 'continue', 'select'):
                carried = ins.operands
            elif ins.op == 'loop':
                carried = ins.operands
            elif ins.op == 'for.range':
                carried = ins.operands[3:]
            if any(v.type in listy for v in carried) or (
                    ins.op in ('if', 'loop', 'for.range') and any(r.type in listy for r in ins.results)):
                self.err(ins.op, 'a list reference cannot be carried, yielded or selected (it would be a second owner)')
        want = sorted(n for n in places if n)
        have = sorted(fn.attrs.get('owned') or [])
        if want != have:
            self.err('attrs', 'owned places %s are not the function\'s list places %s' % (have, want))
        if bool(fn.results and fn.results[0] in listy) != bool(fn.attrs.get('ret_list')):
            self.err('attrs', 'ret_list must be set exactly when the function returns a list')

    def check_spans(self):
        """A span (data pointer and length, read once) over an owned list must not be used after an
        operation that may resize or replace that list: between `span.of` and the last use of the
        span, in program order and around any loop the two share, nothing resizes its list."""
        fn = self.fn
        defs = E.defs_of(fn)

        def uses(region, v):
            return any(v in i.operands for i in I.walk(region))

        def visit(region):
            for k, ins in enumerate(region.instrs):
                if ins.op == 'span.of':
                    root = E._root(ins.operands[0], fn, defs)
                    if root.startswith('Own('):
                        s = ins.result
                        last = -1
                        for j in range(k + 1, len(region.instrs)):
                            if uses(I.Region([], [region.instrs[j]]), s):
                                last = j
                        for j in range(k + 1, last + 1):
                            for sub in I.walk(I.Region([], [region.instrs[j]])):
                                if self._resizes(sub, root, defs):
                                    self.err(sub.op, 'resizes %s while a span over it is still in use' % root)
                for r in ins.regions:
                    visit(r)
        visit(fn.body)

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
            # (a constant divisor is checked here; a variable one was proven positive by the range pass)
            d = E.const_value(ins.operands[1], E.defs_of(self.fn))
            self.want(where, d is None or (isinstance(d, int) and not isinstance(d, bool) and d > 0),
                      'mode nonneg needs a positive divisor')
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

    def op_global_load(self, ins, scope, stack, where, top):
        self.want(where, isinstance(ins.attrs.get('name'), str) and ins.attrs['name'].isidentifier(),
                  'global.load needs a variable name')
        if self.nresults(ins, where, 1):
            self.want(where, ins.result.type in (I.I64, I.F64), 'a module variable is an i64 or an f64')

    def op_global_store(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        self.want(where, isinstance(ins.attrs.get('name'), str) and ins.attrs['name'].isidentifier(),
                  'global.store needs a variable name')
        self.want(where, ins.operands[0].type in (I.I64, I.F64), 'a module variable is an i64 or an f64')

    def op_call(self, ins, scope, stack, where, top):
        sym = ins.attrs.get('callee')
        sig = self.program.callee_type(sym) if self.program is not None else None
        if not self.want(where, sig is not None, 'call to unknown function %r' % (sym,)):
            return
        params, results = sig.args[0].args, sig.args[1].args
        abi = ins.attrs.get('abi') or ['value'] * len(ins.operands)
        ok = len(ins.operands) == len(params) == len(abi)
        for a, p, how in zip(ins.operands, params, abi):
            # an owned list lent to a read-only list parameter (a span in the callee's signature)
            lent = how in ('array', 'flist') and p.head == 'span' and self._is_list_ref(a) \
                and a.type.args[0].args[0] == p.args[0]
            ok = ok and (a.type == p or lent)
        self.want(where, ok, 'arguments (%s) do not match %s' % (', '.join(map(str, self.types(ins.operands))), sig))
        self.want(where, list(self.types(ins.results)) == list(results),
                  'results do not match %s' % sig)

    def op_rt(self, ins, scope, stack, where, top):
        entry = E.RUNTIME.get(ins.attrs.get('callee'))
        if not self.want(where, entry is not None, 'unknown runtime entry %r' % ins.attrs.get('callee')):
            return
        params, results, _ = entry
        spec = E.rtc.ENTRIES.get(ins.attrs.get('callee'))
        if spec is not None and spec['variadic']:
            # one repeated parameter type (str_catn): at least one operand
            self.want(where, len(ins.operands) >= 1 and all(t == params[0] for t in self.types(ins.operands)),
                      'runtime argument mismatch')
        else:
            self.want(where, tuple(self.types(ins.operands)) == tuple(params), 'runtime argument mismatch')
        if spec is not None:
            for a in spec['attrs']:
                self.want(where, a in ins.attrs, 'runtime entry %s needs attribute %s' % (ins.attrs['callee'], a))
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

    # ------------------------------------------------------------------ owned lists (S3a)
    def _is_list_ref(self, v):
        return v.type in _LISTY

    def op_list_ref(self, ins, scope, stack, where, top):
        if not self.nresults(ins, where, 1):
            return
        p = ins.operands[0]
        if self.want(where, p.type.is_place and p.type.pointee in _LISTY,
                     'list.ref takes the place of an owned list'):
            self.want(where, ins.result.type == p.type.pointee, "list.ref yields a borrow of the place's list")
            d = E.defs_of(self.fn).get(p)
            self.want(where, d is not None and d.op == 'local.alloc', 'list.ref of something that is not a local place')

    def op_list_reset(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        self.want(where, self._is_list_ref(ins.operands[0]), 'list.reset takes a list reference')

    def op_list_repeat(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        r, v, n = ins.operands
        self.want(where, self._is_list_ref(r) and v.type == r.type.args[0].args[0] and n.type == I.I64,
                  'list.repeat takes (list, element, i64)')

    def op_list_lit(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        r = ins.operands[0]
        self.want(where, self._is_list_ref(r) and all(v.type == r.type.args[0].args[0] for v in ins.operands[1:]),
                  'list.lit takes (list, elements of the element type...)')

    def op_list_reserve(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        r, n = ins.operands
        self.want(where, self._is_list_ref(r) and n.type == I.I64, 'list.reserve takes (list, i64)')

    def op_list_move(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        d, s = ins.operands
        self.want(where, self._is_list_ref(d) and d.type == s.type, 'list.move takes two lists of one type')
        self.want(where, d is not s, 'list.move of a list into itself')

    # ------------------------------------------------------------------ owned lists of str (S3c-1)
    def op_list_rt(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        callee = ins.attrs.get('callee')
        entry = rtc.LIST_ENTRIES.get(callee)
        if not self.want(where, entry is not None, 'list.rt of an unknown runtime call %r' % (callee,)):
            return
        dst, args = ins.operands[0], ins.operands[1:]
        self.want(where, dst.type == _LIST_STR, 'list.rt fills a list of str')
        self.want(where, list(self.types(args)) == list(entry['params']),
                  'list.rt %s takes (%s)' % (callee, ', '.join(map(str, entry['params']))))

    def op_list_sortperm(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        perm, cols = ins.operands[0], ins.operands[1:]
        self.want(where, perm.type == _LIST_I64, 'list.sortperm fills a list of int')
        self.want(where, all(c.type in (_LIST_I64, _LIST_F64, _LIST_STR) for c in cols),
                  'list.sortperm takes key columns that are lists of int, float or str')
        self.want(where, ins.attrs.get('rev') in (0, 1), 'list.sortperm needs rev = 0 or 1')

    def op_list_permute(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        xs, perm = ins.operands
        self.want(where, xs.type in (_LIST_I64, _LIST_F64, _LIST_STR) and perm.type == _LIST_I64,
                  'list.permute takes (list of int, float or str; list of int)')
        self.want(where, xs is not perm, 'list.permute of a list by itself')

    def op_rec_push(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        r = ins.operands[0]
        e = I.rec_elem(r.type)
        self.want(where, e is not None and list(self.types(ins.operands[1:])) == list(e.args),
                  'rec.push takes (list of records, one value per field)')

    def _rec_key(self, ins, where, e):
        key = ins.attrs.get('key')
        self.want(where, isinstance(key, list) and key and all(isinstance(k, int) and not isinstance(k, bool)
                                                                and 0 <= k < len(e.args) for k in key),
                  'a record heap needs key = field indices')

    def op_rec_up(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        e = I.rec_elem(ins.operands[0].type)
        if self.want(where, e is not None, 'rec.up takes a list of records'):
            self._rec_key(ins, where, e)

    def op_rec_pop(self, ins, scope, stack, where, top):
        e = I.rec_elem(ins.operands[0].type)
        if self.want(where, e is not None, 'rec.pop takes a list of records'):
            self._rec_key(ins, where, e)
            self.want(where, list(self.types(ins.results)) == list(e.args), 'rec.pop yields one value per field')

    def _dict_place(self, ins, where):
        p = ins.operands[0]
        ok = p.type.is_place and p.type.pointee == I.DICT_II
        self.want(where, ok, '%s takes the place of an int dictionary' % ins.op)
        return ok

    def op_dict_has(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1) and self._dict_place(ins, where):
            self.want(where, ins.operands[1].type == I.I64 and ins.result.type == I.I1, 'dict.has takes (place, i64) and yields i1')

    def op_dict_need(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1) and self._dict_place(ins, where):
            self.want(where, ins.operands[1].type == I.I64 and ins.result.type == I.I64, 'dict.need takes (place, i64) and yields i64')

    def op_dict_get(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1) and self._dict_place(ins, where):
            self.want(where, ins.operands[1].type == I.I64 and ins.operands[2].type == I.I64
                      and ins.result.type == I.I64, 'dict.get takes (place, i64, i64) and yields i64')

    def op_dict_put(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 0) and self._dict_place(ins, where):
            self.want(where, ins.operands[1].type == I.I64 and ins.operands[2].type == I.I64, 'dict.put takes (place, i64, i64)')

    def op_dict_len(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1) and self._dict_place(ins, where):
            self.want(where, ins.result.type == I.I64, 'dict.len yields i64')

    def op_dict_reset(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 0):
            self._dict_place(ins, where)

    def op_list_has(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            L, v = ins.operands
            self.want(where, L.type == _LIST_STR and v.type == I.STRV and ins.result.type == I.I1,
                      'list.has takes (list of str, str) and yields i1')

    def op_list_sort(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        self.want(where, ins.operands[0].type in (_LIST_STR, _LIST_I64, _LIST_F64),
                  'list.sort takes a list of str, int or float')

    def op_list_join(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            sep, L = ins.operands
            self.want(where, sep.type == I.STRV and L.type == _LIST_STR and ins.result.type == I.STRV,
                      'list.join takes (str, list of str) and yields str')

    def op_list_share(self, ins, scope, stack, where, top):
        self.err(where, 'list.share is resolved by the ownership analysis before verification')

    def op_list_copy(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        d, s = ins.operands
        elem = self._list_elem(d)
        ok = self._is_list_ref(d) and elem is not None and (
            s.type == d.type or s.type == I.T('span', elem))
        self.want(where, ok, 'list.copy takes (list, list or span of the same element type)')

    def op_list_call(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        sym = ins.attrs.get('callee')
        sig = self.program.callee_type(sym) if self.program is not None else None
        if not self.want(where, sig is not None, 'call to unknown function %r' % (sym,)):
            return
        params, results = sig.args[0].args, sig.args[1].args
        dst, args = ins.operands[0], ins.operands[1:]
        self.want(where, self._is_list_ref(dst) and list(results) == [dst.type],
                  'list.call destination must be the list type %s the callee returns' % (list(results),))
        abi = ins.attrs.get('abi') or ['value'] * len(args)
        ok = len(args) == len(params) == len(abi)
        for a, p, how in zip(args, params, abi):
            if how in ('array', 'flist'):
                ok = ok and p.head == 'span' and (a.type == p or (self._is_list_ref(a) and a.type.args[0].args[0] == p.args[0]))
            else:
                ok = ok and a.type == p
        self.want(where, ok, 'arguments (%s) do not match %s' % (', '.join(str(a.type) for a in args), sig))

    def op_ba_new(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        p, n = ins.operands
        self.want(where, p.type.is_place and p.type.pointee == _BA and n.type == I.I64,
                  'ba.new takes (place of a bytearray, i64)')

    def op_ba_drop(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        p = ins.operands[0]
        self.want(where, p.type.is_place and p.type.pointee == _BA, 'ba.drop takes the place of a bytearray')

    def op_ba_copyref(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        p, b = ins.operands
        self.want(where, p.type.is_place and p.type.pointee == _BA and b.type == _BA,
                  'ba.copyref takes (place of a bytearray, bytearray)')

    def op_ba_call(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        sym = ins.attrs.get('callee')
        sig = self.program.callee_type(sym) if self.program is not None else None
        if not self.want(where, sig is not None, 'call to unknown function %r' % (sym,)):
            return
        params, results = sig.args[0].args, sig.args[1].args
        place, args = ins.operands[0], ins.operands[1:]
        self.want(where, place.type.is_place and place.type.pointee == _BA and list(results) == [_BA],
                  'ba.call adopts a bytearray result into a bytearray place')
        self.want(where, list(self.types(args)) == list(params), 'arguments do not match %s' % sig)

    def op_ba_clear(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        self.want(where, self._is_ba(ins.operands[0]), 'ba.clear takes a bytearray')

    def op_ba_extend_lit(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        self.want(where, self._is_ba(ins.operands[0]), 'ba.extend_lit takes a bytearray')
        data = ins.attrs.get('data')
        self.want(where, isinstance(data, list) and all(isinstance(x, int) and not isinstance(x, bool)
                                                         and 0 <= x <= 255 for x in data),
                  'ba.extend_lit needs data = [byte values]')

    def _is_obj(self, t):
        return t.head == 'obj' and t.args[0].head == 'class'

    def op_obj_init(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        p = ins.operands[0]
        if not self.want(where, p.type.is_place and self._is_obj(p.type.pointee), 'obj.init takes the place of an object'):
            return
        info = (self.program.object_classes.get(p.type.pointee.args[0].name)
                if self.program is not None and hasattr(self.program, 'object_classes') else None)
        abi = ins.attrs.get('abi')
        self.want(where, isinstance(abi, list) and len(abi) == len(ins.operands) - 1
                  and all(a in ('value', 'list') for a in abi), 'obj.init needs abi = [value|list, ...]')
        self.want(where, ins.attrs.get('cls') == p.type.pointee.args[0].name, 'obj.init names the place\'s class')
        if isinstance(abi, list) and len(abi) == len(ins.operands) - 1:
            for v, a in zip(ins.operands[1:], abi):
                self.want(where, self._is_list_ref(v) if a == 'list' else v.type.is_scalar or v.type in (I.BYTES, I.STRV),
                          'obj.init argument of type %s as %s' % (v.type, a))

    def op_obj_copyref(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        p, o = ins.operands
        self.want(where, p.type.is_place and p.type.pointee == o.type and self._is_obj(o.type),
                  'obj.copyref takes (place of an object, object of that class)')

    def op_ba_extend(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        self.want(where, self._is_ba(ins.operands[0]) and ins.operands[1].type == I.BYTES,
                  'ba.extend takes (bytearray, bytes)')

    def op_field_ba(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            o = ins.operands[0].type
            self.want(where, o.head == 'obj' and o.args[0].head == 'class', 'field.ba of a non-object')
            self.want(where, ins.result.type == _BA, 'field.ba yields a bytearray')
            self.want(where, isinstance(ins.attrs.get('name'), str), 'field.ba needs a name')

    def op_ba_write(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        self.want(where, self._is_ba(ins.operands[0]), 'ba.write takes a bytearray')

    def op_field_plist(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            o = ins.operands[0].type
            self.want(where, o.head == 'obj' and o.args[0].head == 'class', 'field.plist of a non-object')
            self.want(where, ins.result.type == I.PLIST, 'field.plist yields a borrow of a list of str')
            self.want(where, isinstance(ins.attrs.get('name'), str), 'field.plist needs a name')

    def op_plist_len(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            self.want(where, ins.operands[0].type == I.PLIST and ins.result.type == I.I64, 'plist.len takes a plist and yields i64')

    def op_plist_get(self, ins, scope, stack, where, top):
        self._index_mode(ins, where)
        if self.nresults(ins, where, 1):
            self.want(where, ins.operands[0].type == I.PLIST and ins.operands[1].type == I.I64
                      and ins.result.type == I.STRV, 'plist.get takes (plist, i64) and yields a str')

    def op_plist_has(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            self.want(where, ins.operands[0].type == I.PLIST and ins.operands[1].type == I.STRV
                      and ins.result.type == I.I1, 'plist.has takes (plist, str) and yields i1')

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

    def op_spec_get(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            c, i, g = ins.operands
            elem = self._list_elem(c) if c.type.head == 'obj' else self._span_elem(c)
            self.want(where, elem in (I.I64, I.F64) and c.type != I.T('span', I.T('u8')) and i.type == I.I64
                      and g.type == I.I1 and ins.result.type == elem,
                      'spec.get takes (int or float list or span, i64, i1) and yields the element')

    def op_span_set(self, ins, scope, stack, where, top):
        if ins.attrs.get('mode') == 'vck':
            # a byte store whose index is proven, its value still checked (licm.py)
            self.want(where, ins.operands[0].type == I.T('span', I.T('u8')),
                      'mode vck is for a byte store through a span<u8>')
        else:
            self._index_mode(ins, where)
        self.nresults(ins, where, 0)
        elem = self._span_elem(ins.operands[0])
        self.want(where, elem is not None and ins.operands[1].type == I.I64 and ins.operands[2].type == elem,
                  'span.set takes (span, i64, element)')

    # ------------------------------------------------------------------ text (S4a)
    def op_str_lit(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            self.want(where, ins.result.type == I.STRV and isinstance(ins.attrs.get('value'), str),
                      'str.lit yields a strv and carries its text')

    def op_bytes_lit(self, ins, scope, stack, where, top):
        if self.nresults(ins, where, 1):
            data = ins.attrs.get('data')
            self.want(where, ins.result.type == I.BYTES and isinstance(data, list)
                      and all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 255 for x in data),
                      'bytes.lit yields bytes and carries its byte values')

    _PRINT_KINDS = {'int': I.I64, 'flt': I.F64, 'str': I.STRV, 'bool': I.I64}

    def op_print(self, ins, scope, stack, where, top):
        self.nresults(ins, where, 0)
        kinds = ins.attrs.get('kinds')
        if not self.want(where, isinstance(kinds, list) and all(k in self._PRINT_KINDS for k in kinds),
                         'print needs kinds = [int|flt|str|bool, ...]'):
            return
        stream = ins.attrs.get('stream', 'stdout')
        self.want(where, stream in ('stdout', 'stderr'), 'print stream is stdout or stderr')
        extra = int(bool(ins.attrs.get('sep'))) + int(bool(ins.attrs.get('end')))
        if self.want(where, len(ins.operands) == len(kinds) + extra, 'print takes its values, then sep, then end'):
            for v, k in zip(ins.operands, kinds):
                self.want(where, v.type == self._PRINT_KINDS[k] or (k in ('int', 'bool') and v.type == I.I1),
                          'print %s argument has type %s' % (k, v.type))
            for v in ins.operands[len(kinds):]:
                self.want(where, v.type == I.STRV, 'print sep and end are strings')
        if ins.attrs.get('parts'):
            self.want(where, len(kinds) >= 1 and all(k == 'str' for k in kinds) and extra == 0
                      and stream == 'stdout', 'print parts: strings only, to stdout, no sep or end')

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
