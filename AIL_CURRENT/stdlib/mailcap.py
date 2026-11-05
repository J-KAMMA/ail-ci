"""Mailcap file handling.  See RFC 1524.

This is CPython 3.12's Lib/mailcap.py as AIL source, used under the PSF license
(https://docs.python.org/3/license.html).  Rewrites for this compiler, with the
behaviour kept:

* `warnings` is not a bundled module, so `_warn` writes the warning text and a
  newline to sys.stderr instead.  CPython prints its `import mailcap`
  DeprecationWarning to stderr and this module prints nothing there; the
  `readmailcapfile` deprecation message and the two `UnsafeMailcapInput`
  refusals go to stderr with CPython's exact text.  Only stdout and the exit
  status are intended to match.
* `UnsafeMailcapInput` derives from `Exception` because this compiler does not
  build a class whose base is the builtin `Warning`.  CPython only ever raises
  it as a warning and mailcap itself never catches it.
* `os.system` is not built on either compiler path, so an entry carrying a
  `test=` field raises OSError with a clear message instead of running the
  command.  Entries without `test=` behave exactly as CPython's, and a `test=`
  field that substitutes to None is skipped on both.  The lab programs only use
  entries without `test=`.
* `os.pathsep` is not built as a value, so listmailcapfiles splits MAILCAPS on
  ":" (the POSIX separator this platform uses).  A missing or empty HOME uses
  "." through `os.environ.get`, as CPython's membership test does.
* `re.compile(...).search` is not built as one expression, so `_find_unsafe` is a
  function over the module-level compiled pattern.  The pattern is CPython's.

Compared with CPython only stdout and the exit status are intended to match; all
warning text goes to stderr.
"""

import os
import re
import sys

__all__ = ["getcaps", "findmatch"]

_unsafe_pattern = re.compile(r'[^\xa1-\U0010FFFF\w@+=:,./-]')


def _find_unsafe(text):
    """Search text for a character unsafe in a shell command (CPython's .search)."""
    return _unsafe_pattern.search(text)


class UnsafeMailcapInput(Exception):
    """Warning raised when refusing unsafe input"""


def _warn(text):
    sys.stderr.write(text + "\n")


def lineno_sort_key(entry):
    # Sort in ascending order, with unspecified entries at the end
    if 'lineno' in entry:
        return 0, entry['lineno']
    else:
        return 1, 0


# Part 1: top-level interface.

def getcaps():
    """Return a dictionary containing the mailcap database.

    The dictionary maps a MIME type (in all lowercase, e.g. 'text/plain')
    to a list of dictionaries corresponding to mailcap entries.  The list
    collects all the entries for that MIME type from all available mailcap
    files.  Each dictionary contains key-value pairs for that MIME type,
    where the viewing command is stored with the key "view".

    """
    caps = {}
    lineno = 0
    for mailcap in listmailcapfiles():
        try:
            fp = open(mailcap, 'r')
        except OSError:
            continue
        with fp:
            morecaps, lineno = _readmailcapfile(fp, lineno)
        for key, value in morecaps.items():
            if key not in caps:
                caps[key] = value
            else:
                caps[key] = caps[key] + value
    return caps


def listmailcapfiles():
    """Return a list of all mailcap files found on the system."""
    if 'MAILCAPS' in os.environ:
        pathstr = os.environ.get('MAILCAPS', '')
        mailcaps = pathstr.split(':')
    else:
        home = os.environ.get('HOME', '.')
        mailcaps = [home + '/.mailcap', '/etc/mailcap',
                    '/usr/etc/mailcap', '/usr/local/etc/mailcap']
    return mailcaps


# Part 2: the parser.
def readmailcapfile(fp):
    """Read a mailcap file and return a dictionary keyed by MIME type."""
    _warn('readmailcapfile is deprecated, use getcaps instead')
    caps, _lineno = _readmailcapfile(fp, None)
    return caps


