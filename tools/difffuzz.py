#!/usr/bin/env python3
"""Differential program generator and runner for AIL (CPython 3.12 is the oracle).

  python3 tools/difffuzz.py --seed 7                 # print one generated program
  python3 tools/difffuzz.py --seed 7 --check         # run it under CPython only (generator self-test)
  python3 tools/difffuzz.py --run --start 0 --count 200 -j 2 --out /tmp/fuzz1
  python3 tools/difffuzz.py --minimize FILE.py       # shrink a program that differs (cmp.sh classification)

A program is `imports, classes, functions, def main(): blocks, main()`. Blocks are independent top-level
statements of main(); every value is shown with print. Output never depends on set/dict hash order (sets
are shown through sorted()). Integer results outside int64 are a declared difference (A1): the runner runs
the program once under CPython with a range check on every integer-producing node and cuts the program at
the first block that leaves int64, so the part that is compared never needs bignums.
"""
import argparse
import ast
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

STRS = ["", "a", "ab", "hello", "h\u00e9llo", "\u65e5\u672c\u8a9e", "\u00f1and\u00fa", "\u03a9mega", "\u03b1\u03b2\u03b3",
        "\u20aczuro", "\u00df", "stra\u00dfe", "\u01c5", "\u0130", "x y z", " pad ", "a,b,,c", "12", "-7", "3.5",
        "1e3", "\u0663", "\ufb01", "\u00dcn\u00ef", "AbC", "na\u00efve caf\u00e9", "  ", "0", "+4", "nan", "inf", "1_0"]
KEYS = ["a", "b", "\u00e9", "\u65e5", "k1", "", " ", "zz"]
INTS = [0, 0, 1, 1, -1, 2, 3, 5, 7, 10, -7, 100, 255, 256, 1000, 65535, 2**31 - 1, 2**31, 2**31 + 1, -2**31,
        -2**31 - 1, 2**32, 2**32 - 1, 2**53, 2**53 + 1, -2**53 - 1, 2**62, 2**63 - 1, 2**63 - 2, -2**63,
        -2**63 + 1, 2**40, -2**40 - 3, 4294967295, 4294967296]
FLOATS = ["0.0", "-0.0", "1.0", "-1.0", "0.5", "-0.5", "1.5", "2.5", "-2.5", "3.5", "0.1", "0.2", "0.3", "1e16",
          "1e-7", "123456.789", "-3.0", "1e308", "-1e308", "5e-324", "2.0", "9007199254740993.0",
          "4.35", "2.675", "1e22", "1e21", "1e15", "0.000123", "100.0", "1e100"]
SMALLI = [0, 1, 2, 3, 5, 7, -1, -3, 10, 12, 100, -100, 31, 64, 255]


