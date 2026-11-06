#!/usr/bin/env python3
"""PIPE_CC shim used only by lab/tcc/run.py.

Runs tcc on the generated C the way the AIL build would, but:

* prepends lab/tcc/tcc_prelude.h to every .c input (the overflow builtins), and
* drops the flags tcc does not accept (-f*, -W*, -Wl,--gc-sections, ...),
  keeping -I/-D/-U/-L/-l/-O/-g/-std= and -c/-shared/-static/-pthread.

Nothing here is part of a normal build; the default C compiler is unchanged.
"""
import os
import pathlib
import subprocess
import sys

KEEP_EXACT = ('-c', '-shared', '-static', '-pthread')
KEEP_PREFIX = ('-I', '-D', '-U', '-L', '-l', '-O', '-g', '-std=')
KEEP_WITH_VALUE = ('-I', '-D', '-U', '-L', '-l')
DROP_WITH_VALUE = ('-MF', '-MT', '-MQ', '-x', '-include', '-isystem', '-iquote')


def keep(argument):
    return argument in KEEP_EXACT or argument.startswith(KEEP_PREFIX)


def main():
    args = sys.argv[1:]
    tcc = os.environ['TCC_BIN']
    prelude = pathlib.Path(os.environ['TCC_PRELUDE']).read_text(encoding='utf-8')
    rewritten = []
    i = 0
    while i < len(args):
        argument = args[i]
        if argument == '-o':
            rewritten += [argument, args[i + 1]]
            i += 2
            continue
        if argument.endswith('.c'):
            path = pathlib.Path(argument)
            patched = path.with_name(path.name + '.tcc.c')
            patched.write_text(prelude + path.read_text(encoding='utf-8', errors='surrogateescape'),
                               encoding='utf-8', errors='surrogateescape')
            rewritten.append(str(patched))
            i += 1
            continue
        if argument.startswith('-'):
            if argument in DROP_WITH_VALUE:
                i += 2
                continue
            if argument in KEEP_WITH_VALUE and i + 1 < len(args):
                rewritten += [argument, args[i + 1]]
                i += 2
                continue
            if keep(argument):
                rewritten.append(argument)
            i += 1
            continue
        rewritten.append(argument)
        i += 1
    return subprocess.run([tcc, *rewritten]).returncode


if __name__ == '__main__':
    sys.exit(main())