def _readmailcapfile(fp, lineno):
    """Read a mailcap file and return a dictionary keyed by MIME type.

    Each MIME type is mapped to an entry consisting of a list of
    dictionaries; the list will contain more than one such dictionary
    if a given MIME type appears more than once in the mailcap file.
    Each dictionary contains key-value pairs for that MIME type, where
    the viewing command is stored with the key "view".
    """
    caps = {}
    line = fp.readline()
    while line:
        # Ignore comments and blank lines
        if line[0] == '#' or line.strip() == '':
            line = fp.readline()
            continue
        nextline = line
        # Join continuation lines
        while nextline[-2:] == '\\\n':
            nextline = fp.readline()
            if not nextline:
                nextline = '\n'
            line = line[:-2] + nextline
        # Parse the line
        key, fields = parseline(line)
        if not (key and fields):
            line = fp.readline()
            continue
        if lineno is not None:
            fields['lineno'] = lineno
            lineno = lineno + 1
        # Normalize the key
        types = key.split('/')
        for j in range(len(types)):
            types[j] = types[j].strip()
        key = '/'.join(types).lower()
        # Update the database
        if key in caps:
            caps[key].append(fields)
        else:
            caps[key] = [fields]
        line = fp.readline()
    return caps, lineno


def parseline(line):
    """Parse one entry in a mailcap file and return a dictionary.

    The viewing command is stored as the value with the key "view",
    and the rest of the fields produce key-value pairs in the dict.
    """
    fields = []
    i, n = 0, len(line)
    while i < n:
        field, i = parsefield(line, i, n)
        fields.append(field)
        i = i + 1  # Skip semicolon
    if len(fields) < 2:
        return None, None
    key, view, rest = fields[0], fields[1], fields[2:]
    fields = {'view': view}
    for field in rest:
        i = field.find('=')
        if i < 0:
            fkey = field
            fvalue = ""
        else:
            fkey = field[:i].strip()
            fvalue = field[i + 1:].strip()
        if fkey in fields:
            # Ignore it
            pass
        else:
            fields[fkey] = fvalue
    return key, fields


def parsefield(line, i, n):
    """Separate one key-value pair in a mailcap entry."""
    start = i
    while i < n:
        c = line[i]
        if c == ';':
            break
        elif c == '\\':
            i = i + 2
        else:
            i = i + 1
    return line[start:i].strip(), i


# Part 3: using the database.

def findmatch(caps, MIMEtype, key='view', filename="/dev/null", plist=[]):
    """Find a match for a mailcap entry.

    Return a tuple containing the command line, and the mailcap entry
    used; (None, None) if no match is found.  This may invoke the
    'test' command of several matching entries before deciding which
    entry to use.  A 'test' field cannot run here (os.system is not
    built); such an entry raises OSError instead.
    """
    if _find_unsafe(filename):
        msg = "Refusing to use mailcap with filename %r. Use a safe temporary filename." % (filename,)
        _warn(msg)
        return None, None
    entries = lookup(caps, MIMEtype, key)
    for e in entries:
        if 'test' in e:
            raise OSError("mailcap: an entry with a 'test' field needs os.system, "
                          "which this compiler does not build: " + e['test'])
        command = subst(e[key], MIMEtype, filename, plist)
        if command is not None:
            return command, e
    return None, None


def lookup(caps, MIMEtype, key=None):
    entries = []
    if MIMEtype in caps:
        entries = entries + caps[MIMEtype]
    MIMEtypes = MIMEtype.split('/')
    MIMEtype = MIMEtypes[0] + '/*'
    if MIMEtype in caps:
        entries = entries + caps[MIMEtype]
    if key is not None:
        entries = [e for e in entries if key in e]
    entries = sorted(entries, key=lineno_sort_key)
    return entries


def subst(field, MIMEtype, filename, plist=[]):
    # XXX Actually, this is Unix-specific
    res = ''
    i, n = 0, len(field)
    while i < n:
        c = field[i]
        i = i + 1
        if c != '%':
            if c == '\\':
                c = field[i:i + 1]
                i = i + 1
            res = res + c
        else:
            c = field[i]
            i = i + 1
            if c == '%':
                res = res + c
            elif c == 's':
                res = res + filename
            elif c == 't':
                if _find_unsafe(MIMEtype):
                    msg = "Refusing to substitute MIME type %r into a shell command." % (MIMEtype,)
                    _warn(msg)
                    return None
                res = res + MIMEtype
            elif c == '{':
                start = i
                while i < n and field[i] != '}':
                    i = i + 1
                name = field[start:i]
                i = i + 1
                param = findparam(name, plist)
                if _find_unsafe(param):
                    msg = "Refusing to substitute parameter %r (%s) into a shell command" % (param, name)
                    _warn(msg)
                    return None
                res = res + param
            # XXX To do:
            # %n == number of parts if type is multipart/*
            # %F == list of alternating type and filename for parts
            else:
                res = res + '%' + c
    return res


def findparam(name, plist):
    name = name.lower() + '='
    n = len(name)
    for p in plist:
        if p[:n].lower() == name:
            return p[n:]
    return ''
