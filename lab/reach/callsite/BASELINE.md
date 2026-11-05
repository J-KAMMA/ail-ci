# Call-site specialisation sample: baseline (fcspec0)

Base: `integ` at `ff12fa938` (2026-11-06). Oracle: CPython 3.12, stdout and exit status.
Reproduce: `python3 lab/reach/callsite/census.py -j 1` (about 7 minutes at -j 1 on this laptop).

**programs 52: typed 2 / general 39 / refused 11 / wrong 0**

| step | programs | typed | general | refused | wrong |
|---|---:|---:|---:|---:|---:|
| S1 scalar defs | 5 | 0 | 3 | 2 | 0 |
| S2 container defs, returns, recursion | 19 | 0 | 17 | 2 | 0 |
| S3 methods and constructors | 23 | 1 | 15 | 7 | 0 |
| out (nested defs, lambdas) | 5 | 1 | 4 | 0 | 0 |
| confidence medium | 14 | 0 | 11 | 3 | 0 |
| confidence low | 38 | 2 | 28 | 8 | 0 |
| confidence high | 0 | | | | |

## Stop rule: fired

fcspec0's stop rule is "fewer than 30 programs fail for a call-site-disagreement reason". Measured:

- **Population.** 905 programs (`lab/census/programs/` 686, `lab/corpus/programs/` 219) plus the 55 pyproof
  rows, traced under CPython. Only 74 have any function reached by two or more argument-kind tuples
  and are not typed; after dropping noise (an empty container's unknown element, a subclass
  receiver) **52** have a real disagreement. That is the whole sample; it cannot reach 60.
- **First reason.** 19 of the 905 fail first with a call-site message (`passing a float to f(),
  whose 'x' is an int64`, `... but the caller also supplies ...`, `gets a bool from some calls and
  a number from others`, `passing X where f() wants Y`). Only 2 of those 19 (`gdev/g14_040.py`,
  `gdev/g18_022.py`) have a real runtime disagreement; the other 17 are an annotation contradicted by a wrong claim, or the front end's
  own generated helpers (`_ail_ctr_new_int`, `_ail_dcv`): inference bugs, not specialisation.
