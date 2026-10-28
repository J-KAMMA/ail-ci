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
import copy
import ctypes
import hashlib
import json
import keyword
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
    'c_char': ('char', 'int8', 8, True),
}
NATIVE = {'int8': 'int8_t', 'int16': 'int16_t', 'int32': 'int32_t', 'uint8': 'uint8_t', 'uint16': 'uint16_t',
          'uint32': 'uint32_t', 'int': 'int64_t', 'uint64_bits': 'uint64_t'}
CSTRUCT_CTYPES = {
    'c_int8': ctypes.c_int8, 'c_byte': ctypes.c_int8, 'c_int16': ctypes.c_int16, 'c_short': ctypes.c_short,
    'c_int32': ctypes.c_int32, 'c_int': ctypes.c_int, 'c_int64': ctypes.c_int64, 'c_long': ctypes.c_long,
    'c_longlong': ctypes.c_longlong, 'c_ssize_t': ctypes.c_ssize_t, 'c_char': ctypes.c_char,
    'c_uint8': ctypes.c_uint8, 'c_ubyte': ctypes.c_uint8, 'c_uint16': ctypes.c_uint16, 'c_ushort': ctypes.c_ushort,
    'c_uint32': ctypes.c_uint32, 'c_uint': ctypes.c_uint, 'c_uint64': ctypes.c_uint64, 'c_ulong': ctypes.c_ulong,
    'c_ulonglong': ctypes.c_ulonglong, 'c_size_t': ctypes.c_size_t, 'c_bool': ctypes.c_bool,
    'c_double': ctypes.c_double, 'c_float': ctypes.c_float,
}
CSTRUCT_KINDS = {}
for _name, (_c, _kind, _bits, _signed) in INTS.items():
    CSTRUCT_KINDS[_name] = ('i' if _signed else 'u') + str(_bits)
for _name in ('c_bool',):
    CSTRUCT_KINDS[_name] = 'bool'
for _name in ('c_double',):
    CSTRUCT_KINDS[_name] = 'f64'
for _name in ('c_float',):
    CSTRUCT_KINDS[_name] = 'f32'
for _name in ('c_char_p', 'c_mut_char_p', 'c_void_p', 'c_const_void_p', 'c_mut_void_p'):
    CSTRUCT_KINDS[_name] = 'i64'
    CSTRUCT_CTYPES[_name] = ctypes.c_void_p
CSTRUCT_FIELDS = set(CSTRUCT_CTYPES)
EXCEPTIONS = ('OSError', 'ValueError', 'RuntimeError', 'KeyError', 'IndexError', 'OverflowError', 'EOFError')
CHECKS = {'negative': '< 0', 'nonzero': '!= 0', 'null': '== 0', 'minus1': '== -1'}
OPTIONS = ('lib', 'header', 'symbol', 'check', 'errno', 'exc', 'pkg_config', 'sources', 'trust')


class Param:
    def __init__(self, name, ann, default=None, has_default=False):
        self.name, self.ann, self.default, self.has_default = name, ann, default, has_default
        self.length_of = None          # for length("x", T): the parameter name
        self.length_type = None
        self.elem = None               # ptr(T) / cptr(T): the element type name, else None
        self.struct = None             # @cstruct class name for a pointer to a struct
        self.struct_c = None           # its C name (`struct tm`)


class Decl:
    def __init__(self):
        self.path = self.line = self.name = self.symbol = self.export = None
        self.lib = self.header = self.pkg_config = None
        self.check = self.exc = None
        self.sources = []
        self.errno = False
        self.trust = False             # trust=True: the header is included but its prototype is not compared
        self.params = []
        self.result = None             # annotation name, 'cstruct', or None for void
        self.result_struct = None      # the @cstruct class name of a struct pointer result
        self.result_struct_c = None
        self.tag = None                # per-file hash
        self.local_header = False
        self.directory = None

    @property
    def has_bytearray(self):
        return any(p.struct is None and p.ann in ('bytearray', 'c_mut_void_p') for p in self.params)

    @property
    def has_writable(self):
        """A bytearray, or a pointer to a @cstruct class the C function may write."""
        return self.has_bytearray or any(p.struct is not None and p.ann != 'bytes' for p in self.params)

    def c_params(self):
        """[(C type, name)] of the real function, in order."""
        out = []
        for p in self.params:
            out.append(p_ctype(p))
        return out

    def prototype(self):
        ret = 'void' if self.result is None else result_ctype(self.result, self.result_struct_c)
        return '%s %s(%s)' % (ret, self.symbol, ', '.join(self.c_params()) or 'void')


