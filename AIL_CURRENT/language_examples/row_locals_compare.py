"""Fixed current/candidate row CLI comparison; no adoption or memory claim."""
import argparse
import array
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'language_examples'
sys.path.insert(0, str(ROOT))
import benchmark_current_rows as row

LABELS = ('baseline', 'candidate', 'c', 'rust')
ROWS, COLS, BATCH_RUNS = 65537, 17, 32
STATE = r'''use integer_row_stream;
fn main()->int {
 let reader:binaryfile=open_binary(sys.argv[1],"rb");
 let state=IntegerRowStreamState(int(sys.argv[2]),0,0,b"");
 if int(sys.argv[3])!=0 {state.carry=b"\x01";}
 let output=bytearray(b"");let failed:int=0;
 try {_integer_row_stream_step(reader,state,output,65536);}
 except ValueError {failed=1;}
 write_stdout_bytes((str(failed)+" "+str(state.total)+" "+str(state.column)+" "+str(len(state.carry))+" "+str(reader.tell())+"\n").encode());
 reader.close();write_stdout_bytes(bytes(output));return 0;
}'''
WIDTH = r'''use integer_row_stream;
fn main()->int {
 let reader:binaryfile=open_binary(sys.argv[1],"rb");
 let state=IntegerRowStreamState(9223372036854775807,int(sys.argv[2]),int(sys.argv[3]),b"");
 let output=bytearray();let failed:int=0;
 try {_integer_row_stream_step(reader,state,output,65536);}
 except ValueError {failed=1;}
 write_stdout_bytes((str(failed)+" "+str(state.total)+" "+str(state.column)+" "+str(len(state.carry))+" "+str(reader.tell())).encode());
 write_stdout_bytes(b"\n");reader.close();write_stdout_bytes(bytes(output));return 0;
}'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def observed(process):
    return dict(returncode=process.returncode, stdout_bytes=len(process.stdout), stdout_sha256=digest(process.stdout),
                stderr_bytes=len(process.stderr), stderr_sha256=digest(process.stderr),
                stderr_preview=process.stderr[:2000].decode('utf8', errors='replace'))


def build(work, label, code, gcc, rustc, report, rust=False):
    source = work / (label + ('.rs' if rust else '.c'))
    binary = work / label
    source.write_text(code, encoding='utf8')
    source_before = row.pin(source)
    command = ([str(rustc), '-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'codegen-units=1',
                '-C', 'lto=fat', '--edition=2021', str(source), '-o', str(binary)] if rust else
               [str(gcc), *row.FLAGS, str(source), '-lm', '-o', str(binary)])
    process = subprocess.run(command, capture_output=True, timeout=180)
    report['builds'][label] = dict(command=command, source_before=source_before, actual=observed(process))
    if process.returncode:
        raise ValueError('build failed: ' + label)
    report['builds'][label]['binary_before'] = row.pin(binary)
    return binary


def private_controls(work, variants, gcc, rustc, report):
    hi, lo = (1 << 63) - 1, -(1 << 63)
    cases = [([1, hi], 3, 1, 1, b''), ([hi, 1], 3, hi, 1, b''),
             ([-1, lo], 3, -1, 1, b''), ([lo, -1], 3, lo, 1, b''),
             ([7, 8, 1, hi], 2, 1, 1, b'15\n'), ([7, 8, -1, lo], 2, -1, 1, b'15\n')]
    for variant, directory in variants.items():
        for harness, text in (('state', STATE), ('width', WIDTH)):
            driver = directory / (harness + '.ail')
            driver.write_text(text, encoding='utf8')
            driver_before = row.pin(driver)
            binary = build(work, variant + '_' + harness, row.generated(driver), gcc, rustc, report)
            tests = []
            if harness == 'state':
                for index, (values, cols, total, column, output) in enumerate(cases):
                    data = b''.join(struct.pack('<q', value) for value in values)
                    expected = f'1 {total} {column} 0 {len(data)}\n'.encode() + output
                    tests.append(('caught_' + str(index), data, [str(cols), '0'], 0, expected, b''))
                tests.append(('carry', b'\0' * 7, ['3', '1'], 0, b'0 1 1 0 7\n', b''))
            else:
                tests = [('column_at_max_minus_one', struct.pack('<q', 1), [str(hi - 1), '0'], 0, b'0 0 0 0 8\n1\n', b''),
                         ('fatal_column_increment', struct.pack('<q', 1), [str(hi), '0'], 1, b'', b'integer overflow\r\n' if sys.platform == 'win32' else b'integer overflow\n'),
                         ('caught_before_column_increment', struct.pack('<q', 1), [str(hi), str(hi)], 0,
                          f'1 {hi} {hi} 0 8\n'.encode(), b'')]
            for name, data, argv, code, expected, stderr in tests:
                path = work / (variant + '_' + harness + '_' + name + '.bin')
                path.write_bytes(data)
                before = row.pin(path)
                process = subprocess.run([str(binary), str(path), *argv], capture_output=True, timeout=30)
                passed = (process.returncode, process.stdout, process.stderr) == (code, expected, stderr)
                item = dict(variant=variant, harness=harness, case=name, passed=passed, actual=observed(process),
                            expected_sha256=digest(expected), expected_stderr_sha256=digest(stderr),
                            input_before=before, input_after=row.pin(path))
                report['private_controls'].append(item)
                if not passed or item['input_before'] != item['input_after']:
                    raise ValueError('private-state control failed: ' + variant + '/' + name)
            if driver_before != row.pin(driver):
                raise ValueError('private driver changed')


def timings(work, binaries, report):
    values = array.array('q', ((-1 if index % 2 else 1) * ((1 << 53) + 37 * index + 19)
                              for index in range(ROWS * COLS)))
    path, expected_path = work / 'input.bin', work / 'expected.bin'
    path.write_bytes(values.tobytes())
    expected = row.oracle(values, COLS, 1)
    expected_path.write_bytes(expected)
    del values
    report.update(input_before=row.pin(path), expected_before=row.pin(expected_path))
    try:
        def sample(label, stage, cycle=None, position=None):
            result = dict(program=label, stage=stage, cycle=cycle, position=position, runs=[])
            report['samples'].append(result)
            start = time.perf_counter_ns()
            try:
                for _ in range(BATCH_RUNS):
                    process = subprocess.run([str(binaries[label]), str(path), str(COLS), '1'], capture_output=True, timeout=120)
                    actual = observed(process)
                    actual['output_verified'] = process.stdout == expected
                    result['runs'].append(actual)
                    if process.returncode or not actual['output_verified'] or process.stderr:
                        raise ValueError('timed whole-output control failed: ' + label)
            finally:
                result['wall_ns'] = time.perf_counter_ns() - start
            return result
        for label in LABELS:
            sample(label, 'warmup')
        controls, paired = {}, []
        rotations = [LABELS[index:] + LABELS[:index] for index in range(4)]
        orders = rotations + [order[::-1] for order in rotations]
        for stage in ('aa_before', 'comparison', 'aa_after'):
            if stage == 'comparison':
                for cycle, order in enumerate(orders):
                    group = {label: sample(label, stage, cycle, position) for position, label in enumerate(order)}
                    paired.append({label: group['candidate']['wall_ns'] / group[label]['wall_ns']
                                   for label in ('baseline', 'c', 'rust')})
            else:
                for label in LABELS:
                    ratios = []
                    for _ in range(9):
                        first, second = sample(label, stage), sample(label, stage)
                        ratios.append(second['wall_ns'] / first['wall_ns'])
                    controls[stage + '_' + label] = ratios
            print('finished ' + stage, file=sys.stderr, flush=True)
        report['control_ratios'] = controls
        report['control_intervals'] = {name: [sorted(ratios)[1], sorted(ratios)[7]] for name, ratios in controls.items()}
        report['minimum_sample_ns'] = min(sample['wall_ns'] for sample in report['samples'])
        report['paired_ratios'] = paired
        report['calibration_passed'] = (report['minimum_sample_ns'] >= 50_000_000
            and all(1 / 1.1 <= low <= high <= 1.1 for low, high in report['control_intervals'].values()))
    finally:
        report.update(input_after=row.pin(path), expected_after=row.pin(expected_path))
        report['data_unchanged'] = (report['input_before'] == report['input_after']
                                    and report['expected_before'] == report['expected_after'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, default=HERE/'integer_row_stream_locals_candidate.ail')
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('fresh JSON output required')
    report = dict(status='UNQUALIFIED', quality_passed=False, rows=ROWS, cols=COLS, batch_runs=BATCH_RUNS,
                  profile='32 sequential whole CLI jobs per sample; same LE i64 input; full independent stdout check every run',
                  protocol='nine AA before/after per four programs; eight comparisons: four rotations and their reverse orders; each position twice; >=50ms; rank2..8 reciprocal10%; no adaptive retries',
                  ratio_scope='candidate wall / comparator wall, paired by comparison cycle',
                  interval_scope='min/max of eight ratios; conditional population-median coverage99.21875% under iid stationary continuous observations; assumptions unverified',
                  memory_measurement='not_performed', requested_heap_measurement='not_performed', memory_claim=False,
                  optimization_adopted=False, physical_roof_measured=False, all_purpose_fastest_claim=False,
                  beats_c_and_rust=False, controls_passed=False, builds={}, qualification={}, private_controls=[], samples=[], pins_before={})
    sources = {'baseline': HERE / 'integer_row_stream.ail', 'candidate': args.candidate.resolve()}
    main_source = HERE / 'row_reduce_stream_main.ail'
    watched = [Path(__file__), Path(row.__file__), ROOT / 'ail_chatgpt.py', ROOT / 'ail_syntax.py', ROOT / 'MANIFEST.json',
               main_source, *sources.values(), *sorted((ROOT / 'python/pkg-v12').glob('*.py'))]
    try:
        if sys.platform != 'linux' or sys.byteorder != 'little' or array.array('q').itemsize != 8:
            raise ValueError('Linux little-endian q8 required')
        compiler_paths = {name: shutil.which(name) for name in ('gcc', 'rustc')}
        if not all(compiler_paths.values()):
            raise ValueError('gcc and rustc required')
        gcc, rustc = (Path(compiler_paths[name]).absolute() for name in ('gcc', 'rustc'))
        watched += [gcc, rustc]
        report['pins_before'] = {str(path): row.pin(path) for path in watched}
        report['compiler_versions'] = {}
        for name, compiler in (('gcc', gcc), ('rustc', rustc)):
            process = subprocess.run([str(compiler), '--version'], capture_output=True, timeout=30, check=True)
            report['compiler_versions'][name] = process.stdout.decode(errors='replace')
        sysroot = subprocess.run([str(rustc), '--print', 'sysroot'], capture_output=True, timeout=30, check=True)
        backend = Path(sysroot.stdout.decode().strip()) / 'bin/rustc'
        watched.append(backend)
        report['pins_before'][str(backend)] = row.pin(backend)
        cpu = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {cpu})
        report['cpu'], report['affinity'] = cpu, sorted(os.sched_getaffinity(0))
        with tempfile.TemporaryDirectory(prefix='ail-row-locals-compare-') as temporary:
            work = Path(temporary)
            variants, binaries, copied = {}, {}, []
            try:
                for label, source in sources.items():
                    directory = work / (label + '_sources')
                    directory.mkdir()
                    module, entry = directory / 'integer_row_stream.ail', directory / main_source.name
                    module.write_bytes(source.read_bytes())
                    entry.write_bytes(main_source.read_bytes())
                    variants[label] = directory
                    copied.extend((module, entry))
                    report.setdefault('copied_sources_before', {}).update({str(path): row.pin(path) for path in (module, entry)})
                    if module.read_bytes() != source.read_bytes() or entry.read_bytes() != main_source.read_bytes():
                        raise ValueError('copied source mismatch')
                    binaries[label] = build(work, label, row.generated(entry), gcc, rustc, report)
                binaries['c'] = build(work, 'c', row.REFERENCE_C, gcc, rustc, report)
                binaries['rust'] = build(work, 'rust', row.REFERENCE_RUST, gcc, rustc, report, rust=True)
                for label, binary in binaries.items():
                    controls = row.qualify(binary, work, label)
                    report['qualification'][label] = controls
                    if len(controls) != 20 or not all(item['passed'] and item.get('input_unchanged', True) for item in controls):
                        raise ValueError('public boundary control failed: ' + label)
                private_controls(work, variants, gcc, rustc, report)
                report['controls_passed'] = True
                timings(work, binaries, report)
            finally:
                report['copied_sources_after'] = {str(path): row.pin(path) for path in copied}
                for label, entry in report['builds'].items():
                    source = work / (label + ('.rs' if label == 'rust' else '.c'))
                    binary = work / label
                    if source.is_file():
                        entry['source_after'] = row.pin(source)
                    if binary.is_file():
                        entry['binary_after'] = row.pin(binary)
            report['artifacts_unchanged'] = (report['copied_sources_before'] == report['copied_sources_after']
                and all(entry['source_before'] == entry['source_after'] and entry['binary_before'] == entry['binary_after']
                        for entry in report['builds'].values()))
            if not report['artifacts_unchanged']:
                raise ValueError('copied/generated source or binary changed')
        report['pins_after'] = {str(path): row.pin(path) for path in watched}
        if report['pins_before'] != report['pins_after'] or not report['data_unchanged']:
            raise ValueError('source/compiler/input/expected changed')
        if report['calibration_passed']:
            ratios = {label: [pair[label] for pair in report['paired_ratios']] for label in ('baseline', 'c', 'rust')}
            report['paired_summary'] = {label: dict(median=statistics.median(values), interval=[min(values), max(values)])
                                        for label, values in ratios.items()}
            report.update(status='QUALIFIED', quality_passed=True,
                          beats_c_and_rust=all(report['paired_summary'][label]['interval'][1] < 1 for label in ('c', 'rust')))
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
        report.update(status='FAILED', quality_passed=False, failure=str(error), beats_c_and_rust=False)
    finally:
        try:
            report['pins_after'] = {str(path): row.pin(path) for path in watched}
        except OSError as error:
            report.update(status='FAILED', quality_passed=False, pin_failure=str(error), beats_c_and_rust=False)
        if report.get('pins_after') != report['pins_before']:
            report.update(status='FAILED', quality_passed=False, pin_failure='source/compiler changed', beats_c_and_rust=False)
        if not report['quality_passed']:
            report.pop('paired_summary', None)
        with args.output.open('x', encoding='utf8') as output:
            json.dump(report, output, indent=2)
            output.write('\n')
    print(json.dumps({key: report[key] for key in ('status', 'quality_passed', 'beats_c_and_rust', 'memory_measurement')}))
    return 0 if report['quality_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
