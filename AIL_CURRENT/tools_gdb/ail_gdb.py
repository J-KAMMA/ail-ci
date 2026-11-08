"""gdb pretty-printers for AIL values.

Load with `gdb -x AIL_CURRENT/tools_gdb/ail_gdb.py --args ./program`, or in a
`gdb -batch` run.  Then `print x` shows a value as CPython 3.12's `repr(x)`
instead of the C struct behind it.

The printers only read memory.  They never call a function in the program and
never execute any of it.  Every loop is bounded by the value's own length field,
a bad pointer prints `<unreadable>` (never a guessed value), and a container
longer than 100 elements prints the first 100 and then `...`.
"""

import re

import gdb

MAX_ITEMS = 100
MAX_DEPTH = 16
MAX_TABLE = 10000000

# ail_obj's tag enum from the generated C (cruntime.py / ail_obj2.h).
T_UNBOUND, T_NONE, T_BOOL, T_INT, T_FLOAT, T_STR, T_LIST, T_TUPLE, T_DICT, T_SET = range(10)
T_FUNC, T_BOUND, T_ITER, T_CLASS, T_INST, T_EXC, T_RANGE, T_CELL, T_FROZENSET = range(10, 19)


class _Unreadable(Exception):
    pass


def _r(value):
    """The Python repr of VALUE, or the unreadable marker for a bad value."""
    try:
        return _format(value, 0)
    except (gdb.MemoryError, gdb.error, _Unreadable, ValueError, UnicodeError, OverflowError):
        return "<unreadable>"


def _type_name(t):
    if t.name:
        return t.name
    if t.tag:
        return t.tag
    try:
        s = t.strip_typedefs()
    except gdb.error:
        return ""
    return s.name or s.tag or ""


def _is_pointer(t):
    return t.strip_typedefs().code == gdb.TYPE_CODE_PTR


def _pointer_target(t):
    return t.strip_typedefs().target()


def _int(value):
    return int(value)


def _need_count(n):
    if n < 0:
        raise _Unreadable()
    return n


def _need_table(n):
    if n < 0 or n > MAX_TABLE:
        raise _Unreadable()
    return n


def _need_pointer(p, n):
    if n and _int(p) == 0:
        raise _Unreadable()
    return p


def _read_str(value):
    """`ail_str` (typed path: UTF-8 bytes; general path: UTF-16 code units)."""
    p = value["p"]
    n = _need_count(_int(value["n"]))
    flag = _int(value["bytes"]) != 0
    if n == 0:
        return "''"
    _need_pointer(p, n)
    width = _pointer_target(p.type).sizeof
    if flag and width != 1:
        # `bytes` marks a pure-ASCII buffer: the elements are uint8_t even
        # though the general path's ail_str.p has a uint16_t type.
        cp = p.cast(gdb.lookup_type("unsigned char").pointer())
        raw = bytearray(_int(cp[i]) & 0xFF for i in range(n))
        text = bytes(raw).decode("utf-8")
    elif flag or width == 1:
        raw = bytearray(_int(p[i]) & 0xFF for i in range(n))
        text = bytes(raw).decode("utf-8")
    else:
        units = [_int(p[i]) & 0xFFFF for i in range(n)]
        chars = []
        i = 0
        while i < len(units):
            u = units[i]
            if 0xD800 <= u <= 0xDBFF and i + 1 < len(units) and 0xDC00 <= units[i + 1] <= 0xDFFF:
                chars.append(chr(0x10000 + ((u - 0xD800) << 10) + (units[i + 1] - 0xDC00)))
                i += 2
            else:
                chars.append(chr(u))
                i += 1
        text = "".join(chars)
    return repr(text)


def _read_bytes(value):
    p = value["p"]
    n = _need_count(_int(value["n"]))
    if n == 0:
        return "b''"
    _need_pointer(p, n)
    raw = bytearray()
    for i in range(n):
        raw.append(_int(p[i]) & 0xFF)
    return repr(bytes(raw))


