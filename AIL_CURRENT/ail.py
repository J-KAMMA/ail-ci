"""AIL-only built-ins for CPython (the `from ail import ...` surface).

The compiler lowers these names to its own runtime; this module is the behaviourally equal
pure-Python version, so a converted program runs under CPython.  The names are the free functions
declared in ``ail_builtin_api.DECLARATIONS`` that CPython does not have, plus the keyed heap
helpers and ``par_range``.
"""
import heapq
import math
import os
import select
import socket
import stat
import struct
import sys
import time

AIL_BUILTINS = frozenset((
    'append_bytes', 'current_dir', 'file_chunks', 'file_size', 'float64_decode',
    'float64_encode', 'flush_stdout', 'get_env', 'heappop', 'heappush', 'integer_decode',
    'integer_encode', 'is_dir', 'jscharat', 'jsdiv', 'jsnegzero', 'list_dir', 'make_dir',
    'monotonic_ms', 'open_binary', 'par_range', 'path_exists', 'pcm16_scale_le', 'read_bytes',
    'read_stdin_bytes', 'remove_dir', 'remove_file', 'replace_path', 'same_file', 'tcp_connect',
    'tcp_listen', 'tcp_poll', 'wrapping_add', 'wrapping_mul', 'wrapping_sub', 'write_bytes',
    'write_stdout_bytes', 'write_text',
))

_INT64 = 1 << 63
_MOD64 = 1 << 64
_INT_MAX = 2147483647

par_range = range


class _BinaryFile:
    __slots__ = ('_file',)

    def __init__(self, path, mode):
        if not isinstance(mode, str) or not 1 <= len(mode) <= 3:
            raise ValueError('invalid binary open mode')
        first = mode[0]
        if first not in 'rwa':
            raise ValueError('invalid binary open mode')
        binary = update = False
        for char in mode[1:]:
            if char == 'b' and not binary:
                binary = True
            elif char == '+' and not update:
                update = True
            else:
                raise ValueError('invalid binary open mode')
        spelling = first + 'b' + ('+' if update else '')
        self._file = open(path, spelling)

    def read(self, size):
        if size < 0:
            raise ValueError('negative read size')
        return self._file.read(size)

    def readinto(self, buffer):
        return self._file.readinto(buffer)

    def write(self, data):
        return self._file.write(data)

    def seek(self, offset, whence=0):
        if whence < 0 or whence > 2:
            raise ValueError('invalid whence')
        return self._file.seek(offset, whence)

    def tell(self):
        return self._file.tell()

    def flush(self):
        self._file.flush()

    def close(self):
        if self._file is not None:
            try:
                self._file.close()
            finally:
                self._file = None

    @property
    def closed(self):
        return int(self._file is None or self._file.closed)


class _TcpSocket:
    __slots__ = ('_socket', '_listener', '_write_closed')

    def __init__(self, sock, listener=False):
        self._socket = sock
        self._listener = bool(listener)
        self._write_closed = False

    def _ready(self):
        if self._socket is None:
            raise ValueError('closed TCP socket')

    def _stream(self):
        self._ready()
        if self._listener:
            raise OSError('operation on a listening socket')

    def recv(self, size):
        self._stream()
        if size < 0 or size > _INT_MAX:
            raise ValueError('invalid receive size')
        if not size:
            return b''
        return self._socket.recv(size)

    def recv_into(self, buffer):
        self._stream()
        if not len(buffer):
            return 0
        return self._socket.recv_into(buffer, min(len(buffer), _INT_MAX))

    def send(self, data):
        self._stream()
        if self._write_closed:
            raise OSError('write side closed')
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            sent = self._socket.send(view[offset:offset + _INT_MAX])
            if sent <= 0:
                raise OSError('send failed')
            offset += sent
        return offset

    def send_some(self, data):
        self._stream()
        if self._write_closed:
            raise OSError('write side closed')
        if not len(data):
            return 0
        sent = self._socket.send(memoryview(data)[:_INT_MAX])
        if sent <= 0:
            raise OSError('send failed')
        return sent

    def accept(self):
        self._ready()
        if not self._listener:
            raise OSError('accept on a connected socket')
        child, _address = self._socket.accept()
        return _TcpSocket(child, False)

    def local_port(self):
        self._ready()
        return self._socket.getsockname()[1]

    def _wait(self, milliseconds, writable):
        self._ready()
        if milliseconds < -1 or milliseconds > _INT_MAX:
            raise ValueError('invalid wait time')
        if writable and self._listener:
            raise OSError('a listening socket is not writable')
        if milliseconds < 0:
            timeout = None
        else:
            timeout = milliseconds / 1000.0
        if hasattr(select, 'poll'):
            poller = select.poll()
            events = select.POLLOUT if writable else select.POLLIN
            poller.register(self._socket.fileno(), events)
            result = poller.poll(None if milliseconds < 0 else milliseconds)
            if not result:
                return 0
            revents = result[0][1]
            if revents & select.POLLNVAL:
                raise OSError('invalid socket')
            if revents & (events | select.POLLHUP | select.POLLERR):
                return 1
            raise OSError('unexpected poll event')
        readable, writable_ready, errors = select.select(
            [] if writable else [self._socket], [self._socket] if writable else [], [self._socket], timeout)
        return 1 if readable or writable_ready or errors else 0

    def wait_readable(self, milliseconds):
        return self._wait(milliseconds, False)

    def wait_writable(self, milliseconds):
        return self._wait(milliseconds, True)

    def set_blocking(self, enabled):
        self._ready()
        if enabled not in (0, 1):
            raise ValueError('set_blocking takes 0 or 1')
        self._socket.setblocking(bool(enabled))

    def shutdown_write(self):
        self._stream()
        if not self._write_closed:
            self._socket.shutdown(socket.SHUT_WR)
            self._write_closed = True

    def close(self):
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None
                self._write_closed = True

    @property
    def closed(self):
        return int(self._socket is None)


