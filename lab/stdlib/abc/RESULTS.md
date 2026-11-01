# abc: real-program coverage

Twelve programs in this directory use `abc` the way ordinary code does: `ABC`, `ABCMeta`,
`abstractmethod`, `abstractclassmethod`, `abstractstaticmethod`, `abstractproperty`,
`get_cache_token`, ordinary subclasses and partially implemented subclasses. They are 26-51 lines
each and are built with

    AIL_CURRENT/ail_chatgpt.py compile <file>.py --syntax python

## Result

Nine of the twelve build and match CPython 3.12 stdout and exit code on both `AIL_IR=0` and
`AIL_IR=1`. All nine are built on the **general** path: the abstractness guard is Python source
added to the program, and the typed path declines it (the default build falls back to the general
runtime).

| # | program | final result | CPython stdout + exit |
| --- | --- | --- | --- |
| 1 | `abstract_instantiation.py` | general | match (incomplete classes raise `TypeError`, complete class runs) |
| 2 | `animal.py` | general | match |
| 3 | `cache_token.py` | general | match (token type and stability) |
| 4 | `codec.py` | general | match (`abstractstaticmethod`, `abstractclassmethod`, `abstractproperty`) |
| 5 | `metaclass_abcm.py` | general | match |
| 6 | `notifications.py` | general | match |
| 7 | `payment.py` | general | match |
| 8 | `plugin_registry.py` | general | match |
| 9 | `shapes.py` | general | match |
| 10 | `subclasshook.py` | refused | follow-up (see below) |
| 11 | `update_abstractmethods.py` | refused | follow-up (see below) |
| 12 | `virtual_subclass.py` | refused | follow-up (see below) |

The first build of these programs had 6 matching, 1 built with different stdout and 5 refused:

| program | first result | first message / difference |
| --- | --- | --- |
| `abstract_instantiation.py` | general, stdout differed | CPython raises `TypeError: Can't instantiate abstract class Shape ...`; the base class was instantiated (`Shape built None None`) and the incomplete subclass said `Square() takes other arguments` |
| `animal.py` | typed, match | |
| `cache_token.py` | refused | `not in the subset: a non-name base class in class Visitor` (and `abc.get_cache_token used here is not built`) |
| `codec.py` | refused | `not in the subset: class Codec bases on ABC, defined after it or unknown` (and `abc.abstractstaticmethod is not built`) |
| `metaclass_abcm.py` | general, match | |
| `notifications.py` | typed, match | |
| `payment.py` | typed, match | |
| `plugin_registry.py` | general, match | |
| `shapes.py` | typed, match | |
| `subclasshook.py` | refused | `not in the subset: the name 'issubclass' is not a known function/class/builtin` |
| `update_abstractmethods.py` | refused | `not in the subset: class Job bases on ABC, defined after it or unknown` (and `abc.update_abstractmethods is not built`) |
| `virtual_subclass.py` | refused | `not in the subset: the method .register() (on a value of unknown static kind)` |

## Fixes

* `python/pkg-v12/smalllib5.py`: the `abc` pass now accepts the deprecated abstract decorators
  (`abstractclassmethod`, `abstractstaticmethod`, `abstractproperty`) as well as `abstractmethod`,
  handles `abc.ABC` as a base and `metaclass=abc.ABCMeta`, and works out which abstract methods
  each class in the hierarchy still has to implement. It strips the abstractness and adds a marker
  method plus a generated `_ail_abc_check_name`, which raises CPython 3.12's exact
  `Can't instantiate abstract class ...` text with the method names sorted. A class with no ABC
  ancestor is untouched, so `@abstractmethod` on a plain class still does nothing, as in CPython.
* `python/pkg-v12/pyboxed2.py`, `python/pkg-v12/boxclosure.py`: the guard runs before the
  constructor binds arguments for both a direct class call and a class held in a value. CPython
  checks abstractness before argument binding, so `Incomplete()` and `Incomplete(1, 2, 3, 4)` both
  report the abstract-class `TypeError` rather than an arity error.
* `python/pkg-v12/smalllib5.py`: `abc.get_cache_token()` is built as a stable `int` (`0`). Programs
  that compare the token around ordinary code match CPython; the absolute value and the change on
  `register()` are not modelled (the latter is part of the `register` follow-up).

## Follow-ups

* `virtual_subclass.py` -- `ABC.register` / virtual subclasses, and `issubclass` over them. Exact
  refusal: `not in the subset: the method .register() (on a value of unknown static kind)`.
* `subclasshook.py` -- `__subclasshook__` needs the `issubclass` builtin and the `__mro__` /
  `__dict__` structures. Exact refusal:
  `not in the subset: the name 'issubclass' is not a known function/class/builtin`.
* `update_abstractmethods.py` -- `abc.update_abstractmethods` (including assigning the missing
  method after the class body). Exact refusal:
  `not in the subset: class Job bases on ABC, defined after it or unknown`, with the note
  `abc.update_abstractmethods is not built: ...` .
* `get_cache_token` returns `0` and does not change after `register()`; only its type and stability
  are modelled.

## Verification

`test_ail_std_abc.py` builds the nine passing programs on both `AIL_IR` modes and compares stdout
and exit code with CPython. Probes in `/tmp/probes/abc_probe_*.py` cover single, multiple (sorted),
inherited, overridden, property/static/class abstract methods, `abc.ABC`/`abc.ABCMeta` attribute
forms, empty ABCs, wrong arities, and classes reached as an alias, a list item, a dict value, an
attribute and a function argument. The ten `lab/compare` tasks were rebuilt with the base and the
changed compiler: the six that build are byte-identical; the other four fail identically on both.
