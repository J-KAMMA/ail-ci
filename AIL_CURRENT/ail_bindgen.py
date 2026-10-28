#!/usr/bin/env python3
"""ail_bindgen: write `@extern` stubs (ail_ffi) from a simple C header, or a cbindgen-style header.

    python3 AIL_CURRENT/ail_bindgen.py tinyrs.h --lib ./libtinyrs.so -o tinyrs_ffi.py
    python3 AIL_CURRENT/ail_bindgen.py mylib.h --link mylib --check mylib_open=negative:OSError --errno mylib_open

It reads function prototypes and `struct` declarations it can lay out (comments, preprocessor lines,
`extern "C" {}`, enums, unions, bitfields, flexible array members and inline bodies are skipped) and maps
the C types as follows:

    int / long / size_t / int32_t / uintptr_t / enum ...   the c_* integer type of the same width (LP64)
    float double bool                                         c_float c_double c_bool
    const char *   char *                                     c_char_p   c_mut_char_p
    const uint8_t * / uint8_t * (unsigned char)              bytes / bytearray
    const T * / T * for a number T                           cptr(T) / ptr(T)
    a pointer followed by a length parameter                 the pointer plus length("name", C type)
    void *   const void *                                     c_void_p   c_const_void_p
    struct T * (a struct it can read)                         ptr(T) / cptr(T), with a generated @cstruct class
    T ** and pointers to an opaque or unknown typedef         ptr(c_void_p) and c_void_p, and the stub gets trust=True
    callbacks, variadics, struct by value, unknown typedefs  skipped, listed as a comment (pass --typedef NAME=c_int to name a typedef)

The result is a starting point: review it, add `check=` / `errno=` / `exc=` for the functions whose result is
an error code (--check NAME=KIND[:EXC] and --errno NAME do it from the command line).
"""
import argparse
import keyword
import re
import sys

INTS = {
    'char': 'c_int8', 'signed char': 'c_int8', 'unsigned char': 'c_uint8', 'short': 'c_short', 'short int': 'c_short',
    'unsigned short': 'c_ushort', 'unsigned short int': 'c_ushort', 'int': 'c_int', 'signed': 'c_int', 'signed int': 'c_int',
    'unsigned': 'c_uint', 'unsigned int': 'c_uint', 'long': 'c_long', 'long int': 'c_long', 'unsigned long': 'c_ulong',
    'unsigned long int': 'c_ulong', 'long long': 'c_longlong', 'long long int': 'c_longlong',
    'unsigned long long': 'c_ulonglong', 'unsigned long long int': 'c_ulonglong',
    'int8_t': 'c_int8', 'int16_t': 'c_int16', 'int32_t': 'c_int32', 'int64_t': 'c_int64',
    'uint8_t': 'c_uint8', 'uint16_t': 'c_uint16', 'uint32_t': 'c_uint32', 'uint64_t': 'c_uint64',
    'size_t': 'c_size_t', 'uintptr_t': 'c_size_t', 'ssize_t': 'c_ssize_t', 'intptr_t': 'c_ssize_t', 'ptrdiff_t': 'c_ssize_t',
    'off_t': 'c_long', 'time_t': 'c_long', 'pid_t': 'c_int', 'uid_t': 'c_uint', 'gid_t': 'c_uint', 'mode_t': 'c_uint',
}
OTHERS = {'float': 'c_float', 'double': 'c_double', 'bool': 'c_bool', '_Bool': 'c_bool'}
LENGTH_NAMES = re.compile(r'^(n|len|length|size|count|num|nbytes|nmemb|cap|capacity|buflen|bufsize)$|(_len|_n|_size|_count|_cap|len|size)$',
                          re.I)
LENGTH_TYPES = ('c_size_t', 'c_ssize_t', 'c_int', 'c_uint', 'c_long', 'c_ulong', 'c_int32', 'c_uint32', 'c_int64', 'c_uint64')
QUALIFIERS = {'const', 'volatile', 'restrict', '__restrict', '__restrict__', 'register'}


class Skip(Exception):
    pass


def strip_source(text):
    text = text.replace('\\\n', ' ')
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', ' ', text)
    text = re.sub(r'(?m)^\s*#.*$', ' ', text)
    text = re.sub(r'extern\s+"C"\s*\{', ' ', text)
    text = re.sub(r'__attribute__\s*\(\(.*?\)\)', ' ', text)
    text = re.sub(r'__declspec\s*\([^)]*\)', ' ', text)
    out, depth, last = [], 0, ''
    for ch in text:
        if ch == '{':
            depth += 1
            continue
        if ch == '}':
            if depth:
                depth -= 1
                if depth == 0:
                    out.append(';' if last == ')' else ' ')
            continue
        if depth == 0:
            out.append(ch)
            if not ch.isspace():
                last = ch
    return ''.join(out)


