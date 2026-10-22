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
import sys
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
            return ('a `let` needs an initial value.\n'
                    '  write instead: `let x = 0;` (or `let x: int = 0;`)')
        return ('this `let` is not of the form `let name = value;`.\n'
                '  write instead: `let total: int = 0;` (one name, an optional type, then `= value`)')
    name, annotation = found[1], re.sub(r'\s+', '', found[2])
    head = f'`let {name}: {annotation}`'
    if re.match(r'list\[(?:list|set|dict|tuple\[[^]]*(?:str|list))', annotation):
        return (f'{head}: a list of lists holds rows of int, float, str or a struct; lists of '
                f'sets, dicts, bytes or deeper lists are not supported.\n'
                f'  write instead: `let {name}: list[list[int]] = [[] for _ in range(n)];`, '
                f'or a list of structs')
    key = re.match(r'(dict|set)\[([A-Za-z_]\w*)', annotation)
    if key and key[2] not in ('str', 'int'):
        rewrite = ('key it by str with `.decode()`: `let d: dict[str, int] = {}; d[k.decode()] = v;`'
                   if key[2] == 'bytes' else f'key it by str or int: `let {name}: {key[1]}[str, int] = {{}};`')
        return f'{head}: {key[1]} keys must be str or int, not {key[2]}.\n  write instead: {rewrite}'
    if key and annotation.startswith('dict['):
        if annotation.endswith(',bool]'):
            return (f'{head}: a dict value must be int, float, str or bytes, not bool.\n'
                    f'  write instead: `let {name}: dict[{key[2]}, int] = {{}};` storing 1 or 0 '
                    f'(`{name}[k] = 1`, test with `k in {name}`)')
        return (f'{head}: a dict value must be int, float, str or bytes.\n'
                f'  write instead: keep the values in their own list and map each key to its '
                f'index (`let {name}: dict[{key[2]}, int] = {{}};`)')
    return (f'{head}: this type is not supported in a `let`.\n'
            f'  write instead: int, float, str, bytes, a struct, T | None, list[T], '
            f'list[tuple[...]], dict[str|int, int|float|str|bytes], set[int|str], or no type at all '
            f'(`let {name} = ...;`)')

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


