# wedge3b: two more real libraries, pure Python versus their Rust rewrites

Measurement only; no compiler or library source is changed. Branch `job-wedge3b-11091226`, run
2026-11-09 on a 4-core GitHub Actions runner. Hybrid built from branch `job-obs5-op1109` at commit
`69e2dcd0` (`../obs5/AIL_CURRENT`). CPython 3.12.3, PyPy 3.10.16 (7.3.19), gcc 13.3.0.

## The answer, in one paragraph

**On two real libraries with different shapes, the CPython hybrid accelerates 0 of the 137
top-level functions in their hot modules and therefore runs at CPython parity (hybrid/CPython
0.96x-1.01x, indistinguishable from run noise), while the Rust rewrites run 2.35x (pydantic-core)
and 2.83x (sqlglotrs) faster than CPython.** The measured reason is selection, not the C boundary:
73% of pydantic's profiled hot-module self time is in methods of classes with bases/attributes and
21% in top-level functions whose observed types are a union or a tuple return; for sqlparse 54% is
in methods, 24% in top-level helpers with union/`None` kinds, and 14% in nested helpers. The
observed-type recorder does annotate sqlparse (98 annotation lines), but the annotated functions
return `None` or take `int|None`/`type|None` unions, which the hybrid ABI cannot carry; on pydantic
it adds one annotation because v1's functions are already annotated, mostly `Any`, and `annotate`
never replaces an existing annotation.

## 1. Libraries and workloads

| library | pure build (CPython, PyPy) | native rewrite | workload |
| --- | --- | --- | --- |
| pydantic | 1.10.27, installed `--no-binary pydantic` (no Cython; no `.so` in the package) | pydantic 2.14.3 + pydantic-core 2.50.4 (Rust) | `workloads/pydantic_records.py`: 20,000 nested `Order`/`Address`/`Line` models, integer-cent aggregation; output is version-independent |
| sqlparse | 0.6.1 (pure Python) | sqlglot 26.33.0 + real `sqlglotrs` 0.6.1 Rust extension (`sqlglot[rs]`) | `workloads/sql_workload.py` + `workloads/queries.sql`: 2,000 statements split and formatted; compares the normalised text (lowercase, whitespace/`;` removed) so the two formatters' style does not matter |

`sqlglot[rs]` at the current 30.30.0 installs only a deprecated warning stub, not the Rust module;
26.33.0 is pinned because its `[rs]` extra ships
`sqlglotrs.cpython-312-x86_64-linux-gnu.so`, and `SQLGLOTRS_TOKENIZER` defaults to `1`.
Every variant's stdout is byte-identical to CPython (SHA-256 checked in `times.json`), including the
250 s/2 s PyPy and native runs below.

All runs: one workload at a time, `RLIMIT_AS = 2.5 GB`, median of 5 processes, `AIL_NO_CACHE=1` for
builds. `tools/icount.c` builds but `perf_event_open` is denied on this runner (`Permission denied`),
so instruction counts are **not available**; wall time is the only metric here.

## 2. pydantic: 0 of 100 top-level functions native

Hot modules (89.9% of the profiled library self time): `main.py`, `fields.py`, `validators.py`,
`class_validators.py`, `utils.py`. Each was copied to a one-file staging directory, built with
`ail build --cpython`, and its generated module copy put back into a private copy of the package.

| build | median s | hybrid/CPython | hybrid/PyPy | hybrid/native | stdout |
| --- | ---: | ---: | ---: | ---: | --- |
| CPython (pydantic 1.10.27) | 1.2711 | -- | -- | -- | oracle |
| PyPy 3.10.16 | 0.5027 | -- | -- | -- | identical |
| hybrid, no observed kinds | 1.2628 | 0.993x | 2.512x | 2.334x | identical |
| hybrid, observed kinds | 1.2800 | 1.007x | 2.546x | 2.366x | identical |
| native (pydantic 2.14.3 / pydantic-core) | 0.5410 | -- | -- | -- | identical |

Functions in those five modules: **100 top-level defs, 0 native**; 105 methods and 9 nested defs are
outside the hybrid's unit. The build produced no extension at all (`build.json` `extension: null`).
The spread of the five runs overlaps (CPython 1.2657-1.2876 s, hybrid 1.2555-1.3930 s), so
1.007x is parity, not a regression.

Refusal reasons ranked by profiled self time (observer profile, 77 functions, 5.317 s in these
modules; the profile adds ~1.4x call overhead, so shares rank functions, not wall time):

