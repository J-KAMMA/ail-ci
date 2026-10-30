"""GPU stage G2 (docs/design/GPU.md): the SPIR-V emitter and the Vulkan runtime that loads at run time.

The kernels of stage G1 now have a device twin: `gpu_spirv.py` writes a compute shader for the same kernel IR, and the
C runtime in `gpu_vk.py` opens the Vulkan loader with dlopen at run time, runs the shader, and falls back to the CPU
emulation (stage G1) whenever anything is missing.  The rule is the one of GPU.md section 0: the program prints what the
same build prints with `AIL_GPU=0`, which is what CPython prints.

Layers:

* `Spirv`     -- the emitter alone: header, capabilities, no fast-math decoration anywhere, NoContraction on every float
                 arithmetic result, no division/FMA/FMin/FMax, the float-controls execution modes; every kernel of the
                 catalogue passes `spirv-val` (when spirv-tools is installed; CI installs it).
* `Layout`    -- the Vulkan structs and constants the runtime declares itself, against the real vulkan_core.h (when the
                 header is installed: libvulkan-dev).
* `BitTests`  -- GPU.md 5.1 "bit tests": a C harness runs every kernel of the catalogue over ~65k operand sets (random
                 bit patterns, +-0, +-inf, NaN, subnormals, the 2**-1000 guard boundary, neighbours for cancellation,
                 int64 limits) on the CPU emulation (one element at a time) and on the device (all clean elements in one
                 launch).  Every element the emulation accepts must come back from the device with the same bits and
                 flag 0; every element the emulation flags must flag on the device.  Needs a Vulkan device (lavapipe).
* `Programs`  -- whole programs: lengths 0, 1, workgroup size +-1, 4096+-1, 100003 and a 2-D grid; special float values;
                 errors at chosen positions (replay); aliasing; the same binary with AIL_GPU=force (device),
                 AIL_GPU=emu (emulation), AIL_GPU=0 (CPU loop), no libvulkan, a device without the needed features, and
                 CPython: all print the same.
* `Notes`     -- the compile note naming the path a kernel can take.

Device tests skip when no Vulkan device exists (the shards of tools/ci_shards.py have none); the `gpu` job of
.github/workflows/tests.yml installs lavapipe and sets AIL_GPU_REQUIRE_DEVICE=1, which turns a missing device into a
failure.
"""
import ast
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

CLI = ROOT / 'ail_chatgpt.py'
CC = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
REQUIRE_DEVICE = os.environ.get('AIL_GPU_REQUIRE_DEVICE', '') not in ('', '0')
SPIRV_VAL = os.environ.get('SPIRV_VAL') or shutil.which('spirv-val')
VK_INCLUDE = os.environ.get('VULKAN_INCLUDE') or ('/usr/include' if Path('/usr/include/vulkan/vulkan.h').is_file() else '')


def run_python(path, stdin=''):
    r = subprocess.run([sys.executable, '-B', str(path)], input=stdin, capture_output=True, text=True, timeout=300)
    return r.stdout, r.returncode


def kernel_of(src, types, scalars=None):
    """The kernel IR of the last statement of `src` (a marked-loop body or a comprehension), typed by `types`."""
    import gpu
    tree = ast.parse(src)
    funcs = gpu._funcs_of(tree)
    stmt = [n for n in tree.body if not isinstance(n, ast.FunctionDef)][-1]
    site = gpu._classify(stmt, funcs)
    site['k'] = 0

    def oracle(what, name, node):
        return types[name] if what == 'list' else (scalars or {})[name]
    builder = gpu.Builder(site, funcs, oracle)
    return builder.build_for() if site['kind'] == 'for' else builder.build_comp()


# the catalogue: (name, source, {list: type}); lists are a, b, c.  Comprehensions over zip, so every element is independent
FF = {'a': 'f', 'b': 'f', 'c': 'f'}
II = {'a': 'i', 'b': 'i', 'c': 'i'}
FI = {'a': 'f', 'b': 'i'}


def comp(expr, names='x, y', lists='a, b'):
    source = lists if ',' not in lists else 'zip(%s)' % lists
    return 'import math\nr = [%s for %s in %s]\n' % (expr, names, source)


CATALOGUE = [
    # binary64 arithmetic
    ('f_add', comp('x + y'), FF), ('f_sub', comp('x - y'), FF), ('f_mul', comp('x * y'), FF),
    ('f_fma3', comp('x * y + z', 'x, y, z', 'a, b, c'), FF), ('f_fms3', comp('x * y - z', 'x, y, z', 'a, b, c'), FF),
    ('f_two_mul', comp('x * y - z * x', 'x, y, z', 'a, b, c'), FF),
    ('f_chain', comp('(x + y) * (x - y) + x * 0.1', 'x, y', 'a, b'), FF),
    ('f_neg', comp('-x', 'x', 'a'), FF), ('f_abs', comp('abs(x)', 'x', 'a'), FF),
    ('f_min', comp('min(x, y)'), FF), ('f_max', comp('max(x, y)'), FF), ('f_min3', comp('min(x, y, z)', 'x, y, z', 'a, b, c'), FF),
    ('f_sel', comp('x if x < y else y'), FF), ('f_const', comp('x * 3.0 + 1e300 - 0.1', 'x', 'a'), FF),
    ('f_neg0', comp('0.0 - x', 'x', 'a'), FF), ('f_negzero', comp('-0.0 + x', 'x', 'a'), FF),
    ('f_or', comp('x or y'), FF), ('f_and', comp('x and y'), FF),
    # comparisons (int results)
    ('c_lt', comp('1 if x < y else 0'), FF), ('c_le', comp('1 if x <= y else 0'), FF),
    ('c_gt', comp('1 if x > y else 0'), FF), ('c_ge', comp('1 if x >= y else 0'), FF),
    ('c_eq', comp('1 if x == y else 0'), FF), ('c_ne', comp('1 if x != y else 0'), FF),
    ('c_truth', comp('1 if x else 0', 'x', 'a'), FF), ('c_boolarith', comp('(x < y) + (x == y) * 2 + (not x > y) * 4'), FF),
    ('c_chain', comp('1 if x < y < z else 0', 'x, y, z', 'a, b, c'), FF),
    ('c_mixed', comp('1 if x < i else 0', 'x, i', 'a, b'), FI), ('c_mixed_eq', comp('1 if x == i else 0', 'x, i', 'a, b'), FI),
    # conversions
    ('v_int', comp('int(x)', 'x', 'a'), FF), ('v_floor', comp('math.floor(x)', 'x', 'a'), FF),
    ('v_ceil', comp('math.ceil(x)', 'x', 'a'), FF), ('v_trunc', comp('math.trunc(x)', 'x', 'a'), FF),
    ('v_ffloor', comp('x // 1', 'x', 'a'), FF), ('v_float', comp('float(i)', 'i', 'a'), {'a': 'i'}),
    ('v_float_half', comp('float(i) * 0.5 + i', 'i', 'a'), {'a': 'i'}),
    # int64
    ('i_add', comp('x + y'), II), ('i_sub', comp('x - y'), II), ('i_mul', comp('x * y'), II),
    ('i_fdiv', comp('x // y'), II), ('i_mod', comp('x % y'), II), ('i_neg', comp('-x', 'x', 'a'), II),
    ('i_abs', comp('abs(x)', 'x', 'a'), II), ('i_min', comp('min(x, y)'), II), ('i_max', comp('max(x, y)', 'x, y'), II),
    ('i_sel', comp('x if x > y else y'), II), ('i_lt', comp('1 if x < y else 0'), II),
    ('i_eq', comp('1 if x == y else 0'), II), ('i_logic', comp('(x and y) + (x or y) * 10'), II),
    ('i_expr', comp('(x + y) // 3 + x * y - z', 'x, y, z', 'a, b, c'), II),
    ('i_not', comp('1 if not x else 0', 'x', 'a'), II),
]

