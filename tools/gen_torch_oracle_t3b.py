#!/usr/bin/env python3
"""Write AIL_CURRENT/array_t3b_data/torch_oracle.json: what real PyTorch (CPU wheel) gives for the behaviours that
docs/design/TORCH_COMPAT.md pins to it and that stage T3b of ail_array reproduces (int64 wrap, casts, comparisons, bool
logic, promotion, index errors, strided gather/scatter, segments, f32 matmul).

Owner-run, never in CI (the venv is 938 MB):

    ATEN_CPU_CAPABILITY=default OMP_NUM_THREADS=1 /home/bluec/scratch/torch-venv/bin/python tools/gen_torch_oracle_t3b.py

The oracle configuration is the one of TORCH_COMPAT.md 2.2. Floats are stored as the hex of their bits, ints as ints,
bools as bools. test_ail_array_t3b.py checks the reference `ail_array.py` against this file and the compiled programs
against the reference.
"""
import json
import math
import struct
import sys
from pathlib import Path

import torch

torch.use_deterministic_algorithms(True)
torch.set_num_threads(1)

OUT = Path(__file__).resolve().parent.parent / "AIL_CURRENT" / "array_t3b_data" / "torch_oracle.json"
LO, HI = -(1 << 63), (1 << 63) - 1
DT = {"bool": torch.bool, "int8": torch.int8, "int32": torch.int32, "int64": torch.int64, "f16": torch.float16,
      "f32": torch.float32, "f64": torch.float64}
CODE = {"f16": "e", "f32": "f", "f64": "d"}
NAN = float("nan")


def fb(dt, x):
    """The bits of the Python float x (already a value of dt) as hex."""
    return struct.pack("<" + CODE[dt], x).hex()


def fl(dt, t):
    return [fb(dt, x) for x in t.tolist()]


def ten(values, dt):
    return torch.tensor(values, dtype=DT[dt])


def f32s(values):
    return [struct.unpack("<f", struct.pack("<f", v))[0] for v in values]


out = {"meta": {"torch": torch.__version__, "python": sys.version.split()[0],
                "config": "ATEN_CPU_CAPABILITY=default OMP_NUM_THREADS=1 use_deterministic_algorithms(True)",
                "generator": "tools/gen_torch_oracle_t3b.py"}}

# ---- int64 arithmetic wraps ---------------------------------------------------------------------------------------------
edge = [LO, LO + 1, -(1 << 62), -(1 << 32), -3037000500, -2, -1, 0, 1, 2, 3037000500, 3037000499, 1 << 32, 1 << 62,
        HI - 1, HI]
ops = {"add": lambda a, b: a + b, "sub": lambda a, b: a - b, "mul": lambda a, b: a * b,
       "floordiv": torch.floor_divide, "mod": torch.remainder}
rows = []
for name, f in ops.items():
    for a in edge:
        for b in edge:
            if name in ("floordiv", "mod") and b == 0:
                continue
            r = f(ten([a], "int64"), ten([b], "int64"))
            assert r.dtype == torch.int64
            rows.append([name, a, b, r.item()])
out["int64_binary"] = rows
out["int64_unary"] = [[n, a, f(ten([a], "int64")).item()] for n, f in (("neg", torch.neg), ("abs", torch.abs)) for a in edge]
sums = []
for vals in ([HI, 1], [HI, HI, HI], [LO, LO], [LO, -1], [HI, HI, LO, LO], [1 << 62] * 5, [1, 2, 3], [], [HI] * 7 + [LO] * 3,
             [3037000500] * 4):
    t = ten(vals, "int64")
    other = [(v * 3 + 1) % (1 << 63) for v in vals]
    sums.append({"values": vals, "sum": t.sum().item(), "other": other, "dot": t.dot(ten(other, "int64")).item() if vals else 0})
out["int64_sums"] = sums
# index_put with accumulate wraps too
t = torch.zeros(3, dtype=torch.int64)
t.index_put_((torch.tensor([0, 0, 2]),), torch.tensor([HI, 5, LO]), accumulate=True)
out["int64_put_accumulate"] = {"idx": [0, 0, 2], "src": [HI, 5, LO], "result": t.tolist()}

