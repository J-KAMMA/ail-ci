# GPU offload (design 2026-10-29; G1 to G4 built (6.1 to 6.4), G5 (typed arrays on the device) in 6.5)

Design note for running parts of an AIL program on a GPU. Stages G1 to G4 and the typed-array part of G5 are built (sections 6.1 to 6.5); the rest is design. The roadmap keeps the
implementation last (IR core -> correctness -> coverage -> FFI/modules -> tooling -> release -> GPU); this note fixes the
design now so the earlier stages do not close doors. Oracle: CPython 3.12, as everywhere else.

The one rule that drives every choice below:

> **A program built with the GPU enabled prints exactly what the same build prints with `AIL_GPU=0`**, stdout and exit
> code, on every device and on no device. The CPU build already matches CPython (or refuses by name), so the GPU build
> does too. The GPU never decides what an error is, how a float rounds, or in which order a sum is taken: when it cannot
> guarantee the CPU's answer it either is not used (compile-time refusal or CPU-only lowering) or its result is thrown
> away and the loop is run again on the CPU (**CPU replay**, section 3.1).

Words used: *kernel* = one loop body compiled for the GPU; *launch* = one run of a kernel over n elements; *device* = a
Vulkan physical device (a real GPU or the CPU implementation lavapipe); *flag* = a per-launch word the kernel sets when
it hit something it must not decide itself.

Verification status is given inline: **[verified 2026-10-29]** means checked on the laptop or with `apt-cache` while
writing this note; **[unverified]** means taken from memory or vendor material and to be checked in the stage named.

## 0. Strategy: vendor-neutral GPU (owner decision 2026-10-29)

**Goal: break CUDA lock-in.** The same plain Python program runs on AMD, Intel, NVIDIA and mobile GPUs through one
backend, Vulkan compute with SPIR-V, and prints CPython's output on every vendor. Users never write CUDA, a kernel
language or a vendor API; they write Python loops and (section 8) call vendor-neutral array operations.

- **Vulkan only.** No CUDA, HIP, Metal or D3D12 backend (section 2.3). A CUDA backend would make NVIDIA the best-tested
  and fastest target and pull users back into the lock-in this work exists to break; it is rejected, not deferred.
- **Exact on every vendor** follows from the rule above: the GPU only computes what it can compute bit for bit, and
  everything else is refused, kept on the CPU or replayed. Two vendors cannot disagree, because neither may decide.
- **What "mobile" means honestly**: many mobile GPUs have no `shaderFloat64` or `shaderInt64` **[unverified per device]**.
  There, float64 and int64 loops run on the CPU (same output); only kernels the device supports exactly are offloaded.
- **First benchmark goal (B0)**: one AIL program (a fused element-wise chain plus a matmul, section 8) on the laptop's AMD
  780M and on a Colab NVIDIA GPU, both through Vulkan, against PyTorch + CUDA on the same Colab GPU. Report the ratio per
  device. **Unmeasured**; it needs NVIDIA's Vulkan driver inside Colab, which is **[unverified]** (section 7).

**Prior attempts and what AIL does differently.** Mojo/Modular offers a new language (a Python superset) with its own
compiler and MAX runtime targeting several vendors; Triton is a Python-embedded kernel DSL compiled through each vendor's
toolchain (mainly NVIDIA and AMD); tinygrad is a Python tensor library with many small backends (CUDA, HIP, Metal,
OpenCL, WebGPU and others); ROCm/HIP is AMD's CUDA-like stack that ports CUDA code to AMD; SYCL (oneAPI DPC++,
AdaptiveCpp) is single-source C++ over several vendors' runtimes **[descriptions from memory, unverified in detail]**.
Each asks the user to learn a new language, a DSL, a tensor API or a vendor SDK, and none promises results equal to
CPython's. AIL keeps **plain Python** that CPython also runs, **exact results** (CPython's output or a refusal by name),
and **no vendor SDK**: only the Vulkan loader present on the system and SPIR-V that AIL emits itself.

## 1. Scope: what goes to the GPU

### 1.1 Eligible constructs (typed path only)

Only code the typed path already compiles with C `double` / `int64_t` and contiguous buffers is a candidate. The general
(boxed) path never offloads: a boxed object, a refcount or a GC pointer cannot be moved to a device.

A loop is a *GPU candidate* when it has one of these shapes, all of which CPython runs unchanged:

| shape (Python surface) | becomes |
| --- | --- |
| `out = [expr for x in xs]`, `out = [expr for i in range(a, b)]`, `[expr for x, y in zip(xs, ys)]` | map kernel; the list is allocated on the CPU, filled from the device |
| `for i in range(a, b): out[i] = expr` with `out` sized before the loop (`[0.0] * n`, `array('d', ...)`) | map kernel (the `parallel for` shape of AIL_REFERENCE_MORE "Parallel") |
| `ThreadPoolExecutor(...).map(f, xs)` / `Pool(k).map(f, xs)` already lowered by `typedpar.py` | map kernel over the generated `_ail_pmap` loop |
| `sum(<int expr> for ...)`, `min(...)` / `max(...)` of an int or float generator or comprehension | map kernel + reduction (section 3.4) |
| `s += <float expr>` carried through the loop | map kernel for the expression, the sum itself on the CPU (section 3.4) |

Element types: `float` (IEEE binary64, never binary32), `int` held as int64 by the typed path, `bool`. Storage: typed
`list[float]` / `list[int]` (`ail_flist` is `{double *p; int64_t n, cap;}`, cruntime.py) and `array.array('d'|'q')`
**[verified: struct in cruntime.py; array support listed in AIL_REFERENCE_MORE]**.

The body may contain: `+ - *` on floats and ints, `/` and `math.sqrt` on floats (from stage G5), `//` and `%` on ints,
comparisons, `and`/`or`/`not` (short-circuit kept as branches), `x if c else y`, `if`/`else`, `abs`, `min`/`max` of two
or three scalars, `float(int)`, `int(float)`, `math.floor/ceil/trunc`, reads `ys[j]` of other typed lists (any index
expression; bounds checked), an inner `for j in range(K)` with a loop-invariant `K`, local scalars created in the body,
and calls of module-level functions that take and return only int/float and pass the same checks (inlined into the
kernel; recursion refused). This is the `parallel.py` body rule minus what a GPU cannot do, plus reads with computed
indices (they only need a bounds check).

### 1.2 What stays on the CPU

- Everything with a boxed value, a str, bytes, a dict, a set, an object, `print`, I/O, `try`, `raise`, `yield`, `append`,
  `pop`, a global write, a nested list, a bigint-marked function (`bigcap.py`: no typed clone, so no candidate).
- Transcendental and libm functions: `math.sin/cos/exp/log/pow/atan2/...`, float `**`, float `%`, `round`, `math.fsum`.
  CPython's result is glibc's; no GPU API promises glibc's bits, and a software copy of glibc's libm in SPIR-V is far
  more work than it is worth. A loop that calls one stays on the CPU (it may still be a CPU `parallel for`).
- Float reductions themselves (section 3.4).
- numpy: AIL has no numpy today (no `numpy` in the reference docs **[verified by grep]**). A numpy subset is a
  modules/FFI question, not a GPU one; it is out of scope here and listed as open question Q5.

### 1.3 How a loop is selected: a comment marker plus a proof

The user writes a comment on the line before the loop:

```python
out = [0.0] * n
# ail: gpu
for i in range(n):
    out[i] = a[i] * b[i] + c[i]

ys = [x * x - 1.0 for x in xs]  # ail: gpu
```

- CPython ignores a comment, so the program is unchanged for the oracle. The front end reads it with `tokenize` (the
  `ast` drops comments), keyed by line.
- The compiler then **proves** eligibility (1.1 plus the race-freedom proof of `parallel.py`). A marked loop that fails
  is refused **by name** in a `--gpu` build, with the usual form:
  `prog.py:12: GPU loop: math.exp has no exact GPU form; write instead: drop '# ail: gpu' (the loop runs on the CPU) or move the math.exp call out of the loop`.
  In a build without `--gpu` the marker is ignored silently (it is a hint, not semantics; the output is the same).
- `compile --gpu` (env `AIL_GPU_BUILD=1`) turns the feature on for a build. Without it no kernel, no Vulkan loader and
  no GPU runtime is in the binary, and the C is byte-identical to today's (the same gate idea as `biggate.py`).
- `--gpu=auto` (stage G7) also offloads unmarked loops that pass the proof and the cost model, without refusals.

Rejected alternatives:

- *A decorator `@ail.gpu`*: CPython would need an importable `ail` module, so the program is no longer plain Python
  (or needs a stub installed for the oracle). Rejected.
- *AIL-syntax `gpu for`* only: the Python surface is the main surface; a keyword CPython cannot parse breaks the oracle.
  The AIL surface may get `gpu for` as sugar for the same marker later.
- *Automatic only, no marker*: the user gets no diagnostic when the loop they care about silently stays on the CPU.
  Kept as the `auto` mode on top of the marker, not instead of it.

## 2. Backend: Vulkan compute with SPIR-V, loaded at run time

### 2.1 Decision

- Kernels are emitted by AIL itself as **SPIR-V binary** (an in-house Python emitter, a few hundred lines, same policy
  as the bigint core: small things written in-house) and embedded in the C file as `static const uint32_t[]`.
- The runtime talks to the **Vulkan 1.1+ compute API** through a loader opened with **`dlopen("libvulkan.so.1")`**
  (`LoadLibrary("vulkan-1.dll")` on Windows). No `-lvulkan` at link time, no header-only dependency beyond the few
  Vulkan structs the runtime declares itself.
- No device, no loader, no `shaderFloat64`/`shaderInt64` feature, or an init failure: every launch runs the CPU loop. The
  output is the same by construction; `AIL_GPU_TRACE=1` prints the reason to stderr for tests and users.

### 2.2 Why Vulkan

1. **The laptop iGPU has a Vulkan driver on Windows** **[verified 2026-10-29: `C:\Windows\System32\vulkan-1.dll` exists,
   AMD `amdvlk64.dll` (~100 MB) in the DriverStore, video controller "AMD Radeon 780M Graphics"]**. Linux has RADV
   for the same chip. There is no NVIDIA card, so CUDA cannot run on the laptop at all.
2. **CI has a CPU implementation of exactly the same API**: Mesa lavapipe. In this WSL it is installed and enumerates
   as `llvmpipe (LLVM 20.1.2, 256 bits)`, Vulkan 1.4, `shaderFloat64=1`, `shaderInt64=1`,
   `shaderRoundingModeRTEFloat64=1`, `shaderDenormPreserveFloat64=0` **[verified 2026-10-29 with a probe program against
   `libvulkan1 1.3.275`]**. The same SPIR-V words run on lavapipe in CI and on the iGPU on the laptop.
3. **SPIR-V is compiled by AIL, ahead of time**, so the user's machine needs no shader compiler, and AIL controls the
   bits that matter for exactness: the `NoContraction` decoration on every float op (no fused multiply-add), the
   `RoundingModeRTE` and `DenormPreserve` execution modes (`SPV_KHR_float_controls`, core in 1.2).
4. **Binary and dependency cost is small for the user**: `libvulkan.so.1` is 510,592 bytes and already present on most
   desktops **[verified size in this WSL]**; it is opened at run time, so a binary without it still starts.

### 2.3 Rejected backends

