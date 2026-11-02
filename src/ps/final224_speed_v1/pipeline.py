"""Bounded camera pipeline experiment. Unchanged model and real FPGA backend.

No device access on import. Timing is host API timing, NOT exposure-to-browser
latency or physical SD write latency. Hardware/CMA lifetime remains owned by
the pinned fpga_camera.HardwareSession and its original reset-before-free path.
"""
import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import queue
import shutil
import struct
import threading
import time
import traceback
import uuid
import zipfile

import numpy as np
import fpga_camera as backend

ROOT = Path(__file__).resolve().parent
EXPECTED_ROOT = Path('/home/xilinx/jupyter_notebooks/traffic_project/camera_pipeline_v1')
NOTEBOOK = '打开我_取帧存储分项诊断.ipynb'
MODES = {
    'serial_probe': dict(background=False, check_every=1, save_interval=0, report_interval=0),
    'async_probe': dict(background=True, check_every=1, save_interval=0, report_interval=1),
    'realtime': dict(background=True, check_every=10, save_interval=1, report_interval=1),
}
LIMIT_BYTES = 128 * 1024 * 1024
MAX_INFERRED = 120
RETAINED_WORKERS = []
RETAINED_FAILURE_EVIDENCE = []  # Ordinary RAM only; never CMA or DMA owners.


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify():
    manifest = json.loads((ROOT / 'FILES_SHA256.json').read_text(encoding='utf-8'))
    if NOTEBOOK in manifest or not manifest or 'pipeline.py' not in manifest:
        raise RuntimeError('Unexpected immutable manifest; Notebook must remain editable')
    for name, expected in manifest.items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT.resolve())
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError('Package hash mismatch: ' + name)
    print('PIPELINE_PACKAGE_HASH_PASS:', len(manifest), 'immutable files; no device opened')
    return len(manifest)


class Metrics:
    """Bounded samples, exact count/sum/extrema, sampled percentiles if >10000."""
    def __init__(self):
        self.lock = threading.Lock()
        self.values = {}

    def add(self, name, milliseconds):
        value = float(milliseconds)
        if not math.isfinite(value) or value < 0:
            raise ValueError('Invalid timing: ' + name)
        with self.lock:
            entry = self.values.setdefault(name, dict(count=0, total=0., minimum=value,
                                                     maximum=value, samples=[]))
            entry['count'] += 1
            entry['total'] += value
            entry['minimum'] = min(value, entry['minimum'])
            entry['maximum'] = max(value, entry['maximum'])
            if len(entry['samples']) < 10000:
                entry['samples'].append(value)

    def elapsed(self, name, started):
        value = (time.perf_counter() - started) * 1000
        self.add(name, value)
        return value

    def summary(self):
        with self.lock:
            snapshot = {name: dict(entry, samples=list(entry['samples']))
                        for name, entry in self.values.items()}
        return {name: dict(count=e['count'], total_ms=e['total'],
                          mean_ms=e['total']/e['count'], min_ms=e['minimum'], max_ms=e['maximum'],
                          p50_ms=float(np.percentile(e['samples'], 50)),
                          p95_ms=float(np.percentile(e['samples'], 95)),
                          percentile_samples=len(e['samples']))
                for name, e in snapshot.items()}


