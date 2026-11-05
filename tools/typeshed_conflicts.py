#!/usr/bin/env python3
"""Compare the compiler's hand-written stdlib result types with the vendored typeshed table.

Read-only: this tool imports `unified`, `pyfunc`, `filelib`, `genlib` and `stubsigs` and never edits
the compiler.  Every entry of the named tables is checked.  An entry whose callee has no vendored
signature (or whose signature returns `obj`) is counted as `stub_obj`; a concrete stub type that is
not one of the rule's result types is a `conflict`.

Usage:
    python3 tools/typeshed_conflicts.py [--markdown PATH]

One line per pair:  qualname rule_type stub_type source
Then:               checked N agree A conflict C stub_obj O
Then one line per conflict with the CPython 3.12 verdict of a typical call.
"""
import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PKG = REPO / 'AIL_CURRENT' / 'python' / 'pkg-v12'
sys.path.insert(0, str(PKG))

import stubsigs  # noqa: E402
import unified  # noqa: E402
import pyfunc  # noqa: E402
import filelib  # noqa: E402
import genlib  # noqa: E402

KIND = {'INT': 'int', 'FLT': 'float', 'STR': 'str', 'BYTES': 'bytes', 'BOOL': 'bool'}


def kind(value):
    return KIND.get(value, value)


def lookup(qualname):
    """stubsigs.lookup, following random.pyi's `name = _inst.name` aliases to Random."""
    entry = stubsigs.lookup(qualname)
    if entry is None and qualname.startswith('random.') and qualname.count('.') == 1:
        method = qualname.split('.', 1)[1]
        entry = stubsigs.lookup('random.Random.' + method)
        if entry is None:
            entry = stubsigs.lookup('_random.Random.' + method)
    return entry


# ---- unified._etype's builtin rules.  A set is a rule whose result depends on the arguments.
BUILTIN_RULES = [
    ('builtins.len', {'int'}, 'unified.py:2183'),
    ('builtins.ord', {'int'}, 'unified.py:2183'),
    ('builtins.int', {'int'}, 'unified.py:2185'),
    ('builtins.float', {'float'}, 'unified.py:2187'),
    ('builtins.bool', {'bool'}, 'unified.py:2189'),
    ('builtins.isinstance', {'bool'}, 'unified.py:2189'),
    ('builtins.callable', {'bool'}, 'unified.py:2189'),
    ('builtins.round', {'int'}, 'unified.py:2191'),
    ('builtins.abs', {'int', 'float'}, 'unified.py:2194'),
    ('builtins.min', {'int', 'float'}, 'unified.py:2197'),
    ('builtins.max', {'int', 'float'}, 'unified.py:2197'),
]

DRAWS_SOURCE = 'unified.py:1990'

# ---- pyfunc tables: internal name -> the vendored callee whose result the primitive carries, or None
# for an internal helper (a status / a serialised value with no stdlib result of its own).
CLOCK_MAP = {
    '_ail_time': 'time.time',
    '_ail_time_ns': 'time.time_ns',
    '_ail_sleep_ns': 'time.sleep',
    '_ail_local_offset': None,
    '_ail_local_isdst': None,
    '_ail_tz_name': None,
    '_ail_mktime': 'time.mktime',
}
SYSINFO_MAP = {
    '_ail_perf_counter': 'time.perf_counter',
    '_ail_perf_counter_ns': 'time.perf_counter_ns',
    '_ail_cpu_count': 'os.cpu_count',
}
RAND_MAP = {
    '_ail_rand_seed': 'random.seed',
    '_ail_rand_random': 'random.random',
    '_ail_rand_uniform': 'random.uniform',
    '_ail_rand_gauss': 'random.gauss',
    '_ail_rand_normalvariate': 'random.normalvariate',
    '_ail_rand_expovariate': 'random.expovariate',
    '_ail_rand_getrandbits': 'random.getrandbits',
    '_ail_rand_range': 'random.randrange',
    '_ail_rand_below_i': None,
    '_ail_rand_choice_index': None,
    '_ail_rand_setsize': None,
}