# ---- casts ---------------------------------------------------------------------------------------------------------------
ints = [0, 1, -1, 255, 256, -129, 65519, 65520, 65535, 65536, 1 << 24, (1 << 24) + 1, (1 << 24) + 3, 1 << 53, (1 << 53) + 1,
        (1 << 53) + 3, (1 << 62) + (1 << 38), (1 << 62) + (1 << 38) + 1, (1 << 62) + (1 << 39) - 1, (1 << 40) + 5, -(1 << 40) - 5,
        2147483647, 2147483648, -2147483648, -2147483649, HI, LO, HI - 1000, LO + 1000, 4294967296 + 7]
t = ten(ints, "int64")
out["casts"] = {
    "ints": ints,
    "to_f64": fl("f64", t.double()), "to_f32": fl("f32", t.float()), "to_f16": fl("f16", t.half()),
    "to_int8": t.to(torch.int8).tolist(), "to_int32": t.to(torch.int32).tolist(), "to_bool": t.bool().tolist(),
}
fs = [0.0, -0.0, 1.0, -1.0, 1.5, -1.5, 2.5, -2.5, 0.9999999, 1e10, -1e10, 4294967296.5, 9007199254740992.0,
      4611686018427387904.0, 9223372036854774784.0, -9223372036854775808.0, 0.1, 1e-300, NAN, math.inf, -math.inf, 3.4e38,
      5e-324]
tf = ten(fs, "f64")
out["casts"]["floats"] = [fb("f64", x) for x in fs]
out["casts"]["f64_to_bool"] = tf.bool().tolist()
inr = [x for x in fs if x == x and abs(x) < 9.3e18 and -9223372036854775808.0 <= x < 9223372036854775808.0]
out["casts"]["f64_in_range"] = [fb("f64", x) for x in inr]
out["casts"]["f64_to_int64_trunc"] = ten(inr, "f64").to(torch.int64).tolist()
f32v = f32s([0.0, -0.0, 1.0, 0.1, NAN, math.inf, -math.inf, 1e-45, 3.4028235e38, -2.5])
out["casts"]["f32_values"] = [fb("f32", x) for x in f32v]
out["casts"]["f32_to_bool"] = ten(f32v, "f32").bool().tolist()
out["casts"]["bool_to_int64"] = torch.tensor([True, False, True]).to(torch.int64).tolist()
out["casts"]["bool_to_f32"] = fl("f32", torch.tensor([True, False, True]).float())

# ---- comparisons (NaN, signed zero, scalars stored to the array dtype first) ---------------------------------------------
cmp_rows = []
specials = f32s([NAN, 0.0, -0.0, 1.0, 0.1, 16777216.0, -2.5, math.inf, -math.inf, 3.4028235e38])
tx = ten(specials, "f32")
ty = ten(list(reversed(specials)), "f32")
for n, f in (("eq", torch.eq), ("ne", torch.ne), ("lt", torch.lt), ("le", torch.le), ("gt", torch.gt), ("ge", torch.ge)):
    cmp_rows.append({"op": n, "dtype": "f32", "a": [fb("f32", x) for x in specials], "b": [fb("f32", x) for x in reversed(specials)],
                     "array": f(tx, ty).tolist(),
                     "scalar": 0.1, "scalar_result": f(tx, 0.1).tolist(),
                     "scalar2": 16777217.0, "scalar2_result": f(tx, 16777217.0).tolist()})
out["compare_f32"] = cmp_rows
iv = [LO, -1, 0, 1, HI, 5, 5, -5]
iw = [HI, -1, 0, 2, HI, -5, 5, 5]
out["compare_int64"] = [{"op": n, "a": iv, "b": iw, "result": f(ten(iv, "int64"), ten(iw, "int64")).tolist(),
                         "scalar": 1, "scalar_result": f(ten(iv, "int64"), 1).tolist()}
                        for n, f in (("eq", torch.eq), ("ne", torch.ne), ("lt", torch.lt), ("le", torch.le),
                                     ("gt", torch.gt), ("ge", torch.ge))]

