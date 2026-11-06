#!/usr/bin/env python3
"""Build a C library from a typed-path AIL/Python module.

    python3 AIL_CURRENT/ail_embed.py build examples/embed/fib/mod.py -o build/fib
    python3 AIL_CURRENT/ail_embed.py build examples/embed/fib/mod.py -o build/fib --shared

The module names its exports in a plain Python list:

    __ail_export__ = ["fib", "gcd"]

For each name the tool writes ``lib<name>.a`` and ``<name>.h`` in the output
directory, or ``lib<name>.so`` and ``<name>.h`` with ``--shared``.  Every export
takes one process-wide lock, so calls from several threads are serialised.  See
examples/embed/README.md for the version 1 ABI.
"""
import argparse
import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / "ail_chatgpt.py"

C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "inline",
    "int", "long", "register", "restrict", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned",
    "void", "volatile", "while", "_Bool", "_Complex", "_Imaginary",
}
PY_KINDS = {"int": "int", "float": "float", "bool": "bool", "str": "str", "bytes": "bytes"}
C_KINDS = {"int64_t": "int", "double": "float", "ail_str": "str", "ail_bytes": "bytes",
           "_Bool": "bool", "int": "int"}
RESERVED_EXPORTS = {"init", "shutdown", "last_error"}


