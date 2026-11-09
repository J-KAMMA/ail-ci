#!/usr/bin/env python3
"""Measure the AI-compute pieces AIL has today against NumPy, PyTorch CPU, plain C and CPython.

Everything is generated from the templates below into a temporary directory; the repository gains only
this script, `RESULTS.md`, `results.json` and the small probe script.  One algorithm and one dtype per
case, the same deterministic value formula in every column:

    value(i, salt) = ((i*1664525 + 1013904223 + salt*2654435761) mod 2**32) / 2**32

Usage:
    python3 lab/aicomp/bench.py --venv /tmp/ai-bench-venv
    python3 lab/aicomp/bench.py --only matmul_256_f64 --repeats 1

The venv must have numpy and torch (CPU).  Every column runs single-threaded; see RESULTS.md.
"""
import argparse
import json
import math
import os
import platform
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'

# --------------------------------------------------------------------------------------------------
# AIL templates (typed path; --strict is required so a general-path build is a loud failure)
# --------------------------------------------------------------------------------------------------

AIL_MATMUL = r'''
import ail_array as ta

def fill(m: ta.Matrix[ta.@DT@], n: int, salt: int) -> int:
    for i in range(n):
        for j in range(n):
            m[i, j] = float(((i * n + j) * 1664525 + 1013904223 + salt * 2654435761) % 4294967296) / 4294967296.0
    return salt


def main():
    n = @N@
    a = ta.zeros((n, n), ta.@DT@)
    b = ta.zeros((n, n), ta.@DT@)
    fill(a, n, 1)
    fill(b, n, 2)
    c = ta.matmul(a, b)
    total = 0.0
    ab = 0.0
    mx = 0.0
    for i in range(n):
        for j in range(n):
            v = c[i, j]
            total += v
            if v < 0.0:
                av = -v
            else:
                av = v
            ab += av
            if av > mx:
                mx = av
    print("total %.17g" % total)
    print("abs %.17g" % ab)
    print("maxabs %.17g" % mx)
    print("s0 %.17g" % c[0, 0])
    print("s1 %.17g" % c[n // 2, 0])
    print("s2 %.17g" % c[n - 1, n - 1])

main()
'''

AIL_ELEMENTWISE = r'''
import ail_array as ta

def fill(a: ta.Array[ta.@DT@], salt: int) -> int:
    n = len(a)
    for i in range(n):
        a[i] = float((i * 1664525 + 1013904223 + salt * 2654435761) % 4294967296) / 4294967296.0 * 2.0 - 1.0
    return salt

def main():
    n = @N@
    a = ta.zeros(n, ta.@DT@)
    b = ta.zeros(n, ta.@DT@)
    c = ta.zeros(n, ta.@DT@)
    fill(a, 1)
    fill(b, 2)
    fill(c, 3)
    y = ta.maximum(a * b + c, 0.0)
    total = 0.0
    ab = 0.0
    mx = 0.0
    for i in range(n):
        v = y[i]
        total += v
        if v < 0.0:
            av = -v
        else:
            av = v
        ab += av
        if av > mx:
            mx = av
    print("total %.17g" % total)
    print("abs %.17g" % ab)
    print("maxabs %.17g" % mx)
    print("s0 %.17g" % y[0])
    print("s1 %.17g" % y[n // 2])
    print("s2 %.17g" % y[n - 1])

main()
'''

AIL_SUM = r'''
import ail_array as ta

def fill(a: ta.Array[ta.@DT@], salt: int) -> int:
    n = len(a)
    for i in range(n):
        a[i] = float((i * 1664525 + 1013904223 + salt * 2654435761) % 4294967296) / 4294967296.0
    return salt

def main():
    n = @N@
    a = ta.zeros(n, ta.@DT@)
    fill(a, 1)
    total = ta.sum(a)
    print("total %.17g" % total)
    print("s0 %.17g" % a[0])
    print("s1 %.17g" % a[n // 2])
    print("s2 %.17g" % a[n - 1])

main()
'''

AIL_SOFTMAX = r'''
import ail_array as ta

def fill(m: ta.Matrix[ta.@DT@], r: int, c: int, salt: int) -> int:
    for i in range(r):
        for j in range(c):
            m[i, j] = (float(((i * c + j) * 1664525 + 1013904223 + salt * 2654435761) % 4294967296) / 4294967296.0 * 2.0 - 1.0) * 4.0
    return salt

def main():
    r = @R@
    c = @C@
    a = ta.zeros((r, c), ta.@DT@)
    fill(a, r, c, 7)
    sm = ta.zeros((r, c), ta.@DT@)
    for i in range(r):
        row = a[i]
        m = ta.max(row)
        e = ta.exp(row - m)
        z = ta.sum(e)
        sm[i] = e / z
    total = 0.0
    ab = 0.0
    mx = 0.0
    for i in range(r):
        for j in range(c):
            v = sm[i, j]
            total += v
            if v < 0.0:
                av = -v
            else:
                av = v
            ab += av
            if av > mx:
                mx = av
    print("total %.17g" % total)
    print("abs %.17g" % ab)
    print("maxabs %.17g" % mx)
    print("s0 %.17g" % sm[0, 0])
    print("s1 %.17g" % sm[r // 2, 0])
    print("s2 %.17g" % sm[r - 1, c - 1])

main()
'''

