import unreal
les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not les.load_level('/Game/GliderCanyon_v2/Maps/L_GliderCanyon_v2'): raise RuntimeError('Cannot open canyon map')
count=0
for actor in eas.get_all_level_actors():
 if not str(actor.get_actor_label()).startswith('FabGrass_'): continue
 components=actor.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
 for comp in components:
  comp.set_cull_distances(25000,34000)
  unreal.log('GRASS_CULL_UPDATED '+str(actor.get_actor_label())+' instances='+str(comp.get_instance_count())+' start_cm=25000 end_cm=34000')
  count+=1
if count!=3:raise RuntimeError('Expected 3 grass components; found '+str(count))
if not les.save_current_level():raise RuntimeError('Cannot save canyon level')
unreal.log('GRASS_CULL_DISTANCE_SAVED')