| # | reason (build.json wording) | self s | share | funcs | examples |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | method of a class with decorators, bases, a metaclass or class attributes | 3.889 | 73.2% | 25 | `ModelField.validate` 1.185, `ModelField._validate_singleton` 1.113, `ModelField._apply_validators` 0.608, `BaseModel.__init__` 0.337 |
| 2 | not a typed candidate | 1.111 | 20.9% | 21 | `validate_model` 0.795, `int_validator` 0.115, `str_validator` 0.101, `float_validator` 0.064 |
| 3 | nested function (not a unit) | 0.315 | 5.9% | 5 | `_generic_validator_basic.<locals>.<lambda>` 0.315 |
| 4 | decorated/dunder/non-plain-signature method | 0.001 | 0.0% | 3 | `IfConfig.__init__` |
| 5 | method: field kind not expressible | 0.000 | 0.0% | 3 | `IfConfig.check` (`self.config_attr_names`) |
| 6 | not recorded (silent refusal) | 0.000 | 0.0% | 20 | |

`validate_model` is the single hottest top-level function (0.795 s) and is refused before selection:
its observed `input_data` is one of `dict[str, float|int|str]`, `dict[str, int|str]` and a nested
dict, and it returns a 3-tuple — neither is a hybrid ABI kind. The validators are annotated
`(v: Any) -> int`, so the observed kind is recorded but the existing `Any` annotation is kept.

Observed-type effect: `ail_observe.py annotate` added **1 annotation line across all five modules**
(`ModelMetaclass.__new__` `mcs: str`); 0 new candidates, 0 new native functions. The hybrid with and
without observed kinds is the same program.

## 3. sqlparse: 0 of 37 top-level functions native

Hot modules (93.2% of profiled library self time): `sql.py`, `engine/grouping.py`, `utils.py`,
`lexer.py`, `engine/statement_splitter.py`, `tokens.py`, `filters/reindent.py`.

| build | median s | hybrid/CPython | hybrid/PyPy | hybrid/native | stdout |
| --- | ---: | ---: | ---: | ---: | --- |
| CPython (sqlparse 0.6.1) | 2.0194 | -- | -- | -- | oracle |
| PyPy 3.10.16 | 4.3260 | -- | -- | -- | identical |
| hybrid, no observed kinds | 1.9965 | 0.989x | 0.462x | 2.797x | identical |
| hybrid, observed kinds | 1.9469 | 0.964x | 0.450x | 2.727x | identical |
| native (sqlglot 26.33.0 / `sqlglotrs`) | 0.7139 | -- | -- | -- | identical |

Functions in those seven modules: **37 top-level defs, 0 native**; 86 methods and 41 nested defs.
No extension is produced. The hybrid's advantage over CPython (0.96x-0.99x) is inside the run spread
(CPython 1.9526-2.0591 s, hybrid-observed 1.9407-1.9596 s); the honest reading is parity. PyPy is
**2.14x slower** than CPython on this workload, so the hybrid beats PyPy without doing any work.

Refusal reasons ranked by profiled self time (147 functions, 6.222 s in these modules):

| # | reason (build.json wording) | self s | share | funcs | examples |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | method of a class with decorators, bases, a metaclass or class attributes | 3.327 | 53.5% | 28 | `Token.match` 1.079, `Lexer.get_tokens` 0.578, `_TokenType.__contains__` 0.513, `TokenList._token_matching` 0.345 |
| 2 | not a typed candidate | 1.502 | 24.1% | 36 | `imt` 0.766, `_group` 0.334, `consume` 0.120 |
| 3 | nested function (not a unit) | 0.867 | 13.9% | 28 | `TokenList.token_next_by.<locals>.<lambda>` 0.274, `wrapped_f`, filter lambdas |
| 4 | method: field kind not expressible | 0.454 | 7.3% | 15 | `StatementSplitter._change_splitlevel` (`self._block_stack`), `process` (`self.tokens`) |
| 5 | decorated/dunder/non-plain-signature method | 0.070 | 1.1% | 6 | |
| 6 | not recorded (silent refusal) | 0.001 | 0.0% | 34 | |

Observed-type effect: `annotate` added **98 annotation lines** (grouping.py 46, reindent.py 17,
sql.py 16, lexer.py 7, utils.py 6, statement_splitter.py 4, tokens.py 2) and still accelerated
nothing. The reason is the observed kinds themselves: every `group_*` helper is typed
`(tlist) -> None`, and `None` is not a hybrid result kind; `imt` returns `bool` but takes
`i: int|None`, `m: type|None`, `t: type|None`, none of which is a single expressible kind.

## 4. Reading the two libraries together

| | pydantic | sqlparse |
| --- | ---: | ---: |
| top-level functions in hot modules | 100 | 37 |
| of those native | 0 | 0 |
| all defs (top-level + methods + nested) | 214 | 164 |
| hybrid / CPython | 1.007x (obs), 0.993x (plain) | 0.964x (obs), 0.989x (plain) |
| hybrid / PyPy 3.10 | 2.55x | 0.45x |
| hybrid / native rewrite | 2.37x | 2.73x |
| native rewrite / CPython | **2.35x faster** | **2.83x faster** |
| native rewrite / PyPy | 0.93x (PyPy is 1.08x faster) | 6.06x faster |

