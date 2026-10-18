"""The runtime-call table of the text stage (S4a): every `rt @name` the lowering may emit besides the
two recursion-depth entries of effects.py.

An entry says what the call takes and yields (IR types), its effect record, and how it is written in
C. The C text is a `str.format` template over the operands `{0}`, `{1}`, ..., the function's arenas
`{A}` (str) and `{B}` (bytes), the attributes of the instruction (`{width}`, ...), the operand list
`{va}` and count `{n}` of a variadic entry, and, for the cursor forms, the three cursor cells
`{cp}`, `{cu}`, `{cl}`. The runtime pieces (`cruntime.ORDER` names) it needs are in `parts`.

Calls are the legacy runtime's own helpers with the legacy's own messages: the IR changes who calls
them, not what they say.
"""
from .effects import Effects, INDEX, VALUE
from . import ir as I

S, B, N, F, T1 = I.STRV, I.BYTES, I.I64, I.F64, I.I1
ARGV = 'Global(rt,argv)'
STDIN = 'Global(rt,stdin)'
STDOUT = 'Global(rt,stdout)'
ARENA = 'Arena(str)'
BARENA = 'Arena(bytes)'
OSERR = 'OSError'
DIE = 'Die'

ENTRIES = {}


def _entry(name, params, results, c, effects=None, parts=(), arena=None, pure=False, cursor=False,
           variadic=False, attrs=()):
    ENTRIES[name] = dict(params=tuple(params), results=tuple(results), c=c,
                         effects=effects if effects is not None else Effects(), parts=frozenset(parts),
                         arena=arena, pure=pure, cursor=cursor, variadic=variadic, attrs=tuple(attrs))


_PURE = Effects()
_ALLOC = Effects(allocs=[ARENA])
_BALLOC = Effects(allocs=[BARENA])

# --- the command line
_entry('argv_len', (), (N,), 'ail_argv_len()', Effects(reads=[ARGV]), parts=('ARGV',), pure=True)
_entry('argv_get', (N,), (S,), 'ail_argv_get({A}, {0})', Effects(reads=[ARGV], allocs=[ARENA], raises=[INDEX, DIE]),
       parts=('ARGV',), arena='s')

# --- reading text: length, index, slice (the cursor forms keep a position for a name that never changes)
_entry('str_len', (S,), (N,), 'ail_str_len_points({0})', _PURE, parts=('STR',), pure=True)
_entry('str_len_cur', (S,), (N,), 'ail__cur_len({0}, &{cl})', _PURE, parts=('STR',), pure=True, cursor=True)
_entry('str_index', (S, N), (S,), 'ail_str_index({0}, {1})', Effects(raises=[INDEX, DIE]), parts=('STR',))
_entry('str_index_cur', (S, N), (S,), 'ail_str_index_cur({0}, {1}, &{cp}, &{cu}, &{cl})',
       Effects(raises=[INDEX, DIE]), parts=('STR',), cursor=True)
_entry('str_slice', (S, N, N), (S,), 'ail_str_slice({0}, {1}, {2})', _PURE, parts=('STR',), pure=True)
_entry('str_slice_cur', (S, N, N), (S,), 'ail_str_slice_cur({0}, {1}, {2}, &{cp}, &{cu}, &{cl})', _PURE,
       parts=('STR',), pure=True, cursor=True)
_entry('str_point', (S,), (N,), 'ail_str_point({0}, 0)', Effects(raises=[DIE]), parts=('STR',))
_entry('str_strip', (S,), (S,), 'ail_str_strip({0})', _PURE, parts=('STR',), pure=True)
_entry('str_lstrip', (S,), (S,), 'ail_str_lstrip({0})', _PURE, parts=('STR',), pure=True)
_entry('str_rstrip', (S,), (S,), 'ail_str_rstrip({0})', _PURE, parts=('STR',), pure=True)
_entry('str_strip_chars', (S, S), (S,), 'ail_str_strip_chars({0}, {1})', _PURE, parts=('STR',), pure=True)
_entry('str_lstrip_chars', (S, S), (S,), 'ail_str_lstrip_chars({0}, {1})', _PURE, parts=('STR',), pure=True)
_entry('str_rstrip_chars', (S, S), (S,), 'ail_str_rstrip_chars({0}, {1})', _PURE, parts=('STR',), pure=True)

