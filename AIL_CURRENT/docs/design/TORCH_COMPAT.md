# PyTorch-style programs on AIL (design only, 2026-10-30)

Design note for the owner's decision to let small PyTorch programs compile with AIL: a torch-like API written in Python on
top of `ail_array` (TYPED_ARRAY.md), so that existing scripts run with little or no change. Nothing here is built. No
PyTorch C++/CUDA code is copied. It sits after the `ail_array` stages it needs (T3, T6 and two new dtypes, section 3).

Owner priorities this note is written against: results reproducible bit for bit on every device by default; never
silently different from the reference; Vulkan only, no CUDA; small binaries and fast start-up; a device-dependent fast
mode only as an explicit opt-in, later.

Verification marks, as in the other notes: **[verified 2026-10-30]** = checked while writing this note against
`torch 2.15.0+cpu` (CPU wheel from `download.pytorch.org/whl/cpu`, CPython 3.12.3, WSL on this laptop; PyTorch reports CPU
capability `AVX512`, MKL 2024.2, oneDNN 3.13.3), installed in a throwaway venv (`/home/bluec/scratch/torch-venv`);
**[read, not run]** = follows from reading code or docs; **[unverified]** = from memory or inference, to be checked in the
stage named. No AIL program was compiled for this note.

## 0. Words

- *torch layer*: the Python package AIL provides for `import torch` (working name `ail_torch`, section 9). Plain Python
  over `ail_array`; CPython can run it too.
- *oracle*: real PyTorch on CPU in the oracle configuration of section 2.2.
- *AIL reference run*: CPython 3.12 running the program with the torch layer and `ail_array.py` on the path instead of real
  PyTorch. This is what AIL's native build must equal bit for bit (the usual AIL rule).
- *op class*: E, O, L or R (section 2.3). Says how an op's AIL result relates to PyTorch's.
- *view*: a tensor that shares storage with another (PyTorch semantics, section 7.4).

## 1. Target programs (acceptance corpus)

### 1.1 The corpus

Ten small programs that cover what tutorials and small scripts do. They are kept here as the acceptance corpus. P1 adds
them as files with their oracle outputs (section 2.5). Each one was run under the oracle in five configurations
(threads 1, 4, 8 x capability DEFAULT, AVX2, AVX512) **[verified 2026-10-30]**; the last column says what changed.

| # | program | exercises | PyTorch's own output across configurations |
| --- | --- | --- | --- |
| C01 | tensor math | creation, `+ - * / ** // %`, broadcasting, `linspace`, `sum`/`mean`, `reshape`, `t()`, `@`, `sqrt exp log tanh`, `.item()`, `.tolist()`, sci-mode printing, `nan`/`inf`/`-0.` printing | identical |
| C02 | indexing and views | `x[0]`, `x[:, 1]`, `x[1:, ::2]`, `row = x[0]; row += 100` (writes `x`), `x[1] = 0`, `clone`, masks, `where`, `view(-1)` aliasing, `cat`, `stack`, `z[[0, 2]] = 1.0`, `unsqueeze`/`squeeze` | identical |
| C03 | scalar autograd | `requires_grad`, `x ** 3 + 2 * x`, `backward`, `.grad`, `grad_fn` in printing, `grad.zero_()`, `relu`, `no_grad`, `detach` | identical (after replacing `print(z.grad_fn)`, which prints an address, with `z.grad_fn.name()`) |
| C04 | hand-written MLP | `randn` data, `requires_grad_()`, `relu`, `@`, MSE written out, `backward`, manual SGD under `no_grad`, `p -= lr * p.grad` | `.item()` digits differ DEFAULT vs AVX2/512 (`2.032076835632324` vs `2.032076597213745`); tensor prints at 4 decimals identical |
| C05 | linear regression with `nn` | `nn.Linear`, `nn.MSELoss`, `optim.SGD`, `zero_grad/backward/step`, f-string of `loss.item()`, `print(model.weight)`, `print(model)` | `f"{loss:.6f}"` differs DEFAULT vs AVX2/512 (`8.976581` vs `8.976579`) |
| C06 | MLP classifier | `nn.Sequential`, `ReLU`, `F.cross_entropy`, `optim.Adam`, `argmax`, `.long()`, `.float().mean()`, `eval()`, `softmax` | **tensor print differs** DEFAULT vs AVX2/512: `2.1790e-08` vs `2.1774e-08`, `1.0343e-10` vs `1.0363e-10` |
| C07 | softmax / cross-entropy | stable softmax by hand, `max(dim, keepdim)`, `F.softmax`, `log_softmax`, `cross_entropy`, `nll_loss`, `logsumexp`, `sigmoid`, advanced index `p[arange, target]` | identical |
| C08 | tiny CNN | `nn.Module` subclass, `Conv2d(padding=1)`, `MaxPool2d`, `flatten`, `Linear`, `SGD(momentum=0.9)`, 20 steps | identical |
| C09 | module and state | `__init__`/`forward`, `print(net)`, `named_parameters`, `numel`, `state_dict`, `load_state_dict`, `eval()`, `torch.equal` | identical |
| C10 | reductions and broadcasting | `rand`, `sum/mean/var/std(dim, keepdim, unbiased)`, `max(dim)` (prints `torch.return_types.max(...)`), `argmax`, `min(dim).indices`, `(3,1) + (4,)`, `clamp`, `round`, `any`, `prod`, int sums, `eye`, `full` | identical |

Thread count (1, 4, 8) changed none of the ten outputs: their tensors are below PyTorch's parallel grain. It does change
larger ones (section 2.1).

### 1.2 The programs

```python
# C01 tensor math
import torch

a = torch.tensor([1.0, 2.0, 3.0])
b = torch.arange(3)
c = torch.zeros(2, 3)
d = torch.ones(3) * 0.1
print(a, b, c, d, sep="\n")
print(a.dtype, b.dtype, a.shape, c.shape, c.size(0))
print(a + d, a * 2, a / 3, a - 1, -a, a ** 2)
print(a + b)
print(b / 2, b // 2, b % 2)
e = torch.linspace(0, 1, 5)
print(e, e.sum(), e.mean())
m = torch.arange(6.0).reshape(2, 3)
print(m, m.t(), m.T.shape)
print(m @ torch.ones(3), torch.matmul(m, m.t()))
print(torch.sqrt(a), torch.exp(a), torch.log(a), torch.tanh(a))
print(a.item() if a.numel() == 1 else a.tolist(), a.sum().item())
print(torch.tensor(1e-5), torch.tensor([1e-5, 1e5]), torch.tensor([1.5, 1e9]))
print(torch.tensor([0.1, -0.0, float("nan"), float("inf")]))
```

```python
# C02 indexing and views
import torch

x = torch.arange(12.0).reshape(3, 4)
print(x[0], x[:, 1], x[1:, ::2], x[-1, -1])
row = x[0]
row += 100
print(x)
x[1] = 0
x[2, 3] = -1
print(x)
y = x.clone()
y[0, 0] = 7
print(x[0, 0].item(), y[0, 0].item())
mask = x > 50
print(mask, x[mask], torch.where(mask, x, torch.zeros_like(x)))
v = x.view(-1)
v[0] = 42
print(x[0, 0], v.shape, x.flatten().shape)
print(torch.cat([x, x], dim=0).shape, torch.stack([x, x]).shape)
z = torch.zeros(5)
z[[0, 2]] = 1.0
print(z, z.unsqueeze(0).shape, z.unsqueeze(1).shape, z.unsqueeze(0).squeeze().shape)
```

