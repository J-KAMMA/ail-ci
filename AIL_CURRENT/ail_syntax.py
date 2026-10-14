"""Translate the initial AIL block syntax to the existing checked compiler surface."""
import ast
import builtins
import copy
import io
import importlib.util
import keyword
import math
import operator
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


# ------------------------------------------------------------------------------------------------
# Module constants: `MASK = (1 << 40) - 1` and `const MOD = 10 ** 9 + 7;` are literals the writer
# spelled as arithmetic. Folded here, in place on the same line, for both syntaxes.

class _NotConstant(Exception):
    pass


_FOLD_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Div: operator.truediv,
                ast.Pow: operator.pow, ast.LShift: operator.lshift, ast.RShift: operator.rshift,
                ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor}


def _fold(node, known):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float, str, bytes):
        return node.value
    if isinstance(node, ast.Name) and node.id in known:
        return known[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd, ast.Invert)):
        value = _fold(node.operand, known)
        if type(value) not in (int, float) or isinstance(node.op, ast.Invert) and type(value) is not int:
            raise _NotConstant
        value = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Invert: operator.invert}[type(node.op)](value)
    elif isinstance(node, ast.BinOp) and type(node.op) in _FOLD_BINARY:
        left, right = _fold(node.left, known), _fold(node.right, known)
        numbers = type(left) in (int, float) and type(right) in (int, float)
        if isinstance(node.op, ast.Pow):
            if not numbers or type(right) is int and not 0 <= right <= 64:
                raise _NotConstant
        elif isinstance(node.op, (ast.LShift, ast.RShift)):
            if type(left) is not int or type(right) is not int or not 0 <= right < 64:
                raise _NotConstant
        elif isinstance(node.op, ast.Mult) and not numbers:
            if not ({type(left), type(right)} in ({str, int}, {bytes, int})
                    and len(left if type(left) is not int else right) * (right if type(right) is int else left) <= 4096):
                raise _NotConstant
        elif isinstance(node.op, ast.Add) and not numbers:
            if type(left) is not type(right) or type(left) not in (str, bytes):
                raise _NotConstant
        elif not numbers:
            raise _NotConstant
        value = _FOLD_BINARY[type(node.op)](left, right)
    else:
        raise _NotConstant
    if (type(value) is int and not -(1 << 63) <= value < 1 << 63
            or type(value) is float and not math.isfinite(value)
            or type(value) not in (int, float, str, bytes)):
        raise _NotConstant
    return value


def _is_literal(node):
    return (isinstance(node, ast.Constant) or isinstance(node, ast.UnaryOp)
            and isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(node.operand, ast.Constant))


def _byte_offsets(data):
    starts = [0]
    starts.extend(index + 1 for index, byte in enumerate(data) if byte == 10)
    return starts


