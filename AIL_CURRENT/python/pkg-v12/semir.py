"""Semantic AIL IR (SemIR), v0.1.

A fact layer inserted between the analysis half of `_one_function` (everything in `pyfunc.py`
above the call to `_stmts`, which decides every container's kind, every records list's arity,
every bytes-backing, every grid-ness) and the C generator (`_stmts`/`_expr`/`_method`/`signature`,
which turn those decisions into text). Before this file existed, those facts lived only as
scattered dict/set attributes on `Ctx` (`ctx.tstride`, `ctx.bkeys`, `ctx.rowbytes`, ...), each
named for the ONE mechanism that first needed it. This module gives them one vocabulary -- a
closed node set (`Scalar`, `Sequence`, `RecordType`, `Collection`) plus one `Facts` record -- so a
later pass can ask a binding what it is and what is known about it, instead of re-deriving the
answer from a dict keyed by convention.

Building this file does not change the language, the analysis, or a single byte of emitted C: see
`test_semir.py`. It CANNOT, by construction, do the analysis over again -- `FunctionIR` is built
from `Ctx`'s already-finished analysis fields, never from the AST directly, and the handful of call
sites in `pyfunc.py` that were changed to read a `FunctionIR` accessor instead of the matching
`Ctx` dict read the exact same backing value the same way (`arity_of` is `self._ctx.tstride[name]`,
literally). See `SEMANTICS.md`'s SemIR section for what is and is not routed through it yet, and
why: in particular, most of `Ctx`'s per-name facts (`tstride`, `bkeys`, `blist`, `trowsf`,
`rowbytes`, `handles`, `ranges`, `row_sort_ks`) are still growing while `_stmts` runs -- a
`sorted(x)` call assigns a brand-new temporary its own arity and float-ness *during* code
generation (`_sorted_into_temp`), not before it -- so `FunctionIR`'s accessors for those facts are
LIVE views over the one `Ctx` instance, not a frozen snapshot taken at construction time. Only the
facts that are genuinely settled before a line of C is emitted (every parameter's kind, the
records guard, whether this function is recursive) are captured once, at construction, and never
re-read from `Ctx` again.

The type-constant strings below (`INT`, `FLT`, ...) mirror `pyfunc.py`'s own module-level
constants by VALUE, deliberately not by import: `pyfunc.py` imports this module, so importing it
back would be circular. They are not free to drift -- `test_semir.py`'s byte-identical corpus
comparison would catch it the moment either side's spelling changed.
"""
from dataclasses import dataclass, field
from typing import FrozenSet, Optional, Tuple

# Mirrors pyfunc.py's INT, FLT, LIST, FLIST, SET, DICT, RANGE, BYTES, HANDLE -- see module
# docstring above for why this is a value-copy rather than an import.
INT, FLT, LIST, FLIST, SET, DICT, RANGE, BYTES, HANDLE = (
    'int', 'float', 'list', 'flist', 'set', 'dict', 'range', 'bytes', 'handle')
NUM = (INT, FLT)


# ------------------------------------------------------------------------------------------------
# Facts -- attached to a binding, never to a node: the same Scalar(INT) means something different
# on a parameter (mutable=False, ownership='caller' -- SEMANTICS section on records parameters:
# "the array a program is given is read-only and lives in the caller's memory; nothing copies it")
# than on a local (mutable=True, ownership='owned' -- freed at every return, `_one_function`'s
# `owned` list). v0.1 carries exactly the fields the task's scope names; three of them
# (`bounded_range`, `unique` outside a Collection, `ordered`) are named here so a later pass has
# somewhere to put the answer, but nothing in this compiler computes a non-default value for them
# yet -- see SEMANTICS.md for exactly which, and why not.
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Facts:
    fixed_length: Optional[int] = None      # a RecordType binding's row width, mirrored here from
                                             # the node for convenience (SEMANTICS: "a list of
                                             # records has one arity") -- None for anything else
    bounded_range: Optional[Tuple[int, int]] = None   # [lo, hi] of every value a name can hold --
                                             # v0.1 never populates this; see SEMANTICS.md
    unique: bool = False                    # true for a Collection(kind='set') binding
    ordered: bool = False                   # "this sequence is sorted" -- v0.1 never populates
                                             # this either; see SEMANTICS.md for why it is
                                             # momentary in this compiler, not a lasting property
    mutable: bool = True                    # false for any parameter (always emitted `const`)
    ownership: str = 'owned'                # 'owned' (freed at every return) | 'caller' (the
                                             # caller's memory, an array/bytes/records parameter,
                                             # never copied) | 'view' (a scalar, a range, or a
                                             # bytes/handle local -- owns nothing itself; see
                                             # `_one_function`'s `owned` list)


