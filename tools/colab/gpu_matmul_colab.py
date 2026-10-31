#!/usr/bin/env python3
"""Colab / GPU-box script: build AIL, run the GPU tests, and benchmark the GPU matrix multiply.  Owner-started; CI never runs it.

Run it in a Colab cell (a GPU runtime: L4 for the checks, A100 for the f64 bench):

    !wget -q https://raw.githubusercontent.com/J-KAMMA/ail-ci/gpu-matmul/tools/colab/gpu_matmul_colab.py
    !python3 gpu_matmul_colab.py                    # clone, tests, bench (about 5 to 15 minutes)

or from a checkout:  python3 tools/colab/gpu_matmul_colab.py --repo . --no-clone

What it does, in order (it stops early, with a message, when a step cannot work):
 1. prints the runtime (nvidia-smi, OS, Python) and stops when there is no GPU (use --allow-software to run on lavapipe: the checks
    still mean something, the timings do not);
 2. installs gcc, the Vulkan loader and vulkaninfo (apt), makes sure an NVIDIA Vulkan driver is visible (see vulkan_setup) and
    prints the Vulkan device list;
 3. clones https://github.com/J-KAMMA/ail-ci at --ref (default gpu-matmul);
 4. runs the GPU tests with AIL_GPU_REQUIRE_DEVICE=1 and AIL_GPU_DEVICE=<nvidia>: test_ail_gpu_mm (this PR) and, unless --tests mm,
    the older GPU modules g1..g5; prints PASS/FAIL per module and the tail of every failure;
 5. benchmarks matmul f32 and f64 at 512, 1024, 2048, 4096 (square), end to end as a caller sees it (host arrays in, host array out,
    median of 3 to 5 runs after one warm-up that pays the pipeline build and the device self-test):
        gpu exact   the default kernel, bit-identical to the CPU kernel (checked here at every size against the CPU kernel when it ran)
        gpu fast    the opt-in tiled kernel, NOT bit-identical (reports its max relative difference from the exact result)
        cpu exact   the C CPU kernel of the same summation order, one thread, -O2 (skipped above --cpu-max, default 2048)
        numpy       numpy.matmul (BLAS, all cores of the VM)  [NOT the same order: for scale only]
        ail cpu     an AIL-compiled program calling ta.matmul on the CPU (f64), when the checked-out ref can build one; else "n/a"
    and prints one table per dtype plus a JSON line, and writes /content/gpu_matmul_report.txt (or ./gpu_matmul_report.txt).

Exit status 0 when every test passed and every exact-kernel bench check matched, 1 otherwise.
Only the GPU timings include the copies to and from the device (the runtime copies through host-visible buffers); no number here
is a claim about AIL's speed: the script just measures.
"""
import argparse
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO_URL = 'https://github.com/J-KAMMA/ail-ci'
SIZES = (512, 1024, 2048, 4096)


def sh(cmd, check=False, timeout=None, env=None, quiet=False):
    if not quiet:
        print('$', cmd if isinstance(cmd, str) else ' '.join(cmd), flush=True)
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout, env=env)
    if check and r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('command failed (%d): %s' % (r.returncode, cmd))
    return r


def have(cmd):
    return shutil.which(cmd) is not None


def apt(*pkgs):
    if not have('apt-get'):
        return False
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive')
    sudo = '' if os.geteuid() == 0 else 'sudo -n '
    r = sh('%sapt-get install -y --no-install-recommends %s' % (sudo, ' '.join(pkgs)), env=env)
    return r.returncode == 0


def runtime_report():
    print('== runtime')
    print(platform.platform(), '| python', platform.python_version())
    r = sh('nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader', quiet=True) if have('nvidia-smi') else None
    gpu = r.stdout.strip() if r is not None and r.returncode == 0 else ''
    print('GPU:', gpu or 'none (nvidia-smi missing or no device)')
    return gpu


def vulkan_devices():
    if not have('vulkaninfo'):
        return []
    r = sh('vulkaninfo --summary', quiet=True)
    return re.findall(r'deviceName\s*=\s*(.+)', r.stdout)


