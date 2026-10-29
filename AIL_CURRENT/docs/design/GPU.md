# GPU offload (design only, 2026-10-29)

Design note for running parts of an AIL program on a GPU. Nothing here is built yet. The roadmap keeps the
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
| CUDA / PTX | No NVIDIA GPU on the laptop and no GPU in CI: nothing CUDA-specific could be tested where AIL is tested. Its float semantics are good (`add.rn.f64`, `div.rn.f64`, `sqrt.rn.f64`, f64 denormals kept) **[unverified: from memory of the PTX ISA]**. Possible later as a second backend from the same kernel IR (stage G9, owner decision Q1); see section 7 (Colab). |
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
| `//`, `%` | floor division, divisor's sign | **match**: emitted as `OpSDiv`/`OpSRem` plus the floor fix-up; `INT64_MIN // -1` sets the flag |
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
| **G9** (optional, owner decision Q1) | second backend: CUDA via PTX text from the same kernel IR, `dlopen("libcuda.so.1")` | validated on Colab only (section 7); CI still covers the Vulkan backend and the shared IR | G7 |

G1 can start as soon as the IR core and typed path are stable, but the roadmap order holds: GPU work is scheduled after
release. G3 needs the Windows build of the FFI/modules stage for the laptop run.

## 7. Colab validation (owner-started, manual)

The owner has a paid Google Colab subscription with NVIDIA GPUs (T4/L4/A100 class, CUDA). It is useful as a second real
device, with three limits that keep it out of CI: every run spends paid compute units, there is no stable automation
API, and the runtime image changes without notice. **CI never depends on Colab; a Colab run is started by the owner.**

Does it change the backend choice? No:
- The default backend must run on the AMD iGPU and on lavapipe in CI; CUDA runs on neither, so a CUDA-first design would
  leave the CI and the owner's laptop untested.
- Colab can still run the **Vulkan** backend if the container exposes the NVIDIA Vulkan driver (`nvidia_icd.json` and
  `libGLX_nvidia`); whether Colab mounts the graphics part of the driver or only compute/utility is **[unverified]**. The
  notebook checks it first. If it is there, Colab is a third device for the same SPIR-V (NVIDIA has full f64, RTE and
  DenormPreserve support **[unverified per driver]**).
- If Colab has no Vulkan, it only becomes useful through the optional CUDA/PTX backend (G9). PTX has the float rules
  AIL needs natively (`.rn` division and sqrt, f64 denormals), so G9 would be cheap per kernel, but its code could only be
  tested on Colab, by hand. That trade-off is Q1.

Notebook outline (`tools/colab/gpu_check.ipynb`, written in G3):
1. Show the runtime: `nvidia-smi`, `cat /etc/os-release`, `python3 --version`; stop with a clear message if no GPU.
2. Install build deps: `apt-get install -y gcc libvulkan1` (and `vulkan-tools` for `vulkaninfo`); install CPython 3.12
   if the image's Python is another version (the oracle must be 3.12).
3. Probe Vulkan: list ICD files, run the AIL probe (`tools/gpu_probe.c`: device name, `shaderFloat64`, `shaderInt64`,
   RTE, DenormPreserve). Print "Vulkan: NVIDIA device found" or "Vulkan: none (CUDA only)".
4. `git clone https://github.com/J-KAMMA/ail-ci` at a commit the owner types in a cell (default `integ`).
5. Run `python3 -m unittest AIL_CURRENT/test_ail_gpu*.py` with `AIL_GPU=force` and the device chosen by
   `AIL_GPU_DEVICE=nvidia`; the modules compare with CPython in the notebook.
6. Run the bit tests (section 5.1) on the device.
7. (G9 only) the same modules with `AIL_GPU_BACKEND=cuda`.
8. Write a short summary (commit, device, driver, pass/fail per module, wall time) the owner pastes into the PR.

Cost control: the notebook does steps 1-3 first (seconds) and stops if nothing is usable; the whole run should fit in a
few minutes on a T4.

## 8. Positioning for ML workloads (owner decision 2026-10-29)

Goal: beat PyTorch where it can be measured, not everywhere. **Every speed statement in this section is unmeasured
until the benchmark named next to it has been run and its numbers are written here.**

### 8.1 What AIL does not rewrite

Matmul, convolution and attention kernels are not written by AIL. AIL calls the same vendor libraries PyTorch calls
(cuBLAS/cuDNN on NVIDIA, rocBLAS/MIOpen on AMD, an optimized CPU BLAS such as OpenBLAS) through the FFI (`@extern`;
library policy: big proven native libraries are linked, not rewritten). For those kernels the target is **parity**, not a
win. They are loaded with `dlopen`, like Vulkan, so a binary without them still starts.

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