class G:
    def __init__(s, seed, nblocks=16):
        s.seed = seed
        s.r = random.Random(seed)
        s.nblocks = nblocks
        s.vars = {}          # name -> type for the current scope
        s.n = 0
        s.risk = False
        s.ind = 1
        s.lines = []
        s.defs = []          # names defined by the current block
        s.blocks = []        # (lines, defs)
        s.pre = []           # top level text before main
        s.funcs = []         # (name, nreq, ndef, star, raises)
        s.use_math = s.r.random() < 0.6
        s.use_cls = s.r.random() < 0.6
        s.cls = None
        s.obj_keys = s.r.random() < 0.25
        s.depth = 0
        s.tail = None
        s.pend = []

    # ---------- helpers
    def name(s, t):
        s.n += 1
        return {"int": "i", "float": "f", "str": "s", "bool": "b", "li": "li", "ls": "ls", "lf": "lf",
                "lo": "lo", "ti": "ti", "tm": "tm", "di": "di", "dk": "dk", "si": "si", "ss": "ss",
                "obj": "o"}.get(t, "v") + str(s.n)

    def w(s, text):
        s.lines.append("    " * s.ind + text)

    def newvar(s, t):
        v = s.name(t)
        s.pend.append((v, t))
        s.defs.append(v)
        return v

    def flush(s):
        for v, t in s.pend:
            s.vars[v] = t
        s.pend = []

    def var(s, t):
        c = [v for v, x in s.vars.items() if x == t]
        if not c:
            return None
        if len(c) > 2 and s.r.random() < 0.5:
            return s.r.choice(c[-2:])
        return s.r.choice(c)

    def ch(s, alts):
        ws = [a[0] for a in alts]
        return s.r.choices(alts, ws)[0][1]()

    def lit_int(s):
        v = s.r.choice(INTS) if s.r.random() < 0.55 else s.r.randint(-20, 60)
        return s.fmt_int(v)

    @staticmethod
    def fmt_int(v):
        if v == -2**63:
            return "(-9223372036854775807 - 1)"
        return "(%d)" % v if v < 0 else str(v)

    def small_int(s):
        v = s.var("int")
        if v and s.r.random() < 0.4:
            return "(%s %% %d)" % (v, s.r.choice([7, 10, 100, 1000]))
        return str(s.r.choice(SMALLI)) if s.r.random() < 0.8 else "(%d)" % s.r.randint(-9, 9)

    def lit_str(s):
        return repr(s.r.choice(STRS))

    def lit_float(s):
        v = s.r.choice(FLOATS)
        return "(%s)" % v if v.startswith("-") else v

    # ---------- int expressions
    def gi(s, d):
        r = s.r
        if d <= 0 or r.random() < 0.18:
            v = s.var("int")
            return v if v and r.random() < 0.6 else s.lit_int()
        D = d - 1
        A = [
            (6, lambda: "(%s %s %s)" % (s.gi(D), r.choice("+-"), s.gi(D))),
            (4, lambda: "(%s * %s)" % ((s.gi(D), s.gi(D)) if r.random() < 0.15 else (s.small_int(), s.gi(D)))),
            (4, lambda: s.divmod_i(D)),
            (3, lambda: "(%s %s %s)" % (s.gi(D), r.choice(["&", "|", "^"]), s.gi(D))),
            (2, lambda: "(%s %s %s)" % (s.gi(D), r.choice(["<<", ">>"]), s.shift_amt())),
            (2, lambda: "(~%s)" % s.gi(D)),
            (2, lambda: "(-%s)" % s.gi(D)),
            (2, lambda: "abs(%s)" % s.gi(D)),
            (2, lambda: "(%s ** %d)" % (s.gi(D), r.choice([0, 1, 2, 3, 4]))),
            (3, lambda: "len(%s)" % s.seq(D)),
            (3, lambda: "sum(%s)" % s.gli(D)),
            (2, lambda: s.risky("%s(%s)" % (r.choice(["min", "max"]), s.gli(D)))),
            (2, lambda: "%s(%s, %s)" % (r.choice(["min", "max"]), s.gi(D), s.gi(D))),
            (3, lambda: s.risky("%s[%s]" % (s.gli(D), s.gi(D)))),
            (2, lambda: s.risky("%s[%s]" % (s.gdi(D), s.key()))),
            (2, lambda: s.risky("%s[%s]" % (s.gdk(D), s.gi(D)))),
            (1, lambda: "%s[%d]" % (s.gti(D), r.randint(-3, 2))),
            (3, lambda: s.risky("int(%s)")  and "" or s.risky("int(%s)" % s.gf(D))),
            (3, lambda: s.risky("int(%s)" % s.gs(D))),
            (1, lambda: "int(%s)" % s.gb(D)),
            (2, lambda: s.risky("round(%s)" % s.gf(D))),
            (1, lambda: s.risky("(%s).__floor__()" % s.gf(D)) if False else "len(%s)" % s.gs(D)),
            (2, lambda: s.risky("divmod(%s, %s)[%d]" % (s.gi(D), s.gi(D), r.randint(0, 1)))),
            (2, lambda: "(%s if %s else %s)" % (s.gi(D), s.gb(D), s.gi(D))),
            (2, lambda: "%s.%s(%s)" % (s.gs(D), r.choice(["find", "count", "rfind"]), s.gs(D))),
            (1, lambda: s.risky("%s.index(%s)" % (s.gs(D), s.gs(D)))),
            (2, lambda: s.risky("ord(%s[%s])" % (s.gs(D), s.small_int()))),
            (1, lambda: "hash(%s)" % s.gi(D)),
            (1, lambda: "(%s).bit_length()" % s.gi(D)),
            (2, lambda: s.call_func(D)),
            (1, lambda: "(%s + %s)" % (s.gb(D), s.gb(D))),
            (1, lambda: s.risky("pow(%s, %s, %s)" % (s.gi(D), s.small_int(), s.small_int()))),
            (2, lambda: "%s(%s)" % (r.choice(["sum", "max", "min"]) if False else "sum", s.gen_i(D))),
            (1, lambda: s.obj_int(D)),
            (1, lambda: "len(%s)" % s.gset(D)),
            (1, lambda: "(%s // %s)" % (s.gf(D), "1") if False else "int(%s)" % s.gb(D)),
        ]
        return s.ch(A)

    def shift_amt(s):
        v = s.r.choice([0, 1, 2, 3, 7, 8, 15, 16, 31, 32, 33, 40, 62, 63, 64, -1])
        if v < 0:
            s.risk = True
        return str(v) if v >= 0 else "(%d)" % v

    def risky(s, text):
        s.risk = True
        return text

    def divmod_i(s, D):
        op = s.r.choice(["//", "%"])
        s.risk = True
        return "(%s %s %s)" % (s.gi(D), op, s.gi(D) if s.r.random() < 0.6 else s.r.choice(["3", "(-3)", "7", "(-7)", "0", "1", "(-1)"]))

    def key(s):
        v = s.var("str")
        return v if v and s.r.random() < 0.4 else repr(s.r.choice(KEYS))

    def gen_i(s, D):
        """a generator expression of ints (argument of sum/min/max/any/all)"""
        with s.scope():
            v = s.name("int")
            src = s.gli(D)
            s.vars[v] = "int"
            body = s.gi(D)
            cond = " if %s" % s.gb(D) if s.r.random() < 0.4 else ""
        s.risk = True
        return "(%s for %s in %s%s)" % (body, v, src, cond)

    def obj_int(s, D):
        if not s.cls:
            return s.lit_int()
        return s.r.choice(["%s.a", "%s.a", "hash(%s)"]) % s.go(D)

    # ---------- float expressions
    def gf(s, d):
        r = s.r
        if d <= 0 or r.random() < 0.2:
            v = s.var("float")
            return v if v and r.random() < 0.6 else s.lit_float()
        D = d - 1
        A = [
            (6, lambda: "(%s %s %s)" % (s.gf(D), r.choice("+-*"), s.gf(D))),
            (3, lambda: s.risky("(%s / %s)" % (s.gf(D), s.gf(D)))),
            (3, lambda: s.risky("(%s / %s)" % (s.gi(D), s.gi(D)))),
            (2, lambda: "(%s %s %s)" % (s.gi(D), r.choice("+-*"), s.gf(D))),
            (2, lambda: "float(%s)" % s.gi(D)),
            (2, lambda: s.risky("(%s %s %s)" % (s.gf(D), r.choice(["//", "%"]), s.gf(D)))),
            (2, lambda: s.risky("(%s %s %s)" % (s.gi(D), r.choice(["//", "%"]), s.gf(D)))),
            (2, lambda: "abs(%s)" % s.gf(D)),
            (2, lambda: "(-%s)" % s.gf(D)),
            (2, lambda: s.risky("(%s ** %s)" % (s.gf(D), r.choice(["2", "3", "0", "1"])))),
            (2, lambda: "sum(%s)" % s.glf(D)),
            (2, lambda: s.risky("%s(%s)" % (r.choice(["min", "max"]), s.glf(D)))),
            (3, lambda: "%s(%s, %s)" % (r.choice(["min", "max"]), s.gf(D), s.gf(D))),
            (2, lambda: "%s(%s, %s)" % (r.choice(["min", "max"]), s.gi(D), s.gf(D))),
            (2, lambda: s.risky("round(%s, %d)" % (s.gf(D), r.randint(-2, 4)))),
            (2, lambda: s.risky("%s[%s]" % (s.glf(D), s.gi(D)))),
            (2, lambda: s.risky("float(%s)" % s.gs(D))),
            (2, lambda: "(%s if %s else %s)" % (s.gf(D), s.gb(D), s.gf(D))),
            (1, lambda: s.mathf(D)),
            (1, lambda: s.risky("divmod(%s, %s)[%d]" % (s.gf(D), s.gf(D), r.randint(0, 1)))),
            (1, lambda: "float(%s)" % s.gb(D)),
        ]
        return s.ch(A)

    def mathf(s, D):
        if not s.use_math:
            return s.lit_float()
        r = s.r
        c = r.choice(["sqrt", "fabs", "floor", "copysign", "fmod", "trunc", "ceil", "hypot", "exp"])
        s.risk = True
        if c in ("copysign", "fmod", "hypot"):
            return "float(math.%s(%s, %s))" % (c, s.gf(D), s.gf(D))
        if c == "exp":
            return "math.exp(%s %% 10.0)" % s.gf(D)
        return "float(math.%s(%s))" % (c, s.gf(D))

    # ---------- bool expressions
    def gb(s, d):
        r = s.r
        if d <= 0 or r.random() < 0.15:
            v = s.var("bool")
            return v if v and r.random() < 0.6 else r.choice(["True", "False"])
        D = d - 1
        cmp = ["<", "<=", ">", ">=", "==", "!="]
        A = [
            (6, lambda: "(%s %s %s)" % (s.gi(D), r.choice(cmp), s.gi(D))),
            (4, lambda: "(%s %s %s)" % (s.gf(D), r.choice(cmp), s.gf(D))),
            (4, lambda: "(%s %s %s)" % (s.gi(D), r.choice(cmp), s.gf(D))),
            (3, lambda: "(%s %s %s)" % (s.gs(D), r.choice(cmp), s.gs(D))),
            (2, lambda: "(%s < %s < %s)" % (s.gi(D), s.gi(D), s.gi(D))),
            (2, lambda: "(%s %s %s)" % (s.gb(D), r.choice(["and", "or"]), s.gb(D))),
            (1, lambda: "(not %s)" % s.gb(D)),
            (2, lambda: "(%s in %s)" % (s.gi(D), s.gli(D))),
            (1, lambda: "(%s in %s)" % (s.gf(D), s.glf(D))),
            (2, lambda: "(%s in %s)" % (s.gs(D), s.gs(D))),
            (1, lambda: "(%s %s %s)" % (s.gs(D), r.choice(["in", "not in"]), s.gdi(D))),
            (1, lambda: "(%s in %s)" % (s.gi(D), s.gset(D))),
            (1, lambda: "(%s in %s)" % (s.gi(D), s.gdk(D))),
            (2, lambda: "%s.%s(%s)" % (s.gs(D), r.choice(["startswith", "endswith"]), s.gs(D))),
            (2, lambda: "%s.%s()" % (s.gs(D), r.choice(["isdigit", "isalpha", "isspace", "isupper", "islower", "isalnum", "isnumeric", "isdecimal", "isidentifier", "isascii"]))),
            (1, lambda: "%s(%s)" % (r.choice(["any", "all"]), s.glb(D))),
            (1, lambda: "%s(%s)" % (r.choice(["any", "all"]), s.gli(D))),
            (2, lambda: "(%s %s %s)" % (s.gli(D), r.choice(cmp), s.gli(D))),
            (1, lambda: "(%s %s %s)" % (s.gti(D), r.choice(cmp), s.gti(D))),
            (1, lambda: "(%s %s %s)" % (s.gb(D), r.choice(["==", "!=", "<"]), s.gi(D))),
            (2, lambda: s.obj_bool(D)),
            (1, lambda: "(%s and %s)" % (s.gi(D), s.gb(D)) if False else "bool(%s)" % s.gi(D)),
            (1, lambda: "bool(%s)" % s.gf(D)),
            (1, lambda: "bool(%s)" % s.gs(D)),
            (1, lambda: "(%s is not None)" % s.gi(D)),
        ]
        return s.ch(A)

    def glb(s, D):
        with s.scope():
            v = s.name("int")
            src = s.gli(D)
            s.vars[v] = "int"
            body = s.gb(D)
        s.risk = True
        return "[%s for %s in %s]" % (body, v, src)

    def obj_bool(s, D):
        if not s.cls:
            return s.r.choice(["True", "False"])
        c = s.cls
        ops = ["==", "!=", "<", ">"]
        if c["le"]:
            ops += ["<=", ">="]
        if s.r.random() < 0.2 and c["eqnot"]:
            return "(%s == %s)" % (s.go(D), s.gi(D))
        if s.r.random() < 0.25:
            return "(%s in %s)" % (s.go(D), s.glo(D))
        return "(%s %s %s)" % (s.go(D), s.r.choice(ops), s.go(D))

    # ---------- string expressions
    def gs(s, d):
        r = s.r
        if d <= 0 or r.random() < 0.2:
            v = s.var("str")
            return v if v and r.random() < 0.6 else s.lit_str()
        D = d - 1
        sl = lambda: s.slice_of(s.gs(D), D)
        A = [
            (5, lambda: "(%s + %s)" % (s.gs(D), s.gs(D))),
            (2, lambda: "(%s * %s)" % (s.gs(D), s.small_i3())),
            (4, sl),
            (2, lambda: s.risky("%s[%s]" % (s.gs(D), s.small_int()))),
            (3, lambda: "%s.%s()" % (s.gs(D), r.choice(["upper", "lower", "strip", "lstrip", "rstrip"]))),
            (2, lambda: "%s.replace(%s, %s)" % (s.gs(D), s.gs(D), s.gs(D))),
            (2, lambda: "%s.join(%s)" % (s.gs(D), s.gls(D))),
            (2, lambda: "str(%s)" % s.gi(D)),
            (2, lambda: "str(%s)" % s.gf(D)),
            (1, lambda: "str(%s)" % s.gb(D)),
            (3, lambda: "repr(%s)" % s.any_val(D)),
            (3, lambda: s.fstr(D)),
            (1, lambda: "%s.%s(%s)" % (s.gs(D), r.choice(["zfill", "center", "ljust", "rjust"]), s.small_i3() if False else str(r.randint(0, 12)))),
            (1, lambda: "(%s if %s else %s)" % (s.gs(D), s.gb(D), s.gs(D))),
            (2, lambda: s.risky("%s[%s]" % (s.gls(D), s.gi(D)))),
            (1, lambda: s.risky("%s[%s]" % (s.gs(D), s.small_int())) if False else "%s.%s(%s)" % (s.gs(D), r.choice(["lstrip", "rstrip", "strip"]), s.gs(D))),
            (1, lambda: '("%%s|%%d" %% (%s, %s))' % (s.gs(D), s.gi(D))),
                        (1, lambda: '("%%5.2f|%%-6s|%%x" %% (%s, %s, %s))' % (s.gf(D), s.gs(D), s.gi(D))),
            (1, lambda: s.risky("format(%s, %r)" % (s.gi(D), s.int_spec()))),
            (1, lambda: s.risky("chr(%s)" % s.small_chr())),
            (1, lambda: s.obj_str(D)),
            (1, lambda: s.risky("%s.partition(%s)[%d]" % (s.gs(D), s.gs(D), r.randint(0, 2)))),
        ]
        return s.ch(A)

    def small_chr(s):
        return s.r.choice(["65", "233", "955", "26085", "8364", "0", "(-1)", "1114112", "97", "223"])

    def small_i3(s):
        return str(s.r.choice([0, 1, 2, 3, -1]))

    def obj_str(s, D):
        if not s.cls:
            return s.lit_str()
        return s.r.choice(["str(%s)", "repr(%s)", "f'{%s}'"]) % s.go(D)

    def any_val(s, D):
        t = s.r.choice(["int", "float", "str", "bool", "li", "ls", "ti", "tm", "di", "lf", "obj", "lo"])
        if t in ("obj", "lo") and not s.cls:
            t = "int"
        return s.expr(t, D)

    # f-string with a format spec
    def fstr(s, D):
        r = s.r
        parts = []
        for _ in range(r.randint(1, 3)):
            t = r.choice(["int", "int", "float", "str", "bool", "obj"])
            if t == "obj" and not s.cls:
                t = "int"
            v = s.var(t)
            if t == "int":
                if v is None or r.random() < 0.3:
                    v = s.lit_int()
                spec = s.int_spec() if r.random() < 0.7 else ""
            elif t == "float":
                if v is None or r.random() < 0.3:
                    v = s.lit_float()
                spec = s.float_spec() if r.random() < 0.8 else ""
            elif t == "str":
                if v is None:
                    v = repr(r.choice([x for x in STRS if "\t" not in x]))
                spec = s.str_spec() if r.random() < 0.6 else ""
            elif t == "bool":
                if v is None:
                    v = "True"
                spec = r.choice(["", "", ">6", "d", "<7", "^8"])
            else:
                v = s.go(1)
                spec = ""
            conv = r.choice(["", "", "", "!r", "!s"]) if t in ("str", "obj", "int") and not (t == "int" and spec) else ""
            if t == "obj" and conv:
                spec = r.choice(["", ">12", "<14"])
            if conv and spec and t == "int":
                conv = ""
            if t == "str" and conv == "!a" and spec == "":
                pass
            if "'" in v and '"' in v:
                v = "0"
            parts.append("{%s%s%s}" % (v if not v.startswith("{") else "(%s)" % v, conv, (":" + spec) if spec else ""))
        txt = r.choice(["", "<", "x=", "[", "\u00e9 "]).join(["", ""]) if False else ""
        body = " ".join(parts)
        q = '"'
        out = "f" + q + body + q
        if '"' in body:
            out = "f'" + body + "'"
        if "'" in body and '"' in body:
            out = "'0'"
        s.risk = True
        return out

    def fill_align(s, allow_eq=False):
        r = s.r
        a = r.choice(["<", ">", "^"] + (["="] if allow_eq else []))
        f = r.choice(["", "", "*", "0", "\u00e9", "\u65e5", "-", " "])
        return f + a if r.random() < 0.8 else a

    def width(s):
        return s.r.choice(["", "", "5", "8", "12", "20", "3"])

    def int_spec(s):
        r = s.r
        t = r.choice(["", "d", "d", "x", "X", "o", "b", "e", "f", "g", "%", "n", "E"])
        sp = ""
        zero = ""
        if r.random() < 0.4:
            sp += s.fill_align(True)
        elif r.random() < 0.15:
            zero = "0"
        sign = r.choice(["", "", "+", " ", "-"])
        alt = "#" if t in "xXob" and t and r.random() < 0.4 else ""
        grp = ""
        if t in ("", "d", "e", "f", "g", "%", "E") and r.random() < 0.25:
            grp = r.choice([",", "_"])
        elif t in ("x", "X", "o", "b") and r.random() < 0.2:
            grp = "_"
        w = s.width() if not (sp.startswith("0") and False) else ""
        prec = ""
        if t in ("e", "f", "g", "%", "E") and r.random() < 0.6:
            prec = "." + str(r.randint(0, 6))
        if t == "" and sp == "" and not sign and not alt and not grp and not w:
            return ""
        if t == "" and (grp or prec):
            t = "d" if not prec else "g"
        if t == "n":
            grp = ""
        return sp + sign + alt + zero + w + grp + prec + t

    def float_spec(s):
        r = s.r
        t = r.choice(["", "f", "f", "e", "E", "g", "G", "%", "F", "n"])
        sp = s.fill_align(True) if r.random() < 0.4 else ""
        zero = "0" if not sp and r.random() < 0.1 else ""
        sign = r.choice(["", "", "+", " "])
        alt = "#" if r.random() < 0.1 else ""
        grp = r.choice([",", "_"]) if t in ("f", "g", "e", "%", "") and r.random() < 0.2 else ""
        w = s.width()
        prec = "." + str(r.randint(0, 8)) if r.random() < 0.7 else ""
        if t == "n":
            grp = ""
        return sp + sign + alt + zero + w + grp + prec + t

    def str_spec(s):
        r = s.r
        sp = s.fill_align() if r.random() < 0.7 else ""
        w = s.width()
        prec = "." + str(r.randint(0, 6)) if r.random() < 0.4 else ""
        t = r.choice(["", "", "s"])
        if sp == "" and w == "" and prec == "" and t == "":
            return ">4"
        return sp + w + prec + t

    # ---------- slices
    def slice_of(s, base, D):
        r = s.r
        def bound():
            c = r.random()
            if c < 0.3:
                return ""
            if c < 0.5 and s.var("int"):
                return s.small_int()
            return str(r.randint(-8, 8))
        a, b = bound(), bound()
        c = r.choice(["", "", "-1", "-2", "-3", "2", "3", "1", "-1", "-5"])
        if r.random() < 0.03:
            c = "0"
            s.risk = True
        if c == "":
            return "%s[%s:%s]" % (base, a, b)
        return "%s[%s:%s:%s]" % (base, a, b, c)

    # ---------- lists
    def gli(s, d):
        r = s.r
        if d <= 0 or r.random() < 0.2:
            v = s.var("li")
            if v and r.random() < 0.7:
                return v
            return "[%s]" % ", ".join(s.lit_int() if r.random() < 0.6 else s.small_int() for _ in range(r.randint(0, 6)))
        D = d - 1
        A = [
            (3, lambda: s.slice_of(s.gli(D), D)),
            (3, lambda: "(%s + %s)" % (s.gli(D), s.gli(D))),
            (1, lambda: "(%s * %s)" % (s.gli(D), s.small_i3())),
            (3, lambda: "sorted(%s)" % s.gli(D)),
            (2, lambda: "sorted(%s, reverse=True)" % s.gli(D)),
            (2, lambda: "sorted(%s, key=%s)" % (s.gli(D), r.choice(["abs", "lambda q: -q", "lambda q: q % 3", "lambda q: (q % 2, -q)"]))),
            (2, lambda: "list(reversed(%s))" % s.gli(D)),
            (3, lambda: s.comp_li(D)),
            (2, lambda: "list(map(%s, %s))" % (r.choice(["abs", "lambda q: q * 2", "lambda q: q - 1", "lambda q: -q", "lambda q: q // 2 if q else 0"]), s.gli(D))),
            (2, lambda: "list(filter(%s, %s))" % (r.choice(["lambda q: q > 0", "lambda q: q % 2", "None", "lambda q: q != 3"]), s.gli(D))),
            (2, lambda: "list(range(%s, %s, %s))" % (s.small_int(), s.small_int(), r.choice(["1", "2", "-1", "-3", "5"]))),
            (1, lambda: "list(range(%s))" % r.randint(0, 9)),
            (1, lambda: "list(%s)" % s.gli(D)),
            (1, lambda: "%s.copy()" % s.gli(D)),
            (1, lambda: "sorted(%s)" % s.gset(D)),
            (1, lambda: "list(%s)" % s.gdk(D)),
            (1, lambda: "list(%s.values())" % s.gdi(D)),
            (1, lambda: "list(%s.values())" % s.gdk(D)),
            (1, lambda: "[len(q) for q in %s]" % s.gls(D)),
            (1, lambda: "[q[0] for q in %s]" % s.gtl(D) if False else "list(%s)" % s.gti(D)),
            (1, lambda: "[divmod(%s, %s)[0] for q in range(3)]" % (s.gi(D), "7") if False else "[x for x in %s if x]" % s.gli(D)),
            (1, lambda: "[a for a, _ in enumerate(%s)]" % s.gs(D)),
            (1, lambda: "[a + b for a, b in zip(%s, %s)]" % (s.gli(D), s.gli(D))),
            (1, lambda: "[a * b for a, b in zip(%s, %s)]" % (s.gli(D), s.gli(D)) if False else "[a - b for a, b in zip(%s, %s)]" % (s.gli(D), s.gli(D))),
            (1, lambda: "[ord(q) for q in %s]" % s.gs(D)),
            (1, lambda: "[%s for _ in range(%d)]" % (s.gi(D), r.randint(0, 4))),
        ]
        return s.ch(A)

    def comp_li(s, D):
        with s.scope():
            v = s.name("int")
            src = s.gli(D)
            s.vars[v] = "int"
            body = s.gi(D)
            cond = " if %s" % s.gb(D) if s.r.random() < 0.5 else ""
            if s.r.random() < 0.2:
                w2 = s.name("int")
                src2 = s.gli(0)
                s.vars[w2] = "int"
                body = s.gi(D)
                s.risk = True
                return "[%s for %s in %s for %s in %s%s]" % (body, v, src, w2, src2, cond)
        s.risk = True
        return "[%s for %s in %s%s]" % (body, v, src, cond)

    def gls(s, d):
        r = s.r
        if d <= 0 or r.random() < 0.25:
            v = s.var("ls")
            if v and r.random() < 0.7:
                return v
            return "[%s]" % ", ".join(s.lit_str() for _ in range(r.randint(0, 5)))
        D = d - 1
        A = [
            (3, lambda: s.slice_of(s.gls(D), D)),
            (2, lambda: "(%s + %s)" % (s.gls(D), s.gls(D))),
            (3, lambda: "sorted(%s)" % s.gls(D)),
            (1, lambda: "sorted(%s, key=%s)" % (s.gls(D), r.choice(["len", "lambda q: q[::-1]", "str.lower", "lambda q: (len(q), q)"]))),
            (2, lambda: "%s.split(%s)" % (s.gs(D), r.choice(["", "','", "' '", "'a'", "'\u00e9'"]))),
            (2, lambda: "[str(q) for q in %s]" % s.gli(D)),
            (2, lambda: "[q.upper() for q in %s]" % s.gls(D)),
            (1, lambda: "list(%s)" % s.gs(D)),
            (1, lambda: "sorted(%s)" % s.gdi(D)),
            (1, lambda: "list(%s)" % s.gdi(D)),
            (1, lambda: "sorted(set(%s))" % s.gls(D)),
            (1, lambda: "%s.splitlines()" % s.gs(D)),
            (1, lambda: "list(reversed(%s))" % s.gls(D)),
            (1, lambda: "[q + %s for q in %s]" % (s.gs(D), s.gls(D))),
            (1, lambda: "[s2 for s2 in %s if len(s2) %s %d]" % (s.gls(D), r.choice(["<", ">", "=="]), r.randint(0, 4))),
        ]
        return s.ch(A)

    def glf(s, d):
        r = s.r
        if d <= 0 or r.random() < 0.25:
            v = s.var("lf")
            if v and r.random() < 0.7:
                return v
            return "[%s]" % ", ".join(s.lit_float() for _ in range(r.randint(0, 5)))
        D = d - 1
        A = [
            (2, lambda: s.slice_of(s.glf(D), D)),
            (2, lambda: "(%s + %s)" % (s.glf(D), s.glf(D))),
            (2, lambda: "sorted(%s)" % s.glf(D)),
            (2, lambda: "[float(q) for q in %s]" % s.gli(D)),
            (2, lambda: "[q * %s for q in %s]" % (s.lit_float(), s.glf(D))),
            (1, lambda: "[q / 3 for q in %s]" % s.glf(D)),
            (1, lambda: "list(reversed(%s))" % s.glf(D)),
            (1, lambda: "[%s]" % s.gf(D)),
        ]
        return s.ch(A)

    # tuples
    def gti(s, d):
        r = s.r
        v = s.var("ti")
        if d <= 0 or (v and r.random() < 0.4):
            if v and r.random() < 0.7:
                return v
        return "(%s, %s, %s)" % (s.gi(max(d - 1, 0)), s.gi(max(d - 1, 0)), s.gi(max(d - 1, 0)))

    def gtm(s, d):
        v = s.var("tm")
        if v and s.r.random() < 0.5:
            return v
        return "(%s, %s)" % (s.gi(max(d - 1, 0)), s.gs(max(d - 1, 0)))

    def gtl(s, d):
        return "[%s, %s]" % (s.gtm(d), s.gtm(d))

    # dicts
    def gdi(s, d):
        r = s.r
        v = s.var("di")
        if v and (d <= 0 or r.random() < 0.6):
            return v
        D = max(d - 1, 0)
        n = r.randint(0, 4)
        items = ["%s: %s" % (repr(r.choice(KEYS)), s.gi(D)) for _ in range(n)]
        A = [
            (4, lambda: "{%s}" % ", ".join(items)),
            (1, lambda: "{k: len(k) for k in %s}" % s.gls(D)),
            (1, lambda: "{k: %s for k in %s}" % (s.gi(D), s.gls(D)) if False else "dict(zip(%s, %s))" % (s.gls(D), s.gli(D))),
            (1, lambda: "dict(%s)" % s.gdi(D)),
            (1, lambda: "{k: v * 2 for k, v in %s.items() if v}" % s.gdi(D)),
                        (1, lambda: "%s.copy()" % s.gdi(D)),
            (1, lambda: "{k: v for k, v in sorted(%s.items())}" % s.gdi(D)),
        ]
        return s.ch(A)

    def gdk(s, d):
        r = s.r
        v = s.var("dk")
        if v and (d <= 0 or r.random() < 0.6):
            return v
        D = max(d - 1, 0)
        items = ["%s: %s" % (s.gi(D) if r.random() < 0.7 else s.small_int(), s.gi(D)) for _ in range(r.randint(0, 4))]
        A = [
            (4, lambda: "{%s}" % ", ".join(items)),
            (2, lambda: "{q: q * q for q in %s}" % s.gli(D)),
            (1, lambda: "dict(enumerate(%s))" % s.gli(D)),
            (1, lambda: "{q %% 5: q for q in %s}" % s.gli(D)),
        ]
        return s.ch(A)

    def gset(s, d):
        r = s.r
        v = s.var("si")
        if v and (d <= 0 or r.random() < 0.6):
            return v
        D = max(d - 1, 0)
        A = [
            (3, lambda: "set(%s)" % s.gli(D)),
            (2, lambda: "{%s}" % ", ".join(s.lit_int() for _ in range(r.randint(1, 4)))),
            (2, lambda: "{q %% %d for q in %s}" % (r.choice([3, 5, 10]), s.gli(D))),
            (1, lambda: "(%s %s %s)" % (s.gset(D), r.choice(["|", "&", "-", "^"]), s.gset(D))),
            (1, lambda: "%s.%s(%s)" % (s.gset(D), r.choice(["union", "intersection", "difference", "symmetric_difference"]), s.gset(D))),
            (1, lambda: "set(%s)" % s.gdk(D)),
        ]
        return s.ch(A)

    # objects
    def go(s, d):
        if not s.cls:
            return "0"
        r = s.r
        v = s.var("obj")
        if v and r.random() < 0.5:
            return v
        D = max(d - 1, 0)
        A = [
            (5, lambda: s.new_obj(D)),
            (2, lambda: s.risky("%s[%s]" % (s.glo(D), s.gi(D)))),
            (1, lambda: s.risky("%s(%s)" % (r.choice(["min", "max"]), s.glo(D)))),
            (1, lambda: s.risky("sorted(%s)[%s]" % (s.glo(D), r.choice(["0", "-1", "1"])))),
        ]
        return s.ch(A)

    def new_obj(s, D):
        c = s.cls
        k = "P" if not c["sub"] or s.r.random() < 0.6 else "Q"
        if k == "Q":
            return "Q(%s, %s, %s)" % (s.gi(D), s.gs(D), s.small_int())
        return "P(%s, %s)" % (s.gi(D), s.gs(D))

    def glo(s, d):
        if not s.cls:
            return "[]"
        r = s.r
        v = s.var("lo")
        if v and (d <= 0 or r.random() < 0.6):
            return v
        D = max(d - 1, 0)
        A = [
            (4, lambda: "[%s]" % ", ".join(s.new_obj(D) for _ in range(r.randint(0, 4)))),
            (2, lambda: "sorted(%s)" % s.glo(D)),
            (1, lambda: "(%s + %s)" % (s.glo(D), s.glo(D))),
            (1, lambda: s.slice_of(s.glo(D), D)),
            (1, lambda: "[q for q in %s if q %s %s]" % (s.glo(D), r.choice(["<", ">", "=="]), s.go(D))),
            (1, lambda: "list(reversed(%s))" % s.glo(D)),
            (1, lambda: "sorted(%s, reverse=True)" % s.glo(D)),
        ]
        return s.ch(A)

    # ---------- dispatch
    def seq(s, D):
        return s.ch([(3, lambda: s.gli(D)), (2, lambda: s.gs(D)), (1, lambda: s.gls(D)), (1, lambda: s.gdi(D)),
                     (1, lambda: s.gdk(D)), (1, lambda: s.gset(D)), (1, lambda: s.gti(D)), (1, lambda: s.glf(D))])

    def expr(s, t, D):
        return {"int": s.gi, "float": s.gf, "str": s.gs, "bool": s.gb, "li": s.gli, "ls": s.gls, "lf": s.glf,
                "ti": s.gti, "tm": s.gtm, "di": s.gdi, "dk": s.gdk, "si": s.gset, "obj": s.go,
                "lo": s.glo}[t](D)

    class _Scope:
        def __init__(s, g):
            s.g = g

        def __enter__(s):
            s.saved = dict(s.g.vars)
            s.nd = len(s.g.defs)

        def __exit__(s, *a):
            s.g.vars = s.saved

    def scope(s):
        return G._Scope(s)

    def default(s, t):
        return {"int": "0", "float": "0.0", "str": "''", "bool": "False", "li": "[]", "ls": "[]", "lf": "[]",
                "ti": "(0, 0, 0)", "tm": "(0, '')", "di": "{}", "dk": "{}", "si": "set()",
                "obj": "P(0, '')", "lo": "[]"}[t]

    def call_func(s, D):
        if not s.funcs:
            return s.lit_int()
        name, nreq, ndef, star, raises = s.r.choice(s.funcs)
        if raises:
            s.risk = True
        n = nreq + s.r.randint(0, ndef + (2 if star else 0))
        args = [s.gi(D) for _ in range(nreq)]
        extra = n - nreq
        if s.r.random() < 0.25 and ndef and extra == 1 and not star:
            return "%s(%s, d0=%s)" % (name, ", ".join(args), s.gi(D))
        args += [s.gi(D) for _ in range(extra)]
        return "%s(%s)" % (name, ", ".join(args))

    # ---------- statements
    def guard(s, fn):
        """run fn (emits lines); wrap them in try/except when an expression said it may raise"""
        saved = s.risk
        s.risk = False
        before = set(s.vars)
        start = len(s.lines)
        fn()
        s.flush()
        risky = s.risk
        s.risk = saved
        if risky and len(s.lines) > start:
            body = s.lines[start:]
            del s.lines[start:]
            for v in list(s.vars):
                if v not in before:
                    s.w("%s = %s" % (v, s.default(s.vars[v])))
            s.w("try:")
            for ln in body:
                s.lines.append("    " + ln)
            s.w("except %s:" % s.r.choice(["Exception as ex"] * 5 + ["(ValueError, ZeroDivisionError, IndexError, KeyError, OverflowError, RuntimeError, MyErr) as ex"]))
            s.w("    print('E', type(ex).__name__)")

    def stmt(s, simple=False):
        r = s.r
        s.depth += 1
        mut_ok = s.in_loop == 0 if hasattr(s, "in_loop") else True
        A = [
            (8, s.st_assign),
            (6, s.st_print),
            (5, s.st_aug),
            (3, s.st_reassign),
            (4, s.st_mut if mut_ok else s.st_itemaug),
            (3, s.st_itemaug),
            (2, s.st_unpack),
            (2, s.st_obj),
        ]
        if not simple and s.depth < 4:
            A += [(4, s.st_if), (4, s.st_for), (2, s.st_while), (4, s.st_try), (3, s.st_template)]
        fn = s.ch([(a[0], (lambda f=a[1]: f)) for a in A])
        s.guard(fn)
        s.depth -= 1

    in_loop = 0

    TYPES = [(6, "int"), (3, "float"), (3, "str"), (2, "bool"), (3, "li"), (1, "ls"), (1, "lf"), (1, "ti"), (1, "tm"),
             (2, "di"), (1, "dk"), (1, "si"), (1, "obj"), (1, "lo")]

    def pick_type(s):
        ts = [(w, t) for w, t in s.TYPES if t not in ("obj", "lo") or s.cls]
        return s.r.choices([t for _, t in ts], [w for w, _ in ts])[0]

    def st_assign(s):
        t = s.pick_type()
        e = s.expr(t, s.r.randint(1, 3))
        v = s.newvar(t)
        s.w("%s = %s" % (v, e))

    def st_reassign(s):
        t = s.pick_type()
        v = s.var(t)
        if v is None:
            return s.st_assign()
        if s.in_loop and t not in ("int", "float", "bool"):
            return s.st_assign()
        s.w("%s = %s" % (v, s.expr(t, s.r.randint(1, 3))))

    def st_print(s):
        r = s.r
        c = r.random()
        if c < 0.55:
            t = r.choice(["int", "int", "float", "float", "str", "bool", "li", "ls", "lf", "ti", "tm", "di", "dk", "obj", "lo"])
            if t in ("obj", "lo") and not s.cls:
                t = "int"
            s.w("print(%s)" % s.expr(t, r.randint(1, 3)))
        elif c < 0.65:
            s.w("print(%s)" % s.ch([(1, lambda: "sorted(%s)" % s.gset(2)), (1, lambda: "len(%s)" % s.gset(2))]))
        elif c < 0.75:
            s.w("print(%s, %s, sep=%r)" % (s.expr(r.choice(["int", "float", "str"]), 2), s.expr(r.choice(["int", "str", "bool"]), 2), r.choice([",", " | ", "", "\u00e9"])))
        elif c < 0.82:
            s.w("print(*%s, sep=%r, end=%r)" % (s.gli(2), r.choice([",", " "]), r.choice(["\n", "!\n", "\u00e9\n"])))
        elif c < 0.9:
            t = r.choice(["int", "float", "str", "bool", "li", "ls", "ti", "tm", "di", "dk"])
            s.w("print(repr(%s), str(%s))" % (s.expr(t, 2), s.expr(t, 2)))
        else:
            s.w("print(%s)" % s.gs(3))

    def st_aug(s):
        r = s.r
        t = r.choice(["int", "int", "int", "float", "str", "bool", "li", "ls"])
        v = s.var(t)
        if v is None:
            return s.st_assign()
        if t == "int":
            op = r.choice(["+=", "-=", "*=", "//=", "%=", "**=", "<<=", ">>=", "&=", "|=", "^=", "+=", "+=", "-="])
            if op in ("*=", "**=") or s.in_loop and op in ("<<=",):
                e = s.small_int() if op == "*=" else str(r.choice([0, 1, 2, 3]))
            elif op in ("<<=", ">>="):
                e = s.shift_amt()
            else:
                e = s.small_int() if s.in_loop else s.gi(2)
            if op in ("//=", "%=", "<<=", ">>=", "**="):
                s.risk = True
            if op == "%=" and r.random() < 0.5:
                pass
            s.w("%s %s %s" % (v, op, e))
        elif t == "float":
            op = r.choice(["+=", "-=", "*=", "/=", "//=", "%=", "**="])
            if op in ("/=", "//=", "%="):
                s.risk = True
            e = s.gf(2) if op != "**=" else r.choice(["2", "3"])
            if op == "**=":
                s.w("%s %s %s" % (v, op, e)) if False else s.w("%s = %s ** %s" % (v, v, e if e != "0.5" else "2"))
            else:
                s.w("%s %s %s" % (v, op, e))
            s.risk = True
        elif t == "str":
            if r.random() < 0.7:
                s.w("%s += %s" % (v, s.gs(2)))
            else:
                s.w("%s *= %s" % (v, r.choice(["0", "1", "2", "(-1)"])))
            if s.in_loop:
                s.w("%s = %s[:12]" % (v, v))
        elif t == "bool":
            s.w("%s %s= %s" % (v, r.choice(["|", "&", "^"]), s.gb(2)))
        elif t == "li":
            if s.in_loop:
                return
            if r.random() < 0.6:
                s.w("%s += %s" % (v, s.gli(2)))
            else:
                s.w("%s *= %s" % (v, r.choice(["0", "1", "2", "(-1)"])))
        elif t == "ls":
            if s.in_loop:
                return
            s.w("%s += %s" % (v, s.gls(2)))

    def st_itemaug(s):
        r = s.r
        c = r.random()
        if c < 0.3 and s.var("li"):
            v = s.var("li")
            idx = s.gi(1) if r.random() < 0.5 else str(r.randint(-4, 4))
            op = r.choice(["+=", "-=", "*=", "//=", "%=", "|=", "&=", "^=", ">>=", "<<="])
            s.risk = True
            if op in ("*=", "<<="):
                e = s.small_int() if op == "*=" else str(r.choice([0, 1, 3, 20]))
            elif op == ">>=":
                e = str(r.choice([0, 1, 5, 63]))
            else:
                e = s.gi(2)
            s.w("%s[%s] %s %s" % (v, idx, op, e))
        elif c < 0.5 and s.var("di"):
            s.risk = True
            s.w("%s[%s] %s %s" % (s.var("di"), s.key(), r.choice(["+=", "-=", "*=", "//=", "%="]), s.small_int() if r.random() < 0.7 else s.gi(2)))
        elif c < 0.6 and s.var("dk"):
            s.risk = True
            s.w("%s[%s] %s %s" % (s.var("dk"), s.gi(1) if r.random() < 0.5 else s.small_int(), r.choice(["+=", "-=", "*="]), s.small_int()))
        elif c < 0.7 and s.var("lf"):
            s.risk = True
            s.w("%s[%s] %s %s" % (s.var("lf"), r.randint(-3, 3), r.choice(["+=", "-=", "*=", "/=", "**="]), s.lit_float() if r.random() < 0.5 else "2"))
        elif c < 0.8 and s.var("ls"):
            s.risk = True
            s.w("%s[%s] %s %s" % (s.var("ls"), r.randint(-3, 3), r.choice(["+=", "*="]) , "2" if False else "'x'") if False else "%s[%s] += %s" % (s.var("ls"), r.randint(-3, 3), s.lit_str()))
        elif c < 0.9 and s.cls and s.var("obj"):
            v = s.var("obj")
            s.w("%s.a %s %s" % (v, r.choice(["+=", "-=", "*=", "|=", "^="]), s.small_int()))
        elif s.var("li") and s.var("li"):
            v = s.var("li")
            s.risk = True
            s.w("%s[%s] = %s" % (v, r.randint(-4, 4), s.gi(2)))
        else:
            s.st_assign()

    def st_mut(s):
        r = s.r
        t = r.choice(["li", "li", "li", "ls", "di", "dk", "si", "lo", "lf", "obj"])
        v = s.var(t)
        if v is None or (t in ("lo", "obj") and not s.cls):
            return s.st_assign()
        if t == "li":
            A = [
                (3, lambda: "%s.append(%s)" % (v, s.gi(2))),
                (2, lambda: "%s.extend(%s)" % (v, s.gli(2))),
                (2, lambda: "%s.insert(%s, %s)" % (v, r.randint(-5, 5), s.gi(2))),
                (2, lambda: s.risky("%s.pop()" % v)),
                (2, lambda: s.risky("print(%s.pop(%s))" % (v, r.randint(-3, 3)))),
                (1, lambda: s.risky("%s.remove(%s)" % (v, s.gi(1)))),
                (2, lambda: "%s.sort(%s)" % (v, r.choice(["", "reverse=True", "key=lambda q: -q", "key=abs"]))),
                (1, lambda: "%s.reverse()" % v),
                (1, lambda: "%s.clear()" % v),
                (2, lambda: s.risky("del %s[%s]" % (v, r.randint(-4, 4)))),
                (2, lambda: s.risky("del %s[%s]" % (v, s.slice_of("", 1)[0:][0:] if False else s.slice_part()))),
                (2, lambda: s.risky("%s[%s] = %s" % (v, s.slice_part(), s.gli(1)))),
                (1, lambda: s.risky("print(%s.index(%s))" % (v, s.gi(1)))),
                (1, lambda: "print(%s.count(%s))" % (v, s.gi(1))),
            ]
            s.ch(A)
        elif t == "ls":
            s.ch([(2, lambda: s.w("%s.append(%s)" % (v, s.gs(2)))), (1, lambda: s.w("%s.sort()" % v)),
                  (1, lambda: s.w("%s.extend(%s)" % (v, s.gls(2)))), (1, lambda: s.w("%s.insert(1, %s)" % (v, s.gs(1)))),
                  (1, lambda: (s.risky(""), s.w("%s.remove(%s)" % (v, s.gs(1))))), (1, lambda: s.w("%s.sort(key=len)" % v))])
        elif t == "lf":
            s.ch([(2, lambda: s.w("%s.append(%s)" % (v, s.gf(2)))), (1, lambda: s.w("%s.sort()" % v)),
                  (1, lambda: s.w("%s.sort(reverse=True)" % v)),
                  (1, lambda: (s.risky(""), s.w("%s.remove(%s)" % (v, s.gf(1))))), (1, lambda: s.w("%s.reverse()" % v))])
        elif t == "di":
            A = [
                (3, lambda: s.w("%s[%s] = %s" % (v, s.key(), s.gi(2)))),
                (2, lambda: s.w("print(%s.pop(%s, %s))" % (v, s.key(), s.gi(1)))),
                (1, lambda: (s.risky(""), s.w("print(%s.pop(%s))" % (v, s.key())))),
                (1, lambda: (s.risky(""), s.w("del %s[%s]" % (v, s.key())))),
                (2, lambda: s.w("print(%s.setdefault(%s, %s))" % (v, s.key(), s.gi(1)))),
                (1, lambda: s.w("%s.update(%s)" % (v, s.gdi(2)))),
                (1, lambda: s.w("%s.clear()" % v)),
                (1, lambda: (s.risky(""), s.w("print(%s.popitem())" % v))),
                (1, lambda: s.w("print(%s.get(%s))" % (v, s.key()))),
                (1, lambda: s.w("print(list(%s.items()))" % v)),
                (1, lambda: s.w("print(%s.get(%s, %s))" % (v, s.key(), s.gi(1)))),
                (1, lambda: s.w("%s |= %s" % (v, s.gdi(1)))),
            ]
            s.ch(A)
        elif t == "dk":
            ks = s.ch([(3, lambda: s.gi(1)), (1, lambda: s.small_int()), (1, lambda: s.gf(1) if s.r.random() < 0.5 else "True"),
                       (1, lambda: s.r.choice(["1.0", "0.0", "-0.0", "True", "False", "2.0", "(-1.0)"]))])
            s.ch([(3, lambda: s.w("%s[%s] = %s" % (v, ks, s.gi(2)))),
                  (1, lambda: s.w("print(%s.get(%s, -1))" % (v, ks))),
                  (1, lambda: (s.risky(""), s.w("del %s[%s]" % (v, ks)))),
                  (1, lambda: s.w("print(%s.pop(%s, None))" % (v, ks))),
                  (1, lambda: s.w("print(%s.setdefault(%s, 5))" % (v, ks))),
                  (1, lambda: s.w("print(list(%s.items()))" % v))])
        elif t == "si":
            s.ch([(3, lambda: s.w("%s.add(%s)" % (v, s.gi(2)))), (2, lambda: s.w("%s.discard(%s)" % (v, s.gi(1)))),
                  (1, lambda: (s.risky(""), s.w("%s.remove(%s)" % (v, s.gi(1))))),
                  (1, lambda: s.w("%s.update(%s)" % (v, s.gli(1)))),
                  (1, lambda: s.w("%s %s= %s" % (v, r.choice(["|", "&", "-", "^"]), s.gset(1)))),
                  (1, lambda: s.w("print(len(%s), sorted(%s))" % (v, v))),
                  (1, lambda: s.w("%s.clear()" % v))])
        elif t == "lo":
            s.ch([(3, lambda: s.w("%s.append(%s)" % (v, s.go(2)))), (2, lambda: s.w("%s.sort(%s)" % (v, r.choice(["", "reverse=True"])))),
                  (1, lambda: (s.risky(""), s.w("%s.remove(%s)" % (v, s.go(1))))),
                  (1, lambda: (s.risky(""), s.w("print(%s.index(%s))" % (v, s.go(1))))),
                  (1, lambda: s.w("print(%s.count(%s))" % (v, s.go(1))))])
        elif t == "obj":
            s.ch([(2, lambda: s.w("%s.a = %s" % (v, s.small_int()))), (2, lambda: s.w("%s.b += %s" % (v, s.gs(1)))),
                  (2, lambda: s.w("print(%s.bump(%s))" % (v, s.small_int())))])

    def slice_part(s):
        r = s.r
        a = r.choice(["", str(r.randint(-6, 6))])
        b = r.choice(["", str(r.randint(-6, 6))])
        c = r.choice(["", "", "2", "-1", "-2", "3"])
        return "%s:%s" % (a, b) + (":" + c if c else "")

    def st_unpack(s):
        r = s.r
        c = r.random()
        if c < 0.25:
            t = r.choice(["int", "float", "str"])
            a, b = s.var(t), s.var(t)
            if a and b:
                s.w("%s, %s = %s, %s" % (a, b, b, a))
                return
        if c < 0.45:
            v = s.newvar("int")
            w = s.newvar("int")
            s.risk = True
            s.w("%s, %s = divmod(%s, %s)" % (v, w, s.gi(2), s.gi(1)))
        elif c < 0.6:
            v = s.newvar("int")
            w = s.newvar("li")
            s.risk = True
            s.w("%s, *%s = %s" % (v, w, s.gli(2)))
        elif c < 0.75:
            a, b, c2 = s.newvar("int"), s.newvar("int"), s.newvar("int")
            s.w("%s, %s, %s = %s" % (a, b, c2, s.gti(2)))
        elif c < 0.85:
            v = s.newvar("int")
            w = s.newvar("int")
            s.w("%s = %s = %s" % (v, w, s.gi(2)))
        elif c < 0.93:
            a, b = s.newvar("str"), s.newvar("str")
            s.risk = True
            s.w("%s, *_, %s = %s" % (a, b, s.gs(2)))
        else:
            a, b = s.newvar("int"), s.newvar("str")
            s.w("%s, %s = %s" % (a, b, s.gtm(2)))

    def st_obj(s):
        if not s.cls:
            return s.st_assign()
        r = s.r
        c = r.random()
        if c < 0.4:
            v = s.newvar("obj")
            s.w("%s = %s" % (v, s.new_obj(2)))
        elif c < 0.7 and s.var("obj"):
            v = s.var("obj")
            s.w("print(%s, repr(%s), %s.a, %s.b)" % (v, v, v, v))
        elif c < 0.85:
            v = s.newvar("lo")
            s.w("%s = %s" % (v, s.glo(2)))
        else:
            s.w("print(%s)" % s.glo(2))

    # ---------- compound statements
    def body(s, n=None, loop=False):
        s.ind += 1
        start = len(s.lines)
        if loop:
            s.in_loop += 1
        with s.scope():
            for _ in range(n or s.r.randint(1, 3)):
                s.stmt(simple=s.depth >= 3)
        if loop:
            s.in_loop -= 1
        if len(s.lines) == start:
            s.w("pass")
        s.ind -= 1

    def st_if(s):
        s.w("if %s:" % s.gb(3))
        s.body()
        if s.r.random() < 0.3:
            s.w("elif %s:" % s.gb(2))
            s.body()
        if s.r.random() < 0.5:
            s.w("else:")
            s.body()

    def loop_ctl(s):
        r = s.r
        if r.random() < 0.5:
            s.w("if %s:" % s.gb(2))
            s.w("    %s" % r.choice(["break", "continue", "continue"]))

    def st_for(s):
        r = s.r
        acc = s.var("int")
        k = r.randint(0, 6)
        with s.scope():
            c = r.random()
            if c < 0.3:
                v = s.name("int")
                a, b = str(r.randint(-3, 6)), str(r.randint(-2, 14))
                step = r.choice(["", ", 1", ", 2", ", -1", ", -2", ", 3"])
                hdr = "for %s in range(%s, %s%s):" % (v, a if step else "0", b, step) if r.random() < 0.8 else "for %s in range(%d):" % (v, r.randint(0, 8))
                tv = [(v, "int")]
                s.risk = False
            elif c < 0.5:
                v = s.name("int")
                hdr = "for %s in %s:" % (v, s.gli(2))
                tv = [(v, "int")]
            elif c < 0.62:
                v, w = s.name("int"), s.name("str")
                hdr = "for %s, %s in enumerate(%s%s):" % (v, w, s.gs(1), r.choice(["", ", 1", ", -2"]))
                tv = [(v, "int"), (w, "str")]
            elif c < 0.72:
                v, w = s.name("int"), s.name("int")
                hdr = "for %s, %s in zip(%s, %s):" % (v, w, s.gli(1), s.gli(1))
                tv = [(v, "int"), (w, "int")]
            elif c < 0.82:
                v, w = s.name("str"), s.name("int")
                hdr = "for %s, %s in %s.items():" % (v, w, s.gdi(1))
                tv = [(v, "str"), (w, "int")]
            elif c < 0.9:
                v = s.name("str")
                hdr = "for %s in %s:" % (v, s.gs(2))
                tv = [(v, "str")]
            elif c < 0.95:
                v = s.name("str")
                hdr = "for %s in sorted(%s):" % (v, s.gdi(1))
                tv = [(v, "str")]
            else:
                v = s.name("int")
                hdr = "for %s in reversed(%s):" % (v, s.gli(2))
                tv = [(v, "int")]
            for n_, t_ in tv:
                s.vars[n_] = t_
            s.w(hdr)
            s.ind += 1
            s.in_loop += 1
            if acc and r.random() < 0.7:
                s.w("%s += %s" % (acc, s.small_int() if r.random() < 0.6 else (tv[0][0] if tv[0][1] == "int" else "len(%s)" % tv[0][0])))
            n0 = len(s.lines)
            for _ in range(r.randint(1, 3)):
                s.stmt(simple=s.depth >= 3)
                s.loop_ctl()
            if len(s.lines) == n0:
                s.w("pass")
            s.in_loop -= 1
            s.ind -= 1
        if r.random() < 0.25:
            s.w("else:")
            s.body(1)

    def st_while(s):
        r = s.r
        k = s.name("int")
        s.defs.append(k)
        s.w("%s = %d" % (k, r.randint(0, 3)))
        s.w("while %s < %d:" % (k, r.randint(3, 9)))
        s.ind += 1
        s.in_loop += 1
        s.w("%s += 1" % k)
        with s.scope():
            for _ in range(r.randint(1, 3)):
                s.stmt(simple=s.depth >= 3)
                s.loop_ctl()
        s.in_loop -= 1
        s.ind -= 1
        if r.random() < 0.2:
            s.w("else:")
            s.body(1)

    def raise_stmt(s):
        r = s.r
        c = r.random()
        if c < 0.3:
            s.w("raise %s(%s)" % (r.choice(["ValueError", "KeyError", "IndexError", "ZeroDivisionError", "RuntimeError", "OverflowError"]), r.choice(["", "'m'"])))
        elif c < 0.7:
            s.w("raise %s(%s)" % (r.choice(["MyErr", "SubErr"]), s.small_int()))
        elif c < 0.85:
            s.w("raise MyErr(%s, %s)" % (s.small_int(), s.lit_str()))
        else:
            s.w("raise SubErr")

    def st_try(s):
        r = s.r
        s.w("try:")
        s.ind += 1
        with s.scope():
            n0 = len(s.lines)
            for _ in range(r.randint(1, 2)):
                s.stmt(simple=True)
            if len(s.lines) == n0:
                s.w("pass")
            if r.random() < 0.7:
                s.w("if %s:" % s.gb(2))
                s.ind += 1
                s.raise_stmt()
                s.ind -= 1
            if r.random() < 0.3:
                s.w("%s" % r.choice(["1 // 0", "[][0]", "{}['q']", "int('x')", "[1].remove(2)", "(-1) ** 0.5 if False else float('x')"]))
        s.ind -= 1
        used = False
        for cl in range(r.randint(1, 3)):
            used = True
            cls = r.choice(["SubErr", "MyErr", "ValueError", "ZeroDivisionError", "(KeyError, IndexError)", "Exception", "(MyErr, ValueError)"])
            nm = "ex"
            s.w("except %s as %s:" % (cls, nm))
            s.ind += 1
            c = r.random()
            if c < 0.4:
                s.w("print('caught', type(ex).__name__, ex.args)" if cls in ("SubErr", "MyErr") else "print('caught', type(ex).__name__)")
            elif c < 0.6:
                s.w("print('caught', repr(ex), str(ex))" if cls in ("SubErr", "MyErr") else "print('caught', type(ex).__name__)")
            elif c < 0.75:
                s.w("raise")
            elif c < 0.85:
                s.w("raise MyErr(%s)" % s.small_int())
            else:
                with s.scope():
                    s.stmt(simple=True)
                s.w("print('handled', type(ex).__name__)")
            s.ind -= 1
        if r.random() < 0.3:
            s.w("else:")
            s.body(1)
        if r.random() < 0.5:
            s.w("finally:")
            s.body(1)
        elif not used:
            s.w("finally:")
            s.body(1)
        s.risk = False
        # an uncaught `raise` inside a handler must not leave the program: wrap at the call site
        s.wrap_try_all()

    def wrap_try_all(s):
        """indent everything the try statement emitted (from its `try:` line) inside an outer catch-all"""
        i = len(s.lines) - 1
        base = "    " * s.ind
        while i >= 0 and not (s.lines[i] == base + "try:"):
            i -= 1
        if i < 0:
            return
        body = s.lines[i:]
        del s.lines[i:]
        s.w("try:")
        for ln in body:
            s.lines.append("    " + ln)
        s.w("except Exception as ex2:")
        s.w("    print('outer', type(ex2).__name__)")

    def st_template(s):
        T = [s.t_closure, s.t_lambda, s.t_mutdef, s.t_alias, s.t_tryfin, s.t_gen, s.t_varargs, s.t_defbind,
             s.t_unicode, s.t_numdict, s.t_ties, s.t_forelse, s.t_inplace_alias, s.t_sortkey, s.t_recur, s.t_strmeth,
             s.t_intfloat, s.t_nested_cmp]
        r = s.r.choice(T)
        s.uniq = getattr(s, "uniq", 0) + 1
        r()

    def U(s, p):
        s.n += 1
        return "%s%d" % (p, s.n)

    def t_closure(s):
        mk, g = s.U("mk"), s.U("g")
        c, inc = s.U("c"), s.U("inc")
        s.pre += ["def %s(n):" % mk, "    %s = n" % c, "    def %s(k):" % inc, "        nonlocal %s" % c,
                  "        %s += k" % c, "        return %s" % c, "    return %s" % inc]
        s.w("%s = %s(%s)" % (g, mk, s.small_int()))
        s.w("print(%s(1), %s(%s), %s(0), %s(3))" % (g, g, s.small_int(), g, g))
        s.defs.append(g)

    def t_lambda(s):
        fs = s.U("fs")
        n = s.r.randint(1, 4)
        s.w("%s = [lambda: q for q in range(%d)]" % (fs, n))
        s.w("print([f() for f in %s])" % fs)
        s.w("%s = [lambda x, q=q: x * q + %s for q in range(%d)]" % (fs, s.small_int(), n))
        s.w("print([f(%s) for f in %s])" % (s.small_int(), fs))
        s.defs.append(fs)

    def t_mutdef(s):
        f = s.U("md")
        s.pre += ["def %s(x, acc=[]):" % f, "    acc.append(x)", "    return len(acc), sum(acc)"]
        s.w("print(%s(%s), %s(%s), %s(%s, []))" % (f, s.small_int(), f, s.small_int(), f, s.small_int()))

    def t_alias(s):
        g, h, x = s.U("g"), s.U("h"), s.U("x")
        n = s.r.randint(1, 3)
        s.w("%s = [1, 2]" % x)
        s.w("%s = [%s, %s, [%s]]" % (g, x, x, x))
        s.w("%s[0].append(%s)" % (g, s.small_int()))
        s.w("%s = [[0] * 3 for _ in range(%d)]" % (h, n))
        s.w("%s[0][1] += %s" % (h, s.small_int()))
        s.w("print(%s, %s, %s, %s[0] is %s[1])" % (g, h, x, g, g))
        s.defs += [g, h, x]

    def t_tryfin(s):
        f = s.U("tf")
        r = s.r
        s.pre += ["def %s(x):" % f, "    for q in range(3):", "        try:", "            if x == q:",
                  "                return q", "            if x > 5:", "                raise ValueError(x)",
                  "        except ValueError:", "            return -1",
                  "        finally:", "            print('fin', q)"]
        if r.random() < 0.3:
            s.pre.append("            pass")
        s.pre.append("    return 99")
        s.w("print(%s(%s), %s(%s), %s(%s))" % (f, r.randint(0, 3), f, r.randint(4, 8), f, r.randint(-1, 9)))

    def t_gen(s):
        f = s.U("gen")
        s.pre += ["def %s(n):" % f, "    a, b = 0, 1", "    for _ in range(n):", "        yield a", "        a, b = b, a + b"]
        s.w("print(list(%s(%d)), sum(%s(%d)))" % (f, s.r.randint(0, 12), f, s.r.randint(0, 12)))

    def t_varargs(s):
        f = s.U("va")
        s.pre += ["def %s(a, *args, k=1, **kw):" % f, "    return a * k + len(args) + sum(args) + len(kw)"]
        s.w("print(%s(%s), %s(%s, %s, %s), %s(%s, k=%s), %s(%s, 1, k=2, z=3))" % (
            f, s.small_int(), f, s.small_int(), s.small_int(), s.small_int(), f, s.small_int(), s.small_int(), f, s.small_int()))

    def t_defbind(s):
        x, f = s.U("X"), s.U("db")
        s.pre += ["%s = %s" % (x, s.r.randint(-5, 9)), "def %s(a=%s, b=%s * 2):" % (f, x, x), "    return a + b",
                  "%s = %s + 1" % (x, x)]
        s.w("print(%s(), %s(1), %s(1, 2), %s)" % (f, f, f, x))

    def t_unicode(s):
        v, i, ch = s.var("str") or repr(s.r.choice(STRS)), s.U("i"), s.U("ch")
        s.w("for %s, %s in enumerate(%s):" % (i, ch, v))
        s.w("    print(%s, %s, ord(%s), %s.upper(), %s.lower(), %s.isalpha(), %s.isdigit(), len(%s.encode('utf-8')))" % (i, ch, ch, ch, ch, ch, ch, ch))

    def t_numdict(s):
        d = s.U("nd")
        s.w("%s = {}" % d)
        for _ in range(s.r.randint(2, 5)):
            k = s.r.choice(["1", "1.0", "True", "0", "0.0", "False", "-0.0", "2", "2.0", "(1, 2)", "(1.0, 2)", "'1'", "3", "nan", "inf", "(-1)", "-1.0"])
            if k == "nan" and not s.var("float"):
                k = "1"
            s.w("%s[%s] = %r" % (d, k, s.r.choice(STRS)))
        s.w("print(%s, len(%s))" % (d, d))
        s.defs.append(d)

    def t_ties(s):
        l = s.gls(1)
        s.w("print(max(%s, key=len), min(%s, key=len), sorted(%s, key=len))" % (l, l, l))
        s.risk = True

    def t_forelse(s):
        r = s.r
        i = s.U("i")
        s.w("for %s in range(%d):" % (i, r.randint(0, 5)))
        s.w("    if %s == %d:" % (i, r.randint(0, 5)))
        s.w("        break")
        s.w("else:")
        s.w("    print('no break')")
        s.w("print(%s)" % i if False else "print('after')")

    def t_inplace_alias(s):
        a, b, c = s.U("a"), s.U("b"), s.U("c")
        s.w("%s = %s" % (a, s.gli(1) if False else "[1, 2]"))
        s.w("%s = %s" % (b, a))
        s.w("%s = %s[:]" % (c, a))
        s.w("%s += [%s]" % (b, s.small_int()))
        s.w("%s = %s + [9]" % (c, c))
        s.w("print(%s, %s, %s, %s is %s)" % (a, b, c, a, b))
        s.defs += [a, b, c]

    def t_sortkey(s):
        r = s.r
        v = s.U("pairs")
        s.w("%s = [(%s, %s), (%s, %s), (%s, %s)]" % ((v,) + tuple(x for _ in range(3) for x in (s.small_int(), s.lit_str()))))
        s.w("print(sorted(%s), sorted(%s, key=lambda p: p[1]), max(%s), min(%s, key=lambda p: (p[1], -p[0])))" % (v, v, v, v))
        s.defs.append(v)

    def t_recur(s):
        f = s.U("rec")
        s.pre += ["def %s(n):" % f, "    return 1 if n <= 1 else n * %s(n - 1) %% 1000003" % f]
        s.w("print(%s(%d), %s(%d))" % (f, s.r.randint(0, 25), f, s.r.randint(-3, 25)))

    def t_strmeth(s):
        r = s.r
        v = s.gs(1)
        m = r.choice(["split", "rsplit", "splitlines", "strip", "expandtabs"])
        s.w("print(%s.%s(), %s.%s(%s))" % (v, m, v, r.choice(["find", "rfind", "count", "startswith", "endswith", "index"]) if False else "count", s.gs(1)))

    def t_intfloat(s):
        r = s.r
        a = s.gi(1)
        b = s.gf(1)
        s.w("print(%s == %s, %s < %s, %s >= %s, float(%s) == %s, %s + %s, %s * %s)" % (a, b, a, b, a, b, a, a, a, b, a, b))

    def t_nested_cmp(s):
        s.w("print(%s, %s, %s)" % (s.gtm(1), s.gti(1), "[%s, %s]" % (s.gtm(1), s.gtm(1))))

    # ---------- classes, functions, program
    def gen_class(s):
        r = s.r
        eqv = r.choice(["a", "ab", "isinst"])
        ltv = r.choice(["a", "ab", "neg"])
        hv = "a" if eqv == "a" else r.choice(["a", "ab"])
        le = r.random() < 0.3
        sub = r.random() < 0.4
        out = ["class P:", "    def __init__(self, a, b):", "        self.a = a", "        self.b = b"]
        out.append("    def __eq__(self, o):")
        if eqv == "isinst":
            out += ["        if not isinstance(o, P):", "            return NotImplemented"]
        out.append("        return self.a == o.a" if eqv != "ab" else "        return self.a == o.a and self.b == o.b")
        if eqv == "isinst":
            out[-1] = "        return self.a == o.a and self.b == o.b" if r.random() < 0.5 else "        return self.a == o.a"
        out.append("    def __lt__(self, o):")
        out.append({"a": "        return self.a < o.a", "ab": "        return (self.a, self.b) < (o.a, o.b)",
                    "neg": "        return -self.a < -o.a"}[ltv])
        if le:
            out += ["    def __le__(self, o):", "        return self.a <= o.a"]
        out.append("    def __repr__(self):")
        out.append(r.choice(["        return f\"P({self.a!r}, {self.b!r})\"", "        return \"P<%d:%s>\" % (self.a, self.b)",
                             "        return f'P{self.a}'"]))
        if r.random() < 0.3:
            out += ["    def __str__(self):", "        return f\"<{self.b}:{self.a}>\""]
        out.append("    def __hash__(self):")
        out.append("        return hash(self.a)" if hv == "a" else "        return hash((self.a, self.b))")
        out += ["    def bump(self, k):", "        self.a += k", "        return self.a"]
        if sub:
            out += ["class Q(P):", "    def __init__(self, a, b, c):", "        super().__init__(a, b)", "        self.c = c",
                    "    def __repr__(self):", "        return f\"Q({self.a!r}, {self.b!r}, {self.c!r})\""]
        s.cls = {"le": le, "sub": sub, "eqnot": eqv == "isinst"}
        s.cls_lines = out

    def gen_func(s, idx):
        r = s.r
        name = "fn%d" % idx
        nreq, ndef, star = r.randint(1, 2), r.randint(0, 2), r.random() < 0.3
        ps = ["p%d" % i for i in range(nreq)]
        ds = ["d%d" % i for i in range(ndef)]
        sig = ps + ["%s=%s" % (d, s.small_int() if r.random() < 0.7 else s.lit_int()) for d in ds] + (["*rest"] if star else [])
        sv = (s.vars, s.lines, s.ind, s.defs, s.in_loop, s.depth)
        s.vars = {p: "int" for p in ps + ds}
        s.lines = []
        s.ind = 1
        s.defs = []
        s.in_loop = 0
        s.depth = 3
        if star:
            t = s.newvar("int")
            s.flush()
            s.w("%s = len(rest) + sum(rest)" % t)
            s.w("for q in rest:")
            s.w("    %s += q %% 7" % t)
        raises = False
        for _ in range(r.randint(0, 3)):
            s.stmt(simple=True)
        if r.random() < 0.4:
            raises = True
            s.w("if %s:" % s.gb(2))
            s.ind += 1
            s.raise_stmt()
            s.ind -= 1
        s.risk = False
        s.w("return %s" % s.gi(3))
        raises = raises or s.risk
        s.risk = False
        body = s.lines
        s.vars, s.lines, s.ind, s.defs, s.in_loop, s.depth = sv
        s.pre.append("def %s(%s):" % (name, ", ".join(sig)))
        s.pre += body
        s.funcs.append((name, nreq, ndef, star, raises))

    def program(s):
        r = s.r
        if s.use_cls:
            s.gen_class()
        for i in range(r.randint(1, 3)):
            s.gen_func(i)
        s.vars["inf"] = "float"
        s.vars["nan"] = "float"
        s.vars["nz"] = "float"
        s.lines = ["    inf = 1e308 * 10.0", "    nan = inf - inf", "    nz = -0.0"]
        s.blocks.append((s.lines, ["inf", "nan", "nz"]))
        for t in ["int", "str", "li", "di", "float", "ls", "int", "dk", "si", "lf"] + (["obj", "lo"] if s.cls else []):
            s.lines = []
            s.defs = []
            s.guard(lambda t=t: s.w("%s = %s" % (s.newvar(t), s.expr(t, 2))))
            s.blocks.append((s.lines, s.defs))
        for _ in range(s.nblocks):
            s.lines = []
            s.defs = []
            s.stmt()
            if s.lines:
                s.blocks.append((s.lines, s.defs))
        t = r.random()
        s.tail = None
        if t < 0.06:
            s.tail = ["    raise %s(%r)" % (r.choice(["ValueError", "KeyError", "MyErr", "RuntimeError"]), "end")]
        elif t < 0.12:
            s.tail = ["    sys.exit(%d)" % r.choice([0, 1, 2, 3, 7, 255, 256])]
        elif t < 0.15:
            s.tail = ["    print(1 // 0)"]
        elif t < 0.17:
            s.tail = ["    sys.exit(%r)" % "bye"]
        return s


