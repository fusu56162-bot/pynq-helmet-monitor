"""Matched old/new two-layer FPGA + original ARM suffix comparison.

Import/--verify-only never opens devices. Both models use exactly the same
bridge, transfer protocol, 100 MHz clock, two threads and timing boundaries.
"""
import argparse,datetime,json,os,platform,shutil,struct,sys,time,traceback,uuid,zipfile
from pathlib import Path
import numpy as np
import run_whole as core
import fpga_camera as backend
import mjpg_camera as camera
import pipeline as support

ROOT=Path(__file__).resolve().parent
EXPECTED_ROOT=Path('/home/xilinx/jupyter_notebooks/traffic_project/final224_speed_v1')
ORDER=('old','new','new','old')
ACTIVE=None

def verify():
    for name in ('run_whole','native_whole','parity_support','board_model_runtime','polling_dma','fpga_camera','camera_io','pipeline','mjpg_camera'):
        if Path(sys.modules[name].__file__).resolve().parent!=ROOT:
            raise RuntimeError('Old module still loaded: '+name+'; restart this Notebook kernel before using the new package')
    manifest=json.loads((ROOT/'FILES_SHA256.json').read_text(encoding='utf-8'))
    if not manifest or any(p.endswith('.ipynb') for p in manifest):
        raise RuntimeError('Invalid protected-file manifest')
    for name,digest in manifest.items():
        p=(ROOT/name).resolve();p.relative_to(ROOT)
        if core.sha(p)!=digest: raise RuntimeError('Package file changed: '+name)
    print('MATCHED_OLD_NEW_PACKAGE_HASH_PASS',len(manifest),'files; devices untouched',flush=True)
    return len(manifest)

def preflight(spec):
    # The complete rollback archive was already SHA-verified on the PC. It is
    # deliberately NOT required to occupy another 1.49 GiB on the SD card.
    if spec['threads']!=2 or spec['input_side']!=224 or spec['rounds']!=3:
        raise RuntimeError('Fixed comparison protocol changed')
    if not all(core.originals_check(spec['originals_sha256']).values()):
        raise RuntimeError('Original library/model identity changed')
    for name,digest in spec['model_sha256'].items():
        if core.sha(core.ROOT/'model'/name)!=digest: raise RuntimeError('Selected model changed')
    source=core.BASE/'int8_v1/build/source/ncnn-20260526/src'
    for name,digest in spec['upstream_sources_sha256'].items():
        if core.sha(source/name)!=digest: raise RuntimeError('Pinned ncnn source changed: '+name)

def configure(name):
    global ACTIVE
    if name not in ('old','new'): raise ValueError('Select old or new')
    if backend.RETAINED_SESSIONS or support.RETAINED_WORKERS or support.RETAINED_FAILURE_EVIDENCE:
        raise RuntimeError('Previous device/worker session retained; do not start another run')
    p=ROOT/'profiles'/name
    core.ROOT=backend.ROOT=camera.ROOT=support.ROOT=p
    backend.EXPECTED_ROOT=camera.EXPECTED_ROOT=support.EXPECTED_ROOT=EXPECTED_ROOT/'profiles'/name
    core.preflight=preflight
    core.verify_package=verify
    camera.verify=verify
    ACTIVE=name
    return json.loads((p/'SPEC.json').read_text(encoding='utf-8'))

def validate(programs_stopped,backup_on_pc_confirmed):
    if programs_stopped is not True or backup_on_pc_confirmed is not True:
        raise ValueError('Stop other camera/FPGA kernels and confirm the existing PC backup')
    if ROOT!=EXPECTED_ROOT or platform.system()!='Linux' or platform.machine()!='armv7l' or struct.calcsize('P')!=4:
        raise RuntimeError('Use independent traffic_project/final224_speed_v1 on ARMv7 Linux')
    if shutil.disk_usage(ROOT).free<512*1024*1024:
        raise RuntimeError('Need at least 512 MiB free; no FPGA load attempted')

def telemetry(): return camera.telemetry()

