"""Generate a centerline from the approved review diagram; does not alter the level."""
import ast, sys, json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter1d, maximum_filter1d
R=Path(__file__).resolve().parents[1]
source=Path('/Users/lucas/HKUST_TLE/ISDN5230/canyon_delivery/GliderCanyon_v2/Generator')
sys.path.insert(0,str(source));import scene_common as terrain
module=ast.parse((R/'Tools/design_route_review.py').read_text())
segments=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='segments' for x in n.targets))
points=[]
for seg,_ in segments:
    points.extend(seg if not points else seg[1:])
points=np.array(points,float)
def catmull(points, count=60):
 p=np.vstack((points[0],points,points[-1])); result=[]
 for i in range(1,len(p)-2):
  a,b,c,d=p[i-1:i+3]
  for t in np.linspace(0,1,count,endpoint=False):
   result.append(.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t**3))
 return np.vstack((result,points[-1]))
p=catmull(points); xy=np.column_stack((p[:,0]*1300/2048,(2048-p[:,1])*1300/2048))
raw_d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]; length=float(raw_d[-1]); d=np.arange(0,length,5.);d=np.r_[d,length]
x=np.interp(d,raw_d,xy[:,0]); y=np.interp(d,raw_d,xy[:,1]); tang=np.column_stack((np.gradient(x),np.gradient(y)));tang/=np.linalg.norm(tang,axis=1)[:,None]
# Sample terrain beneath the centerline, both wings and a 15 m lateral margin.
heights=[]
for lateral in np.arange(-20,21,5):
  heights.append(terrain.height(x-tang[:,1]*lateral,y+tang[:,0]*lateral))
floor=np.max(np.vstack(heights),axis=0)
# Require terrain and vegetation clearance, then allow time to climb before approaching high ground.
required=maximum_filter1d(floor+28,size=13,mode='nearest')
z=required.copy(); max_slope=.24
for i in range(len(d)-2,-1,-1): z[i]=max(z[i],z[i+1]-max_slope*(d[i+1]-d[i]))
for i in range(1,len(d)): z[i]=max(z[i],z[i-1]-max_slope*(d[i]-d[i-1]))
z=gaussian_filter1d(z, sigma=3,mode='nearest')+2
# Smooth terrain interpolation can soften majorant slightly: verify numerical clearance.
clear=z-floor
head=['#pragma once','#include "CoreMinimal.h"','struct FRouteSample { float D,X,Y,Z; };','static const FRouteSample RouteSamples[] = {']
for a,b,c,h in zip(d,x,y,z): head.append(f'{{{a:.3f}f,{b*100:.2f}f,{-c*100:.2f}f,{h*100:.2f}f}},')
head.append('};'); (R/'Source/WindRoute/CanyonRoute.h').write_text('\n'.join(head)+'\n')
control=R/'Source/WindRoute/ControlMath.h';s=control.read_text();import re
s=re.sub(r'constexpr float RouteLengthMeters = [^;]+;',f'constexpr float RouteLengthMeters = {length:.3f}f;',s)
count=int(length//80);s=re.sub(r'constexpr int GateCount = \d+;',f'constexpr int GateCount = {count};',s)
s=s.replace('return 120.f * (std::clamp(Index, 0, GateCount-1) + 1);','return 80.f * (std::clamp(Index, 0, GateCount-1) + 1);');control.write_text(s)
report={'length_m':round(length,2),'gate_count':count,'nominal_interval_s':4,'clearance_center_and_20m_sides_m':round(float(clear.min()),2),'height_min_m':round(float(z.min()),1),'height_max_m':round(float(z.max()),1),'max_height_gradient':round(float(np.max(np.abs(np.gradient(z,d)))),3),'note':'Clearance uses procedural terrain height, not UE collision meshes, foliage, camera, or player deviation.'}
(R/'RouteReview/approved_route_generated.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
