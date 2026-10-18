# -*- coding: utf-8 -*-
"""threadlib.py -- stage G12 (threads): `threading`, `queue` and `concurrent.futures.ThreadPoolExecutor`
with CPython's GIL semantics (docs/design/GENERAL_PURPOSE.md s4.6, decision Q9; design note
docs/design/G12_THREADS.md).

Two halves:

  * `rewrite_text(source, notes)` -- a source pass, the first one python_surface runs. It lowers the
    uses of the three modules onto the classes of thread_prelude.py and onto one small generated
    class per callable a thread or an executor runs (`_AilCall_<k>`: the function, the arguments,
    and `call()` / `call1(x)` / `call2(x, y)` that make the call). The general path cannot pass a
    function as a value, so `target=worker, args=(a, b)` becomes `target=_AilCall_1(a, b)` whose
    `call()` is `return worker(self.a0, self.a1)`. `with <lock or executor>:` becomes the
    acquire / try / finally / release CPython runs. The imports are replaced by one marker import,
    `import _ail_threads`.
  * `inject(tree)` -- run by pyboxed2 on the tree it compiles: when the marker is there, it is
    removed and the prelude is added. `refuse_typed(tree, Unsupported)` -- run by the typed path:
    a threaded program is built by the general path only (one runtime, one lock).

A use that is not built is refused by name with a `write instead:` line (a note, and the import stays,
so the build stops with the import refusal and the note). A program that imports none of the three
modules is returned as written, byte for byte.
"""
import ast
import builtins
import copy

MARKER = '_ail_threads'
MODULES = ('threading', 'queue', 'concurrent.futures')

BUILT = ('threading: Thread(target=, args=, kwargs=, name=, daemon=) and subclasses with run(), start, join, '
         'is_alive, name, ident, daemon, Lock, RLock, Condition (wait, notify, notify_all), Semaphore, '
         'BoundedSemaphore, Event, current_thread, main_thread, get_ident, active_count, enumerate; '
         'queue: Queue, SimpleQueue, LifoQueue, Empty, Full; concurrent.futures: ThreadPoolExecutor '
         '(submit, map, shutdown, with), Future (result, exception, done, cancel), as_completed')

_REPL = {
    ('threading', 'Thread'): '_AilThread', ('threading', 'Lock'): '_AilLock', ('threading', 'RLock'): '_AilRLock',
    ('threading', 'Condition'): '_AilCondition', ('threading', 'Event'): '_AilEvent',
    ('threading', 'Semaphore'): '_AilSemaphore', ('threading', 'BoundedSemaphore'): '_AilBoundedSemaphore',
    ('threading', 'current_thread'): '_ail_current_thread', ('threading', 'main_thread'): '_ail_main_thread',
    ('threading', 'get_ident'): '_ail_th_ident', ('threading', 'get_native_id'): '_ail_th_ident',
    ('threading', 'active_count'): '_ail_active_count', ('threading', 'enumerate'): '_ail_enumerate',
    ('queue', 'Queue'): '_AilQueue', ('queue', 'SimpleQueue'): '_AilQueue', ('queue', 'LifoQueue'): '_AilLifoQueue',
    ('queue', 'Empty'): '_AilQueueEmpty', ('queue', 'Full'): '_AilQueueFull',
    ('concurrent.futures', 'ThreadPoolExecutor'): '_AilPool', ('concurrent.futures', 'Future'): '_AilFuture',
    ('concurrent.futures', 'as_completed'): '_ail_as_completed',
    ('concurrent.futures', 'TimeoutError'): 'TimeoutError',
    ('concurrent.futures', 'CancelledError'): '_AilCancelledError',
    '_ail_th_raise': ('ail_th_p_raise(cx, &{t}, {a0})', 1),
}

