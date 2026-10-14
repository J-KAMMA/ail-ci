"""Translate the initial AIL block syntax to the existing checked compiler surface."""
import ast
import builtins
import io
import importlib.util
import keyword
from pathlib import Path
import re
import token
import tokenize


class SyntaxErrorAIL(ValueError):
    def __init__(self, message, *, lineno=None, offset=None, code=None):
        super().__init__(message)
        self.lineno = lineno
        self.offset = offset
        self.code = code



# `list[list[T]]` (rows of int, float, str or a struct): compiled as a list of row objects
# (python/pkg-v12/nested_lists.py). Bytes and handle rows, and deeper nesting, stay refused.
_NESTED = (r'list\s*\[\s*list\s*\[\s*(?!(?:bytes|bytearray|binaryfile|tcpsocket|exception|list|set|dict|tuple)\b)'
           r'[A-Za-z_]\w*\s*\]\s*\]')


def _let_refusal(statement, line):
    """Why a `let` did not parse, naming the construct and the rewrite that does compile -- the
    bare "invalid let statement" sent LLM writers guessing at a type the compiler never builds."""
    found = re.fullmatch(r'let\s+([A-Za-z_]\w*)\s*:\s*([^=]+?)\s*=(?!=)\s*(.+)', statement)
    if not found:
        if re.fullmatch(r'let\s+[A-Za-z_]\w*(?:\s*:\s*[^=]+)?', statement):
            return f'invalid let statement at line {line}: a let needs an initializer (`let x = ...;`)'
        return f'invalid let statement at line {line}'
    name, annotation = found[1], re.sub(r'\s+', '', found[2])
    head = f'invalid let statement at line {line}: `let {name}: {annotation}`'
    if re.match(r'list\[(?:list|set|dict|tuple\[[^]]*(?:str|list))', annotation):
        return (f'{head} -- a list of lists holds rows of int, float, str or a struct '
                f'(`let {name}: list[list[int]] = [[] for _ in range(n)];`); a list of sets, dicts, '
                f'bytes or deeper lists is not a supported type: use a list of structs')
    key = re.match(r'(dict|set)\[([A-Za-z_]\w*)', annotation)
    if key and key[2] not in ('str', 'int'):
        rewrite = ('key it by str with `.decode()` (`let d: dict[str, int] = {}; d[k.decode()] = v;`)'
                   if key[2] == 'bytes' else 'key it by str or int')
        return f'{head} -- {key[1]} keys must be str or int, not {key[2]}; {rewrite}'
    if key and annotation.startswith('dict['):
        return (f'{head} -- dict values must be int, float, str or bytes; keep the values in '
                f'their own list and map each key to its index (`dict[str, int]`)')
    return (f'{head} -- unsupported annotation; a let may be annotated with a plain type '
            f'(int, float, str, bytes, a struct, T | None), list[T], list[tuple[...]], '
            f'dict[str|int, int|float|str|bytes], set[int|str] or Callable[...], or left unannotated')

def _callable(annotation):
    # The block frontend is also loaded before the compiler adds pkg-v12 to sys.path.
    if not hasattr(_callable, 'parse'):
        spec = importlib.util.spec_from_file_location(
            '_ail_callable_types', Path(__file__).parent / 'python' / 'pkg-v12' / 'callable_types.py')
        codec = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(codec)
        _callable.parse = codec.parse
    try:
        # Resolve local/imported/later struct declarations in the compiler.
        candidates = {node.id for node in ast.walk(annotation) if isinstance(node, ast.Name)} if annotation else set()
        return _callable.parse(annotation, structs=candidates - set(dir(builtins)) - {'Callable', 'void'})
    except ValueError as exc:
        raise SyntaxErrorAIL(str(exc)) from exc


_OPTIONAL = re.compile(r'\bOptional\s*\[\s*([A-Za-z_]\w*)\s*\]')