- **Counterfactual.** Cloning every disagreeing top-level def per key in the source (what
  instances would give today's typed path) makes **0** of the 52 typed, and moves the first
  reason of none of them. The same with every def signature unannotated (`select --strip`, what a
  user who never annotates writes): again 0 of 52.
- **Why.** Of 82 disagreeing functions, 30 have more than K = 4 keys and 23 have heterogeneous
  (`mix(...)`) or None-holding containers: genuinely dynamic code (JSON-like trees, `flatten`,
  `describe(value)`), which the general path is right to keep. 29 are clean with at most 4 keys,
  spread over 19 programs, and every one of those 19 has an unrelated first blocker (json types,
  `list[Any]`, `object` annotations, class features). The corpus is also almost fully annotated:
  57 of 1,872 parameters have no annotation.
- **pyproof.** One of 55 rows has a disagreement: `examples/hybrid/fallback_demo.py`'s `triple`,
  called with bigint, bool and float on purpose (the hybrid fallback demo). raytrace, mdlite, nbody
  and tsv_join have none: their blockers are class inference (`Vector__plus never returns a
  value`), a bool/number return of `escape_char()`, an int field given a float, and a
  tuple-or-scalar return. They are fcspec3-adjacent single-key inference, not instancing.

**Owner decision needed:** re-rank `fcspec1`-`fcspec3` (see docs/design/CALLSITE_SPEC.md section 8).

## How the sample was made

```
python3 lab/reach/callsite/census.py select -j 2 -o select.jsonl PROGRAM[=INPUT] ...
python3 lab/reach/callsite/census.py make-sample select.jsonl > lab/reach/callsite/sample.txt
```

Inputs: `lab/census/programs/dev/tNNN.py` and `lab/corpus/programs/*/tNNN.py` read
`lab/corpus/tasks/tNNN/in0.txt` on stdin; `gdev` programs take none; pyproof rows use
`lab/pyproof/programs.txt`. Confidence: **high** = the source-clone counterfactual is typed;
**medium** = the first refusal is a call-site message, or sits inside or at a call of a
disagreeing function; **low** = an unrelated blocker comes first. The compile-only typed attempt
of `select` can disagree with the real build (2 sample rows are typed by the real default build,
through the unified/mixed route); the table below, from real builds, is the baseline.

## Programs

| program | step | conf. | result | first reason (bucket) | first disagreeing function (keys) |
|---|---|---|---|---|---|
| `examples/hybrid/fallback_demo.py` | S1 | low | refused | write instead: keep the value inside intN, or compile with --exact-int | triple(bigint / bool / float / int) |
| `census/dev/t184.py` | S2 | medium | general | json.dumps of value: the type of this value is not known here -- bind  | flatten(None,str,list[str] / bool,str,list[str] / dict[str,float],str,list |
| `census/dev/t452.py` | S3 | low | general | Node.__init__ must take plain positional arguments, no defaults, *args | LinkedList.__init__(list[int] / tuple()) |
| `census/gdev/g01_024.py` | S2 | low | general | json.dumps of tree: the type of this value is not known here -- bind i | insert_nested(dict[str,dict[str,mix(dict / str)]],str,str / dict[str,dict[ |
| `census/gdev/g07_032.py` | S2 | medium | general | 'X' is annotated list[Any], which this compiler has no rule for. write | is_palindrome(list[bool] / list[int] / list[list[int]] / list[mix(float / int /  |
| `census/gdev/g08_006.py` | out | low | general | a records annotation whose field type is 'X'; a row holds intN or floa | main.<locals>.<lambda>(tuple() / tuple(int) / tuple(int,int) / tuple(int,int |
| `census/gdev/g08_014.py` | S2 | low | general | 'X' uses 'X' as a dict of containers -- its values are lists, sets or  | list_simple_paths(dict[str,list[str]],str,str,list[str],list[mix(tuple |
| `census/gdev/g08_020.py` | S2 | low | general | a records annotation whose field type is 'X'; a row holds intN or floa | segment_from(str,set[str],int,dict[int,list[?]] / str,set[str],int,dict[ |
| `census/gdev/g10_016.py` | S1 | medium | general | a method on Call; run with --strict to see why | format_cell(float,int / int,int) |
| `census/gdev/g10_026.py` | out | low | typed |  | find_bridges.<locals>.dfs(str,None / str,int) |
| `census/gdev/g11_034.py` | S3 | low | general | list[list[Creature / None]]: a nested list holds rows of int, float, s | set_cell(list[list[None]],tuple(int,int),cls:Creature / list[list[mix(Cr |
| `census/gdev/g13_000.py` | S3 | low | general | dunder method Shape.__repr__; only __init__ is supported here, no othe | Rectangle.__init__(float,int / int,int) |
| `census/gdev/g13_002.py` | S3 | low | refused | KeyError: 'X' | Vehicle.__init__(None,None / None,float / int,float) |
| `census/gdev/g13_008.py` | S3 | low | general | a decorator on Matrix.shape (classmethod, staticmethod, property, or a | Matrix.__init__(list[list[float]] / list[list[int]]) |
| `census/gdev/g13_018.py` | S3 | low | general | Subject.notify must take plain positional arguments, no defaults, *arg | Subject.attach(cls:CounterObserver / cls:LoggingObserver) |
| `census/gdev/g13_022.py` | S3 | low | refused | not in the subset: class 'X' has no __init__; its shape (which fields  | check_isinstance(cls:Base,tuple(cls:type,cls:type,cls:type,cls:type) / c |
| `census/gdev/g13_030.py` | S3 | low | general | only a class type can be None: write 'X'; run with --strict to see why | Node.__init__(int,None / str,None) |
| `census/gdev/g13_036.py` | S3 | low | typed |  | Directory.add(cls:Directory / cls:File) |
| `census/gdev/g13_038.py` | S3 | low | general | a format spec on a Decimal in an f-string (__format__ is not built); r | print_inventory_report(cls:Inventory / cls:PerishableItem) |
| `census/gdev/g14_014.py` | S3 | low | general | 'X' is annotated object, which this compiler has no rule for. write in | Matrix2x2.__mul__(cls:Matrix2x2 / int) |
| `census/gdev/g14_016.py` | S3 | low | refused | not in the subset: json.loads(s): the type of the result is not declar | person_from_dict(dict[str,mix(dict[str,str] / int / list[str] / str)] / dict[s |
| `census/gdev/g14_026.py` | S3 | low | general | inheritance from 'X' (class 'X'); a class here may only derive from a  | Stack.push(int / str) |
| `census/gdev/g14_038.py` | S3 | medium | refused | not in the subset: 'X' is annotated object, which this compiler has no | shallow_size(cls:PlainDataPoint / cls:RegularPoint / cls:SlottedDataPoint) |
| `census/gdev/g14_040.py` | S3 | medium | refused | not in the subset: parameter 'X' of _ail_dcv() gets a bool from some c | from_dict(cls:type,dict[str,bool] / cls:type,dict[str,int] / cls:type,dict |
| `census/gdev/g15_006.py` | S2 | medium | general | only a class type can be None: write 'X'; run with --strict to see why | validate_age(None,int,int / bool,int,int / float,int,int / int,int,int / list[ |
| `census/gdev/g15_026.py` | S1 | low | refused | write instead: keep the value inside intN, or compile with --exact-int | safe_divide(None,int / bigint,bigint / float,float / int,float / int,int / int,s |
| `census/gdev/g15_028.py` | S3 | low | refused | not in the subset: import of 'X' is not available: this compiler build | run_scenario(str,None,cls:ReleaseLog / str,str,cls:ReleaseLog) |
| `census/gdev/g15_032.py` | S3 | low | general | 'X' is annotated callable, which this compiler has no rule for. write  | run_transfer(cls:Bank,str,str,int,None / cls:Bank,str,str,int,int) |
| `census/gdev/g16_004.py` | S2 | low | general | 'X' mixes bools and numbers; Python keeps each value's own type and a  | flatten(list[int] / list[list[float]] / list[list[mix(int / list)]] / list[mix |
| `census/gdev/g16_036.py` | S2 | medium | general | 'X' is annotated Tree, which this compiler has no rule for. write inst | inorder(None / tuple(None,int,None) / tuple(tuple(None,int,None),int,tuple |
| `census/gdev/g17_004.py` | S1 | low | general | functools.partial used here is not built: reduce, lru_cache / cache an | scale(float,float / float,int / int,float / int,int) |
| `census/gdev/g17_018.py` | S2 | low | refused | write instead: give each function its own name and call the right one  | _(list[int] / list[mix(float / int / str)]) |
| `census/gdev/g17_022.py` | out | medium | general | 'X' is annotated list[Any], which this compiler has no rule for. write | flatten(list[int] / list[list[list]] / list[list[mix(int / list)]] / list[mix( |
| `census/gdev/g17_024.py` | S1 | low | general | functools.partial used here is not built: reduce, lru_cache / cache an | power(float,float / float,int) |
| `census/gdev/g17_028.py` | out | low | general | 'X' mixes bools and numbers; Python keeps each value's own type and a  | filter_records.<locals>.<lambda>(dict[str,mix(None / int / str)] / dict[str, |
| `census/gdev/g18_022.py` | S3 | medium | general | parameter 'X' of Employee() gets a bool from some calls and a number f | describe(cls:Employee / cls:Point) |
| `census/gdev/g21_010.py` | S3 | low | general | json.loads(s): the type of the result is not declared here; write the  | count_leaves(None / bool / dict[str,mix(None / bool / dict[?,?] / int / list[?] / li |
| `census/gdev/g21_012.py` | out | medium | general | json.dumps of value: the type of this value is not known here -- bind  | main.<locals>.<lambda>(tuple(str,None) / tuple(str,bool) / tuple(str,dict[ |
| `census/gdev/g21_016.py` | S2 | low | general | json.dumps of rounded: the type of this value is not known here -- bin | round_floats(dict[str,mix(dict[str,mix(float / list)] / dict[str,mix(float |
| `census/gdev/g21_020.py` | S2 | medium | general | json.loads(s): the type of the result is not declared here; write the  | describe(str,None / str,bool / str,dict[str,dict[str,int]] / str,list[int] / s |
| `census/gdev/g21_024.py` | S2 | low | general | json.dumps of records: the type of this value is not known here -- bin | flatten(None,str,str / bool,str,str / dict[str,int],str,str / dict[str,mix(N |
| `census/gdev/g21_026.py` | S2 | low | general | json.dumps of serializable: the type of this value is not known here - | prepare_for_json(dict[str,bytes] / dict[str,mix(bool / bytes / dict[str,byte |
| `census/gdev/g21_034.py` | S2 | low | general | json.dumps of operations: the type of this value is not known here --  | make_patch(bool,int,str,list[dict[str,mix(dict / str)]] / dict[str,mix(boo |
| `census/gdev/g21_036.py` | S3 | low | general | json.dumps(..., default=...) is not built (built: indent, sort_keys, s | Employee.__init__(str,cls:date,list[str],None / str,cls:date,list[str],c |
| `census/gdev/g22_012.py` | S3 | low | refused | write instead: keep the value inside intN, or compile with --exact-int | BitSet64.__init__(None / list[int]) |
| `census/gdev/g25_008.py` | S2 | low | general | 'X' is a module-level list of non-numbers; only an int/float/str/bytes | to_string(int / tuple(str,int) / tuple(str,int,int) / tuple(str,int,tuple(st |
| `census/gdev/g25_020.py` | S2 | low | general | 'X' is a module-level list of non-numbers; only an int/float/str/bytes | record(dict[str,cls:Summary],dict[str,mix(bool / str)] / dict[str,cls:Summ |
| `census/gdev/g25_024.py` | S3 | medium | general | 'X' is annotated Circle / Rectangle / Square / Triangle / Ellipse, whi | area(cls:Circle / cls:Ellipse / cls:Rectangle / cls:Square / cls:Triangle) |
| `census/gdev/g25_028.py` | S3 | low | general | 'X' is a module-level list of non-numbers; only an int/float/str/bytes | print_linear_section(str,cls:EnumType,list[tuple(float,Length)] / str,cl |
| `corpus/deepseek-v4.1-flash-free/t184.py` | S2 | medium | general | json.dumps of value: the type of this value is not known here -- bind  | flatten(None,str,list[str] / bool,str,list[str] / dict[str,float],str,list |
| `corpus/deepseek-v4.1-flash-free/t447.py` | S2 | medium | refused | not in the subset: 'X' is annotated Observers, which this compiler has | register(dict[str,list[function]],str,fn / dict[str,mix(list[?] / list[fun |
| `corpus/glm-5.3-flash-free/t184.py` | S2 | low | general | json.loads(s): the type of the result is not declared here; write the  | flatten(None,str / bool,str / dict[str,float],str / dict[str,mix(bool / str)], |
