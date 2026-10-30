#!/usr/bin/env python3
"""Seeded mutation fuzzer for the AIL runtime's input-parsing and text paths.

Builds the programs in AIL_CURRENT/test_ail_hostile_input.py with AddressSanitizer and
UndefinedBehaviorSanitizer, then feeds each one random and mutated stdin. A finding is a
sanitizer report, a signal, a hang, a non-zero internal stop, or stdout/exit status that
differs from CPython running the same program on the same bytes.

Python only, no third-party dependencies. Results are deterministic for a seed when the
same number of cases is reached; --seconds is only an upper bound on wall time.

    python3 tools/input_fuzz.py --seed 20261025 --cases 200 --seconds 60
    python3 tools/input_fuzz.py --programs numbers,text --mode general --keep /tmp/findings
"""
import argparse
import importlib.util
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AIL_CURRENT = REPO / 'AIL_CURRENT'
PYC = AIL_CURRENT / 'python' / 'pkg-v12' / 'pyc.py'
TEST_MODULE = AIL_CURRENT / 'test_ail_hostile_input.py'
SAN = ['-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
       '-g', '-fno-omit-frame-pointer']
SAN_ENV = {
    'ASAN_OPTIONS': 'detect_leaks=0:detect_stack_use_after_return=0',
    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1',
}
# Differences already recorded in DIFFERENCES.md; they are still counted and printed, but
# not reported as new findings.
KNOWN_STDERR = (
    'decode: a code point above U+FFFF in the 16-bit v2 runtime',
    'integer overflow',
    'Exceeds the limit (4300 digits)',
)
MAX_STDIN = 1 << 20


