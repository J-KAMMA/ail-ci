"""Resident compile server, opt-in with AIL_SERVER=1.  POSIX with SO_PEERCRED (Linux) only; everywhere else, and whenever
anything goes wrong before a build starts, `ail_chatgpt.py compile|check` runs the normal way.

Why: a build pays about 0.25 s to import the compiler (the CLI front end, then the `pyc.py` child).  A server imports it
once.  Every request is a fork of that template process, so no state leaks between builds and a crash kills one build.

    client (ail_chatgpt.py, at the very top)         server (python ail_server.py serve SOCKET IDLE_SECONDS)
    ------------------------------------------       ---------------------------------------------------------
    connect, or start a server and connect           template: imported ail_chatgpt, pyc, ... once
    send argv, cwd, env, umask, rlimits + fds 0,1,2   per connection fork M (own session; checks SO_PEERCRED uid)
    wait; forward SIGINT/SIGTERM/SIGHUP/SIGQUIT       M forks A (own process group): ail_chatgpt.main(argv) with the
    exit like the build did (also death by signal)    client's fds, cwd, env, umask; M relays signals to A's group,
                                                      kills the group when the client goes away, reports A's status
                                                      A runs `python pyc.py ...` as a fork B running pyc.main, with the
                                                      same capture, env and timeout as subprocess.run gave it

The socket lives in a private per-user directory (0700, owned by the user, checked) and its name carries a hash of what the
template process froze at import: the interpreter, every compiler source file, the environment variables the compiler reads
while it is imported (IMPORT_ENV), PYTHON*/LANG/LC_* and the memory limits.  Another value of any of them means another
server; an old one exits after AIL_SERVER_IDLE seconds (default 600) without a request.  The server refuses a request
whose hash differs from its own (the client then builds the normal way), so a source file that changed between the
client's check and the fork is never served stale.

Environment: AIL_SERVER=1 turns the client on; AIL_SERVER_IDLE=seconds; AIL_SERVER_DIR=directory (tests)."""
import os
import sys

PROTOCOL = 1
SERVED_COMMANDS = ('compile', 'check')
# Environment variables read while the compiler is imported (module level).  test_ail_server.py imports the compiler with
# a recording os.environ and fails when a module reads one that is not named here.
IMPORT_ENV = ('AIL_EXTRA_CFLAGS', 'AIL_FASTWALK', 'AIL_G7_FORCE', 'AIL_QUERY_CACHE', 'AIL_RANGE_BUDGET', 'AIL_RANGE_DEBUG',
              'AIL_V2_INCLUDE_ABS', 'AIL_V2_WIDE_EMBED')
LIMITS = ('RLIMIT_AS', 'RLIMIT_DATA', 'RLIMIT_STACK', 'RLIMIT_NOFILE', 'RLIMIT_CPU', 'RLIMIT_FSIZE', 'RLIMIT_CORE')
KEYED_LIMITS = ('RLIMIT_AS', 'RLIMIT_DATA', 'RLIMIT_STACK', 'RLIMIT_NOFILE')   # fixed when the template is made
FORWARD = ('SIGINT', 'SIGTERM', 'SIGHUP', 'SIGQUIT')
START_WAIT = 30.0           # seconds a client waits for a server it started
ACK_WAIT = 10.0             # seconds from sending a request to the server's "started" answer


# ----------------------------------------------------------------------------------------------- identity

def _environment_part(env):
    names = [name for name in sorted(env) if name.startswith('PYTHON') or name.startswith('LC_') or name in ('LANG', 'LANGUAGE')]
    return ['%s=%s' % (name, env[name]) for name in IMPORT_ENV if name in env] + ['-'] + ['%s=%s' % (name, env[name]) for name in names]