_WRITE_INSTEAD = {
    ('threading', 'local'): 'threading.local is not built\n  write instead: pass what each thread needs in args=, '
                            'or keep it in a dict keyed by threading.get_ident()',
    ('threading', 'Timer'): 'threading.Timer is not built\n  write instead: a Thread whose function calls '
                            'time.sleep(delay) first',
    ('threading', 'Barrier'): 'threading.Barrier is not built\n  write instead: join the threads, or a Condition '
                              'with a counter',
    ('threading', 'excepthook'): 'threading.excepthook is not built\n  write instead: catch the exception in the '
                                 'thread function and put it in a list or a queue',
    ('threading', 'settrace'): 'threading.settrace is not built',
    ('threading', 'setprofile'): 'threading.setprofile is not built',
    ('threading', 'stack_size'): 'threading.stack_size is not built (threads get the system default stack)',
    ('threading', 'ThreadError'): 'threading.ThreadError is not built\n  write instead: except RuntimeError '
                                  '(ThreadError is RuntimeError in CPython)',
    ('queue', 'PriorityQueue'): 'queue.PriorityQueue is not built\n  write instead: a Queue, then sort what you '
                                'collected, or heapq under a Lock',
    ('concurrent.futures', 'ProcessPoolExecutor'): 'ProcessPoolExecutor is not built (no worker processes)\n'
                                                   '  write instead: ThreadPoolExecutor, or subprocess.run',
    ('concurrent.futures', 'wait'): 'concurrent.futures.wait is not built\n  write instead: '
                                    '[f.result() for f in futures], or as_completed(futures)',
    '_ail_th_raise': ('ail_th_p_raise(cx, &{t}, {a0})', 1),
}

_TARGET_HOW = ('\n  write instead: a function defined at module level (def worker(...)), or a method of an '
               'object (obj.method), with its arguments in args=(...)')


class Refused(Exception):
    def __init__(self, node, text):
        Exception.__init__(self, text)
        self.line = getattr(node, 'lineno', None) or 1
        self.text = text


def _uses_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name in MODULES or a.name == 'concurrent' for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and not node.level:
            if node.module in MODULES or node.module == 'concurrent':
                return True
    return False


class _Imports:
    def __init__(self, tree):
        self.mods = {}      # alias -> module
        self.names = {}     # bound name -> (module, attr)
        self.concurrent = False   # `import concurrent.futures` binds `concurrent`
        self.others = set()       # aliases of every other import (a module: not a bound method)
        keep = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                rest = []
                for a in node.names:
                    if a.name in ('threading', 'queue'):
                        self.mods[a.asname or a.name] = a.name
                    elif a.name == 'concurrent.futures':
                        if a.asname:
                            self.mods[a.asname] = 'concurrent.futures'
                        else:
                            self.concurrent = True
                    elif a.name == 'concurrent':
                        raise Refused(node, 'import concurrent: write instead: import concurrent.futures')
                    else:
                        rest.append(a)
                        self.others.add(a.asname or a.name.split('.')[0])
                if rest:
                    node.names = rest
                    keep.append(node)
                continue
            if isinstance(node, ast.ImportFrom) and not node.level and node.module in MODULES + ('concurrent',):
                for a in node.names:
                    if a.name == '*':
                        raise Refused(node, 'from %s import *: write instead: import %s and name what you use'
                                      % (node.module, node.module))
                    if node.module == 'concurrent':
                        if a.name != 'futures':
                            raise Refused(node, 'from concurrent import %s is not built' % a.name)
                        self.mods[a.asname or a.name] = 'concurrent.futures'
                        continue
                    self.names[a.asname or a.name] = (node.module, a.name)
                continue
            if isinstance(node, ast.ImportFrom):
                for a in node.names:
                    self.others.add(a.asname or a.name)
            keep.append(node)
        tree.body[:] = keep
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in keep:
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
                if any(n in MODULES or n == 'concurrent' for n in names):
                    raise Refused(node, 'an import of %s inside a function or a block is not built\n'
                                  '  write instead: put the import at the top of the file' % names[0])

    def module_of(self, node):
        if isinstance(node, ast.Name) and node.id in self.mods:
            return self.mods[node.id]
        if (self.concurrent and isinstance(node, ast.Attribute) and node.attr == 'futures'
                and isinstance(node.value, ast.Name) and node.value.id == 'concurrent'):
            return 'concurrent.futures'
        return None

    def resolve(self, node):
        """(module, attribute) when `node` names something of the three modules."""
        if isinstance(node, ast.Name) and node.id in self.names:
            return self.names[node.id]
        if isinstance(node, ast.Attribute):
            mod = self.module_of(node.value)
            if mod is not None:
                return (mod, node.attr)
        return None


