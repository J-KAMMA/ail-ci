/* icount PROG ARGS...: run PROG (stdout to /dev/null) and print its user-space instruction count, or
   CPU cycles with CYCLES=1, via perf_event_open. Build: cc -O2 -w -include signal.h -include stdlib.h
   -o icount tools/icount.c. Deterministic where wall time is noisy (WSL laptop: +-3x). */
#define _GNU_SOURCE
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <fcntl.h>
int main(int argc, char **argv) {
    struct perf_event_attr a; memset(&a, 0, sizeof a);
    a.type = PERF_TYPE_HARDWARE; a.size = sizeof a; a.config = getenv("CYCLES") ? PERF_COUNT_HW_CPU_CYCLES : PERF_COUNT_HW_INSTRUCTIONS;
    a.disabled = 1; a.exclude_kernel = 1; a.exclude_hv = 1; a.enable_on_exec = 1; a.inherit = 1;
    int go[2]; pipe(go);
    pid_t pid = fork();
    if (!pid) { char c; close(go[1]); read(go[0], &c, 1); int fd = open("/dev/null", O_WRONLY); dup2(fd, 1); execvp(argv[1], argv + 1); _exit(127); }
    int fd = syscall(SYS_perf_event_open, &a, pid, -1, -1, 0);
    if (fd < 0) { perror("perf_event_open"); kill(pid, 9); return 1; }
    close(go[0]); write(go[1], "x", 1);
    int st; waitpid(pid, &st, 0);
    uint64_t n = 0; read(fd, &n, sizeof n);
    printf("%llu\n", (unsigned long long)n);
    return 0;
}
