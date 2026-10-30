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
    AIL_GPU=emu          never touch Vulkan: the C emulation runs (the "CPU path" of the kernels)
    AIL_GPU=force        use the device for every launch, whatever its size
    (unset / other)      the device for launches of at least AIL_GPU_MIN_N elements (default 4096), else the emulation
    AIL_GPU_TRACE=1      one line per launch on stderr: `gpu: k0 n=4096 device=llvmpipe (LLVM 20.1.2, 256 bits)`;
                         `gpu: k0 device unavailable (<why>)` when the device was wanted and not used
    AIL_GPU_DEVICE=name  use the first device whose name contains `name`
    AIL_VULKAN_LIB=path  open this loader instead of the default (a test hook: a path that does not exist = no Vulkan)
    AIL_GPU_DISABLE=...  test hook: pretend the device lacks the features named in the value (f64 i64 rte szinp)
"""
import gpu_spirv

VK_RUNTIME = r'''
#ifndef AIL_GKV_RT
#define AIL_GKV_RT
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
static struct {
    int state;                     /* 0 untried, 1 ready, -1 unusable */
    const char *why;
    char name[256];
    void *lib, *inst, *pd, *dev, *queue;
    uint64_t cpool;
    uint32_t family;
    int has_f64, has_i64, szinp64, rte64;
    uint64_t max_range;
    gkv_MemProps mem;
    int npipes;
    gkv_pipe pipes[GKV_MAXPIPES];
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
        if (rank < best_rank) { best = (int)d; best_rank = rank; best_family = (uint32_t)fam; }
    }
    if (best < 0) return 0;
    gkv_G.pd = devs[best]; gkv_G.family = best_family;
    {
        gkv_FloatCtl fc; memset(&fc, 0, sizeof fc); fc.sType = 1000197000;
        gkv_Props2 pr; memset(&pr, 0, sizeof pr); pr.sType = 1000059001; pr.pNext = &fc;
        gkv_G.vkGetPhysicalDeviceProperties2(gkv_G.pd, &pr);
        strncpy(gkv_G.name, (const char *)pr.p + 20, 255); gkv_G.name[255] = 0;
        memcpy(&gkv_G.max_range, pr.p + 296 + 28, 4); gkv_G.max_range &= 0xffffffffu;
        gkv_G.szinp64 = fc.szinp64 != 0; gkv_G.rte64 = fc.rte64 != 0;
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

typedef struct { uint64_t buf, mem; void *ptr; } gkv_buf;
static int gkv_memtype(uint32_t bits) {
    for (uint32_t i = 0; i < gkv_G.mem.memoryTypeCount; i++)
        if ((bits & (1u << i)) && (gkv_G.mem.memoryTypes[i].propertyFlags & 6u) == 6u) return (int)i;     /* host visible + coherent */
    return -1;
}
static int gkv_mkbuf(gkv_buf *b, uint64_t size) {
    memset(b, 0, sizeof *b);
    if (size < 16) size = 16;
    gkv_BufferCI ci; memset(&ci, 0, sizeof ci);
    ci.sType = 12; ci.size = size; ci.usage = 0x20u;
    if (gkv_G.vkCreateBuffer(gkv_G.dev, &ci, 0, &b->buf) != 0) { b->buf = 0; return 0; }
    gkv_MemReq rq; memset(&rq, 0, sizeof rq);
    gkv_G.vkGetBufferMemoryRequirements(gkv_G.dev, b->buf, &rq);
    int mt = gkv_memtype(rq.memoryTypeBits);
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

/* the pipeline of one kernel, built on its first launch and kept */
static gkv_pipe *gkv_pipe_for(const uint32_t *spv, uint32_t nwords, int nbind) {
    for (int i = 0; i < gkv_G.npipes; i++) if (gkv_G.pipes[i].spv == spv) return gkv_G.pipes[i].ok ? &gkv_G.pipes[i] : 0;
    if (gkv_G.npipes >= GKV_MAXPIPES) { gkv_G.why = "too many kernels"; return 0; }
    gkv_pipe *p = &gkv_G.pipes[gkv_G.npipes++];
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
    return p;
}

/* One launch.  Returns 1 when the device ran the kernel (*flag is its flag word; `res` holds the result iff *flag == 0),
   0 when it did not (nothing in the caller's memory was touched).  Buffers live for the launch only. */
static GKV_UNUSED int gkv_launch(const uint32_t *spv, uint32_t nwords, int need_f64, int nl, int nprm, uint64_t *prm,
                                 const void *const *lp, const int64_t *ln, void *res, int64_t cnt, unsigned *flag) {
    if (!gkv_init()) return 0;
    if (!gkv_G.has_i64) { gkv_G.why = "the device lacks shaderInt64"; return 0; }
    if (need_f64 && !(gkv_G.has_f64 && gkv_G.szinp64 && gkv_G.rte64)) {
        gkv_G.why = "the device lacks shaderFloat64, signed-zero/inf/NaN preservation or round-to-nearest-even for binary64";
        return 0;
    }
    if (cnt <= 0 || cnt > ((int64_t)1 << 40)) { gkv_G.why = "launch size out of range"; return 0; }
    uint64_t groups = ((uint64_t)cnt + 63) / 64;
    uint64_t gx = groups < 65535 ? groups : 65535, gy = (groups + gx - 1) / gx;
    if (gy > 65535) { gkv_G.why = "launch too large"; return 0; }
    prm[2] = gx * 64;
    if ((uint64_t)cnt * 8 > gkv_G.max_range) { gkv_G.why = "result larger than maxStorageBufferRange"; return 0; }
    for (int i = 0; i < nl; i++) if ((uint64_t)ln[i] * 8 > gkv_G.max_range) { gkv_G.why = "input larger than maxStorageBufferRange"; return 0; }
    if (nl > 36) { gkv_G.why = "too many lists"; return 0; }
    int nb = 3 + nl, ok = 0, have_cb = 0, have_pool = 0, have_fence = 0;
    gkv_buf bufs[43];
    int made = 0;
    uint64_t pool = 0, fence = 0, set = 0;
    void *cb = 0;
    gkv_pipe *p = gkv_pipe_for(spv, nwords, nb);
    if (!p) return 0;
    if (!gkv_mkbuf(&bufs[made++], (uint64_t)nprm * 8)) { gkv_G.why = "device memory: params"; goto done; }
    if (!gkv_mkbuf(&bufs[made++], 4)) { gkv_G.why = "device memory: flags"; goto done; }
    if (!gkv_mkbuf(&bufs[made++], (uint64_t)cnt * 8)) { gkv_G.why = "device memory: result"; goto done; }
    for (int i = 0; i < nl; i++) {
        if (!gkv_mkbuf(&bufs[made++], (uint64_t)ln[i] * 8)) { gkv_G.why = "device memory: input"; goto done; }
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
        *flag = f;
        if (f == 0) memcpy(res, bufs[2].ptr, (size_t)cnt * 8);
        ok = 1;
    }
done:
    if (have_cb) gkv_G.vkResetCommandPool(gkv_G.dev, gkv_G.cpool, 0);
    if (have_fence) gkv_G.vkDestroyFence(gkv_G.dev, fence, 0);
    if (have_pool) gkv_G.vkDestroyDescriptorPool(gkv_G.dev, pool, 0);
    for (int i = made; i-- > 0; ) gkv_rmbuf(&bufs[i]);
    return ok;
}

static GKV_UNUSED int gkv_mode(void) {         /* 0 never (AIL_GPU=emu), 1 by size, 2 always */
    static int v = -1;
    if (v < 0) {
        const char *e = getenv("AIL_GPU");
        v = (e && !strcmp(e, "emu")) ? 0 : (e && !strcmp(e, "force")) ? 2 : 1;
    }
    return v;
}
static GKV_UNUSED int64_t gkv_min_n(void) {
    static int64_t v = -1;
    if (v < 0) { const char *e = getenv("AIL_GPU_MIN_N"); v = e && e[0] ? (int64_t)atoll(e) : 4096; if (v < 0) v = 0; }
    return v;
}
static GKV_UNUSED int gkv_want(int64_t n) { int m = gkv_mode(); return m == 2 || (m == 1 && n >= gkv_min_n()); }
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


def device_text(kernel, name, k):
    """(C text, info, words) for the kernel: the SPIR-V array and `<name>_run`, which has the signature of `<name>` (the
    emulation), tries the device and falls back to the emulation.  Raises gpu_spirv.Unsupported."""
    words, info = gpu_spirv.compile_kernel(kernel)
    lists = info['lists']
    nl, nprm = len(lists), len(info['params'])
    scal = [(n, t) for n, t in info['params'][3 + nl:]]               # ('s_x', 'i'|'f') in parameter order
    params = []
    for lst in lists:
        params += ['const %s *p_%s' % ('double' if kernel.lists[lst] == 'f' else 'int64_t', lst), 'int64_t n_%s' % lst]
    for sc, t in kernel.scalars.items():
        params.append('%s s_%s' % ('double' if t == 'f' else 'int64_t', sc))
    for sc, (t, value) in kernel.consts.items():
        params.append('%s s_%s' % ('double' if t == 'f' else 'int64_t', sc))
    if kernel.loop_var:
        params.append('int64_t _lo')
    res_c = 'double' if kernel.res_type == 'f' else 'int64_t'
    params += ['int64_t _cnt', '%s *_res' % res_c]
    names = []
    for lst in lists:
        names += ['p_' + lst, 'n_' + lst]
    names += ['s_' + sc for sc in kernel.scalars] + ['s_' + sc for sc in kernel.consts]
    if kernel.loop_var:
        names.append('_lo')
    names += ['_cnt', '_res']
    lines = ['/* GPU.md G2: SPIR-V of kernel k%d (%s) */' % (k, gpu_spirv.disassemble_hint(words)),
             'static const uint32_t %s_spv[%d] = {\n%s\n};' % (name, len(words), _words_c(words)),
             'static unsigned %s_run(%s) {' % (name, ', '.join(params)),
             '    if (gkv_want(_cnt)) {',
             '        uint64_t prm[%d]; memset(prm, 0, sizeof prm);' % max(nprm, 1),
             '        prm[0] = (uint64_t)_cnt;']
    if kernel.loop_var:
        lines.append('        prm[1] = (uint64_t)_lo;')
    for j, lst in enumerate(lists):
        lines.append('        prm[%d] = (uint64_t)n_%s;' % (3 + j, lst))
    for j, (pname, t) in enumerate(scal):
        slot = 3 + nl + j
        if t == 'f':
            lines.append('        memcpy(&prm[%d], &%s, 8);' % (slot, pname))
        else:
            lines.append('        prm[%d] = (uint64_t)%s;' % (slot, pname))
    lines.append('        const void *lp[%d]; int64_t ln[%d];' % (max(nl, 1), max(nl, 1)))
    for j, lst in enumerate(lists):
        lines.append('        lp[%d] = p_%s; ln[%d] = n_%s;' % (j, lst, j, lst))
    lines += ['        unsigned f = 0;',
              '        if (gkv_launch(%s_spv, %d, %d, %d, %d, prm, lp, ln, _res, _cnt, &f)) { gk_dev = gkv_dev_name(); return f; }'
              % (name, len(words), 1 if info['need_f64'] else 0, nl, max(nprm, 1)),
              '        gkv_trace_why(%d);' % k,
              '    }',
              '    gk_dev = "emulation";',
              '    return %s(%s);' % (name, ', '.join(names)),
              '}']
    return '\n'.join(lines) + '\n', info, words
