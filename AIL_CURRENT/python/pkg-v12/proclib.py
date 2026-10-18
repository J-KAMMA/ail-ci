# -*- coding: utf-8 -*-
"""proclib.py -- stage G8: `subprocess.run` and `subprocess.check_output`
(docs/design/GENERAL_PURPOSE.md s4.3).

A tree-to-tree pass in the manner of filelib.py, run by both compile paths just before the file pass.
It lowers

  * `subprocess.run(args, ...)` and `subprocess.check_output(args, ...)` onto a generated function per
    call shape (`_ail_run_<out><err>`, out/err in n = not captured, t = str, b = bytes) that drives the
    primitives of `PROCS` (their C is ailproc_core.h; filert.py holds the adapters);
  * the result onto a generated class per shape (`_AilCP_<out><err>`) with the fields CPython has for
    that call: `args`, `returncode`, and `stdout` / `stderr` only where the stream was captured (a
    stream that was not captured is None in CPython and there is no None str here);
  * `except subprocess.CalledProcessError / TimeoutExpired / SubprocessError [as e]` onto exception
    classes (codes of their own in the typed runtime, classes of the prelude in the general runtime),
    with `e.returncode`, `e.cmd`, `e.output`, `e.stdout`, `e.stderr`, `e.timeout` read from the
    last-error record of the C layer;
  * `print(r)`, `repr(r)`, `str(r)` of a result onto its repr (CompletedProcess(args=[...], ...)).

Everything the pass does not build is refused by name with a `write instead:` line. A program that does
not import subprocess is not touched, so its C stays byte for byte what it was.
"""
import ast
import copy

import iterlower

# ---------------------------------------------------------------------------------------------
# The primitives: name -> (result kind, argument kinds). The C behind them is ailproc_core.h.

PROCS = {
    '_ail_sp_begin': ('int', ()),
    '_ail_sp_arg': ('int', ('str',)),
    '_ail_sp_cwd': ('int', ('str',)),
    '_ail_sp_envbegin': ('int', ()),
    '_ail_sp_env': ('int', ('str', 'str')),
    '_ail_sp_inputt': ('int', ('str', 'int', 'int')),
    '_ail_sp_inputb': ('int', ('bytes',)),
    '_ail_sp_run': ('int', ('int', 'int')),
    '_ail_sp_rc': ('int', ('int',)),
    '_ail_sp_timedout': ('int', ('int',)),
    '_ail_sp_outt': ('str', ('int', 'int', 'int', 'int')),
    '_ail_sp_outb': ('bytes', ('int', 'int')),
    '_ail_sp_free': ('int', ('int',)),
    '_ail_sp_errfrom': ('int', ('int', 'str')),
    '_ail_sp_errbegin': ('int', ('int', 'int', 'str')),
    '_ail_sp_errarg': ('int', ('str',)),
    '_ail_sp_errout_t': ('int', ('str',)),
    '_ail_sp_errout_b': ('int', ('bytes',)),
    '_ail_sp_errerr_t': ('int', ('str',)),
    '_ail_sp_errerr_b': ('int', ('bytes',)),
    '_ail_sp_errrc': ('int', ()),
    '_ail_sp_errcmd': ('str', ()),
    '_ail_sp_erro_t': ('str', ()),
    '_ail_sp_erro_b': ('bytes', ()),
    '_ail_sp_erre_t': ('str', ()),
    '_ail_sp_erre_b': ('bytes', ()),
    '_ail_sp_errtimeout': ('str', ()),
    '_ail_sp_errmsg': ('str', ()),
    '_ail_sp_repr': ('str', ('str',)),
    '_ail_sp_reprb': ('str', ('bytes',)),
}

# flag bits of _ail_sp_run (ailproc_core.h AILP_*)
PIPE_OUT, PIPE_ERR, ERR_TO_OUT, NULL_OUT, NULL_ERR, HAS_TIMEOUT, NULL_IN, PIPE_IN = 1, 2, 4, 8, 16, 32, 64, 128

ACTIVE = False        # set when the last pass lowered a program that uses subprocess

_MODULE_NAMES = {'subprocess'}
_BUILT = 'Built: subprocess.run, subprocess.check_output, subprocess.PIPE / DEVNULL / STDOUT, CompletedProcess, ' \
         'CalledProcessError, TimeoutExpired, SubprocessError'