### 8.5 The precision problem (owner decision Q8)

ML runs in binary32/bf16/fp16; CPython floats are binary64. A fused kernel that computes in binary32 is not what
CPython computes, so under the zero-silent-differences rule it cannot be the meaning of ordinary Python float code. Two
ways out: (a) ML kernels stay binary64 (exact, but slow on consumer GPUs, section 4.3), or (b) a separate typed array
module whose element type is declared (`f32`) and whose arithmetic is defined by its own spec (rounded to binary32
after every op, like `array('f')` storage but for arithmetic too), shipped with a CPython reference implementation of
that module so the oracle comparison still works. (b) is what makes the targets above reachable; it is a semantics
decision.

### 8.6 Staged plan (after G7; each one PR)

| stage | content | done means |
| --- | --- | --- |
| M1 | FFI bindings for CPU BLAS (`sgemm`/`dgemm`) and the typed array storage they read | B1 CPU numbers recorded against PyTorch eager; outputs equal the same BLAS called from CPython |
| M2 | fusion of whole element-wise chains (G1 IR) over the typed arrays, on Vulkan | B2 numbers on the laptop iGPU; CPython-equal outputs on lavapipe in CI |
| M3 | small-model inference example (MLP, small transformer) + Python tokenizer, end to end | B1, B3, B4, B6 recorded |
| M4 | the binary32 array module of 8.5 (only if Q8 says yes) | its CPython reference matches bit for bit |
| M5 | GPU BLAS through `dlopen` (rocBLAS/cuBLAS) and the B2 run on Colab against `torch.compile` | the 8.4 result written here, win or not |

Out of scope: automatic differentiation, training (distributed or not), a model zoo, ONNX import.

## 9. Risks

- **Little speed for float64 on the iGPU.** Consumer GPUs run binary64 far slower than binary32 **[unverified ratio for
  the 780M]**, and ordinary Python float code can never use binary32 (section 8.5). The guards (denormal, NaN, overflow) and software `/`/`sqrt` add work per
  element. G7 may find that only int and comparison-heavy kernels pay off. The design stops cleanly there.
- **Driver bugs.** A driver that ignores `NoContraction` or RTE would give wrong bits with no flag. Mitigation: the bit
  tests run on every device before it is trusted, and a device whose start-up feature list is not on a tested list can be
  kept on the CPU (decided in G3; this costs a small table of known-good driver versions).
- **lavapipe is not a GPU.** It runs SPIR-V through LLVM on the CPU, so it cannot find bugs that depend on real GPU
  scheduling or memory. The laptop and Colab runs cover that, by hand only.
- **Proof scope creep.** The eligible body is deliberately the `parallel for` body; widening it (structs, nested lists)
  is a typed-path project first.
- **CI install time.** The lavapipe packages are about 240 MB installed if the runner image lacks them; caching may be
  needed (G3).

## 10. Open questions for the owner

- **Q1. CUDA for NVIDIA (Colab)?** Vulkan is the main backend. Should a second CUDA backend (G9) be built later, knowing
  it can only be tested by hand on Colab, never in CI? Or only use Colab to test the Vulkan backend if Colab supports it?
- **Q2. If Vulkan float rules fail on the iGPU** (G2 bit tests), switch to OpenCL, or keep the GPU off on that device?
- **Q3. Stop rule.** If G7 shows little or no speed gain for float64 on the 780M, may the GPU work stop after G7 (code
  kept, `auto` not offered)?
- **Q4. Marker form.** Is a `# ail: gpu` comment acceptable as the user-facing switch, plus `compile --gpu`?
- **Q5. numpy.** A numpy-like subset is not in this plan. Should it be planned as part of modules/FFI first?
- **Q6. CI cost.** One extra CI job (target under 5 minutes) for GPU tests on lavapipe: acceptable?
- **Q7. Windows laptop runs** need the Windows (MinGW) build path working for GPU programs. Is a by-hand run before each
  GPU merge enough, or do you want it scripted to run on a schedule?
- **Q8. binary32 for ML.** Ordinary Python floats are binary64, so fast ML kernels need a separate array module whose
  element type is declared `f32` and whose results follow its own spec, with a CPython reference version (section 8.5).
  Build it, or keep ML kernels in binary64?
- **Q9. Benchmark baseline.** For the PyTorch comparisons (section 8.2), which versions and machines count: the laptop
  CPU plus a Colab T4/L4, with `torch.compile` in its default mode?
