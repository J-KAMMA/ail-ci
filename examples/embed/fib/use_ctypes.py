#!/usr/bin/env python3
"""Call libfib.so through ctypes and compare every result with the module itself.

    python3 examples/embed/fib/use_ctypes.py [--lib build/fib/libfib.so]

Without --lib the shared library is built into a temporary directory with
`AIL_CURRENT/ail_embed.py build mod.py -o DIR --shared`.
"""
import argparse
import ctypes
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CLI = REPO / "AIL_CURRENT" / "ail_embed.py"
I64P = ctypes.POINTER(ctypes.c_int64)


def load_module():
    spec = importlib.util.spec_from_file_location("fib_mod", HERE / "mod.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def as_buf(data):
    return (ctypes.c_char * len(data)).from_buffer_copy(data)


def bind(lib):
    lib.fib_init.restype = ctypes.c_int
    lib.fib_shutdown.restype = None
    lib.fib_last_error.restype = ctypes.c_char_p
    lib.fib_fib.argtypes = [ctypes.c_int64, I64P]
    lib.fib_fib.restype = ctypes.c_int
    lib.fib_gcd.argtypes = [ctypes.c_int64, ctypes.c_int64, I64P]
    lib.fib_gcd.restype = ctypes.c_int
    lib.fib_sum_line.argtypes = [ctypes.POINTER(ctypes.c_char), ctypes.c_size_t, I64P]
    lib.fib_sum_line.restype = ctypes.c_int


def call_int(lib, function, args):
    value = ctypes.c_int64()
    status = function(*args, ctypes.byref(value))
    return status, value.value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lib", help="path to libfib.so")
    options = parser.parse_args()
    temp = None
    if options.lib:
        library = Path(options.lib)
    else:
        temp = tempfile.TemporaryDirectory(prefix="ail-ctypes-fib-")
        built = subprocess.run(
            [sys.executable, "-B", str(CLI), "build", str(HERE / "mod.py"), "-o", temp.name,
             "--shared"], capture_output=True, text=True)
        if built.returncode != 0:
            print(built.stderr, file=sys.stderr)
            return 1
        library = Path(temp.name) / "libfib.so"
    module = load_module()
    lib = ctypes.CDLL(str(library))
    bind(lib)
    lib.fib_init()
    ok = True

    for n in (0, 1, 10, 92):
        status, value = call_int(lib, lib.fib_fib, (n,))
        want = module.fib(n)
        print("fib(%d) = %d" % (n, value))
        ok &= status == 0 and value == want

    for a, b in ((48, 18), (-48, 18)):
        status, value = call_int(lib, lib.fib_gcd, (a, b))
        want = module.gcd(a, b)
        print("gcd(%d, %d) = %d" % (a, b, value))
        ok &= status == 0 and value == want

    for text in ("a12 b34 c5", "no digits"):
        payload = text.encode("utf-8")
        status, value = call_int(lib, lib.fib_sum_line, (as_buf(payload), len(payload)))
        want = module.sum_line(text)
        print('sum_line("%s") = %d' % (text, value))
        ok &= status == 0 and value == want

    value = ctypes.c_int64()
    status = lib.fib_fib(93, ctypes.byref(value))
    error = lib.fib_last_error()
    ok &= status == 1 and error.startswith(b"OverflowError: ")
    if not ok:
        print("fib example: ctypes results differ from the module", file=sys.stderr)
    lib.fib_shutdown()
    if temp is not None:
        temp.cleanup()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
