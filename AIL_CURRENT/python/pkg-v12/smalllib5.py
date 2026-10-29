"""keyword, calendar, abc, array and io.StringIO (library batch 5, called from stdlib5).

* keyword: `iskeyword`, `issoftkeyword`, `kwlist`, `softkwlist` (Python 3.12's lists).
* calendar: `isleap leapdays weekday monthrange monthcalendar`, `month_name month_abbr day_name day_abbr` (indexable,
  sliceable lists with '' at 0), `MONDAY`..`SUNDAY`, `month(y, m[, w, l])` and `prmonth(y, m)` (the text calendar of
  one month), Monday-first. Not built, refused by name: `calendar.calendar / prcal`, the Calendar classes,
  `setfirstweekday`, `timegm`, `itermonthdates`.
* abc: `ABC`, `abstractmethod` and `ABCMeta`: the base and the decorators are dropped (an abstract class can still be
  instantiated here; CPython raises TypeError).
* array: `array(typecode, iterable)` for the integer typecodes and 'd' (prelude_array.py). Not built: 'f', 'u', tobytes /
  frombytes / tofile / fromfile / buffer_info.
* io: `io.StringIO` (prelude_stringio.py). `csv.reader(io.StringIO(text))` and `csv.DictReader(io.StringIO(text))`
  become the csv pass's list of lines, `json.load(io.StringIO(text))` is `json.loads(text)`, and
  `print(..., file=buf)` writes into the buffer. `io.BytesIO` and the rest of `io` are refused by name.
"""
import ast

import stdlib5
from stdlib4 import refuse

KEYWORDS = ['False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield']
SOFT_KEYWORDS = ['_', 'case', 'match', 'type']


def call_of(func, args):
    return stdlib5.call(stdlib5.name(func), args)


def run(tree, text, mods):
    if 'keyword' in mods:
        run_keyword(tree, text)
    if 'calendar' in mods:
        run_calendar(tree, text)
    if 'abc' in mods:
        run_abc(tree)
    if 'array' in mods:
        run_array(tree, text)
    if 'io' in mods:
        run_io(tree, text)
    if 'unicodedata' in mods:
        run_unicodedata(tree, text)


# ---------------------------------------------------------------------------------------------------------------
def run_keyword(tree, text):
    b = stdlib5.take_imports(tree, 'keyword', {'iskeyword', 'issoftkeyword', 'kwlist', 'softkwlist'},
                             unknown='iskeyword, issoftkeyword, kwlist and softkwlist are built')
    if not b:
        return
    used = set()

    def fix(node):
        if isinstance(node, ast.Call) and b.attr(node.func) in ('iskeyword', 'issoftkeyword') and len(node.args) == 1 \
                and not node.keywords:
            fn = '_ail_' + b.attr(node.func)
            used.add(fn)
            return call_of(fn, [stdlib5.Replace(fix).visit(node.args[0])])
        found = b.attr(node)
        if found in ('kwlist', 'softkwlist'):
            fn = '_ail_' + found
            used.add(fn)
            return call_of(fn, [])
        return None
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]
    b.names.clear()
    stdlib5.leftover(tree, b, 'iskeyword(s), issoftkeyword(s), kwlist and softkwlist are built')
    src = (
        'def _ail_iskeyword(s: str) -> bool:\n    return s in %s\n\n'
        'def _ail_issoftkeyword(s: str) -> bool:\n    return s in %s\n\n'
        'def _ail_kwlist() -> list[str]:\n    return %s\n\n'
        'def _ail_softkwlist() -> list[str]:\n    return %s\n'
        % ('{' + ', '.join(repr(k) for k in KEYWORDS) + '}', '{' + ', '.join(repr(k) for k in SOFT_KEYWORDS) + '}',
           repr(KEYWORDS), repr(SOFT_KEYWORDS)))
    text.append(stdlib5.shake(src, used))


# ---------------------------------------------------------------------------------------------------------------
CAL_FUNCS = {'isleap': '_ail_cal_isleap', 'leapdays': '_ail_cal_leapdays', 'weekday': '_ail_cal_weekday',
             'monthrange': '_ail_cal_monthrange', 'monthcalendar': '_ail_cal_monthcalendar'}
CAL_DAYS = {'MONDAY': 0, 'TUESDAY': 1, 'WEDNESDAY': 2, 'THURSDAY': 3, 'FRIDAY': 4, 'SATURDAY': 5, 'SUNDAY': 6}
CAL_LISTS = {'month_name': '_ail_cal_month_names', 'month_abbr': '_ail_cal_month_abbrs',
             'day_name': '_ail_cal_day_names', 'day_abbr': '_ail_cal_day_abbrs'}


