"""itertools and functools.reduce, lowered to the loops the compiler already builds (called from stdlib3.py).

An itertools call is never a value here (there are no iterators or tuples to hold it): it is a *stream*
walked by a `while True:` loop whose first statements fetch the next item, so `break` / `continue` in the
loop body mean what they mean in CPython. Each stream class below writes the fetch for one function:

* sequences (a list / str held in a variable, a slice, a literal, range(a, b[, step])) are read live by
  index, as a list iterator does (a list the body grows is walked on); a fresh sequence is bound to a
  temporary first;
* count, repeat, chain, chain.from_iterable, islice, accumulate, pairwise, zip_longest, groupby, and
  (over a snapshot of their inputs, as CPython takes one) product, permutations, combinations and
  combinations_with_replacement. The items come out in CPython's order.

Where a stream may appear: `for TARGET in <stream>:`, a comprehension / generator expression, and as the
argument of list / sum / min / max / sorted / set / any / all / "".join where that call starts a
statement (hoisted ahead of it, as map / filter are). Tuples are not a type here, so a tuple-valued item is
unpacked into names (`for a, b in product(x, y)`), or bound to a name that is only indexed, iterated or
reduced (it is held as a list; any other use of it -- print, ==, a dict key -- is refused).

functools.reduce is the same loop with an accumulator.
"""
import ast
import copy
import re
import textwrap

import iterlower
from iterlower import _name, _mark, _call, _locate, _Rename, _Subst, _rebinds

STREAMS = ('count', 'repeat', 'chain', 'chain.from_iterable', 'islice', 'accumulate', 'pairwise', 'zip_longest',
           'groupby', 'product', 'permutations', 'combinations', 'combinations_with_replacement')
CONSUMERS = ('list', 'sorted', 'set', 'sum', 'min', 'max', 'any', 'all')
NONESCAPE_CALLS = ('sum', 'min', 'max', 'sorted', 'list', 'any', 'all', 'set', 'len')
PURE_CALLS = ('len', 'abs', 'str', 'int', 'float', 'ord', 'chr', 'min', 'max', 'round', 'bool', 'sum')
PURE_METHODS = ('lower', 'upper', 'strip', 'lstrip', 'rstrip', 'isdigit', 'isalpha', 'isalnum', 'isspace',
                'isupper', 'islower', 'title', 'capitalize', 'swapcase', 'startswith', 'endswith', 'find',
                'count', 'index', 'rfind', 'replace', 'zfill', 'split', 'join', 'encode', 'decode')


def S():
    import stdlib3
    return stdlib3


def refuse(node, text):
    S().refuse(node, text)