def detect(source):
    """Select block syntax from its first declaration."""
    stream = (part for part in tokenize.generate_tokens(io.StringIO(source).readline)
              if part.type not in (tokenize.NL, token.NEWLINE, token.INDENT, token.DEDENT,
                                   token.COMMENT, token.ENDMARKER))
    first = next(stream, None)
    second = next(stream, None)
    return bool(first and second and first.type == second.type == token.NAME
                and first.string in ('fn', 'const', 'use', 'struct', 'impl'))


def _render(tokens):
    converted = []
    i = 0
    while i < len(tokens):
        current = tokens[i]
        value = current.string
        if value in ('&', '|') and i + 1 < len(tokens) and tokens[i + 1].string == value:
            raise SyntaxErrorAIL(f'{value * 2} is not an AIL operator; use {"and" if value == "&" else "or"}',
                                 lineno=current.start[0], offset=current.start[1] + 1)
        if value == '!':
            raise SyntaxErrorAIL('! is not an AIL operator; use not',
                                 lineno=current.start[0], offset=current.start[1] + 1)
        if current.type == token.NAME and value in ('true', 'false'):
            converted.append((token.NAME, value.title()))
        else:
            converted.append((current.type, value))
        i += 1
    return tokenize.untokenize(converted).strip()


def _contract_condition(expression, result_name):
    """The condition text of a requires/ensures clause, with `result` naming the returned value."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(expression).readline))
        ast.parse(expression, mode='eval')
    except (SyntaxError, tokenize.TokenError) as exc:
        raise SyntaxErrorAIL(f'invalid contract condition: {expression}') from exc
    uses_result = any(part.type == token.NAME and part.string == 'result' for part in tokens)
    if uses_result and result_name is None:
        raise SyntaxErrorAIL('ensures in a function without a result cannot use result')
    renamed = [(part.type, result_name if part.type == token.NAME and part.string == 'result' else part.string)
               for part in tokens]
    return tokenize.untokenize(renamed).strip()


def _contract_check(kind, function, expression, condition):
    """`assert` with a message naming the clause: a violated contract stops the program."""
    shown = ast.unparse(ast.parse(expression, mode='eval'))
    return f'assert ({condition}), {(f"{kind} failed in {function}: {shown}")!r}'


_PARALLEL_FOR = re.compile(r'parallel\s+for\s+([A-Za-z_]\w*)\s+in\s+range\s*\((.*)\)', re.S)


def _parallel_header(statement):
    """`parallel for i in range(a, b)` is the ordinary `for i in par_range(a, b)` header; the
    compiler's parallel pass (pyfunc._par_prepare) recognizes `par_range`."""
    match = _PARALLEL_FOR.fullmatch(statement)
    if not match:
        raise SyntaxErrorAIL('parallel for has the form: parallel for i in range(a, b) { ... }')
    return f'for {match[1]} in par_range({match[2]})'


def _block_open(statement):
    if re.match(r'parallel\b', statement):
        statement = _parallel_header(statement)
    if statement.startswith(('fn ', 'struct ', 'impl ', 'except ')) or statement in ('else', 'try', 'finally'):
        return True
    if not re.match(r'^(if|elif|while|for)\s+', statement):
        return False
    header = re.sub(r'^elif\b', 'if', statement)
    try:
        ast.parse(header + ':\n    pass\n')
    except SyntaxError:
        return False
    return True


