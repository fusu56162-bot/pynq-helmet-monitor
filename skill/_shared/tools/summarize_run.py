#!/usr/bin/env python3
"""Read archived camera RESULT/AUDIT JSON. No inference, device or network use."""
import argparse
import json
import math
from pathlib import Path
import statistics
import sys


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def nonnegative(value):
    return value if number(value) and value >= 0 else None


MAIN_EXCLUSIVE_TIMERS = set(['main.acquire_wait_ms', 'main.camera_decode_ms', 'main.cpu_reference_ms', 'main.decode_ms', 'main.display_publish_ms', 'main.draw_ms', 'main.evidence_snapshot_ms', 'main.exact_compare_ms', 'main.fpga_arm_forward_ms', 'main.jpeg_encode_once_ms', 'main.preprocess_ms', 'main.preview_resize_ms', 'main.report_json_ms', 'main.report_write_close_ms'])

def summarize_result(r):
    frames = r['frames']
    warnings = []
    count = len(frames)
    live_count = nonnegative(r.get('live_fpga_forward_count'))
    if live_count is not None and live_count != count:
        warnings.append('Frame records and live-forward count differ; stored frames may be incomplete.')
    seconds = nonnegative(r.get('loop_seconds'))
    fps_from_records = count/seconds if seconds and (live_count is None or live_count == count) else None
    metrics = []
    for key, value in sorted(r['metrics'].items()):
        if key not in MAIN_EXCLUSIVE_TIMERS or not isinstance(value, dict):
            continue
        total = nonnegative(value.get('total_ms'))
        metrics.append({'name': key, 'events': nonnegative(value.get('count')),
                        'mean_per_event_ms': nonnegative(value.get('mean_ms')),
                        'total_ms': total,
                        'amortized_per_inferred_frame_ms': total/count if total is not None and count and
                            (live_count is None or live_count == count) else None})
    wall = [f.get('iteration_wall_ms') for f in frames if isinstance(f, dict)]
    wall = [v for v in wall if nonnegative(v) is not None]
    suffix = []
    for f in frames:
        if not isinstance(f, dict):
            continue
        timing = f.get('timing', {})
        components = timing.get('components_ms', {}) if isinstance(timing, dict) else {}
        value = components.get('owned_pack_and_suffix_ms') if isinstance(components, dict) else None
        if nonnegative(value) is not None:
            suffix.append(value)
    main_sum = sum(m['amortized_per_inferred_frame_ms'] for m in metrics) if metrics and all(
        m['amortized_per_inferred_frame_ms'] is not None for m in metrics) else None
    mean_wall = statistics.mean(wall) if wall else None
    recorded_fps = nonnegative(r.get('inference_fps'))
    if recorded_fps is not None and fps_from_records is not None and not math.isclose(
            recorded_fps, fps_from_records, rel_tol=0.005, abs_tol=0.001):
        warnings.append('Recorded inference FPS differs from complete frame count / loop_seconds.')
    warnings.append('ARM suffix is nested inside full forward; do not add it to main timers.')
    warnings.append('Background saving and setup/cleanup timers are excluded from the main-timer list.')
    if any(m['events'] != count for m in metrics):
        warnings.append('Some timers occur only on selected frames; use amortized rather than per-event mean.')
    return {
        'schema_recognized': 'project_camera_result', 'source_status': r.get('status'),
        'frame_records': count, 'live_forward_count': live_count,
        'loop_seconds': seconds, 'recorded_inference_fps': recorded_fps,
        'fps_from_complete_frame_records': fps_from_records,
        'capture_read_returns_per_second': nonnegative(r.get('capture_read_returns_per_second')),
        'main_iteration_mean_ms': mean_wall,
        'main_timers': metrics, 'main_timer_sum_ms': main_sum,
        'nonexclusive_or_unknown_main_keys_excluded': sorted(k for k in r['metrics'] if k.startswith('main.') and k not in MAIN_EXCLUSIVE_TIMERS),
        'unattributed_or_timer_overlap_ms': mean_wall-main_sum if mean_wall is not None and main_sum is not None else None,
        'nested_arm_suffix': {'mean_ms': statistics.mean(suffix) if suffix else None,
                              'sample_count': len(suffix), 'included_in': 'main.fpga_arm_forward_ms'},
        'identity': {'model': r.get('model_identity'), 'overlay': r.get('overlay_sha256')},
        'evidence': {key: r.get(key) for key in ['checked_count', 'unchecked_count',
            'checked_frames_all_bit_exact', 'cpu_fallback_enabled', 'capture_worker_stopped',
            'writer_worker_stopped', 'dma_quiesced', 'old_hardware_restored',
            'browser_render_latency_measured', 'saved_frames_count', 'save_queue_dropped']},
        'warnings': warnings,
    }


def summarize_audit(r):
    modes = []
    for value in r['modes']:
        if not isinstance(value, dict):
            raise ValueError('Audit mode must be a dictionary')
        n = nonnegative(value.get('frames'))
        seconds = nonnegative(value.get('seconds'))
        modes.append({key: value.get(key) for key in ['quality', 'width', 'frames', 'seconds',
            'fps', 'iteration_ms', 'bytes_per_jpeg', 'capture_fps', 'checked', 'saved',
            'save_dropped', 'components_mean_ms', 'arm_suffix_merged_mean_ms']})
        modes[-1]['fps_from_frames_and_seconds'] = n/seconds if n is not None and seconds else None
        modes[-1]['nested_arm_suffix_included_in'] = 'components_mean_ms.fpga_arm_forward'
    return {'schema_recognized': 'project_camera_quality_audit', 'source_status': r.get('status'),
            'modes': modes, 'warnings': ['Audit fields are reported, not recomputed from raw hardware execution.',
                'ARM suffix is nested; background saving is not an extra serial stage.',
                'Sequential live-camera runs alone do not establish a stable causal FPS gain.']}


def summarize(r):
    if not isinstance(r, dict):
        raise ValueError('Expected a JSON object')
    if isinstance(r.get('frames'), list) and isinstance(r.get('metrics'), dict):
        return summarize_result(r)
    if isinstance(r.get('modes'), list) and any(isinstance(v, dict) and
            'components_mean_ms' in v for v in r['modes']):
        return summarize_audit(r)
    raise ValueError('Unsupported schema; available keys: ' + ', '.join(sorted(r)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    args = parser.parse_args()
    try:
        r = json.loads(args.result.read_text(encoding='utf-8'))
        result = summarize(r)
        result['source'] = str(args.result.resolve())
        result['hardware_executed'] = False
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'schema_recognized': None, 'error': type(exc).__name__ + ': ' + str(exc),
                          'hardware_executed': False}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