def split_top(text, sep=','):
    parts, depth, current = [], 0, []
    for ch in text:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    return [p.strip() for p in parts]


STRUCT_RE = re.compile(r'\b(typedef\s+)?(struct|union)\s*([A-Za-z_]\w*)?\s*\{([^{}]*)\}\s*([A-Za-z_]\w*)?\s*;', re.S)
ARRAY_RE = re.compile(r'^(?P<base>.*?)\b(?P<name>[A-Za-z_]\w*)\s*\[\s*(?P<count>[^\]]*)\s*\]$')


def clean_structs(text):
    """Comments, preprocessor lines and attributes removed; braces and struct bodies kept."""
    text = text.replace('\\\n', ' ')
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', ' ', text)
    text = re.sub(r'(?m)^\s*#.*$', ' ', text)
    text = re.sub(r'extern\s+"C"\s*\{', ' ', text)
    text = re.sub(r'__attribute__\s*\(\(.*?\)\)', ' ', text)
    text = re.sub(r'__declspec\s*\([^)]*\)', ' ', text)
    return text


def struct_keys(structs):
    keys = set()
    for item in structs:
        if item['tag']:
            keys.add('STRUCT_' + item['tag'])
        if item['alias']:
            keys.add(item['alias'])
    return keys


def read_struct_field(statement, typedefs, known):
    field = None
    array = ARRAY_RE.match(statement)
    if array:
        field = array.group('name')
        base = parse_type(array.group('base'), typedefs, False)
        count = array.group('count').strip()
        if count == '' or (count.isdigit() and int(count) <= 0):
            raise Skip('flexible array member %r is not supported' % field)
        if not count.isdigit():
            raise Skip('field %r has an unsupported array length' % field)
        if base.stars == 0 and base.base in known:
            raise Skip('nested by-value array of structs in field %r is not supported' % field)
        if base.stars:
            return field, 'c_array(c_void_p, %d)' % int(count)
        ctype = scalar(base.base, typedefs)
        if ctype is None:
            raise Skip('field %r has an unknown type %r' % (field, base.base))
        return field, 'c_array(%s, %d)' % (ctype, int(count))
    t = parse_type(statement, typedefs, True)
    field = t.name
    if field is None:
        raise Skip('a field has no name')
    if t.stars == 0 and t.base in known:
        raise Skip('nested struct field %r by value is not supported' % field)
    if t.stars:
        return field, 'c_void_p'
    ctype = scalar(t.base, typedefs)
    if ctype is None:
        raise Skip('field %r has an unknown type %r' % (field, t.base))
    return field, ctype


def read_structs(text, typedefs, skipped):
    """The structs bindgen can lay out: @cstruct fields in declaration order."""
    matches = list(STRUCT_RE.finditer(clean_structs(text)))
    raw = []
    for match in matches:
        raw.append(dict(typedef=bool(match.group(1)), kind=match.group(2), tag=match.group(3),
                        body=match.group(4), alias=match.group(5)))
    known = struct_keys([item for item in raw if item['kind'] == 'struct'])
    out = []
    for item in raw:
        shown = item['alias'] or item['tag'] or 'anonymous'
        if item['kind'] == 'union':
            skipped.append('# skipped struct %s: union %s is not supported' % (shown, shown))
            continue
        if not item['tag'] and not item['alias']:
            skipped.append('# skipped struct anonymous: a struct needs a name')
            continue
        cls = item['tag'] or item['alias']
        if keyword.iskeyword(cls) or not cls.isidentifier():
            skipped.append('# skipped struct %s: %r is not a usable Python name' % (shown, cls))
            continue
        fields, reason = [], None
        for statement in split_top(item['body'], ';'):
            statement = ' '.join(statement.split())
            if not statement:
                continue
            if ':' in statement:
                reason = 'bitfield field %r is not supported' % statement
                break
            try:
                field, annotation = read_struct_field(statement, typedefs, known)
            except Skip as why:
                reason = str(why)
                break
            if keyword.iskeyword(field):
                reason = 'field name %r is a Python keyword' % field
                break
            fields.append((field, annotation))
        if reason is not None:
            skipped.append('# skipped struct %s: %s' % (shown, reason))
            continue
        if not fields:
            skipped.append('# skipped struct %s: no readable fields' % shown)
            continue
        out.append(dict(class_name=pyname(cls), c_name='struct ' + item['tag'] if item['tag'] else item['alias'],
                        tag=item['tag'], alias=item['alias'], fields=fields))
    return out


