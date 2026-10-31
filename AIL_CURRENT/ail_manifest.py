"""Read AIL_CURRENT/MANIFEST.json together with its per-file pin shards (AIL_CURRENT/manifest.d/).

Why shards: the SHA-256 pins used to be two big dicts inside MANIFEST.json, so every pull request that
touched a pinned file or added a test edited that one file, and two requests that merely appended a
line at the end of a dict conflicted.  The pins now live one per line, sorted by name, in 256 small
files `manifest.d/<xx>.txt` (xx = first two hex digits of sha256(name)), so requests that touch
different files touch different lines (nearly always different files) and merge without a conflict.
MANIFEST.json keeps only the static provenance fields.

A shard line is `<sha256> <flags> <name>`.  flags is `-` or letters: `s` the file is in sdk_files,
`f` the file is in the legacy `files` map.  `load()` assembles the same dictionary the old single
file held (`sha256`, `files`, `sdk_files` plus the provenance fields), so every reader sees the same
data.  A tree without manifest.d (an exported SDK, a legacy checkout) is read as the plain
MANIFEST.json it is.
"""
import hashlib
import json
from pathlib import Path

SHARD_DIR = 'manifest.d'
MARKERS = ('<<<<<<<', '=======', '>>>>>>>', '|||||||')


def bucket(name):
    return hashlib.sha256(name.encode('utf-8')).hexdigest()[:2]


def shard_name(name):
    return bucket(name) + '.txt'


def _flags(text):
    return '' if text == '-' else ''.join(sorted(set(text)))


def parse(text, source='shard', repair=False):
    """Return {name: (sha256, flags)}.  repair=True tolerates git conflict markers and duplicate names
    (the later line wins, flags are united); update_manifest.py recomputes the pins afterwards."""
    pins = {}
    for number, line in enumerate(text.split('\n'), 1):
        if not line:
            continue
        if repair and line.startswith(MARKERS):
            continue
        parts = line.split(' ', 2)
        if (len(parts) != 3 or len(parts[0]) != 64 or any(c not in '0123456789abcdef' for c in parts[0])
                or not parts[2] or not set(_flags(parts[1])) <= set('sf')):
            raise ValueError(f'{source}:{number}: malformed pin line')
        sha, flags, name = parts[0], _flags(parts[1]), parts[2]
        if name in pins:
            if not repair:
                raise ValueError(f'{source}:{number}: duplicate pin for {name}')
            flags = _flags(''.join(set(flags) | set(pins[name][1])) or '-')
        pins[name] = (sha, flags)
    return pins


def read_pins(root, repair=False):
    """All pins of the shard directory as {name: (sha256, flags)} (empty without the directory)."""
    directory = Path(root) / SHARD_DIR
    pins = {}
    if not directory.is_dir():
        return pins
    for path in sorted(directory.iterdir()):
        if path.name.startswith('.'):
            continue
        if path.suffix != '.txt' or len(path.stem) != 2:
            raise ValueError(f'unexpected file in {SHARD_DIR}: {path.name}')
        for name, value in parse(path.read_text(encoding='utf-8'), f'{SHARD_DIR}/{path.name}', repair).items():
            if not repair and shard_name(name) != path.name:
                raise ValueError(f'{SHARD_DIR}/{path.name}: {name} belongs in {shard_name(name)}')
            if name in pins and not repair:
                raise ValueError(f'duplicate pin for {name}')
            pins[name] = value
    return pins


def render(pins):
    """{shard file name: exact text} for the given {name: (sha256, flags)} (canonical form)."""
    shards = {}
    for name in sorted(pins):
        if not name or any(c in name for c in '\n\r') or name != name.strip():
            raise ValueError(f'unsupported manifest name: {name!r}')
        sha, flags = pins[name]
        shards.setdefault(shard_name(name), []).append(f'{sha} {_flags(flags) or "-"} {name}\n')
    return {file: ''.join(lines) for file, lines in shards.items()}


def write_pins(root, pins):
    """Write the canonical shards and remove shard files that are no longer needed."""
    directory = Path(root) / SHARD_DIR
    directory.mkdir(exist_ok=True)
    texts = render(pins)
    for file, text in texts.items():
        path = directory / file
        data = text.encode('utf-8')
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
    for path in directory.glob('*.txt'):
        if path.name not in texts:
            path.unlink()


def load(root):
    """The manifest dictionary: MANIFEST.json with the shard pins merged into sha256/files/sdk_files."""
    root = Path(root)
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    if not (root / SHARD_DIR).is_dir():
        return manifest
    pins = read_pins(root)
    manifest['sha256'] = {**manifest.get('sha256', {}), **{name: sha for name, (sha, _) in pins.items()}}
    manifest['files'] = {**manifest.get('files', {}), **{name: sha for name, (sha, f) in pins.items() if 'f' in f}}
    manifest['sdk_files'] = sorted(set(manifest.get('sdk_files', [])) | {name for name, (_, f) in pins.items() if 's' in f})
    return manifest


def fingerprint(root):
    """SHA-256 over every byte of the manifest sources (equal to the file's hash for a plain MANIFEST.json)."""
    root = Path(root)
    digest = hashlib.sha256((root / 'MANIFEST.json').read_bytes())
    directory = root / SHARD_DIR
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            digest = hashlib.sha256(digest.digest() + path.name.encode('utf-8') + b'\0' + path.read_bytes())
    return digest.hexdigest()
