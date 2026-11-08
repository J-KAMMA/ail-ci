#!/usr/bin/env python3
"""Run-time kind recorder for the observed-types hybrid (job obs1).

    python3 ail_observe.py run [-o profile.json] [--all] [--full] [--fast] [--exact-time]
                               SCRIPT [ARGS...]
    python3 ail_observe.py run [-o profile.json] -m MODULE [ARGS...]
    python3 ail_observe.py annotate PROFILE SOURCE.py [-o OUT.py] [--strip] [--decisions F]
    python3 ail_observe.py strip SOURCE.py [-o OUT.py]

`run` executes a program once under CPython and writes a JSON profile.  Per Python function it
records the call count, the self time (the function's own time, children excluded; time spent in
C builtins it calls counts as its own, unlike cProfile), the kinds of its arguments and of the
values it returns or yields, and how often it left by an exception.

Self time comes from a SIGPROF sampler (1 ms of CPU time per tick, charged to the innermost
recorded frame, scaled to wall time); `--exact-time` times every call on a shadow stack instead
(slower; also the `sys.setprofile` fallback).  Call counts are exact by default, which costs one
Python callback per call (measured 1.0-6.0x instructions on lab/wedge, geomean 1.43x); `--fast`
stops counting a function once its sample budget is spent and re-arms every 0.25 s, so `calls`
becomes a lower bound and the overhead drops to ~1.04x.

A kind is the annotation spelling of a value: `int`, `float`, `bool`, `str`, `bytes`, `None`,
`list[int]`, `dict[str, int]`, `tuple[int, str]`, `tuple[int, ...]`, `set[str]`; a value of a
user class is `cls:<module>.<qualname>`.  Container elements are SAMPLED, never fully scanned: a
list or tuple looks at most at 8 elements (first, last and evenly spaced ones), a dict or set at
its first 4 items.  Mixed elements give a union (`list[int|str]`); an empty container gives
`list[?]`.  An int outside int64 is still `int`, and the parameter's `big` counter is raised.

Argument kinds are recorded for the first 1024 calls of a function and then on every 64th call;
return and yield kinds for the first 1024 returns of a function, after which that return site is
disabled and re-armed with 16 more samples every 0.25 s; `--full` records every call.  A kind seen
only between samples can be missed, so a profile is a hint for selection, never a proof: native
code built from it must check its inputs.  By default only code whose
file lies under the script's directory is recorded (stdlib and site-packages calls count as the
caller's own time); `--all` records every Python function.

`annotate` writes a copy of a module in which every parameter and return observed with exactly
one expressible kind gets that kind as an annotation.  Existing annotations are kept unless
`--strip` first removes all of them (the "untyped Python" view).  It changes only the annotation
text; every other byte of the module stays where it was.

The recorder uses `sys.monitoring` (Python 3.12+) and falls back to `sys.setprofile` before that.
"""
import ast
import io
import itertools
import json
import os
import runpy
import sys
import time
import tokenize

SCHEMA = 'ail.observe/1'
FULL_CALLS = 1024          # record kinds for every call up to this count ...
SAMPLE_EVERY = 64          # ... then on every Nth call
TICK_S = 0.001             # SIGPROF sampler period (CPU seconds)
REARM_S = 0.25             # re-arm disabled return/yield sites this often
REARM_BUDGET = 16          # return/yield samples per site per re-arm
SEQ_SAMPLE = 8             # elements looked at in a list/tuple
MAP_SAMPLE = 4             # items looked at in a dict/set
MAX_DEPTH = 3              # container nesting followed
MAX_KINDS = 8              # distinct kinds kept per slot; more is "megamorphic"
INT64_MIN, INT64_MAX = -(1 << 63), (1 << 63) - 1
MEGA = '<megamorphic>'
_SCALARS = {int: 'int', float: 'float', bool: 'bool', str: 'str', bytes: 'bytes',
            type(None): 'None', complex: 'complex', bytearray: 'bytearray'}


# ---------------------------------------------------------------------------------------------
# kinds