```python
# C03 scalar autograd
import torch

x = torch.tensor(2.0, requires_grad=True)
y = x ** 3 + 2 * x
print(y)
y.backward()
print(x.grad)
w = torch.tensor([1.0, -2.0, 3.0], requires_grad=True)
z = (w * w).sum()
print(z, z.grad_fn.name())
z.backward()
print(w.grad)
w.grad.zero_()
q = torch.relu(w).mean()
q.backward()
print(q, w.grad)
with torch.no_grad():
    r = w * 2
print(r, r.requires_grad, w.detach())
```

```python
# C04 hand-written MLP with autograd
import torch

torch.manual_seed(0)
X = torch.randn(64, 3)
true_w = torch.tensor([[1.5], [-2.0], [0.5]])
Y = X @ true_w + 0.3
W1 = (torch.randn(3, 8) * 0.5).requires_grad_()
b1 = torch.zeros(8, requires_grad=True)
W2 = (torch.randn(8, 1) * 0.5).requires_grad_()
b2 = torch.zeros(1, requires_grad=True)
lr = 0.05
for step in range(201):
    h = torch.relu(X @ W1 + b1)
    pred = h @ W2 + b2
    loss = ((pred - Y) ** 2).mean()
    loss.backward()
    with torch.no_grad():
        for p in (W1, b1, W2, b2):
            p -= lr * p.grad
            p.grad.zero_()
    if step % 50 == 0:
        print(step, loss.item(), loss)
print(W2.grad, pred[:3])
```

```python
# C05 linear regression with nn.Linear / MSELoss / SGD
import torch
import torch.nn as nn

torch.manual_seed(42)
x = torch.randn(100, 1)
y = 3.0 * x - 1.0 + 0.1 * torch.randn(100, 1)
model = nn.Linear(1, 1)
loss_fn = nn.MSELoss()
opt = torch.optim.SGD(model.parameters(), lr=0.1)
for epoch in range(100):
    opt.zero_grad()
    loss = loss_fn(model(x), y)
    loss.backward()
    opt.step()
    if epoch % 20 == 0:
        print(f"epoch {epoch}: loss {loss.item():.6f}")
print(model.weight, model.bias)
print(model)
```

```python
# C06 MLP classifier with Sequential / cross_entropy / Adam
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.manual_seed(1)
n = 200
x = torch.randn(n, 2)
labels = (x[:, 0] * x[:, 1] > 0).long()
model = nn.Sequential(nn.Linear(2, 16), nn.ReLU(), nn.Linear(16, 2))
opt = torch.optim.Adam(model.parameters(), lr=0.01)
for epoch in range(300):
    logits = model(x)
    loss = F.cross_entropy(logits, labels)
    opt.zero_grad()
    loss.backward()
    opt.step()
    if epoch % 100 == 0:
        acc = (logits.argmax(dim=1) == labels).float().mean()
        print(epoch, round(loss.item(), 4), acc.item())
model.eval()
with torch.no_grad():
    probs = F.softmax(model(torch.tensor([[1.0, 1.0], [1.0, -1.0]])), dim=1)
print(probs)
print(model)
```

```python
# C07 softmax and cross-entropy
import torch
import torch.nn.functional as F

logits = torch.tensor([[2.0, 1.0, 0.1], [0.5, 2.5, -1.0]])
target = torch.tensor([0, 1])
e = torch.exp(logits - logits.max(dim=1, keepdim=True).values)
p = e / e.sum(dim=1, keepdim=True)
print(p, p.sum(dim=1))
print(F.softmax(logits, dim=1), F.log_softmax(logits, dim=1))
manual = -torch.log(p[torch.arange(2), target]).mean()
print(manual, F.cross_entropy(logits, target), F.nll_loss(F.log_softmax(logits, dim=1), target))
print(torch.logsumexp(logits, dim=1), torch.sigmoid(logits), torch.softmax(logits, -1).argmax(-1))
big = torch.tensor([1000.0, 1001.0])
print(F.softmax(big, dim=0))
```

```python
# C08 tiny CNN
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.manual_seed(0)


class TinyCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv2d(1, 4, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2)
        self.fc = nn.Linear(4 * 4 * 4, 3)

    def forward(self, x):
        x = self.pool(F.relu(self.conv(x)))
        x = torch.flatten(x, 1)
        return self.fc(x)


net = TinyCNN()
imgs = torch.randn(5, 1, 8, 8)
target = torch.tensor([0, 1, 2, 1, 0])
opt = torch.optim.SGD(net.parameters(), lr=0.1, momentum=0.9)
for step in range(20):
    out = net(imgs)
    loss = F.cross_entropy(out, target)
    opt.zero_grad()
    loss.backward()
    opt.step()
    if step % 5 == 0:
        print(step, f"{loss.item():.4f}")
print(out.shape, net.conv.weight.shape, net.conv.weight.grad.shape)
print(out.argmax(1))
```

```python
# C09 nn.Module subclass, parameters, state_dict
import torch
import torch.nn as nn


class Net(nn.Module):
    def __init__(self, d_in, d_hidden):
        super().__init__()
        self.fc1 = nn.Linear(d_in, d_hidden)
        self.act = nn.Tanh()
        self.fc2 = nn.Linear(d_hidden, 1)

    def forward(self, x):
        return self.fc2(self.act(self.fc1(x)))


torch.manual_seed(3)
net = Net(4, 6)
print(net)
for name, p in net.named_parameters():
    print(name, tuple(p.shape), p.requires_grad)
print(sum(p.numel() for p in net.parameters()))
sd = net.state_dict()
print(list(sd.keys()))
net2 = Net(4, 6)
net2.load_state_dict(sd)
x = torch.ones(2, 4)
net2.eval()
with torch.no_grad():
    print(net(x), net2(x), torch.equal(net(x), net2(x)))
print(net.fc1.weight[0])
```

```python
# C10 reductions and broadcasting
import torch

torch.manual_seed(7)
t = torch.rand(3, 4)
print(t)
print(t.sum(), t.sum(dim=0), t.sum(1, keepdim=True).shape)
print(t.mean(dim=1), t.var(), t.std(dim=0), t.var(unbiased=False))
print(t.max(), t.max(dim=1), t.argmax(), t.min(dim=0).indices)
col = torch.tensor([[1.0], [2.0], [3.0]])
r = torch.tensor([10.0, 20.0, 30.0, 40.0])
print(col + r, (col * r).shape)
print(t.abs().clamp(0.2, 0.8), t.round(), (t > 0.5).sum(), (t > 0.5).any(), t.prod())
print(torch.tensor([1, 2, 3]).sum(), torch.tensor([1, 2, 3], dtype=torch.int32).sum().dtype)
print(torch.tensor([[1, 2], [3, 4]]).float().mean(), torch.eye(3), torch.full((2, 2), 7))
```

### 1.3 API surface ranked by use

Counted with `ast` over the ten programs (number of programs that use a name, then occurrences) **[verified
2026-10-30]**. Ten programs are a small sample; the order below is the corpus order, adjusted only where a name is a
known tutorial staple that the corpus under-counts (`DataLoader`, `torch.save`), which are marked. 107 distinct names
in total.