The two libraries fail for different but adjacent reasons. pydantic is already typed, and its hot
work is in instance methods of `BaseModel`/`ModelField`; the one big top-level function,
`validate_model`, takes a dict-of-union and returns a tuple. sqlparse is untyped, and observation
does annotate it, but its top-level grouping helpers return `None` and its predicates take
`int|None`/`type|None`. Neither library contains the hybrid's unit: a top-level function with
scalar (or `list[int]`/`list[float]`) parameters and a scalar return, no call/index/raise in the
body. That is why the C boundary is irrelevant here — there is nothing to send across it.

## 5. Probes (mandatory self-check)

Probes are in `probes/` (copies of `/tmp/probes/`), all self-contained. `bash ~/tools/cmp.sh`
compares the general path with CPython; the hybrid column is `ail build --cpython` from
`../obs5/AIL_CURRENT`, run and compared with `python3` byte for byte.

| probe | `cmp.sh` g / d | hybrid plain: native, output | hybrid + observed: native, output |
| --- | --- | --- | --- |
| `w3b_boundary.py` | refused by name on both: `int64 constant expression out of range: 1180591620717411303424` | 9 native, SAME | 9 native, SAME |
| `w3b_none_union.py` | same stdout on both | 0 native, SAME | 1 native, SAME |
| `w3b_sqlshape.py` | refused by name on both: constant `(1 << 64) - 1` overflows int64 | 0 native, SAME | 0 native, SAME |
| `w3b_observed.py` | same stdout on both | 4 native, SAME | 4 native, SAME |

`w3b_boundary.py` covers `int`/`bool`/`float`/`str`/`list[int]` parameters and returns, an empty
list, a negative value, a value outside int64 (fallback), `-0.0`, NaN, infinity, a mutated list
parameter (stays in CPython), a zero divisor caught by the caller, and values reaching the call
through an argument, a list item, an attribute and a dict value. `w3b_none_union.py` is the
pydantic/sqlparse shape (methods, nested lambda, `None` returns, union dict) and stays in CPython.
`w3b_sqlshape.py` is the sqlparse shape (split + normalise + FNV) and stays in CPython.
`w3b_observed.py` is untyped code that the recorder can annotate; it goes native in both modes.

The two library workloads themselves were additionally run in all five builds and every stdout
matched byte for byte (recorded in `times.json`, `match: true`).

## 6. One tooling limitation found (worked around, not a wrong answer)

`ail build --cpython main.py -o DIR` on a *package* module, built in place, produces a copy whose
preamble inserts the module's own directory at the front of `sys.path`. For `pydantic/main.py`
that directory contains `json.py`, `typing.py`, `dataclasses.py` and `config.py`, so the next
stdlib `import json` resolves to `pydantic/json.py` and the package dies with
`ImportError: cannot import name 'TYPE_CHECKING' from partially initialized module 'typing'`.
The measurement builds each module from a staging directory that contains only that one file, so
the inserted path shadows nothing; the original library directory is never put on `sys.path`.
This is a real limitation for using the hybrid on library packages as-is; it does not affect these
numbers, and no stdout difference was observed.

## 7. Reproduce

```sh
sh lab/wedge3/wedge3b/install.sh /tmp/w3b          # two venvs + portable PyPy 3.10
python3 lab/wedge3/wedge3b/hybrid.py \
  --package /tmp/w3b/vpure/lib/python3.12/site-packages/pydantic --name pydantic \
  --modules main.py,fields.py,validators.py,class_validators.py,utils.py \
  --profile /tmp/w3b/pyprof.json --work /tmp/w3b/hyb_py_obs
python3 lab/wedge3/wedge3b/measure.py --out lab/wedge3/wedge3b/times.json
python3 lab/wedge3/wedge3b/analyse.py --profile ... --summary ... --package ... \
  --modules ... --out lab/wedge3/wedge3b/refusals_pydantic.json
```

`hybrid.py` also runs without `--profile` for the "no observed kinds" build; the profile comes from
`python3 ../obs5/AIL_CURRENT/ail_observe.py run --all -o PROF.json workloads/<workload>.py`.

## 8. What is not measured

* Instruction counts: `perf_event_open` is denied on this runner (`tools/icount.c` builds, the
  counter open fails with EPERM), so there are no icount columns.
* Only the listed hot modules are hybridised (89.9% and 93.2% of the profiled library self time);
  the rest of each library has no meaningful top-level-function share.
* The hybrid has no native function in either library, so there is no per-call boundary effect to
  measure; the hybrid times are the generated module copies running in CPython.
* PyPy 3.10.16 is the portable 7.3.19 build from python.org because the distro `pypy3` is 3.9.