def elem_info(name):
    """(C type, size in bytes) of the element type of ptr(T) / cptr(T)."""
    if name in INTS:
        return INTS[name][0], INTS[name][2] // 8
    return {'c_double': ('double', 8), 'c_float': ('float', 4), 'c_bool': ('_Bool', 1), 'c_void_p': ('void *', 8)}[name]


def p_ctype(p):
    if p.length_of is not None:
        return INTS[p.length_type][0]
    if p.struct is not None:
        return ('const %s *' if p.ann == 'bytes' else '%s *') % p.struct_c
    if p.elem is not None:
        return ('const %s *' if p.ann == 'bytes' else '%s *') % elem_info(p.elem)[0]
    if p.ann in INTS:
        return INTS[p.ann][0]
    return {'c_bool': '_Bool', 'c_double': 'double', 'c_float': 'float', 'c_char_p': 'const char *',
            'c_void_p': 'void *', 'c_mut_char_p': 'char *', 'bytes': 'const unsigned char *', 'bytearray': 'unsigned char *',
            'c_const_void_p': 'const void *', 'c_mut_void_p': 'void *'}[p.ann]


def result_ctype(ann, struct_c=None):
    if ann == 'cstruct':
        return '%s *' % struct_c
    if ann in INTS:
        return INTS[ann][0]
    return {'c_bool': '_Bool', 'c_double': 'double', 'c_float': 'float', 'c_char_p': 'const char *',
            'c_mut_char_p': 'char *', 'c_void_p': 'void *'}[ann]


PARAM_ANN = set(INTS) | {'c_bool', 'c_double', 'c_float', 'c_char_p', 'c_mut_char_p', 'c_void_p', 'bytes', 'bytearray', 'str',
                         'c_const_void_p', 'c_mut_void_p'}
CSTRUCT_ACCESSORS = {'i8': ('get_i8', 'put_i8'), 'u8': ('get_u8', 'put_u8'), 'i16': ('get_i16', 'put_i16'),
                     'u16': ('get_u16', 'put_u16'), 'i32': ('get_i32', 'put_i32'), 'u32': ('get_u32', 'put_u32'),
                     'i64': ('get_i64', 'put_i64'), 'u64': ('get_i64', 'put_i64'), 'bool': ('get_u8', 'put_u8'),
                     'f32': ('get_f32', 'put_f32'), 'f64': ('get_f64', 'put_f64')}
RESULT_ANN = set(INTS) | {'c_bool', 'c_double', 'c_float', 'c_char_p', 'c_mut_char_p', 'c_void_p', 'str', 'cstruct'}


def python_type(ann):
    """The AIL/Python type the wrapper uses for a stub annotation."""
    if ann in INTS:
        return 'int'
    return {'c_bool': 'bool', 'c_double': 'float', 'c_float': 'float', 'c_char_p': 'str', 'c_mut_char_p': 'str', 'str': 'str',
            'c_void_p': 'int', 'bytes': 'bytes', 'c_const_void_p': 'bytes', 'bytearray': 'bytearray',
            'c_mut_void_p': 'bytearray', 'cstruct': 'int'}[ann]


class CStruct:
    def __init__(self):
        self.name = self.c_name = self.header = None
        self.path = self.directory = None
        self.fields = []               # dicts: name, ann, count, offset, size, kind, ctype
        self.size = 0
        self.local_header = False

    def c_field(self, field):
        return self.c_name + ' ' + field