def _union(kinds):
    kinds = sorted(set(kinds))
    if not kinds:
        return '?'
    return '|'.join(kinds)


def _seq_sample(seq):
    n = len(seq)
    if n <= SEQ_SAMPLE:
        return list(seq)
    step = (n - 1) / (SEQ_SAMPLE - 1)
    return [seq[int(round(i * step))] for i in range(SEQ_SAMPLE)]


def kind_of(value, depth=0):
    """The annotation-style kind of `value`, sampling container elements."""
    t = type(value)
    s = _SCALARS.get(t)
    if s is not None:
        return s
    if depth >= MAX_DEPTH and t in (list, tuple, dict, set, frozenset):
        return t.__name__
    try:
        if t is list:
            return 'list[%s]' % _union(kind_of(v, depth + 1) for v in _seq_sample(value))
        if t is tuple:
            if len(value) <= SEQ_SAMPLE:
                if not value:
                    return 'tuple[()]'
                return 'tuple[%s]' % ', '.join(kind_of(v, depth + 1) for v in value)
            return 'tuple[%s, ...]' % _union(kind_of(v, depth + 1) for v in _seq_sample(value))
        if t is dict:
            items = list(itertools.islice(value.items(), MAP_SAMPLE))
            if not items:
                return 'dict[?, ?]'
            return 'dict[%s, %s]' % (_union(kind_of(k, depth + 1) for k, _ in items),
                                     _union(kind_of(v, depth + 1) for _, v in items))
        if t is set or t is frozenset:
            items = list(itertools.islice(value, MAP_SAMPLE))
            return '%s[%s]' % (t.__name__, _union(kind_of(v, depth + 1) for v in items))
    except Exception:                       # a container mutated under us, or a weird __len__
        return t.__name__
    mod = getattr(t, '__module__', '?')
    if mod == 'builtins':
        return t.__name__
    return 'cls:%s.%s' % (mod, getattr(t, '__qualname__', t.__name__))


def _is_big(value):
    return type(value) is int and not (INT64_MIN <= value <= INT64_MAX)


# ---------------------------------------------------------------------------------------------
# the recorder

class _Fn:
    __slots__ = ('code', 'calls', 'sampled', 'self_ns', 'ticks', 'raised', 'params', 'big',
                 'returns', 'yields', 'nparams', 'names', 'varargs', 'varkw', 'rsamp', 'rbudget',
                 'cbudget')

    def __init__(self, code):
        self.code = code
        self.calls = 0
        self.sampled = 0
        self.self_ns = 0
        self.ticks = 0
        self.raised = 0
        self.rsamp = 0
        self.rbudget = FULL_CALLS
        self.cbudget = FULL_CALLS
        flags = code.co_flags
        n = code.co_argcount + code.co_kwonlyargcount
        self.varargs = bool(flags & 0x04)
        self.varkw = bool(flags & 0x08)
        self.nparams = n + self.varargs + self.varkw
        self.names = code.co_varnames[:self.nparams]
        self.params = [dict() for _ in range(self.nparams)]
        self.big = [0] * self.nparams
        self.returns = {}
        self.yields = {}


def _bump(counter, kind):
    if kind in counter:
        counter[kind] += 1
    elif len(counter) < MAX_KINDS:
        counter[kind] = 1
    else:
        counter[MEGA] = counter.get(MEGA, 0) + 1