def source_signature(root):
    """Hash of (relative path, size, mtime) of every file the compiler can import: root/*.py (not the tests) and
    root/python/**.  Stats only, a few hundred of them."""
    import hashlib
    digest = hashlib.sha256()
    def scan(directory, recurse, prefix):
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError:
            return
        for entry in entries:
            name = entry.name
            if entry.is_dir(follow_symlinks=False):
                if recurse and name not in ('__pycache__', 'tests'):
                    scan(entry.path, True, prefix + name + '/')
            elif name.endswith(('.py', '.h', '.c', '.json', '.so')) and not (not recurse and name.startswith('test_')):
                try:
                    info = entry.stat()
                except OSError:
                    continue
                digest.update(('%s%s\0%d\0%d\n' % (prefix, name, info.st_size, info.st_mtime_ns)).encode('utf-8', 'surrogateescape'))
    scan(root, False, '')
    scan(os.path.join(root, 'python'), True, 'python/')
    return digest.hexdigest()


def identity(root, env, limits):
    """The name of the server that may serve a request with this environment and these limits."""
    import hashlib
    parts = ['ail-server', str(PROTOCOL), sys.executable, sys.version, _text_encoding(), sys.platform, os.path.realpath(root),
             source_signature(root)] + _environment_part(env) + ['%s=%r' % (name, limits.get(name)) for name in KEYED_LIMITS]
    return hashlib.sha256('\n'.join(parts).encode('utf-8', 'surrogateescape')).hexdigest()[:20]


def _text_encoding():
    """What text I/O defaults to: -X utf8 and a UTF-8 locale are the same thing here (a build that re-runs
    `python -B ail_chatgpt.py check` without the flag must find the same server)."""
    import codecs
    import locale
    return codecs.lookup('utf-8' if sys.flags.utf8_mode else locale.getpreferredencoding(False)).name


def current_limits():
    import resource
    return {name: list(resource.getrlimit(getattr(resource, name))) for name in LIMITS if hasattr(resource, name)}


def runtime_directory():
    """A directory only this user can enter: $AIL_SERVER_DIR, else $XDG_RUNTIME_DIR/ail-server, else /tmp/ail-server-UID."""
    import stat
    uid = os.getuid()
    path = os.environ.get('AIL_SERVER_DIR')
    if not path:
        base = os.environ.get('XDG_RUNTIME_DIR')
        path = os.path.join(base, 'ail-server') if base and os.path.isabs(base) and os.path.isdir(base) else '/tmp/ail-server-%d' % uid
    if len(os.fsencode(path)) > 70:
        path = '/tmp/ail-server-%d' % uid
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid:
        raise OSError('runtime directory %s is not a directory of this user' % path)
    if info.st_mode & 0o077:
        os.chmod(path, 0o700)
    return path


def _peer_uid(sock):
    import socket
    import struct
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
    return struct.unpack('3i', raw)[1]


def supported():
    import socket
    return os.name == 'posix' and hasattr(socket, 'AF_UNIX') and hasattr(socket, 'SO_PEERCRED') and hasattr(socket, 'send_fds')


# ----------------------------------------------------------------------------------------------- client

def _connect(path):
    import socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(5)
        sock.connect(path)
        if _peer_uid(sock) != os.getuid():
            raise OSError('socket owned by another user')
        return sock
    except BaseException:
        sock.close()
        raise


def _start(path, root, flags):
    """Start a server (once, whatever the number of clients that want one), then connect."""
    import fcntl
    import subprocess
    import time
    with open(path + '.lock', 'a+') as lock:
        deadline = time.monotonic() + START_WAIT
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.02)
        try:
            return _connect(path)
        except OSError:
            pass
        try:
            os.unlink(path)
        except OSError:
            pass
        idle = os.environ.get('AIL_SERVER_IDLE', '600')
        with open(path + '.log', 'wb') as log:
            process = subprocess.Popen([sys.executable, *flags, os.path.join(root, 'ail_server.py'), 'serve', path, idle],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd='/', close_fds=True,
                                       start_new_session=True)
        while time.monotonic() < deadline:
            try:
                return _connect(path)
            except OSError:
                if process.poll() is not None:
                    raise
                time.sleep(0.02)
        raise OSError('compile server did not start')


