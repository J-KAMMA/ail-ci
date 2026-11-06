#!/usr/bin/env python3
"""Call libwordcount.so through ctypes and compare every result with the module itself.

    python3 examples/embed/wordcount/use_ctypes.py [--lib build/wordcount/libwordcount.so]

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
    spec = importlib.util.spec_from_file_location("wordcount_mod", HERE / "mod.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def as_buf(data):
    return (ctypes.c_char * len(data)).from_buffer_copy(data)


def bind(lib):
    lib.wordcount_init.restype = ctypes.c_int
    lib.wordcount_shutdown.restype = None
    lib.wordcount_last_error.restype = ctypes.c_char_p
    lib.wordcount_word_count.argtypes = [ctypes.POINTER(ctypes.c_char), ctypes.c_size_t, I64P]
    lib.wordcount_word_count.restype = ctypes.c_int


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lib", help="path to libwordcount.so")
    options = parser.parse_args()
    temp = None
    if options.lib:
        library = Path(options.lib)
    else:
        temp = tempfile.TemporaryDirectory(prefix="ail-ctypes-wordcount-")
        built = subprocess.run(
            [sys.executable, "-B", str(CLI), "build", str(HERE / "mod.py"), "-o", temp.name,
             "--shared"], capture_output=True, text=True)
        if built.returncode != 0:
            print(built.stderr, file=sys.stderr)
            return 1
        library = Path(temp.name) / "libwordcount.so"
    module = load_module()
    lib = ctypes.CDLL(str(library))
    bind(lib)
    lib.wordcount_init()
    ok = True

    cases = (("", ""), ("one", "one"), ("  one two\\tthree\\nfour  ", "  one two\tthree\nfour  "),
             ("a,b c-d", "a,b c-d"))
    for label, text in cases:
        payload = text.encode("utf-8")
        count = ctypes.c_int64()
        status = lib.wordcount_word_count(as_buf(payload), len(payload), ctypes.byref(count))
        want = module.word_count(text)
        print('word_count("%s") = %d' % (label, count.value))
        ok &= status == 0 and count.value == want

    if not ok:
        print("wordcount example: ctypes results differ from the module", file=sys.stderr)
    lib.wordcount_shutdown()
    if temp is not None:
        temp.cleanup()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
