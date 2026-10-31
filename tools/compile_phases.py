#!/usr/bin/env python3
"""Where does the time of one cold AIL build go?  (POSIX; needs bash and gcc.)

    python3 tools/compile_phases.py lab/compare/src/chain_relax/main.ail
    python3 tools/compile_phases.py lab/compare/src/chain_relax/main.py --syntax python --runs 7
    python3 tools/compile_phases.py PROGRAM --repo /path/to/other/checkout     # same tool on a base checkout

Every run is a cold build: a fresh AIL_CACHE and TMPDIR, so neither the front-end nor the C-compiler cache can hit. The C compiler
is reached through a small wrapper (PIPE_CC) that times each invocation and keeps the C it was given, so the build splits into

    python   everything but the C compiler: the CLI, the Python front end, C emission (CPU seconds)
    gcc      the C compiler driver: preprocess, compile, assemble, link (CPU seconds)

and the saved C is then compiled once more with -fsyntax-only and -ftime-report: how much of gcc is reading the text (lexing, parsing)
and how much is optimising and generating code, how large the C and the code are.  Medians of --runs builds, with the spread.
Laptop timing is noisy: CPU seconds (user+sys of the children) are used, wall time is shown for reference.
"""
import argparse, glob, os, re, resource, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WRAPPER = r'''#!/bin/bash
d=${WRAP_DIR:?}
n=$(ls "$d" | grep -c '\.log$')
for a in "$@"; do case "$a" in *.c) cp "$a" "$d/$n.c";; esac; done
/usr/bin/time -f "%e %U %S" -o "$d/$n.t" __GCC__ "$@"
rc=$?
echo "$(tail -n1 "$d/$n.t") | $*" > "$d/$n.log"
exit $rc
'''


def one_build(ail, source, syntax, work, wrapper):
    shutil.rmtree(work, ignore_errors=True)
    for sub in ('cache', 'tmp', 'w'):
        (work / sub).mkdir(parents=True)
    env = dict(os.environ, AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'), PIPE_CC=str(wrapper), WRAP_DIR=str(work / 'w'))
    env.pop('AIL_NO_CACHE', None)
    cmd = [sys.executable, '-B', str(ail), 'compile', str(source), '-o', str(work / 'prog')]
    if syntax:
        cmd[5:5] = ['--syntax', syntax]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    done = subprocess.run(cmd, env=env, capture_output=True, text=True)
    wall = time.perf_counter() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime
    gcc_wall = gcc_cpu = 0.0
    main_log = None
    for log in sorted(glob.glob(str(work / 'w' / '*.log')), key=lambda p: int(Path(p).stem)):
        times, _, args = Path(log).read_text().partition('|')
        e, u, s = (float(x) for x in times.split())
        gcc_wall += e
        gcc_cpu += u + s
        if '.c' in args and ' -o ' in args:
            main_log = (log, args.strip())
    return dict(ok=done.returncode == 0, wall=wall, cpu=cpu, gcc_cpu=gcc_cpu, gcc_wall=gcc_wall, err=done.stderr[-300:],
                main=main_log, work=work, binary=(work / 'prog').stat().st_size if (work / 'prog').is_file() else 0)


def cpu_of(cmd):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    subprocess.run(cmd, capture_output=True)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime


def gcc_phases(run):
    """Re-run the last build's compile with -fsyntax-only / -c / -ftime-report on the saved C."""
    log, args = run['main']
    c_file = Path(log).with_suffix('.c')
    flags = [a for a in args.split() if a.startswith('-O') or a.startswith('-f') or a.startswith('-m') or a == '-pthread']
    flags = [f for f in flags if not f.startswith('-fdiagnostics')]
    best = lambda cmd: min(cpu_of(cmd) for _ in range(3))
    syntax = best(['gcc', *flags, '-fsyntax-only', '-w', str(c_file)])
    obj = run['work'] / 'p.o'
    compile_only = best(['gcc', *flags, '-w', '-c', '-o', str(obj), str(c_file)])
    report = subprocess.run(['gcc', *flags, '-w', '-ftime-report', '-c', '-o', str(obj), str(c_file)], capture_output=True, text=True).stderr
    phases = {}
    for m in re.finditer(r'^ (phase \w[\w ]*?|TOTAL)\s*:\s*([\d.]+)\s*\(\s*\d+%\)\s*([\d.]+)', report, re.M):
        phases[m.group(1).strip()] = float(m.group(2))
    text = 0
    size = subprocess.run(['size', str(obj)], capture_output=True, text=True).stdout.split('\n')
    if len(size) > 1 and size[1].split():
        text = int(size[1].split()[0])
    return dict(c_bytes=c_file.stat().st_size, syntax=syntax, compile_only=compile_only, phases=phases, text=text)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source')
    parser.add_argument('--syntax', choices=('python', 'ail'), default=None)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--repo', type=Path, default=REPO, help='checkout whose compiler to measure (default: this one)')
    args = parser.parse_args()
    ail = args.repo / 'AIL_CURRENT' / 'ail_chatgpt.py'
    syntax = args.syntax or ('python' if args.source.endswith('.py') else None)
    with tempfile.TemporaryDirectory(prefix='compile-phases-') as scratch:
        scratch = Path(scratch)
        gcc = shutil.which('gcc') or '/usr/bin/gcc'
        wrapper = scratch / 'cc_wrap.sh'
        wrapper.write_text(WRAPPER.replace('__GCC__', gcc))
        wrapper.chmod(0o755)
        runs = [one_build(ail, args.source, syntax, scratch / ('run%d' % i), wrapper) for i in range(args.runs)]
        bad = [r for r in runs if not r['ok']]
        if bad:
            print('build failed:', bad[0]['err'])
            return 1
        med = lambda key: statistics.median(r[key] for r in runs)
        spread = lambda key: '%.2f-%.2f' % (min(r[key] for r in runs), max(r[key] for r in runs))
        total, gcc_cpu = med('cpu'), med('gcc_cpu')
        print('%s  (%d cold builds, CPU seconds, median [min-max])' % (args.source, args.runs))
        print('  total          %6.2f  [%s]   wall %.2f' % (total, spread('cpu'), med('wall')))
        print('  python         %6.2f   %2.0f%%   CLI, front end, C emission' % (total - gcc_cpu, 100 * (total - gcc_cpu) / total))
        print('  gcc            %6.2f   %2.0f%%   [%s]' % (gcc_cpu, 100 * gcc_cpu / total, spread('gcc_cpu')))
        info = gcc_phases(runs[-1])
        print('  generated C    %d bytes, code (text) %d bytes, executable %d bytes' % (info['c_bytes'], info['text'], runs[-1]['binary']))
        print('  gcc, one compile of that C: -fsyntax-only %.2f (read the text), full -c %.2f' % (info['syntax'], info['compile_only']))
        ph = info['phases']
        if ph:
            print('  gcc -ftime-report (usr): ' + ', '.join('%s %.2f' % (k, v) for k, v in ph.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