def run_calendar(tree, text):
    handled = set(CAL_FUNCS) | set(CAL_LISTS) | set(CAL_DAYS) | {'month', 'prmonth', 'IllegalMonthError'}
    b = stdlib5.take_imports(tree, 'calendar', handled, unknown='isleap, leapdays, weekday, monthrange, monthcalendar, '
                             'month, prmonth, month_name, month_abbr, day_name, day_abbr and MONDAY..SUNDAY are built')
    if not b:
        return
    used = set()

    def fix(node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'list' \
                and len(node.args) == 1 and not node.keywords and b.attr(node.args[0]) in CAL_LISTS:
            used.add(CAL_LISTS[b.attr(node.args[0])])
            return call_of(CAL_LISTS[b.attr(node.args[0])], [])        # the function already gives a fresh list
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Call)                 and b.attr(node.value.func) == 'monthrange' and not node.value.keywords                 and isinstance(node.slice, ast.Constant) and node.slice.value in (0, 1):
            used.add('_ail_cal_monthrange_int')                       # one field of the pair: a plain int
            return ast.Subscript(value=call_of('_ail_cal_monthrange_int', [stdlib5.Replace(fix).visit(a)
                                                                           for a in node.value.args]),
                                 slice=node.slice, ctx=ast.Load())
        if isinstance(node, ast.Call):
            found = b.attr(node.func)
            if found in CAL_FUNCS:
                used.add(CAL_FUNCS[found])
                return call_of(CAL_FUNCS[found], [stdlib5.Replace(fix).visit(a) for a in node.args]) \
                    if not node.keywords else None
            if found in ('month', 'prmonth') and not node.keywords and 2 <= len(node.args) <= 4:
                used.add('_ail_cal_month')
                args = [stdlib5.Replace(fix).visit(a) for a in node.args]
                text_call = call_of('_ail_cal_month', args)
                if found == 'month':
                    return text_call
                return ast.Call(func=stdlib5.name('print'), args=[text_call],
                                keywords=[ast.keyword(arg='end', value=ast.Constant(value=''))])
        found = b.attr(node)
        if found in CAL_LISTS:
            used.add(CAL_LISTS[found])
            return call_of(CAL_LISTS[found], [])
        if found in CAL_DAYS:
            used.add('_ail_cal_day')
            return call_of('_ail_cal_day', [ast.Constant(value=CAL_DAYS[found])])
        if found == 'IllegalMonthError':
            return stdlib5.name('ValueError')
        return None
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]
    b.names.clear()
    stdlib5.leftover(tree, b, 'see the reference for the calendar forms that are built')
    if used & {'_ail_cal_day', '_ail_cal_weekday', '_ail_cal_monthrange'}:
        stdlib5.add_once(text, stdlib5.prelude('enum'))                 # the days are IntEnum members
    text.append(stdlib5.shake(stdlib5.prelude('calendar'), used))


# ---------------------------------------------------------------------------------------------------------------
def run_abc(tree):
    b = stdlib5.take_imports(tree, 'abc', {'ABC', 'ABCMeta', 'abstractmethod'},
                             unknown='ABC, ABCMeta and abstractmethod are built (as plain classes and methods)')
    if not b:
        return

    class Strip(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            node.bases = [x for x in node.bases if b.attr(x) not in ('ABC',)]
            keep = []
            for kw in node.keywords:
                if kw.arg == 'metaclass' and b.attr(kw.value) == 'ABCMeta':
                    continue
                keep.append(kw)
            node.keywords = keep
            self.generic_visit(node)
            return node

        def visit_FunctionDef(self, node):
            node.decorator_list = [d for d in node.decorator_list if b.attr(d) != 'abstractmethod']
            node.body = [ast.Pass() if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                         and s.value.value is Ellipsis else s for s in node.body]
            self.generic_visit(node)
            return node
    tree.body = [Strip().visit(s) for s in tree.body]
    b.names.clear()
    stdlib5.leftover(tree, b, 'ABC, ABCMeta and abstractmethod are the names that are built')


# ---------------------------------------------------------------------------------------------------------------
ARRAY_REFUSED = ('tobytes', 'frombytes', 'tofile', 'fromfile', 'buffer_info', 'tounicode', 'fromunicode')


def run_array(tree, text):
    b = stdlib5.take_imports(tree, 'array', {'array'}, unknown='array is the one name of the module that is built')
    if not b:
        return
    for each in ast.walk(tree):
        if isinstance(each, ast.Name) and each.id == '_AilArray':
            return

    def fix(node):
        if b.attr(node) == 'array':
            return stdlib5.name('_AilArray')
        return None
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]
    b.names.clear()
    stdlib5.leftover(tree, b, 'array.array(typecode, iterable) is the form that is built')
    for each in ast.walk(tree):
        if isinstance(each, ast.Attribute) and each.attr in ARRAY_REFUSED:
            refuse(each, 'array.%s is not built: arrays are lists of numbers here (tolist(), extend, append, pop, '
                   'insert, index, count, reverse, byteswap)' % each.attr)
        if isinstance(each, ast.Call) and isinstance(each.func, ast.Name) and each.func.id == '_AilArray' and each.args \
                and isinstance(each.args[0], ast.Constant) and each.args[0].value in ('f', 'u', 'w'):
            refuse(each, "array typecode %r is not built (single precision and unicode arrays); use 'd' or an int type"
                   % each.args[0].value)
    text.append(stdlib5.prelude('array'))