def _seq_body(p, n, kind, depth):
    n = _need_count(n)
    _need_pointer(p, n)
    count = min(n, MAX_ITEMS)
    parts = [_format(p[i], depth + 1) for i in range(count)]
    if n > MAX_ITEMS:
        parts.append("...")
    if kind == "tuple":
        return "(" + ", ".join(parts) + ("," if len(parts) == 1 else "") + ")"
    return "[" + ", ".join(parts) + "]"


def _read_typed_list(value, kind, depth):
    return _seq_body(value["p"], _int(value["n"]), kind, depth)


def _read_typed_dict(value, depth):
    table = value["table"] if _type_name(value.type) == "ail_sdict" else value
    order = table["order"]
    vals = table["val"]
    top = _need_table(_int(table["top"]))
    _need_pointer(order, top)
    parts = []
    seen = 0
    for j in range(top):
        key = order[j]
        if _int(key["n"]) < 0:          # a deleted entry's hole
            continue
        if seen >= MAX_ITEMS:
            parts.append("...")
            break
        parts.append("%s: %s" % (_format(key, depth + 1), repr(_int(vals[j]))))
        seen += 1
    return "{" + ", ".join(parts) + "}"


def _general_str(value):
    sv = value["sv"]
    backing = sv["backing"]
    off = _int(sv["off"])
    ln = _need_count(_int(sv["len"]))
    if ln == 0:
        return "''"
    _need_pointer(backing, 1)
    if off < 0:
        raise _Unreadable()
    back = backing.cast(gdb.lookup_type("ail_strback").pointer()).dereference()
    n = _int(back["n"])
    if off + ln > n:
        raise _Unreadable()
    data = back["data"]
    units = [_int(data[off + i]) & 0xFFFF for i in range(ln)]
    chars = []
    i = 0
    while i < len(units):
        u = units[i]
        if 0xD800 <= u <= 0xDBFF and i + 1 < len(units) and 0xDC00 <= units[i + 1] <= 0xDFFF:
            chars.append(chr(0x10000 + ((u - 0xD800) << 10) + (units[i + 1] - 0xDC00)))
            i += 2
        else:
            chars.append(chr(u))
            i += 1
    return repr("".join(chars))


def _general_vec(value, kind, depth):
    obj = value["o"].cast(gdb.lookup_type("ail_vecobj").pointer()).dereference()
    return _seq_body(obj["p"], _int(obj["n"]), kind, depth)


def _general_dict(value, depth):
    obj = value["o"].cast(gdb.lookup_type("ail_mapobj").pointer()).dereference()
    entries = obj["entries"]
    n = _need_count(_int(obj["n"]))
    _need_pointer(entries, n)
    count = min(n, MAX_ITEMS)
    parts = []
    for i in range(count):
        entry = entries[i]
        parts.append("%s: %s" % (_format(entry["key"], depth + 1), _format(entry["val"], depth + 1)))
    if n > MAX_ITEMS:
        parts.append("...")
    return "{" + ", ".join(parts) + "}"


def _general_set(value, frozenset_, depth):
    obj = value["o"].cast(gdb.lookup_type("ail_setobj").pointer()).dereference()
    ent = obj["ent"]
    n = _need_count(_int(obj["n"]))
    _need_pointer(ent, n)
    parts = []
    count = 0
    for i in range(n):
        key = ent[i]["key"]
        if _int(key["tag"]) == T_UNBOUND:   # a removal's hole
            continue
        if count >= MAX_ITEMS:
            parts.append("...")
            break
        parts.append(_format(key, depth + 1))
        count += 1
    body = "{" + ", ".join(parts) + "}"
    return "frozenset(" + body + ")" if frozenset_ else body


def _class_name(cls):
    try:
        obj = cls["o"].cast(gdb.lookup_type("ail_classobj").pointer()).dereference()
        name = obj["name"]
        if _int(name["tag"]) == T_STR:
            text = _general_str(name)
            if text[0] in "'\"":
                return text[1:-1]
    except (gdb.error, _Unreadable, ValueError, UnicodeError):
        pass
    return "?"