def client(argv):
    """Run `ail_chatgpt.py ARGV` on the server and return its exit code, or None when the caller should run it itself."""
    if os.environ.get('AIL_SERVER') != '1' or not argv or argv[0] not in SERVED_COMMANDS or not supported():
        return None
    import json
    import array
    import socket
    root = os.path.dirname(os.path.realpath(__file__))
    try:
        for descriptor in (0, 1, 2):
            os.fstat(descriptor)
        env = dict(os.environ)
        limits = current_limits()
        key = identity(root, env, limits)
        path = os.path.join(runtime_directory(), 'ail-%s.sock' % key)
        flags = ['-X', 'utf8'] if sys.flags.utf8_mode else []
        try:
            sock = _connect(path)
        except OSError:
            sock = _start(path, root, flags)
        request = json.dumps({'v': PROTOCOL, 'key': key, 'argv': list(argv), 'cwd': os.getcwd(), 'env': env,
                              'umask': _umask(), 'limits': limits}).encode('ascii')
        framed = len(request).to_bytes(4, 'big') + request
        sent = sock.sendmsg([framed], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [0, 1, 2]))])
        sock.sendall(framed[sent:])
        sock.settimeout(ACK_WAIT)
        if _line(sock, bytearray()) != b'S':
            sock.close()
            return None
    except (OSError, ValueError, TypeError, UnicodeError, OverflowError):
        return None
    return _wait(sock)


def _umask():
    mask = os.umask(0o77)
    os.umask(mask)
    return mask


def _line(sock, buffer):
    """The next newline-terminated message from the server, or None at end of stream."""
    while True:
        end = buffer.find(b'\n')
        if end >= 0:
            line = bytes(buffer[:end])
            del buffer[:end + 1]
            return line
        chunk = sock.recv(4096)
        if not chunk:
            return None
        buffer += chunk


def _wait(sock):
    """The build runs on the server: forward our termination signals to it and wait for its answer."""
    import json
    import signal
    def forward(number, frame):
        try:
            sock.send(b'sig %d\n' % number)
        except OSError:
            pass
    saved = {}
    for name in FORWARD:
        saved[getattr(signal, name)] = signal.signal(getattr(signal, name), forward)
    sock.settimeout(None)
    buffer = bytearray()
    answer = None
    while answer is None:
        try:
            line = _line(sock, buffer)
        except InterruptedError:
            continue
        except OSError:
            line = None
        if line is None:
            break
        try:
            answer = json.loads(line)
        except ValueError:
            continue
    sock.close()
    for number, handler in saved.items():
        signal.signal(number, handler)
    if answer is None:
        sys.stderr.write('ail: the compile server stopped during the build\n')
        return 1
    if 'sig' in answer:
        number = answer['sig']
        try:
            signal.signal(number, signal.SIG_DFL)
            os.kill(os.getpid(), number)
            signal.pause()
        except (OSError, ValueError):
            pass
        return 128 + number
    return answer.get('rc', 1)


# ----------------------------------------------------------------------------------------------- server

