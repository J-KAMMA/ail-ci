"""Build the toy kernel: AIL modules -> objects, boot.S -> object, link with linker.ld -> ELF.

    python3 AIL_CURRENT/freestanding/kernel/build.py OUTDIR

Writes OUTDIR/kernel.elf (ELF64, for GRUB: `multiboot2 /boot/kernel.elf`) and OUTDIR/kernel32.elf (the
same image as ELF32, which is what QEMU's -kernel loader accepts), and prints the QEMU command.
Nothing here is downloaded or installed: it needs python3, gcc, ld and objcopy.

Run it (QEMU is not needed to build):

    qemu-system-x86_64 -kernel OUTDIR/kernel32.elf -serial stdio -display none -no-reboot \
        -device isa-debug-exit,iobase=0xf4,iosize=0x04 ; echo "qemu exit status $? (33 = kernel reached its end)"

Drop `-display none` to see the VGA text window as well.
"""
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                        # AIL_CURRENT
CLI = ROOT / 'ail_chatgpt.py'
AIL_MODULES = [HERE / 'console.py', HERE / 'idt.py', HERE.parent / 'pagealloc.py', HERE / 'kmain.py']
# Code that can be interrupted needs no red zone; the generated C is non-PIE, general-register only.
AIL_FS_CFLAGS = '-mno-red-zone -mgeneral-regs-only -fno-pic -fno-pie'
QEMU = ('qemu-system-x86_64 -kernel {kernel} -serial stdio -display none -no-reboot '
        '-device isa-debug-exit,iobase=0xf4,iosize=0x04')


def run(cmd, env=None):
    result = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, env=env)
    if result.returncode:
        raise SystemExit('%s\n%s%s' % (' '.join(shlex.quote(str(c)) for c in cmd), result.stdout, result.stderr))
    return result


def build(out, cc=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cc = cc or os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
    env = dict(os.environ, AIL_FS_CFLAGS=os.environ.get('AIL_FS_CFLAGS', AIL_FS_CFLAGS))
    objects = []
    for source in AIL_MODULES:
        obj = out / (source.stem + '.o')
        for stale in (obj, obj.with_suffix('.h')):
            if stale.exists():
                stale.unlink()
        run([sys.executable, '-B', CLI, 'compile', '--freestanding', source, '-o', obj], env)
        objects.append(obj)
    boot = out / 'boot.o'
    run([cc, '-ffreestanding', '-mno-red-zone', '-fno-pic', '-fno-pie', '-c', HERE / 'boot.S', '-o', boot])
    elf = out / 'kernel.elf'
    run([cc, '-ffreestanding', '-nostdlib', '-static', '-no-pie', '-T', HERE / 'linker.ld', '-o', elf, boot, *objects,
         '-Wl,-z,max-page-size=0x1000', '-Wl,-z,noexecstack', '-Wl,--build-id=none', '-Wl,--no-warn-rwx-segments'])
    elf32 = out / 'kernel32.elf'
    run(['objcopy', '-O', 'elf32-i386', elf, elf32])
    return {'elf': elf, 'elf32': elf32, 'objects': objects + [boot]}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit(__doc__)
    done = build(argv[0])
    print('built %s and %s' % (done['elf'], done['elf32']))
    print(QEMU.format(kernel=done['elf32']))


if __name__ == '__main__':
    main()
