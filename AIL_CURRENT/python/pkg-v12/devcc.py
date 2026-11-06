"""Opt-in development C compiler (`compile --cc=tcc|mir`) for AIL.

Nothing in this module runs unless ``$AIL_DEVCC`` is set: the release and
default builds keep using gcc ``-O2`` byte for byte.  When the mode is on, the
gcc command is mapped to the external tool, gcc-only flags are dropped, and the
generated C is scanned for constructs the tool does not build identically to
gcc.  A construct that cannot be guaranteed refuses the whole program by name
before any C is compiled; there is no partial build and no silent difference.

The finding this follows (``lab/tccdev``, 2026-11-01) is that tcc 0.9.28
accepts AIL's generated C once the three checked-overflow builtins are given a
portable definition.  tcc 0.9.27 has no ``_Thread_local`` and no size inference
for unsized aggregate literals/declarations, which nearly every generated C
uses, so that whole version is refused by its ``tcc -v``.  On 0.9.28 the corpus
gate (``lab/devcc/gate.py``) found three constructs to refuse by name: 128-bit
integers (``__int128``, ``__int128_t``, ``__uint128_t``), ``__builtin_fabs``
and ``__builtin_isinf``.  A program that reaches one is refused rather than
mis-compiled.

MIR is reached as an external ``c2m`` command only (`$AIL_MIR_C2M`, else
``c2m`` on PATH).  c2m cannot write an executable, so ``--cc=mir`` is accepted
only for a run-style command and refused for ``compile -o`` with a named
message.
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

try:                                        # pyc imports this through pipeline
    from pipeline import PipelineError as _PipelineError
except Exception:                           # a standalone import (tests, tooling)

    class _PipelineError(Exception):
        pass


class DevCCRefusal(_PipelineError):
    """The program cannot be built identically to gcc by the selected tool."""


MODE_ENV = 'AIL_DEVCC'
MIR_ENV = 'AIL_MIR_C2M'
MODES = ('tcc', 'mir')

# tcc 0.9.27 predates the parser fixes this generated C needs: it fails on
# _Thread_local, unsized aggregate literals/declarations and __builtin_unreachable.
# tccprobe1 measured 0 of 50 programs building with it, so the whole version is
# refused instead of enumerating constructs that would refuse almost everything.
_TCC_MIN_VERSION = (0, 9, 28)
_TCC_VERSION = re.compile(r'\btcc version\s+(\d+)\.(\d+)\.(\d+)')

# Constructs reached by the generated C that the tool does not implement.
# Keep the names exactly as they appear in the C: the message quotes them.
_TCC_CONSTRUCTS = (
    # tcc has no 128-bit integer: `unsigned __int128` and the gcc typedefs
    # `__int128_t` / `__uint128_t` all fail (devcc3 gate measured `__uint128_t`).
    ('__int128', re.compile(r'\b(?:unsigned\s+)?__int128\b|\b__u?int128_t\b')),
    # tcc neither defines these builtins nor links them from libm (devcc3 gate).
    ('__builtin_fabs', re.compile(r'\b__builtin_fabs\b')),
    ('__builtin_isinf', re.compile(r'\b__builtin_isinf\b')),
    ('__builtin_choose_expr', re.compile(r'\b__builtin_choose_expr\b')),
    ('__builtin_types_compatible_p', re.compile(r'\b__builtin_types_compatible_p\b')),
    ('__builtin_shuffle', re.compile(r'\b__builtin_shuffle\b')),
    ('__builtin_convertvector', re.compile(r'\b__builtin_convertvector\b')),
)
# MIR's C front end is stricter: the generated C's GCC extensions are refused.
_MIR_CONSTRUCTS = (
    ('__int128', re.compile(r'\b(?:unsigned\s+)?__int128\b')),
    ('__attribute__', re.compile(r'\b__attribute__\b')),
    ('__typeof__', re.compile(r'\b__typeof__\b')),
    ('__builtin_expect', re.compile(r'\b__builtin_expect\b')),
    ('__builtin_unreachable', re.compile(r'\b__builtin_unreachable\b')),
    ('__builtin_constant_p', re.compile(r'\b__builtin_constant_p\b')),
    ('__builtin_memcpy', re.compile(r'\b__builtin_memcpy\b')),
    ('__builtin_add_overflow', re.compile(r'\b__builtin_add_overflow\b')),
    ('__builtin_sub_overflow', re.compile(r'\b__builtin_sub_overflow\b')),
    ('__builtin_mul_overflow', re.compile(r'\b__builtin_mul_overflow\b')),
    ('statement expression', re.compile(r'\(\s*\{')),
)
_CONSTRUCTS = {'tcc': _TCC_CONSTRUCTS, 'mir': _MIR_CONSTRUCTS}

# The portable stand-ins for the only builtins tcc lacks (same semantics as the
# gcc builtins; measured against gcc on 511 corpus cases in lab/tccdev).
_PRELUDE_MARK = '/* ail devcc tcc prelude */'
_PRELUDE = _PRELUDE_MARK + r'''
#include <stdint.h>
#ifdef __TINYC__
static int ail_tcc_add_overflow(int64_t a, int64_t b, int64_t *r) {
    *r = (int64_t)((uint64_t)a + (uint64_t)b);
    return ((a ^ *r) & (b ^ *r)) < 0;
}
static int ail_tcc_sub_overflow(int64_t a, int64_t b, int64_t *r) {
    *r = (int64_t)((uint64_t)a - (uint64_t)b);
    return ((a ^ b) & (a ^ *r)) < 0;
}
static int ail_tcc_mul_overflow(int64_t a, int64_t b, int64_t *r) {
    if (a == 0 || b == 0) { *r = 0; return 0; }
    if (a == -1) { if (b == INT64_MIN) { *r = b; return 1; } *r = -b; return 0; }
    if (b == -1) { if (a == INT64_MIN) { *r = a; return 1; } *r = -a; return 0; }
    if (a > 0) {
        if (b > 0) { if (a > INT64_MAX / b) { *r = (int64_t)((uint64_t)a * (uint64_t)b); return 1; } }
        else { if (b < INT64_MIN / a) { *r = (int64_t)((uint64_t)a * (uint64_t)b); return 1; } }
    } else {
        if (b > 0) { if (a < INT64_MIN / b) { *r = (int64_t)((uint64_t)a * (uint64_t)b); return 1; } }
        else { if (a < INT64_MAX / b) { *r = (int64_t)((uint64_t)a * (uint64_t)b); return 1; } }
    }
    *r = a * b;
    return 0;
}
#define __builtin_add_overflow(a, b, r) ail_tcc_add_overflow((a), (b), (r))
#define __builtin_sub_overflow(a, b, r) ail_tcc_sub_overflow((a), (b), (r))
#define __builtin_mul_overflow(a, b, r) ail_tcc_mul_overflow((a), (b), (r))
#endif
'''


class _Prepared(list):
    """The rewritten command plus the temporary files it owns."""

    def __init__(self, command, directories=()):
        super().__init__(command)
        self.directories = list(directories)

    def cleanup(self):
        for directory in self.directories:
            shutil.rmtree(directory, ignore_errors=True)
        self.directories[:] = []


def mode():
    """The selected mode, or None when the opt-in flag is off."""
    value = os.environ.get(MODE_ENV, '').strip().lower()
    if not value or value in ('0', 'off', 'false', 'no'):
        return None
    if value not in MODES:
        raise DevCCRefusal('--cc=%s: unknown development compiler (choose tcc or mir); build without --cc' % value)
    return value


def executable(name):
    """The external tool for `name`, or a named refusal when it is not installed."""
    if name == 'tcc':
        found = shutil.which('tcc')
        label = 'tcc'
    elif name == 'mir':
        found = os.environ.get(MIR_ENV) or shutil.which('c2m')
        label = 'c2m'
    else:
        found, label = None, name
    if not found:
        raise DevCCRefusal('--cc=%s: %s is not on PATH; build without --cc' % (name, label))
    return found


def tcc_version(tool):
    """The ``x.y.z`` tuple from ``tcc -v``, or None when it cannot be read."""
    try:
        done = subprocess.run([os.fspath(tool), '-v'], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    match = _TCC_VERSION.search((done.stdout or '') + (done.stderr or ''))
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def _check_tcc_version(tool):
    version = tcc_version(tool)
    if version is not None and version < _TCC_MIN_VERSION:
        text = '%d.%d.%d' % version
        raise DevCCRefusal(
            '--cc=tcc: tcc %s cannot build this generated C; use tcc 0.9.28 or later, '
            'or build without --cc' % text)


def _refuse(name, construct, line):
    raise DevCCRefusal(
        '--cc=%s: this program uses %s (line %d of the generated C), which %s '
        'does not build identically to gcc; build without --cc'
        % (name, construct, line, name))


def scan(name, text):
    """Refuse the first generated-C construct the tool cannot build identically to gcc."""
    for construct, pattern in _CONSTRUCTS.get(name, ()):
        match = pattern.search(text)
        if match is not None:
            _refuse(name, construct, text.count('\n', 0, match.start()) + 1)


def _sources(command):
    result = []
    for part in command[1:]:
        part = os.fspath(part)
        if part.endswith('.c') and os.path.isfile(part):
            result.append(part)
    return result


# Flags that mean the same thing to tcc; everything else gcc-specific is dropped.
_KEEP = {'-c', '-shared', '-static', '-pthread', '-nostdinc', '-fPIC', '-fpic'}
_KEEP_WITH_ARG = {'-o', '-I', '-D', '-U', '-L', '-l', '-include', '-isystem', '-idirafter', '-MF', '-MT', '-MQ'}


def _rewrite_args(args):
    kept = []
    index = 0
    while index < len(args):
        part = os.fspath(args[index])
        if part in _KEEP_WITH_ARG:
            kept.append(part)
            if index + 1 < len(args):
                kept.append(os.fspath(args[index + 1]))
            index += 2
            continue
        if part.startswith(('-I', '-D', '-U', '-L', '-l')):
            kept.append(part)
        elif part in _KEEP:
            kept.append(part)
        elif not part.startswith('-'):
            kept.append(part)
        index += 1
    return kept


def _with_prelude(sources):
    directory = tempfile.mkdtemp(prefix='ail-devcc-')
    replaced = {}
    for source in sources:
        text = Path(source).read_text(encoding='utf-8')
        if _PRELUDE_MARK in text:
            continue
        copy = Path(directory) / Path(source).name
        copy.write_text(_PRELUDE + text, encoding='utf-8')
        replaced[source] = str(copy)
    return replaced, directory


def rewrite(command, phase='compile_link'):
    """Map a gcc command to the selected tool, or refuse the program by name.

    With the mode off the command object is returned unchanged, so the default
    build sees exactly the arguments it saw before this module existed.
    """
    name = mode()
    if name is None:
        return command
    if name == 'mir' and phase != 'run':
        raise DevCCRefusal(
            '--cc=mir: c2m cannot write an executable, so --cc=mir is available only '
            'for a run-style command; build without --cc')
    tool = executable(name)
    if name == 'tcc':
        _check_tcc_version(tool)
    source_paths = _sources(command)
    for source in source_paths:
        try:
            text = Path(source).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        scan(name, text)
    directories = []
    if name == 'tcc' and source_paths:
        replaced, directory = _with_prelude(source_paths)
        directories.append(directory)
    else:
        replaced = {}
    rewritten = [tool]
    for part in _rewrite_args(command[1:]):
        rewritten.append(replaced.get(os.fspath(part), part))
    return _Prepared(rewritten, directories)


def cleanup(command):
    """Remove temporary files a rewrite created (a no-op for an unchanged command)."""
    closer = getattr(command, 'cleanup', None)
    if closer is not None:
        closer()