def vulkan_setup(gpu_line, allow_software):
    """Make an NVIDIA Vulkan device visible.  Colab images carry the compute driver; the Vulkan part (libGLX_nvidia / libnvidia-gl and
    an ICD file) is sometimes missing.  Steps, each re-checked: (1) as is; (2) write nvidia_icd.json for a libGLX_nvidia that exists;
    (3) apt install the libnvidia-gl package of the driver's major version.  [Unverified on the current Colab image: it worked on a
    T4 with driver 580 on 2026-10-30 (GPU.md 6.3).]"""
    apt('gcc', 'libc6-dev', 'libvulkan1', 'vulkan-tools')
    devs = vulkan_devices()
    print('Vulkan devices:', devs or 'none')
    if any('nvidia' in d.lower() or 'a100' in d.lower() or 'l4' in d.lower() or 'tesla' in d.lower() for d in devs):
        return True
    if gpu_line:
        so = sh('ldconfig -p | grep -E "libGLX_nvidia|libnvidia-vulkan" | head -3', quiet=True).stdout.strip()
        icd_dir = Path('/usr/share/vulkan/icd.d')
        if 'libGLX_nvidia' in so and not (icd_dir / 'nvidia_icd.json').exists():
            lib = re.search(r'=>\s*(\S+libGLX_nvidia\S*)', so)
            if lib:
                try:
                    icd_dir.mkdir(parents=True, exist_ok=True)
                    (icd_dir / 'nvidia_icd.json').write_text(json.dumps(
                        {'file_format_version': '1.0.0', 'ICD': {'library_path': lib.group(1), 'api_version': '1.3.0'}}))
                    print('wrote', icd_dir / 'nvidia_icd.json')
                except OSError as e:
                    print('could not write the ICD file:', e)
        devs = vulkan_devices()
        if not any('nvidia' in d.lower() for d in devs):
            major = gpu_line.split(',')[1].strip().split('.')[0]
            print('trying apt: libnvidia-gl-%s (a package of another minor version than the kernel driver may not load)' % major)
            apt('libnvidia-gl-' + major)
            devs = vulkan_devices()
            print('Vulkan devices:', devs or 'none')
        if any(('nvidia' in d.lower()) or re.search(r'a100|l4|t4|h100|tesla', d.lower()) for d in devs):
            return True
    if allow_software:
        print('NOTE: no NVIDIA Vulkan device found; --allow-software: the tests run on whatever device the loader gives (%s) and the '
              'timings are not GPU timings' % (devs[0] if devs else 'unknown'))
        return True
    print('\nNo NVIDIA Vulkan device is visible, so nothing here can run on the GPU.  AIL has no CUDA backend (GPU.md section 0).')
    print('Check: vulkaninfo --summary ; ls /usr/share/vulkan/icd.d /etc/vulkan/icd.d ; ldconfig -p | grep -i nvidia')
    return False


def clone(args):
    if args.no_clone:
        return Path(args.repo).resolve()
    dest = Path(args.dest)
    if dest.exists():
        shutil.rmtree(dest)
    sh(['git', 'clone', '--depth', '1', '--branch', args.ref, REPO_URL, str(dest)], check=True)
    print('commit', sh(['git', '-C', str(dest), 'rev-parse', 'HEAD'], quiet=True).stdout.strip())
    return dest.resolve()


def run_tests(root, which, device_name):
    print('\n== GPU tests')
    names = {'mm': ['test_ail_gpu_mm'],
             'all': ['test_ail_gpu_mm', 'test_ail_gpu_g1', 'test_ail_gpu_g2', 'test_ail_gpu_g3', 'test_ail_gpu_g4', 'test_ail_gpu_g5']}[which]
    env = dict(os.environ, AIL_GPU_REQUIRE_DEVICE='1')
    if device_name:
        env['AIL_GPU_DEVICE'] = device_name
    results = []
    for n in names:
        path = root / 'AIL_CURRENT' / (n + '.py')
        if not path.is_file():
            results.append((n, 'MISSING', 0.0, ''))
            continue
        t0 = time.time()
        r = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, text=True, env=env, cwd=str(root / 'AIL_CURRENT'))
        dt = time.time() - t0
        tail = (r.stdout + r.stderr)[-1500:]
        results.append((n, 'PASS' if r.returncode == 0 else 'FAIL', dt, tail))
        print('%-22s %-5s %6.1fs' % (n, results[-1][1], dt), flush=True)
        if r.returncode != 0:
            print(tail)
    return results


