# Strategy: how AIL becomes the default language

Decided by the owner on 2026-11-08. This file sets the order of work; docs/ROADMAP.md lists the items.

## Lessons from languages that won

Dominant languages did not win on technical merit alone. Each of them:

1. **rode a new platform.** C rode Unix, JavaScript the browser, Java the enterprise server, and
   Python machine learning.
2. **let people move without throwing code away.** C++ took C as it was, TypeScript took JavaScript,
   and Kotlin took Java.
3. **had a first reason to use it.** Rails, NumPy and PyTorch were the reason people started.

## The platform AIL rides: AI writes the code

The language that wins this wave is the one that:

- AI writes most correctly;
- a machine can check after AI wrote it;
- runs fast.

Python is the language AI writes best, but it is slow and weakly checked. AIL takes that gap: Python
syntax, AIL's own semantics in docs/spec, Rust-level speed and safety, and loud refusal of any
difference from CPython.

## How to move: the TypeScript playbook

Existing `.py` code goes in unchanged and runs. Every function AIL can prove becomes as fast and as
safe as Rust. Nobody has to rewrite anything to start.

## The first use (the wedge): speeding up Python without rewriting it in Rust

Today, when part of a Python project is too slow, people rewrite that part in Rust through PyO3.
Polars, ruff and pydantic-core are examples. AIL's first promise is:

> Do not rewrite it in Rust. Compile it.

For a user that means:

1. **Install:** `pip install ailc`.
2. **Compile:** `ailc ext mod.py` (or the hybrid build) produces an importable extension module. The
   functions AIL proves run native; everything else stays on CPython unchanged.
3. **When a function stays on CPython,** the build says which line keeps it there and how to fix it,
   in the agent-readable error format (docs/design/AGENT_ERRORS.md). An AI can then make the change.
4. **Output** equals CPython's, or the build refuses by name. Silent differences are never allowed.

## Work order this sets

1. **The wedge works end to end.**
   - The hybrid / extension build (docs/design/CPYTHON_HYBRID.md) is correct today: 40 of 40 programs
     match CPython.
   - But it accelerates almost nothing: one function in 40 programs. The CPython boundary decides
     which functions can go native. Widening that boundary is the main line of work.
   - Typed reach for plain `.py` (pyreach, fc*) feeds the same goal.
2. **Errors AI can fix** (err2-6). A refused function must come with a fix an AI can apply.
3. **Proof in public.** compare-lab results against Rust, C and CPython, reproducible by anyone. The
   wedge benchmark is the hot path of real Python projects that were rewritten in Rust, compiled by
   AIL instead.
4. **Release early** (0.1, PyPI). This needs the owner's go each time. Only users show where real
   `.py` breaks.
5. **After that:** compile time and memory through self-hosting, data layout (layout1), safety proofs
   (proof1), and systems or embedded use (robo1).

## What waits

GPU, the torch-like API, async and other wide surface work stay on hold. They resume only when they
serve the wedge or after 0.1.

## How we judge progress

Each step reports numbers. The judging measures are:

- the share of functions in the wedge corpus that go native;
- speed against CPython and against the Rust rewrite;
- the AI fix rate for refusals;
- silent differences, which must stay at zero.