def line_blocks(g):
    """block index (or None) of every source line of render(g), 1-based list index"""
    src = render(g)
    m = [None]
    n = len(src.splitlines())
    pos = 0
    # rebuild the layout the same way render() does
    head = src.split("def main():\n")[0].count("\n") + 1
    m += [None] * head
    for k, (lines, _d) in enumerate(g.blocks):
        m += [k] * len(lines)
    m += [None] * (n + 5 - len(m) + 1)
    return m


def render(g, upto=None, instrument=False, tail=True):
    out = []
    if g.use_math:
        out.append("import math")
    if g.tail and any("sys." in ln for ln in g.tail):
        out.append("import sys")
    out += ["class MyErr(Exception):", "    pass", "class SubErr(MyErr):", "    pass"]
    out += getattr(g, "cls_lines", [])
    out += g.pre
    out.append("def main():")
    for k, (lines, _d) in enumerate(g.blocks[:upto]):
        if instrument:
            out.append("    _blk(%d)" % k)
        out += lines
    if tail and g.tail and upto is None:
        out += g.tail
    if len(out) and out[-1] == "def main():":
        out.append("    pass")
    out.append("main()")
    return "\n".join(out) + "\n"


PRELUDE = '''import sys as _sys
_BLK = [0]
_OVF = []
def _blk(k):
    _BLK[0] = k
def _ck(x):
    t = type(x)
    if t is int:
        if not -9223372036854775808 <= x <= 9223372036854775807 and not _OVF:
            _OVF.append(_BLK[0])
    elif t is tuple:
        for y in x:
            _ck(y)
    return x
'''


