"""Portable entry for the AIL source snapshot; no implicit model calls."""
import ast
import argparse
import hashlib
import json
import operator
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from ail_syntax import SyntaxErrorAIL, detect, fold_constants, python_surface, python_wording, translate
import ail_sexpr
import ail_modules

sys.path.append(str(Path(__file__).resolve().parent / 'python/pkg-v12'))
import fastwalk
fastwalk.install()      # the same ast.walk in half the time, for every walk this process makes

ROOT = Path(__file__).resolve().parent
_BUILDCACHE = []


def _relpath(path):
    """os.path.relpath that survives the platforms where there is no plain relative form:
    a path on another drive (Windows: temp on C:, cwd on D:) answers the '..' spelling every caller
    already treats as "show it absolute", and a spelling that differs only by aliases (Windows
    8.3 short names such as RUNNER~1, macOS /var -> /private/var) is compared by real path."""
    try:
        relative = os.path.relpath(path)
    except ValueError:
        relative = None
    if relative is None or relative.startswith(os.pardir):
        try:
            relative = os.path.relpath(os.path.realpath(path), os.path.realpath(os.curdir))
        except ValueError:
            return os.pardir + os.sep + str(path)
    return relative


def _build_cache(args=None):
    """The build cache module (python/pkg-v12/buildcache.py), or None when it is switched off
    (AIL_NO_CACHE, --no-cache) or cannot be loaded. Loaded by path so pkg-v12 stays off sys.path."""
    if not _BUILDCACHE:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location('buildcache', ROOT / 'python/pkg-v12/buildcache.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _BUILDCACHE.append(module)
        except (OSError, ImportError, SyntaxError):
            _BUILDCACHE.append(None)
    module = _BUILDCACHE[0]
    return None if module is None or module.disabled() else module


_MERGED_ENTRIES = {}         # entry file -> ail_modules.Merged, for entries whose text merges several modules


def _literal_number(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        node = node.operand
    return isinstance(node, ast.Constant) and type(node.value) in (int, float)


def _module_constant(node):
    if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return False
    value = node.value
    return (isinstance(value, ast.Constant) and type(value.value) in (str, bytes)
            or _literal_number(value) or isinstance(value, (ast.List, ast.Tuple))
            and bool(value.elts) and all(map(_literal_number, value.elts)))


_PURE_INT_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
                    ast.Pow: operator.pow, ast.LShift: operator.lshift, ast.RShift: operator.rshift,
                    ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor}
_MAX_CONST_BITS = 1 << 16


class _HugeConstant(Exception):
    pass


_HUGE = object()


def _pure_constant_int(node):
    """The value of a pure integer constant expression, or None when `node` is not one.

    `_HugeConstant` means the value is certainly outside int64 (larger than _MAX_CONST_BITS bits),
    so a 10**100000000 exponent is refused without computing it.  Operators that yield a float
    (division, a negative exponent) are not constant int expressions here."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
        value = _pure_constant_int(node.operand)
        if value is None:
            return None
        if isinstance(node.op, ast.Invert):
            value = ~value
        elif isinstance(node.op, ast.USub):
            value = -value
        if value.bit_length() > _MAX_CONST_BITS:
            raise _HugeConstant
        return value
    if isinstance(node, ast.BinOp) and type(node.op) in _PURE_INT_BINARY:
        try:
            left = _pure_constant_int(node.left)
        except _HugeConstant:
            left = _HUGE
        try:
            right = _pure_constant_int(node.right)
        except _HugeConstant:
            right = _HUGE
        if left is None or right is None:
            return None
        if left is _HUGE or right is _HUGE:
            if isinstance(node.op, (ast.Mult, ast.BitAnd)) and (left == 0 or right == 0):
                return 0
            if isinstance(node.op, ast.LShift) and left == 0:
                return 0
            if isinstance(node.op, ast.Pow) and (right == 0 or left == 0):
                return 1 if right == 0 else 0
            raise _HugeConstant
        if isinstance(node.op, ast.Pow):
            if right < 0:
                return None
            if abs(left) > 1 and (right > 4096 or abs(left).bit_length() * right > _MAX_CONST_BITS):
                raise _HugeConstant
            value = left ** right
        elif isinstance(node.op, ast.LShift):
            if right < 0:
                return None
            if left and (right > 4096 or left.bit_length() + right > _MAX_CONST_BITS):
                raise _HugeConstant
            value = left << right
        elif isinstance(node.op, ast.RShift):
            if right < 0:
                return None
            value = 0 if left >= 0 else -1
            if right <= _MAX_CONST_BITS:
                value = left >> right
        else:
            try:
                value = _PURE_INT_BINARY[type(node.op)](left, right)
            except (ArithmeticError, ValueError):
                return None
        if value.bit_length() > _MAX_CONST_BITS:
            raise _HugeConstant
        return value
    return None


def _check_int64_literals(tree):
    maxsplit = _maxsplit_constant_nodes(tree)
    nodes = [tree]
    while nodes:
        node = nodes.pop()
        if id(node) in maxsplit and not (isinstance(node, ast.Constant) and type(node.value) is int):
            continue
        text = None
        if isinstance(node, ast.Constant) and type(node.value) is int:
            value = node.value
            text = str(value)
        elif (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert))
              or isinstance(node, ast.BinOp) and type(node.op) in _PURE_INT_BINARY):
            try:
                value = _pure_constant_int(node)
            except _HugeConstant:
                text = ast.unparse(node)
                error = ValueError(f'int64 literal out of range: {text}')
                error.source_line = node.lineno
                error.source_column = node.col_offset
                raise error
            if value is None:
                nodes.extend(ast.iter_child_nodes(node))
                continue
            text = str(value)
        else:
            nodes.extend(ast.iter_child_nodes(node))
            continue
        if not -(1 << 63) <= value < 1 << 63:
            error = ValueError(f'int64 literal out of range: {text}')
            error.source_line = node.lineno
            error.source_column = node.col_offset
            raise error


_INT_BINARY = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
}


def _constant_int(node, known):
    """The int value of a constant expression, or None when it is not statically known.
    Names resolve only through known module constants; a local of the same name keeps the
    expression out of known, so a shadowed constant is never folded by mistake."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.Name):
        return known.get(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _constant_int(node.operand, known)
        if value is None:
            return None
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        left = _constant_int(node.left, known)
        if left is None:
            return None
        if isinstance(node.op, ast.Pow):
            right = _constant_int(node.right, known)
            if right is None or right < 0:
                return None
            if abs(left) <= 1:
                return left ** right
            if right > 64:
                return 1 << 64 if left > 0 else -(1 << 64)
            return left ** right
        operation = _INT_BINARY.get(type(node.op))
        if operation is None:
            return None
        right = _constant_int(node.right, known)
        if right is None:
            return None
        return operation(left, right)
    return None


def _maxsplit_constant_nodes(tree):
    """Nodes under a name-free str.split/rsplit maxsplit argument, whose own front end folds a
    constant and reports an out-of-int64 value with the maxsplit wording."""
    handled = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in ('split', 'rsplit')):
            continue
        roots = []
        if len(node.args) > 1:
            roots.append(node.args[1])
        roots.extend(kw.value for kw in node.keywords if kw.arg == 'maxsplit')
        for root in roots:
            if any(isinstance(inner, ast.Name) for inner in ast.walk(root)):
                continue
            handled.update(id(inner) for inner in ast.walk(root))
    return handled


def _check_int64_unary_constants(tree):
    """Refuse a statically known unary integer constant expression outside int64 by name.
    `-MIN` on a module constant or a nested literal compiles to the fixed-width trap on the
    default build, while CPython prints a bignum; the runtime trap stays for values that only
    reach the unary operation as variables."""
    maxsplit = _maxsplit_constant_nodes(tree)
    stores = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stores[node.id] = stores.get(node.id, 0) + 1
    parameters = {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    known = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or stores.get(target.id) != 1 or target.id in parameters:
            continue
        value = _constant_int(node.value, known)
        if value is not None:
            known[target.id] = value
    for node in ast.walk(tree):
        if not isinstance(node, ast.UnaryOp) or not isinstance(node.op, (ast.UAdd, ast.USub)):
            continue
        if id(node) in maxsplit:
            continue
        value = _constant_int(node, known)
        if value is not None and not -(1 << 63) <= value < 1 << 63:
            error = ValueError(f'int64 constant expression out of range: {value}')
            error.source_line = node.lineno
            error.source_column = node.col_offset
            raise error


def _returns_on_every_path(statements):
    def loop_exit(body):
        pending = list(body)
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.Break, ast.Continue)):
                return True
            if isinstance(node, (ast.For, ast.While)):
                pending.extend(node.orelse)
            elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                pending.extend(ast.iter_child_nodes(node))
        return False

    return any(
        isinstance(node, (ast.Return, ast.Raise))
        or (isinstance(node, ast.If) and bool(node.orelse)
            and _returns_on_every_path(node.body)
            and _returns_on_every_path(node.orelse))
        or (isinstance(node, ast.Try)
            and (_returns_on_every_path(node.finalbody)
                 or not loop_exit(node.finalbody)
                 and all(_returns_on_every_path(handler.body) for handler in node.handlers)
                 and (_returns_on_every_path(node.body)
                      or bool(node.orelse) and _returns_on_every_path(node.orelse))))
        for node in statements)


ZIG_TARGETS = {'linux': 'x86_64-linux-gnu', 'linux-arm64': 'aarch64-linux-gnu',
               'windows': 'x86_64-windows-gnu', 'macos': 'aarch64-macos', 'macos-x86_64': 'x86_64-macos'}


def _zig_compiler(target):
    """A one-file C compiler command that runs `zig cc -target <triple>`, for $PIPE_CC.

    zig bundles the C libraries of every target, so one install builds Linux, Windows and macOS
    executables from any host. The wrapper lives in a temporary directory for this process."""
    import atexit, shutil, stat, tempfile
    zig = os.environ.get('AIL_ZIG') or shutil.which('zig')
    if not zig:
        local = Path.home() / 'tools' / 'zig' / ('zig.exe' if os.name == 'nt' else 'zig')
        zig = str(local) if local.is_file() else None
    if not zig:
        raise SystemExit('--target needs zig: set $AIL_ZIG, put zig on PATH, or unpack it to ~/tools/zig')
    directory = Path(tempfile.mkdtemp(prefix='ail-zigcc-'))
    atexit.register(shutil.rmtree, directory, True)
    triple = ZIG_TARGETS[target]
    if os.name == 'nt':
        wrapper = directory / 'zigcc.cmd'
        wrapper.write_text('@"%s" cc -target %s %%*\r\n' % (zig, triple), encoding='utf-8')
    else:
        wrapper = directory / 'zigcc'
        wrapper.write_text('#!/bin/sh\nexec "%s" cc -target %s "$@"\n' % (zig, triple), encoding='utf-8')
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return str(wrapper)


def _check_main_called(tree):
    """Python-surface programs: CPython runs nothing for a `main` that is defined and never
    called, so this compiler (whose entry convention would call it) refuses instead of printing
    what CPython would not. `main()`, `sys.exit(main())` and `raise SystemExit(main())` count as
    calls; a call inside `main` itself (recursion) does not."""
    mains = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main']
    if not mains:
        return
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'main'
                and not any(m.lineno <= node.lineno <= m.end_lineno for m in mains)):
            return
    error = ValueError('main() is defined but never called, so CPython would run nothing and this '
                       'compiler refuses rather than run it.\n'
                       '  write instead: add `main()` as the last line of the file '
                       '(or `if __name__ == "__main__": main()`)')
    error.source_line, error.source_column = mains[0].lineno, mains[0].col_offset
    raise error