class _Rewriter(ast.NodeTransformer):
    def __init__(self, tree, imports):
        self.tree = tree
        self.imp = imports
        self.defs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        self.module_bound = set()
        for n in tree.body:
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    for each in ast.walk(t):
                        if isinstance(each, ast.Name):
                            self.module_bound.add(each.id)
        self.local_bound = [set()]
        self.class_stack = []    # per enclosing class: whether it subclasses threading.Thread directly
        self.calls = []          # generated class sources
        self.call_n = 0
        self.cm_n = 0
        self.uses_pool = any(r == ('concurrent.futures', 'ThreadPoolExecutor') for r in imports.names.values()) or \
            bool(imports.concurrent) or 'concurrent.futures' in imports.mods.values()
        self.opened = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) \
                    and n.value.func.id == 'open':
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        self.opened.add(t.id)

    # -- scopes -----------------------------------------------------------------------------
    def visit_FunctionDef(self, node):
        bound = {a.arg for a in node.args.args + node.args.kwonlyargs + node.args.posonlyargs}
        if node.args.vararg:
            bound.add(node.args.vararg.arg)
        if node.args.kwarg:
            bound.add(node.args.kwarg.arg)
        for each in ast.walk(node):
            if each is node:
                continue
            if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Store):
                bound.add(each.id)
            elif isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound.add(each.name)
        for each in ast.walk(node):
            if isinstance(each, ast.Global):
                bound.difference_update(each.names)
        self.local_bound.append(bound)
        self.generic_visit(node)
        self.local_bound.pop()
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        self.generic_visit(node)
        return node

    def _is_local(self, name):
        return any(name in s for s in self.local_bound[1:])

    # -- names ------------------------------------------------------------------------------
    def _replacement(self, node, what):
        if what in _REPL:
            return ast.copy_location(ast.Name(id=_REPL[what], ctx=ast.Load()), node)
        if what in _WRITE_INSTEAD:
            raise Refused(node, _WRITE_INSTEAD[what])
        raise Refused(node, '%s.%s is not built. Built: %s' % (what[0], what[1], BUILT))

    def visit_Name(self, node):
        if node.id in self.imp.names and not self._is_local(node.id):
            if not isinstance(node.ctx, ast.Load):
                raise Refused(node, '%s is imported from %s and assigned again; rename one of them'
                              % (node.id, self.imp.names[node.id][0]))
            return self._replacement(node, self.imp.names[node.id])
        if node.id in self.imp.mods and not self._is_local(node.id):
            raise Refused(node, 'the module %s used as a value is not built\n  write instead: name what you use, '
                          '%s.Thread(...), %s.Lock()' % (node.id, node.id, node.id))
        return node

    def visit_Attribute(self, node):
        what = self.imp.resolve(node)
        if what is not None:
            if not isinstance(node.ctx, ast.Load):
                raise Refused(node, 'assigning to %s.%s is not built' % what)
            return self._replacement(node, what)
        if self.imp.concurrent and isinstance(node.value, ast.Name) and node.value.id == 'concurrent':
            raise Refused(node, 'concurrent.%s is not built' % node.attr)
        self.generic_visit(node)
        return node

    # -- callables --------------------------------------------------------------------------
    def _callable(self, fn, where):
        """(C-free) the text of the callee and the receiver expression to capture, or a refusal."""
        if isinstance(fn, ast.Name):
            if self._is_local(fn.id):
                raise Refused(where, '%s is a function or a value defined inside a function; a thread or an '
                              'executor runs only a function defined at module level or a method%s'
                              % (fn.id, _TARGET_HOW))
            if fn.id in self.defs:
                return fn.id, None, fn.id
            if fn.id in self.classes:
                return fn.id, None, fn.id
            if fn.id in self.imp.names or fn.id in self.module_bound:
                raise Refused(where, '%s is not a function defined in this program%s' % (fn.id, _TARGET_HOW))
            if hasattr(builtins, fn.id):
                return fn.id, None, fn.id
            raise Refused(where, "name '%s' is not a function defined at module level%s" % (fn.id, _TARGET_HOW))
        if isinstance(fn, ast.Attribute):
            if isinstance(fn.value, ast.Name) and fn.value.id in self.imp.others and not self._is_local(fn.value.id):
                return '%s.%s' % (fn.value.id, fn.attr), None, fn.attr
            if self.imp.resolve(fn) is not None or self.imp.module_of(fn.value) is not None:
                raise Refused(where, '%s as the function of a thread is not built%s' % (ast.unparse(fn), _TARGET_HOW))
            return None, fn.value, fn.attr
        if isinstance(fn, ast.Lambda):
            raise Refused(where, 'a lambda as the function of a thread or an executor is not built%s' % _TARGET_HOW)
        raise Refused(where, '%s as the function of a thread or an executor is not built%s'
                      % (ast.unparse(fn), _TARGET_HOW))

    def _make_call(self, fn, args, star, kwargs, where, modes=('call',)):
        """A Call node constructing a fresh `_AilCall_<k>` for fn(*args, **kwargs)."""
        callee, recv, display = self._callable(fn, where)
        self.call_n += 1
        name = '_AilCall_%d' % self.call_n
        params, values = [], []
        if recv is not None:
            params.append('o')
            values.append(recv)
            callee = 'self.o.' + display
        for i, a in enumerate(args):
            params.append('a%d' % i)
            values.append(a)
        if star is not None:
            params.append('star')
            values.append(ast.Call(func=ast.Name(id='list', ctx=ast.Load()), args=[star], keywords=[]))
        kwnames = []
        for i, (k, v) in enumerate(kwargs):
            params.append('k%d' % i)
            values.append(v)
            kwnames.append(k)
        fixed = ['self.a%d' % i for i in range(len(args))]
        if star is not None:
            fixed.append('*self.star')
        kws = ['%s=self.k%d' % (k, i) for i, k in enumerate(kwnames)]
        lines = ['class %s:' % name,
                 '    def __init__(self%s):' % ''.join(', ' + p for p in params),
                 '        self._ail_name = %r' % display]
        lines += ['        self.%s = %s' % (p, p) for p in params]
        for mode in modes:
            extra = {'call': [], 'call1': ['x'], 'call2': ['x', 'y']}[mode]
            lines.append('    def %s(self%s):' % (mode, ''.join(', ' + e for e in extra)))
            lines.append('        return %s(%s)' % (callee, ', '.join(fixed + extra + kws)))
        self.calls.append('\n'.join(lines) + '\n')
        values = [self.visit(v) for v in values]
        return ast.copy_location(ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=values, keywords=[]), where)

    def _args_of(self, node, where):
        """The positional argument nodes of an args= value, plus a starred remainder."""
        if node is None or (isinstance(node, ast.Constant) and node.value is None):
            return [], None
        if isinstance(node, (ast.Tuple, ast.List)):
            if any(isinstance(e, ast.Starred) for e in node.elts):
                if len(node.elts) == 1:
                    return [], node.elts[0].value
                raise Refused(where, 'args= with a * inside the tuple is not built\n  write instead: args=tuple(xs)')
            return list(node.elts), None
        return [], node

    def _kwargs_of(self, node, where):
        if node is None or (isinstance(node, ast.Constant) and node.value is None):
            return []
        if isinstance(node, ast.Dict) and all(isinstance(k, ast.Constant) and isinstance(k.value, str)
                                              for k in node.keys):
            return [(k.value, v) for k, v in zip(node.keys, node.values)]
        raise Refused(where, 'kwargs= that is not a dict display with string keys is not built\n'
                      '  write instead: kwargs={"name": value}, or pass the values in args=')

    def _thread_call(self, node):
        return ast.copy_location(ast.Call(func=ast.Name(id='_AilThread', ctx=ast.Load()),
                                          args=self._thread_args(node, node.args), keywords=[]), node)

    def _thread_args(self, node, positional):
        """Thread(group, target, name, args, kwargs, *, daemon) as six positional arguments of _AilThread."""
        names = ['group', 'target', 'name', 'args', 'kwargs']
        got = {}
        if len(positional) > len(names):
            raise Refused(node, 'Thread() takes at most 5 positional arguments')
        for i, a in enumerate(positional):
            got[names[i]] = a
        for kw in node.keywords:
            if kw.arg is None:
                raise Refused(node, 'Thread(**kwargs) is not built\n  write instead: name the arguments')
            if kw.arg not in names + ['daemon']:
                raise Refused(node, "Thread() got an unexpected keyword argument '%s'" % kw.arg)
            got[kw.arg] = kw.value
        if 'group' in got and not (isinstance(got['group'], ast.Constant) and got['group'].value is None):
            raise Refused(node, 'Thread(group=...) must be None (thread groups are reserved in CPython too)')
        none = ast.Constant(value=None)
        target = got.get('target')
        if target is None or (isinstance(target, ast.Constant) and target.value is None):
            call = none
        else:
            args, star = self._args_of(got.get('args'), node)
            call = self._make_call(target, args, star, self._kwargs_of(got.get('kwargs'), node), node)
        rest = [self.visit(got[k]) if k in got else copy.copy(none) for k in ('name',)]
        daemon = self.visit(got['daemon']) if 'daemon' in got else copy.copy(none)
        return [copy.copy(none), call, rest[0], copy.copy(none), copy.copy(none), daemon]

    def visit_ClassDef(self, node):
        thread_base = any(self.imp.resolve(b) == ('threading', 'Thread') for b in node.bases)
        self.class_stack.append(thread_base)
        self.generic_visit(node)
        self.class_stack.pop()
        return node

    def _thread_init(self, node):
        """`threading.Thread.__init__(self, ...)` or, in a direct subclass, `super().__init__(...)`."""
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == '__init__'):
            return None
        if self.imp.resolve(func.value) == ('threading', 'Thread'):
            # the general path calls a base method through super() only: in a direct subclass the two are one call
            if not (self.class_stack and self.class_stack[-1] and node.args and isinstance(node.args[0], ast.Name)):
                raise Refused(node, 'Thread.__init__(...) outside a direct subclass of Thread is not built\n'
                              '  write instead: class Worker(threading.Thread) with super().__init__(...) in __init__')
            sup = ast.Call(func=ast.Name(id='super', ctx=ast.Load()), args=[], keywords=[])
            return ast.copy_location(ast.Call(func=ast.Attribute(value=sup, attr='__init__', ctx=ast.Load()),
                                              args=self._thread_args(node, node.args[1:]), keywords=[]), node)
        if (self.class_stack and self.class_stack[-1] and isinstance(func.value, ast.Call)
                and isinstance(func.value.func, ast.Name) and func.value.func.id == 'super' and not func.value.args):
            return ast.copy_location(ast.Call(func=func, args=self._thread_args(node, node.args), keywords=[]), node)
        return None

    def visit_Call(self, node):
        func = node.func
        what = self.imp.resolve(func)
        if what == ('threading', 'Thread'):
            return self._thread_call(node)
        init = self._thread_init(node)
        if init is not None:
            return init
        if isinstance(func, ast.Attribute) and func.attr in ('wait_for', 'add_done_callback'):
            raise Refused(node, '%s() takes a function as a value, which is not built\n  write instead: %s'
                          % (func.attr, 'while not <condition>: cond.wait()' if func.attr == 'wait_for'
                             else 'call f.result() where you need the value'))
        if self.uses_pool and isinstance(func, ast.Attribute) and func.attr == 'submit' and node.args \
                and self.imp.resolve(func.value) is None:
            fn = node.args[0]
            rest = node.args[1:]
            star = None
            if rest and isinstance(rest[-1], ast.Starred):
                if len(rest) != 1:
                    raise Refused(node, 'submit(f, x, *xs) is not built\n  write instead: submit(f, *xs)')
                star = rest[0].value
                rest = []
            if any(isinstance(a, ast.Starred) for a in rest) or any(k.arg is None for k in node.keywords):
                raise Refused(node, 'submit() with * or ** in the middle is not built')
            call = self._make_call(fn, rest, star, [(k.arg, k.value) for k in node.keywords], node)
            recv = self.visit(func.value)
            return ast.copy_location(ast.Call(func=ast.Attribute(value=recv, attr='_submit', ctx=ast.Load()),
                                              args=[call], keywords=[]), node)
        if self.uses_pool and isinstance(func, ast.Attribute) and func.attr == 'map' and len(node.args) >= 2 \
                and self.imp.resolve(func.value) is None:
            its = node.args[1:]
            if len(its) > 2:
                raise Refused(node, 'executor.map over more than two iterables is not built\n'
                              '  write instead: map over zip(a, b, c) with a function that takes one tuple')
            if any(isinstance(a, ast.Starred) for a in its):
                raise Refused(node, 'executor.map(f, *iterables) is not built')
            call = self._make_call(node.args[0], [], None, [], node, modes=('call1',) if len(its) == 1 else ('call2',))
            kws = []
            for k in node.keywords:
                if k.arg == 'timeout':
                    kws.append(ast.keyword(arg='timeout', value=self.visit(k.value)))
                elif k.arg == 'chunksize':
                    continue
                else:
                    raise Refused(node, "map() got an unexpected keyword argument '%s'" % k.arg)
            recv = self.visit(func.value)
            args = [call] + [self.visit(a) for a in its]
            return ast.copy_location(ast.Call(func=ast.Attribute(value=recv, attr='_map', ctx=ast.Load()),
                                              args=args, keywords=kws), node)
        self.generic_visit(node)
        return node

    # -- with -------------------------------------------------------------------------------
    def _lockish(self, expr):
        if isinstance(expr, ast.Name):
            return expr.id not in self.opened
        if isinstance(expr, ast.Attribute):
            return self.imp.resolve(expr) is None
        if isinstance(expr, ast.Call):
            return self.imp.resolve(expr.func) is not None
        return False

    def visit_With(self, node):
        if len(node.items) > 1:
            inner = ast.With(items=node.items[1:], body=node.body, type_comment=None)
            ast.copy_location(inner, node)
            node = ast.copy_location(ast.With(items=node.items[:1], body=[inner], type_comment=None), node)
        item = node.items[0]
        if not self._lockish(item.context_expr):
            self.generic_visit(node)
            return node
        expr = self.visit(item.context_expr)
        body = []
        for s in node.body:
            r = self.visit(s)
            body.extend(r if isinstance(r, list) else [r])
        out = []
        if isinstance(expr, ast.Name):
            holder = expr
        else:
            self.cm_n += 1
            holder = ast.Name(id='_ail_cm%d' % self.cm_n, ctx=ast.Load())
            out.append(ast.Assign(targets=[ast.Name(id=holder.id, ctx=ast.Store())], value=expr, lineno=node.lineno))
        enter = ast.Call(func=ast.Attribute(value=copy.copy(holder), attr='_ail_enter', ctx=ast.Load()), args=[],
                         keywords=[])
        if item.optional_vars is not None:
            out.append(ast.Assign(targets=[item.optional_vars], value=enter, lineno=node.lineno))
        else:
            out.append(ast.Expr(value=enter))
        def leave():
            return ast.Expr(value=ast.Call(func=ast.Attribute(value=copy.copy(holder), attr='_ail_exit',
                                                              ctx=ast.Load()), args=[], keywords=[]))
        body = body or [ast.Pass()]
        if not _release_before_jumps(body, leave):
            out.append(ast.Try(body=body, handlers=[], orelse=[], finalbody=[leave()]))
        else:
            # a break / continue leaves the block: the general path does not run a finally on that edge, so
            # release before the jump, on an exception (raised again as it was), and after the block
            self.cm_n += 1
            exc = '_ail_e%d' % self.cm_n
            again = ast.Expr(value=ast.Call(func=ast.Name(id='_ail_th_raise', ctx=ast.Load()),
                                            args=[ast.Name(id=exc, ctx=ast.Load())], keywords=[]))
            out.append(ast.Try(body=body, handlers=[ast.ExceptHandler(type=ast.Name(id='Exception', ctx=ast.Load()),
                                                                      name=exc, body=[leave(), again])],
                               orelse=[], finalbody=[]))
            out.append(leave())
        for s in out:
            ast.copy_location(s, node)
        return out


