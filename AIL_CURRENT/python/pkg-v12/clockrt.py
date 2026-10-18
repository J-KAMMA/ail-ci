# -*- coding: utf-8 -*-
"""clockrt.py -- runtime parts of stage G9 (the wall clock).

`CORE` is plain C (libc only), shared by the typed runtime and the general runtime:

  ailc_clock_ns     the wall clock in nanoseconds since the Unix epoch. `AIL_CLOCK=<seconds>[.<fraction>]`
                    in the environment pins it (the fraction keeps nine digits, the rest is dropped); then
                    every read returns that value plus whatever `sleep` has advanced it by.
  ailc_sleep_ns     sleeps (or, with the clock pinned, advances the pinned clock without sleeping)
  ailc_local_*      the OS time zone exactly as CPython reads it: tzset() once (the TZ variable is
                    respected) and localtime_r(); the UTC offset is computed from the broken-down time
  ailc_mktime       mktime() with CPython's error test

Errors never leave the core as exceptions: a function returns AILC_BAD (INT64_MIN) and the adapters raise,
or the Python helper in dtrt.py checks the value and raises the exception CPython raises.

`TYPED` are the adapters of the typed runtime (cruntime part CLOCK); `GENERAL` those of the general runtime
(pyboxed2); both are spliced into a program only when it reaches them, so every other program keeps its C.
"""

