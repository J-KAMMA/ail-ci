"""Shared helpers for the wedge3 workloads (no library code lives here)."""
import importlib.util
import os
import sys


def impl():
    return os.environ.get('WEDGE_IMPL', 'cpython')


def hybrid_dir():
    d = os.environ.get('WEDGE_HYBRID_DIR')
    if not d:
        raise SystemExit('WEDGE_IMPL=hybrid needs WEDGE_HYBRID_DIR')
    if d not in sys.path:
        sys.path.insert(0, d)
    return d


def load_hybrid(name):
    d = hybrid_dir()
    path = os.path.join(d, name + '.py')
    spec = importlib.util.spec_from_file_location('wedge_hy_' + name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    # A second copy of a networkx module re-registers its dispatchable algorithms; clear the
    # global registry for the duration of the load and restore it afterwards.
    registry = None
    saved = None
    try:
        from networkx.utils import backends as _nx_backends
        registry = _nx_backends._registered_algorithms
        saved = dict(registry)
        registry.clear()
    except Exception:
        registry = None
    try:
        spec.loader.exec_module(mod)
    finally:
        if registry is not None and saved is not None:
            registry.clear()
            registry.update(saved)
    return mod


class LCG:
    def __init__(self, seed):
        self.x = seed & 0xFFFFFFFF

    def next(self):
        self.x = (1103515245 * self.x + 12345) & 0x7FFFFFFF
        return self.x

    def below(self, n):
        return self.next() % n