# ---- filelib.PRIMS (and PATHS): same convention.  The file/os primitives are the C bodies of the
# corresponding methods and functions in filelib_prelude.py.
FILE_PRIMS_MAP = {
    '_ail_f_open': 'builtins.open',
    '_ail_f_close': '_io._IOBase.close',
    '_ail_f_flush': '_io._IOBase.flush',
    '_ail_f_tread': '_io._TextIOBase.read',
    '_ail_f_treadline': '_io._TextIOBase.readline',
    '_ail_f_tnext': None,                      # iterator __next__; no vendored entry
    '_ail_f_twrite': '_io._TextIOBase.write',
    '_ail_f_bread': '_io._BufferedIOBase.read',
    '_ail_f_breadline': None,                  # no vendored entry
    '_ail_f_bnext': None,
    '_ail_f_bwrite': '_io._BufferedIOBase.write',
    '_ail_f_seek': '_io._IOBase.seek',
    '_ail_f_tell': '_io._IOBase.tell',
    '_ail_f_readable': '_io._IOBase.readable',
    '_ail_f_writable': '_io._IOBase.writable',
    '_ail_f_seekable': '_io._IOBase.seekable',
    '_ail_os_getcwd': 'os.getcwd',
    '_ail_os_chdir': 'os.chdir',
    '_ail_os_scandir': 'os.scandir',           # a serialised listing; the callee is os.listdir/os.scandir
    '_ail_os_kind': None,                      # the body of os.path.exists/isfile/isdir/islink
    '_ail_os_getsize': 'os.path.getsize',
    '_ail_os_mkdir': 'os.mkdir',
    '_ail_os_rmdir': 'os.rmdir',
    '_ail_os_unlink': 'os.unlink',
    '_ail_os_chmod': 'os.chmod',
    '_ail_os_rename': 'os.rename',
    '_ail_os_replace': 'os.replace',
    '_ail_os_getenv': 'os.getenv',
    '_ail_os_hasenv': None,
    '_ail_os_setenv': None,
    '_ail_os_unsetenv': None,
    '_ail_pp_staterr': None,
    '_ail_pp_readlink': 'os.readlink',
    '_ail_pp_home': None,
    '_ail_pp_repr': None,
    '_ail_ur_unquote': 'urllib.parse.unquote',
    '_ail_ur_repr': None,
    '_ail_hs_new': 'hashlib.new',
    '_ail_hs_hmac': 'hmac.new',
    '_ail_hs_pbkdf2': 'hashlib.pbkdf2_hmac',
    '_ail_hs_rand': 'secrets.token_bytes',
    '_ail_hs_b64e': 'base64.b64encode',
    '_ail_hs_b64d': 'base64.b64decode',
}

# ---- typical CPython 3.12 calls for the conflicts the mappings above produce.
PROBES = {
    'time.sleep': 'import time; v = time.sleep(0)',
    'time.mktime': 'import time; v = time.mktime((2020, 1, 1, 0, 0, 0, 0, 0, -1))',
    'random.seed': 'import random; v = random.seed(1)',
    '_io._IOBase.close': 'import io; v = io.StringIO().close()',
    '_io._IOBase.flush': 'import io; v = io.StringIO().flush()',
    '_io._IOBase.readable': 'import io; v = io.StringIO().readable()',
    '_io._IOBase.writable': 'import io; v = io.StringIO().writable()',
    '_io._IOBase.seekable': 'import io; v = io.StringIO().seekable()',
    'os.chdir': 'import os; v = os.chdir(".")',
    'os.mkdir': 'import os, tempfile; d = tempfile.mkdtemp(); v = os.mkdir(d + "/x")',
    'os.rmdir': 'import os, tempfile; d = tempfile.mkdtemp(); os.mkdir(d + "/x"); v = os.rmdir(d + "/x")',
    'os.unlink': 'import os, tempfile; d = tempfile.mkdtemp(); p = d + "/x"; open(p, "w").close(); v = os.unlink(p)',
    'os.chmod': 'import os, tempfile; d = tempfile.mkdtemp(); p = d + "/x"; open(p, "w").close(); v = os.chmod(p, 0o600)',
    'os.rename': 'import os, tempfile; d = tempfile.mkdtemp(); p = d + "/x"; open(p, "w").close(); v = os.rename(p, d + "/y")',
    'os.replace': 'import os, tempfile; d = tempfile.mkdtemp(); p = d + "/x"; open(p, "w").close(); v = os.replace(p, d + "/y")',
}


