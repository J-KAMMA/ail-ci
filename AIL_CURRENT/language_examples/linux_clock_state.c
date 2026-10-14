#include <errno.h>
#include <stdio.h>
#include <sys/timex.h>

int main(void) {
    struct timex state = {0}; /* modes == 0: query only; no clock settings. */
    int result = adjtimex(&state);
    if (result < 0) {
        fprintf(stderr, "adjtimex query errno=%d\n", errno);
        return 1;
    }
    printf("{\"modes\":0,\"state\":%d,\"status\":%d,"
           "\"freq_scaled_ppm\":%ld,\"offset\":%ld,\"tick_us\":%ld,"
           "\"maxerror_us\":%ld,\"esterror_us\":%ld}\n",
           result, state.status, state.freq, state.offset, state.tick,
           state.maxerror, state.esterror);
    return 0;
}
