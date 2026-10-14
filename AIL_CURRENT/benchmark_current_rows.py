"""Fixed current-row baseline pricing; empirical references, never speed adoption."""
import argparse
import array
import hashlib
import io, itertools
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
import time

ROOT = Path(__file__).resolve().parent
HERE = ROOT / 'language_examples'
sys.path[:0] = [str(ROOT), str(ROOT / 'python/pkg-v12')]
from ail_chatgpt import _load_sources
import pyc
import pyfunc

FLAGS = ['-std=gnu11', '-O3', '-march=native', '-flto']
BATCH_RUNS = 16
LABELS = ('ail', 'c', 'rust')
COMPARISON_ORDERS = (*itertools.permutations(LABELS), LABELS, LABELS[1:]+LABELS[:1], LABELS[2:]+LABELS[:2])

HEADER = r'''#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#ifdef _WIN32
#include <windows.h>
static uint64_t profile_now(void) {
 LARGE_INTEGER counter, frequency;
 if(!QueryPerformanceFrequency(&frequency) || !QueryPerformanceCounter(&counter)) __builtin_trap();
 return (uint64_t)(counter.QuadPart/frequency.QuadPart)*UINT64_C(1000000000)
       +(uint64_t)(counter.QuadPart%frequency.QuadPart)*UINT64_C(1000000000)/(uint64_t)frequency.QuadPart;
}
#else
#include <time.h>
static uint64_t profile_now(void) {
 struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t)) __builtin_trap();
 return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
#endif
static uint64_t report_read_parse_ns, report_select_ns, report_total_ns, report_render_ns;
'''


def generated(path,profile=False,encode_clock=True):
    original=pyfunc._one_function
    def instrument(fn,sigs,strict,cname,*args,**kwargs):
        signature,body,ctx=original(fn,sigs,strict,cname,*args,**kwargs)
        if fn.name!='integer_row_report_stream':return signature,body,ctx
        anchor=signature+' {\n';private='price_'+cname
        if body.count(anchor)!=1:raise ValueError('report boundary changed')
        body=body.replace(anchor,signature.replace(cname+'(',private+'(',1)+' {\n',1)
        names=','.join(re.findall(r'([A-Za-z_]\w*)\s*(?:,|$)',signature.partition('(')[2].rsplit(')',1)[0]))
        kind=signature.partition(cname+'(')[0].strip().removeprefix('static ')
        body+=signature+' {uint64_t start=profile_now();'+kind+' result='+private+'('+names+');phases[0]+=profile_now()-start;return result;}\n'
        return signature,body,ctx
    info={'_want_units':True,'_checked_arrays':True}
    try:
        if profile:pyfunc._one_function=instrument
        code=pyc.to_c(_load_sources(path)[0],strict=True,info=info)
    finally:pyfunc._one_function=original
    code+=pyc._io_main_for(info) if info.get('io') else pyc._main_for(info)
    if not profile:return code
    def wrap(signature,names,index):
        nonlocal code
        target=signature.partition('(')[0].split()[-1];anchor=signature+' {'
        if code.count(anchor)!=1:raise ValueError('phase boundary changed: '+target)
        code=code.replace(anchor,signature+';'+signature.replace(target+'(','raw_'+target+'(',1)+' {',1)
        kind=signature.partition('(')[0].removeprefix('static ').rsplit(' ',1)[0]
        call='raw_'+target+'('+names+')'
        body=call+';' if kind=='void' else kind+' result='+call+';'
        code+=signature+' {uint64_t start=profile_now();'+body+'phases['+str(index)+']+=profile_now()-start;'+('' if kind=='void' else 'return result;')+'}\n'
    wrap('static ail_bytes ail_binaryfile_read(ail_barena *A, ail_binaryfile *F, int64_t size)','A,F,size',1)
    wrap('static ail_list ail_integer_decode(ail_bytes data, int64_t width, int64_t order)','data,width,order',2)
    if encode_clock:
        wrap('static ail_bytes ail_str_encode_utf8(ail_barena *A, ail_str s)','A,s',3)
    wrap('static void ail_stdout_write_bytes(ail_bytes data)','data',4)
    tail=r'''
#undef main
static void price_report(void) {
 fprintf(stderr,"ROWPRICE %llu %llu %llu %llu %llu\n",(unsigned long long)phases[0],(unsigned long long)phases[1],(unsigned long long)phases[2],(unsigned long long)phases[3],(unsigned long long)phases[4]);
}
int main(int argc,char **argv) {if(atexit(price_report))return 123;return price_main(argc,argv);}
'''
    return HEADER+'\nstatic uint64_t phases[5];\n#define main price_main\n'+code+tail


