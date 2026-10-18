# -*- coding: utf-8 -*-
"""filert.py -- runtime parts of stage G7 (files and os).

`ailfile_core.h` is the shared C core. Here:

  FILECORE   the core text (embedded once per program, typed or general)
  FILEEXC    the OS-family exception codes of the typed runtime (spliced into DIE only when a
             program names them, so every other program keeps its C byte for byte)
  FILEIO     the typed adapters: one `ailt_<prim>` function per primitive of filelib.PRIMS, taking
             ail_str / ail_bytes / int64 and raising through the typed exception machinery
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import filelib

with open(os.path.join(HERE, 'ailfile_core.h'), 'r', encoding='utf-8') as _f:
    CORE = _f.read()

# ---------------------------------------------------------------------------------------------
# Typed runtime: exception codes 11..16 (FileNotFoundError, PermissionError, IsADirectoryError,
# FileExistsError, NotADirectoryError, io.UnsupportedOperation). They extend the code table the
# AssertionError / OverflowError edits (cruntime.py) already extend.

FILE_EXC_NAMES = ('FileNotFoundError', 'PermissionError', 'IsADirectoryError', 'FileExistsError',
                  'NotADirectoryError', 'UnsupportedOperation')
FILE_EXC_CODES = {name: 11 + i for i, name in enumerate(FILE_EXC_NAMES)}

EXC_EDITS = (
    ('AIL_EXC_OVERFLOW = 10 };',
     'AIL_EXC_OVERFLOW = 10, AIL_EXC_FNF = 11, AIL_EXC_PERM = 12, AIL_EXC_ISDIR = 13, AIL_EXC_EXIST = 14,\n'
     '       AIL_EXC_NOTDIR = 15, AIL_EXC_UNSUP = 16 };'),
    ('"AssertionError", "OverflowError"};',
     '"AssertionError", "OverflowError", "FileNotFoundError", "PermissionError", "IsADirectoryError",\n'
     '         "FileExistsError", "NotADirectoryError", "UnsupportedOperation"};'),
    ('return code >= 1 && code <= 10 ? names[code]', 'return code >= 1 && code <= 16 ? names[code]'),
    ('if (code < 1 || code > 10 || n < 0', 'if (code < 1 || code > 16 || n < 0'),
    ('if (code < 1 || code > 10) code = AIL_EXC_RUNTIME;', 'if (code < 1 || code > 16) code = AIL_EXC_RUNTIME;'),
)
# a program that opens files also flushes them before an uncaught exception ends it (CPython does,
# at interpreter shutdown); the hook is only spliced in when the core is present
FLUSH_EDITS = (
    ('static void ail_die(const char *w);\n', 'static void ail_die(const char *w);\nstatic void ailf_flush_all(void);\n'),
    ('    fflush(stdout); fputs(w, stderr); fputc(10, stderr); _Exit(1);\n',
     '    ailf_flush_all();\n    fflush(stdout); fputs(w, stderr); fputc(10, stderr); _Exit(1);\n'),
    ('static void ail_exception_uncaught(ail_exception *value) {\n    fflush(stdout);\n',
     'static void ail_exception_uncaught(ail_exception *value) {\n    ailf_flush_all();\n    fflush(stdout);\n'),
)


def file_exception(text, with_flush):
    """The DIE block with the OS-family codes (it must already carry the Assertion/Overflow edits)."""
    for old, new in EXC_EDITS:
        if text.count(old) != 1:
            raise AssertionError('DIE block changed; update filert.EXC_EDITS: ' + old)
        text = text.replace(old, new)
    if with_flush:
        for old, new in FLUSH_EDITS:
            if text.count(old) != 1:
                raise AssertionError('DIE block changed; update filert.FLUSH_EDITS: ' + old)
            text = text.replace(old, new)
    return text


# ---------------------------------------------------------------------------------------------
# The typed adapters. Every function is `static` and sits after the STR / BYTES blocks.

TYPED = r'''
/* ---- G7 typed adapters: the primitives of filelib.PRIMS over ailfile_core.h ---- */
static int ailt_ascii(const char *s) { for (; *s; s++) if ((unsigned char)*s >= 0x80) return 0; return 1; }
static void ailt_fraise(void) {
    int code = AIL_EXC_RUNTIME;
    switch (ailf_e.kind) {
    case AILF_E_OS:
        switch (ailf_e.err) {
        case ENOENT: code = AIL_EXC_FNF; break;
        case EACCES: case EPERM: code = AIL_EXC_PERM; break;
        case EISDIR: code = AIL_EXC_ISDIR; break;
        case EEXIST: code = AIL_EXC_EXIST; break;
        case ENOTDIR: code = AIL_EXC_NOTDIR; break;
        default: code = AIL_EXC_OS; break;
        }
        break;
    case AILF_E_VALUE: case AILF_E_UENCODE: code = AIL_EXC_VALUE; break;
    case AILF_E_UNSUP: code = AIL_EXC_UNSUP; break;
    case AILF_E_UDECODE: code = AIL_EXC_UNICODE_DECODE; break;
    case AILF_E_KEY: code = AIL_EXC_KEY; break;
    default: ail_die(ailf_e.msg);
    }
    ail_raise_value_adopt(ail_exception_new(code, (const uint8_t *)ailf_e.msg, (int64_t)strlen(ailf_e.msg),
                                            (_Bool)ailt_ascii(ailf_e.msg)));
}
#define AILT_CHECK(call) do { if ((call) < 0) ailt_fraise(); } while (0)
static ail_str ailt_adopt_str(ail_sarena *A, ailf_buf *b) {
    if (b->n == 0) { free(b->p); return (ail_str){(const uint8_t *)"", 0, 1}; }
    b->p[b->n] = 0;
    int64_t k = 0;
    while (k < b->n && b->p[k] < 0x80) k++;
    ail_sarena_pushn(A, b->p, ail_bytes_elems(b->cap));
    ail_str r; r.p = b->p; r.n = b->n; r.bytes = (k == b->n);
    return r;
}
static ail_bytes ailt_adopt_bytes(ail_barena *A, ailf_buf *b) {
    if (b->n == 0) { free(b->p); return (ail_bytes){NULL, 0}; }
    ail_barena_push(A, b->p);
    return (ail_bytes){b->p, b->n};
}
static int64_t ailt_f_open(ail_str path, ail_str mode, int64_t buffering, ail_str enc, int64_t hasenc,
                           ail_str err, int64_t haserr, ail_str nl, int64_t hasnl) {
    int64_t h = ailf_open(path.p, path.n, mode.p, mode.n, buffering, enc.p, enc.n, (int)hasenc,
                          err.p, err.n, (int)haserr, nl.p, nl.n, (int)hasnl);
    if (h < 0) ailt_fraise();
    return h;
}
static int64_t ailt_f_close(int64_t h) { AILT_CHECK(ailf_close(h)); return 0; }
static int64_t ailt_f_flush(int64_t h) { AILT_CHECK(ailf_flush(h)); return 0; }
static ail_str ailt_f_tread(ail_sarena *A, int64_t h, int64_t n) {
    ailf_buf b; AILT_CHECK(ailf_tread(h, n, &b)); return ailt_adopt_str(A, &b);
}
static ail_str ailt_f_treadline(ail_sarena *A, int64_t h, int64_t n) {
    ailf_buf b; AILT_CHECK(ailf_treadline(h, n, &b)); return ailt_adopt_str(A, &b);
}
static ail_str ailt_f_tnext(ail_sarena *A, int64_t h) {
    ailf_buf b; AILT_CHECK(ailf_tnext(h, &b)); return ailt_adopt_str(A, &b);
}
static int64_t ailt_f_twrite(int64_t h, ail_str s) {
    int64_t r = ailf_twrite(h, s.p, s.n); if (r < 0) ailt_fraise(); return r;
}
static ail_bytes ailt_f_bread(ail_barena *A, int64_t h, int64_t n) {
    ailf_buf b; AILT_CHECK(ailf_bread(h, n, &b)); return ailt_adopt_bytes(A, &b);
}
static ail_bytes ailt_f_breadline(ail_barena *A, int64_t h, int64_t n) {
    ailf_buf b; AILT_CHECK(ailf_breadline(h, n, &b)); return ailt_adopt_bytes(A, &b);
}
static ail_bytes ailt_f_bnext(ail_barena *A, int64_t h) {
    ailf_buf b; AILT_CHECK(ailf_bnext(h, &b)); return ailt_adopt_bytes(A, &b);
}
static int64_t ailt_f_bwrite(int64_t h, ail_bytes d) {
    int64_t r = ailf_bwrite(h, d.p, d.n); if (r < 0) ailt_fraise(); return r;
}
static int64_t ailt_f_seek(int64_t h, int64_t off, int64_t whence) {
    ailf *f = ailf_get(h);
    int64_t r = (f && f->text) ? ailf_tseek(h, off, whence) : ailf_bseek(h, off, whence);
    if (r < 0) ailt_fraise(); return r;
}
static int64_t ailt_f_tell(int64_t h) {
    ailf *f = ailf_get(h);
    int64_t r = (f && f->text) ? ailf_ttell(h) : ailf_btell(h);
    if (r < 0) ailt_fraise(); return r;
}
static int64_t ailt_f_readable(int64_t h) { int64_t r = ailf_readable(h); if (r < 0) ailt_fraise(); return r; }
static int64_t ailt_f_writable(int64_t h) { int64_t r = ailf_writable(h); if (r < 0) ailt_fraise(); return r; }
static int64_t ailt_f_seekable(int64_t h) { int64_t r = ailf_seekable(h); if (r < 0) ailt_fraise(); return r; }
static ail_str ailt_os_getcwd(ail_sarena *A) { ailf_buf b; AILT_CHECK(ailf_getcwd(&b)); return ailt_adopt_str(A, &b); }
static int64_t ailt_os_chdir(ail_str p) { AILT_CHECK(ailf_chdir(p.p, p.n)); return 0; }
static ail_str ailt_os_scandir(ail_sarena *A, ail_str p, int64_t typed) {
    ailf_buf b; AILT_CHECK(ailf_scandir(p.p, p.n, &b, (int)typed)); return ailt_adopt_str(A, &b);
}
static int64_t ailt_os_kind(ail_str p, int64_t follow) { return ailf_stat_kind(p.p, p.n, (int)follow); }
static int64_t ailt_os_getsize(ail_str p) { int64_t r = ailf_getsize(p.p, p.n); if (r < 0) ailt_fraise(); return r; }
static int64_t ailt_os_mkdir(ail_str p, int64_t mode) { AILT_CHECK(ailf_mkdir(p.p, p.n, mode)); return 0; }
static int64_t ailt_os_rmdir(ail_str p) { AILT_CHECK(ailf_rmdir(p.p, p.n)); return 0; }
static int64_t ailt_os_unlink(ail_str p) { AILT_CHECK(ailf_unlink(p.p, p.n)); return 0; }
static int64_t ailt_os_chmod(ail_str p, int64_t mode) { AILT_CHECK(ailf_chmod(p.p, p.n, mode)); return 0; }
static int64_t ailt_os_rename(ail_str a, ail_str b) { AILT_CHECK(ailf_rename(a.p, a.n, b.p, b.n, 0)); return 0; }
static int64_t ailt_os_replace(ail_str a, ail_str b) { AILT_CHECK(ailf_rename(a.p, a.n, b.p, b.n, 1)); return 0; }
static ail_str ailt_os_getenv(ail_sarena *A, ail_str k) {
    ailf_buf b; int r = ailf_getenv(k.p, k.n, &b);
    if (r < 0) ailt_fraise();
    if (!r) { ailf_buf_free(&b); return (ail_str){(const uint8_t *)"", 0, 1}; }
    return ailt_adopt_str(A, &b);
}
static int64_t ailt_os_hasenv(ail_str k) {
    ailf_buf b; int r = ailf_getenv(k.p, k.n, &b);
    if (r < 0) ailt_fraise();
    ailf_buf_free(&b);
    return r;
}
static int64_t ailt_os_setenv(ail_str k, ail_str v) { AILT_CHECK(ailf_setenv(k.p, k.n, v.p, v.n)); return 0; }
static int64_t ailt_os_unsetenv(ail_str k) { AILT_CHECK(ailf_unsetenv(k.p, k.n)); return 0; }
'''

# which primitives of the table take an arena first, by result kind
ARENA_FIRST = {'str': 'ail_sarena', 'bytes': 'ail_barena'}

for _name in filelib.PRIMS:
    assert ('ailt_' + filelib.c_name(_name) + '(') in TYPED, _name


def register(ORDER, SOURCE, REQUIRES):
    """Add the file parts to cruntime's tables (called once at the end of cruntime.py)."""
    for name, text, requires in (
            ('FILECORE', CORE, ['MONOTONICHEAD', 'TYPES', 'DIE']),
            ('FILEIO', TYPED, ['FILECORE', 'FILEEXC', 'STR', 'BYTES', 'DIE'])):
        ORDER.append(name)
        SOURCE[name] = text
        REQUIRES[name] = requires