class Recorder:
    """Collects the profile.  `keep(code)` decides which code objects are recorded.

    timing='sample' (default with sys.monitoring): self time comes from a SIGPROF stack sampler
    (one tick per `TICK_S` of CPU time, charged to the innermost recorded frame), and the per-call
    work is a counter; return and yield kinds are recorded at each site until a budget is spent,
    then that site's event is disabled and re-armed with a small budget every `REARM_S`.
    timing='exact': every call and return is timed on a shadow stack (slower, exact)."""

    def __init__(self, keep=None, full=False, timing='sample', fast=False):
        self.keep = keep or (lambda code: True)
        self.fast = fast and not full and timing == 'sample'
        self.full = full
        self.timing = timing
        self.fns = {}           # code -> _Fn
        self.skip = set()       # code objects not recorded
        self.stack = []         # exact timing: [fn, start_ns, child_ns]
        self.clock = time.perf_counter_ns
        self.wall_s = 0.0
        self.tool = None
        self.total_ticks = 0
        self.lost_ticks = 0

    def _fn(self, code):
        fn = self.fns.get(code)
        if fn is None:
            if code in self.skip:
                return None
            if not self.keep(code):
                self.skip.add(code)
                return None
            fn = self.fns[code] = _Fn(code)
        return fn

    def _sample_args(self, fn, frame):
        loc = frame.f_locals
        for i, name in enumerate(fn.names):
            if name in loc:
                v = loc[name]
                _bump(fn.params[i], kind_of(v))
                if type(v) is int and _is_big(v):
                    fn.big[i] += 1

    def _leave(self, fn, now):
        stack = self.stack
        while stack:
            top = stack.pop()
            elapsed = now - top[1]
            top[0].self_ns += elapsed - top[2]
            if stack:
                stack[-1][2] += elapsed
            if top[0] is fn:
                return True
        return False

    def report(self):
        out = {}
        sampled_time = self.timing == 'sample' and self.tool == 'sys.monitoring'
        for code, fn in self.fns.items():
            qual = getattr(code, 'co_qualname', code.co_name)
            key = '%s:%s:%d' % (code.co_filename, qual, code.co_firstlineno)
            params = []
            for i, name in enumerate(fn.names):
                star = ''
                if fn.varargs and i == fn.nparams - 1 - fn.varkw:
                    star = '*'
                if fn.varkw and i == fn.nparams - 1:
                    star = '**'
                params.append({'name': name, 'star': star, 'kinds': fn.params[i],
                               'big': fn.big[i]})
            if sampled_time:
                self_s = fn.ticks * self.wall_s / self.total_ticks if self.total_ticks else 0.0
            else:
                self_s = fn.self_ns / 1e9
            out[key] = {
                'file': code.co_filename, 'qualname': qual, 'name': code.co_name,
                'line': code.co_firstlineno, 'calls': fn.calls, 'sampled_calls': fn.sampled,
                'self_s': round(self_s, 6), 'ticks': fn.ticks, 'raised': fn.raised,
                'generator': bool(code.co_flags & (0x20 | 0x80 | 0x200)),
                'params': params, 'returns': fn.returns, 'yields': fn.yields,
            }
        return {'schema': SCHEMA, 'python': sys.version.split()[0], 'tool': self.tool,
                'timing': 'sample' if sampled_time else 'exact',
                'calls_exact': not self.fast,
                'tick_s': TICK_S if sampled_time else None,
                'ticks': self.total_ticks, 'unattributed_ticks': self.lost_ticks,
                'wall_s': round(self.wall_s, 6), 'full': self.full,
                'sampling': {'full_calls': FULL_CALLS, 'sample_every': SAMPLE_EVERY,
                             'seq_sample': SEQ_SAMPLE, 'map_sample': MAP_SAMPLE,
                             'rearm_s': REARM_S, 'rearm_budget': REARM_BUDGET},
                'functions': out}

    # -- sys.monitoring (3.12+) ---------------------------------------------------------------
    def _start_monitoring(self):
        mon = sys.monitoring
        tool = None
        for cand in (mon.PROFILER_ID, 4, 5):
            if mon.get_tool(cand) is None:
                tool = cand
                break
        if tool is None:
            return False
        mon.use_tool_id(tool, 'ail_observe')
        self._tool_id = tool
        ev = mon.events
        disable = mon.DISABLE
        getframe = sys._getframe
        fns = self.fns
        full = self.full
        sample_args = self._sample_args
        lookup = self._fn
        exact = self.timing == 'exact'
        clock = self.clock
        stack = self.stack
        fast = self.fast

        def py_start(code, offset):
            fn = fns.get(code)
            if fn is None:
                fn = lookup(code)
                if fn is None:
                    return disable
            n = fn.calls = fn.calls + 1
            if fast:
                if n > fn.cbudget:
                    return disable
                fn.sampled += 1
                sample_args(fn, getframe(1))
                return None
            if full or n <= FULL_CALLS or not n % SAMPLE_EVERY:
                fn.sampled += 1
                sample_args(fn, getframe(1))
            if exact:
                stack.append([fn, clock(), 0])

        def py_resume(code, offset):
            fn = fns.get(code)
            if fn is None:
                return disable
            stack.append([fn, clock(), 0])

        def _ret(code, value, which):
            fn = fns.get(code)
            if fn is None:
                return disable
            if exact:
                self._leave(fn, clock())
            r = fn.rsamp = fn.rsamp + 1
            if full or r <= fn.rbudget:
                _bump(fn.yields if which else fn.returns, kind_of(value))
                return None
            if exact:
                return None
            return disable

        def py_return(code, offset, value):
            return _ret(code, value, 0)

        def py_yield(code, offset, value):
            return _ret(code, value, 1)

        def py_unwind(code, offset, exc):
            fn = fns.get(code)
            if fn is not None:
                fn.raised += 1
                if exact:
                    self._leave(fn, clock())

        mon.register_callback(tool, ev.PY_START, py_start)
        mon.register_callback(tool, ev.PY_RETURN, py_return)
        mon.register_callback(tool, ev.PY_YIELD, py_yield)
        mon.register_callback(tool, ev.PY_UNWIND, py_unwind)
        events = ev.PY_START | ev.PY_RETURN | ev.PY_YIELD | ev.PY_UNWIND
        if exact:
            mon.register_callback(tool, ev.PY_RESUME, py_resume)
            events |= ev.PY_RESUME
        mon.set_events(tool, events)
        self.tool = 'sys.monitoring'
        if not exact and not self._start_sampler():
            self.timing = 'exact-unavailable'
        return True

    def _start_sampler(self):
        import signal
        if not hasattr(signal, 'setitimer') or not hasattr(signal, 'SIGPROF'):
            return False
        fns = self.fns
        rearm_every = max(1, int(REARM_S / TICK_S))
        mon = sys.monitoring

        def on_tick(signum, frame):
            self.total_ticks += 1
            f = frame
            while f is not None:
                fn = fns.get(f.f_code)
                if fn is not None:
                    fn.ticks += 1
                    break
                f = f.f_back
            else:
                self.lost_ticks += 1
            if not self.total_ticks % rearm_every:
                for fn in fns.values():
                    fn.rbudget = fn.rsamp + REARM_BUDGET
                    fn.cbudget = fn.calls + REARM_BUDGET
                mon.restart_events()

        self._old_handler = signal.signal(signal.SIGPROF, on_tick)
        signal.setitimer(signal.ITIMER_PROF, TICK_S, TICK_S)
        self._sampler = True
        return True

    def _stop_monitoring(self):
        if getattr(self, '_sampler', False):
            import signal
            signal.setitimer(signal.ITIMER_PROF, 0, 0)
            signal.signal(signal.SIGPROF, self._old_handler or signal.SIG_DFL)
        mon = sys.monitoring
        tool = self._tool_id
        mon.set_events(tool, 0)
        for e in (mon.events.PY_START, mon.events.PY_RESUME, mon.events.PY_RETURN,
                  mon.events.PY_YIELD, mon.events.PY_UNWIND):
            mon.register_callback(tool, e, None)
        mon.free_tool_id(tool)

    # -- sys.setprofile fallback (exact timing) -----------------------------------------------
    def _profile_hook(self, frame, event, arg):
        if event == 'call':
            code = frame.f_code
            fn = self.fns.get(code) or self._fn(code)
            if fn is None:
                return
            is_resume = bool(code.co_flags & (0x20 | 0x80 | 0x200)) and frame.f_lasti > 0
            if not is_resume:
                n = fn.calls = fn.calls + 1
                if self.full or n <= FULL_CALLS or not n % SAMPLE_EVERY:
                    fn.sampled += 1
                    self._sample_args(fn, frame)
            self.stack.append([fn, self.clock(), 0])
        elif event == 'return':
            fn = self.fns.get(frame.f_code)
            if fn is None:
                return
            now = self.clock()
            if self._leave(fn, now):
                fn.rsamp += 1
                if self.full or fn.rsamp <= FULL_CALLS or not fn.rsamp % SAMPLE_EVERY:
                    gen = frame.f_code.co_flags & (0x20 | 0x80 | 0x200)
                    _bump(fn.yields if gen else fn.returns, kind_of(arg))
            if self.stack:
                self.stack[-1][1] += self.clock() - now

    def start(self):
        self._t0 = time.perf_counter()
        if not (hasattr(sys, 'monitoring') and self._start_monitoring()):
            self.tool = 'sys.setprofile'
            self.timing = 'exact'
            sys.setprofile(self._profile_hook)

    def stop(self):
        if self.tool == 'sys.monitoring':
            self._stop_monitoring()
        else:
            sys.setprofile(None)
        now = self.clock()
        while self.stack:                      # frames still open (SystemExit, os._exit paths)
            self._leave(self.stack[-1][0], now)
        self.wall_s = time.perf_counter() - self._t0