def _release_before_jumps(stmts, leave):
    """Put `leave()` before every break / continue in `stmts` that jumps out of them; whether there was one."""
    found = False
    i = 0
    while i < len(stmts):
        s = stmts[i]
        if isinstance(s, (ast.Break, ast.Continue)):
            stmts.insert(i, ast.copy_location(leave(), s))
            found = True
            i += 2
            continue
        if isinstance(s, (ast.For, ast.While, ast.AsyncFor)):
            found = _release_before_jumps(s.orelse, leave) or found     # a jump in the loop body stays inside
        elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            pass
        else:
            for field in ('body', 'orelse', 'finalbody'):
                block = getattr(s, field, None)
                if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                    found = _release_before_jumps(block, leave) or found
            for h in getattr(s, 'handlers', []) or []:
                found = _release_before_jumps(h.body, leave) or found
            for case in getattr(s, 'cases', []) or []:
                found = _release_before_jumps(case.body, leave) or found
        i += 1
    return found


def rewrite_text(source, notes=None):
    """The program with its threading / queue / concurrent.futures uses lowered, or the source as written."""
    if not any(word in source for word in ('threading', 'queue', 'concurrent')):
        return source
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return source
    if not _uses_modules(tree):
        return source
    try:
        imports = _Imports(tree)
        rw = _Rewriter(tree, imports)
        tree = rw.visit(tree)
        index = 0
        while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
                isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
            index += 1
        added = [ast.Import(names=[ast.alias(name=MARKER, asname=None)])]
        for text in rw.calls:
            added.extend(ast.parse(text).body)
        tree.body[index:index] = added
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree)
    except Refused as exc:
        if notes is not None:
            notes.append((exc.line, exc.text))
        return source
    return text.rstrip('\n') + '\n'