# ---- bool logic, where, any, all, sums -----------------------------------------------------------------------------------
ba = [True, True, False, False]
bb = [True, False, True, False]
a_, b_ = torch.tensor(ba), torch.tensor(bb)
out["bool"] = {
    "a": ba, "b": bb, "and": torch.logical_and(a_, b_).tolist(), "or": torch.logical_or(a_, b_).tolist(),
    "xor": torch.logical_xor(a_, b_).tolist(), "not": torch.logical_not(a_).tolist(),
    "add": (a_ + b_).tolist(), "mul": (a_ * b_).tolist(),     # torch: bool + bool is or, bool * bool is and
    "sum": a_.sum().item(), "sum_dtype": str(a_.sum().dtype), "any": [a_.any().item(), torch.tensor([False] * 3).any().item(),
                                                                         torch.tensor([], dtype=torch.bool).any().item()],
    "all": [a_.all().item(), torch.tensor([True] * 3).all().item(), torch.tensor([], dtype=torch.bool).all().item()],
    "any_float_nan": torch.tensor([0.0, NAN]).any().item(), "all_float_zero": torch.tensor([1.0, -0.0]).all().item(),
    "where_f32": fl("f32", torch.where(a_, ten(f32s([1.5, 2.5, 3.5, 4.5]), "f32"), ten(f32s([-1.0, -2.0, -3.0, -4.0]), "f32"))),
}
for name, call in (("sub", lambda: a_ - b_), ("neg", lambda: -a_)):
    try:
        call()
        out["bool"][name + "_error"] = None
    except Exception as e:           # NotImplementedError with torch's text
        out["bool"][name + "_error"] = type(e).__name__
# ---- promotion ----------------------------------------------------------------------------------------------------------
names = list(DT)
out["promote_types"] = {a: {b: str(torch.promote_types(DT[a], DT[b])).split(".")[1] for b in names} for a in names}
short = {"bool": "bool", "int8": "int8", "int32": "int32", "int64": "int64", "float16": "f16", "float32": "f32", "float64": "f64"}
out["promote_types"] = {a: {b: short[v] for b, v in row.items()} for a, row in out["promote_types"].items()}
scal = {"True": True, "1": 1, "1.5": 1.5}
out["promote_scalar"] = {a: {k: short[str((torch.zeros(2, dtype=DT[a]) + v).dtype).split(".")[1]] for k, v in scal.items()}
                         for a in names}
out["promote_scalar_mul_true"] = {a: short[str((torch.zeros(2, dtype=DT[a]) * True).dtype).split(".")[1]] for a in names}

# ---- indexing ---------------------------------------------------------------------------------------------------------
x = torch.tensor([10.0, 20.0, 30.0])
takes = []
for idx in ([0, 2], [-1, -3], [2, 2, 0], [], [3], [-4], [1, 5, 9]):
    row = {"idx": idx}
    try:
        row["result"] = fl("f32", x[torch.tensor(idx, dtype=torch.int64)])
    except Exception as e:
        row["error"] = [type(e).__name__, str(e)]
    takes.append(row)
out["take"] = {"x": fl("f32", x), "cases": takes}
puts = []
for idx, src, acc in (([0, 2], [1.0, 2.0], False), ([1, 1, 1], [1.0, 2.0, 3.0], False), ([1, 1, 1], [1.0, 2.0, 3.0], True),
                      ([-1], [9.0], False), ([3], [9.0], False), ([0, -4], [1.0, 2.0], False)):
    y = x.clone()
    row = {"idx": idx, "src": src, "accumulate": acc}
    try:
        y.index_put_((torch.tensor(idx, dtype=torch.int64),), torch.tensor(src), accumulate=acc)
        row["result"] = fl("f32", y)
    except Exception as e:
        row["error"] = [type(e).__name__, str(e)]
        row["after"] = fl("f32", y)
    puts.append(row)
out["put"] = {"x": fl("f32", x), "cases": puts}

# ---- strided gather / scatter (as_strided) -------------------------------------------------------------------------------
base = torch.arange(24.0, dtype=torch.float64)
g = []
for off, shape, strides in ((0, [24], [1]), (1, [2, 2], [1, 4]), (0, [3, 4], [4, 1]), (0, [4, 3], [1, 4]), (3, [2, 3], [0, 2]),
                            (5, [2, 3, 2], [12, 3, 1]), (7, [0, 3], [1, 1]), (7, [], []), (23, [1], [100]), (0, [2, 2, 2], [8, 0, 1]),
                            (0, [6, 4], [4, 1]), (2, [3, 3], [7, 1])):
    row = {"offset": off, "shape": shape, "strides": strides}
    try:
        row["result"] = fl("f64", torch.as_strided(base, shape, strides, off).reshape(-1))
    except Exception as e:
        row["torch_error"] = type(e).__name__
    g.append(row)