def _under(root):
    root = os.path.realpath(root)
    me = os.path.realpath(__file__)
    cache = {}

    def keep(code):
        fn = code.co_filename
        r = cache.get(fn)
        if r is None:
            if fn.startswith('<'):
                r = False
            else:
                p = os.path.realpath(fn)
                r = p != me and (p == root or p.startswith(root + os.sep))
            cache[fn] = r
        return r
    return keep


def observe(target, argv=(), module=False, out=None, all_code=False, full=False,
            timing='sample', fast=False):
    """Run `target` (a script path, or a module name with `module=True`) and return the profile."""
    if module:
        root = os.getcwd()
    else:
        root = os.path.dirname(os.path.abspath(target))
    rec = Recorder(keep=None if all_code else _under(root), full=full, timing=timing, fast=fast)
    saved_argv, saved_path = sys.argv[:], sys.path[:]
    sys.argv = [target] + list(argv)
    if not module:
        sys.path.insert(0, root)
    status = 0
    rec.start()
    try:
        if module:
            runpy.run_module(target, run_name='__main__', alter_sys=True)
        else:
            runpy.run_path(target, run_name='__main__')
    except SystemExit as e:
        status = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        rec.stop()
        sys.argv, sys.path[:] = saved_argv, saved_path
    data = rec.report()
    data['target'] = target
    data['exit'] = status
    if out:
        with open(out, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=1, sort_keys=True)
            handle.write('\n')
    return data


