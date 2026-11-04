"""Constants/functions for interpreting results of os.stat() and os.lstat().

Suggested usage: from stat import *

This is CPython 3.12's Lib/stat.py as AIL source.  Every public name and value is kept: the
ST_* indices, S_IMODE/S_IFMT, the S_IF*/S_I* constants, the S_IS* predicates, UF_*/SF_*,
FILE_ATTRIBUTE_* and filemode.

The trailing `from _stat import *` is dropped.  CPython replaces the Python definitions with the
C `_stat` module when it is available; an AIL program is one executable and there is no C `_stat`
to import, so this module is the whole implementation.

CPython builds `filemode` from `_filemode_table`, a module-level tuple of tuples of int and str.
The typed path refuses a module-level table holding non-numbers, so `filemode` here is an explicit
if chain over the same bits.  Its output is identical for every mode.  Like CPython's shipped C
`_stat.filemode` (which replaces the Python function at import time), the type character is chosen
from `S_IFMT(mode)` and an unrecognised type prints `?`; the Python fallback in Lib/stat.py would
print `-` there, but `_stat` is what CPython 3.12 exposes.  Every mode-taking function here takes
the C unsigned 32-bit mode, so a negative mode or one above 0xFFFFFFFF raises the same
OverflowError CPython's C functions do (the Python fallbacks would compute instead).
A mode beyond int64 stops loudly (an OverflowError), as ints are int64.
"""

# Indices for stat struct members in the tuple returned by os.stat()

ST_MODE = 0
ST_INO = 1
ST_DEV = 2
ST_NLINK = 3
ST_UID = 4
ST_GID = 5
ST_SIZE = 6
ST_ATIME = 7
ST_MTIME = 8
ST_CTIME = 9


# Extract bits from the mode

def _check_mode(mode: int) -> None:
    """CPython's C _stat takes the mode as an unsigned 32-bit int."""
    if mode < 0:
        raise OverflowError("can't convert negative value to unsigned int")
    if mode > 0xFFFFFFFF:
        raise OverflowError("mode out of range")


def S_IMODE(mode: int) -> int:
    """Return the portion of the file's mode that can be set by
    os.chmod().
    """
    _check_mode(mode)
    return mode & 0o7777


def S_IFMT(mode: int) -> int:
    """Return the portion of the file's mode that describes the
    file type.
    """
    _check_mode(mode)
    return mode & 0o170000


# Constants used as S_IFMT() for various file types
# (not all are implemented on all systems)

S_IFDIR = 0o040000   # directory
S_IFCHR = 0o020000   # character device
S_IFBLK = 0o060000   # block device
S_IFREG = 0o100000   # regular file
S_IFIFO = 0o010000   # fifo (named pipe)
S_IFLNK = 0o120000   # symbolic link
S_IFSOCK = 0o140000  # socket file
# Fallbacks for uncommon platform-specific constants
S_IFDOOR = 0
S_IFPORT = 0
S_IFWHT = 0


# Functions to test for each file type

def S_ISDIR(mode: int) -> bool:
    """Return True if mode is from a directory."""
    return S_IFMT(mode) == S_IFDIR


def S_ISCHR(mode: int) -> bool:
    """Return True if mode is from a character special device file."""
    return S_IFMT(mode) == S_IFCHR


def S_ISBLK(mode: int) -> bool:
    """Return True if mode is from a block special device file."""
    return S_IFMT(mode) == S_IFBLK


def S_ISREG(mode: int) -> bool:
    """Return True if mode is from a regular file."""
    return S_IFMT(mode) == S_IFREG


def S_ISFIFO(mode: int) -> bool:
    """Return True if mode is from a FIFO (named pipe)."""
    return S_IFMT(mode) == S_IFIFO


def S_ISLNK(mode: int) -> bool:
    """Return True if mode is from a symbolic link."""
    return S_IFMT(mode) == S_IFLNK


def S_ISSOCK(mode: int) -> bool:
    """Return True if mode is from a socket."""
    return S_IFMT(mode) == S_IFSOCK


def S_ISDOOR(mode: int) -> bool:
    """Return True if mode is from a door."""
    _check_mode(mode)
    return False


def S_ISPORT(mode: int) -> bool:
    """Return True if mode is from an event port."""
    _check_mode(mode)
    return False


def S_ISWHT(mode: int) -> bool:
    """Return True if mode is from a whiteout."""
    _check_mode(mode)
    return False


# Names for permission bits

S_ISUID = 0o4000   # set UID bit
S_ISGID = 0o2000   # set GID bit
S_ENFMT = S_ISGID  # file locking enforcement
S_ISVTX = 0o1000   # sticky bit
S_IREAD = 0o0400   # Unix V7 synonym for S_IRUSR
S_IWRITE = 0o0200  # Unix V7 synonym for S_IWUSR
S_IEXEC = 0o0100   # Unix V7 synonym for S_IXUSR
S_IRWXU = 0o0700   # mask for owner permissions
S_IRUSR = 0o0400   # read by owner
S_IWUSR = 0o0200   # write by owner
S_IXUSR = 0o0100   # execute by owner
S_IRWXG = 0o0070   # mask for group permissions
S_IRGRP = 0o0040   # read by group
S_IWGRP = 0o0020   # write by group
S_IXGRP = 0o0010   # execute by group
S_IRWXO = 0o0007   # mask for others (not in group) permissions
S_IROTH = 0o0004   # read by others
S_IWOTH = 0o0002   # write by others
S_IXOTH = 0o0001   # execute by others


