#!/usr/bin/env python3
"""Run `pyc.py` with low-overhead timers around its top-level passes.

`timed_outer.py` makes `ail_chatgpt._compiler_python()` start this file instead
of `pyc.py`; the first argument is the real pyc.py path, the rest are its
arguments.  Only wall-clock `perf_counter` calls are added around the driver's
own pass boundaries, so the generated C and every decision are unchanged.

Writes `$FE_TIME_OUT_INNER` as JSON: import time, the time from the end of the
imports to process exit, and total/exclusive time plus call count for each
wrapped function.  Exclusive subtracts nested wrapped calls, so the labels can
be summed without double counting.
"""
import ast
import builtins
import json
import os
import sys
import time

REAL_IMPORT = builtins.__import__
TIMERS = {}
STACK = []


def timed(label, function):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        STACK.append([label, start, 0.0])
        try:
            return function(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            frame = STACK.pop()
            record = TIMERS.setdefault(label, {'total': 0.0, 'exclusive': 0.0, 'calls': 0})
            record['total'] += elapsed
            record['exclusive'] += elapsed - frame[2]
            record['calls'] += 1
            if STACK:
                STACK[-1][2] += elapsed
    wrapper.__name__ = getattr(function, '__name__', label)
    wrapper.__doc__ = getattr(function, '__doc__', None)
    return wrapper


def wrap(module, name, label):
    function = getattr(module, name, None)
    if function is not None:
        setattr(module, name, timed(label, function))


def _import_hook(name, *args, **kwargs):
    module = REAL_IMPORT(name, *args, **kwargs)
    if name == 'pyboxed2' and module is not None:
        if not getattr(module, '_fe_timed', False):
            wrap(module, 'build', 'general_emit')
            module._fe_timed = True
    return module


def main():
    started = time.perf_counter()
    pyc_path = sys.argv[1]
    sys.path.insert(0, os.path.dirname(os.path.abspath(pyc_path)))
    import pyc
    imported = time.perf_counter()

    for name, label in (
            ('build_cached', 'build_cached'),
            ('build', 'build'),
            ('to_c', 'typed_emit'),
            ('fold_int_constants', 'fold_int_constants'),
            ('_refuse_static_big_calls', 'refuse_static_big_calls'),
            ('_python_defs_only_runs_nothing', 'python_defs_only_runs_nothing'),
            ('_refuse_big_capable', 'refuse_big_capable'),
            ('_refuse_typed_big_store', 'refuse_typed_big_store'),
            ('_cc', 'cc'),
    ):
        wrap(pyc, name, label)
    wrap(ast, 'parse', 'parse')
    builtins.__import__ = _import_hook

    main_started = time.perf_counter()
    try:
        return pyc.main(sys.argv[2:])
    finally:
        main_ended = time.perf_counter()
        out = os.environ.get('FE_TIME_OUT_INNER')
        if out:
            data = {'import': round(imported - started, 6),
                    'main': round(main_ended - main_started, 6),
                    'timers': TIMERS}
            try:
                with open(out, 'w', encoding='utf8') as stream:
                    json.dump(data, stream)
            except OSError:
                pass


if __name__ == '__main__':
    sys.exit(main())
