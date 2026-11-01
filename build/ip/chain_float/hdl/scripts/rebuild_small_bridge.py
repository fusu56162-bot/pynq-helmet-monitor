"""Rebuild the ARM bridge in a new directory; never update pinned identities."""
from pathlib import Path
import argparse,platform,struct,subprocess
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--traffic-project',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if platform.system()!='Linux' or platform.machine() not in ('armv7l','armv8l') or struct.calcsize('P')!=4:
        raise RuntimeError('Native 32-bit ARMv7 NEON environment required')
    b=Path(a.traffic_project).resolve()/'ncnn_candidate_20261019';o=Path(a.output).resolve()
    if o.exists():raise RuntimeError('Use a new output directory')
    o.mkdir(parents=True)
    cmd=['g++','-std=c++11','-O3','-DNDEBUG','-fPIC','-shared','-mcpu=cortex-a9','-mfpu=neon','-mfloat-abi=hard','-fopenmp','-pthread',
         '-I'+str(b/'int8_v1/build/source/ncnn-20260526/src'),'-I'+str(b/'int8_v1/build/ncnn/src'),str(b/'small_v1/small_bridge.cpp'),
         str(b/'int8_v1/build/ncnn/src/libncnn.a'),'-Wl,--no-undefined','-lm','-ldl','-o',str(o/'libsmall.so')]
    subprocess.run(cmd,check=True)
    print('BUILD_COMPLETE_NOT_BOARD_PARITY_TESTED; pinned runtime unchanged')