def prelude_annotations():
    """qualname -> (annotation kind, source) for the prelude functions of genlib.TABLE that have a return annotation."""
    out = {}
    gen_text = (PKG / 'prelude_genlib.py').read_text(encoding='utf-8')
    gen_tree = ast.parse(gen_text)
    gen_funcs = {n.name: n for n in gen_tree.body if isinstance(n, ast.FunctionDef)}
    rand_text = (PKG / 'prelude_random.py').read_text(encoding='utf-8')
    rand_tree = ast.parse(rand_text)
    rand_methods = {}
    for node in rand_tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'Random':
            rand_methods = {n.name: n for n in node.body if isinstance(n, ast.FunctionDef)}
    for qualname, target in genlib.TABLE.items():
        if target.startswith('_ail_rng.'):
            method = target[len('_ail_rng.'):]
            node = rand_methods.get(method)
            source = 'prelude_random.py:%d' % (node.lineno if node else 0)
        else:
            node = gen_funcs.get(target)
            source = 'prelude_genlib.py:%d' % (node.lineno if node else 0)
        if node is None or node.returns is None:
            continue
        annotation = ast.unparse(node.returns).strip().strip('"\'')
        if annotation in ('int', 'float', 'bool', 'str', 'bytes'):
            out[qualname] = (annotation, source)
        else:
            out[qualname] = ('obj', source)
    return out


_LINE_CACHE = {}


def source_of(name):
    """`file:line` of the first quoted occurrence of `name` in the compiler's table files."""
    if name in _LINE_CACHE:
        return _LINE_CACHE[name]
    needle = "'" + name + "'"
    found = ''
    for filename in ('pyfunc.py', 'filelib.py', 'proclib.py', 'urllower.py', 'sqllower.py', 'hashlower.py'):
        path = PKG / filename
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            continue
        at = text.find(needle)
        if at >= 0:
            found = '%s:%d' % (filename, text.count('\n', 0, at) + 1)
            break
    _LINE_CACHE[name] = found
    return found


def rows():
    out = []

    for qualname, rule, source in BUILTIN_RULES:
        out.append((qualname, rule, source))

    for method, (kind_value, _arity) in unified._DRAWS.items():
        if kind_value is None:                  # choice(): an element of the argument
            out.append(('random.Random.' + method, {'obj'}, DRAWS_SOURCE))
        else:
            out.append(('random.Random.' + method, {kind(kind_value)}, DRAWS_SOURCE))

    for label, table, mapping, line in (
            ('_AIL_CLOCK', pyfunc._AIL_CLOCK, CLOCK_MAP, 'pyfunc.py:1404'),
            ('_AIL_SYSINFO', pyfunc._AIL_SYSINFO, SYSINFO_MAP, 'pyfunc.py:1429'),
            ('_AIL_RAND', pyfunc._AIL_RAND, RAND_MAP, 'pyfunc.py:1434')):
        for name, spec in table.items():
            target = mapping.get(name)
            source = '%s %s %s' % (line, label, source_of(name))
            if target is None:
                out.append((name, {kind(spec[0])}, source))
            else:
                out.append((target, {kind(spec[0])}, source))

    for name, spec in filelib.PRIMS.items():
        target = FILE_PRIMS_MAP.get(name)
        source = 'filelib.py:33 PRIMS %s' % (source_of(name) or '?')
        if target is None:
            out.append((name, {kind(spec[0])}, source))
        else:
            out.append((target, {kind(spec[0])}, source))

    for qualname, (rule, source) in prelude_annotations().items():
        out.append((qualname, {rule}, source))

    return out


def classify(rule, qualname):
    entry = lookup(qualname)
    stub = entry[0] if entry is not None else None
    if stub is None or stub == 'obj':
        return stub or 'obj', 'stub_obj'
    if stub in rule:
        return stub, 'agree'
    return stub, 'conflict'