class _Instr(ast.NodeTransformer):
    def _wrap(self, node):
        return ast.copy_location(ast.Call(ast.Name("_ck", ast.Load()), [node], []), node)

    def visit_BinOp(self, node):
        self.generic_visit(node)
        return self._wrap(node)

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        return self._wrap(node)

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "_ck":
            return node
        return self._wrap(node)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        t = node.target
        load = ast.parse(ast.unparse(t), mode="eval").body
        chk = ast.Expr(ast.Call(ast.Name("_ck", ast.Load()), [load], []))
        return [node, ast.copy_location(chk, node)]


def instrumented(src_with_blk):
    assert src_with_blk.endswith("\nmain()\n")
    tree = ast.parse(src_with_blk[:-len("main()\n")])
    tree = _Instr().visit(tree)
    ast.fix_missing_locations(tree)
    body = ast.unparse(tree).rstrip() + "\n"
    body = body + "try:\n    main()\nexcept BaseException:\n    pass\n_sys.stderr.write('OVF %s\\n' % (_OVF[0] if _OVF else -1))\n"
    return PRELUDE + body


def overflow_block(g, timeout=20):
    src = instrumented(render(g, instrument=True))
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, timeout=timeout, text=True, encoding="utf-8",
                           errors="replace")
    except subprocess.TimeoutExpired:
        return "timeout"
    finally:
        os.unlink(path)
    m = re.search(r"OVF (-?\d+)", p.stderr)
    if not m:
        return "crash:" + p.stderr[-300:]
    v = int(m.group(1))
    return None if v < 0 else v


