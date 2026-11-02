"""Experimental FPGA prefix + unchanged ncnn suffix, versus original CPU library.

No camera, no deployment, no model replacement. Per-frame boundary packing,
cache maintenance, DMA and suffix execution are INSIDE candidate forward time.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import struct
import subprocess
import sys
import time
import traceback
import uuid
import zipfile
import numpy as np
from native_whole import Native, validate_input
from parity_support import Runtime, parity, sha, stats
from polling_dma import PollingDMA, invalid_size_guard

ROOT=Path(__file__).resolve().parent
BASE=Path('/home/xilinx/jupyter_notebooks/traffic_project/ncnn_candidate_20261019')
EXPECTED_ROOT=BASE.parent/'chain_whole_v1'
BACKUP=Path('/home/xilinx/jupyter_notebooks/traffic_backups/before_conv_v1_20250504_054120_757f3bcb')
POISON=0x5A5A5A5A
VALUES=32*56*56


def verify_package():
    manifest=json.loads((ROOT/'FILES_SHA256.json').read_text(encoding='utf-8'))
    for relative,expected in manifest.items():
        path=(ROOT/relative).resolve();path.relative_to(ROOT.resolve())
        if sha(path)!=expected: raise RuntimeError('Package hash mismatch: '+relative)
    return len(manifest)


def originals_check(originals):
    result={}
    for name,expected in originals.items():
        try: result[name]=sha(BASE/name)==expected
        except OSError: result[name]=False
    return result


def preflight(spec):
    if spec['cases']!=['case_%02d'%i for i in range(1,13)] or spec['rounds']!=3 or spec['threads']!=2:
        raise RuntimeError('Unexpected fixed comparison protocol')
    receipt=json.loads((ROOT/'BACKUP_RECEIPT.json').read_text(encoding='utf-8'))
    b=receipt['backup']
    if (receipt['status']!='BACKUP_VERIFIED_METADATA_PASS_NO_FPGA_CHANGE' or
            Path(b['archive'])!=BACKUP/'traffic_project.tar.gz' or Path(b['manifest'])!=BACKUP/'MANIFEST.json' or
            not (BACKUP/'traffic_project.tar.gz').is_file() or
            (BACKUP/'traffic_project.tar.gz').stat().st_size!=b['archive_bytes'] or
            sha(BACKUP/'MANIFEST.json')!=b['manifest_sha256']):
        raise RuntimeError('Verified rollback backup is missing or changed; no FPGA load')
    if not all(originals_check(spec['originals_sha256']).values()):
        raise RuntimeError('Original model/library identity changed; no FPGA load')
    for name,expected in spec['model_sha256'].items():
        if sha(ROOT/'model'/name)!=expected: raise RuntimeError('Packaged model identity changed')
    source=BASE/'int8_v1/build/source/ncnn-20260526/src'
    for name,expected in spec['upstream_sources_sha256'].items():
        if sha(source/name)!=expected: raise RuntimeError('Original ncnn source differs: '+name)


def build(directory,spec):
    source=BASE/'int8_v1/build/source/ncnn-20260526/src'
    headers=BASE/'int8_v1/build/ncnn/src'
    static=headers/'libncnn.a'
    if sha(static)!=spec['originals_sha256']['int8_v1/build/ncnn/src/libncnn.a']:
        raise RuntimeError('Pinned ARM static archive changed')
    compiler=shutil.which('g++')
    if not compiler: raise RuntimeError('g++ is missing')
    library=directory/'libwhole_chain.so'
    command=[compiler,'-std=c++11','-O3','-DNDEBUG','-fPIC','-shared','-fno-fast-math','-ffp-contract=off',
             '-mcpu=cortex-a9','-mfpu=neon','-mfloat-abi=hard','-fopenmp','-pthread',
             '-I'+str(source),'-I'+str(source/'layer'),'-I'+str(headers),'-I'+str(ROOT)]
    command += [str(ROOT/name) for name in ('whole_bridge.cpp','boundary_bridge.cpp')]
    command += [str(static),'-Wl,-Bsymbolic','-Wl,--no-undefined','-lm','-ldl','-o',str(library)]
    print('BUILD: small boundary/resume bridge only; original operators and libraries unchanged',flush=True)
    with (directory/'build.log').open('w',encoding='utf-8') as log:
        log.write(repr(command)+'\n');log.flush()
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    return library,dict(command=command,library_sha256=sha(library),static_sha256=sha(static))


def exact(a,b):
    return a.shape==b.shape and a.dtype==b.dtype and np.array_equal(a.view(np.uint32),b.view(np.uint32))


def require_exact(actual,expected,label,directory):
    if not exact(actual,expected):
        np.save(directory/(label+'_actual.npy'),actual,allow_pickle=False)
        np.save(directory/(label+'_expected.npy'),expected,allow_pickle=False)
        raise RuntimeError('BIT_EXACT_CHECK_FAILED: '+label+'; outputs saved; tolerances were NOT relaxed')


class Candidate:
    def __init__(self,native,dma,ip,tx,rx):
        self.native,self.dma,self.ip,self.tx,self.rx=native,dma,ip,tx,rx
        self.safe_to_release=True
        self.last={}

    def forward(self,x):
        # Caller starts the whole-forward timer BEFORE entering this method.
        started=time.perf_counter()
        self.native.pack_input(x,self.tx)  # strict exact-value validation; no rounding fallback
        packed=time.perf_counter()
        self.rx.fill(POISON)
        self.tx.flush();self.rx.flush()
        self.safe_to_release=False
        dma_ms=self.dma.run(self.ip,112,112,int(self.tx.device_address),self.tx.nbytes,
                            int(self.rx.device_address),VALUES*4)
        self.safe_to_release=True
        self.rx.invalidate()
        received=np.asarray(self.rx)
        if not np.all(received[VALUES:]==POISON): raise RuntimeError('RX guard overwritten')
        ready=time.perf_counter()
        out=self.native.resume(received[:VALUES])  # owned packed4 copy + remaining ORIGINAL network
        if not np.isfinite(out).all(): raise RuntimeError('Nonfinite FPGA-plus-suffix output')
        finished=time.perf_counter()
        self.last=dict(input_pack_ms=(packed-started)*1000,dma_window_ms=dma_ms,
                       cache_dma_readback_guard_ms=(ready-packed)*1000,
                       owned_pack_and_suffix_ms=(finished-ready)*1000)
        return out


def retain_until_reset():
    def ignore(signum,frame):
        print('DMA buffers retained. Do not kill this process; reset the board SRST once.',flush=True)
    signal.signal(signal.SIGINT,ignore);signal.signal(signal.SIGTERM,ignore)
    print('RESET_REQUIRED: DMA not quiescent. Keep this terminal/process alive, then press SRST once.',flush=True)
    while True: time.sleep(1)


def experiment(directory,report,spec,checkpoint):
    native=baseline=dma=candidate=None
    buffers=[];safe=True
    try:
        checkpoint('CHECK_BACKUP_AND_ORIGINAL_IDENTITIES')
        preflight(spec)
        checkpoint('BUILD_CUTPOINT_ADAPTER_ONLY_NO_FPGA_YET')
        library,report['build']=build(directory,spec)
        native=Native(library,ROOT/'model')
        baseline=Runtime(BASE/'small_v1/build/libsmall.so',ROOT/'model')
        inputs={}; cpu={}; boundaries={}; input_bytes={}
        checkpoint('CPU_PREFLIGHT_12_CASES_NO_FPGA_YET')
        for key in spec['cases']:
            path=ROOT/'inputs'/(key+'_input.npy')
            if sha(path)!=sha(BASE/'small_v1/fixtures_224'/path.name):
                raise RuntimeError('Board original input differs: '+key)
            x=np.load(path,allow_pickle=False);validate_input(x)
            input_bytes[key]=x.tobytes();x.setflags(write=False);inputs[key]=x
            native.pack_input(x,np.empty(x.size//4,np.uint32))
            original=baseline.forward(x)
            previous=np.load(ROOT/'previous_arm'/(key+'.npy'),allow_pickle=False)
            historical=parity(original,previous)
            if not historical['passed']: raise RuntimeError('Original CPU output differs from historical ARM reference: '+key)
            require_exact(native.full(x),original,key+'_new_bridge_full_vs_original',directory)
            boundary=native.boundary(x)
            require_exact(native.resume(boundary),original,key+'_cpu_cutpoint_resume',directory)
            if key in ('case_01','case_02'):
                known=np.fromfile(ROOT/'known_boundary'/(key+'.u32'),'<u4')
                require_exact(boundary,known,key+'_previous_arm_boundary',directory)
            if x.tobytes()!=input_bytes[key]: raise RuntimeError('Input changed in CPU preflight: '+key)
            cpu[key]=original;boundaries[key]=boundary
            np.save(directory/(key+'_cpu_full.npy'),original,allow_pickle=False)
            np.save(directory/(key+'_cpu_boundary_hwc.npy'),boundary,allow_pickle=False)
            report['cpu_preflight'].append(dict(id=key,new_bridge_full_bit_exact=True,cpu_resume_bit_exact=True,
                                                previous_arm_comparison=historical))
            checkpoint('CPU_PREFLIGHT_PASS_'+key)
        from pynq import Overlay, MMIO, allocate
        from pynq.ps import Clocks
        checkpoint('LOAD_BOARD_VERIFIED_CHAIN_OVERLAY')
        report['new_overlay_load_attempted']=True
        overlay=Overlay(str(ROOT/'overlay/rider_monitor_chain_float.bit'))
        report['new_overlay_loaded']=True
        for name,address in [('conv_accel_0',0x40010000),('axi_dma_conv',0x41E10000)]:
            if int(overlay.ip_dict[name]['phys_addr'])!=address: raise RuntimeError('Overlay address mismatch: '+name)
        report['fclk0_mhz']=float(Clocks.fclk0_mhz)
        if not 99.5<=report['fclk0_mhz']<=100.5: raise RuntimeError('Unexpected PL clock')
        ip=MMIO(0x40010000,0x10000);dma=PollingDMA(MMIO(0x41E10000,0x10000))
        dma.reset();ip.write(0x04,0);ip.write(0x08,0)
        invalid_size_guard(ip,0,1);invalid_size_guard(ip,113,1);dma.start()
        tx=allocate(shape=(3*224*224//4,),dtype=np.uint32);buffers.append(tx)
        rx=allocate(shape=(VALUES+16,),dtype=np.uint32);buffers.append(rx)
        candidate=Candidate(native,dma,ip,tx,rx)
        checkpoint('FPGA_FULL_NETWORK_FUNCTIONAL_12_CASES')
        for key in spec['cases']:
            out=candidate.forward(inputs[key])
            hwc=np.array(np.asarray(rx)[:VALUES],dtype=np.uint32,copy=True)
            np.save(directory/(key+'_fpga_boundary_hwc.npy'),hwc,allow_pickle=False)
            np.save(directory/(key+'_fpga_full.npy'),out,allow_pickle=False)
            require_exact(hwc,boundaries[key],key+'_fpga_boundary',directory)
            require_exact(out,cpu[key],key+'_fpga_full',directory)
            quality=parity(out,cpu[key])
            if not quality['passed']: raise RuntimeError('Full raw/detection parity failed: '+key)
            if inputs[key].tobytes()!=input_bytes[key]: raise RuntimeError('Input changed: '+key)
            report['functional_cases'].append(dict(id=key,boundary_bit_exact=True,full_output_bit_exact=True,
                                                    input_unchanged=True,raw_and_detection_comparison=quality))
            checkpoint('FPGA_FULL_NETWORK_EXACT_PASS_'+key)
        report['whole_model_integrated']=True
        checkpoint('WARMUP_BOTH_PATHS_NOT_MEASURED')
        for key in spec['cases']:
            require_exact(baseline.forward(inputs[key]),cpu[key],key+'_warm_cpu',directory)
            require_exact(candidate.forward(inputs[key]),cpu[key],key+'_warm_fpga',directory)
            if inputs[key].tobytes()!=input_bytes[key]: raise RuntimeError('Input changed in warmup: '+key)
        checkpoint('PAIRED_WHOLE_FORWARD_TIMING_3_ROUNDS')
        recorded=[]
        for round_index in range(spec['rounds']):
            for i,key in enumerate(spec['cases']):
                order=['baseline','candidate'] if (round_index+i)%2==0 else ['candidate','baseline']
                current={}
                for kind in order:
                    started=time.perf_counter()
                    out=(baseline.forward if kind=='baseline' else candidate.forward)(inputs[key])
                    elapsed=(time.perf_counter()-started)*1000
                    row=dict(round=round_index+1,id=key,kind=kind,whole_forward_ms=elapsed,
                             pair_order=order,measured=True,warmup=False)
                    if kind=='candidate': row['components_ms']=dict(candidate.last)
                    report['timings'].append(row);recorded.append((row,out));current[kind]=out
                for kind,out in current.items(): require_exact(out,cpu[key],'%s_r%d_%s'%(key,round_index+1,kind),directory)
                if inputs[key].tobytes()!=input_bytes[key]: raise RuntimeError('Input changed during timing: '+key)
                print('ROUND=%d %s EXACT_PASS CPU=%.3f ms FPGA+CPU=%.3f ms'%
                      (round_index+1,key,*[next(r['whole_forward_ms'] for r in reversed(report['timings'])
                                               if r['round']==round_index+1 and r['id']==key and r['kind']==k)
                                         for k in ('baseline','candidate')]),flush=True)
            checkpoint('ROUND_%d_COMPLETE'%(round_index+1))
        # Disk I/O, output comparisons and NMS are outside BOTH forward timers.
        for row,out in recorded:
            filename='r%d_%s_%s.npy'%(row['round'],row['kind'],row['id'])
            np.save(directory/filename,out,allow_pickle=False);row['output_file']=filename;row['output_sha256']=sha(directory/filename)
        for kind in ('baseline','candidate'):
            report[kind+'_whole_forward']=stats([r['whole_forward_ms'] for r in report['timings'] if r['kind']==kind])
        a,b=report['baseline_whole_forward']['mean_ms'],report['candidate_whole_forward']['mean_ms']
        report['observed_mean_speedup']=a/b
        report['whole_model_speedup_observed']=b<a
        report['candidate_mean_at_or_below_150_ms']=b<=150
        report['candidate_p95_at_or_below_150_ms']=report['candidate_whole_forward']['p95_ms']<=150
        report['comparison_passed']=True
        report['status']='WHOLE_FORWARD_BIT_EXACT_COMPARISON_PASS_NOT_DEPLOYED'
    except BaseException as error:
        report['status']='WHOLE_FORWARD_EXPERIMENT_FAILED'
        report['error']=traceback.format_exc()
        print('STOPPED:',repr(error),flush=True)
        if dma is not None:
            try: report['dma_at_failure']=dma.snapshot()
            except BaseException as e: report['dma_snapshot_error']=repr(e)
    finally:
        if candidate is not None: safe=candidate.safe_to_release
        if dma is not None:
            try: dma.reset();safe=True;report['dma_quiesced']=True
            except BaseException:
                safe=False;report['dma_quiesced']=False;report['dma_reset_error']=traceback.format_exc()
        if safe:
            for buffer in buffers:
                try: buffer.freebuffer()
                except BaseException:
                    report['status']='BUFFER_RELEASE_FAILED_AFTER_DMA_HALTED'
                    report.setdefault('buffer_release_errors',[]).append(traceback.format_exc())
            buffers.clear()
            if report['new_overlay_load_attempted']:
                try:
                    checkpoint('RESTORE_OLD_PREPROCESS_HARDWARE')
                    from pynq import Overlay
                    old=Overlay(str(ROOT/'rollback/rider_monitor_preprocess.bit'))
                    if 'conv_accel_0' in old.ip_dict or 'vision_preprocess_0' not in old.ip_dict:
                        raise RuntimeError('Old hardware identity mismatch')
                    report['old_hardware_restored']=bool(old.is_loaded())
                    if not report['old_hardware_restored']: raise RuntimeError('Old hardware not reported loaded')
                except BaseException:
                    report['status']='RESTORE_FAILED_RESET_AND_RECOVERY_REQUIRED'
                    report['restore_error']=traceback.format_exc()
        else: report['status']='DMA_NOT_QUIESCED_KEEP_BUFFERS_RESET_REQUIRED'
        for runtime in (baseline,native):
            if runtime is not None:
                try:
                    if runtime is baseline: runtime.__exit__(None,None,None)
                    else: runtime.close()
                except BaseException: report.setdefault('close_errors',[]).append(traceback.format_exc())
        report['originals_unchanged']=originals_check(spec['originals_sha256'])
        if not all(report['originals_unchanged'].values()): report['status']='ORIGINAL_IDENTITY_CHANGED_STOP'
        report['stage']='FINISHED' if safe else 'WAITING_FOR_BOARD_RESET'
        checkpoint(report['stage'])
        report['array_files_sha256']={p.name:sha(p) for p in sorted(directory.glob('*.npy'))}
        checkpoint(report['stage'])
        archive_path=ROOT/('双层硬件接入整网_对照结果_'+directory.name+'.zip')
        with zipfile.ZipFile(archive_path,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for path in sorted(directory.iterdir()):
                if path.is_file() and path.suffix!='.so': z.write(path,path.name)
        print('STATUS:',report['status'],flush=True)
        if 'candidate_whole_forward' in report:
            print('CPU_WHOLE_MEAN_MS:',report['baseline_whole_forward']['mean_ms'],flush=True)
            print('FPGA_PLUS_CPU_WHOLE_MEAN_MS:',report['candidate_whole_forward']['mean_ms'],flush=True)
            print('FPGA_PLUS_CPU_WHOLE_P95_MS:',report['candidate_whole_forward']['p95_ms'],flush=True)
        print('OLD_HARDWARE_RESTORED:',report['old_hardware_restored'],flush=True)
        print('DOWNLOAD_RESULT:',archive_path,flush=True)
        if not safe: retain_until_reset()  # references to DMA buffers stay alive in this stack frame
    return 0 if (report['comparison_passed'] and report['old_hardware_restored'] and
                 report['status']=='WHOLE_FORWARD_BIT_EXACT_COMPARISON_PASS_NOT_DEPLOYED') else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only',action='store_true')
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--backup-on-pc-confirmed',action='store_true')
    parser.add_argument('--programs-stopped',action='store_true')
    args=parser.parse_args();count=verify_package()
    if args.verify_only and not args.run:
        print('WHOLE_PACKAGE_HASH_PASS:',count,'files; no compilation or hardware access');return 0
    if not (args.run and args.backup_on_pc_confirmed and args.programs_stopped):
        parser.error('--run --backup-on-pc-confirmed --programs-stopped required')
    if ROOT!=EXPECTED_ROOT or platform.system()!='Linux' or platform.machine()!='armv7l' or struct.calcsize('P')!=4:
        raise RuntimeError('Expected independent chain_whole_v1 directory on ARMv7 Linux')
    import fcntl
    lock=(ROOT.parent/'.conv_board_exclusive.lock').open('a')
    fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    spec=json.loads((ROOT/'SPEC.json').read_text(encoding='utf-8'))
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    directory=ROOT/'results'/stamp;directory.mkdir(parents=True,exist_ok=False)
    os.chdir(directory)
    report=dict(status='STARTED_NOT_PASS',stage='PREFLIGHT',package_verified_files=count,
                cpu_preflight=[],functional_cases=[],timings=[],new_overlay_load_attempted=False,
                new_overlay_loaded=False,old_hardware_restored=False,comparison_passed=False,
                whole_model_integrated=False,accuracy_accepted=False,deployment_changed=False,
                model='recover5',input_side=224,threads=2,rounds=3,
                timing_scope='Original float32 CHW input -> full decoded raw out0. Candidate INCLUDES per-frame exact float-to-byte packing, RX poisoning, cache maintenance, DMA, guard, owned HWC-to-packed4 copy, all unchanged suffix ncnn operators, output allocation/copy/finite checks. Excludes preprocessing, parity/NMS, camera/UI and one-time model/library/buffer setup. Balanced paired 3x12, both warmed, no outlier removal.',
                precision_contract='Current CPU vs FPGA full outputs must be uint32 bit-exact; historical ARM reference uses original published parity tolerances, also reports exactness. No model/threshold/operator changes.',
                partial_report=str(directory/'RESULT.json'))
    def checkpoint(stage):
        report['stage']=stage
        (directory/'RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('STAGE:',stage,flush=True)
    return experiment(directory,report,spec,checkpoint)


if __name__=='__main__': sys.exit(main())
