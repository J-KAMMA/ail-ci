"""Canonical typed, borrowed-argument function pointer signatures."""
import ast
import hashlib
import json
import keyword
import re

PREFIX = 'callable:'
_PARAMS = {'int', 'float', 'str', 'bytes', 'bytearray', 'binaryfile', 'tcpsocket', 'exception', 'array', 'flist', 'slist', 'blist'}
_RESULTS = {'int', 'float', 'noret', 'str', 'bytes', 'bytearray', 'binaryfile', 'tcpsocket', 'exception', 'list', 'flist', 'slist', 'blist'}
_RESERVED = {'int', 'float', 'str', 'bytes', 'bytearray', 'binaryfile', 'tcpsocket', 'exception', 'bool', 'void', 'None', 'Callable',
             'Optional', 'list', 'dict', 'tuple', 'set', 'Any'}
_SOURCE = {'array': 'list[int]', 'list': 'list[int]', 'flist': 'list[float]', 'slist': 'list[str]', 'blist': 'list[bytes]', 'noret': 'void'}
_C = {'int': 'int64_t', 'float': 'double', 'str': 'ail_str',
      'bytes': 'ail_bytes', 'bytearray': 'ail_bytearray *', 'binaryfile': 'ail_binaryfile *', 'tcpsocket': 'ail_tcpsocket *', 'exception': 'ail_exception *', 'array': 'const int64_t*, int64_t',
      'flist': 'ail_flist', 'slist': 'ail_slist', 'blist': 'ail_blist *', 'noret': 'void'}
for _element in ('bytearray', 'binaryfile', 'tcpsocket', 'exception'):
    _kind = 'handle_list:' + _element
    _PARAMS.add(_kind)
    _RESULTS.add(_kind)
    _SOURCE[_kind] = 'list[' + _element + ']'
    _C[_kind] = 'ail_hlist_' + _element + ' *'



def _encode(params, result):
    return PREFIX + json.dumps([params, result], separators=(',', ':'))


def _struct_kind(kind):
    name = kind.removeprefix('struct:') if isinstance(kind, str) else ''
    return (isinstance(kind, str) and kind.startswith('struct:')
            and bool(re.fullmatch(r'[A-Za-z_]\w*', name))
            and name.isidentifier() and not keyword.iskeyword(name) and name not in _RESERVED)


def parse(annotationAST, structs=()):
    """Parse Callable annotations; unrelated annotations return None."""
    node = annotationAST
    if not (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id == 'Callable'):
        if isinstance(node, ast.Name) and node.id == 'Callable':
            raise ValueError('Callable requires [[parameter types], result type]')
        return None
    if not (isinstance(node.slice, ast.Tuple) and len(node.slice.elts) == 2
            and isinstance(node.slice.elts[0], ast.List)):
        raise ValueError('Callable requires [[parameter types], result type]')
    params, result = node.slice.elts
    def kind(item, result=False):
        if isinstance(item, ast.Name):
            return (item.id if item.id in ('int', 'float', 'str', 'bytes', 'bytearray', 'binaryfile', 'tcpsocket', 'exception')
                    else 'struct:' + item.id if item.id in structs else None)
        if (isinstance(item, ast.Subscript) and isinstance(item.value, ast.Name)
                and item.value.id == 'list' and isinstance(item.slice, ast.Name)):
            return {'int': 'list' if result else 'array', 'float': 'flist', 'str': 'slist', 'bytes': 'blist',
                    **{element: 'handle_list:' + element for element in ('bytearray', 'binaryfile', 'tcpsocket', 'exception')}}.get(item.slice.id)
        return None
    kinds = [kind(item) for item in params.elts]
    result_kind = 'noret' if isinstance(result, ast.Name) and result.id == 'void' else kind(result, result=True)
    if any(item not in _PARAMS and not _struct_kind(item) for item in kinds) or result_kind not in _RESULTS and not _struct_kind(result_kind):
        raise ValueError('unsupported Callable parameter or result type')
    return _encode(kinds, result_kind)


def unpack(kind):
    if not isinstance(kind, str) or not kind.startswith(PREFIX):
        return None
    try:
        value = json.loads(kind[len(PREFIX):])
        if (not isinstance(value, list) or len(value) != 2
                or not isinstance(value[0], list)
                or any(not isinstance(item, str) or item not in _PARAMS and not _struct_kind(item) for item in value[0])
                or not isinstance(value[1], str) or value[1] not in _RESULTS and not _struct_kind(value[1])
                or _encode(*value) != kind):
            raise ValueError('noncanonical Callable kind')
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError('malformed Callable kind') from exc
    return tuple(value[0]), value[1]


def _signature(kind):
    signature = unpack(kind)
    if signature is None:
        raise ValueError('expected Callable kind')
    return signature


def annotation(kind):
    params, result = _signature(kind)
    def source(item):
        return item.removeprefix('struct:') if _struct_kind(item) else _SOURCE.get(item, item)
    return 'Callable[[' + ', '.join(map(source, params)) + '], ' + source(result) + ']'


def struct_names(kind):
    params, result = _signature(kind)
    return {item.partition(':')[2] for item in (*params, result) if _struct_kind(item)}


def ctype(kind):
    _signature(kind)
    return 'ail_fn_' + hashlib.sha256(kind.encode('utf-8')).hexdigest()[:24]


def declaration(kind, struct_types=None):
    params, result = _signature(kind)
    def ctype_for(item):
        if not _struct_kind(item):
            return _C[item]
        name = item.partition(':')[2]
        c_type = (struct_types or {}).get(name)
        if not isinstance(c_type, str) or not re.fullmatch(r'[A-Za-z_]\w*', c_type):
            raise ValueError('Callable struct type requires a known C declaration: ' + name)
        return c_type + ' *'
    args = [ctype_for(item) for item in params]
    if result in ('list', 'flist'):
        args.extend(('int64_t*' if result == 'list' else 'double*', 'int64_t'))
    return_type = 'int64_t' if result in ('list', 'flist') else ctype_for(result)
    return f'typedef {return_type} (*{ctype(kind)})({", ".join(args) or "void"});'


def valid(kind):
    try:
        return unpack(kind) is not None
    except ValueError:
        return False
