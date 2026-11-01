import ctypes as ct
import hashlib
import json
from pathlib import Path
import sys
import threading
import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))
from reference.board_model_runtime import decode

INFO = 'small-v1;ncnn=1.0.20260526;armv7-neon;fp32-or-int8;abi=1'
THRESHOLDS = [.35, .25, .5, .2]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_package():
    m = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    for name, digest in m['sha256'].items():
        p = (HERE / name).resolve()
        p.relative_to(HERE)
        if sha(p) != digest:
            raise RuntimeError('Small candidate hash mismatch: ' + name)
    return m


def decode_small(raw, side, confidence=THRESHOLDS):
    rows = sum(3*(side//s)**2 for s in (8, 16, 32))
    if raw.shape != (1, rows, 9) or raw.dtype != np.float32:
        raise ValueError('Unexpected raw output')
    a = np.zeros((1, 6300, 9), np.float32)
    a[:, :rows] = raw
    a[:, :rows, :4] *= np.float32(320/side)
    return decode(a, confidence)


class Runtime:
    def __init__(self, model, side, int8, param=None, binary=None):
        self.side, self.handle, self.lock = side, None, threading.Lock()
        self.rows = sum(3*(side//s)**2 for s in (8, 16, 32))
        self.lib = ct.CDLL(str(HERE / 'build/libsmall.so'))
        self.lib.small_build_info.restype = ct.c_char_p
        if self.lib.small_build_info().decode() != INFO:
            raise RuntimeError('Wrong dynamic-size bridge ABI')
        self.lib.small_create.argtypes = [ct.c_char_p, ct.c_char_p, ct.c_int, ct.c_int, ct.c_char_p, ct.c_int]
        self.lib.small_create.restype = ct.c_void_p
        self.lib.small_forward.argtypes = [ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.c_void_p, ct.c_size_t, ct.c_char_p, ct.c_int]
        self.lib.small_forward.restype = ct.c_int
        self.lib.small_destroy.argtypes = [ct.c_void_p]
        self.lib.small_destroy.restype = None
        err = ct.create_string_buffer(1024)
        param = model / 'best.ncnn.param' if param is None else param
        binary = model / 'best.ncnn.bin' if binary is None else binary
        self.handle = self.lib.small_create(str(param).encode(), str(binary).encode(), side, int(int8), err, len(err))
        if not self.handle:
            raise RuntimeError(err.value.decode(errors='replace'))

    def forward(self, x):
        if (not isinstance(x, np.ndarray) or x.shape != (1, 3, self.side, self.side) or
                x.dtype != np.float32 or not x.flags.c_contiguous or not np.isfinite(x).all() or x.min() < 0 or x.max() > 1):
            raise ValueError('Wrong tensor dtype, size, layout or range')
        with self.lock:
            if not self.handle:
                raise RuntimeError('Runtime closed')
            out = np.empty((1, self.rows, 9), np.float32)
            err = ct.create_string_buffer(1024)
            if self.lib.small_forward(self.handle, x.ctypes.data, x.size, out.ctypes.data, out.size, err, len(err)):
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
