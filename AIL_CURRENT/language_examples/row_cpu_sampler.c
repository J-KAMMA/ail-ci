#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#if !defined(__linux__) || !defined(__x86_64__)
#error "row_cpu_sampler requires Linux x86-64"
#endif
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>
#include <ucontext.h>
#include <unistd.h>

/* Owned single-thread process only: SIGPROF is process-wide, not thread isolation.
 * PC counts estimate CPU attribution; they do not prove causal wall-time costs. */
enum { CAPACITY = 65536, INTERVAL_US = 1000 };
_Static_assert(CAPACITY <= SIG_ATOMIC_MAX, "sample count fits sig_atomic_t");
_Static_assert(ATOMIC_LONG_LOCK_FREE == 2 && ATOMIC_LLONG_LOCK_FREE == 2, "64-bit signal samples must be lock-free");
static _Atomic uint64_t pcs[CAPACITY];
_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "signal counters must be lock-free");
static _Atomic sig_atomic_t sample_count, dropped;
static struct sigaction previous_action;
static struct itimerval previous_timer;
static int report_fd = -1, maps_fd = -1, maps_input_fd = -1;
static int handler_installed, timer_armed, active;
static pid_t sampled_pid;

static void sample_pc(int number, siginfo_t *info, void *context) {
    (void)number;
    (void)info;
    sig_atomic_t index = atomic_load_explicit(&sample_count, memory_order_relaxed);
    if (index < CAPACITY) {
        atomic_store_explicit(&pcs[index], (uint64_t)((ucontext_t *)context)->uc_mcontext.gregs[REG_RIP], memory_order_relaxed);
        atomic_store_explicit(&sample_count, index + 1, memory_order_relaxed);
    } else {
        sig_atomic_t lost = atomic_load_explicit(&dropped, memory_order_relaxed);
        if (lost < SIG_ATOMIC_MAX) atomic_store_explicit(&dropped, lost + 1, memory_order_relaxed);
    }
}

static int write_all(int fd, const void *data, size_t length) {
    const char *cursor = data;
    while (length) {
        ssize_t written = write(fd, cursor, length);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) {
            if (!written) errno = EIO;
            return -1;
        }
        cursor += written;
        length -= (size_t)written;
    }
    return 0;
}

static void failure(const char *stage, const char *reason) {
    int error = errno;
    struct itimerval stopped = {0};
    if (timer_armed) (void)setitimer(ITIMER_PROF, &stopped, NULL);
    if (handler_installed) (void)sigaction(SIGPROF, &previous_action, NULL);
    if (maps_input_fd >= 0) (void)close(maps_input_fd);
    if (maps_fd >= 0) (void)close(maps_fd);
    if (report_fd >= 0) {
        /* This descriptor always belongs to our O_EXCL-created report. */
        if (lseek(report_fd, 0, SEEK_SET) >= 0 && ftruncate(report_fd, 0) == 0)
            (void)dprintf(report_fd,
                "{\"schema\":\"ail.pc_sample/1\",\"status\":\"%s\",\"reason\":\"%s\","
                "\"errno\":%d,\"pid\":%ld,\"interval_us\":%d,\"count\":%ld,\"dropped\":%ld}\n",
                stage, reason, error, (long)sampled_pid, INTERVAL_US,
                (long)sample_count, (long)dropped);
        (void)close(report_fd);
        report_fd = -1;
    }
    /* Setup errors abort in the constructor, before the target main starts.
     * Cleanup/report errors also abort, so a partial file cannot qualify a run. */
    (void)fprintf(stderr, "AIL PC sampler %s: %s (errno=%d)\n", stage, reason, error);
    abort();
}

static void save_maps(const char *path) {
    maps_fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (maps_fd < 0) failure("setup_failed", "maps_open");
    maps_input_fd = open("/proc/self/maps", O_RDONLY | O_CLOEXEC);
    if (maps_input_fd < 0) failure("setup_failed", "maps_read_open");
    char block[8192];
    for (;;) {
        ssize_t length = read(maps_input_fd, block, sizeof block);
        if (length < 0 && errno == EINTR) continue;
        if (length < 0) failure("setup_failed", "maps_read");
        if (!length) break;
        if (write_all(maps_fd, block, (size_t)length)) failure("setup_failed", "maps_write");
    }
    int fd = maps_input_fd;
    maps_input_fd = -1;
    if (close(fd)) failure("setup_failed", "maps_read_close");
    fd = maps_fd;
    maps_fd = -1;
    if (close(fd)) failure("setup_failed", "maps_close");
}

