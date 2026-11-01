"""Independent MJPG/YUYV experiment; unchanged real-FPGA inference backend.

Import opens no camera/FPGA. New camera path negotiates V4L2 explicitly,
retains encoded MJPG bytes, and decodes only the frames selected for inference.
The old camera/pipeline packages are not modified. Never queue CMA buffers.
"""
import contextlib
import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import queue
import struct
import threading
import time
import traceback
import uuid
import zipfile

import numpy as np
import pipeline as support
import fpga_camera as backend

ROOT = Path(__file__).resolve().parent
EXPECTED_ROOT = Path('/home/xilinx/jupyter_notebooks/traffic_project/camera_mjpg_v2')
NOTEBOOK = '打开我_MJPG取帧与去PNG实测.ipynb'
RETAINED_WORKERS = support.RETAINED_WORKERS
RETAINED_EVIDENCE = support.RETAINED_FAILURE_EVIDENCE
FORMAT_NAMES = ('YUYV', 'MJPG')
MAX_FRAMES = 120
RAM_LIMIT = 48*1024*1024


def fourcc(value):
    if not math.isfinite(float(value)):
        raise RuntimeError('Driver did not report a finite FOURCC')
    return int(value).to_bytes(4, 'little').decode('ascii', errors='replace')


def verify():
    manifest = json.loads((ROOT/'FILES_SHA256.json').read_text(encoding='utf-8'))
    if NOTEBOOK in manifest or 'mjpg_camera.py' not in manifest:
        raise RuntimeError('Unexpected package manifest')
    for name, digest in manifest.items():
        path = (ROOT/name).resolve()
        path.relative_to(ROOT.resolve())
        if not path.is_file() or support.sha(path) != digest:
            raise RuntimeError('Package hash mismatch: '+name)
    print('MJPG_PACKAGE_HASH_PASS:',len(manifest),'files; no camera/FPGA opened')
    return len(manifest)


def validate(seconds, camera_index, fps, programs_stopped):
    RETAINED_WORKERS[:] = [w for w in RETAINED_WORKERS if w.thread.is_alive()]
    if RETAINED_WORKERS or RETAINED_EVIDENCE or backend.RETAINED_SESSIONS:
        raise RuntimeError('Previous worker/DMA/evidence still retained; do not start a new test')
    if programs_stopped is not True:
        raise ValueError('Confirm all other camera/FPGA programs and kernels stopped')
    if (ROOT != EXPECTED_ROOT or backend.ROOT != ROOT or platform.system() != 'Linux' or
            platform.machine() != 'armv7l' or struct.calcsize('P') != 4):
        raise RuntimeError('Run in independent traffic_project/camera_mjpg_v2 on ARMv7 Linux')
    if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or not 0<seconds<=60:
        raise ValueError('seconds must be finite, >0, <=60')
    if type(camera_index) is not int or not 0<=camera_index<=15:
        raise ValueError('camera_index must be 0..15')
    if type(fps) is not int or fps not in (10,15,20,25,30):
        raise ValueError('fps must be one of 10,15,20,25,30')


