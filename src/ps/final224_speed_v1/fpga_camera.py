"""Real-camera FPGA prefix + ARM suffix, paired with same-frame CPU reference.

No hardware access on import. No CPU fallback. DMA must halt before buffers
are freed and the verified rollback overlay is restored.
"""
import datetime
import io
import json
import math
from pathlib import Path
import platform
import shutil
import struct
import time
import traceback
import uuid
import zipfile
import numpy as np
import camera_io
import run_whole as core
from parity_support import preprocess224, decode224, sha

ROOT = Path(__file__).resolve().parent
EXPECTED_ROOT = Path('/home/xilinx/jupyter_notebooks/traffic_project/fpga_camera_v1')
NAMES = ['ebike', 'rider', 'helmet_head', 'bare_head']
COLORS = [(255,180,0), (255,180,255), (0,200,0), (0,0,255)]
RETAINED_SESSIONS = []  # Never release in-flight DMA buffers on a reporting error.


def verify():
    count = core.verify_package()
    print('FPGA_CAMERA_PACKAGE_HASH_PASS:', count, 'files; no hardware/camera opened')
    return count


def validate(scene, notes, seconds, camera_index, backup_on_pc_confirmed, programs_stopped):
    if RETAINED_SESSIONS:
        raise RuntimeError('An unsafe DMA session is retained: board reset/recovery required')
    if backup_on_pc_confirmed is not True or programs_stopped is not True:
        raise ValueError('Confirm PC backup and all old camera/FPGA programs stopped before running')
    if (ROOT != EXPECTED_ROOT or platform.system()!='Linux' or
            platform.machine()!='armv7l' or struct.calcsize('P')!=4):
        raise RuntimeError('Run only in independent traffic_project/fpga_camera_v1 on ARMv7 Linux')
    if scene not in camera_io.SCENES or not isinstance(notes,str) or len(notes)>2000:
        raise ValueError('Choose a listed actual scene and notes <=2000 characters')
    if (isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or
            not math.isfinite(seconds) or not 0<seconds<=60):
        raise ValueError('seconds must be >0 and <=60')
    if type(camera_index)!=int or not 0<=camera_index<=15:
        raise ValueError('camera_index must be 0..15')