# ---------------------------------------------------------------------------------------------
# profile -> annotations

_EXPRESSIBLE = ('int', 'float', 'bool', 'str', 'bytes', 'None', 'complex', 'bytearray')


def merge_kinds(counter):
    """The kinds of one slot after folding empty containers into a typed sibling."""
    kinds = set(counter)
    for k in list(kinds):
        if '?' in k:
            stem = k.split('[', 1)[0]
            if any(o != k and o.split('[', 1)[0] == stem and '?' not in o for o in kinds):
                kinds.discard(k)
    return kinds


def expressible(kind):
    """True when `kind` is a valid annotation in any module namespace (builtins only)."""
    if kind in _EXPRESSIBLE:
        return True
    if kind.startswith('cls:') or '?' in kind or '|' in kind or MEGA in kind:
        return False
    try:
        node = ast.parse(kind, mode='eval').body
    except SyntaxError:
        return False
    ok = {'int', 'float', 'bool', 'str', 'bytes', 'None', 'list', 'dict', 'tuple', 'set',
          'frozenset', 'complex', 'bytearray'}
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id not in ok:
            return False
        if isinstance(n, ast.Constant) and n.value not in (None, Ellipsis):
            return False
    return True


def slot_verdict(counter):
    """('mono', kind) | ('poly', kinds) | ('unexpressible', kind) | ('unseen', None)."""
    if not counter:
        return 'unseen', None
    kinds = merge_kinds(counter)
    if MEGA in kinds or len(kinds) > 1:
        return 'poly', sorted(kinds)
    kind = next(iter(kinds))
    if not expressible(kind):
        return 'unexpressible', kind
    return 'mono', kind