@contextlib.contextmanager
def hardware_lock():
    import fcntl
    with (ROOT.parent/'.conv_board_exclusive.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def new_result(kind):
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    path = ROOT/'results'/(kind+'_'+stamp)
    path.mkdir(parents=True,exist_ok=False)
    return path


def packet_from_array(frame, name):
    if not isinstance(frame,np.ndarray) or frame.dtype != np.uint8:
        raise RuntimeError('Expected uint8 undecoded V4L2 payload')
    if name == 'MJPG':
        if frame.ndim != 2 or frame.shape[0] != 1 or not 32<=frame.size<=2*1024*1024:
            raise RuntimeError('MJPG raw retrieval unavailable; expected [1,encoded_bytes], got '+str(frame.shape))
        payload = frame.tobytes()
        if not payload.startswith(b'\xff\xd8') or b'\xff\xd9' not in payload[-64:]:
            raise RuntimeError('Returned MJPG payload is not a complete JPEG; no BGR fallback')
    elif name == 'YUYV':
        if frame.shape != (480,640,2):
            raise RuntimeError('Expected undecoded YUYV [480,640,2], got '+str(frame.shape))
        payload = frame.tobytes()
    else:
        raise ValueError('Unknown camera format')
    return payload


def decode(packet, metrics=None):
    import cv2
    t = time.perf_counter()
    data = np.frombuffer(packet['payload'],np.uint8)
    if packet['format'] == 'MJPG':
        frame = cv2.imdecode(data,cv2.IMREAD_COLOR)
    else:
        frame = cv2.cvtColor(data.reshape(480,640,2),cv2.COLOR_YUV2BGR_YUY2)
    if frame is None or frame.shape != (480,640,3) or frame.dtype != np.uint8:
        raise RuntimeError('Decoded frame is not original-size BGR uint8 [480,640,3]')
    if metrics is not None:
        metrics.elapsed('main.camera_decode_ms',t)
    frame.setflags(write=False)
    return frame


def encode_jpeg(frame, metrics):
    import cv2
    t = time.perf_counter()
    ok, jpeg = cv2.imencode('.jpg',frame,[int(cv2.IMWRITE_JPEG_QUALITY),80])
    if not ok:
        raise RuntimeError('Preview JPEG encoding failed')
    result = jpeg.tobytes()
    metrics.elapsed('main.jpeg_encode_once_ms',t)
    return result


def publish(jpeg,handle,metrics):
    from IPython.display import Image,display
    t = time.perf_counter()
    image = Image(data=jpeg)
    if handle is None:
        handle = display(image,display_id=True)
    else:
        handle.update(image)
    metrics.elapsed('main.display_publish_ms',t)
    return handle


class RawCamera:
    """Single explicit V4L2 stream; fail rather than silently convert/fallback."""
    def __init__(self,index,name,fps):
        if name not in FORMAT_NAMES:
            raise ValueError('Choose YUYV or MJPG')
        self.index,self.name,self.fps = index,name,fps
        self.cap = self.lock = None
        self.info = {}

    def __enter__(self):
        import cv2
        import fcntl
        directory = ROOT.parent/'camera_collect_v1'
        directory = directory if directory.is_dir() else ROOT
        self.lock = (directory/'.camera_collection.lock').open('a')
        try:
            fcntl.flock(self.lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.cap = cv2.VideoCapture(self.index,cv2.CAP_V4L2)
            if not self.cap.isOpened():
                raise RuntimeError('V4L2 camera could not open; check device index and other users')
            settings = [('FRAME_WIDTH',640),('FRAME_HEIGHT',480),
                        ('FOURCC',cv2.VideoWriter_fourcc(*self.name)),('FPS',self.fps),
                        ('BUFFERSIZE',1),('CONVERT_RGB',0)]
            accepted = {key:bool(self.cap.set(getattr(cv2,'CAP_PROP_'+key),value)) for key,value in settings}
            values = {key:float(self.cap.get(getattr(cv2,'CAP_PROP_'+key))) for key,_ in settings}
            self.info = dict(requested_format=self.name,requested_fps=self.fps,
                             set_returned=accepted,reported=values,
                             actual_fourcc=fourcc(values['FOURCC']),
                             raw_undecoded_requested=True,opencv_version=cv2.__version__,
                             opencv_threads=cv2.getNumThreads())
            if self.info['actual_fourcc'] != self.name or values['FRAME_WIDTH'] != 640 or values['FRAME_HEIGHT'] != 480:
                raise RuntimeError('Negotiated camera format/size differs: '+str(self.info))
            if not math.isfinite(values['FPS']) or abs(values['FPS']-self.fps)>.5:
                raise RuntimeError('Negotiated camera FPS differs: '+str(self.info))
            if not accepted['CONVERT_RGB'] or values['CONVERT_RGB'] != 0:
                raise RuntimeError('Undecoded V4L2 retrieval unsupported; no silent fallback')
            return self
        except BaseException:
            self.__exit__(None,None,None)
            raise

    def read(self):
        t = time.perf_counter()
        ok, data = self.cap.read()
        returned_ms = time.monotonic()*1000
        read_ms = (time.perf_counter()-t)*1000
        if not ok or data is None:
            raise RuntimeError('V4L2 camera read failed')
        t = time.perf_counter()
        payload = packet_from_array(data,self.name)
        return dict(format=self.name,payload=payload,returned_ms=returned_ms,read_api_ms=read_ms,
                    payload_copy_ms=(time.perf_counter()-t)*1000)

    def __exit__(self,*args):
        try:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
        finally:
            if self.lock is not None:
                self.lock.close()
                self.lock = None


class LatestCapture:
    """One latest encoded payload; decoding never runs on capture thread."""
    def __init__(self,index,name,fps,metrics):
        self.camera = RawCamera(index,name,fps)
        self.metrics = metrics
        self.stop_event,self.ready = threading.Event(),threading.Event()
        self.condition = threading.Condition()
        self.thread = None
        self.latest = None
        self.error = None
        self.rows = []
        self.count = 0
        self.first = None
        self.last = None

    def start(self):
        self.thread = threading.Thread(target=self._worker,name='encoded-camera-owner',daemon=True)
        self.thread.start()
        if not self.ready.wait(8):
            raise TimeoutError('Camera startup exceeded 8 seconds')
        if self.error:
            raise RuntimeError(self.error)

    def _worker(self):
        try:
            with self.camera:
                t = time.perf_counter()
                for _ in range(3):
                    warm = self.camera.read()
                decode(warm)  # One original-size/type check before timing.
                self.metrics.elapsed('setup.camera_warmup_ms',t)
                self.ready.set()
                while not self.stop_event.is_set():
                    item = self.camera.read()
                    self.count += 1
                    item['sequence'] = self.count
                    self.metrics.add('capture.read_api_ms',item['read_api_ms'])
                    self.metrics.add('capture.payload_copy_ms',item['payload_copy_ms'])
                    self.first = item['returned_ms'] if self.first is None else self.first
                    self.last = item['returned_ms']
                    if len(self.rows)<5000:
                        self.rows.append({key:value for key,value in item.items() if key!='payload'})
                    with self.condition:
                        self.latest = item
                        self.condition.notify_all()
        except BaseException:
            self.error = traceback.format_exc()
        finally:
            self.ready.set()
            with self.condition:
                self.condition.notify_all()

    def get(self,after):
        deadline = time.monotonic()+5
        with self.condition:
            while True:
                if self.error:
                    raise RuntimeError('Capture worker failed: '+self.error)
                if self.latest is not None and self.latest['sequence']>after:
                    return self.latest
                remaining = deadline-time.monotonic()
                if remaining<=0:
                    raise TimeoutError('No new camera payload within 5 seconds')
                self.condition.wait(min(.1,remaining))

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                if self not in RETAINED_WORKERS:
                    RETAINED_WORKERS.append(self)
                return False
        return True


def telemetry():
    result = dict(process_user_s=os.times().user,process_system_s=os.times().system)
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith(('VmRSS:','VmHWM:','Threads:')):
                result[line.split(':')[0]] = int(line.split()[1])
    except OSError:
        pass
    path = Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq')
    try:
        result['cpu0_frequency_khz'] = int(path.read_text().strip())
    except (OSError,ValueError):
        result['cpu0_frequency_khz'] = None
    return result


def write_report(directory,report,metrics,scope='main'):
    t = time.perf_counter()
    data = json.dumps(report,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    metrics.elapsed(scope+'.report_json_ms',t)
    t = time.perf_counter()
    temporary = directory/'RESULT.json.tmp'
    temporary.write_bytes(data)
    temporary.replace(directory/'RESULT.json')
    metrics.elapsed(scope+'.report_write_close_ms',t)


def probe_capture(name='MJPG',preview=True,seconds=8,camera_index=0,fps=15,programs_stopped=False):
    validate(seconds,camera_index,fps,programs_stopped)
    if name not in FORMAT_NAMES or type(preview) is not bool:
        raise ValueError('Choose MJPG/YUYV and boolean preview')
    verify()
    if support.shutil.disk_usage(ROOT).free<256*1024*1024:
        raise RuntimeError('Less than 256MiB free; no camera opened')
    with hardware_lock():
        directory = new_result('capture_'+name+('_preview' if preview else '_only'))
        metrics = support.Metrics()
        r = dict(kind='capture_probe',status='STARTED_NOT_PASS',format=name,preview=preview,
                 requested_fps=fps,requested_seconds=seconds,fpga_accessed=False,model_opened=False,
                 frames=[],files={},source_time_basis='PS read return, NOT sensor exposure',
                 mjpg_preview_passthrough=preview and name=='MJPG',browser_render_latency_measured=False)
        failed = None
        samples = []
        try:
            with RawCamera(camera_index,name,fps) as camera:
                r['camera'] = camera.info
                t = time.perf_counter()
                for _ in range(3):
                    packet = camera.read()
                decode(packet)
                r['warmup_ms'] = (time.perf_counter()-t)*1000
                print('CAPTURE PROBE:',name,'preview=',preview,'| no YOLO/FPGA/save inside timed loop',flush=True)
                handle = None
                started = time.monotonic()
                r['telemetry_start'] = telemetry()
                while time.monotonic()-started<seconds and len(r['frames'])<2000:
                    packet = camera.read()
                    metrics.add('capture.read_api_ms',packet['read_api_ms'])
                    metrics.add('capture.payload_copy_ms',packet['payload_copy_ms'])
                    row = dict(index=len(r['frames'])+1,returned_ms=packet['returned_ms'],
                               read_api_ms=packet['read_api_ms'],payload_copy_ms=packet['payload_copy_ms'],
                               payload_bytes=len(packet['payload']))
                    if preview:
                        # MJPG retains camera's JPEG. YUYV needs conversion+one JPEG.
                        jpeg = packet['payload'] if name=='MJPG' else encode_jpeg(decode(packet,metrics),metrics)
                        handle = publish(jpeg,handle,metrics)
                        row['display_submitted_ms'] = time.monotonic()*1000
                    r['frames'].append(row)
                    if not samples:
                        samples.append(packet)
                    elif len(samples)==1:
                        samples.append(packet)
                    else:
                        samples[1] = packet
                r['loop_seconds'] = time.monotonic()-started
                r['telemetry_end'] = telemetry()
            r['status'] = 'CAPTURE_PROBE_COMPLETE_NOT_DETECTION_ACCEPTANCE'
        except KeyboardInterrupt:
            r['status'] = 'INTERRUPTED_PARTIAL_RESULT'
        except BaseException:
            failed = r['error'] = traceback.format_exc()
            r['status'] = 'CAPTURE_PROBE_FAILED_NO_FALLBACK'
        finally:
            # Save at most first/last samples AFTER timing; no PNG compression.
            for index,packet in enumerate(samples):
                try:
                    stem = 'sample_%02d'%index
                    name_raw = stem+('.jpg' if packet['format']=='MJPG' else '.yuyv')
                    (directory/name_raw).write_bytes(packet['payload'])
                    r['files'][name_raw] = support.sha(directory/name_raw)
                    array_name = stem+'_bgr.npy'
                    np.save(directory/array_name,decode(packet),allow_pickle=False)
                    r['files'][array_name] = support.sha(directory/array_name)
                except BaseException:
                    failed = r['sample_save_error'] = traceback.format_exc()
                    r['status'] = 'SAMPLE_SAVE_FAILED_PARTIAL_RETAINED'
                    break
            elapsed = r.get('loop_seconds',0)
            r['captured_count'] = len(r['frames'])
            r['read_returns_per_second'] = len(r['frames'])/elapsed if elapsed else 0
            r['preview_submissions_per_second'] = sum('display_submitted_ms' in x for x in r['frames'])/elapsed if elapsed else 0
            r['metrics'] = metrics.summary()
            write_report(directory,r,metrics,scope='cleanup')
            print('STATUS:',r['status'],'| read FPS:',round(r['read_returns_per_second'],3),
                  '| preview submissions:',round(r['preview_submissions_per_second'],3),flush=True)
            print('RESULT_DIR:',directory,flush=True)
        if failed:
            raise RuntimeError('Stopped; preserve '+str(directory/'RESULT.json')+'\n'+failed)
        return directory


def capture_compare(seconds=8,camera_index=0,fps=15,programs_stopped=False):
    paths = []
    for preview in (False,True):
        for name in FORMAT_NAMES:
            paths.append(probe_capture(name,preview,seconds,camera_index,fps,programs_stopped))
    return paths


class RawWriter(support.Writer):
    """No image compression: BGR/tensor/prediction .npy plus reused JPEG."""
    def write(self,job):
        started = time.perf_counter()
        row = dict(id=job['id'],status='WRITING_NOT_COMPLETE',files={},timing_ms={})
        with self.lock:
            self.results.append(row)
        row = dict(row,files={},timing_ms={})
        try:
            wait = max(0.,(started-job['enqueued_at'])*1000)
            self.metrics.add('writer.queue_wait_ms',wait)
            t = time.perf_counter()
            stem = job['id']
            payloads = {stem+'_input_bgr.npy':support.npy_bytes(job['bgr']),
                        stem+'_input_224.npy':support.npy_bytes(job['input']),
                        stem+'_fpga_raw.npy':support.npy_bytes(job['raw']),
                        stem+'_boxes.npy':support.npy_bytes(job['boxes']),
                        stem+'_view.jpg':job['jpeg']}
            if job['cpu'] is not None:
                payloads[stem+'_cpu_raw.npy'] = support.npy_bytes(job['cpu'])
            if job['packet']['format']=='MJPG':
                payloads[stem+'_camera.jpg'] = job['packet']['payload']
            row['timing_ms']['serialize_ms'] = self.metrics.elapsed('writer.serialize_ms',t)
            size = sum(len(value) for value in payloads.values())
            if self.total_bytes+size>support.LIMIT_BYTES:
                raise RuntimeError('128MiB evidence limit; original files retained')
            if support.shutil.disk_usage(self.directory).free<size+128*1024*1024:
                raise RuntimeError('Low disk space; original files retained')
            write_ms = hash_ms = 0.
            for name,data in payloads.items():
                t = time.perf_counter()
                with (self.directory/name).open('xb') as stream:
                    stream.write(data)
                write_ms += (time.perf_counter()-t)*1000
                t = time.perf_counter()
                row['files'][name] = support.sha(self.directory/name)
                hash_ms += (time.perf_counter()-t)*1000
            self.metrics.add('writer.file_write_close_ms',write_ms)
            self.metrics.add('writer.hash_readback_ms',hash_ms)
            self.total_bytes += size
            row.update(status='SAVED',bytes=size)
            row['timing_ms'].update(queue_wait_ms=wait,file_write_close_ms=write_ms,hash_readback_ms=hash_ms)
        except BaseException:
            row.update(status='SAVE_FAILED_PARTIAL_RETAINED',error=traceback.format_exc())
            raise
        finally:
            row['timing_ms']['service_ms'] = self.metrics.elapsed('writer.service_ms',started)
            with self.lock:
                index = next(i for i,item in enumerate(self.results) if item['id']==row['id'])
                self.results[index] = row


def infer(session,frame,checked,metrics):
    t = time.perf_counter()
    x = backend.preprocess224(frame)
    preprocess_ms = metrics.elapsed('main.preprocess_ms',t)
    t = time.perf_counter()
    session.safe = False
    raw = session.candidate.forward(x)
    session.safe = True
    forward_ms = metrics.elapsed('main.fpga_arm_forward_ms',t)
    session.report['live_fpga_forward_count'] += 1
    cpu = None
    exact = None
    cpu_ms = 0.
    if checked:
        t = time.perf_counter()
        cpu = session.cpu.forward(x)
        cpu_ms = metrics.elapsed('main.cpu_reference_ms',t)
        t = time.perf_counter()
        exact = bool(backend.core.exact(raw,cpu))
        metrics.elapsed('main.exact_compare_ms',t)
    t = time.perf_counter()
    boxes = backend.decode224(raw)
    decode_ms = metrics.elapsed('main.decode_ms',t)
    proof = dict(cpu_checked=checked,same_frame_cpu_bit_exact=exact,fpga_forward_completed=True,
                 dma_registers_after_completed_forward=session.dma.snapshot())
    timing = dict(preprocess_ms=preprocess_ms,fpga_arm_forward_ms=forward_ms,
                  cpu_reference_ms=cpu_ms,decode_ms=decode_ms,components_ms=dict(session.candidate.last))
    return x,raw,cpu,boxes,proof,timing


def evidence_job(row,packet,frame,x,raw,cpu,boxes,jpeg):
    # All arrays are owned user-space objects, never CMA/DMA views.
    return dict(id=row['id'],packet=packet,bgr=frame,input=np.array(x,copy=True),
                raw=np.array(raw,copy=True),cpu=None if cpu is None else np.array(cpu,copy=True),
                boxes=np.array(boxes,copy=True),jpeg=jpeg,enqueued_at=time.perf_counter())


def job_bytes(job):
    return (sum(value.nbytes for value in (job['bgr'],job['input'],job['raw'],job['boxes']))+
            (0 if job['cpu'] is None else job['cpu'].nbytes)+len(job['jpeg'])+len(job['packet']['payload']))


def run_fpga(save_mode='deferred_checks',format_name='MJPG',scene='bare_head_static',notes='',
             seconds=20,camera_index=0,fps=15,programs_stopped=False,backup_on_pc_confirmed=False):
    validate(seconds,camera_index,fps,programs_stopped)
    if backup_on_pc_confirmed is not True:
        raise ValueError('Confirm complete traffic_project backup really saved on PC')
    if save_mode not in ('deferred_checks','raw_sampled') or format_name not in FORMAT_NAMES:
        raise ValueError('Choose deferred_checks/raw_sampled and MJPG/YUYV')
    if scene not in backend.camera_io.SCENES or not isinstance(notes,str) or len(notes)>2000:
        raise ValueError('Choose an actual scene and notes <=2000 characters')
    count = verify()
    if support.shutil.disk_usage(ROOT).free<512*1024*1024:
        raise RuntimeError('Less than 512MiB free; no camera or FPGA opened')
    with hardware_lock():
        directory = new_result('fpga_'+format_name+'_'+save_mode)
        spec = json.loads((ROOT/'SPEC.json').read_text(encoding='utf-8'))
        metrics = support.Metrics()
        writer = RawWriter(directory,metrics)
        camera = LatestCapture(camera_index,format_name,fps,metrics)
        r = dict(kind='fpga_probe',status='STARTED_NOT_PASS',format=format_name,save_mode=save_mode,
            requested_seconds=seconds,requested_fps=fps,scene_declared=scene,notes=notes,
            runtime_environment={key:os.environ.get(key) for key in
                ('OMP_NUM_THREADS','OMP_WAIT_POLICY','GOMP_SPINCOUNT','OPENBLAS_NUM_THREADS')},
            backend='REAL_MATCHED_FPGA_PREFIX_PLUS_ARM_SUFFIX_224',package_verified_files=count,
            cpu_reference_cases=[],fpga_reference_cases=[],fpga_reference_forward_count=0,
            live_fpga_forward_count=0,frames=[],model_identity=spec['model_sha256'],cpu_fallback_enabled=False,
            camera_allowed_after_12_fpga_cases=False,camera_opened=False,
            new_overlay_load_attempted=False,new_overlay_loaded=False,old_hardware_restored=False,dma_quiesced=None,
            thresholds=[.35,.25,.5,.2],nms_iou=.45,cpu_check_policy='first and every 10th inferred frame',
            saved_input_format='lossless uint8 BGR .npy + actual normalized 224 input .npy',
            camera_mjpg_is_lossy=True if format_name=='MJPG' else False,
            no_png_encoding=True,jpeg_encoded_once_per_inferred_frame=True,
            app_latest_payload_slot=True,sensor_latest_frame_guaranteed=False,
            browser_render_latency_measured=False,physical_sd_write_latency_measured=False,
            tracking_performed=False,event_validation_performed=False,full_system_accepted=False,
            overlay_sha256={name:support.sha(ROOT/name) for name in
                ('overlay/rider_monitor_chain_float.bit','overlay/rider_monitor_chain_float.hwh')})
        live = [False]
        def checkpoint(stage):
            r['stage'] = stage
            if not live[0]:
                print('STAGE:',stage,flush=True)
            snapshot = dict(r,saved_frames=writer.snapshot())
            write_report(directory,snapshot,metrics,'main' if live[0] else 'setup_or_cleanup')
        session = backend.HardwareSession(spec,directory,r,checkpoint)
        started = None
        failed = None
        interrupted = False
        clean = False
        camera_stopped = writer_stopped = False
        last_sequence = skipped = 0
        deferred = []
        deferred_bytes = 0
        try:
            checkpoint('PREFLIGHT')
            session.prepare()  # Pinned 12 CPU + 12 FPGA exact checks, no weakened tolerance.
            camera.start()
            r['camera_opened'] = True
            if save_mode=='raw_sampled':
                writer.start()
            print('REAL FPGA:',format_name,save_mode,'| same-frame boxes, no CPU fallback',flush=True)
            handle = None
            last_saved = last_report = -float('inf')
            started = time.monotonic()
            r['telemetry'] = [dict(wall_s=0,**telemetry())]
            live[0] = True
            while time.monotonic()-started<seconds and len(r['frames'])<MAX_FRAMES:
                iteration = time.perf_counter()
                writer.raise_if_failed()
                t = time.perf_counter()
                packet = camera.get(last_sequence)
                metrics.elapsed('main.acquire_wait_ms',t)
                skipped += max(0,packet['sequence']-last_sequence-1)
                last_sequence = packet['sequence']
                age = max(0.,time.monotonic()*1000-packet['returned_ms'])
                metrics.add('main.frame_age_before_decode_ms',age)
                frame = decode(packet,metrics)
                number = len(r['frames'])+1
                checked = number==1 or number%10==0
                x,raw,cpu,boxes,proof,timing = infer(session,frame,checked,metrics)
                t = time.perf_counter()
                painted = support.paint(frame,boxes,timing,proof)
                draw_ms = metrics.elapsed('main.draw_ms',t)
                jpeg = encode_jpeg(painted,metrics)  # Also reused by saved view.jpg, never recompressed.
                row = dict(id='frame_%06d'%number,capture_sequence=packet['sequence'],
                    capture_returned_ms=packet['returned_ms'],frame_age_before_decode_ms=age,
                    camera_payload_bytes=len(packet['payload']),detections_xyxy_score_class=boxes.tolist(),
                    timing=timing,proof=proof,draw_ms=draw_ms,save_state='NOT_SELECTED')
                r['frames'].append(row)
                mismatch = checked and not proof['same_frame_cpu_bit_exact']
                now = time.monotonic()
                select = checked or (save_mode=='raw_sampled' and now-last_saved>=2)
                if select:
                    t = time.perf_counter()
                    job = evidence_job(row,packet,frame,x,raw,cpu,boxes,jpeg)
                    metrics.elapsed('main.evidence_snapshot_ms',t)
                    if mismatch:
                        RETAINED_EVIDENCE.append(job)
                        r['mismatch_evidence_retained_in_ram'] = True
                        if not writer.stop():
                            raise RuntimeError('Mismatch retained in RAM; writer still active')
                        writer.raise_if_failed()
                        writer.write(job)
                        RETAINED_EVIDENCE.remove(job)
                        r['mismatch_evidence_retained_in_ram'] = False
                        row['save_state'] = 'SAVED_MISMATCH'
                        raise RuntimeError('LIVE_FPGA_CPU_BIT_MISMATCH; stopped without fallback')
                    if save_mode=='deferred_checks':
                        size = job_bytes(job)
                        if deferred_bytes+size>RAM_LIMIT:
                            raise RuntimeError('48MiB deferred evidence limit; stop, do not grow memory')
                        deferred.append(job)
                        deferred_bytes += size
                        row['save_state'] = 'DEFERRED_UNTIL_AFTER_TIMER'
                    else:
                        row['save_state'] = 'QUEUED' if writer.enqueue(job) else 'DROPPED_QUEUE_FULL'
                    last_saved = now
                handle = publish(jpeg,handle,metrics)
                row['display_submitted_ms'] = time.monotonic()*1000
                metrics.add('main.read_return_to_display_submit_ms',max(0.,row['display_submitted_ms']-packet['returned_ms']))
                if now-last_report>=1:
                    r['telemetry'].append(dict(wall_s=time.monotonic()-started,**telemetry()))
                    checkpoint('LIVE_FRAME_%d'%number)
                    last_report = now
                row['iteration_wall_ms'] = metrics.elapsed('main.iteration_wall_ms',iteration)
            r['loop_seconds'] = time.monotonic()-started
            r['telemetry'].append(dict(wall_s=r['loop_seconds'],**telemetry()))
            if not r['frames']:
                raise RuntimeError('No live FPGA frames completed')
            r['status'] = 'FPGA_MEASUREMENT_COMPLETE_NOT_FULL_SYSTEM_ACCEPTANCE'
        except KeyboardInterrupt:
            interrupted = True
            r['status'] = 'INTERRUPTED_PARTIAL_RESULT'
        except BaseException:
            failed = r['error'] = traceback.format_exc()
            r['status'] = 'FPGA_MEASUREMENT_FAILED_PARTIAL_RETAINED'
        finally:
            if started is not None and 'loop_seconds' not in r:
                r['loop_seconds'] = time.monotonic()-started
            live[0] = False
            # Storage/USB exceptions cannot bypass the pinned DMA reset/free/rollback.
            try:
                camera.stop_event.set()
                clean = session.close()
            finally:
                try:
                    camera_stopped = camera.stop()
                except BaseException:
                    r['camera_stop_error'] = traceback.format_exc()
                try:
                    t = time.perf_counter()
                    writer_stopped = writer.stop()
                    metrics.elapsed('cleanup.writer_drain_ms',t)
                except BaseException:
                    r['writer_stop_error'] = traceback.format_exc()
            # Deferred lossless evidence is written only after camera/FPGA stop.
            try:
                if writer_stopped:
                    t = time.perf_counter()
                    for job in deferred:
                        writer.write(job)
                    metrics.elapsed('cleanup.deferred_write_ms',t)
                    deferred.clear()
            except BaseException:
                r['deferred_save_error'] = traceback.format_exc()
                RETAINED_EVIDENCE.extend(deferred)
                failed = failed or r['deferred_save_error']
                r['status'] = 'DEFERRED_SAVE_FAILED_EVIDENCE_RETAINED_IN_RAM'
            saved = writer.snapshot()
            r.update(safe_cleanup_complete=clean,capture_worker_stopped=camera_stopped,
                writer_worker_stopped=writer_stopped,camera=camera.camera.info,
                capture_samples=camera.rows,captured_read_count=camera.count,
                capture_telemetry_truncated=camera.count>len(camera.rows),
                skipped_before_inference=skipped,not_selected_tail=max(0,camera.count-last_sequence),
                saved_frames=saved,saved_bytes=writer.total_bytes,save_queue_dropped=writer.dropped,
                save_queue_high_water=writer.high_water,save_queue_capacity=2,
                deferred_ram_bytes=deferred_bytes,camera_error=camera.error,writer_error=writer.error)
            by_id = {item['id']:item['status'] for item in saved}
            for row in r['frames']:
                if row['save_state'] in ('QUEUED','DEFERRED_UNTIL_AFTER_TIMER'):
                    row['save_state'] = by_id.get(row['id'],'NOT_WRITTEN_WORKER_FAILED_OR_PENDING')
            if not camera_stopped or not writer_stopped or camera.error or writer.error:
                failed = failed or str(dict(camera=camera.error,writer=writer.error))
                r['status'] = 'WORKER_FAILURE_OR_TIMEOUT_PARTIAL_RESULT'
            checked = [row for row in r['frames'] if row['proof']['cpu_checked']]
            r['checked_count'] = len(checked)
            r['unchecked_count'] = len(r['frames'])-len(checked)
            r['checked_frames_all_bit_exact'] = bool(checked) and all(row['proof']['same_frame_cpu_bit_exact'] for row in checked)
            elapsed = r.get('loop_seconds',0)
            r['inference_fps'] = len(r['frames'])/elapsed if elapsed else 0.
            r['display_submissions_per_second'] = sum('display_submitted_ms' in row for row in r['frames'])/elapsed if elapsed else 0.
            r['capture_read_returns_per_second'] = ((camera.count-1)*1000/(camera.last-camera.first)
                if camera.count>1 and camera.last>camera.first else None)
            r['saved_frames_count'] = sum(item['status']=='SAVED' for item in saved)
            r['evidence_files_sha256'] = {p.name:support.sha(p) for p in directory.iterdir()
                if p.is_file() and p.name.startswith('case_') and p.suffix=='.npy'}
            r['metrics'] = metrics.summary()
            checkpoint('FINISHED')
            print('STATUS:',r['status'],'| inferred FPS:',round(r['inference_fps'],3),
                  '| checked:',r['checked_count'],'| unchecked:',r['unchecked_count'],flush=True)
            print('DMA_QUIESCED:',r['dma_quiesced'],'OLD_HARDWARE_RESTORED:',r['old_hardware_restored'],flush=True)
            print('RESULT_DIR:',directory,flush=True)
        if failed or not clean or not camera_stopped or not writer_stopped:
            raise RuntimeError('Stopped; preserve '+str(directory/'RESULT.json')+'\n'+str(failed or r['status']))
        if interrupted:
            print('Interrupted with partial results only; not a PASS')
        return directory


def summarize(sessions):
    rows = []
    for directory in sessions:
        path = Path(directory).resolve()
        if path.parent != (ROOT/'results').resolve():
            raise ValueError('Choose direct-child result directories')
        r = json.loads((path/'RESULT.json').read_text(encoding='utf-8'))
        mean = lambda key:round(r['metrics'].get(key,{}).get('mean_ms',0),2)
        row = dict(kind=r['kind'],format=r['format'],status=r['status'],
            preview=r.get('preview'),save_mode=r.get('save_mode'),
            read_fps=r.get('read_returns_per_second',r.get('capture_read_returns_per_second')),
            inferred_fps=r.get('inference_fps'),display_submissions_fps=r.get('preview_submissions_per_second',r.get('display_submissions_per_second')),
            read_ms=mean('capture.read_api_ms'),decode_ms=mean('main.camera_decode_ms'),
            forward_ms=mean('main.fpga_arm_forward_ms'),jpeg_encode_ms=mean('main.jpeg_encode_once_ms'),
            publish_ms=mean('main.display_publish_ms'),writer_ms=mean('writer.service_ms'),
            save_drops=r.get('save_queue_dropped',0),checked=r.get('checked_count'),unchecked=r.get('unchecked_count'))
        rows.append(row)
        print(json.dumps(row,ensure_ascii=False,indent=2))
    print('Read returns / display submissions / inference FPS differ. Browser rendering and sensor latency NOT measured.')
    return rows


def export(sessions):
    if any(w.thread.is_alive() for w in RETAINED_WORKERS):
        raise RuntimeError('Worker still active; cannot export changing files')
    base = (ROOT/'results').resolve()
    paths,seen,total = [],set(),0
    for session in sessions:
        directory = Path(session).resolve()
        if directory.parent!=base or directory in seen:
            raise ValueError('Choose unique direct-child result directories')
        seen.add(directory)
        r = json.loads((directory/'RESULT.json').read_text(encoding='utf-8'))
        if r['kind']=='fpga_probe' and (r.get('capture_worker_stopped') is not True or r.get('writer_worker_stopped') is not True):
            raise RuntimeError('Worker stop not confirmed; preserve files and investigate')
        expected = dict(r.get('files',{}),**r.get('evidence_files_sha256',{}))
        for saved in r.get('saved_frames',[]):
            expected.update(saved['files'])
        for name,digest in expected.items():
            path = (directory/name).resolve()
            if path.parent!=directory or support.sha(path)!=digest:
                raise RuntimeError('Evidence path/hash mismatch: '+name)
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix in ('.npy','.yuyv','.jpg','.json','.log'):
                paths.append(path)
                total += path.stat().st_size
    if not paths or total>384*1024*1024 or support.shutil.disk_usage(ROOT).free<total+64*1024*1024:
        raise RuntimeError('Export needs <=384MiB results and enough free disk space')
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    output = ROOT/('MJPG取帧与去PNG实测结果_发给我_'+stamp+'.zip')
    manifest = {path.relative_to(base).as_posix():support.sha(path) for path in paths}
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_STORED) as archive:
        for path in paths:
            archive.write(path,path.relative_to(base).as_posix())
        archive.writestr('RESULT_FILES_SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Export ZIP CRC failed')
    print('DOWNLOAD:',output)
    return output