# ---------------------------------------------------------------------------------------------------------------
def run_io(tree, text):
    b = stdlib5.take_imports(tree, 'io', {'StringIO'}, unknown='StringIO is the one name of the module that is built')
    if not b:
        return
    csvb = stdlib5.peek_imports(tree, 'csv')
    jsonb = stdlib5.peek_imports(tree, 'json')

    def is_stringio(node):
        return isinstance(node, ast.Call) and b.attr(node.func) == 'StringIO'

    def csv_reader_call(node):
        return isinstance(node, ast.Call) and csvb.attr(node.func) in ('reader', 'DictReader')

    # names bound to io.StringIO(...) once, and how they are used
    bound = {}
    for each in ast.walk(tree):
        if isinstance(each, ast.Assign) and len(each.targets) == 1 and isinstance(each.targets[0], ast.Name) \
                and is_stringio(each.value):
            bound.setdefault(each.targets[0].id, []).append(each)
    csv_only = set()
    for var, assigns in bound.items():
        if len(assigns) != 1 or len(assigns[0].value.args) != 1 or assigns[0].value.keywords:
            continue
        uses = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == var and isinstance(n.ctx, ast.Load)]
        reader_args = [c.args[0] for c in ast.walk(tree) if csv_reader_call(c) and c.args
                       and isinstance(c.args[0], ast.Name) and c.args[0].id == var]
        if uses and len(uses) == len(reader_args) and not any(
                isinstance(n, ast.Name) and n.id == var and not isinstance(n.ctx, ast.Load) for n in ast.walk(tree)
                if n is not assigns[0].targets[0]):
            csv_only.add(var)

    def lines_of(call):
        if len(call.args) != 1 or any(k.arg != 'newline' for k in call.keywords):
            refuse(call, 'io.StringIO(text) with the text is the form that is built for csv.reader')
        return ast.Call(func=ast.Attribute(value=call.args[0], attr='splitlines', ctx=ast.Load()),
                        args=[ast.Constant(value=True)], keywords=[])

    class Lower(ast.NodeTransformer):
        used_class = False

        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in csv_only:
                node.value = lines_of(node.value)
                return node
            return self.generic_visit(node)

        def visit_Call(self, node):
            if csv_reader_call(node) and node.args and is_stringio(node.args[0]):
                first = lines_of(node.args[0])
                first.func.value = self.visit(first.func.value)
                node.args = [first] + [self.visit(a) for a in node.args[1:]]
                node.keywords = [self.visit(k) for k in node.keywords]
                return node
            if isinstance(node.func, ast.Attribute) and jsonb.attr(node.func) == 'load' and len(node.args) == 1 \
                    and is_stringio(node.args[0]) and len(node.args[0].args) == 1:
                text_arg = self.visit(node.args[0].args[0])
                return ast.Call(func=ast.Attribute(value=node.func.value, attr='loads', ctx=ast.Load()),
                                args=[text_arg], keywords=[])
            if isinstance(node.func, ast.Name) and node.func.id == 'print':
                files = [k for k in node.keywords if k.arg == 'file']
                if files and isinstance(files[0].value, ast.Name) and files[0].value.id in bound \
                        and files[0].value.id not in csv_only:
                    return self.print_to(node, files[0].value)
            self.generic_visit(node)
            if is_stringio(node):
                Lower.used_class = True
                return ast.Call(func=stdlib5.name('_AilStringIO'), args=node.args, keywords=node.keywords)
            return node

        def print_to(self, node, target):
            self.generic_visit(node)
            sep = ast.Constant(value=' ')
            end = ast.Constant(value='\n')
            for kw in node.keywords:
                if kw.arg == 'sep':
                    sep = kw.value
                elif kw.arg == 'end':
                    end = kw.value
                elif kw.arg not in ('file', 'flush'):
                    refuse(node, 'print(%s=...) to a StringIO is not built' % kw.arg)
            if any(isinstance(a, ast.Starred) for a in node.args):
                refuse(node, 'print(*xs, file=buffer) is not built: write a loop')
            strs = [ast.Call(func=stdlib5.name('str'), args=[a], keywords=[]) for a in node.args]
            joined = ast.Call(func=ast.Attribute(value=sep, attr='join', ctx=ast.Load()),
                              args=[ast.List(elts=strs, ctx=ast.Load())], keywords=[])
            body = ast.BinOp(left=joined, op=ast.Add(), right=end)
            return ast.Call(func=ast.Attribute(value=target, attr='write', ctx=ast.Load()), args=[body], keywords=[])

    lower = Lower()
    tree.body = [lower.visit(s) for s in tree.body]
    b.names.clear()
    stdlib5.leftover(tree, b, 'io.StringIO(text) is the form that is built')
    if Lower.used_class:
        text.append(stdlib5.prelude('stringio'))


