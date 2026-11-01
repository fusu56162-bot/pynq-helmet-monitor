#!/usr/bin/env python3
"""Parse project hierarchical utilization and Design Timing Summary; no Vivado run."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


def parse_reports(utilization,timing):
    up,tp=Path(utilization),Path(timing)
    u,t=up.read_text(encoding='utf-8',errors='replace'),tp.read_text(encoding='utf-8',errors='replace')
    header=None;resource=None
    for line in u.splitlines():
        if not line.strip().startswith('|'):continue
        cells=[s.strip() for s in line.strip().strip('|').split('|')]
        if 'Total LUTs' in cells and 'DSP Blocks' in cells:
            header=cells;continue
        if header and len(cells)==len(header) and cells[1]=='(top)' and not cells[0].startswith('('):
            row=dict(zip(header,cells))
            val=lambda k:int(row[k].replace(',',''))
            resource={'top_instance':row['Instance'],'LUT':val('Total LUTs'),'FF':val('FFs'),
                      'RAMB36':val('RAMB36'),'RAMB18':val('RAMB18'),'DSP':val('DSP Blocks')}
            resource['BRAM_tiles']=resource['RAMB36']+resource['RAMB18']/2
            break
    if resource is None:raise ValueError('Recognized top-level hierarchical utilization row missing')
    lines=t.splitlines();summary=None
    for i,line in enumerate(lines):
        if not line.strip().startswith('WNS(ns)'):continue
        for row in lines[i+1:i+5]:
            values=row.split()
            if len(values)==12 and re.fullmatch(r'-?\d+(?:\.\d+)?',values[0]):
                summary={'WNS_ns':float(values[0]),'TNS_ns':float(values[1]),
                         'setup_failing_endpoints':int(values[2]),'setup_total_endpoints':int(values[3]),
                         'WHS_ns':float(values[4]),'THS_ns':float(values[5]),
                         'hold_failing_endpoints':int(values[6]),'hold_total_endpoints':int(values[7]),
                         'WPWS_ns':float(values[8]),'TPWS_ns':float(values[9]),
                         'pulse_failing_endpoints':int(values[10]),'pulse_total_endpoints':int(values[11])}
                break
        if summary is not None:break
    if summary is None:raise ValueError('Design Timing Summary numeric row missing')
    coverage={}
    for key in ['no_clock','unconstrained_internal_endpoints','no_input_delay','no_output_delay']:
        m=re.search(r'checking\s+'+key+r'\s*\((\d+)\)',t)
        coverage[key]=int(m.group(1)) if m else None
    state=re.search(r'\|\s*Design State\s*:\s*([^\r\n|]+)',u)
    return {'status':'REPORTS_PARSED_NOT_BOARD_ACCEPTANCE','resource':resource,'timing':summary,
            'reported_constraint_counts':coverage,'design_state':state.group(1).strip() if state else None,
            'checks':{'summary_slacks_nonnegative':all(summary[k]>=0 for k in ['WNS_ns','WHS_ns','WPWS_ns']),
                      'summary_failing_endpoints_zero':all(summary[k]==0 for k in
                        ['setup_failing_endpoints','hold_failing_endpoints','pulse_failing_endpoints'])},
            'sha256':{up.name:hashlib.sha256(up.read_bytes()).hexdigest(),
                      tp.name:hashlib.sha256(tp.read_bytes()).hexdigest()},
            'limitation':'Parsing is not timing signoff. Missing checks stay unknown; inspect exceptions, IO constraints, warnings and matching bitstream.',
            'hardware_accessed':False}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--utilization',type=Path,required=True);ap.add_argument('--timing',type=Path,required=True)
    a=ap.parse_args()
    try:
        r=parse_reports(a.utilization,a.timing);print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if all(r['checks'].values()) else 1
    except (OSError,ValueError,KeyError,IndexError,TypeError) as e:print(json.dumps({'error':str(e)},ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