__attribute__((constructor)) static void start_sampling(void) {
    const char *output = getenv("AIL_PC_SAMPLE_OUT");
    if (!output) return;
    sampled_pid = getpid();
    size_t length = strnlen(output, PATH_MAX);
    if (!length || length > PATH_MAX - sizeof ".maps") {
        errno = length ? ENAMETOOLONG : EINVAL;
        failure("setup_failed", "output_path");
    }
    if (sigaction(SIGPROF, NULL, &previous_action)) failure("setup_failed", "handler_query");
    if (getitimer(ITIMER_PROF, &previous_timer)) failure("setup_failed", "timer_query");
    if (previous_action.sa_handler != SIG_DFL || previous_timer.it_value.tv_sec || previous_timer.it_value.tv_usec
            || previous_timer.it_interval.tv_sec || previous_timer.it_interval.tv_usec) {
        errno = EBUSY;
        failure("setup_failed", "existing_handler_or_timer");
    }
    sigset_t selected, previous_mask, pending;
    if (sigemptyset(&selected) || sigaddset(&selected, SIGPROF)) failure("setup_failed", "signal_set");
    if (sigprocmask(SIG_BLOCK, &selected, &previous_mask)) failure("setup_failed", "signal_block");
    if (sigismember(&previous_mask, SIGPROF) == 1) {
        errno = EBUSY;
        failure("setup_failed", "signal_already_blocked");
    }
    if (sigpending(&pending)) failure("setup_failed", "pending_query");
    if (sigismember(&pending, SIGPROF) == 1) {
        errno = EBUSY;
        failure("setup_failed", "signal_already_pending");
    }
    report_fd = open(output, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (report_fd < 0) failure("setup_failed", "report_open");
    char maps_path[PATH_MAX];
    memcpy(maps_path, output, length);
    memcpy(maps_path + length, ".maps", sizeof ".maps");
    save_maps(maps_path);
    struct sigaction action = {0};
    action.sa_sigaction = sample_pc;
    action.sa_flags = SA_SIGINFO;
    if (sigemptyset(&action.sa_mask)) failure("setup_failed", "handler_mask");
    if (sigaction(SIGPROF, &action, NULL)) failure("setup_failed", "handler_install");
    handler_installed = 1;
    struct itimerval timer = { .it_interval = {0, INTERVAL_US}, .it_value = {0, INTERVAL_US} };
    if (setitimer(ITIMER_PROF, &timer, NULL)) failure("setup_failed", "timer_arm");
    timer_armed = active = 1;
    if (sigprocmask(SIG_SETMASK, &previous_mask, NULL)) failure("setup_failed", "signal_restore");
}

__attribute__((destructor)) static void finish_sampling(void) {
    if (!active) return;
    sigset_t selected, current_mask;
    if (sigemptyset(&selected) || sigaddset(&selected, SIGPROF)) failure("cleanup_failed", "signal_set");
    if (sigprocmask(SIG_BLOCK, &selected, &current_mask)) failure("cleanup_failed", "signal_block");
    struct itimerval stopped = {0};
    if (setitimer(ITIMER_PROF, &stopped, NULL)) failure("cleanup_failed", "timer_stop");
    timer_armed = 0;
    /* Consume only the pending sampler tick before restoring default SIGPROF.
     * Application use of SIGPROF during this owned-process profile is unqualified. */
    struct timespec immediate = {0};
    int number;
    do {
        number = sigtimedwait(&selected, NULL, &immediate);
    } while (number == SIGPROF || (number < 0 && errno == EINTR));
    if (number >= 0 || errno != EAGAIN) failure("cleanup_failed", "pending_drain");
    if (sigaction(SIGPROF, &previous_action, NULL)) failure("cleanup_failed", "handler_restore");
    handler_installed = 0;
    if (setitimer(ITIMER_PROF, &previous_timer, NULL)) failure("cleanup_failed", "timer_restore");
    if (sigprocmask(SIG_SETMASK, &current_mask, NULL)) failure("cleanup_failed", "signal_restore");
    active = 0;
    const char *status = dropped ? "buffer_full" : sample_count ? "ok" : "no_samples";
    char line[256];
    int length = snprintf(line, sizeof line,
        "{\"schema\":\"ail.pc_sample/1\",\"status\":\"%s\",\"pid\":%ld,"
        "\"interval_us\":%d,\"count\":%ld,\"dropped\":%ld}\n",
        status, (long)sampled_pid, INTERVAL_US, (long)sample_count, (long)dropped);
    if (length < 0 || (size_t)length >= sizeof line) failure("cleanup_failed", "header_format");
    if (write_all(report_fd, line, (size_t)length)) failure("cleanup_failed", "header_write");
    for (sig_atomic_t index = 0; index < sample_count; index++) {
        length = snprintf(line, sizeof line, "0x%016" PRIx64 "\n", atomic_load_explicit(&pcs[index], memory_order_relaxed));
        if (length < 0 || (size_t)length >= sizeof line) failure("cleanup_failed", "pc_format");
        if (write_all(report_fd, line, (size_t)length)) failure("cleanup_failed", "pc_write");
    }
    int fd = report_fd;
    report_fd = -1;
    if (close(fd)) failure("cleanup_failed", "report_close");
}
