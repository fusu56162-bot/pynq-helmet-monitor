"""Materialize a new source workspace and launch AMD tools; never program a board."""
from pathlib import Path
import argparse,subprocess
from materialize import restore
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--phase',choices=['create_only','full','csim','synthesis','cosim','package'],default='create_only')
    p.add_argument('--vivado',default='vivado');p.add_argument('--vitis-run',default='vitis-run');p.add_argument('--vpp',default='v++');a=p.parse_args()
    root=Path(a.output).resolve()
    if root.exists():raise RuntimeError('Use a new output directory')
    restore('pl',root)
    if a.phase in ('create_only','full'):
        cmd=[a.vivado,'-mode','batch','-source',str(root/'vivado/build_detection.tcl'),'-tclargs',a.phase];cwd=root
    else:
        cwd=root/'hls_float_chain_compact'
        if a.phase=='synthesis':cmd=[a.vpp,'-c','--mode','hls','--config','hls_config.cfg','--work_dir','build']
        else:cmd=[a.vitis_run,'--mode','hls','--config','hls_config.cfg','--work_dir','build','--'+a.phase]
    subprocess.run(cmd,cwd=cwd,check=True)