| backend | why not |
| --- | --- |
| OpenCL (C source or SPIR-V) | Its float rules are better (OpenCL C requires correctly rounded `double` `/` and `sqrt`) **[unverified: from memory of the OpenCL C spec, re-read if Q2 reopens]**. But: the CPU implementation for CI, PoCL, pulls clang-16 and LLVM 16: `libpocl2t64` 83,673 KB + `libllvm16t64` 120,178 KB + `libclang-cpp16t64` 60,592 KB installed **[verified `apt-cache show`]**; no OpenCL vendor is registered under `HKLM\SOFTWARE\Khronos\OpenCL\Vendors` on the laptop **[verified empty; the AMD driver may register elsewhere, unverified]**; OpenCL C source means a compiler at run time on the user's machine; SPIR-V for OpenCL (`cl_khr_il_program`) support on AMD is doubtful **[unverified]**. Kept as the fallback if Vulkan's float controls fail in G2 (Q2). |
| CUDA / PTX | No NVIDIA GPU on the laptop and no GPU in CI: nothing CUDA-specific could be tested where AIL is tested. Its float semantics are good (`add.rn.f64`, `div.rn.f64`, `sqrt.rn.f64`, f64 denormals kept) **[unverified: from memory of the PTX ISA]**. **Rejected, not deferred**: a CUDA backend adds the vendor lock-in this work is meant to break (section 0). NVIDIA GPUs are reached through their Vulkan driver instead. |
| HIP / ROCm | The 780M is not on the ROCm support list **[unverified]**; the stack is GBs; no CPU implementation for CI. |
| D3D12 compute | WSL exposes `/dev/dxg` and `/usr/lib/wsl/lib/libd3d12.so` **[verified]**, so it would reach the real iGPU from WSL. But it is Windows/WSL only, needs DXIL and dxc, and has no CPU implementation in Ubuntu CI. Mesa's Vulkan-on-D3D12 driver (dozen) is not in Ubuntu's package: the ICD list here is asahi, gfxstream, intel, intel_hasvk, lvp, nouveau, radeon, virtio **[verified]**. |
| WebGPU / wgpu, Metal | No binary64 in WGSL or Metal **[unverified for current spec revisions]**; Python floats are binary64, binary32 is a silent difference. So macOS gets no GPU offload (MoltenVK runs on Metal: no `shaderFloat64`). |
| OpenMP `target` offload (gcc amdgcn) | Needs the ROCm runtime on Linux, nothing on Windows, no CPU device that tests the offload path. |

### 2.4 Linking vs loading

`dlopen` is chosen: a linked `-lvulkan` makes every GPU-enabled binary fail to start on a machine without the loader,
which would turn a performance feature into a hard dependency. The runtime resolves about 25 entry points
(`vkCreateInstance` ... `vkCmdDispatch`, `vkWaitForFences`) through `vkGetInstanceProcAddr`. Static builds
(`AIL_STATIC=1`) keep `dlopen` (glibc warns for static `dlopen`; the runtime then always takes the CPU path and says so
in the trace, decided at G3).

### 2.5 Size budget

- Programs built without `--gpu`, or with `--gpu` but no kernel: byte-identical C and binary to today.
- A program with kernels: the Vulkan runtime (instance, device pick, buffer pool, dispatch, fence, CPU replay glue,
  estimated 1,000-1,500 lines of C) plus the SPIR-V words (estimated 2-8 KB per kernel). Budget: **+40 KB** binary per
  program, built with `-ffunction-sections` / `--gc-sections` like the bigint runtime. The estimate is **[unverified]**;
  G3 measures it and the budget is a G3 done-condition.

## 3. Zero silent differences on the GPU

Every row says what CPython does, what the GPU might do, and the rule. "Replay" = section 3.1.

### 3.1 The flag and CPU replay

A kernel writes only to device buffers. Every launch has a flag word (atomic OR, one per launch). When any element meets
a condition in the table below, the kernel sets a bit and stops working on that element. After the fence:

- flag == 0: copy the results into the CPU list.
- flag != 0: **discard every device result and run the original CPU loop from the start.** The CPU loop then prints,
  raises, promotes or stops exactly as the `AIL_GPU=0` build does, including which element fails first.

Replay is exact because the eligible body (section 1.1) has no visible effect except writes to `out[i]`, `out` is not
read by the body and not aliased with an input (checked at run time by pointer comparison, section 4.2), and the CPU
inputs were not touched. Replay costs one CPU run of the loop, only on the rare path.

### 3.2 Float rules

| issue | CPython | GPU risk | rule |
| --- | --- | --- | --- |
| `+ - *` rounding | each op rounded to nearest-even, binary64 | Vulkan's precision table requires correct rounding for add/sub/mul **[unverified: Vulkan spec section "Precision and Operation of SPIR-V Instructions", G2 records the text]** | **match exactly**: `OpFAdd/OpFSub/OpFMul` on f64 with `RoundingModeRTE`; device without `shaderRoundingModeRTEFloat64` -> CPU |
| fused multiply-add | never fused (AIL builds with `-ffp-contract=off` for the same reason, pyc.py) | a driver may contract `a*b+c` | **match exactly**: every f64 op decorated `NoContraction`; the emitter never emits `Fma` |
| `/`, `math.sqrt` | correctly rounded (IEEE; glibc `sqrt` is) | Vulkan allows several ULP for `OpFDiv` and sqrt **[unverified, same section]** | **match exactly in software** from G5: f64 division and sqrt written in SPIR-V with int64 mantissa arithmetic (round-to-nearest-even, exact remainder test). Before G5: a loop with `/` or `sqrt` is refused under the marker ("`/` needs stage G5") |
| denormals (subnormals) | kept (gradual underflow) | flushed to zero unless `DenormPreserve` is honoured; lavapipe reports `shaderDenormPreserveFloat64=0` **[verified]** | **guard + replay**: before each f64 op the kernel checks the operands' exponent fields; any operand or a possible result with magnitude below 2^-1000 (nonzero), or a `*`/`/` whose exponent sum can fall below -1000, sets the flag. Conservative on purpose: a false alarm only costs a replay. A device that reports `DenormPreserve` may drop the guards later, after the G2 bit-tests pass on it |
| NaN sign and payload | x86 produces the default NaN; `math.copysign`, `struct.pack` and `float.hex` can reveal it | a GPU may produce another NaN | **guard + replay**: a NaN result from non-NaN operands sets the flag. How a device passes a NaN operand through `+ - *` is not guaranteed either, so any NaN operand also sets the flag |
| `inf` | IEEE | IEEE | **match**: `inf` arithmetic is exact; `inf - inf` is the NaN case above |
| comparisons | `<` false with NaN, `!=` true with NaN | ordered/unordered op choice | **match**: `<,<=,>,>=,==` -> `OpFOrd*`; `!=` -> `OpFUnordNotEqual` |
| `min`/`max` of scalars | `max(a, b)` keeps the first of equal values (`max(0.0, -0.0)` is `0.0`, `max(-0.0, 0.0)` is `-0.0`); NaN is position-dependent (`max(nan, 1.0)` is `nan`, `max(1.0, nan)` is `1.0`) **[verified with CPython 3.12.3]** | `FMax`/`NMax` pick differently | **match**: emitted as Python's compare-and-select sequence, never `FMin/FMax` |
| `abs` | clears the sign | - | **match**: sign-bit clear |
| `float(i)` | rounded to nearest-even | conversion rounding mode | **match**: `OpConvertSToF` with `FPRoundingMode RTE` |
| `int(x)`, `floor/ceil/trunc` | exact; NaN/inf raise; beyond int64 becomes a big int | out of range is undefined | **match** in range; NaN, inf or a value outside int64 sets the flag -> replay (the CPU raises or promotes) |
| `math.exp`, `**`, `%` on floats, libm | glibc's bits | no matching GPU function | **refuse** under the marker; the loop stays on the CPU |
| binary32 | never used | faster on GPUs | **never**: no f32 anywhere in a kernel |

### 3.3 Integer rules

| issue | CPython | rule |
| --- | --- | --- |
| overflow of `+ - *` | exact big ints | The typed path keeps int64 with the loud `integer overflow` stop (BIGINT.md section 4, DIFFERENCES C288); bigint-marked functions are not candidates. On the GPU each op checks overflow (sign tests for add/sub, `OpSMulExtended` high word for mul) and sets the flag -> replay, which produces the CPU build's exact behaviour. Requires `shaderInt64`; without it the CPU runs the loop |
| `//`, `%` | floor division, divisor's sign | **match**: emitted as `OpSDiv`, the remainder as `a - (a // d) * d` (never `OpSRem`, see 6.3 "Tesla T4"), plus the floor fix-up; `INT64_MIN // -1` sets the flag |
| `ZeroDivisionError` | raised at the first failing element | divisor 0 sets the flag -> replay raises it at the same element with the same text |
| `IndexError` | raised at the first failing element | every `ys[j]` is bounds-checked (negative index normalised as Python does); a miss sets the flag -> replay |
| `<<`, `>>`, `**` on ints | big ints | **refuse** under the marker until a stage needs them (`**` and `<<` by a variable already mark a function bigint, so it is no candidate) |
| bool | `True + 1 == 2` | **match**: bools are int64 0/1 in the kernel |

### 3.4 Reductions

CPython 3.12 `sum()` of floats is a sequential compensated (Neumaier) sum: `sum([0.1] * 10)` prints `1.0` on 3.12
**[verified]**, and `s += x` in a loop is plain left-to-right rounding. Both depend on the order; a GPU tree does not
give the same bits.