def fold_constants(text):
    """Top-level `NAME = <constant arithmetic>` assigned once, rewritten to its literal value."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    stored = {}
    for node in tree.body:
        for target in (node.targets if isinstance(node, ast.Assign) else
                       [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else []):
            for name in ast.walk(target):
                if isinstance(name, ast.Name):
                    stored[name.id] = stored.get(name.id, 0) + 1
    known = {}
    edits = []
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and stored[node.targets[0].id] == 1):
            continue
        try:
            value = _fold(node.value, known)
        except (_NotConstant, ArithmeticError, ValueError, TypeError, RecursionError):
            continue
        known[node.targets[0].id] = value
        if not _is_literal(node.value):
            edits.append((node.value, repr(value)))
    if not edits:
        return text
    data = text.encode('utf8')
    starts = _byte_offsets(data)
    for node, literal in reversed(edits):
        start = starts[node.lineno - 1] + node.col_offset
        end = starts[node.end_lineno - 1] + node.end_col_offset
        padding = data[start:end].count(b'\n')
        replacement = ('(' + literal + '\n' * padding + ')') if padding else literal
        data = data[:start] + replacement.encode('utf8') + data[end:]
    return data.decode('utf8')


# ------------------------------------------------------------------------------------------------
# Python syntax (`--syntax python`): the ordinary Python spellings of what the compiler already
# builds under another name -- `-> str` as the same checked result type the block syntax's
# `-> str` is, `import heapq` / `heapq.heappush` as the built-in heappush, `sys.stdin.buffer.read()`
# as read_stdin_bytes, `@dataclass` as the `__init__` it stands for. Every rewrite replaces source
# text in place and keeps each statement on the line it was written on, so a later refusal points
# at the writer's own line. A construct this pass cannot map is left exactly as written (the
# compiler's general path may still build it) and a note saying why is kept for the refusal.

_HEAPQ = ('heappush', 'heappop', 'heapify', 'heappushpop', 'heapreplace')
_BISECT = ('bisect_left', 'bisect_right', 'bisect', 'insort', 'insort_left', 'insort_right')
_MATH_VALUES = {'pi': repr(math.pi), 'e': repr(math.e), 'tau': repr(math.tau),
                'inf': "float('inf')", 'nan': "float('nan')"}
_MATH_CALLS = ('sqrt', 'floor', 'ceil', 'isqrt', 'gcd', 'fabs')
_MATH_BUILT = ('math.sqrt, math.floor, math.ceil, math.isqrt, math.gcd (two arguments), math.fabs '
               'and the constants math.pi, math.e, math.tau, math.inf, math.nan')
# Exact CPython results: sqrt keeps -0.0 and raises ValueError below zero, isqrt and gcd are
# integer-only (no float rounding reaches the answer).
_MATH_HELPERS = {
    'sqrt': '''def _ail_math_sqrt(x: float) -> float:
    if x < 0.0:
        raise ValueError("math domain error")
    if x == 0.0:
        return x
    return x ** 0.5
''',
    'isqrt': '''def _ail_math_isqrt(n: int) -> int:
    if n < 0:
        raise ValueError("isqrt() argument must be nonnegative")
    if n < 2:
        return n
    x = int(float(n) ** 0.5)
    while x > n // x:
        x -= 1
    while x + 1 <= n // (x + 1):
        x += 1
    return x
''',
    'gcd': '''def _ail_math_gcd(a: int, b: int) -> int:
    x = abs(a)
    y = abs(b)
    while y != 0:
        t = x % y
        x = y
        y = t
    return x
'''}
_TYPING = {'List': 'list', 'Dict': 'dict', 'Set': 'set', 'Tuple': 'tuple', 'FrozenSet': 'frozenset'}
_DROPPED = ('heapq', 'bisect', 'typing', 'dataclasses', '__future__')
_STDOUT_STATEMENTS = ('sys.stdout.write', 'sys.stdout.buffer.write', 'sys.stdout.flush',
                      'sys.stdout.buffer.flush', 'sys.setrecursionlimit')
_ALIASABLE = ('sys.stdout.write', 'sys.stdout.buffer.write', 'sys.stdin.readline',
              'sys.stdin.buffer.read')
_RESULT_NAMES = ('int', 'float', 'str', 'bytes', 'bool', 'bytearray')
_ATOMIC = (ast.Name, ast.Constant, ast.Call, ast.Attribute, ast.Subscript, ast.List, ast.Dict,
           ast.Set, ast.ListComp, ast.SetComp, ast.DictComp, ast.JoinedStr)
_FILE_HINT = ('with open(path) as f: is built for one file opened to read ("r" or "rb") and read '
              'whole with f.read(), or in text mode line by line with `for line in f:`; '
              'read_bytes(path) reads a binary file, write_text(path, text) / write_bytes(path, '
              'data) write one')


def _own_nodes(function):
    """Nodes of `function` itself, not of the functions, lambdas or classes nested in it."""
    pending = list(ast.iter_child_nodes(function))
    while pending:
        node = pending.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            pending.extend(ast.iter_child_nodes(node))


class _SurfaceExpr(ast.NodeTransformer):
    def __init__(self, surface):
        self.surface = surface
        self.changed = False

    def replaced(self, new, old):
        self.changed = True
        return ast.fix_missing_locations(ast.copy_location(new, old))

    def visit_Call(self, node):
        surface = self.surface
        path = surface.path(node.func)
        node.args = [self.visit(arg) for arg in node.args]
        for item in node.keywords:
            item.value = self.visit(item.value)
            if (item.arg == 'key' and isinstance(item.value, ast.Attribute) and item.value.attr == '__getitem__'
                    and isinstance(item.value.value, (ast.Name, ast.Attribute))):
                # `key=xs.__getitem__` is `key=lambda i: xs[i]`, the key form that is built.
                item.value = ast.Lambda(
                    args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='_ail_key')], vararg=None,
                                       kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                    body=ast.Subscript(value=item.value.value, slice=ast.Name(id='_ail_key', ctx=ast.Load()),
                                       ctx=ast.Load()))
                self.changed = True
        new = surface.call(node, path)
        if new is not None:
            return self.replaced(new, node)
        if path is None:
            node.func = self.visit(node.func)
        return node

    def visit_Attribute(self, node):
        surface = self.surface
        path = surface.path(node)
        if path is not None:
            new = surface.value(node, path)
            return node if new is None else self.replaced(new, node)
        if isinstance(node.value, ast.Name) and node.value.id in surface.files:
            surface.note(node, f'{node.value.id}.{node.attr}: ' + _FILE_HINT)
            return node
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        surface = self.surface
        if not isinstance(node.ctx, ast.Load):
            return node
        if node.id in surface.files:
            surface.note(node, f'the file object {node.id} is used as a value: ' + _FILE_HINT)
        elif node.id in surface.names:
            new = surface.value(node, surface.names[node.id])
            if new is not None:
                return self.replaced(new, node)
        return node


class _Surface:
    def __init__(self, source):
        self.data = source.encode('utf8')
        self.starts = _byte_offsets(self.data)
        self.tree = ast.parse(source)
        self.edits = []
        self.notes = []
        self.helpers = []
        self.imports = []
        self.modules = {'sys': 'sys'}  # local module name -> module
        self.names = {}                # local bare name -> dotted path it stands for
        self.aliases = {}              # `write = sys.stdout.write` -> {'write': 'sys.stdout.write'}
        self.alias_nodes = set()
        self.typing = {}               # local name -> typing name
        self.keep = set()              # dropped-by-default modules still needed as written
        self.files = {}                # file object name -> (path expression, binary)
        self.dataclasses = {}          # class name -> [(field, default text | None)]
        self.consumed = set()
        self.void = set()
        self.classes = {node.name for node in self.tree.body if isinstance(node, ast.ClassDef)}
        self.parents = {child: parent for parent in ast.walk(self.tree)
                        for child in ast.iter_child_nodes(parent)}

    # -- text ---------------------------------------------------------------------------------
    def offset(self, line, column):
        return self.starts[line - 1] + column

    def replace(self, node, text, statement=False):
        self.edits.append((self.offset(node.lineno, node.col_offset),
                           self.offset(node.end_lineno, node.end_col_offset), text, statement))

    def note(self, node, message):
        entry = (node.lineno, message)
        if entry not in self.notes:
            self.notes.append(entry)

    def header_colon(self, statement):
        """Byte offset of the `:` that ends a def/with header."""
        start = self.offset(statement.lineno, statement.col_offset)
        end = self.offset(statement.body[0].lineno, statement.body[0].col_offset)
        segment = self.data[start:end].decode('utf8')
        lines = segment.splitlines(True)
        depth = 0
        try:
            for part in tokenize.generate_tokens(io.StringIO(segment).readline):
                if part.type != token.OP:
                    continue
                if part.string in '([{':
                    depth += 1
                elif part.string in ')]}':
                    depth -= 1
                elif part.string == ':' and depth == 0:
                    row, column = part.start
                    return (start + sum(len(line.encode('utf8')) for line in lines[:row - 1])
                            + len(lines[row - 1][:column].encode('utf8')))
        except (tokenize.TokenError, IndentationError):
            pass
        return None

    def apply(self):
        data = self.data
        floor = len(data) + 1
        for start, end, text, statement in sorted(self.edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
            if end > floor:
                continue                       # nested inside a later edit's text: never expected
            missing = data[start:end].count(b'\n') - text.count('\n')
            if missing > 0:
                text = text + '\n' * missing if statement else '(' + text + '\n' * missing + ')'
            data = data[:start] + text.encode('utf8') + data[end:]
            floor = start
        text = data.decode('utf8')
        if self.helpers:
            text = text.rstrip('\n') + '\n\n\n' + '\n\n'.join(_MATH_HELPERS[name] for name in self.helpers)
        return text

    # -- names --------------------------------------------------------------------------------
    def path(self, node):
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        root = self.names.get(node.id) or self.modules.get(node.id)
        if root is None:
            return None
        return '.'.join([root, *reversed(parts)])

    def collect(self):
        stored = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ('heapq', 'bisect', 'math', 'typing', 'dataclasses', 'sys'):
                        self.modules[alias.asname or alias.name] = alias.name
            elif isinstance(node, ast.ImportFrom) and not node.level:
                for alias in node.names:
                    local = alias.asname or alias.name
                    if node.module in ('heapq', 'bisect', 'math', 'dataclasses'):
                        self.names[local] = f'{node.module}.{alias.name}'
                    elif node.module == 'typing':
                        self.typing[local] = alias.name
            names = ([node.id] if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load)
                     else [node.arg] if isinstance(node, ast.arg)
                     else [node.name] if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else [])
            for name in names:
                stored[name] = stored.get(name, 0) + 1
        for node in ast.walk(self.tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name) and stored[node.targets[0].id] == 1):
                path = self.path(node.value) if isinstance(node.value, ast.Attribute) else None
                if path in _ALIASABLE:
                    self.aliases[node.targets[0].id] = path
                    self.names[node.targets[0].id] = path
                    self.alias_nodes.add(node)

    # -- expressions --------------------------------------------------------------------------
    def rewritten(self, node):
        rewriter = _SurfaceExpr(self)
        new = rewriter.visit(copy.deepcopy(node))
        return new, rewriter.changed

    def expression(self, node):
        if node is None:
            return
        new, changed = self.rewritten(node)
        if changed:
            text = ast.unparse(new)
            self.replace(node, text if isinstance(new, _ATOMIC) else '(' + text + ')')

    def value(self, node, path):
        module, _, name = path.partition('.')
        if module == 'math' and name in _MATH_VALUES:
            return ast.parse(_MATH_VALUES[name], mode='eval').body
        if module in ('heapq', 'bisect') and name in (_HEAPQ if module == 'heapq' else _BISECT):
            return ast.Name(id=name, ctx=ast.Load()) if isinstance(node, ast.Attribute) else None
        if module in ('heapq', 'bisect', 'math'):
            if module != 'math':
                self.keep.add(module)
            self.note(node, f'{path} used as a value is not built; the built ones are '
                      + (_MATH_BUILT if module == 'math' else ', '.join(
                          f'{module}.{each}' for each in (_HEAPQ if module == 'heapq' else _BISECT)))
                      + ', called directly')
        elif path in _STDOUT_STATEMENTS or path.startswith('sys.stdin.buffer'):
            self.note(node, f'{path} used as a value is not built: call it as a statement '
                      '(sys.stdout.write(text) on its own line, sys.stdin.buffer.read())')
        return None

    def opened(self, call):
        """`open(path[, mode][, encoding=...])` read whole: (path, binary, needs rewrite)."""
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'open'
                and 1 <= len(call.args) <= 2 and not any(isinstance(arg, ast.Starred) for arg in call.args)):
            return None
        mode = call.args[1] if len(call.args) == 2 else None
        rewrite = mode is not None
        for item in call.keywords:
            if item.arg == 'mode' and mode is None:
                mode = item.value
            elif not (item.arg == 'encoding' and isinstance(item.value, ast.Constant)
                      and str(item.value.value).lower().replace('-', '').replace('_', '') == 'utf8'):
                return None
            rewrite = True
        if mode is not None and not (isinstance(mode, ast.Constant) and isinstance(mode.value, str)):
            return None
        mode = 'r' if mode is None else mode.value
        if ''.join(sorted(mode)) == 'br':
            return call.args[0], True, True
        if mode in ('r', 'rt', 'tr'):
            return call.args[0], False, rewrite
        return None

    @staticmethod
    def read_whole(path, binary):
        path = copy.deepcopy(path)
        if binary:
            return ast.Call(func=ast.Name(id='read_bytes', ctx=ast.Load()), args=[path], keywords=[])
        return ast.Call(func=ast.Attribute(value=ast.Call(func=ast.Name(id='open', ctx=ast.Load()),
                                                          args=[path], keywords=[]),
                                           attr='read', ctx=ast.Load()), args=[], keywords=[])

    def call(self, node, path):
        func = node.func
        if path is not None:
            module, _, name = path.partition('.')
            if module in ('heapq', 'bisect') and name:
                built = _HEAPQ if module == 'heapq' else _BISECT
                if name not in built:
                    self.keep.add(module)
                    self.note(node, f'{module}.{name}() is not built in; the {module} functions here '
                              f'are {", ".join(built)} (no import needed)'
                              + ('; for the k smallest, sort a copy or pop k times from a heap'
                                 if name in ('nsmallest', 'nlargest') else ''))
                    return None
                if isinstance(func, ast.Name) and func.id == name:
                    return None
                return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=node.args, keywords=node.keywords)
            if module == 'math' and name:
                return self.math_call(node, name)
            if path == 'sys.stdin.buffer.read' and not node.keywords and len(node.args) <= 1:
                return ast.Call(func=ast.Name(id='read_stdin_bytes', ctx=ast.Load()),
                                args=node.args or [ast.parse('1 << 40', mode='eval').body], keywords=[])
            if path in _STDOUT_STATEMENTS:
                self.note(node, f'{path}(...) is built as a statement on its own line; its result '
                          'is not a value')
                return None
            if path.startswith('sys.stdin.buffer'):
                self.note(node, f'{path}(): only sys.stdin.buffer.read() (all of stdin as bytes) is '
                          'built; read text lines with sys.stdin.readline() or `for line in sys.stdin:`')
                return None
            if isinstance(func, ast.Name) and func.id in self.aliases:
                return ast.Call(func=ast.parse(path, mode='eval').body, args=node.args, keywords=node.keywords)
            return None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in self.files:
            path_node, binary = self.files[func.value.id]
            if func.attr == 'read' and not node.args and not node.keywords:
                return self.read_whole(path_node, binary)
            self.note(node, f'{func.value.id}.{func.attr}(): ' + _FILE_HINT)
            return None
        if isinstance(func, ast.Attribute) and func.attr == 'read' and not node.args and not node.keywords:
            opened = self.opened(func.value)
            if opened is not None and opened[2]:
                return self.read_whole(opened[0], opened[1])
            return None
        if isinstance(func, ast.Name) and func.id in self.dataclasses:
            return self.construct(node)
        return None

    def math_call(self, node, name):
        args = node.args
        if not node.keywords and not any(isinstance(arg, ast.Starred) for arg in args):
            if name in ('sqrt', 'isqrt') and len(args) == 1 or name == 'gcd' and len(args) == 2:
                if name not in self.helpers:
                    self.helpers.append(name)
                return ast.Call(func=ast.Name(id='_ail_math_' + name, ctx=ast.Load()), args=args, keywords=[])
            if len(args) == 1 and name in ('floor', 'ceil', 'fabs'):
                def call(function, argument):
                    return ast.Call(func=ast.Name(id=function, ctx=ast.Load()), args=[argument], keywords=[])
                if name == 'fabs':
                    return call('abs', call('float', args[0]))
                if name == 'floor':      # int(x // 1): floor of an int or a float, as an int
                    return call('int', ast.BinOp(left=args[0], op=ast.FloorDiv(), right=ast.Constant(value=1)))
                return ast.UnaryOp(op=ast.USub(), operand=call('int', ast.BinOp(
                    left=ast.UnaryOp(op=ast.USub(), operand=args[0]), op=ast.FloorDiv(), right=ast.Constant(value=1))))
        self.note(node, f'math.{name}() with these arguments is not built; the math names built here '
                  f'are {_MATH_BUILT}')
        return None

    def construct(self, node):
        """A dataclass constructor call with defaults or keywords, as the positional call the
        generated `__init__` takes."""
        fields = self.dataclasses[node.func.id]
        if (any(isinstance(arg, ast.Starred) for arg in node.args) or len(node.args) > len(fields)
                or any(item.arg is None for item in node.keywords)):
            return None
        given = {item.arg: item.value for item in node.keywords}
        if not node.keywords and len(node.args) == len(fields):
            return None
        args = []
        for index, (field, default) in enumerate(fields):
            if index < len(node.args):
                if field in given:
                    return None
                args.append(node.args[index])
            elif field in given:
                args.append(given.pop(field))
            elif default is not None:
                args.append(ast.parse(default, mode='eval').body)
            else:
                return None
        if given:
            return None
        return ast.Call(func=node.func, args=args, keywords=[])

    # -- annotations --------------------------------------------------------------------------
    def normalized(self, node):
        """`List[int]`, `Optional[Node]`, `"Node"` as `list[int]`, `Node | None`, `Node`."""
        surface = self

        def typing_name(node):
            if isinstance(node, ast.Name):
                return surface.typing.get(node.id)
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and surface.modules.get(node.value.id) == 'typing'):
                return node.attr
            return None

        class Normal(ast.NodeTransformer):
            changed = False

            def visit_Constant(self, node):
                if isinstance(node.value, str):
                    try:
                        parsed = ast.parse(node.value.strip(), mode='eval').body
                    except SyntaxError:
                        return node
                    self.changed = True
                    return self.visit(parsed)
                return node

            def visit_Subscript(self, node):
                name = typing_name(node.value)
                node.slice = self.visit(node.slice)
                if name in ('Optional', 'Union'):
                    elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
                    if name == 'Optional':
                        elements = [*elements, ast.Constant(value=None)]
                    self.changed = True
                    result = elements[0]
                    for element in elements[1:]:
                        result = ast.BinOp(left=result, op=ast.BitOr(), right=element)
                    return result
                if name in _TYPING:
                    self.changed = True
                    node.value = ast.Name(id=_TYPING[name], ctx=ast.Load())
                return node

            def visit_Name(self, node):
                name = typing_name(node)
                if name in _TYPING:
                    self.changed = True
                    return ast.Name(id=_TYPING[name], ctx=ast.Load())
                return node

            visit_Attribute = visit_Name

        normal = Normal()
        new = normal.visit(copy.deepcopy(node))
        return new, normal.changed

    def annotation(self, node):
        if node is not None:
            new, changed = self.normalized(node)
            if changed:
                self.replace(node, ast.unparse(new))

    def contract(self, node):
        """The block syntax's checked result spelling for a Python return annotation, if it has one."""
        if isinstance(node, ast.Constant) and node.value is None:
            return '__ail_checked_void__'
        if isinstance(node, ast.Name) and (node.id in _RESULT_NAMES or node.id in self.classes):
            return f'__ail_checked_{node.id}__'
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr) and isinstance(node.left, ast.Name)
                and node.left.id in self.classes and isinstance(node.right, ast.Constant)
                and node.right.value is None):
            return f'__ail_checked_{node.left.id}__ | None'
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'list'
                and isinstance(node.slice, ast.Name)):
            if node.slice.id == 'float':
                return '__ail_checked_flist__'
            if node.slice.id in ('int', 'str', 'bytes', 'bool') or node.slice.id in self.classes:
                return f'__ail_checked_list[{node.slice.id}]'
        return None

    # -- statements ---------------------------------------------------------------------------
    def block(self, body, function, owner):
        for statement in body:
            self.statement(statement, function, owner)

    def statement(self, node, function, owner):
        if node in self.consumed:
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            self.imports.append(node)
        elif isinstance(node, ast.FunctionDef):
            self.function(node, owner)
        elif isinstance(node, ast.ClassDef):
            self.klass(node)
        elif node in self.alias_nodes:
            self.replace(node, 'pass', True)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and self.output(node):
            pass
        elif isinstance(node, ast.With) and self.with_open(node, function, owner):
            pass
        elif isinstance(node, ast.Assign) and self.file_assign(node, function):
            pass
        elif isinstance(node, ast.AnnAssign):
            self.ann_assign(node, function, owner)
        elif (isinstance(node, ast.Return) and function in self.void
              and isinstance(node.value, ast.Constant) and node.value.value is None):
            self.replace(node, 'return', True)
        elif isinstance(node, ast.For) and self.file_loop(node):
            self.expression(node.target)
            self.block(node.body, function, owner)
            self.block(node.orelse, function, owner)
        else:
            self.generic(node, function, owner)

    def generic(self, node, function, owner):
        for _, value in ast.iter_fields(node):
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, ast.stmt):
                    self.statement(item, function, owner)
                elif isinstance(item, ast.expr):
                    self.expression(item)
                elif isinstance(item, ast.keyword):
                    self.expression(item.value)
                elif isinstance(item, ast.withitem):
                    self.expression(item.context_expr)
                    self.expression(item.optional_vars)
                elif isinstance(item, ast.ExceptHandler):
                    self.expression(item.type)
                    self.block(item.body, function, owner)

    def function(self, node, owner):
        arguments = node.args
        for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                         arguments.vararg, arguments.kwarg):
            if argument is not None:
                self.annotation(argument.annotation)
        for default in (*arguments.defaults, *arguments.kw_defaults):
            self.expression(default)
        for decorator in node.decorator_list:
            self.expression(decorator)
        own = list(_own_nodes(node))
        values = any(isinstance(each, ast.Return) and each.value is not None
                     and not (isinstance(each.value, ast.Constant) and each.value.value is None)
                     for each in own)
        if node.returns is None:
            if (owner is not None and node.name != '__init__' and not values
                    and not any(isinstance(each, (ast.Yield, ast.YieldFrom)) for each in own)):
                colon = self.header_colon(node)
                if colon is not None:
                    self.edits.append((colon, colon, ' -> __ail_checked_void__', False))
                    self.void.add(node)
        else:
            new, changed = self.normalized(node.returns)
            result = None if node.name == '__init__' else self.contract(new)
            if result is not None:
                self.replace(node.returns, result)
                if result == '__ail_checked_void__':
                    self.void.add(node)
            elif changed:
                self.replace(node.returns, ast.unparse(new))
        files = dict(self.files)
        self.block(node.body, node, None)
        self.files = files

    def klass(self, node):
        decorators = [each for each in node.decorator_list
                      if self.path(each.func if isinstance(each, ast.Call) else each) == 'dataclasses.dataclass']
        if decorators:
            self.dataclass(node, decorators[0])
        for base in node.bases:
            self.expression(base)
        self.block(node.body, None, node)

    def dataclass(self, node, decorator):
        options = {item.arg: item.value for item in decorator.keywords} if isinstance(decorator, ast.Call) else {}
        for option, value in options.items():
            enabled = not (isinstance(value, ast.Constant) and not value.value)
            if option == 'init' and not enabled or option == 'order' and enabled:
                self.note(node, f'@dataclass({option}={ast.unparse(value)}) is not built; @dataclass '
                          'with annotated fields is, as the __init__ it generates')
                return
        if any(isinstance(each, ast.FunctionDef) and each.name == '__init__' for each in node.body):
            return
        fields = []
        for statement in node.body:
            if not (isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)):
                continue
            annotation, _ = self.normalized(statement.annotation)
            if 'ClassVar' in ast.unparse(annotation):
                self.note(statement, 'a ClassVar in a @dataclass is not built')
                return
            default = None
            value = statement.value
            if (isinstance(value, ast.Call) and self.path(value.func) == 'dataclasses.field'):
                options = {item.arg: item.value for item in value.keywords}
                factory = options.pop('default_factory', None)
                plain = options.pop('default', None)
                if value.args or set(options) - {'repr', 'compare', 'hash'}:
                    self.note(statement, 'field(...) in a @dataclass is built with default= or '
                              'default_factory= only')
                    return
                if factory is not None:
                    shown = {'list': '[]', 'dict': '{}', 'set': 'set()'}
                    default = (shown.get(factory.id) if isinstance(factory, ast.Name) else None) or (
                        ast.unparse(factory.body) if isinstance(factory, ast.Lambda) and not factory.args.args
                        else ast.unparse(factory) + '()')
                elif plain is not None:
                    default = ast.unparse(self.rewritten(plain)[0])
            elif value is not None:
                default = ast.unparse(self.rewritten(value)[0])
            fields.append((statement, statement.target.id, ast.unparse(annotation), default))
        if not fields:
            return
        start = self.offset(decorator.lineno, decorator.col_offset)
        at = start - 1
        while at >= 0 and self.data[at:at + 1] in (b' ', b'\t'):
            at -= 1
        if at < 0 or self.data[at:at + 1] != b'@':
            return
        self.edits.append((at, self.offset(decorator.end_lineno, decorator.end_col_offset), '', False))
        parameters = ', '.join(f'{name}: {annotation}' for _, name, annotation, _ in fields)
        body = '; '.join(f'self.{name} = {name}' for _, name, _, _ in fields)
        self.replace(fields[0][0], f'def __init__(self, {parameters}): {body}', True)
        for statement, *_ in fields[1:]:
            self.replace(statement, '', True)  # a class body here holds methods only, not `pass`
        self.consumed.update(statement for statement, *_ in fields)
        self.dataclasses[node.name] = [(name, default) for _, name, _, default in fields]

    def ann_assign(self, node, function, owner):
        if isinstance(node.target, ast.Attribute) and node.value is None:
            self.replace(node, 'pass', True)
            return
        if function is None and owner is None and isinstance(node.target, ast.Name) and node.value is not None:
            value, _ = self.rewritten(node.value)
            self.replace(node, f'{node.target.id} = {ast.unparse(value)}', True)
            return
        self.annotation(node.annotation)
        self.expression(node.value)

    def output(self, node):
        call = node.value
        path = self.path(call.func)
        if path in _STDOUT_STATEMENTS:
            if path in ('sys.stdout.flush', 'sys.stdout.buffer.flush', 'sys.setrecursionlimit'):
                self.replace(node, 'pass', True)
                return True
            if len(call.args) == 1 and not call.keywords and not isinstance(call.args[0], ast.Starred):
                argument = ast.unparse(self.rewritten(call.args[0])[0])
                self.replace(node, f"print({argument}, end='')" if path == 'sys.stdout.write'
                             else f'write_stdout_bytes({argument})', True)
                return True
        func = call.func
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in self.files
                and func.attr == 'close' and not call.args and not call.keywords):
            self.replace(node, 'pass', True)
            return True
        return False

    def file_uses(self, name, body, binary, binding=None):
        """Every use of the file object `name` in `body` (other than `binding`, the name it is
        opened into) is one this pass maps."""
        for statement in body:
            for node in ast.walk(statement):
                if not (isinstance(node, ast.Name) and node.id == name) or node is binding:
                    continue
                if not isinstance(node.ctx, ast.Load):
                    return False
                parent = self.parents.get(node)
                grand = self.parents.get(parent)
                if isinstance(parent, ast.Attribute) and isinstance(grand, ast.Call) and grand.func is parent \
                        and not grand.args and not grand.keywords:
                    if parent.attr == 'read':
                        continue
                    if parent.attr == 'close' and isinstance(self.parents.get(grand), ast.Expr):
                        continue
                    if (parent.attr == 'readlines' and not binary and isinstance(self.parents.get(grand), ast.For)
                            and self.parents[grand].iter is grand):
                        continue
                if isinstance(parent, ast.For) and parent.iter is node and not binary:
                    continue
                return False
        return True

    def stable(self, path, body):
        """The path expression names the same file everywhere in `body`."""
        names = {node.id for node in ast.walk(path) if isinstance(node, ast.Name)}
        if not all(isinstance(node, (ast.Name, ast.Constant, ast.Attribute, ast.Subscript, ast.Load,
                                     ast.expr_context)) for node in ast.walk(path)):
            return False
        return not any(isinstance(node, ast.Name) and node.id in names and not isinstance(node.ctx, ast.Load)
                       for statement in body for node in ast.walk(statement))

    def with_open(self, node, function, owner):
        if not any(isinstance(item.context_expr, ast.Call) and isinstance(item.context_expr.func, ast.Name)
                   and item.context_expr.func.id == 'open' for item in node.items):
            return False
        item = node.items[0]
        opened = self.opened(item.context_expr) if len(node.items) == 1 else None
        target = item.optional_vars
        if (opened is None or not isinstance(target, ast.Name) or not self.stable(opened[0], node.body)
                or not self.file_uses(target.id, node.body, opened[1])):
            self.note(node, _FILE_HINT)
            return False
        colon = self.header_colon(node)
        if colon is None:
            return False
        self.edits.append((self.offset(node.lineno, node.col_offset), colon + 1, 'if True:', True))
        saved = dict(self.files)
        self.files[target.id] = (opened[0], opened[1])
        self.block(node.body, function, owner)
        self.files = saved
        return True

    def file_assign(self, node, function):
        if not (function is not None and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            return False
        opened = self.opened(node.value)
        if opened is None:
            return False
        name = node.targets[0].id
        stores = sum(1 for each in _own_nodes(function)
                     if isinstance(each, ast.Name) and each.id == name and not isinstance(each.ctx, ast.Load))
        if stores != 1 or not self.stable(opened[0], function.body) \
                or not self.file_uses(name, function.body, opened[1], node.targets[0]):
            self.note(node, _FILE_HINT)
            return False
        self.replace(node, 'pass', True)
        self.files[name] = (opened[0], opened[1])
        return True

    def file_loop(self, node):
        iterated = node.iter
        if (isinstance(iterated, ast.Call) and isinstance(iterated.func, ast.Attribute)
                and iterated.func.attr == 'readlines' and not iterated.args):
            iterated = iterated.func.value
        if not (isinstance(iterated, ast.Name) and iterated.id in self.files):
            return False
        path, binary = self.files[iterated.id]
        if binary:
            return False
        self.replace(node.iter, f'open({ast.unparse(path)})')
        return True

    def finish_imports(self):
        for node in self.imports:
            if isinstance(node, ast.Import):
                kept = [alias for alias in node.names if alias.name not in _DROPPED or alias.name in self.keep]
                if len(kept) != len(node.names):
                    self.replace(node, 'import ' + ', '.join(
                        alias.name + (f' as {alias.asname}' if alias.asname else '') for alias in kept)
                        if kept else 'pass', True)
            elif not node.level and node.module in ('typing', 'dataclasses', '__future__'):
                self.replace(node, 'pass', True)
            elif not node.level and node.module in ('heapq', 'bisect', 'math'):
                built = {'heapq': _HEAPQ, 'bisect': _BISECT, 'math': (*_MATH_CALLS, *_MATH_VALUES)}[node.module]
                if node.module not in self.keep and all(alias.name in built for alias in node.names):
                    self.replace(node, 'pass', True)
                else:
                    missing = [alias.name for alias in node.names if alias.name not in built]
                    if missing:
                        self.note(node, f'from {node.module} import {", ".join(missing)}: not built in; '
                                  + (f'the math names built here are {_MATH_BUILT}' if node.module == 'math'
                                     else f'the {node.module} functions here are {", ".join(built)} '
                                     '(no import needed)'))

    def run(self):
        self.collect()
        self.block(self.tree.body, None, None)
        self.finish_imports()
        return self.apply()


def python_surface(source, notes=None):
    """Map the Python spellings above onto the compiler's own; `notes` collects (line, why) for
    the constructs left as written."""
    try:
        surface = _Surface(source)
    except (SyntaxError, ValueError):
        return source                          # the caller's own parse reports it
    text = surface.run()
    if notes is not None:
        notes.extend(sorted(surface.notes))
    return text


def python_wording(message):
    """A refusal written for the block syntax, respelled for a reader of the Python syntax: the
    code it quotes loses `let` and the braces, a struct is a class."""
    def snippet(match):
        code = match.group(1)
        if not re.search(r'\blet\s|\bstruct\s|\{\s|;', code):
            return match.group(0)
        code = re.sub(r'\bstruct\s+(\w+)\s*\{\s*(.*?)\s*\}',
                      lambda found: '@dataclass class %s: %s' % (
                          found[1], ', '.join(part.strip() for part in found[2].split(';') if part.strip())), code)
        code = re.sub(r'\blet\s+', '', code)
        code = re.sub(r'\s*\{\s+', ': ', code)
        code = re.sub(r';?\s+\}', '', code)
        code = re.sub(r'\s*;\s*$', '', code.strip())
        return '`' + code + '`'
    message = re.sub(r'`([^`\n]*)`', snippet, message)
    message = re.sub(r'\ba let\b', 'an assignment', message)
    message = re.sub(r'(?<!C )\bstructs\b', 'class instances', message)
    message = re.sub(r'(?<!C )\bstruct\b', 'class', message)
    return message
