"""`ail explain FILE`: the typed-path status of every function in one program, and why.

The build itself is the oracle. This module runs the compiler twice: once in the default mode
(the program's status: `typed` when nothing fell back, `general` when the general path built it,
`refused` when it did not build), and once with `--strict --json` (the typed-path blockers).

A blocker names the function its construct sits in. When the blocker list stops early (it can:
some refusals carry no position), the function-level ones are hidden -- replaced by a typed stub
with the same signature -- and the build is run again, at most ten times, to find the rest. A
function that no round named is `typed` only when the last round built on the typed path;
otherwise it is `unknown`. The first strict build runs on the source file itself, so imports
resolve relative to it; only the hiding rounds use a transient copy beside it, removed
afterwards. The source file is only read.

Ordinary Python 3.12 with annotations. Runnable as `python3 -m ail_lang.explain FILE [--json]`.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = 'ail.explain/1'
MAX_HIDE_ROUNDS = 10
COMPILER = Path('AIL_CURRENT') / 'ail_chatgpt.py'

# Environment a caller may set to tune one build. The status line must describe the default
# build, so these are removed from the compiler's environment: otherwise a caller's
# AIL_QUIET_FALLBACK=1 hides the fallback note and the program would be called `typed`.
_TUNING_VARIABLES = ('AIL_QUIET_FALLBACK', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL')


# ------------------------------------------------------------------ the compiler


def find_compiler(explicit=None):
    """The `ail_chatgpt.py` to build with: --compiler, AIL_COMPILER, then an ancestor of this file."""
    for candidate in (explicit, os.environ.get('AIL_COMPILER')):
        if candidate:
            path = Path(candidate).resolve()
            if path.is_file():
                return path
            raise SystemExit('ail explain: no compiler at %s' % path)
    here = Path(__file__).resolve()
    for parent in here.parents:
        path = parent / COMPILER
        if path.is_file():
            return path
    raise SystemExit('ail explain: cannot find %s; pass --compiler' % COMPILER)


def _build(compiler, source, workdir, strict=False, tag='out'):
    """Run one build; (returncode, stdout, stderr) as text. Never writes outside `workdir`."""
    target = Path(workdir) / tag
    command = [sys.executable, '-B', str(compiler), 'compile', str(source), '-o', str(target)]
    if strict:
        command += ['--strict', '--json']
    environment = {key: value for key, value in os.environ.items() if key not in _TUNING_VARIABLES}
    try:
        done = subprocess.run(command, capture_output=True, text=True, env=environment)
    except OSError as error:
        raise SystemExit('ail explain: cannot run %s: %s' % (compiler, error))
    return done.returncode, done.stdout, done.stderr


def _strict_payload(compiler, source, workdir, tag='strict'):
    code, out, err = _build(compiler, source, workdir, strict=True, tag=tag)
    try:
        payload = json.loads(out)
    except (ValueError, TypeError):
        return {'status': 'unparseable', 'blockers': [], 'message': (err or out).strip()[:400]}
    if not isinstance(payload, dict):
        return {'status': 'unparseable', 'blockers': [], 'message': str(payload)[:400]}
    payload.setdefault('blockers', [])
    return payload


def _refusal_message(stderr, stdout):
    text = (stderr or '').strip() or (stdout or '').strip()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('{'):
            continue
        return line
    return text.splitlines()[0].strip() if text else 'the build refused this program'


# ------------------------------------------------------------------ source model

# (kind, ...) -> dummy literal a typed stub can return for that annotation.
_SCALARS = {
    'int': '0',
    'float': '0.0',
    'bool': 'False',
    'str': '""',
    'bytes': 'b""',
}


def _dummy(annotation, classes=frozenset()):
    """A C-source literal of the annotated type, or None when this module cannot make one."""
    if annotation is None:
        return None
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode='eval').body
        except SyntaxError:
            return None
    text = ast.unparse(annotation).strip()
    if text in ('None', 'NoneType'):
        return None
    if '|' in text:
        for part in text.split('|'):
            part = part.strip()
            if part not in ('None', 'NoneType'):
                return _dummy(ast.parse(part, mode='eval').body, classes)
        return None
    if text in _SCALARS:
        return _SCALARS[text]
    node = annotation
    if isinstance(node, ast.Subscript):
        base = ast.unparse(node.value).strip()
        if base == 'list':
            return '[]'
        if base == 'dict':
            key, value = _subscript_parts(node)
            kd, vd = _dummy(key, classes), _dummy(value, classes)
            if kd is None or vd is None:
                return None
            key_text = ast.unparse(key).strip()
            key_literal = '"a"' if key_text == 'str' else kd
            return '{%s: %s}' % (key_literal, vd)
    if isinstance(node, ast.Name) and node.id in classes:
        return '%s(0)' % node.id
    return None


def _subscript_parts(node):
    sl = node.slice
    if isinstance(sl, ast.Tuple) and len(sl.elts) == 2:
        return sl.elts[0], sl.elts[1]
    return ast.Constant(None), sl


class Function:
    """One def that a blocker can name, with the name the compiler mangles it to."""

    def __init__(self, node, key, mangled, parent, kind):
        self.node = node
        self.key = key             # the name a reader knows: `f` or `Cls.method`
        self.mangled = mangled     # `Cls__method`, `outer__inner` (a `__N` suffix is ignored)
        self.parent = parent       # the top-level Function this def belongs to (None for top-level)
        self.kind = kind           # 'function' | 'method' | 'nested'

    @property
    def owner(self):
        return self.parent or self

    @property
    def line(self):
        return self.node.lineno

    def stub_lines(self, classes=frozenset()):
        """The def's whole span, replaced by a typed stub that keeps its signature and decorators."""
        node = self.node
        indent = ' ' * node.col_offset
        args = ast.unparse(node.args)
        ret = (' -> ' + ast.unparse(node.returns)) if node.returns is not None else ''
        dummy = _dummy(node.returns, classes)
        if dummy is not None:
            body = indent + '    return ' + dummy
        else:
            body = indent + '    print(0)'
        decorators = [indent + '@' + ast.unparse(deco) for deco in node.decorator_list]
        first = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
        last = (node.end_lineno or node.lineno) - 1
        return first, last, decorators + [indent + 'def %s(%s)%s:' % (node.name, args, ret), body]