def _general_obj(value, depth):
    tag = _int(value["tag"])
    if tag == T_NONE:
        return "None"
    if tag == T_BOOL:
        return "True" if _int(value["i"]) else "False"
    if tag == T_INT:
        return repr(_int(value["i"]))
    if tag == T_FLOAT:
        box = value["o"].cast(gdb.lookup_type("ail_floatbox").pointer()).dereference()
        return repr(float(box["v"]))
    if tag == T_STR:
        return _general_str(value)
    if tag == T_LIST:
        return _general_vec(value, "list", depth)
    if tag == T_TUPLE:
        return _general_vec(value, "tuple", depth)
    if tag == T_DICT:
        return _general_dict(value, depth)
    if tag == T_SET:
        return _general_set(value, False, depth)
    if tag == T_FROZENSET:
        return _general_set(value, True, depth)
    if tag == T_RANGE:
        obj = value["o"].cast(gdb.lookup_type("ail_rangeobj").pointer()).dereference()
        start, stop, step = _int(obj["start"]), _int(obj["stop"]), _int(obj["step"])
        return "range(%d, %d)" % (start, stop) if step == 1 else "range(%d, %d, %d)" % (start, stop, step)
    if tag == T_CELL:
        obj = value["o"].cast(gdb.lookup_type("ail_cellobj").pointer()).dereference()
        return _format(obj["val"], depth + 1)
    if tag == T_CLASS:
        return "<class '%s'>" % _class_name(value)
    if tag == T_INST:
        obj = value["o"].cast(gdb.lookup_type("ail_instobj").pointer()).dereference()
        return "<%s object>" % _class_name(obj["cls"])
    return "<ail_obj tag %d>" % tag


def _tuple_struct(value, depth):
    fields = []
    for field in value.type.fields():
        m = re.match(r"^f_f(\d+)$", field.name or "")
        if m:
            fields.append((int(m.group(1)), field.name))
    fields.sort()
    parts = [_format(value[name], depth + 1) for _, name in fields]
    return "(" + ", ".join(parts) + ("," if len(parts) == 1 else "") + ")"


def _format(value, depth):
    if depth > MAX_DEPTH:
        return "..."
    t = value.type
    name = _type_name(t)
    st = t.strip_typedefs()

    if st.code == gdb.TYPE_CODE_PTR:
        target = _pointer_target(t)
        target_name = _type_name(target)
        if target_name and (target_name in PRINTER_TYPES or target_name.startswith("ail_obj__AilT_")):
            if _int(value) == 0:
                raise _Unreadable()
            return _format(value.dereference(), depth)
        return str(value)

    if name == "ail_str":
        return _read_str(value)
    if name == "ail_bytes":
        return _read_bytes(value)
    if name == "ail_list":
        return _read_typed_list(value, "list", depth)
    if name == "ail_flist":
        return _read_typed_list(value, "list", depth)
    if name == "ail_slist":
        return _read_typed_list(value, "list", depth)
    if name in ("ail_sdict", "ail_stab"):
        return _read_typed_dict(value, depth)
    if name == "ail_obj":
        return _general_obj(value, depth)
    if name.startswith("ail_obj__AilT_"):
        return _tuple_struct(value, depth)
    if name in ("_Bool", "bool"):
        return "True" if _int(value) else "False"
    if name in ("double", "float"):
        return repr(float(value))
    if st.code in (gdb.TYPE_CODE_INT, gdb.TYPE_CODE_ENUM):
        return repr(_int(value))
    return str(value)


PRINTER_TYPES = {
    "ail_str", "ail_bytes", "ail_list", "ail_flist", "ail_slist", "ail_sdict", "ail_stab",
    "ail_obj", "_Bool", "bool", "double", "float",
}


class _AilPrinter(object):
    def __init__(self, value):
        self.value = value

    def to_string(self):
        return _r(self.value)


def _lookup(value):
    t = value.type
    name = _type_name(t)
    if _is_pointer(t):
        name = _type_name(_pointer_target(t))
    if name in PRINTER_TYPES or name.startswith("ail_obj__AilT_"):
        return _AilPrinter(value)
    return None


gdb.pretty_printers.append(_lookup)
