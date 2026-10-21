# -*- coding: utf-8 -*-
"""threadrt.py -- the runtime half of stage G12 (threads): one interpreter lock with CPython's GIL
semantics, for the general-path runtime (cruntime.OBJ2) only.

Only a program that imports threading, queue or concurrent.futures gets any of this (threadlib.py
decides; pyboxed2.py asks for it). Every other program's C is byte for byte what it was: the text
below is added to the preamble and the few patches are applied to a copy of it, never to the shared
runtime text.

The model
  * One mutex-protected flag is the lock. The thread that holds it runs AIL code; every other
    thread is blocked in the lock, in a wait, in sleep(), or in a blocking system call.
  * The lock changes hands only at defined points: a loop back-edge when another thread has asked
    for it (the request is made after 5 ms of waiting, CPython's switch interval), a wait
    (`_ail_th_wait`: join, Lock.acquire, Queue.get, Event.wait, ...), sleep(), and the end of a
    thread. Between two such points the running thread is alone, so reference counts, the GC's
    object list and every container need no atomics.
  * The runtime state that belongs to a thread -- the shadow-stack frame chain, the pending
    exception, the pending limit -- lives in the one ail_ctx while the thread runs and is saved in
    the thread's record while it does not. The GC marks the running thread's state through the
    ctx (as before) and every other thread's saved state through the records (ail_thr_mark_roots).
  * Everything else in ail_ctx (the heap, the GC threshold, the interned names, the builtin classes,
    the stdout buffer, the stdin line buffer) is shared and touched only by the holder.
"""

