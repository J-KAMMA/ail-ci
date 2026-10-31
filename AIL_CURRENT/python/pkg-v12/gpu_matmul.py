# -*- coding: utf-8 -*-
"""gpu_matmul.py -- the GPU matrix multiply for 2-D `ail_array` arrays (docs/design/TYPED_ARRAY.md 5.7, GPU.md 6.7).

Two kernels per element type (f64, f32), both Vulkan compute written as SPIR-V by this file (no shader compiler):

* the DEFAULT kernel is exact: one invocation per output element runs the fixed order of TYPED_ARRAY.md 3.7 along `k` (blocks
  of 1024, sixteen lanes starting at -0.0, the 8-4-2-1 tree, the power-of-two tree over the blocks, +0.0 for K = 0, canonical
  NaN), with every product and every add a separate `NoContraction` instruction, so the result is bit for bit the one of
  `ail_array.matmul` (CPU).  f32 uses real binary32 instructions (a binary32 add or multiply is one correct rounding,
  which is what the reference computes: binary64 operation, one rounding to binary32).
* the FAST kernel is opt-in (`fast=True`): a 32 x 32 tile per workgroup in shared memory, 4 x 4 outputs per invocation, `k`
  summed in order from 0 with ONE accumulator and a driver that may fuse multiply and add.  It is NOT bit-identical to the
  default kernel or to the CPU and its bits may differ from device to device; use it when speed matters more than bits.

Around the kernels sits a C host function (`ail_gpu_matmul`) built on the Vulkan runtime of gpu_vk.py (loader opened with
dlopen at run time, one pipeline per kernel, the same buffer pool): it checks the inputs, runs the device, and falls back to a
CPU kernel with the same order whenever the device is missing, `AIL_GPU=0`/`emu`, untrusted, or the data would make a device
that flushes subnormals differ (the guard below).  What is checked about a device:

* the SELF-TEST (once per process and kernel): matmul-specific operand sets (a K = 1025 sum that only the lane order gets
  right, inf/NaN, -0.0 products, a pair a fused multiply-add gets wrong, random data over 6 blocks) run on the device and on the CPU
  kernel; a difference marks the device untrusted for that kernel and the CPU kernel runs;
* the first real launch compares its first 256 outputs with the CPU kernel;
* the subnormal GUARD: devices may flush subnormals (lavapipe does not preserve binary64 denormals).  Before a launch the host
  scans A and B once; when the smallest nonzero |a| times the smallest nonzero |b| could make a product or a difference of
  products fall below the smallest normal number, the CPU kernel runs instead.  That also fixes the exactness rule for what
  the kernel does not check itself: with the guard satisfied no intermediate is subnormal, so flushing never happens.

Switches: AIL_GPU=0 or emu (CPU kernel only), AIL_GPU_TRACE=1 (one line per call on stderr), AIL_GPU_DEVICE=<name>, and the rest
of gpu_vk.py.  Not built: int8/int32/int64 (the CPU reference has no integer matmul yet), f16, cooperative matrix.
"""
import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import gpu_spirv
import gpu_vk
from gpu_spirv import Module, inst, OP, CAP, DEC, SC, words_of_string, f64_words

OPX = dict(OP, UDiv=134, UMod=137, FConvert=115, ShiftLeftLogical=196, ControlBarrier=224, TypeArray=28,
           FUnordNotEqual=183, ConvertUToF=112, Select=169, INotEqual=171, UConvert=113)
DECX = dict(DEC, Block=2)
SCX = dict(SC, Workgroup=4)

TILE = 32               # fast kernel: outputs per workgroup edge
TK = 8                  # fast kernel: k per shared-memory step
LOCAL = 64              # invocations per workgroup, both kernels
MAX_STACK = 64          # block values kept by the exact kernel (blocks <= 2**63)
PARAMS = ('cnt', 'lo', 'width', 'm', 'k', 'n')         # u64 members of the parameter block (binding 0)
BIND_PARAMS, BIND_RESULT, BIND_A, BIND_B = 0, 2, 3, 4  # binding 1 (flags) is unused by these kernels


def _f32_words(value):
    import struct
    return [struct.unpack('<I', struct.pack('<f', value))[0]]


