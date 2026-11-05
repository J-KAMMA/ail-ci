"""A generic class to build line-oriented command interpreters.

This is CPython 3.12's Lib/cmd.py as AIL source.  Copyright (c) 2001 Python Software
Foundation; see the PSF license at https://docs.python.org/3/license.html.

The bundled copy keeps Cmd's public interface and every printed text exactly as CPython
prints them.  It differs only where this compiler refuses a value: `sys.stdin` and
`sys.stdout` are not stored as fields, so input is read with `input()` (or
`sys.stdin.readline()` at the call site) and output is written with `sys.stdout.write()` at
the call site.  The `stdin`/`stdout` constructor arguments are stored as in CPython, but the
process streams are always used: `input()` when `use_rawinput` is true,
`sys.stdin.readline()` when it is false, and `sys.stdout` for output.  Readline completion
is not available in a single-file program, so `complete()` is a stub that returns None.

Reflection needs a word of explanation.  This compiler has no `dir()` and an AIL class
exposes neither `__dict__` nor a method as a value, so `get_names()` cannot ask the class
for its methods and `getattr(obj, name)` with a name computed at run time cannot find a
method.  Two things work, and the module is built on them:

* `hasattr(obj, name)` accepts a computed `name`, and the compiler answers it by matching
  the name against the methods of every class in the program (a literal `hasattr` is the
  same test for one name).  That answer is exact, including whether a class overrides a
  name it inherits.
* An attribute call on a parameter whose type is unknown -- `o.do_x(arg)` in a module-level
  helper -- is compiled to a run-time check against every class that defines `do_x`, so it
  dispatches to the subclass's own method.  A literal name is required, which is why the
  module spells one small helper per command name.

The helpers refer to a private `_Stubs` class that is not a base of `Cmd`; it exists only so
that the compiler sees a definition of each name and accepts the helpers.  Because `Cmd`
does not inherit it and no program instantiates it, `hasattr(self, 'do_x')` is false for a
subclass that does not implement `do_x`, `parseline('!ls')` keeps `!ls` when there is no
`do_shell`, and `onecmd()` falls through to `default()` for an unimplemented name, exactly
as CPython does.

`get_names()` cannot ask the class for its method names (no `dir()`, `__dict__` or
`__mro__`), but the class's *base* names are fixed and the subclass's commands can be found
with the computed `hasattr()` above.  So it returns CPython's names for `Cmd` itself plus
every command in the supported vocabulary that the instance really defines, and the
no-argument `help` table is built from that list with CPython's own algorithm.  A command
whose name is outside the vocabulary cannot be seen this way and is not listed.

The compiler needs a literal attribute name to call a method, so the module can dispatch
only that fixed vocabulary of command names (`_COMMAND_NAMES`).  The two cases it cannot
make exact stop by name (a documented loud stop, never a guessed answer):

* `onecmd()` raises `NotImplementedError` when the line names a real `do_*` method outside
  that vocabulary (`hasattr()` can see it, but there is no way to call it);
* `help <name>` raises `NotImplementedError` when it would have to read a `do_<name>`
  docstring; a `help_<name>` method, the base `help` text and `*** No help on <name>` for
  an unknown name are exact and still work.

The ten lab programs use only the supported vocabulary and `help_<name>`, so nine of them
print exactly what CPython prints, including the no-argument help table; the calculator
stops loudly on an integer beyond int64 (as the task allows).
"""

import sys

__all__ = ["Cmd"]

PROMPT = '(Cmd) '
IDENTCHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'

# The command names the module can dispatch: one module-level helper each (below).
_COMMAND_NAMES = (
    'EOF',
    'add',
    'alpha',
    'count',
    'echo',
    'greet',
    'help',
    'num',
    'ping',
    'secret',
    'shell',
)

