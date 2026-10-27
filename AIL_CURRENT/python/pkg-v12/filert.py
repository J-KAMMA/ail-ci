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
with open(os.path.join(HERE, 'ailproc_core.h'), 'r', encoding='utf-8') as _f:      # stage G8
    PROCCORE = _f.read()
with open(os.path.join(HERE, 'ailpath_core.h'), 'r', encoding='utf-8') as _f:      # stage G10
    PATHCORE = _f.read()
with open(os.path.join(HERE, 'ailurl_core.h'), 'r', encoding='utf-8') as _f:       # stage G12
    URLCORE = _f.read()
with open(os.path.join(HERE, 'ailhttp_core.h'), 'r', encoding='utf-8') as _f:      # stage G12
    HTTPCORE = _f.read()
with open(os.path.join(HERE, 'ailsql_core.h'), 'r', encoding='utf-8') as _f:       # stage G11
    SQLCORE = _f.read()
with open(os.path.join(HERE, 'ailhash_core.h'), 'r', encoding='utf-8') as _f:      # crypto: hashlib, hmac, secrets, base64
    HASHCORE = _f.read()

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
     '       AIL_EXC_NOTDIR = 15, AIL_EXC_UNSUP = 16 };\n#define AIL_FILE_EXC_CODES 1'),
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
    ('    fflush(stdout); fputs(w, stderr); AIL_DBG_UNCAUGHT(); fputc(10, stderr); _Exit(1);\n',
     '    ailf_flush_all();\n    fflush(stdout); fputs(w, stderr); AIL_DBG_UNCAUGHT(); fputc(10, stderr); _Exit(1);\n'),
    ('static void ail_exception_uncaught(ail_exception *value) {\n    fflush(stdout);\n',
     'static void ail_exception_uncaught(ail_exception *value) {\n    ailf_flush_all();\n    fflush(stdout);\n'),
)


# Stage G8: CalledProcessError (17) and TimeoutExpired (18) extend the same table; spliced in after the
# file edits, and only into a program that names them.
PROC_EXC_EDITS = (
    ('AIL_EXC_UNSUP = 16 };', 'AIL_EXC_UNSUP = 16, AIL_EXC_CPE = 17, AIL_EXC_TIMEDOUT = 18 };'),
    ('"FileExistsError", "NotADirectoryError", "UnsupportedOperation"};',
     '"FileExistsError", "NotADirectoryError", "UnsupportedOperation", "CalledProcessError", "TimeoutExpired"};'),
    ('return code >= 1 && code <= 16 ? names[code]', 'return code >= 1 && code <= 18 ? names[code]'),
    ('if (code < 1 || code > 16 || n < 0', 'if (code < 1 || code > 18 || n < 0'),
    ('if (code < 1 || code > 16) code = AIL_EXC_RUNTIME;', 'if (code < 1 || code > 18) code = AIL_EXC_RUNTIME;'),
)


# Stage G12: URLError (30) and HTTPError (31). Codes 19..27 are sqlite3's, 28 is Exception and the user classes
# (userexc.py) start at 29, so a program that uses urllib reserves 29 (spare), 30 and 31 and its classes start at 32.
# Spliced in last, after the file, process and sqlite3 edits, whatever of them the table carries: the names array
# is read, padded with empty names up to code 29 and given the two names; the three limits move to 31.
HTTP_CODES = (30, 31)
HTTP_NAMES = ('URLError', 'HTTPError')


def http_exception(text):
    """The DIE block (already carrying the file, process and sqlite3 edits) with URLError and HTTPError."""
    import re
    text = text.replace('AIL_EXC_TIMEDOUT = 18 };', 'AIL_EXC_TIMEDOUT = 18, AIL_EXC_URLERR = 30, AIL_EXC_HTTPERR = 31 };')
    pattern = re.compile(r'(static const char \*ail_exception_name\(int code\) \{\n\s*static const char \*names\[\] =\s*\{)(.*?)(\};)', re.S)
    found = pattern.search(text)
    if not found:
        raise AssertionError('DIE block changed; update filert.http_exception (names)')
    names = re.findall(r'"([^"]*)"', found.group(2))
    names += [''] * (30 - len(names)) + list(HTTP_NAMES)
    text = text[:found.start()] + found.group(1) + ', '.join('"%s"' % n for n in names) + found.group(3) + text[found.end():]
    for old, new in ((r'return code >= 1 && code <= \d+ \? names\[code\]', 'return code >= 1 && code <= 31 ? names[code]'),
                     (r'code > \d+ \|\| n < 0', 'code > 31 || n < 0'),
                     (r'if \(code < 1 \|\| code > \d+\) code = AIL_EXC_RUNTIME;', 'if (code < 1 || code > 31) code = AIL_EXC_RUNTIME;')):
        text, count = re.subn(old, new, text)
        if count != 1:
            raise AssertionError('DIE block changed; update filert.http_exception: ' + old)
    return text