class EmbedError(Exception):
    pass


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def module_facts(source):
    """(exports, library name or None, {function: (params, result)})."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise EmbedError("Python syntax is required: %s" % error) from error
    exports = None
    library = None
    functions = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                value = _literal(node.value)
                if target.id == "__ail_export__":
                    exports = value
                elif target.id == "__ail_name__":
                    library = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            value = _literal(node.value) if node.value is not None else None
            if node.target.id == "__ail_export__":
                exports = value
            elif node.target.id == "__ail_name__":
                library = value
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = []
            args = node.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                if arg.arg in ("self", "cls"):
                    continue
                params.append(_annotation_kind(arg.annotation))
            functions[node.name] = (params, _annotation_kind(node.returns))
    if exports is None:
        raise EmbedError("the module has no __ail_export__ list")
    if not isinstance(exports, (list, tuple)) or not all(isinstance(x, str) for x in exports):
        raise EmbedError("__ail_export__ must be a list of function names")
    if library is not None and not isinstance(library, str):
        raise EmbedError("__ail_name__ must be a string")
    return list(dict.fromkeys(exports)), library, functions


def _annotation_kind(node):
    if node is None:
        return None
    if isinstance(node, ast.Name) and node.id in PY_KINDS:
        return PY_KINDS[node.id]
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "void"
        if isinstance(node.value, str) and node.value in PY_KINDS:
            return PY_KINDS[node.value]
    return "other"


PROTOTYPE = re.compile(
    r"^(?:int64_t|double|ail_str|ail_bytes|void|_Bool|int)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*;",
    re.M)
GENERAL_PROTOTYPE = re.compile(r"^static\s+ail_st\s+pfu_([A-Za-z_]\w*)\s*\(", re.M)


def prototypes(program):
    found = {}
    for match in PROTOTYPE.finditer(program):
        name, raw = match.group(1), match.group(2)
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        params = []
        for part in parts:
            bits = part.split()
            if len(bits) == 1 and bits[0] == "void":
                continue
            if len(bits) != 2:
                params.append(("other", bits[-1]))
            else:
                params.append((bits[0], bits[1]))
        found[name] = (match.group(0).split()[0], params)
    return found


def library_name(source_path, requested):
    if requested:
        name = requested
    else:
        name = source_path.stem
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not name or name[0].isdigit():
        name = "_" + name
    return name


def c_identifier(name):
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not name or name[0].isdigit():
        name = "_" + name
    if name in C_KEYWORDS:
        name += "_"
    return name


def _kind_from_c(c_type, py_kind):
    if c_type not in C_KINDS:
        return None
    kind = C_KINDS[c_type]
    if py_kind in ("int", "bool"):
        return "bool" if py_kind == "bool" else kind
    if py_kind in ("float", "str", "bytes") and py_kind == kind:
        return kind
    if py_kind is None:
        return kind
    if py_kind == "other":
        return kind
    return None


def describe(exports, facts, protos):
    out = []
    for name in exports:
        if name in RESERVED_EXPORTS:
            raise EmbedError("cannot export %r: the name is reserved by the ABI" % name)
        if name not in facts:
            raise EmbedError("cannot export %r: the module defines no such function" % name)
        py_params, py_result = facts[name]
        if name not in protos:
            raise EmbedError("cannot export %r: the function is on the general path (only typed-path "
                             "functions can be exported)" % name)
        c_result, c_params = protos[name]
        if len(c_params) != len(py_params):
            raise EmbedError("cannot export %r: annotation count does not match the generated C" % name)
        params = []
        for (c_type, c_name), py_kind in zip(c_params, py_params):
            kind = _kind_from_c(c_type, py_kind)
            if kind is None:
                raise EmbedError("cannot export %r: parameter %s has unsupported type %s"
                                 % (name, c_name, c_type))
            params.append((c_identifier(c_name), kind))
        if c_result == "void" or py_result == "void":
            raise EmbedError("cannot export %r: a void result is not part of ABI version 1" % name)
        result = _kind_from_c(c_result, py_result)
        if result is None or result == "void":
            raise EmbedError("cannot export %r: unsupported result type %s" % (name, c_result))
        out.append((name, params, result))
    return out


def transform_program(program):
    marker = re.search(r"static\s+void\s+ail_die\s*\(const char\s*\*w\)\s*\{", program)
    if not marker:
        raise EmbedError("the generated C has no ail_die definition to adapt")
    program = program[:marker.start()] + marker.group(0).replace("ail_die", "ail_die_default", 1) + \
        program[marker.end():]
    program, count = re.subn(r"\bint\s+main\s*\(", "static int ail_embed_unused_main(", program)
    if not count:
        raise EmbedError("the generated C has no main function to rename")
    return program


RUNTIME_C = r'''
#include <stdbool.h>
#include <pthread.h>

/* The AIL runtime of a typed-path module has no lock of its own: the generated
 * state is static and the exception stack, the arena and the saved error are
 * globals.  One process-wide mutex is that lock, so two threads calling an
 * export at once are serialised instead of racing. */
static pthread_mutex_t ail_embed_mutex = PTHREAD_MUTEX_INITIALIZER;

static void ail_embed_lock(void) { pthread_mutex_lock(&ail_embed_mutex); }
static void ail_embed_unlock(void) { pthread_mutex_unlock(&ail_embed_mutex); }

static int ail_embed_in_call = 0;
static int ail_embed_slot = -1;
static int ail_embed_saved_top = -1;
static ail_cleanup_frame *ail_embed_saved_cleanup = NULL;
static const char *ail_embed_die_message = NULL;
static char *ail_embed_error = NULL;

static void ail_embed_clear_error(void) {
    free(ail_embed_error);
    ail_embed_error = NULL;
}

static void ail_embed_set_error(const char *name, const char *message, size_t n, int prefix) {
    size_t nl = name ? strlen(name) : 0;
    size_t total;
    char *p;
    ail_embed_clear_error();
    if (nl && prefix && n) total = nl + 2 + n;
    else if (nl && prefix) total = nl;
    else total = n;
    p = (char *)malloc(total + 1);
    if (!p) return;
    if (nl && prefix && n) {
        memcpy(p, name, nl);
        p[nl] = ':';
        p[nl + 1] = ' ';
        memcpy(p + nl + 2, message, n);
    } else if (nl && prefix) {
        memcpy(p, name, nl);
    } else if (n && message) {
        memcpy(p, message, n);
    }
    p[total] = 0;
    ail_embed_error = p;
}

static void ail_die(const char *w) {
    if (ail_embed_in_call) {
        int kind = ail_exc_kind_of(w);
        if (ail_exc_top == ail_embed_slot || !kind) {
            ail_embed_die_message = w;
            ail_exc_code = 0;
            ail_exc_top = ail_embed_slot;
            ail_exc_unwind();
            ail_exc_throw();
        }
    }
    ail_die_default(w);
}

#define AIL_EMBED_BEGIN() do { \
    ail_embed_clear_error(); \
    ail_embed_die_message = NULL; \
    if (ail_exc_top + 1 >= AIL_EXC_MAX_DEPTH) { \
        ail_embed_set_error("RuntimeError", "try nesting too deep", 20, 1); \
        ail_embed_unlock(); \
        return 1; \
    } \
    ail_embed_saved_top = ail_exc_top; \
    ail_embed_saved_cleanup = ail_cleanup_top; \
    ail_embed_slot = ail_exc_top + 1; \
    ail_exc_cleanup[ail_embed_slot] = ail_cleanup_top; \
    ail_exc_top = ail_embed_slot; \
    ail_embed_in_call = 1; \
    if (AIL_SETJMP(ail_exc_stack[ail_embed_slot]) != 0) return ail_embed_failed(); \
} while (0)

static void ail_embed_leave(void) {
    ail_embed_in_call = 0;
    ail_exc_top = ail_embed_saved_top;
}

static int ail_embed_failed(void) {
    ail_embed_leave();
    ail_exc_code = 0;
    ail_cleanup_top = ail_embed_saved_cleanup;
    if (ail_embed_die_message) {
        const char *w = ail_embed_die_message;
        const char *name = ail_exc_pyname(w);
        ail_embed_die_message = NULL;
        if (name) ail_embed_set_error(name, w, strlen(w), 1);
        else ail_embed_set_error(NULL, w, strlen(w), 0);
    } else if (ail_exc_value) {
        ail_exception *value = ail_exc_value;
        const char *name = ail_exception_name(value->code);
        ail_embed_set_error(name, (const char *)value->p, (size_t)value->n, 1);
        ail_exception_release(value);
        ail_exc_value = NULL;
    } else {
        ail_embed_set_error("RuntimeError", "unknown error", 13, 1);
    }
    ail_embed_unlock();
    return 1;
}

static int ail_embed_too_long(size_t n) {
    return n > (size_t)INT64_MAX;
}

static void ail_embed_length_error(void) {
    ail_embed_set_error("OverflowError", "length does not fit in int64", 28, 1);
}
'''


def param_c_declarations(params):
    decls = []
    for name, kind in params:
        if kind == "str":
            decls.append("const char *%s" % name)
            decls.append("size_t %s_len" % name)
        elif kind == "bytes":
            decls.append("const char *%s" % name)
            decls.append("size_t %s_len" % name)
        elif kind == "float":
            decls.append("double %s" % name)
        elif kind == "bool":
            decls.append("bool %s" % name)
        else:
            decls.append("int64_t %s" % name)
    return decls


def result_c_declarations(result):
    if result == "str":
        return ["char *out", "size_t cap", "size_t *len"]
    if result == "bytes":
        return ["char *out", "size_t cap", "size_t *len"]
    if result == "float":
        return ["double *out"]
    if result == "bool":
        return ["bool *out"]
    return ["int64_t *out"]


def wrapper_function(library, name, params, result):
    local = []
    for i, (pname, kind) in enumerate(params):
        v = "e_p%d" % i
        if kind == "str":
            local.append("    if (ail_embed_too_long(%s_len)) { ail_embed_length_error(); return ail_embed_failed(); }" % pname)
            local.append("    ail_str %s = {(const uint8_t *)%s, (int64_t)%s_len, 0};" % (v, pname, pname))
        elif kind == "bytes":
            local.append("    if (ail_embed_too_long(%s_len)) { ail_embed_length_error(); return ail_embed_failed(); }" % pname)
            local.append("    ail_bytes %s = {(const unsigned char *)%s, (int64_t)%s_len};" % (v, pname, pname))
        elif kind == "float":
            local.append("    double %s = %s;" % (v, pname))
        elif kind == "bool":
            local.append("    int64_t %s = %s ? 1 : 0;" % (v, pname))
        else:
            local.append("    int64_t %s = %s;" % (v, pname))
    cname = "%s_%s" % (library, name)
    lines = ["", "int %s(%s) {" % (cname, ", ".join(param_c_declarations(params) +
                                                    result_c_declarations(result)))]
    lines.append("    ail_embed_lock();")
    if result in ("int", "float", "bool"):
        lines.append("    if (!out) { ail_embed_set_error(\"TypeError\", \"out is NULL\", 11, 1); ail_embed_unlock(); return 1; }")
    elif result in ("str", "bytes"):
        lines.append("    if (!len) { ail_embed_set_error(\"TypeError\", \"len is NULL\", 11, 1); ail_embed_unlock(); return 1; }")
        lines.append("    if (cap && !out) { ail_embed_set_error(\"TypeError\", \"out is NULL\", 11, 1); ail_embed_unlock(); return 1; }")
    lines.append("    AIL_EMBED_BEGIN();")
    lines.extend(local)
    lines.append("    %s e_r;" % {
        "int": "int64_t", "float": "double", "bool": "int64_t",
        "str": "ail_str", "bytes": "ail_bytes"}[result])
    call_args = ", ".join("e_p%d" % i for i in range(len(params)))
    lines.append("    e_r = %s(%s);" % (name, call_args))
    lines.append("    ail_embed_leave();")
    if result == "bool":
        lines.append("    *out = e_r != 0;")
    elif result in ("str", "bytes"):
        lines.append("    {")
        lines.append("        size_t n = (size_t)e_r.n;")
        lines.append("        *len = n;")
        lines.append("        if (n > cap) { free((void *)e_r.p); ail_embed_unlock(); return 2; }")
        lines.append("        if (n) memcpy(out, e_r.p, n);")
        lines.append("        free((void *)e_r.p);")
        lines.append("    }")
    else:
        lines.append("    *out = e_r;")
    lines.append("    ail_embed_unlock();")
    lines.append("    return 0;")
    lines.append("}")
    return "\n".join(lines)


def wrapper_source(program, library, described):
    body = [transform_program(program), RUNTIME_C]
    body.append("")
    body.append("int %s_init(void) { ail_embed_lock(); ail_embed_clear_error(); ail_exc_top = -1; "
                "ail_embed_unlock(); return 0; }" % library)
    body.append("void %s_shutdown(void) { ail_embed_lock(); ail_embed_clear_error(); ail_embed_unlock(); }"
                % library)
    body.append("const char *%s_last_error(void) { return ail_embed_error ? ail_embed_error : \"\"; }" % library)
    for name, params, result in described:
        body.append(wrapper_function(library, name, params, result))
    return "\n".join(body) + "\n"


def header_source(library, described):
    guard = "%s_H" % re.sub(r"[^A-Za-z0-9]", "_", library).upper()
    lines = ["#ifndef %s" % guard, "#define %s" % guard, "",
             "#include <stddef.h>", "#include <stdint.h>", "#include <stdbool.h>", "",
             "#ifdef __cplusplus", 'extern "C" {', "#endif", "",
             "int %s_init(void);" % library,
             "void %s_shutdown(void);" % library,
             "const char *%s_last_error(void);" % library, ""]
    for name, params, result in described:
        cname = "%s_%s" % (library, name)
        args = param_c_declarations(params) + result_c_declarations(result)
        lines.append("int %s(%s);" % (cname, ", ".join(args)))
    lines.extend(["", "#ifdef __cplusplus", "}", "#endif", "", "#endif", ""])
    return "\n".join(lines)


def build(source, out_dir, name=None, cc=None, shared=False):
    source = Path(source).resolve()
    if not source.is_file():
        raise EmbedError("no such source file: %s" % source)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    exports, declared_name, facts = module_facts(text)
    library = library_name(source, name or declared_name)
    cc_cmd = shlex.split(cc or os.environ.get("CC") or "gcc")
    if not cc_cmd or not shutil.which(cc_cmd[0]):
        raise EmbedError("no C compiler found: %s" % " ".join(cc_cmd))
    with tempfile.TemporaryDirectory(prefix="ail-embed-") as tmp:
        tmp = Path(tmp)
        exe = tmp / "probe"
        debug = tmp / "dbg"
        command = [sys.executable, "-B", str(CLI), "compile", str(source), "-o", str(exe),
                   "--debug-dir", str(debug)]
        proc = subprocess.run(command, cwd=tmp, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0:
            raise EmbedError((proc.stderr or proc.stdout).strip())
        program_path = debug / "program.c"
        if not program_path.is_file():
            raise EmbedError("the compiler did not write program.c")
        program = program_path.read_text(encoding="utf-8")
        protos = prototypes(program)
        general = set(GENERAL_PROTOTYPE.findall(program))
        missing = [n for n in exports if n in general and n not in protos]
        if missing or "built on the general path" in proc.stderr:
            names = missing or [n for n in exports if n not in protos]
            raise EmbedError("cannot export %s: the function is on the general path (only typed-path "
                             "functions can be exported)" % ", ".join(repr(n) for n in names))
        described = describe(exports, facts, protos)
        wrapper = tmp / "ail_embed_wrapper.c"
        wrapper.write_text(wrapper_source(program, library, described), encoding="utf-8")
        obj = tmp / "ail_embed_wrapper.o"
        compile_cmd = cc_cmd + ["-O2", "-std=gnu11", "-fPIC", "-c", str(wrapper), "-o", str(obj)]
        compiled = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=900)
        if compiled.returncode != 0:
            raise EmbedError(compiled.stderr.strip() or compiled.stdout.strip())
        lib = out_dir / (("lib%s.so" if shared else "lib%s.a") % library)
        if lib.exists():
            lib.unlink()
        if shared:
            linked = subprocess.run(cc_cmd + ["-shared", "-pthread", "-o", str(lib), str(obj), "-lm"],
                                    capture_output=True, text=True, timeout=900)
            if linked.returncode != 0:
                raise EmbedError(linked.stderr.strip())
        else:
            ar = shutil.which("ar")
            if not ar:
                raise EmbedError("no ar found")
            packed = subprocess.run([ar, "rcs", str(lib), str(obj)], capture_output=True, text=True, timeout=900)
            if packed.returncode != 0:
                raise EmbedError(packed.stderr.strip())
        header = out_dir / ("%s.h" % library)
        header.write_text(header_source(library, described), encoding="utf-8")
    return lib, header


def main(argv=None):
    parser = argparse.ArgumentParser(description="build a static C library from an AIL module")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build", help="write lib<name>.a (or .so with --shared) and <name>.h")
    build_parser.add_argument("source")
    build_parser.add_argument("-o", "--output", required=True, help="output directory")
    build_parser.add_argument("--name", help="library name (default: __ail_name__ or the file stem)")
    build_parser.add_argument("--cc", help="C compiler command (default: $CC or gcc)")
    build_parser.add_argument("--shared", action="store_true",
                              help="write lib<name>.so (compiled with -fPIC) instead of lib<name>.a")
    args = parser.parse_args(argv)
    try:
        lib, header = build(args.source, args.output, args.name, args.cc, args.shared)
    except EmbedError as error:
        print("error: %s" % error, file=sys.stderr)
        return 1
    print(lib)
    print(header)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
