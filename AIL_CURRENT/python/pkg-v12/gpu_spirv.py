# -*- coding: utf-8 -*-
"""gpu_spirv.py -- stage G2 of docs/design/GPU.md: the kernel IR of gpu.py as a SPIR-V compute shader.

A minimal SPIR-V writer (no shaderc, no glslang, no spirv-tools at user build time) and the lowering of one `gpu.Kernel`
to a module.  The module is the device twin of the C emulation `ail_gk<k>` that gpu.emit_c writes: same inputs, same flag
bits (index 1, zero division 2, int64 overflow 4, denormal 8, NaN 16, range 32), same result.  The glue discards the
result and runs the original CPU loop whenever the flag word is not 0 (CPU replay, GPU.md 3.1), so the device may flag
MORE than the emulation does (a spurious flag costs a replay) but never LESS: a value it hands back with flag 0 must be
bit for bit what the CPU loop computes.  That is what every rule below is for.

Exactness rules (GPU.md 3.2, 3.3):

* no float op is ever fused or reordered: every FAdd/FSub/FMul/FNegate carries `NoContraction`; the module carries no
  `FPFastMathMode` decoration at all (no NotNaN/NotInf/NSZ/AllowRecip/Fast), and the entry point has the execution modes
  `SignedZeroInfNanPreserve 64` (a compiler may not assume there is no NaN, no inf, and that -0.0 == 0.0 as a value) and
  `RoundingModeRTE 64`, which also fixes the rounding of `OpConvertSToF` (the `FPRoundingMode` decoration is only
  allowed on 16-bit conversions).  A device that does not report
  `shaderSignedZeroInfNanPreserveFloat64` and `shaderRoundingModeRTEFloat64` does not get a float kernel (gpk_vk runtime).
* subnormals: the device may or may not flush them (`shaderDenormPreserveFloat64` is 0 on lavapipe), so the kernel never
  lets one matter.  An operand or result with 0 < |x| < 2**-1000 sets the flag; a product whose operand exponents sum
  below -1000 sets the flag; a sum or difference that comes out as 0 although the operands are not each other's negation
  sets the flag (that is a flushed subnormal; the CPU emulation flags the tiny result itself).
* NaN: a NaN made from numbers (inf - inf, inf * 0) or read from an input sets the flag, so the replay produces the
  CPU's NaN, and nothing about NaN payload or sign is ever visible from the device.
* comparisons are ordered (`OpFOrd*`), `!=` is unordered; min/max are Python's compare-and-select, never FMin/FMax.
* int64: `+ - *` and `-x`, `abs` check overflow (xor sign tests; the product by division) and flag; `//` and `%` take the
  divisor's sign as Python does, divide by a safe divisor (never 0 or -1: both are UB in SPIR-V or flagged) and flag
  zero division and INT64_MIN // -1.
* every list read is bounds checked after Python's negative-index rule; a miss flags and reads element 0 of the buffer
  (every buffer holds at least one element) instead.

No kernel the emulation can run is refused here except by `Unsupported` (an IR node this writer does not know), in which
case the build keeps the emulation only and says so in a note.
"""
import struct

INT64_MIN, INT64_MAX = -(1 << 63), (1 << 63) - 1

GK_INDEX, GK_ZERODIV, GK_OVERFLOW, GK_DENORM, GK_NAN, GK_RANGE = 1, 2, 4, 8, 16, 32
LOCAL_SIZE = 64                 # invocations per workgroup (x); the grid is 2-D when the count needs it
TINY_EXP = -1000                # GPU.md 3.2: |x| < 2**-1000 (nonzero) is a denormal-guard hit
MAX_STORAGE_BINDINGS = 3        # params, flags, result come before the lists


class Unsupported(Exception):
    """The kernel uses an IR node or type this writer does not lower; the build keeps the CPU emulation only."""


# ---------------------------------------------------------------------------------------------------------------------
# SPIR-V numbers (SPIR-V 1.4 unified specification)
# ---------------------------------------------------------------------------------------------------------------------
OP = dict(
    ExtInstImport=11, ExtInst=12, MemoryModel=14, EntryPoint=15, ExecutionMode=16, Capability=17,
    TypeVoid=19, TypeBool=20, TypeInt=21, TypeFloat=22, TypeVector=23, TypeRuntimeArray=29, TypeStruct=30,
    TypePointer=32, TypeFunction=33, ConstantTrue=41, ConstantFalse=42, Constant=43, Function=54, FunctionEnd=56,
    Variable=59, Load=61, Store=62, AccessChain=65, Decorate=71, MemberDecorate=72, CompositeExtract=81,
    ConvertFToS=110, ConvertSToF=111, UConvert=113, Bitcast=124, SNegate=126, FNegate=127, IAdd=128, FAdd=129,
    ISub=130, FSub=131, IMul=132, FMul=133, SDiv=135, SRem=138, IsNan=156, IsInf=157, LogicalNotEqual=165, LogicalOr=166, LogicalAnd=167,
    LogicalNot=168, Select=169, IEqual=170, INotEqual=171, UGreaterThan=172, SGreaterThan=173, UGreaterThanEqual=174,
    SGreaterThanEqual=175, ULessThan=176, SLessThan=177, ULessThanEqual=178, SLessThanEqual=179, FOrdEqual=180,
    FUnordEqual=181, FOrdNotEqual=182, FUnordNotEqual=183, FOrdLessThan=184, FOrdGreaterThan=186,
    FOrdLessThanEqual=188, FOrdGreaterThanEqual=190, ShiftRightLogical=194, BitwiseOr=197, BitwiseXor=198,
    BitwiseAnd=199, AtomicOr=241, Phi=245, LoopMerge=246, SelectionMerge=247, Label=248, Branch=249,
    BranchConditional=250, Return=253,
)
CAP = dict(Shader=1, Float64=10, Int64=11, RoundingModeRTE=4467, SignedZeroInfNanPreserve=4466)
DEC = dict(Block=2, ArrayStride=6, BuiltIn=11, NoContraction=42, FPRoundingMode=39, NonWritable=24, Binding=33,
           DescriptorSet=34, Offset=35)
