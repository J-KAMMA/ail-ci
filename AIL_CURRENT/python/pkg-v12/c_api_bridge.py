"""Library-specific runtime bridge for separately compiled C API dependencies."""
import ast
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from pipeline import PipelineError, compiler
from pyfront import Unsupported


def validate_namespace(name):
    if type(name) is not str or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,47}', name) or name.startswith('ail_'):
        raise Unsupported('C API namespace must be a library name (ASCII, 1..48 characters, not ail_*)')
    return name


def validate_source(source):
    if any(isinstance(n, ast.Name) and n.id == 'sys' or isinstance(n, ast.Call)
           and isinstance(n.func, ast.Name) and n.func.id == 'input' for n in ast.walk(ast.parse(source))):
        raise Unsupported('C API dependency receives input through parameters; input() and sys are unsupported')


def namespace_module(source, exports, name):
    validate_namespace(name)
    names = {spec['symbol']: name + '_ail_dependency_' + spec['symbol'] for spec in exports.values()}
    class Rename(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            node.name = names.get(node.name, node.name)
            return self.generic_visit(node)

        def visit_Name(self, node):
            node.id = names.get(node.id, node.id)
            return node
    for spec in exports.values():
        spec['symbol'] = names[spec['symbol']]
    return ast.unparse(Rename().visit(ast.parse(source)))


def state_prefix(body, name):
    validate_namespace(name)
    states = re.findall(r'^AIL_LINK_STATE\(.+, ([A-Za-z_]\w*)(?:\[[^]]+\])?,\s*.*?\);', body, re.MULTILINE)
    return ''.join(f'#define {state} {name}_ail_state_{state}\n' for state in dict.fromkeys(states))


def rewrite_uncaught(body, trap_name):
    """Replace exactly the owning-exception terminal boundary, leaving active handlers intact."""
    if not isinstance(trap_name,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',trap_name):
        raise Unsupported('invalid C API exception trap name')
    marker=re.compile(r'^static void ail_exception_uncaught\(ail_exception \*value\) \{\n.*?^\}',re.MULTILINE|re.DOTALL)
    matches=list(marker.finditer(body))
    if len(matches)!=1 or matches[0].group().count('    fputc(10, stderr); _Exit(1);')!=1 or not matches[0].group().endswith('    fputc(10, stderr); _Exit(1);\n}'):
        raise Unsupported('C API owning exception boundary marker changed')
    replacement=r'''static void ail_exception_uncaught(ail_exception *value) {
    char message[160];
    size_t used = 0;
    if (value->n > 0 && value->p) {
        /* UTF-8 already: copy whole characters while they fit, stopping at a NUL. */
        const unsigned char *raw = (const unsigned char *)value->p;
        for (int64_t i = 0; i < value->n && raw[i];) {
            unsigned width = raw[i] < 0x80 ? 1 : raw[i] < 0xE0 ? 2 : raw[i] < 0xF0 ? 3 : 4;
            if (width > sizeof message - 1 - used || (int64_t)width > value->n - i) break;
            memcpy(message + used, raw + i, width); used += width; i += width;
        }
        message[used] = 0;
        TRAP(value->code, message);
    }
    TRAP(value->code, ail_exception_name(value->code));
}'''.replace('TRAP',trap_name)
    match=matches[0]
    return body[:match.start()]+replacement+body[match.end():]


def object_prefix(body, name):
    """Redirect generated runtime state, fatal paths and resource management."""
    validate_namespace(name)
    trap = name + '_ail_bridge_trap'
    replacements = {
        'fflush(stdout); fputs(w, stderr); fputc(10, stderr); _Exit(1);':
            f'{trap}(ail_exc_kind_of(w) ? ail_exc_kind_of(w) : 8, w);',
    }
    for old, new in replacements.items():
        body, count = re.subn(r'^    ' + re.escape(old) + '$', '    ' + new, body, flags=re.MULTILINE)
        if count != int('static void ail_die(' in body):
            raise Unsupported('C API dependency fatal boundary marker changed')
    if 'static void ail_die(' in body:
        body = rewrite_uncaught(body, trap)
    body = body.replace('    ail_str_write(s, stderr);\n    fputc(10, stderr);\n    _Exit(1);',
                        f'    (void)s; {trap}(8, "assertion failed");')
    tokens = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '', body, flags=re.DOTALL)
    if re.search(r'\b(?:_Exit|_exit)\s*\(', tokens):
        raise Unsupported('unhandled process exit in C API dependency')
    return resource_prefix(name) + state_prefix(body, name) + body


def resource_prefix(name):
    validate_namespace(name)
    prefix = name + '_ail_bridge_'
    signatures = {'malloc': 'void *%s(size_t)', 'calloc': 'void *%s(size_t,size_t)',
                  'realloc': 'void *%s(void *,size_t)', 'free': 'void %s(void *)',
                  'fopen': 'FILE *%s(const char *,const char *)', 'fclose': 'int %s(FILE *)'}
    result = '#include <stdlib.h>\n#include <stdio.h>\n#include <wchar.h>\n'
    result += f'extern _Noreturn void {prefix}trap(int,const char *);\n'
    result += ''.join('extern ' + signature % (prefix + fn) + ';\n#define ' + fn + ' ' + prefix + fn + '\n'
                      for fn, signature in signatures.items())
    return result + f'#ifdef _WIN32\nextern FILE *{prefix}wfopen(const wchar_t *,const wchar_t *);\n#define _wfopen {prefix}wfopen\n#endif\n'


def archive_tools(environment):
    tools = {}
    for name in ('nm', 'objcopy'):
        query = subprocess.run([compiler(), '-print-prog-name='+name], capture_output=True,
                               timeout=20, env=environment)
        if query.returncode:
            raise PipelineError('cannot identify archive '+name+' tool')
        value = query.stdout.decode().strip()
        path = Path(shutil.which(value) or value).resolve(strict=True)
        tools[name] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return tools


def bind_archive_resources(target, name, prefix, tools, environment, archives=()):
    """Bind relocations to the same tracked call that owns the C adapter."""
    validate_namespace(name)
    def run(argv):
        result = subprocess.run(argv, capture_output=True, timeout=120, env=environment)
        if result.returncode:
            raise PipelineError('C archive resource binding failed: '+result.stderr.decode(errors='replace')[-2000:])
        return result.stdout.decode(errors='replace')
    def unchanged():
        if any(hashlib.sha256(Path(t['path']).read_bytes()).hexdigest() != t['sha256'] for t in tools.values()):
            raise Unsupported('archive binding tool changed during C object build')
    unchanged()
    rows = [line.split() for line in run([tools['nm']['path'], '-g', '--format=posix', str(target)]).splitlines()
            if line.strip()]
    if any(not 2 <= len(row) <= 4 or len(row[1]) != 1 for row in rows):
        raise Unsupported('unrecognized C archive symbol listing')
    defined = {row[0] for row in rows if row[1] not in ('U', 'w', 'v')}
    undefined = {row[0] for row in rows if row[1] in ('U', 'w', 'v')}
    if any(symbol.startswith(prefix) for symbol in defined):
        decoration = ''
    elif any(symbol.startswith('_'+prefix) for symbol in defined):
        decoration = '_'
    else:
        raise Unsupported('C archive adapter symbol ABI is unrecognized')
    signatures = {'malloc': ('void *', 'size_t'), 'calloc': ('void *', 'size_t,size_t'),
                  'realloc': ('void *', 'void *,size_t'), 'free': ('void', 'void *'),
                  'fopen': ('FILE *', 'const char *,const char *'), 'fclose': ('int', 'FILE *'),
                  '_wfopen': ('FILE *', 'const wchar_t *,const wchar_t *')}
    fatal = ('exit', '_Exit', '_exit', 'abort', 'longjmp', '_longjmp', 'siglongjmp', '__longjmp_chk')
    aliases = lambda fn: (decoration+fn, '__imp_'+decoration+fn)
    forbidden_prefix = 'ail_archive_forbidden_'+hashlib.sha256(prefix.encode()).hexdigest()[:24]+'_'
    # Preserve generated runtime jumps. Mark archive references before selection
    # so only forbidden references in members actually linked are rejected.
    if archives:
        with tempfile.TemporaryDirectory(prefix='ail-archive-bind-') as temporary:
            for index, archive in enumerate(archives):
                bound = Path(temporary)/f'{index}.a'
                run([tools['objcopy']['path'], *(f'--redefine-sym={symbol}={decoration+forbidden_prefix}{symbol}'
                     for fn in fatal for symbol in aliases(fn)), str(archive), str(bound)])
                archive.write_bytes(bound.read_bytes())
        unchanged()
        return
    if any(symbol in defined for fn in signatures for symbol in aliases(fn)):
        raise Unsupported('C API archives must not define standard resource symbols')
    if any(symbol.startswith(decoration+forbidden_prefix) for symbol in undefined | defined):
        raise Unsupported('C API archive process exit or external nonlocal jump is unsupported')
    replacements, imports = {}, []
    for fn, (result, args) in signatures.items():
        direct, imported = aliases(fn)
        bridge = name+'_ail_bridge_'+fn.lstrip('_')
        if direct in undefined:
            replacements[direct] = decoration+bridge
        if imported in undefined:
            pointer = 'ail_archive_import_'+hashlib.sha256(prefix.encode()).hexdigest()[:24]+'_'+fn.lstrip('_')
            replacements[imported] = decoration+pointer
            imports.append(f'extern {result} {bridge}({args});\n{result} (*{pointer})({args}) = {bridge};\n')
    if replacements:
        bound = target.with_name('archive_bound.o')
        run([tools['objcopy']['path'], *(f'--redefine-sym={old}={new}' for old, new in replacements.items()),
             str(target), str(bound)])
        if imports:
            from module_object import FLAGS
            source, obj = target.with_name('archive_imports.c'), target.with_name('archive_imports.o')
            source.write_text('#include <stddef.h>\n#include <stdio.h>\n#include <wchar.h>\n'+''.join(imports), encoding='utf8')
            run([compiler(), *FLAGS, '-std=c11', '-c', str(source), '-o', str(obj)])
            combined = target.with_name('archive_with_imports.o')
            run([compiler(), '-r', str(bound), str(obj), '-o', str(combined)])
            bound = combined
        target.write_bytes(bound.read_bytes())
    unchanged()


def library_bridges(name):
    validate_namespace(name)
    prefix = name + '_ail_bridge_'
    return f'''
void *{prefix}malloc(size_t n) {{ return ail_api_malloc(n); }}
void *{prefix}calloc(size_t n,size_t s) {{ return ail_api_calloc(n,s); }}
void *{prefix}realloc(void *p,size_t n) {{ return ail_api_realloc(p,n); }}
void {prefix}free(void *p) {{ ail_api_free(p); }}
FILE *{prefix}fopen(const char *p,const char *m) {{ return ail_api_fopen(p,m); }}
int {prefix}fclose(FILE *p) {{ return ail_api_fclose(p); }}
#ifdef _WIN32
FILE *{prefix}wfopen(const wchar_t *p,const wchar_t *m) {{ return ail_api_wfopen(p,m); }}
#endif
_Noreturn void {prefix}trap(int c,const char *m) {{ ail_api_trap(c,m); }}
'''
