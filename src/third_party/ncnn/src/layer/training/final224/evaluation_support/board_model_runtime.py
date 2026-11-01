"""Portable single-frame model acceptance helper (NumPy + OpenCV only).

Shared by model acceptance and production inference; no camera/DMA dependencies.
The model returns decoded cx,cy,w,h,objectness,p0,p1,p2,p3; no second sigmoid.
"""
import hashlib
from pathlib import Path
import numpy as np

NAMES = ['ebike', 'rider', 'helmet_head', 'bare_head']


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_image(path):
    """Decode via Python file I/O so Windows Unicode paths work too."""
    import cv2
    frame=cv2.imdecode(np.frombuffer(Path(path).read_bytes(),dtype=np.uint8),cv2.IMREAD_COLOR)
    if frame is None:raise ValueError('Cannot decode image: '+str(path))
    return frame


def write_image(path, frame):
    import cv2
    path=Path(path)
    ok,encoded=cv2.imencode(path.suffix,frame)
    if not ok:raise IOError('Cannot encode image: '+str(path))
    path.write_bytes(encoded.tobytes())
    return True


def load_onnx_net(path):
    import cv2
    # OpenCV's filename overload is not Unicode-safe on some Windows builds.
    return cv2.dnn.readNetFromONNX(np.frombuffer(Path(path).read_bytes(),dtype=np.uint8))


def validate_tensor(tensor):
    """Check A's tensor without converting, copying or repairing its contents.

    Numeric checks cannot identify a mislabeled BGR tensor or double division by
    255 when values remain in [0,1]; A must also follow the preprocessing contract.
    """
    if not isinstance(tensor, np.ndarray) or tensor.dtype != np.float32:
        raise ValueError('Input must be a numpy float32 array')
    if tensor.shape != (1, 3, 320, 320) or not tensor.flags.c_contiguous:
        raise ValueError('Input must have shape [1,3,320,320] and be C-contiguous')
    if not np.isfinite(tensor).all() or tensor.min() < 0 or tensor.max() > 1:
        raise ValueError('Input must be finite and already normalized to [0,1]')
    return tensor


def preprocess_bgr(frame):
    if not isinstance(frame, np.ndarray) or frame.shape != (480,640,3) or frame.dtype != np.uint8:
        raise ValueError('Frame must be BGR uint8 [480,640,3]')
    # Exact even-row/even-column sampling, including pixel origin (0,0).
    canvas = np.full((320,320,3),114,dtype=np.uint8)
    canvas[40:280] = frame[::2,::2,::-1]
    return np.ascontiguousarray(canvas.transpose(2,0,1)[None],dtype=np.float32) / np.float32(255)


def iou(box, boxes):
    wh = np.maximum(0,np.minimum(box[2:],boxes[:,2:])-np.maximum(box[:2],boxes[:,:2]))
    inter = wh[:,0]*wh[:,1]
    area = np.maximum(0,boxes[:,2]-boxes[:,0])*np.maximum(0,boxes[:,3]-boxes[:,1])
    own = max(0,float(box[2]-box[0]))*max(0,float(box[3]-box[1]))
    return inter / np.maximum(own+area-inter,1e-12)


