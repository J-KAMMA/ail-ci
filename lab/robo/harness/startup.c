/* Minimal Cortex-M3 startup and semihosting exit for QEMU mps2-an385.

   The AIL runtime is hosted C: it wants malloc, stdio and setjmp. newlib-nano
   supplies those; librdimon (--specs=rdimon.specs) supplies the syscalls over
   QEMU semihosting. This file only provides the vector table the CPU needs at
   address 0 and the reset path: copy .data, zero .bss, open the semihosting
   handles, call main, and stop QEMU with an exit status.
*/
#include <stdint.h>
#include <stdio.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
extern int main(void);
extern void initialise_monitor_handles(void);
extern size_t memcount_peak(void);

static void semihost_exit(int code) {
    /* SYS_EXIT_EXTENDED (0x20) with {ADP_Stopped_ApplicationExit, code}. */
    uint32_t block[2];
    block[0] = 0x20026u;
    block[1] = (uint32_t)code;
    register uint32_t r0 __asm__("r0") = 0x20u;
    register uint32_t r1 __asm__("r1") = (uint32_t)(uintptr_t)block;
    __asm__ volatile("bkpt 0xAB" : : "r"(r0), "r"(r1) : "memory");
    for (;;) {
    }
}

void Reset_Handler(void) {
    uint32_t *src = &_sidata;
    uint32_t *dst = &_sdata;
    while (dst < &_edata) {
        *dst++ = *src++;
    }
    for (uint32_t *b = &_sbss; b < &_ebss;) {
        *b++ = 0u;
    }
    initialise_monitor_handles();
    int rc = main();
    fflush(stdout);
    fprintf(stderr, "heap_peak %u\n", (unsigned)memcount_peak());
    fflush(stderr);
    semihost_exit(rc);
}

void Default_Handler(void) {
    semihost_exit(2);
}

__attribute__((section(".isr_vector"), used))
const void *const g_vectors[16] = {
    &_estack,
    (const void *)Reset_Handler,
    (const void *)Default_Handler, /* NMI */
    (const void *)Default_Handler, /* HardFault */
    (const void *)Default_Handler, /* MemManage */
    (const void *)Default_Handler, /* BusFault */
    (const void *)Default_Handler, /* UsageFault */
    0, 0, 0, 0,
    (const void *)Default_Handler, /* SVCall */
    (const void *)Default_Handler, /* DebugMonitor */
    0,
    (const void *)Default_Handler, /* PendSV */
    (const void *)Default_Handler, /* SysTick */
};
