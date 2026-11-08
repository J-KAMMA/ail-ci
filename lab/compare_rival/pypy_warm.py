#!/usr/bin/env python3
"""Run one task program `reps` times inside one PyPy process and time each run.

    pypy3 lab/compare_rival/pypy_warm.py SRC REPS EXPECTED_OUT EXPECTED_EXIT [STDIN|-] OUT.json [args...]

The first run executes the source (which calls its own `main()` at the bottom); runs 2..REPS call the
module's `main()` again in the **same** module state, with a fresh stdin over the same input bytes,
its own stdout file and `sys.argv` reset.  That is what a long-lived process (a server, a notebook)
does, and it is the only way PyPy's JIT sees the same code twice: re-executing the source with fresh
globals creates new function objects and the JIT discards its traces, which makes later runs *slower*
than the first (measured on a 40x3M-iteration loop: 133 ms re-exec vs 366 ms, against 365 ms for the
first import and ~9 ms per repeat call in one module state).

Every run's stdout and exit status are compared with the CPython reference, so a warm run that
computes something else cannot pass silently.  A driver with no `main` in its module globals is
re-executed instead (`mode: "re-exec"` in the report), which is the best that driver allows.
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
    ns = None
    mode = 'one-import'
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
            entry = ns.get('main') if i and ns else None
            if i and not callable(entry) and mode == 'one-import':
                mode = 're-exec'
            start = time.perf_counter()
            status = 0
            try:
                if callable(entry):
                    entry()
                else:
                    ns = {'__name__': '__main__', '__file__': src, '__builtins__': __builtins__}
                    exec(code, ns)
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
        json.dump(dict(src=src, reps=reps, mode=mode, runs=runs,
                       last_match=runs[-1]['match'] if runs else False), f)


if __name__ == '__main__':
    main()