| rank | names (programs / uses) | stage |
| --- | --- | --- |
| 1 | `print(tensor)` (10/56), `torch.tensor` (7/18), `*` (7/14), `.item()` (6/9), `.mean` (6/7), `torch.manual_seed` (6/6) | P1 |
| 2 | indexing `[]` (5/19), `.shape` (5/16), `+` (5/8), `.backward()` (5/7) | P1, backward P2 |
| 3 | `.sum` (4/11), `torch.randn` (4/7), `nn.Linear` (4/6), `.argmax`, `.parameters()`, `-`, `torch.no_grad` (4 each) | P1-P3 |
| 4 | `.grad` (3/8), `.weight`, `torch.arange`, `torch.zeros`, `.step()`, `.zero_grad()`, `F.cross_entropy`, `**` (3 each) | P1-P3 |
| 5 | `@` (2/4), `.dtype`, `.max`, `F.softmax`, `/`, `torch.ones`, `.eval()`, `.float()`, `.numel()`, `.requires_grad(_)`, `.reshape`, `.zero_()`, `nn.Module`, `torch.exp`, `torch.log`, `optim.SGD`, `torch.relu` (2 each) | P1-P3 |
| 6 | used once: `.T`, `.t()`, `.view`, `.flatten`, `.clone`, `.detach`, `.tolist`, `.var/.std/.prod/.round/.abs/.clamp/.any`, `unsqueeze/squeeze`, `torch.cat/stack/where/eye/full/linspace/logsumexp/sigmoid/sqrt/tanh/equal/zeros_like/rand`, `F.log_softmax/nll_loss/relu`, `nn.Sequential/ReLU/Tanh/MSELoss/Conv2d/MaxPool2d`, `optim.Adam`, `state_dict/load_state_dict/named_parameters` | P1-P4 |
| - | not in the corpus but common in tutorials **[unverified frequency]**: `utils.data.TensorDataset/DataLoader`, `torch.save/load` of a `state_dict`, `nn.Dropout`, `nn.BatchNorm1d`, `.to(device)` with `device = "cuda" if torch.cuda.is_available() else "cpu"` | P5, and section 7.5 for devices |

## 2. Semantics and the reference

### 2.1 What PyTorch itself guarantees on CPU (measured)

The owner's rule needs a reference that gives one answer. PyTorch on CPU does not, even on one machine with
`torch.use_deterministic_algorithms(True)` and a fixed thread count. ATen picks a kernel per *CPU capability* at start-up
(`DEFAULT`, `AVX2`, `AVX512`; `ATEN_CPU_CAPABILITY` overrides it) and splits reductions by thread count. Measured on this
laptop, one process per configuration, same seed **[verified 2026-10-30]**:

| quantity (float32) | threads 1 vs 8 | DEFAULT vs AVX2 / AVX512 |
| --- | --- | --- |
| `x.sum()` of 65,536 `rand` values | **differs**: prints `tensor(32783.1523)` vs `tensor(32783.1562)` | same |
| `x.sum()` of 1,000,000 values | same | same |
| `A @ B`, 64x256 by 256x64; `F.linear` | same | **differs** (bits) |
| `exp`, `tanh`, `sigmoid` of 4,096 values | same | **differs** (bits) |
| `exp` vs `r_f32(math.exp(x))` (glibc, rounded once) | - | 41 (DEFAULT) / 35 (AVX2/512) of 4,096 differ |
| `sqrt` vs the correctly rounded result | - | **794 of 4,096 differ by 1 ulp in all three** (checked with an exact `Fraction` midpoint test) |
| `/`, `a * b + a` vs correctly rounded | 0 of 4,096 | 0 of 4,096 |
| a vector op vs the same op on one element at a time (`exp`, `tanh`, `sqrt`) | - | equal (no tail-vs-body difference) |
| `torch.rand(1000)` | - | same; and reproduced bit for bit from mt19937 (section 2.4) |
| `torch.randn(6400)` | - | **differs** |
| corpus C04, C05, C06 | same | **differs** (table 1.1); C06 at PyTorch's own print precision |

So "PyTorch's output" is a family of outputs. Two facts follow. First, matching PyTorch "at the default print
precision of 4 decimals" is not a property anyone can guarantee: PyTorch does not have it across its own kernels
(C06 differs in the 4th significant digit after 300 Adam steps; the 65,536-element sum differs in the printed digits
by thread count, because 4 decimals of a value near 32,783 is finer than one float32 ulp, 0.0039). Second, any fixed
AIL order will differ from some PyTorch configuration in the last bits of every reduction and matmul.

### 2.2 The oracle configuration

The oracle is real PyTorch, CPU wheel, version pinned (2.15.0 today), run as:

```
ATEN_CPU_CAPABILITY=default OMP_NUM_THREADS=1 python oracle.py prog.py
# oracle.py: torch.use_deterministic_algorithms(True); torch.set_num_threads(1); runpy.run_path(prog)
```

`DEFAULT` capability and one thread are chosen because they select the scalar kernels, the most portable
configuration (whether another x86-64 or an arm64 machine gives the same bits in it is **[unverified]**), and the one
whose `randn` AIL can reproduce exactly (2.4). The program text is not changed; settings live in the runner.

### 2.3 How to state "no silent differences" honestly: options

| option | statement | verdict |
| --- | --- | --- |
| (a) fixed order only | AIL defines one order for every reduction and matmul (TYPED_ARRAY 3.5 / 3.7); PyTorch differs in the last bits; nothing more is promised | honest but says nothing about which ops do match PyTorch exactly, which most do |
| (b) tolerance only | every output is compared with PyTorch within a tolerance | gives up bit-exact claims even where they hold (element-wise ops, indexing, RNG, printing); weak |
| (c) print-precision exact | "prints exactly what PyTorch prints at 4 decimals", refuse what cannot be guaranteed | **not achievable**: 2.1 shows PyTorch's own prints differ by ISA and thread count, and no compile-time check can tell which sums are safe (it depends on the data). Refusing every sum and matmul would refuse every corpus program |
| (d) replicate PyTorch's kernels bit for bit | copy the DEFAULT-capability order of every kernel | MKL `sgemm` is closed and dispatches on CPUID itself; the order is defined by PyTorch's source of one version; it is not SIMD- or GPU-friendly, so the GPU could not reproduce it. Rejected for reductions; used where the kernel is integer-exact or scalar (RNG, 2.4) |
| **(e) two levels with op classes (recommended)** | below | |

**Recommended (e): two levels, four op classes.**

- **Level A, the AIL rule, unchanged.** An AIL build prints exactly what the AIL reference run prints (CPython + torch
  layer + `ail_array.py`), on every device, with `AIL_GPU` on or off, or it is refused at compile time by name. This
  is where "reproducible bit for bit on every device" and "never silently different" are guaranteed, because AIL owns
  the definition.
- **Level B, the PyTorch relation, stated per op.** Every torch op is in one class, listed in the API table of P1:

| class | meaning | ops (first stages) | test against the oracle |
| --- | --- | --- | --- |
| **E** exact | AIL's definition equals PyTorch's oracle bit for bit; PyTorch's own result is the same in every configuration of 2.1 | creation, `+ - * /` (element-wise, same dtype, float or int), comparisons, `abs`, `neg`, `clamp`, `relu`, `maximum/minimum`, casts, `round`, indexing, views, `cat/stack/where`, `max/min/argmax` (order-free), int reductions, `rand`/`randint`/`randperm`/`manual_seed`, `randn` (oracle configuration), `nn.Linear` init, printing of equal bits, `item/tolist` | bit equality (`.tolist()` reprs and prints) |
| **O** ordered | AIL uses its one fixed order (16 lanes, 1024 blocks, TYPED_ARRAY 3.5/3.7); PyTorch's order depends on threads and ISA | float `sum/mean/var/std/prod/logsumexp`, `@/matmul/mm/addmm/linear`, `conv2d`, `softmax/log_softmax/cross_entropy/nll_loss/mse_loss` (their sums), gradients that go through these | each number within the bound of TYPED_ARRAY 7 (`gamma_n * sum|x_i|` per output); printed text compared field by field with that bound plus one unit of the last printed digit |
| **L** libm | AIL computes `r_T(libm(double(x)))` (TA definition, one rounding; `sqrt` correctly rounded); PyTorch uses vector approximations that differ from that, and from each other per ISA, by about 1 ulp | `exp log tanh sigmoid sqrt pow(float)`, `softmax` (also O) | within 2 ulp per element **[bound from the 2.1 sample, unverified in general; P1 measures on large samples]** |
| **R** refused | neither AIL nor PyTorch gives one answer, or AIL has no defined form yet | section 7.5 | compile-time refusal test |

The sentence in the docs: *"AIL's torch gives the same bits on every machine and every device, and equals its CPython
reference exactly. Against PyTorch: class E ops give PyTorch's exact bits; class O and L ops give AIL's documented
result, which is within a stated bound of PyTorch's, and PyTorch's own result for them changes with the CPU and the
thread count."* A build that uses O or L ops gets one compile note (not one per op):
`note: prog.py: 14 order-defined (O) and 3 libm (L) torch ops; their last bits follow AIL's definition, not a particular PyTorch build (TORCH_COMPAT.md 2.3)`.

Corpus expectation: C02 uses class E ops only; C03's sums and means are of small integers and halves, exact in binary32
in any order, so its O-class results are exact too; the other eight use O/L ops on inexact values. Most of their printed lines are expected to match the oracle text exactly, but that
is a result to be measured in P1-P4, not a promise; a line that does not match is accepted only if every number is within
its bound, and the program is then listed as "O/L: within bound" in the corpus table.

### 2.4 Random numbers (measured, mostly class E)

Synthetic data and `nn.Linear` initialisation come from PyTorch's CPU generator, so matching it decides whether C04-C10
print the same tensors at all.

- **Generator**: mt19937, seeded with `init_genrand(seed & 0xffffffff)` **[read, not run: the seed > 2^32 case is
  unverified]**.
- **`rand` (float32)**: `(u32 & 0xffffff) * 2^-24` per element, one 32-bit draw each. Reproduced from a 40-line Python
  mt19937: `rand(1000)` after `manual_seed(0)`, 0 differences **[verified 2026-10-30]**.
- **`randn`, n >= 16, float32, contiguous (DEFAULT capability)**: fill with `rand`, then per group of 16 Box-Muller in
  float: `u1 = 1 - d[j]`, `u2 = d[j+8]`, `radius = sqrtf(-2 * logf(u1))`, `theta = (float)(2 * pi * u2)`,
  `d[j] = radius * cosf(theta)`, `d[j+8] = radius * sinf(theta)`; when `n % 16 != 0` the last 16 are redrawn and redone.
  Reproduced with glibc `logf/sqrtf/cosf/sinf` (through ctypes): `randn(6400)`, 0 differences **[verified]**. Variants
  with binary64 `log`/`cos` gave 1,466 to 3,948 differences, so the float libm calls are part of the definition. The
  AVX2/AVX512 kernels give other bits (2.1); they are not the oracle.
- **`randn`, n < 16**: binary64 Box-Muller over 53-bit uniforms (`(hi << 32 | lo) & (2^53 - 1)) * 2^-53` from two
  draws), `r = sqrt(-2 * log1p(-u2))`, `theta = 2 * pi * u1`, returns `r * cos(theta)` and keeps `r * sin(theta)` in
  the generator for the next call, rounded to float32. Reproduced for n = 1, 3, 15 and across two calls **[verified]**.
- **Consequence**: `rand`, `randint`, `randperm`, `uniform_`, `normal_` and the `kaiming_uniform_` of `nn.Linear` are
  integer- or scalar-exact and can be class E; `randn` is class E against the oracle configuration, with the same
  platform dependence as `math.exp` (it follows the platform's `logf`, as PyTorch does). The exact `uniform_(a, b)`
  arithmetic (float or double accumulation) is **[unverified]**: P1 checks it on `nn.Linear` weights.

## 3. dtypes

### 3.1 Default float: options

| option | for | against |
| --- | --- | --- |
| **f32 default (recommended)** | the oracle is PyTorch; `torch.tensor([1.0])` is `float32` there **[verified]** and every printed value, `.item()` (`0.10000000149011612` for `tensor(0.1)`) and `dtype` line depends on it | needs native f32 in `ail_array` (stage T3) before anything runs fast |
| f64 default | matches CPython floats; T2/T6 already build f64 | every corpus program would print different digits from PyTorch (`.item()`, sums, losses): a silent difference by design. Rejected |

`torch.set_default_dtype(torch.float64)` and `dtype=torch.float64` are supported; then the printed suffix
`dtype=torch.float64` appears as in PyTorch.

### 3.2 Integer and bool tensors

PyTorch's integer default is **int64** (`torch.tensor([1, 2])`, `torch.arange(5)`, `argmax`, `.long()`, class labels
for `cross_entropy`) and comparisons give **bool** **[verified]**. `ail_array` has int8/int32 only (TYPED_ARRAY 1.2 lists
int64 and bool as out). So the torch layer needs two new `ail_array` dtypes:

- **int64**: storage and `+ - * // %`, comparisons, sums. Overflow: PyTorch wraps silently (`tensor([2**62]) * 4` is
  `tensor([0])`, `tensor([2**63 - 1]) + 1` is `-9223372036854775808`, int8 `127 + 1` is `-128` **[verified]**).
  Options: (i) **wrap like PyTorch** (recommended: the oracle wraps, so wrapping is not a difference; implemented with
  `ta.wrapping_*`, which exist for that purpose; TA1 stays the rule for direct `ta.*` use), with an opt-in
  `AIL_TORCH_INT_CHECK=1` that raises `OverflowError` instead; (ii) raise as TA1 does: a loud difference from the oracle
  on programs PyTorch runs, which rule 1 of the agent rules counts as a regression in spirit. Integer division by zero
  raises `RuntimeError: ZeroDivisionError` in PyTorch **[verified text]**; the torch layer checks first and raises that.
- **bool**: one byte per element, results of comparisons, masks, `any/all`, `sum` of bool is int64 **[verified:
  `(t > 0.5).sum()` prints `tensor(7)`]**.
- int32 and int8 (`dtype=torch.int32`) map onto the existing dtypes; `int32.sum()` returns int64 **[verified]**.
  float16 maps onto `f16`. bfloat16, uint8, int16, complex: refused by name (7.5) until a stage needs them.

### 3.3 Promotion (PyTorch's rules, implemented in the torch layer)

PyTorch promotes by category (bool < int < float); a tensor with dimensions decides the dtype within its category,
and zero-dim tensors and Python scalars only raise the category. Verified rows **[verified 2026-10-30]**:

| expression | result |
| --- | --- |
| int64 tensor + `2.5` | float32 (the default float, not float64) |
| int64 / int64 | float32 (true division) |
| int64 // 2, int64 % 2 | int64 (floor semantics: `[7, -7] // 2` is `[3, -4]`, `% 3` is `[1, 2]`) |
| float32 + float64 tensor | float64 |
| float32 + `2.5`; float32 + 0-dim float64 tensor | float32 |
| int32 + int64 tensor | int64; int32 + `1` stays int32 |
| float16 + float32 tensor | float32; float16 + `1.5` stays float16 |
| int64 * `True` | int64 |

`ail_array` itself refuses mixed dtypes (TA 3.6). The torch layer inserts the `astype` PyTorch's rule implies, then calls
one same-dtype `ail_array` op, so every promotion is visible in the layer's Python. One detail for f16: PyTorch computes
an f16 op with a Python scalar in float32 ("opmath") and rounds once **[read, not run]**, while `ail_array` first stores
the scalar to f16 (TA 3.6). For f16 the layer must pass the scalar at f32; P1 tests `h * 0.1` bits against the oracle.

## 4. Tensor printing

Printing is where a difference shows first, so it is implemented as PyTorch's formatter, re-written from its observed
behaviour and checked against the oracle on every case below. Given equal bits it is exact: each element is formatted from
its exact binary64 widening with Python's correctly rounded `'{:.4f}'` / `'{:.4e}'`, which AIL's float formatting already
reproduces.

Defaults (`torch._tensor_str.PRINT_OPTS`): `precision=4, threshold=1000, edgeitems=3, linewidth=80, sci_mode=None`
**[verified]**. Rules, with oracle output **[all verified 2026-10-30]**:

| rule | example |
| --- | --- |
| wrapper `tensor(...)`; 0-dim `tensor(2.5000)`; empty `tensor([])`, `tensor([], size=(2, 0))` | `tensor(5)` |
| integer-valued float tensors print `1.` style | `tensor([1., 2., 3.])`, `tensor([100000000.])` for `1e8` |
| otherwise fixed with 4 decimals, all elements padded to one width | `tensor([0.1000, -0.0000,    nan,    inf])`, `tensor([  -1.5000, 1000.0000])` |
| sci mode when the nonzero finite max/min ratio > 1000, or max > 1e8, or min < 1e-4 | `tensor(1.0000e-05)`, `tensor([1.0000e+00, 1.0005e+03])` (ratio 1000.5), but `tensor([0.0010, 1.0000])` (ratio 1000) and `tensor([0.0010, 0.0005])` |
| int tensors | `tensor([0, 1, 2])`; padded: `tensor([ 3, -4])` |
| bool | `tensor([ True, False])` |
| dtype suffix when not the default float, int64 or bool | `tensor([1, 2, 3], dtype=torch.int32)`, `tensor([1.5000], dtype=torch.float64)`, `dtype=torch.float16` |
| autograd suffix | `tensor([1., 2., 3.], requires_grad=True)` (leaf), `tensor(12., grad_fn=<AddBackward0>)` (non-leaf); none under `no_grad` or after `detach()` |
| `nn.Parameter` | `Parameter containing:` on its own line, then `tensor([0., 0.], requires_grad=True)` |
| 2-D: rows on new lines indented to the bracket; columns share one width | `tensor([[   1.5000,   -2.2500],` / `        [1000.0000,    4.0000]])` |
| line width 80: wrap and indent 8 | `torch.arange(30.0)` wraps after 14 elements |
| more than 1000 elements: 3 edge items and `...` | `tensor([   0.,    1.,    2.,  ...,  998.,  999., 1000.])` (width computed over the shown items) |
| named tuples | `torch.return_types.max(` / `values=tensor([...]),` / `indices=tensor([...]))` |
| `torch.Size([2, 3])`, `torch.float32`, `cpu` (device) | as shown |
| `print(model)` | `Net(` / `  (fc1): Linear(in_features=4, out_features=6, bias=True)` / `  (act): Tanh()` / ... / `)` |
| `print(t.grad_fn)` | `<SumBackward0 object at 0x758253a40670>`: an address, different in every PyTorch run; follows AIL's existing rule for default object reprs (not part of any comparison) |

Order of checks, as PyTorch: summarise first, then decide int mode and sci mode over the shown elements only, then
width. The cases above become `tests` in P1, plus a generated sweep: 2,000 random tensors (shapes 0-D to 4-D, sizes
around 1000 and 80 columns, values spanning the sci-mode thresholds, NaN, inf, `-0.0`, subnormals) printed by the oracle
and by the AIL reference run, compared as text. If the formatter is ported from PyTorch's `_tensor_str.py` rather than
re-written, it carries PyTorch's BSD-3 notice (section 9).

## 5. Autograd

### 5.1 In scope, as stage P2

Six of the ten corpus programs call `backward()`; a torch layer without autograd runs inference only. Recommendation:
P1 without autograd (tensors, printing, `no_grad` as a no-op context), **P2 autograd** immediately after, before `nn`.

### 5.2 Tape design

- Every tensor op that has an input with `requires_grad=True` (and is not under `no_grad`) creates a node: the op's
  PyTorch name (`AddBackward0`), its input edges, the saved values, and a sequence number from a per-process counter.
  `t.grad_fn` returns the node; `.name()` and printing give the name.
- `backward()` runs nodes in **decreasing sequence number** from the root (PyTorch's CPU engine order for one device
  **[read, not run: P2 verifies on graphs with shared inputs]**). A tensor that receives gradients from several consumers
  accumulates them **in arrival order** (`buf = buf + g`), and a leaf's `.grad` is accumulated across calls
  (`(x * x).sum()` then `(x * 3).sum()` give `tensor([5., 5., 5.])` **[verified]**). Both orders are fixed by the program,
  so gradients are reproducible; where the forward ops are class E, AIL's gradients equal PyTorch's bit for bit only if
  each backward formula is the same expression as PyTorch's (`grad * other` for `MulBackward0`, `grad * y * (1 - y)`
  for `SigmoidBackward0`, ...). P2 writes each formula from PyTorch's documented derivatives and tests the bits.
- Saved tensors carry the version of their storage; an in-place change before `backward` raises PyTorch's text
  `RuntimeError: one of the variables needed for gradient computation has been modified by an inplace operation: ...`
  **[verified text]**. In-place on a leaf that requires grad raises `RuntimeError: a leaf Variable that requires grad is
  being used in an in-place operation.`; a second backward through a freed graph raises
  `RuntimeError: Trying to backward through the graph a second time ...` **[verified texts]**.
- Gradients through O-class ops (matmul, sums) are themselves O-class.

### 5.3 Names in printing (verified) and the first ops with gradients

`grad_fn` names observed **[verified 2026-10-30]**: `AddBackward0`, `SubBackward0`, `MulBackward0`, `DivBackward0`,
`PowBackward0` (both `x.pow(2)` and `x ** 2`), `ExpBackward0`, `TanhBackward0`, `SigmoidBackward0`, `ReluBackward0`,
`SumBackward0` (full) and `SumBackward1` (with `dim`), `MeanBackward0`, `MmBackward0` (2-D `@`), `AddmmBackward0`
(`nn.Linear` on 2-D input), `UnsafeViewBackward0` (`nn.Linear` on 1-D input), `ViewBackward0` (`view`, `reshape`),
`SelectBackward0` (`x[0]`), `SliceBackward0` (`pred[:3]`), `TBackward0`, `MseLossBackward0`, `NllLossBackward0`
(`F.cross_entropy`).

