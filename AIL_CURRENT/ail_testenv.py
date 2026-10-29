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


def rustc():
    """Path of a rustc that actually runs, else None. A rustup shim with no default toolchain is on
    PATH but is not a compiler, so `which` alone would fail those tests instead of skipping them."""
    found = shutil.which('rustc')
    if not found:
        return None
    try:
        probe = subprocess.run([found, '--version'], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return found if probe.returncode == 0 else None


def glibc_cookie_streams():
    """fopencookie() is a glibc extension (macOS has funopen, MinGW neither)."""
    return sys.platform.startswith('linux')
