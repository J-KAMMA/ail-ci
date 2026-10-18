"""Build cache (GENERAL_PURPOSE G3): the C compiler step and whole front-end results, on disk.

Two kinds of entries, both content addressed and both safe to lose at any time:

* ``cc`` -- one C compiler invocation. Key = compiler/linker/libc identity, the command with file
  names normalised, the bytes of every input file and of every ``-I`` directory inside the working
  directory, and the build environment. Value = the output file plus the system headers the compile
  read (path, size, mtime, sha256: ccache's "direct mode", validated before a hit is used).
* ``fe`` -- a finished ``compile`` (merged source text -> executable). Key = the bytes of every
  compiler source file, the toolchain identity, the merged source text and the relevant
  environment. Value = the executable and the compiler's stderr notes.

Rules that keep the cache invisible: a hit produces exactly the bytes a miss would have produced;
anything unexpected (unreadable cache, corrupt entry, vanished header, tool that will not run) is
a miss, never an error; failed builds are never stored; a cache write that fails is ignored.
``AIL_NO_CACHE=1`` / ``--no-cache`` turn it off, ``AIL_CACHE`` moves it, ``AIL_CACHE_MAX_MB``
bounds it (least recently used entries go first), ``ail cache clear`` empties it.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FORMAT = b'ail-build-cache-1'
MAGIC = b'AILC1\n'
KINDS = ('cc', 'fe')
DEFAULT_MAX_MB = 512
MAX_ENTRY = 64 << 20
# Variables a C compiler reads on its own. They are part of every cc key.
CC_ENV = ('CPATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'COMPILER_PATH', 'GCC_EXEC_PREFIX', 'GCC_COMPARE_DEBUG',
          'SOURCE_DATE_EPOCH', 'SDKROOT', 'MACOSX_DEPLOYMENT_TARGET', 'LD_RUN_PATH', 'DEPENDENCIES_OUTPUT',
          'SUNPRO_DEPENDENCIES', 'TMPDIR_FOR_CC')
CC_FILES = ('crt1.o', 'crti.o', 'crtn.o', 'crtbegin.o', 'crtend.o', 'libc.so', 'libc.a', 'libm.so', 'libm.a',
            'libgcc.a', 'libgcc_s.so', 'libpthread.a', 'libc_nonshared.a')
SYSTEM_HEADERS = ('stdio.h', 'stdlib.h', 'string.h', 'stdint.h', 'stddef.h', 'stdbool.h', 'stdarg.h', 'math.h',
                  'limits.h', 'float.h', 'errno.h', 'ctype.h', 'time.h', 'unistd.h', 'fcntl.h', 'pthread.h',
                  'setjmp.h', 'signal.h', 'sys/stat.h', 'sys/types.h', 'sys/mman.h', 'sys/socket.h')
_VALUE_OPTIONS = {'-o', '-MF', '-MT', '-MQ', '-I', '-x', '-include', '-isystem', '-L', '-D', '-U', '-iquote'}

_active = False            # set by activate(): this process may use the cc cache
_toolchains = {}
_sources = {}


# ----------------------------------------------------------------------------- switches and location

def disabled():
    """True when the cache is switched off for this process (AIL_NO_CACHE) or unsupported here."""
    if os.environ.get('AIL_NO_CACHE', '').strip().lower() not in ('', '0', 'false', 'no'):
        return True
    return os.name == 'nt'       # Windows builds link statically and append .exe; not covered yet


def activate():
    global _active
    _active = not disabled()
    return _active


def root():
    configured = os.environ.get('AIL_CACHE')
    if configured:
        return Path(configured).expanduser()
    xdg = os.environ.get('XDG_CACHE_HOME')
    return (Path(xdg) if xdg else Path.home() / '.cache') / 'ail'


def max_bytes():
    try:
        return int(float(os.environ.get('AIL_CACHE_MAX_MB', DEFAULT_MAX_MB)) * (1 << 20))
    except ValueError:
        return DEFAULT_MAX_MB << 20


# ----------------------------------------------------------------------------- storage

def digest(*parts):
    h = hashlib.sha256(FORMAT)
    for part in parts:
        data = part if isinstance(part, bytes) else str(part).encode('utf8', 'surrogatepass')
        h.update(len(data).to_bytes(8, 'little'))
        h.update(data)
    return h.hexdigest()


def _entry_path(kind, key):
    return root() / kind / key[:2] / key


def get(kind, key):
    """The stored bytes, or None. A corrupt or truncated entry is deleted and counts as a miss."""
    path = _entry_path(kind, key)
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    head = len(MAGIC) + 64 + 1
    if len(raw) < head or not raw.startswith(MAGIC) or raw[head - 1:head] != b'\n':
        _discard(path)
        return None
    payload = raw[head:]
    if hashlib.sha256(payload).hexdigest().encode() != raw[len(MAGIC):len(MAGIC) + 64]:
        _discard(path)
        return None
    try:
        os.utime(path)                       # least recently used bookkeeping
    except OSError:
        pass
    return payload


def _discard(path):
    try:
        path.unlink()
    except OSError:
        pass


def put(kind, key, payload):
    """Store atomically (temp file in the same directory, then rename). Failures are ignored."""
    if len(payload) > MAX_ENTRY:
        return False
    path = _entry_path(kind, key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        marker = root() / 'CACHEDIR.TAG'
        if not marker.exists():
            marker.write_text('Signature: 8a477f597d28d172789f06886806bc55\n# AIL build cache\n')
        descriptor, temporary = tempfile.mkstemp(prefix='.tmp-', dir=str(path.parent))
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(MAGIC + hashlib.sha256(payload).hexdigest().encode() + b'\n' + payload)
            os.replace(temporary, path)
        except BaseException:
            _discard(Path(temporary))
            raise
    except OSError:
        return False
    _maybe_trim()
    return True


def entries():
    """(path, size, mtime) of every cache entry; temp files older than an hour are removed."""
    result = []
    base = root()
    now = time.time()
    for kind in KINDS:
        try:
            shards = list(os.scandir(base / kind))
        except OSError:
            continue
        for shard in shards:
            try:
                files = list(os.scandir(shard.path))
            except OSError:
                continue
            for item in files:
                try:
                    info = item.stat()
                except OSError:
                    continue
                if item.name.startswith('.tmp-'):
                    if now - info.st_mtime > 3600:
                        _discard(Path(item.path))
                    continue
                result.append((item.path, info.st_size, info.st_mtime))
    return result


def trim(limit=None):
    """Delete least recently used entries until the cache is under 80 percent of the limit."""
    limit = max_bytes() if limit is None else limit
    found = entries()
    total = sum(size for _, size, _ in found)
    if total <= limit:
        return 0
    removed = 0
    for path, size, _ in sorted(found, key=lambda item: item[2]):
        if total <= limit * 0.8:
            break
        _discard(Path(path))
        total -= size
        removed += 1
    return removed


def _maybe_trim():
    stamp = root() / '.trimmed'
    try:
        if time.time() - stamp.stat().st_mtime < 30:
            return
    except OSError:
        pass
    try:
        stamp.touch()
        trim()
    except OSError:
        pass


def stats():
    found = entries()
    return {'path': str(root()), 'entries': len(found), 'bytes': sum(size for _, size, _ in found),
            'limit_bytes': max_bytes(), 'enabled': not disabled()}


def clear():
    """Remove every entry. Only the directories this module creates are touched."""
    removed = 0
    for kind in KINDS:
        directory = root() / kind
        if directory.is_dir():
            removed += sum(1 for _ in entries_of(directory))
            shutil.rmtree(directory, ignore_errors=True)
    for name in ('.trimmed', 'CACHEDIR.TAG'):
        _discard(root() / name)
    for name in ('srcsig',):
        shutil.rmtree(root() / name, ignore_errors=True)
    return removed


def entries_of(directory):
    for shard in os.scandir(directory):
        if shard.is_dir():
            for item in os.scandir(shard.path):
                if not item.name.startswith('.tmp-'):
                    yield item


# ----------------------------------------------------------------------------- identities

def sources_hash(package):
    """Hash of every compiler source file (.py and .h under `package`). A stat signature memo makes
    the common case (nothing changed) cost a few hundred stats instead of reading 6 MB."""
    package = Path(package).resolve()
    if package in _sources:
        return _sources[package]
    names = sorted(p for p in package.rglob('*') if p.suffix in ('.py', '.h') and '__pycache__' not in p.parts)
    signature = hashlib.sha256()
    for p in names:
        try:
            info = p.stat()
        except OSError:
            continue
        signature.update(('%s\0%d\0%d\n' % (p.relative_to(package).as_posix(), info.st_size, info.st_mtime_ns)).encode())
    memo = root() / 'srcsig' / signature.hexdigest()
    try:
        value = memo.read_text().strip()
        if len(value) == 64:
            _sources[package] = value
            return value
    except OSError:
        pass
    h = hashlib.sha256()
    for p in names:
        h.update(p.relative_to(package).as_posix().encode() + b'\0')
        h.update(hashlib.sha256(p.read_bytes()).digest())
    value = h.hexdigest()
    _sources[package] = value
    try:
        memo.parent.mkdir(parents=True, exist_ok=True)
        memo.write_text(value)
    except OSError:
        pass
    return value


def resolve_compiler():
    """The same compiler the build would use: $PIPE_CC, else cc, clang or gcc on PATH."""
    configured = os.environ.get('PIPE_CC')
    if configured:
        return configured
    for name in ('cc', 'clang', 'gcc'):
        found = shutil.which(name)
        if found:
            return found
    return None


def _run(command):
    result = subprocess.run(command, capture_output=True, timeout=30)
    if result.returncode:
        raise OSError('%s failed' % command[0])
    return result.stdout


def _stat_signature(path):
    try:
        real = Path(path).resolve(strict=True)
        info = real.stat()
    except OSError:
        return None
    return '%s:%d:%d' % (real, info.st_size, info.st_mtime_ns)


def toolchain(compiler):
    """Identity of compiler, assembler, linker and the C library files they pick, or None."""
    if compiler in _toolchains:
        return _toolchains[compiler]
    # The parent `ail compile` process already probed the toolchain and hands the answer to the
    # compiler subprocess it starts, so the (about 50 ms) probe runs once per build.
    identity, _, named = os.environ.get('AIL_CACHE_TOOLCHAIN', '').partition(':')
    if len(identity) == 64 and named == compiler:
        _toolchains[compiler] = identity
        return identity
    value = None
    try:
        real = Path(shutil.which(compiler) or compiler).resolve(strict=True)
        h = hashlib.sha256()
        h.update(real.read_bytes())
        for option in ('--version', '-dumpmachine'):
            h.update(_run([compiler, option]))
        search = _run([compiler, '-print-search-dirs']).decode('utf8', 'replace')
        h.update(search.encode())
        for program in ('as', 'ld'):
            located = _run([compiler, '-print-prog-name=' + program]).decode().strip()
            found = shutil.which(located) or located
            h.update((_stat_signature(found) or 'missing').encode())
        directories = []
        for line in search.splitlines():
            if line.startswith('libraries:'):
                directories = [d for d in line.split('=', 1)[1].split(os.pathsep) if d]
        for name in CC_FILES:
            for directory in directories:
                signature = _stat_signature(Path(directory) / name)
                if signature:
                    h.update(signature.encode())
                    break
        # System headers: the include search list of the compiler, each directory and the headers
        # every generated C file pulls in. (The cc entries also record the exact headers they read.)
        listing = subprocess.run([compiler, '-E', '-x', 'c', '-', '-v'], input=b'', capture_output=True,
                                 timeout=30).stderr.decode('utf8', 'replace')
        if '#include <...> search starts here:' in listing:
            roots = listing.split('#include <...> search starts here:', 1)[1].split('End of search list.', 1)[0]
            for line in roots.splitlines():
                directory = line.strip().split(' (framework')[0]
                if not directory:
                    continue
                h.update((_stat_signature(directory) or 'missing').encode() + b'\n')
                for name in SYSTEM_HEADERS:
                    signature = _stat_signature(Path(directory) / name)
                    if signature:
                        h.update(signature.encode())
        value = h.hexdigest()
    except (OSError, subprocess.SubprocessError, ValueError):
        value = None
    _toolchains[compiler] = value
    return value


def build_env():
    """Environment variables that can change a build: AIL_* and PIPE_* (except the cache's own)
    and the ones a C compiler reads itself."""
    names = sorted(k for k in os.environ
                   if (k.startswith('AIL_') or k.startswith('PIPE_')) and not k.startswith('AIL_CACHE')
                   and k != 'AIL_NO_CACHE')
    names += [k for k in CC_ENV if k in os.environ]
    return ['%s=%s' % (k, os.environ[k]) for k in names]


def frontend_key(package, *parts):
    """Key of a whole `compile` result, or None when the cache cannot vouch for the toolchain."""
    compiler = resolve_compiler()
    tool = toolchain(compiler) if compiler else None
    if tool is None:
        return None
    return digest('fe', sources_hash(package), tool, sys.version.split()[0], sys.platform,
                  '\n'.join(build_env()), *parts)


# ----------------------------------------------------------------------------- front-end entries

def pack(meta, blob):
    head = json.dumps(meta, sort_keys=True).encode()
    return len(head).to_bytes(8, 'little') + head + blob


def unpack(payload):
    size = int.from_bytes(payload[:8], 'little')
    return json.loads(payload[8:8 + size]), payload[8 + size:]


def write_output(path, blob, executable):
    """Create `path` the way the C compiler would have: fresh file, mode 0777/0666 minus umask."""
    path = Path(path)
    temporary = path.with_name('.%s.%d.tmp' % (path.name, os.getpid()))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o777 if executable else 0o666)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(blob)
        os.replace(temporary, path)
    except BaseException:
        _discard(temporary)
        raise


# ----------------------------------------------------------------------------- the cc cache

def _dependency_paths(text):
    body = text.replace('\\\n', ' ').split(':', 1)[-1]
    paths, token, i = [], '', 0
    while i < len(body):
        c = body[i]
        if c == '\\' and i + 1 < len(body):
            token += body[i + 1]
            i += 2
            continue
        if c.isspace():
            if token:
                paths.append(token)
            token = ''
        else:
            token += c
        i += 1
    if token:
        paths.append(token)
    return paths


def _analyse(command, cwd):
    """(output index, input files, include directories inside cwd, depfile index) or None."""
    base = Path(cwd) if cwd else Path.cwd()
    if '-o' not in command[1:] or command.index('-o') + 1 >= len(command):
        return None
    out_at = command.index('-o') + 1
    inputs, include_dirs, skip, dep_at = [], [], set(), None
    for j, arg in enumerate(command):
        if j == 0 or j in skip:
            continue
        if arg in _VALUE_OPTIONS and j + 1 < len(command):
            skip.add(j + 1)
            if arg == '-MF':
                dep_at = j + 1
            if arg == '-I':
                candidate = base / command[j + 1]
                if candidate.is_dir() and base.resolve() in candidate.resolve().parents:
                    include_dirs.append(candidate)
            continue
        if arg.startswith('-'):
            continue
        candidate = base / arg
        if candidate.is_file():
            inputs.append(candidate)
    return out_at, inputs, include_dirs, dep_at


def _tree(directory):
    for path in sorted(p for p in directory.rglob('*') if p.is_file()):
        yield path.relative_to(directory).as_posix(), path.read_bytes()


def _cc_key(command, cwd, plan):
    out_at, inputs, include_dirs, dep_at = plan
    tool = toolchain(command[0])
    if tool is None:
        return None
    base = Path(cwd) if cwd else Path.cwd()
    normal = []
    skip = set()
    for j, arg in enumerate(command):
        if j in skip:
            continue
        if arg in ('-MF',) and j + 1 < len(command):
            skip.add(j + 1)
            continue
        if arg in ('-MD', '-MMD'):
            continue
        if j == out_at:
            normal.append('<out>')
        elif (base / arg) in inputs and j != 0:
            normal.append('<in:%s>' % Path(arg).name)
        elif arg in ('-I',) and j + 1 < len(command):
            normal.append(arg)
        else:
            normal.append(arg)
    parts = [tool, '\0'.join(normal), '\n'.join(build_env()), str(os.path.basename(command[out_at]))]
    for path in inputs:
        parts += [path.name, path.read_bytes()]
    for directory in include_dirs:
        for name, data in _tree(directory):
            parts += [name, data]
    return digest('cc', *parts)


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _deps_valid(deps):
    for path, size, mtime_ns, sha in deps:
        try:
            info = os.stat(path)
        except OSError:
            return False
        if info.st_size == size and info.st_mtime_ns == mtime_ns:
            continue
        try:
            if info.st_size != size or _sha_file(path) != sha:
                return False
        except OSError:
            return False
    return True


def run_cc(command, runner, cwd=None):
    """Run a C compiler/linker command through the cache. `runner(command)` does the real run and
    returns a CompletedProcess; it is also what runs when the cache is off, cannot key the command,
    or misses. A hit returns a successful CompletedProcess with empty output."""
    if not _active or disabled() or '__FILE__' in ' '.join(command):
        return runner(command)
    try:
        plan = _analyse(command, cwd)
        if plan is None or any(a in ('-E', '-S', '-save-temps', '-save-temps=obj') or a.startswith('-Wa,--MD')
                               or a.startswith('-save-temps') for a in command):
            return runner(command)
        key = _cc_key(command, cwd, plan)
    except (OSError, ValueError):
        return runner(command)
    if key is None:
        return runner(command)
    out_at, inputs, _, dep_at = plan
    base = Path(cwd) if cwd else Path.cwd()
    out_path = base / command[out_at]
    compile_only = '-c' in command
    payload = get('cc', key)
    if payload is not None:
        try:
            meta, blob = unpack(payload)
            if _deps_valid(meta['deps']):
                write_output(out_path, blob, not compile_only)
                if dep_at is not None and meta.get('depfile') is not None:
                    (base / command[dep_at]).write_text(meta['depfile'])
                return subprocess.CompletedProcess(command, 0, b'' if meta.get('bytes') else '', b'' if meta.get('bytes') else '')
        except (OSError, ValueError, KeyError):
            pass
    own_dep = None
    run_command = list(command)
    if dep_at is None:
        own_dep = Path(tempfile.mkdtemp(prefix='ail-cc-dep-')) / 'dep.d'
        run_command += ['-MD', '-MF', str(own_dep), '-MT', 'x']
    result = runner(run_command)
    try:
        if result.returncode == 0 and out_path.is_file():
            dep_file = own_dep if own_dep is not None else base / command[dep_at]
            text = dep_file.read_text(encoding='utf8')
            skip_roots = [base.resolve()] if cwd else []
            skip_files = {p.resolve() for p in inputs}
            deps = []
            for name in _dependency_paths(text):
                path = (base / name)
                real = path.resolve()
                if real in skip_files or any(r == real or r in real.parents for r in skip_roots):
                    continue
                info = real.stat()
                deps.append([str(real), info.st_size, info.st_mtime_ns, _sha_file(real)])
            meta = {'deps': deps, 'depfile': text if own_dep is None else None,
                    'bytes': isinstance(result.stdout, bytes)}
            put('cc', key, pack(meta, out_path.read_bytes()))
    except (OSError, ValueError, UnicodeError):
        pass
    finally:
        if own_dep is not None:
            shutil.rmtree(own_dep.parent, ignore_errors=True)
    return result
