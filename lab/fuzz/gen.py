#!/usr/bin/env python3
"""Seeded random program generator for the AIL differential fuzz lab (stdlib only).

    python3 gen.py SEED            # print the program for SEED
    python3 gen.py SEED -o f.py    # write it

The same seed always gives the same program. Programs are typed Python (annotations everywhere,
unique variable names, one type per name) aimed at the Python surface AIL accepts. They avoid the
declared differences: sets are only observed through sorted() or order-free reductions, nothing
prints a list or a tuple, and OverflowError is never caught (a 64-bit overflow ends the program,
which run.py classifies separately from a real difference).
"""
import argparse
import random
import sys

CATCH = ['ValueError', 'KeyError', 'IndexError', 'ZeroDivisionError']
WORDS = ['ab', 'abc', 'hello', 'x', 'Zed', ' pad ', 'a,b,c', 'café', '日本', 'AbCd', '12', '-7', '3.5', 'q q']
BWORDS = ['ab', 'abc', 'hello', 'x', 'Zed', 'a,b', '12']
FLOATS = ['0.5', '1.25', '3.0', '0.1', '2.5e-3', '1e10', '7.0', '0.3', '100.75', '1e-7', '123456.789']
EDGE_INTS = ['0', '1', '-1', '2', '255', '4611686018427387904', '3037000499', '9223372036854775807', '-9223372036854775807']
DEFAULT = {'int': '0', 'float': '0.0', 'str': '""', 'bytes': 'b""', 'bool': 'False',
           'li': '[]', 'di': '{}', 'si': 'set()', 'ls': '[]'}
ANNOT = {'int': 'int', 'float': 'float', 'str': 'str', 'bytes': 'bytes', 'bool': 'bool',
         'li': 'list[int]', 'di': 'dict[str, int]', 'si': 'set[int]', 'ls': 'list[str]'}


