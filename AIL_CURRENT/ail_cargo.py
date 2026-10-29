#!/usr/bin/env python3
"""ail_cargo: build one Rust crate as an AIL/CPython FFI library in one step.

    python3 AIL_CURRENT/ail_cargo.py build CRATE_DIR -o OUT [--header crate.h]

`CRATE_DIR` needs a `Cargo.toml` whose `[lib]` has `crate-type = ["cdylib", "staticlib"]`
and whose `[profile.release]` has `panic = "abort"`; both are checked before cargo runs and
refused by name when they are missing.  The crate is built with

    cargo build --release --offline --lib

(`--allow-network` drops `--offline`; it is never needed for a crate whose dependencies are
vendored, and it is off by default).  A header comes from `cbindgen` when that program is
installed, otherwise from `--header FILE`; `ail_bindgen.py` then writes the `@extern` stubs.

OUT receives:

    lib<name>.so / lib<name>.dylib     the cdylib, for CPython's ctypes
    lib<name>.a                        the staticlib, for the compiled AIL program
    <name>.h                           the C header
    <name>_ffi.py                      the stubs, with link("./lib<name>.a")
    <name>.link.txt                    cargo's `--print native-static-libs` line
    link.txt                           the same line, for a tool that looks for one name

The link line is also printed.  `--check`, `--errno` and `--typedef` are passed through to
ail_bindgen.  A vendored crate (`cargo vendor` plus `.cargo/config.toml`) needs no network.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BINDGEN = ROOT / 'ail_bindgen.py'
NATIVE_STATIC_LIBS = re.compile(r'native-static-libs:\s*(.*)')
MAX_ERROR = 6000


class CargoError(ValueError):
    """A refusal or a failed tool, with the text the user needs."""


def _run(command, cwd, what, timeout=1800):
    try:
        done = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as error:
        raise CargoError('%s: %s is not installed' % (what, command[0])) from error
    except subprocess.TimeoutExpired as error:
        raise CargoError('%s timed out after %d seconds' % (what, timeout)) from error
    if done.returncode:
        detail = (done.stderr or done.stdout or '').strip()
        if len(detail) > MAX_ERROR:
            detail = detail[-MAX_ERROR:]
        raise CargoError('%s failed (exit %d):\n%s' % (what, done.returncode, detail))
    return done


def _manifest(crate):
    """(the parsed Cargo.toml, the library name) after the two required checks."""
    path = crate / 'Cargo.toml'
    if not path.is_file():
        raise CargoError('no Cargo.toml in %s (build the crate directory, not its src/)' % crate)
    try:
        data = tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise CargoError('cannot read %s: %s' % (path, error)) from error
    lib = data.get('lib') or {}
    kinds = lib.get('crate-type') or []
    if not isinstance(kinds, list) or 'cdylib' not in kinds or 'staticlib' not in kinds:
        raise CargoError('Cargo.toml: [lib] crate-type must be ["cdylib", "staticlib"] '
                         '(CPython loads the cdylib, a compiled AIL program links the staticlib); found %r' % (kinds,))
    release = (data.get('profile') or {}).get('release') or {}
    if release.get('panic') != 'abort':
        raise CargoError('Cargo.toml: [profile.release] panic = "abort" is required for a library '
                         'called across the C FFI; found %r' % release.get('panic'))
    package = data.get('package') or {}
    name = lib.get('name') or package.get('name')
    if not isinstance(name, str) or not name:
        raise CargoError('Cargo.toml: [lib] name or [package] name is required')
    return data, name.replace('-', '_')


def _artifact(crate, name, suffix):
    path = crate / 'target' / 'release' / ('lib%s%s' % (name, suffix))
    if not path.is_file():
        raise CargoError('cargo did not write %s (does [lib] name match %r?)' % (path, name))
    return path


def _header(crate, out, name, header):
    target = out / (name + '.h')
    if header is not None:
        source = Path(header).expanduser()
        if not source.is_absolute():
            source = Path.cwd() / source
        if not source.is_file():
            raise CargoError('--header: no such file: %s' % source)
        target.write_bytes(source.read_bytes())
        return target, 'header'
    cbindgen = shutil.which('cbindgen')
    if cbindgen is None:
        raise CargoError('cbindgen is not installed; pass --header FILE (the C header of the crate), '
                         'or install cbindgen')
    _run([cbindgen, '--output', str(target), '--lang', 'c'], crate, 'cbindgen')
    if not target.is_file():
        raise CargoError('cbindgen did not write %s' % target)
    return target, 'cbindgen'


def _stubs(header, out, name, checks, errnos, typedefs):
    archive = './lib%s.a' % name
    command = [sys.executable, str(BINDGEN), str(header), '--link', archive]
    for check in checks:
        command += ['--check', check]
    for name_of_function in errnos:
        command += ['--errno', name_of_function]
    for typedef in typedefs:
        command += ['--typedef', typedef]
    done = _run(command, out, 'ail_bindgen.py')
    path = out / (name.lower() + '_ffi.py')
    path.write_text(done.stdout, encoding='utf-8', newline='\n')
    return path


def _native_static_libs(crate, allow_network, cargo):
    command = [cargo, 'rustc', '--release']
    if not allow_network:
        command.append('--offline')
    command += ['--lib', '--', '--print', 'native-static-libs']
    done = _run(command, crate, 'cargo rustc --print native-static-libs')
    match = NATIVE_STATIC_LIBS.search(done.stderr + '\n' + done.stdout)
    if match is None:
        raise CargoError('cargo did not print a native-static-libs line; its output was:\n%s'
                         % ((done.stderr or done.stdout).strip()[-MAX_ERROR:]))
    return 'native-static-libs: ' + match.group(1).strip()


def build(crate_dir, output, header=None, allow_network=False, checks=(), errnos=(), typedefs=(), cargo=None):
    """Build CRATE_DIR into OUTPUT and return a summary dict. Raises CargoError."""
    crate = Path(crate_dir).expanduser().resolve()
    out = Path(output).expanduser().resolve()
    if not crate.is_dir():
        raise CargoError('crate directory does not exist: %s' % crate)
    cargo = cargo or shutil.which('cargo')
    if not cargo:
        raise CargoError('cargo is not installed (install Rust from https://rustup.rs)')
    _data, name = _manifest(crate)
    out.mkdir(parents=True, exist_ok=True)

    command = [cargo, 'build', '--release']
    if not allow_network:
        command.append('--offline')
    command.append('--lib')
    _run(command, crate, 'cargo build --release%s --lib' % ('' if allow_network else ' --offline'))

    shared_suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    shared = _artifact(crate, name, shared_suffix)
    archive = _artifact(crate, name, '.a')
    shutil.copy2(shared, out / shared.name)
    shutil.copy2(archive, out / archive.name)

    header_path, header_source = _header(crate, out, name, header)
    stub_path = _stubs(header_path, out, name, checks, errnos, typedefs)
    link_line = _native_static_libs(crate, allow_network, cargo)
    (out / (name + '.link.txt')).write_text(link_line + '\n', encoding='utf-8')
    (out / 'link.txt').write_text(link_line + '\n', encoding='utf-8')

    files = [out / shared.name, out / archive.name, header_path, stub_path,
             out / (name + '.link.txt'), out / 'link.txt']
    return {'schema': 1, 'name': name, 'output': str(out), 'header_source': header_source,
            'native_static_libs': link_line.split(':', 1)[1].strip(), 'link_line': link_line,
            'files': [str(path) for path in files]}


def main(argv=None):
    parser = argparse.ArgumentParser(description='build a Rust crate as an AIL FFI library')
    commands = parser.add_subparsers(dest='command', required=True)
    build_cmd = commands.add_parser('build', help='cargo build --release --offline --lib, then header + stubs')
    build_cmd.add_argument('crate_dir', metavar='CRATE_DIR')
    build_cmd.add_argument('-o', '--output', required=True, metavar='OUT')
    build_cmd.add_argument('--header', help='C header to use when cbindgen is not installed (or to override it)')
    build_cmd.add_argument('--allow-network', action='store_true',
                           help='do not pass --offline to cargo (off by default; tests never use it)')
    build_cmd.add_argument('--check', action='append', default=[], metavar='FUNC=KIND[:EXC]',
                           help='passed to ail_bindgen.py (repeatable)')
    build_cmd.add_argument('--errno', action='append', default=[], metavar='FUNC',
                           help='passed to ail_bindgen.py (repeatable)')
    build_cmd.add_argument('--typedef', action='append', default=[], metavar='NAME=c_type',
                           help='passed to ail_bindgen.py (repeatable)')
    args = parser.parse_args(argv)
    try:
        result = build(args.crate_dir, args.output, header=args.header, allow_network=args.allow_network,
                       checks=args.check, errnos=args.errno, typedefs=args.typedef)
    except (CargoError, OSError) as error:
        print('ail_cargo: %s' % error, file=sys.stderr)
        return 1
    print(result['link_line'])
    print('ail_cargo: wrote %s' % ', '.join(Path(path).name for path in result['files']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
