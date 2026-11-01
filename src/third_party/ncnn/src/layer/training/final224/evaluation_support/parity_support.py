"""CPU-only measurement support; no PYNQ, MMIO, or hardware access."""
import ctypes as ct
import hashlib
from pathlib import Path
import statistics
import threading
import numpy as np
from board_model_runtime import decode, compare_detections

INFO = 'small-v1;ncnn=1.0.20260526;armv7-neon;fp32-or-int8;abi=1'
PROFILE_INFO = 'whole-profile-v1;ncnn=1.0.20260526;224;recover5;diagnostic-only'
THRESHOLDS = [.35, .25, .5, .2]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def stats(values):
    if not values:
        raise ValueError('Empty timing samples')
    return {'mean_ms': statistics.mean(values), 'median_ms': statistics.median(values),
            'min_ms': min(values), 'max_ms': max(values),
            'p95_ms': float(np.percentile(values, 95)), 'samples_ms': values}


def preprocess224(frame):
    # Frozen fifth/sixth-round preprocessing, NOT a new resize/accuracy scheme.
    import cv2
    if frame.shape != (480,640,3) or frame.dtype != np.uint8:
        raise ValueError('Expected already decoded BGR640x480 frame')
    canvas = np.full((224,224,3), 114, np.uint8)
    canvas[28:196] = cv2.resize(frame, (224,168), interpolation=cv2.INTER_NEAREST)[...,::-1]
    return np.ascontiguousarray(canvas.transpose(2,0,1)[None], dtype=np.float32) / np.float32(255)


def decode224(raw):
    if raw.shape != (1,3087,9) or raw.dtype != np.float32:
        raise ValueError('Wrong 224 output')
    padded = np.zeros((1,6300,9), np.float32)
    padded[:,:3087] = raw
    padded[:,:3087,:4] *= np.float32(320/224)
    return decode(padded, THRESHOLDS)


def parity(actual, reference):
    if actual.shape != (1,3087,9) or reference.shape != actual.shape:
        raise ValueError('Output shape changed')
    coordinates = bool(np.allclose(actual[...,:4], reference[...,:4], atol=.02, rtol=1e-4))
    scores = bool(np.allclose(actual[...,4:], reference[...,4:], atol=2e-5, rtol=2e-4))
    detections = bool(compare_detections(decode224(actual), decode224(reference)))
    return {'passed': coordinates and scores and detections,
            'coordinates_passed': coordinates, 'scores_passed': scores, 'detections_passed': detections,
            'byte_exact': bool(np.array_equal(actual, reference)),
            'max_coordinate_error': float(np.max(np.abs(actual[...,:4]-reference[...,:4]))),
            'max_score_error': float(np.max(np.abs(actual[...,4:]-reference[...,4:])))}


class Runtime:
    """Same Python validation/allocation/copy contract as small_v1.common.Runtime."""
    def __init__(self, library, model, instrumented=False):
        self.lock, self.handle = threading.Lock(), None
        self.lib = ct.CDLL(str(library))
        self.lib.small_build_info.restype = ct.c_char_p
        if self.lib.small_build_info().decode() != INFO:
            raise RuntimeError('Unexpected dynamic-size bridge ABI')
        if instrumented:
            self.lib.whole_profile_version.restype = ct.c_char_p
            if self.lib.whole_profile_version().decode() != PROFILE_INFO:
                raise RuntimeError('Profiler ABI mismatch')
        self.lib.small_create.argtypes = [ct.c_char_p,ct.c_char_p,ct.c_int,ct.c_int,ct.c_char_p,ct.c_int]
        self.lib.small_create.restype = ct.c_void_p
        self.lib.small_forward.argtypes = [ct.c_void_p,ct.c_void_p,ct.c_size_t,ct.c_void_p,ct.c_size_t,ct.c_char_p,ct.c_int]
        self.lib.small_forward.restype = ct.c_int
        self.lib.small_destroy.argtypes = [ct.c_void_p]
        self.lib.small_destroy.restype = None
        err = ct.create_string_buffer(1024)
        self.handle = self.lib.small_create(str(model/'best.ncnn.param').encode(),
                                           str(model/'best.ncnn.bin').encode(),224,1,err,len(err))
        if not self.handle:
            raise RuntimeError(err.value.decode(errors='replace'))

    def forward(self, x):
        if (not isinstance(x,np.ndarray) or x.shape != (1,3,224,224) or x.dtype != np.float32 or
                not x.flags.c_contiguous or not np.isfinite(x).all() or x.min() < 0 or x.max() > 1):
            raise ValueError('Invalid input tensor')
        with self.lock:
            if not self.handle:
                raise RuntimeError('Runtime closed')
            out = np.empty((1,3087,9), np.float32)
            err = ct.create_string_buffer(1024)
            if self.lib.small_forward(self.handle,x.ctypes.data,x.size,out.ctypes.data,out.size,err,len(err)):
                raise RuntimeError(err.value.decode(errors='replace'))
            if not np.isfinite(out).all():
                raise ValueError('Nonfinite output')
            return out

    def __enter__(self):
        return self

    def __exit__(self, *args):
        with self.lock:
            if self.handle:
                self.lib.small_destroy(self.handle)
                self.handle = None
