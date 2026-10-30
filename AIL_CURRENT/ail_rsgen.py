#!/usr/bin/env python3
"""ail_rsgen: emit a Rust binding crate from an AIL `build --lib NAME` header.

    python3 AIL_CURRENT/ail_rsgen.py NAME.h -o bindings
    cargo run --offline                          # in a host that depends on `bindings`

The input is the header that `ail build --lib NAME` (or `ail_cargo.py build`) writes: every
exported C function returns a status and puts its result in trailing `out` parameters, with
`NAME_last_error()` returning "Kind: text" after a failure.  The generated crate has

    src/lib.rs     an `extern "C"` block with the raw symbols, plus one safe function per
                   export that returns Result<T, Error> (and frees str/bytes/list results)
    build.rs       links libNAME.a, found next to NAME.h by default (override AIL_RS_LIB_DIR)
    Cargo.toml     a plain rlib crate (std only)

The generated Rust surface uses i64 for int, f64 for float, bool for bool, &str for str,
&[u8] for bytes, &[i64] / &[f64] for the lists, and a `#[repr(C)]` struct for a dataclass.
`Error` carries the status code, the kind (ValueError, OSError, ...) and the text of
NAME_last_error().  Inputs are copied/borrowed only for the call; outputs are copied out of
the library's buffer before it is freed.  No network is used.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import ail_bindgen  # noqa: E402

QUALIFIERS = {'const', 'volatile', 'restrict', '__restrict', '__restrict__', 'register'}
SCALAR_RUST = {'int64_t': 'i64', 'int32_t': 'i32', 'int16_t': 'i16', 'int8_t': 'i8',
               'uint64_t': 'u64', 'uint32_t': 'u32', 'uint16_t': 'u16', 'uint8_t': 'u8',
               'size_t': 'usize', 'ssize_t': 'isize', 'intptr_t': 'isize', 'uintptr_t': 'usize',
               'int': 'i32', 'unsigned': 'u32', 'long': 'i64', 'unsigned long': 'u64',
               'double': 'f64', 'float': 'f32', 'bool': 'bool', 'char': 'i8'}
BUFFER_RUST = {'uint8_t': 'u8', 'int64_t': 'i64', 'double': 'f64'}
LIST_RUST = {'uint8_t': 'u8', 'int64_t': 'i64', 'double': 'f64'}
KINDS = {'VALUE': 'ValueError', 'ZERO_DIVISION': 'ZeroDivisionError', 'INDEX': 'IndexError',
         'KEY': 'KeyError', 'EOF': 'EOFError', 'OS': 'OSError', 'RUNTIME': 'RuntimeError',
         'INTERNAL': 'InternalError', 'ARGUMENT': 'InvalidArgument'}
KEYWORDS = set('as break const continue crate else enum extern false fn for if impl in let loop match mod move mut '
               'pub ref return self Self static struct super trait true type unsafe use where while async await dyn '
               'abstract become box do final override priv typeof unsized virtual yield try union macro_rules'.split())


class RsGenError(ValueError):
    pass


def rust_name(name):
    return 'r#' + name if name in KEYWORDS else name


def rust_string(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return re.sub(r'//[^\n]*', ' ', text)


def library_name(text):
    match = re.search(r'\b([A-Za-z_]\w*)_last_error\s*\(', text)
    if match is None:
        raise RsGenError('not an AIL library header: no NAME_last_error() declaration')
    return match.group(1)


def status_constants(text, lib):
    prefix = lib.upper() + '_'
    found = []
    for name, value in re.findall(r'#define\s+([A-Za-z_]\w*)\s+(-?\d+)\b', text):
        if name.startswith(prefix):
            short = name[len(prefix):]
            if short == 'OK' or short.startswith('ERR_'):
                found.append((short, int(value)))
    if not found:
        raise RsGenError('header has no %sOK / %sERR_* status constants' % (prefix, prefix))
    names = {name for name, _ in found}
    if 'ERR_ARGUMENT' not in names:
        found.append(('ERR_ARGUMENT', 9))
    return found


def parse_structs(text, lib):
    structs, order = {}, []
    for match in re.finditer(r'typedef\s+struct\s+(\w+)\s*\{(.*?)\}\s*(\w+)\s*;', text, re.S):
        c_name, body, typedef = match.group(1), match.group(2), match.group(3)
        if c_name != typedef and not typedef.startswith(lib + '_'):
            continue
        fields = []
        for statement in body.split(';'):
            statement = ' '.join(statement.split())
            if not statement:
                continue
            field = re.match(r'(.+?)\s*\b([A-Za-z_]\w*)$', statement)
            if field is None:
                raise RsGenError('struct %s: cannot read field %r' % (c_name, statement))
            c_type, field_name = field.group(1).strip(), field.group(2)
            if c_type not in ('int64_t', 'int32_t', 'double', 'float', 'bool'):
                raise RsGenError('struct %s: unsupported field type %r' % (c_name, c_type))
            fields.append((SCALAR_RUST[c_type], field_name))
        name = typedef[len(lib) + 1:] if typedef.startswith(lib + '_') else typedef
        structs[typedef] = {'rust': name, 'fields': fields}
        order.append(typedef)
    return structs, order


def c_param(text):
    text = re.sub(r'\[[^\]]*\]', ' * ', text)
    stars = text.count('*')
    const = bool(re.search(r'\bconst\b', text.split('*')[0])) if stars else False
    words = [word for word in re.findall(r'[A-Za-z_]\w*', text) if word not in QUALIFIERS]
    if len(words) < 2:
        raise RsGenError('cannot read parameter %r' % text)
    name = words[-1]
    base = ' '.join(words[:-1])
    return {'base': base, 'stars': stars, 'const': const, 'name': name, 'text': text}


def ffi_type(param, structs):
    base, stars = param['base'], param['stars']
    if stars == 0:
        if base not in SCALAR_RUST:
            raise RsGenError('unsupported C type %r' % param['text'])
        return SCALAR_RUST[base]
    if base == 'char':
        inner = '*const c_char' if param['const'] or stars > 1 else '*mut c_char'
        if stars == 1:
            return inner
        return '*mut *mut c_char' if stars == 2 else '*mut ' + inner
    if base == 'void':
        return '*mut c_void'
    if base in SCALAR_RUST:
        scalar = SCALAR_RUST[base]
        pointer = ('*const %s' if param['const'] else '*mut %s') % scalar
        return pointer if stars == 1 else '*mut ' + pointer
    if base in structs:
        return ('*const %s' if param['const'] else '*mut %s') % structs[base]['rust']
    raise RsGenError('unsupported pointer type %r' % param['text'])


def function_prototypes(body, lib):
    result = []
    for statement in body.split(';'):
        statement = ' '.join(statement.split())
        if not statement or '(' not in statement:
            continue
        if re.match(r'(typedef|struct\s+\w*\s*$|union\s+\w*\s*$|enum\s+\w*\s*$)', statement):
            continue
        statement = re.sub(r'\b(extern|inline|__inline__|__inline)\b', ' ', statement).strip()
        head, _, rest = statement.partition('(')
        match = re.search(r'([A-Za-z_]\w*)\s*$', head)
        if match is None or ')' not in rest:
            continue
        c_name = match.group(1)
        if not c_name.startswith(lib + '_'):
            continue
        export = c_name[len(lib) + 1:]
        if export in ('last_error', 'free'):
            continue
        arguments = rest[:rest.rindex(')')]
        params = [] if arguments.strip() in ('', 'void') else [c_param(part) for part in ail_bindgen.split_top(arguments)]
        result.append((export, c_name, params))
    return result


def logical(export, c_name, params, structs):
    """Split C parameters into the safe inputs and the result kind."""
    result_kind, consumed = 'void', 0
    if params:
        last = params[-1]
        if last['name'] == 'out_len' and last['stars'] == 1 and last['base'] == 'size_t' and len(params) >= 2:
            before = params[-2]
            if before['name'] == 'out' and before['stars'] == 2 and before['base'] in BUFFER_RUST:
                result_kind = {'uint8_t': 'bytes', 'int64_t': 'ints', 'double': 'floats'}[before['base']]
                consumed = 2
        if not consumed:
            last = params[-1]
            if last['name'] == 'out' and last['stars'] == 1:
                if last['base'] in SCALAR_RUST and last['base'] != 'void':
                    result_kind = {'bool': 'bool', 'double': 'float', 'float': 'float'}.get(last['base'], 'int')
                    consumed = 1
            elif last['name'] == 'out' and last['stars'] == 2 and last['base'] == 'char':
                result_kind, consumed = 'str', 1
    inputs = params[:len(params) - consumed] if consumed else params[:]
    specs = []
    index = 0
    while index < len(inputs):
        param = inputs[index]
        following = inputs[index + 1] if index + 1 < len(inputs) else None
        has_length = (following is not None and following['name'] == param['name'] + '_len'
                      and following['stars'] == 0 and following['base'] == 'size_t')
        if param['stars'] == 0:
            if param['base'] not in SCALAR_RUST:
                raise RsGenError('%s: unsupported parameter %r' % (export, param['text']))
            kind = 'bool' if param['base'] == 'bool' else 'float' if param['base'] in ('double', 'float') else 'int'
            specs.append({'kind': kind, 'name': param['name'], 'param': param, 'extra': []})
            index += 1
        elif param['stars'] == 1 and param['base'] == 'char' and param['const']:
            specs.append({'kind': 'str', 'name': param['name'], 'param': param, 'extra': []})
            index += 1
        elif param['stars'] == 1 and param['base'] in LIST_RUST and param['const'] and has_length:
            kind = {'uint8_t': 'bytes', 'int64_t': 'ints', 'double': 'floats'}[param['base']]
            specs.append({'kind': kind, 'name': param['name'], 'param': param, 'extra': [following]})
            index += 2
        elif param['stars'] == 1 and param['base'] in structs:
            specs.append({'kind': 'struct', 'name': param['name'], 'param': param,
                          'extra': [], 'struct': structs[param['base']]['rust']})
            index += 1
        else:
            raise RsGenError('%s: unsupported parameter %r' % (export, param['text']))
    return specs, result_kind, params[len(params) - consumed:] if consumed else []


def wrapper(export, c_name, specs, result_kind, outs, structs, lib):
    arguments, declarations, prelude = [], [], []
    for spec in specs:
        name = rust_name(spec['name'])
        kind = spec['kind']
        if kind in ('int', 'float', 'bool'):
            rust_type = {'int': 'i64', 'float': 'f64', 'bool': 'bool'}[kind]
            arguments.append(name)
            declarations.append('%s: %s' % (name, rust_type))
        elif kind == 'str':
            local = 'c_' + spec['name']
            prelude.append('    let %s = CString::new(%s).map_err(|_| '
                           'Error::new(ERR_ARGUMENT, "argument %s contains a NUL byte"))?;'
                           % (local, name, spec['name']))
            arguments.append(local + '.as_ptr()')
            declarations.append('%s: &str' % name)
        elif kind in ('bytes', 'ints', 'floats'):
            element = {'bytes': 'u8', 'ints': 'i64', 'floats': 'f64'}[kind]
            arguments += [name + '.as_ptr()', name + '.len()']
            declarations.append('%s: &[%s]' % (name, element))
        elif kind == 'struct':
            arguments.append(name)
            declarations.append('%s: &%s' % (name, spec['struct']))
    result_type, result_code = '()', '    Ok(())'
    if result_kind == 'int':
        prelude.append('    let mut out: i64 = 0;')
        arguments.append('&mut out')
        result_type, result_code = 'i64', '    Ok(out)'
    elif result_kind == 'float':
        prelude.append('    let mut out: f64 = 0.0;')
        arguments.append('&mut out')
        result_type, result_code = 'f64', '    Ok(out)'
    elif result_kind == 'bool':
        prelude.append('    let mut out: bool = false;')
        arguments.append('&mut out')
        result_type, result_code = 'bool', '    Ok(out)'
    elif result_kind == 'str':
        prelude.append('    let mut out: *mut c_char = std::ptr::null_mut();')
        arguments.append('&mut out')
        result_type = 'String'
        result_code = ('    if out.is_null() {\n        Ok(String::new())\n    } else {\n'
                       '        let text = unsafe { CStr::from_ptr(out).to_string_lossy().into_owned() };\n'
                       '        unsafe { %s_free(out as *mut c_void); }\n        Ok(text)\n    }' % lib)
    elif result_kind in ('bytes', 'ints', 'floats'):
        element = {'bytes': 'u8', 'ints': 'i64', 'floats': 'f64'}[result_kind]
        prelude.append('    let mut out: *mut %s = std::ptr::null_mut();' % element)
        prelude.append('    let mut out_len: usize = 0;')
        arguments += ['&mut out', '&mut out_len']
        result_type = 'Vec<%s>' % element
        result_code = ('    let value = if out.is_null() || out_len == 0 {\n        Vec::new()\n    } else {\n'
                       '        unsafe { std::slice::from_raw_parts(out, out_len).to_vec() }\n    };\n'
                       '    if !out.is_null() {\n        unsafe { %s_free(out as *mut c_void); }\n'
                       '    }\n    Ok(value)' % lib)
    lines = ['/// `%s` from the AIL library; the error text comes from `%s_last_error()`.' % (export, lib),
             'pub fn %s(%s) -> Result<%s, Error> {' % (rust_name(export), ', '.join(declarations), result_type)]
    lines += prelude
    lines.append('    let status = unsafe { %s(%s) };' % (c_name, ', '.join(arguments)))
    lines.append('    if status != 0 {\n        return Err(Error::last_error(status));\n    }')
    lines.append(result_code)
    lines.append('}')
    return '\n'.join(lines)


def generate(header_text, lib, header_path=None):
    text = strip_comments(header_text)
    structs, struct_order = parse_structs(text, lib)
    constants = status_constants(header_text, lib)
    constant_names = {name for name, _ in constants}
    status = ['pub const %s: i32 = %d;' % (name, value) for name, value in constants]
    lines = ['/* generated by AIL_CURRENT/ail_rsgen.py from %s -- do not edit */' % (header_path or 'an AIL header'),
             '#![allow(clippy::not_unsafe_ptr_arg_deref)]', '',
             'use std::ffi::{c_char, c_void, CStr, CString};', '',
             'pub const OK: i32 = 0;']
    lines += [line for line in status if not line.startswith('pub const OK:')]
    lines += ['', '#[derive(Debug, Clone)]', 'pub struct Error {', '    pub code: i32,',
              '    pub kind: &\'static str,', '    pub message: String,', '}', '',
              'impl Error {', '    fn new(code: i32, message: impl Into<String>) -> Self {',
              '        Error { code, kind: kind_of(code), message: message.into() }', '    }',
              '    fn last_error(code: i32) -> Self {',
              '        let message = unsafe {',
              '            let pointer = %s_last_error();' % lib,
              '            if pointer.is_null() { String::new() } else { CStr::from_ptr(pointer).to_string_lossy().into_owned() }',
              '        };', '        Error::new(code, message)', '    }', '}', '',
              'fn kind_of(code: i32) -> &\'static str {', '    match code {']
    for name, value in constants:
        if name == 'OK':
            continue
        short = name[len('ERR_'):] if name.startswith('ERR_') else name
        lines.append('        %s => %s,' % (value, rust_string(KINDS.get(short, 'Error'))))
    lines += ['        _ => "Error",', '    }', '}', '',
              'impl std::fmt::Display for Error {',
              '    fn fmt(&self, f: &mut std::fmt::Formatter<\'_>) -> std::fmt::Result {',
              '        if self.message.is_empty() { write!(f, "{} (code {})", self.kind, self.code) } '
              'else { f.write_str(&self.message) }', '    }', '}',
              'impl std::error::Error for Error {}', '']
    if struct_order:
        for c_name in struct_order:
            info = structs[c_name]
            lines.append('#[repr(C)]')
            lines.append('pub struct %s {' % info['rust'])
            for rust_type, field in info['fields']:
                lines.append('    pub %s: %s,' % (rust_name(field), rust_type))
            lines.append('}')
            lines.append('')
    lines.append('pub fn last_error() -> String {')
    lines.append('    let message = unsafe {')
    lines.append('        let pointer = %s_last_error();' % lib)
    lines.append('        if pointer.is_null() { String::new() } else { CStr::from_ptr(pointer).to_string_lossy().into_owned() }')
    lines.append('    };')
    lines.append('    message')
    lines.append('}')
    lines.append('')
    lines.append('extern "C" {')
    lines.append('    fn %s_last_error() -> *const c_char;' % lib)
    lines.append('    fn %s_free(data: *mut c_void);' % lib)
    for export, c_name, params in function_prototypes(ail_bindgen.strip_source(header_text), lib):
        lines.append('    pub fn %s(%s) -> i32;' % (c_name, ', '.join(
            '%s: %s' % (rust_name(param['name']), ffi_type(param, structs)) for param in params)))
    lines.append('}')
    lines.append('')
    for export, c_name, params in function_prototypes(ail_bindgen.strip_source(header_text), lib):
        specs, result_kind, _outs = logical(export, c_name, params, structs)
        lines.append(wrapper(export, c_name, specs, result_kind, _outs, structs, lib))
        lines.append('')
    assert constant_names <= {name for name, _ in constants}
    return '\n'.join(lines)


def cargo_toml(lib, package):
    return ('[package]\nname = %s\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[lib]\nname = %s\npath = "src/lib.rs"\n\n[build-dependencies]\n'
            % (rust_string(package), rust_string(package)))


def build_rs(lib, header_dir):
    return '''use std::{env, path::PathBuf};

fn main() {
    let directory = env::var_os("AIL_RS_LIB_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(%s));
    println!("cargo:rustc-link-search=native={}", directory.display());
    println!("cargo:rustc-link-lib=static=%s");
    let native = env::var("AIL_RS_NATIVE_LIBS").unwrap_or_else(|_| "m,pthread".to_string());
    for library in native.split(|c| c == ',' || c == ':').filter(|s| !s.is_empty()) {
        println!("cargo:rustc-link-lib={}", library.trim());
    }
    println!("cargo:rerun-if-env-changed=AIL_RS_LIB_DIR");
    println!("cargo:rerun-if-env-changed=AIL_RS_NATIVE_LIBS");
}
''' % (rust_string(str(header_dir)), lib)


def write_crate(header, output, package=None):
    header = Path(header).expanduser().resolve()
    if not header.is_file():
        raise RsGenError('no such header: %s' % header)
    try:
        text = header.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as error:
        raise RsGenError('cannot read %s: %s' % (header, error)) from error
    lib = library_name(text)
    output = Path(output).expanduser().resolve()
    package = package or (re.sub(r'[^A-Za-z0-9_]+', '_', lib.lower()).strip('_') or 'ail') + '_bindings'
    if package[:1].isdigit():
        package = 'ail_' + package
    source = output / 'src'
    source.mkdir(parents=True, exist_ok=True)
    (output / 'Cargo.toml').write_text(cargo_toml(lib, package), encoding='utf-8')
    (output / 'build.rs').write_text(build_rs(lib, header.parent), encoding='utf-8')
    (source / 'lib.rs').write_text(generate(text, lib, header.name), encoding='utf-8')
    return {'schema': 1, 'library': lib, 'package': package, 'output': str(output),
            'files': [str(output / 'Cargo.toml'), str(output / 'build.rs'), str(source / 'lib.rs')]}


def main(argv=None):
    parser = argparse.ArgumentParser(description='emit a Rust binding crate from an AIL library header')
    parser.add_argument('header', metavar='NAME.h')
    parser.add_argument('-o', '--output', help='new crate directory (default: <name>_bindings beside the header)')
    parser.add_argument('--package', help='cargo package/lib name (default: <name>_bindings)')
    args = parser.parse_args(argv)
    output = args.output
    if output is None:
        try:
            text = Path(args.header).expanduser().read_text(encoding='utf-8')
            output = str(Path(args.header).expanduser().resolve().parent / (library_name(text) + '_bindings'))
        except (OSError, UnicodeError, RsGenError) as error:
            print('ail_rsgen: %s' % error, file=sys.stderr)
            return 1
    try:
        result = write_crate(args.header, output, args.package)
    except (RsGenError, OSError) as error:
        print('ail_rsgen: %s' % error, file=sys.stderr)
        return 1
    print('ail_rsgen: wrote %s (%s)' % (result['output'], ', '.join(Path(path).name for path in result['files'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
