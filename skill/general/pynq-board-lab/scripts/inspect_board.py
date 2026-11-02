#!/usr/bin/env python3
"""Read-only host inventory. No device opens, PYNQ imports, MMIO or network."""
import argparse
import datetime
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import sys


def read_optional(path, errors):
    try:
        with Path(path).open('rb') as stream:
            return stream.read(32768).replace(b'\x00', b' ').decode('utf-8', errors='replace').strip()
    except FileNotFoundError:
        return None
    except OSError as exc:
        errors.append({'path': str(path), 'error': type(exc).__name__ + ': ' + str(exc)})
        return None


def parse_meminfo(text):
    result = {}
    for line in (text or '').splitlines():
        key, _, value = line.partition(':')
        if key not in {'MemTotal', 'MemAvailable', 'CmaTotal', 'CmaFree'}:
            continue
        fields = value.split()
        if len(fields) == 2 and fields[1] == 'kB' and fields[0].isdigit():
            result[key + '_bytes'] = int(fields[0]) * 1024
    return result


def disk_inventory(path, errors):
    path = Path(path).expanduser().resolve()
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    result = {'requested_path': str(path), 'requested_path_exists': path.exists(),
              'capacity_probe_path': str(probe)}
    try:
        usage = shutil.disk_usage(str(probe))
        result.update(total_bytes=usage.total, used_bytes=usage.used, free_bytes=usage.free)
    except OSError as exc:
        errors.append({'path': str(probe), 'error': type(exc).__name__ + ': ' + str(exc)})
    return result


def linux_inventory(root, errors):
    root = Path(root)
    result = {
        'device_tree_model': read_optional(root/'proc/device-tree/model', errors),
        'os_release': read_optional(root/'etc/os-release', errors),
        'memory': parse_meminfo(read_optional(root/'proc/meminfo', errors)),
        'video_nodes': [], 'fpga_manager_states': [],
    }
    try:
        for node in sorted((root/'sys/class/video4linux').glob('video*')):
            result['video_nodes'].append({'device_node': '/dev/' + node.name,
                                         'sysfs_name': read_optional(node/'name', errors)})
        for node in sorted((root/'sys/class/fpga_manager').glob('*')):
            result['fpga_manager_states'].append({'manager': node.name,
                'state': read_optional(node/'state', errors),
                'meaning': 'driver-reported state; not bitstream identity or numeric validation'})
    except OSError as exc:
        errors.append({'path': str(root/'sys/class'), 'error': type(exc).__name__ + ': ' + str(exc)})
    return result


def collect(project=None):
    errors = []
    versions = {}
    for name in ['pynq', 'numpy', 'opencv-python', 'opencv-python-headless', 'ncnn']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
        except (OSError, ValueError) as exc:
            versions[name] = None
            errors.append({'package': name, 'error': str(exc)})
    result = {
        'schema': 'pynq-host-inventory-v1',
        'status': 'INVENTORY_ONLY_NOT_HARDWARE_TEST',
        'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'hardware_test_performed': False,
        'actions_not_performed': ['camera_open', 'overlay_download', 'mmio_access',
                                  'dma_start', 'cma_allocation', 'network_access'],
        'host': {'hostname': platform.node(), 'system': platform.system(),
                 'release': platform.release(), 'machine': platform.machine(),
                 'pointer_bits': struct.calcsize('P') * 8,
                 'python': platform.python_version(), 'python_executable': sys.executable},
        'installed_distribution_versions': versions,
        'distribution_version_note': 'Missing metadata is unknown; native libraries may still exist.',
        'disk': disk_inventory(project if project is not None else Path.cwd(), errors),
        'linux': linux_inventory(Path('/'), errors) if platform.system() == 'Linux' else None,
        'tools_present': {name: shutil.which(name) is not None for name in
                          ['v4l2-ctl', 'ip', 'df', 'du', 'ss', 'fuser']},
        'errors': errors,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, help='Target path for filesystem capacity; never scanned recursively.')
    parser.add_argument('--output', type=Path, help='Create a JSON report; refuse to overwrite an existing file.')
    args = parser.parse_args()
    try:
        result = collect(args.project)
        payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output is not None:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(payload)
        sys.stdout.write(payload)
        return 0
    except (OSError, ValueError) as exc:
        sys.stderr.write(type(exc).__name__ + ': ' + str(exc) + '\n')
        return 2


if __name__ == '__main__':
    sys.exit(main())
