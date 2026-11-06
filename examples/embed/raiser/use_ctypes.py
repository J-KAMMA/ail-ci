#!/usr/bin/env python3
"""Call libraiser.so through ctypes and compare every result with the module itself.

    python3 examples/embed/raiser/use_ctypes.py [--lib build/raiser/libraiser.so]

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
    spec = importlib.util.spec_from_file_location("raiser_mod", HERE / "mod.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bind(lib):
    lib.raiser_init.restype = ctypes.c_int
    lib.raiser_shutdown.restype = None
    lib.raiser_last_error.restype = ctypes.c_char_p
    lib.raiser_checked_div.argtypes = [ctypes.c_int64, ctypes.c_int64, I64P]
    lib.raiser_checked_div.restype = ctypes.c_int
    lib.raiser_require_positive.argtypes = [ctypes.c_int64, I64P]
    lib.raiser_require_positive.restype = ctypes.c_int


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lib", help="path to libraiser.so")
    options = parser.parse_args()
    temp = None
    if options.lib:
        library = Path(options.lib)
    else:
        temp = tempfile.TemporaryDirectory(prefix="ail-ctypes-raiser-")
        built = subprocess.run(
            [sys.executable, "-B", str(CLI), "build", str(HERE / "mod.py"), "-o", temp.name,
             "--shared"], capture_output=True, text=True)
        if built.returncode != 0:
            print(built.stderr, file=sys.stderr)
            return 1
        library = Path(temp.name) / "libraiser.so"
    module = load_module()
    lib = ctypes.CDLL(str(library))
    bind(lib)
    lib.raiser_init()
    ok = True

    value = ctypes.c_int64()
    status = lib.raiser_checked_div(7, 2, ctypes.byref(value))
    print("checked_div(7, 2) = %d" % value.value)
    ok &= status == 0 and value.value == module.checked_div(7, 2)

    try:
        module.checked_div(1, 0)
        want = None
    except ValueError as error:
        want = b"ValueError: " + str(error).encode("utf-8")
    status = lib.raiser_checked_div(1, 0, ctypes.byref(value))
    error = lib.raiser_last_error()
    if status == 1 and error == want:
        print("error: %s" % error.decode("utf-8"))
    else:
        ok = False

    try:
        module.require_positive(-3)
        want = None
    except ValueError as error:
        want = b"ValueError: " + str(error).encode("utf-8")
    status = lib.raiser_require_positive(-3, ctypes.byref(value))
    error = lib.raiser_last_error()
    if status == 1 and error == want:
        print("error: %s" % error.decode("utf-8"))
    else:
        ok = False

    status = lib.raiser_require_positive(5, ctypes.byref(value))
    print("require_positive(5) = %d" % value.value)
    ok &= status == 0 and value.value == module.require_positive(5)

    if not ok:
        print("raiser example: ctypes results differ from the module", file=sys.stderr)
    lib.raiser_shutdown()
    if temp is not None:
        temp.cleanup()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