# dir(Cmd) minus the names a subclass adds: object's attributes, Cmd's methods and class
# attributes.  `dir()` itself is refused, so this fixed list stands in for it.  Subclass
# commands found by `hasattr()` are added to it by get_names().
_BASE_NAMES = (
    '__class__',
    '__delattr__',
    '__dict__',
    '__dir__',
    '__doc__',
    '__eq__',
    '__format__',
    '__ge__',
    '__getattribute__',
    '__getstate__',
    '__gt__',
    '__hash__',
    '__init__',
    '__init_subclass__',
    '__le__',
    '__lt__',
    '__module__',
    '__ne__',
    '__new__',
    '__reduce__',
    '__reduce_ex__',
    '__repr__',
    '__setattr__',
    '__sizeof__',
    '__str__',
    '__subclasshook__',
    '__weakref__',
    'cmdloop',
    'columnize',
    'complete',
    'complete_help',
    'completedefault',
    'completenames',
    'default',
    'do_help',
    'doc_header',
    'doc_leader',
    'emptyline',
    'get_names',
    'identchars',
    'intro',
    'lastcmd',
    'misc_header',
    'nohelp',
    'onecmd',
    'parseline',
    'postcmd',
    'postloop',
    'precmd',
    'preloop',
    'print_topics',
    'prompt',
    'ruler',
    'undoc_header',
    'use_rawinput',
)

class _Stubs:
    """Compile-time definitions of the command names; never instantiated.

    `Cmd` does not inherit this class.  It only gives the compiler a definition for each
    name used by the helper functions below, so that `o.do_add(arg)` on an untyped `o` is
    accepted and compiled to a run-time check against the classes that really define it.
    """

    def __init__(self):
        self.ready = 0

    def do_EOF(self, arg):
        pass

    def do_add(self, arg):
        pass

    def do_alpha(self, arg):
        pass

    def do_count(self, arg):
        pass

    def do_echo(self, arg):
        pass

    def do_greet(self, arg):
        pass

    def do_num(self, arg):
        pass

    def do_ping(self, arg):
        pass

    def do_secret(self, arg):
        pass

    def do_shell(self, arg):
        pass

    def help_EOF(self):
        pass

    def help_add(self):
        pass

    def help_alpha(self):
        pass

    def help_count(self):
        pass

    def help_echo(self):
        pass

    def help_greet(self):
        pass

    def help_help(self):
        pass

    def help_num(self):
        pass

    def help_ping(self):
        pass

    def help_secret(self):
        pass

    def help_shell(self):
        pass


# One helper per name: an untyped receiver makes the compiler dispatch to the class that
# defines the method at run time.
def _call_do_EOF(o, arg):
    return o.do_EOF(arg)


def _call_do_add(o, arg):
    return o.do_add(arg)


def _call_do_alpha(o, arg):
    return o.do_alpha(arg)


def _call_do_count(o, arg):
    return o.do_count(arg)


def _call_do_echo(o, arg):
    return o.do_echo(arg)


def _call_do_greet(o, arg):
    return o.do_greet(arg)


def _call_do_help(o, arg):
    return o.do_help(arg)


def _call_do_num(o, arg):
    return o.do_num(arg)


def _call_do_ping(o, arg):
    return o.do_ping(arg)


def _call_do_secret(o, arg):
    return o.do_secret(arg)


def _call_do_shell(o, arg):
    return o.do_shell(arg)


def _call_help_EOF(o):
    return o.help_EOF()


def _call_help_add(o):
    return o.help_add()


def _call_help_alpha(o):
    return o.help_alpha()


def _call_help_count(o):
    return o.help_count()


def _call_help_echo(o):
    return o.help_echo()


def _call_help_greet(o):
    return o.help_greet()


def _call_help_help(o):
    return o.help_help()


def _call_help_num(o):
    return o.help_num()


def _call_help_ping(o):
    return o.help_ping()


def _call_help_secret(o):
    return o.help_secret()


def _call_help_shell(o):
    return o.help_shell()