def write_json(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def stats(rows):
    result={}
    for kind in ('cpu','fpga_arm'):
        subset=[r for r in rows if r['kind']==kind]
        if subset: result[kind]=core.stats([r['whole_forward_ms'] for r in subset])
    parts=('input_pack_ms','dma_window_ms','cache_dma_readback_guard_ms','owned_pack_and_suffix_ms')
    result['fpga_components']={k:core.stats([r['components_ms'][k] for r in rows if r['kind']=='fpga_arm']) for k in parts} if rows else {}
    return result

def one_block(name,index,directory,common):
    spec=configure(name)
    directory.mkdir(parents=True,exist_ok=False)
    r=dict(model=name,block=index,status='STARTED_NOT_PASS',cpu_reference_cases=[],fpga_reference_cases=[],
           fpga_reference_forward_count=0,live_fpga_forward_count=0,new_overlay_load_attempted=False,
           new_overlay_loaded=False,old_hardware_restored=False,timings=[],model_identity=spec['model_sha256'],
           overlay_sha256=core.sha(core.ROOT/'overlay/rider_monitor_chain_float.bit'),telemetry_start=telemetry())
    def checkpoint(stage):
        r['stage']=stage;write_json(directory/'RESULT.json',r)
        print('BLOCK',index,name,stage,flush=True)
    session=backend.HardwareSession(spec,directory,r,checkpoint)
    clean=False
    try:
        session.prepare()  # Actual 12 CPU + 12 FPGA comparisons BEFORE timing.
        goldens={}
        for key,x in common.items():
            goldens[key]=session.cpu.forward(x)
            core.require_exact(session.native.full(x),goldens[key],key+'_common_full',directory)
            boundary=session.native.boundary(x)
            core.require_exact(session.native.resume(boundary),goldens[key],key+'_common_cpu_resume',directory)
            session.safe=False;out=session.candidate.forward(x);session.safe=True
            core.require_exact(out,goldens[key],key+'_common_fpga_warm',directory)
            core.require_exact(np.asarray(session.buffers[1])[:core.VALUES],boundary,key+'_common_boundary_warm',directory)
        checkpoint('WARMUP_EXACT_PASS')
        for round_index in range(2):
            for i,(key,x) in enumerate(common.items()):
                order=('cpu','fpga_arm') if (round_index+i+index)%2==0 else ('fpga_arm','cpu')
                for kind in order:
                    t=time.perf_counter()
                    if kind=='fpga_arm':
                        session.safe=False;out=session.candidate.forward(x);session.safe=True
                    else: out=session.cpu.forward(x)
                    elapsed=(time.perf_counter()-t)*1000
                    row=dict(id=key,block=index,model=name,round=round_index+1,kind=kind,
                             pair_order=order,whole_forward_ms=elapsed)
                    if kind=='fpga_arm': row['components_ms']=dict(session.candidate.last)
                    # Array checks, output saving and JSON writes outside timer.
                    core.require_exact(out,goldens[key],key+'_timed_'+kind,directory)
                    if x.tobytes()!=common_bytes[key]: raise RuntimeError('Input memory modified')
                    r['timings'].append(row)
            checkpoint('MEASURED_ROUND_'+str(round_index+1))
        for key in common:
            if core.sha(ROOT/'common_inputs'/(key+'_input.npy'))!=spec['common_inputs_sha256'][key]:
                raise RuntimeError('Pinned input file changed')
        r['statistics']=stats(r['timings']);r['status']='BLOCK_BIT_EXACT_PASS'
    except BaseException:
        r['status']='BLOCK_FAILED';r['error']=traceback.format_exc()
    finally:
        clean=session.close()
        r['cleanup_passed']=clean;r['telemetry_end']=telemetry()
        write_json(directory/'RESULT.json',r)
    if not clean or r['status']!='BLOCK_BIT_EXACT_PASS':
        raise RuntimeError('Stopped at '+str(directory/'RESULT.json')+'\n'+r.get('error',r['status']))
    return r

common_bytes={}

def benchmark(programs_stopped=False,backup_on_pc_confirmed=False):
    global common_bytes
    validate(programs_stopped,backup_on_pc_confirmed);count=verify()
    import fcntl
    with (ROOT.parent/'.conv_board_exclusive.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
        directory=ROOT/'results'/('AB_'+stamp);directory.mkdir(parents=True,exist_ok=False)
        r=dict(status='STARTED_NOT_PASS',package_files=count,order=ORDER,blocks=[],
               timing_scope='normalized float32 CHW input -> full raw out0; packing/cache/DMA/ARM suffix included; model load/CPU audits/camera/NMS/UI/storage excluded',
               threads=2,input_side=224,clock_mhz=100,precision='55 INT8 + 5 FP32 convolutions',
               board_tested=False,accuracy_accepted=False,optimization_prototype_enabled=False)
        try:
            common={}
            for i in range(1,13):
                key='case_%02d'%i;x=np.load(ROOT/'common_inputs'/(key+'_input.npy'),allow_pickle=False)
                core.validate_input(x);x.setflags(write=False);common[key]=x
            common_bytes={k:v.tobytes() for k,v in common.items()}
            for index,name in enumerate(ORDER,1):
                r['blocks'].append(one_block(name,index,directory/('%02d_%s'%(index,name)),common))
                write_json(directory/'RESULT.json',r)
            rows=[row for block in r['blocks'] for row in block['timings']]
            r['statistics']={name:stats([row for row in rows if row['model']==name]) for name in ('old','new')}
            old=r['statistics']['old']['fpga_arm']['mean_ms'];new=r['statistics']['new']['fpga_arm']['mean_ms']
            r['old_over_new_forward_ratio']=old/new
            r['new_minus_old_forward_ms']=new-old
            a=r['blocks'][0]['statistics']['fpga_arm']['mean_ms'];b=r['blocks'][3]['statistics']['fpga_arm']['mean_ms']
            r['old_start_end_drift_percent']=100*(b-a)/a
            r['drift_over_5_percent']=abs(r['old_start_end_drift_percent'])>5
            r['board_tested']=True;r['status']='MATCHED_OLD_NEW_BIT_EXACT_SPEED_COMPARISON_PASS'
            print(json.dumps(r['statistics'],ensure_ascii=False,indent=2),flush=True)
            print('OLD/NEW FORWARD RATIO',r['old_over_new_forward_ratio'],'OLD DRIFT %',r['old_start_end_drift_percent'],flush=True)
            print('These are forward timings; 1000/ms is NOT live camera FPS.',flush=True)
        except BaseException:
            r['status']='AB_STOPPED_PARTIAL_RESULT';r['error']=traceback.format_exc();print(r['error'],flush=True)
        finally:
            write_json(directory/'RESULT.json',r)
            output=export_paths([directory],'新旧模型同通路测速结果')
            print('STATUS',r['status'],'DOWNLOAD_RESULT',output,flush=True)
        if r['status']!='MATCHED_OLD_NEW_BIT_EXACT_SPEED_COMPARISON_PASS': raise RuntimeError('Preserve partial result '+str(output))
        return directory

def run_camera(name='new',seconds=30,scene='bare_head_static',notes='',camera_index=0,
               programs_stopped=False,backup_on_pc_confirmed=False):
    validate(programs_stopped,backup_on_pc_confirmed);verify();configure(name)
    # Reuses the measured single-view MJPG path. No raw preview thread, no PNG.
    return camera.run_fpga(save_mode='raw_sampled',format_name='MJPG',seconds=seconds,scene=scene,notes=notes,
        camera_index=camera_index,fps=15,programs_stopped=programs_stopped,backup_on_pc_confirmed=backup_on_pc_confirmed)

def export_paths(paths,label='新模型单画面摄像头结果'):
    files=[]
    for directory in paths:
        directory=Path(directory).resolve();directory.relative_to(ROOT)
        report=json.loads((directory/'RESULT.json').read_text(encoding='utf-8'))
        if report.get('kind')=='fpga_probe' and not (report.get('capture_worker_stopped') and report.get('writer_worker_stopped') and report.get('dma_quiesced')):
            raise RuntimeError('Workers/DMA not safely stopped; preserve original result directory')
        files += [p for p in directory.rglob('*') if p.is_file() and p.suffix in ('.npy','.json','.log','.jpg','.yuyv')]
    total=sum(p.stat().st_size for p in files)
    if total>384*1024*1024 or shutil.disk_usage(ROOT).free<total+64*1024*1024:
        raise RuntimeError('Insufficient free space for result ZIP; original files preserved')
    output=ROOT/(label+'_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.zip')
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_STORED) as z:
        manifest={p.relative_to(ROOT).as_posix():core.sha(p) for p in files}
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
        z.writestr('RESULT_FILES_SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(output) as z:
        if z.testzip():raise RuntimeError('Result ZIP CRC failed')
    print('DOWNLOAD_RESULT:',output,flush=True)
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verify-only',action='store_true');p.add_argument('--run',action='store_true')
    p.add_argument('--programs-stopped',action='store_true');p.add_argument('--backup-on-pc-confirmed',action='store_true')
    a=p.parse_args()
    if a.verify_only and not a.run:verify();return
    if not a.run:p.error('Use --verify-only or --run --programs-stopped --backup-on-pc-confirmed')
    benchmark(a.programs_stopped,a.backup_on_pc_confirmed)

if __name__=='__main__':main()
