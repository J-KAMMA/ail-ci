"""C for the text stage (S4a), as a mixin of `emit_c.Emitter`: static literals, the runtime-call table
(`rtc.py`), `print`, the function's two arenas, cursor cells, and the per-iteration reset of the str
arena in loops that allocate text (the legacy policy: `ail_sarena_keep_roots` with every str place as
a root, so a text-heavy loop holds what the legacy build held).

Every helper called here is the legacy runtime's own, with its own messages: the IR changes who
calls them, not what they say.
"""
from . import ir as I
from . import rtc
from . import ownership

STRV, BYTES = I.STRV, I.BYTES


def c_literal(text):
    """A UTF-8 string as one `"\\xHH"` literal per byte (what the legacy path writes), its length, ASCII?"""
    data = text.encode('utf-8')
    body = ''.join('"' + chr(92) + 'x%X"' % b for b in data) or '""'
    return body, len(data), int(data.isascii())


def c_bytes_literal(data):
    return '(ail_bytes){(const unsigned char *)"%s", %d}' % (''.join(chr(92) + '%03o' % x for x in data), len(data))


def allocates_str(ins):
    """Whether `ins` puts a block into the function's str arena."""
    if ins.op == 'list.join':
        return True
    if ins.op == 'rt':
        spec = rtc.ENTRIES.get(ins.attrs.get('callee'))
        return bool(spec and spec['arena'] == 's')
    return ins.op == 'call' and bool(ins.results) and ins.results[0].type == STRV


def allocates_bytes(ins):
    if ins.op == 'rt':
        spec = rtc.ENTRIES.get(ins.attrs.get('callee'))
        return bool(spec and spec['arena'] == 'b')
    return ins.op == 'call' and bool(ins.results) and ins.results[0].type == BYTES