class HardwareSession:
    """One explicit lifetime; caller must call close even if prepare fails."""
    def __init__(self, spec, directory, report, checkpoint):
        self.spec, self.directory, self.report, self.checkpoint = spec,directory,report,checkpoint
        self.native = self.cpu = self.dma = self.candidate = None
        self.buffers = []
        self.attempted = False
        self.safe = True

    def prepare(self):
        r = self.report
        self.checkpoint('CHECK_BACKUP_MODELS_LIBRARY_AND_SOURCES')
        core.preflight(self.spec)
        self.checkpoint('BUILD_SMALL_PINNED_ARM_ADAPTER_ONLY')
        library,r['build'] = core.build(self.directory,self.spec)
        self.native = core.Native(library,ROOT/'model')
        self.cpu = core.Runtime(core.BASE/'small_v1/build/libsmall.so',ROOT/'model')
        inputs, outputs, boundaries = {},{},{}
        self.checkpoint('CPU_REFERENCE_12_CASES_NO_FPGA_LOAD_YET')
        for key in self.spec['cases']:
            x = np.load(ROOT/'inputs'/(key+'_input.npy'),allow_pickle=False)
            x.setflags(write=False)
            expected = np.load(ROOT/'previous_arm'/(key+'.npy'),allow_pickle=False)
            actual = self.cpu.forward(x)
            core.require_exact(actual,expected,key+'_cpu_historical',self.directory)
            core.require_exact(self.native.full(x),actual,key+'_new_bridge_full',self.directory)
            boundary = self.native.boundary(x)
            core.require_exact(self.native.resume(boundary),actual,key+'_cpu_cutpoint',self.directory)
            self.native.pack_input(x,np.empty(x.size//4,np.uint32))
            if key in ('case_01','case_02'):
                golden = np.fromfile(ROOT/'known_boundary'/(key+'.u32'),'<u4')
                core.require_exact(boundary,golden,key+'_known_boundary',self.directory)
            inputs[key],outputs[key],boundaries[key] = x,actual,boundary
            r['cpu_reference_cases'].append(dict(id=key,bit_exact=True))
            self.checkpoint('CPU_EXACT_PASS_'+key)
        from pynq import Overlay, MMIO, allocate
        from pynq.ps import Clocks
        self.attempted = r['new_overlay_load_attempted'] = True
        self.checkpoint('LOAD_VERIFIED_FPGA_CHAIN')
        overlay = Overlay(str(ROOT/'overlay/rider_monitor_chain_float.bit'))
        r['new_overlay_loaded'] = bool(overlay.is_loaded())
        if not r['new_overlay_loaded']:
            raise RuntimeError('New chain overlay not reported loaded')
        for name,address in [('conv_accel_0',0x40010000),('axi_dma_conv',0x41E10000)]:
            if int(overlay.ip_dict[name]['phys_addr'])!=address:
                raise RuntimeError('Overlay IP address mismatch: '+name)
        r['fclk0_mhz'] = float(Clocks.fclk0_mhz)
        if not 99.5<=r['fclk0_mhz']<=100.5:
            raise RuntimeError('Expected 100MHz PL clock')
        ip = MMIO(0x40010000,0x10000)
        self.dma = core.PollingDMA(MMIO(0x41E10000,0x10000))
        self.safe = False
        self.dma.reset()
        self.safe = True
        ip.write(0x04,0);ip.write(0x08,0)
        core.invalid_size_guard(ip,0,1)
        core.invalid_size_guard(ip,113,1)
        self.dma.start()
        tx = allocate(shape=(3*224*224//4,),dtype=np.uint32)
        self.buffers.append(tx)
        rx = allocate(shape=(core.VALUES+16,),dtype=np.uint32)
        self.buffers.append(rx)
        self.candidate = core.Candidate(self.native,self.dma,ip,tx,rx)
        self.checkpoint('FPGA_12_REFERENCE_CASES_BEFORE_CAMERA')
        for key in self.spec['cases']:
            self.safe = False
            out = self.candidate.forward(inputs[key])
            self.safe = True
            hwc = np.array(np.asarray(rx)[:core.VALUES],dtype=np.uint32,copy=True)
            np.save(self.directory/(key+'_fpga_boundary.npy'),hwc,allow_pickle=False)
            np.save(self.directory/(key+'_fpga_raw.npy'),out,allow_pickle=False)
            core.require_exact(hwc,boundaries[key],key+'_fpga_boundary',self.directory)
            core.require_exact(out,outputs[key],key+'_fpga_full',self.directory)
            r['fpga_reference_cases'].append(dict(id=key,boundary_bit_exact=True,full_bit_exact=True))
            r['fpga_reference_forward_count'] += 1
            self.checkpoint('FPGA_EXACT_PASS_'+key)
        r['camera_allowed_after_12_fpga_cases'] = True
        self.checkpoint('FPGA_READY_FOR_REAL_CAMERA')

    def infer(self, frame):
        started = time.perf_counter()
        x = preprocess224(frame)
        ready = time.perf_counter()
        self.safe = False
        raw = self.candidate.forward(x)
        self.safe = True
        completed = time.perf_counter()
        self.report['live_fpga_forward_count'] += 1
        # CPU cross-check is OUTSIDE the FPGA+CPU forward timer, never fallback.
        cpu = self.cpu.forward(x)
        checked = time.perf_counter()
        exact = core.exact(raw,cpu)
        boxes = decode224(raw)
        decoded = time.perf_counter()
        timing = dict(preprocess_ms=(ready-started)*1000,
            fpga_plus_cpu_forward_ms=(completed-ready)*1000,
            cpu_reference_forward_ms=(checked-completed)*1000,
            decode_ms=(decoded-checked)*1000,
            preprocess_forward_reference_decode_ms=(decoded-started)*1000,
            components_ms=dict(self.candidate.last))
        proof = dict(fpga_forward_completed=True,same_frame_cpu_bit_exact=exact,
            dma_registers_after_completed_forward=self.dma.snapshot())
        return raw,cpu,boxes,timing,proof

    def close(self):
        r = self.report
        # Pin the owner BEFORE any cleanup work. An unexpected interrupt/logging
        # exception must not garbage-collect CMA while DMA may still be active.
        if self not in RETAINED_SESSIONS:
            RETAINED_SESSIONS.append(self)
        safe = self.safe
        if self.candidate is not None:
            safe = safe and self.candidate.safe_to_release
        if self.dma is not None:
            try:
                self.dma.reset()
                safe = True
                r['dma_quiesced'] = True
            except BaseException:
                safe = False
                r['dma_quiesced'] = False
                r['dma_reset_error'] = traceback.format_exc()
        if safe:
            for buffer in self.buffers:
                try:
                    buffer.freebuffer()
                except BaseException:
                    r.setdefault('buffer_release_errors',[]).append(traceback.format_exc())
            self.buffers.clear()
            if self.attempted:
                try:
                    self.checkpoint('RESTORE_ORIGINAL_PREPROCESS_OVERLAY')
                except BaseException:
                    r['cleanup_report_write_error'] = traceback.format_exc()
                try:
                    from pynq import Overlay
                    old = Overlay(str(ROOT/'rollback/rider_monitor_preprocess.bit'))
                    if 'conv_accel_0' in old.ip_dict or 'vision_preprocess_0' not in old.ip_dict or not old.is_loaded():
                        raise RuntimeError('Rollback overlay identity/load mismatch')
                    r['old_hardware_restored'] = True
                except BaseException:
                    r['status'] = 'RESTORE_FAILED_RESET_AND_RECOVERY_REQUIRED'
                    r['restore_error'] = traceback.format_exc()
        else:
            r['status'] = 'DMA_NOT_QUIESCED_KEEP_PROCESS_ALIVE_RESET_REQUIRED'
        for runtime in (self.cpu,self.native):
            if runtime is not None:
                try:
                    if runtime is self.cpu:
                        runtime.__exit__(None,None,None)
                    else:
                        runtime.close()
                except BaseException:
                    r.setdefault('runtime_close_errors',[]).append(traceback.format_exc())
        r['originals_unchanged'] = core.originals_check(self.spec['originals_sha256'])
        if not all(r['originals_unchanged'].values()):
            r['status'] = 'ORIGINAL_IDENTITY_CHANGED_STOP'
        elif r.get('buffer_release_errors') or r.get('runtime_close_errors'):
            r['status'] = 'CLEANUP_ERROR_STOP'
        try:
            self.checkpoint('FINISHED' if safe else 'WAITING_FOR_BOARD_RESET')
        except BaseException:
            r['cleanup_report_write_error'] = traceback.format_exc()
        if not safe:
            # Keep self.buffers and the caller's exclusive lock alive until SRST.
            core.retain_until_reset()
        if self in RETAINED_SESSIONS:
            RETAINED_SESSIONS.remove(self)
        return (safe and (not self.attempted or r['old_hardware_restored']) and
                not r.get('buffer_release_errors') and not r.get('runtime_close_errors') and
                all(r['originals_unchanged'].values()))


def draw(frame, boxes, timing, exact):
    import cv2
    image = frame.copy()
    for x1,y1,x2,y2,score,cls in boxes:
        cls = int(cls)
        a = (int(round(float(x1))),int(round(float(y1))))
        b = (min(639,int(round(float(x2)))),min(479,int(round(float(y2)))))
        cv2.rectangle(image,a,b,COLORS[cls],2)
        cv2.putText(image,'%s %.2f'%(NAMES[cls],score),(a[0],max(15,a[1]-5)),
                    cv2.FONT_HERSHEY_SIMPLEX,.48,COLORS[cls],1,cv2.LINE_AA)
    text = 'FPGA+ARM %.1f ms | CPU-check %s'%(timing['fpga_plus_cpu_forward_ms'],'EXACT' if exact else 'FAILED')
    cv2.putText(image,text,(6,465),cv2.FONT_HERSHEY_SIMPLEX,.48,(0,255,255),1,cv2.LINE_AA)
    return image


def npy_bytes(array):
    stream = io.BytesIO()
    np.save(stream,array,allow_pickle=False)
    return stream.getvalue()


def save_frame(directory, frame, raw, cpu, boxes, timing, proof, captured, report):
    import cv2
    stem = 'frame_%06d'%(len(report['frames'])+1)
    ok,png = cv2.imencode('.png',frame,[int(cv2.IMWRITE_PNG_COMPRESSION),3])
    painted = draw(frame,boxes,timing,proof['same_frame_cpu_bit_exact'])
    ok_jpg,jpg = cv2.imencode('.jpg',painted,[int(cv2.IMWRITE_JPEG_QUALITY),85])
    if not ok or not ok_jpg:
        raise RuntimeError('Camera PNG/JPG encoding failed')
    payloads = {stem+'.png':png.tobytes(),stem+'_fpga_raw.npy':npy_bytes(raw),
        stem+'_cpu_raw.npy':npy_bytes(cpu),stem+'_boxes.npy':npy_bytes(boxes),stem+'_view.jpg':jpg.tobytes()}
    size = sum(map(len,payloads.values()))
    if report['saved_bytes']+size>128*1024*1024:
        raise RuntimeError('128MiB clip limit; previous frames preserved')
    row = dict(id=stem,capture_monotonic_ms=captured,source='live',
        detections_xyxy_score_class=boxes.tolist(),timing=timing,proof=proof,files={})
    for name,payload in payloads.items():
        with (directory/name).open('xb') as stream:
            stream.write(payload)
        row['files'][name] = sha(directory/name)
    report['frames'].append(row)
    report['saved_bytes'] += size
    return painted


def run(scene='empty_scene', camera_index=0, seconds=15, notes='',
        backup_on_pc_confirmed=False, programs_stopped=False):
    validate(scene,notes,seconds,camera_index,backup_on_pc_confirmed,programs_stopped)
    count = verify()
    if shutil.disk_usage(ROOT).free<384*1024*1024:
        raise RuntimeError('Less than 384MiB free; no hardware/camera opened')
    import fcntl
    with (ROOT.parent/'.conv_board_exclusive.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        spec = json.loads((ROOT/'SPEC.json').read_text(encoding='utf-8'))
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
        directory = ROOT/'results'/(scene+'_'+stamp)
        directory.mkdir(parents=True,exist_ok=False)
        report = dict(schema_version=1,status='STARTED_NOT_PASS',stage='PREFLIGHT',
            package_verified_files=count,backend='REAL_MATCHED_FPGA_PREFIX_PLUS_ARM_SUFFIX_224',
            source='live',scene_declared=scene,scene_is_not_ground_truth=True,notes=notes,
            requested_seconds=seconds,camera_index=camera_index,model='recover5',input_side=224,
            cpu_reference_cases=[],fpga_reference_cases=[],fpga_reference_forward_count=0,
            live_fpga_forward_count=0,frames=[],saved_bytes=0,camera_opened=False,
            camera_allowed_after_12_fpga_cases=False,new_overlay_load_attempted=False,
            new_overlay_loaded=False,old_hardware_restored=False,dma_quiesced=None,
            cpu_fallback_enabled=False,live_cpu_check_every_frame=True,model_identity=spec['model_sha256'],
            thresholds=[.35,.25,.5,.2],nms_iou=.45,tracking_performed=False,
            head_rider_association_performed=False,event_validation_performed=False,
            light_state=None,light_valid=False,latest_frame_guaranteed=False,
            capture_time_basis='PS monotonic after read returns; NOT sensor exposure',
            wall_time_may_be_wrong_on_board=True,
            timing_scope='FPGA+ARM forward includes exact packing/cache/DMA/guard/owned-copy/suffix/output; excludes capture/preprocess/CPU-reference/NMS/display/save/setup. Paired live check reduces preview FPS; not end-to-end sensor latency.',
            overlay_sha256={name:sha(ROOT/name) for name in ('overlay/rider_monitor_chain_float.bit','overlay/rider_monitor_chain_float.hwh')})
        def checkpoint(stage):
            report['stage'] = stage
            (directory/'RESULT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
            print('STAGE:',stage,flush=True)
        checkpoint('PREFLIGHT')
        session = HardwareSession(spec,directory,report,checkpoint)
        interrupted = False
        error = None
        try:
            session.prepare()
            collector = ROOT.parent/'camera_collect_v1'
            camera_io.ROOT = collector if collector.is_dir() else ROOT
            with camera_io._Camera(camera_index) as camera:
                report['camera_opened'] = True
                print('REAL FPGA+ARM recognition; every frame checked against CPU. 5-second countdown.',flush=True)
                for remaining in range(5,0,-1):
                    print('START IN',remaining,flush=True)
                    time.sleep(1)
                checkpoint('REAL_CAMERA_FPGA_RUNNING')
                handle = None
                started = time.monotonic()
                while time.monotonic()-started<seconds and len(report['frames'])<120:
                    if shutil.disk_usage(ROOT).free<192*1024*1024:
                        raise RuntimeError('Low disk space; previous results preserved')
                    frame,captured = camera.read()
                    raw,cpu,boxes,timing,proof = session.infer(frame)
                    painted = save_frame(directory,frame,raw,cpu,boxes,timing,proof,captured,report)
                    checkpoint('LIVE_FRAME_%d_SAVED'%len(report['frames']))
                    if not proof['same_frame_cpu_bit_exact']:
                        raise RuntimeError('LIVE_FPGA_CPU_BIT_MISMATCH; both raw outputs saved; NO CPU fallback')
                    handle = camera_io._display_frame(painted,handle)
                report['capture_loop_seconds'] = time.monotonic()-started
                if not report['frames']:
                    raise RuntimeError('No live FPGA frames saved')
                report['status'] = 'LIVE_FPGA_CPU_ALL_FRAMES_BIT_EXACT_NOT_FULL_SYSTEM_ACCEPTANCE'
        except KeyboardInterrupt:
            interrupted = True
            report['status'] = 'INTERRUPTED_PARTIAL_RESULTS'
        except BaseException:
            report['status'] = 'FPGA_CAMERA_FAILED_PARTIAL_RESULTS_RETAINED'
            report['error'] = traceback.format_exc()
            error = report['error']
            if session.dma is not None:
                try:
                    report['dma_at_failure'] = session.dma.snapshot()
                except BaseException:
                    pass
        finally:
            clean = session.close()
            report['safe_cleanup_complete'] = clean
            report['evidence_files_sha256'] = {
                p.name:sha(p) for p in directory.iterdir() if p.is_file() and p.suffix=='.npy' and p.name.startswith('case_')}
            if report['frames']:
                values = [f['timing']['fpga_plus_cpu_forward_ms'] for f in report['frames']]
                report['live_fpga_plus_cpu_forward'] = core.stats(values)
                report['all_saved_live_frames_cpu_bit_exact'] = all(f['proof']['same_frame_cpu_bit_exact'] for f in report['frames'])
            checkpoint('FINISHED')
            print('STATUS:',report['status'],flush=True)
            print('LIVE_FPGA_FORWARDS:',report['live_fpga_forward_count'],flush=True)
            print('DMA_QUIESCED:',report['dma_quiesced'],'OLD_HARDWARE_RESTORED:',report['old_hardware_restored'],flush=True)
            print('RESULT_DIR:',directory,flush=True)
        if not clean or error:
            raise RuntimeError('Stopped. Preserve RESULT.json in '+str(directory)+'\n'+(error or report['status']))
        if interrupted:
            print('Interrupted; hardware cleaned up and partial results retained.')
        return directory


def export(sessions):
    base = (ROOT/'results').resolve()
    paths,seen,total = [],set(),0
    for session in sessions:
        directory = Path(session).resolve()
        directory.relative_to(base)
        if directory.parent!=base or directory in seen:
            raise ValueError('Choose unique direct-child result directories')
        seen.add(directory)
        report = json.loads((directory/'RESULT.json').read_text(encoding='utf-8'))
        expected_files = dict(report.get('evidence_files_sha256',{}))
        for frame in report['frames']:
            expected_files.update(frame['files'])
        for name,expected in expected_files.items():
            path = (directory/name).resolve()
            if path.parent!=directory or sha(path)!=expected:
                raise RuntimeError('Result hash/path mismatch: '+name)
            paths.append(path)
            total += path.stat().st_size
        for name in ('RESULT.json','build.log'):
            path = directory/name
            if path.is_file():
                paths.append(path)
                total += path.stat().st_size
    if not paths or total>256*1024*1024:
        raise ValueError('Choose 1-3 short sessions, total <=256MiB')
    if shutil.disk_usage(ROOT).free<total+64*1024*1024:
        raise RuntimeError('Insufficient space for export')
    output = ROOT/('摄像头FPGA识别结果_发给我_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.zip')
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_STORED) as archive:
        for path in paths:
            archive.write(path,path.relative_to(base).as_posix())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Export ZIP CRC failed')
    print('DOWNLOAD:',output)
    return output


if __name__=='__main__':
    verify()
