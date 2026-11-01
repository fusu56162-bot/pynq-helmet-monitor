"""Output JPEG A/B on the verified 178-DSP, single-view camera path.

The model, FPGA bitstream, infer/paint/publish functions and raw evidence policy
are imported from the protected final224_speed_v1 package without editing it.
Only the post-detection JPEG encoder and report metadata are replaced in memory.
"""
import contextlib
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
BOARD_BASE = Path('/home/xilinx/jupyter_notebooks/traffic_project/final224_speed_v1')
_MODULE = None
_SESSION_LOCK = threading.Lock()
NEW_MODEL = {
    'best.ncnn.param': '3f4cb05109cc65a1563d557ca44b8a6542282acf7bc73c7f9fd570ac8a271b1d',
    'best.ncnn.bin': 'c07c5773535189d23bc0c9c94fc3377bc2e7713982735c7dced85ff8f49daa9f',
}
NEW_BIT = '77987ca9b7dd4e926df7c720745a242942f9542f729fa081e2ef36074a182f78'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def checked_options(jpeg_quality, output_width):
    if type(jpeg_quality) is not int or not 1 <= jpeg_quality <= 95:
        raise ValueError('jpeg_quality must be an integer from 1 to 95; start with 80 and 60')
    if type(output_width) is not int or output_width not in (640, 480):
        raise ValueError('output_width must be 640 or 480; only the outgoing annotated image is resized')
    return dict(jpeg_quality=jpeg_quality, output_width=output_width,
                output_height=output_width * 3 // 4)


def verify():
    """File-only check. Never import PYNQ, load a bitstream or open a camera."""
    manifest = json.loads((ROOT / 'FILES_SHA256.json').read_text(encoding='utf-8'))
    for name, digest in manifest.items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT)
        if sha(path) != digest:
            raise RuntimeError('JPEG comparison package changed: ' + name)
    pins = json.loads((ROOT / 'BASELINE_PIN.json').read_text(encoding='utf-8'))
    if sha(BOARD_BASE / 'FILES_SHA256.json') != pins['manifest_sha256']:
        raise RuntimeError('Use the verified final224_speed_v1 baseline; its manifest differs')
    old_manifest = json.loads((BOARD_BASE / 'FILES_SHA256.json').read_text(encoding='utf-8'))
    for name, digest in old_manifest.items():
        path = (BOARD_BASE / name).resolve()
        path.relative_to(BOARD_BASE)
        if sha(path) != digest:
            raise RuntimeError('Protected baseline file changed: ' + name)
    spec = json.loads((BOARD_BASE / 'profiles/new/SPEC.json').read_text(encoding='utf-8'))
    if spec['model_sha256'] != NEW_MODEL or spec['input_side'] != 224 or spec['threads'] != 2:
        raise RuntimeError('The latest trained 224 model identity or execution settings differ')
    if sha(BOARD_BASE / 'profiles/new/overlay/rider_monitor_chain_float.bit') != NEW_BIT:
        raise RuntimeError('New-model matched 178-DSP bitstream differs')
    print('JPEG_QUALITY_PACKAGE_AND_BASELINE_HASH_PASS; model input 224; devices untouched', flush=True)
    return dict(addon_files=len(manifest), baseline_files=len(old_manifest),
                baseline_manifest_sha256=pins['manifest_sha256'], model_sha256=NEW_MODEL,
                runtime_overlay_sha256=NEW_BIT)