CORE = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <unistd.h>
#include <errno.h>
#endif
#ifndef AIL_LINK_STATE
#define AIL_LINK_STATE(type, name, init) static type name init
#endif
#define AILC_BAD INT64_MIN
AIL_LINK_STATE(int, ailc_pinned, = -1);
AIL_LINK_STATE(int64_t, ailc_pin_ns, = 0);
AIL_LINK_STATE(int, ailc_tz_ready, = 0);
/* 0 ok; 1 AIL_CLOCK is not a number of seconds; 2 the operating system failed */
static int ailc_parse_pin(const char *s, int64_t *out) {
    int neg = 0;
    if (*s == '-') { neg = 1; s++; } else if (*s == '+') s++;
    if (*s < '0' || *s > '9') return 1;
    int64_t whole = 0;
    for (; *s >= '0' && *s <= '9'; s++) {
        if (whole > (INT64_MAX - 9) / 10 / 1000000000LL) return 1;
        whole = whole * 10 + (*s - '0');
    }
    int64_t frac = 0;
    int digits = 0;
    if (*s == '.') {
        s++;
        for (; *s >= '0' && *s <= '9'; s++)
            if (digits < 9) { frac = frac * 10 + (*s - '0'); digits++; }
    }
    if (*s) return 1;
    while (digits < 9) { frac *= 10; digits++; }
    int64_t ns = whole * 1000000000LL + frac;
    *out = neg ? -ns : ns;
    return 0;
}
static int ailc_clock_ns(int64_t *out) {
    if (ailc_pinned < 0) {
        const char *s = getenv("AIL_CLOCK");
        if (s && *s) {
            if (ailc_parse_pin(s, &ailc_pin_ns)) return 1;
            ailc_pinned = 1;
        } else ailc_pinned = 0;
    }
    if (ailc_pinned) { *out = ailc_pin_ns; return 0; }
#ifdef _WIN32
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    uint64_t t = ((uint64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
    *out = ((int64_t)t - 116444736000000000LL) * 100;
#else
    struct timespec ts;
    if (clock_gettime(CLOCK_REALTIME, &ts) != 0) return 2;
    *out = (int64_t)ts.tv_sec * 1000000000LL + (int64_t)ts.tv_nsec;
#endif
    return 0;
}
/* the same conversion CPython makes for time.time() */
static double ailc_seconds(int64_t t) {
    if (t % 1000000000LL == 0) return (double)(t / 1000000000LL);
    return (double)t / 1e9;
}
static int ailc_sleep_ns(int64_t ns) {
    if (ailc_pinned < 0) { int64_t now; int e = ailc_clock_ns(&now); if (e) return e; }
    if (ailc_pinned) {
        ailc_pin_ns = (ailc_pin_ns > 0 && ns > INT64_MAX - ailc_pin_ns) ? INT64_MAX : ailc_pin_ns + ns;
        return 0;
    }
#ifdef _WIN32
    int64_t ms = (ns + 999999) / 1000000;
    while (ms > 0) { DWORD d = ms > 0x7ffffff0 ? 0x7ffffff0 : (DWORD)ms; Sleep(d); ms -= d; }
#else
    struct timespec req, rem;
    req.tv_sec = (time_t)(ns / 1000000000LL);
    req.tv_nsec = (long)(ns % 1000000000LL);
    while (nanosleep(&req, &rem) != 0) {
        if (errno != EINTR) return 2;
        req = rem;
    }
#endif
    return 0;
}
static int64_t ailc_days_from_civil(int64_t y, int64_t m, int64_t d) {
    y -= m <= 2;
    int64_t era = (y >= 0 ? y : y - 399) / 400;
    int64_t yoe = y - era * 400;
    int64_t doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    int64_t doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + doe - 719468;
}
static int ailc_localtime(int64_t secs, struct tm *tm) {
    if (!ailc_tz_ready) {
#ifdef _WIN32
        _tzset();
#else
        tzset();
#endif
        ailc_tz_ready = 1;
    }
    time_t t = (time_t)secs;
    if ((int64_t)t != secs) return -1;
#ifdef _WIN32
    if (localtime_s(tm, &t) != 0) return -1;
#else
    if (!localtime_r(&t, tm)) return -1;
#endif
    return 0;
}
/* seconds east of UTC that the OS time zone has at the UTC instant `secs` */
static int64_t ailc_local_offset(int64_t secs) {
    struct tm tm;
    if (ailc_localtime(secs, &tm)) return AILC_BAD;
    return ailc_days_from_civil((int64_t)tm.tm_year + 1900, (int64_t)tm.tm_mon + 1, tm.tm_mday) * 86400
           + (int64_t)tm.tm_hour * 3600 + (int64_t)tm.tm_min * 60 + tm.tm_sec - secs;
}
static int64_t ailc_local_isdst(int64_t secs) {
    struct tm tm;
    if (ailc_localtime(secs, &tm)) return AILC_BAD;
    return tm.tm_isdst > 0 ? 1 : (tm.tm_isdst == 0 ? 0 : -1);
}
/* the zone abbreviation at `secs` as up to seven bytes packed little endian into an int */
static int64_t ailc_tz_name(int64_t secs) {
    struct tm tm;
    char buf[64];
    if (ailc_localtime(secs, &tm)) return AILC_BAD;
    if (!strftime(buf, sizeof buf, "%Z", &tm)) return 0;
    int64_t v = 0;
    for (int i = 0; i < 7 && buf[i]; i++) v |= (int64_t)(unsigned char)buf[i] << (8 * i);
    return v;
}
static int64_t ailc_mktime(int64_t y, int64_t mo, int64_t d, int64_t h, int64_t mi, int64_t s, int64_t isdst) {
    struct tm tm;
    memset(&tm, 0, sizeof tm);
    if (y - 1900 > 2147483647LL || y - 1900 < -2147483647LL) return AILC_BAD;
    if (!ailc_tz_ready) {
#ifdef _WIN32
        _tzset();
#else
        tzset();
#endif
        ailc_tz_ready = 1;
    }
    tm.tm_year = (int)(y - 1900); tm.tm_mon = (int)(mo - 1); tm.tm_mday = (int)d;
    tm.tm_hour = (int)h; tm.tm_min = (int)mi; tm.tm_sec = (int)s;
    tm.tm_isdst = isdst > 0 ? 1 : (isdst == 0 ? 0 : -1);
    tm.tm_wday = -1;
    time_t r = mktime(&tm);
    if (r == (time_t)-1 && tm.tm_wday == -1) return AILC_BAD;
    return (int64_t)r;
}
'''

# the typed runtime: C functions of the names pyfunc._AIL_CLOCK maps to
TYPED = r'''
static void ailc_raise(int e) {
    const char *text = e == 1 ? "AIL_CLOCK must be a number of seconds since the epoch, like 1700000000.25"
                              : "the operating system clock failed";
    ail_raise_value_adopt(ail_exception_new(e == 1 ? AIL_EXC_VALUE : AIL_EXC_OS, (const uint8_t *)text, (int64_t)strlen(text), 1));
}
static int64_t ail_time_ns(void) {
    int64_t t;
    int e = ailc_clock_ns(&t);
    if (e) ailc_raise(e);
    return t;
}
static double ail_time(void) { return ailc_seconds(ail_time_ns()); }
static int64_t ail_sleep_ns(int64_t ns) {
    int e = ailc_sleep_ns(ns);
    if (e) ailc_raise(e);
    return 0;
}
static int64_t ail_local_offset(int64_t secs) { return ailc_local_offset(secs); }
static int64_t ail_local_isdst(int64_t secs) { return ailc_local_isdst(secs); }
static int64_t ail_tz_name(int64_t secs) { return ailc_tz_name(secs); }
static int64_t ail_mktime(int64_t y, int64_t mo, int64_t d, int64_t h, int64_t mi, int64_t s, int64_t isdst) {
    return ailc_mktime(y, mo, d, h, mi, s, isdst);
}
'''

GENERAL = r'''
static ail_st ailc_gfail(ail_ctx *cx, int e) {
    if (e == 1) return ail_raise_c(cx, AIL_B_VALUEERROR, "AIL_CLOCK must be a number of seconds since the epoch, like 1700000000.25");
    return ail_raise_c(cx, AIL_B_OSERROR, "the operating system clock failed");
}
static ail_st ailc_gint(ail_ctx *cx, ail_obj v, int64_t *out) {
    if (v.tag == AIL_T_INT || v.tag == AIL_T_BOOL) { *out = v.i; return AIL_OK; }
    return ail_raise_c(cx, AIL_B_TYPEERROR, "expected int");
}
static ail_st ailc_gtime_ns(ail_ctx *cx, ail_obj *out) {
    int64_t t;
    int e = ailc_clock_ns(&t);
    if (e) return ailc_gfail(cx, e);
    *out = ail_box_int(t);
    return AIL_OK;
}
static ail_st ailc_gtime(ail_ctx *cx, ail_obj *out) {
    int64_t t;
    int e = ailc_clock_ns(&t);
    if (e) return ailc_gfail(cx, e);
    *out = ail_box_float(cx, ailc_seconds(t));
    return AIL_OK;
}
static ail_st ailc_gsleep_ns(ail_ctx *cx, ail_obj *out, ail_obj ns) {
    int64_t n;
    ail_st st = ailc_gint(cx, ns, &n);
    if (st != AIL_OK) return st;
    int e = ailc_sleep_ns(n);
    if (e) return ailc_gfail(cx, e);
    *out = ail_box_int(0);
    return AIL_OK;
}
static ail_st ailc_glocal(ail_ctx *cx, ail_obj *out, ail_obj secs, int which) {
    int64_t n;
    ail_st st = ailc_gint(cx, secs, &n);
    if (st != AIL_OK) return st;
    *out = ail_box_int(which == 0 ? ailc_local_offset(n) : which == 1 ? ailc_local_isdst(n) : ailc_tz_name(n));
    return AIL_OK;
}
static ail_st ailc_gmktime(ail_ctx *cx, ail_obj *out, ail_obj *a) {
    int64_t v[7];
    for (int i = 0; i < 7; i++) {
        ail_st st = ailc_gint(cx, a[i], &v[i]);
        if (st != AIL_OK) return st;
    }
    *out = ail_box_int(ailc_mktime(v[0], v[1], v[2], v[3], v[4], v[5], v[6]));
    return AIL_OK;
}
'''


def register(ORDER, SOURCE, REQUIRES):
    """Add the clock part to cruntime's tables (called once at the end of cruntime.py)."""
    ORDER.append('CLOCK')
    SOURCE['CLOCK'] = CORE + TYPED
    REQUIRES['CLOCK'] = ['MONOTONICHEAD', 'DIE', 'TYPES']


def general_text():
    """The C the general runtime needs once a program reaches a clock primitive."""
    return '\n/* ---- G9: the wall clock ---- */\n' + CORE + GENERAL