| reduction | rule |
| --- | --- |
| float `sum(...)`, `s += x`, `math.fsum` | **GPU map, CPU reduce**: the kernel computes the element values into a buffer; the CPU then adds them in order with the exact code the CPU build uses (Neumaier for `sum`, plain `+=` for the loop). Exact, and the expensive part (the element expression) still runs on the device. Never a tree sum of floats |
| int `sum(...)`, `t += i_expr` | **GPU scan with a range check**: an int64 tree computes the total and also the minimum and maximum *prefix* sum (a standard scan, every partial checked for overflow). If any prefix leaves int64, flag -> replay. Otherwise the sequential CPU loop would have produced the same total without overflow, so the result equals the CPU build's. (A plain tree would print the right total for `[MAX, 1, -1]` where the typed CPU build stops loudly: correct for CPython, but a difference from `AIL_GPU=0`, which section 0 forbids) |
| float `min`/`max` | **tree with (value, index)**: combine keeps the smaller index on `==` (so `-0.0`/`0.0` ties pick the first, as CPython); any NaN element sets the flag -> replay (CPython's NaN result depends on position) |
| int `min`/`max` | tree with (value, index), exact |
| `any`/`all` of a comparison | exact (OR/AND tree); short-circuit has no visible effect in an eligible body |

### 3.5 Things that are not differences but must be kept

- **Evaluation of errors**: an element that would raise is never "skipped"; the flag forces the CPU to find the first one.
- **Short-circuit**: `a and f(b)` is emitted as a branch, because `f(b)` may set the flag (index, zero division).
- **Determinism across devices**: the flag rules depend only on values, not on the device, except the
  `DenormPreserve`/RTE feature checks, which only choose between the GPU and the CPU, both exact.

## 4. Data movement and memory

### 4.1 When transfers happen

G3..G7: **copy in at launch, copy out after the fence, nothing resident.** For each launch:
1. Inputs (read-only lists/arrays and scalars) are copied into host-visible staging buffers; scalars go in push constants.
2. Dispatch, one fence, wait.
3. On flag 0, the output buffer is copied into the CPU list (allocated by the CPU before the launch, so `len`, identity
   and the list header stay CPU objects).

On the 780M the memory is shared with the CPU (UMA), so "copy" is a `memcpy` into host-visible memory, not a PCIe
transfer **[unverified that the driver exposes a host-visible device-local heap for the iGPU; G7 checks]**. G8 may
import the list's own buffer (`VK_EXT_external_memory_host`) for zero copy and keep a buffer resident between two
consecutive launches that use the same unchanged list.

### 4.2 Sharing semantics with Python lists

- A kernel never holds a reference to a list after the launch returns: the launch is synchronous, like a function call.
- Inputs are snapshotted at launch; the body cannot write them (proof), and no other thread can (the typed path's race
  rules; a launch inside a `parallel for` body is refused).
- `out` must not alias an input. The proof refuses the same name; two names for one list (`ys = xs`) are caught by a
  run-time pointer comparison of the buffers before the launch -> CPU loop (not a refusal: the output is the same).
- A comprehension result is a new list, so it has no alias by construction.

### 4.3 Cost model: small inputs stay on the CPU

Decided at run time per launch, with a static shortcut:

- **Static**: if `n` is a compile-time constant below `N_MIN`, no kernel is emitted (and a marked loop gets a note, not a
  refusal: "`# ail: gpu` ignored: n = 100 is below the GPU threshold").
- **Run time**: `work = n * ops_per_element` (ops counted by the emitter, inner loops multiplied by `K` when known).
  Launch on the device only if `work >= W_LAUNCH` and, for the first launch of the process, `work >= W_INIT` (device
  creation is paid once; on lavapipe it includes LLVM start-up). Otherwise the CPU loop runs.
- Starting constants (placeholders, **[unverified]**, measured in G7 on the laptop iGPU with `tools/icount.c` for the CPU
  side and wall time for the device): `N_MIN = 4096`, `W_LAUNCH = 2^22`, `W_INIT = 2^26`. They live in one table in the
  runtime, overridable with `AIL_GPU_MIN_WORK` for tests.
- `AIL_GPU=0` never uses the device; `AIL_GPU=force` ignores the cost model (tests use it so tiny inputs exercise the
  device path); unset = the cost model.
  **Superseded by 6.4:** the constants and the rule are those of 6.4 (`AIL_GPU=auto`, margin 1.5, cold start earned back).
- No speed claim is made in this note. fp64 throughput on an RDNA3 iGPU is a small fraction of fp32
  **[unverified: vendor ratio]**, so the benefit for float64 kernels may be small; G7 measures before `auto` is offered
  and the result can stop the work (Q3).

### 4.4 Memory

Device buffers come from one pool per process, freed at exit; a launch whose buffers do not fit (the laptop has 6 GB in
WSL, the iGPU shares system RAM) falls back to the CPU instead of failing. lavapipe in CI runs in the runner's memory.

## 5. Testing

### 5.1 In CI, on lavapipe (no GPU, no paid runners)

- **One job, `gpu`**, in `tests.yml` beside the 20 shards: installs `mesa-vulkan-drivers` (lavapipe; 96,231 KB installed
  plus `libllvm20` 140,245 KB **[verified `apt-cache show`; whether the runner image already has it is unverified, G3
  checks and caches]**), sets `VK_ICD_FILENAMES` to `lvp_icd.json` and `LP_NUM_THREADS=2`, and runs only the
  `test_ail_gpu*.py` modules. Target: under 5 minutes of runner time; the modules are kept out of the 20 shards
  (`tools/ci_shards.py`), so they add one job, not time to every shard.
- **Differential**: each test program is run by CPython 3.12 and built twice by AIL, `AIL_GPU=force` and `AIL_GPU=0`;
  stdout and exit code must equal CPython's in both. The forced run must also show in `AIL_GPU_TRACE` that the kernel
  ran on the device (`gpu: k0 n=4096 device=llvmpipe`): a test that silently fell back to the CPU fails.
- **Many cases per binary**: one test program covers one feature with dozens of inputs (gcc time per build dominates, as
  in the other test modules), so a stage adds a handful of builds, not hundreds.
- **Bit tests of the float ops** (G2, G5): one kernel applies each op to ~100k operand pairs (random bit patterns plus
  the edge set: +-0, smallest/largest subnormal and normal, 1 +- ulp, powers of two, halfway cases for `/` and `sqrt`,
  NaN, inf) and the C side compares every result bit with the CPU's `double` op. This checks the device, not CPython,
  so it needs no oracle run.
- **Replay tests**: `AIL_GPU_FAULT=<element>` (test-only, compiled in by the test build) forces the flag at one element,
  so every replay path (index, zero division, overflow, denormal guard, NaN) runs on lavapipe even where the guard would
  not fire naturally; plus real triggers (an `IndexError` at element 3000 of 4096).
- **Refusals**: each refusal message, with file:line and its `write instead:` line, has a case; the same program without
  `--gpu` builds and runs on the CPU with CPython's output.
- **No cost**: a program without `--gpu`, and a `--gpu` program without a marker (before G7), give byte-identical C.
- **SPIR-V validity**: every emitted module passes `spirv-val` (`spirv-tools`, 34,578 KB installed **[verified]**, CI and
  dev only, never a run-time dependency).
- **Semantics without Vulkan** (G1): the kernel IR also lowers to a C function that emulates the kernel on the CPU
  (same flags, same replay). Those tests run in the normal shards, need no driver, and catch most bugs before G3.

### 5.2 On the laptop's real iGPU (optional, owner-run)

WSL has no vendor Vulkan driver: only lavapipe enumerates, `/dev/dri` does not exist **[verified 2026-10-29]**. So the
real-iGPU run is a **Windows-native** build (MinGW, the Windows target `pipeline.link_flags` already describes) that loads
`vulkan-1.dll` and the AMD driver. `tools/gpu_laptop.ps1` (G3) builds the `test_ail_gpu*` programs for Windows, runs
them with `AIL_GPU=force`, and compares stdout/exit with the CPython outputs saved by the WSL run. It also runs the bit
tests of 5.1 on the device and reports which features the driver offers (`shaderFloat64`, `shaderInt64`, RTE,
DenormPreserve). Run by hand before each GPU stage is merged; not a CI gate.

### 5.3 Keeping CI time small

One extra job; feature programs batched; G1 emulation tests in shards are cheap C runs; no GPU module is added to
`par_check` beyond its own file; the bit tests use one binary per op family; lavapipe threads capped at 2 to match the
runner.

## 6. Staging

Each stage is one PR, CPython-compared as in section 5, and leaves programs without `--gpu` byte-identical.

| stage | content | done means | depends on |
| --- | --- | --- | --- |
| **G0** | this design note | merged into `integ` | - |
| **G1** | `# ail: gpu` marker (tokenize), eligibility proof, kernel IR, refusals by name; kernel lowered to a CPU *emulation* (C function with the flag and replay) | marked loops of 1.1 build and match CPython via emulation; each refusal has a test; no-marker C unchanged | typed path + IR core (stable typed loops, `parallel.py` proof) |
| **G2** | SPIR-V emitter for f64/int64 `+ - *`, comparisons, select, branches, bounds checks, overflow/denormal/NaN guards | every module passes `spirv-val`; bit tests of the ops on lavapipe equal the CPU | G1 |
| **G3** | Vulkan runtime: `dlopen` loader, device pick, buffer pool, dispatch, fence, CPU fallback, `AIL_GPU`/`AIL_GPU_TRACE`; CI `gpu` job; Windows laptop script | map kernels run on lavapipe in CI and match CPython; fallback without a loader matches; size within +40 KB; laptop run reported once | G2; FFI/modules work for the Windows target and `dlopen` in static builds |
| **G4** | errors through replay: IndexError, ZeroDivisionError, int overflow, `int(float)` range, `AIL_GPU_FAULT` | every replay path tested on lavapipe; first failing element matches CPython | G3 |
| **G5** | software correctly rounded f64 `/` and `sqrt` | bit tests (incl. halfway cases) equal the CPU on lavapipe and on the laptop | G2 |
| **G6** | reductions: int sum with prefix range check, int/float min/max with index ties, float sum as GPU map + CPU reduce | CPython-equal on the edge cases of 3.4 (`[MAX, 1, -1]`, `-0.0/0.0` ties, NaN positions) | G4 |
| **G7** | cost model constants measured on the laptop iGPU and lavapipe; `--gpu=auto` | measured table in this note; `auto` never slower than the CPU by more than the launch cost on the measured set, or the stage reports why it stops | G3..G6; tooling (bench harness) |
| **G8** (optional) | zero copy on UMA, residency between consecutive launches | measured gain, outputs unchanged | G7 |

G1 can start as soon as the IR core and typed path are stable, but the roadmap order holds: GPU work is scheduled after
release. G3 needs the Windows build of the FFI/modules stage for the laptop run. The ML and matrix-multiply stages
M1..M6 (section 8.6) follow G7. There is no CUDA stage (section 0).

### 6.1 G1 as built (2026-10-30)

Code: `python/pkg-v12/gpu.py` (marker, proof, kernel IR, C emulation), hooks in `pyfunc.py` / `pyc.py` / `ail_chatgpt.py`,
tests in `test_ail_gpu_g1.py`. Everything is off unless `compile --gpu` (or `AIL_GPU_BUILD=1`) is given: no marker, or no
switch, gives byte-identical C and binary (tested).

- **Shapes built.** `for i in range(a[, b]): ... out[i] = <expr>` (the store is the last statement; `out` is a local
  `list[float]`/`list[int]` sized before the loop) and `ys = [<expr> for x in xs]` / `for i in range(a[, b])` (one `for`, no
  `if`), also over the module-level numeric list constants. Body: locals, `if/elif/else`, an inner `for j in range(K)` with
  a loop-invariant bound, `+ - *` (int and float), `//` and `%` (int), comparisons (chained, int against float), `and`/`or`/
  `not`, conditional expressions, `abs`, two-argument `min`/`max` (the typed path takes only two; the kernel also takes three),
  `float()`, `int()`, `math.floor/ceil/trunc` (the surface layer writes them `int(x // 1)`; a float `// 1` is exactly
  floor and is built), `len(xs)`, reads `ys[j]` with any int index (negative normalised, bounds checked), and calls of
  top-level functions over annotated `int`/`float` with one `return` at the end (inlined, recursion refused).
- **The emulation** is one C function per kernel (`ail_gk<k>`), shared helpers in `gpu.RUNTIME`. It computes into a buffer,
  ORs into a flag word instead of raising (index 1, zero division 2, int64 overflow 4, denormal 8, NaN 16, range 32) and
  stops at the first flagged element. The glue commits the buffer on flag 0, otherwise runs the original loop (the C the
  build makes without the marker). The float guards of 3.2 are in the emulation too (a NaN operand or result, an operand or
  result below 2**-1000, a product whose exponents sum below -1000), so the G2 SPIR-V has a CPU twin to be tested against.
- **Run time.** `AIL_GPU=0` skips every kernel; `AIL_GPU_TRACE=1` prints one line per launch on stderr
  (`gpu: k0 n=4 device=emulation`, `gpu: k0 replay flags=0x4 (overflow )`, `gpu: k0 cpu (...)` when the glue did not launch:
  a range that does not fit the output list, a negative start, an output that shares memory with an input).
- **Refusals** (GPU.md 1.3), all `file:line:col: not in the subset: GPU loop: <why>; write instead: <hint>`, exit 3: a
  marker that is not on a loop or list-comprehension assignment, `while`, a step or a non-`range` iterator, `for ... else`,
  a body without the closing `out[i] = <expr>`, a call/print/append statement, `break`/`continue`/`return`/`try`/..., a
  second store, the output list read in the body, a value carried between iterations (`s += x`: G6), a local read after the
  loop, `/` and `math.sqrt` (G5), `**`, shifts, float `%` and `//`, libm calls, `round`, str/None constants, attributes,
  tuples, unknown calls, recursion, a callee without annotations or with several returns, mixed int/float branches,
  a local that changes type, a triangular inner loop, a GPU loop inside a GPU loop, comprehensions with `if` / two `for`s /
  another iterator, `sum(...)`; and, on the typed path, a function with `try`, a method, a name that is not an int/float
  scalar or a `list[int]`/`list[float]`.
- **The proof has two halves.** The syntactic half runs on the file as the user wrote it (`ail_chatgpt.py`, before the
  surface layer lowers anything) and again in `pyc.build` before either path is tried, so a refusal never depends on which
  path would have built the program. The typed half (which names are int/float scalars and lists) runs when the typed path
  has the function's C. A marked loop whose program is built on the general path is not offloaded (section 1.1) and the build
  says so: `note: prog.py:12: '# ail: gpu' ignored: the loop is not on the typed path ...`.
- **Integers.** The kernel is int64 with an overflow flag. Replay then gives whatever the same build gives without the
  marker: the typed path's loud `integer overflow` stop, or exact big ints where the function is built on the general path.
  A function that the default build keeps off the typed path because an int local or parameter is not provably int64 (the
  tagged-int lowering of BIGINT.md) is not a candidate, exactly as `parallel for` (the IR emitter does not know the
  region; the legacy emitter would use int64 where the unmarked build uses exact ints, a silent difference).

Deviations from the text above, all recorded in the PR: no cost model and no `N_MIN` note (G7; `AIL_GPU=force` is accepted
and means the same as unset); no `AIL_GPU_FAULT` (G4); no `--gpu=auto` (G7); float reductions, int `sum`/`min`/`max` and
`s += expr` are refused with a G6 hint instead of being built; `ThreadPoolExecutor.map` / `Pool.map` loops and
`array.array` storage are not built (the typed path has no `array` module; `typedpar` loops are lowered before the marker is
read); strided writes (`out[i * K + j]`) and conditional stores are not built; a comprehension over `zip()` is proven but the
typed path does not compile it, so such a program runs on the general path with the note; `float()` of a bool list and
bool-valued results are stored as 0/1 ints.

### 6.2 G2 as built (2026-10-30)

Code: `python/pkg-v12/gpu_spirv.py` (SPIR-V writer + kernel lowering), `python/pkg-v12/gpu_vk.py` (the C runtime and the
per-kernel wrapper), a few lines in `gpu.py` (`_glue` calls `ail_gk<k>_run` instead of `ail_gk<k>`, `PATHS`, `path_note`),
`pyc.py` / `ail_chatgpt.py` (the compile note), tests in `test_ail_gpu_g2.py`, a `gpu` job in `tests.yml`. G2 took the
runtime of G3 along (the task that built it asked for both): what G3 still has is the Windows laptop script, the +40 KB size
budget measurement, the cost model constants (G7) and a table of tested drivers.

- **What runs on the device.** Every kernel G1 builds: map kernels over `list[float]` / `list[int]` with locals, `if`, inner
  `for`, conditional expressions, short-circuit `and`/`or`, `+ - *` and unary minus/`abs` on binary64, `+ - * // %` on int64,
  comparisons (including int against float), `min`/`max`, `float()`, `int()`, `floor`/`ceil`/`trunc`, reads at computed
  indices, inlined functions. One invocation per element, 64 per workgroup, a 2-D grid when the count needs more than 65535
  groups. SPIR-V 1.4 for Vulkan 1.2; capabilities `Shader`, `Int64` and, for kernels that touch binary64, `Float64`,
  `RoundingModeRTE`, `SignedZeroInfNanPreserve`. Nothing else in G1's scope is left to the emulation: a kernel whose IR the
  writer does not know raises `Unsupported` and keeps the emulation only (the note says so).
- **No int32 yet.** The typed array module (`ail_array`, #225/#235) is not in this base, and the G1 kernels are int64 with the
  overflow flag. int64 overflow at any element is detected on the device (xor sign tests for `+ -`, division check for `*`,
  `-INT64_MIN`, `INT64_MIN // -1`), flagged, and replayed on the CPU, which then does what the CPU build does (the loud
  `integer overflow` stop, or exact big integers on the general path).
- **Floating point.** Every `FAdd`/`FSub`/`FMul` carries `NoContraction`; no `FPFastMathMode` decoration exists in any module;
  there is no `Fma`, `FDiv`, `FMin`, `FMax` (the tests parse every module and fail on any of them). The entry point has the
  execution modes `RoundingModeRTE 64` (which also rounds `OpConvertSToF`; the `FPRoundingMode` decoration is only legal on
  16-bit conversions) and `SignedZeroInfNanPreserve 64`. `DenormPreserve` is not requested: the guards of 3.2 (operand or
  result in 0 < |x| < 2**-1000, a product whose exponents sum below -1000, a sum that is 0 although the operands do not cancel)
  set the flag, so a device that flushes subnormals can never show a different bit. NaN: a NaN operand or a NaN made from
  numbers sets the flag, so the payload and sign of a NaN are never visible (the CPU replay makes the CPU's NaN).
  A device that does not report `shaderFloat64`, `shaderRoundingModeRTEFloat64` and `shaderSignedZeroInfNanPreserveFloat64`
  gets int64 kernels only; the binary64 kernels run as the emulation. **Finding:** lavapipe's compiler rewrote `0.0 - x` to
  `-x` although the subtraction carried `NoContraction` (wrong for x = +0.0), caught by the bit test. The emitter now builds the
  sign of an exact zero (add, sub, mul), `-x` and `abs(x)` from integer bit operations, and breaks `min`/`max` ties
  explicitly. The same class of bug can exist in another driver for a pattern the bit test does not contain; that is the
  risk of section 9 and the reason a device list is still a G3 item.
- **Fallbacks, in order**, each one printed by `AIL_GPU_TRACE=1` as `gpu: k0 device unavailable (<why>)`: `AIL_GPU=emu` or
  `AIL_GPU=0`; a launch below `AIL_GPU_MIN_N` (4096) unless `AIL_GPU=force`; no loader (`dlopen` fails); no Vulkan 1.2 device
  with a compute queue (`AIL_GPU_DEVICE=<name>` picks by name, otherwise discrete, integrated, virtual, CPU in that order);
  a missing feature (test hook `AIL_GPU_DISABLE=f64,i64,rte,szinp`); buffers larger than `maxStorageBufferRange`; any failed
  Vulkan call; a static build (`AIL_STATIC=1`: a static glibc segfaults in `dlopen`, so such a build always takes the CPU
  path); output that overlaps an input (G1's pointer check, before any launch). The result is committed only when the flag
  word is 0.
- **Compile note.** `note: prog.py:12: kernel k0: SPIR-V for binary64 + int64 (909 words, needs ...). At run time it runs on a
  Vulkan device that has those features ...; with no device ... the CPU emulation of the same kernel runs, with identical
  output. AIL_GPU=emu forces the CPU emulation, AIL_GPU=0 the original CPU loop.` A kernel without SPIR-V gets
  `kernel k0: no SPIR-V (<why>); the kernel runs as the CPU emulation only`.
- **Tests (lavapipe 1.4, Mesa/LLVM 20.1.2 on this laptop's WSL).** Bit tests (5.1): 51 kernels (every op, comparison,
  conversion, fused-multiply-add-shaped expression, min/max/ternary tie case) over 65,536 operand sets each (random bit
  patterns, +-0, +-inf, NaN, subnormals, the 2**-1000 boundary, neighbours for cancellation, int64 limits): 2,779,992 clean
  elements compared bit for bit between the emulation (one element per call) and the device (one launch), 0 differences; for
  the 562,344 elements the emulation flags, 17,200 single-element launches (the first 400 per kernel), all flagged on the
  device; in-place output over input equal. Whole programs: lengths 0, 1, 2, 63, 64, 65, 127..129, 255..257, 4095..4097,
  100003; a 4.3 million element launch (2-D grid); special floats; 21 error kinds at positions 0, 63, 64, 4999 (add/sub/mul
  overflow, `-INT64_MIN`, `abs`, floor division and modulo by zero, `INT64_MIN // -1`, index == len, -len, -len-1,
  `int(1e30)`, `int(inf)`, subnormal and NaN operands, inf + -inf, underflowing product, subnormal difference, floor of inf,
  inf * 0): the same binary under `AIL_GPU=0`, `emu`, `force` (device), no loader, a device without features, and CPython print
  the same stdout and exit code, and the device and the emulation make the same ran/replay decision for every launch. All
  modules pass `spirv-val --target-env vulkan1.2`; the declared Vulkan structs and constants are checked against `vulkan_core.h`
  (sizes, alignments, offsets). Aliasing of the output and an input cannot be written in the typed path (a `list`
  parameter is read-only, and `ys = xs` is refused by name), so it is tested at the C level (output over input, same index) and by
  G1's `gk_disjoint` unit tests. **Speed: unmeasured.** Nothing in G2 measures time; lavapipe is a CPU.

### 6.3 G3 (first part) as built: device trust, the 780M, and the first measurements (2026-10-30)

Code: `python/pkg-v12/gpu_vk.py` (self-test, first-launch comparison, test hook, host-cached result memory),
`test_ail_gpu_g3.py`; no change to `gpu.py`, `gpu_spirv.py` or the C of programs built without `--gpu`. G2 left the question
what to do about a driver whose shader compiler rewrites a pattern that the module forbids (lavapipe: `0.0 - x` to `-x`).
A list of known-good drivers would not cover the next driver; a check on the device itself does.

**The self-test (per kernel, at first use).** Before a process first trusts a device for a kernel `k`, `ail_gk<k>_selftest`
runs THAT kernel's own SPIR-V over 4096 operand sets and compares it with the C emulation of the same kernel:
- Operands: for the first 33 x 33 (28 x 28 for ints) elements the pair table of the edge values of the bit tests of 5.1
  (+-0, +-inf, NaN-free edge floats, 2**-1000 neighbours, subnormals, 2**53, 2**63, int64 limits, 3037000499/500), a
  different permutation per list so three-operand kernels see many triples; the rest are neighbours of the previous list's
  value (equal, negated, +-4 ulp, halved) and random bit patterns with tiny and 2**-1000 exponents. Fixed seeds: the same
  sets every run. The kernel's captured scalars are the real ones.
- Clean elements (the emulation does not flag them) must come back bit for bit. The device is launched once over all 4096 with
  `all` set (the results of a flagged launch are read too; the shader stores every element's result before it ORs the
  flag). A launch the emulation flags must flag on the device, and a launch the emulation accepts must not be flagged. One
  single-element launch per new flag bit the emulation raised (at most 6) must flag on the device, which checks the guards
  one element at a time (a missed denormal/NaN/overflow flag is the dangerous failure: a wrong value with flag 0).
- Kernels that also read an iterated list by computed index cannot be cut into single elements; they are compared on the
  whole launch (no kernel in the G1/G2 catalogue is of that kind).
- Trust classes: `binary64` kernels and `int64` kernels. A difference in a binary64 kernel marks binary64 untrusted for the
  process (every later binary64 kernel takes the CPU path), a difference in an int64 kernel marks int64 untrusted; a binary64
  kernel needs both classes. The per-device, per-process cache is the state in the runtime (one device per process,
  chosen by `AIL_GPU_DEVICE` or the rank rule); the trace names the device, `driverVersion` and `vendorID` it was judged on.
  **No disk cache**: the check is per kernel (the shader under test is the program's own), so a cache keyed by device,
  driver and AIL version would have to be keyed by kernel too; with 7 to 25 ms per kernel on the 780M it does not pay.
- **First launch.** The first real launch of each kernel is compared with the emulation on its first 4096 elements
  (elements run one at a time; a flagged emulation element requires a flagged device launch). `AIL_GPU_CHECK=all` repeats this
  for every launch; `AIL_GPU_CHECK=0` skips self-test and comparison and exists to measure their cost.
- **What happens on a difference.** One trace line (`gpu: k0 device <name> (driver 0x..., vendor 0x...) differs from the CPU
  emulation: result bits differ (element 1); untrusted for binary64 kernels, the CPU path runs`), the device answer is thrown
  away and the emulation's is used, and all later launches of the class run the CPU path (`gpu: k1 device unavailable (device
  untrusted ...)`). The program's stdout and exit code are the ones of `AIL_GPU=0` (tested).
- **Limits, stated plainly.** 4096 operand sets are a sample, not a proof: a driver that rewrites a pattern only for operand
  combinations that the sets miss, or only above some size, is not found. The first-launch comparison covers the program's
  own first 4096 elements, not the rest. What the check does remove is the class of failure found in G2 (a rewrite of a
  pattern for a few special operands, here +0.0) for every kernel on every device without a list. The test hook
  `AIL_GPU_INJECT=<flip|negzero|noflag>[:selftest|:launch]` simulates a bad driver; `RealBug` in `test_ail_gpu_g3.py` also
  removes the G2 workaround (`Gen.zero_sign`) from the emitter and shows that the self-test then finds the real lavapipe
  rewrite (skipped on a driver that does not have it).

**Cost of the check (measured, noisy).** One launch costs 3 to 5 ms fixed on the 780M with the Windows driver, so a
self-test with one 4096-element launch and 1 to 3 single launches takes 7 ms (warm, many kernels in one process) to 12 to 21
ms (the first kernel of a process), plus 0.1 to 0.2 ms to build the pipeline, which the first launch needs anyway; the
first-launch comparison adds up to about 5 ms (emulation of 4096 elements of the 320-op kernel below; 0.05 ms for a 5-op kernel).
Per-process cold start of the first device launch (instance, device, pipeline, self-test, comparison) was 100 to 300 ms with
or without the check; the medians of 6 runs per kernel were 161/156/198 ms with the check and 140/145/136 ms with `AIL_GPU_CHECK=0` (a difference of 11 to 62 ms, inside a spread of 100 to 300 ms). On lavapipe a warm self-test takes about 4 ms.

**Real hardware: AMD Radeon 780M (driver 0x00800156, vendor 0x1002) through `vulkan-1.dll` (Vulkan loader 1.4.304.0), built
natively on Windows with WinLibs gcc 16.1 (UCRT) found on the PATH; nothing was installed.** The runtime's `LoadLibraryA`
path worked unchanged (only `setenv` needed a one-line shim in the test harness; the generated program code does not use
it). The three bit-test harnesses of 5.1 (51 kernels x 65,536 operand sets, 2.78 million clean elements compared) ran on the device:

| group | kernels | clean elements compared bit for bit | flagged elements | single flagged launches checked | differences |
| --- | --- | --- | --- | --- | --- |
| float arithmetic | 18 | 931,789 | 247,859 | 7,200 | 0 |
| comparisons and conversions | 18 | 952,820 | 226,828 | 6,400 | 0 |
| int64 | 15 | 895,383 | 87,657 | 3,600 | 0 |

The self-test passed for every kernel on the 780M. **So no pattern was found where the 780M differs from the CPU emulation;**
that is a statement about these 51 kernels and these operand sets, and the Windows driver is one driver. The 780M reports
`shaderFloat64`, `shaderInt64`, round-to-nearest-even and signed-zero/inf/NaN preservation for binary64 (otherwise the float
kernels would not have run).

**Measurements (this laptop with the Radeon 780M, Windows 11, "balanced" power plan, on mains power; noise: run
to run spread of 10 to 70 percent, 3 runs per cell; nothing else was stopped).** Host buffers, one device launch includes
creating the buffers, copying the inputs in, the dispatch, the fence wait and copying the result out. CPU loop = the
plain C loop gcc -O2 -ffp-contract=off makes of the Python loop (single thread), `emu` = the G1 emulation (what runs today
when the device is not used), device = the median of 7 launches after the first. Times in ms; median of the three process
runs for the device column, `cpu` and `emu` are medians of 5 and 3 in-process repeats of the middle run.

| kernel | n | CPU loop | emulation | device (steady) | device vs CPU loop |
| --- | --- | --- | --- | --- | --- |
| light f64: `(x+y)*(x-y)+x*0.1` (5 ops) | 4,096 | 0.002 | 0.05 | 4.6 | ~2000x slower |
| | 65,536 | 0.05 | 0.97 | 5.3 | 100x slower |
| | 1,000,000 | 1.0 | 16 | 16 (10 to 17) | 10 to 16x slower |
| | 10,000,000 | 10.8 | 176 | 58 (56 to 63) | 5x slower |
| heavy f64: 64-step recurrence (~320 ops) | 4,096 | 0.3 | 2.3 to 4.6 | 3.6 (3.0 to 4.0) | 12x slower |
| | 65,536 | 5.2 | 49.6 | 4.9 (4.7 to 5.2) | 1.06x faster (tie) |
| | 1,000,000 | 74.5 | 758 | 27.9 (25 to 28) | 2.7x faster |
| | 10,000,000 | 961 (733 to 1010) | 12,756 | 152 (143 to 188) | 6x faster |
| int64: `(x+y)//3 + x*y - z` (3 lists, ~8 ops) | 4,096 | 0.008 | 0.01 | 5.1 | 600x slower |
| | 65,536 | 0.12 | 0.12 | 6.2 | 50x slower |
| | 1,000,000 | 2.3 | 3.0 | 19 (16 to 21) | 8x slower |
| | 10,000,000 | 22.5 | 27.2 | 92 (76 to 97) | 4x slower |

Cold start of the first device launch of a process (instance + device + pipeline + self-test + comparison): 125 to 270 ms
in these runs.

What the numbers say, and no more than that:
- A fixed cost of about 4 to 5 ms per launch on this driver puts the break-even beyond 4,096 elements for every kernel
  measured; the placeholder `AIL_GPU_MIN_N = 4096` sends launches to a device that is 12x to 2000x slower for them.
- The device wins only where the arithmetic per element is large (here the 64-step loop): about a tie at 65,536 elements and
  2.7x to 6x faster at 1M to 10M. For the light and the int64 kernels it loses at every size up to 10M, 4x to 16x at
  1M and 10M. They are bound by moving 16 to 24 bytes per element through new buffers (about 5 ns per element in these runs).
- These are binary64 and int64 kernels on an integrated GPU; the speed of other kernels, other drivers and discrete GPUs is
  not measured here.
- **Memory type matters more than the shader.** The first measurement used write-combined memory for the result buffer
  (the first host-visible, coherent type): reading the result back was the dominant cost (light kernel 10M: 446 ms, heavy
  1M: 74 ms, heavy 10M: 587 ms). The result buffer now asks for host-visible, coherent, cached memory first (falling back
  to the old type), which gave the table above (58, 28 and 152 ms). The results are unchanged (the same bits, the bit tests
  repeated on the final code).
- **The CPU path today is the emulation, not the plain loop.** When the device is not used (below `AIL_GPU_MIN_N`, no
  device, untrusted device), `ail_gk<k>_run` runs the G1 emulation, which carries a check per operation: 1.2x (the int64 kernel) to 16x (the light f64 kernel) slower than the plain loop in the table above (light 176 vs 10.8 ms, heavy 12,756 vs 961 ms, int64 27 vs 22.5 ms at 10M). It is exact, and it is what makes
  the fallback bit-identical without a replay, but a program that falls back pays for it. (`AIL_GPU=0` runs the plain loop.)

**Where this leaves the cost model (the G7 placeholder).** Not changed in this stage; the numbers above support a model but
only from three kernels on one device, and applying one needs the fallback to be the plain loop. A fit from this table:
`t_device = 4.5 ms + n * (5 ns + ops * 0.07 ns)` and `t_cpu = n * ops * 0.25 ns`, with `ops` the number of IR operations of the
kernel body (loops multiplied by their trip count when it is a constant), gives "never for ops below about 28; for 320 ops
from about 100,000 elements", which matches all twelve cells. Next steps, in order: (1) let the wrapper return "declined" so the
glue runs the original loop instead of the emulation when the device is not wanted; (2) count `ops` in the emitter and add
`AIL_GPU=auto` with the model above and a safety factor, constants in one table; (3) reuse buffers between launches and map
host memory instead of copying on a unified-memory device (the 5 ns per element is mostly copying and page-faulting fresh
80 to 240 MB allocations: G8); (4) re-fit on the Colab NVIDIA GPU and a second AMD/Intel device before the model is the default.

#### Tesla T4 (Colab, NVIDIA 580.82.07, Vulkan 1.4.312), 2026-10-30: `OpSRem` on 64-bit is wrong

The first run on a real NVIDIA device matched every binary64 kernel bit for bit and every int64 kernel except those with `//` or
`%`. The device answers `-1 // 2` with 0 (Python: -1), `3 // -3` with -2 (-1), `3 % -2` with 1 (-1), and for a large positive dividend
and divisor -22 a remainder that is nearly the dividend. The SPIR-V was valid and lavapipe agreed with the emulation; the self-test
(6.3) caught the difference on its first operand with a negative dividend, marked the int64 class untrusted, and the programs kept
printing what CPython prints on the CPU path. Only kernels using `OpSRem` (and `OpLogicalNotEqual`, which was never shown guilty)
failed; `OpSDiv`, `OpSNegate`, the multiply overflow check and all comparisons passed. Replacing `OpSRem` by `a - OpSDiv(a, d) * d` and
the sign test by `(r ^ b) < 0` made every such kernel match on the T4 (variants tried: no `OpSRem`; plus no `OpLogicalNotEqual`; plus
unsigned divide of the magnitudes: all three matched). `gpu_spirv` now emits no `OpSRem` at all (test `Spirv.test_no_op_srem`).

A harness lesson from the same run: a kernel whose self-test fails makes the whole class untrusted, so every later launch in the process
returns `GK_DECLINED`. `BitTests` first counted those as "spurious flags" (also on min/max/lt/eq, which cannot flag); it now resets the
trust state per kernel and prints the distrust message of a declined launch.

### 6.4 G4 as built: a declined launch runs the original loop, the cost model, and a cheaper launch (2026-10-30)

Code: `python/pkg-v12/gpu.py` (`ops_expr`, the glue), `python/pkg-v12/gpu_vk.py` (the decision, the model, the buffer pool),
`test_ail_gpu_g4.py` (22 tests), small changes to the G1 to G3 tests. Without `--gpu` nothing changes.

**1. The declined path.** `ail_gk<k>_run` has a third answer, `GK_DECLINED` (a value no flag word can have). The glue first calls
`ail_gk<k>_want(...)` (before it allocates or reserves anything), and on a no, or on `GK_DECLINED` from the run, executes the ORIGINAL
typed loop. The G1 emulation now runs only for `AIL_GPU=emu`, inside the self-test and in the first-launch comparison. A device
launch that flags is still replayed by the original loop. Declined because: the model said no, below `AIL_GPU_MIN_N`, no loader
or device, a missing feature, an untrusted class, a failed Vulkan call, a failed first-launch comparison, a static build. The
result is no longer copied through a temporary: the wrapper hands the device the output list itself and the device copies into it
only when the flag word is 0 (a flagged launch leaves the list untouched, so the replay starts from the same state as before);
only a launch that is being compared with the emulation, and `AIL_GPU=emu`, use a temporary. Trace lines: `gpu: k0 declined (...)`
with the model's two predictions, `gpu: k0 original loop`; a launch that ran prints `gpu: k0 n=... device=<name>` as before, and
`device=emulation` now appears only for `AIL_GPU=emu`.

**2. The decision (`AIL_GPU=auto`, the default of a `--gpu` build).** Per kernel the emitter counts `ops` per element
(`ops_expr`: a C expression over the captured scalars and list lengths; arithmetic, comparisons, loads, conversions and
min/max count 1, a branch counts its dearer side, an inner loop its trip count times its body, a bound it cannot read counts 1,
which under-counts and so declines more; the 780M kernels give 6, 321 and 6). At run time, before anything is allocated:

```
t_cpu = n * ops * 0.20 ns
t_dev = 0.3 ms + bytes * 0.17 ns + n * ops * 0.06 ns          bytes = 8 * (n + sum of the input list lengths)
launch only if  t_cpu >= 1.5 * t_dev                          (margin 1.5)
         and the device is not a software device (Vulkan type CPU or virtual)
         and the cold start has been earned back (below)
```

The constants are the fit of the 780M measurements of this stage (the buffer pool of item 3 moved the fixed cost from 4.5 ms to
0.3 ms and the copy from 0.21 to 0.17 ns per byte, so the G3 constants were re-fitted; the fit is in one table in the runtime,
`AIL_GPU_MODEL=fixed_us,ns_per_byte,ns_per_op_dev,ns_per_op_cpu,margin,init_us` overrides it). **Cold start.** The first device
launch of a process also pays instance, device, pipeline and self-test (120 to 370 ms measured; one outlier of 720 ms), so a
launch the model likes is still declined until the sum of what the declined launches would have saved reaches `init_us`
(300 ms): ski rental. A program that launches a kernel only a few times therefore pays nothing; a program that crosses the line
pays at most about one cold start once, and gets it back after about six more launches of the kind that crossed it (measured
below: 1M heavy, 8 launches: 1.1 to 1.2 times the plain loop's total; 40 launches: 0.35 to 0.40). `AIL_GPU_STRICT=1` removes even
that: only a single launch that saves more than the cold start goes to the device (the heavy kernel from about 7M elements).
`AIL_GPU_MIN_N=<n>` still overrides the model with the old size rule; `AIL_GPU=force` ignores it; `AIL_GPU=0` never launches.
No per-device calibration at the first self-test: the self-test's launches are a cold device's, they would not measure the
steady 0.3 ms, and a second device or driver has not been seen. The constants are the 780M's; a discrete GPU or another driver can
differ (the margin 1.5 and the software-device rule are what protect it), and re-fitting on the Colab NVIDIA GPU and a second
AMD/Intel device is still open.

**Auto against `AIL_GPU=0` on the 780M** (Windows driver, mains power, WinLibs gcc 16.1 `-O2 -ffp-contract=off`; the glue of
`gpu.py` copied into a bench, one process per cell, 8 launches in a row, plain loop timed before and after the launches and
averaged; 3 process runs per cell; "total" is the 8 launches including the cold start; a ratio below 1 means auto is faster).
Cells where auto declined run the same machine code as the plain loop; their ratios are timer noise (the loop takes 3 us to 0.1 ms
there), spread 0.9 to 1.1 except the smallest cells (3 to 10 us per launch, where one timer tick is 10 to 30 percent):

| kernel | n | plain loop, ms | auto, steady ms | auto total / plain total, 8 launches (3 runs) | what auto did |
| --- | --- | --- | --- | --- | --- |
| light f64 (6 ops) | 4,096 to 262,144 | 0.003 to 0.19 | same | 0.91 to 2.0 (noise: 3 to 190 us per launch) | declined, original loop |
| | 1,000,000 | 0.79 | 0.88 | 0.97 to 1.31 (noise) | declined |
| | 10,000,000 | 9.8 | 10.1 | 0.91 to 1.04 | declined |
| int64 (6 ops, 3 lists) | 4,096 to 10,000,000 | 0.008 to 19.9 | same | 0.93 to 1.16 (1.3 to 1.5 at 4,096: 8 us) | declined |
| heavy f64 (321 ops) | 4,096 to 262,144 | 0.28 to 19.5 | same | 0.94 to 1.06 | declined (cold start not yet earned) |
| | 1,000,000 | 70 | 75 | **1.12 to 1.21** | cold start paid at launch 8 |
| | 10,000,000 | 975 | 170 | 0.18 to 0.24 | device from launch 1 |
| heavy f64, 40 launches | 262,144 | 16.0 | 15.5 | 0.93 to 0.94 | device from launch about 28 |
| | 1,000,000 | 93 | 18.4 | 0.35 to 0.40 | device from launch 8 |

So the one place where auto is slower than `AIL_GPU=0` is a program that launches a 1M-element 321-op kernel about 8 to 12 times
and then stops: it loses about 0.1 s once (one cold start less the savings so far). That is the ski-rental bound, and it is the
price of ever using the device for repeated launches; `AIL_GPU_STRICT=1` buys it back. Every other measured cell is a tie or a win.
Light and int64 kernels never go to the device (their copy costs 3 to 4 ns per element, more than the plain loop's work).

**3. Transfer cost: a buffer pool.** The device buffers (parameters, flag word, result, one per input list) are kept between
launches and reused when big enough (the memory stays mapped; up to `AIL_GPU_KEEP_MB`, default 512, are kept; a failure
releases all). The 4.5 ms per launch were mostly allocating, binding and mapping seven small and large buffers on the
Windows driver and faulting in their pages, not the dispatch. Forced device launches (`AIL_GPU=force`, same bench, 3 runs, medians
of the 7 launches after the first; min to max in brackets), before and after, plain loop for scale:

| kernel | n | plain loop | device before | device after | after / before |
| --- | --- | --- | --- | --- | --- |
| light f64 | 4,096 | 0.004 | 4.78 (4.45 to 22.7) | 0.285 (0.18 to 0.32) | 0.06 |
| | 65,536 | 0.056 | 5.75 (5.64 to 6.14) | 0.513 (0.51 to 0.53) | 0.09 |
| | 1,000,000 | 0.93 | 18.5 (14.0 to 20.4) | 3.95 (3.73 to 4.29) | 0.21 |
| | 10,000,000 | 10.5 | 77.4 (71.0 to 83.4) | 33.2 (31.1 to 37.2) | 0.43 |
| heavy f64 | 4,096 | 0.40 | 3.91 (3.08 to 4.47) | 0.323 (0.318 to 0.451) | 0.08 |
| | 65,536 | 6.05 | 6.19 (5.36 to 6.24) | 1.61 (1.53 to 1.68) | 0.26 |
| | 1,000,000 | 86.3 | 28.6 (28.4 to 29.8) | 19.8 (15.5 to 20.3) | 0.69 |
| | 10,000,000 | 1006 | 189 (183 to 204) | 155 (142 to 167) | 0.82 |
| int64 | 4,096 | 0.009 | 5.93 (4.63 to 6.30) | 0.181 (0.145 to 0.307) | 0.03 |
| | 65,536 | 0.162 | 6.41 (5.13 to 6.86) | 0.503 (0.503 to 0.513) | 0.08 |
| | 1,000,000 | 2.16 | 24.2 (22.6 to 24.8) | 4.08 (3.94 to 4.48) | 0.17 |
| | 10,000,000 | 24.2 | 97.8 (93.2 to 100) | 42.5 (34.5 to 45.3) | 0.43 |

The fixed cost is now 0.2 to 0.3 ms; the copy of the inputs into mapped memory is what is left (the light kernel at 10M: 33 ms for
240 MB). That moves the break-even for the heavy kernel from about 100,000 elements (G3) to below 15,000 (4,096 elements: 1.2 times
faster, 65,536 elements: 3.7 times faster than the plain loop, was a tie; the model's own threshold with the margin is about 15,000), and the light and int64 kernels stay on the CPU at every size. **Not done:** importing the
list's own memory (`VK_EXT_external_memory_host`, needs 4096-aligned host pointers that the lists do not have) or a host-visible
device-local heap, which would remove the input copy on the APU; the memory types of the 780M were not investigated beyond host-cached
for the result. Unchanged inputs are not detected (comparing costs as much as copying).

**Tests (lavapipe, no device in CI beyond it).** `test_ail_gpu_g4.py`: the ops counter against the kernels of the G3 fit (6, 321,
6; scalar and length bounds; an unreadable bound counts 1; a branch counts its dearer side); the model on the G3 cells (light and
int64 never, heavy from 65,536, the margin in the rule, the cold-start credit and `AIL_GPU_STRICT`); at C level that a declined
launch calls the emulation zero times (an `emu_calls` counter inside the kernel) and `AIL_GPU=emu` once; whole programs (the G2
program, 9 scenarios including replays at positions 0, 63, 64, 4999) in 12 modes (off, emu, force, auto declined by the model, auto
on the device, auto with a flagged launch, `MIN_N`, no loader, no features, an untrusted device found by the self-test and by the first
launch) with the same stdout, exit code and stderr as `AIL_GPU=0` and CPython, no `device=emulation` line outside `emu`/`force`/`MIN_N`,
and `original loop` for every declined launch; a lavapipe is never used by auto (software device); a pool program with growing,
shrinking and repeated sizes in six modes. The 780M bit tests (51 kernels x 65,536 operand sets) were repeated on the final code:
2,779,992 clean elements, 562,344 flagged, 17,200 single launches, 0 differences, 0 missed flags.

### 6.5 G5 as built: typed arrays (`ail_array`) on the device (2026-10-30)

Code: `python/pkg-v12/ailarray.py` (class `Fuser`: the rewrite of a `--gpu` build), `prelude_ailarray.py` (the block kernels of `ta.sum` /
`ta.dot`, `_ail_ta_c32`, `_ail_ta_cn`), `gpu.py` (internal markers, the IR node `c32`), `gpu_spirv.py` (`x_c32`), `gpu_vk.py` (self-test
and first-launch shape of the block kernels), `test_ail_gpu_g5.py`, `array_g5_cases/`. Base: G4 plus T1/T2 (#225/#235). Without `--gpu`
the lowering of `ailarray.py` is T2's, text for text (tested); with it the loops below carry a marker that is a NAME, not a comment,
because the surface passes unparse the program several times and a comment does not survive that.

**What goes to the device** (everything else in `ail_array` runs T2's code):

| op | kernel | notes |
| --- | --- | --- |
| f64 `+ - *` and unary minus, between arrays and with a scalar | one generated function per expression SHAPE, one loop | fused, see the rule below |
| `ta.sum(a)` of f64 | `_ail_taf_gk_sum`: one invocation per whole block of 1024 elements | 16 lanes x 64 adds in index order, then the 8-4-2-1 tree; the short last block and the tree over the blocks run on the CPU: the order of TYPED_ARRAY.md 3.5 on every device |
| `ta.dot(a, b)` of f64 | `_ail_taf_gk_dot`, the same with `d[q] * e[q]`; **opt-in** (`AIL_GPU_ARRAY_SLOW=1`) | same bits as the CPU for f64 (the products are rounded, then added) |
| int32 `+ - *`, array with array or scalar | `_ail_tai_k*`: one kernel per operation, **opt-in** (`AIL_GPU_ARRAY_SLOW=1` at build time, like the `ta.dot` kernel) | the int32 range is checked in the kernel (new IR node `c32`: the overflow flag when the value is outside int32); the flagged launch is replayed by the CPU loop, which raises T2's `OverflowError` with the operation and the lowest index |
| f64 `/`, `abs`, `sqrt`, `exp`, `minimum`, ..., int32 `// %`, `astype`, in-place `+=`, slices, min/max | not on the device | no correctly rounded device division (G5 of the plan), or the output overlaps an input (G1's pointer check declines it) |

**The fusion rule.** After T2's lowering has turned `a * b + a` into nested `_ail_taf_bin` calls, a tree of f64 `+ - *` / unary minus whose
leaves are plain names, constants or attribute chains (scalar operands: also `float(x)`, `-x`, `x * y`, `x + y`, `x - y` of those), at most 256
operations, becomes ONE call of `_ail_taf_fu<N>`: the shape checks in the order the unfused code made them (same text), then a loop
`o = [_ail_ta_cn(<expr>, inf) for _ailg_map in range(n)]`. Arithmetic is unchanged: the same binary64 operations in the same order, no
fused multiply-add (`-ffp-contract=off`, `NoContraction` in the module), and a NaN is made canonical once, at the end, which is the same bits as after every
operation (an operation with a NaN operand gives a NaN). A tree with an operand that is a call, a subscript or a division is not fused as a
whole (evaluating all operands first could change which error comes first): each single operation is still rewritten (its two operands are
evaluated where they stood), so `g(a) * b + g(b) * a` is three single-operation kernels, two of which share a function. Trees of the same shape
(leaves and scalars numbered by first use) share one function and one kernel. int32 chains are not fused: the `OverflowError` of `a + b * a`
names the multiplication over the whole array first, and a per-element chain would name the first failing element of either operation.

**Decision and cost.** `ops_expr` counts the new kernels like the old ones (a load, an operation, a comparison: 1 each; the inner loop of a block
kernel: 64 x its body, about 3.2 per element for `ta.sum`). The constants of 6.4 are unchanged. Consequences, from the model and then measured below:
a chain pays for its copy only when it is long (about 40 operations with one input array, about 60 with two); `ta.sum`, `ta.dot` and int32 never do.
Two things were found on the way and are in the code: (1) the function that holds a marked loop is emitted by the legacy emitter, which fills
`[0] * n` one element at a time and checks every element access, so the kernel loops are written as comprehensions (no fill, one reserve) and the
whole-block loops of `ta.sum` / `ta.dot` use eight accumulators per pass, two passes (16 accumulators and the loaded values spill out of registers);
(2) even so the int32 loop is 1.6 to 1.8x and the `ta.dot` loop 10 to 29 percent slower on the CPU than T2's, which is why those two are opt-in (`AIL_GPU_ARRAY_SLOW=1` at build time):
`--gpu` must not make programs slower, and the model never uses them on this device.

**Bit tests.** `array_g5_cases/sumdot.py`, `fused.py`, `int32.py` (each built with `compile --gpu`, typed path only, run in every mode, stdout and
exit code compared with CPython running the T1 reference `ail_array.py` on the same text):
- `sumdot.py`: 9 data kinds (ramp of 0.1, 1e16 / 1 / -1e16, random, 1/k, all -0.0, +-1e308, 1e-300 scale, 1 + eps, wide) x lengths
  0, 1, 2, 15, 16, 17, 31, 32, 33, 1023, 1024, 1025, 1536, 2047, 2048, 2049, 3071, 3072, 3073, 4097, 5000, 20000, 100003; inf, NaN, -inf (cancelling
  across blocks), -0.0, 1e308 x2, 1e-310 and +-1e308 planted at positions 0, 1, 15, 16, 17, 1023, 1024, 1025, 2047, 2048, 2049 of a 2100-element array
  (two whole blocks and a short third); all -0.0 / all 0.0 / mixes at 1, 16, 1024, 1040, 2048, 2049; a 70000-element array with a NaN at the end and one
  whose infinities meet in the tree. Printed: the bits of `ta.sum` and `ta.dot` (hex) and their reprs.
- `fused.py`: 11 chains (`a*b + a`, `(a+b)*(a-b) - c*0.5`, `2.0 - a*b`, `-(a*b) + c`, `a*3 + 1`, `s*a - b*s + c`, each single operation, `-a`, and a
  depth-5 chain) on 5 data kinds (including 1e290 and 1e-150 scales, where products overflow and underflow) at lengths 0, 1, 2, 63, 64, 65, 127..129,
  255..257, 4095..4097, 100003; 12 special values (inf, -inf, NaN, -0.0, 0.0, 1e308, -1e308, 1e-310, 5e-324, 2**-1000, 1.5 * 2**-1000, 2**53 + 1) planted
  in the three operands and the scalar at 5 positions of 65- and 4097-element arrays; shape errors; NaN / inf / int scalars. Printed: a hash of every bit
  of every result (n <= 4100) or the bits of ends, middle, `ta.sum` and `ta.dot` of the result.
- `int32.py`: add / sub / mul, with a scalar on either side and a scalar outside int32, at the same lengths for ranges that fit, near +-2**31 and with
  overflow at positions 0, 1, 63, 64 and n - 1 (the message names the operation and the lowest failing index), shape error, chains where the multiplication fails first.

**Real hardware: AMD Radeon 780M, Windows driver 0x00800156, WinLibs gcc 16.1, `-O2 -ffp-contract=off`, the `program.c` of a `compile --gpu --debug-dir` build in WSL
compiled natively on Windows (the whole program, not a harness).** The three case programs print byte for byte what CPython with the T1 reference prints
in `AIL_GPU=0`, `emu`, `force` (229 / 1,448 / 335 device launches for `int32` / `fused` / `sumdot`), auto with a model that says yes (the same counts),
auto as shipped (0 launches: declined), no loader, and an untrusted device (`flip:selftest`). Every new kernel passed its self-test on the 780M
(`selftest ok device=AMD Radeon 780M Graphics`; e.g. the sum kernel: 43 clean blocks compared bit for bit, 21 flagged, 2 single launches). On lavapipe (LLVM 20.1.2): the same programs in `0`, `emu`, `force` and auto, the same stdout and exit code (1,431 / 220 / 333 emulation launches and 1,448 / 229 / 335 device launches).

**Measurements on the 780M** (Windows 11, mains power, the machine shared with other work: run-to-run spread 5 to 60 percent, so each cell is the median of 3 process
runs of the median of 6 to 14 repeats, min..max of those three medians in brackets; the repeats of one process allocate a new result each time, as a program does).
"T2 CPU" = the same program built WITHOUT `--gpu` (T2's code, one pass per operation); "off" = `--gpu` build, `AIL_GPU=0` (the fused loop); "auto" = the shipped default;
"force" = `AIL_GPU=force`. Times in ms. Chains are Horner's rule in one array `x` with scalar coefficients, so `cN` has N multiplications and N additions
(`c1` is `a * b + a` with two arrays). The cold start of the first device launch (instance, device, shader, self-test) is 150 to 630 ms per process on this laptop and is in the `first` repeat only.

| op | n | T2 CPU | off (fused CPU) | auto | force (device) | what auto did |
| --- | --- | --- | --- | --- | --- | --- |
| `a*b + a` (3 ops) | 1M | 12.2 [11.1..12.6] | 8.8 [7.5..9.3] | 8.8 | 5.8 [5.6..7.6] | declined |
| | 10M | 104 [94..123] | 94 [74..171] | 87 | 59 [57..70] | declined |
| Horner 4 (8 ops) | 1M | 47.8 [46..51] | 5.4 [5.0..6.3] | 5.3 | 5.1 [4.9..5.2] | declined |
| | 10M | 486 [452..584] | 45.5 [44.5..48.9] | 46.1 | 37.6 [35.9..66] | declined |
| Horner 16 (32 ops) | 1M | 128 [122..135] | 15.3 [15.0..30] | 13.6 | 6.8 [6.3..7.2] | declined |
| | 4M | 613 [573..644] | 44.6 [44.6..48.8] | 45.5 | 23.6 [23.0..31] | declined |
| | 10M | 1,509 [1,290..1,699] | 96.9 [95..99] | 113 | 55.8 [53.8..58.1] | declined |
| Horner 32 (64 ops) | 1M | 256 [229..271] | 34.7 [30..57] | 29.1 | 11.7 [11.4..11.8] | declined |
| | 4M | 1,250 [1,136..1,471] | 128 [127..130] | 118 | 45.2 [43.7..55.7] | declined |
| | 10M | 3,695 [3,385..4,042] | 298 [284..303] | 108 | 109 [104..109] | device |
| Horner 64 (128 ops) | 1M | 721 [557..781] | 88.2 [82..89] | 81.8 | 34.4 [29..37] | declined |
| | 4M | 2,903 [2,579..3,547] | 326 [323..341] | 130 | 135 [131..141] | device |
| | 10M | 16,036 [15,685..16,237] | 770 [761..782] | 276 | 263 [262..283] | device |
| `ta.sum` | 1M | 0.47 | 0.79 [0.41..0.87] | 0.44 | 1.20 | declined |
| | 10M | 6.7 [5.5..7.2] | 5.4 [5.4..5.7] | 5.1 | 8.4 [8.3..8.9] | declined |
| `ta.dot` (opt-in kernel) | 1M | 0.76 [0.59..0.93] | 0.98 [0.95..2.7] | 0.79 | 2.3 | declined |
| | 10M | 7.4 [6.3..7.6] | 8.2 [7.7..9.7] | 9.2 | 23.7 [22.9..24.4] | declined |
| int32 `a + b` (opt-in kernel) | 1M | 2.6 | 4.4 [4.2..4.6] | 4.5 | 4.4 | declined |
| | 10M | 28.6 [28.0..30.0] | 52.7 [43.6..66.6] | 42.4 | 44.1 | declined |

An earlier sweep of the same programs on a quieter machine (older loop shape, 3 runs): `a*b + a` at 1M: T2 6.0, off 5.0, auto 5.4, force 5.5; at 10M: 59.5 / 50.4 / 54.8 / 50.6, a tie
within the spread. Horner 64 at 10M: T2 11,790, off 889, auto 312, force 329. The ordering of the table is the same in both sweeps.

What the numbers say, and no more than that:
- **Fusion is the big win and it needs no device.** The fused loop (`off`) is 1.1x (3 ops) to 21x (128 ops) faster than T2's one-pass-per-operation code, because T2 allocates and
  fills an array per operation. It is what runs when the device is declined, so a `--gpu` build is faster than a plain build for every chain.
- **The device wins for long chains and only for them.** Against the fused CPU loop: 3 ops a tie (1.0 to 1.5x faster, inside the spread of this machine); 8 ops about 1.0 to 1.2x; 32 ops 1.7 to 2.2x
  (1M to 10M); 64 ops 2.7 to 3.0x; 128 ops 2.6 to 2.9x. The copy of the inputs and the result (16 bytes per element for one input array) is what a short chain cannot pay for.
- **auto is conservative.** It picked the device where the device was at least as good (Horner 32 at 10M, Horner 64 at 4M and 10M: 2.7x, 2.5x and 2.8x faster than `off`) and never ran slower than `off` beyond the spread,
  but it left a 1.7x to 3x on the table for the 32- to 128-op chains at 1M to 4M and for Horner 16 (the model needs about 40 operations per input array and the ski-rental cold start): the constants of 6.4 were not re-fitted here.
- **`ta.sum` and `ta.dot` never win on this device.** They are bound by memory on the CPU (0.4 to 0.7 ns per element) and the device has to copy 8 to 16 bytes per element first: 1.5x to 3x slower forced.
  The block kernel's CPU loop is as fast as T2's or faster for `ta.sum` (equal within the spread on Windows, 1.7x faster in WSL) and 10 to 29 percent SLOWER for `ta.dot`, which is why the `ta.dot` kernel is opt-in.
- **int32 never wins** (1.6x to 1.7x slower forced than the CPU) and its CPU loop is 1.6 to 1.8x slower than T2's (the function that holds a marked loop is emitted by the legacy emitter), so its kernels are opt-in too.
- The 3 to 5 percent differences between modes where auto declined are noise (the same machine code runs).

**Tests.** `test_ail_gpu_g5.py` (19 tests, `gpu` CI job and `GPU_JOB` of `tools/ci_shards.py`): the text of the lowering (nothing added without the switch; one function and one loop for a chain; same
shape shares a function; division not fused; calls among the operands not reordered; int32 and dot opt-in), the lowered text run by CPython equals the reference on the three case programs, the IR node
`c32` in SPIR-V and C, the sum kernel as a range kernel, the three case programs built with `compile --gpu` on the typed path (kernels present) and run in `AIL_GPU=0`, default, a model that says no, `emu`, `force`, auto on a
device, no loader, auto without loader, a device without features, an untrusted device found by the self-test, one found by the first launch; the self-test of every new kernel passes on the device;
a corrupted device (`flip`, `negzero`, `noflag` in the self-test) is found for every kernel of every program; a Horner chain of 40 steps in all modes and sent to the device by a model that says yes.
G1 (42), G2 (25), G3 (16), G4 (22), T2 (23) and the T1 reference (38) re-run on the merged tree.

**Not done / open.** The cost model constants are G4's; a re-fit with the chains of this stage (the model is conservative for 16 to 64 operations) would move the break-even for chains from about 40 to about 15 operations per input array.
Reductions run one invocation per block of 1024 elements (uncoalesced; a lane-parallel kernel with a workgroup tree would read 16 consecutive elements per step) because the kernel IR has no workgroup-local memory yet;
it does not matter for the decision on this device (the copy dominates) but it would on a discrete GPU. `ta.min`/`ta.max`/`argmin`, `astype`, f32/f16 and f64 division/`sqrt` (correctly rounded device division, stage G5 of the plan) are not on the device.


## 7. Colab validation (owner-started, manual)

The owner has a paid Google Colab subscription with NVIDIA GPUs (T4/L4/A100 class, CUDA). It is useful as a second real
device, with three limits that keep it out of CI: every run spends paid compute units, there is no stable automation
API, and the runtime image changes without notice. **CI never depends on Colab; a Colab run is started by the owner.**

It does not change the backend: Colab is the NVIDIA device for the **same Vulkan/SPIR-V** code, and the place where
PyTorch + CUDA is run as the baseline of B0 (section 0).
- Colab runs the Vulkan backend only if the container exposes the NVIDIA Vulkan driver (`nvidia_icd.json` and
  `libGLX_nvidia`); whether Colab mounts the graphics part of the driver or only compute/utility is **[unverified]**. The
  notebook checks it first. If it is there, Colab is a third device for the same SPIR-V (NVIDIA's f64, RTE and
  DenormPreserve support **[unverified per driver]**).
- If Colab has no NVIDIA Vulkan driver, B0's NVIDIA half cannot run there; AIL does not add CUDA to work around it
  (section 0). Decided (D3, 2026-10-29): B0 then runs on the AMD 780M only, and its NVIDIA half waits for an NVIDIA
  machine with a Vulkan driver; no new spending.

Notebook outline (`tools/colab/gpu_check.ipynb`, written in G3):
1. Show the runtime: `nvidia-smi`, `cat /etc/os-release`, `python3 --version`; stop with a clear message if no GPU.
2. Install build deps: `apt-get install -y gcc libvulkan1` (and `vulkan-tools` for `vulkaninfo`); install CPython 3.12
   if the image's Python is another version (the oracle must be 3.12).
3. Probe Vulkan: list ICD files, run the AIL probe (`tools/gpu_probe.c`: device name, `shaderFloat64`, `shaderInt64`,
   RTE, DenormPreserve, cooperative-matrix shapes). Print "Vulkan: NVIDIA device found" or "Vulkan: none" and stop.
4. `git clone https://github.com/J-KAMMA/ail-ci` at a commit the owner types in a cell (default `integ`).
5. Run `python3 -m unittest AIL_CURRENT/test_ail_gpu*.py` with `AIL_GPU=force` and the device chosen by
   `AIL_GPU_DEVICE=nvidia`; the modules compare with CPython in the notebook.
6. Run the bit tests (section 5.1) on the device.
7. B0: run the AIL benchmark program through Vulkan, then the same model in PyTorch + CUDA in the same notebook.
8. Write a short summary (commit, device, driver, pass/fail per module, wall time) the owner pastes into the PR.

Cost control: the notebook does steps 1-3 first (seconds) and stops if nothing is usable; the whole run should fit in a
few minutes on a T4.

## 8. Positioning for ML workloads (owner decision 2026-10-29)

Goal: beat PyTorch where it can be measured, not everywhere. **Every speed statement in this section is unmeasured
until the benchmark named next to it has been run and its numbers are written here.**

### 8.1 What AIL does not rewrite

On the CPU, matmul and convolution are not written by AIL: it calls an optimized CPU BLAS (OpenBLAS or the system BLAS)
through the FFI (`@extern`; library policy: big proven native libraries are linked, not rewritten), so those kernels
reach **parity**. On the GPU, vendor libraries (cuBLAS, rocBLAS, oneMKL) are not used, because each ties the program to
one vendor (section 0); matrix multiply goes through a vendor-neutral Vulkan library first and AIL's own SPIR-V kernels
later (section 8.7). All of them are loaded with `dlopen`, so a binary without them still starts.

Exactness: a BLAS call is an FFI call, and the library defines its result, as with every `@extern` today. It is outside
the CPython comparison, and the docs say so. AIL never *replaces* a matmul the user wrote as Python loops with a BLAS
call: that changes the summation order, which is a silent difference. Tests of the FFI layer compare with the same
library called from CPython (ctypes), not with a Python loop.

### 8.2 Where AIL can win

| claim (unmeasured) | why it could hold | benchmark: what to measure, against what |
| --- | --- | --- |
| **No per-op dispatch**: small models and batch size 1 run faster | PyTorch eager pays Python and dispatcher work per op (often quoted as microseconds per op **[unverified]**); AIL compiles the whole forward pass to C with direct library calls | B1: latency per inference (median and p99 of 1,000 runs) of an MLP and a small transformer (2-4 layers, hidden 128-512), batch 1 and 8, CPU and GPU; against PyTorch eager and `torch.compile` (default and `mode="reduce-overhead"`), same weights, same BLAS |
| **Whole-program fusion** of element-wise chains into one kernel | the G1 kernel IR sees the whole loop body (bias + activation + scale + residual) and emits one kernel with one pass over memory | B2: wall time and bytes moved for chains of 3-10 element-wise ops over 10^5..10^8 elements; against PyTorch eager, `torch.compile` (Inductor/Triton) and a hand-written Triton kernel; on Colab (T4/L4) |
| **Start-up** | a native binary with no interpreter and no framework import | B3: time from process start to first output; against `python -c "import torch"` plus the same model |
| **Binary size and memory** for deployed inference | AIL binaries are tens of KB to a few MB (build disk 0.34 MB vs Rust 8.8 MB, measured earlier on another program); no framework in memory | B4: size on disk and peak RSS for B1's models; against a PyTorch install (wheel + CUDA libs), LibTorch C++ and ONNX Runtime |
| **CPython-exact surrounding code** | preprocessing and control code prints exactly what CPython prints, or is refused by name | B5: not a speed claim; the differential tests of section 5 on the preprocessing programs |

### 8.3 First target: small-model inference plus CPU-side preprocessing

The case: a program that reads text, tokenizes it (BPE/WordPiece written in Python: dicts, strings and loops, which the
typed and general paths already compile), runs a small model through BLAS and the fused element-wise kernels, and
prints the results. It is compared **end to end** (time and peak memory) with the same Python program under CPython +
PyTorch. The tokenizer alone is compared with Hugging Face `tokenizers` (Rust): B6, tokens per second on a fixed corpus
with the same vocabulary, identical token ids required.

### 8.4 Second target: one fused kernel faster than `torch.compile`

One element-wise chain (for example `gelu(x * w + b) * scale + residual`) where AIL's fused kernel beats `torch.compile`
on a Colab GPU. Measured with B2: median of 100 runs after warm-up, compile time reported separately. If it does not
win, the result is written here and the claim is dropped.

### 8.5 The precision problem (decided: D1, 2026-10-29, option (b))

ML runs in binary32/bf16/fp16; CPython floats are binary64. A fused kernel that computes in binary32 is not what
CPython computes, so under the zero-silent-differences rule it cannot be the meaning of ordinary Python float code. Two
ways out: (a) ML kernels stay binary64 (exact, but slow on consumer GPUs, section 4.3), or (b) a separate typed array
module whose element type is declared (`f32`) and whose arithmetic is defined by its own spec (rounded to binary32
after every op, like `array('f')` storage but for arithmetic too), shipped with a CPython reference implementation of
that module so the oracle comparison still works. (b) is what makes the targets above reachable. The owner chose (b)
on 2026-10-29 (D1, section 10): element types `f64`, `f32`, `f16`, `int8`, `int32`.

### 8.6 Staged plan (after G7; each one PR)

| stage | content | done means |
| --- | --- | --- |
| M1 | FFI bindings for CPU BLAS (`sgemm`/`dgemm`) and the typed array storage they read | B1 CPU numbers recorded against PyTorch eager; outputs equal the same BLAS called from CPython |
| M2 | fusion of whole element-wise chains (G1 IR) over the typed arrays, on Vulkan | B2 numbers on the laptop iGPU; CPython-equal outputs on lavapipe in CI |
| M3 | small-model inference example (MLP, small transformer) + Python tokenizer, end to end | B1, B3, B4, B6 recorded |
| M4 | GPU kernels for the declared-precision array module of 8.5 (D1: f64, f32, f16, int8, int32; the module itself is built in the modules/FFI stage) | bit-identical to the module's pure-Python reference under CPython |
| M5 | vendor-neutral GPU matmul through an existing Vulkan library (8.7) | bit-equal to the module's CPython reference on lavapipe, the 780M and (if available) Colab NVIDIA, or restricted to the cases where it is; B0 first numbers |
| M6 | own SPIR-V matmul kernels: exact binary64 tiled kernel, then `VK_KHR_cooperative_matrix` under the rules of 8.7 | every refusal and fallback of 8.7 tested; B0 and the 8.4 run on Colab against PyTorch + CUDA and `torch.compile`, result written here, win or not |

Out of scope: automatic differentiation, training (distributed or not), a model zoo, ONNX import, any CUDA code.

### 8.7 Vendor-neutral matrix multiply

**First (M5): an existing vendor-neutral Vulkan library.** Candidates, none checked yet (license, size and API all
**[unverified]**): the Vulkan backend of ggml (llama.cpp; MIT; matmul shaders, some with cooperative matrix), ncnn
(Tencent; BSD-3-Clause; Vulkan inference kernels), IREE (Apache-2.0 with LLVM exceptions; a whole compiler, likely too
big for the size budget), Kompute (Apache-2.0; a Vulkan compute framework without BLAS kernels, so it would not save
the matmul work). VkFFT (MIT) is FFT only; CLBlast is OpenCL, so it fails "Vulkan only". M5 picks one after checking
license, installed size, binary-size delta and whether its kernels are bit-identical across devices. Its kernels choose
their own accumulation order, so M5 accepts a library kernel only for an operation whose result is order-independent
(8.7 rules below) or whose order is fixed and documented; anything else stays on the CPU BLAS.

**Later (M6): AIL's own kernels.** Two kinds, with these exactness rules:

| matmul | CPython / spec result | rule |
| --- | --- | --- |
| a matmul written as Python loops over `float` (`c[i][j] += a[i][k] * b[k][j]`, or `sum(... for k ...)`) | binary64, `k` in order, each op rounded; `sum()` is Neumaier | **exact kernel**: tile over `i, j` only, never split `k`; each output element runs its `k` loop in order with `NoContraction` (plain `+=` or Neumaier, as written). Never cooperative matrix (its multiply-add order and internal precision are not specified **[unverified: reading of VK_KHR_cooperative_matrix]**) |
| the same loops over `int` (int64) | exact integers; overflow is the typed path's loud stop | exact kernel with overflow flags -> replay (section 3.3); order-independent, so `k` may be split |
| module op `matmul(A, B)` on int8 inputs with int32 accumulation (D1 module) | exact integer sum, defined by the module spec | **cooperative matrix allowed**: integer sums do not depend on order. Precondition checked before launch: `K * max|a| * max|b| < 2^31` (a max-abs reduction of each input, or a proof from the element type: int8 gives `K < 2^31 / 2^14`, so `K <= 131071`). Otherwise the exact scalar kernel in int64 runs |
| module op on f16 inputs, f32 accumulation | spec: each output is the exact sum of exact products, rounded once to f32 | **cooperative matrix only when the sum is exact in f32 whatever the order**: products of f16 are exact in f32 (22 significant bits); the run-time check verifies that the exponent span of all nonzero products plus `log2(K)` fits in 24 bits, so every partial sum is exact. Otherwise flag -> the exact kernel (wide accumulation in software) runs. Real ML data rarely passes this check, so most f16 matmuls take the exact kernel |
| module op on f32 inputs | spec: sequential `k` order, f32 rounding per op | exact kernel only; cooperative matrix **refused** (f32 inputs are rounded to tf32 or similar inside many matrix units **[unverified per vendor]**) |
| an "any order, faster" matmul whose bits differ per device | none: CPython has no such result | **explicit opt-in only** (D2): compile flag plus per-call or per-module marker, a note at every use, tolerance tests in a separate suite; never default, never chosen silently |

Cooperative matrix is on AMD RDNA3 (WMMA, the 780M's architecture), NVIDIA and Intel Arc hardware through their Vulkan
drivers **[unverified per driver]**; whether lavapipe implements `VK_KHR_cooperative_matrix` is **[unverified]**. If it
does not, the CI tests run the same kernels through the G1 CPU emulation and the exact fallback, and the
cooperative-matrix path itself is tested only on the laptop and Colab, by hand (a risk, section 9).

## 9. Risks

- **Little speed for float64 on the iGPU.** Consumer GPUs run binary64 far slower than binary32 **[unverified ratio for
  the 780M]**, and ordinary Python float code can never use binary32 (section 8.5). The guards (denormal, NaN, overflow) and software `/`/`sqrt` add work per
  element. G7 may find that only int and comparison-heavy kernels pay off. The design stops cleanly there.
- **Driver bugs.** A driver that ignores `NoContraction` or RTE would give wrong bits with no flag. Mitigation: the bit
  tests run on every device before it is trusted, and a device whose start-up feature list is not on a tested list can be
  kept on the CPU (decided in G3; this costs a small table of known-good driver versions). **Built in G3 (6.3) as a run-time
  self-test instead of a list**: every kernel is checked on the device it will run on, so an unlisted driver is covered too.
- **lavapipe is not a GPU.** It runs SPIR-V through LLVM on the CPU, so it cannot find bugs that depend on real GPU
  scheduling or memory. The laptop and Colab runs cover that, by hand only.
- **Proof scope creep.** The eligible body is deliberately the `parallel for` body; widening it (structs, nested lists)
  is a typed-path project first.
- **Cooperative matrix untested in CI** if lavapipe lacks it (8.7); and the exactness checks may make it rarely used.
- **Vendor-neutral can mean slower.** PyTorch + CUDA uses tuned vendor kernels; B0 may show AIL well behind on NVIDIA.
  The goal is to report how close it gets, not to assume parity.
- **CI install time.** The lavapipe packages are about 240 MB installed if the runner image lacks them; caching may be
  needed (G3).

## 10. Owner decisions

- **D1 (2026-10-29, was Q8): declared-precision array module, yes.** A separate array module with declared element
  types `f64`, `f32`, `f16`, `int8`, `int32` is planned under the modules/FFI stage (M4 is its GPU use). Each type has a
  pure-Python reference implementation that runs on CPython and gives bit-identical results (for example rounding every
  `f32`/`f16` result through `struct.pack('f'|'e')` / `array('f')`, and wrapping `int8`/`int32` as the spec says).
  Programs that use the module are compared with that reference under CPython, like every other AIL test.
- **D2 (2026-10-29, was Q10): exact is the default; inexact matmul only by explicit opt-in.** A fast matmul whose result
  can depend on the device or the summation order may exist only when both a compile flag and a per-call or per-module
  marker ask for it. The compiler prints a note naming every place it is used (file:line). It is never on by default and
  never chosen silently. Its tests compare within a stated tolerance, in a suite separate from the exact one.
- **D3 (2026-10-29, was Q1): no new spending, no CUDA.** First check whether Colab exposes NVIDIA's Vulkan driver
  (notebook step 3). If it does not, B0 runs on the AMD 780M only, and its NVIDIA half waits until an NVIDIA machine with
  a Vulkan driver is available.

## 11. Open questions for the owner

- **Q2. If Vulkan float rules fail on the iGPU** (G2 bit tests), switch to OpenCL, or keep the GPU off on that device?
- **Q3. Stop rule.** If G7 shows little or no speed gain for float64 on the 780M, may the GPU work stop after G7 (code
  kept, `auto` not offered)?
- **Q4. Marker form.** Is a `# ail: gpu` comment acceptable as the user-facing switch, plus `compile --gpu`?
- **Q5. numpy.** A numpy-like subset is not in this plan. Should it be planned as part of modules/FFI first?
- **Q6. CI cost.** One extra CI job (target under 5 minutes) for GPU tests on lavapipe: acceptable?
- **Q7. Windows laptop runs** need the Windows (MinGW) build path working for GPU programs. Is a by-hand run before each
  GPU merge enough, or do you want it scripted to run on a schedule?
- **Q9. Benchmark baseline.** For the PyTorch comparisons (section 8.2), which versions and machines count: the laptop
  CPU plus a Colab T4/L4, with `torch.compile` in its default mode?