# Stage G11: the sqlite3 exception classes, codes 19..27 (pyfunc.EXC_NAMES), on top of whatever the table
# already holds (the file edits, and the subprocess ones when the program has them).
SQL_EXC_NAMES = ('sqlite3.Error', 'sqlite3.DatabaseError', 'sqlite3.OperationalError', 'sqlite3.IntegrityError',
                 'sqlite3.ProgrammingError', 'sqlite3.InterfaceError', 'sqlite3.DataError', 'sqlite3.InternalError',
                 'sqlite3.NotSupportedError')


def sql_exception(text):
    """The DIE block (already carrying the file edits, and the subprocess ones if present) with codes 19..27."""
    if 'AIL_EXC_TIMEDOUT = 18 };' in text:
        last, tail, pad = 18, '"CalledProcessError", "TimeoutExpired"};', ''
    else:
        last, tail, pad = 16, '"UnsupportedOperation"};', ', "RuntimeError", "RuntimeError"'
    names = ', '.join('"%s"' % n for n in SQL_EXC_NAMES)
    edits = (
        ('return code >= 1 && code <= %d ? names[code]' % last, 'return code >= 1 && code <= 27 ? names[code]'),
        ('if (code < 1 || code > %d || n < 0' % last, 'if (code < 1 || code > 27 || n < 0'),
        ('if (code < 1 || code > %d) code = AIL_EXC_RUNTIME;' % last, 'if (code < 1 || code > 27) code = AIL_EXC_RUNTIME;'),
        (tail, tail[:-2] + pad + ',\n         ' + names + '};'),
    )
    for old, new in edits:
        if text.count(old) != 1:
            raise AssertionError('DIE block changed; update filert.sql_exception: ' + old)
        text = text.replace(old, new)
    return text


def proc_exception(text):
    """The DIE block (already carrying the file edits) with the two subprocess exception codes."""
    for old, new in PROC_EXC_EDITS:
        if text.count(old) != 1:
            raise AssertionError('DIE block changed; update filert.PROC_EXC_EDITS: ' + old)
        text = text.replace(old, new)
    return text


# C23: the older whole-file builtins (open(path).read(), read_bytes, file_size, list_dir, the binary file
# handle) used to raise the plain OSError for every failure, which `except FileNotFoundError` had to take
# so that a missing file was still caught.  With the OS-family codes present they now raise the class of
# their errno, exactly like the file layer (ailt_fraise); spliced into those parts only with FILEEXC.
_FAIL_HELPER = """/* C23: the exception class of an errno, as the file layer's ailt_fraise picks it. */
static void ail_file_fail(int err) {
    switch (err) {
    case ENOENT: ail_raise_named(AIL_EXC_FNF);
    case EACCES: case EPERM: ail_raise_named(AIL_EXC_PERM);
    case EISDIR: ail_raise_named(AIL_EXC_ISDIR);
    case EEXIST: ail_raise_named(AIL_EXC_EXIST);
    case ENOTDIR: ail_raise_named(AIL_EXC_NOTDIR);
    default: break;
    }
    ail_raise_named(AIL_EXC_OS);
}
"""
LEGACY_EDITS = {
    'STR': (
        ('/* mode: 0 read, 1 replace, 2 append; binary on every platform. */\n',
         _FAIL_HELPER + '/* mode: 0 read, 1 replace, 2 append; binary on every platform. */\n', 1),
        ('    free(name);\n    if (!f) ail_raise_named(AIL_EXC_OS);\n',
         '    int open_errno = errno;\n    free(name);\n    if (!f) ail_file_fail(open_errno);\n', 1),
        ('if (ferror(it->file)) ail_raise_named(AIL_EXC_OS);', 'if (ferror(it->file)) ail_file_fail(errno);', 1),
        ('if (next == EOF && ferror(it->file)) ail_raise_named(AIL_EXC_OS);',
         'if (next == EOF && ferror(it->file)) ail_file_fail(errno);', 1),
        ('if (ferror(f)) { fclose(f); free(buf); ail_raise_named(AIL_EXC_OS); }',
         'if (ferror(f)) { int read_errno = errno; fclose(f); free(buf); ail_file_fail(read_errno); }', 1),
    ),
    'FILESIZE': (
        ('    int ok = stat(name, &info) == 0;\n    free(name);\n    if (!ok || !S_ISREG(info.st_mode)) ail_raise_named(AIL_EXC_OS);\n',
         '    int ok = stat(name, &info) == 0;\n    int stat_errno = ok ? 0 : errno;\n    free(name);\n'
         '    if (!ok) ail_file_fail(stat_errno);\n'
         '    if (!S_ISREG(info.st_mode)) ail_file_fail(S_ISDIR(info.st_mode) ? EISDIR : 0);\n', 1),
    ),
    'BINARYFILE': (
        ('    free(name);\n    if (!F->fp) { free(F); ail_raise_named(AIL_EXC_OS); }\n',
         '    int open_errno = errno;\n    free(name);\n    if (!F->fp) { free(F); ail_file_fail(open_errno); }\n', 1),
        ('    int valid = _fstat64(_fileno(F->fp), &info) == 0 && (info.st_mode & _S_IFMT) != _S_IFDIR;\n',
         '    int is_dir = 0;\n'
         '    int valid = _fstat64(_fileno(F->fp), &info) == 0 && !(is_dir = (info.st_mode & _S_IFMT) == _S_IFDIR);\n', 1),
        ('    int valid = fstat(fileno(F->fp), &info) == 0 && !S_ISDIR(info.st_mode);\n',
         '    int is_dir = 0;\n    int valid = fstat(fileno(F->fp), &info) == 0 && !(is_dir = S_ISDIR(info.st_mode));\n', 1),
        ('    if (!valid) { fclose(F->fp); free(F); ail_raise_named(AIL_EXC_OS); }\n',
         '    if (!valid) { fclose(F->fp); free(F); ail_file_fail(is_dir ? EISDIR : 0); }\n', 1),
    ),
    'DIRPATH': (
        ('    if (!ail_is_dir(path)) ail_raise_named(AIL_EXC_OS);\n',
         '    if (!ail_is_dir(path)) ail_file_fail(ail_path_exists(path) ? ENOTDIR : ENOENT);\n', 1),
    ),
}