# ------------------------------------------------------------------------------------------------
# Nodes. Deliberately not collapsed into one generic "container" node -- see module docstring in
# the task brief this file was built against: a node that only knows "container" has already
# thrown away the thing a later specialisation pass would need to ask for.
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Scalar:
    """`int` (a C `int64_t`) or `float` (a C `double`). No `bool` node is ever constructed in v0.1
    -- see SEMANTICS.md: this compiler has no boolean-typed binding at all, only truthiness
    computed at the point it is used (`_truthy`), so there is nothing today to attach one to."""
    kind: str    # INT | FLT | 'bool' (reserved; unused -- see docstring)


@dataclass(frozen=True)
class RecordType:
    """A fixed-layout row: `arity` fields, all the same C type (`ctx.trowsf`: uniform PER TUPLE,
    never per field -- SEMANTICS section 11), and which field positions are bytes-backed
    (`ctx.rowbytes`, via BPOOL handles rather than raw int64)."""
    arity: int
    uniform: str = INT               # INT | FLT -- every field's C type
    bytes_fields: FrozenSet[int] = frozenset()


@dataclass(frozen=True)
class Sequence:
    """`list[T]` or `bytes`. `elem` is a `Scalar` for a plain list, a `RecordType` for a list of
    fixed-arity tuples (`ctx.tstride`), or the string `'handle'` for a list of nested containers
    (`ctx.nlist`) -- the pool-index level `ctx.hstride`/`ctx.hrowof` describe further, which v0.1
    does not yet fold into this node; see SEMANTICS.md. `kind` distinguishes the three backing
    structs this compiler actually has (`ail_list` / `ail_flist` / `ail_bytes`), never a run-time
    tag on one shared struct (SEMANTICS section 11 again, for FLIST specifically)."""
    elem: object
    kind: str = LIST                 # LIST | FLIST | BYTES


@dataclass(frozen=True)
class Collection:
    """`set[T]` or `dict[K, V]`. `key` is a `Scalar` or the string `'bytes'` (`ctx.bkeys` -- an
    `ail_btab`, hashing/comparing by content, not the int64-identity `ail_tab` every other table
    uses). `value` is `None` for a set, a `Scalar` or `'handle'` (`ctx.ndict`, SEMANTICS section on
    nested containers) for a dict. The array-vs-hash representation described in SEMANTICS.md
    section 21 is NOT a fact of this node: it is chosen per instance, at run time, entirely inside
    `cruntime.c`'s `ail_tab`, from key values `pyfunc.py` never sees at compile time -- there is
    today no compile-time-known key range for this node's `Facts.bounded_range` to carry, and
    inventing one here would misrepresent what the compiler actually knows. See SEMANTICS.md."""
    kind: str                        # SET | DICT
    key: object = Scalar(INT)
    value: object = None


# ------------------------------------------------------------------------------------------------
# Bindings -- a name (a parameter or a local) tied to one node and one Facts.
# ------------------------------------------------------------------------------------------------
@dataclass
class Binding:
    name: str
    node: object
    facts: Facts


def rows_guard_of(ctx):
    """Every records PARAMETER, with its fixed arity -- checked once, at function entry, before
    anything reads a row (SEMANTICS: the caller's slot count and the source's arity have to
    agree). Identical to the expression `_one_function` computed inline before this file existed;
    named here because every name in it is a parameter, so -- unlike a local's `ctx.tstride` entry
    -- it can never change again after this point (a parameter cannot be reassigned; see
    `Ctx.declare`)."""
    return [(nm, ctx.tstride[nm]) for nm, _k in ctx.params if nm in ctx.rowparam]


