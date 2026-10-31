"""Memo tables for work the general path repeats on a tree that has not changed.

`unified.analyze` restarts itself with a larger demote set (up to a dozen times for one program), `pyboxed2._build`
re-runs the whole `Compiler` for a conflict, and `pyc` builds the same source on the general path up to three times
when the typed path refused it.  Each of those passes asks `bigcap.marked` / `bigcap.own_marked` the same two
questions about the same tree (a call graph closure over a walk of every function body: ~30% of a refusing build on
the compare-lab sources).  Both are pure functions of (the tree, `local`, `typed`, the AIL_* environment), so the
answer is kept, keyed by a digest of the tree's content (`ast.dump` with attributes), never by object identity: a
tree an earlier pass edited in place gets a new key.

`mix_report` does the same for `pymix.analyze`.

Also `failed_build`: the refusal of `pyboxed2.build` for a source, kept for the rest of the process.  `pyc` builds
the same source on the general path again after the typed path's second and third attempt; a refusal is a function
of (source, allow_mix, environment) and the repeat took exactly the same 8-25 s to say the same thing.

Nothing here changes what is computed: a miss calls the original function, a hit returns a copy of what it returned.
`AIL_NO_WALKMEMO=1` turns both off (measurement only).
"""
import ast
import copy
import hashlib
import os

_MAX = 48
_MARKS = {}
_FAILS = {}
_MIX = {}


def enabled():
    return os.environ.get('AIL_NO_WALKMEMO') != '1'


def _env():
    return tuple(sorted((k, v) for k, v in os.environ.items() if k.startswith('AIL_')))


def fingerprint(tree):
    """A digest of everything in `tree` (fields, constants, line numbers), or None when it cannot be taken."""
    try:
        text = ast.dump(tree, include_attributes=True)
    except (RecursionError, ValueError, TypeError):
        return None
    return hashlib.blake2b(text.encode('utf-8', 'surrogatepass'), digest_size=16).digest()


def marks(tree, own, local=True, typed=False, fp=None):
    """`bigcap.own_marked(tree, local)` (own) or `bigcap.marked(tree, local, typed)`, remembered per tree content."""
    import bigcap
    call = (lambda: bigcap.own_marked(tree, local)) if own else (lambda: bigcap.marked(tree, local, typed))
    if not enabled():
        return call()
    if fp is None:
        fp = fingerprint(tree)
    if fp is None:
        return call()
    key = (fp, own, local, typed, _env())
    hit = _MARKS.get(key)
    if hit is None:
        hit = call()
        if len(_MARKS) >= _MAX:
            _MARKS.pop(next(iter(_MARKS)))
        _MARKS[key] = dict(hit)
    return dict(hit)


def fail_key(source, allow_mix):
    return (source, bool(allow_mix), _env()) if enabled() else None


def failed_build(source, allow_mix):
    """A fresh copy of the refusal `pyboxed2.build` raised earlier for this source, or None."""
    key = fail_key(source, allow_mix)
    if key is None:
        return None
    hit = _FAILS.get(key)
    if hit is None and not allow_mix:
        # a build with typed clones switched off refuses the same way when the build with them wired none
        hit = _FAILS.get(fail_key(source, True))
        if hit is not None and not getattr(hit, '_mix_inert', False):
            hit = None
    if hit is None:
        return None
    return _fresh(hit)


def remember_failure(source, allow_mix, error):
    key = fail_key(source, allow_mix)
    if key is None:
        return
    if len(_FAILS) >= 8:
        _FAILS.pop(next(iter(_FAILS)))
    _FAILS[key] = _fresh(error)


def _fresh(error):
    new = copy.copy(error)
    new.__traceback__ = None
    new.__context__ = None
    new.__cause__ = None
    return new


def mix_report(pymix, source):
    """`pymix.analyze(source)`, remembered for the rest of the process.  The analysis compiles every candidate function on
    the typed path (it was ~45% of a refusing build of tree_fold) and the general path asks it again for each re-run of the
    `Compiler` and for each of pyc's builds of the same source.  A function of (source, environment); its result is only
    read by `Compiler._setup_mix`.  An analysis that raises is not remembered."""
    if not enabled():
        return pymix.analyze(source)
    key = (source, _env())
    hit = _MIX.get(key)
    if hit is None:
        hit = pymix.analyze(source)
        if len(_MIX) >= 4:
            _MIX.pop(next(iter(_MIX)))
        _MIX[key] = hit
    return hit