class Capture:
    """One owner of the USB camera, one replaceable application frame slot.

    This removes the application FIFO only. A V4L2/USB/sensor FIFO may remain;
    read-return monotonic timestamps cannot establish physical exposure age.
    """
    def __init__(self, index, metrics, root):
        self.index, self.metrics = index, metrics
        self.condition = threading.Condition()
        self.stop_event = threading.Event()
        self.opened = threading.Event()
        self.latest = None
        self.error = None
        self.count = 0
        self.rows = []
        self.info = {}
        self.thread = None
        self.camera = None
        self.root = root

    def open(self):
        backend.camera_io.ROOT = self.root
        self.camera = backend.camera_io._Camera(self.index)
        self.camera.__enter__()
        cap = getattr(self.camera, 'cap', None)
        if cap is not None:
            import cv2
            for name in ('FRAME_WIDTH', 'FRAME_HEIGHT', 'FPS', 'FOURCC', 'BUFFERSIZE'):
                prop = getattr(cv2, 'CAP_PROP_' + name, None)
                if prop is not None:
                    try:
                        value = float(cap.get(prop))
                        self.info[name] = value if math.isfinite(value) else None
                    except Exception:
                        self.info[name] = None
        self.info['requested'] = dict(width=640, height=480, fps=15, buffersize=1)
        self.info['properties_not_proof_of_actual_sensor_rate'] = True

    def read_owned(self):
        start = time.perf_counter()
        frame, returned_ms = self.camera.read()
        end = time.perf_counter()
        read_ms = (end-start)*1000
        self.metrics.add('capture.read_api_ms', read_ms)
        copied = time.perf_counter()
        frame = np.array(frame, copy=True, order='C')
        frame.setflags(write=False)
        self.metrics.elapsed('capture.owned_copy_ms', copied)
        self.count += 1
        item = dict(sequence=self.count, frame=frame, returned_ms=returned_ms,
                    read_api_ms=read_ms)
        if len(self.rows) < 10000:
            self.rows.append(dict(sequence=self.count, read_api_ms=read_ms,
                                  returned_ms=returned_ms))
        return item

    def start(self):
        self.thread = threading.Thread(target=self._worker, name='single-camera-owner', daemon=True)
        self.thread.start()
        if not self.opened.wait(timeout=5):
            raise TimeoutError('Camera initialization did not return within 5 seconds')
        if self.error:
            raise RuntimeError('Camera initialization failed: '+self.error)

    def _worker(self):
        try:
            self.open()
            self.opened.set()
            while not self.stop_event.is_set():
                item = self.read_owned()
                with self.condition:
                    self.latest = item
                    self.condition.notify_all()
        except BaseException:
            self.error = traceback.format_exc()
        finally:
            self.opened.set()
            try:
                if self.camera is not None:
                    self.camera.__exit__(None, None, None)
            except BaseException:
                self.error = (self.error or '') + traceback.format_exc()
            with self.condition:
                self.condition.notify_all()

    def get(self, after, timeout=5):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                if self.error:
                    raise RuntimeError('Camera worker failed: ' + self.error)
                if self.latest is not None and self.latest['sequence'] > after:
                    return self.latest
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('No new camera read returned within 5 seconds')
                self.condition.wait(min(remaining, .1))

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                if self not in RETAINED_WORKERS:
                    RETAINED_WORKERS.append(self)
                return False
        elif self.camera is not None:
            self.camera.__exit__(None, None, None)
        return True


def npy_bytes(array):
    stream = io.BytesIO()
    np.save(stream, array, allow_pickle=False)
    return stream.getvalue()


