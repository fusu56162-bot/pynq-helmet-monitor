"""Explicit USB-camera preview/capture only. No model, PYNQ, DMA, GPIO or web server.

Import has no device/file-writing side effects. Read-return timestamps are PS
monotonic times, NOT camera exposure timestamps or measured sensor latency.
"""
import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
import traceback
import uuid
import zipfile

ROOT=Path(__file__).resolve().parent
SCENES=('empty_scene','helmet_static','bare_head_static','walk_push_helmet','walk_push_bare_head',
        'handheld_helmet_static','occluded_head_static')


def _cv():
    import cv2
    return cv2


def show_devices():
    import platform
    cv2=_cv()
    print('Python camera preview; OpenCV:',cv2.__version__,'system:',platform.system())
    print('Video nodes:',[str(p) for p in sorted(Path('/dev').glob('video*'))])
    print('Use the USB camera connected to PYNQ, not the laptop camera. No model/FPGA is used.')


def _duration(value,limit):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<value<=limit:
        raise ValueError('Duration/rate must be finite, positive and at most '+str(limit))


class _Camera:
    def __init__(self,index):
        if type(index)!=int or not 0<=index<=15: raise ValueError('camera_index must be 0..15')
        self.index=index;self.cap=None;self.lock=None

    def __enter__(self):
        cv2=_cv()
        try:
            import fcntl
            self.lock=(ROOT/'.camera_collection.lock').open('a')
            fcntl.flock(self.lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.cap=cv2.VideoCapture(self.index)
            if not self.cap.isOpened(): raise RuntimeError('Camera failed to open. Check USB/index and stop other camera programs.')
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
            self.cap.set(cv2.CAP_PROP_FPS,15)
            if hasattr(cv2,'CAP_PROP_BUFFERSIZE'): self.cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
            return self
        except BaseException:
            self.__exit__(None,None,None);raise

    def __exit__(self,*args):
        try:
            if self.cap is not None: self.cap.release()
        finally:
            if self.lock is not None: self.lock.close();self.lock=None

    def read(self):
        ok,frame=self.cap.read()
        captured=time.monotonic()*1000
        if not ok or frame is None: raise RuntimeError('Camera read failed. No new frame was saved.')
        import numpy as np
        if frame.dtype!=np.uint8 or frame.shape!=(480,640,3):
            raise RuntimeError('Expected actual BGR uint8 480x640x3, got '+str(frame.shape)+'. Not silently resizing.')
        return frame,captured


def _display_frame(frame,handle):
    from IPython.display import Image,display
    cv2=_cv()
    ok,data=cv2.imencode('.jpg',frame,[int(cv2.IMWRITE_JPEG_QUALITY),80])
    if not ok: raise RuntimeError('Preview JPEG encoding failed')
    image=Image(data=data.tobytes())
    if handle is None: return display(image,display_id=True)
    handle.update(image);return handle


def preview(camera_index=0,seconds=8):
    """Show a bounded raw camera preview in a Jupyter Notebook; save no frames."""
    _duration(seconds,30)
    handle=None;shown=0
    print('RAW CAMERA PREVIEW ONLY: no detection boxes, no FPGA. Automatically stops in',seconds,'seconds.')
    try:
        with _Camera(camera_index) as camera:
            started=time.monotonic();next_preview=started
            while time.monotonic()-started<seconds:
                frame,_=camera.read()
                now=time.monotonic()
                if now>=next_preview:
                    handle=_display_frame(frame,handle);shown+=1;next_preview=now+.2
    except KeyboardInterrupt:
        print('Preview interrupted; camera released.')
    print('PREVIEW_FINISHED; updates:',shown,'camera released. No samples saved.')


def collect(scene,camera_index=0,seconds=10,save_fps=5,notes='',countdown=5,show_preview=True):
    """Save lossless original-size PNGs and explicit metadata in a NEW session.

    Run this cell once when participants are ready; countdown then bounded
    capture. Interrupt retains a partial report and already saved frames.
    """
    if scene not in SCENES: raise ValueError('Choose scene from '+str(SCENES))
    _duration(seconds,60);_duration(save_fps,10)
    if type(countdown)!=int or not 0<=countdown<=10: raise ValueError('countdown must be 0..10')
    if not isinstance(notes,str) or len(notes)>2000: raise ValueError('notes must be <=2000 characters')
    if seconds*save_fps>600: raise ValueError('At most 600 requested saved frames per clip')
    if shutil.disk_usage(ROOT).free<256*1024*1024: raise RuntimeError('Less than 256MiB free. Stop and preserve existing files.')
    cv2=_cv()
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    directory=ROOT/'captures'/(scene+'_'+stamp)
    directory.mkdir(parents=True,exist_ok=False)
    report=dict(schema_version=1,status='STARTED_NOT_COMPLETE',session_id=directory.name,scene_declared_by_operator=scene,
        notes=notes,source='live',inference_performed=False,fpga_accessed=False,light_state=None,light_valid=False,
        camera_index=camera_index,shape=[480,640,3],dtype='uint8',layout='BGR',file_format='lossless PNG',
        requested_seconds=seconds,requested_save_fps=save_fps,frames=[],saved_bytes=0,
        capture_time_basis='PS monotonic immediately after cap.read returns; NOT sensor exposure time; no latency claim',
        scene_is_not_ground_truth_annotation=True,wall_time_may_be_wrong_on_board=True,
        no_red_light_or_helmet_event_validation=True)
    def save_report():
        (directory/'CAPTURE.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    save_report();handle=None
    try:
        with _Camera(camera_index) as camera:
            print('RAW CAPTURE ONLY. Prepare the scene; do not ride without a helmet.')
            for remaining in range(countdown,0,-1): print('START IN',remaining,flush=True);time.sleep(1)
            started=time.monotonic();next_save=started;frame_id=0
            with (directory/'frames.jsonl').open('x',encoding='utf-8') as log:
                while time.monotonic()-started<seconds:
                    frame,captured=camera.read();frame_id+=1;now=time.monotonic()
                    if now<next_save: continue
                    if len(report['frames'])>=600: raise RuntimeError('Frame count limit reached')
                    ok,data=cv2.imencode('.png',frame,[int(cv2.IMWRITE_PNG_COMPRESSION),3])
                    if not ok: raise RuntimeError('Lossless sample encoding failed')
                    payload=data.tobytes()
                    if report['saved_bytes']+len(payload)>128*1024*1024: raise RuntimeError('128MiB per-clip size limit reached; already saved data retained')
                    if shutil.disk_usage(directory).free<128*1024*1024: raise RuntimeError('Free space low; preserving existing frames')
                    filename='frame_%06d.png'%frame_id
                    with (directory/filename).open('xb') as stream: stream.write(payload)
                    item=dict(frame_id=frame_id,saved_index=len(report['frames'])+1,capture_monotonic_ms=captured,
                        elapsed_ms=captured-started*1000,image=filename,sha256=hashlib.sha256(payload).hexdigest(),
                        bgr_payload_sha256=hashlib.sha256(frame.tobytes()).hexdigest(),source='live')
                    report['frames'].append(item);report['saved_bytes']+=len(payload)
                    log.write(json.dumps(item)+'\n');log.flush();save_report()
                    if show_preview: handle=_display_frame(frame,handle)
                    next_save=now+1/save_fps  # Do not manufacture duplicate frames to meet a requested rate.
            report['elapsed_seconds']=time.monotonic()-started
            if not report['frames']: raise RuntimeError('No sample frames saved')
            report['status']='CAPTURE_COMPLETE_RAW_ONLY_NOT_DETECTION_TEST'
    except KeyboardInterrupt:
        report['status']='INTERRUPTED_PARTIAL_CAPTURE';print('Interrupted: retained already saved frames.')
    except BaseException:
        report['status']='CAPTURE_FAILED_PARTIAL_DATA_RETAINED';report['error']=traceback.format_exc()
        raise
    finally:
        save_report()
        print('CAPTURE_STATUS:',report['status'])
        print('SAVED_FRAMES:',len(report['frames']))
        print('SESSION_DIR:',directory)
        print('Camera released. Samples contain no model predictions or true traffic-light record.')
    return directory


def export_sessions(sessions=None):
    """Read-only integrity verification + bounded export. Does not start a camera."""
    base=(ROOT/'captures').resolve()
    sessions=list(base.iterdir()) if sessions is None and base.is_dir() else list(sessions or [])
    if not sessions: raise ValueError('No capture sessions to export')
    paths=[];total=0
    for session in sessions:
        directory=Path(session).resolve();directory.relative_to(base)
        if directory.parent!=base: raise ValueError('Expected a direct child capture session')
        report=json.loads((directory/'CAPTURE.json').read_text(encoding='utf-8'))
        names={'CAPTURE.json','frames.jsonl'}
        for frame in report['frames']:
            image=(directory/frame['image']).resolve();image.relative_to(directory)
            if image.parent!=directory or hashlib.sha256(image.read_bytes()).hexdigest()!=frame['sha256']:
                raise ValueError('Saved sample integrity failed: '+frame['image'])
            names.add(frame['image'])
        for name in sorted(names):
            path=directory/name
            if path.is_file(): total+=path.stat().st_size;paths.append(path)
    if total>256*1024*1024: raise ValueError('Export exceeds 256MiB. Choose only the first 1-3 short sessions, or export separately.')
    if shutil.disk_usage(ROOT).free<total+64*1024*1024: raise RuntimeError('Not enough space to safely create export')
    output=ROOT/('摄像头真实样本_发给我_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.zip')
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_STORED) as z:
        for path in paths: z.write(path,path.relative_to(base).as_posix())
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None: raise RuntimeError('Export CRC failed')
    print('DOWNLOAD_RESULT:',output)
    print('EXPORT_BYTES:',output.stat().st_size)
    print('Raw camera samples only. Send to A/chat for inspection, then B for visual quality; NOT C event validation yet.')
    return output
