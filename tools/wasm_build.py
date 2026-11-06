#!/usr/bin/env python3
"""Build an AIL program for wasm32-wasi: the host compiler writes the C, `zig cc` builds it.

    python3 tools/wasm_build.py SRC -o OUT.wasm [--keep DIR] [-- extra compile args]

Runs `ail_chatgpt.py compile SRC --debug-dir WORK/c` for the host (the host binary is a by-product, kept as
WORK/native), takes WORK/c/program.c plus every other generated C file WORK/c/native_report.json lists, and builds them
with `zig cc -target wasm32-wasi -O2`, force-including tools/wasm_shim.h (setjmp/longjmp stand-ins, all behind
`#ifdef __wasi__`). zig is AIL_ZIG, `zig` on PATH, or ~/tools/zig/zig (as test_ail_cross_target.py finds it).
Prints one JSON line: output path, bytes, and the native binary. A failing step exits 1 with the first error line.
"""
import argparse
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
             '-D_WASI_EMULATED_SIGNAL', '-D_WASI_EMULATED_PROCESS_CLOCKS', '-D_WASI_EMULATED_MMAN',
             '-lwasi-emulated-signal', '-lwasi-emulated-process-clocks', '-lwasi-emulated-mman',
             '-Wl,-z,stack-size=8388608', '-s']


def zig():
    local = Path.home() / 'tools' / 'zig' / ('zig.exe' if os.name == 'nt' else 'zig')
    return os.environ.get('AIL_ZIG') or shutil.which('zig') or (str(local) if local.is_file() else None)


def first_error(text):
    lines = [l for l in text.splitlines() if l.strip()]
    for l in lines:
        if 'error' in l.lower():
            return l.strip()
    return lines[0].strip() if lines else '(no output)'


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
    z = zig()
    if not z:
        return False, 'zig is not installed (AIL_ZIG, PATH or ~/tools/zig/zig)'
    work.mkdir(parents=True, exist_ok=True)
    debug_dir, native = work / 'c', work / 'native'
    if debug_dir.exists() or native.exists():
        return False, '%s already holds a build' % work
    r = subprocess.run([sys.executable, '-B', str(COMPILER), 'compile', str(src), '-o', str(native),
                        '--debug-dir', str(debug_dir), *extra], capture_output=True, text=True)
    if r.returncode != 0 or not (debug_dir / 'program.c').is_file():
        return False, 'host compile: ' + first_error(r.stderr + r.stdout)
    cmd = [z, 'cc', *ZIG_FLAGS, '-include', str(SHIM), '-o', str(out), *map(str, c_sources(debug_dir)), '-lm']
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