class Writer:
    """Two waiting jobs maximum, one active job. No device/CMA references."""
    def __init__(self, directory, metrics):
        self.directory, self.metrics = directory, metrics
        self.queue = queue.Queue(maxsize=2)
        self.stop_event = threading.Event()
        self.thread = None
        self.error = None
        self.results = []
        self.lock = threading.Lock()
        self.total_bytes = 0
        self.accepted = self.dropped = self.high_water = 0

    def start(self):
        self.thread = threading.Thread(target=self._worker, name='bounded-evidence-writer', daemon=True)
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return list(self.results)

    def raise_if_failed(self):
        if self.error:
            raise RuntimeError('Storage worker failed; partial files retained: ' + self.error)

    def enqueue(self, job):
        self.raise_if_failed()
        try:
            self.queue.put_nowait(job)
        except queue.Full:
            self.dropped += 1
            return False
        self.accepted += 1
        self.high_water = max(self.high_water, self.queue.qsize())
        return True

    def write(self, job):
        import cv2
        row = dict(id=job['id'], files={}, timing_ms={}, status='WRITING_NOT_COMPLETE')
        with self.lock:
            self.results.append(row)
        # The published row is only read after writer join or under this lock.
        # All edits below are local until the replacement at the end.
        row = dict(row, files={}, timing_ms={})
        started = time.perf_counter()
        try:
            wait = max(0., (started-job['enqueued_at'])*1000)
            row['timing_ms']['queue_wait_ms'] = wait
            self.metrics.add('writer.queue_wait_ms', wait)
            t = time.perf_counter()
            ok, png = cv2.imencode('.png', job['frame'], [int(cv2.IMWRITE_PNG_COMPRESSION), 3])
            row['timing_ms']['png_encode_ms'] = self.metrics.elapsed('writer.png_encode_ms', t)
            t = time.perf_counter()
            ok_jpg, jpg = cv2.imencode('.jpg', job['painted'], [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            row['timing_ms']['jpeg_encode_ms'] = self.metrics.elapsed('writer.jpeg_encode_ms', t)
            if not ok or not ok_jpg:
                raise RuntimeError('PNG/JPEG encoder failed')
            t = time.perf_counter()
            stem = job['id']
            payloads = {stem+'.png':png.tobytes(), stem+'_fpga_raw.npy':npy_bytes(job['raw']),
                        stem+'_boxes.npy':npy_bytes(job['boxes']), stem+'_view.jpg':jpg.tobytes()}
            if job['cpu'] is not None:
                payloads[stem+'_cpu_raw.npy'] = npy_bytes(job['cpu'])
            row['timing_ms']['npy_serialize_ms'] = self.metrics.elapsed('writer.npy_serialize_ms', t)
            size = sum(len(payload) for payload in payloads.values())
            if self.total_bytes+size > LIMIT_BYTES:
                raise RuntimeError('128MiB evidence limit; previous files retained')
            if shutil.disk_usage(self.directory).free < size+128*1024*1024:
                raise RuntimeError('Low disk space; previous files retained')
            write_ms = hash_ms = 0.
            for name, payload in payloads.items():
                t = time.perf_counter()
                with (self.directory/name).open('xb') as stream:
                    stream.write(payload)
                write_ms += (time.perf_counter()-t)*1000
                t = time.perf_counter()
                row['files'][name] = sha(self.directory/name)
                hash_ms += (time.perf_counter()-t)*1000
            self.metrics.add('writer.file_write_close_ms', write_ms)
            self.metrics.add('writer.hash_readback_ms', hash_ms)
            row['timing_ms'].update(file_write_close_ms=write_ms, hash_readback_ms=hash_ms)
            self.total_bytes += size
            row.update(status='SAVED', bytes=size)
        except BaseException:
            row.update(status='SAVE_FAILED_PARTIAL_FILES_RETAINED', error=traceback.format_exc())
            raise
        finally:
            row['timing_ms']['writer_service_ms'] = self.metrics.elapsed('writer.service_ms', started)
            with self.lock:
                index = next(i for i, r in enumerate(self.results) if r['id'] == row['id'])
                self.results[index] = row

    def _worker(self):
        try:
            while not self.stop_event.is_set() or not self.queue.empty():
                try:
                    job = self.queue.get(timeout=.1)
                except queue.Empty:
                    continue
                try:
                    self.write(job)
                finally:
                    self.queue.task_done()
        except BaseException:
            self.error = traceback.format_exc()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=15)
            if self.thread.is_alive():
                if self not in RETAINED_WORKERS:
                    RETAINED_WORKERS.append(self)
                return False
        return True


def infer(session, frame, check, metrics):
    t = time.perf_counter()
    x = backend.preprocess224(frame)
    preprocess_ms = metrics.elapsed('main.preprocess_ms', t)
    t = time.perf_counter()
    session.safe = False
    raw = session.candidate.forward(x)
    session.safe = True
    forward_ms = metrics.elapsed('main.fpga_arm_forward_ms', t)
    session.report['live_fpga_forward_count'] += 1
    cpu = None
    exact = None
    cpu_ms = 0.
    compare_ms = 0.
    if check:
        t = time.perf_counter()
        cpu = session.cpu.forward(x)
        cpu_ms = metrics.elapsed('main.cpu_reference_ms', t)
        t = time.perf_counter()
        exact = bool(backend.core.exact(raw, cpu))
        compare_ms = metrics.elapsed('main.exact_compare_ms', t)
    t = time.perf_counter()
    boxes = backend.decode224(raw)
    decode_ms = metrics.elapsed('main.decode_ms', t)
    t = time.perf_counter()
    proof = dict(fpga_forward_completed=True, cpu_checked=check, same_frame_cpu_bit_exact=exact,
                 dma_registers_after_completed_forward=session.dma.snapshot())
    metrics.elapsed('main.dma_status_snapshot_ms', t)
    return raw, cpu, boxes, proof, dict(fpga_arm_forward_ms=forward_ms, cpu_reference_ms=cpu_ms,
                                      preprocess_ms=preprocess_ms, exact_compare_ms=compare_ms,
                                      decode_ms=decode_ms,
                                      components_ms=dict(session.candidate.last))


def paint(frame, boxes, timing, proof):
    import cv2
    image = frame.copy()
    for x1, y1, x2, y2, score, cls in boxes:
        cls = int(cls)
        a = (max(0, min(639, int(round(float(x1))))), max(0, min(479, int(round(float(y1))))))
        b = (max(0, min(639, int(round(float(x2))))), max(0, min(479, int(round(float(y2))))))
        cv2.rectangle(image, a, b, backend.COLORS[cls], 2)
        cv2.putText(image, '%s %.2f'%(backend.NAMES[cls], score), (a[0], max(15, a[1]-5)),
                    cv2.FONT_HERSHEY_SIMPLEX, .48, backend.COLORS[cls], 1, cv2.LINE_AA)
    checked = ('EXACT' if proof['same_frame_cpu_bit_exact'] else 'FAILED') if proof['cpu_checked'] else 'NOT CHECKED'
    cv2.putText(image, 'FPGA+ARM %.1f ms | CPU %s'%(timing['fpga_arm_forward_ms'], checked),
                (6, 465), cv2.FONT_HERSHEY_SIMPLEX, .48, (0,255,255), 1, cv2.LINE_AA)
    return image


def show(frame, handle, metrics):
    import cv2
    from IPython.display import Image, display
    t = time.perf_counter()
    ok, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    metrics.elapsed('main.display_jpeg_encode_ms', t)
    if not ok:
        raise RuntimeError('Preview JPEG encoder failed')
    t = time.perf_counter()
    image = Image(data=jpeg.tobytes())
    if handle is None:
        handle = display(image, display_id=True)
    else:
        handle.update(image)
    metrics.elapsed('main.display_publish_ms', t)
    return handle


def validate(mode, scene, notes, seconds, index, backup_on_pc_confirmed, programs_stopped, display_on):
    # Never resume while a background camera/writer still owns resources/files.
    RETAINED_WORKERS[:] = [w for w in RETAINED_WORKERS if w.thread.is_alive()]
    if RETAINED_WORKERS or RETAINED_FAILURE_EVIDENCE or backend.RETAINED_SESSIONS:
        raise RuntimeError('Retained worker/DMA owner: stop and resolve previous session first')
    if backup_on_pc_confirmed is not True or programs_stopped is not True:
        raise ValueError('Confirm full PC backup and other camera/FPGA kernels stopped')
    if (ROOT != EXPECTED_ROOT or backend.ROOT != ROOT or platform.system() != 'Linux' or
            platform.machine() != 'armv7l' or struct.calcsize('P') != 4):
        raise RuntimeError('Run from independent traffic_project/camera_pipeline_v1 on ARMv7 Linux')
    if mode not in MODES or scene not in backend.camera_io.SCENES:
        raise ValueError('Unknown mode/scene')
    if not isinstance(notes, str) or len(notes) > 2000 or type(display_on) is not bool:
        raise ValueError('notes <=2000 characters; display_on must be bool')
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or
            not math.isfinite(seconds) or not 0 < seconds <= 60):
        raise ValueError('seconds must be >0 and <=60')
    if type(index) is not int or not 0 <= index <= 15:
        raise ValueError('camera_index must be 0..15')