def _wrap64(value):
    return ((value + _INT64) % _MOD64) - _INT64


def wrapping_add(a, b):
    return _wrap64(int(a) + int(b))


def wrapping_sub(a, b):
    return _wrap64(int(a) - int(b))


def wrapping_mul(a, b):
    return _wrap64(int(a) * int(b))


def _key_lt(a, b, key):
    return key(a) < key(b) if key is not None else a < b


def _siftdown(heap, startpos, pos, key):
    newitem = heap[pos]
    while pos > startpos:
        parentpos = (pos - 1) >> 1
        parent = heap[parentpos]
        if _key_lt(newitem, parent, key):
            heap[pos] = parent
            pos = parentpos
            continue
        break
    heap[pos] = newitem


def _siftup(heap, pos, key):
    endpos = len(heap)
    startpos = pos
    newitem = heap[pos]
    childpos = 2 * pos + 1
    while childpos < endpos:
        rightpos = childpos + 1
        if rightpos < endpos and not _key_lt(heap[childpos], heap[rightpos], key):
            childpos = rightpos
        heap[pos] = heap[childpos]
        pos = childpos
        childpos = 2 * pos + 1
    heap[pos] = newitem
    _siftdown(heap, startpos, pos, key)


def heappush(heap, item, key=None):
    if key is None:
        heapq.heappush(heap, item)
        return
    heap.append(item)
    _siftdown(heap, 0, len(heap) - 1, key)


def heappop(heap, key=None):
    if key is None:
        return heapq.heappop(heap)
    if not heap:
        raise IndexError('pop from an empty heap')
    last = heap.pop()
    if not heap:
        return last
    root = heap[0]
    heap[0] = last
    _siftup(heap, 0, key)
    return root


def read_stdin_bytes(size):
    if size < 0:
        raise ValueError('negative read size')
    chunks = []
    remaining = size
    while remaining > 0:
        data = sys.stdin.buffer.read(min(remaining, 1 << 20))
        if not data:
            break
        chunks.append(data)
        remaining -= len(data)
    return b''.join(chunks) if len(chunks) != 1 else chunks[0]


def write_stdout_bytes(data):
    sys.stdout.flush()
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def flush_stdout():
    sys.stdout.flush()


def read_bytes(path):
    with open(path, 'rb') as handle:
        return handle.read()


def write_bytes(path, data):
    with open(path, 'wb') as handle:
        handle.write(data)


def append_bytes(path, data):
    with open(path, 'ab') as handle:
        handle.write(data)


def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(text)


def open_binary(path, mode):
    return _BinaryFile(path, mode)


def file_chunks(path, size):
    if size <= 0:
        raise ValueError('file_chunks size must be positive')
    chunk = size if size < 65536 else 65536
    with open(path, 'rb') as handle:
        while True:
            data = handle.read(chunk)
            if not data:
                return
            yield data


def get_env(name, default):
    if not name or '\0' in name or '=' in name:
        raise ValueError('invalid environment name')
    value = os.environ.get(name)
    return default if value is None else value


def current_dir():
    return os.getcwd()


def list_dir(path):
    return os.listdir(path)


def path_exists(path):
    if not path:
        return 0
    return int(os.path.exists(path))


def is_dir(path):
    if not path:
        return 0
    return int(os.path.isdir(path))


def file_size(path):
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode):
        raise OSError('not a regular file')
    return info.st_size


def same_file(first, second):
    try:
        a = os.stat(first)
    except FileNotFoundError:
        return 0
    except NotADirectoryError:
        return 0
    try:
        b = os.stat(second)
    except FileNotFoundError:
        return 0
    except NotADirectoryError:
        return 0
    return int(a.st_dev == b.st_dev and a.st_ino == b.st_ino)


def make_dir(path):
    os.mkdir(path, 0o777)


def remove_file(path):
    os.unlink(path)


def remove_dir(path):
    os.rmdir(path)


def replace_path(source, destination):
    os.replace(source, destination)


def monotonic_ms():
    return int(time.monotonic() * 1000)