def drop_blocks(g, k):
    """remove block k and every later block that mentions a name defined by a removed block"""
    gone = set(g.blocks[k][1])
    keep = g.blocks[:k]
    for lines, defs in g.blocks[k + 1:]:
        text = "\n".join(lines)
        if any(re.search(r"\b%s\b" % re.escape(n), text) for n in gone):
            gone |= set(defs)
        else:
            keep.append((lines, defs))
    g.blocks = keep


def build(seed, nblocks=16):
    """-> (program, None, None) with every integer inside int64, or (program, None, 'reason') when unusable"""
    g = G(seed, nblocks).program()
    dropped = 0
    for _ in range(12):
        ob = overflow_block(g)
        if ob is None:
            return g, None, None
        if isinstance(ob, str):
            return g, None, ob
        drop_blocks(g, ob)
        dropped += 1
    return g, None, "overflow: too many blocks dropped"


def cpython_run(path, timeout=20):
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, timeout=timeout, text=True, encoding="utf-8",
                           errors="replace")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    return p.returncode, p.stdout, p.stderr


# ------------------------------------------------------------------ runner
HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(HERE)
CMP = os.path.expanduser("~/tools/cmp.sh")


def parse_cmp(text, d):
    """classify one cmp.sh run; returns (kind, detail)"""
    cp = re.search(r"^cpython exit (\d+)", text, re.M)
    cpx = int(cp.group(1)) if cp else -1
    res = {}
    for m in ("g", "d"):
        if re.search(r"^build %s failed" % m, text, re.M):
            log = ""
            try:
                log = open(os.path.join(d, "b_%s.log" % m), encoding="utf-8", errors="replace").read()
            except OSError:
                pass
            res[m] = ("build", log)
            continue
        mm = re.search(r"^%s exit (\d+)" % m, text, re.M)
        if not mm:
            res[m] = ("none", "")
            continue
        code = int(mm.group(1))
        same = re.search(r"^%s same stdout" % m, text, re.M) is not None
        err = ""
        try:
            err = open(os.path.join(d, "%s.err" % m), encoding="utf-8", errors="replace").read()
        except OSError:
            pass
        res[m] = ("run", code, same, err)
    return cpx, res


