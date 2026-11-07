#!/usr/bin/env python3
"""Run `ail_chatgpt.py <args>` with low-overhead timers on the outer pass boundary.

This is the timing counterpart of `timed_inner.py`: it imports the normal
driver, wraps `_load_sources`, and makes `_compiler_python()` start
`timed_inner.py` (which then runs the real `pyc.py`).  Nothing about the
compiler's input, output or decisions changes.

Writes `$FE_TIME_OUT_OUTER` as JSON: import time, main wall, and total /
exclusive time plus calls for each wrapped outer function.
"""
import ast
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'AIL_CURRENT'))

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
    return wrapper


def wrap(module, name, label):
    function = getattr(module, name, None)
    if function is not None:
        setattr(module, name, timed(label, function))


def main():
    started = time.perf_counter()
    import ail_chatgpt
    imported = time.perf_counter()

    for name, label in (('_load_sources', 'load_sources'),
                        ('_ffi_session', 'ffi_session'),
                        ('_build_cache', 'build_cache')):
        function = getattr(ail_chatgpt, name, None)
        if function is not None:
            setattr(ail_chatgpt, name, timed(label, function))
    wrap(ast, 'parse', 'parse')

    inner = os.path.join(HERE, 'timed_inner.py')

    def compiler_python():
        return [sys.executable, inner]

    ail_chatgpt._compiler_python = compiler_python

    main_started = time.perf_counter()
    try:
        return ail_chatgpt.main(sys.argv[1:])
    finally:
        main_ended = time.perf_counter()
        out = os.environ.get('FE_TIME_OUT_OUTER')
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