RUNTIME = r'''
/* ==== G12 threads: one interpreter lock with CPython's GIL semantics (threadrt.py) ==== */
#include <pthread.h>
#include <errno.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

typedef struct ail_thr {
    ail_frame *frames;            /* saved while the thread does not hold the lock */
    ail_excslot exc;
    int exc_pending;
    ail_limitslot limit;
    ail_obj tobj;                 /* the Thread object (a GC root while the thread runs) */
    int64_t ident;
    int daemon;
    ail_ctx *cx;                  /* the one context, handed to the new thread */
    struct ail_thr *next;
} ail_thr;

static pthread_mutex_t ail_gil_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ail_gil_cv = PTHREAD_COND_INITIALIZER;     /* the lock became free */
static pthread_cond_t ail_gil_sw_cv = PTHREAD_COND_INITIALIZER;  /* a waiter took the lock */
static pthread_cond_t ail_th_cv = PTHREAD_COND_INITIALIZER;      /* the notify generation moved */
static int ail_gil_locked = 1;        /* the main thread holds the lock from the start */
static int ail_gil_waiting;           /* threads blocked in ail_gil_take_locked */
static uint64_t ail_gil_switches;
static int ail_gil_drop;              /* "please let go": set by a waiter, read at back-edges */
static int64_t ail_th_gen;
static int64_t ail_th_next_ident = 1;
static ail_thr ail_th_main = { .ident = 1 };
static ail_thr *ail_th_cur = &ail_th_main;   /* the holder (read and written under the lock) */
static ail_thr *ail_th_list;                  /* started threads that have not finished */
static int ail_th_any;
static ail_st (*ail_th_body_fn)(ail_ctx *, ail_obj *, ail_obj);
static ail_st (*ail_th_atexit_fn)(ail_ctx *, ail_obj *);

static void ail_th_abstime(struct timespec *ts, double secs) {
    if (secs > 1e9) secs = 1e9;
    clock_gettime(CLOCK_REALTIME, ts);
    time_t whole = (time_t)secs;
    long frac = (long)((secs - (double)whole) * 1e9);
    ts->tv_sec += whole;
    ts->tv_nsec += frac;
    if (ts->tv_nsec >= 1000000000L) { ts->tv_sec += 1; ts->tv_nsec -= 1000000000L; }
}

/* both with ail_gil_mu held */
static void ail_gil_take_locked(ail_ctx *cx, ail_thr *t) {
    if (ail_gil_locked) {
        ail_gil_waiting++;
        while (ail_gil_locked) {
            uint64_t seen = ail_gil_switches;
            struct timespec ts;
            ail_th_abstime(&ts, 0.005);
            int rc = pthread_cond_timedwait(&ail_gil_cv, &ail_gil_mu, &ts);
            if (rc == ETIMEDOUT && ail_gil_locked && ail_gil_switches == seen)
                __atomic_store_n(&ail_gil_drop, 1, __ATOMIC_RELAXED);
        }
        ail_gil_waiting--;
    }
    ail_gil_locked = 1;
    ail_gil_switches++;
    __atomic_store_n(&ail_gil_drop, 0, __ATOMIC_RELAXED);
    pthread_cond_broadcast(&ail_gil_sw_cv);
    cx->frames = t->frames;
    cx->exc = t->exc;
    cx->exc_pending = t->exc_pending;
    cx->limit = t->limit;
    ail_th_cur = t;
}
static void ail_gil_drop_locked(ail_ctx *cx, ail_thr *t, int save) {
    if (save) {
        t->frames = cx->frames;
        t->exc = cx->exc;
        t->exc_pending = cx->exc_pending;
        t->limit = cx->limit;
    }
    ail_gil_locked = 0;
    pthread_cond_signal(&ail_gil_cv);
}

/* a loop back-edge after another thread asked: hand the lock over and queue up again */
static void ail_gil_yield(ail_ctx *cx) {
    ail_thr *t = ail_th_cur;
    pthread_mutex_lock(&ail_gil_mu);
    ail_gil_drop_locked(cx, t, 1);
    if (ail_gil_waiting) {
        uint64_t seen = ail_gil_switches;
        while (ail_gil_switches == seen && ail_gil_waiting) pthread_cond_wait(&ail_gil_sw_cv, &ail_gil_mu);
    }
    ail_gil_take_locked(cx, t);
    pthread_mutex_unlock(&ail_gil_mu);
}
#define AIL_GIL_CHECK(cx) do { if (__builtin_expect(__atomic_load_n(&ail_gil_drop, __ATOMIC_RELAXED), 0)) ail_gil_yield(cx); } while (0)

/* around a blocking call that touches no AIL value */
static ail_thr *ail_gil_release(ail_ctx *cx) {
    ail_thr *t = ail_th_cur;
    pthread_mutex_lock(&ail_gil_mu);
    ail_gil_drop_locked(cx, t, 1);
    pthread_mutex_unlock(&ail_gil_mu);
    return t;
}
static void ail_gil_acquire(ail_ctx *cx, ail_thr *t) {
    pthread_mutex_lock(&ail_gil_mu);
    ail_gil_take_locked(cx, t);
    pthread_mutex_unlock(&ail_gil_mu);
}

static inline void ail_thr_mark_one(ail_thr *r) {
    if (r != ail_th_cur) {
        for (ail_frame *f = r->frames; f; f = f->prev)
            for (int32_t i = 0; i < f->n; i++) ail_gc_mark_value(f->slots[i]);
        if (r->exc_pending) {
            ail_gc_mark_value(r->exc.cls);
            ail_gc_mark_value(r->exc.msg);
            ail_gc_mark_value(r->exc.value);
        }
    }
    if (r->tobj.tag != AIL_T_UNBOUND) ail_gc_mark_value(r->tobj);
}
static inline void ail_thr_mark_roots(ail_ctx *cx) {
    (void)cx;
    ail_thr_mark_one(&ail_th_main);
    for (ail_thr *r = ail_th_list; r; r = r->next) ail_thr_mark_one(r);
}

static double ail_th_num(ail_obj x) {
    if (x.tag == AIL_T_INT || x.tag == AIL_T_BOOL) return (double)x.i;
    if (x.tag == AIL_T_FLOAT) return ail_float_val(x);
    return -1.0;
}

/* wait until the notify generation moves past g, or secs pass (secs < 0: no limit) */
static int ail_th_wait_gen(ail_ctx *cx, int64_t g, double secs) {
    ail_thr *t = ail_th_cur;
    int moved = 1;
    pthread_mutex_lock(&ail_gil_mu);
    if (ail_th_gen == g) {
        struct timespec ts;
        if (secs >= 0) ail_th_abstime(&ts, secs);
        ail_gil_drop_locked(cx, t, 1);
        while (ail_th_gen == g) {
            int rc = secs < 0 ? pthread_cond_wait(&ail_th_cv, &ail_gil_mu)
                              : pthread_cond_timedwait(&ail_th_cv, &ail_gil_mu, &ts);
            if (rc == ETIMEDOUT) break;
        }
        moved = ail_th_gen != g;
        ail_gil_take_locked(cx, t);
    }
    pthread_mutex_unlock(&ail_gil_mu);
    return moved;
}
static void ail_th_bump(void) {
    pthread_mutex_lock(&ail_gil_mu);
    ail_th_gen++;
    pthread_cond_broadcast(&ail_th_cv);
    pthread_mutex_unlock(&ail_gil_mu);
}

static ail_st ail_th_p_gen(ail_ctx *cx, ail_obj *out) { (void)cx; *out = ail_box_int(ail_th_gen); return AIL_OK; }
static ail_st ail_th_p_notify(ail_ctx *cx, ail_obj *out) { (void)cx; ail_th_bump(); *out = ail_box_none(); return AIL_OK; }
static ail_st ail_th_p_wait(ail_ctx *cx, ail_obj *out, ail_obj g, ail_obj secs) {
    *out = ail_box_bool(ail_th_wait_gen(cx, g.tag == AIL_T_INT ? g.i : 0, ail_th_num(secs)));
    return AIL_OK;
}
static ail_st ail_th_p_ident(ail_ctx *cx, ail_obj *out) { (void)cx; *out = ail_box_int(ail_th_cur->ident); return AIL_OK; }
static ail_st ail_th_p_done(ail_ctx *cx, ail_obj *out, ail_obj id) {
    (void)cx;
    int64_t want = id.tag == AIL_T_INT ? id.i : -1;
    int done = want != 1;
    for (ail_thr *r = ail_th_list; r; r = r->next) if (r->ident == want) { done = 0; break; }
    *out = ail_box_bool(done);
    return AIL_OK;
}
static ail_st ail_th_p_now(ail_ctx *cx, ail_obj *out) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    *out = ail_box_float(cx, (double)ts.tv_sec + (double)ts.tv_nsec / 1e9);
    return AIL_OK;
}
static ail_st ail_th_p_cpus(ail_ctx *cx, ail_obj *out) {
    (void)cx;
    long n = 1;
#ifdef _WIN32
    SYSTEM_INFO si; GetSystemInfo(&si); n = (long)si.dwNumberOfProcessors;
#else
    n = sysconf(_SC_NPROCESSORS_ONLN);
#endif
    *out = ail_box_int(n > 0 ? n : 1);
    return AIL_OK;
}
/* the line CPython's threading.excepthook ends with (no traceback here) */
static ail_st ail_th_p_report(ail_ctx *cx, ail_obj *out, ail_obj name, ail_obj e) {
    fputs("Exception in thread ", stderr);
    if (name.tag == AIL_T_STR) ail_str_write(ail_view_to_str(name), stderr);
    fputs(":\nTraceback (most recent call last):\n  (no traceback in compiled code)\n", stderr);
    if (e.tag == AIL_T_INST || e.tag == AIL_T_EXC) {
        ail_instobj *ii = (ail_instobj *)e.o;
        if (ii->cls.tag == AIL_T_CLASS) ail_str_write(ail_view_to_str(((ail_classobj *)ii->cls.o)->name), stderr);
        ail_obj msg = ail_obj_str(cx, e);
        if (msg.tag == AIL_T_STR && msg.sv.len > 0) { fputs(": ", stderr); ail_str_write(ail_view_to_str(msg), stderr); }
    }
    fputc('\n', stderr);
    fflush(stderr);
    *out = ail_box_none();
    return AIL_OK;
}

/* raise a caught exception object again (Future.result() of a call that raised) */
static ail_st ail_th_p_raise(ail_ctx *cx, ail_obj *out, ail_obj e) {
    *out = ail_box_none();
    if (e.tag != AIL_T_INST && e.tag != AIL_T_EXC)
        return ail_raise_c(cx, AIL_B_TYPEERROR, "exceptions must derive from BaseException");
    ail_instobj *ii = (ail_instobj *)e.o;
    ail_obj msg = ail_box_unbound();
    for (int64_t i = 0; i < ii->n; i++) if (ii->attrs[i].name_id == AIL_ATTR_MESSAGE) msg = ii->attrs[i].val;
    if (msg.tag != AIL_T_STR) msg = ail_obj_str(cx, e);
    ail_st st = ail_raise(cx, ii->cls, msg);
    cx->exc.value = e;
    return st;
}

/* the end of a thread: leave the list, wake the joiners, let the lock go for good */
static void ail_th_finish_self(ail_ctx *cx, ail_thr *t) {
    for (ail_thr **p = &ail_th_list; *p; p = &(*p)->next) if (*p == t) { *p = t->next; break; }
    pthread_mutex_lock(&ail_gil_mu);
    ail_th_gen++;
    pthread_cond_broadcast(&ail_th_cv);
    ail_gil_drop_locked(cx, t, 0);
    pthread_mutex_unlock(&ail_gil_mu);
    free(t);
}
static void *ail_th_entry(void *p) {
    ail_thr *t = (ail_thr *)p;
    ail_ctx *cx = t->cx;
    ail_gil_acquire(cx, t);
    ail_st st;
    {
        AIL_FRAME_ENTER(cx, f, 2);
        f.slots[0] = t->tobj;
        st = ail_th_body_fn(cx, &f.slots[1], f.slots[0]);
        AIL_FRAME_LEAVE(cx, f);
    }
    if (st == AIL_LIMIT) {
        ail_out_flush(cx);
        if (cx->limit.name && !strcmp(cx->limit.name, "int_overflow")) {
            fputs("integer overflow\n", stderr);      /* as the main thread ends it (ail_main_finish) */
            fflush(stderr);
            _exit(1);
        }
        fprintf(stderr, "AIL limit: %s\n", cx->limit.name ? cx->limit.name : "?");
        fflush(stderr);
        _exit(3);
    }
    if (st == AIL_EXC) {
        ail_classobj *c = (ail_classobj *)cx->exc.cls.o;
        fputs("Exception in thread:\n", stderr);
        ail_str_write(ail_view_to_str(c->name), stderr);
        fputs(": ", stderr);
        ail_str_write(ail_view_to_str(cx->exc.msg), stderr);
        fputc('\n', stderr);
        cx->exc_pending = 0;
    }
    ail_th_finish_self(cx, t);
    return NULL;
}
static ail_st ail_th_p_start(ail_ctx *cx, ail_obj *out, ail_obj tobj, ail_obj daemon) {
    ail_thr *t = (ail_thr *)ail_xcalloc(sizeof *t);
    t->tobj = tobj;
    t->daemon = ail_obj_truthy(daemon);
    t->ident = ++ail_th_next_ident;
    t->next = ail_th_list;
    ail_th_list = t;
    t->cx = cx;
    ail_th_any = 1;
    pthread_t pt;
    pthread_attr_t at;
    pthread_attr_init(&at);
    pthread_attr_setdetachstate(&at, PTHREAD_CREATE_DETACHED);
    int rc = pthread_create(&pt, &at, ail_th_entry, t);
    pthread_attr_destroy(&at);
    if (rc) {
        ail_th_list = t->next;
        free(t);
        return ail_raise_c(cx, AIL_B_RUNTIMEERROR, "can't start new thread");
    }
    *out = ail_box_int(t->ident);
    return AIL_OK;
}

/* sys.exit() in a thread other than the main one ends only that thread (SystemExit there is silent) */
static void ail_th_exit_thread(ail_ctx *cx) {
    ail_thr *t = ail_th_cur;
    cx->exc_pending = 0;
    ail_th_finish_self(cx, t);
    pthread_exit(NULL);
}

/* the end of the program (and sys.exit() in the main thread): CPython's threading._shutdown --
   wake the executors' workers, then wait for every thread that is not a daemon */
static int ail_th_finish(ail_ctx *cx, int rc) {
    if (!ail_th_any || rc == 3) return rc;
    cx->exc_pending = 0;
    if (ail_th_atexit_fn) {
        AIL_FRAME_ENTER(cx, f, 1);
        if (ail_th_atexit_fn(cx, &f.slots[0]) != AIL_OK) cx->exc_pending = 0;
        AIL_FRAME_LEAVE(cx, f);
    }
    for (;;) {
        int left = 0;
        for (ail_thr *r = ail_th_list; r; r = r->next) if (!r->daemon) { left = 1; break; }
        if (!left) break;
        ail_th_wait_gen(cx, ail_th_gen, -1.0);
    }
    if (ail_out_flush(cx) != AIL_OK && rc == 0) rc = 1;
    return rc;
}
/* ==== end G12 threads ==== */
'''