def baseline():
    global _MODULE
    if _MODULE is None:
        sys.path.insert(0, str(BOARD_BASE))
        spec = importlib.util.spec_from_file_location('_camera_quality_baseline', BOARD_BASE / 'compare.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.verify()  # Also rejects stale modules from other notebooks/packages.
        _MODULE = module
    return _MODULE


class PreviewEncoder:
    """Receives the full-resolution painted frame AFTER inference only."""
    def __init__(self, jpeg_quality, output_width):
        self.options = checked_options(jpeg_quality, output_width)
        self.rows = []

    def __call__(self, frame, metrics):
        import cv2
        import numpy as np
        if frame.shape != (480, 640, 3) or frame.dtype != np.uint8:
            raise ValueError('Expected the full-size annotated BGR frame after inference')
        width = self.options['output_width']
        resize_ms = 0.0
        image = frame
        if width != 640:
            started = time.perf_counter()
            image = cv2.resize(frame, (width, self.options['output_height']), interpolation=cv2.INTER_AREA)
            resize_ms = metrics.elapsed('main.preview_resize_ms', started)
        started = time.perf_counter()
        ok, encoded = cv2.imencode('.jpg', image,
                                  [int(cv2.IMWRITE_JPEG_QUALITY), self.options['jpeg_quality']])
        if not ok:
            raise RuntimeError('Outgoing preview JPEG encoding failed')
        payload = encoded.tobytes()
        elapsed = metrics.elapsed('main.jpeg_encode_once_ms', started)
        self.rows.append(dict(jpeg_bytes=len(payload), encode_ms=elapsed, resize_ms=resize_ms))
        return payload

    def annotate_report(self, report):
        n = len(self.rows)
        total = sum(row['jpeg_bytes'] for row in self.rows)
        seconds = report.get('loop_seconds')
        report['outgoing_preview'] = dict(
            **self.options, encoded_frames=n, jpeg_bytes_total=total,
            jpeg_bytes_mean=total / n if n else None,
            jpeg_bytes_min=min((r['jpeg_bytes'] for r in self.rows), default=None),
            jpeg_bytes_max=max((r['jpeg_bytes'] for r in self.rows), default=None),
            estimated_base64_bytes_total=sum(4 * ((r['jpeg_bytes'] + 2) // 3) for r in self.rows),
            jpeg_payload_bytes_per_loop_second=total / seconds if seconds else None,
            source_camera='MJPG 640x480 requested 15 FPS, unchanged',
            encoder_location='PS ARM; after inference and drawing; before Jupyter publication',
            same_encoded_bytes_reused_for_saved_view=True,
            raw_camera_and_bgr_and_224_tensor_and_detection_coordinates_unchanged=True,
            network_round_trip_measured=False, browser_receive_or_render_time_measured=False,
            publication_timing='main.display_publish_ms is kernel submission, not network transit',
            base64_estimate_excludes_protocol_headers=True)
        for row, encoded in zip(report.get('frames', []), self.rows):
            row['outgoing_jpeg_bytes'] = encoded['jpeg_bytes']


@contextlib.contextmanager
def override_preview(module, encoder, provenance):
    camera = module.camera
    original_encoder = camera.encode_jpeg
    original_report = camera.write_report
    original_lock = camera.hardware_lock

    def report_writer(directory, report, metrics, scope='main'):
        encoder.annotate_report(report)
        report['jpeg_quality_addon'] = provenance
        return original_report(directory, report, metrics, scope)

    @contextlib.contextmanager
    def hardware_lock():
        import fcntl
        # The baseline's profile-local lock is retained, plus the project lock
        # used by the standalone convolution tests. Never delete an owned lock.
        path = BOARD_BASE.parent / '.conv_board_exclusive.lock'
        with path.open('a') as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('Another camera/FPGA test still owns the project lock; stop it first') from exc
            with original_lock():
                yield

    camera.encode_jpeg = encoder
    camera.write_report = report_writer
    camera.hardware_lock = hardware_lock
    try:
        yield
    finally:
        camera.encode_jpeg = original_encoder
        camera.write_report = original_report
        camera.hardware_lock = original_lock


def run(jpeg_quality=60, output_width=640, seconds=20, scene='bare_head_static', notes='',
        camera_index=0, programs_stopped=False, backup_on_pc_confirmed=False):
    options = checked_options(jpeg_quality, output_width)
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise ValueError('seconds must be greater than 0 and at most 60')
    if programs_stopped is not True or backup_on_pc_confirmed is not True:
        raise ValueError('Stop other camera/FPGA kernels and confirm the existing complete PC backup')
    if not _SESSION_LOCK.acquire(blocking=False):
        raise RuntimeError('A JPEG comparison is already running in this kernel')
    try:
        provenance = verify()
        module = baseline()
        encoder = PreviewEncoder(jpeg_quality, output_width)
        print('SINGLE ANNOTATED VIEW | latest model | 178-DSP + ARM | JPEG', options, flush=True)
        with override_preview(module, encoder, provenance):
            directory = Path(module.run_camera(name='new', seconds=seconds, scene=scene,
                notes=notes, camera_index=camera_index, programs_stopped=programs_stopped,
                backup_on_pc_confirmed=backup_on_pc_confirmed))
        report = json.loads((directory / 'RESULT.json').read_text(encoding='utf-8'))
        if report['status'] == 'FPGA_MEASUREMENT_COMPLETE_NOT_FULL_SYSTEM_ACCEPTANCE':
            if len(encoder.rows) != len(report['frames']):
                raise RuntimeError('JPEG/frame counts differ; preserve result, do not claim an A/B pass')
        print('QUALITY_RESULT_DIR:', directory, flush=True)
        return directory
    finally:
        _SESSION_LOCK.release()


def summarize(sessions):
    rows = []
    for directory in sessions:
        path = Path(directory).resolve()
        path.relative_to((BOARD_BASE / 'profiles/new/results').resolve())
        report = json.loads((path / 'RESULT.json').read_text(encoding='utf-8'))
        preview = report['outgoing_preview']
        metrics = report.get('metrics', {})
        mean = lambda name: metrics.get(name, {}).get('mean_ms')
        row = dict(quality=preview['jpeg_quality'], width=preview['output_width'],
            jpeg_bytes_mean=preview['jpeg_bytes_mean'], inference_fps=report.get('inference_fps'),
            jpeg_encode_ms=mean('main.jpeg_encode_once_ms'),
            publish_submit_ms=mean('main.display_publish_ms'),
            fpga_arm_forward_ms=mean('main.fpga_arm_forward_ms'),
            decode_ms=mean('main.camera_decode_ms'),
            status=report['status'], checked=report.get('checked_count'),
            checked_exact=report.get('checked_frames_all_bit_exact'),
            camera_stopped=report.get('capture_worker_stopped'),
            writer_stopped=report.get('writer_worker_stopped'), dma_quiesced=report.get('dma_quiesced'))
        rows.append(row)
    try:
        import pandas as pd
        from IPython.display import display
        display(pd.DataFrame(rows))
    except ImportError:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    print('Board inference FPS and kernel publication are measured; browser/network delivery is not.')
    return rows


def export(sessions):
    if not sessions:
        raise ValueError('Run at least one camera test before export')
    verify()
    return baseline().export_paths(sessions, label='单画面178DSP_JPEG画质对比结果')


if __name__ == '__main__':
    verify()