def pin(path):
    data = Path(path).read_bytes()
    return {'path': str(Path(path).resolve()), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def oracle(values, cols, repeat):
    output = io.BytesIO()
    for start in range(0, len(values), cols):
        total = 0
        for value in values[start:start + cols]:
            total += value
            if not -(1 << 63) <= total < (1 << 63):
                raise ValueError('prefix overflow')
        output.write(f'{total}\n'.encode('ascii'))
    return output.getvalue() * repeat

def qualify(binary, directory, label):
    lo, hi = -(1 << 63), (1 << 63) - 1
    cases = [
        ('empty', [], 3, 2, True),
        ('numeric', [1, -2, 3, 10, 20, -4], 3, 3, True),
        ('above_2p53', [(1 << 53) + 1, 2, -3, -(1 << 53) - 3], 2, 2, True),
        ('minmax', [lo, hi, hi, -hi], 2, 2, True),
        ('disparate16', [v for i in range(16) for v in (i * 137 - 999, i * i, 31 - i)], 3, 4, True),
        ('nonrepeat', [17, -9, 1003, -40, 91, 0, 11, -8], 2, 1, True),
        ('buffer_edge', [1] * 8193, 3, 1, True),
        ('negative_cols', [1], -1, 1, False),
        ('negative_repeat', [1], 1, -1, False),
        ('zero_cols', [1], 0, 1, False),
        ('zero_repeat', [1], 1, 0, False),
        ('partial_row', [1, 2, 3], 2, 1, False),
        ('prefix_overflow_cancel', [hi, 1, -1], 3, 1, False),
        ('prefix_underflow_cancel', [lo, -1, 1], 3, 1, False),
    ]
    results = []
    for name, values, cols, repeat, valid in cases:
        path = directory / (name + '.bin')
        path.write_bytes(b''.join(struct.pack('<q', v) for v in values))
        before = pin(path)
        p = subprocess.run([str(binary), str(path), str(cols), str(repeat)], capture_output=True, timeout=30)
        if p.returncode == 0 or label.endswith('_profile'):
            observed_phases(label, p.stderr)
        expected = oracle(values, cols, repeat) if valid else None
        passed = p.returncode == 0 and p.stdout == expected if valid else p.returncode != 0 and not p.stdout
        results.append({'case': name, 'passed': passed, 'returncode': p.returncode, 'input': before,
                        'input_unchanged': before == pin(path), 'stdout_bytes': len(p.stdout),
                        'stdout_sha256': hashlib.sha256(p.stdout).hexdigest(),
                        'expected_sha256': hashlib.sha256(expected).hexdigest() if valid else None})
    for name, data in [('partial_record', b'1234567'), ('missing_file', None)]:
        path = directory / (name + '.bin')
        if data is not None:
            path.write_bytes(data)
        p = subprocess.run([str(binary), str(path), '1', '1'], capture_output=True, timeout=30)
        results.append({'case': name, 'passed': p.returncode != 0 and not p.stdout, 'returncode': p.returncode})
    for args in [[], ['x', '1'], ['x', '1x', '1'], ['x', '18446744073709551616', '1']]:
        p = subprocess.run([str(binary), *args], capture_output=True, timeout=30)
        results.append({'case': 'invalid_argv', 'args': args, 'passed': p.returncode != 0 and not p.stdout, 'returncode': p.returncode})
    return results

REFERENCE_C = r'''#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdlib.h>
#include <errno.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
static int positive(const char *s, size_t *v) {
 if (*s < '0' || *s > '9') return 0;
 char *end; errno=0; uintmax_t n=strtoumax(s,&end,10);
 if(errno || *end || !n || n>SIZE_MAX) return 0;
 *v=(size_t)n; return 1;
}
int main(int argc,char **argv) {
 size_t cols,repeat;
 if(argc!=4 || !positive(argv[2],&cols) || !positive(argv[3],&repeat)) return 1;
 FILE *in=fopen(argv[1],"rb"); if(!in) return 1;
 unsigned char *report=NULL; size_t capacity=0,length=0,column=0; int64_t sum=0;
 unsigned char buf[65536]; size_t used;
 while((used=fread(buf,1,sizeof buf,in))) {
  if(used%8) goto fail;
  for(size_t i=0;i<used;i+=8) {
   uint64_t bits=0;
   for(unsigned j=0;j<8;++j) bits|=(uint64_t)buf[i+j]<<(8*j);
   int64_t value=bits<=INT64_MAX?(int64_t)bits:-1-(int64_t)(UINT64_MAX-bits);
   if(__builtin_add_overflow(sum,value,&sum)) goto fail;
   if(++column==cols) {
    char line[32]; int n=snprintf(line,sizeof line,"%" PRId64 "\n",sum);
    if(n<0 || (size_t)n>=sizeof line || length>SIZE_MAX-(size_t)n) goto fail;
    size_t need=length+(size_t)n;
    if(need>capacity) {
     size_t next=capacity && capacity<=SIZE_MAX/2?capacity*2:need;
     if(next<need) next=need;
     unsigned char *p=realloc(report,next); if(!p) goto fail;
     report=p; capacity=next;
    }
    for(int j=0;j<n;++j) report[length++]=(unsigned char)line[j];
    sum=0; column=0;
   }
  }
 }
 if(ferror(in) || column) goto fail;
 fclose(in);
#ifdef _WIN32
 if(_setmode(_fileno(stdout),_O_BINARY)==-1) {free(report);return 1;}
#endif
 for(size_t r=0;r<repeat;++r) if(length && fwrite(report,1,length,stdout)!=length) {free(report);return 1;}
 free(report); return fflush(stdout)?1:0;
fail:
 fclose(in); free(report); return 1;
}'''
REFERENCE_RUST = r'''use std::{env, fs, io::{self, Write}};
fn positive(s: &str) -> Result<usize, String> {
 if s.is_empty() || !s.bytes().all(|c| c.is_ascii_digit()) {return Err("invalid integer".into());}
 s.parse::<usize>().ok().filter(|&n| n>0).ok_or("invalid integer".into())
}
fn run() -> Result<(), Box<dyn std::error::Error>> {
 let args: Vec<String> = env::args().collect();
 if args.len()!=4 {return Err("usage: INPUT cols repeat".into());}
 let cols=positive(&args[2])?; let repeat=positive(&args[3])?;
 let input=fs::read(&args[1])?;
 if input.len()%8!=0 || (input.len()/8)%cols!=0 {return Err("partial row or record".into());}
 let mut report=Vec::new(); let mut column=0; let mut sum=0i64;
 for record in input.chunks_exact(8) {
  sum=sum.checked_add(i64::from_le_bytes(record.try_into()?)).ok_or("prefix overflow")?;
  column+=1;
  if column==cols {writeln!(&mut report,"{sum}")?; column=0; sum=0;}
 }
 let stdout=io::stdout(); let mut out=io::BufWriter::new(stdout.lock());
 for _ in 0..repeat {out.write_all(&report)?;}
 out.flush()?; Ok(())
}
fn main() {if let Err(e)=run() {eprintln!("{e}"); std::process::exit(1);}}'''

def c_profile():
    code=REFERENCE_C
    start='  for(size_t i=0;i<used;i+=8) {'
    end=' }\n if(ferror(in) || column) goto fail;'
    if code.count(start)!=1 or code.count(end)!=1:raise ValueError('C processing boundary changed')
    code=code.replace(start,'  uint64_t start=profile_now();\n'+start,1)
    code=code.replace(end,'  phases[0]+=profile_now()-start;\n'+end,1)
    header=HEADER+r'''
static uint64_t phases[3];
static size_t observe_read(void *p,size_t size,size_t count,FILE *f) {
 uint64_t start=profile_now();size_t n=fread(p,size,count,f);phases[1]+=profile_now()-start;return n;
}
static size_t observe_write(const void *p,size_t size,size_t count,FILE *f) {
 uint64_t start=profile_now();size_t n=fwrite(p,size,count,f);phases[2]+=profile_now()-start;return n;
}
#define fread observe_read
#define fwrite observe_write
#define main raw_main
'''
    tail=r'''
#undef main
#undef fread
#undef fwrite
static void show(void) {fprintf(stderr,"CPRICE %llu %llu %llu\n",(unsigned long long)phases[0],(unsigned long long)phases[1],(unsigned long long)phases[2]);}
int main(int argc,char **argv) {if(atexit(show))return 123;return raw_main(argc,argv);}
'''
    return header+code+tail


def observed_phases(label, stderr):
    if label == 'ail_profile':
        match = re.fullmatch(rb'ROWPRICE (\d+) (\d+) (\d+) (\d+) (\d+)\n', stderr)
        if not match:
            raise ValueError('AIL observer stderr differs')
        values = list(map(int, match.groups()))
        if values[3] != 0:
            raise ValueError('encode clock unexpectedly active')
        return [values[0] - values[1], values[1], values[4]]
    if label == 'c_profile':
        match = re.fullmatch(rb'CPRICE (\d+) (\d+) (\d+)\n', stderr)
        if not match:
            raise ValueError('C observer stderr differs')
        return list(map(int, match.groups()))
    if stderr:
        raise ValueError('unexpected successful-program stderr: ' + label)
    return None


def build(work, gcc, rustc, report):
    codes = {'ail': generated(HERE / 'row_reduce_stream_main.ail'),
             'ail_profile': generated(HERE / 'row_reduce_stream_main.ail', True, encode_clock=False),
             'c': REFERENCE_C, 'c_profile': c_profile(), 'rust': REFERENCE_RUST}
    binaries = {}
    for label, code in codes.items():
        source = work / (label + ('.rs' if label == 'rust' else '.c'))
        source.write_text(code, encoding='utf8')
        binary = work / label
        command = ([str(rustc), '-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'codegen-units=1',
                    '-C', 'lto=fat', '--edition=2021', str(source), '-o', str(binary)] if label == 'rust' else
                   [str(gcc), *FLAGS, str(source), '-lm', '-o', str(binary)])
        source_pin = pin(source)
        result = subprocess.run(command, capture_output=True, timeout=180)
        entry = dict(command=command, returncode=result.returncode, source_before=source_pin,
                     stderr=result.stderr.decode(errors='replace'))
        report['builds'][label] = entry
        if result.returncode:
            raise ValueError('build failed: ' + label)
        binaries[label] = binary
        entry['binary_before'] = pin(binary)
        controls = qualify(binary, work, label)
        report['qualification'][label] = controls
        if len(controls) != 20 or not all(row['passed'] and row.get('input_unchanged', True) for row in controls):
            raise ValueError('boundary controls failed: ' + label)
        print('built/qualified ' + label, file=sys.stderr, flush=True)
    return binaries


def measure(work, binaries, rows, cols, report):
    values = array.array('q', ((-1 if index % 2 else 1) * ((1 << 53) + 37 * index + 19)
                              for index in range(rows * cols)))
    path, expected_path = work / (str(cols) + '.bin'), work / (str(cols) + '.expected')
    path.write_bytes(values.tobytes())
    expected = oracle(values, cols, 1)
    expected_path.write_bytes(expected)
    del values
    result = dict(rows=rows, cols=cols, input_before=pin(path), expected_before=pin(expected_path), samples=[])
    report['workloads'].append(result)
    try:
        def sample(label, stage):
            row = dict(program=label, stage=stage, runs=[])
            result['samples'].append(row)
            start = time.perf_counter_ns()
            phase_runs = []
            try:
                for _ in range(BATCH_RUNS):
                    process = subprocess.run([str(binaries[label]), str(path), str(cols), '1'],
                                             capture_output=True, timeout=120)
                    run = dict(returncode=process.returncode, output_verified=process.stdout == expected,
                               stdout_sha256=hashlib.sha256(process.stdout).hexdigest(),
                               stderr=process.stderr.decode(errors='replace'))
                    row['runs'].append(run)
                    if process.returncode or not run['output_verified']:
                        raise ValueError('timed complete output mismatch: ' + label)
                    phases = observed_phases(label, process.stderr)
                    if phases is not None:
                        if any(value < 0 for value in phases):
                            raise ValueError('negative processing phase')
                        phase_runs.append(phases)
            finally:
                row['wall_ns'] = time.perf_counter_ns() - start
            if phase_runs:
                row['processing_read_write_ns'] = [sum(phases[index] for phases in phase_runs) for index in range(3)]
            return row
        for label in binaries:
            sample(label, 'warmup')
        controls = {}
        for stage in ('aa_before', 'observer', 'comparison', 'aa_after'):
            if stage == 'comparison':
                for cycle in range(9):
                    order = COMPARISON_ORDERS[cycle]
                    for label in order:
                        sample(label, stage)
            else:
                for label in (('ail', 'c') if stage == 'observer' else LABELS):
                    ratios = []
                    for cycle in range(9):
                        if stage == 'observer':
                            profile = label + '_profile'
                            order = (label, profile) if cycle % 2 == 0 else (profile, label)
                            pair = {name: sample(name, stage) for name in order}
                            ratios.append(pair[profile]['wall_ns'] / pair[label]['wall_ns'])
                        else:
                            first, second = sample(label, stage), sample(label, stage)
                            ratios.append(second['wall_ns'] / first['wall_ns'])
                    controls[stage + '_' + label] = ratios
            print('finished cols=' + str(cols) + ' ' + stage, file=sys.stderr, flush=True)
        intervals = {key: [sorted(ratios)[1], sorted(ratios)[7]] for key, ratios in controls.items()}
        minimum = min(row['wall_ns'] for row in result['samples'])
        result.update(controls=controls, control_intervals=intervals, minimum_sample_ns=minimum,
                      calibration_passed=minimum >= 50_000_000 and all(1 / 1.1 <= low <= high <= 1.1
                                                                       for low, high in intervals.values()))
    finally:
        result['input_after'], result['expected_after'] = pin(path), pin(expected_path)
        result['files_unchanged'] = (result['input_before'] == result['input_after']
                                     and result['expected_before'] == result['expected_after'])
    return result


def price(result):
    profiles = {label: [row for row in result['samples'] if row['stage'] == 'observer'
                        and row['program'] == label + '_profile'] for label in ('ail', 'c')}
    phase_ns = {label: [statistics.median(row['processing_read_write_ns'][index] for row in samples)
                       for index in range(3)] for label, samples in profiles.items()}
    shares = {name: statistics.median(row['processing_read_write_ns'][index] / row['wall_ns']
                                    for row in profiles['ail'])
              for index, name in enumerate(('processing', 'read', 'write'))}
    if not all(0 <= share < 1 for share in shares.values()) or phase_ns['ail'][0] <= 0:
        raise ValueError('phase share bounds invalid')
    medians = {label: statistics.median(row['wall_ns'] for row in result['samples']
                                       if row['stage'] == 'comparison' and row['program'] == label) for label in LABELS}
    return dict(processing_read_write_median_ns=phase_ns, diagnostic_wall_shares=shares,
                qualified_amdahl_bounds={name: 1 / (1 - share) for name, share in shares.items()},
                median_batch_ns=medians, ail_over_c=medians['ail'] / medians['c'],
                ail_over_rust=medians['ail'] / medians['rust'],
                achieved_empirical_c_processing_fraction=phase_ns['c'][0] / phase_ns['ail'][0],
                assumed_empirical_reference_fraction=1,
                reference_scope='measured C processing cost; an empirical comparator, not a physical roof')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('ail-performance-baseline.json'))
    parser.add_argument('--qualify-only', action='store_true')
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('fresh JSON output path required')
    report = dict(status='unqualified', quality_passed=False, measurement='not_performed',
                  mode='qualify_only' if args.qualify_only else 'fixed_measurement', batch_runs=BATCH_RUNS,
                  scope='16 sequential whole CLI jobs per sample; warm LE i64 regular file; exact full stdout; includes startup, transport, checks and cleanup',
                  processing_scope='AIL report minus reads; C decode/sum/render/growth block; C initial setup and final fclose excluded',
                  protocol='nine AA pairs before/after for AIL/C/Rust; nine alternating observer pairs for AIL/C; nine fixed comparison cycles covering all six permutations and three rotations; rank2..8 ratios in1/1.1..1.1; >=50ms; no adaptive retries',
                  encode_measured=False, physical_roof_measured=False, assumed_physical_roof_fraction=None,
                  achieved_physical_roof_fraction=None, optimization_adopted=False, all_purpose_fastest_claim=False,
                  builds={}, qualification={}, controls_passed=False, workloads=[], pins_before={})
    watched = [Path(__file__), ROOT / 'ail_chatgpt.py', ROOT / 'ail_syntax.py', ROOT / 'MANIFEST.json',
               HERE / 'row_reduce_stream_main.ail', HERE / 'integer_row_stream.ail',
               *sorted((ROOT / 'python/pkg-v12').glob('*.py'))]
    try:
        if sys.platform != 'linux' or sys.byteorder != 'little' or array.array('q').itemsize != 8:
            raise ValueError('Linux little-endian 8-byte array q required')
        compiler_paths = {name: shutil.which(name) for name in ('gcc', 'rustc')}
        if not all(compiler_paths.values()):
            raise ValueError('gcc and rustc required')
        gcc, rustc = (Path(compiler_paths[name]).absolute() for name in ('gcc', 'rustc'))
        watched += [gcc, rustc]
        report['pins_before'] = {str(path): pin(path) for path in watched}
        report['compiler_versions'] = {}
        for label, compiler in (('gcc', gcc), ('rustc', rustc)):
            version = subprocess.run([str(compiler), '--version'], capture_output=True, timeout=30, check=True)
            report['compiler_versions'][label] = version.stdout.decode(errors='replace')
        sysroot = subprocess.run([str(rustc), '--print', 'sysroot'], capture_output=True, timeout=30, check=True)
        rust_backend = Path(sysroot.stdout.decode().strip()) / 'bin/rustc'
        if not rust_backend.is_file():
            raise ValueError('actual Rust compiler unavailable for pinning')
        watched.append(rust_backend)
        report['pins_before'][str(rust_backend)] = pin(rust_backend)
        report['cpu'] = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {report['cpu']})
        report['affinity'] = sorted(os.sched_getaffinity(0))
        with tempfile.TemporaryDirectory(prefix='ail-current-rows-') as directory:
            work = Path(directory)
            snapshots = {}
            _load_sources(HERE / 'row_reduce_stream_main.ail', source_bytes=snapshots)
            report['loaded_sources_before'] = {str(path): pin(path) for path in snapshots}
            try:
                binaries = build(work, gcc, rustc, report)
                report['controls_passed'] = True
                if not args.qualify_only:
                    report['measurement'] = 'started'
                    for rows, cols in ((65537, 17), (17, 65537)):
                        measure(work, binaries, rows, cols, report)
                    report['measurement'] = 'completed'
            finally:
                report['loaded_sources_after'] = {str(path): pin(path) for path in snapshots}
                for label, entry in report['builds'].items():
                    source = work / (label + ('.rs' if label == 'rust' else '.c'))
                    if source.is_file():
                        entry['source_after'] = pin(source)
                    binary = work / label
                    if binary.is_file():
                        entry['binary_after'] = pin(binary)
            unchanged = (report['loaded_sources_before'] == report['loaded_sources_after']
                         and all(path.read_bytes() == data for path, data in snapshots.items())
                         and all(entry['source_before'] == entry['source_after']
                                 and entry.get('binary_before') == entry.get('binary_after')
                                 for entry in report['builds'].values()))
            report['artifacts_unchanged'] = unchanged
            if not unchanged:
                raise ValueError('loaded source/generated source/binary changed')
        report['pins_after'] = {str(path): pin(path) for path in watched}
        if report['pins_before'] != report['pins_after']:
            raise ValueError('source/compiler changed')
        if args.qualify_only:
            report.update(status='controls_passed', quality_passed=False)
        elif all(result['calibration_passed'] and result['files_unchanged'] for result in report['workloads']):
            pricing = [price(result) for result in report['workloads']]
            for result, details in zip(report['workloads'], pricing):
                result['qualified_pricing'] = details
            report.update(status='priced', quality_passed=True)
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
        report.update(status='unqualified', quality_passed=False, failure=str(error))
    finally:
        try:
            report['pins_after'] = {str(path): pin(path) for path in watched}
        except OSError as error:
            report.update(status='unqualified', quality_passed=False, pin_failure=str(error))
        if report.get('pins_after') != report['pins_before']:
            report.update(status='unqualified', quality_passed=False, pin_failure='source/compiler changed or unavailable')
        if not report['quality_passed']:
            for result in report['workloads']:
                result.pop('qualified_pricing', None)
        with args.output.open('x', encoding='utf8') as output:
            json.dump(report, output, indent=2)
            output.write('\n')
    print(json.dumps({key: report[key] for key in ('status', 'quality_passed', 'measurement')}))
    return 0 if (args.qualify_only and report['status'] == 'controls_passed') or report['quality_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