def classify(cpx, res):
    """-> list of (kind, mode, detail); empty list = clean"""
    out = []
    for m in ("g", "d"):
        r = res[m]
        if r[0] == "build":
            log = r[1].strip()
            last = log.splitlines()[-1] if log else ""
            if re.search(r"not in the subset|refus|not supported|not built|unsupported", log, re.I) and "Traceback" not in log:
                out.append(("refused", m, last[:200]))
            else:
                out.append(("buildcrash", m, last[:300]))
        elif r[0] == "run":
            _, code, same, err = r
            if code == 3 and "AIL limit:" in err:
                out.append(("limit", m, err.strip().splitlines()[-1][:100]))
            elif (code >= 128 or code < 0) and code != cpx:
                out.append(("crash", m, "exit %d %s" % (code, err.strip()[-120:])))
            elif not same:
                if "integer overflow" in err and code == 1:
                    out.append(("overflow", m, ""))
                else:
                    out.append(("stdout", m, "exit %d vs cpython %d" % (code, cpx)))
            elif code != cpx:
                out.append(("exit", m, "exit %d vs cpython %d: %s" % (code, cpx, err.strip()[-120:])))
            if "internal error" in err.lower() and not out:
                out.append(("internal", m, err.strip()[-200:]))
    return out


def run_cmp(path):
    p = subprocess.run(["bash", CMP, path, WT], capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = p.stdout
    m = re.search(r"^dir (\S+)", text, re.M)
    d = m.group(1) if m else ""
    cpx, res = parse_cmp(text, d)
    return cpx, res, d, text


def refusal_block(g, d):
    """block index named by the location of a refusal in the build logs, or None"""
    m = line_blocks(g)
    for mode in ("d", "g"):
        try:
            log = open(os.path.join(d, "b_%s.log" % mode), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        rows = [ln for ln in log.splitlines() if re.match(r"(note: )?p\.ail:(\d+)", ln)]
        rows.sort(key=lambda ln: ln.startswith("note"))
        for ln in rows:
            ln_no = int(re.match(r"(?:note: )?p\.ail:(\d+)", ln).group(1))
            if ln_no < len(m) and m[ln_no] is not None:
                return m[ln_no]
        # no location: look for a quoted word of the message in the blocks
        words = re.findall(r"\b([A-Z][A-Za-z]+Error|[A-Z][A-Za-z]+Exception|[A-Z][a-z]+Warning)\b", log)
        for w in words:
            for k, (lines, _d) in enumerate(g.blocks):
                if k and re.search(r"\b%s\b" % w, "\n".join(lines)):
                    return k
    return None


def one(seed, out, nblocks):
    g, upto, ob = build(seed, nblocks)
    rec = {"seed": seed, "kinds": [], "ob": ob}
    upto = None
    if ob is not None:
        rec["kinds"].append(("skip" if ob.startswith("overflow") else "genbug", "-", ob))
        return rec
    if len(g.blocks) < 12:
        rec["kinds"].append(("skip", "-", "too few blocks"))
        return rec
    path = os.path.join(out, "s%d.py" % seed)
    repairs = 0
    while True:
        src = render(g)
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        cpx, res, d, text = run_cmp(path)
        ks = classify(cpx, res)
        if cpx != 0 and not g.tail:
            rec["kinds"] = [("genbug", "-", "cpython exit %d" % cpx)]
            return rec
        if not any(k[0] == "refused" for k in ks) or repairs >= 3:
            break
        k = refusal_block(g, d)
        if k is None or k == 0:
            break
        try:
            lg = open(os.path.join(d, "b_d.log"), encoding="utf-8", errors="replace").read()
        except OSError:
            lg = ""
        try:
            lg += open(os.path.join(d, "b_g.log"), encoding="utf-8", errors="replace").read()
        except OSError:
            pass
        msg = [re.sub(r"^.*general path: ", "G: ", ln) for ln in lg.splitlines() if "not in the subset" in ln or "p.ail" in ln][:1]
        with open(os.path.join(out, "refusals.log"), "a", encoding="utf-8") as rl:
            rl.write("== seed %d block %d: %s\n%s\n" % (seed, k, (msg or [""])[0][:400], "\n".join(g.blocks[k][0][:14])))
        shutil.rmtree(d, ignore_errors=True)
        drop_blocks(g, k)
        repairs += 1
        for _ in range(12):
            ob = overflow_block(g)
            if ob is None or isinstance(ob, str):
                break
            drop_blocks(g, ob)
        if len(g.blocks) < 10 or isinstance(ob, str):
            rec["kinds"] = [("skip", "-", "too little left after refusal repair")]
            return rec
    rec["repairs"] = repairs
    rec["cpx"] = cpx
    rec["kinds"] = ks
    bad = [k for k in ks if k[0] not in ("refused",)]
    if bad:
        shutil.copy(path, os.path.join(out, "find_%d.py" % seed))
        with open(os.path.join(out, "find_%d.txt" % seed), "w", encoding="utf-8") as f:
            f.write(text)
    if d and not bad:
        shutil.rmtree(d, ignore_errors=True)
    elif d:
        rec["dir"] = d
    if not bad:
        os.unlink(path)
    return rec


def run_many(args):
    os.makedirs(args.out, exist_ok=True)
    seeds = list(range(args.start, args.start + args.count))
    stats = {}
    total = 0
    t0 = time.time()
    log = open(os.path.join(args.out, "results.log"), "a", encoding="utf-8")

    def job(sd):
        try:
            return one(sd, args.out, args.blocks)
        except Exception as e:  # a generator bug must not stop the run
            return {"seed": sd, "kinds": [("genbug", "-", "exception %r" % e)], "ob": None}
    with ThreadPoolExecutor(args.j) as ex:
        for rec in ex.map(job, seeds):
            total += 1
            ks = rec["kinds"] or [("clean", "-", "")]
            for kd in ks:
                key = kd[0]
                if kd[0] in ("refused", "buildcrash"):
                    key += ":" + re.sub(r"\d+", "N", kd[2])[:90]
                stats[key] = stats.get(key, 0) + 1
            log.write("%d %s\n" % (rec["seed"], ks))
            log.flush()
            if any(k[0] not in ("refused", "clean", "skip") for k in ks):
                print("seed %d: %s" % (rec["seed"], [k for k in ks if k[0] != "refused"]), flush=True)
    print("programs: %d in %.0fs" % (total, time.time() - t0))
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print("%6d %s" % (v, k))


# ------------------------------------------------------------------ minimizer
def ail_differs(src, mode, tmp, orig_cpx):
    """True if the program builds with `mode` (g|d) and prints/exits differently from CPython.
    Every call works in a fresh directory below `tmp`: reusing one directory made the second and later
    builds see leftovers of the first and report "no difference" (the shrinker never shrank)."""
    tmp = tempfile.mkdtemp(prefix="t", dir=tmp)
    try:
        return _ail_differs(src, mode, tmp, orig_cpx)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _ail_differs(src, mode, tmp, orig_cpx):
    p = os.path.join(tmp, "m.py")
    with open(p, "w", encoding="utf-8") as f:
        f.write(src)
    cpx, so, se = cpython_run(p)
    # a candidate whose output depends on an address or on run order is not a finding (deleting a
    # __repr__ leaves "<P object at 0x...>", which differs from any other run)
    if " at 0x" in so or cpython_run(p)[1] != so:
        return False
    if cpx != orig_cpx or "NameError" in se or "TypeError" in se or "SyntaxError" in se or "UnboundLocal" in se or "AttributeError" in se:
        return False
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
    env.pop("AIL_UNIFIED_FORCE", None)
    if mode == "g":
        env["AIL_UNIFIED_FORCE"] = "1"
    exe = os.path.join(tmp, "m_exe")
    c = subprocess.run([sys.executable, os.path.join(WT, "AIL_CURRENT", "ail_chatgpt.py"), "compile", p, "--syntax", "python",
                        "-o", exe], capture_output=True, text=True, env=env, errors="replace")
    if c.returncode != 0:
        return False
    try:
        r = subprocess.run([exe], capture_output=True, timeout=20, env=env)
    except subprocess.TimeoutExpired:
        return True
    return r.stdout.decode("utf-8", "replace") != so or r.returncode != cpx


def stmt_lists(tree):
    """every list of statements (bodies) in the tree"""
    for node in ast.walk(tree):
        for fld in ("body", "orelse", "finalbody"):
            b = getattr(node, fld, None)
            if isinstance(b, list) and b and isinstance(b[0], ast.stmt):
                yield node, fld


def minimize(path, mode, keep=None):
    src = open(path, encoding="utf-8").read()
    tmp = tempfile.mkdtemp(prefix="dfmin")
    cp0, _, _ = cpython_run(path)
    if not ail_differs(src, mode, tmp, cp0):
        print("does not differ in mode %s" % mode)
        return src
    tests = 0
    changed = True
    cur = src
    while changed:
        changed = False
        tree = ast.parse(cur)
        sites = [(n, f, i) for n, f in stmt_lists(tree) for i in range(len(getattr(n, f)))]
        # try bigger deletions first: from the end of main's body
        sites.sort(key=lambda s: -len(ast.unparse(getattr(s[0], s[1])[s[2]])))
        for n, f, i in sites:
            t2 = ast.parse(cur)
            lists = [(n2, f2) for n2, f2 in stmt_lists(t2)]
            # locate the same site by position in the walk order
            idx = [(a.__class__, b) for a, b in stmt_lists(tree)].index((n.__class__, f)) if False else None
            tree_sites = [(a, b) for a, b in stmt_lists(tree)]
            k = tree_sites.index((n, f))
            n2, f2 = lists[k]
            body = getattr(n2, f2)
            if i >= len(body):
                continue
            if isinstance(body[i], (ast.FunctionDef, ast.ClassDef)) and body[i].name in ("main",):
                continue
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                continue                      # already as small as a body gets (else: endless Pass -> Pass)
            new = body[:i] + body[i + 1:]
            if not new:
                if f2 == "body":
                    new = [ast.Pass()]
                else:
                    new = []
            setattr(n2, f2, new)
            cand = ast.unparse(ast.fix_missing_locations(t2)) + "\n"
            tests += 1
            if ail_differs(cand, mode, tmp, cp0):
                cur = cand
                changed = True
                if keep:
                    with open(keep, "w", encoding="utf-8") as kf:
                        kf.write(cur)
                print("  shrunk to %d lines (%d tests)" % (cur.count("\n"), tests), file=sys.stderr, flush=True)
                break
    shutil.rmtree(tmp, ignore_errors=True)
    return cur


def main_cli():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, help="print the program of this seed")
    ap.add_argument("--blocks", type=int, default=16, help="random statements per program")
    ap.add_argument("--check", action="store_true", help="with --seed: run under CPython only (generator self-test)")
    ap.add_argument("--run", action="store_true", help="run seeds --start..--start+--count-1 through cmp.sh")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("-j", type=int, default=2)
    ap.add_argument("--out", default="/tmp/difffuzz")
    ap.add_argument("--minimize", help="shrink this program (it must differ from CPython)")
    ap.add_argument("--keep", help="with --minimize: also write the current smallest program to this file")
    ap.add_argument("--mode", default="d", choices=["d", "g"], help="build used by --minimize (d default, g general)")
    a = ap.parse_args()
    if a.minimize:
        sys.stdout.write(minimize(a.minimize, a.mode, a.keep))
    elif a.run:
        run_many(a)
    elif a.seed is not None:
        g, upto, ob = build(a.seed, a.blocks)
        if a.check:
            if ob is not None:
                print("GENBUG" if not ob.startswith("overflow") else "SKIP", ob)
                return 1
            src = render(g)
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(src)
            rc, so, se = cpython_run(f.name)
            os.unlink(f.name)
            expected = bool(g.tail)
            if rc != 0 and not expected:
                print("GENBUG exit %d: %s" % (rc, se.strip()[-300:]))
                return 1
            print("ok exit=%d blocks=%d lines=%d" % (rc, len(g.blocks), src.count("\n")))
        else:
            sys.stdout.write(render(g))
    else:
        ap.print_help()


if __name__ == "__main__":
    sys.exit(main_cli() or 0)