def legacy_errno(part, text):
    for old, new, count in LEGACY_EDITS.get(part, ()):
        if text.count(old) != count:
            raise AssertionError('%s block changed; update filert.LEGACY_EDITS: %s' % (part, old))
        text = text.replace(old, new)
    return text


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

TYPED_PROC = r'''
/* ---- G8 typed adapters: the process primitives of proclib.PROCS over ailproc_core.h ---- */
static int64_t ailt_sp_begin(void) { ailp_begin(); return 0; }
static int64_t ailt_sp_arg(ail_str s) { AILT_CHECK(ailp_add_arg(s.p, s.n)); return 0; }
static int64_t ailt_sp_cwd(ail_str s) { AILT_CHECK(ailp_set_cwd(s.p, s.n)); return 0; }
static int64_t ailt_sp_envbegin(void) { ailp_env_begin(); return 0; }
static int64_t ailt_sp_env(ail_str k, ail_str v) { AILT_CHECK(ailp_env_add(k.p, k.n, v.p, v.n)); return 0; }
static int64_t ailt_sp_inputt(ail_str s, int64_t enc, int64_t errh) { AILT_CHECK(ailp_input_text(s.p, s.n, enc, errh)); return 0; }
static int64_t ailt_sp_inputb(ail_bytes d) { AILT_CHECK(ailp_input_bytes(d.p, d.n)); return 0; }
static int64_t ailt_sp_run(int64_t flags, int64_t us) { int64_t r = ailp_run(flags, us); if (r < 0) ailt_fraise(); return r; }
static int64_t ailt_sp_rc(int64_t h) { return ailp_rc(h); }
static int64_t ailt_sp_timedout(int64_t h) { return ailp_timedout(h); }
static ail_str ailt_sp_outt(ail_sarena *A, int64_t h, int64_t which, int64_t enc, int64_t errh) {
    ailf_buf b; AILT_CHECK(ailp_out_text(h, which, enc, errh, &b)); return ailt_adopt_str(A, &b);
}
static ail_bytes ailt_sp_outb(ail_barena *A, int64_t h, int64_t which) {
    ailf_buf b; AILT_CHECK(ailp_out_bytes(h, which, &b)); return ailt_adopt_bytes(A, &b);
}
static int64_t ailt_sp_free(int64_t h) { return ailp_free(h); }
static int64_t ailt_sp_errfrom(int64_t h, ail_str t) { return ailp_err_from(h, t.p, t.n); }
static int64_t ailt_sp_errbegin(int64_t kind, int64_t rc, ail_str t) { return ailp_err_begin(kind, rc, t.p, t.n); }
static int64_t ailt_sp_errarg(ail_str s) { AILT_CHECK(ailp_err_arg(s.p, s.n)); return 0; }
static int64_t ailt_sp_errout_t(ail_str s) { AILT_CHECK(ailp_err_out(s.p, s.n)); return 0; }
static int64_t ailt_sp_errout_b(ail_bytes d) { AILT_CHECK(ailp_err_out(d.p, d.n)); return 0; }
static int64_t ailt_sp_errerr_t(ail_str s) { AILT_CHECK(ailp_err_err(s.p, s.n)); return 0; }
static int64_t ailt_sp_errerr_b(ail_bytes d) { AILT_CHECK(ailp_err_err(d.p, d.n)); return 0; }
static int64_t ailt_sp_errrc(void) { return ailp_get_rc(); }
static ail_str ailt_sp_errcmd(ail_sarena *A) { ailf_buf b; AILT_CHECK(ailp_get_cmd(&b)); return ailt_adopt_str(A, &b); }
static ail_str ailt_sp_erro_t(ail_sarena *A) { ailf_buf b; AILT_CHECK(ailp_get_buf(&b, &ailp_last.out)); return ailt_adopt_str(A, &b); }
static ail_bytes ailt_sp_erro_b(ail_barena *A) { ailf_buf b; AILT_CHECK(ailp_get_buf(&b, &ailp_last.out)); return ailt_adopt_bytes(A, &b); }
static ail_str ailt_sp_erre_t(ail_sarena *A) { ailf_buf b; AILT_CHECK(ailp_get_buf(&b, &ailp_last.err)); return ailt_adopt_str(A, &b); }
static ail_bytes ailt_sp_erre_b(ail_barena *A) { ailf_buf b; AILT_CHECK(ailp_get_buf(&b, &ailp_last.err)); return ailt_adopt_bytes(A, &b); }
static ail_str ailt_sp_errtimeout(ail_sarena *A) { ailf_buf b; AILT_CHECK(ailp_get_timeout(&b)); return ailt_adopt_str(A, &b); }
static ail_str ailt_sp_errmsg(ail_sarena *A) { ailf_buf b; AILT_CHECK(ailp_err_msg(&b)); return ailt_adopt_str(A, &b); }
static ail_str ailt_sp_repr(ail_sarena *A, ail_str s) { ailf_buf b; AILT_CHECK(ailp_repr(s.p, s.n, &b)); return ailt_adopt_str(A, &b); }
static ail_str ailt_sp_reprb(ail_sarena *A, ail_bytes d) { ailf_buf b; AILT_CHECK(ailp_repr_bytes(d.p, d.n, &b)); return ailt_adopt_str(A, &b); }
'''

