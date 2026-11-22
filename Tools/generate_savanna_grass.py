"""Generate an original low-poly grass clump and terrain-sampled instance positions."""
import bpy, math, random, csv
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path('/Users/lucas/HKUST_TLE/ISDN5230/windroute_canyon')
obj=Path('/Users/lucas/HKUST_TLE/ISDN5230/canyon_delivery/GliderCanyon_v2/Meshes_OBJ/SM_Terrain_Play.obj')
verts=[]; faces=[]
with obj.open() as f:
 for line in f:
  if line.startswith('v '):
   a=line.split();verts.append((float(a[1]),-float(a[3]),float(a[2])))
  elif line.startswith('f '):
   ids=[int(v.split('/')[0])-1 for v in line.split()[1:]]
   if len(ids)>=3:faces.append(tuple(ids))
tree=BVHTree.FromPolygons(verts,faces,all_triangles=True)
rng=random.Random(172903)
# Multiple individually pointed blades on a wide, uneven clump, locally modeled in metres.
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
v=[];f=[];weights=[]
for i in range(14):
 angle=rng.uniform(0,math.tau);rad=2.7*math.sqrt(rng.random());x=rad*math.cos(angle);y=rad*math.sin(angle)
 a=rng.uniform(0,math.tau);w=rng.uniform(.10,.20);h=rng.uniform(1.15,2.25);lean=rng.uniform(.25,.85);dx=math.cos(a)*w;dy=math.sin(a)*w
 lx=math.cos(a+1.0)*lean;ly=math.sin(a+1.0)*lean;z=rng.uniform(-.1,.02);idx=len(v)
 v.extend([(x-dx,y-dy,z),(x+dx,y+dy,z),(x-dx*.65+lx*.3,y-dy*.65+ly*.3,h*.53),(x+dx*.65+lx*.3,y+dy*.65+ly*.3,h*.53),(x+lx,y+ly,h)])
 weights.extend([0,0,.35,.35,1]);f.extend([(idx,idx+1,idx+3),(idx,idx+3,idx+2),(idx+2,idx+3,idx+4)])
mesh=bpy.data.meshes.new('SM_SavannaGrass');mesh.from_pydata(v,[],f);mesh.update()
colors=mesh.color_attributes.new(name='WindWeight',type='BYTE_COLOR',domain='CORNER')
for poly in mesh.polygons:
 for li in poly.loop_indices:
  weight=weights[mesh.loops[li].vertex_index];colors.data[li].color=(weight,weight,weight,1.0)
ob=bpy.data.objects.new('SM_SavannaGrass',mesh);bpy.context.collection.objects.link(ob);ob.select_set(True);bpy.context.view_layer.objects.active=ob
bpy.ops.export_scene.fbx(filepath=str(root/'Assets/Vegetation/SM_SavannaGrass.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,axis_forward='-Y',axis_up='Z',add_leaf_bones=False,bake_space_transform=False)
rows=[]
# Patchy savanna, with gaps, no grass on steep cliffs or mountain slopes.
for yi in range(120,1210,6):
 for xi in range(430,1240,6):
  x=xi+rng.uniform(-2.5,2.5);y=yi+rng.uniform(-2.5,2.5)
  if math.hypot(x-835,y-650)<210:continue
  pattern=(math.sin(x*.020+y*.013)+math.sin(y*.030-x*.012)+math.cos(x*.008-y*.021))/3
  if rng.random() > max(.10,min(.76,.51+.30*pattern)):continue
  hit,n,idx,dist=tree.ray_cast(Vector((x,y,800)),Vector((0,0,-1)),1200)
  if hit is None or n.z<.88:continue
  typ=rng.choices([0,1,2],[.48,.34,.18])[0]
  sc=rng.uniform(.8,1.35);rows.append((typ,round(x*100,2),round(-y*100,2),round((hit.z-.20)*100,2),round(rng.uniform(0,360),2),round(sc,3),round(rng.uniform(.85,1.2),3)))
with (root/'Assets/Vegetation/savanna_grass_instances.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['variant','x','y','z','yaw','scale','height']);w.writerows(rows)
print('SAVANNA_MESH_AND_INSTANCES',len(rows))