def cpython_type(snippet):
    code = snippet + '\nprint(type(v).__name__)\n'
    try:
        proc = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return '?'
    if proc.returncode != 0:
        return '?'
    name = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else '?'
    return {'NoneType': 'None'}.get(name, name)


def verdict(rule, stub, cpython):
    if cpython == '?':
        return 'unprobed'
    if cpython in rule:
        return 'rule'
    if cpython == stub or (stub == 'None' and cpython == 'None'):
        return 'stub'
    return 'neither'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--markdown', type=Path, help='write the conflict report to this path')
    args = parser.parse_args(argv)

    counts = {'agree': 0, 'conflict': 0, 'stub_obj': 0}
    conflicts = []
    lines = []
    for qualname, rule, source in rows():
        stub, status = classify(rule, qualname)
        counts[status] += 1
        lines.append('%s %s %s %s' % (qualname, '|'.join(sorted(rule)), stub, source))
        if status == 'conflict':
            snippet = PROBES.get(qualname)
            cpython = cpython_type(snippet) if snippet else '?'
            conflicts.append((qualname, '|'.join(sorted(rule)), stub, source, cpython,
                              verdict(rule, stub, cpython), snippet or ''))

    checked = sum(counts.values())
    for line in lines:
        print(line)
    print('checked %d agree %d conflict %d stub_obj %d'
          % (checked, counts['agree'], counts['conflict'], counts['stub_obj']))
    for qualname, rule, stub, source, cpython, which, _snippet in conflicts:
        print('conflict %s rule=%s stub=%s cpython=%s verdict=%s' % (qualname, rule, stub, cpython, which))

    if args.markdown:
        write_markdown(args.markdown, checked, counts, conflicts)
    return 0


def write_markdown(path, checked, counts, conflicts):
    heading = ('# typeshed3 conflicts\n\n'
               'Generated by `python3 tools/typeshed_conflicts.py --markdown lab/typeshed/CONFLICTS.md`.\n'
               'The compiler keeps every hand-written rule; a conflict is only reported here.\n\n'
               '`checked %d agree %d conflict %d stub_obj %d`\n\n'
               'Every entry of `unified._etype`\'s builtin rules, `unified._DRAWS`, `pyfunc._AIL_SYSINFO`,\n'
               '`pyfunc._AIL_RAND`, `pyfunc._AIL_CLOCK`, `filelib.PRIMS` and the annotated prelude functions of\n'
               '`genlib.TABLE` is checked. `stub_obj` means the vendored entry is missing or its return is `obj`\n'
               '(no concrete claim); `agree` means the stub return is one of the rule\'s result types.\n\n'
               '## Conflicts\n\n'
               '| qualname | rule | stub | source | CPython | verdict |\n'
               '|---|---|---|---|---|---|\n' % (checked, counts['agree'], counts['conflict'], counts['stub_obj']))
    body = []
    for qualname, rule, stub, source, cpython, which, _snippet in conflicts:
        body.append('| `%s` | %s | %s | %s | %s | %s |\n'
                    % (qualname, rule, stub, source, cpython, which))
    if not body:
        body.append('| _none_ | | | | | |\n')
    text = heading + ''.join(body) + '\n## Rule may be wrong\n\n'
    if not conflicts:
        text += 'No conflict: every checked rule agrees with its vendored signature.\n'
    else:
        text += ('A `stub` verdict means CPython 3.12 returns the stub\'s type, so the hand-written rule\n'
                 'differs from the public callee. Most of these are internal C status values (`int`) whose\n'
                 'public result is `None`/`bool`/`float`; the prelude converts or discards them. No rule is\n'
                 'changed by this job. Probes (`python3 -c`):\n\n')
        for qualname, rule, stub, source, cpython, which, snippet in conflicts:
            text += ('- `%s`: rule `%s` at `%s`, stub `%s`, CPython `%s` (verdict `%s`). Probe: `%s`\n'
                     % (qualname, rule, source, stub, cpython, which, snippet))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
