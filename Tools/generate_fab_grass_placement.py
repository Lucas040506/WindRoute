"""Scatter Fab grass cards in varied groups using the existing meadow density mask."""
import bpy,random,csv,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pathlib import Path
root=Path('/Users/lucas/HKUST_TLE/ISDN5230/windroute_canyon')
path=Path('/Users/lucas/HKUST_TLE/ISDN5230/canyon_delivery/GliderCanyon_v2/Meshes_OBJ/SM_Terrain_Play.obj')
v=[];f=[]
with path.open() as fh:
 for ln in fh:
  if ln.startswith('v '):
   p=ln.split();v.append((float(p[1]),-float(p[3]),float(p[2])))
  elif ln.startswith('f '):f.append(tuple(int(i.split('/')[0])-1 for i in ln.split()[1:]))
tree=BVHTree.FromPolygons(v,f,all_triangles=True);rnd=random.Random(32892);rows=[]
with (root/'Assets/Vegetation/savanna_grass_instances.csv').open() as fh:
 for r in csv.DictReader(fh):
  x=float(r['x'])/100;y=-float(r['y'])/100
  for j in range(15):
   theta=rnd.uniform(0,2*math.pi);rad=2.2*math.sqrt(rnd.random());xx=x+rad*math.cos(theta);yy=y+rad*math.sin(theta)
   hit,n,_,_=tree.ray_cast(Vector((xx,yy,800)),Vector((0,0,-1)),1200)
   if hit is None or n.z<.87:continue
   typ=rnd.choices([0,1,2],[.38,.34,.28])[0]
   scale=rnd.uniform(.8,1.4);height=rnd.uniform(.75,1.2)
   rows.append((typ,round(xx*100,2),round(-yy*100,2),round((hit.z-.12)*100,2),round(rnd.uniform(0,360),2),round(scale,3),round(height,3)))
with (root/'Assets/Vegetation/fab_grass_instances.csv').open('w',newline='') as fh:
 w=csv.writer(fh);w.writerow(['variant','x','y','z','yaw','scale','height']);w.writerows(rows)
print('FAB_GRASS_INSTANCES',len(rows))
