#!/usr/bin/env python3
"""Read-only SHA256 verification of a flat manifest or a {sha256: {...}} manifest."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):
            h.update(block)
    return h.hexdigest()


def verify(root, manifest):
    root=Path(root).resolve()
    data=manifest if isinstance(manifest,dict) else json.loads(Path(manifest).read_text(encoding='utf-8'))
    label='inline_mapping' if isinstance(manifest,dict) else str(Path(manifest).resolve())
    entries=data.get('sha256') if isinstance(data,dict) and 'sha256' in data else data
    if not isinstance(entries,dict) or not entries:
        raise ValueError('Expected a nonempty relative-path -> SHA256 mapping')
    problems=[]
    good=0
    for name,digest in entries.items():
        if not isinstance(name,str) or not isinstance(digest,str) or not re.fullmatch('[0-9a-fA-F]{64}',digest):
            problems.append({'file':str(name),'reason':'invalid_manifest_entry'});continue
        norm=name.replace('\\','/')
        rel=PurePosixPath(norm)
        if rel.is_absolute() or '..' in rel.parts or re.match(r'^[A-Za-z]:',norm):
            problems.append({'file':name,'reason':'outside_root_path'});continue
        p=(root/Path(*rel.parts)).resolve()
        try:p.relative_to(root)
        except ValueError:
            problems.append({'file':name,'reason':'symlink_outside_root'});continue
        if not p.is_file():
            problems.append({'file':name,'reason':'missing_file'});continue
        try:actual=sha(p)
        except OSError as exc:
            problems.append({'file':name,'reason':'read_error','error':str(exc)});continue
        if actual.lower()!=digest.lower():
            problems.append({'file':name,'reason':'sha256_mismatch','actual':actual})
        else:good+=1
    return {'status':'FILES_VERIFIED' if not problems else 'FILES_NOT_VERIFIED',
            'root':str(root),'manifest':label,'verified_files':good,
            'listed_files':len(entries),'problems':problems,'hardware_accessed':False,
            'scope':'Listed files only; extra files are not silently certified.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--manifest',type=Path)
    a=ap.parse_args()
    try:
        m=a.manifest or next((a.root/n for n in ('manifest.json','SOURCE_MANIFEST.json','MANIFEST.json') if (a.root/n).is_file()),a.root/'manifest.json')
        r=verify(a.root,m);print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if not r['problems'] else 1
    except (OSError,ValueError,TypeError) as e:
        print(json.dumps({'error':type(e).__name__+': '+str(e),'hardware_accessed':False},ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
