/* Diagnostic only: single-threaded Linux x86-64 program-counter sampling.
 * The workload must not modify SIGPROF, its mask, or ITIMER_PROF.
 * Include after renaming the generated main to ail_sample_subject_main.
 */
#include <signal.h>
#include <limits.h>
#include <stdint.h>
#include <stdatomic.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <time.h>
#include <ucontext.h>

#if !defined(__linux__) || !defined(__x86_64__)
#error This diagnostic sampler requires Linux x86-64
#endif
#ifndef AIL_SAMPLE_CAPACITY
#define AIL_SAMPLE_CAPACITY 65536
#endif
_Static_assert(AIL_SAMPLE_CAPACITY > 0 && AIL_SAMPLE_CAPACITY <= INT_MAX, "sample capacity");
static _Atomic uintptr_t ail_sample_pc[AIL_SAMPLE_CAPACITY];
static _Atomic unsigned int ail_sample_count, ail_sample_dropped;
static void ail_sample_handler(int signal_number, siginfo_t *info, void *context) {
    (void)signal_number; (void)info;
    unsigned int index = atomic_load_explicit(&ail_sample_count, memory_order_relaxed);
    if (index < AIL_SAMPLE_CAPACITY) {
        atomic_store_explicit(&ail_sample_pc[index], (uintptr_t)((ucontext_t *)context)->uc_mcontext.gregs[REG_RIP], memory_order_relaxed);
        atomic_store_explicit(&ail_sample_count, index + 1, memory_order_relaxed);
    } else {
        unsigned int dropped = atomic_load_explicit(&ail_sample_dropped, memory_order_relaxed);
        if (dropped < INT_MAX) atomic_store_explicit(&ail_sample_dropped, dropped + 1, memory_order_relaxed);
    }
}
static double ail_sample_cpu(struct timeval value) {
    return value.tv_sec + value.tv_usec / 1e6;
}
static double ail_sample_wall(struct timespec value) {
    return value.tv_sec + value.tv_nsec / 1e9;
}
static struct timespec ail_sample_start;
static struct rusage ail_sample_before;
static long ail_sample_interval;
static void ail_sample_finish(void) {
    sigset_t mask;
    sigemptyset(&mask);
    sigaddset(&mask, SIGPROF);
    if (sigprocmask(SIG_BLOCK, &mask, NULL)) _Exit(3);
    struct timespec finish;
    struct rusage after;
    if (clock_gettime(CLOCK_MONOTONIC, &finish) || getrusage(RUSAGE_SELF, &after)) _Exit(3);
    struct itimerval disabled = {{0, 0}, {0, 0}};
    if (setitimer(ITIMER_PROF, &disabled, NULL)) _Exit(3);
    /* Keep SIGPROF blocked through exit, including any pending signal. */
    fprintf(stderr, "{\"interval_us\":%ld,\"capacity\":%d,\"dropped\":%d,"
            "\"wall_seconds\":%.9f,\"user_seconds\":%.9f,\"system_seconds\":%.9f,\"pcs\":[",
            ail_sample_interval, AIL_SAMPLE_CAPACITY, (int)ail_sample_dropped,
            ail_sample_wall(finish) - ail_sample_wall(ail_sample_start),
            ail_sample_cpu(after.ru_utime) - ail_sample_cpu(ail_sample_before.ru_utime),
            ail_sample_cpu(after.ru_stime) - ail_sample_cpu(ail_sample_before.ru_stime));
    for (unsigned int i = 0; i < ail_sample_count; i++)
        fprintf(stderr, "%s\"0x%lx\"", i ? "," : "", (unsigned long)ail_sample_pc[i]);
    fputs("]\n}", stderr);
}
int main(int argc, char **argv) {
    if (argc != 4) return 2; /* FILE REPEATS INTERVAL_US; zero disables sampling. */
    if (!atomic_is_lock_free(&ail_sample_pc[0]) || !atomic_is_lock_free(&ail_sample_count)
            || !atomic_is_lock_free(&ail_sample_dropped)) return 3;
    char *end;
    long interval = strtol(argv[3], &end, 10);
    if (!*argv[3] || *end || interval < 0 || interval > 999999) return 2;
    sigset_t mask;
    sigemptyset(&mask);
    sigaddset(&mask, SIGPROF);
    if (sigprocmask(SIG_BLOCK, &mask, NULL)) return 3;
    struct sigaction action = {0};
    action.sa_sigaction = ail_sample_handler;
    action.sa_flags = SA_SIGINFO | SA_RESTART;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGPROF, &action, NULL)) return 3;
    struct itimerval timer = {{0, interval}, {0, interval}};
    if (setitimer(ITIMER_PROF, &timer, NULL)) return 3;
    ail_sample_interval = interval;
    if (atexit(ail_sample_finish)) return 3;
    if (getrusage(RUSAGE_SELF, &ail_sample_before) || clock_gettime(CLOCK_MONOTONIC, &ail_sample_start)) _Exit(3);
    if (sigprocmask(SIG_UNBLOCK, &mask, NULL)) return 3;
    return ail_sample_subject_main(argc - 1, argv);
}