def _record_node(ctx, name):
    k = ctx.tstride[name]
    return RecordType(arity=k,
                       uniform=FLT if name in ctx.trowsf else INT,
                       bytes_fields=frozenset(ctx.rowbytes.get(name, ())))


def _param_binding(name, kind, ctx):
    """One parameter's Binding, settled the moment `Ctx` exists -- a parameter's kind, its
    records arity (if any), its float-uniformity and its grid-ness are all fixed by `_signatures`/
    the `_mark_*` calls in `_one_function` before ANY of them can change again (unlike a local's
    `ctx.types` entry, which `declare()` only fills in as `_stmts` reaches its first assignment).
    """
    facts = Facts(mutable=False, ownership='caller' if kind in ('array', BYTES) else 'view')
    if kind == 'array':
        if name in ctx.tstride:
            node = Sequence(_record_node(ctx, name),
                             kind=FLIST if name in ctx.trowsf else LIST)
            facts = Facts(fixed_length=ctx.tstride[name], mutable=False, ownership='caller')
        else:
            node = Sequence(Scalar(INT), kind=LIST)
        return Binding(name, node, facts)
    if kind == BYTES:
        return Binding(name, Sequence(Scalar(INT), kind=BYTES), facts)
    if kind == FLT:
        return Binding(name, Scalar(FLT), facts)
    return Binding(name, Scalar(INT), facts)


def _local_node(ctx, name):
    """Best-effort Binding for an ordinary LOCAL, from whatever `Ctx` currently knows.

    Unlike a parameter, a local's base kind (`ctx.types[name]`) is only known once `declare()` has
    seen its first assignment -- during `_stmts`, not before it (see module docstring). Called
    from `FunctionIR.bindings()`, which is only ever used AFTER `_stmts` has returned, so every
    local -- including a compiler-introduced temporary like `_sorted_into_temp`'s `_t3` -- already
    has an entry here.
    """
    t = ctx.types.get(name)
    if t == INT:
        node = Scalar(INT)
    elif t == FLT:
        node = Scalar(FLT)
    elif t == RANGE:
        node = Scalar(INT)                    # a range is its two bounds, both plain ints
    elif t == BYTES:
        node = Sequence(Scalar(INT), kind=BYTES)
    elif t == HANDLE:
        node = Scalar(INT)                    # a bare pool index -- see `ctx.handles`
    elif t == FLIST:
        node = Sequence(_record_node(ctx, name), kind=FLIST) if name in ctx.tstride \
            else Sequence(Scalar(FLT), kind=FLIST)
    elif t == LIST:
        if name in ctx.tstride:
            node = Sequence(_record_node(ctx, name), kind=LIST)
        elif name in ctx.nlist:
            node = Sequence('handle', kind=LIST)
        elif name in ctx.blist:
            node = Sequence(Scalar(INT), kind=LIST)   # bytes VALUES via BPOOL handles per slot
        else:
            node = Sequence(Scalar(INT), kind=LIST)
    elif t in (SET, DICT):
        key = 'bytes' if name in ctx.bkeys else Scalar(INT)
        value = None
        if t == DICT:
            value = 'handle' if name in ctx.ndict else Scalar(INT)
        node = Collection(kind=t, key=key, value=value)
    else:
        node = None
    fixed_length = node.elem.arity if isinstance(node, Sequence) and isinstance(node.elem, RecordType) else None
    ownership = 'view' if t in (None, INT, FLT, RANGE, BYTES, HANDLE) else 'owned'
    unique = t == SET
    return Binding(name, node, Facts(fixed_length=fixed_length, ownership=ownership, unique=unique))


