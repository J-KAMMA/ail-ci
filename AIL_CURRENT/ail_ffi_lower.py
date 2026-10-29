"""G4: compile `@extern` stubs (see ail_ffi.py) into a typed C object plus plain AIL wrappers.

`Session.lower(path, text)` reads one Python-syntax file. A file that does not mention `ail_ffi` comes
back byte for byte, so programs without FFI compile exactly as before. For a file that does:

* the `from ail_ffi import ...` lines and the decorated stubs are blanked (line numbers do not move);
* one ordinary AIL function per stub is appended at the end of the file. It has the stub's name and
  Python-level signature (`length(...)` parameters disappear) and calls an exported function of the
  C object by a unique name, then does what C cannot do: raise the declared exception, copy a
  bytearray back, supply the `length` arguments;
* the stub is recorded for `Session.build`, which writes one C file (the adapter source: includes
  each header, checks each real prototype with `_Static_assert(_Generic(...))`, converts arguments,
  captures errno right after the call) and one interface JSON, and builds them with the existing
  `compile-c` machinery (c_object.py). Nothing here changes how a program without stubs compiles.

Link flags (`-lz`, a shared library path with its rpath) travel in `Session.link_args`.

Callbacks (F7). A stub parameter `callback(ret, arg, ...)` takes the name of a module-level def. Each call of such a
stub is rewritten in place to a wrapper made for that def (`ffi_<tag>_<stub>__via_<def>`; the callback argument
becomes `0`), so the C side never holds an AIL function value. The adapter runs the C function on a stack of its
own (ucontext): its trampoline stores C's arguments and switches back to the wrapper, which reads them, calls the
def and switches into C again with the result. An exception leaves the wrapper's loop; its `finally` lets the C call
run to the end with every callback returning `on_error`, copies the bytearrays back, and the exception goes on.
A stub that takes a callback has no plain wrapper, so it is called in the file that declares it (another module calls
a def of that file which makes the call).
"""
import ast
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from ail_modules import ModuleRefusal

# name -> (C type, interface kind for a parameter/result, Python annotation, bits, signed)
INTS = {
    'c_int8': ('int8_t', 'int8', 8, True), 'c_byte': ('int8_t', 'int8', 8, True),
    'c_int16': ('int16_t', 'int16', 16, True), 'c_short': ('short', 'int16', 16, True),
    'c_int32': ('int32_t', 'int32', 32, True), 'c_int': ('int', 'int32', 32, True),
    'c_int64': ('int64_t', 'int', 64, True), 'c_long': ('long', 'int', 64, True),
    'c_longlong': ('long long', 'int', 64, True), 'c_ssize_t': ('ssize_t', 'int', 64, True),
    'c_uint8': ('uint8_t', 'uint8', 8, False), 'c_ubyte': ('uint8_t', 'uint8', 8, False),
    'c_uint16': ('uint16_t', 'uint16', 16, False), 'c_ushort': ('unsigned short', 'uint16', 16, False),
    'c_uint32': ('uint32_t', 'uint32', 32, False), 'c_uint': ('unsigned int', 'uint32', 32, False),
    'c_uint64': ('uint64_t', 'uint64_bits', 64, False), 'c_ulong': ('unsigned long', 'uint64_bits', 64, False),
    'c_ulonglong': ('unsigned long long', 'uint64_bits', 64, False), 'c_size_t': ('size_t', 'uint64_bits', 64, False),
}
NATIVE = {'int8': 'int8_t', 'int16': 'int16_t', 'int32': 'int32_t', 'uint8': 'uint8_t', 'uint16': 'uint16_t',
          'uint32': 'uint32_t', 'int': 'int64_t', 'uint64_bits': 'uint64_t'}
EXCEPTIONS = ('OSError', 'ValueError', 'RuntimeError', 'KeyError', 'IndexError', 'OverflowError', 'EOFError')
CHECKS = {'negative': '< 0', 'nonzero': '!= 0', 'null': '== 0', 'minus1': '== -1'}
OPTIONS = ('lib', 'header', 'symbol', 'check', 'errno', 'exc', 'pkg_config', 'sources', 'trust')


PARALLEL_CALLS = ('Thread', 'Process', 'start_new_thread', 'submit', 'map', 'starmap', 'apply', 'apply_async', 'map_async',
                  'starmap_async', 'imap', 'imap_unordered')
PARALLEL_LOOPS = ('par_range', '_ail_par_range')

CB_RESULT_ANN = set(INTS) | {'c_bool', 'c_double', 'c_float', 'c_void_p'}
CB_ARG_ANN = set(INTS) | {'c_bool', 'c_double', 'c_float', 'c_void_p', 'c_const_void_p', 'c_char_p', 'c_mut_char_p'}
CB_ELEM_ANN = set(INTS) | {'c_bool', 'c_double', 'c_float', 'c_char_p', 'c_mut_char_p'}
CB_MAX = 16
# array element codes the adapter's accessors switch on
CB_CODES = {'int8_t': 1, 'uint8_t': 2, 'int16_t': 3, 'short': 3, 'uint16_t': 4, 'unsigned short': 4, 'int32_t': 5, 'int': 5,
            'uint32_t': 6, 'unsigned int': 6, 'int64_t': 7, 'long': 7, 'long long': 7, 'ssize_t': 7, 'uint64_t': 8,
            'unsigned long': 8, 'unsigned long long': 8, 'size_t': 8, '_Bool': 9, 'double': 10, 'float': 11,
            'const char *': 12, 'char *': 12}


class CbArg:
    """One argument of a callback type: `kind` is value, cptr or array; `ann` the C type name; `count` (array) the
    index of the argument that holds the number of elements."""

    def __init__(self, kind, ann, count=None):
        self.kind, self.ann, self.count = kind, ann, count

    def ctype(self):
        if self.kind == 'cptr':
            return 'const %s *' % elem_info(self.ann)[0]
        if self.kind == 'array':
            inner = cb_value_ctype(self.ann)
            return inner + ('*' if inner.endswith('*') else ' *')
        return cb_value_ctype(self.ann)

    def python(self):
        if self.kind == 'array':
            return 'list[%s]' % python_type(self.ann)
        return 'int' if self.ann == 'c_const_void_p' else python_type(self.ann)


class CallbackType:
    """One `callback(ret, arg, ...)` parameter type."""

    def __init__(self, ret, args, on_error, text):
        self.ret, self.args, self.on_error, self.text = ret, args, on_error, text

    def ctype(self):
        return '%s (*)(%s)' % ('void' if self.ret is None else result_ctype(self.ret),
                               ', '.join(a.ctype() for a in self.args) or 'void')

    def python_result(self):
        return 'None' if self.ret is None else python_type(self.ret)

    def signature(self, name):
        return 'def %s(%s) -> %s:' % (name, ', '.join('a%d: %s' % (i, a.python()) for i, a in enumerate(self.args)),
                                       self.python_result())


def cb_value_ctype(ann):
    if ann in INTS:
        return INTS[ann][0]
    return {'c_bool': '_Bool', 'c_double': 'double', 'c_float': 'float', 'c_void_p': 'void *', 'c_const_void_p': 'const void *',
            'c_char_p': 'const char *', 'c_mut_char_p': 'char *'}[ann]


class HandleType:
    """One `Handle(name, free=...)`: the AIL class that owns the pointer and the C helpers behind it."""

    def __init__(self, name, free, cls, line):
        self.name, self.free, self.cls, self.line = name, free, cls, line
        self.emitted = False
        tag = hashlib.sha1(('%s\0%s' % (name, free)).encode()).hexdigest()[:6]
        self.reg, self.release, self.adopt, self.make = ('ffi_h%s_%s' % (tag, word) for word in ('reg', 'release', 'adopt', 'make'))


class Param:
    def __init__(self, name, ann, default=None, has_default=False):
        self.name, self.ann, self.default, self.has_default = name, ann, default, has_default
        self.handle = None             # an owned Handle parameter: its HandleType (ann is then c_void_p)
        self.length_of = None          # for length("x", T): the parameter name
        self.length_type = None
        self.elem = None               # ptr(T) / cptr(T): the element type name, else None
        self.callback = None           # callback(...): its CallbackType (ann is then 'callback')


class Decl:
    def __init__(self):
        self.path = self.line = self.name = self.symbol = self.export = None
        self.lib = self.header = self.pkg_config = None
        self.check = self.exc = None
        self.sources = []
        self.errno = False
        self.trust = False             # trust=True: the header is included but its prototype is not compared
        self.params = []
        self.result = None             # annotation name, or None for void
        self.result_handle = None      # an owned Handle result: its HandleType (result is then c_void_p)
        self.tag = None                # per-file hash
        self.local_header = False
        self.directory = None
        self.variants = {}             # F7: (callback def names) -> the wrapper made for them

    @property
    def has_callbacks(self):
        return any(p.callback is not None for p in self.params)

    @property
    def has_bytearray(self):
        return any(p.ann in ('bytearray', 'c_mut_void_p') for p in self.params)

    def c_params(self):
        """[(C type, name)] of the real function, in order."""
        out = []
        for p in self.params:
            out.append(p_ctype(p))
        return out

    def prototype(self):
        ret = 'void' if self.result is None else result_ctype(self.result)
        return '%s %s(%s)' % (ret, self.symbol, ', '.join(self.c_params()) or 'void')


def elem_info(name):
    """(C type, size in bytes) of the element type of ptr(T) / cptr(T)."""
    if name in INTS:
        return INTS[name][0], INTS[name][2] // 8
    return {'c_double': ('double', 8), 'c_float': ('float', 4), 'c_bool': ('_Bool', 1), 'c_void_p': ('void *', 8)}[name]


def p_ctype(p):
    if p.callback is not None:
        return p.callback.ctype()
    if p.length_of is not None:
        return INTS[p.length_type][0]
    if p.elem is not None:
        return ('const %s *' if p.ann == 'bytes' else '%s *') % elem_info(p.elem)[0]
    if p.ann in INTS:
        return INTS[p.ann][0]
    return {'c_bool': '_Bool', 'c_double': 'double', 'c_float': 'float', 'c_char_p': 'const char *',
            'c_void_p': 'void *', 'c_mut_char_p': 'char *', 'bytes': 'const unsigned char *', 'bytearray': 'unsigned char *',
            'c_const_void_p': 'const void *', 'c_mut_void_p': 'void *'}[p.ann]


def result_ctype(ann):
    if ann in INTS:
        return INTS[ann][0]
    return {'c_bool': '_Bool', 'c_double': 'double', 'c_float': 'float', 'c_char_p': 'const char *',
            'c_mut_char_p': 'char *', 'c_void_p': 'void *'}[ann]


PARAM_ANN = set(INTS) | {'c_bool', 'c_double', 'c_float', 'c_char_p', 'c_mut_char_p', 'c_void_p', 'bytes', 'bytearray', 'str',
                         'c_const_void_p', 'c_mut_void_p'}
RESULT_ANN = set(INTS) | {'c_bool', 'c_double', 'c_float', 'c_char_p', 'c_mut_char_p', 'c_void_p', 'str'}


def python_type(ann):
    """The AIL/Python type the wrapper uses for a stub annotation."""
    if ann in INTS:
        return 'int'
    return {'c_bool': 'bool', 'c_double': 'float', 'c_float': 'float', 'c_char_p': 'str', 'c_mut_char_p': 'str', 'str': 'str',
            'c_void_p': 'int', 'bytes': 'bytes', 'c_const_void_p': 'bytes', 'bytearray': 'bytearray',
            'c_mut_void_p': 'bytearray'}[ann]