# ---------------------------------------------------------------------------------------------------------------
UNICODE_FUNCS = {'name': '_ail_uni_name', 'category': '_ail_uni_category', 'normalize': '_ail_uni_normalize'}

# Seven CJK compatibility ideographs have a canonical decomposition above U+FFFF; the 16-bit v2 runtime
# cannot hold that code point, so a literal form is refused by name instead of returning the character
# unchanged.  A value that only reaches normalize at run time keeps the open 16-bit limitation.
UNICODE_ASTRAL_DECOMP = {
    0xFA6C: 0x242EE, 0xFACF: 0x2284A, 0xFAD0: 0x22844, 0xFAD1: 0x233D5,
    0xFAD5: 0x25249, 0xFAD6: 0x25CD0, 0xFAD7: 0x27ED3,
}


def unicodedata_astral_decomp(cp):
    return UNICODE_ASTRAL_DECOMP.get(cp)


def run_unicodedata(tree, text):
    b = stdlib5.take_imports(tree, 'unicodedata', set(UNICODE_FUNCS) | {'unidata_version'},
                             unknown='name, category, normalize (NFC/NFD) and unidata_version are built')
    if not b:
        return
    used = set()

    def form_node(call):
        if call.args:
            return call.args[0]
        for keyword in call.keywords:
            if keyword.arg == 'form':
                return keyword.value
        return None

    def fix(node):
        if isinstance(node, ast.Call):
            found = b.attr(node.func)
            if found in ('name', 'category', 'normalize') and node.keywords:
                refuse(node, 'unicodedata.%s takes no keyword arguments in CPython; write the arguments '
                       'positionally' % found)
            if found in ('name', 'category'):
                used.add(UNICODE_FUNCS[found])
                return ast.Call(func=stdlib5.name(UNICODE_FUNCS[found]),
                                args=[stdlib5.Replace(fix).visit(a) for a in node.args],
                                keywords=[ast.keyword(arg=k.arg, value=stdlib5.Replace(fix).visit(k.value))
                                          for k in node.keywords])
            if found == 'normalize':
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) \
                        and isinstance(node.args[1].value, str):
                    for ch in node.args[1].value:
                        point = unicodedata_astral_decomp(ord(ch))
                        if point is not None:
                            refuse(node, "unicodedata.normalize: U+%04X decomposes to U+%X, above U+FFFF, "
                                   "which the 16-bit v2 runtime cannot hold" % (ord(ch), point))
                form = form_node(node)
                if not (isinstance(form, ast.Constant) and isinstance(form.value, str)
                        and form.value in ('NFC', 'NFD')):
                    refuse(node, "unicodedata.normalize(%s...): only the literal forms 'NFC' and 'NFD' are built "
                           "(canonical decomposition and composition); NFKC/NFKD and a form computed at run time "
                           "are not" % (ast.unparse(form) if form is not None else ''))
                used.add(UNICODE_FUNCS['normalize'])
                return ast.Call(func=stdlib5.name(UNICODE_FUNCS['normalize']),
                                args=[stdlib5.Replace(fix).visit(a) for a in node.args],
                                keywords=[ast.keyword(arg=k.arg, value=stdlib5.Replace(fix).visit(k.value))
                                          for k in node.keywords])
        found = b.attr(node)
        if found == 'unidata_version':
            return ast.Constant(value='15.0.0')
        return None
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]
    b.names.clear()
    stdlib5.leftover(tree, b, 'name, category, normalize (NFC/NFD) and unidata_version are built')
    text.append(stdlib5.shake(stdlib5.prelude('unicodedata'), used))
