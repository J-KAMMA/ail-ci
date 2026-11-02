"""Opt-in front-end cache: the C emitted for one program, keyed by everything that can change it.

The cache is off unless ``AIL_FE_CACHE`` is true (or ``ail_chatgpt.py compile --fe-cache``).
A key covers the merged source text (which already contains every imported module), the
environment a build reads, the compiler package's own files and the Python version.  A hit
skips the Python lowering and compiles the stored C; a miss runs the normal build and stores
the C only after the build succeeded.

Entries live under ``$XDG_CACHE_HOME/ail/fe/c`` (default ``~/.cache/ail/fe/c``), bounded by
``AIL_FE_CACHE_MAX_MB`` (default 200).  The least recently used entries are evicted first.
A corrupt or truncated entry is deleted and treated as a miss.  Writes are atomic.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import buildcache

FORMAT = b'ail-fe-cache-1'
MAGIC = b'AILFEC1\n'
DEFAULT_MAX_MB = 200
MAX_ENTRY = 64 << 20
TRUE = ('1', 'on', 'yes', 'true')


def enabled():
    if os.name == 'nt':
        return False
    return os.environ.get('AIL_FE_CACHE', '').strip().lower() in TRUE


def root():
    configured = os.environ.get('AIL_FE_CACHE_DIR')
    if configured:
        return Path(configured).expanduser()
    xdg = os.environ.get('XDG_CACHE_HOME')
    return (Path(xdg) if xdg else Path.home() / '.cache') / 'ail' / 'fe'


def entries_root():
    return root() / 'c'


def max_bytes():
    try:
        return int(float(os.environ.get('AIL_FE_CACHE_MAX_MB', DEFAULT_MAX_MB)) * (1 << 20))
    except ValueError:
        return DEFAULT_MAX_MB << 20


def digest(*parts):
    h = hashlib.sha256(FORMAT)
    for part in parts:
        data = part if isinstance(part, bytes) else str(part).encode('utf8', 'surrogatepass')
        h.update(len(data).to_bytes(8, 'little'))
        h.update(data)
    return h.hexdigest()


def key(*parts):
    return digest(*parts)


def sources_hash(package):
    return buildcache.sources_hash(package)


def build_env():
    return [item for item in buildcache.build_env() if not item.startswith('AIL_FE_CACHE')]


def _entry_path(key):
    return entries_root() / key[:2] / key


def _discard(path):
    try:
        path.unlink()
    except OSError:
        pass


def get(key):
    path = _entry_path(key)
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
        os.utime(path)
    except OSError:
        pass
    return payload


def put(key, payload):
    if len(payload) > MAX_ENTRY:
        return False
    path = _entry_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        marker = entries_root() / 'CACHEDIR.TAG'
        if not marker.exists():
            marker.write_text('Signature: 8a477f597d28d172789f06886806bc55\n# AIL front-end cache\n')
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
    result = []
    base = entries_root()
    now = time.time()
    try:
        shards = list(os.scandir(base))
    except OSError:
        return result
    for shard in shards:
        if not shard.is_dir():
            continue
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
            if not item.is_file() or item.name == 'CACHEDIR.TAG':
                continue
            result.append((item.path, info.st_size, info.st_mtime))
    return result


def trim(limit=None):
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
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        trim()
    except OSError:
        pass


def stats():
    found = entries()
    return {'path': str(root()), 'entries': len(found), 'bytes': sum(size for _, size, _ in found),
            'limit_bytes': max_bytes(), 'enabled': enabled()}


def clear():
    removed = sum(1 for _ in entries())
    shutil.rmtree(entries_root(), ignore_errors=True)
    _discard(root() / '.trimmed')
    return removed


def pack(meta, blob):
    head = json.dumps(meta, sort_keys=True).encode()
    return len(head).to_bytes(8, 'little') + head + blob


def unpack(payload):
    size = int.from_bytes(payload[:8], 'little')
    return json.loads(payload[8:8 + size]), payload[8 + size:]


def log(message):
    path = os.environ.get('AIL_FE_CACHE_LOG')
    if not path:
        return
    try:
        with open(path, 'a', encoding='utf8') as handle:
            handle.write(message + '\n')
    except OSError:
        pass