def integer_decode(data, width, byteorder):
    if width not in (1, 2, 4, 8):
        raise ValueError('width must be 1, 2, 4 or 8')
    if byteorder not in (0, 1):
        raise ValueError('byteorder must be 0 or 1')
    if len(data) % width:
        raise ValueError('byte length is not a multiple of width')
    order = 'little' if byteorder == 0 else 'big'
    signed = width == 8
    return [int.from_bytes(data[index:index + width], order, signed=signed)
            for index in range(0, len(data), width)]


def integer_encode(values, width, byteorder):
    if width not in (1, 2, 4, 8):
        raise ValueError('width must be 1, 2, 4 or 8')
    if byteorder not in (0, 1):
        raise ValueError('byteorder must be 0 or 1')
    order = 'little' if byteorder == 0 else 'big'
    mask = (1 << (width * 8)) - 1
    if width != 8:
        for value in values:
            if value < 0 or value > mask:
                raise ValueError('value out of range for width')
    return b''.join((int(value) & mask).to_bytes(width, order) for value in values)


def float64_decode(data, byteorder):
    if byteorder not in (0, 1):
        raise ValueError('byteorder must be 0 or 1')
    if len(data) % 8:
        raise ValueError('byte length is not a multiple of 8')
    prefix = '<' if byteorder == 0 else '>'
    return list(struct.unpack(prefix + 'd' * (len(data) // 8), data))


def float64_encode(values, byteorder):
    if byteorder not in (0, 1):
        raise ValueError('byteorder must be 0 or 1')
    prefix = '<' if byteorder == 0 else '>'
    return struct.pack(prefix + 'd' * len(values), *values)


def pcm16_scale_le(data, numerator, denominator):
    if numerator < -65536 or numerator > 65536:
        raise ValueError('numerator out of range')
    if denominator < 1 or denominator > 65536:
        raise ValueError('denominator out of range')
    if len(data) % 2:
        raise ValueError('byte length is not a multiple of 2')
    out = bytearray(len(data))
    for index in range(0, len(data), 2):
        sample = data[index] | (data[index + 1] << 8)
        if sample >= 32768:
            sample -= 65536
        value = sample * numerator
        if value < 0:
            value = -((-value) // denominator)
        else:
            value //= denominator
        if value < -32768:
            value = -32768
        if value > 32767:
            value = 32767
        out[index] = value & 0xFF
        out[index + 1] = (value >> 8) & 0xFF
    return bytes(out)


def jscharat(text, index):
    if index < 0:
        return ''
    units = text.encode('utf-16-le')
    offset = index * 2
    if offset + 2 > len(units):
        return ''
    return units[offset:offset + 2].decode('utf-16-le', 'surrogatepass')


def jsdiv(left, right):
    if right == 0.0:
        if left == 0.0 or math.isnan(left):
            return math.nan
        sign = math.copysign(1.0, left) * math.copysign(1.0, right)
        return math.copysign(math.inf, sign)
    return left / right


def jsnegzero(value):
    return int(value == 0.0 and math.copysign(1.0, value) < 0)


def tcp_connect(host, port):
    if not host or port < 1 or port > 65535:
        raise ValueError('invalid TCP endpoint')
    host.encode('ascii')
    return _TcpSocket(socket.create_connection((host, port)), False)


def tcp_listen(host, port, backlog):
    if not host or port < 0 or port > 65535 or backlog < 1 or backlog > _INT_MAX:
        raise ValueError('invalid TCP listener')
    host.encode('ascii')
    last_error = None
    for family, kind, proto, _canonname, address in socket.getaddrinfo(
            host, port, socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_TCP):
        sock = socket.socket(family, kind, proto)
        try:
            sock.bind(address)
            sock.listen(backlog)
        except OSError as error:
            last_error = error
            sock.close()
            continue
        return _TcpSocket(sock, True)
    if last_error is not None:
        raise last_error
    raise OSError('cannot listen')


def tcp_poll(peers, interests, milliseconds):
    if milliseconds < -1 or milliseconds > _INT_MAX or len(interests) != len(peers):
        raise ValueError('invalid tcp_poll arguments')
    result = [0] * len(peers)
    poller = select.poll()
    registered = []
    for index, (peer, interest) in enumerate(zip(peers, interests)):
        if interest < 0 or interest > 3:
            raise ValueError('invalid tcp_poll interest')
        if not isinstance(peer, _TcpSocket):
            raise TypeError('tcp_poll takes tcpsocket values')
        peer._ready()
        if (interest & 2) and peer._listener:
            raise OSError('a listening socket is not writable')
        if interest:
            events = (select.POLLIN if interest & 1 else 0) | (select.POLLOUT if interest & 2 else 0)
            poller.register(peer._socket.fileno(), events)
            registered.append((index, interest, events))
    if registered:
        ready = poller.poll(None if milliseconds < 0 else milliseconds)
        by_fd = {fd: revents for fd, revents in ready}
        for index, interest, events in registered:
            revents = by_fd.get(peers[index]._socket.fileno(), 0)
            if revents & select.POLLNVAL:
                raise OSError('invalid socket')
            if revents & (select.POLLHUP | select.POLLERR):
                result[index] = interest
            else:
                result[index] = ((interest & 1) if revents & select.POLLIN else 0) | \
                                ((interest & 2) if revents & select.POLLOUT else 0)
    return result