SC = dict(Input=1, Function=7, StorageBuffer=12)
GLSL_FLOOR, GLSL_CEIL, GLSL_FABS = 8, 9, 4


def words_of_string(text):
    raw = text.encode('utf-8') + b'\0'
    raw += b'\0' * (-len(raw) % 4)
    return list(struct.unpack('<%dI' % (len(raw) // 4), raw))


def inst(opcode, *operands):
    ops = []
    for o in operands:
        if isinstance(o, (list, tuple)):
            ops.extend(o)
        else:
            ops.append(o)
    return [((len(ops) + 1) << 16) | opcode] + ops


def f64_words(value):
    lo, hi = struct.unpack('<II', struct.pack('<d', value))
    return [lo, hi]


def i64_words(value):
    value &= (1 << 64) - 1
    return [value & 0xFFFFFFFF, value >> 32]


# ---------------------------------------------------------------------------------------------------------------------
# module builder
# ---------------------------------------------------------------------------------------------------------------------
class Module:
    def __init__(self):
        self.bound = 1
        self.cache = {}
        self.caps, self.imports, self.entry, self.modes = [], [], [], []
        self.annot, self.decl, self.funcs = [], [], []

    def new(self):
        i = self.bound
        self.bound += 1
        return i

    def tdecl(self, opname, *ops, share=True):
        """A type declaration (result id first, no result type); identical declarations are shared."""
        key = (opname,) + tuple(tuple(o) if isinstance(o, list) else o for o in ops)
        if share and key in self.cache:
            return self.cache[key]
        i = self.new()
        self.decl += inst(OP[opname], i, *ops)
        if share:
            self.cache[key] = i
        return i

    def cdecl(self, opname, ty, *ops):
        key = (opname, ty) + tuple(ops)
        if key in self.cache:
            return self.cache[key]
        i = self.new()
        self.decl += inst(OP[opname], ty, i, *ops)
        self.cache[key] = i
        return i

    def decorate(self, target, name, *args):
        self.annot += inst(OP['Decorate'], target, DEC[name], *args)

    def member_decorate(self, target, member, name, *args):
        self.annot += inst(OP['MemberDecorate'], target, member, DEC[name], *args)

    # -- types
    def void(self): return self.tdecl('TypeVoid')
    def bool_(self): return self.tdecl('TypeBool')
    def u32(self): return self.tdecl('TypeInt', 32, 0)
    def i64(self): return self.tdecl('TypeInt', 64, 1)
    def u64(self): return self.tdecl('TypeInt', 64, 0)
    def f64(self): return self.tdecl('TypeFloat', 64)
    def v3u32(self): return self.tdecl('TypeVector', self.u32(), 3)
    def ptr(self, sc, ty): return self.tdecl('TypePointer', SC[sc], ty)

    # -- constants
    def c_u32(self, v): return self.cdecl('Constant', self.u32(), v & 0xFFFFFFFF)
    def c_i64(self, v): return self.cdecl('Constant', self.i64(), *i64_words(v))
    def c_u64(self, v): return self.cdecl('Constant', self.u64(), *i64_words(v))
    def c_f64(self, v): return self.cdecl('Constant', self.f64(), *f64_words(v))
    def c_bool(self, v): return self.cdecl('ConstantTrue' if v else 'ConstantFalse', self.bool_())


# ---------------------------------------------------------------------------------------------------------------------
# the kernel
# ---------------------------------------------------------------------------------------------------------------------
class Gen:
    """One kernel -> one module.  Values are (id, kind) with kind 'i' (int64), 'f' (binary64) or 'b' (SPIR-V bool)."""

    def __init__(self, kernel):
        self.k = kernel
        self.m = Module()
        self.body = []                     # instructions of the function after its first OpLabel
        self.vars = []                     # OpVariable instructions (they go first in the entry block)
        self.cur = None
        self.need_f64 = False
        self.glsl = None
        self.scal = {}
        self.locals = {}
        self.names = {}
        self._scan()

    # -- the lists, scalars and constants of the kernel in their parameter order -------------------------------------
    def _scan(self):
        k = self.k
        self.lists = list(k.lists)
        self.scalars = list(k.scalars.items())
        self.consts = list(k.consts.items())
        f = any(t == 'f' for t in k.lists.values()) or any(t == 'f' for _, t in self.scalars) \
            or any(t == 'f' for t, _ in k.consts.values()) or k.res_type == 'f' \
            or any(t == 'f' for t in k.locals.values())
        self.need_f64 = f

    # -- emission helpers
    def op(self, name, ty, *ops):
        r = self.m.new()
        self.body += inst(OP[name], ty, r, *ops)
        return r

    def op0(self, name, *ops):
        self.body += inst(OP[name], *ops)

    def label(self, i):
        self.body += inst(OP['Label'], i)
        self.cur = i

    def branch(self, i):
        self.op0('Branch', i)

    def newvar(self, ty, init=None):
        r = self.m.new()
        ops = [self.m.ptr('Function', ty), r, SC['Function']]
        if init is not None:
            ops.append(init)
        self.vars += inst(OP['Variable'], *ops)
        return r

    def contraction(self, r):
        self.m.decorate(r, 'NoContraction')
        return r

    # -- types shortcuts
    @property
    def I(self): return self.m.i64()
    @property
    def F(self):
        self.need_f64 = True
        return self.m.f64()
    @property
    def B(self): return self.m.bool_()
    @property
    def U32(self): return self.m.u32()
    @property
    def U64(self): return self.m.u64()

    def ci(self, v): return self.m.c_i64(v)
    def cf(self, v):
        self.need_f64 = True
        return self.m.c_f64(v)

    # -- the flag word (a Function variable; one atomic OR at the end if it is not 0)
    def flag(self, cond, bit):
        f = self.op('Load', self.U32, self.fvar)
        add = self.op('Select', self.U32, cond, self.m.c_u32(bit), self.m.c_u32(0))
        self.op0('Store', self.fvar, self.op('BitwiseOr', self.U32, f, add))

    # -- kind conversions
    def to_i(self, v):
        id_, kind = v
        if kind == 'i':
            return id_
        if kind == 'b':
            return self.op('Select', self.I, id_, self.ci(1), self.ci(0))
        raise Unsupported('a float where an int was expected')

    def to_f(self, v):
        id_, kind = v
        if kind != 'f':
            raise Unsupported('an int where a float was expected')
        return id_

    def to_b(self, v):
        id_, kind = v
        if kind == 'b':
            return id_
        if kind == 'i':
            return self.op('INotEqual', self.B, id_, self.ci(0))
        return self.op('FUnordNotEqual', self.B, id_, self.cf(0.0))

    def as_kind(self, v, t):
        return (self.to_f(v), 'f') if t == 'f' else (self.to_i(v), 'i')

    # -- control flow
    def if_then_else(self, cond, then_fn, else_fn=None):
        t, m = self.m.new(), self.m.new()
        e = self.m.new() if else_fn is not None else m
        self.op0('SelectionMerge', m, 0)
        self.op0('BranchConditional', cond, t, e)
        self.label(t)
        then_fn()
        self.branch(m)
        if else_fn is not None:
            self.label(e)
            else_fn()
            self.branch(m)
        self.label(m)

    def if_value(self, cond, ty, then_fn, else_fn):
        t, e, m = self.m.new(), self.m.new(), self.m.new()
        self.op0('SelectionMerge', m, 0)
        self.op0('BranchConditional', cond, t, e)
        self.label(t)
        a = then_fn()
        at = self.cur
        self.branch(m)
        self.label(e)
        b = else_fn()
        bt = self.cur
        self.branch(m)
        self.label(m)
        return self.op('Phi', ty, a, at, b, bt)

    # -- guards (the device twins of gk_chk and friends)
    def chk(self, r):
        """gk_chk: NaN and subnormal-range results set the flag."""
        self.flag(self.op('IsNan', self.B, r), GK_NAN)
        m = self.ext(GLSL_FABS, r)
        tiny = self.op('LogicalAnd', self.B, self.op('FOrdNotEqual', self.B, m, self.cf(0.0)),
                       self.op('FOrdLessThan', self.B, m, self.cf(2.0 ** TINY_EXP)))
        self.flag(tiny, GK_DENORM)
        return r

    def ext(self, number, *args):
        if self.glsl is None:
            self.glsl = self.m.new()
            self.m.imports += inst(OP['ExtInstImport'], self.glsl, words_of_string('GLSL.std.450'))
        return self.op('ExtInst', self.F, self.glsl, number, *args)

    SIGN = 1 << 63

    def bits(self, x):
        return self.op('Bitcast', self.U64, x)

    def from_bits(self, b):
        return self.op('Bitcast', self.F, b)

    def zero_sign(self, r, sign_bits):
        """r with the sign of an exact zero result forced to `sign_bits` (a u64 holding only the sign bit).  The device's
        compiler may fold `0.0 - x` into `-x` and the like, which gets the sign of zero wrong; an integer select it
        cannot rewrite."""
        isz = self.op('FOrdEqual', self.B, r, self.cf(0.0))
        return self.op('Select', self.F, isz, self.from_bits(sign_bits), r)

    def exp_field(self, x):
        bits = self.op('Bitcast', self.U64, x)
        return self.op('BitwiseAnd', self.U64, self.op('ShiftRightLogical', self.U64, bits, self.m.c_u32(52)),
                       self.m.c_u64(0x7FF))

    # -- expressions
    def ex(self, e):
        op, t = e[0], e[1]
        h = getattr(self, 'x_' + op, None)
        if h is None:
            raise Unsupported('IR node %r' % op)
        return h(e)

    def x_c(self, e):
        t, v = e[1], e[2]
        if t == 'f':
            c = self.cf(float(v))
            if v != 0 and abs(v) < 2.0 ** TINY_EXP:
                self.flag(self.m.c_bool(True), GK_DENORM)
            return c, 'f'
        return self.ci(int(v)), 'i'

    def x_v(self, e):
        name = e[2]
        if name in self.scal:
            return self.scal[name]
        if name not in self.locals:
            raise Unsupported('unknown name %s' % name)
        var, t = self.locals[name]
        return self.op('Load', self.F if t == 'f' else self.I, var), t

    def list_n(self, name):
        return self.listn[name]

    def x_len(self, e):
        return self.listn[e[2]], 'i'

    def x_ld(self, e):
        t, name = e[1], e[2]
        idx = self.to_i(self.ex(e[3]))
        n = self.listn[name]
        neg = self.op('SLessThan', self.B, idx, self.ci(0))
        i2 = self.op('Select', self.I, neg, self.op('IAdd', self.I, idx, n), idx)
        ok = self.op('LogicalAnd', self.B, self.op('SGreaterThanEqual', self.B, i2, self.ci(0)),
                     self.op('SLessThan', self.B, i2, n))
        self.flag(self.op('LogicalNot', self.B, ok), GK_INDEX)
        safe = self.op('Select', self.I, ok, i2, self.ci(0))
        elem = self.F if t == 'f' else self.I
        ptr = self.op('AccessChain', self.m.ptr('StorageBuffer', elem), self.listvar[name], self.m.c_u32(0), safe)
        v = self.op('Load', elem, ptr)
        if t == 'f':
            self.chk(v)
        return v, t

    def x_neg(self, e):
        t = e[1]
        if t == 'f':       # flip the sign bit: exact for every value, zeros included
            a = self.to_f(self.ex(e[2]))
            return self.from_bits(self.op('BitwiseXor', self.U64, self.bits(a), self.m.c_u64(self.SIGN))), 'f'
        a = self.to_i(self.ex(e[2]))
        self.flag(self.op('IEqual', self.B, a, self.ci(INT64_MIN)), GK_OVERFLOW)
        return self.op('SNegate', self.I, a), 'i'

    def x_pos(self, e):
        return self.as_kind(self.ex(e[2]), e[1])

    def x_c32(self, e):
        """gk_c32 (stage G5): an int that must fit int32 (the array dtype); outside it the overflow flag is set and the value is
        not used (the CPU replay raises OverflowError with the index)."""
        a = self.to_i(self.ex(e[2]))
        bad = self.op('LogicalOr', self.B, self.op('SLessThan', self.B, a, self.ci(-(1 << 31))),
                      self.op('SGreaterThan', self.B, a, self.ci((1 << 31) - 1)))
        self.flag(bad, GK_OVERFLOW)
        return a, 'i'

    def x_abs(self, e):
        t = e[1]
        if t == 'f':       # clear the sign bit
            a = self.to_f(self.ex(e[2]))
            return self.from_bits(self.op('BitwiseAnd', self.U64, self.bits(a), self.m.c_u64(self.SIGN - 1))), 'f'
        a = self.to_i(self.ex(e[2]))
        self.flag(self.op('IEqual', self.B, a, self.ci(INT64_MIN)), GK_OVERFLOW)
        neg = self.op('SLessThan', self.B, a, self.ci(0))
        return self.op('Select', self.I, neg, self.op('SNegate', self.I, a), a), 'i'

    def x_bin(self, e):
        t, name = e[1], e[2]
        if t == 'f':
            a, b = self.to_f(self.ex(e[3])), self.to_f(self.ex(e[4]))
            return self.fbin(name, a, b), 'f'
        if t != 'i':
            raise Unsupported('binary op of type %r' % t)
        a, b = self.to_i(self.ex(e[3])), self.to_i(self.ex(e[4]))
        return self.ibin(name, a, b), 'i'

    def fbin(self, name, a, b):
        U64 = self.U64
        sign = self.m.c_u64(self.SIGN)
        if name == 'mul':
            r = self.contraction(self.op('FMul', self.F, a, b))
            # a product of two normals whose exponents sum below -1000 may be a subnormal the device flushes
            nz = self.op('LogicalAnd', self.B, self.op('FOrdNotEqual', self.B, a, self.cf(0.0)),
                         self.op('FOrdNotEqual', self.B, b, self.cf(0.0)))
            ea, eb = self.exp_field(a), self.exp_field(b)
            fin = self.op('LogicalAnd', self.B, self.op('INotEqual', self.B, ea, self.m.c_u64(0x7FF)),
                          self.op('INotEqual', self.B, eb, self.m.c_u64(0x7FF)))
            low = self.op('ULessThan', self.B, self.op('IAdd', U64, ea, eb), self.m.c_u64(2044 + TINY_EXP))
            self.flag(self.op('LogicalAnd', self.B, self.op('LogicalAnd', self.B, nz, fin), low), GK_DENORM)
            # the sign of a zero product is the xor of the signs
            r = self.zero_sign(r, self.op('BitwiseAnd', U64, self.op('BitwiseXor', U64, self.bits(a), self.bits(b)), sign))
            return self.chk(r)
        if name in ('add', 'sub'):
            r = self.contraction(self.op('FAdd' if name == 'add' else 'FSub', self.F, a, b))
            bb = self.bits(b)
            if name == 'sub':
                bb = self.op('BitwiseXor', U64, bb, sign)               # a - b is a + (-b)
            bp = self.from_bits(bb)                                       # the addend: b, or -b for a - b
            flushed = self.op('LogicalAnd', self.B, self.op('FOrdEqual', self.B, r, self.cf(0.0)),
                              self.op('LogicalNot', self.B, self.op('FOrdEqual', self.B, a, self.from_bits(
                                  self.op('BitwiseXor', U64, bb, sign)))))
            self.flag(flushed, GK_DENORM)
            # a zero sum: -0.0 only when both operands are -0.0; any other exact zero is +0.0 (round to nearest even)
            both0 = self.op('LogicalAnd', self.B, self.op('FOrdEqual', self.B, a, self.cf(0.0)),
                            self.op('FOrdEqual', self.B, bp, self.cf(0.0)))
            zbits = self.op('Select', U64, both0, self.op('BitwiseAnd', U64, self.op('BitwiseAnd', U64, self.bits(a), bb), sign),
                            self.m.c_u64(0))
            r = self.zero_sign(r, zbits)
            return self.chk(r)
        raise Unsupported('float op %s' % name)

    def ibin(self, name, a, b):
        I, B = self.I, self.B
        if name in ('add', 'sub'):
            r = self.op('IAdd' if name == 'add' else 'ISub', I, a, b)
            if name == 'add':          # overflow iff a and b have the sign that r lacks
                bad = self.op('SLessThan', B, self.op('BitwiseAnd', I, self.op('BitwiseXor', I, a, r),
                                                      self.op('BitwiseXor', I, b, r)), self.ci(0))
            else:                      # overflow iff a and b differ in sign and r differs from a
                bad = self.op('SLessThan', B, self.op('BitwiseAnd', I, self.op('BitwiseXor', I, a, b),
                                                      self.op('BitwiseXor', I, a, r)), self.ci(0))
            self.flag(bad, GK_OVERFLOW)
            return r
        if name == 'mul':
            r = self.op('IMul', I, a, b)
            a_neg1 = self.op('IEqual', B, a, self.ci(-1))
            a_zero = self.op('IEqual', B, a, self.ci(0))
            safe = self.op('Select', I, self.op('LogicalOr', B, a_neg1, a_zero), self.ci(1), a)
            div_bad = self.op('INotEqual', B, self.op('SDiv', I, r, safe), b)
            min_case = self.op('LogicalAnd', B, a_neg1, self.op('IEqual', B, b, self.ci(INT64_MIN)))
            normal = self.op('LogicalAnd', B, self.op('LogicalNot', B, self.op('LogicalOr', B, a_neg1, a_zero)), div_bad)
            self.flag(self.op('LogicalOr', B, normal, min_case), GK_OVERFLOW)
            return r
        if name in ('floordiv', 'mod'):
            bz = self.op('IEqual', B, b, self.ci(0))
            bm1 = self.op('IEqual', B, b, self.ci(-1))
            self.flag(bz, GK_ZERODIV)
            d = self.op('Select', I, self.op('LogicalOr', B, bz, bm1), self.ci(1), b)
            r = self.op('SRem', I, a, d)
            differ = self.op('LogicalNotEqual', B, self.op('SLessThan', B, r, self.ci(0)),
                             self.op('SLessThan', B, b, self.ci(0)))
            fix = self.op('LogicalAnd', B, self.op('INotEqual', B, r, self.ci(0)), differ)
            if name == 'mod':
                rr = self.op('Select', I, fix, self.op('IAdd', I, r, b), r)
                return self.op('Select', I, bm1, self.ci(0), rr)
            q0 = self.op('SDiv', I, a, d)
            q = self.op('Select', I, fix, self.op('ISub', I, q0, self.ci(1)), q0)
            self.flag(self.op('LogicalAnd', B, bm1, self.op('IEqual', B, a, self.ci(INT64_MIN))), GK_OVERFLOW)
            return self.op('Select', I, bm1, self.op('SNegate', I, a), q)
        raise Unsupported('int op %s' % name)

    def x_cmp(self, e):
        op, mode = e[2], e[5]
        a, b = self.ex(e[3]), self.ex(e[4])
        if mode == 'i':
            a, b = self.to_i(a), self.to_i(b)
            name = {'<': 'SLessThan', '<=': 'SLessThanEqual', '>': 'SGreaterThan', '>=': 'SGreaterThanEqual',
                    '==': 'IEqual', '!=': 'INotEqual'}[op]
            return self.op(name, self.B, a, b), 'b'
        if mode == 'if':
            a, b = self.cvt_exact(a), self.cvt_exact(b)      # int against float: exact only up to 2**53
        else:
            a, b = self.to_f(a), self.to_f(b)
        name = {'<': 'FOrdLessThan', '<=': 'FOrdLessThanEqual', '>': 'FOrdGreaterThan', '>=': 'FOrdGreaterThanEqual',
                '==': 'FOrdEqual', '!=': 'FUnordNotEqual'}[op]
        return self.op(name, self.B, a, b), 'b'

    def cvt_exact(self, v):
        """gk_i2fx: an int operand of a float compare becomes a float, and the flag is set above 2**53."""
        if v[1] == 'f':
            return v[0]
        i = self.to_i(v)
        big = self.op('LogicalOr', self.B, self.op('SGreaterThan', self.B, i, self.ci(1 << 53)),
                      self.op('SLessThan', self.B, i, self.ci(-(1 << 53))))
        self.flag(big, GK_RANGE)
        return self.i2f(i)

    def i2f(self, i):
        r = self.op('ConvertSToF', self.F, i)
        return r

    def x_truth(self, e):
        return self.to_b(self.ex(e[3])), 'b'

    def x_not(self, e):
        return self.op('LogicalNot', self.B, self.to_b(self.ex(e[2]))), 'b'

    def x_and(self, e):
        a = self.to_b(self.ex(e[2]))
        r = self.if_value(a, self.B, lambda: self.to_b(self.ex(e[3])), lambda: self.m.c_bool(False))
        return r, 'b'

    def x_or(self, e):
        a = self.to_b(self.ex(e[2]))
        r = self.if_value(a, self.B, lambda: self.m.c_bool(True), lambda: self.to_b(self.ex(e[3])))
        return r, 'b'

    def x_vand(self, e):
        t = e[1]
        a = self.as_kind(self.ex(e[2]), t)[0]
        ty = self.F if t == 'f' else self.I
        test = self.to_b((a, 'f' if t == 'f' else 'i'))
        r = self.if_value(test, ty, lambda: self.as_kind(self.ex(e[3]), t)[0], lambda: a)
        return r, 'f' if t == 'f' else 'i'

    def x_vor(self, e):
        t = e[1]
        a = self.as_kind(self.ex(e[2]), t)[0]
        ty = self.F if t == 'f' else self.I
        test = self.to_b((a, 'f' if t == 'f' else 'i'))
        r = self.if_value(test, ty, lambda: a, lambda: self.as_kind(self.ex(e[3]), t)[0])
        return r, 'f' if t == 'f' else 'i'

    def x_sel(self, e):
        t = e[1]
        c = self.to_b(self.ex(e[2]))
        kind = 'f' if t == 'f' else 'i'
        ty = self.F if t == 'f' else self.I
        r = self.if_value(c, ty, lambda: self.as_kind(self.ex(e[3]), t)[0], lambda: self.as_kind(self.ex(e[4]), t)[0])
        return r, kind

    def x_cvt(self, e):
        kind, a = e[2], self.ex(e[3])
        if kind == 'i2f':
            return self.i2f(self.to_i(a)), 'f'
        if kind == 'b2i':
            return self.to_i(a), 'i'
        x = self.to_f(a)
        if kind == 'ffloor':
            bad = self.op('LogicalOr', self.B, self.op('IsInf', self.B, x), self.op('IsNan', self.B, x))
            self.flag(bad, GK_RANGE)
            return self.ext(GLSL_FLOOR, x), 'f'
        if kind == 'floor':
            x = self.ext(GLSL_FLOOR, x)
        elif kind == 'ceil':
            x = self.ext(GLSL_CEIL, x)
        elif kind != 'trunc':
            raise Unsupported('conversion %s' % kind)
        ok = self.op('LogicalAnd', self.B, self.op('FOrdGreaterThanEqual', self.B, x, self.cf(-9223372036854775808.0)),
                     self.op('FOrdLessThan', self.B, x, self.cf(9223372036854775808.0)))
        self.flag(self.op('LogicalNot', self.B, ok), GK_RANGE)
        safe = self.op('Select', self.F, ok, x, self.cf(0.0))     # never convert an out-of-range value
        return self.op('ConvertFToS', self.I, safe), 'i'

    def x_mm(self, e):
        t, which, args = e[1], e[2], e[3]
        vals = [self.as_kind(self.ex(a), t)[0] for a in args]
        body = vals[0]
        for tm in vals[1:]:
            prev = body
            if t == 'f':
                better = self.op('FOrdGreaterThan' if which == 'max' else 'FOrdLessThan', self.B, tm, body)
            else:
                better = self.op('SGreaterThan' if which == 'max' else 'SLessThan', self.B, tm, body)
            body = self.op('Select', self.F if t == 'f' else self.I, better, tm, body)
            if t == 'f':       # equal values (+0.0 and -0.0 included) keep the first, as Python does, whatever the compiler does
                tie = self.op('FOrdEqual', self.B, tm, prev)
                body = self.op('Select', self.F, tie, prev, body)
        return body, 'f' if t == 'f' else 'i'

    def x_blk(self, e):
        self.stmts(e[2])
        return self.ex(e[3])

    # -- statements
    def stmts(self, stmts):
        for s in stmts:
            h = getattr(self, 's_' + s[0], None)
            if h is None:
                raise Unsupported('statement %r' % s[0])
            h(s)

    def s_set(self, s):
        _, name, t, e = s
        v = self.as_kind(self.ex(e), t)[0]
        self.op0('Store', self.locals[name][0], v)

    def s_if(self, s):
        c = self.to_b(self.ex(s[1]))
        then, other = s[2], s[3]
        self.if_then_else(c, lambda: self.stmts(then), (lambda: self.stmts(other)) if other else None)

    def s_for(self, s):
        _, var, lo, hi, body = s
        a, b = self.to_i(self.ex(lo)), self.to_i(self.ex(hi))
        v = self.locals[var][0]
        self.op0('Store', v, a)
        header, cond, bodyl, cont, merge = (self.m.new() for _ in range(5))
        self.branch(header)
        self.label(header)
        self.op0('LoopMerge', merge, cont, 0)
        self.branch(cond)
        self.label(cond)
        i = self.op('Load', self.I, v)
        f = self.op('Load', self.U32, self.fvar)
        go = self.op('LogicalAnd', self.B, self.op('SLessThan', self.B, i, b), self.op('IEqual', self.B, f, self.m.c_u32(0)))
        self.op0('BranchConditional', go, bodyl, merge)
        self.label(bodyl)
        self.stmts(body)
        self.branch(cont)
        self.label(cont)
        i2 = self.op('Load', self.I, v)
        self.op0('Store', v, self.op('IAdd', self.I, i2, self.ci(1)))
        self.branch(header)
        self.label(merge)

    # -- the module
    def build(self):
        k, m = self.k, self.m
        I, U32 = self.I, self.U32
        # parameters block: cnt, lo, width, n of every list, then the scalars and the constants
        members = [('cnt', 'i'), ('lo', 'i'), ('width', 'i')]
        members += [('n_' + l, 'i') for l in self.lists]
        members += [(name, t) for name, t in self.scalars_named()]
        self.members = members
        pstruct = m.tdecl('TypeStruct', *[self.F if t == 'f' else I for _, t in members], share=False)
        m.decorate(pstruct, 'Block')
        for idx, (_, t) in enumerate(members):
            m.member_decorate(pstruct, idx, 'Offset', 8 * idx)
            m.member_decorate(pstruct, idx, 'NonWritable')
        self.pvar = self.gvar(pstruct, 0)

        fstruct = m.tdecl('TypeStruct', U32, share=False)
        m.decorate(fstruct, 'Block')
        m.member_decorate(fstruct, 0, 'Offset', 0)
        self.fbuf = self.gvar(fstruct, 1)

        def buffer_of(elem, binding, readonly):
            arr = m.tdecl('TypeRuntimeArray', elem, share=False)
            m.decorate(arr, 'ArrayStride', 8)
            st = m.tdecl('TypeStruct', arr, share=False)
            m.decorate(st, 'Block')
            m.member_decorate(st, 0, 'Offset', 0)
            if readonly:
                m.member_decorate(st, 0, 'NonWritable')
            return self.gvar(st, binding)

        res_t = self.F if k.res_type == 'f' else I
        self.resvar = buffer_of(res_t, 2, False)
        self.listvar = {}
        for j, l in enumerate(self.lists):
            self.listvar[l] = buffer_of(self.F if k.lists[l] == 'f' else I, MAX_STORAGE_BINDINGS + j, True)

        gid = m.new()
        m.decl += inst(OP['Variable'], m.ptr('Input', m.v3u32()), gid, SC['Input'])
        m.decorate(gid, 'BuiltIn', 28)
        self.interface = [self.pvar, self.fbuf, self.resvar] + [self.listvar[l] for l in self.lists] + [gid]

        fnty = m.tdecl('TypeFunction', m.void())
        main = m.new()
        first = m.new()
        self.label(first)

        # global index = y * width + x
        v = self.op('Load', m.v3u32(), gid)
        x = self.op('UConvert', self.U64, self.op('CompositeExtract', U32, v, 0))
        y = self.op('UConvert', self.U64, self.op('CompositeExtract', U32, v, 1))
        width = self.param('width')
        cnt = self.param('cnt')
        idx_u = self.op('IAdd', self.U64, self.op('IMul', self.U64, y, self.op('Bitcast', self.U64, width)), x)
        inr = self.op('ULessThan', self.B, idx_u, self.op('Bitcast', self.U64, cnt))
        idx = self.op('Bitcast', I, idx_u)
        work, done = m.new(), m.new()
        self.fvar = self.newvar(U32, m.c_u32(0))
        self.op0('SelectionMerge', done, 0)
        self.op0('BranchConditional', inr, work, done)
        self.label(work)

        self.listn = {l: self.param('n_' + l) for l in self.lists}
        for name, t in self.scalars_named():
            val = self.param(name)
            self.scal[name] = (val, t)
        for name, t in self.scalars_named():
            if t == 'f':
                self.chk(self.scal[name][0])
        for cname, t in sorted(k.locals.items()):
            self.locals[cname] = (self.newvar(self.F if t == 'f' else I, self.cf(0.0) if t == 'f' else self.ci(0)), t)
        if k.loop_var:
            lo = self.param('lo')
            self.op0('Store', self.locals[k.loop_var[0]][0], self.op('IAdd', I, lo, idx))
        for cname, t, lst in k.elems:
            elem = self.F if t == 'f' else I
            ptr = self.op('AccessChain', m.ptr('StorageBuffer', elem), self.listvar[lst], m.c_u32(0), idx)
            val = self.op('Load', elem, ptr)
            if t == 'f':
                self.chk(val)
            self.op0('Store', self.locals[cname][0], val)

        self.stmts(k.body)
        rv = self.as_kind(self.ex(k.result), k.res_type)[0]
        self.op0('Store', self.op('AccessChain', m.ptr('StorageBuffer', res_t), self.resvar, m.c_u32(0), idx), rv)
        fl = self.op('Load', U32, self.fvar)
        hit = self.op('INotEqual', self.B, fl, m.c_u32(0))
        def publish():
            p = self.op('AccessChain', m.ptr('StorageBuffer', U32), self.fbuf, m.c_u32(0))
            self.op('AtomicOr', U32, p, m.c_u32(1), m.c_u32(0), fl)
        self.if_then_else(hit, publish)
        self.branch(done)
        self.label(done)
        self.op0('Return')

        # function assembly: OpFunction, first label, variables, the rest
        head = inst(OP['Function'], m.void(), main, 0, fnty)
        label_words = inst(OP['Label'], first)
        rest = self.body[len(label_words):]
        func = head + label_words + self.vars + rest + inst(OP['FunctionEnd'])

        for cap in self.capabilities():
            m.caps += inst(OP['Capability'], CAP[cap])
        mem = inst(OP['MemoryModel'], 0, 1)
        entry = inst(OP['EntryPoint'], 5, main, words_of_string('main'), self.interface)
        modes = inst(OP['ExecutionMode'], main, 17, LOCAL_SIZE, 1, 1)
        if self.need_f64:
            modes += inst(OP['ExecutionMode'], main, 4462, 64)       # RoundingModeRTE
            modes += inst(OP['ExecutionMode'], main, 4461, 64)       # SignedZeroInfNanPreserve
        out = [0x07230203, 0x00010400, 0x0A1A0001, m.bound, 0]
        out += m.caps + m.imports + mem + entry + modes + m.annot + m.decl + func
        return out

    def capabilities(self):
        caps = ['Shader', 'Int64']
        if self.need_f64:
            caps += ['Float64', 'RoundingModeRTE', 'SignedZeroInfNanPreserve']
        return caps

    def scalars_named(self):
        return [('s_' + n, t) for n, t in self.scalars] + [('s_' + n, t) for n, (t, _) in self.consts]

    def gvar(self, struct_ty, binding):
        m = self.m
        v = m.new()
        m.decl += inst(OP['Variable'], m.ptr('StorageBuffer', struct_ty), v, SC['StorageBuffer'])
        m.decorate(v, 'DescriptorSet', 0)
        m.decorate(v, 'Binding', binding)
        return v

    def param(self, name):
        idx = [n for n, _ in self.members].index(name)
        t = self.members[idx][1]
        ty = self.F if t == 'f' else self.I
        p = self.op('AccessChain', self.m.ptr('StorageBuffer', ty), self.pvar, self.m.c_u32(idx))
        return self.op('Load', ty, p)


def compile_kernel(kernel):
    """(words, info) of the kernel's compute shader.  info: need_f64, lists (names in binding order), params (member
    names and types in order: cnt, lo, width, n_<list>..., s_<scalar>..., s_<const>...).  Raises Unsupported."""
    g = Gen(kernel)
    words = g.build()
    return words, dict(need_f64=g.need_f64, lists=list(g.lists), params=list(g.members))


def disassemble_hint(words):
    """The header of a module as text (tests and notes)."""
    return 'SPIR-V %d.%d, %d words, bound %d' % ((words[1] >> 16) & 0xFF, (words[1] >> 8) & 0xFF, len(words), words[3])
