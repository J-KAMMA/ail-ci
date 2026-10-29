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


class Param:
    def __init__(self, name, ann, default=None, has_default=False):
        self.name, self.ann, self.default, self.has_default = name, ann, default, has_default
        self.length_of = None          # for length("x", T): the parameter name
        self.length_type = None
        self.elem = None               # ptr(T) / cptr(T): the element type name, else None


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
        self.tag = None                # per-file hash
        self.local_header = False
        self.directory = None

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
                        imported.update(set(INTS) | PARAM_ANN | {'extern', 'link', 'length', 'ptr', 'cptr', 'declarations'})
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
        self.decls.extend(decls)
        # a file that imports ail_ffi but declares nothing is left with its import blanked
        block = []
        if decls:
            if any(d.has_bytearray for d in decls):
                block.append('')
                block.append('def ffi_put_%s(dst: bytearray, src: bytes, at: int) -> int:' % tag)
                block.append('    n = len(dst)')
                block.append('    dst.clear()')
                block.append('    dst.extend(src[at:at + n])')
                block.append('    return at + n')
            for decl in decls:
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
        else:
            decl.result = self._ann_name(path, node, node.returns, imported, module_names, node.name)
            if decl.result not in RESULT_ANN:
                self._refuse(path, node.returns, '%s: `%s` cannot be a result type' % (node.name, decl.result))
            if decl.result == 'str':
                decl.result = 'c_char_p'
        if decl.check is not None and (decl.result is None or decl.result in ('c_double', 'c_float', 'c_bool', 'c_char_p', 'c_mut_char_p')):
            self._refuse(path, node, '%s: check= needs an integer or handle result' % node.name)
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

    # ------------------------------------------------------------------ AIL wrappers

    def _wrapper(self, d):
        out = ['']
        sig = []
        for p in d.params:
            if p.length_of is not None:
                continue
            text = '%s: %s' % (p.name, python_type(p.ann))
            if p.has_default:
                text += ' = %r' % (p.default,)
            sig.append(text)
        ret = {None: 'None'}.get(d.result) or python_type(d.result)
        out.append('def %s(%s) -> %s:' % (d.name, ', '.join(sig), ret))
        args = []
        for p in d.params:
            if p.length_of is not None:
                target = next(q for q in d.params if q.name == p.length_of)
                size = elem_info(target.elem)[1] if target.elem is not None else 1
                args.append('len(%s)' % p.length_of if size == 1 else 'len(%s) // %d' % (p.length_of, size))
            elif p.ann in ('bytearray', 'c_mut_void_p'):
                args.append('bytes(%s)' % p.name)
            else:
                args.append(p.name)
        call = '%s(%s)' % (d.export, ', '.join(args))
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
        out.append('    return ffi_rc != 0' if d.result == 'c_bool' else '    return ffi_rc')
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
            self._emit(d, functions, bodies)
        for tag in tags:
            name = 'ffi_%s__errno' % tag
            functions[name] = dict(symbol=name, params=[], result='int')
            bodies.append('int64_t %s(void) { return ffi_last_errno; }' % name)
            name = 'ffi_%s__strerror' % tag
            functions[name] = dict(symbol=name, params=[['code', 'int']], result='str')
            bodies.append('ail_c_utf8_view %s(int64_t code) { const char *s = strerror((int)code); return (ail_c_utf8_view){(const unsigned char *)s, strlen(s)}; }' % name)
        # the per-declaration helpers must be exported under the declaration's own tag
        source = '\n'.join(code + extern_decls + sorted(set(asserts)) + bodies) + '\n'
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