def functions_for(profile, source_path):
    """Profile entries whose code came from `source_path`, keyed by qualname."""
    want = os.path.realpath(source_path)
    base = os.path.basename(source_path)
    rows = {}
    for rec in profile.get('functions', {}).values():
        f = rec.get('file') or ''
        if os.path.realpath(f) == want or (not os.path.exists(f) and os.path.basename(f) == base):
            rows[rec['qualname']] = rec
    return rows


class _Offsets:
    def __init__(self, text):
        self.text = text
        self.lines = text.splitlines(keepends=True)
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line))

    def at(self, lineno, col_bytes):
        line = self.lines[lineno - 1]
        return self.starts[lineno - 1] + len(line.encode('utf-8')[:col_bytes].decode('utf-8',
                                                                                     'replace'))


def _def_nodes(tree):
    """{qualname: FunctionDef} for every def, with CPython's qualname spelling."""
    out = {}

    def walk(body, prefix):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = prefix + node.name
                out[q] = node
                walk(node.body, q + '.<locals>.')
            elif isinstance(node, ast.ClassDef):
                walk(node.body, prefix + node.name + '.')
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for field in ('body', 'orelse', 'finalbody'):
                    walk(getattr(node, field, []) or [], prefix)
                for h in getattr(node, 'handlers', []) or []:
                    walk(h.body, prefix)
    walk(tree.body, '')
    return out


def _header_close(text, offs, node):
    """Character offset just after the `)` that closes a def's parameter list."""
    start = offs.at(node.lineno, node.col_offset)
    body0 = node.body[0]
    stop = offs.at(body0.lineno, body0.col_offset)
    toks = tokenize.generate_tokens(io.StringIO(text[start:stop]).readline)
    depth = 0
    seen_open = False
    sub = _Offsets(text[start:stop])
    try:
        for tok in toks:
            if tok.type == tokenize.OP and tok.string == '(':
                depth += 1
                seen_open = True
            elif tok.type == tokenize.OP and tok.string == ')':
                depth -= 1
                if seen_open and depth == 0:
                    line, col = tok.end
                    return start + sub.starts[line - 1] + col
    except tokenize.TokenError:
        pass
    return None


def strip_edits(text, tree, offs):
    """Edits that remove every parameter, return and variable annotation."""
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
                if arg is not None and arg.annotation is not None:
                    s = offs.at(arg.lineno, arg.col_offset) + len(arg.arg)
                    e = offs.at(arg.annotation.end_lineno, arg.annotation.end_col_offset)
                    edits.append((s, e, ''))
            if node.returns is not None:
                close = _header_close(text, offs, node)
                if close is not None:
                    e = offs.at(node.returns.end_lineno, node.returns.end_col_offset)
                    edits.append((close, e, ''))
        elif isinstance(node, ast.AnnAssign) and node.simple and node.value is not None:
            s = offs.at(node.target.end_lineno, node.target.end_col_offset)
            e = offs.at(node.annotation.end_lineno, node.annotation.end_col_offset)
            edits.append((s, e, ''))
    return edits


def _apply(text, edits):
    for s, e, new in sorted(edits, key=lambda x: (x[0], x[1]), reverse=True):
        text = text[:s] + new + text[e:]
    return text


def strip_source(text):
    tree = ast.parse(text)
    return _apply(text, strip_edits(text, tree, _Offsets(text)))


