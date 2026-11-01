"""Maximum-weight one-to-one assignment with unmatched dummies; no SciPy dependency."""
import math


def maximum_weight_matching(weights):
    n=len(weights)
    if not n:return []
    m=len(weights[0])
    if any(len(r)!=m for r in weights):raise ValueError('rectangular weights required')
    if not m:return []
    original=[[float(x) for x in row] for row in weights]
    if not all(math.isfinite(x) for r in original for x in r):raise ValueError('nonfinite matching weight')
    a=[[max(0.,x) for x in row]+[0.]*n for row in original]
    m+=n;u=[0.]*(n+1);v=[0.]*(m+1);p=[0]*(m+1);way=[0]*(m+1)
    for i in range(1,n+1):
        p[0]=i;j0=0;minimum=[float('inf')]*(m+1);used=[False]*(m+1)
        while True:
            used[j0]=True;i0=p[j0];delta=float('inf');j1=0
            for j in range(1,m+1):
                if used[j]:continue
                cur=-a[i0-1][j-1]-u[i0]-v[j]
                if cur<minimum[j]:minimum[j]=cur;way[j]=j0
                if minimum[j]<delta:delta=minimum[j];j1=j
            for j in range(m+1):
                if used[j]:u[p[j]]+=delta;v[j]-=delta
                else:minimum[j]-=delta
            j0=j1
            if p[j0]==0:break
        while True:
            j1=way[j0];p[j0]=p[j1];j0=j1
            if j0==0:break
    return sorted((p[j]-1,j-1) for j in range(1,m+1) if p[j] and j<=len(weights[0]) and weights[p[j]-1][j-1]>0)