TYPED_PATH = r'''
/* ---- G10 typed adapters: the pathlib primitives of filelib.PATHS over ailpath_core.h ---- */
static int64_t ailt_pp_staterr(ail_str p) { return ailf_stat_errno(p.p, p.n); }
static ail_str ailt_pp_readlink(ail_sarena *A, ail_str p) { ailf_buf b; AILT_CHECK(ailf_readlink(p.p, p.n, &b)); return ailt_adopt_str(A, &b); }
static ail_str ailt_pp_repr(ail_sarena *A, ail_str s) { ailf_buf b; AILT_CHECK(ailf_repr_buf(s.p, s.n, &b)); return ailt_adopt_str(A, &b); }
'''

TYPED_URL = r'''
/* ---- G12 typed adapters: the urllib.parse primitives of urllower.URL_PRIMS over ailurl_core.h ---- */
static ail_str ailt_ur_unquote(ail_sarena *A, ail_str s, int64_t plus) { ailf_buf b; AILT_CHECK(ailu_unquote(s.p, s.n, plus, &b)); return ailt_adopt_str(A, &b); }
static ail_str ailt_ur_repr(ail_sarena *A, ail_str s) { ailf_buf b; AILT_CHECK(ailu_repr(s.p, s.n, &b)); return ailt_adopt_str(A, &b); }
'''

