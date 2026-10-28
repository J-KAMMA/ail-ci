# -*- coding: utf-8 -*-
# prelude_tempfile.py -- the subset of `tempfile` that tempfilelib.py lowers onto (library batch 22).
#
# Plain Python in the subset both builds accept. The names are the compiler's own (`_ail_tf_*`); the
# rewrite fills the call defaults at compile time, so no signature here has a default. A name is eight
# characters from CPython's tempfile alphabet; CPython's own sequence is random and its exact text is not
# part of the API.

import os
import time

TMP_MAX = 238328
_counter = 0
_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"


def _ail_tf_writable(d: str) -> bool:
    for i in range(100):
        name = os.path.join(d, "tmp" + _ail_tf_rand8())
        try:
            os.mkdir(name, 0o700)
        except FileExistsError:
            continue
        except OSError:
            return False
        os.rmdir(name)
        return True
    return False


def _ail_tf_pick(d: str) -> str:
    if d == "":
        return ""
    where = d
    if where != ".":
        where = os.path.abspath(where)
    if _ail_tf_writable(where):
        return where
    return ""


def _ail_tf_default_dir() -> str:
    for key in ["TMPDIR", "TEMP", "TMP"]:
        found = _ail_tf_pick(os.environ.get(key, ""))
        if found != "":
            return found
    for standard in ["/tmp", "/var/tmp", "/usr/tmp"]:
        found = _ail_tf_pick(standard)
        if found != "":
            return found
    return _ail_tf_pick(os.getcwd())


def _ail_tf_gettempdir() -> str:
    found = _ail_tf_default_dir()
    if found == "":
        raise FileNotFoundError("No usable temporary directory found")
    return found


def _ail_tf_gettempprefix() -> str:
    return "tmp"


def _ail_tf_gettempdirb() -> bytes:
    return _ail_tf_gettempdir().encode()


def _ail_tf_gettempprefixb() -> bytes:
    return b"tmp"


def _ail_tf_rand8() -> str:
    global _counter
    _counter = _counter + 1
    x = (time.time_ns() + _counter * 1000003) % 2147483648
    out = ""
    for i in range(8):
        x = (x * 1103515245 + 12345) % 2147483648
        out = out + _CHARS[(x >> 16) % 63]
    return out


def _ail_tf_mktemp(suffix: str, prefix: str, dir: str) -> str:
    for attempt in range(TMP_MAX):
        name = os.path.join(dir, prefix + _ail_tf_rand8() + suffix)
        if not os.path.exists(name):
            return name
    raise FileExistsError("No usable temporary filename found")


def _ail_tf_mkdtemp(suffix: str, prefix: str, dir: str) -> str:
    for attempt in range(TMP_MAX):
        name = os.path.join(dir, prefix + _ail_tf_rand8() + suffix)
        try:
            os.mkdir(name, 0o700)
        except FileExistsError:
            continue
        return os.path.abspath(name)
    raise FileExistsError("No usable temporary directory name found")


def _ail_tf_rmtree(path: str) -> None:
    names = os.listdir(path)
    for name in names:
        full = os.path.join(path, name)
        if os.path.isdir(full) and not os.path.islink(full):
            _ail_tf_rmtree(full)
        else:
            os.remove(full)
    os.rmdir(path)


def _ail_tf_cleanup(name: str, ignore: bool) -> None:
    if not os.path.exists(name):
        return
    if ignore:
        try:
            _ail_tf_rmtree(name)
        except OSError:
            pass
    else:
        _ail_tf_rmtree(name)


class _AilTemporaryDirectory:
    def __init__(self, name: str, ignore_cleanup_errors: bool, delete: bool):
        self.name = name
        self._ignore = ignore_cleanup_errors
        self._delete = delete

    def __enter__(self) -> str:
        return self.name

    def cleanup(self) -> None:
        _ail_tf_cleanup(self.name, self._ignore)

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._delete:
            self.cleanup()
        return False


def _ail_tf_new(suffix: str, prefix: str, dir: str, ignore_cleanup_errors: bool, delete: bool) -> _AilTemporaryDirectory:
    return _AilTemporaryDirectory(_ail_tf_mkdtemp(suffix, prefix, dir), ignore_cleanup_errors, delete)