def decode(raw, confidence=(.25,.25,.25,.25), nms_iou=.45, restore=True, max_det=300):
    """Postprocess this model's already-decoded cxcywh/probability output.

    Select one best class per row, multiply objectness once, apply that class's
    inclusive threshold and classwise float NMS (suppress only IoU > nms_iou).
    No sigmoid or anchor/grid decoding is needed. Stable score ties use raw row
    order. Return float32 [N,6]: xyxy, score, class, sorted by class/x/y.

    With restore=True, exclude boxes with no visible image area before NMS and
    the global max_det limit, then map x*2, (y-40)*2 exactly once and clip to
    640x480. NMS still uses unclipped canvas boxes. restore=False retains canvas
    coordinates for evaluation, including valid boxes inside the padding.
    """
    if not isinstance(raw, np.ndarray) or raw.shape != (1,6300,9) or raw.dtype != np.float32 or not np.isfinite(raw).all():
        raise ValueError('Output must be finite float32 [1,6300,9]')
    if np.any(raw[...,2:4] < 0) or np.any(raw[...,4:] < -1e-5) or np.any(raw[...,4:] > 1.00001):
        raise ValueError('Unexpected decoded box/probability layout')
    try:
        thresholds=np.asarray(confidence,dtype=np.float32)
        valid_iou=(isinstance(nms_iou,(int,float,np.integer,np.floating)) and
                   not isinstance(nms_iou,(bool,np.bool_)) and 0<nms_iou<1)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError('Four class thresholds and valid NMS IoU required') from exc
    if thresholds.shape != (4,) or not ((thresholds>0)&(thresholds<=1)).all() or not valid_iou:
        raise ValueError('Four class thresholds and valid NMS IoU required')
    if isinstance(max_det,(bool,np.bool_)) or not isinstance(max_det,(int,np.integer)) or max_det<1:
        raise ValueError('max_det must be a positive integer')
    if not isinstance(restore,(bool,np.bool_)):
        raise ValueError('restore must be boolean')
    p=raw[0];cls=p[:,5:].argmax(1);score=p[:,4]*p[np.arange(len(p)),5+cls]
    mask=score>=thresholds[cls];p=p[mask];cls=cls[mask];score=score[mask]
    if not len(p):return np.zeros((0,6),np.float32)
    xyxy=np.concatenate((p[:,:2]-p[:,2:4]/2,p[:,:2]+p[:,2:4]/2),axis=1)
    valid=(xyxy[:,2]>xyxy[:,0])&(xyxy[:,3]>xyxy[:,1])
    if restore:
        # Visible image in canvas coordinates is [0,40,320,280]. Invalid or
        # padding-only boxes must not consume the cap on returned detections.
        valid &= (xyxy[:,2]>0)&(xyxy[:,0]<320)&(xyxy[:,3]>40)&(xyxy[:,1]<280)
    xyxy=xyxy[valid];cls=cls[valid];score=score[valid]
    if not len(xyxy):return np.zeros((0,6),np.float32)
    order=np.argsort(-score,kind='stable')[:30000];kept=[]
    while len(order) and len(kept)<max_det:
        n=int(order[0]);kept.append(n);rest=order[1:]
        overlap=iou(xyxy[n],xyxy[rest]) if len(rest) else np.zeros(0)
        order=rest[(cls[rest]!=cls[n]) | (overlap<=nms_iou)]
    a=np.column_stack((xyxy[kept],score[kept],cls[kept])).astype(np.float32)
    if restore:
        a[:,[0,2]]*=2;a[:,[1,3]]=(a[:,[1,3]]-40)*2
        a[:,[0,2]]=a[:,[0,2]].clip(0,640);a[:,[1,3]]=a[:,[1,3]].clip(0,480)
        a=a[(a[:,2]>a[:,0])&(a[:,3]>a[:,1])]
    # A canonical, backend-independent output order.
    return a[np.lexsort((a[:,1],a[:,0],a[:,5]))]


def load_model(path, backend='opencv', threads=2):
    if backend=='opencv':
        import cv2
        cv2.setNumThreads(threads)
        net=load_onnx_net(path)
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        def forward(tensor):
            validate_tensor(tensor)
            net.setInput(tensor,'images')
            return net.forward('output0')
        return forward
    if backend=='onnxruntime':
        import onnxruntime as ort
        opt=ort.SessionOptions();opt.intra_op_num_threads=threads;opt.inter_op_num_threads=1
        session=ort.InferenceSession(str(path),sess_options=opt,providers=['CPUExecutionProvider'])
        if session.get_inputs()[0].shape!=[1,3,320,320] or session.get_outputs()[0].shape!=[1,6300,9]:
            raise ValueError('Unexpected model I/O')
        def forward(tensor):
            return session.run(['output0'],{'images':validate_tensor(tensor)})[0]
        return forward
    raise ValueError('Unknown backend')


def compare_detections(actual, reference, coordinate_atol=.06, score_atol=2e-5):
    reference=np.asarray(reference,np.float32).reshape(-1,6)
    if actual.shape!=reference.shape:return False
    used=set()
    # Match by class and coordinates, not by backend score tie ordering.
    for row in reference:
        candidates=[i for i,a in enumerate(actual) if i not in used and a[5]==row[5]]
        if not candidates:return False
        best=min(candidates,key=lambda i:float(np.max(np.abs(actual[i,:4]-row[:4]))))
        if not np.allclose(actual[best,:4],row[:4],atol=coordinate_atol,rtol=1e-4):return False
        if not np.isclose(actual[best,4],row[4],atol=score_atol,rtol=2e-4):return False
        used.add(best)
    return True