# third-party modules whose refusal elsewhere names the standard-library replacement (regex -> re)
_IMPORT_HINTS = {'regex'}


def _check_importable(tree):
    """A top-level `import X` / `from X import ...` whose X is neither in the standard library nor on the search
    path (a third-party package, a typo): CPython stops with ModuleNotFoundError at that line, and a program that
    never uses the name would otherwise be built and run. (Local modules were merged away before this; an import
    inside `try:`, a function or `if` is not looked at, so `try: import numpy ... except ImportError` keeps its
    meaning. `_ail_*` names are the compiler's own markers, such as the one the threads rewrite adds.)"""
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            root = name.split('.')[0]
            if root in sys.stdlib_module_names or root in ail_modules.MODELLED or root == 'ail_ffi' or root.startswith('_ail_') or root in _IMPORT_HINTS:
                continue
            error = ValueError(
                "import of %r is not available: it is not part of the standard library and no module of that name "
                "is on the search path, so CPython stops here with ModuleNotFoundError.\n"
                "  write instead: drop the import and write what you need by hand with plain lists, dicts and "
                "loops" % name)
            error.source_line, error.source_column = node.lineno, node.col_offset
            raise error


def _ffi_session(args):
    """The G4 session that lowers `@extern` stubs (ail_ffi_lower.py), closed when the process ends."""
    import atexit
    import ail_ffi_lower
    session = ail_ffi_lower.Session(forbid=getattr(args, 'no_ffi', False))
    atexit.register(session.close)
    return session


def _refuse_load(error):
    """Print a load-time refusal as `path:line:col: message` (no argparse usage dump) and exit 2.
    The position comes from the failing check (`error.refusal`) when the loader found one."""
    refusal = getattr(error, 'refusal', None)
    if refusal is None:
        message = str(error)
    else:
        path, line, column, text = refusal
        where = _relpath(path)
        message = '%s:%d:%d: %s' % (path if where.startswith('..') else where, line, column, text)
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _load_sources(source, extra_modules=(), source_syntax='auto', *, module_only=False,
                  separate=False, module_paths=(), origins=None, source_map=None, declarations_only=False, source_bytes=None,
                  notes=None, local_imports=False, ffi=None, prelower=None):
    """Resolve source imports once and validate their shared declaration scope.

    `prelower` rewrites the entry's text right after it is read (ail_export.lower for `--lib`); the
    classes it leaves behind are then allowed in a module-only Python source.

    `local_imports` lets a Python-syntax entry import sibling modules (ail_modules, stage G1): their
    bodies are merged into the entry's text before everything below sees it."""
    search_paths = tuple(dict.fromkeys(Path(path).resolve() for path in module_paths))
    if any(not path.is_dir() for path in search_paths):
        raise ValueError('each --module-path must name an existing directory')
    standard = ROOT / 'language_examples'
    modules = []
    names = set()
    seen = set()
    active = []
    contracts = []
    constants = set()
    functions = []
    unit_map = {}
    unit_locations = {}

    def load(path, *, entry=False):
        path = path.resolve()
        if path in active:
            raise ValueError('AIL module cycle: ' + ' -> '.join(p.name for p in [*active, path]))
        if path in seen:
            return None
        if path.suffix.lower() not in (('.ail', '.py') if entry else ('.ail',)) or not path.is_file():
            raise ValueError(f'AIL module not found: {path}')
        # set before decoding: the error handler below reads it when the bytes are not UTF-8
        syntax = 'python' if path.suffix.lower() == '.py' else source_syntax
        try:
            if source_bytes is None:
                text = path.read_text(encoding='utf-8-sig')
            else:
                data=path.read_bytes();source_bytes[path]=data
                text=data.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
            if prelower is not None and entry:
                text = prelower(text)
            if source_syntax in ('auto', 'ail') and ail_sexpr.detect(text):
                # The S-expression surface is converted to block syntax and then checked exactly
                # like it; positions in diagnostics refer to that block text.
                text = ail_sexpr.to_block(text)
            syntax = ('ail' if detect(text) else 'python') if source_syntax == 'auto' else source_syntax
            if path.suffix.lower() == '.py':
                syntax = 'python'
            merged = None
            if ffi is not None and syntax == 'python':
                # G4: `@extern` stubs become ordinary functions over a generated C object (ail_ffi_lower.py);
                # a file that does not mention ail_ffi is returned untouched
                text = ffi.lower(path, text)
            if local_imports and entry and syntax == 'python' and not module_only:
                merged = ail_modules.merge_program(path, text, **({} if ffi is None else {'read': ffi.read}))
                if merged is not None:
                    _MERGED_ENTRIES[str(path)] = merged
                    text = merged.text
                    for line in merged.notes:
                        print(line, file=sys.stderr)
            imports = []
            declarations = {}
            locations = {}
            if syntax == 'ail':
                text = translate(text, module=module_only or not entry, imports=imports, declarations=declarations, source_map=locations)
            else:
                # Python spellings of built-ins and result contracts (ail_syntax.python_surface);
                # every statement stays on its own line, so positions below are unchanged.
                text = python_surface(text, None if notes is None else notes.setdefault(str(path), []),
                                     library=module_only)
            text = fold_constants(text)
            tree = ast.parse(text, filename=str(path))
            if syntax == 'python' and entry and not module_only and not declarations_only:
                _check_main_called(tree)
                if local_imports:
                    _check_importable(tree)
            if not declarations_only:
                _check_int64_literals(tree)
                _check_int64_unary_constants(tree)
            if merged is not None and merged.positions:
                locations = dict(merged.positions)
            if source_map is not None:
                if syntax == 'python' and merged is None:
                    for node in ast.walk(tree):
                        if isinstance(node, ast.stmt):
                            position = (node.lineno, len(text.splitlines()[node.lineno - 1].encode('utf8')[:node.col_offset].decode('utf8')) + 1)
                            locations[node.lineno] = None if node.lineno in locations else position
                    locations = {line: position for line, position in locations.items() if position is not None}
                unit_locations[text] = ({line: position for line, position in locations.items()}
                                        if merged is not None and merged.positions else
                                        {line: (str(path), *position) for line, position in locations.items()})
            if origins is not None:
                if syntax == 'python' and merged is None:
                    for owner, fn in ((node.name if isinstance(node, ast.ClassDef) else None, member)
                                      for node in tree.body for member in
                                      (node.body if isinstance(node, ast.ClassDef) else [node])
                                      if isinstance(member, ast.FunctionDef)):
                        key = f'{owner}__{fn.name}' if owner else fn.name
                        column = len(text.splitlines()[fn.lineno - 1].encode('utf8')[:fn.col_offset].decode('utf8')) + 1
                        declarations[key] = None if key in declarations else (fn.lineno, column, f'{owner}.{fn.name}' if owner else fn.name)
                if merged is not None:
                    for owner, fn in ((node.name if isinstance(node, ast.ClassDef) else None, member)
                                      for node in tree.body for member in
                                      (node.body if isinstance(node, ast.ClassDef) else [node])
                                      if isinstance(member, ast.FunctionDef)):
                        key = f'{owner}__{fn.name}' if owner else fn.name
                        where = merged.positions.get(fn.lineno)
                        shown = merged.names.get(fn.name, fn.name)
                        declarations[key] = None if key in declarations or where is None else (
                            where[0], where[1], where[2], f'{owner}.{shown}' if owner else shown)
                for key, declaration in declarations.items():
                    if merged is not None:
                        origins[key] = None if declaration is None or key in origins else declaration
                    else:
                        origins[key] = None if declaration is None or key in origins else (str(path), *declaration)
        except ail_modules.ModuleRefusal:
            raise
        except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
            if hasattr(exc, 'source_line') and merged is not None and exc.source_line in (merged.positions or {}):
                where = merged.positions[exc.source_line]
                exc.source_position = where
                located = ValueError(f'AIL source {where[0]}: line {where[1]}: {exc}')
                located.refusal = (where[0], where[1], where[2], str(exc))
                raise located from exc
            if hasattr(exc, 'source_line'):
                position = locations.get(exc.source_line)
                if syntax == 'python':
                    prefix = text.splitlines()[exc.source_line - 1].encode('utf8')[:exc.source_column]
                    position = (exc.source_line, len(prefix.decode('utf8')) + 1)
                if position is not None:
                    exc.source_position = (str(path), *position)
                if syntax == 'python' and position is not None:
                    # `compile` prints only this message: name the line the check report has.
                    located = ValueError(f'AIL {"source" if entry else "module"} {path}: line {position[0]}: {exc}')
                    located.refusal = (str(path), position[0], position[1], str(exc))
                    raise located from exc
            elif ((isinstance(exc, SyntaxErrorAIL) or syntax == 'python' and type(exc) is SyntaxError)
                  and getattr(exc, 'lineno', None)):
                # a block-syntax or Python syntax error carries its own position
                located = ValueError(f'AIL {"source" if entry else "module"} {path}: {exc}')
                located.refusal = (str(path), exc.lineno, exc.offset or 1,
                                   exc.msg if type(exc) is SyntaxError else str(exc))
                raise located from exc
            raise ValueError(f'AIL {"source" if entry else "module"} {path}: {exc}')
        if syntax == 'ail' and any(isinstance(node, ast.Assign)
                and not _module_constant(node) for node in tree.body):
            raise ValueError('AIL const must be a literal number, string, bytes, or numeric list')
        if syntax == 'ail' and not declarations_only:
            if any(isinstance(node, ast.ClassDef) for node in tree.body):
                contracts.append(path)
            def contract_error(fn, owner, message):
                error = ValueError(message)
                error.source_function = f'{owner}__{fn.name}' if owner else fn.name
                error.diagnostic_code = 'contract'
                return error

            for owner, fn in ((node.name if isinstance(node, ast.ClassDef) else None, member)
                              for node in tree.body for member in
                              (node.body if isinstance(node, ast.ClassDef) else [node])
                              if isinstance(member, ast.FunctionDef)):
                if isinstance(fn.returns, ast.Name) and fn.returns.id == '__ail_checked_void__':
                    if any(isinstance(node, ast.Return) and node.value is not None for node in ast.walk(fn)):
                        raise contract_error(fn, owner, f'AIL function {fn.name}: void function cannot return a value')
                elif fn.returns is not None:
                    if any(isinstance(node, ast.Return) and node.value is None
                           for node in ast.walk(fn)) or not _returns_on_every_path(fn.body):
                        raise contract_error(fn, owner, f'AIL function {fn.name}: annotated return needs a value '
                                     'on every path')
                if fn.returns is not None or any(arg.annotation is not None
                                                  for arg in fn.args.args):
                    contracts.append(path)
        if (module_only or not entry) and ((not tree.body and not imports) or any(not (isinstance(node, ast.FunctionDef)
                or (syntax == 'ail' or prelower is not None) and isinstance(node, ast.ClassDef))
                and not _module_constant(node) for node in tree.body)):
            raise ValueError(f'AIL module needs functions, structs, or literal constants only: {path}')
        if separate and not entry and any(
                isinstance(node, ast.FunctionDef)
                for fn in tree.body if isinstance(fn, ast.FunctionDef)
                for node in ast.walk(fn) if node is not fn):
            raise ValueError(f'AIL separate module cannot contain nested functions: {path}')
        for node in tree.body:
            # a Python-syntax script rebinds a module-level name freely (`values = ...` twice is
            # ordinary Python); only AIL consts and definitions must be unique
            name = (node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else
                    node.targets[0].id if isinstance(node, ast.Assign) and syntax == 'ail'
                    and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) else None)
            if name is not None:
                if name in names:
                    raise ValueError(f'duplicate AIL name: {name}')
                names.add(name)
            if isinstance(node, ast.FunctionDef):
                functions.append(node)
            elif syntax == 'ail' and isinstance(node, ast.Assign) and _module_constant(node):
                constants.add(node.targets[0].id)
        active.append(path)
        for name in imports:
            directories = tuple(dict.fromkeys((path.parent, *search_paths, standard)))
            candidate = next((directory / (name + '.ail') for directory in directories
                              if (directory / (name + '.ail')).exists()
                              or (directory / (name + '.ail')).is_symlink()), None)
            if candidate is None:
                raise ValueError('AIL module not found: %s; searched: %s' % (
                    name, ', '.join(map(str, directories))))
            load(candidate)
        active.pop()
        seen.add(path)
        if not entry:
            modules.append(text)
            if separate:
                unit_map.update({node.name: len(modules) for node in tree.body
                                 if isinstance(node, ast.FunctionDef)})
        return text

    source_text = load(source, entry=True)
    explicit = set()
    for module_arg in extra_modules:
        module = module_arg.resolve()
        if module == source or module in explicit or module.suffix.lower() != '.ail' or not module.is_file():
            raise ValueError('each --module must name a distinct existing .ail file')
        explicit.add(module)
        load(module)
    for fn in functions:
        shadowed = constants.intersection(arg.arg for arg in fn.args.args)
        shadowed.update(node.id for node in ast.walk(fn)
                        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
                        and node.id in constants)
        if shadowed:
            raise ValueError(f'AIL const {min(shadowed)} cannot be rebound or shadowed in a function')
    units = [*modules, source_text]
    if source_map is not None:
        offset = 0
        for text in units:
            source_map.update({offset + line: position for line, position in unit_locations[text].items()})
            offset += text.count('\n') + 2
    return '\n\n'.join(units), bool(contracts), unit_map


