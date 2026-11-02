#!/usr/bin/env python3
"""Compare saved numeric NPY tensors; never execute inference or hardware."""
import argparse
import json
import math
from pathlib import Path
import sys


def compare_paths(reference, candidate, mode='exact', atol=None, rtol=None):
    import numpy as np
    if mode not in {'exact', 'tolerance'}:
        raise ValueError('Unsupported comparison mode')
    if mode == 'tolerance':
        if any(v is None or not math.isfinite(v) or v < 0 for v in (atol, rtol)):
            raise ValueError('Tolerance mode requires explicit finite nonnegative atol and rtol')
    elif atol is not None or rtol is not None:
        raise ValueError('atol/rtol require --mode tolerance')
    a = np.load(str(reference), allow_pickle=False, mmap_mode='r')
    b = np.load(str(candidate), allow_pickle=False, mmap_mode='r')
    if not isinstance(a, np.ndarray) or not isinstance(b, np.ndarray):
        raise ValueError('Inputs must be individual .npy arrays, not archives')
    if a.dtype.kind not in 'biuf' or b.dtype.kind not in 'biuf':
        raise ValueError('Only real numeric or boolean tensors are supported')
    result = {'mode': mode, 'reference': str(Path(reference).resolve()),
              'candidate': str(Path(candidate).resolve()),
              'reference_shape': list(a.shape), 'candidate_shape': list(b.shape),
              'reference_dtype': a.dtype.str, 'candidate_dtype': b.dtype.str,
              'atol': atol, 'rtol': rtol, 'hardware_executed': False}
    if a.shape != b.shape or a.dtype.str != b.dtype.str:
        result.update(passed=False, reason='shape_or_dtype_mismatch')
        return result
    if mode == 'tolerance' and a.dtype.kind != 'f':
        raise ValueError('Use exact mode for integer/boolean tensors')
    mismatches = 0
    first = None
    finite = True
    bit_exact = True
    max_abs = 0.0
    for start in range(0, a.size, 262144):
        x = np.asarray(a.flat[start:start+262144])
        y = np.asarray(b.flat[start:start+262144])
        is_finite = np.isfinite(x) & np.isfinite(y)
        finite = finite and bool(is_finite.all())
        xb = np.ascontiguousarray(x).view(np.uint8).reshape(-1, a.dtype.itemsize)
        yb = np.ascontiguousarray(y).view(np.uint8).reshape(-1, a.dtype.itemsize)
        bit_equal = (xb == yb).all(axis=1)
        bit_exact = bit_exact and bool(bit_equal.all())
        ok = bit_equal & is_finite if mode == 'exact' else np.isclose(
            y, x, atol=atol, rtol=rtol, equal_nan=False) & is_finite
        bad = np.flatnonzero(~ok)
        mismatches += int(bad.size)
        if first is None and bad.size:
            idx = start + int(bad[0])
            first = {'flat_index': idx, 'index': list(np.unravel_index(idx, a.shape)),
                     'reference': str(x[bad[0]].item()), 'candidate': str(y[bad[0]].item())}
        if is_finite.any():
            with np.errstate(over='ignore', invalid='ignore'):
                error = np.abs(x[is_finite].astype(np.float64)-y[is_finite].astype(np.float64))
            if not np.isfinite(error).all():
                max_abs = None
            elif max_abs is not None:
                max_abs = max(max_abs, float(error.max()))
    result.update(passed=finite and mismatches == 0, finite=finite,
                  bit_exact=bit_exact, elements=int(a.size), mismatched_elements=mismatches,
                  first_mismatch=first, max_abs_error_float64_diagnostic=max_abs,
                  reason='comparison_complete')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--mode', choices=['exact', 'tolerance'], default='exact')
    parser.add_argument('--atol', type=float)
    parser.add_argument('--rtol', type=float)
    args = parser.parse_args()
    try:
        result = compare_paths(args.reference, args.candidate, args.mode, args.atol, args.rtol)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False, default=int))
        return 0 if result['passed'] else 1
    except (OSError, ValueError, TypeError, ImportError, EOFError) as exc:
        print(json.dumps({'passed': None, 'error': type(exc).__name__ + ': ' + str(exc),
                          'hardware_executed': False}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