INNER = [   # kernels with locals, branches, inner loops and reads at computed indices (range kernels)
    ('r_branchy', '''
out = [0.0] * 8
for i in range(8):
    y = a[i]
    if y > 10.0:
        y = y - 10.0
    elif y < -10.0:
        y = y + 10.0
    else:
        y = y * 0.5
    out[i] = y
''', {'a': 'f'}),
    ('r_inner', '''
out = [0.0] * 8
for i in range(8):
    acc = 0.0
    for j in range(4):
        acc = acc + a[i] * 0.5
    out[i] = acc
''', {'a': 'f'}),
    ('r_gather', '''
out = [0.0] * 8
for i in range(8):
    out[i] = a[b[i]] + a[-1]
''', {'a': 'f', 'b': 'i'}),
]


# ---------------------------------------------------------------------------------------------------------------------
class Spirv(unittest.TestCase):
    """The emitter alone."""

    @classmethod
    def setUpClass(cls):
        import gpu_spirv
        cls.sp = gpu_spirv
        cls.mods = {}
        for name, src, types in CATALOGUE + INNER:
            cls.mods[name] = cls.sp.compile_kernel(kernel_of(src, types))

    @staticmethod
    def instructions(words):
        i = 5
        while i < len(words):
            n = words[i] >> 16
            yield words[i] & 0xFFFF, words[i + 1:i + n]
            i += n

    def test_header_and_capabilities(self):
        for name, (words, info) in self.mods.items():
            self.assertEqual(words[0], 0x07230203, name)
            self.assertEqual(words[1], 0x00010400, name)                       # SPIR-V 1.4 (Vulkan 1.2)
            caps = [ops[0] for op, ops in self.instructions(words) if op == 17]
            self.assertIn(1, caps, name)                                      # Shader
            self.assertIn(11, caps, name)                                     # Int64
            if info['need_f64']:
                self.assertTrue({10, 4467, 4466} <= set(caps), name)           # Float64, RoundingModeRTE, SignedZeroInfNanPreserve
            else:
                self.assertFalse({10, 4467, 4466} & set(caps), name)           # an int kernel needs no float capability
            if name.startswith('i_'):
                self.assertFalse(info['need_f64'], name)

    def test_float_controls_execution_modes(self):
        for name, (words, info) in self.mods.items():
            modes = [(ops[1], ops[2:]) for op, ops in self.instructions(words) if op == 16]
            kinds = [m for m, _ in modes]
            self.assertIn(17, kinds, name)                                    # LocalSize
            if info['need_f64']:
                self.assertIn((4462, [64]), [(m, a) for m, a in modes], name)    # RoundingModeRTE 64
                self.assertIn((4461, [64]), [(m, a) for m, a in modes], name)    # SignedZeroInfNanPreserve 64
            self.assertNotIn(4459, kinds, name)       # DenormPreserve is not requested: the guards make it unnecessary
            self.assertNotIn(4460, kinds, name)
            self.assertNotIn(4463, kinds, name)       # never round toward zero

    def test_no_fast_math_and_every_float_op_is_not_contractable(self):
        for name, (words, info) in self.mods.items():
            decorated, rounding = {}, {}
            for op, ops in self.instructions(words):
                if op == 71:                                     # OpDecorate
                    decorated.setdefault(ops[0], set()).add(ops[1])
                    self.assertNotEqual(ops[1], 40, '%s: FPFastMathMode decoration' % name)
                    self.assertNotIn(ops[1], (4469,), name)
                if op == 71 and ops[1] == 39:
                    rounding[ops[0]] = ops[2]
            arith = {129: 'FAdd', 131: 'FSub', 133: 'FMul', 127: 'FNegate'}
            seen = 0
            for op, ops in self.instructions(words):
                if op in arith:
                    seen += 1
                    self.assertIn(42, decorated.get(ops[1], ()), '%s: %s %d lacks NoContraction' % (name, arith[op], ops[1]))
                self.assertNotIn(op, (136, 137, 140, 141, 142), '%s: float division/remainder' % name)   # FDiv FRem FMod ...
            if name.startswith(('f_', 'r_')) and name not in ('f_neg', 'f_abs', 'f_min', 'f_max', 'f_sel', 'f_or', 'f_and', 'f_min3'):
                self.assertGreater(seen, 0, name)

    def test_only_exact_extended_instructions(self):
        for name, (words, info) in self.mods.items():
            for op, ops in self.instructions(words):
                if op == 12:                                     # OpExtInst: GLSL.std.450 FAbs 4, Floor 8, Ceil 9 only
                    self.assertIn(ops[3], (4, 8, 9), '%s: extended instruction %d' % (name, ops[3]))

    def test_every_kernel_validates(self):
        if not SPIRV_VAL:
            raise unittest.SkipTest('spirv-val not installed (apt install spirv-tools)')
        with tempfile.TemporaryDirectory(prefix='ail-spv-') as d:
            for name, (words, info) in self.mods.items():
                path = Path(d) / (name + '.spv')
                path.write_bytes(struct.pack('<%dI' % len(words), *words))
                r = subprocess.run([SPIRV_VAL, '--target-env', 'vulkan1.2', str(path)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, '%s:\n%s' % (name, r.stdout + r.stderr))

    def test_unsupported_nodes_are_refused_by_name(self):
        k = kernel_of(comp('x + y'), FF)
        k.result = ('mystery', 'f', k.result)
        with self.assertRaises(self.sp.Unsupported):
            self.sp.compile_kernel(k)

    def test_words_are_deterministic(self):
        a = self.sp.compile_kernel(kernel_of(comp('x * y + z', 'x, y, z', 'a, b, c'), FF))[0]
        b = self.sp.compile_kernel(kernel_of(comp('x * y + z', 'x, y, z', 'a, b, c'), FF))[0]
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------------------------------------------------
STRUCTS = [   # (ours, Vulkan's, fields compared with offsetof)
    ('gkv_AppInfo', 'VkApplicationInfo', 'sType pNext pApplicationName applicationVersion pEngineName engineVersion apiVersion'),
    ('gkv_InstanceCI', 'VkInstanceCreateInfo', 'sType pNext flags pApplicationInfo enabledLayerCount ppEnabledLayerNames enabledExtensionCount ppEnabledExtensionNames'),
    ('gkv_Features', 'VkPhysicalDeviceFeatures', ''),
    ('gkv_QueueCI', 'VkDeviceQueueCreateInfo', 'sType pNext flags queueFamilyIndex queueCount pQueuePriorities'),
    ('gkv_DeviceCI', 'VkDeviceCreateInfo', 'sType pNext flags queueCreateInfoCount pQueueCreateInfos enabledLayerCount ppEnabledLayerNames enabledExtensionCount ppEnabledExtensionNames pEnabledFeatures'),
    ('gkv_QueueFamily', 'VkQueueFamilyProperties', 'queueFlags queueCount timestampValidBits minImageTransferGranularity'),
    ('gkv_MemType', 'VkMemoryType', 'propertyFlags heapIndex'),
    ('gkv_MemHeap', 'VkMemoryHeap', 'size flags'),
    ('gkv_MemProps', 'VkPhysicalDeviceMemoryProperties', 'memoryTypeCount memoryTypes memoryHeapCount memoryHeaps'),
    ('gkv_FloatCtl', 'VkPhysicalDeviceFloatControlsProperties', 'sType pNext denormBehaviorIndependence roundingModeIndependence'),
    ('gkv_Props2', 'VkPhysicalDeviceProperties2', 'sType pNext'),
    ('gkv_BufferCI', 'VkBufferCreateInfo', 'sType pNext flags size usage sharingMode queueFamilyIndexCount pQueueFamilyIndices'),
    ('gkv_MemReq', 'VkMemoryRequirements', 'size alignment memoryTypeBits'),
    ('gkv_MemAlloc', 'VkMemoryAllocateInfo', 'sType pNext allocationSize memoryTypeIndex'),
    ('gkv_ShaderCI', 'VkShaderModuleCreateInfo', 'sType pNext flags codeSize pCode'),
    ('gkv_DSLBinding', 'VkDescriptorSetLayoutBinding', 'binding descriptorType descriptorCount stageFlags pImmutableSamplers'),
    ('gkv_DSLCI', 'VkDescriptorSetLayoutCreateInfo', 'sType pNext flags bindingCount pBindings'),
    ('gkv_PLCI', 'VkPipelineLayoutCreateInfo', 'sType pNext flags setLayoutCount pSetLayouts pushConstantRangeCount pPushConstantRanges'),
    ('gkv_StageCI', 'VkPipelineShaderStageCreateInfo', 'sType pNext flags stage module pName pSpecializationInfo'),
    ('gkv_ComputeCI', 'VkComputePipelineCreateInfo', 'sType pNext flags stage layout basePipelineHandle basePipelineIndex'),
    ('gkv_PoolSize', 'VkDescriptorPoolSize', 'type descriptorCount'),
    ('gkv_DPCI', 'VkDescriptorPoolCreateInfo', 'sType pNext flags maxSets poolSizeCount pPoolSizes'),
    ('gkv_DSAI', 'VkDescriptorSetAllocateInfo', 'sType pNext descriptorPool descriptorSetCount pSetLayouts'),
    ('gkv_DBInfo', 'VkDescriptorBufferInfo', 'buffer offset range'),
    ('gkv_Write', 'VkWriteDescriptorSet', 'sType pNext dstSet dstBinding dstArrayElement descriptorCount descriptorType pImageInfo pBufferInfo pTexelBufferView'),
    ('gkv_CmdPoolCI', 'VkCommandPoolCreateInfo', 'sType pNext flags queueFamilyIndex'),
    ('gkv_CmdBufAI', 'VkCommandBufferAllocateInfo', 'sType pNext commandPool level commandBufferCount'),
    ('gkv_CmdBeginInfo', 'VkCommandBufferBeginInfo', 'sType pNext flags pInheritanceInfo'),
    ('gkv_SubmitInfo', 'VkSubmitInfo', 'sType pNext waitSemaphoreCount pWaitSemaphores pWaitDstStageMask commandBufferCount pCommandBuffers signalSemaphoreCount pSignalSemaphores'),
    ('gkv_FenceCI', 'VkFenceCreateInfo', 'sType pNext flags'),
]
CONSTANTS = [   # the literals the runtime uses, against the header's names
    (0, 'VK_STRUCTURE_TYPE_APPLICATION_INFO'), (1, 'VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO'),
    (2, 'VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO'), (3, 'VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO'),
    (4, 'VK_STRUCTURE_TYPE_SUBMIT_INFO'), (5, 'VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO'), (8, 'VK_STRUCTURE_TYPE_FENCE_CREATE_INFO'),
    (12, 'VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO'), (16, 'VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO'),
    (18, 'VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO'), (29, 'VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO'),
    (30, 'VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO'), (32, 'VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO'),
    (33, 'VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO'), (34, 'VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO'),
    (35, 'VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET'), (39, 'VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO'),
    (40, 'VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO'), (42, 'VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO'),
    (1000197000, 'VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FLOAT_CONTROLS_PROPERTIES'),
    (1000059001, 'VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2'),
    (0x20, 'VK_BUFFER_USAGE_STORAGE_BUFFER_BIT'), (7, 'VK_DESCRIPTOR_TYPE_STORAGE_BUFFER'),
    (0x20, 'VK_SHADER_STAGE_COMPUTE_BIT'), (2, 'VK_QUEUE_COMPUTE_BIT'), (2, 'VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT'),
    (4, 'VK_MEMORY_PROPERTY_HOST_COHERENT_BIT'), (1, 'VK_PIPELINE_BIND_POINT_COMPUTE'),
    (1, 'VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT'), (0, 'VK_COMMAND_BUFFER_LEVEL_PRIMARY'),
    (0x402000, 'VK_API_VERSION_1_2'),
]


class Layout(unittest.TestCase):
    def test_structs_match_vulkan_core_h(self):
        if not CC or not VK_INCLUDE:
            raise unittest.SkipTest('no vulkan headers (apt install libvulkan-dev)')
        import gpu_vk
        lines = ['#include <stdint.h>', '#include <stdio.h>', '#include <stdlib.h>', '#include <string.h>',
                 '#include <stddef.h>', '#include <vulkan/vulkan.h>',
                 'static int gk_tracing(void) { return 0; }', gpu_vk.VK_RUNTIME]
        for ours, theirs, fields in STRUCTS:
            lines.append('_Static_assert(sizeof(%s) == sizeof(%s), "size of %s");' % (ours, theirs, ours))
            lines.append('_Static_assert(_Alignof(%s) == _Alignof(%s), "alignment of %s");' % (ours, theirs, ours))
            for f in fields.split():
                lines.append('_Static_assert(offsetof(%s, %s) == offsetof(%s, %s), "%s.%s");' % (ours, f, theirs, f, ours, f))
        lines.append('_Static_assert(offsetof(VkPhysicalDeviceProperties2, properties) + 296 + 28 == offsetof(VkPhysicalDeviceProperties2, properties) '
                     '+ offsetof(VkPhysicalDeviceProperties, limits) + offsetof(VkPhysicalDeviceLimits, maxStorageBufferRange), "limits");')
        lines.append('_Static_assert(offsetof(VkPhysicalDeviceProperties, deviceName) == 20 && offsetof(VkPhysicalDeviceProperties, deviceType) == 16, "name");')
        lines.append('_Static_assert(sizeof(VkPhysicalDeviceProperties) == 824, "properties");')
        lines.append('_Static_assert(offsetof(VkPhysicalDeviceFeatures, shaderFloat64) == 39 * 4 && offsetof(VkPhysicalDeviceFeatures, shaderInt64) == 40 * 4, "features");')
        lines.append('_Static_assert(offsetof(VkPhysicalDeviceFloatControlsProperties, shaderSignedZeroInfNanPreserveFloat64) == offsetof(gkv_FloatCtl, szinp64), "szinp");')
        lines.append('_Static_assert(offsetof(VkPhysicalDeviceFloatControlsProperties, shaderRoundingModeRTEFloat64) == offsetof(gkv_FloatCtl, rte64), "rte");')
        for value, name in CONSTANTS:
            lines.append('_Static_assert((long long)(%s) == %dLL, "%s");' % (name, value, name))
        lines.append('int main(void) { return 0; }')
        with tempfile.TemporaryDirectory(prefix='ail-vkl-') as d:
            src = Path(d) / 'layout.c'
            src.write_text('\n'.join(lines), encoding='utf-8')
            r = subprocess.run([CC, '-std=gnu11', '-I', VK_INCLUDE, '-Wall', '-Werror', '-c', str(src), '-o', str(Path(d) / 'l.o')],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


# ---------------------------------------------------------------------------------------------------------------------
HARNESS_MAIN = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
%(runtime)s
%(kernels)s
static uint64_t rs = 88172645463325252ull;
static uint64_t rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs; }
static double d_of(uint64_t b) { double d; memcpy(&d, &b, 8); return d; }
static uint64_t b_of(double d) { uint64_t b; memcpy(&b, &d, 8); return b; }
static const double EDGE_F[] = { 0.0, -0.0, 1.0, -1.0, 0.5, 2.0, 1.5, 3.0, 0.1, 1e300, -1e300, 1.7976931348623157e308, -1.7976931348623157e308,
    2.2250738585072014e-308, 4.9406564584124654e-324, 1e-310, -1e-310, 9.332636185032189e-302, 9.3326361850321887e-302, 1e-300, -1e-300,
    4503599627370496.0, 4503599627370497.5, 9007199254740992.0, 9007199254740993.0, 9223372036854775808.0, -9223372036854775808.0,
    9.2233720368547748e18, 1e19, -1e19, 2147483648.0, 123456789.123, 0.30000000000000004 };
static const int64_t EDGE_I[] = { 0, 1, -1, 2, -2, 3, 7, -7, 100, -100, INT64_MAX, INT64_MAX - 1, INT64_MIN, INT64_MIN + 1,
    2147483647LL, 2147483648LL, -2147483648LL, 4294967296LL, 3037000499LL, 3037000500LL, -3037000500LL, 4611686018427387904LL,
    4611686018427387903LL, -4611686018427387904LL, 9007199254740992LL, 9007199254740993LL, -9007199254740993LL, 6148914691236517205LL };
#define NEF ((int)(sizeof EDGE_F / sizeof EDGE_F[0]))
#define NEI ((int)(sizeof EDGE_I / sizeof EDGE_I[0]))
static double rand_f(void) {
    switch (rnd() %% 9) {
    case 0: case 1: return d_of(rnd());
    case 2: case 3: return EDGE_F[rnd() %% NEF];
    case 4: { uint64_t e = rnd() %% 48; return d_of((rnd() & 0x800fffffffffffffull) | (e << 52)); }   /* tiny / subnormal exponents */
    case 5: { uint64_t e = 1023 - 1015 + rnd() %% 32; return d_of((rnd() & 0x800fffffffffffffull) | (e << 52)); }  /* around 2**-1000 */
    case 6: return (double)((int64_t)(rnd() %% 201) - 100);
    case 7: return (double)(int64_t)rnd();
    default: return d_of((rnd() & 0x800fffffffffffffull) | ((1023 - 30 + rnd() %% 60) << 52));
    }
}
static double rand_f_near(double a) {
    switch (rnd() %% 6) {
    case 0: return a;
    case 1: return -a;
    case 2: return d_of(b_of(a) + (rnd() %% 5)) ;
    case 3: return d_of(b_of(a) - (rnd() %% 5));
    case 4: return a * 0.5;
    default: return rand_f();
    }
}
static int64_t rand_i(void) {
    switch (rnd() %% 8) {
    case 0: case 1: return (int64_t)rnd();
    case 2: case 3: return EDGE_I[rnd() %% NEI];
    case 4: return (int64_t)(rnd() %% 201) - 100;
    case 5: return (int64_t)(rnd() >> (1 + rnd() %% 62));
    case 6: return -(int64_t)(rnd() >> (1 + rnd() %% 62));
    default: return (int64_t)(rnd() %% 2000001) - 1000000;
    }
}
static int64_t rand_i_near(int64_t a) {
    switch (rnd() %% 6) {
    case 0: return a;
    case 1: return (int64_t)(0 - (uint64_t)a);
    case 2: return (int64_t)((uint64_t)a + rnd() %% 3);
    case 3: return -(int64_t)(rnd() %% 5) - 1;
    case 4: return (int64_t)(rnd() %% 5);
    default: return rand_i();
    }
}
#define N %(n)d
static double Af[N], Bf[N], Cf[N];
static int64_t Ai[N], Bi[N], Ci[N];
static int mismatches = 0;
%(runs)s
int main(void) {
    for (int i = 0; i < N; i++) {
        Af[i] = rand_f(); Bf[i] = rand_f_near(Af[i]); Cf[i] = rand_f_near(Bf[i]);
        Ai[i] = rand_i(); Bi[i] = rand_i_near(Ai[i]); Ci[i] = rand_i_near(Bi[i]);
    }
    /* the first launch decides whether there is a device at all */
    setenv("AIL_GPU", "force", 1);
    %(calls)s
    printf("DONE mismatches=%%d device=%%s\n", mismatches, gk_dev);
    return 0;
}
'''

RUN_TEMPLATE = r'''
static void run_%(name)s(void) {
    static unsigned ef[N]; static %(rt)s ev[N];
    int clean = 0, flagged = 0, checked = 0, missed = 0, spurious = 0, bad = 0;
    %(pk_decl)s
    %(rt)s *dres = malloc((size_t)N * sizeof(%(rt)s));
    /* every kernel gets its own trust verdict: one that fails its self-test must not make the kernels after it report
       "spurious" (a distrusted class declines every later launch with GK_DECLINED, which is not a flag word) */
    gkv_G.untrusted = 0; %(emu)s_state = 0; %(emu)s_first = 0; gkv_G.distrust[0] = 0;
    for (int i = 0; i < N; i++) {
        ef[i] = %(emu)s(%(one_args)s);
        if (ef[i] == 0) { %(pack)s clean++; } else flagged++;
    }
    if (clean > 0) {
        unsigned f = %(run)s(%(pk_args)s);
        if (f == GK_DECLINED && gkv_G.state != 1) { printf("NODEVICE %(name)s\n"); exit(77); }
        if (f == GK_DECLINED) printf("  %(name)s: the device declined the launch: %%s\n", gkv_G.distrust[0] ? gkv_G.distrust : (gkv_G.why ? gkv_G.why : "?"));
        if (f != 0) spurious++;
        else {
            int j = 0;
            for (int i = 0; i < N; i++) if (ef[i] == 0) { if (memcmp(&dres[j], &ev[i], 8) != 0) { if (bad < 5) printf("  differs at %%d: dev=%%016llx cpu=%%016llx\n", i, (unsigned long long)b_of_raw(&dres[j]), (unsigned long long)b_of_raw(&ev[i])); bad++; } j++; }
        }
    }
    for (int i = 0; i < N && checked < 400; i++) if (ef[i] != 0) {
        %(rt)s tmp = 0;
        unsigned f = %(run)s(%(one_args_tmp)s);
        if (f == 0) { missed++; if (missed < 5) printf("  missed flag %%u at %%d\n", ef[i], i); }
        checked++;
    }
    %(alias)s
    printf("K %(name)s clean=%%d flagged=%%d checked=%%d bad=%%d spurious=%%d missed=%%d\n", clean, flagged, checked, bad, spurious, missed);
    mismatches += bad + spurious + missed;
    free(dres);
}
'''


def _harness(entries, n):
    import gpu
    import gpu_vk
    kernels, runs, calls = [], [], []
    for idx, (name, src, types) in enumerate(entries):
        k = kernel_of(src, types)
        fname = 'ail_gk%d' % idx
        kernels.append(gpu.emit_c(k, fname))
        dev_c, info, words = gpu_vk.device_text(k, fname, idx)
        kernels.append(gpu_vk.VK_RUNTIME + dev_c)
        params, names = gpu.emu_signature(k)
        rt = 'double' if k.res_type == 'f' else 'int64_t'

        def arr(lst):
            return ('Af', 'Bf', 'Cf')['abc'.index(lst)] if k.lists[lst] == 'f' else ('Ai', 'Bi', 'Ci')['abc'.index(lst)]
        one, pk, one_tmp, pk_decl, pack = [], [], [], [], []
        for nm in names:
            if nm.startswith('p_'):
                a = arr(nm[2:])
                one.append('%s + i' % a)
                one_tmp.append('%s + i' % a)
                pk.append('pk_%s' % a)
                if 'pk_%s' % a not in ' '.join(pk_decl):
                    ct = 'double' if a.endswith('f') else 'int64_t'
                    pk_decl.append('%s *pk_%s = malloc((size_t)N * sizeof(%s));' % (ct, a, ct))
                    pack.append('pk_%s[clean] = %s[i];' % (a, a))
            elif nm.startswith('n_'):
                one.append('1'); one_tmp.append('1'); pk.append('clean')
            elif nm == '_cnt':
                one.append('1'); one_tmp.append('1'); pk.append('clean')
            elif nm == '_res':
                one.append('&ev[i]'); one_tmp.append('&tmp'); pk.append('dres')
            elif nm == '_lo':
                raise AssertionError('range kernels are not in the harness')
            else:
                raise AssertionError(nm)
        alias = ''
        if len(k.lists) == 1 and rt == ('double' if list(k.lists.values())[0] == 'f' else 'int64_t'):
            only = pk[0]
            alias = ('if (clean > 0) { %s *inp = malloc((size_t)clean * 8); memcpy(inp, %s, (size_t)clean * 8); '
                     'unsigned f = %s(inp, clean, clean, inp); if (f != 0 || memcmp(inp, dres, (size_t)clean * 8) != 0) { bad++; printf("  in-place differs\\n"); } '
                     'free(inp); }' % (rt, only, fname + '_run'))
        runs.append(RUN_TEMPLATE % dict(alias=alias, name=name, rt=rt, emu=fname, run=fname + '_run', one_args=', '.join(one),
                                         one_args_tmp=', '.join(one_tmp), pk_args=', '.join(pk),
                                         pk_decl='\n    '.join(pk_decl), pack=' '.join(pack)))
        calls.append('run_%s();' % name)
    runs.insert(0, 'static uint64_t b_of_raw(const void *p) { uint64_t b; memcpy(&b, p, 8); return b; }')
    return HARNESS_MAIN % dict(runtime=gpu.RUNTIME, kernels='\n'.join(kernels), n=n, runs='\n'.join(runs),
                               calls='\n    '.join(calls))


def _device_env():
    env = dict(os.environ)
    for key in ('AIL_GPU', 'AIL_GPU_TRACE', 'AIL_GPU_DISABLE', 'AIL_VULKAN_LIB', 'AIL_GPU_DEVICE', 'AIL_GPU_MIN_N', 'AIL_GPU_MODEL',
                'AIL_GPU_AUTO_ANY'):
        env.pop(key, None)
    return env


class BitTests(unittest.TestCase):
    """GPU.md 5.1: the device against the CPU emulation, operand set by operand set."""

    N = 65536

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu2-bits-')
        cls.dir = Path(cls._tmp.name)
        cls.exe = {}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def harness(self, group, entries, extra_env=None):
        src = self.dir / (group + '.c')
        src.write_text(_harness(entries, self.N), encoding='utf-8')
        exe = self.dir / group
        r = subprocess.run([CC, '-O1', '-std=gnu11', '-w', str(src), '-o', str(exe), '-lm', '-ldl'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[:3000])
        env = _device_env()
        env.update(extra_env or {})
        r = subprocess.run([str(exe)], capture_output=True, text=True, env=env, timeout=900)
        if r.returncode == 77:
            if REQUIRE_DEVICE:
                self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set:\n' + r.stdout)
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def check(self, out, entries):
        lines = {m[1]: m for m in (re.match(r'K (\S+) clean=(\d+) flagged=(\d+) checked=(\d+) bad=(\d+) spurious=(\d+) missed=(\d+)', l)
                                   for l in out.splitlines()) if m}
        for name, _, _ in entries:
            self.assertIn(name, lines, out)
            _, clean, flagged, checked, bad, spurious, missed = lines[name].groups()
            self.assertEqual((int(bad), int(spurious), int(missed)), (0, 0, 0), out)
            self.assertGreater(int(clean), self.N // 3, '%s: too few clean elements, the test says little\n%s' % (name, out))
        self.assertIn('DONE mismatches=0', out)

    def test_float_arithmetic_bits(self):
        entries = [e for e in CATALOGUE if e[0].startswith('f_')]
        out = self.harness('bits_float', entries)
        self.check(out, entries)

    def test_comparisons_and_conversions_bits(self):
        entries = [e for e in CATALOGUE if e[0][:2] in ('c_', 'v_')]
        out = self.harness('bits_cmp', entries)
        self.check(out, entries)

    def test_int64_bits(self):
        entries = [e for e in CATALOGUE if e[0].startswith('i_')]
        out = self.harness('bits_int', entries)
        self.check(out, entries)

    def test_a_distrusted_kernel_is_reported_and_does_not_poison_the_next(self):
        """Colab Tesla T4, 2026-10-30: the first int64 kernel whose self-test failed made the device untrusted for the class,
        every later launch of the process returned GK_DECLINED, and the harness counted each of them as a "spurious flag"
        (min/max/lt/eq cannot flag at all).  A declined launch is now named as such with the distrust message, and each
        kernel starts with a fresh trust state, so the second kernel fails (or passes) on its own self-test (k1), not on
        the first one's (k0).  AIL_GPU_INJECT=flip:selftest makes every self-test fail."""
        entries = [e for e in CATALOGUE if e[0] in ('i_add', 'i_min')]
        out = self.harness('bits_declined', entries, {'AIL_GPU_INJECT': 'flip:selftest'})
        self.assertRegex(out, r'i_add: the device declined the launch: device untrusted for int64 kernels: k0 result bits differ')
        self.assertRegex(out, r'i_min: the device declined the launch: device untrusted for int64 kernels: k1 result bits differ')
        self.assertRegex(out, r'K i_add .* spurious=1')
        self.assertRegex(out, r'K i_min .* spurious=1')


# ---------------------------------------------------------------------------------------------------------------------
class Build:
    """One `ail_chatgpt.py compile --gpu` of one program text."""

    def __init__(self, directory, name, text, gpu=True, env=None):
        self.dir = Path(directory)
        self.src = self.dir / (name + '.py')
        self.src.write_text(text.lstrip('\n'), encoding='utf-8')
        self.exe = self.dir / (name + '.exe')
        environ = _device_env()
        environ.update(AIL_NO_CACHE='1', AIL_NO_GENERAL='1')
        environ.update(env or {})
        for key in ('AIL_GPU_BUILD', 'AIL_UNIFIED_FORCE'):
            environ.pop(key, None)
        cmd = [sys.executable, '-B', str(CLI), 'compile', str(self.src), '-o', str(self.exe), '--no-cache',
               '--debug-dir', str(self.dir / (name + '.dbg'))]
        if gpu:
            cmd.append('--gpu')
        r = subprocess.run(cmd, capture_output=True, text=True, env=environ, timeout=900)
        self.returncode, self.stdout, self.stderr = r.returncode, r.stdout, r.stderr

    @property
    def c(self):
        return next(self.dir.glob(self.src.stem + '.dbg/program.c')).read_text(encoding='utf-8')

    def run(self, stdin='', **env):
        environ = _device_env()
        environ.update(env)
        r = subprocess.run([str(self.exe)], input=stdin, capture_output=True, text=True, env=environ, timeout=600)
        return r.stdout, r.returncode, r.stderr


def trace_of(stderr):
    return [l for l in stderr.splitlines() if l.startswith('gpu: ')]


def classes(stderr):
    """The launches of a trace as `k0 n=64 ran` / `k0 replay` / `k0 cpu`: what happened, not on which device."""
    out = []
    for l in trace_of(stderr):
        m = re.match(r'gpu: (k\d+) n=(\d+) device=', l)
        if m:
            out.append('%s n=%s ran' % (m[1], m[2]))
        elif ' replay ' in l:
            out.append(l.split()[1] + ' replay')
        elif ' cpu (' in l:
            out.append(l.split()[1] + ' cpu')
    return out


def device_runs(stderr):
    return [l for l in trace_of(stderr) if re.match(r'gpu: k\d+ n=\d+ device=(?!emulation)', l)]


PROGRAM = r'''
import math

def gen(n: int, seed: int) -> list[float]:
    xs = [0.0] * n
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        xs[i] = float(s) / 1024.0 - 1000000.0
    return xs

def geni(n: int, seed: int) -> list[int]:
    xs = [0] * n
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        xs[i] = s - 1073741824
    return xs

def fmap(a: list[float], b: list[float], c: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * b[i] + c[i] - a[i] * 0.5
    print(out)

def imap(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * 3 + b[i] // 7 - a[i] % 5
    print(out)

def fcomp(a: list[float]) -> None:
    ys = [x * x - 1.0 for x in a]  # ail: gpu
    print(ys)

def lengths() -> None:
    for n in [0, 1, 2, 63, 64, 65, 127, 128, 129, 255, 256, 257, 4095, 4096, 4097, 100003]:
        fmap(gen(n, 1), gen(n, 2), gen(n, 3))
        imap(geni(n, 4), geni(n, 5))
        fcomp(gen(n, 6))

def fadd(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] + b[i]
    print(out)

def fsub(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] - b[i]
    print(out)

def fmul(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * b[i]
    print(out)

def fother(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = min(a[i], b[i]) + max(a[i], b[i]) * 0.5 - abs(a[i]) + (-b[i])
    print(out)
    ys = [1 if a[k] < b[k] else 0 for k in range(len(a))]  # ail: gpu
    print(ys)

def fcmp(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = (a[i] < b[i]) + (a[i] <= b[i]) * 2 + (a[i] == b[i]) * 4 + (a[i] != b[i]) * 8 + (a[i] > b[i]) * 16
    print(out)

def specials() -> None:
    inf = 1e308 * 10.0
    s = [0.0] * 10
    s[1] = -0.0
    s[2] = inf
    s[3] = -inf
    s[4] = 1.0
    s[5] = -1.0
    s[6] = 1e300
    s[7] = -1e300
    s[8] = 1.5
    s[9] = 3.0
    a = [0.0] * 100
    b = [0.0] * 100
    k = 0
    for x in s:
        for y in s:
            a[k] = x
            b[k] = y
            k += 1
    fother(a, b)
    fcmp(a, b)
    for x in s:
        row = [x] * 10
        fadd(row, s)
        fsub(row, s)
        fmul(row, s)
    fadd([1e308, -1e308, 1e308], [1e308, -1e308, -1e308])

def ffloor(a: list[float]) -> None:
    ys = [x // 1 for x in a]  # ail: gpu
    print(ys)

def ftoi(a: list[float]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = int(a[i])
    print(out)

def itof(a: list[int]) -> None:
    ys = [float(x) for x in a]  # ail: gpu
    print(ys)

def conversions() -> None:
    ffloor([1.5, -1.5, 0.5, -0.5, 2.0, -0.0, 4503599627370497.5, 1e300, -1e300])
    ftoi([1.9, -1.9, 0.5, -0.5, 9e18, -9e18, 4503599627370497.5, 1e300 * 0.0])
    itof([1, -1, 9007199254740993, 9007199254740995, -9007199254740993, 9223372036854775807, -9223372036854775807,
          4611686018427387905, 3, 0])

def gather(a: list[float], idx: list[int]) -> None:
    n = len(idx)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[idx[i]] + a[-1]
    print(out)

def branchy(a: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        y = a[i]
        if y > 10.0:
            y = y - 10.0
        elif y < -10.0:
            y = y + 10.0
        else:
            y = y * 0.5
        acc = 0.0
        for j in range(3):
            acc = acc + y
        out[i] = acc if y != 0.0 else -1.0
    print(out)

def structured() -> None:
    xs = gen(5000, 9)
    idx = geni(5000, 10)
    for i in range(5000):
        idx[i] = idx[i] % 5000
    gather(xs, idx)
    branchy(xs)

def iadd(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] + b[i]
    print(out)

def isub(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] - b[i]
    print(out)

def imul(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * b[i]
    print(out)

def ifdiv(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] // b[i]
    print(out)

def imod(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] % b[i]
    print(out)

def ineg(a: list[int]) -> None:
    ys = [-x for x in a]  # ail: gpu
    print(ys)

def iabs(a: list[int]) -> None:
    ys = [abs(x) for x in a]  # ail: gpu
    print(ys)

def fnan(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * b[i] + 1.0
    print(out)

def fidx(a: list[float], idx: list[int]) -> None:
    n = len(idx)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[idx[i]]
    print(out)

def ierrors(which: int, pos: int) -> None:
    n = 5000
    top = 9223372036854775807
    low = -9223372036854775807
    low = low - 1
    ones = [1] * n
    a = [1] * n
    b = [1] * n
    if which == 0:
        a[pos] = top
        iadd(a, ones)
    elif which == 1:
        a[pos] = low
        isub(a, ones)
    elif which == 2:
        a[pos] = 4611686018427387904
        twos = [2] * n
        imul(a, twos)
    elif which == 3:
        a[pos] = low
        ineg(a)
    elif which == 4:
        a[pos] = low
        iabs(a)
    elif which == 5:
        b[pos] = 0
        ifdiv(ones, b)
    elif which == 6:
        a[pos] = low
        b[pos] = -1
        ifdiv(a, b)
    elif which == 7:
        b[pos] = 0
        imod(ones, b)

def xerrors(which: int, pos: int) -> None:
    n = 5000
    fones = [1.0] * n
    idx = [0] * n
    if which == 8:
        idx[pos] = n
    elif which == 9:
        idx[pos] = -n
    else:
        idx[pos] = -n - 1
    fidx(fones, idx)

def ferrors(which: int, pos: int) -> None:
    n = 5000
    fones = [1.0] * n
    huge = 1e308 * 10.0
    a = [1.0] * n
    b = [1.0] * n
    if which == 11:
        a[pos] = 1e30
        ftoi(a)
    elif which == 12:
        a[pos] = huge
        ftoi(a)
    elif which == 13:
        a[pos] = 1e-310
        fadd(a, fones)
    elif which == 14:
        a[pos] = huge - huge
        fadd(a, fones)
    elif which == 15:
        a[pos] = huge
        b[pos] = -huge
        fadd(a, b)
    elif which == 16:
        a[pos] = 1e-200
        b[pos] = 1e-200
        fmul(a, b)
    elif which == 17:
        a[pos] = 1.0000000000000002e-300
        b[pos] = 1e-300
        fsub(a, b)
    elif which == 18:
        a[pos] = huge
        ffloor(a)
    elif which == 19:
        a[pos] = huge
        b[pos] = 0.0
        fnan(a, b)
    else:
        a = [2.0] * n
        b = [3.0] * n
        a[pos] = 1e308
        b[pos] = 1e308
        fmul(a, b)

def errors(which: int, pos: int) -> None:
    if which < 8:
        ierrors(which, pos)
    elif which < 11:
        xerrors(which, pos)
    else:
        ferrors(which, pos)

def big() -> None:
    n = 4300000
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = i * 3 + 1
    s = 0
    for v in out:
        s += v
    print(out[0], out[4194303], out[4194304], out[n - 1], s)
    fs = [float(j) * 0.5 for j in range(n)]  # ail: gpu
    print(fs[0], fs[4194304], fs[n - 1])

def main() -> None:
    which = int(input())
    if which == 100:
        lengths()
    elif which == 101:
        specials()
    elif which == 102:
        conversions()
    elif which == 103:
        structured()
    elif which == 105:
        big()
    else:
        errors(which, int(input()))

main()
'''

ERROR_POSITIONS = (0, 63, 64, 4999)
NO_ERROR_CASES = {9, 20}      # a valid negative index; a product that overflows to inf and nothing else
LISTS_OF = {   # the scenario numbers of errors(): what they exercise
    0: 'add overflow', 1: 'sub overflow', 2: 'mul overflow', 3: 'neg of INT64_MIN', 4: 'abs of INT64_MIN',
    5: 'floor division by zero', 6: 'INT64_MIN // -1', 7: 'modulo by zero', 8: 'index == len', 9: 'index == -len',
    10: 'index == -len - 1', 11: 'int(1e30)', 12: 'int(inf)', 13: 'subnormal operand', 14: 'NaN operand',
    15: 'inf + -inf', 16: 'underflowing product', 17: 'difference that is a subnormal', 18: 'floor of inf',
    19: 'inf * 0', 20: 'overflow to inf',
}


class Programs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu2-')
        cls.dir = Path(cls._tmp.name)
        cls.b = Build(cls.dir, 'g2', PROGRAM)
        cls.cpython = {}
        cls.path = cls.dir / 'g2cpy.py'
        cls.path.write_text(PROGRAM.lstrip('\n'), encoding='utf-8')
        cls.device = None

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.assertEqual(self.b.returncode, 0, self.b.stderr + self.b.stdout)

    def oracle(self, stdin):
        if stdin not in self.cpython:
            self.cpython[stdin] = run_python(self.path, stdin)
        return self.cpython[stdin]

    def have_device(self):
        if Programs.device is None:
            out, rc, err = self.b.run('102\n', AIL_GPU='force', AIL_GPU_TRACE='1')
            Programs.device = bool(device_runs(err))
        if not Programs.device and REQUIRE_DEVICE:
            self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set')
        return Programs.device

    def need_device(self):
        if not self.have_device():
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')

    def modes(self, stdin, with_device=True, noloader=True):
        """Run one scenario in every mode; stdout/exit code must be equal everywhere, and equal CPython's."""
        want_out, want_rc = self.oracle(stdin)
        results = {}
        modes = [('cpu', dict(AIL_GPU='0')), ('emu', dict(AIL_GPU='emu'))]
        if noloader:
            modes.append(('noloader', dict(AIL_GPU='force', AIL_VULKAN_LIB='/nonexistent/libvulkan.so.1')))
        if with_device:
            modes.append(('device', dict(AIL_GPU='force')))
        for name, env in modes:
            out, rc, err = self.b.run(stdin, AIL_GPU_TRACE='1', **env)
            results[name] = (out, rc, err)
        base = results['cpu']
        for name, (out, rc, err) in results.items():
            self.assertEqual((out, rc), (base[0], base[1]), '%s differs from the CPU loop for %r' % (name, stdin))
            plain = lambda e: '\n'.join(l for l in e.splitlines() if not l.startswith('gpu: '))
            self.assertEqual(plain(err), plain(base[2]), '%s: stderr differs for %r' % (name, stdin))
        # the CPU build is CPython's output, or its documented loud stop
        if base[1] == 0:
            self.assertEqual(base[0], want_out, 'the CPU loop differs from CPython for %r' % stdin)
        return results

    # -- lengths and the grid
    def test_lengths_around_the_workgroup_size(self):
        results = self.modes('100\n', with_device=self.have_device())
        emu_classes = classes(results['emu'][2])
        self.assertEqual(len([c for c in emu_classes if c.endswith('ran')]), 15 * 3, emu_classes)   # n = 0 launches nothing
        self.assertFalse([c for c in emu_classes if not c.endswith('ran')], emu_classes)
        for name in ('noloader',):
            # GPU.md 6.4: without a device the launch is declined and the ORIGINAL loop runs (not the emulation)
            self.assertEqual(classes(results[name][2]), [])
            self.assertIn('device unavailable (no Vulkan loader', results[name][2])
            self.assertIn('original loop', results[name][2])
        if 'device' in results:
            self.assertEqual(classes(results['device'][2]), emu_classes)
            self.assertEqual(len(device_runs(results['device'][2])), 15 * 3)

    def test_two_dimensional_grid(self):
        results = self.modes('105\n', with_device=self.have_device())
        self.assertEqual(results['cpu'][0].split('\n')[0].split()[0], '1')
        if 'device' in results:
            self.assertEqual(len(device_runs(results['device'][2])), 2)

    # -- float values
    def test_special_floats(self):
        results = self.modes('101\n', with_device=self.have_device())
        for name, (out, rc, err) in results.items():
            self.assertEqual(rc, 0, err)
        emu = classes(results['emu'][2])
        self.assertTrue(any(c.endswith('replay') for c in emu), emu)            # inf - inf, 1e308 + 1e308 ... ran, but the last fadd
        if 'device' in results:
            self.assertEqual(classes(results['device'][2]), emu)

    def test_conversions_and_structured_kernels(self):
        for scenario in ('102\n', '103\n'):
            results = self.modes(scenario, with_device=self.have_device())
            if 'device' in results:
                self.assertEqual(classes(results['device'][2]), classes(results['emu'][2]), scenario)

    # -- errors at chosen elements: the device flags, the CPU loop replays and prints what the CPU build prints
    def test_errors_replay_at_every_position(self):
        have = self.have_device()
        for which in sorted(LISTS_OF):
            for pos in ERROR_POSITIONS:
                stdin = '%d\n%d\n' % (which, pos)
                results = self.modes(stdin, with_device=have, noloader=False)
                emu = classes(results['emu'][2])
                if 'device' in results:
                    self.assertEqual(classes(results['device'][2]), emu, '%s at %d' % (LISTS_OF[which], pos))
                if which not in NO_ERROR_CASES:
                    self.assertTrue(any(c.endswith('replay') for c in emu), '%s at %d: %s' % (LISTS_OF[which], pos, emu))

    # -- the switches
    def test_a_device_without_the_features_uses_the_emulation(self):
        self.need_device()
        for missing, what in (('f64', 'shaderFloat64'), ('rte', 'round-to-nearest-even'), ('szinp', 'signed-zero')):
            out, rc, err = self.b.run('100\n', AIL_GPU='force', AIL_GPU_TRACE='1', AIL_GPU_DISABLE=missing)
            want = self.oracle('100\n')
            self.assertEqual((out, rc), want)
            self.assertFalse([l for l in device_runs(err) if ' k0 ' in l or ' k2 ' in l or ' k3 ' in l or ' k4 ' in l],
                             'a binary64 kernel ran on a device without %s' % what)
            self.assertIn('device unavailable', err)
        # the int64 kernel (imap, k1) still uses the device
        out, rc, err = self.b.run('100\n', AIL_GPU='force', AIL_GPU_TRACE='1', AIL_GPU_DISABLE='f64')
        self.assertTrue([l for l in device_runs(err) if l.startswith('gpu: k1 ')], err[:600])
        out, rc, err = self.b.run('100\n', AIL_GPU='force', AIL_GPU_TRACE='1', AIL_GPU_DISABLE='i64')
        self.assertFalse(device_runs(err))
        self.assertEqual((out, rc), self.oracle('100\n'))

    def test_min_n_replaces_the_cost_model(self):
        """AIL_GPU_MIN_N=n: the device for launches of at least n elements, the original loop below (GPU.md 6.4)."""
        self.need_device()
        out, rc, err = self.b.run('100\n', AIL_GPU_TRACE='1', AIL_GPU_MIN_N='4096')
        self.assertEqual((out, rc), self.oracle('100\n'))
        ran = {int(re.match(r'gpu: k\d+ n=(\d+) device=', l)[1]) for l in device_runs(err)}
        self.assertFalse([n for n in ran if n < 4096], sorted(ran))
        self.assertTrue(4096 in ran and 100003 in ran, sorted(ran))
        self.assertIn('n = 4095 is below AIL_GPU_MIN_N = 4096', err)
        out, rc, err = self.b.run('100\n', AIL_GPU_TRACE='1', AIL_GPU_MIN_N='64')
        self.assertTrue(any(' n=64 ' in l for l in device_runs(err)), err[:800])

    def test_the_trace_names_the_device(self):
        self.need_device()
        out, rc, err = self.b.run('102\n', AIL_GPU='force', AIL_GPU_TRACE='1')
        self.assertTrue(any(re.match(r'gpu: k\d+ n=\d+ device=\S', l) and 'emulation' not in l for l in trace_of(err)), err)

    def test_the_wanted_device_by_name(self):
        self.need_device()
        out, rc, err = self.b.run('102\n', AIL_GPU='force', AIL_GPU_TRACE='1', AIL_GPU_DEVICE='no-such-device')
        self.assertEqual((out, rc), self.oracle('102\n'))
        self.assertFalse(device_runs(err))
        self.assertIn('device unavailable', err)

    # -- the compile note
    def test_the_compile_note_names_the_path(self):
        notes = [l for l in self.b.stderr.splitlines() if l.startswith('note:') and 'kernel k' in l]
        self.assertGreaterEqual(len(notes), 10, self.b.stderr[:2000])
        self.assertTrue(all('SPIR-V' in l and 'CPU emulation' in l for l in notes), notes[:3])
        self.assertTrue(any('for int64 (' in l for l in notes))
        self.assertTrue(any('binary64 + int64' in l for l in notes))

    def test_c_contains_the_spirv_and_the_loader_is_never_linked(self):
        c = self.b.c
        self.assertIn('static const uint32_t ail_gk0_spv[', c)
        self.assertIn('dlopen', c)
        self.assertNotIn('#include <vulkan', c)
        r = subprocess.run(['ldd', str(self.b.exe)], capture_output=True, text=True)
        if r.returncode == 0:
            self.assertNotIn('libvulkan', r.stdout)

    def test_without_the_switch_nothing_changes(self):
        plain = Build(self.dir, 'g2plain', PROGRAM, gpu=False)
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertNotIn('gkv_', plain.c)
        self.assertNotIn('_spv', plain.c)


TINY = '''
def f(a: list[float]) -> None:
    ys = [x * 2.0 + 1.0 for x in a]  # ail: gpu
    print(ys)

def main() -> None:
    f([1.0, 2.5, -0.0])

main()
'''


class Unavailable(unittest.TestCase):
    """The runtime must not need Vulkan: a program with kernels links and starts on a machine without the loader."""

    def test_a_kernel_program_runs_with_no_loader(self):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        with tempfile.TemporaryDirectory(prefix='ail-gpu2-nol-') as d:
            b = Build(d, 'tiny', TINY)
            self.assertEqual(b.returncode, 0, b.stderr)
            want = run_python(b.src)
            for env in (dict(AIL_VULKAN_LIB='/nonexistent'), dict(AIL_GPU='force', AIL_VULKAN_LIB='/nonexistent'),
                        dict(AIL_GPU='force', AIL_VULKAN_LIB='/dev/null'), dict(AIL_GPU='emu'), dict(AIL_GPU='0'), dict()):
                out, rc, err = b.run('', AIL_GPU_TRACE='1', **env)
                self.assertEqual((out, rc), want, (env, err))


    def test_a_static_build_takes_the_cpu_path(self):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        if sys.platform != 'linux':
            raise unittest.SkipTest('static glibc')
        with tempfile.TemporaryDirectory(prefix='ail-gpu2-static-') as d:
            b = Build(d, 'tiny_static', TINY, env=dict(AIL_STATIC='1'))
            if b.returncode != 0 and 'cannot find -lc' in b.stderr + b.stdout:
                raise unittest.SkipTest('no static libc')
            self.assertEqual(b.returncode, 0, b.stderr)
            out, rc, err = b.run('', AIL_GPU='force', AIL_GPU_TRACE='1')
            self.assertEqual((out, rc), run_python(b.src))
            self.assertIn('static build never opens the Vulkan loader', err)
            self.assertIn('gpu: k0 original loop', err)
            self.assertNotIn('device=emulation', err)


if __name__ == '__main__':
    unittest.main()
