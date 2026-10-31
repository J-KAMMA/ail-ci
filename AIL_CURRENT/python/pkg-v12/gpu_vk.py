# -*- coding: utf-8 -*-
"""gpu_vk.py -- stage G2/G3 of docs/design/GPU.md: the run-time half of the SPIR-V path.

* `VK_RUNTIME` is C text that goes into a `--gpu` program with at least one kernel.  It opens the Vulkan loader with
  dlopen at RUN TIME (`libvulkan.so.1`; `vulkan-1.dll` on Windows), declares the few Vulkan structs it needs itself (no
  header, no `-lvulkan`), picks a device, and runs one compute pipeline per launch.  Anything missing (no loader, no
  device, no compute queue, a device without the features the kernel needs, an allocation or submit that fails) makes
  `gkv_launch` return 0, and the caller runs the CPU emulation `ail_gk<k>` instead: same flags, same result, same replay.
* `device_text` writes, for one kernel, the SPIR-V words as a `static const uint32_t[]` and the wrapper
  `ail_gk<k>_run` that has the signature of the emulation, tries the device and falls back to the emulation.

Run-time switches (all read once):
    AIL_GPU=0            skip every kernel (the original CPU loop runs; G1)
    AIL_GPU=emu          never touch Vulkan: the C emulation runs (a test mode, slower than the original loop)
    AIL_GPU=force        use the device for every launch, whatever its size
    (unset / auto)       the cost model of GPU.md 6.4 decides per launch: the device when it predicts a clear win, else the
                         ORIGINAL typed loop (the wrapper returns GK_DECLINED); AIL_GPU_MIN_N=<n> replaces the model by
                         "the device for launches of at least n elements"
    AIL_GPU_TRACE=1      one line per launch on stderr: `gpu: k0 n=4096 device=llvmpipe (LLVM 20.1.2, 256 bits)`;
                         `gpu: k0 device unavailable (<why>)` when the device was wanted and not used
    AIL_GPU_DEVICE=name  use the first device whose name contains `name`
    AIL_VULKAN_LIB=path  open this loader instead of the default (a test hook: a path that does not exist = no Vulkan)
    AIL_GPU_DISABLE=...  test hook: pretend the device lacks the features named in the value (f64 i64 rte szinp)
    AIL_GPU_CHECK=first  (default) device trust, GPU.md 6.3: before a kernel is first trusted it runs a self-test (4096 operand
                         sets of edge and random values, device against CPU emulation); the first real launch is compared with
                         the emulation on its first 4096 elements.  `all` compares every launch; `0` skips both (measuring only).
                         A difference marks the device untrusted for that class (binary64 or int64) for the process.
    AIL_GPU_INJECT=m[:s] test hook: corrupt the device's answers (m = flip | negzero | noflag; s = selftest | launch)
"""
import gpu_spirv