P2's op set is exactly the corpus's: `+ - * /`, `neg`, `pow` with a scalar exponent, `sum` (0 and 1), `mean`, `mm`,
`addmm`, `t`, `view/reshape`, select/slice indexing, `relu`, `tanh`, `sigmoid`, `exp`, `log`, `mse_loss`,
`log_softmax` + `nll_loss` (`cross_entropy`). P4 adds `conv2d` and `max_pool2d`. Higher-order gradients, hooks,
`autograd.Function`, `retain_graph`/`create_graph` beyond the default: refused (7.5).

## 6. nn and optim subset

- **`nn.Module`**: a Python class in the torch layer with ordered `_parameters`, `_modules`, `_buffers` dicts filled by
  `__setattr__` (as PyTorch), `__call__` -> `forward`, `parameters()`, `named_parameters()` (dotted names in
  registration order), `children()`, `train()/eval()`, `zero_grad()`, `state_dict()` (ordered name -> detached tensor),
  `load_state_dict()` (strict key check, PyTorch's error text), `__repr__` as in section 4. User subclasses are ordinary
  Python subclasses with `super().__init__()`. Whether the AIL compiler builds a user-visible `__setattr__` override
  and `__call__` on the general path is **[unverified]**; if not, P3's first task is either that support or a narrow
  recognition of `self.<name> = <Module or Parameter>` in `__init__` lowered to the registration call.
- **`nn.Parameter`**: a tensor with `requires_grad=True` and its own repr.
- **Modules**: `Linear` (weight `(out, in)`, `kaiming_uniform_(a=sqrt(5))` and bias `uniform(-1/sqrt(fan_in), ...)`,
  forward `addmm`), `ReLU`, `Tanh`, `Sigmoid`, `Sequential` (numbered children), `MSELoss`, `CrossEntropyLoss`,
  `Conv2d` and `MaxPool2d` (P4); `Dropout` and `BatchNorm1d` later (P5; Dropout draws from the generator, so it is class
  E once the draw order is matched).
- **`torch.nn.functional`**: `relu`, `softmax`, `log_softmax`, `cross_entropy`, `nll_loss`, `mse_loss`, `linear`,
  `conv2d`, `max_pool2d`.
- **`optim.SGD`** (`lr`, `momentum`, `weight_decay`, `nesterov`) and **`optim.Adam`** (`lr`, `betas`, `eps`,
  `weight_decay`): on CPU PyTorch takes the single-tensor path, not `foreach` (`_default_to_fused_or_foreach` returns
  `(False, False)` **[verified]**), so its update is a fixed sequence of element-wise ops (`exp_avg.lerp_(grad, 1 - beta1)`,
  `exp_avg_sq.mul_(beta2).addcmul_(grad, grad, value=1 - beta2)`, bias corrections, `addcdiv_` **[read, partly: P3
  transcribes the full sequence of the pinned version]**). The update is class E apart from `sqrt` (class L, 2.1):
  so Adam trajectories match PyTorch only within bound unless P1 finds `sqrt`'s formula (owner question 7).
  `zero_grad()` sets grads to `None` (PyTorch's default since 2.0 **[unverified for 2.15]**).
- `torch.save/torch.load` of a `state_dict`: P5, a subset of PyTorch's zip/pickle format, or refused until then.

## 7. Lowering plan

### 7.1 Representation

A tensor is a torch-layer object: `storage` (one 1-D `ail_array.Array` of its dtype, shared by views), `offset`,
`shape`, `strides` (in elements), `requires_grad`, `grad`, `grad_fn`, and a version counter on the storage. N-D shapes
are handled here; `ail_array` stays 1-D/2-D (TA5 unchanged). The layer is ordinary Python compiled by AIL: the object
side runs on the general path, and the element loops are `ail_array` calls whose dtype switch happens once per call
(TYPED_ARRAY 5.1), so a tensor op costs one dispatch plus the native loop **[per-op cost unmeasured; P1 measures it with
`tools/icount.c`]**. For the AIL reference run the test harness puts a directory holding a `torch` package (a thin alias of
`ail_torch`) first on `sys.path`; for the oracle run it does not, and real PyTorch is imported.

### 7.2 What maps where

| torch op | lowers to | new in `ail_array`? |
| --- | --- | --- |
| element-wise on contiguous operands of one shape | the 1-D op on the storage range (fused chains of 5.2a apply) | f32/int8/f16 native: T3; int64, bool: new stage T3b |
| element-wise with broadcasting or non-contiguous operands | gather each operand to a contiguous temporary by its strides (stride 0 for broadcast dims), then the 1-D op | **strided gather/scatter** primitive (moves only, exact); later a fused kernel that reads strides directly |
| in-place on a view (`row += 100`, `x[1] = 0`, `p -= lr * g`) | compute into a temporary, scatter into the storage, bump the version | strided scatter |
| full reduction (`sum`, `mean`, `prod`, `max`, `argmax`) | `ta.sum` etc. over the gathered elements in index order; `mean = sum / n` in T | none for floats; int64 sums |
| reduction along `dim` (`keepdim`) | move `dim` last (gather), then a **segmented** reduction: each slice in TYPED_ARRAY 3.5's order | **segmented sum/min/max/argmax** primitive |
| `var`, `std` | defined formula on top: mean, then sum of squared differences, divided by `n - 1` (unbiased default **[verified]**) | none |
| `@`, `mm`, `matmul` 2-D | `ta.matmul` (TA4 order) | f32 matmul (T6 has f64 only) |
| 1-D `@` 1-D, `mv`, batched `@` | `ta.dot` (equal to matmul's order by TA4), `(k, 1)` matmul, a loop over batches | none |
| `addmm` / `nn.Linear` | `matmul(x, W.T)` then `+ bias`: two roundings in that order | none |
| `conv2d` | im2col (gather) then `matmul` over `K = C_in * kh * kw` in `(c, kh, kw)` index order | none beyond gather |
| `max_pool2d` | gather windows, segmented max | segmented max |
| `exp log tanh sqrt` | `ta.exp` etc. (L class) | f32 forms: T3 |
| `sigmoid`, `softmax`, `log_softmax`, `logsumexp` | defined formulas over the ops above (max-subtract, `exp`, ordered sum, divide / `log`) | none |
| comparisons, masks, `where`, `x[mask]`, `x[[0, 2]]`, `cat`, `stack`, `index_select` | element-wise compare into bool; gathers and scatters | bool dtype |
| `rand`, `randn`, init | the generator of 2.4 written in the torch layer (integer mt19937; float `logf` etc. through the platform libm) | none |

### 7.3 Broadcasting

PyTorch's rule: align shapes on the right, a dimension of size 1 (or missing) stretches; otherwise
`RuntimeError: The size of tensor a (3) must match the size of tensor b (4) at non-singleton dimension 0`
**[verified text]**. The layer computes the result shape and gives each operand stride 0 along stretched dimensions;
element-wise results do not depend on how the loop walks, so broadcasting is class E. Cost: a materialised temporary
per broadcast operand until the strided kernel exists.

### 7.4 Views versus copies

PyTorch views alias, `ail_array` slices copy (TA 6.1). The torch layer therefore never uses `ail_array` slicing for
tensor indexing; it keeps one storage and makes views with offsets and strides.

- **Views** (share storage): basic indexing `x[0]`, `x[:, 1]`, `x[1:, ::2]`, `view`, `reshape` when strides allow,
  `t()`, `.T`, `transpose`, `permute`, `expand`, `squeeze`, `unsqueeze`, `flatten` of a contiguous tensor, `detach()`,
  `narrow`, `select`. Also: `.float()`, `.to(torch.float32)` and `.contiguous()` return **the same object** when nothing
  changes **[verified: `y.float() is y`]**.
- **Copies**: advanced indexing (`x[mask]`, `x[[0, 2]]`, `p[arange, target]`), `clone`, arithmetic results,
  `reshape`/`flatten` of a non-contiguous tensor, `contiguous()` of one, `cat`, `stack`, dtype changes.
- **Writes through views**: `row = x[0]; row += 100` changes `x` **[verified, C02]**; `x[0] += 1` is Python's
  `tmp = x[0]; tmp += 1; x[0] = tmp`, and the final `__setitem__` copies a view onto itself, as in PyTorch.
- **Overlap**: an in-place op whose input partly overlaps its output (`x[1:] += x[:-1]`) raises
  `RuntimeError: unsupported operation: some elements of the input tensor and the written-to tensor refer to a single memory location. Please clone() the tensor before performing the operation.`
  **[verified]**. The layer detects it (same storage, overlapping ranges) and raises the same text; exact overlap
  (`x += x`) is allowed, as in PyTorch.
- Sharing between tensors and the program follows the language's sharing rule (owner decision 2026-10-15): a tensor is a
  mutable object; its storage is one more object referenced by every view.

### 7.5 Refused at compile time (`write instead:`), and run-time texts

Same form as TYPED_ARRAY 8 and FFI_STAGE3 6: `file:line: not in the subset: torch: <what>; write instead: <hint>`. Where
PyTorch itself raises at run time for a program it accepts, AIL raises the same text at run time instead of refusing.

| construct | message (shape) |
| --- | --- |
| `.cuda()`, `device="cuda"`, `.to("cuda")` with a literal | run time, PyTorch's CPU-build text: `AssertionError: Torch not compiled with CUDA enabled` **[verified]**; `torch.cuda.is_available()` returns `False`, so the usual `device = "cuda" if ... else "cpu"` idiom runs unchanged. The GPU is used through `AIL_GPU` (section 8.3), not device strings |
| `device="mps"`, `"xpu"`, `"vulkan"`, `"meta"` | `torch: only the cpu device exists in AIL; write instead: drop device= (AIL_GPU uses the GPU for you)` |
| `torch.compile(f)` | accepted, returns `f` unchanged, with a note (`torch.compile has no effect: AIL compiles the whole program`); refusing it would refuse programs PyTorch runs |
| `torch.jit.script/trace`, `torch.fx` | `torch: TorchScript and fx are not built; write instead: call the function or module directly` |
| `dtype=torch.bfloat16`, `uint8`, `int16`, `complex64`, sparse or quantized tensors | `torch: dtypes are float32, float64, float16, int64, int32, int8, bool; write instead: torch.float32` |
| `.numpy()`, `torch.from_numpy`, `import numpy` | `torch: numpy is not built in AIL; write instead: t.tolist() / torch.tensor(list)` (PyTorch without numpy says `RuntimeError: Numpy is not available` **[verified]**) |
| `register_hook`, `autograd.Function`, `torch.autograd.grad(create_graph=True)`, `backward(create_graph=True)` | `torch: <name> is not built (stage P2 has first-order backward()); write instead: loss.backward()` |
| `DataLoader(num_workers > 0)`, `torch.multiprocessing`, `torch.distributed` | `torch: worker processes are not built; write instead: num_workers=0` |
| `torch.save`/`torch.load` before P5 | `torch: torch.save is not built yet; write instead: print(t.tolist()) or write the floats to a file` |
| monkeypatching torch (`torch.Tensor.foo = ...`), subclassing `Tensor`, `__torch_function__` | `torch: changing the torch layer is not supported; write instead: a plain function` |
| any torch name not in the layer's table | `torch.<name> is not built; write instead: <nearest built form, or "a loop over t.tolist()">`, generated from the table so that every unbuilt name has a test |
| `torch.use_deterministic_algorithms(True)`, `set_num_threads(n)`, `torch.backends.*.deterministic` | accepted, no effect: AIL's result does not depend on them |

## 8. Stages

### 8.1 Plan

Each stage is one PR, with Level A tests in every build mode (default, `AIL_UNIFIED_FORCE=1`, typed-only where it
applies) and Level B tests against committed oracle outputs. Programs that do not import `torch` keep byte-identical C.
Core compiler work stays one sequential line.

| stage | content | done means | depends on |
| --- | --- | --- | --- |
| **P0** | this note | merged into `integ` | - |
| **T3b** (array) | `ail_array` int64 and bool dtypes (wrapping int64 forms), strided gather/scatter, segmented reductions; f32 `matmul` | reference self-tests as T1; differential as T2; exact by construction (moves and the 3.5 order) | T3 (f32/f16/int8 native), T6 |
| **P1** | torch layer core: `Tensor` with storage/strides/views, dtypes and promotion (3), creation incl. `rand/randn/manual_seed` (2.4), element-wise ops, broadcasting, indexing, reductions with `dim`, `@`, printing (4), `item/tolist/shape/size/dtype`, `no_grad` (no-op), the op-class table (2.3), the oracle runner and committed goldens | C01, C02, C07 (forward), C10 print the oracle's text exactly or within their stated bound; the 2,000-tensor print sweep equal; `rand`/`randn` bits equal; Level A equal in every build mode; per-op instruction counts recorded | T3b |
| **P2** | autograd (5): tape, `backward`, accumulation order, `grad_fn` names, version counters and their errors, `requires_grad/detach/zero_` | C03, C04 match (C04's `.item()` lines within bound); gradient bits equal the oracle on E-only graphs | P1 |
| **P3** | `nn` / `optim` subset (6): `Module`, `Parameter`, `Linear` with exact init, `ReLU/Tanh/Sigmoid/Sequential`, losses, `F.*`, `SGD`, `Adam`, `state_dict` | C05, C06, C09 match or are within bound; `Linear` init weights bit-equal to the oracle | P2; compiler support of 6's `__setattr__`/`__call__` question |
| **P4** | `conv2d`, `max_pool2d`, `Conv2d`, `MaxPool2d`, `flatten` | C08 matches or is within bound | P3 |
| **P5** | data utilities (`TensorDataset`, `DataLoader(num_workers=0, shuffle)` with PyTorch's `randperm` order), `Dropout`, `BatchNorm1d`, `torch.save/load` of a `state_dict` | a second corpus of 5 programs using them | P3 |
| **P6** (GPU) | no torch-specific GPU code: torch ops are `ail_array` ops, offloaded by G5 and its successors; needs f32 device kernels (correctly rounded `/` and `sqrt` in software, as the f64 plan of GPU.md 3.2), matmul M5/M6 in the TA4 order | the whole corpus prints the same bits under `AIL_GPU=0`, `emu`, `force` on lavapipe and the 780M | G5..G7, M5/M6 |
| **P7** (opt-in, later) | fast mode under D2 (`--inexact-arrays` plus `order='any'` or the module marker): BLAS `sgemm`, vector libm, split-k on the device; never default | notes at every use; tolerance suite separate from Level A | T7, P4 |

### 8.2 Size and start-up targets against PyTorch

PyTorch, measured **[verified 2026-10-30; laptop shared with other work, load average about 3.5, page cache warm]**:

| quantity | PyTorch 2.15.0+cpu |
| --- | --- |
| wheel (`torch-2.15.0+cpu-cp312-cp312-manylinux_2_28_x86_64.whl`) | 209,530,490 bytes |
| installed venv (torch plus its 9 dependencies) | 938 MB; `torch/` alone 809 MB, of it `libtorch_cpu.so` 440,280,512 bytes; `sympy` 74 MB, `networkx` 19 MB |
| `python -c "import torch"` | median 2.03 s of 11 runs (1.77 to 2.76); `python -c pass` 0.01 s; `-X importtime` total 1.59 s, `torch._C` 0.31 s |
| peak RSS of `import torch` | 216 MB (5 runs, 216.0 to 216.6 MB) |
| C05 whole program (100 SGD steps on 100 points) | 4.6 to 7.6 s, 301 MB peak RSS (5 runs) |

AIL targets for the corpus programs (all **[unmeasured targets]**, checked in P1-P4 with `tools/icount.c` for
instructions and `/usr/bin/time` for RSS, not wall-clock alone): binary at most 2 MB per program (today's `ail_array`
programs are 31 to 69 KB, TYPED_ARRAY 5.2a; the torch layer is shaken by use like the array prelude); start-up to first
output under 20 ms (a native binary, no import); peak RSS under 20 MB for C01-C10; nothing to install besides the binary
(PyTorch: 938 MB). Throughput is not a target of P1-P4; the `speed-claims` skill applies before any speed claim.

### 8.3 How the GPU stages plug in

The device sees `ail_array` buffers only. G5 already runs f64 element-wise chains and `ta.sum` blocks on the device with
the CPU's bits (GPU.md 6.5). For torch programs the missing pieces are f32 kernels (P6), matmul through M5/M6 in the
TA4 order (a lane never mixes two outputs, so tiling over `i, j` keeps the bits, TYPED_ARRAY 3.7), and conv as im2col
plus that matmul. Device choice stays AIL's cost model (GPU.md 6.4); there is no `device=` in user code. So a torch
program gives the same bits on the CPU, lavapipe, the 780M and an NVIDIA GPU through Vulkan, which PyTorch does not
offer across its own CPU kernels (2.1).

## 9. Licensing

- PyTorch is BSD-3-Clause (copyright Meta Platforms and contributors, with further copyright lines in its `LICENSE` and
  third-party notices in `NOTICE` **[unverified wording; read the pinned version's files before any copy]**). Using the
  API names, signatures, error texts and observable behaviour, and writing our own implementation from that behaviour,
  is what this note plans; it needs no notice.
- **Not planned, but if code is ever copied or translated** (likely temptations: `torch/_tensor_str.py` for printing, the
  `nn.Module.__repr__` and `extra_repr` code, `derivatives.yaml` formulas, the `optim/adam.py` update sequence, the
  `DistributionTemplates.h` transforms): keep PyTorch's copyright line and BSD-3 text in the file that holds the copy and
  in the distribution's third-party notices; BSD-3 also forbids using the contributors' names to endorse AIL. BSD-3 code
  can be included in an MIT OR Apache-2.0 project with the notice kept. Third-party code inside PyTorch has its own
  licenses (SLEEF: Boost Software License 1.0; oneDNN: Apache-2.0; MKL: Intel's proprietary license **[unverified,
  from memory]**); none of it is planned. The mt19937 algorithm is published; AIL writes its own code, so the reference
  implementation's notice is not needed.
- **Names**: "PyTorch" is a trademark of the PyTorch Foundation / Linux Foundation **[unverified]**. The importable name
  `torch` is needed for unchanged programs; the product is described as "a PyTorch-compatible API", the reference
  package is `ail_torch`, and nothing is published to PyPI under `torch` (license decision 2026-10-18: only `ail-lang`,
  at release). This is not legal advice; the owner may want a check before release.

## 10. Risks

- **PyTorch moves.** Printing details, promotion corner cases, `randn` kernels and optimizer code change between
  versions. The oracle is pinned and the goldens name the version; a version bump re-runs the corpus.
- **Bounds instead of bits for O/L ops** will be read as "not exact" by users comparing with PyTorch. The docs show
  2.1's table: PyTorch differs from itself.
- **`sqrt`** (and through it Adam) is class L only because PyTorch's float32 `sqrt` is not correctly rounded in 19% of a
  random sample on this CPU; its formula is unknown **[unverified]**.
- **Per-op overhead of a Python-level layer** compiled by the general path is unmeasured; small tensors could be slower
  than PyTorch's C++ dispatch until the layer's hot paths are typed.
- **`nn.Module`'s `__setattr__`/`__call__`** may need compiler work (section 6).
- **Scope creep**: the long tail of `torch.*` (hundreds of ops). The generated refusal table keeps it visible; stages add
  only what a corpus program needs.
- **CI cost**: no PyTorch in CI (938 MB); goldens are committed and regenerated by an owner-run script with the throwaway
  venv. CI then cannot catch a wrong golden; the regeneration script prints the PyTorch version and configuration in
  each golden's header.

## 11. Owner questions

1. **Contract.** State the rule as two levels (2.3 (e)): bit-exact to AIL's own definition on every device (Level A),
   and per-op classes against PyTorch (E exact, O ordered, L libm, R refused), with one compile note per build for
   O/L ops? *Recommended: yes.* Print-precision matching (option c) is not achievable even by PyTorch (2.1).
2. **Oracle configuration.** PyTorch CPU wheel, version pinned, `ATEN_CPU_CAPABILITY=default`, one thread,
   `use_deterministic_algorithms(True)`, goldens committed? *Recommended: yes.*
3. **Default float dtype.** *Recommended: float32, as PyTorch* (f64 would make every corpus program print other digits).
4. **New `ail_array` dtypes.** Add int64 and bool (amending TYPED_ARRAY 1.2's "out" list), and the strided
   gather/scatter and segmented-reduction primitives, as stage T3b? *Recommended: yes; no other new dtypes.*
5. **Integer overflow in tensors.** Wrap like PyTorch (TA1 stays the rule for direct `ta.*` calls), with
   `AIL_TORCH_INT_CHECK=1` to raise instead? *Recommended: wrap by default.*
6. **Autograd timing.** *Recommended: in scope as P2, right after the core*, because six of ten corpus programs need it.
7. **`sqrt` and libm ops.** Keep AIL's correctly rounded `sqrt` and `r_T(libm)` definitions (class L), and let P1
   investigate PyTorch's float32 `sqrt` formula, switching only if it is the same on every CPU capability?
   *Recommended: yes.*
8. **`randn`.** Define it as PyTorch's DEFAULT-capability algorithm (reproduced bit for bit here, using the platform's
   `logf/sqrtf/cosf/sinf`)? *Recommended: yes*; `rand` and the init functions are integer-exact anyway.
9. **Names and packaging.** The reference package is `ail_torch`, `import torch` binds to it only in AIL builds and in
   AIL reference runs, nothing is published as `torch`, shipped inside `ail-lang` at release? *Recommended: yes.*
10. **Devices.** Only `cpu` exists; `cuda` gives PyTorch's own CPU-build error at run time, other device strings are
    refused, and the GPU is used through `AIL_GPU` with no `device=` in user code? *Recommended: yes.*
11. **Throwaway PyTorch venv.** Keep `/home/bluec/scratch/torch-venv` (938 MB) and the wheel
    (`/home/bluec/scratch/torch-whl`, 210 MB) for the P1 golden script, or delete them now? *Recommended: keep until P1
    merges.*