def cpu_ail_seconds(root, n, tmp):
    """Wall time of an AIL-compiled f64 matmul of n x n on the CPU, or None.  The program is built from the checked-out ref; the fill is
    subtracted by running the same program without the product."""
    src = ('import ail_array as ta\n'
           'n = int(input())\nmode = int(input())\n'
           'a = ta.zeros((n, n), ta.f64)\nb = ta.zeros((n, n), ta.f64)\n'
           'for i in range(n):\n    for j in range(n):\n'
           '        a[i, j] = ((i * 7 + j * 3) % 11) / 4.0 - 1.0\n        b[i, j] = ((i * 5 + j * 9) % 13) / 4.0 - 1.5\n'
           'if mode == 1:\n    c = ta.matmul(a, b)\n    print(c[0, 0])\nelse:\n    print(a[0, 0])\n')
    d = Path(tmp)
    d.mkdir(parents=True, exist_ok=True)
    (d / 'mm.py').write_text(src)
    shutil.copy(root / 'AIL_CURRENT' / 'ail_array.py', d / 'ail_array.py')
    exe = d / 'mm.out'
    if not exe.exists():
        r = subprocess.run([sys.executable, '-B', str(root / 'AIL_CURRENT' / 'ail_chatgpt.py'), 'compile', 'mm.py', '-o', 'mm.out'],
                           capture_output=True, text=True, cwd=str(d))
        if r.returncode != 0 or not exe.exists():
            return None
    try:
        t = {}
        for mode in (0, 1):
            t0 = time.time()
            r = subprocess.run([str(exe)], input='%d\n%d\n' % (n, mode), capture_output=True, text=True, timeout=1800)
            if r.returncode != 0:
                return None
            t[mode] = time.time() - t0
        return max(t[1] - t[0], 0.0)
    except subprocess.TimeoutExpired:
        return None


def make_inputs(n, dtn, np):
    """Two n x n matrices of the dtype as buffers: (A, B, pointer function, as-numpy-or-None)."""
    if np is not None:
        npdt = np.float32 if dtn == 'f32' else np.float64
        rng = np.random.default_rng(n)
        A = np.ascontiguousarray(rng.uniform(-1, 1, (n, n)).astype(npdt))
        B = np.ascontiguousarray(rng.uniform(-1, 1, (n, n)).astype(npdt))
        return A, B, (lambda x: x.ctypes.data), (lambda: np.empty((n, n), npdt))
    import array
    import ctypes
    code = 'f' if dtn == 'f32' else 'd'
    A = array.array(code, ((i * 7919 % 2003) / 1001.0 - 1.0 for i in range(n * n)))
    B = array.array(code, ((i * 104729 % 2011) / 1005.0 - 1.0 for i in range(n * n)))
    return A, B, (lambda x: x.buffer_info()[0]), (lambda: array.array(code, bytes(n * n * (4 if dtn == 'f32' else 8))))


def bench(root, args, device_name):
    try:
        import numpy as np
    except ImportError:
        np = None
        print('numpy is not installed: the numpy column and the difference columns are skipped')
    sys.path[:0] = [str(root / 'AIL_CURRENT' / 'python' / 'pkg-v12'), str(root / 'AIL_CURRENT')]
    import gpu_matmul as gm
    if device_name:
        os.environ['AIL_GPU_DEVICE'] = device_name
    lib = gm._library()
    print('\n== bench (end to end, median of repeats, after one warm-up)')
    rows, ok_all = [], True
    for dtn, dt in (('f32', 1), ('f64', 0)):
        for n in args.sizes:
            A, B, ptr, new_c = make_inputs(n, dtn, np)
            row = {'dtype': dtn, 'n': n}
            flops = 2.0 * n ** 3
            reps = 5 if n <= 1024 else 3
            res = {}
            for label, fast in (('gpu exact', 0), ('gpu fast', 1)):
                C = new_c()
                call = lambda: lib.ail_gpu_matmul(dt, fast, ptr(A), ptr(B), ptr(C), n, n, n)
                used = call()                                    # warm-up: loader, device, pipeline, self-test
                if not used:
                    row[label] = None
                    row[label + ' why'] = lib.ail_gpu_matmul_why().decode()
                    continue
                ts = []
                for _ in range(reps):
                    t0 = time.perf_counter()
                    call()
                    ts.append(time.perf_counter() - t0)
                row[label] = statistics.median(ts)
                res[label] = C.tobytes() if np is None else C.copy()
            if n <= args.cpu_max:
                Cc = new_c()
                ts = []
                for _ in range(1 if n >= 2048 else 3):
                    t0 = time.perf_counter()
                    lib.ail_gpu_matmul_cpu(dt, ptr(A), ptr(B), ptr(Cc), n, n, n)
                    ts.append(time.perf_counter() - t0)
                row['cpu exact'] = statistics.median(ts)
                if 'gpu exact' in res:
                    same = bytes(res['gpu exact'].tobytes() if np is not None else res['gpu exact']) == Cc.tobytes()
                    row['exact == cpu'] = same
                    ok_all &= same
            if np is not None:
                ts = []
                for _ in range(reps):
                    t0 = time.perf_counter()
                    Cn = A @ B
                    ts.append(time.perf_counter() - t0)
                row['numpy'] = statistics.median(ts)
                ref = Cn.astype(np.float64)
                for label, key in (('gpu fast', 'fast max rel diff vs numpy'), ('gpu exact', 'exact max rel diff vs numpy')):
                    if label in res:
                        row[key] = float(np.max(np.abs(res[label] - ref) / np.maximum(np.abs(ref), 1.0)))
            if dtn == 'f64' and n <= args.ail_max:
                row['ail cpu'] = cpu_ail_seconds(root, n, args.work + '/ail')
            row['device'] = lib.ail_gpu_matmul_device().decode()
            rows.append((row, flops))
            print(json.dumps(row), flush=True)
    return rows, ok_all


