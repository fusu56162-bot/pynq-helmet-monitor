"""ctypes cut-point adapter; no hardware access on import or construction."""
import ctypes as ct
import numpy as np


def pointer(x): return ct.c_void_p(x.ctypes.data)


def validate_input(x):
    if (not isinstance(x,np.ndarray) or x.dtype!=np.float32 or x.shape!=(1,3,224,224) or
            not x.flags.c_contiguous or not np.isfinite(x).all() or x.min()<0 or x.max()>1):
        raise ValueError('Expected original normalized contiguous float32 [1,3,224,224]')


class Native:
    def __init__(self, library, model):
        self.lib=ct.CDLL(str(library)); self.handle=None
        self.lib.whole_chain_info.restype=ct.c_char_p
        if self.lib.whole_chain_info()!=b'whole-chain-v1;ncnn=1.0.20260526;224;recover5;owned-packed4':
            raise RuntimeError('Unexpected cut-point bridge ABI')
        self.lib.whole_create.argtypes=[ct.c_char_p,ct.c_char_p,ct.c_char_p,ct.c_int]
        self.lib.whole_create.restype=ct.c_void_p
        self.lib.whole_destroy.argtypes=[ct.c_void_p]; self.lib.whole_destroy.restype=None
        for name in ('whole_full','whole_boundary','whole_resume_hwc'):
            fn=getattr(self.lib,name)
            fn.argtypes=[ct.c_void_p,ct.c_void_p,ct.c_size_t,ct.c_void_p,ct.c_size_t,ct.c_char_p,ct.c_int]
            fn.restype=ct.c_int
        self.lib.chain_boundary_pack_input.argtypes=[ct.c_void_p,ct.c_size_t,ct.c_void_p,ct.c_size_t,ct.c_int,ct.c_int]
        self.lib.chain_boundary_pack_input.restype=ct.c_int
        err=ct.create_string_buffer(1024)
        self.handle=self.lib.whole_create(str(model/'best.ncnn.param').encode(),str(model/'best.ncnn.bin').encode(),err,len(err))
        if not self.handle: raise RuntimeError(err.value.decode(errors='replace'))

    def call(self, name, x, out):
        if not self.handle: raise RuntimeError('Bridge closed')
        err=ct.create_string_buffer(1024)
        if getattr(self.lib,name)(self.handle,pointer(x),x.size,pointer(out),out.size,err,len(err)):
            raise RuntimeError(err.value.decode(errors='replace'))
        return out

    def full(self,x):
        validate_input(x)
        return self.call('whole_full',x,np.empty((1,3087,9),np.float32))

    def boundary(self,x):
        validate_input(x)
        return self.call('whole_boundary',x,np.empty(32*56*56,np.uint32))

    def pack_input(self,x,tx):
        # Validation and exact byte-level inversion are timed for EVERY frame.
        validate_input(x)
        if tx.dtype!=np.uint32 or tx.size*4!=x.size or not tx.flags.c_contiguous:
            raise ValueError('TX contract failed')
        code=self.lib.chain_boundary_pack_input(pointer(x),x.size,pointer(tx),tx.nbytes,112,112)
        if code: raise RuntimeError('Exact normalized float-to-byte packing rejected input, status=%d; DMA NOT started'%code)

    def resume(self,hwc):
        if hwc.dtype!=np.uint32 or hwc.size!=32*56*56 or not hwc.flags.c_contiguous:
            raise ValueError('RX HWC contract failed')
        return self.call('whole_resume_hwc',hwc,np.empty((1,3087,9),np.float32))

    def close(self):
        if self.handle: self.lib.whole_destroy(self.handle); self.handle=None