def _hand_over_toolchain(cache, environment):
    """Tell the compiler subprocess which toolchain the parent already identified (saves a probe)."""
    if cache is not None:
        compiler = cache.resolve_compiler()
        identity = cache.toolchain(compiler) if compiler else None
        if identity:
            environment['AIL_CACHE_TOOLCHAIN'] = identity + ':' + compiler
    return environment


def _compile_c_key(cache, args, source, text):
    """Cache key of a `compile-c` object: the C source, the interface, every declared header,
    source, assembly file and archive (read the way compile_c reads them), the C API name. None
    when anything is unreadable or outside the source directory; the real build then reports it."""
    try:
        interface = args.interface.resolve(strict=True).read_bytes()
        declared = json.loads(interface)
        root = source.parent
        parts = []
        for field in ('headers', 'sources', 'asm_sources', 'archives'):
            for name in declared.get(field, []):
                path = (root / name).resolve(strict=True)
                if not path.is_relative_to(root) or path == source:
                    return None
                parts += [field, name, path.read_bytes()]
    except (OSError, ValueError, AttributeError, TypeError, RuntimeError):
        return None
    return cache.frontend_key(ROOT / 'python/pkg-v12', 'compile-c', text.encode('utf8'), interface,
                              args.c_api_name or '', *parts)


def _doctor_build_check(report):
    """Check a representative SDK build/run through the public CLI."""
    if not report['python_supported']:
        return {'status': 'failed', 'phase': 'configuration',
                'message': 'AIL compilation requires Python 3.10 or newer'}
    if not report['c_compiler_available']:
        return {'status': 'failed', 'phase': 'configuration',
                'message': 'C compiler is unavailable: ' + str(report['c_compiler_configured'])}
    source = r'''fn main()->int {
 let values:list[int]=[1,2,3]; if sum(values)!=6 { return 1; }
 let buffer=bytearray(b"x"); let buffers:list[bytearray]=[buffer];
 buffers[0].append(121); if bytes(buffer)!=b"xy" { return 2; }
 let listener=tcp_listen("127.0.0.1",0,1);
 try {
  let peers:list[tcpsocket]=[listener]; let flags=tcp_poll(peers,[0],0);
  if len(flags)!=1 or flags[0]!=0 { return 3; }
 } finally { listener.close(); }
 write_stdout_bytes(b"AIL environment\n"); return 0;
}'''
    phase = 'compile'
    try:
        with tempfile.TemporaryDirectory(prefix='ail-doctor-') as directory:
            path = Path(directory)
            input_path = path / 'environment.ail'
            output_path = path / ('environment.exe' if os.name == 'nt' else 'environment')
            input_path.write_text(source, encoding='utf-8')
            result = subprocess.run(
                [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'),
                 'compile', str(input_path), '-o', str(output_path)],
                capture_output=True, cwd=ROOT, env={**os.environ, 'AIL_NO_CACHE': '1'}, timeout=120)
            if result.returncode:
                detail = (result.stderr or result.stdout)[:4096].decode('utf-8', errors='replace')
                return {'status': 'failed', 'phase': phase,
                        'message': f'compile exit {result.returncode}: {detail}'}
            if not output_path.is_file():
                return {'status': 'failed', 'phase': phase,
                        'message': 'compile returned success without an executable'}
            phase = 'run'
            result = subprocess.run([str(output_path)], capture_output=True,
                                    cwd=path, timeout=10)
            if result.returncode:
                detail = (result.stderr or result.stdout)[:4096].decode('utf-8', errors='replace')
                return {'status': 'failed', 'phase': phase,
                        'message': f'run exit {result.returncode}: {detail}'}
            if result.stdout != b'AIL environment\n':
                return {'status': 'failed', 'phase': phase,
                        'message': 'stdout mismatch: expected AIL environment followed by LF; actual '
                        + repr(result.stdout[:4096])}
            if result.stderr:
                return {'status': 'failed', 'phase': phase,
                        'message': 'unexpected stderr: '
                        + result.stderr[:4096].decode('utf-8', errors='replace')}
    except subprocess.TimeoutExpired as error:
        detail = (error.stderr or b'')[:4096]
        if isinstance(detail, bytes):
            detail = detail.decode('utf-8', errors='replace')
        return {'status': 'failed', 'phase': phase,
                'message': f'{phase} timed out after {error.timeout} seconds: {detail}'}
    except OSError as error:
        return {'status': 'failed', 'phase': phase, 'message': str(error)[:4096]}
    return {'status': 'passed', 'phase': 'run',
            'message': 'Representative SDK compile/runtime check passed'}


def _source_interface(tree, symbols=(), types_used=False):
    """Declared signatures only; absent annotations remain unknown, never inferred."""
    def annotation(node):
        if node is None:
            return None
        text = ast.unparse(node)
        if text.startswith('__ail_checked_'):
            text = text[len('__ail_checked_'):]
            if text.endswith('__'):
                text = text[:-2]
        return 'list[float]' if text == 'flist' else text

    def function(node):
        positional = [*node.args.posonlyargs, *node.args.args]
        defaults = [None] * (len(positional) - len(node.args.defaults)) + node.args.defaults
        parameters = [dict(name=arg.arg, type=annotation(arg.annotation),
                           kind='positional_only' if i < len(node.args.posonlyargs) else 'positional',
                           default=ast.unparse(default) if default is not None else None)
                      for i, (arg, default) in enumerate(zip(positional, defaults))]
        for arg, kind, default in [
                *((arg, 'keyword_only', default) for arg, default in
                  zip(node.args.kwonlyargs, node.args.kw_defaults)),
                *((arg, kind, None) for arg, kind in
                  ((node.args.vararg, 'variadic'), (node.args.kwarg, 'variadic_keyword')) if arg)]:
            parameters.append(dict(name=arg.arg, type=annotation(arg.annotation), kind=kind,
                                   default=ast.unparse(default) if default is not None else None))
        return dict(name=node.name, parameters=parameters, returns=annotation(node.returns))

    structs = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            constructor = next((fn for fn in node.body if isinstance(fn, ast.FunctionDef)
                                and fn.name == '__init__'), None)
            parameters = {} if constructor is None else {arg.arg: arg.annotation for arg in constructor.args.args[1:]}
            fields = {} if constructor is None else {
                stmt.targets[0].attr: annotation(parameters.get(stmt.value.id)) if isinstance(stmt.value, ast.Name) else None
                for stmt in constructor.body if isinstance(stmt, ast.Assign)}
            structs.append(dict(name=node.name,
                                constructor_parameters=[] if constructor is None else function(constructor)['parameters'][1:],
                                fields=[dict(name=name, type=kind) for name, kind in fields.items()],
                                methods=[function(fn) for fn in node.body
                                         if isinstance(fn, ast.FunctionDef) and fn.name != '__init__']))
    functions = [function(node) for node in tree.body if isinstance(node, ast.FunctionDef)]
    if symbols:
        missing = set(symbols) - {item['name'] for item in functions}
        if missing:
            raise ValueError('unknown interface function: ' + ', '.join(sorted(missing)))
        functions = [item for item in functions if item['name'] in symbols]
    result = dict(scope='loaded_sources', types='declared_annotations', functions=functions, structs=structs)
    if types_used:
        by_name = {item['name']: item for item in structs}
        needed = set()
        pending = [kind for item in functions for kind in
                   [item['returns'], *(param['type'] for param in item['parameters'])]]
        unknown = False
        while pending:
            kind = pending.pop()
            if kind is None:
                unknown = True
                break
            try:
                nodes = list(ast.walk(ast.parse(kind, mode='eval')))
                names = {node.id for node in nodes if isinstance(node, ast.Name)}
                builtins = {'int','float','bool','str','bytes','bytearray','binaryfile','tcpsocket','exception','void','list','dict','tuple','Callable'}
                if (names - builtins - set(by_name) or any(
                        not isinstance(node, (ast.Expression, ast.Name, ast.Load, ast.Subscript, ast.Tuple, ast.List))
                        and not (isinstance(node, ast.Constant) and node.value is None) for node in nodes)):
                    unknown = True
                    break
            except SyntaxError:
                unknown = True
                break
            for name in names.intersection(by_name).difference(needed):
                needed.add(name)
                item = by_name[name]
                pending.extend(field['type'] for field in item['fields'])
                pending.extend(param['type'] for param in item['constructor_parameters'])
                for method in item['methods']:
                    pending.append(method['returns'])
                    pending.extend(param['type'] for index, param in enumerate(method['parameters'])
                                   if index != 0 or param['name'] != 'self')
        result['struct_selection'] = 'all_when_unknown' if unknown else 'reachable_declared_types'
        if not unknown:
            result['structs'] = [item for item in structs if item['name'] in needed]
    return result

def _check_repair_context(args, report, source, original, snapshots):
    """Bind a repair body only to the bytes used by this source check."""
    unavailable = lambda reason: dict(status='unavailable', reason=reason)
    if report['status'] == 'passed':
        return dict(status='not_needed')
    if args.module or args.object:
        return unavailable('explicit_module_or_object')
    diagnostic = report['diagnostics'][0]
    if diagnostic['code'] not in ('type', 'contract'):
        return unavailable('unsupported_diagnostic')
    if not diagnostic['function'] or not diagnostic['path']:
        return unavailable('missing_function_location')
    # Membership precedes any access to a diagnostic path.
    target = next((path for path in snapshots if str(path) == diagnostic['path']), None)
    if target is None:
        return unavailable('source_not_loaded')
    try:
        data = snapshots[target]
        syntax = ('ail' if detect(data.decode('utf8')) else 'python') if args.syntax == 'auto' else args.syntax
        if syntax != 'ail':
            return unavailable('python_source')
        def unchanged():
            return snapshots.get(source) == original and all(
                path.read_bytes() == data for path, data in snapshots.items())
        if not unchanged():
            return unavailable('source_changed')
        from ail_source_context import context
        result = context(data, diagnostic['function'], include_body=True,
                         source_path=target, module_paths=args.module_path, resolve_imports=True)
        if not unchanged():
            return unavailable('source_changed')
        checked_hashes = {str(path): hashlib.sha256(data).hexdigest() for path, data in snapshots.items()}
        if any(checked_hashes.get(path) != digest for path, digest in result['dependency_sha256'].items()):
            return unavailable('source_dependencies_changed')
        result['source_path'] = str(target)
        return result
    except (OSError, UnicodeError, SyntaxError, ValueError, RuntimeError, ImportError, KeyError) as error:
        return unavailable('context_collection_failed: ' + str(error))