TYPED_HTTP = r'''
/* ---- G12 typed adapters: the HTTP primitives of urllower.HTTP_PRIMS over ailhttp_core.h (libcurl) ---- */
static int64_t ailt_ht_begin(ail_str m, ail_str u, int64_t us) { AILT_CHECK(ailh_begin(m.p, m.n, u.p, u.n, us)); return 0; }
static int64_t ailt_ht_hdr(ail_str n, ail_str v) { AILT_CHECK(ailh_hdr_add(n.p, n.n, v.p, v.n)); return 0; }
static int64_t ailt_ht_body(ail_bytes d) { AILT_CHECK(ailh_set_body(d.p, d.n)); return 0; }
static int64_t ailt_ht_perform(void) { int64_t h = ailh_perform(); if (h < 0) ailt_fraise(); return h; }
static int64_t ailt_ht_failed(int64_t h) { return ailh_failed(h); }
static ail_str ailt_ht_errtext(ail_sarena *A, int64_t h) { ailf_buf b; AILT_CHECK(ailh_errtext(h, &b)); return ailt_adopt_str(A, &b); }
static int64_t ailt_ht_status(int64_t h) { return ailh_status(h); }
static ail_str ailt_ht_reason(ail_sarena *A, int64_t h) { ailf_buf b; AILT_CHECK(ailh_reason(h, &b)); return ailt_adopt_str(A, &b); }
static int64_t ailt_ht_nhdr(int64_t h) { return ailh_nhdr(h); }
static ail_str ailt_ht_hname(ail_sarena *A, int64_t h, int64_t i) { ailf_buf b; AILT_CHECK(ailh_hname(h, i, &b)); return ailt_adopt_str(A, &b); }
static ail_str ailt_ht_hval(ail_sarena *A, int64_t h, int64_t i) { ailf_buf b; AILT_CHECK(ailh_hval(h, i, &b)); return ailt_adopt_str(A, &b); }
static int64_t ailt_ht_hfind(int64_t h, ail_str name) { return ailh_hfind(h, name.p, name.n); }
static ail_bytes ailt_ht_read(ail_barena *A, int64_t h, int64_t amt) { ailf_buf b; AILT_CHECK(ailh_read(h, amt, &b)); return ailt_adopt_bytes(A, &b); }
static int64_t ailt_ht_close(int64_t h) { return ailh_close(h); }
static int64_t ailt_ht_free(int64_t h) { return ailh_free(h); }
static int64_t ailt_ht_eset(int64_t h, int64_t kind, int64_t code, ail_str u, ail_str r, ail_str m) {
    AILT_CHECK(ailh_eset(h, kind, code, u.p, u.n, r.p, r.n, m.p, m.n)); return 0;
}
static int64_t ailt_ht_ecode(void) { return ailh_ecode(); }
static int64_t ailt_ht_eh(void) { return ailh_eh(); }
static ail_str ailt_ht_eurl(ail_sarena *A) { ailf_buf b; AILT_CHECK(ailh_eurl(&b)); return ailt_adopt_str(A, &b); }
static ail_str ailt_ht_ereason(ail_sarena *A) { ailf_buf b; AILT_CHECK(ailh_ereason(&b)); return ailt_adopt_str(A, &b); }
static ail_str ailt_ht_emsg(ail_sarena *A) { ailf_buf b; AILT_CHECK(ailh_emsg(&b)); return ailt_adopt_str(A, &b); }
'''


