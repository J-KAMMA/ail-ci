"""Platform facts the tests share, so a test that needs a Linux-only tool skips (or adapts) in one
place and says why. Not part of the compiler: nothing outside test_*.py imports this."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

DARWIN = sys.platform == 'darwin'
WINDOWS = os.name == 'nt'

# AddressSanitizer's leak checker does not exist on macOS (clang prints "detect_leaks is not
# supported on this platform" and nothing else works differently), so the leak half of a sanitizer
# test is Linux-only; the address and undefined-behaviour halves still run everywhere.
ASAN_DETECT_LEAKS = 'detect_leaks=0' if DARWIN else 'detect_leaks=1'
LEAK_CHECK_REASON = 'AddressSanitizer has no leak checker on macOS (detect_leaks is not supported there)'

_GNU_TIME = []


def gnu_time():
    """Path of a `time` that understands `-f %M` (GNU time, peak RSS in KiB), else None. The BSD
    time of macOS has `-l` with another output shape, and Windows has none."""
    if not _GNU_TIME:
        found = None
        candidate = Path('/usr/bin/time')
        if candidate.exists():
            try:
                probe = subprocess.run([str(candidate), '-f', '%M', sys.executable, '-c', 'pass'],
                                       capture_output=True, text=True, timeout=60)
                lines = probe.stderr.strip().splitlines()
                if probe.returncode == 0 and lines and lines[-1].isdigit():
                    found = str(candidate)
            except (OSError, subprocess.SubprocessError):
                pass
        _GNU_TIME.append(found)
    return _GNU_TIME[0]


def objcopy_available():
    """The C-object bridge rewrites symbols with an ELF/COFF `objcopy --redefine-sym`; Apple's
    toolchain has no `objcopy` (Mach-O), so those tests are Linux and MinGW only."""
    return shutil.which('objcopy') is not None


def glibc_cookie_streams():
    """fopencookie() is a glibc extension (macOS has funopen, MinGW neither)."""
    return sys.platform.startswith('linux')