def table(rows):
    out = []
    for dtn in ('f32', 'f64'):
        out.append('\nmatmul %s, n x n x n, seconds (GFLOP/s), end to end' % dtn)
        out.append('| n | gpu exact | gpu fast | cpu exact (C, 1 thread) | numpy | ail cpu | exact==cpu | fast rel diff |')
        out.append('| --- | --- | --- | --- | --- | --- | --- | --- |')
        for row, flops in rows:
            if row['dtype'] != dtn:
                continue

            def cell(k):
                v = row.get(k)
                if v is None:
                    return 'n/a' if k != 'gpu exact' and k != 'gpu fast' else 'cpu (%s)' % row.get(k + ' why', '?')[:40]
                return '%.4f (%.0f)' % (v, flops / v / 1e9)
            out.append('| %d | %s | %s | %s | %s | %s | %s | %s |' % (
                row['n'], cell('gpu exact'), cell('gpu fast'), cell('cpu exact') if 'cpu exact' in row else 'skipped', cell('numpy'),
                cell('ail cpu') if 'ail cpu' in row else 'skipped', row.get('exact == cpu', 'n/a'),
                '%.1e' % row['fast max rel diff vs numpy'] if 'fast max rel diff vs numpy' in row else 'n/a'))
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--ref', default='gpu-matmul', help='branch or tag of J-KAMMA/ail-ci to test (default gpu-matmul)')
    ap.add_argument('--dest', default='/content/ail-ci' if Path('/content').is_dir() else 'ail-ci')
    ap.add_argument('--repo', default='.', help='with --no-clone: the checkout to use')
    ap.add_argument('--no-clone', action='store_true')
    ap.add_argument('--tests', choices=('mm', 'all'), default='all')
    ap.add_argument('--no-tests', action='store_true')
    ap.add_argument('--no-bench', action='store_true')
    ap.add_argument('--cpu-max', type=int, default=2048, help='largest n for the one-thread C CPU kernel (4096 takes minutes)')
    ap.add_argument('--ail-max', type=int, default=1024, help='largest n for the AIL-compiled CPU baseline (when it builds)')
    ap.add_argument('--allow-software', action='store_true')
    ap.add_argument('--device', default='', help='AIL_GPU_DEVICE substring (default: nvidia when an NVIDIA device is listed)')
    ap.add_argument('--work', default='/tmp/gpu_matmul_work')
    ap.add_argument('--sizes', default=','.join(map(str, SIZES)), help='comma separated n (default 512,1024,2048,4096)')
    args = ap.parse_args()
    args.sizes = [int(x) for x in args.sizes.split(',') if x]

    gpu = runtime_report()
    if not gpu and not args.allow_software:
        print('\nNo GPU runtime.  In Colab: Runtime > Change runtime type > GPU.  (--allow-software runs the checks on lavapipe.)')
        return 1
    if not vulkan_setup(gpu, args.allow_software):
        return 1
    device_name = args.device or ('nvidia' if any('nvidia' in d.lower() for d in vulkan_devices()) else '')
    root = clone(args)

    failed = False
    report = ['gpu: %s' % (gpu or 'none'), 'vulkan: %s' % vulkan_devices(), 'python: %s' % platform.python_version()]
    if sys.version_info[:2] != (3, 12):
        print('NOTE: the AIL tests use CPython 3.12 as their oracle; this is %s. test_ail_gpu_mm does not depend on it; a failure in the '
              'older modules may be this.' % platform.python_version())
    if not args.no_tests:
        res = run_tests(root, args.tests, device_name)
        failed |= any(s != 'PASS' for _, s, _, _ in res)
        report += ['%-22s %s %.1fs' % (n, s, t) for n, s, t, _ in res]
    if not args.no_bench:
        try:
            import numpy  # noqa: F401
        except ImportError:
            sh([sys.executable, '-m', 'pip', 'install', '-q', 'numpy'])
        rows, ok = bench(root, args, device_name)
        failed |= not ok
        t = table(rows)
        print(t)
        report.append(t)
    out = Path('/content' if Path('/content').is_dir() else '.') / 'gpu_matmul_report.txt'
    out.write_text('\n'.join(report) + '\n')
    print('\nreport written to', out)
    print('RESULT:', 'FAIL' if failed else 'OK')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