out["gather_strided"] = {"base": fl("f64", base), "cases": g}
sc = []
for off, shape, strides in ((0, [24], [1]), (1, [2, 2], [1, 4]), (0, [4, 3], [1, 4]), (3, [2, 3], [6, 2]), (5, [2, 3, 2], [12, 3, 1]),
                            (23, [1], [100]), (7, [0, 3], [1, 1]), (0, [3, 8], [8, 1])):
    z = torch.zeros(24, dtype=torch.float64)
    total = math.prod(shape)
    srcv = [float(k + 1) for k in range(total)]
    row = {"offset": off, "shape": shape, "strides": strides, "src": [fb("f64", v) for v in srcv]}
    try:
        torch.as_strided(z, shape, strides, off).copy_(torch.tensor(srcv, dtype=torch.float64).reshape(shape))
        row["result"] = fl("f64", z)
    except Exception as e:
        row["torch_error"] = type(e).__name__
    sc.append(row)
out["scatter_strided"] = {"cases": sc}

# ---- segments (values are small ints or NaN placements, so every summation order agrees) --------------------------------------
seg_vals = [3.0, -1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0, 5.0, 3.0]
offs = [0, 3, 3, 7, 10]
seg = {"values": [fb("f32", v) for v in seg_vals], "offsets": offs, "int_values": [3, -1, 4, 1, 5, 9, 2, 6, 5, HI], "sum_f32": [],
       "sum_int64": [], "max": [], "argmax": [], "min": [], "argmin": []}
tv = ten(seg_vals, "f32")
ti = ten(seg["int_values"], "int64")
for lo, hi in zip(offs[:-1], offs[1:]):
    seg["sum_f32"].append(fb("f32", tv[lo:hi].sum().item()))
    seg["sum_int64"].append(ti[lo:hi].sum().item())
    if hi > lo:
        s = tv[lo:hi]
        seg["max"].append(fb("f32", s.max().item()))
        seg["min"].append(fb("f32", s.min().item()))
        seg["argmax"].append(s.argmax().item())
        seg["argmin"].append(s.argmin().item())
    else:
        for k in ("max", "min", "argmax", "argmin"):
            seg[k].append(None)
nan_seg = f32s([1.0, NAN, 3.0, NAN, 2.0])
tn = ten(nan_seg, "f32")
seg["nan"] = {"values": [fb("f32", v) for v in nan_seg], "max": fb("f32", tn.max().item()), "min": fb("f32", tn.min().item()),
              "argmax": tn.argmax().item(), "argmin": tn.argmin().item()}
out["segments"] = seg

# ---- f32 matmul ------------------------------------------------------------------------------------------------------------
import random
rng = random.Random(5)
mm = []
for m, k, n, integer in ((2, 3, 2, True), (3, 17, 4, True), (4, 33, 3, True), (5, 37, 4, False), (2, 1025, 2, False), (1, 0, 3, True)):
    av = f32s([float(rng.randint(-8, 8)) if integer else rng.uniform(-3, 3) for _ in range(m * k)])
    bv = f32s([float(rng.randint(-8, 8)) if integer else rng.uniform(-3, 3) for _ in range(k * n)])
    ta_ = ten(av, "f32").reshape(m, k)
    tb_ = ten(bv, "f32").reshape(k, n)
    r = ta_ @ tb_ if k else torch.zeros(m, n)
    mm.append({"m": m, "k": k, "n": n, "integer": integer, "a": [fb("f32", v) for v in av], "b": [fb("f32", v) for v in bv],
               "result": fl("f32", r.reshape(-1))})
out["mm_f32"] = mm

OUT.parent.mkdir(parents=True, exist_ok=True)
# one line per top-level key: a readable diff without 15,000 lines
body = ",\n".join("%s: %s" % (json.dumps(k), json.dumps(out[k], sort_keys=True, separators=(",", ":"))) for k in sorted(out))
OUT.write_text("{\n" + body + "\n}\n", encoding="utf-8")
print("wrote", OUT, OUT.stat().st_size, "bytes; torch", torch.__version__)