def _slow_patterns(text, source_map):
    """Advisory `file:line: slow: ...` lines (ail_slow_patterns); never raises, never fails a build."""
    if os.environ.get('AIL_NO_SLOW_HINTS') or not source_map:
        return []
    try:
        import ail_slow_patterns
        found = ail_slow_patterns.scan(text, source_map, skip_prefixes=(str(ROOT / 'language_examples'),))
        return [ail_slow_patterns.format_warning(item, Path.cwd()) for item in found]
    except Exception:
        return []


_FALLBACK_NOTE = 'note: built on the general path'
_FALLBACK_HINT = '; run with --strict to see why'
_LINE_MARKER = re.compile(r'^ail-source-line: (\d+)\r?\n?', re.M)


def _split_line_marker(text):
    """(text without the compiler's `ail-source-line: N` line, N or None)."""
    found = _LINE_MARKER.search(text or '')
    return (_LINE_MARKER.sub('', text), int(found.group(1))) if found else (text, None)


def _marker_where(source_map, line):
    """`path:line:col` of the combined-source line the compiler named, or None."""
    position = source_map.get(line) if line is not None else None
    if not position:
        return None
    where = _relpath(position[0])
    where = position[0] if where.startswith('..') else where
    return '%s:%s:%s' % (where, position[1], position[2]) if len(position) > 2 and position[2] is not None else '%s:%s' % (where, position[1])


def _fallback_notes(args, source, stderr, locate=True, source_map=None):
    """The compile-time `note: file:line:col: built on the general path (about 20x slower)
    because <typed refusal>; run with --strict ...` lines the compiler printed, positioned like a refusal. Advisory only:
    stdout and the exit status are never affected; AIL_QUIET_FALLBACK=1 silences it."""
    if os.environ.get('AIL_QUIET_FALLBACK') or not stderr or _FALLBACK_NOTE not in stderr:
        return []
    notes = []
    stderr, marked = _split_line_marker(stderr)
    try:
        python = _python_source(args, source.read_bytes())
        for line in stderr.splitlines():
            if not line.startswith(_FALLBACK_NOTE):
                continue
            hint = _FALLBACK_HINT if line.endswith(_FALLBACK_HINT) else ''
            line = line[:len(line) - len(hint)]       # the position lookup reads the refusal text alone
            if python:
                line = python_wording(line)
            if str(source) in _MERGED_ENTRIES:
                line = ail_modules.unmangle(line, _MERGED_ENTRIES[str(source)].names)
            if locate:
                reason = line.split(' because ', 1)[-1]
                located = _locate_refusal(args, source, reason)
                if located != reason and located.endswith(reason):
                    where = located[:-len(reason)].rstrip(': ')
                else:
                    where = _marker_where(source_map or {}, marked)
                if where:
                    line = 'note: %s: built on the general path%s' % (where, line[len(_FALLBACK_NOTE):])
            notes.append(line + hint)
    except Exception:
        return notes
    return notes


def _strict_requested(args):
    """`--strict` or AIL_STRICT=1: build on the typed path or refuse (never the general path)."""
    return bool(getattr(args, 'strict', False)) or str(os.environ.get('AIL_STRICT', '')).strip().lower() not in (
        '', '0', 'off', 'no', 'false')


def _strict_blockers(args, source, objects, python):
    """(blockers, incomplete): every typed-path blocker of the program, with file:line:col, ranked."""
    origins, source_map = {}, {}
    text, _, _ = _load_sources(source, args.module, args.syntax, module_paths=args.module_path,
                               origins=origins, source_map=source_map, local_imports=True)
    names = _MERGED_ENTRIES[str(source)].names if str(source) in _MERGED_ENTRIES else None

    def reword(message):
        if names:
            message = ail_modules.unmangle(message, names)
        return python_wording(message) if python else message

    compiler_path = str(ROOT / 'python/pkg-v12')
    previous_path, previous_bytecode = sys.path[:], sys.dont_write_bytecode
    saved_surface = os.environ.get('AIL_SURFACE')
    try:
        sys.dont_write_bytecode = True
        sys.path.insert(0, compiler_path)
        from pyfunc import Unsupported, to_c
        import strictmode
        external = None
        if objects:
            from module_object import load_objects
            external = load_objects(list(objects))
        if python:
            os.environ['AIL_SURFACE'] = 'python'
        else:
            os.environ.pop('AIL_SURFACE', None)
        blockers, incomplete = strictmode.collect(text, to_c, Unsupported, external=external, reword=reword)
    finally:
        if saved_surface is None:
            os.environ.pop('AIL_SURFACE', None)
        else:
            os.environ['AIL_SURFACE'] = saved_surface
        sys.path[:] = previous_path
        sys.dont_write_bytecode = previous_bytecode
    for blocker in blockers:
        position = source_map.get(blocker.get('line'))
        origin = origins.get(blocker.get('function'))
        path = line = column = None
        if position is not None:
            path, line = position[0], position[1]
            column = position[2] if len(position) > 2 and position[2] is not None else blocker.get('column')
        elif origin is not None:
            path, line, column = origin[0], origin[1], origin[2]
        else:
            path, line, column = str(source), blocker.get('line'), blocker.get('column')
        shown = _relpath(path)
        blocker['path'] = path if shown.startswith('..') else shown
        blocker['line'], blocker['column'] = line, column
        if names:
            for key in ('function', 'statement', 'construct', 'why', 'write_instead'):
                if isinstance(blocker.get(key), str):
                    blocker[key] = ail_modules.unmangle(blocker[key], names)
            blocker['blocks_functions'] = [ail_modules.unmangle(name, names) for name in blocker['blocks_functions']]
    return blockers, incomplete


def _strict_text(blockers, incomplete):
    count = len(blockers)
    lines = ['strict: %d typed-path blocker%s; nothing was built (ranked by the code each one keeps off the typed path)'
             % (count, '' if count == 1 else 's')]
    for blocker in blockers:
        where = blocker['path'] + (':%s' % blocker['line'] if blocker.get('line') else '') + (
            ':%s' % blocker['column'] if blocker.get('line') and blocker.get('column') else '')
        lines.append('')
        lines.append('%d. %s  blocks %d line%s%s' % (
            blocker['rank'], where, blocker['blocks_lines'], '' if blocker['blocks_lines'] == 1 else 's',
            ' (' + ', '.join(blocker['blocks_functions']) + ')' if blocker['blocks_functions'] else ''))
        if blocker.get('statement'):
            lines.append('   code:          ' + blocker['statement'])
        lines.append('   construct:     ' + blocker['construct'])
        lines.append('   why not typed: ' + blocker['why'])
        lines.append('   write instead: ' + blocker['write_instead'])
    if incomplete:
        lines += ['', 'strict: the list may be incomplete (%s)' % incomplete]
    return '\n'.join(lines) + '\n'


def _strict_json(args, source, blockers, incomplete):
    return json.dumps(dict(
        schema='ail.strict/1', status='refused', strict=True, command=args.command, source=str(source),
        exit_code=3, blocker_count=len(blockers), incomplete=incomplete,
        blockers=[{key: blocker.get(key) for key in (
            'rank', 'path', 'line', 'column', 'function', 'statement', 'construct', 'why', 'write_instead',
            'blocks_lines', 'blocks_functions', 'message')} for blocker in blockers]), ensure_ascii=False)


def _strict_refusal(args, source, objects, first_message):
    """Print every blocker (text on stderr, or `ail.strict/1` JSON on stdout with --json); the exit status
    is the refusal's, 3. None when the blockers cannot be collected (the caller prints the first refusal)."""
    try:
        python = _python_source(args, source.read_bytes())
        blockers, incomplete = _strict_blockers(args, source, objects, python)
    except Exception:
        if os.environ.get('AIL_STRICT_DEBUG'):
            import traceback
            traceback.print_exc()
        return None
    if not blockers:
        return None
    if getattr(args, 'json', False):
        print(_strict_json(args, source, blockers, incomplete))
    else:
        sys.stderr.write(_strict_text(blockers, incomplete))
    return 3