class _B:
    """A small structured SPIR-V builder for one compute shader."""

    def __init__(self, ty):
        self.ty = ty                       # 'f64' or 'f32': the type the arithmetic is done in
        self.m = Module()
        self.body, self.vars = [], []
        self.interface = []
        self.shared = []

    # -- types and constants
    def op(self, name, ty, *ops):
        r = self.m.new()
        self.body += inst(OPX[name], ty, r, *ops)
        return r

    def op0(self, name, *ops):
        self.body += inst(OPX[name], *ops)

    def label(self, i):
        self.body += inst(OPX['Label'], i)

    def branch(self, i):
        self.op0('Branch', i)

    @property
    def U32(self): return self.m.u32()
    @property
    def U64(self): return self.m.u64()
    @property
    def BOOL(self): return self.m.bool_()
    @property
    def D(self): return self.m.f64()                 # storage type (always binary64)
    @property
    def T(self): return self.m.f64() if self.ty == 'f64' else self.m.tdecl('TypeFloat', 32)

    def u(self, v): return self.m.c_u64(v)
    def u32c(self, v): return self.m.c_u32(v)

    def fT(self, v):
        if self.ty == 'f64':
            return self.m.c_f64(v)
        return self.m.cdecl('Constant', self.T, *_f32_words(v))

    def fD(self, v): return self.m.c_f64(v)

    def array_t(self, elem, length):
        key = ('TypeArray', elem, length)
        if key not in self.m.cache:
            ln = self.u32c(length)
            i = self.m.new()
            self.m.decl += inst(OPX['TypeArray'], i, elem, ln)
            self.m.cache[key] = i
        return self.m.cache[key]

    def newvar(self, ty, init=None):
        r = self.m.new()
        ops = [self.m.ptr('Function', ty), r, SC['Function']]
        if init is not None:
            ops.append(init)
        self.vars += inst(OPX['Variable'], *ops)
        return r

    def ld(self, ty, var): return self.op('Load', ty, var)
    def st(self, var, val): self.op0('Store', var, val)

    def nc(self, name, a, b):
        """An arithmetic instruction that may not be fused or reassociated."""
        r = self.op(name, self.T, a, b)
        self.m.decorate(r, 'NoContraction')
        return r

    def fadd(self, a, b, exact=True):
        r = self.op('FAdd', self.T, a, b)
        if exact:
            self.m.decorate(r, 'NoContraction')
        return r

    def fmul(self, a, b, exact=True):
        r = self.op('FMul', self.T, a, b)
        if exact:
            self.m.decorate(r, 'NoContraction')
        return r

    def to_T(self, d):
        return d if self.ty == 'f64' else self.op('FConvert', self.T, d)

    def to_D(self, t):
        return t if self.ty == 'f64' else self.op('FConvert', self.D, t)

    # -- control flow
    def if_(self, cond, then_fn):
        then, merge = self.m.new(), self.m.new()
        self.op0('SelectionMerge', merge, 0)
        self.op0('BranchConditional', cond, then, merge)
        self.label(then)
        then_fn()
        self.branch(merge)
        self.label(merge)

    def loop(self, cond_fn, body_fn):
        header, cond, body, cont, merge = (self.m.new() for _ in range(5))
        self.branch(header)
        self.label(header)
        self.op0('LoopMerge', merge, cont, 0)
        self.branch(cond)
        self.label(cond)
        c = cond_fn()
        self.op0('BranchConditional', c, body, merge)
        self.label(body)
        body_fn()
        self.branch(cont)
        self.label(cont)
        self.branch(header)
        self.label(merge)

    # -- buffers
    def gvar(self, struct_ty, binding):
        m = self.m
        v = m.new()
        m.decl += inst(OPX['Variable'], m.ptr('StorageBuffer', struct_ty), v, SC['StorageBuffer'])
        m.decorate(v, 'DescriptorSet', 0)
        m.decorate(v, 'Binding', binding)
        self.interface.append(v)
        return v

    def buffer_of_doubles(self, binding, readonly):
        m = self.m
        arr = m.tdecl('TypeRuntimeArray', self.D, share=False)
        m.decorate(arr, 'ArrayStride', 8)
        st = m.tdecl('TypeStruct', arr, share=False)
        m.decorate(st, 'Block')
        m.member_decorate(st, 0, 'Offset', 0)
        if readonly:
            m.member_decorate(st, 0, 'NonWritable')
        return self.gvar(st, binding)

    def params(self):
        m = self.m
        st = m.tdecl('TypeStruct', *[self.U64] * len(PARAMS), share=False)
        m.decorate(st, 'Block')
        for i in range(len(PARAMS)):
            m.member_decorate(st, i, 'Offset', 8 * i)
            m.member_decorate(st, i, 'NonWritable')
        self.pvar = self.gvar(st, BIND_PARAMS)

    def param(self, name):
        i = PARAMS.index(name)
        p = self.op('AccessChain', self.m.ptr('StorageBuffer', self.U64), self.pvar, self.u32c(i))
        return self.op('Load', self.U64, p)

    def elem(self, buf, index):
        return self.op('AccessChain', self.m.ptr('StorageBuffer', self.D), buf, self.u32c(0), index)

    def load_T(self, buf, index):
        return self.to_T(self.op('Load', self.D, self.elem(buf, index)))

    def finish(self, main, first, entry_name='main', exact=True, shared=False, builtins=()):
        m = self.m
        head = inst(OPX['Function'], m.void(), main, 0, m.tdecl('TypeFunction', m.void()))
        label_words = inst(OPX['Label'], first)
        rest = self.body[len(label_words):]
        func = head + label_words + self.vars + rest + inst(OPX['FunctionEnd'])
        caps = ['Shader', 'Int64', 'Float64']
        if exact:
            caps += ['RoundingModeRTE', 'SignedZeroInfNanPreserve']
        for cap in caps:
            m.caps += inst(OPX['Capability'], CAP[cap])
        mem = inst(OPX['MemoryModel'], 0, 1)
        entry = inst(OPX['EntryPoint'], 5, main, words_of_string(entry_name), self.interface)
        modes = inst(OPX['ExecutionMode'], main, 17, LOCAL, 1, 1)
        if exact:
            for width in ((64,) if self.ty == 'f64' else (64, 32)):
                modes += inst(OPX['ExecutionMode'], main, 4462, width)     # RoundingModeRTE
                modes += inst(OPX['ExecutionMode'], main, 4461, width)     # SignedZeroInfNanPreserve
        out = [0x07230203, 0x00010400, 0x0A1A0001, m.bound, 0]
        return out + m.caps + m.imports + mem + entry + modes + m.annot + m.decl + func


def _global_index(b, gid):
    """(idx, in_range) of a 1-D launch laid out on a 2-D grid, as gpu_spirv does: idx = y * width + x."""
    m = b.m
    v = b.op('Load', m.v3u32(), gid)
    x = b.op('UConvert', b.U64, b.op('CompositeExtract', b.U32, v, 0))
    y = b.op('UConvert', b.U64, b.op('CompositeExtract', b.U32, v, 1))
    width, cnt = b.param('width'), b.param('cnt')
    idx = b.op('IAdd', b.U64, b.op('IMul', b.U64, y, width), x)
    return idx, b.op('ULessThan', b.BOOL, idx, cnt)