class TextEmitter(object):
    # ------------------------------------------------------------------ set-up
    def text_init(self, fn):
        """Which arenas this function needs, and its cursor cells. Called once, before the owned
        places are listed."""
        ops = list(I.walk(fn.body))
        self.needs_sar = any(allocates_str(i) for i in ops) or any(
            i.op == 'call' and i.results and i.results[0].type == STRV for i in ops)
        self.needs_bar = any(allocates_bytes(i) for i in ops)
        self.cursors = sorted(set(i.attrs['cur'] for i in ops if i.op == 'rt' and 'cur' in i.attrs))
        self.wins = sorted(set(i.attrs['win'] for i in ops if i.op == 'rt' and 'win' in i.attrs))
        self.str_places = [i for i in fn.body.instrs if i.op == 'local.alloc' and i.result.type.pointee == STRV]
        self.sar = self.pre + 'v__sarena'
        self.bar = self.pre + 'v__barena'
        self.roots_loops = 0

    def cursor_cells(self, k):
        return {'cp': '%sv__cp%d' % (self.pre, k), 'cu': '%sv__cu%d' % (self.pre, k), 'cl': '%sv__cl%d' % (self.pre, k)}

    def win_cell(self, k):
        return '%sv__win%d' % (self.pre, k)

    def text_fields(self):
        """Frame-struct fields for the arenas and cursors (functions with a try)."""
        fields = []
        for k in self.wins:
            fields.append('ail_win v__win%d;' % k)
        if self.needs_sar:
            fields.append('ail_sarena v__sarena;')
        if self.needs_bar:
            fields.append('ail_barena v__barena;')
        for k in self.cursors:
            fields.append('int64_t v__cp%d; int64_t v__cu%d; int64_t v__cl%d;' % (k, k, k))
        return fields

    def text_decls(self, depth):
        if self.frame:
            return
        if self.needs_sar:
            self.line(depth, 'ail_sarena v__sarena = {0};')
        if self.needs_bar:
            self.line(depth, 'ail_barena v__barena = {0};')
        for k in self.wins:
            self.line(depth, 'ail_win v__win%d = {0};' % k)
        for k in self.cursors:
            self.line(depth, 'int64_t v__cp%d = 0, v__cu%d = 0, v__cl%d = 0;' % (k, k, k))

    def text_parts(self):
        if self.needs_sar:
            self.parts.add('STR')
        if self.needs_bar:
            self.parts.add('BYTES')

    # ------------------------------------------------------------------ literals
    def emit_str_lit(self, ins, depth):
        body, n, ascii_ = c_literal(ins.attrs['value'])
        self.parts.add('STR')
        return self.assign_new(depth, ins.result, '(ail_str){(const uint8_t *)(%s), %d, %d}' % (body, n, ascii_))

    def emit_bytes_lit(self, ins, depth):
        self.parts.add('BYTES')
        return self.assign_new(depth, ins.result, c_bytes_literal(ins.attrs['data']))

    # ------------------------------------------------------------------ runtime calls
    def emit_rt(self, ins, depth, o):
        callee = ins.attrs['callee']
        spec = rtc.ENTRIES[callee]
        self.parts.update(spec['parts'])
        fields = {'A': '&' + self.sar, 'B': '&' + self.bar, 'va': ', '.join(o), 'n': len(o)}
        if 'win' in ins.attrs:
            fields['W'] = self.win_cell(ins.attrs['win'])
        if spec['cursor']:
            fields.update(self.cursor_cells(ins.attrs['cur']))
        for a in spec['attrs']:
            fields[a] = ins.attrs[a]
        text = spec['c'].format(*o, **fields)
        if callee in ('argv_get', 'str_index', 'str_index_cur', 'str_to_int', 'str_to_float', 'str_point',
                      'bytes_decode', 'bytes_decode_view', 'read_stdin_bytes', 'read_bytes', 'input', 'str_repeat'):
            self.parts.add('DIE')
        if ins.results:
            return self.assign_new(depth, ins.result, text)
        return self.line(depth, text + ';')

    # ------------------------------------------------------------------ print
    def emit_print(self, ins, depth, o):
        kinds = ins.attrs['kinds']
        stream = ins.attrs.get('stream', 'stdout')
        out = 'stdout' if stream == 'stdout' else 'stderr'
        values = o[:len(kinds)]
        rest = o[len(kinds):]
        sep = rest.pop(0) if ins.attrs.get('sep') else None
        end = rest.pop(0) if ins.attrs.get('end') else None
        self.parts.add('STDIO')
        if 'str' in kinds or sep or end:
            self.parts.add('STR')
        if 'flt' in kinds:
            self.parts.add('FREPR')
        if stream == 'stdout':
            self.line(depth, 'ail_stdout_text();')
        if ins.attrs.get('parts'):
            self.line(depth, 'ail_stdout_parts((ail_str[]){%s}, %d);' % (', '.join(values), len(values)))
            return
        for i, (kind, v) in enumerate(zip(kinds, values)):
            if i:
                if sep is not None:
                    self.line(depth, 'ail_str_write(%s, %s);' % (sep, out))
                else:
                    self.line(depth, 'ail_stdout_putc(32);' if stream == 'stdout' else 'fputc(32, stderr);')
            if kind == 'str':
                self.line(depth, 'ail_str_write(%s, %s);' % (v, out))
            elif kind == 'flt':
                self.line(depth, ('ail_write_float((double)(%s));' % v) if stream == 'stdout'
                          else 'ail_write_float_to((double)(%s), stderr);' % v)
            elif kind == 'bool':
                self.line(depth, ('ail_fputs_stdout((%s) ? "True" : "False");' % v) if stream == 'stdout'
                          else 'fputs((%s) ? "True" : "False", stderr);' % v)
            else:
                self.line(depth, ('ail_write_int((int64_t)(%s));' % v) if stream == 'stdout'
                          else 'ail_write_int_to((int64_t)(%s), stderr);' % v)
        if end is not None:
            self.line(depth, 'ail_str_write(%s, %s);' % (end, out))
        else:
            self.line(depth, 'ail_stdout_putc(10);' if stream == 'stdout' else 'fputc(10, stderr);')

    # ------------------------------------------------------------------ loops that allocate text
    def loop_allocates(self, loop):
        return self.needs_sar and any(allocates_str(i) for r in loop.regions for i in I.walk(r))

    def slist_blocks_reset(self, loop):
        """Whether resetting the str arena at the top of each iteration of `loop` could leave a list of str
        pointing at freed text (S3c-1). The elements of a list are views over arena blocks and, unlike a str
        place, cannot be re-pointed by `ail_sarena_keep_roots`. A list written in the loop (replaced, grown,
        sorted) and live at the loop header (read on some path before the loop writes it again, in a later
        iteration or after the loop) may hold views of blocks that the reset releases; a list only read in
        the loop holds what existed before the loop's mark, and a list rebuilt before it is read in every
        iteration is not live at the header. Liveness is the ownership analysis's (places of lists)."""
        places = [i.result for i in self.fn.body.instrs
                  if i.op == 'local.alloc' and i.result.type.pointee == I.T('obj', I.T('list', STRV))]
        if not places:
            return False
        if getattr(self, '_slist_flow', None) is None:
            self._slist_flow = ownership.Flow(self.fn, None, None)
        flow = self._slist_flow
        live = flow.live_in.get(loop, set())
        touched = set()
        for r in loop.regions:
            for ins in I.walk(r):
                touched |= flow.kills.get(ins, set()) | flow.writes.get(ins, set())
        return any(p in live and p in touched for p in places)

    def open_loop_roots(self, loop, depth):
        """Before a loop whose iterations allocate text: the mark and the root list (every str place)."""
        if not self.loop_allocates(loop) or self.slist_blocks_reset(loop):
            return None
        self.roots_loops += 1
        k = self.roots_loops
        roots = ['&' + self.names[p.result] for p in self.str_places]
        self.line(depth, '{')
        self.line(depth + 1, 'int64_t _fmark%d = %s.n;' % (k, self.sar))
        self.line(depth + 1, 'ail_str *_froots%d[] = {%s};' % (k, ', '.join(roots) if roots else 'NULL'))
        return k, len(roots)

    def reset_roots(self, tag, depth):
        k, count = tag
        self.line(depth, 'ail_sarena_keep_roots(&%s, _fmark%d, _froots%d, %d);' % (self.sar, k, k, count))