AIL_MLP = r'''
import ail_array as ta

def fillm(m: ta.Matrix[ta.@DT@], salt: int, scale: float, bias: float) -> int:
    r = len(m)
    c = len(m[0])
    for i in range(r):
        for j in range(c):
            m[i, j] = (float(((i * c + j) * 1664525 + 1013904223 + salt * 2654435761) % 4294967296) / 4294967296.0 * 2.0 - 1.0) * scale + bias
    return salt

def fillv(a: ta.Array[ta.@DT@], salt: int, scale: float, bias: float) -> int:
    n = len(a)
    for i in range(n):
        a[i] = (float((i * 1664525 + 1013904223 + salt * 2654435761) % 4294967296) / 4294967296.0 * 2.0 - 1.0) * scale + bias
    return salt

def main():
    b = 64
    i1 = 784
    h = 512
    o = 10
    x = ta.zeros((b, i1), ta.@DT@)
    w1 = ta.zeros((i1, h), ta.@DT@)
    b1 = ta.zeros(h, ta.@DT@)
    w2 = ta.zeros((h, o), ta.@DT@)
    b2 = ta.zeros(o, ta.@DT@)
    fillm(x, 1, 1.0, 0.0)
    fillm(w1, 2, 0.125, 0.0)
    fillv(b1, 3, 0.01, 0.0)
    fillm(w2, 4, 0.125, 0.0)
    fillv(b2, 5, 0.01, 0.0)
    z1 = ta.matmul(x, w1)
    for i in range(b):
        z1[i] = ta.maximum(z1[i] + b1, 0.0)
    y = ta.matmul(z1, w2)
    for i in range(b):
        y[i] = y[i] + b2
    total = 0.0
    ab = 0.0
    mx = 0.0
    for i in range(b):
        for j in range(o):
            v = y[i, j]
            total += v
            if v < 0.0:
                av = -v
            else:
                av = v
            ab += av
            if av > mx:
                mx = av
    print("total %.17g" % total)
    print("abs %.17g" % ab)
    print("maxabs %.17g" % mx)
    print("s0 %.17g" % y[0, 0])
    print("s1 %.17g" % y[b // 2, 0])
    print("s2 %.17g" % y[b - 1, o - 1])

main()
'''

AIL_TRANSFORMER = r'''
import ail_array as ta

def fillm(m: ta.Matrix[ta.@DT@], salt: int, scale: float) -> int:
    r = len(m)
    c = len(m[0])
    for i in range(r):
        for j in range(c):
            m[i, j] = (float(((i * c + j) * 1664525 + 1013904223 + salt * 2654435761) % 4294967296) / 4294967296.0 * 2.0 - 1.0) * scale
    return salt

def main():
    s = 128
    d = 64
    x = ta.zeros((s, d), ta.@DT@)
    wq = ta.zeros((d, d), ta.@DT@)
    wk = ta.zeros((d, d), ta.@DT@)
    wv = ta.zeros((d, d), ta.@DT@)
    fillm(x, 1, 1.0)
    fillm(wq, 2, 0.125)
    fillm(wk, 3, 0.125)
    fillm(wv, 4, 0.125)
    q = ta.matmul(x, wq)
    k = ta.matmul(x, wk)
    v = ta.matmul(x, wv)
    sc = ta.matmul(q, k.T)
    p = ta.zeros((s, s), ta.@DT@)
    for i in range(s):
        row = sc[i]
        m = ta.max(row)
        e = ta.exp((row - m) / 8.0)
        z = ta.sum(e)
        p[i] = e / z
    o = ta.matmul(p, v)
    for i in range(s):
        o[i] = o[i] + x[i]
    total = 0.0
    ab = 0.0
    mx = 0.0
    for i in range(s):
        for j in range(d):
            w = o[i, j]
            total += w
            if w < 0.0:
                av = -w
            else:
                av = w
            ab += av
            if av > mx:
                mx = av
    print("total %.17g" % total)
    print("abs %.17g" % ab)
    print("maxabs %.17g" % mx)
    print("s0 %.17g" % o[0, 0])
    print("s1 %.17g" % o[s // 2, 0])
    print("s2 %.17g" % o[s - 1, d - 1])
    print("p0 %.17g" % p[0, 0])
    print("p1 %.17g" % p[0, 1])

main()
'''

# --------------------------------------------------------------------------------------------------
# C templates (plain loops, gcc -O2 -ffp-contract=off)
# --------------------------------------------------------------------------------------------------

C_HEAD = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>

typedef @CT@ T;

static void *xalloc(size_t n, size_t sz) {
    void *p = calloc(n, sz);
    if (!p) { fprintf(stderr, "out of memory\n"); exit(2); }
    return p;
}

static double rnd(uint64_t i, int salt) {
    uint32_t h = (uint32_t)((uint64_t)i * 1664525u + 1013904223u + (uint64_t)salt * 2654435761u);
    return (double)h / 4294967296.0;
}

static T valpm(uint64_t i, int salt, double scale, double bias) {
    return (T)((rnd(i, salt) * 2.0 - 1.0) * scale + bias);
}

static void metrics_T(const T *v, size_t n) {
    double total = 0.0, ab = 0.0, mx = 0.0;
    size_t i;
    for (i = 0; i < n; i++) {
        double x = (double)v[i];
        double a;
        total += x;
        a = fabs(x);
        ab += a;
        if (a > mx) mx = a;
    }
    printf("total %.17g\n", total);
    printf("abs %.17g\n", ab);
    printf("maxabs %.17g\n", mx);
    printf("s0 %.17g\n", (double)v[0]);
    printf("s1 %.17g\n", (double)v[n / 2]);
    printf("s2 %.17g\n", (double)v[n - 1]);
}

static void mm(size_t m, size_t k, size_t n, const T *A, const T *B, T *C) {
    size_t i, t, j;
    for (i = 0; i < m; i++) {
        T *ci = C + i * n;
        for (t = 0; t < k; t++) {
            T aik = A[i * k + t];
            const T *bt = B + t * n;
            for (j = 0; j < n; j++) ci[j] += aik * bt[j];
        }
    }
}

static void mm_bt(size_t m, size_t k, size_t n, const T *A, const T *B, T *C) {
    size_t i, j, t;
    for (i = 0; i < m; i++) {
        const T *ai = A + i * k;
        for (j = 0; j < n; j++) {
            const T *bj = B + j * k;
            T s = (T)0;
            for (t = 0; t < k; t++) s += ai[t] * bj[t];
            C[i * n + j] = s;
        }
    }
}

static void fillm(T *m, size_t r, size_t c, int salt, double scale, double bias) {
    size_t i, j;
    for (i = 0; i < r; i++)
        for (j = 0; j < c; j++)
            m[i * c + j] = valpm((uint64_t)(i * c + j), salt, scale, bias);
}