class Gen(object):
    def __init__(self, seed, off=()):
        self.off = set(off)   # feature switches: 'alias' (ys = xs mutation), 'listeq' (xs == ys), 'stridx' (s[i] with an index that may be out of range)
        self.r = random.Random(seed)
        self.n = 0
        self.risk = set()
        self.funcs = []     # (name, kind) kind: 'ii' int,int->int  'rec' int,int->int  'li' list[int]->int  'pt' Pt,int->int
        self.has_pt = False
        self.lazy = 0       # >0 inside the right operand of and/or: AIL builds some calls only unconditionally
        self.prot = set()   # loop variables and counters: never reassigned

    # ---- helpers -------------------------------------------------------------------------
    def k(self, lo, hi):
        return self.r.randint(lo, hi)

    def p(self, x):
        return self.r.random() < x

    def fresh(self, base='v'):
        self.n += 1
        return '%s%d' % (base, self.n)

    def of(self, env, ty):
        return [n for n, t in env.items() if t == ty]

    def lit_str(self):
        return repr(self.r.choice(WORDS))

    def lit_bytes(self):
        return 'b"%s"' % self.r.choice(BWORDS)

    # ---- expressions ----------------------------------------------------------------------
    def iexpr(self, env, d=2):
        r = self.r.random()
        ints = self.of(env, 'int')
        if d <= 0 or r < 0.15:
            if ints and self.p(0.6):
                return self.r.choice(ints)
            if self.p(0.12):
                return self.r.choice(EDGE_INTS)
            return str(self.k(-9, 99))
        a = self.iexpr(env, d - 1)
        b = self.iexpr(env, d - 1)
        if r < 0.40:
            return '(%s %s %s)' % (a, self.r.choice(['+', '-', '*', '+', '-']), b)
        if r < 0.48:
            self.risk.add('ZeroDivisionError')
            return '(%s %s %s)' % (a, self.r.choice(['//', '%']), self.r.choice([b, str(self.k(1, 9)), str(-self.k(1, 9))]))
        if r < 0.53:
            return '(%s %s (abs(%s) + 1))' % (a, self.r.choice(['//', '%']), b)
        if r < 0.58:
            return '(%s %s %s)' % (a, self.r.choice(['&', '|', '^']), b)
        if r < 0.62:
            return '(%s %s %d)' % (a, self.r.choice(['<<', '>>']), self.k(0, 12))
        if r < 0.66:
            return self.r.choice(['abs(%s)', '(-%s)', '(~%s)']) % a
        if r < 0.70:
            return '%s(%s, %s)' % (self.r.choice(['min', 'max']), a, b)
        if r < 0.74:
            return '(%s ** %d)' % (a, self.k(0, 3))
        if r < 0.80:
            return self.lenexpr(env) or a
        if r < 0.86:
            return self.listint(env) or b
        if r < 0.90:
            return self.strint(env) or a
        if r < 0.93:
            f = self.fexpr(env, 1)
            return self.r.choice(['int(%s)', 'round(%s)']) % f
        if r < 0.96 and self.funcs and not self.lazy:
            return self.call(env)
        return a

    def call(self, env):
        name, kind = self.r.choice(self.funcs)
        self.risk.update(CATCH)   # a helper may raise anything the generator can
        if kind in ('ii', 'rec'):
            n = self.k(0, 11) if kind == 'rec' else self.iexpr(env, 1)
            return '%s(%s, %s)' % (name, n, self.iexpr(env, 1))
        if kind == 'li':
            xs = self.of(env, 'li')
            return '%s(%s)' % (name, self.r.choice(xs)) if xs else '0'
        return '0'

    def lenexpr(self, env):
        cands = [('str', 'len(%s)'), ('bytes', 'len(%s)'), ('li', 'len(%s)'), ('di', 'len(%s)'), ('si', 'len(%s)'), ('ls', 'len(%s)')]
        self.r.shuffle(cands)
        for ty, fmt in cands:
            v = self.of(env, ty)
            if v:
                return fmt % self.r.choice(v)
        return None

    def listint(self, env):
        if self.lazy:
            return None
        xs = self.of(env, 'li')
        if not xs:
            return None
        x = self.r.choice(xs)
        r = self.r.random()
        if r < 0.25:
            self.risk.add('IndexError')
            return '%s[%s]' % (x, self.r.choice([str(self.k(-3, 4)), self.iexpr(env, 1)]))
        if r < 0.45:
            return 'sum(%s)' % x
        if r < 0.55:
            self.risk.add('ValueError')
            return '%s(%s)' % (self.r.choice(['min', 'max']), x)
        if r < 0.70:
            return '%s.count(%s)' % (x, self.iexpr(env, 1))
        if r < 0.80:
            self.risk.add('ValueError')
            return '%s.index(%s)' % (x, self.iexpr(env, 1))
        if r < 0.90:
            self.risk.add('IndexError')
            return '%s.pop()' % x
        di = self.of(env, 'di')
        if di:
            return '%s.get(%s, %d)' % (self.r.choice(di), self.sexpr(env, 1), self.k(-2, 5))
        return 'sum(%s)' % x

    def strint(self, env):
        if self.lazy:
            return None
        r = self.r.random()
        s = self.sexpr(env, 1)
        if r < 0.25:
            return '%s.find(%s)' % (s, self.r.choice([self.lit_str(), self.sexpr(env, 1)]))
        if r < 0.45:
            return '%s.count(%s)' % (s, repr(self.r.choice(['a', 'b', 'l', ' ', 'ab'])))
        if r < 0.65:
            self.risk.add('ValueError')
            return 'int(%s)' % self.r.choice([self.lit_str(), s, 'str(%s)' % self.iexpr(env, 1)])
        if r < 0.80 and 'stridx' not in self.off:
            self.risk.add('IndexError')
            return 'ord(%s[%s])' % (s, self.k(0, 3))
        bs = self.of(env, 'bytes')
        if bs:
            self.risk.add('IndexError')
            return '%s[%d]' % (self.r.choice(bs), self.k(0, 3))
        return 'len(%s)' % s

    def fexpr(self, env, d=2):
        r = self.r.random()
        fl = self.of(env, 'float')
        if d <= 0 or r < 0.2:
            if fl and self.p(0.6):
                return self.r.choice(fl)
            return self.r.choice(FLOATS)
        a = self.fexpr(env, d - 1)
        b = self.fexpr(env, d - 1)
        if r < 0.50:
            return '(%s %s %s)' % (a, self.r.choice(['+', '-', '*']), b)
        if r < 0.60:
            return '(%s / (abs(%s) + 1.0))' % (a, b)
        if r < 0.66:
            self.risk.add('ZeroDivisionError')
            return '(%s / %s)' % (a, self.iexpr(env, 1))
        if r < 0.74:
            return 'float(%s)' % self.iexpr(env, 1)
        if r < 0.80:
            return '(abs(%s) ** 0.5)' % a
        if r < 0.86:
            return '%s(%s, %s)' % (self.r.choice(['min', 'max']), a, b)
        if r < 0.90:
            return 'abs(%s)' % a
        if r < 0.94:
            return '(%s %% %s)' % (a, self.r.choice(['2.5', '7.0', '0.75']))
        if r < 0.97:
            return '(%s // %s)' % (a, self.r.choice(['2.5', '3.0']))
        return '(%s / %s)' % (self.iexpr(env, 1), self.r.choice(['4', '3', '8']))

    def sexpr(self, env, d=2):
        r = self.r.random()
        ss = self.of(env, 'str')
        if d <= 0 or r < 0.2:
            if ss and self.p(0.6):
                return self.r.choice(ss)
            return self.lit_str()
        a = self.sexpr(env, d - 1)
        if r < 0.32:
            return '(%s + %s)' % (a, self.sexpr(env, d - 1))
        if r < 0.38:
            return '(%s * %d)' % (a, self.k(0, 3))
        if r < 0.48:
            return '%s[%s:%s]' % (a, self.r.choice(['', '1', '-2', '0']), self.r.choice(['', '2', '-1', '4']))
        if r < 0.56:
            return '%s.%s()' % (a, self.r.choice(['upper', 'lower', 'strip', 'lstrip', 'rstrip']))
        if r < 0.62:
            return '%s.replace(%s, %s)' % (a, repr(self.r.choice(['a', 'l', ' '])), repr(self.r.choice(['', 'XY', '-'])))
        if r < 0.68:
            return 'str(%s)' % self.iexpr(env, 1)
        if r < 0.72:
            return 'str(%s)' % self.fexpr(env, 1)
        if r < 0.82:
            return self.fstring(env)
        if r < 0.86:
            return self.fmtpct(env)
        if r < 0.90:
            ls = self.of(env, 'ls')
            if ls:
                return '%s.join(%s)' % (repr(self.r.choice([',', '-', ''])), self.r.choice(ls))
            return '%s.join(%s.split(%s))' % (repr('-'), a, repr(self.r.choice(['a', ' ', ','])))
        if r < 0.94:
            bs = self.of(env, 'bytes')
            src = self.r.choice(bs) if bs else self.lit_bytes()
            return '%s.decode()' % src
        if r < 0.97 and 'stridx' not in self.off:
            self.risk.add('IndexError')
            return '%s[%s]' % (a, self.k(0, 3))
        return '%s.upper()' % a

    def fmtpct(self, env):
        return '(%s %% %s)' % (self.r.choice(['"%d"', '"<%5d>"', '"%03d"', '"%-4d|"']), self.iexpr(env, 1))

    def fstring(self, env):
        parts = []
        for _ in range(self.k(1, 3)):
            r = self.r.random()
            if r < 0.3:
                parts.append('{%s%s}' % (self.iexpr(env, 1), self.r.choice(['', ':d', ':>6', ':<4', ':05d', ':^7', ':3d'])))
            elif r < 0.6:
                parts.append('{%s%s}' % (self.fexpr(env, 1), self.r.choice(['', ':.2f', ':8.3f', ':.0f', ':>10.1f', ':.3f'])))
            elif r < 0.8:
                parts.append('{%s%s}' % (self.simple_str(env), self.r.choice(['', ':>8', ':<6', ':^9'])))
            else:
                parts.append(self.r.choice(['-', ' = ', '/', '#']))
        return "f'%s'" % ''.join(parts)

    def simple_str(self, env):
        ss = self.of(env, 'str')
        if ss and self.p(0.6):
            return self.r.choice(ss)
        return repr(self.r.choice([w for w in WORDS if "'" not in w]))

    def bexpr(self, env, d=1):
        bs = self.of(env, 'bytes')
        base = self.r.choice(bs) if bs and self.p(0.6) else self.lit_bytes()
        r = self.r.random()
        if d <= 0 or r < 0.3:
            return base
        if r < 0.55:
            return '(%s + %s)' % (base, self.bexpr(env, d - 1))
        if r < 0.8:
            return '%s[%s:%s]' % (base, self.r.choice(['', '1', '-2']), self.r.choice(['', '2', '-1']))
        return '(%s * %d)' % (base, self.k(0, 3))

    def cond(self, env, d=2):
        r = self.r.random()
        if d > 0 and r < 0.2:
            left = self.cond(env, d - 1)
            self.lazy += 1
            right = self.cond(env, d - 1)
            self.lazy -= 1
            return '(%s %s %s)' % (left, self.r.choice(['and', 'or']), right)
        if d > 0 and r < 0.27:
            return '(not %s)' % self.cond(env, d - 1)
        if r < 0.55:
            return '(%s %s %s)' % (self.iexpr(env, 1), self.r.choice(['<', '<=', '==', '!=', '>', '>=']), self.iexpr(env, 1))
        if r < 0.65:
            return '(%s %s %s)' % (self.fexpr(env, 1), self.r.choice(['<', '<=', '==', '>']), self.fexpr(env, 1))
        if r < 0.75:
            return '(%s %s %s)' % (self.sexpr(env, 1), self.r.choice(['<', '==', '!=', '>=']), self.sexpr(env, 1))
        if r < 0.82:
            return '(%s in %s)' % (self.simple_str(env), self.sexpr(env, 1))
        if r < 0.88:
            return '(%s.%s(%s))' % (self.sexpr(env, 1), self.r.choice(['startswith', 'endswith']), repr(self.r.choice(['a', 'he', 'd', ' '])))
        if r < 0.92:
            return '%s.%s()' % (self.simple_str(env), self.r.choice(['isdigit', 'isalpha', 'isupper', 'islower', 'isspace']))
        si = self.of(env, 'si')
        di = self.of(env, 'di')
        if si and r < 0.96:
            return '(%s in %s)' % (self.iexpr(env, 1), self.r.choice(si))
        if di:
            return '(%s in %s)' % (self.simple_str(env), self.r.choice(di))
        return '(%s > 3)' % self.iexpr(env, 1)

    # ---- statements -----------------------------------------------------------------------
    def new_value(self, env, ty):
        if ty == 'int':
            return self.iexpr(env, 2)
        if ty == 'float':
            return self.fexpr(env, 2)
        if ty == 'str':
            return self.sexpr(env, 2)
        if ty == 'bytes':
            return self.bexpr(env, 1)
        if ty == 'bool':
            return self.cond(env, 1)
        if ty == 'li':
            r = self.r.random()
            xs = self.of(env, 'li')
            if r < 0.5:
                return '[%s]' % ', '.join(self.iexpr(env, 1) for _ in range(self.k(0, 5)))
            if r < 0.65:
                return '[%d] * %d' % (self.k(-3, 3), self.k(0, 5))
            if r < 0.8:
                return 'list(range(%d, %d, %d))' % (self.k(-3, 3), self.k(4, 12), self.k(1, 3))
            if r < 0.9:
                v = self.fresh('c')
                return '[%s for %s in range(%d) if %s %% 2 == %d]' % (
                    self.iexpr({**env, v: 'int'}, 1), v, self.k(0, 8), v, self.k(0, 1))
            if xs:
                return 'sorted(%s)' % self.r.choice(xs)
            return '[1, 2, 3]'
        if ty == 'ls':
            if self.p(0.5):
                return '[%s]' % ', '.join(self.simple_str(env) for _ in range(self.k(0, 4)))
            return '%s.split(%s)' % (self.sexpr(env, 1), repr(self.r.choice([',', ' ', 'a'])))
        if ty == 'di':
            return '{%s}' % ', '.join('%s: %s' % (repr(self.r.choice(['a', 'b', 'c', 'dd', 'e'])), self.iexpr(env, 1)) for _ in range(self.k(0, 4)))
        if ty == 'si':
            r = self.r.random()
            if r < 0.5:
                return '{%s}' % ', '.join(str(self.k(-5, 12)) for _ in range(self.k(1, 6)))
            xs = self.of(env, 'li')
            if xs:
                return 'set(%s)' % self.r.choice(xs)
            return 'set()'
        raise AssertionError(ty)

    def define(self, env, ty=None):
        ty = ty or self.r.choice(['int'] * 4 + ['float'] * 2 + ['str'] * 3 + ['bytes', 'bool'] + ['li'] * 3 + ['di', 'si', 'ls'])
        self.risk = set()
        if ty == 'di':
            name = self.fresh()
            env[name] = ty
            return ['%s: dict[str, int] = {}' % name] + ['%s[%r] = %d' % (name, self.r.choice(['a', 'b', 'c', 'dd', 'e']), self.k(-9, 99))
                                                         for _ in range(self.k(0, 4))]
        val = self.new_value(env, ty)
        name = self.fresh()
        risk = self.risk
        env[name] = ty
        decl = '%s: %s = %s' % (name, ANNOT[ty], val)
        return self.guard([decl], risk, pre=['%s: %s = %s' % (name, ANNOT[ty], DEFAULT[ty])] if risk else None,
                          assign=(name, val))

    def guard(self, lines, risk, pre=None, assign=None):
        """Wrap risky statements in try/except most of the time; a bare one may end the program."""
        risk = sorted(risk)
        if not risk or self.p(0.06):
            return lines
        if assign:
            lines = ['%s = %s' % assign]
        kinds = risk if len(risk) == 1 else risk
        head = kinds[0] if len(kinds) == 1 else '(%s)' % ', '.join(kinds)
        out = (pre or []) + ['try:'] + ['    ' + l for l in lines] + ['except %s:' % head, '    print(%d)' % self.k(-99, -1)]
        if self.p(0.2):
            out += ['finally:', '    print(%d)' % self.k(100, 199)]
        return out

    def block(self, env, depth, budget, loops=0, ind='    '):
        env = dict(env)
        out = []
        for _ in range(self.k(1, budget)):
            for l in self.stmt(env, depth, loops):
                out.append(ind + l)
        return out

    def show(self, env):
        self.risk = set()
        r = self.r.random()
        if r < 0.3:
            e = 'print(%s)' % self.iexpr(env, 2)
        elif r < 0.5:
            e = 'print(%s)' % self.fexpr(env, 2)
        elif r < 0.7:
            e = 'print(%s)' % self.sexpr(env, 2)
        elif r < 0.78:
            e = 'print(%s)' % self.cond(env, 2)
        elif r < 0.83:
            e = 'print(%s.decode())' % self.bexpr(env, 1)
        else:
            e = 'print(%s)' % ', '.join(self.r.choice([self.iexpr, self.fexpr, self.sexpr, self.cond])(env, 1) for _ in range(self.k(2, 3)))
        return self.guard([e], self.risk)

    def stmt(self, env, depth, loops):
        r = self.r.random()
        if r < 0.20:
            return self.define(env)
        if r < 0.38:
            return self.show(env)
        if r < 0.50:
            return self.mutate(env)
        if r < 0.55 and self.of(env, 'li') and 'alias' not in self.off:
            return self.alias(env)
        if r < 0.60:
            return self.reassign(env)
        if r < 0.64:
            return self.exc_stmt(env)
        if depth < 3:
            if r < 0.72:
                return self.if_stmt(env, depth, loops)
            if r < 0.80:
                return self.for_stmt(env, depth, loops)
            if r < 0.85:
                return self.while_stmt(env, depth, loops)
            if r < 0.90:
                return self.try_stmt(env, depth, loops)
        if r < 0.93 and loops:
            self.risk = set()
            return ['if %s:' % self.cond(env, 1), '    %s' % self.r.choice(['break', 'continue'])]
        if r < 0.96 and self.has_pt:
            return self.pt_stmt(env)
        return self.show(env)

    def reassign(self, env):
        names = [n for n in env if env[n] in ('int', 'float', 'str', 'bytes', 'bool') and n not in self.prot]
        if not names:
            return self.define(env)
        n = self.r.choice(names)
        ty = env[n]
        self.risk = set()
        if ty == 'int' and self.p(0.5):
            line = '%s %s %s' % (n, self.r.choice(['+=', '-=', '*=', '//=', '%=', '|=', '&=', '^=', '<<=', '>>=']),
                                 self.iexpr(env, 1))
            op = line.split()[1]
            if op in ('//=', '%='):
                line = '%s %s (abs(%s) + 1)' % (n, op, self.iexpr(env, 1))
            elif op in ('<<=', '>>='):
                line = '%s %s %d' % (n, op, self.k(0, 9))
        elif ty == 'float' and self.p(0.5):
            line = '%s %s %s' % (n, self.r.choice(['+=', '-=', '*=']), self.fexpr(env, 1))
        elif ty == 'str' and self.p(0.4):
            line = '%s += %s' % (n, self.sexpr(env, 1))
        else:
            line = '%s = %s' % (n, self.new_value(env, ty))
        return self.guard([line], self.risk)

    def mutate(self, env):
        self.risk = set()
        kinds = [k for k in ('li', 'di', 'si', 'ls') if self.of(env, k)]
        if not kinds:
            return self.define(env, 'li')
        kind = self.r.choice(kinds)
        x = self.r.choice(self.of(env, kind))
        r = self.r.random()
        if kind == 'li':
            if r < 0.2:
                l = '%s.append(%s)' % (x, self.iexpr(env, 1))
            elif r < 0.3:
                l = '%s.extend(%s)' % (x, self.extarg(env))
            elif r < 0.4:
                self.risk.add('IndexError')
                l = '%s.pop()' % x
            elif r < 0.5:
                l = '%s.insert(%s, %s)' % (x, self.k(-2, 3), self.iexpr(env, 1))
            elif r < 0.6:
                l = '%s.sort(%s)' % (x, self.r.choice(['', 'reverse=True']))
            elif r < 0.65:
                l = '%s.sort(key=lambda q: (-q, q))' % x
            elif r < 0.7:
                l = '%s.reverse()' % x
            elif r < 0.8:
                self.risk.add('IndexError')
                l = '%s[%s] = %s' % (x, self.k(-3, 4), self.iexpr(env, 1))
            elif r < 0.85:
                self.risk.add('IndexError')
                l = 'del %s[%s]' % (x, self.k(-2, 3))
            elif r < 0.9:
                self.risk.add('ValueError')
                l = '%s.remove(%s)' % (x, self.iexpr(env, 1))
            else:
                l = '%s += %s' % (x, self.extarg(env))
        elif kind == 'ls':
            l = self.r.choice(['%s.append(%s)' % (x, self.sexpr(env, 1)), '%s.sort()' % x, '%s.reverse()' % x])
        elif kind == 'di':
            if r < 0.4:
                l = '%s[%s] = %s' % (x, self.simple_str(env), self.iexpr(env, 1))
            elif r < 0.55:
                self.risk.add('KeyError')
                l = 'del %s[%s]' % (x, repr(self.r.choice(['a', 'b', 'c'])))
            elif r < 0.7:
                self.risk.add('KeyError')
                l = '%s[%s] += %s' % (x, repr(self.r.choice(['a', 'b', 'c'])), self.iexpr(env, 1))
            elif r < 0.85:
                self.risk.add('KeyError')
                l = '%s.pop(%s)' % (x, repr(self.r.choice(['a', 'b', 'c', 'dd'])))
            else:
                l = '%s.pop(%s, %d)' % (x, repr(self.r.choice(['a', 'b'])), self.k(0, 9))
        else:
            if r < 0.35:
                l = '%s.add(%s)' % (x, self.iexpr(env, 1))
            elif r < 0.55:
                l = '%s.discard(%s)' % (x, self.iexpr(env, 1))
            elif r < 0.65:
                self.risk.add('KeyError')
                l = '%s.remove(%s)' % (x, self.k(-3, 12))
            elif r < 0.8:
                l = '%s.update(%s)' % (x, self.new_value(env, 'si'))
            else:
                l = '%s %s= %s' % (x, self.r.choice(['|', '&', '-', '^']), self.new_value(env, 'si'))
        return self.guard([l], self.risk)

    def extarg(self, env):
        xs = self.of(env, 'li')
        if xs and self.p(0.4):
            return self.r.choice(xs)
        return '[%s]' % ', '.join(self.iexpr(env, 1) for _ in range(self.k(1, 3)))

    def alias(self, env):
        """ys = xs then mutate one of them: Python shares the list."""
        xs = self.r.choice(self.of(env, 'li'))
        ys = self.fresh('al')
        env[ys] = 'li'
        a, b = self.r.choice([(ys, xs), (xs, ys)])
        out = ['%s: list[int] = %s' % (ys, xs)]
        out.append(self.r.choice(['%s.append(%d)' % (a, self.k(0, 9)), '%s[0] = %d' % (a, self.k(0, 9)), '%s.sort()' % a,
                                  '%s.reverse()' % a, '%s += [%d]' % (a, self.k(0, 9))]))
        # [0] on an empty list raises; keep it safe
        out = out[:1] + ['if len(%s) > 0:' % a, '    ' + out[1]] if '[0] =' in out[1] else out
        out.append('print(len(%s), len(%s), sum(%s) - sum(%s))' % (xs, ys, xs, ys))
        if self.p(0.1) and 'listeq' not in self.off:
            out.append('print(%s == %s)' % (xs, ys))
        return out

    def exc_stmt(self, env):
        kind = self.r.choice(CATCH + ['RuntimeError', 'AssertionError'])
        self.risk = set()
        body = ['raise %s(%s)' % (kind, repr('m%d' % self.k(0, 9))) if self.p(0.7) else 'raise %s' % kind]
        if self.p(0.3):
            body = ['assert %s, "boom"' % self.cond(env, 1)]
            kind = 'AssertionError'
        guard = [self.cond(env, 1)]
        names = [kind] + ([self.r.choice(CATCH)] if self.p(0.4) else [])
        names = sorted(set(names))
        head = names[0] if len(names) == 1 else '(%s)' % ', '.join(names)
        out = ['try:', '    if %s:' % guard[0]] + ['        ' + l for l in body]
        out += ['except %s:' % head, '    print(%d)' % self.k(-99, -1)]
        if self.p(0.4):
            out += ['else:', '    print(%d)' % self.k(1, 99)]
        if self.p(0.4):
            out += ['finally:', '    print(%d)' % self.k(100, 199)]
        return out

    def if_stmt(self, env, depth, loops):
        self.risk = set()
        c = self.cond(env, 2)
        out = ['if %s:' % c] + self.block(env, depth + 1, 3, loops)
        for _ in range(self.k(0, 1)):
            out += ['elif %s:' % self.cond(env, 1)] + self.block(env, depth + 1, 2, loops)
        if self.p(0.5):
            out += ['else:'] + self.block(env, depth + 1, 2, loops)
        if self.risk:
            out = self.guard(out, self.risk)
        return out

    def for_stmt(self, env, depth, loops):
        v = self.fresh('i')
        self.prot.add(v)
        e = dict(env)
        r = self.r.random()
        lists = self.of(env, 'li')
        strs = self.of(env, 'str')
        if r < 0.45 or not (lists or strs):
            e[v] = 'int'
            head = 'for %s in range(%s):' % (v, self.r.choice([str(self.k(0, 6)), '%d, %d' % (self.k(-2, 2), self.k(3, 8)),
                                                                 '%d, %d, %d' % (self.k(0, 3), self.k(5, 14), self.k(1, 3)),
                                                                 '%d, %d, -1' % (self.k(5, 9), self.k(-2, 3))]))
        elif r < 0.75 and lists:
            e[v] = 'int'
            head = 'for %s in %s:' % (v, self.r.choice(lists))
            # never mutate the iterated list inside: mutations below only touch other kinds
            body = self.block({k: t for k, t in e.items() if t != 'li'}, depth + 1, 3, loops + 1)
            return [head] + body
        elif strs:
            e[v] = 'str'
            head = 'for %s in %s:' % (v, self.r.choice(strs))
        else:
            e[v] = 'int'
            head = 'for %s in range(4):' % v
        out = [head] + self.block(e, depth + 1, 3, loops + 1)
        return out

    def while_stmt(self, env, depth, loops):
        c = self.fresh('w')
        self.prot.add(c)
        e = dict(env)
        e[c] = 'int'
        body = self.block(e, depth + 1, 3, loops + 1)
        # the counter is advanced first so `continue` cannot skip it
        return ['%s: int = 0' % c, 'while %s < %d:' % (c, self.k(1, 6)), '    %s += 1' % c] + body

    def try_stmt(self, env, depth, loops):
        out = ['try:'] + self.block(env, depth + 1, 3, loops)
        names = self.r.sample(CATCH, self.k(1, 2))
        has_fin = self.p(0.4)
        for nm in names:
            out += ['except %s:' % nm] + self.block(env, depth + 1, 2, loops)
        if self.p(0.25):
            out += ['else:'] + self.block(env, depth + 1, 2, loops)
        if has_fin:
            out += ['finally:', '    print(%d)' % self.k(200, 299)]
        return out

    # ---- dataclass ------------------------------------------------------------------------
    def pt_stmt(self, env):
        pts = self.of(env, 'pt')
        self.risk = set()
        if not pts or self.p(0.25):
            name = self.fresh('p')
            env[name] = 'pt'
            ints = self.of(env, 'int')
            ia = lambda: self.r.choice(ints) if ints and self.p(0.5) else str(self.k(-9, 99))
            return ['%s: Pt = Pt(%s, %s, %s, %s, [])' % (name, ia(), ia(), self.r.choice(FLOATS), self.simple_str(env))]
        p = self.r.choice(pts)
        r = self.r.random()
        if r < 0.2:
            return ['%s.a %s %s' % (p, self.r.choice(['+=', '-=', '=']), self.iexpr(env, 1))]
        if r < 0.3:
            return ['%s.c += %s' % (p, self.fexpr(env, 1))]
        if r < 0.4:
            return ['%s.name += %s' % (p, self.sexpr(env, 1))]
        if r < 0.5:
            return ['%s.items.append(%s)' % (p, self.iexpr(env, 1))]
        if r < 0.65:
            q = self.fresh('p')
            env[q] = 'pt'
            tgt = self.r.choice([p, q])
            return ['%s: Pt = %s' % (q, p), '%s.b = %s' % (tgt, self.iexpr(env, 1)),
                    'print(%s.a, %s.b, %s.b, %d)' % (p, p, q, self.k(0, 9))]
        if r < 0.8:
            return ['print(%s.a, %s.b, %s.c, %s.name, len(%s.items))' % (p, p, p, p, p)]
        if r < 0.9:
            return ['print(%s.name, sum(%s.items))' % (p, p)]
        return ['print(bump(%s, %s))' % (p, self.iexpr(env, 1))]

    # ---- top level --------------------------------------------------------------------------
    def helper(self, i):
        name = 'h%d' % i
        kind = self.r.choice(['ii', 'ii', 'rec', 'li'])
        if kind == 'rec':
            m = self.k(2, 97) * 1000 + 3
            body = ['def %s(n: int, a: int) -> int:' % name,
                    '    if n <= 0:',
                    '        return (a * %d + %d) %% %d' % (self.k(1, 9), self.k(0, 9), m)]
            if self.p(0.5):
                body += ['    return (%s(n - 1, a + %d) * %d + %s(n - %d, a - %d) + n) %% %d' % (
                    name, self.k(0, 3), self.k(1, 5), name, self.k(1, 2), self.k(0, 3), m)]
            else:
                body += ['    return (%s(n - 1, (a * %d + n) %% %d) + %d) %% %d' % (name, self.k(1, 7), m, self.k(0, 9), m)]
            self.funcs.append((name, kind))
            return body
        if kind == 'li':
            body = ['def %s(xs: list[int]) -> int:' % name, '    t: int = 0', '    for x in xs:']
            body += self.r.choice([['        t = (t * %d + x) %% 1000003' % self.k(2, 9)],
                                   ['        if x %% %d == 0:' % self.k(2, 4), '            continue', '        t += x'],
                                   ['        if t > %d:' % self.k(5, 60), '            break', '        t += abs(x) + 1']])
            body += ['    return t']
            self.funcs.append((name, kind))
            return body
        env = {'a': 'int', 'b': 'int'}
        saved = self.funcs
        body = ['def %s(a: int, b: int) -> int:' % name]
        body += ['    ' + l for l in self.define_pre(env)]
        for _ in range(self.k(1, 3)):
            for l in self.stmt(env, 1, 0):
                body.append('    ' + l)
        # a return in a loop, the finally-return interplay is covered by try_stmt bodies
        self.risk = set()
        body += ['    if %s:' % self.cond(env, 1), '        return %s' % self.iexpr(env, 1)]
        body += ['    return %s' % self.iexpr(env, 2)]
        self.funcs = saved + [(name, kind)]
        return body

    def define_pre(self, env):
        out = []
        for ty in ('int', 'str', 'li'):
            out += self.define(env, ty)
        return out

    def program(self):
        use_exit = self.p(0.5)
        lines = ['import sys', ''] if use_exit else []
        pt = self.p(0.5)
        self.has_pt = pt
        if pt:
            lines += ['from dataclasses import dataclass', '', '',
                      '@dataclass', 'class Pt:', '    a: int', '    b: int', '    c: float', '    name: str',
                      '    items: list[int]', '', '']
            lines += ['def bump(p: Pt, k: int) -> int:', '    p.a += k', '    p.items.append(k)',
                      '    return p.a + len(p.items)', '', '']
        for i in range(self.k(1, 3)):
            lines += self.helper(i) + ['', '']
        env = {}
        body = []
        if pt:
            env['pt0'] = 'pt'
            body.append('pt0: Pt = Pt(%d, %d, %s, %s, [])' % (self.k(0, 9), self.k(0, 9), self.r.choice(FLOATS), self.lit_str()))
        for _ in range(self.k(8, 18)):
            body += self.stmt(env, 0, 0)
        # observe state at the end so silent corruption of a variable shows up
        for n, t in list(env.items()):
            if t == 'int':
                body.append('print(%s)' % n)
            elif t == 'float':
                body.append('print(%s)' % n)
            elif t == 'str':
                body.append('print(%s)' % n)
            elif t == 'li':
                body.append('print(len(%s), sum(%s))' % (n, n))
            elif t == 'ls':
                body.append('print(len(%s), %s)' % (n, "','.join(%s)" % n))
            elif t == 'di':
                k = self.fresh('k')
                ks = self.fresh('ks')
                body += ['%s: list[str] = []' % ks, 'for %s in sorted(%s):' % (k, n), '    %s.append(%s)' % (ks, k),
                         'print(len(%s), sum(%s.values()), %s)' % (n, n, "','.join(%s)" % ks)]
            elif t == 'si':
                body.append('print(len(%s), sum(%s), %s)' % (n, n, 'max(%s) if len(%s) > 0 else 0' % (n, n)))
            elif t == 'bytes':
                body.append('print(len(%s), %s.decode())' % (n, n))
            elif t == 'bool':
                body.append('print(%s)' % n)
            elif t == 'pt':
                body.append('print(%s.a, %s.b, %s.c, %s.name, len(%s.items))' % ((n,) * 5))
        lines += ['def main() -> int:'] + ['    ' + l for l in body] + ['    return %d' % self.r.choice([0, 0, 0, 1, 7]), '', '']
        lines += ['sys.exit(main())' if use_exit else 'main()', '']
        return '\n'.join(lines)


def generate(seed, off=()):
    return Gen(seed, off).program()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('seed', type=int)
    ap.add_argument('-o')
    ap.add_argument('--off', default='', help='comma list of features to switch off: alias,listeq,stridx')
    a = ap.parse_args()
    src = generate(a.seed, [f for f in a.off.split(',') if f])
    if a.o:
        with open(a.o, 'w', encoding='utf-8') as f:
            f.write(src)
    else:
        sys.stdout.write(src)
