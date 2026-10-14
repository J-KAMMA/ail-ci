"""Owned Linux x86-64 PC-sampling qualification; estimates, never adoption.

SIGPROF attributes sampled PCs, not causal costs. Its clock includes user and
system CPU. Debug line attribution, startup, sampler overhead, parent validation,
and unsampled short intervals limit the process-CPU/wall-adjusted estimate.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile

import row_locals_compare as compare

row = compare.row
HERE, ROOT = compare.HERE, compare.ROOT


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pins(paths):
    return {str(path): row.pin(path) for path in paths}


def command(argv, report, key, **kwargs):
    item = dict(command=list(map(str, argv)), status='STARTED')
    report['operations'][key] = item
    try:
        result = subprocess.run(argv, capture_output=True, timeout=180, **kwargs)
    except Exception as error:
        item.update(status='ERROR', error=str(error))
        raise
    item.update(status='RETURNED', actual=compare.observed(result))
    if result.returncode:
        raise ValueError('operation failed: ' + key)
    return result


def original_and_debug(work, gcc, objcopy, report):
    source = work / 'current.c'
    source.write_text(row.generated(HERE / 'row_reduce_stream_main.ail'), encoding='utf8')
    binaries, texts, copies = {}, [], []
    for label, extra in (('baseline', []), ('candidate', ['-g'])):
        binary = work / label
        command([str(gcc), *row.FLAGS, *extra, str(source), '-lm', '-o', str(binary)],
                report, 'build_' + label)
        section = work / (label + '.text')
        section_copy = work / (label + '.section-copy.elf')
        command([str(objcopy), '--dump-section', '.text=' + str(section), str(binary), str(section_copy)],
                report, 'text_' + label)
        copies.append(section_copy)
        binaries[label] = binary
        texts.append(section)
    same = texts[0].read_bytes() == texts[1].read_bytes()
    report['text_identity'] = dict(passed=same, baseline=row.pin(texts[0]), candidate=row.pin(texts[1]),
                                   same_c_filename=str(source))
    if not same:
        raise ValueError('original/debug .text differs')
    return binaries, [source, *texts, *copies, *binaries.values()]


def timed(work, binaries, library, report):
    import resource
    original_run, original_observed = subprocess.run, compare.observed
    report_paths = []
    report['sampler_report_paths'] = report_paths

    def run(argv, **kwargs):
        label = next(name for name, path in binaries.items() if str(path) == str(argv[0]))
        output = None
        if label == 'candidate':
            output = work / f'pc-{len(report_paths):05d}.txt'
            report_paths.append(str(output))
            kwargs['env'] = dict(os.environ, LD_PRELOAD=str(library), AIL_PC_SAMPLE_OUT=str(output))
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        result = original_run(argv, **kwargs)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        result.cpu_facts = dict(user_cpu_ns=round((after.ru_utime - before.ru_utime) * 1e9),
                                system_cpu_ns=round((after.ru_stime - before.ru_stime) * 1e9))
        if output is not None:
            result.cpu_facts['sampler_report'] = str(output)
        return result

    def observed(result):
        return dict(original_observed(result), **result.cpu_facts)

    try:
        subprocess.run, compare.observed = run, observed
        compare.timings(work, binaries, report)
    finally:
        subprocess.run, compare.observed = original_run, original_observed
    return report_paths


def load_segments(binary):
    data = binary.read_bytes()
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('ELF64 little-endian binary required')
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    if header[2] != 62 or header[1] not in (2, 3) or header[9] != 56:
        raise ValueError('ELF x86-64 executable/shared image required')
    offset, count = header[5], header[10]
    if not count or offset + count * 56 > len(data):
        raise ValueError('invalid ELF program header bounds')
    segments = []
    for index in range(count):
        kind, flags, file_offset, address, _, size, memory, _ = struct.unpack_from('<IIQQQQQQ', data, offset + index * 56)
        if kind == 1:
            if size > memory or file_offset + size > len(data):
                raise ValueError('invalid PT_LOAD bounds')
            segments.append(dict(offset=file_offset, address=address, size=size, flags=flags))
    if not any(segment['flags'] & 1 for segment in segments):
        raise ValueError('no executable PT_LOAD')
    return segments


def mappings(text, binary):
    own = []
    for line in text.splitlines():
        fields = line.split(None, 5)
        if len(fields) < 6 or 'x' not in fields[1] or fields[5] != str(binary.resolve()):
            continue
        start, end = (int(value, 16) for value in fields[0].split('-'))
        own.append((start, end, int(fields[2], 16)))
    if not own:
        raise ValueError('sample maps lack executable debug binary')
    return own


def elf_address(pc, own, segments):
    for start, end, offset in own:
        if start <= pc < end:
            position = offset + pc - start
            for segment in segments:
                if segment['flags'] & 1 and segment['offset'] <= position < segment['offset'] + segment['size']:
                    return segment['address'] + position - segment['offset']
            raise ValueError('own executable PC outside file-backed PT_LOAD')
    return None


def helper_ranges(source):
    code = source.read_text(encoding='utf8')
    # Mask strings/comments while retaining line numbers and brace positions.
    masked = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda match: re.sub(r'[^\n]', ' ', match.group()), code, flags=re.S)
    ranges = []
    pattern = r'^static[^\n;{}]*?\b(ail_obj_(?:retain|release|store_\w+))\s*\([^;{}]*\)\s*\{'
    for match in re.finditer(pattern, masked, re.M):
        depth = 1
        end = match.end()
        while depth and end < len(masked):
            depth += (masked[end] == '{') - (masked[end] == '}')
            end += 1
        if depth:
            raise ValueError('unbalanced RC helper braces')
        ranges.append(dict(helper=match[1], first=code.count('\n', 0, match.start()) + 1,
                           last=code.count('\n', 0, end) + 1))
    if not {'ail_obj_retain', 'ail_obj_release'} <= {item['helper'] for item in ranges}:
        raise ValueError('managed RC helper definitions missing')
    return ranges


def symbolize(binary, source, addresses, addr2line, report):
    if not addresses:
        raise ValueError('no sampled own-binary PCs')
    process = command([str(addr2line), '-a', '-f', '-i', '-e', str(binary)], report, 'addr2line',
                      input=''.join(f'0x{address:x}\n' for address in sorted(addresses)).encode('ascii'))
    groups, current = {}, None
    for line in process.stdout.decode('utf8', errors='replace').splitlines():
        if re.fullmatch(r'0x[0-9a-fA-F]+', line):
            current = int(line, 16)
            groups[current] = []
        elif current is not None:
            groups[current].append(line)
        elif line:
            raise ValueError('unexpected addr2line prefix')
    if set(groups) != set(addresses):
        raise ValueError('addr2line address set differs')
    ranges = helper_ranges(source)
    report['rc_source_ranges'] = ranges
    classified = {}
    for address, lines in groups.items():
        if len(lines) % 2:
            raise ValueError('incomplete addr2line inline frame')
        frames, helpers, resolved = [], [], False
        for function, location in zip(lines[::2], lines[1::2]):
            frame = dict(function=function, location=location)
            frames.append(frame)
            match = re.match(r'^(.*):(\d+)(?:\s|$)', location)
            if match and Path(match[1]).resolve() == source.resolve():
                number = int(match[2])
                resolved = resolved or number > 0
                helpers.extend(item['helper'] for item in ranges
                               if item['helper'] == function and item['first'] <= number <= item['last'])
        classified[address] = dict(frames=frames, helpers=list(dict.fromkeys(helpers)), resolved_source=resolved)
    report['symbolized_pcs'] = {hex(address): facts for address, facts in classified.items()}
    return classified


def collect(paths, binary, source, addr2line, report):
    segments = load_segments(binary)
    report['elf_pt_load'] = segments
    histogram = Counter()
    external = 0
    raw = report.setdefault('raw_reports', [])
    valid = True
    for path in paths:
        item = dict(path=str(path), status='UNREAD')
        raw.append(item)
        try:
            before = pins((path,))
            report_text = path.read_text(encoding='ascii')
            item.update(report_text=report_text, pins_before=before)
            maps_path = Path(str(path) + '.maps')
            before.update(pins((maps_path,)))
            text = maps_path.read_text(encoding='utf8')
            item['maps'] = text
            lines = report_text.splitlines()
            header = json.loads(lines[0])
            pcs = [int(line, 16) for line in lines[1:]]
            item.update(header=header, pcs=[hex(pc) for pc in pcs], maps=text, pins_before=before)
            if (header.get('schema') != 'ail.pc_sample/1' or header.get('status') != 'ok'
                    or header.get('dropped') != 0 or header.get('interval_us') != 1000
                    or type(header.get('count')) is not int or header['count'] != len(pcs)
                    or not 0 < len(pcs) <= 65536 or type(header.get('pid')) is not int or header['pid'] <= 0
                    or any(not 0 < pc < 1 << 64 for pc in pcs)):
                raise ValueError('sampler header/count/status invalid')
            own = mappings(text, binary)
            for pc in pcs:
                address = elf_address(pc, own, segments)
                if address is None:
                    external += 1
                else:
                    histogram[address] += 1
            item['pins_after'] = pins((path, Path(str(path) + '.maps')))
            if item['pins_before'] != item['pins_after']:
                raise ValueError('sampler report/maps changed')
            item['status'] = 'VALID'
        except (OSError, ValueError, IndexError, struct.error) as error:
            item.update(status='INVALID', error=str(error))
            valid = False
    count = sum(histogram.values()) + external
    report['sampling_valid'] = valid and bool(paths) and count >= 500
    report['sample_counts'] = dict(total=count, own_binary=sum(histogram.values()),
                                   external_or_unmapped=external, reports=len(paths))
    report['own_pc_histogram'] = {hex(pc): count for pc, count in histogram.items()}
    if not report['sampling_valid']:
        return
    symbols = symbolize(binary, source, histogram, addr2line, report)
    rc = sum(count for pc, count in histogram.items() if symbols[pc]['helpers'])
    helpers = Counter()
    for pc, count in histogram.items():
        if symbols[pc]['helpers']:
            helpers[symbols[pc]['helpers'][0]] += count
    unresolved = sum(count for pc, count in histogram.items() if not symbols[pc]['resolved_source'])
    report['sample_counts'].update(rc=rc, own_non_rc=sum(histogram.values()) - rc,
                                   own_unresolved_source=unresolved, helper_counts=dict(helpers))
    report['sampling_valid'] = sum(histogram.values()) > unresolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('fresh JSON output required')
    report = dict(schema='ail.row-cpu-profile/1', status='UNQUALIFIED', quality_passed=False,
                  profile_label='candidate is current debug twin plus owned sampler; no candidate optimization',
                  physical_roof_measured=False, optimization_adopted=False, causal_cost_claim=False,
                  limitations=__doc__.strip(), operations={}, builds={}, qualification={}, samples=[], pins_before={})
    watched = [Path(__file__), Path(compare.__file__), Path(row.__file__), HERE / 'row_cpu_sampler.c',
               HERE / 'integer_row_stream.ail', HERE / 'row_reduce_stream_main.ail', ROOT / 'ail_chatgpt.py',
               ROOT / 'ail_syntax.py', ROOT / 'MANIFEST.json', *sorted((ROOT / 'python/pkg-v12').glob('*.py'))]
    try:
        if sys.platform != 'linux' or sys.byteorder != 'little' or __import__('array').array('q').itemsize != 8:
            raise ValueError('Linux little-endian q8 required')
        if os.uname().machine != 'x86_64':
            raise ValueError('x86-64 sampling required')
        if os.environ.get('LD_PRELOAD') or os.environ.get('AIL_PC_SAMPLE_OUT'):
            raise ValueError('inherited preload/sampler environment is unqualified')
        tools = {name: Path(shutil.which(name) or '') for name in ('gcc', 'rustc', 'objcopy', 'addr2line')}
        if not all(path.is_file() for path in tools.values()):
            raise ValueError('gcc/rustc/objcopy/addr2line required')
        tools = {name: path.absolute() for name, path in tools.items()}
        watched += list(tools.values())
        report['pins_before'] = pins(watched)
        report['compiler_versions'] = {name: command([str(path), '--version'], report, 'version_' + name).stdout.decode(errors='replace')
                                       for name, path in tools.items()}
        backend = Path(command([str(tools['rustc']), '--print', 'sysroot'], report, 'rust_sysroot').stdout.decode().strip()) / 'bin/rustc'
        watched.append(backend)
        report['pins_before'][str(backend)] = row.pin(backend)
        cpu = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {cpu})
        report.update(cpu=cpu, affinity=sorted(os.sched_getaffinity(0)), rows=compare.ROWS,
                      cols=compare.COLS, batch_runs=compare.BATCH_RUNS,
                      protocol='existing 32-job samples; four warmups; nine AA pairs before/after per four programs; eight rotated/reversed comparisons; >=50ms; no retries',
                      observer_gate='eight profile/baseline paired wall ratios: rank2..8 <=1.1')
        with tempfile.TemporaryDirectory(prefix='ail-row-cpu-profile-') as directory:
            work = Path(directory)
            artifacts = []
            try:
                binaries, artifacts = original_and_debug(work, tools['gcc'], tools['objcopy'], report)
                source = work / 'current.c'
                library = work / 'sampler.so'
                command([str(tools['gcc']), '-std=gnu11', '-O2', '-shared', '-fPIC',
                         str(HERE / 'row_cpu_sampler.c'), '-o', str(library)], report, 'sampler_build')
                artifacts.append(library)
                binaries['c'] = compare.build(work, 'c', row.REFERENCE_C, tools['gcc'], tools['rustc'], report)
                binaries['rust'] = compare.build(work, 'rust', row.REFERENCE_RUST, tools['gcc'], tools['rustc'], report, rust=True)
                artifacts += [work / 'c.c', work / 'rust.rs', binaries['c'], binaries['rust']]
                report['artifacts_before'] = pins(artifacts)
                for label, binary in binaries.items():
                    controls = row.qualify(binary, work, label)
                    report['qualification'][label] = controls
                    if len(controls) != 20 or not all(item['passed'] and item.get('input_unchanged', True) for item in controls):
                        raise ValueError('boundary qualification failed: ' + label)
                report['controls_passed'] = True
                try:
                    timed(work, binaries, library, report)
                finally:
                    collect([Path(path) for path in report.get('sampler_report_paths', [])],
                            binaries['candidate'], source, tools['addr2line'], report)
                report['protocol_counts'] = dict(samples=len(report['samples']),
                    runs=sum(len(sample['runs']) for sample in report['samples']),
                    sampler_reports=len(report['sampler_report_paths']))
                report['protocol_complete'] = report['protocol_counts'] == dict(samples=180, runs=5760, sampler_reports=1440)
                ratios = sorted(pair['baseline'] for pair in report['paired_ratios'])
                if len(ratios) != 8:
                    raise ValueError('eight observer pairs required')
                report['observer_interval'] = [ratios[1], ratios[7]]
                report['observer_passed'] = len(ratios) == 8 and ratios[7] <= 1.1
            finally:
                if 'artifacts_before' in report:
                    report['artifacts_after'] = pins(artifacts)
                    report['artifacts_unchanged'] = report['artifacts_before'] == report['artifacts_after']
        report['pins_after'] = pins(watched)
        qualified = (report.get('controls_passed') and report.get('protocol_complete')
                     and report.get('calibration_passed') and report.get('observer_passed')
                     and report.get('sampling_valid') and report.get('data_unchanged')
                     and report.get('artifacts_unchanged') and report['pins_before'] == report['pins_after'])
        if qualified:
            selected = [sample for sample in report['samples'] if sample['program'] == 'candidate']
            user = sum(run['user_cpu_ns'] for sample in selected for run in sample['runs'])
            system = sum(run['system_cpu_ns'] for sample in selected for run in sample['runs'])
            wall = sum(sample['wall_ns'] for sample in selected)
            count = report['sample_counts']
            fraction = count['rc'] / count['total']
            if user <= 0 or wall <= 0 or not count['own_binary']:
                raise ValueError('CPU/wall attribution lacks observations')
            report['estimates'] = dict(sampled_rc_cpu_fraction=fraction,
                                       child_user_cpu_ns=user, child_system_cpu_ns=system,
                                       profiled_batch_wall_ns=wall, user_cpu_over_batch_wall=user / wall,
                                       process_cpu_over_batch_wall=(user + system) / wall,
                                       rc_process_cpu_adjusted_wall_share=fraction * (user + system) / wall,
                                       user_only_sensitivity=fraction * user / wall,
                                       sampling_clock='ITIMER_PROF: user plus system CPU',
                                       scope='all profiled stages; debug inline source attribution; estimates only')
            report.update(status='QUALIFIED', quality_passed=True)
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError, struct.error) as error:
        report.update(status='UNQUALIFIED', failure=str(error), quality_passed=False)
    finally:
        try:
            report['pins_after'] = pins(watched)
            if report['pins_before'] != report['pins_after']:
                report.update(status='UNQUALIFIED', quality_passed=False, pin_failure='source/compiler/sampler changed')
        except OSError as error:
            report.update(status='UNQUALIFIED', quality_passed=False, pin_failure=str(error))
        if not report['quality_passed']:
            report.pop('estimates', None)
        with args.output.open('x', encoding='utf8') as handle:
            json.dump(report, handle, indent=2)
            handle.write('\n')
    print(json.dumps(dict(status=report['status'], quality_passed=report['quality_passed'],
                          output=str(args.output), samples=report.get('sample_counts'))))
    return 0 if report['quality_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