# F7: the adapter's callback machinery, written only when a stub takes a callback. A C call that takes a callback runs on
# a stack of its own; a trampoline stores C's arguments in the call's record and switches back to the AIL wrapper,
# which calls the def and switches into C again with the result (all on the caller's thread).
CB_RUNTIME = r"""#include <stdio.h>
#include <ucontext.h>
#define FFI_CB_STACK ((size_t)8 << 20)
typedef struct ffi_cb_rec {
    ucontext_t ctx, caller;
    void *stack;
    struct ffi_cb_rec *outer;
    const char *mark;
    void (*run)(struct ffi_cb_rec *);
    int stub, done, failed, event, err;
    int64_t ai[16]; double af[16]; void *ap[16]; size_t an[16];
    int64_t ci[16]; double cf[16]; const void *cp[16]; int ck[16];
    int64_t ri; double rf;
    int64_t rc_i; double rc_f; const char *rc_s;
} ffi_cb_rec;
static ffi_cb_rec *ffi_cb_top, *ffi_cb_entering;
static _Thread_local char ffi_cb_mark;
static void ffi_cb_entry(void) { ffi_cb_rec *r = ffi_cb_entering; r->run(r); r->done = 1; }
static void *ffi_cb_dup(const void *p, size_t n) { void *q = malloc(n ? n : 1); if (!q) abort(); if (n) memcpy(q, p, n); return q; }
static ffi_cb_rec *ffi_cb_new(void (*run)(ffi_cb_rec *), int stub) {
    ffi_cb_rec *r = calloc(1, sizeof *r);
    if (!r || !(r->stack = malloc(FFI_CB_STACK)) || getcontext(&r->ctx) != 0) abort();
    r->ctx.uc_stack.ss_sp = r->stack; r->ctx.uc_stack.ss_size = FFI_CB_STACK; r->ctx.uc_link = &r->caller;
    makecontext(&r->ctx, ffi_cb_entry, 0);
    r->run = run; r->stub = stub; r->mark = &ffi_cb_mark; r->outer = ffi_cb_top; ffi_cb_top = r;
    return r;
}
static int64_t ffi_cb_go(ffi_cb_rec *r) {
    ffi_cb_entering = r; r->event = 0;
    if (swapcontext(&r->caller, &r->ctx) != 0) abort();
    return r->done ? 0 : r->event;
}
static ffi_cb_rec *ffi_cb_enter(int stub, const char *name) {
    ffi_cb_rec *r = ffi_cb_top;
    if (!r || r->mark != &ffi_cb_mark || r->stub != stub || r->done) {
        fflush(stdout);
        fprintf(stderr, "ail_ffi: the callback of %s was called from another thread or after its C call returned\n", name);
        fflush(stderr);
        abort();
    }
    return r;
}
static int ffi_cb_yield(ffi_cb_rec *r, int slot) {
    if (r->failed) return 0;
    r->event = slot;
    if (swapcontext(&r->ctx, &r->caller) != 0) abort();
    return !r->failed;
}
static ffi_cb_rec *ffi_cb_end(void) {
    ffi_cb_rec *r = ffi_cb_top;
    if (!r->done) { r->failed = 1; ffi_cb_go(r); }
    ffi_cb_top = r->outer;
    ffi_last_errno = r->err;
    free(r->stack);
    return r;
}
static ail_c_utf8_view ffi_cb_view(const char *s) {
    return s ? (ail_c_utf8_view){(const unsigned char *)s, strlen(s)} : (ail_c_utf8_view){NULL, 0};
}
static int64_t ffi_cb_item_i(ffi_cb_rec *r, int64_t k, int64_t i) {
    const void *p = r->cp[k];
    switch (r->ck[k]) {
    case 1: return ((const int8_t *)p)[i];
    case 2: return ((const uint8_t *)p)[i];
    case 3: return ((const int16_t *)p)[i];
    case 4: return ((const uint16_t *)p)[i];
    case 5: return ((const int32_t *)p)[i];
    case 6: return ((const uint32_t *)p)[i];
    case 7: return ((const int64_t *)p)[i];
    case 8: return (int64_t)((const uint64_t *)p)[i];
    case 9: return ((const _Bool *)p)[i];
    }
    return 0;
}"""