def translate(source, *, module=False, imports=None, declarations=None, source_map=None, function_bodies=None,
              keep_contracts=False):
    """Accept fn/const/let and brace-delimited blocks; reject unsupported top-level code.

    keep_contracts=True leaves requires/ensures as `__ail_requires__(c)` / `__ail_ensures__(c)`
    calls instead of lowering them, for tools that convert the source to another surface."""
    lines = []
    pending = []
    blocks = []
    expression_braces = 0
    main_count = 0
    declared = set()
    fields = []
    structs = {}
    methods = {}
    method_blocks = {}
    body_open = {}
    struct_fields = {}
    impl_start = None
    # requires/ensures of the function being translated: {'depth', 'name', 'void', 'ensures', 'started'}
    contract = None
    pending_contract = None

    def declare(name):
        if keyword.iskeyword(name) or name in declared:
            raise SyntaxErrorAIL(f'invalid or duplicate AIL name: {name}')
        declared.add(name)
    try:
        stream = tokenize.generate_tokens(io.StringIO(source).readline)
        for part in stream:
            if part.type in (tokenize.NL, token.NEWLINE, token.INDENT, token.DEDENT,
                             token.COMMENT, token.ENDMARKER):
                continue
            if part.type == token.ERRORTOKEN and part.string.isspace():
                continue
            if expression_braces:
                pending.append(part)
                if part.string == '{':
                    expression_braces += 1
                elif part.string == '}':
                    expression_braces -= 1
                continue
            if part.string == '{' and pending and not _block_open(_render(pending)):
                pending.append(part)
                expression_braces = 1
                continue
            if part.string not in ('{', '}', ';'):
                pending.append(part)
                continue
            start = pending[0].start if pending else part.start
            statement = _render(pending)
            pending.clear()
            if statement.startswith(('fn ', 'let ')) or (blocks and blocks[-1].startswith('struct ')):
                # `Optional[Node]` is spelled `Node | None` from here on (one form downstream).
                statement = _OPTIONAL.sub(r'\1 | None', statement)
            if blocks and blocks[-1].startswith('struct '):
                if part.string == ';':
                    field = re.fullmatch(r'([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*(?:\s*\|\s*None)?|list\s*\[\s*[A-Za-z_]\w*\s*\]|dict\s*\[\s*(?:str|int)\s*,\s*(?:int|float|str|bytes)\s*\]|set\s*\[\s*(?:int|str)\s*\]|Callable\s*\[.+\]|' + _NESTED + ')', statement)
                    if (not field or keyword.iskeyword(field[1]) or field[1] == 'self'
                            or field[1] in dict(fields)):
                        raise SyntaxErrorAIL('struct fields need distinct names and scalar, struct, list, typed dict or typed set annotations; a struct field that may be None is written `next: Node | None`')
                    annotation = re.sub(r'\s+', '', field[2])
                    if annotation.startswith('Callable'):
                        try:
                            _callable(ast.parse(annotation, mode='eval').body)
                        except SyntaxError as exc:
                            raise SyntaxErrorAIL('invalid callable field annotation') from exc
                    fields.append((field[1], annotation))
                elif part.string == '}' and not statement and fields:
                    name = blocks.pop().split()[1]
                    params = ', '.join(f'{field}: {kind}' for field, kind in fields)
                    lines.extend((line, None) for line in [f'class {name}:', f'    def __init__(self, {params}):',
                                  *(f'        self.{field} = {field}' for field, _ in fields)])
                    struct_fields[name] = {field for field, _ in fields}
                    fields = []
                    structs[name] = len(lines)
                    methods[name] = {}
                    method_blocks[name] = []
                else:
                    raise SyntaxErrorAIL('struct needs fields followed by semicolons; nested blocks are unsupported',
                                         lineno=part.start[0], offset=part.start[1] + 1)
                continue
            if part.string == '{':
                if not statement:
                    raise SyntaxErrorAIL(f'missing block header at line {part.start[0]}',
                                         lineno=part.start[0], offset=part.start[1] + 1)
                if statement.startswith('impl '):
                    match = re.fullmatch(r'impl\s+([A-Za-z_]\w*)', statement)
                    if blocks or not match:
                        raise SyntaxErrorAIL('impl must be a named top-level declaration')
                    if match[1] not in structs:
                        raise SyntaxErrorAIL('impl needs an existing local struct')
                    impl_start = len(lines)
                    blocks.append('impl ' + match[1])
                    continue
                if statement.startswith('struct '):
                    match = re.fullmatch(r'struct\s+([A-Za-z_]\w*)', statement)
                    if blocks or not match:
                        raise SyntaxErrorAIL('struct must be a named top-level declaration')
                    name = match[1]
                    if name in ('sys', 'main', 'int', 'float', 'str', 'bytes', 'bytearray', 'binaryfile', 'tcpsocket', 'exception', 'list', 'flist', 'void'):
                        raise SyntaxErrorAIL(f'reserved struct name: {name}')
                    declare(name)
                    blocks.append('struct ' + name)
                    continue
                if statement.startswith('fn '):
                    is_method = len(blocks) == 1 and blocks[0].startswith('impl ')
                    if blocks and not is_method:
                        raise SyntaxErrorAIL('fn must be at the top level')
                    match = re.fullmatch(r'fn\s+([A-Za-z_]\w*)\s*\((.*)\)(?:\s*->\s*(.+))?', statement)
                    if not match:
                        raise SyntaxErrorAIL(f'invalid fn header at line {part.start[0]}')
                    name, params, result = match.groups()
                    nullable_result = False
                    if result and re.fullmatch(r'[A-Za-z_]\w*\s*\|\s*None', result):
                        result = re.sub(r'\s*\|\s*None$', '', result)
                        nullable_result = True
                        if result in ('int', 'float', 'str', 'bytes', 'bool', 'void', 'list', 'dict'):
                            raise SyntaxErrorAIL('only a struct type can be None: write `-> Node | None`, '
                                                 'or return a sentinel (-1, "") or raise for %s' % result)
                    try:
                        signature = ast.parse(f'def signature({params})' +
                                              (f' -> {result}' if result else '') + ':\n    pass').body[0]
                    except SyntaxError as exc:
                        raise SyntaxErrorAIL(f'invalid fn header: {exc.msg}') from exc
                    for arg in (*signature.args.posonlyargs, *signature.args.args,
                                *signature.args.kwonlyargs):
                        if arg.annotation is not None:
                            _callable(arg.annotation)
                    callable_result = _callable(signature.returns) if result else None
                    if is_method:
                        owner = blocks[0].split()[1]
                        if (keyword.iskeyword(name) or name == '__init__' or name in methods[owner]
                                or name in struct_fields[owner]):
                            raise SyntaxErrorAIL(f'invalid or duplicate struct method: {name}')
                        try:
                            args = ast.parse(f'def method({params}):\n    pass').body[0].args
                        except SyntaxError as exc:
                            raise SyntaxErrorAIL(f'invalid method parameters: {exc.msg}') from exc
                        if (not args.args or args.args[0].arg != 'self'
                                or args.args[0].annotation is not None or args.posonlyargs
                                or args.vararg or args.kwarg or args.kwonlyargs or args.defaults
                                or any(arg.annotation is None for arg in args.args[1:])
                                or len({arg.arg for arg in args.args}) != len(args.args)):
                            raise SyntaxErrorAIL('method needs first untyped self and typed positional parameters')
                        methods[owner][name] = None
                    else:
                        declare(name)
                    if callable_result:
                        result = ast.unparse(signature.returns)
                    elif result and re.sub(r'\s+', '', result) == 'list[float]':
                        result = 'flist'
                    elif result and re.fullmatch(_NESTED, result):
                        result = re.sub(r'\s+', '', result)
                    elif result and re.fullmatch(r'list\s*\[\s*[A-Za-z_]\w*\s*\]', result):
                        result = re.sub(r'\s+', '', result)
                    elif result and re.fullmatch(r'dict\s*\[\s*(?:str|int)\s*,\s*(?:int|float|str|bytes)\s*\]|set\s*\[\s*(?:int|str)\s*\]', result):
                        result = re.sub(r'\s+', '', result)
                    elif result and not re.fullmatch(r'[A-Za-z_]\w*', result):
                        raise SyntaxErrorAIL('return type must be a supported type or a struct name')
                    if not is_method and name == 'sys':
                        raise SyntaxErrorAIL('sys is reserved by the AIL entry point')
                    if not is_method and name == 'main':
                        if module:
                            raise SyntaxErrorAIL('main must be in the entry source')
                        main_count += 1
                        if params.strip():
                            raise SyntaxErrorAIL('main takes no parameters')
                        if result and result != 'int':
                            raise SyntaxErrorAIL('main return type must be int')
                        # `fn main() { ... }` is main returning int: Python's sys.exit(None)
                        # exits 0, which the implicit `return 0` added at its close keeps.
                        result = 'int'
                    # Keep the block syntax's checked contract distinct from legacy Python-style
                    # return annotations, which the compiler has historically treated as hints.
                    annotation = (result if callable_result or result and result.startswith('list[list[') or result and result.startswith(('dict[', 'set['))
                                  else '__ail_checked_' + result if result and result.startswith('list[')
                                  else f'__ail_checked_{result}__')
                    if nullable_result:
                        annotation += ' | None'
                    header = f'def {name}({params})' + (f' -> {annotation}' if result else '')
                    pending_contract = {'name': f'{owner}.{name}' if is_method else name,
                                        'void': not result or result == 'void', 'ensures': [], 'started': False}
                    if function_bodies is not None:
                        target = f'{owner}.{name}' if is_method else name
                        body_open[len(blocks)] = (target, part.end)
                    if declarations is not None:
                        key = f'{owner}__{name}' if is_method else name
                        declarations[key] = None if key in declarations else (
                            start[0], start[1] + 1, f'{owner}.{name}' if is_method else name)
                else:
                    if not blocks:
                        raise SyntaxErrorAIL('only fn and const are allowed at the top level')
                    if blocks[-1].startswith('impl '):
                        raise SyntaxErrorAIL('impl supports only fn methods')
                    if statement in ('else', 'try', 'finally'):
                        header = statement
                    elif re.fullmatch(
                            r'except\s+(?:[A-Za-z_]\w*(?:\s+as\s+[A-Za-z_]\w*)?'
                            r'|\(\s*[A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)+\s*\)'
                            r'(?:\s*as\s+[A-Za-z_]\w*)?)', statement):
                        header = statement
                    elif re.match(r'parallel\b', statement):
                        header = _parallel_header(statement)
                    elif re.match(r'^(if|elif|while|for)\s+.+$', statement):
                        header = statement
                    else:
                        raise SyntaxErrorAIL(f'unsupported block header: {statement}')
                if contract is not None and len(blocks) == contract['depth']:
                    contract['started'] = True
                lines.append(('    ' * len(blocks) + header + ':', start))
                blocks.append(header)
                if pending_contract is not None:
                    contract, pending_contract = dict(pending_contract, depth=len(blocks)), None
            elif part.string == ';':
                if blocks and blocks[-1].startswith('impl '):
                    raise SyntaxErrorAIL('impl supports only fn methods with bodies')
                if not statement:
                    raise SyntaxErrorAIL(f'empty statement at line {part.start[0]}',
                                         lineno=part.start[0], offset=part.start[1] + 1)
                if not blocks:
                    use = re.fullmatch(r'use\s+([A-Za-z_]\w*)', statement)
                    if use:
                        if imports is None:
                            raise SyntaxErrorAIL('use needs compiler import resolution')
                        imports.append(use[1])
                        continue
                    match = re.fullmatch(r'const\s+([A-Za-z_]\w*)\s*=\s*(.+)', statement)
                    if not match:
                        raise SyntaxErrorAIL('only fn, const, and use are allowed at the top level')
                    if match[1] == 'sys':
                        raise SyntaxErrorAIL('sys is reserved by the AIL entry point')
                    declare(match[1])
                    statement = f'{match[1]} = {match[2]}'
                elif re.match(r'(requires|ensures)\b', statement):
                    clause = re.fullmatch(r'(requires|ensures)\s+(.+)', statement)
                    if (not clause or contract is None or len(blocks) != contract['depth']
                            or contract['started']):
                        raise SyntaxErrorAIL('requires/ensures must be the first statements of a function body',
                                             lineno=start[0], offset=start[1] + 1)
                    kind, expression = clause.groups()
                    if keep_contracts:
                        _contract_condition(expression, None if kind == 'requires' or contract['void'] else '_ail_result')
                        lines.append(('    ' * len(blocks) + f'__ail_{kind}__({expression})', start))
                        continue
                    if kind == 'requires':
                        if re.search(r'\bresult\b', expression):
                            raise SyntaxErrorAIL('requires cannot use result; use ensures',
                                                 lineno=start[0], offset=start[1] + 1)
                        condition = _contract_condition(expression, None)
                        lines.append(('    ' * len(blocks) + _contract_check(kind, contract['name'], expression, condition), start))
                    else:
                        contract['ensures'].append((expression, _contract_condition(
                            expression, None if contract['void'] else '_ail_result')))
                    continue
                elif statement.startswith('let '):
                    match = re.fullmatch(r'let\s+([A-Za-z_]\w*)(?:\s*:\s*([A-Za-z_]\w*(?:\s*\|\s*None)?|list\s*\[\s*(?:[A-Za-z_]\w*|tuple\s*\[\s*(?:int|float|bytes)(?:\s*,\s*(?:int|float|bytes))*\s*,?\s*\])\s*\]|dict\s*\[\s*(?:str|int)\s*,\s*(?:int|float|str|bytes)\s*\]|set\s*\[\s*(?:int|str)\s*\]|Callable\s*\[.+\]|' + _NESTED + r'))?\s*=\s*(.+)', statement)
                    if not match:
                        raise SyntaxErrorAIL(_let_refusal(statement, part.start[0]))
                    annotation = ': ' + re.sub(r'\s+', '', match[2]) if match[2] else ''
                    statement = f'{match[1]}{annotation} = {match[3]}'
                if blocks:
                    try:
                        parsed = ast.parse(statement).body
                    except SyntaxError as exc:
                        raise SyntaxErrorAIL(f'invalid statement at line {part.start[0]}: {exc.msg}') from exc
                    if (len(parsed) != 1 or not isinstance(parsed[0],
                            (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete, ast.Return, ast.Raise, ast.Break,
                             ast.Continue, ast.Pass, ast.Expr, ast.Assert))):
                        raise SyntaxErrorAIL(f'unsupported statement at line {part.start[0]}')
                    if isinstance(parsed[0], ast.AnnAssign):
                        declaration = parsed[0]
                        annotation = declaration.annotation
                        callable_local = _callable(annotation)
                        element = annotation.slice if isinstance(annotation, ast.Subscript) else None
                        fields = ((element.slice.elts if isinstance(element.slice, ast.Tuple)
                                   else [element.slice]) if isinstance(element, ast.Subscript)
                                  and isinstance(element.value, ast.Name) and element.value.id == 'tuple' else [])
                        field_kinds = tuple(e.id if isinstance(e, ast.Name) else None for e in fields)
                        records = bool(field_kinds) and (set(field_kinds) in ({'int'}, {'float'}, {'int', 'bytes'}))
                        if (not isinstance(declaration.target, ast.Name) or declaration.value is None
                                or not (callable_local or isinstance(annotation, ast.Name)
                                        or isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr)
                                        and isinstance(annotation.left, ast.Name) and isinstance(annotation.right, ast.Constant)
                                        and annotation.right.value is None
                                        or isinstance(annotation, ast.Subscript)
                                        and isinstance(annotation.value, ast.Name)
                                        and (annotation.value.id == 'list'
                                             and (isinstance(annotation.slice, ast.Name) or records
                                                  or re.fullmatch(_NESTED, ast.unparse(annotation)))
                                             or annotation.value.id == 'dict'
                                             and isinstance(annotation.slice, ast.Tuple)
                                             and tuple(e.id if isinstance(e, ast.Name) else None
                                                       for e in annotation.slice.elts) in {(key, value) for key in ('str', 'int') for value in ('int', 'float', 'str', 'bytes')}
                                             or annotation.value.id == 'set'
                                             and isinstance(annotation.slice, ast.Name)
                                             and annotation.slice.id in ('int', 'str')))):
                            raise SyntaxErrorAIL(f'unsupported local annotation at line {part.start[0]}')
                if contract is not None and len(blocks) == contract['depth']:
                    contract['started'] = True
                if (contract is not None and contract['ensures'] and blocks
                        and isinstance(ast.parse(statement).body[0], ast.Return)):
                    returned = ast.parse(statement).body[0].value
                    pad = '    ' * len(blocks)
                    if returned is not None and not contract['void']:
                        lines.append((pad + '_ail_result = ' + ast.get_source_segment(statement, returned), start))
                    for expression, condition in contract['ensures']:
                        lines.append((pad + _contract_check('ensures', contract['name'], expression, condition), start))
                    statement = 'return _ail_result' if returned is not None and not contract['void'] else statement
                lines.append(('    ' * len(blocks) + statement, start))
            else:
                if statement:
                    raise SyntaxErrorAIL(f'missing semicolon before line {part.start[0]}',
                                         lineno=part.start[0], offset=part.start[1] + 1)
                if not blocks:
                    raise SyntaxErrorAIL(f'unmatched closing brace at line {part.start[0]}',
                                         lineno=part.start[0], offset=part.start[1] + 1)
                if (contract is not None and len(blocks) == contract['depth']):
                    if contract['void']:
                        for expression, condition in contract['ensures']:
                            lines.append(('    ' * len(blocks) + _contract_check('ensures', contract['name'], expression, condition), part.start))
                    contract = None
                closed = blocks.pop()
                if (not blocks and not module and closed.startswith('def main(') and lines
                        and not re.match(r'    (?:return\b|raise\b|sys\.exit\()', lines[-1][0])):
                    # Falling off the end of main exits 0, as sys.exit(None) does in Python.
                    lines.append(('    return 0', part.start))
                if (not closed.startswith('impl ') and lines
                        and lines[-1][0] == '    ' * len(blocks) + closed + ':'):
                    lines.append(('    ' * (len(blocks) + 1) + 'pass', part.start))
                if function_bodies is not None and len(blocks) in body_open:
                    target, opened = body_open.pop(len(blocks))
                    function_bodies[target] = (opened, part.start)
                if closed.startswith('impl '):
                    owner = closed.split()[1]
                    if len(lines) == impl_start:
                        raise SyntaxErrorAIL('impl needs at least one method')
                    method_blocks[owner].append(lines[impl_start:])
                    del lines[impl_start:]
    except tokenize.TokenError as exc:
        position = exc.args[1] if len(exc.args) > 1 else None
        known = (isinstance(position, tuple) and len(position) == 2
                 and all(type(value) is int for value in position))
        raise SyntaxErrorAIL(f'incomplete AIL source: {exc}',
                             lineno=position[0] if known else None,
                             offset=position[1] + 1 if known else None) from exc
    if pending or blocks:
        raise SyntaxErrorAIL('unfinished statement or block',
                             lineno=source.count('\n') + 1,
                             offset=len(source.rsplit('\n', 1)[-1]) + 1)
    if not module and main_count != 1:
        raise SyntaxErrorAIL('entry source needs exactly one fn main()')
    for name, end in sorted(structs.items(), key=lambda item: item[1], reverse=True):
        lines[end:end] = [line for body in method_blocks[name] for line in body]
    if source_map is not None:
        source_map.update({index: (position[0], position[1] + 1)
                           for index, (_, position) in enumerate(lines, 1 if module else 2)
                           if position is not None})
    return '\n'.join([*([] if module else ['import sys']), *(line for line, _ in lines),
                      *([] if module else ['sys.exit(main())']), ''])
