import unreal
E=unreal.EditorAssetLibrary
m=E.load_asset('/Game/GliderCanyon_v2/Meshes/M_CanyonPalette')
m.set_editor_property('used_with_instanced_static_meshes',True)
unreal.MaterialEditingLibrary.recompile_material(m)
E.save_loaded_asset(m,only_if_is_dirty=False)
les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert les.load_level('/Game/GliderCanyon_v2/Maps/L_GliderCanyon_v2')
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
 for cls in (unreal.DirectionalLightComponent,unreal.SkyLightComponent):
  c=a.get_component_by_class(cls)
  if c: c.set_mobility(unreal.ComponentMobility.MOVABLE)
assert les.save_current_level()
print('CANYON_FIX_OK')