VK_RUNTIME = r'''
#ifndef AIL_GKV_RT
#define AIL_GKV_RT
#include <time.h>
#include <math.h>
/* GPU.md stages G2/G3: Vulkan compute through a loader opened at run time.  Struct layouts below are the 64-bit ABI of
   vulkan_core.h (checked against the header by test_ail_gpu_g2.py). */
#ifdef _WIN32
#include <windows.h>
#define GKV_OPEN(n) ((void *)LoadLibraryA(n))
#define GKV_SYM(h, n) ((void *)GetProcAddress((HMODULE)(h), n))
#define GKV_LIBNAME "vulkan-1.dll"
#else
#include <dlfcn.h>
#define GKV_OPEN(n) dlopen((n), RTLD_NOW | RTLD_LOCAL)
#define GKV_SYM(h, n) dlsym((h), (n))
#define GKV_LIBNAME "libvulkan.so.1"
#endif
#define GKV_UNUSED __attribute__((unused))
typedef struct { int32_t sType; const void *pNext; const char *pApplicationName; uint32_t applicationVersion; const char *pEngineName; uint32_t engineVersion; uint32_t apiVersion; } gkv_AppInfo;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; const gkv_AppInfo *pApplicationInfo; uint32_t enabledLayerCount; const char *const *ppEnabledLayerNames; uint32_t enabledExtensionCount; const char *const *ppEnabledExtensionNames; } gkv_InstanceCI;
typedef struct { uint32_t f[55]; } gkv_Features;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; uint32_t queueFamilyIndex; uint32_t queueCount; const float *pQueuePriorities; } gkv_QueueCI;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; uint32_t queueCreateInfoCount; const gkv_QueueCI *pQueueCreateInfos; uint32_t enabledLayerCount; const char *const *ppEnabledLayerNames; uint32_t enabledExtensionCount; const char *const *ppEnabledExtensionNames; const gkv_Features *pEnabledFeatures; } gkv_DeviceCI;
typedef struct { uint32_t queueFlags; uint32_t queueCount; uint32_t timestampValidBits; uint32_t minImageTransferGranularity[3]; } gkv_QueueFamily;
typedef struct { uint32_t propertyFlags; uint32_t heapIndex; } gkv_MemType;
typedef struct { uint64_t size; uint32_t flags; } gkv_MemHeap;
typedef struct { uint32_t memoryTypeCount; gkv_MemType memoryTypes[32]; uint32_t memoryHeapCount; gkv_MemHeap memoryHeaps[16]; } gkv_MemProps;
typedef struct { int32_t sType; void *pNext; uint32_t denormBehaviorIndependence; uint32_t roundingModeIndependence;
    uint32_t szinp16, szinp32, szinp64, dpres16, dpres32, dpres64, dftz16, dftz32, dftz64, rte16, rte32, rte64, rtz16, rtz32, rtz64; } gkv_FloatCtl;
typedef struct { int32_t sType; void *pNext; unsigned char p[824] __attribute__((aligned(8))); } gkv_Props2;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; uint64_t size; uint32_t usage; uint32_t sharingMode; uint32_t queueFamilyIndexCount; const uint32_t *pQueueFamilyIndices; } gkv_BufferCI;
typedef struct { uint64_t size; uint64_t alignment; uint32_t memoryTypeBits; } gkv_MemReq;
typedef struct { int32_t sType; const void *pNext; uint64_t allocationSize; uint32_t memoryTypeIndex; } gkv_MemAlloc;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; size_t codeSize; const uint32_t *pCode; } gkv_ShaderCI;
typedef struct { uint32_t binding; uint32_t descriptorType; uint32_t descriptorCount; uint32_t stageFlags; const uint64_t *pImmutableSamplers; } gkv_DSLBinding;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; uint32_t bindingCount; const gkv_DSLBinding *pBindings; } gkv_DSLCI;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; uint32_t setLayoutCount; const uint64_t *pSetLayouts; uint32_t pushConstantRangeCount; const void *pPushConstantRanges; } gkv_PLCI;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; uint32_t stage; uint64_t module; const char *pName; const void *pSpecializationInfo; } gkv_StageCI;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; gkv_StageCI stage; uint64_t layout; uint64_t basePipelineHandle; int32_t basePipelineIndex; } gkv_ComputeCI;
typedef struct { uint32_t type; uint32_t descriptorCount; } gkv_PoolSize;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; uint32_t maxSets; uint32_t poolSizeCount; const gkv_PoolSize *pPoolSizes; } gkv_DPCI;
typedef struct { int32_t sType; const void *pNext; uint64_t descriptorPool; uint32_t descriptorSetCount; const uint64_t *pSetLayouts; } gkv_DSAI;
typedef struct { uint64_t buffer; uint64_t offset; uint64_t range; } gkv_DBInfo;
typedef struct { int32_t sType; const void *pNext; uint64_t dstSet; uint32_t dstBinding; uint32_t dstArrayElement; uint32_t descriptorCount; uint32_t descriptorType; const void *pImageInfo; const gkv_DBInfo *pBufferInfo; const void *pTexelBufferView; } gkv_Write;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; uint32_t queueFamilyIndex; } gkv_CmdPoolCI;
typedef struct { int32_t sType; const void *pNext; uint64_t commandPool; uint32_t level; uint32_t commandBufferCount; } gkv_CmdBufAI;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; const void *pInheritanceInfo; } gkv_CmdBeginInfo;
typedef struct { int32_t sType; const void *pNext; uint32_t waitSemaphoreCount; const uint64_t *pWaitSemaphores; const uint32_t *pWaitDstStageMask; uint32_t commandBufferCount; const void *const *pCommandBuffers; uint32_t signalSemaphoreCount; const uint64_t *pSignalSemaphores; } gkv_SubmitInfo;
typedef struct { int32_t sType; const void *pNext; uint32_t flags; } gkv_FenceCI;

#define GKV_API12 ((1u << 22) | (2u << 12))
#define GKV_MAXPIPES 128
typedef struct { const uint32_t *spv; uint64_t module, dsl, layout, pipe; int ok; } gkv_pipe;
typedef struct { uint64_t buf, mem; void *ptr; uint64_t cap; int cached; } gkv_buf;   /* a mapped host-visible buffer that later launches reuse */
static struct {
    int state;                     /* 0 untried, 1 ready, -1 unusable */
    const char *why;
    char name[256];
    void *lib, *inst, *pd, *dev, *queue;
    uint64_t cpool;
    uint32_t family;
    int has_f64, has_i64, szinp64, rte64, szinp32, rte32;
    uint32_t devtype;              /* VkPhysicalDeviceType: 1 integrated, 2 discrete, 3 virtual, 4 cpu */
    uint32_t driver, vendor;       /* VkPhysicalDeviceProperties.driverVersion / vendorID */
    unsigned untrusted;            /* GKV_T_* classes a self-test or a check found different from the emulation */
    int st;                        /* 1 while a self-test is running (the test hook can aim at it) */
    char distrust[240];
    double build_us;               /* time spent building pipelines so far (the self-test reports its own time without it) */
    uint64_t max_range;
    gkv_MemProps mem;
    int npipes;
    gkv_pipe pipes[GKV_MAXPIPES];
    gkv_buf pool[43];              /* buffers kept between launches: parameters, flags, result, one per input list (GPU.md 6.4) */
    void *(*gipa)(void *, const char *);
    int32_t (*vkCreateInstance)(const gkv_InstanceCI *, const void *, void **);
    int32_t (*vkEnumeratePhysicalDevices)(void *, uint32_t *, void **);
    void (*vkGetPhysicalDeviceProperties2)(void *, gkv_Props2 *);
    void (*vkGetPhysicalDeviceFeatures)(void *, gkv_Features *);
    void (*vkGetPhysicalDeviceQueueFamilyProperties)(void *, uint32_t *, gkv_QueueFamily *);
    void (*vkGetPhysicalDeviceMemoryProperties)(void *, gkv_MemProps *);
    int32_t (*vkCreateDevice)(void *, const gkv_DeviceCI *, const void *, void **);
    void (*vkGetDeviceQueue)(void *, uint32_t, uint32_t, void **);
    int32_t (*vkCreateShaderModule)(void *, const gkv_ShaderCI *, const void *, uint64_t *);
    int32_t (*vkCreateDescriptorSetLayout)(void *, const gkv_DSLCI *, const void *, uint64_t *);
    int32_t (*vkCreatePipelineLayout)(void *, const gkv_PLCI *, const void *, uint64_t *);
    int32_t (*vkCreateComputePipelines)(void *, uint64_t, uint32_t, const gkv_ComputeCI *, const void *, uint64_t *);
    int32_t (*vkCreateBuffer)(void *, const gkv_BufferCI *, const void *, uint64_t *);
    void (*vkDestroyBuffer)(void *, uint64_t, const void *);
    void (*vkGetBufferMemoryRequirements)(void *, uint64_t, gkv_MemReq *);
    int32_t (*vkAllocateMemory)(void *, const gkv_MemAlloc *, const void *, uint64_t *);
    void (*vkFreeMemory)(void *, uint64_t, const void *);
    int32_t (*vkBindBufferMemory)(void *, uint64_t, uint64_t, uint64_t);
    int32_t (*vkMapMemory)(void *, uint64_t, uint64_t, uint64_t, uint32_t, void **);
    void (*vkUnmapMemory)(void *, uint64_t);
    int32_t (*vkCreateDescriptorPool)(void *, const gkv_DPCI *, const void *, uint64_t *);
    void (*vkDestroyDescriptorPool)(void *, uint64_t, const void *);
    int32_t (*vkAllocateDescriptorSets)(void *, const gkv_DSAI *, uint64_t *);
    void (*vkUpdateDescriptorSets)(void *, uint32_t, const gkv_Write *, uint32_t, const void *);
    int32_t (*vkCreateCommandPool)(void *, const gkv_CmdPoolCI *, const void *, uint64_t *);
    int32_t (*vkAllocateCommandBuffers)(void *, const gkv_CmdBufAI *, void **);
    int32_t (*vkBeginCommandBuffer)(void *, const gkv_CmdBeginInfo *);
    int32_t (*vkEndCommandBuffer)(void *);
    void (*vkCmdBindPipeline)(void *, uint32_t, uint64_t);
    void (*vkCmdBindDescriptorSets)(void *, uint32_t, uint64_t, uint32_t, uint32_t, const uint64_t *, uint32_t, const uint32_t *);
    void (*vkCmdDispatch)(void *, uint32_t, uint32_t, uint32_t);
    int32_t (*vkCreateFence)(void *, const gkv_FenceCI *, const void *, uint64_t *);
    void (*vkDestroyFence)(void *, uint64_t, const void *);
    int32_t (*vkWaitForFences)(void *, uint32_t, const uint64_t *, uint32_t, uint64_t);
    int32_t (*vkQueueSubmit)(void *, uint32_t, const gkv_SubmitInfo *, uint64_t);
    int32_t (*vkResetCommandPool)(void *, uint64_t, uint32_t);
} gkv_G;

static GKV_UNUSED double gkv_now_us(void) {
#ifdef _WIN32
    LARGE_INTEGER f, c; QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c);
    return (double)c.QuadPart * 1e6 / (double)f.QuadPart;
#else
    struct timespec t; timespec_get(&t, TIME_UTC);
    return (double)t.tv_sec * 1e6 + (double)t.tv_nsec / 1e3;
#endif
}
static GKV_UNUSED double gkv_envd(const char *name, double dflt) { const char *e = getenv(name); return e && e[0] ? atof(e) : dflt; }
static GKV_UNUSED const char *gkv_dev_name(void) { return gkv_G.name[0] ? gkv_G.name : "vulkan"; }

#define GKV_LOAD(inst_, fn) do { *(void **)&gkv_G.fn = gkv_G.gipa((inst_), #fn); if (!gkv_G.fn) { gkv_G.why = "the loader lacks " #fn; return 0; } } while (0)

static GKV_UNUSED int gkv_init(void) {
    if (gkv_G.state) return gkv_G.state > 0;
    gkv_G.state = -1;
#ifdef GKV_STATIC
    gkv_G.why = "a static build never opens the Vulkan loader (a statically linked glibc cannot dlopen it safely)";
    return 0;
#endif
    gkv_G.why = "no Vulkan loader (" GKV_LIBNAME ")";
    const char *lib = getenv("AIL_VULKAN_LIB");
    gkv_G.lib = GKV_OPEN(lib && lib[0] ? lib : GKV_LIBNAME);
    if (!gkv_G.lib) return 0;
    *(void **)&gkv_G.gipa = GKV_SYM(gkv_G.lib, "vkGetInstanceProcAddr");
    if (!gkv_G.gipa) { gkv_G.why = "the loader has no vkGetInstanceProcAddr"; return 0; }
    GKV_LOAD(NULL, vkCreateInstance);
    gkv_AppInfo app; memset(&app, 0, sizeof app);
    app.sType = 0; app.pApplicationName = "ail"; app.apiVersion = GKV_API12;
    gkv_InstanceCI ici; memset(&ici, 0, sizeof ici);
    ici.sType = 1; ici.pApplicationInfo = &app;
    if (gkv_G.vkCreateInstance(&ici, 0, &gkv_G.inst) != 0) { gkv_G.why = "vkCreateInstance failed (no Vulkan 1.2 driver?)"; return 0; }
    GKV_LOAD(gkv_G.inst, vkEnumeratePhysicalDevices);
    GKV_LOAD(gkv_G.inst, vkGetPhysicalDeviceProperties2);
    GKV_LOAD(gkv_G.inst, vkGetPhysicalDeviceFeatures);
    GKV_LOAD(gkv_G.inst, vkGetPhysicalDeviceQueueFamilyProperties);
    GKV_LOAD(gkv_G.inst, vkGetPhysicalDeviceMemoryProperties);
    GKV_LOAD(gkv_G.inst, vkCreateDevice);
    uint32_t nd = 0;
    void *devs[16];
    if (gkv_G.vkEnumeratePhysicalDevices(gkv_G.inst, &nd, 0) != 0 || nd == 0) { gkv_G.why = "no Vulkan device"; return 0; }
    if (nd > 16) nd = 16;
    if (gkv_G.vkEnumeratePhysicalDevices(gkv_G.inst, &nd, devs) < 0 || nd == 0) { gkv_G.why = "no Vulkan device"; return 0; }
    const char *want = getenv("AIL_GPU_DEVICE");
    int best = -1, best_rank = 99;
    uint32_t best_type = 0;
    uint32_t best_family = 0;
    gkv_G.why = "no Vulkan 1.2 device with a compute queue";
    for (uint32_t d = 0; d < nd; d++) {
        gkv_FloatCtl fc; memset(&fc, 0, sizeof fc); fc.sType = 1000197000;
        gkv_Props2 pr; memset(&pr, 0, sizeof pr); pr.sType = 1000059001; pr.pNext = &fc;
        gkv_G.vkGetPhysicalDeviceProperties2(devs[d], &pr);
        uint32_t api, type;
        memcpy(&api, pr.p, 4); memcpy(&type, pr.p + 16, 4);
        if (api < GKV_API12) continue;
        if (want && want[0] && !strstr((const char *)pr.p + 20, want)) continue;
        uint32_t nq = 0;
        gkv_G.vkGetPhysicalDeviceQueueFamilyProperties(devs[d], &nq, 0);
        gkv_QueueFamily qf[16];
        if (nq > 16) nq = 16;
        gkv_G.vkGetPhysicalDeviceQueueFamilyProperties(devs[d], &nq, qf);
        int fam = -1;
        for (uint32_t q = 0; q < nq; q++) if ((qf[q].queueFlags & 2u) && qf[q].queueCount > 0) { fam = (int)q; break; }
        if (fam < 0) continue;
        int rank = type == 2 ? 0 : type == 1 ? 1 : type == 3 ? 2 : type == 4 ? 3 : 4;   /* discrete, integrated, virtual, cpu */
        if (rank < best_rank) { best = (int)d; best_rank = rank; best_family = (uint32_t)fam; best_type = type; }
    }
    if (best < 0) return 0;
    gkv_G.pd = devs[best]; gkv_G.family = best_family; gkv_G.devtype = best_type;
    {
        gkv_FloatCtl fc; memset(&fc, 0, sizeof fc); fc.sType = 1000197000;
        gkv_Props2 pr; memset(&pr, 0, sizeof pr); pr.sType = 1000059001; pr.pNext = &fc;
        gkv_G.vkGetPhysicalDeviceProperties2(gkv_G.pd, &pr);
        strncpy(gkv_G.name, (const char *)pr.p + 20, 255); gkv_G.name[255] = 0;
        memcpy(&gkv_G.driver, pr.p + 4, 4); memcpy(&gkv_G.vendor, pr.p + 8, 4);
        memcpy(&gkv_G.max_range, pr.p + 296 + 28, 4); gkv_G.max_range &= 0xffffffffu;
        gkv_G.szinp64 = fc.szinp64 != 0; gkv_G.rte64 = fc.rte64 != 0;
        gkv_G.szinp32 = fc.szinp32 != 0; gkv_G.rte32 = fc.rte32 != 0;
    }
    gkv_Features feat; memset(&feat, 0, sizeof feat);
    gkv_G.vkGetPhysicalDeviceFeatures(gkv_G.pd, &feat);
    gkv_G.has_f64 = feat.f[39] != 0; gkv_G.has_i64 = feat.f[40] != 0;
    {   /* test hook: pretend the device lacks features (f64 i64 rte szinp), to exercise the fallbacks */
        const char *dis = getenv("AIL_GPU_DISABLE");
        if (dis && dis[0]) {
            if (strstr(dis, "f64")) gkv_G.has_f64 = 0;
            if (strstr(dis, "i64")) gkv_G.has_i64 = 0;
            if (strstr(dis, "rte")) gkv_G.rte64 = 0;
            if (strstr(dis, "szinp")) gkv_G.szinp64 = 0;
            if (strstr(dis, "f32ctl")) { gkv_G.szinp32 = 0; gkv_G.rte32 = 0; }
        }
    }
    gkv_Features on; memset(&on, 0, sizeof on);
    on.f[39] = feat.f[39]; on.f[40] = feat.f[40];
    gkv_G.vkGetPhysicalDeviceMemoryProperties(gkv_G.pd, &gkv_G.mem);
    float prio = 1.0f;
    gkv_QueueCI qci; memset(&qci, 0, sizeof qci);
    qci.sType = 2; qci.queueFamilyIndex = gkv_G.family; qci.queueCount = 1; qci.pQueuePriorities = &prio;
    gkv_DeviceCI dci; memset(&dci, 0, sizeof dci);
    dci.sType = 3; dci.queueCreateInfoCount = 1; dci.pQueueCreateInfos = &qci; dci.pEnabledFeatures = &on;
    if (gkv_G.vkCreateDevice(gkv_G.pd, &dci, 0, &gkv_G.dev) != 0) { gkv_G.why = "vkCreateDevice failed"; return 0; }
    GKV_LOAD(gkv_G.inst, vkGetDeviceQueue);
    GKV_LOAD(gkv_G.inst, vkCreateShaderModule);
    GKV_LOAD(gkv_G.inst, vkCreateDescriptorSetLayout);
    GKV_LOAD(gkv_G.inst, vkCreatePipelineLayout);
    GKV_LOAD(gkv_G.inst, vkCreateComputePipelines);
    GKV_LOAD(gkv_G.inst, vkCreateBuffer);
    GKV_LOAD(gkv_G.inst, vkDestroyBuffer);
    GKV_LOAD(gkv_G.inst, vkGetBufferMemoryRequirements);
    GKV_LOAD(gkv_G.inst, vkAllocateMemory);
    GKV_LOAD(gkv_G.inst, vkFreeMemory);
    GKV_LOAD(gkv_G.inst, vkBindBufferMemory);
    GKV_LOAD(gkv_G.inst, vkMapMemory);
    GKV_LOAD(gkv_G.inst, vkUnmapMemory);
    GKV_LOAD(gkv_G.inst, vkCreateDescriptorPool);
    GKV_LOAD(gkv_G.inst, vkDestroyDescriptorPool);
    GKV_LOAD(gkv_G.inst, vkAllocateDescriptorSets);
    GKV_LOAD(gkv_G.inst, vkUpdateDescriptorSets);
    GKV_LOAD(gkv_G.inst, vkCreateCommandPool);
    GKV_LOAD(gkv_G.inst, vkAllocateCommandBuffers);
    GKV_LOAD(gkv_G.inst, vkBeginCommandBuffer);
    GKV_LOAD(gkv_G.inst, vkEndCommandBuffer);
    GKV_LOAD(gkv_G.inst, vkCmdBindPipeline);
    GKV_LOAD(gkv_G.inst, vkCmdBindDescriptorSets);
    GKV_LOAD(gkv_G.inst, vkCmdDispatch);
    GKV_LOAD(gkv_G.inst, vkCreateFence);
    GKV_LOAD(gkv_G.inst, vkDestroyFence);
    GKV_LOAD(gkv_G.inst, vkWaitForFences);
    GKV_LOAD(gkv_G.inst, vkQueueSubmit);
    GKV_LOAD(gkv_G.inst, vkResetCommandPool);
    gkv_G.vkGetDeviceQueue(gkv_G.dev, gkv_G.family, 0, &gkv_G.queue);
    gkv_CmdPoolCI cpi; memset(&cpi, 0, sizeof cpi);
    cpi.sType = 39; cpi.queueFamilyIndex = gkv_G.family;
    if (gkv_G.vkCreateCommandPool(gkv_G.dev, &cpi, 0, &gkv_G.cpool) != 0) { gkv_G.why = "vkCreateCommandPool failed"; return 0; }
    gkv_G.state = 1; gkv_G.why = "";
    return 1;
}

static int gkv_memtype(uint32_t bits, int cached) {
    if (cached)       /* the result is read back by the CPU: host-cached memory reads far faster than write-combined memory */
        for (uint32_t i = 0; i < gkv_G.mem.memoryTypeCount; i++)
            if ((bits & (1u << i)) && (gkv_G.mem.memoryTypes[i].propertyFlags & 14u) == 14u) return (int)i;
    for (uint32_t i = 0; i < gkv_G.mem.memoryTypeCount; i++)
        if ((bits & (1u << i)) && (gkv_G.mem.memoryTypes[i].propertyFlags & 6u) == 6u) return (int)i;     /* host visible + coherent */
    return -1;
}
static void gkv_rmbuf(gkv_buf *b);
/* The buffer of a pool slot: the one from the last launch when it is big enough (no allocation, no new pages to fault in),
   otherwise a new one.  The memory stays mapped. */
static int gkv_mkbuf(gkv_buf *b, uint64_t size, int cached) {
    if (size < 16) size = 16;
    if (b->buf && b->ptr && b->cap >= size && b->cached == cached) return 1;
    gkv_rmbuf(b);
    b->cap = size; b->cached = cached;
    gkv_BufferCI ci; memset(&ci, 0, sizeof ci);
    ci.sType = 12; ci.size = size; ci.usage = 0x20u;
    if (gkv_G.vkCreateBuffer(gkv_G.dev, &ci, 0, &b->buf) != 0) { b->buf = 0; return 0; }
    gkv_MemReq rq; memset(&rq, 0, sizeof rq);
    gkv_G.vkGetBufferMemoryRequirements(gkv_G.dev, b->buf, &rq);
    int mt = gkv_memtype(rq.memoryTypeBits, cached);
    if (mt < 0) return 0;
    gkv_MemAlloc ai; memset(&ai, 0, sizeof ai);
    ai.sType = 5; ai.allocationSize = rq.size; ai.memoryTypeIndex = (uint32_t)mt;
    if (gkv_G.vkAllocateMemory(gkv_G.dev, &ai, 0, &b->mem) != 0) { b->mem = 0; return 0; }
    if (gkv_G.vkBindBufferMemory(gkv_G.dev, b->buf, b->mem, 0) != 0) return 0;
    if (gkv_G.vkMapMemory(gkv_G.dev, b->mem, 0, ~0ull, 0, &b->ptr) != 0) { b->ptr = 0; return 0; }
    return 1;
}
static void gkv_rmbuf(gkv_buf *b) {
    if (b->ptr) gkv_G.vkUnmapMemory(gkv_G.dev, b->mem);
    if (b->buf) gkv_G.vkDestroyBuffer(gkv_G.dev, b->buf, 0);
    if (b->mem) gkv_G.vkFreeMemory(gkv_G.dev, b->mem, 0);
    memset(b, 0, sizeof *b);
}

/* test hook AIL_GPU_INJECT=<flip|negzero|noflag>[:selftest|:launch]: a "bad driver".  flip changes the last bit of every
   result word, negzero turns +0.0 results into -0.0 (the lavapipe `0.0 - x` finding of G2), noflag hides the flag word. */
static GKV_UNUSED void gkv_inject_init(int *m, int *scope) {
    static int mm = -1, sc = 3;
    if (mm < 0) {
        const char *e = getenv("AIL_GPU_INJECT");
        mm = 0;
        if (e && e[0]) {
            mm = strstr(e, "flip") ? 1 : strstr(e, "negzero") ? 2 : strstr(e, "noflag") ? 3 : 0;
            sc = strstr(e, ":selftest") ? 1 : strstr(e, ":launch") ? 2 : 3;
        }
    }
    *m = mm; *scope = sc;
}
static GKV_UNUSED int gkv_inject_flag(void) { int m, sc; gkv_inject_init(&m, &sc); return m == 3 && (sc & (gkv_G.st ? 1 : 2)); }
static GKV_UNUSED void gkv_inject(void *res, int64_t cnt, int copied) {
    int m, sc; gkv_inject_init(&m, &sc);
    if (!copied || m == 0 || m == 3 || !(sc & (gkv_G.st ? 1 : 2))) return;
    uint64_t *w = (uint64_t *)res;
    for (int64_t i = 0; i < cnt; i++) { if (m == 1) w[i] ^= 1u; else if (w[i] == 0) w[i] = 1ull << 63; }
}

/* the pipeline of one kernel, built on its first launch and kept */
static gkv_pipe *gkv_pipe_for(const uint32_t *spv, uint32_t nwords, int nbind) {
    for (int i = 0; i < gkv_G.npipes; i++) if (gkv_G.pipes[i].spv == spv) return gkv_G.pipes[i].ok ? &gkv_G.pipes[i] : 0;
    if (gkv_G.npipes >= GKV_MAXPIPES) { gkv_G.why = "too many kernels"; return 0; }
    gkv_pipe *p = &gkv_G.pipes[gkv_G.npipes++];
    double t0 = gkv_now_us();
    memset(p, 0, sizeof *p); p->spv = spv;
    gkv_ShaderCI sci; memset(&sci, 0, sizeof sci);
    sci.sType = 16; sci.codeSize = (size_t)nwords * 4; sci.pCode = spv;
    if (gkv_G.vkCreateShaderModule(gkv_G.dev, &sci, 0, &p->module) != 0) { gkv_G.why = "vkCreateShaderModule rejected the SPIR-V"; return 0; }
    gkv_DSLBinding bind[40];
    if (nbind > 40) { gkv_G.why = "too many lists"; return 0; }
    for (int i = 0; i < nbind; i++) { memset(&bind[i], 0, sizeof bind[i]); bind[i].binding = (uint32_t)i; bind[i].descriptorType = 7; bind[i].descriptorCount = 1; bind[i].stageFlags = 0x20u; }
    gkv_DSLCI dci; memset(&dci, 0, sizeof dci);
    dci.sType = 32; dci.bindingCount = (uint32_t)nbind; dci.pBindings = bind;
    if (gkv_G.vkCreateDescriptorSetLayout(gkv_G.dev, &dci, 0, &p->dsl) != 0) { gkv_G.why = "vkCreateDescriptorSetLayout failed"; return 0; }
    gkv_PLCI pli; memset(&pli, 0, sizeof pli);
    pli.sType = 30; pli.setLayoutCount = 1; pli.pSetLayouts = &p->dsl;
    if (gkv_G.vkCreatePipelineLayout(gkv_G.dev, &pli, 0, &p->layout) != 0) { gkv_G.why = "vkCreatePipelineLayout failed"; return 0; }
    gkv_ComputeCI cpi; memset(&cpi, 0, sizeof cpi);
    cpi.sType = 29; cpi.stage.sType = 18; cpi.stage.stage = 0x20u; cpi.stage.module = p->module; cpi.stage.pName = "main";
    cpi.layout = p->layout; cpi.basePipelineIndex = -1;
    if (gkv_G.vkCreateComputePipelines(gkv_G.dev, 0, 1, &cpi, 0, &p->pipe) != 0) { gkv_G.why = "vkCreateComputePipelines failed"; return 0; }
    p->ok = 1;
    gkv_G.build_us += gkv_now_us() - t0;
    return p;
}

/* One launch.  Returns 1 when the device ran the kernel (*flag is its flag word; `res` holds the result iff *flag == 0),
   0 when it did not (nothing in the caller's memory was touched).  Buffers live for the launch only. */
static GKV_UNUSED int gkv_launch_ex(const uint32_t *spv, uint32_t nwords, int need, int nl, int nprm, uint64_t *prm,
                                    const void *const *lp, const int64_t *ln, void *res, int64_t cnt, uint64_t gx, uint64_t gy,
                                    unsigned *flag, int all) {
    /* `need`: bit 0 = binary64 features, bit 1 = binary32 float controls (RTE and signed zero/inf/NaN preservation for 32 bits);
       `cnt` = elements of the result buffer; (gx, gy) = workgroups dispatched (the matmul kernels of gpu_matmul.py use their own grid) */
    if (!gkv_init()) return 0;
    if (!gkv_G.has_i64) { gkv_G.why = "the device lacks shaderInt64"; return 0; }
    if ((need & 1) && !(gkv_G.has_f64 && gkv_G.szinp64 && gkv_G.rte64)) {
        gkv_G.why = "the device lacks shaderFloat64, signed-zero/inf/NaN preservation or round-to-nearest-even for binary64";
        return 0;
    }
    if ((need & 2) && !(gkv_G.szinp32 && gkv_G.rte32)) {
        gkv_G.why = "the device lacks signed-zero/inf/NaN preservation or round-to-nearest-even for binary32";
        return 0;
    }
    if (cnt <= 0 || cnt > ((int64_t)1 << 40)) { gkv_G.why = "launch size out of range"; return 0; }
    if (gx == 0 || gy == 0 || gx > 65535 || gy > 65535) { gkv_G.why = "launch too large"; return 0; }
    if ((uint64_t)cnt * 8 > gkv_G.max_range) { gkv_G.why = "result larger than maxStorageBufferRange"; return 0; }
    for (int i = 0; i < nl; i++) if ((uint64_t)ln[i] * 8 > gkv_G.max_range) { gkv_G.why = "input larger than maxStorageBufferRange"; return 0; }
    if (nl > 36) { gkv_G.why = "too many lists"; return 0; }
    int nb = 3 + nl, ok = 0, have_cb = 0, have_pool = 0, have_fence = 0;
    gkv_buf *bufs = gkv_G.pool;
    int made = 0;
    uint64_t pool = 0, fence = 0, set = 0;
    void *cb = 0;
    gkv_pipe *p = gkv_pipe_for(spv, nwords, nb);
    if (!p) return 0;
    if (!gkv_mkbuf(&bufs[made++], (uint64_t)nprm * 8, 0)) { gkv_G.why = "device memory: params"; goto done; }
    if (!gkv_mkbuf(&bufs[made++], 4, 1)) { gkv_G.why = "device memory: flags"; goto done; }
    if (!gkv_mkbuf(&bufs[made++], (uint64_t)cnt * 8, 1)) { gkv_G.why = "device memory: result"; goto done; }
    for (int i = 0; i < nl; i++) {
        if (!gkv_mkbuf(&bufs[made++], (uint64_t)ln[i] * 8, 0)) { gkv_G.why = "device memory: input"; goto done; }
        if (ln[i] > 0) memcpy(bufs[made - 1].ptr, lp[i], (size_t)ln[i] * 8);
    }
    memcpy(bufs[0].ptr, prm, (size_t)nprm * 8);
    memset(bufs[1].ptr, 0, 4);
    {
        gkv_PoolSize ps; ps.type = 7; ps.descriptorCount = (uint32_t)nb;
        gkv_DPCI dpi; memset(&dpi, 0, sizeof dpi);
        dpi.sType = 33; dpi.maxSets = 1; dpi.poolSizeCount = 1; dpi.pPoolSizes = &ps;
        if (gkv_G.vkCreateDescriptorPool(gkv_G.dev, &dpi, 0, &pool) != 0) { gkv_G.why = "vkCreateDescriptorPool failed"; goto done; }
        have_pool = 1;
        gkv_DSAI dai; memset(&dai, 0, sizeof dai);
        dai.sType = 34; dai.descriptorPool = pool; dai.descriptorSetCount = 1; dai.pSetLayouts = &p->dsl;
        if (gkv_G.vkAllocateDescriptorSets(gkv_G.dev, &dai, &set) != 0) { gkv_G.why = "vkAllocateDescriptorSets failed"; goto done; }
        gkv_DBInfo info[43]; gkv_Write wr[43];
        for (int i = 0; i < nb; i++) {
            info[i].buffer = bufs[i].buf; info[i].offset = 0; info[i].range = ~0ull;
            memset(&wr[i], 0, sizeof wr[i]);
            wr[i].sType = 35; wr[i].dstSet = set; wr[i].dstBinding = (uint32_t)i; wr[i].descriptorCount = 1; wr[i].descriptorType = 7; wr[i].pBufferInfo = &info[i];
        }
        gkv_G.vkUpdateDescriptorSets(gkv_G.dev, (uint32_t)nb, wr, 0, 0);
    }
    {
        gkv_CmdBufAI ai; memset(&ai, 0, sizeof ai);
        ai.sType = 40; ai.commandPool = gkv_G.cpool; ai.commandBufferCount = 1;
        if (gkv_G.vkAllocateCommandBuffers(gkv_G.dev, &ai, &cb) != 0) { gkv_G.why = "vkAllocateCommandBuffers failed"; goto done; }
        have_cb = 1;
        gkv_CmdBeginInfo bi; memset(&bi, 0, sizeof bi); bi.sType = 42; bi.flags = 1u;
        if (gkv_G.vkBeginCommandBuffer(cb, &bi) != 0) { gkv_G.why = "vkBeginCommandBuffer failed"; goto done; }
        gkv_G.vkCmdBindPipeline(cb, 1, p->pipe);
        gkv_G.vkCmdBindDescriptorSets(cb, 1, p->layout, 0, 1, &set, 0, 0);
        gkv_G.vkCmdDispatch(cb, (uint32_t)gx, (uint32_t)gy, 1);
        if (gkv_G.vkEndCommandBuffer(cb) != 0) { gkv_G.why = "vkEndCommandBuffer failed"; goto done; }
        gkv_FenceCI fci; memset(&fci, 0, sizeof fci); fci.sType = 8;
        if (gkv_G.vkCreateFence(gkv_G.dev, &fci, 0, &fence) != 0) { gkv_G.why = "vkCreateFence failed"; goto done; }
        have_fence = 1;
        gkv_SubmitInfo si; memset(&si, 0, sizeof si);
        si.sType = 4; si.commandBufferCount = 1; si.pCommandBuffers = (const void *const *)&cb;
        if (gkv_G.vkQueueSubmit(gkv_G.queue, 1, &si, fence) != 0) { gkv_G.why = "vkQueueSubmit failed"; gkv_G.state = -1; goto done; }
        if (gkv_G.vkWaitForFences(gkv_G.dev, 1, &fence, 1, ~0ull) != 0) { gkv_G.why = "vkWaitForFences failed"; gkv_G.state = -1; goto done; }
    }
    {
        uint32_t f; memcpy(&f, bufs[1].ptr, 4);
        if (gkv_inject_flag()) f = 0;
        *flag = f;
        if (f == 0 || all) memcpy(res, bufs[2].ptr, (size_t)cnt * 8);      /* `all`: the self-test also reads the clean elements of a flagged launch */
        gkv_inject(res, cnt, f == 0 || all);
        ok = 1;
    }
done:
    if (have_cb) gkv_G.vkResetCommandPool(gkv_G.dev, gkv_G.cpool, 0);
    if (have_fence) gkv_G.vkDestroyFence(gkv_G.dev, fence, 0);
    if (have_pool) gkv_G.vkDestroyDescriptorPool(gkv_G.dev, pool, 0);
    {   /* the buffers stay for the next launch, up to AIL_GPU_KEEP_MB (default 512); after a failure they are all released */
        static uint64_t keep = ~0ull;
        if (keep == ~0ull) keep = (uint64_t)gkv_envd("AIL_GPU_KEEP_MB", 512.0) * 1048576ull;
        uint64_t held = 0;
        for (int i = 0; i < 43; i++) held += gkv_G.pool[i].cap;
        if (!ok || held > keep) for (int i = 0; i < 43; i++) gkv_rmbuf(&gkv_G.pool[i]);
    }
    return ok;
}

static GKV_UNUSED int gkv_launch(const uint32_t *spv, uint32_t nwords, int need_f64, int nl, int nprm, uint64_t *prm,
                                 const void *const *lp, const int64_t *ln, void *res, int64_t cnt, unsigned *flag, int all) {
    if (cnt <= 0 || cnt > ((int64_t)1 << 40)) { gkv_G.why = "launch size out of range"; return 0; }
    uint64_t groups = ((uint64_t)cnt + 63) / 64;
    uint64_t gx = groups < 65535 ? groups : 65535, gy = (groups + gx - 1) / gx;
    prm[2] = gx * 64;
    return gkv_launch_ex(spv, nwords, need_f64, nl, nprm, prm, lp, ln, res, cnt, gx, gy, flag, all);
}

static GKV_UNUSED int gkv_mode(void) {         /* 0 emulation only (AIL_GPU=emu), 1 auto (default), 2 always (AIL_GPU=force) */
    static int v = -1;
    if (v < 0) {
        const char *e = getenv("AIL_GPU");
        v = (e && !strcmp(e, "emu")) ? 0 : (e && !strcmp(e, "force")) ? 2 : 1;
    }
    return v;
}
static GKV_UNUSED int64_t gkv_min_n(void) {   /* AIL_GPU_MIN_N: when set, the size rule alone decides (no cost model); -1 = unset */
    static int64_t v = -2;
    if (v == -2) { const char *e = getenv("AIL_GPU_MIN_N"); v = e && e[0] ? (int64_t)atoll(e) : -1; if (v < -1) v = 0; }
    return v;
}
static GKV_UNUSED double gkv_max(double a, double b) { return a > b ? a : b; }
static GKV_UNUSED double gkv_trip(double lo, double hi) { return hi > lo ? hi - lo : 0.0; }

/* ---- the cost model (GPU.md 6.4) ---------------------------------------------------------------------------------------
   Fitted on the Radeon 780M (Windows driver), three kernels, n = 4096..10^7, with the buffer pool of this stage (before
   it the fixed cost was 4.5 ms and the copy 0.21 ns per byte):
       t_cpu = n * ops * 0.20 ns                              (the plain typed loop, one thread; measured 0.15 to 0.36)
       t_dev = 0.3 ms + bytes * 0.17 ns + n * ops * 0.06 ns   (fixed launch, copy in/out, arithmetic)
   `ops` is the kernel's IR operation count per element (gpu.py ops_expr), `bytes` what moves through the buffers (inputs
   and result).  A launch goes to the device only when t_cpu >= 1.5 * t_dev (a safety margin on a fit that is itself noisy
   by 10 to 70 percent), the device is not software (a Vulkan CPU device never beats the plain loop it shares cores with)
   and the process-wide cold start (instance, device, self-test: 120 to 370 ms measured) has been paid back by what the
   declined launches would have saved: ski rental, so a program that would launch once pays at most the cold start it
   earned (AIL_GPU_STRICT=1: only a single launch that saves more than the cold start goes).  Constants are overridable for tests and measurements: AIL_GPU_MODEL=fixed_us,ns_per_byte,ns_per_op_dev,
   ns_per_op_cpu,margin,init_us. */
static GKV_UNUSED void gkv_trace_why(int k);
static double gkv_credit;
static GKV_UNUSED int gkv_model_win(int64_t n, double bytes, double ops, double *tc, double *td) {
    static double c[6] = { 300.0, 0.17, 0.06, 0.20, 1.5, 300000.0 };
    static int got;
    if (!got) {
        got = 1;
        const char *e = getenv("AIL_GPU_MODEL");
        if (e && e[0]) { char *q = (char *)e; for (int i = 0; i < 6 && *q; i++) { c[i] = strtod(q, &q); if (*q == ',') q++; } }
    }
    if (ops < 1.0) ops = 1.0;
    *td = c[0] + (bytes * c[1] + (double)n * ops * c[2]) / 1000.0;
    *tc = (double)n * ops * c[3] / 1000.0;
    if (!(*tc >= c[4] * *td)) return 0;
    if (gkv_G.state == 0) {                   /* cold start still to pay: only once the declined launches' savings would cover it */
        if (getenv("AIL_GPU_STRICT")) { if (*tc - *td < c[5]) return -1; }   /* strict: one launch has to pay for the cold start by itself */
        else { gkv_credit += *tc - *td; if (gkv_credit < c[5]) return -1; }
    }
    return 1;
}
/* 0 declined (the caller runs the original loop), 1 the emulation, 2 the device (it may still decline: no loader, untrusted) */
static GKV_UNUSED int gkv_decide(int k, int64_t n, double bytes, double ops) {
    int m = gkv_mode();
    if (m == 0) return 1;
    if (m == 2) return 2;
    if (gkv_min_n() >= 0) {
        if (n >= gkv_min_n()) return 2;
        if (gk_tracing()) fprintf(stderr, "gpu: k%d declined (n = %lld is below AIL_GPU_MIN_N = %lld)\n", k, (long long)n, (long long)gkv_min_n());
        return 0;
    }
    double tc, td;
    int w = gkv_model_win(n, bytes, ops, &tc, &td);
    if (w <= 0) {
        if (gk_tracing())
            fprintf(stderr, "gpu: k%d declined (n = %lld, %.0f ops: predicted device %.0f us, plain loop %.0f us%s)\n", k, (long long)n, ops, td, tc,
                    w < 0 ? "; the device cold start is not yet repaid" : ", not a clear win");
        return 0;
    }
    if (!gkv_init()) { gkv_trace_why(k); return 0; }
    if ((gkv_G.devtype == 3 || gkv_G.devtype == 4) && !getenv("AIL_GPU_AUTO_ANY")) {
        gkv_G.why = "a software device never beats the plain loop"; gkv_trace_why(k); return 0;
    }
    return 2;
}

/* ---- device trust (GPU.md 6.3) ---------------------------------------------------------------------------------------
   A driver's shader compiler may rewrite a float pattern although the module forbids it (lavapipe turned `0.0 - x` into
   `-x` despite NoContraction).  So no device is trusted for a kernel before it has answered, bit for bit like the CPU
   emulation, a fixed set of 4096 adversarial operand sets (signed zeros, inf, NaN, subnormals, the 2**-1000 guard
   boundary, cancellation, int64 limits and overflow, out-of-range indices) run through THAT kernel's own SPIR-V; and the
   first real launch of the kernel is compared with the emulation on its first 4096 elements.  A difference marks the
   class (binary64 or int64) untrusted for the rest of the process: every kernel of the class takes the CPU path. */
#define GKV_T_I64 1u
#define GKV_T_F64 2u
#define GKV_CHK_N 4096
#define GKV_ST_M 4096
#define GKV_ST_SINGLES 6
static GKV_UNUSED int gkv_check_mode(void) {      /* 0 off, 1 self-test + first launch, 2 every launch too */
    static int v = -1;
    if (v < 0) { const char *e = getenv("AIL_GPU_CHECK"); v = (e && !strcmp(e, "0")) ? 0 : (e && !strcmp(e, "all")) ? 2 : 1; }
    return v;
}
static GKV_UNUSED int gkv_usable(unsigned mask) {     /* the device exists and no class this kernel needs is distrusted */
    if (!gkv_init()) return 0;
    if (gkv_G.untrusted & mask) { gkv_G.why = gkv_G.distrust; return 0; }
    return 1;
}
static GKV_UNUSED void gkv_distrust(unsigned cls, int k, const char *what, long long at) {
    gkv_G.untrusted |= cls;
    snprintf(gkv_G.distrust, sizeof gkv_G.distrust, "device untrusted for %s kernels: k%d %s (element %lld); the CPU path runs",
             cls == GKV_T_F64 ? "binary64" : "int64", k, what, at);
    gkv_G.why = gkv_G.distrust;
    if (gk_tracing())
        fprintf(stderr, "gpu: k%d device %s (driver 0x%08x, vendor 0x%04x) differs from the CPU emulation: %s (element %lld); untrusted for %s kernels, the CPU path runs\n",
                k, gkv_dev_name(), gkv_G.driver, gkv_G.vendor, what, at, cls == GKV_T_F64 ? "binary64" : "int64");
}
static GKV_UNUSED void gkv_trace_selftest(int k, int64_t clean, int64_t flagged, int singles, double us, double build) {
    if (gk_tracing())
        fprintf(stderr, "gpu: k%d selftest ok device=%s driver=0x%08x vendor=0x%04x (%d operand sets: %lld clean compared, %lld flagged, %d single launches; %.0f us, plus %.0f us to build the pipeline, which the first launch needs anyway)\n",
                k, gkv_dev_name(), gkv_G.driver, gkv_G.vendor, GKV_ST_M, (long long)clean, (long long)flagged, singles, us, build);
}

/* operand sets of the self-test: the edge values of the bit tests of test_ail_gpu_g2.py in a pair table for the first
   33*33 (28*28) elements, then neighbours of the previous list's value (equal, negated, +-ulps, halved) and random bits */
static const double gkv_ef[] = { 0.0, -0.0, 1.0, -1.0, 0.5, 2.0, 1.5, 3.0, 0.1, 1e300, -1e300, 1.7976931348623157e308, -1.7976931348623157e308,
    2.2250738585072014e-308, 4.9406564584124654e-324, 1e-310, -1e-310, 9.332636185032189e-302, 9.3326361850321887e-302, 1e-300, -1e-300,
    4503599627370496.0, 4503599627370497.5, 9007199254740992.0, 9007199254740993.0, 9223372036854775808.0, -9223372036854775808.0,
    9.2233720368547748e18, 1e19, -1e19, 2147483648.0, 123456789.123, 0.30000000000000004 };
static const int64_t gkv_ei[] = { 0, 1, -1, 2, -2, 3, 7, -7, 100, -100, INT64_MAX, INT64_MAX - 1, INT64_MIN, INT64_MIN + 1,
    2147483647LL, 2147483648LL, -2147483648LL, 4294967296LL, 3037000499LL, 3037000500LL, -3037000500LL, 4611686018427387904LL,
    4611686018427387903LL, -4611686018427387904LL, 9007199254740992LL, 9007199254740993LL, -9007199254740993LL, 6148914691236517205LL };
static uint64_t gkv_rs;
static uint64_t gkv_rnd(void) { gkv_rs ^= gkv_rs << 13; gkv_rs ^= gkv_rs >> 7; gkv_rs ^= gkv_rs << 17; return gkv_rs; }
static double gkv_dof(uint64_t b) { double d; memcpy(&d, &b, 8); return d; }
static uint64_t gkv_bof(double d) { uint64_t b; memcpy(&b, &d, 8); return b; }
static double gkv_rf(void) {
    switch (gkv_rnd() % 9) {
    case 0: case 1: return gkv_dof(gkv_rnd());
    case 2: case 3: return gkv_ef[gkv_rnd() % (sizeof gkv_ef / sizeof gkv_ef[0])];
    case 4: return gkv_dof((gkv_rnd() & 0x800fffffffffffffull) | ((gkv_rnd() % 48) << 52));               /* tiny and subnormal */
    case 5: return gkv_dof((gkv_rnd() & 0x800fffffffffffffull) | ((uint64_t)(1023 - 1015 + gkv_rnd() % 32) << 52));   /* around 2**-1000 */
    case 6: return (double)((int64_t)(gkv_rnd() % 201) - 100);
    case 7: return (double)(int64_t)gkv_rnd();
    default: return gkv_dof((gkv_rnd() & 0x800fffffffffffffull) | ((uint64_t)(1023 - 30 + gkv_rnd() % 60) << 52));
    }
}
static double gkv_rf_near(double a) {
    switch (gkv_rnd() % 6) {
    case 0: return a;
    case 1: return -a;
    case 2: return gkv_dof(gkv_bof(a) + gkv_rnd() % 5);
    case 3: return gkv_dof(gkv_bof(a) - gkv_rnd() % 5);
    case 4: return a * 0.5;
    default: return gkv_rf();
    }
}
static int64_t gkv_ri(void) {
    switch (gkv_rnd() % 8) {
    case 0: case 1: return (int64_t)gkv_rnd();
    case 2: case 3: return gkv_ei[gkv_rnd() % (sizeof gkv_ei / sizeof gkv_ei[0])];
    case 4: return (int64_t)(gkv_rnd() % 201) - 100;
    case 5: return (int64_t)(gkv_rnd() >> (1 + gkv_rnd() % 62));
    case 6: return -(int64_t)(gkv_rnd() >> (1 + gkv_rnd() % 62));
    default: return (int64_t)(gkv_rnd() % 2000001) - 1000000;
    }
}
static int64_t gkv_ri_near(int64_t a) {
    switch (gkv_rnd() % 6) {
    case 0: return a;
    case 1: return (int64_t)(0 - (uint64_t)a);
    case 2: return (int64_t)((uint64_t)a + gkv_rnd() % 3);
    case 3: return -(int64_t)(gkv_rnd() % 5) - 1;
    case 4: return (int64_t)(gkv_rnd() % 5);
    default: return gkv_ri();
    }
}
#define GKV_NEF ((int64_t)(sizeof gkv_ef / sizeof gkv_ef[0]))
#define GKV_NEI ((int64_t)(sizeof gkv_ei / sizeof gkv_ei[0]))
static GKV_UNUSED void gkv_fill_f(double *a, int64_t m, int slot, const double *prev) {
    gkv_rs = 88172645463325252ull + 0x9e3779b97f4a7c15ull * (uint64_t)(slot + 1);
    for (int64_t i = 0; i < m; i++) {
        if (i < GKV_NEF * GKV_NEF)
            a[i] = gkv_ef[slot == 0 ? i % GKV_NEF : slot == 1 ? (i / GKV_NEF) % GKV_NEF : (i % GKV_NEF * (2 * slot + 3) + i / GKV_NEF * slot + slot) % GKV_NEF];
        else a[i] = prev ? gkv_rf_near(prev[i]) : gkv_rf();
    }
}
static GKV_UNUSED void gkv_fill_i(int64_t *a, int64_t m, int slot, const int64_t *prev) {
    gkv_rs = 88172645463325252ull + 0x9e3779b97f4a7c15ull * (uint64_t)(slot + 11);
    for (int64_t i = 0; i < m; i++) {
        if (i < GKV_NEI * GKV_NEI)
            a[i] = gkv_ei[slot == 0 ? i % GKV_NEI : slot == 1 ? (i / GKV_NEI) % GKV_NEI : (i % GKV_NEI * (2 * slot + 3) + i / GKV_NEI * slot + slot) % GKV_NEI];
        else a[i] = prev ? gkv_ri_near(prev[i]) : gkv_ri();
    }
}

/* G5: operand sets for the block-sum and block-dot kernels (one invocation per block of 1024 elements, 16 lanes of 64 adds).  The
   generic sets above are almost all flagged once 1024 of them are added (one NaN or subnormal flags the block), which would
   test nothing; these blocks are mostly clean and each has a character: rounding of a repeated 0.1, absorption (1e16 + 1),
   signed zeros, overflow to inf, one inf, cancellation with a residue, powers of two, exact integers, ties at 2**52, and a few
   that must flag (NaN, a subnormal, inf - inf). */
#define GKV_ST_BLOCKS 64
#define GKV_CHK_BLOCKS 8
static const double gkv_eb[] = { 0.0, -0.0, 1.0, -1.0, 0.5, 2.0, 1.5, 3.0, 0.1, -0.1, 1e300, -1e300, 1.7976931348623157e308, 2.2250738585072014e-308,
    4503599627370496.0, 4503599627370497.5, 9007199254740992.0, 123456789.123, 0.30000000000000004, 1e-300, -1e-300, 1e16, -1e16, 1e-5 };
static double gkv_rb_mid(void) {
    switch (gkv_rnd() % 4) {
    case 0: return gkv_dof((gkv_rnd() & 0x800fffffffffffffull) | ((uint64_t)(1023 - 30 + gkv_rnd() % 60) << 52));
    case 1: return (double)((int64_t)(gkv_rnd() % 2001) - 1000);
    case 2: return 0.1 * (double)((int64_t)(gkv_rnd() % 41) - 20);
    default: return gkv_dof((gkv_rnd() & 0x800fffffffffffffull) | ((uint64_t)(1023 - 100 + gkv_rnd() % 200) << 52));
    }
}
static double gkv_rb(void) {
    if (gkv_rnd() % 64 == 0) return gkv_eb[gkv_rnd() % (sizeof gkv_eb / sizeof gkv_eb[0])];
    return gkv_rb_mid();
}
static GKV_UNUSED void gkv_fill_blocks(double *a, int64_t m, int slot) {
    gkv_rs = 88172645463325252ull + 0x9e3779b97f4a7c15ull * (uint64_t)(slot + 21);
    for (int64_t b = 0; b * 1024 < m; b++) {
        int pat = (int)((b + 3 * slot) % 16);
        int pos = (int)((b * 37 + slot * 11) % 1024);
        for (int64_t j = 0; j < 1024 && b * 1024 + j < m; j++) {
            int64_t i = b * 1024 + j;
            double v;
            switch (pat) {
            case 0: v = gkv_rb(); break;
            case 1: v = 0.1; break;
            case 2: v = (j % 4 == 0) ? 1e16 : (j % 4 == 2) ? -1e16 : 1.0; break;
            case 3: v = -0.0; break;
            case 4: v = (gkv_rnd() & 1) ? 0.0 : -0.0; break;
            case 5: v = (gkv_rnd() % 7) ? 1.7e308 : -1.0; break;
            case 6: v = j == pos ? INFINITY : gkv_rb_mid(); break;
            case 7: v = ((gkv_rnd() & 1) ? 1.0 : -1.0) * 1e-300 * (double)(1 + gkv_rnd() % 5); break;
            case 8: v = j < 512 ? gkv_rb_mid() : -a[i - 512]; break;
            case 9: v = ((gkv_rnd() & 1) ? 1.0 : -1.0) * ldexp(1.0, (int)(gkv_rnd() % 121) - 60); break;
            case 10: v = (double)((int64_t)(gkv_rnd() % 2001) - 1000); break;
            case 11: v = (j & 1) ? 0.5 : 4503599627370496.0; break;
            case 12: v = j == pos ? NAN : gkv_rb_mid(); break;
            case 13: v = j == pos ? 4.9406564584124654e-324 : gkv_rb_mid(); break;
            case 14: v = j == 3 ? INFINITY : j == 19 ? -INFINITY : gkv_rb_mid(); break;
            default: v = gkv_dof(gkv_rnd()); break;
            }
            a[i] = v;
        }
    }
}

static GKV_UNUSED void gkv_trace_why(int k) { if (gk_tracing()) fprintf(stderr, "gpu: k%d device unavailable (%s)\n", k, gkv_G.why && gkv_G.why[0] ? gkv_G.why : "not used"); }
#endif
'''