_KW_REFUSED = {
    'shell': 'shell=True would hand a command string to /bin/sh (quoting and injection)\n'
             '  write instead: a list of args, subprocess.run(["ls", "-l"])',
    'bufsize': 'bufsize= has no meaning for run() without a Popen object',
    'executable': 'executable= is not built\n  write instead: put the program first in the args list',
    'preexec_fn': 'preexec_fn= is not built (it runs Python code in the child)',
    'close_fds': 'close_fds= is not built; every descriptor above 2 is closed in the child, as the default does',
    'pass_fds': 'pass_fds= is not built',
    'restore_signals': 'restore_signals= is not built; the default (True) is what the child gets',
    'start_new_session': 'start_new_session= is not built',
    'process_group': 'process_group= is not built',
    'user': 'user= is not built', 'group': 'group= is not built', 'extra_groups': 'extra_groups= is not built',
    'umask': 'umask= is not built',
    'startupinfo': 'startupinfo= is not built', 'creationflags': 'creationflags= is not built',
    'pipesize': 'pipesize= is not built',
    'universal_newlines': None,        # an alias of text=
}
_RUN_KEYS = {'args', 'stdin', 'stdout', 'stderr', 'input', 'capture_output', 'check', 'cwd', 'env', 'text',
             'universal_newlines', 'encoding', 'errors', 'timeout', 'shell'} | set(_KW_REFUSED)


def _simple_value(node):
    return isinstance(node, (ast.Constant, ast.Name)) or (isinstance(node, ast.Attribute) and _simple_value(node.value))


class _Site:
    """The parsed arguments of one subprocess.run / check_output call."""
    pass