class Template:
    """The imported compiler and what a worker needs to behave like a fresh `python ail_chatgpt.py` / `python pyc.py`."""

    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.package = os.path.join(self.root, 'python', 'pkg-v12')
        self.script = os.path.join(self.root, 'ail_chatgpt.py')
        self.pyc_path = os.path.join(self.package, 'pyc.py')
        sys.argv = [self.script]
        import importlib
        self.ail = importlib.import_module('ail_chatgpt')            # appends pkg-v12 to sys.path, as the script does
        for name in ('pyc', 'pyfunc', 'pyboxed2', 'unified', 'ir.driver', 'cruntime', 'pymix'):
            try:
                importlib.import_module(name)
            except ImportError:
                pass
        self.pyc = sys.modules['pyc']
        self.streams = {}
        for number, stream in ((0, sys.stdin), (1, sys.stdout), (2, sys.stderr)):
            self.streams[number] = (stream.encoding, stream.errors)
        self.counter = None
        self.ail_call = self._main_call(self.script, 'raise SystemExit(main())')
        self.pyc_call = self._main_call(self.pyc_path, 'sys.exit(main())')

    @staticmethod
    def _main_call(path, text):
        """The statement that ends the script, compiled at the script's own line so tracebacks read the same."""
        with open(path, encoding='utf-8') as handle:
            lines = handle.read().split('\n')
        number = max(index for index, line in enumerate(lines, 1) if line.strip() == text)
        return compile('\n' * (number - 2) + 'if 1:\n    ' + text + '\n', path, 'exec')

    # -- process state a request replaces ---------------------------------------------------------
    def attach(self, fds):
        for number, descriptor in enumerate(fds):
            if descriptor != number:
                os.dup2(descriptor, number)
                os.close(descriptor)
        self.streams_for(0, 1, 2)

    def streams_for(self, *numbers):
        import io
        for number in numbers:
            encoding, errors = self.streams[number]
            if number == 0:
                sys.stdin = io.TextIOWrapper(io.BufferedReader(io.FileIO(0, 'rb', closefd=False)), encoding=encoding, errors=errors)
            elif number == 1:
                sys.stdout = io.TextIOWrapper(io.BufferedWriter(io.FileIO(1, 'wb', closefd=False)), encoding=encoding, errors=errors,
                                              line_buffering=os.isatty(1))
            else:
                sys.stderr = io.TextIOWrapper(io.BufferedWriter(io.FileIO(2, 'wb', closefd=False)), encoding=encoding, errors=errors,
                                              line_buffering=True, write_through=True)

    @staticmethod
    def environment(env, cwd):
        import tempfile
        import time
        os.environ.clear()
        os.environ.update(env)
        os.chdir(cwd)
        tempfile.tempdir = None             # gettempdir() looks at TMPDIR again
        if hasattr(time, 'tzset'):
            time.tzset()

    # -- one run of a script's last statement ------------------------------------------------------
    def run_main(self, code, namespace):
        """Exit status of `python script`: what the statement does, an uncaught exception printed as Python prints it."""
        import traceback
        try:
            exec(code, namespace)
        except SystemExit as stop:
            return _status(stop.code)
        except KeyboardInterrupt as error:
            traceback.print_exception(type(error), error, error.__traceback__.tb_next)
            return 'sigint'
        except BaseException as error:
            traceback.print_exception(type(error), error, error.__traceback__.tb_next)
            return 1
        return 0

    def finish(self, status):
        import atexit
        import signal
        try:
            atexit._run_exitfuncs()
            sys.stdout.flush()
            sys.stderr.flush()
        except BaseException:
            status = status if status else 120
        if self.counter is not None:
            self.counter()
        if status == 'sigint':
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGINT)
            status = 130
        os._exit(status & 255 if isinstance(status, int) else 1)

    # -- worker A: ail_chatgpt.main for the client ----------------------------------------------------
    def serve_request(self, request, fds):
        import resource
        import signal
        os.umask(request['umask'])
        for name, (soft, hard) in request['limits'].items():
            try:
                resource.setrlimit(getattr(resource, name), (soft, hard))
            except (ValueError, OSError):
                pass
        self.attach(fds)
        self.environment(request['env'], request['cwd'])
        self.counter = _instruction_counter(request['env'].get('AIL_SERVER_ICOUNT'))
        sys.argv = [self.script] + request['argv']
        self.install_run()
        self.finish(self.run_main(self.ail_call, dict(self.ail.__dict__, __name__='__main__')))

    def install_run(self):
        import subprocess
        real = subprocess.run
        compilers = ([sys.executable], [sys.executable, "-B"])
        allowed = {'capture_output', 'text', 'timeout', 'env', 'cwd'}

        def run(command, *positional, **options):
            if not positional and options.get('capture_output') and not set(options) - allowed and isinstance(command, (list, tuple)):
                parts = [str(part) for part in command]
                if self.pyc_path in parts and parts[:parts.index(self.pyc_path)] in compilers:
                    return self.run_pyc(command, **options)
            return real(command, *positional, **options)
        subprocess.run = run

    # -- worker B: `python pyc.py ARGS` as a fork of A --------------------------------------------------
    def run_pyc(self, command, timeout=None, env=None, cwd=None, text=None, capture_output=None):
        import io
        import select
        import signal
        import subprocess
        import tempfile
        import time
        parts = [str(part) for part in command]
        arguments = parts[parts.index(self.pyc_path) + 1:]
        out, err = tempfile.TemporaryFile(), tempfile.TemporaryFile()
        pid = os.fork()
        if pid == 0:
            try:
                import atexit
                atexit._clear()         # A's exit-time cleanups (its temporary directory) are A's to run, not this fork's
                self.counter = None
                os.dup2(out.fileno(), 1)
                os.dup2(err.fileno(), 2)
                self.streams_for(1, 2)
                if env is not None:
                    self.environment(env, cwd or os.getcwd())
                elif cwd:
                    os.chdir(cwd)
                sys.argv = [self.pyc_path] + arguments
                sys.path[:] = [self.package] + [p for p in sys.path if p not in (self.root, self.package, '')]
                self.finish(self.run_main(self.pyc_call, dict(self.pyc.__dict__)))
            except BaseException:
                import traceback
                traceback.print_exc()
            finally:
                os._exit(1)
        descriptor = os.pidfd_open(pid) if hasattr(os, 'pidfd_open') else None
        deadline = None if timeout is None else time.monotonic() + timeout
        try:
            while True:
                if descriptor is not None:
                    left = None if deadline is None else max(0, deadline - time.monotonic())
                    ready = select.select([descriptor], [], [], left)[0]
                    done, status = os.waitpid(pid, 0 if ready else os.WNOHANG)
                else:
                    time.sleep(0.005)
                    done, status = os.waitpid(pid, os.WNOHANG)
                if done:
                    break
                if deadline is not None and time.monotonic() >= deadline:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                    out.seek(0)
                    err.seek(0)
                    raise subprocess.TimeoutExpired(command, timeout, output=out.read(), stderr=err.read())
        except BaseException:
            try:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            except OSError:
                pass
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)
        out.seek(0)
        err.seek(0)
        data = (out.read(), err.read())
        out.close()
        err.close()
        if text:
            data = tuple(io.TextIOWrapper(io.BytesIO(part)).read() for part in data)
        return subprocess.CompletedProcess(command, os.waitstatus_to_exitcode(status), *data)