_GC_ANCHOR = '    for (int i = 0; i < AIL_B_COUNT; i++) ail_gc_mark_value(cx->builtin_cls[i]);\n'
_GC_FN = 'static inline void ail_gc_collect(ail_ctx *cx) {\n'
_EXIT_ANCHOR = '    ail_ctx_destroy(cx);\n    exit(code);\n'
_EXIT_HEAD = 'static inline void ail2_sys_exit(ail_ctx *cx, int has_arg, ail_obj arg) {\n'
_MAIN_END = '{ int rc = ail_main_finish(cx, st); ail_ctx_destroy(cx); return rc; }'
_SLEEP_ANCHOR = '    int e = ailc_sleep_ns(n);\n    if (e) return ailc_gfail(cx, e);\n'


def _replace_once(text, old, new):
    count = text.count(old)
    if count != 1:
        raise AssertionError('threadrt: expected one %r in the runtime text, found %d' % (old[:60], count))
    return text.replace(old, new)


def patch_head(head):
    """The runtime text with the GC marking every thread's saved state, then the thread runtime."""
    head = _replace_once(head, _GC_FN, 'static inline void ail_thr_mark_roots(ail_ctx *cx);\n' + _GC_FN)
    head = _replace_once(head, _GC_ANCHOR, _GC_ANCHOR + '    ail_thr_mark_roots(cx);\n')
    return head + RUNTIME