def runtime_text():
    """The runtime block for this build.  `AIL_STATIC=1` on Linux/macOS links libc statically; a static glibc cannot
    dlopen the Vulkan loader (it segfaults), so such a build always takes the CPU path and says why in the trace
    (GPU.md 2.4).  Windows builds are static by default and use LoadLibrary, which is fine."""
    import os
    static = os.environ.get('AIL_STATIC') == '1' and not (os.name == 'nt' or os.environ.get('AIL_TARGET_OS') == 'windows')
    return ('#define GKV_STATIC 1\n' if static else '') + VK_RUNTIME


def _words_c(words):
    rows = []
    for i in range(0, len(words), 8):
        rows.append('    ' + ', '.join('0x%08xu' % w for w in words[i:i + 8]))
    return ',\n'.join(rows)


def device_text(kernel, name, k, ops_c='1.0'):
    """(C text, info, words) for the kernel: the SPIR-V array and `<name>_run`, which has the signature of `<name>` (the
    emulation), tries the device and falls back to the emulation.  Before the device is trusted for this kernel it passes
    the self-test `<name>_selftest`, and its first real launch is compared with the emulation (`<name>_agree`): GPU.md 6.3.
    Raises gpu_spirv.Unsupported."""
    words, info = gpu_spirv.compile_kernel(kernel)
    lists = info['lists']
    nl, nprm = len(lists), len(info['params'])
    scal = [(n, t) for n, t in info['params'][3 + nl:]]               # ('s_x', 'i'|'f') in parameter order
    ct = lambda t: 'double' if t == 'f' else 'int64_t'
    params = []
    for lst in lists:
        params += ['const %s *p_%s' % (ct(kernel.lists[lst]), lst), 'int64_t n_%s' % lst]
    for sc, t in kernel.scalars.items():
        params.append('%s s_%s' % (ct(t), sc))
    for sc, (t, value) in kernel.consts.items():
        params.append('%s s_%s' % (ct(t), sc))
    if kernel.loop_var:
        params.append('int64_t _lo')
    res_c = ct(kernel.res_type)
    params += ['int64_t _cnt', '%s *_res' % res_c]
    names = []
    for lst in lists:
        names += ['p_' + lst, 'n_' + lst]
    names += ['s_' + sc for sc in kernel.scalars] + ['s_' + sc for sc in kernel.consts]
    if kernel.loop_var:
        names.append('_lo')
    names += ['_cnt', '_res']
    elem_lists = {lst for _c, _t, lst in kernel.elems}
    safe = not (elem_lists & set(kernel.reads))      # elements can be run one at a time (shifted element lists)
    block = getattr(kernel, 'kind', None) in ('sum', 'dot')       # G5: one invocation per block of 1024 elements
    st_cnt = 'GKV_ST_BLOCKS' if block else 'GKV_ST_M'           # self-test: invocations, and the length of every list
    st_len = 'GKV_ST_BLOCKS * 1024' if block else 'GKV_ST_M'
    chk_n = 'GKV_CHK_BLOCKS' if block else 'GKV_CHK_N'

    mask = 'GKV_T_F64 | GKV_T_I64' if info['need_f64'] else 'GKV_T_I64'
    cls = 'GKV_T_F64' if info['need_f64'] else 'GKV_T_I64'

    def args_at(ie, cnt, res):
        """The arguments of an emulation/_dev call that runs element `ie` (count `cnt`, results at `res`)."""
        out = []
        for lst in lists:
            if lst in elem_lists:
                out += ['p_%s + %s' % (lst, ie), 'n_%s - %s' % (lst, ie)]
            else:
                out += ['p_' + lst, 'n_' + lst]
        out += ['s_' + sc for sc in kernel.scalars] + ['s_' + sc for sc in kernel.consts]
        if kernel.loop_var:
            out.append('_lo + %s' % ie)
        return out + [cnt, res]

    L = ['/* GPU.md G2: SPIR-V of kernel k%d (%s) */' % (k, gpu_spirv.disassemble_hint(words)),
         'static const uint32_t %s_spv[%d] = {\n%s\n};' % (name, len(words), _words_c(words)),
         'static int %s_state, %s_first;       /* state: 0 untested, 1 trusted, -1 not used (untrusted, or the device cannot run it) */' % (name, name),
         '',
         '/* the device alone: 1 when it ran the kernel (_all: also read the results of a flagged launch) */',
         'static int %s_dev(%s, unsigned *_fl, int _all) {' % (name, ', '.join(params)),
         '    uint64_t prm[%d]; memset(prm, 0, sizeof prm);' % max(nprm, 1),
         '    prm[0] = (uint64_t)_cnt;']
    if kernel.loop_var:
        L.append('    prm[1] = (uint64_t)_lo;')
    for j, lst in enumerate(lists):
        L.append('    prm[%d] = (uint64_t)n_%s;' % (3 + j, lst))
    for j, (pname, t) in enumerate(scal):
        slot = 3 + nl + j
        if t == 'f':
            L.append('    memcpy(&prm[%d], &%s, 8);' % (slot, pname))
        else:
            L.append('    prm[%d] = (uint64_t)%s;' % (slot, pname))
    L.append('    const void *lp[%d]; int64_t ln[%d];' % (max(nl, 1), max(nl, 1)))
    for j, lst in enumerate(lists):
        L.append('    lp[%d] = p_%s; ln[%d] = n_%s;' % (j, lst, j, lst))
    L += ['    return gkv_launch(%s_spv, %d, %d, %d, %d, prm, lp, ln, _res, _cnt, _fl, _all);' % (
              name, len(words), 1 if info['need_f64'] else 0, nl, max(nprm, 1)),
          '}', '']

    # the device's answer against the emulation on the first elements of a real launch
    L += ['/* 1 when the device results in _res (valid iff _df == 0) equal the emulation on the first GKV_CHK_N elements; *_at = element */',
          'static int %s_agree(%s, unsigned _df, long long *_at, const char **_what) {' % (name, ', '.join(params)),
          '    int64_t _m = _cnt < %s ? _cnt : %s;' % (chk_n, chk_n),
          '    if (_df != 0) return 1;                  /* replayed anyway: nothing of the device is used */']
    if safe:
        L += ['    for (int64_t _i = 0; _i < _m; _i++) {',
              '        %s _t; unsigned _ef = %s(%s);' % (res_c, name, ', '.join(args_at('_i', '1', '&_t'))),
              '        if (_ef) { *_at = _i; *_what = "the device did not flag what the emulation flags"; return 0; }',
              '        if (memcmp(&_t, &_res[_i], 8) != 0) { *_at = _i; *_what = "result bits differ"; return 0; }',
              '    }',
              '    return 1;']
    else:
        L += ['    %s *_t = (%s *)malloc((size_t)_m * 8); if (!_t) return 1;' % (res_c, res_c),
              '    unsigned _ef = %s(%s);' % (name, ', '.join(names[:-2] + ['_m', '_t'])),
              '    int _ok = 1;',
              '    if (_ef) { *_at = 0; *_what = "the device did not flag what the emulation flags"; _ok = 0; }',
              '    else if (memcmp(_t, _res, (size_t)_m * 8) != 0) { *_at = 0; *_what = "result bits differ"; _ok = 0; }',
              '    free(_t); return _ok;']
    L += ['}', '']

    # the self-test
    scal_params = [q for q in params if ' s_' in q]
    L += ['/* GPU.md 6.3 self-test: 1 passed, 0 the device could not run it, -1 differs from the emulation (class distrusted) */',
          'static int %s_selftest(%s) {' % (name, ', '.join(scal_params) if scal_params else 'void'),
          '    enum { M = %s, LN = %s };' % (st_cnt, st_len),
          '    int _r = 0, _nsel = 0; int64_t _sel[GKV_ST_SINGLES]; unsigned _seen = 0; int64_t _nclean = 0, _nflag = 0;',
          '    double _t0 = gkv_now_us(), _b0 = gkv_G.build_us;',
          '    int64_t _cnt = M;']
    if kernel.loop_var:
        L.append('    int64_t _lo = 0;')
    prev = {'f': None, 'i': None}
    for j, lst in enumerate(lists):
        t = kernel.lists[lst]
        L.append('    %s *p_%s = (%s *)malloc((size_t)LN * 8); int64_t n_%s = LN;' % (ct(t), lst, ct(t), lst))
    L.append('    %s *_res = (%s *)calloc((size_t)M, 8);' % (res_c, res_c))
    L.append('    if (!_res%s) goto out;' % ''.join(' || !p_' + lst for lst in lists))
    for j, lst in enumerate(lists):
        t = kernel.lists[lst]
        if block:
            L.append('    gkv_fill_blocks(p_%s, LN, %d);' % (lst, j))
        else:
            L.append('    gkv_fill_%s(p_%s, LN, %d, %s);' % ('f' if t == 'f' else 'i', lst, j, prev[t] or 'NULL'))
        prev[t] = 'p_' + lst
    L += ['    unsigned _df = 0;',
          '    gkv_G.st = 1;',
          '    if (!%s_dev(%s, &_df, 1)) goto out;' % (name, ', '.join(names)),
          '    {',
          '        const char *_what = 0; long long _at = -1;']
    if safe:
        L += ['        for (int64_t _i = 0; _i < M && !_what; _i++) {',
              '            %s _t; unsigned _ef = %s(%s);' % (res_c, name, ', '.join(args_at('_i', '1', '&_t'))),
              '            if (_ef) {',
              '                _nflag++;',
              '                if (_nsel < GKV_ST_SINGLES && (_ef & ~_seen)) { _seen |= _ef; _sel[_nsel++] = _i; }       /* one single launch per new flag bit (at most 6) */',
              '            } else {',
              '                _nclean++;',
              '                if (memcmp(&_t, &_res[_i], 8) != 0) { _what = "result bits differ"; _at = _i; }',
              '            }',
              '        }']
    else:
        L += ['        %s *_t = (%s *)malloc((size_t)M * 8);' % (res_c, res_c),
              '        if (_t) {',
              '            unsigned _ef = %s(%s);' % (name, ', '.join(names[:-1] + ['_t'])),
              '            if (_ef) { _nflag = 1; } else { _nclean = M; if (memcmp(_t, _res, (size_t)M * 8) != 0) { _what = "result bits differ"; _at = 0; } }',
              '            free(_t);',
              '        }']
    L += ['        if (!_what && _nflag == 0 && _df != 0) { _what = "the device flagged a launch the emulation accepts everywhere"; _at = -1; }',
          '        if (!_what && _nflag != 0 && _df == 0) { _what = "the device did not flag a launch in which the emulation flags"; _at = -1; }']
    if safe:
        L += ['        for (int _s = 0; _s < _nsel && !_what; _s++) {      /* a flagged element alone must flag on the device */',
              '            %s _t = 0; unsigned _f1 = 0;' % res_c,
              '            if (!%s_dev(%s, &_f1, 0)) { _r = 0; goto out; }' % (name, ', '.join(args_at('_sel[_s]', '1', '&_t'))),
              '            if (_f1 == 0) { _what = "the device did not flag a flagged element"; _at = (long long)_sel[_s]; }',
              '        }']
    L += ['        if (_what) { gkv_distrust(%s, %d, _what, _at); _r = -1; goto out; }' % (cls, k),
          '        gkv_trace_selftest(%d, _nclean, _nflag, _nsel, gkv_now_us() - _t0 - (gkv_G.build_us - _b0), gkv_G.build_us - _b0);' % k,
          '        _r = 1;',
          '    }',
          'out:',
          '    gkv_G.st = 0;',
          '    free(_res);']
    for lst in lists:
        L.append('    free((void *)p_%s);' % lst)
    L += ['    return _r;', '}', '']

    # the wrapper: `<name>_want` decides (declined / emulation / device) before the caller allocates anything;
    # `<name>_run` runs the kernel when wanted and returns GK_DECLINED when the caller must run the original loop
    scal_args = [('s_' + sc) for sc in kernel.scalars] + [('s_' + sc) for sc in kernel.consts]
    lens = ' + '.join('(double)n_%s' % lst for lst in lists) or '0.0'
    L += ['static int %s_dec = -1;      /* the decision of the last _want, used by the _run that follows it */' % name,
          'static int %s_want(%s) {' % (name, ', '.join(params[:-1])),
          '    double _ops = %s;' % ops_c,
          '    return %s_dec = gkv_decide(%d, _cnt, 8.0 * ((double)_cnt + %s), _ops);' % (name, k, lens),
          '}', '']
    L += ['static unsigned %s_run(%s) {' % (name, ', '.join(params)),
          '    int _d = %s_dec >= 0 ? %s_dec : %s_want(%s);' % (name, name, name, ', '.join(names[:-1])),
          '    %s_dec = -1;' % name,
          '    if (_d == 1) {                           /* AIL_GPU=emu: the emulation, into a temporary (it may stop half way) */',
          '        %s *_t = (%s *)malloc((size_t)_cnt * 8); if (!_t) return GK_DECLINED;' % (res_c, res_c),
          '        gk_dev = "emulation";',
          '        unsigned f = %s(%s);' % (name, ', '.join(names[:-1] + ['_t'])),
          '        if (f == 0) memcpy(_res, _t, (size_t)_cnt * 8);',
          '        free(_t); return f;',
          '    }',
          '    if (_d == 2) {',
          '        if (gkv_usable(%s)) {' % mask,
          '            if (gkv_check_mode() == 0 && %s_state == 0) %s_state = 1;' % (name, name),
          '            if (%s_state == 0) { int _st = %s_selftest(%s); %s_state = _st > 0 ? 1 : -1; }' % (
              name, name, ', '.join(scal_args), name),
          '            if (%s_state > 0) {' % name,
          '                unsigned f = 0;',
          '                int _chk = gkv_check_mode();',
          '                int _cmp = _chk && (_chk > 1 || !%s_first);      /* compare with the emulation: into a temporary first */' % name,
          '                %s *_dst = _res, *_t = 0;' % res_c,
          '                if (_cmp) { _t = (%s *)malloc((size_t)_cnt * 8); if (!_t) return GK_DECLINED; _dst = _t; }' % res_c,
          '                if (%s_dev(%s, &f, 0)) {' % (name, ', '.join(names[:-1] + ['_dst'])),
          '                    if (_cmp) {',
          '                        const char *_what = 0; long long _at = -1;',
          '                        %s_first = 1;' % name,
          '                        if (!%s_agree(%s, f, &_at, &_what)) {' % (name, ', '.join(names[:-1] + ['_dst'])),
          '                            gkv_distrust(%s, %d, _what, _at); %s_state = -1;' % (cls, k, name),
          '                            free(_t); return GK_DECLINED;',
          '                        }',
          '                        if (f == 0) memcpy(_res, _t, (size_t)_cnt * 8);',
          '                        free(_t);',
          '                    }',
          '                    gk_dev = gkv_dev_name(); return f;',
          '                }',
          '                free(_t);',
          '            }',
          '        }',
          '        gkv_trace_why(%d);' % k,
          '    }',
          '    return GK_DECLINED;',
          '}']
    return '\n'.join(L) + '\n', info, words