class Cmd:
    """A simple framework for writing line-oriented command interpreters.

    These are often useful for test harnesses, administrative tools, and
    prototypes that will later be wrapped in a more sophisticated interface.

    A Cmd instance or subclass instance is a line-oriented interpreter
    framework.  There is no good reason to instantiate Cmd itself; rather,
    it's useful as a superclass of an interpreter class you define yourself
    in order to inherit Cmd's methods and encapsulate action methods.

    """
    prompt = '(Cmd) '
    identchars = IDENTCHARS
    ruler = '='
    lastcmd = ''
    intro = None
    doc_leader = ""
    doc_header = "Documented commands (type help <topic>):"
    misc_header = "Miscellaneous help topics:"
    undoc_header = "Undocumented commands:"
    nohelp = "*** No help on %s"
    use_rawinput = 1

    def __init__(self, completekey='tab', stdin=None, stdout=None):
        """Instantiate a line-oriented interpreter framework.

        The optional argument 'completekey' is the readline name of a
        completion key; it defaults to the Tab key. The optional arguments
        stdin and stdout specify alternate input and output file objects; if
        not specified, sys.stdin and sys.stdout are used.

        """
        self.stdin = stdin
        self.stdout = stdout
        self.cmdqueue = []
        self.completekey = completekey

    def _write(self, text):
        sys.stdout.write(text)

    def _flush(self):
        sys.stdout.flush()

    def cmdloop(self, intro=None):
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.

        """
        self.preloop()
        if intro is not None:
            self.intro = intro
        if self.intro:
            self._write(str(self.intro) + "\n")
        stop = None
        while not stop:
            if self.cmdqueue:
                line = self.cmdqueue.pop(0)
            else:
                if self.use_rawinput:
                    try:
                        line = input(self.prompt)
                    except EOFError:
                        line = 'EOF'
                else:
                    self._write(self.prompt)
                    self._flush()
                    line = sys.stdin.readline()
                    if not len(line):
                        line = 'EOF'
                    else:
                        line = line.rstrip('\r\n')
            line = self.precmd(line)
            stop = self.onecmd(line)
            stop = self.postcmd(stop, line)
        self.postloop()

    def precmd(self, line):
        """Hook method executed just before the command line is
        interpreted, but after the input prompt is generated and issued.

        """
        return line

    def postcmd(self, stop, line):
        """Hook method executed just after a command dispatch is finished."""
        return stop

    def preloop(self):
        """Hook method executed once when the cmdloop() method is called."""
        pass

    def postloop(self):
        """Hook method executed once when the cmdloop() method is about to
        return.

        """
        pass

    def parseline(self, line):
        """Parse the line into a command name and a string containing
        the arguments.  Returns a tuple containing (command, args, line).
        'command' and 'args' may be None if the line couldn't be parsed.
        """
        line = line.strip()
        if not line:
            return None, None, line
        elif line[0] == '?':
            line = 'help ' + line[1:]
        elif line[0] == '!':
            if hasattr(self, 'do_shell'):
                line = 'shell ' + line[1:]
            else:
                return None, None, line
        i, n = 0, len(line)
        while i < n and line[i] in self.identchars:
            i = i + 1
        cmd, arg = line[:i], line[i:].strip()
        return cmd, arg, line

    def onecmd(self, line):
        """Interpret the argument as though it had been typed in response
        to the prompt.

        This may be overridden, but should not normally need to be;
        see the precmd() and postcmd() methods for useful execution hooks.
        The return value is a flag indicating whether interpretation of
        commands by the interpreter should stop.

        """
        cmd, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if cmd is None:
            return self.default(line)
        self.lastcmd = line
        if line == 'EOF':
            self.lastcmd = ''
        if cmd == '':
            return self.default(line)
        if cmd == 'EOF':
            if hasattr(self, 'do_EOF'):
                return _call_do_EOF(self, arg)
        elif cmd == 'add':
            if hasattr(self, 'do_add'):
                return _call_do_add(self, arg)
        elif cmd == 'alpha':
            if hasattr(self, 'do_alpha'):
                return _call_do_alpha(self, arg)
        elif cmd == 'count':
            if hasattr(self, 'do_count'):
                return _call_do_count(self, arg)
        elif cmd == 'echo':
            if hasattr(self, 'do_echo'):
                return _call_do_echo(self, arg)
        elif cmd == 'greet':
            if hasattr(self, 'do_greet'):
                return _call_do_greet(self, arg)
        elif cmd == 'help':
            return _call_do_help(self, arg)
        elif cmd == 'num':
            if hasattr(self, 'do_num'):
                return _call_do_num(self, arg)
        elif cmd == 'ping':
            if hasattr(self, 'do_ping'):
                return _call_do_ping(self, arg)
        elif cmd == 'secret':
            if hasattr(self, 'do_secret'):
                return _call_do_secret(self, arg)
        elif cmd == 'shell':
            if hasattr(self, 'do_shell'):
                return _call_do_shell(self, arg)
        # `hasattr` with a computed name finds every do_* method in the program, but this
        # compiler can only call a method whose name is a literal.  A command that really
        # exists outside the vocabulary is refused by name rather than sent to default().
        if hasattr(self, 'do_' + cmd):
            raise NotImplementedError(
                "cmd.Cmd.onecmd: cannot dispatch do_%s: this compiler can only call a method "
                "whose name is known at build time (the supported command names are EOF, add, "
                "alpha, count, echo, greet, help, num, ping, secret and shell)" % cmd)
        return self.default(line)

    def emptyline(self):
        """Called when an empty line is entered in response to the prompt.

        If this method is not overridden, it repeats the last nonempty
        command entered.

        """
        if self.lastcmd:
            return self.onecmd(self.lastcmd)

    def default(self, line):
        """Called on an input line when the command prefix is not recognized.

        If this method is not overridden, it prints an error message and
        returns.

        """
        self._write('*** Unknown syntax: %s\n' % line)

    def completedefault(self, *ignored):
        """Method called to complete an input line when no command-specific
        complete_*() method is available.

        By default, it returns an empty list.

        """
        return []

    def completenames(self, text, *ignored):
        dotext = 'do_' + text
        return [a[3:] for a in self.get_names() if a.startswith(dotext)]

    def complete(self, text, state):
        """Return the next possible completion for 'text'.

        Readline completion is not available in a single-file program.
        """
        return None

    def get_names(self):
        # `dir(self.__class__)` is refused: this compiler has no dir().  The base class's
        # own names are fixed and listed above; a subclass command is found with
        # hasattr(), which tests exactly the classes that define the name.  A command name
        # outside `_COMMAND_NAMES` cannot be seen this way, so it is not listed.
        names = list(_BASE_NAMES)
        for name in _COMMAND_NAMES:
            if hasattr(self, 'do_' + name) and ('do_' + name) not in names:
                names.append('do_' + name)
            if hasattr(self, 'help_' + name) and ('help_' + name) not in names:
                names.append('help_' + name)
        names.sort()
        return names

    def complete_help(self, *args):
        commands = set(self.completenames(*args))
        topics = set(a[5:] for a in self.get_names()
                     if a.startswith('help_' + args[0]))
        return list(commands | topics)

    def do_help(self, arg):
        'List available commands with "help" or detailed help with "help cmd".'
        if arg:
            # XXX check arg syntax
            if arg == 'EOF':
                if hasattr(self, 'help_EOF'):
                    _call_help_EOF(self)
                    return
            elif arg == 'add':
                if hasattr(self, 'help_add'):
                    _call_help_add(self)
                    return
            elif arg == 'alpha':
                if hasattr(self, 'help_alpha'):
                    _call_help_alpha(self)
                    return
            elif arg == 'count':
                if hasattr(self, 'help_count'):
                    _call_help_count(self)
                    return
            elif arg == 'echo':
                if hasattr(self, 'help_echo'):
                    _call_help_echo(self)
                    return
            elif arg == 'greet':
                if hasattr(self, 'help_greet'):
                    _call_help_greet(self)
                    return
            elif arg == 'help':
                if hasattr(self, 'help_help'):
                    _call_help_help(self)
                    return
            elif arg == 'num':
                if hasattr(self, 'help_num'):
                    _call_help_num(self)
                    return
            elif arg == 'ping':
                if hasattr(self, 'help_ping'):
                    _call_help_ping(self)
                    return
            elif arg == 'secret':
                if hasattr(self, 'help_secret'):
                    _call_help_secret(self)
                    return
            elif arg == 'shell':
                if hasattr(self, 'help_shell'):
                    _call_help_shell(self)
                    return
            # `help help` with no help_help: CPython prints do_help's own docstring, which
            # is the literal below, so this case stays exact.
            if arg == 'help':
                self._write('List available commands with "help" or detailed help with "help cmd".\n')
                return
            # A computed help name cannot be called either.  Refuse it by name instead of
            # printing "No help", which would be a silent difference.
            if hasattr(self, 'help_' + arg):
                raise NotImplementedError(
                    "cmd.Cmd.do_help: cannot call help_%s: this compiler can only call a method "
                    "whose name is known at build time" % arg)
            # CPython reads do_<arg>.__doc__ here.  A method's docstring cannot be read by
            # this compiler, so printing either the docstring or "No help" would be wrong
            # for one of the two cases; refuse by name instead.
            if hasattr(self, 'do_' + arg):
                raise NotImplementedError(
                    "cmd.Cmd.do_help: cannot read the docstring of do_%s; this compiler cannot "
                    "read a method's __doc__ (define a help_%s method instead)" % (arg, arg))
            self._write("%s\n" % str(self.nohelp % (arg,)))
            return
        else:
            # CPython's table needs dir(self.__class__) for the names and each do_*
            # method's __doc__ to split documented from undocumented.  get_names() supplies
            # the base names plus every supported command the instance defines; a docstring
            # cannot be read here, so a do_* command that has no help_<name> topic is listed
            # as documented.
            names = self.get_names()
            cmds_doc = []
            cmds_undoc = []
            topics = set()
            for name in names:
                if name[:5] == 'help_':
                    topics.add(name[5:])
            names.sort()
            # There can be duplicates if routines overridden
            prevname = ''
            for name in names:
                if name[:3] == 'do_':
                    if name == prevname:
                        continue
                    prevname = name
                    cmd = name[3:]
                    if cmd in topics:
                        cmds_doc.append(cmd)
                        topics.remove(cmd)
                    else:
                        cmds_doc.append(cmd)
            self._write("%s\n" % str(self.doc_leader))
            self.print_topics(self.doc_header, cmds_doc, 15, 80)
            self.print_topics(self.misc_header, sorted(topics), 15, 80)
            self.print_topics(self.undoc_header, cmds_undoc, 15, 80)

    def print_topics(self, header, cmds, cmdlen, maxcol):
        if cmds:
            self._write("%s\n" % str(header))
            if self.ruler:
                self._write("%s\n" % str(self.ruler * len(header)))
            self.columnize(cmds, maxcol - 1)
            self._write("\n")

    def columnize(self, list, displaywidth=80):
        """Display a list of strings as a compact set of columns.

        Each column is only as wide as necessary.
        Columns are separated by two spaces (one was not legible enough).
        """
        if not list:
            self._write("<empty>\n")
            return

        nonstrings = [i for i in range(len(list))
                      if not isinstance(list[i], str)]
        if nonstrings:
            raise TypeError("list[i] not a string for i in %s"
                            % ", ".join(map(str, nonstrings)))
        size = len(list)
        if size == 1:
            self._write('%s\n' % str(list[0]))
            return
        # Try every row count from 1 upwards
        for nrows in range(1, len(list)):
            ncols = (size + nrows - 1) // nrows
            colwidths = []
            totwidth = -2
            for col in range(ncols):
                colwidth = 0
                for row in range(nrows):
                    i = row + nrows * col
                    if i >= size:
                        break
                    x = list[i]
                    colwidth = max(colwidth, len(x))
                colwidths.append(colwidth)
                totwidth += colwidth + 2
                if totwidth > displaywidth:
                    break
            if totwidth <= displaywidth:
                break
        else:
            nrows = len(list)
            ncols = 1
            colwidths = [0]
        for row in range(nrows):
            texts = []
            for col in range(ncols):
                i = row + nrows * col
                if i >= size:
                    x = ""
                else:
                    x = list[i]
                texts.append(x)
            while texts and not texts[-1]:
                del texts[-1]
            for col in range(len(texts)):
                texts[col] = texts[col].ljust(colwidths[col])
            self._write("%s\n" % str("  ".join(texts)))