def annotate_source(text, rows, strip=False):
    """Return (new_text, decisions).  `rows` maps qualname -> profile entry."""
    if strip:
        text = strip_source(text)
    tree = ast.parse(text)
    offs = _Offsets(text)
    defs = _def_nodes(tree)
    edits = []
    decisions = {}
    for qual, node in defs.items():
        rec = rows.get(qual)
        d = decisions[qual] = {'observed': rec is not None, 'params': {}, 'return': None,
                               'added': 0}
        if rec is None:
            continue
        by_name = {p['name']: p for p in rec.get('params') or []}
        a = node.args
        for arg in a.posonlyargs + a.args + a.kwonlyargs:
            p = by_name.get(arg.arg)
            verdict, kind = slot_verdict((p or {}).get('kinds') or {})
            entry = {'verdict': verdict, 'kind': kind, 'big': (p or {}).get('big', 0)}
            if arg.annotation is not None:
                entry['kept'] = ast.unparse(arg.annotation)
            elif verdict == 'mono' and kind != 'None':
                e = offs.at(arg.lineno, arg.col_offset) + len(arg.arg)
                edits.append((e, e, ': ' + kind))
                entry['added'] = kind
                d['added'] += 1
            d['params'][arg.arg] = entry
        if rec.get('generator'):
            d['return'] = {'verdict': 'generator', 'kind': None}
            continue
        verdict, kind = slot_verdict(rec.get('returns') or {})
        entry = {'verdict': verdict, 'kind': kind}
        if node.returns is not None:
            entry['kept'] = ast.unparse(node.returns)
        elif verdict == 'mono':
            close = _header_close(text, offs, node)
            if close is not None:
                edits.append((close, close, ' -> ' + kind))
                entry['added'] = kind
                d['added'] += 1
        d['return'] = entry
    return _apply(text, edits), decisions


# ---------------------------------------------------------------------------------------------
# CLI

def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='ail_observe', description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run', help='run a program once and record kinds and time')
    r.add_argument('-o', '--out', default='observe.json')
    r.add_argument('-m', dest='module', action='store_true', help='TARGET is a module name')
    r.add_argument('--all', action='store_true', help='record stdlib/site code too')
    r.add_argument('--full', action='store_true', help='record kinds on every call')
    r.add_argument('--exact-time', action='store_true',
                   help='time every call on a shadow stack instead of the SIGPROF sampler')
    r.add_argument('--fast', action='store_true',
                   help='stop counting a function after its sample budget (calls = lower bound)')
    r.add_argument('target')
    r.add_argument('args', nargs=argparse.REMAINDER)
    a = sub.add_parser('annotate', help='write a copy annotated with monomorphic kinds')
    a.add_argument('profile')
    a.add_argument('source')
    a.add_argument('-o', '--out')
    a.add_argument('--strip', action='store_true', help='drop existing annotations first')
    a.add_argument('--decisions', help='write the per-slot decisions as JSON here')
    s = sub.add_parser('strip', help='write a copy with every annotation removed')
    s.add_argument('source')
    s.add_argument('-o', '--out')
    args = ap.parse_args(argv)
    if args.cmd == 'run':
        data = observe(args.target, args.args, module=args.module, out=args.out,
                       all_code=args.all, full=args.full,
                       timing='exact' if args.exact_time else 'sample', fast=args.fast)
        sys.stderr.write('ail_observe: %d function(s), %.3f s, wrote %s\n'
                         % (len(data['functions']), data['wall_s'], args.out))
        return data['exit']
    if args.cmd == 'annotate':
        with open(args.profile, encoding='utf-8') as handle:
            profile = json.load(handle)
        with open(args.source, encoding='utf-8') as handle:
            text = handle.read()
        new, decisions = annotate_source(text, functions_for(profile, args.source), args.strip)
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as handle:
                handle.write(new)
        else:
            sys.stdout.write(new)
        if args.decisions:
            with open(args.decisions, 'w', encoding='utf-8') as handle:
                json.dump(decisions, handle, indent=1, sort_keys=True)
        return 0
    with open(args.source, encoding='utf-8') as handle:
        new = strip_source(handle.read())
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as handle:
            handle.write(new)
    else:
        sys.stdout.write(new)
    return 0


if __name__ == '__main__':
    sys.exit(_main())