TYPED_SQL = r'''
/* ---- G11 typed adapters: the sqlite3 primitives of sqllower.SQLP over ailsql_core.h ---- */
static void ailt_sraise(void) {
    ail_raise_value_adopt(ail_exception_new(ails_e.code, (const uint8_t *)ails_e.msg, (int64_t)strlen(ails_e.msg),
                                            (_Bool)ailt_ascii(ails_e.msg)));
}
#define AILT_SCHECK(call) do { if ((call) < 0) ailt_sraise(); } while (0)
static int64_t ailt_sq_open(ail_str p, int64_t iso) { int64_t h = ails_connect(p.p, p.n, iso); if (h < 0) ailt_sraise(); return h; }
static int64_t ailt_sq_close(int64_t h) { AILT_SCHECK(ails_close(h)); return 0; }
static int64_t ailt_sq_commit(int64_t h) { AILT_SCHECK(ails_commit(h)); return 0; }
static int64_t ailt_sq_rollback(int64_t h) { AILT_SCHECK(ails_rollback(h)); return 0; }
static int64_t ailt_sq_cursor(int64_t h) { int64_t r = ails_cursor(h); if (r < 0) ailt_sraise(); return r; }
static int64_t ailt_sq_prep(int64_t h, ail_str s) { int64_t r = ails_prep(h, s.p, s.n); if (r < 0) ailt_sraise(); return r; }
static int64_t ailt_sq_named(int64_t h) { AILT_SCHECK(ails_set_named(h)); return h; }
static int64_t ailt_sq_name(int64_t h, ail_str k) { AILT_SCHECK(ails_bind_name(h, k.p, k.n)); return h; }
static int64_t ailt_sq_bi(int64_t h, int64_t v) { AILT_SCHECK(ails_bind_int(h, v)); return h; }
static int64_t ailt_sq_bf(int64_t h, double v) { AILT_SCHECK(ails_bind_float(h, v)); return h; }
static int64_t ailt_sq_bs(int64_t h, ail_str s) { AILT_SCHECK(ails_bind_text(h, s.p, s.n)); return h; }
static int64_t ailt_sq_bb(int64_t h, ail_bytes d) { AILT_SCHECK(ails_bind_blob(h, d.p, d.n)); return h; }
static int64_t ailt_sq_bn(int64_t h) { AILT_SCHECK(ails_bind_null(h)); return h; }
static int64_t ailt_sq_exec(int64_t h) { AILT_SCHECK(ails_exec(h)); return h; }
static int64_t ailt_sq_mbegin(int64_t h) { AILT_SCHECK(ails_mbegin(h)); return h; }
static int64_t ailt_sq_mrow(int64_t h) { AILT_SCHECK(ails_mrow(h)); return h; }
static int64_t ailt_sq_mstep(int64_t h) { AILT_SCHECK(ails_mstep(h)); return h; }
static int64_t ailt_sq_mend(int64_t h) { AILT_SCHECK(ails_mend(h)); return h; }
static int64_t ailt_sq_script(int64_t h, ail_str s) { int64_t r = ails_script(h, s.p, s.n); if (r < 0) ailt_sraise(); return r; }
static int64_t ailt_sq_next(int64_t h) { int r = ails_next(h); if (r < 0) ailt_sraise(); return r; }
static int64_t ailt_sq_cols(int64_t h, int64_t n) { AILT_SCHECK(ails_cols(h, n)); return 0; }
static int64_t ailt_sq_isnull(int64_t h, int64_t i) { int r = ails_isnull(h, i); if (r < 0) ailt_sraise(); return r; }
static int64_t ailt_sq_ci(int64_t h, int64_t i) { int err; int64_t v = ails_col_int(h, i, &err); if (err) ailt_sraise(); return v; }
static double ailt_sq_cf(int64_t h, int64_t i) { int err; double v = ails_col_float(h, i, &err); if (err) ailt_sraise(); return v; }
static ail_str ailt_sq_cs(ail_sarena *A, int64_t h, int64_t i) { ailf_buf b; AILT_SCHECK(ails_col_text(h, i, &b)); return ailt_adopt_str(A, &b); }
static ail_bytes ailt_sq_cb(ail_barena *A, int64_t h, int64_t i) { ailf_buf b; AILT_SCHECK(ails_col_blob(h, i, &b)); return ailt_adopt_bytes(A, &b); }
static int64_t ailt_sq_rowcount(int64_t h) { int64_t v; AILT_SCHECK(ails_rowcount(h, &v)); return v; }
static int64_t ailt_sq_lastrowid(int64_t h) { int64_t v; AILT_SCHECK(ails_lastrowid(h, &v)); return v; }
static int64_t ailt_sq_haslast(int64_t h) { int64_t v; AILT_SCHECK(ails_haslast(h, &v)); return v; }
static ail_str ailt_sq_lastshow(ail_sarena *A, int64_t h) { ailf_buf b; AILT_SCHECK(ails_lastshow(h, &b)); return ailt_adopt_str(A, &b); }
static int64_t ailt_sq_intx(int64_t h) { int64_t v = ails_in_transaction(h); if (v < 0) ailt_sraise(); return v; }
static int64_t ailt_sq_total(int64_t h) { int64_t v = ails_total_changes(h); if (v < 0) ailt_sraise(); return v; }
static int64_t ailt_sq_free(int64_t h) { ails_cur_free(h); return 0; }
static int64_t ailt_sq_drop(int64_t h) { ails_cur_drop(h); return 0; }
static int64_t ailt_sq_blen(int64_t h, int64_t n) { AILT_SCHECK(ails_blen(h, n)); return h; }
static ail_str ailt_sq_reprb(ail_sarena *A, ail_bytes d) { ailf_buf b; AILT_SCHECK(ails_repr_bytes(d.p, d.n, &b)); return ailt_adopt_str(A, &b); }
'''

