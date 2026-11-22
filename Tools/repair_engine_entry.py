import unreal
les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert les.load_level('/Engine/Maps/Entry')
for a in eas.get_all_level_actors():
    if not isinstance(a, unreal.WorldSettings): eas.destroy_actor(a)
assert les.save_current_level()
print('ENTRY_RESET_TO_EMPTY')