# ---------------------------------------------------------------------------------------------
# The general runtime (pyboxed2.py): values are ail_obj, errors are ail_st edges. Strings there are
# 16-bit code units, so file text with a character above U+FFFF stops with a named message, as
# stdin already does. The general runtime has no bytes values: the binary primitives are refused at
# compile time (pyboxed2._call_fileprim).

GENERAL_HEAD = r'''
/* ---- G7 general-path adapters: the primitives of filelib.PRIMS over ailfile_core.h ---- */
static ail_st ailo_raise_os(ail_ctx *cx, int error, const char *message, const char *filename, const char *filename2) {
    AIL_FRAME_ENTER(cx, fr, 6);
    ail_obj *v = fr.slots;
    const char *reason = error ? strerror(error) : "Error";
    v[0] = ail_str_from_cstr(cx, reason);
    v[1] = ail_bi_str_from_utf8(cx, message, (int64_t)strlen(message));
    ail_st st = ail_raise(cx, cx->builtin_cls[ail_bi_oserror_id(error)], v[1]);
    v[2] = ail_exc_as_value(cx);
    ail_obj args[3] = {ail_box_int(error), v[0], ail_box_none()};
    int nargs = 2;
    if (filename) { v[4] = ail_bi_str_from_utf8(cx, filename, (int64_t)strlen(filename)); args[2] = v[4]; nargs = 3; }
    v[3] = ail_tuple_new(cx, args, nargs);
    ail_inst_setattr(cx, v[2], ail_intern(cx, "errno"), ail_box_int(error));
    ail_inst_setattr(cx, v[2], ail_intern(cx, "strerror"), v[0]);
    ail_inst_setattr(cx, v[2], ail_intern(cx, "filename"), filename ? v[4] : ail_box_none());
    if (filename2) { v[5] = ail_bi_str_from_utf8(cx, filename2, (int64_t)strlen(filename2)); ail_inst_setattr(cx, v[2], ail_intern(cx, "filename2"), v[5]); }
    ail_inst_setattr(cx, v[2], ail_intern(cx, "args"), v[3]);
    AIL_FRAME_LEAVE(cx, fr);
    return st;
}
static ail_st ailo_fail(ail_ctx *cx) {
    switch (ailf_e.kind) {
    case AILF_E_OS:
        return ailo_raise_os(cx, ailf_e.err, ailf_e.msg, ailf_e.has_fn1 ? ailf_e.fn1 : NULL, ailf_e.has_fn2 ? ailf_e.fn2 : NULL);
    case AILF_E_VALUE: case AILF_E_UENCODE: case AILF_E_UDECODE:
        return ail_raise_c(cx, AIL_B_VALUEERROR, ailf_e.msg);
    case AILF_E_UNSUP:
        return ail_raise_c(cx, AIL_B_OSERROR, ailf_e.msg);
    case AILF_E_KEY:
        return ail_raise_c(cx, AIL_B_KEYERROR, ailf_e.msg);
    default:
        ail_die(ailf_e.msg);
    }
    return AIL_EXC;
}
static ail_st ailo_utf8_arg(ail_ctx *cx, ail_obj s, ailf_buf *b) {
    if (s.tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "expected str");
    ail_str v = ail_view_to_str(s);
    for (int64_t i = 0; i < v.n; i++) {
        uint32_t c = ail_chr(v, i);
        if (c >= 0xD800 && c < 0xDC00 && i + 1 < v.n) {
            uint32_t d = ail_chr(v, i + 1);
            if (d >= 0xDC00 && d < 0xE000) { c = 0x10000 + ((c - 0xD800) << 10) + (d - 0xDC00); i++; }
        }
        if (ailf_buf_putcp(b, c)) ail_die("out of memory");
    }
    return AIL_OK;
}
static ail_st ailo_int_arg(ail_ctx *cx, ail_obj v, int64_t *out) {
    if (v.tag == AIL_T_INT || v.tag == AIL_T_BOOL) { *out = v.i; return AIL_OK; }
    return ail_raise_c(cx, AIL_B_TYPEERROR, "expected int");
}
'''

