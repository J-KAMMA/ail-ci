"""A generic class to build line-oriented command interpreters.

This is CPython 3.12's Lib/cmd.py as AIL source.  Copyright (c) 2001 Python Software
Foundation; see the PSF license at https://docs.python.org/3/license.html.

The bundled copy keeps Cmd's public interface and every printed text exactly as CPython
prints them.  It differs only where this compiler refuses a value: `sys.stdin` and
`sys.stdout` are not stored as fields, so input is read with `input()` (or
`sys.stdin.readline()` at the call site) and output is written with `sys.stdout.write()` at
the call site.  The `stdin`/`stdout` constructor arguments are stored as in CPython, but the
process streams are always used: `input()` when `use_rawinput` is true, `sys.stdin.readline()`
when it is false, and `sys.stdout` for output.  Readline completion is not available in a
single-file program, so `complete()` is a stub that returns None.  This compiler has no
`dir()` and an AIL class exposes neither `__dict__` nor `__mro__`, so `get_names()` cannot
list a subclass's methods.  Instead the module declares `do_*`/`help_*` stubs for a fixed
vocabulary of common command names, and `get_names()` returns the matching names from that
vocabulary in CPython's sorted order.  A `getattr()` whose name is only known at run time
cannot call a method here, so `onecmd()` dispatches through literal `getattr(self,
'do_name')` calls over the same vocabulary.  Because a method's `__doc__` cannot be read,
`do_help()` lists every vocabulary command as documented and detailed help comes from
`help_*` methods; a docstring-only command prints `*** No help on <name>`.  Commands named
outside the vocabulary are neither dispatched nor listed.
"""

import sys

__all__ = ["Cmd"]

PROMPT = '(Cmd) '
IDENTCHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'


_CANDIDATE_NAMES = (
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
    identchars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
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
        else:
            if cmd == 'EOF':
                return getattr(self, 'do_EOF')(arg)
            elif cmd == 'add':
                return getattr(self, 'do_add')(arg)
            elif cmd == 'alpha':
                return getattr(self, 'do_alpha')(arg)
            elif cmd == 'count':
                return getattr(self, 'do_count')(arg)
            elif cmd == 'echo':
                return getattr(self, 'do_echo')(arg)
            elif cmd == 'greet':
                return getattr(self, 'do_greet')(arg)
            elif cmd == 'help':
                return getattr(self, 'do_help')(arg)
            elif cmd == 'num':
                return getattr(self, 'do_num')(arg)
            elif cmd == 'ping':
                return getattr(self, 'do_ping')(arg)
            elif cmd == 'secret':
                return getattr(self, 'do_secret')(arg)
            elif cmd == 'shell':
                return getattr(self, 'do_shell')(arg)
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
        # `dir(self.__class__)` is refused: this compiler has no dir() and an AIL class
        # has no __dict__.  Probe a fixed vocabulary of command names instead and keep
        # CPython's sorted order.
        names = []
        for name in _CANDIDATE_NAMES:
            if hasattr(self, 'do_' + name):
                names.append('do_' + name)
            if hasattr(self, 'help_' + name):
                names.append('help_' + name)
        names.sort()
        return names

    def complete_help(self, *args):
        commands = set(self.completenames(*args))
        topics = set(a[5:] for a in self.get_names()
                     if a.startswith('help_' + args[0]))
        return list(commands | topics)

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

    def do_help(self, arg):
        'List available commands with "help" or detailed help with "help cmd".'
        if arg:
            # XXX check arg syntax
            if arg == 'EOF':
                if hasattr(self, 'help_EOF'):
                    getattr(self, 'help_EOF')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'add':
                if hasattr(self, 'help_add'):
                    getattr(self, 'help_add')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'alpha':
                if hasattr(self, 'help_alpha'):
                    getattr(self, 'help_alpha')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'count':
                if hasattr(self, 'help_count'):
                    getattr(self, 'help_count')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'echo':
                if hasattr(self, 'help_echo'):
                    getattr(self, 'help_echo')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'greet':
                if hasattr(self, 'help_greet'):
                    getattr(self, 'help_greet')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'help':
                if hasattr(self, 'help_help'):
                    getattr(self, 'help_help')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'num':
                if hasattr(self, 'help_num'):
                    getattr(self, 'help_num')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'ping':
                if hasattr(self, 'help_ping'):
                    getattr(self, 'help_ping')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'secret':
                if hasattr(self, 'help_secret'):
                    getattr(self, 'help_secret')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            elif arg == 'shell':
                if hasattr(self, 'help_shell'):
                    getattr(self, 'help_shell')()
                else:
                    self._write("%s\n" % str(self.nohelp % (arg,)))
                return
            self._write("%s\n" % str(self.nohelp % (arg,)))
            return
        else:
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
                        # A method's __doc__ cannot be read through getattr() here, so
                        # every do_* command is listed as documented.
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