_entry('str_char_at', (S, N), (S,), 'ail_ir_char_at({0}, {1})', _PURE, parts=('STR', 'IRSTR'), pure=True)
_entry('str_bytes', (S,), (N,), '({0}).n', _PURE, parts=('STR',), pure=True)
for _p in ('isdigit', 'isalpha', 'isalnum', 'isspace', 'isupper', 'islower', 'isdecimal', 'isnumeric'):
    _entry('str_' + _p, (S,), (T1,), '(ail_str_%s({0}) != 0)' % _p, _PURE, parts=('STR', 'STRPRED'), pure=True)

# --- comparing
_entry('str_eq', (S, S), (T1,), '(ail_str_eq({0}, {1}) != 0)', _PURE, parts=('STR',), pure=True)
_entry('str_cmp', (S, S), (N,), 'ail_str_cmp({0}, {1})', _PURE, parts=('STR',), pure=True)
_entry('str_contains', (S, S), (T1,), '(ail_text_find_points({1}, {0}) >= 0)', _PURE, parts=('STR',), pure=True)
_entry('str_startswith', (S, S), (T1,), '(ail_str_startswith({0}, {1}) != 0)', _PURE, parts=('STR',), pure=True)
_entry('str_endswith', (S, S), (T1,), '(ail_str_endswith({0}, {1}) != 0)', _PURE, parts=('STR',), pure=True)

# --- building text (the result lives in the function's str arena)
_entry('str_cat', (S, S), (S,), 'ail_str_cat({A}, {0}, {1})', _ALLOC, parts=('STR',), arena='s')
# a copy of a view into the function's arena (an element read out of a struct's list[str] field that outlives the read)
_entry('str_own', (S,), (S,), 'ail_str_adopt({A}, ail_str_return_owned({0}))', Effects(allocs=[ARENA], raises=[DIE]),
       parts=('STR', 'STRRET'), arena='s')
_entry('str_catn', (S,), (S,), 'ail_str_catn({A}, (ail_str[]){{{va}}}, {n})', _ALLOC, parts=('STR',), arena='s',
       variadic=True)
_entry('str_repeat', (S, N), (S,), 'ail_str_repeat({A}, {0}, {1})', Effects(allocs=[ARENA], raises=[DIE]),
       parts=('STR', 'STRRET', 'STRREPEAT'), arena='s')
_entry('str_from_int', (N,), (S,), 'ail_str_from_int({A}, {0})', _ALLOC, parts=('STR',), arena='s')
# digits in a 24-byte buffer of the calling block: only for a piece consumed in the same block
_entry('str_from_int_buf', (N,), (S,), 'ail_str_from_int_buf((uint8_t[24]){{0}}, {0})', _PURE, parts=('STR',))
_entry('str_from_float', (F,), (S,), 'ail_str_from_float({A}, {0})', _ALLOC, parts=('STR', 'FREPR', 'FMT'), arena='s')
_entry('fmt_int', (N,), (S,), 'ail_fmt_spec_int({A}, {0}, {width}, {align}, {zero}, {fill})', _ALLOC,
       parts=('STR', 'FMT'), arena='s', attrs=('width', 'align', 'zero', 'fill'))
_entry('fmt_float', (F,), (S,), 'ail_fmt_spec_float({A}, {0}, {width}, {align}, {zero}, {prec}, {fill})', _ALLOC,
       parts=('STR', 'FREPR', 'FMT'), arena='s', attrs=('width', 'align', 'zero', 'prec', 'fill'))
_entry('fmt_str', (S,), (S,), 'ail_fmt_spec_str({A}, {0}, {width}, {align}, {prec})', _ALLOC,
       parts=('STR', 'FMT'), arena='s', attrs=('width', 'align', 'prec'))

# --- numbers from text
_entry('str_to_int', (S,), (N,), 'ail_str_to_int({0})', Effects(raises=[VALUE]), parts=('STR',))
_entry('bytes_to_int', (B,), (N,), 'ail_bytes_to_int({0})', Effects(raises=[VALUE]), parts=('BYTES',))
_entry('str_to_float', (S,), (F,), 'ail_str_to_float({0})', Effects(raises=[VALUE]), parts=('STR', 'FREPR'))

# --- text and bytes
_entry('str_encode', (S,), (B,), 'ail_str_encode_utf8({B}, {0})', Effects(allocs=[BARENA]), parts=('UTF8CODEC',),
       arena='b')
_entry('bytes_decode', (B,), (S,), 'ail_bytes_decode_utf8({A}, {0})', Effects(allocs=[ARENA], raises=[VALUE]),
       parts=('UTF8CODEC',), arena='s')
_entry('bytes_decode_view', (B,), (S,), 'ail_bytes_decode_utf8_view({0})', Effects(raises=[VALUE]),
       parts=('UTF8CODEC',))