def _instruction_counter(path):
    """Measurement aid: with AIL_SERVER_ICOUNT=FILE in the request, the user-space instructions this build (workers
    included) executed on the server are appended to FILE when it ends; add them to what tools/icount.c says of the
    client.  x86-64 Linux with perf_event_open only; None elsewhere."""
    import platform
    if not path or platform.machine() != 'x86_64':
        return None
    import ctypes
    import struct
    attribute = struct.pack('IIQQQQQ', 0, 128, 1, 0, 0, 0, (1 << 1) | (1 << 5) | (1 << 6)).ljust(128, bytes(1))
    descriptor = ctypes.CDLL(None, use_errno=True).syscall(298, ctypes.create_string_buffer(attribute, 128), 0, -1, -1, 0)
    if descriptor < 0:
        return None

    def report():
        count = struct.unpack('Q', os.read(descriptor, 8))[0]
        with open(path, 'a') as handle:
            handle.write('%d\n' % count)
    return report


def _status(code):
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    sys.stderr.write(str(code) + '\n')
    return 1


def _supervise(template, conn):
    """Process M: read the request, start worker A, relay signals, report A's end, kill A when the client goes away."""
    import json
    import select
    import signal
    import socket
    os.setsid()
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    conn.settimeout(10)
    try:
        if _peer_uid(conn) != os.getuid():
            os._exit(1)
        data, fds, _, _ = socket.recv_fds(conn, 1 << 16, 8)
        if len(fds) != 3 or len(data) < 4:
            os._exit(1)
        size = int.from_bytes(data[:4], 'big')
        data = bytearray(data[4:])
        while len(data) < size:
            chunk = conn.recv(1 << 16)
            if not chunk:
                os._exit(1)
            data += chunk
        request = json.loads(bytes(data))
        if request.get('v') != PROTOCOL or request.get('key') != template.key(request):
            conn.sendall(b'refused\n')
            os._exit(0)
    except BaseException:
        os._exit(1)
    conn.settimeout(None)
    pid = os.fork()
    if pid == 0:
        try:
            os.setpgid(0, 0)
            conn.close()
            template.serve_request(request, fds)
        finally:
            os._exit(1)
    try:
        os.setpgid(pid, pid)
    except OSError:
        pass
    for descriptor in fds:
        os.close(descriptor)
    conn.sendall(b'S\n')
    watch = os.pidfd_open(pid) if hasattr(os, 'pidfd_open') else None
    buffer = bytearray()
    try:
        while True:
            ready = select.select([conn] + ([watch] if watch is not None else []), [], [], 0.05 if watch is None else None)[0]
            if watch is not None:
                if watch in ready:
                    break
            else:
                done, status = os.waitpid(pid, os.WNOHANG)
                if done:
                    break
            if conn in ready:
                chunk = conn.recv(4096)
                if not chunk:                                  # the client died: end the build and everything it started
                    os.killpg(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                    os._exit(0)
                buffer += chunk
                while b'\n' in buffer:
                    line, _, rest = bytes(buffer).partition(b'\n')
                    buffer[:] = rest
                    words = line.split()
                    if len(words) == 2 and words[0] == b'sig' and words[1].isdigit():
                        number = int(words[1])
                        if number in [getattr(signal, name) for name in FORWARD]:
                            try:
                                os.killpg(pid, number)
                            except OSError:
                                pass
        if watch is not None:
            try:
                os.killpg(pid, signal.SIGKILL)         # A is a zombie, its pid is still ours: what it left behind goes first
            except OSError:
                pass
            status = os.waitpid(pid, 0)[1]
        if os.WIFSIGNALED(status):
            answer = {'sig': os.WTERMSIG(status)}
        else:
            answer = {'rc': os.WEXITSTATUS(status)}
        conn.sendall(json.dumps(answer).encode() + b'\n')
    except OSError:
        pass
    os._exit(0)


def serve(path, idle, root):
    import select
    import signal
    import socket
    import time
    os.chdir('/')
    template = Template(root)
    template.key = lambda request: identity(root, request['env'], {name: request['limits'].get(name) for name in KEYED_LIMITS})
    os.umask(0o177)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    os.chmod(path, 0o600)
    server.listen(16)
    inode = os.stat(path).st_ino
    print('ready', os.getpid(), file=sys.stderr, flush=True)
    children = set()
    last = time.monotonic()
    while True:
        for pid in list(children):
            try:
                if os.waitpid(pid, os.WNOHANG)[0]:
                    children.discard(pid)
                    last = time.monotonic()
            except ChildProcessError:
                children.discard(pid)
        try:
            alive = os.stat(path).st_ino == inode
        except OSError:
            alive = False
        if not alive or (not children and time.monotonic() - last > idle):
            break
        if not select.select([server], [], [], 1.0)[0]:
            continue
        try:
            conn, _ = server.accept()
        except OSError:
            continue
        pid = os.fork()
        if pid == 0:
            server.close()
            try:
                _supervise(template, conn)
            finally:
                os._exit(1)
        conn.close()
        children.add(pid)
        last = time.monotonic()
    server.close()
    try:
        if os.stat(path).st_ino == inode:
            os.unlink(path)
    except OSError:
        pass


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == "serve":
        serve(sys.argv[2], float(sys.argv[3]), os.path.dirname(os.path.realpath(__file__)))
