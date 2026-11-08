#!/usr/bin/env python3
"""Build an AIL program for wasm32-wasi: the host compiler writes the C, `zig cc` builds it.

    python3 tools/wasm_build.py SRC -o OUT.wasm [--keep DIR] [-- extra compile args]

Runs `ail_chatgpt.py compile SRC --debug-dir WORK/c` for the host (the host binary is a by-product, kept as
WORK/native), takes WORK/c/program.c plus every other generated C file WORK/c/native_report.json lists, and builds them
with `zig cc -target wasm32-wasi -O2`, force-including tools/wasm_shim.h (the setjmp/longjmp tag, all behind
`#ifdef __wasi__`). zig is AIL_ZIG, `zig` on PATH, or ~/tools/zig/zig (as test_ail_cross_target.py finds it);
tested with zig 0.17.1. Run the result with `wasmtime run` and WASMTIME_FLAGS (wasmtime 50.0.1): `-W exceptions=y`
for try/except and `-W max-wasm-stack=268435456`, without which a deep recursion traps instead of raising
RecursionError.
Prints one JSON line: output path, bytes, and the native binary. A failing step exits 1 with the first error line.
"""
import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
SHIM = Path(__file__).resolve().parent / 'wasm_shim.h'
ZIG_FLAGS = ['-target', 'wasm32-wasi', '-O2', '-fno-tree-slp-vectorize', '-ffp-contract=off',
             '-Werror=implicit-function-declaration', '-Werror=implicit-int', '-Werror=incompatible-pointer-types',
             '-mexception-handling', '-mllvm', '-wasm-enable-sjlj', '-mllvm', '-wasm-use-legacy-eh=false',
             '-D_WASI_EMULATED_SIGNAL', '-lwasi-emulated-signal', '-D_WASI_EMULATED_MMAN', '-lwasi-emulated-mman',
             '-D_WASI_EMULATED_PROCESS_CLOCKS', '-lwasi-emulated-process-clocks',
             # The general path's stack check reserves AIL_STACK_UNLIMITED (256 MiB on 32-bit) when getrlimit is
             # absent, so the real stack must be that large or a runaway recursion would trap before RecursionError.
             '-Wl,-z,stack-size=268435456', '-s']
# try/except runs on the exception-handling proposal. max-wasm-stack is wasmtime's NATIVE execution stack, separate
# from the module's linear-memory stack set by -z stack-size. Its default is under 1 MiB, which traps with "call stack
# exhausted" before a runaway recursion reaches AIL's own depth check (typed: AIL_MAX_RECURSION_DEPTH; general path:
# the real-stack check against a 256 MiB budget). Raise it to the same 256 MiB so the program reports RecursionError
# instead of a bare trap. Without this flag a deep recursion has no message; see RESULTS.md.
WASMTIME_FLAGS = ['-W', 'exceptions=y', '-W', 'max-wasm-stack=268435456']

# Modules whose Python implementations cannot exist on wasm32-wasi. proclib.py and threadlib.py refuse
# them in the compiler when AIL_TARGET_OS is wasi; this scan covers the same imports up front (and the
# threaded patterns typedpar.py lowers away before threadlib.py sees the import), so the build names
# WASI instead of reaching a linker error.
WASI_REFUSED = {
    'subprocess': 'WASI has no process creation (no fork/exec)',
    'multiprocessing': 'WASI has no process creation (no fork/exec)',
    'threading': 'WASI has no threads',
    'queue': 'WASI has no threads',
    'concurrent': 'WASI has no threads',
    'socket': 'WASI has no network sockets',
    'signal': 'WASI has no POSIX signals',
}