# prim (c name) -> (result form, C expression); {sN} is the UTF-8 pointer and length of string
# argument N, {iN} an int argument, `b` the result buffer.
#   val    the expression is the result and is negative on error
#   status the expression is nonzero on error; the result is 0
#   buf    the expression fills `b` and is negative on error; the result is its text
#   plain  the expression is the result
GENERAL_SPEC = {
    'f_open': ('val', 'ailf_open({s0}, {s1}, {i2}, {s3}, (int){i4}, {s5}, (int){i6}, {s7}, (int){i8})'),
    'f_close': ('status', 'ailf_close({i0})'),
    'f_flush': ('status', 'ailf_flush({i0})'),
    'f_tread': ('buf', 'ailf_tread({i0}, {i1}, &b)'),
    'f_treadline': ('buf', 'ailf_treadline({i0}, {i1}, &b)'),
    'f_tnext': ('buf', 'ailf_tnext({i0}, &b)'),
    'f_twrite': ('val', 'ailf_twrite({i0}, {s1})'),
    'f_seek': ('val', '(ailf_get({i0}) && ailf_get({i0})->text ? ailf_tseek({i0}, {i1}, {i2}) : ailf_bseek({i0}, {i1}, {i2}))'),
    'f_tell': ('val', '(ailf_get({i0}) && ailf_get({i0})->text ? ailf_ttell({i0}) : ailf_btell({i0}))'),
    'f_readable': ('val', 'ailf_readable({i0})'),
    'f_writable': ('val', 'ailf_writable({i0})'),
    'f_seekable': ('val', 'ailf_seekable({i0})'),
    'os_getcwd': ('buf', 'ailf_getcwd(&b)'),
    'os_chdir': ('status', 'ailf_chdir({s0})'),
    'os_scandir': ('buf', 'ailf_scandir({s0}, &b, (int){i1})'),
    'os_kind': ('plain', 'ailf_stat_kind({s0}, (int){i1})'),
    'os_getsize': ('val', 'ailf_getsize({s0})'),
    'os_mkdir': ('status', 'ailf_mkdir({s0}, {i1})'),
    'os_rmdir': ('status', 'ailf_rmdir({s0})'),
    'os_unlink': ('status', 'ailf_unlink({s0})'),
    'os_chmod': ('status', 'ailf_chmod({s0}, {i1})'),
    'os_rename': ('status', 'ailf_rename({s0}, {s1}, 0)'),
    'os_replace': ('status', 'ailf_rename({s0}, {s1}, 1)'),
    'os_setenv': ('status', 'ailf_setenv({s0}, {s1})'),
    'os_unsetenv': ('status', 'ailf_unsetenv({s0})'),
    'os_getenv': ('env', 'ailf_getenv({s0}, &b)'),
    'os_hasenv': ('has', 'ailf_getenv({s0}, &b)'),
}


