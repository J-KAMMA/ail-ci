#!/usr/bin/env python3
"""Call libtransform.so through ctypes and compare every result with the module itself.

    python3 examples/embed/transform/use_ctypes.py [--lib build/transform/libtransform.so]

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


def load_module():
    spec = importlib.util.spec_from_file_location("transform_mod", HERE / "mod.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def as_buf(data):
    return (ctypes.c_char * len(data)).from_buffer_copy(data)


def bind(lib):
    lib.transform_init.restype = ctypes.c_int
    lib.transform_shutdown.restype = None
    lib.transform_last_error.restype = ctypes.c_char_p
    lib.transform_transform.argtypes = [ctypes.POINTER(ctypes.c_char), ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_char), ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_size_t)]
    lib.transform_transform.restype = ctypes.c_int


def call_text(lib, text, cap):
    """(status, required length, the bytes written)."""
    payload = text.encode("utf-8")
    out = ctypes.create_string_buffer(cap)
    length = ctypes.c_size_t()
    status = lib.transform_transform(as_buf(payload), len(payload), out, cap, ctypes.byref(length))
    return status, length.value, out.raw[:min(cap, length.value)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lib", help="path to libtransform.so")
    options = parser.parse_args()
    temp = None
    if options.lib:
        library = Path(options.lib)
    else:
        temp = tempfile.TemporaryDirectory(prefix="ail-ctypes-transform-")
        built = subprocess.run(
            [sys.executable, "-B", str(CLI), "build", str(HERE / "mod.py"), "-o", temp.name,
             "--shared"], capture_output=True, text=True)
        if built.returncode != 0:
            print(built.stderr, file=sys.stderr)
            return 1
        library = Path(temp.name) / "libtransform.so"
    module = load_module()
    lib = ctypes.CDLL(str(library))
    bind(lib)
    lib.transform_init()
    ok = True

    for text in ("Hello World 42", "ail embed", "", "already UPPER", "héllo wörld"):
        status, _, value = call_text(lib, text, 64)
        want = module.transform(text).encode("utf-8")
        print('transform("%s") = "%s"' % (text, value.decode("utf-8")))
        ok &= status == 0 and value == want

    status, required, _ = call_text(lib, "Hello World 42", 4)
    ok &= status == 2 and required == 14
    if not ok:
        print("transform example: ctypes results differ from the module", file=sys.stderr)
    lib.transform_shutdown()
    if temp is not None:
        temp.cleanup()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