# Names for file flags

UF_NODUMP = 0x00000001      # do not dump file
UF_IMMUTABLE = 0x00000002   # file may not be changed
UF_APPEND = 0x00000004      # file may only be appended to
UF_OPAQUE = 0x00000008      # directory is opaque when viewed through a union stack
UF_NOUNLINK = 0x00000010    # file may not be renamed or deleted
UF_COMPRESSED = 0x00000020  # OS X: file is hfs-compressed
UF_HIDDEN = 0x00008000      # OS X: file should not be displayed
SF_ARCHIVED = 0x00010000    # file may be archived
SF_IMMUTABLE = 0x00020000   # file may not be changed
SF_APPEND = 0x00040000      # file may only be appended to
SF_NOUNLINK = 0x00100000    # file may not be renamed or deleted
SF_SNAPSHOT = 0x00200000    # file is a snapshot file


def filemode(mode: int) -> str:
    """Convert a file's mode to a string of the form '-rwxrwxrwx'."""
    _check_mode(mode)
    perm = ""
    fmt = S_IFMT(mode)
    if fmt == S_IFLNK:
        perm = perm + "l"
    elif fmt == S_IFSOCK:
        perm = perm + "s"
    elif fmt == S_IFREG:
        perm = perm + "-"
    elif fmt == S_IFBLK:
        perm = perm + "b"
    elif fmt == S_IFDIR:
        perm = perm + "d"
    elif fmt == S_IFCHR:
        perm = perm + "c"
    elif fmt == S_IFIFO:
        perm = perm + "p"
    else:
        perm = perm + "?"
    if (mode & S_IRUSR) == S_IRUSR:
        perm = perm + "r"
    else:
        perm = perm + "-"
    if (mode & S_IWUSR) == S_IWUSR:
        perm = perm + "w"
    else:
        perm = perm + "-"
    if (mode & (S_IXUSR | S_ISUID)) == (S_IXUSR | S_ISUID):
        perm = perm + "s"
    elif (mode & S_ISUID) == S_ISUID:
        perm = perm + "S"
    elif (mode & S_IXUSR) == S_IXUSR:
        perm = perm + "x"
    else:
        perm = perm + "-"
    if (mode & S_IRGRP) == S_IRGRP:
        perm = perm + "r"
    else:
        perm = perm + "-"
    if (mode & S_IWGRP) == S_IWGRP:
        perm = perm + "w"
    else:
        perm = perm + "-"
    if (mode & (S_IXGRP | S_ISGID)) == (S_IXGRP | S_ISGID):
        perm = perm + "s"
    elif (mode & S_ISGID) == S_ISGID:
        perm = perm + "S"
    elif (mode & S_IXGRP) == S_IXGRP:
        perm = perm + "x"
    else:
        perm = perm + "-"
    if (mode & S_IROTH) == S_IROTH:
        perm = perm + "r"
    else:
        perm = perm + "-"
    if (mode & S_IWOTH) == S_IWOTH:
        perm = perm + "w"
    else:
        perm = perm + "-"
    if (mode & (S_IXOTH | S_ISVTX)) == (S_IXOTH | S_ISVTX):
        perm = perm + "t"
    elif (mode & S_ISVTX) == S_ISVTX:
        perm = perm + "T"
    elif (mode & S_IXOTH) == S_IXOTH:
        perm = perm + "x"
    else:
        perm = perm + "-"
    return perm


# Windows FILE_ATTRIBUTE constants for interpreting os.stat()'s
# "st_file_attributes" member

FILE_ATTRIBUTE_ARCHIVE = 32
FILE_ATTRIBUTE_COMPRESSED = 2048
FILE_ATTRIBUTE_DEVICE = 64
FILE_ATTRIBUTE_DIRECTORY = 16
FILE_ATTRIBUTE_ENCRYPTED = 16384
FILE_ATTRIBUTE_HIDDEN = 2
FILE_ATTRIBUTE_INTEGRITY_STREAM = 32768
FILE_ATTRIBUTE_NORMAL = 128
FILE_ATTRIBUTE_NOT_CONTENT_INDEXED = 8192
FILE_ATTRIBUTE_NO_SCRUB_DATA = 131072
FILE_ATTRIBUTE_OFFLINE = 4096
FILE_ATTRIBUTE_READONLY = 1
FILE_ATTRIBUTE_REPARSE_POINT = 1024
FILE_ATTRIBUTE_SPARSE_FILE = 512
FILE_ATTRIBUTE_SYSTEM = 4
FILE_ATTRIBUTE_TEMPORARY = 256
FILE_ATTRIBUTE_VIRTUAL = 65536