def code(text, exh=None, **kw):
    """Parse a statement template. `@key` is replaced by the str kw[key] (text) or by a copy of the
    expression kw[key] (an ast node, load positions only); a statement `EXH` becomes a copy of `exh`."""
    nodes = {}

    def sub(match):
        value = kw[match.group(1)]
        if isinstance(value, str):
            return value
        nodes['_ph_' + match.group(1)] = value
        return '_ph_' + match.group(1)

    module = ast.parse(re.sub(r'@(\w+)', sub, textwrap.dedent(text)))

    class Fill(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == 'EXH':
                return [copy.deepcopy(s) for s in exh]
            return self.generic_visit(node)

        def visit_Name(self, node):
            if node.id in nodes:
                return copy.deepcopy(nodes[node.id])
            return node

    body = Fill().visit(module).body
    for stmt in body:
        _mark(stmt)
    return body


def const(value):
    return ast.Constant(value=value)


def assign(name, value):
    return ast.Assign(targets=[_name(name, True)], value=value)


def int_value(node):
    """The int a literal expression stands for, or None."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = int_value(node.operand)
        return None if inner is None else -inner
    return None


def stored_names(nodes):
    """Names written anywhere in `nodes` (assignment, loop target, augmented assignment, del...)."""
    out = set()
    for stmt in nodes:
        for each in ast.walk(stmt):
            if isinstance(each, ast.Name) and not isinstance(each.ctx, ast.Load):
                out.add(each.id)
    return out


class Src:
    """One stream. `arity`: number of items per step, or 'list' for one list-valued item."""
    arity = 1
    parts = ()

    def setup(self, st):
        return []

    def step(self, st, out, exh):
        raise NotImplementedError

    def live(self):
        names = set()
        for part in self.parts:
            names |= part.live()
        return names

    def scalar(self):
        return self.arity == 1


class Seq(Src):
    """A list / str read by index, live when it is a name the compiler knows to be a sequence."""
    def __init__(self, st, expr, live_name):
        self.expr = expr
        self.name = live_name
        self.holder = live_name or st.fresh('s')
        self.index = st.fresh('i')

    def live(self):
        return {self.name} if self.name else set()

    def setup(self, st, with_index=True):
        out = []
        if self.name is None:
            out.append(assign(self.holder, self.expr))
        if with_index:
            out.append(assign(self.index, const(0)))
        return out

    def step(self, st, out, exh):
        return code('''
            if @I >= len(@H):
                EXH
            else:
                @O = @H[@I]
                @I += 1
        ''', exh, I=self.index, H=self.holder, O=out[0])


class RangeSeq(Src):
    def __init__(self, st, call):
        args = call.args
        if call.keywords or not 1 <= len(args) <= 3 or any(isinstance(a, ast.Starred) for a in args):
            refuse(call, 'range() here takes one to three positional arguments')
        self.start, self.stop = (const(0), args[0]) if len(args) == 1 else (args[0], args[1])
        self.step_node = args[2] if len(args) == 3 else const(1)
        value = int_value(self.step_node)
        if value is None or value == 0:
            refuse(call, 'range() inside an itertools call needs a literal non-zero step')
        self.direction = '>=' if value > 0 else '<='
        self.step_text = str(value)
        self.cur, self.end = st.fresh('r'), st.fresh('e')

    def setup(self, st):
        return [assign(self.cur, self.start), assign(self.end, self.stop)]

    def step(self, st, out, exh):
        return code('''
            if @C @DIR @E:
                EXH
            else:
                @O = @C
                @C += @STEP
        ''', exh, C=self.cur, E=self.end, O=out[0], DIR=self.direction, STEP=self.step_text)


class Count(Src):
    def __init__(self, st, call):
        got = st.lib.args_of(call, ['start', 'step'], what='itertools.count')
        self.start = got.get('start', const(0))
        self.stepv = got.get('step', const(1))
        self.cur, self.inc = st.fresh('c'), st.fresh('cs')

    def setup(self, st):
        return [assign(self.cur, self.start), assign(self.inc, self.stepv)]

    def step(self, st, out, exh):
        return code('''
            @O = @C
            @C += @S
        ''', exh, O=out[0], C=self.cur, S=self.inc)


class Repeat(Src):
    def __init__(self, st, call):
        got = st.lib.args_of(call, ['object', 'times'], what='itertools.repeat')
        if 'object' not in got:
            refuse(call, 'itertools.repeat needs the object to repeat')
        self.obj = got['object']
        self.times = got.get('times')
        lists = st.lib.current_lists or set()
        for each in ast.walk(self.obj):
            if isinstance(each, ast.Name) and (each.id in st.lib.sequences or each.id in lists):
                refuse(call, 'itertools.repeat(%s): the same list object is yielded each time in CPython; '
                       'repeat a number or a str' % each.id)
        if isinstance(self.obj, (ast.List, ast.Dict, ast.Set, ast.ListComp)):
            refuse(call, 'itertools.repeat of a list or dict yields the same object each time; repeat a number or a str')
        self.val, self.left = st.fresh('rv'), st.fresh('rn')

    def setup(self, st):
        out = [assign(self.val, self.obj)]
        if self.times is not None:
            out.append(assign(self.left, self.times))
        return out

    def step(self, st, out, exh):
        if self.times is None:
            return code('@O = @V', exh, O=out[0], V=self.val)
        return code('''
            if @N <= 0:
                EXH
            else:
                @N -= 1
                @O = @V
        ''', exh, N=self.left, O=out[0], V=self.val)


class Chain(Src):
    def __init__(self, st, parts):
        self.parts = parts
        self.phase = st.fresh('ph')

    def setup(self, st):
        out = [assign(self.phase, const(0))]
        for part in self.parts:
            out.extend(part.setup(st))
        return out

    def step(self, st, out, exh):
        chain = None
        # an if/elif ladder over the phases; an exhausted part moves to the next phase and fetches again
        for index in reversed(range(len(self.parts))):
            advance = code('''
                @PH = @PH + 1
                continue
            ''', PH=self.phase)
            body = self.parts[index].step(st, out, advance)
            test = ast.Compare(left=_name(self.phase), ops=[ast.Eq()], comparators=[const(index)])
            orelse = chain if chain is not None else [copy.deepcopy(s) for s in exh]
            chain = [ast.If(test=test, body=body, orelse=orelse)]
        return chain


class ChainRows(Src):
    """chain.from_iterable(X) for a list of lists (or strs) held in a variable."""
    def __init__(self, st, seq):
        self.seq = seq
        self.row, self.col = st.fresh('row'), st.fresh('col')

    def live(self):
        return self.seq.live()

    def setup(self, st):
        return self.seq.setup(st, False) + [assign(self.row, const(0)), assign(self.col, const(0))]

    def step(self, st, out, exh):
        return code('''
            while @R < len(@H) and @C >= len(@H[@R]):
                @R += 1
                @C = 0
            if @R >= len(@H):
                EXH
            else:
                @O = @H[@R][@C]
                @C += 1
        ''', exh, R=self.row, C=self.col, H=self.seq.holder, O=out[0])


class Islice(Src):
    def __init__(self, st, call, inner):
        self.parts = [inner]
        args = call.args
        if call.keywords or not 2 <= len(args) <= 4 or any(isinstance(a, ast.Starred) for a in args):
            refuse(call, 'itertools.islice(iterable, stop) / islice(iterable, start, stop[, step]) take positional arguments')
        rest = args[1:]
        none = lambda n: isinstance(n, ast.Constant) and n.value is None
        if len(rest) == 1:
            self.start, self.stop, self.stepv = const(0), rest[0], const(1)
        else:
            self.start, self.stop = rest[0], rest[1]
            self.stepv = rest[2] if len(rest) == 3 else const(1)
        if none(self.start):
            self.start = const(0)
        if none(self.stepv):
            self.stepv = const(1)
        self.no_stop = none(self.stop)
        self.cnt, self.nxt, self.stp, self.end, self.idx = (st.fresh(n) for n in ('n', 'nx', 'sp', 'en', 'ix'))

    def setup(self, st):
        out = [assign(self.nxt, self.start), assign(self.stp, self.stepv), assign(self.cnt, const(0))]
        checks = ['%s < 0' % self.nxt]
        if not self.no_stop:
            out.append(assign(self.end, self.stop))
            checks.append('%s < 0' % self.end)
        out += code('''
            if @CHECKS:
                raise ValueError("Indices for islice() must be None or an integer: 0 <= x <= sys.maxsize.")
            if @STP <= 0:
                raise ValueError("Step for islice() must be a positive integer or None.")
        ''', CHECKS=' or '.join(checks), STP=self.stp)
        for part in self.parts:
            out.extend(part.setup(st))
        return out

    def step(self, st, out, exh):
        head = []
        if not self.no_stop:
            # nothing is fetched once `stop` items have been, as CPython does
            head = code('''
                if @N >= @E:
                    EXH
            ''', exh, N=self.cnt, E=self.end)
        pull = self.parts[0].step(st, out, exh)
        tail = code('''
            @IDX = @N
            @N += 1
            if @IDX < @NX:
                continue
            @NX = @IDX + @SP
        ''', exh, IDX=self.idx, N=self.cnt, NX=self.nxt, SP=self.stp)
        return head + pull + tail


class Accumulate(Src):
    def __init__(self, st, call, inner):
        self.parts = [inner]
        got = st.lib.args_of(call, ['iterable', 'func', 'initial'], what='itertools.accumulate')
        isnone = lambda n: n is None or (isinstance(n, ast.Constant) and n.value is None)
        self.func = None if isnone(got.get('func')) else got['func']
        self.initial = None if isnone(got.get('initial')) else got['initial']
        if self.initial is not None:
            initial_kind = st.expr_kind(self.initial)
            element_kind = st.seq_elem_kind(got['iterable'])
            if initial_kind is not None and element_kind is not None and initial_kind != element_kind:
                refuse(call, 'itertools.accumulate: initial= has to have the same type as the iterable '
                       'elements (%s, not %s); the accumulator is one typed value here'
                       % (element_kind, initial_kind))
        self.acc, self.started, self.x = st.fresh('acc'), st.fresh('st'), st.fresh('x')
        self.st = st
        self.call = call

    def setup(self, st):
        out = [assign(self.started, const(0))]
        if self.initial is not None:
            out.append(assign(self.acc, self.initial))
        for part in self.parts:
            out.extend(part.setup(st))
        return out

    def step(self, st, out, exh):
        pull = self.parts[0].step(st, [self.x], exh)
        update = [assign(self.acc, self.combine(_name(self.acc), _name(self.x)))]
        is_first = ast.Compare(left=_name(self.started), ops=[ast.Eq()], comparators=[const(0)])
        if self.initial is not None:
            body = [ast.If(test=is_first, body=[assign(self.started, const(1))], orelse=pull + update)]
        else:
            body = pull + [ast.If(test=is_first, body=[assign(self.acc, _name(self.x)),
                                                       assign(self.started, const(1))], orelse=update)]
        body.append(assign(out[0], _name(self.acc)))
        return body

    def combine(self, a, b):
        if self.func is None:
            return ast.BinOp(left=a, op=ast.Add(), right=b)
        result = self.st.apply2(self.func, a, b)
        if result is None:
            refuse(self.call, 'itertools.accumulate: func has to be a lambda of two parameters, a function name, '
                   'max / min or an operator function')
        return result


class Pairwise(Src):
    arity = 2

    def __init__(self, st, inner):
        self.parts = [inner]
        self.prev, self.started, self.x = st.fresh('pv'), st.fresh('st'), st.fresh('x')

    def setup(self, st):
        out = [assign(self.started, const(0))]
        for part in self.parts:
            out.extend(part.setup(st))
        return out

    def step(self, st, out, exh):
        pull = self.parts[0].step(st, [self.x], exh)
        first = ast.If(test=ast.Compare(left=_name(self.started), ops=[ast.Eq()], comparators=[const(0)]),
                       body=pull + [assign(self.prev, _name(self.x)), assign(self.started, const(1))],
                       orelse=[])
        return [first] + [copy.deepcopy(s) for s in pull] + [
            assign(out[0], _name(self.prev)), assign(out[1], _name(self.x)), assign(self.prev, _name(self.x))]


class ZipLongest(Src):
    def __init__(self, st, call, parts, fill):
        self.parts = parts
        self.arity = len(parts)
        self.fill = fill
        self.fill_name = st.fresh('fill')
        self.done = [st.fresh('dn') for _ in parts]
        self.live_count = st.fresh('lv')

    def setup(self, st):
        out = [assign(self.fill_name, self.fill)]
        for flag in self.done:
            out.append(assign(flag, const(0)))
        for part in self.parts:
            out.extend(part.setup(st))
        return out

    def step(self, st, out, exh):
        body = [assign(self.live_count, const(0))]
        for index, part in enumerate(self.parts):
            skip = code('''
                @D = 1
                @O = @F
            ''', D=self.done[index], O=out[index], F=self.fill_name)
            pull = part.step(st, [out[index]], skip)
            body.append(ast.If(
                test=ast.Compare(left=_name(self.done[index]), ops=[ast.Eq()], comparators=[const(0)]),
                body=pull + code('''
                    if @D == 0:
                        @L += 1
                ''', D=self.done[index], L=self.live_count),
                orelse=code('@O = @F', O=out[index], F=self.fill_name)))
        body += code('''
            if @L == 0:
                EXH
        ''', exh, L=self.live_count)
        return body


class Pool:
    """A snapshot of an iterable, taken when the loop starts (as tuple(iterable) is)."""
    def __init__(self, st, expr):
        self.expr = expr
        self.name = st.fresh('pool')
        self.size = st.fresh('n')

    def setup(self, st):
        var = st.fresh('pe')
        comp = ast.ListComp(elt=_name(var), generators=[ast.comprehension(
            target=_name(var, True), iter=self.expr, ifs=[], is_async=0)])
        return [assign(self.name, comp), assign(self.size, _call(_name('len'), _name(self.name)))]


class Product(Src):
    def __init__(self, st, call, pools, repeat):
        base = [Pool(st, expr) for expr in pools]
        self.pools = base * repeat
        self.unique = base
        self.arity = len(self.pools)
        if self.arity == 0:
            refuse(call, 'itertools.product() with no iterables yields one empty tuple; not built')
        self.idx = [st.fresh('ix') for _ in self.pools]
        self.first = st.fresh('first')

    def setup(self, st):
        out = []
        for pool in self.unique:
            out.extend(pool.setup(st))
        for name in self.idx:
            out.append(assign(name, const(0)))
        out.append(assign(self.first, const(1)))
        return out

    def step(self, st, out, exh):
        empty = ' or '.join('%s == 0' % pool.size for pool in self.unique)

        def carry(level):
            # the last position moves fastest; a position that wraps carries into the one before it
            inc = code('@IX += 1', IX=self.idx[level])
            if level == 0:
                over = [copy.deepcopy(s) for s in exh]
            else:
                over = code('@IX = 0', IX=self.idx[level]) + carry(level - 1)
            test = ast.Compare(left=_name(self.idx[level]), ops=[ast.GtE()],
                               comparators=[_name(self.pools[level].size)])
            return inc + [ast.If(test=test, body=over, orelse=[])]

        head = code('''
            if @F == 1:
                @F = 0
                if @EMPTY:
                    EXH
            else:
                pass
        ''', exh, F=self.first, EMPTY=empty)
        head[0].orelse = carry(self.arity - 1)
        for index in range(self.arity):
            head.append(assign(out[index], ast.Subscript(value=_name(self.pools[index].name),
                                                         slice=_name(self.idx[index]), ctx=ast.Load())))
        return head


class PoolStream(Src):
    """permutations / combinations / combinations_with_replacement: r items chosen from a pool by index."""
    def __init__(self, st, call, kind, pool, r_expr):
        self.kind = kind
        self.call = call
        self.pool = Pool(st, pool)
        self.r_expr = r_expr
        self.tuple_arity = None
        self.arity = 'list'
        self.ix, self.cy, self.r, self.first = (st.fresh(n) for n in ('ix', 'cy', 'r', 'first'))
        self.i, self.j, self.found, self.t, self.g = (st.fresh(n) for n in ('i', 'j', 'fd', 't', 'g'))

    def use_arity(self, count):
        """The loop unpacks each item into `count` names."""
        self.tuple_arity = count
        self.arity = count
        if self.r_expr is not None and int_value(self.r_expr) is not None and int_value(self.r_expr) != count:
            refuse(self.call, 'itertools: r=%d but the loop unpacks %d names (CPython raises ValueError)'
                   % (int_value(self.r_expr), count))

    def setup(self, st):
        out = self.pool.setup(st)
        n, r = self.pool.size, self.r
        out.append(assign(r, _name(n) if self.r_expr is None else self.r_expr))
        if self.kind == 'product':
            out += code('''
                if @R < 0:
                    raise ValueError("repeat argument cannot be negative")
            ''', R=r)
        else:
            out += code('''
                if @R < 0:
                    raise ValueError("r must be non-negative")
            ''', R=r)
        if self.tuple_arity is not None:
            if self.r_expr is None:
                out += code('''
                    if @N < @A:
                        raise ValueError("not enough values to unpack (expected @A, got " + str(@N) + ")")
                    if @N > @A:
                        raise ValueError("too many values to unpack (expected @A)")
                ''', N=n, A=str(self.tuple_arity))
            elif int_value(self.r_expr) is None:
                out += code('''
                    if @R != @A:
                        raise ValueError("itertools: r does not match the number of names the items are unpacked into")
                ''', R=r, A=str(self.tuple_arity))
        if self.kind == 'permutations':
            out += code('''
                @IX = list(range(@N))
                @CY = [@N - @T for @T in range(@R)]
            ''', IX=self.ix, CY=self.cy, N=n, R=r, T=self.t)
        elif self.kind == 'combinations':
            out += code('@IX = list(range(@R))', IX=self.ix, R=r)
        else:
            out += code('@IX = [0 for @T in range(@R)]', IX=self.ix, R=r, T=self.t)
        out.append(assign(self.first, const(1)))
        return out

    def step(self, st, out, exh):
        names = dict(N=self.pool.size, R=self.r, IX=self.ix, CY=self.cy, I=self.i, J=self.j, FD=self.found,
                     T=self.t, F=self.first)
        if self.kind == 'permutations':
            first_ok = '''
                if @R > @N:
                    EXH
            '''
            advance = '''
                @I = @R - 1
                @FD = 0
                while @I >= 0 and @FD == 0:
                    @CY[@I] -= 1
                    if @CY[@I] == 0:
                        @T = @IX[@I]
                        @J = @I
                        while @J < @N - 1:
                            @IX[@J] = @IX[@J + 1]
                            @J += 1
                        @IX[@N - 1] = @T
                        @CY[@I] = @N - @I
                        @I -= 1
                    else:
                        @J = @CY[@I]
                        @T = @IX[@I]
                        @IX[@I] = @IX[@N - @J]
                        @IX[@N - @J] = @T
                        @FD = 1
                if @FD == 0:
                    EXH
            '''
        elif self.kind == 'combinations':
            first_ok = '''
                if @R > @N:
                    EXH
            '''
            advance = '''
                @I = @R - 1
                while @I >= 0 and @IX[@I] == @I + @N - @R:
                    @I -= 1
                if @I < 0:
                    EXH
                @IX[@I] += 1
                @J = @I + 1
                while @J < @R:
                    @IX[@J] = @IX[@J - 1] + 1
                    @J += 1
            '''
        elif self.kind == 'product':
            first_ok = '''
                if @N == 0 and @R > 0:
                    EXH
            '''
            advance = '''
                @I = @R - 1
                while @I >= 0 and @IX[@I] == @N - 1:
                    @IX[@I] = 0
                    @I -= 1
                if @I < 0:
                    EXH
                @IX[@I] += 1
            '''
        else:
            first_ok = '''
                if @N == 0 and @R > 0:
                    EXH
            '''
            advance = '''
                @I = @R - 1
                while @I >= 0 and @IX[@I] == @N - 1:
                    @I -= 1
                if @I < 0:
                    EXH
                @T = @IX[@I] + 1
                @J = @I
                while @J < @R:
                    @IX[@J] = @T
                    @J += 1
            '''
        first_stmts = code(textwrap.dedent(first_ok), exh, **names)
        head = code('''
            if @F == 1:
                @F = 0
            else:
                pass
        ''', F=self.first)
        head[0].body.extend(first_stmts)
        head[0].orelse = code(textwrap.dedent(advance), exh, **names)
        if self.tuple_arity is not None:
            for k in range(self.tuple_arity):
                head.append(assign(out[k], ast.Subscript(
                    value=_name(self.pool.name),
                    slice=ast.Subscript(value=_name(self.ix), slice=const(k), ctx=ast.Load()), ctx=ast.Load())))
        else:
            head += code('@O = [@P[@IX[@G]] for @G in range(@R)]', O=out[0], P=self.pool.name, IX=self.ix,
                         G=self.g, R=self.r)
        return head


class Groupby(Src):
    arity = 2

    def __init__(self, st, call, seq, key):
        self.parts = [seq]
        self.seq = seq
        self.key = key
        self.st = st
        self.call = call
        self.i, self.j, self.k, self.t = (st.fresh(n) for n in ("gi", "gj", "gk", "gt"))
        self.kj, self.cached, self.have = (st.fresh(n) for n in ("gkj", "gc", "gh"))
        self.cache = st.element_immutable(self.seq)

    def setup(self, st):
        return self.seq.setup(st, False) + [assign(self.i, const(0)), assign(self.have, const(0))]

    def key_of(self, element):
        if self.key is None:
            return element
        result = self.st.lib.apply(self.key, element)
        if result is None:
            refuse(self.call, 'itertools.groupby: key has to be a lambda of one parameter or a function name')
        return result

    def step(self, st, out, exh):
        holder = self.seq.holder
        at = lambda index: ast.Subscript(value=_name(holder), slice=_name(index), ctx=ast.Load())
        body = [ast.If(
            test=ast.Compare(left=_name(self.i), ops=[ast.GtE()], comparators=[_call(_name('len'), _name(holder))]),
            body=[copy.deepcopy(s) for s in exh], orelse=[])]
        # The key of the element that starts a group was already computed by the look-ahead
        # that ended the previous group; reuse it instead of calling the key twice (CPython
        # calls it exactly once per element).
        body.append(ast.If(
            test=_name(self.have) if self.cache else const(False),
            body=[assign(self.k, _name(self.cached)), assign(self.have, const(0))],
            orelse=[assign(self.k, self.key_of(at(self.i)))]))
        body.append(assign(self.j, ast.BinOp(left=_name(self.i), op=ast.Add(), right=const(1))))
        body.append(ast.While(
            test=ast.Compare(left=_name(self.j), ops=[ast.Lt()],
                             comparators=[_call(_name('len'), _name(holder))]),
            body=[
                assign(self.kj, self.key_of(at(self.j))),
                ast.If(
                    test=ast.Compare(left=_name(self.kj), ops=[ast.NotEq()], comparators=[_name(self.k)]),
                    body=([assign(self.cached, _name(self.kj)), assign(self.have, const(1))]
                          if self.cache else [assign(self.have, const(0))]) + [ast.Break()],
                    orelse=[]),
                ast.AugAssign(target=_name(self.j, True), op=ast.Add(), value=const(1)),
            ],
            orelse=[]))
        body.append(assign(out[0], _name(self.k)))
        body += code('@O = [@H[@T] for @T in range(@I, @J)]', O=out[1], H=holder, T=self.t, I=self.i, J=self.j)
        body.append(assign(self.i, _name(self.j)))
        return [_mark(s) for s in body]


class ZipStreams(Src):
    """zip(...) over streams (count / repeat among them): stops at the first exhausted argument."""
    def __init__(self, parts):
        self.parts = parts
        self.arity = len(parts)

    def setup(self, st):
        out = []
        for part in self.parts:
            out.extend(part.setup(st))
        return out

    def step(self, st, out, exh):
        body = []
        for index, part in enumerate(self.parts):
            body += part.step(st, [out[index]], exh)
        return body


class Streams:
    """The itertools / functools half of Lib3."""
    def __init__(self, lib):
        self.lib = lib
        self.imports = lib.imports

    def fresh(self, stem):
        return self.lib.fresh(stem)

    def prepare(self, tree):
        pass

    def finish(self, tree):
        pass

    # -- recognising a stream -----------------------------------------------------------------------
    def name_of(self, node):
        if isinstance(node, ast.Call):
            found = self.imports.resolve(node.func)
            if found and found[0] == 'itertools':
                return found[1]
        return None

    def has_itertools(self, node):
        return any(self.name_of(each) is not None for each in ast.walk(node))

    def build(self, call):
        """The stream for an itertools call."""
        name = self.name_of(call)
        if name not in STREAMS:
            refuse(call, 'itertools.%s is not built (built: %s)' % (name, ', '.join(STREAMS)))
        if name == 'count':
            return Count(self, call)
        if name == 'repeat':
            return Repeat(self, call)
        if name == 'chain':
            if call.keywords or any(isinstance(a, ast.Starred) for a in call.args) or not call.args:
                refuse(call, 'itertools.chain(a, b, ...) takes iterables as positional arguments')
            return Chain(self, [self.leaf(a) for a in call.args])
        if name == 'chain.from_iterable':
            if len(call.args) != 1 or call.keywords:
                refuse(call, 'itertools.chain.from_iterable takes one argument')
            return ChainRows(self, self.seq_only(call.args[0]))
        if name == 'islice':
            if not call.args:
                refuse(call, 'itertools.islice needs an iterable')
            return Islice(self, call, self.leaf(call.args[0]))
        if name == 'accumulate':
            got = self.lib.args_of(call, ['iterable', 'func', 'initial'], what='itertools.accumulate')
            if 'iterable' not in got:
                refuse(call, 'itertools.accumulate needs an iterable')
            return Accumulate(self, call, self.leaf(got['iterable']))
        if name == 'pairwise':
            if len(call.args) != 1 or call.keywords:
                refuse(call, 'itertools.pairwise takes one iterable')
            return Pairwise(self, self.leaf(call.args[0]))
        if name == 'zip_longest':
            fills = [k for k in call.keywords if k.arg == 'fillvalue']
            if len(fills) != len(call.keywords) or any(isinstance(a, ast.Starred) for a in call.args) or not call.args:
                refuse(call, 'itertools.zip_longest(a, b, ..., fillvalue=v) takes positional iterables')
            if not fills:
                refuse(call, 'itertools.zip_longest without fillvalue= fills with None, which has no type here; '
                       'give fillvalue=<value>')
            return ZipLongest(self, call, [self.leaf(a, False) for a in call.args], fills[0].value)
        if name == 'groupby':
            got = self.lib.args_of(call, ['iterable', 'key'], what='itertools.groupby')
            if 'iterable' not in got:
                refuse(call, 'itertools.groupby needs an iterable')
            key = got.get('key')
            if isinstance(key, ast.Constant) and key.value is None:
                key = None
            if key is not None and not self.pure_key(key):
                refuse(call, 'itertools.groupby: key has to be a pure function (it is computed again for the first '
                       'element of the next group); a lambda over len / abs / str / int / indexing is')
            return Groupby(self, call, self.seq_only(got['iterable']), key)
        if name == 'product':
            repeat = 1
            keys = [k for k in call.keywords if k.arg == 'repeat']
            if len(keys) != len(call.keywords) or any(isinstance(a, ast.Starred) for a in call.args):
                refuse(call, 'itertools.product(a, b, ..., repeat=n) takes positional iterables')
            if keys:
                repeat = int_value(keys[0].value)
                if repeat is None and len(call.args) == 1:
                    # one iterable and a repeat computed at run time: the indices are a list, like permutations
                    return PoolStream(self, call, 'product', call.args[0], keys[0].value)
                if repeat is None or repeat < 0:
                    refuse(call, 'itertools.product: with several iterables repeat= has to be a non-negative '
                           'integer literal (with one iterable it can be any int)')
            return Product(self, call, call.args, repeat)
        got = self.lib.args_of(call, ['iterable', 'r'], what='itertools.' + name)
        if 'iterable' not in got:
            refuse(call, 'itertools.%s needs an iterable' % name)
        if name != 'permutations' and 'r' not in got:
            refuse(call, 'itertools.%s needs r' % name)
        r = got.get('r')
        if isinstance(r, ast.Constant) and r.value is None:
            r = None
        if r is not None:
            rv = int_value(r)
            if rv is not None and rv < 0:
                refuse(call, 'itertools.%s: a negative r literal (CPython raises ValueError: '
                       'r must be non-negative)' % name)
        return PoolStream(self, call, name, got['iterable'], r)

    _SCALAR_TYPES = ('int', 'float', 'str', 'bool', 'bytes')
    _NUMERIC_TYPES = ('int', 'float')

    def _ann_node(self, ann):
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            try:
                return ast.parse(ann.value, mode='eval').body
            except SyntaxError:
                return ann
        return ann

    def _ann_scalar(self, ann):
        ann = self._ann_node(ann)
        if isinstance(ann, ast.Name):
            name = ann.id.lower()
            return name if name in self._SCALAR_TYPES else None
        if isinstance(ann, ast.Attribute):
            name = ann.attr.lower()
            return name if name in self._SCALAR_TYPES else None
        return None

    def _ann_container(self, ann):
        ann = self._ann_node(ann)
        head = ann.value if isinstance(ann, ast.Subscript) else ann
        name = head.id.lower() if isinstance(head, ast.Name) else (
            head.attr.lower() if isinstance(head, ast.Attribute) else None)
        if name == 'str':
            return ('str',)
        if name == 'bytes':
            return ('bytes',)
        if name in ('list', 'set', 'frozenset', 'tuple'):
            if isinstance(ann, ast.Subscript):
                inner = ann.slice
                if isinstance(inner, ast.Tuple):
                    members = self._same_kind([self._ann_scalar(el) for el in inner.elts])
                    return (name, members)
                return (name, self._ann_scalar(inner))
            return (name, None)
        if name in ('dict', 'counter', 'defaultdict'):
            if isinstance(ann, ast.Subscript) and isinstance(ann.slice, ast.Tuple) and len(ann.slice.elts) == 2:
                return ('dict', self._ann_scalar(ann.slice.elts[0]), self._ann_scalar(ann.slice.elts[1]))
            return ('dict', None, None)
        return None

    def _same_kind(self, kinds):
        if not kinds:
            return None
        first = kinds[0]
        if first is None:
            return None
        return first if all(kind == first for kind in kinds) else None

    def _local_nodes(self, root):
        stack = list(root.body) if isinstance(root, (ast.FunctionDef, ast.AsyncFunctionDef)) else list(root)
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            yield node
            stack.extend(ast.iter_child_nodes(node))

    def _name_sources(self, name):
        fn = getattr(self.lib, 'cur_fn', None)
        out = []
        if fn is not None:
            for arg in (*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs):
                if arg.arg == name:
                    out.append(('ann', arg.annotation))
            nodes = self._local_nodes(fn)
        else:
            nodes = []
            for top in self.lib.tree.body:
                if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                nodes.extend(self._local_nodes([top]))
        for node in nodes:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
                out.append(('ann', node.annotation))
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                out.append(('val', node.value))
            elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name) and node.target.id == name:
                out.append(('val', node.value))
            elif isinstance(node, (ast.AugAssign, ast.For, ast.AsyncFor)):
                targets = node.target if isinstance(node, (ast.AugAssign,)) else node.target
                if any(isinstance(t, ast.Name) and t.id == name for t in ast.walk(targets)):
                    out.append(('bad', None))
            elif isinstance(node, (ast.With, ast.AsyncWith)) and any(
                    item.optional_vars is not None and any(
                        isinstance(t, ast.Name) and t.id == name for t in ast.walk(item.optional_vars))
                    for item in node.items):
                out.append(('bad', None))
        return out

    def _kind_of_name(self, name, seen):
        if name in seen:
            return None
        seen = seen | {name}
        sources = self._name_sources(name)
        if not sources:
            return None
        kinds = []
        for source, value in sources:
            if source == 'bad':
                return None
            kind = self._ann_scalar(value) if source == 'ann' else self._kind_of_expr(value, seen)
            if kind is None:
                return None
            kinds.append(kind)
        return self._same_kind(kinds)

    def _seq_elem_of_name(self, name, seen):
        if name in seen:
            return None
        seen = seen | {name}
        sources = self._name_sources(name)
        if not sources:
            return None
        kinds = []
        for source, value in sources:
            if source == 'bad':
                return None
            if source == 'ann':
                info = self._ann_container(value)
            else:
                info = self._container_of_expr(value, seen)
            if info is None:
                return None
            if info[0] == 'str':
                kind = 'str'
            elif info[0] == 'bytes':
                kind = 'int'
            elif info[0] == 'dict':
                kind = info[1]
            else:
                kind = info[1] if len(info) > 1 else None
            if kind is None:
                return None
            kinds.append(kind)
        return self._same_kind(kinds)

    def _container_of_name(self, name, seen):
        if name in seen:
            return None
        seen = seen | {name}
        sources = self._name_sources(name)
        if not sources:
            return None
        infos = []
        for source, value in sources:
            if source == 'bad':
                return None
            info = self._ann_container(value) if source == 'ann' else self._container_of_expr(value, seen)
            if info is None:
                return None
            infos.append(info)
        if not infos:
            return None
        first = infos[0]
        return first if all(info == first for info in infos) else None

    def _container_of_expr(self, e, seen):
        if isinstance(e, ast.Name):
            return self._container_of_name(e.id, seen)
        if isinstance(e, ast.List):
            return ('list', self._same_kind([self._kind_of_expr(el, seen) for el in e.elts]))
        if isinstance(e, ast.Set):
            return ('set', self._same_kind([self._kind_of_expr(el, seen) for el in e.elts]))
        if isinstance(e, ast.Dict):
            return ('dict', self._same_kind([self._kind_of_expr(k, seen) for k in e.keys if k is not None]),
                    self._same_kind([self._kind_of_expr(v, seen) for v in e.values]))
        if isinstance(e, ast.Constant):
            if isinstance(e.value, str):
                return ('str',)
            if isinstance(e.value, (bytes, bytearray)):
                return ('bytes',)
            return None
        if isinstance(e, ast.JoinedStr):
            return ('str',)
        if isinstance(e, ast.Attribute):
            return self._attribute_container(e, seen)
        if isinstance(e, ast.Subscript) and isinstance(e.slice, ast.Slice):
            return self._container_of_expr(e.value, seen)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            left = self._container_of_expr(e.left, seen)
            right = self._container_of_expr(e.right, seen)
            if left is not None and left == right:
                return left
            if left is not None and right is not None and left[0] == right[0] == 'list':
                return ('list', self._same_kind([left[1], right[1]]))
            return None
        if isinstance(e, ast.IfExp):
            left = self._container_of_expr(e.body, seen)
            right = self._container_of_expr(e.orelse, seen)
            return left if left is not None and left == right else None
        if isinstance(e, ast.Call):
            if isinstance(e.func, ast.Name):
                name = e.func.id
                if name in ('list', 'sorted', 'reversed') and e.args and not e.keywords:
                    return ('list', self._seq_elem_of_expr(e.args[0], seen))
                if name == 'str':
                    return ('str',)
                if name == 'range':
                    return ('list', 'int')
                if name == 'dict':
                    return ('dict', None, None)
            if isinstance(e.func, ast.Attribute):
                if e.func.attr in ('split', 'rsplit', 'splitlines'):
                    return ('list', 'str')
                if e.func.attr in ('encode',):
                    return ('bytes',)
                if e.func.attr in ('keys', 'values', 'items'):
                    base = self._container_of_expr(e.func.value, seen)
                    if base is not None and base[0] == 'dict':
                        if e.func.attr == 'keys':
                            return ('list', base[1])
                        if e.func.attr == 'values':
                            return ('list', base[2])
                    return None
        return None

    def _seq_elem_of_expr(self, e, seen):
        if isinstance(e, ast.Name):
            return self._seq_elem_of_name(e.id, seen)
        if isinstance(e, ast.List):
            return self._same_kind([self._kind_of_expr(el, seen) for el in e.elts])
        if isinstance(e, ast.Constant):
            if isinstance(e.value, str):
                return 'str'
            if isinstance(e.value, (bytes, bytearray)):
                return 'int'
            return None
        if isinstance(e, ast.JoinedStr):
            return 'str'
        if isinstance(e, ast.Attribute):
            info = self._attribute_container(e, seen)
            if info is None:
                return None
            if info[0] == 'str':
                return 'str'
            if info[0] == 'bytes':
                return 'int'
            if info[0] == 'dict':
                return info[1]
            return info[1] if len(info) > 1 else None
        if isinstance(e, ast.Subscript):
            if isinstance(e.slice, ast.Slice):
                return self._seq_elem_of_expr(e.value, seen)
            if isinstance(e.value, ast.Dict) and isinstance(e.slice, ast.Constant):
                for key, value in zip(e.value.keys, e.value.values):
                    if isinstance(key, ast.Constant) and key.value == e.slice.value:
                        return self._seq_elem_of_expr(value, seen)
            info = self._container_of_expr(e.value, seen)
            if info is None:
                return None
            if info[0] == 'dict':
                return info[2]
            if info[0] in ('list', 'set', 'tuple'):
                return info[1] if len(info) > 1 else None
            return None
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            left = self._seq_elem_of_expr(e.left, seen)
            right = self._seq_elem_of_expr(e.right, seen)
            return self._same_kind([left, right])
        if isinstance(e, ast.IfExp):
            left = self._seq_elem_of_expr(e.body, seen)
            right = self._seq_elem_of_expr(e.orelse, seen)
            return self._same_kind([left, right])
        if isinstance(e, ast.Call):
            if isinstance(e.func, ast.Name):
                name = e.func.id
                if name in ('list', 'sorted', 'reversed') and e.args and not e.keywords:
                    return self._seq_elem_of_expr(e.args[0], seen)
                if name == 'range':
                    return 'int'
                if name == 'str':
                    return 'str'
                if name in ('enumerate', 'zip'):
                    return None
            if isinstance(e.func, ast.Attribute):
                if e.func.attr in ('split', 'rsplit', 'splitlines'):
                    return 'str'
        return None

    def _attribute_sources(self, attr):
        fn = getattr(self.lib, 'cur_fn', None)
        if fn is not None:
            nodes = list(self._local_nodes(fn))
        else:
            nodes = []
            for top in self.lib.tree.body:
                nodes.extend(self._local_nodes([top]))
        out = []
        for node in nodes:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == attr:
                        out.append(('val', node.value))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Attribute) and node.target.attr == attr:
                out.append(('ann', node.annotation))
        if not out:
            for cls in (n for n in ast.walk(self.lib.tree) if isinstance(n, ast.ClassDef)):
                for node in cls.body:
                    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == attr:
                        out.append(('ann', node.annotation))
                    elif isinstance(node, ast.Assign) and any(
                            isinstance(t, ast.Name) and t.id == attr for t in node.targets):
                        out.append(('val', node.value))
        return out

    def _attribute_kind(self, node, seen):
        key = ('attr', node.attr)
        if key in seen:
            return None
        seen = seen | {key}
        sources = self._attribute_sources(node.attr)
        if not sources:
            return None
        kinds = []
        for source, value in sources:
            kind = self._ann_scalar(value) if source == 'ann' else self._kind_of_expr(value, seen)
            if kind is None:
                return None
            kinds.append(kind)
        return self._same_kind(kinds)

    def _attribute_container(self, node, seen):
        key = ('attr', node.attr)
        if key in seen:
            return None
        seen = seen | {key}
        sources = self._attribute_sources(node.attr)
        if not sources:
            return None
        infos = []
        for source, value in sources:
            info = self._ann_container(value) if source == 'ann' else self._container_of_expr(value, seen)
            if info is None:
                return None
            infos.append(info)
        if not infos:
            return None
        return infos[0] if all(info == infos[0] for info in infos) else None

    def _function_return_kind(self, name, seen):
        if name in seen:
            return None
        seen = seen | {name}
        for node in ast.walk(self.lib.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                if node.returns is not None:
                    return self._ann_scalar(node.returns)
                kinds = []
                for inner in node.body:
                    for each in ast.walk(inner):
                        if isinstance(each, ast.Return) and each.value is not None:
                            kind = self._kind_of_expr(each.value, seen)
                            if kind is None:
                                return None
                            kinds.append(kind)
                return self._same_kind(kinds)
        return None

    def _kind_of_expr(self, e, seen=None):
        seen = set() if seen is None else seen
        if isinstance(e, ast.Constant):
            value = e.value
            if isinstance(value, bool):
                return 'bool'
            if isinstance(value, int):
                return 'int'
            if isinstance(value, float):
                return 'float'
            if isinstance(value, str):
                return 'str'
            if isinstance(value, (bytes, bytearray)):
                return 'bytes'
            return None
        if isinstance(e, ast.Name):
            return self._kind_of_name(e.id, seen)
        if isinstance(e, ast.NamedExpr):
            return self._kind_of_expr(e.value, seen)
        if isinstance(e, ast.UnaryOp):
            if isinstance(e.op, ast.Not):
                return 'bool'
            return self._kind_of_expr(e.operand, seen)
        if isinstance(e, ast.BoolOp):
            return 'bool'
        if isinstance(e, ast.Compare):
            return 'bool'
        if isinstance(e, ast.IfExp):
            return self._same_kind([self._kind_of_expr(e.body, seen), self._kind_of_expr(e.orelse, seen)])
        if isinstance(e, ast.BinOp):
            left = self._kind_of_expr(e.left, seen)
            right = self._kind_of_expr(e.right, seen)
            if isinstance(e.op, ast.Add) and left == right == 'str':
                return 'str'
            if isinstance(e.op, ast.Mod) and left == 'str':
                return 'str'
            if isinstance(e.op, ast.Mult) and 'str' in (left, right) and {left, right} <= {'str', 'int'}:
                return 'str'
            if left in self._NUMERIC_TYPES and right in self._NUMERIC_TYPES:
                if isinstance(e.op, ast.Div):
                    return 'float'
                return 'float' if 'float' in (left, right) else 'int'
            return None
        if isinstance(e, ast.Subscript):
            if isinstance(e.slice, ast.Slice):
                return None
            if isinstance(e.value, ast.Dict) and isinstance(e.slice, ast.Constant):
                for key, value in zip(e.value.keys, e.value.values):
                    if isinstance(key, ast.Constant) and key.value == e.slice.value:
                        return self._kind_of_expr(value, seen)
            info = self._container_of_expr(e.value, seen)
            if info is None:
                return None
            if info[0] == 'dict':
                return info[2]
            if info[0] in ('list', 'set', 'tuple'):
                return info[1] if len(info) > 1 else None
            if info[0] == 'str':
                return 'str'
            return None
        if isinstance(e, ast.Attribute):
            return self._attribute_kind(e, seen)
        if isinstance(e, ast.Call):
            if isinstance(e.func, ast.Name):
                name = e.func.id
                if name in ('len', 'int', 'ord', 'hash'):
                    return 'int'
                if name == 'round':
                    return 'int' if len(e.args) == 1 else ('float' if e.args else None)
                if name == 'float':
                    return 'float'
                if name == 'abs' and e.args:
                    return self._kind_of_expr(e.args[0], seen)
                if name in ('bool', 'isinstance', 'callable', 'any', 'all'):
                    return 'bool'
                if name in ('str', 'repr', 'chr', 'input', 'format', 'ascii', 'hex', 'oct', 'bin'):
                    return 'str'
                if name == 'bytes':
                    return 'bytes'
                if name in ('min', 'max', 'sum') and e.args:
                    if len(e.args) == 1:
                        return self._seq_elem_of_expr(e.args[0], seen)
                    return self._same_kind([self._kind_of_expr(arg, seen) for arg in e.args])
                return self._function_return_kind(name, seen)
            if isinstance(e.func, ast.Attribute):
                attr = e.func.attr
                if attr in ('lower', 'upper', 'strip', 'lstrip', 'rstrip', 'title', 'capitalize',
                            'swapcase', 'replace', 'zfill', 'join'):
                    return 'str'
                if attr in ('find', 'rfind', 'index', 'count'):
                    return 'int'
                if attr in ('startswith', 'endswith', 'isdigit', 'isalpha', 'isalnum', 'isspace',
                            'isupper', 'islower'):
                    return 'bool'
                if attr == 'pop':
                    info = self._container_of_expr(e.func.value, seen)
                    if info is not None and info[0] == 'dict':
                        return info[2]
                    if info is not None and info[0] in ('list', 'set', 'tuple'):
                        return info[1] if len(info) > 1 else None
                if attr == 'get' and e.args:
                    info = self._container_of_expr(e.func.value, seen)
                    if info is not None and info[0] == 'dict':
                        return info[2]
            return None
        return None

    def expr_kind(self, expr):
        return self._kind_of_expr(expr)

    def seq_elem_kind(self, expr):
        return self._seq_elem_of_expr(expr, set())

    def element_immutable(self, seq):
        return self.seq_elem_kind(seq.expr) in self._SCALAR_TYPES

    def pure_key(self, key):
        for each in ast.walk(key):
            if isinstance(each, ast.Call):
                f = each.func
                if isinstance(f, ast.Name) and f.id in PURE_CALLS:
                    continue
                if isinstance(f, ast.Attribute) and f.attr in PURE_METHODS:
                    continue
                return False
            if isinstance(each, ast.NamedExpr):
                return False
        return True

    def seq_only(self, expr):
        src = self.leaf(expr, False)
        if not isinstance(src, Seq):
            refuse(expr, 'itertools: this argument has to be a list or str (held in a variable or written out), '
                   'not a range; wrap it in list(...)')
        return src

    def leaf(self, expr, streams=True):
        if streams:
            name = self.name_of(expr)
            if name is not None:
                src = self.build(expr)
                if not src.scalar():
                    refuse(expr, 'itertools.%s yields tuples here; a tuple-valued stream cannot be the input of '
                           'another itertools function' % name)
                return src
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == 'range':
            return RangeSeq(self, expr)
        if isinstance(expr, ast.Name) and expr.id in self.lib.sequences:
            return Seq(self, expr, expr.id)
        if self.lib.seq_expr(expr):
            return Seq(self, expr, None)
        refuse(expr, 'itertools: %s is not known to be a list / str here (a list or str parameter or a variable '
               'bound only to lists / strs, a slice, a literal, a comprehension or range(...)); bind it to a '
               'name first, or wrap it in list(...)' % ast.unparse(expr))

    # -- applying a function to values ---------------------------------------------------------------
    def apply2(self, func, a, b):
        if isinstance(func, ast.Lambda):
            args = func.args
            if (len(args.args) != 2 or args.vararg or args.kwarg or args.kwonlyargs or args.defaults
                    or args.posonlyargs):
                return None
            p, q = args.args[0].arg, args.args[1].arg
            if p == q:
                return None
            body = copy.deepcopy(func.body)
            if _rebinds(body, p) or _rebinds(body, q):
                return None
            return _mark(_Subst(q, b).visit(_Subst(p, a).visit(body)))
        if isinstance(func, ast.Name):
            return _mark(_call(copy.deepcopy(func), a, b))
        return None

    # -- binding the loop target ---------------------------------------------------------------------
    def targets(self, src, target, origin):
        """(out names, binding statements) for the item(s) of `src`."""
        if isinstance(src, PoolStream) and isinstance(target, ast.Tuple):
            if not all(isinstance(e, ast.Name) for e in target.elts):
                refuse(origin, 'itertools: the loop target has to be a name or a tuple of names')
            src.use_arity(len(target.elts))
        arity = src.arity
        if isinstance(target, ast.Name):
            if arity == 1 or arity == 'list':
                if target.id in src.live():
                    refuse(origin, 'itertools: the loop variable %s is also the list being walked' % target.id)
                if arity == 'list':
                    self.check_nonescaping(target.id, origin)
                return [target.id], []
            self.check_nonescaping(target.id, origin)
            out = [self.fresh('it%d' % k) for k in range(arity)]
            bind = ast.Assign(targets=[_name(target.id, True)], value=ast.List(
                elts=[_name(o) for o in out], ctx=ast.Load()))
            return out, [bind]
        if isinstance(target, ast.Tuple) and all(isinstance(e, ast.Name) for e in target.elts):
            if arity == 'list' or arity == 1 or len(target.elts) != arity:
                refuse(origin, 'itertools: the loop unpacks %d names but each item has %s' % (
                    len(target.elts), 'one value' if arity == 1 else arity))
            out = [self.fresh('it%d' % k) for k in range(arity)]
            bind = [ast.Assign(targets=[_name(e.id, True)], value=_name(o)) for e, o in zip(target.elts, out)]
            return out, bind
        refuse(origin, 'itertools: the loop target has to be a name or a tuple of names')

    def check_nonescaping(self, name, origin):
        """The tuple bound to `name` is held as a list: it may only be indexed, iterated, measured or reduced."""
        scope = self.lib.cur_fn if self.lib.cur_fn is not None else self.lib.tree
        parents = {}
        for parent in ast.walk(scope):
            for child in ast.iter_child_nodes(parent):
                parents[id(child)] = parent
        for each in ast.walk(scope):
            if not (isinstance(each, ast.Name) and each.id == name and isinstance(each.ctx, ast.Load)):
                continue
            parent = parents.get(id(each))
            ok = False
            if isinstance(parent, ast.Subscript) and parent.value is each and not isinstance(parent.slice, ast.Slice):
                ok = True
            elif isinstance(parent, ast.Call) and each in parent.args and len(parent.args) == 1 \
                    and isinstance(parent.func, ast.Name) and parent.func.id in NONESCAPE_CALLS:
                ok = True
            elif isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute) \
                    and parent.func.attr == 'join' and each in parent.args:
                ok = True
            elif isinstance(parent, (ast.For, ast.comprehension)) and parent.iter is each:
                ok = True
            elif isinstance(parent, ast.Compare) and each in parent.comparators and len(parent.ops) == 1 \
                    and isinstance(parent.ops[0], (ast.In, ast.NotIn)):
                ok = True
            elif isinstance(parent, ast.Attribute) and parent.value is each and parent.attr in ('index', 'count'):
                ok = True
            if not ok:
                refuse(each, 'itertools: %s holds a tuple in CPython; here it is a list, and this use of it '
                       '(print, ==, a dict key, a slice...) would differ. Index it, loop over it, or unpack the '
                       'tuple into names in the for statement' % name)

    # -- loops ----------------------------------------------------------------------------------------
    def loop(self, src, target, body, origin):
        out, bind = self.targets(src, target, origin)
        written = stored_names(body)
        for name in src.live():
            if name in written:
                refuse(origin, 'itertools: %s is assigned inside the loop that walks it (CPython keeps walking '
                       'the old list); loop over a copy: list(%s)' % (name, name))
        setup = src.setup(self)
        step = src.step(self, out, [ast.Break()])
        loop = ast.While(test=const(True), body=step + bind + body, orelse=[])
        stmts = [*setup, loop]
        _locate(stmts, origin)
        return stmts

    def for_statement(self, node):
        src = self.stream_of(node.iter)
        if src is None:
            return None
        if node.orelse:
            refuse(node, 'a for ... else over an itertools stream is not built')
        return self.lib.block(self.loop(src, node.target, node.body, node))

    def stream_of(self, it):
        """The stream a for loop / consumer walks, or None when it is not an itertools one."""
        if self.name_of(it) is not None:
            return self.build(it)
        if (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'zip'
                and len(it.args) >= 2 and not it.keywords
                and any(self.name_of(a) in ('count', 'repeat', 'chain', 'islice', 'accumulate') for a in it.args)):
            return ZipStreams([self.leaf(a) for a in it.args])
        return None

    def statement(self, node):
        return None

    # -- comprehensions and consumers ------------------------------------------------------------------
    def comp_loops(self, comp, mode, origin):
        """Statements that compute a comprehension, and the expression holding its value.
        mode 'list': a list; 'any' / 'all': a bool computed with an early exit."""
        mapping = {}
        for gen in comp.generators:
            if gen.is_async:
                refuse(origin, 'async comprehensions are not built')
            for n in ast.walk(gen.target):
                if isinstance(n, ast.Name):
                    mapping[n.id] = self.fresh(n.id)
        rename = _Rename(mapping)
        result, done = self.fresh('res'), self.fresh('done')
        elt = _mark(rename.visit(copy.deepcopy(comp.elt)))
        if mode == 'list':
            pre = [assign(result, ast.List(elts=[], ctx=ast.Load()))]
            core = [ast.Expr(value=_call(ast.Attribute(value=_name(result), attr='append', ctx=ast.Load()), elt))]
        else:
            pre = [assign(result, const(mode == 'all')), assign(done, const(False))]
            test = elt if mode == 'any' else ast.UnaryOp(op=ast.Not(), operand=elt)
            core = [ast.If(test=test, body=[assign(result, const(mode == 'any')), assign(done, const(True)),
                                            ast.Break()], orelse=[])]
        inner = core
        depth = len(comp.generators)
        for index in reversed(range(depth)):
            gen = comp.generators[index]
            for condition in reversed(gen.ifs):
                inner = [ast.If(test=_mark(rename.visit(copy.deepcopy(condition))), body=inner, orelse=[])]
            iterable = copy.deepcopy(gen.iter)
            if index > 0:
                iterable = rename.visit(iterable)
            _mark(iterable)
            body = inner
            if mode != 'list' and index < depth - 1:
                body = inner + [ast.If(test=_name(done), body=[ast.Break()], orelse=[])]
            inner = [ast.For(target=_mark(rename.visit(copy.deepcopy(gen.target))), iter=iterable, body=body,
                             orelse=[], type_comment=None)]
        statements = pre + inner
        _locate(statements, origin)
        return statements, _name(result)

    def bind(self, call, statements):
        """The consumer call computed into a temporary, so that a later operand of the same statement is again the first thing it evaluates."""
        temp = self.fresh("v")
        made = assign(temp, call)
        _locate([made], call)
        return _name(temp), statements + [made]

    def as_genexp(self, call):
        var = self.fresh('v')
        return ast.GeneratorExp(elt=_name(var), generators=[ast.comprehension(
            target=_name(var, True), iter=call, ifs=[], is_async=0)])

    def hoist(self, e):
        """(expression, statements) for a comprehension / consumer / reduce that needs statements; None otherwise."""
        if isinstance(e, ast.ListComp) and self.has_itertools(e):
            statements, result = self.comp_loops(e, 'list', e)
            return result, statements
        if (isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in CONSUMERS
                and e.args and not any(isinstance(a, ast.Starred) for a in e.args)):
            arg = e.args[0]
            direct = self.stream_of(arg) is not None
            if direct or (isinstance(arg, (ast.GeneratorExp, ast.ListComp)) and self.has_itertools(arg)):
                comp = self.as_genexp(arg) if direct else arg
                if e.func.id in ('any', 'all') and len(e.args) == 1 and not e.keywords:
                    statements, result = self.comp_loops(comp, e.func.id, e)
                    return result, statements
                statements, result = self.comp_loops(comp, 'list', e)
                if e.func.id == 'list' and len(e.args) == 1 and not e.keywords:
                    return result, statements
                e.args = [result] + e.args[1:]
                return self.bind(e, statements)
        if (isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == 'join'
                and len(e.args) == 1 and not e.keywords):
            arg = e.args[0]
            direct = self.stream_of(arg) is not None
            if direct or (isinstance(arg, (ast.GeneratorExp, ast.ListComp)) and self.has_itertools(arg)):
                statements, result = self.comp_loops(self.as_genexp(arg) if direct else arg, 'list', e)
                e.args = [result]
                return self.bind(e, statements)
        if isinstance(e, ast.Call) and self.imports.resolve(e.func) == ('functools', 'reduce'):
            return self.reduce(e)
        return None

    def call_expr(self, call, module, attr, node):
        return call

    # -- functools.reduce -------------------------------------------------------------------------------
    def reduce(self, call):
        lib = self.lib
        if call.keywords:
            refuse(call, 'functools.reduce takes positional arguments (CPython 3.12 refuses keywords)')
        if not 2 <= len(call.args) <= 3 or any(isinstance(a, ast.Starred) for a in call.args):
            refuse(call, 'functools.reduce(function, iterable[, initial])')
        func, iterable = call.args[0], call.args[1]
        initial = call.args[2] if len(call.args) == 3 else None
        pre = []
        if isinstance(iterable, (ast.ListComp, ast.GeneratorExp)) or (
                isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name)
                and iterable.func.id in ('map', 'filter')):
            comp = iterable
            if isinstance(iterable, ast.Call):
                comp = lib.as_comprehension(iterable, False)
                if comp is None:
                    refuse(call, 'functools.reduce over %s(...): bind the result to a list first' % iterable.func.id)
            if isinstance(comp, ast.GeneratorExp):
                comp = ast.ListComp(elt=comp.elt, generators=comp.generators)
            holder = self.fresh('rl')
            made = assign(holder, comp)
            _locate([made], call)
            pre.append(made)
            src = Seq(self, _name(holder), holder)
        elif self.name_of(iterable) is not None:
            src = self.build(iterable)
            if not src.scalar():
                refuse(call, 'functools.reduce over a stream of tuples is not built')
        else:
            src = self.leaf(iterable, False)
        acc, started, x = self.fresh('acc'), self.fresh('st'), self.fresh('x')
        combine = self.apply2(func, _name(acc), _name(x))
        if combine is None:
            refuse(call, 'functools.reduce: the function has to be a lambda of two parameters, a function name '
                   '(or max / min) or an operator function')
        setup = src.setup(self)
        pull = src.step(self, [x], [ast.Break()])
        is_first = ast.Compare(left=_name(started), ops=[ast.Eq()], comparators=[const(0)])
        if initial is not None:
            pre.append(assign(acc, initial))
            loop_body = pull + [assign(acc, combine)]
            tail = []
        else:
            pre.append(assign(started, const(0)))
            loop_body = pull + [ast.If(test=is_first, body=[assign(acc, _name(x)), assign(started, const(1))],
                                       orelse=[assign(acc, combine)])]
            tail = [ast.If(test=copy.deepcopy(is_first), body=[ast.Raise(exc=_call(_name("RuntimeError"), const(
                'reduce() of empty iterable with no initial value')), cause=None)], orelse=[])]
        statements = pre + setup + [ast.While(test=const(True), body=loop_body, orelse=[])] + tail
        _locate(statements, call)
        return _name(acc), statements
