#!/usr/bin/env python3
"""Run one task program `reps` times inside one PyPy process and time each run.

    pypy3 lab/compare_rival/pypy_warm.py SRC REPS EXPECTED_OUT EXPECTED_EXIT [STDIN|-] OUT.json [args...]

The timed section is `exec` of the already-compiled source, so the interpreter start-up and
`compile()` of the first run are excluded; run i gets a fresh globals dict, a fresh stdin over the
same input bytes and its own stdout file.  The JSON report carries each run's seconds and whether
its stdout/exit status equals the CPython reference's, so `run.py` can report the 5th run in a
process -- PyPy's JIT needs that warm-up -- next to the plain wall time of a fresh process.
"""
import io
import json
import os
import sys
import time


def _stdin(path):
    data = open(path, 'rb').read() if path not in ('', '-') else b''
    return io.TextIOWrapper(io.BytesIO(data), encoding='utf-8', errors='surrogateescape')


def main():
    src, reps, exp_out, exp_exit, stdin_path, out_json = sys.argv[1:7]
    prog_args = sys.argv[7:]
    reps = int(reps)
    with open(src, 'rb') as f:
        code = compile(f.read(), src, 'exec')
    with open(exp_out, 'rb') as f:
        expected = f.read()
    expected_exit = int(exp_exit)
    saved = os.dup(1)
    runs = []
    try:
        for i in range(reps):
            got = os.path.join(os.path.dirname(out_json) or '.', 'warm-run-%d.out' % i)
            sys.stdin = _stdin(stdin_path)
            sys.argv = [src] + prog_args
            sys.stdout.flush()
            sys.stderr.flush()
            fd = os.open(got, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            os.dup2(fd, 1)
            os.close(fd)
            start = time.perf_counter()
            status = 0
            try:
                exec(code, {'__name__': '__main__', '__file__': src, '__builtins__': __builtins__})
            except SystemExit as exc:
                status = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            except BaseException as exc:                      # a crash is a result, not a harness bug
                status = 1
                sys.stderr.write('warm run %d raised %s: %s\n' % (i + 1, type(exc).__name__, exc))
            sys.stdout.flush()
            sys.stderr.flush()
            elapsed = time.perf_counter() - start
            os.dup2(saved, 1)
            with open(got, 'rb') as f:
                same = f.read() == expected and status == expected_exit
            runs.append(dict(seconds=round(elapsed, 6), exit=status, match=same))
    finally:
        os.dup2(saved, 1)
        os.close(saved)
    with open(out_json, 'w') as f:
        json.dump(dict(src=src, reps=reps, runs=runs, last_match=runs[-1]['match'] if runs else False), f)


if __name__ == '__main__':
    main()