class FunctionIR:
    """The semantic facts for one function. Constructed once in `_one_function`, immediately
    before `body = _stmts(fn.body, ctx, 1)` -- the actual seam between analysis and C generation --
    and handed back on `ctx.semir` so both halves of `_one_function` (before AND after that call)
    can reach it."""

    def __init__(self, ctx, cname, recursive):
        self._ctx = ctx
        self.cname = cname
        self.recursive = recursive
        self.ret = Scalar(FLT) if ctx.ret == FLT else Scalar(INT)   # descriptive only -- see
                                                                     # SEMANTICS.md; nothing reads
                                                                     # this back yet for a
                                                                     # container/tuple/multi return
        self.params = [_param_binding(name, kind, ctx) for name, kind in ctx.params]
        # `_one_function` already computed this (via `rows_guard_of`, above) and stored it on
        # `ctx.rows_guard` before this `FunctionIR` is constructed -- mirrored here, not
        # recomputed, so there is exactly one formula for it, not two that could drift apart.
        self.rows_guard = ctx.rows_guard

    def param_by_name(self, name):
        for b in self.params:
            if b.name == name:
                return b
        return None

    # -- live views over facts `_stmts` can still grow (see module docstring) --------------------
    def has_record(self, name):
        """True if `name` is a list of fixed-arity tuples (`ctx.tstride`) -- a live read: a
        `sorted()`/`list()` copy created while emitting an earlier statement can add an entry here
        that did not exist when this `FunctionIR` was constructed."""
        return name in self._ctx.tstride

    def arity_of(self, name):
        """The row width for a `has_record(name)` binding -- `ctx.tstride[name]`, read live for
        the same reason as `has_record` above."""
        return self._ctx.tstride[name]

    def record_of(self, name):
        """The full `RecordType` for a `has_record(name)` binding, built fresh from the live
        `Ctx` state (arity, float-uniformity, bytes-marked fields)."""
        return _record_node(self._ctx, name)

    def is_bytes_keyed(self, name):
        """True if `name` (a set or dict) is keyed by bytes CONTENT (`ctx.bkeys`, an `ail_btab`)
        rather than int64 identity (a plain `ail_tab`)."""
        return name in self._ctx.bkeys

    def ownership_of(self, name):
        """'owned' if this local is freed at every return (`_one_function`'s `owned` list, the
        Facts.ownership this compiler actually enforces today), else 'view'."""
        t = self._ctx.types.get(name)
        if t in (None, INT, FLT, RANGE, BYTES, HANDLE):
            return 'view'
        return 'owned'

    def bindings(self):
        """Every local currently declared (`ctx.locals`, in declaration order), as a `Binding` --
        meaningful only AFTER `_stmts` has run (see module docstring): a local's base kind is a
        product of code generation itself, not of the analysis phase this IR otherwise mirrors."""
        return [_local_node(self._ctx, name) for name in self._ctx.locals]


def build_function_ir(ctx, cname, recursive):
    return FunctionIR(ctx, cname, recursive)


@dataclass(frozen=True)
class MixedCallIR:
    """Existing inferred kinds, not proofs; runtime guards still check every argument.

    Full-source identity covers callers and callees that influenced inference.
    No range, ownership, or purity facts are invented for the mixed frontend.
    """
    source_sha256: str
    name: str
    params: tuple
    ret: object
    is_bool_ret: bool

    def matches(self, source, name):
        import hashlib
        return self.name == name and self.source_sha256 == hashlib.sha256(source.encode('utf8')).hexdigest()

    def signature(self):
        def kind(node):
            return 'list[' + node.elem.kind + ']' if isinstance(node, Sequence) else node.kind
        return {'params': {name: kind(node) for name, node in self.params},
                'ret': kind(self.ret), 'is_bool_ret': self.is_bool_ret}


def mixed_call_ir(source, name, params, ret, is_bool_ret):
    import hashlib
    def node(kind):
        if kind in ('list[int]', 'list[float]', 'list[str]'):
            return Sequence(Scalar(kind[5:-1]))
        if kind in ('int', 'float', 'bool', 'str'):
            return Scalar(kind)
        raise ValueError('unsupported mixed kind')
    return MixedCallIR(hashlib.sha256(source.encode('utf8')).hexdigest(), name,
                       tuple((name, node(kind)) for name, kind in params.items()), node(ret), is_bool_ret)