class _Lowerer(ast.NodeTransformer):
    def __init__(self, tree, Unsupported, general=False):
        self.tree = tree
        self.U = Unsupported
        self.general = general
        self.mods = {}                  # local name -> 'subprocess'
        self.names = {}                 # local name -> 'subprocess.run' ...
        self.import_nodes = []
        self.user_defs = set()
        self.variants = {}              # (out, err) -> True, in order of first use
        self.result_variants = {}       # the same, for the run() calls whose result is used
        self.sites = []
        self.cp_names = set()           # names bound once to the result of a run()
        self.used = False
        self.counter = 0
        self.synth = set()              # ids of the Name nodes this pass made
        self.try_sites = []             # the run() calls of the try body being lowered

    # ---- helpers ---------------------------------------------------------------------------
    def refuse(self, node, text):
        error = self.U(text)
        error.source_line = getattr(node, 'lineno', None)
        raise error

    def N(self, id_, store=False):
        node = iterlower._name(id_, store)
        self.synth.add(id(node))
        return node

    @staticmethod
    def C(value):
        if isinstance(value, int) and not isinstance(value, bool) and value < 0:
            return ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=-value))
        return ast.Constant(value=value)

    def call(self, func, *args):
        if isinstance(func, str):
            func = self.N(func)
        return ast.Call(func=func, args=list(args), keywords=[])

    @staticmethod
    def at(node, origin):
        ast.copy_location(node, origin)
        ast.fix_missing_locations(node)
        return node

    # ---- scanning --------------------------------------------------------------------------
    def scan(self):
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'subprocess':
                        self.mods[alias.asname or 'subprocess'] = 'subprocess'
                if any(a.name == 'subprocess' for a in node.names):
                    if any(a.name != 'subprocess' for a in node.names):
                        self.refuse(node, 'import subprocess together with other modules on one line: write one import per line')
                    self.import_nodes.append(node)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module == 'subprocess':
                for alias in node.names:
                    if alias.name == '*':
                        self.refuse(node, 'from subprocess import *: name what you use')
                    self.names[alias.asname or alias.name] = 'subprocess.' + alias.name
                self.import_nodes.append(node)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.user_defs.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for each in ast.walk(target):
                        if isinstance(each, ast.Name):
                            self.user_defs.add(each.id)

    def wants(self):
        return bool(self.mods or self.names)

    def qual(self, node):
        """`subprocess.run`, `sp.run`, `run` ... through the imports, else None."""
        if isinstance(node, ast.Name):
            if node.id in self.names:
                return self.names[node.id]
            if node.id in self.mods:
                return self.mods[node.id]
            return None
        if isinstance(node, ast.Attribute):
            inner = self.qual(node.value)
            if inner is not None:
                return inner + '.' + node.attr
        return None

    # ---- the parsed call -------------------------------------------------------------------
    def stream_value(self, node, which):
        """'pipe' | 'null' | 'out' | 'none' of a stdout= / stderr= / stdin= argument."""
        if isinstance(node, ast.Constant) and node.value is None:
            return 'none'
        name = self.qual(node)
        if name == 'subprocess.PIPE':
            return 'pipe'
        if name == 'subprocess.DEVNULL':
            return 'null'
        if name == 'subprocess.STDOUT' and which == 'stderr':
            return 'out'
        self.refuse(node, '%s= is built for subprocess.PIPE, subprocess.DEVNULL%s or None.\n'
                          '  write instead: capture_output=True and write the result to the file yourself'
                    % (which, ', subprocess.STDOUT' if which == 'stderr' else ''))

    def parse(self, call, kind):
        who = 'subprocess.' + kind
        if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            self.refuse(call, '%s() with * or ** arguments is not built.\n  write instead: name each argument' % who)
        if len(call.args) > 1:
            self.refuse(call, '%s() takes the command as its only positional argument' % who)
        given = {}
        if call.args:
            given['args'] = call.args[0]
        for keyword in call.keywords:
            if keyword.arg in given:
                self.refuse(call, "%s() got multiple values for argument '%s'" % (who, keyword.arg))
            if keyword.arg not in _RUN_KEYS:
                self.refuse(call, "%s() got an unexpected keyword argument '%s'" % (who, keyword.arg))
            if keyword.arg in _KW_REFUSED and _KW_REFUSED[keyword.arg] is not None:
                value = keyword.value
                if keyword.arg == 'shell' and isinstance(value, ast.Constant) and value.value is False:
                    continue
                if keyword.arg in ('close_fds', 'restore_signals') and isinstance(value, ast.Constant) and value.value is True:
                    continue
                if keyword.arg == 'bufsize' and isinstance(value, ast.Constant) and value.value in (-1,):
                    continue
                self.refuse(call, '%s(%s=...): %s' % (who, keyword.arg, _KW_REFUSED[keyword.arg]))
            given[keyword.arg] = keyword.value
        if 'args' not in given:
            self.refuse(call, "%s() missing required argument 'args'" % who)
        args = given['args']
        if (isinstance(args, ast.Constant) and isinstance(args.value, (str, bytes))) or isinstance(args, ast.JoinedStr) \
                or (isinstance(args, ast.BinOp) and isinstance(args.op, (ast.Mod, ast.Add)) and any(
                    isinstance(side, (ast.Constant, ast.JoinedStr)) and not isinstance(getattr(side, 'value', ''), (list, tuple))
                    for side in (args.left, args.right)) and not isinstance(args.left, (ast.List, ast.Tuple))):
            self.refuse(call, '%s() with a command string is not built: a str command is a program name on POSIX and a '
                              'command line on Windows.\n  write instead: a list of args, %s(["ls", "-l"])' % (who, who))
        site = _Site()
        site.call = call
        site.kind = kind
        site.args = args
        site.given = given

        def flag(name, default=False):
            value = given.get(name)
            if value is None:
                return default
            if isinstance(value, ast.Constant) and isinstance(value.value, bool):
                return value.value
            self.refuse(call, '%s(%s=...) must be True or False written out: whether the result holds str or bytes has '
                              'to be known when the program is built.\n  write instead: %s=True' % (who, name, name))

        capture = flag('capture_output')
        site.text = flag('text') or flag('universal_newlines')
        if 'encoding' in given:
            site.text = True
        if 'errors' in given:
            site.text = True
        site.capture = capture
        stdout = self.stream_value(given['stdout'], 'stdout') if 'stdout' in given else 'none'
        stderr = self.stream_value(given['stderr'], 'stderr') if 'stderr' in given else 'none'
        stdin = self.stream_value(given['stdin'], 'stdin') if 'stdin' in given else 'none'
        if stdin == 'out':
            self.refuse(call, 'stdin=subprocess.STDOUT is not valid')
        if capture:
            if 'stdout' in given or 'stderr' in given:
                self.refuse(call, 'stdout and stderr arguments may not be used with capture_output (CPython raises ValueError)')
            stdout = stderr = 'pipe'
        if kind == 'check_output':
            if 'stdout' in given:
                self.refuse(call, 'check_output() does not take stdout= (CPython raises ValueError: stdout argument not allowed)')
            stdout = 'pipe'
        has_input = 'input' in given and not (isinstance(given['input'], ast.Constant) and given['input'].value is None and kind == 'run')
        if kind == 'check_output' and 'input' in given and isinstance(given['input'], ast.Constant) and given['input'].value is None:
            has_input = 'empty'
        if has_input and 'stdin' in given:
            self.refuse(call, 'stdin and input arguments may not both be used (CPython raises ValueError)')
        site.stdout, site.stderr, site.stdin, site.has_input = stdout, stderr, stdin, has_input
        # the encoding of text mode
        site.enc, site.errh = 0, 0
        if 'encoding' in given:
            value = given['encoding']
            if isinstance(value, ast.Constant) and value.value is None:
                pass
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                import filelib
                canonical = filelib.canonical_encoding(value.value)
                if canonical is None:
                    self.refuse(call, "%s(encoding=%r): only utf-8, ascii and latin-1 are built.\n"
                                      "  write instead: encoding='utf-8' (capture bytes and decode them yourself for another encoding)"
                                % (who, value.value))
                site.enc = {'utf-8': 0, 'ascii': 1, 'latin-1': 2}[canonical]
            else:
                self.refuse(call, '%s(encoding=...) must be a string literal' % who)
        if 'errors' in given:
            value = given['errors']
            if isinstance(value, ast.Constant) and value.value is None:
                pass
            elif isinstance(value, ast.Constant) and value.value in ('strict', 'replace', 'ignore'):
                site.errh = ('strict', 'replace', 'ignore').index(value.value)
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                self.refuse(call, "%s(errors=%r): only 'strict', 'replace' and 'ignore' are built" % (who, value.value))
            else:
                self.refuse(call, '%s(errors=...) must be a string literal' % who)
        if 'timeout' in given:
            value = given['timeout']
            if not (isinstance(value, ast.Constant) and value.value is None):
                if isinstance(value, ast.Constant):
                    if isinstance(value.value, bool) or not isinstance(value.value, (int, float)):
                        self.refuse(call, '%s(timeout=...) must be a number' % who)
                elif not _simple_value(value):
                    self.refuse(call, '%s(timeout=...): write a number or a name here.\n  write instead: bind the timeout to a variable first' % who)
        site.out = ('t' if site.text else 'b') if stdout == 'pipe' else 'n'
        site.err = ('t' if site.text else 'b') if stderr == 'pipe' else 'n'
        return site

    def timeout_of(self, site):
        value = site.given.get('timeout')
        if value is None or (isinstance(value, ast.Constant) and value.value is None):
            return None
        return value

    # ---- analysis (before the rewrite): every call shape of the program ---------------------
    def analyse(self):
        parents = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                name = self.qual(node.func)
                if name in ('subprocess.run', 'subprocess.check_output'):
                    site = self.parse(node, name.split('.')[1])
                    self.sites.append(site)
                    self.variants[(site.out, site.err)] = True
                    if name == 'subprocess.run' and not isinstance(parents.get(id(node)), ast.Expr):
                        self.result_variants[(site.out, site.err)] = True      # (a discarded result is not a CompletedProcess anyone holds)
        if self.general:
            for site in self.sites:
                if 'b' in (site.out, site.err) or site.has_input and not site.text:
                    self.refuse(site.call, 'subprocess output or input as bytes: the general path has no bytes values, so this is built in '
                                           'typed code only.\n  write instead: text=True (str output and input)')

    def variant_for_annotation(self, node):
        if len(self.result_variants) != 1:
            self.refuse(node, 'subprocess.CompletedProcess as an annotation needs the program\'s run() calls to give one kind of result '
                              '(the same capture and text options)\n  write instead: leave the annotation off')
        return '_AilCP_%s%s' % next(iter(self.result_variants))

    def mode_of(self, node, stream):
        """'t' or 'b': the kind of captured `stream` ('o' or 'e') over all calls; refuses when it is unknown or mixed."""
        kinds = set()
        # the calls of the try body that this handler belongs to decide first, the whole program otherwise
        for site in (self.try_sites or self.sites):
            letter = site.out if stream == 'o' else site.err
            if letter != 'n':
                kinds.add(letter)
        if not kinds:
            self.refuse(node, 'the run() call of this try does not capture this stream, so it is None in CPython and there is no None '
                              'str here.\n  write instead: capture_output=True (or stdout=/stderr=subprocess.PIPE), or leave the attribute out')
        if len(kinds) > 1:
            self.refuse(node, 'the exception attribute is str for some run() calls and bytes for others in this program\n'
                              '  write instead: use text=True (or bytes) for all calls')
        return kinds.pop()

    # ---- rewriting -------------------------------------------------------------------------
    def visit_Call(self, node):
        name = self.qual(node.func)
        if name is not None:
            if name in ('subprocess.run', 'subprocess.check_output'):
                return self.at(self.lower_run(node, name.split('.')[1]), node)
            if name in ('subprocess.CompletedProcess', 'subprocess.CalledProcessError', 'subprocess.TimeoutExpired',
                        'subprocess.SubprocessError'):
                self.refuse(node, '%s(...) is not built: the program cannot construct one.\n  write instead: let run(..., check=True) raise it' % name)
            if name.startswith('subprocess.'):
                self.refuse(node, '%s is not built (Popen and streaming come later). %s' % (name, _BUILT))
        # print(r) / repr(r) / str(r) of a result
        if isinstance(node.func, ast.Name) and node.func.id not in self.user_defs:
            if node.func.id == 'print':
                node.args = [self.repr_of(a) if self.is_result(a) else a for a in node.args]
            elif node.func.id in ('repr', 'str') and len(node.args) == 1 and not node.keywords and self.is_result(node.args[0]):
                return self.repr_of(node.args[0])
        return self.generic_visit(node)

    def is_result(self, node):
        return isinstance(node, ast.Name) and node.id in self.cp_names

    def repr_of(self, node):
        return self.at(ast.Call(func=ast.Attribute(value=copy.deepcopy(node), attr='_repr', ctx=ast.Load()), args=[], keywords=[]), node)

    def visit_Attribute(self, node):
        name = self.qual(node)
        if name is not None and isinstance(node.ctx, ast.Load):
            if name in ('subprocess.PIPE', 'subprocess.DEVNULL', 'subprocess.STDOUT'):
                self.refuse(node, '%s is built as the value of stdin=, stdout= or stderr= of run()' % name)
            if name == 'subprocess.CompletedProcess':
                return self.at(self.N(self.variant_for_annotation(node)), node)
            if name in ('subprocess.CalledProcessError', 'subprocess.TimeoutExpired', 'subprocess.SubprocessError'):
                self.refuse(node, '%s is built in `except %s:` only' % (name, name))
            if name.startswith('subprocess.'):
                self.refuse(node, '%s is not built. %s' % (name, _BUILT))
        return self.generic_visit(node)

    def visit_Name(self, node):
        name = self.names.get(node.id)
        if name is not None and isinstance(node.ctx, ast.Load) and node.id not in self.user_defs:
            if name == 'subprocess.CompletedProcess':
                return self.at(self.N(self.variant_for_annotation(node)), node)
            self.refuse(node, '%s used here is not built. %s' % (name, _BUILT))
        if node.id in self.mods and isinstance(node.ctx, ast.Load):
            self.refuse(node, 'the module name %s used as a value is not built. %s' % (node.id, _BUILT))
        return node

    def visit_Subscript(self, node):
        # CompletedProcess[str] as an annotation
        if self.qual(node.value) == 'subprocess.CompletedProcess':
            return self.at(self.N(self.variant_for_annotation(node)), node)
        return self.generic_visit(node)

    def visit_Assign(self, node):
        node = self.generic_visit(node)
        return node

    def lower_run(self, call, kind):
        site = self.parse(call, kind)
        given = site.given
        out, err = site.out, site.err
        cls = '_AilCP_%s%s' % (out, err)
        self.used = True
        self.variants[(out, err)] = True
        flags = 0
        if site.stdout == 'pipe':
            flags |= PIPE_OUT
        elif site.stdout == 'null':
            flags |= NULL_OUT
        if site.stderr == 'pipe':
            flags |= PIPE_ERR
        elif site.stderr == 'null':
            flags |= NULL_ERR
        elif site.stderr == 'out':
            flags |= ERR_TO_OUT
        if site.stdin == 'pipe':
            flags |= PIPE_IN
        elif site.stdin == 'null':
            flags |= NULL_IN
        timeout = self.timeout_of(site)
        if timeout is not None:
            flags |= HAS_TIMEOUT
        visit = lambda n: self.visit(copy.deepcopy(n))
        argv = visit(site.args)
        cwd = visit(given['cwd']) if 'cwd' in given and not (isinstance(given['cwd'], ast.Constant) and given['cwd'].value is None) else None
        env = None
        if 'env' in given and not (isinstance(given['env'], ast.Constant) and given['env'].value is None):
            envnode = given['env']
            if isinstance(envnode, ast.Dict):
                if any(key is None for key in envnode.keys):
                    self.refuse(call, 'env={**...}: os.environ cannot be copied or iterated here.\n'
                                      '  write instead: name each variable, env={"PATH": "/usr/bin", "HOME": home}')
                env = (ast.List(elts=[visit(k) for k in envnode.keys], ctx=ast.Load()),
                       ast.List(elts=[visit(v) for v in envnode.values], ctx=ast.Load()))
            elif _simple_value(envnode):
                env = (self.call('list', self.method(visit(envnode), 'keys')), self.call('list', self.method(visit(envnode), 'values')))
            else:
                self.refuse(call, 'env= is built for a dict written out or a name.\n  write instead: bind the dict to a variable first')
        if site.has_input is True:
            data = visit(given['input'])
        elif site.has_input == 'empty':
            data = self.C('' if site.text else b'')
        else:
            data = None
        if timeout is None:
            tmo, tsrc = ast.Constant(value=0.0), self.C('')
        elif isinstance(timeout, ast.Constant):
            tmo = ast.Constant(value=float(timeout.value))
            tsrc = self.C(repr(timeout.value))
        else:
            tmo = self.call('float', visit(timeout))
            tsrc = self.call('str', visit(timeout))
        check = given.get('check')
        if kind == 'check_output':
            check = check if check is not None else ast.Constant(value=True)
        check = visit(check) if check is not None else ast.Constant(value=False)
        shape = (out, err, bool(site.text), cwd is not None, env is not None, data is not None)
        fn = self.run_name(shape)
        args = [argv] + [x for x in (cwd,) if x is not None] + (list(env) if env is not None else []) \
            + [x for x in (data,) if x is not None] + [self.C(flags), tmo, tsrc, self.C(site.enc), self.C(site.errh), check]
        result = self.call(fn, *args)
        self.need_run.add(shape)
        if kind == 'check_output':
            return ast.Attribute(value=result, attr='stdout', ctx=ast.Load())
        return result

    # ---- try / except ----------------------------------------------------------------------
    _EXC = {'subprocess.CalledProcessError': ('CalledProcessError',),
            'subprocess.TimeoutExpired': ('TimeoutExpired',),
            'subprocess.SubprocessError': ('CalledProcessError', 'TimeoutExpired')}

    def exc_names(self, node):
        types = node.elts if isinstance(node, ast.Tuple) else [node]
        found, other = [], False
        for each in types:
            name = self.qual(each)
            if name in self._EXC:
                found.extend(self._EXC[name])
            else:
                other = True
        return found, other, types

    def visit_Try(self, node):
        calls = {id(each) for each in ast.walk(ast.Module(body=node.body, type_ignores=[])) if isinstance(each, ast.Call)}
        saved = self.try_sites
        self.try_sites = [site for site in self.sites if id(site.call) in calls]
        try:
            node.body = [self.visit(s) for s in node.body]
            node.orelse = [self.visit(s) for s in node.orelse]
            node.finalbody = [self.visit(s) for s in node.finalbody]
            node.handlers = [self.visit(h) for h in node.handlers]
        finally:
            self.try_sites = saved
        return node

    def visit_ExceptHandler(self, node):
        if node.type is None:
            return self.generic_visit(node)
        found, other, types = self.exc_names(node.type)
        if not found:
            return self.generic_visit(node)
        self.used = True
        self.need_exc = True
        elements = []
        for each in types:
            name = self.qual(each)
            if name in self._EXC:
                for exc in self._EXC[name]:
                    elements.append(self.at(self.N(exc), each))
            else:
                elements.append(self.visit(each))
        node.type = elements[0] if len(elements) == 1 else self.at(ast.Tuple(elts=elements, ctx=ast.Load()), node.type)
        if node.name:
            body = _Attrs(self, node.name, set(found), other).apply(node.body)
            node.body = body
        node.body = [self.visit(s) for s in node.body]
        return node

    # ---- the driver ------------------------------------------------------------------------
    def run(self):
        self.need_run = set()
        self.need_exc = False
        self.analyse()
        self.collect_results()
        self.visit(self.tree)
        for node in self.import_nodes:
            if node in self.tree.body:
                self.tree.body[self.tree.body.index(node)] = self.at(ast.Pass(), node)
        self.leftovers()
        self.inject()
        ast.fix_missing_locations(self.tree)

    def collect_results(self):
        """Names bound exactly once, to a run() call: their print / repr / str is the CompletedProcess repr."""
        stores, bound = {}, {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                stores[node.id] = stores.get(node.id, 0) + 1
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                    and isinstance(node.value, ast.Call) and self.qual(node.value.func) == 'subprocess.run':
                bound[node.targets[0].id] = bound.get(node.targets[0].id, 0) + 1
        self.cp_names = {name for name, count in bound.items() if stores.get(name, 0) == count}

    def leftovers(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and id(node) not in self.synth \
                    and (node.id in self.mods or node.id in self.names) and node.id not in self.user_defs:
                self.refuse(node, '%s used here is not built. %s' % (self.qual(node), _BUILT))

    # ---- the generated prelude ---------------------------------------------------------------
    def prelude(self):
        parts = []
        if self.need_exc or self.need_run:
            if self.general:
                parts.append('''
class SubprocessError(Exception):
    pass


class CalledProcessError(SubprocessError):
    pass


class TimeoutExpired(SubprocessError):
    pass
''')
        if self.need_run:
            parts.append('''
def _ail_sp_listrepr(items: list[str]) -> str:
    text = "["
    first = True
    for item in items:
        if not first:
            text += ", "
        first = False
        text += _ail_sp_repr(item)
    return text + "]"
''')
        for out, err in sorted({(shape[0], shape[1]) for shape in self.need_run}):
            parts.append(self.class_source(out, err))
        for shape in sorted(self.need_run):
            parts.append(self.run_source(shape))
        return parts

    @staticmethod
    def run_name(shape):
        out, err, text, cwd, env, data = shape
        return '_ail_run_%s%s%s%s%s%s' % (out, err, 't' if text else 'b', 'c' if cwd else '', 'e' if env else '', 'd' if data else '')

    def class_source(self, out, err):
        cls = '_AilCP_%s%s' % (out, err)
        kinds = {'t': 'str', 'b': 'bytes'}
        fields = ['args: list[str]', 'returncode: int']
        sets = ['        self.args = args', '        self.returncode = returncode']
        check = ['            _ail_u = _ail_sp_errbegin(1, self.returncode, "")',
                 '            for a in self.args:', '                _ail_u = _ail_sp_errarg(a)']
        repr_ = ['"CompletedProcess(args=" + _ail_sp_listrepr(self.args) + ", returncode=" + str(self.returncode)']
        for letter, name, setter in ((out, 'stdout', 'out'), (err, 'stderr', 'err')):
            if letter == 'n':
                continue
            fields.append('%s: %s' % (name, kinds[letter]))
            sets.append('        self.%s = %s' % (name, name))
            check.append('            _ail_u = _ail_sp_err%s_%s(self.%s)' % (setter, letter, name))
            repr_.append(' + ", %s=" + %s(self.%s)' % (name, '_ail_sp_repr' if letter == 't' else '_ail_sp_reprb', name))
        lines = ['class %s:' % cls,
                 '    def __init__(self, %s):' % ', '.join(fields)] + sets + [
                 '',
                 '    def check_returncode(self) -> None:',
                 '        if self.returncode != 0:'] + check + [
                 '            raise CalledProcessError(_ail_sp_errmsg())',
                 '',
                 '    def _repr(self) -> str:',
                 '        return ' + ''.join(repr_) + ' + ")"']
        if self.general:
            lines += ['', '    def __repr__(self) -> str:', '        return self._repr()']
        return '\n'.join(lines) + '\n'

    def run_source(self, shape):
        out, err, text, has_cwd, has_env, has_data = shape
        cls = '_AilCP_%s%s' % (out, err)
        data_kind = 'str' if text else 'bytes'
        params = ['args: list[str]']
        if has_cwd:
            params.append('cwd: str')
        if has_env:
            params += ['envk: list[str]', 'envv: list[str]']
        if has_data:
            params.append('data: %s' % data_kind)
        params += ['flags: int', 'tmo: float', 'tsrc: str', 'enc: int', 'errh: int', 'check: bool']
        lines = ['def %s(%s) -> %s:' % (self.run_name(shape), ', '.join(params), cls)]
        if self.general:
            # the general path does not check the annotation: a str held in a variable would be walked character by character
            import filelib
            if filelib.target_windows():
                lines += ['    if isinstance(args, str):',
                          '        raise ValueError("a str command line is not built; write instead: a list of args")']
            else:
                lines += ['    if isinstance(args, str):',
                          '        args = [args]']
        lines += ['    if len(args) == 0:',
                 '        raise IndexError("list index out of range")',
                 '    _ail_u = _ail_sp_begin()',
                 '    for a in args:',
                 '        _ail_u = _ail_sp_arg(a)']
        if has_cwd:
            lines.append('    _ail_u = _ail_sp_cwd(cwd)')
        if has_env:
            lines += ['    _ail_u = _ail_sp_envbegin()',
                      '    for i in range(len(envk)):',
                      '        _ail_u = _ail_sp_env(envk[i], envv[i])']
        if has_data:
            lines.append('    _ail_u = _ail_sp_input%s(data%s)' % ('t' if text else 'b', ', enc, errh' if text else ''))
        lines += ['    limit = tmo',
                  '    if limit > 1.0e9:',
                  '        limit = 1.0e9',
                  '    h = _ail_sp_run(flags, int(limit * 1000000.0))',
                  '    if _ail_sp_timedout(h) != 0:',
                  '        _ail_u = _ail_sp_errfrom(h, tsrc)',
                  '        raise TimeoutExpired(_ail_sp_errmsg())',
                  '    rc = _ail_sp_rc(h)']
        call_args = ['args', 'rc']
        for letter, name, which in ((out, 'stdout', 1), (err, 'stderr', 2)):
            if letter == 'n':
                continue
            if letter == 't':
                lines.append('    %s = _ail_sp_outt(h, %d, enc, errh)' % (name, which))
            else:
                lines.append('    %s = _ail_sp_outb(h, %d)' % (name, which))
            call_args.append(name)
        lines += ['    _ail_u = _ail_sp_free(h)',
                  '    result = %s(%s)' % (cls, ', '.join(call_args)),
                  '    if check:',
                  '        result.check_returncode()',
                  '    return result']
        return '\n'.join(lines) + '\n'

    def inject(self):
        import filelower
        statements = []
        for source in self.prelude():
            parsed = ast.parse(filelower._Lowerer.surface(source))
            for each in ast.walk(parsed):
                if 'lineno' in getattr(each, '_attributes', ()):
                    each.lineno = 1
                    each.end_lineno = 1
                    each.col_offset = 0
                    each.end_col_offset = 0
                if isinstance(each, ast.Name):
                    each._ail_synth = True
            statements.extend(parsed.body)
        body = self.tree.body
        index = 0
        while index < len(body) and (
                isinstance(body[index], (ast.Import, ast.ImportFrom, ast.Pass))
                or (isinstance(body[index], ast.Expr) and isinstance(body[index].value, ast.Constant))):
            index += 1
        self.tree.body = body[:index] + statements + body[index:]


class _Attrs(ast.NodeTransformer):
    """`e.returncode` and friends inside `except subprocess.X as e:`, read from the last-error record."""

    def __init__(self, low, name, found, other):
        self.low, self.name, self.found, self.other = low, name, found, other
        self.depth = 0

    def apply(self, body):
        return [self.visit(s) for s in body]

    def is_exc(self, node):
        return isinstance(node, ast.Name) and node.id == self.name and isinstance(node.ctx, ast.Load)

    def visit_Call(self, node):
        # str(e) and print(e): the message of the exception, which the typed runtime cannot print itself
        low = self.low
        if isinstance(node.func, ast.Name) and node.func.id in ('str', 'print') and node.func.id not in low.user_defs \
                and len(node.args) >= 1 and not node.other_ok if False else False:
            pass
        if isinstance(node.func, ast.Name) and node.func.id in ('str', 'print') and node.func.id not in low.user_defs \
                and not any(isinstance(a, ast.Starred) for a in node.args):
            if node.func.id == 'str' and len(node.args) == 1 and not node.keywords and self.is_exc(node.args[0]):
                return low.at(low.call('_ail_sp_errmsg'), node)
            if node.func.id == 'print':
                node.args = [low.at(low.call('_ail_sp_errmsg'), a) if self.is_exc(a) else self.visit(a) for a in node.args]
                node.keywords = [self.visit(k) for k in node.keywords]
                return node
        return self.generic_visit(node)

    def visit_FormattedValue(self, node):
        if self.is_exc(node.value):
            node.value = self.low.at(self.low.call('_ail_sp_errmsg'), node.value)
            return node
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == self.name and isinstance(node.ctx, ast.Load):
            low = self.low
            attr = node.attr
            if self.other:
                low.refuse(node, 'e.%s: this handler also catches other exceptions, which do not have it.\n'
                                 '  write instead: a handler of its own for the subprocess exception' % attr)
            if attr == 'returncode':
                if 'CalledProcessError' not in self.found:
                    low.refuse(node, 'TimeoutExpired has no returncode')
                return low.at(low.call('_ail_sp_errrc'), node)
            if attr == 'cmd':
                return low.at(low.method(low.call('_ail_sp_errcmd'), 'split', low.C('\0')), node)
            if attr in ('stdout', 'output', 'stderr'):
                if 'CalledProcessError' not in self.found or 'TimeoutExpired' in self.found:
                    low.refuse(node, 'e.%s of TimeoutExpired is bytes or None whatever text= says.\n'
                                     '  write instead: catch CalledProcessError for the output; use e.cmd and e.timeout for TimeoutExpired' % attr)
                letter = low.mode_of(node, 'e' if attr == 'stderr' else 'o')
                return low.at(low.call('_ail_sp_err%s_%s' % ('e' if attr == 'stderr' else 'o', letter)), node)
            if attr == 'timeout':
                if 'TimeoutExpired' not in self.found:
                    low.refuse(node, 'CalledProcessError has no timeout')
                pool = [site for site in low.try_sites if low.timeout_of(site) is not None] or low.sites
                for site in pool:
                    timeout = low.timeout_of(site)
                    if timeout is not None and not (isinstance(timeout, ast.Constant) and isinstance(timeout.value, float)):
                        low.refuse(node, 'e.timeout is a float or an int as the call wrote it; here it is float only when every timeout= '
                                         'of the calls in the try body is a float literal.\n  write instead: timeout=2.0 (a float literal)')
                return low.at(low.call('float', low.call('_ail_sp_errtimeout')), node)
            low.refuse(node, 'e.%s is not built; built: returncode cmd stdout output stderr timeout' % attr)
        return self.generic_visit(node)


def _method(obj, name, *args):
    return ast.Call(func=ast.Attribute(value=obj, attr=name, ctx=ast.Load()), args=list(args), keywords=[])


_Lowerer.method = staticmethod(_method)


def rewrite_tree(tree, Unsupported, general=False):
    """Lower subprocess in `tree` (in place). Returns whether the program uses it; a program that does not is untouched."""
    global ACTIVE
    ACTIVE = False
    lowerer = _Lowerer(tree, Unsupported, general)
    lowerer.scan()
    if not lowerer.wants():
        return False
    # an import that is never used does not make the program a subprocess program
    uses = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)) and lowerer.qual(node) is not None and node not in lowerer.import_nodes:
            uses = True
            break
    if not uses:
        return False
    lowerer.run()
    ACTIVE = True
    return True