def general_wrappers():
    out = []
    for prim, (ret, kinds) in filelib.PRIMS.items():
        cname = filelib.c_name(prim)
        if 'bytes' in kinds or ret == 'bytes':
            continue
        form, expr = GENERAL_SPEC[cname]
        params = ''.join(', ail_obj a%d' % i for i in range(len(kinds)))
        lines = ['static ail_st ailo_%s(ail_ctx *cx, ail_obj *out%s) {' % (cname, params), '    ail_st st = AIL_OK;',
                 '    ailf_buf b = {0};']
        for i, kind in enumerate(kinds):
            lines.append('    ailf_buf s%d = {0}; int64_t i%d = 0; (void)i%d;' % (i, i, i) if kind == 'str'
                         else '    int64_t i%d = 0;' % i)
        for i, kind in enumerate(kinds):
            fn = 'ailo_utf8_arg(cx, a%d, &s%d)' % (i, i) if kind == 'str' else 'ailo_int_arg(cx, a%d, &i%d)' % (i, i)
            lines.append('    st = %s; if (st != AIL_OK) goto done;' % fn)
        expr = expr
        for i, kind in enumerate(kinds):
            expr = expr.replace('{s%d}' % i, '(s%d.p ? s%d.p : (const uint8_t *)""), s%d.n' % (i, i, i)).replace('{i%d}' % i, 'i%d' % i)
        lines.append('    {')
        if form == 'val':
            lines.append('        int64_t r = %s;' % expr)
            lines.append('        if (r < 0) { st = ailo_fail(cx); goto done; }')
            lines.append('        *out = ail_box_int(r);')
        elif form == 'status':
            lines.append('        if (%s) { st = ailo_fail(cx); goto done; }' % expr)
            lines.append('        *out = ail_box_int(0);')
        elif form == 'plain':
            lines.append('        *out = ail_box_int(%s);' % expr)
        elif form == 'buf':
            lines.append('        if ((%s) < 0) { st = ailo_fail(cx); goto done; }' % expr)
            lines.append('        *out = ail_bi_str_from_utf8(cx, (const char *)(b.p ? b.p : (uint8_t *)""), b.n);')
        elif form == 'env':
            lines.append('        int r = %s;' % expr)
            lines.append('        if (r < 0) { st = ailo_fail(cx); goto done; }')
            lines.append('        *out = ail_bi_str_from_utf8(cx, (const char *)(r && b.p ? b.p : (uint8_t *)""), r ? b.n : 0);')
        elif form == 'has':
            lines.append('        int r = %s;' % expr)
            lines.append('        if (r < 0) { st = ailo_fail(cx); goto done; }')
            lines.append('        *out = ail_box_int(r);')
        lines.append('    }')
        lines.append('done:')
        lines.append('    free(b.p);')
        for i, kind in enumerate(kinds):
            if kind == 'str':
                lines.append('    free(s%d.p);' % i)
        lines.append('    return st;')
        lines.append('}')
        out.append('\n'.join(lines))
    return '\n'.join(out) + '\n'


GENERAL = GENERAL_HEAD + general_wrappers()


def general_text():
    """The C the general runtime needs once a program reaches a file primitive."""
    return '\n/* ---- G7: shared file core ---- */\n' + CORE + GENERAL