TYPED_HASH = r'''
/* ---- crypto typed adapters: the hashlib / hmac / secrets / base64 primitives of hashlower.HASHP over ailhash_core.h ----
   A state is a bytes value; nothing here raises: the prelude checks every argument first. */
static unsigned char *ailt_hs_buf(ail_barena *A, int64_t n) {
    unsigned char *q = (unsigned char *)ail_alloc_raw((size_t)(n > 0 ? n : 1));
    ail_barena_push(A, q);
    return q;
}
static int64_t ailt_hs_algo(ail_str s) { return ailhs_algo_of(s.p, s.n); }
static ail_bytes ailt_hs_new(ail_barena *A, int64_t algo, int64_t size, ail_bytes key, ail_bytes salt, ail_bytes person) {
    unsigned char *q = ailt_hs_buf(A, AILHS_BLOB1);
    ailhs_new(q, (int)algo, size, key.p, key.n, salt.p, salt.n, person.p, person.n);
    return (ail_bytes){q, AILHS_BLOB1};
}
static ail_bytes ailt_hs_hmac(ail_barena *A, int64_t algo, ail_bytes key) {
    unsigned char *q = ailt_hs_buf(A, AILHS_BLOB2);
    ailhs_hmac_new(q, (int)algo, key.p, key.n);
    return (ail_bytes){q, AILHS_BLOB2};
}
static ail_bytes ailt_hs_update(ail_barena *A, ail_bytes st, ail_bytes d) {
    unsigned char *q = ailt_hs_buf(A, st.n);
    if (ailhs_feed(q, st.p, st.n, d.p, d.n) < 0) ail_die("not a hash state");
    return (ail_bytes){q, st.n};
}
static ail_bytes ailt_hs_digest(ail_barena *A, ail_bytes st) {
    int64_t n = ailhs_info(st.p, st.n, 0);
    if (n < 0) ail_die("not a hash state");
    unsigned char *q = ailt_hs_buf(A, n);
    ailhs_digest_of(q, st.p, st.n);
    return (ail_bytes){q, n};
}
static int64_t ailt_hs_info(ail_bytes st, int64_t which) {
    int64_t r = ailhs_info(st.p, st.n, which);
    if (r < 0) ail_die("not a hash state");
    return r;
}
static ail_bytes ailt_hs_pbkdf2(ail_barena *A, int64_t algo, ail_bytes pw, ail_bytes salt, int64_t iters, int64_t dklen) {
    unsigned char *q = ailt_hs_buf(A, dklen);
    ailhs_pbkdf2(q, dklen, (int)algo, pw.p, pw.n, salt.p, salt.n, iters);
    return (ail_bytes){q, dklen};
}
static int64_t ailt_hs_cmp(ail_bytes a, ail_bytes b) { return ailhs_cmp(a.p, a.n, b.p, b.n); }
static ail_bytes ailt_hs_rand(ail_barena *A, int64_t n) {
    if (n <= 0) return (ail_bytes){NULL, 0};
    unsigned char *q = ailt_hs_buf(A, n);
    if (ailhs_random(q, (size_t)n) < 0) ail_die("cannot read random bytes from the operating system");
    return (ail_bytes){q, n};
}
static int64_t ailt_hs_bits(int64_t k) {
    int64_t r = ailhs_randbits(k);
    if (r < 0) ail_die("cannot read random bytes from the operating system");
    return r;
}
static ail_bytes ailt_hs_b64e(ail_barena *A, ail_bytes d, int64_t urlsafe) {
    int64_t n = ailhs_b64e_len(d.n);
    if (n == 0) return (ail_bytes){NULL, 0};
    unsigned char *q = ailt_hs_buf(A, n);
    ailhs_b64e(q, d.p, d.n, (int)urlsafe);
    return (ail_bytes){q, n};
}
static ail_bytes ailt_hs_b64d(ail_barena *A, ail_bytes d, int64_t mode) {
    unsigned char *q = ailt_hs_buf(A, 3 * ((d.n + 3) / 4) + 3);
    int64_t n = ailhs_b64d(q, d.p, d.n, (int)mode);
    return (ail_bytes){n > 0 ? q : NULL, n > 0 ? n : 0};
}
static int64_t ailt_hs_b64err(void) { return ailhs_b64_err; }
static int64_t ailt_hs_b64n(void) { return ailhs_b64_n; }
'''

_TYPED_BY_KIND = {'file': TYPED, 'proc': TYPED_PROC, 'path': TYPED_PATH, 'sql': TYPED_SQL, 'http': TYPED_HTTP, 'url': TYPED_URL,
                  'hash': TYPED_HASH}
for _name in filelib.PRIMS:
    if _name == '_ail_sq_bind':       # resolved to _ail_sq_bi / bf / bs / bb by pyfunc._fileprim_value
        continue
    assert ('ailt_' + filelib.c_name(_name) + '(') in _TYPED_BY_KIND[filelib.prim_kind(_name)], _name


