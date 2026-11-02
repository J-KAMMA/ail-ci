#!/usr/bin/env python3
"""PIPE_CC shim for lab/fecache/measure.py.

WRAP_MODE=split turns one compile+link driver call into `-c` and a link and times each half.
Every invocation appends one JSON line to $WRAP_LOG; $WRAP_SAVE_C receives the C text.
"""
import json
import os
import pathlib
import subprocess
import sys
import time


def record(row):
    path = os.environ.get('WRAP_LOG')
    if not path:
        return
    with open(path, 'a', encoding='utf-8') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')


def main():
    args = list(sys.argv[1:])
    cc = os.environ['WRAP_CC']
    mode = os.environ.get('WRAP_MODE', 'single')
    sources = [a for a in args if a.endswith('.c')]
    output = args[args.index('-o') + 1] if '-o' in args else None
    save = os.environ.get('WRAP_SAVE_C')
    if save and sources:
        directory = pathlib.Path(save)
        directory.mkdir(parents=True, exist_ok=True)
        for source in sources:
            path = pathlib.Path(source)
            (directory / path.name).write_bytes(path.read_bytes())
    split = mode == 'split' and len(sources) == 1 and output and '-c' not in args
    if split:
        source = sources[0]
        obj = str(pathlib.Path(output).with_name(pathlib.Path(output).name + '.o'))
        at = args.index('-o')
        compile_args = args[:at] + ['-c', '-o', obj] + args[at + 2:]
        start = time.perf_counter()
        first = subprocess.run([cc, *compile_args])
        compiled = time.perf_counter() - start
        if first.returncode:
            record(dict(kind='split', compile=compiled, link=None, total=compiled, args=args, cc=cc, rc=first.returncode))
            return first.returncode
        link_args = [obj if a == source else a for a in args]
        start = time.perf_counter()
        second = subprocess.run([cc, *link_args])
        linked = time.perf_counter() - start
        record(dict(kind='split', compile=compiled, link=linked, total=compiled + linked, args=args, cc=cc, rc=second.returncode))
        return second.returncode
    start = time.perf_counter()
    result = subprocess.run([cc, *args])
    elapsed = time.perf_counter() - start
    kind = 'compile' if '-c' in args else 'link' if not sources else 'single'
    record(dict(kind=kind, compile=elapsed if kind == 'compile' else None,
                link=elapsed if kind == 'link' else None, total=elapsed, args=args, cc=cc, rc=result.returncode))
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