def exact_words(ty):
    """The default kernel: one invocation per output element, the order of TYPED_ARRAY.md 3.7."""
    b = _B(ty)
    m = b.m
    b.params()
    resvar = b.buffer_of_doubles(BIND_RESULT, False)
    avar = b.buffer_of_doubles(BIND_A, True)
    bvar = b.buffer_of_doubles(BIND_B, True)
    gid = m.new()
    m.decl += inst(OPX['Variable'], m.ptr('Input', m.v3u32()), gid, SC['Input'])
    m.decorate(gid, 'BuiltIn', 28)
    b.interface.append(gid)
    main, first = m.new(), m.new()
    b.label(first)
    idx, inr = _global_index(b, gid)
    work, done = m.new(), m.new()
    b.op0('SelectionMerge', done, 0)
    b.op0('BranchConditional', inr, work, done)
    b.label(work)

    U64, T = b.U64, b.T
    K, N = b.param('k'), b.param('n')
    i = b.op('UDiv', U64, idx, N)
    j = b.op('ISub', U64, idx, b.op('IMul', U64, i, N))
    row = b.op('IMul', U64, i, K)
    nb = b.op('ShiftRightLogical', U64, b.op('IAdd', U64, K, b.u(1023)), b.u(10))
    negzero = b.fT(-0.0)
    lanes = [b.newvar(T, negzero) for _ in range(16)]
    stack = b.newvar(b.array_t(T, MAX_STACK))
    dvar = b.newvar(U64, b.u(0))
    bvar_ = b.newvar(U64, b.u(0))
    uvar = b.newvar(U64, b.u(0))
    mvar = b.newvar(U64, b.u(0))
    ptrT = m.ptr('Function', T)

    def term(t_off_k, lane):
        """lane = lane + a[i, k] * b[k, j] for k = t_off_k (a u64 value)"""
        a = b.load_T(avar, b.op('IAdd', U64, row, t_off_k))
        bb = b.load_T(bvar, b.op('IAdd', U64, b.op('IMul', U64, t_off_k, N), j))
        p = b.fmul(a, bb)
        b.st(lane, b.fadd(b.ld(T, lane), p))

    def block():
        bi = b.ld(U64, bvar_)
        base = b.op('ShiftLeftLogical', U64, bi, b.u(10))
        rem = b.op('ISub', U64, K, base)
        big = b.op('UGreaterThan', b.BOOL, rem, b.u(1024))
        blen = b.op('Select', U64, big, b.u(1024), rem)
        for l in lanes:
            b.st(l, negzero)
        full = b.op('BitwiseAnd', U64, blen, b.u(0xFFFFFFFFFFFFFFF0))
        b.st(uvar, b.u(0))

        def groups_cond():
            return b.op('ULessThan', b.BOOL, b.ld(U64, uvar), full)

        def groups_body():
            k0 = b.op('IAdd', U64, base, b.ld(U64, uvar))
            for t in range(16):
                term(b.op('IAdd', U64, k0, b.u(t)), lanes[t])
            b.st(uvar, b.op('IAdd', U64, b.ld(U64, uvar), b.u(16)))
        b.loop(groups_cond, groups_body)
        for t in range(16):                                    # the short tail: lanes it does not reach keep their -0.0
            pos = b.op('IAdd', U64, full, b.u(t))
            b.if_(b.op('ULessThan', b.BOOL, pos, blen),
                  lambda pos=pos, t=t: term(b.op('IAdd', U64, base, pos), lanes[t]))
        for w in (8, 4, 2, 1):                                 # the 8-4-2-1 tree
            for q in range(w):
                b.st(lanes[q], b.fadd(b.ld(T, lanes[q]), b.ld(T, lanes[q + w])))
        d = b.ld(U64, dvar)
        b.st(b.op('AccessChain', ptrT, stack, d), b.ld(T, lanes[0]))
        b.st(dvar, b.op('IAdd', U64, d, b.u(1)))
        b.st(mvar, bi)

        def merge_cond():
            return b.op('INotEqual', b.BOOL, b.op('BitwiseAnd', U64, b.ld(U64, mvar), b.u(1)), b.u(0))

        def merge_body():                                      # two equal perfect subtrees: left + right
            d2 = b.op('ISub', U64, b.ld(U64, dvar), b.u(1))
            b.st(dvar, d2)
            left_p = b.op('AccessChain', ptrT, stack, b.op('ISub', U64, d2, b.u(1)))
            right_p = b.op('AccessChain', ptrT, stack, d2)
            b.st(left_p, b.fadd(b.ld(T, left_p), b.ld(T, right_p)))
            b.st(mvar, b.op('ShiftRightLogical', U64, b.ld(U64, mvar), b.u(1)))
        b.loop(merge_cond, merge_body)
        b.st(bvar_, b.op('IAdd', U64, bi, b.u(1)))

    b.loop(lambda: b.op('ULessThan', b.BOOL, b.ld(U64, bvar_), nb), block)

    result = b.newvar(T, b.fT(0.0))                             # K = 0: +0.0
    d = b.ld(U64, dvar)

    def fold():
        q = b.newvar(U64)
        acc = b.newvar(T)
        top = b.op('ISub', U64, b.ld(U64, dvar), b.u(1))
        b.st(acc, b.ld(T, b.op('AccessChain', ptrT, stack, top)))
        b.st(q, top)

        def cond():
            return b.op('UGreaterThan', b.BOOL, b.ld(U64, q), b.u(0))

        def body():                                            # acc = stack[q - 1] + acc: the right-most subtrees first
            q2 = b.op('ISub', U64, b.ld(U64, q), b.u(1))
            b.st(q, q2)
            b.st(acc, b.fadd(b.ld(T, b.op('AccessChain', ptrT, stack, q2)), b.ld(T, acc)))
        b.loop(cond, body)
        b.st(result, b.ld(T, acc))
    b.if_(b.op('UGreaterThan', b.BOOL, d, b.u(0)), fold)

    r64 = b.to_D(b.ld(T, result))
    isnan = b.op('FUnordNotEqual', b.BOOL, r64, r64)
    r64 = b.op('Select', b.D, isnan, b.fD(float('nan')), r64)    # canonical NaN: 0x7ff8000000000000
    b.st(b.elem(resvar, idx), r64)
    b.branch(done)
    b.label(done)
    b.op0('Return')
    return b.finish(main, first, exact=True)