def patch_tail(tail):
    """sys.exit(): in a thread it ends the thread; in the main thread it waits for the threads first."""
    tail = _replace_once(tail, _EXIT_HEAD, _EXIT_HEAD + '    if (ail_th_cur != &ail_th_main) ail_th_exit_thread(cx);\n')
    return _replace_once(tail, _EXIT_ANCHOR, '    code = ail_th_finish(cx, code);\n' + _EXIT_ANCHOR)


def patch_main(text):
    """Every exit of the generated main waits for the threads after the main body's own outcome."""
    new = '{ int rc = ail_main_finish(cx, st); rc = ail_th_finish(cx, rc); ail_ctx_destroy(cx); return rc; }'
    if _MAIN_END not in text:
        raise AssertionError('threadrt: the generated main has no exit to patch')
    return text.replace(_MAIN_END, new)


def patch_clock(text):
    """time.sleep() lets the lock go while it sleeps; with the clock pinned (AIL_CLOCK) it only yields."""
    return _replace_once(text, _SLEEP_ANCHOR,
                         '    int e;\n'
                         '    if (ailc_pinned < 0) { int64_t now; e = ailc_clock_ns(&now); if (e) return ailc_gfail(cx, e); }\n'
                         '    if (ailc_pinned) { e = ailc_sleep_ns(n); ail_gil_yield(cx); }\n'
                         '    else { ail_thr *me = ail_gil_release(cx); e = ailc_sleep_ns(n); ail_gil_acquire(cx, me); }\n'
                         '    if (e) return ailc_gfail(cx, e);\n')
