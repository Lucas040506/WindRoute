import struct, json, numpy as np, io, subprocess
from PIL import Image
b=open('deliver/GliderCanyon_v2/GliderCanyon_v2_Scene.glb','rb').read()
m,v,l=struct.unpack('<III',b[:12]); assert m==0x46546C67 and v==2 and l==len(b)
jl,_=struct.unpack('<II',b[12:20]); js=json.loads(b[20:20+jl]); o=20+jl; bl,_=struct.unpack('<II',b[o:o+8]); bb=b[o+8:o+8+bl]
def acc(i):
    a=js['accessors'][i]; bv=js['bufferViews'][a['bufferView']]; n={'VEC3':3,'VEC2':2}[a['type']]
    arr=np.frombuffer(bb,np.float32,a['count']*n,bv['byteOffset']).reshape(-1,n)
    if 'min' in a: assert np.allclose(arr.min(0),a['min']) and np.allclose(arr.max(0),a['max'])
    return arr
ibv=js['bufferViews'][js['images'][0]['bufferView']]; tex=np.array(Image.open(io.BytesIO(bb[ibv['byteOffset']:ibv['byteOffset']+ibv['byteLength']])))
cache={}
Ts=[];Cs=[]
for nd in js['nodes']:
    if nd['name'] in ('SM_FlightPath_Guide','SM_Glider_Placeholder'): continue
    if nd['mesh'] not in cache:
        pr=js['meshes'][nd['mesh']]['primitives'][0]; P=acc(pr['attributes']['POSITION']).astype(np.float64); UV=acc(pr['attributes']['TEXCOORD_0'])
        px=(UV[::3]*tex.shape[0]).astype(int); cache[nd['mesh']]=(P,tex[px[:,1],px[:,0]])
    P,C=cache[nd['mesh']]
    if 'matrix' in nd:
        M=np.array(nd['matrix']).reshape(4,4).T; P=P@M[:3,:3].T+M[:3,3]
    Ts.append(np.stack([P[:,0],-P[:,2],P[:,1]],1).reshape(-1,3,3)); Cs.append(C)
T=np.concatenate(Ts).astype(np.float32); C=np.concatenate(Cs).astype(np.uint8)
print('nodes',len(js['nodes']),'meshes',len(js['meshes']),'expanded tris',len(T))
with open('build/static_glb.bin','wb') as f: f.write(struct.pack('i',len(T))); f.write(T.tobytes()); f.write(C.tobytes())
import os; env=dict(os.environ,SMBOX="-450 -450 1750 1750")
r=subprocess.run(['build/raster','build/static_glb.bin','build/frames_top.bin','1024','1024','2'],capture_output=True,check=True,env=env)
a=np.frombuffer(r.stdout,np.uint8).reshape(1024,1024,3).astype(int)
ref=np.array(Image.open('out/topview_v2_clean.png').resize((1024,1024),Image.BOX)).astype(int)
print('GLB re-render vs original top view: mean abs diff',np.abs(a-ref).mean().round(2),'/255')
