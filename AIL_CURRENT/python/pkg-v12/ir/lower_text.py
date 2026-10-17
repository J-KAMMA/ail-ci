"""Lowering of text (stage S4a), as a mixin of `lower.Lowering`: str and bytes values as views
(`ail_str`, `ail_bytes`) over the function's arenas, `len`/index/slice/compare/`in`, concatenation and
f-strings, conversions between int/float and str, `print`, `sys.argv`, `sys.exit`, `read_stdin_bytes`,
`.encode()`/`.decode()` and the strip family. Everything the legacy typed path knows about a shape is
asked of the legacy front end (`_etype`, `_parse_braces_spec`, ...); the runtime calls are the legacy
runtime's own (rtc.py), so legacy and IR functions agree on every message and every byte printed.

Storage is the legacy policy: allocating results go to the function's str arena (`ail_sarena`), freed
at return; loops that allocate reset it per iteration with every str place as a root (emit_text.py).
No value in the IR owns text.
"""
import ast

from . import ir as I
from . import rtc

STRV, BYTES = I.STRV, I.BYTES


class NotS0(Exception):
    """The function is outside the lowered subset; the message says why."""



class TextLowering(object):
    NotS0 = NotS0
    onecp = frozenset()

    # ------------------------------------------------------------------ typing
    def text_kind(self, node):
        """'str' or 'bytes' when the legacy front end types `node` as one, else None."""
        if isinstance(node, (ast.Constant,)) and not isinstance(node.value, (str, bytes)):
            return None
        P = self.P
        try:
            kind = P._etype(node, self.ctx)
        except Exception:
            return None
        if kind == P.STR:
            return 'str'
        if kind == P.BYTES:
            return 'bytes'
        return None

    def is_str(self, node):
        return self.text_kind(node) == 'str'

    @staticmethod
    def src(node):
        try:
            return ast.unparse(node)[:70]
        except Exception:
            return type(node).__name__

    def rt(self, callee, operands, attrs=None):
        spec = rtc.ENTRIES[callee]
        results = list(spec['results'])
        ins = self.b.emit('rt', operands, results, dict(attrs or {}, callee=callee))
        return ins.results[0] if results else None

    def str_lit(self, text):
        return self.b.value('str.lit', [], STRV, {'value': text})

    # ------------------------------------------------------------------ cursors
    def cursor_of(self, node):
        """The cursor id of a str name whose value never changes in this function (a parameter never
        assigned, or a local assigned exactly once by a top-level statement of the body), else None.
        The same rule as the legacy `_str_cursor`."""
        if not isinstance(node, ast.Name):
            return None
        cache = self.__dict__.setdefault('cursor_ids', {})
        name = node.id
        if name in cache:
            return cache[name]
        fn = self.fn
        params = {a.arg for a in (*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs)}
        stores = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == name
                  and isinstance(n.ctx, (ast.Store, ast.Del))]
        top = [s for s in fn.body if isinstance(s, (ast.Assign, ast.AnnAssign))
               and any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Store)
                       for target in (s.targets if isinstance(s, ast.Assign) else [s.target])
                       for n in ast.walk(target))]
        captured = any(isinstance(n, (ast.Lambda, ast.FunctionDef)) and n is not fn
                       and any(isinstance(m, ast.Name) and m.id == name for m in ast.walk(n))
                       for n in ast.walk(fn))
        ok = not captured and ((name in params and not stores)
                               or (name not in params and len(stores) == 1 and len(top) == 1))
        # ids are dense, in the order of first use
        cache[name] = sum(1 for v in cache.values() if v is not None) if ok else None
        return cache[name]

    # ------------------------------------------------------------------ text expressions
    def text_expr(self, node, kind):
        if kind == 'bytes':
            return self.bytes_expr(node)
        if isinstance(node, ast.Constant):
            return self.str_lit(node.value)
        if isinstance(node, ast.Name):
            return self.name_value(node)
        if isinstance(node, ast.JoinedStr):
            return self.concat(self.fstring_pieces(node, buf_always=False))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.str_add(node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) \
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            return self.percent(node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            return self.str_repeat(node)
        if isinstance(node, ast.IfExp):
            return self.ifexp(node)
        if isinstance(node, ast.Subscript):
            return self.str_subscript(node)
        if isinstance(node, ast.Call):
            return self.str_call(node)
        raise self.NotS0('a str expression of shape %s' % type(node).__name__)

    def name_value(self, node):
        if node.id in self.scope_vars:
            return self.scope_vars[node.id]
        if node.id in self.places:
            place = self.places[node.id]
            return self.b.value('load', [place], place.type.pointee)
        if node.id in self.params:
            return self.params[node.id]
        entry = getattr(self.ctx, 'modconsts', {}).get(node.id)
        if entry is not None and entry[0] == self.P.STR and isinstance(entry[1], str):
            return self.str_lit(entry[1])
        raise self.NotS0('name %r' % node.id)

    # --- concatenation and f-strings
    def concat(self, vals):
        if not vals:
            return self.str_lit('')
        if len(vals) == 1:
            return vals[0]
        if len(vals) == 2:
            return self.rt('str_cat', vals)
        return self.rt('str_catn', vals)

    def str_repeat(self, node):
        P = self.P
        kinds = [P.STR if self.is_str(arg) else P._etype(arg, self.ctx) for arg in (node.left, node.right)]
        if tuple(kinds) not in ((P.STR, P.INT), (P.INT, P.STR)):
            raise self.NotS0('str repetition of %r' % (kinds,))
        a = self.expr(node.left)
        b = self.expr(node.right)
        s, n = (a, b) if kinds[0] == P.STR else (b, a)
        return self.rt('str_repeat', [s, self.as_int(n)])

    def is_str_call_of_int(self, e):
        """`str(<int>)`: its digits can be written to a buffer of the consuming block."""
        P = self.P
        if not (isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == 'str'
                and self.is_builtin('str') and len(e.args) == 1 and not e.keywords):
            return False
        try:
            return P._etype(e.args[0], self.ctx) == P.INT and not P._is_bool_expr(e.args[0], self.ctx)
        except Exception:
            return False

    def str_add(self, node):
        parts = []
        cur = node
        while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Add) and self.is_str(cur.left) \
                and self.is_str(cur.right):
            parts.append(cur.right)
            cur = cur.left
        parts.append(cur)
        parts.reverse()
        many = len(parts) >= 3
        vals = [self.str_from_int(e.args[0], buf=True) if many and self.is_str_call_of_int(e)
                else self.expr(e) for e in parts]
        return self.concat(vals)

    def str_from_int(self, arg, buf):
        v = self.as_int(self.expr(arg))
        return self.rt('str_from_int_buf' if buf else 'str_from_int', [v])

    def fstring_pieces(self, node, buf_always):
        vals = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                vals.append(self.str_lit(v.value))
            elif isinstance(v, ast.FormattedValue):
                vals.append(self.fstring_field(v))
            else:
                raise self.NotS0('an f-string piece of type %s' % type(v).__name__)
        # a decimal rendering is a buffer of the consuming block when three or more pieces are joined
        # (ail_str_catn copies) and always when the pieces go straight to stdout
        if buf_always or len(vals) >= 3:
            for v in vals:
                ins = self.def_of(v)
                if ins is not None and ins.op == 'rt' and ins.attrs.get('callee') == 'str_from_int':
                    ins.attrs['callee'] = 'str_from_int_buf'
        return vals

    def def_of(self, v):
        for ins in reversed(self.b.region.instrs):
            if v in ins.results:
                return ins
        return None

    def fstring_field(self, fv):
        P = self.P
        if fv.conversion not in (-1, 115):
            raise self.NotS0('an f-string conversion')
        val = fv.value
        kind = P._etype(val, self.ctx)
        if kind not in (P.INT, P.FLT, P.STR):
            raise self.NotS0('an f-string field of kind %r' % (kind,))
        if kind == P.INT and P._is_bool_expr(val, self.ctx):
            raise self.NotS0('a bool in an f-string')
        if fv.format_spec is None:
            return self.default_conv(val, kind)
        fs = fv.format_spec
        if not isinstance(fs, ast.JoinedStr) or len(fs.values) > 1 \
                or (fs.values and not isinstance(fs.values[0], ast.Constant)):
            raise self.NotS0('a nested format spec')
        spec_text = fs.values[0].value if fs.values else ''
        spec = P._parse_braces_spec(spec_text)
        return self.fmt_value(val, kind, spec, spec_text, '<')

    def default_conv(self, node, kind):
        P = self.P
        if kind == P.STR:
            return self.expr(node)
        if kind == P.INT:
            if P._is_bool_expr(node, self.ctx):
                raise self.NotS0('a bool converted to str')
            return self.rt('str_from_int', [self.as_int(self.expr(node))])
        return self.rt('str_from_float', [self.coerce(self.expr(node), I.F64)])

    def fmt_value(self, val_node, kind, spec, orig_text, str_default_align):
        """The runtime formatter call for a parsed spec (legacy `_fmt_build`)."""
        P = self.P
        P._resolve_fmt_type(spec, kind, orig_text, 'an f-string field with spec')
        width = spec['width'] or 0
        zero = 1 if spec['zero'] else 0
        fill = spec.get('fill', ' ')
        align_char = spec['align']
        if align_char is None:
            align_char = str_default_align if kind == P.STR else '>'
        align = 1 if align_char == '<' else (2 if align_char == '^' else 0)
        if kind == P.INT:
            v = self.as_int(self.expr(val_node))
            return self.rt('fmt_int', [v], {'width': width, 'align': align, 'zero': zero, 'fill': ord(fill)})
        if kind == P.FLT:
            prec = spec['precision'] if spec['precision'] is not None else -1
            v = self.coerce(self.expr(val_node), I.F64)
            return self.rt('fmt_float', [v], {'width': width, 'align': align, 'zero': zero, 'prec': prec,
                                              'fill': ord(fill)})
        prec = spec['precision'] if spec['precision'] is not None else -1
        sv = self.expr(val_node)
        if width <= 0 and prec < 0:
            return sv
        return self.rt('fmt_str', [sv], {'width': width, 'align': align, 'prec': prec})

    def percent(self, node):
        """`"..." % args`: the declared subset of the legacy `_build_percent_value`."""
        P = self.P
        fmt_text = node.left.value
        args = P._percent_args(node.right)
        pieces = P._percent_pieces(fmt_text)
        if sum(1 for k, _ in pieces if k == 'spec') != len(args):
            raise self.NotS0('% format argument count')
        vals = []
        k = 0
        for kind_, piece in pieces:
            if kind_ == 'lit':
                vals.append(self.str_lit(piece))
                continue
            argnode = args[k]
            k += 1
            kind = P._etype(argnode, self.ctx)
            if kind not in (P.INT, P.FLT, P.STR):
                raise self.NotS0('% formatting of kind %r' % (kind,))
            if piece['type'] == 's' and kind in (P.INT, P.FLT) and not piece['zero']:
                argnode = ast.copy_location(ast.Call(func=ast.Name(id='str', ctx=ast.Load()), args=[argnode],
                                                     keywords=[]), argnode)
                kind = P.STR
            spec = {'align': '<' if piece['leftalign'] else None, 'zero': piece['zero'],
                    'width': piece['width'], 'precision': piece['precision'], 'type': piece['type']}
            vals.append(self.fmt_value(argnode, kind, spec, piece['src'], '>'))
        if len(vals) >= 3:
            for v in vals:
                ins = self.def_of(v)
                if ins is not None and ins.op == 'rt' and ins.attrs.get('callee') == 'str_from_int':
                    ins.attrs['callee'] = 'str_from_int_buf'
        return self.concat(vals)

    # --- indexing, slicing, argv
    def is_argv(self, node):
        return self.P._is_sys_argv(node)

    def str_subscript(self, node):
        P = self.P
        if P._is_sys_argv_index(node):
            i = self.as_int(self.expr(node.slice))
            return self.rt('argv_get', [i])
        if not self.is_str(node.value):
            raise self.NotS0('subscript of a non-str text value')
        base = self.expr(node.value)
        cur = self.cursor_of(node.value)
        if isinstance(node.slice, ast.Slice):
            if node.slice.step is not None:
                raise self.NotS0('a stepped str slice')
            lo = self.as_int(self.expr(node.slice.lower)) if node.slice.lower else self.const(I.I64, 0)
            hi = self.as_int(self.expr(node.slice.upper)) if node.slice.upper else self.const(I.I64, (1 << 63) - 1)
            if cur is not None:
                return self.rt('str_slice_cur', [base, lo, hi], {'cur': cur})
            return self.rt('str_slice', [base, lo, hi])
        i = self.as_int(self.expr(node.slice))
        if cur is not None:
            return self.rt('str_index_cur', [base, i], {'cur': cur})
        return self.rt('str_index', [base, i])

    # --- calls that build or read str
    def str_call(self, node):
        P = self.P
        if P._is_sys_stdin_call(node):
            return self.rt('stdin_read' if node.func.attr == 'read' else 'stdin_readline', [])
        if P._is_input_call(node):
            return self.rt('input', [])
        if node.keywords and not (isinstance(node.func, ast.Name) and node.func.id in self.ctx.funcs):
            raise self.NotS0('keywords in a text call')
        f = node.func
        if isinstance(f, ast.Name):
            name = f.id
            if name in self.ctx.funcs and name not in self.places and name not in self.params:
                v = self.user_call(name, node, False)
                if v is None:
                    raise self.NotS0('a void call used as a str')
                return v
            if self.is_builtin(name) and name == 'str' and len(node.args) == 1:
                arg = node.args[0]
                at = P._etype(arg, self.ctx)
                if at == P.FLT:
                    return self.rt('str_from_float', [self.expr(arg)])
                if at == P.INT and not P._is_bool_expr(arg, self.ctx):
                    return self.str_from_int(arg, buf=False)
                raise self.NotS0('str() of kind %r' % (at,))
            raise self.NotS0('str call of %r' % name)
        if isinstance(f, ast.Attribute):
            return self.str_method(node)
        raise self.NotS0('a str call of a non-name')

    def str_method(self, node):
        P = self.P
        f = node.func
        attr = f.attr
        if attr in ('strip', 'lstrip', 'rstrip') and self.is_str(f.value) and len(node.args) <= 1:
            recv = self.expr(f.value)
            if node.args:
                chars = self.expr(node.args[0])
                return self.rt('str_%s_chars' % attr, [recv, chars])
            return self.rt('str_%s' % attr, [recv])
        if attr == 'decode' and self.text_kind(f.value) == 'bytes' and not node.args and not node.keywords:
            return self.decode_value(f.value)
        raise self.NotS0('str method %s()' % attr)

    def bytes_arg(self, node):
        """A bytes operand that is consumed at once (appended, written, iterated, measured, concatenated): for
        `s.encode()` that is a view of `s`'s own UTF-8, with no copy and no block in the bytes arena."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'encode' \
                and self.is_str(node.func.value) and not node.args and not node.keywords:
            return self.rt('str_encode_view', [self.expr(node.func.value)])
        return self.expr(node)

    def bytes_search(self, node):
        """`d.find(x[, start[, end]])` / `rfind` where `d` and `x` are names or bytes literals and the bounds are
        arithmetic on names and literals: the legacy path's borrowing form (no copy of the operands)."""
        P = self.P

        def simple(e, bound):
            if isinstance(e, ast.Name):
                return True
            if bound:
                return not any(isinstance(n, (ast.Call, ast.Subscript, ast.Attribute)) for n in ast.walk(e))
            return isinstance(e, ast.Constant) and isinstance(e.value, bytes)
        recv, needle, bounds = node.func.value, node.args[0], node.args[1:]
        if not (simple(recv, False) and simple(needle, False) and all(simple(b, True) for b in bounds)) \
                or self.text_kind(needle) != 'bytes' or any(P._etype(b, self.ctx) != P.INT for b in bounds):
            raise self.NotS0('bytes search of a computed value')
        h = self.expr(recv)
        nd = self.expr(needle)
        start = self.as_int(self.expr(bounds[0])) if bounds else self.const(I.I64, 0)
        end = self.as_int(self.expr(bounds[1])) if len(bounds) > 1 else self.b.value('bytes.len', [h], I.I64)
        return self.rt('bytes_find_range' if node.func.attr == 'find' else 'bytes_rfind_range', [h, nd, start, end])

    def decode_value(self, source):
        # a decode of a name or a fresh read is a view/owned copy in the legacy path; the plain copy
        # (`ail_bytes_decode_utf8`) is the one every other source uses
        b = self.expr(source)
        if self.P._decode_view_source(source, self.ctx):
            return self.rt('bytes_decode_view', [b])
        return self.rt('bytes_decode', [b])

    # ------------------------------------------------------------------ bytes
    def bytes_expr(self, node):
        P = self.P
        if isinstance(node, ast.Constant):
            return self.b.value('bytes.lit', [], BYTES, {'data': list(node.value)})
        if isinstance(node, ast.Name):
            if node.id in self.params:
                return self.params[node.id]
            if node.id in self.places:
                place = self.places[node.id]
                return self.b.value('load', [place], place.type.pointee)
            raise self.NotS0('name %r' % node.id)
        if isinstance(node, ast.Attribute):
            obj, cls, kind = self.field_of(node)
            if kind != P.BYTES:
                raise self.NotS0('field %s.%s of kind %r as bytes' % (cls, node.attr, kind))
            return self.b.value('field.get', [obj], BYTES, {'cls': cls, 'name': node.attr})
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in ('read_stdin_bytes',) and self.is_builtin(f.id) \
                    and len(node.args) == 1 and not node.keywords:
                if getattr(self.ctx, 'stdin_borrow_call', None) is node:
                    raise self.NotS0('a borrowed stdin read')
                return self.rt('read_stdin_bytes', [self.as_int(self.expr(node.args[0]))])
            if isinstance(f, ast.Name) and f.id == 'read_bytes' and self.is_builtin(f.id) \
                    and len(node.args) == 1 and not node.keywords and self.text_kind(node.args[0]) == 'str':
                return self.rt('read_bytes', [self.expr(node.args[0])])
            if isinstance(f, ast.Attribute) and f.attr == 'encode' and self.is_str(f.value) \
                    and not node.args and not node.keywords:
                return self.rt('str_encode', [self.expr(f.value)])
            if isinstance(f, ast.Name) and f.id in self.ctx.funcs and f.id not in self.places \
                    and f.id not in self.params:
                v = self.user_call(f.id, node, False)
                if v is None:
                    raise self.NotS0('a void call used as bytes')
                return v
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice) and node.slice.step is None \
                and self.text_kind(node.value) == 'bytes':
            base = self.expr(node.value)
            lo = self.as_int(self.expr(node.slice.lower)) if node.slice.lower else self.const(I.I64, 0)
            hi = self.as_int(self.expr(node.slice.upper)) if node.slice.upper \
                else self.b.value('bytes.len', [base], I.I64)
            return self.rt('bytes_slice', [base, lo, hi])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and self.text_kind(node.left) == 'bytes' \
                and self.text_kind(node.right) == 'bytes':
            a = self.bytes_arg(node.left)
            b = self.bytes_arg(node.right)
            return self.rt('bytes_cat', [a, b])
        raise self.NotS0('a bytes expression: %s' % self.src(node))

    # ------------------------------------------------------------------ numbers and booleans of text
    def text_len(self, arg):
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return self.const(I.I64, len(arg.value))
        if isinstance(arg, ast.Attribute) or self.P._is_sys_argv(arg):
            raise self.NotS0('len() of an attribute')
        v = self.expr(arg)
        cur = self.cursor_of(arg)
        if cur is not None:
            return self.rt('str_len_cur', [v], {'cur': cur})
        return self.rt('str_len', [v])

    def str_compare(self, op, a, b):
        """A comparison of two str values (the operator node `op`)."""
        if isinstance(op, (ast.Eq, ast.NotEq)):
            eq = self.rt('str_eq', [a, b])
            if isinstance(op, ast.Eq):
                return eq
            return self.b.value('cmp.eq', [eq, self.const(I.I1, False)], I.I1)
        pred = {ast.Lt: 'lt', ast.LtE: 'le', ast.Gt: 'gt', ast.GtE: 'ge'}.get(type(op))
        if pred is None:
            raise self.NotS0('str comparison %s' % type(op).__name__)
        c = self.rt('str_cmp', [a, b])
        return self.b.value('cmp.' + pred, [c, self.const(I.I64, 0)], I.I1)

    def str_in(self, op, item, holder):
        r = self.rt('str_contains', [item, holder])
        if isinstance(op, ast.NotIn):
            return self.b.value('cmp.eq', [r, self.const(I.I1, False)], I.I1)
        return r

    # ------------------------------------------------------------------ iteration
    def for_str(self, s):
        """`for ch in text`: a loop over a byte offset that steps by the width of each character (the
        legacy loop's own shape); `ch` is a one-character view. The offset is a hidden local, so the
        loop is a plain `loop` with a carried value after mem2reg."""
        target = s.target.id
        if target in self.params or target not in self.places or self.places[target].type.pointee != STRV:
            raise self.NotS0('for target %r' % target)
        sv = self.expr(s.iter)
        n = self.rt('str_bytes', [sv])
        idx = self.new_place('si', I.I64)
        self.b.emit('store', [idx, self.const(I.I64, 0)])
        body = I.Region()
        rebound = any(isinstance(n_, ast.Name) and n_.id == target and isinstance(n_.ctx, (ast.Store, ast.Del))
                      for st in s.body for n_ in ast.walk(st))

        def loop_body():
            k = self.b.value('load', [idx], I.I64)
            c = self.b.value('cmp.lt', [k, n], I.I1)
            go, stop = I.Region(), I.Region()
            self.in_region(go, fill=lambda: self.b.emit('yield'))
            self.in_region(stop, fill=lambda: self.b.emit('break'))
            self.b.emit('if', [c], [], None, [go, stop])
            ch = self.rt('str_char_at', [sv, k])
            w = self.rt('str_bytes', [ch])
            self.b.emit('store', [idx, self.b.value('add', [k, w], I.I64, {'mode': 'nsw'})])
            self.b.emit('store', [self.places[target], ch])
            self.stmts(s.body)
            if not self.b.terminated():
                self.b.emit('continue')
        added = not rebound and target not in self.onecp
        if added:
            self.onecp.add(target)
        self.loop_depth += 1
        try:
            self.in_region(body, fill=loop_body)
        finally:
            self.loop_depth -= 1
            if added:
                self.onecp.discard(target)
        self.b.emit('loop', [], [], None, [body])

    @staticmethod
    def literal_value(e):
        """(kind, value) of a str, int or float literal (a negative number is a unary minus), else None."""
        neg = False
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub) and isinstance(e.operand, ast.Constant):
            e, neg = e.operand, True
        if not isinstance(e, ast.Constant) or isinstance(e.value, bool):
            return None
        if isinstance(e.value, str) and not neg:
            return 'str', e.value
        if isinstance(e.value, int):
            v = -e.value if neg else e.value
            return ('int', v) if -(1 << 63) <= v < (1 << 63) else None
        if isinstance(e.value, float):
            return 'float', (-e.value if neg else e.value)
        return None

    def literal_kind(self, elts):
        found = [self.literal_value(e) for e in elts]
        if any(f is None for f in found) or len({f[0] for f in found}) != 1:
            return None
        return found[0][0]

    def for_literals(self, s):
        """`for x in ["a", "b", ...]` (str, int or float literals): a counted loop whose element is chosen by
        index among the literals."""
        target = s.target.id
        kind = self.literal_kind(s.iter.elts)
        t = {'str': STRV, 'int': I.I64, 'float': I.F64}[kind]
        place = self.kind_places[target].get(t) if target in self.kind_places else self.places.get(target)
        if target in self.params or place is None or place.type.pointee != t:
            raise self.NotS0('for target %r' % target)
        lits = [self.literal_value(e)[1] for e in s.iter.elts]
        index = I.Value(I.I64, hint='k')
        body = I.Region([index])

        def lit(v):
            return self.str_lit(v) if kind == 'str' else self.const(t, v)

        def fill():
            v = lit(lits[-1])
            for k in range(len(lits) - 2, -1, -1):
                c = self.b.value('cmp.eq', [index, self.const(I.I64, k)], I.I1)
                v = self.b.value('select', [c, lit(lits[k]), v], t)
            self.b.emit('store', [place, v])
            self.stmts(s.body)
            if not self.b.terminated():
                self.b.emit('continue')
        self.loop_depth += 1
        try:
            self.in_region(body, fill=fill)
        finally:
            self.loop_depth -= 1
        self.b.emit('for.range', [self.const(I.I64, 0), self.const(I.I64, len(lits)), self.const(I.I64, 1)], [],
                    {'args': 1}, [body])

    # ------------------------------------------------------------------ statements
    def print_stmt(self, node):
        P = self.P
        sep_node = end_node = None
        stream = 'stdout'
        order = []
        for kw in node.keywords:
            if kw.arg == 'sep':
                sep_node = kw.value
                order.append('sep')
            elif kw.arg == 'end':
                end_node = kw.value
                order.append('end')
            elif kw.arg == 'file':
                path = P._sys_attr_path(kw.value)
                if path not in ('sys.stdout', 'sys.stderr'):
                    raise self.NotS0('print(file=...)')
                stream = path[4:]
            else:
                raise self.NotS0('print keyword %r' % kw.arg)
        kinds, vals = [], []
        parts = False
        for a0 in node.args:
            if P._is_bool_expr(a0, self.ctx):
                kinds.append('bool')
                vals.append(self.expr(a0))
                continue
            if self.text_kind(a0) == 'bytes':
                raise self.NotS0('print of bytes')
            t = P._etype(a0, self.ctx)
            if t == P.STR and isinstance(a0, ast.JoinedStr) and len(node.args) == 1 and not node.keywords \
                    and stream == 'stdout':
                pieces = self.fstring_pieces(a0, buf_always=True)
                self.b.emit('print', pieces, [], {'kinds': ['str'] * len(pieces), 'stream': 'stdout', 'parts': True})
                return
            if t == P.STR:
                kinds.append('str')
                vals.append(self.expr(a0))
            elif t == P.FLT:
                kinds.append('flt')
                vals.append(self.expr(a0))
            elif t == P.INT:
                kinds.append('int')
                vals.append(self.as_int(self.expr(a0)))
            else:
                raise self.NotS0('print of kind %r' % (t,))
        extra = {}
        for which in order:
            node_ = sep_node if which == 'sep' else end_node
            if self.text_kind(node_) != 'str':
                raise self.NotS0('print sep/end that is not a str')
            extra[which] = self.expr(node_)
        operands = vals + [extra[k] for k in ('sep', 'end') if k in extra]
        attrs = {'kinds': kinds, 'stream': stream}
        if 'sep' in extra:
            attrs['sep'] = True
        if 'end' in extra:
            attrs['end'] = True
        self.b.emit('print', operands, [], attrs)

    def sys_exit_stmt(self, node):
        P = self.P
        if node.keywords or len(node.args) > 1:
            raise self.NotS0('sys.exit shape')
        if node.args:
            if P._etype(node.args[0], self.ctx) != P.INT:
                raise self.NotS0('sys.exit of a non-int')
            v = self.as_int(self.expr(node.args[0]))
        else:
            v = self.const(I.I64, 0)
        self.rt('exit', [v])
