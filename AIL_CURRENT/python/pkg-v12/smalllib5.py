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
        run_abc(tree, text)
    if 'array' in mods:
        run_array(tree, text)
    if 'io' in mods:
        run_io(tree, text)


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
def run_abc(tree, text):
    b = stdlib5.take_imports(tree, 'abc', {'ABC', 'ABCMeta', 'abstractmethod', 'abstractclassmethod',
                                           'abstractstaticmethod', 'abstractproperty', 'get_cache_token'},
                             unknown='ABC, ABCMeta, abstractmethod, abstractclassmethod, abstractstaticmethod, '
                                     'abstractproperty and get_cache_token are built')
    if not b:
        return

    abstract_decorators = {'abstractmethod', 'abstractclassmethod', 'abstractstaticmethod', 'abstractproperty'}
    decorator_replacement = {'abstractclassmethod': 'classmethod', 'abstractstaticmethod': 'staticmethod',
                             'abstractproperty': 'property'}

    def is_abstract(decorator):
        return b.attr(decorator) in abstract_decorators

    def defined_methods(cls):
        methods = set()
        abstract = set()
        for item in cls.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(is_abstract(d) for d in item.decorator_list):
                    abstract.add(item.name)
                else:
                    methods.add(item.name)
        return methods, abstract

    classes = [stmt for stmt in tree.body if isinstance(stmt, ast.ClassDef)]
    heritage = {}
    abstract = {}
    for cls in classes:
        direct = False
        bases = []
        for base in cls.bases:
            found = b.attr(base)
            if found in ('ABC', 'ABCMeta'):
                direct = True
            elif isinstance(base, ast.Name) and base.id in abstract:
                bases.append(base.id)
        for keyword in cls.keywords:
            if keyword.arg == 'metaclass' and b.attr(keyword.value) == 'ABCMeta':
                direct = True
        inherited = set()
        for base in bases:
            inherited.update(abstract[base])
        methods, declared = defined_methods(cls)
        heritage[cls.name] = direct or bool(bases)
        abstract[cls.name] = (inherited - methods) | declared

    class Strip(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            node.bases = [x for x in node.bases if b.attr(x) not in ('ABC', 'ABCMeta')]
            keep = []
            for kw in node.keywords:
                if kw.arg == 'metaclass' and b.attr(kw.value) == 'ABCMeta':
                    continue
                keep.append(kw)
            node.keywords = keep
            self.generic_visit(node)
            return node

        def visit_FunctionDef(self, node):
            decorators = []
            for decorator in node.decorator_list:
                found = b.attr(decorator)
                if found in abstract_decorators:
                    replacement = decorator_replacement.get(found)
                    if replacement is not None:
                        decorators.append(stdlib5.name(replacement))
                    continue
                decorators.append(decorator)
            node.decorator_list = decorators
            node.body = [ast.Pass() if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                         and s.value.value is Ellipsis else s for s in node.body]
            self.generic_visit(node)
            return node
    tree.body = [Strip().visit(s) for s in tree.body]

    guards = []
    for cls in classes:
        if not heritage.get(cls.name) or not abstract.get(cls.name):
            continue
        guards.append(cls.name)
        marker = ast.parse('def _ail_abc_guard__(self) -> None:\n    _ail_abc_check(self)\n').body[0]
        cls.body.append(marker)

    used_token = [False]

    def fix(node):
        if isinstance(node, ast.Call) and b.attr(node.func) == 'get_cache_token' and not node.args and not node.keywords:
            used_token[0] = True
            return stdlib5.call(stdlib5.name('_ail_abc_cache_token'), [])
        return None
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]

    b.names.clear()
    stdlib5.leftover(tree, b, 'ABC, ABCMeta, abstractmethod, abstractclassmethod, abstractstaticmethod, '
                     'abstractproperty and get_cache_token are the names that are built')
    if guards:
        missing = {}
        for cls in classes:
            if heritage.get(cls.name) and abstract.get(cls.name):
                missing[cls.name] = tuple(sorted(abstract[cls.name]))
        lines = ['def _ail_abc_check_name(name: str) -> None:']
        first = True
        for cname in sorted(missing):
            names = missing[cname]
            if len(names) == 1:
                message = ("Can't instantiate abstract class %s without an implementation for abstract method '%s'"
                           % (cname, names[0]))
            else:
                message = ("Can't instantiate abstract class %s without an implementation for abstract methods '%s'"
                           % (cname, "', '".join(names)))
            lines.append('    %s name == %r:' % ('if' if first else 'elif', cname))
            lines.append('        raise TypeError(%r)' % message)
            first = False
        if first:
            lines.append('    pass')
        lines.extend(['', 'def _ail_abc_check(obj) -> None:',
                      '    _ail_abc_check_name(type(obj).__name__)', ''])
        text.append('\n'.join(lines))
    if used_token[0]:
        text.append('def _ail_abc_cache_token() -> int:\n    return 0\n')


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
        text = call.args[0]
        if isinstance(text, ast.Constant) and isinstance(text.value, str):
            # StringIO's iteration splits after each '\n' only; splitlines(True) would also break a lone
            # '\r', which the csv parser must see (CPython reports it as a new-line in an unquoted field).
            parts = text.value.split("\n")
            lines = [part + "\n" for part in parts[:-1]]
            if parts[-1] != "":
                lines.append(parts[-1])
            return ast.List(elts=[ast.Constant(value=line) for line in lines], ctx=ast.Load())
        # The same split for a text expression known only at run time:
        #   [part + ("\n" if i < len(parts) - 1 else "")
        #    for parts in [text.split("\n")] for i, part in enumerate(parts)
        #    if i < len(parts) - 1 or part != ""]
        def name(ident, ctx=ast.Load()):
            return ast.Name(id=ident, ctx=ctx)
        parts_name, index_name, part_name = "_ail_csv_parts", "_ail_csv_i", "_ail_csv_part"
        last = ast.Compare(left=name(index_name), ops=[ast.Lt()],
                           comparators=[ast.BinOp(left=ast.Call(func=name("len"), args=[name(parts_name)], keywords=[]),
                                                  op=ast.Sub(), right=ast.Constant(value=1))])
        split = ast.Call(func=ast.Attribute(value=text, attr="split", ctx=ast.Load()),
                         args=[ast.Constant(value="\n")], keywords=[])
        return ast.ListComp(elt=ast.IfExp(test=last, body=ast.BinOp(left=name(part_name), op=ast.Add(),
                                                                   right=ast.Constant(value="\n")),
                                          orelse=name(part_name)),
                            generators=[
                                ast.comprehension(target=name(parts_name, ast.Store()),
                                                  iter=ast.List(elts=[split], ctx=ast.Load()), ifs=[], is_async=0),
                                ast.comprehension(target=ast.Tuple(elts=[name(index_name, ast.Store()),
                                                                         name(part_name, ast.Store())],
                                                                   ctx=ast.Store()),
                                                  iter=ast.Call(func=name("enumerate"), args=[name(parts_name)],
                                                                keywords=[]),
                                                  ifs=[ast.BoolOp(op=ast.Or(), values=[
                                                      ast.Compare(left=name(index_name), ops=[ast.Lt()],
                                                                  comparators=[ast.BinOp(
                                                                      left=ast.Call(func=name("len"), args=[name(parts_name)],
                                                                                    keywords=[]), op=ast.Sub(),
                                                                      right=ast.Constant(value=1))]),
                                                      ast.Compare(left=name(part_name), ops=[ast.NotEq()],
                                                                  comparators=[ast.Constant(value="")])])],
                                                  is_async=0)])

    class Lower(ast.NodeTransformer):
        used_class = False

        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in csv_only:
                node.value = self.visit(lines_of(node.value))
                return node
            return self.generic_visit(node)

        def visit_Call(self, node):
            if csv_reader_call(node) and node.args and is_stringio(node.args[0]):
                first = self.visit(lines_of(node.args[0]))
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