def run(mode='serial_probe', scene='empty_scene', notes='', seconds=15, camera_index=0,
        display_on=True, backup_on_pc_confirmed=False, programs_stopped=False):
    validate(mode, scene, notes, seconds, camera_index, backup_on_pc_confirmed, programs_stopped, display_on)
    count = verify()
    if shutil.disk_usage(ROOT).free < 512*1024*1024:
        raise RuntimeError('Less than 512MiB free; no camera/hardware opened')
    import fcntl
    with (ROOT.parent/'.conv_board_exclusive.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = MODES[mode]
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
        directory = ROOT/'results'/(mode+'_'+stamp)
        directory.mkdir(parents=True, exist_ok=False)
        spec = json.loads((ROOT/'SPEC.json').read_text(encoding='utf-8'))
        metrics = Metrics()
        writer = Writer(directory, metrics)
        report = dict(schema_version=1, mode=mode, config=config, status='STARTED_NOT_PASS',
            scene_declared=scene, notes=notes, requested_seconds=seconds, display_on=display_on,
            backend='REAL_FPGA_PREFIX_PLUS_ARM_SUFFIX_RECOVER5_224', package_verified_files=count,
            cpu_reference_cases=[], fpga_reference_cases=[], fpga_reference_forward_count=0,
            live_fpga_forward_count=0, frames=[], camera_opened=False,
            new_overlay_load_attempted=False, new_overlay_loaded=False, old_hardware_restored=False,
            dma_quiesced=None, model_identity=spec['model_sha256'], cpu_fallback_enabled=False,
            camera_allowed_after_12_fpga_cases=False, thresholds=[.35,.25,.5,.2], nms_iou=.45,
            app_latest_frame_slot=config['background'], sensor_latest_frame_guaranteed=False,
            cpu_check_policy='first and every %d inferred frame'%config['check_every'],
            tracking_performed=False, event_validation_performed=False, full_system_accepted=False,
            browser_render_latency_measured=False, physical_sd_write_latency_measured=False,
            source_time_basis='PS monotonic after read returns; NOT sensor exposure',
            timing_scopes='capture/main/writer overlap in async modes; do NOT add their totals',
            overlay_sha256={name:sha(ROOT/name) for name in
                           ('overlay/rider_monitor_chain_float.bit','overlay/rider_monitor_chain_float.hwh')})
        measuring = [False]

        def checkpoint(stage):
            report['stage'] = stage
            prefix = 'main' if measuring[0] else 'setup_or_cleanup'
            if not measuring[0]:
                print('STAGE:', stage, flush=True)
            t = time.perf_counter()
            snapshot = dict(report, saved_frames=writer.snapshot())
            data = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            metrics.elapsed(prefix+'.report_json_ms', t)
            t = time.perf_counter()
            temporary = directory/'RESULT.json.tmp'
            temporary.write_bytes(data)
            temporary.replace(directory/'RESULT.json')
            metrics.elapsed(prefix+'.report_write_close_ms', t)

        session = backend.HardwareSession(spec, directory, report, checkpoint)
        camera = Capture(camera_index, metrics, ROOT.parent/'camera_collect_v1'
                         if (ROOT.parent/'camera_collect_v1').is_dir() else ROOT)
        started = None
        failed = None
        interrupted = False
        clean = False
        capture_stopped = writer_stopped = False
        last_sequence = skipped = 0
        try:
            checkpoint('PREFLIGHT')
            session.prepare()  # unchanged 12 CPU + 12 FPGA exact reference checks
            print('MODE:', mode, '| same-frame boxes, not independent high-FPS video', flush=True)
            print('Capture duration excludes startup/build; CTRL+C retains partial results.', flush=True)
            if config['background']:
                writer.start()
                camera.start()
            else:
                camera.open()
            report['camera_opened'] = True
            measuring[0] = True
            started = time.monotonic()
            last_saved = last_report = -float('inf')
            handle = None
            while time.monotonic()-started < seconds and len(report['frames']) < MAX_INFERRED:
                iteration = time.perf_counter()
                writer.raise_if_failed()
                t = time.perf_counter()
                if shutil.disk_usage(directory).free < 192*1024*1024:
                    raise RuntimeError('Low disk space; stop and preserve evidence')
                metrics.elapsed('main.disk_free_check_ms', t)
                t = time.perf_counter()
                item = camera.get(last_sequence) if config['background'] else camera.read_owned()
                acquire_ms = metrics.elapsed('main.acquire_wait_ms', t)
                skipped += max(0, item['sequence']-last_sequence-1)
                last_sequence = item['sequence']
                frame = item['frame']
                age = max(0., time.monotonic()*1000-item['returned_ms'])
                metrics.add('main.frame_age_before_infer_ms', age)
                number = len(report['frames'])+1
                check = number == 1 or number % config['check_every'] == 0
                raw, cpu, boxes, proof, timing = infer(session, frame, check, metrics)
                t = time.perf_counter()
                painted = paint(frame, boxes, timing, proof)
                draw_ms = metrics.elapsed('main.draw_ms', t)
                t = time.perf_counter()
                row = dict(id='frame_%06d'%number, capture_sequence=item['sequence'],
                    capture_returned_ms=item['returned_ms'], read_api_ms=item['read_api_ms'],
                    acquire_wait_ms=acquire_ms, frame_age_before_infer_ms=age, draw_ms=draw_ms,
                    detections_xyxy_score_class=boxes.tolist(), proof=proof, timing=timing,
                    save_state='NOT_SELECTED')
                report['frames'].append(row)
                metrics.elapsed('main.frame_metadata_ms', t)
                now = time.monotonic()
                mismatch = check and not proof['same_frame_cpu_bit_exact']
                should_save = check or config['save_interval'] == 0 or now-last_saved >= config['save_interval']
                if should_save:
                    t = time.perf_counter()
                    # Snapshot only ordinary owned NumPy arrays. Never queue DMA/CMA buffers.
                    job = dict(id=row['id'], frame=frame, painted=painted,
                        raw=np.array(raw, copy=True), boxes=np.array(boxes, copy=True),
                        cpu=None if cpu is None else np.array(cpu, copy=True), enqueued_at=time.perf_counter())
                    metrics.elapsed('main.evidence_snapshot_ms', t)
                    t = time.perf_counter()
                    if mismatch:
                        # Checked failure evidence must not be dropped with a full queue.
                        RETAINED_FAILURE_EVIDENCE.append(job)
                        report['mismatch_evidence_retained_in_ram'] = True
                        if not writer.stop():
                            raise RuntimeError('Writer still active; raw mismatch kept in memory; stop')
                        writer.raise_if_failed()
                        writer.write(job)
                        RETAINED_FAILURE_EVIDENCE.remove(job)
                        report['mismatch_evidence_retained_in_ram'] = False
                        row['save_state'] = 'SAVED_MISMATCH'
                    elif config['background']:
                        row['save_state'] = 'QUEUED' if writer.enqueue(job) else 'DROPPED_QUEUE_FULL'
                    else:
                        writer.write(job)
                        writer.accepted += 1
                        row['save_state'] = 'SAVED'
                    metrics.elapsed('main.save_dispatch_or_serial_save_ms', t)
                    last_saved = now
                if now-last_report >= config['report_interval'] or mismatch:
                    checkpoint('LIVE_FRAME_%d'%number)
                    last_report = now
                if mismatch:
                    raise RuntimeError('LIVE_FPGA_CPU_BIT_MISMATCH; no fallback; both raw outputs preserved')
                if display_on:
                    handle = show(painted, handle, metrics)
                    row['display_submitted_ms'] = time.monotonic()*1000
                    row['read_return_to_display_submit_ms'] = max(0., row['display_submitted_ms']-item['returned_ms'])
                    metrics.add('main.read_return_to_display_submit_ms', row['read_return_to_display_submit_ms'])
                row['iteration_wall_ms'] = metrics.elapsed('main.iteration_wall_ms', iteration)
            report['capture_loop_seconds'] = time.monotonic()-started
            if not report['frames']:
                raise RuntimeError('No real FPGA camera frames completed')
            report['status'] = 'MEASUREMENT_COMPLETE_NOT_FULL_SYSTEM_ACCEPTANCE'
        except KeyboardInterrupt:
            interrupted = True
            report['status'] = 'INTERRUPTED_PARTIAL_RESULTS'
        except BaseException:
            failed = report['error'] = traceback.format_exc()
            report['status'] = 'FAILED_PARTIAL_RESULTS_RETAINED'
        finally:
            if started is not None and 'capture_loop_seconds' not in report:
                report['capture_loop_seconds'] = time.monotonic()-started
            measuring[0] = False
            # A camera/storage problem must never bypass DMA reset/free/rollback.
            try:
                camera.stop_event.set()
                clean = session.close()
            finally:
                try:
                    capture_stopped = camera.stop()
                except BaseException:
                    report['camera_stop_error'] = traceback.format_exc()
                try:
                    t = time.perf_counter()
                    writer_stopped = writer.stop()
                    metrics.elapsed('cleanup.writer_drain_ms', t)
                except BaseException:
                    report['writer_stop_error'] = traceback.format_exc()
            report.update(safe_cleanup_complete=clean, capture_worker_stopped=capture_stopped,
                          writer_worker_stopped=writer_stopped, camera_properties=camera.info,
                          captured_read_count=camera.count, capture_samples=camera.rows,
                          capture_telemetry_truncated=camera.count > len(camera.rows),
                          skipped_before_inference=skipped,
                          not_selected_after_last_inference=max(0, camera.count-last_sequence),
                          saved_frames=writer.snapshot(), saved_bytes=writer.total_bytes,
                          save_queue_capacity=2, save_queue_high_water=writer.high_water,
                          save_queue_dropped=writer.dropped, writer_error=writer.error)
            by_id = {r['id']:r for r in report['saved_frames']}
            for row in report['frames']:
                if row['save_state'] == 'QUEUED' and row['id'] in by_id:
                    row['save_state'] = by_id[row['id']]['status']
                elif row['save_state'] == 'QUEUED':
                    row['save_state'] = 'NOT_WRITTEN_WORKER_FAILED_OR_PENDING'
            if writer.error or not capture_stopped or not writer_stopped or camera.error:
                report['worker_failure'] = dict(camera_error=camera.error, writer_error=writer.error)
                report['status'] = 'WORKER_FAILURE_OR_TIMEOUT_PARTIAL_RESULTS'
                failed = failed or str(report['worker_failure'])
            checked = [r for r in report['frames'] if r['proof']['cpu_checked']]
            report['live_cpu_checked_count'] = len(checked)
            report['live_cpu_unchecked_count'] = len(report['frames'])-len(checked)
            report['checked_frames_all_bit_exact'] = bool(checked) and all(r['proof']['same_frame_cpu_bit_exact'] for r in checked)
            elapsed = report.get('capture_loop_seconds', 0)
            report['inference_fps'] = len(report['frames'])/elapsed if elapsed else 0.
            submitted = sum('display_submitted_ms' in r for r in report['frames'])
            report['display_submissions_per_second'] = submitted/elapsed if elapsed else 0.
            report['saved_frames_count'] = sum(r['status'] == 'SAVED' for r in report['saved_frames'])
            report['capture_read_api_fps'] = (1000*(camera.count-1)/(camera.rows[-1]['returned_ms']-camera.rows[0]['returned_ms'])
                if camera.count > 1 and len(camera.rows) == camera.count and camera.rows[-1]['returned_ms'] > camera.rows[0]['returned_ms'] else None)
            report['evidence_files_sha256'] = {p.name:sha(p) for p in directory.iterdir()
                if p.is_file() and p.suffix == '.npy' and p.name.startswith('case_')}
            report['timings'] = metrics.summary()
            exclusive = ('disk_free_check_ms', 'acquire_wait_ms', 'preprocess_ms', 'fpga_arm_forward_ms',
                'cpu_reference_ms', 'exact_compare_ms', 'decode_ms', 'dma_status_snapshot_ms', 'draw_ms',
                'frame_metadata_ms', 'evidence_snapshot_ms', 'save_dispatch_or_serial_save_ms',
                'report_json_ms', 'report_write_close_ms', 'display_jpeg_encode_ms', 'display_publish_ms')
            accounted = sum(report['timings'].get('main.'+key, {}).get('total_ms', 0) for key in exclusive)
            # Valid only for completed runs: a failed iteration may lack a wall sample.
            if report['status'] == 'MEASUREMENT_COMPLETE_NOT_FULL_SYSTEM_ACCEPTANCE':
                report['main_loop_accounting'] = dict(loop_wall_ms=elapsed*1000,
                    exclusive_main_stages_ms=accounted, residual_ms=elapsed*1000-accounted,
                    additive_keys=['main.'+key for key in exclusive],
                    writer_and_capture_totals_excluded_because_nested_or_overlapping=True)
            checkpoint('FINISHED')
            print('STATUS:', report['status'], flush=True)
            print('MODE:', mode, '| inferred FPS:', round(report['inference_fps'], 3),
                  '| saved:', report['saved_frames_count'], '| save drops:', writer.dropped, flush=True)
            print('CPU checked:', len(checked), '| NOT checked:', report['live_cpu_unchecked_count'], flush=True)
            print('DMA_QUIESCED:', report['dma_quiesced'], 'OLD_HARDWARE_RESTORED:', report['old_hardware_restored'], flush=True)
            print('RESULT_DIR:', directory, flush=True)
        if not clean or failed or not capture_stopped or not writer_stopped:
            raise RuntimeError('Stopped; preserve '+str(directory/'RESULT.json')+'\n'+str(failed or report['status']))
        if interrupted:
            print('Interrupted safely; partial measurement only. Do not call it PASS.')
        return directory


def summarize(sessions):
    """Readable comparison; no hardware, file mutation, or causal claims."""
    rows = []
    for session in sessions:
        path = Path(session).resolve()
        if path.parent != (ROOT/'results').resolve():
            raise ValueError('Choose direct-child result directories')
        report = json.loads((path/'RESULT.json').read_text(encoding='utf-8'))
        mean = lambda key:round(report['timings'].get(key, {}).get('mean_ms', 0), 2)
        row = dict(mode=report['mode'], status=report['status'], inferred_fps=round(report['inference_fps'], 3),
            captured_reads=report['captured_read_count'], saved=report['saved_frames_count'],
            dropped_saves=report['save_queue_dropped'], checked=report['live_cpu_checked_count'],
            unchecked=report['live_cpu_unchecked_count'],
            read_api_ms=mean('capture.read_api_ms'), forward_ms=mean('main.fpga_arm_forward_ms'),
            extra_cpu_ms_per_checked_frame=mean('main.cpu_reference_ms'),
            png_ms=mean('writer.png_encode_ms'), jpeg_save_ms=mean('writer.jpeg_encode_ms'),
            write_close_ms=mean('writer.file_write_close_ms'), hash_ms=mean('writer.hash_readback_ms'),
            preview_jpeg_ms=mean('main.display_jpeg_encode_ms'), publish_ms=mean('main.display_publish_ms'),
            report_json_ms=mean('main.report_json_ms'), report_write_ms=mean('main.report_write_close_ms'))
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False, indent=2))
    print('Different counts/threads: means are per operation, not additive async latency. NOT browser render/physical SD latency.')
    return rows


