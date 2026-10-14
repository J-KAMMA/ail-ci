"""Print the file-scope identifiers (functions, variables, typedefs, enum constants, macros) the C
headers an AIL program includes declare, as the `_LIBC_CSYMS` text for pyfunc.py.

    python3 tools/gen_libc_names.py > /tmp/names.txt

A user function named like any of these would collide with the header at C compile time (`rename`
vs stdio.h), so `_mangle_csym` renames it. Re-run after changing the runtime's #include list; the
test in test_ail_libc_names.py checks the generated list still covers every header it names.
"""
import re
import subprocess
import sys

HEADERS = ('stdint stdio stdlib string strings math setjmp stdarg unistd errno limits time float fcntl signal '
           'ctype locale assert stdbool stddef inttypes wchar wctype complex fenv iso646 stdatomic threads '
           'sys/types sys/stat sys/mman sys/socket sys/resource sys/time sys/select sys/wait sys/uio sys/un '
           'sys/ioctl sys/utsname sys/times sys/file netinet/in netinet/tcp netdb arpa/inet poll dirent '
           'pthread sched semaphore termios fnmatch glob regex libgen dlfcn getopt utime').split()
IDENT = re.compile(r'[A-Za-z_][A-Za-z_0-9]*')
TOKEN = re.compile(r'[A-Za-z_][A-Za-z_0-9]*|\d[\w.]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\S')


def preprocess(flags, dump_macros=False):
    source = '#define _GNU_SOURCE 1\n' + ''.join('#include <%s.h>\n' % h for h in HEADERS)
    cmd = ['gcc', '-E'] + (['-dM'] if dump_macros else ['-P']) + flags + ['-x', 'c', '-']
    return subprocess.run(cmd, input=source, capture_output=True, text=True, check=True).stdout


def strip_calls(text, words):
    """Remove `word ( ... )` with balanced parentheses (attributes nest them)."""
    pattern = re.compile(r'\b(?:%s)\b' % '|'.join(words))
    out = []
    pos = 0
    while True:
        m = pattern.search(text, pos)
        if not m:
            out.append(text[pos:])
            return ''.join(out)
        out.append(text[pos:m.start()])
        j = m.end()
        while text[j].isspace():
            j += 1
        if text[j] != '(':
            pos = m.end()
            continue
        depth = 0
        while True:
            depth += (text[j] == '(') - (text[j] == ')')
            j += 1
            if depth == 0:
                break
        pos = j


def declared(text):
    text = strip_calls(text, ('__attribute__', '__asm__', '__asm', '__extension__'))
    names = set()
    brace = paren = 0
    enum_stack = []
    tokens = TOKEN.findall(text)
    pending_enum = False
    for i, tok in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ''
        if tok == '{':
            enum_stack.append(pending_enum)
            pending_enum = False
            brace += 1
        elif tok == '}':
            brace -= 1
            if enum_stack:
                enum_stack.pop()
        elif tok == '(':
            paren += 1
        elif tok == ')':
            paren -= 1
        elif tok == ';':
            pending_enum = False
        elif tok == 'enum':
            pending_enum = True
        elif IDENT.fullmatch(tok):
            at_file_scope = brace == 0 and paren == 0
            in_enum = brace >= 1 and enum_stack and enum_stack[-1] and paren == 0
            if at_file_scope and nxt in ('(', ';', '[', '=', ',', ':'):
                names.add(tok)
            elif in_enum and nxt in (',', '=', '}'):
                names.add(tok)
            elif paren >= 1 and brace == 0 and nxt == '(' and not tok.startswith('__'):
                pass                       # function-pointer parameter types: not a declaration
    return names


def main():
    names = set()
    for flags in ([], ['-std=c11'], ['-std=gnu11', '-D_POSIX_C_SOURCE=200809L']):
        names |= declared(preprocess(flags))
        names |= {m.group(1) for m in re.finditer(r'^#define (\w+)', preprocess(flags, True), re.M)}
    names -= set('auto break case char const continue default do double else enum extern float for goto if '
                 'inline int long register restrict return short signed sizeof static struct switch typedef '
                 'union unsigned void volatile while'.split())
    names = sorted(n for n in names if not n.startswith('__') and IDENT.fullmatch(n))
    sys.stdout.write('\n'.join(names) + '\n')


if __name__ == '__main__':
    main()