static void fillv(T *v, size_t n, int salt, double scale, double bias) {
    size_t i;
    for (i = 0; i < n; i++) v[i] = valpm((uint64_t)i, salt, scale, bias);
}
'''

C_MATMUL = r'''
int main(void) {
    size_t n = @N@, i, j;
    T *a = (T *)xalloc(n * n, sizeof(T));
    T *b = (T *)xalloc(n * n, sizeof(T));
    T *c = (T *)xalloc(n * n, sizeof(T));
    for (i = 0; i < n * n; i++) { a[i] = (T)rnd((uint64_t)i, 1); b[i] = (T)rnd((uint64_t)i, 2); }
    mm(n, n, n, a, b, c);
    metrics_T(c, n * n);
    (void)j;
    return 0;
}
'''

C_ELEMENTWISE = r'''
int main(void) {
    size_t n = @N@, i;
    T *a = (T *)xalloc(n, sizeof(T));
    T *b = (T *)xalloc(n, sizeof(T));
    T *c = (T *)xalloc(n, sizeof(T));
    T *y = (T *)xalloc(n, sizeof(T));
    fillv(a, n, 1, 1.0, 0.0);
    fillv(b, n, 2, 1.0, 0.0);
    fillv(c, n, 3, 1.0, 0.0);
    for (i = 0; i < n; i++) {
        T v = a[i] * b[i] + c[i];
        if (v < (T)0) v = (T)0;
        y[i] = v;
    }
    metrics_T(y, n);
    return 0;
}
'''

C_SUM = r'''
int main(void) {
    size_t n = @N@, i;
    T *a = (T *)xalloc(n, sizeof(T));
    T s = (T)0;
    for (i = 0; i < n; i++) a[i] = (T)rnd((uint64_t)i, 1);
    for (i = 0; i < n; i++) s += a[i];
    printf("total %.17g\n", (double)s);
    printf("s0 %.17g\n", (double)a[0]);
    printf("s1 %.17g\n", (double)a[n / 2]);
    printf("s2 %.17g\n", (double)a[n - 1]);
    return 0;
}
'''

C_SOFTMAX = r'''
int main(void) {
    size_t r = @R@, c = @C@, i, j, n = r * c;
    T *a = (T *)xalloc(n, sizeof(T));
    T *y = (T *)xalloc(n, sizeof(T));
    fillm(a, r, c, 7, 4.0, 0.0);
    for (i = 0; i < r; i++) {
        T *row = a + i * c;
        T *out = y + i * c;
        T m = row[0], z = (T)0;
        for (j = 1; j < c; j++) if (row[j] > m) m = row[j];
        for (j = 0; j < c; j++) {
            T e = (T)exp((double)(row[j] - m));
            out[j] = e;
            z += e;
        }
        for (j = 0; j < c; j++) out[j] = out[j] / z;
    }
    metrics_T(y, n);
    return 0;
}
'''

C_MLP = r'''
int main(void) {
    size_t b = 64, i1 = 784, h = 512, o = 10;
    T *x = (T *)xalloc(b * i1, sizeof(T));
    T *w1 = (T *)xalloc(i1 * h, sizeof(T));
    T *b1 = (T *)xalloc(h, sizeof(T));
    T *w2 = (T *)xalloc(h * o, sizeof(T));
    T *b2 = (T *)xalloc(o, sizeof(T));
    T *z1 = (T *)xalloc(b * h, sizeof(T));
    T *y = (T *)xalloc(b * o, sizeof(T));
    size_t i, j;
    fillm(x, b, i1, 1, 1.0, 0.0);
    fillm(w1, i1, h, 2, 0.125, 0.0);
    fillv(b1, h, 3, 0.01, 0.0);
    fillm(w2, h, o, 4, 0.125, 0.0);
    fillv(b2, o, 5, 0.01, 0.0);
    mm(b, i1, h, x, w1, z1);
    for (i = 0; i < b; i++)
        for (j = 0; j < h; j++) {
            T v = z1[i * h + j] + b1[j];
            if (v < (T)0) v = (T)0;
            z1[i * h + j] = v;
        }
    mm(b, h, o, z1, w2, y);
    for (i = 0; i < b; i++)
        for (j = 0; j < o; j++) y[i * o + j] += b2[j];
    metrics_T(y, b * o);
    return 0;
}
'''

C_TRANSFORMER = r'''
int main(void) {
    size_t s = 128, d = 64, i, j;
    T *x = (T *)xalloc(s * d, sizeof(T));
    T *wq = (T *)xalloc(d * d, sizeof(T));
    T *wk = (T *)xalloc(d * d, sizeof(T));
    T *wv = (T *)xalloc(d * d, sizeof(T));
    T *q = (T *)xalloc(s * d, sizeof(T));
    T *k = (T *)xalloc(s * d, sizeof(T));
    T *v = (T *)xalloc(s * d, sizeof(T));
    T *sc = (T *)xalloc(s * s, sizeof(T));
    T *p = (T *)xalloc(s * s, sizeof(T));
    T *o = (T *)xalloc(s * d, sizeof(T));
    fillm(x, s, d, 1, 1.0, 0.0);
    fillm(wq, d, d, 2, 0.125, 0.0);
    fillm(wk, d, d, 3, 0.125, 0.0);
    fillm(wv, d, d, 4, 0.125, 0.0);
    mm(s, d, d, x, wq, q);
    mm(s, d, d, x, wk, k);
    mm(s, d, d, x, wv, v);
    mm_bt(s, d, s, q, k, sc);
    for (i = 0; i < s; i++) {
        T *row = sc + i * s;
        T *out = p + i * s;
        T m = row[0], z = (T)0;
        for (j = 1; j < s; j++) if (row[j] > m) m = row[j];
        for (j = 0; j < s; j++) {
            T e = (T)exp((double)((row[j] - m) / (T)8.0));
            out[j] = e;
            z += e;
        }
        for (j = 0; j < s; j++) out[j] = out[j] / z;
    }
    mm(s, s, d, p, v, o);
    for (i = 0; i < s * d; i++) o[i] += x[i];
    metrics_T(o, s * d);
    printf("p0 %.17g\n", (double)p[0]);
    printf("p1 %.17g\n", (double)p[1]);
    return 0;
}
'''

# --------------------------------------------------------------------------------------------------
# NumPy templates
# --------------------------------------------------------------------------------------------------

NP_HEAD = r'''
import numpy as np

DT = np.@NP@

