"""Independent native INT8 build. Never overwrite the original build or model."""
import ctypes as ct
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SOURCE_SHA = '5aedf25e22d4a9ab7785d33774affee96b55b546e85318cc351a48a365d15ced'
BRIDGE_SHA = '078ea0e728afcc0a376c8d42d44f9b07f5e1f0f484f369c05c15b326e890c7f5'
BUILD_INFO = 'ncnn=1.0.20260526;armv7-neon;int8-candidate;vulkan=off;abi=1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_manifest():
    m = json.loads((HERE / 'addon_manifest.json').read_text(encoding='utf-8'))
    for name, digest in m['sha256'].items():
        p = (HERE / name).resolve()
        p.relative_to(HERE)
        if sha(p) != digest:
            raise ValueError('INT8 package hash mismatch: ' + name)
    return m


def run(command, log):
    print('RUN:', ' '.join(command), flush=True)
    log.write('\n' + repr(command) + '\n')
    log.flush()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, errors='replace')
    try:
        for line in process.stdout:
            print(line, end='', flush=True)
            log.write(line)
            log.flush()
        if process.wait():
            raise RuntimeError('Build failed; send int8_v1/build/build.log')
    except BaseException:
        if process.poll() is None:
            process.terminate()
        process.wait()
        raise


def main():
    check_manifest()
    if sys.platform != 'linux' or platform.machine() not in ('armv7l', 'armv8l') or struct.calcsize('P') != 4:
        raise RuntimeError('Run on the actual 32-bit ARMv7 board')
    if 'neon' not in Path('/proc/cpuinfo').read_text().lower():
        raise RuntimeError('NEON unavailable')
    for tool in ('cmake', 'g++', 'make'):
        if not shutil.which(tool):
            raise RuntimeError('Missing ' + tool)
    if shutil.disk_usage(HERE).free < 1024**3:
        raise RuntimeError('Need >=1 GiB free disk; no automatic deletion')
    mem = {k: int(v.split()[0]) for k, v in
           (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())}
    if mem.get('MemAvailable', 0) < 150*1024 or mem.get('SwapTotal', 0) < 256*1024:
        raise RuntimeError('Need >=150 MiB available RAM and existing >=256 MiB swap')
    original = BASE / 'build/librider_ncnn.so'
    if not original.is_file():
        raise RuntimeError('Missing existing FP32 build; run inside original candidate folder')
    original_sha = sha(original)
    bridge = BASE / 'native/bridge.cpp'
    if sha(bridge) != BRIDGE_SHA:
        raise RuntimeError('Original bridge changed; review first')
    archive = BASE / 'vendor/ncnn-20260526-source.zip'
    if sha(archive) != SOURCE_SHA:
        raise RuntimeError('Pinned source archive mismatch')
    build = HERE / 'build'
    build.mkdir(exist_ok=True)
    output = build / 'librider_ncnn_int8.so'
    if output.exists() and (build / 'BUILD.json').exists():
        info = json.loads((build / 'BUILD.json').read_text())
        if sha(output) == info['int8_library_sha256'] and info['original_library_sha256'] == original_sha:
            print('Existing verified build reused; next run run_compare.py', flush=True)
            return
        raise RuntimeError('Existing build differs; preserve it and report')
    source_root = build / 'source'
    source_root.mkdir(exist_ok=True)
    source = source_root / 'ncnn-20260526'
    # A separate extraction avoids touching or trusting modified old build sources.
    if not (source / '.int8_archive_verified').exists():
        if source.exists():
            raise RuntimeError('Partial source directory exists; preserve it and report')
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                (source_root / info.filename).resolve().relative_to(source_root.resolve())
                if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise RuntimeError('Unexpected source symlink')
            z.extractall(source_root)
        (source / '.int8_archive_verified').write_text(SOURCE_SHA)
    code = bridge.read_text()
    replacements = [('h->net.opt.use_int8_inference = false;', 'h->net.opt.use_int8_inference = true;'),
                    (';armv7-neon;fp32;vulkan=off;abi=1', ';armv7-neon;int8-candidate;vulkan=off;abi=1')]
    for before, after in replacements:
        if code.count(before) != 1:
            raise RuntimeError('Unexpected bridge template')
        code = code.replace(before, after)
    generated = build / 'bridge_int8.cpp'
    generated.write_text(code)
    flags = '-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard'
    command = ['cmake', '-S', str(HERE), '-B', str(build), '-G', 'Unix Makefiles',
               '-DCMAKE_BUILD_TYPE=Release', '-DNCNN_SOURCE_DIR=' + str(source),
               '-DBRIDGE_SOURCE=' + str(generated), '-DCMAKE_C_FLAGS=' + flags,
               '-DCMAKE_CXX_FLAGS=' + flags]
    # Exclude unused model families to reduce board compilation time. Keep
    # ncnn's implicit packing, casting, padding and quantization helper layers.
    used = {line.split()[0].lower() for line in (HERE / 'model/best.ncnn.param').read_text().splitlines()[2:]}
    used.update('bias scale padding crop interp packing flatten cast quantize dequantize requantize relu prelu clip sigmoid hardswish hardsigmoid'.split())
    all_layers = re.findall(r'ncnn_add_layer\((\w+)', (source / 'src/CMakeLists.txt').read_text())
    for layer in all_layers:
        command.append('-DWITH_LAYER_' + layer.lower() + '=' + ('ON' if layer.lower() in used else 'OFF'))
    with (build / 'build.log').open('w', encoding='utf-8') as log:
        run(command, log)
        run(['cmake', '--build', str(build), '--target', 'rider_ncnn_int8', '--', '-j1'], log)
    library = ct.CDLL(str(output))
    library.rider_build_info.restype = ct.c_char_p
    if library.rider_build_info().decode() != BUILD_INFO:
        raise RuntimeError('Unexpected candidate ABI')
    if sha(original) != original_sha:
        raise RuntimeError('Original runtime unexpectedly changed')
    report = {'compiled': True, 'native_inference_verified': False, 'deployment_changed': False,
              'original_library_sha256': original_sha, 'int8_library_sha256': sha(output),
              'bridge_sha256': sha(generated), 'archive_sha256': SOURCE_SHA,
              'configuration': command, 'compile_parallelism': 1, 'precision': 'INT8 convolution / FP32 other operators'}
    (build / 'BUILD.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('INT8 BUILD PASS; original runtime unchanged. Next: real-board comparison.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('BUILD FAIL:', exc, file=sys.stderr)
        sys.exit(1)