def fast_words(ty):
    """The opt-in kernel: 32 x 32 tile per workgroup, shared memory, 4 x 4 outputs per invocation, one accumulator over k."""
    b = _B(ty)
    m = b.m
    b.params()
    resvar = b.buffer_of_doubles(BIND_RESULT, False)
    avar = b.buffer_of_doubles(BIND_A, True)
    bvar = b.buffer_of_doubles(BIND_B, True)
    wg = m.new()
    m.decl += inst(OPX['Variable'], m.ptr('Input', m.v3u32()), wg, SC['Input'])
    m.decorate(wg, 'BuiltIn', 26)                                 # WorkgroupId
    lidv = m.new()
    m.decl += inst(OPX['Variable'], m.ptr('Input', m.u32()), lidv, SC['Input'])
    m.decorate(lidv, 'BuiltIn', 29)                               # LocalInvocationIndex
    b.interface += [wg, lidv]
    T, U64, BOOL = b.T, b.U64, b.BOOL
    as_t = b.array_t(T, TILE * TK)
    bs_t = b.array_t(T, TILE * TK)
    shared_a, shared_b = m.new(), m.new()
    for v, t in ((shared_a, as_t), (shared_b, bs_t)):
        m.decl += inst(OPX['Variable'], m.tdecl('TypePointer', SCX['Workgroup'], t), v, SCX['Workgroup'])
        b.interface.append(v)
    ptrW = m.tdecl('TypePointer', SCX['Workgroup'], T)
    ptrF = m.ptr('Function', T)
    main, first = m.new(), m.new()
    b.label(first)
    M_, K, N = b.param('m'), b.param('k'), b.param('n')
    w = b.op('Load', m.v3u32(), wg)
    tile_j = b.op('IMul', U64, b.op('UConvert', U64, b.op('CompositeExtract', b.U32, w, 0)), b.u(TILE))
    tile_i = b.op('IMul', U64, b.op('UConvert', U64, b.op('CompositeExtract', b.U32, w, 1)), b.u(TILE))
    lid = b.op('UConvert', U64, b.op('Load', b.U32, lidv))
    ty = b.op('ShiftRightLogical', U64, lid, b.u(3))
    tx = b.op('BitwiseAnd', U64, lid, b.u(7))
    zero = b.fT(0.0)
    acc = [[b.newvar(T, zero) for _ in range(4)] for _ in range(4)]
    kt = b.newvar(U64, b.u(0))
    nkt = b.op('ShiftRightLogical', U64, b.op('IAdd', U64, K, b.u(TK - 1)), b.u(3))
    barrier_scope, barrier_sem = b.u32c(2), b.u32c(264)           # Workgroup scope; AcquireRelease | WorkgroupMemory

    def barrier():
        b.op0('ControlBarrier', barrier_scope, barrier_scope, barrier_sem)

    def tile_load(shared, buf, rows_per, edge_shift, gbase_row, gbase_col, nrows, ncols_stride, row_is_k):
        """Fill one shared tile: element e = lid + 64 q, tile row e >> edge_shift, column e & (2**edge_shift - 1)."""
        for q in range(TILE * TK // LOCAL):
            e = b.op('IAdd', U64, lid, b.u(LOCAL * q))
            r = b.op('ShiftRightLogical', U64, e, b.u(edge_shift))
            c = b.op('BitwiseAnd', U64, e, b.u((1 << edge_shift) - 1))
            if row_is_k:        # B tile: row = k, column = j
                gk = b.op('IAdd', U64, gbase_row, r)
                gj = b.op('IAdd', U64, gbase_col, c)
                ok = b.op('LogicalAnd', BOOL, b.op('ULessThan', BOOL, gk, K), b.op('ULessThan', BOOL, gj, N))
                src = b.op('IAdd', U64, b.op('IMul', U64, gk, N), gj)
            else:               # A tile: row = i, column = k
                gi = b.op('IAdd', U64, gbase_row, r)
                gk = b.op('IAdd', U64, gbase_col, c)
                ok = b.op('LogicalAnd', BOOL, b.op('ULessThan', BOOL, gi, M_), b.op('ULessThan', BOOL, gk, K))
                src = b.op('IAdd', U64, b.op('IMul', U64, gi, K), gk)
            src = b.op('Select', U64, ok, src, b.u(0))
            val = b.op('Select', T, ok, b.load_T(buf, src), zero)
            b.st(b.op('AccessChain', ptrW, shared, e), val)       # shared tiles are stored in e order (row-major)

    def ktile():
        k0 = b.op('ShiftLeftLogical', U64, b.ld(U64, kt), b.u(3))
        tile_load(shared_a, avar, TILE, 3, tile_i, k0, M_, K, False)    # 32 rows of 8
        tile_load(shared_b, bvar, TK, 5, k0, tile_j, K, N, True)        # 8 rows of 32
        barrier()
        for kk in range(TK):
            av = []
            for r in range(4):
                row = b.op('IAdd', U64, b.op('IMul', U64, ty, b.u(4 * TK)), b.u(r * TK + kk))
                av.append(b.ld(T, b.op('AccessChain', ptrW, shared_a, row)))
            for c in range(4):
                col = b.op('IAdd', U64, b.u(kk * TILE + 8 * c), tx)
                bv = b.ld(T, b.op('AccessChain', ptrW, shared_b, col))
                for r in range(4):
                    b.st(acc[r][c], b.fadd(b.ld(T, acc[r][c]), b.fmul(av[r], bv, exact=False), exact=False))
        barrier()
        b.st(kt, b.op('IAdd', U64, b.ld(U64, kt), b.u(1)))
    b.loop(lambda: b.op('ULessThan', BOOL, b.ld(U64, kt), nkt), ktile)

    for r in range(4):
        gi = b.op('IAdd', U64, tile_i, b.op('IAdd', U64, b.op('IMul', U64, ty, b.u(4)), b.u(r)))
        for c in range(4):
            gj = b.op('IAdd', U64, tile_j, b.op('IAdd', U64, tx, b.u(8 * c)))
            ok = b.op('LogicalAnd', BOOL, b.op('ULessThan', BOOL, gi, M_), b.op('ULessThan', BOOL, gj, N))
            val = b.to_D(b.ld(T, acc[r][c]))
            b.if_(ok, lambda gi=gi, gj=gj, val=val: b.st(b.elem(resvar, b.op('IAdd', U64, b.op('IMul', U64, gi, N), gj)), val))
    b.op0('Return')
    return b.finish(main, first, exact=False)


def kernels():
    """name -> SPIR-V words of the four kernels."""
    return {'exact_f64': exact_words('f64'), 'exact_f32': exact_words('f32'),
            'fast_f64': fast_words('f64'), 'fast_f32': fast_words('f32')}


# ---------------------------------------------------------------------------------------------------------------------
# the C host function
# ---------------------------------------------------------------------------------------------------------------------
C_HEAD = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static inline int gk_tracing(void) { static int v = -1; if (v < 0) { const char *e = getenv("AIL_GPU_TRACE"); v = e && e[0] && !(e[0] == '0' && e[1] == 0); } return v; }
'''

C_BODY = r'''
/* ---- GPU matmul (gpu_matmul.py): the CPU kernel in the order of TYPED_ARRAY.md 3.7, the guard, the self-test, the launch ---- */
#define GMM_NAN64 0x7ff8000000000000ull
static double gmm_nan64(void) { uint64_t u = GMM_NAN64; double d; memcpy(&d, &u, 8); return d; }
static float gmm_nan32(void) { uint32_t u = 0x7fc00000u; float f; memcpy(&f, &u, 4); return f; }

/* one output element: a = row of A (K), bt = column of B stored as a row (K) */
#define GMM_ELEM(NAME, T, NANF) \
static T NAME(const T *a, const T *bt, int64_t K) { \
    T st[64]; int d = 0; int64_t nb = (K + 1023) >> 10; \
    for (int64_t b = 0; b < nb; b++) { \
        int64_t base = b << 10, L = K - base < 1024 ? K - base : 1024; \
        T l[16]; for (int t = 0; t < 16; t++) l[t] = (T)-0.0; \
        int64_t u = 0; \
        for (; u + 16 <= L; u += 16) for (int t = 0; t < 16; t++) { T p = a[base + u + t] * bt[base + u + t]; l[t] = l[t] + p; } \
        for (int t = 0; u + t < L; t++) { T p = a[base + u + t] * bt[base + u + t]; l[t] = l[t] + p; } \
        for (int w = 8; w >= 1; w >>= 1) for (int q = 0; q < w; q++) l[q] = l[q] + l[q + w]; \
        st[d++] = l[0]; \
        for (int64_t mm = b; mm & 1; mm >>= 1) { d--; st[d - 1] = st[d - 1] + st[d]; } \
    } \
    if (d == 0) return (T)0.0; \
    T acc = st[d - 1]; \
    for (int q = d - 2; q >= 0; q--) acc = st[q] + acc; \
    return acc != acc ? NANF() : acc; \
}
GMM_ELEM(gmm_elem64, double, gmm_nan64)
GMM_ELEM(gmm_elem32, float, gmm_nan32)

/* the whole product on the CPU (B is copied transposed once) */
static int gmm_cpu(int dt, const void *A, const void *B, void *C, int64_t M, int64_t K, int64_t N) {
    if (M <= 0 || N <= 0) return 1;
    size_t w = dt ? 4 : 8;
    if (K <= 0) { memset(C, 0, (size_t)M * (size_t)N * w); return 1; }
    char *bt = (char *)malloc((size_t)K * (size_t)N * w);
    if (!bt) return 0;
    for (int64_t k = 0; k < K; k++) for (int64_t j = 0; j < N; j++)
        memcpy(bt + ((size_t)j * (size_t)K + (size_t)k) * w, (const char *)B + ((size_t)k * (size_t)N + (size_t)j) * w, w);
    for (int64_t i = 0; i < M; i++) for (int64_t j = 0; j < N; j++) {
        if (dt) ((float *)C)[i * N + j] = gmm_elem32((const float *)A + i * K, (const float *)bt + j * K, K);
        else ((double *)C)[i * N + j] = gmm_elem64((const double *)A + i * K, (const double *)bt + j * K, K);
    }
    free(bt);
    return 1;
}

static const char *gmm_why = "";
static const char *gmm_dev = "cpu";
static int gmm_state[2][2];              /* [dt][fast]: 0 untested, 1 trusted, -1 not used */
static int gmm_first[2][2];

/* the subnormal guard: 1 when no product or difference of products can be subnormal (then a device that flushes
   subnormals cannot differ).  Scans the inputs once. */
static int gmm_guard(int dt, const double *A, int64_t na, const double *B, int64_t nb) {
    int ea = 100000, eb = 100000, e;
    for (int64_t i = 0; i < na; i++) { double x = A[i]; if (x != 0.0 && isfinite(x)) { frexp(x, &e); if (e < ea) ea = e; } }
    for (int64_t i = 0; i < nb; i++) { double x = B[i]; if (x != 0.0 && isfinite(x)) { frexp(x, &e); if (e < eb) eb = e; } }
    if (ea == 100000 || eb == 100000) return 1;        /* only zeros, infinities, NaNs: no finite nonzero product */
    return ea + eb >= (dt ? -100 : -900);
}

/* one launch of kernel `which` (0 exact f64, 1 exact f32, 2 fast f64, 3 fast f32) on doubles; 1 when the device produced C */
static int gmm_launch(int which, const double *A, const double *B, double *C, int64_t M, int64_t K, int64_t N) {
    static const uint32_t *spv[4] = { gmm_spv_exact_f64, gmm_spv_exact_f32, gmm_spv_fast_f64, gmm_spv_fast_f32 };
    static const uint32_t nw[4] = { GMM_NW_EXACT_F64, GMM_NW_EXACT_F32, GMM_NW_FAST_F64, GMM_NW_FAST_F32 };
    int fast = which >= 2, dt = which & 1;
    int need = (!fast && dt) ? 3 : 1;
    uint64_t prm[6]; memset(prm, 0, sizeof prm);
    prm[0] = (uint64_t)(M * N); prm[3] = (uint64_t)M; prm[4] = (uint64_t)K; prm[5] = (uint64_t)N;
    const void *lp[2] = { A, B }; int64_t ln[2] = { M * K, K * N };
    unsigned fl = 0;
    uint64_t gx, gy;
    if (fast) { gx = (uint64_t)((N + 31) / 32); gy = (uint64_t)((M + 31) / 32); }
    else {
        uint64_t groups = ((uint64_t)(M * N) + 63) / 64;
        gx = groups < 65535 ? groups : 65535; gy = (groups + gx - 1) / gx;
        prm[2] = gx * 64;
    }
    return gkv_launch_ex(spv[which], nw[which], need, 2, 6, prm, lp, ln, C, M * N, gx, gy, &fl, 0);
}

/* matmul-specific operand sets (TYPED_ARRAY.md 5.7), device against the CPU kernel, bit for bit */
static uint64_t gmm_rng = 0x9E3779B97F4A7C15ull;
static double gmm_rand(void) { gmm_rng = gmm_rng * 6364136223846793005ull + 1442695040888963407ull; uint64_t r = gmm_rng >> 11; return (double)r / 9007199254740992.0; }
static int gmm_selftest_set(int which, const double *A, const double *B, int64_t M, int64_t K, int64_t N, const char **what) {
    int dt = which & 1;
    double *dv = (double *)malloc((size_t)(M * N) * 8);
    double *cv = (double *)malloc((size_t)(M * N) * 8);
    void *Af = malloc((size_t)(M * K) * 8), *Bf = malloc((size_t)(K * N) * 8), *Cf = malloc((size_t)(M * N) * 8);
    int r = 0;
    if (!dv || !cv || !Af || !Bf || !Cf) goto out;
    if (dt) {
        for (int64_t i = 0; i < M * K; i++) ((float *)Af)[i] = (float)A[i];
        for (int64_t i = 0; i < K * N; i++) ((float *)Bf)[i] = (float)B[i];
    } else { memcpy(Af, A, (size_t)(M * K) * 8); memcpy(Bf, B, (size_t)(K * N) * 8); }
    gmm_cpu(dt, Af, Bf, Cf, M, K, N);
    for (int64_t i = 0; i < M * N; i++) cv[i] = dt ? (double)((float *)Cf)[i] : ((double *)Cf)[i];
    if (!gmm_launch(which, A, B, dv, M, K, N)) { r = 0; goto out; }
    for (int64_t i = 0; i < M * N; i++) {
        int bad;
        if (dt) { float x = (float)dv[i], y = (float)cv[i]; bad = memcmp(&x, &y, 4) != 0; }
        else bad = memcmp(&dv[i], &cv[i], 8) != 0;
        if (bad) { *what = "result bits differ"; r = -1; goto out; }
    }
    r = 1;
out:
    free(dv); free(cv); free(Af); free(Bf); free(Cf);
    return r;
}
static int gmm_selftest(int which) {
    int dt = which & 1;
    const char *what = "";
    int sets_ok = 1;
    struct { int64_t M, K, N; } shapes[6] = { {3, 1025, 5}, {2, 37, 3}, {2, 17, 2}, {1, 17, 2}, {2, 5 * 1024 + 13, 3}, {7, 2100, 9} };
    for (int s = 0; s < 6 && sets_ok > 0; s++) {
        int64_t M = shapes[s].M, K = shapes[s].K, N = shapes[s].N;
        double *A = (double *)calloc((size_t)(M * K), 8), *B = (double *)calloc((size_t)(K * N), 8);
        if (!A || !B) { free(A); free(B); return 0; }
        double big = dt ? 1e8 : 1e16, e = dt ? 0x1p-13 : 0x1p-27, e0 = dt ? 0x1p-12 : 0x1p-26;
        for (int64_t i = 0; i < M; i++) for (int64_t k = 0; k < K; k++) {
            double a;
            if (s == 0) a = (k % 3 == 0) ? big : (k % 3 == 1) ? 1.0 : -big;
            else if (s == 1) { a = 1.0; if (i == 0 && k == 3) a = INFINITY; if (i == 1 && k == 5) a = INFINITY; if (i == 1 && k == 21) a = -INFINITY; if (i == 1 && k == 7) a = NAN; }
            else if (s == 2) a = 0.0;
            else if (s == 3) { a = 1.0; if (k == 0) a = 1.0 + e0; if (k == 16) a = 1.0 + e; }   /* fused (a*b)+c differs from rounding the product first */
            else a = (gmm_rand() - 0.5) * (double)(1 << (int)(gmm_rand() * 12));
            A[i * K + k] = dt ? (double)(float)a : a;
        }
        for (int64_t k = 0; k < K; k++) for (int64_t j = 0; j < N; j++) {
            double b;
            if (s == 0) b = (j & 1) ? (double)(j + 1) * 0.5 : 1.0;
            else if (s == 1) b = (k == 3) ? 0.0 : 1.0;
            else if (s == 2) b = -1.0;
            else if (s == 3) { b = 1.0; if (k == 0) b = -1.0; if (k == 16) b = 1.0 + e; }
            else b = (gmm_rand() - 0.5) * (double)(1 << (int)(gmm_rand() * 12));
            B[k * N + j] = dt ? (double)(float)b : b;
        }
        sets_ok = gmm_selftest_set(which, A, B, M, K, N, &what);
        free(A); free(B);
        if (sets_ok < 0 && gk_tracing()) fprintf(stderr, "gpu: matmul selftest set %d (M=%lld K=%lld N=%lld): %s\n", s, (long long)M, (long long)K, (long long)N, what);
    }
    return sets_ok;
}

/* the entry point.  dt: 0 f64, 1 f32.  fast: 0 the exact kernel (bit-identical to the CPU), 1 the opt-in tiled kernel.
   Returns 1 when the device computed C, 0 when the CPU kernel did (C is complete either way). */
int ail_gpu_matmul(int dt, int fast, const void *A, const void *B, void *C, long long M, long long K, long long N) {
    gmm_dev = "cpu"; gmm_why = "";
    if (M <= 0 || N <= 0 || K <= 0) { gmm_cpu(dt, A, B, C, M, K, N); gmm_why = "an empty dimension"; return 0; }
    const char *g = getenv("AIL_GPU");
    if (g && (!strcmp(g, "0") || !strcmp(g, "emu"))) { gmm_cpu(dt, A, B, C, M, K, N); gmm_why = "AIL_GPU switches the device off"; goto traced; }
    {
        int which = (fast ? 2 : 0) + (dt ? 1 : 0);
        int need = (!fast && dt) ? 3 : 1;
        unsigned cls = GKV_T_F64;
        (void)need;
        double *Ad = (double *)A, *Bd = (double *)B, *Cd = 0;
        int conv = dt;
        if (conv) {
            Ad = (double *)malloc((size_t)(M * K) * 8); Bd = (double *)malloc((size_t)(K * N) * 8);
            if (!Ad || !Bd) { free(Ad); free(Bd); gmm_cpu(dt, A, B, C, M, K, N); gmm_why = "out of memory"; goto traced; }
            for (long long i = 0; i < M * K; i++) Ad[i] = (double)((const float *)A)[i];
            for (long long i = 0; i < K * N; i++) Bd[i] = (double)((const float *)B)[i];
        }
        Cd = dt ? (double *)malloc((size_t)(M * N) * 8) : (double *)C;
        int used = 0;
        if (!Cd) { gmm_why = "out of memory"; }
        else if (!gkv_usable(cls)) { gmm_why = gkv_G.why; }
        else if (!fast && !gmm_guard(dt, Ad, M * K, Bd, K * N)) { gmm_why = "subnormal guard: operands too small for a device that may flush subnormals"; }
        else {
            if (gkv_check_mode() == 0 && gmm_state[dt][fast] == 0) gmm_state[dt][fast] = 1;
            if (gmm_state[dt][fast] == 0) {
                int st = fast ? 1 : gmm_selftest(which);
                gmm_state[dt][fast] = st > 0 ? 1 : -1;
                if (gk_tracing()) fprintf(stderr, "gpu: matmul %s %s selftest %s (device %s)\n", dt ? "f32" : "f64", fast ? "fast" : "exact",
                                          st > 0 ? "ok" : st < 0 ? "FAILED" : "could not run", gkv_dev_name());
                if (st < 0) gkv_distrust(cls, 100 + which, "matmul self-test: result bits differ", 0);
                else if (st == 0) gmm_why = gkv_G.why;
            }
            if (gmm_state[dt][fast] > 0) {
                if (gmm_launch(which, Ad, Bd, Cd, M, K, N)) {
                    used = 1;
                    int chk = gkv_check_mode();
                    if (!fast && chk && (chk > 1 || !gmm_first[dt][fast])) {          /* first real launch: the first outputs against the CPU kernel */
                        gmm_first[dt][fast] = 1;
                        int64_t cnt = M * N < 256 ? M * N : 256;
                        for (int64_t e = 0; e < cnt && used; e++) {
                            int64_t i = e / N, j = e % N;
                            double ref;
                            double *ra = (double *)malloc((size_t)K * 8), *rb = (double *)malloc((size_t)K * 8);
                            float *fa = (float *)malloc((size_t)K * 4), *fb = (float *)malloc((size_t)K * 4);
                            if (ra && rb && fa && fb) {
                                for (int64_t k = 0; k < K; k++) {
                                    ra[k] = Ad[i * K + k]; rb[k] = Bd[k * N + j];
                                    fa[k] = (float)ra[k]; fb[k] = (float)rb[k];
                                }
                                ref = dt ? (double)gmm_elem32(fa, fb, K) : gmm_elem64(ra, rb, K);
                                uint64_t x, y; double got = Cd[e]; memcpy(&x, &got, 8); memcpy(&y, &ref, 8);
                                if (x != y) {
                                    used = 0; gmm_state[dt][fast] = -1;
                                    gkv_distrust(cls, 100 + which, "matmul first launch: result bits differ", (long long)e);
                                    gmm_why = gkv_G.distrust;
                                }
                            }
                            free(ra); free(rb); free(fa); free(fb);
                        }
                    }
                } else gmm_why = gkv_G.why;
            } else if (!gmm_why[0]) gmm_why = gkv_G.distrust[0] ? gkv_G.distrust : "device not trusted for this kernel";
        }
        if (used) {
            if (dt) for (long long i = 0; i < M * N; i++) ((float *)C)[i] = (float)Cd[i];
            gmm_dev = gkv_dev_name();
        } else gmm_cpu(dt, A, B, C, M, K, N);
        if (conv) { free(Ad); free(Bd); }
        if (dt) free(Cd);
        if (gk_tracing()) fprintf(stderr, "gpu: matmul %s %s M=%lld K=%lld N=%lld device=%s%s%s\n", dt ? "f32" : "f64", fast ? "fast" : "exact", M, K, N, gmm_dev,
                                  used ? "" : " cpu: ", used ? "" : gmm_why);
        return used;
    }
traced:
    if (gk_tracing()) fprintf(stderr, "gpu: matmul %s %s M=%lld K=%lld N=%lld device=cpu (%s)\n", dt ? "f32" : "f64", fast ? "fast" : "exact", M, K, N, gmm_why);
    return 0;
}
/* the CPU kernel alone (for tests and benchmarks) */
int ail_gpu_matmul_cpu(int dt, const void *A, const void *B, void *C, long long M, long long K, long long N) { return gmm_cpu(dt, A, B, C, M, K, N); }
const char *ail_gpu_matmul_device(void) { return gmm_dev; }
const char *ail_gpu_matmul_why(void) { return gmm_why; }
'''


def c_source():
    """The whole C file: runtime, the four SPIR-V arrays, the host function."""
    ks = kernels()
    parts = [C_HEAD, gpu_vk.runtime_text()]
    for name, words in ks.items():
        parts.append('static const uint32_t gmm_spv_%s[%d] = {\n%s\n};' % (name, len(words), gpu_vk._words_c(words)))
        parts.append('#define GMM_NW_%s %d' % (name.upper(), len(words)))
    parts.append(C_BODY)
    return '\n'.join(parts)


# ---------------------------------------------------------------------------------------------------------------------
# Python API
# ---------------------------------------------------------------------------------------------------------------------
_LIB = None


def build_library(cc=None, out_dir=None):
    """Compile the C source to a shared library (cached by hash of the source) and return its path."""
    cc = cc or os.environ.get('CC') or shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
    if not cc:
        raise RuntimeError('gpu_matmul: no C compiler (cc, gcc or clang) found')
    src = c_source()
    tag = hashlib.sha256(src.encode('utf-8')).hexdigest()[:16]
    out_dir = Path(out_dir or os.path.join(tempfile.gettempdir(), 'ail-gpu-matmul-%d' % os.getuid() if hasattr(os, 'getuid') else 'ail-gpu-matmul'))
    out_dir.mkdir(parents=True, exist_ok=True)
    lib = out_dir / ('gpu_matmul_%s.so' % tag)
    if not lib.is_file():
        c = out_dir / ('gpu_matmul_%s.c' % tag)
        c.write_text(src, encoding='utf-8')
        tmp = out_dir / ('gpu_matmul_%s.%d.tmp' % (tag, os.getpid()))
        r = subprocess.run([cc, '-O2', '-std=gnu11', '-ffp-contract=off', '-fPIC', '-shared', '-w', str(c), '-o', str(tmp), '-ldl', '-lm'],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError('gpu_matmul: the C build failed:\n' + r.stderr[:3000])
        os.replace(tmp, lib)
    return lib


def _library():
    global _LIB
    if _LIB is None:
        lib = ctypes.CDLL(str(build_library()))
        lib.ail_gpu_matmul.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_longlong, ctypes.c_longlong, ctypes.c_longlong]
        lib.ail_gpu_matmul.restype = ctypes.c_int
        lib.ail_gpu_matmul_cpu.argtypes = lib.ail_gpu_matmul.argtypes[:1] + lib.ail_gpu_matmul.argtypes[2:]
        lib.ail_gpu_matmul_cpu.restype = ctypes.c_int
        lib.ail_gpu_matmul_device.restype = ctypes.c_char_p
        lib.ail_gpu_matmul_why.restype = ctypes.c_char_p
        _LIB = lib
    return _LIB


def _check(ta, a, b):
    """The checks of `ail_array.matmul`, in its order and with its texts; returns (dtype, m, k, n).  f32 is allowed here (the CPU
    reference of this version builds f64 only); every other dtype raises the CPU path's own error by calling it."""
    if not isinstance(a, ta.Array) or not isinstance(b, ta.Array):
        raise TypeError('ail_array.matmul() needs two ail_array.Array values')
    if a._sh is None or b._sh is None:
        raise ValueError('ail_array.matmul(): needs two 2-D arrays, not shapes %s and %s' % (a.shape, b.shape))
    if a._dt is not b._dt:
        raise TypeError('ail_array: %s matmul %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)'
                        % (a._dt, b._dt, b._dt, a._dt))
    if a._dt is not ta.f64 and a._dt is not ta.f32:
        raise TypeError('ail_array.matmul(): only f64 arrays are built in this version, not %s' % a._dt)
    m, k = a._sh
    k2, n = b._sh
    if k != k2:
        raise ValueError('ail_array: matmul: shapes %s and %s do not match: %d != %d' % (a._sh, b._sh, k, k2))
    return a._dt, m, k, n


def matmul(a, b, fast=False):
    """`ail_array.matmul(a, b)` on the GPU.  With `fast=False` (the default) the result is bit for bit the one of the CPU kernel (the
    order of TYPED_ARRAY.md 3.7) on every device, and on no device (the CPU kernel runs).  With `fast=True` the opt-in tiled kernel
    runs: its bits may differ from the default kernel's and from device to device.  Returns the product as a new 2-D Array."""
    import ail_array as ta
    dt, m, k, n = _check(ta, a, b)
    lib = _library()
    isf32 = dt is ta.f32
    size = m * n * dt.itemsize
    out = bytearray(max(size, 1))
    ab, bb = bytes(a._buf), bytes(b._buf)
    c_out = (ctypes.c_char * len(out)).from_buffer(out)
    lib.ail_gpu_matmul(1 if isf32 else 0, 1 if fast else 0, ab, bb, ctypes.addressof(c_out), m, k, n)
    return ta.Array._make(dt, bytearray(out[:size]), (m, n))


def last_device():
    """What ran the last call: the Vulkan device's name, or 'cpu'."""
    return _library().ail_gpu_matmul_device().decode()


def last_reason():
    """Why the last call ran on the CPU ('' when it ran on the device)."""
    return _library().ail_gpu_matmul_why().decode()


def cpu_matmul(a, b):
    """The C CPU kernel of the same order (a fast exact reference for tests and benchmarks; equals `ail_array.matmul` for f64)."""
    import ail_array as ta
    dt, m, k, n = _check(ta, a, b)
    lib = _library()
    size = m * n * dt.itemsize
    out = bytearray(max(size, 1))
    c_out = (ctypes.c_char * len(out)).from_buffer(out)
    lib.ail_gpu_matmul_cpu(1 if dt is ta.f32 else 0, bytes(a._buf), bytes(b._buf), ctypes.addressof(c_out), m, k, n)
    return ta.Array._make(dt, bytearray(out[:size]), (m, n))


def reference_matmul(a, b):
    """The oracle in pure Python for any supported dtype: `C[i, j] = ta.dot(A[i], B[:, j])` (public API only)."""
    import ail_array as ta
    dt, m, k, n = _check(ta, a, b)
    bt = b.T
    rows = [a[i] for i in range(m)]
    cols = [bt[j] for j in range(n)]
    vals = [ta.dot(r, c) for r in rows for c in cols]
    return ta.Array._of(dt, vals, (m, n))


if __name__ == '__main__':
    sys.stdout.write(c_source())
