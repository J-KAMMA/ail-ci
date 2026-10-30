#!/usr/bin/env python3
"""C compiler wrapper for AIL (set PIPE_CC to this file).

AIL runs `<cc> -O2 -fno-tree-slp-vectorize ... -o OUT program.c`. This wrapper replaces the compiler and
the -O2 flag from the environment, so the same generated C is built with different flags:

  FLAGS_CC     compiler command (shell words), default gcc
  FLAGS_OPT    replaces -O2 (shell words), default -O2
  FLAGS_EXTRA  appended flags (shell words)
  FLAGS_PGO    gen | use: two-phase profile guided build of non -c invocations
  FLAGS_FIXDIR directory for the PGO build (stable source/object names so profile data is found)
"""
import os, shlex, shutil, subprocess, sys


def main(argv):
    cc = shlex.split(os.environ.get('FLAGS_CC', 'gcc'))
    opt = shlex.split(os.environ.get('FLAGS_OPT', '-O2'))
    extra = shlex.split(os.environ.get('FLAGS_EXTRA', ''))
    pgo = os.environ.get('FLAGS_PGO', '')
    args = []
    for a in argv:
        args.extend(opt if a == '-O2' else [a])
    if pgo and '-c' not in args and '-o' in args:
        fix = os.environ['FLAGS_FIXDIR']
        os.makedirs(fix, exist_ok=True)
        i = args.index('-o')
        target = args[i + 1]
        key = os.path.basename(target)
        args[i + 1] = os.path.join(fix, key + '.bin')
        for j, a in enumerate(args):
            if a.endswith('.c') and j != i + 1:
                dst = os.path.join(fix, key + '.c')
                shutil.copyfile(a, dst)
                args[j] = dst
        if pgo == 'gen':
            extra += ['-fprofile-generate', '-fprofile-update=single']
        else:
            extra += ['-fprofile-use', '-fprofile-correction', '-Wno-missing-profile', '-Wno-coverage-mismatch']
        rc = subprocess.call(cc + args + extra)
        if rc == 0:
            shutil.copyfile(args[i + 1], target)
            shutil.copymode(args[i + 1], target)
        return rc
    return subprocess.call(cc + args + extra)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