# a str is UTF-8 already: its bytes as a view, for a consumer that is done with them at once
_entry('str_encode_view', (S,), (B,), '(ail_bytes){{(const unsigned char *)({0}).p, ({0}).n}}', _PURE,
       parts=('BYTES',), pure=True)
_entry('bytes_cat', (B, B), (B,), 'ail_bytes_cat({B}, {0}, {1})', _BALLOC, parts=('BYTES',), arena='b')
_entry('bytes_find_range', (B, B, N, N), (N,), 'ail_bytes_find_range({0}, {1}, {2}, {3})', _PURE, parts=('BYTES', 'BYTESRET'),
       pure=True)
_entry('bytes_rfind_range', (B, B, N, N), (N,), 'ail_bytes_rfind_range({0}, {1}, {2}, {3})', _PURE,
       parts=('BYTES', 'BYTESRET'), pure=True)
_entry('bytes_slice', (B, N, N), (B,), 'ail_bytes_slice({0}, {1}, {2})', _PURE, parts=('BYTES',), pure=True)

# --- the world
_entry('read_stdin_bytes', (N,), (B,), 'ail_stdin_read_bytes({B}, {0})',
       Effects(reads=[STDIN], writes=[STDIN, STDOUT], allocs=[BARENA], raises=[VALUE, OSERR], io=True),
       parts=('STDINBYTES',), arena='b')
_entry('write_stdout_bytes', (B,), (), 'ail_stdout_write_bytes({0})', Effects(io=True), parts=('STDOUTBYTES',))
_entry('stdin_read', (), (S,), 'ail_stdin_read({A})',
       Effects(reads=[STDIN], writes=[STDIN, STDOUT], allocs=[ARENA], io=True, raises=[DIE]), parts=('STR',), arena='s')
_entry('stdin_readline', (), (S,), 'ail_stdin_readline({A})',
       Effects(reads=[STDIN], writes=[STDIN, STDOUT], allocs=[ARENA], io=True, raises=[DIE]), parts=('STR',), arena='s')
_entry('input', (), (S,), 'ail_input({A})',
       Effects(reads=[STDIN], writes=[STDIN, STDOUT], allocs=[ARENA], io=True, raises=['EOFError', DIE]),
       parts=('STR',), arena='s')
_entry('read_bytes', (S,), (B,), 'ail_file_read_bytes({B}, {0})',
       Effects(allocs=[BARENA], raises=[OSERR, DIE], io=True), parts=('FILEBYTES',), arena='b')
_entry('exit', (N,), (), 'exit((int)({0}))', Effects(io=True))

# --- input windows (S4c-1, passes/window.py): the same reads, mapped where the input is a regular file, and the
# release of the pages behind a forward scan. `win` names the function's window cell.
WIN = 'Global(rt,win)'
_entry('read_stdin_win', (N,), (B,), 'ail_win_stdin(&{W}, {B}, {0})',
       Effects(reads=[STDIN], writes=[STDIN, STDOUT], allocs=[BARENA], raises=[VALUE, OSERR], io=True),
       parts=('IRWINSTDIN',), arena='b', attrs=('win',))
_entry('read_bytes_win', (S,), (B,), 'ail_win_file(&{W}, {B}, {0})',
       Effects(allocs=[BARENA], raises=[OSERR, DIE], io=True), parts=('IRWINFILE',), arena='b', attrs=('win',))
_entry('win_release', (N,), (), 'ail_win_release(&{W}, {0})', Effects(writes=[WIN]), parts=('IRWIN',), attrs=('win',))


# --- lists of str (S3c-1, design section 17): runtime calls that build a list. They are not `rt` calls: the list
# they return lives in a place, so the lowering emits `list.rt (destination, args...)`.
LIST_ENTRIES = {}
LIST_ENTRIES['str_split_ws'] = dict(params=(S,), c='ail_str_split_ws({0})', effects=Effects(raises=[DIE]),
                                    parts=frozenset(('STR', 'SLIST')))
LIST_ENTRIES['str_split_sep'] = dict(params=(S, S), c='ail_str_split_sep({0}, {1})',
                                     effects=Effects(raises=[VALUE, DIE]), parts=frozenset(('STR', 'SLIST')))
LIST_ENTRIES['str_splitlines'] = dict(params=(S,), c='ail_str_splitlines({0})', effects=Effects(raises=[DIE]),
                                      parts=frozenset(('STR', 'SLIST')))

from . import effects as _effects      # noqa: E402

for _name, _e in ENTRIES.items():
    _effects.RUNTIME[_name] = (_e['params'], _e['results'], _e['effects'])


def is_pure(callee):
    e = ENTRIES.get(callee)
    return bool(e and e['pure'])