def has_marker(tree):
    return any(isinstance(n, ast.Import) and any(a.name == MARKER for a in n.names) for n in tree.body)


def refuse_typed(tree, Unsupported):
    """The typed path does not build threads: say so (the general path builds the program)."""
    if has_marker(tree):
        error = Unsupported('threading, queue and concurrent.futures are built on the general path only (one '
                            'interpreter lock, CPython\'s GIL semantics); this program is compiled there')
        line = next((n.lineno for n in tree.body if isinstance(n, ast.Import)
                     and any(a.name == MARKER for a in n.names)), None)
        if line is not None:
            error.source_line = line
        raise error


_PRELUDE_TREE = None


def _prelude_tree():
    global _PRELUDE_TREE
    if _PRELUDE_TREE is None:
        import thread_prelude
        _PRELUDE_TREE = ast.parse(thread_prelude.PRELUDE)
    return _PRELUDE_TREE


def prelude_def_names():
    """Every def of the prelude (functions and methods), once per definition."""
    return [n.name for n in ast.walk(_prelude_tree()) if isinstance(n, ast.FunctionDef)]


def inject(tree):
    """Remove the marker and add the prelude; whether the program uses threads."""
    if not has_marker(tree):
        return False
    tree.body[:] = [n for n in tree.body if not (isinstance(n, ast.Import) and any(a.name == MARKER for a in n.names))]
    index = 0
    while index < len(tree.body) and (isinstance(tree.body[index], (ast.Import, ast.ImportFrom)) or (
            isinstance(tree.body[index], ast.Expr) and isinstance(tree.body[index].value, ast.Constant))):
        index += 1
    tree.body[index:index] = copy.deepcopy(_prelude_tree()).body
    ast.fix_missing_locations(tree)
    return True


# the primitives of thread_prelude.py: name -> (C call, argument count); threadrt.py holds the C
PRIMS = {
    '_ail_th_gen': ('ail_th_p_gen(cx, &{t})', 0),
    '_ail_th_notify': ('ail_th_p_notify(cx, &{t})', 0),
    '_ail_th_wait': ('ail_th_p_wait(cx, &{t}, {a0}, {a1})', 2),
    '_ail_th_start': ('ail_th_p_start(cx, &{t}, {a0}, {a1})', 2),
    '_ail_th_ident': ('ail_th_p_ident(cx, &{t})', 0),
    '_ail_th_done': ('ail_th_p_done(cx, &{t}, {a0})', 1),
    '_ail_th_now': ('ail_th_p_now(cx, &{t})', 0),
    '_ail_th_cpus': ('ail_th_p_cpus(cx, &{t})', 0),
    '_ail_th_report': ('ail_th_p_report(cx, &{t}, {a0}, {a1})', 2),
    '_ail_th_raise': ('ail_th_p_raise(cx, &{t}, {a0})', 1),
}
