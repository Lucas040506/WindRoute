import unreal,csv
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve(); base='/Game/Jayant_Chakradhari_Assets/Free_Grass';e=unreal.EditorAssetLibrary;mel=unreal.MaterialEditingLibrary
names=['12','20','23'];meshes=[unreal.load_asset(base+'/Textured_Meshes/Grass_Meshes/SM_Grass_'+n) for n in names];mats=[unreal.load_asset(base+'/Materials/Grass/MI_Grass_'+n) for n in names]
if not all(meshes) or not all(mats):raise RuntimeError('Fab grass assets are missing')
parent=unreal.load_asset(base+'/Materials/Grass/M_Material_Grass_1')
if not parent: raise RuntimeError('Grass master material missing')
if not parent.get_editor_property('used_with_instanced_static_meshes'):
 parent.set_editor_property('used_with_instanced_static_meshes',True);mel.recompile_material(parent)
 if not e.save_loaded_asset(parent,only_if_is_dirty=False):raise RuntimeError('Grass shader save failed')
les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);eas=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not les.load_level('/Game/GliderCanyon_v2/Maps/L_GliderCanyon_v2'):raise RuntimeError('Cannot open target canyon level')
groups=[[],[],[]]
with (root/'Assets/Vegetation/fab_grass_instances.csv').open() as f:
 for r in csv.DictReader(f):groups[int(r['variant'])].append(unreal.Transform(unreal.Vector(float(r['x']),float(r['y']),float(r['z'])),unreal.Rotator(roll=0,pitch=0,yaw=float(r['yaw'])),unreal.Vector(float(r['scale']),float(r['scale']),float(r['height']))))
if min(map(len,groups))<1:raise RuntimeError('Empty placement groups')
old=[a for a in eas.get_all_level_actors() if str(a.get_actor_label()).startswith(('SavannaGrass_','FabGrass_'))]
sds=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);bfl=unreal.SubobjectDataBlueprintFunctionLibrary;created=[]
try:
 for i,xf in enumerate(groups):
  a=eas.spawn_actor_from_class(unreal.Actor,unreal.Vector(0,0,0));created.append(a);a.set_actor_label(f'FabGrass_{i}')
  parent_handle=sds.k2_gather_subobject_data_for_instance(a)[0];h,_=sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=parent_handle,new_class=unreal.HierarchicalInstancedStaticMeshComponent,blueprint_context=None));comp=bfl.get_object(bfl.get_data(h))
  if not comp:raise RuntimeError('Cannot create grass component')
  comp.set_static_mesh(meshes[i]);comp.set_material(0,mats[i]);comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION);comp.set_editor_property('cast_shadow',False);comp.set_cull_distances(25000,34000);comp.add_instances(xf,False,True)
  unreal.log(f'FAB_PLACED variant={names[i]} count={len(xf)}')
 for a in old:eas.destroy_actor(a)
 if not les.save_current_level():raise RuntimeError('Canyon map save failed')
except Exception:
 for a in created:eas.destroy_actor(a)
 raise
unreal.log('FAB_GRASS_CANYON_SAVED')
