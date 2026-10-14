"""Reproduce the numbers in README.md on this machine, or find out they do not reproduce.

    python3 bench.py

Every arm must print the same line before any of them is timed; if they disagree the run stops and
says so, because a faster answer that differs is not a faster answer. The Python arms are skipped
rather than faked if numpy is missing, and the report says which arms ran.

Deployed bytes are the whole dependency closure: for the program, itself, statically linked; for the
Python arms, the interpreter and its standard library, plus numpy where it is used. The comparison
this makes is between what a user installs, not between two functions.
"""
import pathlib, subprocess, sys, sysconfig, time

import build_app

N = 5_000_000
REPS = 15
TASK = 'sum where odd squares, count where negative, max abs over xs'
WORK = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'benchwork')

NUMPY_ARM = '''import numpy as np, sys
x = np.fromfile(sys.argv[1], dtype=np.int64)
odd = x[x % 2 != 0]
print(int((odd * odd).sum()), int((x < 0).sum()), int(np.abs(x).max()))
'''

PY_ARM = '''import array, sys
x = array.array('q')
with open(sys.argv[1], 'rb') as f:
    x.frombytes(f.read())
s = c = m = 0
for v in x:
    if v % 2 != 0:
        s += v * v
    if v < 0:
        c += 1
    a = -v if v < 0 else v
    if a > m:
        m = a
print(s, c, m)
'''


def weigh(*paths):
    total = 0
    for p in paths:
        p = pathlib.Path(p)
        if not p.exists():
            continue
        total += p.stat().st_size if p.is_file() else sum(
            f.stat().st_size for f in p.rglob('*') if f.is_file() and not f.is_symlink())
    return total


def best(cmd):
    t_best, out = None, None
    for _ in range(REPS):
        t = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True)
        d = time.perf_counter() - t
        if r.returncode:
            raise SystemExit('%s failed:\n%s' % (' '.join(map(str, cmd)), r.stderr[-400:]))
        t_best, out = (d if t_best is None else min(t_best, d)), r.stdout.strip()
    return t_best, out


def numpy_weight():
    try:
        import numpy
    except ImportError:
        return None
    p = pathlib.Path(numpy.__file__).parent
    return weigh(p, p.parent / 'numpy.libs')


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = WORK / 'data.bin'
    if not data.exists() or data.stat().st_size != N * 8:
        import random, array
        r = random.Random(20260913)
        array.array('q', (r.randint(-10_000, 10_000) for _ in range(N))).tofile(data.open('wb'))
    app = build_app.build(TASK, WORK / 'app')
    (WORK / 'arm_numpy.py').write_text(NUMPY_ARM)
    (WORK / 'arm_python.py').write_text(PY_ARM)
    subprocess.run(['cat', str(data)], stdout=subprocess.DEVNULL)      # warm the page cache

    interp = weigh(sys.executable, sysconfig.get_path('stdlib'))
    npw = numpy_weight()
    arms = [('static binary', [str(app), str(data)], weigh(app))]
    if npw is not None:
        arms.append(('python + numpy', [sys.executable, str(WORK / 'arm_numpy.py'), str(data)],
                     interp + npw))
    arms.append(('python only', [sys.executable, str(WORK / 'arm_python.py'), str(data)], interp))

    rows = []
    for name, cmd, size in arms:
        secs, out = best(cmd)
        rows.append((name, size, secs, out))
    if len({r[3] for r in rows}) != 1:
        print('THE ARMS DISAGREE -- not timing anything else')
        for name, _, _, out in rows:
            print('   %-16s %s' % (name, out))
        return 1

    print('%d int64 (%.0f MB), best of %d, page cache warm, answers identical\n'
          % (N, N * 8 / 1e6, REPS))
    print('%-16s %14s %10s' % ('arm', 'deployed B', 'best s'))
    for name, size, secs, _ in rows:
        print('%-16s %14d %10.4f' % (name, size, secs))
    base = rows[0]
    print()
    for name, size, secs, _ in rows[1:]:
        print('   vs %-14s %6.1fx heavier, %6.2fx slower' % (name, size / base[1], secs / base[2]))
    if npw is None:
        print('\n   numpy is not installed here, so that arm did not run')
    print('\n   answer: %s' % base[3])
    return 0


if __name__ == '__main__':
    sys.exit(main())