class Typ:
    """A parsed C type: base words, pointer depth, const on the pointee, and the name (parameters)."""

    def __init__(self, base, stars, const, name=None):
        self.base, self.stars, self.const, self.name = base, stars, const, name


def parse_type(text, typedefs, want_name):
    text = re.sub(r'\b(struct|union|enum)\s+(\w+)', lambda m: ('ENUM_' if m.group(1) == 'enum' else 'STRUCT_') + m.group(2), text)
    if re.search(r'\(\s*\*', text):
        raise Skip('function pointer (callback)')
    text = re.sub(r'\[[^\]]*\]', ' * ', text)           # an array parameter is a pointer
    stars = text.count('*')
    const = bool(re.search(r'\bconst\b', text.split('*')[0])) if stars else False
    words = [w for w in re.findall(r'[A-Za-z_]\w*', text) if w not in QUALIFIERS]
    known = set(INTS) | set(OTHERS) | set(typedefs) | {'void', 'char', 'int', 'long', 'short', 'unsigned', 'signed', 'float', 'double'}
    name = None
    tagged = ('STRUCT_', 'ENUM_')
    if want_name and len(words) > 1 and words[-1] not in known and not words[-1].startswith(tagged):
        name = words.pop()
    elif want_name and len(words) == 1 and stars and words[0] not in known and not words[0].startswith(tagged):
        # `foo *p` where foo is an unknown typedef reads as a pointer to foo with no name
        pass
    return Typ(' '.join(words), stars, const, name)


def scalar(base, typedefs):
    if base in typedefs:
        return typedefs[base]
    if base in INTS:
        return INTS[base]
    if base in OTHERS:
        return OTHERS[base]
    if base.startswith('ENUM_'):
        return 'c_int'
    return None


def convert_param(t, nxt, typedefs, structs):
    """(annotation text, trusted?, the length parameter's C type or None)"""
    found = structs.get(t.base)
    if t.stars == 0:
        if t.base == 'void':
            raise Skip('void parameter')
        if found:
            raise Skip('struct %s by value' % found)
        c = scalar(t.base, typedefs)
        if c is None:
            raise Skip('unknown or struct-by-value type %r (use --typedef NAME=c_type)' % t.base)
        return c, False, None
    length = None
    if not found and nxt is not None and nxt.stars == 0 and scalar(nxt.base, typedefs) in LENGTH_TYPES and nxt.name and LENGTH_NAMES.search(nxt.name):
        length = scalar(nxt.base, typedefs)
    if t.stars >= 3:
        raise Skip('pointer depth %d' % t.stars)
    if t.stars == 2:
        return 'ptr(c_void_p)', True, None
    if found:
        return ('cptr(%s)' if t.const else 'ptr(%s)') % found, False, None
    c = scalar(t.base, typedefs)
    if t.base == 'char':
        if length and not t.const:
            return 'bytearray', False, length
        return ('c_char_p' if t.const else 'c_mut_char_p'), False, None
    if t.base == 'void':
        if length:
            return ('c_const_void_p' if t.const else 'c_mut_void_p'), False, length
        return ('c_const_void_p' if t.const else 'c_void_p'), False, None
    if c == 'c_uint8':
        return ('bytes' if t.const else 'bytearray'), False, length
    if c is not None:
        return ('cptr(%s)' if t.const else 'ptr(%s)') % c, False, length
    return 'c_void_p', True, None                        # struct or unknown typedef pointer: an opaque handle


def convert_result(t, typedefs, structs):
    found = structs.get(t.base)
    if t.stars == 0:
        if t.base == 'void':
            return 'None', False
        if found:
            raise Skip('struct %s by value' % found)
        c = scalar(t.base, typedefs)
        if c is None:
            raise Skip('unknown or struct result type %r' % t.base)
        return c, False
    if t.stars == 1 and found:
        return found, False
    if t.stars == 1 and t.base == 'char':
        return ('c_char_p' if t.const else 'c_mut_char_p'), False
    if t.stars == 1 and t.base == 'void':
        return 'c_void_p', False
    return 'c_void_p', True


def pyname(name):
    return name + '_' if keyword.iskeyword(name) or name in ('None', 'True', 'False') else name


