"""Rebuild ncnn from corresponding source in a NEW ARM workspace."""
from pathlib import Path
import argparse,platform,struct,subprocess
from materialize import restore
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();o=Path(a.output).resolve()
    if platform.system()!='Linux' or platform.machine() not in ('armv7l','armv8l') or struct.calcsize('P')!=4:
        raise RuntimeError('Native 32-bit ARMv7 Linux required')
    if o.exists():raise RuntimeError('Use a new output directory')
    restore('ncnn',o/'source')
    flags='-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard'
    subprocess.run(['cmake','-S',str(o/'source'),'-B',str(o/'build'),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
        '-DNCNN_VULKAN=OFF','-DNCNN_BUILD_TOOLS=OFF','-DNCNN_BUILD_EXAMPLES=OFF','-DNCNN_BUILD_BENCHMARK=OFF','-DNCNN_BUILD_TESTS=OFF',
        '-DNCNN_INT8=ON','-DNCNN_OPENMP=ON','-DCMAKE_C_FLAGS='+flags,'-DCMAKE_CXX_FLAGS='+flags],check=True)
    subprocess.run(['cmake','--build',str(o/'build'),'--','-j1'],check=True)
    print('REBUILD_COMPLETE_NOT_BIT_IDENTICAL_ACCEPTED; preserve pinned archive and rerun numerical validation before replacing it')
