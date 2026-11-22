import struct, json, numpy as np, sys, io
from PIL import Image
sys.path.insert(0,'.')
def read_glb(p):
    b=open(p,'rb').read(); magic,ver,ln=struct.unpack('<III',b[:12]); assert magic==0x46546C67 and ver==2 and ln==len(b)
    jl,jt=struct.unpack('<II',b[12:20]); js=json.loads(b[20:20+jl]); o=20+jl; bl,bt=struct.unpack('<II',b[o:o+8]); assert bt==0x004E4942
    binb=b[o+8:o+8+bl]; return js,binb
def acc(js,binb,i):
    a=js['accessors'][i]; bv=js['bufferViews'][a['bufferView']]; n={'VEC3':3,'VEC2':2}[a['type']]
    arr=np.frombuffer(binb,np.float32,a['count']*n,bv['byteOffset']).reshape(-1,n)
    if 'min' in a: assert np.allclose(arr.min(0),a['min']) and np.allclose(arr.max(0),a['max'])
    return arr
js,binb=read_glb('deliver/GliderCanyon_Sample/GliderCanyon_Scene.glb')
img=Image.open(io.BytesIO(binb[js['bufferViews'][js['images'][0]['bufferView']]['byteOffset']:][:js['bufferViews'][js['images'][0]['bufferView']]['byteLength']])); img.load()
print('nodes',[n['name'] for n in js['nodes']]); print('texture',img.size)
Z=np.load('build/scene.npz'); pal=Z['palette']; tex=np.array(img)
allT=[];allC=[]
for nd in js['nodes']:
    pr=js['meshes'][nd['mesh']]['primitives'][0]
    P=acc(js,binb,pr['attributes']['POSITION']); UV=acc(js,binb,pr['attributes']['TEXCOORD_0']); N=acc(js,binb,pr['attributes']['NORMAL'])
    assert np.allclose(np.linalg.norm(N,axis=1),1,atol=1e-3)
    if 'matrix' in nd:
        M=np.array(nd['matrix']).reshape(4,4).T; P=(P@M[:3,:3].T)+M[:3,3]
    Pz=np.stack([P[:,0],-P[:,2],P[:,1]],1)  # back to Z-up
    T=Pz.reshape(-1,3,3)
    px=(UV[::3]*tex.shape[0]).astype(int); C=tex[px[:,1],px[:,0]]
    key=nd['name'][3:] if nd['name'].startswith('SM_') else nd['name']
    if 'v_'+key in Z.files:
        src=Z['v_'+key]; err=np.abs(src-T).max(); cerr=np.abs(pal[Z['p_'+key]].astype(int)-C).max()
        print(f'{nd["name"]:24s} tris {len(T):6d}  max pos err {err:.2e} m  colour err {cerr}')
    elif nd['name'].startswith('Ring_'):
        src=Z['v_'+nd['name']]; print(f'{nd["name"]:24s} ring instance pos err {np.abs(src-T).max():.2e} m')
    if nd['name'] not in ('SM_FlightPath_Guide','SM_Glider_Placeholder'):
        allT.append(T); allC.append(C)
T=np.concatenate(allT).astype(np.float32); C=np.concatenate(allC).astype(np.uint8)
with open('build/static_glb.bin','wb') as f:
    f.write(struct.pack('i',len(T))); f.write(T.tobytes()); f.write(C.tobytes())
import subprocess
r=subprocess.run(['build/raster','build/static_glb.bin','build/frames_top.bin','1024','1024','2'],capture_output=True,check=True)
a=np.frombuffer(r.stdout,np.uint8).reshape(1024,1024,3).astype(int)
b=np.array(Image.open('out/topview_clean.png').resize((1024,1024),Image.BOX)).astype(int)
print('GLB re-render vs original top view: mean abs diff',np.abs(a-b).mean().round(2),'/255')
