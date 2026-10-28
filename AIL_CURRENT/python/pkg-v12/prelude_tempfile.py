# -*- coding: utf-8 -*-
# prelude_tempfile.py -- the `tempfile` functions that tempfilelib.py builds, as Python source.

_ail_tempfile_counter = 0
_ail_tempfile_tempdir = ''


def _ail_tempfile_gettempdir() -> str:
    global _ail_tempfile_counter, _ail_tempfile_tempdir
    if _ail_tempfile_tempdir != '':
        return _ail_tempfile_tempdir
    candidates = []
    for name in ('TMPDIR', 'TEMP', 'TMP'):
        value = os.environ.get(name, '')
        if value:
            candidates.append(value)
    if os.name != 'nt':
        candidates.append('/tmp')
        candidates.append('/var/tmp')
        candidates.append('/usr/tmp')
    candidates.append(os.getcwd())
    for candidate in candidates:
        directory = candidate
        if directory != os.curdir:
            directory = os.path.abspath(directory)
        if not os.path.isdir(directory):
            continue
        _ail_tempfile_counter = _ail_tempfile_counter + 1
        probe = os.path.join(directory, 'ail-tmp-' + str(_ail_tempfile_counter))
        try:
            os.mkdir(probe, 0o700)
        except OSError:
            continue
        os.rmdir(probe)
        _ail_tempfile_tempdir = directory
        return directory
    raise FileNotFoundError('No usable temporary directory found in ' + str(candidates))


def _ail_tempfile_gettempprefix() -> str:
    return 'tmp'


def _ail_tempfile_mkdtemp(suffix: str, prefix: str, dir: str) -> str:
    global _ail_tempfile_counter
    if not isinstance(suffix, str) or not isinstance(prefix, str) or not isinstance(dir, str):
        raise TypeError('tempfile.mkdtemp() is built for str arguments only')
    attempt = 0
    while attempt < 100:
        attempt = attempt + 1
        _ail_tempfile_counter = _ail_tempfile_counter + 1
        candidate = os.path.join(dir, prefix + str(_ail_tempfile_counter) + suffix)
        if os.path.exists(candidate):
            continue
        try:
            os.mkdir(candidate, 0o700)
        except FileExistsError:
            continue
        return os.path.abspath(candidate)
    raise FileNotFoundError('No usable temporary directory found')


def _ail_tempfile_rmtree(path: str) -> None:
    if os.path.islink(path):
        os.remove(path)
        return
    if not os.path.isdir(path):
        os.remove(path)
        return
    for name in os.listdir(path):
        _ail_tempfile_rmtree(os.path.join(path, name))
    os.rmdir(path)


class _AilTemporaryDirectory:
    name: str

    def __init__(self, suffix: str, prefix: str, dir: str) -> None:
        self.name = _ail_tempfile_mkdtemp(suffix, prefix, dir)

    def cleanup(self) -> None:
        if os.path.exists(self.name):
            _ail_tempfile_rmtree(self.name)

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type: int, exc, tb):
        self.cleanup()