def generate(text, header, lib=None, link=None, checks=None, errnos=(), typedefs=None):
    checks, typedefs = checks or {}, typedefs or {}
    out, skipped, seen = [], [], set()
    struct_items = read_structs(text, typedefs, skipped)
    struct_map = {}
    for item in struct_items:
        if item['tag']:
            struct_map['STRUCT_' + item['tag']] = item['class_name']
        if item['alias']:
            struct_map[item['alias']] = item['class_name']
    for item in struct_items:
        options = []
        if header:
            options.append('header=%r' % header)
        options.append('name=%r' % item['c_name'])
        out.append('@cstruct(%s)' % ', '.join(options))
        out.append('class %s:' % item['class_name'])
        for field, annotation in item['fields']:
            out.append('    %s: %s' % (field, annotation))
        out.append('')
    body = strip_source(text)
    for statement in body.split(';'):
        statement = ' '.join(statement.split())
        if not statement or '(' not in statement:
            continue
        if re.search(r'\bstatic\b', statement):
            continue                                      # static functions have no symbol to link
        statement = re.sub(r'\b(extern|inline|__inline__|__inline)\b', ' ', statement).strip()
        if re.match(r'(typedef|struct\s+\w*\s*$|union\s+\w*\s*$|enum\s+\w*\s*$)', statement):
            continue
        head, _, rest = statement.partition('(')
        m = re.search(r'([A-Za-z_]\w*)\s*$', head)
        if not m:
            continue
        name, ret_text = m.group(1), head[:m.start()].strip()
        arg_text = rest[:rest.rindex(')')] if ')' in rest else rest
        try:
            if not ret_text:
                raise Skip('no result type')
            args = [] if arg_text.strip() in ('', 'void') else split_top(arg_text)
            if any(a == '...' for a in args):
                raise Skip('variadic')
            types = [parse_type(a, typedefs, True) for a in args]
            for index, t in enumerate(types):
                if t.name is None:
                    t.name = 'a%d' % index
            result, trusted = convert_result(parse_type(ret_text, typedefs, False), typedefs, struct_map)
            params, index = [], 0
            while index < len(types):
                t = types[index]
                nxt = types[index + 1] if index + 1 < len(types) else None
                annotation, t_trusted, length = convert_param(t, nxt, typedefs, struct_map)
                trusted = trusted or t_trusted
                params.append('%s: %s' % (pyname(t.name), annotation))
                if length:
                    params.append('%s: length(%r%s)' % (pyname(nxt.name), pyname(t.name), '' if length == 'c_size_t' else ', ' + length))
                    index += 1
                index += 1
        except Skip as why:
            skipped.append('# skipped %s: %s' % (name, why))
            continue
        if name in seen:
            continue
        seen.add(name)
        options = []
        if lib:
            options.append('lib=%r' % lib)
        if header:
            options.append('header=%r' % header)
            if trusted:
                options.append('trust=True')
        if name in checks:
            kind, _, exc = checks[name].partition(':')
            options.append('check=%r' % kind)
            if name in errnos:
                options.append('errno=True')
            if exc:
                options.append('exc=%s' % exc)
        if trusted:
            out.append('# %s: a struct or opaque pointer is in the prototype, so its prototype is not compared (trust=True)' % name)
        out.append('@extern(%s)' % ', '.join(options))
        out.append('def %s(%s) -> %s: ...' % (pyname(name), ', '.join(params), result))
    lines = ['# generated by AIL_CURRENT/ail_bindgen.py from %s -- review before use' % (header or 'a header'),
             'from ail_ffi import *']
    if link:
        lines.append('link(%s)' % ', '.join(repr(x) for x in link))
    lines.append('')
    return '\n'.join(lines + out + skipped) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description='write ail_ffi @extern stubs from a C header')
    ap.add_argument('header')
    ap.add_argument('--lib', help='library for every stub: a name (-lNAME) or a path')
    ap.add_argument('--link', action='append', help='emit link("NAME") instead of lib= (repeatable)')
    ap.add_argument('--header-name', help='name used in header= (default: the file name)')
    ap.add_argument('--check', action='append', default=[], help='FUNC=KIND[:EXC] (negative nonzero null minus1)')
    ap.add_argument('--errno', action='append', default=[], help='FUNC: read errno on failure (needs --check)')
    ap.add_argument('--typedef', action='append', default=[], help='NAME=c_type for an unknown typedef')
    ap.add_argument('-o', '--output')
    args = ap.parse_args(argv)
    with open(args.header, encoding='utf-8') as stream:
        text = stream.read()
    name = args.header_name or args.header.replace('\\', '/').rsplit('/', 1)[-1]
    checks = dict(c.split('=', 1) for c in args.check)
    typedefs = dict(t.split('=', 1) for t in args.typedef)
    result = generate(text, name, lib=args.lib, link=args.link, checks=checks, errnos=set(args.errno), typedefs=typedefs)
    if args.output:
        with open(args.output, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(result)
    else:
        sys.stdout.write(result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