def load_programs():
    spec = importlib.util.spec_from_file_location('test_ail_hostile_input', TEST_MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PROGRAMS


def sanitizers_work():
    if not shutil.which('gcc'):
        return False
    with tempfile.TemporaryDirectory() as d:
        src = Path(d, 'p.c')
        src.write_text('int main(void){return 0;}\n')
        res = subprocess.run(['gcc'] + SAN + [str(src), '-o', str(Path(d, 'p'))],
                             capture_output=True)
        return res.returncode == 0


def build(source, directory, name, general):
    src = Path(directory, name + '.py')
    src.write_text(source, encoding='utf-8')
    exe = Path(directory, name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0',
               AIL_EXTRA_CFLAGS=' '.join(SAN), **SAN_ENV)
    env.pop('AIL_NO_GENERAL', None)
    cmd = [sys.executable, '-B', str(PYC), str(exe), '--file', str(src)]
    if general:
        cmd.append('--general-only')
    res = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if res.returncode:
        raise RuntimeError('build %s failed:\n%s' % (name, res.stderr[-2000:]))
    return exe


def mutate(rng, seeds, i):
    """A deterministic case from the seed list and the case number."""
    if i < len(seeds):
        return seeds[i]
    kind = rng.randrange(6)
    base = bytearray(rng.choice(seeds))
    if kind == 0:  # bit flips
        for _ in range(rng.randrange(1, 12)):
            if base:
                p = rng.randrange(len(base))
                base[p] ^= 1 << rng.randrange(8)
    elif kind == 1:  # splice a seed over a range
        other = rng.choice(seeds)
        if base and other:
            p = rng.randrange(len(base))
            q = rng.randrange(len(other))
            n = rng.randrange(1, min(len(other) - q, 128) + 1)
            base[p:p + n] = other[q:q + n]
    elif kind == 2:  # insert a token
        token = rng.choice(seeds)
        p = rng.randrange(len(base) + 1)
        base[p:p] = token[:rng.randrange(1, len(token) + 1)] if token else b'\x00'
    elif kind == 3:  # delete a range
        if base:
            p = rng.randrange(len(base))
            del base[p:p + rng.randrange(1, min(256, len(base) - p) + 1)]
    elif kind == 4:  # a run of one byte
        base = bytearray(rng.choice(b'0123456789abcdefxX_,+- \t\r\n\x00\xff\x80\xe9\xf0')
                         for _ in range(rng.choice((1, 10, 100, 1000, 10000))))
    else:  # long/near-limit number text
        digits = rng.choice(('9', '1', '0', '_9', '٣', '１'))
        base = bytearray((rng.choice('+- ') + digits * rng.choice((19, 20, 300, 4400, 5000))).encode())
    return bytes(base[:MAX_STDIN])


def run(cmd, data, timeout):
    try:
        return subprocess.run(cmd, input=data, capture_output=True, timeout=timeout,
                              env=dict(os.environ, **SAN_ENV))
    except subprocess.TimeoutExpired:
        return None


def classify(py, got):
    if got is None:
        return 'hang'
    err = got.stderr.decode('utf-8', 'replace')
    if got.returncode < 0:
        return 'signal:%d' % -got.returncode
    if 'Sanitizer' in err or 'runtime error:' in err:
        return 'sanitizer'
    if py.stdout != got.stdout or py.returncode != got.returncode:
        if any(s in err for s in KNOWN_STDERR):
            return 'known'
        return 'diff'
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seed', type=int, default=20261025)
    ap.add_argument('--cases', type=int, default=100, help='cases per program (deterministic)')
    ap.add_argument('--seconds', type=float, default=60.0, help='wall-clock upper bound')
    ap.add_argument('--programs', default='all')
    ap.add_argument('--mode', choices=('general', 'default', 'both'), default='both')
    ap.add_argument('--timeout', type=float, default=10.0)
    ap.add_argument('--keep', help='directory for reproducers and report.json')
    ap.add_argument('--no-build', metavar='DIR', help='reuse a directory with <name>_g / <name>_d binaries')
    args = ap.parse_args(argv)

    programs = load_programs()
    names = sorted(programs) if args.programs == 'all' else [p.strip() for p in args.programs.split(',') if p.strip()]
    unknown = [n for n in names if n not in programs]
    if unknown:
        ap.error('unknown programs: %s' % ', '.join(unknown))

    if args.no_build:
        work = Path(args.no_build)
        builds = {}
        for name in names:
            builds[name] = {}
            for mode, suffix in (('general', '_g'), ('default', '_d')):
                if args.mode in (mode, 'both') and Path(work, name + suffix).exists():
                    builds[name][mode] = Path(work, name + suffix)
    else:
        if not sanitizers_work():
            print('gcc with AddressSanitizer/UndefinedBehaviorSanitizer is required', file=sys.stderr)
            return 2
        work = Path(tempfile.mkdtemp(prefix='ail-fuzz-'))
        builds = {}
        for name in names:
            builds[name] = {}
            for mode, general in (('general', True), ('default', False)):
                if args.mode in (mode, 'both'):
                    builds[name][mode] = build(programs[name], work, name, general)

    rng = random.Random(args.seed)
    seeds = [
        b'', b'\n', b'\x00', b'\x00\x00\x00', b' ', b'\t\r\n',
        b'\xff', b'\xff' * 64, b'\x80', b'\xc0\xaf', b'\xed\xa0\x80',
        b'\xf0\x9f\x98', b'\xf0\x9f\x98\x80', b'\xe4\xb8\xad', b'caf\xc3\xa9',
        b'0', b'-0', b'+7', b' 42 ', b'9223372036854775807',
        b'-9223372036854775808', b'1_000', b'_1', b'1_', b'1__0', b'0x10',
        b'0o17', b'0b101', b'10\x1c', b'\x1c10', b'1\x00', b'1e300', b'inf',
        b'nan', b'-inf', b'abc', b'\xd9\xdd\xa8', b'"k":1,"v":[2,3]',
        b'a,b,,c', b'  a b  ', b'%d|%s|%05x', b'{0:>8}',
        b'a' * 1000, b'9' * 5000, b'x' * (1 << 20), b' ' * (1 << 20),
        b'line1\nline2\r\nline3\n', b'\xe2\x80\xa8', b'\xd9\xa1\xd9\xa2',
    ]
    if not any(len(s) > 100000 for s in seeds):
        seeds.append(b'a' * (1 << 20))

    findings = []
    counts = {}
    started = time.monotonic()
    stopped = False
    for i in range(args.cases):
        data = mutate(rng, seeds, i)
        for name in names:
            for mode, exe in sorted(builds[name].items()):
                if time.monotonic() - started > args.seconds:
                    stopped = True
                    break
                py = run([sys.executable, str(Path(work, name + '.py'))], data, args.timeout)
                got = run([str(exe)], data, args.timeout)
                verdict = classify(py, got)
                if py is None:
                    verdict = 'cpython-hang'
                counts[verdict or 'ok'] = counts.get(verdict or 'ok', 0) + 1
                if verdict and verdict != 'known':
                    findings.append({'program': name, 'mode': mode, 'case': i,
                                     'verdict': verdict, 'stdin': data.hex(),
                                     'stderr': (got.stderr if got else b'')[-4000:].decode('utf-8', 'replace'),
                                     'py_returncode': py.returncode if py else None,
                                     'returncode': got.returncode if got else None})
                    print('FINDING %s %s case %d %s stdin=%r' % (name, mode, i, verdict, data[:80]))
            if stopped:
                break
        if stopped:
            break

    print('seed=%d cases=%d elapsed=%.1fs modes=%s' % (args.seed, args.cases,
          time.monotonic() - started, args.mode))
    print('counts: ' + ', '.join('%s=%d' % kv for kv in sorted(counts.items())))
    if findings:
        print('%d finding(s)' % len(findings))
    if args.keep:
        out = Path(args.keep)
        out.mkdir(parents=True, exist_ok=True)
        for n, f in enumerate(findings):
            Path(out, 'finding_%03d.bin' % n).write_bytes(bytes.fromhex(f['stdin']))
        Path(out, 'report.json').write_text(json.dumps(findings, indent=2) + '\n', encoding='utf-8')
        print('reproducers: %s' % out)
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
