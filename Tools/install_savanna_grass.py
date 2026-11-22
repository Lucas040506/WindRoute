import unreal,csv
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
e=unreal.EditorAssetLibrary; tools=unreal.AssetToolsHelpers.get_asset_tools(); mel=unreal.MaterialEditingLibrary
base='/Game/GliderCanyon_v2/Vegetation'; name='SM_SavannaGrass'
t=unreal.AssetImportTask();t.filename=str(root/'Assets/Vegetation'/f'{name}.fbx');t.destination_path=base;t.destination_name=name;t.automated=True;t.replace_existing=True;t.save=True
ui=unreal.FbxImportUI();ui.import_mesh=True;ui.import_as_skeletal=False;ui.import_materials=False;ui.import_textures=False;ui.static_mesh_import_data.auto_generate_collision=False;ui.static_mesh_import_data.set_editor_property("vertex_color_import_option",unreal.VertexColorImportOption.REPLACE);t.options=ui
tools.import_asset_tasks([t]);paths=t.imported_object_paths
if not paths:raise RuntimeError('Grass mesh import failed')
mesh=unreal.load_asset(paths[0]);unreal.log('SAVANNA_MESH_BOUNDS '+str(mesh.get_bounds()))
colors=[(.27,.43,.075),(.49,.53,.095),(.64,.53,.12)];mats=[]
for i,color in enumerate(colors):
 n=f'M_SavannaGrass_{i}';path=base+'/'+n;mat=e.load_asset(path) if e.does_asset_exist(path) else tools.create_asset(n,base,unreal.Material,unreal.MaterialFactoryNew())
 if not mat:raise RuntimeError('Cannot create '+path)
 node=mel.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-300,0);node.set_editor_property('constant',unreal.LinearColor(*color,1.0));mel.connect_material_property(node,'',unreal.MaterialProperty.MP_BASE_COLOR)
 rough=mel.create_material_expression(mat,unreal.MaterialExpressionConstant,-300,120);rough.set_editor_property('r',.9);mel.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
 # Vertex colour pins roots and allows tips to sway in a gentle world-space breeze.
 color=mel.create_material_expression(mat,unreal.MaterialExpressionVertexColor,-900,450)
 tm=mel.create_material_expression(mat,unreal.MaterialExpressionTime,-1100,100)
 pos=mel.create_material_expression(mat,unreal.MaterialExpressionWorldPosition,-1100,300)
 mask=mel.create_material_expression(mat,unreal.MaterialExpressionComponentMask,-900,300);mask.set_editor_property('r',True)
 spatial=mel.create_material_expression(mat,unreal.MaterialExpressionMultiply,-700,300)
 factor=mel.create_material_expression(mat,unreal.MaterialExpressionConstant,-900,400);factor.set_editor_property('r',.0012)
 add=mel.create_material_expression(mat,unreal.MaterialExpressionAdd,-500,180)
 sine=mel.create_material_expression(mat,unreal.MaterialExpressionSine,-300,250);sine.set_editor_property('period',6.2831853)
 weight=mel.create_material_expression(mat,unreal.MaterialExpressionMultiply,-100,320)
 direction=mel.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-100,450);direction.set_editor_property('constant',unreal.LinearColor(18.0,7.0,0.0,1.0))
 disp=mel.create_material_expression(mat,unreal.MaterialExpressionMultiply,100,320)
 mel.connect_material_expressions(pos,'',mask,'Input');mel.connect_material_expressions(mask,'',spatial,'A');mel.connect_material_expressions(factor,'',spatial,'B')
 mel.connect_material_expressions(tm,'',add,'A');mel.connect_material_expressions(spatial,'',add,'B');mel.connect_material_expressions(add,'',sine,'Input')
 mel.connect_material_expressions(sine,'',weight,'A');mel.connect_material_expressions(color,'R',weight,'B');mel.connect_material_expressions(weight,'',disp,'A');mel.connect_material_expressions(direction,'',disp,'B');mel.connect_material_property(disp,'',unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
 mat.set_editor_property('two_sided',True);mat.set_editor_property('used_with_instanced_static_meshes',True);mel.recompile_material(mat)
 if not e.save_loaded_asset(mat,only_if_is_dirty=False):raise RuntimeError('Cannot save '+path)
 mats.append(mat)
les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);eas=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not les.load_level('/Game/GliderCanyon_v2/Maps/L_GliderCanyon_v2'):raise RuntimeError('Cannot open canyon map')
for a in eas.get_all_level_actors():
 if str(a.get_actor_label()).startswith('SavannaGrass_'):eas.destroy_actor(a)
sds=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);bfl=unreal.SubobjectDataBlueprintFunctionLibrary
groups=[[],[],[]]
with (root/'Assets/Vegetation/savanna_grass_instances.csv').open() as f:
 for r in csv.DictReader(f):
  groups[int(r['variant'])].append(unreal.Transform(unreal.Vector(float(r['x']),float(r['y']),float(r['z'])),unreal.Rotator(roll=0,pitch=0,yaw=float(r['yaw'])),unreal.Vector(float(r['scale']),float(r['scale']),float(r['height']))))
for i,xf in enumerate(groups):
 a=eas.spawn_actor_from_class(unreal.Actor,unreal.Vector(0,0,0));a.set_actor_label(f'SavannaGrass_{i}')
 parent=sds.k2_gather_subobject_data_for_instance(a)[0];h,_=sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=parent,new_class=unreal.HierarchicalInstancedStaticMeshComponent,blueprint_context=None));comp=bfl.get_object(bfl.get_data(h))
 if not comp:raise RuntimeError('HISM creation failed')
 comp.set_static_mesh(mesh);comp.set_material(0,mats[i]);comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION);comp.set_editor_property('cast_shadow',False);comp.set_cull_distances(13500,18000);comp.add_instances(xf,False,True)
 unreal.log(f'SAVANNA_GRASS_VARIANT {i} count={len(xf)}')
if not les.save_current_level():raise RuntimeError('Saving canyon failed')
unreal.log('SAVANNA_GRASS_SAVED')
