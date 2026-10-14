"""Export a qualified CRC implementation as a reusable standard C interop object."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'python/pkg-v12')]
from language_examples.c_headers_workflow.table_crc import HEADER, transform
import c_object


def _incremental_header(source, convert):
    if source != convert(HEADER):
        raise ValueError('expected exact transformed CRC header')
    signature = 'static uint32_t example_crc32(const unsigned char *data, size_t size) {'
    seed = '    uint32_t crc = UINT32_MAX;'
    ending = '#endif\n'
    if any(source.count(marker) != 1 for marker in (signature, seed, ending)):
        raise ValueError('CRC header shape changed')
    return source.replace(signature,
        'static uint32_t example_crc32_update(uint32_t previous, const unsigned char *data, size_t size) {').replace(
        seed, '    uint32_t crc = previous ^ UINT32_MAX;').replace(ending,
        'static uint32_t example_crc32(const unsigned char *data, size_t size) {\n'
        '    return example_crc32_update(0, data, size);\n}\n#endif\n')


def _pins(implementation='table'):
    examples = ROOT/'language_examples/c_headers'
    files = [HERE/'build_crc_library.py', HERE/'table_crc.py', ROOT/'ail_syntax.py',
             *(ROOT/'python/pkg-v12').glob('*.py'),
             *(examples/name for name in ('checksum.c','checksum.json','crc32.h','detail/crc_constants.h'))]
    if implementation == 'slicing': files.append(HERE/'slicing_crc.py')
    return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def build(output, implementation='table', *, c_api_namespace=None):
    if type(implementation) is not str or implementation not in ('table','slicing'):
        raise ValueError('implementation must be table or slicing')
    convert=transform
    if implementation == 'slicing':
        from language_examples.c_headers_workflow.slicing_crc import transform as convert
    # Check the requested path before resolve(), which follows a dangling symlink.
    output = Path(output).absolute()
    metadata = Path(str(output)+'.json')
    if any(path.exists() or path.is_symlink() for path in (output,metadata)):
        raise ValueError('object output or its metadata already exists')
    before = _pins(implementation)
    examples = ROOT/'language_examples/c_headers'
    interface = json.loads((examples/'checksum.json').read_text(encoding='utf8'))
    if interface['functions']['native_crc32']['params'] != [['data','bytes']]:
        raise ValueError('CRC byte interface changed')
    interface['functions']['native_crc32']['params'][0][1] = 'borrowed_bytes'
    interface['functions']['native_crc32_update'] = dict(symbol='native_crc32_update',
        params=[['previous','uint32'],['data','borrowed_bytes']],result='uint32')
    with tempfile.TemporaryDirectory(prefix='ail-crc-library-') as directory:
        temporary = Path(directory)
        for name in ('checksum.c','crc32.h','detail/crc_constants.h'):
            target = temporary/name; target.parent.mkdir(parents=True,exist_ok=True)
            original = (examples/name).read_bytes()
            if name=='crc32.h':
                original = _incremental_header(convert(original.decode('utf8')),convert).encode('utf8')
            elif name=='checksum.c':
                original += (b'\nuint32_t native_crc32_update(uint32_t previous, const unsigned char *data, size_t size) {\n'
                             b'    return example_crc32_update(previous, data, size);\n}\n')
            target.write_bytes(original)
        descriptor = temporary/'checksum.json'
        descriptor.write_text(json.dumps(interface),encoding='utf8')
        c_object.compile_c(temporary/'checksum.c',descriptor,output,c_api_namespace=c_api_namespace)
    if _pins(implementation) != before:
        raise ValueError('original, helper or toolchain source changed during export')
    return dict(object=str(output.resolve()),metadata=str(metadata.resolve()),
        object_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        metadata_sha256=hashlib.sha256(metadata.read_bytes()).hexdigest(),
        source_sha256=before,sources_unchanged=True,implementation=implementation,
        scope='reusable '+implementation+' CRC C object; standard borrowed bytes ABI and metadata; no application build or speed claim')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--implementation',choices=('table','slicing'),default='table')
    parser.add_argument('--c-api-name',help='build a dependency dedicated to this C library name')
    args=parser.parse_args()
    print(json.dumps(build(args.out,implementation=args.implementation,c_api_namespace=args.c_api_name),indent=2))