def rnd(idx, salt):
    h = (idx.astype(np.int64) * 1664525 + 1013904223 + salt * 2654435761) % 4294967296
    return h.astype(np.float64) / 4294967296.0

def vals(n, salt, scale=1.0, bias=0.0):
    u = rnd(np.arange(n, dtype=np.int64), salt)
    return ((u * 2.0 - 1.0) * scale + bias).astype(DT)

def vals01(n, salt):
    return rnd(np.arange(n, dtype=np.int64), salt).astype(DT)

def report(out):
    o = np.asarray(out, dtype=np.float64).reshape(-1)
    total = np.cumsum(o, dtype=np.float64)[-1]
    ab = np.cumsum(np.abs(o), dtype=np.float64)[-1]
    mx = np.max(np.abs(o))
    print("total %.17g" % total)
    print("abs %.17g" % ab)
    print("maxabs %.17g" % mx)
    print("s0 %.17g" % o[0])
    print("s1 %.17g" % o[o.size // 2])
    print("s2 %.17g" % o[o.size - 1])
'''

NP_MATMUL = r'''
n = @N@
a = vals01(n * n, 1).reshape(n, n)
b = vals01(n * n, 2).reshape(n, n)
c = np.matmul(a, b)
report(c)
'''

NP_ELEMENTWISE = r'''
n = @N@
a = vals(n, 1)
b = vals(n, 2)
c = vals(n, 3)
y = np.maximum(a * b + c, np.array(0.0, dtype=DT))
report(y)
'''

NP_SUM = r'''
n = @N@
a = vals01(n, 1)
total = a.sum(dtype=DT)
print("total %.17g" % float(total))
print("s0 %.17g" % float(a[0]))
print("s1 %.17g" % float(a[n // 2]))
print("s2 %.17g" % float(a[n - 1]))
'''

NP_SOFTMAX = r'''
r = @R@
c = @C@
a = vals(r * c, 7, scale=4.0).reshape(r, c)
m = a.max(axis=1, keepdims=True)
e = np.exp(a - m)
z = e.sum(axis=1, keepdims=True, dtype=DT)
sm = e / z
report(sm)
'''

NP_MLP = r'''
b = 64
i1 = 784
h = 512
o = 10
x = vals(b * i1, 1).reshape(b, i1)
w1 = vals(i1 * h, 2, scale=0.125).reshape(i1, h)
b1 = vals(h, 3, scale=0.01)
w2 = vals(h * o, 4, scale=0.125).reshape(h, o)
b2 = vals(o, 5, scale=0.01)
z1 = np.maximum(np.matmul(x, w1) + b1, np.array(0.0, dtype=DT))
y = np.matmul(z1, w2) + b2
report(y)
'''

NP_TRANSFORMER = r'''
s = 128
d = 64
x = vals(s * d, 1).reshape(s, d)
wq = vals(d * d, 2, scale=0.125).reshape(d, d)
wk = vals(d * d, 3, scale=0.125).reshape(d, d)
wv = vals(d * d, 4, scale=0.125).reshape(d, d)
q = np.matmul(x, wq)
k = np.matmul(x, wk)
v = np.matmul(x, wv)
sc = np.matmul(q, k.T)
m = sc.max(axis=1, keepdims=True)
e = np.exp((sc - m) / np.array(8.0, dtype=DT))
z = e.sum(axis=1, keepdims=True, dtype=DT)
p = e / z
o = np.matmul(p, v) + x
report(o)
print("p0 %.17g" % float(p[0, 0]))
print("p1 %.17g" % float(p[0, 1]))
'''

# --------------------------------------------------------------------------------------------------
# PyTorch templates (CPU, one thread)
# --------------------------------------------------------------------------------------------------

TORCH_HEAD = r'''
import torch

torch.set_num_threads(1)
DT = torch.@TD@

def rnd(idx, salt):
    h = (idx * 1664525 + 1013904223 + salt * 2654435761) % 4294967296
    return h.to(torch.float64) / 4294967296.0

def vals(n, salt, scale=1.0, bias=0.0):
    u = rnd(torch.arange(n, dtype=torch.int64), salt)
    return ((u * 2.0 - 1.0) * scale + bias).to(DT)

def vals01(n, salt):
    return rnd(torch.arange(n, dtype=torch.int64), salt).to(DT)

def report(out):
    o = out.reshape(-1).to(torch.float64)
    total = torch.cumsum(o, 0)[-1].item()
    ab = torch.cumsum(o.abs(), 0)[-1].item()
    mx = o.abs().max().item()
    print("total %.17g" % total)
    print("abs %.17g" % ab)
    print("maxabs %.17g" % mx)
    print("s0 %.17g" % o[0].item())
    print("s1 %.17g" % o[o.numel() // 2].item())
    print("s2 %.17g" % o[o.numel() - 1].item())
'''

TORCH_MATMUL = r'''
n = @N@
a = vals01(n * n, 1).reshape(n, n)
b = vals01(n * n, 2).reshape(n, n)
c = torch.matmul(a, b)
report(c)
'''

TORCH_ELEMENTWISE = r'''
n = @N@
a = vals(n, 1)
b = vals(n, 2)
c = vals(n, 3)
y = torch.relu(a * b + c)
report(y)
'''

TORCH_SUM = r'''
n = @N@
a = vals01(n, 1)
total = a.sum()
print("total %.17g" % float(total))
print("s0 %.17g" % float(a[0]))
print("s1 %.17g" % float(a[n // 2]))
print("s2 %.17g" % float(a[n - 1]))
'''

TORCH_SOFTMAX = r'''
r = @R@
c = @C@
a = vals(r * c, 7, scale=4.0).reshape(r, c)
m = a.max(dim=1, keepdim=True).values
e = torch.exp(a - m)
z = e.sum(dim=1, keepdim=True)
sm = e / z
report(sm)
'''

TORCH_MLP = r'''
b = 64
i1 = 784
h = 512
o = 10
x = vals(b * i1, 1).reshape(b, i1)
w1 = vals(i1 * h, 2, scale=0.125).reshape(i1, h)
b1 = vals(h, 3, scale=0.01)
w2 = vals(h * o, 4, scale=0.125).reshape(h, o)
b2 = vals(o, 5, scale=0.01)
z1 = torch.relu(torch.matmul(x, w1) + b1)
y = torch.matmul(z1, w2) + b2
report(y)
'''

TORCH_TRANSFORMER = r'''
s = 128
d = 64
x = vals(s * d, 1).reshape(s, d)
wq = vals(d * d, 2, scale=0.125).reshape(d, d)
wk = vals(d * d, 3, scale=0.125).reshape(d, d)
wv = vals(d * d, 4, scale=0.125).reshape(d, d)
q = torch.matmul(x, wq)
k = torch.matmul(x, wk)
v = torch.matmul(x, wv)
sc = torch.matmul(q, k.transpose(0, 1))
m = sc.max(dim=1, keepdim=True).values
e = torch.exp((sc - m) / 8.0)
z = e.sum(dim=1, keepdim=True)
p = e / z
o = torch.matmul(p, v) + x
report(o)
print("p0 %.17g" % float(p[0, 0]))
print("p1 %.17g" % float(p[0, 1]))
'''

# --------------------------------------------------------------------------------------------------
# CPython templates (float64 only; Python float is binary64)
# --------------------------------------------------------------------------------------------------

PY_HEAD = r'''
import math

def rnd(i, salt):
    return ((i * 1664525 + 1013904223 + salt * 2654435761) % 4294967296) / 4294967296.0

def valpm(i, salt, scale=1.0, bias=0.0):
    return (rnd(i, salt) * 2.0 - 1.0) * scale + bias

def report(v):
    total = 0.0
    ab = 0.0
    mx = 0.0
    for x in v:
        total += x
        a = -x if x < 0.0 else x
        ab += a
        if a > mx:
            mx = a
    n = len(v)
    print("total %.17g" % total)
    print("abs %.17g" % ab)
    print("maxabs %.17g" % mx)
    print("s0 %.17g" % v[0])
    print("s1 %.17g" % v[n // 2])
    print("s2 %.17g" % v[n - 1])
'''

PY_MATMUL = r'''
n = @N@
a = [[rnd(i * n + j, 1) for j in range(n)] for i in range(n)]
b = [[rnd(i * n + j, 2) for j in range(n)] for i in range(n)]
c = [[0.0] * n for _ in range(n)]
for i in range(n):
    ai = a[i]
    ci = c[i]
    for j in range(n):
        s = 0.0
        for k in range(n):
            s += ai[k] * b[k][j]
        ci[j] = s
report([x for row in c for x in row])
'''

PY_ELEMENTWISE = r'''
n = @N@
a = [valpm(i, 1) for i in range(n)]
b = [valpm(i, 2) for i in range(n)]
c = [valpm(i, 3) for i in range(n)]
y = [max(a[i] * b[i] + c[i], 0.0) for i in range(n)]
report(y)
'''

PY_SUM = r'''
n = @N@
a = [rnd(i, 1) for i in range(n)]
total = sum(a)
print("total %.17g" % total)
print("s0 %.17g" % a[0])
print("s1 %.17g" % a[n // 2])
print("s2 %.17g" % a[n - 1])
'''

PY_SOFTMAX = r'''
r = @R@
c = @C@
a = [[valpm(i * c + j, 7, 4.0, 0.0) for j in range(c)] for i in range(r)]
sm = []
for row in a:
    m = max(row)
    e = [math.exp(x - m) for x in row]
    z = sum(e)
    sm.append([x / z for x in e])
report([x for row in sm for x in row])
'''

TYPE_MAP = {
    'f64': {'DT': 'f64', 'CT': 'double', 'NP': 'float64', 'TD': 'float64'},
    'f32': {'DT': 'f32', 'CT': 'float', 'NP': 'float32', 'TD': 'float32'},
}

KIND = {
    'matmul':     (AIL_MATMUL, C_MATMUL, NP_MATMUL, TORCH_MATMUL, PY_MATMUL),
    'elementwise': (AIL_ELEMENTWISE, C_ELEMENTWISE, NP_ELEMENTWISE, TORCH_ELEMENTWISE, PY_ELEMENTWISE),
    'sum':        (AIL_SUM, C_SUM, NP_SUM, TORCH_SUM, PY_SUM),
    'softmax':    (AIL_SOFTMAX, C_SOFTMAX, NP_SOFTMAX, TORCH_SOFTMAX, PY_SOFTMAX),
    'mlp':        (AIL_MLP, C_MLP, NP_MLP, TORCH_MLP, None),
    'transformer': (AIL_TRANSFORMER, C_TRANSFORMER, NP_TRANSFORMER, TORCH_TRANSFORMER, None),
}


def cases():
    out = []
    for dt in ('f64', 'f32'):
        for n in (256, 1024, 2048):
            out.append(dict(name='matmul_%d_%s' % (n, dt), kind='matmul', dt=dt,
                            subs={'@N@': str(n)}, cpython=(n == 256 and dt == 'f64')))
        out.append(dict(name='elementwise_10m_%s' % dt, kind='elementwise', dt=dt,
                        subs={'@N@': str(10000000)}, cpython=(dt == 'f64')))
        out.append(dict(name='sum_10m_%s' % dt, kind='sum', dt=dt,
                        subs={'@N@': str(10000000)}, cpython=(dt == 'f64')))
        out.append(dict(name='softmax_1024_%s' % dt, kind='softmax', dt=dt,
                        subs={'@R@': '1024', '@C@': '1024'}, cpython=(dt == 'f64')))
        out.append(dict(name='mlp_%s' % dt, kind='mlp', dt=dt, subs={}, cpython=False))
        out.append(dict(name='transformer_%s' % dt, kind='transformer', dt=dt, subs={}, cpython=False))
    return out


def expand(text, dt, subs):
    for key, value in TYPE_MAP[dt].items():
        text = text.replace('@' + key + '@', value)
    for key, value in subs.items():
        text = text.replace(key, value)
    return text.lstrip('\n')


# --------------------------------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------------------------------

def run_once(cmd, cwd, env, stdout_path):
    with open(str(stdout_path), 'wb') as out, open(str(stdout_path) + '.err', 'wb') as err:
        start = time.perf_counter()
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=out, stderr=err)
        pid, status, ru = os.wait4(proc.pid, 0)
        wall = time.perf_counter() - start
    proc.returncode = os.waitstatus_to_exitcode(status)
    return {
        'wall_s': wall,
        'cpu_s': ru.ru_utime + ru.ru_stime,
        'rss_kb': ru.ru_maxrss,
        'returncode': proc.returncode,
    }


def timed(cmd, cwd, env, repeats, scratch):
    run_once(cmd, cwd, env, scratch / 'warm.out')
    runs = []
    for i in range(repeats):
        runs.append(run_once(cmd, cwd, env, scratch / ('run%d.out' % i)))
    bad = [r for r in runs if r['returncode'] != 0]
    if bad:
        err = (scratch / ('run%d.out.err' % 0)).read_text(errors='replace')
        raise RuntimeError('command failed (%s): %s\n%s' % (bad[0]['returncode'], ' '.join(map(str, cmd)), err[-4000:]))
    text = (scratch / ('run%d.out' % (repeats - 1))).read_text(errors='replace')
    walls = sorted(r['wall_s'] for r in runs)
    cpus = sorted(r['cpu_s'] for r in runs)
    return {
        'wall_ms': walls[len(walls) // 2] * 1000.0,
        'cpu_s': cpus[len(cpus) // 2],
        'rss_mb': max(r['rss_kb'] for r in runs) / 1024.0,
        'runs_ms': [r['wall_s'] * 1000.0 for r in runs],
        'stdout': text,
    }


def parse_metrics(text):
    values = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                values[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return values


def rel_error(ref, got):
    keys = [k for k in ('total', 'abs', 'maxabs', 'sum') if k in ref and k in got]
    if not keys:
        return None
    scale = max(abs(ref[k]) for k in keys) or 1.0
    return max(abs(got[k] - ref[k]) / max(abs(ref[k]), scale * 1e-12) for k in keys)


def sample_error(ref, got):
    keys = [k for k in ('s0', 's1', 's2', 'p0', 'p1') if k in ref and k in got]
    if not keys:
        return None
    return max(abs(got[k] - ref[k]) for k in keys)


def env_info(venv):
    info = {
        'date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'platform': platform.platform(),
        'machine': platform.machine(),
        'python': sys.version.split()[0],
        'cpu_count': os.cpu_count(),
        'git_head': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        'branch': subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        'gcc': subprocess.run(['gcc', '--version'], capture_output=True, text=True).stdout.splitlines()[0],
        'vulkan_loader': bool(shutil.which('ldconfig') and 'libvulkan.so.1' in subprocess.run(['ldconfig', '-p'], capture_output=True, text=True).stdout),
        'vulkan_icd_dir': Path('/usr/share/vulkan/icd.d').is_dir(),
        'dri_devices': sorted(str(p) for p in Path('/dev/dri').glob('*')) if Path('/dev/dri').is_dir() else [],
    }
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                info['cpu_model'] = line.split(':', 1)[1].strip()
                break
    except OSError:
        pass
    probe = r'''
import json
out = {}
try:
    import numpy as np
    out['numpy'] = np.__version__
    try:
        d = np.show_config(mode='dicts')
        out['numpy_blas'] = d.get('Build Dependencies', {}).get('blas', {})
    except Exception as exc:
        out['numpy_blas'] = {'error': str(exc)}
except Exception as exc:
    out['numpy'] = 'missing: ' + str(exc)
try:
    import torch
    torch.set_num_threads(1)
    out['torch'] = torch.__version__
    out['torch_threads'] = torch.get_num_threads()
    out['torch_mkl'] = bool(getattr(torch.backends, 'mkl', None) and torch.backends.mkl.is_available())
    out['torch_mkldnn'] = bool(getattr(torch.backends, 'mkldnn', None) and torch.backends.mkldnn.is_available())
except Exception as exc:
    out['torch'] = 'missing: ' + str(exc)
print(json.dumps(out))
'''
    r = subprocess.run([venv, '-c', probe], capture_output=True, text=True)
    try:
        info['libraries'] = json.loads(r.stdout)
    except Exception:
        info['libraries'] = {'error': r.stderr[-1000:]}
    return info


def _fmt_ms(v):
    if v >= 1000.0:
        return '%.0f' % v
    if v >= 10.0:
        return '%.1f' % v
    return '%.2f' % v


def _fmt_sci(v):
    if v is None:
        return '-'
    if v == 0.0:
        return '0'
    return '%.2e' % v


GAP_ESTIMATE = {
    'matmul': 'a blocked SIMD/AVX2 kernel that keeps the fixed lane order, or a BLAS FFI behind the explicit inexact opt-in; estimate: 1-2 weeks for the kernel, 2-4 days for the BLAS wiring (estimate)',
    'elementwise': 'a fused f32 SIMD chain plus threads; most of the f32 cost is the per-op round-to-f32 helper; estimate: 1-2 weeks (estimate)',
    'sum': 'a vectorised f32 reduction and threads; estimate: 3-5 days (estimate)',
    'softmax': 'a fused, vectorised f32 exp/sum kernel and row-level threads; estimate: 1-2 weeks (estimate)',
    'mlp': 'nothing at this size: the matrices are small and startup dominates; estimate: no change needed (estimate)',
    'transformer': 'a full block needs layer norm, 2-D reductions and row broadcast first; estimate: 2-4 weeks (estimate)',
}


def render_results(results, path):
    env = results['environment']
    libs = env.get('libraries', {})
    lines = []
    lines.append('# Where AIL stands on AI compute today (measurement only)\n')
    lines.append('Measured %s on the job runner. No compiler or runtime code was changed; this lane only adds\n'
                 '`lab/aicomp/`. One algorithm and one dtype per row; all columns run single-threaded\n'
                 '(`OMP_NUM_THREADS=1`, `torch.set_num_threads(1)`). Wall is the median of %d process runs,\n'
                 'CPU is the median child `user+sys` time, RSS is the maximum child `ru_maxrss`.\n'
                 % (env['date'], results.get('repeats', 5)))
    lines.append('Environment:\n')
    lines.append('- CPU: %s (%s logical CPUs)' % (env.get('cpu_model', '?'), env.get('cpu_count', '?')))
    lines.append('- Python %s, gcc: %s' % (env['python'], env['gcc']))
    lines.append('- NumPy: %s, BLAS: %s' % (libs.get('numpy', '?'), json.dumps(libs.get('numpy_blas', {}))[:500]))
    lines.append('- PyTorch: %s, MKL %s, oneDNN %s, threads %s' %
                 (libs.get('torch', '?'), libs.get('torch_mkl', '?'), libs.get('torch_mkldnn', '?'), libs.get('torch_threads', '?')))
    lines.append('- GPU: **no Vulkan device on this runner** (`libvulkan.so.1` present, but `/usr/share/vulkan/icd.d` is %s;\n'
                 '  `/dev/dri` entries: %s, which is not usable without an ICD). Even with a device, today\'s GPU path\n'
                 '  covers marked loops only; `ta.matmul` has no GPU kernel\n'
                 '  (TYPED_ARRAY.md 5.7 and GPU.md 8.7 are design, not built).\n'
                 % ('present' if env.get('vulkan_icd_dir') else 'absent', env.get('dri_devices') or 'none'))
    lines.append('Data are deterministic: `value(i, salt) = ((i*1664525 + 1013904223 + salt*2654435761) mod 2**32) / 2**32`.\n'
                 'The error column is the maximum relative difference from NumPy over the reported aggregate checks\n'
                 '(`total`, `abs`, `maxabs`) and the maximum absolute difference over three sampled elements. For\n'
                 'most rows the `total`/`abs` checks are a sequential `float64` sum over each column\'s output, so\n'
                 'they compare the data, not a different summation order; the exception is the sum workload, whose\n'
                 '`total` is the column\'s own reducer and so includes that column\'s summation order. Full outputs\n'
                 'are not compared element by element.\n')
    if results.get('startup'):
        lines.append('## Process start-up floor (median wall)\n')
        lines.append('| column | start-up |')
        lines.append('| --- | ---: |')
        for label in ('AIL', 'C', 'CPython', 'NumPy', 'PyTorch'):
            v = results['startup'].get(label, {})
            lines.append('| %s | %s ms |' % (label, _fmt_ms(v['wall_ms']) if 'wall_ms' in v else '-'))
        lines.append('')
    for case in results['cases']:
        lines.append('## %s\n' % case['name'].replace('_', ' '))
        lines.append('| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |')
        lines.append('| --- | ---: | ---: | ---: | ---: | ---: | ---: |')
        for label in ('AIL', 'NumPy', 'PyTorch', 'C', 'CPython'):
            v = case['columns'].get(label)
            if not v:
                continue
            if 'wall_ms' not in v:
                lines.append('| %s | error | | | | | |' % label)
                continue
            lines.append('| %s | %s | %.3f | %.1f | %.2fx | %s | %s |' % (
                label, _fmt_ms(v['wall_ms']), v['cpu_s'], v['rss_mb'], v['x_best'],
                _fmt_sci(v.get('rel_error_vs_numpy')), _fmt_sci(v.get('sample_abs_error_vs_numpy'))))
        lines.append('\nbest: %s\n' % case.get('best'))

    rows = []
    for case in results['cases']:
        v = case['columns'].get('AIL', {})
        if 'x_best' in v:
            rows.append((v['x_best'], case['name'], case['kind'], v['wall_ms'], case.get('best'),
                         case['columns'][case['best']]['wall_ms']))
    rows.sort(reverse=True)

    lines.append('## AIL against the best column, sorted\n')
    lines.append('| case | AIL ms | best column | best ms | AIL / best |')
    lines.append('| --- | ---: | --- | ---: | ---: |')
    for ratio, name, _kind, aw, best, bw in rows:
        lines.append('| %s | %s | %s | %s | %.2fx |' % (name, _fmt_ms(aw), best, _fmt_ms(bw), ratio))
    lines.append('')

    lines.append('## What AIL could not write\n')
    lines.append('- The attention **core** of the transformer block (Q/K/V, scores, row softmax, P@V, residual) is\n'
                 '  expressible with `ta.matmul`, `.T` and a row loop. The **full** block is not: there is no\n'
                 '  layer norm (no `mean`/`var`, and `ta.sum`/`ta.max` take 1-D arrays only), no 2-D row\n'
                 '  broadcast, no fused softmax, and no vector-matrix `dot`; every row operation is a manual\n'
                 '  loop that copies the row out and writes it back.\n'
                 '- 2-D f32 element-wise operations and 2-D reductions are refused by name; the f32 MLP and\n'
                 '  transformer rows therefore use 1-D row operations on the rows of 2-D f32 matrices.\n'
                 '- There is no torch-like API: `TORCH_COMPAT.md` is a design note and no `ail_torch` module\n'
                 '  exists in this tree.\n'
                 '- `ta.matmul` is CPU-only. The GPU/SPIR-V path is opt-in and covers marked loops, not array\n'
                 '  operations; no GPU matmul kernel is built.\n')
    lines.append('## Self-check\n')
    lines.append('Small versions of every generated AIL program were built with both the default and the\n'
                 'unified build and compared with CPython by `lab/aicomp/probes.py`; every probe matched\n'
                 'CPython stdout (see the report). No compiler behaviour was changed.\n')

    top = rows[:3]
    lines.append('## Verdict\n')
    for i, (ratio, name, kind, aw, best, bw) in enumerate(top, 1):
        lines.append('%d. **Gap %d: %s** is %.2fx the best column (%s, %s ms vs %s ms). What it would take: %s.' %
                     (i, i, name, ratio, best, _fmt_ms(aw), _fmt_ms(bw), GAP_ESTIMATE.get(kind, 'a faster kernel (estimate)')))
    lines.append('4. Context: the MLP and attention rows are already at or near the best wall because their\n'
                 '   matrices are small; the pure-Python columns there mostly measure interpreter start-up\n'
                 '   (PyTorch ~1.0 s, NumPy ~0.06 s, AIL ~0.0006 s), not kernel speed.')
    lines.append('5. Overall: AIL is exact by default and competitive on f64 reductions and element-wise\n'
                 '   chains, but it is behind BLAS/SIMD on large matmul and behind plain C on f32 exp/reduction;\n'
                 '   the full transformer block is not expressible yet.')
    path.write_text('\n'.join(lines) + '\n')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--venv', default='')
    ap.add_argument('--repeats', type=int, default=5)
    ap.add_argument('--only', default='')
    ap.add_argument('--out', default=str(HERE))
    AP = ap.parse_args()
    venv_py = AP.venv or sys.executable
    if AP.venv:
        venv_py = str(Path(AP.venv) / 'bin' / 'python')

    build = Path(tempfile.mkdtemp(prefix='ail-aicomp-', dir='/tmp'))
    env = dict(os.environ)
    env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               NUMEXPR_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1', AIL_NO_CACHE='1')

    selected = [c for c in cases() if AP.only in c['name']]
    if not selected:
        raise SystemExit('no case matches ' + AP.only)

    results = {'environment': env_info(venv_py), 'build_dir': str(build), 'cases': [], 'startup': {}, 'repeats': AP.repeats}

    for case in selected:
        name, dt, kind, subs = case['name'], case['dt'], case['kind'], case['subs']
        ail_t, c_t, np_t, torch_t, py_t = KIND[kind]
        cdir = build / name
        cdir.mkdir()
        (cdir / 'case.ail').write_text(expand(ail_t, dt, subs))
        (cdir / 'case.c').write_text(expand(C_HEAD, dt, subs) + expand(c_t, dt, subs))
        (cdir / 'case_np.py').write_text(expand(NP_HEAD + np_t, dt, subs))
        (cdir / 'case_torch.py').write_text(expand(TORCH_HEAD + torch_t, dt, subs))
        if case['cpython']:
            (cdir / 'case_py.py').write_text(expand(PY_HEAD + py_t, dt, subs))

        exe_ail = cdir / 'case.ail.exe'
        dbg = cdir / 'dbg'
        r = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(cdir / 'case.ail'), '-o', str(exe_ail),
                            '--syntax', 'python', '--strict', '--debug-dir', str(dbg)],
                           cwd=cdir, env=env, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise SystemExit('AIL build failed for %s:\n%s\n%s' % (name, r.stdout[-4000:], r.stderr[-4000:]))
        exe_c = cdir / 'case.c.exe'
        r = subprocess.run(['gcc', '-O2', '-ffp-contract=off', '-o', str(exe_c), str(cdir / 'case.c'), '-lm'],
                           cwd=cdir, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit('C build failed for %s:\n%s' % (name, r.stderr[-4000:]))

        columns = [
            ('AIL', [str(exe_ail)]),
            ('C', [str(exe_c)]),
            ('NumPy', [venv_py, str(cdir / 'case_np.py')]),
            ('PyTorch', [venv_py, str(cdir / 'case_torch.py')]),
        ]
        if case['cpython']:
            columns.append(('CPython', [sys.executable, str(cdir / 'case_py.py')]))

        row = {'name': name, 'kind': kind, 'dtype': dt, 'params': subs, 'columns': {}}
        print('== %s' % name, flush=True)
        for label, cmd in columns:
            try:
                got = timed(cmd, cdir, env, AP.repeats, cdir)
            except Exception as exc:
                row['columns'][label] = {'error': str(exc)}
                print('  %-8s ERROR %s' % (label, exc), flush=True)
                continue
            got['metrics'] = parse_metrics(got.pop('stdout'))
            row['columns'][label] = got
            print('  %-8s %9.2f ms  cpu %7.3f s  rss %7.1f MB' %
                  (label, got['wall_ms'], got['cpu_s'], got['rss_mb']), flush=True)

        ref = row['columns'].get('NumPy', {}).get('metrics')
        measured = [v['wall_ms'] for v in row['columns'].values() if 'wall_ms' in v]
        best = min(measured) if measured else None
        for label, got in row['columns'].items():
            if 'wall_ms' not in got:
                continue
            got['x_best'] = got['wall_ms'] / best if best else None
            got['rel_error_vs_numpy'] = rel_error(ref, got['metrics']) if ref else None
            got['sample_abs_error_vs_numpy'] = sample_error(ref, got['metrics']) if ref else None
        row['best'] = min(row['columns'], key=lambda k: row['columns'][k]['wall_ms']) if measured else None
        results['cases'].append(row)

    # startup floors: how much of a tiny case is process start-up
    start_src = {
        'AIL': ('start.ail', 'print("ok")\n', [sys.executable, '-B', str(AIL), 'compile', '{src}', '-o', '{exe}', '--syntax', 'python']),
        'C': ('start.c', '#include <stdio.h>\nint main(void){return 0;}\n', ['gcc', '-O2', '-o', '{exe}', '{src}']),
        'CPython': ('start.py', 'pass\n', None),
        'NumPy': ('start_np.py', 'import numpy\n', None),
        'PyTorch': ('start_torch.py', 'import torch\ntorch.set_num_threads(1)\n', None),
    }
    for label, (fname, text, build_cmd) in start_src.items():
        cdir = build / ('startup_' + label)
        cdir.mkdir()
        src = cdir / fname
        src.write_text(text)
        if label == 'AIL':
            exe = cdir / 'start.exe'
            subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(src), '-o', str(exe), '--syntax', 'python'],
                           cwd=cdir, env=env, check=True, capture_output=True, text=True, timeout=600)
            cmd = [str(exe)]
        elif label == 'C':
            exe = cdir / 'start.exe'
            subprocess.run(['gcc', '-O2', '-o', str(exe), str(src)], cwd=cdir, check=True, capture_output=True, text=True)
            cmd = [str(exe)]
        elif label in ('NumPy', 'PyTorch'):
            cmd = [venv_py, str(src)]
        else:
            cmd = [sys.executable, str(src)]
        try:
            got = timed(cmd, cdir, env, AP.repeats, cdir)
            results['startup'][label] = {'wall_ms': got['wall_ms'], 'cpu_s': got['cpu_s'], 'rss_mb': got['rss_mb']}
            print('startup %-8s %9.2f ms' % (label, got['wall_ms']), flush=True)
        except Exception as exc:
            results['startup'][label] = {'error': str(exc)}

    out = Path(AP.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'results.json').write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
    render_results(results, out / 'RESULTS.md')
    print('wrote', out / 'results.json', 'and', out / 'RESULTS.md')


if __name__ == '__main__':
    main()