class Session:
    def __init__(self, workdir=None, forbid=False):
        self.workdir = None if workdir is None else Path(workdir)
        self.forbid = forbid
        self.decls = []
        self.links = {}                 # declaring file -> [(library, pkg_config, directory)] from link()
        self.lowered = {}               # resolved path -> lowered text
        self.link_args = []
        self.extra_libs = []            # `compile --link LIB`: the same as link("LIB") for the whole program
        self.notes = []
        self._owned = False
        self.library_entry = None       # `compile --lib`: the entry file, the only one that may say `@export`
        self.link_lines = {}            # (declaring file, library) -> line of its link() call
        self.handles = {}               # (name, free) -> HandleType, in order of first mention (F4)
        self.handle_aliases = {}        # `Db = Handle(...)`: alias -> (name, free)
        self.cb_aliases = {}            # `Cmp = callback(...)` in the file being lowered: alias -> CallbackType (F7)

    def close(self):
        if self._owned and self.workdir is not None:
            shutil.rmtree(self.workdir, ignore_errors=True)
            self.workdir, self._owned = None, False

    # ------------------------------------------------------------------ reading

    def read(self, path):
        """ail_modules' `read` callback: the file's text with stubs lowered."""
        text = Path(path).read_bytes().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
        return self.lower(path, text)

    def lower(self, path, text):
        if 'ail_ffi' not in text:
            return text
        key = str(Path(path).resolve())
        if key in self.lowered:
            return self.lowered[key]
        try:
            tree = ast.parse(text, filename=key)
        except SyntaxError:
            return text                 # the caller's own parse reports it
        result = self._lower(Path(key), text, tree)
        self.lowered[key] = result
        return result

    def _refuse(self, path, node, message):
        raise ModuleRefusal(path, getattr(node, 'lineno', 1), getattr(node, 'col_offset', 0) + 1, message)

    def _lower(self, path, text, tree):
        imported = set()                # names bound by `from ail_ffi import`
        module_names = set()            # names bound by `import ail_ffi [as x]`
        blank = []                      # (first line, last line)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == 'ail_ffi' and node.level == 0:
                for alias in node.names:
                    if alias.name == '*':
                        imported.update(set(INTS) | PARAM_ANN | {'extern', 'link', 'length', 'ptr', 'cptr', 'declarations', 'Handle',
                                                                 'callback', 'array'})
                        continue
                    if alias.asname not in (None, alias.name):
                        self._refuse(path, node, 'ail_ffi: import its names plainly (`from ail_ffi import extern, c_int`)')
                    imported.add(alias.name)
                blank.append((node.lineno, node.end_lineno))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'ail_ffi':
                        module_names.add(alias.asname or 'ail_ffi')
                        blank.append((node.lineno, node.end_lineno))
        if not imported and not module_names:
            return text
        keep = []                       # (first line, replacement) in the library entry: `export` stays for ail_export.lower
        if self.library_entry is not None:
            if Path(path) == self.library_entry:
                for node in tree.body:
                    if isinstance(node, ast.ImportFrom) and node.module == 'ail_ffi' and node.level == 0 \
                            and any(a.name == 'export' for a in node.names):
                        keep.append((node.lineno, 'from ail_ffi import export'))
                    elif isinstance(node, ast.Import) and any(a.name == 'ail_ffi' for a in node.names):
                        keep.append((node.lineno, 'import ' + ', '.join(
                            a.name + (' as ' + a.asname if a.asname else '') for a in node.names)))
            else:
                self._refuse_export(path, tree, imported, module_names)
        decls = []
        before = set(self.handles)      # HandleTypes first mentioned in this file get their class written here
        for node in tree.body:
            if isinstance(node, ast.Assign) and self._is_handle_call(node.value, imported, module_names):
                self._handle_alias(path, node, imported, module_names)
                blank.append((node.lineno, node.end_lineno))
        self.cb_aliases = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and self._is_named_call(node.value, 'callback', imported, module_names):
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    self._refuse(path, node, 'a callback type is bound to one plain name: `Cmp = callback(c_int, c_void_p, on_error=0)`')
                self.cb_aliases[node.targets[0].id] = self._callback_type(path, node.value, imported, module_names)
                blank.append((node.lineno, node.end_lineno))
        for node in tree.body:
            if isinstance(node, ast.Expr) and self._is_link(node.value, imported, module_names):
                self._link(path, node.value)
                blank.append((node.lineno, node.end_lineno))
                continue
            if not isinstance(node, ast.FunctionDef):
                continue
            deco = [d for d in node.decorator_list if self._is_extern(d, imported, module_names)]
            if not deco:
                continue
            if len(node.decorator_list) != 1:
                self._refuse(path, node, '%s: an @extern stub takes no other decorator' % node.name)
            decls.append(self._decl(path, node, deco[0], imported, module_names))
            blank.append((node.decorator_list[0].lineno, node.end_lineno))
        if self.forbid and decls:
            first = decls[0]
            raise ModuleRefusal(path, first.line, 1, 'FFI declaration %s (lib %s) is forbidden by --no-ffi' % (first.name, first.lib))
        tag = hashlib.sha1(str(path).encode()).hexdigest()[:6]
        for decl in decls:
            decl.tag = tag
            decl.export = 'ffi_%s_%s' % (tag, decl.name)
        lines = text.split('\n')
        for first, last in blank:
            for index in range(first - 1, last):
                lines[index] = ''
        for first, statement in keep:
            lines[first - 1] = statement
        if any(d.has_callbacks for d in decls):
            self._callback_sites(path, tree, decls, lines, tag)
        self.decls.extend(decls)
        handles_here = [ht for key, ht in self.handles.items() if key not in before]
        if self.handles:
            self._refuse_handle_use(path, tree)
        # a file that imports ail_ffi but declares nothing is left with its import blanked
        block = []
        for ht in handles_here:
            block.extend(self._handle_class(ht, tag))
        if decls:
            if any(d.has_bytearray for d in decls):
                block.append('')
                block.append('def ffi_put_%s(dst: bytearray, src: bytes, at: int) -> int:' % tag)
                block.append('    n = len(dst)')
                block.append('    dst.clear()')
                block.append('    dst.extend(src[at:at + n])')
                block.append('    return at + n')
            for decl in decls:
                if decl.has_callbacks:
                    for names, wrapper in decl.variants.items():
                        block.extend(self._cb_wrapper(decl, wrapper, names))
                else:
                    block.extend(self._wrapper(decl))
        return '\n'.join(lines).rstrip('\n') + '\n' + '\n'.join(block) + ('\n' if block else '')

    def _refuse_export(self, path, tree, imported, module_names):
        """`compile --lib`: only the entry file declares the C API."""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for d in node.decorator_list:
                target = d.func if isinstance(d, ast.Call) else d
                if (isinstance(target, ast.Name) and target.id == 'export' and 'export' in imported) or (
                        isinstance(target, ast.Attribute) and target.attr == 'export'
                        and isinstance(target.value, ast.Name) and target.value.id in module_names):
                    entry = self.library_entry.name
                    self._refuse(path, d, '@export on %s in %s, which is not the entry file: only %s declares '
                                 'the C API of a library.\n  write instead: remove @export here and, in %s, write '
                                 '`@export def %s(...): return <this module>.%s(...)` over the same types'
                                 % (node.name, Path(path).name, entry, entry, node.name, node.name))

    @staticmethod
    def _shared_path(lib):
        return lib.endswith(('.so', '.dylib', '.dll')) or '.so.' in lib

    def refuse_shared_links(self, name):
        """`compile --lib` also writes lib<name>.a: a `.so` path would have to be present wherever the archive is
        linked, so a library build takes library names (`-lz`) or `.a` archives, not shared objects."""
        used = {d.path for d in self.decls}
        wanted = [(d.lib, d.path, d.line) for d in self.decls if d.lib is not None]
        for key, entries in self.links.items():
            if key in used:
                wanted.extend((lib, key, self.link_lines.get((key, lib), 1)) for lib, _, _ in entries)
        for lib, path, line in wanted:
            if self._shared_path(lib):
                raise ModuleRefusal(path, line, 1,
                                    'link of the shared library %r cannot go into lib%s.a: a program that links the archive '
                                    'would need that .so at run time.\n  write instead: link by name (`link("%s")`) '
                                    'so the consumer\'s link line gets -l%s from %s.h, or link a static archive (`.a` path)'
                                    % (lib, name, Path(lib).name.removeprefix('lib').split('.')[0], Path(lib).name.removeprefix('lib').split('.')[0], name))
        for lib in self.extra_libs:
            if self._shared_path(lib):
                raise ValueError('--link %s: a shared library path cannot go into lib%s.a (a program that links the archive '
                                 'would need that .so at run time).\n  write instead: --link by name, or a static archive'
                                 % (lib, name))

    @staticmethod
    def _is_link(node, imported, module_names):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id == 'link' and 'link' in imported
        return (isinstance(func, ast.Attribute) and func.attr == 'link' and isinstance(func.value, ast.Name)
                and func.value.id in module_names)

    def _link(self, path, call):
        """`link("m", "z", pkg_config="zlib")` at module level: libraries for the stubs that have no `lib=`."""
        libs = [a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value]
        pkg = None
        for keyword in call.keywords:
            if keyword.arg == 'pkg_config' and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                pkg = keyword.value.value
            else:
                self._refuse(path, keyword.value, 'link: only pkg_config="name" is an option')
        if not libs or len(libs) != len(call.args):
            self._refuse(path, call, 'link("name", ...) takes library names or paths as string literals')
        self.links.setdefault(str(path), []).extend((lib, pkg, str(path.parent)) for lib in libs)
        for lib in libs:
            self.link_lines.setdefault((str(path), lib), call.lineno)

    @staticmethod
    def _is_extern(node, imported, module_names):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id == 'extern' and 'extern' in imported
        return (isinstance(func, ast.Attribute) and func.attr == 'extern' and isinstance(func.value, ast.Name)
                and func.value.id in module_names)

    def _ann_name(self, path, node, ann, imported, module_names, what):
        if isinstance(ann, ast.Name):
            name = ann.id
            if name in ('bytes', 'bytearray', 'str'):
                return name
            if name in imported:
                return name
        elif (isinstance(ann, ast.Attribute) and isinstance(ann.value, ast.Name) and ann.value.id in module_names):
            return ann.attr
        self._refuse(path, ann if ann is not None else node, '%s: unsupported FFI annotation `%s` (use a C type from ail_ffi, bytes, bytearray or str)'
                     % (what, ast.unparse(ann) if ann is not None else '<missing>'))

    def _decl(self, path, node, call, imported, module_names):
        decl = Decl()
        decl.path, decl.line, decl.name, decl.directory = str(path), node.lineno, node.name, str(path.parent)
        options = {}
        if call.args:
            self._refuse(path, call, '%s: @extern takes keyword options only' % node.name)
        for keyword in call.keywords:
            if keyword.arg not in OPTIONS:
                self._refuse(path, keyword.value, '%s: unknown @extern option %s' % (node.name, keyword.arg))
            options[keyword.arg] = keyword.value
        def constant(key, kinds):
            if key not in options:
                return None
            value = options[key]
            if isinstance(value, ast.Constant) and (value.value is None or isinstance(value.value, kinds)):
                return value.value
            self._refuse(path, value, '%s: @extern %s must be a literal' % (node.name, key))
        decl.lib = constant('lib', str)
        decl.header = constant('header', str)
        decl.pkg_config = constant('pkg_config', str)
        decl.symbol = constant('symbol', str) or node.name
        if 'sources' in options:
            value = options['sources']
            if not isinstance(value, (ast.List, ast.Tuple)) or not all(
                    isinstance(e, ast.Constant) and isinstance(e.value, str) and e.value.endswith('.c') and '/' not in e.value
                    for e in value.elts):
                self._refuse(path, value, '%s: sources must be a list of .c file names beside the declaring file' % node.name)
            decl.sources = [e.value for e in value.elts]
        decl.check = constant('check', str)
        decl.errno = bool(constant('errno', bool))
        decl.trust = bool(constant('trust', bool))
        if decl.check is not None and decl.check not in CHECKS:
            self._refuse(path, options['check'], '%s: check must be one of %s' % (node.name, ', '.join(sorted(CHECKS))))
        if decl.errno and decl.check is None:
            self._refuse(path, call, '%s: errno=True needs check= (which results are failures)' % node.name)
        if 'exc' in options:
            exc = options['exc']
            name = exc.id if isinstance(exc, ast.Name) else None
            if name not in EXCEPTIONS:
                self._refuse(path, exc, '%s: exc must be one of %s (the kinds AIL raises)' % (node.name, ', '.join(EXCEPTIONS)))
            decl.exc = name
        else:
            decl.exc = 'OSError' if decl.errno else 'RuntimeError'
        if decl.header is not None:
            if not decl.header.replace('/', '').replace('_', '').replace('.', '').replace('-', '').isalnum():
                self._refuse(path, options['header'], '%s: unsupported header name' % node.name)
        args = node.args
        if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
            self._refuse(path, node, '%s: variadic and keyword-only parameters are not C parameters' % node.name)
        defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
        seen = {}
        for arg, default in zip(args.args, defaults):
            if arg.annotation is None:
                self._refuse(path, arg, '%s: parameter %s needs an annotation (the C prototype)' % (node.name, arg.arg))
            ann = arg.annotation
            if isinstance(ann, ast.Call) and ((isinstance(ann.func, ast.Name) and ann.func.id == 'length' and 'length' in imported)
                                              or (isinstance(ann.func, ast.Attribute) and ann.func.attr == 'length')):
                if not ann.args or not isinstance(ann.args[0], ast.Constant) or not isinstance(ann.args[0].value, str) or len(ann.args) > 2 or ann.keywords:
                    self._refuse(path, ann, '%s: length("parameter", C integer type)' % node.name)
                param = Param(arg.arg, 'length')
                param.length_of = ann.args[0].value
                param.length_type = (self._ann_name(path, node, ann.args[1], imported, module_names, node.name)
                                     if len(ann.args) == 2 else 'c_size_t')
                if param.length_type not in INTS:
                    self._refuse(path, ann, '%s: length type must be an integer C type' % node.name)
                if default is not None:
                    self._refuse(path, default, '%s: a length parameter has no default' % node.name)
            elif isinstance(ann, ast.Call) and ((isinstance(ann.func, ast.Name) and ann.func.id in ('ptr', 'cptr') and ann.func.id in imported)
                                                or (isinstance(ann.func, ast.Attribute) and ann.func.attr in ('ptr', 'cptr'))):
                kind = ann.func.id if isinstance(ann.func, ast.Name) else ann.func.attr
                if len(ann.args) != 1 or ann.keywords:
                    self._refuse(path, ann, '%s: %s(element C type)' % (node.name, kind))
                element = self._ann_name(path, node, ann.args[0], imported, module_names, node.name)
                if element not in INTS and element not in ('c_double', 'c_float', 'c_bool', 'c_void_p'):
                    self._refuse(path, ann, '%s: %s takes an integer, float, bool or c_void_p C type' % (node.name, kind))
                param = Param(arg.arg, 'bytearray' if kind == 'ptr' else 'bytes')
                param.elem = element
                if default is not None:
                    self._refuse(path, default, '%s: a pointer parameter has no default' % node.name)
            elif self._callback_ref(path, ann, imported, module_names) is not None:
                param = Param(arg.arg, 'callback')
                param.callback = self._callback_ref(path, ann, imported, module_names)
                if default is not None:
                    self._refuse(path, default, '%s: a callback parameter has no default' % node.name)
            elif self._handle_ref(path, ann, imported, module_names) is not None:
                param = Param(arg.arg, 'c_void_p')
                param.handle = self._handle_ref(path, ann, imported, module_names)
                if default is not None:
                    self._refuse(path, default, '%s: a Handle parameter has no default' % node.name)
            else:
                name = self._ann_name(path, node, ann, imported, module_names, node.name)
                if name not in PARAM_ANN:
                    self._refuse(path, ann, '%s: `%s` cannot be a parameter type' % (node.name, name))
                param = Param(arg.arg, name)
                if default is not None:
                    try:
                        param.default = ast.literal_eval(default)
                    except (ValueError, SyntaxError):
                        self._refuse(path, default, '%s: a parameter default must be a literal' % node.name)
                    if type(param.default) not in (int, float, bool, str):
                        self._refuse(path, default, '%s: a parameter default must be an int, float, bool or str' % node.name)
                    param.has_default = True
            seen[arg.arg] = param
            decl.params.append(param)
        for p in decl.params:
            if p.length_of is not None:
                target = seen.get(p.length_of)
                if target is None or target.ann not in ('bytes', 'bytearray', 'c_const_void_p', 'c_mut_void_p'):
                    self._refuse(path, node, '%s: length(%r) must name a bytes or bytearray parameter' % (node.name, p.length_of))
        seen_default = False
        for p in decl.params:
            if p.length_of is not None:
                continue
            if p.has_default:
                seen_default = True
            elif seen_default:
                self._refuse(path, node, '%s: a parameter without a default follows one with a default' % node.name)
        if node.returns is None:
            self._refuse(path, node, '%s: a missing return annotation is refused (write `-> None` for void)' % node.name)
        if isinstance(node.returns, ast.Constant) and node.returns.value is None:
            decl.result = None
        elif self._callback_ref(path, node.returns, imported, module_names) is not None:
            self._refuse(path, node.returns, '%s: a callback cannot be a result: an AIL callback is valid only during the call '
                                             'that receives it\n  write instead: return a c_void_p' % node.name)
        elif self._handle_ref(path, node.returns, imported, module_names) is not None:
            decl.result_handle = self._handle_ref(path, node.returns, imported, module_names)
            decl.result = 'c_void_p'
        else:
            decl.result = self._ann_name(path, node, node.returns, imported, module_names, node.name)
            if decl.result not in RESULT_ANN:
                self._refuse(path, node.returns, '%s: `%s` cannot be a result type' % (node.name, decl.result))
            if decl.result == 'str':
                decl.result = 'c_char_p'
        if decl.check is not None and (decl.result is None or decl.result in ('c_double', 'c_float', 'c_bool', 'c_char_p', 'c_mut_char_p')):
            self._refuse(path, node, '%s: check= needs an integer or handle result' % node.name)
        if len(decl.params) > CB_MAX and decl.has_callbacks:
            self._refuse(path, node, '%s: a stub that takes a callback has at most %d parameters' % (node.name, CB_MAX))
        if decl.has_bytearray and decl.result in ('c_char_p', 'c_mut_char_p'):
            self._refuse(path, node, '%s: a str result together with a bytearray parameter is not supported' % node.name)
        body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                                              and (n.value.value is Ellipsis or isinstance(n.value.value, str)))]
        if body:
            self._refuse(path, body[0], '%s: an @extern stub has no body (write `...`)' % node.name)
        # `str` as a parameter means c_char_p
        for p in decl.params:
            if p.ann == 'str':
                p.ann = 'c_char_p'
        if decl.header is not None:
            decl.local_header = (path.parent / decl.header).is_file()
        return decl

    # ------------------------------------------------------------------ owned handles (F4)

    @staticmethod
    def _is_handle_call(node, imported, module_names):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id == 'Handle' and 'Handle' in imported
        return (isinstance(func, ast.Attribute) and func.attr == 'Handle' and isinstance(func.value, ast.Name)
                and func.value.id in module_names)

    def _handle_type(self, path, call, alias=None):
        """The HandleType of a `Handle("name", free="c_function")` call, made on first mention."""
        words = [a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        free = [k.value.value for k in call.keywords if k.arg == 'free' and isinstance(k.value, ast.Constant)
                and isinstance(k.value.value, str)]
        if len(words) != 1 or len(call.args) != 1 or len(free) != 1 or len(call.keywords) != 1 \
                or not words[0].isidentifier() or not free[0].isidentifier():
            self._refuse(path, call, 'Handle("name", free="c_function"): the name and the free function are string literals '
                                     'that are identifiers')
        key = (words[0], free[0])
        ht = self.handles.get(key)
        if ht is not None:
            if alias is not None and alias != ht.cls:
                self._refuse(path, call, 'Handle(%r, free=%r) is already declared as %s\n  write instead: use %s for this type'
                             % (key[0], key[1], ht.cls, ht.cls))
            return ht
        ht = HandleType(key[0], key[1], alias or 'Handle_%s' % key[0], call.lineno)
        self.handles[key] = ht
        return ht

    def _handle_alias(self, path, node, imported, module_names):
        """`Db = Handle("sqlite3", free="sqlite3_close")` at module level names the type; its class is written here."""
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            self._refuse(path, node, 'a Handle type is bound to one plain name: `Db = Handle("sqlite3", free="sqlite3_close")`')
        alias = node.targets[0].id
        ht = self._handle_type(path, node.value, alias)
        self.handle_aliases[alias] = (ht.name, ht.free)

    def _handle_ref(self, path, ann, imported, module_names):
        """The HandleType an annotation names (an alias or an inline `Handle(...)`), else None."""
        if isinstance(ann, ast.Name) and ann.id in self.handle_aliases:
            return self.handles[self.handle_aliases[ann.id]]
        if self._is_handle_call(ann, imported, module_names):
            return self._handle_type(path, ann)
        return None

    def _handle_class(self, ht, tag):
        """The AIL class that owns the pointer, written at the end of the file that first names the type."""
        ht.emitted = True
        c, name = ht.cls, ht.name
        return ['',
                'class %s:' % c,
                '    def __init__(self, p: int):',
                '        self._p = p',
                '',
                '    def close(self) -> None:',
                '        q = self._p',
                '        if q != 0:',
                '            self._p = 0',
                '            %s(q)' % ht.release,
                '',
                '    def __enter__(self) -> "%s":' % c,
                '        if self._p == 0:',
                '            raise ValueError("%s handle is closed")' % name,
                '        return self',
                '',
                '    def __exit__(self, kind, value, trace) -> bool:',
                '        self.close()',
                '        return False',
                '',
                '    @staticmethod',
                '    def adopt(buffer: bytearray) -> "%s":' % c,
                '        if len(buffer) != 8:',
                '            raise ValueError("adopt takes the bytearray(8) of a ptr(c_void_p) out-parameter")',
                '        q = %s(bytes(buffer))' % ht.adopt,
                '        for i in range(8):',
                '            buffer[i] = 0',
                '        return %s(q)' % ht.make,
                '',
                'def %s(p: int) -> "%s":' % (ht.make, c),
                '    h = %s(p)' % c,
                '    if p != 0:',
                '        %s(p)' % ht.reg,
                '    return h']

    def _refuse_handle_use(self, path, tree):
        """A Handle is not a number and not shared between threads: arithmetic on one and a parallel worker that
        takes one are refused by name. The values are followed by name inside each function (parameters annotated
        with a Handle type, results of the stubs that return one, `Type.adopt(...)`, copies of those)."""
        for d in self.decls:
            for p in d.params:
                if p.handle is not None and d.symbol == p.handle.free:
                    raise ModuleRefusal(d.path, d.line, 1, '%s calls %s, the free function of the %s Handle: the handle frees it '
                                        'itself, and a second free is a crash\n  write instead: call %s.close() and leave out '
                                        'this stub' % (d.name, d.symbol, p.handle.name, p.name))
        classes = set(self.handle_aliases) | {ht.cls for ht in self.handles.values()}
        makers ={d.name for d in self.decls if d.result_handle is not None}
        takers = {d.name for d in self.decls if any(p.handle is not None for p in d.params)}

        def ann_is_handle(a):
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                return a.value in classes
            return isinstance(a, ast.Name) and a.id in classes

        def is_handle(e, names):
            if isinstance(e, ast.Name):
                return e.id in names
            if isinstance(e, ast.Call):
                f = e.func
                return (isinstance(f, ast.Name) and f.id in makers) or (
                    isinstance(f, ast.Attribute) and f.attr == 'adopt' and isinstance(f.value, ast.Name) and f.value.id in classes)
            return False

        def scope_nodes(body):
            stack = list(reversed(body))
            while stack:
                node = stack.pop()
                yield node
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                stack.extend(reversed(list(ast.iter_child_nodes(node))))

        def arithmetic(node, what):
            self._refuse(path, node, 'arithmetic on the Handle %s: a handle is an owned object, not an address\n'
                                     '  write instead: pass the handle to the stub that needs it, and compute with the plain '
                                     'ints that stubs return' % what)

        def parallel(node, what):
            self._refuse(path, node, 'the Handle %s is passed into a parallel worker: a handle has one owner and its free '
                                     'function runs once\n  write instead: call the stubs that take the handle in the calling '
                                     'thread, and give the worker plain ints, bytes or bytearrays' % what)

        def mentions(node, names):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and sub.id in names:
                    return sub.id
            return None

        functions = {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

        def scan(body, names, args=None):
            names = set(names)
            if args is not None:
                for a in args.posonlyargs + args.args + args.kwonlyargs:
                    if a.annotation is not None and ann_is_handle(a.annotation):
                        names.add(a.arg)
            nodes = list(scope_nodes(body))
            for _ in range(2):
                for n in nodes:
                    if isinstance(n, ast.Assign) and is_handle(n.value, names):
                        names.update(t.id for t in n.targets if isinstance(t, ast.Name))
                    elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and (
                            ann_is_handle(n.annotation) or (n.value is not None and is_handle(n.value, names))):
                        names.add(n.target.id)
                    elif isinstance(n, (ast.With, ast.AsyncWith)):
                        for item in n.items:
                            if isinstance(item.optional_vars, ast.Name) and is_handle(item.context_expr, names):
                                names.add(item.optional_vars.id)
            for n in nodes:
                if isinstance(n, ast.BinOp):
                    for side in (n.left, n.right):
                        if is_handle(side, names):
                            arithmetic(n, ast.unparse(side))
                elif isinstance(n, ast.UnaryOp) and not isinstance(n.op, ast.Not) and is_handle(n.operand, names):
                    arithmetic(n, ast.unparse(n.operand))
                elif isinstance(n, ast.AugAssign):
                    if is_handle(n.target, names) or is_handle(n.value, names):
                        arithmetic(n, ast.unparse(n.target if is_handle(n.target, names) else n.value))
                elif isinstance(n, ast.For) and isinstance(n.iter, ast.Call) and isinstance(n.iter.func, ast.Name) \
                        and n.iter.func.id in PARALLEL_LOOPS:
                    found = mentions(ast.Module(body=n.body, type_ignores=[]), names)
                    if found:
                        parallel(n, found)
                elif isinstance(n, ast.Call):
                    f = n.func
                    word = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                    if word in PARALLEL_CALLS:
                        parts = list(n.args) + [k.value for k in n.keywords]
                        for part in parts:
                            found = mentions(part, names)
                            if found:
                                parallel(n, found)
                            for sub in ast.walk(part):
                                target = functions.get(sub.id) if isinstance(sub, ast.Name) else None
                                if target is not None and (sub.id in takers or any(
                                        a.annotation is not None and ann_is_handle(a.annotation)
                                        for a in target.args.posonlyargs + target.args.args + target.args.kwonlyargs)):
                                    parallel(n, '(an argument of %s)' % sub.id)
            for n in nodes:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scan(n.body, names, n.args)
                elif isinstance(n, ast.ClassDef):
                    scan(n.body, names)

        scan(tree.body, ())

    # ------------------------------------------------------------------ callbacks (F7)

    @staticmethod
    def _is_named_call(node, word, imported, module_names):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id == word and word in imported
        return (isinstance(func, ast.Attribute) and func.attr == word and isinstance(func.value, ast.Name)
                and func.value.id in module_names)

    def _callback_ref(self, path, ann, imported, module_names):
        """The CallbackType an annotation names (an alias or an inline `callback(...)`), else None."""
        if isinstance(ann, ast.Name) and ann.id in self.cb_aliases:
            return self.cb_aliases[ann.id]
        if self._is_named_call(ann, 'callback', imported, module_names):
            return self._callback_type(path, ann, imported, module_names)
        return None

    def _callback_type(self, path, call, imported, module_names):
        """`callback(ret, arg, ..., on_error=value)`: the C function pointer type of a stub parameter."""
        text = ast.unparse(call)
        if not call.args:
            self._refuse(path, call, '%s: callback(result C type or None, argument C types...)' % text)
        options = {}
        for keyword in call.keywords:
            if keyword.arg == 'retain':
                self._refuse(path, keyword.value, '%s: retain= declares a callback that C stores and calls after the call '
                             'returns, and an AIL callback is valid only during the call that receives it\n  write instead: '
                             'pass the callback to a C function that calls it before it returns (qsort, bsearch, '
                             'sqlite3_exec), and keep what C must remember as data (a c_void_p context)' % text)
            if keyword.arg == 'threads':
                self._refuse(path, keyword.value, '%s: threads= declares a callback that C calls from another thread, and an '
                             'AIL callback runs only on the thread that made the C call\n  write instead: make the C call '
                             'from the thread that runs the callback, or let C queue the work and read the results after '
                             'the call with plain stubs' % text)
            if keyword.arg != 'on_error':
                self._refuse(path, keyword.value, '%s: unknown callback option %s (only on_error= is an option)' % (text, keyword.arg))
            options[keyword.arg] = keyword.value
        first = call.args[0]
        if isinstance(first, ast.Constant) and first.value is None:
            ret = None
        else:
            ret = self._ann_name(path, call, first, imported, module_names, text)
            if ret not in CB_RESULT_ANN:
                self._refuse(path, first, '%s: `%s` cannot be a callback result (None, an integer type, c_double, '
                             'c_float, c_bool or c_void_p)' % (text, ret))
        args = []
        for node in call.args[1:]:
            if self._is_named_call(node, 'cptr', imported, module_names) or self._is_named_call(node, 'ptr', imported, module_names):
                word = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                if word == 'ptr':
                    self._refuse(path, node, '%s: ptr(T) cannot be a callback argument: the callback cannot write through it\n'
                                 '  write instead: cptr(T), which gives the callback the value it points at' % text)
                if len(node.args) != 1 or node.keywords:
                    self._refuse(path, node, '%s: cptr(element C type)' % text)
                element = self._ann_name(path, call, node.args[0], imported, module_names, text)
                if element not in INTS and element not in ('c_double', 'c_float', 'c_bool'):
                    self._refuse(path, node, '%s: cptr in a callback takes an integer, float or bool C type' % text)
                args.append(CbArg('cptr', element))
            elif self._is_named_call(node, 'array', imported, module_names):
                if len(node.args) != 2 or node.keywords or not isinstance(node.args[1], ast.Constant) \
                        or type(node.args[1].value) is not int:
                    self._refuse(path, node, '%s: array(element C type, index of the count argument)' % text)
                element = self._ann_name(path, call, node.args[0], imported, module_names, text)
                if element not in CB_ELEM_ANN:
                    self._refuse(path, node, '%s: array takes an integer, float, bool or c_char_p element type' % text)
                args.append(CbArg('array', element, node.args[1].value))
            else:
                name = self._ann_name(path, call, node, imported, module_names, text)
                if name not in CB_ARG_ANN:
                    self._refuse(path, node, '%s: `%s` cannot be a callback argument' % (text, name))
                args.append(CbArg('value', name))
        if len(args) > CB_MAX:
            self._refuse(path, call, '%s: a callback takes at most %d arguments' % (text, CB_MAX))
        for a in args:
            if a.kind == 'array' and not (0 <= a.count < len(args) and args[a.count].kind == 'value' and args[a.count].ann in INTS):
                self._refuse(path, call, '%s: array(T, %d) must name an integer argument (0-based)' % (text, a.count))
        on_error = None
        if ret is None:
            if 'on_error' in options:
                self._refuse(path, options['on_error'], '%s: a callback without a result has no on_error' % text)
        else:
            if 'on_error' not in options:
                self._refuse(path, call, '%s needs on_error=<value>: the value C gets back when the callback raises (the '
                             'exception is raised again when the C call returns)\n  write instead: %s'
                             % (text, text[:-1] + ', on_error=%s)' % {'c_double': '0.0', 'c_float': '0.0', 'c_bool': 'False'}.get(ret, '0')))
            try:
                on_error = ast.literal_eval(options['on_error'])
            except (ValueError, SyntaxError):
                on_error = None
            kind = python_type(ret)
            ok = (type(on_error) is int if kind == 'int' else type(on_error) is bool if kind == 'bool'
                  else type(on_error) in (int, float))
            if ok and ret in INTS:
                bits, signed = INTS[ret][2], INTS[ret][3]
                low, high = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
                ok = low <= on_error <= high
            elif ok and ret == 'c_void_p':
                ok = 0 <= on_error < (1 << 64)
            if not ok:
                self._refuse(path, options['on_error'], '%s: on_error must be a %s literal that fits %s' % (text, kind, ret))
        return CallbackType(ret, args, on_error, text)

    def _callback_sites(self, path, tree, decls, lines, tag):
        """Each call of a stub that takes a callback names a module-level def; the call is rewritten (in `lines`, columns
        move, lines do not) to the wrapper made for that def. Everything else that would hand C a callback it cannot
        call safely is refused by name."""
        stubs = {d.name: d for d in decls if d.has_callbacks}
        module_defs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        # functions that make such a call, directly or through each other: never in a parallel worker
        users = set()
        while True:
            more = {f.name for f in functions if f.name not in users and f.name not in stubs and any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and (n.func.id in stubs or n.func.id in users)
                for n in ast.walk(f))}
            if not more:
                break
            users |= more

        def parallel(node, what):
            self._refuse(path, node, '%s is passed into a parallel worker: a C call that takes a callback runs the callback '
                         'on the thread that made the call, between its own steps\n  write instead: make the C call that '
                         'takes the callback in the calling thread, and give the worker plain data' % what)

        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                word = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                if word in PARALLEL_CALLS:
                    for part in list(n.args) + [k.value for k in n.keywords]:
                        for sub in ast.walk(part):
                            if isinstance(sub, ast.Name) and (sub.id in stubs or sub.id in users):
                                parallel(n, sub.id if sub.id in stubs else '%s (which makes a C call that takes a callback)' % sub.id)
            elif isinstance(n, ast.For) and isinstance(n.iter, ast.Call) and isinstance(n.iter.func, ast.Name) \
                    and n.iter.func.id in PARALLEL_LOOPS:
                for sub in ast.walk(ast.Module(body=n.body, type_ignores=[])):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and (sub.func.id in stubs or sub.func.id in users):
                        parallel(sub, 'a call of %s in a par_range body' % sub.func.id)

        def local_names(fn):
            """Names a function (or lambda) binds itself: parameters, assignments, nested defs and classes, imports."""
            names = {}
            a = fn.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x is not None]:
                names[arg.arg] = 'parameter'
            stack = list(fn.body) if isinstance(fn.body, list) else [fn.body]
            declared = set()
            while stack:
                node = stack.pop()
                if isinstance(node, (ast.Global, ast.Nonlocal)):
                    declared.update(node.names)
                    continue
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names[node.name] = 'def' if not isinstance(node, ast.ClassDef) else 'class'
                    continue
                if isinstance(node, ast.Lambda):
                    continue
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    names.setdefault(node.id, 'variable')
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        names.setdefault((alias.asname or alias.name).split('.')[0], 'variable')
                stack.extend(ast.iter_child_nodes(node))
            for name in declared:
                names.pop(name, None)
            return names

        edits = []
        handled = set()

        def visit(node, scopes):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                for d in getattr(node, 'decorator_list', []):
                    visit(d, scopes)
                inner = scopes + [local_names(node)]
                for child in (node.body if isinstance(node.body, list) else [node.body]):
                    visit(child, inner)
                for default in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                    visit(default, scopes)
                return
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in stubs \
                    and not any(node.func.id in scope for scope in scopes):
                handled.add(id(node.func))
                self._callback_call(path, node, stubs[node.func.id], scopes, module_defs, stubs, edits, tag)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in stubs and id(node) not in handled \
                    and not any(node.id in scope for scope in scopes):
                self._refuse(path, node, '%s takes a callback, so it is called by name with the callback written in the call; '
                             'it is not a value\n  write instead: a def that calls %s(...) directly, and use that def'
                             % (node.id, node.id))
            for child in ast.iter_child_nodes(node):
                visit(child, scopes)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in stubs:
                continue
            visit(node, [])
        # apply right to left on each line; ast columns count UTF-8 bytes
        for lineno, start, end, text in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
            data = lines[lineno - 1].encode('utf-8')
            lines[lineno - 1] = (data[:start] + text.encode('utf-8') + data[end:]).decode('utf-8')

    def _callback_call(self, path, call, d, scopes, module_defs, stubs, edits, tag):
        """One call of a stub that takes callbacks: check each callback argument and rewrite the call."""
        visible = [p for p in d.params if p.length_of is None]
        bound = {}
        for index, arg in enumerate(call.args):
            if isinstance(arg, ast.Starred):
                self._refuse(path, arg, '%s takes a callback: write its arguments out (no *args)' % d.name)
            if index < len(visible):
                bound[visible[index].name] = arg
        for keyword in call.keywords:
            if keyword.arg is None:
                self._refuse(path, keyword.value, '%s takes a callback: write its arguments out (no **kwargs)' % d.name)
            bound[keyword.arg] = keyword.value
        names = []
        for p in visible:
            if p.callback is None:
                continue
            node = bound.get(p.name)
            if node is None:
                self._refuse(path, call, '%s: the callback %s is missing' % (d.name, p.name))
            names.append(self._callback_def(path, d, p, node, scopes, module_defs, stubs))
            edits.append((node.lineno, node.col_offset, node.end_col_offset, '0'))
        key = tuple(names)
        if key not in d.variants:
            d.variants[key] = 'ffi_%s_%s__via_%s' % (tag, d.name, '__'.join(names))
        edits.append((call.func.lineno, call.func.col_offset, call.func.end_col_offset, d.variants[key]))

    def _callback_def(self, path, d, p, node, scopes, module_defs, stubs):
        """The name of the module-level def passed as the callback p; anything else is refused by name."""
        cb = p.callback
        hint = '\n  write instead: a module-level `%s` (state it needs goes in module-level variables or a c_void_p ' \
               'context argument), and pass its name' % cb.signature('name')
        where = '%s: the callback %s' % (d.name, p.name)
        if isinstance(node, ast.Lambda):
            self._refuse(path, node, '%s is a lambda; C calls a callback through a fixed C function, and a lambda is a '
                         'value made at run time%s' % (where, hint))
        if isinstance(node, ast.Attribute):
            self._refuse(path, node, '%s is the method %s; a method needs its object, and C passes only the C '
                         'arguments%s' % (where, ast.unparse(node), hint))
        if not isinstance(node, ast.Name):
            self._refuse(path, node, '%s must be the name of a module-level def, not `%s`%s' % (where, ast.unparse(node), hint))
        for scope in reversed(scopes):
            if node.id in scope:
                if scope[node.id] == 'def':
                    self._refuse(path, node, '%s is %s, a def inside a function (a closure): it can read that '
                                 'function\'s variables, which C cannot pass%s' % (where, node.id, hint))
                self._refuse(path, node, '%s is the local %s %s; a callback is a module-level def, known when '
                             'compiling%s' % (where, scope[node.id], node.id, hint))
        fn = module_defs.get(node.id)
        if fn is None or node.id in stubs:
            self._refuse(path, node, '%s: %s is not a module-level def%s' % (where, node.id, hint))
        a = fn.args
        problem = None
        if isinstance(fn, ast.AsyncFunctionDef):
            problem = 'is async'
        elif fn.decorator_list:
            problem = 'has a decorator'
        elif a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs:
            problem = 'has *args, **kwargs or keyword-only parameters'
        elif len(a.args) != len(cb.args):
            problem = 'takes %d parameters and the callback type %d' % (len(a.args), len(cb.args))
        else:
            for arg, want in zip(a.args, cb.args):
                if arg.annotation is None or ast.unparse(arg.annotation).replace(' ', '') != want.python().replace(' ', ''):
                    problem = 'annotates %s as %s, and the C argument is %s' % (
                        arg.arg, '<nothing>' if arg.annotation is None else ast.unparse(arg.annotation), want.python())
                    break
            else:
                ret = fn.returns
                got = None if ret is None else 'None' if isinstance(ret, ast.Constant) and ret.value is None else ast.unparse(ret)
                if got != cb.python_result():
                    problem = 'has the result annotation %s, and the C result is %s' % (got or '<nothing>', cb.python_result())
        if problem is not None:
            self._refuse(path, node, '%s: %s %s; a callback is a fully C-typed def\n  write instead: `%s`'
                         % (where, node.id, problem, cb.signature(node.id)))
        return node.id

    # ------------------------------------------------------------------ AIL wrappers

    def _wrapper(self, d):
        out = ['']
        sig = []
        for p in d.params:
            if p.length_of is not None:
                continue
            text = '%s: %s' % (p.name, p.handle.cls if p.handle is not None else python_type(p.ann))
            if p.has_default:
                text += ' = %r' % (p.default,)
            sig.append(text)
        ret = d.result_handle.cls if d.result_handle is not None else {None: 'None'}.get(d.result) or python_type(d.result)
        out.append('def %s(%s) -> %s:' % (d.name, ', '.join(sig), ret))
        args = []
        for p in d.params:
            if p.length_of is not None:
                target = next(q for q in d.params if q.name == p.length_of)
                size = elem_info(target.elem)[1] if target.elem is not None else 1
                args.append('len(%s)' % p.length_of if size == 1 else 'len(%s) // %d' % (p.length_of, size))
            elif p.ann in ('bytearray', 'c_mut_void_p'):
                args.append('bytes(%s)' % p.name)
            elif p.handle is not None:
                args.append('%s._p' % p.name)
            else:
                args.append(p.name)
        call = '%s(%s)' % (d.export, ', '.join(args))
        for p in d.params:
            if p.handle is not None:
                out.append('    if %s._p == 0:' % p.name)
                out.append('        raise ValueError("%s handle is closed")' % p.handle.name)
        for p in d.params:
            if p.elem is not None and elem_info(p.elem)[1] > 1:
                out.append('    if len(%s) %% %d != 0:' % (p.name, elem_info(p.elem)[1]))
                out.append('        raise ValueError("%s: %s must hold a whole number of %s")' % (d.name, p.name, p.elem))
        if d.has_bytearray:
            out.append('    ffi_r = ' + call)
            out.append('    ffi_o = 0')
            for p in d.params:
                if p.ann in ('bytearray', 'c_mut_void_p'):
                    out.append('    ffi_o = ffi_put_%s(%s, ffi_r, ffi_o)' % (d.tag, p.name))
            if d.result is None:
                return out
            out.append('    ffi_rc = %s__rc()' % d.export)
        elif d.result is None:
            out.append('    ' + call)
            return out
        else:
            out.append('    ffi_rc = ' + call)
        out.extend(self._result_lines(d))
        return out

    @staticmethod
    def _result_lines(d):
        """The wrapper's lines after `ffi_rc` holds the C result: the check= failure and the conversion."""
        out = []
        if d.check is not None:
            out.append('    if ffi_rc %s:' % CHECKS[d.check])
            if d.errno:
                out.append('        ffi_e = ffi_%s__errno()' % d.tag)
                if d.exc == 'OSError':
                    # CPython's shim raises OSError(err, os.strerror(err)): `.errno`, `.strerror`, the
                    # errno-picked subclass and str(e) == "[Errno N] text"
                    out.append('        raise OSError(ffi_e, ffi_%s__strerror(ffi_e))' % d.tag)
                else:
                    out.append('        raise %s("[Errno %%d] %%s" %% (ffi_e, ffi_%s__strerror(ffi_e)))' % (d.exc, d.tag))
            else:
                out.append('        raise %s("%s failed with %%d" %% ffi_rc)' % (d.exc, d.name))
        if d.result_handle is not None:
            out.append('    return %s(ffi_rc)' % d.result_handle.make)
        else:
            out.append('    return ffi_rc != 0' if d.result == 'c_bool' else '    return ffi_rc')
        return out

    def _cb_wrapper(self, d, wrapper, names):
        """The AIL function that a call of a callback-taking stub was rewritten to, for one choice of callback defs.
        It starts the C call, serves each callback C makes (event k: the k-th callback parameter) and finishes the
        call in `finally`, so an exception from a callback is raised after C has returned."""
        t = d.tag
        out = ['']
        sig, args = [], []
        for p in d.params:
            if p.length_of is not None:
                target = next(q for q in d.params if q.name == p.length_of)
                size = elem_info(target.elem)[1] if target.elem is not None else 1
                args.append('len(%s)' % p.length_of if size == 1 else 'len(%s) // %d' % (p.length_of, size))
                continue
            if p.callback is not None:
                sig.append('%s: int' % p.name)          # the call site passes 0 here
                continue
            text = '%s: %s' % (p.name, p.handle.cls if p.handle is not None else python_type(p.ann))
            if p.has_default:
                text += ' = %r' % (p.default,)
            sig.append(text)
            if p.ann in ('bytearray', 'c_mut_void_p'):
                args.append('bytes(%s)' % p.name)
            elif p.handle is not None:
                args.append('%s._p' % p.name)
            else:
                args.append(p.name)
        ret = d.result_handle.cls if d.result_handle is not None else {None: 'None'}.get(d.result) or python_type(d.result)
        out.append('def %s(%s) -> %s:' % (wrapper, ', '.join(sig), ret))
        for p in d.params:
            if p.handle is not None:
                out.append('    if %s._p == 0:' % p.name)
                out.append('        raise ValueError("%s handle is closed")' % p.handle.name)
        for p in d.params:
            if p.elem is not None and elem_info(p.elem)[1] > 1:
                out.append('    if len(%s) %% %d != 0:' % (p.name, elem_info(p.elem)[1]))
                out.append('        raise ValueError("%s: %s must hold a whole number of %s")' % (d.name, p.name, p.elem))
        out.append('    ffi_ev = %s__start(%s)' % (d.export, ', '.join(args)))
        out.append('    try:')
        out.append('        while ffi_ev != 0:')
        slots = [p for p in d.params if p.callback is not None]
        for slot, (p, fn) in enumerate(zip(slots, names), 1):
            cb = p.callback
            values, lists = [], []
            for k, a in enumerate(cb.args):
                kind = python_type(a.ann) if a.ann != 'c_const_void_p' else 'int'
                if a.kind == 'array':
                    reader = {'str': 'cbas', 'float': 'cbaf'}.get(kind, 'cbai')
                    item = 'ffi_%s__%s(%d, ffi_i)' % (t, reader, k)
                    if kind == 'bool':
                        item += ' != 0'
                    # bound to a name first: a comprehension is not an argument everywhere in the typed subset
                    lists.append('                ffi_l%d_%d = [%s for ffi_i in range(ffi_%s__cbn(%d, %d))]' % (slot, k, item, t, k, a.count))
                    values.append('ffi_l%d_%d' % (slot, k))
                else:
                    reader = {'str': 'cbs', 'float': 'cbf'}.get(kind, 'cbi')
                    values.append('ffi_%s__%s(%d)%s' % (t, reader, k, ' != 0' if kind == 'bool' else ''))
            call = '%s(%s)' % (fn, ', '.join(values))
            out.append('            %s ffi_ev == %d:' % ('if' if slot == 1 else 'elif', slot))
            out.extend(lists)
            if cb.ret is None:
                out.append('                ' + call)
                out.append('                ffi_ev = ffi_%s__resume_v()' % t)
            elif cb.ret == 'c_bool':
                out.append('                ffi_ev = ffi_%s__resume_i(1 if %s else 0)' % (t, call))
            elif cb.ret in ('c_double', 'c_float'):
                out.append('                ffi_ev = ffi_%s__resume_f(%s)' % (t, call))
            else:
                v = 'ffi_v%d' % slot
                out.append('                %s = %s' % (v, call))
                if cb.ret == 'c_void_p' or (cb.ret in INTS and not INTS[cb.ret][3] and INTS[cb.ret][2] == 64):
                    test = '%s < 0' % v
                elif INTS[cb.ret][2] == 64:
                    test = None
                else:
                    bits, signed = INTS[cb.ret][2], INTS[cb.ret][3]
                    low, high = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
                    test = '%s < %d or %s > %d' % (v, low, v, high)
                if test is not None:
                    out.append('                if %s:' % test)
                    out.append('                    raise OverflowError("%s: the result of %s does not fit %s")' % (d.name, fn, cb.ret))
                out.append('                ffi_ev = ffi_%s__resume_i(%s)' % (t, v))
        out.append('    finally:')
        if d.has_bytearray:
            out.append('        ffi_r = %s__finish()' % d.export)
            out.append('        ffi_o = 0')
            for p in d.params:
                if p.ann in ('bytearray', 'c_mut_void_p'):
                    out.append('        ffi_o = ffi_put_%s(%s, ffi_r, ffi_o)' % (t, p.name))
        else:
            out.append('        %s__finish()' % d.export)
        if d.result is None:
            return out
        out.append('    ffi_rc = %s__%s()' % (d.export, 'rcs' if d.result in ('c_char_p', 'c_mut_char_p') else 'rc'))
        out.extend(self._result_lines(d))
        return out

    # ------------------------------------------------------------------ the C object

    def symbols(self):
        """The C names the adapter object refers to; the AIL program must not define functions of these names."""
        return sorted({d.symbol for d in self.decls})

    def listing(self):
        """The `ail check --ffi` rows."""
        rows = []
        for d in self.decls:
            rows.append(dict(
                name=d.name, path=d.path, line=d.line, lib=d.lib, header=d.header, symbol=d.symbol,
                prototype=d.prototype(),
                header_checked=d.header is not None and not d.trust,
                trusted_declaration=d.header is None or d.trust,
                writes=[p.name for p in d.params if p.ann in ('bytearray', 'c_mut_void_p')],
                errors=None if d.check is None else dict(check=d.check, errno=d.errno, exception=d.exc),
                pointer_arguments=[p.name for p in d.params if p.ann in ('bytes', 'bytearray', 'c_const_void_p', 'c_mut_void_p', 'c_char_p', 'c_mut_char_p', 'c_void_p')]))
            callbacks = [dict(parameter=p.name, type=p.callback.text) for p in d.params if p.callback is not None]
            if callbacks:
                rows[-1]['callbacks'] = callbacks
            owned = [p.name for p in d.params if p.handle is not None]
            if owned or d.result_handle is not None:
                rows[-1]['owned_handles'] = dict(parameters=owned, result=None if d.result_handle is None else d.result_handle.name)
        return rows

    def build(self, cli, env=None, c_api_name=None):
        """Build the adapter object; returns its path, or None when no stub was declared.
        `c_api_name` builds it as a dependency of a C library (`compile --lib`, c_api.py)."""
        if not self.decls:
            return None
        if self.workdir is None:
            import tempfile
            self.workdir = Path(tempfile.mkdtemp(prefix='ail-ffi-'))
            self._owned = True
        work = self.workdir
        headers_local, headers_system = {}, []
        for d in self.decls:
            if d.header is None:
                continue
            if d.local_header:
                headers_local.setdefault(d.header, Path(d.directory) / d.header)
            elif d.header not in headers_system:
                headers_system.append(d.header)
        for name, source in headers_local.items():
            if '/' in name or not name.endswith(('.h', '.inc')):
                raise ValueError('a local FFI header must sit beside its declaration: ' + name)
            shutil.copyfile(source, work / name)
        sources = {}
        for d in self.decls:
            for name in d.sources:
                sources.setdefault(name, Path(d.directory) / name)
        for name, source in sources.items():
            if not source.is_file():
                raise ValueError('FFI source file not found: ' + str(source))
            shutil.copyfile(source, work / name)
        code = ['#ifndef _DEFAULT_SOURCE', '#define _DEFAULT_SOURCE 1', '#endif',      # POSIX and BSD declarations (gmtime_r, timegm) under -std=c11
                '#include <stddef.h>', '#include <stdint.h>', '#include <errno.h>', '#include <string.h>',
                '#include <sys/types.h>',
                '#include <stdlib.h>']
        code += ['#include <%s>' % h for h in headers_system]
        code += ['#include "%s"' % h for h in headers_local]
        code.append('static int ffi_last_errno;')
        code.append('static const unsigned char ffi_empty[1] = {0};')
        code.append('static unsigned char *ffi_scratch; static size_t ffi_scratch_cap;')
        callbacks = [d for d in self.decls if d.has_callbacks]
        if callbacks:
            code.append(CB_RUNTIME)
        functions = {}
        tags = []
        extern_decls = []
        asserts = []
        bodies = []
        tag_seen = set()
        for d in self.decls:
            if d.tag not in tag_seen:
                tag_seen.add(d.tag)
                tags.append(d.tag)
            # real prototype: declared by the header, or trusted
            if d.header is None:
                extern_decls.append('extern %s;' % d.prototype())
            ptypes = ', '.join(d.c_params()) or 'void'
            ret = 'void' if d.result is None else result_ctype(d.result)
            if not d.trust:
                asserts.append('_Static_assert(_Generic(&%s, %s (*)(%s): 1, default: 0), "ail_ffi: the declaration of %s does not match its C prototype");'
                               % (d.symbol, ret, ptypes, d.symbol))
            if any(t in ('c_long', 'c_ulong') for t in [p.ann for p in d.params] + [d.result]):
                asserts.append('_Static_assert(sizeof(long) == 8, "ail_ffi: c_long/c_ulong need a 64 bit long");')
            if any(t == 'c_size_t' or t == 'c_ssize_t' for t in [p.ann for p in d.params] + [d.result]):
                asserts.append('_Static_assert(sizeof(size_t) == 8, "ail_ffi: c_size_t needs a 64 bit size_t");')
            if d.has_callbacks:
                inner = [a.ann for p in d.params if p.callback is not None for a in p.callback.args] + \
                        [p.callback.ret for p in d.params if p.callback is not None]
                if any(t in ('c_long', 'c_ulong') for t in inner):
                    asserts.append('_Static_assert(sizeof(long) == 8, "ail_ffi: c_long/c_ulong need a 64 bit long");')
                if any(t in ('c_size_t', 'c_ssize_t') for t in inner):
                    asserts.append('_Static_assert(sizeof(size_t) == 8, "ail_ffi: c_size_t needs a 64 bit size_t");')
                self._emit_cb(d, callbacks.index(d) + 1, functions, bodies)
            else:
                self._emit(d, functions, bodies)
        for tag in tags:
            name = 'ffi_%s__errno' % tag
            functions[name] = dict(symbol=name, params=[], result='int')
            bodies.append('int64_t %s(void) { return ffi_last_errno; }' % name)
            name = 'ffi_%s__strerror' % tag
            functions[name] = dict(symbol=name, params=[['code', 'int']], result='str')
            bodies.append('ail_c_utf8_view %s(int64_t code) { const char *s = strerror((int)code); return (ail_c_utf8_view){(const unsigned char *)s, strlen(s)}; }' % name)
            if any(d.tag == tag for d in callbacks):
                self._emit_cb_access(tag, functions, bodies)
        owned = [ht for ht in self.handles.values() if ht.emitted]
        if owned:
            # F4: the pointers that Handle objects own are listed here, so what is still open when the program
            # ends is freed (newest first) and close() frees one exactly once
            extern_decls.append('#if defined(__APPLE__)\n#define FFI_SYM(x) "_" x\n#else\n#define FFI_SYM(x) x\n#endif')
            bodies.append('typedef struct { void *p; void (*free)(void *); } ffi_owned_entry;\n'
                          'static ffi_owned_entry *ffi_owned_v; static size_t ffi_owned_n, ffi_owned_cap; static int ffi_owned_hooked;\n'
                          'static void ffi_owned_all(void) {\n'
                          '    while (ffi_owned_n) { ffi_owned_entry e = ffi_owned_v[--ffi_owned_n]; e.free(e.p); }\n'
                          '    free(ffi_owned_v); ffi_owned_v = NULL; ffi_owned_cap = 0;\n'
                          '}\n'
                          'static void ffi_owned_add(void *p, void (*fn)(void *)) {\n'
                          '    if (ffi_owned_n == ffi_owned_cap) {\n'
                          '        size_t cap = ffi_owned_cap ? ffi_owned_cap * 2 : 8;\n'
                          '        ffi_owned_entry *grown = realloc(ffi_owned_v, cap * sizeof *grown); if (!grown) abort();\n'
                          '        ffi_owned_v = grown; ffi_owned_cap = cap;\n'
                          '    }\n'
                          '    if (!ffi_owned_hooked) { ffi_owned_hooked = 1; atexit(ffi_owned_all); }\n'
                          '    ffi_owned_v[ffi_owned_n].p = p; ffi_owned_v[ffi_owned_n].free = fn; ffi_owned_n++;\n'
                          '}\n'
                          'static void ffi_owned_release(void *p, void (*fn)(void *)) {\n'
                          '    for (size_t i = ffi_owned_n; i-- > 0;) {\n'
                          '        if (ffi_owned_v[i].p == p) {\n'
                          '            memmove(ffi_owned_v + i, ffi_owned_v + i + 1, (ffi_owned_n - i - 1) * sizeof *ffi_owned_v);\n'
                          '            ffi_owned_n--;\n'
                          '            break;\n'
                          '        }\n'
                          '    }\n'
                          '    fn(p);\n'
                          '}')
            for ht in owned:
                fn = 'ffi_free_%s' % ht.reg
                extern_decls.append('extern void %s(void *) __asm__(FFI_SYM("%s"));' % (fn, ht.free))
                functions[ht.reg] = dict(symbol=ht.reg, params=[['p', 'int']], result='void')
                bodies.append('void %s(int64_t p) { ffi_owned_add((void *)(intptr_t)p, %s); }' % (ht.reg, fn))
                functions[ht.release] = dict(symbol=ht.release, params=[['p', 'int']], result='void')
                bodies.append('void %s(int64_t p) { ffi_owned_release((void *)(intptr_t)p, %s); }' % (ht.release, fn))
                functions[ht.adopt] = dict(symbol=ht.adopt, params=[['b', 'borrowed_bytes']], result='int')
                bodies.append('int64_t %s(const unsigned char *b, size_t b_n) {\n'
                              '    void *p = NULL;\n    if (b_n >= sizeof p) memcpy(&p, b, sizeof p);\n'
                              '    return (int64_t)(intptr_t)p;\n}' % ht.adopt)
        # the per-declaration helpers must be exported under the declaration's own tag
        source ='\n'.join(code + extern_decls + sorted(set(asserts)) + bodies) + '\n'
        interface = dict(version=1, functions=functions)
        if headers_local:
            interface['headers'] = sorted(headers_local)
        if sources:
            interface['sources'] = sorted(sources)
        (work / 'ffi_adapter.c').write_text(source, encoding='utf8')
        (work / 'ffi_adapter.json').write_text(json.dumps(interface, indent=1), encoding='utf8')
        out = work / 'ffi_adapter.o'
        run_env = dict(os.environ if env is None else env)
        result = subprocess.run([sys.executable, '-B', str(cli), 'compile-c', str(work / 'ffi_adapter.c'),
                                 '--interface', str(work / 'ffi_adapter.json'), '-o', str(out),
                                 *([] if c_api_name is None else ['--c-api-name', c_api_name])],
                                capture_output=True, text=True, timeout=300, env=run_env)
        if result.returncode:
            raise ValueError('FFI adapter build failed:\n' + (result.stderr or result.stdout)[-3000:])
        self.link_args = self._link_args()
        return out

    def _emit(self, d, functions, bodies):
        """The interface entry and the C wrapper function of one declaration."""
        params, c_params, call_args, pre, post = [], [], [], [], []
        bytearrays = []
        for index, p in enumerate(d.params):
            n = 'p%d' % index
            if p.length_of is not None:
                kind = INTS[p.length_type][1]
                params.append([n, kind])
                c_params.append('%s %s' % (NATIVE[kind], n))
                call_args.append('(%s)%s' % (INTS[p.length_type][0], n))
            elif p.ann in INTS:
                kind = INTS[p.ann][1]
                params.append([n, kind])
                c_params.append('%s %s' % (NATIVE[kind], n))
                call_args.append('(%s)%s' % (INTS[p.ann][0], n))
            elif p.ann == 'c_bool':
                params.append([n, 'bool'])
                c_params.append('_Bool %s' % n)
                call_args.append(n)
            elif p.ann == 'c_double':
                params.append([n, 'float'])
                c_params.append('double %s' % n)
                call_args.append(n)
            elif p.ann == 'c_float':
                params.append([n, 'float32'])
                c_params.append('float %s' % n)
                call_args.append(n)
            elif p.ann in ('c_char_p', 'c_mut_char_p'):
                params.append([n, 'cstr'])
                c_params.append('const char *%s' % n)
                call_args.append(n if p.ann == 'c_char_p' else '(char *)%s' % n)
            elif p.ann == 'c_void_p':
                params.append([n, 'int'])
                c_params.append('int64_t %s' % n)
                call_args.append('(void *)(intptr_t)%s' % n)
            elif p.ann in ('bytes', 'c_const_void_p'):
                params.append([n, 'borrowed_bytes'])
                c_params.append('const unsigned char *%s, size_t %s_n' % (n, n))
                cast = 'const unsigned char *' if p.ann == 'bytes' else 'const void *'
                if p.elem is not None:
                    cast = 'const %s *' % elem_info(p.elem)[0]
                call_args.append('(%s)(%s ? %s : ffi_empty)' % (cast, n, n))
            elif p.ann in ('bytearray', 'c_mut_void_p'):
                params.append([n, 'bytes'])
                c_params.append('const unsigned char *%s, size_t %s_n' % (n, n))
                cast = 'unsigned char *' if p.ann == 'bytearray' else 'void *'
                if p.elem is not None:
                    cast = '%s *' % elem_info(p.elem)[0]
                call_args.append('(%s)(void *)%s' % (cast, n))
                bytearrays.append(n)
        res = d.result
        if d.trust:
            # the header's prototype names types the stub cannot spell (a struct): call through the stub's own prototype
            real = '((%s (*)(%s))%s)(%s)' % ('void' if res is None else result_ctype(res), ', '.join(d.c_params()) or 'void',
                                             d.symbol, ', '.join(call_args))
        else:
            real = '%s(%s)' % (d.symbol, ', '.join(call_args))
        if res is None:
            ret_kind, native_ret, convert = 'void', 'void', None
        elif res in INTS:
            ret_kind = INTS[res][1]
            native_ret, convert = NATIVE[ret_kind], '(%s)r' % NATIVE[ret_kind]
        elif res == 'c_bool':
            ret_kind, native_ret, convert = 'bool', '_Bool', 'r'
        elif res == 'c_double':
            ret_kind, native_ret, convert = 'float', 'double', 'r'
        elif res == 'c_float':
            ret_kind, native_ret, convert = 'float32', 'float', 'r'
        elif res == 'c_void_p':
            ret_kind, native_ret, convert = 'int', 'int64_t', '(int64_t)(intptr_t)r'
        elif res in ('c_char_p', 'c_mut_char_p'):
            ret_kind, native_ret, convert = 'str', 'ail_c_utf8_view', None
        lines = []
        if d.has_bytearray:
            # copy-in/copy-out: the result is the bytearrays' final contents; the C result is kept for `__rc`
            rc_type = 'double' if res in ('c_double', 'c_float') else 'int64_t'
            if res is not None:
                bodies.append('static %s ffi_rc_%s;' % (rc_type, d.export))
            lines.append('errno = 0;')
            lines.append(('%s r = %s;' % (result_ctype(res), real)) if res is not None else real + ';')
            lines.append('ffi_last_errno = errno;')
            if res is not None:
                value = 'r' if rc_type == 'double' else ('(int64_t)(intptr_t)r' if res == 'c_void_p' else
                                                         '(int64_t)r' if res != 'c_bool' else '(int64_t)r')
                lines.append('ffi_rc_%s = %s;' % (d.export, value))
            if len(bytearrays) == 1:
                lines.append('return (ail_c_bytes_view){%s, %s_n};' % (bytearrays[0], bytearrays[0]))
            else:
                total = ' + '.join('%s_n' % n for n in bytearrays)
                lines.append('size_t total = %s;' % total)
                lines.append('if (total > ffi_scratch_cap) { unsigned char *grown = realloc(ffi_scratch, total); if (!grown) abort(); ffi_scratch = grown; ffi_scratch_cap = total; }')
                lines.append('size_t at = 0;')
                for n in bytearrays:
                    lines.append('if (%s_n) memcpy(ffi_scratch + at, %s, %s_n); at += %s_n;' % (n, n, n, n))
                lines.append('return (ail_c_bytes_view){ffi_scratch, total};')
            functions[d.export] = dict(symbol=d.export, params=params, result='bytes')
            bodies.append('ail_c_bytes_view %s(%s) {\n%s\n}' % (d.export, ', '.join(c_params) or 'void', '\n'.join(lines)))
            if res is not None:
                rc_kind = {'float': 'float', 'float32': 'float'}.get(ret_kind, 'int')
                name = d.export + '__rc'
                functions[name] = dict(symbol=name, params=[], result=rc_kind)
                bodies.append('%s %s(void) { return ffi_rc_%s; }' % ('double' if rc_kind == 'float' else 'int64_t', name, d.export))
            return
        lines.append('errno = 0;')
        if res is None:
            lines.append(real + ';')
            lines.append('ffi_last_errno = errno;')
        elif res in ('c_char_p', 'c_mut_char_p'):
            lines.append('const char *r = %s;' % real)
            lines.append('ffi_last_errno = errno;')
            lines.append('if (!r) return (ail_c_utf8_view){NULL, 0};')
            lines.append('return (ail_c_utf8_view){(const unsigned char *)r, strlen(r)};')
        else:
            lines.append('%s r = %s;' % (result_ctype(res), real))
            lines.append('ffi_last_errno = errno;')
            lines.append('return %s;' % convert)
        functions[d.export] = dict(symbol=d.export, params=params, result=ret_kind)
        bodies.append('%s %s(%s) {\n%s\n}' % (native_ret, d.export, ', '.join(c_params) or 'void', '\n'.join(lines)))

    def _emit_cb(self, d, number, functions, bodies):
        """A stub that takes callbacks (F7): `E__start` copies the arguments and runs the C call on its own stack until
        the first callback or the end (the event it returns), `E__finish` runs it to the end and releases it, and
        `E__rc` / `E__rcs` give the C result. Each callback parameter gets a trampoline with the C signature."""
        e = d.export
        params, c_params, copy, call_args, owned = [], [], [], [], []
        for index, p in enumerate(d.params):
            n = 'p%d' % index
            slot = 'r->a%%s[%d]' % index
            if p.callback is not None:
                call_args.append('ffi_tr_%s_%d' % (e, index))
                continue
            if p.length_of is not None or p.ann in INTS:
                kind = INTS[p.length_type if p.length_of is not None else p.ann][1]
                params.append([n, kind])
                c_params.append('%s %s' % (NATIVE[kind], n))
                copy.append('%s = (int64_t)%s;' % (slot % 'i', n))
                call_args.append('(%s)%s' % (INTS[p.length_type if p.length_of is not None else p.ann][0], slot % 'i'))
            elif p.ann == 'c_bool':
                params.append([n, 'bool'])
                c_params.append('_Bool %s' % n)
                copy.append('%s = %s;' % (slot % 'i', n))
                call_args.append('(_Bool)%s' % (slot % 'i'))
            elif p.ann in ('c_double', 'c_float'):
                params.append([n, 'float' if p.ann == 'c_double' else 'float32'])
                c_params.append('%s %s' % ('double' if p.ann == 'c_double' else 'float', n))
                copy.append('%s = %s;' % (slot % 'f', n))
                call_args.append('(%s)%s' % ('double' if p.ann == 'c_double' else 'float', slot % 'f'))
            elif p.ann in ('c_char_p', 'c_mut_char_p'):
                params.append([n, 'cstr'])
                c_params.append('const char *%s' % n)
                copy.append('%s = ffi_cb_dup(%s, strlen(%s) + 1);' % (slot % 'p', n, n))
                call_args.append('(%s)%s' % ('const char *' if p.ann == 'c_char_p' else 'char *', slot % 'p'))
                owned.append(index)
            elif p.ann == 'c_void_p':
                params.append([n, 'int'])
                c_params.append('int64_t %s' % n)
                copy.append('%s = %s;' % (slot % 'i', n))
                call_args.append('(void *)(intptr_t)%s' % (slot % 'i'))
            else:
                writable = p.ann in ('bytearray', 'c_mut_void_p')
                params.append([n, 'bytes' if writable else 'borrowed_bytes'])
                c_params.append('const unsigned char *%s, size_t %s_n' % (n, n))
                copy.append('%s = ffi_cb_dup(%s ? (const void *)%s : (const void *)ffi_empty, %s_n); r->an[%d] = %s_n;'
                            % (slot % 'p', n, n, n, index, n))
                if p.elem is not None:
                    cast = ('%s *' if writable else 'const %s *') % elem_info(p.elem)[0]
                else:
                    cast = {'bytes': 'const unsigned char *', 'c_const_void_p': 'const void *', 'bytearray': 'unsigned char *',
                            'c_mut_void_p': 'void *'}[p.ann]
                call_args.append('(%s)%s' % (cast, slot % 'p'))
                owned.append(index)
        res = d.result
        if d.trust:
            real = '((%s (*)(%s))%s)(%s)' % ('void' if res is None else result_ctype(res), ', '.join(d.c_params()) or 'void',
                                             d.symbol, ', '.join(call_args))
        else:
            real = '%s(%s)' % (d.symbol, ', '.join(call_args))
        # trampolines
        for index, p in enumerate(d.params):
            if p.callback is None:
                continue
            cb = p.callback
            slot = 1 + [q for q in d.params if q.callback is not None].index(p)
            ret = 'void' if cb.ret is None else result_ctype(cb.ret)
            lines = ['    ffi_cb_rec *r = ffi_cb_enter(%d, "%s");' % (number, d.name)]
            for k, a in enumerate(cb.args):
                if a.kind == 'array':
                    lines.append('    r->cp[%d] = (const void *)a%d; r->ck[%d] = %d;' % (k, k, k, CB_CODES[cb_value_ctype(a.ann)]))
                elif a.kind == 'cptr':
                    field = 'cf' if a.ann in ('c_double', 'c_float') else 'ci'
                    cast = 'double' if field == 'cf' else 'int64_t'
                    lines.append('    r->%s[%d] = a%d ? (%s)*a%d : 0;' % (field, k, k, cast, k))
                elif a.ann in ('c_double', 'c_float'):
                    lines.append('    r->cf[%d] = a%d;' % (k, k))
                elif a.ann in ('c_char_p', 'c_mut_char_p'):
                    lines.append('    r->cp[%d] = a%d;' % (k, k))
                elif a.ann in ('c_void_p', 'c_const_void_p'):
                    lines.append('    r->ci[%d] = (int64_t)(intptr_t)a%d;' % (k, k))
                else:
                    lines.append('    r->ci[%d] = (int64_t)a%d;' % (k, k))
            if cb.ret is None:
                lines.append('    ffi_cb_yield(r, %d);' % slot)
            else:
                value = cb.on_error
                if type(value) is bool:
                    literal = '1' if value else '0'
                elif type(value) is float:
                    literal = repr(value)
                elif cb.ret in ('c_double', 'c_float'):
                    literal = repr(float(value))
                else:
                    literal = '%dULL' % value if value > (1 << 63) - 1 else '%dLL' % value
                if cb.ret == 'c_void_p':
                    fail, ok = '(void *)(uintptr_t)%s' % literal, '(void *)(intptr_t)r->ri'
                elif cb.ret in ('c_double', 'c_float'):
                    fail, ok = '(%s)%s' % (ret, literal), '(%s)r->rf' % ret
                elif cb.ret == 'c_bool':
                    fail, ok = '(_Bool)%s' % literal, 'r->ri != 0'
                else:
                    fail, ok = '(%s)%s' % (ret, literal), '(%s)r->ri' % ret
                lines.append('    if (!ffi_cb_yield(r, %d)) return %s;' % (slot, fail))
                lines.append('    return %s;' % ok)
            arglist = ', '.join('%s a%d' % (a.ctype(), k) for k, a in enumerate(cb.args)) or 'void'
            bodies.append('static %s ffi_tr_%s_%d(%s) {\n%s\n}' % (ret, e, index, arglist, '\n'.join(lines)))
        # the C call itself, on the call's own stack
        run = ['    errno = 0;']
        if res is None:
            run.append('    %s;' % real)
        else:
            run.append('    %s v = %s;' % (result_ctype(res), real))
        run.append('    r->err = errno;')
        if res in ('c_double', 'c_float'):
            run.append('    r->rc_f = v;')
        elif res in ('c_char_p', 'c_mut_char_p'):
            run.append('    r->rc_s = v;')
        elif res == 'c_void_p':
            run.append('    r->rc_i = (int64_t)(intptr_t)v;')
        elif res is not None:
            run.append('    r->rc_i = (int64_t)v;')
        bodies.append('static void ffi_run_%s(ffi_cb_rec *r) {\n%s\n}' % (e, '\n'.join(run)))
        functions[e + '__start'] = dict(symbol=e + '__start', params=params, result='int')
        bodies.append('int64_t %s__start(%s) {\n    ffi_cb_rec *r = ffi_cb_new(ffi_run_%s, %d);\n%s\n    return ffi_cb_go(r);\n}'
                      % (e, ', '.join(c_params) or 'void', e, number, '\n'.join('    ' + line for line in copy)))
        finish = ['    ffi_cb_rec *r = ffi_cb_end();']
        if res in ('c_double', 'c_float'):
            bodies.append('static double ffi_rc_%s;' % e)
            finish.append('    ffi_rc_%s = r->rc_f;' % e)
        elif res in ('c_char_p', 'c_mut_char_p'):
            bodies.append('static const char *ffi_rc_%s;' % e)
            finish.append('    ffi_rc_%s = r->rc_s;' % e)
        elif res is not None:
            bodies.append('static int64_t ffi_rc_%s;' % e)
            finish.append('    ffi_rc_%s = r->rc_i;' % e)
        bytearrays = [i for i, p in enumerate(d.params) if p.ann in ('bytearray', 'c_mut_void_p')]
        if bytearrays:
            finish.append('    size_t total = %s;' % ' + '.join('r->an[%d]' % i for i in bytearrays))
            finish.append('    if (total > ffi_scratch_cap) { unsigned char *grown = realloc(ffi_scratch, total ? total : 1); '
                          'if (!grown) abort(); ffi_scratch = grown; ffi_scratch_cap = total; }')
            finish.append('    size_t at = 0;')
            for i in bytearrays:
                finish.append('    if (r->an[%d]) memcpy(ffi_scratch + at, r->ap[%d], r->an[%d]); at += r->an[%d];' % (i, i, i, i))
        for i in owned:
            finish.append('    free(r->ap[%d]);' % i)
        finish.append('    free(r);')
        if bytearrays:
            finish.append('    return (ail_c_bytes_view){ffi_scratch, total};')
        functions[e + '__finish'] = dict(symbol=e + '__finish', params=[], result='bytes' if bytearrays else 'void')
        bodies.append('%s %s__finish(void) {\n%s\n}' % ('ail_c_bytes_view' if bytearrays else 'void', e, '\n'.join(finish)))
        if res in ('c_char_p', 'c_mut_char_p'):
            functions[e + '__rcs'] = dict(symbol=e + '__rcs', params=[], result='str')
            bodies.append('ail_c_utf8_view %s__rcs(void) { const char *s = ffi_rc_%s; '
                          'return s ? (ail_c_utf8_view){(const unsigned char *)s, strlen(s)} : (ail_c_utf8_view){NULL, 0}; }' % (e, e))
        elif res is not None:
            kind = 'float' if res in ('c_double', 'c_float') else 'int'
            functions[e + '__rc'] = dict(symbol=e + '__rc', params=[], result=kind)
            bodies.append('%s %s__rc(void) { return ffi_rc_%s; }' % ('double' if kind == 'float' else 'int64_t', e, e))

    @staticmethod
    def _emit_cb_access(tag, functions, bodies):
        """What the wrappers of one file read and resume a callback with: the innermost running call's arguments."""
        t = 'ffi_%s__' % tag
        rows = [
            ('cbi', [['k', 'int']], 'int', 'int64_t %s(int64_t k) { return ffi_cb_top->ci[k]; }'),
            ('cbf', [['k', 'int']], 'float', 'double %s(int64_t k) { return ffi_cb_top->cf[k]; }'),
            ('cbs', [['k', 'int']], 'str', 'ail_c_utf8_view %s(int64_t k) { return ffi_cb_view((const char *)ffi_cb_top->cp[k]); }'),
            ('cbn', [['k', 'int'], ['c', 'int']], 'int',
             'int64_t %s(int64_t k, int64_t c) { ffi_cb_rec *r = ffi_cb_top; return r->cp[k] && r->ci[c] > 0 ? r->ci[c] : 0; }'),
            ('cbai', [['k', 'int'], ['i', 'int']], 'int', 'int64_t %s(int64_t k, int64_t i) { return ffi_cb_item_i(ffi_cb_top, k, i); }'),
            ('cbaf', [['k', 'int'], ['i', 'int']], 'float',
             'double %s(int64_t k, int64_t i) { const void *p = ffi_cb_top->cp[k]; '
             'return ffi_cb_top->ck[k] == 11 ? (double)((const float *)p)[i] : ((const double *)p)[i]; }'),
            ('cbas', [['k', 'int'], ['i', 'int']], 'str',
             'ail_c_utf8_view %s(int64_t k, int64_t i) { return ffi_cb_view(((const char *const *)ffi_cb_top->cp[k])[i]); }'),
            ('resume_i', [['v', 'int']], 'int', 'int64_t %s(int64_t v) { ffi_cb_rec *r = ffi_cb_top; r->ri = v; return ffi_cb_go(r); }'),
            ('resume_f', [['v', 'float']], 'int', 'int64_t %s(double v) { ffi_cb_rec *r = ffi_cb_top; r->rf = v; return ffi_cb_go(r); }'),
            ('resume_v', [], 'int', 'int64_t %s(void) { return ffi_cb_go(ffi_cb_top); }'),
        ]
        for word, params, result, body in rows:
            functions[t + word] = dict(symbol=t + word, params=params, result=result)
            bodies.append(body % (t + word))

    def _flags(self, lib, directory, pkg_config):
        if '/' in lib or lib.endswith(('.so', '.dylib', '.dll', '.a')) or '.so.' in lib:
            path = Path(os.path.normpath(os.path.join(directory, lib)))
            return [str(path), '-Wl,-rpath,' + str(path.parent)]
        if pkg_config and shutil.which('pkg-config'):
            found = subprocess.run(['pkg-config', '--libs', pkg_config], capture_output=True, text=True)
            if found.returncode == 0 and found.stdout.strip():
                return shlex.split(found.stdout)
        return ['-l' + lib]

    def _link_args(self):
        args, seen = [], set()
        wanted = [(d.lib, d.pkg_config, d.directory) for d in self.decls if d.lib is not None]
        used = {d.path for d in self.decls}
        for key, entries in self.links.items():
            if key in used:
                wanted.extend(entries)
        wanted.extend((lib, None, os.getcwd()) for lib in self.extra_libs)
        for lib, pkg, directory in wanted:
            for flag in self._flags(lib, directory, pkg):
                if flag not in seen:
                    seen.add(flag)
                    args.append(flag)
        return args