def _functions(tree):
    """Every def in source order: top-level, methods, and functions nested in either."""
    ordered = []

    def walk(body, mangled_prefix, key_prefix, parent, in_class=None):
        for node in body:
            if isinstance(node, ast.ClassDef):
                walk(node.body, mangled_prefix + node.name + '__', node.name + '.', parent,
                     in_class=node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if in_class is not None:
                    key, kind = in_class + '.' + node.name, 'method'
                elif key_prefix:
                    key, kind = key_prefix + node.name, 'nested'
                else:
                    key, kind = node.name, 'function'
                prefix = mangled_prefix
                if in_class is not None:
                    decorators = {ast.unparse(deco).strip() for deco in node.decorator_list}
                    if 'staticmethod' in decorators:
                        prefix += 'static__'
                    elif 'classmethod' in decorators:
                        prefix += 'classmethod__'
                record = Function(node, key, prefix + node.name, parent, kind)
                ordered.append(record)
                walk(node.body, record.mangled + '__', key + '.', record.owner)

    walk(tree.body, '', '', None)
    return ordered


def _lookup(functions, name):
    """The def a blocker's (possibly mangled, possibly `__N`-suffixed) function name means."""
    if not isinstance(name, str) or not name:
        return None
    wanted = name
    if wanted not in {fn.mangled for fn in functions}:
        stripped = wanted.rsplit('__', 1)
        if len(stripped) == 2 and stripped[1].isdigit():
            wanted = stripped[0]
    for fn in functions:
        if fn.mangled == wanted:
            return fn
    return None


def _source_with_stubs(text, hidden, classes=frozenset()):
    """`text` with each hidden def replaced by its stub; line numbers of the rest are kept."""
    lines = text.split('\n')
    for record in sorted(hidden, key=lambda fn: fn.node.lineno, reverse=True):
        first, last, stub = record.stub_lines(classes)
        lines[first:last + 1] = stub
    return '\n'.join(lines)


def _hiding_copy(source, workdir):
    """A path for the stub copy. A sibling of the source keeps its imports resolvable; a temporary
    directory is the fallback when the source's directory is not writable."""
    try:
        descriptor, name = tempfile.mkstemp(
            prefix='.ail-explain-', suffix=source.suffix, dir=str(source.parent))
    except OSError:
        return Path(workdir) / 'program.py'
    os.close(descriptor)
    return Path(name)


# ------------------------------------------------------------------ the analysis


def _blocker_fields(blocker):
    def text(key):
        value = blocker.get(key)
        return value if isinstance(value, str) else None
    return {
        'construct': text('construct'),
        'why': text('why'),
        'write_instead': text('write_instead'),
        'statement': text('statement'),
        'line': blocker.get('line'),
        'column': blocker.get('column'),
    }


def explain(path, compiler):
    """The report dict for one source file."""
    source = Path(path)
    try:
        text = source.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as error:
        raise SystemExit('ail explain: cannot read %s: %s' % (path, error))
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    functions = _functions(tree) if tree is not None else []
    classes = ({node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
               if tree is not None else set())

    report = {
        'schema': SCHEMA,
        'source': str(source),
        'status': 'refused',
        'message': None,
        'functions': [],
    }
    with tempfile.TemporaryDirectory(prefix='ail-explain-') as workdir:
        # the program's status: what the default build did with it
        code, out, err = _build(compiler, source, workdir, strict=False, tag='default')
        if code == 0:
            report['status'] = 'general' if 'built on the general path' in (err or '') else 'typed'
        else:
            report['status'] = 'refused'
            report['message'] = _refusal_message(err, out)

        # per function: the blocker list, then hiding rounds when it stopped early
        seen = {}          # top-level function/method key -> explanation
        hidden = []        # defs replaced by stubs in the next copy
        hidden_keys = set()
        last_pass = False
        # Round 0 builds the file itself: AIL resolves imports relative to the source, so a copy in a
        # temporary directory would lose every sibling module. Only the hiding rounds use a copy.
        analysis_source = source
        copy = None
        try:
            for round_number in range(MAX_HIDE_ROUNDS + 1):
                payload = _strict_payload(compiler, analysis_source, workdir, tag='strict%d' % round_number)
                if payload.get('status') == 'passed':
                    last_pass = True
                    break
                progress = False
                for blocker in payload.get('blockers') or []:
                    record = _lookup(functions, blocker.get('function'))
                    if record is None:
                        continue
                    owner = record.owner
                    if owner.key not in seen:
                        seen[owner.key] = {
                            'after': [fn.key for fn in hidden] or None,
                            **_blocker_fields(blocker),
                        }
                        progress = True
                    if record.key not in hidden_keys:
                        hidden.append(record)
                        hidden_keys.add(record.key)
                        progress = True
                if not progress or round_number >= MAX_HIDE_ROUNDS:
                    break
                if copy is None:
                    copy = _hiding_copy(source, workdir)
                copy.write_text(_source_with_stubs(text, hidden, classes), encoding='utf-8')
                analysis_source = copy
        finally:
            if copy is not None:
                try:
                    copy.unlink()
                except OSError:
                    pass

    for record in functions:
        if record.kind == 'nested':
            continue
        entry = {
            'name': record.key,
            'line': record.line,
            'status': 'general' if record.key in seen else ('typed' if last_pass else 'unknown'),
        }
        explanation = seen.get(record.key)
        if explanation is not None:
            entry.update(explanation)
        entry['kind'] = record.kind
        report['functions'].append(entry)
    return report


# ------------------------------------------------------------------ output


def format_text(report):
    """One line per function, in source order, after the program's status line."""
    name = Path(report['source']).name
    if report['status'] == 'refused':
        first = '%s  refused  %s' % (name, report['message'])
    else:
        first = '%s  %s' % (name, report['status'])
    lines = [first]
    for entry in report['functions']:
        line = '%s:%d %s  %s' % (name, entry['line'], entry['name'], entry['status'])
        if entry['status'] == 'general':
            reason = entry.get('construct') or entry.get('why') or 'a construct the typed path refuses'
            line += '  ' + reason
            why = entry.get('why')
            if why and why != reason and reason not in why:
                line += '; ' + why
            if entry.get('write_instead'):
                line += '; write instead: ' + entry['write_instead']
            if entry.get('after'):
                line += '  (found after hiding %s)' % ', '.join(entry['after'])
        lines.append(line)
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='ail explain',
        description='the typed-path status of every function in a program, and the reason')
    parser.add_argument('file', help='the Python/AIL source file')
    parser.add_argument('--json', action='store_true', help='print %s JSON' % SCHEMA)
    parser.add_argument('--compiler', help='the ail_chatgpt.py to build with')
    args = parser.parse_args(argv)
    compiler = find_compiler(args.compiler)
    report = explain(args.file, compiler)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(format_text(report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