def register(ORDER, SOURCE, REQUIRES):
    """Add the file parts to cruntime's tables (called once at the end of cruntime.py)."""
    for name, text, requires in (
            ('FILECORE', CORE, ['MONOTONICHEAD', 'TYPES', 'DIE']),
            ('FILEIO', TYPED, ['FILECORE', 'FILEEXC', 'STR', 'BYTES', 'DIE']),
            ('PROCCORE', PROCCORE, ['FILECORE']),
            ('PROCIO', TYPED_PROC, ['PROCCORE', 'FILEIO', 'PROCEXC']),
            ('PATHCORE', PATHCORE, ['FILECORE']),
            ('PATHIO', TYPED_PATH, ['PATHCORE', 'FILEIO']),
            ('URLCORE', URLCORE, ['FILECORE']),
            ('URLIO', TYPED_URL, ['URLCORE', 'FILEIO']),
            ('HTTPCORE', HTTPCORE, ['FILECORE']),
            ('HTTPIO', TYPED_HTTP, ['HTTPCORE', 'FILEIO', 'HTTPEXC']),
            ('HASHCORE', HASHCORE, ['TYPES', 'DIE']),
            ('HASHIO', TYPED_HASH, ['HASHCORE', 'STR', 'BYTES', 'DIE']),
            ('SQLCORE', SQLCORE, ['FILECORE']),
            ('SQLIO', TYPED_SQL, ['SQLCORE', 'FILEIO', 'SQLEXC'])):
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
    ail_obj args[2] = {ail_box_int(error), v[0]};
    v[3] = ail_tuple_new(cx, args, 2);
    ail_inst_setattr(cx, v[2], ail_intern(cx, "errno"), ail_box_int(error));
    ail_inst_setattr(cx, v[2], ail_intern(cx, "strerror"), v[0]);
    if (filename) v[4] = ail_bi_str_from_utf8(cx, filename, (int64_t)strlen(filename));
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
    # (the process primitives of stage G8 are in GENERAL_SPEC_PROC)
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


GENERAL_SPEC_PROC = {
    'sp_begin': ('status', 'ailp_begin()'),
    'sp_arg': ('status', 'ailp_add_arg({s0})'),
    'sp_cwd': ('status', 'ailp_set_cwd({s0})'),
    'sp_envbegin': ('status', 'ailp_env_begin()'),
    'sp_env': ('status', 'ailp_env_add({s0}, {s1})'),
    'sp_inputt': ('status', 'ailp_input_text({s0}, {i1}, {i2})'),
    'sp_run': ('val', 'ailp_run({i0}, {i1})'),
    'sp_rc': ('plain', 'ailp_rc({i0})'),
    'sp_timedout': ('plain', 'ailp_timedout({i0})'),
    'sp_outt': ('buf', 'ailp_out_text({i0}, {i1}, {i2}, {i3}, &b)'),
    'sp_free': ('plain', 'ailp_free({i0})'),
    'sp_errfrom': ('plain', 'ailp_err_from({i0}, {s1})'),
    'sp_errbegin': ('plain', 'ailp_err_begin({i0}, {i1}, {s2})'),
    'sp_errarg': ('status', 'ailp_err_arg({s0})'),
    'sp_errout_t': ('status', 'ailp_err_out({s0})'),
    'sp_errerr_t': ('status', 'ailp_err_err({s0})'),
    'sp_errrc': ('plain', 'ailp_get_rc()'),
    'sp_errcmd': ('buf', 'ailp_get_cmd(&b)'),
    'sp_erro_t': ('buf', 'ailp_get_buf(&b, &ailp_last.out)'),
    'sp_erre_t': ('buf', 'ailp_get_buf(&b, &ailp_last.err)'),
    'sp_errtimeout': ('buf', 'ailp_get_timeout(&b)'),
    'sp_errmsg': ('buf', 'ailp_err_msg(&b)'),
    'sp_repr': ('buf', 'ailp_repr({s0}, &b)'),
}


GENERAL_SPEC_PATH = {
    'pp_staterr': ('plain', 'ailf_stat_errno({s0})'),
    'pp_readlink': ('buf', 'ailf_readlink({s0}, &b)'),
    'pp_repr': ('buf', 'ailf_repr_buf({s0}, &b)'),
}


def general_wrappers(which='file'):
    out = []
    for prim, (ret, kinds) in filelib.PRIMS.items():
        cname = filelib.c_name(prim)
        if filelib.prim_kind(prim) != which:
            continue
        if 'bytes' in kinds or ret == 'bytes':
            continue
        form, expr = {'file': GENERAL_SPEC, 'proc': GENERAL_SPEC_PROC, 'path': GENERAL_SPEC_PATH}[which][cname]
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
GENERAL_PROC = general_wrappers('proc')
GENERAL_PATH = general_wrappers('path')


def general_text():
    """The C the general runtime needs once a program reaches a file primitive."""
    return '\n/* ---- G7: shared file core ---- */\n' + CORE + GENERAL


def general_proc_text():
    """The C the general runtime needs once a program reaches a process primitive (after general_text())."""
    return '\n/* ---- G8: process core ---- */\n' + PROCCORE + GENERAL_PROC


def general_path_text():
    """The C the general runtime needs once a program reaches a pathlib primitive (after general_text())."""
    return '\n/* ---- G10: pathlib core ---- */\n' + PATHCORE + GENERAL_PATH