def _relib():
    """python/pkg-v12/relib.py (the `re` module's compile-time half), loaded as _callable loads its codec."""
    if not hasattr(_relib, 'module'):
        spec = importlib.util.spec_from_file_location(
            '_ail_relib', Path(__file__).parent / 'python' / 'pkg-v12' / 'relib.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _relib.module = module
    return _relib.module


def _raisefrom():
    """python/pkg-v12/raisefrom.py (`raise X from Y`: the cause dropped, it changes no output here)."""
    if not hasattr(_raisefrom, "module"):
        spec = importlib.util.spec_from_file_location(
            "_ail_raisefrom", Path(__file__).parent / "python" / "pkg-v12" / "raisefrom.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _raisefrom.module = module
    return _raisefrom.module


def _matchlower():
    """python/pkg-v12/matchlower.py (the match statement lowered to an if/elif chain)."""
    if not hasattr(_matchlower, "module"):
        spec = importlib.util.spec_from_file_location(
            "_ail_matchlower", Path(__file__).parent / "python" / "pkg-v12" / "matchlower.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _matchlower.module = module
    return _matchlower.module


def _nestfn():
    """python/pkg-v12/nestfn.py (nested functions that share names with their enclosing function, lifted)."""
    if not hasattr(_nestfn, "module"):
        spec = importlib.util.spec_from_file_location(
            "_ail_nestfn", Path(__file__).parent / "python" / "pkg-v12" / "nestfn.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _nestfn.module = module
    return _nestfn.module


def _optlib():
    """python/pkg-v12/optlib.py (scalar `int | None` / `Optional[str]`, lowered onto a flag and a value)."""
    if not hasattr(_optlib, "module"):
        spec = importlib.util.spec_from_file_location(
            "_ail_optlib", Path(__file__).parent / "python" / "pkg-v12" / "optlib.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _optlib.module = module
    return _optlib.module


def _tuplib():
    """python/pkg-v12/tuplib.py (tuples, lowered onto classes before the surface pass)."""
    if not hasattr(_tuplib, "module"):
        spec = importlib.util.spec_from_file_location(
            "_ail_tuplib", Path(__file__).parent / "python" / "pkg-v12" / "tuplib.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _tuplib.module = module
    return _tuplib.module


def _collib():
    """python/pkg-v12/collib.py (`collections`, lowered onto dict / list / classes before the surface pass)."""
    if not hasattr(_collib, "module"):
        spec = importlib.util.spec_from_file_location(
            "_ail_collib", Path(__file__).parent / "python" / "pkg-v12" / "collib.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _collib.module = module
    return _collib.module


def _threadlib():
    """python/pkg-v12/threadlib.py (stage G12: threading, queue, concurrent.futures; the first source pass)."""
    if not hasattr(_threadlib, "module"):
        here = str(Path(__file__).parent / "python" / "pkg-v12")
        if here not in sys.path:
            sys.path.insert(0, here)
        import threadlib
        _threadlib.module = threadlib
    return _threadlib.module


def _stdlib5():
    """python/pkg-v12/stdlib5.py (library batch 5: fractions, enum, namedtuple, random.Random, ... lowered first)."""
    if not hasattr(_stdlib5, "module"):
        here = str(Path(__file__).parent / "python" / "pkg-v12")
        if here not in sys.path:
            sys.path.insert(0, here)
        import stdlib5
        _stdlib5.module = stdlib5
    return _stdlib5.module


def _stdlib4():
    """python/pkg-v12/stdlib4.py (library batch 4: csv, datetime, ... lowered before the other source passes)."""
    if not hasattr(_stdlib4, "module"):
        here = str(Path(__file__).parent / "python" / "pkg-v12")
        if here not in sys.path:
            sys.path.insert(0, here)
        import stdlib4
        _stdlib4.module = stdlib4
    return _stdlib4.module


_OPTIONAL =re.compile(r'\bOptional\s*\[\s*([A-Za-z_]\w*)\s*\]')


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
    current_start = None

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
            current_start = start
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
                        raise SyntaxErrorAIL('this `fn` header is not of the form `fn name(a: int, b: str) -> int {`.\n'
                                             '  write instead: `fn add(a: int, b: int) -> int { return a + b; }` '
                                             '(the result type follows `->`, never `:`)')
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
                            raise SyntaxErrorAIL('`fn main` takes no parameters.\n'
                                                 '  write instead: `fn main() -> int { ... }`; read input from sys.stdin or sys.argv')
                        if result and result != 'int':
                            raise SyntaxErrorAIL('`fn main` must return int (or have no result type).\n'
                                                 '  write instead: `fn main() -> int { ...; return 0; }`')
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
                        raise SyntaxErrorAIL('a statement outside any function; only `fn`, `struct`, `const` and `use` '
                                             'can be at the top level.\n'
                                             '  write instead: move it into `fn main() -> int { ... }`')
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
                        raise SyntaxErrorAIL(f'unsupported block header: `{statement}`.\n'
                                             f'  write instead: a block opens with `if`, `elif`, `else`, `while`, `for`, '
                                             f'`try`, `except`, `fn` or `struct`, e.g. `if x > 0 {{ ... }}`')
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
                        raise SyntaxErrorAIL('a statement outside any function; only `fn`, `struct`, `const` and `use` '
                                         'can be at the top level.\n'
                                         '  write instead: `const NAME = 10;` for a constant, or move the '
                                         'statement into `fn main() -> int { ... }`')
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
                        raise SyntaxErrorAIL(f'`{statement.strip()}` is not valid here ({exc.msg}).\n'
                                             f'  write instead: one plain statement ending in `;`, such as `x += 1;` '
                                             f'(there is no `x++`; use `and`/`or`/`not`, not `&&`/`||`/`!`)') from exc
                    if (len(parsed) != 1 or not isinstance(parsed[0],
                            (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete, ast.Return, ast.Raise, ast.Break,
                             ast.Continue, ast.Pass, ast.Expr, ast.Assert))):
                        raise SyntaxErrorAIL(f'`{statement.strip()}` is not a statement form this language has.\n'
                                             f'  write instead: an assignment, `return`, a call, `break`/`continue`, '
                                             f'or open a block with `if`/`while`/`for`/`try` and braces')
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
                            raise SyntaxErrorAIL(f'`{statement.strip()}`: this annotation is not supported on a local.\n'
                                             f'  write instead: int, float, str, bytes, a struct, T | None, list[T], '
                                             f'dict[str|int, int|float|str|bytes], set[int|str], or no annotation')
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
    except SyntaxErrorAIL as exc:
        # every block-syntax refusal reports file:line:col; the ones raised without a position
        # get that of the statement being read
        if exc.lineno is None and current_start is not None:
            exc.lineno, exc.offset = current_start[0], current_start[1] + 1
        raise
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
        raise SyntaxErrorAIL('the entry file needs exactly one `fn main()`, and this one has %d.\n'
                             '  write instead: `fn main() -> int { ...; return 0; }` (once, at the top level)' % main_count,
                             lineno=1, offset=1)
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


def _module_scope_bindings(tree):
    """How many times each name is bound at module scope, in any statement outside function and class
    bodies (a store in an `if`/`for`/`while`/`with`/`try` counts), and twice for a name that a function
    declares `global` (it can change whenever that function runs)."""
    count = {}

    def bind(name, times=1):
        count[name] = count.get(name, 0) + times

    def walk(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bind(node.name)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Global):
                    for name in sub.names:
                        bind(name, 2)
            return
        if isinstance(node, ast.Lambda):
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for sub in ast.walk(node):          # only a walrus target leaks out of a comprehension
                if isinstance(sub, ast.NamedExpr) and isinstance(sub.target, ast.Name):
                    bind(sub.target.id)
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bind(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bind((alias.asname or alias.name).split('.')[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bind(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bind(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bind(node.rest)
        for child in ast.iter_child_nodes(node):
            walk(child)
    for node in tree.body:
        walk(node)
    return count


def fold_constants(text):
    """Top-level `NAME = <constant arithmetic>` bound once in module scope, rewritten to its literal
    value. A name that a nested block, a loop or a `global` function rebinds is not folded: its value
    at the line that reads it is not the first one."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    stored = _module_scope_bindings(tree)
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
# One-argument libm functions: name -> True when a finite argument can overflow (OverflowError, as
# CPython's math_1 raises "math range error"); otherwise an infinite result of a finite argument is
# a ValueError ("math domain error"), and a NaN result of a non-NaN argument always is.
_MATH_ONE = {'sin': False, 'cos': False, 'tan': False, 'asin': False, 'acos': False, 'atan': False,
             'sinh': True, 'cosh': True, 'tanh': False, 'asinh': False, 'acosh': False, 'atanh': False,
             'exp': True, 'exp2': True, 'expm1': True, 'log': False, 'log1p': False, 'log2': False,
             'log10': False, 'cbrt': False}
_MATH_PLAIN_TWO = ('atan2', 'copysign', 'hypot')
_MATH_PREDICATES = ('isnan', 'isinf', 'isfinite')
_MATH_INT_TWO = ('comb', 'perm', 'lcm')
_MATH_LIST_ONE = ('fsum', 'prod')
_MATH_CALLS = ('sqrt', 'floor', 'ceil', 'isqrt', 'gcd', 'fabs', 'trunc', 'degrees', 'radians', 'factorial',
               'pow', 'fmod', *_MATH_INT_TWO, *_MATH_LIST_ONE, *_MATH_ONE, *_MATH_PLAIN_TWO, *_MATH_PREDICATES)
_MATH_BUILT = ('math.sqrt, floor, ceil, trunc, isqrt, gcd and lcm (two arguments), comb, perm (two arguments), '
               'fabs, factorial, pow, fmod, hypot, '
               'copysign, atan2, degrees, radians, isnan, isinf, isfinite, sin, cos, tan, asin, acos, atan, '
               'sinh, cosh, tanh, asinh, acosh, atanh, exp, exp2, expm1, log (one or two arguments), log1p, '
               'log2, log10, cbrt and the constants math.pi, math.e, math.tau, math.inf, math.nan; '
               'fsum (a list of floats), prod (a list of ints), modf; dist, erf, gamma and the rest are not built')
# Exact CPython results: sqrt keeps -0.0 and raises ValueError below zero, isqrt and gcd are
# integer-only (no float rounding reaches the answer).
_MATH_HELPERS = {
    'star_max': '''def _ail_star_max(lead, rest):
    xs = lead + list(rest)
    if len(xs) == 1:
        return max(xs[0])
    return max(xs)''',
    'star_min': '''def _ail_star_min(lead, rest):
    xs = lead + list(rest)
    if len(xs) == 1:
        return min(xs[0])
    return min(xs)''',
    'dmerge': '''def _ail_dmerge(parts):
    out = {}
    for d in parts:
        for k in d:
            out[k] = d[k]
    return out''',
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


def _math_one_helper(name, overflow):
    return (f'def _ail_math_{name}(x: float) -> float:\n'
            f'    r = _ail_c_{name}(x)\n'
            '    if r != r:\n'
            '        if x == x:\n'
            '            raise ValueError("math domain error")\n'
            '        return r\n'
            '    if r - r != 0.0 and x - x == 0.0:\n'
            + ('        raise OverflowError("math range error")\n' if overflow
               else '        raise ValueError("math domain error")\n')
            + '    return r\n')


for _name, _overflow in _MATH_ONE.items():
    _MATH_HELPERS[_name] = _math_one_helper(_name, _overflow)
for _name in _MATH_PLAIN_TWO:
    _MATH_HELPERS[_name] = (f'def _ail_math_{_name}(x: float, y: float) -> float:\n'
                            f'    return _ail_c_{_name}(x, y)\n')
_MATH_HELPERS['fabs'] = 'def _ail_math_fabs(x: float) -> float:\n    return _ail_c_fabs(x)\n'
_MATH_HELPERS['isnan'] = 'def _ail_math_isnan(x: float) -> bool:\n    return x != x\n'
_MATH_HELPERS['isinf'] = 'def _ail_math_isinf(x: float) -> bool:\n    return x - x != 0.0 and x == x\n'
_MATH_HELPERS['isfinite'] = 'def _ail_math_isfinite(x: float) -> bool:\n    return x - x == 0.0\n'
_MATH_HELPERS['degrees'] = f'def _ail_math_degrees(x: float) -> float:\n    return x * {180.0 / math.pi!r}\n'
_MATH_HELPERS['radians'] = f'def _ail_math_radians(x: float) -> float:\n    return x * {math.pi / 180.0!r}\n'
_MATH_HELPERS['log2args'] = (
    'def _ail_math_log2args(x: float, base: float) -> float:\n'
    '    num = _ail_math_log(x)\n'
    '    den = _ail_math_log(base)\n'
    '    if den == 0.0:\n'
    '        raise ZeroDivisionError("float division by zero")\n'
    '    return num / den\n')
_MATH_HELPERS['fmod'] = (
    'def _ail_math_fmod(x: float, y: float) -> float:\n'
    '    if y - y != 0.0 and y == y and x - x == 0.0:\n'
    '        return x\n'
    '    r = _ail_c_fmod(x, y)\n'
    '    if r != r and x == x and y == y:\n'
    '        raise ValueError("math domain error")\n'
    '    return r\n')
# CPython's math.pow keeps its own special-case table for non-finite operands (C99 Annex F) and
# turns the finite cases' errno into ValueError / OverflowError.
_MATH_HELPERS['pow'] = (
    'def _ail_math_pow(x: float, y: float) -> float:\n'
    '    if x - x != 0.0 or y - y != 0.0:\n'
    '        if x != x:\n'
    '            if y == 0.0:\n'
    '                return 1.0\n'
    '            return x\n'
    '        if y != y:\n'
    '            if x == 1.0:\n'
    '                return 1.0\n'
    '            return y\n'
    '        if x - x != 0.0:\n'
    '            odd = 0\n'
    '            if y - y == 0.0:\n'
    '                if _ail_c_fmod(_ail_c_fabs(y), 2.0) == 1.0:\n'
    '                    odd = 1\n'
    '            if y > 0.0:\n'
    '                if odd == 1:\n'
    '                    return x\n'
    '                return _ail_c_fabs(x)\n'
    '            if y == 0.0:\n'
    '                return 1.0\n'
    '            if odd == 1:\n'
    '                return _ail_c_copysign(0.0, x)\n'
    '            return 0.0\n'
    '        if _ail_c_fabs(x) == 1.0:\n'
    '            return 1.0\n'
    '        if y > 0.0 and _ail_c_fabs(x) > 1.0:\n'
    '            return y\n'
    '        if y < 0.0 and _ail_c_fabs(x) < 1.0:\n'
    '            return -y\n'
    '        return 0.0\n'
    '    r = _ail_c_pow(x, y)\n'
    '    if r != r:\n'
    '        raise ValueError("math domain error")\n'
    '    if r - r != 0.0:\n'
    '        if x == 0.0:\n'
    '            raise ValueError("math domain error")\n'
    '        raise OverflowError("math range error")\n'
    '    return r\n')
_MATH_HELPERS['factorial'] = (
    'def _ail_math_factorial(n: int) -> int:\n'
    '    if n < 0:\n'
    '        raise ValueError("factorial() not defined for negative values")\n'
    '    r = 1\n'
    '    i = 2\n'
    '    while i <= n:\n'
    '        r = r * i\n'
    '        i += 1\n'
    '    return r\n')
# comb / perm / lcm of two ints, CPython's results and error messages; the running product is divided by the
# gcd first so an intermediate only overflows int64 when the answer is near it
_MATH_HELPERS['comb'] = (
    'def _ail_math_comb(n: int, k: int) -> int:\n'
    '    if n < 0:\n'
    '        raise ValueError("n must be a non-negative integer")\n'
    '    if k < 0:\n'
    '        raise ValueError("k must be a non-negative integer")\n'
    '    if k > n:\n'
    '        return 0\n'
    '    if k > n - k:\n'
    '        k = n - k\n'
    '    r = 1\n'
    '    i = 1\n'
    '    while i <= k:\n'
    '        top = n - k + i\n'
    '        g = _ail_math_gcd(top, i)\n'
    '        r = r // (i // g) * (top // g)\n'
    '        i += 1\n'
    '    return r\n')
_MATH_HELPERS['perm'] = (
    'def _ail_math_perm(n: int, k: int) -> int:\n'
    '    if n < 0:\n'
    '        raise ValueError("n must be a non-negative integer")\n'
    '    if k < 0:\n'
    '        raise ValueError("k must be a non-negative integer")\n'
    '    if k > n:\n'
    '        return 0\n'
    '    r = 1\n'
    '    i = 0\n'
    '    while i < k:\n'
    '        r = r * (n - i)\n'
    '        i += 1\n'
    '    return r\n')
_MATH_HELPERS['lcm'] = (
    'def _ail_math_lcm(a: int, b: int) -> int:\n'
    '    if a == 0 or b == 0:\n'
    '        return 0\n'
    '    return abs(a // _ail_math_gcd(a, b) * b)\n')

# math.fsum (CPython's Shewchuk partials and its final rounding step; a non-finite input is summed plainly),
# math.prod of ints, and textwrap.wrap / fill / dedent for the default options. Text with a hyphen or a tab is a
# loud RuntimeError: CPython may break a line after a hyphen and expands tabs, neither of which is built.
_MATH_HELPERS['fsum'] = (
    'def _ail_math_fsum(xs: list[float]) -> float:\n'
    '    plain = 0.0\n'
    '    finite = True\n'
    '    for v in xs:\n'
    '        plain += v\n'
    '        if v - v != 0.0:\n'
    '            finite = False\n'
    '    if not finite:\n'
    '        return plain\n'
    '    partials = [0.0] * (len(xs) + 1)\n'
    '    m = 0\n'
    '    for v in xs:\n'
    '        x = v\n'
    '        i = 0\n'
    '        j = 0\n'
    '        while j < m:\n'
    '            y = partials[j]\n'
    '            if abs(x) < abs(y):\n'
    '                t = x\n'
    '                x = y\n'
    '                y = t\n'
    '            hi = x + y\n'
    '            lo = y - (hi - x)\n'
    '            if lo != 0.0:\n'
    '                partials[i] = lo\n'
    '                i += 1\n'
    '            x = hi\n'
    '            j += 1\n'
    '        if x != 0.0:\n'
    '            partials[i] = x\n'
    '            i += 1\n'
    '        m = i\n'
    '    n = m\n'
    '    hi = 0.0\n'
    '    if n > 0:\n'
    '        n -= 1\n'
    '        hi = partials[n]\n'
    '        lo = 0.0\n'
    '        while n > 0:\n'
    '            x = hi\n'
    '            n -= 1\n'
    '            y = partials[n]\n'
    '            hi = x + y\n'
    '            yr = hi - x\n'
    '            lo = y - yr\n'
    '            if lo != 0.0:\n'
    '                break\n'
    '        if n > 0 and ((lo < 0.0 and partials[n - 1] < 0.0) or (lo > 0.0 and partials[n - 1] > 0.0)):\n'
    '            y = lo * 2.0\n'
    '            x = hi + y\n'
    '            yr = x - hi\n'
    '            if y == yr:\n'
    '                hi = x\n'
    '    return hi\n')
_MATH_HELPERS['prod'] = (
    'def _ail_math_prod(xs: list[int]) -> int:\n'
    '    r = 1\n'
    '    for v in xs:\n'
    '        r = r * v\n'
    '    return r\n')
_MATH_HELPERS['tw_wrap'] = (
    'def _ail_tw_wrap(text: str, width: int) -> list[str]:\n'
    '    if width <= 0:\n'
    '        raise ValueError("invalid width " + str(width) + " (must be > 0)")\n'
    '    if "-" in text or "\\t" in text:\n'
    '        raise RuntimeError("textwrap: text with a hyphen or a tab is not built")\n'
    '    chunks: list[str] = []\n'
    '    cur = ""\n'
    '    cur_space = False\n'
    '    for ch in text:\n'
    '        sp = ch == " " or ch == "\\n" or ch == "\\r" or ch == "\\x0b" or ch == "\\x0c"\n'
    '        if cur != "" and sp != cur_space:\n'
    '            chunks.append(cur)\n'
    '            cur = ""\n'
    '        cur_space = sp\n'
    '        if sp:\n'
    '            cur += " "\n'
    '        else:\n'
    '            cur += ch\n'
    '    if cur != "":\n'
    '        chunks.append(cur)\n'
    '    lines: list[str] = []\n'
    '    line_chunks: list[str] = []\n'
    '    pos = 0\n'
    '    n = len(chunks)\n'
    '    while pos < n:\n'
    '        while len(line_chunks) > 0:\n'
    '            line_chunks.pop()\n'
    '        if len(lines) > 0 and chunks[pos].strip() == "":\n'
    '            pos += 1\n'
    '        cur_len = 0\n'
    '        while pos < n:\n'
    '            size = len(chunks[pos])\n'
    '            if cur_len + size <= width:\n'
    '                line_chunks.append(chunks[pos])\n'
    '                cur_len += size\n'
    '                pos += 1\n'
    '            else:\n'
    '                break\n'
    '        if pos < n and len(chunks[pos]) > width:\n'
    '            space_left = width - cur_len\n'
    '            line_chunks.append(chunks[pos][:space_left])\n'
    '            chunks[pos] = chunks[pos][space_left:]\n'
    '        if len(line_chunks) > 0 and line_chunks[len(line_chunks) - 1].strip() == "":\n'
    '            line_chunks.pop()\n'
    '        if len(line_chunks) > 0:\n'
    '            lines.append("".join(line_chunks))\n'
    '    return lines\n')
_MATH_HELPERS['tw_fill'] = (
    'def _ail_tw_fill(text: str, width: int) -> str:\n'
    '    parts = _ail_tw_wrap(text, width)\n'
    '    return "\\n".join(parts)\n')
_MATH_HELPERS['tw_dedent'] = (
    'def _ail_tw_dedent(text: str) -> str:\n'
    '    lines = text.split("\\n")\n'
    '    margin = ""\n'
    '    first = True\n'
    '    for line in lines:\n'
    '        if line.strip(" \\t") == "":\n'
    '            continue\n'
    '        k = 0\n'
    '        while k < len(line) and (line[k] == " " or line[k] == "\\t"):\n'
    '            k += 1\n'
    '        indent = line[:k]\n'
    '        if first:\n'
    '            margin = indent\n'
    '            first = False\n'
    '        elif line.startswith(margin):\n'
    '            pass\n'
    '        elif margin.startswith(indent):\n'
    '            margin = indent\n'
    '        else:\n'
    '            j = 0\n'
    '            while j < len(margin) and j < len(indent) and margin[j] == indent[j]:\n'
    '                j += 1\n'
    '            margin = margin[:j]\n'
    '    out: list[str] = []\n'
    '    for line in lines:\n'
    '        if line.strip(" \\t") == "":\n'
    '            out.append("")\n'
    '        else:\n'
    '            out.append(line[len(margin):])\n'
    '    return "\\n".join(out)\n')
_MATH_DEPS = {'log2args': ('log',), 'comb': ('gcd',), 'lcm': ('gcd',), 'tw_fill': ('tw_wrap',)}
import string as _string_module

_STRING_CONSTANTS = {name: getattr(_string_module, name) for name in (
    'ascii_lowercase', 'ascii_uppercase', 'ascii_letters', 'digits', 'hexdigits', 'octdigits', 'punctuation',
    'whitespace', 'printable')}
_TIME_CLOCKS = {'perf_counter': '_ail_perf_counter', 'monotonic': '_ail_perf_counter',
                'perf_counter_ns': '_ail_perf_counter_ns', 'monotonic_ns': '_ail_perf_counter_ns',
                'time': '_ail_time', 'time_ns': '_ail_time_ns'}
# time.sleep / localtime / gmtime / strftime / mktime are lowered by dtlib.py (stdlib4.rewrite_text) before this pass
_TIME_LOWERED = ('sleep', 'localtime', 'gmtime', 'strftime', 'mktime')
_OPERATOR_BINARY = {'add': ast.Add, 'sub': ast.Sub, 'mul': ast.Mult, 'truediv': ast.Div,
                    'floordiv': ast.FloorDiv, 'mod': ast.Mod, 'pow': ast.Pow, 'and_': ast.BitAnd,
                    'or_': ast.BitOr, 'xor': ast.BitXor, 'lshift': ast.LShift, 'rshift': ast.RShift}
_OPERATOR_COMPARE = {'lt': ast.Lt, 'le': ast.LtE, 'gt': ast.Gt, 'ge': ast.GtE, 'eq': ast.Eq, 'ne': ast.NotEq}
_OPERATOR_UNARY = {'neg': ast.USub, 'pos': ast.UAdd, 'invert': ast.Invert, 'inv': ast.Invert}
_SMALL_MODULES = {
    'textwrap': ('wrap', 'fill', 'dedent'),
    'time': (*_TIME_CLOCKS, *_TIME_LOWERED),
    'string': tuple(_STRING_CONSTANTS),
    'os': ('cpu_count',),
    'operator': (*_OPERATOR_BINARY, *_OPERATOR_COMPARE, *_OPERATOR_UNARY, 'not_', 'abs', 'getitem', 'itemgetter'),
}
_SMALL_NOTE = {
    'textwrap': 'textwrap.wrap(text[, width]), fill(text[, width]) and dedent(text) are built; the other options '
                'and functions are not, and text with a hyphen or a tab is a RuntimeError',
    'time': 'time.perf_counter() / monotonic() / time() (and the _ns forms), sleep(), localtime(), gmtime(), '
            'strftime() and mktime() are built (the wall clock is an input: AIL_CLOCK=<seconds> pins it); '
            'asctime, ctime, struct_time, tzset and the zone constants are not',
    'string': 'the string module is built as its constants: ascii_lowercase, ascii_uppercase, ascii_letters, '
              'digits, hexdigits, octdigits, punctuation, whitespace, printable',
    'os': 'os.cpu_count() is built; the rest of os (environ, path, ...) is not',
    'operator': 'operator.add/sub/mul/truediv/floordiv/mod/pow/and_/or_/xor/lshift/rshift, the comparisons, '
                'neg/pos/invert/not_/abs/getitem called directly, and itemgetter(k) as a key= are built',
}
_TYPING = {'List': 'list', 'Dict': 'dict', 'Set': 'set', 'Tuple': 'tuple', 'FrozenSet': 'frozenset'}
_DROPPED = ('heapq', 'bisect', 'textwrap', 'typing', 'dataclasses', '__future__', 'time', 'string', 'os', 'operator', 're')
_STDOUT_STATEMENTS = ('sys.stdout.write', 'sys.stdout.buffer.write', 'sys.stdout.flush',
                      'sys.stdout.buffer.flush', 'sys.setrecursionlimit')
_ALIASABLE = ('sys.stdout.write', 'sys.stdout.buffer.write', 'sys.stdin.readline',
              'sys.stdin.buffer.read')
_RESULT_NAMES = ('int', 'float', 'str', 'bytes', 'bool', 'bytearray')
_ATOMIC = (ast.Name, ast.Constant, ast.Call, ast.Attribute, ast.Subscript, ast.List, ast.Dict,
           ast.Set, ast.ListComp, ast.SetComp, ast.DictComp, ast.JoinedStr)
_FILE_HINT = ('this use of a file is not built: only reading it whole (`f.read()`) or line by line '
              '(`for line in f:`) is.\n'
              '  write instead: `with open(path) as f:` with `text = f.read()` or `for line in f:` to '
              'read, `read_bytes(path)` for a binary file, `write_text(path, text)` / '
              '`write_bytes(path, data)` to write one')


def _annotation_only_names(tree, names):
    """Whether every mention of each of `names` (the ABCs of a `from collections.abc import ...`)
    is inside an annotation, where the import has nothing to do."""
    inside = set()
    for node in ast.walk(tree):
        annotations = []
        if isinstance(node, ast.arg):
            annotations.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
        for annotation in annotations:
            if annotation is not None:
                inside.update(id(n) for n in ast.walk(annotation))
    wanted = set(names)
    return not any(isinstance(n, ast.Name) and n.id in wanted and id(n) not in inside for n in ast.walk(tree))


def _own_nodes(function):
    """Nodes of `function` itself, not of the functions, lambdas or classes nested in it."""
    pending = list(ast.iter_child_nodes(function))
    while pending:
        node = pending.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            pending.extend(ast.iter_child_nodes(node))


_RE_MODES = {'match': 0, 'fullmatch': 1, 'search': 2}
# module function -> positional parameters after the pattern
_RE_PARAMS = {'match': ('string', 'flags'), 'fullmatch': ('string', 'flags'), 'search': ('string', 'flags'),
              'findall': ('string', 'flags'), 'finditer': ('string', 'flags'),
              'split': ('string', 'maxsplit', 'flags'), 'sub': ('repl', 'string', 'count', 'flags'),
              'subn': ('repl', 'string', 'count', 'flags')}
_RE_BUILT = ('re.match / fullmatch / search / findall / finditer / split / sub / subn / escape and re.compile(literal) '
             'with a string-literal pattern (a literal, or a name bound once to one), flags I M S X A, '
             'literals . classes \\d \\w \\s anchors ^ $ \\A \\Z \\b \\B * + ? {m,n} lazy variants | groups '
             '(capturing, (?:), (?P<name>)); lookaround, backreferences, atomic / possessive forms and '
             'conditionals are not built')
_RE_MATCH_METHODS = ('group', 'start', 'end', 'groups', 'groupdict', 'span', 'expand')


class _SurfaceExpr(ast.NodeTransformer):
    def __init__(self, surface, boolean=False):
        self.surface = surface
        self.changed = False
        self.boolean = boolean
        self.bool_calls = set()
        self.bool_compares = {}

    def mark_bool(self, node):
        """Calls whose result is only tested (a match used as a condition): no Match object is built."""
        if isinstance(node, ast.Call):
            self.bool_calls.add(node)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            self.mark_bool(node.operand)
        elif isinstance(node, ast.BoolOp):
            for value in node.values:
                self.mark_bool(value)
        elif (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Is, ast.IsNot))
              and isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value is None
              and isinstance(node.left, ast.Call)):
            self.bool_compares[node] = isinstance(node.ops[0], ast.Is)
            self.bool_calls.add(node.left)

    def group_probe(self, node):
        """`m.group(<int or str literal>)` on a plain name: the Call, else None."""
        surface = self.surface
        if (surface.re_on and 'group' not in surface.user_methods and isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == 'group'
                and isinstance(node.func.value, ast.Name) and len(node.args) == 1 and not node.keywords
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, (int, str))
                and not isinstance(node.args[0].value, bool)):
            return node
        return None

    def start_of(self, group):
        return ast.Call(func=ast.Attribute(value=copy.deepcopy(group.func.value), attr='start', ctx=ast.Load()),
                        args=[copy.deepcopy(group.args[0])], keywords=[])

    def visit_BoolOp(self, node):
        """`m.group(k) or default`: the group when it took part, else the default (CPython's None is
        falsy, and an empty group is falsy too, so `or` keeps its meaning on `m.start(k) < m.end(k)`)."""
        if isinstance(node.op, ast.Or) and len(node.values) >= 2 and self.group_probe(node.values[0]):
            first = node.values[0]
            rest = node.values[1] if len(node.values) == 2 else ast.BoolOp(op=ast.Or(), values=node.values[1:])
            nonempty = ast.Compare(left=self.start_of(first), ops=[ast.Lt()],
                                   comparators=[ast.Call(func=ast.Attribute(value=copy.deepcopy(first.func.value),
                                                                            attr='end', ctx=ast.Load()),
                                                         args=[copy.deepcopy(first.args[0])], keywords=[])])
            new = ast.IfExp(test=nonempty, body=first, orelse=rest)
            self.changed = True
            return self.visit(ast.fix_missing_locations(ast.copy_location(new, node)))
        self.generic_visit(node)
        return node

    def visit_Compare(self, node):
        if (len(node.ops) == 1 and isinstance(node.ops[0], (ast.Is, ast.IsNot)) and self.group_probe(node.left)
                and isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value is None):
            new = ast.Compare(left=self.start_of(node.left), ops=[ast.Lt() if isinstance(node.ops[0], ast.Is)
                                                                  else ast.GtE()],
                              comparators=[ast.Constant(value=0)])
            self.changed = True
            return self.visit(ast.fix_missing_locations(ast.copy_location(new, node)))
        if node in self.bool_compares:
            call = self.visit(node.left)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == '_ail_re_test':
                self.changed = True
                return call if not self.bool_compares[node] else ast.copy_location(
                    ast.UnaryOp(op=ast.Not(), operand=call), node)
            node.left = call
            return node
        self.generic_visit(node)
        return node

    def replaced(self, new, old):
        self.changed = True
        return ast.fix_missing_locations(ast.copy_location(new, old))

    def visit_Call(self, node):
        surface = self.surface
        path = surface.path(node.func)
        if surface.re_on and node in self.bool_calls:
            surface.testing.add(node)
        if (surface.re_on and path is None and isinstance(node.func, ast.Attribute)
                and not isinstance(node.func.value, ast.Name)):
            node.func.value = self.visit(node.func.value)      # re.search(...).start(): the inner call too
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

    def visit_Dict(self, node):
        self.generic_visit(node)
        if None not in node.keys:
            return node
        # {**a, 'k': v, **b}: the parts merged in order (a later key replaces an earlier one, keeping its position)
        parts, run = [], ([], [])
        for key, value in zip(node.keys, node.values):
            if key is None:
                if run[0]:
                    parts.append(ast.Dict(keys=run[0], values=run[1]))
                    run = ([], [])
                parts.append(value)
            else:
                run[0].append(key)
                run[1].append(value)
        if run[0]:
            parts.append(ast.Dict(keys=run[0], values=run[1]))
        self.surface.helper('dmerge')
        return self.replaced(ast.Call(func=ast.Name(id='_ail_dmerge', ctx=ast.Load()),
                                      args=[ast.List(elts=parts, ctx=ast.Load())], keywords=[]), node)

    def visit_Attribute(self, node):
        surface = self.surface
        path = surface.path(node)
        if path is not None:
            new = surface.value(node, path)
            return node if new is None else self.replaced(new, node)
        if (isinstance(node.value, ast.Name) and node.value.id in surface.re_patterns and node.attr == 'pattern'
                and not surface.re_lib.programs[surface.re_patterns[node.value.id]].is_bytes):
            return self.replaced(ast.Constant(value=surface.re_lib.programs[surface.re_patterns[node.value.id]].pattern),
                                 node)
        if isinstance(node.value, ast.Name) and node.value.id in surface.files:
            surface.note(node, f'{node.value.id}.{node.attr}: ' + _FILE_HINT)
            return node
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        surface = self.surface
        if not isinstance(node.ctx, ast.Load):
            return node
        if node.id in surface.re_subst:
            match, number = surface.re_subst[node.id]
            self.changed = True
            return ast.copy_location(ast.Call(func=ast.Attribute(value=ast.Name(id=match, ctx=ast.Load()),
                                                                  attr='gs', ctx=ast.Load()),
                                               args=[ast.Constant(value=number)], keywords=[]), node)
        if node.id in surface.re_patterns:
            surface.keep.add('re')
            surface.note(node, f'the compiled pattern {node.id} is used as a value; only {node.id}.match / '
                         'fullmatch / search / findall / finditer / split / sub / subn (...) calls are built')
        elif node.id in surface.files:
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
        self.dc_initless = {}           # dataclass -> its field(init=False) names
        self.dc_default = {}            # dataclass -> {field: default text | None}, init=False fields included
        self.dc_later = {}              # dataclass -> attributes its __post_init__ (or a base's) assigns
        self.dc_all = {}                # dataclass -> every field name, in order
        self.dc_val = False             # the program calls asdict: the helper that converts a value
        self.dc_fields_used = set()     # classes whose fields() is called
        self.post_init = set()         # dataclasses whose generated __init__ calls __post_init__
        self.dc_annotations = {}       # class name -> [(field, annotation text, hidden from repr)]
        self.consumed = set()
        self.void = set()
        self.re_on = False             # `import re` seen
        self.re_patterns = {}          # NAME -> (library index) for NAME = re.compile(literal)
        self.re_nodes = set()          # those assignment statements
        self.def_names = {node.name for node in ast.walk(self.tree)
                          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        # names that stand for a function (a def outside a class, the name bound nowhere else): the replacement
        # of re.sub that is called with each match
        methods = {id(item) for node in ast.walk(self.tree) if isinstance(node, ast.ClassDef) for item in node.body}
        rebound = {node.id for node in ast.walk(self.tree) if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load)}
        rebound |= {node.arg for node in ast.walk(self.tree) if isinstance(node, ast.arg)}
        rebound |= {(alias.asname or alias.name).split('.')[0] for node in ast.walk(self.tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        plain_defs = {node.name for node in ast.walk(self.tree)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and id(node) not in methods}
        self.callable_names = plain_defs - rebound
        self.ambiguous_names = plain_defs & rebound    # a def and a variable of one name: which one is not told
        self.re_consts = {}            # NAME -> str for a name bound once to a string literal
        self.re_lib = None
        self.testing = set()           # re calls whose result is only tested
        self.re_subst = {}             # findall-loop name -> (match variable, group number)
        self.re_subst_now = None
        self.classes = {node.name for node in self.tree.body if isinstance(node, ast.ClassDef)}
        self.user_methods = {item.name for node in ast.walk(self.tree) if isinstance(node, ast.ClassDef)
                             for item in node.body if isinstance(item, ast.FunctionDef)}
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
        if self.dc_val:
            kinds = ''.join(f'    if isinstance(v, {name}):\n        return v._ail_asdict()\n'
                            for name in sorted(self.dataclasses))
            text = text.rstrip('\n') + '\n\n\ndef _ail_dcv(v):\n' + kinds + (
                '    if isinstance(v, list):\n        return [_ail_dcv(x) for x in v]\n'
                '    if isinstance(v, tuple):\n        return tuple([_ail_dcv(x) for x in v])\n'
                '    if isinstance(v, dict):\n        return {_ail_dcv(k): _ail_dcv(x) for k, x in v.items()}\n'
                '    if isinstance(v, set):\n        return {_ail_dcv(x) for x in v}\n'
                '    return v\n')
        if self.dc_fields_used:
            text = text.rstrip('\n') + '\n\n\nclass _AilField:\n    def __init__(self, name: str):\n        self.name = name\n'
            for name in sorted(self.dc_fields_used):
                items = ', '.join(f'_AilField({field!r})' for field in self.dc_all.get(name, []))
                text += f'\n\ndef _ail_dc_fields_{name}():\n    return [{items}]\n'
        if self.re_lib is not None and (self.re_lib.programs or self.re_lib.uses_escape):
            text = text.rstrip('\n') + '\n\n' + python_surface(self.re_lib.text())
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
                    if alias.name in ('heapq', 'bisect', 'math', 'typing', 'dataclasses', 'sys', 're', *_SMALL_MODULES):
                        self.modules[alias.asname or alias.name] = alias.name
                        if alias.name == 're':
                            self.re_on = True
            elif isinstance(node, ast.ImportFrom) and not node.level:
                for alias in node.names:
                    local = alias.asname or alias.name
                    if node.module in ('heapq', 'bisect', 'math', 'dataclasses', *_SMALL_MODULES):
                        self.names[local] = f'{node.module}.{alias.name}'
                    elif node.module == 'typing':
                        self.typing[local] = alias.name
            names = ([node.id] if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load)
                     else [node.arg] if isinstance(node, ast.arg)
                     else [node.name] if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else [])
            for name in names:
                stored[name] = stored.get(name, 0) + 1
        if self.re_on:
            self.collect_re(stored)
        for node in ast.walk(self.tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name) and stored[node.targets[0].id] == 1):
                path = self.path(node.value) if isinstance(node.value, ast.Attribute) else None
                if path in _ALIASABLE:
                    self.aliases[node.targets[0].id] = path
                    self.names[node.targets[0].id] = path
                    self.alias_nodes.add(node)

    # -- expressions --------------------------------------------------------------------------
    def rewritten(self, node, boolean=False):
        rewriter = _SurfaceExpr(self)
        node = copy.deepcopy(node)
        if boolean and self.re_on:
            rewriter.mark_bool(node)
        if self.re_on:
            for each in ast.walk(node):
                if isinstance(each, (ast.If, ast.IfExp, ast.While, ast.Assert)):
                    rewriter.mark_bool(each.test)
                elif isinstance(each, ast.comprehension):
                    for test in each.ifs:
                        rewriter.mark_bool(test)
        new = rewriter.visit(node)
        return new, rewriter.changed

    def expression(self, node, boolean=False):
        if node is None:
            return
        new, changed = self.rewritten(node, boolean)
        if changed:
            text = ast.unparse(new)
            self.replace(node, text if isinstance(new, _ATOMIC) else '(' + text + ')')

    def function_value(self, module, name):
        """`operator.mul` / `math.gcd` used as a value (reduce, accumulate, a sort key...): the lambda of the
        same arithmetic, which the iterator lowering and sorted(key=) inline. None when it is not one of those."""
        def lam(params, body):
            return ast.Lambda(args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=p) for p in params],
                                                 vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None,
                                                 defaults=[]), body=body)
        a, b = ast.Name(id='_ail_a', ctx=ast.Load()), ast.Name(id='_ail_b', ctx=ast.Load())
        if module == 'operator':
            if name in _OPERATOR_BINARY:
                return lam(['_ail_a', '_ail_b'], ast.BinOp(left=a, op=_OPERATOR_BINARY[name](), right=b))
            if name in _OPERATOR_COMPARE:
                return lam(['_ail_a', '_ail_b'], ast.Compare(left=a, ops=[_OPERATOR_COMPARE[name]()], comparators=[b]))
            if name in _OPERATOR_UNARY:
                return lam(['_ail_a'], ast.UnaryOp(op=_OPERATOR_UNARY[name](), operand=a))
            if name == 'abs':
                return lam(['_ail_a'], ast.Call(func=ast.Name(id='abs', ctx=ast.Load()), args=[a], keywords=[]))
            return None
        if name in _MATH_CALLS:
            two = name in ('gcd', 'pow', 'fmod', *_MATH_PLAIN_TWO)
            call = ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[a, b] if two else [a], keywords=[])
            call.lineno = call.end_lineno = 1
            call.col_offset = call.end_col_offset = 0
            mapped = self.math_call(call, name)
            if mapped is not None:
                return lam(['_ail_a', '_ail_b'] if two else ['_ail_a'], mapped)
        return None

    def value(self, node, path):
        module, _, name = path.partition('.')
        if module == 'math' and name in _MATH_VALUES:
            return ast.parse(_MATH_VALUES[name], mode='eval').body
        if module in ('operator', 'math') and name:
            lowered = self.function_value(module, name)
            if lowered is not None:
                return lowered
        if module in ('heapq', 'bisect') and name in (_HEAPQ if module == 'heapq' else _BISECT):
            return ast.Name(id=name, ctx=ast.Load()) if isinstance(node, ast.Attribute) else None
        if module in ('heapq', 'bisect', 'math'):
            if module != 'math':
                self.keep.add(module)
            self.note(node, f'{path} used as a value is not built; the built ones are '
                      + (_MATH_BUILT if module == 'math' else ', '.join(
                          f'{module}.{each}' for each in (_HEAPQ if module == 'heapq' else _BISECT)))
                      + ', called directly')
        elif module in _SMALL_MODULES and name:
            if module == 'string' and name in _STRING_CONSTANTS:
                return ast.Constant(value=_STRING_CONSTANTS[name])
            self.keep.add(module)
            self.note(node, f'{path} used as a value is not built; ' + _SMALL_NOTE[module])
        elif path == 'sys.maxsize':
            return ast.Constant(value=2 ** 63 - 1)       # the 64-bit sys.maxsize; ints here are int64
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

    # -- re -----------------------------------------------------------------------------------
    @staticmethod
    def re_bind(node):
        """(name, value) of `NAME = value` or `NAME: annotation = value` (a single plain name), else None."""
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id, node.value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            return node.target.id, node.value
        return None

    def collect_re(self, stored):
        self.re_lib = _relib().Library()
        for node in ast.walk(self.tree):
            bound = self.re_bind(node)
            if bound is not None and stored[bound[0]] == 1:
                text = self.re_str(bound[1])
                if text is not None:
                    self.re_consts[bound[0]] = text
        for node in ast.walk(self.tree):
            bound = self.re_bind(node)
            if (bound is not None and stored[bound[0]] == 1 and isinstance(bound[1], ast.Call)
                    and self.path(bound[1].func) == 're.compile'):
                call = bound[1]
                index = self.re_pattern(call, 'compile', call.args, call.keywords, ('flags',))
                if index is not None:
                    self.re_patterns[bound[0]] = index
                    self.re_nodes.add(node)

    def re_str(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            return node.value
        if isinstance(node, ast.Name) and node.id in self.re_consts:
            return self.re_consts[node.id]
        if isinstance(node, ast.JoinedStr):
            # an f-string whose every field is a plain {name} of a constant str (no conversion, no format spec)
            parts = []
            for item in node.values:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    parts.append(item.value)
                elif (isinstance(item, ast.FormattedValue) and item.conversion == -1 and item.format_spec is None):
                    text = self.re_str(item.value)
                    if not isinstance(text, str):
                        return None
                    parts.append(text)
                else:
                    return None
            return ''.join(parts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self.re_str(node.left), self.re_str(node.right)
            if left is not None and right is not None and type(left) is type(right):
                return left + right
        return None

    def re_flags(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left, right = self.re_flags(node.left), self.re_flags(node.right)
            return None if left is None or right is None else left | right
        path = self.path(node) if isinstance(node, ast.Attribute) else None
        if path and path.startswith('re.') and path[3:] in _relib().FLAG_NAMES:
            return _relib().FLAG_NAMES[path[3:]]
        return None

    def re_args(self, node, params, args, keywords):
        """{parameter: expression} of a call, or None (noted) when it has a shape not built."""
        if any(isinstance(arg, ast.Starred) for arg in args) or any(item.arg is None for item in keywords):
            return None
        given = dict(zip(params, args))
        if len(args) > len(params):
            return None
        for item in keywords:
            if item.arg not in params or item.arg in given:
                return None
            given[item.arg] = item.value
        return given

    def re_refuse(self, node, name, why):
        self.keep.add('re')
        self.note(node, f're.{name}(): {why}; built here: {_RE_BUILT}')

    def re_pattern(self, node, name, args, keywords, params):
        """Library index of the pattern literal of a re call (args[0] is the pattern), or None (noted)."""
        if not args:
            self.re_refuse(node, name, 'the pattern is missing')
            return None
        text = self.re_str(args[0])
        if text is None:
            self.re_refuse(node, name, 'the pattern has to be a string literal (or a name bound once to one), '
                           'not an expression: it is compiled when the program is built')
            return None
        given = self.re_args(node, params, args[1:], keywords)
        if given is None:
            self.re_refuse(node, name, 'these arguments are not built')
            return None
        flags = 0
        if 'flags' in given:
            flags = self.re_flags(given['flags'])
            if flags is None:
                self.re_refuse(node, name, 'flags has to be re.I / re.M / re.S / re.X / re.A combined with |')
                return None
        try:
            return self.re_lib.pattern(text, flags, isinstance(text, bytes))
        except _relib().ReRefused as exc:
            self.re_refuse(node, name, f'the pattern {text!r} is not built: {exc}')
            return None

    def re_emit(self, node, name, index, given):
        """The call that stands for re.<name> on library pattern `index` with the non-pattern arguments `given`."""
        lib = self.re_lib
        program = lib.programs[index]
        table = ast.Name(id=lib.table_name(index), ctx=ast.Load())

        def call(function, *args):
            return ast.Call(func=ast.Name(id=function, ctx=ast.Load()), args=list(args), keywords=[])

        if 'string' not in given:
            self.re_refuse(node, name, 'the string argument is missing')
            return None
        subject = given['string']
        sfx = 'B' if program.is_bytes else ''
        if name in _RE_MODES:
            if node in self.testing:
                return call('_ail_re_test' + sfx, table, subject, ast.Constant(value=_RE_MODES[name]))
            return call('_ail_re_do' + sfx, table, subject, ast.Constant(value=_RE_MODES[name]))
        if name == 'findall':
            if program.ngroups > 1:
                self.re_refuse(node, name, 'a pattern with several groups returns tuples, which are not built '
                               '(use finditer and m.group(i))')
                return None
            return call('_ail_re_findall' + sfx, table, subject)
        if name == 'finditer':
            return call('_ail_re_finditer' + sfx, table, subject)
        if name == 'split':
            if program.ngroups:
                self.re_refuse(node, name, 'split with groups returns None for a group that did not match, which '
                               'is not built; use a pattern without groups')
                return None
            return call('_ail_re_split' + sfx, table, subject, given.get('maxsplit', ast.Constant(value=0)))
        if name in ('sub', 'subn'):
            count = given.get('count', ast.Constant(value=0))
            repl = given['repl']
            text = self.re_str(repl)
            counted = name == 'subn'
            if text is not None and isinstance(text, bytes) != program.is_bytes:
                self.re_refuse(node, name, 'a bytes pattern needs a bytes replacement and a str pattern a str one')
                return None
            if text is not None and (b'\\' if program.is_bytes else '\\') in text:
                if counted:
                    self.re_refuse(node, name, 'subn with a replacement template that has a backslash is not built')
                    return None
                try:
                    function = lib.sub_function(index, text)
                except _relib().ReRefused as exc:
                    self.re_refuse(node, name, f'the replacement {text!r} is not built: {exc}')
                    return None
                return call(function, subject, count)
            if text is None and not (isinstance(repl, (ast.Name, ast.Attribute, ast.Subscript, ast.JoinedStr,
                                                       ast.BinOp, ast.Call, ast.Lambda))):
                self.re_refuse(node, name, 'a function (or lambda) as the replacement is not built')
                return None
            if isinstance(repl, ast.Name) and repl.id in self.ambiguous_names:
                self.re_refuse(node, name, f'the replacement {repl.id!r} is both a function and a variable in this program')
                return None
            if isinstance(repl, ast.Lambda) or (isinstance(repl, ast.Name) and repl.id in self.callable_names):
                # a callable replacement: called with each Match, its result is the replacement text
                return call(lib.sub_callable(index, counted), subject, repl, count)
            if counted:
                return call(lib.sub_callable(index, True, True), subject, repl, count)
            return call('_ail_re_sublit' + sfx, table, subject, repl, count)
        return None

    def re_call(self, node, name):
        """re.<name>(pattern, ...) on the module."""
        self.keep.add('re') if name not in _RE_PARAMS and name not in ('escape', 'compile') else None
        if name == 'escape':
            if len(node.args) == 1 and not node.keywords and not isinstance(node.args[0], ast.Starred):
                self.re_lib.uses_escape = True
                return ast.Call(func=ast.Name(id='_ail_re_escape', ctx=ast.Load()), args=node.args, keywords=[])
            self.re_refuse(node, name, 're.escape takes one string')
            return None
        if name == 'compile':
            self.re_refuse(node, name, 're.compile is built only as `NAME = re.compile(literal[, flags])` bound '
                           'once; use NAME.match(...) and so on')
            return None
        if name not in _RE_PARAMS:
            self.re_refuse(node, name, f're.{name} is not built')
            return None
        if not node.args and not any(item.arg == 'pattern' for item in node.keywords):
            self.re_refuse(node, name, 'the pattern is missing')
            return None
        # the pattern is the first positional argument
        params = ('pattern',) + _RE_PARAMS[name]
        given = self.re_args(node, params, node.args, node.keywords)
        if given is None or 'pattern' not in given:
            self.re_refuse(node, name, 'these arguments are not built')
            return None
        pattern_node = given.pop('pattern')
        if isinstance(pattern_node, ast.Name) and pattern_node.id in self.re_patterns and 'flags' not in given:
            # re.match(COMPILED, s) is COMPILED.match(s)
            return self.re_emit(node, name, self.re_patterns[pattern_node.id], given)
        shell = [pattern_node] + ([given['flags']] if 'flags' in given else [])
        index = self.re_pattern(node, name, shell[:1], [ast.keyword(arg='flags', value=given['flags'])]
                                if 'flags' in given else [], ('flags',))
        if index is None:
            return None
        given.pop('flags', None)
        return self.re_emit(node, name, index, given)

    def re_method(self, node, receiver, name):
        """NAME.<name>(...) on a compiled pattern."""
        if name not in _RE_PARAMS:
            self.re_refuse(node, name, f'the compiled pattern method {name} is not built')
            return None
        params = _RE_PARAMS[name]
        params = tuple(p for p in params if p != 'flags')
        given = self.re_args(node, params, node.args, node.keywords)
        if given is None:
            self.re_refuse(node, name, 'these arguments are not built (pos / endpos are not)')
            return None
        return self.re_emit(node, name, self.re_patterns[receiver], given)

    def match_method(self, node):
        """m.group() / m.group("name") / m.start() ... spelled with what the Match class has."""
        func = node.func
        name = func.attr
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            return None
        if name in ('group', 'start', 'end'):
            if not node.args:
                return ast.Call(func=func, args=[ast.Constant(value=0)], keywords=[])
            if (len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                return ast.Call(func=ast.Attribute(value=func.value, attr=name + 'n', ctx=ast.Load()),
                                args=node.args, keywords=[])
            if name == 'group' and len(node.args) > 1:
                self.keep.add('re')
                self.note(node, 'm.group(a, b) returns a tuple, which is not built; call m.group(i) once per group')
        elif name in ('groups', 'groupdict', 'span', 'expand', 'lastindex') and not node.args:
            self.keep.add('re')
            self.note(node, f'm.{name}() is not built (tuples and None groups); built are m.group(i) / '
                      'm.group("name"), m.start(i), m.end(i), and `a, b = m.span()` / `a, b = m.groups()`')
        return None

    def dc_wanted(self):
        """The dataclasses functions the program calls (asdict, replace, fields), found once before any class is lowered."""
        if getattr(self, '_dc_wanted', None) is None:
            self._dc_wanted = {path.split('.')[1] for node in ast.walk(self.tree)
                               if isinstance(node, ast.Call) and (path := self.path(node.func)) is not None
                               and path in ('dataclasses.asdict', 'dataclasses.replace', 'dataclasses.fields')}
        return self._dc_wanted

    def dc_call(self, node, name):
        """asdict(x) / replace(x, f=v) / fields(Cls) on a dataclass lowered by dataclass(): calls of the methods and
        helper written there (`_ail_asdict`, `_ail_replace`, `_ail_dc_fields_Cls`)."""
        args = node.args
        if any(isinstance(arg, ast.Starred) for arg in args) or any(item.arg is None for item in node.keywords):
            return None
        if name == 'asdict' and len(args) == 1 and not node.keywords:
            return ast.Call(func=ast.Attribute(value=args[0], attr='_ail_asdict', ctx=ast.Load()), args=[], keywords=[])
        if name == 'replace' and len(args) == 1:
            changes = ast.Dict(keys=[ast.Constant(value=item.arg) for item in node.keywords],
                               values=[item.value for item in node.keywords])
            return ast.Call(func=ast.Attribute(value=args[0], attr='_ail_replace', ctx=ast.Load()), args=[changes],
                            keywords=[])
        if name == 'fields' and len(args) == 1 and not node.keywords and isinstance(args[0], ast.Name) \
                and args[0].id in self.dc_classes() and not any(
                    isinstance(each, ast.Attribute) and each.attr in ('type', 'default', 'default_factory', 'init', 'repr',
                                                                      'compare', 'metadata', 'kw_only', 'hash')
                    for each in ast.walk(self.tree)):
            # (the Field objects carry the name only; a program that reads .type / .default ... is refused below)
            self.dc_fields_used.add(args[0].id)
            return ast.Call(func=ast.Name(id='_ail_dc_fields_' + args[0].id, ctx=ast.Load()), args=[], keywords=[])
        self.note(node, f'dataclasses.{name}(...) with these arguments is not built; asdict(x), replace(x, f=v) and '
                  'fields(DataclassName) are')
        return None

    def dc_classes(self):
        return {node.name for node in self.tree.body if isinstance(node, ast.ClassDef)
                and any(self.path(each.func if isinstance(each, ast.Call) else each) == 'dataclasses.dataclass'
                        for each in node.decorator_list)}

    def helper(self, name):
        if name not in self.helpers:
            self.helpers.append(name)

    def call(self, node, path):
        func = node.func
        if (isinstance(func, ast.Name) and func.id in ('max', 'min') and func.id not in self.names
                and func.id not in self.def_names and len(node.args) >= 2 and not node.keywords
                and isinstance(node.args[-1], ast.Starred)
                and not any(isinstance(arg, ast.Starred) for arg in node.args[:-1])):
            # max(a, *rest): the maximum of a and the items of rest (max(a) alone, when rest is empty, as CPython)
            self.helper('star_' + func.id)
            return ast.Call(func=ast.Name(id='_ail_star_' + func.id, ctx=ast.Load()),
                            args=[ast.List(elts=node.args[:-1], ctx=ast.Load()), node.args[-1].value], keywords=[])
        if path in ('dataclasses.asdict', 'dataclasses.replace', 'dataclasses.fields'):
            return self.dc_call(node, path.split('.')[1])
        if self.re_on:
            if path is not None and path.startswith('re.') and path.count('.') == 1:
                return self.re_call(node, path[3:])
            if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                    and func.value.id in self.re_patterns):
                return self.re_method(node, func.value.id, func.attr)
            if (path is None and isinstance(func, ast.Attribute) and func.attr in _RE_MATCH_METHODS
                    and func.attr not in self.user_methods):
                return self.match_method(node)
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
            if module in _SMALL_MODULES and name:
                return self.small_call(node, module, name)
            if path == 'sys.stdin.buffer.read' and not node.keywords and len(node.args) <= 1:
                return ast.Call(func=ast.Name(id='read_stdin_bytes', ctx=ast.Load()),
                                args=node.args or [ast.parse('1 << 40', mode='eval').body], keywords=[])
            if path == 'sys.stderr.write' and len(node.args) == 1 and not node.keywords \
                    and not isinstance(node.args[0], ast.Starred):
                # a str only: `"" + x` is refused for an int, as CPython refuses to write one
                text = node.args[0]
                if not (isinstance(text, ast.JoinedStr) or isinstance(text, ast.Constant) and isinstance(text.value, str)):
                    text = ast.BinOp(left=ast.Constant(value=''), op=ast.Add(), right=text)
                return ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=[text], keywords=[
                    ast.keyword(arg='end', value=ast.Constant(value='')),
                    ast.keyword(arg='file', value=ast.parse('sys.stderr', mode='eval').body)])
            if path == 'sys.stderr.flush' and not node.args and not node.keywords:
                return ast.Constant(value=None)       # stderr is written as it is printed
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

    def re_findall_loop(self, node, function):
        """`for a, b in re.findall(P, s):` (several groups): a loop over the matches, each name read as
        that match's group (findall's tuple gives '' for a group that did not take part)."""
        call = node.iter
        if not (function is not None and isinstance(node.target, ast.Tuple) and isinstance(call, ast.Call)
                and all(isinstance(each, ast.Name) for each in node.target.elts)):
            return False
        path = self.path(call.func)
        if path == 're.findall':
            given = self.re_args(call, ('pattern', 'string', 'flags'), call.args, call.keywords)
            if given is None or 'pattern' not in given or 'string' not in given:
                return False
            flag_kw = [ast.keyword(arg='flags', value=given['flags'])] if 'flags' in given else []
            index = self.re_pattern(call, 'findall', [given['pattern']], flag_kw, ('flags',))
            subject = given['string']
        elif (isinstance(call.func, ast.Attribute) and call.func.attr == 'findall'
              and isinstance(call.func.value, ast.Name) and call.func.value.id in self.re_patterns):
            given = self.re_args(call, ('string',), call.args, call.keywords)
            if given is None or 'string' not in given:
                return False
            index = self.re_patterns[call.func.value.id]
            subject = given['string']
        else:
            return False
        if index is None:
            return False
        program = self.re_lib.programs[index]
        names = [each.id for each in node.target.elts]
        if program.ngroups != len(names) or len(names) < 2 or len(set(names)) != len(names):
            return False
        inside = {id(each) for each in ast.walk(node)}
        for each in ast.walk(function):
            if isinstance(each, ast.Name) and each.id in names:
                if id(each) not in inside or (not isinstance(each.ctx, ast.Load) and each not in node.target.elts):
                    self.re_refuse(node, 'findall', 'the loop names %s of a findall loop are used outside it or '
                                   'assigned in it; loop over re.finditer and read m.group(i)' % ', '.join(names))
                    return False
        self.count_re = getattr(self, 'count_re', 0) + 1
        match = '_ail_m%d' % self.count_re
        sfx = 'B' if program.is_bytes else ''
        subject_text = ast.unparse(self.rewritten(subject)[0])
        self.replace(node.target, match)
        self.replace(call, '_ail_re_finditer%s(%s, %s)' % (sfx, self.re_lib.table_name(index), subject_text))
        self.re_subst_now = {name: (match, number) for number, name in enumerate(names, 1)}
        return True

    def re_unpack(self, node):
        """`a, b = m.span()` / `a, b, c = m.groups()` as one assignment per element."""
        value = node.value
        if not (len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple) and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute) and isinstance(value.func.value, ast.Name)
                and value.func.attr in ('span', 'groups') and not value.args and not value.keywords
                and value.func.attr not in self.user_methods and value.func.value.id not in self.re_patterns
                and all(isinstance(each, ast.Name) for each in node.targets[0].elts)):
            return False
        names = [each.id for each in node.targets[0].elts]
        receiver = value.func.value.id
        if value.func.attr == 'span':
            if len(names) != 2:
                return False
            parts = [f'{names[0]} = {receiver}.start(0)', f'{names[1]} = {receiver}.end(0)']
        else:
            parts = [f'{each} = {receiver}.group({index})' for index, each in enumerate(names, 1)]
        self.replace(node, '; '.join(parts), True)
        return True

    def small_call(self, node, module, name):
        """time / string / os / operator, mapped onto what is built (None keeps the call as written)."""
        args = node.args
        plain = not node.keywords and not any(isinstance(arg, ast.Starred) for arg in args)
        if plain and module == 'time' and name in _TIME_CLOCKS and not args:
            return ast.Call(func=ast.Name(id=_TIME_CLOCKS[name], ctx=ast.Load()), args=[], keywords=[])
        if module == 'textwrap' and name in ('wrap', 'fill', 'dedent') and not any(
                isinstance(arg, ast.Starred) for arg in args):
            if name == 'dedent' and len(args) == 1 and not node.keywords:
                self.helpers.append('tw_dedent') if 'tw_dedent' not in self.helpers else None
                return ast.Call(func=ast.Name(id='_ail_tw_dedent', ctx=ast.Load()), args=args, keywords=[])
            width = None
            if name != 'dedent' and 1 <= len(args) + len(node.keywords) <= 2 and len(args) >= 1:
                if len(args) == 2 and not node.keywords:
                    width = args[1]
                elif len(args) == 1 and not node.keywords:
                    width = ast.Constant(value=70)
                elif len(args) == 1 and len(node.keywords) == 1 and node.keywords[0].arg == 'width':
                    width = node.keywords[0].value
            if width is not None:
                for each in (('tw_wrap', 'tw_fill') if name == 'fill' else ('tw_wrap',)):
                    if each not in self.helpers:
                        self.helpers.append(each)
                return ast.Call(func=ast.Name(id='_ail_tw_' + name, ctx=ast.Load()), args=[args[0], width], keywords=[])
        if plain and module == 'os' and name == 'cpu_count' and not args:
            return ast.Call(func=ast.Name(id='_ail_cpu_count', ctx=ast.Load()), args=[], keywords=[])
        if plain and module == 'operator':
            if name in _OPERATOR_BINARY and len(args) == 2:
                return ast.BinOp(left=args[0], op=_OPERATOR_BINARY[name](), right=args[1])
            if name in _OPERATOR_COMPARE and len(args) == 2:
                return ast.Compare(left=args[0], ops=[_OPERATOR_COMPARE[name]()], comparators=[args[1]])
            if name in _OPERATOR_UNARY and len(args) == 1:
                return ast.UnaryOp(op=_OPERATOR_UNARY[name](), operand=args[0])
            if name == 'not_' and len(args) == 1:
                return ast.UnaryOp(op=ast.Not(), operand=args[0])
            if name == 'abs' and len(args) == 1:
                return ast.Call(func=ast.Name(id='abs', ctx=ast.Load()), args=args, keywords=[])
            if name == 'getitem' and len(args) == 2:
                return ast.Subscript(value=args[0], slice=args[1], ctx=ast.Load())
            if name == 'itemgetter' and len(args) == 1:
                return ast.Lambda(
                    args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='_ail_item')], vararg=None,
                                       kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                    body=ast.Subscript(value=ast.Name(id='_ail_item', ctx=ast.Load()), slice=args[0],
                                       ctx=ast.Load()))
        self.keep.add(module)
        self.note(node, f'{module}.{name}() with these arguments is not built; ' + _SMALL_NOTE[module])
        return None

    def math_call(self, node, name):
        args = node.args
        if not node.keywords and not any(isinstance(arg, ast.Starred) for arg in args):
            helper = None
            if name in ('sqrt', 'isqrt') and len(args) == 1 or name == 'gcd' and len(args) == 2:
                helper = name
            elif len(args) == 1 and (name in _MATH_ONE or name in _MATH_PREDICATES
                                     or name in ('degrees', 'radians', 'factorial')):
                helper = name
            elif len(args) == 2 and (name in _MATH_PLAIN_TWO or name in ('pow', 'fmod') or name in _MATH_INT_TWO):
                helper = name
            elif len(args) == 1 and name in _MATH_LIST_ONE:
                helper = name
            elif name == 'log' and len(args) == 2:
                helper = 'log2args'
            elif name == 'fabs' and len(args) == 1:
                helper = 'fabs'
            if name == 'trunc' and len(args) == 1:
                # int(x) truncates a float toward zero and returns an int argument as it is.
                return ast.Call(func=ast.Name(id='int', ctx=ast.Load()), args=args, keywords=[])
            if helper is not None:
                for each in (*_MATH_DEPS.get(helper, ()), helper):
                    if each not in self.helpers:
                        self.helpers.append(each)
                return ast.Call(func=ast.Name(id='_ail_math_' + helper, ctx=ast.Load()), args=args, keywords=[])
            if len(args) == 1 and name in ('floor', 'ceil'):
                def call(function, argument):
                    return ast.Call(func=ast.Name(id=function, ctx=ast.Load()), args=[argument], keywords=[])
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
        elif node in self.alias_nodes or node in self.re_nodes:
            self.replace(node, 'pass', True)
        elif isinstance(node, ast.Assign) and self.re_on and self.re_unpack(node):
            pass
        elif isinstance(node, ast.For) and self.re_on and self.re_findall_loop(node, function):
            names = self.re_subst_now
            self.re_subst_now = None
            saved = dict(self.re_subst)
            self.re_subst.update(names)
            self.block(node.body, function, owner)
            self.re_subst = saved
            self.block(node.orelse, function, owner)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and self.object_setattr(node):
            pass
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

    def object_setattr(self, node):
        """`object.__setattr__(self, "name", value)` (how a frozen dataclass's __post_init__ sets a field) as the
        assignment `self.name = value`; a frozen instance is not write-protected on either path."""
        call = node.value
        func = call.func
        if not (isinstance(func, ast.Attribute) and func.attr == '__setattr__' and isinstance(func.value, ast.Name)
                and func.value.id == 'object' and 'object' not in self.names and 'object' not in self.modules
                and len(call.args) == 3 and not call.keywords
                and not any(isinstance(arg, ast.Starred) for arg in call.args)
                and isinstance(call.args[0], ast.Name)
                and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str)
                and call.args[1].value.isidentifier()):
            return False
        value = ast.unparse(self.rewritten(call.args[2])[0])
        self.replace(node, f'{call.args[0].id}.{call.args[1].value} = {value}', True)
        return True

    def generic(self, node, function, owner):
        for _, value in ast.iter_fields(node):
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, ast.stmt):
                    self.statement(item, function, owner)
                elif isinstance(item, ast.expr):
                    self.expression(item, _ == 'test' and isinstance(node, (ast.If, ast.While, ast.Assert)))
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
        repr_off = isinstance(options.get('repr'), ast.Constant) and not options['repr'].value
        eq_off = isinstance(options.get('eq'), ast.Constant) and not options['eq'].value   # (`options` is reused below)
        order_on = isinstance(options.get('order'), ast.Constant) and options['order'].value is True
        frozen = any(isinstance(options.get(k), ast.Constant) and options[k].value is True
                     for k in ('frozen', 'unsafe_hash'))
        for option, value in options.items():
            enabled = not (isinstance(value, ast.Constant) and not value.value)
            if option == 'init' and not enabled:
                self.note(node, f'@dataclass({option}={ast.unparse(value)}) is not built; @dataclass '
                          'with annotated fields is, as the __init__ it generates')
                return
        if any(isinstance(each, ast.FunctionDef) and each.name == '__init__' for each in node.body):
            return
        fields = []
        hidden = set()
        uncompared = set()
        initless = set()               # field(init=False): not a parameter of __init__
        for statement in node.body:
            if not (isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)):
                continue
            annotation, _ = self.normalized(statement.annotation)
            if 'ClassVar' in ast.unparse(annotation):
                self.note(statement, 'a ClassVar in a @dataclass is not built')
                return
            if 'InitVar' in ast.unparse(annotation):
                self.note(statement, 'an InitVar in a @dataclass is not built')
                return
            default = None
            value = statement.value
            if (isinstance(value, ast.Call) and self.path(value.func) == 'dataclasses.field'):
                options = {item.arg: item.value for item in value.keywords}
                if isinstance(options.get('repr'), ast.Constant) and not options['repr'].value:
                    hidden.add(statement.target.id)
                if 'compare' in options and not (isinstance(options['compare'], ast.Constant)
                                                 and options['compare'].value):
                    uncompared.add(statement.target.id)
                factory = options.pop('default_factory', None)
                plain = options.pop('default', None)
                if isinstance(options.get('init'), ast.Constant) and options['init'].value is False:
                    initless.add(statement.target.id)
                    options.pop('init')
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
        start = self.offset(decorator.lineno, decorator.col_offset)
        at = start - 1
        while at >= 0 and self.data[at:at + 1] in (b' ', b'\t'):
            at -= 1
        if at < 0 or self.data[at:at + 1] != b'@':
            return
        # a marker comment instead of nothing: the general (boxed) path prints the instance as
        # ClassName(field=..., ...) for it; the typed path never sees a comment
        # (the typed path builds the __eq__ a dataclass generates from it too: ` noeq` for eq=False and
        # ` nocmp=` for fields declared compare=False, both written before ` hide=`)
        # ` norepr` for repr=False (the marker is written all the same: the general path's generated __eq__ reads it)
        marker = '# ail:dataclass' + (' noeq' if eq_off else '') + (' frozen' if frozen else '') + (' norepr' if repr_off else '') + (
            ' nocmp=' + ','.join(sorted(uncompared)) if uncompared else '')
        self.edits.append((at, self.offset(decorator.end_lineno, decorator.end_col_offset), marker, False))
        # a dataclass that extends another one: its fields come after the base's (a field of the same
        # name keeps the base's position)
        merged = []                    # (name, annotation, default, hidden, init=False)
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in self.dc_annotations:
                inherited = self.dc_default[base.id]
                merged = [(name, annotation, inherited.get(name), shown, name in self.dc_initless.get(base.id, ()))
                          for name, annotation, shown in self.dc_annotations[base.id]]
        for _, name, annotation, default in fields:
            entry = (name, annotation, default, name in hidden, name in initless)
            for index, old in enumerate(merged):
                if old[0] == name:
                    merged[index] = entry
                    break
            else:
                merged.append(entry)
        given = [each for each in merged if not each[4]]
        parameters = ', '.join(f'{name}: {annotation}' for name, annotation, *_ in given)
        # a field(init=False) is set to its default. With none it is left unset (reading it raises AttributeError),
        # unless some __post_init__ assigns it: then it gets a place in the field order (repr) first, as None
        later = {t.attr for fn in node.body if isinstance(fn, ast.FunctionDef) and fn.name == '__post_init__'
                 for t in ast.walk(fn) if isinstance(t, ast.Attribute) and isinstance(t.ctx, ast.Store)}
        for base in node.bases:
            later |= self.dc_later.get(base.id, set()) if isinstance(base, ast.Name) else set()
        self.dc_later[node.name] = later
        body = '; '.join(f'self.{name} = {name}' if not skip else f'self.{name} = {default}'
                         for name, _, default, _, skip in merged
                         if not skip or default is not None or name in later) or 'pass'
        if (any(isinstance(each, ast.FunctionDef) and each.name == '__post_init__' for each in node.body)
                or any(isinstance(base, ast.Name) and base.id in self.post_init for base in node.bases)):
            # the generated __init__ ends with the call dataclass makes (a base class's hook is inherited)
            body += '; self.__post_init__()'
            self.post_init.add(node.name)
        init = f'def __init__(self, {parameters}): {body}'
        wanted = self.dc_wanted()
        # the indentation of the class body, as written (tabs included). An inline suite (`class E: pass`) has
        # its first statement on the class's own line; its body is made a block first, one level in from the
        # class/decorator indentation, not from the column after the colon.
        base_indent = self.data[self.starts[decorator.lineno - 1]:at].decode('utf8')
        first = fields[0][0] if fields else node.body[0]
        inline = first.lineno == node.lineno
        if inline:
            body_indent = base_indent + ('\t' if '\t' in base_indent else '    ')
        else:
            body_indent = self.data[self.starts[first.lineno - 1]:
                                    self.offset(first.lineno, first.col_offset)].decode('utf8')
        pad = '\n' + body_indent
        if order_on:
            # order=True: the four comparisons of the tuple of the compared fields (an instance of another class,
            # a subclass included, answers NotImplemented, so the comparison raises TypeError, as in CPython)
            compared = [name for name, *_ in merged if name not in uncompared]
            ours = '(' + ''.join(f'self.{name}, ' for name in compared) + ')'
            theirs = '(' + ''.join(f'other.{name}, ' for name in compared) + ')'
            for dunder, operator in (('lt', '<'), ('le', '<='), ('gt', '>'), ('ge', '>=')):
                init += f'{pad}def __{dunder}__(self, other): return {ours} {operator} {theirs} if type(other) is type(self) else NotImplemented'
        if 'asdict' in wanted:
            pairs = ', '.join(f'{name!r}: _ail_dcv(self.{name})' for name, *_ in merged)
            init += f'{pad}def _ail_asdict(self): return {{{pairs}}}'
            self.dc_val = True
        if 'replace' in wanted and not any(each[4] for each in merged):
            values = ', '.join(f'kw[{name!r}] if {name!r} in kw else self.{name}' for name, *_ in merged)
            known = '[' + ', '.join(repr(name) for name, *_ in merged) + ']'
            inner = pad + '    '
            # an unknown field name is the TypeError of the constructor call dataclasses.replace makes
            init += (f'{pad}def _ail_replace(self, kw):{inner}for k in kw:{inner}    if k not in {known}:'
                     f'{inner}        raise TypeError("{node.name}.__init__() got an unexpected keyword argument " + repr(k))'
                     f'{inner}return {node.name}({values})')
        if inline:
            # an inline suite cannot be continued by an indented block: start a block before its first statement
            first_at = self.offset(first.lineno, first.col_offset)
            self.edits.append((first_at, first_at, '\n' + body_indent, False))
        if fields:
            self.replace(fields[0][0], init, True)
            for statement, *_ in fields[1:]:
                self.replace(statement, '', True)  # a class body here holds methods only, not `pass`
            self.consumed.update(statement for statement, *_ in fields)
        else:
            # a @dataclass with no fields of its own (an empty class, or one extending a fieldless dataclass):
            # still gets the generated __init__, __eq__ and repr CPython gives it
            anchor = node.body[-1]
            anchor_at = self.offset(anchor.end_lineno, anchor.end_col_offset)
            self.edits.append((anchor_at, anchor_at, '\n' + body_indent + init, True))
        self.dataclasses[node.name] = [(name, default) for name, _, default, _, skip in merged if not skip]
        self.dc_annotations[node.name] = [(name, annotation, shown) for name, annotation, _, shown, _ in merged]
        self.dc_initless[node.name] = {name for name, *_, skip in merged if skip}
        self.dc_all[node.name] = [name for name, *_ in merged]
        self.dc_default[node.name] = {name: default for name, _, default, *_ in merged}
        extra = ''
        if any(each[4] for each in merged):
            # the field order of repr and ==, which the parameters of __init__ no longer give (pyboxed2 reads it)
            extra += ' fields=' + ','.join(name for name, *_ in merged)
        if not repr_off and any(each[3] for each in merged):
            # which fields repr leaves out, for the general path's marker lookup
            extra += ' hide=' + ','.join(name for name, _, _, shown, _ in merged if shown)
        if extra:
            for index, (start, end, text, flag) in enumerate(self.edits):
                if text == marker and start == at:
                    self.edits[index] = (start, end, marker + extra, flag)

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

    def starts_processes(self):
        if not hasattr(self, '_starts_processes'):
            self._starts_processes = any(
                (isinstance(n, ast.Import) and any(a.name == 'subprocess' for a in n.names))
                or (isinstance(n, ast.ImportFrom) and not n.level and n.module == 'subprocess') for n in self.tree.body)
        return self._starts_processes

    def star_print(self, node):
        """`print(*xs)` / `print(label, *xs, sep=S, end=E)` as a loop over `xs` (constant sep / end): the typed
        path walks any list, str or iterable of a type it knows, and the general path runs the loop too. The
        separator goes in front of every item but the first, so an empty `xs` prints just the leading values."""
        call = node.value
        if not (isinstance(call.func, ast.Name) and call.func.id == 'print' and 'print' not in self.names
                and call.args and isinstance(call.args[-1], ast.Starred)
                and not any(isinstance(a, ast.Starred) for a in call.args[:-1])):
            return False
        options = {}
        for keyword in call.keywords:
            if keyword.arg not in ('sep', 'end') or keyword.arg in options or not (
                    isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str)):
                return False
            options[keyword.arg] = keyword.value.value
        column = node.col_offset
        before = self.data[self.starts[node.lineno - 1]:self.offset(node.lineno, column)]
        if before.strip():
            return False                      # not alone on its line (`if c: print(*xs)`)
        sep, end = options.get('sep', ' '), options.get('end', '\n')
        self.star_prints = getattr(self, 'star_prints', 0) + 1
        flag, item = f'_ail_ps{self.star_prints}', f'_ail_px{self.star_prints}'
        lead = [ast.unparse(self.rewritten(a)[0]) for a in call.args[:-1]]
        source = ast.unparse(self.rewritten(call.args[-1].value)[0])
        pad = ' ' * column
        lines = []
        if lead:
            lines.append(f'print({", ".join(lead)}, sep={sep!r}, end="")')
        lines.append(f'{flag} = {sep!r}' if lead else f'{flag} = ""')
        lines += [f'for {item} in {source}:', f'    print({flag}, {item}, sep="", end="")', f'    {flag} = {sep!r}',
                  f'print("", end={end!r})']
        self.replace(node, ('\n' + pad).join(lines), True)
        return True

    def output(self, node):
        call = node.value
        if self.star_print(node):
            return True
        path = self.path(call.func)
        if path in _STDOUT_STATEMENTS:
            if path in ('sys.stdout.flush', 'sys.stdout.buffer.flush', 'sys.setrecursionlimit'):
                # a program that starts processes needs the flush: the child's output is ordered against ours by it (stage G8)
                real = path != 'sys.setrecursionlimit' and not call.args and not call.keywords and self.starts_processes()
                self.replace(node, 'flush_stdout()' if real else 'pass', True)
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
        opened into) is one this pass maps, and the file is consumed (read, or walked line by line) at
        most once: each mapped use reads the whole file again, where CPython's second read of the same
        file object finds it at its end (`f.read(), f.read()` is the text and '')."""
        consuming = []
        statements = set(map(id, body))

        def repeated(node):
            # inside a loop (or a comprehension) of the body: the use runs more than once
            child, up = node, self.parents.get(node)
            while up is not None and id(child) not in statements:
                if isinstance(up, (ast.For, ast.While, ast.AsyncFor)) and child is not getattr(up, 'iter', None):
                    return True
                if isinstance(up, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda,
                                   ast.FunctionDef)):
                    return True
                child, up = up, self.parents.get(up)
            return False
        for statement in body:
            for node in ast.walk(statement):
                if not (isinstance(node, ast.Name) and node.id == name) or node is binding:
                    continue
                parent = self.parents.get(node)
                grand = self.parents.get(parent)
                if isinstance(parent, ast.Attribute) and isinstance(grand, ast.Call) and grand.func is parent \
                        and not grand.args and not grand.keywords and parent.attr in ('read', 'readlines'):
                    consuming.append(grand)
                elif isinstance(parent, ast.For) and parent.iter is node:
                    consuming.append(node)
        if len(consuming) > 1 or any(repeated(each) for each in consuming):
            return False
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
            elif (not node.level and node.module == 'collections.abc'
                  and _annotation_only_names(self.tree, [alias.asname or alias.name for alias in node.names])):
                self.replace(node, 'pass', True)
            elif not node.level and node.module in _SMALL_MODULES:
                built = _SMALL_MODULES[node.module]
                if node.module not in self.keep and all(alias.name in built for alias in node.names):
                    self.replace(node, 'pass', True)
                else:
                    missing = [alias.name for alias in node.names if alias.name not in built]
                    if missing:
                        self.note(node, f'from {node.module} import {", ".join(missing)}: not built; '
                                  + _SMALL_NOTE[node.module])
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


def _sqllower():
    """python/pkg-v12/sqllower.py (sqlite3 lowered onto the C primitives, before the tuple and Optional passes)."""
    if not hasattr(_sqllower, "module"):
        here = str(Path(__file__).parent / "python" / "pkg-v12")
        if here not in sys.path:
            sys.path.insert(0, here)
        import sqllower
        _sqllower.module = sqllower
    return _sqllower.module


def _modtables():
    """python/pkg-v12/modtables.py (module-level tables with tuples in them, lowered before the tuple pass)."""
    if not hasattr(_modtables, "module"):
        here = str(Path(__file__).parent / "python" / "pkg-v12")
        if here not in sys.path:
            sys.path.insert(0, here)
        import modtables
        _modtables.module = modtables
    return _modtables.module


_ALIAS_TYPE_NAMES = frozenset((
    'int', 'float', 'str', 'bool', 'bytes', 'None', 'list', 'dict', 'set', 'tuple', 'frozenset', 'bytearray',
    'List', 'Dict', 'Set', 'Tuple', 'FrozenSet', 'Optional', 'Union', 'Sequence', 'Iterable', 'Collection',
    'Mapping', 'Final'))


def _inline_type_aliases(source):
    """`Grid = list[list[int]]`, `Point: TypeAlias = tuple[int, int]`, `type Row = list[str]`: a
    module-level name bound once to a type, and named nowhere but in annotations (its own and other
    aliases' included), is written out in those annotations and its statement becomes `pass` -- the
    annotation then says what it means to every pass that reads annotations. Lines and columns of
    everything else are kept. A program without such an alias is returned unchanged."""
    if '=' not in source and 'type ' not in source:
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    candidates = {}
    for node in tree.body:
        name = value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        elif (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None
              and (isinstance(node.annotation, ast.Name) and node.annotation.id == 'TypeAlias'
                   or isinstance(node.annotation, ast.Attribute) and node.annotation.attr == 'TypeAlias')):
            name, value = node.target.id, node.value
        elif hasattr(ast, 'TypeAlias') and isinstance(node, ast.TypeAlias) and not node.type_params:
            name, value = node.name.id, node.value
        if name is not None and name not in classes:
            candidates.setdefault(name, []).append((node, value))
    candidates = {k: v[0] for k, v in candidates.items() if len(v) == 1}
    if not candidates:
        return source

    def is_type(e, names):
        if isinstance(e, ast.Name):
            return e.id in _ALIAS_TYPE_NAMES or e.id in classes or e.id in names
        if isinstance(e, ast.Constant):
            return e.value is None
        if isinstance(e, ast.Attribute):
            return isinstance(e.value, ast.Name) and e.value.id in ('typing', 't') and e.attr in _ALIAS_TYPE_NAMES
        if isinstance(e, ast.Subscript):
            inner = e.slice.elts if isinstance(e.slice, ast.Tuple) else [e.slice]
            return is_type(e.value, names) and all(
                is_type(x, names) or isinstance(x, ast.Constant) and x.value is Ellipsis for x in inner)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.BitOr):
            return is_type(e.left, names) and is_type(e.right, names)
        return False

    aliases = dict(candidates)
    changed = True
    while changed:                    # an alias may name another alias
        changed = False
        for name in list(aliases):
            node, value = aliases[name]
            if not is_type(value, set(aliases)):
                del aliases[name]
                changed = True
    if not aliases:
        return source
    # every mention must sit in an annotation or in an alias's own value
    allowed = set()
    for node in ast.walk(tree):
        spots = []
        if isinstance(node, ast.arg):
            spots.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spots.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            spots.append(node.annotation)
        for spot in spots:
            if spot is not None:
                allowed.update(id(x) for x in ast.walk(spot))
    for node, value in aliases.values():
        allowed.update(id(x) for x in ast.walk(value))
        allowed.update(id(x) for x in ast.walk(node))
    for x in ast.walk(tree):
        if isinstance(x, ast.Name) and x.id in aliases and id(x) not in allowed:
            return source             # used as a value somewhere: leave every alias as written
    lines = source.splitlines(True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def offset(lineno, col):
        return starts[lineno - 1] + len(lines[lineno - 1].encode('utf8')[:col].decode('utf8', 'replace'))

    def text_of(name, depth=0):
        _, value = aliases[name]
        out = ast.get_source_segment(source, value)
        if out is None or depth > 20:
            return None
        inner = sorted(((x.lineno, x.col_offset, x.end_lineno, x.end_col_offset, x.id) for x in ast.walk(value)
                        if isinstance(x, ast.Name) and x.id in aliases), reverse=True)
        base_line, base_col = value.lineno, value.col_offset
        for line, col, end_line, end_col, ref in inner:
            sub = text_of(ref, depth + 1)
            if sub is None:
                return None
            if line != base_line or end_line != base_line:
                return None           # a multi-line alias value with an inner alias: left alone
            out = out[:col - base_col] + sub + out[end_col - base_col:]
        if isinstance(value, ast.BinOp):
            out = '(' + out + ')'
        return ' '.join(out.split())

    edits = []
    texts = {}
    for name in aliases:
        texts[name] = text_of(name)
        if texts[name] is None:
            return source
    alias_nodes = {id(node) for node, _ in aliases.values()}
    in_alias = {id(y) for node, _ in aliases.values() for y in ast.walk(node)}
    for node in tree.body:
        if id(node) in alias_nodes:
            start = offset(node.lineno, node.col_offset)
            end = offset(node.end_lineno, node.end_col_offset)
            edits.append((start, end, 'pass' + '\n' * source[start:end].count('\n')))
    for x in ast.walk(tree):
        if isinstance(x, ast.Name) and x.id in aliases and id(x) in allowed and id(x) not in in_alias:
            edits.append((offset(x.lineno, x.col_offset), offset(x.end_lineno, x.end_col_offset), texts[x.id]))
    for start, end, text in sorted(edits, reverse=True):
        source = source[:start] + text + source[end:]
    return source


def python_surface(source, notes=None, library=False):
    """Map the Python spellings above onto the compiler's own; `notes` collects (line, why) for
    the constructs left as written."""
    source = _inline_type_aliases(source)
    if "raise" in source and " from " in source:
        source = _raisefrom().rewrite(source, notes)
    if "match" in source:
        source = _matchlower().rewrite(source, notes)
    if "def " in source:
        source = _nestfn().rewrite(source, notes)
    if "sqlite3" in source:
        source = _sqllower().rewrite_text(source, notes)
    if any(name in source for name in ("concurrent", "multiprocessing", "threading")):
        _threadlib()                             # puts python/pkg-v12 on sys.path
        import typedpar                          # typed parallelism without the lock (TYPED_PARALLEL.md)
        source = typedpar.rewrite_text(source, notes)
    if any(name in source for name in ("threading", "queue", "concurrent")):
        source = _threadlib().rewrite_text(source, notes)
    if any(name in source for name in ("fractions", "enum", "namedtuple", "NamedTuple", "ChainMap", "keyword", "calendar",
                                       "abc", "array", "Random", "string", "io", "statistics")):
        source = _stdlib5().rewrite_text(source, notes)
    if any(name in source for name in ("csv", "datetime", "decimal", "fractions", "time", "zoneinfo")):
        source = _stdlib4().rewrite_text(source, notes)
    if "collections" in source:
        source = _collib().rewrite(source, notes)
    if "None" in source or "Optional" in source:
        source = _optlib().rewrite(source, notes)
    if "(" in source:
        source = _modtables().rewrite_text(source, library, notes)
    source = _tuplib().rewrite(source, notes)
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
