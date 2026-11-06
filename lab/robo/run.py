#!/usr/bin/env python3
"""robo1: cross-build, bare-metal, jitter and RAM probe for AIL.

    python3 lab/robo/run.py                # everything (about 8 minutes)
    python3 lab/robo/run.py --quick        # 2000-iteration jitter runs
    python3 lab/robo/run.py --skip-jitter

Writes lab/robo/results.json. Nothing here changes the compiler: the AIL C is
the compiler's own (`--debug-dir` keeps program.c) and the cross compilers get
the same -O2 flags.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / "AIL_CURRENT" / "ail_chatgpt.py"
PROGS = HERE / "progs"
HARNESS = HERE / "harness"

# The native flags AIL itself uses for its C (from a --debug-dir build log).
CFLAGS = ["-O2", "-fno-asynchronous-unwind-tables", "-ffp-contract=off",
          "-fopenmp-simd", "-std=c11"]

LINUX_TARGETS = {
    "aarch64-linux-gnu": {
        "cc": "aarch64-linux-gnu-gcc", "size": "aarch64-linux-gnu-size",
        "qemu": ["qemu-aarch64", "-L", "/usr/aarch64-linux-gnu"],
    },
    "arm-linux-gnueabihf": {
        "cc": "arm-linux-gnueabihf-gcc", "size": "arm-linux-gnueabihf-size",
        "qemu": ["qemu-arm", "-L", "/usr/arm-linux-gnueabihf"],
    },
}
BM = {
    "cc": "arm-none-eabi-gcc", "size": "arm-none-eabi-size",
    "cpu": ["-mcpu=cortex-m3", "-mthumb"],
    "qemu": ["qemu-system-arm", "-M", "mps2-an385", "-nographic",
             "-semihosting-config", "enable=on,target=native"],
}
PROGRAMS = ["pid", "ringbuf", "kin2"]
CENSUS = ["thread", "par", "net", "mmap_big", "time", "file", "os"]


def sh(cmd, cwd=None, timeout=300, env=None):
    e = dict(os.environ)
    e.setdefault("AIL_NO_CACHE", "1")
    if env:
        e.update(env)
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=e)
    return p


def first_error(text):
    for line in text.splitlines():
        if "error:" in line or "undefined reference" in line or "fatal error" in line:
            return line.strip()
    return ""


def parse_size(text):
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            return {"text": int(parts[0]), "data": int(parts[1]), "bss": int(parts[2])}
    return {}


def time_rss(cmd, timeout=120):
    """Run cmd, return (rc, stdout, stderr, peak_rss_kb or None)."""
    if Path("/usr/bin/time").exists():
        p = sh(["/usr/bin/time", "-f", "RSSKB %M"] + cmd, timeout=timeout)
        rss = None
        m = re.search(r"RSSKB (\d+)", p.stderr)
        if m:
            rss = int(m.group(1))
        return p.returncode, p.stdout, p.stderr, rss
    p = sh(cmd, timeout=timeout)
    return p.returncode, p.stdout, p.stderr, None


def ail_build(source, work, name):
    """Compile an AIL program, keep program.c. Returns (exe, cpath, log) or (None, None, log)."""
    exe = work / name
    dd = work / (name + "_c")
    cmd = [sys.executable, str(AIL), "compile", str(source), "--syntax", "python",
           "-o", str(exe), "--debug-dir", str(dd), "--no-cache"]
    p = sh(cmd, cwd=work)
    cpath = dd / "program.c"
    if p.returncode != 0 or not cpath.exists():
        return None, None, (p.stdout + p.stderr)
    return exe, cpath, (p.stdout + p.stderr)


def cpython_run(source, work):
    p = sh([sys.executable, str(source)], cwd=work, env={"PYTHONPATH": str(REPO / "AIL_CURRENT")})
    return p.returncode, p.stdout


def versions():
    out = {}
    probes = {
        "gcc": ["gcc", "--version"],
        "aarch64-gcc": ["aarch64-linux-gnu-gcc", "--version"],
        "armhf-gcc": ["arm-linux-gnueabihf-gcc", "--version"],
        "arm-none-eabi-gcc": ["arm-none-eabi-gcc", "--version"],
        "qemu": ["qemu-aarch64", "--version"],
        "qemu-system-arm": ["qemu-system-arm", "--version"],
        "cpython": [sys.executable, "--version"],
        "ail-commit": ["git", "-C", str(REPO), "rev-parse", "HEAD"],
    }
    for name, cmd in probes.items():
        p = sh(cmd)
        out[name] = (p.stdout or p.stderr).splitlines()[0].strip() if (p.stdout or p.stderr) else ""
    p = sh(["micropython", "-c", "import sys; print(sys.version)"])
    out["micropython"] = p.stdout.strip() or p.stderr.strip()
    p = sh(["bash", "-lc", "grep -E 'VERSION_ID' /etc/os-release"])
    out["os"] = p.stdout.strip()
    try:
        import subprocess as sp
        p = sp.run(["dpkg-query", "-W", "-f=${Version}", "gcc-arm-none-eabi"], capture_output=True, text=True)
        out["gcc-arm-none-eabi-package"] = p.stdout.strip()
    except Exception:
        pass
    return out


# ------------------------------------------------------------------ bare metal

def bm_build(cpath, work, name, extra=None, timeout=300):
    elf = work / (name + ".elf")
    cmd = ([BM["cc"]] + BM["cpu"] + CFLAGS +
           ["-nostartfiles", "--specs=nano.specs", "--specs=rdimon.specs",
            "-T", str(HARNESS / "mps2_an385.ld"),
            str(HARNESS / "startup.c"), str(HARNESS / "memcount.c"), str(cpath),
            "-Wl,--wrap=malloc,--wrap=calloc,--wrap=realloc,--wrap=free",
            "-u", "_printf_float"] + (extra or []) + ["-o", str(elf), "-lm"])
    p = sh(cmd, cwd=work, timeout=timeout)
    if p.returncode != 0 or not elf.exists():
        return None, p.stdout + p.stderr
    return elf, p.stdout + p.stderr


def bm_run(elf, cwd, timeout=120):
    p = sh(BM["qemu"] + ["-kernel", str(elf)], cwd=cwd, timeout=timeout)
    peak = None
    m = re.search(r"heap_peak (\d+)", p.stderr)
    if m:
        peak = int(m.group(1))
    return p.returncode, p.stdout, p.stderr, peak


# ------------------------------------------------------------------ jitter

def parse_jitter(stdout):
    d = {}
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                d[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return d


def median(values):
    values = sorted(values)
    return values[len(values) // 2]


def jitter(work, iters, reps):
    out = {"iters": iters, "reps": reps, "tools": {}}
    # C
    exe = work / "pidc"
    p = sh(["gcc"] + CFLAGS + [str(PROGS / "pid.c"), "-o", str(exe), "-lm"])
    out["c_build_error"] = first_error(p.stderr)
    # AIL
    ail_exe, _, log = ail_build(PROGS / "pid_ail.py", work, "pid_ail")
    notes = [l for l in log.strip().splitlines() if l.startswith("note:")]
    out["ail_build_note"] = " ".join(notes)
    # MicroPython: run the source directly
    mpy = ["micropython", "-X", "heapsize=64M", str(PROGS / "pid_mpy.py")]

    for variant in ("noalloc", "alloc"):
        row = {}
        runs = {"c": [], "ail": [], "micropython": []}
        for rep in range(reps):
            p = sh([str(exe), str(iters), variant], timeout=iters // 1000 * 3 + 120)
            runs["c"].append(parse_jitter(p.stdout))
            if ail_exe:
                p = sh([str(ail_exe), str(iters), variant], timeout=iters // 1000 * 3 + 120)
                runs["ail"].append(parse_jitter(p.stdout))
            p = sh(mpy + [str(iters), variant], timeout=iters // 1000 * 3 + 120)
            runs["micropython"].append(parse_jitter(p.stdout))
        for tool, rs in runs.items():
            rs = [r for r in rs if r]
            if not rs:
                row[tool] = None
                continue
            row[tool] = {
                "p50_us": median([r.get("p50", 0) for r in rs]),
                "p99_us": median([r.get("p99", 0) for r in rs]),
                "p999_us": median([r.get("p999", 0) for r in rs]),
                "max_us": median([r.get("max", 0) for r in rs]),
                "overruns": median([r.get("overruns", 0) for r in rs]),
                "runs": rs,
            }
        out["tools"][variant] = row
    return out


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="2000 jitter iterations")
    ap.add_argument("--skip-jitter", action="store_true")
    ap.add_argument("--reps", type=int, default=3)
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="robo1-"))
    results = {"versions": versions(), "programs": {}, "bare_metal": {},
               "census": {}, "jitter": {}, "rss": {}}

    # ---- 1. correctness programs: CPython reference, native, two Linux cross builds
    for name in PROGRAMS:
        src = PROGS / (name + ".py")
        py_rc, py_out = cpython_run(src, work)
        entry = {"cpython": {"rc": py_rc, "stdout": py_out}, "targets": {}}
        exe, cpath, log = ail_build(src, work, name)
        if not exe:
            entry["ail_build_error"] = log[-2000:]
            results["programs"][name] = entry
            continue
        entry["ail_build_note"] = log.strip()
        # native
        nat = work / (name + "_native")
        p = sh(["gcc"] + CFLAGS + [str(cpath), "-o", str(nat), "-lm"])
        cell = {"builds": p.returncode == 0, "first_error": first_error(p.stderr)}
        if cell["builds"]:
            rc, out, err, rss = time_rss([str(nat)])
            s = sh(["size", str(nat)])
            cell.update({"runs": rc == 0, "matches_cpython": out == py_out,
                         "first_diff": "" if out == py_out else _diff(py_out, out),
                         "size": parse_size(s.stdout), "rc": rc, "rss_kb": rss})
        entry["targets"]["native"] = cell
        # cross Linux
        for tname, t in LINUX_TARGETS.items():
            out_exe = work / (name + "_" + tname)
            p = sh([t["cc"]] + CFLAGS + [str(cpath), "-o", str(out_exe), "-lm"])
            cell = {"builds": p.returncode == 0, "first_error": first_error(p.stderr)}
            if cell["builds"]:
                s = sh([t["size"], str(out_exe)])
                rc, out, err, rss = time_rss(t["qemu"] + [str(out_exe)], timeout=300)
                cell.update({"runs": rc == 0, "matches_cpython": out == py_out,
                             "first_diff": "" if out == py_out else _diff(py_out, out),
                             "size": parse_size(s.stdout), "rc": rc, "rss_kb": rss,
                             "stderr_tail": err.strip().splitlines()[-1] if err.strip() else ""})
            entry["targets"][tname] = cell
        # bare metal
        elf, log = bm_build(cpath, work, name)
        cell = {"builds": elf is not None, "first_error": first_error(log)}
        if elf:
            s = sh([BM["size"], str(elf)])
            rc, out, err, peak = bm_run(elf, work)
            cell.update({"runs": rc == 0, "matches_cpython": out == py_out,
                         "first_diff": "" if out == py_out else _diff(py_out, out),
                         "size": parse_size(s.stdout), "rc": rc,
                         "heap_peak_bytes": peak,
                         "compile_warnings": len(re.findall(r"warning:", log))})
        entry["targets"]["arm-none-eabi"] = cell
        results["programs"][name] = entry

    # ---- 2. census probes (one OS subsystem each)
    for probe in CENSUS:
        if probe == "mmap_big":
            continue  # handled below with its own generated file
        src = PROGS / "census" / ("census_" + probe + ".py")
        if not src.exists():
            continue
        exe, cpath, log = ail_build(src, work, "census_" + probe)
        cell = {"ail_builds": exe is not None}
        if exe:
            elf, log2 = bm_build(cpath, work, "census_" + probe)
            cell["bare_builds"] = elf is not None
            cell["first_error"] = first_error(log2)
            cell["undefined"] = sorted(set(re.findall(r"undefined reference to `([^']+)'", log2)))
            if elf:
                rc, out, err, peak = bm_run(elf, work)
                cell.update({"runs": rc == 0, "stdout": out, "heap_peak_bytes": peak})
            m = re.search(r"program\.c:(\d+):\d+:", cell["first_error"])
            if "fatal error:" in cell["first_error"]:
                header = cell["first_error"].split("fatal error:")[1].split(":")[0].strip()
                known = {"sys/socket.h": ("ail_tcpsocket_connect", "cruntime.py"),
                         "sys/mman.h": ("ail_win_map / ail_win_drop", "cruntime.py")}
                if header in known:
                    cell["c_function"], cell["runtime_file"] = known[header]
            elif m and cpath:
                cell["c_function"] = enclosing_function(cpath, int(m.group(1)))
                cell["runtime_file"] = runtime_file(cell["c_function"])
            if probe == "par":
                cell["c_function"] = "ail_par_job / ail_par_pool_main (parallel runtime)"
                cell["runtime_file"] = "cruntime.py"
        else:
            cell["first_error"] = first_error(log)
        results["census"][probe] = cell

    results["census"]["mmap_big"] = mmap_census(work)

    # ---- 3. RAM: native + qemu RSS is in the target cells; jitter below
    if not args.skip_jitter:
        iters = 2000 if args.quick else 20000
        results["jitter"] = jitter(work, iters, args.reps)
    else:
        old = HERE / "results.json"
        if old.exists():
            try:
                results["jitter"] = json.loads(old.read_text(encoding="utf8")).get("jitter", {})
            except ValueError:
                results["jitter"] = {}
            if results["jitter"].get("ail_build_note", "").startswith("{"):
                results["jitter"]["ail_build_note"] = ""

    text = json.dumps(results, indent=1).replace(str(work) + "/", "")
    text = re.sub(r"[\w./-]*/program\.c", "program.c", text)
    (HERE / "results.json").write_text(text + "\n", encoding="utf8")
    print("wrote", HERE / "results.json")
    print("work dir", work)
    return 0


def enclosing_function(cpath, line_no):
    """The C function around a generated-C line (definitions end with `{`)."""
    lines = cpath.read_text(encoding="utf8", errors="replace").splitlines()
    for i in range(min(line_no, len(lines)) - 1, -1, -1):
        line = lines[i]
        m = re.match(r"^[A-Za-z_][\w \*]*\b([A-Za-z_]\w*)\s*\(", line)
        if not m:
            continue
        head = line.split("/*")[0].rstrip()
        tail = head[-1:] if head else ""
        if tail == "{" or (i + 1 < len(lines) and lines[i + 1].strip() == "{"):
            return m.group(1)
    return ""


def runtime_file(function):
    """The AIL runtime Python module that defines a generated C function."""
    if not function:
        return ""
    core = REPO / "AIL_CURRENT" / "python" / "pkg-v12"
    p = sh(["grep", "-rl", "--include=*.py", function, str(core)])
    files = sorted(set(p.stdout.split()))
    return Path(files[0]).name if files else ""


def mmap_census(work):
    """A >1 MiB read_bytes() scanned forward selects the mmap window runtime."""
    (work / "big.bin").write_bytes(bytes(range(256)) * (2 * 1024 * 1024 // 256))
    src = PROGS / "census" / "census_mmap_big.py"
    exe, cpath, log = ail_build(src, work, "mmap_big")
    cell = {"ail_builds": exe is not None,
            "note": "read_bytes() of a 2 MiB file iterated forward selects the IR window (mmap) runtime"}
    if exe:
        elf, log2 = bm_build(cpath, work, "mmap_big")
        cell["bare_builds"] = elf is not None
        cell["first_error"] = first_error(log2)
        cell["undefined"] = sorted(set(re.findall(r"undefined reference to `([^']+)'", log2)))
        cell["mmap_refs_in_c"] = cpath.read_text(encoding="utf8", errors="replace").count("mmap")
        cell["c_function"] = "ail_win_map / ail_win_drop"
        cell["runtime_file"] = "cruntime.py"
    else:
        cell["first_error"] = first_error(log)
    return cell


def _diff(a, b):
    al, bl = a.splitlines(), b.splitlines()
    for i in range(min(len(al), len(bl))):
        if al[i] != bl[i]:
            return "line %d: %r != %r" % (i + 1, al[i], bl[i])
    return "length %d != %d" % (len(al), len(bl))


if __name__ == "__main__":
    raise SystemExit(main())