def wasi_refusal(text):
    """The WASI refusal for the first import of a module wasm32-wasi cannot support, or None."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            base = name.split('.')[0]
            if base in WASI_REFUSED:
                return ('%s is not available on wasm32-wasi: %s.\n'
                        '  write instead: run the program on the host target, or keep %s out of the wasm build'
                        % (base, WASI_REFUSED[base], base))
    return None


def zig():
    local = Path.home() / 'tools' / 'zig' / ('zig.exe' if os.name == 'nt' else 'zig')
    return os.environ.get('AIL_ZIG') or shutil.which('zig') or (str(local) if local.is_file() else None)


def first_error(text):
    lines = [l for l in text.splitlines() if l.strip()]
    for l in lines:
        if 'error' in l.lower():
            return l.strip()
    return lines[0].strip() if lines else '(no output)'


# The typed runtime's stdin reader casts its int64 request to size_t (`next > (size_t)size`). On wasm32 size_t is
# 32 bits, so read_stdin_bytes(1 << 40) becomes 0 and the first realloc is realloc(buf, 0): MemoryError. The emitter
# is not edited in this step; the build saturates the request at SIZE_MAX at the function's entry, in a copy of the C
# (WORK/c/program.wasm.c). No read on wasm32 can exceed SIZE_MAX bytes, so the result is what Python returns. A
# runtime whose reader no longer has this shape stops the build loudly instead of building unpatched.
STDIN_FILL_HEAD = ('static unsigned char *ail_stdin_fill_bytes(unsigned char *buf, size_t *capp, int64_t size, '
                   'int64_t *gotp) {\n    size_t cap = *capp, n = 0;\n')
STDIN_FILL_CAST = '            if (next > (size_t)size) next = (size_t)size;\n'
STDIN_FILL_SAT = '    if ((uint64_t)size > (uint64_t)SIZE_MAX) size = (int64_t)SIZE_MAX; /* wasm_build.py: 32-bit size_t */\n'


def patch_c(text):
    """Returns (text, error): the C with the 32-bit size_t workarounds applied, or an error message."""
    if 'ail_stdin_fill_bytes(unsigned char *buf' not in text:
        return text, ''
    if text.count(STDIN_FILL_HEAD) != 1 or STDIN_FILL_CAST not in text:
        return text, 'wasm_build.py: ail_stdin_fill_bytes changed shape; update the 32-bit size_t patch'
    return text.replace(STDIN_FILL_HEAD, STDIN_FILL_HEAD + STDIN_FILL_SAT), ''


def c_sources(debug_dir):
    """program.c first, then any other generated .c file the report lists (copied into the debug dir or not)."""
    out = [debug_dir / 'program.c']
    report = debug_dir / 'native_report.json'
    if report.is_file():
        for g in json.loads(report.read_text()).get('generated', []):
            p = Path(g.get('debug_path') or g['path'])
            if p.suffix == '.c' and p.name != 'program.c' and p.is_file():
                out.append(p)
    return out


def build(src, out, work, extra=()):
    """Builds WORK/native and OUT; WORK/c must not exist yet. Returns (ok, message): the first compiler or
    linker error on failure."""
    try:
        refusal = wasi_refusal(Path(src).read_text(encoding='utf-8', errors='surrogateescape'))
    except OSError:
        refusal = None
    if refusal:
        return False, refusal
    z = zig()
    if not z:
        return False, 'zig is not installed (AIL_ZIG, PATH or ~/tools/zig/zig)'
    work.mkdir(parents=True, exist_ok=True)
    debug_dir, native = work / 'c', work / 'native'
    if debug_dir.exists() or native.exists():
        return False, '%s already holds a build' % work
    env = dict(os.environ, AIL_TARGET_OS='wasi')      # proclib.py / threadlib.py refuse by name for WASI
    r = subprocess.run([sys.executable, '-B', str(COMPILER), 'compile', str(src), '-o', str(native),
                        '--debug-dir', str(debug_dir), *extra], capture_output=True, text=True, env=env)
    if r.returncode != 0 or not (debug_dir / 'program.c').is_file():
        return False, 'host compile: ' + first_error(r.stderr + r.stdout)
    sources = []
    for p in c_sources(debug_dir):
        text, err = patch_c(p.read_text(encoding='utf-8', errors='surrogateescape'))
        if err:
            return False, err
        if text != p.read_text(encoding='utf-8', errors='surrogateescape'):
            p = p.with_name(p.stem + '.wasm.c')
            p.write_text(text, encoding='utf-8', errors='surrogateescape')
        sources.append(p)
    cmd = [z, 'cc', *ZIG_FLAGS, '-include', str(SHIM), '-o', str(out), *map(str, sources), '-lm']
    r = subprocess.run(cmd, capture_output=True, text=True)
    (debug_dir / 'zig.log').write_text(' '.join(cmd) + '\n' + r.stdout + r.stderr)
    if r.returncode != 0:
        return False, 'zig cc: ' + first_error(r.stderr + r.stdout)
    return True, ''


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('src')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--keep', help='work directory to keep: WORK/c (the C) and WORK/native (default: a temporary one)')
    ap.add_argument('extra', nargs='*', help='extra arguments for the host compile (after --)')
    a = ap.parse_args()
    out = Path(a.out).resolve()
    tmp = None
    if a.keep:
        work = Path(a.keep).resolve()
    else:
        tmp = tempfile.mkdtemp(prefix='ail-wasm-')
        work = Path(tmp)
    try:
        ok, msg = build(Path(a.src).resolve(), out, work, a.extra)
        if not ok:
            print(msg, file=sys.stderr)
            return 1
        print(json.dumps({'output': str(out), 'bytes': out.stat().st_size,
                          'native': str(work / 'native') if a.keep else None}))
        return 0
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
