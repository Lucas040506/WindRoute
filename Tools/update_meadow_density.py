import unreal,csv
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve();base='/Game/GliderCanyon_v2/Vegetation'
mesh=unreal.load_asset(base+'/SM_SavannaGrass');mats=[unreal.load_asset(base+f'/M_SavannaGrass_{i}') for i in range(3)]
if not mesh or not all(mats):raise RuntimeError('Missing existing provisional grass assets')
les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);eas=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not les.load_level('/Game/GliderCanyon_v2/Maps/L_GliderCanyon_v2'):raise RuntimeError('Cannot open map')
for a in eas.get_all_level_actors():
 if str(a.get_actor_label()).startswith('SavannaGrass_'):eas.destroy_actor(a)
sds=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);bfl=unreal.SubobjectDataBlueprintFunctionLibrary;groups=[[],[],[]]
with (root/'Assets/Vegetation/savanna_grass_instances.csv').open() as f:
 for r in csv.DictReader(f):groups[int(r['variant'])].append(unreal.Transform(unreal.Vector(float(r['x']),float(r['y']),float(r['z'])),unreal.Rotator(roll=0,pitch=0,yaw=float(r['yaw'])),unreal.Vector(float(r['scale']),float(r['scale']),float(r['height']))))
for i,xf in enumerate(groups):
 a=eas.spawn_actor_from_class(unreal.Actor,unreal.Vector(0,0,0));a.set_actor_label(f'SavannaGrass_{i}')
 parent=sds.k2_gather_subobject_data_for_instance(a)[0];h,_=sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=parent,new_class=unreal.HierarchicalInstancedStaticMeshComponent,blueprint_context=None));comp=bfl.get_object(bfl.get_data(h))
 if not comp:raise RuntimeError('HISM creation failed')
 comp.set_static_mesh(mesh);comp.set_material(0,mats[i]);comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION);comp.set_editor_property('cast_shadow',False);comp.set_cull_distances(13500,18000);comp.add_instances(xf,False,True)
 unreal.log(f'MEADOW_DENSITY_VARIANT {i} count={len(xf)}')
if not les.save_current_level():raise RuntimeError('Map save failed')
unreal.log('MEADOW_DENSITY_SAVED')