def _source_check(args):
    """Read-only strict type/code-generation check; no C build or runtime proof."""
    report = dict(schema='ail.check/1', status='failed', stage='loader', diagnostics=[],
                  link_verified=False, runtime_verified=False, source_sha256=None,
                  checked_functions=None)
    source = args.source
    origins = {}
    source_map = {}
    stage = 'loader'
    dependency = False
    repair_context = getattr(args, 'repair_context', False)
    snapshots = {} if repair_context or getattr(args, 'contracts', False) else None
    original = None
    try:
        if getattr(args, 'api_module', None) is not None:
            name = args.api_module
            if not re.fullmatch(r'[A-Za-z_]\w*', name):
                raise ValueError('invalid bundled API module name: ' + name)
            try:
                manifest = json.loads((ROOT / 'MANIFEST.json').read_text(encoding='utf8'))
            except (json.JSONDecodeError, UnicodeError) as error:
                raise ValueError('invalid bundled API manifest: ' + str(error)) from error
            selected = manifest.get('sdk_files') if isinstance(manifest, dict) else None
            if not isinstance(selected, list) or not all(isinstance(path, str) for path in selected):
                raise ValueError('invalid bundled API manifest: sdk_files must be a list of paths')
            if 'language_examples/' + name + '.ail' not in selected:
                raise ValueError('unknown bundled API module: ' + name)
        source = source.resolve()
        original = source.read_bytes()
        report['source_sha256'] = hashlib.sha256(original).hexdigest()
        if getattr(args, 'contracts', False) and not args.interface:
            raise ValueError('--contracts requires --interface')
        if args.types_used and (not args.interface or not args.symbol):
            raise ValueError('--types-used requires --interface and --symbol')
        if args.symbol and not args.interface:
            raise ValueError('--symbol requires --interface')
        ffi = _ffi_session(args)
        text, _, _ = _load_sources(source, args.module, args.syntax,
                                  module_only=args.library, module_paths=args.module_path, origins=origins, source_map=source_map,
                                  local_imports=True, ffi=ffi,
                                  **({'source_bytes': snapshots} if snapshots is not None else {}))
        check_objects = list(args.object)
        if getattr(args, 'ffi', False):
            report['ffi'] = ffi.listing()
        if ffi.decls:
            dependency = True
            check_objects.append(ffi.build(ROOT / 'ail_chatgpt.py'))
            os.environ['AIL_FFI_SYMBOLS'] = ' '.join(ffi.symbols())
            dependency = False
        report['checked_functions'] = sum(isinstance(node, ast.FunctionDef)
                                          for node in ast.walk(ast.parse(text)))
        compiler_path = str(ROOT / 'python/pkg-v12')
        previous_path = sys.path[:]
        previous_bytecode = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            sys.path.insert(0, compiler_path)
            from pyfunc import Unsupported, to_c
            external = None
            if check_objects:
                dependency = True
                from module_object import load_objects
                external = load_objects(check_objects)
                dependency = False
            stage = 'type'
            saved_surface = os.environ.get('AIL_SURFACE')
            if _python_source(args, original):
                os.environ['AIL_SURFACE'] = 'python'
            else:
                os.environ.pop('AIL_SURFACE', None)
            try:
                to_c(text, strict=True, info={'_want_units': True, '_checked_arrays': True},
                     library=args.library, external=external)
            finally:
                if saved_surface is None:
                    os.environ.pop('AIL_SURFACE', None)
                else:
                    os.environ['AIL_SURFACE'] = saved_surface
        finally:
            sys.path[:] = previous_path
            sys.dont_write_bytecode = previous_bytecode
        if args.interface:
            report['interface'] = _source_interface(ast.parse(text), args.symbol, args.types_used)
            from ail_source_context import language_rules
            report['language_rules'] = language_rules()
            if getattr(args, 'contracts', False):
                from ail_api_contracts import build_contracts
                report['contracts'] = build_contracts(ast.parse(text), report['interface'], source_sha256=report['source_sha256'], snapshots=snapshots, imports_resolved=True)
                if snapshots.get(source) != original or any(path.read_bytes() != data for path, data in snapshots.items()):
                    raise ValueError('source or dependency changed while collecting API contracts')
        report.update(status='passed', stage='type')
        slow = _slow_patterns(text, source_map)
        if slow:
            report['slow_patterns'] = slow
        status = 0
    except (OSError, UnicodeError, SyntaxError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
        # Unsupported inherits the compiler's error type; inspect it without a fallback.
        status = 2 if dependency or isinstance(error, (OSError, ImportError, subprocess.SubprocessError)) else 1
        message = error.refusal[3] if isinstance(error, ail_modules.ModuleRefusal) else str(error)
        if str(source) in _MERGED_ENTRIES:
            message = ail_modules.unmangle(message, _MERGED_ENTRIES[str(source)].names)
        if _python_source(args, original):
            message = python_wording(message)
        configuration = ('each --module-path', 'each --module must', 'AIL module not found:', '--symbol requires --interface', '--contracts requires --interface', '--types-used requires --interface and --symbol', 'unknown interface function:', 'invalid bundled API module name:', 'unknown bundled API module:', 'invalid bundled API manifest:')
        if any(marker in message for marker in configuration):
            status = 2
        code = 'dependency' if dependency or 'AIL module not found:' in message else (
            'io' if isinstance(error, OSError) else 'configuration' if status == 2 else
            'syntax' if stage == 'loader' else 'type')
        path = None
        line = column = None
        if stage == 'loader':
            if isinstance(error, OSError):
                path = str(source)
            current = error
            while current is not None:
                for prefix in ('AIL source ', 'AIL module '):
                    if str(current).startswith(prefix) and ': ' in str(current):
                        candidate = str(current)[len(prefix):].split(': ', 1)[0]
                        if Path(candidate).is_file():
                            path = candidate
                if isinstance(current, SyntaxErrorAIL):
                    line = getattr(current, 'lineno', None)
                    column = getattr(current, 'offset', None)
                elif isinstance(current, SyntaxError) and current.filename:
                    candidate = Path(current.filename)
                    if candidate.is_file():
                        try:
                            original = candidate.read_text(encoding='utf8')
                            syntax = ('ail' if detect(original) else 'python') if args.syntax == 'auto' else args.syntax
                        except (OSError, UnicodeError):
                            syntax = None
                        if syntax == 'python':
                            path, line, column = str(candidate), current.lineno, current.offset
                if getattr(current, 'source_position', None) is not None:
                    path, line, column = current.source_position
                current = current.__cause__ or current.__context__
        function = getattr(error, 'source_function', None)
        location_kind = 'source' if line is not None else None
        origin = origins.get(function)
        if origin is not None:
            path, line, column, function = origin
            location_kind = 'function_declaration'
        position = source_map.get(getattr(error, 'source_line', None))
        if position is not None:
            path, line, column = position
            location_kind = 'source_statement'
        code = getattr(error, 'diagnostic_code', code)
        report.update(stage=stage, diagnostics=[dict(code=code, message=message,
                                                    path=path, line=line, column=column, function=function,
                                                    location_kind=location_kind)])
        if hasattr(error, 'type_details'):
            details = dict(error.type_details)
            callee_origin = origins.get(details.get('callee'))
            if callee_origin is not None:
                details['callee'] = callee_origin[3]
            report['diagnostics'][0]['type_details'] = details
        if hasattr(error, 'repair_hint'):
            report['diagnostics'][0]['repair_hint'] = error.repair_hint
    if repair_context:
        report['repair_context'] = _check_repair_context(args, report, source, original, snapshots)
    print(json.dumps(report, ensure_ascii=False))
    return status

def _surface_env(args, source, env=None):
    """The environment for a compiler run: `AIL_SURFACE=python` for a def-syntax entry, which makes
    the compiler refuse list/dict/set sharing it would otherwise copy (pkg-v12/aliasrefuse.py)."""
    env = dict(os.environ if env is None else env)
    try:
        python = (Path(source).suffix.lower() in ('.ail', '.py')
                  and (Path(source).suffix.lower() == '.py' or _python_source(args, Path(source).read_bytes())))
    except OSError:
        python = False
    if python:
        env['AIL_SURFACE'] = 'python'
    else:
        env.pop('AIL_SURFACE', None)
    return env


def _python_source(args, data):
    """Whether the entry source is written in the Python syntax (refusals are respelled for it)."""
    if getattr(args, 'syntax', 'auto') != 'auto':
        return args.syntax == 'python'
    try:
        text = data.decode('utf8') if isinstance(data, bytes) else data
        return text is not None and not ail_sexpr.detect(text) and not detect(text)
    except Exception:
        return False


def _python_notes(message, notes, source):
    """A Python-syntax refusal followed by what the Python front end left as written."""
    message = message.rstrip('\n')
    if "'math' is read before it is assigned" in message:
        # a math name the Python front end could not map was left as written; say so, not this
        for entries in notes.values():
            named = [text.split(';')[0] for _, text in entries if text.startswith('math.')]
            if named:
                message = message.replace("'math' is read before it is assigned", named[0] + " (see the note below)")
                break
    for entries in notes.values():
        # `import time` followed by a time name the front end could not map: name that, not the import
        named = [text.split(';')[0] for _, text in entries if re.match(r'(time|string|os|operator)\.', text)]
        found = re.search(r"import of '(time|string|os|operator)' is not available[^\n]*\n  write instead: [^\n]*", message)
        if named and found and any(text.startswith(found.group(1) + '.') for _, text in entries):
            message = message.replace(found.group(0), next(n for n in named if n.startswith(found.group(1) + '.'))
                                      + ' (see the note below)')
            break
    # library batch 4 (csv, datetime, ...): the import is refused because a use was not built; say which
    found = re.search(r"import of '(csv|datetime|decimal|fractions|unicodedata|statistics|textwrap|enum|string)'; [^\n]*?by hand",
                      message)
    if found:
        for entries in notes.values():
            named = [text.split(';')[0] for _, text in entries if found.group(1) in text.split(':')[0]]
            if named:
                message = message.replace(found.group(0), named[0] + ' (see the note below)')
                break
    shown = _relpath(source)
    shown = str(source) if shown.startswith('..') else shown
    for path, entries in notes.items():
        where = shown if Path(path) == source else path
        for line, text in entries:
            message += '\nnote: %s:%d: %s' % (where, line, text)
    return message + '\n'


def _text_position(source, message, function=None):
    """(line, column) of the construct a refusal names, found by reading the source text. This is
    the fallback for refusals the type check cannot map to a statement (a signature, an
    annotation): the position of the def, parameter or annotation the message quotes."""
    try:
        lines = Path(source).read_text(encoding='utf8').splitlines()
    except (OSError, UnicodeError):
        return None
    head = message.split('\n', 1)[0]
    head = re.sub(r'^not in the subset: ', '', head)

    def find(pattern, only_defs=False):
        compiled = re.compile(pattern)
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith(('#', '//')):
                continue
            if only_defs and not re.match(r'\s*(?:def|fn)\s', line):
                continue
            found = compiled.search(line)
            if found:
                return number, found.start() + 1
        return None

    def name_in(pattern):
        found = re.search(pattern, head)
        return re.escape(found.group(1)) if found else None

    named_line = re.match(r'line (\d+): ', head)
    if named_line and int(named_line[1]) <= len(lines):
        at = int(named_line[1])
        return at, len(lines[at - 1]) - len(lines[at - 1].lstrip()) + 1
    nullable = name_in(r'^(\w+) \| None')
    if nullable:
        return find(r'\b%s\s*\|\s*None|Optional\s*\[\s*%s' % (nullable, nullable))
    if 'must take plain positional arguments' in head:
        return find(r'(?:def|fn)\s+\w+\s*\([^)]*(?:\*|,\s*/|/\s*[,)])', only_defs=True)
    default_for = re.search(r"^(\w+)\(\): the default for '(\w+)'", head)
    if default_for:
        at = find(r'(?:def|fn)\s+%s\s*\([^)]*\b%s\b[^)]*=' % default_for.groups(), only_defs=True)
        if at is not None:
            line = lines[at[0] - 1]
            named = re.search(r'\b%s\b\s*[:=]' % re.escape(default_for[2]), line[line.find('('):])
            return (at[0], line.find('(') + named.start() + 1) if named else at
        return find(r'(?:def|fn)\s+%s\b' % default_for[1], only_defs=True)
    annotation = re.search(r'unsupported local annotation (.+?)\.?$', head)
    if annotation:
        squeezed = re.sub(r'\s+', '', annotation[1].rstrip('.'))
        for number, line in enumerate(lines, 1):
            at = re.sub(r'\s+', '', line).find(squeezed)
            if at >= 0:
                return number, max(1, len(line) - len(line.lstrip()) + 1)
        return None
    parameter = name_in(r"^'(\w+)' is annotated")
    if parameter:
        return find(r'\b%s\s*:' % parameter, only_defs=True)
    if head.startswith('a function with no parameters'):
        return find(r'(?:def|fn)\s+\w+\s*\(\s*\)', only_defs=True)
    callee = re.search(r'^(\w+)\(\):', head)
    if callee:
        return find(r'(?:def|fn)\s+%s\b' % callee[1], only_defs=True)
    if function:
        return find(r'(?:def|fn)\s+%s\b' % re.escape(function.split('.')[-1]), only_defs=True)
    return None


def _construct_position(source, message):
    """The position of a construct whose refusal names it, read off the source text. It overrides
    the check's statement mapping, which can point at a later use (the call that reaches a class)."""
    try:
        lines = Path(source).read_text(encoding='utf8').splitlines()
    except (OSError, UnicodeError):
        return None
    head = re.sub(r'^not in the subset: ', '', message.split('\n', 1)[0])
    patterns = ((r"^inheritance \(class '(\w+)'", r'class\s+%s\b'),
                (r"^class '(\w+)' has no __init__", r'class\s+%s\b'),
                (r"^a decorator on class '(\w+)'", r'class\s+%s\b'),
                (r"^a decorator on \w+\.(\w+)", r'def\s+%s\b'),
                (r"^dunder method \w+\.(\w+)", r'def\s+%s\b'),
                (r"^(nonlocal) in a nested function", r'\b%s\b'),
                (r"^(global) in a nested function", r'\b%s\b'))
    for refusal, wanted in patterns:
        found = re.match(refusal, head)
        if found:
            compiled = re.compile(wanted % re.escape(found[1]))
            for number, line in enumerate(lines, 1):
                at = compiled.search(line)
                if at and not line.lstrip().startswith(('#', '//')):
                    return number, at.start() + 1
    return None


def _locate_refusal(args, source, message):
    """Prefix a compile refusal with path:line:col, found by the type check (which maps statements)."""
    command = [sys.executable, '-B', str(Path(__file__).resolve()), 'check', str(source),
               '--syntax', args.syntax]
    for path in args.module_path:
        command += ['-I', str(path)]
    for path in args.module:
        command += ['--module', str(path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        diagnostic = json.loads(result.stdout)['diagnostics'][0]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError):
        diagnostic = None
    text = (diagnostic or {}).get('message') or ''
    if diagnostic is not None and (not text or text not in message):
        diagnostic = None
    where = (diagnostic or {}).get('path') or str(source)
    relative = _relpath(where)
    if not relative.startswith('..'):
        where = relative
    merged = str(Path(source).resolve()) in _MERGED_ENTRIES      # the entry text alone does not hold the code
    named = None if merged else _construct_position(source, message)
    if named is not None:
        return '%s:%d:%d: %s' % (where, named[0], named[1], message)
    if diagnostic is not None and diagnostic.get('line') is not None:
        where += ':%d' % diagnostic['line']
        if diagnostic.get('column') is not None:
            where += ':%d' % diagnostic['column']
        return '%s: %s' % (where, message)
    # the check could not map the refusal to a statement: read the position off the source text
    position = None if merged else _text_position(source, message, (diagnostic or {}).get('function'))
    if position is None:
        if diagnostic is not None and diagnostic.get('function'):
            return '%s (in %s): %s' % (where, diagnostic['function'], message)
        return message
    return '%s:%d:%d: %s' % (where, position[0], position[1], message)


def _compile_freestanding(args, parser, native_build):
    """`compile --freestanding`: one module to C or an object with no runtime and no libc (python/pkg-v12/freestanding.py)."""
    if args.module or args.object or args.separate or args.static or args.target or args.module_path:
        parser.error('--freestanding builds one module alone; drop --module, --object, --separate, --static, --target and -I')
    source = args.source.resolve()
    output = Path(os.path.abspath(args.output))
    if source.suffix.lower() != '.py' or not source.is_file():
        parser.error('--freestanding takes an existing Python-syntax .py module')
    if output.suffix not in ('.c', '.o'):
        parser.error('--freestanding output must end in .c (C source) or .o (object)')
    header = output.with_suffix('.h')
    for path in (output, header):
        if path.exists() or path.is_symlink():
            parser.error('output already exists: %s' % path)
    if source in (output, header) or not output.parent.is_dir():
        parser.error('output must differ from source, in an existing directory')
    sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
    import freestanding
    try:
        report = freestanding.build(source, output, target='i386' if args.m32 else 'x86_64')
    except freestanding.Refusal as error:
        return native_build.emit(args, {}, 3, 'type', error.text(_relpath(source)))
    except SyntaxError as error:
        return native_build.emit(args, {}, 3, 'syntax', 'AIL freestanding: %s:%s: %s' % (_relpath(source), error.lineno, error.msg))
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        return native_build.emit(args, {}, 2, 'backend', 'AIL freestanding: %s' % error)
    return native_build.emit(args, report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check_cmd = sub.add_parser('check', help='strict source/type check without a C build; exit 0 passed, 1 source error, 2 configuration/I/O/dependency')
    check_cmd.add_argument('source', type=Path)
    check_cmd.add_argument('--syntax', choices=('auto', 'ail', 'python'), default='auto')
    check_cmd.add_argument('-I', '--module-path', action='append', type=Path, default=[])
    check_cmd.add_argument('--module', action='append', type=Path, default=[])
    check_cmd.add_argument('--object', action='append', type=Path, default=[], help='typed object metadata; may query compiler identity, never builds or links')
    check_cmd.add_argument('--library', action='store_true')
    check_cmd.add_argument('--ffi', action='store_true', help='list the C FFI declarations (@extern stubs) of the program')
    check_cmd.add_argument('--no-ffi', action='store_true', help='refuse a program that declares C FFI functions')
    check_cmd.add_argument('--repair-context', action='store_true', help='include SHA-bound failing AIL function body and declared import/API context')
    check_cmd.add_argument('--interface', action='store_true', help='include checked source declarations without function bodies; absent types are null')
    check_cmd.add_argument('--symbol', action='append', default=[], help='select top-level function declarations with --interface; repeatable; struct declarations retained')
    api_cmd = sub.add_parser('api', help='check a bundled source module and return its typed API without compiling C')
    api_cmd.add_argument('api_module', help='bundled module name, without path or .ail suffix')
    builtin_cmd = sub.add_parser('api-builtin', help='query intrinsic signatures and declared ownership without building or running code')
    builtin_cmd.add_argument('symbol', nargs='?', help='builtin name or typed receiver.method; omitted lists the available inventory')
    api_cmd.add_argument('--object', action='append', type=Path, default=[], help='typed object metadata; may query compiler identity, never builds or links')
    api_cmd.add_argument('--symbol', action='append', default=[], help='select top-level functions; structs retained')
    check_cmd.add_argument('--types-used', action='store_true', help='retain structs reachable through selected declared types; unknown types retain all')
    api_cmd.add_argument('--types-used', action='store_true', help='retain structs needed by selected declared types; requires --symbol')
    check_cmd.add_argument('--contracts', action='store_true', help='include declared ownership and conservative static call contracts; requires --interface')
    api_cmd.add_argument('--contracts', action='store_true', help='include declared ownership and conservative static call contracts')
    context_cmd = sub.add_parser('context', help='read a local function declaration and call candidates without type checking')
    context_cmd.add_argument('source', type=Path)
    context_cmd.add_argument('--symbol', required=True)
    context_cmd.add_argument('--include-body', action='store_true')
    context_cmd.add_argument('--contracts', action='store_true', help='include syntax-derived ownership/call contracts without binding or runtime proof')
    context_cmd.add_argument('--compact', action='store_true', help='encode context parameter rows in reversible compact JSON')
    context_cmd.add_argument('--resolve-imports', action='store_true')
    context_cmd.add_argument('-I', '--module-path', action='append', type=Path, default=[])
    edit_cmd = sub.add_parser('edit', help='replace function bodies in a new source/type-checked candidate')
    edit_cmd.add_argument('source', type=Path)
    edit_cmd.add_argument('--symbol')
    edit_cmd.add_argument('--base-sha256', required=True)
    body_input = edit_cmd.add_mutually_exclusive_group(required=True)
    body_input.add_argument('--body', type=Path)
    body_input.add_argument('--body-text', help='replacement body directly; no temporary body file needed')
    body_input.add_argument('--edits-text', help='JSON array of symbol/body strings, checked together')
    edit_cmd.add_argument('--context', type=Path, help='bind the resolved source context and dependency hashes')
    edit_cmd.add_argument('-o', '--output', required=True, type=Path)
    edit_cmd.add_argument('--library', action='store_true')
    edit_cmd.add_argument('-I', '--module-path', action='append', type=Path, default=[])
    edit_cmd.add_argument('--module', action='append', type=Path, default=[])
    edit_cmd.add_argument('--object', action='append', type=Path, default=[])
    doctor_cmd = sub.add_parser('doctor')
    doctor_cmd.add_argument('--check', action='store_true',
                            help='compile and run a representative SDK program to check the C/OS runtime')
    sub.add_parser('integrity')
    sdk_cmd = sub.add_parser('export-sdk', help='copy the verified language compiler and standard sources to a new SDK directory')
    sdk_cmd.add_argument('-o', '--output', type=Path, required=True)
    http_cmd = sub.add_parser('compare-http', help='compare local read-only HTTP commands with exact output checks')
    http_cmd.add_argument('manifest', type=Path)
    http_cmd.add_argument('-o', '--output', required=True, type=Path)
    snapshot_cmd = sub.add_parser('snapshot-http', help='copy declared HTTP inputs for relocated comparison')
    snapshot_cmd.add_argument('manifest', type=Path)
    snapshot_cmd.add_argument('-o', '--output', required=True, type=Path)
    snapshot_cmd.add_argument('--compare', action='store_true',
        help='compare the copied inputs and save result.json inside the new snapshot')
    build_http_cmd = sub.add_parser('build-http', help='build a declared HTTP candidate beside a frozen reference')
    build_http_cmd.add_argument('manifest', type=Path)
    build_http_cmd.add_argument('--recipe', required=True, type=Path)
    build_http_cmd.add_argument('-o', '--output', required=True, type=Path)
    build_http_cmd.add_argument('--compare', action='store_true')
    compile_cmd = sub.add_parser('compile', help='compile AIL source to a standalone executable')
    compile_cmd.add_argument('source', type=Path)
    compile_cmd.add_argument('-o', '--output', required=True, type=Path)
    compile_cmd.add_argument('--module', action='append', type=Path, default=[],
        help='additional .ail file containing functions and literal numeric constants')
    compile_cmd.add_argument('--no-ffi', action='store_true', help='refuse a program that declares C FFI functions (@extern)')
    compile_cmd.add_argument('--debug', action='store_true',
                             help='build for gdb: -g -O0, #line directives back to the .py/.ail source (same code generator as a release build), and an uncaught exception names the last statement run (stderr is then not CPython-compatible)')
    compile_cmd.add_argument('--link', action='append', default=[], metavar='LIB',
                             help='link this library as well, like link("LIB") in the source (a name, or a path to a shared library); repeatable')
    compile_cmd.add_argument('--separate', action='store_true',
        help='compile each typed source into a C object, then link the objects')
    compile_cmd.add_argument('--object', action='append', type=Path, default=[],
        help='link an existing typed .o and its adjacent .o.json without its source')
    compile_cmd.add_argument('--syntax', choices=('auto', 'python', 'ail'), default='auto',
        help='source syntax; auto detects fn/const/use/struct declarations, ail uses brace-delimited blocks')
    compile_cmd.add_argument('--strict', action='store_true',
        help='build on the typed path or refuse, listing every blocker with a rewrite (also AIL_STRICT=1); '
             'with --json the blockers are printed as ail.strict/1 JSON')
    compile_cmd.add_argument('--static', action='store_true',
        help='link the C library statically (larger binary that runs on any Linux); default is dynamic')
    compile_cmd.add_argument('--lib', metavar='NAME',
        help='build the @export functions of the source as a C library: -o DIR receives lib<NAME>.so, '
             'lib<NAME>.a and <NAME>.h (error codes, NAME_last_error(), NAME_free(); see NATIVE_LIBRARIES.md)')
    compile_cmd.add_argument('--target', choices=sorted(ZIG_TARGETS),
        help='cross-compile with zig cc for another OS/CPU (needs zig: $AIL_ZIG, PATH, or ~/tools/zig/zig)')
    compile_cmd.add_argument('--freestanding', action='store_true',
        help='compile one Python-syntax module to C (-o x.c) or an object (-o x.o) that needs no runtime and no libc, '
             'plus a header x.h; see docs/design/FREESTANDING.md')
    compile_cmd.add_argument('--m32', action='store_true',
        help='with --freestanding: target 32-bit x86 (usize is 32 bits, gcc -m32); see docs/design/FREESTANDING.md')
    object_cmd = sub.add_parser('compile-module', help='compile typed functions, scalar structs and scalar constants to a reusable object')
    object_cmd.add_argument('source', type=Path)
    object_cmd.add_argument('-o', '--output', required=True, type=Path)
    object_cmd.add_argument('--syntax', choices=('auto', 'python', 'ail'), default='auto')
    object_cmd.add_argument('--object', action='append', type=Path, default=[],
        help='typed dependency objects; entry linking requires their full object closure')
    object_cmd.add_argument('--c-api-name', help='build a dependency dedicated to this C library name')
    library_cmd = sub.add_parser('compile-library', help='build a C callable library with owned results and error returns')
    library_cmd.add_argument('source', type=Path)
    library_cmd.add_argument('--name', required=True)
    library_cmd.add_argument('-o', '--output', required=True, type=Path)
    library_cmd.add_argument('--syntax', choices=('auto', 'python', 'ail'), default='auto')
    library_cmd.add_argument('--module', action='append', type=Path, default=[],
        help='additional typed .ail source, combined with transitive use dependencies')
    library_cmd.add_argument('--export', action='append',
        help='public function name; repeat to select the C API (default: all functions)')
    library_cmd.add_argument('--object', action='append', type=Path, default=[],
        help='complete closure of objects built with --c-api-name matching --name')
    for command in (compile_cmd, object_cmd, library_cmd):
        command.add_argument('-I', '--module-path', action='append', type=Path, default=[],
            help='use module search directory; local, then -I in order, then bundled standard modules')
    c_cmd = sub.add_parser('compile-c', help='compile trusted C functions to a typed reusable object')
    c_cmd.add_argument('source', type=Path)
    c_cmd.add_argument('--interface', required=True, type=Path)
    c_cmd.add_argument('-o', '--output', required=True, type=Path)
    c_cmd.add_argument('--c-api-name', help='build a dependency dedicated to this C library name')
    for command in (compile_cmd, object_cmd, library_cmd, c_cmd):
        command.add_argument('--json', action='store_true', help='return structured build diagnostics without running the generated program')
        command.add_argument('--debug-dir', type=Path, help='keep native diagnostic reports and generated sources in a new directory')
    for command in (compile_cmd, object_cmd, library_cmd, c_cmd):
        command.add_argument('--no-cache', action='store_true', help='do not read or write the build cache (same as AIL_NO_CACHE=1)')
    cache_cmd = sub.add_parser('cache', help='build cache in $AIL_CACHE (default ~/.cache/ail): stats, path or clear')
    cache_cmd.add_argument('action', choices=('stats', 'path', 'clear'))
    smoke = sub.add_parser('selftest'); smoke.add_argument('--out', required=True)
    build = sub.add_parser('build'); build.add_argument('--project', required=True)
    build.add_argument('--out', required=True); build.add_argument('--candidate-patch')
    build.add_argument('--mode', choices=['original','balanced','speed','memory'], default='original')
    args = parser.parse_args(argv)
    if getattr(args, 'no_cache', False):
        os.environ['AIL_NO_CACHE'] = '1'
    if getattr(args, 'static', False):
        if sys.platform == 'darwin' and not getattr(args, 'target', None):
            parser.error('--static is not supported on macOS: Apple ships no static C library, so the '
                         'linker fails on crt0.o (build a static Linux binary with --target linux, or '
                         'drop --static)')
        os.environ['AIL_STATIC'] = '1'
    if getattr(args, 'target', None):
        os.environ['PIPE_CC'] = _zig_compiler(args.target)
        if args.target == 'windows':
            os.environ['AIL_TARGET_OS'] = 'windows'
        os.environ['AIL_TARGET'] = args.target      # os.path takes the flavour of the target (filelib.target_windows)
    if args.command in ('compile', 'compile-module', 'compile-library', 'compile-c'):
        import ail_native_build as native_build
        if native_build.enabled(args):
            native_build.prepare(args, parser)
    if args.command == 'edit':
        if args.edits_text is None and args.symbol is None:
            parser.error('--symbol is required for a single body edit')
        if args.edits_text is not None and args.symbol is not None:
            parser.error('--symbol cannot be combined with --edits-text')
    if args.command == 'context':
        from ail_source_context import context
        try:
            if args.source.suffix.lower()!='.ail':
                raise ValueError('context source must use .ail suffix')
            source=args.source.resolve(strict=True)
            report=context(source.read_bytes(),args.symbol,args.include_body,
                           source_path=source,module_paths=args.module_path,resolve_imports=args.resolve_imports,contracts=args.contracts)
            report['source']=str(source)
            if args.compact:
                from ail_source_context import compact_context
                report=compact_context(report)
            print(json.dumps(report,ensure_ascii=False,**({'separators':(',', ':')} if args.compact else {})));return 0
        except (OSError,UnicodeError,SyntaxError,ValueError) as error:
            print(json.dumps(dict(schema='ail.context/1',status='failed',error=str(error)),ensure_ascii=False));return 2
    if args.command == 'edit':
        from ail_source_edit import run
        status, report = run(args, _source_check)
        print(json.dumps(report, ensure_ascii=False))
        return status
    if args.command == 'api':
        args.source = ROOT / 'language_examples' / (args.api_module + '.ail')
        args.module = args.module_path = []
        args.syntax, args.library, args.interface = 'auto', True, True
        return _source_check(args)
    if args.command == 'check':
        return _source_check(args)
    if args.command == 'api-builtin':
        from ail_builtin_api import query
        try:
            report = query(args.symbol, source_root=ROOT)
        except (OSError, UnicodeError, SyntaxError, ValueError) as error:
            print(json.dumps(dict(schema='ail.builtin_api/1', status='failed', error=str(error)), ensure_ascii=False))
            return 2
        print(json.dumps(report, ensure_ascii=False))
        return 0
    manifest_path = ROOT/'MANIFEST.json'
    if ((ROOT/'SDK_README_JA.md').is_file() and manifest_path.is_file()
            and json.loads(manifest_path.read_text(encoding='utf8')).get('kind') == 'ail_language_sdk'):
        supported = ('doctor', 'integrity', 'cache', 'compile', 'compile-module', 'compile-library', 'compile-c', 'export-sdk', 'check', 'api', 'api-builtin', 'edit', 'context')
        if args.command not in supported:
            parser.error('this language SDK supports: ' + ', '.join(supported))
    if args.command == 'cache':
        module = _BUILDCACHE[0] if _BUILDCACHE else None
        if module is None:
            _build_cache()
            module = _BUILDCACHE[0]
        if module is None:
            print('AIL ERROR: build cache module unavailable', file=sys.stderr)
            return 2
        if args.action == 'path':
            print(module.root())
        elif args.action == 'stats':
            print(json.dumps(module.stats(), indent=2))
        else:
            print(json.dumps({'removed': module.clear(), 'path': str(module.root())}))
        return 0
    if args.command == 'export-sdk':
        from ail_sdk import export_sdk
        try:
            result = export_sdk(ROOT, args.output)
        except (OSError, ValueError, RuntimeError) as error:
            parser.error(str(error))
        print(json.dumps({key: value for key, value in result.items() if key != 'sha256'}, ensure_ascii=False))
        return 0
    if args.command == 'doctor':
        requested = os.environ.get('PIPE_CC') or next(filter(None, (shutil.which(name)
            for name in ('cc', 'clang', 'gcc'))), None)
        resolved = shutil.which(requested) if requested else None
        report = {'python':sys.version, 'platform':platform.platform(),
            'python_supported':sys.version_info >= (3,10),
            'c_compiler':resolved, 'c_compiler_configured':requested,
            'c_compiler_available':resolved is not None,
            'source_root':str(ROOT), 'external_model_required_for_selftest':False}
        if args.check:
            report['build_check'] = _doctor_build_check(report)
        print(json.dumps(report, indent=2))
        return 2 if not report['python_supported'] or args.check and report['build_check']['status'] != 'passed' else 0
    if args.command == 'integrity':
        manifest = json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf8'))
        pins = manifest['sha256']
        is_sdk = manifest.get('kind') == 'ail_language_sdk'
        # A source checkout's sha256 map also holds pins of files from earlier archive layouts that
        # no longer exist; only the shipped sdk_files and the pins of files present are checked
        # (the same set ail_check and tools/update_manifest.py --check verify).
        names = list(pins) if is_sdk else [n for n in pins if (ROOT/n).is_file() or n in manifest.get('sdk_files', [])]
        bad = [name for name in names
               if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=pins[name]]
        report = {'status':'verified' if not bad else 'failed','checked':len(names),'mismatches':bad}
        if not is_sdk:
            report['historical_pins_skipped'] = len(pins) - len(names)
        print(json.dumps(report,indent=2))
        return 1 if bad else 0
    if args.command == 'compare-http':
        from ail_http_compare import main as compare_http
        return compare_http([str(args.manifest), '-o', str(args.output)])
    if args.command == 'snapshot-http':
        from ail_http_snapshot import main as snapshot_http
        return snapshot_http([str(args.manifest), '-o', str(args.output)]
                             + (['--compare'] if args.compare else []))
    if args.command == 'build-http':
        from ail_http_build import main as build_http
        return build_http([str(args.manifest), '--recipe', str(args.recipe), '-o', str(args.output)]
                          + (['--compare'] if args.compare else []))
    if args.command in ('compile-module', 'compile-c'):
        if sys.version_info < (3, 10):
            parser.error('AIL compilation requires Python 3.10 or newer')
        source, output = args.source.resolve(), Path(os.path.abspath(args.output))
        metadata = Path(str(output) + '.json')
        is_c = args.command == 'compile-c'
        if source.suffix.lower() != ('.c' if is_c else '.ail') or not source.is_file():
            parser.error('source must be an existing ' + ('.c' if is_c else '.ail') + ' file')
        if is_c and (not args.interface.is_file() or args.interface.resolve() in (output, metadata)):
            parser.error('interface must be an existing file distinct from outputs')
        if output.exists() or metadata.exists() or output.is_symlink() or metadata.is_symlink():
            parser.error('object output or metadata already exists')
        if not output.parent.is_dir() or source in (output, metadata):
            parser.error('object output requires an existing directory and must differ from source')
        try:
            text = source.read_text(encoding='utf8') if is_c else _load_sources(
                source, source_syntax=args.syntax, module_only=True, module_paths=args.module_path, **native_build.loading(args))[0]
        except (OSError, UnicodeError, SyntaxError, ValueError) as error:
            parser.error(str(error))
        with tempfile.TemporaryDirectory(prefix='ail-module-') as directory:
            prepared, target = Path(directory) / ('module.c' if is_c else 'module.py'), Path(directory) / 'module.o'
            prepared.write_text(text, encoding='utf8')
            command = [sys.executable, '-B', str(ROOT/'python/pkg-v12/pyc.py'),
                       '--file', str(source if is_c else prepared), str(target), '--strict']
            command += ['--compile-c', str(args.interface.resolve())] if is_c else ['--compile-object']
            if args.c_api_name is not None:
                command += ['--c-api-name', args.c_api_name]
            if is_c and _build_cache(args) is not None and not native_build.enabled(args):
                command.append('--cache')
            for object_path in ([] if is_c else args.object):
                command += ['--object', str(object_path.resolve())]
            cache = _build_cache(args) if is_c and not native_build.enabled(args) else None
            key = _compile_c_key(cache, args, source, text) if cache is not None else None
            payload = cache.get('fe', key) if key else None
            result = None
            if payload is not None:
                try:
                    meta, blob = cache.unpack(payload)
                    target.write_bytes(blob)
                    Path(str(target) + '.json').write_text(meta['metadata'], encoding='utf8')
                    result = subprocess.CompletedProcess(command, 0, '', '')
                except (OSError, ValueError, KeyError):
                    result = None
            if result is None:
                result = native_build.invoke(args, command, directory,
                                        capture_output=True, text=True, timeout=180,
                                        env=_hand_over_toolchain(cache, _surface_env(args, source)))
                if key and result.returncode == 0 and target.is_file() and Path(str(target) + '.json').is_file():
                    cache.put('fe', key, cache.pack({'metadata': Path(str(target) + '.json').read_text(encoding='utf8')},
                                                    target.read_bytes()))
            if result.returncode:
                return native_build.emit(args, {}, result.returncode, message=result.stderr or result.stdout)
            created = metadata_created = False
            try:
                with output.open('xb') as destination:
                    created = True
                    destination.write(target.read_bytes())
                with metadata.open('xb') as destination:
                    metadata_created = True
                    destination.write(Path(str(target) + '.json').read_bytes())
            except Exception:
                if metadata_created:
                    metadata.unlink()
                if created:
                    output.unlink()
                raise
        return native_build.emit(args, {'output': str(output), 'metadata': str(metadata),
                          'sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
    if args.command == 'compile' and args.m32 and not args.freestanding:
        parser.error('--m32 is part of --freestanding (a 32-bit x86 kernel target)')
    if args.command == 'compile' and args.freestanding:
        return _compile_freestanding(args, parser, native_build)
    if args.command in ('compile', 'compile-library'):
        export_lib = args.command == 'compile' and getattr(args, 'lib', None)
        library = args.command == 'compile-library' or bool(export_lib)
        lowered = {}
        objects = getattr(args, 'object', [])
        separate = getattr(args, 'separate', False)
        source = args.source.resolve()
        output = Path(os.path.abspath(args.output))
        if sys.version_info < (3, 10):
            parser.error('AIL compilation requires Python 3.10 or newer')
        if source.suffix.lower() not in ('.ail', '.py') or not source.is_file():
            parser.error('source must be an existing .ail or .py file')
        notes = {}
        loading = native_build.loading(args) or {'source_map': {}}
        ffi = None if library else _ffi_session(args)
        if export_lib and (separate or args.target):
            parser.error('--lib cannot be combined with --separate or --target')

        def lower_exports(text):
            import ail_export
            lowered_text, lowered['manifest'] = ail_export.lower(text)
            return lowered_text
        try:
            source_text, contracts, unit_map = _load_sources(
                source, args.module, args.syntax, module_only=library, separate=separate,
                module_paths=args.module_path, notes=notes, local_imports=not library, ffi=ffi,
                prelower=lower_exports if export_lib else None, **loading)
        except (OSError, UnicodeError, SyntaxError, ValueError) as error:
            _refuse_load(error)
        if export_lib:
            if not output.is_dir():
                parser.error('--lib output must be an existing directory (-o DIR)')
            with tempfile.TemporaryDirectory(prefix='ail-export-source-') as temporary:
                prepared, manifest = Path(temporary) / 'library.py', Path(temporary) / 'exports.json'
                prepared.write_text(source_text, encoding='utf8')
                manifest.write_text(json.dumps(lowered['manifest']), encoding='utf8')
                result = native_build.invoke(args, [sys.executable, '-B', str(ROOT/'python/pkg-v12/c_export.py'),
                                       str(prepared), '--manifest', str(manifest), '--name', args.lib, '-o', str(output)],
                                      temporary, timeout=240)
                if not native_build.enabled(args):
                    return result.returncode
                if result.returncode:
                    return native_build.emit(args, {}, result.returncode, message=result.stderr or result.stdout)
                return native_build.emit(args, json.loads(result.stdout))
        ffi_objects, ffi_env = [], {}
        if ffi is not None:
            ffi.extra_libs = list(getattr(args, 'link', None) or [])      # --link LIB is link("LIB") for the whole program
        if ffi is not None and not ffi.decls and ffi.extra_libs:
            ffi_env = {'AIL_FFI_LINK': shlex.join(ffi._link_args())}
        if ffi is not None and ffi.decls:
            try:
                ffi_objects = [ffi.build(ROOT / 'ail_chatgpt.py')]
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                return native_build.emit(args, {}, 2, 'ffi', str(error))
            ffi_env = {'AIL_FFI_LINK': shlex.join(ffi.link_args), 'AIL_FFI_SYMBOLS': ' '.join(ffi.symbols())}
        if library:
            if output.exists() or output.is_symlink() or not output.parent.is_dir():
                parser.error('library output requires a new directory in an existing parent')
            with tempfile.TemporaryDirectory(prefix='ail-library-source-') as temporary:
                prepared = Path(temporary) / 'library.py'
                prepared.write_text(source_text, encoding='utf8')
                result = native_build.invoke(args, [sys.executable, '-B', str(ROOT/'python/pkg-v12/c_api.py'),
                                       str(prepared), '--name', args.name, '-o', str(output),
                                       *(arg for name in args.export or [] for arg in ('--export', name)),
                                       *(arg for obj in objects for arg in ('--object', str(obj.resolve())))],
                                      temporary, timeout=240)
                if not native_build.enabled(args):
                    return result.returncode
                if result.returncode:
                    return native_build.emit(args, {}, result.returncode, message=result.stderr or result.stdout)
                return native_build.emit(args, json.loads(result.stdout))
        if output.exists() or output.is_symlink() or (sys.platform == 'win32' and
                (Path(str(output) + '.exe').exists() or Path(str(output) + '.exe').is_symlink())):
            parser.error('output already exists')
        if source == output or source == Path(str(output) + '.exe'):
            parser.error('output must differ from source')
        if not output.parent.is_dir():
            parser.error('output directory does not exist')
        if separate and not unit_map:
            parser.error('--separate needs a module with at least one function')
        with tempfile.TemporaryDirectory(prefix='ailc-') as tmp:
            target = Path(tmp) / 'program'
            build_source = Path(tmp) / 'combined.ail'
            build_source.write_text(source_text, encoding='utf-8')
            strict = _strict_requested(args)
            command = [sys.executable, '-B', str(ROOT/'python/pkg-v12/pyc.py'),
                       '--file', str(build_source), str(target), '--strict']
            for object_path in [*objects, *ffi_objects]:
                command += ['--object', str(object_path.resolve())]
            if separate:
                unit_map_path = Path(tmp) / 'units.json'
                unit_map_path.write_text(json.dumps(unit_map), encoding='utf-8')
                command += ['--link-units', str(unit_map_path)]
            debug = bool(getattr(args, 'debug', False))
            link = bool(getattr(args, 'link', None)) and ffi is not None
            debug_env = {}
            if debug:
                line_map = Path(tmp) / 'lines.json'
                line_map.write_text(json.dumps({str(key): [value[0], value[1]]
                                                for key, value in loading['source_map'].items()}), encoding='utf-8')
                debug_env = {'AIL_DEBUG': '1', 'AIL_LINE_MAP': str(line_map)}
            environment = _surface_env(args, source, {**os.environ, 'AIL_REPORT_SOURCE_LINE': '1',
                                                **({'AIL_NO_GENERAL': '1'} if contracts or strict else {}), **ffi_env, **debug_env})
            cache = None if separate or getattr(args, 'target', None) else _build_cache(args)
            frontend = None
            if cache is not None and not native_build.enabled(args):
                # A finished build is a function of the merged source, the objects it links, the
                # compiler sources, the toolchain and the environment; nothing else is read.
                frontend = cache.frontend_key(
                    ROOT / 'python/pkg-v12', 'compile', source_text,
                    *[part for object_path in [*objects, *ffi_objects] for part in (
                        hashlib.sha256(object_path.read_bytes()).hexdigest(),
                        hashlib.sha256(Path(str(object_path) + '.json').read_bytes()).hexdigest()
                        if Path(str(object_path) + '.json').is_file() else '-')],
                    environment.get('AIL_SURFACE', ''), environment.get('AIL_NO_GENERAL', ''),
                    *[hashlib.sha256(Path(a).read_bytes()).hexdigest() for a in shlex.split(ffi_env.get('AIL_FFI_LINK', '')) if Path(a).is_file()],
                    *(['link', ffi_env['AIL_FFI_LINK']] if link else []),
                    *(['debug', hashlib.sha256(line_map.read_bytes()).hexdigest()] if debug else []))
            _hand_over_toolchain(cache, environment)
            result = None
            payload = cache.get('fe', frontend) if frontend else None
            if payload is not None:
                try:
                    meta, blob = cache.unpack(payload)
                    cache.write_output(target, blob, True)
                    result = subprocess.CompletedProcess(command, 0, '', meta['stderr'])
                except (OSError, ValueError, KeyError):
                    result = None
            if result is None:
                if cache is not None and not native_build.enabled(args):
                    command.append('--cache')
                result = native_build.invoke(args, command, tmp, capture_output=True, text=True,
                    timeout=660, env=environment)
                if frontend and result.returncode == 0 and target.is_file():
                    cache.put('fe', frontend, cache.pack({'stderr': result.stderr or ''}, target.read_bytes()))
            if result.returncode == 3 and strict and not separate and not ffi_objects:
                refused = _strict_refusal(args, source, objects, result.stderr or result.stdout)
                if refused is not None:
                    return refused
            if result.returncode:
                message, marked = _split_line_marker(result.stderr or result.stdout)
                python = result.returncode == 3 and _python_source(args, source.read_bytes())
                if python:
                    message = python_wording(message)
                if str(source) in _MERGED_ENTRIES:
                    message = ail_modules.unmangle(message, _MERGED_ENTRIES[str(source)].names)
                if result.returncode == 3 and not args.json and not objects and not separate:
                    located = _locate_refusal(args, source, message)
                    where = _marker_where(loading['source_map'], marked) if located == message else None
                    message = '%s: %s' % (where, message) if where else located
                if python and any(notes.values()):
                    message = _python_notes(message, notes, source)
                return native_build.emit(args, {}, result.returncode, message=message)
            built = target if target.is_file() else Path(str(target) + '.exe')
            if not built.is_file():
                return native_build.emit(args, {}, 2, 'artifact', 'AIL ERROR: compiler returned success without an executable')
            if sys.platform == 'win32' and not output.suffix:
                output = Path(str(output) + '.exe')
            created = False
            try:
                with output.open('xb') as dst, built.open('rb') as src:
                    created = True
                    shutil.copyfileobj(src, dst)
                shutil.copymode(built, output)
            except Exception:
                if created:
                    output.unlink()
                raise
            for line in [] if args.json else _slow_patterns(source_text, loading['source_map']):
                print(line, file=sys.stderr)
            if not args.json:
                for line in _fallback_notes(args, source, result.stderr, locate=not objects and not separate,
                                             source_map=loading['source_map']):
                    print(line, file=sys.stderr)
                # typedpar.py: why a thread / executor / pool use runs under the general path's lock
                for path, entries in notes.items():
                    for line, text in entries:
                        if text.startswith('not run in parallel'):
                            print('note: %s:%d: %s' % (_relpath(Path(path)) if Path(path) == source else path,
                                                       line, text), file=sys.stderr)
            return native_build.emit(args, {'output': str(output), 'bytes': output.stat().st_size,
                'sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
    project = ROOT/'example' if args.command == 'selftest' else Path(args.project).resolve()
    output = Path(args.out).resolve()
    command = [sys.executable,'-B',str(ROOT/'workflow/vibe/vibe.py'),'build',
        '--project',str(project),'--selector',str(ROOT/'workflow/selector'),
        '--out',str(output),'--mode',getattr(args,'mode','original'),'--budget-seconds','600']
    if getattr(args,'candidate_patch',None):
        if args.mode == 'original':
            parser.error('candidate-patch requires a measured mode')
        command += ['--candidate-patch',str(Path(args.candidate_patch).resolve())]
    subprocess.run(command,check=True,timeout=660)
    config = json.loads((project/'project.json').read_text(encoding='utf8'))
    checker = config.get('specification_checker')
    if checker:
        subprocess.run([sys.executable,'-B',str(ROOT/'workflow/vibe/vibe.py'),'verify',
            str(output/'app/result.json'),'--checker',str(project/checker)],check=True,timeout=180)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
