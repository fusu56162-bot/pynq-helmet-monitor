"""Link ONE new bridge against the existing INT8-enabled static library."""
import ctypes as ct
import json
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
from common import HERE, BASE, INFO, sha, check_package


def main():
    check_package()
    if sys.platform != 'linux' or platform.machine() not in ('armv7l', 'armv8l') or struct.calcsize('P') != 4:
        raise RuntimeError('Actual ARMv7 Linux board required')
    if 'neon' not in Path('/proc/cpuinfo').read_text().lower():
        raise RuntimeError('NEON missing')
    old = BASE / 'build/librider_ncnn.so'
    int8 = BASE / 'int8_v1/build/librider_ncnn_int8.so'
    if sha(old) != '24f823324d12d117e6822b6ae47e20751e4c2c45df6ee78d72acde1b9c1a5f85':
        raise RuntimeError('Original runtime hash changed')
    if sha(int8) != '8352754002a11bd17ef6d17ec09cb7c1f8e1e6956338f7d95853ed5846464d7e':
        raise RuntimeError('Expected the already-built INT8 library from the uploaded result')
    static = BASE / 'int8_v1/build/ncnn/src/libncnn.a'
    include = BASE / 'int8_v1/build/source/ncnn-20260526/src'
    generated = BASE / 'int8_v1/build/ncnn/src'
    compiler = shutil.which('g++')
    if not compiler or not static.is_file():
        raise RuntimeError('Missing g++ or existing INT8 static library; do not rebuild everything')
    build = HERE / 'build'
    build.mkdir(exist_ok=True)
    output = build / 'libsmall.so'
    report = build / 'BUILD.json'
    if output.exists() and report.exists():
        previous = json.loads(report.read_text())
        if sha(output) == previous['library_sha256'] and sha(HERE / 'small_bridge.cpp') == previous['bridge_sha256']:
            print('Reuse matching small bridge', flush=True)
            return
        raise RuntimeError('Existing bridge differs; preserve it')
    cmd = [compiler, '-std=c++11', '-O3', '-DNDEBUG', '-fPIC', '-shared',
           '-mcpu=cortex-a9', '-mfpu=neon', '-mfloat-abi=hard', '-fopenmp', '-pthread',
           '-I'+str(include), '-I'+str(generated), str(HERE / 'small_bridge.cpp'),
           str(static), '-Wl,--no-undefined', '-lm', '-ldl', '-o', str(output)]
    print('Compile ONE dynamic-size bridge; reusing the existing ncnn library', flush=True)
    with (build / 'build.log').open('w', encoding='utf-8') as log:
        log.write(repr(cmd) + '\n')
        log.flush()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        try:
            for line in p.stdout:
                print(line, end='', flush=True)
                log.write(line)
            if p.wait():
                raise RuntimeError('Bridge build failed; send small_v1/build/build.log')
        except BaseException:
            if p.poll() is None:
                p.terminate()
            p.wait()
            raise
    lib = ct.CDLL(str(output))
    lib.small_build_info.restype = ct.c_char_p
    if lib.small_build_info().decode() != INFO:
        raise RuntimeError('Bridge ABI mismatch')
    data = {'compiled': True, 'native_forward_verified': False, 'deployment_changed': False,
            'library_sha256': sha(output), 'bridge_sha256': sha(HERE / 'small_bridge.cpp'),
            'static_sha256': sha(static), 'command': cmd, 'original_library_sha256': sha(old),
            'existing_int8_library_sha256': sha(int8)}
    report.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print('SMALL BRIDGE BUILD PASS. Native inference has not yet been verified.', flush=True)


if __name__ == '__main__':
    main()