def _cbuf_source(prefix):
    """The ail_cbuf accessors as ordinary AIL source, renamed with `prefix` (the same code the runtime uses)."""
    path = Path(__file__).with_name('ail_cbuf.py')
    tree = ast.parse(path.read_text(encoding='utf8'))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    names = {node.name for node in functions}
    out = []
    for node in functions:
        original = node.name
        node = copy.deepcopy(node)
        for inner in ast.walk(node):
            if isinstance(inner, ast.FunctionDef) and inner.name in names:
                inner.name = prefix + inner.name
            elif isinstance(inner, ast.Name) and inner.id in names:
                inner.id = prefix + inner.id
        # _load reads bytes and _store writes a bytearray: the same accessor never sees both.
        node.args.args[0].annotation = ast.Name(id='bytes' if original.startswith('get_') else 'bytearray', ctx=ast.Load())
        out.append(ast.unparse(node))
    return '\n\n'.join(out)


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
        self.cstructs = {}              # @cstruct class name -> CStruct
        self._owned = False

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
        edits = []                      # (first line, last line, replacement text)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == 'ail_ffi' and node.level == 0:
                for alias in node.names:
                    if alias.name == '*':
                        imported.update(set(INTS) | PARAM_ANN | {'extern', 'link', 'length', 'ptr', 'cptr', 'cstruct',
                                                                 'c_array', 'declarations'})
                        continue
                    if alias.asname not in (None, alias.name):
                        self._refuse(path, node, 'ail_ffi: import its names plainly (`from ail_ffi import extern, c_int`)')
                    imported.add(alias.name)
                edits.append((node.lineno, node.end_lineno, ''))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'ail_ffi':
                        module_names.add(alias.asname or 'ail_ffi')
                        edits.append((node.lineno, node.end_lineno, ''))
        if not imported and not module_names:
            return text
        tag = hashlib.sha1(str(path).encode()).hexdigest()[:6]
        classes = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                deco = [d for d in node.decorator_list if self._is_cstruct(d, imported, module_names)]
                if not deco:
                    continue
                if len(node.decorator_list) != 1:
                    self._refuse(path, node, '%s: a @cstruct class takes no other decorator' % node.name)
                classes.append((node, deco[0]))
        cstructs = []
        class_names = {node.name for node, _ in classes}
        for node, call in classes:
            cs = self._cstruct(path, node, call, imported, module_names, class_names)
            if cs.name in self.cstructs:
                self._refuse(path, node, '%s: a @cstruct class is already declared' % cs.name)
            self.cstructs[cs.name] = cs
            cstructs.append(cs)
            edits.append((node.decorator_list[0].lineno, node.end_lineno, self._cstruct_code(cs, tag)))
        decls = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and any(n is node for n, _ in classes):
                continue
            if isinstance(node, ast.Expr) and self._is_link(node.value, imported, module_names):
                self._link(path, node.value)
                edits.append((node.lineno, node.end_lineno, ''))
                continue
            if not isinstance(node, ast.FunctionDef):
                continue
            deco = [d for d in node.decorator_list if self._is_extern(d, imported, module_names)]
            if not deco:
                continue
            if len(node.decorator_list) != 1:
                self._refuse(path, node, '%s: an @extern stub takes no other decorator' % node.name)
            decls.append(self._decl(path, node, deco[0], imported, module_names))
            edits.append((node.decorator_list[0].lineno, node.end_lineno, ''))
        if self.forbid and (decls or cstructs):
            first = decls[0] if decls else cstructs[0]
            raise ModuleRefusal(path, getattr(first, 'line', 1), 1,
                                'FFI declaration %s is forbidden by --no-ffi' % first.name)
        for decl in decls:
            decl.tag = tag
            decl.export = 'ffi_%s_%s' % (tag, decl.name)
        lines = text.split('\n')
        for first, last, replacement in sorted(edits, reverse=True):
            lines[first - 1:last] = replacement.split('\n') if replacement else ['']
        self.decls.extend(decls)
        block = []
        if decls:
            if any(d.has_writable for d in decls):
                block.append('')
                block.append('def ffi_put_%s(dst: bytearray, src: bytes, at: int) -> int:' % tag)
                block.append('    n = len(dst)')
                block.append('    dst.clear()')
                block.append('    dst.extend(src[at:at + n])')
                block.append('    return at + n')
            for decl in decls:
                block.extend(self._wrapper(decl))
        if cstructs:
            block.append('')
            block.append(_cbuf_source('_ail_cbuf_%s_' % tag))
        return '\n'.join(lines).rstrip('\n') + '\n' + '\n'.join(block) + ('\n' if block else '')

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

    @staticmethod
    def _is_extern(node, imported, module_names):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id == 'extern' and 'extern' in imported
        return (isinstance(func, ast.Attribute) and func.attr == 'extern' and isinstance(func.value, ast.Name)
                and func.value.id in module_names)

    @staticmethod
    def _is_cstruct(node, imported, module_names):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id == 'cstruct' and 'cstruct' in imported
        return (isinstance(func, ast.Attribute) and func.attr == 'cstruct' and isinstance(func.value, ast.Name)
                and func.value.id in module_names)

    def _cstruct(self, path, node, call, imported, module_names, class_names):
        cs = CStruct()
        cs.name, cs.line, cs.path, cs.directory = node.name, node.lineno, str(path), str(path.parent)
        options = {}
        if call.args:
            self._refuse(path, call, '%s: @cstruct takes keyword options only' % node.name)
        for option in call.keywords:
            if option.arg not in ('header', 'name', 'union', 'bitfield'):
                self._refuse(path, option.value, '%s: unknown @cstruct option %s' % (node.name, option.arg))
            options[option.arg] = option.value
        def constant(key, kind):
            if key not in options:
                return None
            value = options[key]
            if isinstance(value, ast.Constant) and (value.value is None or isinstance(value.value, kind)):
                return value.value
            self._refuse(path, value, '%s: @cstruct %s must be a literal' % (node.name, key))
        if constant('union', bool):
            self._refuse(path, options['union'], '%s: @cstruct refuses union %s by name' % (node.name, node.name))
        if constant('bitfield', bool):
            self._refuse(path, options['bitfield'], '%s: @cstruct refuses bitfield %s by name' % (node.name, node.name))
        cs.header = constant('header', str)
        cs.c_name = constant('name', str) or node.name
        if not cs.c_name or not all(ch.isalnum() or ch in ' _' for ch in cs.c_name):
            self._refuse(path, options.get('name', node), '%s: @cstruct name must be a C struct or typedef name' % node.name)
        if cs.header is not None and not cs.header.replace('/', '').replace('_', '').replace('.', '').replace('-', '').isalnum():
            self._refuse(path, options['header'], '%s: unsupported header name' % node.name)
        if node.bases:
            self._refuse(path, node, '%s: a @cstruct class has no base classes' % node.name)
        if node.keywords:
            self._refuse(path, node, '%s: a @cstruct class takes no keyword arguments' % node.name)
        for statement in node.body:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
                continue
            if isinstance(statement, ast.Pass):
                continue
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                self._refuse(path, statement, '%s: a @cstruct class has C-typed fields only' % node.name)
            if statement.value is not None:
                self._refuse(path, statement.value, '%s: a @cstruct field has no default' % node.name)
            field = statement.target.id
            if not field.isidentifier() or keyword.iskeyword(field):
                self._refuse(path, statement.target, '%s: field %r is not a usable attribute name' % (node.name, field))
            ann_name, count = self._cstruct_field(path, node, statement.annotation, field, imported, module_names, class_names)
            cs.fields.append(dict(name=field, ann=ann_name, count=count,
                                  kind=CSTRUCT_KINDS[ann_name], elem_size=ctypes.sizeof(CSTRUCT_CTYPES[ann_name])))
        if not cs.fields:
            self._refuse(path, node, '%s: a @cstruct class needs at least one field' % node.name)
        layout = [(f['name'], CSTRUCT_CTYPES[f['ann']] * f['count'] if f['count'] != 1 else CSTRUCT_CTYPES[f['ann']])
                  for f in cs.fields]
        class Layout(ctypes.Structure):
            _fields_ = layout
        cs.size = ctypes.sizeof(Layout)
        for f in cs.fields:
            descriptor = Layout.__dict__[f['name']]
            f['offset'], f['size'] = descriptor.offset, descriptor.size
        if cs.header is not None:
            cs.local_header = (path.parent / cs.header).is_file()
        return cs

    def _cstruct_field(self, path, node, ann, field, imported, module_names, class_names):
        if isinstance(ann, ast.Call) and ((isinstance(ann.func, ast.Name) and ann.func.id == 'c_array' and 'c_array' in imported)
                                          or (isinstance(ann.func, ast.Attribute) and ann.func.attr == 'c_array'
                                              and isinstance(ann.func.value, ast.Name) and ann.func.value.id in module_names)):
            if len(ann.args) != 2 or ann.keywords:
                self._refuse(path, ann, '%s: c_array(C type, count)' % node.name)
            element_node = ann.args[0]
            if isinstance(element_node, ast.Name) and element_node.id in class_names:
                self._refuse(path, element_node, '%s: nested by-value array of structs in field %r is not supported'
                             % (node.name, field))
            element = self._ann_name(path, node, element_node, imported, module_names, node.name)
            if element in class_names:
                self._refuse(path, element_node, '%s: nested by-value array of structs in field %r is not supported'
                             % (node.name, field))
            if element not in CSTRUCT_FIELDS:
                self._refuse(path, ann.args[0], '%s: field %r must be an array of C scalar types' % (node.name, field))
            count = ann.args[1]
            if not isinstance(count, ast.Constant) or type(count.value) is not int:
                self._refuse(path, ann.args[1], '%s: field %r needs a literal array length' % (node.name, field))
            if count.value <= 0:
                self._refuse(path, ann.args[1], '%s: flexible array member %r is not supported' % (node.name, field))
            return element, count.value
        if isinstance(ann, ast.Call):
            self._refuse(path, ann, '%s: field %r has an unsupported C type' % (node.name, field))
        if isinstance(ann, ast.Name) and ann.id in class_names:
            self._refuse(path, ann, '%s: struct field %r by value is not supported' % (node.name, field))
        name = self._ann_name(path, node, ann, imported, module_names, node.name)
        if name in class_names:
            self._refuse(path, ann, '%s: struct field %r by value is not supported' % (node.name, field))
        if name not in CSTRUCT_FIELDS:
            self._refuse(path, ann, '%s: field %r is not a C type' % (node.name, field))
        return name, 1

    def _cstruct_code(self, cs, tag):
        prefix = '_ail_cbuf_%s_' % tag
        out = ['class %s:' % cs.name,
               '    def __init__(self) -> None:']
        for field in cs.fields:
            name, kind, count = field['name'], field['kind'], field['count']
            if count != 1:
                zero = '0.0' if kind.startswith('f') else ('False' if kind == 'bool' else '0')
                out.append('        self.%s = [%s] * %d' % (name, zero, count))
            elif kind.startswith('f'):
                out.append('        self.%s = 0.0' % name)
            elif kind == 'bool':
                out.append('        self.%s = False' % name)
            else:
                out.append('        self.%s = 0' % name)
        out.append('')
        out.append('    def _load(self, data: bytes) -> None:')
        for field in cs.fields:
            name, kind, count, at, size = field['name'], field['kind'], field['count'], field['offset'], field['elem_size']
            get, put = CSTRUCT_ACCESSORS[kind]
            getter = prefix + get
            if count != 1:
                out.append('        items = []')
                out.append('        for index in range(%d):' % count)
                if kind == 'bool':
                    out.append('            items.append(%s(data, %d + index * %d) != 0)' % (getter, at, size))
                else:
                    out.append('            items.append(%s(data, %d + index * %d))' % (getter, at, size))
                out.append('        self.%s = items' % name)
            elif kind == 'bool':
                out.append('        self.%s = %s(data, %d) != 0' % (name, getter, at))
            else:
                out.append('        self.%s = %s(data, %d)' % (name, getter, at))
        out.append('')
        out.append('    def _store(self, data: bytearray) -> None:')
        for field in cs.fields:
            name, kind, count, at, size = field['name'], field['kind'], field['count'], field['offset'], field['elem_size']
            get, put = CSTRUCT_ACCESSORS[kind]
            setter = prefix + put
            if count != 1:
                out.append('        for index in range(%d):' % count)
                value = 'self.%s[index]' % name
                if kind == 'bool':
                    out.append('            %s(data, %d + index * %d, 1 if %s else 0)' % (setter, at, size, value))
                elif kind.startswith('f'):
                    out.append('            %s(data, %d + index * %d, float(%s))' % (setter, at, size, value))
                else:
                    out.append('            %s(data, %d + index * %d, int(%s))' % (setter, at, size, value))
            else:
                value = 'self.%s' % name
                if kind == 'bool':
                    out.append('        %s(data, %d, 1 if %s else 0)' % (setter, at, value))
                elif kind.startswith('f'):
                    out.append('        %s(data, %d, float(%s))' % (setter, at, value))
                else:
                    out.append('        %s(data, %d, int(%s))' % (setter, at, value))
        return '\n'.join(out)

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
                element_node = ann.args[0]
                element = element_node.id if isinstance(element_node, ast.Name) else None
                if element in self.cstructs:
                    param = Param(arg.arg, 'bytearray' if kind == 'ptr' else 'bytes')
                    param.struct, param.struct_c = element, self.cstructs[element].c_name
                else:
                    element = self._ann_name(path, node, element_node, imported, module_names, node.name)
                    if element not in INTS and element not in ('c_double', 'c_float', 'c_bool', 'c_void_p'):
                        self._refuse(path, ann, '%s: %s takes an integer, float, bool or c_void_p C type' % (node.name, kind))
                    param = Param(arg.arg, 'bytearray' if kind == 'ptr' else 'bytes')
                    param.elem = element
                if default is not None:
                    self._refuse(path, default, '%s: a pointer parameter has no default' % node.name)
            elif isinstance(ann, ast.Name) and ann.id in self.cstructs:
                param = Param(arg.arg, 'bytearray')
                param.struct, param.struct_c = ann.id, self.cstructs[ann.id].c_name
                if default is not None:
                    self._refuse(path, default, '%s: a struct pointer parameter has no default' % node.name)
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
            result_name = node.returns.id if isinstance(node.returns, ast.Name) else None
            if result_name in self.cstructs:
                decl.result = 'cstruct'
                decl.result_struct = result_name
                decl.result_struct_c = self.cstructs[result_name].c_name
            elif isinstance(node.returns, ast.Call) and ((isinstance(node.returns.func, ast.Name)
                                                          and node.returns.func.id in ('ptr', 'cptr') and node.returns.func.id in imported)
                                                         or (isinstance(node.returns.func, ast.Attribute)
                                                             and node.returns.func.attr in ('ptr', 'cptr'))):
                element = node.returns.args[0] if len(node.returns.args) == 1 and not node.returns.keywords else None
                element_name = element.id if isinstance(element, ast.Name) else None
                if element_name not in self.cstructs:
                    self._refuse(path, node.returns, '%s: a pointer result must name a @cstruct class' % node.name)
                decl.result = 'cstruct'
                decl.result_struct = element_name
                decl.result_struct_c = self.cstructs[element_name].c_name
            else:
                decl.result = self._ann_name(path, node, node.returns, imported, module_names, node.name)
                if decl.result not in RESULT_ANN:
                    self._refuse(path, node.returns, '%s: `%s` cannot be a result type' % (node.name, decl.result))
                if decl.result == 'str':
                    decl.result = 'c_char_p'
        if decl.check is not None and (decl.result is None or decl.result in ('c_double', 'c_float', 'c_bool', 'c_char_p', 'c_mut_char_p')):
            self._refuse(path, node, '%s: check= needs an integer or handle result' % node.name)
        if decl.has_writable and decl.result in ('c_char_p', 'c_mut_char_p'):
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
            text = '%s: %s' % (p.name, p.struct or python_type(p.ann))
            if p.has_default:
                text += ' = %r' % (p.default,)
            sig.append(text)
        ret = {None: 'None'}.get(d.result) or (d.result_struct if d.result == 'cstruct' else python_type(d.result))
        out.append('def %s(%s) -> %s:' % (d.name, ', '.join(sig), ret))
        structs = []                    # (index, Param, local buffer)
        for p in d.params:
            if p.struct is None:
                continue
            index = len(structs)
            size = self.cstructs[p.struct].size
            structs.append((index, p))
            out.append('    ffi_s%d = bytearray(%d)' % (index, size))
            out.append('    %s._store(ffi_s%d)' % (p.name, index))
        args = []
        for p in d.params:
            if p.length_of is not None:
                target = next(q for q in d.params if q.name == p.length_of)
                size = elem_info(target.elem)[1] if target.elem is not None else 1
                args.append('len(%s)' % p.length_of if size == 1 else 'len(%s) // %d' % (p.length_of, size))
            elif p.struct is not None:
                index = next(i for i, q in structs if q is p)
                args.append('bytes(ffi_s%d)' % index)
            elif p.ann in ('bytearray', 'c_mut_void_p'):
                args.append('bytes(%s)' % p.name)
            else:
                args.append(p.name)
        call = '%s(%s)' % (d.export, ', '.join(args))
        for p in d.params:
            if p.elem is not None and elem_info(p.elem)[1] > 1:
                out.append('    if len(%s) %% %d != 0:' % (p.name, elem_info(p.elem)[1]))
                out.append('        raise ValueError("%s: %s must hold a whole number of %s")' % (d.name, p.name, p.elem))
        if d.has_writable:
            out.append('    ffi_r = ' + call)
            out.append('    ffi_o = 0')
            for p in d.params:
                if p.struct is not None and p.ann != 'bytes':
                    index = next(i for i, q in structs if q is p)
                    out.append('    ffi_o = ffi_put_%s(ffi_s%d, ffi_r, ffi_o)' % (d.tag, index))
                elif p.ann in ('bytearray', 'c_mut_void_p'):
                    out.append('    ffi_o = ffi_put_%s(%s, ffi_r, ffi_o)' % (d.tag, p.name))
            for index, p in structs:
                out.append('    %s._load(bytes(ffi_s%d))' % (p.name, index))
            if d.result is None:
                return out
            out.append('    ffi_rc = %s__rc()' % d.export)
        elif d.result is None:
            out.append('    ' + call)
            for index, p in structs:
                out.append('    %s._load(bytes(ffi_s%d))' % (p.name, index))
        else:
            out.append('    ffi_rc = ' + call)
            for index, p in structs:
                out.append('    %s._load(bytes(ffi_s%d))' % (p.name, index))
        if d.result is None:
            return out
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
        if d.result == 'cstruct':
            out.append('    ffi_b = %s__cstruct(ffi_rc)' % d.export)
            out.append('    if len(ffi_b) == 0:')
            out.append('        raise RuntimeError("%s returned NULL")' % d.name)
            out.append('    ffi_obj = %s()' % d.result_struct)
            out.append('    ffi_obj._load(ffi_b)')
            out.append('    return ffi_obj')
        else:
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

    def build(self, cli, env=None):
        """Build the adapter object; returns its path, or None when no stub or struct was declared."""
        if not self.decls and not self.cstructs:
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
        for cs in self.cstructs.values():
            if cs.header is None:
                continue
            if cs.local_header:
                headers_local.setdefault(cs.header, Path(cs.directory) / cs.header)
            elif cs.header not in headers_system:
                headers_system.append(cs.header)
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
                # compile-c includes the standard headers before this source, so features.h has already run;
                # set its __USE_* switches directly for headers included below (struct tm's tm_gmtoff/tm_zone).
                '#ifndef __USE_MISC', '#define __USE_MISC 1', '#endif',
                '#ifndef __USE_POSIX', '#define __USE_POSIX 199506L', '#endif',
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
            ret = 'void' if d.result is None else result_ctype(d.result, d.result_struct_c)
            if not d.trust:
                asserts.append('_Static_assert(_Generic(&%s, %s (*)(%s): 1, default: 0), "ail_ffi: the declaration of %s does not match its C prototype");'
                               % (d.symbol, ret, ptypes, d.symbol))
            if any(t in ('c_long', 'c_ulong') for t in [p.ann for p in d.params] + [d.result]):
                asserts.append('_Static_assert(sizeof(long) == 8, "ail_ffi: c_long/c_ulong need a 64 bit long");')
            if any(t == 'c_size_t' or t == 'c_ssize_t' for t in [p.ann for p in d.params] + [d.result]):
                asserts.append('_Static_assert(sizeof(size_t) == 8, "ail_ffi: c_size_t needs a 64 bit size_t");')
            self._emit(d, functions, bodies)
        for cs in self.cstructs.values():
            if cs.header is None:
                continue
            for field in cs.fields:
                asserts.append('_Static_assert(offsetof(%s, %s) == %d && sizeof(((%s *)0)->%s) == %d, '
                               '"ail_cstruct %s.%s does not match its header");'
                               % (cs.c_name, field['name'], field['offset'], cs.c_name, field['name'],
                                  field['size'], cs.name, field['name']))
        for tag in tags:
            name = 'ffi_%s__errno' % tag
            functions[name] = dict(symbol=name, params=[], result='int')
            bodies.append('int64_t %s(void) { return ffi_last_errno; }' % name)
            name = 'ffi_%s__strerror' % tag
            functions[name] = dict(symbol=name, params=[['code', 'int']], result='str')
            bodies.append('ail_c_utf8_view %s(int64_t code) { const char *s = strerror((int)code); return (ail_c_utf8_view){(const unsigned char *)s, strlen(s)}; }' % name)
        if not functions:
            # a @cstruct with no stub still builds, to check its layout against the header
            marker = 'ffi_%s__cstruct_ok' % hashlib.sha1(' '.join(sorted(self.cstructs)).encode()).hexdigest()[:6]
            functions[marker] = dict(symbol=marker, params=[], result='int')
            bodies.append('int64_t %s(void) { return 0; }' % marker)
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
                                 '--interface', str(work / 'ffi_adapter.json'), '-o', str(out)],
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
            elif p.struct is not None and p.ann == 'bytes':
                params.append([n, 'borrowed_bytes'])
                c_params.append('const unsigned char *%s, size_t %s_n' % (n, n))
                call_args.append('(const %s *)(%s ? %s : ffi_empty)' % (p.struct_c, n, n))
            elif p.struct is not None:
                params.append([n, 'bytes'])
                c_params.append('const unsigned char *%s, size_t %s_n' % (n, n))
                call_args.append('(%s *)(void *)%s' % (p.struct_c, n))
                bytearrays.append(n)
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
            real = '((%s (*)(%s))%s)(%s)' % ('void' if res is None else result_ctype(res, d.result_struct_c), ', '.join(d.c_params()) or 'void',
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
        elif res in ('c_void_p', 'cstruct'):
            ret_kind, native_ret, convert = 'int', 'int64_t', '(int64_t)(intptr_t)r'
        elif res in ('c_char_p', 'c_mut_char_p'):
            ret_kind, native_ret, convert = 'str', 'ail_c_utf8_view', None
        lines = []
        if d.has_writable:
            # copy-in/copy-out: the result is the bytearrays' final contents; the C result is kept for `__rc`
            rc_type = 'double' if res in ('c_double', 'c_float') else 'int64_t'
            if res is not None:
                bodies.append('static %s ffi_rc_%s;' % (rc_type, d.export))
            lines.append('errno = 0;')
            lines.append(('%s r = %s;' % (result_ctype(res, d.result_struct_c), real)) if res is not None else real + ';')
            lines.append('ffi_last_errno = errno;')
            if res is not None:
                value = 'r' if rc_type == 'double' else ('(int64_t)(intptr_t)r' if res in ('c_void_p', 'cstruct') else
                                                         '(int64_t)r' if res != 'c_bool' else '(int64_t)r')
                lines.append('ffi_rc_%s = %s;' % (d.export, value))
            if res == 'cstruct':
                size = self.cstructs[d.result_struct].size
                bodies.append('static unsigned char ffi_cstruct_%s[%d];' % (d.export, size))
                bodies.append('static int ffi_cstruct_%s_ok;' % d.export)
                lines.append('ffi_cstruct_%s_ok = r != NULL;' % d.export)
                lines.append('if (r) memcpy(ffi_cstruct_%s, (const void *)r, %d);' % (d.export, size))
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
            if res == 'cstruct':
                size = self.cstructs[d.result_struct].size
                name = d.export + '__cstruct'
                bodies.append('ail_c_bytes_view %s(int64_t address) {\n'
                              '    if (!address || !ffi_cstruct_%s_ok) return (ail_c_bytes_view){NULL, 0};\n'
                              '    return (ail_c_bytes_view){ffi_cstruct_%s, %d};\n}'
                              % (name, d.export, d.export, size))
                functions[name] = dict(symbol=name, params=[['address', 'int']], result='bytes')
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
            lines.append('%s r = %s;' % (result_ctype(res, d.result_struct_c), real))
            lines.append('ffi_last_errno = errno;')
            if res == 'cstruct':
                size = self.cstructs[d.result_struct].size
                bodies.append('static unsigned char ffi_cstruct_%s[%d];' % (d.export, size))
                bodies.append('static int ffi_cstruct_%s_ok;' % d.export)
                lines.append('ffi_cstruct_%s_ok = r != NULL;' % d.export)
                lines.append('if (r) memcpy(ffi_cstruct_%s, (const void *)r, %d);' % (d.export, size))
            lines.append('return %s;' % convert)
        functions[d.export] = dict(symbol=d.export, params=params, result=ret_kind)
        bodies.append('%s %s(%s) {\n%s\n}' % (native_ret, d.export, ', '.join(c_params) or 'void', '\n'.join(lines)))
        if res == 'cstruct':
            size = self.cstructs[d.result_struct].size
            name = d.export + '__cstruct'
            bodies.append('ail_c_bytes_view %s(int64_t address) {\n'
                          '    if (!address || !ffi_cstruct_%s_ok) return (ail_c_bytes_view){NULL, 0};\n'
                          '    return (ail_c_bytes_view){ffi_cstruct_%s, %d};\n}'
                          % (name, d.export, d.export, size))
            functions[name] = dict(symbol=name, params=[['address', 'int']], result='bytes')

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
