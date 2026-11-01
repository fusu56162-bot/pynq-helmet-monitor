"""Install into a chosen traffic_project directory, never overwrite different files."""
import argparse
from materialize import restore
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--destination',required=True);p.add_argument('--check-only',action='store_true');a=p.parse_args()
    restore('board',a.destination,a.check_only)
    print('Open camera_quality_v1/打开我_现场演示_已验证178DSP.ipynb in a NEW kernel after installation.')
