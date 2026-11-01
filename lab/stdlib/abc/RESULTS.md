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
| 3 | `cache_token.py` | general | match (exact positive token, stable) |
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
  each class in the hierarchy still has to implement. A metaclass that is a subclass of `ABCMeta`
  (`class Meta(ABCMeta)`, `metaclass=Meta`) is recognised too, so its users get the same
  abstractness. It strips the abstractness and adds a marker method plus a generated
  `_ail_abc_check_name`, which raises CPython 3.12's exact
  `Can't instantiate abstract class ...` text with the method names sorted.
* `python/pkg-v12/smalllib5.py`: only a class with ABC ancestry (`ABC`/`ABCMeta` or an ABC base)
  gets abstractness. `@abstractmethod` on a plain class still does nothing, and a plain subclass of
  such a class is instantiable, as in CPython. An abstract name inherited through the MRO is
  dropped when the class resolves it to a concrete mixin definition, and an override written as a
  plain assignment (`m = 5`, `m = lambda self: 7`) counts as an implementation just like a `def`.
  A function-valued class attribute in an ABC hierarchy is given to the method dispatcher as a
  real method, so `B().m()` calls it.
* `python/pkg-v12/pyboxed2.py`, `python/pkg-v12/boxclosure.py`: the guard runs after
  `object.__new__`'s own no-`__init__` argument check and before a custom `__init__` binds its
  arguments, for a direct class call and for a class held in a value. `Incomplete(1, 2, 3, 4)`
  therefore reports the abstract-class `TypeError` when a custom `__init__` exists, and
  `Shape(1)` with no `__init__` reports `Shape() takes no arguments`, both as CPython does.
  Only a class's OWN guard always raises: a concrete subclass that merely inherits the guard no
  longer has its constructor binding errors swallowed. Those errors are a named compile refusal
  on the general path (`not in the subset: B() called without a required argument x`), never a
  silently constructed object.
* `python/pkg-v12/smalllib5.py`: `abc.get_cache_token()` returns CPython's own starting token,
  read from a fresh interpreter of the same build at compile time (a positive `int` that stays
  constant for the supported subset, because `register()`/`update_abstractmethods()` -- the only
  operations that invalidate it -- are refused by name).

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
* Multiple inheritance (a concrete mixin before an ABC, or a diamond): the general path still
  refuses it by name. Exact refusal: `not in the subset: multiple inheritance in class C`.
* A class definition nested inside a function: exact refusal
  `not in the subset: a nested class definition (Local)`.
* A module-level alias used as a base (`Base = Shape; class Sq(Base)`): exact refusal
  `not in the subset: class Sq bases on Base, defined after it or unknown`.
* A starred call argument to a class (`Shape(*args)`): exact refusal
  `not in the subset: a starred (*args) call argument ...`.
* Pre-existing general-path value display, not part of this change: a default object `repr` omits
  the `__main__.` prefix and address (`<Good object>` vs `<__main__.Good object at 0x...>`), and
  reading an inherited method as a value (`Child().m` without calling it) is not built.

## Verification

`test_ail_std_abc.py` builds the nine passing programs on both `AIL_IR` modes and compares stdout
and exit code with CPython. It also has review-regression sources for plain (non-ABC) inheritance,
an assignment/lambda override of an abstract method, the no-`__init__` versus custom-`__init__`
guard ordering, an `ABCMeta` subclass used as a metaclass, and the exact cache-token value; a
concrete subclass's arity error is asserted to be a named refusal. Probes in `/tmp/probes/` and
`/tmp/rprobes2/{arity_concrete,arity_custom_own_init,routes_arity,cache_value,meta_sub}.py` cover
sorted messages, inheritance, overrides, all abstract decorators, attribute spellings, empty ABCs,
wrong arities, and classes reached as an alias, a list item, a dict value and a function argument,
on both `cmp.sh` builds. The ten `lab/compare` tasks were rebuilt with the base tree and the changed
compiler: the five that build are byte-identical; the other five fail identically on both.