def export(sessions):
    if any(w.thread.is_alive() for w in RETAINED_WORKERS):
        raise RuntimeError('A worker still owns result files/camera; do not export or start another run')
    base = (ROOT/'results').resolve()
    paths, seen, total = [], set(), 0
    for session in sessions:
        directory = Path(session).resolve()
        if directory.parent != base or directory in seen:
            raise ValueError('Choose unique direct-child result directories')
        seen.add(directory)
        report = json.loads((directory/'RESULT.json').read_text(encoding='utf-8'))
        if report.get('writer_worker_stopped') is not True or report.get('capture_worker_stopped') is not True:
            raise RuntimeError('Worker stop not confirmed; preserve directory and investigate')
        expected = dict(report['evidence_files_sha256'])
        for saved in report['saved_frames']:
            expected.update(saved['files'])
        for name, digest in expected.items():
            path = (directory/name).resolve()
            if path.parent != directory or not path.is_file() or sha(path) != digest:
                raise RuntimeError('Evidence path/hash mismatch: '+name)
        # Keep partial failure evidence too; never include executable .so output.
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix in ('.npy', '.png', '.jpg', '.json', '.log'):
                paths.append(path)
                total += path.stat().st_size
    if not paths or total > 384*1024*1024:
        raise ValueError('Choose 1-3 short results totaling <=384MiB')
    if shutil.disk_usage(ROOT).free < total+64*1024*1024:
        raise RuntimeError('Insufficient free space for export')
    output = ROOT/('取帧存储分项对比结果_发给我_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.zip')
    manifest = {path.relative_to(base).as_posix():sha(path) for path in paths}
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(base).as_posix())
        archive.writestr('RESULT_FILES_SHA256.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Export ZIP CRC failed')
    print('DOWNLOAD:', output)
    return output
